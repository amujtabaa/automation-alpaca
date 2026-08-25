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


def _approval_accessor_binding_is_exact(tree: ast.Module) -> bool:
    """Prove the gate module has one closed executable shape.

    Pinning only the accessor body is insufficient because its builtins and token
    are resolved from module/global state when the function runs.  The human
    unlock therefore permits exactly one byte-level semantic change: replacing
    the token's ``None`` literal with one lowercase SHA-256 string literal.
    """

    body = list(tree.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    if len(body) != 4:
        return False
    future_import, typing_import, token_binding, accessor = body
    if not (
        isinstance(future_import, ast.ImportFrom)
        and future_import.module == "__future__"
        and future_import.level == 0
        and len(future_import.names) == 1
        and future_import.names[0].name == "annotations"
        and future_import.names[0].asname is None
        and isinstance(typing_import, ast.ImportFrom)
        and typing_import.module == "typing"
        and typing_import.level == 0
        and len(typing_import.names) == 1
        and typing_import.names[0].name == "Final"
        and typing_import.names[0].asname is None
        and isinstance(token_binding, ast.AnnAssign)
        and token_binding.simple == 1
        and isinstance(token_binding.target, ast.Name)
        and token_binding.target.id == "APPROVED_EXECUTION_DDL_SHA256"
        and isinstance(accessor, ast.FunctionDef)
        and accessor.name == "require_approved_ddl_execution"
        and not accessor.decorator_list
        and _exact_arguments(accessor.args, positional=(), vararg=None)
    ):
        return False
    expected_annotation = ast.parse(
        "APPROVED_EXECUTION_DDL_SHA256: Final[str | None] = None"
    ).body[0]
    assert isinstance(expected_annotation, ast.AnnAssign)
    if ast.dump(token_binding.annotation, include_attributes=False) != ast.dump(
        expected_annotation.annotation, include_attributes=False
    ):
        return False
    token = token_binding.value
    if not (
        isinstance(token, ast.Constant)
        and (
            token.value is None
            or (
                isinstance(token.value, str)
                and len(token.value) == 64
                and all(character in "0123456789abcdef" for character in token.value)
            )
        )
    ):
        return False
    expected = ast.parse(
        """
def require_approved_ddl_execution() -> str:
    approved = APPROVED_EXECUTION_DDL_SHA256
    if approved is None:
        raise RuntimeError(
            "HUMAN-GATE pending: changed DDL remains static-only until Ameen "
            "approves the exact candidate identity and fresh-file test plan"
        )
    if (
        type(approved) is not str
        or len(approved) != 64
        or any(character not in "0123456789abcdef" for character in approved)
    ):
        raise RuntimeError("HUMAN-GATE invalid: approval token must be SHA-256 text")
    return approved
"""
    ).body[0]
    assert isinstance(expected, ast.FunctionDef)
    if accessor.returns is None or expected.returns is None:
        return False
    return bool(
        ast.dump(accessor.returns, include_attributes=False)
        == ast.dump(expected.returns, include_attributes=False)
        and [
            ast.dump(statement, include_attributes=False)
            for statement in _body_without_docstring(accessor)
        ]
        == [
            ast.dump(statement, include_attributes=False)
            for statement in _body_without_docstring(expected)
        ]
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
    label_parts = label.replace("\\", "/").split("/")
    label_stem = label_parts[-1].removesuffix(".py")
    label_module_parts = (
        label_parts[:-1]
        if label_stem == "__init__"
        else [*label_parts[:-1], label_stem]
    )
    label_package = ".".join(
        label_module_parts if label_stem == "__init__" else label_module_parts[:-1]
    )

    def _absolute_import_from(node: ast.ImportFrom) -> str | None:
        if node.level == 0:
            return node.module
        package_parts = label_package.split(".") if label_package else []
        parent_count = node.level - 1
        if parent_count > len(package_parts):
            return None
        prefix = package_parts[: len(package_parts) - parent_count]
        suffix = node.module.split(".") if node.module else []
        return ".".join((*prefix, *suffix)) or None

    def _is_approval_module_name(module: str | None) -> bool:
        return bool(
            module == "approved_schema_digest"
            or (module is not None and module.endswith(".approved_schema_digest"))
        )

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
            module = _absolute_import_from(node)
            if any(imported.name == "*" for imported in node.names):
                wildcard_import_lines.append(node.lineno)
                if module == "app.execution_core.persistence.schema" or (
                    module is not None and _is_approval_module_name(module)
                ):
                    violations.append(
                        f"{label}:{node.lineno}: governed module wildcard import"
                    )
            if module == "app.execution_core.persistence.schema":
                for imported in node.names:
                    if imported.name == "install_schema":
                        if imported.asname is not None:
                            violations.append(
                                f"{label}:{node.lineno}: installer import alias"
                            )
            if module == "sqlite3" or (
                module is not None and module.startswith("sqlite3.")
            ):
                for imported in node.names:
                    violations.append(
                        f"{label}:{node.lineno}: SQLite import must be module-bound"
                    )
                    if imported.name == "connect":
                        sqlite_connection_import_lines.append(node.lineno)
                        sqlite_connect_names.add(imported.asname or "connect")
            if module == "approved_schema_digest" and node.level == 0:
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
            elif _is_approval_module_name(module):
                approval_member_import_lines.append(node.lineno)
            elif module == "app.execution_core.persistence" and any(
                imported.name == "schema" for imported in node.names
            ):
                # ``from . import schema`` is a real schema-module import and
                # must retain that identity in the lexical table below.
                pass
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
                if _is_approval_module_name(imported.name):
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
            module = _absolute_import_from(node)
            approval_import_is_noncanonical = bool(
                _is_approval_module_name(module)
                and not (
                    module == "approved_schema_digest"
                    and node.level == 0
                    and len(node.names) == 1
                    and node.names[0].name == "require_approved_ddl_execution"
                    and node.names[0].asname is None
                )
            )
            if (
                module == "sqlite3"
                or (module is not None and module.startswith("sqlite3."))
                or module == "app.execution_core.persistence.schema"
                or approval_import_is_noncanonical
                or (
                    module == "app.execution_core.persistence"
                    and any(imported.name == "schema" for imported in node.names)
                )
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
        (
            "tests.execution_core.approved_schema_digest",
            "require_approved_ddl_execution",
        ): "approval-accessor",
        ("approved_schema_digest", "__dict__"): "module-map:approval",
        ("approved_schema_digest", "__delattr__"): "approval-bound-mutator",
        ("approved_schema_digest", "__getattribute__"): "approval-namespace-route",
        ("approved_schema_digest", "__setattr__"): "approval-bound-mutator",
        ("builtins", "__import__"): "importer",
        ("builtins", "__dict__"): "module-map:builtins",
        ("builtins", "dict"): "builtin-dict",
        ("builtins", "eval"): "dynamic-code",
        ("builtins", "exec"): "dynamic-code",
        ("builtins", "getattr"): "getter",
        ("builtins", "globals"): "global-namespace-factory",
        ("builtins", "delattr"): "attribute-mutator",
        ("builtins", "object"): "object-type",
        ("builtins", "setattr"): "attribute-mutator",
        ("builtins", "vars"): "namespace-factory",
        ("importlib", "import_module"): "importer",
        ("operator", "attrgetter"): "attrgetter",
        ("operator", "delitem"): "mapping-mutator-function",
        ("operator", "getitem"): "mapping-getter-function",
        ("operator", "ior"): "mapping-mutator-function",
        ("operator", "setitem"): "mapping-mutator-function",
        ("sys", "__dict__"): "module-map:sys",
        ("sys", "modules"): "module-registry",
    }
    _BUILTIN_CAPABILITY_KINDS = {
        "__builtins__": "module-map:builtins",
        "__import__": "importer",
        "dict": "builtin-dict",
        "eval": "dynamic-code",
        "exec": "dynamic-code",
        "getattr": "getter",
        "globals": "global-namespace-factory",
        "object": "object-type",
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

    Binding = tuple[str, ast.AST | None, tuple[int, int], bool, bool]
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
        value: ast.AST | None,
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
                target = imported.name if imported.asname is not None else name
                kind = _CAPABILITY_MODULE_KINDS.get(target, "ordinary")
                if imported.asname is not None and _is_approval_module_name(target):
                    kind = "module:approval"
                _record_capability_binding(scope, name, kind, None, candidate)
        elif isinstance(candidate, ast.ImportFrom):
            module = _absolute_import_from(candidate)
            for imported in candidate.names:
                name = imported.asname or imported.name
                kind = _DIRECT_CAPABILITY_IMPORT_KINDS.get(
                    (module or "", imported.name)
                )
                if kind is None and module is not None:
                    imported_module = module + "." + imported.name
                    kind = _CAPABILITY_MODULE_KINDS.get(imported_module)
                    if _is_approval_module_name(imported_module):
                        kind = "module:approval"
                _record_capability_binding(
                    scope,
                    name,
                    kind or "ordinary",
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
                (
                    "function"
                    if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef))
                    else "ordinary"
                ),
                (
                    candidate
                    if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef))
                    else None
                ),
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

    def _effective_binding_alternatives(
        scope: ast.AST,
        name: str,
        position: tuple[int, int],
    ) -> tuple[Binding, ...]:
        candidates = capability_bindings.get((scope, name), [])
        if not candidates:
            return ()
        available = [
            candidate
            for candidate in candidates
            if candidate[3] or candidate[2] <= position
        ]
        if not available:
            if isinstance(scope, (ast.ClassDef, ast.Module)):
                return ()
            return (("ordinary", None, position, False, False),)

        # An unconditional assignment replaces every earlier state. A later
        # conditional assignment contributes an alternative because either
        # branch can reach the use. Keeping the alternatives intact is
        # essential for static module targets: collapsing them to a generic
        # unknown can erase the protected target that the gate must own.
        definite = [candidate for candidate in available if not candidate[4]]
        if not definite:
            return tuple(available)
        latest_position = max(candidate[2] for candidate in definite)
        return (
            *(candidate for candidate in definite if candidate[2] == latest_position),
            *(
                candidate
                for candidate in available
                if candidate[4] and candidate[2] > latest_position
            ),
        )

    def _deferred_observed_bindings(
        origin_scope: ast.AST,
        target_scope: ast.AST,
        name: str,
    ) -> tuple[Binding, ...]:
        """Return target-scope states observable when a function can execute."""

        boundary = origin_scope
        current = origin_scope
        while current is not target_scope:
            parent = parents.get(current)
            if parent is None:
                return ()
            if parent is not target_scope and isinstance(
                parent,
                (*_FUNCTION_SCOPE_TYPES, ast.ClassDef),
            ):
                boundary = parent
            current = parent
        if not isinstance(boundary, (ast.FunctionDef, ast.AsyncFunctionDef)):
            final = _effective_binding_alternatives(
                target_scope,
                name,
                (10**9, 10**9),
            )
            return final

        call_positions: set[tuple[int, int]] = set()
        boundary_scope = _capability_scope(boundary)
        if boundary_scope is target_scope:
            for candidate in ast.walk(target_scope):
                if not (
                    isinstance(candidate, ast.Call)
                    and isinstance(candidate.func, ast.Name)
                    and candidate.func.id == boundary.name
                    and _capability_scope(candidate) is target_scope
                ):
                    continue
                selected = _effective_binding_alternatives(
                    target_scope,
                    boundary.name,
                    _source_position(candidate.func),
                )
                if any(
                    binding[0] == "function" and binding[1] is boundary
                    for binding in selected
                ):
                    call_positions.add(_source_position(candidate))

        final_boundary = _effective_binding_alternatives(
            target_scope,
            boundary.name,
            (10**9, 10**9),
        )
        if target_scope is tree and any(
            binding[0] == "function" and binding[1] is boundary
            for binding in final_boundary
        ):
            call_positions.add((10**9, 10**9))

        escaped = False
        if boundary_scope is target_scope:
            for candidate in ast.walk(target_scope):
                if not (
                    isinstance(candidate, ast.Name)
                    and isinstance(candidate.ctx, ast.Load)
                    and candidate.id == boundary.name
                    and _capability_scope(candidate) is target_scope
                ):
                    continue
                parent = parents.get(candidate)
                if isinstance(parent, ast.Call) and parent.func is candidate:
                    continue
                selected = _effective_binding_alternatives(
                    target_scope,
                    boundary.name,
                    _source_position(candidate),
                )
                if any(
                    binding[0] == "function" and binding[1] is boundary
                    for binding in selected
                ):
                    escaped = True
                    break

        if escaped:
            activation = _post_source_position(boundary)
            initial = _effective_binding_alternatives(
                target_scope,
                name,
                activation,
            )
            future = tuple(
                binding
                for binding in capability_bindings.get((target_scope, name), [])
                if binding[2] > activation
            )
            return (*initial, *future)
        if call_positions:
            return tuple(
                binding
                for position in sorted(call_positions)
                for binding in _effective_binding_alternatives(
                    target_scope,
                    name,
                    position,
                )
            )
        return _effective_binding_alternatives(
            target_scope,
            name,
            (10**9, 10**9),
        )

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
            if target_scope is not current:
                current = target_scope
            observed = (
                _deferred_observed_bindings(origin_scope, current, name)
                if current is not origin_scope
                and isinstance(origin_scope, _FUNCTION_SCOPE_TYPES)
                else _effective_binding_alternatives(
                    current,
                    name,
                    position,
                )
            )
            if observed:
                marker = (current, name)
                if marker in seen:
                    return "unknown-dynamic"
                resolved_kinds: set[str] = set()
                for kind, value, _, _, _ in observed:
                    if kind == "alias":
                        resolved = (
                            "unknown-dynamic"
                            if not isinstance(value, ast.expr)
                            else _resolve_capability_expression(
                                value,
                                seen | {marker},
                            )
                        )
                    elif kind == "function":
                        resolved = "ordinary"
                    else:
                        resolved = kind
                    if resolved == "namespace-factory" and current is not origin_scope:
                        resolved = _escaped_namespace_factory_kind(current)
                    resolved_kinds.add(resolved or "unknown-dynamic")
                if len(resolved_kinds) == 1:
                    return next(iter(resolved_kinds))
                if any(kind != "ordinary" for kind in resolved_kinds):
                    return "governed-unknown:deferred-binding"
                return "ordinary"
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

    def _resolve_static_string_state(
        value: ast.expr,
        seen: frozenset[tuple[ast.AST, str]] = frozenset(),
    ) -> tuple[frozenset[str], bool]:
        """Return reachable literal texts and whether every state is known."""

        direct = _static_string(value)
        if direct is not None or not isinstance(value, ast.Name):
            return (
                frozenset() if direct is None else frozenset({direct}),
                direct is not None,
            )
        scope: ast.AST | None = _capability_scope(value)
        origin_scope = scope
        name = value.id
        while scope is not None:
            target_scope = _binding_scope(scope, name)
            if target_scope is not scope:
                scope = target_scope
            observed = (
                _deferred_observed_bindings(origin_scope, scope, name)
                if scope is not origin_scope
                and isinstance(origin_scope, _FUNCTION_SCOPE_TYPES)
                else _effective_binding_alternatives(
                    scope,
                    name,
                    _source_position(value),
                )
            )
            if observed:
                marker = (scope, name)
                if marker in seen:
                    return frozenset(), False
                texts: set[str] = set()
                complete = True
                for kind, payload, _, _, _ in observed:
                    if kind != "alias" or not isinstance(payload, ast.expr):
                        complete = False
                        continue
                    nested_texts, nested_complete = _resolve_static_string_state(
                        payload,
                        seen | {marker},
                    )
                    texts.update(nested_texts)
                    complete = complete and nested_complete
                return frozenset(texts), complete
            scope = _lexical_parent_scope(scope)
        return frozenset(), False

    def _resolve_static_strings(
        value: ast.expr,
        seen: frozenset[tuple[ast.AST, str]] = frozenset(),
    ) -> frozenset[str]:
        return _resolve_static_string_state(value, seen)[0]

    def _resolve_static_string(
        value: ast.expr,
        seen: frozenset[tuple[ast.AST, str]] = frozenset(),
    ) -> str | None:
        alternatives, complete = _resolve_static_string_state(value, seen)
        return next(iter(alternatives)) if complete and len(alternatives) == 1 else None

    def _module_kind_for_target(target: str) -> str | None:
        if target == "sqlite3" or target.startswith("sqlite3."):
            return "module:sqlite3"
        if target == "app.execution_core.persistence.schema":
            return "module:schema"
        if _is_approval_module_name(target):
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

    def _resolved_import_target_state(
        call: ast.Call,
    ) -> tuple[frozenset[str], bool]:
        target_value = _call_argument(call, "name", 0)
        targets, targets_complete = (
            (frozenset(), False)
            if target_value is None
            else _resolve_static_string_state(target_value)
        )
        package_value = _call_argument(call, "package", 1)
        packages, packages_complete = (
            (frozenset(), False)
            if package_value is None
            else _resolve_static_string_state(package_value)
        )
        resolved_targets = frozenset(
            resolved
            for target in targets
            for resolved in (
                (
                    target
                    if not target.startswith(".")
                    else _resolve_relative_target(target, package)
                )
                for package in (packages if target.startswith(".") else {""})
            )
            if resolved is not None
        )
        relative_targets = frozenset(
            target for target in targets if target.startswith(".")
        )
        complete = bool(
            targets_complete
            and (not relative_targets or (packages_complete and bool(packages)))
            and all(
                _resolve_relative_target(target, package) is not None
                for target in relative_targets
                for package in packages
            )
        )
        return resolved_targets, complete

    def _resolved_import_targets(call: ast.Call) -> frozenset[str]:
        return _resolved_import_target_state(call)[0]

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

    _SENSITIVE_MAPPING_KINDS = frozenset({"module-map:sys", "module-registry"})
    _MUTATION_OWNED_MAPPING_KINDS = frozenset(
        {*_SENSITIVE_MAPPING_KINDS, "module-map:builtins"}
    )
    _MAPPING_MUTATOR_NAMES = frozenset(
        {
            "__delitem__",
            "__init__",
            "__ior__",
            "__setitem__",
            "clear",
            "pop",
            "popitem",
            "setdefault",
            "update",
        }
    )
    _MODULE_MAP_MEMBER_KINDS = {
        "module-map:builtins": {
            "__import__": "importer",
            "dict": "builtin-dict",
            "eval": "dynamic-code",
            "exec": "dynamic-code",
            "getattr": "getter",
            "globals": "global-namespace-factory",
            "object": "object-type",
            "delattr": "attribute-mutator",
            "setattr": "attribute-mutator",
            "vars": "namespace-factory",
        },
        "module-map:builtin-dict": {
            "get": "mapping-getter-function",
            "__getitem__": "mapping-getter-function",
            **{member: "mapping-mutator-function" for member in _MAPPING_MUTATOR_NAMES},
        },
        "module-map:importlib": {"import_module": "importer"},
        "module-map:operator": {
            "attrgetter": "attrgetter",
            "delitem": "mapping-mutator-function",
            "getitem": "mapping-getter-function",
            "ior": "mapping-mutator-function",
            "setitem": "mapping-mutator-function",
        },
        "module-map:sys": {},
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
    _ORDINARY_GOVERNED_MODULE_MEMBERS = {
        "module:builtins": frozenset(
            {
                "AssertionError",
                "TypeError",
                "ValueError",
                "bool",
                "bytes",
                "int",
                "isinstance",
                "len",
                "print",
                "str",
                "type",
            }
        ),
        "module:importlib": frozenset(),
        "module:operator": frozenset(),
        "module:sys": frozenset(
            {
                "addaudithook",
                "executable",
                "gettrace",
                "path",
                "settrace",
                "stdout",
                "stdlib_module_names",
            }
        ),
    }
    _NAMESPACE_FALLBACK_KINDS = {
        "__builtins__": "module-map:builtins",
        "__import__": "importer",
        "builtins": "module:builtins",
        "dict": "builtin-dict",
        "eval": "dynamic-code",
        "exec": "dynamic-code",
        "getattr": "getter",
        "globals": "global-namespace-factory",
        "object": "object-type",
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
        if isinstance(base, str) and base.startswith("governed-unknown:"):
            return base
        if base == "unknown-dynamic":
            return "unknown-dynamic"
        if not _is_mapping_kind(base):
            return None
        if key is None:
            return (
                f"governed-unknown:{base}"
                if base in _GOVERNED_MAPPING_KINDS
                else "unknown-dynamic"
            )
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
        if base == "module-map:sys" and key == "modules":
            return "sys-namespace-registry"
        result = _MODULE_MAP_MEMBER_KINDS.get(base, {}).get(key)
        if result is not None:
            return result
        return (
            f"governed-unknown:{base}"
            if base in _GOVERNED_MAPPING_KINDS
            else "unknown-dynamic"
        )

    def _capability_attribute_kind(base: str | None, member: str) -> str | None:
        if isinstance(base, str) and base.startswith("governed-unknown:"):
            return base
        if base == "unknown-dynamic":
            if member in {"connect", "Connection"}:
                return "connection-reference"
            if member == "install_schema":
                return "dynamic-installer"
            return "unknown-dynamic"
        if base in _SENSITIVE_MAPPING_KINDS and member in _MAPPING_MUTATOR_NAMES:
            return f"mapping-mutator:{base}"
        if base == "builtin-dict":
            if member in _MAPPING_MUTATOR_NAMES:
                return "mapping-mutator-function"
            if member in {"get", "__getitem__"}:
                return "mapping-getter-function"
        if base == "object-type":
            if member in {"__delattr__", "__setattr__"}:
                return "object-attribute-mutator"
            if member == "__getattribute__":
                return "object-attribute-getter"
        if base == "approval-accessor":
            if member in {"__delattr__", "__setattr__"}:
                return "approval-accessor-mutator"
            if member in {"__dict__", "__getattribute__", "__globals__"}:
                return "approval-accessor-namespace-route"
        if _is_mapping_kind(base) and member in {"get", "__getitem__"}:
            return f"map-getter:{base}"
        result = {
            ("module:schema", "install_schema"): "installer",
            ("module:schema", "__dict__"): "module-map:schema",
            ("module:schema", "__delattr__"): "schema-bound-mutator",
            ("module:schema", "__getattribute__"): "schema-attribute-getter",
            ("module:schema", "__setattr__"): "schema-bound-mutator",
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
            ("module:builtins", "__delattr__"): "builtin-bound-mutator",
            ("module:builtins", "__getattribute__"): "builtin-namespace-route",
            ("module:builtins", "__setattr__"): "builtin-bound-mutator",
            ("module:builtins", "delattr"): "attribute-mutator",
            ("module:builtins", "dict"): "builtin-dict",
            ("module:builtins", "eval"): "dynamic-code",
            ("module:builtins", "exec"): "dynamic-code",
            ("module:builtins", "getattr"): "getter",
            ("module:builtins", "globals"): "global-namespace-factory",
            ("module:builtins", "object"): "object-type",
            ("module:builtins", "setattr"): "attribute-mutator",
            ("module:builtins", "vars"): "namespace-factory",
            ("module:importlib", "__dict__"): "module-map:importlib",
            ("module:importlib", "import_module"): "importer",
            ("module:operator", "attrgetter"): "attrgetter",
            ("module:operator", "delitem"): "mapping-mutator-function",
            ("module:operator", "getitem"): "mapping-getter-function",
            ("module:operator", "ior"): "mapping-mutator-function",
            ("module:operator", "setitem"): "mapping-mutator-function",
            ("module:sys", "__dict__"): "module-map:sys",
            ("module:sys", "__delattr__"): "sys-bound-mutator",
            ("module:sys", "__getattribute__"): "sys-namespace-route",
            ("module:sys", "__setattr__"): "sys-bound-mutator",
            ("module:sys", "modules"): "module-registry",
        }.get((base, member))
        if result is not None:
            return result
        if member in _ORDINARY_GOVERNED_MODULE_MEMBERS.get(base or "", frozenset()):
            return "ordinary"
        if base in _GOVERNED_MODULE_KINDS:
            return f"governed-unknown:{base}"
        return None

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
        member = _resolve_static_string(member_value, seen)
        if member is None:
            return (
                f"governed-unknown:{base}" if base in _GOVERNED_MODULE_KINDS else None
            )
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
                if module_kind == "builtin-dict":
                    return "module-map:builtin-dict"
                if isinstance(module_kind, str) and module_kind.startswith(
                    "governed-unknown:"
                ):
                    return module_kind
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
            targets, targets_complete = _resolved_import_target_state(value)
            if not targets:
                return "unknown-dynamic"
            target_kinds = {
                _module_kind_for_target(target) or "ordinary" for target in targets
            }
            if not targets_complete:
                return (
                    "governed-unknown:import-target"
                    if any(kind != "ordinary" for kind in target_kinds)
                    else "unknown-dynamic"
                )
            if len(target_kinds) == 1:
                return next(iter(target_kinds))
            if any(kind != "ordinary" for kind in target_kinds):
                return "governed-unknown:import-target"
            return "ordinary"
        if isinstance(function_kind, str) and function_kind.startswith("map-getter:"):
            key_value = _call_argument(value, "key", 0)
            return _map_lookup_kind(
                function_kind.removeprefix("map-getter:"),
                None if key_value is None else _resolve_static_string(key_value, seen),
                value,
            )
        if function_kind == "mapping-getter-function" and len(value.args) >= 2:
            return _map_lookup_kind(
                _resolve_capability_expression(value.args[0], seen),
                _resolve_static_string(value.args[1], seen),
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
        if isinstance(function_kind, str) and function_kind.startswith(
            "governed-unknown:"
        ):
            return function_kind
        if not isinstance(value.func, ast.Attribute):
            return None
        return None

    def _direct_dynamic_import_targets(call: ast.Call) -> frozenset[str]:
        if _resolve_capability_expression(call.func) != "importer":
            return frozenset()
        return _resolved_import_targets(call)

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

    def _schema_mutation_message(member: str | None) -> str:
        return (
            "schema installer mutation route"
            if member in {None, "install_schema"}
            else "schema module mutation route"
        )

    def _sys_mutation_message(member: str | None) -> str:
        return (
            "module registry mutation route"
            if member in {None, "modules"}
            else "sys module namespace mutation route"
        )

    def _governed_module_mutation_message(
        subject_kind: str | None,
        member: str | None,
    ) -> str | None:
        if isinstance(subject_kind, str) and subject_kind.startswith(
            "governed-unknown:"
        ):
            return "governed unknown mutation route"
        if subject_kind == "module:approval":
            return _approval_mutation_message(member)
        if subject_kind == "module:schema":
            return _schema_mutation_message(member)
        if subject_kind == "module:sys":
            return _sys_mutation_message(member)
        if subject_kind == "module:builtins":
            return (
                "importer mutation route"
                if member in {None, "__import__"}
                else "builtin module mutation route"
            )
        if subject_kind == "module:importlib":
            return "importer module mutation route"
        if subject_kind == "module:operator":
            return "operator module mutation route"
        return None

    def _governed_module_reflection_message(
        subject_kind: str | None,
        member: str | None,
    ) -> str | None:
        if isinstance(subject_kind, str) and subject_kind.startswith(
            "governed-unknown:"
        ):
            return "governed unknown reflection route"
        if subject_kind == "module:approval":
            return "approval module namespace route"
        if subject_kind == "module:schema":
            return "schema module reflection route"
        if subject_kind == "module:sys" and member in {None, "modules", "__dict__"}:
            return "sys module reflection route"
        if subject_kind == "module:builtins":
            return "importer namespace route"
        if subject_kind == "module:importlib":
            return "importer module reflection route"
        if subject_kind == "module:operator":
            return "operator module reflection route"
        return None

    def _sensitive_mapping_mutation_message(kind: str) -> str:
        if kind == "module-registry":
            return "module registry mutation route"
        if kind == "module-map:builtins":
            return "builtin module mutation route"
        return "sys module namespace mutation route"

    def _sensitive_mapping_mutation_call(call: ast.Call) -> str | None:
        if _resolve_capability_expression(call.func) != "mapping-mutator-function":
            return None
        subject = _call_argument(call, "object", 0)
        if subject is None:
            return None
        kind = _resolve_capability_expression(subject)
        return kind if kind in _MUTATION_OWNED_MAPPING_KINDS else None

    def _sensitive_mapping_dynamic_lookup_message(kind: str) -> str:
        return (
            "module registry dynamic lookup route"
            if kind == "module-registry"
            else "sys module namespace dynamic lookup route"
        )

    def _has_static_mapping_lookup_key(call: ast.Call, index: int) -> bool:
        key = _call_argument(call, "key", index)
        return key is not None and _resolve_static_string(key) is not None

    def _is_dynamic_sensitive_mapping_lookup(node: ast.expr) -> bool:
        parent = parents.get(node)
        if (
            isinstance(parent, ast.Subscript)
            and parent.value is node
            and isinstance(parent.ctx, ast.Load)
        ):
            return _resolve_static_string(parent.slice) is None
        if isinstance(parent, ast.Attribute) and parent.value is node:
            grandparent = parents.get(parent)
            return bool(
                parent.attr in {"get", "__getitem__"}
                and isinstance(grandparent, ast.Call)
                and grandparent.func is parent
                and not _has_static_mapping_lookup_key(grandparent, 0)
            )
        return bool(
            isinstance(parent, ast.Call)
            and parent.args
            and parent.args[0] is node
            and _resolve_capability_expression(parent.func) == "mapping-getter-function"
            and not _has_static_mapping_lookup_key(parent, 1)
        )

    def _is_supported_sensitive_mapping_use(node: ast.expr) -> bool:
        parent = parents.get(node)
        if (
            isinstance(parent, ast.Subscript)
            and parent.value is node
            and isinstance(parent.ctx, ast.Load)
        ):
            return _resolve_static_string(parent.slice) is not None
        if isinstance(parent, ast.Attribute) and parent.value is node:
            grandparent = parents.get(parent)
            return bool(
                parent.attr in {"get", "__getitem__"}
                and isinstance(grandparent, ast.Call)
                and grandparent.func is parent
                and _has_static_mapping_lookup_key(grandparent, 0)
            )
        if isinstance(parent, ast.Call) and parent.args and parent.args[0] is node:
            return bool(
                _resolve_capability_expression(parent.func) == "mapping-getter-function"
                and _has_static_mapping_lookup_key(parent, 1)
            )
        return False

    _GOVERNED_MODULE_KINDS = frozenset(
        {
            "module:approval",
            "module:builtins",
            "module:importlib",
            "module:operator",
            "module:schema",
            "module:sqlite3",
            "module:sys",
        }
    )
    _GOVERNED_MAPPING_KINDS = frozenset(
        {
            "module-map:approval",
            "module-map:builtins",
            "module-map:importlib",
            "module-map:operator",
            "module-map:schema",
            "module-map:sqlite3",
            "module-map:sys",
            "module-registry",
        }
    )

    def _is_governed_value_kind(kind: str | None) -> bool:
        return bool(
            kind in _GOVERNED_MODULE_KINDS
            or kind in _GOVERNED_MAPPING_KINDS
            or (isinstance(kind, str) and kind.startswith("governed-unknown:"))
        )

    def _is_supported_governed_module_use(node: ast.expr) -> bool:
        """Accept only an operation the finite grammar owns directly."""

        parent = parents.get(node)
        node_kind = _resolve_capability_expression(node)
        if isinstance(parent, ast.Compare) and all(
            isinstance(operator, (ast.Is, ast.IsNot)) for operator in parent.ops
        ):
            return True
        if node_kind in _GOVERNED_MAPPING_KINDS:
            if (
                isinstance(parent, ast.Subscript)
                and parent.value is node
                and isinstance(parent.ctx, ast.Load)
            ):
                return True
            if isinstance(parent, ast.Attribute) and parent.value is node:
                grandparent = parents.get(parent)
                return bool(
                    parent.attr in {"get", "__getitem__"}
                    and isinstance(grandparent, ast.Call)
                    and grandparent.func is parent
                )
            if isinstance(parent, ast.Call) and any(
                argument is node for argument in parent.args
            ):
                return _resolve_capability_expression(parent.func) in {
                    "mapping-getter-function",
                }
            return False
        if isinstance(parent, ast.Attribute) and parent.value is node:
            # ``module.__class__`` leaves the modeled member boundary and can
            # recover arbitrary descriptors such as ``__getattribute__``.
            return parent.attr != "__class__"
        if not (
            isinstance(parent, ast.Call)
            and any(argument is node for argument in parent.args)
        ):
            return False
        function_kind = _resolve_capability_expression(parent.func)
        if function_kind in {
            "attribute-mutator",
            "getter",
            "namespace-factory",
            "object-attribute-getter",
            "object-attribute-mutator",
        }:
            # The call-level rules below own the resulting reflection or
            # mutation.  Do not double-count its subject as an escape.
            return True
        if (
            label == "tests/execution_core/test_persistence_schema.py"
            and isinstance(parent.func, ast.Attribute)
            and parent.func.attr == "setattr"
            and isinstance(parent.func.value, ast.Name)
            and parent.func.value.id == "monkeypatch"
            and parent.args[0] is node
        ):
            member = _call_argument(parent, "name", 1)
            return bool(
                member is not None
                and _resolve_static_string(member) == "schema_ddl_digest"
            )
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            mapping_kind = _resolve_capability_expression(node.value)
            if mapping_kind in _SENSITIVE_MAPPING_KINDS:
                parent = parents.get(node)
                if isinstance(node.ctx, (ast.Store, ast.Del)) or (
                    isinstance(parent, ast.AugAssign) and parent.target is node
                ):
                    violations.append(
                        f"{label}:{node.lineno}: "
                        f"{_sensitive_mapping_mutation_message(mapping_kind)}"
                    )
                elif _resolve_static_string(node.slice) is None:
                    violations.append(
                        f"{label}:{node.lineno}: "
                        f"{_sensitive_mapping_dynamic_lookup_message(mapping_kind)}"
                    )
            elif mapping_kind == "module-map:builtins":
                member = _resolve_static_string(node.slice)
                parent = parents.get(node)
                if isinstance(node.ctx, (ast.Store, ast.Del)) or (
                    isinstance(parent, ast.AugAssign) and parent.target is node
                ):
                    message = (
                        "importer mutation route"
                        if member in {None, "__import__"}
                        else "builtin module mutation route"
                    )
                    violations.append(f"{label}:{node.lineno}: {message}")
                elif member is None and has_gate_surface:
                    violations.append(
                        f"{label}:{node.lineno}: importer namespace route"
                    )
        if (
            isinstance(node, ast.expr)
            and _is_governed_value_kind(_resolve_capability_expression(node))
            and not _is_supported_governed_module_use(node)
        ):
            violations.append(
                f"{label}:{node.lineno}: governed module escapes direct operation"
            )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "mapping-mutator-function"
        ):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                violations.append(
                    f"{label}:{node.lineno}: "
                    "mapping mutator capability escapes direct call"
                )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "module:approval"
            and not (
                isinstance(parents.get(node), ast.Attribute)
                and parents[node].value is node
            )
        ):
            violations.append(
                f"{label}:{node.lineno}: approval module escapes canonical import"
            )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "approval-accessor"
        ):
            if not (
                isinstance(node, ast.Name)
                and isinstance(parents.get(node), ast.Call)
                and parents[node].func is node
            ):
                violations.append(
                    f"{label}:{node.lineno}: approval accessor escapes canonical call"
                )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "importer"
        ):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                violations.append(
                    f"{label}:{node.lineno}: importer escapes direct call"
                )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "schema-attribute-getter"
        ):
            violations.append(f"{label}:{node.lineno}: schema module reflection route")
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "sys-namespace-route"
        ):
            violations.append(f"{label}:{node.lineno}: sys module reflection route")
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "builtin-namespace-route"
        ):
            violations.append(f"{label}:{node.lineno}: importer namespace route")
        if isinstance(node, ast.expr):
            sensitive_mapping_kind = _resolve_capability_expression(node)
            if (
                isinstance(sensitive_mapping_kind, str)
                and sensitive_mapping_kind in _SENSITIVE_MAPPING_KINDS
                and not _is_supported_sensitive_mapping_use(node)
            ):
                if _is_dynamic_sensitive_mapping_lookup(node):
                    parent = parents.get(node)
                    if not isinstance(parent, ast.Subscript):
                        violations.append(
                            f"{label}:{node.lineno}: "
                            f"{_sensitive_mapping_dynamic_lookup_message(sensitive_mapping_kind)}"
                        )
                else:
                    violations.append(
                        f"{label}:{node.lineno}: sensitive mapping escapes static boundary"
                    )
        if isinstance(node, ast.Call):
            for dynamic_import_target in _direct_dynamic_import_targets(node):
                module_kind = _module_kind_for_target(dynamic_import_target)
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
            message = (
                _governed_module_mutation_message(owner_kind, node.attr)
                if isinstance(node.ctx, (ast.Store, ast.Del))
                else None
            )
            if message is not None:
                violations.append(f"{label}:{node.lineno}: {message}")
            if owner_kind == "approval-accessor" and isinstance(
                node.ctx, (ast.Store, ast.Del)
            ):
                violations.append(
                    f"{label}:{node.lineno}: approval accessor mutation route"
                )
            if owner_kind == "approval-accessor" and node.attr in {
                "__dict__",
                "__getattribute__",
                "__globals__",
            }:
                violations.append(
                    f"{label}:{node.lineno}: approval accessor namespace route"
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
                message = (
                    None
                    if subject is None
                    else _governed_module_mutation_message(
                        _resolve_capability_expression(subject),
                        None if member is None else _resolve_static_string(member),
                    )
                )
                if message is not None:
                    violations.append(f"{label}:{node.lineno}: {message}")
                elif (
                    subject is not None
                    and _resolve_capability_expression(subject) == "approval-accessor"
                ):
                    violations.append(
                        f"{label}:{node.lineno}: approval accessor mutation route"
                    )
            elif mutation_kind == "approval-bound-mutator":
                member = _call_argument(node, "name", 0)
                violations.append(
                    f"{label}:{node.lineno}: "
                    f"{_approval_mutation_message(None if member is None else _resolve_static_string(member))}"
                )
            elif mutation_kind == "approval-accessor-mutator":
                violations.append(
                    f"{label}:{node.lineno}: approval accessor mutation route"
                )
            elif mutation_kind in {
                "schema-bound-mutator",
                "sys-bound-mutator",
                "builtin-bound-mutator",
            }:
                member = _call_argument(node, "name", 0)
                subject_kind = {
                    "schema-bound-mutator": "module:schema",
                    "sys-bound-mutator": "module:sys",
                    "builtin-bound-mutator": "module:builtins",
                }[mutation_kind]
                message = _governed_module_mutation_message(
                    subject_kind,
                    None if member is None else _resolve_static_string(member),
                )
                assert message is not None
                violations.append(f"{label}:{node.lineno}: {message}")
            elif mutation_kind == "object-attribute-mutator":
                subject = _call_argument(node, "object", 0)
                member = _call_argument(node, "name", 1)
                message = (
                    None
                    if subject is None
                    else _governed_module_mutation_message(
                        _resolve_capability_expression(subject),
                        None if member is None else _resolve_static_string(member),
                    )
                )
                if message is not None:
                    violations.append(f"{label}:{node.lineno}: {message}")
            elif mutation_kind == "object-attribute-getter":
                subject = _call_argument(node, "object", 0)
                member = _call_argument(node, "name", 1)
                message = (
                    None
                    if subject is None
                    else _governed_module_reflection_message(
                        _resolve_capability_expression(subject),
                        None if member is None else _resolve_static_string(member),
                    )
                )
                if message is not None:
                    violations.append(f"{label}:{node.lineno}: {message}")
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in _MAPPING_MUTATOR_NAMES
                and _resolve_capability_expression(node.func.value)
                == "module-map:builtins"
            ):
                violations.append(f"{label}:{node.lineno}: importer mutation route")
        if (
            isinstance(node, ast.Call)
            and (mapping_kind := _sensitive_mapping_mutation_call(node)) is not None
        ):
            violations.append(
                f"{label}:{node.lineno}: "
                f"{_sensitive_mapping_mutation_message(mapping_kind)}"
            )
        if (
            isinstance(node, ast.Call)
            and isinstance(
                (mutation_kind := _resolve_capability_expression(node.func)), str
            )
            and mutation_kind.startswith("mapping-mutator:")
        ):
            violations.append(
                f"{label}:{node.lineno}: "
                f"{_sensitive_mapping_mutation_message(mutation_kind.removeprefix('mapping-mutator:'))}"
            )
        if (
            isinstance(node, ast.Subscript)
            and _resolve_capability_expression(node.value) == "module-registry"
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ):
            violations.append(f"{label}:{node.lineno}: module registry mutation route")
        if (
            isinstance(node, ast.AugAssign)
            and (mapping_kind := _resolve_capability_expression(node.target))
            in _SENSITIVE_MAPPING_KINDS
        ):
            violations.append(
                f"{label}:{node.lineno}: "
                f"{_sensitive_mapping_mutation_message(mapping_kind)}"
            )
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
        if (
            isinstance(node, ast.expr)
            and isinstance((mutation_kind := _resolve_capability_expression(node)), str)
            and mutation_kind.startswith("mapping-mutator:")
        ):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                violations.append(
                    f"{label}:{node.lineno}: "
                    f"{_sensitive_mapping_mutation_message(mutation_kind.removeprefix('mapping-mutator:'))}"
                )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "approval-accessor-mutator"
        ):
            parent = parents.get(node)
            if not (isinstance(parent, ast.Call) and parent.func is node):
                violations.append(
                    f"{label}:{node.lineno}: approval accessor mutation route"
                )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node)
            == "approval-accessor-namespace-route"
        ):
            violations.append(
                f"{label}:{node.lineno}: approval accessor namespace route"
            )
        if (
            isinstance(node, ast.Call)
            and _resolve_capability_expression(node.func)
            in {"getter", "namespace-factory"}
            and node.args
            and _resolve_capability_expression(node.args[0]) == "approval-accessor"
        ):
            violations.append(
                f"{label}:{node.lineno}: approval accessor namespace route"
            )
        if (
            isinstance(node, ast.expr)
            and _resolve_capability_expression(node) == "sys-namespace-registry"
        ):
            violations.append(f"{label}:{node.lineno}: sys module namespace route")
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


def _repository_sensitive_reexport_violations(
    sources: dict[str, str],
) -> list[str]:
    """Reject governed capabilities recovered through repository-local helpers.

    This is intentionally a finite lexical proof, not a Python evaluator.  It
    follows module exports, function-local shadows, simple aliases, and only
    import/lookup primitives whose bindings are proven canonical.
    """

    trees = {
        label: ast.parse(source, filename=label) for label, source in sources.items()
    }
    parents_by_label = {label: _parent_map(tree) for label, tree in trees.items()}
    module_to_label: dict[str, str] = {}
    package_by_label: dict[str, str] = {}
    for label in trees:
        parts = label.replace("\\", "/").split("/")
        stem = parts[-1].removesuffix(".py")
        module_parts = parts[:-1] if stem == "__init__" else [*parts[:-1], stem]
        module_name = ".".join(module_parts)
        if module_name:
            module_to_label[module_name] = label
        package_by_label[label] = ".".join(
            module_parts if stem == "__init__" else module_parts[:-1]
        )
        if (
            parts[:2] == ["tests", "execution_core"]
            and len(parts) == 3
            and stem != "__init__"
        ):
            module_to_label[stem] = label

    direct_modules = {
        "app.execution_core.persistence.schema": "module:schema",
        "approved_schema_digest": "module:approval",
        "tests.execution_core.approved_schema_digest": "module:approval",
        "builtins": "module:builtins",
        "importlib": "module:importlib",
        "operator": "module:operator",
        "sys": "module:sys",
        "types": "module:types",
    }
    direct_members = {
        (
            "app.execution_core.persistence.schema",
            "install_schema",
        ): "installer",
        (
            "approved_schema_digest",
            "require_approved_ddl_execution",
        ): "approval-accessor",
        ("app.execution_core.persistence", "schema"): "module:schema",
        ("builtins", "__import__"): "importer",
        ("builtins", "dict"): "dict-type",
        ("builtins", "getattr"): "getter",
        ("builtins", "object"): "object-type",
        ("builtins", "type"): "type-factory",
        ("builtins", "vars"): "namespace-factory",
        ("importlib", "import_module"): "importer",
        ("operator", "attrgetter"): "attribute-getter-factory",
        ("operator", "getitem"): "mapping-getter",
        ("sys", "modules"): "module-registry",
        ("types", "ModuleType"): "module-type",
    }
    builtin_members = {
        "__import__": "importer",
        "dict": "dict-type",
        "getattr": "getter",
        "object": "object-type",
        "type": "type-factory",
        "vars": "namespace-factory",
    }
    protected = frozenset(
        {
            "installer",
            "approval-accessor",
            "module:schema",
            "module:approval",
        }
    )

    def _absolute_module(label: str, node: ast.ImportFrom) -> str | None:
        if node.level == 0:
            return node.module
        package_parts = (
            package_by_label[label].split(".") if package_by_label[label] else []
        )
        parent_count = node.level - 1
        if parent_count > len(package_parts):
            return None
        prefix = package_parts[: len(package_parts) - parent_count]
        suffix = node.module.split(".") if node.module else []
        return ".".join([*prefix, *suffix]) or None

    def _module_kind(module: str) -> str | None:
        direct = direct_modules.get(module)
        if direct is not None:
            return direct
        local_label = module_to_label.get(module)
        return None if local_label is None else "local:" + local_label

    known_modules = frozenset((*direct_modules, *module_to_label))

    def _module_prefix_kind(module: str) -> str | None:
        if _module_kind(module) is not None or any(
            known.startswith(module + ".") for known in known_modules
        ):
            return "module-prefix:" + module
        return None

    def _static_text(value: ast.expr | None) -> str | None:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        if isinstance(value, ast.BinOp) and isinstance(value.op, ast.Add):
            left = _static_text(value.left)
            right = _static_text(value.right)
            if left is not None and right is not None:
                return left + right
        return None

    def _call_argument(
        call: ast.Call,
        index: int,
        *names: str,
    ) -> ast.expr | None:
        values = [keyword.value for keyword in call.keywords if keyword.arg in names]
        if len(call.args) > index:
            values.insert(0, call.args[index])
        return values[0] if len(values) == 1 else None

    def _base_kind(kind: str) -> str:
        return kind.removeprefix("relayed:")

    def _describe(kind: str) -> str:
        return {
            "installer": "schema installer",
            "approval-accessor": "approval accessor",
            "module:schema": "schema module",
            "module:approval": "approval module",
        }[kind]

    _FUNCTION_SCOPE_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    _COMPREHENSION_SCOPE_TYPES = (
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )
    _SCOPE_TYPES = (
        *_FUNCTION_SCOPE_TYPES,
        *_COMPREHENSION_SCOPE_TYPES,
        ast.ClassDef,
    )
    function_outer_ids: dict[ast.AST, frozenset[int]] = {}
    class_outer_ids: dict[ast.ClassDef, frozenset[int]] = {}
    comprehension_outer_ids: dict[ast.AST, frozenset[int]] = {}
    for tree in trees.values():
        for candidate in ast.walk(tree):
            if isinstance(candidate, _FUNCTION_SCOPE_TYPES):
                arguments = candidate.args
                argument_nodes: tuple[ast.arg, ...] = (
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
                    *(item for item in arguments.kw_defaults if item is not None),
                    *argument_nodes,
                    *(
                        (candidate.returns,)
                        if getattr(candidate, "returns", None) is not None
                        else ()
                    ),
                )
                function_outer_ids[candidate] = frozenset(
                    id(descendant) for root in roots for descendant in ast.walk(root)
                )
            elif isinstance(candidate, ast.ClassDef):
                roots = (
                    *candidate.decorator_list,
                    *candidate.bases,
                    *(keyword.value for keyword in candidate.keywords),
                )
                class_outer_ids[candidate] = frozenset(
                    id(descendant) for root in roots for descendant in ast.walk(root)
                )
            elif isinstance(candidate, _COMPREHENSION_SCOPE_TYPES):
                comprehension_outer_ids[candidate] = frozenset(
                    id(descendant)
                    for descendant in ast.walk(candidate.generators[0].iter)
                )

    def _scope_for(label: str, node: ast.AST) -> ast.AST:
        original = node
        current = node
        parents = parents_by_label[label]
        while True:
            parent = parents.get(current)
            if parent is None:
                return trees[label]
            if isinstance(parent, _FUNCTION_SCOPE_TYPES):
                if id(original) in function_outer_ids[parent]:
                    current = parent
                    continue
                return parent
            if isinstance(parent, ast.ClassDef):
                if id(original) in class_outer_ids[parent]:
                    current = parent
                    continue
                return parent
            if isinstance(parent, _COMPREHENSION_SCOPE_TYPES):
                if id(original) in comprehension_outer_ids[parent]:
                    current = parent
                    continue
                return parent
            if isinstance(parent, ast.Module):
                return parent
            current = parent

    def _lexical_parent(label: str, scope: ast.AST) -> ast.AST | None:
        parents = parents_by_label[label]
        current = parents.get(scope)
        skip_class = isinstance(
            scope, (*_FUNCTION_SCOPE_TYPES, *_COMPREHENSION_SCOPE_TYPES)
        )
        while current is not None:
            if isinstance(current, ast.ClassDef) and skip_class:
                current = parents.get(current)
                continue
            if isinstance(current, (*_SCOPE_TYPES, ast.Module)):
                return current
            current = parents.get(current)
        return None

    Spec = tuple[str, object | None]
    Binding = tuple[Spec, tuple[int, int], bool]
    bindings: dict[tuple[str, ast.AST, str], list[Binding]] = {}

    def _position(node: ast.AST, *, after: bool = False) -> tuple[int, int]:
        if after:
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
        return (
            int(getattr(node, "lineno", -1)),
            int(getattr(node, "col_offset", -1)),
        )

    def _is_conditional_binding(label: str, node: ast.AST, scope: ast.AST) -> bool:
        current = node
        parents = parents_by_label[label]
        while current is not scope:
            parent = parents.get(current)
            if parent is None:
                return True
            if isinstance(
                parent,
                (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.Match),
            ):
                return True
            current = parent
        return False

    def _record(
        label: str,
        scope: ast.AST,
        name: str,
        spec: Spec,
        source: ast.AST,
        *,
        always_available: bool = False,
    ) -> None:
        target_scope = _binding_scope(label, scope, name)
        bindings.setdefault((label, target_scope, name), []).append(
            (
                spec,
                (-1, -1) if always_available else _position(source, after=True),
                False
                if always_available
                else _is_conditional_binding(label, source, scope),
            )
        )

    def _target_names(target: ast.expr) -> tuple[ast.Name, ...]:
        if isinstance(target, ast.Name):
            return (target,)
        if isinstance(target, ast.Starred):
            return _target_names(target.value)
        if isinstance(target, (ast.List, ast.Tuple)):
            return tuple(name for item in target.elts for name in _target_names(item))
        return ()

    declared_names: dict[tuple[str, ast.AST], set[str]] = {}
    global_names: dict[tuple[str, ast.AST], set[str]] = {}
    nonlocal_names: dict[tuple[str, ast.AST], set[str]] = {}
    for label, tree in trees.items():
        for node in ast.walk(tree):
            scope = _scope_for(label, node)
            declarations: tuple[str, ...] = ()
            if isinstance(node, ast.Assign):
                declarations = tuple(
                    name.id for target in node.targets for name in _target_names(target)
                )
            elif isinstance(node, ast.AnnAssign):
                declarations = tuple(name.id for name in _target_names(node.target))
            elif isinstance(node, ast.NamedExpr):
                declarations = tuple(name.id for name in _target_names(node.target))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                declarations = tuple(
                    imported.asname
                    or (
                        imported.name.split(".", 1)[0]
                        if isinstance(node, ast.Import)
                        else imported.name
                    )
                    for imported in node.names
                )
            elif isinstance(node, ast.arg):
                declarations = (node.arg,)
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                declarations = (node.name,)
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                declarations = (node.id,)
            if declarations:
                declared_names.setdefault((label, scope), set()).update(declarations)
            if isinstance(node, ast.Global):
                global_names.setdefault((label, scope), set()).update(node.names)
            elif isinstance(node, ast.Nonlocal):
                nonlocal_names.setdefault((label, scope), set()).update(node.names)

    def _nearest_nonlocal_owner(
        label: str,
        scope: ast.AST,
        name: str,
    ) -> ast.AST:
        current = _lexical_parent(label, scope)
        while current is not None and current is not trees[label]:
            if (
                name not in global_names.get((label, current), set())
                and name not in nonlocal_names.get((label, current), set())
                and name in declared_names.get((label, current), set())
            ):
                return current
            current = _lexical_parent(label, current)
        return trees[label]

    def _binding_scope(
        label: str,
        scope: ast.AST,
        name: str,
    ) -> ast.AST:
        if name in global_names.get((label, scope), set()):
            return trees[label]
        if name in nonlocal_names.get((label, scope), set()):
            return _nearest_nonlocal_owner(label, scope, name)
        return scope

    handled_stores: set[int] = set()
    for label, tree in trees.items():
        for node in ast.walk(tree):
            scope = _scope_for(label, node)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    for name in _target_names(target):
                        handled_stores.add(id(name))
                        _record(label, scope, name.id, ("expr", node.value), node)
            elif isinstance(node, ast.AnnAssign):
                for name in _target_names(node.target):
                    handled_stores.add(id(name))
                    _record(
                        label,
                        scope,
                        name.id,
                        ("ordinary", None)
                        if node.value is None
                        else ("expr", node.value),
                        node,
                    )
            elif isinstance(node, ast.NamedExpr):
                for name in _target_names(node.target):
                    handled_stores.add(id(name))
                    _record(label, scope, name.id, ("expr", node.value), node)
            elif isinstance(node, ast.Import):
                for imported in node.names:
                    bound = imported.asname or imported.name.split(".", 1)[0]
                    if imported.asname is not None:
                        kind = _module_kind(imported.name) or _module_prefix_kind(
                            imported.name
                        )
                    elif "." in imported.name:
                        kind = _module_prefix_kind(bound)
                    else:
                        kind = _module_kind(imported.name)
                    _record(
                        label,
                        scope,
                        bound,
                        ("kind", kind or "ordinary"),
                        node,
                    )
            elif isinstance(node, ast.ImportFrom):
                module = _absolute_module(label, node)
                for imported in node.names:
                    if imported.name == "*":
                        continue
                    bound = imported.asname or imported.name
                    direct = (
                        None
                        if module is None
                        else direct_members.get((module, imported.name))
                    )
                    local_label = (
                        None if module is None else module_to_label.get(module)
                    )
                    imported_module = (
                        None
                        if module is None
                        else _module_kind(module + "." + imported.name)
                    )
                    if direct is not None:
                        _record(label, scope, bound, ("kind", direct), node)
                        continue
                    recorded = False
                    if local_label is not None:
                        _record(
                            label,
                            scope,
                            bound,
                            ("local-member", (local_label, imported.name)),
                            node,
                        )
                        recorded = True
                    if imported_module is not None:
                        _record(
                            label,
                            scope,
                            bound,
                            ("kind", imported_module),
                            node,
                        )
                        recorded = True
                    if not recorded:
                        _record(label, scope, bound, ("ordinary", None), node)
            elif isinstance(node, ast.arg):
                owner = parents_by_label[label].get(node)
                while owner is not None and not isinstance(
                    owner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
                ):
                    owner = parents_by_label[label].get(owner)
                _record(
                    label,
                    trees[label] if owner is None else owner,
                    node.arg,
                    ("ordinary", None),
                    node,
                    always_available=True,
                )
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                _record(
                    label,
                    scope,
                    node.name,
                    (
                        ("function", node)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        else ("ordinary", None)
                    ),
                    node,
                )

    for label, tree in trees.items():
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, (ast.Store, ast.Del))
                and id(node) not in handled_stores
            ):
                scope = _scope_for(label, node)
                _record(
                    label,
                    scope,
                    node.id,
                    ("ordinary", None),
                    node,
                    always_available=isinstance(scope, _COMPREHENSION_SCOPE_TYPES),
                )

    exports: dict[str, dict[str, set[str]]] = {label: {} for label in trees}

    def _owner_has_protected(owner_label: str) -> bool:
        return any(
            value in protected
            for values in exports[owner_label].values()
            for value in values
        )

    def _member_kinds(owner: str, member: str) -> set[str]:
        relayed_owner = owner.startswith("relayed:")
        base = _base_kind(owner)
        if member == "__dict__" and base == "module-type":
            return {"module-type-map"}
        if member == "__dict__" and (
            base.startswith("module:") or base.startswith("local:")
        ):
            return {
                ("module-map:" if base.startswith("module:") else "local-map:")
                + base.split(":", 1)[1]
            }
        if member == "__class__" and (
            base.startswith("module:") or base.startswith("local:")
        ):
            return {"module-type"}
        if member == "__getattribute__" and (
            base.startswith("module:") or base.startswith("local:")
        ):
            return {"attribute-getter:" + base}
        if (
            member in {"__delattr__", "__setattr__"}
            and base.startswith("local:")
            and _owner_has_protected(base.removeprefix("local:"))
        ):
            return {"mutation-relayed:" + base.removeprefix("local:")}
        if base.startswith("local:"):
            owner_label = base.removeprefix("local:")
            values = exports[owner_label].get(member, set())
            return {
                ("relayed:" + value if value in protected else value)
                for value in values
            }
        if base.startswith("local-map:"):
            owner_label = base.removeprefix("local-map:")
            values = exports[owner_label].get(member, set())
            return {
                ("relayed:" + value if value in protected else value)
                for value in values
            }
        if base.startswith("module-prefix:"):
            candidate = base.removeprefix("module-prefix:") + "." + member
            kind = _module_kind(candidate) or _module_prefix_kind(candidate)
            return set() if kind is None else {kind}
        result = {
            ("module:schema", "install_schema"): "installer",
            (
                "module:approval",
                "require_approved_ddl_execution",
            ): "approval-accessor",
            ("module:builtins", "__import__"): "importer",
            ("module:builtins", "dict"): "dict-type",
            ("module:builtins", "getattr"): "getter",
            ("module:builtins", "object"): "object-type",
            ("module:builtins", "type"): "type-factory",
            ("module:builtins", "vars"): "namespace-factory",
            ("module:importlib", "import_module"): "importer",
            ("module:operator", "attrgetter"): "attribute-getter-factory",
            ("module:operator", "getitem"): "mapping-getter",
            ("module:sys", "modules"): "module-registry",
            ("module:types", "ModuleType"): "module-type",
            ("dict-type", "get"): "mapping-getter",
            ("dict-type", "__getitem__"): "mapping-getter",
            ("module-type", "__getattribute__"): "object-getter",
            ("module-type", "__setattr__"): "object-mutator",
            ("object-type", "__getattribute__"): "object-getter",
        }.get((base, member))
        if (
            result is None
            and (
                base.startswith("local-map:")
                or base.startswith("module-map:")
                or base == "module-registry"
            )
            and member in {"get", "__getitem__"}
        ):
            result = "map-getter:" + base
        if result is None:
            return set()
        return {
            "relayed:" + result if relayed_owner and result in protected else result
        }

    def _map_lookup(base: str, key: str | None) -> set[str]:
        if base.startswith("local-map:"):
            owner_label = base.removeprefix("local-map:")
            if key is None:
                return (
                    {"dynamic-relayed:" + owner_label}
                    if any(
                        value in protected
                        for values in exports[owner_label].values()
                        for value in values
                    )
                    else set()
                )
            return _member_kinds("local:" + owner_label, key)
        if base == "module-registry" and key is not None:
            kind = _module_kind(key)
            return set() if kind is None else {kind}
        if base == "module-type-map" and key == "__getattribute__":
            return {"object-getter"}
        if base == "module-type-map" and key == "__setattr__":
            return {"object-mutator"}
        if base == "module-type-map" and key is None:
            return {"dynamic-module-descriptor"}
        if base == "module-map:sys" and key == "modules":
            return {"module-registry"}
        if base == "module-map:builtins" and key is not None:
            kind = builtin_members.get(key)
            return set() if kind is None else {kind}
        if base == "module-map:importlib" and key == "import_module":
            return {"importer"}
        if base == "module-map:operator" and key == "getitem":
            return {"mapping-getter"}
        if base == "module-map:types" and key == "ModuleType":
            return {"module-type"}
        if base == "module-map:schema" and key == "install_schema":
            return {"installer"}
        if base == "module-map:approval" and key == "require_approved_ddl_execution":
            return {"approval-accessor"}
        return set()

    def _spec_kinds(
        label: str,
        spec: Spec,
        seen: frozenset[tuple[str, int, str]],
    ) -> set[str]:
        category, payload = spec
        if category == "ordinary":
            return set()
        if category == "kind":
            assert isinstance(payload, str)
            return {payload}
        if category == "local-member":
            assert isinstance(payload, tuple)
            owner_label, member = payload
            return _member_kinds("local:" + str(owner_label), str(member))
        if category == "function":
            return set()
        assert category == "expr" and isinstance(payload, ast.expr)
        return _expression_kinds(label, payload, seen)

    def _effective_bindings(
        label: str,
        scope: ast.AST,
        name: str,
        position: tuple[int, int],
    ) -> tuple[Binding, ...]:
        available = [
            binding
            for binding in bindings.get((label, scope, name), [])
            if binding[1] <= position
        ]
        if not available:
            return ()
        definite = [binding for binding in available if not binding[2]]
        if not definite:
            return tuple(available)
        latest_position = max(binding[1] for binding in definite)
        return (
            *(binding for binding in definite if binding[1] == latest_position),
            *(
                binding
                for binding in available
                if binding[2] and binding[1] > latest_position
            ),
        )

    def _deferred_parent_bindings(
        label: str,
        origin_scope: ast.AST,
        target_scope: ast.AST,
        name: str,
    ) -> tuple[Binding, ...]:
        """Return parent bindings observable when a deferred function can run."""

        boundary = origin_scope
        current = origin_scope
        parents = parents_by_label[label]
        while current is not target_scope:
            parent = parents.get(current)
            if parent is None:
                return ()
            if parent is not target_scope and isinstance(
                parent,
                (*_FUNCTION_SCOPE_TYPES, ast.ClassDef),
            ):
                boundary = parent
            current = parent
        activation = _position(boundary, after=True)
        if not isinstance(boundary, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return _effective_bindings(
                label,
                target_scope,
                name,
                (10**9, 10**9),
            )

        call_positions: set[tuple[int, int]] = set()
        boundary_scope = _scope_for(label, boundary)
        if boundary_scope is target_scope:
            for candidate in ast.walk(target_scope):
                if not (
                    isinstance(candidate, ast.Call)
                    and isinstance(candidate.func, ast.Name)
                    and candidate.func.id == boundary.name
                    and _scope_for(label, candidate) is target_scope
                ):
                    continue
                selected = _effective_bindings(
                    label,
                    target_scope,
                    boundary.name,
                    _position(candidate.func),
                )
                if any(
                    spec[0] == "function" and spec[1] is boundary
                    for spec, _, _ in selected
                ):
                    call_positions.add(_position(candidate))

        final_boundary = _effective_bindings(
            label,
            target_scope,
            boundary.name,
            (10**9, 10**9),
        )
        if target_scope is trees[label] and any(
            spec[0] == "function" and spec[1] is boundary
            for spec, _, _ in final_boundary
        ):
            call_positions.add((10**9, 10**9))

        escaped = False
        if boundary_scope is target_scope:
            for candidate in ast.walk(target_scope):
                if not (
                    isinstance(candidate, ast.Name)
                    and isinstance(candidate.ctx, ast.Load)
                    and candidate.id == boundary.name
                    and _scope_for(label, candidate) is target_scope
                ):
                    continue
                parent = parents.get(candidate)
                if isinstance(parent, ast.Call) and parent.func is candidate:
                    continue
                selected = _effective_bindings(
                    label,
                    target_scope,
                    boundary.name,
                    _position(candidate),
                )
                if any(
                    spec[0] == "function" and spec[1] is boundary
                    for spec, _, _ in selected
                ):
                    escaped = True
                    break

        if escaped:
            initial = _effective_bindings(
                label,
                target_scope,
                name,
                activation,
            )
            future = tuple(
                binding
                for binding in bindings.get((label, target_scope, name), [])
                if binding[1] > activation
            )
            return (*initial, *future)
        if call_positions:
            return tuple(
                binding
                for position in sorted(call_positions)
                for binding in _effective_bindings(
                    label,
                    target_scope,
                    name,
                    position,
                )
            )
        return _effective_bindings(
            label,
            target_scope,
            name,
            (10**9, 10**9),
        )

    def _name_kinds(
        label: str,
        scope: ast.AST,
        name: str,
        seen: frozenset[tuple[str, int, str]],
        position: tuple[int, int],
    ) -> set[str]:
        current: ast.AST | None = scope
        origin_scope = scope
        while current is not None:
            target_scope = _binding_scope(label, current, name)
            if target_scope is not current:
                current = target_scope
            selected = (
                _deferred_parent_bindings(
                    label,
                    origin_scope,
                    current,
                    name,
                )
                if current is not origin_scope
                and isinstance(origin_scope, _FUNCTION_SCOPE_TYPES)
                else _effective_bindings(
                    label,
                    current,
                    name,
                    position,
                )
            )
            if selected:
                marker = (label, id(current), name)
                if marker in seen:
                    return set()
                return {
                    kind
                    for spec, _, _ in selected
                    for kind in _spec_kinds(label, spec, seen | {marker})
                }
            current = _lexical_parent(label, current)
        builtin = builtin_members.get(name)
        return set() if builtin is None else {builtin}

    def _static_expression_text_state(
        label: str,
        value: ast.expr | None,
        seen: frozenset[tuple[str, int, str]] = frozenset(),
    ) -> tuple[frozenset[str], bool]:
        direct = _static_text(value)
        if direct is not None or not isinstance(value, ast.Name):
            return (
                frozenset() if direct is None else frozenset({direct}),
                direct is not None,
            )
        scope = _scope_for(label, value)
        current: ast.AST | None = scope
        while current is not None:
            target_scope = _binding_scope(label, current, value.id)
            if target_scope is not current:
                current = target_scope
            selected = (
                _deferred_parent_bindings(
                    label,
                    scope,
                    current,
                    value.id,
                )
                if current is not scope and isinstance(scope, _FUNCTION_SCOPE_TYPES)
                else _effective_bindings(
                    label,
                    current,
                    value.id,
                    _position(value),
                )
            )
            if selected:
                marker = (label, id(current), value.id)
                if marker in seen:
                    return frozenset(), False
                texts: set[str] = set()
                complete = True
                for (category, payload), _, _ in selected:
                    if category != "expr" or not isinstance(payload, ast.expr):
                        complete = False
                        continue
                    nested_texts, nested_complete = _static_expression_text_state(
                        label,
                        payload,
                        seen | {marker},
                    )
                    texts.update(nested_texts)
                    complete = complete and nested_complete
                return frozenset(texts), complete
            current = _lexical_parent(label, current)
        return frozenset(), False

    def _static_expression_texts(
        label: str,
        value: ast.expr | None,
        seen: frozenset[tuple[str, int, str]] = frozenset(),
    ) -> frozenset[str]:
        return _static_expression_text_state(label, value, seen)[0]

    def _static_expression_text(
        label: str,
        value: ast.expr | None,
        seen: frozenset[tuple[str, int, str]] = frozenset(),
    ) -> str | None:
        alternatives, complete = _static_expression_text_state(label, value, seen)
        return next(iter(alternatives)) if complete and len(alternatives) == 1 else None

    def _resolved_relative_module(target: str, package: str) -> str | None:
        depth = len(target) - len(target.lstrip("."))
        if depth == 0:
            return target
        package_parts = package.split(".")
        if depth > len(package_parts):
            return None
        prefix = package_parts[: len(package_parts) - depth + 1]
        suffix = target[depth:]
        return ".".join((*prefix, suffix)) if suffix else ".".join(prefix)

    def _module_from_importer(label: str, call: ast.Call) -> set[str]:
        targets = _static_expression_texts(
            label,
            _call_argument(call, 0, "name"),
        )
        packages = _static_expression_texts(
            label,
            _call_argument(call, 1, "package"),
        )
        resolved_targets = {
            resolved
            for target in targets
            for resolved in (
                (
                    target
                    if not target.startswith(".")
                    else _resolved_relative_module(target, package)
                )
                for package in (packages if target.startswith(".") else {""})
            )
            if resolved is not None
        }
        return {
            kind
            for target in resolved_targets
            if (kind := _module_kind(target)) is not None
        }

    def _expression_kinds(
        label: str,
        value: ast.expr,
        seen: frozenset[tuple[str, int, str]] = frozenset(),
    ) -> set[str]:
        if isinstance(value, ast.Name):
            return _name_kinds(
                label,
                _scope_for(label, value),
                value.id,
                seen,
                _position(value),
            )
        if isinstance(value, ast.NamedExpr):
            return _expression_kinds(label, value.value, seen)
        if isinstance(value, ast.Attribute):
            return {
                member_kind
                for owner in _expression_kinds(label, value.value, seen)
                for member_kind in _member_kinds(owner, value.attr)
            }
        if isinstance(value, ast.Subscript):
            return {
                result
                for owner in _expression_kinds(label, value.value, seen)
                for result in _map_lookup(
                    owner,
                    _static_expression_text(label, value.slice),
                )
            }
        if not isinstance(value, ast.Call):
            return set()
        function_kinds = _expression_kinds(label, value.func, seen)
        results: set[str] = set()
        for function_kind in function_kinds:
            if function_kind == "importer":
                results.update(_module_from_importer(label, value))
            elif function_kind == "namespace-factory":
                subject = _call_argument(value, 0, "object")
                if subject is None:
                    continue
                for owner in _expression_kinds(label, subject, seen):
                    base = _base_kind(owner)
                    if base.startswith("local:"):
                        results.add("local-map:" + base.removeprefix("local:"))
                    elif base.startswith("module:"):
                        results.add("module-map:" + base.removeprefix("module:"))
                    elif base == "module-type":
                        results.add("module-type-map")
            elif function_kind == "getter":
                subject = _call_argument(value, 0, "object")
                member = _call_argument(value, 1, "name")
                if subject is None:
                    continue
                owners = _expression_kinds(label, subject, seen)
                static_member = _static_expression_text(label, member)
                if static_member is None:
                    results.update(
                        "dynamic-relayed:" + _base_kind(owner).removeprefix("local:")
                        for owner in owners
                        if _base_kind(owner).startswith("local:")
                        and any(
                            kind in protected
                            for kinds in exports[
                                _base_kind(owner).removeprefix("local:")
                            ].values()
                            for kind in kinds
                        )
                    )
                    if "module-type" in {_base_kind(owner) for owner in owners}:
                        results.add("dynamic-module-descriptor")
                else:
                    results.update(
                        member_kind
                        for owner in owners
                        for member_kind in _member_kinds(owner, static_member)
                    )
            elif function_kind == "mapping-getter":
                subject = _call_argument(value, 0, "object")
                member = _call_argument(value, 1, "key")
                if subject is not None:
                    results.update(
                        result
                        for owner in _expression_kinds(label, subject, seen)
                        for result in _map_lookup(
                            owner,
                            _static_expression_text(label, member),
                        )
                    )
            elif function_kind == "attribute-getter-factory":
                if len(value.args) == 1 and not value.keywords:
                    member = _static_expression_text(label, value.args[0])
                    results.add(
                        "dynamic-attribute-selector"
                        if member is None
                        else "attribute-selector:" + member
                    )
            elif function_kind.startswith("attribute-selector:"):
                subject = _call_argument(value, 0, "object")
                if subject is not None:
                    results.update(
                        member_kind
                        for owner in _expression_kinds(label, subject, seen)
                        for member_kind in _member_kinds(
                            owner,
                            function_kind.removeprefix("attribute-selector:"),
                        )
                    )
            elif function_kind == "dynamic-attribute-selector":
                subject = _call_argument(value, 0, "object")
                if subject is not None:
                    owners = _expression_kinds(label, subject, seen)
                    results.update(
                        "dynamic-relayed:" + _base_kind(owner).removeprefix("local:")
                        for owner in owners
                        if _base_kind(owner).startswith("local:")
                        and any(
                            kind in protected
                            for kinds in exports[
                                _base_kind(owner).removeprefix("local:")
                            ].values()
                            for kind in kinds
                        )
                    )
                    if "module-type" in {_base_kind(owner) for owner in owners}:
                        results.add("dynamic-module-descriptor")
            elif function_kind == "type-factory":
                subject = _call_argument(value, 0, "object")
                if subject is not None and any(
                    _base_kind(owner).startswith(("local:", "module:"))
                    for owner in _expression_kinds(label, subject, seen)
                ):
                    results.add("module-type")
            elif function_kind.startswith("map-getter:"):
                member = _call_argument(value, 0, "key")
                results.update(
                    _map_lookup(
                        function_kind.removeprefix("map-getter:"),
                        _static_expression_text(label, member),
                    )
                )
            elif function_kind == "object-getter":
                subject = _call_argument(value, 0, "object")
                member = _call_argument(value, 1, "name")
                static_member = _static_expression_text(label, member)
                owners = (
                    set()
                    if subject is None
                    else _expression_kinds(label, subject, seen)
                )
                if static_member is None:
                    results.update(
                        "dynamic-relayed:" + _base_kind(owner).removeprefix("local:")
                        for owner in owners
                        if _base_kind(owner).startswith("local:")
                        and any(
                            kind in protected
                            for kinds in exports[
                                _base_kind(owner).removeprefix("local:")
                            ].values()
                            for kind in kinds
                        )
                    )
                    if "module-type" in {_base_kind(owner) for owner in owners}:
                        results.add("dynamic-module-descriptor")
                else:
                    results.update(
                        member_kind
                        for owner in owners
                        for member_kind in _member_kinds(owner, static_member)
                    )
            elif function_kind == "object-mutator":
                subject = _call_argument(value, 0, "object")
                if subject is not None:
                    results.update(
                        "mutation-relayed:" + _base_kind(owner).removeprefix("local:")
                        for owner in _expression_kinds(label, subject, seen)
                        if _base_kind(owner).startswith("local:")
                        and any(
                            kind in protected
                            for kinds in exports[
                                _base_kind(owner).removeprefix("local:")
                            ].values()
                            for kind in kinds
                        )
                    )
            elif function_kind == "dynamic-module-descriptor":
                subject = _call_argument(value, 0, "object")
                if subject is not None:
                    results.update(
                        "dynamic-relayed:" + _base_kind(owner).removeprefix("local:")
                        for owner in _expression_kinds(label, subject, seen)
                        if _base_kind(owner).startswith("local:")
                        and any(
                            kind in protected
                            for kinds in exports[
                                _base_kind(owner).removeprefix("local:")
                            ].values()
                            for kind in kinds
                        )
                    )
            elif function_kind.startswith("attribute-getter:"):
                member = _call_argument(value, 0, "name")
                static_member = _static_expression_text(label, member)
                owner = function_kind.removeprefix("attribute-getter:")
                if static_member is None:
                    if _base_kind(owner).startswith("local:") and any(
                        kind in protected
                        for kinds in exports[
                            _base_kind(owner).removeprefix("local:")
                        ].values()
                        for kind in kinds
                    ):
                        results.add(
                            "dynamic-relayed:"
                            + _base_kind(owner).removeprefix("local:")
                        )
                else:
                    results.update(
                        _member_kinds(
                            owner,
                            static_member,
                        )
                    )
        return results

    module_names = {
        (label, name) for label, scope, name in bindings if scope is trees[label]
    }
    for _ in range(max(1, len(module_names) + 1)):
        changed = False
        for label, name in module_names:
            kinds = {
                _base_kind(kind)
                for kind in _name_kinds(
                    label,
                    trees[label],
                    name,
                    frozenset(),
                    (10**9, 10**9),
                )
                if not kind.startswith("dynamic-relayed:")
            }
            if not kinds.issubset(exports[label].get(name, set())):
                exports[label].setdefault(name, set()).update(kinds)
                changed = True
        if not changed:
            break

    def _local_module_carries_protected(kind: str) -> bool:
        base = _base_kind(kind)
        if not base.startswith(("local:", "local-map:")):
            return False
        owner_label = base.split(":", 1)[1]
        return _owner_has_protected(owner_label)

    def _is_modeled_local_module_use(
        label: str,
        node: ast.expr,
        kind: str,
    ) -> bool:
        parent = parents_by_label[label].get(node)
        base = _base_kind(kind)
        if base.startswith("local-map:"):
            return False
        if isinstance(parent, ast.Attribute) and parent.value is node:
            return bool(_member_kinds(base, parent.attr))
        if not (
            isinstance(parent, ast.Call)
            and any(argument is node for argument in parent.args)
        ):
            return False
        function_kinds = _expression_kinds(label, parent.func)
        return bool(
            function_kinds
            & {
                "getter",
                "namespace-factory",
                "object-getter",
                "object-mutator",
                "type-factory",
            }
            or any(
                kind.startswith("attribute-selector:")
                or kind == "dynamic-attribute-selector"
                for kind in function_kinds
            )
        )

    violations: list[str] = []
    for label, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = _absolute_module(label, node)
                local_label = None if module is None else module_to_label.get(module)
                if local_label is not None:
                    for imported in node.names:
                        if imported.name == "*":
                            if any(
                                kind in protected
                                for kinds in exports[local_label].values()
                                for kind in kinds
                            ):
                                violations.append(
                                    "%s:%s: wildcard import may recover a "
                                    "re-exported governed capability"
                                    % (label, node.lineno)
                                )
                            continue
                        imported_kinds = exports[local_label].get(imported.name, set())
                        for kind in imported_kinds:
                            if kind in protected:
                                violations.append(
                                    "%s:%s: %s is re-exported through %s"
                                    % (
                                        label,
                                        node.lineno,
                                        _describe(kind),
                                        module,
                                    )
                                )
                        if _owner_has_protected(local_label) and not imported_kinds:
                            violations.append(
                                "%s:%s: unmodeled member is imported from a helper "
                                "carrying a governed capability" % (label, node.lineno)
                            )
            if not isinstance(node, ast.expr):
                continue
            for kind in _expression_kinds(label, node):
                if kind.startswith("relayed:"):
                    base = kind.removeprefix("relayed:")
                    if base in protected:
                        violations.append(
                            "%s:%s: %s is recovered through a re-exported module"
                            % (label, node.lineno, _describe(base))
                        )
                elif kind.startswith("dynamic-relayed:"):
                    violations.append(
                        "%s:%s: dynamic lookup may recover a re-exported "
                        "governed capability" % (label, node.lineno)
                    )
                elif kind.startswith("mutation-relayed:"):
                    violations.append(
                        "%s:%s: module-type mutation reaches a helper carrying "
                        "a governed capability" % (label, node.lineno)
                    )
                elif (
                    not (
                        isinstance(node, ast.Name)
                        and not isinstance(node.ctx, ast.Load)
                    )
                    and _local_module_carries_protected(kind)
                    and not _is_modeled_local_module_use(label, node, kind)
                ):
                    violations.append(
                        "%s:%s: helper module carrying a governed capability "
                        "escapes its modeled operation" % (label, node.lineno)
                    )
    return violations


def _execution_core_python_paths(repository_root: Path) -> tuple[Path, ...]:
    """Return every current or future execution-core Python source recursively."""

    return tuple(
        sorted(
            (
                *repository_root.joinpath("tests", "execution_core").rglob("*.py"),
                *repository_root.joinpath("app", "execution_core").rglob("*.py"),
            ),
            key=lambda candidate: candidate.as_posix(),
        )
    )


def test_changed_ddl_installers_have_one_fail_closed_human_gate() -> None:
    """REV-0078 P0-1: every installer has exactly one approval provenance.

    Candidate DDL identity is evidence; it is not authorization.  Before a human
    records an exact approval, the centrally held token is ``None`` and every
    SQLite-bearing fixture refuses before opening a connection.  This source audit
    remains valid after the separate one-line unlock commit, so the behavior of the
    locked state is proved independently below rather than hard-coding ``None`` here.
    """

    repository_root = Path(__file__).resolve().parents[2]
    sources = {
        path.relative_to(repository_root).as_posix(): path.read_text(encoding="utf-8")
        for path in _execution_core_python_paths(repository_root)
    }
    violations = [
        violation
        for label, source in sources.items()
        for violation in _schema_installer_gate_violations(
            source,
            label,
        )
    ]
    violations.extend(_repository_sensitive_reexport_violations(sources))
    assert violations == [], violations


def test_changed_ddl_gate_source_inventory_is_recursive(tmp_path: Path) -> None:
    """A future nested test module cannot silently leave the static proof."""

    nested_test = tmp_path / "tests" / "execution_core" / "nested" / "test_gate.py"
    nested_app = tmp_path / "app" / "execution_core" / "nested" / "module.py"
    for path in (nested_test, nested_app):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("VALUE = 1\n", encoding="utf-8")

    assert {
        path.relative_to(tmp_path).as_posix()
        for path in _execution_core_python_paths(tmp_path)
    } == {
        "app/execution_core/nested/module.py",
        "tests/execution_core/nested/test_gate.py",
    }


def test_changed_ddl_gate_audit_refuses_sensitive_helper_reexports() -> None:
    """A local helper cannot make the governed imports look ordinary elsewhere."""

    direct = {
        "tests/execution_core/consumer.py": """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
install_schema(connection, approved_ddl_sha256=require_approved_ddl_execution())
""",
    }
    assert _repository_sensitive_reexport_violations(direct) == []

    relayed = {
        "tests/execution_core/helper.py": """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
""",
        "tests/execution_core/consumer.py": """
from helper import install_schema, require_approved_ddl_execution
install_schema(connection, approved_ddl_sha256=require_approved_ddl_execution())
""",
        "tests/execution_core/module_helper.py": """
from app.execution_core.persistence import schema
""",
        "tests/execution_core/module_consumer.py": """
import module_helper
module_helper.schema.install_schema(connection, approved_ddl_sha256=object())
getattr(module_helper.schema, 'install_schema')
""",
        "tests/execution_core/wildcard_consumer.py": """
from helper import *
""",
        "tests/execution_core/namespace_consumer.py": """
import helper
helper.__dict__["install_schema"]
vars(helper)["require_approved_ddl_execution"]
helper.__getattribute__("install_schema")
object.__getattribute__(helper, "require_approved_ddl_execution")
member = "install_schema"
helper.__dict__[member]
getattr(helper, member)
def dynamic_member(member):
    return getattr(helper, member)
""",
        "tests/execution_core/dynamic_import_consumer.py": """
import importlib
import sys
importlib.import_module("helper").install_schema
sys.modules["helper"].require_approved_ddl_execution
""",
    }
    violations = _repository_sensitive_reexport_violations(relayed)
    assert any(
        "schema installer is re-exported through helper" in item for item in violations
    )
    assert any(
        "approval accessor is re-exported through helper" in item for item in violations
    )
    assert any(
        "schema installer is recovered through a re-exported module" in item
        for item in violations
    )
    assert any(
        "approval accessor is recovered through a re-exported module" in item
        for item in violations
    )
    assert any("wildcard import may recover" in item for item in violations)
    assert any("dynamic lookup may recover" in item for item in violations)


def test_rev0099_repository_topology_tracks_only_lexical_capabilities() -> None:
    """Helper recovery follows proven functions and respects local shadows."""

    helper = """
from app.execution_core.persistence.schema import install_schema
from approved_schema_digest import require_approved_ddl_execution
def recover():
    return install_schema
"""
    rejected_consumers = (
        """
from importlib import import_module
import_module('helper').install_schema
""",
        """
import helper
import operator
operator.getitem(vars(helper), 'install_schema')
""",
        """
import builtins
import helper
builtins.getattr(helper, 'require_approved_ddl_execution')
""",
        """
import relay
relay.forwarded.install_schema
""",
        """
from builtins import getattr as read_member
import helper
read_member(helper, 'install_schema')
""",
        """
from builtins import vars as namespace
from operator import getitem
import helper
getitem(namespace(helper), 'require_approved_ddl_execution')
""",
        """
from importlib import import_module
loader = import_module
loader('helper').install_schema
""",
        """
import tests.execution_core.helper
tests.execution_core.helper.install_schema
""",
        """
from tests.execution_core import helper
helper.require_approved_ddl_execution
""",
        """
import tests.execution_core.helper
import tests.execution_core as package
package.helper.require_approved_ddl_execution
""",
        """
from operator import attrgetter
import helper
attrgetter('install_schema')(helper)
""",
        """
from builtins import dict, vars
import helper
dict.get(vars(helper), 'require_approved_ddl_execution')
""",
        """
import helper
helper.__class__.__getattribute__(helper, 'install_schema')
""",
        """
import helper
type(helper).__getattribute__(helper, 'require_approved_ddl_execution')
""",
        """
import helper
box = [helper]
box[0].install_schema
""",
        """
from importlib import import_module
TARGET = 'helper'
import_module(TARGET).install_schema
""",
        """
from importlib import import_module
condition = False
TARGET = 'helper'
if condition:
    TARGET = 'ordinary'
import_module(TARGET).require_approved_ddl_execution
""",
        """
def mutate():
    global helper
    import helper
    return helper.install_schema
mutate()
""",
        """
def outer():
    helper = object()
    def mutate():
        nonlocal helper
        import helper
        return helper.install_schema
    return mutate()
outer()
""",
        """
import helper
def recover(member):
    return helper.__getattribute__(member)
recover('install_schema')
""",
        """
import helper
def recover():
    return helper.install_schema
recover()
helper = object()
""",
        """
from operator import attrgetter
import helper
def recover(member):
    return attrgetter(member)(helper)
recover('install_schema')
""",
        """
import helper
type(helper).__dict__['__getattribute__'](helper, 'install_schema')
""",
        """
import helper
helper.__setattr__('require_approved_ddl_execution', object())
""",
        """
import helper
helper.__dict__.update({'require_approved_ddl_execution': object()})
""",
        """
import helper
helper.__loader__.load_module(helper.__name__).install_schema
""",
        """
import ordinary as selected, helper as selected
selected.install_schema
""",
        """
import helper
helper.recover()
""",
        """
from helper import recover
recover()
""",
        """
import helper
member = unknown_name()
getattr(type(helper), member)(helper, 'install_schema')
""",
        """
import helper
member = unknown_name()
object.__getattribute__(type(helper), member)(helper, 'install_schema')
""",
        """
from operator import attrgetter
import helper
member = unknown_name()
attrgetter(member)(type(helper))(helper, 'install_schema')
""",
        """
import helper
member = unknown_name()
getattr(type(helper), member)(helper, 'install_schema', object())
""",
        """
import helper
vars(type(helper))['__getattribute__'](helper, 'install_schema')
""",
        """
import helper
import types
types.ModuleType.__getattribute__(helper, 'install_schema')
""",
        """
import helper
from types import ModuleType
ModuleType.__dict__['__getattribute__'](helper, 'install_schema')
""",
    )
    for ordinal, consumer in enumerate(rejected_consumers, 1):
        sources = {
            "tests/execution_core/helper.py": helper,
            "tests/execution_core/consumer.py": consumer,
        }
        if ordinal == 4:
            sources["tests/execution_core/relay.py"] = """
import helper
forwarded = helper
"""
        assert _repository_sensitive_reexport_violations(sources), ordinal

    accepted_consumers = (
        """
import helper
def inspect(helper):
    return getattr(helper, 'install_schema')
""",
        """
def getattr(value, member):
    return object()
getattr(object(), 'install_schema')
""",
        """
class Client:
    def import_module(self, name):
        return object()
client = Client()
client.import_module('helper').install_schema
""",
        """
import importlib
def inspect(module_name, member_name):
    return getattr(importlib.import_module(module_name), member_name)
""",
        """
def vars(value):
    return {}
vars(object())['install_schema']
""",
        """
import helper
ordinary = [getattr(helper, 'install_schema') for helper in values]
""",
        """
class Client:
    def attrgetter(self, member):
        return lambda value: object()
operator = Client()
operator.attrgetter('install_schema')(object())
""",
        """
class Mapping:
    def get(self, mapping, member):
        return object()
dict = Mapping()
dict.get({}, 'install_schema')
""",
        """
import helper
helper = object()
ordinary = helper.install_schema
""",
        """
import helper
helper = object()
def recover():
    return helper.install_schema
ordinary = recover()
""",
        """
import helper
class Consumer:
    helper = object()
    ordinary = helper.install_schema
""",
        """
import helper
def recover():
    return helper.install_schema
class Ordinary:
    install_schema = object()
helper = Ordinary()
ordinary = recover()
""",
    )
    for ordinal, consumer in enumerate(accepted_consumers, 1):
        assert (
            _repository_sensitive_reexport_violations(
                {
                    "tests/execution_core/helper.py": helper,
                    "tests/execution_core/consumer.py": consumer,
                }
            )
            == []
        ), ordinal

    nested = {
        "tests/execution_core/nested/__init__.py": "",
        "tests/execution_core/nested/helper.py": helper,
        "tests/execution_core/nested/consumer.py": """
from .helper import install_schema
install_schema
""",
        "tests/execution_core/nested/module_consumer.py": """
from . import helper
helper.require_approved_ddl_execution
""",
        "tests/execution_core/nested/dynamic_consumer.py": """
from importlib import import_module
import_module('.helper', package='tests.execution_core.nested').install_schema
""",
        "tests/execution_core/nested/approval_helper.py": """
from ..approved_schema_digest import require_approved_ddl_execution
""",
        "tests/execution_core/nested/approval_consumer.py": """
from .approval_helper import require_approved_ddl_execution
require_approved_ddl_execution
""",
    }
    assert _repository_sensitive_reexport_violations(nested)


def test_changed_ddl_execution_gate_refuses_without_a_valid_human_token() -> None:
    """The approval accessor stays fail-closed before any fixture can connect."""

    from approved_schema_digest import require_approved_ddl_execution

    with pytest.raises(RuntimeError, match="HUMAN-GATE pending"):
        require_approved_ddl_execution()


def test_changed_ddl_execution_gate_uses_one_exact_locked_binding() -> None:
    """The gate module cannot acquire mutable code or a derived token."""

    source_path = Path(__file__).with_name("approved_schema_digest.py")
    source = source_path.read_text(encoding="utf-8")
    assert _approval_accessor_binding_is_exact(ast.parse(source))

    mutants = (
        source.replace(
            "def require_approved_ddl_execution() -> str:",
            "def require_approved_ddl_execution(token: object = None) -> str:",
            1,
        ),
        source.replace(
            "approved = APPROVED_EXECUTION_DDL_SHA256",
            "approved = 'ab' * 32",
            1,
        ),
        source.replace(
            "or len(approved) != 64",
            "or False",
            1,
        ),
        source.replace(
            "return approved",
            "return 'ab' * 32",
            1,
        ),
        source.replace(
            "APPROVED_EXECUTION_DDL_SHA256: Final[str | None] = None",
            "APPROVED_EXECUTION_DDL_SHA256: Final[str | None] = 'ab' * 32",
            1,
        ),
        source + "\nAPPROVED_EXECUTION_DDL_SHA256 = 'ab' * 32\n",
        source + "\ntype = lambda value: str\n",
        source + "\nlen = lambda value: 64\n",
        source + "\nany = lambda values: False\n",
    )
    assert all(
        not _approval_accessor_binding_is_exact(ast.parse(mutant)) for mutant in mutants
    )

    unlocked = source.replace(
        "APPROVED_EXECUTION_DDL_SHA256: Final[str | None] = None",
        f"APPROVED_EXECUTION_DDL_SHA256: Final[str | None] = {('ab' * 32)!r}",
        1,
    )
    assert _approval_accessor_binding_is_exact(ast.parse(unlocked))


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
            "approval module mutation route",
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
            "sys module namespace route",
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
            "sys module namespace route",
        ),
        (
            """
import sys
sys.modules['approved_schema_digest'] = object()
""",
            "module registry mutation route",
        ),
        (
            """
import sys
del sys.modules['approved_schema_digest']
""",
            "module registry mutation route",
        ),
        (
            """
import sys
dict.setdefault(sys.modules, 'approved_schema_digest', object())
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
from sys import __dict__ as sys_namespace
sys_namespace['modules'].setdefault('approved_schema_digest')
""",
            "sys module namespace route",
        ),
        (
            """
from builtins import __dict__ as builtin_namespace
import sys
builtin_namespace['setattr'](
    sys.modules['approved_schema_digest'],
    'APPROVED_EXECUTION_DDL_SHA256',
    'forged',
)
""",
            "approval token mutation route",
        ),
        (
            """
import sys
mutate = sys.modules.__setitem__
""",
            "module registry mutation route",
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
def inspect(dict):
    return dict.__setitem__
"""
    assert _schema_installer_gate_violations(ordinary, "rev0093-good.py") == []


def test_rev0095_gate_audit_owns_sensitive_values_not_mutator_spellings() -> None:
    """Recognized mutations follow the proven sensitive value through aliases."""

    rejected = (
        (
            """
import operator
import sys
operator.setitem(sys.modules, 'approved_schema_digest', object())
""",
            "module registry mutation route",
        ),
        (
            """
import operator
import sys
operator.delitem(sys.modules, 'approved_schema_digest')
""",
            "module registry mutation route",
        ),
        (
            """
import operator
import sys
operator.ior(sys.modules, {'approved_schema_digest': object()})
""",
            "module registry mutation route",
        ),
        (
            """
from operator import setitem
from sys import modules
setitem(modules, 'approved_schema_digest', object())
""",
            "module registry mutation route",
        ),
        (
            """
import sys
dict.__setitem__(sys.modules, 'approved_schema_digest', object())
""",
            "module registry mutation route",
        ),
        (
            """
import sys
dict.__init__(sys.modules, {'approved_schema_digest': object()})
""",
            "module registry mutation route",
        ),
        (
            """
import sys
mutate = dict.__setitem__
mutate(sys.modules, 'approved_schema_digest', object())
""",
            "module registry mutation route",
        ),
        (
            """
from builtins import dict as builtin_dict
import sys
builtin_dict.__init__(sys.modules, {'approved_schema_digest': object()})
""",
            "module registry mutation route",
        ),
        (
            """
import operator
import sys
mutate = operator.setitem
mutate(sys.modules, 'approved_schema_digest', object())
""",
            "module registry mutation route",
        ),
        (
            """
import sys
registry = sys.modules
registry |= {'approved_schema_digest': object()}
""",
            "module registry mutation route",
        ),
        (
            """
from sys import modules
modules |= {'approved_schema_digest': object()}
""",
            "module registry mutation route",
        ),
        (
            """
import sys
sys.__dict__.update({'modules': object()})
""",
            "sys module namespace mutation route",
        ),
        (
            """
from sys import __dict__ as sys_namespace
sys_namespace.update({'modules': object()})
""",
            "sys module namespace mutation route",
        ),
        (
            """
import sys
vars(sys).pop('modules')
""",
            "sys module namespace mutation route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
def forged():
    return 'forged'
require_approved_ddl_execution.__code__ = forged.__code__
""",
            "approval accessor mutation route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
setattr(require_approved_ddl_execution, '__code__', object())
""",
            "approval accessor mutation route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
mutate = require_approved_ddl_execution.__setattr__
mutate('__code__', object())
""",
            "approval accessor mutation route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
getattr(require_approved_ddl_execution, '__setattr__')('__code__', object())
""",
            "approval accessor mutation route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
vars(require_approved_ddl_execution).update({'__code__': object()})
""",
            "approval accessor namespace route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
getattr(require_approved_ddl_execution, '__code__')
""",
            "approval accessor namespace route",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
object.__setattr__(require_approved_ddl_execution, '__code__', object())
""",
            "approval accessor escapes canonical call",
        ),
        (
            """
import operator
import sys
setattr(
    operator.getitem(sys.modules, 'approved_schema_digest'),
    'APPROVED_EXECUTION_DDL_SHA256',
    'forged',
)
""",
            "approval token mutation route",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0095-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations

    accepted = (
        """
import sqlite3
import sys
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    sys.modules.get('json')
    return sqlite3.connect(path)
""",
        """
from sys import modules
import sqlite3
from approved_schema_digest import require_approved_ddl_execution
def open_connection(path):
    require_approved_ddl_execution()
    modules['json']
    return sqlite3.connect(path)
""",
        """
import sys
def inspect(dict):
    return dict.__setitem__
""",
        """
import sys
def inspect(dict):
    return dict.__setitem__
""",
    )
    for ordinal, source in enumerate(accepted, 1):
        assert (
            _schema_installer_gate_violations(source, f"rev0095-good-{ordinal}.py")
            == []
        )


def test_rev0096_gate_audit_refuses_sensitive_capability_escapes() -> None:
    """Sensitive values have finite allowed uses; unsupported escapes fail closed."""

    rejected = (
        (
            """
import sqlite3
import sys
from approved_schema_digest import require_approved_ddl_execution
def helper(value):
    return value
def open_connection(path):
    require_approved_ddl_execution()
    helper(sys.modules)
    return sqlite3.connect(path)
""",
            "sensitive mapping escapes static boundary",
        ),
        (
            """
import sys
from approved_schema_digest import require_approved_ddl_execution
def escaped_registry():
    return sys.modules
""",
            "sensitive mapping escapes static boundary",
        ),
        (
            """
import operator
class Box:
    pass
box = Box()
box.mutator = operator.setitem
""",
            "mapping mutator capability escapes direct call",
        ),
        (
            """
import operator
def configure(mutator=operator.setitem):
    return mutator
""",
            "mapping mutator capability escapes direct call",
        ),
        (
            """
import operator
(mutator,) = (operator.setitem,)
""",
            "mapping mutator capability escapes direct call",
        ),
        (
            """
import sys
key = 'modules'
sys.__dict__[key] = object()
""",
            "sys module namespace mutation route",
        ),
        (
            """
import sys
del vars(sys)[key]
""",
            "sys module namespace mutation route",
        ),
        (
            """
import sys
vars(sys)[key]['approved_schema_digest'] = object()
""",
            "sys module namespace dynamic lookup route",
        ),
        (
            """
import sys
sys.__dict__[key] |= {'approved_schema_digest': object()}
""",
            "sys module namespace mutation route",
        ),
        (
            """
import operator
import sys
mutate = operator.setitem
if condition:
    mutate = ordinary
mutate(sys.modules, 'approved_schema_digest', object())
""",
            "mapping mutator capability escapes direct call",
        ),
        (
            """
import sys
dict.__setitem__(sys.modules, 'approved_schema_digest', object())
dict = custom_dict
""",
            "module registry mutation route",
        ),
        (
            """
import sys
class Scope:
    dict.__setitem__(sys.modules, 'approved_schema_digest', object())
    dict = custom_dict
""",
            "module registry mutation route",
        ),
        (
            """
import approved_schema_digest as gate
object.__setattr__(gate.require_approved_ddl_execution, '__code__', object())
""",
            "approval accessor escapes canonical call",
        ),
        (
            """
import sys
object.__getattribute__(
    sys.modules['approved_schema_digest'].require_approved_ddl_execution,
    '__globals__',
)['APPROVED_EXECUTION_DDL_SHA256'] = 'forged'
""",
            "approval accessor escapes canonical call",
        ),
        (
            """
import sys
dict.__setitem__.__call__(
    sys.modules, 'approved_schema_digest', object()
)
""",
            "mapping mutator capability escapes direct call",
        ),
        (
            """
import sys
dict.__setitem__.__get__(sys.modules, dict)(
    'approved_schema_digest', object()
)
""",
            "mapping mutator capability escapes direct call",
        ),
        (
            """
import sys
vars(dict)['__setitem__'](sys.modules, 'approved_schema_digest', object())
""",
            "module registry mutation route",
        ),
        (
            """
import operator
import sys
vars(operator)['setitem'](sys.modules, 'approved_schema_digest', object())
""",
            "module registry mutation route",
        ),
        (
            """
import approved_schema_digest as gate
monkeypatch.setattr(gate, 'APPROVED_EXECUTION_DDL_SHA256', 'forged')
""",
            "approval module escapes canonical import",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0096-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations

    accepted = (
        """
import operator
operator.setitem({}, 'ordinary', object())
""",
        """
import sys
def inspect(dict):
    return dict.__setitem__
""",
        """
import sys
ordinary_sys_member = vars(sys)['approved_schema_digest']
""",
    )
    for ordinal, source in enumerate(accepted, 1):
        assert (
            _schema_installer_gate_violations(source, f"rev0096-good-{ordinal}.py")
            == []
        )


def test_rev0097_gate_audit_owns_sensitive_maps_across_source_boundaries() -> None:
    """Registry maps remain owned even before a local source reaches SQLite."""

    rejected = (
        (
            """
import sys
key = runtime_name()
sys.modules.get(key).APPROVED_EXECUTION_DDL_SHA256 = 'forged'
""",
            "module registry dynamic lookup route",
        ),
        (
            """
import sys
def escaped_registry():
    return sys.modules
""",
            "sensitive mapping escapes static boundary",
        ),
        (
            """
import sys
key = runtime_name()
dict.get(sys.modules, key).APPROVED_EXECUTION_DDL_SHA256 = 'forged'
""",
            "module registry dynamic lookup route",
        ),
        (
            """
import sys
def inspect(dict):
    return dict.get(sys.modules, 'approved_schema_digest')
""",
            "sensitive mapping escapes static boundary",
        ),
        (
            """
import operator
import sys
key = runtime_name()
operator.getitem(sys.modules, key).APPROVED_EXECUTION_DDL_SHA256 = 'forged'
""",
            "module registry dynamic lookup route",
        ),
        (
            """
import sys
from approved_schema_digest import require_approved_ddl_execution
def mutate():
    dict.__setitem__(sys.modules, 'approved_schema_digest', object())
mutate()
dict = custom_dict
""",
            "module registry mutation route",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0097-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations

    accepted = (
        """
import sys
ordinary = sys.modules.get('json')
""",
        """
import operator
import sys
ordinary = operator.getitem(sys.modules, 'json')
""",
        """
import sys
def inspect(dict):
    return dict.__setitem__
""",
    )
    for ordinal, source in enumerate(accepted, 1):
        assert (
            _schema_installer_gate_violations(source, f"rev0097-good-{ordinal}.py")
            == []
        )


def test_rev0098_gate_audit_refuses_reflected_capability_roots() -> None:
    """Reflection cannot recover or replace governed modules and import machinery."""

    rejected = (
        (
            """
import sys
sys.__getattribute__('modules')['approved_schema_digest'] = object()
""",
            "sys module reflection route",
        ),
        (
            """
import sys
object.__getattribute__(sys, 'modules')['approved_schema_digest'] = object()
""",
            "sys module reflection route",
        ),
        (
            """
from app.execution_core.persistence import schema
setattr(schema, 'install_schema', object())
""",
            "schema installer mutation route",
        ),
        (
            """
from app.execution_core.persistence import schema
schema.__setattr__('install_schema', object())
""",
            "schema installer mutation route",
        ),
        (
            """
from app.execution_core.persistence import schema
object.__setattr__(schema, 'install_schema', object())
""",
            "schema installer mutation route",
        ),
        (
            """
import builtins
builtins.__import__ = object()
""",
            "importer mutation route",
        ),
        (
            """
import builtins
vars(builtins)['__import__'] = object()
""",
            "importer mutation route",
        ),
        (
            """
import builtins
builtins.__dict__.update({'__import__': object()})
""",
            "importer mutation route",
        ),
        (
            """
import builtins
alias = builtins.__import__
""",
            "importer escapes direct call",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(source, f"rev0098-{ordinal}.py")
        assert any(expected in violation for violation in violations), violations


def test_rev0098_gate_audit_models_deferred_function_global_bindings() -> None:
    """Function globals may be established after definition but before invocation."""

    rejected = (
        (
            """
sqlite3 = object()
def open_connection(path):
    return sqlite3.connect(path)
import sqlite3
open_connection('ordinary-path')
""",
            "approval gate does not dominate SQLite connect",
        ),
        (
            """
def mutate():
    sys.modules['approved_schema_digest'] = object()
import sys
mutate()
""",
            "module registry mutation route",
        ),
        (
            """
def mutate():
    return require_approved_ddl_execution.__globals__
from approved_schema_digest import require_approved_ddl_execution
mutate()
""",
            "approval accessor namespace route",
        ),
    )
    for ordinal, (source, expected) in enumerate(rejected, 1):
        violations = _schema_installer_gate_violations(
            source, f"rev0098-late-{ordinal}.py"
        )
        assert any(expected in violation for violation in violations), violations


def test_rev0099_gate_audit_owns_governed_module_values_without_global_syntax_bans() -> (
    None
):
    """Governed modules cannot escape, while unrelated introspection stays ordinary."""

    rejected = (
        """
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
def escape():
    return consume(schema)
""",
        """
import builtins
from approved_schema_digest import require_approved_ddl_execution
escaped = [builtins]
""",
        """
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
vars(schema).update({'install_schema': object()})
""",
        """
import sys
from approved_schema_digest import require_approved_ddl_execution
registry = sys.__class__.__getattribute__(sys, 'modules')
registry['approved_schema_digest'] = object()
""",
        """
from app.execution_core.persistence import schema
from approved_schema_digest import require_approved_ddl_execution
proxy.setattr(schema, 'schema_ddl_digest', object())
""",
        """
import builtins
vars(builtins)['type'] = object()
""",
        """
import builtins
import operator
operator.setitem(vars(builtins), 'len', object())
""",
    )
    for ordinal, source in enumerate(rejected, 1):
        assert _schema_installer_gate_violations(
            source, f"rev0099-governed-{ordinal}.py"
        )

    unrelated = """
import builtins
def resolve_builtin(name):
    return vars(builtins)[name]
"""
    assert (
        _schema_installer_gate_violations(unrelated, "ordinary-introspection.py") == []
    )


def test_rev0100_gate_audit_owns_package_identity_and_dynamic_governed_values() -> None:
    """Gate provenance is package-aware and independent of a local gate spelling."""

    rejected = (
        (
            """
from app.execution_core.persistence import schema
proxy.setattr(schema, 'install_schema', object())
""",
            "tests/execution_core/no-gate-schema.py",
            "governed module escapes direct operation",
        ),
        (
            """
from app.execution_core.persistence import schema
escaped = [schema]
""",
            "tests/execution_core/no-gate-container.py",
            "governed module escapes direct operation",
        ),
        (
            """
from app.execution_core.persistence import schema
schema.__class__.__setattr__(schema, 'install_schema', object())
""",
            "tests/execution_core/no-gate-module-class.py",
            "governed module escapes direct operation",
        ),
        (
            """
import sys
def mutate(name):
    getattr(sys, name)['approved_schema_digest'] = object()
""",
            "tests/execution_core/dynamic-sys-member.py",
            "governed module escapes direct operation",
        ),
        (
            """
import builtins
def mutate(name):
    getattr(builtins, name)['type'] = object()
""",
            "tests/execution_core/dynamic-builtins-member.py",
            "governed module escapes direct operation",
        ),
        (
            """
from app.execution_core.persistence.schema import *
def setup(connection):
    install_schema(connection, approved_ddl_sha256=schema_ddl_digest())
""",
            "tests/execution_core/schema-wildcard.py",
            "governed module wildcard import",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
from .schema import install_schema
def setup(connection):
    require_approved_ddl_execution()
    install_schema(connection, approved_ddl_sha256='00' * 32)
""",
            "app/execution_core/persistence/relative-member.py",
            "installer lacks exact approval accessor",
        ),
        (
            """
from approved_schema_digest import require_approved_ddl_execution
from . import schema
def setup(connection):
    require_approved_ddl_execution()
    schema.install_schema(connection, approved_ddl_sha256='00' * 32)
""",
            "app/execution_core/persistence/relative-module.py",
            "installer lacks exact approval accessor",
        ),
        (
            """
from .approved_schema_digest import require_approved_ddl_execution
from app.execution_core.persistence.schema import install_schema
def setup(connection):
    require_approved_ddl_execution()
    install_schema(
        connection,
        approved_ddl_sha256=require_approved_ddl_execution(),
    )
""",
            "tests/execution_core/relative-approval.py",
            "approval module member import is not canonical",
        ),
    )
    for source, label, expected in rejected:
        violations = _schema_installer_gate_violations(source, label)
        assert any(expected in violation for violation in violations), violations


def test_rev0101_gate_audit_owns_derived_maps_and_deferred_parent_state() -> None:
    """Derived governed values and call-observable parent bindings stay owned."""

    rejected = (
        """
import builtins
def resolve_builtin(name):
    return vars(builtins)[name]
loader = resolve_builtin('__import__')
schema = loader(
    'app.execution_core.persistence.schema',
    fromlist=('install_schema',),
)
schema.install_schema(
    connection,
    approved_ddl_sha256=schema.schema_ddl_digest(),
)
""",
        """
from app.execution_core.persistence import schema
schema.__builtins__['__import__']('sqlite3').connect('forbidden.db')
""",
        """
from app.execution_core.persistence import schema
vars(schema).update({'install_schema': object()})
""",
        """
def outer():
    def mutate():
        sys.modules['approved_schema_digest'] = object()
    import sys
    mutate()
outer()
""",
        """
from importlib import import_module
def mutate():
    import_module(TARGET).APPROVED_EXECUTION_DDL_SHA256 = 'ab' * 32
TARGET = 'approved_schema_digest'
mutate()
""",
        """
import importlib
escaped = [importlib]
""",
        """
import builtins
import importlib
import operator
import sys
escaped = (
    builtins.__loader__,
    importlib.__loader__,
    operator.__loader__,
    sys.__loader__,
)
""",
        """
from importlib import import_module
TARGET = 'sqlite3'
if condition:
    TARGET = 'json'
import_module(TARGET).connect('forbidden.db')
""",
    )
    for ordinal, source in enumerate(rejected, 1):
        assert _schema_installer_gate_violations(
            source,
            f"rev0101-{ordinal}.py",
        ), ordinal

    accepted = (
        """
import builtins
expected = builtins.ValueError
""",
        """
import builtins
import sys
expected = (builtins.ValueError, sys.executable)
""",
        """
from importlib import import_module
def connect(path):
    return import_module(TARGET).connect(path)
TARGET = 'sqlite3'
TARGET = 'ordinary_transport'
connect('ordinary.resource')
""",
    )
    for ordinal, source in enumerate(accepted, 1):
        assert (
            _schema_installer_gate_violations(
                source,
                f"rev0101-good-{ordinal}.py",
            )
            == []
        ), ordinal
