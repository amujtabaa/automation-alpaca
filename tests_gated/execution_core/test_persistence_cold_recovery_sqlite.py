"""Held fresh-file proof for the WO-0169 cold startup transaction chain."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
import sqlite3

from approved_schema_digest import (
    open_approved_sqlite_connection,
    require_approved_ddl_execution,
)
from app.execution_core import identity
from app.execution_core import venue
from app.execution_core.persistence import checkpoint_codec
from app.execution_core.persistence import market_recovery
from app.execution_core.persistence import operations
from app.execution_core.persistence import records
from app.execution_core.persistence import repository
from app.execution_core.persistence import startup
from app.execution_core.persistence.schema import install_schema
import persistence_setup_support as setup_support
import test_persistence_cold_recovery as cold_fakes
import test_persistence_startup_hydration as hydration_fixtures


def _open_database(path: Path) -> sqlite3.Connection:
    connection = open_approved_sqlite_connection(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    return connection


def _store_setup_record(
    connection: sqlite3.Connection,
    operation: Callable[..., records.RepositoryOutcome[object]],
    record: object,
) -> None:
    outcome = operation(
        connection,
        record,
        capability=setup_support.issue_setup_write_capability(connection),
    )
    assert outcome.kind is records.RepositoryOutcomeKind.APPLIED, (
        getattr(operation, "__name__", repr(operation)),
        outcome.kind,
    )


def _install_claimed_c0(
    path: Path,
) -> tuple[
    startup.StartupRequest,
    records.KernelCheckpointRecord,
    identity.SessionId,
]:
    source_proof, book, authority_state, owners = (
        hydration_fixtures._active_claimed_projection_inputs()
    )
    selection = source_proof._selection
    connection = _open_database(path)
    install_schema(
        connection,
        approved_ddl_sha256=require_approved_ddl_execution(),
    )
    for operation, record in (
        (repository.store_execution_profile, source_proof.execution_profile),
        (repository.store_market_source_profile, source_proof.market_source_profile),
        (
            repository.store_application_generation,
            source_proof.application_generation,
        ),
        (repository.store_scope, selection.scopes[0]),
        (repository.store_acquisition_generation, selection.live_generations[0]),
        (repository.store_symbol_controller, selection.controllers[0]),
        (repository.store_market_stream_authority, selection.streams[0]),
        (repository.store_protection_authority, selection.protection_authorities[0]),
        (
            repository.store_venue_effect,
            replace(selection.effects[0], lifecycle_state="REQUESTED"),
        ),
        (repository.store_dispatch_claim, selection.claims[0]),
    ):
        _store_setup_record(connection, operation, record)
    connection.commit()

    connection.execute("BEGIN")
    selected = repository.select_runtime_checkpoint(
        connection,
        records.RuntimeCheckpointSelectionRequest(
            source_proof.request.application_generation_id,
            source_proof.request.execution_profile_id,
            source_proof.request.market_source_profile_id,
            None,
        ),
    )
    assert selected.kind is records.RepositoryOutcomeKind.FOUND
    assert type(selected.record) is records.RuntimeCheckpointSelectionProof
    proof = selected.record
    assert tuple(item.effect_external for item in proof._selection.effects) == (
        identity.EffectId("effect-1"),
    )
    assert tuple(item.claim_occurrence_id for item in proof._selection.claims) == (
        identity.ClaimOccurrenceId("occurrence-effect-1"),
    )
    envelope = checkpoint_codec._project_runtime_checkpoint(
        proof,
        book,
        authority_state,  # type: ignore[arg-type]
        owners,
    )
    stored = repository.store_runtime_checkpoint(
        connection,
        proof,
        envelope,
        capability=setup_support.issue_setup_write_capability(connection),
    )
    assert stored.kind is records.RepositoryOutcomeKind.APPLIED
    assert type(stored.record) is records.RuntimeCheckpointWriteReceipt
    checkpoint = stored.record.resulting_checkpoint
    connection.commit()
    connection.close()
    return (
        startup.StartupRequest(
            source_proof.request.application_generation_id,
            source_proof.request.execution_profile_id,
            source_proof.request.market_source_profile_id,
        ),
        checkpoint,
        selection.streams[0].session_id,
    )


class _FileDatastore(startup._StartupDatastorePort):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.open_count = 0

    def open(self) -> sqlite3.Connection:
        self.open_count += 1
        return _open_database(self.path)


class _AcknowledgingQueries(market_recovery.EffectQueryPort):
    def __init__(self, session_id: identity.SessionId) -> None:
        self.session_id = session_id
        self.requests: list[market_recovery.EffectQueryRequest] = []

    def query(
        self,
        request: market_recovery.EffectQueryRequest,
    ) -> market_recovery.EffectQueryResult:
        self.requests.append(request)
        return market_recovery.EffectQueryResult(
            request,
            market_recovery.EffectQueryDisposition.RESOLVED,
            operations.VenueRecoveryOperation(
                operations.VenueOperationCoordinates(
                    request.application_generation_id,
                    request.execution_profile_id,
                    request.scope_id,
                    self.session_id,
                ),
                venue.RecordTransportOutcome(
                    identity.VenueInputId("wo0169-acknowledged-query"),
                    request.effect_id,
                    venue.BrokerEffectState.ACKNOWLEDGED,
                ),
            ),
        )


def _checkpoint_state(
    path: Path,
) -> tuple[int, int, str, int, str]:
    connection = _open_database(path)
    row = connection.execute(
        "SELECT currentness_head_ordinal, checkpoint_version_ordinal, "
        "checkpoint_sha256 FROM kernel_checkpoint"
    ).fetchone()
    payload_count = int(
        connection.execute(
            "SELECT count(*) FROM runtime_checkpoint_payload"
        ).fetchone()[0]
    )
    lifecycle = connection.execute(
        "SELECT lifecycle_state FROM venue_effect WHERE effect_external = ?",
        ("effect-1",),
    ).fetchone()
    connection.close()
    assert row is not None and lifecycle is not None
    return int(row[0]), int(row[1]), str(row[2]), payload_count, str(lifecycle[0])


def test_cold_startup_commits_c1_then_reopens_as_exact_replay(tmp_path: Path) -> None:
    database = tmp_path / "wo0169-cold-startup.db"
    request, c0, session_id = _install_claimed_c0(database)
    events: list[str] = []
    first_owner = cold_fakes._Owner(events)
    first_queries = _AcknowledgingQueries(session_id)
    first_datastore = _FileDatastore(database)

    first = startup.start_startup(
        request,
        owner_lock=first_owner,
        datastore=first_datastore,
        effect_queries=first_queries,
        market_source=cold_fakes._NoMarketSource(),
    )

    assert first.disposition is startup.StartupDisposition.SERVING
    assert first.successor_context is not None
    assert first.owner_lease is not None
    assert first_datastore.open_count == 1
    assert len(first_queries.requests) == 1
    assert first.successor_context.expected_checkpoint.checkpoint_version_ordinal == (
        c0.checkpoint_version_ordinal + 1
    )
    first_owner.release(first.owner_lease)

    c1 = _checkpoint_state(database)
    assert c1[1] == c0.checkpoint_version_ordinal + 1
    assert c1[2] == first.successor_context.expected_checkpoint.checkpoint_sha256
    assert c1[3] == 2
    assert c1[4] == "ACKNOWLEDGED"

    second_owner = cold_fakes._Owner(events)
    second_queries = _AcknowledgingQueries(session_id)
    second_datastore = _FileDatastore(database)
    second = startup.start_startup(
        request,
        owner_lock=second_owner,
        datastore=second_datastore,
        effect_queries=second_queries,
        market_source=cold_fakes._NoMarketSource(),
    )

    assert second.disposition is startup.StartupDisposition.SERVING
    assert second.successor_context is not None
    assert second.owner_lease is not None
    assert second_datastore.open_count == 1
    assert second_queries.requests == []
    assert _checkpoint_state(database) == c1
    assert second.successor_context.expected_checkpoint == (
        first.successor_context.expected_checkpoint
    )
    second_owner.release(second.owner_lease)
