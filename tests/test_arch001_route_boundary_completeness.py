"""ARCH-001 — the ADR-005 route->facade boundary (import-linter Contract 5,
``api-routes-reach-backend-only-via-facade``) is an opt-in, hand-enumerated
source list, and ``allow_indirect_imports = True`` lets a route reach the raw
store via ``app.api.deps.get_store``. `lint-imports` therefore stays green even
when a NEW route module is not listed, or a listed route pulls the raw
``StateStore`` through ``get_store``. These two INI-independent regressions close
what the contract cannot see itself:

1. every ``app/api/routes_*.py`` module MUST be a Contract-5 source (a new route
   cannot be silently exempt from the boundary until someone edits the INI);
2. no route module may import ``get_store`` (the raw-``StateStore`` DI seam) —
   routes reach the store/engine/broker only through the typed facade.
"""

from __future__ import annotations

import ast
import configparser
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ROUTES_DIR = _REPO_ROOT / "app" / "api"
_CONTRACT = "importlinter:contract:api-routes-reach-backend-only-via-facade"


def _route_modules() -> set[str]:
    return {f"app.api.{p.stem}" for p in _ROUTES_DIR.glob("routes_*.py")}


def _contract5_sources() -> set[str]:
    cfg = configparser.ConfigParser()
    cfg.read(_REPO_ROOT / ".importlinter")
    raw = cfg[_CONTRACT]["source_modules"]
    return {line.strip() for line in raw.splitlines() if line.strip()}


def test_every_route_module_is_a_contract5_source():
    missing = _route_modules() - _contract5_sources()
    assert not missing, (
        "route module(s) are not listed as Contract-5 sources, so the ADR-005 "
        "route->facade boundary does NOT apply to them (a green lint-imports "
        f"hides the gap): {sorted(missing)}. Add them to `.importlinter` "
        "[importlinter:contract:api-routes-reach-backend-only-via-facade]."
    )


def test_no_route_module_imports_get_store():
    offenders: dict[str, str] = {}
    for path in sorted(_ROUTES_DIR.glob("routes_*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "get_store":
                        offenders[path.name] = node.module or ""
    assert not offenders, (
        "route module(s) import get_store (the raw StateStore DI seam), "
        "bypassing the facade with a green lint-imports (allow_indirect_imports "
        f"= True): {offenders}. Routes must depend only on the facade providers "
        "(get_command_facade / get_query_facade)."
    )
