"""RED contracts for the WO-0167 narrow typed SQLite repository."""

from __future__ import annotations

import sqlite3

import pytest

import app.execution_core.persistence.repository as repository_module
from app.execution_core.persistence import records
from app.execution_core.persistence.schema import (
    install_schema,
    schema_ddl_digest,
)

_EXPORTS = (
    "AcceptanceSetRecord",
    "AcquisitionGenerationCurrentRecord",
    "AcquisitionGenerationRecord",
    "ApplicationGenerationRecord",
    "DispatchClaimRecord",
    "ExecutionFactHeadRecord",
    "KernelCheckpointRecord",
    "RepositoryOutcome",
    "RepositoryOutcomeKind",
    "ScopeRecord",
    "load_acceptance_set",
    "load_acquisition_generation_current",
    "load_application_generation",
    "load_dispatch_claim",
    "load_execution_fact_head",
    "load_kernel_checkpoint",
    "load_scope",
    "record_acceptance_evidence",
    "record_dispatch_claim",
    "record_execution_fact_head",
    "record_kernel_checkpoint",
    "store_acceptance_set",
    "store_acquisition_generation",
    "store_acquisition_generation_current",
    "store_application_generation",
    "store_scope",
)


@pytest.fixture()
def connection(tmp_path):
    conn = sqlite3.connect(tmp_path / "wo167.db")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA recursive_triggers = ON")
    install_schema(conn, approved_ddl_sha256=schema_ddl_digest())
    try:
        yield conn
    finally:
        conn.close()





def _seed_chain(conn: sqlite3.Connection) -> None:
    """Smallest FK-valid chain: both profiles plus one generation."""

    conn.execute(
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
    conn.execute(
        "INSERT INTO market_data_source_profile VALUES"
        " (?, 'ALPACA', 'iex-feed', ?, 'IEX', '0.1.0', ?, ?)",
        (
            "ef" * 32,
            "https://feed.example.com",
            "ff" * 32,
            "01" * 32,
        ),
    )


# ---------------------------------------------------------------------------
# Surface pins.


def test_module_import_is_inert() -> None:
    import sys

    before = set(sys.modules)
    snapshot = dict(vars(repository_module))
    after = set(sys.modules)

    assert not (after - before) - {"app.execution_core.persistence.repository"}
    assert repository_module.__all__ == _EXPORTS


def test_exact_export_surface() -> None:
    public = {n for n in vars(repository_module) if not n.startswith("_")}
    assert public == set(_EXPORTS)


# ---------------------------------------------------------------------------
# Round trips.


def test_application_generation_round_trip(connection) -> None:
    _seed_chain(connection)
    record = records.ApplicationGenerationRecord(
        application_generation_id="ab" * 32,
        selected_execution_profile_id="cd" * 32,
        selected_market_source_profile_id="ef" * 32,
        activation_ordinal=1,
    )
    stored = repository_module.store_application_generation(connection, record)
    assert stored.kind is repository_module.RepositoryOutcomeKind.COMMITTED

    loaded = repository_module.load_application_generation(
        connection, "ab" * 32
    )
    assert loaded.kind is repository_module.RepositoryOutcomeKind.FOUND
    assert loaded.record == record


def test_absence_is_explicit(connection) -> None:
    loaded = repository_module.load_application_generation(connection, "ff" * 32)
    assert loaded.kind is repository_module.RepositoryOutcomeKind.ABSENT
    assert loaded.record is None


def test_conflict_on_duplicate_primary_key(connection) -> None:
    _seed_chain(connection)
    record = records.ScopeRecord(
        scope_id=1,
        application_generation_id="ab" * 32,
        execution_profile_id="cd" * 32,
        symbol_text="AAPL",
    )
    assert (
        repository_module.store_scope(connection, record).kind
        is repository_module.RepositoryOutcomeKind.COMMITTED
    )
    conflict = repository_module.store_scope(connection, record)
    assert conflict.kind is repository_module.RepositoryOutcomeKind.CONFLICT


def test_caller_owned_transaction_rolls_back(connection) -> None:
    _seed_chain(connection)
    record = records.KernelCheckpointRecord(
        application_generation_id="ab" * 32,
        currentness_head_ordinal=4,
        checkpoint_sha256="77" * 32,
        checkpoint_version_ordinal=1,
    )
    connection.execute("BEGIN")
    repository_module.record_kernel_checkpoint(connection, record)
    connection.rollback()

    loaded = repository_module.load_kernel_checkpoint(connection, "ab" * 32)
    assert loaded.kind is repository_module.RepositoryOutcomeKind.ABSENT


def test_repository_never_commits(connection) -> None:
    _seed_chain(connection)
    commits: list[str] = []
    connection.set_trace_callback(
        lambda statement: commits.append(statement.upper())
        if statement.upper().startswith("COMMIT")
        else None
    )
    repository_module.store_scope(
        connection,
        records.ScopeRecord(1, "ab" * 32, "cd" * 32, "MSFT"),
    )
    connection.commit()
    assert commits == []


def test_tampered_catalog_fails_closed(connection) -> None:
    _seed_chain(connection)
    connection.execute(
        "UPDATE schema_meta SET approved_ddl_sha256 = ? WHERE 1", ("00" * 32,)
    )
    with pytest.raises(Exception, match="digest|catalog|schema"):
        repository_module.load_scope(connection, 1)


def test_direct_load_query_shape_is_bounded(connection) -> None:
    _seed_chain(connection)
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    loaded = repository_module.load_application_generation(connection, "ab" * 32)
    connection.set_trace_callback(None)

    assert loaded.kind is repository_module.RepositoryOutcomeKind.FOUND
    domain_queries = [
        s for s in statements if s.strip().upper().startswith("SELECT")
    ]
    assert len(domain_queries) == 1
    plan = connection.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM application_generation"
        " WHERE application_generation_id = ?",
        ("ab" * 32,),
    ).fetchall()
    plan_text = " ".join(str(row[-1]) for row in plan)
    assert "SCAN" not in plan_text
