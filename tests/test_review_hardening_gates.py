"""REV-0029 review-hardening — Tier-1 mechanical gates (CI-blocking).

`pkl/process/review-hardening.md` T1.1 + T1.3, ratified CI-blocking by Ameen on
2026-07-18. These are DETERMINISTIC, no-model-judgment gates: they exist because
REV-0029 found a safety-enum SUBSET gating a decision (P0-1 — `CANCEL_PENDING`
outside the flatten-block set) and a projection field with ZERO rail consumers
(P0-3) that six in-process lenses missed — both catchable without judgment. Adding
an unclassified enum member, shrinking a totality set, or adding a safety field no
rail consumes must break the build HERE, at review time, not at the venue.

Tier-1's other two rules (T1.2 mutation-check, T1.4 N-run) remain review-checklist
items until automated (follow-up process WO) per the same ratification.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.models import OrderStatus
from app.policy import MAY_EXECUTE_ORDER_STATUSES, NON_TERMINAL_ORDER_STATUSES
from app.store.core import FLATTEN_BLOCKING_BUY_STATUSES, OPEN_BUY_STATUSES

_APP = Path(__file__).resolve().parent.parent / "app"


# --------------------------------------------------------------------------- #
# T1.1 — enum-total classification. Every safety-gating set over OrderStatus is
# TOTAL over the enum: a new member (or a member dropped from a totality set)
# breaks the build until explicitly classified. This is the gate that would have
# caught P0-1.
# --------------------------------------------------------------------------- #


def test_t1_1_order_status_partitions_into_terminal_and_non_terminal():
    """`NON_TERMINAL_ORDER_STATUSES` (derived from the transition table) and its
    complement partition the FULL enum: every member is in exactly one bucket, so
    no status is silently unclassified."""
    terminal = {s for s in OrderStatus if s not in NON_TERMINAL_ORDER_STATUSES}
    assert terminal | NON_TERMINAL_ORDER_STATUSES == set(OrderStatus)
    assert terminal & NON_TERMINAL_ORDER_STATUSES == set()
    # Terminal is exactly the settled trio; a change here is a deliberate
    # lifecycle change, not an accident.
    assert {s.value for s in terminal} == {"filled", "canceled", "rejected"}


def test_t1_1_flatten_blocks_every_non_terminal_buy_status():
    """P0-1's class. A flatten must block on EVERY status in which a BUY can still
    fill — the WHOLE non-terminal set, never a subset. `FLATTEN_BLOCKING_BUY_
    STATUSES` must therefore equal `NON_TERMINAL_ORDER_STATUSES`; a new non-
    terminal status not added to the flatten-block set breaks this pin, exactly
    the gap REV-0029 found (`CANCEL_PENDING` was outside `OPEN_BUY_STATUSES`)."""
    assert FLATTEN_BLOCKING_BUY_STATUSES == NON_TERMINAL_ORDER_STATUSES
    # The cancellable subset the caller may act on is a STRICT subset: the
    # venue-uncertain statuses (SUBMITTING / CANCEL_PENDING / TIMEOUT_QUARANTINE)
    # block the flatten but must never be blind-cancelled.
    assert OPEN_BUY_STATUSES < FLATTEN_BLOCKING_BUY_STATUSES
    assert FLATTEN_BLOCKING_BUY_STATUSES - OPEN_BUY_STATUSES == {
        OrderStatus.SUBMITTING,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.TIMEOUT_QUARANTINE,
    }


def test_t1_1_may_execute_is_total_over_order_status():
    """P0-2's set. 'A BUY may execute at the venue' = every non-terminal status
    EXCEPT `CREATED` (a pre-claim BUY is blocked at its own claim). Totality:
    every OrderStatus is may-execute, or `CREATED`, or terminal — no member is
    left unclassified, and a new non-terminal venue status is auto-included
    (fail-safe by derivation)."""
    assert MAY_EXECUTE_ORDER_STATUSES == NON_TERMINAL_ORDER_STATUSES - {
        OrderStatus.CREATED
    }
    terminal = {s for s in OrderStatus if s not in NON_TERMINAL_ORDER_STATUSES}
    classified = MAY_EXECUTE_ORDER_STATUSES | {OrderStatus.CREATED} | terminal
    assert classified == set(OrderStatus)


# --------------------------------------------------------------------------- #
# T1.3 — producer/consumer for new safety fields. A projection/store safety field
# must have real RAIL consumers, verified from executable AST sites (never by
# sampling positives or counting textual mentions). Zero-consumer-while-docs-
# claim-"every-choke" is the P0-3 defect.
# --------------------------------------------------------------------------- #


def _function_node(
    source: str, function_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    ]
    assert len(matches) == 1, (
        f"expected one function {function_name}, found {len(matches)}"
    )
    return matches[0]


def _call_name(callable_node: ast.expr) -> str | None:
    if isinstance(callable_node, ast.Name):
        return callable_node.id
    if isinstance(callable_node, ast.Attribute):
        return callable_node.attr
    return None


def _reachable_statements(statements: list[ast.stmt]):
    """Yield statements on a potentially live path, excluding obvious dead code."""

    for statement in statements:
        yield statement
        if isinstance(statement, ast.If):
            constant = (
                statement.test.value
                if isinstance(statement.test, ast.Constant)
                and isinstance(statement.test.value, bool)
                else None
            )
            if constant is False:
                yield from _reachable_statements(statement.orelse)
            elif constant is True:
                yield from _reachable_statements(statement.body)
            else:
                yield from _reachable_statements(statement.body)
                yield from _reachable_statements(statement.orelse)
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            yield from _reachable_statements(statement.body)
        elif isinstance(statement, (ast.For, ast.AsyncFor)):
            yield from _reachable_statements(statement.body)
            yield from _reachable_statements(statement.orelse)
        elif isinstance(statement, ast.While):
            if not (
                isinstance(statement.test, ast.Constant)
                and statement.test.value is False
            ):
                yield from _reachable_statements(statement.body)
            yield from _reachable_statements(statement.orelse)
        elif isinstance(statement, (ast.Try, ast.TryStar)):
            yield from _reachable_statements(statement.body)
            for handler in statement.handlers:
                yield from _reachable_statements(handler.body)
            yield from _reachable_statements(statement.orelse)
            yield from _reachable_statements(statement.finalbody)
        elif isinstance(statement, ast.Match):
            for case in statement.cases:
                yield from _reachable_statements(case.body)
        if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            break


def _statement_expressions(statement: ast.stmt) -> tuple[ast.expr, ...]:
    if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        return (statement.value,) if statement.value is not None else ()
    if isinstance(statement, (ast.Return, ast.Expr)):
        return (statement.value,) if statement.value is not None else ()
    if isinstance(statement, (ast.If, ast.While)):
        return (statement.test,)
    return ()


def _live_function_calls(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
):
    for statement in _reachable_statements(function.body):
        for expression in _statement_expressions(statement):
            yield from (
                node for node in ast.walk(expression) if isinstance(node, ast.Call)
            )


def _function_call_keyword_loads_name(
    source: str,
    *,
    function_name: str,
    call_name: str,
    keyword_name: str,
    loaded_name: str,
) -> bool:
    function = _function_node(source, function_name)
    for call in _live_function_calls(function):
        if _call_name(call.func) != call_name:
            continue
        for keyword in call.keywords:
            if keyword.arg != keyword_name:
                continue
            if any(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == loaded_name
                for node in ast.walk(keyword.value)
            ):
                return True
    return False


def _function_call_keyword_is_name(
    source: str,
    *,
    function_name: str,
    call_name: str,
    keyword_name: str,
    value_name: str,
) -> bool:
    function = _function_node(source, function_name)
    return any(
        keyword.arg == keyword_name
        and isinstance(keyword.value, ast.Name)
        and isinstance(keyword.value.ctx, ast.Load)
        and keyword.value.id == value_name
        for call in _live_function_calls(function)
        if _call_name(call.func) == call_name
        for keyword in call.keywords
    )


def _function_has_attribute_guard(
    source: str,
    *,
    function_name: str,
    object_name: str,
    attribute_name: str,
    exit_kind: type[ast.stmt],
) -> bool:
    function = _function_node(source, function_name)
    for branch in (
        node
        for node in _reachable_statements(function.body)
        if isinstance(node, ast.If)
    ):
        test = branch.test
        if not (
            isinstance(test, ast.Attribute)
            and test.attr == attribute_name
            and isinstance(test.value, ast.Name)
            and test.value.id == object_name
        ):
            continue
        direct_exits = [
            statement for statement in branch.body if isinstance(statement, exit_kind)
        ]
        if exit_kind is ast.Return:
            if any(
                isinstance(statement, ast.Return)
                and statement.value is not None
                and not (
                    isinstance(statement.value, ast.Constant)
                    and statement.value.value is None
                )
                for statement in direct_exits
            ):
                return True
        elif direct_exits:
            return True
    return False


def _app_source(relative_path: str) -> str:
    return (_APP / relative_path).read_text(encoding="utf-8")


def test_t1_3_needs_review_child_order_ids_has_real_producer():
    """The projection field must be assigned from the computed child set."""

    assert _function_call_keyword_loads_name(
        _app_source("store/core.py"),
        function_name="project_envelope_obligation",
        call_name="EnvelopeObligationProjection",
        keyword_name="needs_review_child_order_ids",
        loaded_name="needs_review_children",
    )


@pytest.mark.parametrize(
    ("relative_path", "function_name", "object_name", "exit_kind"),
    [
        ("store/memory.py", "stage_envelope_action", "obligation", ast.Raise),
        ("store/sqlite.py", "stage_envelope_action", "obligation", ast.Raise),
        (
            "store/memory.py",
            "_envelope_claim_block_reason_unlocked",
            "exact",
            ast.Return,
        ),
        (
            "store/sqlite.py",
            "_envelope_submission_block_reason_locked",
            "exact",
            ast.Return,
        ),
    ],
    ids=["memory-stage", "sqlite-stage", "memory-final", "sqlite-final"],
)
def test_t1_3_needs_review_child_order_ids_has_distinct_executable_consumers(
    relative_path, function_name, object_name, exit_kind
):
    """Each store's stage and final-claim choke is an executable guard."""

    assert _function_has_attribute_guard(
        _app_source(relative_path),
        function_name=function_name,
        object_name=object_name,
        attribute_name="needs_review_child_order_ids",
        exit_kind=exit_kind,
    )


@pytest.mark.parametrize(
    ("relative_path", "function_name", "call_name"),
    [
        (
            "store/memory.py",
            "_same_symbol_buy_may_execute_unlocked",
            "_same_symbol_buy_execution_exposure_ids_unlocked",
        ),
        (
            "store/sqlite.py",
            "_same_symbol_buy_may_execute_locked",
            "_same_symbol_buy_execution_exposure_ids_locked",
        ),
    ],
    ids=["memory", "sqlite"],
)
def test_t1_3_may_execute_order_statuses_has_executable_store_consumers(
    relative_path, function_name, call_name
):
    """Both claim rails pass the total MAY_EXECUTE set to the shared helper."""

    assert _function_call_keyword_is_name(
        _app_source(relative_path),
        function_name=function_name,
        call_name=call_name,
        keyword_name="order_statuses",
        value_name="MAY_EXECUTE_ORDER_STATUSES",
    )


def test_t1_3_ast_predicates_reject_text_only_and_neutered_sites():
    guarded = """
def rail(obligation):
    if obligation.needs_review_child_order_ids:
        raise RuntimeError()
"""
    neutered = """
def rail(obligation):
    # obligation.needs_review_child_order_ids
    if False and obligation.needs_review_child_order_ids:
        raise RuntimeError()
"""
    nested_dead_raise = """
def rail(obligation):
    if obligation.needs_review_child_order_ids:
        if False:
            raise RuntimeError()
"""
    non_blocking_return = """
def rail(exact):
    if exact.needs_review_child_order_ids:
        return None
"""
    dead_guard = """
def rail(obligation):
    return None
    if obligation.needs_review_child_order_ids:
        raise RuntimeError()
"""
    assert _function_has_attribute_guard(
        guarded,
        function_name="rail",
        object_name="obligation",
        attribute_name="needs_review_child_order_ids",
        exit_kind=ast.Raise,
    )
    assert not _function_has_attribute_guard(
        neutered,
        function_name="rail",
        object_name="obligation",
        attribute_name="needs_review_child_order_ids",
        exit_kind=ast.Raise,
    )
    assert not _function_has_attribute_guard(
        nested_dead_raise,
        function_name="rail",
        object_name="obligation",
        attribute_name="needs_review_child_order_ids",
        exit_kind=ast.Raise,
    )
    assert not _function_has_attribute_guard(
        non_blocking_return,
        function_name="rail",
        object_name="exact",
        attribute_name="needs_review_child_order_ids",
        exit_kind=ast.Return,
    )
    assert not _function_has_attribute_guard(
        dead_guard,
        function_name="rail",
        object_name="obligation",
        attribute_name="needs_review_child_order_ids",
        exit_kind=ast.Raise,
    )


def test_t1_3_ast_predicates_require_executable_keyword_values():
    produced = """
def project(needs_review_children):
    return Projection(needs_review_child_order_ids=tuple(needs_review_children))
"""
    text_only = """
from policy import MAY_EXECUTE_ORDER_STATUSES
def consume():
    # order_statuses=MAY_EXECUTE_ORDER_STATUSES
    return helper(order_statuses=frozenset())
"""
    dead_producer = """
def project(needs_review_children):
    return None
    return Projection(needs_review_child_order_ids=tuple(needs_review_children))
"""
    dead_consumer = """
def consume():
    return None
    return helper(order_statuses=MAY_EXECUTE_ORDER_STATUSES)
"""
    assert _function_call_keyword_loads_name(
        produced,
        function_name="project",
        call_name="Projection",
        keyword_name="needs_review_child_order_ids",
        loaded_name="needs_review_children",
    )
    assert not _function_call_keyword_is_name(
        text_only,
        function_name="consume",
        call_name="helper",
        keyword_name="order_statuses",
        value_name="MAY_EXECUTE_ORDER_STATUSES",
    )
    assert not _function_call_keyword_loads_name(
        dead_producer,
        function_name="project",
        call_name="Projection",
        keyword_name="needs_review_child_order_ids",
        loaded_name="needs_review_children",
    )
    assert not _function_call_keyword_is_name(
        dead_consumer,
        function_name="consume",
        call_name="helper",
        keyword_name="order_statuses",
        value_name="MAY_EXECUTE_ORDER_STATUSES",
    )
