#!/usr/bin/env python3
"""Check that top-level AI Project OS version markers are consistent.

Works in the package layout and in an installed layout: the OS root is found
by walking up to AI_OS_MANIFEST.yaml and paths are resolved through the
manifest install_map (see ai_os_paths.py). Exposes collect_failures() for
reuse by the MCP server's doctor tool.
"""
from __future__ import annotations
import re
from pathlib import Path

from ai_os_paths import find_root, resolve

EXPECTED = "0.9.1"
CHECKS = {
    "VERSION.md": [rf"Package version:\s*\*\*v{EXPECTED}\*\*"],
    "AI_OS_MANIFEST.yaml": [rf'os_version:\s*"{EXPECTED}"', rf'package_version:\s*"{EXPECTED}"'],
    "rules/ai-os-rules.yaml": [rf"version:\s*{EXPECTED}", rf"os_version:\s*{EXPECTED}"],
    "rules/prompt-rules.yaml": [rf"version:\s*{EXPECTED}", rf"os_version:\s*{EXPECTED}"],
    "00_START_HERE.md": [rf"AI Project Operating System — v{EXPECTED}"],
    "14_MCP_CONTROL_PLANE.md": [r"MCP is the OS access layer, not the OS source of truth"],
    "mcp/server/pyproject.toml": [rf'target_ai_os_version = "{EXPECTED}"'],
}


def collect_failures(root: Path) -> list[str]:
    failures = []
    for rel, patterns in CHECKS.items():
        p = resolve(root, rel)
        if not p.exists():
            if rel.startswith("mcp/"):
                continue  # MCP tree is optional in installed layouts
            failures.append(f"{rel}: missing")
            continue
        text = p.read_text(encoding="utf-8")
        for pat in patterns:
            if not re.search(pat, text, flags=re.M):
                failures.append(f"{rel}: missing pattern {pat}")
    return failures


def main() -> int:
    root = find_root()
    if root is None:
        print("VERSION CHECK FAILED")
        print("- AI_OS_MANIFEST.yaml not found walking up from the current directory")
        return 1
    failures = collect_failures(root)
    if failures:
        print("VERSION CHECK FAILED")
        for f in failures:
            print("-", f)
        return 1
    print(f"VERSION CHECK PASSED: v{EXPECTED}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
