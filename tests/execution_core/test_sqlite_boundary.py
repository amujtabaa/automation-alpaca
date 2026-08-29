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
import approved_schema_digest as gate_module
from approved_schema_digest import (
    open_approved_sqlite_connection,
    require_approved_ddl_execution,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOKENS = ("sqlite3", "app.store", "SqliteStateStore")
_TOKEN_ALLOWLIST = {
    "app/execution_core/persistence/repository.py": "production module-name inspection",
    "app/execution_core/persistence/schema.py": "schema protocol documentation",
    "tests/execution_core/approved_schema_digest.py": "single gated connection factory",
    "tests/execution_core/test_import_boundary.py": "negative import assertions",
    "tests/execution_core/test_persistence_checkpoint_codec.py": "pure no-SQLite assertion",
    "tests/execution_core/test_persistence_runtime_checkpoint_directness.py": (
        "pure directness assertion"
    ),
    "tests/execution_core/test_persistence_runtime_checkpoint_pure.py": (
        "pure no-SQLite assertion"
    ),
    "tests/execution_core/test_sqlite_boundary.py": "this control and its canaries",
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
        raise AssertionError(
            "authorization or digest refusal must precede connection access"
        )


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


def _annotation_node_ids(tree: ast.Module) -> frozenset[int]:
    roots: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.arg, ast.AnnAssign)) and node.annotation is not None:
            roots.append(node.annotation)
        elif (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.returns is not None
        ):
            roots.append(node.returns)
    return frozenset(id(child) for root in roots for child in ast.walk(root))


def _is_sqlite_module(name: str | None) -> bool:
    return name is not None and (name == "sqlite3" or name.startswith("sqlite3."))


def _direct_connection_capability_violations(
    source: str,
    label: str,
    *,
    allow_sqlite_import: bool,
) -> tuple[str, ...]:
    tree = ast.parse(source, filename=label)
    annotation_nodes = _annotation_node_ids(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if not allow_sqlite_import and any(
                _is_sqlite_module(alias.name) for alias in node.names
            ):
                violations.append(f"{label}:sqlite3-import:{node.lineno}")
        elif isinstance(node, ast.ImportFrom):
            if _is_sqlite_module(node.module) and any(
                alias.name in {"*", "connect", "Connection"} for alias in node.names
            ):
                violations.append(f"{label}:connection-import:{node.lineno}")
        elif isinstance(node, ast.Attribute) and node.attr == "connect":
            violations.append(f"{label}:connect-attribute:{node.lineno}")
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "Connection"
            and id(node) not in annotation_nodes
        ):
            violations.append(f"{label}:Connection:{node.lineno}")
    return tuple(sorted(violations))


def _approved_connection_helper_is_exact(source: str) -> bool:
    tree = ast.parse(source, filename="approved_schema_digest.py")
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "open_approved_sqlite_connection"
    ]
    if len(functions) != 1:
        return False
    body = list(functions[0].body)
    if ast.get_docstring(functions[0]) is not None:
        body = body[1:]
    if len(body) != 2:
        return False
    gate, connection = body
    if not (
        isinstance(connection, ast.Return)
        and isinstance(connection.value, ast.Call)
        and isinstance(connection.value.func, ast.Attribute)
    ):
        return False
    annotation_nodes = _annotation_node_ids(tree)
    sqlite_imports = [
        alias
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
        if _is_sqlite_module(alias.name)
    ]
    connect_attributes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "connect"
    ]
    forbidden_connection_imports = [
        alias
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and _is_sqlite_module(node.module)
        for alias in node.names
        if alias.name in {"*", "connect", "Connection"}
    ]
    executable_connection_attributes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "Connection"
        and id(node) not in annotation_nodes
    ]
    return bool(
        len(sqlite_imports) == 1
        and sqlite_imports[0].name == "sqlite3"
        and sqlite_imports[0].asname is None
        and len(connect_attributes) == 1
        and connect_attributes[0] is connection.value.func
        and not forbidden_connection_imports
        and not executable_connection_attributes
        and isinstance(gate, ast.Expr)
        and isinstance(gate.value, ast.Call)
        and isinstance(gate.value.func, ast.Name)
        and gate.value.func.id == "require_approved_ddl_execution"
        and not gate.value.args
        and not gate.value.keywords
        and isinstance(connection.value.func.value, ast.Name)
        and connection.value.func.value.id == "sqlite3"
        and connection.value.func.attr == "connect"
        and len(connection.value.args) == 1
        and isinstance(connection.value.args[0], ast.Name)
        and connection.value.args[0].id == "database"
        and not connection.value.keywords
    )


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
        "ordinary.py:sqlite3",
    )


def test_lexical_allowlist_does_not_claim_semantic_connection_control() -> None:
    path = "app/execution_core/persistence/repository.py"
    baseline = "# sqlite3\n# sqlite3\n# sqlite3\n# sqlite3\n"
    mutant = "import sqlite3\nsqlite3.connect('candidate.db')\n# sqlite3\n# sqlite3\n"
    assert baseline.count("sqlite3") == mutant.count("sqlite3")
    assert _token_violations({path: mutant}, _TOKEN_ALLOWLIST) == ()
    assert _direct_connection_capability_violations(
        mutant, path, allow_sqlite_import=False
    ) == (
        f"{path}:connect-attribute:2",
        f"{path}:sqlite3-import:1",
    )


def test_sqlite_tokens_exist_only_at_justified_boundaries() -> None:
    sources = _repository_sources()
    assert _token_violations(sources, _TOKEN_ALLOWLIST) == ()
    assert set(_TOKEN_ALLOWLIST) <= set(sources) and all(_TOKEN_ALLOWLIST.values())


@pytest.mark.parametrize(
    ("mutant", "expected"),
    [
        (
            "import sqlite3 as db\ndef connection(path): return db.connect(path)\n",
            ("mutant.py:connect-attribute:2",),
        ),
        (
            "from sqlite3 import connect\ndef connection(path): return connect(path)\n",
            ("mutant.py:connection-import:1",),
        ),
        (
            "import sqlite3 as db\n\n"
            "Connection = db.Connection\n"
            "def direct(path):\n    return db.Connection(path)\n"
            "def aliased(path):\n    return Connection(path)\n",
            ("mutant.py:Connection:3", "mutant.py:Connection:5"),
        ),
        (
            "from sqlite3.dbapi2 import *\n"
            "def connection(path):\n    return Connection(path)\n",
            ("mutant.py:connection-import:1",),
        ),
    ],
)
def test_direct_connection_capability_detector_kills_ordinary_aliases(
    mutant: str, expected: tuple[str, ...]
) -> None:
    assert (
        _direct_connection_capability_violations(
            mutant, "mutant.py", allow_sqlite_import=True
        )
        == expected
    )


def test_production_modules_have_no_direct_sqlite_connection_capability() -> None:
    for relative in (
        "app/execution_core/persistence/repository.py",
        "app/execution_core/persistence/schema.py",
    ):
        source = (_REPO_ROOT / relative).read_text(encoding="utf-8")
        assert (
            _direct_connection_capability_violations(
                source, relative, allow_sqlite_import=False
            )
            == ()
        )


def test_gated_suites_open_only_through_the_central_helper() -> None:
    gated_root = _REPO_ROOT / "tests_gated" / "execution_core"
    violations = tuple(
        violation
        for path in gated_root.glob("test_*.py")
        for violation in _direct_connection_capability_violations(
            path.read_text(encoding="utf-8"),
            path.relative_to(_REPO_ROOT).as_posix(),
            allow_sqlite_import=True,
        )
    )
    assert violations == ()


def test_central_connection_helper_is_exact_and_conditional_canary_fails() -> None:
    source = (_REPO_ROOT / "tests/execution_core/approved_schema_digest.py").read_text(
        encoding="utf-8"
    )
    assert _approved_connection_helper_is_exact(source)
    assert not _approved_connection_helper_is_exact(
        "import sqlite3\n\n"
        "def open_approved_sqlite_connection(database, enforce_gate=True):\n"
        "    if enforce_gate:\n"
        "        require_approved_ddl_execution()\n"
        "    return sqlite3.connect(database)\n"
    )
    assert not _approved_connection_helper_is_exact(
        source + "\n\ndef bypass_connection(database):\n"
        "    return sqlite3.connect(database)\n"
    )
    assert not _approved_connection_helper_is_exact(
        source + "\nConnection = sqlite3.Connection\n"
        "def bypass_connection(database):\n    return Connection(database)\n"
    )
    assert not _approved_connection_helper_is_exact(
        source + "\nfrom sqlite3 import *\n"
    )


def test_central_connection_helper_refuses_before_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection_attempted = False

    def forbidden_connect(database: object) -> None:
        del database
        nonlocal connection_attempted
        connection_attempted = True
        raise AssertionError("closed human gate must dominate connection access")

    monkeypatch.setattr(gate_module.sqlite3, "connect", forbidden_connect)
    with pytest.raises(RuntimeError, match="HUMAN-GATE pending"):
        open_approved_sqlite_connection("must-not-exist.db")
    assert connection_attempted is False


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


def test_expected_digest_is_the_exact_static_ddl_identity() -> None:
    assert EXPECTED_EXECUTION_DDL_SHA256 == schema_ddl_digest()


def test_one_character_digest_mismatch_is_refused_without_connection_use() -> None:
    actual = schema_ddl_digest()
    wrong = ("0" if actual[0] != "0" else "1") + actual[1:]
    with pytest.raises(SchemaDigestMismatchError):
        _require_exact_approved_ddl_digest(wrong, actual)
