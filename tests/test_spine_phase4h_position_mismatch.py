"""Spine v2 Phase 4 wave 4h — broker-vs-local position parity surfacing (§7).

The reconcile compares the locally fill-derived position against the broker's
position report: quantity must match exactly, average price within tolerance. A
drift is surfaced as a durable, deduped ``reconcile_position_mismatch`` needs-review
record — and, crucially, **position truth is NEVER overwritten** (Rule 7: only fill
events change position). The drift also holds trading reduce-only
(``_has_unresolved_divergence`` → the reconcile driver goes Reducing).

Gating (corpus inertness): surfacing + the FSM drive happen only when the caller
passes ``drive_reconcile_state=True`` (the loop / startup / reconnect pass). A
direct ``run_monitoring_tick`` (the whole existing corpus) never surfaces a
mismatch and never flips ``trading_state`` — otherwise every held local position
would false-positive against a mock adapter that reports no positions.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerFill, BrokerPositionReport
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    CandidateStatus,
    EventType,
    OrderStatus,
    TradingState,
    utcnow,
)
from app.monitoring import _submit_pending_orders, run_monitoring_tick

pytestmark = pytest.mark.anyio

MISMATCH = EventType.RECONCILE_POSITION_MISMATCH.value
A, R = TradingState.ACTIVE, TradingState.REDUCING


async def _held(store, adapter, *, symbol="AAPL", qty=100, price=2.0):
    """Create + fill a BUY so local state holds a real fill-derived position."""

    await store.initialize()
    cand = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=price
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)
    await _submit_pending_orders(store, adapter)
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=qty,
        fills=[BrokerFill("exec-hold", qty, price, utcnow())],
    )
    await run_monitoring_tick(store, adapter, Settings())  # legacy poll lands the fill
    return order


async def _mismatch_events(store):
    return [e for e in await store.list_events() if e.event_type == MISMATCH]


# --------------------------------------------------------------------------- #
# Surfacing (drive_state on) — durable, deduped, position never overwritten.
# --------------------------------------------------------------------------- #
async def test_quantity_drift_surfaced_and_position_not_overwritten(any_store):
    adapter = MockBrokerAdapter()
    await _held(any_store, adapter, symbol="AAPL", qty=100, price=2.0)
    # Broker says 150 — a quantity drift the local fill-derived 100 can't explain.
    adapter.seed_positions([BrokerPositionReport("AAPL", 150, 2.0)])

    await run_monitoring_tick(
        any_store, adapter, Settings(), drive_reconcile_state=True
    )

    events = await _mismatch_events(any_store)
    assert len(events) == 1
    p = events[0].payload
    assert p["symbol"] == "AAPL"
    assert p["kind"] == "quantity"
    assert p["local_quantity"] == 100
    assert p["broker_quantity"] == 150
    # Rule 7: position truth is NEVER overwritten by a reconcile record.
    assert (await any_store.get_position("AAPL")).quantity == 100
    # Unresolved divergence → reduce-only.
    assert await any_store.current_trading_state() is R


async def test_avg_price_drift_surfaced_as_avg_price_kind(any_store):
    adapter = MockBrokerAdapter()
    await _held(any_store, adapter, symbol="AAPL", qty=100, price=2.0)
    # Same qty, but avg price far outside the 0.01% tolerance → avg_price kind.
    adapter.seed_positions([BrokerPositionReport("AAPL", 100, 2.50)])

    await run_monitoring_tick(
        any_store, adapter, Settings(), drive_reconcile_state=True
    )

    events = await _mismatch_events(any_store)
    assert len(events) == 1
    assert events[0].payload["kind"] == "avg_price"
    assert (await any_store.get_position("AAPL")).quantity == 100  # untouched


async def test_mismatch_deduped_by_symbol_and_kind_across_ticks(any_store):
    adapter = MockBrokerAdapter()
    await _held(any_store, adapter, symbol="AAPL", qty=100, price=2.0)
    adapter.seed_positions([BrokerPositionReport("AAPL", 150, 2.0)])
    for _ in range(3):
        await run_monitoring_tick(
            any_store, adapter, Settings(), drive_reconcile_state=True
        )
    # One record per (symbol, kind), ever — not re-logged every tick.
    assert len(await _mismatch_events(any_store)) == 1


# --------------------------------------------------------------------------- #
# Inertness — parity surfaces nothing; a direct tick never surfaces/flips.
# --------------------------------------------------------------------------- #
async def test_matching_positions_surface_nothing(any_store):
    adapter = MockBrokerAdapter()
    await _held(any_store, adapter, symbol="AAPL", qty=100, price=2.0)
    adapter.seed_positions([BrokerPositionReport("AAPL", 100, 2.0)])  # agrees
    await run_monitoring_tick(
        any_store, adapter, Settings(), drive_reconcile_state=True
    )
    assert await _mismatch_events(any_store) == []
    assert await any_store.current_trading_state() is A  # parity → Active


async def test_direct_tick_never_surfaces_mismatch(any_store):
    adapter = MockBrokerAdapter()
    await _held(any_store, adapter, symbol="AAPL", qty=100, price=2.0)
    adapter.seed_positions([BrokerPositionReport("AAPL", 150, 2.0)])  # divergent
    # Default drive_reconcile_state=False (the whole existing corpus): no surfacing,
    # no trading_state flip — a mock that doesn't mirror positions must not false-fire.
    await run_monitoring_tick(any_store, adapter, Settings())
    assert await _mismatch_events(any_store) == []
    assert await any_store.current_trading_state() is A
