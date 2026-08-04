"""Failure-capable purity and import-boundary pins for ``app.execution_core``.

The reset kernel is deliberately smaller than an application layer.  These tests
therefore inspect source syntax as well as the import graph: adding a convenient
clock, logger, database helper, incumbent projector, or dynamic import must make
the focused gate red even when that dependency is never exercised by an example.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
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
    "type",
}

_PROTECTION_ALLOWED_ATTRIBUTE_CALLS = {
    ("int", "to_bytes"),
    ("object", "__new__"),
    ("object", "__setattr__"),
}

_PROTECTION_OPAQUE_VALUE_TYPES = {
    "PositionProtectionState",
    "ProtectionVenueProjection",
}

_PROTECTION_ALLOWED_STDLIB_IMPORTED_CALLS = {
    ("dataclasses", "dataclass"),
    ("decimal", "Decimal"),
    ("fractions", "Fraction"),
    ("hashlib", "sha256"),
}

_PROTECTION_IMPORTED_ENUM_MEMBERS = {
    ("app.execution_core.fills", "ExecutionSide"): frozenset({"BUY", "SELL"}),
    ("app.execution_core.position", "BasisAuthority"): frozenset(
        {"AVAILABLE", "BASIS_RECONCILIATION_PENDING"}
    ),
    ("app.execution_core.position", "PositionIntegrity"): frozenset(
        {
            "CONSISTENT",
            "EXECUTION_FACT_CONFLICT",
            "EXECUTION_RECONCILIATION_REQUIRED",
            "OVERFILL_QUARANTINE",
        }
    ),
    ("app.execution_core.venue", "VenueRecoveryDisposition"): frozenset(
        {
            "APPLIED",
            "EXACT_REPLAY",
            "CONFLICT",
            "RECONCILIATION_REQUIRED",
            "REFUSED",
        }
    ),
}

_PROTECTION_ALLOWED_INTERNAL_IMPORTED_CALLS = {
    ("app.execution_core.fills", "PositionScope"),
    ("app.execution_core.fills", "_commit_parts"),
    ("app.execution_core.fills", "_encode_fraction"),
    ("app.execution_core.fills", "_encode_int"),
    ("app.execution_core.fills", "_encode_position_scope"),
    ("app.execution_core.fills", "_encode_reported_price"),
    ("app.execution_core.fills", "_encode_text"),
    ("app.execution_core.fills", "_pack_parts"),
    ("app.execution_core.identity", "MarketOccurrenceId"),
    ("app.execution_core.identity", "MarketStreamGenerationId"),
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
        ("app.execution_core.identity", "MarketStreamGenerationId"),
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

_PROTECTION_FIXED_STATE_LEAF_IMPORTS = {
    ("enum", "Enum"),
    ("fractions", "Fraction"),
    ("app.execution_core.fills", "PositionScope"),
    ("app.execution_core.identity", "MandateId"),
    ("app.execution_core.identity", "MarketDataSourceId"),
    ("app.execution_core.identity", "MarketOccurrenceId"),
    ("app.execution_core.identity", "MarketStreamGenerationId"),
    ("app.execution_core.identity", "SessionId"),
    ("app.execution_core.values", "Quantity"),
    ("app.execution_core.values", "ReportedPrice"),
    ("app.execution_core.values", "TickMetadata"),
}

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
    "MarketSequenceMode",
    "MarketStreamGenerationId",
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
    "invalidate_position_protection_market",
    "project_protection_venue",
    "reduce_position_protection",
    "reduce_position_protection_market",
}

_PROTECTION_PUBLIC_TRANSITIONS = {
    "initialize_position_protection": ("mandate", "projection"),
    "invalidate_position_protection_market": ("state", "projection"),
    "project_protection_venue": ("transition", "mandate"),
    "reduce_position_protection": ("state", "projection"),
    "reduce_position_protection_market": ("state", "projection", "occurrence"),
}

_PROTECTION_MARKET_ROOTS = {
    "invalidate_position_protection_market",
    "reduce_position_protection_market",
}

_PROTECTION_VARIABLE_CARDINALITY_TYPES = {
    "AbstractSet",
    "Collection",
    "DefaultDict",
    "Deque",
    "Dict",
    "FrozenSet",
    "Generator",
    "Iterable",
    "Iterator",
    "List",
    "Mapping",
    "MutableMapping",
    "MutableSequence",
    "Sequence",
    "Set",
    "_PersistentKeyMap",
    "dict",
    "frozenset",
    "list",
    "set",
}

_PROTECTION_VARIADIC_TUPLE_TYPES = {"Tuple", "tuple"}

_PROTECTION_ALLOWED_MARKET_LOCAL_CONSTRUCTORS = {
    "ExecutionGoal",
    "ProtectionTransition",
}

_PROTECTION_HISTORY_NAME_FRAGMENTS = {
    "history",
    "persistentkeymap",
    "receipt",
    "seen_occurrence",
    "tape",
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


def _protection_public_transition_violations(
    tree: ast.Module,
    path: Path,
) -> list[str]:
    """Pin the five ADR-023 roles and reject caller-shaped recovery surfaces."""

    violations: list[str] = []
    public_functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    actual = set(public_functions)
    expected = set(_PROTECTION_PUBLIC_TRANSITIONS)
    if actual != expected:
        violations.append(
            f"{_display(path, tree)} exact public transition set differs: "
            f"missing={sorted(expected - actual)!r}, extra={sorted(actual - expected)!r}"
        )

    for name in sorted(expected & actual):
        function = public_functions[name]
        arguments = function.args
        positional = arguments.posonlyargs + arguments.args
        observed = tuple(argument.arg for argument in positional)
        exact_shape = (
            isinstance(function, ast.FunctionDef)
            and not function.decorator_list
            and not arguments.posonlyargs
            and observed == _PROTECTION_PUBLIC_TRANSITIONS[name]
            and arguments.vararg is None
            and arguments.kwarg is None
            and not arguments.kwonlyargs
            and not arguments.defaults
            and not arguments.kw_defaults
        )
        if not exact_shape:
            violations.append(
                f"{_display(path, function)} public transition {name} has "
                f"noncanonical parameters {observed!r}"
            )
    return violations


def test_protection_has_exact_adr023_public_roles_and_no_operational_seam() -> None:
    """Protection exposes five independent pure roles behind one venue extractor."""

    path = _PACKAGE_ROOT / "protection.py"
    assert path.is_file(), "WO-0148 protection semantic center is missing"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assert not _protection_public_transition_violations(tree, path)
    assert not _protection_dynamic_public_surface_violations(tree, path)
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


def _protection_dynamic_public_surface_violations(
    tree: ast.Module,
    path: Path,
) -> list[str]:
    """Forbid module hooks that synthesize transition or capability aliases."""

    violations: list[str] = []
    forbidden_hooks = {"__dir__", "__getattr__"}
    for statement in tree.body:
        names: set[str] = set()
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(statement.name)
        elif isinstance(statement, ast.Assign):
            names.update(
                target.id
                for target in statement.targets
                if isinstance(target, ast.Name)
            )
        elif isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            names.add(statement.target.id)
        elif isinstance(statement, (ast.Import, ast.ImportFrom)):
            names.update(
                alias.asname or alias.name.split(".", 1)[0] for alias in statement.names
            )
        for name in names & forbidden_hooks:
            violations.append(
                f"{_display(path, statement)} dynamic module surface hook {name}"
            )
    return violations


def _annotation_imports(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """Return retained annotation names and their canonical import bindings."""

    imported: dict[str, tuple[str, str]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            owner = statement.module or ""
            if statement.level == 1:
                owner = "app.execution_core" + (f".{owner}" if owner else "")
            for alias in statement.names:
                imported[alias.asname or alias.name] = (owner, alias.name)
        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                retained = alias.asname or alias.name.split(".", 1)[0]
                imported[retained] = (alias.name, "")
    return imported


def _top_level_annotation_aliases(tree: ast.Module) -> dict[str, ast.AST]:
    """Resolve simple module aliases used by deferred field annotations."""

    aliases: dict[str, ast.AST] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.value is not None
        ):
            aliases[statement.target.id] = statement.value
    return aliases


def _class_annotation_aliases(declaration: ast.ClassDef) -> dict[str, ast.AST]:
    """Return simple aliases declared in one reachable class namespace."""

    aliases: dict[str, ast.AST] = {}
    for statement in declaration.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.value is not None
        ):
            aliases[statement.target.id] = statement.value
    return aliases


def _annotation_assignment_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.List, ast.Tuple)):
        return {
            name
            for element in target.elts
            for name in _annotation_assignment_names(element)
        }
    return set()


def _unsafe_annotation_aliases(statements: list[ast.stmt]) -> frozenset[str]:
    """Find aliases introduced through conditional or structured assignment."""

    unsafe: set[str] = set()
    for statement in statements:
        if isinstance(statement, ast.Assign):
            if not (
                len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
            ):
                unsafe.update(
                    name
                    for target in statement.targets
                    for name in _annotation_assignment_names(target)
                )
            continue
        if isinstance(statement, ast.AnnAssign):
            if not isinstance(statement.target, ast.Name):
                unsafe.update(_annotation_assignment_names(statement.target))
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        pending = [statement]
        while pending:
            node = pending.pop()
            if node is not statement and isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                unsafe.add(node.id)
            pending.extend(ast.iter_child_nodes(node))
    return frozenset(unsafe)


def _local_annotation_classes(tree: ast.Module) -> dict[str, tuple[ast.ClassDef, ...]]:
    """Index module and lexically nested classes without entering functions."""

    found: dict[str, list[ast.ClassDef]] = {}

    def collect(statements: list[ast.stmt]) -> None:
        for statement in statements:
            if not isinstance(statement, ast.ClassDef):
                continue
            found.setdefault(statement.name, []).append(statement)
            collect(statement.body)

    collect(tree.body)
    return {name: tuple(declarations) for name, declarations in found.items()}


def _annotation_terminal_name(
    node: ast.AST,
    imported: dict[str, tuple[str, str]],
) -> str | None:
    if isinstance(node, ast.Name):
        binding = imported.get(node.id)
        return node.id if binding is None else binding[1].rsplit(".", 1)[-1]
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _annotation_slice_elements(node: ast.AST) -> tuple[ast.AST, ...]:
    return tuple(node.elts) if isinstance(node, ast.Tuple) else (node,)


def _protection_bounded_market_state_violations(
    tree: ast.Module,
    path: Path,
) -> list[str]:
    """Reject reachable protection history stores and variable-cardinality state."""

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "_PersistentKeyMap":
            violations.append(
                f"{_display(path, node)} protection owns forbidden _PersistentKeyMap"
            )
        elif isinstance(node, ast.ImportFrom) and any(
            alias.name == "_PersistentKeyMap" for alias in node.names
        ):
            violations.append(
                f"{_display(path, node)} protection imports forbidden _PersistentKeyMap"
            )

    aliases = _top_level_annotation_aliases(tree)
    unsafe_aliases = _unsafe_annotation_aliases(tree.body)
    imported = _annotation_imports(tree)
    local_classes = _local_annotation_classes(tree)
    class_aliases = {
        declaration: _class_annotation_aliases(declaration)
        for declarations in local_classes.values()
        for declaration in declarations
    }
    class_unsafe_aliases = {
        declaration: _unsafe_annotation_aliases(declaration.body)
        for declarations in local_classes.values()
        for declaration in declarations
    }
    state_classes = local_classes.get("PositionProtectionState", ())
    if len(state_classes) != 1:
        violations.append(
            f"{_display(path, tree)} expected one PositionProtectionState declaration"
        )
        return violations

    completed_classes: set[str] = set()
    safe_terminals = {"bool", "bytes", "int", "str"}
    opaque_terminals = {"object", "type"}

    def report(owner: str, node: ast.AST, detail: str) -> None:
        violations.append(
            f"{_display(path, node)} variable-cardinality protection field "
            f"{owner}: {detail}"
        )

    def inspect_class(
        class_name: str,
        owner: str,
        active_aliases: frozenset[tuple[ast.ClassDef | None, str]],
        active_classes: frozenset[str],
    ) -> None:
        declarations = local_classes.get(class_name, ())
        if not declarations:
            return
        if len(declarations) != 1:
            violations.append(
                f"{_display(path, declarations[0])} ambiguous reachable protection "
                f"state type {class_name}"
            )
            return
        if class_name in active_classes:
            violations.append(
                f"{_display(path, declarations[0])} recursive reachable protection "
                f"state type {class_name} from {owner}"
            )
            return
        if class_name in completed_classes:
            return
        declaration = declarations[0]
        next_classes = active_classes | {class_name}
        for base in declaration.bases:
            inspect_annotation(
                base,
                f"{owner}.<base>",
                active_aliases,
                next_classes,
                None,
            )
        for statement in declaration.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            field = (
                statement.target.id
                if isinstance(statement.target, ast.Name)
                else "<dynamic>"
            )
            inspect_annotation(
                statement.annotation,
                f"{owner}.{field}",
                active_aliases,
                next_classes,
                declaration,
            )
        completed_classes.add(class_name)

    def inspect_reference(
        node: ast.AST,
        owner: str,
        active_aliases: frozenset[tuple[ast.ClassDef | None, str]],
        active_classes: frozenset[str],
        scope: ast.ClassDef | None,
    ) -> None:
        if not isinstance(node, ast.Name):
            return
        name = node.id
        scoped_aliases = class_aliases.get(scope, {}) if scope is not None else {}
        scoped_unsafe = (
            class_unsafe_aliases.get(scope, frozenset())
            if scope is not None
            else unsafe_aliases
        )
        if name in scoped_unsafe or (
            name not in scoped_aliases and name in unsafe_aliases
        ):
            violations.append(
                f"{_display(path, node)} unsafe protection annotation alias "
                f"{name} from {owner}"
            )
            return
        alias_scope: ast.ClassDef | None = None
        alias_value: ast.AST | None = None
        if name in scoped_aliases:
            alias_scope = scope
            alias_value = scoped_aliases[name]
        elif name in aliases:
            alias_value = aliases[name]
        if alias_value is not None:
            alias_key = (alias_scope, name)
            if alias_key in active_aliases:
                violations.append(
                    f"{_display(path, node)} recursive protection annotation alias "
                    f"{name} from {owner}"
                )
                return
            inspect_annotation(
                alias_value,
                owner,
                active_aliases | {alias_key},
                active_classes,
                alias_scope,
            )
        elif name in local_classes:
            inspect_class(name, owner, active_aliases, active_classes)
        elif name in safe_terminals:
            return
        elif name in opaque_terminals:
            violations.append(
                f"{_display(path, node)} unapproved opaque protection state "
                f"terminal {name} from {owner}"
            )
        elif name in imported:
            if imported[name] not in _PROTECTION_FIXED_STATE_LEAF_IMPORTS:
                violations.append(
                    f"{_display(path, node)} unapproved imported protection state "
                    f"type {name} from {owner}"
                )
        else:
            violations.append(
                f"{_display(path, node)} unresolved protection annotation name "
                f"{name} from {owner}"
            )

    def inspect_qualified_annotation(
        annotation: ast.Attribute,
        owner: str,
        active_aliases: frozenset[tuple[ast.ClassDef | None, str]],
        active_classes: frozenset[str],
    ) -> None:
        attribute_path = _static_attribute_path(annotation)
        if attribute_path is None or len(attribute_path) != 2:
            violations.append(
                f"{_display(path, annotation)} unresolved protection annotation path "
                f"for {owner}"
            )
            return
        class_name, member = attribute_path
        declarations = local_classes.get(class_name, ())
        if len(declarations) != 1:
            violations.append(
                f"{_display(path, annotation)} unresolved protection annotation path "
                f"{'.'.join(attribute_path)} from {owner}"
            )
            return
        declaration = declarations[0]
        if member in class_unsafe_aliases.get(declaration, frozenset()):
            violations.append(
                f"{_display(path, annotation)} unsafe protection annotation alias "
                f"{'.'.join(attribute_path)} from {owner}"
            )
            return
        alias_value = class_aliases.get(declaration, {}).get(member)
        if alias_value is not None:
            alias_key = (declaration, member)
            if alias_key in active_aliases:
                violations.append(
                    f"{_display(path, annotation)} recursive protection annotation "
                    f"alias {'.'.join(attribute_path)} from {owner}"
                )
                return
            inspect_annotation(
                alias_value,
                owner,
                active_aliases | {alias_key},
                active_classes,
                declaration,
            )
            return
        nested = [
            statement
            for statement in declaration.body
            if isinstance(statement, ast.ClassDef) and statement.name == member
        ]
        if len(nested) == 1:
            inspect_class(member, owner, active_aliases, active_classes)
            return
        violations.append(
            f"{_display(path, annotation)} unresolved protection annotation path "
            f"{'.'.join(attribute_path)} from {owner}"
        )

    def inspect_annotation(
        annotation: ast.AST,
        owner: str,
        active_aliases: frozenset[tuple[ast.ClassDef | None, str]],
        active_classes: frozenset[str],
        scope: ast.ClassDef | None,
    ) -> None:
        if isinstance(annotation, ast.Name):
            terminal = _annotation_terminal_name(annotation, imported)
            if terminal in _PROTECTION_VARIABLE_CARDINALITY_TYPES:
                report(owner, annotation, terminal)
                return
            if terminal in _PROTECTION_VARIADIC_TUPLE_TYPES:
                report(owner, annotation, f"unparameterized {terminal}")
                return
            inspect_reference(
                annotation,
                owner,
                active_aliases,
                active_classes,
                scope,
            )
            return
        if isinstance(annotation, ast.Attribute):
            terminal = _annotation_terminal_name(annotation, imported)
            if terminal in _PROTECTION_VARIABLE_CARDINALITY_TYPES:
                report(owner, annotation, terminal)
                return
            if terminal in _PROTECTION_VARIADIC_TUPLE_TYPES:
                report(owner, annotation, f"unparameterized {terminal}")
                return
            inspect_qualified_annotation(
                annotation,
                owner,
                active_aliases,
                active_classes,
            )
            return
        if isinstance(annotation, ast.Subscript):
            terminal = _annotation_terminal_name(annotation.value, imported)
            elements = _annotation_slice_elements(annotation.slice)
            if terminal in _PROTECTION_VARIABLE_CARDINALITY_TYPES:
                report(owner, annotation, terminal)
            elif terminal in _PROTECTION_VARIADIC_TUPLE_TYPES:
                if any(
                    isinstance(element, ast.Constant) and element.value is Ellipsis
                    for element in elements
                ):
                    report(owner, annotation, f"variadic {terminal}")
            else:
                if isinstance(annotation.value, ast.Name):
                    inspect_reference(
                        annotation.value,
                        owner,
                        active_aliases,
                        active_classes,
                        scope,
                    )
                elif isinstance(annotation.value, ast.Attribute):
                    inspect_qualified_annotation(
                        annotation.value,
                        owner,
                        active_aliases,
                        active_classes,
                    )
                else:
                    violations.append(
                        f"{_display(path, annotation.value)} unsupported reachable "
                        f"protection annotation base for {owner}"
                    )
            for element in elements:
                if not (
                    isinstance(element, ast.Constant) and element.value is Ellipsis
                ):
                    inspect_annotation(
                        element,
                        owner,
                        active_aliases,
                        active_classes,
                        scope,
                    )
            return
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            inspect_annotation(
                annotation.left,
                owner,
                active_aliases,
                active_classes,
                scope,
            )
            inspect_annotation(
                annotation.right,
                owner,
                active_aliases,
                active_classes,
                scope,
            )
            return
        if isinstance(annotation, ast.Tuple):
            for element in annotation.elts:
                inspect_annotation(
                    element,
                    owner,
                    active_aliases,
                    active_classes,
                    scope,
                )
            return
        if isinstance(annotation, ast.Constant):
            if annotation.value is None:
                return
            violations.append(
                f"{_display(path, annotation)} unsupported reachable protection "
                f"annotation for {owner}"
            )
            return
        violations.append(
            f"{_display(path, annotation)} unsupported reachable protection "
            f"annotation grammar for {owner}"
        )

    inspect_class(
        "PositionProtectionState",
        "PositionProtectionState",
        frozenset(),
        frozenset(),
    )
    return list(dict.fromkeys(violations))


def _function_body_nodes(function: ast.FunctionDef) -> tuple[ast.AST, ...]:
    """Walk one function body without entering nested callable declarations."""

    found: list[ast.AST] = []
    pending = list(reversed(function.body))
    while pending:
        node = pending.pop()
        found.append(node)
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        pending.extend(reversed(tuple(ast.iter_child_nodes(node))))
    return tuple(found)


def _assigned_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return {name for element in node.elts for name in _assigned_names(element)}
    return set()


def _expression_uses_names(node: ast.AST, names: set[str]) -> bool:
    return any(
        isinstance(candidate, ast.Name)
        and isinstance(candidate.ctx, ast.Load)
        and candidate.id in names
        for candidate in ast.walk(node)
    )


def _protection_market_constructor_shape_violations(
    declaration: ast.ClassDef,
    imported: dict[str, tuple[str, str]],
    shadowed: set[str],
    path: Path,
) -> list[str]:
    """Seal the only constructor shapes admitted into the market closure."""

    violations: list[str] = []
    class_name = declaration.name
    if declaration.bases:
        violations.append(
            f"{_display(path, declaration)} inherited constructor shape for {class_name}"
        )
    if declaration.keywords:
        violations.append(
            f"{_display(path, declaration)} metaclass or class keyword for {class_name}"
        )

    exact_dataclass = False
    if len(declaration.decorator_list) == 1:
        decorator = declaration.decorator_list[0]
        exact_dataclass = bool(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "_dataclass"
            and imported.get(decorator.func.id) == ("dataclasses", "dataclass")
            and decorator.func.id not in shadowed
            and not decorator.args
            and len(decorator.keywords) == 2
            and {keyword.arg for keyword in decorator.keywords} == {"frozen", "slots"}
            and all(
                isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                for keyword in decorator.keywords
            )
        )
    if declaration.decorator_list and not exact_dataclass:
        violations.append(
            f"{_display(path, declaration)} unapproved constructor decorator for "
            f"{class_name}"
        )

    lifecycle_names: set[str] = set()
    for statement in declaration.body:
        if isinstance(statement, ast.Expr) and isinstance(
            statement.value,
            ast.Constant,
        ):
            if type(statement.value.value) is str:
                continue
        if isinstance(statement, ast.Pass):
            continue
        if isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target,
            ast.Name,
        ):
            if statement.target.id in {"__init__", "__new__", "__post_init__"}:
                violations.append(
                    f"{_display(path, statement)} lifecycle assignment "
                    f"{class_name}.{statement.target.id}"
                )
            elif statement.simple != 1 or statement.value is not None:
                violations.append(
                    f"{_display(path, statement)} non-declarative constructor field "
                    f"for {class_name}"
                )
            elif not _supported_annotation_expression(statement.annotation):
                violations.append(
                    f"{_display(path, statement)} unsupported constructor field "
                    f"annotation for {class_name}"
                )
            continue
        if isinstance(statement, ast.FunctionDef):
            if statement.name == "__new__":
                violations.append(
                    f"{_display(path, statement)} direct __new__ constructor for "
                    f"{class_name}"
                )
                continue
            if statement.name not in {"__init__", "__post_init__"}:
                violations.append(
                    f"{_display(path, statement)} unapproved constructor method "
                    f"{class_name}.{statement.name}"
                )
                continue
            if statement.name in lifecycle_names:
                violations.append(
                    f"{_display(path, statement)} duplicate constructor lifecycle "
                    f"{class_name}.{statement.name}"
                )
            lifecycle_names.add(statement.name)
            if statement.decorator_list:
                violations.append(
                    f"{_display(path, statement)} decorated constructor lifecycle "
                    f"{class_name}.{statement.name}"
                )
            positional = statement.args.posonlyargs + statement.args.args
            annotations = [
                argument.annotation
                for argument in (
                    statement.args.posonlyargs
                    + statement.args.args
                    + statement.args.kwonlyargs
                )
                if argument.annotation is not None
            ]
            exact_lifecycle_signature = bool(
                positional
                and positional[0].arg == "self"
                and not statement.args.posonlyargs
                and statement.args.vararg is None
                and statement.args.kwarg is None
                and not statement.args.kwonlyargs
                and not statement.args.defaults
                and not statement.args.kw_defaults
                and statement.type_comment is None
                and (statement.name != "__post_init__" or len(positional) == 1)
                and all(
                    _supported_annotation_expression(annotation)
                    for annotation in annotations
                )
                and (
                    statement.returns is None
                    or _supported_annotation_expression(statement.returns)
                )
            )
            if not exact_lifecycle_signature:
                violations.append(
                    f"{_display(path, statement)} unapproved constructor lifecycle "
                    f"signature {class_name}.{statement.name}"
                )
            if any(
                isinstance(node, (ast.Global, ast.Nonlocal, ast.Yield, ast.YieldFrom))
                for node in _function_body_nodes(statement)
            ):
                violations.append(
                    f"{_display(path, statement)} unapproved constructor lifecycle "
                    f"control for {class_name}.{statement.name}"
                )
            continue
        if isinstance(statement, ast.Assign):
            targets = {
                name for target in statement.targets for name in _assigned_names(target)
            }
            lifecycle_targets = targets & {"__init__", "__new__", "__post_init__"}
            if lifecycle_targets:
                for name in sorted(lifecycle_targets):
                    violations.append(
                        f"{_display(path, statement)} lifecycle assignment "
                        f"{class_name}.{name}"
                    )
            else:
                violations.append(
                    f"{_display(path, statement)} non-field constructor binding for "
                    f"{class_name}"
                )
            continue
        violations.append(
            f"{_display(path, statement)} unapproved constructor body shape for "
            f"{class_name}"
        )
    return violations


def _protection_market_closure_violations(
    tree: ast.Module,
    path: Path,
) -> list[str]:
    """Prove both market roles and their private closure are bounded static code."""

    violations: list[str] = []
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    class_declarations = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    classes = set(class_declarations)
    missing_roots = _PROTECTION_MARKET_ROOTS - set(functions)
    if missing_roots:
        violations.append(
            f"{_display(path, tree)} missing market closure roots "
            f"{sorted(missing_roots)!r}"
        )

    imported: dict[str, tuple[str, str]] = {}
    for statement in tree.body:
        if not isinstance(statement, ast.ImportFrom) or statement.module is None:
            continue
        owner = statement.module
        if statement.level == 1:
            owner = f"app.execution_core.{owner}"
        for alias in statement.names:
            imported[alias.asname or alias.name] = (owner, alias.name)
    rebound = _protection_rebound_names(tree)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }

    def exact_sha_digest_call(node: ast.AST) -> bool:
        return bool(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"digest", "hexdigest"}
            and not node.args
            and not node.keywords
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Name)
            and node.func.value.func.id == "_sha256"
            and imported.get("_sha256") == ("hashlib", "sha256")
            and "_sha256" not in rebound
            and "_sha256" not in functions
            and "_sha256" not in classes
            and len(node.func.value.args) == 1
            and not node.func.value.keywords
        )

    def exact_sha_constructor_call(node: ast.AST) -> bool:
        attribute = parents.get(node)
        digest_call = parents.get(attribute) if attribute is not None else None
        return bool(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_sha256"
            and isinstance(attribute, ast.Attribute)
            and attribute.value is node
            and isinstance(digest_call, ast.Call)
            and digest_call.func is attribute
            and exact_sha_digest_call(digest_call)
        )

    constructor_lifecycles: dict[str, set[str]] = {
        name: set() for name in _PROTECTION_ALLOWED_MARKET_LOCAL_CONSTRUCTORS
    }
    lifecycle_functions: dict[str, ast.FunctionDef] = {}
    for class_name in sorted(_PROTECTION_ALLOWED_MARKET_LOCAL_CONSTRUCTORS):
        declaration = class_declarations.get(class_name)
        if declaration is None:
            continue
        violations.extend(
            _protection_market_constructor_shape_violations(
                declaration,
                imported,
                rebound | set(functions) | classes,
                path,
            )
        )
        for statement in declaration.body:
            if not (
                isinstance(statement, ast.FunctionDef)
                and statement.name in {"__init__", "__post_init__"}
            ):
                continue
            lifecycle_name = f"{class_name}.{statement.name}"
            lifecycle_functions[lifecycle_name] = statement
            constructor_lifecycles[class_name].add(lifecycle_name)

    callables = {**functions, **lifecycle_functions}
    bodies = {
        name: _function_body_nodes(function) for name, function in callables.items()
    }
    call_graph: dict[str, set[str]] = {}
    for name in callables:
        dependencies: set[str] = set()
        for node in bodies[name]:
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id in functions:
                dependencies.add(node.func.id)
            else:
                dependencies.update(constructor_lifecycles.get(node.func.id, set()))
        call_graph[name] = dependencies
    closure: set[str] = set()
    pending = list(sorted(_PROTECTION_MARKET_ROOTS & set(functions)))
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        closure.add(name)
        pending.extend(sorted(call_graph[name] - closure))

    visiting: set[str] = set()
    visited: set[str] = set()

    def reject_cycle(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            violations.append(
                f"{_display(path, callables[name])} recursive market closure at {name}"
            )
            return
        visiting.add(name)
        for dependency in sorted(call_graph[name] & closure):
            reject_cycle(dependency)
        visiting.remove(name)
        visited.add(name)

    for name in sorted(closure):
        reject_cycle(name)

    positional_parameters = {
        name: tuple(
            argument.arg for argument in function.args.posonlyargs + function.args.args
        )
        for name, function in callables.items()
    }
    tainted_parameters = {name: set() for name in closure}
    for root in _PROTECTION_MARKET_ROOTS & closure:
        if positional_parameters[root]:
            tainted_parameters[root].add(positional_parameters[root][0])

    tainted_locals = {name: set(values) for name, values in tainted_parameters.items()}
    changed = True
    while changed:
        changed = False
        for name in sorted(closure):
            local_taint = set(tainted_parameters[name])
            local_changed = True
            while local_changed:
                local_changed = False
                for node in bodies[name]:
                    value: ast.AST | None = None
                    targets: set[str] = set()
                    if isinstance(node, ast.Assign):
                        value = node.value
                        targets = {
                            assigned
                            for candidate in node.targets
                            for assigned in _assigned_names(candidate)
                        }
                    elif isinstance(node, ast.AnnAssign):
                        value = node.value
                        targets = _assigned_names(node.target)
                    elif isinstance(node, ast.NamedExpr):
                        value = node.value
                        targets = _assigned_names(node.target)
                    if (
                        value is not None
                        and _expression_uses_names(value, local_taint)
                        and not targets <= local_taint
                    ):
                        local_taint.update(targets)
                        local_changed = True
            if not local_taint <= tainted_locals[name]:
                tainted_locals[name].update(local_taint)
                changed = True

            for node in bodies[name]:
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                    continue
                callees: set[str]
                if node.func.id in functions:
                    callees = {node.func.id} & closure
                else:
                    callees = constructor_lifecycles.get(node.func.id, set()) & closure
                for callee in callees:
                    callee_parameters = positional_parameters[callee]
                    propagated: set[str] = set()
                    lifecycle = callee in lifecycle_functions
                    argument_parameters = (
                        callee_parameters[1:] if lifecycle else callee_parameters
                    )
                    tainted_argument = False
                    for index, argument in enumerate(node.args):
                        if not _expression_uses_names(argument, local_taint):
                            continue
                        tainted_argument = True
                        if index < len(argument_parameters):
                            propagated.add(argument_parameters[index])
                    for keyword in node.keywords:
                        if not _expression_uses_names(keyword.value, local_taint):
                            continue
                        tainted_argument = True
                        if keyword.arg in argument_parameters:
                            propagated.add(keyword.arg)
                    if lifecycle and tainted_argument and callee_parameters:
                        propagated.add(callee_parameters[0])
                    if not propagated <= tainted_parameters[callee]:
                        tainted_parameters[callee].update(propagated)
                        changed = True

    allowed_imported_calls = (
        _PROTECTION_ALLOWED_STDLIB_IMPORTED_CALLS
        | _PROTECTION_ALLOWED_INTERNAL_IMPORTED_CALLS
    )
    fixed_lifecycle_len_calls: set[ast.Call] = set()
    for lifecycle_name, function in lifecycle_functions.items():
        class_name = lifecycle_name.split(".", 1)[0]
        declaration = class_declarations[class_name]
        fixed_fields = {
            statement.target.id
            for statement in declaration.body
            if isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and isinstance(statement.annotation, ast.Name)
            and statement.annotation.id in {"bytes", "str"}
        }
        for node in bodies[lifecycle_name]:
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "len"
                and len(node.args) == 1
                and not node.keywords
                and isinstance(node.args[0], ast.Attribute)
                and isinstance(node.args[0].value, ast.Name)
                and function.args.args
                and node.args[0].value.id == function.args.args[0].arg
                and node.args[0].attr in fixed_fields
            ):
                continue
            fixed_lifecycle_len_calls.add(node)
    loop_nodes = (ast.For, ast.AsyncFor, ast.While)
    comprehension_nodes = (
        ast.DictComp,
        ast.GeneratorExp,
        ast.ListComp,
        ast.SetComp,
    )
    for name in sorted(closure):
        local_taint = tainted_locals[name]
        for node in bodies[name]:
            if isinstance(node, loop_nodes):
                violations.append(
                    f"{_display(path, node)} loop in market closure {name}"
                )
            elif isinstance(node, comprehension_nodes):
                violations.append(
                    f"{_display(path, node)} comprehension in market closure {name}"
                )
            elif isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            ):
                violations.append(
                    f"{_display(path, node)} nested dynamic binding in market closure {name}"
                )

            if isinstance(node, ast.Compare):
                for operator, comparator in zip(
                    node.ops,
                    node.comparators,
                    strict=True,
                ):
                    if isinstance(
                        operator, (ast.In, ast.NotIn)
                    ) and _expression_uses_names(
                        comparator,
                        local_taint,
                    ):
                        violations.append(
                            f"{_display(path, node)} membership over state-derived value"
                        )

            if not isinstance(node, ast.Call):
                continue
            rendered = "<dynamic>"
            resolved = False
            if isinstance(node.func, ast.Name):
                rendered = node.func.id
                local_class = rendered in classes
                allowed_local_constructor = bool(
                    local_class
                    and rendered in _PROTECTION_ALLOWED_MARKET_LOCAL_CONSTRUCTORS
                )
                imported_call = imported.get(rendered)
                imported_call_is_allowed = bool(
                    imported_call in allowed_imported_calls
                    and (
                        imported_call != ("hashlib", "sha256")
                        or exact_sha_constructor_call(node)
                    )
                )
                resolved = bool(
                    rendered in functions
                    or allowed_local_constructor
                    or imported_call_is_allowed
                    or rendered in {"TypeError", "ValueError", "len", "type"}
                )
                if local_class and not allowed_local_constructor:
                    violations.append(
                        f"{_display(path, node)} local class construction in market "
                        f"closure {rendered}"
                    )
                    resolved = True
            elif isinstance(node.func, ast.Attribute):
                attribute_path = _static_attribute_path(node.func)
                rendered = (
                    ".".join(attribute_path)
                    if attribute_path is not None
                    else f"<dynamic>.{node.func.attr}"
                )
                resolved = bool(
                    attribute_path in _PROTECTION_ALLOWED_ATTRIBUTE_CALLS
                    or exact_sha_digest_call(node)
                )

            lowered = rendered.lower()
            if any(
                fragment in lowered for fragment in _PROTECTION_HISTORY_NAME_FRAGMENTS
            ):
                violations.append(
                    f"{_display(path, node)} history helper in market closure {rendered}"
                )
            if not resolved:
                violations.append(
                    f"{_display(path, node)} unresolved call in market closure {rendered}"
                )
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "len"
                and node.args
                and node not in fixed_lifecycle_len_calls
                and _expression_uses_names(node.args[0], local_taint)
            ):
                violations.append(
                    f"{_display(path, node)} len over state-derived value"
                )
            if (
                isinstance(node.func, ast.Name)
                and node.func.id
                in {
                    "all",
                    "any",
                    "dict",
                    "frozenset",
                    "iter",
                    "list",
                    "max",
                    "min",
                    "set",
                    "sorted",
                    "sum",
                    "tuple",
                }
                and node.args
                and _expression_uses_names(node.args[0], local_taint)
            ):
                violations.append(
                    f"{_display(path, node)} iteration over state-derived value"
                )
            packer_name = rendered.rsplit(".", 1)[-1]
            if packer_name in {"_commit_parts", "_pack_parts"} and (
                any(isinstance(argument, ast.Starred) for argument in node.args)
                or any(keyword.arg is None for keyword in node.keywords)
            ):
                violations.append(
                    f"{_display(path, node)} dynamically sized packer arguments"
                )
    return violations


def test_protection_adr023_market_state_is_constant_cardinality() -> None:
    """The protection semantic center owns no replay history or growing container."""

    path = _PACKAGE_ROOT / "protection.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = _protection_bounded_market_state_violations(tree, path)
    assert not violations, "unbounded protection market state:\n" + "\n".join(
        violations
    )


def test_protection_adr023_market_closure_is_static_and_bounded() -> None:
    """Both market roles and every reachable private helper have bounded work."""

    path = _PACKAGE_ROOT / "protection.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = _protection_market_closure_violations(tree, path)
    assert not violations, "unbounded protection market closure:\n" + "\n".join(
        violations
    )


def test_adr023_public_transition_contract_oracle_is_failure_capable() -> None:
    """Cross-shaped calls and caller-authored recovery surfaces fail the pin."""

    path = _PACKAGE_ROOT / "synthetic_protection_public_contract.py"

    def source_with(overrides: dict[str, tuple[str, ...]], extra: str = "") -> str:
        lines: list[str] = []
        for name, expected in _PROTECTION_PUBLIC_TRANSITIONS.items():
            parameters = overrides.get(name, expected)
            lines.append(f"def {name}({', '.join(parameters)}):\n    return None\n")
        lines.append(extra)
        return "".join(lines)

    accepted = ast.parse(source_with({}))
    assert _protection_public_transition_violations(accepted, path) == []

    mutants = {
        "projection reducer accepts market input": source_with(
            {"reduce_position_protection": ("state", "projection", "occurrence")}
        ),
        "market reducer omits occurrence": source_with(
            {"reduce_position_protection_market": ("state", "projection")}
        ),
        "invalidation accepts caller evidence": source_with(
            {
                "invalidate_position_protection_market": (
                    "state",
                    "projection",
                    "occurrence",
                )
            }
        ),
        "caller recovery role": source_with(
            {},
            "def recover_position_protection_market(state, baseline):\n"
            "    return None\n",
        ),
    }
    for label, source in mutants.items():
        assert _protection_public_transition_violations(ast.parse(source), path), label


def test_adr023_all_five_public_roles_are_independent() -> None:
    """No public transition can delegate authority to another public transition."""

    path = _PACKAGE_ROOT / "synthetic_protection_public_roles.py"
    for caller in sorted(_PROTECTION_PUBLIC_TRANSITIONS):
        for callee in sorted(set(_PROTECTION_PUBLIC_TRANSITIONS) - {caller}):
            for indirect in (False, True):
                functions: list[str] = []
                arguments = ", ".join(
                    "None" for _ in _PROTECTION_PUBLIC_TRANSITIONS[callee]
                )
                if indirect:
                    functions.append(
                        f"def _private_bridge():\n    return {callee}({arguments})\n"
                    )
                for name, parameters in _PROTECTION_PUBLIC_TRANSITIONS.items():
                    body = "    return None\n"
                    if name == caller:
                        body = (
                            "    return _private_bridge()\n"
                            if indirect
                            else f"    return {callee}({arguments})\n"
                        )
                    functions.append(f"def {name}({', '.join(parameters)}):\n{body}")
                violations = _protection_call_binding_violations(
                    ast.parse("".join(functions)),
                    path,
                )
                expected = f"public role {caller} delegates to public role {callee}"
                assert sum(expected in item for item in violations) == 1


def test_adr023_bounded_state_oracle_is_failure_capable() -> None:
    """History maps and every variable-cardinality field shape are rejected."""

    path = _PACKAGE_ROOT / "synthetic_protection_state.py"
    accepted = ast.parse(
        "from enum import Enum as _Enum\n"
        "from fractions import Fraction as _Fraction\n"
        "from .fills import PositionScope as _PositionScope\n"
        "from .identity import MandateId as _MandateId\n"
        "from .identity import MarketDataSourceId as _MarketDataSourceId\n"
        "from .identity import MarketOccurrenceId as _MarketOccurrenceId\n"
        "from .identity import MarketStreamGenerationId as "
        "_MarketStreamGenerationId\n"
        "from .identity import SessionId as _SessionId\n"
        "from .values import Quantity as _Quantity\n"
        "from .values import ReportedPrice as _ReportedPrice\n"
        "from .values import TickMetadata as _TickMetadata\n"
        "_FixedEvidence = tuple[bytes, bytes]\n"
        "class _Policy(_Enum):\n"
        "    READY = 'READY'\n"
        "class _Mandate:\n"
        "    mandate_id: _MandateId\n"
        "    source_id: _MarketDataSourceId\n"
        "    stream_generation: _MarketStreamGenerationId\n"
        "    session_id: _SessionId\n"
        "    position_scope: _PositionScope\n"
        "    fraction: _Fraction\n"
        "    maximum_quantity: _Quantity\n"
        "    price: _ReportedPrice | None\n"
        "    tick: _TickMetadata\n"
        "class _FixedTypes:\n"
        "    Pair = tuple[bytes, bytes]\n"
        "class _EvidenceWindow:\n"
        "    Alias = _FixedEvidence\n"
        "    identity: bytes\n"
        "    pair: Alias\n"
        "class PositionProtectionState:\n"
        "    current_identity: bytes\n"
        "    evidence_pair: tuple[bytes, bytes]\n"
        "    evidence_window: _EvidenceWindow\n"
        "    qualified_pair: _FixedTypes.Pair\n"
        "    policy: _Policy\n"
        "    mandate: _Mandate\n"
        "    occurrence_id: _MarketOccurrenceId\n"
    )
    assert _protection_bounded_market_state_violations(accepted, path) == []

    mutants = {
        "persistent receipt map": (
            "from .fills import _PersistentKeyMap\n"
            "class PositionProtectionState:\n"
            "    receipts: _PersistentKeyMap\n"
        ),
        "dictionary history": (
            "class PositionProtectionState:\n    history: dict[bytes, bytes]\n"
        ),
        "variadic tuple history": (
            "class PositionProtectionState:\n    history: tuple[bytes, ...]\n"
        ),
        "aliased dictionary history": (
            "_Cache = dict[bytes, bytes]\n"
            "class PositionProtectionState:\n"
            "    cache: _Cache\n"
        ),
        "chained aliased list history": (
            "_Rows = list[bytes]\n"
            "_History = _Rows\n"
            "class PositionProtectionState:\n"
            "    history: _History\n"
        ),
        "reachable nested variadic history": (
            "class _History:\n"
            "    entries: tuple[bytes, ...]\n"
            "class PositionProtectionState:\n"
            "    history: _History\n"
        ),
        "lexically nested variadic history": (
            "class PositionProtectionState:\n"
            "    class _History:\n"
            "        entries: tuple[bytes, ...]\n"
            "    history: _History\n"
        ),
        "import-aliased variable collection": (
            "from typing import Mapping as _Cache\n"
            "class PositionProtectionState:\n"
            "    cache: _Cache[bytes, bytes]\n"
        ),
        "class alias reaches nested list history": (
            "class PositionProtectionState:\n"
            "    class _History:\n"
            "        entries: list[bytes]\n"
            "    Alias = _History\n"
            "    history: Alias\n"
        ),
        "class alias reaches recursive node": (
            "class _Node:\n"
            "    Alias = _Node\n"
            "    next: Alias\n"
            "class PositionProtectionState:\n"
            "    node: _Node\n"
        ),
        "class alias cycle": (
            "class _History:\n"
            "    First = Second\n"
            "    Second = First\n"
            "    entries: First\n"
            "class PositionProtectionState:\n"
            "    history: _History\n"
        ),
        "unresolved annotation name": (
            "class PositionProtectionState:\n    value: Missing\n"
        ),
        "unresolved annotation path": (
            "class Types:\n"
            "    pass\n"
            "class PositionProtectionState:\n"
            "    value: Types.Missing\n"
        ),
        "qualified class alias laundering": (
            "class Types:\n"
            "    Cache = list[bytes]\n"
            "class PositionProtectionState:\n"
            "    cache: Types.Cache\n"
        ),
        "qualified subscript alias laundering": (
            "class Types:\n"
            "    Cache = list\n"
            "class PositionProtectionState:\n"
            "    cache: Types.Cache[bytes]\n"
        ),
        "structured annotation alias": (
            "_Cache, _Other = (list[bytes], bytes)\n"
            "class PositionProtectionState:\n"
            "    cache: _Cache\n"
        ),
        "conditional annotation alias": (
            "if flag:\n"
            "    _Cache = list[bytes]\n"
            "class PositionProtectionState:\n"
            "    cache: _Cache\n"
        ),
        "opaque object state": (
            "class PositionProtectionState:\n    history: object\n"
        ),
        "opaque type state": (
            "class PositionProtectionState:\n    history_type: type\n"
        ),
        "imported venue recovery transition": (
            "from .venue import VenueRecoveryTransition as "
            "_VenueRecoveryTransition\n"
            "class PositionProtectionState:\n"
            "    recovery: _VenueRecoveryTransition\n"
        ),
        "aliased imported venue recovery transition": (
            "from .venue import VenueRecoveryTransition as _RecoveryBook\n"
            "class PositionProtectionState:\n"
            "    recovery: _RecoveryBook\n"
        ),
    }
    exact_findings = {
        "class alias reaches nested list history": (
            "PositionProtectionState.history.entries: list"
        ),
        "class alias reaches recursive node": (
            "recursive reachable protection state type _Node"
        ),
        "class alias cycle": "recursive protection annotation alias First",
        "unresolved annotation name": "unresolved protection annotation name Missing",
        "unresolved annotation path": "unresolved protection annotation path Types.Missing",
        "qualified class alias laundering": ("PositionProtectionState.cache: list"),
        "qualified subscript alias laundering": ("PositionProtectionState.cache: list"),
        "structured annotation alias": "unsafe protection annotation alias _Cache",
        "conditional annotation alias": "unsafe protection annotation alias _Cache",
        "opaque object state": "unapproved opaque protection state terminal object",
        "opaque type state": "unapproved opaque protection state terminal type",
        "imported venue recovery transition": (
            "unapproved imported protection state type _VenueRecoveryTransition"
        ),
        "aliased imported venue recovery transition": (
            "unapproved imported protection state type _RecoveryBook"
        ),
    }
    for label, source in mutants.items():
        violations = _protection_bounded_market_state_violations(
            ast.parse(source),
            path,
        )
        assert violations, label
        if label in exact_findings:
            assert sum(exact_findings[label] in item for item in violations) == 1, label


def test_adr023_market_closure_oracle_is_failure_capable() -> None:
    """Every prohibited unbounded or indirect closure shape kills its mutant."""

    path = _PACKAGE_ROOT / "synthetic_protection_market_closure.py"
    accepted = ast.parse(
        "from .fills import _pack_parts\n"
        "from .venue import _extract_protection_transition\n"
        "def _cursor(state, value):\n"
        "    return _pack_parts(b'domain', state.commitment, value)\n"
        "def _unrelated_venue_helper(values):\n"
        "    for value in values:\n"
        "        pass\n"
        "def project_protection_venue(transition, mandate):\n"
        "    return _extract_protection_transition(transition)\n"
        "def reduce_position_protection_market(state, projection, occurrence):\n"
        "    return _cursor(state, occurrence.identity)\n"
        "def invalidate_position_protection_market(state, projection):\n"
        "    return _cursor(state, b'invalidate')\n"
    )
    assert _protection_market_closure_violations(accepted, path) == []

    accepted_direct_constructor = ast.parse(
        "class ProtectionTransition:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "def _helper(value):\n"
        "    return ProtectionTransition(value)\n"
        "def reduce_position_protection_market(state, projection, occurrence):\n"
        "    return _helper(state)\n"
        "def invalidate_position_protection_market(state, projection):\n"
        "    return _helper(state)\n"
    )
    assert (
        _protection_market_closure_violations(accepted_direct_constructor, path) == []
    )

    accepted_dataclass_constructor = ast.parse(
        "from dataclasses import dataclass as _dataclass\n"
        "@_dataclass(frozen=True, slots=True)\n"
        "class ExecutionGoal:\n"
        "    value: bytes\n"
        "    def __post_init__(self):\n"
        "        pass\n"
        "def _helper(value):\n"
        "    return ExecutionGoal(value)\n"
        "def reduce_position_protection_market(state, projection, occurrence):\n"
        "    return _helper(state)\n"
        "def invalidate_position_protection_market(state, projection):\n"
        "    return _helper(state)\n"
    )
    assert (
        _protection_market_closure_violations(accepted_dataclass_constructor, path)
        == []
    )

    accepted_hash_digest = ast.parse(
        "from hashlib import sha256 as _sha256\n"
        "def _helper(value):\n"
        "    return _sha256(value).digest()\n"
        "def reduce_position_protection_market(state, projection, occurrence):\n"
        "    return _helper(state.commitment)\n"
        "def invalidate_position_protection_market(state, projection):\n"
        "    return _helper(state.commitment)\n"
    )
    assert _protection_market_closure_violations(accepted_hash_digest, path) == []

    def wrapped(helper: str) -> str:
        return (
            "from .fills import _pack_parts\n"
            f"{helper}"
            "def reduce_position_protection_market(state, projection, occurrence):\n"
            "    return _helper(state)\n"
            "def invalidate_position_protection_market(state, projection):\n"
            "    return _helper(state)\n"
        )

    mutants = {
        "loop": (
            wrapped(
                "def _helper(value):\n"
                "    for item in value.history:\n"
                "        return item\n"
                "    return None\n"
            ),
            "loop in market closure",
        ),
        "recursion": (
            wrapped("def _helper(value):\n    return _helper(value)\n"),
            "recursive market closure",
        ),
        "comprehension": (
            wrapped(
                "def _helper(value):\n"
                "    return tuple(item for item in value.history)\n"
            ),
            "comprehension in market closure",
        ),
        "dynamic callback": (
            wrapped("def _helper(value):\n    return callback(value)\n"),
            "unresolved call in market closure callback",
        ),
        "history helper": (
            (
                "def _read_history(value):\n"
                "    return value\n"
                "def _helper(value):\n"
                "    return _read_history(value)\n"
                "def reduce_position_protection_market(state, projection, occurrence):\n"
                "    return _helper(state)\n"
                "def invalidate_position_protection_market(state, projection):\n"
                "    return _helper(state)\n"
            ),
            "history helper in market closure _read_history",
        ),
        "state-derived iteration": (
            wrapped(
                "def _helper(value):\n"
                "    retained = value.receipts\n"
                "    return tuple(retained)\n"
            ),
            "iteration over state-derived value",
        ),
        "state-derived len": (
            wrapped(
                "def _helper(value):\n"
                "    retained = value.receipts\n"
                "    return len(retained)\n"
            ),
            "len over state-derived value",
        ),
        "state-derived membership": (
            wrapped(
                "def _helper(value):\n"
                "    retained = value.receipts\n"
                "    return b'key' in retained\n"
            ),
            "membership over state-derived value",
        ),
        "starred packer": (
            wrapped(
                "def _helper(value):\n    return _pack_parts(b'domain', *value.parts)\n"
            ),
            "dynamically sized packer arguments",
        ),
        "dynamic attribute call": (
            wrapped("def _helper(value):\n    return value.callback()\n"),
            "unresolved call in market closure value.callback",
        ),
        "raw hash result": (
            wrapped(
                "from hashlib import sha256 as _sha256\n"
                "def _helper(value):\n"
                "    return _sha256(value)\n"
            ),
            "unresolved call in market closure _sha256",
        ),
        "local class constructor": (
            wrapped(
                "class _Scanner:\n"
                "    def __init__(self, value):\n"
                "        for item in value.history:\n"
                "            self.last = item\n"
                "def _helper(value):\n"
                "    return _Scanner(value)\n"
            ),
            "local class construction in market closure _Scanner",
        ),
        "laundered class constructor": (
            wrapped(
                "class _Scanner:\n"
                "    pass\n"
                "_Build = _Scanner\n"
                "def _helper(value):\n"
                "    return _Build(value)\n"
            ),
            "unresolved call in market closure _Build",
        ),
        "allowed constructor init loop": (
            wrapped(
                "class ProtectionTransition:\n"
                "    def __init__(self, value):\n"
                "        for item in value.history:\n"
                "            self.last = item\n"
                "def _helper(value):\n"
                "    return ProtectionTransition(value)\n"
            ),
            "loop in market closure ProtectionTransition.__init__",
        ),
        "allowed constructor post-init loop": (
            wrapped(
                "class ExecutionGoal:\n"
                "    value: object\n"
                "    def __post_init__(self):\n"
                "        for item in self.value.history:\n"
                "            self.last = item\n"
                "def _helper(value):\n"
                "    return ExecutionGoal(value)\n"
            ),
            "loop in market closure ExecutionGoal.__post_init__",
        ),
        "allowed constructor state-derived len": (
            wrapped(
                "class ProtectionTransition:\n"
                "    def __init__(self, value):\n"
                "        self.size = len(value.history)\n"
                "def _helper(value):\n"
                "    return ProtectionTransition(value)\n"
            ),
            "len over state-derived value",
        ),
        "allowed constructor direct new": (
            wrapped(
                "class ProtectionTransition:\n"
                "    def __new__(cls, value):\n"
                "        return object.__new__(cls)\n"
                "def _helper(value):\n"
                "    return ProtectionTransition(value)\n"
            ),
            "direct __new__ constructor for ProtectionTransition",
        ),
        "allowed constructor inherited init": (
            wrapped(
                "class _Base:\n"
                "    def __init__(self, value):\n"
                "        self.value = value\n"
                "class ProtectionTransition(_Base):\n"
                "    pass\n"
                "def _helper(value):\n"
                "    return ProtectionTransition(value)\n"
            ),
            "inherited constructor shape for ProtectionTransition",
        ),
        "allowed constructor assigned init": (
            wrapped(
                "def _build(self, value):\n"
                "    self.value = value\n"
                "class ProtectionTransition:\n"
                "    __init__ = _build\n"
                "def _helper(value):\n"
                "    return ProtectionTransition(value)\n"
            ),
            "lifecycle assignment ProtectionTransition.__init__",
        ),
        "allowed constructor metaclass": (
            wrapped(
                "class _Meta(type):\n"
                "    pass\n"
                "class ProtectionTransition(metaclass=_Meta):\n"
                "    pass\n"
                "def _helper(value):\n"
                "    return ProtectionTransition(value)\n"
            ),
            "metaclass or class keyword for ProtectionTransition",
        ),
    }
    for label, (source, expected) in mutants.items():
        violations = _protection_market_closure_violations(ast.parse(source), path)
        assert sum(expected in item for item in violations) == 1, label


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


def _protection_rebound_names(tree: ast.AST) -> set[str]:
    """Collect every non-declaration binding form represented by Python 3.11 AST."""

    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    names.update(
        argument.arg for argument in ast.walk(tree) if isinstance(argument, ast.arg)
    )
    names.update(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and node.name is not None
    )
    names.update(
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name is not None
    )
    names.update(
        node.rest
        for node in ast.walk(tree)
        if isinstance(node, ast.MatchMapping) and node.rest is not None
    )
    return names


def _protection_state_commitment_binding_violations(
    tree: ast.AST,
    path: Path,
) -> list[str]:
    """Pin the four bindings that form the protection state commitment path."""

    if not isinstance(tree, ast.Module):
        return [f"{_display(path, tree)} protection source is not a module"]
    violations: list[str] = []
    protected = {
        "_commit_parts",
        "_protection_market_cursor_preimage",
        "_sha256",
        "_state_commitment",
    }
    import_bindings: dict[str, list[tuple[object, ...]]] = {
        name: [] for name in protected
    }
    top_level = set(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                retained = alias.asname or alias.name
                if retained in import_bindings:
                    import_bindings[retained].append(
                        (
                            node in top_level,
                            "from",
                            node.level,
                            node.module,
                            alias.name,
                            alias.asname,
                        )
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                retained = alias.asname or alias.name.split(".", 1)[0]
                if retained in import_bindings:
                    import_bindings[retained].append(
                        (
                            node in top_level,
                            "import",
                            alias.name,
                            alias.asname,
                        )
                    )

    expected_imports = {
        "_commit_parts": [(True, "from", 1, "fills", "_commit_parts", None)],
        "_sha256": [(True, "from", 0, "hashlib", "sha256", "_sha256")],
    }
    for name, expected in expected_imports.items():
        if import_bindings[name] != expected:
            violations.append(
                f"{_display(path, tree)} expected one exact commitment import {name}"
            )
    for name in {"_protection_market_cursor_preimage", "_state_commitment"}:
        if import_bindings[name]:
            violations.append(
                f"{_display(path, tree)} commitment helper imported as {name}"
            )

    declarations: dict[str, list[tuple[type[ast.AST], bool]]] = {
        name: [] for name in protected
    }
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in declarations:
                declarations[node.name].append((type(node), node in top_level))
    for name in {"_commit_parts", "_sha256"}:
        if declarations[name]:
            violations.append(
                f"{_display(path, tree)} commitment import shadowed by declaration {name}"
            )
    for name in {"_protection_market_cursor_preimage", "_state_commitment"}:
        if declarations[name] != [(ast.FunctionDef, True)]:
            violations.append(
                f"{_display(path, tree)} expected one exact commitment function {name}"
            )

    for name in sorted(protected & _protection_rebound_names(tree)):
        violations.append(
            f"{_display(path, tree)} rebound protected commitment binding {name}"
        )
    return violations


def _immutable_literal_expression(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return node.value is None or type(node.value) in {bool, bytes, int, str}
    if isinstance(node, ast.Tuple):
        return all(_immutable_literal_expression(item) for item in node.elts)
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    )


def _annotation_syntax_roots(tree: ast.AST) -> tuple[ast.AST, ...]:
    roots: list[ast.AST] = []
    for candidate in ast.walk(tree):
        candidate_roots: tuple[ast.AST | None, ...] = ()
        if isinstance(candidate, ast.arg):
            candidate_roots = (candidate.annotation,)
        elif isinstance(candidate, ast.AnnAssign):
            candidate_roots = (candidate.annotation,)
        elif isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)):
            candidate_roots = (candidate.returns,)
        for root in candidate_roots:
            if root is not None:
                roots.append(root)
    return tuple(roots)


def _annotation_syntax_nodes(tree: ast.AST) -> set[ast.AST]:
    nodes: set[ast.AST] = set()
    for root in _annotation_syntax_roots(tree):
        nodes.update(ast.walk(root))
    return nodes


def _supported_annotation_expression(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return isinstance(node.ctx, ast.Load)
    if isinstance(node, ast.Constant):
        return node.value is None
    if isinstance(node, ast.BinOp):
        return (
            isinstance(node.op, ast.BitOr)
            and _supported_annotation_expression(node.left)
            and _supported_annotation_expression(node.right)
        )
    if not (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and isinstance(node.value.ctx, ast.Load)
        and node.value.id in {"frozenset", "tuple", "type"}
    ):
        return False
    if node.value.id != "tuple":
        return not isinstance(
            node.slice, ast.Tuple
        ) and _supported_annotation_expression(node.slice)
    if not isinstance(node.slice, ast.Tuple):
        return False
    elements = node.slice.elts
    if not elements:
        return False
    if isinstance(elements[-1], ast.Constant) and elements[-1].value is Ellipsis:
        return len(elements) == 2 and _supported_annotation_expression(elements[0])
    return len(elements) >= 2 and all(
        _supported_annotation_expression(element) for element in elements
    )


def _protection_write_effect_violations(
    tree: ast.Module,
    path: Path,
    *,
    require_complete: bool = False,
) -> list[str]:
    """Reject retained state and authenticate the two opaque constructors."""

    violations: list[str] = []
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    annotation_nodes = _annotation_syntax_nodes(tree)
    rebound = _protection_rebound_names(tree)

    module_declarations: dict[str, list[ast.AST]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_declarations.setdefault(node.name, []).append(node)
    for name, declarations in module_declarations.items():
        if len(declarations) != 1:
            for declaration in declarations[1:]:
                violations.append(
                    f"{_display(path, declaration)} ambiguous module declaration {name}"
                )

    def declarative_assignment_value(node: ast.AST | None) -> bool:
        return node is None or _immutable_literal_expression(node)

    for owner in (
        tree,
        *(node for node in tree.body if isinstance(node, ast.ClassDef)),
    ):
        for statement in owner.body:
            if isinstance(statement, ast.Assign):
                if not all(
                    isinstance(target, ast.Name) for target in statement.targets
                ):
                    violations.append(
                        f"{_display(path, statement)} non-declarative retained binding"
                    )
                if not declarative_assignment_value(statement.value):
                    violations.append(
                        f"{_display(path, statement)} mutable retained binding"
                    )
            elif isinstance(statement, ast.AnnAssign):
                if not isinstance(statement.target, ast.Name):
                    violations.append(
                        f"{_display(path, statement)} non-declarative retained binding"
                    )
                if not declarative_assignment_value(statement.value):
                    violations.append(
                        f"{_display(path, statement)} mutable retained binding"
                    )
            elif isinstance(statement, ast.Expr) and (
                isinstance(statement.value, ast.Constant)
                and type(statement.value.value) is str
            ):
                continue
            elif isinstance(owner, ast.Module) and isinstance(
                statement,
                (ast.ClassDef, ast.FunctionDef, ast.Import, ast.ImportFrom),
            ):
                continue
            elif isinstance(owner, ast.ClassDef) and isinstance(
                statement,
                (ast.FunctionDef, ast.Pass),
            ):
                continue
            else:
                violations.append(
                    f"{_display(path, statement)} unapproved retained-scope statement"
                )

    def sealed_lifecycle_is_exact(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        owner: ast.ClassDef,
    ) -> bool:
        admitted_name = function.name == "__init_subclass__" or (
            owner.name in _PROTECTION_OPAQUE_VALUE_TYPES and function.name == "__init__"
        )
        positional = function.args.args[0] if len(function.args.args) == 1 else None
        vararg = function.args.vararg
        kwarg = function.args.kwarg
        exact_signature = bool(
            admitted_name
            and isinstance(function, ast.FunctionDef)
            and not function.decorator_list
            and function.type_comment is None
            and not function.args.posonlyargs
            and not function.args.kwonlyargs
            and positional is not None
            and positional.annotation is None
            and not function.args.defaults
            and not function.args.kw_defaults
            and kwarg is not None
            and kwarg.arg == "kwargs"
            and isinstance(kwarg.annotation, ast.Name)
            and kwarg.annotation.id == "object"
            and isinstance(function.returns, ast.Constant)
            and function.returns.value is None
            and (
                (
                    function.name == "__init__"
                    and positional.arg == "self"
                    and vararg is not None
                    and vararg.arg == "args"
                    and isinstance(vararg.annotation, ast.Name)
                    and vararg.annotation.id == "object"
                )
                or (
                    function.name == "__init_subclass__"
                    and positional.arg == "cls"
                    and vararg is None
                )
            )
        )
        statements = function.body
        if (
            statements
            and isinstance(statements[0], ast.Expr)
            and (
                isinstance(statements[0].value, ast.Constant)
                and type(statements[0].value.value) is str
            )
        ):
            statements = statements[1:]
        terminal = statements[0] if len(statements) == 1 else None
        exception = terminal.exc if isinstance(terminal, ast.Raise) else None
        return bool(
            exact_signature
            and isinstance(terminal, ast.Raise)
            and terminal.cause is None
            and isinstance(exception, ast.Call)
            and isinstance(exception.func, ast.Name)
            and exception.func.id == "TypeError"
            and len(exception.args) == 1
            and not exception.keywords
            and isinstance(exception.args[0], ast.Constant)
            and type(exception.args[0].value) is str
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            violations.append(f"{_display(path, node)} ambient binding mutation")
        elif isinstance(node, ast.NamedExpr):
            violations.append(f"{_display(path, node)} expression binding mutation")
        elif isinstance(node, ast.Lambda):
            violations.append(f"{_display(path, node)} retained lambda capability")
        elif node not in annotation_nodes and isinstance(
            node, (ast.List, ast.Set, ast.Dict)
        ):
            violations.append(f"{_display(path, node)} mutable container expression")
        elif node not in annotation_nodes and isinstance(node, ast.Starred):
            violations.append(f"{_display(path, node)} implicit unpacking dispatch")
        elif node not in annotation_nodes and isinstance(node, ast.Subscript):
            violations.append(f"{_display(path, node)} implicit subscription dispatch")
        elif (
            node not in annotation_nodes
            and isinstance(node, ast.Compare)
            and any(isinstance(operator, (ast.In, ast.NotIn)) for operator in node.ops)
        ):
            violations.append(f"{_display(path, node)} implicit membership dispatch")
        elif (
            node not in annotation_nodes
            and isinstance(node, ast.BinOp)
            and not isinstance(
                node.op,
                (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod),
            )
        ):
            violations.append(f"{_display(path, node)} unapproved arithmetic operator")
        elif (
            node not in annotation_nodes
            and isinstance(node, ast.UnaryOp)
            and not isinstance(node.op, (ast.UAdd, ast.USub, ast.Not))
        ):
            violations.append(f"{_display(path, node)} unapproved unary operator")
        elif isinstance(node, ast.AsyncFunctionDef):
            violations.append(
                f"{_display(path, node)} asynchronous function capability"
            )
        elif isinstance(
            node,
            (
                ast.Await,
                ast.Yield,
                ast.YieldFrom,
                ast.GeneratorExp,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
            ),
        ):
            violations.append(f"{_display(path, node)} suspended execution capability")
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            violations.append(f"{_display(path, node)} context-manager capability")
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            violations.append(
                f"{_display(path, node)} unbounded control-flow capability"
            )
        elif isinstance(node, (ast.Try, ast.TryStar, ast.Match)):
            violations.append(f"{_display(path, node)} unapproved control-flow grammar")
        elif isinstance(node, ast.Assert):
            violations.append(
                f"{_display(path, node)} optimization-sensitive assertion"
            )
        elif isinstance(node, ast.Raise):
            exception = node.exc
            if not (
                node.cause is None
                and isinstance(exception, ast.Call)
                and isinstance(exception.func, ast.Name)
                and exception.func.id in {"TypeError", "ValueError"}
                and len(exception.args) == 1
                and not exception.keywords
                and isinstance(exception.args[0], ast.Constant)
                and type(exception.args[0].value) is str
            ):
                violations.append(
                    f"{_display(path, node)} unapproved exception control flow"
                )
        elif isinstance(node, ast.Delete):
            violations.append(f"{_display(path, node)} deletion mutation")
        elif isinstance(node, ast.AugAssign):
            violations.append(f"{_display(path, node)} in-place mutation")
        elif isinstance(node, ast.Subscript) and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            violations.append(f"{_display(path, node)} mutable subscript binding")

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = parents.get(node)
            if not isinstance(parent, (ast.Module, ast.ClassDef)):
                violations.append(
                    f"{_display(path, node)} nested or conditional function binding"
                )
            class_lifecycle = isinstance(parent, ast.ClassDef) and (
                node.name == "__init_subclass__"
                or (
                    parent.name in _PROTECTION_OPAQUE_VALUE_TYPES
                    and node.name == "__init__"
                )
            )
            lifecycle_is_exact = bool(
                class_lifecycle
                and isinstance(parent, ast.ClassDef)
                and sealed_lifecycle_is_exact(node, parent)
            )
            if class_lifecycle and not lifecycle_is_exact:
                violations.append(
                    f"{_display(path, node)} sealed lifecycle is not exact"
                )
            elif not class_lifecycle and (
                node.args.posonlyargs
                or node.args.kwonlyargs
                or node.args.vararg is not None
                or node.args.kwarg is not None
            ):
                violations.append(
                    f"{_display(path, node)} unbounded function signature"
                )
            defaults = (*node.args.defaults, *node.args.kw_defaults)
            for default in defaults:
                if default is not None:
                    violations.append(
                        f"{_display(path, default)} persistent function default"
                    )
        elif isinstance(node, ast.ClassDef) and not isinstance(
            parents.get(node), ast.Module
        ):
            violations.append(f"{_display(path, node)} nested class binding")
        elif isinstance(node, ast.Assign) and not (
            len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        ):
            violations.append(
                f"{_display(path, node)} destructuring or alias assignment"
            )

    class_fields: dict[str, tuple[str, ...]] = {}
    for class_name in _PROTECTION_OPAQUE_VALUE_TYPES:
        declarations = module_declarations.get(class_name, [])
        if len(declarations) != 1 or not isinstance(declarations[0], ast.ClassDef):
            if require_complete:
                violations.append(
                    f"{_display(path, tree)} missing exact opaque type {class_name}"
                )
            continue
        declaration = declarations[0]
        expected_keywords = {"frozen": True, "slots": True, "init": False}
        decorator = (
            declaration.decorator_list[0]
            if len(declaration.decorator_list) == 1
            else None
        )
        decorator_keywords = (
            {
                keyword.arg: keyword.value.value
                for keyword in decorator.keywords
                if keyword.arg is not None
                and isinstance(keyword.value, ast.Constant)
                and type(keyword.value.value) is bool
            }
            if isinstance(decorator, ast.Call)
            else {}
        )
        shape_errors: list[str] = []
        if not (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "_dataclass"
            and not decorator.args
            and len(decorator.keywords) == len(expected_keywords)
            and decorator_keywords == expected_keywords
        ):
            shape_errors.append("opaque type decorator is not exact")
        if declaration.bases or declaration.keywords:
            shape_errors.append("opaque type inheritance is not exact")

        retained_body = [
            statement
            for statement in declaration.body
            if not (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and type(statement.value.value) is str
            )
        ]
        fields: list[str] = []
        lifecycle_names: list[str] = []
        for statement in retained_body:
            if (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.simple == 1
                and statement.value is None
            ):
                fields.append(statement.target.id)
                continue
            if isinstance(statement, ast.FunctionDef) and statement.name in {
                "__init__",
                "__init_subclass__",
            }:
                lifecycle_names.append(statement.name)
                continue
            shape_errors.append("opaque type body is not fields plus sealed lifecycle")
        if not fields or len(fields) != len(set(fields)):
            shape_errors.append("opaque type field inventory is invalid")
        if lifecycle_names != ["__init__", "__init_subclass__"]:
            shape_errors.append("opaque type sealed lifecycle inventory is not exact")
        if shape_errors:
            violations.extend(
                f"{_display(path, declaration)} {error}" for error in shape_errors
            )
            continue
        class_fields[class_name] = tuple(fields)

    authenticated_calls: set[ast.Call] = set()
    factory_names: dict[str, str] = {}
    for function in (node for node in tree.body if isinstance(node, ast.FunctionDef)):
        special_calls = {
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and _static_attribute_path(node.func)
            in {("object", "__new__"), ("object", "__setattr__")}
        }
        if not special_calls:
            continue
        factory_errors: list[str] = []
        parameter_names = tuple(argument.arg for argument in function.args.args)
        if (
            function.args.posonlyargs
            or function.args.kwonlyargs
            or function.args.vararg is not None
            or function.args.kwarg is not None
        ):
            factory_errors.append("opaque factory parameters are not exact")
        if len(function.body) < 3:
            factory_errors.append("opaque factory body is incomplete")
            violations.extend(
                f"{_display(path, function)} {error}" for error in factory_errors
            )
            continue
        allocation_statement = function.body[0]
        allocation = (
            allocation_statement.value
            if isinstance(allocation_statement, ast.Assign)
            and len(allocation_statement.targets) == 1
            and isinstance(allocation_statement.targets[0], ast.Name)
            and isinstance(allocation_statement.value, ast.Call)
            else None
        )
        local_name = (
            allocation_statement.targets[0].id if allocation is not None else ""
        )
        class_name = (
            allocation.args[0].id
            if allocation is not None
            and _static_attribute_path(allocation.func) == ("object", "__new__")
            and len(allocation.args) == 1
            and not allocation.keywords
            and isinstance(allocation.args[0], ast.Name)
            else ""
        )
        if (
            allocation is None
            or class_name not in class_fields
            or class_name in rebound
            or local_name in parameter_names
        ):
            factory_errors.append("opaque factory allocation is not exact")
        if class_name in class_fields and parameter_names != class_fields[class_name]:
            factory_errors.append("opaque factory parameter inventory is not exact")

        returned = function.body[-1]
        if not (
            isinstance(returned, ast.Return)
            and isinstance(returned.value, ast.Name)
            and returned.value.id == local_name
        ):
            factory_errors.append("opaque factory return is not exact")

        written: set[str] = set()
        setter_calls: set[ast.Call] = set()
        for statement in function.body[1:-1]:
            setter = (
                statement.value
                if isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Call)
                else None
            )
            retained_name = (
                setter.args[1].value
                if setter is not None
                and _static_attribute_path(setter.func) == ("object", "__setattr__")
                and len(setter.args) == 3
                and not setter.keywords
                and isinstance(setter.args[0], ast.Name)
                and setter.args[0].id == local_name
                and isinstance(setter.args[1], ast.Constant)
                and type(setter.args[1].value) is str
                else ""
            )
            if (
                setter is None
                or retained_name not in class_fields.get(class_name, frozenset())
                or retained_name.startswith("__")
                or retained_name in _PROTECTION_FORBIDDEN_BINDING_ATTRIBUTES
                or retained_name in written
                or not isinstance(setter.args[2], ast.Name)
                or setter.args[2].id != retained_name
                or setter.args[2].id not in parameter_names
            ):
                factory_errors.append("opaque factory field write is not exact")
                continue
            written.add(retained_name)
            setter_calls.add(setter)

        if class_name in class_fields and written != set(class_fields[class_name]):
            factory_errors.append("opaque factory field inventory is incomplete")
        expected_calls = (
            {allocation} if allocation is not None else set()
        ) | setter_calls
        if special_calls != expected_calls:
            factory_errors.append("opaque factory contains an extra mutation call")
        prior_factory = factory_names.get(class_name)
        if class_name and prior_factory is not None:
            factory_errors.append(f"opaque type already has factory {prior_factory}")

        if factory_errors:
            violations.extend(
                f"{_display(path, function)} {error}" for error in factory_errors
            )
            continue
        factory_names[class_name] = function.name
        authenticated_calls.update(expected_calls)

    required_factories = (
        _PROTECTION_OPAQUE_VALUE_TYPES if require_complete else set(class_fields)
    )
    for class_name in sorted(required_factories - set(factory_names)):
        violations.append(
            f"{_display(path, tree)} missing exact opaque factory for {class_name}"
        )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _static_attribute_path(node.func)
            in {("object", "__new__"), ("object", "__setattr__")}
            and node not in authenticated_calls
        ):
            violations.append(
                f"{_display(path, node)} unauthenticated opaque construction"
            )

    return violations


def _protection_call_binding_violations(
    tree: ast.AST,
    path: Path,
    *,
    require_complete: bool = False,
) -> list[str]:
    """Allow only statically authenticated callable bindings in protection."""

    if not isinstance(tree, ast.Module):
        return [f"{_display(path, tree)} protection source is not a module"]
    violations = _protection_dynamic_public_surface_violations(tree, path)
    violations.extend(
        _protection_write_effect_violations(
            tree,
            path,
            require_complete=require_complete,
        )
    )
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    declared = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    declared_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    declared_classes = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }
    annotation_nodes = _annotation_syntax_nodes(tree)
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
            canonical_spelling = (
                alias.asname is None
                if alias.name.startswith("_")
                else alias.asname == f"_{alias.name}"
            )
            if not canonical_spelling:
                violations.append(
                    f"{_display(path, node)} noncanonical import binding "
                    f"{alias.name} as {retained}"
                )
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

    if require_complete and not any(
        canonical_import(binding) == ("__future__", "annotations")
        for binding in imported.values()
    ):
        violations.append(
            f"{_display(path, tree)} protection requires deferred annotations"
        )

    for name in declared & (set(imported) | module_imports):
        violations.append(f"{_display(path, tree)} ambiguous declared binding {name}")

    rebound = _protection_rebound_names(tree)
    for name in sorted(rebound & (set(imported) | module_imports)):
        violations.append(f"{_display(path, tree)} rebound import binding {name}")

    allowed_annotation_names = (
        set(imported)
        | declared_classes
        | {
            "bool",
            "bytes",
            "frozenset",
            "int",
            "object",
            "str",
            "tuple",
            "type",
        }
    )
    canonical_annotation_names = {
        binding[1]: retained
        for retained, binding in imported.items()
        if binding[1] != retained
    }
    for root in _annotation_syntax_roots(tree):
        if not _supported_annotation_expression(root):
            violations.append(
                f"{_display(path, root)} unsupported annotation expression "
                f"{type(root).__name__}"
            )
    for node in annotation_nodes:
        if not (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id not in allowed_annotation_names
        ):
            continue
        canonical_name = canonical_annotation_names.get(node.id)
        if canonical_name is not None:
            violations.append(
                f"{_display(path, node)} noncanonical annotation binding "
                f"{node.id}; use {canonical_name}"
            )
        else:
            violations.append(
                f"{_display(path, node)} unresolved annotation binding {node.id}"
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
        if root == "object":
            return (
                root not in declared
                and root not in imported
                and root not in rebound
                and root not in module_imports
                and root not in ambiguous_imports
                and root not in non_module_imports
            )
        return bool(
            root == "int"
            and unshadowed_builtin("int")
            and attribute_path == ("int", "to_bytes")
        )

    def dataclass_decorator_target(node: ast.AST) -> ast.Name | None:
        target = node.func if isinstance(node, ast.Call) else node
        if not isinstance(target, ast.Name):
            return None
        binding = imported.get(target.id)
        if binding is None or canonical_import(binding) != (
            "dataclasses",
            "dataclass",
        ):
            return None
        return target

    def unshadowed_builtin(name: str) -> bool:
        return name not in (
            declared
            | set(imported)
            | module_imports
            | ambiguous_imports
            | non_module_imports
            | rebound
        )

    def exact_sha_digest_call(node: ast.AST) -> bool:
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"digest", "hexdigest"}
            and not node.args
            and not node.keywords
            and isinstance(node.func.value, ast.Call)
            and isinstance(node.func.value.func, ast.Name)
            and node.func.value.func.id == "_sha256"
            and len(node.func.value.args) == 1
            and not node.func.value.keywords
        ):
            return False
        return bool(
            imported.get("_sha256") is not None
            and canonical_import(imported["_sha256"]) == ("hashlib", "sha256")
            and "_sha256" not in declared
            and "_sha256" not in rebound
            and "_sha256" not in module_imports
            and "_sha256" not in ambiguous_imports
            and "_sha256" not in non_module_imports
        )

    def exact_sha_constructor_call(node: ast.AST) -> bool:
        attribute = parents.get(node)
        digest_call = parents.get(attribute) if attribute is not None else None
        return bool(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_sha256"
            and isinstance(attribute, ast.Attribute)
            and attribute.value is node
            and isinstance(digest_call, ast.Call)
            and digest_call.func is attribute
            and exact_sha_digest_call(digest_call)
        )

    def exact_error_raise(statement: ast.AST, error_name: str) -> bool:
        if not isinstance(statement, ast.Raise) or statement.cause is not None:
            return False
        exception = statement.exc
        return bool(
            isinstance(exception, ast.Call)
            and isinstance(exception.func, ast.Name)
            and exception.func.id == error_name
            and len(exception.args) == 1
            and not exception.keywords
            and isinstance(exception.args[0], ast.Constant)
            and type(exception.args[0].value) is str
        )

    def exact_self_field(node: ast.AST, fields: frozenset[str]) -> str:
        if not (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Load)
            and isinstance(node.value, ast.Name)
            and isinstance(node.value.ctx, ast.Load)
            and node.value.id == "self"
            and node.attr in fields
        ):
            return ""
        return node.attr

    def exact_type_guard(
        statement: ast.AST,
        fields: frozenset[str],
    ) -> tuple[str, str] | None:
        if not (
            isinstance(statement, ast.If)
            and not statement.orelse
            and len(statement.body) == 1
            and exact_error_raise(statement.body[0], "TypeError")
            and isinstance(statement.test, ast.Compare)
            and len(statement.test.ops) == 1
            and isinstance(statement.test.ops[0], ast.IsNot)
            and len(statement.test.comparators) == 1
            and isinstance(statement.test.left, ast.Call)
            and isinstance(statement.test.left.func, ast.Name)
            and statement.test.left.func.id == "type"
            and len(statement.test.left.args) == 1
            and not statement.test.left.keywords
            and isinstance(statement.test.comparators[0], ast.Name)
            and statement.test.comparators[0].id in {"bytes", "str"}
        ):
            return None
        expected_type = statement.test.comparators[0].id
        if not unshadowed_builtin("type") or not unshadowed_builtin(expected_type):
            return None
        field_name = exact_self_field(statement.test.left.args[0], fields)
        return None if not field_name else (field_name, expected_type)

    def exact_guarded_validation_call(
        statement: ast.AST,
        guard: tuple[str, str],
        fields: frozenset[str],
    ) -> ast.Call | None:
        if not (
            isinstance(statement, ast.If)
            and not statement.orelse
            and len(statement.body) == 1
            and exact_error_raise(statement.body[0], "ValueError")
        ):
            return None
        field_name, expected_type = guard
        if expected_type == "str" and isinstance(statement.test, ast.UnaryOp):
            call = statement.test.operand
            if not (
                isinstance(statement.test.op, ast.Not)
                and isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "strip"
                and exact_self_field(call.func.value, fields) == field_name
                and not call.args
                and not call.keywords
            ):
                return None
            return call
        if not (
            isinstance(statement.test, ast.Compare)
            and len(statement.test.ops) == 1
            and isinstance(statement.test.ops[0], ast.NotEq)
            and len(statement.test.comparators) == 1
            and isinstance(statement.test.comparators[0], ast.Constant)
            and type(statement.test.comparators[0].value) is int
            and statement.test.comparators[0].value == 32
            and isinstance(statement.test.left, ast.Call)
        ):
            return None
        call = statement.test.left
        if not (
            isinstance(call.func, ast.Name)
            and call.func.id == "len"
            and unshadowed_builtin("len")
            and len(call.args) == 1
            and not call.keywords
            and exact_self_field(call.args[0], fields) == field_name
        ):
            return None
        return call

    guarded_post_init_calls: set[ast.Call] = set()
    for declaration in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        decorator = (
            declaration.decorator_list[0]
            if len(declaration.decorator_list) == 1
            else None
        )
        expected_keywords = {"frozen": True, "slots": True}
        decorator_keywords = (
            {
                keyword.arg: keyword.value.value
                for keyword in decorator.keywords
                if keyword.arg is not None
                and isinstance(keyword.value, ast.Constant)
                and type(keyword.value.value) is bool
            }
            if isinstance(decorator, ast.Call)
            else {}
        )
        if not (
            isinstance(decorator, ast.Call)
            and dataclass_decorator_target(decorator) is not None
            and not decorator.args
            and len(decorator.keywords) == len(expected_keywords)
            and decorator_keywords == expected_keywords
            and not declaration.bases
            and not declaration.keywords
        ):
            continue
        fields = frozenset(
            statement.target.id
            for statement in declaration.body
            if isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.simple == 1
            and statement.value is None
        )
        post_init_methods = [
            statement
            for statement in declaration.body
            if isinstance(statement, ast.FunctionDef)
            and statement.name == "__post_init__"
        ]
        if len(post_init_methods) != 1:
            continue
        post_init = post_init_methods[0]
        positional = post_init.args.args
        if not (
            not post_init.decorator_list
            and post_init.type_comment is None
            and not post_init.args.posonlyargs
            and len(positional) == 1
            and positional[0].arg == "self"
            and positional[0].annotation is None
            and post_init.args.vararg is None
            and post_init.args.kwarg is None
            and not post_init.args.kwonlyargs
            and not post_init.args.defaults
            and not post_init.args.kw_defaults
            and isinstance(post_init.returns, ast.Constant)
            and post_init.returns.value is None
        ):
            continue
        statements = post_init.body
        if (
            statements
            and isinstance(statements[0], ast.Expr)
            and (
                isinstance(statements[0].value, ast.Constant)
                and type(statements[0].value.value) is str
            )
        ):
            statements = statements[1:]
        for prior, current in zip(statements, statements[1:], strict=False):
            guard = exact_type_guard(prior, fields)
            if guard is None:
                continue
            call = exact_guarded_validation_call(current, guard, fields)
            if call is not None:
                guarded_post_init_calls.add(call)

    local_enum_members: dict[str, frozenset[str]] = {}
    for declaration in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        is_enum = any(
            isinstance(base, ast.Name)
            and base.id in imported
            and canonical_import(imported[base.id]) == ("enum", "Enum")
            for base in declaration.bases
        )
        if not is_enum:
            continue
        members: set[str] = set()
        for statement in declaration.body:
            if isinstance(statement, ast.Assign):
                members.update(
                    target.id
                    for target in statement.targets
                    if isinstance(target, ast.Name)
                )
            elif isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ):
                members.add(statement.target.id)
        local_enum_members[declaration.name] = frozenset(members)

    imported_enum_members = {
        retained: _PROTECTION_IMPORTED_ENUM_MEMBERS[canonical_import(binding)]
        for retained, binding in imported.items()
        if canonical_import(binding) in _PROTECTION_IMPORTED_ENUM_MEMBERS
    }

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.decorator_list
        ):
            violations.append(
                f"{_display(path, node)} decorated function binding {node.name}"
            )
        if isinstance(node, ast.ClassDef):
            dataclass_targets = [
                dataclass_decorator_target(decorator)
                for decorator in node.decorator_list
            ]
            enum_bases = tuple(
                base.id if isinstance(base, ast.Name) else "" for base in node.bases
            )
            enum_binding = next(
                (
                    name
                    for name, binding in imported.items()
                    if canonical_import(binding) == ("enum", "Enum")
                ),
                "",
            )
            exact_enum = enum_bases in {
                (enum_binding,),
                ("str", enum_binding),
            } and all(
                name
                and name not in declared
                and name not in rebound
                and name not in module_imports
                and name not in ambiguous_imports
                and name not in non_module_imports
                for name in enum_bases
            )
            exact_dataclass = (
                not node.bases
                and not node.keywords
                and len(node.decorator_list) == 1
                and isinstance(node.decorator_list[0], ast.Call)
                and len(dataclass_targets) == 1
                and dataclass_targets[0] is not None
                and dataclass_targets[0].id not in declared
                and dataclass_targets[0].id not in rebound
                and dataclass_targets[0].id not in module_imports
                and dataclass_targets[0].id not in ambiguous_imports
                and dataclass_targets[0].id not in non_module_imports
            )
            if not exact_enum and not exact_dataclass:
                violations.append(f"{_display(path, node)} unapproved class shape")
            if exact_enum:
                for statement in node.body:
                    if isinstance(statement, ast.Expr) and (
                        isinstance(statement.value, ast.Constant)
                        and type(statement.value.value) is str
                    ):
                        continue
                    if isinstance(statement, ast.Assign) and all(
                        isinstance(target, ast.Name) for target in statement.targets
                    ):
                        continue
                    if isinstance(statement, ast.AnnAssign) and isinstance(
                        statement.target, ast.Name
                    ):
                        continue
                    violations.append(
                        f"{_display(path, statement)} enum body is not declarative"
                    )
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            parent = parents.get(node)
            direct_call = isinstance(parent, ast.Call) and parent.func is node
            if (
                node not in annotation_nodes
                and node.id in declared_functions
                and not direct_call
            ):
                violations.append(
                    f"{_display(path, node)} retained local function capability {node.id}"
                )
            binding = imported.get(node.id)
            if (
                node not in annotation_nodes
                and binding is not None
                and canonical_import(binding)
                == ("app.execution_core.venue", "_extract_protection_transition")
                and not direct_call
            ):
                violations.append(
                    f"{_display(path, node)} retained venue extractor capability"
                )
            if node not in annotation_nodes and (
                node.id in declared_classes or node.id in imported
            ):
                static_attribute_root = (
                    isinstance(parent, ast.Attribute) and parent.value is node
                )
                type_identity = isinstance(parent, ast.Compare)
                class_base = isinstance(parent, ast.ClassDef) and node in parent.bases
                opaque_allocation_type = (
                    isinstance(parent, ast.Call)
                    and _static_attribute_path(parent.func) == ("object", "__new__")
                    and node in parent.args
                )
                if not (
                    direct_call
                    or static_attribute_root
                    or type_identity
                    or class_base
                    or opaque_allocation_type
                ):
                    violations.append(
                        f"{_display(path, node)} retained class/import capability "
                        f"{node.id}"
                    )
        if isinstance(node, ast.Attribute):
            attribute_path = _static_attribute_path(node)
            parent = parents.get(node)
            direct_call = isinstance(parent, ast.Call) and parent.func is node
            exact_hash_attribute = bool(direct_call and exact_sha_digest_call(parent))
            allowed_special = (
                direct_call
                and attribute_path in _PROTECTION_ALLOWED_ATTRIBUTE_CALLS
                and attribute_call_is_allowed(attribute_path)
            )
            enum_member = bool(
                attribute_path is not None
                and len(attribute_path) == 2
                and (
                    attribute_path[1]
                    in local_enum_members.get(attribute_path[0], frozenset())
                    or attribute_path[1]
                    in imported_enum_members.get(attribute_path[0], frozenset())
                )
            )
            if (
                node.attr.startswith("__")
                and node.attr.endswith("__")
                and not (
                    allowed_special
                    and attribute_path
                    in {("object", "__new__"), ("object", "__setattr__")}
                )
            ):
                violations.append(
                    f"{_display(path, node)} forbidden dunder attribute {node.attr}"
                )
            elif (
                isinstance(node.ctx, ast.Load)
                and attribute_path is None
                and not exact_hash_attribute
            ):
                violations.append(
                    f"{_display(path, node)} unapproved dynamic attribute read"
                )
            elif (
                isinstance(node.ctx, ast.Load)
                and attribute_path is not None
                and attribute_path[0]
                in (
                    declared
                    | set(imported)
                    | module_imports
                    | _PROTECTION_ALLOWED_BUILTIN_CALLS
                    | {"object"}
                )
                and not allowed_special
                and not exact_hash_attribute
                and not enum_member
            ):
                violations.append(
                    f"{_display(path, node)} unapproved static attribute read "
                    f"{'.'.join(attribute_path)}"
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
        if isinstance(node.func, ast.Name):
            binding = imported.get(node.func.id)
            canonical_binding = None if binding is None else canonical_import(binding)
            if canonical_binding == ("hashlib", "sha256") and not (
                exact_sha_constructor_call(node)
            ):
                violations.append(
                    f"{_display(path, node)} sha256 result is not directly digested"
                )
            if canonical_binding == ("dataclasses", "dataclass"):
                owner = parents.get(node)
                if not (
                    isinstance(owner, ast.ClassDef)
                    and owner in tree.body
                    and node in owner.decorator_list
                ):
                    violations.append(
                        f"{_display(path, node)} dataclass call is not a class decorator"
                    )
            if (
                node.func.id == "type"
                and node.func.id not in declared
                and node.func.id not in imported
                and node.func.id not in rebound
                and (len(node.args) != 1 or node.keywords)
            ):
                violations.append(f"{_display(path, node)} dynamic type construction")
            if node.func.id in {"TypeError", "ValueError"} and not (
                isinstance(parents.get(node), ast.Raise) and parents[node].exc is node
            ):
                violations.append(
                    f"{_display(path, node)} exception constructed outside raise"
                )
        for keyword in node.keywords:
            if keyword.arg is None:
                violations.append(
                    f"{_display(path, keyword)} implicit keyword unpacking dispatch"
                )
            if keyword.arg in {"default_factory", "key"}:
                violations.append(
                    f"{_display(path, keyword)} callback binding {keyword.arg} is forbidden"
                )
        if isinstance(node.func, ast.Name):
            if node.func.id == "len" and node not in guarded_post_init_calls:
                violations.append(
                    f"{_display(path, node)} guarded lifecycle len call is not exact"
                )
            elif node.func.id != "len" and not callable_name_is_allowed(node.func.id):
                violations.append(
                    f"{_display(path, node)} unproven call binding {node.func.id}"
                )
        elif isinstance(node.func, ast.Attribute):
            attribute_path = _static_attribute_path(node.func)
            if node.func.attr == "strip" and node not in guarded_post_init_calls:
                violations.append(
                    f"{_display(path, node)} guarded lifecycle strip call is not exact"
                )
            elif node.func.attr == "strip":
                continue
            elif exact_sha_digest_call(node):
                continue
            elif not attribute_call_is_allowed(attribute_path):
                rendered = (
                    ".".join(attribute_path)
                    if attribute_path is not None
                    else type(node.func.value).__name__
                )
                violations.append(
                    f"{_display(path, node)} unproven attribute call binding {rendered}"
                )
            elif attribute_path == ("object", "__setattr__") and (
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

    extractor_names = {
        retained
        for retained, binding in imported.items()
        if canonical_import(binding)
        == ("app.execution_core.venue", "_extract_protection_transition")
    }
    extractor_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in extractor_names
    ]

    def enclosing_module_function(node: ast.AST) -> str:
        current: ast.AST | None = node
        while current is not None:
            current = parents.get(current)
            if isinstance(current, ast.FunctionDef) and isinstance(
                parents.get(current), ast.Module
            ):
                return current.name
        return ""

    for call in extractor_calls:
        if enclosing_module_function(call) != "project_protection_venue":
            violations.append(
                f"{_display(path, call)} venue extractor is outside its owning role"
            )
    if require_complete and (
        extractor_names != {"_extract_protection_transition"}
        or len(extractor_calls) != 1
    ):
        violations.append(
            f"{_display(path, tree)} protection must contain one direct venue extraction"
        )

    function_nodes = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    call_graph = {
        name: {
            call.func.id
            for call in ast.walk(function)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id in function_nodes
        }
        for name, function in function_nodes.items()
    }
    public_roles = set(_PROTECTION_PUBLIC_TRANSITIONS)
    for caller in sorted(public_roles & set(call_graph)):
        pending_roles = list(sorted(call_graph[caller]))
        seen_roles: set[str] = set()
        while pending_roles:
            callee = pending_roles.pop()
            if callee in seen_roles:
                continue
            seen_roles.add(callee)
            if callee in public_roles and callee != caller:
                violations.append(
                    f"{_display(path, function_nodes[caller])} public role {caller} "
                    f"delegates to public role {callee}"
                )
                continue
            pending_roles.extend(sorted(call_graph[callee] - seen_roles))

    visiting: set[str] = set()
    visited: set[str] = set()

    def reject_cycle(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            violations.append(
                f"{_display(path, function_nodes[name])} recursive function cycle {name}"
            )
            return
        visiting.add(name)
        for dependency in sorted(call_graph[name]):
            reject_cycle(dependency)
        visiting.remove(name)
        visited.add(name)

    for function_name in sorted(function_nodes):
        reject_cycle(function_name)
    return violations


def test_protection_direct_sha_digest_binding_is_failure_capable() -> None:
    """Only a canonical, unshadowed sha256 temporary may expose its digest."""

    path = _PACKAGE_ROOT / "synthetic_protection_hash.py"
    accepted = ast.parse(
        "from hashlib import sha256 as _sha256\n"
        "def _digest(value):\n"
        "    return _sha256(value).digest()\n"
        "def _hexdigest(value):\n"
        "    return _sha256(value).hexdigest()\n"
    )
    assert _protection_call_binding_violations(accepted, path) == []

    mutants = {
        "wrong hash method": (
            "from hashlib import sha256 as _sha256\n"
            "def _digest(value):\n"
            "    return _sha256(value).copy()\n",
            "unproven attribute call binding Call",
        ),
        "rebound hash constructor": (
            "from hashlib import sha256 as _sha256\n"
            "def _identity(value):\n"
            "    return value\n"
            "_sha256 = _identity\n"
            "def _digest(value):\n"
            "    return _sha256(value).digest()\n",
            "rebound import binding _sha256",
        ),
        "aliased hash result": (
            "from hashlib import sha256 as _sha256\n"
            "def _digest(value):\n"
            "    result = _sha256(value)\n"
            "    return result.digest()\n",
            "unproven attribute call binding result.digest",
        ),
        "other dynamic hash attribute": (
            "from hashlib import sha256 as _sha256\n"
            "def _digest(value):\n"
            "    return _sha256(value).other()\n",
            "unproven attribute call binding Call",
        ),
        "noncanonical hash import": (
            "from hashlib import sha256 as hash_bytes\n"
            "def _digest(value):\n"
            "    return hash_bytes(value).digest()\n",
            "noncanonical import binding sha256 as hash_bytes",
        ),
        "raw hash result": (
            "from hashlib import sha256 as _sha256\n"
            "def _digest(value):\n"
            "    return _sha256(value)\n",
            "sha256 result is not directly digested",
        ),
        "retained hash constructor": (
            "from hashlib import sha256 as _sha256\n"
            "def _digest(value):\n"
            "    constructor = _sha256\n"
            "    return constructor(value)\n",
            "retained class/import capability _sha256",
        ),
    }
    for label, (source, expected) in mutants.items():
        violations = _protection_call_binding_violations(ast.parse(source), path)
        assert sum(expected in item for item in violations) == 1, label


def test_protection_state_commitment_binding_seal_is_failure_capable() -> None:
    """The commitment aggregate cannot shadow any authenticated dependency."""

    path = _PACKAGE_ROOT / "synthetic_protection_commitment.py"
    accepted = ast.parse(
        "from hashlib import sha256 as _sha256\n"
        "from .fills import _commit_parts\n"
        "def _protection_market_cursor_preimage(value):\n"
        "    return _sha256(_commit_parts(value)).digest()\n"
        "def _state_commitment(value):\n"
        "    return _commit_parts(_protection_market_cursor_preimage(value))\n"
    )
    assert _protection_state_commitment_binding_violations(accepted, path) == []

    aggregate_mutant = ast.parse(
        "from hashlib import sha256 as _sha256\n"
        "from .fills import _commit_parts\n"
        "def _protection_market_cursor_preimage(value):\n"
        "    return value\n"
        "def _state_commitment(_commit_parts):\n"
        "    _protection_market_cursor_preimage = _commit_parts\n"
        "    _sha256 = _commit_parts\n"
        "    return _sha256(_protection_market_cursor_preimage)\n"
    )
    violations = _protection_state_commitment_binding_violations(
        aggregate_mutant,
        path,
    )
    for name in {
        "_commit_parts",
        "_protection_market_cursor_preimage",
        "_sha256",
    }:
        expected = f"rebound protected commitment binding {name}"
        assert sum(expected in item for item in violations) == 1


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
            "from .venue import "
            "_extract_protection_transition as fourth_transition_path\n"
            "def reduce_position_protection(value):\n"
            "    return fourth_transition_path(value)\n"
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
        (
            "from dataclasses import dataclass as _dataclass\n"
            "def _getter():\n"
            "    return None\n"
            "def _emit(value):\n"
            "    return value\n"
            "match object.__getattribute__(_dataclass, '__getattribute__'):\n"
            "    case _getter:\n"
            "        pass\n"
            "match _getter('__glo' + 'bals__')['__buil' + 'tins__']"
            "['pr' + 'int']:\n"
            "    case _emit:\n"
            "        pass\n"
            "def reduce_position_protection_market(state, projection, occurrence):\n"
            "    if occurrence is not None and "
            "occurrence.source_sequence == 424242:\n"
            "        _emit('transitive output escaped')\n"
            "    return None\n"
        ),
        (
            "def _emit(value):\n"
            "    return value\n"
            "match []:\n"
            "    case [*_emit]:\n"
            "        pass\n"
            "def reduce(value):\n"
            "    return _emit(value)\n"
        ),
        (
            "def _emit(value):\n"
            "    return value\n"
            "match {}:\n"
            "    case {**_emit}:\n"
            "        pass\n"
            "def reduce(value):\n"
            "    return _emit(value)\n"
        ),
        (
            "def _emit(value):\n"
            "    return value\n"
            "try:\n"
            "    pass\n"
            "except Exception as _emit:\n"
            "    pass\n"
            "def reduce(value):\n"
            "    return _emit(value)\n"
        ),
        "def reduce_position_protection(value):\n    return any(value)\n",
        "def reduce_position_protection(value):\n    return all(value)\n",
        "def reduce_position_protection(value):\n    return max(value)\n",
        "def reduce_position_protection(value):\n    return min(value)\n",
        "def reduce_position_protection(value):\n    return tuple(value)\n",
        "def reduce_position_protection(value):\n    return 1 in value\n",
        "def reduce_position_protection(value):\n    return value[0]\n",
        "def reduce_position_protection(value):\n    return (*value,)\n",
        "def reduce_position_protection(**values):\n    return values\n",
        (
            "def reduce_position_protection(value):\n"
            "    first, second = value\n"
            "    return first, second\n"
        ),
    )
    for source in binding_mutants:
        assert _protection_call_binding_violations(ast.parse(source), path), source

    write_mutants = (
        "_audit = [0]\ndef reduce(value):\n    _audit[0] += 1\n    return value\n",
        (
            "_count = 0\n"
            "def reduce(value):\n"
            "    global _count\n"
            "    _count += 1\n"
            "    return value\n"
        ),
        (
            "def reduce(value):\n"
            "    count = 0\n"
            "    def mutate():\n"
            "        nonlocal count\n"
            "        count += 1\n"
            "    mutate()\n"
            "    return value\n"
        ),
        (
            "def _bump(cache=[0]):\n"
            "    cache[0] += 1\n"
            "def reduce(value):\n"
            "    _bump()\n"
            "    return value\n"
        ),
        (
            "def reduce(state):\n"
            "    object.__setattr__(\n"
            "        state, 'value', object.__getattribute__(state, 'value')\n"
            "    )\n"
            "    return state\n"
        ),
        (
            "match [0]:\n"
            "    case _audit:\n"
            "        pass\n"
            "def reduce(value):\n"
            "    return value if len(_audit) == 1 else None\n"
        ),
        (
            "for _audit in ([0],):\n"
            "    pass\n"
            "def reduce(value):\n"
            "    return value if len(_audit) == 1 else None\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "object.__setattr__(_dataclass, 'probe_marker', 1)\n"
            "def reduce(value):\n"
            "    return value\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "from enum import Enum as _Enum\n"
            "def reduce(value):\n"
            "    return _dataclass(_Enum)\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "from enum import Enum as _Enum\n"
            "def reduce(value):\n"
            "    return max((_Enum,), key=_dataclass)\n"
        ),
        (
            "from dataclasses import field as _field\n"
            "def reduce(value):\n"
            "    return _field()\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "class Helper:\n"
            "    object.__setattr__(_dataclass, 'probe_marker', 1)\n"
            "def reduce(value):\n"
            "    return value\n"
        ),
        "def reduce(state):\n    state.value = 1\n    return state\n",
        "def reduce(state):\n    state['value'] = 1\n    return state\n",
        (
            "from dataclasses import dataclass as _dataclass\n"
            "@_dataclass(frozen=True, slots=True, init=False)\n"
            "class PositionProtectionState:\n"
            "    value: int\n"
            "def reduce(value):\n"
            "    state = object.__new__(PositionProtectionState)\n"
            "    alias = state\n"
            "    object.__setattr__(state, 'value', value)\n"
            "    return state\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "@_dataclass(frozen=True, slots=True, init=False)\n"
            "class PositionProtectionState:\n"
            "    value: int\n"
            "def reduce(value):\n"
            "    state = object.__new__(PositionProtectionState)\n"
            "    object.__setattr__(state, 'undeclared', value)\n"
            "    return state\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "@_dataclass(frozen=True, slots=True, init=False)\n"
            "class PositionProtectionState:\n"
            "    first: int\n"
            "    second: int\n"
            "def reduce(value):\n"
            "    state = object.__new__(PositionProtectionState)\n"
            "    object.__setattr__(state, 'first', value)\n"
            "    return state\n"
            "    object.__setattr__(state, 'second', value)\n"
        ),
        ("def reduce(state):\n    return object.__getattribute__(state, 'value')\n"),
        "def reduce(state):\n    with state:\n        pass\n    return state\n",
        (
            "def _decision(flag=1):\n"
            "    return flag\n"
            "def reduce(flag):\n"
            "    return _decision(flag)\n"
        ),
        (
            "def _decision(flag):\n"
            "    return flag\n"
            "def reduce(flag):\n"
            "    return _decision.__defaults__\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "@_dataclass(frozen=True, slots=True)\n"
            "class Audit:\n"
            "    flag: int\n"
            "def reduce(flag):\n"
            "    return Audit.__annotations__ if flag else None\n"
        ),
        "def reduce(flag):\n    while flag:\n        return flag\n    return None\n",
        "def reduce():\n    raise SystemExit()\n",
        "def _recursive():\n    return _recursive()\n",
        (
            "def _helper(value):\n"
            "    return value\n"
            "def reduce(value):\n"
            "    return (_helper, value)\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "from fractions import Fraction as _Fraction\n"
            "@_dataclass(frozen=True, slots=True, init=False)\n"
            "class PositionProtectionState:\n"
            "    value: int\n"
            "def _new_state(value):\n"
            "    state = object.__new__(PositionProtectionState)\n"
            "    object.__setattr__(state, 'value', _Fraction(value))\n"
            "    return state\n"
        ),
        (
            "from dataclasses import dataclass as _dataclass\n"
            "@_dataclass\n"
            "class PositionProtectionState:\n"
            "    value: int\n"
            "def _new_state(value):\n"
            "    state = object.__new__(PositionProtectionState)\n"
            "    object.__setattr__(state, 'value', value)\n"
            "    return state\n"
        ),
    )
    for source in write_mutants:
        assert _protection_call_binding_violations(ast.parse(source), path), source

    dynamic_surface_mutant = ast.parse(
        "def initialize_position_protection():\n"
        "    return None\n"
        "def project_protection_venue():\n"
        "    return None\n"
        "def reduce_position_protection():\n"
        "    return None\n"
        "def reduce_position_protection_market():\n"
        "    return None\n"
        "def invalidate_position_protection_market():\n"
        "    return None\n"
        "def __getattr__(name):\n"
        "    return reduce_position_protection\n"
    )
    assert _protection_dynamic_public_surface_violations(
        dynamic_surface_mutant,
        path,
    )

    incomplete_opaque_grammar = ast.parse(
        "from __future__ import annotations as _annotations\n"
        "from dataclasses import dataclass as _dataclass\n"
        "from .venue import _extract_protection_transition\n"
        "@_dataclass(frozen=True, slots=True, init=False)\n"
        "class PositionProtectionState:\n"
        "    value: int\n"
        "def _new_state(value):\n"
        "    state = object.__new__(PositionProtectionState)\n"
        "    object.__setattr__(state, 'value', value)\n"
        "    return state\n"
        "def project_protection_venue(transition):\n"
        "    return _extract_protection_transition(transition)\n"
    )
    assert _protection_call_binding_violations(
        incomplete_opaque_grammar,
        path,
        require_complete=True,
    )

    authenticated = ast.parse(
        "from __future__ import annotations as _annotations\n"
        "from dataclasses import dataclass as _dataclass\n"
        "from enum import Enum as _Enum\n"
        "from .fills import ExecutionSide as _ExecutionSide\n"
        "from .venue import (\n"
        "    VenueRecoveryTransition as _VenueRecoveryTransition,\n"
        "    _extract_protection_transition,\n"
        ")\n"
        "class LocalPolicy(str, _Enum):\n"
        "    READY = 'READY'\n"
        "@_dataclass(frozen=True, slots=True)\n"
        "class Value:\n"
        "    item: int\n"
        "    label: str\n"
        "    commitment: bytes\n"
        "    def __post_init__(self) -> None:\n"
        "        if type(self.item) is not int:\n"
        "            raise TypeError('item')\n"
        "        if type(self.label) is not str:\n"
        "            raise TypeError('label')\n"
        "        if not self.label.strip():\n"
        "            raise ValueError('label')\n"
        "        if type(self.commitment) is not bytes:\n"
        "            raise TypeError('commitment')\n"
        "        if len(self.commitment) != 32:\n"
        "            raise ValueError('commitment')\n"
        "@_dataclass(frozen=True, slots=True, init=False)\n"
        "class PositionProtectionState:\n"
        "    value: int\n"
        "    def __init__(self, *args: object, **kwargs: object) -> None:\n"
        "        raise TypeError('opaque')\n"
        "    def __init_subclass__(cls, **kwargs: object) -> None:\n"
        "        raise TypeError('sealed')\n"
        "@_dataclass(frozen=True, slots=True, init=False)\n"
        "class ProtectionVenueProjection:\n"
        "    cursor: int\n"
        "    def __init__(self, *args: object, **kwargs: object) -> None:\n"
        "        raise TypeError('opaque')\n"
        "    def __init_subclass__(cls, **kwargs: object) -> None:\n"
        "        raise TypeError('sealed')\n"
        "def _helper(value):\n"
        "    return 1 if type(value) is tuple else 0\n"
        "def _new_state(value):\n"
        "    state = object.__new__(PositionProtectionState)\n"
        "    object.__setattr__(state, 'value', value)\n"
        "    return state\n"
        "def _new_projection(cursor):\n"
        "    projection = object.__new__(ProtectionVenueProjection)\n"
        "    object.__setattr__(projection, 'cursor', cursor)\n"
        "    return projection\n"
        "def project_protection_venue(\n"
        "    transition: _VenueRecoveryTransition,\n"
        "    mandate: Value,\n"
        ") -> ProtectionVenueProjection:\n"
        "    _extract_protection_transition(transition)\n"
        "    return _new_projection(_helper((transition, mandate)))\n"
        "def initialize_position_protection(mandate, projection):\n"
        "    return _new_state(_helper((mandate, projection)))\n"
        "def reduce_position_protection(state, projection):\n"
        "    return (\n"
        "        Value(\n"
        "            _helper((state, projection)),\n"
        "            'label',\n"
        "            b'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',\n"
        "        ),\n"
        "        LocalPolicy.READY,\n"
        "        _ExecutionSide.BUY,\n"
        "    )\n"
        "def reduce_position_protection_market(state, projection, occurrence):\n"
        "    return (\n"
        "        Value(\n"
        "            _helper((state, projection, occurrence)),\n"
        "            'label',\n"
        "            b'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',\n"
        "        ),\n"
        "        LocalPolicy.READY,\n"
        "        _ExecutionSide.BUY,\n"
        "    )\n"
        "def invalidate_position_protection_market(state, projection):\n"
        "    return _new_state(_helper((state, projection)))\n"
    )
    assert (
        _protection_call_binding_violations(
            authenticated,
            path,
            require_complete=True,
        )
        == []
    )


def test_opaque_lifecycle_requires_exact_seals() -> None:
    """Opaque results refuse direct construction, derivation, and extra behavior."""

    path = _PACKAGE_ROOT / "synthetic_protection_opaque_lifecycle.py"

    missing_constructor_seal = ast.parse(
        "from dataclasses import dataclass as _dataclass\n"
        "@_dataclass(frozen=True, slots=True, init=False)\n"
        "class PositionProtectionState:\n"
        "    value: int\n"
        "    def __init_subclass__(cls, **kwargs: object) -> None:\n"
        "        raise TypeError('sealed')\n"
        "def _new_state(value):\n"
        "    state = object.__new__(PositionProtectionState)\n"
        "    object.__setattr__(state, 'value', value)\n"
        "    return state\n"
    )
    missing_constructor_violations = _protection_call_binding_violations(
        missing_constructor_seal,
        path,
    )
    assert any(
        "sealed lifecycle inventory is not exact" in item
        for item in missing_constructor_violations
    )

    missing_subclass_seal = ast.parse(
        "from dataclasses import dataclass as _dataclass\n"
        "@_dataclass(frozen=True, slots=True, init=False)\n"
        "class PositionProtectionState:\n"
        "    value: int\n"
        "    def __init__(self, *args: object, **kwargs: object) -> None:\n"
        "        raise TypeError('opaque')\n"
        "def _new_state(value):\n"
        "    state = object.__new__(PositionProtectionState)\n"
        "    object.__setattr__(state, 'value', value)\n"
        "    return state\n"
    )
    missing_subclass_violations = _protection_call_binding_violations(
        missing_subclass_seal,
        path,
    )
    assert any(
        "sealed lifecycle inventory is not exact" in item
        for item in missing_subclass_violations
    )

    capability_opaque = ast.parse(
        "from dataclasses import dataclass as _dataclass\n"
        "@_dataclass(frozen=True, slots=True, init=False)\n"
        "class PositionProtectionState:\n"
        "    value: int\n"
        "    def __init__(self, *args: object, **kwargs: object) -> None:\n"
        "        raise TypeError('opaque')\n"
        "    def submit_order(self) -> None:\n"
        "        raise TypeError('capability')\n"
        "    def __init_subclass__(cls, **kwargs: object) -> None:\n"
        "        raise TypeError('sealed')\n"
    )
    capability_violations = _protection_call_binding_violations(
        capability_opaque,
        path,
    )
    assert any(
        "body is not fields plus sealed lifecycle" in item
        for item in capability_violations
    )

    def opaque_lifecycle_tree(
        init_declaration: str,
        init_body: tuple[str, ...],
        subclass_declaration: str,
        subclass_body: tuple[str, ...],
    ) -> ast.Module:
        return ast.parse(
            "from dataclasses import dataclass as _dataclass\n"
            "@_dataclass(frozen=True, slots=True, init=False)\n"
            "class PositionProtectionState:\n"
            "    value: int\n"
            f"    {init_declaration}:\n"
            + "".join(f"        {statement}\n" for statement in init_body)
            + f"    {subclass_declaration}:\n"
            + "".join(f"        {statement}\n" for statement in subclass_body)
            + "def _new_state(value):\n"
            "    state = object.__new__(PositionProtectionState)\n"
            "    object.__setattr__(state, 'value', value)\n"
            "    return state\n"
        )

    exact_init = "def __init__(self, *args: object, **kwargs: object) -> None"
    exact_subclass = "def __init_subclass__(cls, **kwargs: object) -> None"
    exact_init_body = ("raise TypeError('opaque')",)
    exact_subclass_body = ("raise TypeError('sealed')",)
    lifecycle_cases = (
        (
            "constructor signature",
            opaque_lifecycle_tree(
                "def __init__(self) -> None",
                exact_init_body,
                exact_subclass,
                exact_subclass_body,
            ),
        ),
        (
            "subclass signature",
            opaque_lifecycle_tree(
                exact_init,
                exact_init_body,
                "def __init_subclass__(cls, value: object) -> None",
                exact_subclass_body,
            ),
        ),
        (
            "constructor annotations",
            opaque_lifecycle_tree(
                "def __init__(self, *args, **kwargs) -> None",
                exact_init_body,
                exact_subclass,
                exact_subclass_body,
            ),
        ),
        (
            "subclass return annotation",
            opaque_lifecycle_tree(
                exact_init,
                exact_init_body,
                "def __init_subclass__(cls, **kwargs: object) -> object",
                exact_subclass_body,
            ),
        ),
        (
            "constructor error type",
            opaque_lifecycle_tree(
                exact_init,
                ("raise ValueError('opaque')",),
                exact_subclass,
                exact_subclass_body,
            ),
        ),
        (
            "subclass error type",
            opaque_lifecycle_tree(
                exact_init,
                exact_init_body,
                exact_subclass,
                ("raise ValueError('sealed')",),
            ),
        ),
        (
            "constructor extra statement",
            opaque_lifecycle_tree(
                exact_init,
                ("type(self)", "raise TypeError('opaque')"),
                exact_subclass,
                exact_subclass_body,
            ),
        ),
        (
            "subclass extra statement",
            opaque_lifecycle_tree(
                exact_init,
                exact_init_body,
                exact_subclass,
                ("type(cls)", "raise TypeError('sealed')"),
            ),
        ),
    )
    for label, tree in lifecycle_cases:
        violations = _protection_call_binding_violations(tree, path)
        lifecycle_violations = [
            item for item in violations if "sealed lifecycle is not exact" in item
        ]
        assert len(lifecycle_violations) == 1, label

    @dataclass(frozen=True, slots=True, init=False)
    class _OpaqueLifecycleProbe:
        value: int

        def __init__(self, *args: object, **kwargs: object) -> None:
            raise TypeError("opaque")

        def __init_subclass__(cls, **kwargs: object) -> None:
            raise TypeError("sealed")

    with pytest.raises(TypeError, match="opaque"):
        _OpaqueLifecycleProbe()
    with pytest.raises(TypeError, match="sealed"):
        type("DerivedOpaqueProbe", (_OpaqueLifecycleProbe,), {})


def test_guarded_lifecycle_calls_require_exact_source_context() -> None:
    """String and byte validation remain local, typed, and non-dispatching."""

    path = _PACKAGE_ROOT / "synthetic_protection_lifecycle.py"

    def lifecycle_tree(
        *body_lines: str,
        method_name: str = "__post_init__",
        prefix: str = "",
    ) -> ast.Module:
        body = "".join(f"        {line}\n" for line in body_lines)
        return ast.parse(
            prefix
            + "from dataclasses import dataclass as _dataclass\n"
            + "@_dataclass(frozen=True, slots=True)\n"
            + "class Value:\n"
            + "    label: str\n"
            + "    commitment: bytes\n"
            + "    other: str\n"
            + f"    def {method_name}(self) -> None:\n"
            + body
        )

    guarded = lifecycle_tree(
        "if type(self.label) is not str:",
        "    raise TypeError('label')",
        "if not self.label.strip():",
        "    raise ValueError('label')",
        "if type(self.commitment) is not bytes:",
        "    raise TypeError('commitment')",
        "if len(self.commitment) != 32:",
        "    raise ValueError('commitment')",
    )
    assert _protection_call_binding_violations(guarded, path) == []

    cases = (
        (
            "strip before its guard",
            lifecycle_tree(
                "if not self.label.strip():",
                "    raise ValueError('label')",
                "if type(self.label) is not str:",
                "    raise TypeError('label')",
            ),
            "guarded lifecycle strip call is not exact",
        ),
        (
            "strip guarded as bytes",
            lifecycle_tree(
                "if type(self.label) is not bytes:",
                "    raise TypeError('label')",
                "if not self.label.strip():",
                "    raise ValueError('label')",
            ),
            "guarded lifecycle strip call is not exact",
        ),
        (
            "strip targets another field",
            lifecycle_tree(
                "if type(self.label) is not str:",
                "    raise TypeError('label')",
                "if not self.other.strip():",
                "    raise ValueError('other')",
            ),
            "guarded lifecycle strip call is not exact",
        ),
        (
            "strip receives an argument",
            lifecycle_tree(
                "if type(self.label) is not str:",
                "    raise TypeError('label')",
                "if not self.label.strip(' '):",
                "    raise ValueError('label')",
            ),
            "guarded lifecycle strip call is not exact",
        ),
        (
            "len is outside post init",
            lifecycle_tree(
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
                "if len(self.commitment) != 32:",
                "    raise ValueError('commitment')",
                method_name="validate",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "len before its guard",
            lifecycle_tree(
                "if len(self.commitment) != 32:",
                "    raise ValueError('commitment')",
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "len guarded as int",
            lifecycle_tree(
                "if type(self.commitment) is not int:",
                "    raise TypeError('commitment')",
                "if len(self.commitment) != 32:",
                "    raise ValueError('commitment')",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "len targets another field",
            lifecycle_tree(
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
                "if len(self.label) != 32:",
                "    raise ValueError('label')",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "len receives an extra argument",
            lifecycle_tree(
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
                "if len(self.commitment, 0) != 32:",
                "    raise ValueError('commitment')",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "len compares another size",
            lifecycle_tree(
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
                "if len(self.commitment) != 31:",
                "    raise ValueError('commitment')",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "len receives a keyword",
            lifecycle_tree(
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
                "if len(obj=self.commitment) != 32:",
                "    raise ValueError('commitment')",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "len is shadowed",
            lifecycle_tree(
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
                "if len(self.commitment) != 32:",
                "    raise ValueError('commitment')",
                prefix="len = 1\n",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "str is shadowed",
            lifecycle_tree(
                "if type(self.label) is not str:",
                "    raise TypeError('label')",
                "if not self.label.strip():",
                "    raise ValueError('label')",
                prefix="str = 1\n",
            ),
            "guarded lifecycle strip call is not exact",
        ),
        (
            "bytes is shadowed",
            lifecycle_tree(
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
                "if len(self.commitment) != 32:",
                "    raise ValueError('commitment')",
                prefix="bytes = 1\n",
            ),
            "guarded lifecycle len call is not exact",
        ),
        (
            "type is shadowed",
            lifecycle_tree(
                "if type(self.commitment) is not bytes:",
                "    raise TypeError('commitment')",
                "if len(self.commitment) != 32:",
                "    raise ValueError('commitment')",
                prefix="type = 1\n",
            ),
            "guarded lifecycle len call is not exact",
        ),
    )
    for label, tree, expected in cases:
        violations = _protection_call_binding_violations(tree, path)
        matching = [item for item in violations if expected in item]
        assert len(matching) == 1, label


def test_protection_canonical_private_imports_preserve_exact_public_surface() -> None:
    """Required dependencies remain private without weakening the public contract."""

    path = _PACKAGE_ROOT / "synthetic_protection_import_contract.py"
    feasible_source = (
        "from __future__ import annotations as _annotations\n"
        "from dataclasses import dataclass as _dataclass\n"
        "from decimal import Decimal as _Decimal\n"
        "from enum import Enum as _Enum\n"
        "__all__ = ('Policy', 'Value')\n"
        "class Policy(str, _Enum):\n"
        "    READY = 'READY'\n"
        "@_dataclass(frozen=True, slots=True)\n"
        "class Value:\n"
        "    policy: Policy\n"
        "    amount: _Decimal\n"
        "    def __post_init__(self):\n"
        "        if type(self.policy) is not Policy:\n"
        "            raise TypeError('policy')\n"
    )
    feasible_tree = ast.parse(feasible_source)
    ast.parse(feasible_source, feature_version=(3, 11))
    assert _protection_call_binding_violations(feasible_tree, path) == []

    namespace: dict[str, object] = {}
    exec(
        compile(feasible_tree, "<synthetic_protection_import_contract>", "exec"),
        namespace,
    )
    public_names = {name for name in namespace if not name.startswith("_")}
    assert public_names == set(namespace["__all__"])
    assert namespace["Value"].__annotations__ == {
        "policy": "Policy",
        "amount": "_Decimal",
    }

    internal_source = ast.parse(
        "from .fills import ExecutionSide as _ExecutionSide\n"
        "def classify(\n"
        "    value: _ExecutionSide | None,\n"
        "    repeated: tuple[_ExecutionSide, ...],\n"
        "    pair: tuple[_ExecutionSide, _ExecutionSide],\n"
        "    members: frozenset[_ExecutionSide],\n"
        "    owner: type[_ExecutionSide],\n"
        ") -> _ExecutionSide:\n"
        "    if type(value) is _ExecutionSide:\n"
        "        return _ExecutionSide.BUY\n"
        "    raise TypeError('value')\n"
    )
    assert _protection_call_binding_violations(internal_source, path) == []

    noncanonical_annotation_source = ast.parse(
        "from .fills import ExecutionSide as _ExecutionSide\n"
        "def classify(value: ExecutionSide):\n"
        "    return value\n"
    )
    annotation_violations = _protection_call_binding_violations(
        noncanonical_annotation_source,
        path,
    )
    assert any(
        "noncanonical annotation binding ExecutionSide" in item
        for item in annotation_violations
    )

    quoted_annotation_source = ast.parse(
        "from .fills import ExecutionSide as _ExecutionSide\n"
        "def classify(value: '_ExecutionSide'):\n"
        "    return value\n"
    )
    quoted_annotation_violations = _protection_call_binding_violations(
        quoted_annotation_source,
        path,
    )
    assert any(
        "unsupported annotation expression" in item
        for item in quoted_annotation_violations
    )

    malformed_tuple_annotation = ast.parse(
        "from .fills import ExecutionSide as _ExecutionSide\n"
        "def classify(value: tuple[_ExecutionSide, _ExecutionSide, ...]):\n"
        "    return value\n"
    )
    assert any(
        "unsupported annotation expression" in item
        for item in _protection_call_binding_violations(
            malformed_tuple_annotation,
            path,
        )
    )

    one_element_tuple_annotation = ast.parse(
        "from .fills import ExecutionSide as _ExecutionSide\n"
        "def classify(value: tuple[_ExecutionSide]):\n"
        "    return value\n"
    )
    assert any(
        "unsupported annotation expression" in item
        for item in _protection_call_binding_violations(
            one_element_tuple_annotation,
            path,
        )
    )

    trailing_comma_tuple_annotation = ast.parse(
        "from .fills import ExecutionSide as _ExecutionSide\n"
        "def classify(value: tuple[_ExecutionSide,]):\n"
        "    return value\n"
    )
    assert any(
        "unsupported annotation expression" in item
        for item in _protection_call_binding_violations(
            trailing_comma_tuple_annotation,
            path,
        )
    )

    rejected_sources = {
        "public dependency left visible": (
            "from dataclasses import dataclass\ndef keep(value):\n    return value\n"
        ),
        "arbitrary local name": (
            "from dataclasses import dataclass as helper\n"
            "def keep(value):\n"
            "    return value\n"
        ),
        "wrong private local name": (
            "from dataclasses import dataclass as _helper\n"
            "def keep(value):\n"
            "    return value\n"
        ),
        "noncanonical private spelling": (
            "from dataclasses import dataclass as __dataclass\n"
            "def keep(value):\n"
            "    return value\n"
        ),
        "renamed already-private dependency": (
            "from .fills import _PersistentKeyMap as _Map\n"
            "def keep(value):\n"
            "    return value\n"
        ),
        "redundantly aliased private dependency": (
            "from .fills import _PersistentKeyMap as _PersistentKeyMap\n"
            "def keep(value):\n"
            "    return value\n"
        ),
        "public future binding left visible": (
            "from __future__ import annotations\ndef keep(value):\n    return value\n"
        ),
    }
    for label, source in rejected_sources.items():
        violations = _protection_call_binding_violations(ast.parse(source), path)
        import_rule_violations = [
            item for item in violations if "noncanonical import binding" in item
        ]
        assert len(import_rule_violations) == 1, label

    structural_rejections = {
        "aliased module import": (
            "import dataclasses as _dataclasses\ndef keep(value):\n    return value\n",
            "module import binding",
        ),
        "wildcard import": (
            "from dataclasses import *\ndef keep(value):\n    return value\n",
            "wildcard import",
        ),
        "duplicate canonical import": (
            "from dataclasses import dataclass as _dataclass\n"
            "from dataclasses import dataclass as _dataclass\n"
            "def keep(value):\n"
            "    return value\n",
            "duplicate import binding _dataclass",
        ),
        "post-import rebinding": (
            "from dataclasses import dataclass as _dataclass\n"
            "_dataclass = 1\n"
            "def keep(value):\n"
            "    return value\n",
            "rebound import binding _dataclass",
        ),
    }
    for label, (source, expected) in structural_rejections.items():
        violations = _protection_call_binding_violations(ast.parse(source), path)
        assert sum(expected in item for item in violations) == 1, label

    leaking_source = (
        "from dataclasses import dataclass\n"
        "from enum import Enum\n"
        "__all__ = ('Policy', 'Value')\n"
        "class Policy(str, Enum):\n"
        "    READY = 'READY'\n"
        "@dataclass(frozen=True, slots=True)\n"
        "class Value:\n"
        "    policy: Policy\n"
    )
    leaking_namespace: dict[str, object] = {}
    exec(
        compile(leaking_source, "<synthetic_protection_import_contract_leak>", "exec"),
        leaking_namespace,
    )
    leaking_public_names = {
        name for name in leaking_namespace if not name.startswith("_")
    }
    assert leaking_public_names - set(leaking_namespace["__all__"]) == {
        "Enum",
        "dataclass",
    }


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
            violations.extend(
                _protection_call_binding_violations(
                    tree,
                    path,
                    require_complete=True,
                )
            )
            violations.extend(
                _protection_state_commitment_binding_violations(tree, path)
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
import hashlib
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
