"""AlpacaPaperAdapter.get_order_status / cancel_order — direct unit coverage.

Both previously had zero direct unit tests: get_order_status's fill-sourcing
internals were tested via _get_fills directly (test_alpaca_paper_fills.py) and
status mapping via _map_status, but the method itself was never exercised
end-to-end; cancel_order had no coverage at all. The adapter imports the
alpaca SDK, so this module is skipped where the SDK isn't installed (mirrors
the sibling files' precedent).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("alpaca")

from alpaca.common.exceptions import APIError  # noqa: E402

from app.broker.adapter import BrokerError  # noqa: E402
from app.broker.alpaca_paper import AlpacaPaperAdapter  # noqa: E402
from app.models import OrderStatus  # noqa: E402

pytestmark = pytest.mark.anyio


def _adapter() -> AlpacaPaperAdapter:
    # TradingClient construction is offline (no network); paper=True is hardcoded.
    return AlpacaPaperAdapter("fake-key", "fake-secret")


def _alpaca_order(**kw):
    defaults = dict(
        id="b1",
        client_order_id="local-order-1",
        symbol="AAPL",
        side="buy",
        status="new",
        qty="100",
        filled_qty="0",
        filled_avg_price=None,
        type="limit",
        time_in_force="day",
        order_class="simple",
        limit_price=2.0,
        asset_class="us_equity",
        notional=None,
        legs=None,
        extended_hours=False,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


class _FakeAPIError(APIError):
    """A real APIError subclass with a controllable status_code.

    The base class derives status_code from an http_error's
    .response.status_code, which is awkward to construct for a test double —
    subclassing keeps the `except APIError` isinstance check honest while
    making the status directly settable.
    """

    def __init__(self, status_code: int) -> None:
        super().__init__("error")
        self._status_code = status_code

    @property
    def status_code(self) -> int:
        return self._status_code


class TestGetOrderStatus:
    @pytest.mark.parametrize("status", ["stopped", "suspended", "done_for_day"])
    async def test_nonterminal_lifecycle_states_remain_pollable(self, status):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(status=status)
        )

        update = await adapter.get_order_status("b1")

        assert update.status is OrderStatus.SUBMITTED

    async def test_unknown_lifecycle_state_fails_closed(self):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(status="future_venue_state")
        )

        with pytest.raises(BrokerError, match="Unrecognised Alpaca order status"):
            await adapter.get_order_status("b1")

    async def test_response_broker_identity_must_match_requested_identity(self):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(id="foreign-broker-id", status="canceled")
        )

        with pytest.raises(BrokerError, match="mismatched broker id"):
            await adapter.get_order_status("expected-broker-id")

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("client_order_id", "foreign-client", "client id"),
            ("symbol", "MSFT", "symbol"),
            ("side", "sell", "side"),
        ],
    )
    async def test_response_immutable_scope_must_match_local_order(
        self, field, value, message
    ):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(**{field: value})
        )

        with pytest.raises(BrokerError, match=f"mismatched {message}"):
            await adapter.get_order_status(
                "b1",
                expected_client_order_id="local-order-1",
                expected_symbol="AAPL",
                expected_side="buy",
            )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("qty", "80"),
            ("limit_price", 999.0),
            ("type", "market"),
            ("time_in_force", "gtc"),
            ("order_class", "bracket"),
        ],
    )
    async def test_response_total_order_scope_must_match(self, field, value):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(**{field: value})
        )

        with pytest.raises(BrokerError, match="acknowledgement scope"):
            await adapter.get_order_status(
                "b1",
                expected_quantity=100,
                expected_limit_price=2.0,
                expected_order_type="limit",
                expected_time_in_force="day",
                expected_order_class="simple",
            )

    @pytest.mark.parametrize("raw_quantity", ["0.9", "-1", "nan", "inf"])
    async def test_rejects_non_whole_or_invalid_filled_quantity(self, raw_quantity):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(filled_qty=raw_quantity)
        )

        with pytest.raises(BrokerError, match="malformed quantity"):
            await adapter.get_order_status("b1")

    async def test_maps_status_and_filled_quantity(self):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(
                status="partially_filled", filled_qty="40", filled_avg_price=2.0
            )
        )

        update = await adapter.get_order_status("b1", recorded_quantity=0)

        assert update.status is OrderStatus.PARTIALLY_FILLED
        assert update.filled_quantity == 40
        adapter._client.get_order_by_id.assert_called_once_with("b1")

    async def test_includes_delta_fill_via_get_fills(self):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(
                status="filled", filled_qty="100", filled_avg_price=2.0
            )
        )

        update = await adapter.get_order_status("b1", recorded_quantity=40)

        assert [(f.source_fill_id, f.quantity) for f in update.fills] == [
            ("b1:100", 60)
        ]

    async def test_already_recorded_quantity_yields_no_new_fills(self):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(
                status="filled", filled_qty="100", filled_avg_price=2.0
            )
        )

        update = await adapter.get_order_status("b1", recorded_quantity=100)

        assert update.fills == []

    async def test_legacy_dynamic_market_rejects_extended_hours(self):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(
                side="sell",
                type="market",
                limit_price=None,
                extended_hours=True,
            )
        )

        with pytest.raises(BrokerError, match="acknowledgement scope"):
            await adapter.get_order_status(
                "b1",
                expected_quantity=100,
                expected_time_in_force="day",
                expected_order_class="simple",
                allow_dynamic_market_sell=True,
            )

    async def test_dynamic_limit_response_requires_current_persisted_scope(self):
        """REV-0033 F2: arbitrary limit prices cannot fill a scope crash gap."""

        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(
            return_value=_alpaca_order(
                side="sell",
                type="limit",
                limit_price=987.65,
                extended_hours=True,
            )
        )

        with pytest.raises(BrokerError, match="acknowledgement scope") as caught:
            await adapter.get_order_status(
                "b1",
                expected_client_order_id="local-order-1",
                expected_symbol="AAPL",
                expected_side="sell",
                expected_quantity=100,
                expected_time_in_force="day",
                expected_order_class="simple",
                allow_dynamic_market_sell=True,
            )
        assert caught.value.__cause__ is not None
        assert "persisted venue scope" in str(caught.value.__cause__)

    async def test_network_failure_raises_brokererror(self):
        adapter = _adapter()
        adapter._client.get_order_by_id = Mock(side_effect=RuntimeError("timeout"))

        with pytest.raises(BrokerError):
            await adapter.get_order_status("b1")


class TestCancelOrder:
    async def test_success_calls_sdk(self):
        adapter = _adapter()
        adapter._client.cancel_order_by_id = Mock(return_value=None)

        await adapter.cancel_order("b1")  # must not raise

        adapter._client.cancel_order_by_id.assert_called_once_with("b1")

    async def test_404_is_a_noop_not_an_error(self):
        """Already gone (e.g. a race with a fill) -> idempotent no-op."""
        adapter = _adapter()
        adapter._client.cancel_order_by_id = Mock(side_effect=_FakeAPIError(404))

        await adapter.cancel_order("b1")  # must not raise

    async def test_422_is_a_noop_not_an_error(self):
        """Already in a terminal state (not cancelable) -> idempotent no-op."""
        adapter = _adapter()
        adapter._client.cancel_order_by_id = Mock(side_effect=_FakeAPIError(422))

        await adapter.cancel_order("b1")  # must not raise

    async def test_other_api_error_status_raises_brokererror(self):
        """A genuine failure (e.g. 500) must NOT be swallowed as a no-op."""
        adapter = _adapter()
        adapter._client.cancel_order_by_id = Mock(side_effect=_FakeAPIError(500))

        with pytest.raises(BrokerError):
            await adapter.cancel_order("b1")

    async def test_network_failure_raises_brokererror(self):
        adapter = _adapter()
        adapter._client.cancel_order_by_id = Mock(side_effect=RuntimeError("timeout"))

        with pytest.raises(BrokerError):
            await adapter.cancel_order("b1")
