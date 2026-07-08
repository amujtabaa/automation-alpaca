"""Spine v2 Phase 5 — import-boundary enforcement (CLAUDE.md §5, ADR-005/006).

Runs the ``.importlinter`` contracts as part of the normal test suite so a PR that
crosses a protected architectural boundary fails locally too, not only in CI. The
contracts are static import-graph analysis (grimp) — no network / live IO (Rule 9);
this is an architecture test, in the spirit of the ``harness/`` boundary scripts.

Two layers of defense:

* ``test_all_import_contracts_hold`` runs the full ``.importlinter`` config.
* the grimp-based tests re-assert the two load-bearing invariants (alpaca-SDK
  confinement, a thin UI) DIRECTLY against the import graph — so those safety
  boundaries stay proven even if the INI is later weakened or mis-edited.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG = _REPO_ROOT / ".importlinter"

importlinter = pytest.importorskip(
    "importlinter", reason="import-linter not installed (it is a CI/dev tool)"
)
grimp = pytest.importorskip("grimp")

# The two — and only two — modules sanctioned to import the Alpaca SDK: the
# concrete broker adapter and the concrete market-data stream (ADR-005).
_SANCTIONED_ALPACA_IMPORTERS = {
    "app.broker.alpaca_paper",
    "app.marketdata.alpaca_stream",
}


def test_all_import_contracts_hold():
    """The full ``.importlinter`` contract set is KEPT (0 broken)."""

    from importlinter import configuration
    from importlinter.application import use_cases

    assert _CONFIG.is_file(), f"missing {_CONFIG}"
    # Bootstrap the built-in contract/option readers — the CLI does this at
    # startup; a programmatic call must do it explicitly or lint_imports raises
    # KeyError('USER_OPTION_READERS').
    configuration.configure()
    # cache_dir=None: don't write an import-linter cache dir into the repo/tmp
    # during the test run.
    ok = use_cases.lint_imports(config_filename=str(_CONFIG), cache_dir=None)
    assert ok, (
        "import-linter reported a broken contract — run `lint-imports` to see which "
        "architectural boundary was crossed (see .importlinter / docs/adr/"
        "ADR-006-import-boundaries.md)."
    )


def test_alpaca_sdk_is_confined_to_the_two_concrete_ports():
    """INI-independent proof of invariant #5: nothing outside the concrete adapter
    and stream imports ``alpaca``. This is the boundary that keeps the UI/engine
    from ever touching the venue directly (CLAUDE.md §3)."""

    graph = grimp.build_graph("app", "cockpit", include_external_packages=True)
    importers = graph.find_modules_that_directly_import("alpaca")
    stray = set(importers) - _SANCTIONED_ALPACA_IMPORTERS
    assert not stray, (
        f"modules importing alpaca-py outside the sanctioned ports: {sorted(stray)} "
        f"— only {sorted(_SANCTIONED_ALPACA_IMPORTERS)} may import the SDK (ADR-005)."
    )


def test_cockpit_imports_no_backend_code():
    """INI-independent proof of invariant #4: the Streamlit cockpit imports no
    ``app.*`` module — it is a thin client over its typed API client only."""

    graph = grimp.build_graph("app", "cockpit", include_external_packages=False)
    leaks = sorted(
        m
        for cockpit_mod in graph.modules
        if cockpit_mod == "cockpit" or cockpit_mod.startswith("cockpit.")
        for m in graph.find_modules_directly_imported_by(cockpit_mod)
        if m == "app" or m.startswith("app.")
    )
    assert not leaks, (
        f"cockpit imports backend modules {leaks} — the UI must call the backend only "
        f"over HTTP via cockpit.api_client (invariant #4)."
    )
