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
            if node.module == "app.execution_core.persistence.repository":
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
    *,
    scope: ast.AST,
    before_line: int,
) -> tuple[ast.expr, ...] | None:
    if isinstance(expression, ast.Name):
        candidates = [
            candidate
            for candidate in assignments.get((scope, expression.id), [])
            if candidate.lineno < before_line
        ]
        if not candidates:
            return None
        expression = max(candidates, key=lambda candidate: candidate.lineno)
    if isinstance(expression, (ast.Tuple, ast.List)):
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
    ):
        return None
    scope = _lexical_scope(loop, parents)
    rows = _literal_rows(
        loop.iter,
        assignments,
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

    for node in ast.walk(loop):
        if not isinstance(node, ast.Name) or node.id != "operation":
            continue
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
            if any(alias.name == "importlib" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
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


def _fixture_mutator_capability_violations(source: str) -> tuple[str, ...]:
    """Enforce the three fixtures' closed, syntax-level mutator grammar."""

    tree = ast.parse(source)
    parents = _parent_map(tree)
    violations: list[str] = []
    if not _repository_import_is_canonical(tree):
        violations.append("repository-import-or-alias")
    if _has_dynamic_namespace_recovery(tree, parents):
        violations.append("dynamic-namespace-recovery")

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
    return (
        not _has_dynamic_namespace_recovery(tree, parents)
        and _fixture_setup_helper_is_exact(tree)
        and (not require_apply_helper or _fixture_apply_helper_is_exact(tree))
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
    )
    for mutant in mutants:
        assert not _fixture_helper_shape_is_exact(mutant, require_apply_helper=True)
