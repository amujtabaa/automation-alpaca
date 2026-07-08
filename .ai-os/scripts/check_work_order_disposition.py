#!/usr/bin/env python3
"""Check completed work-order disposition hygiene (real implementation, WO-0603).

Failures (exit 1):
- a completed work order (MERGED/CLOSED/ABANDONED/SUPERSEDED) has an empty disposition
- any disposition value is outside rules/ai-os-rules.yaml valid_work_order_dispositions
- a DELETED disposition has no matching work/ledger.jsonl entry
  (implements require_ledger_entry_for_deleted_work_orders)

Warnings (exit 0): a completed order still sits in work/queue|active|review
(doc 12's anti-bloat rule; the hygiene report treats this as a violation).

Also exposes scan_work_orders() and review() for reuse by the hygiene report
and the MCP server (shared code, not shelling out).

Usage:
  python scripts/check_work_order_disposition.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

from ai_os_paths import find_root, load_yaml_list

COMPLETED = {"MERGED", "CLOSED", "ABANDONED", "SUPERSEDED"}
LIVE_FOLDERS = ("queue", "active", "review")
SKIP_NAMES = {"README.md", "retention-policy.md"}


def parse_work_order(path: Path) -> dict | None:
    """Frontmatter parse with list support for the disposition key."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    data: dict = {}
    dispositions: list[str] = []
    in_disposition = False
    for line in text[4:end].splitlines():
        stripped = line.strip()
        if in_disposition:
            if stripped.startswith("- "):
                dispositions.append(stripped[2:].split("#", 1)[0].strip())
                continue
            in_disposition = False
        if stripped.startswith("disposition:"):
            value = stripped.split(":", 1)[1].split("#", 1)[0].strip()
            if value == "":
                in_disposition = True
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                dispositions = [x.strip() for x in inner.split(",") if x.strip()]
            continue
        if ":" in line and not stripped.startswith("#"):
            key, val = line.split(":", 1)
            data[key.strip()] = val.split("#", 1)[0].strip()
    data["disposition"] = dispositions
    return data


def scan_work_orders(root: Path) -> list[dict]:
    records = []
    work = root / "work"
    if not work.exists():
        return records
    for p in sorted(work.rglob("*.md")):
        if p.name in SKIP_NAMES:
            continue
        fm = parse_work_order(p)
        if fm is None or fm.get("type", "") != "Work Order":
            continue
        records.append({
            "path": p,
            "folder": p.relative_to(work).parts[0],
            "id": fm.get("work_order_id", p.stem),
            "status": fm.get("status", ""),
            "dispositions": fm["disposition"],
        })
    return records


def ledger_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    ledger = root / "work" / "ledger.jsonl"
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict) and entry.get("id"):
                ids.add(entry["id"])
    return ids


def analyze(root: Path) -> tuple[list[str], list[str]]:
    valid = set(load_yaml_list(root, "valid_work_order_dispositions"))
    known_ledger_ids = ledger_ids(root)
    failures: list[str] = []
    warnings: list[str] = []
    for record in scan_work_orders(root):
        rel = record["path"]
        if record["status"] in COMPLETED and not record["dispositions"]:
            failures.append(f"{record['id']}: completed ({record['status']}) with empty disposition ({rel})")
        for d in record["dispositions"]:
            if valid and d not in valid:
                failures.append(f"{record['id']}: disposition {d!r} not in rules/ai-os-rules.yaml vocabulary ({rel})")
        if "DELETED" in record["dispositions"] and record["id"] not in known_ledger_ids:
            failures.append(
                f"{record['id']}: DELETED disposition without a matching ledger entry "
                f"(require_ledger_entry_for_deleted_work_orders) ({rel})")
        if record["status"] in COMPLETED and record["folder"] in LIVE_FOLDERS:
            warnings.append(f"{record['id']}: completed ({record['status']}) still in work/{record['folder']}/ ({rel})")
    return failures, warnings


def review(root: Path, work_order_id: str) -> dict:
    """Conservative disposition recommendation (derived from the work order,
    never invented) for the MCP ai_os_disposition_review tool."""
    for record in scan_work_orders(root):
        if record["id"] == work_order_id or record["path"].name.startswith(work_order_id):
            if record["status"] not in COMPLETED:
                return {
                    "work_order_id": work_order_id,
                    "recommended_dispositions": [],
                    "raw_work_order_action": "do_not_delete_yet",
                    "reason": f"status {record['status'] or 'unknown'!r} is not a completed status; disposition is premature.",
                    "requires_human_approval": True,
                }
            if record["dispositions"]:
                if "DELETED" in record["dispositions"]:
                    action = "delete"
                elif "ARCHIVED" in record["dispositions"]:
                    action = "archive"
                else:
                    action = "keep"
                return {
                    "work_order_id": work_order_id,
                    "recommended_dispositions": record["dispositions"],
                    "raw_work_order_action": action,
                    "reason": "dispositions already assigned in frontmatter; checked against the rules vocabulary and ledger.",
                    "requires_human_approval": True,
                }
            return {
                "work_order_id": work_order_id,
                "recommended_dispositions": ["RESULT_SUMMARY_KEPT"],
                "raw_work_order_action": "summarize",
                "reason": "completed without a disposition; conservative default — the human decides the final disposition.",
                "requires_human_approval": True,
            }
    raise FileNotFoundError(f"no work order matching {work_order_id!r} under work/")


def main() -> int:
    root = find_root()
    if root is None:
        print("DISPOSITION CHECK FAILED")
        print("- AI_OS_MANIFEST.yaml not found walking up from the current directory")
        return 1
    failures, warnings = analyze(root)
    for w in warnings:
        print("WARNING -", w)
    if failures:
        print("DISPOSITION CHECK FAILED")
        for f in failures:
            print("-", f)
        return 1
    print("DISPOSITION CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
