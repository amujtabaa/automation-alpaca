"""Layout-independent path resolution for AI Project OS scripts.

Scripts must work in both supported layouts:
- package layout: files at the package root (this repo/zip as shipped)
- installed layout: files relocated per the manifest install_map (.ai-os/...)

The root is found by walking up until a directory contains AI_OS_MANIFEST.yaml
directly or under .ai-os/ (same pattern as the MCP server scaffold's
find_repo_root). Paths are then resolved source-relative through the manifest
install_map, never from a script's __file__ position.
"""
from __future__ import annotations

import re
from pathlib import Path

MANIFEST_NAME = "AI_OS_MANIFEST.yaml"


def find_root(start: Path | None = None) -> Path | None:
    """Walk up from start (default: cwd, then this file) to the OS root."""
    bases = []
    if start is not None:
        bases.append(Path(start))
    bases.append(Path.cwd())
    bases.append(Path(__file__).resolve().parent)
    for base in bases:
        cur = base.resolve()
        for candidate in [cur, *cur.parents]:
            if (candidate / MANIFEST_NAME).exists() or (candidate / ".ai-os" / MANIFEST_NAME).exists():
                return candidate
    return None


def manifest_path(root: Path) -> Path:
    direct = root / MANIFEST_NAME
    return direct if direct.exists() else root / ".ai-os" / MANIFEST_NAME


def load_install_map(root: Path) -> dict[str, str]:
    """Parse the manifest install_map block: quoted "source": "installed" pairs.

    Directory entries end with "/". Comment lines are ignored.
    """
    entries: dict[str, str] = {}
    mp = manifest_path(root)
    if not mp.exists():
        return entries
    in_block = False
    for line in mp.read_text(encoding="utf-8").splitlines():
        if line.strip() == "install_map:":
            in_block = True
            continue
        if in_block:
            if line and not line[0].isspace():
                break
            m = re.match(r'\s+"([^"]+)":\s*"([^"]+)"', line)
            if m:
                entries[m.group(1)] = m.group(2)
    return entries


def resolve(root: Path, rel: str) -> Path:
    """Resolve a package-source-relative path in either layout.

    Returns the package-layout path if it exists, else the installed path per
    the install_map (exact entry first, then longest matching directory
    prefix). Callers check .exists() on the result.
    """
    direct = root / rel
    if direct.exists():
        return direct
    install_map = load_install_map(root)
    if rel in install_map:
        return root / install_map[rel]
    best_src = ""
    best_dst = ""
    for src, dst in install_map.items():
        if src.endswith("/") and rel.startswith(src) and len(src) > len(best_src):
            best_src, best_dst = src, dst
    if best_src:
        return root / (best_dst + rel[len(best_src):])
    return direct


def resolve_dir(root: Path, rel_dir: str) -> Path:
    """Resolve a source-relative directory (e.g. "mcp") in either layout."""
    direct = root / rel_dir
    if direct.exists():
        return direct
    key = rel_dir.rstrip("/") + "/"
    install_map = load_install_map(root)
    if key in install_map:
        return root / install_map[key].rstrip("/")
    return direct


def _clean_item(raw: str) -> str:
    """Strip quotes and trailing comments from a YAML list item."""
    raw = raw.strip()
    if raw.startswith('"'):
        end = raw.find('"', 1)
        if end != -1:
            return raw[1:end]
    return raw.split("#", 1)[0].strip().strip("\"'")


def load_yaml_list(root: Path, key: str, rel_file: str = "rules/ai-os-rules.yaml") -> list[str]:
    """Parse a top-level YAML list block: `key:` followed by `- item` lines."""
    path = resolve(root, rel_file)
    if not path.exists():
        return []
    items: list[str] = []
    in_block = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.split("#", 1)[0].strip() == f"{key}:":
            in_block = True
            continue
        if in_block:
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(_clean_item(stripped[2:]))
            elif stripped.startswith("#") or not stripped:
                continue
            else:
                break
    return items


def load_scalar(root: Path, key: str, rel_file: str = "rules/ai-os-rules.yaml") -> str | None:
    """Return the value of a `key: value` line anywhere in the file (first match)."""
    path = resolve(root, rel_file)
    if not path.exists():
        return None
    m = re.search(rf"^\s*{re.escape(key)}:\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
    return _clean_item(m.group(1)) if m else None


def load_manifest_scalar(root: Path, key: str) -> str | None:
    """Return a top-level `key: value` from the manifest (either layout)."""
    mp = manifest_path(root)
    if not mp.exists():
        return None
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", mp.read_text(encoding="utf-8"), re.M)
    return _clean_item(m.group(1)) if m else None


def get_pkl_root(root: Path) -> Path:
    """PKL location per the manifest pkl_root variable (default: pkl/)."""
    return root / (load_manifest_scalar(root, "pkl_root") or "pkl")


def load_not_installed(root: Path) -> list[str]:
    """Parse the manifest not_installed list (dev-package-only files)."""
    mp = manifest_path(root)
    if not mp.exists():
        return []
    entries: list[str] = []
    in_block = False
    for line in mp.read_text(encoding="utf-8").splitlines():
        if line.split("#", 1)[0].strip() == "not_installed:":
            in_block = True
            continue
        if in_block:
            stripped = line.strip()
            if stripped.startswith("- "):
                entries.append(_clean_item(stripped[2:]))
            elif stripped.startswith("#") or not stripped:
                continue
            else:
                break
    return entries
