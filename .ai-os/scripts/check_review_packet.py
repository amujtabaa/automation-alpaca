#!/usr/bin/env python3
"""Check cross-model review-packet hygiene (see core/15_CROSS_MODEL_REVIEW.md).

A review packet is a folder work/review/REV-*/ with request.md (outbound),
optionally result.md (the external reviewer's output), and disposition.md (the
author's close-out).

Failures (exit 1):
- a REV-*/ packet has no request.md, or its front-matter is missing a required
  key (type, rev_id, status, targets)
- request status not in rules/ai-os-rules.yaml valid_review_statuses, or a filled
  verdict not in valid_review_verdicts
- a result.md carries a real verdict but request status is still AWAITING_REVIEW,
  or disposition.md is missing/empty
- a BLOCK / ACCEPT-WITH-CHANGES verdict without a non-empty disposition.md
- a work/review/FINDING-*.md still marked "queues for independent review" that is
  not covered by any packet's targets (or referenced in a request.md)

Warnings (exit 0): a packet left AWAITING_REVIEW longer than review_staleness_days
(informational; the checker can't read mtimes deterministically, so this warns on
packets whose request `created` date is older than the threshold when a date is
present).

Also exposes scan_packets() and review() for reuse by the hygiene report / MCP
server (shared code, not shelling out).

Usage:
  python scripts/check_review_packet.py
"""
from __future__ import annotations
import datetime as _dt
import re
import sys
from pathlib import Path

from ai_os_paths import find_root, load_scalar, load_yaml_list

REQUIRED_REQUEST_KEYS = ("type", "rev_id", "status", "targets")
_PLACEHOLDER = re.compile(r"[<>]")  # unfilled template markers like <ACCEPT | ...>


def _is_placeholder(value: str) -> bool:
    return value == "" or value.lower() == "null" or bool(_PLACEHOLDER.search(value))


def parse_frontmatter(path: Path) -> dict | None:
    """Minimal YAML-frontmatter parse: scalars plus inline/block lists.

    No yaml dependency (matches the other .ai-os checkers). `targets` and
    `human_gated_surfaces` come back as lists; other keys as strings.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    data: dict = {}
    current_list_key: str | None = None
    for line in text[4:end].splitlines():
        stripped = line.strip()
        if current_list_key is not None:
            if stripped.startswith("- "):
                data[current_list_key].append(stripped[2:].split("#", 1)[0].strip().strip("\"'"))
                continue
            current_list_key = None
        if not stripped or stripped.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.split("#", 1)[0].strip()
        if val == "":
            data[key] = []
            current_list_key = key
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            data[key] = [x.strip().strip("\"'") for x in inner.split(",") if x.strip()]
        else:
            data[key] = val.strip("\"'")
    return data


def scan_packets(root: Path) -> list[dict]:
    """One record per work/review/REV-*/ folder."""
    records: list[dict] = []
    review_dir = root / "work" / "review"
    if not review_dir.exists():
        return records
    for folder in sorted(p for p in review_dir.iterdir() if p.is_dir() and p.name.startswith("REV-")):
        request = folder / "request.md"
        result = folder / "result.md"
        disposition = folder / "disposition.md"
        req_fm = parse_frontmatter(request) if request.exists() else None
        res_fm = parse_frontmatter(result) if result.exists() else None
        res_verdict = (res_fm or {}).get("verdict", "")
        records.append({
            "folder": folder,
            "name": folder.name,
            "request_exists": request.exists(),
            "request_fm": req_fm,
            "result_verdict": "" if _is_placeholder(res_verdict) else res_verdict,
            "disposition_text": disposition.read_text(encoding="utf-8").strip() if disposition.exists() else "",
            "disposition_exists": disposition.exists(),
        })
    return records


def _finding_covered(stem: str, packets: list[dict], root: Path) -> bool:
    for rec in packets:
        targets = (rec["request_fm"] or {}).get("targets", []) or []
        if any(stem in t or t in stem for t in targets):
            return True
        request = rec["folder"] / "request.md"
        if request.exists() and stem in request.read_text(encoding="utf-8"):
            return True
    return False


def _unreviewed_findings(root: Path) -> list[str]:
    review_dir = root / "work" / "review"
    flagged: list[str] = []
    if not review_dir.exists():
        return flagged
    for f in sorted(review_dir.glob("FINDING-*.md")):
        norm = re.sub(r"[*`_]", "", f.read_text(encoding="utf-8")).lower()
        if "queues for independent review" in norm:
            flagged.append(f.stem)
    return flagged


def _parse_date(value: str) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def analyze(root: Path, today: _dt.date | None = None) -> tuple[list[str], list[str]]:
    valid_status = set(load_yaml_list(root, "valid_review_statuses"))
    valid_verdicts = set(load_yaml_list(root, "valid_review_verdicts"))
    stale_days = int(load_scalar(root, "review_staleness_days") or 0)
    failures: list[str] = []
    warnings: list[str] = []
    packets = scan_packets(root)

    for rec in packets:
        name = rec["name"]
        if not rec["request_exists"] or rec["request_fm"] is None:
            failures.append(f"{name}: missing or unparseable request.md front-matter")
            continue
        fm = rec["request_fm"]
        for key in REQUIRED_REQUEST_KEYS:
            if key not in fm:
                failures.append(f"{name}: request.md front-matter missing required key {key!r}")
        status = fm.get("status", "")
        if valid_status and status and status not in valid_status:
            failures.append(f"{name}: request status {status!r} not in valid_review_statuses")
        verdict = fm.get("verdict", "")
        if valid_verdicts and not _is_placeholder(verdict) and verdict not in valid_verdicts:
            failures.append(f"{name}: request verdict {verdict!r} not in valid_review_verdicts")

        if rec["result_verdict"]:
            if valid_verdicts and rec["result_verdict"] not in valid_verdicts:
                failures.append(f"{name}: result verdict {rec['result_verdict']!r} not in valid_review_verdicts")
            if status == "AWAITING_REVIEW":
                failures.append(f"{name}: result.md delivered a verdict but request status is still AWAITING_REVIEW")
            if not rec["disposition_text"]:
                failures.append(f"{name}: result.md delivered ({rec['result_verdict']}) but disposition.md is missing/empty")
        # staleness (only when a created date is present)
        created = _parse_date((fm.get("created") or "")) if stale_days else None
        if created is not None and status == "AWAITING_REVIEW":
            age = ((today or _dt.date.today()) - created).days
            if age > stale_days:
                warnings.append(f"{name}: AWAITING_REVIEW for {age} days (> review_staleness_days={stale_days})")

    for stem in _unreviewed_findings(root):
        if not _finding_covered(stem, packets, root):
            failures.append(
                f"{stem}: still 'queues for independent review' but no review packet covers it "
                f"(add it to a REV-*/ request targets)")

    return failures, warnings


def review(root: Path, rev_id: str) -> dict:
    """Status summary for one packet (for the hygiene report / MCP)."""
    for rec in scan_packets(root):
        fm = rec["request_fm"] or {}
        if rec["name"].startswith(rev_id) or fm.get("rev_id") == rev_id:
            return {
                "rev_id": fm.get("rev_id", rec["name"]),
                "status": fm.get("status", ""),
                "targets": fm.get("targets", []),
                "result_verdict": rec["result_verdict"] or None,
                "disposed": rec["disposition_exists"] and bool(rec["disposition_text"]),
            }
    raise FileNotFoundError(f"no review packet matching {rev_id!r} under work/review/")


def main() -> int:
    root = find_root()
    if root is None:
        print("REVIEW PACKET CHECK FAILED")
        print("- AI_OS_MANIFEST.yaml not found walking up from the current directory")
        return 1
    failures, warnings = analyze(root)
    for w in warnings:
        print("WARNING -", w)
    if failures:
        print("REVIEW PACKET CHECK FAILED")
        for f in failures:
            print("-", f)
        return 1
    print("REVIEW PACKET CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
