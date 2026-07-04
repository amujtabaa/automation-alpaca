"""HTTP tests for the Phase 7 routes: POST /positions/{symbol}/flatten,
GET /protection, GET /sell-intents, and /review sell-intent inclusion.

Async (httpx ASGI), app state wired by hand (no lifespan -> no background loop).
"""

from __future__ import annotations

import httpx
import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.main import create_app
from app.marketdata.fake import FakeMarketDataFeed
from app.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
)
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _app():
    store = InMemoryStateStore()
    await store.initialize()
    adapter = MockBrokerAdapter()
    market_data = FakeMarketDataFeed()
    app = create_app(store)
    app.state.store = store
    app.state.broker_adapter = adapter
    app.state.market_data = market_data
    app.state.settings = Settings()
    return app, store, adapter, market_data


def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def _hold(store, symbol, qty, avg=10.0):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)


# ---- POST /positions/{symbol}/flatten ------------------------------------- #


async def test_flatten_no_position_409():
    app, store, _, _ = await _app()
    async with _client(app) as client:
        r = await client.post("/api/positions/AAPL/flatten")
    assert r.status_code == 409


async def test_flatten_creates_manual_exit():
    app, store, _, _ = await _app()
    await _hold(store, "AAPL", 100)
    async with _client(app) as client:
        r = await client.post("/api/positions/AAPL/flatten")
    assert r.status_code == 200
    body = r.json()
    assert body["intent"]["reason"] == "manual_flatten"
    assert body["intent"]["status"] == "ordered"
    assert body["intent"]["target_quantity"] == 100
    assert body["order"]["side"] == "sell"
    assert body["order"]["order_type"] == "market"
    assert body["order"]["quantity"] == 100
    assert body["order"]["candidate_id"] is None


async def test_flatten_works_under_kill_switch():
    app, store, _, _ = await _app()
    await _hold(store, "AAPL", 100)
    await store.set_kill_switch(True)
    async with _client(app) as client:
        r = await client.post("/api/positions/AAPL/flatten")
    # D-P2: a human flatten is created even under the kill switch (submission is
    # separately claimable — the claim gate lets MANUAL_FLATTEN through).
    assert r.status_code == 200
    assert r.json()["intent"]["reason"] == "manual_flatten"


async def test_flatten_is_idempotent():
    app, store, _, _ = await _app()
    await _hold(store, "AAPL", 100)
    async with _client(app) as client:
        first = await client.post("/api/positions/AAPL/flatten")
        second = await client.post("/api/positions/AAPL/flatten")
    assert first.status_code == second.status_code == 200
    assert first.json()["intent"]["id"] == second.json()["intent"]["id"]
    sells = [o for o in await store.list_orders() if o.side is OrderSide.SELL]
    assert len(sells) == 1


async def test_flatten_cancels_open_buys():
    app, store, _, _ = await _app()
    await _hold(store, "AAPL", 100)
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    open_buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 50, session_id=session.id
    )
    async with _client(app) as client:
        r = await client.post("/api/positions/AAPL/flatten")
    assert r.status_code == 200
    assert (await store.get_order(open_buy.id)).status is OrderStatus.CANCELED


async def test_flatten_supersedes_unsent_protection_order():
    app, store, _, _ = await _app()
    await _hold(store, "AAPL", 100)
    # An autonomous PROTECTION_FLOOR exit whose order is still CREATED (unsent).
    session = await store.get_current_session()
    prot = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
        session_id=session.id,
    )
    await store.transition_sell_intent(prot.id, SellIntentStatus.APPROVED)
    prot_order = await store.create_order_for_sell_intent(
        prot.id, order_type=OrderType.MARKET
    )
    async with _client(app) as client:
        r = await client.post("/api/positions/AAPL/flatten")
    assert r.status_code == 200
    # The protective order was canceled; a MANUAL_FLATTEN now owns the exit.
    assert (await store.get_order(prot_order.id)).status is OrderStatus.CANCELED
    assert r.json()["intent"]["reason"] == "manual_flatten"


async def test_flatten_supersedes_stranded_protection_intent_without_order():
    # Regression (routes review, major): a stranded PROTECTION_FLOOR intent with
    # NO order (APPROVED, order_id None — e.g. a crash between approve and order)
    # must be superseded so the human flatten still exits, not returned as a no-op.
    app, store, _, _ = await _app()
    await _hold(store, "AAPL", 100)
    session = await store.get_current_session()
    stranded = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
        session_id=session.id,
    )
    await store.transition_sell_intent(stranded.id, SellIntentStatus.APPROVED)
    # Intentionally do NOT create the order — this is the stranded state.
    assert stranded.order_id is None

    async with _client(app) as client:
        r = await client.post("/api/positions/AAPL/flatten")
    assert r.status_code == 200
    # A real MANUAL_FLATTEN exit now exists (not the stranded protective intent).
    assert r.json()["intent"]["reason"] == "manual_flatten"
    assert r.json()["intent"]["id"] != stranded.id
    assert r.json()["order"]["side"] == "sell"
    # The stranded intent was expired to free the dedup.
    assert (await store.get_sell_intent(stranded.id)).status is SellIntentStatus.EXPIRED


async def test_flatten_leaves_live_protection_order_alone():
    # A genuinely LIVE protective exit (order submitted) is returned as-is — the
    # human is told it is already exiting (not double-exited).
    app, store, _, _ = await _app()
    await _hold(store, "AAPL", 100)
    session = await store.get_current_session()
    prot = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
        session_id=session.id,
    )
    await store.transition_sell_intent(prot.id, SellIntentStatus.APPROVED)
    order = await store.create_order_for_sell_intent(prot.id, order_type=OrderType.MARKET)
    # Make the order live at the broker.
    claim = await store.claim_order_for_submission(order.id)
    await store.transition_order(
        claim.order.id, OrderStatus.SUBMITTED, broker_order_id="b-1"
    )
    async with _client(app) as client:
        r = await client.post("/api/positions/AAPL/flatten")
    assert r.status_code == 200
    # Returned as-is — the protective exit is left executing.
    assert r.json()["intent"]["id"] == prot.id
    assert (await store.get_order(order.id)).status is OrderStatus.SUBMITTED


async def test_flatten_bad_symbol_422():
    app, *_ = await _app()
    async with _client(app) as client:
        r = await client.post("/api/positions/@@/flatten")
    assert r.status_code == 422


# ---- GET /protection ------------------------------------------------------ #


async def test_protection_status_breaching():
    app, store, _, market_data = await _app()
    await _hold(store, "AAPL", 100, avg=10.0)  # floor @ 8% = 9.20
    market_data.set_snapshot("AAPL", last_price=9.0, bid=8.9)
    async with _client(app) as client:
        r = await client.get("/api/protection")
    assert r.status_code == 200
    body = r.json()
    assert body["config"]["enabled"] is True
    assert body["config"]["stop_loss_pct"] == pytest.approx(0.08)
    assert body["config"]["protection_active"] is True  # enabled ∧ monitoring on
    pos = next(p for p in body["positions"] if p["symbol"] == "AAPL")
    assert pos["quantity"] == 100
    assert pos["floor_price"] == pytest.approx(9.2)
    assert pos["observed_price"] == pytest.approx(9.0)
    assert pos["breaching"] is True
    assert pos["paused_by_kill_switch"] is False


async def test_protection_status_paused_under_kill_switch():
    app, store, _, market_data = await _app()
    await _hold(store, "AAPL", 100, avg=10.0)
    market_data.set_snapshot("AAPL", last_price=9.0)
    await store.set_kill_switch(True)
    async with _client(app) as client:
        r = await client.get("/api/protection")
    pos = next(p for p in r.json()["positions"] if p["symbol"] == "AAPL")
    assert pos["breaching"] is True
    assert pos["paused_by_kill_switch"] is True


async def test_protection_status_not_breaching_without_snapshot():
    app, store, _, _ = await _app()
    await _hold(store, "AAPL", 100, avg=10.0)
    async with _client(app) as client:
        r = await client.get("/api/protection")
    pos = next(p for p in r.json()["positions"] if p["symbol"] == "AAPL")
    assert pos["breaching"] is False
    assert pos["observed_price"] is None
    assert pos["floor_price"] == pytest.approx(9.2)  # derivable from avg alone


# ---- GET /sell-intents + /review ------------------------------------------ #


async def test_list_sell_intents():
    app, store, _, _ = await _app()
    session = await store.get_current_session()
    await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=10,
        session_id=session.id,
    )
    async with _client(app) as client:
        r = await client.get("/api/sell-intents")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["symbol"] == "AAPL"


async def test_review_includes_sell_intents():
    app, store, _, _ = await _app()
    session = await store.get_current_session()
    await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=10,
        session_id=session.id,
    )
    async with _client(app) as client:
        r = await client.get("/api/review")
    assert r.status_code == 200
    assert len(r.json()["sell_intents"]) == 1
    assert r.json()["sell_intents"][0]["reason"] == "manual_flatten"
