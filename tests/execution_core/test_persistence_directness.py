"""Mutation-surviving guard, cardinality, and direct-query proofs for WO-0167."""

from __future__ import annotations

import dataclasses
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable

import pytest

from app.execution_core import identity
from app.execution_core.persistence import records
import app.execution_core.persistence.repository as repository
from app.execution_core.persistence.schema import (
    SchemaInstallError,
    install_schema,
    schema_ddl_digest,
)
import persistence_setup_support as setup_support
import test_persistence_repository as fixtures


@pytest.fixture()
def connection(tmp_path: Path):
    connection = sqlite3.connect(tmp_path / "wo167-directness.db")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    install_schema(connection, approved_ddl_sha256=schema_ddl_digest())
    try:
        yield connection
    finally:
        connection.close()


def _evidence(
    effect_id: int,
    *,
    acceptance_set_id: int | None = None,
    evidence_id: int | None = None,
) -> records.AcceptanceEvidenceRecord:
    set_id = effect_id if acceptance_set_id is None else acceptance_set_id
    return records.AcceptanceEvidenceRecord(
        effect_id if evidence_id is None else evidence_id,
        set_id,
        effect_id,
        "OBSERVATION",
        None,
        f"{160 + effect_id:02x}" * 32,
        effect_id,
        None,
        None,
    )


def _closure(effect_id: int) -> records.ClosureChainRecord:
    owner = fixtures._owner(effect_id, root_fill_key_id=None)
    return records.ClosureChainRecord(
        effect_id,
        1,
        owner.owner_id,
        1,
        effect_id,
        "TERMINAL_LEG",
        None,
    )


def _route() -> records.AcquisitionRootRouteRecord:
    owner = fixtures._owner(1, root_fill_key_id=1)
    return records.AcquisitionRootRouteRecord(
        1,
        1,
        fixtures.APP_ID,
        fixtures.EXECUTION_PROFILE_ID,
        fixtures.ACQUISITION_ID,
        1,
        owner.owner_id,
        owner.observation_id,
    )


def _setup_write_capability(connection: sqlite3.Connection) -> object:
    """Issue the named fixture-only token for one directness test connection."""

    return setup_support.issue_setup_write_capability(connection)


def _apply_mutator(
    connection: sqlite3.Connection,
    operation: Callable[..., Any],
    *arguments: object,
) -> Any:
    """Invoke the real repository mutator with an explicit setup capability."""

    return operation(
        connection,
        *arguments,
        capability=_setup_write_capability(connection),
    )


def _seed_complete(connection: sqlite3.Connection) -> None:
    fixtures._foundation(connection)
    fixtures._expect_applied(
        repository.store_root_fill(
            connection, fixtures._root(), capability=_setup_write_capability(connection)
        )
    )
    effect1 = fixtures._effect(1, controller_head=0, protection_version=1)
    owner1 = fixtures._owner(1, root_fill_key_id=1)
    for operation, value in (
        (repository.store_venue_effect, effect1),
        (repository.store_venue_identity_owner, owner1),
        (repository.store_acquisition_root_route, _route()),
        (repository.store_execution_fact, fixtures._fact()),
    ):
        fixtures._expect_applied(_apply_mutator(connection, operation, value))
    protection_v2 = fixtures._protection(controller_head=1, version=2)
    fixtures._expect_applied(
        repository.advance_protection_authority(
            connection, 1, protection_v2, capability=_setup_write_capability(connection)
        )
    )
    effect2 = fixtures._effect(2, controller_head=1, protection_version=2)
    owner2 = fixtures._owner(2, root_fill_key_id=None)
    for operation, value in (
        (repository.store_venue_effect, effect2),
        (repository.store_venue_identity_owner, owner2),
        (repository.store_dispatch_claim, fixtures._claim(2)),
        (repository.store_acceptance_set, records.AcceptanceSetRecord(77, 2)),
        (
            repository.store_acceptance_evidence,
            _evidence(2, acceptance_set_id=77, evidence_id=88),
        ),
        (repository.store_closure, _closure(2)),
    ):
        fixtures._expect_applied(_apply_mutator(connection, operation, value))


def _operation_cases() -> dict[str, Callable[[Any], Any]]:
    effect = fixtures._effect(1, controller_head=0, protection_version=1)
    owner = fixtures._owner(1, root_fill_key_id=1)
    route = _route()
    evidence = _evidence(1)
    closure = _closure(1)
    return {
        "advance_market_cursor": lambda c: repository.advance_market_cursor(
            c,
            0,
            0,
            fixtures._cursor(fixed=1, published=1),
            capability=_setup_write_capability(c),
        ),
        "advance_protection_authority": lambda c: (
            repository.advance_protection_authority(
                c,
                1,
                fixtures._protection(version=2),
                capability=_setup_write_capability(c),
            )
        ),
        "advance_symbol_controller": lambda c: repository.advance_symbol_controller(
            c, 1, fixtures._controller(version=2), capability=_setup_write_capability(c)
        ),
        "advance_venue_effect": lambda c: repository.advance_venue_effect(
            c, "REQUESTED", "OPEN", effect, capability=_setup_write_capability(c)
        ),
        "load_acceptance_evidence": lambda c: repository.load_acceptance_evidence(c, 1),
        "load_acceptance_set": lambda c: repository.load_acceptance_set(c, 1),
        "load_acceptance_set_for_effect": lambda c: (
            repository.load_acceptance_set_for_effect(c, 1)
        ),
        "load_acquisition_generation": lambda c: repository.load_acquisition_generation(
            c, fixtures.ACQUISITION_ID
        ),
        "load_acquisition_generation_current": lambda c: (
            repository.load_acquisition_generation_current(c, fixtures.ACQUISITION_ID)
        ),
        "load_acquisition_root_route": lambda c: repository.load_acquisition_root_route(
            c, 1
        ),
        "load_application_generation": lambda c: repository.load_application_generation(
            c, fixtures.APP_ID
        ),
        "load_closure_head": lambda c: repository.load_closure_head(
            c, 1, owner.owner_id
        ),
        "load_current_proof": lambda c: repository.load_current_proof(
            c, records.CurrentProofRequest(fixtures.APP_ID, 1)
        ),
        "load_dispatch_claim": lambda c: repository.load_dispatch_claim(c, 1),
        "load_dispatch_claim_for_effect": lambda c: (
            repository.load_dispatch_claim_for_effect(c, 1)
        ),
        "load_execution_fact": lambda c: repository.load_execution_fact(c, 1),
        "load_execution_fact_by_source": lambda c: (
            repository.load_execution_fact_by_source(
                c, fixtures.EXECUTION_PROFILE_ID, identity.SourceEventId("event-1")
            )
        ),
        "load_execution_fact_head": lambda c: repository.load_execution_fact_head(c, 1),
        "load_execution_profile": lambda c: repository.load_execution_profile(
            c, fixtures.EXECUTION_PROFILE_ID
        ),
        "load_latest_acceptance_evidence": lambda c: (
            repository.load_latest_acceptance_evidence(c, 1)
        ),
        "load_live_acquisition_generation": lambda c: (
            repository.load_live_acquisition_generation(c, 1)
        ),
        "load_market_cursor": lambda c: repository.load_market_cursor(
            c, fixtures.STREAM_ID
        ),
        "load_market_source_profile": lambda c: repository.load_market_source_profile(
            c, fixtures.MARKET_PROFILE_ID
        ),
        "load_market_stream_authority": lambda c: (
            repository.load_market_stream_authority(c, fixtures.STREAM_ID)
        ),
        "load_open_venue_effects": lambda c: repository.load_open_venue_effects(c, 1),
        "load_protection_authority": lambda c: repository.load_protection_authority(
            c, 1
        ),
        "load_root_fill": lambda c: repository.load_root_fill(c, 1),
        "load_root_fill_by_external": lambda c: repository.load_root_fill_by_external(
            c, fixtures.EXECUTION_PROFILE_ID, identity.RootFillId("root-1")
        ),
        "load_scope": lambda c: repository.load_scope(c, 1),
        "load_symbol_controller": lambda c: repository.load_symbol_controller(c, 1),
        "load_venue_effect": lambda c: repository.load_venue_effect(c, 1),
        "load_venue_identity_owner": lambda c: repository.load_venue_identity_owner(
            c, fixtures.EXECUTION_PROFILE_ID, owner.owner_id
        ),
        "load_venue_identity_owners_for_effect": lambda c: (
            repository.load_venue_identity_owners_for_effect(c, 1)
        ),
        "retire_acquisition_generation": lambda c: (
            repository.retire_acquisition_generation(
                c, fixtures.ACQUISITION_ID, capability=_setup_write_capability(c)
            )
        ),
        "store_acceptance_evidence": lambda c: repository.store_acceptance_evidence(
            c, evidence, capability=_setup_write_capability(c)
        ),
        "store_acceptance_set": lambda c: repository.store_acceptance_set(
            c, records.AcceptanceSetRecord(1, 1), capability=_setup_write_capability(c)
        ),
        "store_acquisition_generation": lambda c: (
            repository.store_acquisition_generation(
                c, fixtures._acquisition(), capability=_setup_write_capability(c)
            )
        ),
        "store_acquisition_root_route": lambda c: (
            repository.store_acquisition_root_route(
                c, route, capability=_setup_write_capability(c)
            )
        ),
        "store_application_generation": lambda c: (
            repository.store_application_generation(
                c, fixtures._application(), capability=_setup_write_capability(c)
            )
        ),
        "store_closure": lambda c: repository.store_closure(
            c, closure, capability=_setup_write_capability(c)
        ),
        "store_dispatch_claim": lambda c: repository.store_dispatch_claim(
            c, fixtures._claim(1), capability=_setup_write_capability(c)
        ),
        "store_execution_fact": lambda c: repository.store_execution_fact(
            c, fixtures._fact(), capability=_setup_write_capability(c)
        ),
        "store_execution_profile": lambda c: repository.store_execution_profile(
            c, fixtures._execution_profile(), capability=_setup_write_capability(c)
        ),
        "store_market_cursor": lambda c: repository.store_market_cursor(
            c, fixtures._cursor(), capability=_setup_write_capability(c)
        ),
        "store_market_source_profile": lambda c: repository.store_market_source_profile(
            c, fixtures._market_profile(), capability=_setup_write_capability(c)
        ),
        "store_market_stream_authority": lambda c: (
            repository.store_market_stream_authority(
                c, fixtures._market_stream(), capability=_setup_write_capability(c)
            )
        ),
        "store_protection_authority": lambda c: repository.store_protection_authority(
            c, fixtures._protection(), capability=_setup_write_capability(c)
        ),
        "store_root_fill": lambda c: repository.store_root_fill(
            c, fixtures._root(), capability=_setup_write_capability(c)
        ),
        "store_scope": lambda c: repository.store_scope(
            c, fixtures._scope(), capability=_setup_write_capability(c)
        ),
        "store_symbol_controller": lambda c: repository.store_symbol_controller(
            c, fixtures._controller(), capability=_setup_write_capability(c)
        ),
        "store_venue_effect": lambda c: repository.store_venue_effect(
            c, effect, capability=_setup_write_capability(c)
        ),
        "store_venue_identity_owner": lambda c: repository.store_venue_identity_owner(
            c, owner, capability=_setup_write_capability(c)
        ),
    }


class _TransactionTripwireCursor:
    def __init__(
        self,
        connection: _TransactionTripwireConnection,
        cursor: Any,
    ) -> None:
        self._connection = connection
        self._cursor = cursor

    @property
    def connection(self) -> _TransactionTripwireConnection:
        return self._connection

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        self._connection._refuse_transaction_sql(sql)
        result = self._cursor.execute(sql, parameters)
        return self if result is self._cursor else result

    def executemany(self, sql: str, parameters: Any) -> Any:
        self._connection._refuse_transaction_sql(sql)
        result = self._cursor.executemany(sql, parameters)
        return self if result is self._cursor else result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _TransactionTripwireConnection:
    _FORBIDDEN_ATTRIBUTES = frozenset({"commit", "rollback", "executescript"})
    _FORBIDDEN_SQL = frozenset(
        {"BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE"}
    )

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def __getattribute__(self, name: str) -> Any:
        if name in object.__getattribute__(self, "_FORBIDDEN_ATTRIBUTES"):
            raise AssertionError(f"repository attempted transaction method {name}")
        return object.__getattribute__(self, name)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        self._refuse_transaction_sql(sql)
        return _TransactionTripwireCursor(
            self,
            self._connection.execute(sql, parameters),
        )

    def cursor(self, *args: Any, **kwargs: Any) -> _TransactionTripwireCursor:
        return _TransactionTripwireCursor(
            self,
            self._connection.cursor(*args, **kwargs),
        )

    def executemany(self, sql: str, parameters: Any) -> _TransactionTripwireCursor:
        self._refuse_transaction_sql(sql)
        return _TransactionTripwireCursor(
            self,
            self._connection.executemany(sql, parameters),
        )

    def _refuse_transaction_sql(self, sql: str) -> None:
        token = _first_sql_token(sql)
        if token in self._FORBIDDEN_SQL:
            raise AssertionError(f"repository attempted transaction SQL {token}")


def _application_row_counts(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, int], ...]:
    tables = tuple(
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' AND name <> 'schema_meta' ORDER BY name"
        )
    )
    return tuple(
        (
            table,
            int(connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]),
        )
        for table in tables
    )


def _first_sql_token(sql: str) -> str:
    remaining = sql
    while True:
        remaining = remaining.lstrip()
        if remaining.startswith("--"):
            newline = remaining.find("\n")
            if newline < 0:
                return ""
            remaining = remaining[newline + 1 :]
            continue
        if remaining.startswith("/*"):
            close = remaining.find("*/", 2)
            if close < 0:
                return ""
            remaining = remaining[close + 2 :]
            continue
        break
    if not remaining:
        return ""
    return remaining.split(None, 1)[0].rstrip(";").upper()


@pytest.mark.parametrize("operation_name", tuple(sorted(_operation_cases())))
def test_every_public_operation_leaves_transactions_with_caller(
    connection,
    operation_name: str,
) -> None:
    connection.commit()
    before = _application_row_counts(connection)
    connection.execute("BEGIN")
    assert connection.in_transaction
    guarded_connection = _TransactionTripwireConnection(connection)
    _seed_complete(guarded_connection)  # type: ignore[arg-type]
    outcome = _operation_cases()[operation_name](guarded_connection)
    assert isinstance(outcome, records.RepositoryOutcome)
    assert connection.in_transaction
    connection.rollback()
    assert not connection.in_transaction
    assert _application_row_counts(connection) == before


@pytest.mark.parametrize(
    "channel",
    ("connection", "cursor"),
)
@pytest.mark.parametrize(
    "sql",
    (
        "-- transaction\nCOMMIT",
        "/* transaction */ COMMIT",
        "-- first\n/* second */ ROLLBACK",
    ),
)
def test_transaction_tripwire_rejects_leading_comment_bypasses(
    connection,
    channel: str,
    sql: str,
) -> None:
    guarded_connection = _TransactionTripwireConnection(connection)
    executor = (
        guarded_connection.execute
        if channel == "connection"
        else guarded_connection.cursor().execute
    )
    with pytest.raises(AssertionError, match="transaction SQL"):
        executor(sql)


def test_every_public_operation_executes_the_schema_guard_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = _operation_cases()
    assert set(cases) == set(repository.__all__)

    class GuardSentinel(Exception):
        pass

    class TripwireConnection:
        def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
            del sql, parameters
            raise AssertionError("domain SQL ran before the schema guard")

    def stop(connection: Any) -> int:
        del connection
        raise GuardSentinel

    monkeypatch.setattr(repository, "_verify_schema_connection", stop)
    for operation in cases.values():
        with pytest.raises(GuardSentinel):
            operation(TripwireConnection())


def test_every_public_operation_refuses_a_tampered_catalog(connection) -> None:
    cases = _operation_cases()
    connection.execute("CREATE TABLE rogue_catalog_object (value INTEGER)")
    for operation in cases.values():
        with pytest.raises(SchemaInstallError, match="exact installed schema catalog"):
            operation(connection)


def _seed_direct_load_rows(connection: sqlite3.Connection) -> None:
    _seed_complete(connection)


def _assert_direct_query(
    connection: sqlite3.Connection,
    operation: Callable[[], records.RepositoryOutcome[Any]],
    table: str,
    predicate: str,
) -> None:
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    outcome = operation()
    connection.set_trace_callback(None)
    assert outcome.kind is records.RepositoryOutcomeKind.FOUND
    domain = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
        and f"FROM {table}" in statement
    ]
    assert len(domain) == 1
    statement = " ".join(domain[0].lower().split())
    assert predicate in statement
    assert "select *" not in statement
    plan = connection.execute(f"EXPLAIN QUERY PLAN {domain[0]}").fetchall()
    plan_text = " ".join(str(row[-1]) for row in plan).upper()
    assert "SEARCH" in plan_text
    assert "SCAN" not in plan_text
    assert "USE TEMP B-TREE" not in plan_text


def test_every_direct_loader_uses_its_production_key_and_index(connection) -> None:
    _seed_direct_load_rows(connection)
    owner = fixtures._owner(2, root_fill_key_id=None)
    cases: tuple[tuple[Callable[[], records.RepositoryOutcome[Any]], str, str], ...] = (
        (
            lambda: repository.load_execution_profile(
                connection, fixtures.EXECUTION_PROFILE_ID
            ),
            "execution_connection_profile",
            "where connection_profile_id =",
        ),
        (
            lambda: repository.load_market_source_profile(
                connection, fixtures.MARKET_PROFILE_ID
            ),
            "market_data_source_profile",
            "where market_source_profile_id =",
        ),
        (
            lambda: repository.load_application_generation(connection, fixtures.APP_ID),
            "application_generation",
            "where application_generation_id =",
        ),
        (
            lambda: repository.load_scope(connection, 1),
            "acquisition_scope",
            "where scope_id =",
        ),
        (
            lambda: repository.load_acquisition_generation(
                connection, fixtures.ACQUISITION_ID
            ),
            "acquisition_generation",
            "where acquisition_generation_id =",
        ),
        (
            lambda: repository.load_live_acquisition_generation(connection, 1),
            "acquisition_generation",
            "where scope_id = 1 and status = 'live'",
        ),
        (
            lambda: repository.load_acquisition_generation_current(
                connection, fixtures.ACQUISITION_ID
            ),
            "acquisition_generation_current",
            "where acquisition_generation_id =",
        ),
        (
            lambda: repository.load_symbol_controller(connection, 1),
            "symbol_controller",
            "where scope_id =",
        ),
        (
            lambda: repository.load_root_fill(connection, 1),
            "root_fill",
            "where root_fill_key_id =",
        ),
        (
            lambda: repository.load_root_fill_by_external(
                connection, fixtures.EXECUTION_PROFILE_ID, identity.RootFillId("root-1")
            ),
            "root_fill",
            "where execution_profile_id =",
        ),
        (
            lambda: repository.load_execution_fact(connection, 1),
            "execution_fact",
            "where fact_id =",
        ),
        (
            lambda: repository.load_execution_fact_by_source(
                connection,
                fixtures.EXECUTION_PROFILE_ID,
                identity.SourceEventId("event-1"),
            ),
            "execution_fact",
            "where execution_profile_id =",
        ),
        (
            lambda: repository.load_execution_fact_head(connection, 1),
            "execution_fact_head",
            "where root_fill_key_id =",
        ),
        (
            lambda: repository.load_venue_effect(connection, 2),
            "venue_effect",
            "where effect_id =",
        ),
        (
            lambda: repository.load_open_venue_effects(connection, 1),
            "venue_effect",
            "where scope_id = 1 and disposition = 'open'",
        ),
        (
            lambda: repository.load_venue_identity_owner(
                connection, fixtures.EXECUTION_PROFILE_ID, owner.owner_id
            ),
            "venue_identity_owner",
            "where execution_profile_id =",
        ),
        (
            lambda: repository.load_venue_identity_owners_for_effect(connection, 2),
            "venue_identity_owner",
            "where effect_id =",
        ),
        (
            lambda: repository.load_acquisition_root_route(connection, 1),
            "acquisition_root_route",
            "where root_fill_key_id =",
        ),
        (
            lambda: repository.load_dispatch_claim(connection, 2),
            "dispatch_claim",
            "where claim_id =",
        ),
        (
            lambda: repository.load_dispatch_claim_for_effect(connection, 2),
            "dispatch_claim",
            "where effect_id =",
        ),
        (
            lambda: repository.load_acceptance_set(connection, 77),
            "acceptance_set",
            "where acceptance_set_id =",
        ),
        (
            lambda: repository.load_acceptance_set_for_effect(connection, 2),
            "acceptance_set",
            "where effect_id =",
        ),
        (
            lambda: repository.load_acceptance_evidence(connection, 88),
            "acceptance_evidence",
            "where evidence_id =",
        ),
        (
            lambda: repository.load_latest_acceptance_evidence(connection, 77),
            "acceptance_evidence",
            "where acceptance_set_id =",
        ),
        (
            lambda: repository.load_closure_head(connection, 1, owner.owner_id),
            "closure_chain",
            "where scope_id = 1 and owner_external =",
        ),
        (
            lambda: repository.load_market_stream_authority(
                connection, fixtures.STREAM_ID
            ),
            "market_stream_authority",
            "where stream_generation_id =",
        ),
        (
            lambda: repository.load_market_cursor(connection, fixtures.STREAM_ID),
            "market_cursor",
            "where stream_generation_id =",
        ),
        (
            lambda: repository.load_protection_authority(connection, 1),
            "protection_authority",
            "where scope_id =",
        ),
    )
    for operation, table, predicate in cases:
        _assert_direct_query(connection, operation, table, predicate)


def test_same_family_growth_cannot_hide_a_root_full_scan(connection) -> None:
    fixtures._foundation(connection)
    target = fixtures._root()
    fixtures._expect_applied(
        repository.store_root_fill(
            connection, target, capability=_setup_write_capability(connection)
        )
    )
    connection.executemany(
        "INSERT INTO root_fill (root_fill_key_id, scope_id, application_generation_id,"
        " execution_profile_id, owner_generation_id, root_fill_external,"
        " economics_head_ordinal) VALUES (?, 1, ?, ?, ?, ?, 0)",
        (
            (
                root_id,
                fixtures.APP_ID.value,
                fixtures.EXECUTION_PROFILE_ID,
                fixtures.ACQUISITION_ID.value,
                f"unrelated-root-{root_id}",
            )
            for root_id in range(2, 202)
        ),
    )
    _assert_direct_query(
        connection,
        lambda: repository.load_root_fill(connection, 1),
        "root_fill",
        "where root_fill_key_id = 1",
    )


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.lower().split())


class _ProofRecordingCursor:
    def __init__(
        self,
        connection: _ProofRecordingConnection,
        cursor: Any,
    ) -> None:
        self._connection = connection
        self._cursor = cursor

    @property
    def connection(self) -> _ProofRecordingConnection:
        return self._connection

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        self._connection._record(sql, parameters)
        result = self._cursor.execute(sql, parameters)
        return self if result is self._cursor else result

    def executemany(self, sql: str, parameters: Any) -> Any:
        self._connection._record(sql, ("<executemany>",))
        result = self._cursor.executemany(sql, parameters)
        return self if result is self._cursor else result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class _ProofRecordingConnection:
    def __init__(self, connection: Any) -> None:
        self._connection = connection
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        self._record(sql, parameters)
        return _ProofRecordingCursor(
            self,
            self._connection.execute(sql, parameters),
        )

    def cursor(self, *args: Any, **kwargs: Any) -> _ProofRecordingCursor:
        return _ProofRecordingCursor(
            self,
            self._connection.cursor(*args, **kwargs),
        )

    def executemany(self, sql: str, parameters: Any) -> _ProofRecordingCursor:
        self._record(sql, ("<executemany>",))
        return _ProofRecordingCursor(
            self,
            self._connection.executemany(sql, parameters),
        )

    def executescript(self, sql: str) -> _ProofRecordingCursor:
        self._record(sql, ("<executescript>",))
        return _ProofRecordingCursor(
            self,
            self._connection.executescript(sql),
        )

    def _record(self, sql: str, parameters: tuple[Any, ...]) -> None:
        self.calls.append((sql, tuple(parameters)))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)


_SCHEMA_GUARD_CALLS = tuple(
    (_normalize_sql(sql), ())
    for sql in (
        "PRAGMA foreign_keys",
        "PRAGMA recursive_triggers",
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'",
        "SELECT schema_version, approved_ddl_sha256 FROM schema_meta",
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name",
    )
)


def _capture_proof_queries(
    connection: Any,
    proof_request: records.CurrentProofRequest,
    expected_shapes: tuple[str, ...],
    expected_parameters: tuple[tuple[Any, ...], ...],
) -> tuple[tuple[str, tuple[Any, ...]], ...]:
    recording = _ProofRecordingConnection(connection)
    outcome = repository.load_current_proof(recording, proof_request)
    assert outcome.kind is records.RepositoryOutcomeKind.FOUND
    assert outcome.record is not None
    normalized_calls = tuple(
        (_normalize_sql(statement), parameters)
        for statement, parameters in recording.calls
    )
    assert normalized_calls[: len(_SCHEMA_GUARD_CALLS)] == _SCHEMA_GUARD_CALLS
    proof_calls = recording.calls[len(_SCHEMA_GUARD_CALLS) :]
    assert len(proof_calls) == len(expected_shapes)
    assert len(proof_calls) == len(expected_parameters)
    for (statement, parameters), expected_shape, expected_values in zip(
        proof_calls,
        expected_shapes,
        expected_parameters,
        strict=True,
    ):
        normalized = _normalize_sql(statement)
        normalized = normalized.translate(str.maketrans("", "", '"`[]'))
        query_tail = "from " + normalized.split(" from ", 1)[1]
        query_tail = re.sub(r"'(?:''|[^'])*'", "?", query_tail)
        query_tail = re.sub(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", "?", query_tail)
        assert query_tail == expected_shape
        assert parameters == expected_values
        assert "select *" not in normalized
        plan = connection.execute(
            f"EXPLAIN QUERY PLAN {statement}",
            parameters,
        ).fetchall()
        plan_text = " ".join(str(row[-1]) for row in plan).upper()
        assert "SEARCH" in plan_text
        assert "SCAN" not in plan_text
        assert "USE TEMP B-TREE" not in plan_text
    return tuple(
        (_normalize_sql(statement), parameters) for statement, parameters in proof_calls
    )


_BASE_PROOF_QUERY_SHAPES = (
    "from application_generation where application_generation_id = ?",
    "from acquisition_scope where scope_id = ?",
    "from execution_connection_profile where connection_profile_id = ?",
    "from market_data_source_profile where market_source_profile_id = ?",
    "from kernel_checkpoint where application_generation_id = ?",
    "from symbol_controller where scope_id = ?",
    "from acquisition_generation where scope_id = ? and status = ?",
    "from acquisition_generation_current where acquisition_generation_id = ?",
    "from protection_authority where scope_id = ?",
    "from market_stream_authority where stream_generation_id = ?",
    "from market_cursor where stream_generation_id = ?",
)

_ROOT_PROOF_QUERY_SHAPES = _BASE_PROOF_QUERY_SHAPES + (
    "from root_fill where root_fill_key_id = ?",
    "from acquisition_root_route where root_fill_key_id = ?",
    "from execution_fact_head where root_fill_key_id = ?",
    "from execution_fact where fact_id = ?",
)

_EFFECT_PROOF_QUERY_SHAPES = _BASE_PROOF_QUERY_SHAPES + (
    "from venue_effect where effect_id = ?",
    "from dispatch_claim where effect_id = ?",
    "from venue_identity_owner where execution_profile_id = ? and owner_external = ?",
    "from acceptance_set where effect_id = ?",
    "from acceptance_evidence where acceptance_set_id = ?"
    " order by evidence_ordinal desc limit ?",
    "from closure_chain where scope_id = ? and owner_external = ?"
    " order by ordinal desc limit ?",
)

_BASE_PROOF_QUERY_PARAMETERS = (
    (fixtures.APP_ID.value,),
    (1,),
    (fixtures.EXECUTION_PROFILE_ID,),
    (fixtures.MARKET_PROFILE_ID,),
    (fixtures.APP_ID.value,),
    (1,),
    (1,),
    (fixtures.ACQUISITION_ID.value,),
    (1,),
    (fixtures.STREAM_ID.value,),
    (fixtures.STREAM_ID.value,),
)

_ROOT_PROOF_QUERY_PARAMETERS = _BASE_PROOF_QUERY_PARAMETERS + (
    (1,),
    (1,),
    (1,),
    (1,),
)

_EFFECT_PROOF_QUERY_PARAMETERS = _BASE_PROOF_QUERY_PARAMETERS + (
    (2,),
    (2,),
    (fixtures.EXECUTION_PROFILE_ID, "owner-2"),
    (2,),
    (77,),
    (1, "owner-2"),
)


def test_total_proof_uses_only_fixed_direct_key_queries_under_history_stress(
    connection,
) -> None:
    _seed_complete(connection)
    root_request = records.CurrentProofRequest(
        fixtures.APP_ID,
        1,
        root_fill_key_id=1,
    )
    effect_request = records.CurrentProofRequest(
        fixtures.APP_ID,
        1,
        effect_id=2,
        owner_id=identity.OrderId("owner-2"),
        require_acceptance=True,
        require_closure=True,
    )
    baseline_root = _capture_proof_queries(
        connection,
        root_request,
        _ROOT_PROOF_QUERY_SHAPES,
        _ROOT_PROOF_QUERY_PARAMETERS,
    )
    baseline_effect = _capture_proof_queries(
        connection,
        effect_request,
        _EFFECT_PROOF_QUERY_SHAPES,
        _EFFECT_PROOF_QUERY_PARAMETERS,
    )

    connection.executemany(
        "INSERT INTO root_fill (root_fill_key_id, scope_id, application_generation_id,"
        " execution_profile_id, owner_generation_id, root_fill_external,"
        " economics_head_ordinal) VALUES (?, 1, ?, ?, ?, ?, 0)",
        (
            (
                root_id,
                fixtures.APP_ID.value,
                fixtures.EXECUTION_PROFILE_ID,
                fixtures.ACQUISITION_ID.value,
                f"proof-stress-root-{root_id}",
            )
            for root_id in range(10, 510)
        ),
    )
    assert (
        _capture_proof_queries(
            connection,
            root_request,
            _ROOT_PROOF_QUERY_SHAPES,
            _ROOT_PROOF_QUERY_PARAMETERS,
        )
        == baseline_root
    )
    assert (
        _capture_proof_queries(
            connection,
            effect_request,
            _EFFECT_PROOF_QUERY_SHAPES,
            _EFFECT_PROOF_QUERY_PARAMETERS,
        )
        == baseline_effect
    )


def test_root_proof_binds_fact_head_id_not_root_coordinate(connection) -> None:
    fixtures._foundation(connection)
    root_key = 41
    fact_id = 7
    root = dataclasses.replace(
        fixtures._root(),
        root_fill_key_id=root_key,
        root_fill_id=identity.RootFillId("root-41"),
    )
    effect = fixtures._effect(1, controller_head=0, protection_version=1)
    owner = dataclasses.replace(
        fixtures._owner(1, root_fill_key_id=1),
        root_fill_key_id=root_key,
    )
    route = dataclasses.replace(
        _route(),
        root_fill_key_id=root_key,
        owner_id=owner.owner_id,
        observation_id=owner.observation_id,
    )
    fact = dataclasses.replace(
        fixtures._fact(),
        fact_id=fact_id,
        root_fill_key_id=root_key,
    )
    for operation, value in (
        (repository.store_root_fill, root),
        (repository.store_venue_effect, effect),
        (repository.store_venue_identity_owner, owner),
        (repository.store_acquisition_root_route, route),
        (repository.store_execution_fact, fact),
    ):
        fixtures._expect_applied(_apply_mutator(connection, operation, value))
    fixtures._expect_applied(
        repository.advance_protection_authority(
            connection,
            1,
            fixtures._protection(controller_head=1, version=2),
            capability=_setup_write_capability(connection),
        )
    )

    _capture_proof_queries(
        connection,
        records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            root_fill_key_id=root_key,
        ),
        _ROOT_PROOF_QUERY_SHAPES,
        _BASE_PROOF_QUERY_PARAMETERS
        + ((root_key,), (root_key,), (root_key,), (fact_id,)),
    )


class _HiddenReadConnection:
    def __init__(self, connection: sqlite3.Connection, hidden_sql: str) -> None:
        self._connection = connection
        self._hidden_sql = hidden_sql

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        if sql == self._hidden_sql:
            return self._connection.execute("SELECT 0")
        return self._connection.execute(sql, parameters)


@pytest.mark.parametrize(
    "hidden_sql",
    (
        "SELECT count(*) FROM 'execution_fact'",
        "SELECT count(*) FROM (execution_fact)",
        "SELECT count(*) FROM execution_fact, root_fill",
        "SELECT count(*) FROM aux.execution_fact",
    ),
)
def test_exact_prepared_call_gate_rejects_every_hidden_statement_form(
    connection,
    monkeypatch: pytest.MonkeyPatch,
    hidden_sql: str,
) -> None:
    _seed_complete(connection)
    accepted_select = repository._select_one_unchecked
    injected = False

    def inject_once(connection_arg, sql, parameters, build):
        nonlocal injected
        if not injected:
            injected = True
            connection_arg.execute(hidden_sql).fetchone()
        return accepted_select(connection_arg, sql, parameters, build)

    monkeypatch.setattr(repository, "_select_one_unchecked", inject_once)
    with pytest.raises(AssertionError):
        _capture_proof_queries(
            _HiddenReadConnection(connection, hidden_sql),
            records.CurrentProofRequest(fixtures.APP_ID, 1),
            _BASE_PROOF_QUERY_SHAPES,
            _BASE_PROOF_QUERY_PARAMETERS,
        )


def test_exact_prepared_call_gate_cannot_hide_a_cursor_capability_branch(
    connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_complete(connection)
    accepted_select = repository._select_one_unchecked
    injected = False

    def inject_cursor_once(connection_arg, sql, parameters, build):
        nonlocal injected
        if not injected and hasattr(connection_arg, "cursor"):
            injected = True
            connection_arg.cursor().execute(
                "SELECT count(*) FROM (execution_fact)"
            ).fetchone()
        return accepted_select(connection_arg, sql, parameters, build)

    monkeypatch.setattr(repository, "_select_one_unchecked", inject_cursor_once)
    with pytest.raises(AssertionError):
        _capture_proof_queries(
            connection,
            records.CurrentProofRequest(fixtures.APP_ID, 1),
            _BASE_PROOF_QUERY_SHAPES,
            _BASE_PROOF_QUERY_PARAMETERS,
        )


class _AbsentCursor:
    def fetchone(self) -> None:
        return None


class _OmittingConnection:
    def __init__(self, connection: sqlite3.Connection, table: str) -> None:
        self._connection = connection
        self._table = table

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()):
        normalized = " ".join(sql.lower().split())
        if normalized.startswith("select ") and f" from {self._table}" in normalized:
            return _AbsentCursor()
        return self._connection.execute(sql, parameters)


@pytest.mark.parametrize(
    ("omitted_table", "request_kind"),
    (
        ("execution_connection_profile", "base"),
        ("market_data_source_profile", "base"),
        ("application_generation", "base"),
        ("acquisition_scope", "base"),
        ("acquisition_generation", "base"),
        ("acquisition_generation_current", "base"),
        ("kernel_checkpoint", "base"),
        ("symbol_controller", "base"),
        ("protection_authority", "base"),
        ("market_stream_authority", "base"),
        ("market_cursor", "base"),
        ("root_fill", "root"),
        ("acquisition_root_route", "root"),
        ("execution_fact_head", "root"),
        ("execution_fact", "root"),
        ("venue_effect", "effect"),
        ("dispatch_claim", "effect"),
        ("venue_identity_owner", "effect"),
        ("acceptance_set", "effect"),
        ("acceptance_evidence", "effect"),
        ("closure_chain", "effect"),
    ),
)
def test_total_proof_refuses_each_independently_omitted_member(
    connection,
    omitted_table: str,
    request_kind: str,
) -> None:
    _seed_complete(connection)
    requests = {
        "base": records.CurrentProofRequest(fixtures.APP_ID, 1),
        "root": records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            root_fill_key_id=1,
        ),
        "effect": records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            effect_id=2,
            owner_id=identity.OrderId("owner-2"),
            require_acceptance=True,
            require_closure=True,
        ),
    }
    request = requests[request_kind]
    baseline = repository.load_current_proof(connection, request)
    assert baseline.kind is records.RepositoryOutcomeKind.FOUND
    assert baseline.record is not None

    outcome = repository.load_current_proof(
        _OmittingConnection(connection, omitted_table),  # type: ignore[arg-type]
        request,
    )
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert outcome.record is None


class _CorruptingCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor
        self._first = True

    def fetchone(self) -> tuple[Any, ...] | None:
        row = self._cursor.fetchone()
        if row is None or not self._first:
            return row
        self._first = False
        corrupted = list(row)
        corrupted[0] = object()
        return tuple(corrupted)


class _FailingProofMemberConnection:
    def __init__(
        self,
        connection: sqlite3.Connection,
        table: str,
        failure_mode: str,
    ) -> None:
        self._connection = connection
        self._table = table
        self._failure_mode = failure_mode

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        normalized = " ".join(sql.lower().split())
        targeted = normalized.startswith("select ") and re.search(
            rf"\bfrom\s+{re.escape(self._table)}\b",
            normalized,
        )
        if not targeted:
            return self._connection.execute(sql, parameters)
        if self._failure_mode == "read":
            raise sqlite3.DatabaseError(f"injected {self._table} read failure")
        return _CorruptingCursor(self._connection.execute(sql, parameters))


@pytest.mark.parametrize("failure_mode", ("read", "decode"))
@pytest.mark.parametrize(
    ("failed_table", "request_kind"),
    (
        ("execution_connection_profile", "base"),
        ("market_data_source_profile", "base"),
        ("application_generation", "base"),
        ("acquisition_scope", "base"),
        ("acquisition_generation", "base"),
        ("acquisition_generation_current", "base"),
        ("kernel_checkpoint", "base"),
        ("symbol_controller", "base"),
        ("protection_authority", "base"),
        ("market_stream_authority", "base"),
        ("market_cursor", "base"),
        ("root_fill", "root"),
        ("acquisition_root_route", "root"),
        ("execution_fact_head", "root"),
        ("execution_fact", "root"),
        ("venue_effect", "effect"),
        ("dispatch_claim", "effect"),
        ("venue_identity_owner", "effect"),
        ("acceptance_set", "effect"),
        ("acceptance_evidence", "effect"),
        ("closure_chain", "effect"),
    ),
)
def test_total_proof_fails_closed_for_each_member_read_or_decode_failure(
    connection,
    failed_table: str,
    request_kind: str,
    failure_mode: str,
) -> None:
    _seed_complete(connection)
    requests = {
        "base": records.CurrentProofRequest(fixtures.APP_ID, 1),
        "root": records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            root_fill_key_id=1,
        ),
        "effect": records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            effect_id=2,
            owner_id=identity.OrderId("owner-2"),
            require_acceptance=True,
            require_closure=True,
        ),
    }
    outcome = repository.load_current_proof(
        _FailingProofMemberConnection(
            connection,
            failed_table,
            failure_mode,
        ),  # type: ignore[arg-type]
        requests[request_kind],
    )
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert outcome.record is None


class _MutatingCursor:
    def __init__(self, cursor: Any, column: int, value: Any) -> None:
        self._cursor = cursor
        self._column = column
        self._value = value
        self._first = True

    def fetchone(self) -> tuple[Any, ...] | None:
        row = self._cursor.fetchone()
        if row is None or not self._first:
            return row
        self._first = False
        mutated = list(row)
        mutated[self._column] = self._value
        return tuple(mutated)


class _MutatingProofMemberConnection:
    def __init__(
        self,
        connection: sqlite3.Connection,
        table: str,
        column: int,
        value: Any,
    ) -> None:
        self._connection = connection
        self._table = table
        self._column = column
        self._value = value

    def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
        normalized = " ".join(sql.lower().split())
        if not (
            normalized.startswith("select ")
            and re.search(rf"\bfrom\s+{re.escape(self._table)}\b", normalized)
        ):
            return self._connection.execute(sql, parameters)
        return _MutatingCursor(
            self._connection.execute(sql, parameters),
            self._column,
            self._value,
        )


@pytest.mark.parametrize(
    ("table", "column", "value", "request_kind"),
    (
        ("protection_authority", 2, None, "base"),
        ("protection_authority", 3, None, "base"),
        ("protection_authority", 4, None, "base"),
        ("protection_authority", 5, None, "base"),
        ("protection_authority", 6, None, "base"),
        ("protection_authority", 7, None, "base"),
        ("protection_authority", 5, "00" * 32, "base"),
        ("market_cursor", 4, "00" * 32, "base"),
        ("execution_fact", 1, 999, "root"),
        ("execution_fact", 2, "generation-2", "root"),
        ("execution_fact", 3, "00" * 32, "root"),
        ("venue_effect", 6, "00" * 32, "effect"),
        ("venue_identity_owner", 1, "00" * 32, "effect"),
        ("acceptance_set", 1, 999, "effect"),
    ),
)
def test_total_proof_rejects_each_cross_record_contradiction(
    connection,
    table: str,
    column: int,
    value: Any,
    request_kind: str,
) -> None:
    _seed_complete(connection)
    requests = {
        "base": records.CurrentProofRequest(fixtures.APP_ID, 1),
        "root": records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            root_fill_key_id=1,
        ),
        "effect": records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            effect_id=2,
            owner_id=identity.OrderId("owner-2"),
            require_acceptance=True,
            require_closure=True,
        ),
    }
    outcome = repository.load_current_proof(
        _MutatingProofMemberConnection(
            connection,
            table,
            column,
            value,
        ),  # type: ignore[arg-type]
        requests[request_kind],
    )
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert outcome.record is None


def test_total_proof_accepts_an_all_null_active_stream_tuple(connection) -> None:
    for operation, value in (
        (repository.store_execution_profile, fixtures._execution_profile()),
        (repository.store_market_source_profile, fixtures._market_profile()),
        (repository.store_application_generation, fixtures._application()),
        (repository.store_scope, fixtures._scope()),
        (repository.store_acquisition_generation, fixtures._acquisition()),
        (repository.store_symbol_controller, fixtures._controller()),
        (
            repository.store_protection_authority,
            dataclasses.replace(
                fixtures._protection(),
                active_stream_generation_id=None,
                active_acquisition_generation_id=None,
                active_generation_mandate_commitment_sha256=None,
                active_source_profile_id=None,
                active_session_id=None,
                active_sequence_mode=None,
            ),
        ),
    ):
        fixtures._expect_applied(_apply_mutator(connection, operation, value))

    outcome = repository.load_current_proof(
        connection,
        records.CurrentProofRequest(fixtures.APP_ID, 1),
    )
    assert outcome.kind is records.RepositoryOutcomeKind.FOUND
    assert outcome.record is not None
    assert outcome.record.market_stream_authority is None
    assert outcome.record.market_cursor is None


def test_single_row_loader_refuses_a_second_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = (1, fixtures.APP_ID.value, fixtures.EXECUTION_PROFILE_ID, "AAPL")

    class Cursor:
        def __init__(self) -> None:
            self.rows = [row, row]

        def fetchone(self) -> tuple[Any, ...] | None:
            return self.rows.pop(0) if self.rows else None

    class DuplicateConnection:
        def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Cursor:
            del sql, parameters
            return Cursor()

    monkeypatch.setattr(repository, "_verify_schema_connection", lambda connection: 1)
    outcome = repository.load_scope(DuplicateConnection(), 1)  # type: ignore[arg-type]
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert outcome.record is None


def test_scope_proof_refuses_every_incomplete_foundation_stage(connection) -> None:
    proof_request = records.CurrentProofRequest(fixtures.APP_ID, 1)

    def assert_incomplete() -> None:
        outcome = repository.load_current_proof(connection, proof_request)
        assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
        assert outcome.record is None

    assert_incomplete()
    for operation, value in (
        (repository.store_execution_profile, fixtures._execution_profile()),
        (repository.store_market_source_profile, fixtures._market_profile()),
        (repository.store_application_generation, fixtures._application()),
        (repository.store_scope, fixtures._scope()),
        (repository.store_acquisition_generation, fixtures._acquisition()),
        (repository.store_symbol_controller, fixtures._controller()),
        (repository.store_market_stream_authority, fixtures._market_stream()),
        (repository.store_market_cursor, fixtures._cursor()),
    ):
        fixtures._expect_applied(_apply_mutator(connection, operation, value))
        assert_incomplete()

    fixtures._expect_applied(
        repository.store_protection_authority(
            connection,
            fixtures._protection(),
            capability=_setup_write_capability(connection),
        )
    )
    outcome = repository.load_current_proof(connection, proof_request)
    assert outcome.kind is records.RepositoryOutcomeKind.FOUND
    assert outcome.record is not None


@pytest.mark.parametrize(
    "proof_request",
    (
        records.CurrentProofRequest(fixtures.APP_ID, 1, root_fill_key_id=999),
        records.CurrentProofRequest(fixtures.APP_ID, 1, effect_id=999),
        records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            effect_id=2,
            owner_id=identity.OrderId("missing-owner"),
        ),
        records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            effect_id=1,
            require_acceptance=True,
        ),
        records.CurrentProofRequest(
            fixtures.APP_ID,
            1,
            effect_id=2,
            owner_id=identity.OrderId("owner-2"),
            require_closure=True,
        ),
    ),
)
def test_total_proof_omissions_fail_without_partial_records(
    connection, proof_request
) -> None:
    _seed_complete(connection)
    if proof_request.require_closure:
        connection.execute(
            "INSERT INTO venue_identity_owner VALUES"
            " (1, ?, 'spare-owner', 'spare-observation', 2, NULL, ?, 0)",
            (fixtures.EXECUTION_PROFILE_ID, fixtures.ACQUISITION_ID.value),
        )
        proof_request = dataclasses.replace(
            proof_request,
            owner_id=identity.OrderId("spare-owner"),
        )
    outcome = repository.load_current_proof(connection, proof_request)
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert outcome.record is None
