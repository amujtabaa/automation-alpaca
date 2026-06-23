"""Fill dedup is keyed per-(order_id, source_fill_id) (Item 5 / F1).

Dedup was table-wide on source_fill_id, so two DIFFERENT orders reporting a fill
with the same source_fill_id string swallowed the second (defense-in-depth gap;
unreachable via the real adapter today, which namespaces ids by broker_order_id).
Now scoped per order; same-order replays are still ignored. Includes a migration
test that rebuilds an old DB carrying the column-level UNIQUE.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.models import CandidateStatus, OrderSide
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


async def _order_for(store, symbol, *, qty=100, limit=1.0):
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(candidate.id)


async def test_cross_order_same_source_fill_id_both_recorded(any_store):
    await any_store.initialize()
    order_a = await _order_for(any_store, "AAA")
    order_b = await _order_for(any_store, "BBB")

    res_a = await any_store.append_fill(
        order_a.id, "AAA", OrderSide.BUY, 100, 1.0, source_fill_id="X"
    )
    res_b = await any_store.append_fill(
        order_b.id, "BBB", OrderSide.BUY, 100, 1.0, source_fill_id="X"
    )

    # Same source_fill_id on DIFFERENT orders: both recorded, neither swallowed.
    assert res_a.status == "appended"
    assert res_b.status == "appended"
    assert (await any_store.get_position("AAA")).quantity == 100
    assert (await any_store.get_position("BBB")).quantity == 100


async def test_same_order_duplicate_source_fill_id_still_ignored(any_store):
    await any_store.initialize()
    order = await _order_for(any_store, "AAA")

    first = await any_store.append_fill(
        order.id, "AAA", OrderSide.BUY, 50, 1.0, source_fill_id="X"
    )
    replay = await any_store.append_fill(
        order.id, "AAA", OrderSide.BUY, 50, 1.0, source_fill_id="X"
    )

    assert first.status == "appended"
    assert replay.status == "duplicate"  # same-order replay still ignored
    assert (await any_store.get_position("AAA")).quantity == 50


async def test_migration_rebuilds_old_unique_fills_and_preserves_rows(tmp_path):
    # A pre-Item-5 DB: column-level UNIQUE on source_fill_id, and pre-D-007 (no
    # session_id column) to exercise both migrations composing.
    db = tmp_path / "old.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE fills (
            id             TEXT PRIMARY KEY,
            order_id       TEXT NOT NULL,
            symbol         TEXT NOT NULL,
            side           TEXT NOT NULL,
            quantity       INTEGER NOT NULL,
            price          REAL NOT NULL,
            source_fill_id TEXT UNIQUE,
            filled_at      TEXT NOT NULL,
            created_at     TEXT NOT NULL
        );
        INSERT INTO fills
            (id, order_id, symbol, side, quantity, price, source_fill_id,
             filled_at, created_at)
        VALUES
            ('f1', 'o1', 'AAA', 'buy', 100, 1.5, 'X',
             '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()

    store = SqliteStateStore(db)
    await store.initialize()  # runs _migrate
    try:
        # Existing row preserved through the rebuild.
        fills = await store.list_fills()
        assert len(fills) == 1
        assert fills[0].id == "f1"
        assert fills[0].source_fill_id == "X"
        assert fills[0].session_id is None  # session_id added by migration

        c = store._connect()
        table_sql = c.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='fills'"
        ).fetchone()[0]
        assert "UNIQUE" not in table_sql.upper()  # column UNIQUE dropped
        idx = c.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_fills_order_source'"
        ).fetchone()
        assert idx is not None  # composite dedup index present
    finally:
        await store.close()
