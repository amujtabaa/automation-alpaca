"""WO-0134 approved SQLite schema, migration guard, and atomicity pins."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

import pytest

from app.models import SignalRecord, SignalStatus
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)

EXPECTED_SIGNAL_COLUMNS: dict[str, tuple[str, bool, bool]] = {
    "id": ("TEXT", False, True),
    "producer_id": ("TEXT", True, False),
    "signal_id": ("TEXT", True, False),
    "status": ("TEXT", True, False),
    "symbol": ("TEXT", True, False),
    "direction": ("TEXT", True, False),
    "issued_at": ("TEXT", False, False),
    "ttl_seconds": ("INTEGER", False, False),
    "expires_at": ("TEXT", False, False),
    "received_at": ("TEXT", True, False),
    "raw_fields": ("TEXT", False, False),
    "suggested_quantity": ("INTEGER", False, False),
    "suggested_limit_price": ("REAL", False, False),
    "thesis": ("TEXT", True, False),
    "provenance": ("TEXT", True, False),
    "payload_hash": ("TEXT", True, False),
    "quarantine_reason": ("TEXT", False, False),
    "created_at": ("TEXT", True, False),
    "updated_at": ("TEXT", True, False),
    "approved_at": ("TEXT", False, False),
    "rejected_at": ("TEXT", False, False),
    "expired_at": ("TEXT", False, False),
    "quarantined_at": ("TEXT", False, False),
    "converted_kind": ("TEXT", False, False),
    "converted_id": ("TEXT", False, False),
    "approved_by": ("TEXT", False, False),
}


def _signal_table_ddl(*, ttl_type: str = "INTEGER", unique_key: bool = True) -> str:
    unique_clause = ", UNIQUE (producer_id, signal_id)" if unique_key else ""
    return f"""
        CREATE TABLE signal_records (
            id TEXT PRIMARY KEY,
            producer_id TEXT NOT NULL,
            signal_id TEXT NOT NULL,
            status TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            issued_at TEXT,
            ttl_seconds {ttl_type},
            expires_at TEXT,
            received_at TEXT NOT NULL,
            raw_fields TEXT,
            suggested_quantity INTEGER,
            suggested_limit_price REAL,
            thesis TEXT NOT NULL,
            provenance TEXT NOT NULL DEFAULT '{{}}',
            payload_hash TEXT NOT NULL,
            quarantine_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            approved_at TEXT,
            rejected_at TEXT,
            expired_at TEXT,
            quarantined_at TEXT,
            converted_kind TEXT,
            converted_id TEXT,
            approved_by TEXT
            {unique_clause}
        );
        CREATE INDEX idx_signal_records_status ON signal_records(status);
        CREATE INDEX idx_signal_records_symbol ON signal_records(symbol);
    """


def _unique_keys(conn: sqlite3.Connection) -> set[tuple[str, ...]]:
    keys: set[tuple[str, ...]] = set()
    for index_row in conn.execute("PRAGMA index_list(signal_records)").fetchall():
        if not bool(index_row[2]):
            continue
        keys.add(
            tuple(
                str(column_row[2])
                for column_row in conn.execute(
                    "SELECT * FROM pragma_index_info(?) ORDER BY seqno",
                    (index_row[1],),
                ).fetchall()
            )
        )
    return keys


async def test_approved_signal_schema_shape_and_indexes(tmp_path) -> None:
    store = SqliteStateStore(tmp_path / "approved-signal-schema.db")
    await store.initialize()
    assert store._conn is not None
    try:
        rows = store._conn.execute("PRAGMA table_info(signal_records)").fetchall()
        actual = {
            row["name"]: (
                str(row["type"]).upper(),
                bool(row["notnull"]),
                bool(row["pk"]),
            )
            for row in rows
        }
        defaults = {row["name"]: row["dflt_value"] for row in rows}
        index_names = {
            row["name"]
            for row in store._conn.execute(
                "PRAGMA index_list(signal_records)"
            ).fetchall()
        }

        assert actual == EXPECTED_SIGNAL_COLUMNS
        assert defaults["provenance"] == "'{}'"
        assert ("producer_id", "signal_id") in _unique_keys(store._conn)
        assert {
            "idx_signal_records_status",
            "idx_signal_records_symbol",
        } <= index_names
    finally:
        store._conn.close()
        store._conn = None


@pytest.mark.parametrize(
    ("ttl_type", "unique_key", "error_fragment"),
    [
        ("TEXT", True, "schema mismatch"),
        ("INTEGER", False, "missing UNIQUE(producer_id, signal_id)"),
    ],
)
async def test_signal_schema_guard_fails_closed(
    tmp_path,
    ttl_type: str,
    unique_key: bool,
    error_fragment: str,
) -> None:
    path = tmp_path / f"malformed-{ttl_type}-{unique_key}.db"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_signal_table_ddl(ttl_type=ttl_type, unique_key=unique_key))
        conn.commit()
    finally:
        conn.close()

    store = SqliteStateStore(path)
    try:
        with pytest.raises(RuntimeError, match=re.escape(error_fragment)):
            await store.initialize()
    finally:
        if store._conn is not None:
            store._conn.close()
            store._conn = None


async def test_signal_event_and_record_rollback_together(tmp_path, monkeypatch) -> None:
    store = SqliteStateStore(tmp_path / "signal-atomicity.db")
    await store.initialize()

    try:

        def fail_record_insert(_cur, _record) -> None:
            raise RuntimeError("injected signal row failure")

        monkeypatch.setattr(store, "_insert_signal_record", fail_record_insert)
        with pytest.raises(RuntimeError, match="injected signal row failure"):
            await store.ingest_signal(
                producer_id="property",
                signal_id="atomic",
                symbol="AAPL",
                direction="buy",
                issued_at=NOW,
                ttl_seconds=300,
                suggested_quantity=10,
                suggested_limit_price=100.0,
                thesis="atomic co-write",
                provenance={"test": "wo-0134"},
                server_max_ttl_seconds=3600,
                cycle_budget_limit=50,
                received_at=NOW,
            )

        assert await store.get_signal("property", "atomic") is None
        assert await store.get_execution_events() == []
    finally:
        if store._conn is not None:
            store._conn.close()
            store._conn = None


async def test_memory_signal_event_and_record_rollback_together(monkeypatch) -> None:
    store = InMemoryStateStore()
    await store.initialize()
    ingest = {
        "producer_id": "property",
        "signal_id": "memory-atomic",
        "symbol": "AAPL",
        "direction": "buy",
        "issued_at": NOW,
        "ttl_seconds": 300,
        "suggested_quantity": 10,
        "suggested_limit_price": 100.0,
        "thesis": "atomic co-write",
        "provenance": {"test": "rev-0039-f2"},
        "server_max_ttl_seconds": 3600,
        "cycle_budget_limit": 50,
        "received_at": NOW,
    }

    def fail_post_write_copy(_record: SignalRecord, **_kwargs: object) -> SignalRecord:
        raise RuntimeError("injected post-write signal failure")

    # The result copy happens after both the event append and signal-map write,
    # so this exercises rollback of both mutations rather than failing pre-write.
    with monkeypatch.context() as patch:
        patch.setattr(SignalRecord, "model_copy", fail_post_write_copy)
        with pytest.raises(RuntimeError, match="injected post-write signal failure"):
            await store.ingest_signal(**ingest)

    assert await store.get_signal("property", "memory-atomic") is None
    assert await store.get_execution_events() == []

    clean = await store.ingest_signal(**ingest)
    assert clean.record.status is SignalStatus.RECEIVED
    assert await store.get_signal("property", "memory-atomic") == clean.record
    assert len(await store.get_execution_events()) == 1
