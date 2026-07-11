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
from unittest.mock import Mock

import pytest

pytest.importorskip("alpaca")

from alpaca.common.exceptions import APIError  # noqa: E402

from app.broker.adapter import (  # noqa: E402
    AmbiguousBrokerError,
    BrokerError,
    TerminalBrokerError,
)
from app.broker.alpaca_paper import AlpacaPaperAdapter  # noqa: E402
from app.models import Order, OrderSide, OrderType  # noqa: E402

pytestmark = pytest.mark.anyio


def _api_error(status_code: int, message: str = "rejected") -> APIError:
    """An ``APIError`` whose read-only ``status_code`` resolves to ``status_code``
    (derived from the SDK's ``http_error.response.status_code``)."""

    http_error = SimpleNamespace(response=SimpleNamespace(status_code=status_code))
    return APIError('{"message": "%s"}' % message, http_error=http_error)


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
    adapter._client.submit_order = Mock(
        return_value=SimpleNamespace(id="alpaca-order-1")
    )
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


def _market_sell(**kw):
    defaults = dict(
        candidate_id=None,
        sell_intent_id="si1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=10,
        limit_price=None,
    )
    defaults.update(kw)
    return Order(**defaults)


class TestMarketOrder:
    """Phase 7 §7: a MARKET order (a protective sell, only ever submitted in
    regular hours by §5.4) becomes a MarketOrderRequest; a MARKET reaching the
    adapter outside regular hours is refused (Rule 12 defensive backstop)."""

    async def test_regular_hours_builds_market_request(self, monkeypatch):
        from alpaca.trading.enums import OrderType as AlpacaOrderType
        from alpaca.trading.enums import TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        adapter = _adapter()
        adapter._client.submit_order = Mock(return_value=SimpleNamespace(id="m1"))
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        order = _market_sell(symbol="MSFT", quantity=25)
        broker_id = await adapter.submit_order(order)

        assert broker_id == "m1"
        (req,) = adapter._client.submit_order.call_args.args
        assert isinstance(req, MarketOrderRequest)
        assert req.type == AlpacaOrderType.MARKET
        assert req.time_in_force == TimeInForce.DAY
        assert req.symbol == "MSFT"
        assert req.qty == 25
        assert req.client_order_id == order.id
        # No limit price on a market request.
        assert getattr(req, "limit_price", None) is None

    @pytest.mark.parametrize("now", [_PRE_MARKET, _AFTER_HOURS, _OVERNIGHT])
    async def test_market_refused_outside_regular_hours(self, monkeypatch, now):
        adapter = _adapter()
        adapter._client.submit_order = Mock(return_value=SimpleNamespace(id="x"))
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: now)

        # The §5.4 submit path must have downgraded to LIMIT; a MARKET reaching
        # here in a limit-only session is a bug -> fail closed, never sent.
        with pytest.raises(BrokerError):
            await adapter.submit_order(_market_sell())
        adapter._client.submit_order.assert_not_called()


class TestSubmitErrorClassification:
    """AIR-003 review: a definitive broker rejection must surface as
    TerminalBrokerError so a stale-SUBMITTING re-drive escalates to needs_review
    instead of livelocking forever; a transient failure stays a plain BrokerError
    (retryable)."""

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
    async def test_definitive_4xx_is_terminal(self, monkeypatch, code):
        adapter = _adapter()
        adapter._client.submit_order = Mock(
            side_effect=_api_error(code, "no buying power")
        )
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        with pytest.raises(TerminalBrokerError):
            await adapter.submit_order(_order())

    async def test_rate_limit_429_is_a_plain_safe_transient(self, monkeypatch):
        # ADR-002 (wave 3c) / conflict C2: a 429 is a PRE-FLIGHT reject — the order
        # provably never reached the book — so it stays a plain BrokerError (safe
        # idempotent redrive), NOT ambiguous. Distinguishing this from 5xx is the
        # whole point: only an ambiguous outcome quarantines.
        adapter = _adapter()
        adapter._client.submit_order = Mock(side_effect=_api_error(429, "slow down"))
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        with pytest.raises(BrokerError) as ei:
            await adapter.submit_order(_order())
        assert not isinstance(ei.value, TerminalBrokerError)
        assert not isinstance(ei.value, AmbiguousBrokerError)  # NOT quarantined

    @pytest.mark.parametrize("code", [500, 502, 503, 504])
    async def test_5xx_is_ambiguous_not_a_plain_transient(self, monkeypatch, code):
        # ADR-002: a 5xx (incl. 504) means the request REACHED Alpaca's servers,
        # which then failed — the order MAY be live. This MUST be AmbiguousBrokerError
        # so the monitoring loop quarantines it instead of blind-redriving (the
        # oversell path). A regression back to plain BrokerError would revive the
        # blind redrive — this pins the classification.
        adapter = _adapter()
        adapter._client.submit_order = Mock(
            side_effect=_api_error(code, "server error")
        )
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        with pytest.raises(AmbiguousBrokerError):
            await adapter.submit_order(_order())

    @pytest.mark.parametrize("exc", [ConnectionError("boom"), TimeoutError("slow")])
    async def test_network_or_timeout_error_is_ambiguous(self, monkeypatch, exc):
        # A transport/timeout failure AFTER the request may have left the process is
        # ambiguous (may be live) -> AmbiguousBrokerError, never blind-redriven.
        adapter = _adapter()
        adapter._client.submit_order = Mock(side_effect=exc)
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        with pytest.raises(AmbiguousBrokerError):
            await adapter.submit_order(_order())

    async def test_duplicate_recovered_returns_existing_id(self, monkeypatch):
        # Idempotency preserved: a duplicate client_order_id whose existing order
        # looks up cleanly returns that broker id (never raises, never re-submits).
        adapter = _adapter()
        adapter._client.submit_order = Mock(
            side_effect=_api_error(409, "duplicate client_order_id")
        )
        # The SDK method is get_order_by_client_id (NOT get_order_by_client_order_id,
        # which does not exist on TradingClient) — mocking the real name is what
        # makes this test actually exercise the recovery path.
        adapter._client.get_order_by_client_id = Mock(
            return_value=SimpleNamespace(id="existing-broker-id")
        )
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        order = _order()
        assert await adapter.submit_order(order) == "existing-broker-id"
        adapter._client.get_order_by_client_id.assert_called_once_with(order.id)

    async def test_duplicate_but_lookup_fails_is_terminal(self, monkeypatch):
        # The broker says duplicate but we cannot confirm the existing order — its
        # fate is unknowable, so a re-drive must escalate, not retry forever.
        adapter = _adapter()
        adapter._client.submit_order = Mock(
            side_effect=_api_error(422, "duplicate client_order_id")
        )
        adapter._client.get_order_by_client_id = Mock(
            side_effect=ConnectionError("lookup failed")
        )
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        with pytest.raises(TerminalBrokerError):
            await adapter.submit_order(_order())
