"""Wave 1 (D-018) — deterministic chaos-matrix reproductions using the
controllable :class:`SimBrokerAdapter`.

These pin the specific temporal-sequence scenarios the random state machine
(``tests/test_lifecycle_state_machine.py``) explores but doesn't guarantee to
hit, plus the historical blocker bugs, so they can never silently regress:
duplicate fill, late-fill-after-cancel (CHAOS-1), disconnect-then-recover, the
F-001 mid-submit kill flip, and the F-002 accept -> local-cancel -> recovery
orphan — all driven through the real monitoring loop, IO-free (Rule 9).
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerFill, BrokerOrderUpdate
from app.broker.sim import SimBrokerAdapter
from app.config import Settings
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    CandidateStatus,
    OrderStatus,
    utcnow,
)
from app.monitoring import (
    _recover_unpersisted_submits,
    _submit_pending_orders,
    run_monitoring_tick,
)
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio

_S = Settings()


async def _submitted_order(store, sim, *, symbol="AAPL", qty=10, limit=2.0):
    """A candidate approved, dispatched, and driven to SUBMITTED (with a broker
    id) by one real monitoring tick — the claim + submit path."""

    cand = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)
    await run_monitoring_tick(store, sim, _S)
    fresh = await store.get_order(order.id)
    assert fresh.status is OrderStatus.SUBMITTED
    assert fresh.broker_order_id is not None
    return fresh


async def test_duplicate_fill_via_reconcile_is_not_double_counted():
    store = InMemoryStateStore()
    await store.initialize()
    sim = SimBrokerAdapter()
    order = await _submitted_order(store, sim, qty=10, limit=2.0)
    bid = order.broker_order_id

    # The broker reports the SAME execution twice across two polls.
    dup = BrokerFill("dup-sfid", 5, 2.0, utcnow())
    sim.script(
        bid,
        [
            BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 5, [dup]),
            BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 5, [dup]),
        ],
    )

    await run_monitoring_tick(store, sim, _S)  # first report -> 5 filled
    await run_monitoring_tick(store, sim, _S)  # duplicate -> ignored

    assert (await store.get_position("AAPL")).quantity == 5  # not 10
    assert (await store.get_order(order.id)).filled_quantity == 5
    assert any(
        e.event_type == "fill_duplicate_ignored" for e in await store.list_events()
    )


async def test_late_fill_after_cancel_pending_wins_chaos_1():
    """CHAOS-1: a cancel is requested (order cancel_pending) but a late fill
    completes at the broker before the venue confirms the cancel — the fill is
    still recorded and the order resolves FILLED, never lost."""

    store = InMemoryStateStore()
    await store.initialize()
    sim = SimBrokerAdapter()
    order = await _submitted_order(store, sim, qty=10, limit=2.0)
    bid = order.broker_order_id

    # Cancel requested (not yet broker-confirmed): order -> cancel_pending.
    await store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
    # The broker fills it fully before confirming the cancel.
    sim.script(bid, [BrokerOrderUpdate(OrderStatus.FILLED, 10, [BrokerFill("late", 10, 2.0, utcnow())])])

    await run_monitoring_tick(store, sim, _S)

    fresh = await store.get_order(order.id)
    assert fresh.status is OrderStatus.FILLED  # late fill wins over the pending cancel
    assert (await store.get_position("AAPL")).quantity == 10


async def test_status_disconnect_then_recover_never_crashes_and_applies_fill():
    store = InMemoryStateStore()
    await store.initialize()
    sim = SimBrokerAdapter()
    order = await _submitted_order(store, sim, qty=10, limit=2.0)
    bid = order.broker_order_id

    sim.script(bid, [BrokerOrderUpdate(OrderStatus.FILLED, 10, [BrokerFill("f1", 10, 2.0, utcnow())])])
    sim.disconnect_status_for(2)  # next two status polls raise

    # Two ticks during the disconnect: the loop logs-and-continues, the order is
    # untouched, nothing crashes.
    await run_monitoring_tick(store, sim, _S)
    await run_monitoring_tick(store, sim, _S)
    assert (await store.get_order(order.id)).status is OrderStatus.SUBMITTED

    # Feed recovers: the fill lands.
    await run_monitoring_tick(store, sim, _S)
    assert (await store.get_order(order.id)).status is OrderStatus.FILLED
    assert (await store.get_position("AAPL")).quantity == 10


async def test_f001_kill_flip_mid_submit_still_submits():
    """F-001, reproduced with the accept-then-signal hook: the kill switch flips
    *inside* submit_order — after the atomic claim (CREATED -> SUBMITTING) has
    already committed the order. Correct semantics is that it still submits."""

    store = InMemoryStateStore()
    await store.initialize()
    sim = SimBrokerAdapter()

    async def flip_kill(order, broker_id):
        assert sim.is_live(broker_id)  # already accepted at the broker
        await store.set_kill_switch(True)

    sim.set_on_submit(flip_kill)

    cand = await store.create_candidate("AAPL", suggested_quantity=10, suggested_limit_price=2.0)
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)

    await _submit_pending_orders(store, sim)

    fresh = await store.get_order(order.id)
    assert fresh.status is OrderStatus.SUBMITTED  # committed before the stop landed
    assert (await store.get_current_session()).kill_switch is True


async def test_f002_cancel_races_submit_records_and_recovers_orphan():
    """F-002, reproduced with the accept-then-signal hook: a manual cancel lands
    *inside* submit_order (after the claim), so the order is CANCELED locally
    while live at the broker. A durable recovery record is written and the
    recovery loop cancels the stranded broker order."""

    store = InMemoryStateStore()
    await store.initialize()
    sim = SimBrokerAdapter()
    captured = {}

    async def cancel_mid_submit(order, broker_id):
        captured["bid"] = broker_id
        # The SUBMITTING order is cancelled by a racing manual cancel.
        await store.transition_order(order.id, OrderStatus.CANCELED)

    sim.set_on_submit(cancel_mid_submit)

    cand = await store.create_candidate("AAPL", suggested_quantity=10, suggested_limit_price=2.0)
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)

    # Submit phase only: the order is live at the broker but CANCELED locally,
    # so a recovery record is written (the SUBMITTED persist was illegal).
    await _submit_pending_orders(store, sim)
    assert (await store.get_order(order.id)).status is OrderStatus.CANCELED
    open_recs = await store.list_submit_recoveries(statuses=RECOVERY_OPEN_STATUSES)
    assert len(open_recs) == 1
    assert open_recs[0].broker_order_id == captured["bid"]
    assert sim.is_live(captured["bid"])  # orphaned: live at broker, terminal locally

    # Recovery phase: cancels the stranded broker order and resolves the record.
    await _recover_unpersisted_submits(store, sim)
    assert not sim.is_live(captured["bid"])
    assert await store.list_submit_recoveries(statuses=RECOVERY_OPEN_STATUSES) == []


async def test_f002_orphan_with_partial_fill_flags_needs_review():
    """The nastier F-002 variant the pre-merge review caught: the stranded
    broker order partially fills before recovery can cancel it. Those executed
    shares are a real untracked position — flagged needs_review and kept
    visible, never cancelled-and-dropped."""

    store = InMemoryStateStore()
    await store.initialize()
    sim = SimBrokerAdapter()

    async def cancel_mid_submit(order, broker_id):
        await store.transition_order(order.id, OrderStatus.CANCELED)

    sim.set_on_submit(cancel_mid_submit)
    cand = await store.create_candidate("AAPL", suggested_quantity=10, suggested_limit_price=2.0)
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    await store.create_order_for_candidate(cand.id)

    await _submit_pending_orders(store, sim)
    bid = (await store.list_submit_recoveries())[0].broker_order_id
    # The stranded broker order partially fills.
    sim.script(bid, [BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 4, [BrokerFill("p", 4, 2.0, utcnow())])])

    await _recover_unpersisted_submits(store, sim)

    recs = await store.list_submit_recoveries()
    assert recs[0].cleanup_status == RECOVERY_NEEDS_REVIEW
    assert len(await store.list_submit_recoveries(statuses=RECOVERY_OPEN_STATUSES)) == 1  # still visible
    assert bid not in sim.canceled  # not cancelled-and-dropped
