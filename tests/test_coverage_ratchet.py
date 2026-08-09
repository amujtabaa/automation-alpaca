"""Failure-capable pins for the independent line and branch coverage ratchets."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from decimal import Decimal
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / ".ai-os" / "scripts"


def _load_checker():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "check_coverage_ratchet",
        _SCRIPTS / "check_coverage_ratchet.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _report(
    *,
    covered_lines: int = 24_819,
    num_statements: int = 26_530,
    covered_branches: int = 8_457,
    num_branches: int = 9_920,
) -> dict[str, object]:
    return {
        "meta": {"branch_coverage": True},
        "totals": {
            "covered_lines": covered_lines,
            "num_statements": num_statements,
            "covered_branches": covered_branches,
            "num_branches": num_branches,
        },
    }


def test_current_exact_totals_pass_both_independent_ratchets() -> None:
    assert checker.LINE_MINIMUM_PERCENT == Decimal("93.00")
    assert checker.BRANCH_MINIMUM_PERCENT == Decimal("85.25")
    result = checker.evaluate_report(_report())

    assert result.problems == ()
    assert result.line_percent == checker.LINE_MINIMUM_PERCENT or (
        result.line_percent > checker.LINE_MINIMUM_PERCENT
    )
    assert result.branch_percent >= checker.BRANCH_MINIMUM_PERCENT


def test_line_regression_cannot_hide_behind_branch_improvement() -> None:
    result = checker.evaluate_report(
        _report(
            covered_lines=92_999,
            num_statements=100_000,
            covered_branches=100_000,
            num_branches=100_000,
        )
    )

    assert any("line coverage" in problem for problem in result.problems)
    assert not any("branch coverage" in problem for problem in result.problems)


def test_branch_regression_cannot_hide_behind_line_improvement() -> None:
    result = checker.evaluate_report(
        _report(
            covered_lines=100_000,
            num_statements=100_000,
            covered_branches=85_249,
            num_branches=100_000,
        )
    )

    assert any("branch coverage" in problem for problem in result.problems)
    assert not any("line coverage" in problem for problem in result.problems)


def test_exact_thresholds_pass_without_rounding_down() -> None:
    result = checker.evaluate_report(
        _report(
            covered_lines=9_300,
            num_statements=10_000,
            covered_branches=8_525,
            num_branches=10_000,
        )
    )

    assert result.problems == ()


def test_missing_and_impossible_totals_fail_closed() -> None:
    reports: tuple[dict[str, object], ...] = (
        {},
        {"totals": {}},
        _report(num_statements=0),
        _report(num_branches=0),
        _report(covered_lines=26_531),
        _report(covered_branches=9_921),
    )

    for report in reports:
        assert checker.evaluate_report(report).problems


def test_negative_totals_are_rejected_in_an_otherwise_valid_report() -> None:
    for field in (
        "covered_lines",
        "num_statements",
        "covered_branches",
        "num_branches",
    ):
        report = _report()
        totals = report["totals"]
        assert isinstance(totals, dict)
        totals[field] = -1

        result = checker.evaluate_report(report)

        assert result.problems == (
            f"coverage total {field!r} must be a non-negative exact integer",
        )


def test_boolean_total_is_rejected_without_an_unrelated_metadata_failure() -> None:
    report = _report()
    totals = report["totals"]
    assert isinstance(totals, dict)
    totals["covered_lines"] = True

    result = checker.evaluate_report(report)

    assert result.problems == (
        "coverage total 'covered_lines' must be a non-negative exact integer",
    )


def test_non_branch_report_is_rejected_with_otherwise_valid_totals() -> None:
    report = _report()
    report["meta"] = {"branch_coverage": False}

    result = checker.evaluate_report(report)

    assert result.problems == ("coverage report must enable branch instrumentation",)


def test_ci_generates_branch_json_then_enforces_both_exact_ratchets() -> None:
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    measurement = (
        "pytest --cov=app --cov-branch --cov-report=term-missing "
        "--cov-report=json:coverage.json"
    )
    enforcement = "python .ai-os/scripts/check_coverage_ratchet.py coverage.json"

    assert workflow.count(measurement) == 1
    assert workflow.count(enforcement) == 1
    assert workflow.index(measurement) < workflow.index(enforcement)

    configuration = tomllib.loads((_ROOT / "pyproject.toml").read_text("utf-8"))
    assert configuration["tool"]["coverage"]["run"] == {
        "source": ["app"],
        "branch": True,
    }
    assert configuration["tool"]["coverage"]["report"]["fail_under"] == 0


def test_cli_reports_both_dimensions_and_fails_a_regression(
    tmp_path: Path,
    capsys,
) -> None:
    report_path = tmp_path / "coverage.json"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")

    assert checker.main([str(report_path)]) == 0
    output = capsys.readouterr().out
    assert "COVERAGE RATCHET PASSED" in output
    assert "lines: 24819/26530" in output
    assert "branches: 8457/9920" in output

    report_path.write_text(
        json.dumps(_report(covered_branches=8_456)),
        encoding="utf-8",
    )
    assert checker.main([str(report_path)]) == 1
    output = capsys.readouterr().out
    assert "COVERAGE RATCHET FAILED" in output
    assert "branch coverage" in output


def test_cli_fails_closed_for_invalid_json_and_a_missing_report(
    tmp_path: Path,
    capsys,
) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not json", encoding="utf-8")

    assert checker.main([str(invalid)]) == 1
    output = capsys.readouterr().out
    assert "COVERAGE RATCHET FAILED" in output
    assert "unable to read coverage report" in output

    missing = tmp_path / "missing.json"
    assert checker.main([str(missing)]) == 1
    output = capsys.readouterr().out
    assert "COVERAGE RATCHET FAILED" in output
    assert "unable to read coverage report" in output
