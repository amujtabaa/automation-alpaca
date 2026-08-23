"""Failure-capable contracts for the complete WO-0167 repository boundary."""

from __future__ import annotations

import ast
import dataclasses
from decimal import Decimal
from enum import IntEnum
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


class _IntCoordinateAlias(int):
    pass


class _TextCoordinateAlias(str):
    pass


class _CoordinateEnum(IntEnum):
    ONE = 1


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
    expected_repository_exports = (
        "advance_kernel_checkpoint",
        "advance_market_cursor",
        "advance_protection_authority",
        "advance_symbol_controller",
        "advance_venue_effect",
        "load_acceptance_evidence",
        "load_acceptance_set",
        "load_acceptance_set_for_effect",
        "load_acquisition_generation",
        "load_acquisition_generation_current",
        "load_acquisition_root_route",
        "load_application_generation",
        "load_closure_head",
        "load_current_proof",
        "load_dispatch_claim",
        "load_dispatch_claim_for_effect",
        "load_execution_fact",
        "load_execution_fact_by_source",
        "load_execution_fact_head",
        "load_execution_profile",
        "load_kernel_checkpoint",
        "load_latest_acceptance_evidence",
        "load_live_acquisition_generation",
        "load_market_cursor",
        "load_market_source_profile",
        "load_market_stream_authority",
        "load_open_venue_effects",
        "load_protection_authority",
        "load_root_fill",
        "load_root_fill_by_external",
        "load_scope",
        "load_symbol_controller",
        "load_venue_effect",
        "load_venue_identity_owner",
        "load_venue_identity_owners_for_effect",
        "retire_acquisition_generation",
        "store_acceptance_evidence",
        "store_acceptance_set",
        "store_acquisition_generation",
        "store_acquisition_root_route",
        "store_application_generation",
        "store_closure",
        "store_dispatch_claim",
        "store_execution_fact",
        "store_execution_profile",
        "store_kernel_checkpoint",
        "store_market_cursor",
        "store_market_source_profile",
        "store_market_stream_authority",
        "store_protection_authority",
        "store_root_fill",
        "store_scope",
        "store_symbol_controller",
        "store_venue_effect",
        "store_venue_identity_owner",
    )
    expected_record_exports = (
        "AcceptanceEvidenceRecord",
        "AcceptanceSetRecord",
        "AcquisitionGenerationCurrentRecord",
        "AcquisitionGenerationRecord",
        "AcquisitionRootRouteRecord",
        "ApplicationGenerationRecord",
        "ClosureChainRecord",
        "CurrentProofRequest",
        "CurrentProofSlice",
        "DispatchClaimRecord",
        "ExecutionFactHeadRecord",
        "ExecutionFactRecord",
        "KernelCheckpointRecord",
        "MarketCursorRecord",
        "MarketStreamAuthorityRecord",
        "ProtectionAuthorityRecord",
        "RepositoryOutcome",
        "RepositoryOutcomeKind",
        "RootFillRecord",
        "ScopeRecord",
        "SymbolControllerRecord",
        "VenueEffectRecord",
        "VenueIdentityOwnerRecord",
    )
    assert repository.__all__ == expected_repository_exports
    assert records.__all__ == expected_record_exports
    assert len(repository.__all__) == len(set(repository.__all__))
    assert len(records.__all__) == len(set(records.__all__))
    assert {name for name in vars(repository) if not name.startswith("_")} == set(
        expected_repository_exports
    )
    assert {name for name in vars(records) if not name.startswith("_")} == set(
        expected_record_exports
    )
    with pytest.raises(ValueError):
        records.RepositoryOutcome(records.RepositoryOutcomeKind.FOUND)
    with pytest.raises(ValueError):
        records.RepositoryOutcome(records.RepositoryOutcomeKind.ABSENT, object())


def _import_probe(
    repo_root: Path,
    scratch: Path,
    write_target: Path,
    *,
    mutate: bool,
) -> subprocess.CompletedProcess[str]:
    script = f"""
import os
from pathlib import Path
import sys
root = Path({str(repo_root)!r})
scratch = Path({str(scratch)!r})
write_target = Path({str(write_target)!r})
sys.path.insert(0, str(root))
source_path = root / 'app/execution_core/persistence/repository.py'
source = source_path.read_text(encoding='utf-8')
scratch.mkdir(parents=True, exist_ok=True)
before_env = dict(os.environ)
before_files = set(scratch.rglob('*'))
write_events = []
capability_events = []
def audit(event, args):
    if event == 'open':
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        writes_by_mode = isinstance(mode, str) and any(mark in mode for mark in 'wax+')
        writes_by_flags = isinstance(flags, int) and bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        )
        if writes_by_mode or writes_by_flags:
            write_events.append((event, args[0]))
    elif event in ('sqlite3.connect', 'socket.connect', 'subprocess.Popen'):
        capability_events.append(event)
sys.addaudithook(audit)
import app.execution_core.persistence
if {mutate!r}:
    insertion = "\\nopen(" + repr(str(write_target)) + ", 'w').write('x')\\n"
    source = source.replace('from __future__ import annotations as _annotations', 'from __future__ import annotations as _annotations' + insertion, 1)
    namespace = {{'__name__': 'app.execution_core.persistence._repository_mutant', '__package__': 'app.execution_core.persistence'}}
    exec(compile(source, str(source_path), 'exec'), namespace)
else:
    __import__('app.execution_core.persistence.repository')
after_files = set(scratch.rglob('*'))
assert dict(os.environ) == before_env
assert after_files == before_files
assert write_events == []
assert capability_events == []
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
    write_target = tmp_path / "outside-observed-scratch" / "mutant-write"
    write_target.parent.mkdir()
    actual = _import_probe(
        repo_root,
        tmp_path / "actual",
        write_target,
        mutate=False,
    )
    assert actual.returncode == 0, actual.stderr
    mutant = _import_probe(
        repo_root,
        tmp_path / "mutant",
        write_target,
        mutate=True,
    )
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
    checkpoint_v2 = _checkpoint(head=1, version=2)
    _expect_applied(repository.advance_kernel_checkpoint(connection, 1, checkpoint_v2))
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

    root_proof = repository.load_current_proof(
        connection,
        records.CurrentProofRequest(APP_ID, 1, root_fill_key_id=1),
    )
    assert root_proof.kind is records.RepositoryOutcomeKind.FOUND
    assert root_proof.record is not None
    assert root_proof.record.current_execution_fact == _fact()

    effect_proof = repository.load_current_proof(
        connection,
        records.CurrentProofRequest(
            APP_ID,
            1,
            effect_id=2,
            owner_id=owner.owner_id,
            require_acceptance=True,
            require_closure=True,
        ),
    )
    assert effect_proof.kind is records.RepositoryOutcomeKind.FOUND
    assert effect_proof.record is not None
    assert effect_proof.record.dispatch_claim == claim
    assert effect_proof.record.closure_head == closure

    spliced = repository.load_current_proof(
        connection,
        records.CurrentProofRequest(
            APP_ID,
            1,
            root_fill_key_id=1,
            effect_id=2,
            owner_id=owner.owner_id,
        ),
    )
    assert spliced.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert spliced.record is None


def test_repository_loads_cross_the_accepted_codec_boundary(
    connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _foundation(connection)
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
    for operation, value in (
        (repository.store_root_fill, root),
        (repository.store_venue_effect, effect),
        (repository.store_venue_identity_owner, owner),
        (repository.store_acquisition_root_route, route),
        (repository.store_dispatch_claim, _claim(1)),
        (repository.store_execution_fact, _fact()),
    ):
        _expect_applied(operation(connection, value))

    decoded_tags: list[str] = []
    accepted_decoder = repository._decode_m1_value

    def tracing_decoder(atom):
        decoded_tags.append(atom.type_tag)
        return accepted_decoder(atom)

    monkeypatch.setattr(repository, "_decode_m1_value", tracing_decoder)
    outcomes = (
        repository.load_scope(connection, 1),
        repository.load_market_cursor(connection, STREAM_ID),
        repository.load_root_fill(connection, 1),
        repository.load_execution_fact(connection, 1),
        repository.load_venue_effect(connection, 1),
        repository.load_venue_identity_owner(
            connection,
            EXECUTION_PROFILE_ID,
            owner.owner_id,
        ),
        repository.load_acquisition_root_route(connection, 1),
        repository.load_dispatch_claim(connection, 1),
    )
    assert {outcome.kind for outcome in outcomes} == {
        records.RepositoryOutcomeKind.FOUND
    }
    assert {
        "application_generation_id",
        "symbol_id",
        "market_stream_generation_id",
        "acquisition_generation_id",
        "session_id",
        "root_fill_id",
        "source_event_id",
        "order_id",
        "quantity",
        "reported_price",
        "effect_id",
        "request_occurrence_id",
        "mandate_id",
        "claim_occurrence_id",
        "venue_observation_id",
    } <= set(decoded_tags)


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


def test_repository_source_cannot_begin_commit_or_rollback_transactions() -> None:
    path = Path(repository.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_attributes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr
        in {"commit", "rollback", "cursor", "executemany", "executescript"}
    ]
    transaction_tokens = {
        "BEGIN",
        "COMMIT",
        "END",
        "ROLLBACK",
        "SAVEPOINT",
        "RELEASE",
    }

    def constant_text(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = constant_text(node.left)
            right = constant_text(node.right)
            return None if left is None or right is None else left + right
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
            and not node.keywords
            and len(node.args) == 1
            and isinstance(node.args[0], (ast.Tuple, ast.List))
        ):
            separator = constant_text(node.func.value)
            parts = [constant_text(item) for item in node.args[0].elts]
            if separator is not None and all(part is not None for part in parts):
                return separator.join(part for part in parts if part is not None)
        return None

    def first_sql_token(text: str) -> str:
        remaining = text
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

    forbidden_sql = []
    for node in ast.walk(tree):
        text = constant_text(node)
        if text is not None and first_sql_token(text) in transaction_tokens:
            forbidden_sql.append(text)
    assert forbidden_attributes == []
    assert forbidden_sql == []


def test_retirement_changes_state_and_remains_caller_rollback_owned(connection) -> None:
    _foundation(connection)
    successor = identity.AcquisitionGenerationId("56" * 32)
    _expect_applied(
        repository.store_scope(
            connection,
            records.ScopeRecord(
                2,
                APP_ID,
                EXECUTION_PROFILE_ID,
                identity.SymbolId("MSFT"),
            ),
        )
    )
    generation = dataclasses.replace(
        _acquisition(),
        acquisition_generation_id=successor,
        scope_id=2,
    )
    _expect_applied(repository.store_acquisition_generation(connection, generation))
    connection.commit()
    connection.execute("BEGIN")
    _expect_applied(repository.retire_acquisition_generation(connection, successor))
    retired = dataclasses.replace(generation, status="RETIRED_UNSERVING")
    _assert_found(
        repository.load_acquisition_generation(connection, successor), retired
    )
    connection.rollback()
    _assert_found(
        repository.load_acquisition_generation(connection, successor), generation
    )


def test_advances_reject_contradictory_immutable_authority(connection) -> None:
    _foundation(connection)
    effect = _effect(1, controller_head=0, protection_version=1)
    _expect_applied(repository.store_venue_effect(connection, effect))

    wrong_application = identity.ApplicationGenerationId("wrong-generation")
    controller = dataclasses.replace(
        _controller(version=2),
        application_generation_id=wrong_application,
        execution_profile_id="ab" * 32,
    )
    cursor = dataclasses.replace(
        _cursor(fixed=1, published=1),
        scope_id=99,
        application_generation_id=wrong_application,
        acquisition_generation_id=identity.AcquisitionGenerationId("78" * 32),
        generation_mandate_commitment_sha256="91" * 32,
        source_profile_id="92" * 32,
        session_id=identity.SessionId("wrong-session"),
        sequence_mode="BROKER_SEQUENCE",
    )
    contradictory_effect = dataclasses.replace(
        effect,
        effect_external=identity.EffectId("different-effect"),
        scope_id=99,
        application_generation_id=wrong_application,
        execution_profile_id="93" * 32,
        lifecycle_state="ACKNOWLEDGED",
    )

    outcomes = (
        repository.advance_symbol_controller(connection, 1, controller),
        repository.advance_market_cursor(connection, 0, 0, cursor),
        repository.advance_venue_effect(
            connection,
            "REQUESTED",
            "OPEN",
            contradictory_effect,
        ),
    )
    assert {outcome.kind for outcome in outcomes} == {
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    }
    _assert_found(repository.load_symbol_controller(connection, 1), _controller())
    _assert_found(repository.load_market_cursor(connection, STREAM_ID), _cursor())
    _assert_found(repository.load_venue_effect(connection, 1), effect)


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


def test_every_insert_owned_family_rejects_primary_identity_mismatch(
    connection,
) -> None:
    _foundation(connection)
    foundation_mismatches = (
        (
            repository.store_execution_profile,
            dataclasses.replace(
                _execution_profile(),
                deployment_identity="de" * 32,
            ),
        ),
        (
            repository.store_market_source_profile,
            dataclasses.replace(
                _market_profile(),
                environment_or_feed="sip-feed",
            ),
        ),
        (
            repository.store_application_generation,
            dataclasses.replace(_application(), activation_ordinal=2),
        ),
        (
            repository.store_scope,
            dataclasses.replace(_scope(), symbol=identity.SymbolId("MSFT")),
        ),
        (
            repository.store_acquisition_generation,
            dataclasses.replace(
                _acquisition(),
                emergency_compatibility_sha256="ac" * 32,
            ),
        ),
        (repository.store_kernel_checkpoint, _checkpoint(head=1, version=2)),
        (
            repository.store_symbol_controller,
            dataclasses.replace(
                _controller(),
                emergency_compatibility_sha256="ac" * 32,
            ),
        ),
        (
            repository.store_market_stream_authority,
            dataclasses.replace(
                _market_stream(),
                session_id=identity.SessionId("session-2"),
            ),
        ),
        (
            repository.store_market_cursor,
            dataclasses.replace(
                _cursor(),
                session_id=identity.SessionId("session-2"),
            ),
        ),
        (
            repository.store_protection_authority,
            dataclasses.replace(
                _protection(),
                state_commitment_sha256="ac" * 32,
            ),
        ),
    )
    for operation, mismatched in foundation_mismatches:
        outcome = operation(connection, mismatched)
        assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE, (
            operation.__name__
        )

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
    fact = _fact()
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
        (
            repository.store_root_fill,
            root,
            dataclasses.replace(root, root_fill_id=identity.RootFillId("root-x")),
        ),
        (
            repository.store_venue_effect,
            effect,
            dataclasses.replace(effect, economic_scope=b"\x02"),
        ),
        (
            repository.store_venue_identity_owner,
            owner,
            dataclasses.replace(
                owner,
                observation_id=identity.VenueObservationId("observation-x"),
            ),
        ),
        (
            repository.store_acquisition_root_route,
            route,
            dataclasses.replace(
                route,
                observation_id=identity.VenueObservationId("observation-x"),
            ),
        ),
        (
            repository.store_dispatch_claim,
            claim,
            dataclasses.replace(claim, claim_ordinal=99),
        ),
        (
            repository.store_execution_fact,
            fact,
            dataclasses.replace(fact, order_id=identity.OrderId("order-x")),
        ),
        (
            repository.store_acceptance_set,
            acceptance,
            dataclasses.replace(acceptance, effect_id=999),
        ),
        (
            repository.store_acceptance_evidence,
            evidence,
            dataclasses.replace(evidence, evidence_digest="ab" * 32),
        ),
        (
            repository.store_closure,
            closure,
            dataclasses.replace(closure, effect_id=999),
        ),
    )
    for operation, retained, mismatched in owned:
        _expect_applied(operation(connection, retained))
        outcome = operation(connection, mismatched)
        assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE, (
            operation.__name__
        )


def test_insert_conflict_probes_cover_alternate_and_ambiguous_identities(
    connection,
) -> None:
    _foundation(connection)
    alternate_foundation = (
        (
            repository.store_application_generation,
            dataclasses.replace(
                _application(),
                application_generation_id=identity.ApplicationGenerationId(
                    "generation-2"
                ),
            ),
        ),
        (
            repository.store_scope,
            dataclasses.replace(_scope(), scope_id=2),
        ),
        (
            repository.store_acquisition_generation,
            dataclasses.replace(
                _acquisition(),
                acquisition_generation_id=identity.AcquisitionGenerationId("13" * 32),
            ),
        ),
    )
    for operation, alternate in alternate_foundation:
        outcome = operation(connection, alternate)
        assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE, (
            operation.__name__
        )

    root = _root()
    _expect_applied(repository.store_root_fill(connection, root))
    alternate_root = dataclasses.replace(root, root_fill_key_id=2)
    assert (
        repository.store_root_fill(connection, alternate_root).kind
        is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )

    effect = _effect(1, controller_head=0, protection_version=1)
    _expect_applied(repository.store_venue_effect(connection, effect))
    alternate_effect = dataclasses.replace(
        effect,
        effect_id=2,
        created_ordinal=2,
    )
    assert (
        repository.store_venue_effect(connection, alternate_effect).kind
        is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )

    claim = _claim(1)
    _expect_applied(repository.store_dispatch_claim(connection, claim))
    alternate_claim = dataclasses.replace(claim, claim_id=2, claim_ordinal=2)
    assert (
        repository.store_dispatch_claim(connection, alternate_claim).kind
        is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )

    acceptance = records.AcceptanceSetRecord(1, 1)
    _expect_applied(repository.store_acceptance_set(connection, acceptance))
    assert (
        repository.store_acceptance_set(
            connection,
            records.AcceptanceSetRecord(2, 1),
        ).kind
        is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )

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
    _expect_applied(repository.store_acceptance_evidence(connection, evidence))
    alternate_evidence = dataclasses.replace(evidence, evidence_id=2)
    assert (
        repository.store_acceptance_evidence(connection, alternate_evidence).kind
        is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )

    owner = _owner(1, root_fill_key_id=1)
    _expect_applied(repository.store_venue_identity_owner(connection, owner))
    closure = records.ClosureChainRecord(
        1,
        1,
        owner.owner_id,
        1,
        1,
        "TERMINAL_LEG",
        None,
    )
    _expect_applied(repository.store_closure(connection, closure))
    alternate_closure = dataclasses.replace(closure, closure_id=2)
    assert (
        repository.store_closure(connection, alternate_closure).kind
        is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    )

    scope_two = records.ScopeRecord(
        2,
        APP_ID,
        EXECUTION_PROFILE_ID,
        identity.SymbolId("MSFT"),
    )
    _expect_applied(repository.store_scope(connection, scope_two))
    ambiguous_scope = dataclasses.replace(
        scope_two,
        scope_id=1,
    )
    assert (
        repository.store_scope(connection, ambiguous_scope).kind
        is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
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


@pytest.mark.parametrize(
    "alias",
    (
        True,
        1.0,
        "1",
        "01",
        "+1",
        "1.0",
        _IntCoordinateAlias(1),
        _CoordinateEnum.ONE,
    ),
)
def test_every_numeric_loader_rejects_cross_type_coordinate_aliases(
    connection,
    alias: object,
) -> None:
    _foundation(connection)
    owner_id = identity.OrderId("owner-1")
    operations = (
        repository.load_scope(connection, alias),  # type: ignore[arg-type]
        repository.load_symbol_controller(connection, alias),  # type: ignore[arg-type]
        repository.load_root_fill(connection, alias),  # type: ignore[arg-type]
        repository.load_execution_fact(connection, alias),  # type: ignore[arg-type]
        repository.load_execution_fact_head(connection, alias),  # type: ignore[arg-type]
        repository.load_venue_effect(connection, alias),  # type: ignore[arg-type]
        repository.load_acquisition_root_route(connection, alias),  # type: ignore[arg-type]
        repository.load_dispatch_claim(connection, alias),  # type: ignore[arg-type]
        repository.load_acceptance_set(connection, alias),  # type: ignore[arg-type]
        repository.load_acceptance_evidence(connection, alias),  # type: ignore[arg-type]
        repository.load_protection_authority(connection, alias),  # type: ignore[arg-type]
        repository.load_live_acquisition_generation(connection, alias),  # type: ignore[arg-type]
        repository.load_open_venue_effects(connection, alias),  # type: ignore[arg-type]
        repository.load_venue_identity_owners_for_effect(connection, alias),  # type: ignore[arg-type]
        repository.load_dispatch_claim_for_effect(connection, alias),  # type: ignore[arg-type]
        repository.load_acceptance_set_for_effect(connection, alias),  # type: ignore[arg-type]
        repository.load_latest_acceptance_evidence(connection, alias),  # type: ignore[arg-type]
        repository.load_closure_head(connection, alias, owner_id),  # type: ignore[arg-type]
        repository.load_current_proof(
            connection,
            records.CurrentProofRequest(APP_ID, alias),  # type: ignore[arg-type]
        ),
    )
    assert {outcome.kind for outcome in operations} == {
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    }


@pytest.mark.parametrize("alias", (1, _TextCoordinateAlias(EXECUTION_PROFILE_ID)))
def test_every_text_loader_rejects_non_exact_coordinate_aliases(
    connection,
    alias: object,
) -> None:
    _foundation(connection)
    operations = (
        repository.load_execution_profile(connection, alias),  # type: ignore[arg-type]
        repository.load_market_source_profile(connection, alias),  # type: ignore[arg-type]
        repository.load_root_fill_by_external(
            connection,
            alias,  # type: ignore[arg-type]
            identity.RootFillId("root-1"),
        ),
        repository.load_execution_fact_by_source(
            connection,
            alias,  # type: ignore[arg-type]
            identity.SourceEventId("event-1"),
        ),
        repository.load_venue_identity_owner(
            connection,
            alias,  # type: ignore[arg-type]
            identity.OrderId("owner-1"),
        ),
    )
    assert {outcome.kind for outcome in operations} == {
        records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    }


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


def test_non_sqlite_exception_cannot_spoof_sqlite_module_and_mro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_error = type("Error", (Exception,), {"__module__": "sqlite3"})
    fake_integrity = type(
        "IntegrityError",
        (fake_error,),
        {"__module__": "sqlite3"},
    )
    caught = fake_integrity("not SQLite")
    caught.sqlite_errorcode = 2067

    class FakeConnection:
        def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
            del sql, parameters
            raise caught

    monkeypatch.setattr(repository, "_verify_schema_connection", lambda connection: 1)
    with pytest.raises(fake_integrity):
        repository.load_scope(FakeConnection(), 1)  # type: ignore[arg-type]


def test_duplicate_probe_cannot_hide_broken_claim_authority(connection) -> None:
    _foundation(connection)
    effect = _effect(1, controller_head=0, protection_version=1)
    claim = _claim(1)
    _expect_applied(repository.store_venue_effect(connection, effect))
    _expect_applied(repository.store_dispatch_claim(connection, claim))

    broken = dataclasses.replace(claim, effect_id=999)
    outcome = repository.store_dispatch_claim(connection, broken)
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    _assert_found(repository.load_dispatch_claim(connection, claim.claim_id), claim)


def test_duplicate_probe_cannot_hide_broken_execution_fact_authority(
    connection,
) -> None:
    _foundation(connection)
    root = _root()
    alternate_root = dataclasses.replace(
        root,
        root_fill_key_id=2,
        root_fill_id=identity.RootFillId("root-2"),
    )
    fact = _fact()
    _expect_applied(repository.store_root_fill(connection, root))
    _expect_applied(repository.store_root_fill(connection, alternate_root))
    _expect_applied(repository.store_execution_fact(connection, fact))

    assert (
        repository.store_execution_fact(connection, fact).kind
        is records.RepositoryOutcomeKind.CONFLICT
    )
    broken = dataclasses.replace(
        fact,
        fact_id=2,
        root_fill_key_id=2,
        fact_ordinal=2,
    )
    outcome = repository.store_execution_fact(connection, broken)
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    _assert_found(repository.load_execution_fact(connection, fact.fact_id), fact)


def test_requested_effect_proof_propagates_claim_read_failure(connection) -> None:
    _foundation(connection)
    effect = _effect(1, controller_head=0, protection_version=1)
    _expect_applied(repository.store_venue_effect(connection, effect))

    baseline = repository.load_current_proof(
        connection,
        records.CurrentProofRequest(APP_ID, 1, effect_id=effect.effect_id),
    )
    assert baseline.kind is records.RepositoryOutcomeKind.FOUND
    assert baseline.record is not None
    assert baseline.record.dispatch_claim is None

    class ClaimReadFailureConnection:
        def execute(self, sql: str, parameters: tuple[Any, ...] = ()) -> Any:
            if "FROM dispatch_claim WHERE effect_id =" in sql:
                raise sqlite3.DatabaseError("injected claim read failure")
            return connection.execute(sql, parameters)

    outcome = repository.load_current_proof(
        ClaimReadFailureConnection(),  # type: ignore[arg-type]
        records.CurrentProofRequest(APP_ID, 1, effect_id=effect.effect_id),
    )
    assert outcome.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert outcome.record is None


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


def test_current_proof_refuses_checkpoint_behind_controller_head(connection) -> None:
    _foundation(connection)
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
    for operation, value in (
        (repository.store_root_fill, _root()),
        (
            repository.store_venue_effect,
            _effect(1, controller_head=0, protection_version=1),
        ),
        (repository.store_venue_identity_owner, owner),
        (repository.store_acquisition_root_route, route),
        (repository.store_execution_fact, _fact()),
    ):
        _expect_applied(operation(connection, value))
    _expect_applied(
        repository.advance_protection_authority(
            connection,
            1,
            _protection(controller_head=1, version=2),
        )
    )

    proof_request = records.CurrentProofRequest(APP_ID, 1, root_fill_key_id=1)
    stale = repository.load_current_proof(connection, proof_request)
    assert stale.kind is records.RepositoryOutcomeKind.INTEGRITY_FAILURE
    assert stale.record is None

    _expect_applied(
        repository.advance_kernel_checkpoint(
            connection,
            1,
            _checkpoint(head=1, version=2),
        )
    )
    fresh = repository.load_current_proof(connection, proof_request)
    assert fresh.kind is records.RepositoryOutcomeKind.FOUND
    assert fresh.record is not None
