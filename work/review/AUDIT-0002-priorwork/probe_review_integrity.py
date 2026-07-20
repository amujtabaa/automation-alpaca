"""Mechanical inventory of REV packets and standalone FINDING status lines."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REVIEW = ROOT / "work" / "review"
VERDICT_RE = re.compile(r"\b(ACCEPT-WITH-CHANGES|ACCEPT|BLOCK)\b")


def first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    return match.group(1).strip() if match else None


def result_verdict(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    frontmatter = first_match(text, r"^verdict:\s*(.+)$")
    if frontmatter:
        match = VERDICT_RE.search(frontmatter.upper())
        return match.group(1) if match else frontmatter
    section = re.search(
        r"^## Verdict\s*$([\s\S]{0,300})", text, re.MULTILINE | re.IGNORECASE
    )
    if section:
        match = VERDICT_RE.search(section.group(1).upper())
        return match.group(1) if match else None
    return None


def packet_inventory(path: Path) -> dict[str, object]:
    files = sorted(item.name for item in path.iterdir() if item.is_file())
    result_paths = sorted(
        item
        for item in path.glob("result*.md")
        if "SUPERSEDED" not in item.name.upper()
    )
    disposition_path = path / "disposition.md"
    disposition_text = (
        disposition_path.read_text(encoding="utf-8")
        if disposition_path.is_file()
        else ""
    )
    return {
        "id": path.name,
        "files": files,
        "has_request": (path / "request.md").is_file(),
        "has_result": bool(result_paths),
        "has_disposition": disposition_path.is_file(),
        "has_supersession": any("SUPERSEDED" in name.upper() for name in files),
        "result_verdicts": {
            item.name: result_verdict(item) for item in result_paths
        },
        "disposition_verdict_received": first_match(
            disposition_text, r"^verdict_received:\s*(.+)$"
        ),
        "disposition_status": first_match(
            disposition_text, r"^disposition_status:\s*(.+)$"
        ),
        "disposition_in_progress": "IN PROGRESS" in disposition_text.upper(),
    }


def finding_inventory(path: Path) -> dict[str, str | None]:
    text = path.read_text(encoding="utf-8")
    status = first_match(text, r"^-\s*\*\*Status:\*\*\s*(.+)$")
    return {"file": path.name, "status": status}


def main() -> int:
    output = {
        "packets": [
            packet_inventory(path)
            for path in sorted(REVIEW.glob("REV-*"))
            if path.is_dir()
        ],
        "findings": [
            finding_inventory(path)
            for path in sorted(REVIEW.glob("FINDING-*.md"))
        ],
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
