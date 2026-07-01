"""AlpacaPaperAdapter.submit_order — LimitOrderRequest construction, especially
``extended_hours`` (BACKEND-2, resolved post-Phase-5).

Before this file, ``submit_order``'s request-construction logic had ZERO unit
test coverage — only the env-gated integration test touched it. A real gap,
found during a self-review sweep after fixing the extended_hours bug itself:
the Strategy Engine's premarket_momentum_v1 proposes candidates EXCLUSIVELY
during premarket/after-hours, but submit_order never set extended_hours=True,
so an approved candidate was silently ineligible to fill in the very session
it was proposed for.

The adapter imports the ``alpaca`` SDK, so this module is skipped where the
SDK isn't installed (mirrors test_alpaca_paper_fills.py's precedent).
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

pytest.importorskip("alpaca")

from app.broker.alpaca_paper import AlpacaPaperAdapter  # noqa: E402
from app.models import Order, OrderSide, OrderType  # noqa: E402

pytestmark = pytest.mark.anyio

# 2026-01-07 (Wednesday). ET offsets: EST = UTC-5 in January.
_PRE_MARKET = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)  # 05:00 ET
_REGULAR = datetime(2026, 1, 7, 16, 0, tzinfo=timezone.utc)  # 11:00 ET
_AFTER_HOURS = datetime(2026, 1, 7, 22, 0, tzinfo=timezone.utc)  # 17:00 ET
_OVERNIGHT = datetime(2026, 1, 7, 6, 0, tzinfo=timezone.utc)  # 01:00 ET


def _adapter() -> AlpacaPaperAdapter:
    # TradingClient construction is offline (no network); paper=True is hardcoded.
    return AlpacaPaperAdapter("fake-key", "fake-secret")


def _order(**kw) -> Order:
    defaults = dict(
        candidate_id="c1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=103.5,
    )
    defaults.update(kw)
    return Order(**defaults)


async def _submit_and_capture_request(monkeypatch, *, now: datetime):
    """Submit an order with a mocked client + a fixed 'current time', and
    return the LimitOrderRequest that was actually sent."""

    adapter = _adapter()
    adapter._client.submit_order = Mock(return_value=SimpleNamespace(id="alpaca-order-1"))
    monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: now)

    broker_order_id = await adapter.submit_order(_order())

    assert broker_order_id == "alpaca-order-1"
    adapter._client.submit_order.assert_called_once()
    (request,) = adapter._client.submit_order.call_args.args
    return request


class TestExtendedHours:
    async def test_premarket_sets_extended_hours_true(self, monkeypatch):
        req = await _submit_and_capture_request(monkeypatch, now=_PRE_MARKET)
        assert req.extended_hours is True

    async def test_after_hours_sets_extended_hours_true(self, monkeypatch):
        req = await _submit_and_capture_request(monkeypatch, now=_AFTER_HOURS)
        assert req.extended_hours is True

    async def test_regular_hours_sets_extended_hours_false(self, monkeypatch):
        req = await _submit_and_capture_request(monkeypatch, now=_REGULAR)
        assert req.extended_hours is False

    async def test_overnight_sets_extended_hours_false(self, monkeypatch):
        """No SessionType at all (session_type_for returns None) must not
        raise, and correctly means "not extended-hours-eligible" here — there
        is no session to be extended for."""

        req = await _submit_and_capture_request(monkeypatch, now=_OVERNIGHT)
        assert req.extended_hours is False


class TestRequestConstruction:
    async def test_symbol_quantity_price_carried_through(self, monkeypatch):
        adapter = _adapter()
        adapter._client.submit_order = Mock(return_value=SimpleNamespace(id="x"))
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        order = _order(symbol="MSFT", quantity=25, limit_price=410.5)
        await adapter.submit_order(order)

        (req,) = adapter._client.submit_order.call_args.args
        assert req.symbol == "MSFT"
        assert req.qty == 25
        assert req.limit_price == 410.5

    async def test_client_order_id_is_our_order_id(self, monkeypatch):
        adapter = _adapter()
        adapter._client.submit_order = Mock(return_value=SimpleNamespace(id="x"))
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        order = _order()
        await adapter.submit_order(order)

        (req,) = adapter._client.submit_order.call_args.args
        assert req.client_order_id == order.id

    async def test_always_a_limit_day_order(self, monkeypatch):
        from alpaca.trading.enums import OrderType as AlpacaOrderType
        from alpaca.trading.enums import TimeInForce

        adapter = _adapter()
        adapter._client.submit_order = Mock(return_value=SimpleNamespace(id="x"))
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _PRE_MARKET)

        await adapter.submit_order(_order())

        (req,) = adapter._client.submit_order.call_args.args
        assert req.type == AlpacaOrderType.LIMIT
        assert req.time_in_force == TimeInForce.DAY
