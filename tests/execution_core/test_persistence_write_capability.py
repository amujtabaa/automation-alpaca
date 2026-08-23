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


def _assignment_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    """Return simple names written by one source assignment."""

    targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
    return tuple(target.id for target in targets if isinstance(target, ast.Name))


def _mutator_name_from_expression(
    expression: ast.expr,
    *,
    repository_aliases: frozenset[str],
    mutator_aliases: dict[str, str],
) -> str | None:
    """Resolve the deliberately small set of permitted fixture mutator aliases."""

    if isinstance(expression, ast.Name):
        return mutator_aliases.get(expression.id)
    if (
        isinstance(expression, ast.Attribute)
        and isinstance(expression.value, ast.Name)
        and expression.value.id in repository_aliases
        and expression.attr in _mutator_names()
    ):
        return expression.attr
    if (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "getattr"
        and len(expression.args) == 2
        and isinstance(expression.args[0], ast.Name)
        and expression.args[0].id in repository_aliases
        and isinstance(expression.args[1], ast.Constant)
        and isinstance(expression.args[1].value, str)
        and expression.args[1].value in _mutator_names()
    ):
        return expression.args[1].value
    return None


def _fixture_mutator_aliases(
    tree: ast.Module,
) -> tuple[frozenset[str], dict[str, str]]:
    """Resolve repository/module/callable aliases without accepting dynamic routes."""

    repository_aliases = {"repository"}
    mutator_aliases: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "app.execution_core.persistence.repository":
                        name = alias.asname or alias.name.rsplit(".", 1)[-1]
                        if name not in repository_aliases:
                            repository_aliases.add(name)
                            changed = True
                continue
            if isinstance(node, ast.ImportFrom):
                if node.module != "app.execution_core.persistence.repository":
                    continue
                for alias in node.names:
                    if alias.name in _mutator_names():
                        name = alias.asname or alias.name
                        if mutator_aliases.get(name) != alias.name:
                            mutator_aliases[name] = alias.name
                            changed = True
                continue
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            if value is None:
                continue
            for target in _assignment_names(node):
                if isinstance(value, ast.Name) and value.id in repository_aliases:
                    if target not in repository_aliases:
                        repository_aliases.add(target)
                        changed = True
                    continue
                mutator_name = _mutator_name_from_expression(
                    value,
                    repository_aliases=frozenset(repository_aliases),
                    mutator_aliases=mutator_aliases,
                )
                if (
                    mutator_name is not None
                    and mutator_aliases.get(target) != mutator_name
                ):
                    mutator_aliases[target] = mutator_name
                    changed = True
    return frozenset(repository_aliases), mutator_aliases


def _same_source_expression(left: ast.expr, right: ast.expr) -> bool:
    return ast.dump(left, include_attributes=False) == ast.dump(
        right, include_attributes=False
    )


def _is_issued_setup_capability(
    expression: ast.expr,
    *,
    connection: ast.expr,
) -> bool:
    """Accept only the named fixture wrapper bound to this exact connection node."""

    return (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "_setup_write_capability"
        and len(expression.args) == 1
        and not expression.keywords
        and _same_source_expression(expression.args[0], connection)
    )


def _fixture_mutator_capability_violations(source: str) -> tuple[str, ...]:
    """Return direct fixture mutators lacking an issued, connection-bound token.

    The check deliberately resolves the small alias surface ordinary fixtures can
    use.  Higher-order dispatch is permitted only through the separately pinned
    ``_apply_mutator`` helper below, so a raw token or a callable alias cannot
    silently evade the fixture gate.
    """

    tree = ast.parse(source)
    repository_aliases, mutator_aliases = _fixture_mutator_aliases(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        mutator_name = _mutator_name_from_expression(
            node.func,
            repository_aliases=repository_aliases,
            mutator_aliases=mutator_aliases,
        )
        if mutator_name is None:
            continue
        capability_keywords = [
            keyword.value for keyword in node.keywords if keyword.arg == "capability"
        ]
        if (
            len(node.args) < 1
            or len(capability_keywords) != 1
            or not _is_issued_setup_capability(
                capability_keywords[0], connection=node.args[0]
            )
        ):
            violations.append(mutator_name)
    return tuple(sorted(violations))


def _fixture_helper_shape_is_exact(source: str) -> bool:
    """Pin the only allowed higher-order fixture writer to the named issuer."""

    tree = ast.parse(source)
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    setup_helper = functions.get("_setup_write_capability")
    apply_helper = functions.get("_apply_mutator")
    if setup_helper is None or apply_helper is None:
        return False

    def body_without_docstring(function: ast.FunctionDef) -> list[ast.stmt]:
        body = list(function.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
        return body

    setup_body = body_without_docstring(setup_helper)
    if (
        len(setup_helper.args.args) != 1
        or setup_helper.args.args[0].arg != "connection"
        or len(setup_body) != 1
        or not isinstance(setup_body[0], ast.Return)
        or not isinstance(setup_body[0].value, ast.Call)
    ):
        return False
    setup_call = setup_body[0].value
    if (
        not isinstance(setup_call.func, ast.Name)
        or setup_call.func.id != "issue_setup_write_capability"
        or len(setup_call.args) != 1
        or setup_call.keywords
        or not isinstance(setup_call.args[0], ast.Name)
        or setup_call.args[0].id != "connection"
    ):
        return False

    apply_body = body_without_docstring(apply_helper)
    if (
        len(apply_helper.args.args) < 2
        or apply_helper.args.args[0].arg != "connection"
        or apply_helper.args.args[1].arg != "operation"
        or len(apply_body) != 1
        or not isinstance(apply_body[0], ast.Return)
        or not isinstance(apply_body[0].value, ast.Call)
    ):
        return False
    apply_call = apply_body[0].value
    if (
        not isinstance(apply_call.func, ast.Name)
        or apply_call.func.id != "operation"
        or not apply_call.args
        or not isinstance(apply_call.args[0], ast.Name)
        or apply_call.args[0].id != "connection"
        or not any(
            isinstance(argument, ast.Starred)
            and isinstance(argument.value, ast.Name)
            and argument.value.id == "arguments"
            for argument in apply_call.args[1:]
        )
    ):
        return False
    capability_keywords = [
        keyword.value for keyword in apply_call.keywords if keyword.arg == "capability"
    ]
    return len(capability_keywords) == 1 and _is_issued_setup_capability(
        capability_keywords[0], connection=apply_call.args[0]
    )


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


def test_every_persistence_fixture_passes_issued_setup_capability_to_each_mutator() -> (
    None
):
    for fixture_name in (
        "test_persistence_repository.py",
        "test_persistence_directness.py",
    ):
        fixture_path = Path(__file__).with_name(fixture_name)
        fixture_source = fixture_path.read_text(encoding="utf-8")
        assert _fixture_helper_shape_is_exact(fixture_source)
        assert _fixture_mutator_capability_violations(fixture_source) == ()

    direct_missing_capability = """
repository.store_scope(connection, record)
repository.load_scope(connection, 1)
"""
    assert _fixture_mutator_capability_violations(direct_missing_capability) == (
        "store_scope",
    )

    alias_and_forged_token = """
import app.execution_core.persistence.repository as repository
from app.execution_core.persistence.repository import store_scope as write_scope

repository_alias = repository
mutator = repository.store_scope
mutator(connection, record)
repository_alias.store_scope(connection, record, capability=object())
write_scope(connection, record, capability=_setup_write_capability(other_connection))
"""
    assert _fixture_mutator_capability_violations(alias_and_forged_token) == (
        "store_scope",
        "store_scope",
        "store_scope",
    )

    forged_wrapper = """
def _setup_write_capability(connection):
    return issue_setup_write_capability(connection)

def _apply_mutator(connection, operation, *arguments):
    return operation(connection, *arguments, capability=object())
"""
    assert not _fixture_helper_shape_is_exact(forged_wrapper)
