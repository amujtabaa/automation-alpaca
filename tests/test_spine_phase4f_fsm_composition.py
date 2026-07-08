"""Spine v2 Phase 4 wave 4f slice 1 — the TradingState FSM gains a second,
independent RECONCILE driver, composed with the control (kill/pause) driver via
``Halted > Reducing > Active`` (R2). The reconcile driver never drives ``Halted``
(R3: a held position stays exitable) and never touches the kill/pause booleans.

Behavior preservation: with no reconcile events the composition reduces to the
control state exactly (the wave-3d world) — proven by the untouched wave-3d suite.
"""

from __future__ import annotations

import pytest

from app.events.projectors import (
    compose_trading_state,
    control_trading_state,
    reconcile_trading_state,
)
from app.models import ExecutionEventType, TradingState

pytestmark = pytest.mark.anyio

A, R, H = TradingState.ACTIVE, TradingState.REDUCING, TradingState.HALTED


# --------------------------------------------------------------------------- #
# Pure composition
# --------------------------------------------------------------------------- #
def test_compose_is_most_restrictive():
    assert compose_trading_state(A, A) is A
    assert compose_trading_state(A, R) is R
    assert compose_trading_state(R, A) is R
    assert compose_trading_state(H, R) is H
    assert compose_trading_state(R, H) is H
    assert compose_trading_state(A, H) is H
    assert compose_trading_state() is A          # no drivers → Active
    assert compose_trading_state(A) is A


# --------------------------------------------------------------------------- #
# Reconcile driver composes with control, independently.
# --------------------------------------------------------------------------- #
async def test_reconcile_reducing_composes_over_active_control(any_store):
    await any_store.initialize()
    s = await any_store.set_reconcile_trading_state(R, reason="startup_pending")
    assert s.trading_state is R
    assert await any_store.current_trading_state() is R
    # It did NOT touch the control booleans (R2).
    assert s.kill_switch is False and s.buys_paused is False


async def test_kill_dominates_a_reconcile_reducing(any_store):
    await any_store.initialize()
    await any_store.set_reconcile_trading_state(R, reason="pending")
    await any_store.set_kill_switch(True)                       # control → HALTED
    assert await any_store.current_trading_state() is H          # kill dominates
    # A kill RELEASE cannot lift the Reducing that reconciliation still requires.
    s = await any_store.set_kill_switch(False)
    assert s.trading_state is R
    assert await any_store.current_trading_state() is R


async def test_parity_restored_lifts_reconcile_to_active(any_store):
    await any_store.initialize()
    await any_store.set_reconcile_trading_state(R, reason="pending")
    assert await any_store.current_trading_state() is R
    s = await any_store.set_reconcile_trading_state(A, reason="parity_ok")
    assert s.trading_state is A
    assert await any_store.current_trading_state() is A


async def test_buys_paused_and_reconcile_both_reducing_stays_reducing(any_store):
    await any_store.initialize()
    await any_store.set_buys_paused(True)                        # control → REDUCING
    await any_store.set_reconcile_trading_state(R, reason="pending")
    assert await any_store.current_trading_state() is R
    # Resuming buys while reconciliation still pending stays Reducing (reconcile holds).
    await any_store.set_buys_paused(False)
    assert await any_store.current_trading_state() is R
    # Only when reconcile ALSO clears does it return to Active.
    await any_store.set_reconcile_trading_state(A, reason="parity_ok")
    assert await any_store.current_trading_state() is A


async def test_reconcile_driver_rejects_halted(any_store):
    await any_store.initialize()
    with pytest.raises(ValueError):
        await any_store.set_reconcile_trading_state(H, reason="nope")


# --------------------------------------------------------------------------- #
# Event-truth: the effective state replays from the log; drivers fold independently.
# --------------------------------------------------------------------------- #
async def test_drivers_fold_independently_from_the_log(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    await any_store.set_kill_switch(True)                        # control HALTED
    await any_store.set_reconcile_trading_state(R, reason="pending")
    await any_store.set_kill_switch(False)                       # control ACTIVE

    events = await any_store.get_execution_events()
    assert control_trading_state(events, session.id) is A        # control folded alone
    assert reconcile_trading_state(events, session.id) is R      # reconcile folded alone
    # The column read-model equals the composed effective state.
    fresh = await any_store.get_current_session()
    assert fresh.trading_state is R

    # Each reconcile change is a driver="reconcile" TRADING_STATE_CHANGED event.
    recon = [
        e for e in events
        if e.event_type is ExecutionEventType.TRADING_STATE_CHANGED
        and (e.payload or {}).get("driver") == "reconcile"
    ]
    assert len(recon) == 1 and recon[0].payload["to"] == "reducing"


async def test_redundant_reconcile_set_is_a_noop(any_store):
    await any_store.initialize()
    await any_store.set_reconcile_trading_state(R, reason="pending")
    before = len(await any_store.get_execution_events())
    await any_store.set_reconcile_trading_state(R, reason="pending-again")
    after = len(await any_store.get_execution_events())
    assert after == before          # no event when the reconcile state is unchanged
