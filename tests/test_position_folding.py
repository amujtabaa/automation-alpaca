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
    # Buys and sells now go through side-matched orders (D-010); the position
    # still folds across all of the symbol's fills regardless of which order.
    buy_order = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 200
    )
    sell_order = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.SELL, 200
    )

    # order submitted, no fill yet -> position quantity 0
    assert (await store.get_position("AAPL")).quantity == 0

    await store.append_fill(buy_order.id, "AAPL", OrderSide.BUY, 100, 1.00)
    p = await store.get_position("AAPL")
    assert (p.quantity, p.average_price) == (100, pytest.approx(1.00))

    await store.append_fill(buy_order.id, "AAPL", OrderSide.BUY, 100, 2.00)
    p = await store.get_position("AAPL")
    assert (p.quantity, p.average_price) == (200, pytest.approx(1.50))

    await store.append_fill(sell_order.id, "AAPL", OrderSide.SELL, 50, 5.00)
    p = await store.get_position("AAPL")
    assert (p.quantity, p.average_price) == (150, pytest.approx(1.50))

    await store.append_fill(sell_order.id, "AAPL", OrderSide.SELL, 150, 5.00)
    p = await store.get_position("AAPL")
    assert p.quantity == 0 and p.average_price is None


async def test_broker_overfill_is_recorded_and_quarantines_the_symbol(store):
    # Spine v2 wave 3b / ADR-001: a broker-authoritative overfill (a SELL that
    # crosses the long-only position through flat into short) is a FACT to be
    # RECORDED and quarantined, not reject-and-dropped. The oversell goes through
    # a side-matched SELL order so it clears the side-match guard and reaches the
    # overfill branch; selling 101 vs a 100 position is the case under test.
    candidate = await store.create_candidate("AAPL")
    buy_order = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 100
    )
    await store.append_fill(buy_order.id, "AAPL", OrderSide.BUY, 100, 1.00)

    sell_order = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.SELL, 101
    )
    result = await store.append_fill(sell_order.id, "AAPL", OrderSide.SELL, 101, 1.00)
    assert result.status == "appended"

    # The recorded short is projected (broker reality is not hidden) and the
    # symbol is quarantined so autonomous trading cannot resume from it.
    p = await store.get_position("AAPL")
    assert p.quantity == -1
    assert p.average_price is None
    assert len(await store.list_fills(symbol="AAPL")) == 2
    assert "AAPL" in await store.list_quarantined_symbols()

    # The overfill is audit-logged as a quarantine, not silently absorbed.
    quarantines = [
        e
        for e in await store.list_events()
        if e.event_type == "fill_overfill_quarantined"
    ]
    assert len(quarantines) == 1
    assert quarantines[0].payload["attempted_sell"] == 101
    assert quarantines[0].payload["quarantined"] is True
