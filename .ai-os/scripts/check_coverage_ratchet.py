#!/usr/bin/env python3
"""Enforce independent, never-lower line and branch coverage ratchets.

Coverage.py reports a combined percentage when branch instrumentation is active.
That number mixes statement and branch denominators, so an improvement in one
dimension can conceal a regression in the other.  This validator consumes the
branch-aware JSON report and gates each dimension independently.

Usage:
  python .ai-os/scripts/check_coverage_ratchet.py coverage.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Sequence

LINE_MINIMUM_PERCENT = Decimal("93.00")
BRANCH_MINIMUM_PERCENT = Decimal("85.25")


@dataclass(frozen=True)
class CoverageRatchetResult:
    covered_lines: int | None
    num_statements: int | None
    covered_branches: int | None
    num_branches: int | None
    line_percent: Decimal | None
    branch_percent: Decimal | None
    problems: tuple[str, ...]


def _exact_nonnegative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _percent(covered: int, total: int) -> Decimal:
    return Decimal(covered) * Decimal(100) / Decimal(total)


def evaluate_report(report: object) -> CoverageRatchetResult:
    """Validate one coverage.py JSON value and return exact dimension results."""

    problems: list[str] = []
    if not isinstance(report, dict):
        problems.append("coverage report must be a JSON object")
        totals: object = None
        branch_enabled = False
    else:
        totals = report.get("totals")
        meta = report.get("meta")
        branch_enabled = isinstance(meta, dict) and meta.get("branch_coverage") is True
    if not branch_enabled:
        problems.append("coverage report must enable branch instrumentation")
    if not isinstance(totals, dict):
        problems.append("coverage report totals must be a JSON object")
        totals = {}

    covered_lines = _exact_nonnegative_int(totals.get("covered_lines"))
    num_statements = _exact_nonnegative_int(totals.get("num_statements"))
    covered_branches = _exact_nonnegative_int(totals.get("covered_branches"))
    num_branches = _exact_nonnegative_int(totals.get("num_branches"))
    for name, value in (
        ("covered_lines", covered_lines),
        ("num_statements", num_statements),
        ("covered_branches", covered_branches),
        ("num_branches", num_branches),
    ):
        if value is None:
            problems.append(
                f"coverage total {name!r} must be a non-negative exact integer"
            )

    line_percent: Decimal | None = None
    branch_percent: Decimal | None = None
    if num_statements == 0:
        problems.append("coverage statement denominator must be positive")
    if num_branches == 0:
        problems.append("coverage branch denominator must be positive")
    if covered_lines is not None and num_statements is not None and num_statements > 0:
        if covered_lines > num_statements:
            problems.append("covered lines cannot exceed the statement denominator")
        else:
            line_percent = _percent(covered_lines, num_statements)
            if line_percent < LINE_MINIMUM_PERCENT:
                problems.append(
                    "line coverage "
                    f"{line_percent:.6f}% is below {LINE_MINIMUM_PERCENT:.2f}%"
                )
    if covered_branches is not None and num_branches is not None and num_branches > 0:
        if covered_branches > num_branches:
            problems.append("covered branches cannot exceed the branch denominator")
        else:
            branch_percent = _percent(covered_branches, num_branches)
            if branch_percent < BRANCH_MINIMUM_PERCENT:
                problems.append(
                    "branch coverage "
                    f"{branch_percent:.6f}% is below {BRANCH_MINIMUM_PERCENT:.2f}%"
                )

    return CoverageRatchetResult(
        covered_lines=covered_lines,
        num_statements=num_statements,
        covered_branches=covered_branches,
        num_branches=num_branches,
        line_percent=line_percent,
        branch_percent=branch_percent,
        problems=tuple(problems),
    )


def _display_dimension(
    label: str,
    covered: int | None,
    total: int | None,
    percent: Decimal | None,
    minimum: Decimal,
) -> str:
    shown_percent = "invalid" if percent is None else f"{percent:.6f}%"
    return f"{label}: {covered}/{total} = {shown_percent} (minimum {minimum:.2f}%)"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="coverage.py JSON report")
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print("COVERAGE RATCHET FAILED")
        print(f"- unable to read coverage report: {exc}")
        return 1

    result = evaluate_report(report)
    print(
        "COVERAGE RATCHET PASSED" if not result.problems else "COVERAGE RATCHET FAILED"
    )
    print(
        _display_dimension(
            "lines",
            result.covered_lines,
            result.num_statements,
            result.line_percent,
            LINE_MINIMUM_PERCENT,
        )
    )
    print(
        _display_dimension(
            "branches",
            result.covered_branches,
            result.num_branches,
            result.branch_percent,
            BRANCH_MINIMUM_PERCENT,
        )
    )
    for problem in result.problems:
        print(f"- {problem}")
    return 1 if result.problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
