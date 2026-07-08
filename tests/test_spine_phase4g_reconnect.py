"""Spine v2 Phase 4 wave 4g — stream reconnect → Reducing + reconcile (§7 / R1).

A trade-update stream reconnect has no replay, so cached order/position state may have
drifted: `on_stream_reconnect` enters reduce-only (reconcile driver → Reducing) and
triggers a mass reconcile that lifts to Active on parity (or holds Reducing on
divergence / failure — R3). R1 sim seam: no real trade-update stream exists yet, so
this is invoked deterministically from the sim/tests; real wiring is deferred.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import CandidateStatus, TradingState
from app.monitoring import _submit_pending_orders, on_stream_reconnect

pytestmark = pytest.mark.anyio

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED
_NO_RECENT = Settings(reconcile_recent_threshold_ms=0)


async def _absent_open_order(store):
    session = await store.get_current_session()
    cand = await store.create_candidate(
        "AAPL", suggested_quantity=100, suggested_limit_price=2.0, session_id=session.id
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    await store.create_order_for_candidate(cand.id)
    await _submit_pending_orders(store, MockBrokerAdapter())   # throwaway owns the id


async def test_reconnect_on_clean_state_reconciles_to_active(any_store):
    await any_store.initialize()
    await on_stream_reconnect(any_store, MockBrokerAdapter(), Settings())
    # Reduced-only during reconnect, then parity confirmed → Active.
    assert await any_store.current_trading_state() is A


async def test_reconnect_with_divergence_stays_reducing(any_store):
    await any_store.initialize()
    await _absent_open_order(any_store)
    await on_stream_reconnect(any_store, MockBrokerAdapter(), _NO_RECENT)
    assert await any_store.current_trading_state() is R


async def test_reconnect_failure_stays_reducing_never_halted(any_store):
    await any_store.initialize()
    adapter = MockBrokerAdapter()
    adapter.fail_next_positions(BrokerError("stream flap + REST down"))
    await on_stream_reconnect(any_store, adapter, Settings())
    assert await any_store.current_trading_state() is R       # R3: never auto-Halt


async def test_reconnect_under_kill_switch_stays_halted(any_store):
    await any_store.initialize()
    await any_store.set_kill_switch(True)
    await on_stream_reconnect(any_store, MockBrokerAdapter(), Settings())
    assert await any_store.current_trading_state() is H       # kill dominates


async def test_reconnect_is_noop_when_reconciliation_disabled(any_store):
    await any_store.initialize()
    await on_stream_reconnect(
        any_store, MockBrokerAdapter(), Settings(reconciliation_enabled=False)
    )
    assert await any_store.current_trading_state() is A       # untouched
