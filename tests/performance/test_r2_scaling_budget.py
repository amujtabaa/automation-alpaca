"""Executable beta-scale budget contract for both R2 scaling gates."""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

from tests.performance import r2_scaling_budget as budget
from tests.performance import r2_scaling_gate as canonical_gate
from tests.performance import r2_scaling_gate_claude_ported as ported_gate

EXPECTED_TARGET = {
    "symbols": 100,
    "envelopes": 1_001,
    "events": 10_002,
    "recoveries": 1_000,
}
EXPECTED_STRESS = {
    "symbols": 1_000,
    "envelopes": 10_001,
    "events": 100_002,
    "recoveries": 10_000,
}
PROTECTED_LIMIT_NAMES = {
    "RUNTIME_SCALE_LIMIT",
    "STARTUP_SCALE_LIMIT",
    "PROJECTION_PEAK_LIMIT_BYTES",
}


@pytest.mark.parametrize("gate", [canonical_gate, ported_gate])
def test_both_gates_share_the_frozen_budget(gate: ModuleType) -> None:
    assert budget.BETA_TARGET_CARDINALITY == EXPECTED_TARGET
    assert budget.BETA_STRESS_CARDINALITY == EXPECTED_STRESS
    assert budget.RUNTIME_SCALE_LIMIT == 3.0
    assert budget.STARTUP_SCALE_LIMIT == 12.0
    assert budget.PROJECTION_PEAK_LIMIT_BYTES == 2 * 1024 * 1024

    assert budget.dataset_cardinality(gate.REALISTIC) == EXPECTED_TARGET
    assert budget.dataset_cardinality(gate.STRESS) == EXPECTED_STRESS
    assert gate.RUNTIME_SCALE_LIMIT == budget.RUNTIME_SCALE_LIMIT
    assert gate.STARTUP_SCALE_LIMIT == budget.STARTUP_SCALE_LIMIT


@pytest.mark.parametrize("gate", [canonical_gate, ported_gate])
def test_each_gate_applies_one_shared_budget_contract(gate: ModuleType) -> None:
    source = Path(gate.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "apply_beta_scale_budget"
    ]
    assert len(calls) == 1

    local_limit_assignments = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and target.id in PROTECTED_LIMIT_NAMES
    }
    assert local_limit_assignments == set()


def test_cardinality_drift_and_missing_stress_assertion_turn_red() -> None:
    gates = budget.cardinality_gates(
        target=EXPECTED_TARGET,
        stress=EXPECTED_STRESS,
    )
    assert all(gates.values())

    drifted_stress = {**EXPECTED_STRESS, "events": 100_001}
    assert not all(
        budget.cardinality_gates(
            target=EXPECTED_TARGET,
            stress=drifted_stress,
        ).values()
    )

    stress_gates = {name: True for name in budget.REQUIRED_STRESS_GATES}
    assert budget.stress_contract_complete(stress_gates)
    stress_gates.pop(next(iter(budget.REQUIRED_STRESS_GATES)))
    assert not budget.stress_contract_complete(stress_gates)


def test_report_exposes_measured_headroom_without_rebudgeting() -> None:
    ratios = {
        "stress_runtime_p95_over_realistic": 1.25,
        "stress_startup_select_over_realistic": 9.9,
        "stress_startup_elapsed_over_realistic": 11.4,
    }
    stress_gates = {name: True for name in budget.REQUIRED_STRESS_GATES}
    report: dict[str, object] = {"gates": stress_gates, "ratios": ratios}

    budget.apply_beta_scale_budget(
        report,
        target=EXPECTED_TARGET,
        stress=EXPECTED_STRESS,
        stress_executed=True,
    )

    contract = report["beta_scale_budget"]
    assert isinstance(contract, dict)
    assert contract["target_cardinality"] == EXPECTED_TARGET
    assert contract["stress_cardinality"] == EXPECTED_STRESS
    assert contract["limits"] == {
        "runtime_p95_ratio_max": 3.0,
        "startup_growth_ratio_max": 12.0,
        "projection_peak_bytes_max": 2 * 1024 * 1024,
    }
    assert contract["measured_ratio_margin"] == {
        "runtime_p95": 1.75,
        "startup_selects": pytest.approx(2.1),
        "startup_elapsed": pytest.approx(0.6),
    }
    assert report["passed"] is True
