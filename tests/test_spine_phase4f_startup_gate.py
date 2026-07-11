"""Spine v2 Phase 4 wave 4f slice 2 — startup mass-reconcile + gate (§7 / R2 / R3).

Trading is NOT enabled until a reconcile pass confirms parity: startup enters
reduce-only (reconcile driver → Reducing), then lifts to Active on parity, stays
Reducing on divergence, and — R3 — stays Reducing (never Halted) on a reconcile
FAILURE, so a held position is always exitable at boot. Kill still dominates.

Only the loop/startup pass drive_reconcile_state; a direct ``run_monitoring_tick``
(the whole existing corpus) never flips ``trading_state``.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import CandidateStatus, TradingState
from app.monitoring import (
    _submit_pending_orders,
    run_monitoring_tick,
    run_startup_reconcile,
)

pytestmark = pytest.mark.anyio

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED
_NO_RECENT = Settings(reconcile_recent_threshold_ms=0)


async def _absent_open_order(store):
    """A locally-SUBMITTED order the reconcile adapter never minted (submitted via a
    throwaway) → absent from the mass report AND confirmed-absent by the query."""

    session = await store.get_current_session()
    cand = await store.create_candidate(
        "AAPL", suggested_quantity=100, suggested_limit_price=2.0, session_id=session.id
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    await store.create_order_for_candidate(cand.id)
    await _submit_pending_orders(store, MockBrokerAdapter())  # throwaway owns the id


# --------------------------------------------------------------------------- #
# Startup gate
# --------------------------------------------------------------------------- #
async def test_clean_startup_confirms_parity_and_enables_trading(any_store):
    await any_store.initialize()
    # No orders/positions → the first reconcile pass finds parity → Active.
    await run_startup_reconcile(any_store, MockBrokerAdapter(), Settings())
    assert await any_store.current_trading_state() is A


async def test_startup_with_divergence_stays_reduce_only(any_store):
    await any_store.initialize()
    await _absent_open_order(any_store)
    # A fresh adapter: the order is absent from the mass report → unresolved
    # divergence → trading stays Reducing (reduce-only) until reconciled.
    await run_startup_reconcile(any_store, MockBrokerAdapter(), _NO_RECENT)
    assert await any_store.current_trading_state() is R


async def test_startup_reconcile_failure_stays_reducing_never_halted(any_store):
    await any_store.initialize()
    adapter = MockBrokerAdapter()
    adapter.fail_next_open_orders(BrokerError("venue down at boot"))
    await run_startup_reconcile(any_store, adapter, Settings())
    # R3: a reconcile FAILURE is reduce-only, NEVER auto-Halted (a held position
    # stays exitable at boot).
    assert await any_store.current_trading_state() is R


async def test_kill_switch_dominates_startup_parity(any_store):
    await any_store.initialize()
    await any_store.set_kill_switch(True)
    # Even though the reconcile pass confirms parity (→ reconcile driver Active), the
    # effective state stays HALTED — kill dominates (§8).
    await run_startup_reconcile(any_store, MockBrokerAdapter(), Settings())
    assert await any_store.current_trading_state() is H


async def test_divergence_then_resolution_lifts_to_active(any_store):
    await any_store.initialize()
    await _absent_open_order(any_store)
    settings = Settings(
        reconcile_recent_threshold_ms=0, reconcile_open_check_missing_retries=1
    )
    await run_startup_reconcile(any_store, MockBrokerAdapter(), settings)
    assert await any_store.current_trading_state() is R  # absent order pending

    # The loop keeps re-checking each tick (drive_reconcile_state=True). One more
    # tick resolves the absent order (retries=1 → REJECTED) → next pass is clean →
    # parity → Active.
    await run_monitoring_tick(
        any_store, MockBrokerAdapter(), settings, drive_reconcile_state=True
    )
    await run_monitoring_tick(
        any_store, MockBrokerAdapter(), settings, drive_reconcile_state=True
    )
    assert await any_store.current_trading_state() is A


# --------------------------------------------------------------------------- #
# Direct tick callers stay ungated (corpus inertness).
# --------------------------------------------------------------------------- #
async def test_direct_tick_never_drives_trading_state(any_store):
    await any_store.initialize()
    # Default drive_reconcile_state=False → the reconcile never touches trading_state,
    # even with a divergent venue picture.
    await _absent_open_order(any_store)
    await run_monitoring_tick(any_store, MockBrokerAdapter(), _NO_RECENT)
    assert await any_store.current_trading_state() is A  # unchanged (Active)
