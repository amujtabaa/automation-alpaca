"""Phase 7 — data model + schema migration.

Pins the order-origin XOR invariant and the SQLite `orders` table rebuild that
makes `candidate_id` nullable + adds `sell_intent_id` on a pre-Phase-7 database
(the design-review blocker: `CREATE TABLE IF NOT EXISTS` cannot relax a NOT NULL
column, and SQLite has no ALTER COLUMN, so an existing DB must be rebuilt).
"""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from app.models import Order, OrderSide, OrderType
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


# The pre-Phase-7 orders table: candidate_id NOT NULL, no sell_intent_id column.
_PRE_P7_ORDERS = """
CREATE TABLE orders (
    id                TEXT PRIMARY KEY,
    candidate_id      TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    side              TEXT NOT NULL,
    order_type        TEXT NOT NULL,
    quantity          INTEGER NOT NULL,
    limit_price       REAL,
    status            TEXT NOT NULL,
    filled_quantity   INTEGER NOT NULL DEFAULT 0,
    replaces_order_id TEXT,
    broker_order_id   TEXT,
    session_id        TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    submitted_at      TEXT,
    filled_at         TEXT,
    canceled_at       TEXT,
    rejected_at       TEXT
);
"""


async def test_orders_table_rebuilt_for_nullable_candidate_and_sell_intent():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # Simulate a pre-Phase-7 DB: the old orders table + one buy order row.
        conn = sqlite3.connect(path)
        conn.executescript(_PRE_P7_ORDERS)
        conn.execute(
            "INSERT INTO orders (id, candidate_id, symbol, side, order_type, "
            "quantity, status, created_at, updated_at) "
            "VALUES ('o1','c1','AAPL','buy','limit',10,'created',"
            "'2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')"
        )
        conn.commit()
        conn.close()

        # Pre-migration the column is NOT NULL and has no sell_intent_id.
        cols = _order_cols(path)
        assert "sell_intent_id" not in cols
        assert cols["candidate_id"]["notnull"] == 1

        # initialize() runs _migrate() → the orders table is rebuilt.
        store = SqliteStateStore(path)
        await store.initialize()
        try:
            cols = _order_cols(path)
            assert "sell_intent_id" in cols
            assert cols["candidate_id"]["notnull"] == 0  # now nullable

            # The pre-existing buy order survived, with sell_intent_id NULL.
            existing = await store.get_order("o1")
            assert existing is not None
            assert existing.candidate_id == "c1"
            assert existing.sell_intent_id is None
            assert existing.symbol == "AAPL"

            # A SELL order (candidate_id NULL, sell_intent_id set) now inserts —
            # this raised IntegrityError before the rebuild.
            sell = Order(
                sell_intent_id="si1",
                symbol="AAPL",
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=10,
            )
            store._insert_order(store._conn.cursor(), sell)
            store._conn.commit()
            fetched = await store.get_order(sell.id)
            assert fetched is not None
            assert fetched.candidate_id is None
            assert fetched.sell_intent_id == "si1"
            assert fetched.side is OrderSide.SELL
        finally:
            await store.close()
    finally:
        os.remove(path)


async def test_fresh_db_has_phase7_orders_schema():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        store = SqliteStateStore(path)
        await store.initialize()
        try:
            cols = _order_cols(path)
            assert "sell_intent_id" in cols
            assert cols["candidate_id"]["notnull"] == 0
            # The sell_intents table exists too.
            names = {
                r[0]
                for r in store._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert "sell_intents" in names
        finally:
            await store.close()
    finally:
        os.remove(path)


def _order_cols(path: str) -> dict:
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("PRAGMA table_info(orders)").fetchall()
        return {r[1]: {"notnull": r[3]} for r in rows}
    finally:
        conn.close()
