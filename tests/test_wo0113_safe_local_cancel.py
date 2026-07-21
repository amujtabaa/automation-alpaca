"""WO-0113 RED pins for one safe local-CREATED cancellation property.

Local cancellation is valid only while event truth still projects CREATED and
no recovery or venue identity says the order may have reached the broker.  The
same property must hold at direct transition, facade, envelope cleanup, and
session-close choke points on both stores.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.errors import ConflictError
from app.facade.store_backed import StoreBackedCommandFacade
from app.monitoring import _cancel_envelope_working_order
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
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_RESOLVED,
    RECOVERY_UNRESOLVED,
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionType,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 19, 18, 0, tzinfo=timezone.utc)
RACE_NOW = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)


async def _created_buy(store, *, symbol: str = "AAPL", quantity: int = 10):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        limit_price=9.9,
        session_id=session.id,
    )
    return session, candidate, order


def _raw_order_fields(store, order_id: str, **updates) -> None:
    if hasattr(store, "_orders"):
        store._orders[order_id] = store._orders[order_id].model_copy(update=updates)
        return
    assignments = ", ".join(f"{name} = ?" for name in updates)
    values = [
        value.value
        if isinstance(value, OrderStatus)
        else value.isoformat()
        if isinstance(value, datetime)
        else value
        for value in updates.values()
    ]
    store._conn.execute(
        f"UPDATE orders SET {assignments} WHERE id = ?", (*values, order_id)
    )
    store._conn.commit()


def _raw_order_storage_state(store, order_id: str) -> dict[str, object]:
    """Read the persisted row without applying the event projection."""

    if hasattr(store, "_orders"):
        order = store._orders[order_id]
        return {
            "status": order.status.value,
            "canceled_at": order.canceled_at,
            "updated_at": order.updated_at,
        }
    row = store._conn.execute(
        "SELECT status, canceled_at, updated_at FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()
    assert row is not None
    return {
        "status": row["status"],
        "canceled_at": row["canceled_at"],
        "updated_at": row["updated_at"],
    }


def _raw_recovery_status(store, recovery_id: str, cleanup_status: str) -> None:
    """Build a legacy/read-model distinction without adding a terminal fact."""

    if hasattr(store, "_submit_recoveries"):
        store._submit_recoveries = [
            recovery.model_copy(update={"cleanup_status": cleanup_status})
            if recovery.id == recovery_id
            else recovery
            for recovery in store._submit_recoveries
        ]
        return
    store._conn.execute(
        "UPDATE submit_recoveries SET cleanup_status = ? WHERE id = ?",
        (cleanup_status, recovery_id),
    )
    store._conn.commit()


def _raw_insert_order(store, order: Order) -> None:
    if hasattr(store, "_orders"):
        store._orders[order.id] = order
        return
    with store._tx() as cur:
        store._insert_order(cur, order)


def _raw_insert_envelope(store, envelope: ExecutionEnvelope) -> None:
    if hasattr(store, "_envelopes"):
        store._envelopes[envelope.id] = envelope
        return
    with store._tx() as cur:
        store._insert_envelope(cur, envelope)


def _raw_insert_sell_intent(store, intent: SellIntent) -> None:
    if hasattr(store, "_sell_intents"):
        store._sell_intents[intent.id] = intent
        return
    with store._tx() as cur:
        store._insert_sell_intent(cur, intent)


def _draft_envelope(
    intent_id: str, session_id: str, *, now: datetime = NOW
) -> ExecutionEnvelope:
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
        expires_at=now + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


async def _append_action(
    store,
    envelope: ExecutionEnvelope,
    order: Order,
    *,
    now: datetime = NOW,
) -> None:
    await store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.ENVELOPE_ACTION,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            ts_event=now,
            ts_init=now,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.limit_price,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={
                "action": "submit",
                "snapshot_fingerprint": f"wo0113-safe-cancel:{order.id}",
            },
        )
    )


async def _terminal_envelope_with_children(store, *order_ids: str):
    await store.initialize()
    session = await store.get_current_session()
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = _draft_envelope(intent.id, session.id).model_copy(
        update={
            "status": EnvelopeStatus.BREACHED,
            "approved_at": NOW - timedelta(minutes=2),
            "activated_at": NOW - timedelta(minutes=2),
            "breached_at": NOW,
        }
    )
    _raw_insert_envelope(store, envelope)
    orders = []
    for order_id in order_ids:
        order = Order(
            id=order_id,
            sell_intent_id=intent.id,
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            limit_price=9.9,
            status=OrderStatus.CREATED,
            session_id=session.id,
        )
        _raw_insert_order(store, order)
        await _append_action(store, envelope, order)
        orders.append(order)
    return envelope, orders


async def _active_envelope_with_created_child(store):
    """Seed one projection-valid child with fixed ids and decision clocks."""

    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    holding = Order(
        id="wo0113-cancel-race-holding",
        candidate_id=candidate.id,
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=10.0,
        session_id=session.id,
        created_at=RACE_NOW - timedelta(minutes=5),
        updated_at=RACE_NOW - timedelta(minutes=5),
    )
    _raw_insert_order(store, holding)
    await store.append_fill(
        holding.id,
        holding.symbol,
        holding.side,
        holding.quantity,
        10.0,
        source_fill_id="wo0113-cancel-race-holding-fill",
        filled_at=RACE_NOW - timedelta(minutes=4),
        session_id=session.id,
    )
    intent = SellIntent(
        id="wo0113-cancel-race-intent",
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED,
        target_quantity=100,
        floor_price=9.0,
        observed_price=8.9,
        session_id=session.id,
        created_at=RACE_NOW - timedelta(minutes=3),
        updated_at=RACE_NOW - timedelta(minutes=2),
        approved_at=RACE_NOW - timedelta(minutes=2),
    )
    _raw_insert_sell_intent(store, intent)
    envelope = _draft_envelope(intent.id, session.id, now=RACE_NOW).model_copy(
        update={
            "id": "wo0113-cancel-race-envelope",
            "status": EnvelopeStatus.ACTIVE,
            "created_at": RACE_NOW - timedelta(minutes=3),
            "updated_at": RACE_NOW - timedelta(minutes=1),
            "approved_at": RACE_NOW - timedelta(minutes=2),
            "activated_at": RACE_NOW - timedelta(minutes=1),
        }
    )
    _raw_insert_envelope(store, envelope)
    child = Order(
        id="wo0113-cancel-race-child",
        sell_intent_id=intent.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CREATED,
        session_id=session.id,
        created_at=RACE_NOW,
        updated_at=RACE_NOW,
    )
    _raw_insert_order(store, child)
    await _append_action(store, envelope, child, now=RACE_NOW)
    return envelope, child


def _canceled_facts(events, order_id: str):
    return [
        event
        for event in events
        if event.order_id == order_id
        and event.event_type is ExecutionEventType.CANCELED
    ]


@pytest.mark.parametrize("cleanup_status", [RECOVERY_UNRESOLVED, RECOVERY_NEEDS_REVIEW])
async def test_direct_created_cancel_is_blocked_by_open_recovery(
    any_store, cleanup_status
):
    session, candidate, order = await _created_buy(any_store)
    await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"paper-{order.id}",
        client_order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason="WO-0113 recovery owns the local CREATED row",
        cleanup_status=cleanup_status,
        session_id=session.id,
        candidate_id=candidate.id,
    )
    before = await any_store.get_execution_events()

    returned = await any_store.transition_order(
        order.id,
        OrderStatus.CANCELED,
        expected_from=OrderStatus.CREATED,
    )

    assert returned.status is OrderStatus.CREATED
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED
    after = await any_store.get_execution_events()
    assert _canceled_facts(after, order.id) == _canceled_facts(before, order.id) == []


async def test_direct_created_cancel_is_blocked_by_venue_identity(any_store):
    _session, _candidate, order = await _created_buy(any_store)
    _raw_order_fields(any_store, order.id, broker_order_id=f"paper-{order.id}")

    returned = await any_store.transition_order(
        order.id,
        OrderStatus.CANCELED,
        expected_from=OrderStatus.CREATED,
    )

    assert returned.status is OrderStatus.CREATED
    assert returned.broker_order_id == f"paper-{order.id}"
    assert _canceled_facts(await any_store.get_execution_events(), order.id) == []


async def test_resolved_recovery_does_not_block_local_created_cancel(any_store):
    session, candidate, order = await _created_buy(any_store)
    recovery = await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"paper-{order.id}",
        client_order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason="WO-0113 resolved recovery is no longer venue exposure",
        cleanup_status=RECOVERY_UNRESOLVED,
        session_id=session.id,
        candidate_id=candidate.id,
    )
    # A public resolution appends broker-terminal event truth and therefore
    # projects CANCELED already. This raw legacy distinction isolates the guard:
    # only RECOVERY_OPEN_STATUSES may prevent a still-CREATED local cancel.
    _raw_recovery_status(any_store, recovery.id, RECOVERY_RESOLVED)

    returned = await any_store.transition_order(
        order.id,
        OrderStatus.CANCELED,
        expected_from=OrderStatus.CREATED,
    )

    assert returned.status is OrderStatus.CANCELED
    assert len(_canceled_facts(await any_store.get_execution_events(), order.id)) == 1


async def test_direct_created_cancel_uses_event_projection_not_raw_status(any_store):
    session, candidate, projected_created = await _created_buy(any_store)
    projected_submitting = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        11,
        limit_price=9.8,
        session_id=session.id,
    )

    claimed = await any_store.claim_order_for_submission(projected_created.id)
    assert claimed.order is not None
    await any_store.transition_order(projected_created.id, OrderStatus.CREATED)
    _raw_order_fields(any_store, projected_created.id, status=OrderStatus.SUBMITTING)
    assert (
        await any_store.get_order(projected_created.id)
    ).status is OrderStatus.CREATED

    claimed = await any_store.claim_order_for_submission(projected_submitting.id)
    assert claimed.order is not None
    _raw_order_fields(any_store, projected_submitting.id, status=OrderStatus.CREATED)
    assert (
        await any_store.get_order(projected_submitting.id)
    ).status is OrderStatus.SUBMITTING

    canceled = await any_store.transition_order(
        projected_created.id,
        OrderStatus.CANCELED,
        expected_from=OrderStatus.CREATED,
    )
    skipped = await any_store.transition_order(
        projected_submitting.id,
        OrderStatus.CANCELED,
        expected_from=OrderStatus.CREATED,
    )

    assert canceled.status is OrderStatus.CANCELED
    assert skipped.status is OrderStatus.SUBMITTING
    execution = await any_store.get_execution_events()
    assert len(_canceled_facts(execution, projected_created.id)) == 1
    assert _canceled_facts(execution, projected_submitting.id) == []


async def test_facade_created_cancel_loses_safely_to_submission_claim(
    any_store, monkeypatch
):
    _session, _candidate, order = await _created_buy(any_store)
    real_get_order = any_store.get_order
    raced = False

    async def stale_created_then_claim(order_id: str):
        nonlocal raced
        snapshot = await real_get_order(order_id)
        if not raced:
            raced = True
            claim = await any_store.claim_order_for_submission(order_id)
            assert claim.order is not None
            assert claim.order.status is OrderStatus.SUBMITTING
        return snapshot

    monkeypatch.setattr(any_store, "get_order", stale_created_then_claim)
    adapter = MockBrokerAdapter()
    facade = StoreBackedCommandFacade(any_store, broker=adapter, settings=Settings())

    with pytest.raises(ConflictError):
        await facade.cancel(order_id=order.id, actor="operator-a")

    monkeypatch.setattr(any_store, "get_order", real_get_order)
    current = await real_get_order(order.id)
    assert current is not None and current.status is OrderStatus.SUBMITTING
    assert adapter.canceled == []
    assert _canceled_facts(await any_store.get_execution_events(), order.id) == []


async def test_monitoring_created_cancel_race_uses_cas_returned_venue_state(
    any_store, monkeypatch
):
    store_clock = (
        "app.store.memory.utcnow"
        if hasattr(any_store, "_orders")
        else "app.store.sqlite.utcnow"
    )
    monkeypatch.setattr(store_clock, lambda: RACE_NOW)
    envelope, child = await _active_envelope_with_created_child(any_store)
    adapter = MockBrokerAdapter()
    broker_order_id = "paper-wo0113-cancel-race-child"
    real_transition = any_store.transition_order
    raced = False

    async def claim_and_ack_before_cancel(
        order_id: str,
        new_status: OrderStatus,
        **kwargs,
    ):
        nonlocal raced
        if not raced and order_id == child.id and new_status is OrderStatus.CANCELED:
            raced = True
            assert kwargs.get("expected_from") is OrderStatus.CREATED
            claim = await any_store.claim_order_for_submission(child.id)
            assert claim.order is not None
            assert claim.order.status is OrderStatus.SUBMITTING
            acknowledged = await real_transition(
                child.id,
                OrderStatus.SUBMITTED,
                broker_order_id=broker_order_id,
            )
            assert acknowledged.status is OrderStatus.SUBMITTED
            assert acknowledged.broker_order_id == broker_order_id
        return await real_transition(order_id, new_status, **kwargs)

    monkeypatch.setattr(any_store, "transition_order", claim_and_ack_before_cancel)

    await _cancel_envelope_working_order(any_store, adapter, envelope)

    assert raced
    current = await any_store.get_order(child.id)
    assert current is not None
    assert current.status is OrderStatus.CANCEL_PENDING
    assert current.broker_order_id == broker_order_id
    assert adapter.canceled == [broker_order_id]
    assert _canceled_facts(await any_store.get_execution_events(), child.id) == []


async def test_monitoring_created_cancel_race_revalidates_broker_terminal_fill(
    any_store, monkeypatch
):
    store_clock = (
        "app.store.memory.utcnow"
        if hasattr(any_store, "_orders")
        else "app.store.sqlite.utcnow"
    )
    monkeypatch.setattr(store_clock, lambda: RACE_NOW)
    envelope, child = await _active_envelope_with_created_child(any_store)
    adapter = MockBrokerAdapter()
    broker_order_id = "paper-wo0113-cancel-race-filled-child"
    real_transition = any_store.transition_order
    raced = False

    async def fill_before_cancel_cas(
        order_id: str,
        new_status: OrderStatus,
        **kwargs,
    ):
        nonlocal raced
        if not raced and order_id == child.id and new_status is OrderStatus.CANCELED:
            raced = True
            assert kwargs.get("expected_from") is OrderStatus.CREATED
            claim = await any_store.claim_order_for_submission(child.id)
            assert claim.order is not None
            assert claim.order.status is OrderStatus.SUBMITTING
            await real_transition(
                child.id,
                OrderStatus.SUBMITTED,
                broker_order_id=broker_order_id,
            )
            await any_store.append_fill(
                child.id,
                child.symbol,
                OrderSide.SELL,
                child.quantity,
                child.limit_price,
                source_fill_id="wo0113-created-cancel-race-terminal-fill",
                filled_at=RACE_NOW,
                session_id=child.session_id,
            )
            await real_transition(
                child.id,
                OrderStatus.FILLED,
                filled_quantity=child.quantity,
            )
        return await real_transition(order_id, new_status, **kwargs)

    monkeypatch.setattr(any_store, "transition_order", fill_before_cancel_cas)

    await _cancel_envelope_working_order(any_store, adapter, envelope)

    assert raced
    current = await any_store.get_order(child.id)
    assert current is not None and current.status is OrderStatus.FILLED
    assert adapter.canceled == []
    assert await any_store.list_submit_recoveries() == []
    assert not any(
        event.event_type is ExecutionEventType.ENVELOPE_ACTION
        and event.order_id == child.id
        and event.payload.get("action") == "cancel"
        for event in await any_store.get_execution_events()
    )


async def test_terminal_fill_excludes_source_cancels_sibling_and_reconciles_once(
    any_store, monkeypatch
):
    envelope, children = await _terminal_envelope_with_children(
        any_store,
        "wo0113-fill-source",
        "wo0113-lingering-created-sibling",
    )
    source, sibling = children

    calls = 0
    if hasattr(any_store, "_reconcile_envelope_owner_unlocked"):
        real_reconcile = any_store._reconcile_envelope_owner_unlocked

        def counted_reconcile(intent_id, *, now=None):
            nonlocal calls
            calls += 1
            return real_reconcile(intent_id, now=now)

        monkeypatch.setattr(
            any_store, "_reconcile_envelope_owner_unlocked", counted_reconcile
        )
    else:
        real_reconcile = any_store._reconcile_envelope_owner_locked

        def counted_reconcile(cur, intent_id, *, now=None):
            nonlocal calls
            calls += 1
            return real_reconcile(cur, intent_id, now=now)

        monkeypatch.setattr(
            any_store, "_reconcile_envelope_owner_locked", counted_reconcile
        )

    await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key="wo0113-terminal-late-fill",
        order_id=source.id,
        price=9.9,
        now=NOW,
    )

    source_after = await any_store.get_order(source.id)
    sibling_after = await any_store.get_order(sibling.id)
    assert source_after is not None and source_after.status is OrderStatus.CREATED
    assert sibling_after is not None and sibling_after.status is OrderStatus.CANCELED
    canceled = _canceled_facts(await any_store.get_execution_events(), sibling.id)
    assert len(canceled) == 1
    assert _canceled_facts(await any_store.get_execution_events(), source.id) == []
    assert calls == 1


async def test_terminal_cleanup_spares_recovery_owned_created_child(any_store):
    envelope, children = await _terminal_envelope_with_children(
        any_store, "wo0113-terminal-recovery-owned-child"
    )
    child = children[0]
    await any_store.create_submit_recovery(
        local_order_id=child.id,
        broker_order_id="paper-wo0113-terminal-recovery-owned-child",
        client_order_id=child.id,
        symbol=child.symbol,
        side=child.side,
        quantity=child.quantity,
        limit_price=child.limit_price,
        failure_reason="WO-0113 terminal cleanup must preserve recovery ownership",
        cleanup_status=RECOVERY_UNRESOLVED,
        session_id=child.session_id,
        candidate_id=child.candidate_id,
    )
    before = await any_store.get_order(child.id)
    assert before is not None and before.status is OrderStatus.CREATED

    await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key="wo0113-terminal-recovery-owned-fill",
        order_id=None,
        price=9.9,
        now=NOW + timedelta(minutes=1),
    )

    current = await any_store.get_order(child.id)
    assert current is not None and current.status is OrderStatus.CREATED
    assert current.canceled_at is None
    assert _canceled_facts(await any_store.get_execution_events(), child.id) == []


async def test_terminal_cleanup_uses_injected_fill_clock(any_store):
    envelope, children = await _terminal_envelope_with_children(
        any_store, "wo0113-terminal-clock-child"
    )
    child = children[0]

    await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key="wo0113-terminal-clock-fill",
        order_id=None,
        price=9.9,
        now=NOW,
    )

    canceled = await any_store.get_order(child.id)
    assert canceled is not None and canceled.status is OrderStatus.CANCELED
    assert canceled.canceled_at == NOW
    assert canceled.updated_at == NOW


async def test_session_close_uses_projection_spares_recovery_and_counts_exactly(
    any_store,
):
    session, candidate, projected_created = await _created_buy(any_store)
    projected_submitting = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        11,
        limit_price=9.8,
        session_id=session.id,
    )
    recovery_owned = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        12,
        limit_price=9.7,
        session_id=session.id,
    )

    first_claim = await any_store.claim_order_for_submission(projected_created.id)
    assert first_claim.order is not None
    await any_store.transition_order(projected_created.id, OrderStatus.CREATED)
    _raw_order_fields(any_store, projected_created.id, status=OrderStatus.SUBMITTING)
    assert (
        await any_store.get_order(projected_created.id)
    ).status is OrderStatus.CREATED

    second_claim = await any_store.claim_order_for_submission(projected_submitting.id)
    assert second_claim.order is not None
    _raw_order_fields(any_store, projected_submitting.id, status=OrderStatus.CREATED)
    assert (
        await any_store.get_order(projected_submitting.id)
    ).status is OrderStatus.SUBMITTING

    await any_store.create_submit_recovery(
        local_order_id=recovery_owned.id,
        broker_order_id=f"paper-{recovery_owned.id}",
        client_order_id=recovery_owned.id,
        symbol=recovery_owned.symbol,
        side=recovery_owned.side,
        quantity=recovery_owned.quantity,
        limit_price=recovery_owned.limit_price,
        failure_reason="WO-0113 close must preserve recovery truth",
        cleanup_status=RECOVERY_UNRESOLVED,
        session_id=session.id,
        candidate_id=candidate.id,
    )

    await any_store.close_session(session.id, actor="operator-a")

    assert (
        await any_store.get_order(projected_created.id)
    ).status is OrderStatus.CANCELED
    assert (
        await any_store.get_order(projected_submitting.id)
    ).status is OrderStatus.SUBMITTING
    assert (await any_store.get_order(recovery_owned.id)).status is OrderStatus.CREATED
    close_events = await any_store.list_events(event_type="session_closed")
    assert len(close_events) == 1
    assert close_events[0].payload["canceled_orders"] == 1
    execution = await any_store.get_execution_events()
    assert len(_canceled_facts(execution, projected_created.id)) == 1
    assert _canceled_facts(execution, projected_submitting.id) == []
    assert _canceled_facts(execution, recovery_owned.id) == []


async def test_local_created_cancel_rolls_back_row_audit_and_execution(
    any_store, monkeypatch
):
    _session, _candidate, order = await _created_buy(any_store)
    persisted_updated_at = NOW - timedelta(minutes=15)
    _raw_order_fields(
        any_store,
        order.id,
        status=OrderStatus.CREATED,
        canceled_at=None,
        updated_at=persisted_updated_at,
    )
    raw_before = _raw_order_storage_state(any_store, order.id)
    assert raw_before["status"] == OrderStatus.CREATED.value
    assert raw_before["canceled_at"] is None
    stored_updated_at = raw_before["updated_at"]
    assert stored_updated_at is not None
    if isinstance(stored_updated_at, str):
        assert datetime.fromisoformat(stored_updated_at) == persisted_updated_at
    else:
        assert stored_updated_at == persisted_updated_at
    audit_before = [event.id for event in await any_store.list_events()]
    execution_before = [event.id for event in await any_store.get_execution_events()]

    if hasattr(any_store, "_append_event_unlocked"):
        real_append = any_store._append_event_unlocked

        def fail_cancel_audit(event_type, *args, **kwargs):
            if (
                event_type == "order_transition"
                and kwargs.get("order_id") == order.id
                and kwargs.get("payload", {}).get("to") == "canceled"
            ):
                raise RuntimeError("WO-0113 injected cancel audit failure")
            return real_append(event_type, *args, **kwargs)

        monkeypatch.setattr(any_store, "_append_event_unlocked", fail_cancel_audit)
    else:
        real_append = any_store._insert_event

        def fail_cancel_audit(cur, event_type, *args, **kwargs):
            if (
                event_type == "order_transition"
                and kwargs.get("order_id") == order.id
                and kwargs.get("payload", {}).get("to") == "canceled"
            ):
                raise RuntimeError("WO-0113 injected cancel audit failure")
            return real_append(cur, event_type, *args, **kwargs)

        monkeypatch.setattr(any_store, "_insert_event", fail_cancel_audit)

    with pytest.raises(RuntimeError, match="injected cancel audit failure"):
        await any_store.transition_order(
            order.id,
            OrderStatus.CANCELED,
            expected_from=OrderStatus.CREATED,
        )

    current = await any_store.get_order(order.id)
    assert current is not None and current.status is OrderStatus.CREATED
    assert _raw_order_storage_state(any_store, order.id) == raw_before
    assert [event.id for event in await any_store.list_events()] == audit_before
    assert [
        event.id for event in await any_store.get_execution_events()
    ] == execution_before
