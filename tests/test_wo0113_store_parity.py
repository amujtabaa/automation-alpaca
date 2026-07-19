"""WO-0113 C2 distinguishing-state pins for store decision parity."""

from __future__ import annotations

from datetime import datetime, timezone
import sys

import pytest

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_RESOLVED,
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
)
from app.store.base import RecoveryTransitionError, StoreError

pytestmark = pytest.mark.anyio

DAY_ONE = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)
DAY_TWO = datetime(2026, 7, 21, 18, 0, tzinfo=timezone.utc)


async def _held(store, *, quantity: int = 100):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        quantity,
        10.0,
        source_fill_id="wo0113-parity-hold",
        session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    return session, candidate


def _raw_order_status(store, order_id: str, status: OrderStatus) -> None:
    if hasattr(store, "_orders"):
        store._orders[order_id] = store._orders[order_id].model_copy(
            update={"status": status}
        )
        return
    store._conn.execute(
        "UPDATE orders SET status = ? WHERE id = ?", (status.value, order_id)
    )
    store._conn.commit()


async def test_open_protection_idempotent_return_uses_event_projection(any_store):
    """C2: an idempotent return is still an event-truth read path."""

    session, _candidate = await _held(any_store)
    order = await any_store.open_protection_exit(
        symbol="AAPL",
        target_quantity=100,
        floor_price=9.0,
        observed_price=8.5,
        average_price=10.0,
        session_id=session.id,
    )
    assert order is not None
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.order is not None
    _raw_order_status(any_store, order.id, OrderStatus.CREATED)
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING

    returned = await any_store.open_protection_exit(
        symbol="AAPL",
        target_quantity=100,
        floor_price=9.0,
        observed_price=8.5,
        average_price=10.0,
        session_id=session.id,
    )
    assert returned is not None and returned.status is OrderStatus.SUBMITTING


async def test_append_fill_without_source_id_does_not_exclude_empty_dedupe(any_store):
    """C2: ``None`` self-identity excludes nothing in either store."""

    await any_store.initialize()
    session = await any_store.get_current_session()
    candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 10, session_id=session.id
    )
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key="",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            price=10.0,
            order_id=buy.id,
            session_id=session.id,
        )
    )
    sell = await any_store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.SELL, 10, session_id=session.id
    )

    result = await any_store.append_fill(
        sell.id,
        "AAPL",
        OrderSide.SELL,
        10,
        9.9,
        source_fill_id=None,
        session_id=session.id,
    )
    assert result.status == "appended"
    assert result.event.event_type == "fill_appended"
    assert (await any_store.get_position("AAPL")).quantity == 0


async def test_duplicate_execution_event_id_is_domain_rejected(any_store):
    """C2: caller-owned event identity cannot fork within the append-only log."""

    await any_store.initialize()
    event = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        payload={"action": "noop"},
    )
    await any_store.append_execution_event(event)

    with pytest.raises(StoreError, match="event id"):
        await any_store.append_execution_event(event)
    assert [item.id for item in await any_store.get_execution_events()] == [event.id]


async def test_audit_payload_is_json_canonical_and_invalid_payload_is_rejected(
    any_store,
):
    """C2: memory exposes the same durable JSON value domain as SQLite."""

    await any_store.initialize()
    await any_store.append_event("wo0113_json", payload={"items": (1, 2)})
    listed = await any_store.list_events(event_type="wo0113_json")
    assert listed[-1].payload == {"items": [1, 2]}
    before = len(await any_store.list_events())

    with pytest.raises(StoreError, match="JSON"):
        await any_store.append_event("wo0113_bad_json", payload={"bad": {1, 2}})
    assert len(await any_store.list_events()) == before


async def test_execution_payload_is_json_canonical_and_invalid_payload_is_rejected(
    any_store,
):
    """C2: execution-event payloads share one validated durable domain."""

    await any_store.initialize()
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.ENVELOPE_ACTION,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            payload={"items": (1, 2)},
        )
    )
    assert (await any_store.get_execution_events())[-1].payload == {"items": [1, 2]}
    before = len(await any_store.get_execution_events())

    with pytest.raises(StoreError, match="JSON"):
        await any_store.append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.ENVELOPE_ACTION,
                source=EventSource.ENGINE,
                authority=EventAuthority.LOCAL,
                payload={"bad": {1, 2}},
            )
        )
    assert len(await any_store.get_execution_events()) == before


async def test_recovery_extra_payload_uses_the_same_json_domain(any_store):
    """C2: recovery audit payloads cannot diverge by backend serialization."""

    await any_store.initialize()
    session = await any_store.get_current_session()
    candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    order = await any_store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 10, session_id=session.id
    )
    await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id="broker-json-good",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        failure_reason="wo0113 json parity",
        session_id=session.id,
        extra_payload={"items": (1, 2)},
    )
    events = await any_store.list_events(event_type="submit_recovery_recorded")
    assert events[-1].payload["items"] == [1, 2]
    # WO-0113 duplicate-ownership remediation rejects reusing ``order`` with a
    # second broker id before payload persistence. Use an independent identity
    # so this pin still reaches (and preserves) the JSON-domain boundary.
    bad_order = await _recovery_order(any_store, "MSFT")
    before_recoveries = len(await any_store.list_submit_recoveries())
    before_events = len(await any_store.list_events())

    with pytest.raises(StoreError, match="JSON"):
        await any_store.create_submit_recovery(
            local_order_id=bad_order.id,
            broker_order_id="broker-json-bad",
            symbol=bad_order.symbol,
            side=bad_order.side,
            quantity=bad_order.quantity,
            failure_reason="wo0113 invalid json",
            session_id=bad_order.session_id,
            extra_payload={"bad": {1, 2}},
        )
    assert len(await any_store.list_submit_recoveries()) == before_recoveries
    assert len(await any_store.list_events()) == before_events


async def _recovery_order(any_store, symbol: str):
    session = await any_store.get_current_session()
    candidate = await any_store.create_candidate(symbol, session_id=session.id)
    return await any_store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        10,
        session_id=session.id,
    )


async def test_submit_recovery_exact_pair_retry_is_idempotent(any_store):
    """C2/C3: one accepted broker/local pair has one durable owner."""

    await any_store.initialize()
    order = await _recovery_order(any_store, "AAPL")
    kwargs = {
        "local_order_id": order.id,
        "broker_order_id": "broker-wo0113-owner",
        "client_order_id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "limit_price": order.limit_price,
        "failure_reason": "accepted submit needs recovery",
        "session_id": order.session_id,
    }

    first = await any_store.create_submit_recovery(**kwargs)
    retried = await any_store.create_submit_recovery(**kwargs)
    await any_store.update_submit_recovery(first.id, cleanup_status=RECOVERY_RESOLVED)
    terminal_replay = await any_store.create_submit_recovery(**kwargs)

    assert retried.id == first.id
    assert terminal_replay.id == first.id
    assert terminal_replay.cleanup_status == RECOVERY_RESOLVED
    assert [item.id for item in await any_store.list_submit_recoveries()] == [first.id]
    recorded = await any_store.list_events(event_type="submit_recovery_recorded")
    assert [item.payload["recovery_id"] for item in recorded] == [first.id]


@pytest.mark.parametrize(
    "conflict",
    [
        "same_local_new_broker",
        "same_broker_new_local",
        "same_pair_new_quantity",
        "same_pair_new_cleanup_status",
    ],
)
async def test_submit_recovery_duplicate_identity_conflicts_fail_closed(
    any_store, conflict
):
    """C2/C3: a recovery identifier cannot acquire ambiguous ownership."""

    await any_store.initialize()
    first_order = await _recovery_order(any_store, "AAPL")
    second_order = await _recovery_order(any_store, "MSFT")
    kwargs = {
        "local_order_id": first_order.id,
        "broker_order_id": "broker-wo0113-owner-conflict",
        "client_order_id": first_order.id,
        "symbol": first_order.symbol,
        "side": first_order.side,
        "quantity": first_order.quantity,
        "limit_price": first_order.limit_price,
        "failure_reason": "accepted submit needs recovery",
        "session_id": first_order.session_id,
    }
    original = await any_store.create_submit_recovery(**kwargs)
    if conflict == "same_local_new_broker":
        kwargs["broker_order_id"] = "broker-wo0113-other"
    elif conflict == "same_broker_new_local":
        kwargs.update(
            {
                "local_order_id": second_order.id,
                "client_order_id": second_order.id,
                "symbol": second_order.symbol,
                "side": second_order.side,
                "quantity": second_order.quantity,
                "limit_price": second_order.limit_price,
                "session_id": second_order.session_id,
            }
        )
    else:
        if conflict == "same_pair_new_quantity":
            kwargs["quantity"] = first_order.quantity + 1
        else:
            kwargs["cleanup_status"] = RECOVERY_NEEDS_REVIEW

    with pytest.raises(RecoveryTransitionError, match="conflicts with existing"):
        await any_store.create_submit_recovery(**kwargs)

    assert [item.id for item in await any_store.list_submit_recoveries()] == [
        original.id
    ]
    recorded = await any_store.list_events(event_type="submit_recovery_recorded")
    assert [item.payload["recovery_id"] for item in recorded] == [original.id]


async def test_submit_recovery_unknown_broker_ids_do_not_alias(any_store):
    """An empty broker-id sentinel is absence, not a global venue identity."""

    await any_store.initialize()
    first_order = await _recovery_order(any_store, "AAPL")
    second_order = await _recovery_order(any_store, "MSFT")

    async def create_for(order):
        return await any_store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id="",
            client_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason="broker acceptance cannot be confirmed",
            session_id=order.session_id,
            cleanup_status=RECOVERY_NEEDS_REVIEW,
        )

    first = await create_for(first_order)
    second = await create_for(second_order)
    replayed = await create_for(first_order)

    assert first.id != second.id
    assert replayed.id == first.id
    assert {item.id for item in await any_store.list_submit_recoveries()} == {
        first.id,
        second.id,
    }


async def test_rollover_session_bootstrap_survives_failed_control_write(
    any_store, monkeypatch
):
    """C2: today's session is prerequisite truth, not part of control rollback."""

    module = sys.modules[type(any_store).__module__]
    monkeypatch.setattr(module, "utcnow", lambda: DAY_ONE)
    await any_store.initialize()
    assert len(await any_store.list_sessions()) == 1
    monkeypatch.setattr(module, "utcnow", lambda: DAY_TWO)

    def _fail_after_bootstrap(*_args, **_kwargs):
        raise RuntimeError("wo0113 injected control failure")

    method = (
        "_apply_control_change_unlocked"
        if hasattr(any_store, "_apply_control_change_unlocked")
        else "_apply_control_change_locked"
    )
    monkeypatch.setattr(any_store, method, _fail_after_bootstrap)
    with pytest.raises(RuntimeError, match="injected control failure"):
        await any_store.set_buys_paused(True)

    sessions = await any_store.list_sessions()
    assert [item.session_date for item in sessions] == [
        DAY_ONE.date().isoformat(),
        DAY_TWO.date().isoformat(),
    ]
    opened = await any_store.list_events(event_type="session_opened")
    assert [item.session_id for item in opened] == [sessions[0].id, sessions[1].id]


async def test_multi_owner_reconciliation_has_one_canonical_order(
    any_store, monkeypatch
):
    """C2: malformed multi-owner facts reconcile deterministically by owner id."""

    session, _candidate = await _held(any_store)
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
    foreign_owner_id = "000-wo0113-foreign-owner"
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.ENVELOPE_ACTION,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            order_id=order.id,
            correlation_id=foreign_owner_id,
            payload={"action": "hostile-multi-owner"},
        )
    )

    calls: list[str] = []
    if hasattr(any_store, "_reconcile_envelope_owner_unlocked"):
        monkeypatch.setattr(
            any_store,
            "_reconcile_envelope_owner_unlocked",
            lambda intent_id, *, now=None: calls.append(intent_id),
        )
        any_store._reconcile_envelope_owners_for_order_unlocked(order.id)
    else:

        def _spy(_cur, intent_id, *, now=None):
            calls.append(intent_id)

        monkeypatch.setattr(any_store, "_reconcile_envelope_owner_locked", _spy)
        with any_store._tx() as cur:
            any_store._reconcile_envelope_owners_for_order_locked(cur, order.id)

    assert calls == sorted({owner.id, foreign_owner_id})
