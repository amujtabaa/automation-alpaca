"""Pure closeout controls for the finite M2 persistence fault matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.execution_core.persistence import unit_of_work
from harness.m2 import closeout, soak
from tests.execution_core import test_persistence_unit_of_work as uow_faults


def test_closeout_catalog_is_finite_complete_and_points_to_real_tests() -> None:
    closeout.validate_catalog()
    root = Path(__file__).resolve().parents[2]

    assert closeout.missing_nodeids(root) == ()
    assert len(closeout.FAULT_CASES) == len(closeout.FAULT_OBLIGATIONS)
    assert len(closeout.MUTANT_CASES) == len(closeout.MUTANT_OBLIGATIONS)
    assert {case.case_id for case in closeout.FAULT_CASES} == {
        f"F{ordinal:02d}" for ordinal in range(1, 20)
    }
    assert {case.case_id for case in closeout.MUTANT_CASES} == {
        f"M{ordinal:02d}" for ordinal in range(1, 11)
    }


@pytest.mark.parametrize("obligation", closeout.FAULT_OBLIGATIONS)
def test_removing_any_fault_obligation_breaks_catalog_validation(
    obligation: str,
) -> None:
    mutant = tuple(
        case for case in closeout.FAULT_CASES if case.obligation != obligation
    )

    with pytest.raises(closeout.CloseoutCatalogError, match="fault obligations"):
        closeout.validate_catalog(fault_cases=mutant)


@pytest.mark.parametrize("obligation", closeout.MUTANT_OBLIGATIONS)
def test_removing_any_mutant_obligation_breaks_catalog_validation(
    obligation: str,
) -> None:
    mutant = tuple(
        case for case in closeout.MUTANT_CASES if case.obligation != obligation
    )

    with pytest.raises(closeout.CloseoutCatalogError, match="mutant obligations"):
        closeout.validate_catalog(mutant_cases=mutant)


def test_uow_fault_generator_covers_every_current_repository_write_before_and_after() -> (
    None
):
    cases = uow_faults._catalogued_write_fault_cases()
    observed = {
        (method_name, phase)
        for _edge, phase, call_path, _index in cases
        for method_name in call_path
    }

    assert observed == {
        (method_name, phase)
        for method_name in unit_of_work._M2_REPOSITORY_WRITE_CALLS
        for phase in ("before", "after")
    }
    assert all(edge.startswith(("F04:", "COMMON:")) for edge, *_rest in cases)


def test_soak_schedule_is_exact_ordered_and_never_launders_a_short_run() -> None:
    assert len(closeout.SOAK_NODEIDS) == len(set(closeout.SOAK_NODEIDS)) == 7
    assert any(nodeid.startswith("tests_gated/") for nodeid in closeout.SOAK_NODEIDS)
    assert (
        soak.soak_status(
            configured_seconds=86_400,
            elapsed_seconds=86_400,
            passed=True,
        )
        == "PASSED"
    )
    assert (
        soak.soak_status(
            configured_seconds=86_400,
            elapsed_seconds=86_399.999,
            passed=True,
        )
        == "NOT_RUN"
    )
    assert (
        soak.soak_status(
            configured_seconds=60,
            elapsed_seconds=90,
            passed=True,
        )
        == "NOT_RUN"
    )
    assert (
        soak.soak_status(
            configured_seconds=86_400,
            elapsed_seconds=86_400,
            passed=False,
        )
        == "FAILED"
    )
