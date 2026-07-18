"""Hostile closure pins for WO-0036 R2 lifecycle linking.

These tests intentionally seed legacy/corrupt persisted shapes that public R2
ingress now refuses.  The safety contract is fail-closed: ambiguity must retain
the SELL obligation and every order-minting choke point must observe the same
projection in both stores.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.broker.adapter import BrokerError, BrokerFill, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_RESOLVED,
    RECOVERY_UNRESOLVED,
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
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionType,
    SubmitRecoveryRecord,
)
from app.sellside.types import ActionKind, PlannedAction
from app.monitoring import (
    _apply_update,
    _cancel_envelope_working_order,
    _converge_expired_envelope_cancels,
    _record_recovery_terminal_fact,
    _recover_unpersisted_submits,
    _validated_envelope_lineage,
)
from app.reconciliation import (
    ENVELOPE_EXEC_BLOCKED,
    ENVELOPE_EXEC_REPRICED,
    ENVELOPE_EXEC_SUBMITTED,
    _drive_staged_order,
    execute_envelope_action,
)
from app.store.sqlite import SqliteStateStore
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    FlattenBlockedError,
    InvalidFillError,
    InvalidOrderError,
    OrderTransitionError,
    RecoveryTransitionError,
    SellIntentTransitionError,
)
from app.store.core import (
    EnvelopeActionPausedError,
    EnvelopeTransitionError,
    direct_sell_order_may_execute,
    plan_envelope_transition,
    project_envelope_obligation,
    recovery_resolution_execution_event,
    recovery_terminal_fact_matches,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
CAUSAL_TIME = NOW + timedelta(minutes=1)
INGEST_TIME = NOW + timedelta(minutes=9)
FP = "wo0036-r2-hostile"


def _draft(
    intent_id: str,
    *,
    symbol: str = "AAPL",
    quantity: int = 100,
    session_id: str | None = None,
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
    *,
    kind: ActionKind = ActionKind.SUBMIT,
    price: float = 9.9,
    quantity: int = 100,
) -> PlannedAction:
    return PlannedAction(
        kind=kind,
        limit_price=price,
        quantity=quantity,
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
        source_fill_id=f"{FP}:hold:{candidate.id}",
        session_id=session.id,
    )
    return session


async def _activate(store):
    await store.initialize()
    session = await _hold(store)
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


async def _stage(store, envelope_id: str):
    return await store.stage_envelope_action(
        envelope_id,
        _action(),
        snapshot_fingerprint=FP,
        now=NOW,
    )


def _raw_insert_intent(store, intent: SellIntent) -> None:
    if hasattr(store, "_sell_intents"):
        store._sell_intents[intent.id] = intent
        return
    with store._tx() as cur:
        store._insert_sell_intent(cur, intent)


def _raw_insert_envelope(store, envelope: ExecutionEnvelope) -> None:
    if hasattr(store, "_envelopes"):
        store._envelopes[envelope.id] = envelope
        return
    with store._tx() as cur:
        store._insert_envelope(cur, envelope)


def _raw_replace_envelope(store, envelope: ExecutionEnvelope) -> None:
    if hasattr(store, "_envelopes"):
        store._envelopes[envelope.id] = envelope
        return
    with store._tx() as cur:
        store._update_envelope(cur, envelope)


def _raw_insert_order(store, order: Order) -> None:
    if hasattr(store, "_orders"):
        store._orders[order.id] = order
        return
    with store._tx() as cur:
        store._insert_order(cur, order)


def _raw_append_execution(store, event: ExecutionEvent) -> ExecutionEvent:
    if hasattr(store, "_execution_events"):
        return store._append_execution_event_unlocked(event)
    with store._tx() as cur:
        return store._insert_execution_event(cur, event)


def _raw_force_owner_status(store, intent_id: str, status: SellIntentStatus) -> None:
    if hasattr(store, "_sell_intents"):
        intent = store._sell_intents[intent_id]
        intent.status = status
        intent.approved_at = NOW if status is SellIntentStatus.APPROVED else None
        intent.expired_at = NOW if status is SellIntentStatus.EXPIRED else None
        return
    store._conn.execute(
        "UPDATE sell_intents SET status=?, approved_at=?, expired_at=? WHERE id=?",
        (
            status.value,
            NOW.isoformat() if status is SellIntentStatus.APPROVED else None,
            NOW.isoformat() if status is SellIntentStatus.EXPIRED else None,
            intent_id,
        ),
    )
    store._conn.commit()


def _action_event(
    envelope: ExecutionEnvelope,
    order: Order,
    *,
    envelope_id: str | None = None,
    correlation_id: str | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=NOW,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.limit_price,
        order_id=order.id,
        envelope_id=envelope.id if envelope_id is None else envelope_id,
        session_id=order.session_id,
        correlation_id=(
            envelope.sell_intent_id if correlation_id is None else correlation_id
        ),
        payload={"action": "submit", "snapshot_fingerprint": FP},
    )


def _status_event(
    event_type: ExecutionEventType,
    order: Order,
    envelope: ExecutionEnvelope,
    *,
    authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
    source: EventSource = EventSource.BROKER_REST,
    ts_event: datetime = NOW,
    ts_init: datetime = NOW,
    sequence: int = 0,
) -> ExecutionEvent:
    return ExecutionEvent(
        sequence=sequence,
        event_type=event_type,
        source=source,
        authority=authority,
        ts_event=ts_event,
        ts_init=ts_init,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=order.limit_price,
        order_id=order.id,
        envelope_id=envelope.id,
        session_id=order.session_id,
        correlation_id=envelope.sell_intent_id,
    )


def _raw_seed_live_child(store, envelope: ExecutionEnvelope, *, order_id: str) -> Order:
    order = Order(
        id=order_id,
        sell_intent_id=envelope.sell_intent_id,
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=envelope.qty_ceiling,
        limit_price=9.9,
        status=OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{order_id}",
        session_id=envelope.session_id,
        submitted_at=NOW,
    )
    _raw_insert_order(store, order)
    _raw_append_execution(store, _action_event(envelope, order))
    _raw_append_execution(
        store, _status_event(ExecutionEventType.SUBMITTED, order, envelope)
    )
    return order


def _terminal_envelope(intent_id: str, *, session_id: str | None) -> ExecutionEnvelope:
    return _draft(intent_id, session_id=session_id).model_copy(
        update={
            "status": EnvelopeStatus.BREACHED,
            "approved_at": NOW - timedelta(minutes=1),
            "activated_at": NOW - timedelta(minutes=1),
            "breached_at": NOW,
        }
    )


@pytest.mark.parametrize(
    ("case", "event_update", "order_update"),
    [
        ("event-below-floor", {"price": 8.99}, {}),
        ("event-over-ceiling", {"quantity": 101}, {}),
        ("event-wrong-session", {"session_id": "other-session"}, {}),
        ("event-wrong-correlation", {"correlation_id": "other-owner"}, {}),
        ("market-order", {}, {"order_type": OrderType.MARKET}),
        ("order-below-floor", {}, {"limit_price": 8.99}),
        ("order-over-ceiling", {}, {"quantity": 101}),
        ("order-wrong-session", {}, {"session_id": "other-session"}),
        ("event-order-quantity-disagree", {}, {"quantity": 99}),
        ("event-order-price-disagree", {}, {"limit_price": 9.8}),
    ],
)
def test_projection_fails_closed_for_every_bounded_child_mismatch(
    case, event_update, order_update
):
    del case
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    order = Order(
        id="child-1",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    ).model_copy(update=order_update)
    action = _action_event(envelope, order).model_copy(
        update={"quantity": 100, "price": 9.9, **event_update}
    )

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
    )

    assert projected.retains_intent is True
    assert projected.invalid_order_ids == (order.id,)


def test_projection_retains_an_action_whose_child_identity_is_missing():
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    child = Order(
        id="identified-only-before-corruption",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    )
    action = _action_event(envelope, child).model_copy(update={"order_id": None})

    projected = project_envelope_obligation(
        envelopes=[envelope], action_events=[action], orders_by_id={}
    )

    assert projected.linked is True
    assert projected.retains_intent is True
    assert projected.missing_order_ids == (f"<missing-order-id:{envelope.id}>",)


@pytest.mark.parametrize(
    "event_update",
    [
        {"price": 9.8},
        {"quantity": 99},
        {"payload": {"action": "reprice", "snapshot_fingerprint": FP}},
        {"source": EventSource.BROKER_REST},
        {"authority": EventAuthority.BROKER_AUTHORITATIVE},
    ],
    ids=["price", "quantity", "payload", "source", "authority"],
)
def test_projection_rejects_a_later_conflicting_action_for_the_same_child(
    event_update,
):
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    order = Order(
        id="child-1",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    )
    canonical = _action_event(envelope, order)
    conflicting = canonical.model_copy(update=event_update)

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[canonical, conflicting],
        orders_by_id={order.id: order},
    )

    assert projected.retains_intent is True
    assert projected.invalid_order_ids == (order.id,)


@pytest.mark.parametrize(
    ("event_update", "order_update"),
    [
        ({"payload": {"action": "cancel"}}, {}),
        ({"payload": {"action": "reprice", "replaces_order_id": None}}, {}),
        (
            {"payload": {"action": "submit", "replaces_order_id": None}},
            {"replaces_order_id": "foreign-order"},
        ),
        ({"source": EventSource.BROKER_REST}, {}),
        ({"authority": EventAuthority.BROKER_AUTHORITATIVE}, {}),
    ],
    ids=[
        "unknown-action-kind",
        "reprice-without-predecessor",
        "submit-with-predecessor",
        "wrong-source",
        "wrong-authority",
    ],
)
def test_projection_rejects_noncanonical_action_identity_and_shape(
    event_update, order_update
):
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    order = Order(
        id="child-1",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    ).model_copy(update=order_update)
    action = _action_event(envelope, order).model_copy(update=event_update)

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
    )

    assert projected.retains_intent is True
    assert projected.invalid_order_ids == (order.id,)


@pytest.mark.parametrize(
    ("envelope_session", "child_session"),
    [(None, "session-1"), ("session-1", None)],
    ids=["unbound-envelope", "unbound-child"],
)
def test_projection_requires_exact_session_scope_even_when_one_side_is_unbound(
    envelope_session, child_session
):
    envelope = _terminal_envelope("owner-1", session_id=envelope_session)
    order = Order(
        id="child-1",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id=child_session,
    )
    action = _action_event(envelope, order)

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
    )

    assert projected.retains_intent is True
    assert projected.invalid_order_ids == (order.id,)


@pytest.mark.parametrize("corruption", ["missing-order-id", "conflicting-duplicate"])
async def test_public_claim_refuses_a_corrupt_action_lineage(any_store, corruption):
    _, _, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    corrupt = _action_event(envelope, staged.order)
    if corruption == "missing-order-id":
        corrupt = corrupt.model_copy(update={"order_id": None})
    else:
        corrupt = corrupt.model_copy(update={"price": 9.8})
    await any_store.append_execution_event(corrupt)

    claim = await any_store.claim_order_for_submission(staged.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "missing or malformed" in claim.reason
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CREATED


async def test_missing_parent_action_blocks_every_symbol_mint_choke_point(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    owner = SellIntent(
        id="orphan-action-owner",
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.EXPIRED,
        target_quantity=100,
        session_id=session.id,
        expired_at=NOW,
    )
    _raw_insert_intent(any_store, owner)
    missing_parent = _terminal_envelope(owner.id, session_id=session.id)
    child = Order(
        id="orphan-action-child",
        sell_intent_id=owner.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.SUBMITTED,
        broker_order_id="broker-orphan-action",
        session_id=session.id,
    )
    _raw_insert_order(any_store, child)
    _raw_append_execution(
        any_store,
        _action_event(
            missing_parent,
            child,
            envelope_id="missing-envelope-row",
            correlation_id=owner.id,
        ),
    )
    _raw_append_execution(
        any_store, _status_event(ExecutionEventType.SUBMITTED, child, missing_parent)
    )

    assert await any_store.active_sell_intent_for("AAPL") is None
    with pytest.raises(SellIntentTransitionError):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
    with pytest.raises(FlattenBlockedError):
        await any_store.flatten_position("AAPL", actor="operator-a")


async def test_mixed_valid_and_invalid_retained_lineages_never_choose_the_valid_one(
    any_store,
):
    session, _, _ = await _activate(any_store)
    malformed = _terminal_envelope("missing-owner", session_id=session.id)
    _raw_insert_envelope(any_store, malformed)
    _raw_seed_live_child(any_store, malformed, order_id="mixed-invalid-child")

    assert await any_store.active_sell_intent_for("AAPL") is None
    with pytest.raises(SellIntentTransitionError):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
    with pytest.raises(FlattenBlockedError):
        await any_store.flatten_position("AAPL", actor="operator-a")


async def test_two_retained_valid_owners_are_ambiguity_not_last_writer_wins(any_store):
    session, first, _ = await _activate(any_store)
    second = SellIntent(
        id="second-valid-owner",
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED,
        target_quantity=100,
        session_id=session.id,
        approved_at=NOW,
    )
    _raw_insert_intent(any_store, second)
    second_envelope = _terminal_envelope(second.id, session_id=session.id)
    _raw_insert_envelope(any_store, second_envelope)
    _raw_seed_live_child(any_store, second_envelope, order_id="second-owner-child")

    assert first.id != second.id
    assert await any_store.active_sell_intent_for("AAPL") is None
    with pytest.raises(FlattenBlockedError):
        await any_store.flatten_position("AAPL", actor="operator-a")
    with pytest.raises(SellIntentTransitionError):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )


async def test_ownerless_lineage_blocks_claim_redrive_dispatch_and_protection(
    any_store,
):
    await any_store.initialize()
    session = await _hold(any_store)
    ownerless = _draft("missing-owner", session_id=session.id).model_copy(
        update={
            "status": EnvelopeStatus.ACTIVE,
            "approved_at": NOW,
            "activated_at": NOW,
        }
    )
    _raw_insert_envelope(any_store, ownerless)
    child = Order(
        id="ownerless-created-child",
        sell_intent_id=ownerless.sell_intent_id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CREATED,
        session_id=session.id,
    )
    _raw_insert_order(any_store, child)
    _raw_append_execution(any_store, _action_event(ownerless, child))
    legacy = SellIntent(
        id="unlinked-legacy-approved",
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED,
        target_quantity=100,
        session_id=session.id,
        approved_at=NOW,
    )
    _raw_insert_intent(any_store, legacy)

    claim = await any_store.claim_order_for_submission(child.id)
    assert claim.outcome == CLAIM_BLOCKED
    assert (await any_store.get_order(child.id)).status is OrderStatus.CREATED
    claim_audits = await any_store.list_events(
        event_type="envelope_submission_claim_blocked"
    )
    assert len(claim_audits) == 1
    assert claim_audits[0].order_id == child.id
    assert claim_audits[0].correlation_id == ownerless.sell_intent_id

    with pytest.raises(SellIntentTransitionError):
        await any_store.create_order_for_sell_intent(
            legacy.id, order_type=OrderType.MARKET
        )
    with pytest.raises(SellIntentTransitionError):
        await any_store.open_protection_exit(
            symbol="AAPL",
            target_quantity=100,
            floor_price=9.0,
            observed_price=8.9,
            average_price=10.0,
            session_id=session.id,
        )
    sells = [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ]
    assert [order.id for order in sells] == [child.id]


async def test_local_terminal_after_claim_without_recovery_retains_owner(any_store):
    _, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await any_store.transition_order(claimed.order.id, OrderStatus.CANCELED)
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="hostile rail", now=NOW
    )

    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    assert (await any_store.active_sell_intent_for("AAPL")).id == intent.id


@pytest.mark.parametrize(
    "event_type",
    [
        ExecutionEventType.SUBMIT_PENDING,
        ExecutionEventType.SUBMIT_RELEASED,
        ExecutionEventType.SUBMITTED,
        ExecutionEventType.PARTIALLY_FILLED,
        ExecutionEventType.CANCEL_PENDING,
        ExecutionEventType.FILLED,
        ExecutionEventType.CANCELED,
        ExecutionEventType.REJECTED,
        ExecutionEventType.TIMEOUT_QUARANTINE,
    ],
)
def test_every_child_lifecycle_fact_is_scope_validated(event_type):
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    order = Order(
        id="child-1",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    )
    action = _action_event(envelope, order)
    wrong_scope = _status_event(event_type, order, envelope).model_copy(
        update={"symbol": "MSFT"}
    )

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
        order_events=[wrong_scope],
    )

    assert projected.retains_intent is True
    assert projected.invalid_order_ids == (order.id,)


@pytest.mark.parametrize(
    "event_update",
    [
        {"symbol": "MSFT"},
        {"side": OrderSide.BUY},
        {"session_id": "other-session"},
        {"correlation_id": "other-owner"},
        {"envelope_id": "other-envelope"},
        {"payload": {"claim_occurrence": "not-an-int"}},
    ],
    ids=["symbol", "side", "session", "owner", "envelope", "occurrence"],
)
def test_invalid_broker_terminal_scope_cannot_release_the_lineage(event_update):
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    order = Order(
        id="child-1",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    )
    action = _action_event(envelope, order)
    terminal = _status_event(ExecutionEventType.CANCELED, order, envelope).model_copy(
        update=event_update
    )

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
        order_events=[terminal],
    )

    assert projected.retains_intent is True
    assert projected.invalid_order_ids == (order.id,)


@pytest.mark.parametrize(
    "working_type",
    [ExecutionEventType.SUBMITTED, ExecutionEventType.PARTIALLY_FILLED],
)
def test_broker_working_interval_survives_a_later_local_cancel(working_type):
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    order = Order(
        id="child-1",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    )
    action = _action_event(envelope, order)
    broker_working = _status_event(
        working_type, order, envelope, sequence=1
    ).model_copy(update={"correlation_id": None, "envelope_id": None})
    local_cancel = _status_event(
        ExecutionEventType.CANCELED,
        order,
        envelope,
        authority=EventAuthority.LOCAL,
        source=EventSource.ENGINE,
        sequence=2,
    ).model_copy(update={"correlation_id": None, "envelope_id": None})

    retained = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
        order_events=[broker_working, local_cancel],
    )

    assert retained.invalid_order_ids == ()
    assert retained.retains_intent is True
    assert retained.uncertain_claim_order_ids == ()
    assert [venue.id for venue in retained.venue_orders] == [order.id]

    broker_cancel = _status_event(
        ExecutionEventType.CANCELED, order, envelope, sequence=3
    ).model_copy(update={"correlation_id": None, "envelope_id": None})
    released = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
        order_events=[broker_working, local_cancel, broker_cancel],
    )
    assert released.retains_intent is False
    assert released.venue_orders == ()


def test_old_recovery_resolution_cannot_clear_a_later_claim_occurrence():
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    order = Order(
        id="reclaimed-child",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    )
    action = _action_event(envelope, order)
    order_events = [
        _status_event(
            ExecutionEventType.SUBMIT_PENDING,
            order,
            envelope,
            authority=EventAuthority.LOCAL,
            source=EventSource.ENGINE,
            sequence=1,
        ),
        _status_event(
            ExecutionEventType.SUBMIT_RELEASED,
            order,
            envelope,
            authority=EventAuthority.LOCAL,
            source=EventSource.ENGINE,
            sequence=2,
        ),
        _status_event(
            ExecutionEventType.CANCELED,
            order,
            envelope,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            sequence=3,
        ),
        _status_event(
            ExecutionEventType.SUBMIT_PENDING,
            order,
            envelope,
            authority=EventAuthority.LOCAL,
            source=EventSource.ENGINE,
            sequence=4,
        ),
        _status_event(
            ExecutionEventType.CANCELED,
            order,
            envelope,
            authority=EventAuthority.LOCAL,
            source=EventSource.ENGINE,
            sequence=5,
        ),
    ]

    projected = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
        order_events=order_events,
    )

    assert projected.retains_intent is True
    assert projected.uncertain_claim_order_ids == (order.id,)
    assert [venue.id for venue in projected.venue_orders] == [order.id]


def test_late_old_recovery_resolution_cannot_close_a_new_claim_occurrence():
    envelope = _terminal_envelope("owner-1", session_id="session-1")
    order = Order(
        id="reclaimed-child",
        sell_intent_id="owner-1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
    )
    action = _action_event(envelope, order)
    pending_0 = _status_event(
        ExecutionEventType.SUBMIT_PENDING,
        order,
        envelope,
        authority=EventAuthority.LOCAL,
        source=EventSource.ENGINE,
        sequence=1,
    ).model_copy(update={"dedupe_key": f"submit_pending:{order.id}:0"})
    release_0 = _status_event(
        ExecutionEventType.SUBMIT_RELEASED,
        order,
        envelope,
        authority=EventAuthority.LOCAL,
        source=EventSource.ENGINE,
        sequence=2,
    ).model_copy(update={"dedupe_key": f"release:{order.id}:0"})
    pending_1 = _status_event(
        ExecutionEventType.SUBMIT_PENDING,
        order,
        envelope,
        authority=EventAuthority.LOCAL,
        source=EventSource.ENGINE,
        sequence=3,
    ).model_copy(update={"dedupe_key": f"submit_pending:{order.id}:1"})
    local_cancel = _status_event(
        ExecutionEventType.CANCELED,
        order,
        envelope,
        authority=EventAuthority.LOCAL,
        source=EventSource.ENGINE,
        sequence=4,
    )

    def resolved_record(record_id: str) -> SubmitRecoveryRecord:
        return SubmitRecoveryRecord(
            id=record_id,
            local_order_id=order.id,
            broker_order_id=f"broker-{record_id}",
            client_order_id=f"client-{record_id}",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason="resolved by broker cancel",
            cleanup_status=RECOVERY_RESOLVED,
            session_id=order.session_id,
            created_at=NOW,
        )

    late_old_resolution = recovery_resolution_execution_event(
        resolved_record("recovery-0"), now=NOW, claim_occurrence=0
    ).model_copy(update={"sequence": 5})
    assert late_old_resolution.payload["claim_occurrence"] == 0

    retained = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
        order_events=[
            pending_0,
            release_0,
            pending_1,
            local_cancel,
            late_old_resolution,
        ],
    )
    assert retained.retains_intent is True
    assert retained.uncertain_claim_order_ids == (order.id,)
    assert [venue.id for venue in retained.venue_orders] == [order.id]

    matching_resolution = recovery_resolution_execution_event(
        resolved_record("recovery-1"), now=NOW, claim_occurrence=1
    ).model_copy(update={"sequence": 6})
    released = project_envelope_obligation(
        envelopes=[envelope],
        action_events=[action],
        orders_by_id={order.id: order},
        order_events=[
            pending_0,
            release_0,
            pending_1,
            local_cancel,
            late_old_resolution,
            matching_resolution,
        ],
    )
    assert released.retains_intent is False
    assert released.uncertain_claim_order_ids == ()
    assert released.venue_orders == ()


async def test_open_recovery_retains_and_broker_resolution_releases_owner(any_store):
    session, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await any_store.transition_order(claimed.order.id, OrderStatus.CANCELED)
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="hostile rail", now=NOW
    )
    recovery = await any_store.create_submit_recovery(
        local_order_id=claimed.order.id,
        broker_order_id="broker-hostile-recovery",
        client_order_id="client-hostile-recovery",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="broker accepted before local terminal",
        session_id=session.id,
        cleanup_status=RECOVERY_UNRESOLVED,
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED

    await any_store.update_submit_recovery(
        recovery.id, cleanup_status=RECOVERY_RESOLVED
    )

    owner = await any_store.get_sell_intent(intent.id)
    assert owner.status is SellIntentStatus.EXPIRED
    assert await any_store.active_sell_intent_for("AAPL") is None
    releases = await any_store.list_events(
        event_type="sell_intent_transition", correlation_id=intent.id
    )
    assert [
        event.payload.get("reason")
        for event in releases
        if event.payload.get("to") == SellIntentStatus.EXPIRED.value
    ] == ["envelope_delegation_released"]


@pytest.mark.parametrize(
    "stale_status", [SellIntentStatus.PENDING, SellIntentStatus.EXPIRED]
)
async def test_startup_restores_every_stale_retained_owner_state(
    any_store, stale_status
):
    _, intent, _ = await _activate(any_store)
    _raw_force_owner_status(any_store, intent.id, stale_status)

    await any_store.initialize()

    owner = await any_store.get_sell_intent(intent.id)
    assert owner.status is SellIntentStatus.APPROVED
    assert owner.approved_at is not None
    assert owner.expired_at is None
    assert (await any_store.active_sell_intent_for("AAPL")).id == intent.id


async def test_stage_refuses_a_locally_terminal_but_claim_uncertain_child(any_store):
    _, _, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await any_store.transition_order(claimed.order.id, OrderStatus.CANCELED)

    with pytest.raises(EnvelopeActionPausedError):
        await any_store.stage_envelope_action(
            envelope.id,
            _action(price=9.8),
            snapshot_fingerprint=f"{FP}:second",
            now=NOW + timedelta(seconds=1),
        )

    sells = [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ]
    assert [order.id for order in sells] == [staged.order.id]


async def test_broker_fact_uses_causal_time_and_emits_one_release_audit(any_store):
    _, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    child = await any_store.transition_order(
        claimed.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id="broker-causal",
    )
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.BREACHED,
        reason="hostile rail",
        now=NOW + timedelta(seconds=1),
    )

    stored = await any_store.append_execution_event(
        _status_event(
            ExecutionEventType.CANCELED,
            child,
            envelope,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            source=EventSource.BROKER_STREAM,
            ts_event=CAUSAL_TIME,
            ts_init=INGEST_TIME,
        ).model_copy(update={"dedupe_key": f"{FP}:causal-cancel"})
    )

    assert stored.ts_event == CAUSAL_TIME
    assert stored.ts_init == INGEST_TIME
    owner = await any_store.get_sell_intent(intent.id)
    assert owner.status is SellIntentStatus.EXPIRED
    assert owner.expired_at == CAUSAL_TIME
    audits = await any_store.list_events(
        event_type="sell_intent_transition", correlation_id=intent.id
    )
    release_audits = [
        event
        for event in audits
        if event.payload
        == {
            "from": SellIntentStatus.APPROVED.value,
            "to": SellIntentStatus.EXPIRED.value,
            "reason": "envelope_delegation_released",
        }
    ]
    assert len(release_audits) == 1


async def test_stage_binds_immutable_envelope_session_and_rejects_override(any_store):
    session, _, envelope = await _activate(any_store)
    before_orders = await any_store.list_orders()
    before_actions = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
    ]

    with pytest.raises(EnvelopeActionPausedError, match="immutable envelope session"):
        await any_store.stage_envelope_action(
            envelope.id,
            _action(),
            snapshot_fingerprint=f"{FP}:wrong-session",
            session_id="foreign-session",
            now=NOW,
        )

    assert await any_store.list_orders() == before_orders
    assert [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
    ] == before_actions

    staged = await _stage(any_store, envelope.id)
    assert staged.order is not None
    assert staged.order.session_id == envelope.session_id == session.id


async def test_stage_default_survives_date_rollover_without_scope_corruption(any_store):
    session, _, envelope = await _activate(any_store)
    if hasattr(any_store, "_sessions"):
        for record in any_store._sessions:
            record.session_date = "2000-01-01"
    else:
        any_store._conn.execute("UPDATE sessions SET session_date = '2000-01-01'")
        any_store._conn.commit()

    staged = await _stage(any_store, envelope.id)
    current = await any_store.get_current_session()

    assert current.id != session.id
    assert staged.order is not None
    assert staged.order.session_id == envelope.session_id == session.id
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.outcome == CLAIM_CLAIMED


async def test_direct_recovery_blocks_mint_and_final_envelope_claim(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    old_owner = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(old_owner.id, SellIntentStatus.APPROVED)
    old_order = await any_store.create_order_for_sell_intent(
        old_owner.id, order_type=OrderType.MARKET
    )
    old_claim = await any_store.claim_order_for_submission(old_order.id)
    assert old_claim.order is not None
    await any_store.transition_order(old_order.id, OrderStatus.CANCELED)

    # The network-await claim itself is possibly live even before a recovery
    # record can be written.
    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )

    await any_store.create_submit_recovery(
        local_order_id=old_order.id,
        broker_order_id="broker-direct-recovery",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="accepted before local cancellation",
        session_id=session.id,
        cleanup_status=RECOVERY_UNRESOLVED,
    )

    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )

    # Bypass every earlier public guard to prove the final claim choke still
    # refuses a second possibly-live SELL.
    new_owner = SellIntent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED,
        target_quantity=100,
        session_id=session.id,
        approved_at=NOW,
    )
    envelope = _draft(new_owner.id, session_id=session.id).model_copy(
        update={
            "status": EnvelopeStatus.ACTIVE,
            "approved_at": NOW,
            "activated_at": NOW,
        }
    )
    child = Order(
        sell_intent_id=new_owner.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        session_id=session.id,
    )
    _raw_insert_intent(any_store, new_owner)
    _raw_insert_envelope(any_store, envelope)
    _raw_insert_order(any_store, child)
    _raw_append_execution(any_store, _action_event(envelope, child))

    blocked = await any_store.claim_order_for_submission(child.id)
    assert blocked.outcome == CLAIM_BLOCKED
    assert "direct SELL exposure" in (blocked.reason or "")


async def test_open_recovery_blocks_reclaim_of_same_direct_order(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    owner = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(owner.id, SellIntentStatus.APPROVED)
    order = await any_store.create_order_for_sell_intent(
        owner.id, order_type=OrderType.MARKET
    )
    first = await any_store.claim_order_for_submission(order.id)
    assert first.outcome == CLAIM_CLAIMED
    await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id="broker-direct-reclaim",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="broker accepted before local persistence",
        session_id=session.id,
    )
    await any_store.transition_order(order.id, OrderStatus.CREATED)

    second = await any_store.claim_order_for_submission(order.id)

    assert second.outcome == CLAIM_BLOCKED
    assert second.reason == "order has unresolved broker-submit recovery"
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED


async def test_orphan_sell_recovery_blocks_every_symbol_mint_choke(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    await any_store.create_submit_recovery(
        local_order_id="missing-local-order",
        broker_order_id="broker-orphan-recovery",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="local row was lost",
        session_id=session.id,
    )

    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
    with pytest.raises(FlattenBlockedError, match="cannot be safely deduplicated"):
        await any_store.flatten_position("AAPL", session_id=session.id)

    owner = SellIntent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED,
        target_quantity=100,
        session_id=session.id,
        approved_at=NOW,
    )
    envelope = _draft(owner.id, session_id=session.id).model_copy(
        update={
            "status": EnvelopeStatus.ACTIVE,
            "approved_at": NOW,
            "activated_at": NOW,
        }
    )
    _raw_insert_intent(any_store, owner)
    _raw_insert_envelope(any_store, envelope)
    with pytest.raises(EnvelopeActionPausedError, match="direct SELL exposure"):
        await _stage(any_store, envelope.id)

    child = Order(
        sell_intent_id=owner.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        session_id=session.id,
    )
    _raw_insert_order(any_store, child)
    _raw_append_execution(any_store, _action_event(envelope, child))
    claim = await any_store.claim_order_for_submission(child.id)
    assert claim.outcome == CLAIM_BLOCKED
    assert "missing-local-order" in (claim.reason or "")


async def test_orphan_recovery_blocks_preexisting_direct_dispatch(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    await any_store.create_submit_recovery(
        local_order_id="missing-prior-direct-order",
        broker_order_id="broker-prior-direct-order",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="local direct order row was lost",
        session_id=session.id,
    )
    owner = SellIntent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED,
        target_quantity=100,
        session_id=session.id,
        approved_at=NOW,
    )
    _raw_insert_intent(any_store, owner)
    before_owner = (await any_store.get_sell_intent(owner.id)).model_copy(deep=True)
    before_orders = [
        order.model_copy(deep=True) for order in await any_store.list_orders()
    ]

    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_order_for_sell_intent(
            owner.id, order_type=OrderType.MARKET
        )

    assert await any_store.get_sell_intent(owner.id) == before_owner
    assert await any_store.list_orders() == before_orders


async def test_misscoped_child_recovery_retains_both_symbol_obligations(any_store):
    session, intent, envelope = await _activate(any_store)
    await _hold(any_store, symbol="MSFT")
    staged = await _stage(any_store, envelope.id)
    assert staged.order is not None
    await any_store.transition_order(staged.order.id, OrderStatus.CANCELED)

    # The local order/action lineage is a structurally valid AAPL Envelope
    # child, but the persisted recovery falsely scopes the same possibly-live
    # venue order to MSFT.  Neither side of that ambiguity may disappear.
    await any_store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id="broker-misscoped-child",
        symbol="MSFT",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=staged.order.limit_price,
        failure_reason="recovery symbol disagrees with child lineage",
        session_id=session.id,
    )
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.BREACHED,
        reason="hostile misscoped recovery",
        now=NOW,
    )

    aapl_owner = await any_store.get_sell_intent(intent.id)
    assert aapl_owner.status is SellIntentStatus.APPROVED
    assert (await any_store.active_sell_intent_for("AAPL")).id == intent.id
    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="MSFT",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
    assert await any_store.active_sell_intent_for("MSFT") is None


async def test_wrong_symbol_terminal_cannot_erase_recovery_resolution_truth(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    recovery = await any_store.create_submit_recovery(
        local_order_id="missing-aapl-recovery-order",
        broker_order_id="broker-aapl-recovery-order",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="local AAPL order row was lost",
        session_id=session.id,
    )
    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )

    # Same recovery/order/broker identity and otherwise exact scope, except for
    # the symbol.  That corrupt terminal must remain audit truth, but it cannot
    # suppress the correctly scoped AAPL resolution event.
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=f"{FP}:wrong-symbol-terminal:{recovery.id}",
            ts_event=NOW,
            symbol="MSFT",
            side=OrderSide.SELL,
            quantity=100,
            order_id=recovery.local_order_id,
            session_id=session.id,
            payload={
                "broker_order_id": recovery.broker_order_id,
                "recovery_id": recovery.id,
                "cleanup_status": RECOVERY_RESOLVED,
            },
        )
    )
    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )

    resolved = await any_store.update_submit_recovery(
        recovery.id, cleanup_status=RECOVERY_RESOLVED
    )
    facts = [
        event
        for event in await any_store.get_execution_events()
        if event.payload.get("recovery_id") == recovery.id
    ]
    matching = [
        event
        for event in facts
        if recovery_terminal_fact_matches(
            resolved,
            event,
            claim_occurrence=None,
        )
    ]

    assert {event.symbol for event in facts} == {"AAPL", "MSFT"}
    assert len(matching) == 1
    assert matching[0].symbol == "AAPL"
    assert matching[0].order_id == recovery.local_order_id
    assert matching[0].event_type is ExecutionEventType.CANCELED
    replacement = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    assert replacement.status is SellIntentStatus.PENDING


async def test_flatten_cannot_bypass_terminal_direct_order_open_claim(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    owner = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(owner.id, SellIntentStatus.APPROVED)
    first_order = await any_store.create_order_for_sell_intent(
        owner.id, order_type=OrderType.MARKET
    )
    assert (
        await any_store.claim_order_for_submission(first_order.id)
    ).outcome == CLAIM_CLAIMED
    await any_store.transition_order(first_order.id, OrderStatus.CANCELED)

    with pytest.raises(FlattenBlockedError, match="cannot be safely deduplicated"):
        await any_store.flatten_position("AAPL", session_id=session.id)

    sells = [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ]
    assert [order.id for order in sells] == [first_order.id]


async def test_orphan_recovery_blocks_direct_order_final_claim(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    await any_store.create_submit_recovery(
        local_order_id="lost-direct-order",
        broker_order_id="broker-lost-direct",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="local row missing",
        session_id=session.id,
    )
    owner = SellIntent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.ORDERED,
        target_quantity=100,
        session_id=session.id,
        ordered_at=NOW,
    )
    order = Order(
        sell_intent_id=owner.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=100,
        session_id=session.id,
    )
    owner.order_id = order.id
    _raw_insert_intent(any_store, owner)
    _raw_insert_order(any_store, order)

    claim = await any_store.claim_order_for_submission(order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert "lost-direct-order" in (claim.reason or "")


async def test_cross_symbol_action_cannot_hide_direct_sell_from_flatten(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    foreign_owner = SellIntent(
        symbol="MSFT",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED,
        target_quantity=100,
        session_id=session.id,
        approved_at=NOW,
    )
    foreign_envelope = _draft(
        foreign_owner.id, symbol="MSFT", session_id=session.id
    ).model_copy(
        update={
            "status": EnvelopeStatus.ACTIVE,
            "approved_at": NOW,
            "activated_at": NOW,
        }
    )
    live_aapl = Order(
        sell_intent_id=foreign_owner.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.SUBMITTED,
        broker_order_id="broker-cross-symbol",
        session_id=session.id,
        submitted_at=NOW,
    )
    _raw_insert_intent(any_store, foreign_owner)
    _raw_insert_envelope(any_store, foreign_envelope)
    _raw_insert_order(any_store, live_aapl)
    malformed_action = _action_event(foreign_envelope, live_aapl).model_copy(
        update={"symbol": "MSFT"}
    )
    _raw_append_execution(any_store, malformed_action)
    _raw_append_execution(
        any_store,
        ExecutionEvent(
            event_type=ExecutionEventType.SUBMITTED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            symbol="AAPL",
            side=OrderSide.SELL,
            order_id=live_aapl.id,
            session_id=session.id,
        ),
    )

    with pytest.raises(FlattenBlockedError):
        await any_store.flatten_position("AAPL", session_id=session.id)

    sells = [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ]
    assert [order.id for order in sells] == [live_aapl.id]


async def test_malformed_foreign_envelope_cannot_restore_unrelated_owner(any_store):
    session, intent, envelope = await _activate(any_store)
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="released", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED

    malformed = _draft(intent.id, symbol="MSFT", session_id=session.id).model_copy(
        update={
            "status": EnvelopeStatus.ACTIVE,
            "approved_at": NOW,
            "activated_at": NOW,
        }
    )
    _raw_insert_envelope(any_store, malformed)

    await any_store.initialize()

    owner = await any_store.get_sell_intent(intent.id)
    assert owner.status is SellIntentStatus.EXPIRED
    assert await any_store.active_sell_intent_for("AAPL") is None


async def test_submit_release_after_terminal_parent_cancels_child_atomically(any_store):
    _, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="during venue await", now=NOW
    )

    released = await any_store.transition_order(staged.order.id, OrderStatus.CREATED)

    assert released.status is OrderStatus.CANCELED
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CANCELED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED


async def test_close_expires_only_unlinked_duplicate_not_retained_owner(any_store):
    session, owner, _ = await _activate(any_store)
    duplicate = SellIntent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.PENDING,
        target_quantity=100,
        session_id=session.id,
    )
    _raw_insert_intent(any_store, duplicate)

    await any_store.close_session(session.id)

    assert (
        await any_store.get_sell_intent(owner.id)
    ).status is SellIntentStatus.APPROVED
    assert (
        await any_store.get_sell_intent(duplicate.id)
    ).status is SellIntentStatus.EXPIRED


async def test_order_noop_reconciles_owner_with_fresh_timestamp(any_store):
    _, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    submitted = await any_store.transition_order(
        staged.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id="broker-noop",
    )
    _raw_force_owner_status(any_store, intent.id, SellIntentStatus.EXPIRED)
    stale_updated_at = (await any_store.get_sell_intent(intent.id)).updated_at

    same = await any_store.transition_order(submitted.id, OrderStatus.SUBMITTED)

    owner = await any_store.get_sell_intent(intent.id)
    assert same.status is OrderStatus.SUBMITTED
    assert owner.status is SellIntentStatus.APPROVED
    assert owner.updated_at >= stale_updated_at


async def test_recovery_rejection_remains_rejected_event_truth(any_store):
    session, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await any_store.transition_order(staged.order.id, OrderStatus.CANCELED)
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="recovery", now=NOW
    )
    recovery = await any_store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id="broker-rejected-recovery",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="accepted upstream",
        session_id=session.id,
    )

    await _record_recovery_terminal_fact(any_store, recovery, OrderStatus.REJECTED)
    await any_store.update_submit_recovery(
        recovery.id, cleanup_status=RECOVERY_RESOLVED
    )

    facts = [
        event
        for event in await any_store.get_execution_events()
        if event.payload.get("recovery_id") == recovery.id
        and event.event_type
        in (ExecutionEventType.CANCELED, ExecutionEventType.REJECTED)
    ]
    assert [event.event_type for event in facts] == [ExecutionEventType.REJECTED]
    assert facts[0].payload["claim_occurrence"] == 0
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED


async def test_recovery_resolution_dedupe_collision_rolls_back_ledger(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    recovery = await any_store.create_submit_recovery(
        local_order_id="missing-collision-order",
        broker_order_id="broker-collision-order",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="local order row was lost",
        session_id=session.id,
    )
    resolved_record = recovery.model_copy(update={"cleanup_status": RECOVERY_RESOLVED})
    poisoned = recovery_resolution_execution_event(
        resolved_record, now=NOW, claim_occurrence=None
    ).model_copy(update={"symbol": "MSFT"})
    await any_store.append_execution_event(poisoned)

    with pytest.raises(RecoveryTransitionError, match="identity conflicts"):
        await any_store.update_submit_recovery(
            recovery.id, cleanup_status=RECOVERY_RESOLVED
        )

    stored = {record.id: record for record in await any_store.list_submit_recoveries()}[
        recovery.id
    ]
    assert stored.cleanup_status == RECOVERY_UNRESOLVED
    assert not recovery_terminal_fact_matches(stored, poisoned, claim_occurrence=None)
    assert await any_store.list_events(event_type="submit_recovery_resolved") == []
    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )


async def test_born_resolved_recovery_collision_rolls_back_creation(
    any_store, monkeypatch
):
    await any_store.initialize()
    session = await _hold(any_store)
    fixed = UUID("d9f2cf2b-74c4-4ec5-9f8f-e3bbc75dc74b")
    recovery_id = fixed.hex
    await any_store.append_execution_event(
        ExecutionEvent(
            id="poison-born-resolved-event",
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=f"submit_recovery_resolved:{recovery_id}",
            symbol="MSFT",
            side=OrderSide.SELL,
            quantity=100,
            order_id="missing-born-resolved-order",
            session_id=session.id,
            payload={
                "broker_order_id": "broker-born-resolved",
                "recovery_id": recovery_id,
                "cleanup_status": RECOVERY_RESOLVED,
            },
        )
    )
    monkeypatch.setattr("app.models.uuid.uuid4", lambda: fixed)

    with pytest.raises(RecoveryTransitionError, match="identity conflicts"):
        await any_store.create_submit_recovery(
            local_order_id="missing-born-resolved-order",
            broker_order_id="broker-born-resolved",
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100,
            failure_reason="already terminal at first durable write",
            session_id=session.id,
            cleanup_status=RECOVERY_RESOLVED,
        )

    assert all(
        record.id != recovery_id for record in await any_store.list_submit_recoveries()
    )
    assert not any(
        event.payload.get("recovery_id") == recovery_id
        for event in await any_store.list_events(event_type="submit_recovery_recorded")
    )


async def test_later_audit_payload_cannot_retarget_recovery_claim_occurrence(any_store):
    session, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    first_claim = await any_store.claim_order_for_submission(staged.order.id)
    assert first_claim.outcome == CLAIM_CLAIMED
    recovery = await any_store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id="broker-old-claim-recovery",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="old claim accepted upstream",
        session_id=session.id,
    )
    await any_store.transition_order(staged.order.id, OrderStatus.CREATED)
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.SUBMIT_PENDING,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=f"submit_pending:{staged.order.id}:1",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_id=staged.order.id,
            session_id=session.id,
            payload={"claim_occurrence": 1},
        )
    )
    await any_store.append_event(
        "hostile_recovery_occurrence_override",
        symbol="AAPL",
        order_id=staged.order.id,
        session_id=session.id,
        payload={"recovery_id": recovery.id, "claim_occurrence": 1},
    )
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="terminal", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED

    await any_store.update_submit_recovery(
        recovery.id, cleanup_status=RECOVERY_RESOLVED
    )

    owner = await any_store.get_sell_intent(intent.id)
    assert owner.status is SellIntentStatus.APPROVED
    matching = [
        event
        for event in await any_store.get_execution_events()
        if event.payload.get("recovery_id") == recovery.id
        and recovery_terminal_fact_matches(
            recovery.model_copy(update={"cleanup_status": RECOVERY_RESOLVED}),
            event,
            claim_occurrence=0,
        )
    ]
    assert len(matching) == 1


@pytest.mark.parametrize("identity_source", ["correlation", "referenced-order"])
async def test_late_orphan_action_reconciles_valid_owner_by_every_identity(
    any_store, identity_source
):
    session, intent, envelope = await _activate(any_store)
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="released", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
    child = Order(
        id=f"late-orphan-{identity_source}",
        candidate_id=(
            "legacy-correlation-origin" if identity_source == "correlation" else None
        ),
        sell_intent_id=(intent.id if identity_source == "referenced-order" else None),
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id=session.id,
    )
    _raw_insert_order(any_store, child)
    action = _action_event(
        envelope,
        child,
        envelope_id=f"missing-parent-{identity_source}",
        correlation_id=intent.id,
    )
    if identity_source == "referenced-order":
        action = action.model_copy(update={"correlation_id": None})

    await any_store.append_execution_event(action)

    owner = await any_store.get_sell_intent(intent.id)
    assert owner.status is SellIntentStatus.APPROVED


async def test_needs_review_retains_owner_on_terminal_and_dedups_replacement(any_store):
    # AMENDED under the operator-ratified P2 spec change (2026-07-17,
    # RATIFICATION-partb-completion.md D2 — the cross-investigator oracle's
    # needs-review property). This pin originally asserted the OPPOSITE
    # (release on terminal + a fresh replacement intent): under P2, an open
    # needs_review child is unresolved venue exposure, so the terminal envelope
    # RETAINS its owner, and "creating a replacement" idempotently returns the
    # retained owner (single-mandate identity). The full quarantine posture is
    # pinned in tests/test_wo0036_r2_close_and_recovery_ownership.py.
    session, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await any_store.transition_order(staged.order.id, OrderStatus.CANCELED)

    await any_store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id="broker-envelope-needs-review",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="operator escalation",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED

    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="delegation ended", now=NOW
    )

    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    replacement = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    assert replacement.id == intent.id


async def test_recovery_audit_payload_cannot_override_reserved_identity(any_store):
    await any_store.initialize()
    session = await _hold(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    order = await any_store.create_order_for_sell_intent(
        intent.id, order_type=OrderType.MARKET
    )
    claimed = await any_store.claim_order_for_submission(order.id)
    assert claimed.outcome == CLAIM_CLAIMED
    poison = {
        "broker_order_id": "poison-broker",
        "recovery_id": "poison-recovery",
        "failure_reason": "poison-reason",
        "cleanup_status": "poison-status",
        "claim_occurrence": 999,
        "custom": "preserved",
    }
    claimed_recovery = await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id="broker-canonical",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="canonical-reason",
        session_id=session.id,
        extra_payload=poison,
    )
    unclaimed_recovery = await any_store.create_submit_recovery(
        local_order_id="missing-unclaimed-order",
        broker_order_id="broker-unclaimed",
        symbol="MSFT",
        side=OrderSide.SELL,
        quantity=10,
        failure_reason="unclaimed-reason",
        session_id=session.id,
        extra_payload=poison,
    )
    audit_by_recovery = {
        event.payload.get("recovery_id"): event
        for event in await any_store.list_events(event_type="submit_recovery_recorded")
    }

    claimed_payload = audit_by_recovery[claimed_recovery.id].payload
    assert claimed_payload == {
        "broker_order_id": "broker-canonical",
        "recovery_id": claimed_recovery.id,
        "failure_reason": "canonical-reason",
        "cleanup_status": RECOVERY_UNRESOLVED,
        "claim_occurrence": 0,
        "custom": "preserved",
    }
    unclaimed_payload = audit_by_recovery[unclaimed_recovery.id].payload
    assert unclaimed_payload == {
        "broker_order_id": "broker-unclaimed",
        "recovery_id": unclaimed_recovery.id,
        "failure_reason": "unclaimed-reason",
        "cleanup_status": RECOVERY_UNRESOLVED,
        "custom": "preserved",
    }


async def test_reprice_cannot_claim_a_needs_review_direct_order_as_predecessor(
    any_store,
):
    await any_store.initialize()
    session = await _hold(any_store)
    legacy_owner = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(legacy_owner.id, SellIntentStatus.APPROVED)
    direct = await any_store.create_order_for_sell_intent(
        legacy_owner.id, order_type=OrderType.LIMIT, limit_price=9.9
    )
    first_claim = await any_store.claim_order_for_submission(direct.id)
    assert first_claim.outcome == CLAIM_CLAIMED
    await any_store.transition_order(
        direct.id, OrderStatus.SUBMITTED, broker_order_id="broker-direct-predecessor"
    )
    await any_store.create_submit_recovery(
        local_order_id=direct.id,
        broker_order_id="broker-direct-predecessor",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="operator owns stranded direct order",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )

    # AMENDED under WO-0108 / REV-0029 P0-3 (Policy A): the public creation
    # path now correctly REFUSES a fresh owner beside the needs_review
    # exposure, so this hostile shape is constructed raw (the suite's
    # legacy/corrupt-shape idiom) — the property under test is the CLAIM
    # choke, which must block regardless of how the shape came to exist.
    owner = SellIntent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED,
        target_quantity=100,
        session_id=session.id,
    )
    _raw_insert_intent(any_store, owner)
    envelope = _draft(owner.id, session_id=session.id).model_copy(
        update={
            "status": EnvelopeStatus.ACTIVE,
            "approved_at": NOW,
            "activated_at": NOW,
        }
    )
    _raw_insert_envelope(any_store, envelope)
    replacement = Order(
        id="hostile-cross-lineage-reprice",
        sell_intent_id=owner.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.8,
        replaces_order_id=direct.id,
        session_id=session.id,
    )
    _raw_insert_order(any_store, replacement)
    action = _action_event(envelope, replacement).model_copy(
        update={
            "price": 9.8,
            "payload": {
                "action": "reprice",
                "replaces_order_id": direct.id,
                "snapshot_fingerprint": FP,
            },
        }
    )
    await any_store.append_execution_event(action)

    claim = await any_store.claim_order_for_submission(replacement.id)

    assert claim.outcome == CLAIM_BLOCKED
    # Any of the fail-closed rails may fire first (the WO-0108 needs_review /
    # direct-exposure rails precede the lineage-shape check) — blocked is the
    # property; the reason names whichever rail caught it.
    assert claim.reason is not None and (
        "missing or malformed" in claim.reason
        or "needs_review" in claim.reason
        or "direct SELL exposure" in claim.reason
    )
    assert (await any_store.get_order(replacement.id)).status is OrderStatus.CREATED


async def test_second_submit_child_cannot_claim_while_first_child_is_venue_live(
    any_store,
):
    session, owner, envelope = await _activate(any_store)
    first = _raw_seed_live_child(
        any_store, envelope, order_id="hostile-first-live-child"
    )
    second = Order(
        id="hostile-second-submit-child",
        sell_intent_id=owner.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.8,
        session_id=session.id,
    )
    _raw_insert_order(any_store, second)
    await any_store.append_execution_event(
        _action_event(envelope, second).model_copy(
            update={
                "price": 9.8,
                "payload": {
                    "action": "submit",
                    "replaces_order_id": None,
                    "snapshot_fingerprint": FP,
                },
            }
        )
    )

    claim = await any_store.claim_order_for_submission(second.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and first.id in claim.reason
    assert (await any_store.get_order(second.id)).status is OrderStatus.CREATED


@pytest.mark.parametrize(
    "occurrences",
    [(0, 0), (1,)],
    ids=["duplicate", "gap"],
)
async def test_duplicate_or_gapped_claim_occurrence_fails_closed_at_public_claim(
    any_store, occurrences
):
    _, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    for index, occurrence in enumerate(occurrences):
        await any_store.append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.SUBMIT_PENDING,
                source=EventSource.ENGINE,
                authority=EventAuthority.LOCAL,
                dedupe_key=(
                    f"hostile-claim-occurrence:{staged.order.id}:{occurrence}:{index}"
                ),
                ts_event=NOW + timedelta(seconds=index),
                symbol=staged.order.symbol,
                side=OrderSide.SELL,
                quantity=staged.order.quantity,
                price=staged.order.limit_price,
                order_id=staged.order.id,
                envelope_id=envelope.id,
                session_id=staged.order.session_id,
                correlation_id=intent.id,
                payload={"claim_occurrence": occurrence},
            )
        )

    claim = await any_store.claim_order_for_submission(staged.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "missing or malformed" in claim.reason
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_orderless_action_immediately_restores_its_terminal_envelope_owner(
    any_store,
):
    session, intent, envelope = await _activate(any_store)
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="released", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED

    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.ENVELOPE_ACTION,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            ts_event=NOW + timedelta(seconds=1),
            symbol=envelope.symbol,
            side=OrderSide.SELL,
            quantity=envelope.qty_ceiling,
            price=9.9,
            order_id=None,
            envelope_id=envelope.id,
            session_id=session.id,
            correlation_id=intent.id,
            payload={"action": "submit", "snapshot_fingerprint": FP},
        )
    )

    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_terminal_cleanup_cannot_cancel_a_foreign_created_child(any_store):
    session, original_owner, terminal_parent = await _activate(any_store)
    await any_store.transition_envelope(
        terminal_parent.id,
        EnvelopeStatus.BREACHED,
        reason="release original mandate",
        now=NOW,
    )
    assert (
        await any_store.get_sell_intent(original_owner.id)
    ).status is SellIntentStatus.EXPIRED

    foreign_owner = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(foreign_owner.id, SellIntentStatus.APPROVED)
    foreign = await any_store.create_order_for_sell_intent(
        foreign_owner.id, order_type=OrderType.LIMIT, limit_price=9.9
    )
    claim = await any_store.claim_order_for_submission(foreign.id)
    assert claim.outcome == CLAIM_CLAIMED

    await any_store.append_execution_event(_action_event(terminal_parent, foreign))
    released = await any_store.transition_order(foreign.id, OrderStatus.CREATED)

    assert released.status is OrderStatus.CREATED
    assert (await any_store.get_order(foreign.id)).status is OrderStatus.CREATED


async def test_supersede_rejects_unresolved_direct_sell_with_store_parity(any_store):
    session, owner, envelope = await _activate(any_store)
    direct = Order(
        id="hostile-direct-supersede-sibling",
        sell_intent_id=owner.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CREATED,
        session_id=session.id,
    )
    _raw_insert_order(any_store, direct)
    successor = _draft(owner.id, session_id=session.id).model_copy(
        update={"floor_price": 9.1}
    )

    with pytest.raises(EnvelopeTransitionError, match="unresolved direct SELL"):
        await any_store.supersede_envelope(
            envelope.id,
            successor,
            actor="operator-a",
            reason="must not bypass direct sibling",
        )

    assert (await any_store.get_envelope(envelope.id)).status is EnvelopeStatus.ACTIVE
    assert await any_store.get_envelope(successor.id) is None


async def test_monitoring_fill_mapping_never_guesses_between_envelope_parents(
    any_store,
):
    session, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.outcome == CLAIM_CLAIMED
    submitted = await any_store.transition_order(
        staged.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id="broker-ambiguous-fill-parent",
    )

    second_parent = _terminal_envelope(intent.id, session_id=session.id)
    _raw_insert_envelope(any_store, second_parent)
    await any_store.append_execution_event(_action_event(second_parent, submitted))

    await _apply_update(
        any_store,
        submitted,
        BrokerOrderUpdate(
            OrderStatus.PARTIALLY_FILLED,
            10,
            [
                BrokerFill(
                    source_fill_id="ambiguous-parent-fill",
                    quantity=10,
                    price=9.9,
                    filled_at=NOW + timedelta(minutes=1),
                )
            ],
        ),
    )

    assert (
        sum(fill.quantity for fill in await any_store.list_fills(order_id=submitted.id))
        == 10
    )
    assert (await any_store.get_position("AAPL")).quantity == 90
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_envelope(second_parent.id)).remaining_quantity == 100
    fill_facts = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.FILL
        and event.order_id == submitted.id
        and event.dedupe_key == f"fill:{submitted.id}:ambiguous-parent-fill"
    ]
    assert len(fill_facts) == 1
    assert fill_facts[0].envelope_id is None
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_recovery_terminal_poison_does_not_abort_clean_sibling(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    poisoned = await any_store.create_submit_recovery(
        local_order_id="poisoned-recovery-order",
        broker_order_id="broker-poisoned-recovery",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=10,
        limit_price=9.9,
        failure_reason="poisoned terminal persistence",
        session_id=session.id,
    )
    clean = await any_store.create_submit_recovery(
        local_order_id="clean-recovery-order",
        broker_order_id="broker-clean-recovery",
        symbol="MSFT",
        side=OrderSide.SELL,
        quantity=20,
        limit_price=19.9,
        failure_reason="clean sibling must still converge",
        session_id=session.id,
    )
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=(
                f"submit_recovery_terminal:{poisoned.id}:{OrderStatus.CANCELED.value}"
            ),
            ts_event=NOW,
            symbol="WRONG",
            side=OrderSide.SELL,
            quantity=poisoned.quantity,
            order_id=poisoned.local_order_id,
            session_id=session.id,
            payload={
                "broker_order_id": poisoned.broker_order_id,
                "recovery_id": poisoned.id,
                "cleanup_status": RECOVERY_RESOLVED,
            },
        )
    )
    adapter = MockBrokerAdapter()
    adapter.set_response(
        poisoned.broker_order_id,
        BrokerOrderUpdate(OrderStatus.CANCELED, 0, []),
    )
    adapter.set_response(
        clean.broker_order_id,
        BrokerOrderUpdate(OrderStatus.CANCELED, 0, []),
    )

    await _recover_unpersisted_submits(any_store, adapter)

    records = {record.id: record for record in await any_store.list_submit_recoveries()}
    assert adapter.status_queries == [poisoned.broker_order_id, clean.broker_order_id]
    assert records[poisoned.id].cleanup_status == RECOVERY_UNRESOLVED
    assert records[clean.id].cleanup_status == RECOVERY_RESOLVED
    clean_facts = [
        event
        for event in await any_store.get_execution_events()
        if event.payload.get("recovery_id") == clean.id
        and recovery_terminal_fact_matches(
            records[clean.id], event, claim_occurrence=None
        )
    ]
    assert len(clean_facts) == 1


async def test_envelope_fill_rejects_foreign_session_without_mutation(any_store):
    session, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    before = await any_store.get_envelope(envelope.id)
    before_events = await any_store.get_execution_events()

    with pytest.raises(InvalidFillError, match="immutable envelope session"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=f"fill:{staged.order.id}:foreign-session",
            price=9.9,
            order_id=staged.order.id,
            session_id=f"foreign-{session.id}",
            ts_event=NOW + timedelta(minutes=1),
            now=NOW + timedelta(minutes=1),
        )

    after = await any_store.get_envelope(envelope.id)
    assert after == before
    assert await any_store.get_execution_events() == before_events
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CREATED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    assert (await any_store.get_position("AAPL")).quantity == 100


async def test_executor_persisted_reprice_overrides_caller_submit_kind(any_store):
    _, _, envelope = await _activate(any_store)
    adapter = MockBrokerAdapter()
    first = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _action(),
        snapshot_fingerprint=f"{FP}:executor-first",
        now=NOW,
    )
    assert first.outcome == ENVELOPE_EXEC_SUBMITTED
    predecessor = await any_store.get_order(first.order_id)
    assert predecessor is not None and predecessor.broker_order_id is not None
    staged = await any_store.stage_envelope_action(
        envelope.id,
        _action(kind=ActionKind.REPRICE, price=9.8),
        snapshot_fingerprint=f"{FP}:executor-reprice",
        now=NOW + timedelta(minutes=1),
    )
    assert staged.order is not None
    assert staged.order.replaces_order_id == predecessor.id

    result = await _drive_staged_order(
        any_store,
        adapter,
        order=staged.order,
        kind=ActionKind.SUBMIT,
        working_order=None,
        envelope_id=envelope.id,
        now=NOW + timedelta(minutes=1),
    )

    assert result.outcome == ENVELOPE_EXEC_REPRICED
    assert [order.id for order in adapter.submitted] == [predecessor.id]
    assert [call[0] for call in adapter.replaced] == [predecessor.broker_order_id]
    assert (await any_store.get_order(predecessor.id)).status is OrderStatus.CANCELED
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.SUBMITTED


async def test_executor_ignores_caller_working_order_for_persisted_predecessor(
    any_store,
):
    _, _, envelope = await _activate(any_store)
    adapter = MockBrokerAdapter()
    first = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _action(),
        snapshot_fingerprint=f"{FP}:working-first",
        now=NOW,
    )
    assert first.outcome == ENVELOPE_EXEC_SUBMITTED
    predecessor = await any_store.get_order(first.order_id)
    assert predecessor is not None and predecessor.broker_order_id is not None
    staged = await any_store.stage_envelope_action(
        envelope.id,
        _action(kind=ActionKind.REPRICE, price=9.8),
        snapshot_fingerprint=f"{FP}:working-reprice",
        now=NOW + timedelta(minutes=1),
    )
    assert staged.order is not None
    wrong_working = predecessor.model_copy(
        update={
            "id": "caller-supplied-wrong-predecessor",
            "broker_order_id": "broker-caller-supplied-wrong-predecessor",
        }
    )

    result = await _drive_staged_order(
        any_store,
        adapter,
        order=staged.order,
        kind=ActionKind.REPRICE,
        working_order=wrong_working,
        envelope_id=envelope.id,
        now=NOW + timedelta(minutes=1),
    )

    assert result.outcome == ENVELOPE_EXEC_REPRICED
    assert [call[0] for call in adapter.replaced] == [predecessor.broker_order_id]
    assert all(call[0] != wrong_working.broker_order_id for call in adapter.replaced)
    assert (await any_store.get_order(predecessor.id)).status is OrderStatus.CANCELED
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.SUBMITTED


async def test_executor_final_claim_blocks_stale_staged_action(any_store):
    _, _, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    adapter = MockBrokerAdapter()

    result = await _drive_staged_order(
        any_store,
        adapter,
        order=staged.order,
        kind=ActionKind.SUBMIT,
        working_order=None,
        envelope_id=envelope.id,
        now=NOW + timedelta(seconds=121),
    )

    assert result.outcome == ENVELOPE_EXEC_BLOCKED
    assert "staleness:" in result.detail
    assert "121s" in result.detail
    assert adapter.submitted == []
    assert adapter.replaced == []
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CREATED


async def test_final_claim_rechecks_remaining_after_predecessor_fill_race(any_store):
    _, _, envelope = await _activate(any_store)
    adapter = MockBrokerAdapter()
    first = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _action(),
        snapshot_fingerprint=f"{FP}:remaining-first",
        now=NOW,
    )
    assert first.outcome == ENVELOPE_EXEC_SUBMITTED
    predecessor = await any_store.get_order(first.order_id)
    assert predecessor is not None
    staged = await any_store.stage_envelope_action(
        envelope.id,
        _action(kind=ActionKind.REPRICE, price=9.8),
        snapshot_fingerprint=f"{FP}:remaining-reprice",
        now=NOW + timedelta(minutes=1),
    )
    assert staged.order is not None

    fill_time = NOW + timedelta(minutes=1, seconds=1)
    await _apply_update(
        any_store,
        predecessor,
        BrokerOrderUpdate(
            OrderStatus.PARTIALLY_FILLED,
            60,
            [
                BrokerFill(
                    source_fill_id="remaining-race",
                    quantity=60,
                    price=9.9,
                    filled_at=fill_time,
                )
            ],
        ),
    )
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 40
    assert (await any_store.get_position("AAPL")).quantity == 40

    claim = await any_store.claim_order_for_submission(staged.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "size 100 outside (0, 40]" in claim.reason
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CREATED


async def test_final_claim_rechecks_envelope_expiry_after_staging(
    any_store, monkeypatch
):
    await any_store.initialize()
    session = await _hold(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await any_store.approve_envelope_activation(
        _draft(intent.id, session_id=session.id).model_copy(
            update={"expires_at": NOW + timedelta(seconds=60)}
        ),
        actor="operator-a",
    )
    staged = await _stage(any_store, envelope.id)

    monkeypatch.setattr("app.store.memory.utcnow", lambda: envelope.expires_at)
    monkeypatch.setattr("app.store.sqlite.utcnow", lambda: envelope.expires_at)
    claim = await any_store.claim_order_for_submission(staged.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "ttl:" in claim.reason
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CREATED


async def test_final_claim_rechecks_session_phase_after_staging(any_store, monkeypatch):
    phase_start = datetime(2026, 7, 14, 19, 59, 30, tzinfo=timezone.utc)
    await any_store.initialize()
    session = await _hold(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await any_store.approve_envelope_activation(
        _draft(intent.id, session_id=session.id).model_copy(
            update={"expires_at": NOW + timedelta(hours=8)}
        ),
        actor="operator-a",
    )
    staged = await any_store.stage_envelope_action(
        envelope.id,
        _action(),
        snapshot_fingerprint=FP,
        now=phase_start,
    )

    after_close = phase_start + timedelta(seconds=31)
    monkeypatch.setattr("app.store.memory.utcnow", lambda: after_close)
    monkeypatch.setattr("app.store.sqlite.utcnow", lambda: after_close)
    claim = await any_store.claim_order_for_submission(staged.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "session_phase:" in claim.reason
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CREATED


async def test_final_claim_rechecks_reduce_only_after_unrelated_fill(any_store):
    session, _, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    external_exit = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.SELL,
        60,
        session_id=session.id,
    )
    await any_store.append_fill(
        external_exit.id,
        "AAPL",
        OrderSide.SELL,
        60,
        9.9,
        source_fill_id=f"{FP}:unrelated-position-shrink",
        session_id=session.id,
    )
    assert (await any_store.get_position("AAPL")).quantity == 40

    claim = await any_store.claim_order_for_submission(staged.order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None and "reduce_only:" in claim.reason
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CREATED


@pytest.mark.parametrize("release_kind", ["fake-broker", "valid-local"])
async def test_submit_release_provenance_controls_envelope_release(
    any_store, release_kind
):
    _, intent, envelope = await _activate(any_store)
    staged = await _stage(any_store, envelope.id)
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.outcome == CLAIM_CLAIMED
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="release provenance", now=NOW
    )

    if release_kind == "fake-broker":
        await any_store.append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.SUBMIT_RELEASED,
                source=EventSource.BROKER_REST,
                authority=EventAuthority.BROKER_AUTHORITATIVE,
                dedupe_key=f"{FP}:fake-broker-release:{staged.order.id}",
                ts_event=NOW + timedelta(seconds=1),
                symbol=staged.order.symbol,
                side=OrderSide.SELL,
                quantity=staged.order.quantity,
                price=staged.order.limit_price,
                order_id=staged.order.id,
                envelope_id=envelope.id,
                session_id=staged.order.session_id,
                correlation_id=intent.id,
                payload={"claim_occurrence": 0},
            )
        )
    else:
        released = await any_store.transition_order(
            staged.order.id, OrderStatus.CREATED
        )
        assert released.status is OrderStatus.CANCELED

    events = await any_store.get_execution_events()
    current_envelope = await any_store.get_envelope(envelope.id)
    current_order = await any_store.get_order(staged.order.id)
    projected = project_envelope_obligation(
        envelopes=[current_envelope],
        action_events=[
            event
            for event in events
            if event.event_type is ExecutionEventType.ENVELOPE_ACTION
            and event.envelope_id == envelope.id
        ],
        orders_by_id={current_order.id: current_order},
        order_events=[
            event
            for event in events
            if event.order_id == current_order.id
            and event.event_type is not ExecutionEventType.ENVELOPE_ACTION
        ],
    )

    if release_kind == "fake-broker":
        assert projected.invalid_order_ids == (staged.order.id,)
        assert projected.retains_intent is True
        assert (
            await any_store.get_sell_intent(intent.id)
        ).status is SellIntentStatus.APPROVED
    else:
        assert projected.invalid_order_ids == ()
        assert projected.retains_intent is False
        assert (
            await any_store.get_sell_intent(intent.id)
        ).status is SellIntentStatus.EXPIRED


@pytest.mark.parametrize("release_kind", ["fake-broker", "valid-local"])
async def test_submit_release_provenance_controls_direct_sell_exposure(
    any_store, release_kind
):
    await any_store.initialize()
    session = await _hold(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    order = await any_store.create_order_for_sell_intent(
        intent.id, order_type=OrderType.LIMIT, limit_price=9.9
    )
    claimed = await any_store.claim_order_for_submission(order.id)
    assert claimed.outcome == CLAIM_CLAIMED

    if release_kind == "fake-broker":
        await any_store.transition_order(order.id, OrderStatus.CANCELED)
        await any_store.append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.SUBMIT_RELEASED,
                source=EventSource.BROKER_REST,
                authority=EventAuthority.BROKER_AUTHORITATIVE,
                dedupe_key=f"{FP}:fake-direct-release:{order.id}",
                ts_event=NOW,
                symbol=order.symbol,
                side=OrderSide.SELL,
                quantity=order.quantity,
                price=order.limit_price,
                order_id=order.id,
                session_id=order.session_id,
                correlation_id=intent.id,
                payload={"claim_occurrence": 0},
            )
        )
    else:
        await any_store.transition_order(order.id, OrderStatus.CREATED)
        await any_store.transition_order(order.id, OrderStatus.CANCELED)

    current = await any_store.get_order(order.id)
    order_events = [
        event
        for event in await any_store.get_execution_events()
        if event.order_id == order.id
        and event.event_type is not ExecutionEventType.ENVELOPE_ACTION
    ]
    possibly_live = direct_sell_order_may_execute(current, order_events)

    assert possibly_live is (release_kind == "fake-broker")
    if release_kind == "fake-broker":
        retained = await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
        assert retained.id == intent.id
    else:
        replacement = await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
        assert replacement.id != intent.id


async def test_broker_accepted_submit_transition_race_creates_recovery(
    any_store, monkeypatch
):
    _, intent, envelope = await _activate(any_store)
    adapter = MockBrokerAdapter()
    original_transition = any_store.transition_order
    failures = 0

    async def fail_local_submit(order_id, new_status, *args, **kwargs):
        nonlocal failures
        if new_status is OrderStatus.SUBMITTED and failures < 2:
            failures += 1
            raise OrderTransitionError("injected post-accept submit persistence race")
        return await original_transition(order_id, new_status, *args, **kwargs)

    monkeypatch.setattr(any_store, "transition_order", fail_local_submit)
    result = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _action(),
        snapshot_fingerprint=f"{FP}:accepted-submit-race",
        now=NOW,
    )

    assert result.outcome == "quarantined"
    assert failures == 2
    assert len(adapter.submitted) == 1
    recoveries = await any_store.list_submit_recoveries(statuses={RECOVERY_UNRESOLVED})
    assert len(recoveries) == 1
    recovery = recoveries[0]
    assert recovery.local_order_id == result.order_id
    assert recovery.broker_order_id == result.broker_order_id
    assert (await any_store.get_order(result.order_id)).status is OrderStatus.SUBMITTING
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_broker_accepted_reprice_transition_race_creates_recovery(
    any_store, monkeypatch
):
    _, intent, envelope = await _activate(any_store)
    adapter = MockBrokerAdapter()
    first = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _action(),
        snapshot_fingerprint=f"{FP}:accepted-reprice-first",
        now=NOW,
    )
    assert first.outcome == ENVELOPE_EXEC_SUBMITTED
    predecessor = await any_store.get_order(first.order_id)
    assert predecessor is not None and predecessor.broker_order_id is not None
    original_transition = any_store.transition_order
    failures = 0

    async def fail_replacement_submit(order_id, new_status, *args, **kwargs):
        nonlocal failures
        if (
            order_id != predecessor.id
            and new_status is OrderStatus.SUBMITTED
            and failures < 2
        ):
            failures += 1
            raise OrderTransitionError("injected post-replace persistence race")
        return await original_transition(order_id, new_status, *args, **kwargs)

    monkeypatch.setattr(any_store, "transition_order", fail_replacement_submit)
    result = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _action(kind=ActionKind.REPRICE, price=9.8),
        snapshot_fingerprint=f"{FP}:accepted-reprice-race",
        now=NOW + timedelta(minutes=1),
    )

    assert result.outcome == "quarantined"
    assert failures == 2
    assert [call[0] for call in adapter.replaced] == [predecessor.broker_order_id]
    recoveries = await any_store.list_submit_recoveries(statuses={RECOVERY_UNRESOLVED})
    assert len(recoveries) == 1
    recovery = recoveries[0]
    assert recovery.local_order_id == result.order_id
    assert recovery.broker_order_id == result.broker_order_id
    assert (await any_store.get_order(result.order_id)).status is OrderStatus.SUBMITTING
    assert (await any_store.get_order(predecessor.id)).status is OrderStatus.SUBMITTED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


@pytest.mark.parametrize(
    "fail_first", [False, True], ids=["all-converge", "isolated-failure"]
)
async def test_cancel_and_return_cancels_every_valid_legacy_venue_child(
    any_store, fail_first
):
    _, intent, envelope = await _activate(any_store)
    first = _raw_seed_live_child(
        any_store, envelope, order_id="legacy-cancel-child-first"
    )
    second = _raw_seed_live_child(
        any_store, envelope, order_id="legacy-cancel-child-second"
    )
    expired = await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        reason="cancel-and-return legacy lineage",
        now=NOW,
    )
    assert expired.expiry_disposition is EnvelopeExpiryDisposition.CANCEL_AND_RETURN
    adapter = MockBrokerAdapter()
    if fail_first:
        adapter.fail_next_cancel(BrokerError("isolated first-child cancel failure"))

    await _converge_expired_envelope_cancels(any_store, adapter)

    assert adapter.canceled == [first.broker_order_id, second.broker_order_id]
    first_after = await any_store.get_order(first.id)
    second_after = await any_store.get_order(second.id)
    if fail_first:
        assert first_after.status is OrderStatus.SUBMITTED
    else:
        assert first_after.status is OrderStatus.CANCEL_PENDING
    assert second_after.status is OrderStatus.CANCEL_PENDING
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_cancel_and_return_recovers_broker_open_terminal_local_child(any_store):
    _, intent, envelope = await _activate(any_store)
    child = Order(
        id="legacy-terminal-local-live-venue",
        sell_intent_id=intent.id,
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=envelope.qty_ceiling,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        broker_order_id="broker-legacy-terminal-local-live-venue",
        session_id=envelope.session_id,
        created_at=NOW,
        updated_at=NOW + timedelta(seconds=2),
        submitted_at=NOW + timedelta(seconds=1),
        canceled_at=NOW + timedelta(seconds=2),
    )
    _raw_insert_order(any_store, child)
    _raw_append_execution(any_store, _action_event(envelope, child))
    _raw_append_execution(
        any_store,
        ExecutionEvent(
            event_type=ExecutionEventType.SUBMIT_PENDING,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=f"submit_pending:{child.id}:0",
            ts_event=NOW,
            ts_init=NOW,
            symbol=child.symbol,
            side=child.side,
            quantity=child.quantity,
            price=child.limit_price,
            order_id=child.id,
            envelope_id=envelope.id,
            session_id=child.session_id,
            correlation_id=intent.id,
            payload={"claim_occurrence": 0},
        ),
    )
    _raw_append_execution(
        any_store,
        _status_event(
            ExecutionEventType.SUBMITTED,
            child,
            envelope,
            ts_event=NOW + timedelta(seconds=1),
            ts_init=NOW + timedelta(seconds=1),
        ),
    )
    _raw_append_execution(
        any_store,
        _status_event(
            ExecutionEventType.CANCELED,
            child,
            envelope,
            authority=EventAuthority.LOCAL,
            source=EventSource.ENGINE,
            ts_event=NOW + timedelta(seconds=2),
            ts_init=NOW + timedelta(seconds=2),
        ),
    )
    assert (await any_store.get_order(child.id)).status is OrderStatus.CANCELED

    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        reason="cancel broker interval hidden by local terminal state",
        now=NOW + timedelta(seconds=3),
    )
    adapter = MockBrokerAdapter()

    await _converge_expired_envelope_cancels(any_store, adapter)

    assert adapter.canceled == [child.broker_order_id]
    recoveries = await any_store.list_submit_recoveries(statuses={RECOVERY_UNRESOLVED})
    assert len(recoveries) == 1
    recovery = recoveries[0]
    assert recovery.local_order_id == child.id
    assert recovery.broker_order_id == child.broker_order_id
    assert recovery.symbol == child.symbol
    assert recovery.side is child.side
    assert recovery.quantity == child.quantity
    assert recovery.limit_price == child.limit_price
    assert recovery.session_id == child.session_id
    audits = [
        event
        for event in await any_store.list_events()
        if event.order_id == child.id
        and event.payload.get("recovery_id") == recovery.id
    ]
    assert len(audits) == 1
    assert audits[0].payload["claim_occurrence"] == 0
    assert audits[0].payload["envelope_id"] == envelope.id
    assert audits[0].payload["action_kind"] == "cancel_terminal_venue_interval"
    assert (await any_store.get_order(child.id)).status is OrderStatus.CANCELED
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


@pytest.mark.parametrize("excluded_kind", ["recovery", "uncertain-claim"])
async def test_cancel_exclusion_does_not_strand_valid_venue_sibling(
    any_store, excluded_kind
):
    _, intent, envelope = await _activate(any_store)
    if excluded_kind == "recovery":
        excluded = _raw_seed_live_child(
            any_store,
            envelope,
            order_id="legacy-recovery-owned-cancel-child",
        )
        await any_store.create_submit_recovery(
            local_order_id=excluded.id,
            broker_order_id=excluded.broker_order_id,
            client_order_id=excluded.id,
            symbol=excluded.symbol,
            side=excluded.side,
            quantity=excluded.quantity,
            limit_price=excluded.limit_price,
            failure_reason="operator-owned cleanup must not block sibling",
            session_id=excluded.session_id,
            extra_payload={"envelope_id": envelope.id},
        )
    else:
        excluded = Order(
            id="legacy-claim-uncertain-cancel-child",
            sell_intent_id=intent.id,
            symbol=envelope.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=envelope.qty_ceiling,
            limit_price=9.9,
            status=OrderStatus.SUBMITTING,
            session_id=envelope.session_id,
            created_at=NOW,
            updated_at=NOW,
        )
        _raw_insert_order(any_store, excluded)
        _raw_append_execution(any_store, _action_event(envelope, excluded))
        _raw_append_execution(
            any_store,
            ExecutionEvent(
                event_type=ExecutionEventType.SUBMIT_PENDING,
                source=EventSource.ENGINE,
                authority=EventAuthority.LOCAL,
                dedupe_key=f"submit_pending:{excluded.id}:0",
                ts_event=NOW,
                ts_init=NOW,
                symbol=excluded.symbol,
                side=excluded.side,
                quantity=excluded.quantity,
                price=excluded.limit_price,
                order_id=excluded.id,
                envelope_id=envelope.id,
                session_id=excluded.session_id,
                correlation_id=intent.id,
                payload={"claim_occurrence": 0},
            ),
        )
    sibling = _raw_seed_live_child(
        any_store,
        envelope,
        order_id=f"legacy-valid-sibling-{excluded_kind}",
    )
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        reason="per-child cancel isolation",
        now=NOW + timedelta(seconds=3),
    )
    adapter = MockBrokerAdapter()

    await _converge_expired_envelope_cancels(any_store, adapter)

    assert adapter.canceled == [sibling.broker_order_id]
    assert (await any_store.get_order(sibling.id)).status is OrderStatus.CANCEL_PENDING
    assert (await any_store.get_order(excluded.id)).status is excluded.status
    recoveries = await any_store.list_submit_recoveries(statuses={RECOVERY_UNRESOLVED})
    assert len(recoveries) == (1 if excluded_kind == "recovery" else 0)
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_broker_order_id_is_write_once_with_zero_mutation_on_retarget(
    any_store,
):
    await any_store.initialize()
    session = await _hold(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    order = await any_store.create_order_for_sell_intent(
        intent.id, order_type=OrderType.LIMIT, limit_price=9.9
    )
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
    submitted = await any_store.transition_order(
        order.id,
        OrderStatus.SUBMITTED,
        broker_order_id="broker-write-once",
    )
    assert submitted.broker_order_id == "broker-write-once"

    before_order = await any_store.get_order(order.id)
    before_audit = await any_store.list_events()
    before_execution = await any_store.get_execution_events()
    same = await any_store.transition_order(
        order.id,
        OrderStatus.SUBMITTED,
        broker_order_id="broker-write-once",
    )
    assert same == before_order
    assert await any_store.list_events() == before_audit
    assert await any_store.get_execution_events() == before_execution

    with pytest.raises(InvalidOrderError, match="immutable once set"):
        await any_store.transition_order(
            order.id,
            OrderStatus.SUBMITTED,
            broker_order_id="broker-retargeted",
        )

    assert await any_store.get_order(order.id) == before_order
    assert await any_store.list_events() == before_audit
    assert await any_store.get_execution_events() == before_execution


async def test_only_atomic_supersede_can_enter_superseded_and_transfer_owner(
    any_store,
):
    session, intent, old = await _activate(any_store)
    bypass = plan_envelope_transition(
        old,
        EnvelopeStatus.SUPERSEDED,
        superseded_by_id="arbitrary-unpersisted-successor",
        now=NOW,
    )
    assert bypass.envelope is None
    assert isinstance(bypass.error, EnvelopeTransitionError)
    assert "only through the atomic supersede_envelope" in str(bypass.error)

    before_old = await any_store.get_envelope(old.id)
    before_owner = await any_store.get_sell_intent(intent.id)
    before_audit = await any_store.list_events()
    before_execution = await any_store.get_execution_events()
    with pytest.raises(
        EnvelopeTransitionError,
        match="only through the atomic supersede_envelope",
    ):
        await any_store.transition_envelope(
            old.id,
            EnvelopeStatus.SUPERSEDED,
            reason="must not manufacture a successor edge",
            now=NOW,
        )
    assert await any_store.get_envelope(old.id) == before_old
    assert await any_store.get_sell_intent(intent.id) == before_owner
    assert await any_store.list_events() == before_audit
    assert await any_store.get_execution_events() == before_execution

    successor = _draft(intent.id, session_id=session.id).model_copy(
        update={"floor_price": 9.1}
    )
    current = await any_store.supersede_envelope(
        old.id,
        successor,
        actor="operator-a",
        reason="atomic bounded amendment",
    )

    retired = await any_store.get_envelope(old.id)
    assert retired.status is EnvelopeStatus.SUPERSEDED
    assert retired.superseded_by_id == successor.id
    assert current.id == successor.id
    assert current.supersedes_id == old.id
    assert current.status is EnvelopeStatus.ACTIVE
    assert current.sell_intent_id == intent.id
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    assert (await any_store.active_sell_intent_for("AAPL")).id == intent.id


@pytest.mark.parametrize(
    "successor_shape",
    ["null", "dangling", "non-reciprocal"],
)
async def test_initialize_retains_malformed_superseded_owner_and_blocks_sibling(
    any_store, successor_shape
):
    session, intent, old = await _activate(any_store)
    if successor_shape == "null":
        successor_id = None
    elif successor_shape == "dangling":
        successor_id = "missing-supersession-successor"
    else:
        successor = _draft(intent.id, session_id=session.id).model_copy(
            update={"floor_price": 9.1}
        )
        _raw_insert_envelope(any_store, successor)
        successor_id = successor.id
    malformed = old.model_copy(
        update={
            "status": EnvelopeStatus.SUPERSEDED,
            "superseded_by_id": successor_id,
            "superseded_at": NOW,
            "updated_at": NOW,
        }
    )
    _raw_replace_envelope(any_store, malformed)
    _raw_force_owner_status(any_store, intent.id, SellIntentStatus.EXPIRED)
    before_ids = {item.id for item in await any_store.list_sell_intents()}

    await any_store.initialize()

    assert (await any_store.get_envelope(old.id)).status is EnvelopeStatus.SUPERSEDED
    restored = await any_store.get_sell_intent(intent.id)
    assert restored.status is SellIntentStatus.APPROVED
    assert await any_store.active_sell_intent_for("AAPL") is None
    with pytest.raises(
        SellIntentTransitionError,
        match="unresolved envelope delegation has no usable owner",
    ):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
    assert {item.id for item in await any_store.list_sell_intents()} == before_ids


async def test_initialize_retains_completed_envelope_with_remaining_quantity(
    any_store,
):
    session, intent, envelope = await _activate(any_store)
    malformed = envelope.model_copy(
        update={
            "status": EnvelopeStatus.COMPLETED,
            "remaining_quantity": 40,
            "completed_at": NOW,
            "updated_at": NOW,
        }
    )
    _raw_replace_envelope(any_store, malformed)
    _raw_force_owner_status(any_store, intent.id, SellIntentStatus.EXPIRED)
    before_ids = {item.id for item in await any_store.list_sell_intents()}

    await any_store.initialize()

    persisted = await any_store.get_envelope(envelope.id)
    assert persisted.status is EnvelopeStatus.COMPLETED
    assert persisted.remaining_quantity == 40
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED
    assert await any_store.active_sell_intent_for("AAPL") is None
    with pytest.raises(
        SellIntentTransitionError,
        match="unresolved envelope delegation has no usable owner",
    ):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
    assert {item.id for item in await any_store.list_sell_intents()} == before_ids


async def test_only_fill_path_can_complete_envelope_with_zero_mutation_on_reject(
    any_store,
):
    _, intent, envelope = await _activate(any_store)
    before_envelope = await any_store.get_envelope(envelope.id)
    before_owner = await any_store.get_sell_intent(intent.id)
    before_audit = await any_store.list_events()
    before_execution = await any_store.get_execution_events()

    with pytest.raises(
        EnvelopeTransitionError,
        match="COMPLETED is reachable only from the fill-driven Envelope path",
    ):
        await any_store.transition_envelope(
            envelope.id,
            EnvelopeStatus.COMPLETED,
            reason="must not fabricate zero remaining",
            now=NOW,
        )

    assert await any_store.get_envelope(envelope.id) == before_envelope
    assert await any_store.get_sell_intent(intent.id) == before_owner
    assert await any_store.list_events() == before_audit
    assert await any_store.get_execution_events() == before_execution

    staged = await _stage(any_store, envelope.id)
    completed = await any_store.record_envelope_fill(
        envelope.id,
        quantity=100,
        dedupe_key=f"fill:{staged.order.id}:fill-only-completion",
        price=9.9,
        order_id=staged.order.id,
        session_id=staged.order.session_id,
        now=NOW + timedelta(seconds=1),
    )
    assert completed.status is EnvelopeStatus.COMPLETED
    assert completed.remaining_quantity == 0
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED


# --------------------------------------------------------------------------- #
# E.3.2 / R6: the cancel-convergence arm must fail closed LOUDLY, not silently.
# _cancel_envelope_working_order had two early returns (a vanished envelope, and
# a malformed/corrupt lineage) that no-oped with no log/alert/ledger entry, so a
# stranded live SELL never surfaced. These pin: (1) the malformed branch emits a
# warning and still cancels nothing, (2) the vanished-envelope branch emits a
# warning, and (3) — the load-bearing anti-spam negative — a benign clean lineage
# emits NO fail-closed warning (it proceeds down the normal cancel path). All
# three run on both stores (any_store) per CLAUDE.md's dual-store rule. These are
# the first caplog assertions in the tests/ tree.
# --------------------------------------------------------------------------- #


async def test_cancel_convergence_logs_and_no_ops_on_malformed_lineage(
    any_store, caplog
):
    await any_store.initialize()
    session = await _hold(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    # An EXPIRED CANCEL_AND_RETURN envelope whose lineage is malformed: an
    # ENVELOPE_ACTION references a child order that has no order row, so the
    # shared projection reports it in missing_order_ids and the cancel fails
    # closed (no target is guessed).
    malformed = _draft(intent.id, session_id=session.id).model_copy(
        update={
            "id": "malformed-expired-env",
            "status": EnvelopeStatus.EXPIRED,
            "approved_at": NOW - timedelta(minutes=1),
            "activated_at": NOW - timedelta(minutes=1),
            "expired_at": NOW,
        }
    )
    _raw_insert_envelope(any_store, malformed)
    ghost = Order(
        id="ghost-child-no-order-row",
        sell_intent_id=intent.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.SUBMITTED,
        broker_order_id="broker-ghost-child",
        session_id=session.id,
        submitted_at=NOW,
    )
    # Append the ENVELOPE_ACTION but do NOT insert the order row.
    _raw_append_execution(any_store, _action_event(malformed, ghost))

    # Precondition: the lineage genuinely trips the malformed fail-closed guard
    # (guards against the fixture silently going valid and vacuously passing).
    loaded = await _validated_envelope_lineage(any_store, malformed.id)
    assert loaded is not None
    _, projection, _ = loaded
    assert (
        projection.missing_order_ids
        or projection.missing_envelope_ids
        or projection.invalid_order_ids
    ), "fixture did not produce a malformed lineage"

    adapter = MockBrokerAdapter()
    with caplog.at_level(logging.WARNING, logger="app.monitoring"):
        await _cancel_envelope_working_order(any_store, adapter, malformed)

    # Behaviour unchanged — fail closed, nothing cancelled at the venue.
    assert adapter.canceled == []
    # Visibility — exactly one warning, naming the stranded envelope.
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and r.name == "app.monitoring"
    ]
    assert len(warnings) == 1
    assert malformed.id in warnings[0].getMessage()


async def test_cancel_convergence_logs_on_vanished_envelope(any_store, caplog):
    await any_store.initialize()
    session = await _hold(any_store)
    # An envelope object that was never inserted -> get_envelope returns None
    # inside the cancel function -> the vanished-envelope fail-closed branch.
    phantom = _draft("phantom-intent", session_id=session.id).model_copy(
        update={"id": "phantom-envelope"}
    )
    adapter = MockBrokerAdapter()
    with caplog.at_level(logging.WARNING, logger="app.monitoring"):
        await _cancel_envelope_working_order(any_store, adapter, phantom)

    assert adapter.canceled == []
    warnings = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING and r.name == "app.monitoring"
    ]
    assert len(warnings) == 1
    assert "phantom-envelope" in warnings[0].getMessage()


async def test_cancel_convergence_no_warning_on_benign_clean_lineage(any_store, caplog):
    # A valid ACTIVE envelope with a valid live child, then EXPIRED
    # CANCEL_AND_RETURN -> lineage is clean; the cancel proceeds down the normal
    # path (cancels the child) and must NOT emit a fail-closed warning. This is
    # the anti-spam pin: the new logging fires ONLY on the malformed/vanished
    # branches, never on the ordinary no-op/valid path.
    _, _, envelope = await _activate(any_store)
    child = _raw_seed_live_child(any_store, envelope, order_id="benign-live-child")
    expired = await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        reason="benign clean lineage",
        now=NOW,
    )
    adapter = MockBrokerAdapter()
    with caplog.at_level(logging.WARNING, logger="app.monitoring"):
        await _cancel_envelope_working_order(any_store, adapter, expired)

    # Normal path ran: the valid child was cancelled at the venue.
    assert adapter.canceled == [child.broker_order_id]
    # And NO fail-closed warning was emitted.
    fail_closed = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and r.name == "app.monitoring"
        and "fail-closed" in r.getMessage()
    ]
    assert fail_closed == []


# --------------------------------------------------------------------------- #
# REV-0029 P1-1 (WO-0108 step 4): monitoring must load the store's OWNER-SCOPED
# identity universe, not an exact-envelope_id subset. The store's gates discover
# a hostile action through every immutable owner identity (parent envelope +
# owner correlation + referenced-order owner) and quarantine the symbol; a
# monitoring path that keys only on exact envelope_id projects clean-empty for
# an owner-keyed action whose parent is wrong/missing — losing the R6 malformed-
# lineage diagnostic and, worse, silently declining to fail closed. These pins
# seed the two owner-keyed shapes the reviewer named (correlation-keyed and
# order-owner-keyed), on both stores + a sqlite restart, and assert monitoring
# now SEES the action (projects it malformed) and fails the cancel closed loudly.
# --------------------------------------------------------------------------- #


async def _seed_owner_keyed_hostile_lineage(store, *, key: str):
    """An EXPIRED envelope ``E`` owns intent ``I``; a live SELL child asserts
    ownership by ``I`` ONLY through the chosen owner key, with a WRONG/missing
    parent ``envelope_id`` (never ``E.id``).

    ``key='correlation'`` -> the ENVELOPE_ACTION carries ``correlation_id=I``.
    ``key='order_owner'`` -> the action's ``correlation_id`` is a stranger and
    only the child ORDER carries ``sell_intent_id=I``. Either way the store's
    owner-scoped discovery quarantines the symbol, while a bare exact-envelope_id
    monitoring scan sees nothing.
    """

    await store.initialize()
    session = await _hold(store)
    owner = SellIntent(
        id="p1-1-owner",
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.EXPIRED,
        target_quantity=100,
        session_id=session.id,
        expired_at=NOW,
    )
    _raw_insert_intent(store, owner)
    envelope = _draft(owner.id, session_id=session.id).model_copy(
        update={
            "status": EnvelopeStatus.EXPIRED,
            "approved_at": NOW - timedelta(minutes=2),
            "activated_at": NOW - timedelta(minutes=2),
            "expired_at": NOW,
        }
    )
    _raw_insert_envelope(store, envelope)
    child = Order(
        id="p1-1-hostile-child",
        sell_intent_id=owner.id,  # referenced-order-owner key = I
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.SUBMITTED,
        broker_order_id="broker-p1-1-hostile",
        session_id=session.id,
        submitted_at=NOW,
    )
    _raw_insert_order(store, child)
    correlation = owner.id if key == "correlation" else "p1-1-stranger-owner"
    _raw_append_execution(
        store,
        _action_event(
            envelope,
            child,
            envelope_id="p1-1-missing-envelope-row",  # wrong/missing parent
            correlation_id=correlation,
        ),
    )
    _raw_append_execution(
        store, _status_event(ExecutionEventType.SUBMITTED, child, envelope)
    )
    return session, owner, envelope, child


@pytest.mark.parametrize("key", ["correlation", "order_owner"])
async def test_p1_1_owner_keyed_hostile_lineage_seen_and_fails_closed(
    any_store, key, caplog
):
    _, _, envelope, child = await _seed_owner_keyed_hostile_lineage(any_store, key=key)

    # DISCOVERY: monitoring now loads the owner-scoped universe, so the malformed
    # owner-keyed action is IN the projection (it was invisible to the old exact-
    # envelope_id scan, which projected clean-empty).
    loaded = await _validated_envelope_lineage(any_store, envelope.id)
    assert loaded is not None
    _, projection, _ = loaded
    assert (
        projection.missing_envelope_ids
        or projection.missing_order_ids
        or projection.invalid_order_ids
    ), (
        "monitoring projected a clean-empty lineage — the owner-keyed hostile "
        f"action ({key}) was not discovered (P1-1 regression)"
    )

    # FAIL CLOSED + R6: convergence emits the malformed-lineage warning and
    # cancels nothing (identity never validated).
    adapter = MockBrokerAdapter()
    with caplog.at_level(logging.WARNING, logger="app.monitoring"):
        await _cancel_envelope_working_order(any_store, adapter, envelope)
    assert adapter.canceled == []
    fail_closed = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and r.name == "app.monitoring"
        and "fail-closed" in r.getMessage()
        and "malformed lineage" in r.getMessage()
    ]
    assert len(fail_closed) == 1, (
        "monitoring did not emit the R6 malformed-lineage warning for the "
        f"owner-keyed hostile action ({key})"
    )
    # The hostile child was never touched.
    assert (await any_store.get_order(child.id)).status is OrderStatus.SUBMITTED


async def test_p1_1_owner_keyed_hostile_lineage_survives_sqlite_restart(
    tmp_path, caplog
):
    """The owner-scoped discovery is a property of the persisted event log, not
    of a live in-process index: a sqlite store reopened on the same file still
    sees the owner-keyed hostile action and fails the cancel closed."""

    db_path = tmp_path / "p1_1_restart.db"
    store = SqliteStateStore(db_path)
    _, _, envelope, child = await _seed_owner_keyed_hostile_lineage(
        store, key="order_owner"
    )
    if store._conn is not None:
        store._conn.close()
        store._conn = None

    reopened = SqliteStateStore(db_path)
    await reopened.initialize()
    loaded = await _validated_envelope_lineage(reopened, envelope.id)
    assert loaded is not None
    _, projection, _ = loaded
    assert (
        projection.missing_envelope_ids
        or projection.missing_order_ids
        or projection.invalid_order_ids
    ), "reopened sqlite store lost the owner-keyed hostile action (P1-1)"

    adapter = MockBrokerAdapter()
    with caplog.at_level(logging.WARNING, logger="app.monitoring"):
        await _cancel_envelope_working_order(reopened, adapter, envelope)
    assert adapter.canceled == []
    fail_closed = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and r.name == "app.monitoring"
        and "fail-closed" in r.getMessage()
    ]
    assert len(fail_closed) == 1
    assert (await reopened.get_order(child.id)).status is OrderStatus.SUBMITTED
    if reopened._conn is not None:
        reopened._conn.close()
        reopened._conn = None
