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
    installer_names: set[str] = set()
    schema_module_names: set[str] = set()
    sqlite_module_names: set[str] = set()
    sqlite_connect_names: set[str] = set()
    dynamic_import_module_names: set[str] = set()
    dynamic_import_names: set[str] = {"__import__"}
    builtins_module_names: set[str] = {"__builtins__"}
    operator_module_names: set[str] = set()
    attrgetter_names: set[str] = set()
    sqlite_connection_import_lines: list[int] = []
    sqlite_module_alias_lines: list[int] = []
    sqlite_nested_module_import_lines: list[int] = []
    dynamic_import_lines: list[int] = []
    dynamic_builtin_lines: list[int] = []
    wildcard_import_lines: list[int] = []
    approval_module_import_lines: list[int] = []
    approval_member_import_lines: list[int] = []
    sys_module_names: set[str] = set()
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
                        installer_names.add(imported.asname or "install_schema")
            if node.module == "app.execution_core.persistence":
                for imported in node.names:
                    if imported.name == "schema":
                        schema_module_names.add(imported.asname or "schema")
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
            if node.module == "importlib":
                for imported in node.names:
                    if imported.name == "import_module":
                        dynamic_import_names.add(imported.asname or "import_module")
                        dynamic_import_lines.append(node.lineno)
            if node.module == "operator":
                for imported in node.names:
                    if imported.name == "attrgetter":
                        attrgetter_names.add(imported.asname or "attrgetter")
            if node.module == "builtins":
                for imported in node.names:
                    if imported.name == "__import__":
                        dynamic_import_names.add(imported.asname or "__import__")
                    if imported.name in {
                        "__import__",
                        "getattr",
                        "vars",
                        "eval",
                        "exec",
                    }:
                        dynamic_builtin_lines.append(node.lineno)
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
                    else:
                        schema_module_names.add(imported.asname)
                if imported.name == "sqlite3":
                    if imported.asname is not None:
                        sqlite_module_alias_lines.append(node.lineno)
                    sqlite_module_names.add(imported.asname or "sqlite3")
                if imported.name == "importlib":
                    dynamic_import_module_names.add(imported.asname or "importlib")
                    dynamic_import_lines.append(node.lineno)
                if imported.name == "operator":
                    operator_module_names.add(imported.asname or "operator")
                if imported.name == "builtins":
                    builtins_module_names.add(imported.asname or "builtins")
                    dynamic_builtin_lines.append(node.lineno)
                if imported.name == "sys":
                    sys_module_names.add(imported.asname or "sys")
                if imported.name == "approved_schema_digest":
                    approval_module_import_lines.append(node.lineno)
                if imported.name.startswith("sqlite3."):
                    sqlite_nested_module_import_lines.append(node.lineno)

    # The missing-gate grammar must also recognize direct local import aliases.
    # It does not infer arbitrary object methods from their attribute spelling.
    for candidate in ast.walk(tree):
        if isinstance(candidate, ast.Import):
            for imported in candidate.names:
                if imported.name == "sys":
                    sys_module_names.add(imported.asname or "sys")
                if imported.name == "importlib":
                    dynamic_import_module_names.add(imported.asname or "importlib")
                if imported.name == "builtins":
                    builtins_module_names.add(imported.asname or "builtins")
        elif isinstance(candidate, ast.ImportFrom):
            if candidate.module == "importlib":
                dynamic_import_names.update(
                    imported.asname or "import_module"
                    for imported in candidate.names
                    if imported.name == "import_module"
                )
            if candidate.module == "builtins":
                dynamic_import_names.update(
                    imported.asname or "__import__"
                    for imported in candidate.names
                    if imported.name == "__import__"
                )

    def _static_string(value: ast.expr) -> str | None:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            left = _static_string(value.left)
            right = _static_string(value.right)
            if left is not None and right is not None:
                return left + right
        return None

    def _literal_dynamic_import_target(call: ast.Call) -> str | None:
        is_dynamic_import = bool(
            (isinstance(call.func, ast.Name) and call.func.id in dynamic_import_names)
            or (
                isinstance(call.func, ast.Attribute)
                and call.func.attr in {"__import__", "import_module"}
                and isinstance(call.func.value, ast.Name)
                and (
                    (
                        call.func.attr == "import_module"
                        and call.func.value.id in dynamic_import_module_names
                    )
                    or (
                        call.func.attr == "__import__"
                        and call.func.value.id in builtins_module_names
                    )
                )
            )
        )
        if not is_dynamic_import or not call.args:
            return None
        return _static_string(call.args[0])

    dynamic_sqlite_or_schema_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (target := _literal_dynamic_import_target(node)) is not None
        and (
            target == "sqlite3"
            or target.startswith("sqlite3.")
            or target == "app.execution_core.persistence.schema"
        )
    ]
    canonical_gate_import = (
        canonical_gate_imports[0] if len(canonical_gate_imports) == 1 else None
    )
    canonical_gate_is_exact = bool(
        canonical_gate_import is not None
        and not _name_is_rebound(
            tree,
            "require_approved_ddl_execution",
            permitted_import=canonical_gate_import,
        )
    )
    has_sqlite_surface = bool(
        sqlite_module_names
        or sqlite_connect_names
        or sqlite_nested_module_import_lines
        or dynamic_sqlite_or_schema_lines
    )
    # A canonical approval import marks a potential gate-bearing fixture.
    # Missing-gate namespace recovery is checked separately at the exact
    # ``connect``/``Connection`` expression, rather than broadening the
    # provenance checks to any source that happens to mention ``sqlite3``.
    has_gate_surface = bool(
        has_sqlite_surface or installer_names or canonical_gate_imports
    )
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
    if has_gate_surface:
        violations.extend(
            f"{label}:{line}: literal dynamic SQLite/schema import"
            for line in dynamic_sqlite_or_schema_lines
        )
        violations.extend(
            f"{label}:{line}: dynamic import route" for line in dynamic_import_lines
        )
        violations.extend(
            f"{label}:{line}: dynamic builtin import" for line in dynamic_builtin_lines
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
                if has_gate_surface and imported.name in {"importlib", "builtins"}:
                    violations.append(
                        f"{label}:{node.lineno}: dynamic import route is not module-bound"
                    )
                if has_gate_surface and imported.name == "sys":
                    violations.append(
                        f"{label}:{node.lineno}: approval module registry route is not module-bound"
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
            if has_gate_surface and node.module in {"importlib", "builtins"}:
                violations.append(
                    f"{label}:{node.lineno}: dynamic import route is not module-bound"
                )
            if has_gate_surface and node.module == "sys":
                violations.append(
                    f"{label}:{node.lineno}: approval module registry route is not module-bound"
                )

    parents = _parent_map(tree)

    def _expression_path(value: ast.expr) -> str | None:
        if isinstance(value, ast.Name):
            return value.id
        if isinstance(value, ast.Attribute):
            parent = _expression_path(value.value)
            return None if parent is None else f"{parent}.{value.attr}"
        return None

    def _call_tail(value: ast.expr) -> str | None:
        if isinstance(value, ast.Name):
            return value.id
        if isinstance(value, ast.Attribute):
            return value.attr
        return None

    def _is_schema_module_expression(value: ast.expr) -> bool:
        return bool(
            _expression_path(value) == "app.execution_core.persistence.schema"
            or (isinstance(value, ast.Name) and value.id in schema_module_names)
        )

    def _is_sqlite_module_expression(value: ast.expr) -> bool:
        return bool(isinstance(value, ast.Name) and value.id in sqlite_module_names)

    def _is_sqlite_owned_expression(value: ast.expr) -> bool:
        current = value
        while isinstance(current, ast.Attribute):
            current = current.value
        return _is_sqlite_module_expression(current)

    def _is_getattr_call(call: ast.Call) -> bool:
        return _call_tail(call.func) == "getattr"

    def _is_vars_call(call: ast.Call) -> bool:
        return _call_tail(call.func) == "vars"

    def _is_attrgetter_call(call: ast.Call) -> bool:
        if isinstance(call.func, ast.Name):
            return call.func.id in attrgetter_names
        return bool(
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "attrgetter"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id in operator_module_names
        )

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
            and isinstance(value.func, ast.Name)
            and value.func.id == "require_approved_ddl_execution"
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

    def _has_dynamic_import(owner: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        return any(
            _nearest_enclosing_function(candidate, parents) is owner
            and isinstance(candidate, ast.Call)
            and _is_dynamic_import_call(candidate)
            for candidate in ast.walk(owner)
        )

    def _is_dynamic_import_call(call: ast.Call) -> bool:
        if isinstance(call.func, ast.Name):
            return call.func.id in dynamic_import_names
        return bool(
            isinstance(call.func, ast.Attribute)
            and call.func.attr in {"__import__", "import_module"}
            and isinstance(call.func.value, ast.Name)
            and (
                (
                    call.func.attr == "import_module"
                    and call.func.value.id in dynamic_import_module_names
                )
                or (
                    call.func.attr == "__import__"
                    and call.func.value.id in builtins_module_names
                )
            )
        )

    assignments: dict[tuple[ast.AST, str], list[tuple[int, ast.expr]]] = {}
    for assignment in ast.walk(tree):
        if isinstance(assignment, ast.Assign):
            targets = assignment.targets
            value = assignment.value
        elif isinstance(assignment, ast.AnnAssign) and assignment.value is not None:
            targets = (assignment.target,)
            value = assignment.value
        else:
            continue
        scope = _lexical_scope(assignment, parents)
        for target in targets:
            if isinstance(target, ast.Name):
                assignments.setdefault((scope, target.id), []).append(
                    (assignment.lineno, value)
                )

    def _resolve_alias(
        value: ast.expr,
        seen: frozenset[int] = frozenset(),
    ) -> ast.expr:
        """Follow one unambiguous simple assignment in lexical scope only."""

        if not isinstance(value, ast.Name) or id(value) in seen:
            return value
        scope = _lexical_scope(value, parents)
        scopes = (scope,) if scope is tree else (scope, tree)
        for candidate_scope in scopes:
            bindings = assignments.get((candidate_scope, value.id), [])
            if not bindings:
                continue
            prior = [candidate for line, candidate in bindings if line < value.lineno]
            if len(bindings) == len(prior) == 1:
                return _resolve_alias(prior[0], seen | {id(value)})
            return value
        return value

    def _resolved_static_string(
        value: ast.expr,
        seen: frozenset[int] = frozenset(),
    ) -> str | None:
        value = _resolve_alias(value, seen)
        if id(value) in seen:
            return None
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            left = _resolved_static_string(value.left, seen | {id(value)})
            right = _resolved_static_string(value.right, seen | {id(value)})
            return left + right if left is not None and right is not None else None
        return None

    def _mapping_lookup(
        value: ast.expr,
        seen: frozenset[int] = frozenset(),
    ) -> tuple[ast.expr, str] | None:
        if isinstance(value, ast.Subscript):
            key = _resolved_static_string(value.slice)
            return (value.value, key) if key is not None else None
        if isinstance(value, ast.Call) and value.args:
            lookup = _resolve_alias(value.func, seen)
            if not (
                isinstance(lookup, ast.Attribute)
                and lookup.attr in {"get", "__getitem__"}
            ):
                return None
            key = _resolved_static_string(value.args[0])
            return (lookup.value, key) if key is not None else None
        return None

    def _is_dynamic_namespace_mapping(
        value: ast.expr,
        seen: frozenset[int] = frozenset(),
    ) -> bool:
        value = _resolve_alias(value, seen)
        if id(value) in seen:
            return False
        next_seen = seen | {id(value)}
        if isinstance(value, ast.Call) and not value.args and not value.keywords:
            namespace_callable = _resolve_alias(value.func, next_seen)
            if isinstance(namespace_callable, ast.Name) and namespace_callable.id in {
                "globals",
                "vars",
            }:
                return True
        if isinstance(value, ast.Attribute) and value.attr == "modules":
            receiver = _resolve_alias(value.value, next_seen)
            if isinstance(receiver, ast.Name) and receiver.id in sys_module_names:
                return True
        if isinstance(value, ast.Name) and value.id == "__builtins__":
            return True
        lookup = _mapping_lookup(value)
        return bool(
            lookup is not None
            and lookup[1] == "__builtins__"
            and _is_dynamic_namespace_mapping(lookup[0], next_seen)
        )

    def _is_dynamic_import_callable(
        value: ast.expr,
        seen: frozenset[int] = frozenset(),
    ) -> bool:
        value = _resolve_alias(value, seen)
        if id(value) in seen:
            return False
        next_seen = seen | {id(value)}
        if isinstance(value, ast.Name):
            return value.id in dynamic_import_names
        if isinstance(value, ast.Attribute):
            receiver = _resolve_alias(value.value, next_seen)
            is_importlib = bool(
                isinstance(receiver, ast.Name)
                and receiver.id in dynamic_import_module_names
            )
            is_builtins = bool(
                isinstance(receiver, ast.Name) and receiver.id in builtins_module_names
            )
            return bool(
                (value.attr == "import_module" and is_importlib)
                or (
                    value.attr == "__import__"
                    and (
                        is_builtins
                        or _is_dynamic_namespace_mapping(receiver, next_seen)
                    )
                )
            )
        lookup = _mapping_lookup(value)
        if (
            lookup is not None
            and lookup[1] == "__import__"
            and _is_dynamic_namespace_mapping(lookup[0], next_seen)
        ):
            return True
        if (
            isinstance(value, ast.Call)
            and _is_getattr_call(value)
            and len(value.args) >= 2
        ):
            receiver = _resolve_alias(value.args[0], next_seen)
            member = _resolved_static_string(value.args[1], next_seen)
            is_importlib = bool(
                isinstance(receiver, ast.Name)
                and receiver.id in dynamic_import_module_names
            )
            is_builtins = bool(
                isinstance(receiver, ast.Name) and receiver.id in builtins_module_names
            )
            return bool(
                (member == "import_module" and is_importlib)
                or (
                    member == "__import__"
                    and (
                        is_builtins
                        or _is_dynamic_namespace_mapping(receiver, next_seen)
                    )
                )
            )
        return False

    def _is_dynamic_import_factory_call(
        value: ast.expr,
        seen: frozenset[int] = frozenset(),
    ) -> bool:
        value = _resolve_alias(value, seen)
        return bool(
            isinstance(value, ast.Call)
            and value.args
            and (target := _resolved_static_string(value.args[0], seen)) is not None
            and (target == "sqlite3" or target.startswith("sqlite3."))
            and _is_dynamic_import_callable(value.func, seen | {id(value)})
        )

    def _is_dynamic_namespace_module_expression(
        value: ast.expr,
        seen: frozenset[int] = frozenset(),
    ) -> bool:
        value = _resolve_alias(value, seen)
        if id(value) in seen:
            return False
        next_seen = seen | {id(value)}
        lookup = _mapping_lookup(value)
        if (
            lookup is not None
            and lookup[1] == "sqlite3"
            and _is_dynamic_namespace_mapping(lookup[0], next_seen)
        ):
            return True
        if isinstance(value, ast.Attribute):
            return _is_dynamic_namespace_module_expression(value.value, next_seen)
        return False

    def _is_dynamic_sqlite_acquisition_call(call: ast.Call) -> bool:
        if not isinstance(call.func, ast.Attribute) or call.func.attr not in {
            "connect",
            "Connection",
        }:
            return False
        return _is_dynamic_sqlite_connection_receiver(call.func.value)

    def _is_dynamic_sqlite_connection_receiver(value: ast.expr) -> bool:
        receiver = _resolve_alias(value)
        return bool(
            _is_dynamic_import_factory_call(receiver)
            or _is_dynamic_namespace_module_expression(receiver)
        )

    def _is_installer_call(call: ast.Call) -> bool:
        if isinstance(call.func, ast.Name):
            return call.func.id in installer_names
        return (
            isinstance(call.func, ast.Attribute)
            and call.func.attr == "install_schema"
            and _is_schema_module_expression(call.func.value)
        ) or (isinstance(call.func, ast.Call) and _dynamic_installer_getter(call.func))

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in {"connect", "Connection"}
            and _is_dynamic_sqlite_connection_receiver(node.value)
        ):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                violations.append(
                    f"{label}:{node.lineno}: SQLite connection reference escapes direct call"
                )
        if isinstance(node, ast.Call) and _is_dynamic_sqlite_acquisition_call(node):
            violations.append(
                f"{label}:{node.lineno}: SQLite connection route is not direct"
            )
            continue
        if not has_gate_surface:
            continue
        if isinstance(node, ast.Name) and node.id == "__builtins__":
            violations.append(f"{label}:{node.lineno}: dynamic builtin namespace route")
        if isinstance(node, ast.Call) and _is_dynamic_import_call(node):
            violations.append(f"{label}:{node.lineno}: dynamic import route")
        if isinstance(node, ast.Call) and _call_tail(node.func) in {"eval", "exec"}:
            violations.append(f"{label}:{node.lineno}: dynamic code route")
        if (
            canonical_gate_imports
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "globals"
        ):
            violations.append(
                f"{label}:{node.lineno}: approval accessor namespace route"
            )
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, ast.Name) and value.id in {"getattr", "vars"}:
                violations.append(f"{label}:{node.lineno}: dynamic namespace alias")
            if isinstance(value, ast.Name) and value.id in {
                *schema_module_names,
                *sqlite_module_names,
            }:
                violations.append(f"{label}:{node.lineno}: module alias")
        if isinstance(node, ast.Attribute):
            if (
                canonical_gate_imports
                and node.attr == "__globals__"
                and isinstance(node.value, ast.Name)
                and node.value.id == "require_approved_ddl_execution"
            ):
                violations.append(
                    f"{label}:{node.lineno}: approval accessor namespace route"
                )
            if (
                canonical_gate_imports
                and node.attr == "modules"
                and isinstance(node.value, ast.Name)
                and node.value.id in sys_module_names
            ):
                violations.append(
                    f"{label}:{node.lineno}: approval module registry route"
                )
            if node.attr == "__dict__" and (
                _is_schema_module_expression(node.value)
                or _is_sqlite_owned_expression(node.value)
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

    if any(
        isinstance(node, ast.Call) and _is_sqlite_acquisition_call(node)
        for node in ast.walk(tree)
    ):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_dynamic_import_call(node):
                violations.append(
                    f"{label}:{node.lineno}: dynamic import in SQLite-bearing source"
                )

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in installer_names:
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                violations.append(
                    f"{label}:{node.lineno}: installer reference escapes direct call"
                )
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "install_schema"
            and _is_schema_module_expression(node.value)
        ):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                violations.append(
                    f"{label}:{node.lineno}: installer attribute escapes direct call"
                )
        elif isinstance(node, ast.Call) and _dynamic_installer_getter(node):
            violations.append(f"{label}:{node.lineno}: dynamic installer lookup")
        if not isinstance(node, ast.Call) or not _is_installer_call(node):
            continue
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
            if _has_dynamic_import(owner):
                violations.append(
                    f"{label}:{node.lineno}: dynamic installer import route"
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
            "dynamic builtin import",
        ),
        (
            """
from builtins import __import__ as module_loader
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return module_loader('sqlite3').connect(path)
""",
            "dynamic builtin import",
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
            "dynamic import route",
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
            "dynamic import route is not module-bound",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    return __import__('sqlite' + '3').connect(path)
""",
            "dynamic import route",
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
