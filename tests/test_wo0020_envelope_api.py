"""WO-0020 — the envelope HTTP surface: list / approve / cancel via the typed
facade only (ADR-005 route boundary). Async httpx ASGI, hand-wired app state,
no background loop, no live IO."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.main import create_app
from app.marketdata.fake import FakeMarketDataFeed
from app.models import SellReason, utcnow
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _app():
    store = InMemoryStateStore()
    await store.initialize()
    app = create_app(store)
    app.state.store = store
    app.state.broker_adapter = MockBrokerAdapter()
    app.state.market_data = FakeMarketDataFeed()
    app.state.settings = Settings()
    return app, store


def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


def draft_payload(intent_id: str, **overrides) -> dict:
    base = dict(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=750,
        cancel_replace_budget=5,
        expires_at=(utcnow() + timedelta(hours=2)).isoformat(),
        allowed_session_phases=["regular"],
        expiry_disposition="cancel_and_return",
        stale_data_disposition="cancel",
    )
    base.update(overrides)
    return base


async def _intent(store) -> str:
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return si.id


async def test_approve_then_list_shows_the_active_envelope():
    app, store = await _app()
    intent_id = await _intent(store)
    async with _client(app) as client:
        resp = await client.post(
            "/api/envelopes/approve", json=draft_payload(intent_id)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "active"
        assert body["sell_intent_id"] == intent_id

        listed = await client.get("/api/envelopes")
        assert listed.status_code == 200
        rows = listed.json()
        assert [r["id"] for r in rows] == [body["id"]]
        assert rows[0]["remaining_quantity"] == 100


async def test_approve_without_dispositions_is_rejected_end_to_end():
    app, store = await _app()
    intent_id = await _intent(store)
    async with _client(app) as client:
        for missing in ("expiry_disposition", "stale_data_disposition", "expires_at"):
            payload = draft_payload(intent_id)
            payload.pop(missing)
            resp = await client.post("/api/envelopes/approve", json=payload)
            assert resp.status_code == 422, (missing, resp.text)
        # Nothing leaked through any of the rejected attempts.
        listed = await client.get("/api/envelopes")
        assert listed.json() == []


async def test_approve_under_kill_switch_conflicts():
    app, store = await _app()
    intent_id = await _intent(store)
    await store.set_kill_switch(True, actor="operator-a")
    async with _client(app) as client:
        resp = await client.post(
            "/api/envelopes/approve", json=draft_payload(intent_id)
        )
        assert resp.status_code == 409


async def test_cancel_pre_activation_envelope_and_errors():
    app, store = await _app()
    intent_id = await _intent(store)
    async with _client(app) as client:
        approved = (
            await client.post("/api/envelopes/approve", json=draft_payload(intent_id))
        ).json()
        # An ACTIVE envelope is not cancellable through the gate route (no
        # ACTIVE -> CANCELLED edge) — 409, per the §3 machine.
        conflict = await client.post(f"/api/envelopes/{approved['id']}/cancel")
        assert conflict.status_code == 409
        missing = await client.post("/api/envelopes/nope/cancel")
        assert missing.status_code == 404

    # A pre-activation draft cancels fine.
    from app.models import ExecutionEnvelope

    draft = await store.create_envelope(
        ExecutionEnvelope(
            **{
                **draft_payload(await _intent_other(store), symbol="MSFT"),
                "expires_at": utcnow() + timedelta(hours=2),
            }
        )
    )
    async with _client(app) as client:
        resp = await client.post(f"/api/envelopes/{draft.id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


async def _intent_other(store) -> str:
    si = await store.create_sell_intent(
        symbol="MSFT", reason=SellReason.PROTECTION_FLOOR, target_quantity=50
    )
    return si.id
