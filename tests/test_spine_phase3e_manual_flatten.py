"""Spine v2 Phase 3 wave 3e slices 3-4 — manual flatten + emergency reduce (ADR-003).

The behavior migration (E1 ruled Option B): an ordinary manual flatten is DENIED by
default while ``Halted`` (the kill switch is a true all-stop); the operator exits via
an explicit, audited emergency-reduce override that scopes a SINGLE reduce-only exit
while the global ``TradingState`` stays ``Halted``. Flatten stays allowed in
``Active``/``Reducing``. Gating is at *creation* (``plan_flatten_position``), since
``flatten_position`` is the sole producer of ``MANUAL_FLATTEN`` orders.

Maps ADR-003's required-tests checklist.
"""

from __future__ import annotations

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SellIntentStatus,
    SellReason,
    SessionType,
    TradingState,
)
from app.monitoring import run_monitoring_tick
import app.monitoring as monitoring
from app.store.base import EmergencyReduceBlockedError, FlattenBlockedError

pytestmark = pytest.mark.anyio


async def _hold(store, symbol: str, qty: int, *, avg: float = 10.0) -> None:
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id)
    await store.transition_order(buy.id, OrderStatus.CANCELED)


def _regular(monkeypatch):
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)


# --------------------------------------------------------------------------- #
# The graded matrix: Active / Reducing allow; Halted denies (no override)
# --------------------------------------------------------------------------- #
async def test_active_allows_manual_flatten(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    result = await any_store.flatten_position("AAPL")
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert result.intent.status is SellIntentStatus.ORDERED


async def test_reducing_allows_reduce_only_manual_flatten(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_buys_paused(True)  # -> REDUCING
    assert await any_store.current_trading_state() is TradingState.REDUCING
    result = await any_store.flatten_position("AAPL")
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert result.intent.status is SellIntentStatus.ORDERED


async def test_halted_denies_ordinary_manual_flatten_and_mints_nothing(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_kill_switch(True)  # -> HALTED
    with pytest.raises(FlattenBlockedError):
        await any_store.flatten_position("AAPL")
    # No intent/order minted, position untouched.
    assert await any_store.active_sell_intent_for("AAPL") is None
    assert (await any_store.get_position("AAPL")).quantity == 100


# --------------------------------------------------------------------------- #
# Halted still allows cancels + reconciliation (ADR-003)
# --------------------------------------------------------------------------- #
async def test_halted_still_allows_order_cancel(any_store):
    # A CREATED order can still be canceled while Halted — the kill switch stops
    # new intent, not winding down.
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    order = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 10, session_id=session.id
    )
    await any_store.set_kill_switch(True)
    canceled = await any_store.transition_order(order.id, OrderStatus.CANCELED)
    assert canceled.status is OrderStatus.CANCELED


# --------------------------------------------------------------------------- #
# Emergency reduce override: exits while Halted; global state stays Halted
# --------------------------------------------------------------------------- #
async def test_emergency_reduce_exits_while_halted_global_stays_halted(
    any_store, monkeypatch
):
    _regular(monkeypatch)
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_kill_switch(True)

    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    assert await any_store.list_emergency_reduce_overrides() == {"AAPL"}

    result = await any_store.flatten_position("AAPL")
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    # Global TradingState never left Halted (scoped grant, not a global flip).
    assert await any_store.current_trading_state() is TradingState.HALTED
    # The override was consumed on create (single-use).
    assert await any_store.list_emergency_reduce_overrides() == set()

    # The authorized exit submits.
    adapter = MockBrokerAdapter()
    await run_monitoring_tick(any_store, adapter, Settings())
    assert (await any_store.get_order(result.order.id)).status is OrderStatus.SUBMITTED


async def test_override_is_single_use(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 200)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    await any_store.flatten_position("AAPL")  # consumes the override
    # A second flatten under Halted is denied again — the grant did not persist.
    with pytest.raises(FlattenBlockedError):
        await any_store.flatten_position("AAPL")


async def test_override_consumed_on_existing_outcome_no_leak(any_store):
    # Review MEDIUM: the override must be spent even when the flatten dedup's to an
    # EXISTING exit — otherwise the grant leaks and later lets an ordinary flatten
    # slip past the Halted-deny.
    await any_store.initialize()
    await _hold(any_store, "AAPL", 200)
    await any_store.set_kill_switch(True)

    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    await any_store.flatten_position("AAPL")  # creates O1, consumes grant1
    assert await any_store.list_emergency_reduce_overrides() == set()

    # A fresh authorization whose flatten dedup's to the existing O1 must still be
    # consumed (FLATTEN_EXISTING), leaving NO active grant.
    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    result = await any_store.flatten_position("AAPL")
    assert result.outcome != "created"  # dedup'd to the existing exit
    assert await any_store.list_emergency_reduce_overrides() == set()  # no leak

    # And an ordinary flatten under Halted is still denied (the grant did not leak).
    with pytest.raises(FlattenBlockedError):
        await any_store.flatten_position("AAPL")


async def test_double_authorize_without_flatten_refused(any_store):
    # Never stack a second grant on an active one — one override authorizes one exit.
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    with pytest.raises(EmergencyReduceBlockedError):
        await any_store.authorize_emergency_reduce_override("AAPL", actor="op")


async def test_inv3_gate_is_symbol_specific(any_store):
    # A quarantined order for a DIFFERENT symbol must NOT block an emergency reduce
    # of this symbol (INV-3 is per-symbol).
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("MSFT", session_id=session.id)
    other = await any_store.create_order_for_test(
        cand.id, "MSFT", OrderSide.BUY, 10, session_id=session.id
    )
    claim = await any_store.claim_order_for_submission(other.id)
    await any_store.quarantine_timed_out_order(claim.order.id)  # MSFT quarantined

    await any_store.set_kill_switch(True)
    # AAPL is unaffected by the MSFT quarantine -> authorize succeeds + flatten runs.
    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    result = await any_store.flatten_position("AAPL")
    assert result.intent.reason is SellReason.MANUAL_FLATTEN


async def test_manual_flatten_created_in_active_submits_under_later_halt(
    any_store, monkeypatch
):
    # Deliberate, documented scoping (review LOW): the Halted-deny is at ISSUANCE
    # (creation). A flatten issued while Active — an exit the operator already
    # commanded — completes even if the kill switch engages before it is submitted;
    # a locally-CREATED order is not new intent. This is asymmetric with autonomous
    # PROTECTION_FLOOR (still held by the kill switch at claim) by design: a human
    # command outranks autonomous protection (D-P2). Pinned so the choice is explicit.
    _regular(monkeypatch)
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    created = await any_store.flatten_position("AAPL")  # Active -> allowed
    assert created.order.status is OrderStatus.CREATED

    await any_store.set_kill_switch(True)  # Halt AFTER the exit was issued
    assert await any_store.list_emergency_reduce_overrides() == set()  # no override
    adapter = MockBrokerAdapter()
    await run_monitoring_tick(any_store, adapter, Settings())
    assert (await any_store.get_order(created.order.id)).status is OrderStatus.SUBMITTED


# --------------------------------------------------------------------------- #
# authorize_emergency_reduce_override preconditions
# --------------------------------------------------------------------------- #
async def test_authorize_refused_when_not_halted(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    # Active — an ordinary flatten works, so the override is refused.
    with pytest.raises(EmergencyReduceBlockedError):
        await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    # Reducing likewise (buys-paused is not the all-stop).
    await any_store.set_buys_paused(True)
    with pytest.raises(EmergencyReduceBlockedError):
        await any_store.authorize_emergency_reduce_override("AAPL", actor="op")


async def test_authorize_refused_when_flat(any_store):
    await any_store.initialize()
    await any_store.set_kill_switch(True)
    with pytest.raises(EmergencyReduceBlockedError):
        await any_store.authorize_emergency_reduce_override("AAPL", actor="op")


async def test_ambiguous_timeout_quarantine_blocks_emergency_reduce(any_store):
    # INV-3 / E8: no exit while a possibly-live spawn is unresolved.
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    order = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 10, session_id=session.id
    )
    claim = await any_store.claim_order_for_submission(order.id)  # -> SUBMITTING
    await any_store.quarantine_timed_out_order(claim.order.id)   # -> TIMEOUT_QUARANTINE

    await any_store.set_kill_switch(True)
    with pytest.raises(EmergencyReduceBlockedError):
        await any_store.authorize_emergency_reduce_override("AAPL", actor="op")


# --------------------------------------------------------------------------- #
# Replay reproduces the override grant/consume lifecycle
# --------------------------------------------------------------------------- #
async def test_replay_reproduces_override_lifecycle(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    await any_store.flatten_position("AAPL")  # grant then consume

    types = [
        e.event_type
        for e in await any_store.get_execution_events()
        if e.event_type
        in (
            ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE,
            ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE_RESOLVED,
        )
    ]
    # A grant followed by its consume — the log alone reproduces "no longer active".
    assert types == [
        ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE,
        ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE_RESOLVED,
    ]
    assert await any_store.list_emergency_reduce_overrides() == set()
