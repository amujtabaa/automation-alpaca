"""Held fresh-file SQLite proof for WO-0168c; run only after the exact DDL gate."""

from __future__ import annotations

import json
import re as _re
from pathlib import Path
import sqlite3
from typing import Any, Callable

import pytest

from app.execution_core import authority as _authority
from app.execution_core import identity
from app.execution_core import venue as _venue
from app.execution_core.fills import PositionScope
from app.execution_core.position import ExecutionSnapshot
from app.execution_core.persistence import checkpoint_codec, records, repository
from app.execution_core.persistence.schema import install_schema, schema_ddl_digest
import persistence_setup_support as setup_support
import test_persistence_repository as base


_INDEX_IN_PLAN = _re.compile(r"USING (?:COVERING )?INDEX (\w+)")

_SQL_SOURCE_ALIAS = _re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z_0-9]*)(?:\s+AS\s+([A-Za-z_][A-Za-z_0-9]*))?",
    _re.IGNORECASE,
)


def _base_table_plan_names(sql: str, base_tables: frozenset[str]) -> frozenset[str]:
    """Names EXPLAIN QUERY PLAN would use for this query's base-table sources.

    The planner reports the alias when one is given and the table name otherwise,
    so both spellings are collected; a source that is not a base table is a CTE or
    subquery and is deliberately absent.
    """

    names: set[str] = set()
    for source, alias in _SQL_SOURCE_ALIAS.findall(sql):
        if source.lower() not in base_tables:
            continue
        names.add((alias or source).upper())
    return frozenset(names)


def _open_fresh(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    return connection


def _install_foundation(
    connection: sqlite3.Connection, *, dormant: bool = True
) -> None:
    """Install the schema and, by default, a dormant-scope foundation.

    ``dormant=False`` restores ``base._foundation`` exactly, for the selection
    tests that pin row counts produced by a live controller and protection
    authority.

    ``base._foundation`` installs an *active* controller and protection authority
    whose commitment digests are fixture constants. No honestly constructed owner
    can carry those digests, so the projector's active path is unreachable from it.
    The dormant variant below differs only in those two records and lets the real
    projector run end to end, which is what this file needs: it proves the
    persistence round trip, so the bytes it stores should be the bytes the
    production projector actually emits.
    """

    install_schema(connection, approved_ddl_sha256=schema_ddl_digest())
    if not dormant:
        base._foundation(connection)
        connection.commit()
        return
    for operation, value in (
        (repository.store_execution_profile, base._execution_profile()),
        (repository.store_market_source_profile, base._market_profile()),
        (repository.store_application_generation, base._application()),
        (repository.store_scope, base._scope()),
        (repository.store_acquisition_generation, base._acquisition()),
        (repository.store_symbol_controller, _dormant_controller()),
        (repository.store_market_stream_authority, base._market_stream()),
        (repository.store_market_cursor, base._cursor()),
        (repository.store_protection_authority, _dormant_protection()),
    ):
        outcome = operation(
            connection,
            value,
            capability=setup_support.issue_setup_write_capability(connection),
        )
        assert outcome.kind is records.RepositoryOutcomeKind.APPLIED, (
            operation.__name__,
            outcome.kind,
        )
    connection.commit()


def _dormant_controller() -> records.SymbolControllerRecord:
    return records.SymbolControllerRecord(
        1,
        base.APP_ID,
        base.EXECUTION_PROFILE_ID,
        None,
        0,
        "CONSISTENT",
        0,
        1,
        "9b" * 32,
    )


def _dormant_protection() -> records.ProtectionAuthorityRecord:
    return records.ProtectionAuthorityRecord(
        1, "NORMAL", None, None, None, None, None, None, 0, "51" * 32, 1
    )


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


def _genesis_owners() -> tuple[
    _authority.ExecutionAuthorityState, _venue.VenueRecoveryBook
]:
    """Genesis authority and venue owners on the exact scope the fixture installs."""

    state = _authority.initial_execution_authority_state(
        _venue.VenueScope(
            base.APP_ID,
            identity.BrokerId("paper"),
            identity.EnvironmentId("paper"),
            identity.AccountId("account"),
        )
    )
    return state, state.venue


def _projected_envelope(
    proof: records.RuntimeCheckpointSelectionProof,
) -> checkpoint_codec.RuntimeCheckpointEnvelope:
    """Project the envelope through the production projector, not a hand-built shape.

    The earlier fixture assembled every wire by hand as an all-null skeleton and
    handed it to ``_issue_projected_runtime_checkpoint``. That skeleton is what the
    wire validator now refuses, and hand-assembly was never the thing under test
    here: this file proves the persistence round trip, so it should carry whatever
    bytes the real projector emits. Family coverage stays with the pure suite.

    The fixture's selection admits a single scope with no effects, owners, or roots,
    so the honest projection of genesis owners is a populated top row over empty
    collections.
    """

    state, book = _genesis_owners()
    scope_owners = tuple(
        checkpoint_codec._RuntimeCheckpointScopeOwners(
            record.scope_id,
            None,
            ExecutionSnapshot.flat(
                PositionScope(
                    book.scope.broker,
                    book.scope.environment,
                    book.scope.account,
                    record.symbol,
                )
            ),
            None,
        )
        for record in proof._selection.scopes
    )
    return checkpoint_codec._project_runtime_checkpoint(
        proof, book, state, scope_owners
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


class _InjectedCheckpointFault(RuntimeError):
    """Exact non-SQL fault used at one named checkpoint seam."""


class _InjectedCommitFault(RuntimeError):
    """Exact caller-side ambiguous COMMIT fault."""


class _ReceiptValueErrorSubclass(ValueError):
    """Adjacent receipt error that must not enter exact-type translation."""


class _CursorOverride:
    def __init__(
        self,
        cursor: sqlite3.Cursor | None = None,
        *,
        rows: list[tuple[Any, ...]] | None = None,
        rowcount: int | None = None,
    ) -> None:
        self._cursor = cursor
        self._rows = rows
        self._rowcount = rowcount

    @property
    def rowcount(self) -> int:
        if self._rowcount is not None:
            return self._rowcount
        assert self._cursor is not None
        return self._cursor.rowcount

    def fetchall(self) -> list[tuple[Any, ...]]:
        if self._rows is not None:
            return self._rows
        assert self._cursor is not None
        return [tuple(row) for row in self._cursor.fetchall()]


class _ObservedConnection:
    """Connection-identity preserving fault proxy with exact call accounting."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self.before_execute: dict[str, BaseException] = {}
        self.after_execute: dict[str, BaseException] = {}
        self.cursor_overrides: dict[str, _CursorOverride] = {}
        self.statements: list[tuple[str, tuple[Any, ...]]] = []
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0
        self.commit_fault: BaseException | None = None
        self.commit_before_fault = False

    @property
    def in_transaction(self) -> bool:
        return self._connection.in_transaction

    def execute(
        self,
        sql: str,
        parameters: tuple[Any, ...] = (),
    ) -> sqlite3.Cursor | _CursorOverride:
        exact_parameters = tuple(parameters)
        self.statements.append((sql, exact_parameters))
        before = self.before_execute.get(sql)
        if before is not None:
            raise before
        override = self.cursor_overrides.get(sql)
        if override is None:
            cursor: sqlite3.Cursor | _CursorOverride = self._connection.execute(
                sql, exact_parameters
            )
        else:
            cursor = override
        after = self.after_execute.get(sql)
        if after is not None:
            raise after
        return cursor

    def commit(self) -> None:
        self.commit_calls += 1
        if self.commit_fault is not None and not self.commit_before_fault:
            raise self.commit_fault
        self._connection.commit()
        if self.commit_fault is not None:
            raise self.commit_fault

    def rollback(self) -> None:
        self.rollback_calls += 1
        self._connection.rollback()

    def close(self) -> None:
        self.close_calls += 1
        self._connection.close()

    def set_trace_callback(self, callback: Callable[[str], None] | None) -> None:
        self._connection.set_trace_callback(callback)


def _begin_projected_candidate(
    connection: _ObservedConnection,
) -> tuple[
    records.RuntimeCheckpointSelectionProof,
    checkpoint_codec.RuntimeCheckpointEnvelope,
]:
    connection.execute("BEGIN")
    selected = repository.select_runtime_checkpoint(connection, _selection_request())
    assert selected.kind is records.RepositoryOutcomeKind.FOUND
    assert type(selected.record) is records.RuntimeCheckpointSelectionProof
    proof = selected.record
    assert proof is not None
    return proof, _projected_envelope(proof)


def _checkpoint_rows(database: Path) -> dict[str, tuple[tuple[Any, ...], ...]]:
    """Read only the exact durable checkpoint and reverse-edge coordinates."""

    reopened = _open_fresh(database)
    reopened.execute("BEGIN")
    assert reopened.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert reopened.execute("PRAGMA recursive_triggers").fetchone() == (1,)
    result = {
        "head": tuple(
            tuple(row)
            for row in reopened.execute(
                "SELECT application_generation_id,currentness_head_ordinal,"
                "checkpoint_sha256,checkpoint_version_ordinal "
                "FROM kernel_checkpoint ORDER BY application_generation_id"
            ).fetchall()
        ),
        "payload": tuple(
            tuple(row)
            for row in reopened.execute(
                "SELECT application_generation_id,execution_profile_id,"
                "market_source_profile_id,currentness_head_ordinal,"
                "checkpoint_version_ordinal,payload_bytes,payload_length,payload_sha256 "
                "FROM runtime_checkpoint_payload "
                "ORDER BY application_generation_id,checkpoint_version_ordinal"
            ).fetchall()
        ),
        "receipt_edge": tuple(
            tuple(row)
            for row in reopened.execute(
                "SELECT application_generation_id,checkpoint_currentness_head_ordinal,"
                "checkpoint_version_ordinal,checkpoint_payload_sha256 "
                "FROM decision_receipt "
                "WHERE checkpoint_version_ordinal IS NOT NULL "
                "ORDER BY application_generation_id,receipt_ordinal"
            ).fetchall()
        ),
        "outcome_edge": tuple(
            tuple(row)
            for row in reopened.execute(
                "SELECT application_generation_id,checkpoint_currentness_head_ordinal,"
                "checkpoint_version_ordinal,checkpoint_payload_sha256 "
                "FROM durable_input_outcome "
                "WHERE checkpoint_version_ordinal IS NOT NULL "
                "ORDER BY application_generation_id,input_domain,input_identity_sha256"
            ).fetchall()
        ),
    }
    reopened.rollback()
    reopened.close()
    return result


def _assert_exact_predecessor_retained(database: Path) -> None:
    assert _checkpoint_rows(database) == {
        "head": (),
        "payload": (),
        "receipt_edge": (),
        "outcome_edge": (),
    }


def _finish_failed_write(
    database: Path,
    writer: _ObservedConnection,
) -> None:
    writer.rollback()
    assert writer.rollback_calls == 1
    assert writer.commit_calls == 0
    writer.close()
    assert writer.close_calls == 1
    _assert_exact_predecessor_retained(database)


def _fresh_writer(database: Path, *, dormant: bool = True) -> _ObservedConnection:
    raw = _open_fresh(database)
    _install_foundation(raw, dormant=dormant)
    return _ObservedConnection(raw)


def _store(
    writer: _ObservedConnection,
    proof: records.RuntimeCheckpointSelectionProof,
    envelope: checkpoint_codec.RuntimeCheckpointEnvelope,
) -> records.RepositoryOutcome[Any]:
    return repository.store_runtime_checkpoint(
        writer,
        proof,
        envelope,
        capability=setup_support.issue_setup_write_capability(writer),
    )


def test_w00a_capability_refusals_are_exact_and_execute_zero_sql(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-w00a.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    writer.rollback()
    writer.statements.clear()

    with pytest.raises(TypeError, match="missing 1 required keyword-only argument"):
        repository.store_runtime_checkpoint(writer, proof, envelope)  # type: ignore[call-arg]
    with pytest.raises(TypeError, match="write capability is not admitted"):
        repository.store_runtime_checkpoint(
            writer, proof, envelope, capability=object()
        )

    missing = object.__new__(repository._SetupWriteCapability)
    with pytest.raises(ValueError, match="not current for connection"):
        repository.store_runtime_checkpoint(writer, proof, envelope, capability=missing)

    forged = object.__new__(repository._SetupWriteCapability)
    object.__setattr__(forged, "_connection", writer)
    object.__setattr__(forged, "_seal", object())
    with pytest.raises(ValueError, match="not current for connection"):
        repository.store_runtime_checkpoint(writer, proof, envelope, capability=forged)

    other_database = tmp_path / "wo0168c-w00a-other.db"
    other = _fresh_writer(other_database)
    cross_connection = setup_support.issue_setup_write_capability(other)
    with pytest.raises(ValueError, match="not current for connection"):
        repository.store_runtime_checkpoint(
            writer,
            proof,
            envelope,
            capability=cross_connection,
        )

    wrong_seal = object.__new__(repository._RuntimeWriteCapability)
    object.__setattr__(wrong_seal, "_connection", writer)
    object.__setattr__(wrong_seal, "_seal", object())
    with pytest.raises(ValueError, match="not current for connection"):
        repository.store_runtime_checkpoint(
            writer, proof, envelope, capability=wrong_seal
        )

    assert writer.statements == []
    other.close()
    writer.close()


def test_w00a_capability_types_cannot_be_subclassed() -> None:
    with pytest.raises(TypeError, match="cannot be subclassed"):

        class _ForbiddenSetupCapability(repository._SetupWriteCapability):
            pass

    with pytest.raises(TypeError, match="cannot be subclassed"):

        class _ForbiddenRuntimeCapability(repository._RuntimeWriteCapability):
            pass


def test_w00a_authentic_setup_capability_outside_transaction_returns_integrity_with_zero_sql(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-w00a-no-transaction.db"
    writer = _fresh_writer(database)
    writer.execute("BEGIN")
    selected = repository.select_runtime_checkpoint(writer, _selection_request())
    assert type(selected.record) is records.RuntimeCheckpointSelectionProof
    proof = selected.record
    assert proof is not None
    envelope = _projected_envelope(proof)
    writer.rollback()
    writer.statements.clear()

    outcome = _store(writer, proof, envelope)

    assert outcome == records.RepositoryOutcome(
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )
    assert writer.statements == []
    writer.close()


def test_w00b_only_authentic_setup_capability_reaches_checkpoint_sql(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-w00b.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    fault = _InjectedCheckpointFault("W00b reached exact reselection SQL")
    writer.before_execute[repository._RUNTIME_CHECKPOINT_SELECTION_SQL[0]] = fault
    before = len(writer.statements)

    with pytest.raises(_InjectedCheckpointFault) as raised:
        _store(writer, proof, envelope)

    assert raised.value is fault
    # The capability check runs first, then _verify_schema_connection issues its
    # connection PRAGMAs. Those are not checkpoint SQL, so the claim under test is
    # that the FIRST checkpoint statement reached is the reselection query.
    checkpoint_sql = set(repository._RUNTIME_CHECKPOINT_SELECTION_SQL)
    reached = [sql for sql, _ in writer.statements[before:] if sql in checkpoint_sql]
    assert reached[:1] == [repository._RUNTIME_CHECKPOINT_SELECTION_SQL[0]], reached[:1]
    _finish_failed_write(database, writer)


def test_f00_caller_fault_before_store_rolls_back_without_repository_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "wo0168c-f00.db"
    writer = _fresh_writer(database)
    writer.execute("BEGIN")
    calls = 0

    def forbidden_store(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        del args, kwargs

    monkeypatch.setattr(repository, "store_runtime_checkpoint", forbidden_store)
    fault = _InjectedCheckpointFault("F00")
    with pytest.raises(_InjectedCheckpointFault) as raised:
        try:
            raise fault
        except _InjectedCheckpointFault:
            writer.rollback()
            raise

    assert raised.value is fault
    assert calls == 0
    assert writer.rollback_calls == 1
    assert writer.commit_calls == 0
    writer.close()
    _assert_exact_predecessor_retained(database)


@pytest.mark.parametrize(
    ("error", "expected"),
    (
        (_integrity_error("primary", 1555), records.RepositoryOutcomeKind.CONFLICT),
        (_integrity_error("unique", 2067), records.RepositoryOutcomeKind.CONFLICT),
        (
            _integrity_error(
                repository._RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE, 1811
            ),
            records.RepositoryOutcomeKind.CONFLICT,
        ),
        (
            _integrity_error("foreign key", 787),
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            sqlite3.OperationalError("F01 operation"),
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
        (
            sqlite3.DataError("F01 data"),
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
        ),
    ),
)
def test_f01_payload_insert_sqlite_partition_rolls_back_exactly(
    tmp_path: Path,
    error: sqlite3.Error,
    expected: records.RepositoryOutcomeKind,
) -> None:
    database = tmp_path / f"wo0168c-f01-{type(error).__name__}-{expected.value}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    writer.before_execute[repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL] = error

    outcome = _store(writer, proof, envelope)

    assert outcome.kind is expected
    assert outcome.record is None
    assert not any(
        sql
        in {
            repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL,
            repository._RUNTIME_CHECKPOINT_HEAD_UPDATE_SQL,
        }
        for sql, _ in writer.statements
    )
    _finish_failed_write(database, writer)


@pytest.mark.parametrize(
    "error",
    (
        TypeError("F01 type"),
        ValueError("F01 value"),
        OverflowError("F01 overflow"),
        _InjectedCheckpointFault("F01 injected"),
    ),
)
def test_f01_payload_insert_non_sql_fault_propagates_identical_object(
    tmp_path: Path,
    error: Exception,
) -> None:
    database = tmp_path / f"wo0168c-f01-nonsql-{type(error).__name__}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    writer.before_execute[repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL] = error

    with pytest.raises(type(error)) as raised:
        _store(writer, proof, envelope)

    assert raised.value is error
    _finish_failed_write(database, writer)


def test_f02_fault_after_payload_insert_before_cas_rolls_back_exactly(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-f02.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    fault = _InjectedCheckpointFault("F02")
    writer.after_execute[repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL] = fault

    with pytest.raises(_InjectedCheckpointFault) as raised:
        _store(writer, proof, envelope)

    assert raised.value is fault
    assert not any(
        sql
        in {
            repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL,
            repository._RUNTIME_CHECKPOINT_HEAD_UPDATE_SQL,
        }
        for sql, _ in writer.statements
    )
    _finish_failed_write(database, writer)


@pytest.mark.parametrize(
    "error",
    (
        sqlite3.OperationalError("F03 operation"),
        _integrity_error(repository._RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE, 1811),
    ),
)
def test_f03_cas_sqlite_failure_is_integrity_not_payload_conflict(
    tmp_path: Path,
    error: sqlite3.Error,
) -> None:
    database = tmp_path / f"wo0168c-f03-{type(error).__name__}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    writer.before_execute[repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL] = error

    outcome = _store(writer, proof, envelope)

    assert outcome == records.RepositoryOutcome(
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )
    _finish_failed_write(database, writer)


def test_f03_cas_non_sql_fault_propagates_identical_object(tmp_path: Path) -> None:
    database = tmp_path / "wo0168c-f03-nonsql.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    fault = _InjectedCheckpointFault("F03")
    writer.before_execute[repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL] = fault

    with pytest.raises(_InjectedCheckpointFault) as raised:
        _store(writer, proof, envelope)

    assert raised.value is fault
    _finish_failed_write(database, writer)


def test_f04_zero_row_cas_returns_conflict_and_rolls_back_exactly(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-f04.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    writer.cursor_overrides[repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL] = (
        _CursorOverride(rowcount=0)
    )

    outcome = _store(writer, proof, envelope)

    assert outcome == records.RepositoryOutcome(records.RepositoryOutcomeKind.CONFLICT)
    _finish_failed_write(database, writer)


def test_f05_stale_full_reselection_returns_conflict_before_insert(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "wo0168c-f05.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    writer.statements.clear()
    monkeypatch.setattr(
        repository,
        "select_runtime_checkpoint",
        lambda connection, request: records.RepositoryOutcome(
            records.RepositoryOutcomeKind.CONFLICT
        ),
    )

    outcome = _store(writer, proof, envelope)

    assert outcome == records.RepositoryOutcome(records.RepositoryOutcomeKind.CONFLICT)
    assert not any(
        sql == repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL
        for sql, _ in writer.statements
    )
    _finish_failed_write(database, writer)


def test_f06_fault_after_successful_cas_before_reread_rolls_back_exactly(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-f06.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    fault = _InjectedCheckpointFault("F06")
    writer.after_execute[repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL] = fault

    with pytest.raises(_InjectedCheckpointFault) as raised:
        _store(writer, proof, envelope)

    assert raised.value is fault
    assert any(
        sql == repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL
        for sql, _ in writer.statements
    )
    _finish_failed_write(database, writer)


@pytest.mark.parametrize(
    "error",
    (
        sqlite3.OperationalError("F07 operation"),
        _integrity_error(repository._RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE, 1811),
    ),
)
def test_f07_reread_sqlite_failure_is_integrity_not_payload_conflict(
    tmp_path: Path,
    error: sqlite3.Error,
) -> None:
    database = tmp_path / f"wo0168c-f07-{type(error).__name__}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    writer.before_execute[repository._RUNTIME_CHECKPOINT_HEAD_SELECT_SQL] = error

    outcome = _store(writer, proof, envelope)

    assert outcome == records.RepositoryOutcome(
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )
    _finish_failed_write(database, writer)


@pytest.mark.parametrize(
    "rows",
    (
        [],
        [(base.APP_ID.value, 99, "f" * 64, 99)],
        [(base.APP_ID.value, 0, "0" * 64, 1), (base.APP_ID.value, 0, "1" * 64, 1)],
    ),
)
def test_f07_reread_zero_two_or_mismatched_rows_is_integrity(
    tmp_path: Path,
    rows: list[tuple[Any, ...]],
) -> None:
    database = tmp_path / f"wo0168c-f07-rows-{len(rows)}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    writer.cursor_overrides[repository._RUNTIME_CHECKPOINT_HEAD_SELECT_SQL] = (
        _CursorOverride(rows=rows)
    )

    outcome = _store(writer, proof, envelope)

    assert outcome == records.RepositoryOutcome(
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )
    _finish_failed_write(database, writer)


def test_f07_reread_non_sql_fault_propagates_identical_object(tmp_path: Path) -> None:
    database = tmp_path / "wo0168c-f07-nonsql.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    fault = _InjectedCheckpointFault("F07")
    writer.before_execute[repository._RUNTIME_CHECKPOINT_HEAD_SELECT_SQL] = fault

    with pytest.raises(_InjectedCheckpointFault) as raised:
        _store(writer, proof, envelope)

    assert raised.value is fault
    _finish_failed_write(database, writer)


def test_f08_fault_after_exact_reread_before_receipt_rolls_back_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "wo0168c-f08.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    fault = _InjectedCheckpointFault("F08")

    def fault_before_receipt(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise fault

    monkeypatch.setattr(
        repository, "_issue_runtime_checkpoint_write_receipt", fault_before_receipt
    )
    with pytest.raises(_InjectedCheckpointFault) as raised:
        _store(writer, proof, envelope)

    assert raised.value is fault
    assert any(
        sql == repository._RUNTIME_CHECKPOINT_HEAD_SELECT_SQL
        for sql, _ in writer.statements
    )
    _finish_failed_write(database, writer)


def _inject_receipt_phase(
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    error: Exception,
) -> None:
    def raise_exact(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise error

    target = {
        "construction": "_issue_runtime_checkpoint_write_receipt",
        "validation": "_runtime_checkpoint_write_receipt_binding",
        "registration": "_runtime_checkpoint_register",
    }[phase]
    monkeypatch.setattr(records, target, raise_exact)


@pytest.mark.parametrize("phase", ("construction", "validation", "registration"))
@pytest.mark.parametrize("error_type", (TypeError, ValueError, OverflowError))
def test_f09_exact_receipt_exception_cartesian_matrix_translates_to_integrity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    error_type: type[Exception],
) -> None:
    database = tmp_path / f"wo0168c-f09-{phase}-{error_type.__name__}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    error = error_type(f"F09 {phase}")
    _inject_receipt_phase(monkeypatch, phase, error)

    outcome = _store(writer, proof, envelope)

    assert outcome == records.RepositoryOutcome(
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )
    assert outcome.record is None
    _finish_failed_write(database, writer)


@pytest.mark.parametrize(
    "error",
    (
        _ReceiptValueErrorSubclass("F09 adjacent"),
        _InjectedCheckpointFault("F09 injected"),
    ),
)
def test_f09_nontranslated_receipt_fault_propagates_identical_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    database = tmp_path / f"wo0168c-f09-propagate-{type(error).__name__}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    _inject_receipt_phase(monkeypatch, "validation", error)

    with pytest.raises(type(error)) as raised:
        _store(writer, proof, envelope)

    assert raised.value is error
    _finish_failed_write(database, writer)


@pytest.mark.parametrize("commit_before_fault", (False, True))
def test_f10_ambiguous_commit_allows_only_exact_old_or_new_complete_state(
    tmp_path: Path,
    commit_before_fault: bool,
) -> None:
    database = tmp_path / f"wo0168c-f10-{commit_before_fault}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    stored = _store(writer, proof, envelope)
    assert stored.kind is records.RepositoryOutcomeKind.APPLIED
    assert type(stored.record) is records.RuntimeCheckpointWriteReceipt
    fault = _InjectedCommitFault("F10")
    writer.commit_fault = fault
    writer.commit_before_fault = commit_before_fault

    with pytest.raises(_InjectedCommitFault) as raised:
        writer.commit()

    assert raised.value is fault
    assert writer.commit_calls == 1
    assert writer.rollback_calls == 0
    writer.close()
    assert writer.close_calls == 1
    state = _checkpoint_rows(database)
    if commit_before_fault:
        assert len(state["head"]) == 1
        assert len(state["payload"]) == 1
        assert state["head"][0] == (
            base.APP_ID.value,
            envelope.currentness_head_ordinal,
            envelope.payload_sha256,
            envelope.checkpoint_version_ordinal,
        )
        assert state["payload"][0][0:5] == (
            base.APP_ID.value,
            base.EXECUTION_PROFILE_ID,
            base.MARKET_PROFILE_ID,
            envelope.currentness_head_ordinal,
            envelope.checkpoint_version_ordinal,
        )
        assert state["payload"][0][5:] == (
            envelope.canonical_payload_bytes,
            len(envelope.canonical_payload_bytes),
            envelope.payload_sha256,
        )
    else:
        assert state == {
            "head": (),
            "payload": (),
            "receipt_edge": (),
            "outcome_edge": (),
        }
    assert state["receipt_edge"] == ()
    assert state["outcome_edge"] == ()


def test_f11_successful_commit_has_exact_new_complete_state_and_receipt(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-f11.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)

    stored = _store(writer, proof, envelope)

    assert stored.kind is records.RepositoryOutcomeKind.APPLIED
    assert type(stored.record) is records.RuntimeCheckpointWriteReceipt
    receipt = stored.record
    assert receipt is not None
    assert receipt.predecessor_checkpoint is None
    assert receipt.resulting_checkpoint == records.KernelCheckpointRecord(
        base.APP_ID,
        envelope.currentness_head_ordinal,
        envelope.payload_sha256,
        envelope.checkpoint_version_ordinal,
    )
    assert receipt.payload.payload_bytes == envelope.canonical_payload_bytes
    assert receipt.payload.payload_length == len(envelope.canonical_payload_bytes)
    assert receipt.selection_commitment == proof.selection_commitment
    writer.commit()
    assert writer.commit_calls == 1
    assert writer.rollback_calls == 0
    writer.close()
    state = _checkpoint_rows(database)
    assert state["head"] == (
        (
            base.APP_ID.value,
            envelope.currentness_head_ordinal,
            envelope.payload_sha256,
            envelope.checkpoint_version_ordinal,
        ),
    )
    assert state["payload"][0][0:5] == (
        base.APP_ID.value,
        base.EXECUTION_PROFILE_ID,
        base.MARKET_PROFILE_ID,
        envelope.currentness_head_ordinal,
        envelope.checkpoint_version_ordinal,
    )
    assert state["payload"][0][5:] == (
        envelope.canonical_payload_bytes,
        len(envelope.canonical_payload_bytes),
        envelope.payload_sha256,
    )
    assert state["receipt_edge"] == ()
    assert state["outcome_edge"] == ()


@pytest.mark.parametrize(
    ("seam", "sql", "expected", "expected_payload_insert"),
    (
        (
            "selection",
            repository._RUNTIME_CHECKPOINT_SELECTION_SQL[0],
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
            False,
        ),
        (
            "payload",
            repository._RUNTIME_CHECKPOINT_PAYLOAD_INSERT_SQL,
            records.RepositoryOutcomeKind.CONFLICT,
            True,
        ),
        (
            "cas",
            repository._RUNTIME_CHECKPOINT_HEAD_INSERT_SQL,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
            False,
        ),
        (
            "reread",
            repository._RUNTIME_CHECKPOINT_HEAD_SELECT_SQL,
            records.RepositoryOutcomeKind.INTEGRITY_FAILURE,
            False,
        ),
    ),
)
def test_trigger_message_is_enabled_only_at_payload_insert_integrated_seam(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seam: str,
    sql: str,
    expected: records.RepositoryOutcomeKind,
    expected_payload_insert: bool,
) -> None:
    database = tmp_path / f"wo0168c-trigger-route-{seam}.db"
    writer = _fresh_writer(database)
    proof, envelope = _begin_projected_candidate(writer)
    error = _integrity_error(
        repository._RUNTIME_CHECKPOINT_PAYLOAD_CONFLICT_MESSAGE, 1811
    )
    writer.before_execute[sql] = error
    original = repository._classify_runtime_checkpoint_sqlite_failure
    observed: list[bool] = []

    def observe(
        caught: Exception, *, payload_insert: bool
    ) -> records.RepositoryOutcome[Any]:
        observed.append(payload_insert)
        return original(caught, payload_insert=payload_insert)

    monkeypatch.setattr(
        repository, "_classify_runtime_checkpoint_sqlite_failure", observe
    )
    outcome = _store(writer, proof, envelope)

    assert outcome.kind is expected
    assert outcome.record is None
    assert observed == [expected_payload_insert]
    _finish_failed_write(database, writer)


@pytest.mark.parametrize(
    ("query_index", "row_count"),
    ((1, 4_097), (2, 65_536), (4, 65_536), (12, 65_536)),
)
def test_selection_refuses_scope_and_general_cap_sentinels_before_decoding(
    tmp_path: Path,
    query_index: int,
    row_count: int,
) -> None:
    database = tmp_path / f"wo0168c-cap-q{query_index}.db"
    writer = _fresh_writer(database)
    writer.execute("BEGIN")
    target_sql = repository._RUNTIME_CHECKPOINT_SELECTION_SQL[query_index]
    writer.cursor_overrides[target_sql] = _CursorOverride(rows=[()] * row_count)

    outcome = repository.select_runtime_checkpoint(writer, _selection_request())

    assert outcome == records.RepositoryOutcome(
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )
    executed = [sql for sql, _ in writer.statements]
    assert target_sql in executed
    assert not any(
        sql in executed
        for sql in repository._RUNTIME_CHECKPOINT_SELECTION_SQL[query_index + 1 :]
    )
    writer.rollback()
    writer.close()


def test_selection_records_exact_counts_and_canonical_absence_evidence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-absence.db"
    # Pins the counts a live controller and protection authority produce.
    writer = _fresh_writer(database, dormant=False)
    writer.execute("BEGIN")

    selected = repository.select_runtime_checkpoint(writer, _selection_request())

    assert selected.kind is records.RepositoryOutcomeKind.FOUND
    assert type(selected.record) is records.RuntimeCheckpointSelectionProof
    proof = selected.record
    assert proof is not None
    selection = proof._selection
    assert selection.query_row_counts == (
        1,
        1,
        1,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        1,
    )
    absence_names = (
        "owner_effect_absences",
        "claim_effect_absences",
        "acceptance_effect_absences",
        "evidence_acceptance_absences",
        "closure_owner_absences",
        "route_owner_absences",
        "fact_head_root_absences",
        "current_fact_root_absences",
        "stream_generation_absences",
        "cursor_stream_absences",
    )
    for name in absence_names:
        absence = getattr(selection, name)
        assert tuple(item[1] for item in absence) == tuple(
            sorted(item[1] for item in absence)
        )
        assert len({item[1] for item in absence}) == len(absence)
        assert all(type(item[1]) is bytes and len(item[1]) == 32 for item in absence)
    assert selection.stream_generation_absences == ()
    assert selection.cursor_stream_absences == ()
    writer.rollback()
    writer.close()


def test_all_thirteen_selection_queries_have_bounded_indexed_plans(
    tmp_path: Path,
) -> None:
    database = tmp_path / "wo0168c-query-plans.db"
    connection = _open_fresh(database)
    _install_foundation(connection)
    connection.execute("BEGIN")
    base_tables = frozenset(
        str(row[0]).lower()
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    )
    partial_indexes = frozenset(
        str(name).upper()
        for name, index_sql in connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
        ).fetchall()
        # The predicate follows the column list, and the DDL puts it on its own
        # line, so this must not assume a space before WHERE.
        if _re.search(r"\)\s*WHERE\s", str(index_sql), _re.S | _re.I)
    )

    unbounded: set[tuple[int, str]] = set()

    for ordinal, sql in enumerate(repository._RUNTIME_CHECKPOINT_SELECTION_SQL, 1):
        parameters = tuple("plan-probe" for _ in range(sql.count("?")))
        plan = connection.execute(f"EXPLAIN QUERY PLAN {sql}", parameters).fetchall()
        assert plan, f"Q{ordinal} produced no plan"
        details = tuple(str(row[-1]).upper() for row in plan)
        assert any("SEARCH " in detail for detail in details), (ordinal, details)
        # The bounded-plan property is "no pass over a base table whose length
        # tracks history". Three cases, and only the third is a violation:
        #
        #   * a scan of a materialized CTE or subquery is bounded by that CTE's
        #     own selection;
        #   * a scan of a PARTIAL index is bounded by that index's predicate --
        #     the ix_*_checkpoint_* indexes exist precisely so a scan of them
        #     costs live state rather than history, and scanning them is the
        #     intended design;
        #   * any other scan of a base table -- including one through a full
        #     index -- visits every row ever written.
        #
        # An earlier revision of this control excused every "USING INDEX" scan on
        # the reasoning that an index bounds it. That reasoning is wrong: a full
        # index has exactly as many entries as its table, so scanning it is the
        # same unbounded pass. Only the predicate of a partial index bounds one.
        table_names = _base_table_plan_names(sql, base_tables)
        for detail in details:
            if not detail.startswith("SCAN "):
                continue
            scanned = detail.split()[1]
            if scanned not in table_names:
                continue
            index = _INDEX_IN_PLAN.search(detail)
            if index is not None and index.group(1) in partial_indexes:
                continue
            unbounded.add((ordinal, detail))
        # An automatic index over a base table means SQLite is compensating for a
        # missing schema index and will index the whole table -- unbounded. Over a
        # materialized CTE it is a transient index on that CTE's own bounded
        # result, which is expected and costs nothing that grows with the
        # database, so the same base-table distinction applies here.
        for detail in details:
            if "AUTOMATIC" not in detail:
                continue
            indexed = detail.split()[1]
            if indexed in table_names:
                unbounded.add((ordinal, detail))

    # Exactly the known, dispositioned violations -- equality, not a subset, so a
    # new one fails and a fixed one must be removed from this set deliberately.
    #
    # Each is the same shape: the planner leads with a base table instead of the
    # bounded CTE beside it, so the pass costs total history rather than the
    # selection. Q9 carried a sixth and is fixed: pinning the join order with
    # CROSS JOIN turned its SCAN into a SEARCH. The same one-token remedy clears
    # all five of these (measured 5 -> 0), but it is a repository SQL change
    # across five more queries and is not yet authorized.
    assert unbounded == {
        (7, "SCAN OWNER USING INDEX IX_VENUE_IDENTITY_OWNER_EFFECT"),
        (8, "SCAN CLAIM USING INDEX IX_DISPATCH_CLAIM_EFFECT"),
        (10, "SCAN EVIDENCE USING INDEX IX_ACCEPTANCE_EVIDENCE_SET"),
        (11, "SCAN OWNER USING COVERING INDEX IX_VENUE_IDENTITY_OWNER_EFFECT"),
        (12, "SCAN ROUTE USING INDEX IX_ACQUISITION_ROOT_ROUTE_OWNER"),
    }, unbounded

    connection.rollback()
    connection.close()
