"""Regression test for the AI-OS work-order scope checker's inline-comment parsing (WO-0010).

`.ai-os/scripts/check_work_order_scope.py::extract_list` must strip an inline `#` comment
from each YAML list entry, so an `allowed_paths` entry written as `- "**"  # read-only`
parses to the glob `**` (which matches every path) rather than a garbage pattern that then
reports every real changed file as "outside allowed paths". The sibling
`check_work_order_disposition.py` already strips comments this way; this locks the same
behaviour into the scope checker so a commented `allowed_paths` never yields a false
SCOPE CHECK FAILED.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1] / ".ai-os" / "scripts"


def _load_checker():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "check_work_order_scope", _SCRIPTS / "check_work_order_scope.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


checker = _load_checker()

# A work-order frontmatter fragment written exactly the way this repo's real work orders
# write it — a commented `- "**"` catch-all plus commented path globs.
COMMENTED_WO = """---
type: Work Order
allowed_paths:
  - "**"                                 # read-only everywhere
write_allowed:
  - app/store/**                         # emit the co-written events
forbidden_paths:
  - docs/adr/**     # ADR amendment is a separate reviewed change
---
"""

# A frontmatter with no inline comments — must be unaffected by the fix.
UNCOMMENTED_WO = """---
type: Work Order
allowed_paths:
  - app/store/**
  - tests/**
---
"""


def test_extract_list_strips_inline_comment_on_catch_all_glob():
    assert checker.extract_list(COMMENTED_WO, "allowed_paths") == ["**"]


def test_commented_catch_all_glob_matches_a_real_path():
    allowed = checker.extract_list(COMMENTED_WO, "allowed_paths")
    assert any(fnmatch.fnmatch("app/store/core.py", pat) for pat in allowed)


def test_extract_list_strips_inline_comment_on_forbidden_entry():
    assert checker.extract_list(COMMENTED_WO, "forbidden_paths") == ["docs/adr/**"]


def test_extract_list_strips_inline_comment_on_path_glob():
    assert checker.extract_list(COMMENTED_WO, "write_allowed") == ["app/store/**"]


def test_uncommented_entries_are_unchanged():
    assert checker.extract_list(UNCOMMENTED_WO, "allowed_paths") == [
        "app/store/**",
        "tests/**",
    ]
