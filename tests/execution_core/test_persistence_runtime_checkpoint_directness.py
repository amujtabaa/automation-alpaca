"""Static directness controls for the non-serving runtime-checkpoint boundary."""

from __future__ import annotations

import ast
import inspect
import re

from app.execution_core.persistence import records, repository


def test_runtime_checkpoint_repository_has_one_static_thirteen_query_manifest() -> None:
    queries = repository._RUNTIME_CHECKPOINT_SELECTION_SQL

    assert type(queries) is tuple
    assert len(queries) == 13
    assert all(type(query) is str and "LIMIT" in query for query in queries)
    assert "ix_acquisition_scope_checkpoint" in queries[1]
    assert "ix_acquisition_generation_current_checkpoint_effect" in queries[3]
    assert "ix_acquisition_generation_current_checkpoint_protection" in queries[3]
    assert "ix_venue_owner_checkpoint_late" in queries[5]
    assert "ix_market_stream_authority_checkpoint_generation" in queries[12]
    assert all("?" in query for query in queries)


def test_runtime_checkpoint_write_sql_is_exact_and_transaction_free() -> None:
    assert repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL == (
        "INSERT INTO runtime_checkpoint_payload("
        "application_generation_id,execution_profile_id,market_source_profile_id,"
        "currentness_head_ordinal,checkpoint_version_ordinal,payload_bytes,"
        "payload_length,payload_sha256) VALUES (?,?,?,?,?,?,?,?)"
    )
    assert repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL == (
        "INSERT INTO kernel_checkpoint(application_generation_id,currentness_head_ordinal,"
        "checkpoint_sha256,checkpoint_version_ordinal) SELECT ?,?,?,? WHERE NOT EXISTS ("
        "SELECT 1 FROM kernel_checkpoint WHERE application_generation_id=?)"
    )
    assert repository._RUNTIME_CHECKPOINT_HEAD_UPDATE_SQL == (
        "UPDATE kernel_checkpoint SET currentness_head_ordinal=?,checkpoint_sha256=?,"
        "checkpoint_version_ordinal=? WHERE application_generation_id=? "
        "AND currentness_head_ordinal=? AND checkpoint_sha256=? "
        "AND checkpoint_version_ordinal=?"
    )
    checkpoint_sql = "\n".join(
        (
            *repository._RUNTIME_CHECKPOINT_SELECTION_SQL,
            repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL,
            repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL,
            repository._RUNTIME_CHECKPOINT_HEAD_UPDATE_SQL,
        )
    ).upper()
    assert re.search(r"(?m)^\s*(BEGIN|COMMIT|ROLLBACK)\b", checkpoint_sql) is None
    assert "REPLACE" not in checkpoint_sql
    assert "UPSERT" not in checkpoint_sql


def test_runtime_checkpoint_classifier_and_issuers_have_one_source_route() -> None:
    source = inspect.getsource(repository)
    tree = ast.parse(source)
    definitions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_classify_runtime_checkpoint_sqlite_failure" in definitions
    assert source.count("def _classify_runtime_checkpoint_sqlite_failure(") == 1
    assert source.count("def _issue_runtime_checkpoint_write_receipt(") == 1
    assert "_activate_runtime_write_lease" not in source
    assert "_retire_runtime_write_lease" not in source
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "sqlite3" not in imported


def test_runtime_checkpoint_public_repository_surface_is_exactly_added() -> None:
    expected = {
        "select_runtime_checkpoint",
        "store_runtime_checkpoint",
        "load_runtime_checkpoint_payload",
        "load_runtime_checkpoint",
    }

    assert expected <= set(repository.__all__)
    assert "store_runtime_checkpoint_payload" not in repository.__all__
    assert "load_kernel_checkpoint" not in repository.__all__
    assert "store_kernel_checkpoint" not in repository.__all__


def test_runtime_checkpoint_records_integration_routes_and_boolean_domains_exist() -> (
    None
):
    assert callable(records._runtime_checkpoint_selection_proof_is_authentic)
    assert callable(records._issue_runtime_checkpoint_load_proof_binding)
    absent_fact_price = records._runtime_checkpoint_price_columns(
        None, absent_is_null=False
    )
    absent_root_price = records._runtime_checkpoint_price_columns(
        None, absent_is_null=True
    )

    assert absent_fact_price[0] is False
    assert absent_root_price[0] is None
    assert records._runtime_checkpoint_storage_field_binding(False) != (
        records._runtime_checkpoint_storage_field_binding(0)
    )
