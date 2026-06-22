"""Position folding — the average-cost, long-only formula and its guardrail.

Covers the exact minimum cases from docs/02_DATA_AND_PERSISTENCE.md, both at the
pure-function level and through the store, plus the rejected-oversell case.
"""

from __future__ import annotations

import pytest

from app.models import Fill, OrderSide
from app.position import NegativePositionError, fold_fills

pytestmark = pytest.mark.anyio


def _fill(side: OrderSide, qty: int, price: float) -> Fill:
    return Fill(order_id="o1", symbol="AAPL", side=side, quantity=qty, price=price)


def test_fold_pure_function_cases():
    # No fills -> flat.
    p = fold_fills("AAPL", [])
    assert p.quantity == 0 and p.average_price is None

    fills = [_fill(OrderSide.BUY, 100, 1.00)]
    p = fold_fills("AAPL", fills)
    assert p.quantity == 100 and p.average_price == pytest.approx(1.00)

    fills.append(_fill(OrderSide.BUY, 100, 2.00))
    p = fold_fills("AAPL", fills)
    assert p.quantity == 200 and p.average_price == pytest.approx(1.50)

    fills.append(_fill(OrderSide.SELL, 50, 7.77))  # sell price is irrelevant
    p = fold_fills("AAPL", fills)
    assert p.quantity == 150 and p.average_price == pytest.approx(1.50)

    fills.append(_fill(OrderSide.SELL, 150, 0.01))
    p = fold_fills("AAPL", fills)
    assert p.quantity == 0 and p.average_price is None  # flat


def test_fold_rejects_negative():
    with pytest.raises(NegativePositionError):
        fold_fills("AAPL", [_fill(OrderSide.SELL, 1, 1.0)])


async def test_position_folding_through_store(store):
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order(candidate.id, "AAPL", OrderSide.BUY, 200)

    # order submitted, no fill yet -> position quantity 0
    assert (await store.get_position("AAPL")).quantity == 0

    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.00)
    p = await store.get_position("AAPL")
    assert (p.quantity, p.average_price) == (100, pytest.approx(1.00))

    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 2.00)
    p = await store.get_position("AAPL")
    assert (p.quantity, p.average_price) == (200, pytest.approx(1.50))

    await store.append_fill(order.id, "AAPL", OrderSide.SELL, 50, 5.00)
    p = await store.get_position("AAPL")
    assert (p.quantity, p.average_price) == (150, pytest.approx(1.50))

    await store.append_fill(order.id, "AAPL", OrderSide.SELL, 150, 5.00)
    p = await store.get_position("AAPL")
    assert p.quantity == 0 and p.average_price is None


async def test_oversell_is_rejected_with_audit_and_no_negative(store):
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order(candidate.id, "AAPL", OrderSide.BUY, 100)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.00)

    with pytest.raises(NegativePositionError):
        await store.append_fill(order.id, "AAPL", OrderSide.SELL, 101, 1.00)

    # Position is unchanged (no short), and no extra fill row was written.
    p = await store.get_position("AAPL")
    assert p.quantity == 100
    assert len(await store.list_fills(symbol="AAPL")) == 1

    # The rejection is audit-logged, not silent.
    rejects = [
        e for e in await store.list_events()
        if e.event_type == "fill_rejected_negative_position"
    ]
    assert len(rejects) == 1
    assert rejects[0].payload["attempted_sell"] == 101
