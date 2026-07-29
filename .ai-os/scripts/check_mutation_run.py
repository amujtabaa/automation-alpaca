#!/usr/bin/env python3
"""Classify a mutmut run and enforce the survivor ratchet (REV-0045 P1-5 repair).

The previous workflow counted result lines with ``grep -cE "^[a-zA-Z_]"``, but
mutmut 3.6.0 prints every result as ``f"    {k}: {status}"`` — four leading
spaces — and suppresses killed results entirely unless ``--all`` is passed. Both
a survivors run and an all-killed run therefore counted zero and tripped the
NO_MUTANTS guard, so the job was permanently red and the ratchet unreachable.
The guard added to make silence fail loudly instead made every run fail
uselessly, which is the same inert-evidence class in a different costume.

Parsing lives here, not in shell, so it can be exercised by committed fixtures
of real mutmut output without running a mutation pass in CI.

Run states (distinct, because they carry different evidentiary meaning):

  COMPLETE_CLEAN      mutants generated, none survived, none indeterminate
  COMPLETE_SURVIVORS  mutants generated, at least one survived or uncovered
  INDETERMINATE       timeouts/segfaults/unchecked results — NOT a pass
  NO_MUTANTS          empty population: scope or config is broken
  TOOL_ERROR          unparseable output

Usage:
  mutmut results --all True > results.txt
  python .ai-os/scripts/check_mutation_run.py results.txt --max-survivors N
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field

# mutmut/__main__.py: status_by_exit_code
SURVIVOR_STATUSES = frozenset({"survived", "no tests"})
KILLED_STATUSES = frozenset({"killed"})
BENIGN_STATUSES = frozenset({"skipped", "caught by type check"})
INDETERMINATE_STATUSES = frozenset(
    {
        "timeout",
        "segfault",
        "suspicious",
        "not checked",
        "check was interrupted by user",
    }
)

# Tolerates leading whitespace by design — presentation must not change meaning.
_RESULT = re.compile(r"^\s*(?P<key>\S+):\s*(?P<status>[a-z][a-z ]*[a-z]|[a-z])\s*$")


@dataclass
class RunReport:
    state: str
    killed: int = 0
    survived: int = 0
    indeterminate: int = 0
    benign: int = 0
    unknown_statuses: set[str] = field(default_factory=set)

    @property
    def generated(self) -> int:
        return self.killed + self.survived + self.indeterminate + self.benign


def classify(output: str) -> RunReport:
    """Classify mutmut result output into a run state and counts."""

    report = RunReport(state="NO_MUTANTS")
    for line in output.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _RESULT.match(line)
        if match is None:
            continue
        status = match.group("status").strip()
        if status in KILLED_STATUSES:
            report.killed += 1
        elif status in SURVIVOR_STATUSES:
            report.survived += 1
        elif status in INDETERMINATE_STATUSES:
            report.indeterminate += 1
        elif status in BENIGN_STATUSES:
            report.benign += 1
        else:
            report.unknown_statuses.add(status)
            report.indeterminate += 1

    if report.generated == 0:
        report.state = "NO_MUTANTS"
    elif report.indeterminate:
        report.state = "INDETERMINATE"
    elif report.survived:
        report.state = "COMPLETE_SURVIVORS"
    else:
        report.state = "COMPLETE_CLEAN"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", help="file holding `mutmut results --all True` output")
    parser.add_argument("--max-survivors", type=int, required=True)
    args = parser.parse_args(argv)

    try:
        output = open(args.results, encoding="utf-8").read()
    except OSError as exc:
        print(f"TOOL_ERROR — cannot read results: {exc}")
        return 1

    report = classify(output)
    print(
        f"run state: {report.state} (generated={report.generated} "
        f"killed={report.killed} survived={report.survived} "
        f"indeterminate={report.indeterminate} benign={report.benign})"
    )
    if report.unknown_statuses:
        print(f"unknown statuses seen: {sorted(report.unknown_statuses)}")

    if report.state == "NO_MUTANTS":
        print("::error::NO_MUTANTS — empty population; scope or config is broken")
        return 1
    if report.state == "INDETERMINATE":
        print(
            "::error::INDETERMINATE — timeouts/segfaults/unchecked mutants; "
            "a run that did not finish is not evidence"
        )
        return 1
    if report.survived > args.max_survivors:
        print(
            f"::error::ratchet regressed: {report.survived} survivors "
            f"> {args.max_survivors}"
        )
        return 1
    print(f"ratchet OK: {report.survived} survivors <= {args.max_survivors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
