"""WO-0110 — the three P1 findings from the PR #9 Codex review.

Symmetric twins of the WO-0109 exit-preempt / recovery-aware exposure fixes,
exercised through ``any_store`` so memory and SQLite carry identical behavior.
Each pin is red on the pre-fix tree and mutation-verified in the commit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    CandidateStatus,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    RECOVERY_NEEDS_REVIEW,
    SellReason,
    SessionType,
    SubmitRecoveryRecord,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import OrderIntentBlockedError

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Shared setup helpers (mirrors of the WO-0109 pin helpers)
# --------------------------------------------------------------------------- #
async def _held_position(store, *, symbol: str = "AAPL", quantity: int = 100):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    establishing_buy = await store.create_order_for_test(
        candidate.id, symbol, OrderSide.BUY, quantity, session_id=session.id
    )
    await store.append_fill(
        establishing_buy.id,
        symbol,
        OrderSide.BUY,
        quantity,
        10.0,
        session_id=session.id,
    )
    await store.transition_order(establishing_buy.id, OrderStatus.CANCELED)
    return session


def _draft(intent_id: str, *, symbol: str = "AAPL", qty: int = 100, session_id=None):
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=qty,
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


def _submit_action(*, price: float = 9.9, qty: int = 100) -> PlannedAction:
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=price,
        quantity=qty,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _activate(store, *, symbol: str = "AAPL", qty: int = 100):
    session = await _held_position(store, symbol=symbol, quantity=qty)
    intent = await store.create_sell_intent(
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=qty,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _draft(intent.id, symbol=symbol, session_id=session.id), actor="operator-a"
    )
    return session, intent, envelope


async def _approved_buy_candidate(
    store, session, *, symbol: str = "AAPL", qty: int = 40
):
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, session_id=session.id
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return candidate


def _raw_insert_recovery(store, recovery: SubmitRecoveryRecord) -> None:
    if hasattr(store, "_submit_recoveries"):
        store._submit_recoveries.append(recovery)
        return
    with store._tx() as cur:
        store._insert_submit_recovery(cur, recovery)


# --------------------------------------------------------------------------- #
# P1-a — an envelope staging its SELL child stands down same-symbol BUY candidates
# --------------------------------------------------------------------------- #
async def test_p1a_envelope_stage_stands_down_same_symbol_buy_candidate(any_store):
    session, _intent, envelope = await _activate(any_store)
    buy_candidate = await _approved_buy_candidate(any_store, session)

    staged = await any_store.stage_envelope_action(
        envelope.id, _submit_action(), snapshot_fingerprint="wo0110-p1a", now=_NOW
    )
    assert staged.order is not None and staged.order.side is OrderSide.SELL

    # The exit was minted; the same-symbol BUY candidate must be stood down in the
    # SAME stage transaction, exactly as the direct-protection and flatten paths do.
    after = await any_store.get_candidate(buy_candidate.id)
    assert after.status is CandidateStatus.EXPIRED, (
        "envelope-stage exit did not stand down the same-symbol BUY candidate "
        f"(status {after.status!r}) — it can re-grow the exited position"
    )


# --------------------------------------------------------------------------- #
# P1-b — a same-symbol BUY is blocked while an open SELL recovery may execute
# --------------------------------------------------------------------------- #
async def test_p1b_buy_dispatch_blocked_by_open_sell_recovery(any_store):
    session = await _held_position(any_store)
    # Precreate the approved candidate to model a legacy handoff race. Candidate
    # admission is now refused once the recovery exists; retaining this older
    # artifact keeps the downstream candidate-to-order backstop covered.
    buy_candidate = await _approved_buy_candidate(any_store, session)
    # A SELL that reached the broker but whose local row fell back to an open
    # needs_review recovery (the broker order may still execute).
    sell_cand = await any_store.create_candidate("AAPL", session_id=session.id)
    sell = await any_store.create_order_for_test(
        sell_cand.id, "AAPL", OrderSide.SELL, 100, session_id=session.id
    )
    await any_store.transition_order(sell.id, OrderStatus.CANCELED)
    await any_store.create_submit_recovery(
        local_order_id=sell.id,
        broker_order_id=f"paper-{sell.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="WO-0110 open SELL recovery",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )

    with pytest.raises(OrderIntentBlockedError, match="exit"):
        await any_store.create_order_for_candidate(buy_candidate.id)


# --------------------------------------------------------------------------- #
# P1-c — a legacy misscoped open BUY recovery is seen through its referenced order
# --------------------------------------------------------------------------- #
async def test_p1c_flatten_blocked_by_misscoped_open_buy_recovery(any_store):
    session = await _held_position(any_store)
    buy_candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(
        buy_candidate.id, "AAPL", OrderSide.BUY, 40, session_id=session.id
    )
    await any_store.transition_order(buy.id, OrderStatus.CANCELED)  # local terminal

    # Legacy misscoped recovery (predates the ingress guard): declares MSFT/SELL
    # while local_order_id points at this symbol's BUY order. Raw-inserted to
    # bypass the scope-validating ingress.
    _raw_insert_recovery(
        any_store,
        SubmitRecoveryRecord(
            local_order_id=buy.id,
            broker_order_id=f"paper-{buy.id}",
            symbol="MSFT",
            side=OrderSide.SELL,
            quantity=40,
            failure_reason="WO-0110 legacy misscoped BUY recovery",
            session_id=session.id,
            cleanup_status=RECOVERY_NEEDS_REVIEW,
        ),
    )

    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.order is None, (
        "flatten minted a SELL beside a possibly-live BUY whose only visible "
        "identity is the misscoped recovery's referenced order"
    )
