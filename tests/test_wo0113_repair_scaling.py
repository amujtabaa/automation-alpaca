"""WO-0113 bounded repair cursors and selective store-read performance pins."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models import (
    ACCEPTED_SUBMIT_UNPERSISTED_REASON,
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
)
from app.monitoring import (
    _repair_unattributed_envelope_fills,
    _repair_unpersisted_submit_audits,
)
from app.store.base import InvalidFillError, StoreError
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 19, 18, 0, tzinfo=UTC)
REPAIR_BATCH_SIZE = 256


def _irrelevant_execution_event(index: int) -> ExecutionEvent:
    return ExecutionEvent(
        id=f"wo0113-repair-irrelevant-{index}",
        event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
        source=EventSource.RECONCILIATION,
        authority=EventAuthority.SYNTHETIC,
        dedupe_key=f"wo0113-repair-irrelevant:{index}",
        ts_event=NOW,
        ts_init=NOW,
        payload={"reason": "unrelated repair fact", "index": index},
    )


async def test_attribution_repair_batches_and_leaves_poison_stationary(
    any_store, monkeypatch
):
    """Clean pages advance, but the first failing page is retried in place."""

    await any_store.initialize()
    clean = [
        await any_store.append_execution_event(_irrelevant_execution_event(index))
        for index in range(300)
    ]
    poison = await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-repair-poison-marker",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key="wo0113-repair-poison-marker",
            ts_event=NOW,
            ts_init=NOW,
            envelope_id="missing-envelope",
            payload={"fill_dedupe_key": "missing-canonical-fill"},
        )
    )
    real_get_events = any_store.get_execution_events
    reads: list[tuple[int, int | None]] = []

    async def observed_get_events(*, after_sequence=0, limit=None):
        reads.append((after_sequence, limit))
        return await real_get_events(after_sequence=after_sequence, limit=limit)

    monkeypatch.setattr(any_store, "get_execution_events", observed_get_events)

    for _ in range(2):
        with pytest.raises(InvalidFillError, match="does not name one canonical FILL"):
            await _repair_unattributed_envelope_fills(any_store)
        checkpoint = await any_store.get_latest_execution_event(
            ExecutionEventType.ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT
        )
        assert checkpoint is not None
        assert checkpoint.payload["up_to_sequence"] == clean[255].sequence
        assert checkpoint.payload["up_to_sequence"] < poison.sequence

    assert reads
    assert all(limit == REPAIR_BATCH_SIZE for _after, limit in reads)
    assert reads[-1][0] == clean[255].sequence


async def test_accepted_submit_repair_pages_audits_from_durable_cursor(
    any_store, monkeypatch
):
    """Unrelated audit history is read once in bounded global-log pages."""

    await any_store.initialize()
    for index in range(300):
        await any_store.append_event(
            "wo0113_unrelated_audit",
            payload={"index": index},
        )

    real_page = any_store.get_audit_event_page
    reads: list[tuple[int, int]] = []

    async def observed_page(*, after_cursor: int, limit: int):
        reads.append((after_cursor, limit))
        return await real_page(after_cursor=after_cursor, limit=limit)

    async def legacy_full_scan_forbidden(*_args, **_kwargs):
        raise AssertionError("accepted-submit repair used legacy full audit scan")

    monkeypatch.setattr(any_store, "get_audit_event_page", observed_page)
    monkeypatch.setattr(any_store, "list_events", legacy_full_scan_forbidden)

    await _repair_unpersisted_submit_audits(any_store)
    first_run_calls = len(reads)
    await _repair_unpersisted_submit_audits(any_store)

    assert first_run_calls >= 2
    assert all(limit == REPAIR_BATCH_SIZE for _after, limit in reads)
    assert reads[first_run_calls][0] >= 301  # session_opened + 300 fixtures
    checkpoint = await any_store.get_latest_execution_event(
        ExecutionEventType.SUBMIT_ACCEPTANCE_REPAIR_CHECKPOINT
    )
    assert checkpoint is not None
    assert checkpoint.payload["audit_cursor"] >= 301


async def test_accepted_submit_repair_uses_selective_identity_reads(
    any_store, monkeypatch
):
    """One fallback does not materialize the complete orders/recovery tables."""

    await any_store.initialize()
    session = await any_store.get_current_session()
    candidate = await any_store.create_candidate(
        "AAPL",
        suggested_quantity=10,
        suggested_limit_price=10.0,
        session_id=session.id,
    )
    order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
        session_id=session.id,
    )
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.order is not None
    broker_order_id = "broker-selective-repair"
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-selective-accepted-submit",
            event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=(f"accepted_submit_unpersisted:{order.id}:{broker_order_id}"),
            ts_init=NOW,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.limit_price,
            order_id=order.id,
            session_id=order.session_id,
            correlation_id=order.candidate_id,
            payload={
                "reason": ACCEPTED_SUBMIT_UNPERSISTED_REASON,
                "broker_order_id": broker_order_id,
            },
        )
    )

    async def full_table_read_forbidden(*_args, **_kwargs):
        raise AssertionError("accepted-submit repair materialized a complete table")

    monkeypatch.setattr(any_store, "list_orders", full_table_read_forbidden)
    monkeypatch.setattr(any_store, "list_submit_recoveries", full_table_read_forbidden)

    await _repair_unpersisted_submit_audits(any_store)

    repaired = await any_store.get_order(order.id)
    assert repaired is not None
    assert repaired.status is OrderStatus.SUBMITTED
    assert repaired.broker_order_id == broker_order_id


async def test_uncertainty_hot_path_early_returns_without_unrelated_table_reads(
    any_store,
):
    """No uncertainty fact means no order/recovery scan on either backend."""

    await any_store.initialize()
    if isinstance(any_store, InMemoryStateStore):

        class NoIteration(list):
            def __iter__(self):
                raise AssertionError("uncertainty helper scanned the execution log")

        original = any_store._execution_events
        any_store._execution_events = NoIteration(original)
        try:
            found = any_store._accepted_submit_uncertainty_ids_unlocked(
                "AAPL", side=OrderSide.BUY
            )
        finally:
            any_store._execution_events = original
        assert found == ()
        return

    statements: list[str] = []

    def trace(sql: str) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(" ".join(sql.lower().split()))

    connection = any_store._connect()
    connection.set_trace_callback(trace)
    try:
        found = any_store._accepted_submit_uncertainty_ids_locked(
            "AAPL", side=OrderSide.BUY
        )
    finally:
        connection.set_trace_callback(None)

    assert found == ()
    assert not any(" from orders" in sql for sql in statements)
    assert not any(" from submit_recoveries" in sql for sql in statements)


async def test_selective_store_read_apis_have_dual_store_semantics(any_store):
    """Repair lookup primitives are indexed/selective without backend drift."""

    await any_store.initialize()
    first = await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-selective-first",
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key="wo0113-selective:first",
            ts_init=NOW,
            order_id="order-selective",
        )
    )
    latest = await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-selective-latest",
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key="wo0113-selective:latest",
            ts_init=NOW,
            order_id="order-selective",
        )
    )
    await any_store.append_execution_event(_irrelevant_execution_event(999))

    assert (
        await any_store.get_execution_event_by_dedupe_key(first.dedupe_key)
    ) == first
    assert (
        await any_store.get_latest_execution_event(ExecutionEventType.CANCELED)
    ) == latest
    assert await any_store.get_order_execution_events("order-selective") == [
        first,
        latest,
    ]

    await any_store.append_event("wo0113-page-1")
    await any_store.append_event("wo0113-page-2")
    cursor, page = await any_store.get_audit_event_page(after_cursor=0, limit=2)
    assert cursor == 2
    assert len(page) == 2
    final_cursor, tail = await any_store.get_audit_event_page(
        after_cursor=cursor, limit=10
    )
    assert final_cursor >= cursor
    assert [event.event_type for event in page + tail][-2:] == [
        "wo0113-page-1",
        "wo0113-page-2",
    ]


async def test_memory_execution_id_index_is_constant_time_and_rollback_safe(
    monkeypatch,
):
    store = InMemoryStateStore()
    await store.initialize()
    existing = ExecutionEvent(
        id="wo0113-index-existing",
        event_type=ExecutionEventType.CANCELED,
        source=EventSource.BROKER_REST,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        ts_init=NOW,
    )
    await store.append_execution_event(existing)

    class NoIteration(list):
        def __iter__(self):
            raise AssertionError("duplicate-id guard scanned the execution log")

    original = store._execution_events
    store._execution_events = NoIteration(original)
    try:
        with pytest.raises(StoreError, match="event id"):
            store._append_execution_event_unlocked(existing)
    finally:
        store._execution_events = original

    attempts = 0

    def fail_once(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("injected post-append failure")

    monkeypatch.setattr(
        store, "_reconcile_envelope_owners_for_order_unlocked", fail_once
    )
    retried = ExecutionEvent(
        id="wo0113-index-rollback",
        event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
        source=EventSource.RECONCILIATION,
        authority=EventAuthority.SYNTHETIC,
        dedupe_key="wo0113-index:rollback",
        ts_init=NOW,
        order_id="missing-order",
        payload={"reason": "rollback pin"},
    )
    with pytest.raises(RuntimeError, match="post-append failure"):
        await store.append_execution_event(retried)

    assert retried.id not in store._execution_event_ids
    stored = await store.append_execution_event(retried)
    assert stored.id == retried.id
    assert retried.id in store._execution_event_ids


async def test_alternating_idle_repair_consumers_do_not_ping_pong_checkpoints(
    any_store,
):
    """Checkpoint-only tails converge instead of making each other look like work.

    A fresh SQLite instance exercises the durable restart path. In-memory repeats
    initialization on the same process-local store because it has no persistence
    contract across instances.
    """

    await any_store.initialize()

    async def idle_round(store) -> None:
        await _repair_unpersisted_submit_audits(store)
        await _repair_unattributed_envelope_fills(store)

    for _ in range(3):
        await idle_round(any_store)

    active_store = any_store
    reopened = None
    if isinstance(any_store, SqliteStateStore):
        assert any_store._conn is not None
        any_store._conn.close()
        any_store._conn = None
        reopened = SqliteStateStore(any_store._db_path)
        await reopened.initialize()
        active_store = reopened
    else:
        await active_store.initialize()

    try:
        checkpoint_types = {
            ExecutionEventType.ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT,
            ExecutionEventType.SUBMIT_ACCEPTANCE_REPAIR_CHECKPOINT,
        }
        before = [
            event
            for event in await active_store.get_execution_events()
            if event.event_type in checkpoint_types
        ]

        for _ in range(4):
            await idle_round(active_store)

        after = [
            event
            for event in await active_store.get_execution_events()
            if event.event_type in checkpoint_types
        ]
    finally:
        if reopened is not None and reopened._conn is not None:
            reopened._conn.close()
            reopened._conn = None

    assert [event.id for event in after] == [event.id for event in before]
