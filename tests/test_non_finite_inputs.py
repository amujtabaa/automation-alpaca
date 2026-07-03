"""Non-finite (NaN / Infinity) input rejection at the store + API boundary.

BACKEND-1 from the Codex QA/red-team review: ``NaN``/``Infinity`` slip past a
bare ``<= 0`` guard (``nan <= 0`` and ``inf <= 0`` are both ``False``) and would
poison ``cost_basis``/``average_price`` and persisted order/fill rows. They must
be rejected at the store boundary (D-010), with the API schema rejecting them too.
"""

from __future__ import annotations

import math

import pytest

from app.api.schemas import MockCandidateCreate
from app.models import CandidateStatus, OrderSide
from app.store.base import InvalidFillError, InvalidOrderError

pytestmark = pytest.mark.anyio

_NON_FINITE = [math.nan, math.inf, -math.inf]


async def _order(store, *, symbol="AAPL", qty=100, limit=2.0):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(candidate.id)


@pytest.mark.parametrize("bad_price", _NON_FINITE)
async def test_append_fill_rejects_non_finite_price(any_store, bad_price):
    order = await _order(any_store)
    with pytest.raises(InvalidFillError):
        await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, 10, bad_price)
    # Nothing recorded; position stays flat (no NaN cost basis).
    assert await any_store.list_fills(order_id=order.id) == []
    assert (await any_store.get_position("AAPL")).quantity == 0


@pytest.mark.parametrize("bad_qty", _NON_FINITE)
async def test_append_fill_rejects_non_finite_quantity(any_store, bad_qty):
    order = await _order(any_store)
    with pytest.raises(InvalidFillError):
        await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, bad_qty, 2.0)
    assert await any_store.list_fills(order_id=order.id) == []


@pytest.mark.parametrize("bad_price", _NON_FINITE)
async def test_create_order_rejects_non_finite_limit_price(any_store, bad_price):
    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=bad_price
    )
    await any_store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    with pytest.raises(InvalidOrderError):
        await any_store.create_order_for_candidate(candidate.id)
    # Rejected before any state changed: no order, candidate stays APPROVED.
    assert await any_store.list_orders() == []
    assert (
        await any_store.get_candidate(candidate.id)
    ).status is CandidateStatus.APPROVED


def test_schema_rejects_non_finite_limit_price():
    from pydantic import ValidationError

    for bad in _NON_FINITE:
        with pytest.raises(ValidationError):
            MockCandidateCreate(symbol="AAPL", suggested_limit_price=bad)
    # A finite positive price is still accepted.
    assert MockCandidateCreate(symbol="AAPL", suggested_limit_price=1.5).suggested_limit_price == 1.5
