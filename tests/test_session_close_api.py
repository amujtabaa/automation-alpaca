"""D-007 at the HTTP layer: POST /api/session/close and review date-scoping.

Async tests drive the ASGI app with httpx while holding the same in-memory
store reference (same event loop) to set up fills the public API can't yet
create. Proves the closed-session review reads the point-in-time snapshot, not
today's live fold.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.models import OrderSide
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _app_client():
    store = InMemoryStateStore()
    await store.initialize()
    app = create_app(store)
    app.state.store = store  # ASGITransport doesn't run the lifespan
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return client, store


async def test_close_endpoint_returns_closed_then_409_on_second_close():
    client, _ = await _app_client()
    async with client:
        first = await client.post("/api/session/close")
        assert first.status_code == 200
        assert first.json()["status"] == "closed"

        second = await client.post("/api/session/close")
        assert second.status_code == 409


async def test_review_closed_returns_snapshot_active_returns_live():
    client, store = await _app_client()
    async with client:
        session = await store.get_current_session()
        candidate = await store.create_candidate("AAPL", session_id=session.id)
        # Order sized for both buy fills (cumulative 200): the first fills 100
        # before close, the second (post-close) moves the live fold to 200.
        order = await store.create_order(
            candidate.id, "AAPL", OrderSide.BUY, 200, session_id=session.id
        )
        await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0,
                                session_id=session.id)

        date = session.session_date

        # Active session -> live derived positions.
        active = (await client.get("/api/review", params={"date": date})).json()
        assert active["session"]["status"] == "active"
        assert active["positions"][0]["quantity"] == 100

        # Close, then add another fill that moves the LIVE fold to 200.
        assert (await client.post("/api/session/close")).status_code == 200
        await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0,
                                session_id=session.id)

        closed = (await client.get("/api/review", params={"date": date})).json()
        assert closed["session"]["status"] == "closed"
        # Point-in-time: the snapshot says 100, even though live is now 200.
        assert [p["symbol"] for p in closed["positions"]] == ["AAPL"]
        assert closed["positions"][0]["quantity"] == 100
        # Fills are scoped to this session.
        assert len(closed["fills"]) == 2


async def test_get_session_between_close_and_review_keeps_snapshots_visible():
    """D-009 regression: a GET /api/session call between close and review must
    not spawn a second same-date session that hides the close-time snapshots.

    This interleaving is exactly what the original test above never exercises —
    it goes close -> review without the GET /api/session that Session Control
    issues on every render.
    """

    client, store = await _app_client()
    async with client:
        session = await store.get_current_session()
        candidate = await store.create_candidate("AAPL", session_id=session.id)
        order = await store.create_order(
            candidate.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
        )
        await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0,
                                session_id=session.id)
        date = session.session_date

        assert (await client.post("/api/session/close")).status_code == 200

        # The call that used to create a second active session for today.
        sess = (await client.get("/api/session")).json()
        assert sess["status"] == "closed"
        assert sess["id"] == session.id

        review = (await client.get("/api/review", params={"date": date})).json()
        assert review["session"]["status"] == "closed"
        assert review["session"]["id"] == session.id
        # Snapshots captured at close are still visible by date.
        assert [p["symbol"] for p in review["positions"]] == ["AAPL"]
        assert review["positions"][0]["quantity"] == 100
