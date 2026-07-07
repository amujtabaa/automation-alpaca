"""Spine v2 Phase 0 harness smoke checks, wired as regression guards.

These pin two repo-hygiene invariants introduced by the Spine v2 doc
backfill/archive work: root ``CLAUDE.md``'s ``@`` imports must all resolve
(``harness/check_claude_imports.py``), and no active file may reference an
archived ``docs/IMPLEMENTATION_PROMPT_*.md`` at its old, pre-archive path
(``harness/check_stale_prompt_links.py``). Both scripts are also runnable
standalone; these tests just make sure a future doc edit that breaks either
one is caught by the normal suite, not only by someone remembering to run the
script by hand — see ``docs/CONTEXT_PROMPT_LOOP_GOAL_HARNESS_PLAN.md``'s
"harness engineering" list ("CLAUDE.md import resolution checks",
"stale-link checks").

Read-only: these tests only read files under the repo root and make no
network/IO-heavy calls, no store/broker/monitoring interaction — they are
pure repo-state assertions, IO-free per Rule 9's spirit (filesystem reads of
the checked-out repo itself, not network).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS_DIR = REPO_ROOT / "harness"

if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))


def test_claude_md_imports_resolve():
    # harness/check_claude_imports.py is a standalone script (module-level
    # code, no function wrapper, no __main__ guard) supplied as-is by the
    # Spine v2 doc package — kept byte-for-byte as provided rather than
    # refactored to be importable. Its logic is reproduced here as a plain
    # assertion instead of importing/subprocessing that script, so a failure
    # reads as a normal pytest assertion, not a SystemExit.
    missing = []
    for line in (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("@"):
            p = REPO_ROOT / line[1:]
            if not p.exists():
                missing.append(line[1:])
    assert not missing, f"CLAUDE.md @ imports do not resolve: {missing}"


def test_no_stale_implementation_prompt_links():
    import check_stale_prompt_links

    stale = check_stale_prompt_links.find_stale_references()
    assert not stale, "stale docs/IMPLEMENTATION_PROMPT_*.md references:\n" + "\n".join(
        stale
    )
