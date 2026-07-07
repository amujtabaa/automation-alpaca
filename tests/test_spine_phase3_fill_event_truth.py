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
from app.store.core import execution_event_for_fill
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_TS = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


def _reconciliation_fill_event(symbol, qty, price, key):
    """A FILL event that has NO fill-table row — the reconciliation-inferred
    fill path (Phase 4) and the mechanism proving position is event-derived."""
    return ExecutionEvent(
        event_type=ExecutionEventType.FILL,
        source=EventSource.RECONCILIATION,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        dedupe_key=key,
        ts_event=_TS,
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=qty,
        price=price,
        order_id="recon",
    )


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


# --------------------------------------------------------------------------- #
# Review BLOCKER regression: mixed prefix(no-event)/suffix(event) layout. The
# event-less fills are a PREFIX (pre-shadow), so a count/offset backfill
# mis-selects; the rebuild must reconstruct the whole FILL log in fill order.
# --------------------------------------------------------------------------- #
async def test_memory_backfill_rebuilds_mixed_prefix_suffix_layout():
    store = InMemoryStateStore()
    await store.initialize()
    session = await store.get_current_session()
    # 2 pre-shadow fills (rows, NO events) then 2 shadow fills (rows + events).
    for oid, sid in [("o1", "s1"), ("o2", "s2")]:
        store._fills.append(
            Fill(order_id=oid, symbol="AAPL", side=OrderSide.BUY, quantity=100,
                 price=1.0, source_fill_id=sid, session_id=session.id, filled_at=_TS)
        )
    for oid, sid in [("o3", "s3"), ("o4", "s4")]:
        f = Fill(order_id=oid, symbol="AAPL", side=OrderSide.BUY, quantity=100,
                 price=1.0, source_fill_id=sid, session_id=session.id, filled_at=_TS)
        store._fills.append(f)
        async with store._lock:
            with store._atomic():
                store._append_execution_event_unlocked(execution_event_for_fill(f))
    # Backfill must REBUILD (not skip the prefix): all 4 fills -> qty 400.
    async with store._lock:
        with store._atomic():
            store._backfill_fill_events_unlocked()
    assert (await store.get_position("AAPL")).quantity == 400
    assert len(await store.get_execution_events()) == 4


async def test_sqlite_backfill_rebuilds_mixed_prefix_suffix_layout(tmp_path):
    path = tmp_path / "mixed.db"
    store = SqliteStateStore(path)
    await store.initialize()
    session = await store.get_current_session()
    conn = store._connect()
    # 2 pre-shadow fills: rows only.
    for oid, sid in [("o1", "s1"), ("o2", "s2")]:
        conn.execute(
            "INSERT INTO fills (id, order_id, symbol, side, quantity, price, "
            "source_fill_id, session_id, filled_at, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (new_id(), oid, "AAPL", "buy", 100, 1.0, sid, session.id,
             _TS.isoformat(), _TS.isoformat()),
        )
    # 2 shadow fills: rows + matching FILL events (the suffix).
    for oid, sid in [("o3", "s3"), ("o4", "s4")]:
        f = Fill(order_id=oid, symbol="AAPL", side=OrderSide.BUY, quantity=100,
                 price=1.0, source_fill_id=sid, session_id=session.id, filled_at=_TS)
        conn.execute(
            "INSERT INTO fills (id, order_id, symbol, side, quantity, price, "
            "source_fill_id, session_id, filled_at, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f.id, oid, "AAPL", "buy", 100, 1.0, sid, session.id,
             _TS.isoformat(), _TS.isoformat()),
        )
    conn.commit()
    # Emit the 2 suffix events out-of-band so the log holds only the suffix.
    for oid, sid in [("o3", "s3"), ("o4", "s4")]:
        await store.append_execution_event(
            execution_event_for_fill(
                Fill(order_id=oid, symbol="AAPL", side=OrderSide.BUY, quantity=100,
                     price=1.0, source_fill_id=sid, session_id=session.id, filled_at=_TS)
            )
        )
    store._conn.close()
    store._conn = None

    # Reopen -> backfill must rebuild the whole FILL log in order -> qty 400.
    reopened = SqliteStateStore(path)
    await reopened.initialize()
    assert (await reopened.get_position("AAPL")).quantity == 400
    assert len(await reopened.get_execution_events()) == 4
    reopened._conn.close()
    reopened._conn = None


# --------------------------------------------------------------------------- #
# Review MEDIUM regression: symbol enumeration for exposure + close_session must
# read the event log, so an event-only (reconciliation) fill is counted and the
# two stores agree.
# --------------------------------------------------------------------------- #
async def test_current_exposure_enumerates_symbols_from_the_event_log(any_store):
    await any_store.initialize()
    await any_store.append_execution_event(
        _reconciliation_fill_event("AAPL", 100, 3.0, "fill:recon:r1")
    )
    # No fill-table row, but the event log has a 100-share AAPL position.
    assert await any_store.list_fills() == []
    assert await any_store.current_exposure() == pytest.approx(300.0)


async def test_close_session_snapshots_enumerate_from_the_event_log(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    await any_store.append_execution_event(
        _reconciliation_fill_event("AAPL", 100, 3.0, "fill:recon:r1")
    )
    await any_store.close_session(session.id)
    snapshots = await any_store.list_position_snapshots(session.id)
    assert [s.symbol for s in snapshots] == ["AAPL"]
    assert snapshots[0].quantity == 100
