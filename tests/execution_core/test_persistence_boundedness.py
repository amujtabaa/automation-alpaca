"""Pure pins for the measured WO-0170 M2 persistence budget."""

from __future__ import annotations

import pytest

from app.execution_core.persistence import repository
from harness.m2 import closeout
from tests.performance import m2_persistence_budget as budget


def test_m2_budget_inherits_the_frozen_target_stress_ratio_and_ceilings() -> None:
    frozen = budget.M2_PERSISTENCE_BUDGET

    assert frozen.target_unrelated_rows == 1_000
    assert frozen.stress_unrelated_rows == 10_000
    assert frozen.stress_unrelated_rows / frozen.target_unrelated_rows == 10
    assert frozen.runtime_p95_growth_limit == 3.0
    assert frozen.startup_select_and_elapsed_growth_limit == 12.0
    assert frozen.canonical_projection_peak_bytes == 2 * 1024 * 1024


def test_budget_math_is_exact_and_failure_capable() -> None:
    assert budget.percentile_95(range(1, 21)) == 19
    assert budget.growth_ratio(100, 299) == 2.99
    assert budget.growth_ratio(100, 301) > (
        budget.M2_PERSISTENCE_BUDGET.runtime_p95_growth_limit
    )

    for samples in ((), (0,), (1, True)):
        with pytest.raises(ValueError, match="positive exact integers"):
            budget.percentile_95(samples)
    for coordinates in ((0, 1), (1, 0), (True, 1), (1, 1.5)):
        with pytest.raises(ValueError, match="positive exact integers"):
            budget.growth_ratio(*coordinates)  # type: ignore[arg-type]


def test_runtime_checkpoint_directness_manifest_remains_fixed_and_indexed() -> None:
    assert len(repository._RUNTIME_CHECKPOINT_SELECTION_SQL) == 13
    assert len(repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS) == 13
    assert len(repository._RUNTIME_CHECKPOINT_LOAD_PLAN_ACCESS) == 2
    assert all(
        accesses for accesses in repository._RUNTIME_CHECKPOINT_SELECTION_PLAN_ACCESS
    )
    assert {case.obligation for case in closeout.BOUNDEDNESS_CASES} == {
        "direct-current-proof",
        "checkpoint-query-plans",
        "target-stress-measurement",
        "startup-no-history-fold",
    }
