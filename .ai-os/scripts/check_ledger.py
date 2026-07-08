#!/usr/bin/env python3
"""Validate work/ledger.jsonl (WO-0603 item 1).

Every non-blank line must be a JSON object with the fields from doc 12's
ledger contract (id, title, status, disposition[], commit, date, reason);
statuses and dispositions are bound to the vocabularies in
rules/ai-os-rules.yaml. The formal contract is mcp/schemas/ledger_entry.schema.json.
An empty ledger passes.

Usage:
  python scripts/check_ledger.py
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

from ai_os_paths import find_root, load_yaml_list

REQUIRED = ("id", "title", "status", "disposition", "commit", "date", "reason")


def validate_ledger(root: Path) -> list[str]:
    ledger = root / "work" / "ledger.jsonl"
    if not ledger.exists():
        return ["work/ledger.jsonl not found"]
    statuses = set(load_yaml_list(root, "valid_work_order_statuses"))
    dispositions = set(load_yaml_list(root, "valid_work_order_dispositions"))
    problems: list[str] = []
    for i, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {i}: invalid JSON ({exc})")
            continue
        if not isinstance(entry, dict):
            problems.append(f"line {i}: entry is not a JSON object")
            continue
        for key in REQUIRED:
            if key not in entry:
                problems.append(f"line {i}: missing required field {key!r}")
        status = entry.get("status")
        if status and statuses and status not in statuses:
            problems.append(f"line {i}: status {status!r} not in rules/ai-os-rules.yaml vocabulary")
        disposition = entry.get("disposition")
        if disposition is not None:
            if not isinstance(disposition, list):
                problems.append(f"line {i}: disposition must be a list")
            else:
                for d in disposition:
                    if dispositions and d not in dispositions:
                        problems.append(f"line {i}: disposition {d!r} not in rules/ai-os-rules.yaml vocabulary")
        date = entry.get("date")
        if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
            problems.append(f"line {i}: date {date!r} must be YYYY-MM-DD")
    return problems


def main() -> int:
    root = find_root()
    if root is None:
        print("LEDGER CHECK FAILED")
        print("- AI_OS_MANIFEST.yaml not found walking up from the current directory")
        return 1
    problems = validate_ledger(root)
    if problems:
        print("LEDGER CHECK FAILED")
        for p in problems:
            print("-", p)
        return 1
    print("LEDGER CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
