"""WO-0019a — the broker-adapter replace/edit seam.

The envelope executor's cancel/replace path (WO-0019) needs a venue-side
atomic replace: one round-trip, no window with zero resting orders or two
live ones. Contract mirrors ``submit_order``: non-empty NEW broker id or a
classified error (transient / terminal / ambiguous per ADR-002), with a
deterministic ``client_order_id`` on the replacement so an ambiguous outcome
is reconcilable by the existing targeted query — never blind-retried.

The Alpaca tests mock the SDK client and assert the REAL SDK method name
(``replace_order_by_id``) is invoked — the X-002 regression pattern from
work/review/FINDING-alpaca-adapter-wrong-sdk-method.md.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import (
    AmbiguousBrokerError,
    BrokerAdapter,
    BrokerError,
    BrokerFill,
    BrokerOrderUpdate,
    TerminalBrokerError,
)
from app.broker.mock import MockBrokerAdapter
from app.broker.sim import SimBrokerAdapter
from app.models import Order, OrderSide, OrderStatus, OrderType, utcnow

pytestmark = pytest.mark.anyio


def make_order(**kw) -> Order:
    defaults = dict(
        candidate_id="c1",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=10.50,
    )
    defaults.update(kw)
    return Order(**defaults)


# --- the seam itself ---------------------------------------------------------- #


def test_replace_order_is_part_of_the_abstract_contract():
    assert "replace_order" in BrokerAdapter.__abstractmethods__


# --- MockBrokerAdapter --------------------------------------------------------- #


async def test_mock_replace_mints_a_new_id_and_terminates_the_old(any_broker=None):
    mock = MockBrokerAdapter()
    order = make_order()
    old_id = await mock.submit_order(order)

    new_id = await mock.replace_order(
        old_id, client_order_id="repl-1", limit_price=10.25, quantity=8
    )
    assert new_id and new_id.strip() and new_id != old_id
    assert mock.replaced == [(old_id, "repl-1", 10.25, 8)]

    # The old venue order is terminal (Alpaca marks it replaced; our status
    # vocabulary maps that to CANCELED) and its observed fills are preserved.
    old = await mock.get_order_status(old_id)
    assert old.status is OrderStatus.CANCELED

    # The replacement is discoverable by its deterministic client id — the
    # ADR-002 recovery path for an ambiguous replace.
    found = await mock.get_order_by_client_order_id("repl-1")
    assert found is not None
    assert found.broker_order_id == new_id
    assert found.status is OrderStatus.SUBMITTED


async def test_mock_replace_preserves_partial_fills_on_the_old_order():
    mock = MockBrokerAdapter()
    order = make_order()
    old_id = await mock.submit_order(order)
    fill = BrokerFill(source_fill_id="x1", quantity=4, price=10.60, filled_at=utcnow())
    mock.set_response(
        old_id, BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 4, [fill])
    )

    await mock.replace_order(old_id, client_order_id="repl-2", limit_price=10.30)
    old = await mock.get_order_status(old_id)
    assert old.status is OrderStatus.CANCELED
    assert old.filled_quantity == 4
    assert old.fills == [fill]  # the partial is never lost


async def test_mock_fail_next_replace_raises_then_clears():
    mock = MockBrokerAdapter()
    old_id = await mock.submit_order(make_order())
    mock.fail_next_replace(AmbiguousBrokerError("504 mid-replace"))
    with pytest.raises(AmbiguousBrokerError):
        await mock.replace_order(old_id, client_order_id="repl-3")
    # Cleared: the retry (same client id — idempotent identity) succeeds.
    new_id = await mock.replace_order(old_id, client_order_id="repl-3")
    assert new_id


# --- SimBrokerAdapter (chaos-injectable like submit/cancel) --------------------- #


async def test_sim_replace_chaos_predicate_fires_then_recovers():
    sim = SimBrokerAdapter()
    old_id = await sim.submit_order(make_order())
    sim.fail_replace_when(
        lambda broker_order_id, call_index: (
            AmbiguousBrokerError("flaky venue") if call_index == 0 else None
        )
    )
    with pytest.raises(AmbiguousBrokerError):
        await sim.replace_order(old_id, client_order_id="repl-s1")
    new_id = await sim.replace_order(old_id, client_order_id="repl-s1")
    assert new_id and new_id != old_id


# --- AlpacaPaperAdapter (mocked SDK; X-002-proof method-name assertions) --------- #


class TestAlpacaReplace:
    @staticmethod
    def _adapter_and_mock():
        pytest.importorskip("alpaca")
        from types import SimpleNamespace
        from unittest.mock import Mock

        from app.broker.alpaca_paper import AlpacaPaperAdapter

        adapter = AlpacaPaperAdapter("fake-key", "fake-secret")
        client = Mock()
        client.replace_order_by_id = Mock(
            return_value=SimpleNamespace(id="new-venue-id")
        )
        adapter._client = client
        return adapter, client

    @staticmethod
    def _api_error(status_code: int, message: str = "rejected"):
        from types import SimpleNamespace

        from alpaca.common.exceptions import APIError

        http_error = SimpleNamespace(response=SimpleNamespace(status_code=status_code))
        return APIError('{"message": "%s"}' % message, http_error=http_error)

    async def test_invokes_the_real_sdk_method_with_a_replace_request(self):
        adapter, client = self._adapter_and_mock()
        new_id = await adapter.replace_order(
            "venue-1", client_order_id="repl-a1", limit_price=10.25, quantity=8
        )
        assert new_id == "new-venue-id"
        # X-002 regression: the REAL SDK name, with the request carrying the
        # deterministic client_order_id + the new bounds.
        assert client.replace_order_by_id.call_count == 1
        args, _ = client.replace_order_by_id.call_args
        assert args[0] == "venue-1"
        req = args[1]
        assert req.client_order_id == "repl-a1"
        assert float(req.limit_price) == 10.25
        assert int(req.qty) == 8

    async def test_definitive_4xx_is_terminal(self):
        adapter, client = self._adapter_and_mock()
        client.replace_order_by_id.side_effect = self._api_error(403, "forbidden")
        with pytest.raises(TerminalBrokerError):
            await adapter.replace_order("venue-1", client_order_id="repl-a2")

    async def test_rate_limit_is_a_plain_transient(self):
        adapter, client = self._adapter_and_mock()
        client.replace_order_by_id.side_effect = self._api_error(429, "slow down")
        with pytest.raises(BrokerError) as exc_info:
            await adapter.replace_order("venue-1", client_order_id="repl-a3")
        assert not isinstance(
            exc_info.value, (TerminalBrokerError, AmbiguousBrokerError)
        )

    async def test_5xx_and_transport_failures_are_ambiguous(self):
        adapter, client = self._adapter_and_mock()
        client.replace_order_by_id.side_effect = self._api_error(504, "gateway")
        with pytest.raises(AmbiguousBrokerError):
            await adapter.replace_order("venue-1", client_order_id="repl-a4")

        adapter2, client2 = self._adapter_and_mock()
        client2.replace_order_by_id.side_effect = TimeoutError("socket timeout")
        with pytest.raises(AmbiguousBrokerError):
            await adapter2.replace_order("venue-1", client_order_id="repl-a5")

    async def test_duplicate_client_id_recovers_the_existing_replacement(self):
        """A crash-then-retry of the SAME replace (same client_order_id) must
        adopt the already-created replacement, never mint a second one."""

        from types import SimpleNamespace
        from unittest.mock import Mock

        adapter, client = self._adapter_and_mock()
        client.replace_order_by_id.side_effect = self._api_error(
            422, "duplicate client_order_id"
        )
        client.get_order_by_client_id = Mock(
            return_value=SimpleNamespace(id="already-created")
        )
        new_id = await adapter.replace_order("venue-1", client_order_id="repl-a6")
        assert new_id == "already-created"
        client.get_order_by_client_id.assert_called_once_with("repl-a6")

    async def test_duplicate_whose_lookup_fails_is_terminal(self):
        from unittest.mock import Mock

        adapter, client = self._adapter_and_mock()
        client.replace_order_by_id.side_effect = self._api_error(
            422, "duplicate client_order_id"
        )
        client.get_order_by_client_id = Mock(side_effect=RuntimeError("down"))
        with pytest.raises(TerminalBrokerError):
            await adapter.replace_order("venue-1", client_order_id="repl-a7")
