"""WO-0112 — the three round-3 findings from the PR #9 Codex review.

All pre-existing R2 safety-surface gaps the WO-0109/0111 diffs did not touch,
exercised through ``any_store`` so memory and SQLite carry identical behavior.
Each pin is red on the pre-fix tree and mutation-verified in the commit.

F3 (P1, §5.3 self-cross) — the exit-preempt stand-down only expired PENDING/
APPROVED BUY candidates. A same-symbol BUY already dispatched to a CREATED order
under an ORDERED candidate was neither stood down nor blocking (CREATED is not in
MAY_EXECUTE), so after the exit SELL filled it could claim and re-grow the exited
position. Flatten already cancels CREATED buys (FLATTEN_BLOCKING includes CREATED);
the envelope-stage / protection paths did not.

F1 (P1) — open_protection_exit minted the PROTECTION_FLOOR SELL even when a
same-symbol BUY may execute (venue-uncertain), unlike flatten which fails closed.
The claim rail then wedged that SELL, or it was mis-sized if the BUY later filled.

F2 (P2 parity) — a late fill on an already-terminal envelope left a live CREATED
staged child uncancelled in memory (cleanup nested under the transition-only
branch) while SQLite cancels it (unconditionally when the stored envelope is
terminal) — an any_store divergence for a legacy/crash-recovery terminal envelope.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    CandidateStatus,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)


def _draft(intent_id, session_id, *, symbol="AAPL"):
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=100,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=_NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _submit_action(qty=100):
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=qty,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _held_with_dispatched_buy(store, *, buy_qty=40):
    """A held 100-share AAPL position plus a same-symbol BUY dispatched to a
    CREATED order under an ORDERED candidate (one sized candidate serves both,
    since single-flight forbids a second active same-symbol candidate)."""
    await store.initialize()
    session = await store.get_current_session()
    cand = await store.create_candidate(
        "AAPL",
        suggested_quantity=buy_qty,
        suggested_limit_price=9.9,
        session_id=session.id,
    )
    establishing = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        establishing.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )
    await store.transition_order(establishing.id, OrderStatus.CANCELED)
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    buy_order = await store.create_order_for_candidate(cand.id)
    return session, cand, buy_order


async def _activate_envelope(store, session):
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    return await store.approve_envelope_activation(
        _draft(intent.id, session.id), actor="op"
    )


# --------------------------------------------------------------------------- #
# F3 — staging an exit stands down a same-symbol CREATED buy order
# --------------------------------------------------------------------------- #
async def test_f3_envelope_stage_stands_down_same_symbol_created_buy(any_store):
    session, _cand, buy_order = await _held_with_dispatched_buy(any_store)
    assert buy_order.status is OrderStatus.CREATED

    envelope = await _activate_envelope(any_store, session)
    await any_store.stage_envelope_action(
        envelope.id, _submit_action(), snapshot_fingerprint="wo0112-f3", now=_NOW
    )

    after = await any_store.get_order(buy_order.id)
    assert after.status is OrderStatus.CANCELED, (
        "exit-preempt left a same-symbol CREATED buy live "
        f"(status {after.status!r}); it can claim and re-grow the exited position"
    )


# --------------------------------------------------------------------------- #
# F1 — protection-open fails closed while a same-symbol buy may execute
# --------------------------------------------------------------------------- #
async def test_f1_protection_open_fails_closed_on_venue_uncertain_buy(any_store):
    session, _cand, buy_order = await _held_with_dispatched_buy(any_store)
    # Claim the buy to SUBMITTING — venue-uncertain, NOT locally cancellable.
    claim = await any_store.claim_order_for_submission(buy_order.id)
    assert claim.order is not None and claim.order.status is OrderStatus.SUBMITTING

    result = await any_store.open_protection_exit(
        symbol="AAPL",
        target_quantity=100,
        floor_price=9.0,
        observed_price=8.5,
        average_price=10.0,
        session_id=session.id,
    )
    assert result is None, (
        "protection minted a SELL beside a venue-uncertain same-symbol BUY "
        "(it would wedge behind the claim rail or be mis-sized if the BUY fills)"
    )
    # No PROTECTION_FLOOR exit intent was created (fail closed, retry next tick).
    intents = await any_store.list_sell_intents()
    assert not [
        si
        for si in intents
        if si.reason is SellReason.PROTECTION_FLOOR
        and si.status is not SellIntentStatus.EXPIRED
    ]


# --------------------------------------------------------------------------- #
# F2 — a late fill on an already-terminal envelope cancels a live CREATED child
# (memory must match SQLite; the state is legacy/crash-recovery, raw-built)
# --------------------------------------------------------------------------- #
def _raw_insert_order(store, order):
    if hasattr(store, "_orders"):
        store._orders[order.id] = order
        return
    with store._tx() as cur:
        store._insert_order(cur, order)


def _raw_insert_envelope(store, envelope):
    if hasattr(store, "_envelopes"):
        store._envelopes[envelope.id] = envelope
        return
    with store._tx() as cur:
        store._insert_envelope(cur, envelope)


def _raw_append_action(store, envelope, order):
    event = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=_NOW,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.limit_price,
        order_id=order.id,
        envelope_id=envelope.id,
        session_id=order.session_id,
        correlation_id=envelope.sell_intent_id,
        payload={"action": "submit", "snapshot_fingerprint": "wo0112-f2"},
    )
    if hasattr(store, "_execution_events"):
        store._execution_events.append(event)
        return
    with store._tx() as cur:
        store._insert_execution_event(cur, event)


async def test_f2_late_fill_on_terminal_envelope_cancels_created_child(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    # A legacy/crash-recovery TERMINAL envelope that still owns a live CREATED
    # staged child (the normal transition path would have cancelled it).
    envelope = _draft(intent.id, session.id).model_copy(
        update={
            "status": EnvelopeStatus.BREACHED,
            "approved_at": _NOW - timedelta(minutes=2),
            "activated_at": _NOW - timedelta(minutes=2),
            "breached_at": _NOW,
        }
    )
    _raw_insert_envelope(any_store, envelope)
    child = Order(
        id="wo0112-f2-created-child",
        sell_intent_id=intent.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CREATED,
        session_id=session.id,
    )
    _raw_insert_order(any_store, child)
    _raw_append_action(any_store, envelope, child)

    # A late fill on the already-terminal envelope: plan.transition is None.
    await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key="wo0112-f2-late",
        order_id=child.id,
        price=9.9,
    )

    after = await any_store.get_order(child.id)
    assert after.status is OrderStatus.CANCELED, (
        "late fill on a terminal envelope left the staged CREATED child live "
        f"(status {after.status!r}) — memory/SQLite parity break"
    )
