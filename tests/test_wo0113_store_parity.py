"""WO-0113 C2 distinguishing-state pins for store decision parity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys

import pytest

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_RESOLVED,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.events.projectors import project_order_status
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import (
    InvalidFillError,
    OrderTransitionError,
    RecoveryTransitionError,
    StoreError,
)
from app.store.core import overfill_quarantine_dedupe_key
from app.store.sqlite import SqliteStateStore

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
    bad_broker_id = "broker-json-bad"
    before_recoveries = len(await any_store.list_submit_recoveries())
    before_events = len(await any_store.list_events())

    with pytest.raises(StoreError, match="JSON"):
        await any_store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=bad_broker_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            failure_reason="wo0113 invalid json",
            session_id=order.session_id,
            extra_payload={"bad": {1, 2}},
        )
    assert len(await any_store.list_submit_recoveries()) == before_recoveries
    assert len(await any_store.list_events()) == before_events
    assert (
        await any_store.get_submit_recovery_by_identity(order.id, bad_broker_id) is None
    )

    retried = await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=bad_broker_id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        failure_reason="wo0113 valid retry after rollback",
        session_id=order.session_id,
        extra_payload={"good": True},
    )
    assert retried.broker_order_id == bad_broker_id


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
    if conflict == "same_broker_new_local":
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


async def test_submit_recovery_keeps_distinct_brokers_for_one_local_order(
    any_store,
):
    """Two concrete acceptances share scope but never collapse identity."""

    await any_store.initialize()
    order = await _recovery_order(any_store, "AAPL")
    kwargs = {
        "local_order_id": order.id,
        "client_order_id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "limit_price": order.limit_price,
        "failure_reason": "distinct accepted submit needs recovery",
        "session_id": order.session_id,
    }
    first = await any_store.create_submit_recovery(
        **kwargs, broker_order_id="broker-wo0113-distinct-one"
    )
    second = await any_store.create_submit_recovery(
        **kwargs, broker_order_id="broker-wo0113-distinct-two"
    )

    assert first.id != second.id
    assert [
        (item.local_order_id, item.broker_order_id)
        for item in await any_store.list_submit_recoveries()
    ] == [
        (order.id, "broker-wo0113-distinct-one"),
        (order.id, "broker-wo0113-distinct-two"),
    ]


async def test_broker_identity_is_canonical_and_exclusive_across_owner_kinds(
    any_store,
):
    """One canonical venue id may have several owners only for one local row."""

    await any_store.initialize()
    order_owner = await _recovery_order(any_store, "AAPL")
    owner_claim = await any_store.claim_order_for_submission(order_owner.id)
    assert owner_claim.order is not None
    stored_owner = await any_store.transition_order(
        order_owner.id,
        OrderStatus.SUBMITTED,
        broker_order_id="  shared-owner-broker  ",
    )
    assert stored_owner.broker_order_id == "shared-owner-broker"

    foreign = await _recovery_order(any_store, "MSFT")
    with pytest.raises(RecoveryTransitionError, match="broker identity"):
        await any_store.create_submit_recovery(
            local_order_id=foreign.id,
            broker_order_id="shared-owner-broker",
            client_order_id=foreign.id,
            symbol=foreign.symbol,
            side=foreign.side,
            quantity=foreign.quantity,
            limit_price=foreign.limit_price,
            failure_reason="foreign recovery must not alias order owner",
            session_id=foreign.session_id,
        )

    same_local = await any_store.create_submit_recovery(
        local_order_id=order_owner.id,
        broker_order_id="  shared-owner-broker  ",
        client_order_id=order_owner.id,
        symbol=order_owner.symbol,
        side=order_owner.side,
        quantity=order_owner.quantity,
        limit_price=order_owner.limit_price,
        failure_reason="same accepted leg may have overlapping local ownership",
        session_id=order_owner.session_id,
    )
    assert same_local.broker_order_id == "shared-owner-broker"

    recovery_owner = await _recovery_order(any_store, "GOOG")
    await any_store.create_submit_recovery(
        local_order_id=recovery_owner.id,
        broker_order_id="recovery-owned-broker",
        client_order_id=recovery_owner.id,
        symbol=recovery_owner.symbol,
        side=recovery_owner.side,
        quantity=recovery_owner.quantity,
        limit_price=recovery_owner.limit_price,
        failure_reason="recovery owns concrete broker identity",
        session_id=recovery_owner.session_id,
    )
    order_contender = await _recovery_order(any_store, "TSLA")
    contender_claim = await any_store.claim_order_for_submission(order_contender.id)
    assert contender_claim.order is not None
    with pytest.raises(OrderTransitionError, match="broker identity"):
        await any_store.transition_order(
            order_contender.id,
            OrderStatus.SUBMITTED,
            broker_order_id="  recovery-owned-broker  ",
        )


async def test_timeout_resolution_rejects_foreign_recovery_broker_identity(
    any_store,
):
    """Targeted quarantine resolution obeys the same global identity rail."""

    await any_store.initialize()
    recovery_owner = await _recovery_order(any_store, "AAPL")
    await any_store.create_submit_recovery(
        local_order_id=recovery_owner.id,
        broker_order_id="timeout-owned-broker",
        client_order_id=recovery_owner.id,
        symbol=recovery_owner.symbol,
        side=recovery_owner.side,
        quantity=recovery_owner.quantity,
        limit_price=recovery_owner.limit_price,
        failure_reason="recovery owns timeout identity",
        session_id=recovery_owner.session_id,
    )

    contender = await _recovery_order(any_store, "MSFT")
    claim = await any_store.claim_order_for_submission(contender.id)
    assert claim.order is not None
    await any_store.quarantine_timed_out_order(contender.id, reason="test")
    with pytest.raises(OrderTransitionError, match="broker identity"):
        await any_store.resolve_timeout_quarantine(
            contender.id,
            OrderStatus.SUBMITTED,
            broker_order_id="  timeout-owned-broker  ",
        )


async def test_submit_recovery_canonicalizes_broker_identity_at_boundary(any_store):
    """Padded aliases collapse and whitespace-only remains the empty sentinel."""

    await any_store.initialize()
    concrete = await _recovery_order(any_store, "AAPL")
    kwargs = {
        "local_order_id": concrete.id,
        "client_order_id": concrete.id,
        "symbol": concrete.symbol,
        "side": concrete.side,
        "quantity": concrete.quantity,
        "limit_price": concrete.limit_price,
        "failure_reason": "canonical recovery identity",
        "session_id": concrete.session_id,
    }
    first = await any_store.create_submit_recovery(
        **kwargs, broker_order_id="  venue-42  "
    )
    replay = await any_store.create_submit_recovery(
        **kwargs, broker_order_id="venue-42"
    )
    assert first.id == replay.id
    assert first.broker_order_id == "venue-42"

    unknown = await _recovery_order(any_store, "MSFT")
    whitespace = await any_store.create_submit_recovery(
        local_order_id=unknown.id,
        broker_order_id="   ",
        client_order_id=unknown.id,
        symbol=unknown.symbol,
        side=unknown.side,
        quantity=unknown.quantity,
        limit_price=unknown.limit_price,
        failure_reason="unknown recovery identity",
        session_id=unknown.session_id,
    )
    assert whitespace.broker_order_id == ""


async def test_sqlite_concrete_recovery_lookup_avoids_unindexed_global_scan(
    tmp_path,
):
    """Concrete identity enforcement stays O(1) without a schema migration."""

    store = SqliteStateStore(tmp_path / "recovery-identity-cache.db")
    await store.initialize()
    try:
        for index in range(24):
            await store.create_submit_recovery(
                local_order_id=f"unrelated-local-{index}",
                broker_order_id=f"unrelated-broker-{index}",
                client_order_id=f"unrelated-local-{index}",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=1,
                limit_price=10.0,
                failure_reason="unrelated accepted leg",
            )

        statements: list[str] = []
        connection = store._connect()

        def trace(sql: str) -> None:
            if sql.lstrip().upper().startswith("SELECT"):
                statements.append(sql)

        connection.set_trace_callback(trace)
        try:
            await store.create_submit_recovery(
                local_order_id="target-local",
                broker_order_id="target-broker",
                client_order_id="target-local",
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=1,
                limit_price=10.0,
                failure_reason="target accepted leg",
            )
        finally:
            connection.set_trace_callback(None)

        recovery_plans = [
            detail
            for statement in statements
            if "submit_recoveries" in statement.lower()
            for detail in (
                row[3]
                for row in connection.execute(
                    f"EXPLAIN QUERY PLAN {statement}"
                ).fetchall()
            )
        ]
        assert not any(
            detail.lower().startswith("scan submit_recoveries")
            for detail in recovery_plans
        ), recovery_plans
    finally:
        await store.close()


async def test_sqlite_restart_rebuilds_concrete_recovery_identity_cache(
    tmp_path,
):
    """Restart preserves exact replay and global concrete-id exclusivity."""

    path = tmp_path / "recovery-identity-restart.db"
    kwargs = {
        "local_order_id": "restart-local-one",
        "broker_order_id": "restart-concrete-broker",
        "client_order_id": "restart-local-one",
        "symbol": "AAPL",
        "side": OrderSide.BUY,
        "quantity": 1,
        "limit_price": 10.0,
        "failure_reason": "restart accepted leg",
    }
    first_store = SqliteStateStore(path)
    await first_store.initialize()
    first = await first_store.create_submit_recovery(**kwargs)
    await first_store.close()

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    try:
        replay = await reopened.create_submit_recovery(**kwargs)
        assert replay.id == first.id

        conflict = dict(kwargs)
        conflict.update(
            {
                "local_order_id": "restart-local-two",
                "client_order_id": "restart-local-two",
            }
        )
        with pytest.raises(
            RecoveryTransitionError,
            match="broker identity|conflicts with existing",
        ):
            await reopened.create_submit_recovery(**conflict)
        assert [record.id for record in await reopened.list_submit_recoveries()] == [
            first.id
        ]
    finally:
        await reopened.close()


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


async def _adr001_buy_order(store, *, quantity: int = 100):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )
    return session, order


async def test_broker_order_overfill_records_raw_truth_and_quarantine(any_store):
    """ADR-001: broker excess is truth even when position remains positive."""

    session, order = await _adr001_buy_order(any_store)
    result = await any_store.append_fill(
        order.id,
        "AAPL",
        OrderSide.BUY,
        150,
        10.0,
        source_fill_id="adr001-broker-overfill",
        session_id=session.id,
    )

    assert result.status == "appended"
    assert [
        fill.quantity for fill in await any_store.list_fills(order_id=order.id)
    ] == [150]
    assert (await any_store.get_position("AAPL")).quantity == 150
    assert await any_store.list_quarantined_symbols() == {"AAPL"}

    events = await any_store.get_execution_events()
    fills = [event for event in events if event.event_type is ExecutionEventType.FILL]
    quarantine = [
        event for event in events if event.event_type is ExecutionEventType.QUARANTINED
    ]
    assert len(fills) == 1
    assert len(quarantine) == 1
    assert quarantine[0].payload["order_overfill"] is True
    assert quarantine[0].payload["position_overfill"] is False
    assert quarantine[0].payload["manual_review_required"] is True
    assert project_order_status(events, order.id, order.quantity).filled_quantity == 100
    assert (await any_store.get_order(order.id)).filled_quantity == 100


@pytest.mark.parametrize(
    ("source", "authority"),
    [
        pytest.param(EventSource.ENGINE, EventAuthority.LOCAL, id="local"),
        pytest.param(
            EventSource.RECONCILIATION,
            EventAuthority.SYNTHETIC,
            id="synthetic",
        ),
    ],
)
async def test_non_broker_order_overfill_is_zero_truth_mutation(
    any_store,
    source,
    authority,
):
    """INV-4: inferred/local excess is rejected before durable fill truth."""

    session, order = await _adr001_buy_order(any_store)
    await any_store.append_fill(
        order.id,
        "AAPL",
        OrderSide.BUY,
        80,
        10.0,
        source_fill_id="adr001-first-fill",
        session_id=session.id,
    )
    before_fills = await any_store.list_fills(order_id=order.id)
    before_events = await any_store.get_execution_events()
    before_position = await any_store.get_position("AAPL")

    with pytest.raises(InvalidFillError, match="cumulative_exceeds_order_quantity"):
        await any_store.append_fill(
            order.id,
            "AAPL",
            OrderSide.BUY,
            30,
            10.0,
            source_fill_id=f"adr001-{authority.value}-excess",
            session_id=session.id,
            source=source,
            authority=authority,
        )

    assert await any_store.list_fills(order_id=order.id) == before_fills
    assert await any_store.get_execution_events() == before_events
    assert await any_store.get_position("AAPL") == before_position
    assert await any_store.list_quarantined_symbols() == set()


async def test_source_fill_identity_exact_replay_vs_economic_conflict(any_store):
    """INV-5: exact replay dedups; changed economics is reviewable conflict."""

    session, order = await _adr001_buy_order(any_store)
    kwargs = {
        "order_id": order.id,
        "symbol": "AAPL",
        "side": OrderSide.BUY,
        "quantity": 40,
        "price": 10.0,
        "source_fill_id": "adr001-stable-trade-id",
        "session_id": session.id,
    }
    assert (await any_store.append_fill(**kwargs)).status == "appended"
    assert (await any_store.append_fill(**kwargs)).status == "duplicate"

    for changed in (
        {"quantity": 41},
        {"price": 10.25},
        {"side": OrderSide.SELL},
    ):
        conflicting = dict(kwargs)
        conflicting.update(changed)
        assert (await any_store.append_fill(**conflicting)).status == "conflict"

    assert len(await any_store.list_fills(order_id=order.id)) == 1
    assert (await any_store.get_position("AAPL")).quantity == 40
    execution_events = await any_store.get_execution_events()
    assert (
        sum(event.event_type is ExecutionEventType.FILL for event in execution_events)
        == 1
    )
    conflicts = await any_store.list_events(event_type="fill_duplicate_conflict")
    assert len(conflicts) == 3
    assert all(event.payload["manual_review_required"] is True for event in conflicts)


def _adr001_envelope_draft(owner_id: str, session_id: str) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=owner_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.5,
        trail_distance_min=0.05,
        trail_distance_max=0.25,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=750,
        cancel_replace_budget=40,
        expires_at=DAY_ONE + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


async def _adr001_active_envelope(store, *, holding_quantity: int = 100):
    session, buy = await _adr001_buy_order(store, quantity=holding_quantity)
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        holding_quantity,
        10.0,
        source_fill_id=f"adr001-envelope-holding-{holding_quantity}",
        session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    owner = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await store.create_envelope(_adr001_envelope_draft(owner.id, session.id))
    await store.transition_envelope(envelope.id, EnvelopeStatus.APPROVED)
    await store.transition_envelope(envelope.id, EnvelopeStatus.ACTIVE)
    staged = await store.stage_envelope_action(
        envelope.id,
        PlannedAction(
            kind=ActionKind.SUBMIT,
            limit_price=9.9,
            quantity=100,
            regime=None,
            urgency=0.0,
            working_stop=9.5,
            atr=0.05,
            tranche=False,
            stop_triggered=False,
        ),
        snapshot_fingerprint=f"adr001:{envelope.id}",
        now=DAY_ONE,
    )
    assert staged.order is not None
    return session, envelope, staged.order


@pytest.mark.parametrize(
    ("source", "authority"),
    [
        pytest.param(EventSource.ENGINE, EventAuthority.LOCAL, id="local"),
        pytest.param(
            EventSource.RECONCILIATION,
            EventAuthority.SYNTHETIC,
            id="synthetic",
        ),
    ],
)
async def test_non_broker_envelope_overfill_has_zero_mutation_and_replay_is_exact(
    any_store,
    source,
    authority,
):
    session, envelope, order = await _adr001_active_envelope(any_store)

    before = await any_store.get_envelope(envelope.id)
    before_events = await any_store.get_execution_events()
    with pytest.raises(InvalidFillError, match="exceeds remaining quantity"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=101,
            dedupe_key=f"fill:{order.id}:non-broker-envelope-excess",
            price=9.9,
            session_id=session.id,
            source=source,
            authority=authority,
        )
    assert await any_store.get_envelope(envelope.id) == before
    assert await any_store.get_execution_events() == before_events

    source_fill_id = f"adr001-envelope-{authority.value}"
    dedupe_key = f"fill:{order.id}:{source_fill_id}"
    after = await any_store.record_envelope_fill(
        envelope.id,
        quantity=80,
        dedupe_key=dedupe_key,
        price=9.9,
        order_id=order.id,
        session_id=session.id,
        source=source,
        authority=authority,
    )
    assert after.remaining_quantity == 20
    assert (
        await any_store.append_fill(
            order.id,
            "AAPL",
            OrderSide.SELL,
            80,
            9.8,
            source_fill_id=source_fill_id,
            session_id=session.id,
            source=source,
            authority=authority,
        )
    ).status == "conflict"
    assert await any_store.list_fills(order_id=order.id) == []
    assert (
        await any_store.append_fill(
            order.id,
            "AAPL",
            OrderSide.SELL,
            80,
            9.9,
            source_fill_id=source_fill_id,
            session_id=session.id,
            source=source,
            authority=authority,
        )
    ).status == "appended"

    replay = await any_store.record_envelope_fill(
        envelope.id,
        quantity=80,
        dedupe_key=dedupe_key,
        price=9.9,
        order_id=order.id,
        session_id=session.id,
        source=source,
        authority=authority,
    )
    assert replay.remaining_quantity == 20

    before_events = await any_store.get_execution_events()
    with pytest.raises(InvalidFillError, match="cumulative_exceeds_order_quantity"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=30,
            dedupe_key=f"fill:{order.id}:non-broker-order-excess",
            price=9.8,
            order_id=order.id,
            session_id=session.id,
            source=source,
            authority=authority,
        )
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 20
    assert await any_store.get_execution_events() == before_events
    assert [
        fill.quantity for fill in await any_store.list_fills(order_id=order.id)
    ] == [80]


async def test_sqlite_restart_preserves_overfill_quarantine_and_conflict(tmp_path):
    path = tmp_path / "adr001-restart.db"
    first = SqliteStateStore(path)
    session, order = await _adr001_buy_order(first)
    result = await first.append_fill(
        order.id,
        "AAPL",
        OrderSide.BUY,
        150,
        10.0,
        source_fill_id="adr001-restart-fill",
        session_id=session.id,
    )
    assert result.status == "appended"
    await first.close()

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    try:
        assert await reopened.list_quarantined_symbols() == {"AAPL"}
        assert [
            fill.quantity for fill in await reopened.list_fills(order_id=order.id)
        ] == [150]
        assert (await reopened.get_position("AAPL")).quantity == 150
        assert (
            await reopened.append_fill(
                order.id,
                "AAPL",
                OrderSide.BUY,
                150,
                10.0,
                source_fill_id="adr001-restart-fill",
                session_id=session.id,
            )
        ).status == "duplicate"
        assert (
            await reopened.append_fill(
                order.id,
                "AAPL",
                OrderSide.BUY,
                150,
                10.25,
                source_fill_id="adr001-restart-fill",
                session_id=session.id,
            )
        ).status == "conflict"
        assert len(await reopened.list_fills(order_id=order.id)) == 1
        assert (await reopened.get_position("AAPL")).quantity == 150
        assert (
            len(await reopened.list_events(event_type="fill_duplicate_conflict")) == 1
        )
    finally:
        await reopened.close()


async def _seed_overfill_quarantine_poison(
    store,
    *,
    order_id: str,
    source_fill_id: str,
    side: OrderSide,
    quantity: int,
    price: float,
    session_id: str,
) -> tuple[str, str]:
    fill_key = f"fill:{order_id}:{source_fill_id}"
    quarantine_key = overfill_quarantine_dedupe_key(fill_key)
    await store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=quarantine_key,
            symbol="AAPL",
            side=side,
            quantity=quantity,
            price=price,
            order_id=order_id,
            session_id=session_id,
            payload={
                "fill_dedupe_key": fill_key,
                "side": side.value,
                "quantity": quantity,
                "price": price,
                "quarantined": True,
                "manual_review_required": True,
            },
        )
    )
    return fill_key, quarantine_key


async def test_record_first_broker_overfill_atomically_quarantines(any_store):
    """The envelope boundary closes containment before the fill-row bridge."""

    session, envelope, order = await _adr001_active_envelope(
        any_store, holding_quantity=200
    )
    source_fill_id = "adr001-record-first-overfill"
    fill_key = f"fill:{order.id}:{source_fill_id}"
    quarantine_key = overfill_quarantine_dedupe_key(fill_key)

    breached = await any_store.record_envelope_fill(
        envelope.id,
        quantity=110,
        dedupe_key=fill_key,
        price=9.9,
        order_id=order.id,
        session_id=session.id,
    )
    assert breached.status is EnvelopeStatus.BREACHED
    assert breached.remaining_quantity == 0
    assert await any_store.list_fills(order_id=order.id) == []
    assert (await any_store.get_position("AAPL")).quantity == 90
    assert await any_store.list_quarantined_symbols() == {"AAPL"}

    child_events = [
        event
        for event in await any_store.get_execution_events()
        if event.order_id == order.id
    ]
    assert (
        sum(event.event_type is ExecutionEventType.FILL for event in child_events) == 1
    )
    quarantines = [
        event
        for event in child_events
        if event.event_type is ExecutionEventType.QUARANTINED
    ]
    assert len(quarantines) == 1
    assert quarantines[0].dedupe_key == quarantine_key
    assert quarantines[0].payload["fill_dedupe_key"] == fill_key
    assert quarantines[0].payload["envelope_overfill"] is True
    assert quarantines[0].payload["order_overfill"] is True

    bridged = await any_store.append_fill(
        order.id,
        "AAPL",
        OrderSide.SELL,
        110,
        9.9,
        source_fill_id=source_fill_id,
        session_id=session.id,
    )
    assert bridged.status == "appended"
    child_events = [
        event
        for event in await any_store.get_execution_events()
        if event.order_id == order.id
    ]
    assert (
        sum(event.event_type is ExecutionEventType.FILL for event in child_events) == 1
    )
    assert (
        sum(
            event.event_type is ExecutionEventType.QUARANTINED for event in child_events
        )
        == 1
    )
    assert [
        fill.quantity for fill in await any_store.list_fills(order_id=order.id)
    ] == [110]
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_append_fill_rejects_poisoned_quarantine_identity(any_store):
    """A non-quarantine occupant cannot swallow containment after raw truth."""

    session, order = await _adr001_buy_order(any_store)
    source_fill_id = "adr001-poisoned-append"
    _fill_key, quarantine_key = await _seed_overfill_quarantine_poison(
        any_store,
        order_id=order.id,
        source_fill_id=source_fill_id,
        side=OrderSide.BUY,
        quantity=150,
        price=10.0,
        session_id=session.id,
    )
    before_execution = await any_store.get_execution_events()

    with pytest.raises(InvalidFillError, match="quarantine identity conflict"):
        await any_store.append_fill(
            order.id,
            "AAPL",
            OrderSide.BUY,
            150,
            10.0,
            source_fill_id=source_fill_id,
            session_id=session.id,
        )

    assert await any_store.list_fills(order_id=order.id) == []
    assert (await any_store.get_position("AAPL")).quantity == 0
    assert await any_store.get_execution_events() == before_execution
    assert await any_store.list_quarantined_symbols() == set()
    occupant = next(
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == quarantine_key
    )
    assert occupant.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
    assert (
        len(await any_store.list_events(event_type="fill_quarantine_identity_conflict"))
        == 1
    )


async def test_record_envelope_fill_rejects_poisoned_quarantine_identity(any_store):
    session, envelope, order = await _adr001_active_envelope(
        any_store, holding_quantity=200
    )
    source_fill_id = "adr001-poisoned-record-first"
    fill_key, _quarantine_key = await _seed_overfill_quarantine_poison(
        any_store,
        order_id=order.id,
        source_fill_id=source_fill_id,
        side=OrderSide.SELL,
        quantity=110,
        price=9.9,
        session_id=session.id,
    )
    before_envelope = await any_store.get_envelope(envelope.id)
    before_execution = await any_store.get_execution_events()
    before_position = await any_store.get_position("AAPL")

    with pytest.raises(InvalidFillError, match="quarantine identity conflict"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=110,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=session.id,
        )

    assert await any_store.get_envelope(envelope.id) == before_envelope
    assert await any_store.get_execution_events() == before_execution
    assert await any_store.get_position("AAPL") == before_position
    assert await any_store.list_fills(order_id=order.id) == []
    assert await any_store.list_quarantined_symbols() == set()


async def test_sqlite_restart_preserves_record_first_overfill_quarantine(tmp_path):
    path = tmp_path / "adr001-record-first-crash-gap.db"
    first = SqliteStateStore(path)
    session, envelope, order = await _adr001_active_envelope(
        first, holding_quantity=200
    )
    source_fill_id = "adr001-record-first-restart"
    fill_key = f"fill:{order.id}:{source_fill_id}"
    quarantine_key = overfill_quarantine_dedupe_key(fill_key)
    await first.record_envelope_fill(
        envelope.id,
        quantity=110,
        dedupe_key=fill_key,
        price=9.9,
        order_id=order.id,
        session_id=session.id,
    )
    await first.close()

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    try:
        assert (
            await reopened.get_envelope(envelope.id)
        ).status is EnvelopeStatus.BREACHED
        assert await reopened.list_fills(order_id=order.id) == []
        assert (await reopened.get_position("AAPL")).quantity == 90
        assert await reopened.list_quarantined_symbols() == {"AAPL"}
        quarantines = [
            event
            for event in await reopened.get_execution_events()
            if event.dedupe_key == quarantine_key
        ]
        assert len(quarantines) == 1
        assert quarantines[0].event_type is ExecutionEventType.QUARANTINED

        assert (
            await reopened.append_fill(
                order.id,
                "AAPL",
                OrderSide.SELL,
                110,
                9.9,
                source_fill_id=source_fill_id,
                session_id=session.id,
            )
        ).status == "appended"
        assert (
            sum(
                event.dedupe_key == quarantine_key
                for event in await reopened.get_execution_events()
            )
            == 1
        )
        assert (await reopened.get_position("AAPL")).quantity == 90
    finally:
        await reopened.close()


async def test_sqlite_restart_preserves_quarantine_poison_guard(tmp_path):
    path = tmp_path / "adr001-quarantine-poison-restart.db"
    first = SqliteStateStore(path)
    session, envelope, order = await _adr001_active_envelope(
        first, holding_quantity=200
    )
    source_fill_id = "adr001-poison-restart"
    fill_key, _quarantine_key = await _seed_overfill_quarantine_poison(
        first,
        order_id=order.id,
        source_fill_id=source_fill_id,
        side=OrderSide.SELL,
        quantity=110,
        price=9.9,
        session_id=session.id,
    )
    await first.close()

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    try:
        before_envelope = await reopened.get_envelope(envelope.id)
        before_execution = await reopened.get_execution_events()
        before_position = await reopened.get_position("AAPL")
        with pytest.raises(InvalidFillError, match="quarantine identity conflict"):
            await reopened.record_envelope_fill(
                envelope.id,
                quantity=110,
                dedupe_key=fill_key,
                price=9.9,
                order_id=order.id,
                session_id=session.id,
            )
        assert await reopened.get_envelope(envelope.id) == before_envelope
        assert await reopened.get_execution_events() == before_execution
        assert await reopened.get_position("AAPL") == before_position
        assert await reopened.list_fills(order_id=order.id) == []
        assert await reopened.list_quarantined_symbols() == set()
    finally:
        await reopened.close()
