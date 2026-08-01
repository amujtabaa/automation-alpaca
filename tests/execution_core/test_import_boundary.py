"""Failure-capable purity and import-boundary pins for ``app.execution_core``.

The reset kernel is deliberately smaller than an application layer.  These tests
therefore inspect source syntax as well as the import graph: adding a convenient
clock, logger, database helper, incumbent projector, or dynamic import must make
the focused gate red even when that dependency is never exercised by an example.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "app" / "execution_core"

_FORBIDDEN_IMPORT_ROOTS = {
    # Persistence, process, filesystem, and general I/O surfaces.
    "asyncio",
    "dbm",
    "glob",
    "io",
    "logging",
    "os",
    "pathlib",
    "pickle",
    "shelve",
    "shutil",
    "sqlite3",
    "subprocess",
    "tempfile",
    # Wall-clock, nondeterminism, and dynamic loading.
    "datetime",
    "importlib",
    "random",
    "time",
    "uuid",
    # Web, network, UI, ORM, and venue dependencies.
    "aiohttp",
    "alpaca",
    "fastapi",
    "http",
    "httpx",
    "requests",
    "socket",
    "sqlalchemy",
    "streamlit",
    "urllib",
}

_FORBIDDEN_CALL_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "open",
}

_FORBIDDEN_CALL_ATTRIBUTES = {
    "connect",
    "get_event_loop",
    "get_running_loop",
    "import_module",
    "monotonic",
    "now",
    "open",
    "perf_counter",
    "read_bytes",
    "read_text",
    "sleep",
    "socket",
    "time",
    "today",
    "urlopen",
    "utcnow",
    "uuid1",
    "uuid4",
    "write_bytes",
    "write_text",
}

_PUBLIC_SURFACE = {
    "AccountId",
    "AcceptanceProof",
    "AcceptanceProofKind",
    "AcceptanceSetState",
    "ActorId",
    "ApplicationGenerationId",
    "BasisAuthority",
    "BasisCandidate",
    "BasisCandidateStatus",
    "BrokerFillFact",
    "BrokerEffect",
    "BrokerEffectState",
    "BrokerId",
    "BrokerTradeBustFact",
    "BrokerTradeCorrectFact",
    "CancelBeforeDispatch",
    "ClaimOccurrenceId",
    "ClientOrderId",
    "CloseAcceptanceSet",
    "ClosureId",
    "DiscoverVenueLeg",
    "EnvironmentId",
    "ExactBasis",
    "ExecutionAuthority",
    "ExecutionFactKey",
    "ExecutionScope",
    "ExecutionSide",
    "ExecutionSnapshot",
    "ExecutionTransition",
    "EffectId",
    "EffectKind",
    "EvidenceReference",
    "FactKind",
    "FirstObservationClassification",
    "FoldInput",
    "HumanAttestedFillFact",
    "HumanCoverage",
    "IngestHumanAttestedFill",
    "MandateId",
    "ObserveVenueStatus",
    "OrderId",
    "PendingVenueOperation",
    "PositionIntegrity",
    "PositionScope",
    "PositionState",
    "PriceScale",
    "PriceUnits",
    "Quantity",
    "ReportedPrice",
    "RecordBrokerFillEvidence",
    "RecordDispatchClaim",
    "RecordPendingVenueOperation",
    "RecordTransportOutcome",
    "RecoverClaimedEffect",
    "ReconciliationRecord",
    "ReleaseVenueLeg",
    "RequestOccurrenceId",
    "RequestedEffect",
    "RootFillId",
    "RootFillKey",
    "RootHead",
    "RootHeadIndex",
    "SeenFact",
    "SeenFactIndex",
    "SourceEventId",
    "SymbolId",
    "TickMetadata",
    "TransitionDisposition",
    "VenueAttempt",
    "VenueAttemptState",
    "VenueIdentityOwner",
    "VenueInputId",
    "VenueIntegrity",
    "VenueLegKey",
    "VenueObservationId",
    "VenueRecoveryBook",
    "VenueRecoveryDisposition",
    "VenueRecoveryTransition",
    "VenueScope",
    "VenueTerminalClosure",
    "apply_broker_execution_fact",
    "apply_venue_recovery_input",
    "derive_ordered_basis_candidate",
}


def _python_files() -> list[Path]:
    assert _PACKAGE_ROOT.is_dir(), "the isolated app.execution_core package is missing"
    files = sorted(_PACKAGE_ROOT.glob("*.py"))
    assert {path.name for path in files} == {
        "__init__.py",
        "fills.py",
        "identity.py",
        "position.py",
        "recovery.py",
        "values.py",
        "venue.py",
    }
    return files


def _display(path: Path, node: ast.AST) -> str:
    return f"{path.relative_to(_REPO_ROOT)}:{getattr(node, 'lineno', '?')}"


def test_execution_core_imports_only_itself_and_deterministic_stdlib() -> None:
    """Direct imports stay inside the new kernel or deterministic stdlib."""

    violations: list[str] = []
    stdlib = sys.stdlib_module_names
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    # Relative imports cannot escape this one-level package because
                    # only ``from .x`` is accepted; ``from ..`` is a boundary leak.
                    if node.level != 1:
                        violations.append(
                            f"{_display(path, node)} relative level {node.level}"
                        )
                    continue
                if node.module:
                    names.append(node.module)
            for name in names:
                root = name.split(".", 1)[0]
                own = name == "app.execution_core" or name.startswith(
                    "app.execution_core."
                )
                if root in _FORBIDDEN_IMPORT_ROOTS:
                    violations.append(f"{_display(path, node)} forbidden import {name}")
                elif name == "app" or name.startswith("app."):
                    if not own:
                        violations.append(
                            f"{_display(path, node)} incumbent import {name}"
                        )
                elif root not in stdlib:
                    violations.append(f"{_display(path, node)} external import {name}")

    assert not violations, "execution-core import boundary crossed:\n" + "\n".join(
        violations
    )


def test_execution_core_ast_has_no_dynamic_import_io_clock_or_nondeterminism() -> None:
    """Aliases cannot hide forbidden effectful calls from the import test."""

    violations: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                resolved = aliases.get(node.func.id, node.func.id)
                root = resolved.split(".", 1)[0]
                if (
                    node.func.id in _FORBIDDEN_CALL_NAMES
                    or root in _FORBIDDEN_IMPORT_ROOTS
                ):
                    violations.append(
                        f"{_display(path, node)} forbidden call {resolved}"
                    )
            elif isinstance(node.func, ast.Attribute):
                base = node.func.value
                base_name = base.id if isinstance(base, ast.Name) else ""
                resolved_root = aliases.get(base_name, base_name).split(".", 1)[0]
                if (
                    node.func.attr in _FORBIDDEN_CALL_ATTRIBUTES
                    or resolved_root in _FORBIDDEN_IMPORT_ROOTS
                ):
                    violations.append(
                        f"{_display(path, node)} forbidden call *.{node.func.attr}"
                    )

    assert not violations, "execution-core effect boundary crossed:\n" + "\n".join(
        violations
    )


def test_grimp_graph_has_no_incumbent_or_external_dependency() -> None:
    """Graph proof complements AST aliases and catches package-level imports."""

    grimp = pytest.importorskip("grimp")
    # Grimp requires a top-level package root. Build the complete ``app`` graph,
    # then inspect only the execution-core modules below; asking it to build the
    # nested package directly raises ``NotATopLevelModule`` before any boundary
    # assertion can run.
    graph = grimp.build_graph("app", include_external_packages=True)
    kernel_modules = {
        module
        for module in graph.modules
        if module == "app.execution_core" or module.startswith("app.execution_core.")
    }
    assert kernel_modules

    leaks: dict[str, list[str]] = {}
    for module in sorted(kernel_modules):
        imported = graph.find_modules_directly_imported_by(module)
        bad = sorted(
            target
            for target in imported
            if (
                (target == "app" or target.startswith("app."))
                and not (
                    target == "app.execution_core"
                    or target.startswith("app.execution_core.")
                )
            )
            or target.split(".", 1)[0] in _FORBIDDEN_IMPORT_ROOTS
        )
        if bad:
            leaks[module] = bad

    assert not leaks, f"app.execution_core import-graph leaks: {leaks}"


def test_public_import_is_side_effect_free_and_complete() -> None:
    """A clean interpreter import loads no banned subsystem and exports the API."""

    script = f"""
import json
import sys
sys.path.insert(0, {str(_REPO_ROOT)!r})
# Establish the transitive import baseline of the deterministic stdlib modules
# the AST gate permits. For example, ``dataclasses`` itself loads ``inspect``,
# which loads ``importlib`` and ``os``; those are not execution-core imports.
import dataclasses
import decimal
import enum
import fractions
import typing
before = set(sys.modules)
import app.execution_core as kernel
after = set(sys.modules) - before
forbidden = {sorted(_FORBIDDEN_IMPORT_ROOTS)!r}
loaded = sorted(name for name in after if name.split('.', 1)[0] in forbidden)
missing = sorted(name for name in {_PUBLIC_SURFACE!r} if not hasattr(kernel, name))
declared = sorted(kernel.__all__)
print(json.dumps({{'loaded': loaded, 'missing': missing, 'declared': declared}}))
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", script],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["loaded"] == []
    assert result["missing"] == []
    assert result["declared"] == sorted(_PUBLIC_SURFACE)
