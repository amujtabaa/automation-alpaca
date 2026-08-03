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

_ALLOWED_STDLIB_ROOTS = {
    "__future__",
    "dataclasses",
    "decimal",
    "enum",
    "fractions",
    "hashlib",
    "typing",
}

_FORBIDDEN_IMPORT_ROOTS = {
    # Runtime capability laundering.
    "builtins",
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
    "sys",
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
    "breakpoint",
    "compile",
    "copyright",
    "credits",
    "dir",
    "eval",
    "exec",
    "exit",
    "globals",
    "help",
    "input",
    "license",
    "locals",
    "open",
    "print",
    "quit",
    "vars",
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
    "print",
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

_FORBIDDEN_CAPABILITY_ATTRIBUTES = {
    "flush",
    "print",
    "stderr",
    "stdin",
    "stdout",
    "write",
    "writelines",
}

_PROTECTION_ALLOWED_BUILTIN_CALLS = {
    "TypeError",
    "ValueError",
    "abs",
    "all",
    "any",
    "bool",
    "bytes",
    "enumerate",
    "frozenset",
    "int",
    "isinstance",
    "len",
    "max",
    "min",
    "object",
    "range",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "type",
    "zip",
}

_PROTECTION_ALLOWED_ATTRIBUTE_CALLS = {
    ("_PersistentKeyMap", "empty"),
    ("_PersistentKeyMap", "get"),
    ("_PersistentKeyMap", "insert_new"),
    ("_PersistentKeyMap", "replace_existing"),
    ("object", "__getattribute__"),
    ("object", "__new__"),
    ("object", "__setattr__"),
    ("str", "strip"),
}

_PROTECTION_ALLOWED_STDLIB_IMPORTED_CALLS = {
    ("dataclasses", "dataclass"),
    ("dataclasses", "field"),
    ("decimal", "Decimal"),
    ("fractions", "Fraction"),
    ("typing", "cast"),
}

_PROTECTION_ALLOWED_INTERNAL_IMPORTED_CALLS = {
    ("app.execution_core.fills", "PositionScope"),
    ("app.execution_core.fills", "_PersistentKeyMap"),
    ("app.execution_core.fills", "_commit_parts"),
    ("app.execution_core.fills", "_encode_fraction"),
    ("app.execution_core.fills", "_encode_int"),
    ("app.execution_core.fills", "_encode_position_scope"),
    ("app.execution_core.fills", "_encode_reported_price"),
    ("app.execution_core.fills", "_encode_text"),
    ("app.execution_core.values", "PriceScale"),
    ("app.execution_core.values", "PriceUnits"),
    ("app.execution_core.values", "Quantity"),
    ("app.execution_core.values", "ReportedPrice"),
    ("app.execution_core.values", "TickMetadata"),
    ("app.execution_core.venue", "_extract_protection_transition"),
}

_PROTECTION_ALLOWED_IMPORTED_BINDINGS = (
    _PROTECTION_ALLOWED_STDLIB_IMPORTED_CALLS
    | _PROTECTION_ALLOWED_INTERNAL_IMPORTED_CALLS
    | {
        ("__future__", "annotations"),
        ("enum", "Enum"),
        ("app.execution_core.fills", "ExecutionSide"),
        ("app.execution_core.identity", "MandateId"),
        ("app.execution_core.identity", "MarketDataSourceId"),
        ("app.execution_core.identity", "MarketOccurrenceId"),
        ("app.execution_core.identity", "SessionId"),
        ("app.execution_core.position", "BasisAuthority"),
        ("app.execution_core.position", "ExecutionSnapshot"),
        ("app.execution_core.position", "PositionIntegrity"),
        ("app.execution_core.venue", "VenueExecutionBinding"),
        ("app.execution_core.venue", "VenueRecoveryDisposition"),
        ("app.execution_core.venue", "VenueRecoveryTransition"),
        ("app.execution_core.venue", "_ProtectionCursor"),
        ("app.execution_core.venue", "_ProtectionTransitionProof"),
        ("app.execution_core.venue", "_SymbolAuthoritySummary"),
    }
)

_PROTECTION_FORBIDDEN_BINDING_ATTRIBUTES = {
    "__bases__",
    "__builtins__",
    "__class__",
    "__closure__",
    "__code__",
    "__dict__",
    "__func__",
    "__globals__",
    "__mro__",
    "__self__",
    "__subclasses__",
}

_PUBLIC_SURFACE = {
    "AccountId",
    "AcceptanceSetState",
    "ActorId",
    "AdvanceManualFlatten",
    "ApplicationGenerationId",
    "AuthorityDisposition",
    "AuthorityInputId",
    "AuthorityQueryKind",
    "AuthorityReason",
    "BasisAuthority",
    "BasisCandidate",
    "BasisCandidateStatus",
    "BeginManualFlatten",
    "BrokerEffect",
    "BrokerEffectRequest",
    "BrokerEffectState",
    "BrokerFillFact",
    "BrokerId",
    "BrokerTradeBustFact",
    "BrokerTradeCorrectFact",
    "CatchUpExecutionRegistry",
    "ClaimBrokerQuery",
    "ClaimEffect",
    "ClaimOccurrenceId",
    "ClientOrderId",
    "ClosureId",
    "CreateBrokerEffect",
    "DiscoverVenueLeg",
    "EffectId",
    "EffectKind",
    "EmergencyGrantId",
    "EngageKill",
    "EnginePhase",
    "EnvironmentId",
    "EvidencePolicy",
    "EvidenceReference",
    "ExactBasis",
    "ExecutionAuthority",
    "ExecutionAuthorityState",
    "ExecutionAuthorityTransition",
    "ExecutionFactKey",
    "ExecutionGoal",
    "ExecutionGuard",
    "ExecutionReconciliationCursor",
    "ExecutionRegistryReconciliationRecord",
    "ExecutionScope",
    "ExecutionSide",
    "ExecutionSnapshot",
    "ExecutionTransition",
    "FactKind",
    "FirstObservationClassification",
    "FoldInput",
    "HumanAttestedFillFact",
    "HumanCoverage",
    "IngestHumanAttestedFill",
    "MandateId",
    "MarketDataSourceId",
    "MarketKind",
    "MarketOccurrence",
    "MarketOccurrenceId",
    "ManualFlattenId",
    "ObserveVenueStatus",
    "OrderId",
    "PendingVenueOperation",
    "PositionIntegrity",
    "PositionProtectionState",
    "PositionScope",
    "PositionState",
    "PriceScale",
    "PriceUnits",
    "ProtectionAlert",
    "ProtectionDisposition",
    "ProtectionMandate",
    "ProtectionPolicy",
    "ProtectionTransition",
    "ProtectionUrgency",
    "ProtectionVenueProjection",
    "Quantity",
    "QueryClaimId",
    "ReconciliationRecord",
    "RecordBrokerFillEvidence",
    "RecordBrokerRevisionEvidence",
    "RecordTransportOutcome",
    "RecoverClaimedEffect",
    "ReleaseVenueLeg",
    "ReportedPrice",
    "RequestBudget",
    "RequestOccurrenceId",
    "RevisionReconciliationRecord",
    "RootFillId",
    "RootFillKey",
    "RootHead",
    "RootHeadIndex",
    "SeenFact",
    "SeenFactIndex",
    "SessionId",
    "SourceEventId",
    "SupervisorFence",
    "SymbolId",
    "TickMetadata",
    "TradingMode",
    "TransitionDisposition",
    "VenueAttempt",
    "VenueAttemptState",
    "VenueClosureKind",
    "VenueExecutionCheckpoint",
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
    "apply_execution_authority_input",
    "apply_venue_recovery_input",
    "bind_venue_execution_snapshot",
    "derive_ordered_basis_candidate",
    "initial_execution_authority_state",
    "initialize_position_protection",
    "project_protection_venue",
    "reduce_position_protection",
}

_FORBIDDEN_PUBLIC_ACCEPTANCE_CLOSURE_CAPABILITIES = {
    "AcceptanceProof",
    "AcceptanceProofKind",
    "CloseAcceptanceSet",
}

_FORBIDDEN_PRODUCTION_VENUE_INTERNAL_NAMES = {
    "AcceptanceProof",
    "AcceptanceProofKind",
    "CloseAcceptanceSet",
    "_apply_venue_input",
    "_audit_hydrate_book",
    "_external_acceptance_closure_is_certified",
}


def _private_acceptance_closure_seam_violations(
    tree: ast.AST,
    path: Path,
) -> list[str]:
    """Report raw closure and reducer seams named by one production syntax tree."""

    violations: list[str] = []
    for node in ast.walk(tree):
        forbidden_name: str | None = None
        if isinstance(node, ast.Name):
            forbidden_name = node.id
        elif isinstance(node, ast.Attribute):
            forbidden_name = node.attr
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name in _FORBIDDEN_PRODUCTION_VENUE_INTERNAL_NAMES:
                    violations.append(f"{_display(path, node)}:{alias.name}")
        elif isinstance(node, ast.Constant) and type(node.value) is str:
            forbidden_name = node.value
        if forbidden_name in _FORBIDDEN_PRODUCTION_VENUE_INTERNAL_NAMES:
            violations.append(f"{_display(path, node)}:{forbidden_name}")
    return violations


def _python_files() -> list[Path]:
    assert _PACKAGE_ROOT.is_dir(), "the isolated app.execution_core package is missing"
    files = sorted(_PACKAGE_ROOT.glob("*.py"))
    assert {path.name for path in files} == {
        "__init__.py",
        "authority.py",
        "fills.py",
        "identity.py",
        "position.py",
        "protection.py",
        "recovery.py",
        "values.py",
        "venue.py",
    }
    return files


def test_protection_has_one_public_reducer_and_no_operational_or_raw_venue_seam() -> (
    None
):
    """Protection stays pure policy data behind one authenticated venue extractor."""

    path = _PACKAGE_ROOT / "protection.py"
    assert path.is_file(), "WO-0148 protection semantic center is missing"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    public_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    assert public_functions == {
        "initialize_position_protection",
        "project_protection_venue",
        "reduce_position_protection",
    }
    forbidden = {
        "BrokerEffectRequest",
        "ClaimEffect",
        "CloseAcceptanceSet",
        "CreateBrokerEffect",
        "RecordDispatchClaim",
        "RequestedEffect",
        "VenueRecoveryBook",
        "_apply_venue_input",
        "apply_execution_authority_input",
        "apply_venue_recovery_input",
    }
    violations: list[str] = []
    extractor_imports = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "venue" and node.level == 1:
                extractor_imports += sum(
                    alias.name == "_extract_protection_transition"
                    for alias in node.names
                )
            for alias in node.names:
                if alias.name in forbidden:
                    violations.append(f"{_display(path, node)}:{alias.name}")
        elif isinstance(node, ast.Name) and node.id in forbidden:
            violations.append(f"{_display(path, node)}:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in forbidden:
            violations.append(f"{_display(path, node)}:{node.attr}")
    assert extractor_imports == 1
    assert not violations, sorted(set(violations))


def _display(path: Path, node: ast.AST) -> str:
    return f"{path.relative_to(_REPO_ROOT)}:{getattr(node, 'lineno', '?')}"


def _call_root_name(node: ast.AST) -> str:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def _static_attribute_path(node: ast.AST) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return (node.id,)
    if not isinstance(node, ast.Attribute):
        return None
    prefix = _static_attribute_path(node.value)
    return None if prefix is None else prefix + (node.attr,)


def _absolute_import_is_allowed(name: str) -> bool:
    root = name.split(".", 1)[0]
    return (
        root in _ALLOWED_STDLIB_ROOTS
        or name == "app.execution_core"
        or name.startswith("app.execution_core.")
    )


def _effect_call_violations(tree: ast.AST, path: Path) -> list[str]:
    """Reject direct or imported effect capabilities without executing them."""

    violations: list[str] = []
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".", 1)[0]] = alias.name
                if not _absolute_import_is_allowed(alias.name):
                    violations.append(
                        f"{_display(path, node)} forbidden capability import {alias.name}"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
                if node.level == 0 and not _absolute_import_is_allowed(node.module):
                    violations.append(
                        f"{_display(path, node)} forbidden capability import {node.module}"
                    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and (
            node.id in _FORBIDDEN_CALL_NAMES or node.id == "__builtins__"
        ):
            violations.append(f"{_display(path, node)} forbidden capability {node.id}")
        if (
            isinstance(node, ast.Attribute)
            and node.attr in _FORBIDDEN_CAPABILITY_ATTRIBUTES
        ):
            violations.append(
                f"{_display(path, node)} forbidden capability attribute {node.attr}"
            )
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in _FORBIDDEN_CAPABILITY_ATTRIBUTES
        ):
            violations.append(
                f"{_display(path, node)} forbidden dynamic capability "
                f"{node.args[1].value}"
            )
        if isinstance(node.func, ast.Name):
            resolved = aliases.get(node.func.id, node.func.id)
            root = resolved.split(".", 1)[0]
            leaf = resolved.rsplit(".", 1)[-1]
            if (
                node.func.id in _FORBIDDEN_CALL_NAMES
                or leaf in _FORBIDDEN_CALL_NAMES
                or root in _FORBIDDEN_IMPORT_ROOTS
            ):
                violations.append(f"{_display(path, node)} forbidden call {resolved}")
        elif isinstance(node.func, ast.Attribute):
            base_name = _call_root_name(node.func)
            resolved_root = aliases.get(base_name, base_name).split(".", 1)[0]
            if (
                node.func.attr in _FORBIDDEN_CALL_ATTRIBUTES
                or resolved_root in _FORBIDDEN_IMPORT_ROOTS
            ):
                violations.append(
                    f"{_display(path, node)} forbidden call *.{node.func.attr}"
                )
        else:
            violations.append(
                f"{_display(path, node)} dynamically constructed call target "
                f"{type(node.func).__name__}"
            )
    return violations


def _protection_call_binding_violations(tree: ast.AST, path: Path) -> list[str]:
    """Allow only statically authenticated callable bindings in protection."""

    if not isinstance(tree, ast.Module):
        return [f"{_display(path, tree)} protection source is not a module"]
    violations: list[str] = []
    declared = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    imported: dict[str, tuple[str, str, int]] = {}
    module_imports: set[str] = set()
    ambiguous_imports: set[str] = set()
    non_module_imports: set[str] = set()
    top_level_imports = {
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    }

    def retain_import_name(name: str, node: ast.AST) -> None:
        if name in imported or name in module_imports:
            ambiguous_imports.add(name)
            violations.append(f"{_display(path, node)} duplicate import binding {name}")

    def canonical_import(binding: tuple[str, str, int]) -> tuple[str, str]:
        module, imported_name, level = binding
        if level == 1:
            owner = "app.execution_core"
            if module:
                owner = f"{owner}.{module}"
            return owner, imported_name
        return module, imported_name

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if node not in top_level_imports:
            violations.append(f"{_display(path, node)} non-module import binding")
            non_module_imports.update(
                alias.asname or alias.name.split(".", 1)[0] for alias in node.names
            )
            continue
        if isinstance(node, ast.Import):
            violations.append(f"{_display(path, node)} module import binding")
            for alias in node.names:
                retained = alias.asname or alias.name.split(".", 1)[0]
                retain_import_name(retained, node)
                module_imports.add(retained)
            continue
        if any(alias.name == "*" for alias in node.names):
            violations.append(f"{_display(path, node)} wildcard import")
        if node.module is None:
            violations.append(f"{_display(path, node)} module import binding")
        for alias in node.names:
            if alias.name == "*":
                continue
            retained = alias.asname or alias.name
            retain_import_name(retained, node)
            if node.module is None:
                module_imports.add(retained)
            else:
                binding = (node.module, alias.name, node.level)
                imported[retained] = binding
                if (
                    canonical_import(binding)
                    not in _PROTECTION_ALLOWED_IMPORTED_BINDINGS
                ):
                    violations.append(
                        f"{_display(path, node)} unapproved imported binding "
                        f"{canonical_import(binding)[0]}.{alias.name}"
                    )

    rebound = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    rebound.update(
        argument.arg for argument in ast.walk(tree) if isinstance(argument, ast.arg)
    )

    def imported_call_is_allowed(name: str) -> bool:
        if name in ambiguous_imports or name in non_module_imports:
            return False
        binding = imported.get(name)
        if binding is None:
            return False
        canonical = canonical_import(binding)
        return canonical in (
            _PROTECTION_ALLOWED_STDLIB_IMPORTED_CALLS
            | _PROTECTION_ALLOWED_INTERNAL_IMPORTED_CALLS
        )

    def callable_name_is_allowed(name: str) -> bool:
        if (
            name in rebound
            or name in module_imports
            or name in ambiguous_imports
            or name in non_module_imports
        ):
            return False
        if name in imported:
            return (
                name not in declared
                and name not in _PROTECTION_ALLOWED_BUILTIN_CALLS
                and imported_call_is_allowed(name)
            )
        if name in declared:
            return name not in _PROTECTION_ALLOWED_BUILTIN_CALLS
        return name in _PROTECTION_ALLOWED_BUILTIN_CALLS

    def attribute_call_is_allowed(attribute_path: tuple[str, ...] | None) -> bool:
        if attribute_path not in _PROTECTION_ALLOWED_ATTRIBUTE_CALLS:
            return False
        root = attribute_path[0]
        if root in {"object", "str"}:
            return (
                root not in declared
                and root not in imported
                and root not in rebound
                and root not in module_imports
                and root not in ambiguous_imports
                and root not in non_module_imports
            )
        return (
            root == "_PersistentKeyMap"
            and root not in declared
            and root not in rebound
            and root not in module_imports
            and root not in ambiguous_imports
            and root not in non_module_imports
            and root in imported
            and canonical_import(imported[root])
            == ("app.execution_core.fills", "_PersistentKeyMap")
        )

    def callback_binding_is_allowed(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant) and node.value is None:
            return True
        if isinstance(node, ast.Name):
            return callable_name_is_allowed(node.id)
        if isinstance(node, ast.Attribute):
            return attribute_call_is_allowed(_static_attribute_path(node))
        return False

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.decorator_list
        ):
            violations.append(
                f"{_display(path, node)} decorated function binding {node.name}"
            )
        if isinstance(node, ast.ClassDef):
            if node.keywords:
                violations.append(f"{_display(path, node)} custom class construction")
            for base in node.bases:
                if not (
                    isinstance(base, ast.Name)
                    and (
                        (base.id == "object" and callable_name_is_allowed(base.id))
                        or (
                            imported.get(base.id) == ("enum", "Enum", 0)
                            and base.id not in declared
                            and base.id not in rebound
                            and base.id not in module_imports
                            and base.id not in ambiguous_imports
                            and base.id not in non_module_imports
                        )
                    )
                ):
                    violations.append(
                        f"{_display(path, base)} unapproved class base binding"
                    )
            for decorator in node.decorator_list:
                target = (
                    decorator.func if isinstance(decorator, ast.Call) else decorator
                )
                if not (
                    isinstance(target, ast.Name)
                    and imported.get(target.id) == ("dataclasses", "dataclass", 0)
                    and target.id not in declared
                    and target.id not in rebound
                    and target.id not in module_imports
                    and target.id not in ambiguous_imports
                    and target.id not in non_module_imports
                ):
                    violations.append(
                        f"{_display(path, decorator)} unapproved class decorator binding"
                    )
        if (
            isinstance(node, ast.Attribute)
            and node.attr in _PROTECTION_FORBIDDEN_BINDING_ATTRIBUTES
        ):
            violations.append(
                f"{_display(path, node)} forbidden binding attribute {node.attr}"
            )
        if isinstance(node, ast.Attribute) and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            violations.append(f"{_display(path, node)} mutable attribute binding")
        if (
            isinstance(node, ast.Constant)
            and type(node.value) is str
            and node.value in _PROTECTION_FORBIDDEN_BINDING_ATTRIBUTES
        ):
            violations.append(
                f"{_display(path, node)} forbidden dynamic binding name {node.value}"
            )
        if not isinstance(node, ast.Call):
            continue
        callback_keywords: set[str] = set()
        if isinstance(node.func, ast.Name):
            binding = imported.get(node.func.id)
            if binding is not None and canonical_import(binding) == (
                "dataclasses",
                "field",
            ):
                callback_keywords.add("default_factory")
            if (
                node.func.id in {"max", "min", "sorted"}
                and node.func.id not in declared
                and node.func.id not in imported
                and node.func.id not in rebound
            ):
                callback_keywords.add("key")
            if (
                node.func.id == "type"
                and node.func.id not in declared
                and node.func.id not in imported
                and node.func.id not in rebound
                and (len(node.args) != 1 or node.keywords)
            ):
                violations.append(f"{_display(path, node)} dynamic type construction")
        for keyword in node.keywords:
            if keyword.arg in callback_keywords and not callback_binding_is_allowed(
                keyword.value
            ):
                violations.append(
                    f"{_display(path, keyword)} unproven callback binding {keyword.arg}"
                )
        if isinstance(node.func, ast.Name):
            if not callable_name_is_allowed(node.func.id):
                violations.append(
                    f"{_display(path, node)} unproven call binding {node.func.id}"
                )
        elif isinstance(node.func, ast.Attribute):
            attribute_path = _static_attribute_path(node.func)
            if not attribute_call_is_allowed(attribute_path):
                rendered = (
                    ".".join(attribute_path)
                    if attribute_path is not None
                    else type(node.func.value).__name__
                )
                violations.append(
                    f"{_display(path, node)} unproven attribute call binding {rendered}"
                )
            elif attribute_path in {
                ("object", "__getattribute__"),
                ("object", "__setattr__"),
            } and (
                len(node.args) < 2
                or not isinstance(node.args[1], ast.Constant)
                or type(node.args[1].value) is not str
                or node.args[1].value in _PROTECTION_FORBIDDEN_BINDING_ATTRIBUTES
            ):
                violations.append(
                    f"{_display(path, node)} unproven object attribute name"
                )
        else:
            violations.append(
                f"{_display(path, node)} unproven dynamic call binding "
                f"{type(node.func).__name__}"
            )
    return violations


def test_effect_call_oracle_rejects_direct_runtime_output() -> None:
    path = _PACKAGE_ROOT / "synthetic_output_mutant.py"
    mutants = (
        (
            "def reduce(occurrence):\n"
            "    if occurrence is not None:\n"
            "        print('mutant output')\n"
        ),
        "import sys\ndef reduce():\n    sys.stdout.write('mutant output')\n",
        "from builtins import print as emit\ndef reduce():\n    emit('mutant output')\n",
        (
            "import builtins\n"
            "emit = builtins.print\n"
            "def reduce():\n"
            "    emit('mutant output')\n"
        ),
        (
            "import builtins\n"
            "def reduce():\n"
            "    getattr(builtins, 'print')('mutant output')\n"
        ),
        ("def reduce():\n    __builtins__['print']('mutant output')\n"),
        (
            "def reduce(occurrence):\n"
            "    if occurrence.source_sequence == 424242:\n"
            "        globals()['__builtins__']['print']('mutant output')\n"
        ),
        "def reduce():\n    help('mutant output')\n",
        "import traceback\ndef reduce():\n    traceback.print_exc()\n",
    )
    for source in mutants:
        assert _effect_call_violations(ast.parse(source), path), source

    passive = ast.parse("def reduce(values):\n    return len(values)\n")
    assert _effect_call_violations(passive, path) == []

    binding_mutants = (
        (
            "import dataclasses\n"
            "_emit = dataclasses.__builtins__['print']\n"
            "def reduce(occurrence):\n"
            "    if occurrence.source_sequence == 424242:\n"
            "        _emit('escaped output')\n"
        ),
        "def reduce():\n    credits()\n",
        (
            "def _helper():\n"
            "    return None\n"
            "_helper = lambda: None\n"
            "def reduce():\n"
            "    _helper()\n"
        ),
        (
            "import dataclasses\n"
            "def _helper():\n"
            "    return None\n"
            "_helper.__globals__['_helper'] = "
            "dataclasses.__builtins__['print']\n"
            "def reduce():\n"
            "    _helper('escaped output')\n"
        ),
        (
            "def _helper():\n"
            "    return None\n"
            "def reduce():\n"
            "    namespace = object.__getattribute__(\n"
            "        _helper, '__glo' + 'bals__'\n"
            "    )\n"
            "    namespace['_helper'] = len\n"
            "    _helper()\n"
        ),
        (
            "def _replacement(value):\n"
            "    return value\n"
            "str.strip = _replacement\n"
            "def reduce(value):\n"
            "    return str.strip(value)\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass, field as _field\n"
            "@_dataclass(frozen=True)\n"
            "class _Payload:\n"
            "    value: object = _field(default_factory=credits)\n"
            "def reduce(flag):\n"
            "    if flag:\n"
            "        _Payload()\n"
        ),
        (
            "class _PersistentKeyMap:\n"
            "    empty = credits\n"
            "def reduce(flag):\n"
            "    if flag:\n"
            "        _PersistentKeyMap.empty()\n"
        ),
        ("class str:\n    strip = credits\ndef reduce():\n    str.strip()\n"),
        "from .venue import _emit\ndef reduce():\n    _emit()\n",
        (
            "from .venue import _evil_iterable\n"
            "def reduce(flag):\n"
            "    if flag:\n"
            "        for _ in _evil_iterable:\n"
            "            pass\n"
        ),
        (
            "if flag:\n"
            "    from .venue import _emit as target\n"
            "else:\n"
            "    from .venue import _extract_protection_transition as target\n"
            "def reduce(value):\n"
            "    target(value)\n"
        ),
        (
            "from . import fills as str\n"
            "def reduce(value):\n"
            "    return str.strip(value)\n"
        ),
        (
            "from . import venue as _venue\n"
            "def reduce(flag):\n"
            "    if flag:\n"
            "        for _ in _venue._evil_iterable:\n"
            "            pass\n"
        ),
        (
            "def reduce():\n"
            "    dynamic = type('Dynamic', (object,), {})\n"
            "    return dynamic\n"
        ),
    )
    for source in binding_mutants:
        assert _protection_call_binding_violations(ast.parse(source), path), source

    authenticated = ast.parse(
        "from dataclasses import dataclass, field\n"
        "from .fills import _PersistentKeyMap\n"
        "from .venue import _extract_protection_transition\n"
        "@dataclass(frozen=True)\n"
        "class Value:\n"
        "    item: int\n"
        "@dataclass(frozen=True)\n"
        "class Book:\n"
        "    retained: object = field(default_factory=_PersistentKeyMap.empty)\n"
        "def _helper(values):\n"
        "    return len(values)\n"
        "def reduce(values, transition):\n"
        "    _extract_protection_transition(transition)\n"
        "    _PersistentKeyMap.get(_PersistentKeyMap.empty(), b'key')\n"
        "    return Value(_helper(values)), Book()\n"
    )
    assert _protection_call_binding_violations(authenticated, path) == []


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
                elif root not in _ALLOWED_STDLIB_ROOTS:
                    violations.append(
                        f"{_display(path, node)} unapproved stdlib import {name}"
                    )

    assert not violations, "execution-core import boundary crossed:\n" + "\n".join(
        violations
    )


def test_execution_core_ast_has_no_dynamic_import_io_clock_or_nondeterminism() -> None:
    """Aliases cannot hide forbidden effectful calls from the import test."""

    violations: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(_effect_call_violations(tree, path))
        if path.name == "protection.py":
            violations.extend(_protection_call_binding_violations(tree, path))

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


def test_caller_authored_acceptance_closure_is_not_a_public_capability() -> None:
    """Proof metadata and its close command must stay behind the venue reducer."""

    import app.execution_core as kernel
    import app.execution_core.venue as venue

    exposures = {
        f"root attribute:{name}"
        for name in _FORBIDDEN_PUBLIC_ACCEPTANCE_CLOSURE_CAPABILITIES
        if hasattr(kernel, name)
    }
    exposures.update(
        f"root __all__:{name}"
        for name in _FORBIDDEN_PUBLIC_ACCEPTANCE_CLOSURE_CAPABILITIES
        if name in kernel.__all__
    )
    exposures.update(
        f"venue __all__:{name}"
        for name in _FORBIDDEN_PUBLIC_ACCEPTANCE_CLOSURE_CAPABILITIES
        if name in venue.__all__
    )

    assert not exposures, sorted(exposures)


def test_production_modules_cannot_reach_private_acceptance_closure_seams() -> None:
    """Only venue.py may name raw closure, generic reducer, or audit-hydration seams."""

    assert _FORBIDDEN_PRODUCTION_VENUE_INTERNAL_NAMES == {
        "AcceptanceProof",
        "AcceptanceProofKind",
        "CloseAcceptanceSet",
        "_apply_venue_input",
        "_audit_hydrate_book",
        "_external_acceptance_closure_is_certified",
    }
    app_root = _REPO_ROOT / "app"
    venue_path = _PACKAGE_ROOT / "venue.py"
    violations: list[str] = []
    for path in sorted(app_root.rglob("*.py")):
        if path == venue_path:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(_private_acceptance_closure_seam_violations(tree, path))

    assert not violations, sorted(set(violations))


@pytest.mark.parametrize(
    "forbidden_name",
    [
        "AcceptanceProof",
        "AcceptanceProofKind",
        "CloseAcceptanceSet",
        "_apply_venue_input",
        "_audit_hydrate_book",
        "_external_acceptance_closure_is_certified",
    ],
)
def test_private_acceptance_closure_ast_guard_is_failure_capable(
    forbidden_name: str,
) -> None:
    """Every protected spelling is caught as a name, attribute, import, and string."""

    synthetic_path = _REPO_ROOT / "tests" / "synthetic_private_venue_seam.py"
    snippets = (
        forbidden_name,
        f"venue.{forbidden_name}",
        f"from app.execution_core.venue import {forbidden_name}",
        repr(forbidden_name),
    )
    for snippet in snippets:
        tree = ast.parse(snippet, filename=str(synthetic_path))
        violations = _private_acceptance_closure_seam_violations(
            tree,
            synthetic_path,
        )
        assert any(item.endswith(f":{forbidden_name}") for item in violations), snippet
