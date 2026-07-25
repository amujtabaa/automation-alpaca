"""Spine v2 Phase 5 — import-boundary enforcement (CLAUDE.md §5, ADR-005/006).

Runs the ``.importlinter`` contracts as part of the normal test suite so a PR that
crosses a protected architectural boundary fails locally too, not only in CI. The
contracts are static import-graph analysis (grimp) — no network / live IO (Rule 9);
this is an architecture test, in the spirit of the ``harness/`` boundary scripts.

Two layers of defense:

* ``test_all_import_contracts_hold`` runs the full ``.importlinter`` config.
* the grimp-based tests re-assert the load-bearing invariants DIRECTLY against the
  import graph — alpaca-SDK confinement (direct AND transitive), a thin UI, a
  venue-agnostic engine, and a leaf model kernel — so those safety boundaries stay
  proven even if the INI is later weakened or mis-edited (the review's Finding 3).
  Only the ADR-005 route→facade *ratchet* (a migration-debt tracker, not a runtime
  safety boundary) is INI-only.
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

# The two — and only two — modules sanctioned to DIRECTLY import the Alpaca SDK:
# the concrete broker adapter and the concrete market-data stream (ADR-005).
_SANCTIONED_ALPACA_IMPORTERS = {
    "app.broker.alpaca_paper",
    "app.marketdata.alpaca_stream",
}

# The full set of modules allowed to TRANSITIVELY reach the SDK: the two direct
# importers above, the two credential-safe factories that build them, and the
# composition roots that wire them: the application, backend-owned launcher,
# and read-only tape-recorder launcher. (ADR-006 Finding 1 — the factories were
# lifted out of the package __init__ so the bare `app.broker`/`app.marketdata`
# packages, and thus the abstract port, never reach alpaca.)
_SANCTIONED_ALPACA_REACHERS = _SANCTIONED_ALPACA_IMPORTERS | {
    "app.broker.factory",
    "app.marketdata.factory",
    "app.main",
    # The backend-owned launch/composition root (ADR-009 A-1 clause 6):
    # `python -m app` -> app.server.run() -> app.main.create_app().
    "app.server",
    "app.__main__",
    "app.recorder.__main__",
    "app.recorder.runner",
}

# Concrete venue implementations the venue-agnostic engine must never reach
# (directly or transitively) — it depends only on the abstract ports
# (`app.broker.adapter`, `app.marketdata.service`).
_CONCRETE_VENUE_MODULES = {
    "app.broker.alpaca_paper",
    "app.broker.mock",
    "app.broker.sim",
    "app.marketdata.alpaca_stream",
    "app.marketdata.fake",
}

# The venue-agnostic engine layer (mirrors the `engine-is-venue-agnostic` contract
# source list). Kept in sync with `.importlinter`.
_ENGINE_PACKAGES = [
    "app.monitoring",
    "app.reconciliation",
    "app.policy",
    "app.position",
    "app.protection",
    "app.strategy",
    "app.strategy_loop",
    "app.features",
    "app.transitions",
    "app.events",
    "app.approval",
]


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


def test_only_sanctioned_modules_transitively_reach_the_alpaca_sdk():
    """INI-independent, TRANSITIVE strengthening of INV-070 / ADR-006 Finding 1:
    the set of modules that reach ``alpaca`` by ANY import chain is exactly the two
    concrete ports + the two factories + the composition roots. This catches an
    indirect leak (e.g. an engine module importing the bare `app.broker` factory
    package) that the direct-import contract, with ``allow_indirect_imports``, does
    not — the exact hole the review found."""

    graph = grimp.build_graph("app", "cockpit", include_external_packages=True)
    reachers = set(graph.find_downstream_modules("alpaca"))
    stray = reachers - _SANCTIONED_ALPACA_REACHERS
    assert not stray, (
        f"modules that transitively reach the Alpaca SDK outside the sanctioned "
        f"factory/composition-root set: {sorted(stray)}. Only "
        f"{sorted(_SANCTIONED_ALPACA_REACHERS)} may reach alpaca (ADR-006)."
    )


def test_engine_never_reaches_a_concrete_venue_implementation():
    """INI-independent proof of INV-072 (the `engine-is-venue-agnostic` contract):
    no engine module reaches a concrete broker/feed implementation by ANY chain — it
    depends only on the abstract ports. Guards the contract against a config
    mis-edit AND against a NEW engine module importing a concrete adapter."""

    graph = grimp.build_graph("app", "cockpit", include_external_packages=False)
    engine_mods = {
        m
        for pkg in _ENGINE_PACKAGES
        for m in graph.modules
        if m == pkg or m.startswith(pkg + ".")
    }
    offenders = {}
    for concrete in _CONCRETE_VENUE_MODULES:
        reachers = set(graph.find_downstream_modules(concrete)) | {concrete}
        hit = engine_mods & reachers
        if hit:
            offenders[concrete] = sorted(hit)
    assert not offenders, (
        f"engine modules reach a concrete venue implementation (must use the abstract "
        f"port only): {offenders}"
    )


def test_models_kernel_imports_no_app_layer():
    """INI-independent proof of INV-073 (the `models-is-a-leaf` contract):
    ``app.models`` imports no other ``app.*`` module, so the shared kernel can never
    take a dependency back on a higher layer."""

    graph = grimp.build_graph("app", include_external_packages=False)
    model_mods = [
        m for m in graph.modules if m == "app.models" or m.startswith("app.models.")
    ]
    leaks = sorted(
        tgt
        for m in model_mods
        for tgt in graph.find_modules_directly_imported_by(m)
        if (tgt == "app" or tgt.startswith("app."))
        and not (tgt == "app.models" or tgt.startswith("app.models."))
    )
    assert not leaks, (
        f"app.models imports other app layers {leaks} — the model kernel must be a "
        f"leaf (INV-073)."
    )
