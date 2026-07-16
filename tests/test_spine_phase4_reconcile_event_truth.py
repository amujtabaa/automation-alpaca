"""Spine v2 Phase 4 wave 4e slice 5 — the reconcile facts are `event_truth`.

Substantiates the migration-rule conditions for the runtime-reconcile facts:
1. the first durable write is an `ExecutionEvent` (the not-found resolution's
   REJECTED/CANCELED event is BROKER_AUTHORITATIVE; a synthetic fill is a FILL event);
2. replay reproduces the projection (position replays from the event log alone);
3. in-memory and SQLite agree (every test runs on `any_store`).

The order-status column stays a co-written read-model of the lifecycle ExecutionEvent
(the honest `event_truth` scope for an order-lifecycle fact — a full order-status
projector is deferred, mirror of wave 3c C5).
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerFill, BrokerOrderReport
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.events.replay import project_store_event_log
from app.models import (
    CandidateStatus,
    EventAuthority,
    EventSource,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    utcnow,
)
from app.monitoring import _run_reconciliation, _submit_pending_orders

pytestmark = pytest.mark.anyio

_NO_RECENT = Settings(reconcile_recent_threshold_ms=0)


async def _submitted_buy(store, *, symbol="AAPL", qty=100):
    await store.initialize()
    cand = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=2.0
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(store, adapter)
    return order, adapter


async def test_synthetic_fill_position_replays_from_the_event_log(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                adapter.broker_id_for(order.id),
                order.id,
                "AAPL",
                OrderSide.BUY,
                OrderStatus.PARTIALLY_FILLED,
                40,
                fills=[BrokerFill("ex-1", 40, 2.0, utcnow())],
            )
        ]
    )
    await _run_reconciliation(any_store, adapter, _NO_RECENT)

    live = await any_store.get_position("AAPL")
    replay = await project_store_event_log(any_store)
    # Position replays from the execution-event log ALONE (event_truth) — the
    # reconciliation-inferred FILL event is the durable fact.
    assert live.quantity == 40
    assert replay.positions["AAPL"].quantity == 40
    assert live.quantity == replay.positions["AAPL"].quantity


async def test_not_found_reject_first_durable_write_is_a_broker_authoritative_event(
    any_store,
):
    # A locally-SUBMITTED order the reconcile adapter never minted (submitted via a
    # throwaway) is confirmed-absent → REJECTED, whose durable truth is a
    # BROKER_AUTHORITATIVE REJECTED ExecutionEvent (the order row is a co-written
    # read-model). Runs on any_store → dual-store parity.
    await any_store.initialize()
    cand = await any_store.create_candidate(
        "AAPL", suggested_quantity=100, suggested_limit_price=2.0
    )
    await any_store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await any_store.create_order_for_candidate(cand.id)
    await _submit_pending_orders(
        any_store, MockBrokerAdapter()
    )  # throwaway owns the id

    adapter = MockBrokerAdapter()  # fresh: doesn't know the order → confirmed absent
    await _run_reconciliation(
        any_store,
        adapter,
        Settings(
            reconcile_recent_threshold_ms=0, reconcile_open_check_missing_retries=1
        ),
    )

    assert (await any_store.get_order(order.id)).status is OrderStatus.REJECTED
    rejects = [
        e
        for e in await any_store.get_execution_events()
        if e.order_id == order.id and e.event_type is ExecutionEventType.REJECTED
    ]
    assert len(rejects) == 1
    assert rejects[0].authority is EventAuthority.BROKER_AUTHORITATIVE
    assert rejects[0].source is EventSource.BROKER_REST
