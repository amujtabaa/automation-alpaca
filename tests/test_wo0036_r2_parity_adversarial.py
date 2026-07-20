"""Adversarial RED pins for WO-0036 R2 lifecycle-class closure.

These cases exercise persisted states that the aggregate lifecycle projection
must resolve without guessing: a terminal sibling with venue exposure, fill
truth arriving before terminal order truth, reverse-stale status columns, and
malformed pre-R2 ownership.  Every behavioral pin runs against both stores.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import FLATTEN_EXISTING, FlattenBlockedError
from app.store.core import EnvelopeActionPausedError, EnvelopeTransitionError

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)


def _draft(
    intent_id: str,
    *,
    symbol: str = "AAPL",
    quantity: int = 100,
    session_id: str,
) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=quantity,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _action(
    kind: ActionKind = ActionKind.SUBMIT,
    *,
    price: float = 9.9,
) -> PlannedAction:
    return PlannedAction(
        kind=kind,
        limit_price=price,
        quantity=100,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _activate(store):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        100,
        session_id=session.id,
    )
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        100,
        10.0,
        session_id=session.id,
    )
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _draft(intent.id, session_id=session.id), actor="operator-a"
    )
    return session, intent, envelope


async def _submitted_child(store, envelope_id: str):
    staged = await store.stage_envelope_action(
        envelope_id,
        _action(),
        snapshot_fingerprint="r2-parity-submit",
        now=NOW,
    )
    claimed = await store.claim_order_for_submission(staged.order.id)
    return await store.transition_order(
        claimed.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{claimed.order.id}",
    )


def _force_legacy_active(store, envelope_id: str) -> None:
    """Inject a pre-R2 ACTIVE row without invoking the now-guarded ingress."""

    if hasattr(store, "_envelopes"):
        envelope = store._envelopes[envelope_id]
        envelope.status = EnvelopeStatus.ACTIVE
        envelope.approved_at = NOW
        envelope.activated_at = NOW
        return
    store._conn.execute(
        "UPDATE execution_envelopes SET status=?, approved_at=?, activated_at=? "
        "WHERE id=?",
        (
            EnvelopeStatus.ACTIVE.value,
            NOW.isoformat(),
            NOW.isoformat(),
            envelope_id,
        ),
    )
    store._conn.commit()


def _force_raw_order_status(store, order_id: str, status: OrderStatus) -> None:
    if hasattr(store, "_orders"):
        store._orders[order_id].status = status
        return
    store._conn.execute(
        "UPDATE orders SET status=? WHERE id=?", (status.value, order_id)
    )
    store._conn.commit()


def _force_owner_symbol(store, intent_id: str, symbol: str) -> None:
    if hasattr(store, "_sell_intents"):
        store._sell_intents[intent_id].symbol = symbol
        return
    store._conn.execute(
        "UPDATE sell_intents SET symbol=? WHERE id=?", (symbol, intent_id)
    )
    store._conn.commit()


async def test_terminal_sibling_with_live_child_blocks_new_activation(any_store):
    session, intent, old = await _activate(any_store)
    child = await _submitted_child(any_store, old.id)
    await any_store.transition_envelope(
        old.id, EnvelopeStatus.BREACHED, reason="hard rail", now=NOW
    )
    successor = _draft(intent.id, session_id=session.id)

    with pytest.raises(EnvelopeTransitionError):
        await any_store.approve_envelope_activation(successor, actor="operator-a")

    assert await any_store.get_envelope(successor.id) is None
    assert (await any_store.get_order(child.id)).status is OrderStatus.SUBMITTED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_legacy_active_sibling_cannot_stage_beside_retained_child(any_store):
    session, intent, old = await _activate(any_store)
    child = await _submitted_child(any_store, old.id)
    await any_store.transition_envelope(
        old.id, EnvelopeStatus.BREACHED, reason="hard rail", now=NOW
    )
    successor = _draft(intent.id, session_id=session.id)
    await any_store.create_envelope(successor, actor="legacy-import")
    _force_legacy_active(any_store, successor.id)

    with pytest.raises(EnvelopeActionPausedError):
        await any_store.stage_envelope_action(
            successor.id,
            _action(),
            snapshot_fingerprint="r2-parity-foreign-child",
            now=NOW + timedelta(seconds=1),
        )

    sells = [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ]
    assert [order.id for order in sells] == [child.id]


async def test_flat_position_preserves_manager_of_possibly_live_child(any_store):
    session, intent, envelope = await _activate(any_store)
    child = await _submitted_child(any_store, envelope.id)
    await any_store.append_fill(
        child.id,
        "AAPL",
        OrderSide.SELL,
        100,
        9.9,
        source_fill_id="r2-parity-flat-before-terminal",
        session_id=session.id,
    )

    try:
        result = await any_store.flatten_position("AAPL", actor="operator-a")
    except FlattenBlockedError:
        pass
    else:
        assert result.outcome == FLATTEN_EXISTING
        assert result.deferred is True
        assert result.order is not None and result.order.id == child.id

    assert (await any_store.get_envelope(envelope.id)).status is EnvelopeStatus.ACTIVE
    assert (await any_store.get_order(child.id)).status is OrderStatus.SUBMITTED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_terminal_transition_uses_event_truth_over_reverse_stale_column(
    any_store,
):
    _, intent, envelope = await _activate(any_store)
    child = await _submitted_child(any_store, envelope.id)
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="hard rail", now=NOW
    )
    _force_raw_order_status(any_store, child.id, OrderStatus.CANCELED)

    await any_store.transition_order(child.id, OrderStatus.CANCELED)

    assert (await any_store.get_order(child.id)).status is OrderStatus.CANCELED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED


async def test_terminal_fact_does_not_mutate_malformed_legacy_owner(any_store):
    _, intent, envelope = await _activate(any_store)
    _force_owner_symbol(any_store, intent.id, "MSFT")

    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="hard rail", now=NOW
    )

    assert (await any_store.get_envelope(envelope.id)).status is EnvelopeStatus.BREACHED
    owner = await any_store.get_sell_intent(intent.id)
    assert owner.symbol == "MSFT"
    assert owner.status is SellIntentStatus.APPROVED


async def test_active_intent_selection_is_newest_first_in_both_stores(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    old = SellIntent(
        id="legacy-intent-old",
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
        created_at=NOW,
        updated_at=NOW,
    )
    newest = SellIntent(
        id="legacy-intent-new",
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
        created_at=NOW + timedelta(seconds=1),
        updated_at=NOW + timedelta(seconds=1),
    )
    if hasattr(any_store, "_sell_intents"):
        any_store._sell_intents[old.id] = old
        any_store._sell_intents[newest.id] = newest
    else:
        with any_store._tx() as cur:
            any_store._insert_sell_intent(cur, old)
            any_store._insert_sell_intent(cur, newest)

    active = await any_store.active_sell_intent_for("AAPL")
    assert active is not None and active.id == newest.id


async def test_mid_reprice_supersession_scans_past_created_replacement(any_store):
    session, intent, envelope = await _activate(any_store)
    predecessor = await _submitted_child(any_store, envelope.id)
    replacement = await any_store.stage_envelope_action(
        envelope.id,
        _action(ActionKind.REPRICE, price=9.8),
        snapshot_fingerprint="r2-parity-mid-reprice",
        now=NOW + timedelta(seconds=1),
    )
    successor = _draft(intent.id, quantity=90, session_id=session.id)

    with pytest.raises(EnvelopeTransitionError):
        await any_store.supersede_envelope(
            envelope.id, successor, actor="operator-a", reason="narrow bounds"
        )

    assert (await any_store.get_envelope(envelope.id)).status is EnvelopeStatus.ACTIVE
    assert await any_store.get_envelope(successor.id) is None
    assert (await any_store.get_order(predecessor.id)).status is OrderStatus.SUBMITTED
    assert (
        await any_store.get_order(replacement.order.id)
    ).status is OrderStatus.CREATED
