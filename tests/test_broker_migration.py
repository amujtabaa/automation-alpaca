"""``broker_order_id`` persistence + the idempotent SQLite migration.

Two concerns:

1. **Parity** — ``transition_order`` persists ``broker_order_id`` identically in
   both store implementations (``any_store``).
2. **Migration** — a SQLite database whose ``orders`` table predates the
   ``broker_order_id`` column (a pre-Phase-4 db) gains the column idempotently
   on ``initialize``, the same pattern already used for ``fills.session_id``.
"""

from __future__ import annotations

import sqlite3

import pytest

from app.models import CandidateStatus, OrderStatus
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


async def _ordered(store, *, symbol="AAPL", qty=10, limit=1.0):
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(candidate.id)


async def test_transition_persists_broker_order_id(any_store):
    await any_store.initialize()
    order = await _ordered(any_store)

    updated = await any_store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="alpaca-uuid-123"
    )
    assert updated.broker_order_id == "alpaca-uuid-123"

    # And it survives a fresh read (i.e. it was actually persisted, not just
    # returned).
    reread = await any_store.get_order(order.id)
    assert reread.broker_order_id == "alpaca-uuid-123"


# A pre-Phase-4 orders table: every current column EXCEPT broker_order_id.
_OLD_ORDERS_SCHEMA = """
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
    session_id        TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    submitted_at      TEXT,
    filled_at         TEXT,
    canceled_at       TEXT,
    rejected_at       TEXT
);
"""


async def test_migration_adds_broker_order_id_to_legacy_db(tmp_path):
    db_path = tmp_path / "legacy.db"

    # Hand-build a database whose orders table lacks broker_order_id.
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_OLD_ORDERS_SCHEMA)
    conn.commit()
    conn.close()

    cols_before = {
        r[1]
        for r in sqlite3.connect(str(db_path))
        .execute("PRAGMA table_info(orders)")
        .fetchall()
    }
    assert "broker_order_id" not in cols_before  # precondition

    store = SqliteStateStore(db_path)
    await store.initialize()  # runs _migrate -> adds the column idempotently

    cols_after = {
        r[1]
        for r in sqlite3.connect(str(db_path))
        .execute("PRAGMA table_info(orders)")
        .fetchall()
    }
    assert "broker_order_id" in cols_after

    # The migrated db is fully usable: create + transition with a broker id.
    order = await _ordered(store)
    updated = await store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="b-xyz"
    )
    assert updated.broker_order_id == "b-xyz"
    assert (await store.get_order(order.id)).broker_order_id == "b-xyz"
    await store.close()


async def test_migration_is_idempotent_on_current_db(tmp_path):
    """Running initialize twice on a current-schema db is a no-op (no error)."""

    db_path = tmp_path / "current.db"
    store = SqliteStateStore(db_path)
    await store.initialize()
    await store.initialize()  # must not raise (column already present)
    order = await _ordered(store)
    assert order.broker_order_id is None
    await store.close()
