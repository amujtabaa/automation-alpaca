#!/usr/bin/env python3
"""AI Project OS context/artifact hygiene report (real implementation, WO-0603).

Report-only: never deletes or moves files. Findings use 13's category
vocabulary (keep/shorten/distill/convert-to-ADR/summarize-result/archive/delete)
and are split into:

- violations (exit 1) — doc 12's hard anti-bloat rules:
  completed work orders still in live folders; non-empty
  work/completed/delete-candidates/
- advisories (exit 0) — tunable-default findings:
  budget overruns (context_budgets in rules/ai-os-rules.yaml, never hard-coded);
  duplicate titles across PKL pages

The PKL location comes from the manifest pkl_root variable. Exposes collect()
for reuse by the MCP server's ai_os_hygiene_report tool.

Usage:
  python scripts/context_hygiene_report.py
"""
from __future__ import annotations
import sys
from pathlib import Path

from ai_os_paths import find_root, get_pkl_root, load_scalar
from check_work_order_disposition import COMPLETED, LIVE_FOLDERS, scan_work_orders


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8").splitlines())
    except (UnicodeDecodeError, OSError):
        return 0


def _title(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    for line in text[4:end].splitlines():
        if line.strip().startswith("title:"):
            return line.split(":", 1)[1].strip()
    return None


def collect(root: Path) -> list[dict]:
    """Return findings as dicts: severity, category, path, message."""
    findings: list[dict] = []

    def budget(key: str, default: int) -> int:
        value = load_scalar(root, key)
        return int(value) if value else default

    root_budget = budget("root_instruction_max_lines", 150)
    pkl_budget = budget("pkl_page_max_lines", 220)
    wo_budget = budget("work_order_max_lines", 220)

    def advisory(category: str, path: Path, message: str) -> dict:
        return {"severity": "advisory", "category": category, "path": path.as_posix(), "message": message}

    def violation(category: str, path: Path, message: str) -> dict:
        return {"severity": "violation", "category": category, "path": path.as_posix(), "message": message}

    for name in ("AGENTS.md", "CLAUDE.md"):
        shim = root / name
        if shim.exists() and _line_count(shim) > root_budget:
            findings.append(advisory("shorten", shim,
                                     f"root shim exceeds root_instruction_max_lines ({root_budget})"))

    pkl = get_pkl_root(root)
    titles: dict[str, list[Path]] = {}
    if pkl.exists():
        for page in sorted(pkl.rglob("*.md")):
            if page.name in ("index.md", "log.md"):
                continue
            count = _line_count(page)
            if count > pkl_budget:
                findings.append(advisory("shorten", page,
                                         f"{count} lines exceeds pkl_page_max_lines ({pkl_budget})"))
            title = _title(page)
            if title:
                titles.setdefault(title, []).append(page)
    for title, pages in titles.items():
        if len(pages) > 1:
            findings.append(advisory("distill", pages[1],
                                     f"duplicate PKL title {title!r} (also in {pages[0].as_posix()})"))

    delete_candidates = root / "work" / "completed" / "delete-candidates"
    if delete_candidates.exists():
        stale = [p for p in delete_candidates.rglob("*") if p.is_file()]
        if stale:
            findings.append(violation("delete", delete_candidates,
                                      f"work/completed/delete-candidates/ is not empty ({len(stale)} file(s)); "
                                      "it must be emptied during maintenance (doc 12)"))

    for record in scan_work_orders(root):
        if record["status"] in COMPLETED and record["folder"] in LIVE_FOLDERS:
            findings.append(violation("archive", record["path"],
                                      f"{record['id']}: completed ({record['status']}) still in "
                                      f"work/{record['folder']}/ (doc 12 anti-bloat rule)"))
        if record["folder"] in LIVE_FOLDERS and _line_count(record["path"]) > wo_budget:
            findings.append(advisory("shorten", record["path"],
                                     f"{record['id']}: exceeds work_order_max_lines ({wo_budget})"))

    return findings


def main() -> int:
    root = find_root()
    if root is None:
        print("HYGIENE REPORT FAILED")
        print("- AI_OS_MANIFEST.yaml not found walking up from the current directory")
        return 1
    findings = collect(root)
    violations = [f for f in findings if f["severity"] == "violation"]
    for f in findings:
        print(f"FINDING [{f['severity']}] {f['category']}: {f['message']} ({f['path']})")
    print(f"HYGIENE REPORT: {len(violations)} violation(s), {len(findings) - len(violations)} advisory finding(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
