#!/usr/bin/env python3
"""Validate a repository against the manifest install_map.

Checks (WO-0602 item 4):
- every install_map file entry resolves to an existing file (either layout)
- every mapped directory tree exists (mcp/ is conditional and may be absent)
- no `not_installed` content leaked into an installed repository
- no duplicate or unbalanced AI-PROJECT-OS marker blocks in root shims

Exposes validate_install() as the deterministic backend for the MCP server's
ai_os_doctor tool (the doctor imports this logic, it does not reimplement it).

Usage:
  python scripts/check_install.py [target-repo-dir]
"""
from __future__ import annotations
import sys
from pathlib import Path

from ai_os_paths import (MANIFEST_NAME, find_root, load_install_map,
                         load_not_installed, manifest_path, resolve, resolve_dir)

MARKER_BEGIN = "<!-- AI-PROJECT-OS:BEGIN -->"
MARKER_END = "<!-- AI-PROJECT-OS:END -->"


def validate_install(root: Path) -> list[str]:
    problems: list[str] = []
    if not manifest_path(root).exists():
        return [f"{MANIFEST_NAME} not found under {root}"]
    install_map = load_install_map(root)
    if not install_map:
        return ["manifest has no install_map"]
    package_layout = (root / MANIFEST_NAME).exists()
    for src, dst in install_map.items():
        if src.endswith("/"):
            if not resolve_dir(root, src.rstrip("/")).exists():
                if src == "mcp/":
                    continue  # conditional: installed only when MCP is requested
                problems.append(f"mapped directory missing: {src} -> {dst}")
        else:
            if not resolve(root, src).exists():
                problems.append(f"mapped file missing: {src} -> {dst}")
    if not package_layout:
        for entry in load_not_installed(root):
            name = entry.rstrip("/")
            candidates = (root / name, root / ".ai-os" / name, root / ".ai-os" / "core" / Path(name).name)
            for cand in candidates:
                if cand.exists():
                    problems.append(f"not_installed content leaked: {cand}")
    for shim in ("CLAUDE.md", "AGENTS.md"):
        p = root / shim
        if p.exists():
            text = p.read_text(encoding="utf-8")
            begins, ends = text.count(MARKER_BEGIN), text.count(MARKER_END)
            if begins > 1 or ends > 1:
                problems.append(f"duplicate marker blocks in {shim} (begin={begins}, end={ends})")
            elif begins != ends:
                problems.append(f"unbalanced marker block in {shim} (begin={begins}, end={ends})")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = find_root(Path(args[0])) if args else find_root()
    if root is None:
        print("INSTALL CHECK FAILED")
        print(f"- no {MANIFEST_NAME} found walking up from the target directory")
        return 1
    problems = validate_install(root)
    if problems:
        print("INSTALL CHECK FAILED")
        for p in problems:
            print("-", p)
        return 1
    print("INSTALL CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
