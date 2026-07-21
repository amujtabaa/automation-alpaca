"""Read-only AUDIT-0002 probe for claimed pytest pins and WO front matter.

The script prints JSON only. It writes no repository or application state.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TEST_REF_RE = re.compile(
    r"tests/[A-Za-z0-9_./-]+\.py(?:"
    r"(?:::[A-Za-z0-9_.*\[\],=-]+)+"
    r")?"
)
INV_RE = re.compile(r"^\*\*(INV-(\d{3}))\b", re.MULTILINE)
WO_ID_RE = re.compile(r"^work_order_id:\s*(WO-(\d{4})[A-Za-z]?)\s*$", re.MULTILINE)


def collect_nodes() -> tuple[list[str], str]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"pytest collection failed ({completed.returncode})\n{completed.stderr}"
        )
    nodes = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().startswith("tests/") and "::" in line
    ]
    summary = next(
        (
            line.strip()
            for line in reversed(completed.stdout.splitlines())
            if " collected in " in line
        ),
        f"{len(nodes)} collected nodes",
    )
    return nodes, summary


def refs(text: str) -> list[str]:
    return sorted(set(TEST_REF_RE.findall(text)))


def ref_matches(ref: str, nodes: list[str]) -> bool:
    normalized = ref.replace("\\", "/")
    if "::" not in normalized:
        return any(node.startswith(f"{normalized}::") for node in nodes)
    if "*" in normalized:
        return any(fnmatch.fnmatchcase(node, normalized) for node in nodes)
    return any(
        node == normalized
        or node.startswith(f"{normalized}[")
        or node.startswith(f"{normalized}::")
        for node in nodes
    )


def inspect_refs(text: str, nodes: list[str]) -> dict[str, object]:
    cited = refs(text)
    return {
        "refs": cited,
        "missing_files": sorted(
            {
                ref.split("::", 1)[0]
                for ref in cited
                if not (ROOT / ref.split("::", 1)[0]).is_file()
            }
        ),
        "uncollected_refs": [ref for ref in cited if not ref_matches(ref, nodes)],
    }


def invariant_blocks(text: str) -> list[tuple[str, int, str]]:
    matches = list(INV_RE.finditer(text))
    blocks: list[tuple[str, int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks.append((match.group(1), int(match.group(2)), text[match.start() : end]))
    return blocks


def frontmatter_value(text: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def main() -> int:
    nodes, collection_summary = collect_nodes()

    invariants_text = (ROOT / "docs" / "INVARIANTS.md").read_text(encoding="utf-8")
    invariants: list[dict[str, object]] = []
    for inv_id, number, block in invariant_blocks(invariants_text):
        if number > 89:
            continue
        pin_start = block.find("*Pinned by:*")
        pin_text = block[pin_start:] if pin_start >= 0 else ""
        entry = {"id": inv_id, **inspect_refs(pin_text, nodes)}
        entry["has_pinned_by"] = pin_start >= 0
        entry["pin_excerpt"] = " ".join(pin_text.split())[:300]
        invariants.append(entry)

    adrs: list[dict[str, object]] = []
    for path in sorted((ROOT / "docs" / "adr").glob("ADR-00[1-9]-*.md")):
        text = path.read_text(encoding="utf-8")
        adrs.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                **inspect_refs(text, nodes),
            }
        )

    work_orders: list[dict[str, object]] = []
    for path in sorted((ROOT / "work" / "completed").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = WO_ID_RE.search(text)
        if not match or int(match.group(2)) > 35:
            continue
        evidence_text = text
        if path.parent != ROOT / "work" / "completed":
            evidence_text = "\n".join(
                sibling.read_text(encoding="utf-8")
                for sibling in sorted(path.parent.glob("*.md"))
            )
        work_orders.append(
            {
                "id": match.group(1),
                "path": path.relative_to(ROOT).as_posix(),
                "status": frontmatter_value(text, "status"),
                "disposition": frontmatter_value(text, "disposition"),
                **inspect_refs(evidence_text, nodes),
            }
        )

    output = {
        "collection": collection_summary,
        "collected_node_count": len(nodes),
        "invariants": invariants,
        "adrs": adrs,
        "work_orders": work_orders,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
