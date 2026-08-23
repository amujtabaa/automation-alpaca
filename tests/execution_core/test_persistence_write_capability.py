"""Static and pure boundary controls for WO-0168a write capabilities."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import app.execution_core.persistence.repository as repository
import persistence_setup_support as setup_support


_SETUP_ISSUER = "_issue_setup_write_capability"


class _Connection:
    """A no-I/O connection stand-in used only before repository SQL dispatch."""

    def execute(self, sql: str, parameters: object = ()) -> object:
        del sql, parameters
        raise AssertionError("capability refusal must occur before SQL dispatch")


def _mutator_names() -> set[str]:
    return {
        name
        for name in repository.__all__
        if name.startswith(("store_", "advance_", "retire_", "claim_", "finalize_"))
    }


def _setup_issuer_reference_kinds(source: str) -> frozenset[str]:
    """Classify direct and aliased source routes to the private setup issuer."""

    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == _SETUP_ISSUER:
                found.add("definition")
        elif isinstance(node, ast.Attribute) and node.attr == _SETUP_ISSUER:
            found.add("attribute")
        elif isinstance(node, ast.Name) and node.id == _SETUP_ISSUER:
            found.add("name")
        elif isinstance(node, ast.ImportFrom):
            if any(alias.name == _SETUP_ISSUER for alias in node.names):
                found.add("from-import")
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == _SETUP_ISSUER
        ):
            found.add("dynamic-getattr")
    return frozenset(found)


def _repository_mutator_calls_missing_capability(source: str) -> tuple[str, ...]:
    """Return direct fixture mutators that bypass the mandatory keyword token."""

    tree = ast.parse(source)
    missing: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = node.func.value
        if (
            not isinstance(receiver, ast.Name)
            or receiver.id != "repository"
            or not node.func.attr.startswith(
                ("store_", "advance_", "retire_", "claim_", "finalize_")
            )
        ):
            continue
        if not any(keyword.arg == "capability" for keyword in node.keywords):
            missing.append(node.func.attr)
    return tuple(sorted(missing))


def test_every_exported_repository_mutator_requires_one_keyword_capability() -> None:
    for name in _mutator_names():
        signature = inspect.signature(getattr(repository, name))
        capability = signature.parameters.get("capability")
        assert capability is not None, name
        assert capability.kind is inspect.Parameter.KEYWORD_ONLY, name
        assert capability.default is inspect.Parameter.empty, name


def test_setup_capability_is_exact_connection_bound_and_constructor_closed() -> None:
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


def test_runtime_capability_has_no_issuance_route_in_wo0168a() -> None:
    app_root = Path(repository.__file__).resolve().parents[1]
    runtime_mint_sites = {
        path.relative_to(app_root).as_posix()
        for path in app_root.rglob("*.py")
        if "object.__new__(_RuntimeWriteCapability)" in path.read_text(encoding="utf-8")
    }

    assert runtime_mint_sites == set()


def test_setup_issuer_and_support_imports_have_the_frozen_direction() -> None:
    test_root = Path(__file__).resolve().parent
    importers = {
        path.name
        for path in test_root.glob("test_*.py")
        if "persistence_setup_support" in path.read_text(encoding="utf-8")
    }
    assert importers <= {
        "test_persistence_schema.py",
        "test_persistence_repository.py",
        "test_persistence_directness.py",
        "test_persistence_input_receipt.py",
        "test_persistence_write_capability.py",
    }
    assert "test_persistence_write_capability.py" in importers

    repository_tree = ast.parse(inspect.getsource(repository))
    issuer_definitions = {
        node.name
        for node in repository_tree.body
        if isinstance(node, ast.FunctionDef) and "setup_write_capability" in node.name
    }
    assert issuer_definitions == {"_issue_setup_write_capability"}

    app_root = Path(repository.__file__).resolve().parents[1]
    forbidden_runtime_imports = {
        path.relative_to(app_root).as_posix()
        for path in app_root.rglob("*.py")
        if "persistence_setup_support" in path.read_text(encoding="utf-8")
    }
    assert forbidden_runtime_imports == set()


def test_setup_issuer_has_one_test_support_route_and_alias_detector_is_failure_capable() -> (
    None
):
    app_root = Path(repository.__file__).resolve().parents[1]
    runtime_issuer_sites = {
        path.relative_to(app_root).as_posix(): _setup_issuer_reference_kinds(
            path.read_text(encoding="utf-8")
        )
        for path in app_root.rglob("*.py")
        if _setup_issuer_reference_kinds(path.read_text(encoding="utf-8"))
    }
    assert runtime_issuer_sites == {
        "persistence/repository.py": frozenset({"definition"})
    }

    test_root = Path(__file__).resolve().parent
    test_issuer_sites = {
        path.name: _setup_issuer_reference_kinds(path.read_text(encoding="utf-8"))
        for path in test_root.glob("*.py")
        if _setup_issuer_reference_kinds(path.read_text(encoding="utf-8"))
    }
    assert test_issuer_sites == {
        "persistence_setup_support.py": frozenset({"attribute"})
    }

    mutant = """
from app.execution_core.persistence.repository import _issue_setup_write_capability as mint
import app.execution_core.persistence.repository as repository

mint(connection)
repository._issue_setup_write_capability(connection)
getattr(repository, "_issue_setup_write_capability")(connection)
"""
    assert _setup_issuer_reference_kinds(mutant) == frozenset(
        {"from-import", "attribute", "dynamic-getattr"}
    )


def test_every_persistence_fixture_passes_setup_capability_to_each_direct_mutator() -> (
    None
):
    for fixture_name in (
        "test_persistence_repository.py",
        "test_persistence_directness.py",
    ):
        fixture_path = Path(__file__).with_name(fixture_name)
        fixture_source = fixture_path.read_text(encoding="utf-8")
        assert _repository_mutator_calls_missing_capability(fixture_source) == ()

    mutant = """
repository.store_scope(connection, record)
repository.load_scope(connection, 1)
"""
    assert _repository_mutator_calls_missing_capability(mutant) == ("store_scope",)
