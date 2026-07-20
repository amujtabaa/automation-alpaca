"""WO-0113 accepted-submit identity, multiplicity, and bounded-selection pins."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    ACCEPTED_SUBMIT_UNPERSISTED_REASON,
    RECOVERY_RESOLVED,
    CandidateStatus,
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntent,
    SellIntentStatus,
    SellReason,
)
from app.monitoring import (
    _repair_unpersisted_submit_audits,
    _submit_pending_orders,
)
from app.store.base import (
    CLAIM_BLOCKED,
    RiskLimitBlockedError,
    RiskLimits,
    SellIntentTransitionError,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


async def _new_buy(
    store: Any,
    *,
    symbol: str = "AAPL",
    quantity: int = 10,
    price: float = 10.0,
) -> Order:
    candidate = await store.create_candidate(
        symbol,
        suggested_quantity=quantity,
        suggested_limit_price=price,
    )
    return await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        limit_price=price,
        session_id=candidate.session_id,
    )


async def _approved_buy_candidate(
    store: Any,
    *,
    symbol: str,
    quantity: int,
    price: float,
):
    candidate = await store.create_candidate(
        symbol,
        suggested_quantity=quantity,
        suggested_limit_price=price,
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return candidate


async def _terminal_buy_with_fill(store: Any, *, filled_quantity: int = 4) -> Order:
    order = await _new_buy(store)
    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == "claimed"
    if filled_quantity:
        await store.append_fill(
            order.id,
            order.symbol,
            OrderSide.BUY,
            filled_quantity,
            10.0,
            source_fill_id=f"accepted-identity-fill-{order.id}",
        )
    await store.transition_order(order.id, OrderStatus.CANCELED)
    return order


def _accepted_event(
    order: Order,
    broker_order_id: str,
    *,
    event_id: str,
    quantity: int | None = None,
    price: float | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        id=event_id,
        event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=(f"accepted_submit_unpersisted:{order.id}:{broker_order_id}"),
        ts_init=_NOW,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity if quantity is None else quantity,
        price=order.limit_price if price is None else price,
        order_id=order.id,
        session_id=order.session_id,
        correlation_id=order.sell_intent_id or order.candidate_id,
        payload={
            "reason": ACCEPTED_SUBMIT_UNPERSISTED_REASON,
            "broker_order_id": broker_order_id,
            "error": "injected accepted-submit persistence failure",
        },
    )


async def _poison_legacy_recovery_numeric_scope(
    store: Any,
    order: Order,
    *,
    field: str,
) -> None:
    recovery = await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"legacy-recovery-{field}-{order.id}",
        client_order_id=order.id,
        symbol=order.symbol,
        side=OrderSide.BUY,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason="legacy accepted-submit recovery",
        session_id=order.session_id,
        candidate_id=order.candidate_id,
    )
    update = {"quantity": 1} if field == "quantity" else {"limit_price": 1.0}
    poisoned = recovery.model_copy(update=update)
    if isinstance(store, InMemoryStateStore):
        store._submit_recoveries = [
            poisoned if item.id == recovery.id else item
            for item in store._submit_recoveries
        ]
        store._index_submit_recovery_unlocked(poisoned)
        return
    assert isinstance(store, SqliteStateStore)
    if field == "quantity":
        store._connect().execute(
            "UPDATE submit_recoveries SET quantity = ? WHERE id = ?",
            (1, recovery.id),
        )
    else:
        store._connect().execute(
            "UPDATE submit_recoveries SET limit_price = ? WHERE id = ?",
            (1.0, recovery.id),
        )


@pytest.mark.parametrize("owner_kind", ["unknown", "legacy_recovery"])
@pytest.mark.parametrize("field", ["quantity", "price"])
async def test_malformed_numeric_owner_cannot_undercount_referenced_buy(
    any_store: Any,
    owner_kind: str,
    field: str,
) -> None:
    """Immutable order scope outranks a smaller malformed accepted-owner scope."""

    await any_store.initialize()
    order = await _terminal_buy_with_fill(any_store)
    if owner_kind == "unknown":
        await any_store.append_execution_event(
            _accepted_event(
                order,
                f"malformed-{field}-{order.id}",
                event_id=f"malformed-{field}-unknown",
                quantity=1 if field == "quantity" else None,
                price=1.0 if field == "price" else None,
            )
        )
    else:
        await _poison_legacy_recovery_numeric_scope(
            any_store,
            order,
            field=field,
        )

    # Four filled shares contribute $40.  The one accepted venue order still
    # owns the immutable six-share remainder at $10, for $100 total exposure.
    assert await any_store.current_exposure() == 100.0

    candidate = await _approved_buy_candidate(
        any_store,
        symbol="MSFT",
        quantity=6,
        price=10.0,
    )
    with pytest.raises(RiskLimitBlockedError, match="exceeds_max_total_exposure"):
        await any_store.create_order_for_candidate(
            candidate.id,
            risk_limits=RiskLimits(max_total_exposure=150.0),
        )


async def test_distinct_broker_acceptances_for_one_order_are_distinct_exposure(
    any_store: Any,
) -> None:
    """Two venue acceptances are additive; one local fill allocation is not."""

    await any_store.initialize()
    order = await _terminal_buy_with_fill(any_store)
    for occurrence in (1, 2):
        broker_id = f"distinct-acceptance-{occurrence}-{order.id}"
        await any_store.append_execution_event(
            _accepted_event(
                order,
                broker_id,
                event_id=f"distinct-acceptance-event-{occurrence}",
            )
        )

    # The venue may hold 20 accepted shares.  Allocate the four recorded fills
    # once across that aggregate: $40 position + $160 remaining = $200, not
    # $100 (collapse by local id) or $160 (subtract the fill from both owners).
    assert await any_store.current_exposure() == 200.0

    candidate = await _approved_buy_candidate(
        any_store,
        symbol="MSFT",
        quantity=6,
        price=10.0,
    )
    with pytest.raises(RiskLimitBlockedError, match="exceeds_max_total_exposure"):
        await any_store.create_order_for_candidate(
            candidate.id,
            risk_limits=RiskLimits(max_total_exposure=250.0),
        )


async def test_distinct_recovery_resolution_releases_only_its_exact_accepted_leg(
    any_store: Any,
) -> None:
    """Resolved history represents one pair without hiding its live sibling."""

    await any_store.initialize()
    order = await _terminal_buy_with_fill(any_store)
    broker_ids = [f"resolved-leg-a-{order.id}", f"resolved-leg-b-{order.id}"]
    recoveries = []
    for index, broker_id in enumerate(broker_ids):
        await any_store.append_execution_event(
            _accepted_event(
                order,
                broker_id,
                event_id=f"resolved-leg-event-{index}-{order.id}",
            )
        )
        recoveries.append(
            await any_store.create_submit_recovery(
                local_order_id=order.id,
                broker_order_id=broker_id,
                client_order_id=order.id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                limit_price=order.limit_price,
                failure_reason=f"accepted leg {index} needs recovery",
                session_id=order.session_id,
                candidate_id=order.candidate_id,
            )
        )

    assert await any_store.current_exposure() == 200.0
    await any_store.update_submit_recovery(
        recoveries[0].id, cleanup_status=RECOVERY_RESOLVED
    )
    assert await any_store.current_exposure() == 100.0
    await any_store.update_submit_recovery(
        recoveries[1].id, cleanup_status=RECOVERY_RESOLVED
    )
    assert await any_store.current_exposure() == 40.0


async def _produce_whitespace_fallback(
    store: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MockBrokerAdapter, Order, Exception | None]:
    order = await _new_buy(store)
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order
    real_create_recovery = store.create_submit_recovery
    raw_broker_id = "  Paper-Opaque_ID:42  "

    async def accept_then_cancel(submitted: Order, *, venue_scope) -> str:
        await real_submit(submitted, venue_scope=venue_scope)
        await store.transition_order(submitted.id, OrderStatus.CANCELED)
        return raw_broker_id

    async def fail_recovery(**_kwargs: Any) -> None:
        raise RuntimeError("injected recovery-ledger failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery)
    error: Exception | None = None
    try:
        await _submit_pending_orders(store, adapter, Settings())
    except Exception as exc:  # noqa: BLE001 - inspect the mandatory fallback owner
        error = exc
    finally:
        monkeypatch.setattr(store, "create_submit_recovery", real_create_recovery)
    return adapter, order, error


async def test_whitespace_broker_identity_is_canonical_from_fallback_to_repair(
    any_store: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Producer, fallback, repair, and resubmit rail share one opaque identity."""

    await any_store.initialize()
    adapter, order, error = await _produce_whitespace_fallback(any_store, monkeypatch)
    canonical_id = "Paper-Opaque_ID:42"
    fallback = next(
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == order.id
        and event.payload.get("reason") == ACCEPTED_SUBMIT_UNPERSISTED_REASON
    )
    assert fallback.payload["broker_order_id"] == canonical_id
    assert fallback.dedupe_key == (
        f"accepted_submit_unpersisted:{order.id}:{canonical_id}"
    )

    await _repair_unpersisted_submit_audits(any_store)
    assert [
        (record.local_order_id, record.broker_order_id)
        for record in await any_store.list_submit_recoveries()
        if record.local_order_id == order.id
    ] == [(order.id, canonical_id)]
    await _submit_pending_orders(any_store, adapter, Settings())
    assert len(adapter.submitted) == 1
    assert isinstance(error, RuntimeError)
    assert "durable uncertainty" in str(error)


async def test_sqlite_restart_preserves_whitespace_acceptance_identity(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The producer's canonical opaque broker id survives restart and repair."""

    database = tmp_path / "whitespace-acceptance.db"
    store = SqliteStateStore(database)
    await store.initialize()
    adapter, order, error = await _produce_whitespace_fallback(store, monkeypatch)
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        await _repair_unpersisted_submit_audits(reopened)
        canonical_id = "Paper-Opaque_ID:42"
        fallback = next(
            event
            for event in await reopened.get_execution_events()
            if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
            and event.order_id == order.id
            and event.payload.get("reason") == ACCEPTED_SUBMIT_UNPERSISTED_REASON
        )
        assert fallback.payload["broker_order_id"] == canonical_id
        assert fallback.dedupe_key == (
            f"accepted_submit_unpersisted:{order.id}:{canonical_id}"
        )
        assert [
            (record.local_order_id, record.broker_order_id)
            for record in await reopened.list_submit_recoveries()
            if record.local_order_id == order.id
        ] == [(order.id, canonical_id)]

        await _submit_pending_orders(reopened, adapter, Settings())
        assert len(adapter.submitted) == 1
        assert isinstance(error, RuntimeError)
        assert "durable uncertainty" in str(error)
    finally:
        await reopened.close()


async def _seed_held_position(store: Any) -> None:
    establishing = await _new_buy(store, quantity=20)
    await store.append_fill(
        establishing.id,
        establishing.symbol,
        OrderSide.BUY,
        20,
        10.0,
        source_fill_id=f"held-position-{establishing.id}",
    )
    await store.transition_order(establishing.id, OrderStatus.CANCELED)
    assert establishing.candidate_id is not None
    await store.transition_candidate(
        establishing.candidate_id,
        CandidateStatus.EXPIRED,
    )


async def _new_created_order(store: Any, side: OrderSide) -> Order:
    if side is OrderSide.BUY:
        return await _new_buy(store)
    await _seed_held_position(store)
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.MANUAL_FLATTEN,
        target_quantity=10,
    )
    await store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    return await store.create_order_for_sell_intent(
        intent.id,
        order_type=OrderType.LIMIT,
        limit_price=10.0,
    )


def _raw_insert_direct_exit(store: Any, intent: SellIntent, order: Order) -> None:
    """Bypass the earlier mint rails to exercise the final claim choke."""

    if isinstance(store, InMemoryStateStore):
        store._sell_intents[intent.id] = intent
        store._orders[order.id] = order
        return
    assert isinstance(store, SqliteStateStore)
    with store._tx() as cur:
        store._insert_sell_intent(cur, intent)
        store._insert_order(cur, order)


async def _append_local_cancel_projection(store: Any, order: Order) -> None:
    """Model a sibling local-cancel bug without invoking the guard under test."""

    await store.append_execution_event(
        ExecutionEvent(
            id=f"local-cancel-projection-{order.id}",
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=f"local-cancel-projection:{order.id}",
            ts_event=_NOW,
            ts_init=_NOW,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.limit_price,
            order_id=order.id,
            session_id=order.session_id,
            correlation_id=order.sell_intent_id,
            payload={"reason": "adversarial local cancel after broker acceptance"},
        )
    )


async def test_accepted_direct_sell_cannot_be_canceled_as_local_created(
    any_store: Any,
) -> None:
    """An accepted-submit fallback is venue identity, not local-only CREATED."""

    await any_store.initialize()
    order = await _new_created_order(any_store, OrderSide.SELL)
    await any_store.append_execution_event(
        _accepted_event(
            order,
            f"accepted-direct-cancel-{order.id}",
            event_id="accepted-direct-cancel-event",
        )
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
    assert (
        [
            event
            for event in after
            if event.order_id == order.id
            and event.event_type is ExecutionEventType.CANCELED
        ]
        == [
            event
            for event in before
            if event.order_id == order.id
            and event.event_type is ExecutionEventType.CANCELED
        ]
        == []
    )


@pytest.mark.parametrize("entrypoint", ["mint", "claim"])
async def test_accepted_direct_sell_retains_single_flight_after_local_terminal_fact(
    any_store: Any,
    entrypoint: str,
) -> None:
    """A local terminal fact cannot erase an accepted direct SELL at later rails."""

    await any_store.initialize()
    accepted = await _new_created_order(any_store, OrderSide.SELL)
    await any_store.append_execution_event(
        _accepted_event(
            accepted,
            f"accepted-direct-single-flight-{accepted.id}",
            event_id=f"accepted-direct-single-flight-{entrypoint}",
        )
    )
    await _append_local_cancel_projection(any_store, accepted)
    assert (await any_store.get_order(accepted.id)).status is OrderStatus.CANCELED

    if entrypoint == "mint":
        before_intent_ids = {
            intent.id for intent in await any_store.list_sell_intents(symbol="AAPL")
        }
        before_order_ids = {order.id for order in await any_store.list_orders()}
        with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
            await any_store.create_sell_intent(
                symbol="AAPL",
                reason=SellReason.MANUAL_FLATTEN,
                target_quantity=10,
                session_id=accepted.session_id,
            )
        assert {
            intent.id for intent in await any_store.list_sell_intents(symbol="AAPL")
        } == before_intent_ids
        assert {order.id for order in await any_store.list_orders()} == before_order_ids
        return

    second_intent = SellIntent(
        id="second-direct-exit-intent",
        symbol="AAPL",
        reason=SellReason.MANUAL_FLATTEN,
        status=SellIntentStatus.APPROVED,
        target_quantity=10,
        session_id=accepted.session_id,
        created_at=_NOW,
        updated_at=_NOW,
        approved_at=_NOW,
    )
    second_order = Order(
        id="second-direct-exit-order",
        sell_intent_id=second_intent.id,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=10.0,
        status=OrderStatus.CREATED,
        session_id=accepted.session_id,
        created_at=_NOW,
        updated_at=_NOW,
    )
    _raw_insert_direct_exit(any_store, second_intent, second_order)

    claim = await any_store.claim_order_for_submission(second_order.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert accepted.id in (claim.reason or "")
    assert (await any_store.get_order(second_order.id)).status is OrderStatus.CREATED


async def _seed_own_venue_identity(
    store: Any,
    order: Order,
    owner_kind: str,
) -> None:
    broker_id = f"own-{owner_kind}-{order.id}"
    if owner_kind == "unknown":
        await store.append_execution_event(
            _accepted_event(
                order,
                broker_id,
                event_id=f"own-unknown-{order.side.value}",
            )
        )
        return
    if owner_kind == "recovery":
        await store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=broker_id,
            client_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason="same-order acceptance identity",
            session_id=order.session_id,
            candidate_id=order.candidate_id,
        )
        return
    assert owner_kind == "broker_id"
    if isinstance(store, InMemoryStateStore):
        stored = store._orders[order.id]
        store._orders[order.id] = stored.model_copy(
            update={"broker_order_id": broker_id}
        )
        return
    assert isinstance(store, SqliteStateStore)
    store._connect().execute(
        "UPDATE orders SET broker_order_id = ? WHERE id = ?",
        (broker_id, order.id),
    )


@pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
@pytest.mark.parametrize("owner_kind", ["broker_id", "unknown", "recovery"])
@pytest.mark.parametrize("entrypoint", ["claim", "submit_sweep"])
async def test_created_order_with_own_venue_identity_cannot_be_resubmitted(
    any_store: Any,
    side: OrderSide,
    owner_kind: str,
    entrypoint: str,
) -> None:
    """Projected CREATED is not claimable when its own acceptance already exists."""

    await any_store.initialize()
    order = await _new_created_order(any_store, side)
    await _seed_own_venue_identity(any_store, order, owner_kind)
    projected = await any_store.get_order(order.id)
    assert projected is not None
    assert projected.status is OrderStatus.CREATED

    if entrypoint == "claim":
        claim = await any_store.claim_order_for_submission(
            order.id,
            risk_limits=RiskLimits(max_total_exposure=10_000.0),
        )
        assert claim.outcome == "blocked"
        assert claim.order is None
    else:
        adapter = MockBrokerAdapter()
        await _submit_pending_orders(
            any_store,
            adapter,
            Settings(capi_max_total_exposure=10_000.0),
        )
        assert adapter.submitted == []

    after = await any_store.get_order(order.id)
    assert after is not None
    assert after.status is OrderStatus.CREATED


class _CountingBucket(list[ExecutionEvent]):
    def __init__(self, values: list[ExecutionEvent]) -> None:
        super().__init__(values)
        self.yielded = 0

    def __iter__(self) -> Iterator[ExecutionEvent]:
        for value in super().__iter__():
            self.yielded += 1
            yield value


async def _seed_cold_unknown_history(store: Any) -> None:
    for index in range(48):
        await store.append_execution_event(
            ExecutionEvent(
                id=f"historical-unknown-noise-{index}",
                event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
                source=EventSource.RECONCILIATION,
                authority=EventAuthority.SYNTHETIC,
                dedupe_key=f"historical-unknown-noise:{index}",
                ts_init=_NOW,
                symbol="NOISE",
                side=OrderSide.BUY,
                quantity=1,
                price=1.0,
                payload={"reason": "historical_non_submit_reconcile"},
            )
        )

    for index in range(4):
        order = await _new_buy(store, symbol="HIST", quantity=1, price=1.0)
        claim = await store.claim_order_for_submission(order.id)
        assert claim.outcome == "claimed"
        await store.transition_order(order.id, OrderStatus.CANCELED)
        broker_id = f"represented-history-{index}"
        await store.append_execution_event(
            _accepted_event(
                order,
                broker_id,
                event_id=f"represented-history-event-{index}",
            )
        )
        recovery = await store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=broker_id,
            client_order_id=order.id,
            symbol=order.symbol,
            side=OrderSide.BUY,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason="historical represented acceptance",
            session_id=order.session_id,
            candidate_id=order.candidate_id,
        )
        await store.update_submit_recovery(
            recovery.id,
            cleanup_status=RECOVERY_RESOLVED,
        )


def _instrument_unknown_materialization(
    store: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], int]:
    if isinstance(store, InMemoryStateStore):
        bucket = _CountingBucket(
            list(
                store._execution_events_by_type.get(
                    ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
                    (),
                )
            )
        )
        store._execution_events_by_type[
            ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        ] = bucket
        return lambda: bucket.yielded

    assert isinstance(store, SqliteStateStore)
    decoded = 0
    real_decode = store._execution_event

    def counted_decode(row: Any) -> ExecutionEvent:
        nonlocal decoded
        if row["event_type"] == ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED.value:
            decoded += 1
        return real_decode(row)

    monkeypatch.setattr(store, "_execution_event", counted_decode)
    return lambda: decoded


@pytest.mark.parametrize("consumer", ["cross_side", "capi"])
async def test_cold_unknown_history_is_not_materialized_on_hot_path(
    any_store: Any,
    monkeypatch: pytest.MonkeyPatch,
    consumer: str,
) -> None:
    """Unrelated/resolved UNKNOWN history stays off routine decision hot paths."""

    await any_store.initialize()
    await _seed_cold_unknown_history(any_store)
    decoded_count = _instrument_unknown_materialization(any_store, monkeypatch)

    if consumer == "capi":
        assert await any_store.current_exposure() == 0.0
    elif isinstance(any_store, InMemoryStateStore):
        assert (
            any_store._accepted_submit_uncertainty_ids_unlocked(
                "TARGET",
                side=OrderSide.BUY,
            )
            == ()
        )
    else:
        assert isinstance(any_store, SqliteStateStore)
        assert (
            any_store._accepted_submit_uncertainty_ids_locked(
                "TARGET",
                side=OrderSide.BUY,
            )
            == ()
        )

    # A bounded selector may inspect the small active/relevant frontier; it may
    # not decode or materialize the 48 unrelated plus four represented rows.
    assert decoded_count() <= 4
