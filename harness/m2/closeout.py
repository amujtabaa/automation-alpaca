"""Finite WO-0170 proof catalog and isolated SQLite restore utilities."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import copyfile
from typing import Final, Iterable


class CloseoutCatalogError(ValueError):
    """The finite closeout catalog or restore bundle is incomplete."""


@dataclass(frozen=True, slots=True)
class ProofCase:
    case_id: str
    obligation: str
    nodeid: str
    fresh_file: bool


@dataclass(frozen=True, slots=True)
class RestoreFileEvidence:
    suffix: str
    source_sha256: str
    destination_sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class RestoreBundleEvidence:
    source_database: Path
    destination_database: Path
    files: tuple[RestoreFileEvidence, ...]


FAULT_OBLIGATIONS: Final = (
    "uow-write-before-after",
    "uow-body-exception",
    "transaction-rollback",
    "commit-return-ambiguity",
    "post-commit-publication",
    "durable-input-claim",
    "broker-outbox-order",
    "checkpoint-payload-write",
    "checkpoint-head-cas",
    "checkpoint-reread",
    "checkpoint-receipt",
    "checkpoint-commit",
    "owner-lock-acquire",
    "owner-lock-currentness",
    "owner-lock-release",
    "market-fence-cursor",
    "market-baseline-publication",
    "startup-cutover",
    "startup-reconciliation",
)


_UOW = "tests/execution_core/test_persistence_unit_of_work.py"
_COLD = "tests/execution_core/test_persistence_cold_recovery.py"
_SCHEMA = "tests_gated/execution_core/test_persistence_schema.py"
_CHECKPOINT = "tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py"
_DIRECTNESS = "tests_gated/execution_core/test_persistence_directness.py"
_REPOSITORY = "tests_gated/execution_core/test_persistence_repository.py"
_FAULT_MATRIX = "tests/execution_core/test_persistence_fault_matrix.py"
_GATED_FAULT_MATRIX = "tests_gated/execution_core/test_persistence_fault_matrix.py"


def _cases(
    prefix: str,
    obligations: tuple[str, ...],
    nodeids: tuple[str, ...],
) -> tuple[ProofCase, ...]:
    if len(obligations) != len(nodeids):
        raise CloseoutCatalogError("proof obligations and node IDs must be total")
    return tuple(
        ProofCase(
            f"{prefix}{ordinal:02d}",
            obligation,
            nodeid,
            nodeid.startswith("tests_gated/"),
        )
        for ordinal, (obligation, nodeid) in enumerate(
            zip(obligations, nodeids, strict=True), 1
        )
    )


FAULT_CASES: Final = _cases(
    "F",
    FAULT_OBLIGATIONS,
    (
        f"{_UOW}::test_every_catalogued_repository_call_fault_is_old_complete",
        f"{_UOW}::test_body_fault_retires_lease_then_rolls_back_once",
        f"{_UOW}::test_rollback_ambiguity_propagates_without_retry",
        f"{_UOW}::test_commit_ambiguity_never_rolls_back_or_mints_eligibility",
        f"{_UOW}::test_commit_mints_effect_eligibility_only_after_normal_return",
        f"{_FAULT_MATRIX}::test_durable_input_claim_faults_are_old_complete",
        f"{_UOW}::test_claim_completion_stores_outbox_after_outcome_before_finalization",
        f"{_CHECKPOINT}::test_f02_fault_after_payload_insert_before_cas_rolls_back_exactly",
        f"{_CHECKPOINT}::test_f06_fault_after_successful_cas_before_reread_rolls_back_exactly",
        f"{_CHECKPOINT}::test_f08_fault_after_exact_reread_before_receipt_rolls_back_exactly",
        f"{_CHECKPOINT}::test_f09_exact_receipt_exception_cartesian_matrix_translates_to_integrity",
        f"{_CHECKPOINT}::test_f10_ambiguous_commit_allows_only_exact_old_or_new_complete_state",
        f"{_COLD}::test_owner_lock_precedes_datastore_and_dormant_success_retains_lease",
        f"{_COLD}::test_owner_loss_after_open_stops_before_database_transition",
        f"{_COLD}::test_owner_loss_during_connection_close_cannot_publish_serving",
        f"{_COLD}::test_retained_cursor_equality_fails_before_baseline",
        f"{_COLD}::test_baseline_commit_cannot_publish_effect_eligibility",
        f"{_COLD}::test_initial_cutover_ambiguity_is_datastore_failure_before_query_or_source",
        f"{_COLD}::test_complete_claimed_unresolved_union_is_queried_once_and_resolved",
    ),
)


MUTANT_OBLIGATIONS: Final = (
    "duplicate-or-forked-lineage",
    "stale-or-missing-route",
    "two-live-controllers",
    "profile-substitution",
    "claim-erasure",
    "acceptance-or-closure-gap",
    "cursor-ordering",
    "history-fold-startup",
    "cross-scope-route",
    "cross-acquisition-outbox",
)


MUTANT_CASES: Final = _cases(
    "M",
    MUTANT_OBLIGATIONS,
    (
        f"{_SCHEMA}::test_revision_predecessor_must_exist_inside_same_root",
        f"{_DIRECTNESS}::test_total_proof_refuses_each_independently_omitted_member",
        f"{_SCHEMA}::test_two_live_acquisition_generations_in_one_scope_are_rejected",
        "tests_gated/execution_core/test_persistence_restore.py::"
        "test_restored_profile_substitution_and_catalog_corruption_are_non_serving",
        f"{_GATED_FAULT_MATRIX}::test_current_proof_refuses_erased_dispatch_claim",
        f"{_GATED_FAULT_MATRIX}::test_current_proof_refuses_acceptance_or_closure_gap",
        f"{_GATED_FAULT_MATRIX}::test_market_cursor_refuses_each_monotonic_regression",
        f"{_COLD}::test_cold_context_loader_uses_only_bounded_checkpoint_routes",
        f"{_SCHEMA}::test_market_occurrence_input_requires_its_exact_stream_route",
        f"{_SCHEMA}::test_broker_outbox_refuses_durable_input_from_another_acquisition",
    ),
)


BOUNDEDNESS_OBLIGATIONS: Final = (
    "direct-current-proof",
    "checkpoint-query-plans",
    "target-stress-measurement",
    "startup-no-history-fold",
)


BOUNDEDNESS_CASES: Final = _cases(
    "B",
    BOUNDEDNESS_OBLIGATIONS,
    (
        f"{_DIRECTNESS}::test_total_proof_uses_only_fixed_direct_key_queries_under_history_stress",
        f"{_CHECKPOINT}::test_thirteen_selection_and_load_queries_have_direct_plans_under_history_stress",
        "tests_gated/execution_core/test_persistence_boundedness.py::"
        "test_runtime_checkpoint_selection_and_hydration_stay_bounded_from_target_to_stress",
        f"{_COLD}::test_cold_context_loader_uses_only_bounded_checkpoint_routes",
    ),
)


SOAK_NODEIDS: Final = (
    FAULT_CASES[0].nodeid,
    FAULT_CASES[3].nodeid,
    FAULT_CASES[11].nodeid,
    "tests_gated/execution_core/test_persistence_fault_matrix.py::"
    "test_startup_commit_fault_reopens_old_or_new_complete",
    "tests_gated/execution_core/test_persistence_restore.py::"
    "test_live_wal_bundle_restores_to_independent_exact_replay",
    MUTANT_CASES[2].nodeid,
    MUTANT_CASES[5].nodeid,
)


def validate_catalog(
    fault_cases: Iterable[ProofCase] = FAULT_CASES,
    mutant_cases: Iterable[ProofCase] = MUTANT_CASES,
) -> None:
    faults = tuple(fault_cases)
    mutants = tuple(mutant_cases)
    all_cases = (*faults, *mutants, *BOUNDEDNESS_CASES)
    ids = tuple(case.case_id for case in all_cases)
    if len(ids) != len(set(ids)):
        raise CloseoutCatalogError("proof case IDs must be unique")
    if {case.obligation for case in faults} != set(FAULT_OBLIGATIONS):
        raise CloseoutCatalogError("fault obligations are incomplete")
    if {case.obligation for case in mutants} != set(MUTANT_OBLIGATIONS):
        raise CloseoutCatalogError("mutant obligations are incomplete")
    for case in all_cases:
        if "::test_" not in case.nodeid:
            raise CloseoutCatalogError(f"invalid pytest node ID: {case.case_id}")
        if case.fresh_file != case.nodeid.startswith("tests_gated/"):
            raise CloseoutCatalogError(f"misclassified evidence gate: {case.case_id}")


def missing_nodeids(repository_root: Path) -> tuple[str, ...]:
    missing: list[str] = []
    for case in (*FAULT_CASES, *MUTANT_CASES, *BOUNDEDNESS_CASES):
        path_text, test_name = case.nodeid.split("::", 1)
        path = repository_root / path_text
        if not path.is_file():
            missing.append(case.nodeid)
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if test_name not in names:
            missing.append(case.nodeid)
    return tuple(missing)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bundle_path(database: Path, suffix: str) -> Path:
    return database if not suffix else database.with_name(database.name + suffix)


def snapshot_sqlite_bundle(
    source_database: Path,
    destination_database: Path,
    *,
    require_wal: bool,
) -> RestoreBundleEvidence:
    source = source_database.resolve(strict=True)
    destination = destination_database.resolve(strict=False)
    if source == destination:
        raise CloseoutCatalogError("restore destination must be independent")
    if not destination.parent.is_dir():
        raise CloseoutCatalogError("restore destination parent must already exist")

    destination_family = tuple(
        _bundle_path(destination, suffix) for suffix in ("", "-wal", "-shm")
    )
    if any(path.exists() for path in destination_family):
        raise CloseoutCatalogError(
            "restore destination collides with existing evidence"
        )

    suffixes = [""]
    source_wal = _bundle_path(source, "-wal")
    if source_wal.is_file():
        suffixes.append("-wal")
    elif require_wal:
        raise CloseoutCatalogError("required WAL evidence is absent")

    sources = tuple(_bundle_path(source, suffix) for suffix in suffixes)
    destinations = tuple(_bundle_path(destination, suffix) for suffix in suffixes)
    before = tuple((_file_sha256(path), path.stat().st_size) for path in sources)
    for source_path, destination_path in zip(sources, destinations, strict=True):
        copyfile(source_path, destination_path)
    after = tuple((_file_sha256(path), path.stat().st_size) for path in sources)
    if after != before:
        raise CloseoutCatalogError("source bundle changed while it was copied")

    files = tuple(
        RestoreFileEvidence(
            suffix,
            source_digest,
            _file_sha256(destination_path),
            source_size,
        )
        for suffix, (source_digest, source_size), destination_path in zip(
            suffixes,
            before,
            destinations,
            strict=True,
        )
    )
    if any(item.source_sha256 != item.destination_sha256 for item in files):
        raise CloseoutCatalogError("restore copy is not byte-identical")
    return RestoreBundleEvidence(source, destination, files)


def verify_restore_bundle(evidence: RestoreBundleEvidence) -> None:
    recorded_suffixes = tuple(item.suffix for item in evidence.files)
    if (
        not recorded_suffixes
        or recorded_suffixes[0] != ""
        or len(recorded_suffixes) != len(set(recorded_suffixes))
        or any(suffix not in {"", "-wal"} for suffix in recorded_suffixes)
    ):
        raise CloseoutCatalogError("restore evidence suffix set is invalid")
    if "-wal" not in recorded_suffixes and (
        _bundle_path(evidence.source_database, "-wal").exists()
        or _bundle_path(evidence.destination_database, "-wal").exists()
    ):
        raise CloseoutCatalogError("unrecorded restore WAL sidecar is present")
    if _bundle_path(evidence.destination_database, "-shm").exists():
        raise CloseoutCatalogError("unrecorded restore SHM sidecar is present")

    for item in evidence.files:
        source = _bundle_path(evidence.source_database, item.suffix)
        destination = _bundle_path(evidence.destination_database, item.suffix)
        if not source.is_file() or not destination.is_file():
            raise CloseoutCatalogError("restore evidence file is missing")
        if source.stat().st_size != item.byte_count:
            raise CloseoutCatalogError("restore source size drifted")
        if destination.stat().st_size != item.byte_count:
            raise CloseoutCatalogError("restore destination size drifted")
        if _file_sha256(source) != item.source_sha256:
            raise CloseoutCatalogError("restore source digest drifted")
        if _file_sha256(destination) != item.destination_sha256:
            raise CloseoutCatalogError("restore destination digest drifted")


validate_catalog()
