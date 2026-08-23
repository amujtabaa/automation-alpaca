"""Held fresh-file SQLite proof for WO-0168c; run only after the exact DDL gate."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from app.execution_core.persistence import checkpoint_codec, records, repository
from app.execution_core.persistence.schema import install_schema, schema_ddl_digest
import persistence_setup_support as setup_support
import test_persistence_repository as base


def _open_fresh(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    return connection


def _install_foundation(connection: sqlite3.Connection) -> None:
    install_schema(connection, approved_ddl_sha256=schema_ddl_digest())
    base._foundation(connection)
    connection.commit()


def _scope_wire() -> tuple[int, list[object], list[object], list[object], list[object]]:
    position_scope = [
        "m1.fills.PositionScope/v1",
        ["1", "broker_id", ["paper"]],
        ["1", "environment_id", ["paper"]],
        ["1", "account_id", ["account"]],
        ["1", "symbol_id", ["AAPL"]],
    ]
    return (
        1,
        position_scope,
        [
            "m2.acquisition.State/v1",
            ["1", "application_generation_id", [base.APP_ID.value]],
            position_scope,
            *([None] * 14),
        ],
        ["m2.position.execution-state/v1", position_scope, *([None] * 19)],
        ["m2.protection.checkpoint/v1", *([None] * 31)],
    )


def _projected_envelope(
    proof: records.RuntimeCheckpointSelectionProof,
) -> checkpoint_codec.RuntimeCheckpointEnvelope:
    venue = ["m2.venue.State/v1", *([None] * 22)]
    authority = ["m2.authority.Checkpoint/v1", *([None] * 13)]
    return checkpoint_codec._issue_projected_runtime_checkpoint(
        selection_proof_binding=proof._binding,
        application_generation_id=proof.request.application_generation_id,
        execution_profile_id=proof.request.execution_profile_id,
        market_source_profile_id=proof.request.market_source_profile_id,
        currentness_head_ordinal=proof.target_currentness_head_ordinal,
        checkpoint_version_ordinal=proof.target_checkpoint_version_ordinal,
        venue_wire=venue,
        authority_wire=authority,
        scope_wires=(_scope_wire(),),
        venue_owner_commitment=b"v" * 32,
        authority_owner_commitment=b"a" * 32,
        scope_owner_commitments=((1, b"q" * 32, b"e" * 32, b"p" * 32),),
    )


def _selection_request() -> records.RuntimeCheckpointSelectionRequest:
    return records.RuntimeCheckpointSelectionRequest(
        base.APP_ID,
        base.EXECUTION_PROFILE_ID,
        base.MARKET_PROFILE_ID,
        None,
    )


def test_checkpoint_select_store_commit_reopen_and_load(tmp_path: Path) -> None:
    database = tmp_path / "wo0168c-success.db"
    writer = _open_fresh(database)
    _install_foundation(writer)
    writer.execute("BEGIN")
    selected = repository.select_runtime_checkpoint(writer, _selection_request())
    assert selected.kind is records.RepositoryOutcomeKind.FOUND
    assert type(selected.record) is records.RuntimeCheckpointSelectionProof
    proof = selected.record
    assert proof is not None
    envelope = _projected_envelope(proof)
    stored = repository.store_runtime_checkpoint(
        writer,
        proof,
        envelope,
        capability=setup_support.issue_setup_write_capability(writer),
    )
    assert stored.kind is records.RepositoryOutcomeKind.APPLIED
    assert type(stored.record) is records.RuntimeCheckpointWriteReceipt
    writer.commit()
    writer.close()

    reader = _open_fresh(database)
    reader.execute("BEGIN")
    loaded = repository.load_runtime_checkpoint(
        reader,
        records.RuntimeCheckpointLoadRequest(
            base.APP_ID,
            base.EXECUTION_PROFILE_ID,
            base.MARKET_PROFILE_ID,
        ),
    )
    assert loaded.kind is records.RepositoryOutcomeKind.FOUND
    assert type(loaded.record) is checkpoint_codec.RuntimeCheckpointEnvelope
    assert loaded.record is not None
    assert loaded.record._provenance == "LOADED"
    assert checkpoint_codec.encode_runtime_checkpoint(loaded.record) == (
        envelope.canonical_payload_bytes
    )
    reader.rollback()
    reader.close()


def test_checkpoint_selection_requires_explicit_transaction_with_zero_sql(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-no-transaction.db"
    connection = _open_fresh(database)
    _install_foundation(connection)
    traced: list[str] = []
    connection.set_trace_callback(traced.append)

    outcome = repository.select_runtime_checkpoint(connection, _selection_request())

    assert outcome == records.RepositoryOutcome(
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )
    assert traced == []
    connection.close()


def _integrity_error(message: str, code: int) -> sqlite3.IntegrityError:
    error = sqlite3.IntegrityError(message)
    error.sqlite_errorcode = code
    return error


@pytest.mark.parametrize(
    ("error", "payload_insert", "expected"),
    (
        (
            _integrity_error("primary", 1555),
            False,
            records.RepositoryOutcomeKind.CONFLICT,
        ),
        (
            _integrity_error("unique", 2067),
            False,
            records.RepositoryOutcomeKind.CONFLICT,
        ),
        (
            _integrity_error(
                repository._RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE, 1811
            ),
            True,
            records.RepositoryOutcomeKind.CONFLICT,
        ),
        (
            _integrity_error(
                repository._RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE, 1811
            ),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            _integrity_error("foreign key", 787),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (sqlite3.Error("base"), False, records.RepositoryOutcomeKind.INTEGRITY_FAILURE),
        (
            sqlite3.InterfaceError("interface"),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            sqlite3.DatabaseError("database"),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            sqlite3.DataError("data"),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            sqlite3.OperationalError("operation"),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            sqlite3.InternalError("internal"),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            sqlite3.ProgrammingError("program"),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            sqlite3.NotSupportedError("unsupported"),
            False,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
    ),
)
def test_checkpoint_sqlite_classifier_is_total(
    error: Exception,
    payload_insert: bool,
    expected: records.RepositoryOutcomeKind,
) -> None:
    outcome = repository._classify_runtime_checkpoint_sqlite_failure(
        error,
        payload_insert=payload_insert,
    )

    assert outcome == records.RepositoryOutcome(expected)


class _SQLiteShapedFault(RuntimeError):
    sqlite_errorcode = 1555

    def __str__(self) -> str:
        return repository._RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE


@pytest.mark.parametrize(
    "error",
    (
        TypeError("type"),
        ValueError("value"),
        OverflowError("overflow"),
        sqlite3.Warning("warning"),
        _SQLiteShapedFault(),
    ),
)
def test_checkpoint_non_sqlite_classifier_inputs_propagate_identical_object(
    error: Exception,
) -> None:
    with pytest.raises(type(error)) as raised:
        repository._classify_runtime_checkpoint_sqlite_failure(
            error,
            payload_insert=True,
        )

    assert raised.value is error


def test_checkpoint_payload_bytes_are_canonical_json_not_pickle(tmp_path: Path) -> None:
    database = tmp_path / "wo0168c-canonical.db"
    connection = _open_fresh(database)
    _install_foundation(connection)
    connection.execute("BEGIN")
    selected = repository.select_runtime_checkpoint(connection, _selection_request())
    assert type(selected.record) is records.RuntimeCheckpointSelectionProof
    proof = selected.record
    assert proof is not None
    envelope = _projected_envelope(proof)

    decoded = json.loads(envelope.canonical_payload_bytes.decode("utf-8"))

    assert decoded[0:2] == [1, "m2.runtime-checkpoint/v1"]
    connection.rollback()
    connection.close()
