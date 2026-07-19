"""WO-0113 durable ownership whenever accepted-submit recovery cannot persist."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    CandidateStatus,
    EventAuthority,
    EventSource,
    EventType,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
)
from app.monitoring import (
    _record_accepted_submit_uncertainty,
    _repair_unpersisted_submit_audits,
    _submit_pending_orders,
)
from app.store.base import (
    OrderIntentBlockedError,
    RecoveryTransitionError,
    SellIntentTransitionError,
)
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


async def _held_position(store) -> None:
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        100,
        limit_price=10.0,
        session_id=session.id,
    )
    await store.append_fill(
        order.id,
        "AAPL",
        OrderSide.BUY,
        100,
        10.0,
        session_id=session.id,
    )
    await store.transition_order(order.id, OrderStatus.CANCELED)
    await store.transition_candidate(candidate.id, CandidateStatus.EXPIRED)


async def _accepted_sell_without_local_owner(store, monkeypatch):
    """Broker-accept a SELL while forcing both ordinary ownership writes to fail."""

    await _held_position(store)
    spare_buy_candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.MANUAL_FLATTEN,
        target_quantity=100,
    )
    await store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    sell = await store.create_order_for_sell_intent(
        intent.id,
        order_type=OrderType.LIMIT,
        limit_price=10.0,
    )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order

    async def accept_then_cancel_local(order):
        broker_id = await real_submit(order)
        await store.transition_order(order.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("injected accepted-submit audit failure")

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected accepted-submit recovery failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(store, "append_event", fail_audit)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError, match="durable uncertainty"):
        await _submit_pending_orders(store, adapter, Settings())

    fallback = next(
        event
        for event in await store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == sell.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    )
    assert fallback.side is OrderSide.SELL
    assert len(adapter.submitted) == 1
    return sell, fallback, spare_buy_candidate.id


async def _created_buy_claim(store, *, candidate_id=None):
    if candidate_id is None:
        candidate = await store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=10.0
        )
        candidate_id = candidate.id
    buy = await store.create_order_for_test(
        candidate_id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    return buy, await store.claim_order_for_submission(buy.id)


async def _accepted_order_with_audit_only(store, side, monkeypatch):
    """Persist the ordinary audit, but fail the recovery ownership write."""

    await _held_position(store)
    spare_buy_candidate_id = None
    if side is OrderSide.BUY:
        candidate = await store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=10.0
        )
        order = await store.create_order_for_test(
            candidate.id,
            "AAPL",
            OrderSide.BUY,
            10,
            limit_price=10.0,
        )
    else:
        spare_buy_candidate = await store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=10.0
        )
        spare_buy_candidate_id = spare_buy_candidate.id
        intent = await store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.MANUAL_FLATTEN,
            target_quantity=100,
        )
        await store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
        order = await store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.LIMIT,
            limit_price=10.0,
        )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order

    async def accept_then_cancel_local(submitted):
        broker_id = await real_submit(submitted)
        await store.transition_order(submitted.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected accepted-submit recovery failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError):
        await _submit_pending_orders(store, adapter, Settings())

    assert any(
        event.event_type == EventType.ORDER_SUBMIT_UNPERSISTED.value
        and event.order_id == order.id
        for event in await store.list_events()
    )
    fallback = [
        event
        for event in await store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == order.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    ]
    return order, fallback, spare_buy_candidate_id


async def test_double_persist_failure_keeps_accepted_buy_owned(any_store, monkeypatch):
    """An accepted BUY remains exposure when audit and recovery writes both fail."""

    await _held_position(any_store)
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    buy = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order
    real_append_event = any_store.append_event
    real_create_recovery = any_store.create_submit_recovery

    async def accept_then_cancel_local(order):
        broker_id = await real_submit(order)
        await any_store.transition_order(order.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("injected accepted-submit audit failure")

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected accepted-submit recovery failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(any_store, "append_event", fail_audit)
    monkeypatch.setattr(any_store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError):
        await _submit_pending_orders(any_store, adapter, Settings())

    accepted = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == buy.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    ]
    assert len(accepted) == 1
    assert accepted[0].source is EventSource.ENGINE
    assert accepted[0].authority is EventAuthority.LOCAL
    assert accepted[0].symbol == buy.symbol
    assert accepted[0].side is OrderSide.BUY
    broker_id = accepted[0].payload["broker_order_id"]

    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    with pytest.raises(SellIntentTransitionError, match="same-symbol BUY may execute"):
        await any_store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.MARKET,
        )

    monkeypatch.setattr(any_store, "append_event", real_append_event)
    monkeypatch.setattr(any_store, "create_submit_recovery", real_create_recovery)
    await _repair_unpersisted_submit_audits(any_store)

    recoveries = await any_store.list_submit_recoveries()
    assert [
        (record.local_order_id, record.broker_order_id)
        for record in recoveries
        if record.local_order_id == buy.id
    ] == [(buy.id, broker_id)]
    assert len(adapter.submitted) == 1


async def test_sqlite_restart_repairs_accepted_submit_uncertainty(
    tmp_path, monkeypatch
):
    """The last-write uncertainty owner survives a process restart."""

    database = tmp_path / "accepted-submit-uncertainty.db"
    store = SqliteStateStore(database)
    await _held_position(store)
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    buy = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order

    async def accept_then_cancel_local(order):
        broker_id = await real_submit(order)
        await store.transition_order(order.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("injected accepted-submit audit failure")

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected accepted-submit recovery failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(store, "append_event", fail_audit)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError, match="durable uncertainty"):
        await _submit_pending_orders(store, adapter, Settings())

    fallback = next(
        event
        for event in await store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == buy.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    )
    broker_id = fallback.payload["broker_order_id"]
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        await _repair_unpersisted_submit_audits(reopened)
        recoveries = await reopened.list_submit_recoveries()
        assert [
            (record.local_order_id, record.broker_order_id)
            for record in recoveries
            if record.local_order_id == buy.id
        ] == [(buy.id, broker_id)]
        assert len(adapter.submitted) == 1
    finally:
        await reopened.close()


async def test_double_persist_failure_keeps_accepted_sell_owned(any_store, monkeypatch):
    """An accepted SELL fallback blocks an opposite-side BUY claim on both stores."""

    sell, _fallback, candidate_id = await _accepted_sell_without_local_owner(
        any_store, monkeypatch
    )

    with pytest.raises(OrderIntentBlockedError, match="same-symbol exit may execute"):
        await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=10.0
        )
    buy, claim = await _created_buy_claim(any_store, candidate_id=candidate_id)

    assert claim.outcome == "blocked"
    assert claim.order is None
    assert claim.reason == f"same-symbol exit may execute ({sell.id})"
    assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED


async def test_sqlite_restart_keeps_accepted_sell_as_exit_exposure(
    tmp_path, monkeypatch
):
    """A SELL fallback still blocks BUY submission after a SQLite restart."""

    database = tmp_path / "accepted-sell-uncertainty.db"
    store = SqliteStateStore(database)
    sell, fallback, candidate_id = await _accepted_sell_without_local_owner(
        store, monkeypatch
    )
    broker_id = fallback.payload["broker_order_id"]
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        with pytest.raises(
            OrderIntentBlockedError, match="same-symbol exit may execute"
        ):
            await reopened.create_candidate(
                "AAPL", suggested_quantity=10, suggested_limit_price=10.0
            )
        buy, claim = await _created_buy_claim(reopened, candidate_id=candidate_id)

        assert claim.outcome == "blocked"
        assert claim.order is None
        assert claim.reason == f"same-symbol exit may execute ({sell.id})"
        assert (await reopened.get_order(buy.id)).status is OrderStatus.CREATED
        assert any(
            event.order_id == sell.id
            and event.payload.get("broker_order_id") == broker_id
            for event in await reopened.get_execution_events()
        )
    finally:
        await reopened.close()


@pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
async def test_audit_only_acceptance_still_gets_execution_uncertainty_owner(
    any_store, monkeypatch, side
):
    """The ordinary audit is diagnostic, not a substitute for an exposure owner."""

    accepted, fallback, candidate_id = await _accepted_order_with_audit_only(
        any_store, side, monkeypatch
    )

    assert len(fallback) == 1
    assert fallback[0].side is side
    if side is OrderSide.BUY:
        intent = await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
        )
        await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
        with pytest.raises(
            SellIntentTransitionError, match="same-symbol BUY may execute"
        ):
            await any_store.create_order_for_sell_intent(
                intent.id,
                order_type=OrderType.MARKET,
            )
    else:
        with pytest.raises(
            OrderIntentBlockedError, match="same-symbol exit may execute"
        ):
            await any_store.create_candidate(
                "AAPL", suggested_quantity=10, suggested_limit_price=10.0
            )
        assert candidate_id is not None
        buy, claim = await _created_buy_claim(any_store, candidate_id=candidate_id)
        assert claim.outcome == "blocked"
        assert claim.order is None
        assert claim.reason == f"same-symbol exit may execute ({accepted.id})"
        assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED


@pytest.mark.parametrize(
    "malformation",
    ["scope", "source", "authority", "dedupe"],
)
async def test_malformed_accepted_submit_truth_cannot_disappear_from_scope(
    any_store, malformation
):
    """Only canonical fallback truth may be released by a represented broker id."""

    await _held_position(any_store)
    reference_symbol = "MSFT" if malformation == "scope" else "AAPL"
    reference_side = OrderSide.SELL if malformation == "scope" else OrderSide.BUY
    candidate = await any_store.create_candidate(
        reference_symbol,
        suggested_quantity=10,
        suggested_limit_price=10.0,
    )
    referenced = await any_store.create_order_for_test(
        candidate.id,
        reference_symbol,
        reference_side,
        10,
        limit_price=10.0,
    )
    claim = await any_store.claim_order_for_submission(referenced.id)
    assert claim.order is not None
    broker_id = f"broker-{malformation}"
    await any_store.transition_order(
        referenced.id,
        OrderStatus.SUBMITTED,
        broker_order_id=broker_id,
    )
    await any_store.transition_order(referenced.id, OrderStatus.CANCELED)

    dedupe_key = f"accepted_submit_unpersisted:{referenced.id}:{broker_id}"
    await any_store.append_execution_event(
        ExecutionEvent(
            id=f"malformed-accepted-{malformation}",
            event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
            source=(
                EventSource.BROKER_REST
                if malformation == "source"
                else EventSource.ENGINE
            ),
            authority=(
                EventAuthority.SYNTHETIC
                if malformation == "authority"
                else EventAuthority.LOCAL
            ),
            dedupe_key=(
                f"wrong:{referenced.id}:{broker_id}"
                if malformation == "dedupe"
                else dedupe_key
            ),
            ts_init=datetime(2026, 7, 19, 12, tzinfo=UTC),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            price=10.0,
            order_id=referenced.id,
            session_id=referenced.session_id,
            payload={
                "reason": "accepted_submit_unpersisted",
                "broker_order_id": broker_id,
                "error": "forged fallback",
            },
        )
    )

    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    with pytest.raises(SellIntentTransitionError, match="same-symbol BUY may execute"):
        await any_store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.MARKET,
        )


async def test_fallback_dedupe_collision_validates_complete_immutable_scope(
    any_store,
):
    """A reserved dedupe collision cannot bless mismatched quantity truth."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    broker_id = f"broker-{order.id}"
    dedupe_key = f"accepted_submit_unpersisted:{order.id}:{broker_id}"
    await any_store.append_execution_event(
        ExecutionEvent(
            id="forged-accepted-submit-collision",
            event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=dedupe_key,
            ts_init=datetime(2026, 7, 19, 12, tzinfo=UTC),
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity + 1,
            price=order.limit_price,
            order_id=order.id,
            session_id=order.session_id,
            correlation_id=order.candidate_id,
            payload={
                "reason": "accepted_submit_unpersisted",
                "broker_order_id": broker_id,
                "error": "forged quantity",
            },
        )
    )
    with pytest.raises(RecoveryTransitionError, match="conflicting truth"):
        await _record_accepted_submit_uncertainty(
            any_store,
            order,
            broker_id,
            RuntimeError("injected accepted-submit recovery failure"),
        )

    collisions = [
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == dedupe_key
    ]
    assert len(collisions) == 1
    assert collisions[0].quantity == order.quantity + 1
