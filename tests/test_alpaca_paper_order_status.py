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
        status="new", filled_qty="0", filled_avg_price=None, limit_price=2.0
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
