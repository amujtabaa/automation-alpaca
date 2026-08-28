"""Finite source and fail-closed runtime controls for the held SQLite suites."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping

import pytest

from app.execution_core.persistence.schema import (
    EXPECTED_EXECUTION_DDL_SHA256,
    SchemaDigestMismatchError,
    SchemaInstallError,
    _require_exact_approved_ddl_digest,
    install_schema,
    schema_ddl_digest,
)
from approved_schema_digest import require_approved_ddl_execution


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOKENS = ("sqlite3", "app.store", "SqliteStateStore")
_TOKEN_EXPECTATIONS = {
    # The count tuple follows _TOKENS. Exact counts make each justification
    # occurrence-bounded: adding another token to an allowed file fails closed.
    "app/execution_core/persistence/repository.py": (
        "production persistence boundary",
        (4, 0, 0),
    ),
    "app/execution_core/persistence/schema.py": (
        "schema definition and installer boundary",
        (2, 0, 0),
    ),
    "tests/execution_core/test_import_boundary.py": (
        "negative import-boundary assertions",
        (1, 0, 0),
    ),
    "tests/execution_core/test_persistence_checkpoint_codec.py": (
        "pure no-SQLite assertion",
        (1, 0, 0),
    ),
    "tests/execution_core/test_persistence_runtime_checkpoint_directness.py": (
        "pure directness assertion",
        (1, 0, 0),
    ),
    "tests/execution_core/test_persistence_runtime_checkpoint_pure.py": (
        "pure no-SQLite assertion",
        (2, 0, 0),
    ),
    "tests/execution_core/test_sqlite_boundary.py": (
        "this lexical control and its canaries",
        (13, 1, 1),
    ),
    "tests_gated/execution_core/test_persistence_directness.py": (
        "held SQLite proof",
        (14, 0, 0),
    ),
    "tests_gated/execution_core/test_persistence_repository.py": (
        "held SQLite proof",
        (12, 0, 0),
    ),
    "tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py": (
        "held SQLite proof",
        (32, 0, 0),
    ),
    "tests_gated/execution_core/test_persistence_schema.py": (
        "held SQLite proof",
        (142, 0, 0),
    ),
}


class _Connection:
    """No-I/O stand-in that proves a digest refusal precedes connection use."""

    def execute(self, sql: str, parameters: object = ()) -> object:
        del sql, parameters
        raise AssertionError(
            "authorization or digest refusal must precede connection access"
        )


def _token_violations(
    sources: Mapping[str, str],
    expectations: Mapping[str, tuple[str, tuple[int, int, int]]] | None = None,
) -> tuple[str, ...]:
    expected = expectations or {}
    violations: list[str] = []
    for label, source in sorted(sources.items()):
        actual_counts = tuple(source.count(token) for token in _TOKENS)
        expectation = expected.get(label)
        if expectation is None:
            violations.extend(
                f"{label}:{token}:expected=0:actual={actual}"
                for token, actual in zip(_TOKENS, actual_counts, strict=True)
                if actual
            )
            continue
        _, expected_counts = expectation
        violations.extend(
            f"{label}:{token}:expected={wanted}:actual={actual}"
            for token, wanted, actual in zip(
                _TOKENS, expected_counts, actual_counts, strict=True
            )
            if actual != wanted
        )
    return tuple(violations)


def _calls_in_scope(statements: list[ast.stmt]) -> tuple[ast.Call, ...]:
    calls: list[ast.Call] = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            calls.append(node)
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            del node

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            del node

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            del node

        def visit_Lambda(self, node: ast.Lambda) -> None:
            del node

    visitor = Visitor()
    for statement in statements:
        visitor.visit(statement)
    return tuple(sorted(calls, key=lambda call: (call.lineno, call.col_offset)))


def _import_bindings(
    tree: ast.Module,
) -> tuple[frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    sqlite_modules = {"sqlite3"}
    sqlite_connects: set[str] = set()
    gate_modules: set[str] = set()
    gate_functions = {"require_approved_ddl_execution"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlite3":
                    sqlite_modules.add(alias.asname or alias.name)
                elif alias.name == "approved_schema_digest":
                    gate_modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "sqlite3":
                sqlite_connects.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "connect"
                )
            elif node.module == "approved_schema_digest":
                gate_functions.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name == "require_approved_ddl_execution"
                )
    return (
        frozenset(sqlite_modules),
        frozenset(sqlite_connects),
        frozenset(gate_modules),
        frozenset(gate_functions),
    )


def _is_direct_connect(
    call: ast.Call,
    sqlite_modules: frozenset[str],
    sqlite_connects: frozenset[str],
) -> bool:
    return bool(
        (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "connect"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id in sqlite_modules
        )
        or (isinstance(call.func, ast.Name) and call.func.id in sqlite_connects)
    )


def _is_gate_call(
    call: ast.Call,
    gate_modules: frozenset[str],
    gate_functions: frozenset[str],
) -> bool:
    return bool(
        (isinstance(call.func, ast.Name) and call.func.id in gate_functions)
        or (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "require_approved_ddl_execution"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id in gate_modules
        )
    )


def _connection_gate_violations(source: str, label: str) -> tuple[str, ...]:
    tree = ast.parse(source, filename=label)
    sqlite_modules, sqlite_connects, gate_modules, gate_functions = _import_bindings(
        tree
    )
    violations: list[str] = []
    module_calls = _calls_in_scope(
        [
            statement
            for statement in tree.body
            if not isinstance(
                statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
        ]
    )
    for call in module_calls:
        if _is_direct_connect(call, sqlite_modules, sqlite_connects):
            violations.append(f"{label}:<module>:{call.lineno}")

    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        calls = _calls_in_scope(function.body)
        direct_connections = tuple(
            call
            for call in calls
            if _is_direct_connect(call, sqlite_modules, sqlite_connects)
        )
        if direct_connections and (
            not calls or not _is_gate_call(calls[0], gate_modules, gate_functions)
        ):
            violations.append(f"{label}:{function.name}:{direct_connections[0].lineno}")
    return tuple(sorted(violations))


def _installer_gate_order_is_exact(source: str) -> bool:
    tree = ast.parse(source, filename="schema.py")
    installers = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "install_schema"
    ]
    if len(installers) != 1:
        return False
    body = list(installers[0].body)
    if ast.get_docstring(installers[0]) is not None:
        body = body[1:]
    if len(body) < 3:
        return False
    digest_assignment, authorization_guard, digest_guard = body[:3]
    return bool(
        isinstance(digest_assignment, ast.Assign)
        and len(digest_assignment.targets) == 1
        and isinstance(digest_assignment.targets[0], ast.Name)
        and digest_assignment.targets[0].id == "actual_digest"
        and isinstance(digest_assignment.value, ast.Call)
        and isinstance(digest_assignment.value.func, ast.Name)
        and digest_assignment.value.func.id == "schema_ddl_digest"
        and not digest_assignment.value.args
        and not digest_assignment.value.keywords
        and isinstance(authorization_guard, ast.Expr)
        and isinstance(authorization_guard.value, ast.Call)
        and isinstance(authorization_guard.value.func, ast.Name)
        and authorization_guard.value.func.id
        == "_require_human_authorized_schema_install"
        and not authorization_guard.value.keywords
        and len(authorization_guard.value.args) == 1
        and isinstance(authorization_guard.value.args[0], ast.Name)
        and authorization_guard.value.args[0].id == "actual_digest"
        and isinstance(digest_guard, ast.Expr)
        and isinstance(digest_guard.value, ast.Call)
        and isinstance(digest_guard.value.func, ast.Name)
        and digest_guard.value.func.id == "_require_exact_approved_ddl_digest"
        and not digest_guard.value.keywords
        and len(digest_guard.value.args) == 2
        and all(isinstance(argument, ast.Name) for argument in digest_guard.value.args)
        and [argument.id for argument in digest_guard.value.args]  # type: ignore[union-attr]
        == ["approved_ddl_sha256", "actual_digest"]
    )


def _repository_sources() -> dict[str, str]:
    roots = (
        _REPO_ROOT / "app" / "execution_core",
        _REPO_ROOT / "tests" / "execution_core",
        _REPO_ROOT / "tests_gated",
    )
    return {
        path.relative_to(_REPO_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for root in roots
        for path in root.rglob("*.py")
    }


def test_lexical_boundary_has_a_failure_capable_canary() -> None:
    assert _token_violations({"ordinary.py": "import sqlite3\n"}) == (
        "ordinary.py:sqlite3:expected=0:actual=1",
    )


def test_allowed_production_path_rejects_an_added_token_occurrence() -> None:
    path = "app/execution_core/persistence/repository.py"
    reason, counts = _TOKEN_EXPECTATIONS[path]
    sources = {path: "sqlite3\nsqlite3.connect('candidate.db')\n"}
    expectations = {path: (reason, (1, counts[1], counts[2]))}
    assert _token_violations(sources, expectations) == (
        f"{path}:sqlite3:expected=1:actual=2",
    )


def test_sqlite_tokens_exist_only_at_justified_boundaries() -> None:
    sources = _repository_sources()
    assert _token_violations(sources, _TOKEN_EXPECTATIONS) == ()
    assert set(_TOKEN_EXPECTATIONS) <= set(sources)
    assert all(
        reason and len(counts) == len(_TOKENS)
        for reason, counts in _TOKEN_EXPECTATIONS.values()
    )


def test_connection_gate_detector_has_a_failure_capable_canary() -> None:
    mutant = """
def connection(path):
    return sqlite3.connect(path)
"""
    assert _connection_gate_violations(mutant, "mutant.py") == (
        "mutant.py:connection:3",
    )


@pytest.mark.parametrize(
    ("mutant", "expected_line"),
    [
        (
            "import sqlite3 as db\n\n"
            "def connection(path):\n"
            "    return db.connect(path)\n",
            4,
        ),
        (
            "from sqlite3 import connect\n\n"
            "def connection(path):\n"
            "    return connect(path)\n",
            4,
        ),
    ],
)
def test_connection_gate_detector_resolves_ordinary_import_aliases(
    mutant: str, expected_line: int
) -> None:
    assert _connection_gate_violations(mutant, "mutant.py") == (
        f"mutant.py:connection:{expected_line}",
    )


def test_connection_gate_detector_accepts_an_aliased_gate_first() -> None:
    source = (
        "import sqlite3 as db\n"
        "from approved_schema_digest import "
        "require_approved_ddl_execution as gate\n\n"
        "def connection(path):\n"
        "    gate()\n"
        "    return db.connect(path)\n"
    )
    assert _connection_gate_violations(source, "gated.py") == ()


def test_every_direct_connection_opener_calls_the_human_gate_first() -> None:
    gated_root = _REPO_ROOT / "tests_gated" / "execution_core"
    assert (
        tuple(
            violation
            for path in gated_root.glob("test_*.py")
            for violation in _connection_gate_violations(
                path.read_text(encoding="utf-8"), path.name
            )
        )
        == ()
    )


def test_schema_installer_authorization_and_digest_order_is_exact() -> None:
    source = (_REPO_ROOT / "app/execution_core/persistence/schema.py").read_text(
        encoding="utf-8"
    )
    assert _installer_gate_order_is_exact(source)
    assert not _installer_gate_order_is_exact(
        "def install_schema(connection, *, approved_ddl_sha256):\n"
        "    actual_digest = schema_ddl_digest()\n"
        "    _require_exact_approved_ddl_digest(approved_ddl_sha256, actual_digest)\n"
    )


def test_human_gate_is_closed_without_ameen_authorization() -> None:
    with pytest.raises(RuntimeError, match="HUMAN-GATE pending"):
        require_approved_ddl_execution()


def test_matching_expected_digest_cannot_bypass_closed_human_gate() -> None:
    with pytest.raises(SchemaInstallError, match="HUMAN-GATE pending"):
        install_schema(_Connection(), approved_ddl_sha256=EXPECTED_EXECUTION_DDL_SHA256)


def test_one_character_digest_mismatch_is_refused_without_connection_use() -> None:
    actual = schema_ddl_digest()
    wrong = ("0" if actual[0] != "0" else "1") + actual[1:]
    with pytest.raises(SchemaDigestMismatchError):
        _require_exact_approved_ddl_digest(wrong, actual)
