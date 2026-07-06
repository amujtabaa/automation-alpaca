"""SqliteStateStore: schema, persistence, atomic rollback, and parity.

This exercises the real on-disk implementation (a temp file), which is fine —
it's testing our storage code, not Alpaca, so it is not env-gated. Unit tests
elsewhere remain IO-free via the in-memory store.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.models import OrderSide
from app.position import NegativePositionError
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


async def _fresh(tmp_path):
    store = SqliteStateStore(tmp_path / "app.db")
    await store.initialize()
    return store


async def test_schema_creation_is_idempotent(tmp_path):
    path = tmp_path / "app.db"
    s1 = SqliteStateStore(path)
    await s1.initialize()
    await s1.initialize()  # second startup must not error
    await s1.add_watchlist_symbol("AAPL")
    await s1.close()
    assert path.exists()


async def test_data_survives_reopen(tmp_path):
    store = await _fresh(tmp_path)
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 200)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 2.0)
    await store.set_kill_switch(True)
    await store.close()

    # "Restart": a brand-new store over the same file.
    reopened = SqliteStateStore(tmp_path / "app.db")
    await reopened.initialize()
    position = await reopened.get_position("AAPL")
    assert position.quantity == 200
    assert position.average_price == pytest.approx(1.5)
    assert (await reopened.get_current_session()).kill_switch is True
    await reopened.close()


async def test_duplicate_fill_protection_in_sqlite(tmp_path):
    store = await _fresh(tmp_path)
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 100)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="x")
    dup = await store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 100, 9.0, source_fill_id="x"
    )
    assert dup.status == "duplicate"
    assert len(await store.list_fills(symbol="AAPL")) == 1
    await store.close()


async def test_oversell_rejected_in_sqlite(tmp_path):
    store = await _fresh(tmp_path)
    candidate = await store.create_candidate("AAPL")
    buy_order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 100)
    await store.append_fill(buy_order.id, "AAPL", OrderSide.BUY, 100, 1.0)
    # Sell through a side-matched order so the long-only guard is what rejects.
    sell_order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.SELL, 200)
    with pytest.raises(NegativePositionError):
        await store.append_fill(sell_order.id, "AAPL", OrderSide.SELL, 200, 1.0)
    assert (await store.get_position("AAPL")).quantity == 100
    # The rejection is persisted as an audit event (not silent), just like the
    # in-memory store.
    rejects = [
        e for e in await store.list_events()
        if e.event_type == "fill_rejected_negative_position"
    ]
    assert len(rejects) == 1
    await store.close()


async def test_multi_row_write_is_atomic_rolls_back(tmp_path):
    """If the audit-event write fails mid-transaction, the fill insert that
    shares the transaction must roll back too — all or nothing."""

    store = await _fresh(tmp_path)
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 100)

    original = store._insert_event

    def boom(*args, **kwargs):
        raise RuntimeError("simulated mid-transaction failure")

    store._insert_event = boom
    with pytest.raises(RuntimeError):
        await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0)
    store._insert_event = original  # restore

    # The fill row was rolled back with the failed event — nothing persisted.
    assert await store.list_fills(symbol="AAPL") == []
    assert (await store.get_position("AAPL")).quantity == 0
    await store.close()


async def test_position_snapshots_survive_restart(tmp_path):
    store = await _fresh(tmp_path)
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.5,
                            session_id=session.id)
    await store.close_session()
    await store.close()

    # "Restart": snapshots and the closed session must persist.
    reopened = SqliteStateStore(tmp_path / "app.db")
    await reopened.initialize()
    snaps = await reopened.list_position_snapshots(session.id)
    assert len(snaps) == 1
    assert snaps[0].quantity == 100
    assert snaps[0].average_price == pytest.approx(1.5)
    await reopened.close()


async def test_migration_adds_fills_session_id_to_old_db(tmp_path):
    # Simulate a database created before D-007 (fills has no session_id column).
    path = tmp_path / "old.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE fills (
               id TEXT PRIMARY KEY, order_id TEXT, symbol TEXT, side TEXT,
               quantity INTEGER, price REAL, source_fill_id TEXT,
               filled_at TEXT, created_at TEXT)"""
    )
    conn.commit()
    conn.close()

    store = SqliteStateStore(path)
    await store.initialize()  # _migrate must ALTER fills to add session_id
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 10)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 10, 1.0,
                            session_id="sess-x")
    fills = await store.list_fills(symbol="AAPL")
    assert fills[0].session_id == "sess-x"
    await store.close()
