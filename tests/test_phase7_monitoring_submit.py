"""Phase 7 §5.4 / §5.5 / §7 — the monitoring submit + reconcile paths for
protective sells.

- §5.4: a protective MARKET sell's order type is (re)decided at SUBMISSION —
  MARKET in regular hours, downgraded to a live-priced LIMIT in pre/after-hours,
  held when it can't be priced. The persisted order stays MARKET (the downgrade
  is a per-submit rendering).
- §5.5: a SELL always releases SUBMITTING->CREATED on a submit failure (never
  CANCELED), even in a closed session — it stays submittable (unlike a BUY).
- §7 fill-price fallback helper (`_snapshot_fill_fallback`).
"""

from __future__ import annotations

import pytest

import app.monitoring as monitoring
from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.monitoring import _snapshot_fill_fallback, _submit_pending_orders
from app.protection import ProtectionConfig, protective_limit_price

pytestmark = pytest.mark.anyio


async def _protective_sell(
    store, *, reason=SellReason.PROTECTION_FLOOR, symbol="AAPL", qty=100, price=10.0
):
    """A CREATED protective/flatten SELL order (MARKET) backed by a real position."""
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, price, session_id=session.id
    )
    # The seed buy is still CREATED (append_fill never transitions the order);
    # move it terminal so it isn't itself picked up by _submit_pending_orders.
    # The fill is append-only, so the position survives the cancel.
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    si = await store.create_sell_intent(
        symbol=symbol, reason=reason, target_quantity=qty, session_id=session.id
    )
    await store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    order = await store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    return si, order


def _regular(monkeypatch):
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)


def _premarket(monkeypatch):
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.PRE_MARKET)


# ---- §5.4: order-type re-derivation at submission ------------------------- #


async def test_regular_hours_submits_market(store, monkeypatch):
    await store.initialize()
    _regular(monkeypatch)
    _, order = await _protective_sell(store)
    adapter, md = MockBrokerAdapter(), FakeMarketDataFeed()

    await _submit_pending_orders(store, adapter, Settings(), market_data=md)

    assert len(adapter.submitted) == 1
    assert adapter.submitted[0].order_type is OrderType.MARKET
    assert adapter.submitted[0].limit_price is None
    assert (await store.get_order(order.id)).status is OrderStatus.SUBMITTED


async def test_premarket_downgrades_to_limit(store, monkeypatch):
    await store.initialize()
    _premarket(monkeypatch)
    _, order = await _protective_sell(store)
    adapter, md = MockBrokerAdapter(), FakeMarketDataFeed()
    md.set_snapshot("AAPL", last_price=9.0, bid=8.9)
    settings = Settings()

    await _submit_pending_orders(store, adapter, settings, market_data=md)

    assert len(adapter.submitted) == 1
    sent = adapter.submitted[0]
    assert sent.order_type is OrderType.LIMIT
    expected = protective_limit_price(
        await md.get_snapshot("AAPL"),
        ProtectionConfig(limit_buffer_pct=settings.protection_limit_buffer_pct),
    )
    assert sent.limit_price == pytest.approx(expected)
    # The PERSISTED order stays MARKET — the downgrade is a per-submit rendering.
    assert (await store.get_order(order.id)).order_type is OrderType.MARKET
    assert (await store.get_order(order.id)).status is OrderStatus.SUBMITTED


async def test_premarket_unpriceable_holds(store, monkeypatch):
    await store.initialize()
    _premarket(monkeypatch)
    _, order = await _protective_sell(store)
    adapter, md = MockBrokerAdapter(), FakeMarketDataFeed()  # no snapshot for AAPL

    await _submit_pending_orders(store, adapter, Settings(), market_data=md)

    # Never sent; released back to CREATED to retry a later tick.
    assert adapter.submitted == []
    assert (await store.get_order(order.id)).status is OrderStatus.CREATED


async def test_premarket_stale_snapshot_holds(store, monkeypatch):
    await store.initialize()
    _premarket(monkeypatch)
    _, order = await _protective_sell(store)
    adapter, md = MockBrokerAdapter(), FakeMarketDataFeed()
    md.set_snapshot("AAPL", last_price=9.0, bid=8.9, stale=True)

    await _submit_pending_orders(store, adapter, Settings(), market_data=md)

    # A stale feed can't price a marketable limit safely -> held.
    assert adapter.submitted == []
    assert (await store.get_order(order.id)).status is OrderStatus.CREATED


async def test_premarket_no_market_data_handle_holds(store, monkeypatch):
    await store.initialize()
    _premarket(monkeypatch)
    _, order = await _protective_sell(store)
    adapter = MockBrokerAdapter()

    # market_data=None (a degraded config) -> can't price pre/after-hours -> hold.
    await _submit_pending_orders(store, adapter, Settings(), market_data=None)

    assert adapter.submitted == []
    assert (await store.get_order(order.id)).status is OrderStatus.CREATED


# ---- §5.5: side-aware transient release ----------------------------------- #


async def test_sell_releases_to_created_on_submit_failure_in_closed_session(
    store, monkeypatch
):
    await store.initialize()
    _regular(monkeypatch)
    _, order = await _protective_sell(store, reason=SellReason.PROTECTION_FLOOR)
    # Close the session: the CREATED SELL survives, its ORDERED intent untouched.
    await store.close_session()
    assert (await store.get_order(order.id)).status is OrderStatus.CREATED

    adapter, md = MockBrokerAdapter(), FakeMarketDataFeed()
    adapter.fail_next_submit(BrokerError("transient"))

    await _submit_pending_orders(store, adapter, Settings(), market_data=md)

    # §5.5: a SELL ALWAYS releases to CREATED (never CANCELED), even closed —
    # it is legitimately submittable post-close and retries next tick.
    assert (await store.get_order(order.id)).status is OrderStatus.CREATED


async def test_buy_cancels_on_submit_failure_in_closed_session(store, monkeypatch):
    await store.initialize()
    _regular(monkeypatch)
    session = await store.get_current_session()
    from app.models import CandidateStatus

    cand = await store.create_candidate(
        "MSFT", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)

    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))

    # Claim happens while the session is OPEN (so it isn't blocked), but the
    # session closes before the submit failure is handled — reproduced by closing
    # right after the claim. Simplest deterministic proxy: patch get_session_by_id
    # to report the own session as CLOSED at release time.
    real_get = store.get_session_by_id

    async def closed_view(sid):
        s = await real_get(sid)
        if s is not None:
            s = s.model_copy(deep=True)
            from app.models import SessionStatus

            s.status = SessionStatus.CLOSED
        return s

    monkeypatch.setattr(store, "get_session_by_id", closed_view)

    await _submit_pending_orders(store, adapter, Settings(), market_data=None)

    # A BUY keeps D-013a's no-zombie CANCELED when its own session is closed.
    assert (await store.get_order(order.id)).status is OrderStatus.CANCELED


# ---- §7: fill-price fallback helper --------------------------------------- #


async def test_snapshot_fill_fallback():
    md = FakeMarketDataFeed()
    md.set_snapshot("AAPL", last_price=12.5, bid=12.4)
    assert await _snapshot_fill_fallback(md, "AAPL") == pytest.approx(12.5)

    md.set_snapshot("STALE", last_price=12.5, stale=True)
    assert await _snapshot_fill_fallback(md, "STALE") is None

    md.set_snapshot("BADPX", last_price=0.0)
    assert await _snapshot_fill_fallback(md, "BADPX") is None

    assert await _snapshot_fill_fallback(md, "UNKNOWN") is None
    assert await _snapshot_fill_fallback(None, "AAPL") is None
