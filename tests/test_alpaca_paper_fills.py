"""AlpacaPaperAdapter fill-sourcing — single scalar-delta scheme (CHAOS-2 fix).

The adapter imports the ``alpaca`` SDK, so this module is skipped where the SDK
isn't installed (the standard suite stays import-safe without alpaca-py).

CHAOS-2 / DATA-1 from the Codex review: the prior code mixed two fill-identity
schemes (per-execution activity ids vs synthetic cumulative-level ids), which
could record the *same* shares twice under different ids when the activities API
flapped. The fix uses ONE id scheme — ``<broker_order_id>:<cumulative>`` deltas —
which makes a double-count structurally impossible.
"""

from __future__ import annotations

import pytest

pytest.importorskip("alpaca")

from app.broker.alpaca_paper import AlpacaPaperAdapter, _resolve_fill_price  # noqa: E402

pytestmark = pytest.mark.anyio


def _adapter() -> AlpacaPaperAdapter:
    # TradingClient construction is offline (no network); paper=True is hardcoded.
    return AlpacaPaperAdapter("fake-key", "fake-secret")


async def test_get_fills_emits_delta_and_never_double_counts():
    a = _adapter()

    # First 40 of 100.
    f1 = await a._get_fills(
        broker_order_id="b1",
        filled_qty=40,
        recorded_quantity=0,
        filled_avg_price=2.0,
        limit_price=2.0,
    )
    assert [(x.source_fill_id, x.quantity) for x in f1] == [("b1:40", 40)]

    # Same cumulative level re-observed -> nothing (cannot double-count the 40).
    f2 = await a._get_fills(
        broker_order_id="b1",
        filled_qty=40,
        recorded_quantity=40,
        filled_avg_price=2.0,
        limit_price=2.0,
    )
    assert f2 == []

    # Advance to fully filled -> only the incremental 60, new stable id.
    f3 = await a._get_fills(
        broker_order_id="b1",
        filled_qty=100,
        recorded_quantity=40,
        filled_avg_price=2.0,
        limit_price=2.0,
    )
    assert [(x.source_fill_id, x.quantity) for x in f3] == [("b1:100", 60)]


async def test_get_fills_nothing_when_unfilled():
    a = _adapter()
    f = await a._get_fills(
        broker_order_id="b1",
        filled_qty=0,
        recorded_quantity=0,
        filled_avg_price=None,
        limit_price=2.0,
    )
    assert f == []


async def test_get_fills_price_falls_back_to_limit():
    a = _adapter()
    f = await a._get_fills(
        broker_order_id="b1",
        filled_qty=10,
        recorded_quantity=0,
        filled_avg_price=None,
        limit_price=3.5,
    )
    assert f[0].price == 3.5


def test_resolve_fill_price_prefers_avg_then_limit_then_zero():
    assert _resolve_fill_price(2.0, 3.0) == 2.0
    assert _resolve_fill_price(None, 3.0) == 3.0
    assert _resolve_fill_price(None, None) == 0.0
    # Tolerant of the SDK's string/Decimal shapes; an unparseable avg falls back.
    assert _resolve_fill_price("not-a-number", 3.0) == 3.0


def test_pending_cancel_maps_to_non_terminal_state():
    from app.broker.alpaca_paper import _map_status
    from app.models import OrderStatus

    # CHAOS-1: pending_cancel is NOT terminal, so the order keeps being polled.
    assert _map_status("pending_cancel") is OrderStatus.CANCEL_PENDING
    assert _map_status("canceled") is OrderStatus.CANCELED
    assert _map_status("filled") is OrderStatus.FILLED


def test_held_and_calculated_map_to_submitted():
    from app.broker.alpaca_paper import _map_status
    from app.models import OrderStatus

    # F4: real Alpaca statuses, mapped so they don't hit the unknown-status path.
    assert _map_status("held") is OrderStatus.SUBMITTED
    assert _map_status("calculated") is OrderStatus.SUBMITTED
