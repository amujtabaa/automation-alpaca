"""Measured target/stress boundedness proof for the M2 checkpoint selector."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter_ns
import tracemalloc

import pytest

from app.execution_core.persistence import records, repository, unit_of_work
from tests.performance import m2_persistence_budget as budget
import persistence_setup_support as setup_support
from tests_gated.execution_core import (
    test_persistence_runtime_checkpoint_sqlite as checkpoint_sqlite,
)


def _sample_selection(connection) -> tuple[int, tuple[int, ...]]:
    connection.execute("BEGIN")
    try:
        started = perf_counter_ns()
        selected = repository.select_runtime_checkpoint(
            connection,
            checkpoint_sqlite._selection_request(),
        )
        elapsed = perf_counter_ns() - started
        assert selected.kind is records.RepositoryOutcomeKind.FOUND
        assert type(selected.record) is records.RuntimeCheckpointSelectionProof
        return elapsed, selected.record._selection.query_row_counts
    finally:
        connection.rollback()


def _measured_selection_samples(connection) -> tuple[tuple[int, ...], tuple[int, ...]]:
    _sample_selection(connection)
    elapsed: list[int] = []
    row_counts: tuple[int, ...] | None = None
    for _ in range(20):
        sample, observed_counts = _sample_selection(connection)
        elapsed.append(sample)
        if row_counts is None:
            row_counts = observed_counts
        else:
            assert observed_counts == row_counts

    assert row_counts is not None
    return tuple(elapsed), row_counts


def _sample_hydration(
    connection,
) -> tuple[int, tuple[int, ...], int]:
    traced: list[str] = []
    connection.execute("BEGIN")
    connection.set_trace_callback(traced.append)
    try:
        started = perf_counter_ns()
        context, proof, envelope = unit_of_work._m2_load_compact_context(
            connection,
            checkpoint_sqlite.base.APP_ID,
            checkpoint_sqlite.base.EXECUTION_PROFILE_ID,
            checkpoint_sqlite.base.MARKET_PROFILE_ID,
        )
        elapsed = perf_counter_ns() - started
    finally:
        connection.set_trace_callback(None)
        connection.rollback()

    assert envelope._provenance == "LOADED"
    assert (
        context.expected_checkpoint
        == unit_of_work._m2_checkpoint_head_from_envelope(envelope)
    )
    assert proof.request.expected_checkpoint == context.expected_checkpoint
    normalized = tuple(" ".join(statement.upper().split()) for statement in traced)
    assert not any(
        statement.startswith(("INSERT ", "UPDATE ", "DELETE ", "REPLACE "))
        for statement in normalized
    )
    read_count = sum(
        statement.startswith(("SELECT ", "WITH ")) for statement in normalized
    )
    assert read_count > len(proof._selection.query_row_counts)
    return elapsed, proof._selection.query_row_counts, read_count


def _measured_hydration_samples(
    connection,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], int]:
    _sample_hydration(connection)
    elapsed: list[int] = []
    read_counts: list[int] = []
    row_counts: tuple[int, ...] | None = None
    for _ in range(20):
        sample, observed_rows, observed_reads = _sample_hydration(connection)
        elapsed.append(sample)
        read_counts.append(observed_reads)
        if row_counts is None:
            row_counts = observed_rows
        else:
            assert observed_rows == row_counts

    tracemalloc.start()
    try:
        _sample_hydration(connection)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert row_counts is not None
    return tuple(elapsed), row_counts, tuple(read_counts), peak


def _store_checkpoint(connection) -> None:
    connection.execute("BEGIN")
    selected = repository.select_runtime_checkpoint(
        connection,
        checkpoint_sqlite._selection_request(),
    )
    assert selected.kind is records.RepositoryOutcomeKind.FOUND
    assert type(selected.record) is records.RuntimeCheckpointSelectionProof
    proof = selected.record
    envelope = checkpoint_sqlite._projected_envelope(proof)
    stored = repository.store_runtime_checkpoint(
        connection,
        proof,
        envelope,
        capability=setup_support.issue_setup_write_capability(connection),
    )
    assert stored.kind is records.RepositoryOutcomeKind.APPLIED
    connection.commit()


def _assert_direct_plans(connection) -> None:
    for sql, accesses, bounded_intermediates in zip(
        repository._RUNTIME_CHECKPOINT_SELECTION_SQL,
        repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS,
        repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_BOUNDED_INTERMEDIATES,
        strict=True,
    ):
        details = checkpoint_sqlite._explain_details(connection, sql)
        assert (
            checkpoint_sqlite._plan_access_violations(
                details,
                accesses,
                bounded_intermediates,
            )
            == ()
        )
    for sql, accesses in zip(
        (
            repository._RUNTIME_CHECKPOINT_HEAD_SELECT_SQL,
            repository._RUNTIME_CHECKPOINT_PAYLOAD_SELECT_SQL,
        ),
        repository._RUNTIME_CHECKPOINT_LOAD_PLAN_ACCESS,
        strict=True,
    ):
        details = checkpoint_sqlite._explain_details(connection, sql)
        assert checkpoint_sqlite._plan_access_violations(details, accesses) == ()


def _build_history_database(
    path: Path,
    row_count: int,
    monkeypatch: pytest.MonkeyPatch,
):
    connection = checkpoint_sqlite._open_fresh(path)
    checkpoint_sqlite._install_foundation(connection)
    _store_checkpoint(connection)
    monkeypatch.setattr(checkpoint_sqlite, "_PLAN_HISTORY_ROW_COUNT", row_count)
    checkpoint_sqlite._seed_unrelated_plan_history(connection)
    checkpoint_sqlite._assert_unrelated_plan_history_floor(connection)
    connection.execute("ANALYZE")
    return connection


def test_runtime_checkpoint_selection_and_hydration_stay_bounded_from_target_to_stress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen = budget.M2_PERSISTENCE_BUDGET
    target = _build_history_database(
        tmp_path / "target.db",
        frozen.target_unrelated_rows,
        monkeypatch,
    )
    stress = _build_history_database(
        tmp_path / "stress.db",
        frozen.stress_unrelated_rows,
        monkeypatch,
    )
    try:
        target_samples, target_counts = _measured_selection_samples(target)
        stress_samples, stress_counts = _measured_selection_samples(stress)

        runtime_growth = budget.growth_ratio(
            budget.percentile_95(target_samples),
            budget.percentile_95(stress_samples),
        )
        assert runtime_growth <= frozen.runtime_p95_growth_limit
        assert target_counts == stress_counts
        assert len(target_counts) == 13

        (
            target_hydration,
            target_hydration_rows,
            target_reads,
            target_peak,
        ) = _measured_hydration_samples(target)
        (
            stress_hydration,
            stress_hydration_rows,
            stress_reads,
            stress_peak,
        ) = _measured_hydration_samples(stress)
        startup_elapsed_growth = budget.growth_ratio(
            budget.percentile_95(target_hydration),
            budget.percentile_95(stress_hydration),
        )
        startup_select_growth = budget.growth_ratio(
            budget.percentile_95(target_reads),
            budget.percentile_95(stress_reads),
        )
        assert startup_elapsed_growth <= frozen.startup_select_and_elapsed_growth_limit
        assert startup_select_growth <= frozen.startup_select_and_elapsed_growth_limit
        assert target_hydration_rows == stress_hydration_rows == target_counts
        assert len(set(target_reads)) == len(set(stress_reads)) == 1
        assert target_reads == stress_reads
        assert max(target_peak, stress_peak) <= frozen.canonical_projection_peak_bytes

        _assert_direct_plans(target)
        _assert_direct_plans(stress)
    finally:
        target.close()
        stress.close()
