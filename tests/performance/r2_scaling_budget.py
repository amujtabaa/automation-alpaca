"""Shared, fail-closed beta-scale budget for the explicit R2 gates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

RUNTIME_SCALE_LIMIT = 3.0
STARTUP_SCALE_LIMIT = 12.0
PROJECTION_PEAK_LIMIT_BYTES = 2 * 1024 * 1024

# WO-0115's real-paper inventory is unavailable because its source path is not
# ratified.  These values are therefore the declared beta design target and the
# approximately-10x stress corpus, never a claim about observed customer data.
BETA_TARGET_CARDINALITY = {
    "symbols": 100,
    "envelopes": 1_001,
    "events": 10_002,
    "recoveries": 1_000,
}
BETA_STRESS_CARDINALITY = {
    "symbols": 1_000,
    "envelopes": 10_001,
    "events": 100_002,
    "recoveries": 10_000,
}

REQUIRED_STRESS_GATES = (
    "stress_runtime_query_count_independent_of_scale",
    "stress_runtime_has_no_unrelated_full_scan",
    "stress_runtime_p95_over_realistic_le_3x",
    "stress_startup_select_growth_for_10x_facts_le_12x",
    "stress_startup_elapsed_growth_for_10x_facts_le_12x",
)


class DatasetLike(Protocol):
    symbols: int
    envelopes: int
    events: int
    generations: int


def dataset_cardinality(dataset: DatasetLike) -> dict[str, int]:
    """Return the four facts that define one gate corpus."""

    return {
        "symbols": dataset.symbols,
        "envelopes": dataset.envelopes,
        "events": dataset.events,
        "recoveries": dataset.symbols * dataset.generations,
    }


def cardinality_gates(
    *, target: Mapping[str, int], stress: Mapping[str, int]
) -> dict[str, bool]:
    """Pin the target and stress corpus independently of wall-clock noise."""

    return {
        "beta_target_cardinality_matches_declared_budget": (
            dict(target) == BETA_TARGET_CARDINALITY
        ),
        "beta_stress_cardinality_matches_declared_budget": (
            dict(stress) == BETA_STRESS_CARDINALITY
        ),
    }


def stress_contract_complete(gates: Mapping[str, object]) -> bool:
    """Reject removal of any structural or wall-clock stress assertion."""

    return all(name in gates for name in REQUIRED_STRESS_GATES)


def _cardinality_headroom(
    *, target: Mapping[str, int], stress: Mapping[str, int]
) -> dict[str, float]:
    return {name: stress[name] / target[name] for name in BETA_TARGET_CARDINALITY}


def _measured_ratio_margin(ratios: Mapping[str, float]) -> dict[str, float]:
    required = {
        "runtime_p95": (
            RUNTIME_SCALE_LIMIT,
            "stress_runtime_p95_over_realistic",
        ),
        "startup_selects": (
            STARTUP_SCALE_LIMIT,
            "stress_startup_select_over_realistic",
        ),
        "startup_elapsed": (
            STARTUP_SCALE_LIMIT,
            "stress_startup_elapsed_over_realistic",
        ),
    }
    if not all(ratio_name in ratios for _, ratio_name in required.values()):
        return {}
    return {
        label: limit - ratios[ratio_name]
        for label, (limit, ratio_name) in required.items()
    }


def beta_scale_budget_report(
    *,
    target: Mapping[str, int],
    stress: Mapping[str, int],
    stress_executed: bool,
    gates: Mapping[str, object],
    ratios: Mapping[str, float],
) -> dict[str, Any]:
    """Build the auditable budget section included in each JSON gate report."""

    return {
        "inventory_basis": (
            "declared beta design target; observed paper inventory unavailable "
            "until WO-0115 receives a ratified source database path"
        ),
        "target_cardinality": dict(target),
        "stress_cardinality": dict(stress),
        "declared_cardinality_headroom": _cardinality_headroom(
            target=target,
            stress=stress,
        ),
        "limits": {
            "runtime_p95_ratio_max": RUNTIME_SCALE_LIMIT,
            "startup_growth_ratio_max": STARTUP_SCALE_LIMIT,
            "projection_peak_bytes_max": PROJECTION_PEAK_LIMIT_BYTES,
        },
        "stress_executed": stress_executed,
        "stress_assertions": {
            name: gates.get(name) if stress_executed else None
            for name in REQUIRED_STRESS_GATES
        },
        "measured_ratio_margin": (
            _measured_ratio_margin(ratios) if stress_executed else {}
        ),
        "limits_changed": False,
    }


def apply_beta_scale_budget(
    report: dict[str, Any],
    *,
    target: Mapping[str, int],
    stress: Mapping[str, int],
    stress_executed: bool,
) -> None:
    """Attach the budget and make every declared contract part of ``passed``."""

    gates = report.get("gates")
    ratios = report.get("ratios")
    if not isinstance(gates, dict) or not isinstance(ratios, dict):
        raise TypeError("scaling report must contain mutable gates and ratios mappings")

    gates.update(cardinality_gates(target=target, stress=stress))
    gates["stress_budget_contract_complete"] = (
        stress_contract_complete(gates) if stress_executed else True
    )
    report["beta_scale_budget"] = beta_scale_budget_report(
        target=target,
        stress=stress,
        stress_executed=stress_executed,
        gates=gates,
        ratios=ratios,
    )
    report["passed"] = all(gates.values())
