"""Monitoring-loop unit tests — submit, reconcile, dedup, stale, resilience.

IO-free (Rule 9): everything runs against a StateStore and the controllable
``MockBrokerAdapter``; no network, no real broker, no sleep. The loop's body is
exercised through ``run_monitoring_tick`` / the two step functions directly, not
the ``while True``/``sleep`` wrapper.

Run through ``any_store`` where it proves the loop behaves identically against
InMemoryStateStore and SqliteStateStore.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerError, BrokerFill, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import CandidateStatus, OrderStatus, utcnow
from app.monitoring import (
    _reconcile_open_orders,
    _submit_pending_orders,
    run_monitoring_tick,
)

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

    async def get_order_status(self, broker_order_id):  # type: ignore[override]
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
