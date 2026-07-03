"""GET /api/marketdata/snapshots (Phase 5) — read-only, no mutating endpoint."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.marketdata.fake import FakeMarketDataFeed
from app.store.memory import InMemoryStateStore


@pytest.fixture
def client():
    app = create_app(InMemoryStateStore())
    with TestClient(app) as c:
        yield c


def test_empty_when_nothing_subscribed(client):
    resp = client.get("/api/marketdata/snapshots")
    assert resp.status_code == 200
    assert resp.json() == []


def test_returns_populated_snapshot(client):
    feed: FakeMarketDataFeed = client.app.state.market_data
    feed.set_snapshot(
        "AAPL", last_price=103.0, bid=102.9, ask=103.1, volume=100_000, prev_close=100.0
    )

    resp = client.get("/api/marketdata/snapshots")

    assert resp.status_code == 200
    [snap] = resp.json()
    assert snap["symbol"] == "AAPL"
    assert snap["last_price"] == 103.0
    assert snap["bid"] == 102.9
    assert snap["ask"] == 103.1
    assert snap["volume"] == 100_000
    assert snap["prev_close"] == 100.0
    assert snap["pct_move"] == pytest.approx(3.0)
    assert snap["stale"] is False
    assert "updated_at" in snap


def test_subscribed_symbol_with_no_data_yet_serializes_nulls(client):
    feed: FakeMarketDataFeed = client.app.state.market_data
    asyncio.run(feed.subscribe(["MSFT"]))

    resp = client.get("/api/marketdata/snapshots")

    assert resp.status_code == 200
    [snap] = resp.json()
    assert snap["symbol"] == "MSFT"
    assert snap["last_price"] is None
    assert snap["bid"] is None
    assert snap["ask"] is None
    assert snap["volume"] is None
    assert snap["prev_close"] is None
    assert snap["pct_move"] is None


def test_pct_move_computed_by_backend_not_cockpit(client):
    """The route computes pct_move (app.features.pct_move) — this is the value
    the Strategy Engine actually decided on; the cockpit only displays it."""

    feed: FakeMarketDataFeed = client.app.state.market_data
    feed.set_snapshot("AAPL", last_price=97.0, prev_close=100.0)

    resp = client.get("/api/marketdata/snapshots")

    [snap] = resp.json()
    assert snap["pct_move"] == pytest.approx(-3.0)
