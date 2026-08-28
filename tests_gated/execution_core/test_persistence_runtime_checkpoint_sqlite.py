"""Held fresh-file SQLite proof for WO-0168c; run only after the exact DDL gate."""

from __future__ import annotations

import json
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
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import (
    open_approved_sqlite_connection,
    require_approved_ddl_execution,
)
import persistence_setup_support as setup_support
import test_persistence_repository as base


_RuntimeCheckpointPlanAccess = tuple[str, str, str | None]


def _plan_access_violations(
    details: tuple[str, ...],
    accesses: tuple[_RuntimeCheckpointPlanAccess, ...],
) -> tuple[str, ...]:
    """Checks EXPLAIN output against the explicit repository plan contract.

    The repository records every expected base-table access beside its frozen SQL.
    This deliberately consumes that reviewable contract rather than parsing SQL
    sources in a test: SQLite permits aliases, optional ``AS``, ``INDEXED BY``,
    CTEs, and other grammar that a partial source parser can misread.  A missing
    metadata entry is a source-review defect; a missing or scanning EXPLAIN entry
    is an executable plan defect.
    """

    normalized = tuple(detail.upper() for detail in details)
    available = set(range(len(normalized)))
    violations: list[str] = []

    def matching_searches(plan_name: str) -> tuple[int, ...]:
        prefix = f"SEARCH {plan_name.upper()} "
        return tuple(
            index for index in sorted(available) if normalized[index].startswith(prefix)
        )

    def matching_base_details(plan_name: str) -> tuple[str, ...]:
        name = plan_name.upper()
        return tuple(
            detail
            for detail in normalized
            if detail.startswith(f"SEARCH {name} ")
            or detail.startswith(f"SCAN {name} ")
        )

    # Match forced-index entries first so an ordinary primary-key search cannot
    # accidentally consume the only plan row that proves a named index.
    ordered_accesses = tuple(
        access for access in accesses if access[2] is not None
    ) + tuple(access for access in accesses if access[2] is None)
    for base_table, plan_name, required_index in ordered_accesses:
        base_details = matching_base_details(plan_name)
        scans = tuple(
            detail
            for detail in base_details
            if detail.startswith(f"SCAN {plan_name.upper()} ")
        )
        if scans:
            violations.append(f"{base_table}/{plan_name}: unbounded scan {scans!r}")
        if any("AUTOMATIC" in detail for detail in base_details):
            violations.append(
                f"{base_table}/{plan_name}: automatic index {base_details!r}"
            )

        candidates = matching_searches(plan_name)
        if required_index is not None:
            expected_index = f"INDEX {required_index.upper()}"
            candidates = tuple(
                index for index in candidates if expected_index in normalized[index]
            )
            if not candidates:
                violations.append(
                    f"{base_table}/{plan_name}: missing SEARCH via {required_index}"
                )
                continue
        if not candidates:
            violations.append(f"{base_table}/{plan_name}: missing SEARCH")
            continue
        available.remove(candidates[0])

    for index in sorted(available):
        detail = normalized[index]
        if detail.startswith(("SEARCH ", "SCAN ")):
            violations.append(f"unexpected plan access {detail!r}")

    return tuple(violations)


def test_plan_access_checker_refuses_an_unlisted_search_access() -> None:
    """A new SQL source cannot evade the plan proof by omitting its metadata row."""

    violations = _plan_access_violations(
        (
            "SEARCH expected USING INDEX ix_expected (key=?)",
            "SEARCH omitted USING INDEX ix_omitted (key=?)",
        ),
        (("expected_table", "expected", None),),
    )

    assert any("unexpected plan access" in violation for violation in violations)


def _explain_details(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...] | None = None,
) -> tuple[str, ...]:
    if parameters is None:
        parameters = tuple("plan-probe" for _ in range(sql.count("?")))
    return tuple(
        str(row[-1])
        for row in connection.execute(
            f"EXPLAIN QUERY PLAN {sql}", parameters
        ).fetchall()
    )


def _open_fresh(path: Path) -> sqlite3.Connection:
    connection = open_approved_sqlite_connection(path)
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

    install_schema(connection, approved_ddl_sha256=require_approved_ddl_execution())
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


_PLAN_HISTORY_ROW_COUNT = 10_000
_PLAN_HISTORY_SCOPE_OFFSET = 1_000_000
_PLAN_HISTORY_EFFECT_OFFSET = 2_000_000
_PLAN_HISTORY_ROOT_OFFSET = 3_000_000
_PLAN_HISTORY_FACT_OFFSET = 4_000_000
_PLAN_HISTORY_CLAIM_OFFSET = 5_000_000
_PLAN_HISTORY_ACCEPTANCE_OFFSET = 6_000_000
_PLAN_HISTORY_EVIDENCE_OFFSET = 7_000_000
_PLAN_HISTORY_CLOSURE_OFFSET = 8_000_000

_PLAN_HISTORY_POPULATED_TABLES = (
    "execution_connection_profile",
    "market_data_source_profile",
    "application_generation",
    "acquisition_scope",
    "acquisition_generation",
    "acquisition_generation_current",
    "kernel_checkpoint",
    "symbol_controller",
    "root_fill",
    "execution_fact",
    "execution_fact_head",
    "venue_effect",
    "venue_identity_owner",
    "acquisition_root_route",
    "dispatch_claim",
    "acceptance_set",
    "acceptance_evidence",
    "closure_chain",
    "market_stream_authority",
    "market_cursor",
    "protection_authority",
    "runtime_checkpoint_payload",
)


def _history_hex(family: int, ordinal: int) -> str:
    """Returns a deterministic, lowercase, 64-hex stress-lane identity."""

    return f"{family * _PLAN_HISTORY_SCOPE_OFFSET + ordinal:064x}"


def _history_application(ordinal: int) -> str:
    return f"checkpoint-plan-history-{ordinal:05d}"


def _history_scope(ordinal: int) -> int:
    return _PLAN_HISTORY_SCOPE_OFFSET + ordinal


def _history_effect(ordinal: int) -> int:
    return _PLAN_HISTORY_EFFECT_OFFSET + ordinal


def _history_root(ordinal: int) -> int:
    return _PLAN_HISTORY_ROOT_OFFSET + ordinal


def _history_fact(ordinal: int) -> int:
    return _PLAN_HISTORY_FACT_OFFSET + ordinal


def _seed_unrelated_plan_history(connection: sqlite3.Connection) -> None:
    """Creates one valid 10k-row unrelated lane through every planned family.

    Each row is attached to a different application generation than the selected
    foundation.  It is therefore genuine unrelated durable state, not fabricated
    planner statistics or a disabled-constraint shortcut.  The lane reaches every
    base family named by the thirteen-query and load-plan contracts.
    """

    ordinals = range(1, _PLAN_HISTORY_ROW_COUNT + 1)
    connection.execute("BEGIN")
    connection.executemany(
        """
        INSERT INTO execution_connection_profile (
            connection_profile_id, application_generation, broker_provider,
            environment_class, account_identity, trade_command_origin,
            order_query_origin, order_event_origin,
            credential_handle_fingerprint, adapter_contract_version,
            capability_profile_sha256, deployment_identity,
            profile_commitment_sha256
        ) VALUES (?, ?, 'ALPACA', 'PAPER', ?, ?, ?, ?, ?, '1.0.0', ?, ?, ?)
        """,
        (
            (
                _history_hex(1, ordinal),
                _history_application(ordinal),
                _history_hex(5, ordinal),
                f"https://trade-{ordinal}.example.test",
                f"https://query-{ordinal}.example.test",
                f"https://event-{ordinal}.example.test",
                _history_hex(6, ordinal),
                _history_hex(7, ordinal),
                _history_hex(8, ordinal),
                _history_hex(9, ordinal),
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO market_data_source_profile (
            market_source_profile_id, provider, environment_or_feed,
            source_origin, entitlement_class, normalization_contract_version,
            data_capability_profile_sha256, source_profile_commitment_sha256
        ) VALUES (?, 'ALPACA', ?, ?, 'IEX', '1.0.0', ?, ?)
        """,
        (
            (
                _history_hex(2, ordinal),
                f"feed-{ordinal}",
                f"https://feed-{ordinal}.example.test",
                _history_hex(10, ordinal),
                _history_hex(11, ordinal),
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO application_generation (
            application_generation_id, selected_execution_profile_id,
            selected_market_source_profile_id, activation_ordinal
        ) VALUES (?, ?, ?, ?)
        """,
        (
            (
                _history_application(ordinal),
                _history_hex(1, ordinal),
                _history_hex(2, ordinal),
                _PLAN_HISTORY_SCOPE_OFFSET + ordinal,
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO runtime_checkpoint_payload (
            application_generation_id, execution_profile_id,
            market_source_profile_id, currentness_head_ordinal,
            checkpoint_version_ordinal, payload_bytes, payload_length,
            payload_sha256
        ) VALUES (?, ?, ?, 0, 1, x'01', 1, ?)
        """,
        (
            (
                _history_application(ordinal),
                _history_hex(1, ordinal),
                _history_hex(2, ordinal),
                _history_hex(15, ordinal),
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO kernel_checkpoint (
            application_generation_id, currentness_head_ordinal,
            checkpoint_sha256, checkpoint_version_ordinal
        ) VALUES (?, 0, ?, 1)
        """,
        (
            (_history_application(ordinal), _history_hex(15, ordinal))
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO acquisition_scope (
            scope_id, application_generation_id, execution_profile_id, symbol_text
        ) VALUES (?, ?, ?, ?)
        """,
        (
            (
                _history_scope(ordinal),
                _history_application(ordinal),
                _history_hex(1, ordinal),
                f"PLAN{ordinal}",
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO acquisition_generation (
            acquisition_generation_id, scope_id, status, successor_ordinal,
            predecessor_generation_id, mandate_commitment_sha256,
            emergency_compatibility_sha256
        ) VALUES (?, ?, 'LIVE', 1, NULL, ?, ?)
        """,
        (
            (
                _history_hex(3, ordinal),
                _history_scope(ordinal),
                _history_hex(12, ordinal),
                _history_hex(13, ordinal),
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO symbol_controller (
            scope_id, application_generation_id, execution_profile_id,
            live_acquisition_generation_id, aggregate_quantity, integrity_state,
            currentness_head_ordinal, controller_version_ordinal,
            emergency_compatibility_sha256
        ) VALUES (?, ?, ?, ?, 0, 'CONSISTENT', 0, 1, ?)
        """,
        (
            (
                _history_scope(ordinal),
                _history_application(ordinal),
                _history_hex(1, ordinal),
                _history_hex(3, ordinal),
                _history_hex(13, ordinal),
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO market_stream_authority (
            stream_generation_id, scope_id, application_generation_id,
            acquisition_generation_id, generation_mandate_commitment_sha256,
            source_profile_id, session_external, sequence_mode
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SEQUENCED')
        """,
        (
            (
                _history_hex(4, ordinal),
                _history_scope(ordinal),
                _history_application(ordinal),
                _history_hex(3, ordinal),
                _history_hex(12, ordinal),
                _history_hex(2, ordinal),
                f"plan-session-{ordinal}",
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO market_cursor (
            stream_generation_id, scope_id, application_generation_id,
            acquisition_generation_id, generation_mandate_commitment_sha256,
            source_profile_id, session_external, sequence_mode,
            fixed_cursor_ordinal, published_head_ordinal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'SEQUENCED', 0, 0)
        """,
        (
            (
                _history_hex(4, ordinal),
                _history_scope(ordinal),
                _history_application(ordinal),
                _history_hex(3, ordinal),
                _history_hex(12, ordinal),
                _history_hex(2, ordinal),
                f"plan-session-{ordinal}",
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO protection_authority (
            scope_id, authority_class, active_stream_generation_id,
            active_acquisition_generation_id,
            active_generation_mandate_commitment_sha256,
            active_source_profile_id, active_session_external,
            active_sequence_mode, expected_controller_head_ordinal,
            state_commitment_sha256, version_ordinal
        ) VALUES (?, 'NORMAL', ?, ?, ?, ?, ?, 'SEQUENCED', 0, ?, 1)
        """,
        (
            (
                _history_scope(ordinal),
                _history_hex(4, ordinal),
                _history_hex(3, ordinal),
                _history_hex(12, ordinal),
                _history_hex(2, ordinal),
                f"plan-session-{ordinal}",
                _history_hex(14, ordinal),
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO root_fill (
            root_fill_key_id, scope_id, application_generation_id,
            execution_profile_id, owner_generation_id, root_fill_external,
            economics_head_ordinal
        ) VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (
            (
                _history_root(ordinal),
                _history_scope(ordinal),
                _history_application(ordinal),
                _history_hex(1, ordinal),
                _history_hex(3, ordinal),
                f"plan-root-{ordinal}",
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO venue_effect (
            effect_id, effect_external, scope_id, application_generation_id,
            execution_profile_id, acquisition_generation_id,
            generation_mandate_commitment_sha256,
            expected_controller_head_ordinal, expected_protection_version_ordinal,
            authority_class, request_occurrence_external, mandate_external,
            effect_kind, client_order_external, target_order_external, side,
            quantity, economic_scope, lifecycle_state, disposition, created_ordinal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 'NORMAL', ?, ?, 'SUBMIT', ?, NULL,
                  'BUY', 1, x'01', 'REQUESTED', 'OPEN', ?)
        """,
        (
            (
                _history_effect(ordinal),
                f"plan-effect-{ordinal}",
                _history_scope(ordinal),
                _history_application(ordinal),
                _history_hex(1, ordinal),
                _history_hex(3, ordinal),
                _history_hex(12, ordinal),
                f"plan-request-{ordinal}",
                f"plan-mandate-{ordinal}",
                f"plan-client-{ordinal}",
                _PLAN_HISTORY_EFFECT_OFFSET + ordinal,
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO venue_identity_owner (
            scope_id, execution_profile_id, owner_external, observation_external,
            effect_id, root_fill_key_id, owner_generation_id,
            admitted_after_effect_closed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            (
                _history_scope(ordinal),
                _history_hex(1, ordinal),
                f"plan-owner-{ordinal}",
                f"plan-observation-{ordinal}",
                _history_effect(ordinal),
                _history_root(ordinal),
                _history_hex(3, ordinal),
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO acquisition_root_route (
            root_fill_key_id, scope_id, application_generation_id,
            execution_profile_id, acquisition_generation_id, effect_id,
            owner_external, observation_external
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            (
                _history_root(ordinal),
                _history_scope(ordinal),
                _history_application(ordinal),
                _history_hex(1, ordinal),
                _history_hex(3, ordinal),
                _history_effect(ordinal),
                f"plan-owner-{ordinal}",
                f"plan-observation-{ordinal}",
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO dispatch_claim (
            claim_id, effect_id, execution_profile_id, claim_occurrence_external,
            claim_ordinal
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            (
                _PLAN_HISTORY_CLAIM_OFFSET + ordinal,
                _history_effect(ordinal),
                _history_hex(1, ordinal),
                f"plan-claim-{ordinal}",
                _PLAN_HISTORY_CLAIM_OFFSET + ordinal,
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        "INSERT INTO acceptance_set (acceptance_set_id, effect_id) VALUES (?, ?)",
        (
            (_PLAN_HISTORY_ACCEPTANCE_OFFSET + ordinal, _history_effect(ordinal))
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO acceptance_evidence (
            evidence_id, acceptance_set_id, effect_id, evidence_kind, proof_kind,
            evidence_digest, evidence_ordinal, contradiction_owner_external,
            contradiction_observation_external
        ) VALUES (?, ?, ?, 'OBSERVATION', NULL, ?, ?, NULL, NULL)
        """,
        (
            (
                _PLAN_HISTORY_EVIDENCE_OFFSET + ordinal,
                _PLAN_HISTORY_ACCEPTANCE_OFFSET + ordinal,
                _history_effect(ordinal),
                _history_hex(16, ordinal),
                _PLAN_HISTORY_EVIDENCE_OFFSET + ordinal,
            )
            for ordinal in ordinals
        ),
    )
    connection.executemany(
        """
        INSERT INTO closure_chain (
            closure_id, scope_id, owner_external, ordinal, effect_id,
            closure_kind, predecessor_closure_id
        ) VALUES (?, ?, ?, 1, ?, 'TERMINAL_LEG', NULL)
        """,
        (
            (
                _PLAN_HISTORY_CLOSURE_OFFSET + ordinal,
                _history_scope(ordinal),
                f"plan-owner-{ordinal}",
                _history_effect(ordinal),
            )
            for ordinal in ordinals
        ),
    )
    current_fact = connection.execute(
        "SELECT COALESCE(MAX(fact_ordinal), 0) FROM execution_fact"
    ).fetchone()
    assert current_fact is not None
    first_fact_ordinal = int(current_fact[0])
    connection.executemany(
        """
        INSERT INTO execution_fact (
            fact_id, scope_id, application_generation_id, execution_profile_id,
            root_fill_key_id, source_event_id, order_external, side, kind,
            authority, quantity, price_present, price_units, scale_sign,
            scale_digits, scale_exponent, tick_units, tick_scale_sign,
            tick_scale_digits, tick_scale_exponent, predecessor_fact_id,
            fact_ordinal
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'BUY', 'FILL', 'BROKER_AUTHORITATIVE',
                  1, 1, 100, 0, '1', -2, 1, 0, '1', -2, NULL, ?)
        """,
        (
            (
                _history_fact(ordinal),
                _history_scope(ordinal),
                _history_application(ordinal),
                _history_hex(1, ordinal),
                _history_root(ordinal),
                f"plan-event-{ordinal}",
                f"plan-order-{ordinal}",
                first_fact_ordinal + ordinal,
            )
            for ordinal in ordinals
        ),
    )
    connection.commit()


def _assert_unrelated_plan_history_floor(connection: sqlite3.Connection) -> None:
    for table_name in _PLAN_HISTORY_POPULATED_TABLES:
        row = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        assert row is not None
        assert int(row[0]) >= _PLAN_HISTORY_ROW_COUNT, (table_name, row)


def _required_selection_indexes() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            required_index
            for accesses in repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS
            for _, _, required_index in accesses
            if required_index is not None
        )
    )


def _first_selection_query_for_index(
    index: str,
) -> tuple[str, tuple[_RuntimeCheckpointPlanAccess, ...]]:
    for sql, accesses in zip(
        repository._RUNTIME_CHECKPOINT_SELECTION_SQL,
        repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS,
        strict=True,
    ):
        if any(required_index == index for _, _, required_index in accesses):
            return sql, accesses
    raise AssertionError(f"selection manifest does not name {index}")


def _assert_required_indexes_are_hard_requirements(
    connection: sqlite3.Connection,
) -> None:
    """Proves each named R3 index cannot be silently optimized away."""

    for index in _required_selection_indexes():
        sql, _ = _first_selection_query_for_index(index)
        connection.execute("SAVEPOINT checkpoint_plan_required_index")
        try:
            connection.execute(f"DROP INDEX {index}")
            with pytest.raises(sqlite3.OperationalError):
                _explain_details(connection, sql)
        finally:
            connection.execute("ROLLBACK TO checkpoint_plan_required_index")
            connection.execute("RELEASE checkpoint_plan_required_index")


def _assert_unaliased_not_indexed_mutant_is_detected(
    connection: sqlite3.Connection,
) -> None:
    """Exercises an unaliased source that the former SQL parser misclassified."""

    index = "ix_venue_effect_generation_disposition"
    accesses: tuple[_RuntimeCheckpointPlanAccess, ...] = (
        ("venue_effect", "venue_effect", index),
    )
    sql = (
        "SELECT effect_id FROM venue_effect "
        f"INDEXED BY {index} "
        "WHERE acquisition_generation_id=? AND disposition='OPEN'"
    )
    parameters = (_history_hex(3, 1),)
    original_details = _explain_details(connection, sql, parameters)
    assert _plan_access_violations(original_details, accesses) == (), original_details

    mutant_sql = sql.replace(f"INDEXED BY {index}", "NOT INDEXED", 1)
    mutant_details = _explain_details(connection, mutant_sql, parameters)
    assert any(
        detail.upper().startswith("SCAN VENUE_EFFECT ") for detail in mutant_details
    ), mutant_details
    assert _plan_access_violations(mutant_details, accesses), mutant_details


def test_thirteen_selection_and_load_queries_have_direct_plans_under_history_stress(
    tmp_path: Path,
) -> None:
    """Held R3 plan proof; execution is allowed only by the exact DDL gate."""

    database = tmp_path / "wo0168c-query-plans.db"
    connection = _open_fresh(database)
    try:
        _install_foundation(connection)
        _seed_unrelated_plan_history(connection)
        _assert_unrelated_plan_history_floor(connection)
        connection.execute("ANALYZE")
        connection.execute("BEGIN")

        for ordinal, (sql, accesses) in enumerate(
            zip(
                repository._RUNTIME_CHECKPOINT_SELECTION_SQL,
                repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS,
                strict=True,
            ),
            1,
        ):
            details = _explain_details(connection, sql)
            violations = _plan_access_violations(details, accesses)
            assert not violations, (f"Q{ordinal}", details, violations)

        for label, sql, accesses in zip(
            ("head", "payload"),
            (
                repository._RUNTIME_CHECKPOINT_HEAD_SELECT_SQL,
                repository._RUNTIME_CHECKPOINT_PAYLOAD_SELECT_SQL,
            ),
            repository._RUNTIME_CHECKPOINT_LOAD_PLAN_ACCESS,
            strict=True,
        ):
            details = _explain_details(connection, sql)
            violations = _plan_access_violations(details, accesses)
            assert not violations, (label, details, violations)

        _assert_required_indexes_are_hard_requirements(connection)
        _assert_unaliased_not_indexed_mutant_is_detected(connection)
    finally:
        connection.rollback()
        connection.close()
