"""Directness stress controls: unrelated history cannot change repository work."""

from __future__ import annotations

import sqlite3

import pytest

from app.execution_core.persistence.schema import (
    install_schema,
    schema_ddl_digest,
)





@pytest.fixture()
def connection(tmp_path):
    conn = sqlite3.connect(tmp_path / "wo167-directness.db")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA recursive_triggers = ON")
    install_schema(conn, approved_ddl_sha256=schema_ddl_digest())
    try:
        yield conn
    finally:
        conn.close()


def test_unrelated_history_cannot_change_query_count(tmp_path, connection):
    del tmp_path
    import app.execution_core.persistence.repository as repo

    from test_persistence_repository import _seed_chain as seed_minimal_chain

    seed_minimal_chain(connection)
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    first = repo.load_kernel_checkpoint(connection, "ab" * 32)
    connection.set_trace_callback(None)
    base_count = len([
        s
        for s in statements
        if s.upper().startswith("SELECT")
        and "sqlite_master" not in s
        and "schema_meta" not in s
    ])

    # Unrelated growth in a family the load never touches.
    for ordinal in range(200):
        connection.execute(
            "INSERT INTO market_data_source_profile ("
            " market_source_profile_id, provider, environment_or_feed,"
            " source_origin, entitlement_class,"
            " normalization_contract_version,"
            " data_capability_profile_sha256,"
            " source_profile_commitment_sha256)"
            " VALUES (?, 'ALPACA', 'feed-?', ?, 'IEX', '0.1.0', ?, ?)",
            (
                f"{ordinal:064x}",
                f"https://feed-{ordinal}.example.com",
                f"{ordinal:064x}",
                f"{ordinal + 1:064x}",
            ),
        )

    statements.clear()
    connection.set_trace_callback(statements.append)
    second = repo.load_kernel_checkpoint(connection, "ab" * 32)
    connection.set_trace_callback(None)
    stressed_count = len([
        s
        for s in statements
        if s.upper().startswith("SELECT")
        and "sqlite_master" not in s
        and "schema_meta" not in s
    ])

    assert first == second
    assert base_count == stressed_count
