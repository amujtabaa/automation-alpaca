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

    conn_execute = connection.execute
    conn_execute(
        "INSERT INTO execution_connection_profile ("
        " connection_profile_id, broker_provider, environment_class,"
        " account_identity, trade_command_origin, order_query_origin,"
        " order_event_origin, credential_handle_fingerprint,"
        " adapter_contract_version, capability_profile_sha256,"
        " deployment_identity, profile_commitment_sha256)"
        " VALUES (?, 'ALPACA', 'PAPER', ?, ?, ?, ?, ?, '1.2.3', ?, ?, ?)",
        (
            "cd" * 32,
            "aa" * 32,
            "https://trade.example.com",
            "https://query.example.com",
            "https://stream.example.com",
            "bb" * 32,
            "cc" * 32,
            "dd" * 32,
        ),
    )
    conn_execute(
        "INSERT INTO application_generation VALUES (?, ?, ?, 1)",
        ("ab" * 32, "cd" * 32, "ef" * 32),
    )

    seed_minimal_chain(connection)
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    first = repo.load_kernel_checkpoint(connection, "ab" * 32)
    connection.set_trace_callback(None)
    base_count = len([s for s in statements if s.upper().startswith("SELECT")])

    # Unrelated growth in a family the load never touches.
    for ordinal in range(200):
        connection.execute(
            "INSERT INTO acceptance_evidence (evidence_id, acceptance_set_id,"
            " effect_id, evidence_kind, evidence_digest, evidence_ordinal)"
            " VALUES (?, 1, 1, 'OBSERVATION', ?, ?)",
            (ordinal + 1, f"{ordinal:02d}" * 32, ordinal + 1),
        )

    statements.clear()
    connection.set_trace_callback(statements.append)
    second = repo.load_kernel_checkpoint(connection, "ab" * 32)
    connection.set_trace_callback(None)
    stressed_count = len(
        [s for s in statements if s.upper().startswith("SELECT")]
    )

    assert first == second
    assert base_count == stressed_count
