"""WO-0036 R2 — structural SellIntent↔Envelope lifecycle linking.

The contract is deliberately store-parametrized.  The link is not one happy-path
status update: every ingress validates the owner, every egress consults the same
persisted obligation projection, and every consumer that could mint a sibling
SELL observes that projection.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
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
from app.store.base import (
    CLAIM_CLAIMED,
    FlattenBlockedError,
    InvalidOrderError,
    SellIntentTransitionError,
)
from app.store.core import project_envelope_obligation

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
FP = "wo0036-r2"


def _draft(intent_id: str, *, symbol: str = "AAPL", **overrides) -> ExecutionEnvelope:
    values = dict(
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
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    values.update(overrides)
    return ExecutionEnvelope(**values)


def _action(
    kind: ActionKind = ActionKind.SUBMIT, *, price: float = 9.9
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


async def _hold(store, *, symbol: str = "AAPL", quantity: int = 100):
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )
    await store.append_fill(
        buy.id,
        symbol,
        OrderSide.BUY,
        quantity,
        10.0,
        session_id=session.id,
    )
    # Terminalize the establishing BUY so the held position carries no lingering
    # "open buy": the realistic state (a filled buy is done). Since WO-0036 R2
    # Option B, flatten_position detects a still-open BUY under its lock and
    # returns FLATTEN_BUYS_OPEN (caller cancels + retries) rather than minting a
    # SELL next to a live BUY; leaving this buy CREATED would exercise that
    # signal instead of the envelope-deferral outcomes these tests pin.
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    return session


async def _activate(
    store,
    *,
    symbol: str = "AAPL",
    quantity: int = 100,
    disposition: EnvelopeExpiryDisposition = EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
):
    await store.initialize()
    session = await _hold(store, symbol=symbol, quantity=quantity)
    intent = await store.create_sell_intent(
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=quantity,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _draft(
            intent.id,
            symbol=symbol,
            qty_ceiling=quantity,
            session_id=session.id,
            expiry_disposition=disposition,
        ),
        actor="operator-a",
    )
    return session, intent, envelope


async def _submitted_child(store, envelope_id: str):
    staged = await store.stage_envelope_action(
        envelope_id,
        _action(),
        snapshot_fingerprint=FP,
        now=NOW,
    )
    claimed = await store.claim_order_for_submission(staged.order.id)
    return await store.transition_order(
        claimed.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{claimed.order.id}",
    )


async def test_activation_approves_the_real_owner_and_close_spares_it(any_store):
    session, intent, envelope = await _activate(any_store)

    linked = await any_store.get_sell_intent(intent.id)
    assert linked.status is SellIntentStatus.APPROVED
    assert (await any_store.active_sell_intent_for("AAPL")).id == intent.id

    await any_store.close_session(session.id, actor="operator-a")
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    assert (await any_store.get_envelope(envelope.id)).status is EnvelopeStatus.ACTIVE


@pytest.mark.parametrize(
    "case",
    ["missing", "symbol", "terminal", "reason", "quantity", "session"],
)
async def test_activation_rejects_every_invalid_owner_binding(any_store, case):
    await any_store.initialize()
    session = await any_store.get_current_session()

    if case == "missing":
        draft = _draft("does-not-exist", session_id=session.id)
    else:
        symbol = "MSFT" if case == "symbol" else "AAPL"
        reason = (
            SellReason.MANUAL_FLATTEN
            if case == "reason"
            else SellReason.PROTECTION_FLOOR
        )
        quantity = 10 if case == "quantity" else 100
        intent = await any_store.create_sell_intent(
            symbol=symbol,
            reason=reason,
            target_quantity=quantity,
            session_id=session.id,
        )
        if case == "terminal":
            await any_store.transition_sell_intent(intent.id, SellIntentStatus.EXPIRED)
        draft = _draft(
            intent.id,
            session_id=("different-session" if case == "session" else session.id),
        )

    with pytest.raises(InvalidOrderError, match="envelope owner"):
        await any_store.approve_envelope_activation(draft, actor="operator-a")
    assert await any_store.get_envelope(draft.id) is None


async def test_direct_approval_ingress_uses_the_same_owner_link(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    draft = _draft(intent.id, session_id=session.id)
    await any_store.create_envelope(draft, actor="operator-a")

    approved = await any_store.transition_envelope(
        draft.id, EnvelopeStatus.APPROVED, actor="operator-a", now=NOW
    )
    assert approved.status is EnvelopeStatus.APPROVED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    active = await any_store.transition_envelope(
        draft.id, EnvelopeStatus.ACTIVE, actor="operator-a", now=NOW
    )
    assert active.status is EnvelopeStatus.ACTIVE


async def test_envelope_delegation_closes_legacy_dispatch_and_direct_release(any_store):
    _, intent, _ = await _activate(any_store)

    with pytest.raises(SellIntentTransitionError, match="envelope delegation"):
        await any_store.create_order_for_sell_intent(
            intent.id, order_type=OrderType.MARKET
        )
    with pytest.raises(SellIntentTransitionError, match="envelope delegation"):
        await any_store.transition_sell_intent(intent.id, SellIntentStatus.EXPIRED)
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    assert [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ] == []


async def test_terminal_envelope_without_child_releases_its_owner(any_store):
    _, intent, envelope = await _activate(any_store)

    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.BREACHED,
        reason="hard rail",
        now=NOW,
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
    assert await any_store.active_sell_intent_for("AAPL") is None


async def test_terminal_envelope_retains_owner_until_venue_child_resolves(any_store):
    session, intent, envelope = await _activate(
        any_store, disposition=EnvelopeExpiryDisposition.REST_AT_FLOOR
    )
    child = await _submitted_child(any_store, envelope.id)

    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.EXPIRED, reason="ttl", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    assert (await any_store.active_sell_intent_for("AAPL")).id == intent.id

    await any_store.close_session(session.id, actor="operator-a")
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED

    await any_store.transition_order(child.id, OrderStatus.CANCELED)
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
    assert await any_store.active_sell_intent_for("AAPL") is None


async def test_flatten_defers_to_real_envelope_child(any_store):
    _, intent, envelope = await _activate(any_store)
    child = await _submitted_child(any_store, envelope.id)

    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.deferred is True
    assert result.intent.id == intent.id
    assert result.order.id == child.id
    assert (await any_store.get_envelope(envelope.id)).status is EnvelopeStatus.ACTIVE
    assert (
        len(
            [
                order
                for order in await any_store.list_orders()
                if order.side is OrderSide.SELL
            ]
        )
        == 1
    )


async def test_mid_reprice_created_child_cannot_hide_submitted_predecessor(any_store):
    _, intent, envelope = await _activate(any_store)
    predecessor = await _submitted_child(any_store, envelope.id)
    replacement = await any_store.stage_envelope_action(
        envelope.id,
        _action(ActionKind.REPRICE, price=9.8),
        snapshot_fingerprint=f"{FP}-reprice",
        now=NOW + timedelta(seconds=1),
    )
    assert replacement.order.status is OrderStatus.CREATED

    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.deferred is True
    assert result.intent.id == intent.id
    assert result.order.id == predecessor.id
    assert (
        await any_store.get_order(replacement.order.id)
    ).status is OrderStatus.CREATED
    assert (await any_store.get_envelope(envelope.id)).status is EnvelopeStatus.ACTIVE


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.CREATED,
        OrderStatus.SUBMITTING,
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.TIMEOUT_QUARANTINE,
    ],
)
def test_projection_retains_terminal_lineage_for_every_unresolved_child(status):
    envelope = _draft("si-1").model_copy(
        update={
            "status": EnvelopeStatus.BREACHED,
            "approved_at": NOW - timedelta(minutes=1),
            "breached_at": NOW,
        }
    )
    order = Order(
        sell_intent_id="si-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=status,
    )
    action = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=NOW,
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        price=9.9,
        order_id=order.id,
        envelope_id=envelope.id,
        correlation_id="si-1",
        payload={"action": "submit"},
    )

    projection = project_envelope_obligation(
        envelopes=[envelope], action_events=[action], orders_by_id={order.id: order}
    )
    assert projection.linked is True
    assert projection.retains_intent is True
    assert projection.unresolved_order_ids == (order.id,)
    assert bool(projection.venue_orders) is (status is not OrderStatus.CREATED)


def test_projection_fails_closed_for_missing_child_and_releases_terminal_children():
    envelope = _draft("si-1").model_copy(
        update={
            "status": EnvelopeStatus.EXPIRED,
            "approved_at": NOW - timedelta(minutes=1),
            "expired_at": NOW,
        }
    )
    action = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=NOW,
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        price=9.9,
        order_id="child-1",
        envelope_id=envelope.id,
        correlation_id="si-1",
        payload={"action": "submit"},
    )
    missing = project_envelope_obligation(
        envelopes=[envelope], action_events=[action], orders_by_id={}
    )
    assert missing.retains_intent is True
    assert missing.missing_order_ids == ("child-1",)

    for terminal in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED):
        order = Order(
            id="child-1",
            sell_intent_id="si-1",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            limit_price=9.9,
            status=terminal,
        )
        released = project_envelope_obligation(
            envelopes=[envelope],
            action_events=[action],
            orders_by_id={order.id: order},
        )
        assert released.linked is True
        assert released.retains_intent is False


async def test_multiple_venue_windows_block_flatten_instead_of_guessing(any_store):
    _, _, envelope = await _activate(any_store)
    await _submitted_child(any_store, envelope.id)
    replacement = await any_store.stage_envelope_action(
        envelope.id,
        _action(ActionKind.REPRICE, price=9.8),
        snapshot_fingerprint=f"{FP}-ambiguous",
        now=NOW + timedelta(seconds=1),
    )
    claim = await any_store.claim_order_for_submission(replacement.order.id)
    assert claim.outcome == CLAIM_CLAIMED

    with pytest.raises(FlattenBlockedError, match="multiple envelope children"):
        await any_store.flatten_position("AAPL", actor="operator-a")


async def test_flatten_preemption_releases_staged_owner_exactly_once(any_store):
    _, intent, envelope = await _activate(any_store)
    staged = await any_store.stage_envelope_action(
        envelope.id,
        _action(),
        snapshot_fingerprint=f"{FP}-staged",
        now=NOW,
    )

    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.deferred is False
    assert result.superseded is True
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert (
        await any_store.get_envelope(envelope.id)
    ).status is EnvelopeStatus.CANCELLED
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CANCELED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
    releases = [
        event
        for event in await any_store.list_events()
        if event.correlation_id == intent.id
        and event.event_type == "sell_intent_transition"
        and event.payload.get("reason") == "envelope_delegation_released"
    ]
    assert len(releases) == 1


async def test_supersession_transfers_one_owner_without_release_gap(any_store):
    session, intent, old = await _activate(any_store)
    successor = _draft(
        intent.id,
        qty_ceiling=90,
        session_id=session.id,
    )
    current = await any_store.supersede_envelope(
        old.id, successor, actor="operator-a", reason="narrow bounds"
    )
    assert (await any_store.get_envelope(old.id)).status is EnvelopeStatus.SUPERSEDED
    assert current.status is EnvelopeStatus.ACTIVE
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED

    await any_store.transition_envelope(
        current.id, EnvelopeStatus.BREACHED, reason="hard rail", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED


async def test_event_truth_not_stale_order_column_controls_release(any_store):
    _, intent, envelope = await _activate(any_store)
    child = await _submitted_child(any_store, envelope.id)

    if hasattr(any_store, "_orders"):
        any_store._orders[child.id].status = OrderStatus.CANCELED
    else:
        any_store._conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (OrderStatus.CANCELED.value, child.id),
        )
        any_store._conn.commit()
    assert (await any_store.get_order(child.id)).status is OrderStatus.SUBMITTED

    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.EXPIRED, reason="ttl", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_broker_fill_truth_survives_a_missing_legacy_owner(any_store):
    _, intent, envelope = await _activate(any_store)
    child = await _submitted_child(any_store, envelope.id)
    if hasattr(any_store, "_sell_intents"):
        any_store._sell_intents.pop(intent.id)
    else:
        any_store._conn.execute("DELETE FROM sell_intents WHERE id = ?", (intent.id,))
        any_store._conn.commit()

    completed = await any_store.record_envelope_fill(
        envelope.id,
        quantity=100,
        dedupe_key=f"fill:{child.id}:legacy-owner",
        price=9.9,
        order_id=child.id,
        now=NOW,
    )
    assert completed.status is EnvelopeStatus.COMPLETED
    assert completed.remaining_quantity == 0


async def test_initialize_converges_a_pre_r2_released_owner(any_store):
    _, intent, envelope = await _activate(any_store)
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="hard rail", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED

    if hasattr(any_store, "_sell_intents"):
        legacy = any_store._sell_intents[intent.id]
        legacy.status = SellIntentStatus.APPROVED
        legacy.expired_at = None
    else:
        any_store._conn.execute(
            "UPDATE sell_intents SET status = ?, expired_at = NULL WHERE id = ?",
            (SellIntentStatus.APPROVED.value, intent.id),
        )
        any_store._conn.commit()

    await any_store.initialize()
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
