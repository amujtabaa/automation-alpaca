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
    BrokerOrderReport,
    BrokerPositionReport,
)
from app.broker.mock import MockBrokerAdapter
from app.broker.sim import SimBrokerAdapter
from app.models import OrderSide, OrderStatus

pytestmark = pytest.mark.anyio


def _adapters():
    return [MockBrokerAdapter(), SimBrokerAdapter()]


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
