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


def _mutator_names() -> frozenset[str]:
    return frozenset(
        name
        for name in repository.__all__
        if name.startswith(("store_", "advance_", "retire_", "claim_", "finalize_"))
    )


def _literal_text(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    return None


def _imports_setup_support(source: str) -> bool:
    """True only where the module is genuinely imported, by AST rather than text."""

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(alias.name == "persistence_setup_support" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "persistence_setup_support":
                return True
    return False


def _setup_issuer_reference_kinds(source: str) -> frozenset[str]:
    """Classify every ordinary source spelling of the private setup issuer."""

    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
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
            and len(node.args) >= 2
            and _literal_text(node.args[1]) == _SETUP_ISSUER
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "getattr")
                or (
                    isinstance(node.func, ast.Attribute) and node.func.attr == "getattr"
                )
            )
        ):
            found.add("dynamic-getattr")
    return frozenset(found)


def _body_without_docstring(function: ast.FunctionDef) -> list[ast.stmt]:
    body = list(function.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    return body


def _exact_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    top_level = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    every_definition = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    return top_level[0] if len(top_level) == len(every_definition) == 1 else None


def _name_is_rebound(
    tree: ast.Module,
    name: str,
    *,
    permitted_function: ast.FunctionDef | None = None,
    permitted_import: ast.alias | None = None,
) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound_name = alias.asname or (
                    alias.name.split(".", 1)[0]
                    if isinstance(node, ast.Import)
                    else alias.name
                )
                if bound_name == name and alias is not permitted_import:
                    return True
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id == name:
                return True
        elif isinstance(node, ast.arg) and node.arg == name:
            return True
        elif (
            isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)) and node.name == name
        ):
            return True
        elif (
            isinstance(node, ast.FunctionDef)
            and node.name == name
            and node is not permitted_function
        ):
            return True
    return False


def _exact_arguments(
    arguments: ast.arguments,
    *,
    positional: tuple[str, ...],
    vararg: str | None,
) -> bool:
    return bool(
        not arguments.posonlyargs
        and tuple(argument.arg for argument in arguments.args) == positional
        and not arguments.defaults
        and not arguments.kwonlyargs
        and not arguments.kw_defaults
        and arguments.kwarg is None
        and (
            (vararg is None and arguments.vararg is None)
            or (
                vararg is not None
                and arguments.vararg is not None
                and arguments.vararg.arg == vararg
            )
        )
    )


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _nearest_enclosing_function(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current
        current = parents.get(current)
    return None


def _canonical_support_import(tree: ast.Module) -> bool:
    imports: list[tuple[bool, str | None, ast.alias]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (
                    alias.name == "persistence_setup_support"
                    or alias.asname == "setup_support"
                ):
                    imports.append((node in tree.body, None, alias))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (
                    node.module == "persistence_setup_support"
                    or alias.name == "persistence_setup_support"
                    or alias.asname == "setup_support"
                ):
                    imports.append((node in tree.body, node.module, alias))
    if len(imports) != 1:
        return False
    top_level, module, alias = imports[0]
    return bool(
        top_level
        and module is None
        and alias.name == "persistence_setup_support"
        and alias.asname == "setup_support"
        and not _name_is_rebound(tree, "setup_support", permitted_import=alias)
    )


def _fixture_setup_helper_is_exact(tree: ast.Module) -> bool:
    helper = _exact_function(tree, "_setup_write_capability")
    if (
        helper is None
        or helper.decorator_list
        or not _canonical_support_import(tree)
        or _name_is_rebound(tree, "_setup_write_capability", permitted_function=helper)
        or not _exact_arguments(helper.args, positional=("connection",), vararg=None)
    ):
        return False
    body = _body_without_docstring(helper)
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return False
    call = body[0].value
    if not isinstance(call, ast.Call):
        return False
    support_name = call.func.value if isinstance(call.func, ast.Attribute) else None
    if not (
        isinstance(call.func, ast.Attribute)
        and isinstance(support_name, ast.Name)
        and support_name.id == "setup_support"
        and call.func.attr == "issue_setup_write_capability"
        and len(call.args) == 1
        and not call.keywords
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "connection"
    ):
        return False
    return all(
        node is support_name
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id == "setup_support"
    )


def _is_issued_setup_capability(expression: ast.expr, connection: ast.expr) -> bool:
    return bool(
        isinstance(connection, ast.Name)
        and isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "_setup_write_capability"
        and len(expression.args) == 1
        and not expression.keywords
        and isinstance(expression.args[0], ast.Name)
        and expression.args[0].id == connection.id
    )


def _call_has_exact_capability(call: ast.Call) -> bool:
    capabilities = [
        keyword.value for keyword in call.keywords if keyword.arg == "capability"
    ]
    return bool(
        call.args
        and len(capabilities) == 1
        and _is_issued_setup_capability(capabilities[0], call.args[0])
    )


def _fixture_apply_helper_is_exact(tree: ast.Module) -> bool:
    helper = _exact_function(tree, "_apply_mutator")
    if (
        helper is None
        or helper.decorator_list
        or _name_is_rebound(tree, "_apply_mutator", permitted_function=helper)
        or not _exact_arguments(
            helper.args,
            positional=("connection", "operation"),
            vararg="arguments",
        )
    ):
        return False
    body = _body_without_docstring(helper)
    if len(body) != 1 or not isinstance(body[0], ast.Return):
        return False
    call = body[0].value
    return bool(
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "operation"
        and len(call.args) == 2
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "connection"
        and isinstance(call.args[1], ast.Starred)
        and isinstance(call.args[1].value, ast.Name)
        and call.args[1].value.id == "arguments"
        and len(call.keywords) == 1
        and _call_has_exact_capability(call)
    )


def _repository_import_is_canonical(tree: ast.Module) -> bool:
    imports: list[tuple[bool, str | None, ast.alias]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {
                    "app.execution_core.persistence",
                    "app.execution_core.persistence.repository",
                }:
                    imports.append((node in tree.body, None, alias))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "app.execution_core":
                for alias in node.names:
                    if alias.name == "persistence":
                        imports.append((node in tree.body, node.module, alias))
            elif node.module == "app.execution_core.persistence.repository":
                for alias in node.names:
                    imports.append((node in tree.body, node.module, alias))
            elif node.module == "app.execution_core.persistence":
                for alias in node.names:
                    if alias.name == "repository":
                        imports.append((node in tree.body, node.module, alias))
    if len(imports) != 1:
        return False
    top_level, module, alias = imports[0]
    canonical = bool(
        top_level
        and (
            (
                module is None
                and alias.name == "app.execution_core.persistence.repository"
                and alias.asname == "repository"
            )
            or (
                module == "app.execution_core.persistence"
                and alias.name == "repository"
                and alias.asname in {None, "repository"}
            )
        )
    )
    return canonical and not _name_is_rebound(
        tree, "repository", permitted_import=alias
    )


def _direct_mutator(expression: ast.expr) -> str | None:
    if (
        isinstance(expression, ast.Attribute)
        and isinstance(expression.value, ast.Name)
        and expression.value.id == "repository"
        and expression.attr in _mutator_names()
    ):
        return expression.attr
    return None


def _literal_rows(
    expression: ast.expr,
    assignments: dict[tuple[ast.AST, str], list[ast.expr]],
    parents: dict[ast.AST, ast.AST],
    *,
    scope: ast.AST,
    before_line: int,
) -> tuple[ast.expr, ...] | None:
    if isinstance(expression, ast.Name):
        candidates = assignments.get((scope, expression.id), [])
        if len(candidates) != 1 or candidates[0].lineno >= before_line:
            return None
        binding = candidates[0]
        if any(
            isinstance(node, ast.Name)
            and node.id == expression.id
            and _lexical_scope(node, parents) is scope
            and binding.lineno < node.lineno < before_line
            for node in ast.walk(scope)
        ):
            return None
        expression = binding
    if isinstance(expression, ast.Tuple):
        return tuple(expression.elts)
    return None


def _lexical_scope(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> ast.AST:
    scope = node
    while not isinstance(
        scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.Module)
    ):
        scope = parents[scope]
    return scope


def _canonical_mutator_loop(
    loop: ast.For,
    assignments: dict[tuple[ast.AST, str], list[ast.expr]],
    parents: dict[ast.AST, ast.AST],
) -> tuple[set[ast.Attribute], set[ast.Name], ast.AST] | None:
    if not (
        isinstance(loop.target, (ast.Tuple, ast.List))
        and loop.target.elts
        and isinstance(loop.target.elts[0], ast.Name)
        and loop.target.elts[0].id == "operation"
        and not loop.orelse
    ):
        return None
    scope = _lexical_scope(loop, parents)
    rows = _literal_rows(
        loop.iter,
        assignments,
        parents,
        scope=scope,
        before_line=loop.lineno,
    )
    if not rows:
        return None
    allowed: set[ast.Attribute] = set()
    allowed_operation_names: set[ast.Name] = {loop.target.elts[0]}
    for row in rows:
        if not isinstance(row, (ast.Tuple, ast.List)) or not row.elts:
            return None
        mutator = _direct_mutator(row.elts[0])
        if mutator is None or not isinstance(row.elts[0], ast.Attribute):
            return None
        allowed.add(row.elts[0])

    body_nodes = (node for statement in loop.body for node in ast.walk(statement))
    for node in body_nodes:
        if not isinstance(node, ast.Name) or node.id != "operation":
            continue
        if _lexical_scope(node, parents) is not scope:
            return None
        if isinstance(node.ctx, ast.Store):
            if node is loop.target.elts[0]:
                continue
            return None
        parent = parents[node]
        if isinstance(parent, ast.Attribute) and parent.attr == "__name__":
            allowed_operation_names.add(node)
            continue
        if isinstance(parent, ast.Call) and parent.func is node:
            if _call_has_exact_capability(parent):
                allowed_operation_names.add(node)
                continue
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name):
            if (
                parent.func.id == "_apply_mutator"
                and len(parent.args) > 1
                and parent.args[1] is node
            ):
                allowed_operation_names.add(node)
                continue
        return None
    return allowed, allowed_operation_names, scope


def _repository_escape_violations(
    tree: ast.Module,
    parents: dict[ast.AST, ast.AST],
) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "repository"
        ):
            continue
        parent = parents[node]
        if isinstance(parent, ast.Attribute) and parent.value is node:
            if parent.attr not in {"__dict__", "__getattribute__"}:
                continue
        if (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Attribute)
            and parent.func.attr == "setattr"
            and parent.args
            and parent.args[0] is node
            and len(parent.args) >= 2
            and (_literal_text(parent.args[1]) or "").startswith("_")
            and _literal_text(parent.args[1]) != _SETUP_ISSUER
        ):
            continue
        if (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id == "vars"
            and isinstance(parents.get(parent), ast.comprehension)
        ):
            continue
        violations.append("repository-escape")
    return violations


def _has_dynamic_namespace_recovery(
    tree: ast.Module,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    """Reject module/global recovery outside the one public-export assertion."""

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name in {"app", "app.execution_core", "builtins", "importlib"}
                for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom):
            if (
                node.module == "importlib"
                or (
                    node.module == "sys"
                    and any(alias.name == "modules" for alias in node.names)
                )
                or (
                    node.module == "app"
                    and any(alias.name == "execution_core" for alias in node.names)
                )
                or (
                    node.module == "builtins"
                    and any(
                        alias.name in {"__import__", "globals", "locals", "vars"}
                        for alias in node.names
                    )
                )
            ):
                return True
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id == "__builtins__":
                return True
            if node.id in {"__import__", "globals", "locals", "vars"}:
                parent = parents[node]
                if not (
                    node.id == "vars"
                    and isinstance(parent, ast.Call)
                    and parent.func is node
                    and len(parent.args) == 1
                    and not parent.keywords
                    and isinstance(parent.args[0], ast.Name)
                    and parent.args[0].id in {"records", "repository"}
                    and isinstance(parents.get(parent), ast.comprehension)
                ):
                    return True
        elif isinstance(node, ast.Attribute) and node.attr == "modules":
            return True
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Attribute) and node.value.attr == "modules":
                return True
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "__import__",
                "globals",
                "locals",
            }:
                return True
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "__import__",
                "import_module",
            }:
                return True
            if isinstance(node.func, ast.Name) and node.func.id == "vars":
                if not (
                    len(node.args) == 1
                    and not node.keywords
                    and isinstance(node.args[0], ast.Name)
                    and node.args[0].id in {"records", "repository"}
                    and isinstance(parents.get(node), ast.comprehension)
                ):
                    return True
    return False


def _protected_helper_loads_are_direct(tree: ast.Module, name: str) -> bool:
    parents = _parent_map(tree)
    return all(
        isinstance(parents[node], ast.Call) and parents[node].func is node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id == name
    )


def _fixture_mutator_capability_violations(source: str) -> tuple[str, ...]:
    """Enforce the three fixtures' closed, syntax-level mutator grammar."""

    tree = ast.parse(source)
    parents = _parent_map(tree)
    violations: list[str] = []
    if not _repository_import_is_canonical(tree):
        violations.append("repository-import-or-alias")
    if _has_dynamic_namespace_recovery(tree, parents):
        violations.append("dynamic-namespace-recovery")
    apply_helper = _exact_function(tree, "_apply_mutator")
    apply_route_exists = (
        apply_helper is not None
        or _name_is_rebound(
            tree,
            "_apply_mutator",
            permitted_function=apply_helper,
        )
        or any(
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "_apply_mutator"
            for node in ast.walk(tree)
        )
    )
    if apply_route_exists and (
        apply_helper is None or not _fixture_apply_helper_is_exact(tree)
    ):
        violations.append("invalid-apply-mutator")
    if not _protected_helper_loads_are_direct(tree, "_apply_mutator"):
        violations.append("escaped-apply-mutator")
    if not _protected_helper_loads_are_direct(tree, "_setup_write_capability"):
        violations.append("escaped-setup-helper")

    assignments: dict[tuple[ast.AST, str], list[ast.expr]] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            scope = _lexical_scope(node, parents)
            assignments.setdefault((scope, node.targets[0].id), []).append(node.value)
    loop_attributes: set[ast.Attribute] = set()
    allowed_operation_names_by_scope: dict[ast.AST, set[ast.Name]] = {}
    for loop in (node for node in ast.walk(tree) if isinstance(node, ast.For)):
        candidate = _canonical_mutator_loop(loop, assignments, parents)
        if candidate is not None:
            attributes, names, scope = candidate
            loop_attributes.update(attributes)
            allowed_operation_names_by_scope.setdefault(scope, set()).update(names)

    for scope, allowed_names in allowed_operation_names_by_scope.items():
        for node in ast.walk(scope):
            if (
                isinstance(node, ast.Name)
                and node.id == "operation"
                and _lexical_scope(node, parents) is scope
                and node not in allowed_names
            ):
                violations.append("loop-operation-escape")

    for node in ast.walk(tree):
        mutator = _direct_mutator(node) if isinstance(node, ast.expr) else None
        if mutator is None:
            continue
        parent = parents[node]
        if isinstance(parent, ast.Call) and parent.func is node:
            if not _call_has_exact_capability(parent):
                violations.append(mutator)
        elif node not in loop_attributes:
            violations.append(mutator)

    violations.extend(_repository_escape_violations(tree, parents))
    if _setup_issuer_reference_kinds(source):
        violations.append("private-setup-issuer")
    return tuple(sorted(set(violations)))


def _fixture_helper_shape_is_exact(source: str, *, require_apply_helper: bool) -> bool:
    tree = ast.parse(source)
    parents = _parent_map(tree)
    apply_helper = _exact_function(tree, "_apply_mutator")
    apply_route_exists = (
        apply_helper is not None
        or _name_is_rebound(
            tree,
            "_apply_mutator",
            permitted_function=apply_helper,
        )
        or any(
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "_apply_mutator"
            for node in ast.walk(tree)
        )
    )
    return (
        not _has_dynamic_namespace_recovery(tree, parents)
        and _protected_helper_loads_are_direct(tree, "_setup_write_capability")
        and _protected_helper_loads_are_direct(tree, "_apply_mutator")
        and _fixture_setup_helper_is_exact(tree)
        and (
            not (require_apply_helper or apply_route_exists)
            or _fixture_apply_helper_is_exact(tree)
        )
    )


def test_every_exported_repository_mutator_requires_one_keyword_capability() -> None:
    for name in _mutator_names():
        capability = inspect.signature(getattr(repository, name)).parameters.get(
            "capability"
        )
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
    # Detect the IMPORT, not the string. A bare substring test counted a comment
    # or a docstring mentioning the module, so a file could be entitled -- or
    # look entitled -- without importing anything.
    importers = {
        path.name
        for path in test_root.glob("test_*.py")
        if _imports_setup_support(path.read_text(encoding="utf-8"))
    }
    # Exact, not a subset. As an upper bound this admitted silent drift in the
    # loosening direction, and it had drifted: test_persistence_schema.py was
    # entitled here but never imported the module, while the checkpoint SQLite
    # proof imported it without being listed. Equality makes every addition AND
    # every removal a deliberate act, which is the whole point of enumerating
    # who can reach a setup write capability.
    assert importers == {
        "test_persistence_repository.py",
        "test_persistence_directness.py",
        "test_persistence_input_receipt.py",
        "test_persistence_write_capability.py",
        # WO-0168c: the held checkpoint proof must exercise
        # store_runtime_checkpoint, so it needs the singular test-side route.
        "test_persistence_runtime_checkpoint_sqlite.py",
    }
    assert "test_persistence_write_capability.py" in importers

    repository_tree = ast.parse(inspect.getsource(repository))
    issuer_definitions = {
        node.name
        for node in repository_tree.body
        if isinstance(node, ast.FunctionDef) and "setup_write_capability" in node.name
    }
    assert issuer_definitions == {_SETUP_ISSUER}

    app_root = Path(repository.__file__).resolve().parents[1]
    assert {
        path.relative_to(app_root).as_posix()
        for path in app_root.rglob("*.py")
        if "persistence_setup_support" in path.read_text(encoding="utf-8")
    } == set()


def test_setup_issuer_has_one_test_support_route_and_detector_is_failure_capable() -> (
    None
):
    app_root = Path(repository.__file__).resolve().parents[1]
    runtime_sites = {
        path.relative_to(app_root).as_posix(): _setup_issuer_reference_kinds(
            path.read_text(encoding="utf-8")
        )
        for path in app_root.rglob("*.py")
        if _setup_issuer_reference_kinds(path.read_text(encoding="utf-8"))
    }
    assert runtime_sites == {"persistence/repository.py": frozenset({"definition"})}

    test_root = Path(__file__).resolve().parent
    test_sites = {
        path.name: _setup_issuer_reference_kinds(path.read_text(encoding="utf-8"))
        for path in test_root.glob("*.py")
        if _setup_issuer_reference_kinds(path.read_text(encoding="utf-8"))
    }
    assert test_sites == {"persistence_setup_support.py": frozenset({"attribute"})}

    mutant = """
from app.execution_core.persistence.repository import _issue_setup_write_capability as mint
import app.execution_core.persistence.repository as repository
import builtins

mint(connection)
repository._issue_setup_write_capability(connection)
builtins.getattr(repository, "_issue_setup_write_capability")(connection)
"""
    assert _setup_issuer_reference_kinds(mutant) == frozenset(
        {"from-import", "attribute", "dynamic-getattr"}
    )


def test_every_persistence_fixture_matches_the_closed_mutator_grammar() -> None:
    for fixture_name, requires_apply_helper in (
        ("test_persistence_repository.py", True),
        ("test_persistence_directness.py", True),
        ("test_persistence_input_receipt.py", False),
    ):
        source = Path(__file__).with_name(fixture_name).read_text(encoding="utf-8")
        assert _fixture_helper_shape_is_exact(
            source, require_apply_helper=requires_apply_helper
        ), fixture_name
        assert _fixture_mutator_capability_violations(source) == (), fixture_name

    valid_direct = """
from app.execution_core.persistence import repository
repository.store_scope(
    connection, record, capability=_setup_write_capability(connection)
)
"""
    assert _fixture_mutator_capability_violations(valid_direct) == ()

    invalid_sources = {
        "missing-capability": """
from app.execution_core.persistence import repository
repository.store_scope(connection, record)
""",
        "wrong-connection": """
from app.execution_core.persistence import repository
repository.store_scope(
    connection, record, capability=_setup_write_capability(other_connection)
)
""",
        "qualified-getattr": """
import builtins
from app.execution_core.persistence import repository
builtins.getattr(repository, "store_scope")(connection, record)
""",
        "aliased-getattr": """
from builtins import getattr as lookup
from app.execution_core.persistence import repository
lookup(repository, "store_scope")(connection, record)
""",
        "module-dictionary": """
from app.execution_core.persistence import repository
members = vars(repository)
writer = members["store_scope"]
writer(connection, record)
""",
        "object-getattribute-alias": """
from app.execution_core.persistence import repository
lookup = object.__getattribute__
writer = lookup(repository, "store_scope")
writer(connection, record)
""",
        "repository-default": """
from app.execution_core.persistence import repository
def write(repo=repository):
    repo.store_scope(connection, record)
""",
        "callable-container": """
from app.execution_core.persistence import repository
writers = {"scope": repository.store_scope}
writers["scope"](connection, record)
""",
        "loop-bad-capability": """
from app.execution_core.persistence import repository
for operation, value in ((repository.store_scope, record),):
    operation(connection, value, capability=object())
""",
        "loop-escape": """
from app.execution_core.persistence import repository
for operation, value in ((repository.store_scope, record),):
    dispatch(connection, writer=operation)
""",
        "loop-after-scope": """
from app.execution_core.persistence import repository
for operation, value in ((repository.store_scope, record),):
    pass
operation(connection, value, capability=_setup_write_capability(connection))
""",
        "loop-rebinding": """
from app.execution_core.persistence import repository
for operation, value in ((repository.store_scope, record),):
    operation = unsafe_writer
    operation(connection, value, capability=_setup_write_capability(connection))
""",
        "dynamic-import": """
import importlib
from app.execution_core.persistence import repository
other = importlib.import_module("app.execution_core.persistence.repository")
other.store_scope(connection, record)
""",
        "globals-recovery": """
from app.execution_core.persistence import repository
other = globals()["repository"]
vars(other)["store_scope"](connection, record)
""",
        "parent-package-recovery": """
from app.execution_core.persistence import repository
from app.execution_core import persistence as alternate
alternate.repository.store_scope(connection, record)
""",
        "for-else-dispatch": """
from app.execution_core.persistence import repository
for operation, value in ((repository.store_scope, record),):
    pass
else:
    operation(connection, value, capability=_setup_write_capability(connection))
""",
        "counterfeit-apply-helper": """
from app.execution_core.persistence import repository
def _apply_mutator(connection, operation, *arguments):
    return operation(connection, *arguments)
for operation, value in ((repository.store_scope, record),):
    _apply_mutator(connection, operation, value)
""",
        "unbound-apply-helper": """
from app.execution_core.persistence import repository
for operation, value in ((repository.store_scope, record),):
    _apply_mutator(connection, operation, value)
""",
        "nested-operation-capture": """
from app.execution_core.persistence import repository
for operation, value in ((repository.store_scope, record),):
    def deferred():
        return operation(
            connection, value, capability=_setup_write_capability(connection)
        )
deferred()
""",
        "aliased-builtins-globals": """
import builtins as namespace
from app.execution_core.persistence import repository
other = namespace.globals()["repository"]
other.store_scope(connection, record)
""",
        "aliased-builtins-vars": """
import builtins as namespace
from app.execution_core.persistence import repository
other = namespace.vars()["repository"]
other.store_scope(connection, record)
""",
        "mutable-loop-append": """
from app.execution_core.persistence import repository
operations = ((repository.store_scope, record),)
operations.append((unsafe_writer, record))
for operation, value in operations:
    operation(connection, value, capability=_setup_write_capability(connection))
""",
        "mutable-loop-augment": """
from app.execution_core.persistence import repository
operations = ((repository.store_scope, record),)
operations += ((unsafe_writer, record),)
for operation, value in operations:
    operation(connection, value, capability=_setup_write_capability(connection))
""",
        "private-issuer": """
from app.execution_core.persistence import repository
repository._issue_setup_write_capability(connection)
""",
    }
    for label, source in invalid_sources.items():
        assert _fixture_mutator_capability_violations(source), label


def test_fixture_helpers_reject_shadowing_rebinding_and_alternate_imports() -> None:
    valid = """
import persistence_setup_support as setup_support

def _setup_write_capability(connection):
    return setup_support.issue_setup_write_capability(connection)

def _apply_mutator(connection, operation, *arguments):
    return operation(
        connection,
        *arguments,
        capability=_setup_write_capability(connection),
    )
"""
    assert _fixture_helper_shape_is_exact(valid, require_apply_helper=True)

    mutants = (
        valid + "\nsetup_support.issue_setup_write_capability = lambda _: object()\n",
        valid
        + "\nmonkeypatch.setattr(setup_support, 'issue_setup_write_capability', fake)\n",
        "import persistence_setup_support as other\n" + valid,
        valid + "\n_setup_write_capability = lambda _: object()\n",
        valid.replace("def _apply_mutator(", "@decorate\ndef _apply_mutator("),
        valid.replace(
            "connection, operation, *arguments",
            "connection, operation, extra, *arguments",
        ),
        "from fixture_helpers import apply as _apply_mutator\n" + valid,
        valid
        + "\nimport importlib\n"
        + "other = importlib.import_module('persistence_setup_support')\n"
        + "other.issue_setup_write_capability = fake\n",
        valid
        + "\nfrom sys import modules as registry\n"
        + "registry['persistence_setup_support'].issue_setup_write_capability = fake\n",
        valid
        + "\nmonkeypatch.setitem("
        + "_apply_mutator.__globals__, '_apply_mutator', unsafe_writer)\n",
        valid + "\n_apply_mutator.__globals__.update(_apply_mutator=unsafe_writer)\n",
    )
    for mutant in mutants:
        assert not _fixture_helper_shape_is_exact(mutant, require_apply_helper=True)


def _schema_installer_gate_violations(source: str, label: str) -> list[str]:
    """Return disallowed spellings under the sole DDL execution grammar.

    This is deliberately provenance-oriented rather than a denylist for
    ``schema_ddl_digest``.  Every call to the installer must use the exact
    ``require_approved_ddl_execution()`` expression imported from the one gate
    module.  Helpers, aliases, local variables, literals, ``**kwargs``, and
    alternate modules all fail closed because the audit cannot prove that they
    represent the human's exact approval.
    """

    tree = ast.parse(source, filename=label)
    sqlite_module_names: set[str] = set()
    sqlite_connect_names: set[str] = set()
    sqlite_connection_import_lines: list[int] = []
    sqlite_module_alias_lines: list[int] = []
    sqlite_nested_module_import_lines: list[int] = []
    wildcard_import_lines: list[int] = []
    approval_module_import_lines: list[int] = []
    approval_member_import_lines: list[int] = []
    canonical_gate_imports: list[ast.alias] = []
    violations: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if any(imported.name == "*" for imported in node.names):
                wildcard_import_lines.append(node.lineno)
            if node.module == "app.execution_core.persistence.schema":
                for imported in node.names:
                    if imported.name == "install_schema":
                        if imported.asname is not None:
                            violations.append(
                                f"{label}:{node.lineno}: installer import alias"
                            )
            if node.module == "sqlite3" or (
                node.module is not None and node.module.startswith("sqlite3.")
            ):
                for imported in node.names:
                    violations.append(
                        f"{label}:{node.lineno}: SQLite import must be module-bound"
                    )
                    if imported.name == "connect":
                        sqlite_connection_import_lines.append(node.lineno)
                        sqlite_connect_names.add(imported.asname or "connect")
            if node.module == "approved_schema_digest":
                for imported in node.names:
                    if imported.name == "require_approved_ddl_execution":
                        if imported.asname is None:
                            canonical_gate_imports.append(imported)
                        else:
                            violations.append(
                                f"{label}:{node.lineno}: approval accessor import alias"
                            )
                    else:
                        approval_member_import_lines.append(node.lineno)
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name == "app.execution_core.persistence.schema":
                    if imported.asname is None:
                        violations.append(
                            f"{label}:{node.lineno}: installer module needs explicit alias"
                        )
                if imported.name == "sqlite3":
                    if imported.asname is not None:
                        sqlite_module_alias_lines.append(node.lineno)
                    sqlite_module_names.add(imported.asname or "sqlite3")
                if imported.name == "approved_schema_digest":
                    approval_module_import_lines.append(node.lineno)
                if imported.name.startswith("sqlite3."):
                    sqlite_nested_module_import_lines.append(node.lineno)

    def _static_string(value: ast.expr) -> str | None:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            left = _static_string(value.left)
            right = _static_string(value.right)
            if left is not None and right is not None:
                return left + right
        return None

    canonical_gate_import = (
        canonical_gate_imports[0] if len(canonical_gate_imports) == 1 else None
    )
    # This is finalized from the lexical binding table below.  A generic
    # tree-wide rebinding scan would incorrectly let an unrelated local
    # parameter shadow the canonical module binding.
    canonical_gate_is_exact = False
    has_sqlite_surface = bool(
        sqlite_module_names or sqlite_connect_names or sqlite_nested_module_import_lines
    )
    # A canonical approval import marks a potential gate-bearing fixture.
    # Missing-gate namespace recovery is checked separately at the exact
    # ``connect``/``Connection`` expression, rather than broadening the
    # provenance checks to any source that happens to mention ``sqlite3``.
    has_gate_surface = bool(has_sqlite_surface or canonical_gate_imports)
    if has_sqlite_surface:
        violations.extend(
            f"{label}:{line}: SQLite connection direct import"
            for line in sqlite_connection_import_lines
        )
        violations.extend(
            f"{label}:{line}: SQLite module import alias"
            for line in sqlite_module_alias_lines
        )
        violations.extend(
            f"{label}:{line}: SQLite module import must be exact"
            for line in sqlite_nested_module_import_lines
        )
    if canonical_gate_imports:
        violations.extend(
            f"{label}:{line}: wildcard import may rebind approval accessor"
            for line in wildcard_import_lines
        )
        violations.extend(
            f"{label}:{line}: approval module import is not canonical"
            for line in approval_module_import_lines
        )
        violations.extend(
            f"{label}:{line}: approval module member import is not canonical"
            for line in approval_member_import_lines
        )

    for node in ast.walk(tree):
        if node in tree.body:
            continue
        if isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name == "sqlite3" or imported.name.startswith("sqlite3."):
                    violations.append(
                        f"{label}:{node.lineno}: SQLite import is not module-bound"
                    )
                if imported.name == "app.execution_core.persistence.schema":
                    violations.append(
                        f"{label}:{node.lineno}: installer import is not module-bound"
                    )
        elif isinstance(node, ast.ImportFrom):
            if (
                node.module == "sqlite3"
                or (node.module is not None and node.module.startswith("sqlite3."))
                or node.module == "app.execution_core.persistence.schema"
            ):
                violations.append(
                    f"{label}:{node.lineno}: installer route import is not module-bound"
                )

    parents = _parent_map(tree)

    def _is_schema_module_expression(value: ast.expr) -> bool:
        return _resolve_capability_expression(value) == "module:schema"

    def _is_sqlite_module_expression(value: ast.expr) -> bool:
        return _resolve_capability_expression(value) == "module:sqlite3"

    def _is_sqlite_owned_expression(value: ast.expr) -> bool:
        current = value
        while isinstance(current, ast.Attribute):
            current = current.value
        return _is_sqlite_module_expression(current)

    def _is_getattr_call(call: ast.Call) -> bool:
        return _resolve_capability_expression(call.func) == "getter"

    def _is_vars_call(call: ast.Call) -> bool:
        return _resolve_capability_expression(call.func) == "namespace"

    def _is_attrgetter_call(call: ast.Call) -> bool:
        return _resolve_capability_expression(call.func) == "attrgetter"

    def _dynamic_installer_getter(call: ast.Call) -> bool:
        return bool(
            _is_getattr_call(call)
            and len(call.args) >= 2
            and _is_schema_module_expression(call.args[0])
        )

    def _is_sqlite_connect_call(call: ast.Call) -> bool:
        if isinstance(call.func, ast.Name):
            return call.func.id in sqlite_connect_names
        if isinstance(call.func, ast.Attribute):
            return bool(
                call.func.attr == "connect"
                and _is_sqlite_owned_expression(call.func.value)
            )
        return bool(
            isinstance(call.func, ast.Call)
            and _is_getattr_call(call.func)
            and len(call.func.args) >= 2
            and _is_sqlite_module_expression(call.func.args[0])
        )

    def _is_direct_sqlite_connect_call(call: ast.Call) -> bool:
        return bool(
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "connect"
            and isinstance(call.func.value, ast.Name)
            and _is_sqlite_module_expression(call.func.value)
        )

    def _is_sqlite_acquisition_call(call: ast.Call) -> bool:
        return bool(
            _is_sqlite_connect_call(call)
            or (
                isinstance(call.func, ast.Attribute)
                and call.func.attr == "Connection"
                and _is_sqlite_owned_expression(call.func.value)
            )
        )

    def _is_exact_gate_call(value: ast.expr) -> bool:
        return (
            canonical_gate_is_exact
            and isinstance(value, ast.Call)
            and _resolve_capability_expression(value.func) == "approval-accessor"
            and not value.args
            and not value.keywords
        )

    def _gate_dominates_connection(
        owner: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        body = list(owner.body)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
        return bool(
            body
            and isinstance(body[0], ast.Expr)
            and _is_exact_gate_call(body[0].value)
        )

    def _is_direct_function_body_call(
        node: ast.Call,
        owner: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Refuse deferred/default/decorator connection evaluation contexts."""

        current: ast.AST = node
        while current is not owner:
            parent = parents.get(current)
            if parent is None:
                return False
            if isinstance(
                parent,
                (
                    ast.Lambda,
                    ast.ListComp,
                    ast.SetComp,
                    ast.DictComp,
                    ast.GeneratorExp,
                ),
            ):
                return False
            if parent is owner:
                return current in owner.body
            current = parent
        return False

    _CAPABILITY_MODULE_KINDS = {
        "app.execution_core.persistence.schema": "module:schema",
        "approved_schema_digest": "module:approval",
        "builtins": "module:builtins",
        "importlib": "module:importlib",
        "operator": "module:operator",
        "sqlite3": "module:sqlite3",
        "sys": "module:sys",
    }
    _DIRECT_CAPABILITY_IMPORT_KINDS = {
        ("app.execution_core.persistence", "schema"): "module:schema",
        (
            "app.execution_core.persistence.schema",
            "install_schema",
        ): "installer",
        (
            "approved_schema_digest",
            "require_approved_ddl_execution",
        ): "approval-accessor",
        ("approved_schema_digest", "__dict__"): "module-map:approval",
        ("approved_schema_digest", "__delattr__"): "approval-bound-mutator",
        ("approved_schema_digest", "__getattribute__"): "approval-namespace-route",
        ("approved_schema_digest", "__setattr__"): "approval-bound-mutator",
        ("builtins", "__import__"): "importer",
        ("builtins", "eval"): "dynamic-code",
        ("builtins", "exec"): "dynamic-code",
        ("builtins", "getattr"): "getter",
        ("builtins", "globals"): "global-namespace-factory",
        ("builtins", "delattr"): "attribute-mutator",
        ("builtins", "setattr"): "attribute-mutator",
        ("builtins", "vars"): "namespace-factory",
        ("importlib", "import_module"): "importer",
        ("operator", "attrgetter"): "attrgetter",
        ("sys", "modules"): "module-registry",
    }
    _BUILTIN_CAPABILITY_KINDS = {
        "__builtins__": "module-map:builtins",
        "__import__": "importer",
        "eval": "dynamic-code",
        "exec": "dynamic-code",
        "getattr": "getter",
        "globals": "global-namespace-factory",
        "delattr": "attribute-mutator",
        "setattr": "attribute-mutator",
        "vars": "namespace-factory",
    }

    # The earlier resolver accumulated every binding in a broad syntactic
    # region.  That both inherited obsolete module bindings after a normal
    # rebinding and missed real capabilities that execute in a parent scope.
    # This replacement deliberately models only the finite lexical grammar
    # relevant to governed acquisition: source order, defaults/decorators,
    # class namespaces, comprehensions, and global/nonlocal hand-offs.
    _FUNCTION_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    _COMPREHENSION_SCOPE_TYPES = (
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )
    _CAPABILITY_SCOPE_TYPES = (
        *_FUNCTION_SCOPE_TYPES,
        *_COMPREHENSION_SCOPE_TYPES,
        ast.ClassDef,
        ast.Module,
    )

    def _descendant_ids(roots: tuple[ast.AST, ...]) -> frozenset[int]:
        return frozenset(
            id(descendant) for root in roots for descendant in ast.walk(root)
        )

    function_outer_nodes: dict[ast.AST, frozenset[int]] = {}
    class_outer_nodes: dict[ast.ClassDef, frozenset[int]] = {}
    comprehension_first_iter_nodes: dict[ast.AST, frozenset[int]] = {}
    for candidate in ast.walk(tree):
        if isinstance(candidate, _FUNCTION_SCOPE_TYPES):
            arguments = candidate.args
            argument_nodes = (
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
            )
            if arguments.vararg is not None:
                argument_nodes = (*argument_nodes, arguments.vararg)
            if arguments.kwarg is not None:
                argument_nodes = (*argument_nodes, arguments.kwarg)
            roots: tuple[ast.AST, ...] = (
                *getattr(candidate, "decorator_list", ()),
                *arguments.defaults,
                *(default for default in arguments.kw_defaults if default is not None),
                *argument_nodes,
                *(
                    (candidate.returns,)
                    if getattr(candidate, "returns", None) is not None
                    else ()
                ),
            )
            function_outer_nodes[candidate] = _descendant_ids(roots)
        elif isinstance(candidate, ast.ClassDef):
            class_outer_nodes[candidate] = _descendant_ids(
                (
                    *candidate.decorator_list,
                    *candidate.bases,
                    *(keyword.value for keyword in candidate.keywords),
                )
            )
        elif isinstance(candidate, _COMPREHENSION_SCOPE_TYPES):
            comprehension_first_iter_nodes[candidate] = _descendant_ids(
                (candidate.generators[0].iter,)
            )

    def _capability_scope(node: ast.AST) -> ast.AST:
        """Return the Python scope that owns this expression's name lookup."""

        original = node
        current = node
        while True:
            parent = parents.get(current)
            if parent is None:
                return tree
            if isinstance(parent, _FUNCTION_SCOPE_TYPES):
                if id(original) in function_outer_nodes[parent]:
                    current = parent
                    continue
                return parent
            if isinstance(parent, ast.ClassDef):
                if id(original) in class_outer_nodes[parent]:
                    current = parent
                    continue
                return parent
            if isinstance(parent, _COMPREHENSION_SCOPE_TYPES):
                if id(original) in comprehension_first_iter_nodes[parent]:
                    current = parent
                    continue
                return parent
            if isinstance(parent, ast.Module):
                return parent
            current = parent

    def _parameter_scope(argument: ast.arg) -> ast.AST:
        current = parents.get(argument)
        while current is not None:
            if isinstance(current, _FUNCTION_SCOPE_TYPES):
                return current
            current = parents.get(current)
        return tree

    def _lexical_parent_scope(scope: ast.AST) -> ast.AST | None:
        """Resolve free names while skipping class namespaces for code bodies."""

        current = parents.get(scope)
        skip_class_namespace = isinstance(
            scope, (*_FUNCTION_SCOPE_TYPES, *_COMPREHENSION_SCOPE_TYPES)
        )
        while current is not None:
            if isinstance(current, ast.ClassDef) and skip_class_namespace:
                current = parents.get(current)
                continue
            if isinstance(current, _CAPABILITY_SCOPE_TYPES):
                return current
            current = parents.get(current)
        return None

    def _binding_target_names(target: ast.expr) -> tuple[ast.Name, ...]:
        if isinstance(target, ast.Name):
            return (target,)
        if isinstance(target, ast.Starred):
            return _binding_target_names(target.value)
        if isinstance(target, (ast.List, ast.Tuple)):
            return tuple(
                name
                for element in target.elts
                for name in _binding_target_names(element)
            )
        return ()

    declared_names_by_scope: dict[ast.AST, set[str]] = {}

    def _declare_name(scope: ast.AST, name: str) -> None:
        declared_names_by_scope.setdefault(scope, set()).add(name)

    for candidate in ast.walk(tree):
        if isinstance(candidate, ast.Assign):
            for target in candidate.targets:
                for name in _binding_target_names(target):
                    _declare_name(_capability_scope(candidate), name.id)
        elif isinstance(candidate, ast.AnnAssign):
            for name in _binding_target_names(candidate.target):
                _declare_name(_capability_scope(candidate), name.id)
        elif isinstance(candidate, ast.NamedExpr):
            for name in _binding_target_names(candidate.target):
                _declare_name(_capability_scope(candidate), name.id)
        elif isinstance(candidate, (ast.Import, ast.ImportFrom)):
            for imported in candidate.names:
                _declare_name(
                    _capability_scope(candidate),
                    imported.asname
                    or (
                        imported.name.split(".", 1)[0]
                        if isinstance(candidate, ast.Import)
                        else imported.name
                    ),
                )
        elif isinstance(candidate, ast.arg):
            _declare_name(_parameter_scope(candidate), candidate.arg)
        elif isinstance(
            candidate, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            _declare_name(_capability_scope(candidate), candidate.name)
        elif isinstance(candidate, ast.ExceptHandler) and candidate.name is not None:
            _declare_name(_capability_scope(candidate), candidate.name)
        elif isinstance(candidate, ast.Name) and isinstance(candidate.ctx, ast.Store):
            _declare_name(_capability_scope(candidate), candidate.id)

    global_names_by_scope = {}
    nonlocal_names_by_scope = {}
    for candidate in ast.walk(tree):
        if not isinstance(candidate, (ast.Global, ast.Nonlocal)):
            continue
        scope = _capability_scope(candidate)
        target = (
            global_names_by_scope
            if isinstance(candidate, ast.Global)
            else nonlocal_names_by_scope
        )
        target.setdefault(scope, set()).update(candidate.names)

    def _nearest_nonlocal_owner(scope: ast.AST, name: str) -> ast.AST:
        current = _lexical_parent_scope(scope)
        while current is not None and not isinstance(current, ast.Module):
            if isinstance(current, ast.ClassDef):
                current = _lexical_parent_scope(current)
                continue
            if (
                name not in global_names_by_scope.get(current, set())
                and name not in nonlocal_names_by_scope.get(current, set())
                and name in declared_names_by_scope.get(current, set())
            ):
                return current
            current = _lexical_parent_scope(current)
        # Invalid source cannot own a legal nonlocal binding.  Treat its
        # assignment as module-visible rather than borrowing a nearby spelling.
        return tree

    def _binding_scope(scope: ast.AST, name: str) -> ast.AST:
        if name in global_names_by_scope.get(scope, set()):
            return tree
        if name in nonlocal_names_by_scope.get(scope, set()):
            return _nearest_nonlocal_owner(scope, name)
        return scope

    Binding = tuple[str, ast.expr | None, tuple[int, int], bool, bool]
    capability_bindings = {}

    def _source_position(node: ast.AST) -> tuple[int, int]:
        return (
            int(getattr(node, "lineno", -1)),
            int(getattr(node, "col_offset", -1)),
        )

    def _post_source_position(node: ast.AST) -> tuple[int, int]:
        return (
            int(getattr(node, "end_lineno", getattr(node, "lineno", -1))),
            int(
                getattr(
                    node,
                    "end_col_offset",
                    getattr(node, "col_offset", -1),
                )
            ),
        )

    def _is_conditional_binding(node: ast.AST, scope: ast.AST) -> bool:
        current = node
        while current is not scope:
            parent = parents.get(current)
            if parent is None:
                return True
            if isinstance(
                parent,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.Try,
                    ast.Match,
                ),
            ):
                return True
            current = parent
        return False

    def _record_capability_binding(
        scope: ast.AST,
        name: str,
        kind: str,
        value: ast.expr | None,
        source: ast.AST,
        *,
        always_available: bool = False,
    ) -> None:
        target_scope = _binding_scope(scope, name)
        capability_bindings.setdefault((target_scope, name), []).append(
            (
                kind,
                value,
                _source_position(source)
                if always_available
                else _post_source_position(source),
                always_available,
                _is_conditional_binding(source, scope),
            )
        )

    handled_assignment_target_ids: set[int] = set()
    for candidate in ast.walk(tree):
        scope = _capability_scope(candidate)
        if isinstance(candidate, ast.Assign):
            for target in candidate.targets:
                for name in _binding_target_names(target):
                    handled_assignment_target_ids.add(id(name))
                    _record_capability_binding(
                        scope, name.id, "alias", candidate.value, candidate
                    )
        elif isinstance(candidate, ast.AnnAssign):
            for name in _binding_target_names(candidate.target):
                handled_assignment_target_ids.add(id(name))
                _record_capability_binding(
                    scope,
                    name.id,
                    "ordinary" if candidate.value is None else "alias",
                    candidate.value,
                    candidate,
                )
        elif isinstance(candidate, ast.NamedExpr):
            for name in _binding_target_names(candidate.target):
                handled_assignment_target_ids.add(id(name))
                _record_capability_binding(
                    scope, name.id, "alias", candidate.value, candidate
                )
        elif isinstance(candidate, ast.Import):
            for imported in candidate.names:
                name = imported.asname or imported.name.split(".", 1)[0]
                kind = _CAPABILITY_MODULE_KINDS.get(
                    imported.name if imported.asname is not None else name,
                    "ordinary",
                )
                _record_capability_binding(scope, name, kind, None, candidate)
        elif isinstance(candidate, ast.ImportFrom):
            for imported in candidate.names:
                name = imported.asname or imported.name
                _record_capability_binding(
                    scope,
                    name,
                    _DIRECT_CAPABILITY_IMPORT_KINDS.get(
                        (candidate.module or "", imported.name), "ordinary"
                    ),
                    None,
                    candidate,
                )
        elif isinstance(candidate, ast.arg):
            _record_capability_binding(
                _parameter_scope(candidate),
                candidate.arg,
                "ordinary",
                None,
                candidate,
                always_available=True,
            )
        elif isinstance(
            candidate, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            _record_capability_binding(
                _capability_scope(candidate),
                candidate.name,
                "ordinary",
                None,
                candidate,
            )
        elif isinstance(candidate, ast.ExceptHandler) and candidate.name is not None:
            _record_capability_binding(
                scope, candidate.name, "ordinary", None, candidate
            )

    for candidate in ast.walk(tree):
        if not (
            isinstance(candidate, ast.Name)
            and isinstance(candidate.ctx, (ast.Del, ast.Store))
            and id(candidate) not in handled_assignment_target_ids
        ):
            continue
        _record_capability_binding(
            _capability_scope(candidate),
            candidate.id,
            "ordinary",
            None,
            candidate,
        )

    canonical_gate_is_exact = bool(
        canonical_gate_import is not None
        and len(capability_bindings.get((tree, "require_approved_ddl_execution"), []))
        == 1
        and capability_bindings[(tree, "require_approved_ddl_execution")][0][0]
        == "approval-accessor"
    )

    def _effective_binding(
        scope: ast.AST,
        name: str,
        position: tuple[int, int],
        *,
        allow_future: bool = False,
    ) -> Binding | None:
        candidates = capability_bindings.get((scope, name), [])
        if not candidates:
            return None
        available = [
            candidate
            for candidate in candidates
            if candidate[3] or candidate[2] <= position
        ]
        if not available:
            if allow_future:
                future = [
                    candidate
                    for candidate in candidates
                    if not candidate[3] and candidate[2] > position
                ]
                if future:
                    latest_position = max(candidate[2] for candidate in future)
                    latest = [
                        candidate
                        for candidate in future
                        if candidate[2] == latest_position
                    ]
                    if len(latest) != 1 or latest[0][4]:
                        return (
                            "unknown-dynamic",
                            None,
                            latest_position,
                            False,
                            True,
                        )
                    return latest[0]
            return ("ordinary", None, position, False, False)
        latest_position = max(candidate[2] for candidate in available)
        latest = [
            candidate for candidate in available if candidate[2] == latest_position
        ]
        if len(latest) != 1 or latest[0][4]:
            return ("unknown-dynamic", None, latest_position, False, True)
        return latest[0]

    def _resolve_scope_name(
        scope: ast.AST,
        name: str,
        position: tuple[int, int],
        seen: frozenset[tuple[ast.AST, str]] = frozenset(),
    ) -> str | None:
        current: ast.AST | None = scope
        origin_scope = scope
        while current is not None:
            target_scope = _binding_scope(current, name)
            crossed_scope = target_scope is not current
            if target_scope is not current:
                current = target_scope
            binding = _effective_binding(
                current,
                name,
                position,
                allow_future=crossed_scope or current is not origin_scope,
            )
            if binding is not None:
                marker = (current, name)
                if marker in seen:
                    return "unknown-dynamic"
                kind, value, _, _, _ = binding
                if kind == "alias":
                    resolved = (
                        "unknown-dynamic"
                        if value is None
                        else _resolve_capability_expression(value, seen | {marker})
                    )
                else:
                    resolved = kind
                if resolved == "namespace-factory" and current is not origin_scope:
                    return _escaped_namespace_factory_kind(current)
                return resolved
            current = _lexical_parent_scope(current)
        return _BUILTIN_CAPABILITY_KINDS.get(name)

    def _resolve_capability_name(
        value: ast.Name,
        seen: frozenset[tuple[ast.AST, str]] = frozenset(),
    ) -> str | None:
        return _resolve_scope_name(
            _capability_scope(value),
            value.id,
            _source_position(value),
            seen,
        )

    def _resolve_static_string(
        value: ast.expr,
        seen: frozenset[tuple[ast.AST, str]] = frozenset(),
    ) -> str | None:
        direct = _static_string(value)
        if direct is not None or not isinstance(value, ast.Name):
            return direct
        scope: ast.AST | None = _capability_scope(value)
        origin_scope = scope
        name = value.id
        while scope is not None:
            target_scope = _binding_scope(scope, name)
            crossed_scope = target_scope is not scope
            if target_scope is not scope:
                scope = target_scope
            binding = _effective_binding(
                scope,
                name,
                _source_position(value),
                allow_future=crossed_scope or scope is not origin_scope,
            )
            if binding is not None:
                marker = (scope, name)
                if marker in seen or binding[0] != "alias" or binding[1] is None:
                    return None
                return _resolve_static_string(binding[1], seen | {marker})
            scope = _lexical_parent_scope(scope)
        return None

    def _module_kind_for_target(target: str) -> str | None:
        if target == "sqlite3" or target.startswith("sqlite3."):
            return "module:sqlite3"
        if target == "app.execution_core.persistence.schema":
            return "module:schema"
        if target == "approved_schema_digest":
            return "module:approval"
        return None

    def _call_argument(
        call: ast.Call,
        name: str,
        positional_index: int,
    ) -> ast.expr | None:
        values: list[ast.expr] = []
        if len(call.args) > positional_index:
            values.append(call.args[positional_index])
        values.extend(keyword.value for keyword in call.keywords if keyword.arg == name)
        return values[0] if len(values) == 1 else None

    def _resolve_relative_target(name: str, package: str) -> str | None:
        depth = len(name) - len(name.lstrip("."))
        if depth == 0:
            return name
        parts = package.split(".")
        if depth > len(parts):
            return None
        prefix = parts[: len(parts) - depth + 1]
        suffix = name[depth:]
        return ".".join((*prefix, suffix)) if suffix else ".".join(prefix)

    def _resolved_import_target(call: ast.Call) -> str | None:
        target_value = _call_argument(call, "name", 0)
        target = None if target_value is None else _resolve_static_string(target_value)
        if target is None:
            return None
        if not target.startswith("."):
            return target
        package_value = _call_argument(call, "package", 1)
        package = (
            None if package_value is None else _resolve_static_string(package_value)
        )
        return None if package is None else _resolve_relative_target(target, package)

    namespace_scopes: dict[str, ast.AST] = {}
    escaped_namespace_factory_scopes: dict[str, ast.AST] = {}

    def _namespace_kind(scope: ast.AST) -> str:
        kind = f"namespace:{id(scope)}"
        namespace_scopes[kind] = scope
        return kind

    def _escaped_namespace_factory_kind(scope: ast.AST) -> str:
        kind = f"namespace-factory:{id(scope)}"
        escaped_namespace_factory_scopes[kind] = scope
        return kind

    def _is_mapping_kind(kind: str | None) -> bool:
        return bool(
            kind == "global-namespace"
            or kind == "module-registry"
            or (isinstance(kind, str) and kind.startswith("namespace:"))
            or (isinstance(kind, str) and kind.startswith("module-map:"))
        )

    _MODULE_MAP_MEMBER_KINDS = {
        "module-map:builtins": {
            "__import__": "importer",
            "eval": "dynamic-code",
            "exec": "dynamic-code",
            "getattr": "getter",
            "globals": "global-namespace-factory",
            "delattr": "attribute-mutator",
            "setattr": "attribute-mutator",
            "vars": "namespace-factory",
        },
        "module-map:importlib": {"import_module": "importer"},
        "module-map:sys": {"modules": "module-registry"},
        "module-registry": {
            "app.execution_core.persistence.schema": "module:schema",
            "approved_schema_digest": "module:approval",
            "builtins": "module:builtins",
            "importlib": "module:importlib",
            "operator": "module:operator",
            "sqlite3": "module:sqlite3",
            "sys": "module:sys",
        },
        "module-map:schema": {"install_schema": "dynamic-installer"},
        "module-map:sqlite3": {
            "connect": "connection-reference",
            "Connection": "connection-reference",
        },
        "module-map:approval": {
            "require_approved_ddl_execution": "approval-accessor",
            "APPROVED_EXECUTION_DDL_SHA256": "approval-token",
        },
    }
    _NAMESPACE_FALLBACK_KINDS = {
        "__builtins__": "module-map:builtins",
        "__import__": "importer",
        "builtins": "module:builtins",
        "eval": "dynamic-code",
        "exec": "dynamic-code",
        "getattr": "getter",
        "globals": "global-namespace-factory",
        "importlib": "module:importlib",
        "delattr": "attribute-mutator",
        "setattr": "attribute-mutator",
        "sqlite3": "module:sqlite3",
        "sys": "module:sys",
        "vars": "namespace-factory",
        "approved_schema_digest": "module:approval",
    }

    def _map_lookup_kind(
        base: str | None,
        key: str | None,
        reference: ast.AST,
    ) -> str | None:
        if base == "unknown-dynamic":
            return "unknown-dynamic"
        if not _is_mapping_kind(base):
            return None
        if key is None:
            return "unknown-dynamic"
        if base == "global-namespace":
            kind = _resolve_scope_name(tree, key, _source_position(reference))
            return (
                _NAMESPACE_FALLBACK_KINDS.get(key, "unknown-dynamic")
                if kind is None
                else kind
            )
        if isinstance(base, str) and base.startswith("namespace:"):
            scope = namespace_scopes[base]
            kind = _resolve_scope_name(scope, key, _source_position(reference))
            return (
                _NAMESPACE_FALLBACK_KINDS.get(key, "unknown-dynamic")
                if kind is None
                else kind
            )
        return _MODULE_MAP_MEMBER_KINDS.get(base, {}).get(key, "unknown-dynamic")

    def _capability_attribute_kind(base: str | None, member: str) -> str | None:
        if base == "unknown-dynamic":
            if member in {"connect", "Connection"}:
                return "connection-reference"
            if member == "install_schema":
                return "dynamic-installer"
            return "unknown-dynamic"
        if _is_mapping_kind(base) and member in {"get", "__getitem__"}:
            return f"map-getter:{base}"
        return {
            ("module:schema", "install_schema"): "installer",
            ("module:schema", "__dict__"): "module-map:schema",
            ("module:schema", "__getattribute__"): "schema-attribute-getter",
            ("module:sqlite3", "__dict__"): "module-map:sqlite3",
            ("module:sqlite3", "__getattribute__"): "unknown-dynamic",
            ("module:approval", "__dict__"): "module-map:approval",
            ("module:approval", "require_approved_ddl_execution"): "approval-accessor",
            (
                "module:approval",
                "APPROVED_EXECUTION_DDL_SHA256",
            ): "approval-token",
            ("module:approval", "__delattr__"): "approval-bound-mutator",
            ("module:approval", "__getattribute__"): "approval-namespace-route",
            ("module:approval", "__setattr__"): "approval-bound-mutator",
            ("module:builtins", "__dict__"): "module-map:builtins",
            ("module:builtins", "__import__"): "importer",
            ("module:builtins", "delattr"): "attribute-mutator",
            ("module:builtins", "eval"): "dynamic-code",
            ("module:builtins", "exec"): "dynamic-code",
            ("module:builtins", "getattr"): "getter",
            ("module:builtins", "globals"): "global-namespace-factory",
            ("module:builtins", "setattr"): "attribute-mutator",
            ("module:builtins", "vars"): "namespace-factory",
            ("module:importlib", "__dict__"): "module-map:importlib",
            ("module:importlib", "import_module"): "importer",
            ("module:operator", "attrgetter"): "attrgetter",
            ("module:sys", "__dict__"): "module-map:sys",
            ("module:sys", "modules"): "module-registry",
        }.get((base, member))

    def _static_capability_lookup_kind(
        value: ast.Call,
        seen: frozenset[tuple[ast.AST, str]] = frozenset(),
    ) -> str | None:
        if _resolve_capability_expression(value.func, seen) != "getter":
            return None
        base_value = _call_argument(value, "object", 0)
        member_value = _call_argument(value, "name", 1)
        if base_value is None or member_value is None:
            return None
        base = _resolve_capability_expression(base_value, seen)
        member = _resolve_static_string(member_value, seen) or ""
        if base == "module:sqlite3" and member in {"connect", "Connection"}:
            return "connection-reference"
        return _capability_attribute_kind(base, member)

    def _resolve_capability_expression(
        value: ast.expr,
        seen: frozenset[tuple[ast.AST, str]] = frozenset(),
    ) -> str | None:
        if isinstance(value, ast.Name):
            return _resolve_capability_name(value, seen)
        if isinstance(value, ast.NamedExpr):
            return _resolve_capability_expression(value.value, seen)
        if isinstance(value, ast.Subscript):
            return _map_lookup_kind(
                _resolve_capability_expression(value.value, seen),
                _resolve_static_string(value.slice, seen),
                value,
            )
        if isinstance(value, ast.Attribute):
            return _capability_attribute_kind(
                _resolve_capability_expression(value.value, seen), value.attr
            )
        if not isinstance(value, ast.Call):
            return None
        static_lookup = _static_capability_lookup_kind(value, seen)
        if static_lookup is not None:
            return static_lookup
        function_kind = _resolve_capability_expression(value.func, seen)
        if function_kind == "global-namespace-factory":
            return (
                "global-namespace"
                if not value.args and not value.keywords
                else "unknown-dynamic"
            )
        if function_kind == "namespace-factory":
            if not value.args and not value.keywords:
                return _namespace_kind(_capability_scope(value))
            if len(value.args) == 1 and not value.keywords:
                module_kind = _resolve_capability_expression(value.args[0], seen)
                return (
                    f"module-map:{module_kind.removeprefix('module:')}"
                    if isinstance(module_kind, str)
                    and module_kind.startswith("module:")
                    else None
                )
            return "unknown-dynamic"
        if isinstance(function_kind, str) and function_kind.startswith(
            "namespace-factory:"
        ):
            if not value.args and not value.keywords:
                return _namespace_kind(escaped_namespace_factory_scopes[function_kind])
            return "unknown-dynamic"
        if function_kind == "importer":
            target = _resolved_import_target(value)
            return (
                "unknown-dynamic"
                if target is None
                else (_module_kind_for_target(target) or "ordinary")
            )
        if isinstance(function_kind, str) and function_kind.startswith("map-getter:"):
            key_value = _call_argument(value, "key", 0)
            return _map_lookup_kind(
                function_kind.removeprefix("map-getter:"),
                None if key_value is None else _resolve_static_string(key_value, seen),
                value,
            )
        if function_kind == "schema-attribute-getter":
            member_value = _call_argument(value, "name", 0)
            return (
                "dynamic-installer"
                if member_value is not None
                and _resolve_static_string(member_value, seen) == "install_schema"
                else "unknown-dynamic"
            )
        if function_kind == "attrgetter":
            member_value = _call_argument(value, "attr", 0)
            member = (
                None
                if member_value is None
                else _resolve_static_string(member_value, seen)
            )
            return None if member is None else f"attrgetter:{member}"
        if (
            isinstance(function_kind, str)
            and function_kind.startswith("attrgetter:")
            and value.args
        ):
            return _capability_attribute_kind(
                _resolve_capability_expression(value.args[0], seen),
                function_kind.removeprefix("attrgetter:"),
            )
        if function_kind == "unknown-dynamic":
            return "unknown-dynamic"
        if not isinstance(value.func, ast.Attribute):
            return None
        if (
            isinstance(value.func.value, ast.Name)
            and value.func.value.id == "dict"
            and value.func.attr in {"get", "__getitem__"}
            and len(value.args) >= 2
        ):
            return _map_lookup_kind(
                _resolve_capability_expression(value.args[0], seen),
                _resolve_static_string(value.args[1], seen),
                value,
            )
        return None

    def _direct_dynamic_import_target(call: ast.Call) -> str | None:
        if _resolve_capability_expression(call.func) != "importer":
            return None
        return _resolved_import_target(call)

    def _is_dynamic_sqlite_acquisition(value: ast.AST) -> bool:
        parent = parents.get(value)
        grandparent = parents.get(parent) if parent is not None else None
        is_member_reference = bool(
            isinstance(parent, ast.Attribute)
            and parent.value is value
            and parent.attr in {"connect", "Connection"}
            and not (isinstance(grandparent, ast.Call) and grandparent.func is parent)
        )
        is_static_getter_reference = bool(
            isinstance(parent, ast.Call)
            and _is_getattr_call(parent)
            and parent.args
            and parent.args[0] is value
            and _resolve_static_string(
                _call_argument(parent, "name", 1) or ast.Constant()
            )
            in {"connect", "Connection"}
        )
        return bool(
            isinstance(value, ast.expr)
            and not isinstance(value, ast.Name)
            and _resolve_capability_expression(value) == "module:sqlite3"
            and not is_member_reference
            and not is_static_getter_reference
        )

    def _is_dynamic_connection_reference(value: ast.AST) -> bool:
        return bool(
            isinstance(value, ast.expr)
            and (
                _resolve_capability_expression(value) == "connection-reference"
                or (
                    isinstance(value, ast.Attribute)
                    and value.attr in {"connect", "Connection"}
                    and not isinstance(value.value, ast.Name)
                    and _is_sqlite_owned_expression(value.value)
                )
            )
        )

    def _is_installer_call(call: ast.Call) -> bool:
        return _resolve_capability_expression(call.func) in {
            "dynamic-installer",
            "installer",
        }

    def _is_vars_call(call: ast.Call) -> bool:
        return bool(
            isinstance(_resolve_capability_expression(call), str)
            and _resolve_capability_expression(call).startswith("module-map:")
        )

    def _is_current_global_namespace_call(call: ast.Call) -> bool:
        return _resolve_capability_expression(call) == "global-namespace"

    def _approval_mutation_message(member: str | None) -> str:
        return (
            "approval token mutation route"
            if member == "APPROVED_EXECUTION_DDL_SHA256"
            else "approval module mutation route"
        )

    def _is_module_registry_mutation_call(call: ast.Call) -> bool:
        if not isinstance(call.func, ast.Attribute):
            return False
        if _resolve_capability_expression(call.func.value) == "module-registry":
            return call.func.attr not in {"get", "__getitem__"}
        return bool(
            isinstance(call.func.value, ast.Name)
            and call.func.value.id == "dict"
            and call.func.attr not in {"get", "__getitem__"}
            and call.args
            and _resolve_capability_expression(call.args[0]) == "module-registry"
        )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and (target := _direct_dynamic_import_target(node)) is not None
        ):
            module_kind = _module_kind_for_target(target)
            if module_kind in {"module:schema", "module:sqlite3"}:
                violations.append(
                    f"{label}:{node.lineno}: literal dynamic SQLite/schema import"
                )
            elif module_kind == "module:approval":
                violations.append(
                    f"{label}:{node.lineno}: literal dynamic approval module import"
                )
        if _is_dynamic_sqlite_acquisition(node):
            violations.append(
                f"{label}:{node.lineno}: SQLite connection route is not direct"
            )
        if _is_dynamic_connection_reference(node):
            parent = parents.get(node)
            if isinstance(parent, ast.Call) and parent.func is node:
                violations.append(
                    f"{label}:{node.lineno}: SQLite connection route is not direct"
                )
            else:
                violations.append(
                    f"{label}:{node.lineno}: SQLite connection reference escapes direct call"
                )
            if isinstance(node, ast.Call):
                continue
        if (
            isinstance(node, ast.Call)
            and _resolve_capability_expression(node.func) == "dynamic-code"
        ):
            source_value = _call_argument(node, "source", 0)
            source_text = (
                None if source_value is None else _resolve_static_string(source_value)
            )
            if has_gate_surface or (
                source_text is not None
                and any(
                    marker in source_text
                    for marker in (
                        "sqlite3",
                        "install_schema",
                        "approved_schema_digest",
                    )
                )
            ):
                violations.append(f"{label}:{node.lineno}: dynamic code route")
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            kind = (
                _resolve_capability_expression(value)
                if isinstance(value, ast.expr)
                else None
            )
            if kind in {"module:approval", "module:schema", "module:sqlite3"}:
                violations.append(f"{label}:{node.lineno}: module alias")
        if isinstance(node, ast.Attribute):
            owner_kind = _resolve_capability_expression(node.value)
            if owner_kind == "module:approval" and isinstance(
                node.ctx, (ast.Store, ast.Del)
            ):
                violations.append(
                    f"{label}:{node.lineno}: {_approval_mutation_message(node.attr)}"
                )
            if owner_kind == "module:approval" and node.attr == "__getattribute__":
                violations.append(
                    f"{label}:{node.lineno}: approval module namespace route"
                )
            if owner_kind == "module:schema" and node.attr == "__dict__":
                violations.append(
                    f"{label}:{node.lineno}: schema module namespace route"
                )
        if isinstance(node, ast.Call):
            mutation_kind = _resolve_capability_expression(node.func)
            if mutation_kind == "attribute-mutator":
                subject = _call_argument(node, "object", 0)
                member = _call_argument(node, "name", 1)
                if (
                    subject is not None
                    and _resolve_capability_expression(subject) == "module:approval"
                ):
                    violations.append(
                        f"{label}:{node.lineno}: "
                        f"{_approval_mutation_message(None if member is None else _resolve_static_string(member))}"
                    )
            elif mutation_kind == "approval-bound-mutator":
                member = _call_argument(node, "name", 0)
                violations.append(
                    f"{label}:{node.lineno}: "
                    f"{_approval_mutation_message(None if member is None else _resolve_static_string(member))}"
                )
        if isinstance(node, ast.Call) and _is_module_registry_mutation_call(node):
            violations.append(f"{label}:{node.lineno}: module registry mutation route")
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "module-map:approval"
        ):
            violations.append(f"{label}:{node.lineno}: approval module namespace route")
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "approval-bound-mutator"
        ):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                violations.append(
                    f"{label}:{node.lineno}: approval module mutation route"
                )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "approval-namespace-route"
        ):
            violations.append(f"{label}:{node.lineno}: approval module namespace route")
        if not has_gate_surface:
            continue
        if (
            isinstance(node, ast.Name)
            and node.id == "__builtins__"
            and _resolve_capability_expression(node) == "module-map:builtins"
        ):
            violations.append(f"{label}:{node.lineno}: dynamic builtin namespace route")
        if (
            canonical_gate_imports
            and isinstance(node, ast.Call)
            and _is_current_global_namespace_call(node)
        ):
            violations.append(
                f"{label}:{node.lineno}: approval accessor namespace route"
            )
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            kind = (
                _resolve_capability_expression(value)
                if isinstance(value, ast.expr)
                else None
            )
            if kind in {
                "getter",
                "global-namespace-factory",
                "namespace-factory",
            } or _is_mapping_kind(kind):
                violations.append(f"{label}:{node.lineno}: dynamic namespace alias")
        if isinstance(node, ast.Attribute):
            if (
                canonical_gate_imports
                and node.attr == "__globals__"
                and _resolve_capability_expression(node.value) == "approval-accessor"
            ):
                violations.append(
                    f"{label}:{node.lineno}: approval accessor namespace route"
                )
            if (
                canonical_gate_imports
                and node.attr == "modules"
                and _resolve_capability_expression(node) == "module-registry"
            ):
                violations.append(
                    f"{label}:{node.lineno}: approval module registry route"
                )
            if node.attr == "__dict__" and (
                _is_schema_module_expression(node.value)
                or _is_sqlite_owned_expression(node.value)
                or _resolve_capability_expression(node.value) == "module:approval"
            ):
                violations.append(f"{label}:{node.lineno}: module namespace route")
            if node.attr == "__getattribute__" and _is_sqlite_owned_expression(
                node.value
            ):
                violations.append(
                    f"{label}:{node.lineno}: SQLite module namespace route"
                )
            if node.attr == "connect" and _is_sqlite_owned_expression(node.value):
                parent = parents.get(node)
                if not (isinstance(parent, ast.Call) and parent.func is node):
                    violations.append(
                        f"{label}:{node.lineno}: SQLite connection reference escapes direct call"
                    )
        if not isinstance(node, ast.Call):
            continue
        if (
            (_is_getattr_call(node) or _is_vars_call(node))
            and node.args
            and (
                _is_schema_module_expression(node.args[0])
                or _is_sqlite_owned_expression(node.args[0])
            )
        ):
            violations.append(f"{label}:{node.lineno}: dynamic module attribute route")
        if (
            isinstance(node.func, ast.Call)
            and _is_attrgetter_call(node.func)
            and node.args
            and (
                _is_schema_module_expression(node.args[0])
                or _is_sqlite_owned_expression(node.args[0])
            )
        ):
            violations.append(f"{label}:{node.lineno}: dynamic module attribute route")
        if _is_sqlite_acquisition_call(node):
            if not _is_direct_sqlite_connect_call(node):
                violations.append(
                    f"{label}:{node.lineno}: SQLite connection route is not direct"
                )
                continue
            owner = _nearest_enclosing_function(node, parents)
            if owner is None:
                violations.append(
                    f"{label}:{node.lineno}: SQLite connection is not function-bound"
                )
            elif not _is_direct_function_body_call(node, owner):
                violations.append(
                    f"{label}:{node.lineno}: SQLite connection is not in a direct function body"
                )
            elif not _gate_dominates_connection(owner):
                violations.append(
                    f"{label}:{node.lineno}: approval gate does not dominate SQLite connect"
                )

    for node in ast.walk(tree):
        if isinstance(node, ast.expr) and _resolve_capability_expression(node) in {
            "dynamic-installer",
            "installer",
        }:
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                if isinstance(node, ast.Name):
                    message = "installer reference escapes direct call"
                elif isinstance(node, ast.Attribute):
                    message = "installer attribute escapes direct call"
                else:
                    message = "dynamic installer reference escapes direct call"
                violations.append(f"{label}:{node.lineno}: {message}")
        elif isinstance(node, ast.Call) and _dynamic_installer_getter(node):
            violations.append(f"{label}:{node.lineno}: dynamic installer lookup")
        if not isinstance(node, ast.Call) or not _is_installer_call(node):
            continue
        if _resolve_capability_expression(node.func) == "dynamic-installer":
            violations.append(f"{label}:{node.lineno}: dynamic installer route")
        owner = _nearest_enclosing_function(node, parents)
        if owner is None:
            violations.append(f"{label}:{node.lineno}: installer is not function-bound")
        else:
            connection_calls = tuple(
                candidate
                for candidate in ast.walk(owner)
                if isinstance(candidate, ast.Call)
                and _nearest_enclosing_function(candidate, parents) is owner
                and _is_sqlite_acquisition_call(candidate)
            )
            if connection_calls and not _gate_dominates_connection(owner):
                violations.append(
                    f"{label}:{node.lineno}: approval gate does not dominate SQLite connect"
                )
            if any(isinstance(call.func, ast.Call) for call in connection_calls):
                violations.append(
                    f"{label}:{node.lineno}: dynamic SQLite connection lookup"
                )
        if not canonical_gate_is_exact:
            violations.append(
                f"{label}:{node.lineno}: approval accessor binding is not canonical"
            )
        if any(keyword.arg is None for keyword in node.keywords):
            violations.append(f"{label}:{node.lineno}: installer accepts **kwargs")
            continue
        matching = [
            keyword for keyword in node.keywords if keyword.arg == "approved_ddl_sha256"
        ]
        if len(matching) != 1 or not _is_exact_gate_call(matching[0].value):
            violations.append(
                f"{label}:{node.lineno}: installer lacks exact approval accessor"
            )
    return violations


def test_changed_ddl_installers_have_one_fail_closed_human_gate() -> None:
    """REV-0078 P0-1: every installer has exactly one approval provenance.

    Candidate DDL identity is evidence; it is not authorization.  Before a human
    records an exact approval, the centrally held token is ``None`` and every
    SQLite-bearing fixture refuses before opening a connection.  This source audit
    remains valid after the separate one-line unlock commit, so the behavior of the
    locked state is proved independently below rather than hard-coding ``None`` here.
    """

    repository_root = Path(__file__).resolve().parents[2]
    paths = sorted(
        (
            *repository_root.joinpath("tests", "execution_core").glob("*.py"),
            *repository_root.joinpath("app", "execution_core").rglob("*.py"),
        ),
        key=lambda candidate: candidate.as_posix(),
    )
    violations = [
        violation
        for path in paths
        for violation in _schema_installer_gate_violations(
            path.read_text(encoding="utf-8"),
            path.relative_to(repository_root).as_posix(),
        )
    ]
    assert violations == [], violations


def test_changed_ddl_execution_gate_refuses_without_a_valid_human_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The approval accessor stays fail-closed before any fixture can connect."""

    import approved_schema_digest as gate

    monkeypatch.setattr(gate, "APPROVED_EXECUTION_DDL_SHA256", None)
    with pytest.raises(RuntimeError, match="HUMAN-GATE pending"):
        gate.require_approved_ddl_execution()
    for malformed in ("", "AB" * 32, 1):
        monkeypatch.setattr(gate, "APPROVED_EXECUTION_DDL_SHA256", malformed)
        with pytest.raises(RuntimeError, match="HUMAN-GATE invalid"):
            gate.require_approved_ddl_execution()

    approved = "ab" * 32
    monkeypatch.setattr(gate, "APPROVED_EXECUTION_DDL_SHA256", approved)
    assert gate.require_approved_ddl_execution() == approved


def test_changed_ddl_gate_audit_refuses_bypass_spellings() -> None:
    """The approval audit is failure-capable for each known bypass family."""

    valid = """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
def install(connection):
    return install_schema(connection, approved_ddl_sha256=require_approved_ddl_execution())
"""
    assert _schema_installer_gate_violations(valid, "valid.py") == []

    mutants = (
        # Helper source.
        """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
def gate_helper(): return require_approved_ddl_execution()
install_schema(connection, approved_ddl_sha256=gate_helper())
""",
        # Aliased gate source.
        """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution as approved
install_schema(connection, approved_ddl_sha256=approved())
""",
        # Locally retained or computed value.
        """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
digest = require_approved_ddl_execution()
install_schema(connection, approved_ddl_sha256=digest)
""",
        # Duplicate literal.
        """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
install_schema(connection, approved_ddl_sha256='00' * 32)
""",
        # Self-derived or alternate approval module.
        """
from app.execution_core.persistence.schema import install_schema, schema_ddl_digest
from other_gate import approval
install_schema(connection, approved_ddl_sha256=schema_ddl_digest())
""",
        # Installer alias prevents complete call-site accounting.
        """
from app.execution_core.persistence.schema import install_schema as installer
from approved_schema_digest import require_approved_ddl_execution
installer(connection, approved_ddl_sha256=require_approved_ddl_execution())
""",
        # Local installer aliases and dynamic lookup both evade simple call-name scans.
        """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
installer = install_schema
installer(connection, approved_ddl_sha256=require_approved_ddl_execution())
""",
        """
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
getattr(schema, 'install_schema')(connection, approved_ddl_sha256=require_approved_ddl_execution())
""",
        # Composition must not evade the dynamic schema lookup rule.
        """
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
def install(connection):
    return getattr(schema, 'install_' + 'schema')(
        connection, approved_ddl_sha256=schema.schema_ddl_digest()
    )
""",
        # A dynamically imported schema module is also an unprovable installer route.
        """
import importlib
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def install(path):
    require_approved_ddl_execution()
    connection = sqlite3.connect(path)
    schema = importlib.import_module('app.execution_core.persistence.' + 'schema')
    return getattr(schema, 'install_' + 'schema')(
        connection, approved_ddl_sha256=schema.schema_ddl_digest()
    )
""",
    )
    for ordinal, mutant in enumerate(mutants, 1):
        assert _schema_installer_gate_violations(mutant, f"mutant-{ordinal}.py")


def test_changed_ddl_gate_audit_requires_the_gate_before_connection_open() -> None:
    """An installer route may not create a SQLite connection then seek approval."""

    valid = """
import sqlite3
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
def install(path):
    require_approved_ddl_execution()
    connection = sqlite3.connect(path)
    return install_schema(connection, approved_ddl_sha256=require_approved_ddl_execution())
"""
    assert _schema_installer_gate_violations(valid, "valid-order.py") == []

    late_gate = """
import sqlite3
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
def install(path):
    connection = sqlite3.connect(path)
    return install_schema(connection, approved_ddl_sha256=require_approved_ddl_execution())
"""
    violations = _schema_installer_gate_violations(late_gate, "late-gate.py")
    assert any(
        "does not dominate SQLite connect" in violation for violation in violations
    )

    connection_only = """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    connection = sqlite3.connect(path)
    require_approved_ddl_execution()
    return connection
"""
    violations = _schema_installer_gate_violations(
        connection_only, "connection-only.py"
    )
    assert any(
        "does not dominate SQLite connect" in violation for violation in violations
    )


def test_changed_ddl_gate_audit_refuses_indirect_connection_and_installer_routes() -> (
    None
):
    """The gate accepts only direct, statically accountable route spellings."""

    mutants = (
        # Assignment can hide a pre-gate connection acquisition from a call-name scan.
        """
import sqlite3
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
def install(path):
    connector = sqlite3.connect
    connection = connector(path)
    return install_schema(connection, approved_ddl_sha256=require_approved_ddl_execution())
""",
        # Aliasing import_module hides both the imported schema module and installer.
        """
import sqlite3
from importlib import import_module as module_loader
from approved_schema_digest import require_approved_ddl_execution
def install(path):
    require_approved_ddl_execution()
    connection = sqlite3.connect(path)
    schema = module_loader('app.execution_core.persistence.schema')
    return getattr(schema, 'install_schema')(
        connection, approved_ddl_sha256=require_approved_ddl_execution()
    )
""",
        # Namespace dictionaries are an equally dynamic installer recovery route.
        """
import sqlite3
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
def install(path):
    require_approved_ddl_execution()
    connection = sqlite3.connect(path)
    return vars(schema)['install_schema'](
        connection, approved_ddl_sha256=require_approved_ddl_execution()
    )
""",
        # Attribute factories must not substitute for a direct installer call.
        """
import operator
import sqlite3
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
def install(path):
    require_approved_ddl_execution()
    connection = sqlite3.connect(path)
    return operator.attrgetter('install_schema')(schema)(
        connection, approved_ddl_sha256=require_approved_ddl_execution()
    )
""",
        # Function-local imports cannot hide a connection or installer route.
        """
from approved_schema_digest import require_approved_ddl_execution
def install(path):
    import sqlite3
    from app.execution_core.persistence.schema import install_schema
    require_approved_ddl_execution()
    connection = sqlite3.connect(path)
    return install_schema(connection, approved_ddl_sha256=require_approved_ddl_execution())
""",
    )
    for ordinal, mutant in enumerate(mutants, 1):
        assert _schema_installer_gate_violations(mutant, f"indirect-{ordinal}.py")


def test_rev0081_gate_audit_requires_canonical_runtime_provenance() -> None:
    """The held DDL gate accepts one direct, runtime-safe source grammar only."""

    rejected = (
        (
            # A same-spelled local helper is not the human approval accessor.
            """
import sqlite3
def require_approved_ddl_execution():
    return 'forged'
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
""",
            "approval gate does not dominate SQLite connect",
        ),
        (
            # The imported accessor cannot be reassigned before the connect route.
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
original = require_approved_ddl_execution
require_approved_ddl_execution = original
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
""",
            "approval gate does not dominate SQLite connect",
        ),
        (
            # A literal dynamic SQLite import is still a connection route.
            """
import importlib
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return importlib.import_module('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return __import__('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import builtins
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return builtins.__import__('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
from builtins import __import__ as module_loader
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return module_loader('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return __builtins__['__import__']('sqlite3').connect(path)
""",
            "dynamic builtin namespace route",
        ),
        (
            """
import importlib
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return getattr(importlib, 'import_module')('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            # Alternate public sqlite3 module paths are not the accepted grammar.
            """
from sqlite3 import dbapi2
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return dbapi2.connect(path)
""",
            "SQLite import must be module-bound",
        ),
        (
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.dbapi2.connect(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            # Defaults execute while the function is defined, before its body gate.
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def open_connection(connection=sqlite3.connect('would-open.db')):
    require_approved_ddl_execution()
    return connection
""",
            "SQLite connection is not in a direct function body",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0081-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations

    unrelated = """
class DocumentInstaller:
    def install_schema(self):
        return 'document-only'
DocumentInstaller().install_schema()
"""
    assert _schema_installer_gate_violations(unrelated, "unrelated.py") == []


def test_rev0082_gate_audit_refuses_remaining_connection_and_provenance_routes() -> (
    None
):
    """Each R20 gate rule has a focused, failure-capable source mutant."""

    rejected = (
        (
            """
from sqlite3.dbapi2 import connect
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return connect(path)
""",
            "SQLite import must be module-bound",
        ),
        (
            """
import sqlite3.dbapi2
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.dbapi2.connect(path)
""",
            "SQLite module import must be exact",
        ),
        (
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.Connection(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.__getattribute__('connect')(path)
""",
            "SQLite module namespace route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    import importlib
    require_approved_ddl_execution()
    return importlib.import_module('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return __import__('sqlite' + '3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
from forged_gate import *
""",
            "wildcard import may rebind approval accessor",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
globals()['require_approved_ddl_execution'] = forged
""",
            "approval accessor namespace route",
        ),
        (
            """
import approved_schema_digest as gate
from approved_schema_digest import require_approved_ddl_execution
gate.APPROVED_EXECUTION_DDL_SHA256 = 'forged'
""",
            "approval module import is not canonical",
        ),
        (
            """
import sys
from approved_schema_digest import require_approved_ddl_execution
sys.modules['approved_schema_digest'].require_approved_ddl_execution = forged
""",
            "approval module registry route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
require_approved_ddl_execution.__globals__['APPROVED_EXECUTION_DDL_SHA256'] = 'forged'
""",
            "approval accessor namespace route",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0082-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations

    unrelated = """
class DocumentInstaller:
    def install_schema(self):
        return 'document-only'
saved = DocumentInstaller().install_schema
"""
    assert _schema_installer_gate_violations(unrelated, "bound-unrelated.py") == []


def test_rev0083_gate_audit_refuses_missing_gate_dynamic_acquisition() -> None:
    """Only canonical ``sqlite3.connect`` may reach the held DDL gate."""

    rejected = (
        """
def open_connection(path):
    return __import__('sqlite' + '3').connect(path)
""",
        """
def open_connection(path):
    return globals()['sqlite3'].connect(path)
""",
        """
import sys
def open_connection(path):
    return sys.modules['sqlite3'].connect(path)
""",
        """
def open_connection(path):
    module_name = 'sqlite3'
    module = __import__(module_name)
    return module.connect(path)
""",
        """
def open_connection(path):
    namespace = globals()
    module = namespace['sqlite3']
    return module.connect(path)
""",
        """
def open_connection(path):
    from importlib import import_module as loader
    return loader('sqlite' + '3').connect(path)
""",
        """
def open_connection(path):
    from builtins import __import__ as loader
    return loader('sqlite' + '3').connect(path)
""",
        """
def open_connection(path):
    return __builtins__['__import__']('sqlite' + '3').connect(path)
""",
        """
def open_connection(path):
    return globals().get('sqlite3').connect(path)
""",
        """
def open_connection(path):
    return vars().get('sqlite3').Connection(path)
""",
        """
import sys
def open_connection(path):
    return sys.modules.get('sqlite3').connect(path)
""",
        """
def open_connection(path):
    return globals().__getitem__('sqlite3').connect(path)
""",
        """
def open_connection(path):
    return globals()['__builtins__']['__import__']('sqlite3').connect(path)
""",
        """
def open_connection(path):
    namespace = globals()
    builtins_namespace = namespace['__builtins__']
    loader = builtins_namespace['__import__']
    return loader('sqlite3').connect(path)
""",
        """
def open_connection(path):
    factory = globals
    return factory()['sqlite3'].connect(path)
""",
        """
def open_connection(path):
    getter = globals().get
    return getter('sqlite3').connect(path)
""",
        """
def open_connection(path):
    factory = vars
    getter = factory().__getitem__
    return getter('sqlite3').Connection(path)
""",
        """
import sys
def open_connection(path):
    getter = sys.modules.get
    return getter('sqlite3').Connection(path)
""",
        """
def open_connection(path):
    namespace = globals()
    builtins_getter = namespace.get
    builtins_namespace = builtins_getter('__builtins__')
    loader_getter = builtins_namespace.get
    loader = loader_getter('__import__')
    return loader('sqlite3').connect(path)
""",
    )
    for ordinal, source in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0083-{ordinal}.py")
        assert any(
            "SQLite connection route is not direct" in violation
            for violation in violations
        ), f"mutant {ordinal}: {violations}"

    escaped_references = (
        """
def open_connection(path):
    operation = globals()['sqlite3'].connect
    return operation(path)
""",
        """
def open_connection(path):
    operation = globals().get('sqlite3').Connection
    return operation(path)
""",
    )
    for ordinal, source in enumerate(escaped_references, 1):
        violations = _schema_installer_gate_violations(source, f"escaped-{ordinal}.py")
        assert any(
            "SQLite connection reference escapes direct call" in violation
            for violation in violations
        ), f"escaped mutant {ordinal}: {violations}"

    ordinary_client = """
SQLITE_DRIVER_LABEL = 'sqlite3'
class Client:
    def import_module(self, target):
        return self
    def get(self, target):
        return self
    def __getitem__(self, target):
        return self
    def connect(self, path):
        return path
def open_connection(path):
    return Client().import_module('transport').connect(path)
def open_with_getattr(path):
    return getattr(Client(), 'import_module')('transport').connect(path)
def open_with_lookup_alias(path):
    getter = Client().get
    return getter('sqlite3').connect(path)
def open_with_item_alias(path):
    getter = Client().__getitem__
    return getter('sqlite3').Connection(path)
"""
    assert (
        _schema_installer_gate_violations(ordinary_client, "ordinary-client.py") == []
    )

    exception_only = """
import sqlite3
def injected_error():
    return sqlite3.DatabaseError('test-only')
"""
    assert _schema_installer_gate_violations(exception_only, "exception-only.py") == []


def test_rev0086_gate_audit_tracks_bounded_dynamic_provenance() -> None:
    """Historical alias/accessor routes remain rejected without client-name guesses."""

    rejected = (
        (
            """
def outer():
    module = globals()['sqlite3']
    def open_connection(path):
        return module.connect(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
factory = globals
factory = vars
def open_connection(path):
    return factory()['sqlite3'].connect(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
def open_connection(path):
    return (factory := globals)()['sqlite3'].connect(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
def open_connection(path):
    return dict.get(globals(), 'sqlite3').connect(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
def open_connection(path):
    return dict.__getitem__(globals(), 'sqlite3').Connection(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
def open_connection(path):
    factory = globals
    mapping = factory()
    lookup = getattr(mapping, 'get')
    return lookup('sqlite3').connect(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
def open_connection(path):
    factory = globals
    module = factory()['sqlite3']
    return getattr(module, 'connect')(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
def open_connection(path):
    operation = getattr(globals()['sqlite3'], 'Connection')
    return operation(path)
""",
            "SQLite connection reference escapes direct call",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0086-{ordinal}.py")
        assert any(expected in violation for violation in violations), (
            f"rev0086 mutant {ordinal}: {violations}"
        )

    escaped = """
def open_connection(path):
    operation = globals()['sqlite3'].connect
    return operation(path)
"""
    violations = _schema_installer_gate_violations(escaped, "rev0086-escaped.py")
    assert any(
        "SQLite connection reference escapes direct call" in violation
        for violation in violations
    ), violations

    ordinary_client = """
SQLITE_DRIVER_LABEL = 'sqlite3'
class Client:
    def import_module(self, target):
        return self
    def get(self, target):
        return self
    def __getitem__(self, target):
        return self
    def connect(self, path):
        return path
def open_connection(path):
    lookup = getattr(Client(), 'get')
    return lookup('sqlite3').connect(path)
def open_with_dict_get(path):
    return Client().get('sqlite3').Connection(path)
"""
    assert _schema_installer_gate_violations(ordinary_client, "rev0086-client.py") == []


def test_rev0087_gate_audit_refuses_dynamic_capability_cross_scope_routes() -> None:
    """A capability region is fail-closed without emulating Python bindings."""

    rejected = (
        # A later outer binding still governs the nested connection endpoint.
        """
def outer():
    def open_connection(path):
        return module.connect(path)
    module = globals()['sqlite3']
    return open_connection
""",
        # Explicit aliases of the privileged namespace/import roots are no safer.
        """
from builtins import globals as namespace_factory
def open_connection(path):
    return namespace_factory()['sqlite3'].connect(path)
""",
        """
import builtins as runtime_builtins
def open_connection(path):
    return runtime_builtins.globals()['sqlite3'].connect(path)
""",
        """
import sys as runtime_sys
def open_connection(path):
    return runtime_sys.modules['sqlite3'].Connection(path)
""",
        # A generic accessor becomes a connection route only inside that region.
        """
def outer():
    module = globals()['sqlite3']
    def open_connection(path):
        member = getattr
        return member(module, 'connect')(path)
    return open_connection
""",
        # A global hand-off crosses sibling functions through the module scope.
        """
module = None
def recover():
    global module
    module = globals()['sqlite3']
def open_connection(path):
    return module.connect(path)
""",
        # A nonlocal hand-off crosses sibling functions through the outer scope.
        """
def outer():
    module = None
    def recover():
        nonlocal module
        module = globals()['sqlite3']
    def open_connection(path):
        return module.connect(path)
    return open_connection
""",
    )
    for ordinal, source in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0087-{ordinal}.py")
        assert any(
            "SQLite connection route is not direct" in violation
            for violation in violations
        ), f"rev0087 mutant {ordinal}: {violations}"

    unrelated_fixture_delegation = """
import builtins
import sys
def registered_fixture():
    return globals()['document_fixture']
class Client:
    def get(self, target):
        return self
    def connect(self, path):
        return path
def open_connection(path):
    return Client().get('sqlite3').connect(path)
"""
    assert (
        _schema_installer_gate_violations(
            unrelated_fixture_delegation, "unrelated-fixture-client.py"
        )
        == []
    )


def test_rev0089_gate_audit_recognizes_dynamic_acquisition_precisely() -> None:
    """Reject dynamic SQLite acquisition or endpoints without tainting nearby code."""

    rejected = (
        # Static access to a known capability module is a real dynamic source.
        """
import builtins
def open_connection(path):
    return getattr(builtins, 'globals')()['sqlite3'].connect(path)
""",
        """
import importlib
def open_connection(path):
    return getattr(importlib, 'import_module')('sqlite3').Connection(path)
""",
        """
import sys
def open_connection(path):
    return getattr(sys, 'modules')['sqlite3'].connect(path)
""",
        # A known SQLite acquisition is rejected at its source, even if it is
        # returned or supplied to a callback rather than opened locally.
        """
def recover_module():
    return globals()['sqlite3']
def open_connection(path):
    return recover_module().connect(path)
""",
        """
def recover_module(callback):
    return callback(globals()['sqlite3'])
def open_connection(path):
    return recover_module(lambda module: module.connect(path))
""",
        # A lexically proven getter alias is still a dynamic endpoint lookup.
        """
def open_connection(path):
    module = globals()['sqlite3']
    member = getattr
    return member(module, 'connect')(path)
""",
        # Unknown dynamic values are only disallowed when they reach the
        # connection surface; ordinary reflection remains outside this grammar.
        """
def open_connection(module_name, path):
    return globals()[module_name].connect(path)
""",
        """
import importlib
def open_connection(module_name, path):
    return importlib.import_module(module_name).Connection(path)
""",
        """
import importlib
sqlite_module_name = 'sqlite3'
def recover_module():
    return importlib.import_module(sqlite_module_name)
""",
        """
import importlib
def recover_module():
    return importlib.import_module(name='sqlite3')
""",
    )
    for ordinal, source in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0089-{ordinal}.py")
        assert any(
            "SQLite connection route is not direct" in violation
            for violation in violations
        ), f"rev0089 mutant {ordinal}: {violations}"

    accepted = (
        # A local alias and a static non-privileged map lookup do not turn an
        # unrelated client endpoint into SQLite.
        """
def register_document_fixture():
    namespace = globals
    return namespace()['document_fixture']
class Client:
    def get(self, target):
        return self
    def connect(self, path):
        return path
def open_connection(path):
    return Client().get('sqlite3').connect(path)
""",
        """
def direct_control(test_name):
    return globals()[test_name]
""",
        # A string argument alone does not make an arbitrary call a lookup.
        """
def open_connection(client, path):
    globals()['document_fixture']
    emit(client, 'connect')
    return client.get('sqlite3').connect(path)
""",
        # A parameter shadows an imported capability module name.
        """
import importlib
def open_connection(importlib, path):
    return importlib.import_module('sqlite3').connect(path)
""",
        # A parameter may also shadow the direct SQLite module import.
        """
import sqlite3
class Client:
    def connect(self, path):
        return path
def open_connection(sqlite3, path):
    return sqlite3.connect(path)
""",
        # A real canonical route does not make shadowed client parameters
        # privileged elsewhere in the same source file.
        """
import importlib
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def canonical(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
def custom(importlib, path):
    return importlib.import_module('sqlite3').connect(path)
""",
        """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def canonical(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
def custom(sqlite3, path):
    return sqlite3.connect(path)
""",
        # An imported builtin getter may still inspect an ordinary client.
        """
from builtins import getattr as member
class Client:
    def get(self, target):
        return self
    def connect(self, path):
        return path
def open_connection(path):
    return member(Client(), 'get')('sqlite3').connect(path)
""",
        # A static non-SQLite import target stays outside the SQLite grammar.
        """
import importlib
def open_connection(path):
    return importlib.import_module('transport').connect(path)
""",
        """
import importlib
transport_module_name = 'transport'
def open_connection(path):
    return importlib.import_module(transport_module_name).connect(path)
""",
        # A namespace alias keeps a fully static non-privileged lookup local.
        """
from builtins import globals as namespace
def register_document_fixture():
    return namespace()['document_fixture']
class Client:
    def get(self, target):
        return self
    def connect(self, path):
        return path
def open_connection(path):
    return Client().get('sqlite3').connect(path)
""",
    )
    for ordinal, source in enumerate(accepted, 1):
        assert (
            _schema_installer_gate_violations(source, f"rev0089-good-{ordinal}.py")
            == []
        )


def test_rev0090_gate_audit_uses_lexical_bindings_end_to_end() -> None:
    """Capability rules reject real routes without borrowing a shadowed spelling."""

    rejected = (
        (
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
alias = sqlite3
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
""",
            "module alias",
        ),
        (
            """
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
alias = schema
""",
            "module alias",
        ),
        (
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
def inspect_source():
    return eval('1 + 1')
""",
            "dynamic code route",
        ),
        (
            """
import importlib
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def install(path, module_name):
    require_approved_ddl_execution()
    connection = sqlite3.connect(path)
    return importlib.import_module(module_name).install_schema(
        connection,
        approved_ddl_sha256=require_approved_ddl_execution(),
    )
""",
            "dynamic installer route",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0090-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations

    accepted = (
        # A local parameter is an ordinary object even if it shadows an import.
        """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def canonical(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
def custom(sqlite3, path):
    alias = sqlite3
    return alias.connect(path)
""",
        """
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
def custom(schema):
    alias = schema
    return alias.install_schema
""",
        # A static non-SQLite import remains unrelated to the direct route.
        """
import importlib
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def canonical(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
def metadata_module():
    return importlib.import_module('transport')
""",
        # The function name on a custom object is not a builtin evaluator.
        """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
class Client:
    def eval(self):
        return 1
def canonical(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
def custom(client):
    return client.eval()
""",
    )
    for ordinal, source in enumerate(accepted, 1):
        assert (
            _schema_installer_gate_violations(source, f"rev0090-good-{ordinal}.py")
            == []
        )


def test_rev0091_gate_audit_scopes_approval_accessor_bindings_lexically() -> None:
    """Local approval-name shadows do not taint a separate canonical route."""

    accepted = """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution

def canonical(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)

def unrelated(require_approved_ddl_execution):
    return require_approved_ddl_execution()
"""
    assert _schema_installer_gate_violations(accepted, "rev0091-good.py") == []

    rejected = """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution

def forge_gate():
    global require_approved_ddl_execution
    require_approved_ddl_execution = lambda: 'forged'

def canonical(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
"""
    violations = _schema_installer_gate_violations(rejected, "rev0091-bad.py")
    assert any(
        "approval gate does not dominate" in violation for violation in violations
    )


def test_rev0092_gate_audit_models_capability_ownership_at_the_source() -> None:
    """Every governed dynamic route is refused at its real lexical owner."""

    rejected = (
        (
            """
import importlib
importlib.import_module('.dbapi2', 'sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import importlib
importlib.import_module(
    name='.schema',
    package='app.execution_core.persistence',
).install_schema(connection, approved_ddl_sha256='forged')
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import importlib
importlib.__dict__['import_module']('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import importlib
vars(importlib)['import_module']('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import importlib
def default_uses_parent(
    importlib=importlib.import_module('sqlite3').connect(path),
):
    return importlib
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import importlib
values = [importlib for importlib in ()]
importlib.import_module('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import sqlite3
def outer(sqlite3):
    def inner():
        global sqlite3
        return sqlite3.connect(path)
    return inner
""",
            "approval gate does not dominate",
        ),
        (
            """
def outer():
    module = globals()['sqlite3']
    def middle():
        def preserve_owner():
            nonlocal module
            module = module
        return preserve_owner
    def open_connection(path):
        return module.connect(path)
    return open_connection
""",
            "SQLite connection route is not direct",
        ),
        (
            """
import importlib
class CapabilityShadow:
    import sys as importlib
    def open_connection(self, path):
        return importlib.import_module('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import importlib
globals()['importlib'].import_module('sqlite3').connect(path)
""",
            "literal dynamic SQLite/schema import",
        ),
        (
            """
import sys
vars(sys)['modules']['sqlite3'].connect(path)
""",
            "SQLite connection route is not direct",
        ),
        (
            """
eval("__import__('sqlite3').connect('would-open.db')")
""",
            "dynamic code route",
        ),
        (
            """
from app.execution_core.persistence import schema
schema_alias = schema
""",
            "module alias",
        ),
        (
            """
import importlib
def installer_factory(module_name):
    return importlib.import_module(module_name).install_schema
""",
            "installer attribute escapes direct call",
        ),
        (
            """
from app.execution_core.persistence import schema
def installer_factory():
    return vars(schema)['install_schema']
""",
            "dynamic installer reference escapes direct call",
        ),
        (
            """
from app.execution_core.persistence import schema
def installer_factory():
    return schema.__dict__['install_schema']
""",
            "schema module namespace route",
        ),
        (
            """
import operator
from app.execution_core.persistence import schema
def installer_factory():
    return operator.attrgetter('install_schema')(schema)
""",
            "dynamic installer reference escapes direct call",
        ),
        (
            """
import importlib
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
gate = importlib.import_module('approved_schema_digest')
gate.APPROVED_EXECUTION_DDL_SHA256 = (
    '2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5'
)
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
""",
            "approval token mutation route",
        ),
        (
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def forge_gate():
    import approved_schema_digest as gate
    setattr(
        gate,
        'APPROVED_EXECUTION_DDL_SHA256',
        '2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5',
    )
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
""",
            "approval token mutation route",
        ),
        (
            """
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def forge_gate():
    import approved_schema_digest as gate
    vars(gate).update(
        {
            'APPROVED_EXECUTION_DDL_SHA256': (
                '2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5'
            ),
        }
    )
def open_connection(path):
    require_approved_ddl_execution()
    return sqlite3.connect(path)
""",
            "approval module namespace route",
        ),
        (
            """
import sys
def forge_gate():
    setattr(
        sys.modules['approved_schema_digest'],
        'APPROVED_EXECUTION_DDL_SHA256',
        '2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5',
    )
""",
            "approval token mutation route",
        ),
        (
            """
def forge_gate():
    import approved_schema_digest as gate
    delattr(gate, 'APPROVED_EXECUTION_DDL_SHA256')
""",
            "approval token mutation route",
        ),
        (
            """
def forge_gate():
    import approved_schema_digest as gate
    gate.__setattr__(
        'APPROVED_EXECUTION_DDL_SHA256',
        '2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5',
    )
""",
            "approval token mutation route",
        ),
        (
            """
def forge_gate():
    import approved_schema_digest as gate
    getattr(gate, '__setattr__')(
        'APPROVED_EXECUTION_DDL_SHA256',
        '2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5',
    )
""",
            "approval token mutation route",
        ),
        (
            """
def forge_gate():
    import approved_schema_digest as gate
    return gate.__setattr__
""",
            "approval module mutation route",
        ),
        (
            """
from app.execution_core.persistence import schema
schema.__getattribute__('install_schema')(
    connection,
    approved_ddl_sha256='forged',
)
""",
            "dynamic installer route",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0092-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations

    accepted = (
        # vars() resolves the actual local scope, where this spelling is ordinary.
        """
def custom(sqlite3, path):
    return vars()['sqlite3'].connect(path)
""",
        # A same-scope ordinary rebinding replaces the imported capability.
        """
import importlib
class Client:
    def import_module(self, name):
        return self
    def connect(self, path):
        return path
importlib = Client()
importlib.import_module('sqlite3').connect(path)
""",
    )
    for ordinal, source in enumerate(accepted, 1):
        assert (
            _schema_installer_gate_violations(source, f"rev0092-good-{ordinal}.py")
            == []
        )


def test_rev0093_approval_module_is_not_runtime_mutable() -> None:
    """Known mutation primitives cannot alter any approval-module member."""

    rejected = (
        (
            """
import approved_schema_digest as gate
gate.require_approved_ddl_execution = lambda: 'forged'
""",
            "approval module mutation route",
        ),
        (
            """
def forge_gate(member):
    import approved_schema_digest as gate
    setattr(gate, member, 'forged')
""",
            "approval module mutation route",
        ),
        (
            """
import approved_schema_digest as gate
gate.__setattr__('require_approved_ddl_execution', lambda: 'forged')
""",
            "approval module mutation route",
        ),
        (
            """
from approved_schema_digest import __dict__ as approval_namespace
approval_namespace.update({'APPROVED_EXECUTION_DDL_SHA256': 'forged'})
""",
            "approval module namespace route",
        ),
        (
            """
from approved_schema_digest import __setattr__ as mutate
mutate('require_approved_ddl_execution', lambda: 'forged')
""",
            "approval module mutation route",
        ),
        (
            """
from approved_schema_digest import __delattr__ as mutate
mutate('require_approved_ddl_execution')
""",
            "approval module mutation route",
        ),
        (
            """
from approved_schema_digest import __getattribute__ as recover
recover('__dict__').update({'APPROVED_EXECUTION_DDL_SHA256': 'forged'})
""",
            "approval module namespace route",
        ),
        (
            """
import approved_schema_digest as gate
gate.__getattribute__('__dict__').update(
    {'APPROVED_EXECUTION_DDL_SHA256': 'forged'}
)
""",
            "approval module namespace route",
        ),
        (
            """
import sys
setattr(
    vars(sys)['modules'].setdefault('approved_schema_digest'),
    'APPROVED_EXECUTION_DDL_SHA256',
    'forged',
)
""",
            "module registry mutation route",
        ),
        (
            """
import sys
sys.modules['builtins'].setattr(
    sys.modules['approved_schema_digest'],
    'APPROVED_EXECUTION_DDL_SHA256',
    'forged',
)
""",
            "approval token mutation route",
        ),
        (
            """
from builtins import delattr
import approved_schema_digest as gate
delattr(gate, 'APPROVED_EXECUTION_DDL_SHA256')
""",
            "approval token mutation route",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0093-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations

    ordinary = """
import sys
class Box:
    pass
def mutate(box):
    setattr(box, 'APPROVED_EXECUTION_DDL_SHA256', 'ordinary')
    delattr(box, 'APPROVED_EXECUTION_DDL_SHA256')
    return box
unrelated_sys_member = vars(sys)['approved_schema_digest']
"""
    assert _schema_installer_gate_violations(ordinary, "rev0093-good.py") == []
