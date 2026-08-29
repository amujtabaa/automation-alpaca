"""Small, pure controls for repository write and DDL-approval boundaries."""

from __future__ import annotations

import ast
from copy import copy, deepcopy
import inspect
from pathlib import Path

import pytest

import app.execution_core.persistence.repository as repository
import persistence_setup_support as setup_support


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SETUP_ISSUER = "_issue_setup_write_capability"


class _Connection:
    """No-I/O stand-in: a refusal test fails if repository SQL is reached."""

    def execute(self, sql: str, parameters: object = ()) -> object:
        del sql, parameters
        raise AssertionError("capability refusal must occur before SQL dispatch")


class _TransactionalConnection(_Connection):
    def __init__(self, *, in_transaction: bool) -> None:
        self.in_transaction = in_transaction


def _literal_text(expression: ast.expr) -> str | None:
    return (
        expression.value
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str)
        else None
    )


def _imports_setup_support(source: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import) and any(
            alias.name == "persistence_setup_support" for alias in node.names
        ):
            return True
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "persistence_setup_support"
        ):
            return True
    return False


def _setup_issuer_reference_kinds(source: str) -> frozenset[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == _SETUP_ISSUER:
                found.add("definition")
        elif isinstance(node, ast.Attribute) and node.attr == _SETUP_ISSUER:
            found.add("attribute")
        elif isinstance(node, ast.Name) and node.id == _SETUP_ISSUER:
            found.add("name")
        elif isinstance(node, ast.ImportFrom) and any(
            alias.name == _SETUP_ISSUER for alias in node.names
        ):
            found.add("from-import")
        elif (
            isinstance(node, ast.Call)
            and len(node.args) >= 2
            and _literal_text(node.args[1]) == _SETUP_ISSUER
            and (
                isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                or isinstance(node.func, ast.Attribute)
                and node.func.attr == "getattr"
            )
        ):
            found.add("dynamic-getattr")
    return frozenset(found)


def _uses_self_approved_digest(source: str) -> bool:
    """Detect the exact non-evasive self-approval form rejected since REV-0078."""

    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            value = keyword.value
            if (
                keyword.arg == "approved_ddl_sha256"
                and isinstance(value, ast.Call)
                and (
                    isinstance(value.func, ast.Name)
                    and value.func.id == "schema_ddl_digest"
                    or isinstance(value.func, ast.Attribute)
                    and value.func.attr == "schema_ddl_digest"
                )
            ):
                return True
    return False


def test_every_exported_repository_mutator_requires_keyword_capability() -> None:
    mutators = {
        name
        for name in repository.__all__
        if name.startswith(("store_", "advance_", "retire_", "claim_", "finalize_"))
    }
    assert mutators
    for name in mutators:
        capability = inspect.signature(getattr(repository, name)).parameters.get(
            "capability"
        )
        assert capability is not None, name
        assert capability.kind is inspect.Parameter.KEYWORD_ONLY, name
        assert capability.default is inspect.Parameter.empty, name


def test_setup_capability_is_connection_bound_and_constructor_closed() -> None:
    connection = _Connection()
    other_connection = _Connection()
    capability = setup_support.issue_setup_write_capability(connection)

    assert type(capability) is repository._SetupWriteCapability
    repository._require_write_capability(connection, capability)
    with pytest.raises(ValueError, match="not current"):
        repository._require_write_capability(other_connection, capability)
    with pytest.raises(TypeError, match="factory-issued"):
        repository._SetupWriteCapability()
    with pytest.raises(TypeError, match="write capability"):
        repository._require_write_capability(connection, object())


def test_runtime_capability_has_one_repository_owned_lease_route() -> None:
    app_root = Path(repository.__file__).resolve().parents[1]
    assert {
        path.relative_to(app_root).as_posix()
        for path in app_root.rglob("*.py")
        if "object.__new__(_RuntimeWriteCapability)" in path.read_text(encoding="utf-8")
    } == {"persistence/repository.py"}


def test_runtime_lease_requires_transaction_and_rejects_overlap() -> None:
    connection = _TransactionalConnection(in_transaction=False)
    with pytest.raises(ValueError, match="active transaction"):
        repository._activate_runtime_write_lease(connection)

    connection.in_transaction = True
    capability = repository._activate_runtime_write_lease(connection)
    assert type(capability) is repository._RuntimeWriteCapability
    repository._require_write_capability(connection, capability)
    with pytest.raises(ValueError, match="already active"):
        repository._activate_runtime_write_lease(connection)

    repository._retire_runtime_write_lease(connection, capability)
    with pytest.raises(ValueError, match="not current"):
        repository._require_write_capability(connection, capability)


def test_runtime_lease_is_exact_connection_bound_and_noncopyable() -> None:
    connection = _TransactionalConnection(in_transaction=True)
    other = _TransactionalConnection(in_transaction=True)
    capability = repository._activate_runtime_write_lease(connection)

    with pytest.raises(ValueError, match="not current"):
        repository._require_write_capability(other, capability)
    with pytest.raises(TypeError, match="cannot be copied"):
        copy(capability)
    with pytest.raises(TypeError, match="cannot be copied"):
        deepcopy(capability)
    with pytest.raises(TypeError, match="cannot be reduced"):
        capability.__reduce__()
    with pytest.raises(TypeError, match="cannot be reduced"):
        capability.__reduce_ex__(4)

    repository._retire_runtime_write_lease(connection, capability)


def test_retired_runtime_lease_stays_stale_after_next_transaction() -> None:
    connection = _TransactionalConnection(in_transaction=True)
    first = repository._activate_runtime_write_lease(connection)
    repository._retire_runtime_write_lease(connection, first)

    connection.in_transaction = False
    with pytest.raises(ValueError, match="not current"):
        repository._require_write_capability(connection, first)
    connection.in_transaction = True
    second = repository._activate_runtime_write_lease(connection)
    repository._require_write_capability(connection, second)
    with pytest.raises(ValueError, match="not current"):
        repository._require_write_capability(connection, first)
    with pytest.raises(ValueError, match="not active"):
        repository._retire_runtime_write_lease(connection, first)
    repository._retire_runtime_write_lease(connection, second)


def test_runtime_lease_rejects_forged_exact_type() -> None:
    connection = _TransactionalConnection(in_transaction=True)
    forged = object.__new__(repository._RuntimeWriteCapability)
    with pytest.raises(ValueError, match="not current"):
        repository._require_write_capability(connection, forged)
    with pytest.raises(ValueError, match="not active"):
        repository._retire_runtime_write_lease(connection, forged)


def test_setup_support_importers_have_the_frozen_direction() -> None:
    roots = (
        _REPO_ROOT / "tests" / "execution_core",
        _REPO_ROOT / "tests_gated" / "execution_core",
    )
    importers = {
        path.relative_to(_REPO_ROOT).as_posix()
        for root in roots
        for path in root.glob("*.py")
        if _imports_setup_support(path.read_text(encoding="utf-8"))
    }
    assert importers == {
        "tests/execution_core/test_persistence_input_receipt.py",
        "tests/execution_core/test_persistence_write_capability.py",
        "tests_gated/execution_core/test_persistence_directness.py",
        "tests_gated/execution_core/test_persistence_repository.py",
        "tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py",
    }


def test_setup_issuer_has_one_support_route_and_detector_can_fail() -> None:
    app_root = Path(repository.__file__).resolve().parents[1]
    runtime_sites = {
        path.relative_to(app_root).as_posix(): kinds
        for path in app_root.rglob("*.py")
        if (kinds := _setup_issuer_reference_kinds(path.read_text(encoding="utf-8")))
    }
    assert runtime_sites == {"persistence/repository.py": frozenset({"definition"})}

    support_source = (
        _REPO_ROOT / "tests/execution_core/persistence_setup_support.py"
    ).read_text(encoding="utf-8")
    assert _setup_issuer_reference_kinds(support_source) == frozenset({"attribute"})
    mutant = f"""
from app.execution_core.persistence.repository import {_SETUP_ISSUER} as mint
import app.execution_core.persistence.repository as repository
mint(connection)
repository.{_SETUP_ISSUER}(connection)
getattr(repository, "{_SETUP_ISSUER}")(connection)
"""
    assert _setup_issuer_reference_kinds(mutant) == frozenset(
        {"from-import", "attribute", "dynamic-getattr"}
    )


def test_gated_suites_never_compute_their_own_approval_digest() -> None:
    gated_root = _REPO_ROOT / "tests_gated" / "execution_core"
    assert {
        path.name
        for path in gated_root.glob("test_*.py")
        if _uses_self_approved_digest(path.read_text(encoding="utf-8"))
    } == set()
    assert _uses_self_approved_digest(
        "install_schema(connection, approved_ddl_sha256=schema_ddl_digest())"
    )
    assert _uses_self_approved_digest(
        "schema.install_schema(connection, "
        "approved_ddl_sha256=schema.schema_ddl_digest())"
    )
