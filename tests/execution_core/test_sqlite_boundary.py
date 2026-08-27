"""Finite source and fail-closed runtime controls for the held SQLite suites."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping

import pytest

from app.execution_core.persistence.schema import (
    SchemaDigestMismatchError,
    install_schema,
    schema_ddl_digest,
)
from approved_schema_digest import require_approved_ddl_execution


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOKENS = ("sqlite3", "app.store", "SqliteStateStore")
_TOKEN_ALLOWLIST = {
    "app/execution_core/persistence/repository.py": "production persistence boundary",
    "app/execution_core/persistence/schema.py": "schema definition and installer boundary",
    "tests/execution_core/test_import_boundary.py": "negative import-boundary assertions",
    "tests/execution_core/test_persistence_checkpoint_codec.py": "pure no-SQLite assertion",
    "tests/execution_core/test_persistence_runtime_checkpoint_directness.py": (
        "pure directness assertion"
    ),
    "tests/execution_core/test_persistence_runtime_checkpoint_pure.py": (
        "pure no-SQLite assertion"
    ),
    "tests/execution_core/test_sqlite_boundary.py": "this lexical control and its canary",
    "tests_gated/execution_core/test_persistence_directness.py": "held SQLite proof",
    "tests_gated/execution_core/test_persistence_repository.py": "held SQLite proof",
    "tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py": (
        "held SQLite proof"
    ),
    "tests_gated/execution_core/test_persistence_schema.py": "held SQLite proof",
}


class _Connection:
    """No-I/O stand-in that proves a digest refusal precedes connection use."""

    def execute(self, sql: str, parameters: object = ()) -> object:
        del sql, parameters
        raise AssertionError("digest refusal must precede connection access")


def _token_violations(
    sources: Mapping[str, str],
    allowlist: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    permitted = frozenset(allowlist or {})
    return tuple(
        f"{label}:{token}"
        for label, source in sorted(sources.items())
        if label not in permitted
        for token in _TOKENS
        if token in source
    )


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


def _is_direct_connect(call: ast.Call) -> bool:
    return bool(
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "connect"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "sqlite3"
    )


def _is_gate_call(call: ast.Call) -> bool:
    return bool(
        isinstance(call.func, ast.Name)
        and call.func.id == "require_approved_ddl_execution"
    )


def _connection_gate_violations(source: str, label: str) -> tuple[str, ...]:
    tree = ast.parse(source, filename=label)
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
        if _is_direct_connect(call):
            violations.append(f"{label}:<module>:{call.lineno}")

    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        calls = _calls_in_scope(function.body)
        direct_connections = tuple(call for call in calls if _is_direct_connect(call))
        if direct_connections and (not calls or not _is_gate_call(calls[0])):
            violations.append(f"{label}:{function.name}:{direct_connections[0].lineno}")
    return tuple(sorted(violations))


def _installer_digest_order_is_exact(source: str) -> bool:
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
    if len(body) < 2:
        return False
    digest_assignment, guard_statement = body[:2]
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
        and isinstance(guard_statement, ast.Expr)
        and isinstance(guard_statement.value, ast.Call)
        and isinstance(guard_statement.value.func, ast.Name)
        and guard_statement.value.func.id == "_require_exact_approved_ddl_digest"
        and not guard_statement.value.keywords
        and len(guard_statement.value.args) == 2
        and all(
            isinstance(argument, ast.Name) for argument in guard_statement.value.args
        )
        and [argument.id for argument in guard_statement.value.args]  # type: ignore[union-attr]
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
        "ordinary.py:sqlite3",
    )


def test_sqlite_tokens_exist_only_at_justified_boundaries() -> None:
    sources = _repository_sources()
    assert _token_violations(sources, _TOKEN_ALLOWLIST) == ()
    assert set(_TOKEN_ALLOWLIST) <= set(sources)
    assert all(_TOKEN_ALLOWLIST.values())


def test_connection_gate_detector_has_a_failure_capable_canary() -> None:
    mutant = """
def connection(path):
    return sqlite3.connect(path)
"""
    assert _connection_gate_violations(mutant, "mutant.py") == (
        "mutant.py:connection:3",
    )


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


def test_schema_installer_digest_refusal_is_first_and_can_fail() -> None:
    source = (_REPO_ROOT / "app/execution_core/persistence/schema.py").read_text(
        encoding="utf-8"
    )
    assert _installer_digest_order_is_exact(source)
    assert not _installer_digest_order_is_exact(
        "def install_schema(connection, *, approved_ddl_sha256):\n"
        "    connection.execute('BEGIN')\n"
    )


def test_human_gate_is_closed_without_ameen_authorization() -> None:
    with pytest.raises(RuntimeError, match="HUMAN-GATE pending"):
        require_approved_ddl_execution()


def test_one_character_digest_mismatch_refuses_before_connection_use() -> None:
    actual = schema_ddl_digest()
    wrong = ("0" if actual[0] != "0" else "1") + actual[1:]
    with pytest.raises(SchemaDigestMismatchError):
        install_schema(_Connection(), approved_ddl_sha256=wrong)  # type: ignore[arg-type]
