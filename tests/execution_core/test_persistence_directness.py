"""Mutation-surviving guard, cardinality, and direct-query proofs for WO-0167."""

from __future__ import annotations

import dataclasses
from pathlib import Path
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


def _evidence(effect_id: int) -> records.AcceptanceEvidenceRecord:
    return records.AcceptanceEvidenceRecord(
        effect_id,
        effect_id,
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


def _seed_complete(connection: sqlite3.Connection) -> None:
    fixtures._foundation(connection)
    fixtures._expect_applied(repository.store_root_fill(connection, fixtures._root()))
    effect1 = fixtures._effect(1, controller_head=0, protection_version=1)
    owner1 = fixtures._owner(1, root_fill_key_id=1)
    for operation, value in (
        (repository.store_venue_effect, effect1),
        (repository.store_venue_identity_owner, owner1),
        (repository.store_acquisition_root_route, _route()),
        (repository.store_execution_fact, fixtures._fact()),
    ):
        fixtures._expect_applied(operation(connection, value))

    protection_v2 = fixtures._protection(controller_head=1, version=2)
    fixtures._expect_applied(
        repository.advance_protection_authority(connection, 1, protection_v2)
    )
    effect2 = fixtures._effect(2, controller_head=1, protection_version=2)
    owner2 = fixtures._owner(2, root_fill_key_id=None)
    for operation, value in (
        (repository.store_venue_effect, effect2),
        (repository.store_venue_identity_owner, owner2),
        (repository.store_dispatch_claim, fixtures._claim(2)),
        (repository.store_acceptance_set, records.AcceptanceSetRecord(2, 2)),
        (repository.store_acceptance_evidence, _evidence(2)),
        (repository.store_closure, _closure(2)),
    ):
        fixtures._expect_applied(operation(connection, value))


def _operation_cases() -> dict[str, Callable[[Any], Any]]:
    effect = fixtures._effect(1, controller_head=0, protection_version=1)
    owner = fixtures._owner(1, root_fill_key_id=1)
    route = _route()
    evidence = _evidence(1)
    closure = _closure(1)
    return {
        "advance_kernel_checkpoint": lambda c: repository.advance_kernel_checkpoint(
            c, 1, fixtures._checkpoint(head=1, version=2)
        ),
        "advance_market_cursor": lambda c: repository.advance_market_cursor(
            c, 0, 0, fixtures._cursor(fixed=1, published=1)
        ),
        "advance_protection_authority": lambda c: (
            repository.advance_protection_authority(
                c, 1, fixtures._protection(version=2)
            )
        ),
        "advance_symbol_controller": lambda c: repository.advance_symbol_controller(
            c, 1, fixtures._controller(version=2)
        ),
        "advance_venue_effect": lambda c: repository.advance_venue_effect(
            c, "REQUESTED", "OPEN", effect
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
        "load_kernel_checkpoint": lambda c: repository.load_kernel_checkpoint(
            c, fixtures.APP_ID
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
            repository.retire_acquisition_generation(c, fixtures.ACQUISITION_ID)
        ),
        "store_acceptance_evidence": lambda c: repository.store_acceptance_evidence(
            c, evidence
        ),
        "store_acceptance_set": lambda c: repository.store_acceptance_set(
            c, records.AcceptanceSetRecord(1, 1)
        ),
        "store_acquisition_generation": lambda c: (
            repository.store_acquisition_generation(c, fixtures._acquisition())
        ),
        "store_acquisition_root_route": lambda c: (
            repository.store_acquisition_root_route(c, route)
        ),
        "store_application_generation": lambda c: (
            repository.store_application_generation(c, fixtures._application())
        ),
        "store_closure": lambda c: repository.store_closure(c, closure),
        "store_dispatch_claim": lambda c: repository.store_dispatch_claim(
            c, fixtures._claim(1)
        ),
        "store_execution_fact": lambda c: repository.store_execution_fact(
            c, fixtures._fact()
        ),
        "store_execution_profile": lambda c: repository.store_execution_profile(
            c, fixtures._execution_profile()
        ),
        "store_kernel_checkpoint": lambda c: repository.store_kernel_checkpoint(
            c, fixtures._checkpoint()
        ),
        "store_market_cursor": lambda c: repository.store_market_cursor(
            c, fixtures._cursor()
        ),
        "store_market_source_profile": lambda c: repository.store_market_source_profile(
            c, fixtures._market_profile()
        ),
        "store_market_stream_authority": lambda c: (
            repository.store_market_stream_authority(c, fixtures._market_stream())
        ),
        "store_protection_authority": lambda c: repository.store_protection_authority(
            c, fixtures._protection()
        ),
        "store_root_fill": lambda c: repository.store_root_fill(c, fixtures._root()),
        "store_scope": lambda c: repository.store_scope(c, fixtures._scope()),
        "store_symbol_controller": lambda c: repository.store_symbol_controller(
            c, fixtures._controller()
        ),
        "store_venue_effect": lambda c: repository.store_venue_effect(c, effect),
        "store_venue_identity_owner": lambda c: repository.store_venue_identity_owner(
            c, owner
        ),
    }


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
            lambda: repository.load_kernel_checkpoint(connection, fixtures.APP_ID),
            "kernel_checkpoint",
            "where application_generation_id =",
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
            lambda: repository.load_acceptance_set(connection, 2),
            "acceptance_set",
            "where acceptance_set_id =",
        ),
        (
            lambda: repository.load_acceptance_set_for_effect(connection, 2),
            "acceptance_set",
            "where effect_id =",
        ),
        (
            lambda: repository.load_acceptance_evidence(connection, 2),
            "acceptance_evidence",
            "where evidence_id =",
        ),
        (
            lambda: repository.load_latest_acceptance_evidence(connection, 2),
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
    fixtures._expect_applied(repository.store_root_fill(connection, target))
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
        (repository.store_kernel_checkpoint, fixtures._checkpoint()),
        (repository.store_symbol_controller, fixtures._controller()),
        (repository.store_market_stream_authority, fixtures._market_stream()),
        (repository.store_market_cursor, fixtures._cursor()),
    ):
        fixtures._expect_applied(operation(connection, value))
        assert_incomplete()

    fixtures._expect_applied(
        repository.store_protection_authority(connection, fixtures._protection())
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
