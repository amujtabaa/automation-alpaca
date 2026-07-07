"""Spine v2 Phase 3 wave 3a-truth — fill ingestion flipped to `event_truth`.

Position is now derived from the append-only `ExecutionEvent` log, not the fill
table (a compatibility read-model). The whole existing position/fill corpus
staying green (characterization) proves the flip is behavior-preserving; these
tests prove the *truth actually moved*: a FILL event with no fill-table row still
changes position, and a store opened on pre-wave-3a fill rows backfills events at
init so position is not silently understated.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    Fill,
    OrderSide,
    new_id,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_TS = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


async def test_position_derives_from_the_event_log_not_the_fill_table(any_store):
    """Append a FILL ExecutionEvent directly (no fill-table row) and confirm it
    changes position — the event log is the Rule-7 source of truth now."""
    await any_store.initialize()
    event = ExecutionEvent(
        event_type=ExecutionEventType.FILL,
        source=EventSource.RECONCILIATION,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        dedupe_key="fill:oX:sX",
        ts_event=_TS,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=42,
        price=3.0,
        order_id="oX",
    )
    await any_store.append_execution_event(event)

    position = await any_store.get_position("AAPL")
    assert position.quantity == 42
    assert position.average_price == pytest.approx(3.0)
    # No fill-table row backs this position — the truth is the event log.
    assert await any_store.list_fills() == []
    assert [p.symbol for p in await any_store.list_positions()] == ["AAPL"]


async def test_memory_backfill_emits_events_for_preexisting_fills():
    """A store opened on pre-wave-3a fill rows (fills, no events) must backfill a
    FILL event per fill so position is not understated."""
    store = InMemoryStateStore()
    await store.initialize()
    session = await store.get_current_session()
    # Simulate a pre-wave-3a fill: a fill row with no ExecutionEvent.
    store._fills.append(
        Fill(order_id="o1", symbol="AAPL", side=OrderSide.BUY, quantity=100,
             price=2.0, source_fill_id="s1", session_id=session.id, filled_at=_TS)
    )
    assert await store.get_execution_events() == []
    assert (await store.get_position("AAPL")).quantity == 0  # no event yet

    # Re-run the init backfill (as reopening the store would).
    async with store._lock:
        with store._atomic():
            store._backfill_fill_events_unlocked()

    events = await store.get_execution_events()
    assert len(events) == 1
    assert events[0].dedupe_key == "fill:o1:s1"
    assert events[0].event_type is ExecutionEventType.FILL
    assert (await store.get_position("AAPL")).quantity == 100

    # Idempotent: a second backfill emits nothing more.
    async with store._lock:
        with store._atomic():
            store._backfill_fill_events_unlocked()
    assert len(await store.get_execution_events()) == 1


async def test_sqlite_backfill_emits_events_for_preexisting_fills(tmp_path):
    path = tmp_path / "orphan.db"
    store = SqliteStateStore(path)
    await store.initialize()
    session = await store.get_current_session()
    # Insert a fill row directly, bypassing append_fill (pre-wave-3a fill).
    conn = store._connect()
    conn.execute(
        """INSERT INTO fills
           (id, order_id, symbol, side, quantity, price, source_fill_id,
            session_id, filled_at, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (new_id(), "o1", "AAPL", "buy", 100, 2.0, "s1", session.id,
         _TS.isoformat(), _TS.isoformat()),
    )
    conn.commit()
    # Position reads the event log, which has no event for this fill yet.
    assert (await store.get_position("AAPL")).quantity == 0
    store._conn.close()
    store._conn = None

    # Reopen -> initialize() runs the backfill.
    reopened = SqliteStateStore(path)
    await reopened.initialize()
    assert (await reopened.get_position("AAPL")).quantity == 100
    events = await reopened.get_execution_events()
    assert len(events) == 1
    assert events[0].dedupe_key == "fill:o1:s1"

    # Idempotent across another reopen.
    reopened._conn.close()
    reopened._conn = None
    reopened2 = SqliteStateStore(path)
    await reopened2.initialize()
    assert len(await reopened2.get_execution_events()) == 1
    assert (await reopened2.get_position("AAPL")).quantity == 100
    reopened2._conn.close()
    reopened2._conn = None
