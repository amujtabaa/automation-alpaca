"""WO-0109 round-3 correctness pins.

Each safety pin is exercised through ``any_store`` so the in-memory and SQLite
implementations carry the same behavior.  Mutation evidence is recorded in the
work-order progress log and cluster commits.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import app.monitoring as monitoring
from app.broker.mock import MockBrokerAdapter
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_UNRESOLVED,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
    SubmitRecoveryRecord,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import CLAIM_BLOCKED, FLATTEN_BUYS_OPEN
from app.store.base import RecoveryTransitionError
from app.store.core import EnvelopeActionPausedError

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)


async def _held_position(store, *, symbol: str = "AAPL", quantity: int = 100):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    establishing_buy = await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        session_id=session.id,
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


async def _created_buy(store, session, *, symbol: str = "AAPL", quantity: int = 40):
    candidate = await store.create_candidate(symbol, session_id=session.id)
    return await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )


async def _terminal_buy_with_open_recovery(
    store,
    session,
    *,
    cleanup_status: str,
    symbol: str = "AAPL",
    quantity: int = 40,
):
    buy = await _created_buy(store, session, symbol=symbol, quantity=quantity)
    claim = await store.claim_order_for_submission(buy.id)
    assert claim.order is not None
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    await store.create_submit_recovery(
        local_order_id=buy.id,
        broker_order_id=f"paper-{buy.id}",
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=quantity,
        failure_reason="WO-0109 open BUY recovery pin",
        session_id=session.id,
        cleanup_status=cleanup_status,
    )
    return buy


# ---------------------------------------------------------------------------
# Cluster A — stale local-cancel compare-and-swap and BUY recovery exposure
# ---------------------------------------------------------------------------


async def test_stale_created_snapshot_cannot_cancel_claimed_buy(any_store, monkeypatch):
    """A CREATED snapshot must not terminalize the row after a concurrent claim."""

    session = await _held_position(any_store)
    buy = await _created_buy(any_store, session)
    real_list_orders = any_store.list_orders

    async def stale_snapshot_then_claim(*args, **kwargs):
        snapshot = await real_list_orders(*args, **kwargs)
        claim = await any_store.claim_order_for_submission(buy.id)
        assert claim.order is not None
        assert claim.order.status is OrderStatus.SUBMITTING
        return snapshot

    monkeypatch.setattr(any_store, "list_orders", stale_snapshot_then_claim)

    adapter = MockBrokerAdapter()
    await monitoring.cancel_open_buys(any_store, adapter, "AAPL")

    current = await any_store.get_order(buy.id)
    assert current is not None
    assert current.status is OrderStatus.SUBMITTING
    assert adapter.canceled == []

    flatten = await any_store.flatten_position("AAPL", actor="operator-a")
    assert flatten.outcome == FLATTEN_BUYS_OPEN
    assert flatten.order is None
    assert [o for o in await real_list_orders() if o.side is OrderSide.SELL] == []


@pytest.mark.parametrize("cleanup_status", [RECOVERY_UNRESOLVED, RECOVERY_NEEDS_REVIEW])
async def test_flatten_blocks_terminal_local_buy_with_open_recovery(
    any_store, cleanup_status
):
    """Flatten sees venue exposure even when the referenced BUY is local-terminal."""

    session = await _held_position(any_store)
    await _terminal_buy_with_open_recovery(
        any_store, session, cleanup_status=cleanup_status
    )

    result = await any_store.flatten_position("AAPL", actor="operator-a")

    assert result.outcome == FLATTEN_BUYS_OPEN
    assert result.intent is None and result.order is None
    assert [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ] == []


@pytest.mark.parametrize("cleanup_status", [RECOVERY_UNRESOLVED, RECOVERY_NEEDS_REVIEW])
async def test_final_sell_claim_blocks_terminal_local_buy_with_open_recovery(
    any_store, cleanup_status
):
    """The last pre-venue claim consumes the same BUY-exposure projection."""

    session = await _held_position(any_store)
    buy = await _terminal_buy_with_open_recovery(
        any_store, session, cleanup_status=cleanup_status
    )
    sell_candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    sell = await any_store.create_order_for_test(
        sell_candidate.id,
        "AAPL",
        OrderSide.SELL,
        100,
        session_id=session.id,
    )

    claim = await any_store.claim_order_for_submission(sell.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None
    assert "same-symbol BUY may execute" in claim.reason
    assert buy.id in claim.reason
    current = await any_store.get_order(sell.id)
    assert current is not None and current.status is OrderStatus.CREATED


# ---------------------------------------------------------------------------
# Cluster B — recovery ingress identity and honest stage/claim sibling pins
# ---------------------------------------------------------------------------


def _envelope_draft(intent_id: str, session_id: str) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
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


def _submit_action() -> PlannedAction:
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=100,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _active_envelope(store, session):
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _envelope_draft(intent.id, session.id), actor="operator-a"
    )
    return intent, envelope


async def _stage(store, envelope, *, suffix: str, now: datetime):
    return await store.stage_envelope_action(
        envelope.id,
        _submit_action(),
        snapshot_fingerprint=f"wo0109-b-{suffix}",
        now=now,
    )


async def _terminal_direct_sell(store, session):
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    order = await store.create_order_for_sell_intent(
        intent.id, order_type=OrderType.LIMIT, limit_price=9.9
    )
    claim = await store.claim_order_for_submission(order.id)
    assert claim.order is not None
    await store.transition_order(
        order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"paper-terminal-{order.id}",
    )
    await store.transition_order(order.id, OrderStatus.CANCELED)
    return order


async def _needs_review_sell_recovery(store, session, order) -> None:
    await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"paper-needs-review-{order.id}",
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason="WO-0109 honest sibling pin",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )


def _raw_insert_recovery(store, recovery: SubmitRecoveryRecord) -> None:
    """Seed a legacy row that predates the guarded public ingress."""

    if hasattr(store, "_submit_recoveries"):
        store._submit_recoveries.append(recovery)
        return
    with store._tx() as cur:
        store._insert_submit_recovery(cur, recovery)


@pytest.mark.parametrize(
    ("declared_symbol", "declared_side"),
    [("MSFT", OrderSide.SELL), ("AAPL", OrderSide.BUY)],
)
async def test_recovery_ingress_rejects_scope_that_contradicts_order(
    any_store, declared_symbol, declared_side
):
    """One malformed identity cannot de-index its referenced SELL exposure."""

    session = await _held_position(any_store)
    prior = await _terminal_direct_sell(any_store, session)
    second_candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    second = await any_store.create_order_for_test(
        second_candidate.id,
        "AAPL",
        OrderSide.SELL,
        100,
        session_id=session.id,
    )
    before = await any_store.list_submit_recoveries()

    with pytest.raises(RecoveryTransitionError, match="scope"):
        await any_store.create_submit_recovery(
            local_order_id=prior.id,
            broker_order_id=f"paper-misscoped-{prior.id}",
            symbol=declared_symbol,
            side=declared_side,
            quantity=prior.quantity,
            limit_price=prior.limit_price,
            failure_reason="WO-0109 contradictory recovery scope",
            session_id=session.id,
            cleanup_status=RECOVERY_NEEDS_REVIEW,
        )

    assert await any_store.list_submit_recoveries() == before
    current = await any_store.get_order(second.id)
    assert current is not None and current.status is OrderStatus.CREATED


@pytest.mark.parametrize(
    ("declared_symbol", "declared_side"),
    [("MSFT", OrderSide.SELL), ("AAPL", OrderSide.BUY)],
)
async def test_legacy_misscoped_direct_recovery_blocks_referenced_sell_scope(
    any_store, declared_symbol, declared_side
):
    """A persisted mismatch cannot hide O1 from O2's actual-symbol claim rail."""

    session = await _held_position(any_store)
    prior = await _terminal_direct_sell(any_store, session)
    _, envelope = await _active_envelope(any_store, session)
    second = await _stage(any_store, envelope, suffix="legacy-misscope", now=_NOW)
    _raw_insert_recovery(
        any_store,
        SubmitRecoveryRecord(
            local_order_id=prior.id,
            broker_order_id=f"paper-legacy-misscope-{prior.id}",
            symbol=declared_symbol,
            side=declared_side,
            quantity=prior.quantity,
            limit_price=prior.limit_price,
            failure_reason="WO-0109 legacy contradictory recovery scope",
            session_id=session.id,
            cleanup_status=RECOVERY_NEEDS_REVIEW,
        ),
    )

    claim = await any_store.claim_order_for_submission(second.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "direct SELL exposure" in claim.reason
    assert prior.id in claim.reason
    current = await any_store.get_order(second.order.id)
    assert current is not None and current.status is OrderStatus.CREATED


async def test_same_envelope_prior_sibling_blocks_claim_after_stage(any_store):
    """The recovery belongs to O1; the guarded final-claim consumer sees it on O2."""

    session = await _held_position(any_store)
    _, envelope = await _active_envelope(any_store, session)
    first = await _stage(any_store, envelope, suffix="same-first", now=_NOW)
    first_claim = await any_store.claim_order_for_submission(first.order.id)
    assert first_claim.order is not None
    await any_store.transition_order(
        first.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"paper-terminal-{first.order.id}",
    )
    await any_store.transition_order(first.order.id, OrderStatus.CANCELED)
    second = await _stage(
        any_store,
        envelope,
        suffix="same-second",
        now=_NOW + timedelta(seconds=1),
    )
    assert second.order.id != first.order.id
    await _needs_review_sell_recovery(any_store, session, first.order)

    claim = await any_store.claim_order_for_submission(second.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "needs_review" in claim.reason
    assert first.order.id in claim.reason


async def test_fresh_owner_direct_sibling_blocks_stage(any_store):
    """A fresh envelope created before the latch still revalidates at stage."""

    session = await _held_position(any_store)
    prior = await _terminal_direct_sell(any_store, session)
    _, envelope = await _active_envelope(any_store, session)
    await _needs_review_sell_recovery(any_store, session, prior)

    with pytest.raises(EnvelopeActionPausedError, match="direct SELL exposure"):
        await _stage(any_store, envelope, suffix="fresh-stage", now=_NOW)


async def test_fresh_owner_direct_sibling_blocks_claim_after_stage(any_store):
    """A direct recovery latched after O2 stages is rechecked at final claim."""

    session = await _held_position(any_store)
    prior = await _terminal_direct_sell(any_store, session)
    _, envelope = await _active_envelope(any_store, session)
    second = await _stage(any_store, envelope, suffix="fresh-claim", now=_NOW)
    await _needs_review_sell_recovery(any_store, session, prior)

    claim = await any_store.claim_order_for_submission(second.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "direct SELL exposure" in claim.reason
    assert prior.id in claim.reason
