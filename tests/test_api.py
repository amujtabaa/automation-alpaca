"""HTTP API smoke tests via FastAPI TestClient (in-memory store injected).

These are synchronous (TestClient drives the app) and IO-free — the injected
store is in-memory.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store.memory import InMemoryStateStore


@pytest.fixture
def client():
    app = create_app(InMemoryStateStore())
    with TestClient(app) as c:
        yield c


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_session_reports_paper_mode_and_flags(client):
    body = client.get("/api/session").json()
    assert body["mode"] == "paper"
    assert body["kill_switch"] is False
    assert body["buys_paused"] is False


def test_session_type_is_computed_live_from_wall_clock_not_stored(client, monkeypatch):
    """session_type has no route to persist it (StateStore.set_session_type
    was removed as dead code) — GET /api/session overlays session_type_for
    live on every read instead, since a single day's session spans all three
    windows as wall-clock time passes."""
    from datetime import datetime, timezone

    regular_hours = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)  # 11:00 ET, Monday
    monkeypatch.setattr("app.api.routes_system.utcnow", lambda: regular_hours)
    assert client.get("/api/session").json()["session_type"] == "regular"

    premarket = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)  # 06:00 ET
    monkeypatch.setattr("app.api.routes_system.utcnow", lambda: premarket)
    assert client.get("/api/session").json()["session_type"] == "pre_market"

    weekend = datetime(2026, 6, 6, 15, 0, tzinfo=timezone.utc)  # Saturday
    monkeypatch.setattr("app.api.routes_system.utcnow", lambda: weekend)
    assert client.get("/api/session").json()["session_type"] is None


def test_watchlist_crud_and_arming(client):
    # Add (normalized + created).
    r = client.post("/api/watchlist", json={"symbol": "aapl"})
    assert r.status_code == 201
    assert r.json()["symbol"] == "AAPL"
    assert r.json()["armed"] is False

    # Upsert arms it (arm/disarm goes through POST).
    r = client.post("/api/watchlist", json={"symbol": "AAPL", "armed": True})
    assert r.json()["armed"] is True

    assert [w["symbol"] for w in client.get("/api/watchlist").json()] == ["AAPL"]

    # Delete.
    assert client.delete("/api/watchlist/AAPL").status_code == 204
    assert client.get("/api/watchlist").json() == []
    assert client.delete("/api/watchlist/AAPL").status_code == 404


def test_readonly_views_are_empty_not_mocked(client):
    assert client.get("/api/candidates").json() == []
    assert client.get("/api/positions").json() == []
    assert client.get("/api/orders").json() == []
    # A symbol with no fills returns a flat position, not a 404.
    flat = client.get("/api/positions/AAPL").json()
    assert flat == {
        "symbol": "AAPL",
        "quantity": 0,
        "cost_basis": 0.0,
        "average_price": None,
        "updated_at": None,
    }
    assert client.get("/api/candidates/does-not-exist").status_code == 404


def test_controls_persist_flags(client):
    assert client.post("/api/controls/kill-switch", json={"engaged": True}).json()[
        "kill_switch"
    ] is True
    assert client.get("/api/session").json()["kill_switch"] is True
    assert client.post("/api/controls/kill-switch", json={"engaged": False}).json()[
        "kill_switch"
    ] is False

    assert client.post("/api/controls/pause-buys").json()["buys_paused"] is True
    assert client.get("/api/session").json()["buys_paused"] is True
    assert client.post("/api/controls/resume-buys").json()["buys_paused"] is False


def test_review_returns_session_with_empty_sections(client):
    body = client.get("/api/review").json()
    assert body["session"] is not None
    assert body["candidates"] == []
    assert body["orders"] == []
    assert body["fills"] == []

    # An unused past date has no session.
    past = client.get("/api/review", params={"date": "2000-01-01"}).json()
    assert past["session"] is None
