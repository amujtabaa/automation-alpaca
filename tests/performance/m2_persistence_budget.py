"""Frozen measured-budget helpers for the WO-0170 persisted M2 boundary."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Final, Iterable


@dataclass(frozen=True, slots=True)
class M2PersistenceBudget:
    target_unrelated_rows: int
    stress_unrelated_rows: int
    runtime_p95_growth_limit: float
    startup_select_and_elapsed_growth_limit: float
    canonical_projection_peak_bytes: int


M2_PERSISTENCE_BUDGET: Final = M2PersistenceBudget(
    target_unrelated_rows=1_000,
    stress_unrelated_rows=10_000,
    runtime_p95_growth_limit=3.0,
    startup_select_and_elapsed_growth_limit=12.0,
    canonical_projection_peak_bytes=2 * 1024 * 1024,
)


def percentile_95(samples_ns: Iterable[int]) -> int:
    samples = sorted(samples_ns)
    if not samples or any(type(value) is not int or value <= 0 for value in samples):
        raise ValueError("p95 samples must be positive exact integers")
    return samples[ceil(len(samples) * 0.95) - 1]


def growth_ratio(target: int, stress: int) -> float:
    if type(target) is not int or type(stress) is not int or target <= 0 or stress <= 0:
        raise ValueError("growth coordinates must be positive exact integers")
    return stress / target
