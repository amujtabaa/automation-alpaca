"""Measured target/stress boundedness proof for the M2 checkpoint selector."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter_ns
import tracemalloc

import pytest

from app.execution_core.persistence import records, repository
from tests.performance import m2_persistence_budget as budget
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


def _measured_samples(connection) -> tuple[tuple[int, ...], tuple[int, ...], int]:
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

    tracemalloc.start()
    try:
        _sample_selection(connection)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert row_counts is not None
    return tuple(elapsed), row_counts, peak


def _build_history_database(
    path: Path,
    row_count: int,
    monkeypatch: pytest.MonkeyPatch,
):
    connection = checkpoint_sqlite._open_fresh(path)
    checkpoint_sqlite._install_foundation(connection)
    monkeypatch.setattr(checkpoint_sqlite, "_PLAN_HISTORY_ROW_COUNT", row_count)
    checkpoint_sqlite._seed_unrelated_plan_history(connection)
    checkpoint_sqlite._assert_unrelated_plan_history_floor(connection)
    connection.execute("ANALYZE")
    return connection


def test_runtime_checkpoint_selection_stays_bounded_from_target_to_stress(
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
        target_samples, target_counts, target_peak = _measured_samples(target)
        stress_samples, stress_counts, stress_peak = _measured_samples(stress)

        runtime_growth = budget.growth_ratio(
            budget.percentile_95(target_samples),
            budget.percentile_95(stress_samples),
        )
        assert runtime_growth <= frozen.runtime_p95_growth_limit
        assert target_counts == stress_counts
        assert len(target_counts) == 13
        assert max(target_peak, stress_peak) <= frozen.canonical_projection_peak_bytes

        for sql, accesses, bounded_intermediates in zip(
            repository._RUNTIME_CHECKPOINT_SELECTION_SQL,
            repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS,
            repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_BOUNDED_INTERMEDIATES,
            strict=True,
        ):
            details = checkpoint_sqlite._explain_details(stress, sql)
            assert (
                checkpoint_sqlite._plan_access_violations(
                    details,
                    accesses,
                    bounded_intermediates,
                )
                == ()
            )
    finally:
        target.close()
        stress.close()
