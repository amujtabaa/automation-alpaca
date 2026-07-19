"""WO-0113 C1 closure pins for the raw/public SELL store boundary.

Production protection and manual flattening use fused store operations, but the
decomposed sell-intent APIs remain public StateStore methods. They must preserve
the same HALTED and cross-side exposure rules when called directly.
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
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import CLAIM_BLOCKED, FlattenBlockedError, SellIntentTransitionError
from app.store.core import EnvelopeActionPausedError

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)


async def _held_position(store, *, symbol: str = "AAPL", quantity: int = 100):
    """Establish a position while leaving no working establishing BUY."""

    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        limit_price=10.0,
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
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    await store.transition_candidate(candidate.id, CandidateStatus.EXPIRED)
    return session


async def _created_buy(store, *, symbol: str = "AAPL", quantity: int = 10):
    candidate = await store.create_candidate(
        symbol,
        suggested_quantity=quantity,
        suggested_limit_price=10.0,
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(candidate.id)
    assert order.status is OrderStatus.CREATED
    return candidate, order


async def _approved_exit(
    store,
    *,
    reason: SellReason = SellReason.PROTECTION_FLOOR,
    symbol: str = "AAPL",
    quantity: int = 100,
):
    intent = await store.create_sell_intent(
        symbol=symbol,
        reason=reason,
        target_quantity=quantity,
    )
    await store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    return intent


def _draft(intent_id: str, session_id: str, *, quantity: int = 100):
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
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


def _submit_action(quantity: int = 100):
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _activate_envelope(store, session, *, quantity: int = 100):
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=quantity,
        session_id=session.id,
    )
    return await store.approve_envelope_activation(
        _draft(intent.id, session.id, quantity=quantity), actor="wo0113"
    )


async def _attach_broker_identity_to_created_buy(store, order):
    attached = await store.transition_order(
        order.id,
        OrderStatus.CREATED,
        broker_order_id=f"broker-{order.id}",
    )
    assert attached.status is OrderStatus.CREATED
    assert attached.broker_order_id == f"broker-{order.id}"
    return attached


async def test_direct_manual_intent_creation_is_denied_while_halted(any_store):
    """The decomposed API cannot bypass ``flatten_position``'s HALTED gate."""

    await any_store.initialize()
    await any_store.set_kill_switch(True)

    with pytest.raises(FlattenBlockedError, match="halted"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.MANUAL_FLATTEN,
            target_quantity=100,
        )

    assert await any_store.list_sell_intents(symbol="AAPL") == []
    assert [
        order
        for order in await any_store.list_orders()
        if order.symbol == "AAPL" and order.side is OrderSide.SELL
    ] == []


async def test_direct_manual_dispatch_rechecks_halted_and_self_heals(any_store):
    """A halt landing after intent approval still blocks the order mint."""

    await _held_position(any_store)
    intent = await _approved_exit(any_store, reason=SellReason.MANUAL_FLATTEN)
    await any_store.set_kill_switch(True)

    with pytest.raises(FlattenBlockedError, match="halted"):
        await any_store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.MARKET,
        )

    refreshed = await any_store.get_sell_intent(intent.id)
    assert refreshed is not None
    assert refreshed.status is SellIntentStatus.EXPIRED
    assert refreshed.order_id is None
    assert [
        order
        for order in await any_store.list_orders()
        if order.symbol == "AAPL" and order.side is OrderSide.SELL
    ] == []


async def test_direct_sell_dispatch_blocks_venue_uncertain_buy(any_store):
    """The raw dispatcher cannot size a SELL beside a possibly-executing BUY."""

    await _held_position(any_store)
    _, buy = await _created_buy(any_store)
    claim = await any_store.claim_order_for_submission(buy.id)
    assert claim.order is not None
    assert claim.order.status is OrderStatus.SUBMITTING
    intent = await _approved_exit(any_store)

    with pytest.raises(SellIntentTransitionError, match="same-symbol BUY may execute"):
        await any_store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.MARKET,
        )

    refreshed = await any_store.get_sell_intent(intent.id)
    assert refreshed is not None
    assert refreshed.status is SellIntentStatus.EXPIRED
    assert refreshed.order_id is None
    assert (await any_store.get_order(buy.id)).status is OrderStatus.SUBMITTING
    assert [
        order
        for order in await any_store.list_orders()
        if order.symbol == "AAPL" and order.side is OrderSide.SELL
    ] == []


async def test_direct_sell_dispatch_blocks_recovery_owned_created_buy(any_store):
    """A projected-CREATED BUY with open recovery is still venue-uncertain."""

    await _held_position(any_store)
    _, buy = await _created_buy(any_store)
    await any_store.create_submit_recovery(
        local_order_id=buy.id,
        broker_order_id="broker-wo0113-created-buy",
        client_order_id=buy.id,
        symbol=buy.symbol,
        side=buy.side,
        quantity=buy.quantity,
        limit_price=buy.limit_price,
        failure_reason="injected accepted submit ambiguity",
        session_id=buy.session_id,
        candidate_id=buy.candidate_id,
    )
    intent = await _approved_exit(any_store)

    with pytest.raises(SellIntentTransitionError, match="same-symbol BUY may execute"):
        await any_store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.MARKET,
        )

    refreshed = await any_store.get_sell_intent(intent.id)
    assert refreshed is not None
    assert refreshed.status is SellIntentStatus.EXPIRED
    assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED


async def test_direct_sell_dispatch_blocks_broker_owned_created_buy(any_store):
    """A broker identity makes projected-CREATED BUY venue exposure concrete."""

    await _held_position(any_store)
    _, buy = await _created_buy(any_store)
    await _attach_broker_identity_to_created_buy(any_store, buy)
    intent = await _approved_exit(any_store)

    with pytest.raises(SellIntentTransitionError, match="same-symbol BUY may execute"):
        await any_store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.MARKET,
        )

    assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED
    assert [
        order
        for order in await any_store.list_orders()
        if order.symbol == "AAPL" and order.side is OrderSide.SELL
    ] == []


async def test_envelope_stage_blocks_broker_owned_created_buy(any_store):
    """Envelope staging cannot cancel-and-cross a broker-owned CREATED BUY."""

    session = await _held_position(any_store)
    _, buy = await _created_buy(any_store)
    await _attach_broker_identity_to_created_buy(any_store, buy)
    envelope = await _activate_envelope(any_store, session)
    order_ids_before = {order.id for order in await any_store.list_orders()}

    with pytest.raises(EnvelopeActionPausedError, match="same-symbol BUY may execute"):
        await any_store.stage_envelope_action(
            envelope.id,
            _submit_action(),
            snapshot_fingerprint="wo0113-broker-owned-created-buy",
            now=NOW,
        )

    assert {order.id for order in await any_store.list_orders()} == order_ids_before
    assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED


async def test_sell_claim_blocks_broker_owned_created_buy_race(any_store):
    """The final claim closes the race after SELL staging but before venue I/O."""

    session = await _held_position(any_store)
    owner_candidate = (await any_store.list_candidates(session_id=session.id))[0]
    envelope = await _activate_envelope(any_store, session)
    staged = await any_store.stage_envelope_action(
        envelope.id,
        _submit_action(),
        snapshot_fingerprint="wo0113-before-created-buy-race",
        now=NOW,
    )
    assert staged.order is not None
    buy = await any_store.create_order_for_test(
        owner_candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
        session_id=session.id,
    )
    await _attach_broker_identity_to_created_buy(any_store, buy)

    claim = await any_store.claim_order_for_submission(staged.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert "same-symbol BUY may execute" in claim.reason
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CREATED


async def test_direct_sell_dispatch_stands_down_local_buy_epoch(any_store):
    """A successful raw dispatch closes every still-local same-symbol BUY path."""

    await _held_position(any_store)
    _, created_buy = await _created_buy(any_store)
    pending = await any_store.create_candidate(
        "AAPL",
        suggested_quantity=5,
        suggested_limit_price=10.0,
    )
    intent = await _approved_exit(any_store)

    sell = await any_store.create_order_for_sell_intent(
        intent.id,
        order_type=OrderType.MARKET,
    )

    assert sell.side is OrderSide.SELL
    assert sell.status is OrderStatus.CREATED
    assert (await any_store.get_order(created_buy.id)).status is OrderStatus.CANCELED
    refreshed_pending = await any_store.get_candidate(pending.id)
    assert refreshed_pending is not None
    assert refreshed_pending.status is CandidateStatus.EXPIRED
    exit_preemptions = [
        event
        for event in await any_store.list_events(event_type="candidate_transition")
        if event.candidate_id == pending.id
        and event.payload.get("reason") == "exit_preemption"
    ]
    assert len(exit_preemptions) == 1
