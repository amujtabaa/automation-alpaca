"""Failure-capable contracts for the complete WO-0167 repository boundary."""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

import pytest

from app.execution_core import identity, profiles, values
from app.execution_core.persistence import records
import app.execution_core.persistence.repository as repository
from app.execution_core.persistence.schema import install_schema, schema_ddl_digest


APP_ID = identity.ApplicationGenerationId("generation-1")
EXECUTION_PROFILE_ID = "cd" * 32
MARKET_PROFILE_ID = "ef" * 32
ACQUISITION_ID = identity.AcquisitionGenerationId("12" * 32)
STREAM_ID = identity.MarketStreamGenerationId("34" * 32)
SESSION_ID = identity.SessionId("session-1")


@pytest.fixture()
def connection(tmp_path: Path):
    connection = sqlite3.connect(tmp_path / "wo167-repository.db")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    install_schema(connection, approved_ddl_sha256=schema_ddl_digest())
    try:
        yield connection
    finally:
        connection.close()


def _execution_profile() -> profiles.ExecutionConnectionProfile:
    return profiles.ExecutionConnectionProfile(
        connection_profile_id=EXECUTION_PROFILE_ID,
        application_generation=APP_ID.value,
        broker_provider="ALPACA",
        environment_class="PAPER",
        account_identity="aa" * 32,
        trade_command_origin="https://trade.example.com",
        order_query_origin="https://query.example.com",
        order_event_origin="https://stream.example.com",
        credential_handle_fingerprint="bb" * 32,
        adapter_contract_version="1.0.0",
        capability_profile_sha256="cc" * 32,
        deployment_identity="dd" * 32,
    )


def _market_profile() -> profiles.MarketDataSourceProfile:
    return profiles.MarketDataSourceProfile(
        market_source_profile_id=MARKET_PROFILE_ID,
        provider="ALPACA",
        environment_or_feed="iex-feed",
        source_origin="https://feed.example.com",
        entitlement_class="IEX",
        normalization_contract_version="1.0.0",
        data_capability_profile_sha256="ff" * 32,
    )


def _application() -> records.ApplicationGenerationRecord:
    return records.ApplicationGenerationRecord(
        APP_ID,
        EXECUTION_PROFILE_ID,
        MARKET_PROFILE_ID,
        1,
    )


def _scope() -> records.ScopeRecord:
    return records.ScopeRecord(
        1, APP_ID, EXECUTION_PROFILE_ID, identity.SymbolId("AAPL")
    )


def _acquisition() -> records.AcquisitionGenerationRecord:
    return records.AcquisitionGenerationRecord(
        ACQUISITION_ID,
        1,
        "LIVE",
        1,
        None,
        "9a" * 32,
        "9b" * 32,
    )


def _controller(*, head: int = 0, version: int = 1) -> records.SymbolControllerRecord:
    return records.SymbolControllerRecord(
        1,
        APP_ID,
        EXECUTION_PROFILE_ID,
        ACQUISITION_ID,
        0,
        "CONSISTENT",
        head,
        version,
        "9b" * 32,
    )


def _checkpoint(*, head: int = 0, version: int = 1) -> records.KernelCheckpointRecord:
    return records.KernelCheckpointRecord(
        APP_ID, head, f"{70 + version:02x}" * 32, version
    )


def _market_stream() -> records.MarketStreamAuthorityRecord:
    return records.MarketStreamAuthorityRecord(
        STREAM_ID,
        1,
        APP_ID,
        ACQUISITION_ID,
        "9a" * 32,
        MARKET_PROFILE_ID,
        SESSION_ID,
        "SEQUENCED",
    )


def _cursor(*, fixed: int = 0, published: int = 0) -> records.MarketCursorRecord:
    return records.MarketCursorRecord(
        STREAM_ID,
        1,
        APP_ID,
        ACQUISITION_ID,
        "9a" * 32,
        MARKET_PROFILE_ID,
        SESSION_ID,
        "SEQUENCED",
        fixed,
        published,
    )


def _protection(
    *, controller_head: int = 0, version: int = 1
) -> records.ProtectionAuthorityRecord:
    return records.ProtectionAuthorityRecord(
        1,
        "NORMAL",
        STREAM_ID,
        ACQUISITION_ID,
        "9a" * 32,
        MARKET_PROFILE_ID,
        SESSION_ID,
        "SEQUENCED",
        controller_head,
        f"{80 + version:02x}" * 32,
        version,
    )


def _root() -> records.RootFillRecord:
    return records.RootFillRecord(
        1,
        1,
        APP_ID,
        EXECUTION_PROFILE_ID,
        ACQUISITION_ID,
        identity.RootFillId("root-1"),
        None,
        None,
        None,
        None,
        None,
        None,
        0,
    )


def _price() -> values.ReportedPrice:
    scale = values.PriceScale(Decimal("0.01"))
    return values.ReportedPrice(
        values.PriceUnits(10100),
        scale,
        values.TickMetadata(values.PriceUnits(1), scale),
    )


def _fact() -> records.ExecutionFactRecord:
    return records.ExecutionFactRecord(
        1,
        1,
        APP_ID,
        EXECUTION_PROFILE_ID,
        1,
        identity.SourceEventId("event-1"),
        identity.OrderId("order-1"),
        "BUY",
        "FILL",
        "BROKER_AUTHORITATIVE",
        values.Quantity(10),
        _price(),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        1,
    )


def _effect(
    effect_id: int, *, controller_head: int, protection_version: int
) -> records.VenueEffectRecord:
    return records.VenueEffectRecord(
        effect_id,
        identity.EffectId(f"effect-{effect_id}"),
        1,
        APP_ID,
        EXECUTION_PROFILE_ID,
        ACQUISITION_ID,
        "9a" * 32,
        controller_head,
        protection_version,
        "NORMAL",
        identity.RequestOccurrenceId(f"request-{effect_id}"),
        identity.MandateId(f"mandate-{effect_id}"),
        "SUBMIT",
        identity.ClientOrderId(f"client-{effect_id}"),
        None,
        "BUY",
        values.Quantity(10),
        bytes([effect_id]),
        "REQUESTED",
        "OPEN",
        None,
        None,
        None,
        None,
        effect_id,
    )


def _owner(
    effect_id: int, *, root_fill_key_id: int | None
) -> records.VenueIdentityOwnerRecord:
    return records.VenueIdentityOwnerRecord(
        1,
        EXECUTION_PROFILE_ID,
        identity.OrderId(f"owner-{effect_id}"),
        identity.VenueObservationId(f"observation-{effect_id}"),
        effect_id,
        root_fill_key_id,
        ACQUISITION_ID,
        False,
    )


def _claim(effect_id: int) -> records.DispatchClaimRecord:
    return records.DispatchClaimRecord(
        effect_id,
        effect_id,
        EXECUTION_PROFILE_ID,
        identity.ClaimOccurrenceId(f"claim-{effect_id}"),
        effect_id,
    )


def _expect_applied(outcome: records.RepositoryOutcome[Any]) -> None:
    assert outcome == records.RepositoryOutcome(records.RepositoryOutcomeKind.APPLIED)


def _foundation(connection: sqlite3.Connection) -> None:
    for operation, value in (
        (repository.store_execution_profile, _execution_profile()),
        (repository.store_market_source_profile, _market_profile()),
        (repository.store_application_generation, _application()),
        (repository.store_scope, _scope()),
        (repository.store_acquisition_generation, _acquisition()),
        (repository.store_kernel_checkpoint, _checkpoint()),
        (repository.store_symbol_controller, _controller()),
        (repository.store_market_stream_authority, _market_stream()),
        (repository.store_market_cursor, _cursor()),
        (repository.store_protection_authority, _protection()),
    ):
        _expect_applied(operation(connection, value))


def _assert_found(outcome: records.RepositoryOutcome[Any], expected: Any) -> None:
    assert outcome.kind is records.RepositoryOutcomeKind.FOUND
    assert outcome.record == expected


def test_exact_exports_and_outcome_invariants() -> None:
    assert {name for name in vars(repository) if not name.startswith("_")} == set(
        repository.__all__
    )
    assert {name for name in vars(records) if not name.startswith("_")} == set(
        records.__all__
    )
    with pytest.raises(ValueError):
        records.RepositoryOutcome(records.RepositoryOutcomeKind.FOUND)
    with pytest.raises(ValueError):
        records.RepositoryOutcome(records.RepositoryOutcomeKind.ABSENT, object())


def _import_probe(
    repo_root: Path, scratch: Path, *, mutate: bool
) -> subprocess.CompletedProcess[str]:
    script = f"""
import os
from pathlib import Path
import sys
root = Path({str(repo_root)!r})
scratch = Path({str(scratch)!r})
sys.path.insert(0, str(root))
source_path = root / 'app/execution_core/persistence/repository.py'
source = source_path.read_text(encoding='utf-8')
import app.execution_core.persistence
scratch.mkdir(parents=True, exist_ok=True)
before_env = dict(os.environ)
before_files = set(scratch.rglob('*'))
if {mutate!r}:
    insertion = "\\nopen(" + repr(str(scratch / 'mutant-write')) + ", 'w').write('x')\\n"
    source = source.replace('from __future__ import annotations as _annotations', 'from __future__ import annotations as _annotations' + insertion, 1)
    namespace = {{'__name__': 'app.execution_core.persistence._repository_mutant', '__package__': 'app.execution_core.persistence'}}
    exec(compile(source, str(source_path), 'exec'), namespace)
else:
    __import__('app.execution_core.persistence.repository')
after_files = set(scratch.rglob('*'))
assert dict(os.environ) == before_env
assert after_files == before_files
assert 'sqlite3' not in sys.modules
"""
    return subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_repository_import_is_inert_and_mutant_is_killed(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    actual = _import_probe(repo_root, tmp_path / "actual", mutate=False)
    assert actual.returncode == 0, actual.stderr
    mutant = _import_probe(repo_root, tmp_path / "mutant", mutate=True)
    assert mutant.returncode != 0
    assert "AssertionError" in mutant.stderr


def test_profiles_application_scope_generation_and_current_round_trip(
    connection,
) -> None:
    _foundation(connection)
    for outcome, expected in (
        (
            repository.load_execution_profile(connection, EXECUTION_PROFILE_ID),
            _execution_profile(),
        ),
        (
            repository.load_market_source_profile(connection, MARKET_PROFILE_ID),
            _market_profile(),
        ),
        (repository.load_application_generation(connection, APP_ID), _application()),
        (repository.load_scope(connection, 1), _scope()),
        (
            repository.load_acquisition_generation(connection, ACQUISITION_ID),
            _acquisition(),
        ),
        (repository.load_live_acquisition_generation(connection, 1), _acquisition()),
        (repository.load_kernel_checkpoint(connection, APP_ID), _checkpoint()),
        (repository.load_symbol_controller(connection, 1), _controller()),
        (
            repository.load_market_stream_authority(connection, STREAM_ID),
            _market_stream(),
        ),
        (repository.load_market_cursor(connection, STREAM_ID), _cursor()),
        (repository.load_protection_authority(connection, 1), _protection()),
    ):
        _assert_found(outcome, expected)

    current = repository.load_acquisition_generation_current(connection, ACQUISITION_ID)
    _assert_found(
        current,
        records.AcquisitionGenerationCurrentRecord(ACQUISITION_ID, 1, 0, 0, 1),
    )
    assert "store_acquisition_generation_current" not in repository.__all__
    assert "store_execution_fact_head" not in repository.__all__


def test_all_remaining_families_and_total_current_proof_round_trip(connection) -> None:
    _foundation(connection)
    _expect_applied(repository.store_root_fill(connection, _root()))

    first_effect = _effect(1, controller_head=0, protection_version=1)
    first_owner = _owner(1, root_fill_key_id=1)
    _expect_applied(repository.store_venue_effect(connection, first_effect))
    _expect_applied(repository.store_venue_identity_owner(connection, first_owner))
    route = records.AcquisitionRootRouteRecord(
        1,
        1,
        APP_ID,
        EXECUTION_PROFILE_ID,
        ACQUISITION_ID,
        1,
        first_owner.owner_id,
        first_owner.observation_id,
    )
    _expect_applied(repository.store_acquisition_root_route(connection, route))
    _expect_applied(repository.store_execution_fact(connection, _fact()))

    controller = repository.load_symbol_controller(connection, 1).record
    assert isinstance(controller, records.SymbolControllerRecord)
    assert controller.currentness_head_ordinal == 1
    protection_v2 = _protection(controller_head=1, version=2)
    _expect_applied(
        repository.advance_protection_authority(connection, 1, protection_v2)
    )

    effect = _effect(2, controller_head=1, protection_version=2)
    owner = _owner(2, root_fill_key_id=None)
    claim = _claim(2)
    acceptance = records.AcceptanceSetRecord(2, 2)
    evidence = records.AcceptanceEvidenceRecord(
        2,
        2,
        2,
        "OBSERVATION",
        None,
        "a2" * 32,
        2,
        None,
        None,
    )
    closure = records.ClosureChainRecord(
        2,
        1,
        owner.owner_id,
        1,
        2,
        "TERMINAL_LEG",
        None,
    )
    for operation, value in (
        (repository.store_venue_effect, effect),
        (repository.store_venue_identity_owner, owner),
        (repository.store_dispatch_claim, claim),
        (repository.store_acceptance_set, acceptance),
        (repository.store_acceptance_evidence, evidence),
        (repository.store_closure, closure),
    ):
        _expect_applied(operation(connection, value))

    claimed_effect = dataclasses.replace(effect, lifecycle_state="DISPATCH_CLAIMED")
    root_after_fact = repository.load_root_fill(connection, 1).record
    assert isinstance(root_after_fact, records.RootFillRecord)
    assert root_after_fact.current_quantity == values.Quantity(10)
    assert root_after_fact.current_price == _price()

    for outcome, expected in (
        (
            repository.load_root_fill_by_external(
                connection, EXECUTION_PROFILE_ID, identity.RootFillId("root-1")
            ),
            root_after_fact,
        ),
        (repository.load_execution_fact(connection, 1), _fact()),
        (
            repository.load_execution_fact_by_source(
                connection, EXECUTION_PROFILE_ID, identity.SourceEventId("event-1")
            ),
            _fact(),
        ),
        (
            repository.load_execution_fact_head(connection, 1),
            records.ExecutionFactHeadRecord(1, 1, 1),
        ),
        (repository.load_venue_effect(connection, 2), claimed_effect),
        (
            repository.load_venue_identity_owner(
                connection, EXECUTION_PROFILE_ID, owner.owner_id
            ),
            owner,
        ),
        (repository.load_acquisition_root_route(connection, 1), route),
        (repository.load_dispatch_claim_for_effect(connection, 2), claim),
        (repository.load_acceptance_set_for_effect(connection, 2), acceptance),
        (repository.load_latest_acceptance_evidence(connection, 2), evidence),
        (repository.load_closure_head(connection, 1, owner.owner_id), closure),
    ):
        _assert_found(outcome, expected)

    proof = repository.load_current_proof(
        connection,
        records.CurrentProofRequest(
            APP_ID,
            1,
            root_fill_key_id=1,
            effect_id=2,
            owner_id=owner.owner_id,
            require_acceptance=True,
            require_closure=True,
        ),
    )
    assert proof.kind is records.RepositoryOutcomeKind.FOUND
    assert proof.record is not None
    assert proof.record.current_execution_fact == _fact()
    assert proof.record.dispatch_claim == claim
    assert proof.record.closure_head == closure


def test_mutable_rows_use_expected_version_and_caller_owns_rollback(connection) -> None:
    _foundation(connection)
    connection.commit()
    connection.execute("BEGIN")
    _expect_applied(
        repository.advance_kernel_checkpoint(
            connection, 1, _checkpoint(head=1, version=2)
        )
    )
    _expect_applied(
        repository.advance_market_cursor(
            connection, 0, 0, _cursor(fixed=1, published=1)
        )
    )
    _expect_applied(
        repository.advance_symbol_controller(connection, 1, _controller(version=2))
    )
    _expect_applied(
        repository.advance_protection_authority(connection, 1, _protection(version=2))
    )
    connection.rollback()
    _assert_found(repository.load_kernel_checkpoint(connection, APP_ID), _checkpoint())
    _assert_found(repository.load_market_cursor(connection, STREAM_ID), _cursor())
    _assert_found(repository.load_symbol_controller(connection, 1), _controller())
    _assert_found(repository.load_protection_authority(connection, 1), _protection())

    stale = repository.advance_kernel_checkpoint(
        connection, 9, _checkpoint(head=1, version=2)
    )
    assert stale.kind is records.RepositoryOutcomeKind.CONFLICT


def test_effect_transition_uses_expected_state(connection) -> None:
    _foundation(connection)
    effect = _effect(1, controller_head=0, protection_version=1)
    _expect_applied(repository.store_venue_effect(connection, effect))
    _expect_applied(repository.store_dispatch_claim(connection, _claim(1)))
    claimed = dataclasses.replace(effect, lifecycle_state="DISPATCH_CLAIMED")
    acknowledged = dataclasses.replace(claimed, lifecycle_state="ACKNOWLEDGED")
    _expect_applied(
        repository.advance_venue_effect(
            connection,
            "DISPATCH_CLAIMED",
            "OPEN",
            acknowledged,
        )
    )
    stale = repository.advance_venue_effect(
        connection,
        "DISPATCH_CLAIMED",
        "OPEN",
        acknowledged,
    )
    assert stale.kind is records.RepositoryOutcomeKind.CONFLICT
    _assert_found(repository.load_venue_effect(connection, 1), acknowledged)


def test_duplicate_is_conflict_but_malformed_authority_is_integrity(connection) -> None:
    _foundation(connection)
    duplicate = repository.store_scope(connection, _scope())
    assert duplicate.kind is records.RepositoryOutcomeKind.CONFLICT

    _expect_applied(
        repository.store_scope(
            connection,
            records.ScopeRecord(
                2, APP_ID, EXECUTION_PROFILE_ID, identity.SymbolId("MSFT")
            ),
        )
    )
    malformed = dataclasses.replace(
        _acquisition(),
        acquisition_generation_id=identity.AcquisitionGenerationId("13" * 32),
        scope_id=2,
        mandate_commitment_sha256="not-a-digest",
    )
    refused = repository.store_acquisition_generation(connection, malformed)
    assert refused.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert refused.record is None

    wrong_type = dataclasses.replace(_scope(), symbol="AAPL")  # type: ignore[arg-type]
    refused_before_sql = repository.store_scope(connection, wrong_type)
    assert refused_before_sql.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE


def test_every_insert_owned_family_reports_duplicate_contention(connection) -> None:
    _foundation(connection)
    foundation_duplicates = (
        repository.store_execution_profile(connection, _execution_profile()),
        repository.store_market_source_profile(connection, _market_profile()),
        repository.store_application_generation(connection, _application()),
        repository.store_scope(connection, _scope()),
        repository.store_acquisition_generation(connection, _acquisition()),
        repository.store_kernel_checkpoint(connection, _checkpoint()),
        repository.store_symbol_controller(connection, _controller()),
        repository.store_market_stream_authority(connection, _market_stream()),
        repository.store_market_cursor(connection, _cursor()),
        repository.store_protection_authority(connection, _protection()),
    )
    assert {outcome.kind for outcome in foundation_duplicates} == {
        records.RepositoryOutcomeKind.CONFLICT
    }

    root = _root()
    effect = _effect(1, controller_head=0, protection_version=1)
    owner = _owner(1, root_fill_key_id=1)
    route = records.AcquisitionRootRouteRecord(
        1,
        1,
        APP_ID,
        EXECUTION_PROFILE_ID,
        ACQUISITION_ID,
        1,
        owner.owner_id,
        owner.observation_id,
    )
    claim = _claim(1)
    acceptance = records.AcceptanceSetRecord(1, 1)
    evidence = records.AcceptanceEvidenceRecord(
        1,
        1,
        1,
        "OBSERVATION",
        None,
        "a1" * 32,
        1,
        None,
        None,
    )
    closure = records.ClosureChainRecord(
        1,
        1,
        owner.owner_id,
        1,
        1,
        "TERMINAL_LEG",
        None,
    )
    owned = (
        (repository.store_root_fill, root),
        (repository.store_venue_effect, effect),
        (repository.store_venue_identity_owner, owner),
        (repository.store_acquisition_root_route, route),
        (repository.store_dispatch_claim, claim),
        (repository.store_execution_fact, _fact()),
        (repository.store_acceptance_set, acceptance),
        (repository.store_acceptance_evidence, evidence),
        (repository.store_closure, closure),
    )
    for operation, value in owned:
        _expect_applied(operation(connection, value))
        duplicate = operation(connection, value)
        assert duplicate.kind is records.RepositoryOutcomeKind.CONFLICT, (
            operation.__name__
        )


def test_profile_decoder_rejects_a_valid_shape_with_wrong_commitment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _execution_profile()
    row = (
        profile.connection_profile_id,
        profile.application_generation,
        profile.broker_provider,
        profile.environment_class,
        profile.account_identity,
        profile.trade_command_origin,
        profile.order_query_origin,
        profile.order_event_origin,
        profile.credential_handle_fingerprint,
        profile.adapter_contract_version,
        profile.capability_profile_sha256,
        profile.deployment_identity,
        "00" * 32,
    )

    class Cursor:
        def __init__(self) -> None:
            self.rows = [row]

        def fetchone(self) -> tuple[Any, ...] | None:
            return self.rows.pop(0) if self.rows else None

    class ForgedConnection:
        def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Cursor:
            del sql, parameters
            return Cursor()

    monkeypatch.setattr(repository, "_verify_schema_connection", lambda connection: 1)
    outcome = repository.load_execution_profile(
        ForgedConnection(),  # type: ignore[arg-type]
        EXECUTION_PROFILE_ID,
    )
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert outcome.record is None


def test_non_sqlite_same_named_exception_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class IntegrityError(Exception):
        pass

    class FakeConnection:
        def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
            del sql, parameters
            raise IntegrityError("not SQLite")

    monkeypatch.setattr(repository, "_verify_schema_connection", lambda connection: 1)
    with pytest.raises(IntegrityError):
        repository.load_scope(FakeConnection(), 1)  # type: ignore[arg-type]


def test_repository_never_commits(connection) -> None:
    commits: list[str] = []
    connection.set_trace_callback(
        lambda statement: (
            commits.append(statement)
            if statement.upper().startswith("COMMIT")
            else None
        )
    )
    _foundation(connection)
    connection.set_trace_callback(None)
    assert commits == []


def test_missing_requested_proof_member_fails_without_partial_record(
    connection,
) -> None:
    _foundation(connection)
    outcome = repository.load_current_proof(
        connection,
        records.CurrentProofRequest(APP_ID, 1, root_fill_key_id=999),
    )
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert outcome.record is None
