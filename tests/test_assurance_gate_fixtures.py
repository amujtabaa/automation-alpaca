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
