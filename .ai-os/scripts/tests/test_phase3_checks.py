"""WO-0603 tests: ledger validation, real disposition check, real hygiene
report, and the pkl_root manifest variable.
"""
from __future__ import annotations

import json
from pathlib import Path

from conftest import SCRIPTS, run_script

RULES_YAML = """\
version: 0.9.1
os_version: 0.9.1
valid_work_order_statuses:
  - DRAFT
  - READY
  - ACTIVE
  - REVIEW
  - MERGED
  - CLOSED
  - ABANDONED
  - SUPERSEDED
  - DISTILLED
  - DISPOSED
valid_work_order_dispositions:
  - PKL_UPDATED
  - ADR_CREATED
  - RESULT_SUMMARY_KEPT
  - ARCHIVED
  - DELETED
  - SUPERSEDED
  - ABANDONED
pkl_staleness_days: 90
context_budgets:
  root_instruction_max_lines: 150
  nested_instruction_max_lines: 100
  work_order_max_lines: 220
  pkl_page_max_lines: 5
"""


def _repo(tmp_path: Path, pkl_root: str = "pkl") -> Path:
    root = tmp_path / "repo"
    (root / "rules").mkdir(parents=True)
    (root / "AI_OS_MANIFEST.yaml").write_text(
        f'os_version: "0.9.1"\npkl_root: "{pkl_root}"\n', encoding="utf-8")
    (root / "rules" / "ai-os-rules.yaml").write_text(RULES_YAML, encoding="utf-8")
    for sub in ("queue", "active", "review", "completed/keep", "completed/delete-candidates", "archive"):
        (root / "work" / sub).mkdir(parents=True)
    (root / "work" / "ledger.jsonl").write_text("", encoding="utf-8")
    (root / pkl_root).mkdir()
    return root


def _wo(root: Path, folder: str, wo_id: str, status: str, dispositions: list[str]) -> Path:
    disp = "disposition: []" if not dispositions else "disposition:\n" + "\n".join(f"  - {d}" for d in dispositions)
    text = f"""---
type: Work Order
title: {wo_id} fixture
status: {status}
work_order_id: {wo_id}
{disp}
owner: tester
---

# Work Order: {wo_id}
"""
    p = root / "work" / folder / f"{wo_id}-fixture.md"
    p.write_text(text, encoding="utf-8")
    return p


LEDGER_OK = {"id": "WO-0300", "title": "t", "status": "MERGED",
             "disposition": ["DELETED"], "commit": "abc123", "date": "2026-07-07", "reason": "routine"}


# ===== check_ledger =====

def test_ledger_empty_file_passes(tmp_path):
    root = _repo(tmp_path)
    result = run_script(SCRIPTS / "check_ledger.py", cwd=root)
    assert result.returncode == 0, result.stdout
    assert "LEDGER CHECK PASSED" in result.stdout


def test_ledger_valid_line_passes(tmp_path):
    root = _repo(tmp_path)
    (root / "work" / "ledger.jsonl").write_text(json.dumps(LEDGER_OK) + "\n", encoding="utf-8")
    result = run_script(SCRIPTS / "check_ledger.py", cwd=root)
    assert result.returncode == 0, result.stdout


def test_ledger_malformed_json_fails(tmp_path):
    root = _repo(tmp_path)
    (root / "work" / "ledger.jsonl").write_text("{not json}\n", encoding="utf-8")
    result = run_script(SCRIPTS / "check_ledger.py", cwd=root)
    assert result.returncode == 1
    assert "LEDGER CHECK FAILED" in result.stdout


def test_ledger_bad_disposition_enum_fails(tmp_path):
    root = _repo(tmp_path)
    bad = dict(LEDGER_OK, disposition=["NUKED"])
    (root / "work" / "ledger.jsonl").write_text(json.dumps(bad) + "\n", encoding="utf-8")
    result = run_script(SCRIPTS / "check_ledger.py", cwd=root)
    assert result.returncode == 1
    assert "NUKED" in result.stdout


def test_ledger_missing_required_field_fails(tmp_path):
    root = _repo(tmp_path)
    bad = {k: v for k, v in LEDGER_OK.items() if k != "reason"}
    (root / "work" / "ledger.jsonl").write_text(json.dumps(bad) + "\n", encoding="utf-8")
    result = run_script(SCRIPTS / "check_ledger.py", cwd=root)
    assert result.returncode == 1
    assert "reason" in result.stdout


# ===== check_work_order_disposition (real) =====

DISPO = SCRIPTS / "check_work_order_disposition.py"


def test_completed_without_disposition_fails(tmp_path):
    root = _repo(tmp_path)
    _wo(root, "completed/keep", "WO-0301", "MERGED", [])
    result = run_script(DISPO, cwd=root)
    assert result.returncode == 1, result.stdout
    assert "WO-0301" in result.stdout


def test_invalid_disposition_vocabulary_fails(tmp_path):
    root = _repo(tmp_path)
    _wo(root, "completed/keep", "WO-0302", "MERGED", ["NUKED"])
    result = run_script(DISPO, cwd=root)
    assert result.returncode == 1
    assert "NUKED" in result.stdout


def test_deleted_without_ledger_entry_fails(tmp_path):
    root = _repo(tmp_path)
    _wo(root, "completed/keep", "WO-0303", "MERGED", ["DELETED"])
    result = run_script(DISPO, cwd=root)
    assert result.returncode == 1
    assert "ledger" in result.stdout.lower()


def test_deleted_with_ledger_entry_passes(tmp_path):
    root = _repo(tmp_path)
    _wo(root, "completed/keep", "WO-0304", "MERGED", ["DELETED"])
    entry = dict(LEDGER_OK, id="WO-0304")
    (root / "work" / "ledger.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
    result = run_script(DISPO, cwd=root)
    assert result.returncode == 0, result.stdout


def test_completed_order_in_active_warns(tmp_path):
    root = _repo(tmp_path)
    _wo(root, "active", "WO-0305", "MERGED", ["ARCHIVED"])
    result = run_script(DISPO, cwd=root)
    assert result.returncode == 0, result.stdout
    assert "WARNING" in result.stdout
    assert "WO-0305" in result.stdout


def test_clean_order_passes(tmp_path):
    root = _repo(tmp_path)
    _wo(root, "active", "WO-0306", "ACTIVE", [])
    result = run_script(DISPO, cwd=root)
    assert result.returncode == 0, result.stdout
    assert "WARNING" not in result.stdout


# ===== context_hygiene_report (real) =====

HYGIENE = SCRIPTS / "context_hygiene_report.py"


def test_hygiene_flags_over_budget_page_from_rules_budget(tmp_path):
    root = _repo(tmp_path)  # pkl_page_max_lines: 5 in the test rules file
    (root / "pkl" / "big.md").write_text("\n".join(f"line {i}" for i in range(40)), encoding="utf-8")
    result = run_script(HYGIENE, cwd=root)
    assert result.returncode == 0, result.stdout  # advisory only
    assert "big.md" in result.stdout
    assert "shorten" in result.stdout


def test_hygiene_flags_nonempty_delete_candidates_as_violation(tmp_path):
    root = _repo(tmp_path)
    (root / "work" / "completed" / "delete-candidates" / "old.md").write_text("x", encoding="utf-8")
    result = run_script(HYGIENE, cwd=root)
    assert result.returncode == 1, result.stdout
    assert "delete-candidates" in result.stdout
    assert "violation" in result.stdout.lower()


def test_hygiene_advisory_only_exits_zero(tmp_path):
    root = _repo(tmp_path)
    result = run_script(HYGIENE, cwd=root)
    assert result.returncode == 0, result.stdout


def test_hygiene_completed_in_live_folder_is_violation(tmp_path):
    root = _repo(tmp_path)
    _wo(root, "review", "WO-0307", "CLOSED", ["ARCHIVED"])
    result = run_script(HYGIENE, cwd=root)
    assert result.returncode == 1
    assert "WO-0307" in result.stdout


# ===== pkl_root manifest variable =====

def test_alternate_pkl_root_honored_by_hygiene(tmp_path):
    root = _repo(tmp_path, pkl_root="knowledge")
    (root / "knowledge" / "big.md").write_text("\n".join(f"line {i}" for i in range(40)), encoding="utf-8")
    result = run_script(HYGIENE, cwd=root)
    assert result.returncode == 0, result.stdout
    assert "big.md" in result.stdout


def test_alternate_pkl_root_honored_by_check_pkl(tmp_path):
    root = _repo(tmp_path, pkl_root="knowledge")
    (root / "knowledge" / "nofm.md").write_text("no frontmatter", encoding="utf-8")
    result = run_script(SCRIPTS / "check_pkl.py", cwd=root)
    assert result.returncode == 1, result.stdout
    assert "nofm.md" in result.stdout
