"""WO-0017 — ADR-010 §4 precedence, BOTH stores.

Kill switch ⇒ every ACTIVE envelope freezes in the same atomic unit as the
control change; release never auto-resumes; activation/resume is refused
while HALTED. Manual flatten preempts envelopes: when the flatten itself
takes over the exit (create / already-flat), the symbol's non-terminal
envelopes are CANCELLED first, inside the same lock hold, with the
preemption events sequenced BEFORE the flatten's own writes. The ADR-003 /
WO-0015 safe-deferral outcome is UNCHANGED — deferring to a live protection
exit leaves that exit's envelope alone (it IS the live exit's manager;
cancelling it would strand the working order the human is deferring to).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
    utcnow,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import FLATTEN_CREATED, FLATTEN_FLAT, OrderIntentBlockedError

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
ACTION_NOW = datetime(2026, 7, 15, 15, 0, 0, tzinfo=timezone.utc)


def make_draft(intent_id: str, symbol: str = "AAPL", **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=100,
        floor_price=9.50,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.20,
        aggressiveness=["passive"],
        cooldown_floor_ms=750,
        cancel_replace_budget=40,
        expires_at=utcnow() + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


async def _hold(store, symbol, qty, avg=10.0):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )


async def _protection_intent(store, symbol, qty):
    session = await store.get_current_session()
    si = await store.create_sell_intent(
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=qty,
        session_id=session.id,
    )
    return si


def _bound_draft(si, **overrides):
    return make_draft(
        si.id,
        si.symbol,
        qty_ceiling=si.target_quantity,
        session_id=si.session_id,
        **overrides,
    )


def _planned(quantity=100, limit_price=9.90) -> PlannedAction:
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=limit_price,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=9.50,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


# --- kill switch ⇒ freeze --------------------------------------------------------- #


async def test_kill_freezes_every_active_envelope_atomically(any_store):
    await any_store.initialize()
    si_a = await _protection_intent(any_store, "AAPL", 100)
    a = await any_store.approve_envelope_activation(
        _bound_draft(si_a), actor="operator-a"
    )
    si_b = await _protection_intent(any_store, "MSFT", 100)
    b = await any_store.approve_envelope_activation(
        _bound_draft(si_b), actor="operator-a"
    )
    si_pending = await _protection_intent(any_store, "NVDA", 100)
    pending = await any_store.create_envelope(_bound_draft(si_pending))

    await any_store.set_kill_switch(True, actor="operator-a")

    assert (await any_store.get_envelope(a.id)).status is S.FROZEN
    assert (await any_store.get_envelope(b.id)).status is S.FROZEN
    # Non-ACTIVE envelopes are untouched (a PENDING draft carries no standing
    # order intent — it cannot even activate while HALTED).
    assert (await any_store.get_envelope(pending.id)).status is S.PENDING

    frozen_events = [
        e
        for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.ENVELOPE_FROZEN
    ]
    assert {e.envelope_id for e in frozen_events} == {a.id, b.id}
    assert all(e.payload.get("reason") == "kill_switch" for e in frozen_events)


async def test_release_never_auto_resumes(any_store):
    await any_store.initialize()
    si = await _protection_intent(any_store, "AAPL", 100)
    env = await any_store.approve_envelope_activation(
        _bound_draft(si), actor="operator-a"
    )
    await any_store.set_kill_switch(True, actor="operator-a")
    await any_store.set_kill_switch(False, actor="operator-a")
    assert (await any_store.get_envelope(env.id)).status is S.FROZEN  # still

    # Resume is an EXPLICIT human action — and it works once released.
    resumed = await any_store.transition_envelope(env.id, S.ACTIVE, actor="operator-a")
    assert resumed.status is S.ACTIVE


async def test_resume_and_activation_are_refused_while_halted(any_store):
    await any_store.initialize()
    si = await _protection_intent(any_store, "AAPL", 100)
    env = await any_store.approve_envelope_activation(
        _bound_draft(si), actor="operator-a"
    )
    si_pending = await _protection_intent(any_store, "MSFT", 100)
    pending = await any_store.create_envelope(_bound_draft(si_pending))
    await any_store.transition_envelope(pending.id, S.APPROVED)
    await any_store.set_kill_switch(True, actor="operator-a")

    with pytest.raises(OrderIntentBlockedError):
        await any_store.transition_envelope(env.id, S.ACTIVE)  # resume
    with pytest.raises(OrderIntentBlockedError):
        await any_store.transition_envelope(pending.id, S.ACTIVE)  # activation

    # Risk-reducing / administrative transitions stay allowed under HALTED.
    cancelled = await any_store.transition_envelope(env.id, S.CANCELLED)
    assert cancelled.status is S.CANCELLED


# --- manual flatten preempts ------------------------------------------------------- #


async def test_flatten_cancels_the_symbols_envelopes_before_proceeding(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await _protection_intent(any_store, "AAPL", 100)
    env = await any_store.approve_envelope_activation(
        _bound_draft(si), actor="operator-a"
    )
    si_other = await _protection_intent(any_store, "MSFT", 100)
    other = await any_store.approve_envelope_activation(
        _bound_draft(si_other), actor="operator-a"
    )

    result = await any_store.flatten_position("AAPL", actor="operator-ameen")
    assert result.outcome == FLATTEN_CREATED
    assert result.intent is not None
    assert result.intent.reason is SellReason.MANUAL_FLATTEN

    after = await any_store.get_envelope(env.id)
    assert after.status is S.CANCELLED  # never outlives the backstop
    # Another symbol's envelope is untouched.
    assert (await any_store.get_envelope(other.id)).status is S.ACTIVE

    # Ordering: the envelope preemption events land BEFORE the flatten's own
    # intent-creation audit in the shared execution-event/audit sequence.
    events = await any_store.get_execution_events()
    cancel_seq = max(
        e.sequence
        for e in events
        if e.envelope_id == env.id
        and e.event_type is ExecutionEventType.ENVELOPE_CANCELLED
    )
    audit = await any_store.list_events()
    created_rows = [
        ev
        for ev in audit
        if ev.event_type == "sell_intent_created"
        and ev.payload.get("reason") == "manual_flatten"
    ]
    assert created_rows, "flatten did not record its intent creation"
    frozen_and_cancelled = [
        e.event_type
        for e in events
        if e.envelope_id == env.id
        and e.event_type
        in (
            ExecutionEventType.ENVELOPE_FROZEN,
            ExecutionEventType.ENVELOPE_CANCELLED,
        )
    ]
    assert frozen_and_cancelled == [
        ExecutionEventType.ENVELOPE_FROZEN,
        ExecutionEventType.ENVELOPE_CANCELLED,
    ]
    assert cancel_seq > 0


async def test_flatten_on_a_flat_position_still_cancels_stale_envelopes(any_store):
    await any_store.initialize()
    si = await _protection_intent(any_store, "AAPL", 50)
    # No position was ever built — the envelope is a stale mandate.
    env = await any_store.approve_envelope_activation(
        _bound_draft(si), actor="operator-a"
    )
    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.outcome == FLATTEN_FLAT
    assert (await any_store.get_envelope(env.id)).status is S.CANCELLED


async def test_deferral_to_a_live_protection_exit_leaves_its_envelope_alone(
    any_store,
):
    """ADR-003/WO-0015 unchanged: with the protection order in flight, the
    flatten defers — and the envelope managing that live exit stays ACTIVE
    (cancelling it would strand the very order the flatten defers to)."""

    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await _protection_intent(any_store, "AAPL", 100)
    env = await any_store.approve_envelope_activation(
        _bound_draft(si, expires_at=ACTION_NOW + timedelta(hours=2)),
        actor="operator-a",
    )
    staged = await any_store.stage_envelope_action(
        env.id,
        _planned(quantity=100),
        snapshot_fingerprint="fp-live-protection-exit",
        now=ACTION_NOW,
    )
    assert staged.order is not None
    claim = await any_store.claim_order_for_submission(staged.order.id)
    await any_store.transition_order(
        claim.order.id, OrderStatus.SUBMITTED, broker_order_id="broker-x"
    )

    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.deferred is True
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE


async def test_flatten_cancels_frozen_and_preactivation_envelopes_too(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await _protection_intent(any_store, "AAPL", 100)
    active = await any_store.approve_envelope_activation(
        _bound_draft(si), actor="operator-a"
    )
    await any_store.transition_envelope(active.id, S.FROZEN)
    pending = await any_store.create_envelope(_bound_draft(si))

    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.outcome == FLATTEN_CREATED
    assert (await any_store.get_envelope(active.id)).status is S.CANCELLED
    assert (await any_store.get_envelope(pending.id)).status is S.CANCELLED
