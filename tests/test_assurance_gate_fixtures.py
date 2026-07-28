"""Negative fixtures for the P-6 hygiene gates (AUDIT-0003 corrected meta-law).

A mandatory control is durable only when it is machine-consumed, semantically
complete, failure-capable, exercised by a COMMITTED negative fixture, and
current. The two P-6 gates were verified red on planted violations at landing
time, but that evidence lived only in a session transcript — the exact
attestation-only decay class S-5 names. These fixtures make failure-capability
a property of the tree: each builds a minimal violating corpus in tmp_path and
asserts the checker REFUSES it, alongside a clean corpus it must ACCEPT.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / ".ai-os" / "scripts"))

from check_ledger import validate_ledger  # noqa: E402
from check_work_order_disposition import analyze  # noqa: E402


def _fixture_root(tmp_path: Path) -> Path:
    # No rules file on purpose: load_yaml_list returns [] for a missing
    # vocabulary, which skips status-vocabulary checks — these fixtures pin
    # ONLY the P-6 predicates, hermetically.
    root = tmp_path / "repo"
    (root / "work" / "review").mkdir(parents=True)
    return root


def _fixture_root(tmp_path: Path) -> Path:  # noqa: F811 - alias for per-case roots
    root = Path(tmp_path) / "repo"
    (root / "work" / "review").mkdir(parents=True)
    return root


def _row(**over: object) -> str:
    row: dict[str, object] = {
        "id": "WO-9999",
        "title": "fixture",
        "status": "CLOSED",
        "disposition": ["ARCHIVED"],
        "commit": "a" * 7,
        "date": "2026-07-29",
        "reason": "fixture",
    }
    row.update(over)
    return json.dumps(row) + "\n"


def test_ledger_gate_refuses_head_commit_after_cutoff(tmp_path) -> None:
    root = _fixture_root(tmp_path)
    (root / "work" / "ledger.jsonl").write_text(_row(commit="HEAD"))
    problems = validate_ledger(root)
    assert any("not a hex SHA" in p for p in problems), problems


def test_ledger_gate_accepts_hex_sha_and_grandfathers_old_rows(tmp_path) -> None:
    root = _fixture_root(tmp_path)
    (root / "work" / "ledger.jsonl").write_text(
        _row() + _row(id="WO-9998", commit="HEAD", date="2026-07-01")
    )
    assert validate_ledger(root) == []


def test_packet_gate_refuses_disposition_without_result(tmp_path) -> None:
    root = _fixture_root(tmp_path)
    packet = root / "work" / "review" / "REV-9999"
    packet.mkdir()
    (packet / "disposition.md").write_text("verdict: ACCEPT\n")
    (root / "work" / "ledger.jsonl").write_text("")
    failures, _ = analyze(root)
    assert any("REV-9999" in f and "without any result" in f for f in failures), (
        failures
    )


def test_packet_gate_accepts_result_without_disposition(tmp_path) -> None:
    """The inverse is legitimate open-gate state and must NOT be flagged."""
    root = _fixture_root(tmp_path)
    packet = root / "work" / "review" / "REV-9998"
    packet.mkdir()
    (packet / "result.md").write_text("verdict: BLOCK\n")
    (root / "work" / "ledger.jsonl").write_text("")
    failures, _ = analyze(root)
    assert failures == [], failures


# --------------------------------------------------------------------------- #
# REV-0045 addendum-03 repairs — adversarial fixtures for P1-5 and P1-6
# --------------------------------------------------------------------------- #

sys.path.insert(0, str(REPO / ".ai-os" / "scripts"))
from check_mutation_run import classify  # noqa: E402

# Verbatim mutmut 3.6.0 output shape: `print(f"    {k}: {status}")` — four
# leading spaces. The previous workflow grep anchored on `^[a-zA-Z_]` and could
# never match this, which is exactly what P1-5 recorded.
_MUTMUT_SURVIVORS = """
# app/events/projectors.py
    app.events.projectors.fold_str__mutmut_1: survived
    app.events.projectors.fold_str__mutmut_2: killed
"""
_MUTMUT_ALL_KILLED = """
# app/events/projectors.py
    app.events.projectors.fold_str__mutmut_1: killed
    app.events.projectors.fold_str__mutmut_2: killed
"""
_MUTMUT_TIMEOUT = """
    app.events.projectors.fold_str__mutmut_1: timeout
    app.events.projectors.fold_str__mutmut_2: killed
"""


def test_classifier_reads_indented_mutmut_output() -> None:
    """The exact defect: four leading spaces must not hide a survivor."""

    report = classify(_MUTMUT_SURVIVORS)
    assert report.state == "COMPLETE_SURVIVORS"
    assert (report.killed, report.survived) == (1, 1)


def test_classifier_distinguishes_all_killed_from_empty() -> None:
    """Without --all, mutmut hides killed results and a clean run looks empty;
    the classifier must tell COMPLETE_CLEAN from NO_MUTANTS."""

    assert classify(_MUTMUT_ALL_KILLED).state == "COMPLETE_CLEAN"
    assert classify("").state == "NO_MUTANTS"
    assert classify("# app/events/projectors.py\n").state == "NO_MUTANTS"


def test_classifier_refuses_to_call_an_unfinished_run_clean() -> None:
    """A timeout is not a kill — an incomplete run is never evidence."""

    report = classify(_MUTMUT_TIMEOUT)
    assert report.state == "INDETERMINATE"
    assert report.indeterminate == 1


def test_classifier_counts_uncovered_mutants_as_survivors() -> None:
    assert classify("    x: no tests\n").state == "COMPLETE_SURVIVORS"


def test_ledger_gate_refuses_blank_or_null_date_with_head_commit(tmp_path) -> None:
    """P1-6: `if date:` let blank/null dates bypass BOTH the format check and
    the commit-SHA ratchet, re-admitting the exact `commit: "HEAD"` form."""

    for blank in ("", None):
        root = _fixture_root(tmp_path / f"d{blank!r}")
        (root / "work" / "ledger.jsonl").write_text(_row(commit="HEAD", date=blank))
        problems = validate_ledger(root)
        assert any("YYYY-MM-DD" in p for p in problems), (blank, problems)


def test_ledger_gate_refuses_a_non_string_date(tmp_path) -> None:
    root = _fixture_root(tmp_path / "dint")
    (root / "work" / "ledger.jsonl").write_text(_row(commit="HEAD", date=20260729))
    assert any("YYYY-MM-DD" in p for p in validate_ledger(root))
