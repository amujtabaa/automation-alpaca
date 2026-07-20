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
from alpaca.trading.enums import OrderSide as AlpacaOrderSide  # noqa: E402

from app.broker.adapter import (  # noqa: E402
    AmbiguousBrokerError,
    BrokerError,
    TerminalBrokerError,
    VenueOrderScope,
)
from app.broker.alpaca_paper import AlpacaPaperAdapter  # noqa: E402
from app.models import Order, OrderSide, OrderStatus, OrderType  # noqa: E402

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


def _ack(order: Order, broker_order_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=broker_order_id,
        client_order_id=order.id,
        symbol=order.symbol,
        side=(
            AlpacaOrderSide.BUY
            if OrderSide(order.side) is OrderSide.BUY
            else AlpacaOrderSide.SELL
        ),
        qty=order.quantity,
        type=order.order_type.value,
        time_in_force="day",
        order_class="simple",
        limit_price=order.limit_price,
        asset_class="us_equity",
        notional=None,
        legs=None,
        extended_hours=False,
        status="new",
        filled_qty=0,
    )


def _mass_order(**kw) -> SimpleNamespace:
    defaults = dict(
        id="venue-order-1",
        client_order_id="local-order-1",
        symbol="AAPL",
        side=AlpacaOrderSide.BUY,
        status="new",
        filled_qty=0,
        qty=10,
        notional=None,
        type="limit",
        order_type=None,
        time_in_force="day",
        order_class="simple",
        limit_price=10.0,
        asset_class="us_equity",
        extended_hours=False,
        legs=None,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


async def _submit_and_capture_request(monkeypatch, *, now: datetime):
    """Submit an order with a mocked client + a fixed 'current time', and
    return the LimitOrderRequest that was actually sent."""

    adapter = _adapter()
    order = _order()
    response = _ack(order, "alpaca-order-1")
    response.extended_hours = now in {_PRE_MARKET, _AFTER_HOURS}
    adapter._client.submit_order = Mock(return_value=response)
    monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: now)

    broker_order_id = await adapter.submit_order(order)

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
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        order = _order(symbol="MSFT", quantity=25, limit_price=410.5)
        adapter._client.submit_order = Mock(return_value=_ack(order, "x"))
        await adapter.submit_order(order)

        (req,) = adapter._client.submit_order.call_args.args
        assert req.symbol == "MSFT"
        assert req.qty == 25
        assert req.limit_price == 410.5

    async def test_client_order_id_is_our_order_id(self, monkeypatch):
        adapter = _adapter()
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        order = _order()
        adapter._client.submit_order = Mock(return_value=_ack(order, "x"))
        await adapter.submit_order(order)

        (req,) = adapter._client.submit_order.call_args.args
        assert req.client_order_id == order.id

    async def test_always_a_limit_day_order(self, monkeypatch):
        from alpaca.trading.enums import OrderType as AlpacaOrderType
        from alpaca.trading.enums import TimeInForce

        adapter = _adapter()
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _PRE_MARKET)

        order = _order()
        response = _ack(order, "x")
        response.extended_hours = True
        adapter._client.submit_order = Mock(return_value=response)
        await adapter.submit_order(order)

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
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        order = _market_sell(symbol="MSFT", quantity=25)
        adapter._client.submit_order = Mock(return_value=_ack(order, "m1"))
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

    @pytest.mark.parametrize("raw_id", [None, "", "   "])
    async def test_success_response_without_concrete_id_is_ambiguous(
        self, monkeypatch, raw_id
    ):
        """A malformed success response follows the post-call quarantine path."""

        adapter = _adapter()
        adapter._client.submit_order = Mock(return_value=SimpleNamespace(id=raw_id))
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        with pytest.raises(AmbiguousBrokerError, match="concrete broker id"):
            await adapter.submit_order(_order())
        adapter._client.submit_order.assert_called_once()

    @pytest.mark.parametrize("raw_id", [None, "", "   "])
    async def test_duplicate_recovery_without_concrete_id_is_ambiguous(
        self, monkeypatch, raw_id
    ):
        """Duplicate lookup cannot turn a missing venue identity into ``'None'``."""

        adapter = _adapter()
        adapter._client.submit_order = Mock(
            side_effect=_api_error(409, "duplicate client_order_id")
        )
        adapter._client.get_order_by_client_id = Mock(
            return_value=SimpleNamespace(id=raw_id)
        )
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        with pytest.raises(AmbiguousBrokerError, match="concrete broker id"):
            await adapter.submit_order(_order())
        adapter._client.get_order_by_client_id.assert_called_once()

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


class TestBrokerIdentityIngress:
    """Every Alpaca response that introduces a venue id uses one canonical gate."""

    @pytest.mark.parametrize("status", ["stopped", "suspended", "done_for_day"])
    async def test_targeted_query_keeps_nonterminal_lifecycle_state_pollable(
        self, status
    ):
        adapter = _adapter()
        adapter._client.get_order_by_client_id = Mock(
            return_value=SimpleNamespace(
                id="venue-order-1",
                client_order_id="local-order-1",
                status=status,
                filled_qty=0,
            )
        )

        update = await adapter.get_order_by_client_order_id("local-order-1")

        assert update is not None
        assert update.status is OrderStatus.SUBMITTED

    async def test_targeted_query_none_without_404_is_failure(self):
        adapter = _adapter()
        adapter._client.get_order_by_client_id = Mock(return_value=None)

        with pytest.raises(BrokerError, match="malformed targeted query"):
            await adapter.get_order_by_client_order_id("local-order-1")

    @pytest.mark.parametrize("ingress", ["submit", "duplicate"])
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("symbol", "MSFT"),
            ("side", AlpacaOrderSide.SELL),
            ("qty", 80),
            ("type", "market"),
            ("time_in_force", "gtc"),
            ("order_class", "bracket"),
            ("limit_price", 999.0),
            ("asset_class", "crypto"),
            ("notional", 1000.0),
            ("legs", [SimpleNamespace(id="leg-1")]),
            ("extended_hours", True),
            ("stop_price", 99.0),
            ("order_type", "market"),
            ("position_intent", "sell_to_open"),
        ],
    )
    async def test_submit_ack_requires_request_scope(
        self, monkeypatch, ingress, field, value
    ):
        order = _order()
        adapter = _adapter()
        response = _ack(order, "venue-order-1")
        setattr(response, field, value)
        if ingress == "submit":
            adapter._client.submit_order = Mock(return_value=response)
        else:
            adapter._client.submit_order = Mock(
                side_effect=_api_error(409, "duplicate client_order_id")
            )
            adapter._client.get_order_by_client_id = Mock(return_value=response)
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        with pytest.raises(AmbiguousBrokerError, match="acknowledgement scope"):
            await adapter.submit_order(order)

    @pytest.mark.parametrize("ingress", ["submit", "duplicate"])
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("status", "future_venue_state"),
            ("filled_qty", None),
            ("filled_qty", -1),
            ("filled_qty", "0.5"),
        ],
    )
    async def test_submit_ack_requires_recognized_nonnegative_whole_state(
        self, monkeypatch, ingress, field, value
    ):
        order = _order()
        adapter = _adapter()
        response = _ack(order, "venue-order-1")
        setattr(response, field, value)
        if ingress == "submit":
            adapter._client.submit_order = Mock(return_value=response)
        else:
            adapter._client.submit_order = Mock(
                side_effect=_api_error(409, "duplicate client_order_id")
            )
            adapter._client.get_order_by_client_id = Mock(return_value=response)
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        with pytest.raises(AmbiguousBrokerError, match="acknowledgement state"):
            await adapter.submit_order(order)

    async def test_submit_ack_allows_broker_overfill_state(self, monkeypatch):
        order = _order(quantity=10)
        adapter = _adapter()
        response = _ack(order, "venue-overfill")
        response.status = "filled"
        response.filled_qty = 12
        adapter._client.submit_order = Mock(return_value=response)
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        assert await adapter.submit_order(order) == "venue-overfill"

    @pytest.mark.parametrize("ingress", ["submit", "duplicate"])
    async def test_market_submit_ack_rejects_a_limit_price(self, monkeypatch, ingress):
        order = _order(order_type=OrderType.MARKET, limit_price=None)
        adapter = _adapter()
        response = _ack(order, "venue-market-1")
        response.limit_price = 99.0
        if ingress == "submit":
            adapter._client.submit_order = Mock(return_value=response)
        else:
            adapter._client.submit_order = Mock(
                side_effect=_api_error(409, "duplicate client_order_id")
            )
            adapter._client.get_order_by_client_id = Mock(return_value=response)
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)

        with pytest.raises(AmbiguousBrokerError, match="acknowledgement scope"):
            await adapter.submit_order(order)

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [("symbol", "MSFT", "symbol"), ("side", "sell", "side")],
    )
    async def test_targeted_query_requires_immutable_scope(self, field, value, message):
        adapter = _adapter()
        response = dict(
            id="venue-order-1",
            client_order_id="local-order-1",
            symbol="AAPL",
            side="buy",
            status="new",
            filled_qty=0,
        )
        response[field] = value
        adapter._client.get_order_by_client_id = Mock(
            return_value=SimpleNamespace(**response)
        )

        with pytest.raises(BrokerError, match=f"mismatched {message}"):
            await adapter.get_order_by_client_order_id(
                "local-order-1",
                expected_symbol="AAPL",
                expected_side=OrderSide.BUY,
            )

    async def test_targeted_query_missing_status_is_broker_error(self):
        adapter = _adapter()
        adapter._client.get_order_by_client_id = Mock(
            return_value=SimpleNamespace(
                id="venue-order-1",
                client_order_id="local-order-1",
                symbol="AAPL",
                side="buy",
                filled_qty=0,
            )
        )

        with pytest.raises(BrokerError, match="missing order status"):
            await adapter.get_order_by_client_order_id(
                "local-order-1",
                expected_symbol="AAPL",
                expected_side=OrderSide.BUY,
            )

    @pytest.mark.parametrize("report", ["orders", "positions"])
    async def test_mass_report_none_is_failure_never_empty(self, report):
        adapter = _adapter()
        if report == "orders":
            adapter._client.get_orders = Mock(return_value=None)
            call = adapter.list_open_orders()
        else:
            adapter._client.get_all_positions = Mock(return_value=None)
            call = adapter.list_positions()

        with pytest.raises(BrokerError, match="malformed"):
            await call

    @pytest.mark.parametrize("raw_quantity", ["-1", "nan", "inf"])
    async def test_open_order_report_rejects_invalid_quantity(self, raw_quantity):
        adapter = _adapter()
        adapter._client.get_orders = Mock(
            return_value=[_mass_order(filled_qty=raw_quantity)]
        )

        with pytest.raises(BrokerError, match="malformed quantity"):
            await adapter.list_open_orders()

    async def test_open_order_report_surfaces_external_fractional_quantity(self):
        # WO-0113 / managed-ingress contract: a valid unmanaged fractional row
        # is observable external truth. It must not abort the whole mass report;
        # exact managed scope correlation rejects it later if it claims our id.
        adapter = _adapter()
        adapter._client.get_orders = Mock(
            return_value=[
                _mass_order(
                    id="external-fractional",
                    client_order_id="external-client",
                    qty="0.9",
                    filled_qty="0.4",
                )
            ]
        )

        [report] = await adapter.list_open_orders()

        assert report.quantity == 0.9
        assert report.filled_quantity == 0.4

    async def test_open_order_report_surfaces_valid_unmanaged_advanced_scope(self):
        adapter = _adapter()
        adapter._client.get_orders = Mock(
            return_value=[
                _mass_order(
                    id="external-bracket",
                    client_order_id="external-client",
                    qty=None,
                    notional="250.00",
                    type="stop_limit",
                    order_type="stop_limit",
                    time_in_force="gtc",
                    order_class="bracket",
                    asset_class="crypto",
                    limit_price=None,
                    extended_hours=True,
                    legs=[SimpleNamespace(id="leg-1")],
                    stop_price="95.0",
                )
            ]
        )

        [report] = await adapter.list_open_orders()

        assert report.quantity is None
        assert report.quantity_mode == "notional"
        assert report.order_type == "stop_limit"
        assert report.time_in_force == "gtc"
        assert report.order_class == "bracket"
        assert report.asset_class == "crypto"
        assert report.has_legs is True
        assert report.advanced_fields == ("stop_price",)

    async def test_open_order_report_preserves_replace_predecessor(self):
        adapter = _adapter()
        adapter._client.get_orders = Mock(
            return_value=[_mass_order(replaces="  predecessor-broker  ")]
        )

        [report] = await adapter.list_open_orders()

        assert report.replaces_broker_order_id == "predecessor-broker"

    async def test_open_order_report_rejects_unknown_side(self):
        adapter = _adapter()
        adapter._client.get_orders = Mock(return_value=[_mass_order(side="garbage")])

        with pytest.raises(BrokerError, match="malformed order side"):
            await adapter.list_open_orders()

    @pytest.mark.parametrize("status", ["filled", "canceled", "rejected"])
    async def test_open_order_report_rejects_terminal_status(self, status):
        adapter = _adapter()
        adapter._client.get_orders = Mock(return_value=[_mass_order(status=status)])

        with pytest.raises(BrokerError, match="terminal order status"):
            await adapter.list_open_orders()

    @pytest.mark.parametrize("duplicate_key", ["broker", "client"])
    async def test_open_order_report_rejects_duplicate_identity(self, duplicate_key):
        adapter = _adapter()
        first = _mass_order()
        second = _mass_order(
            id="venue-order-1" if duplicate_key == "broker" else "venue-order-2",
            client_order_id=(
                "local-order-2" if duplicate_key == "broker" else "local-order-1"
            ),
            symbol="MSFT",
            side=AlpacaOrderSide.SELL,
        )
        adapter._client.get_orders = Mock(return_value=[first, second])

        with pytest.raises(BrokerError, match="duplicate identity"):
            await adapter.list_open_orders()

    @pytest.mark.parametrize("raw_quantity", ["0.9", "nan", "inf"])
    async def test_position_report_rejects_non_whole_or_nonfinite_quantity(
        self, raw_quantity
    ):
        adapter = _adapter()
        adapter._client.get_all_positions = Mock(
            return_value=[
                SimpleNamespace(symbol="AAPL", qty=raw_quantity, avg_entry_price="10.0")
            ]
        )

        with pytest.raises(BrokerError, match="malformed quantity"):
            await adapter.list_positions()

    async def test_position_report_preserves_integral_short_quantity(self):
        adapter = _adapter()
        adapter._client.get_all_positions = Mock(
            return_value=[
                SimpleNamespace(symbol="AAPL", qty="-3", avg_entry_price="10.0")
            ]
        )

        [position] = await adapter.list_positions()
        assert position.quantity == -3

    @pytest.mark.parametrize("raw_price", ["0", "-1", "nan", "inf", "garbage"])
    async def test_position_report_rejects_invalid_average_price(self, raw_price):
        adapter = _adapter()
        adapter._client.get_all_positions = Mock(
            return_value=[
                SimpleNamespace(symbol="AAPL", qty="10", avg_entry_price=raw_price)
            ]
        )

        with pytest.raises(BrokerError, match="malformed average price"):
            await adapter.list_positions()

    async def test_position_report_rejects_duplicate_canonical_symbol(self):
        adapter = _adapter()
        adapter._client.get_all_positions = Mock(
            return_value=[
                SimpleNamespace(symbol="AAPL", qty="20", avg_entry_price="10.0"),
                SimpleNamespace(symbol=" aapl ", qty="10", avg_entry_price="10.0"),
            ]
        )

        with pytest.raises(BrokerError, match="duplicate symbol"):
            await adapter.list_positions()

    @pytest.mark.parametrize("ingress", ["submit", "duplicate", "targeted_query"])
    @pytest.mark.parametrize("raw_client_id", [None, "", "different-local-order"])
    async def test_response_client_identity_must_match_request(
        self, monkeypatch, ingress, raw_client_id
    ):
        order = _order()
        adapter = _adapter()
        response = SimpleNamespace(
            id="venue-order-1",
            client_order_id=raw_client_id,
            status="new",
            filled_qty=0,
        )
        if ingress == "submit":
            adapter._client.submit_order = Mock(return_value=response)
            monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
            call = adapter.submit_order(order)
        elif ingress == "duplicate":
            adapter._client.submit_order = Mock(
                side_effect=_api_error(409, "duplicate client_order_id")
            )
            adapter._client.get_order_by_client_id = Mock(return_value=response)
            monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
            call = adapter.submit_order(order)
        else:
            adapter._client.get_order_by_client_id = Mock(return_value=response)
            call = adapter.get_order_by_client_order_id(order.id)

        with pytest.raises(AmbiguousBrokerError, match="client_order_id"):
            await call

    @pytest.mark.parametrize("raw_id", [None, "", "   "])
    async def test_targeted_query_without_concrete_id_is_ambiguous(self, raw_id):
        adapter = _adapter()
        adapter._client.get_order_by_client_id = Mock(
            return_value=SimpleNamespace(id=raw_id, status="new", filled_qty=0)
        )

        with pytest.raises(AmbiguousBrokerError, match="concrete broker id"):
            await adapter.get_order_by_client_order_id("local-order-1")

    async def test_targeted_query_returns_trimmed_concrete_id(self):
        adapter = _adapter()
        adapter._client.get_order_by_client_id = Mock(
            return_value=SimpleNamespace(
                id="  venue-order-1  ",
                client_order_id="local-order-1",
                status="new",
                filled_qty=0,
            )
        )

        update = await adapter.get_order_by_client_order_id("local-order-1")

        assert update is not None
        assert update.broker_order_id == "venue-order-1"

    @pytest.mark.parametrize("raw_id", [None, "", "   "])
    async def test_mass_report_without_concrete_id_is_ambiguous(self, raw_id):
        adapter = _adapter()
        adapter._client.get_orders = Mock(return_value=[_mass_order(id=raw_id)])

        with pytest.raises(AmbiguousBrokerError, match="concrete broker id"):
            await adapter.list_open_orders()

    async def test_mass_report_returns_trimmed_concrete_id(self):
        adapter = _adapter()
        adapter._client.get_orders = Mock(
            return_value=[_mass_order(id="  venue-order-1  ")]
        )

        [report] = await adapter.list_open_orders()

        assert report.broker_order_id == "venue-order-1"

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
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        order = _order()
        adapter._client.get_order_by_client_id = Mock(
            return_value=_ack(order, "existing-broker-id")
        )
        assert await adapter.submit_order(order) == "existing-broker-id"
        adapter._client.get_order_by_client_id.assert_called_once_with(order.id)

    async def test_fresh_submit_rejects_replace_lineage_before_venue(self, monkeypatch):
        adapter = _adapter()
        order = _order()
        adapter._client.submit_order = Mock(return_value=_ack(order, "never-called"))
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        scope = VenueOrderScope(
            client_order_id=order.id,
            symbol=order.symbol,
            side=OrderSide(order.side),
            quantity=order.quantity,
            order_type=OrderType(order.order_type),
            limit_price=order.limit_price,
            extended_hours=False,
            replaces_broker_order_id="predecessor-1",
        )

        with pytest.raises(BrokerError, match="contradicts rendered"):
            await adapter.submit_order(order, venue_scope=scope)

        adapter._client.submit_order.assert_not_called()

    async def test_legacy_dynamic_targeted_market_rejects_extended_hours(self):
        adapter = _adapter()
        order = _order(
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            limit_price=None,
        )
        response = _ack(order, "venue-market-legacy")
        response.extended_hours = True
        adapter._client.get_order_by_client_id = Mock(return_value=response)

        with pytest.raises(BrokerError, match="acknowledgement scope"):
            await adapter.get_order_by_client_order_id(
                order.id,
                expected_symbol=order.symbol,
                expected_side=OrderSide.SELL,
                expected_quantity=order.quantity,
                expected_time_in_force="day",
                expected_order_class="simple",
                allow_dynamic_market_sell=True,
            )

    async def test_duplicate_but_lookup_fails_is_ambiguous(self, monkeypatch):
        # WO-0113 late root-class audit: duplicate proves a prior venue order
        # exists, while lookup failure leaves its identity/state unknowable. The
        # envelope producer previously treated Terminal as REJECTED and lost all
        # ownership, so this must take ambiguity quarantine/targeted reconcile.
        adapter = _adapter()
        adapter._client.submit_order = Mock(
            side_effect=_api_error(422, "duplicate client_order_id")
        )
        adapter._client.get_order_by_client_id = Mock(
            side_effect=ConnectionError("lookup failed")
        )
        monkeypatch.setattr("app.broker.alpaca_paper.utcnow", lambda: _REGULAR)
        with pytest.raises(AmbiguousBrokerError):
            await adapter.submit_order(_order())
