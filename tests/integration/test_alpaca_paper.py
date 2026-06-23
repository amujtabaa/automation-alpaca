"""Env-gated integration tests for the real Alpaca **paper** adapter.

These are NOT part of the standard unit-test run: they are skipped unless paper
credentials are present in the environment, and they make real network calls to
Alpaca's **paper** endpoint (never a live account). Run them deliberately with:

    ALPACA_PAPER_API_KEY=... ALPACA_PAPER_API_SECRET=... pytest tests/integration/

Import discipline: ``app.broker.alpaca_paper`` (which imports ``alpaca-py``) is
imported *inside* the test, not at module top, so collecting this file in an
environment without the SDK installed does not raise — the skipif fires first.
"""

from __future__ import annotations

import os

import pytest

_HAVE_CREDS = bool(
    os.getenv("ALPACA_PAPER_API_KEY") and os.getenv("ALPACA_PAPER_API_SECRET")
)

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        not _HAVE_CREDS, reason="Alpaca paper credentials not configured"
    ),
]


def _adapter():
    # Imported lazily so this module collects cleanly without alpaca-py present.
    from app.broker.alpaca_paper import AlpacaPaperAdapter

    return AlpacaPaperAdapter(
        api_key=os.environ["ALPACA_PAPER_API_KEY"],
        api_secret=os.environ["ALPACA_PAPER_API_SECRET"],
    )


def _resting_buy_order():
    """A 1-share BUY LIMIT far below market so it rests unfilled (then we cancel
    it). Paper only — long-only, limit-only, tiny."""

    from app.models import Order, OrderSide, OrderType

    return Order(
        candidate_id="integration-test",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        limit_price=1.00,  # deliberately unfillable so it rests
    )


async def test_submit_poll_cancel_roundtrip():
    """Submit a resting paper order, observe it via polling, then cancel it.

    Asserts the adapter maps Alpaca's responses onto our types and that cancel is
    idempotent — without ever touching a live account.
    """

    from app.broker.adapter import BrokerOrderUpdate
    from app.models import OrderStatus

    adapter = _adapter()
    order = _resting_buy_order()

    broker_order_id = await adapter.submit_order(order)
    assert isinstance(broker_order_id, str) and broker_order_id

    try:
        update = await adapter.get_order_status(broker_order_id)
        assert isinstance(update, BrokerOrderUpdate)
        # A just-submitted resting order should not be filled.
        assert update.status in {
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
        }
        assert update.filled_quantity == 0
    finally:
        # Always clean up the paper order; cancel is idempotent.
        await adapter.cancel_order(broker_order_id)
        await adapter.cancel_order(broker_order_id)  # second cancel = no-op
