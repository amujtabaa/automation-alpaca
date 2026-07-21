"""WO-0122 pins for CI oracle coverage and store lock liveness."""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from app.models import OrderSide, OrderStatus
from app.store.base import FLATTEN_CREATED

pytestmark = pytest.mark.anyio

_ROOT = Path(__file__).resolve().parents[1]
_CI = _ROOT / ".github" / "workflows" / "ci.yml"
_STORE_FILES = (
    _ROOT / "app" / "store" / "memory.py",
    _ROOT / "app" / "store" / "sqlite.py",
)


def test_ci_runs_r2_conformance_oracle_without_replacing_full_suite() -> None:
    workflow = _CI.read_text(encoding="utf-8")

    assert "python -m pytest -q tests/r2_conformance_oracle.py" in workflow
    assert "pytest --cov=app --cov-branch --cov-report=term-missing" in workflow


def _is_self_lock(expr: ast.expr) -> bool:
    return (
        isinstance(expr, ast.Attribute)
        and isinstance(expr.value, ast.Name)
        and expr.value.id == "self"
        and expr.attr == "_lock"
    )


class _AwaitCollector(ast.NodeVisitor):
    """Collect awaits executed in the current block, excluding nested callables."""

    def __init__(self) -> None:
        self.awaits: list[ast.Await] = []

    def visit_Await(self, node: ast.Await) -> None:  # noqa: N802 - ast visitor API
        self.awaits.append(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        return


def _awaits_under_store_lock(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncWith):
            continue
        if not any(_is_self_lock(item.context_expr) for item in node.items):
            continue
        collector = _AwaitCollector()
        for statement in node.body:
            collector.visit(statement)
        violations.extend(
            f"{path.name}:{await_node.lineno}: {ast.unparse(await_node.value)}"
            for await_node in collector.awaits
        )
    return violations


@pytest.mark.parametrize("store_path", _STORE_FILES, ids=lambda path: path.stem)
def test_inv052_store_lock_contains_no_awaits(store_path: Path) -> None:
    """A broker/network await cannot hide among synchronous local lock helpers."""

    assert _awaits_under_store_lock(store_path) == []


async def _seed_flattenable_position(store) -> None:
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        session_id=session.id,
    )
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        10,
        10.0,
        session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)


async def test_inv051_composite_store_call_never_reenters_lock(any_store) -> None:
    """A nested public lock acquisition turns this bounded probe into a timeout."""

    await _seed_flattenable_position(any_store)
    result = await asyncio.wait_for(any_store.flatten_position("AAPL"), timeout=1.0)

    assert result.outcome == FLATTEN_CREATED
