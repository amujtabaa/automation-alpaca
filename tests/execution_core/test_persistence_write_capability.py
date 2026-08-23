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


def _exact_function(
    tree: ast.Module,
    name: str,
) -> ast.FunctionDef | None:
    definitions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    nested = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(definitions) != 1 or len(nested) != 1:
        return None
    return definitions[0]


def _has_rebinding(
    tree: ast.Module,
    *,
    name: str,
    permitted_function: ast.FunctionDef | None = None,
) -> bool:
    """Reject every shadow/rebind route rather than trusting a name spelling."""

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and node.id == name
        ):
            return True
        if isinstance(node, ast.arg) and node.arg == name:
            return True
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)) and node.name == name:
            return True
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
            and node is not permitted_function
        ):
            return True
    return False


def _import_bindings(
    tree: ast.Module,
    name: str,
) -> tuple[tuple[str | None, str, str | None], ...]:
    bindings: list[tuple[str | None, str, str | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if (alias.asname or alias.name.split(".", 1)[0]) == name:
                    bindings.append((None, alias.name, alias.asname))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if (alias.asname or alias.name) == name:
                    bindings.append((node.module, alias.name, alias.asname))
    return tuple(bindings)


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


def _support_import_is_exact(tree: ast.Module) -> bool:
    return bool(
        _import_bindings(tree, "setup_support")
        == ((None, "persistence_setup_support", "setup_support"),)
        and not _has_rebinding(tree, name="setup_support")
    )


def _fixture_setup_helper_is_exact(tree: ast.Module) -> bool:
    """Pin one unshadowed setup wrapper to the named test-support issuer."""

    helper = _exact_function(tree, "_setup_write_capability")
    if (
        helper is None
        or helper.decorator_list
        or not _support_import_is_exact(tree)
        or _import_bindings(tree, "_setup_write_capability")
        or _has_rebinding(
            tree,
            name="_setup_write_capability",
            permitted_function=helper,
        )
        or not _exact_arguments(
            helper.args,
            positional=("connection",),
            vararg=None,
        )
    ):
        return False
    body = _body_without_docstring(helper)
    if (
        len(body) != 1
        or not isinstance(body[0], ast.Return)
        or not isinstance(body[0].value, ast.Call)
    ):
        return False
    call = body[0].value
    return bool(
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "setup_support"
        and call.func.attr == "issue_setup_write_capability"
        and len(call.args) == 1
        and not call.keywords
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "connection"
    )


def _fixture_apply_helper_is_exact(tree: ast.Module) -> bool:
    """Pin the only allowed higher-order writer to the exact setup wrapper."""

    helper = _exact_function(tree, "_apply_mutator")
    if (
        helper is None
        or helper.decorator_list
        or _import_bindings(tree, "_apply_mutator")
        or _has_rebinding(tree, name="_apply_mutator", permitted_function=helper)
        or not _exact_arguments(
            helper.args,
            positional=("connection", "operation"),
            vararg="arguments",
        )
    ):
        return False
    body = _body_without_docstring(helper)
    if (
        len(body) != 1
        or not isinstance(body[0], ast.Return)
        or not isinstance(body[0].value, ast.Call)
    ):
        return False
    call = body[0].value
    capability_keywords = [
        keyword.value for keyword in call.keywords if keyword.arg == "capability"
    ]
    return bool(
        isinstance(call.func, ast.Name)
        and call.func.id == "operation"
        and len(call.args) == 2
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "connection"
        and isinstance(call.args[1], ast.Starred)
        and isinstance(call.args[1].value, ast.Name)
        and call.args[1].value.id == "arguments"
        and len(capability_keywords) == 1
        and _is_issued_setup_capability(capability_keywords[0], connection=call.args[0])
    )


def _is_repository_expression(
    expression: ast.expr,
    *,
    repository_aliases: frozenset[str],
    package_aliases: frozenset[str],
) -> bool:
    return bool(
        (isinstance(expression, ast.Name) and expression.id in repository_aliases)
        or (
            isinstance(expression, ast.Attribute)
            and isinstance(expression.value, ast.Name)
            and expression.value.id in package_aliases
            and expression.attr == "repository"
        )
    )


def _dispatch_from_expression(
    expression: ast.expr,
    *,
    repository_aliases: frozenset[str],
    package_aliases: frozenset[str],
    getter_aliases: frozenset[str],
    mutator_aliases: dict[str, str],
    unresolved_aliases: frozenset[str],
) -> tuple[str | None, bool]:
    """Resolve finite fixture dispatch or mark repository-derived dynamics unsafe."""

    if isinstance(expression, ast.Name):
        return mutator_aliases.get(expression.id), expression.id in unresolved_aliases
    if (
        isinstance(expression, ast.Attribute)
        and _is_repository_expression(
            expression.value,
            repository_aliases=repository_aliases,
            package_aliases=package_aliases,
        )
        and expression.attr in _mutator_names()
    ):
        return expression.attr, False
    if (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id in getter_aliases
        and len(expression.args) == 2
        and not expression.keywords
        and _is_repository_expression(
            expression.args[0],
            repository_aliases=repository_aliases,
            package_aliases=package_aliases,
        )
    ):
        member = expression.args[1]
        if (
            isinstance(member, ast.Constant)
            and isinstance(member.value, str)
            and member.value in _mutator_names()
        ):
            return member.value, False
        return None, True
    return None, False


def _fixture_mutator_aliases(
    tree: ast.Module,
) -> tuple[
    frozenset[str],
    frozenset[str],
    frozenset[str],
    dict[str, str],
    frozenset[str],
]:
    """Resolve only the finite, source-level repository dispatch grammar."""

    repository_aliases = {"repository"}
    package_aliases: set[str] = set()
    getter_aliases = {"getattr"}
    mutator_aliases: dict[str, str] = {}
    unresolved_aliases: set[str] = set()

    def resolve(value: ast.expr) -> tuple[str | None, bool]:
        return _dispatch_from_expression(
            value,
            repository_aliases=frozenset(repository_aliases),
            package_aliases=frozenset(package_aliases),
            getter_aliases=frozenset(getter_aliases),
            mutator_aliases=mutator_aliases,
            unresolved_aliases=frozenset(unresolved_aliases),
        )

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
                    elif alias.name == "app.execution_core.persistence":
                        name = alias.asname or alias.name.rsplit(".", 1)[-1]
                        if name not in package_aliases:
                            package_aliases.add(name)
                            changed = True
                continue
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if (
                        node.module == "app.execution_core.persistence"
                        and alias.name == "repository"
                    ):
                        name = alias.asname or alias.name
                        if name not in repository_aliases:
                            repository_aliases.add(name)
                            changed = True
                    elif (
                        node.module == "app.execution_core.persistence.repository"
                        and alias.name in _mutator_names()
                    ):
                        name = alias.asname or alias.name
                        if mutator_aliases.get(name) != alias.name:
                            mutator_aliases[name] = alias.name
                            changed = True
                    elif node.module == "builtins" and alias.name == "getattr":
                        name = alias.asname or alias.name
                        if name not in getter_aliases:
                            getter_aliases.add(name)
                            changed = True
                continue
            if isinstance(node, ast.FunctionDef):
                positional = (*node.args.posonlyargs, *node.args.args)
                defaults = node.args.defaults
                default_pairs = (
                    zip(positional[-len(defaults) :], defaults) if defaults else ()
                )
                for argument, value in (
                    *default_pairs,
                    *zip(node.args.kwonlyargs, node.args.kw_defaults),
                ):
                    if value is None:
                        continue
                    mutator_name, unresolved = resolve(value)
                    if (
                        mutator_name is not None
                        and mutator_aliases.get(argument.arg) != mutator_name
                    ):
                        mutator_aliases[argument.arg] = mutator_name
                        changed = True
                    if unresolved and argument.arg not in unresolved_aliases:
                        unresolved_aliases.add(argument.arg)
                        changed = True
                continue
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                continue
            value = node.value
            for target in _assignment_names(node):
                if _is_repository_expression(
                    value,
                    repository_aliases=frozenset(repository_aliases),
                    package_aliases=frozenset(package_aliases),
                ):
                    if target not in repository_aliases:
                        repository_aliases.add(target)
                        changed = True
                    continue
                if isinstance(value, ast.Name) and value.id in getter_aliases:
                    if target not in getter_aliases:
                        getter_aliases.add(target)
                        changed = True
                    continue
                mutator_name, unresolved = resolve(value)
                if (
                    mutator_name is not None
                    and mutator_aliases.get(target) != mutator_name
                ):
                    mutator_aliases[target] = mutator_name
                    changed = True
                if unresolved and target not in unresolved_aliases:
                    unresolved_aliases.add(target)
                    changed = True
    return (
        frozenset(repository_aliases),
        frozenset(package_aliases),
        frozenset(getter_aliases),
        mutator_aliases,
        frozenset(unresolved_aliases),
    )


def _is_issued_setup_capability(
    expression: ast.expr,
    *,
    connection: ast.expr,
) -> bool:
    """Accept only an exact wrapper call bound to the same direct name."""

    return (
        isinstance(connection, ast.Name)
        and isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "_setup_write_capability"
        and len(expression.args) == 1
        and not expression.keywords
        and isinstance(expression.args[0], ast.Name)
        and expression.args[0].id == connection.id
    )


def _fixture_mutator_capability_violations(source: str) -> tuple[str, ...]:
    """Return every direct, escaped, or dynamic mutator route outside the grammar."""

    tree = ast.parse(source)
    (
        repository_aliases,
        package_aliases,
        getter_aliases,
        mutator_aliases,
        unresolved_aliases,
    ) = _fixture_mutator_aliases(tree)

    def resolve(expression: ast.expr) -> tuple[str | None, bool]:
        return _dispatch_from_expression(
            expression,
            repository_aliases=repository_aliases,
            package_aliases=package_aliases,
            getter_aliases=getter_aliases,
            mutator_aliases=mutator_aliases,
            unresolved_aliases=unresolved_aliases,
        )

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        mutator_name, unresolved = resolve(node.func)
        if unresolved:
            violations.append("unresolved-repository-dispatch")
        if mutator_name is not None:
            capability_keywords = [
                keyword.value
                for keyword in node.keywords
                if keyword.arg == "capability"
            ]
            if (
                len(node.args) < 1
                or len(capability_keywords) != 1
                or not _is_issued_setup_capability(
                    capability_keywords[0], connection=node.args[0]
                )
            ):
                violations.append(mutator_name)
        for index, argument in enumerate(node.args):
            argument_mutator, argument_unresolved = resolve(argument)
            if argument_unresolved:
                violations.append("unresolved-repository-dispatch")
            if argument_mutator is not None and not (
                isinstance(node.func, ast.Name)
                and node.func.id == "_apply_mutator"
                and index == 1
            ):
                violations.append(argument_mutator)
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            argument_mutator, argument_unresolved = resolve(keyword.value)
            if argument_unresolved:
                violations.append("unresolved-repository-dispatch")
            if argument_mutator is not None:
                violations.append(argument_mutator)
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and node.value is not None:
            mutator_name, unresolved = resolve(node.value)
            if unresolved:
                violations.append("unresolved-repository-dispatch")
            elif mutator_name is not None:
                violations.append(mutator_name)
    return tuple(sorted(violations))


def _fixture_helper_shape_is_exact(
    source: str,
    *,
    require_apply_helper: bool,
) -> bool:
    """Require an exact unshadowed setup helper and optional writer helper."""

    tree = ast.parse(source)
    return _fixture_setup_helper_is_exact(tree) and (
        not require_apply_helper or _fixture_apply_helper_is_exact(tree)
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
    for fixture_name, requires_apply_helper in (
        ("test_persistence_repository.py", True),
        ("test_persistence_directness.py", True),
        ("test_persistence_input_receipt.py", False),
    ):
        fixture_path = Path(__file__).with_name(fixture_name)
        fixture_source = fixture_path.read_text(encoding="utf-8")
        assert _fixture_helper_shape_is_exact(
            fixture_source,
            require_apply_helper=requires_apply_helper,
        )
        assert _fixture_mutator_capability_violations(fixture_source) == ()

    direct_missing_capability = """
repository.store_scope(connection, record)
repository.load_scope(connection, 1)
"""
    assert _fixture_mutator_capability_violations(direct_missing_capability) == (
        "store_scope",
    )

    module_getter_and_alias_chain = """
from app.execution_core.persistence import repository as repo
import app.execution_core.persistence as persistence

repository_alias = persistence.repository
mutator = repository_alias.store_scope
mutator(connection, record)
repo.store_scope(connection, record, capability=object())
getattr(repository, "store_scope")(connection, record, capability=object())
lookup = getattr
lookup(repository, "store_scope")(connection, record, capability=object())
getattr(repository, dynamic_member)(connection, record, capability=object())
"""
    assert _fixture_mutator_capability_violations(module_getter_and_alias_chain) == (
        "store_scope",
        "store_scope",
        "store_scope",
        "store_scope",
        "unresolved-repository-dispatch",
    )

    wrong_connection_and_proxy = """
repository.store_scope(
    connection,
    record,
    capability=_setup_write_capability(other_connection),
)
repository.store_scope(
    next_connection(),
    record,
    capability=_setup_write_capability(next_connection()),
)
"""
    assert _fixture_mutator_capability_violations(wrong_connection_and_proxy) == (
        "store_scope",
        "store_scope",
    )

    valid_setup_helper = """
import persistence_setup_support as setup_support

def _setup_write_capability(connection):
    return setup_support.issue_setup_write_capability(connection)
"""
    assert _fixture_helper_shape_is_exact(
        valid_setup_helper,
        require_apply_helper=False,
    )

    valid_apply_helper = (
        valid_setup_helper
        + """

def _apply_mutator(connection, operation, *arguments):
    return operation(
        connection,
        *arguments,
        capability=_setup_write_capability(connection),
    )
"""
    )
    assert _fixture_helper_shape_is_exact(
        valid_apply_helper,
        require_apply_helper=True,
    )

    rebound_setup_helper = (
        valid_setup_helper
        + """

_setup_write_capability = lambda connection: object()
"""
    )
    assert not _fixture_helper_shape_is_exact(
        rebound_setup_helper,
        require_apply_helper=False,
    )

    shadowed_issuer = (
        valid_setup_helper
        + """

setup_support = object()
"""
    )
    assert not _fixture_helper_shape_is_exact(
        shadowed_issuer,
        require_apply_helper=False,
    )

    imported_shadow = (
        valid_setup_helper
        + """

def hide_issuer():
    import counterfeit_support as setup_support
"""
    )
    assert not _fixture_helper_shape_is_exact(
        imported_shadow,
        require_apply_helper=False,
    )

    decorated_or_extra_apply_helper = (
        valid_setup_helper
        + """

@decorate
def _apply_mutator(connection, operation, extra, *arguments):
    return operation(
        connection,
        *arguments,
        capability=_setup_write_capability(connection),
    )
"""
    )
    assert not _fixture_helper_shape_is_exact(
        decorated_or_extra_apply_helper,
        require_apply_helper=True,
    )

    default_and_proxy_dispatch = """
def invoke(operation=repository.store_scope):
    return operation(connection, record, capability=object())

def proxy(operation):
    return operation(connection, record, capability=object())

proxy(repository.store_scope)
"""
    assert _fixture_mutator_capability_violations(default_and_proxy_dispatch) == (
        "store_scope",
        "store_scope",
        "store_scope",
    )
