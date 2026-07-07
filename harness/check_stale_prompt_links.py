"""Smoke check (Spine v2 Phase 0, docs/STALE_ARTIFACT_CLEANUP_GUIDE.md's "Stale
link update rule"): confirm no active file still references
``docs/IMPLEMENTATION_PROMPT_*.md`` at its pre-archive path — those files
were moved to ``docs/archive/legacy_implementation_prompts/`` (see
``docs/00_START_HERE.md`` and the archive's own README). A reference at the
old path is a dead link, not just stale prose.

Two files are allowed to mention the bare pattern, because they document the
archival *policy* itself rather than linking to a specific moved file:

* ``CLAUDE.md`` ("Older `IMPLEMENTATION_PROMPT_*` files are historical
  artifacts...")
* ``docs/STALE_ARTIFACT_CLEANUP_GUIDE.md`` (the glob patterns in its own
  "Archive, do not delete" / "Stale link update rule" sections)

Run directly: ``python harness/check_stale_prompt_links.py``. Read-only; not
part of the pytest suite by default (a thin pytest wrapper in
``tests/test_harness_smoke.py`` runs the same check as a regression guard).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# A stale reference: "docs/IMPLEMENTATION_PROMPT_" NOT immediately followed by
# the archive subpath. (The archive's own contents legitimately reference
# themselves at the correct, already-archived path.)
_STALE_PATTERN = re.compile(r"docs/IMPLEMENTATION_PROMPT_[A-Za-z0-9_.]*\.md")
_ARCHIVE_PREFIX = "docs/archive/legacy_implementation_prompts/"

_ALLOWED_GENERIC_MENTION_FILES = {
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "docs" / "STALE_ARTIFACT_CLEANUP_GUIDE.md",
}

_SCAN_GLOBS = ("**/*.md", "**/*.py")
_SKIP_DIR_PARTS = {".venv", ".git", "__pycache__", "node_modules"}


def _iter_candidate_files():
    for pattern in _SCAN_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if any(part in _SKIP_DIR_PARTS for part in path.parts):
                continue
            if _ARCHIVE_PREFIX.rstrip("/") in path.parts:
                continue  # the archive itself is allowed to reference its own files
            yield path


def find_stale_references() -> list[str]:
    findings: list[str] = []
    for path in _iter_candidate_files():
        if path in _ALLOWED_GENERIC_MENTION_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in _STALE_PATTERN.finditer(line):
                if match.group(0).startswith(_ARCHIVE_PREFIX):
                    continue
                findings.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}"
                )
    return findings


if __name__ == "__main__":
    stale = find_stale_references()
    if stale:
        print("STALE docs/IMPLEMENTATION_PROMPT_*.md references found:")
        print("\n".join(stale))
        raise SystemExit(1)
    print("No stale docs/IMPLEMENTATION_PROMPT_*.md references found.")
