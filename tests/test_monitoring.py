"""Monitoring-loop unit tests — submit, reconcile, dedup, stale, resilience.

IO-free (Rule 9): everything runs against a StateStore and the controllable
``MockBrokerAdapter``; no network, no real broker, no sleep. The loop's body is
exercised through ``run_monitoring_tick`` / the two step functions directly, not
the ``while True``/``sleep`` wrapper.

Run through ``any_store`` where it proves the loop behaves identically against
InMemoryStateStore and SqliteStateStore.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.broker.adapter import BrokerError, BrokerFill, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import CandidateStatus, OrderStatus, utcnow
from app.monitoring import (
    _recover_unpersisted_submits,
    _reconcile_open_orders,
    _submit_pending_orders,
    run_monitoring_tick,
)
from app.store.base import OrderTransitionError
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _created_order(store, *, symbol="AAPL", qty=100, limit=2.0):
    """An order freshly created by the approval handoff — status CREATED."""

    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(candidate.id)


# --------------------------------------------------------------------------- #
# Submit
# --------------------------------------------------------------------------- #
async def test_submit_marks_created_order_submitted_with_broker_id(any_store):
    order = await _created_order(any_store)
    adapter = MockBrokerAdapter()

    await _submit_pending_orders(any_store, adapter)

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.SUBMITTED
    assert fresh.broker_order_id == adapter.broker_id_for(order.id)
    assert fresh.submitted_at is not None
    # The adapter was asked to submit exactly this order, once.
    assert [o.id for o in adapter.submitted] == [order.id]


async def test_submit_failure_leaves_order_created_and_retries(any_store):
    order = await _created_order(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("alpaca down"))

    # First attempt fails: order stays CREATED, no broker id, loop does not raise.
    await _submit_pending_orders(any_store, adapter)
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.CREATED
    assert fresh.broker_order_id is None

    # Next tick retries and succeeds.
    await _submit_pending_orders(any_store, adapter)
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.SUBMITTED
    assert fresh.broker_order_id == adapter.broker_id_for(order.id)


# --------------------------------------------------------------------------- #
# Reconcile: fills drive position; status advances
# --------------------------------------------------------------------------- #
async def test_full_fill_updates_order_and_position(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.FILLED
    assert fresh.filled_quantity == 100
    pos = await any_store.get_position("AAPL")
    assert pos.quantity == 100
    assert pos.average_price == 2.0


async def test_partial_then_full_fill(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    # First poll: 40 filled.
    adapter.make_fill(
        order.id,
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=40,
        fills=[BrokerFill("exec-1", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.PARTIALLY_FILLED
    assert fresh.filled_quantity == 40
    assert (await any_store.get_position("AAPL")).quantity == 40

    # Second poll: the broker reports the first fill again (replayed) plus a new
    # one totalling the rest. The replay is deduped; only the new 60 appends.
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[
            BrokerFill("exec-1", 40, 2.0, utcnow()),  # duplicate
            BrokerFill("exec-2", 60, 2.0, utcnow()),  # new
        ],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.FILLED
    assert fresh.filled_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 100
    # Exactly two fills were appended (the replay was ignored, not double-counted).
    assert len(await any_store.list_fills(order_id=order.id)) == 2


async def test_duplicate_fill_replay_is_ignored(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    # The order stays partially filled across two identical polls.
    adapter.make_fill(
        order.id,
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=40,
        fills=[BrokerFill("exec-1", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())
    await _reconcile_open_orders(any_store, adapter, Settings())  # same fill again

    assert len(await any_store.list_fills(order_id=order.id)) == 1
    assert (await any_store.get_position("AAPL")).quantity == 40
    dup_events = [
        e
        for e in await any_store.list_events()
        if e.event_type == "fill_duplicate_ignored" and e.order_id == order.id
    ]
    assert len(dup_events) >= 1


# --------------------------------------------------------------------------- #
# Reconcile: defensive — a glitchy broker value never corrupts the order
# --------------------------------------------------------------------------- #
async def test_overfill_report_is_rejected_not_corrupting(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    # Broker erroneously reports more filled than the order's quantity.
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=150,
        fills=[BrokerFill("exec-bad", 150, 2.0, utcnow())],
    )
    # Must not raise, must not corrupt.
    await _reconcile_open_orders(any_store, adapter, Settings())

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.SUBMITTED  # transition rejected
    assert fresh.filled_quantity == 0
    assert (await any_store.get_position("AAPL")).quantity == 0  # fill rejected
    assert any(
        e.event_type == "fill_rejected_invalid" and e.order_id == order.id
        for e in await any_store.list_events()
    )


class _PollRaisesAdapter(MockBrokerAdapter):
    """Submits like the mock, but every status poll raises — to prove the loop
    logs-and-continues rather than crashing."""

    async def get_order_status(self, broker_order_id, *, recorded_quantity=0):  # type: ignore[override]
        raise BrokerError("poll endpoint down")


async def test_poll_error_does_not_crash_tick(any_store):
    order = await _created_order(any_store)
    adapter = _PollRaisesAdapter()
    await _submit_pending_orders(any_store, adapter)

    # A raising poll must be swallowed; the order is simply left as-is.
    await run_monitoring_tick(any_store, adapter, Settings())

    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED


# --------------------------------------------------------------------------- #
# Stale detection — once per order, persisted
# --------------------------------------------------------------------------- #
async def test_stale_event_written_once(any_store):
    order = await _created_order(any_store)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    # timeout 0 => any open order is immediately stale.
    settings = Settings(unfilled_timeout_minutes=0.0)
    await _reconcile_open_orders(any_store, adapter, settings)
    await _reconcile_open_orders(any_store, adapter, settings)
    await _reconcile_open_orders(any_store, adapter, settings)

    stale = [
        e
        for e in await any_store.list_events()
        if e.event_type == "order_stale" and e.order_id == order.id
    ]
    assert len(stale) == 1
    assert stale[0].payload.get("status") == "submitted"


async def test_filled_order_is_not_flagged_stale(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    # Even with timeout 0, an order that fills in this tick is terminal and must
    # not be flagged stale (the stale check runs on the refreshed order).
    await _reconcile_open_orders(any_store, adapter, Settings(unfilled_timeout_minutes=0.0))

    assert not any(
        e.event_type == "order_stale" and e.order_id == order.id
        for e in await any_store.list_events()
    )


# --------------------------------------------------------------------------- #
# D-011 — polling continues across session close
# --------------------------------------------------------------------------- #
async def test_open_order_is_polled_after_session_close(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    session = await any_store.get_current_session()
    await any_store.close_session(session.id)

    # The order's session is now closed, but the loop must still poll it to a
    # terminal state and record the fill (position carries forward — D-011).
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 100


# --------------------------------------------------------------------------- #
# End-to-end single tick: submit then reconcile in one call
# --------------------------------------------------------------------------- #
async def test_tick_submits_then_reconciles(any_store):
    order = await _created_order(any_store, qty=10, limit=3.0)
    adapter = MockBrokerAdapter()

    # Tick 1 submits the CREATED order; the default poll shows nothing filled.
    await run_monitoring_tick(any_store, adapter, Settings())
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED

    # Queue a fill, then tick 2 reconciles it.
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=10,
        fills=[BrokerFill("exec-1", 10, 3.0, utcnow())],
    )
    await run_monitoring_tick(any_store, adapter, Settings())
    assert (await any_store.get_order(order.id)).status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 10


# --------------------------------------------------------------------------- #
# Cancel-pending lifecycle (CHAOS-1): keep polling until the broker confirms
# --------------------------------------------------------------------------- #
async def test_cancel_pending_keeps_polling_and_records_late_fill(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)
    # The cancel route requested a broker cancel -> cancel_pending (non-terminal).
    await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)

    # A late partial fill arrives while the broker still reports pending_cancel.
    adapter.make_fill(
        order.id,
        status=OrderStatus.CANCEL_PENDING,
        filled_quantity=40,
        fills=[BrokerFill("late-1", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.CANCEL_PENDING  # not reverted to open
    assert fresh.filled_quantity == 40
    assert (await any_store.get_position("AAPL")).quantity == 40

    # The broker confirms the cancel (replaying the same fill, which dedups).
    adapter.make_fill(
        order.id,
        status=OrderStatus.CANCELED,
        filled_quantity=40,
        fills=[BrokerFill("late-1", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.CANCELED  # now terminal
    assert fresh.filled_quantity == 40
    # The late fill was recorded exactly once.
    assert len(await any_store.list_fills(order_id=order.id)) == 1
    assert (await any_store.get_position("AAPL")).quantity == 40


async def test_cancel_pending_late_fill_can_complete_the_order(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)
    await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)

    # A late fill completes the order before the cancel landed -> FILLED wins.
    adapter.make_fill(
        order.id,
        status=OrderStatus.CANCEL_PENDING,
        filled_quantity=100,
        fills=[BrokerFill("late-full", 100, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 100


async def test_cancel_pending_order_is_not_flagged_stale(any_store):
    order = await _created_order(any_store)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)
    await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)

    # Even with timeout 0, a cancel_pending order is not "stuck unfilled" — it's
    # being wound down, so it is excluded from the stale flag.
    await _reconcile_open_orders(any_store, adapter, Settings(unfilled_timeout_minutes=0.0))
    assert not any(
        e.event_type == "order_stale" and e.order_id == order.id
        for e in await any_store.list_events()
    )
    # But it is still being polled (status unchanged, no error).
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCEL_PENDING


# --------------------------------------------------------------------------- #
# The order tracks RECORDED fills, never the broker's scalar (review M1/M2)
# --------------------------------------------------------------------------- #
async def test_order_follows_recorded_fills_not_broker_scalar(any_store):
    """If the broker over-claims (FILLED / a higher cumulative) but provides
    fewer fills, the order tracks the fills we actually recorded — never the raw
    scalar. order.filled_quantity == Σfills == position, and it is not marked
    FILLED without the fills to back it. The order completes only once the
    remaining execution actually arrives."""

    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    # Broker claims fully filled but supplies a single 40-share execution.
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("exec-1", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.PARTIALLY_FILLED  # NOT filled
    assert fresh.filled_quantity == 40  # follows recorded fills, not the scalar
    assert (await any_store.get_position("AAPL")).quantity == 40

    # The remaining execution arrives; now the order legitimately completes.
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[
            BrokerFill("exec-1", 40, 2.0, utcnow()),  # dup
            BrokerFill("exec-2", 60, 2.0, utcnow()),
        ],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.FILLED
    assert fresh.filled_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 100


async def test_broker_cancel_with_partial_fill_keeps_recorded_position(any_store):
    """A broker cancel after a partial fill cancels the order but preserves the
    recorded fill/position (the recorded fills are the truth)."""

    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)
    adapter.make_fill(
        order.id,
        status=OrderStatus.CANCELED,
        filled_quantity=40,
        fills=[BrokerFill("exec-1", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.CANCELED
    assert fresh.filled_quantity == 40
    assert (await any_store.get_position("AAPL")).quantity == 40


# --------------------------------------------------------------------------- #
# Broker accepted but the SUBMITTED transition failed (review 3.1 / m3)
# --------------------------------------------------------------------------- #
class _SubmitTransitionFails(InMemoryStateStore):
    """Fails the first CREATED->SUBMITTED transition, to simulate a store error
    after the broker has already accepted the order."""

    def __init__(self) -> None:
        super().__init__()
        self._fail_once = True

    async def transition_order(
        self, order_id, new_status, *, filled_quantity=None, broker_order_id=None
    ):
        if new_status is OrderStatus.SUBMITTED and self._fail_once:
            self._fail_once = False
            raise OrderTransitionError("simulated persist failure")
        return await super().transition_order(
            order_id,
            new_status,
            filled_quantity=filled_quantity,
            broker_order_id=broker_order_id,
        )


async def test_submit_accepted_but_unpersisted_is_audited():
    store = _SubmitTransitionFails()
    order = await _created_order(store, qty=10, limit=1.0)
    adapter = MockBrokerAdapter()

    await _submit_pending_orders(store, adapter)

    # The order was claimed (CREATED -> SUBMITTING), the broker accepted it, and
    # the first SUBMITTING -> SUBMITTED transition failed — but the order is not
    # cancelled, so it is genuinely open at the broker. The handler retries the
    # transition (the store fails only once), so the order ends up SUBMITTED and
    # tracked. The hiccup is audited; no cancel, no recovery record (the order
    # is legitimately live, not orphaned).
    assert [o.id for o in adapter.submitted] == [order.id]
    assert (await store.get_order(order.id)).status is OrderStatus.SUBMITTED
    unpersisted = [
        e
        for e in await store.list_events()
        if e.event_type == "order_submit_unpersisted" and e.order_id == order.id
    ]
    assert len(unpersisted) == 1
    assert unpersisted[0].payload.get("broker_order_id") == adapter.broker_id_for(
        order.id
    )
    assert adapter.canceled == []  # not cancelled — it is a valid open order
    assert await store.list_submit_recoveries() == []  # recovered on retry


class _CancelDuringSubmit(InMemoryStateStore):
    """Simulates a manual cancel landing during the submit network call: the
    CREATED->SUBMITTED transition instead finds the order already CANCELED."""

    async def transition_order(
        self, order_id, new_status, *, filled_quantity=None, broker_order_id=None
    ):
        if new_status is OrderStatus.SUBMITTED:
            await super().transition_order(order_id, OrderStatus.CANCELED)
            raise OrderTransitionError("order was cancelled during submit")
        return await super().transition_order(
            order_id,
            new_status,
            filled_quantity=filled_quantity,
            broker_order_id=broker_order_id,
        )


async def test_cancel_during_submit_records_durable_recovery():
    store = _CancelDuringSubmit()
    order = await _created_order(store, qty=10, limit=1.0)
    adapter = MockBrokerAdapter()

    await _submit_pending_orders(store, adapter)

    # The order was cancelled mid-submit: it is live at the broker but CANCELED
    # locally (the F-002 orphan). Instead of a lone best-effort cancel, a durable
    # recovery record is written; the submission is audited. The cancel now
    # happens in the recovery loop, not here.
    assert (await store.get_order(order.id)).status is OrderStatus.CANCELED
    assert adapter.canceled == []  # no immediate cancel — deferred to recovery
    assert any(
        e.event_type == "order_submit_unpersisted" and e.order_id == order.id
        for e in await store.list_events()
    )
    unresolved = await store.list_submit_recoveries(unresolved_only=True)
    assert len(unresolved) == 1
    assert unresolved[0].broker_order_id == adapter.broker_id_for(order.id)
    assert unresolved[0].local_order_id == order.id


async def test_recovery_loop_cancels_stranded_broker_order_and_resolves():
    """The recovery loop drives an unresolved record to resolution: it cancels
    the still-live broker order and marks the record resolved. A single
    best-effort cancel is replaced by retry-until-resolved (F-002)."""

    store = _CancelDuringSubmit()
    order = await _created_order(store, qty=10, limit=1.0)
    adapter = MockBrokerAdapter()

    # First: strand the broker order (records the recovery, no cancel yet).
    await _submit_pending_orders(store, adapter)
    broker_id = adapter.broker_id_for(order.id)
    assert adapter.canceled == []

    # A transient cancel failure on the first recovery attempt must NOT resolve
    # it — it stays unresolved, retry_count bumped, retried next tick.
    adapter.fail_next_cancel(BrokerError("cancel temporarily unavailable"))
    await _recover_unpersisted_submits(store, adapter)
    still = await store.list_submit_recoveries(unresolved_only=True)
    assert len(still) == 1
    assert still[0].retry_count == 1

    # Next tick: cancel succeeds, broker confirms CANCELED, record resolves.
    await _recover_unpersisted_submits(store, adapter)
    assert broker_id in adapter.canceled
    assert await store.list_submit_recoveries(unresolved_only=True) == []
    resolved = await store.list_submit_recoveries()
    assert resolved[0].cleanup_status == "resolved_canceled"


# --------------------------------------------------------------------------- #
# Stale-age computation tolerates a tz-naive created_at (review 2.1)
# --------------------------------------------------------------------------- #
async def test_stale_check_tolerates_naive_created_at():
    store = InMemoryStateStore()
    order = await _created_order(store)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(store, adapter)

    # Force a tz-naive created_at (a legacy / hand-inserted row). Without the
    # guard, `now - created_at` would raise TypeError and abort the whole tick.
    store._orders[order.id].created_at = datetime(2020, 1, 1, 0, 0, 0)  # naive

    await _reconcile_open_orders(store, adapter, Settings(unfilled_timeout_minutes=0.0))

    assert any(
        e.event_type == "order_stale" and e.order_id == order.id
        for e in await store.list_events()
    )
