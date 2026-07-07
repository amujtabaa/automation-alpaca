"""Spine v2 Phase 4 wave 4a — broker adapter reconciliation reports (§7).

Additive/inert: the mass order-status report (`list_open_orders`) + position report
(`list_positions`) the reconciliation engine will consume. Nothing calls them yet.
Pins the mock/sim seed + failure semantics, incl. the §7 safeguards that a FAILED
report must never be read as "no open orders" / "flat" (it raises, not returns empty).
"""

from __future__ import annotations

import pytest

from app.broker.adapter import (
    BrokerError,
    BrokerFill,
    BrokerOrderReport,
    BrokerOrderUpdate,
    BrokerPositionReport,
)
from app.broker.mock import MockBrokerAdapter
from app.broker.sim import SimBrokerAdapter
from app.models import Order, OrderSide, OrderStatus, utcnow

pytestmark = pytest.mark.anyio


def _adapters():
    return [MockBrokerAdapter(), SimBrokerAdapter()]


def _order(**kw) -> Order:
    defaults = dict(
        candidate_id="c1", symbol="AAPL", side=OrderSide.BUY, quantity=10, limit_price=2.0
    )
    defaults.update(kw)
    return Order(**defaults)


@pytest.mark.parametrize("adapter", _adapters())
async def test_open_orders_report_default_empty(adapter):
    assert await adapter.list_open_orders() == []
    assert adapter.open_order_report_queries == 1


@pytest.mark.parametrize("adapter", _adapters())
async def test_open_orders_report_returns_seeded(adapter):
    rows = [
        BrokerOrderReport(
            broker_order_id="b1", client_order_id="o1", symbol="AAPL",
            side=OrderSide.SELL, status=OrderStatus.SUBMITTED, filled_quantity=0,
        ),
        BrokerOrderReport(
            broker_order_id="b2", client_order_id=None, symbol="MSFT",
            side=OrderSide.BUY, status=OrderStatus.PARTIALLY_FILLED, filled_quantity=5,
        ),
    ]
    adapter.seed_open_orders(rows)
    got = await adapter.list_open_orders()
    assert got == rows
    # A client_order_id=None row models an external/unmanaged venue order.
    assert got[1].client_order_id is None


@pytest.mark.parametrize("adapter", _adapters())
async def test_positions_report_returns_seeded(adapter):
    rows = [BrokerPositionReport(symbol="AAPL", quantity=100, average_price=10.5)]
    adapter.seed_positions(rows)
    assert await adapter.list_positions() == rows
    assert adapter.position_report_queries == 1


@pytest.mark.parametrize("adapter", _adapters())
async def test_open_orders_failure_raises_never_empty(adapter):
    # §7 safeguard: a failed report must NOT be read as "no open orders".
    adapter.seed_open_orders(
        [BrokerOrderReport("b1", "o1", "AAPL", OrderSide.SELL, OrderStatus.SUBMITTED, 0)]
    )
    adapter.fail_next_open_orders(BrokerError("report down"))
    with pytest.raises(BrokerError):
        await adapter.list_open_orders()
    # Recovers on the next call (one-shot failure), returning the real set.
    assert len(await adapter.list_open_orders()) == 1


@pytest.mark.parametrize("adapter", _adapters())
async def test_positions_failure_raises_never_flat(adapter):
    # §7 safeguard: a failed position query must NEVER be read as flat.
    adapter.seed_positions([BrokerPositionReport("AAPL", 100, 10.0)])
    adapter.fail_next_positions(BrokerError("positions down"))
    with pytest.raises(BrokerError):
        await adapter.list_positions()
    assert len(await adapter.list_positions()) == 1


async def test_reports_are_isolated_copies():
    # Mutating the returned list must not corrupt the adapter's seeded state.
    adapter = MockBrokerAdapter()
    adapter.seed_open_orders(
        [BrokerOrderReport("b1", "o1", "AAPL", OrderSide.SELL, OrderStatus.SUBMITTED, 0)]
    )
    got = await adapter.list_open_orders()
    got.clear()
    assert len(await adapter.list_open_orders()) == 1


# --------------------------------------------------------------------------- #
# Wave 4e-3 E5 fidelity — an UNSEEDED list_open_orders derives from known-live
# submits, so a locally-open managed order is never spuriously absent from the
# adapter's own mass report (which would drive a false not-found → reject).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("adapter", _adapters())
async def test_unseeded_derives_the_submitted_live_order(adapter):
    order = _order(symbol="MSFT", side=OrderSide.SELL)
    bid = await adapter.submit_order(order)
    got = await adapter.list_open_orders()
    assert len(got) == 1
    r = got[0]
    assert r.broker_order_id == bid
    assert r.client_order_id == order.id      # matches the local order id
    assert r.symbol == "MSFT"
    assert r.side is OrderSide.SELL
    assert r.status is OrderStatus.SUBMITTED
    assert r.filled_quantity == 0


@pytest.mark.parametrize("adapter", _adapters())
async def test_unseeded_excludes_a_terminal_order(adapter):
    order = _order()
    await adapter.submit_order(order)
    adapter.set_response_for_order(
        order.id,
        BrokerOrderUpdate(OrderStatus.FILLED, 10, [BrokerFill("e1", 10, 2.0, utcnow())]),
    )
    # A filled order is no longer venue-open → excluded from the derived report.
    assert await adapter.list_open_orders() == []


@pytest.mark.parametrize("adapter", _adapters())
async def test_fresh_adapter_derives_empty(adapter):
    # No submits → nothing known-live → empty (the wave-4a default is preserved).
    assert await adapter.list_open_orders() == []


async def test_explicit_seed_overrides_derivation():
    adapter = MockBrokerAdapter()
    await adapter.submit_order(_order())   # a live order that WOULD derive
    adapter.seed_open_orders([])            # explicit empty seed wins (models a drop)
    assert await adapter.list_open_orders() == []


async def test_sim_derivation_tracks_consumed_script():
    adapter = SimBrokerAdapter()
    order = _order()
    bid = await adapter.submit_order(order)
    adapter.script(
        order.id,
        [
            BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 4,
                              [BrokerFill("e1", 4, 2.0, utcnow())]),
            BrokerOrderUpdate(OrderStatus.FILLED, 10,
                              [BrokerFill("e2", 6, 2.0, utcnow())]),
        ],
    )
    # Before any poll the script is unconsumed → falls back to the default SUBMITTED.
    assert (await adapter.list_open_orders())[0].status is OrderStatus.SUBMITTED
    await adapter.get_order_status(bid)     # consume #1 → PARTIALLY_FILLED
    r = await adapter.list_open_orders()
    assert r[0].status is OrderStatus.PARTIALLY_FILLED and r[0].filled_quantity == 4
    await adapter.get_order_status(bid)     # consume #2 → FILLED (terminal)
    assert await adapter.list_open_orders() == []
