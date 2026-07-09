"""Tests for check_review_packet.py — the cross-model review-packet checker.

Self-contained: builds a minimal package-layout temp repo (AI_OS_MANIFEST.yaml +
the real rules/ai-os-rules.yaml + work/review/…) and runs the script via
subprocess, so it does not depend on the package-vs-installed fixtures.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from conftest import PKG, SCRIPTS, run_script

CHECK = SCRIPTS / "check_review_packet.py"

_REQUEST = """\
---
type: Review Request
rev_id: {rev}
title: sample
status: {status}
targets: [{targets}]
human_gated_surfaces: [manual-flatten]
commit_range: aaa..bbb
reviewer_model: null
verdict: null
created: 2026-07-09
---

# body
"""

_RESULT = """\
---
type: Review Result
rev_id: {rev}
reviewer_model: gpt-5
verdict: {verdict}
date: 2026-07-09
---

# result
"""


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "rules").mkdir(parents=True)
    (root / "AI_OS_MANIFEST.yaml").write_text('os_version: "0.0.0"\n', encoding="utf-8")
    shutil.copy(PKG / "rules" / "ai-os-rules.yaml", root / "rules" / "ai-os-rules.yaml")
    (root / "work" / "review").mkdir(parents=True)
    return root


def _packet(root: Path, rev: str, *, status="AWAITING_REVIEW", targets="WO-0001",
            verdict=None, disposition: str | None = None) -> Path:
    folder = root / "work" / "review" / f"{rev}-sample"
    folder.mkdir(parents=True)
    (folder / "request.md").write_text(
        _REQUEST.format(rev=rev, status=status, targets=targets), encoding="utf-8")
    if verdict is not None:
        (folder / "result.md").write_text(_RESULT.format(rev=rev, verdict=verdict), encoding="utf-8")
    if disposition is not None:
        (folder / "disposition.md").write_text(disposition, encoding="utf-8")
    return folder


def _run(root: Path):
    return run_script(CHECK, cwd=root)


def test_awaiting_review_packet_passes(tmp_path):
    root = _repo(tmp_path)
    _packet(root, "REV-0001")
    r = _run(root)
    assert r.returncode == 0, r.stdout
    assert "REVIEW PACKET CHECK PASSED" in r.stdout


def test_delivered_verdict_without_disposition_fails(tmp_path):
    root = _repo(tmp_path)
    _packet(root, "REV-0001", status="REVIEWED", verdict="ACCEPT-WITH-CHANGES")
    r = _run(root)
    assert r.returncode == 1, r.stdout
    assert "disposition.md is missing/empty" in r.stdout


def test_delivered_verdict_but_status_still_awaiting_fails(tmp_path):
    root = _repo(tmp_path)
    _packet(root, "REV-0001", status="AWAITING_REVIEW", verdict="ACCEPT",
            disposition="handled")
    r = _run(root)
    assert r.returncode == 1, r.stdout
    assert "still AWAITING_REVIEW" in r.stdout


def test_delivered_verdict_with_disposition_passes(tmp_path):
    root = _repo(tmp_path)
    _packet(root, "REV-0001", status="DISPOSED", verdict="ACCEPT-WITH-CHANGES",
            disposition="applied fixes; gate cleared")
    r = _run(root)
    assert r.returncode == 0, r.stdout
    assert "REVIEW PACKET CHECK PASSED" in r.stdout


def test_bad_status_fails(tmp_path):
    root = _repo(tmp_path)
    _packet(root, "REV-0001", status="BOGUS")
    r = _run(root)
    assert r.returncode == 1, r.stdout
    assert "not in valid_review_statuses" in r.stdout


def test_unreviewed_finding_without_packet_fails(tmp_path):
    root = _repo(tmp_path)
    (root / "work" / "review" / "FINDING-sample-thing.md").write_text(
        "# FINDING\n- **Status:** still queues for **independent review**.\n", encoding="utf-8")
    r = _run(root)
    assert r.returncode == 1, r.stdout
    assert "no review packet covers it" in r.stdout


def test_unreviewed_finding_covered_by_packet_targets_passes(tmp_path):
    root = _repo(tmp_path)
    (root / "work" / "review" / "FINDING-sample-thing.md").write_text(
        "# FINDING\n- **Status:** still queues for **independent review**.\n", encoding="utf-8")
    _packet(root, "REV-0001", targets="FINDING-sample-thing")
    r = _run(root)
    assert r.returncode == 0, r.stdout
    assert "REVIEW PACKET CHECK PASSED" in r.stdout
