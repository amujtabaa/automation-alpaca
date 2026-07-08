"""Phase 6 (P6-C) — minimal actor-audit for the sensitive control commands.

The accepted resolution of the 01_ARCHITECTURE "no auth in beta" vs ADR-005
"command endpoints require actor audit" conflict was a MINIMAL actor-audit: an
optional ``X-Actor`` header (``app.api.deps.get_actor``, default ``operator``)
threaded into the command facade and PERSISTED on the sensitive control command's
audit event — an audit LABEL, not authentication (beta stays single-user
localhost; there is no login/token gate).

P6-0 captured + threaded the actor; emergency-reduce already persisted it. P6-C
persists it on the ``/api/controls/*`` surface: kill-switch and pause/resume-buys.
A direct (non-facade) store call records the ``COMMAND_ACTOR_SYSTEM`` default.
"""

from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from app.models import EventType
from app.store.base import COMMAND_ACTOR_SYSTEM
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _app():
    store = InMemoryStateStore()
    await store.initialize()
    app = create_app(store)
    app.state.store = store
    app.state.settings = Settings()
    return app, store


def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def _latest_payload(store, event_type: EventType) -> dict:
    events = await store.list_events(event_type=event_type.value)
    assert events, f"no {event_type.value} audit event was written"
    return events[-1].payload


# --------------------------------------------------------------------------- #
# Direct store call: records the COMMAND_ACTOR_SYSTEM default (internal caller).
# --------------------------------------------------------------------------- #
async def test_direct_store_kill_switch_records_system_actor():
    store = InMemoryStateStore()
    await store.initialize()
    await store.set_kill_switch(True)
    payload = await _latest_payload(store, EventType.KILL_SWITCH_ENGAGED)
    assert payload["actor"] == COMMAND_ACTOR_SYSTEM


async def test_direct_store_kill_switch_accepts_explicit_actor():
    store = InMemoryStateStore()
    await store.initialize()
    await store.set_kill_switch(True, actor="alice")
    assert (await _latest_payload(store, EventType.KILL_SWITCH_ENGAGED))["actor"] == "alice"
    await store.set_buys_paused(True, actor="bob")
    assert (await _latest_payload(store, EventType.BUYS_PAUSED))["actor"] == "bob"


# --------------------------------------------------------------------------- #
# Through the facade/route: the resolved X-Actor is persisted; default operator.
# --------------------------------------------------------------------------- #
async def test_kill_switch_route_persists_default_operator_actor():
    app, store = await _app()
    async with _client(app) as client:
        resp = await client.post("/api/controls/kill-switch")
    assert resp.status_code == 200
    payload = await _latest_payload(store, EventType.KILL_SWITCH_ENGAGED)
    assert payload["actor"] == "operator"  # DEFAULT_ACTOR when no X-Actor header


async def test_kill_switch_route_persists_x_actor_header():
    app, store = await _app()
    async with _client(app) as client:
        resp = await client.post(
            "/api/controls/kill-switch", headers={"X-Actor": "carol"}
        )
    assert resp.status_code == 200
    assert (await _latest_payload(store, EventType.KILL_SWITCH_ENGAGED))["actor"] == "carol"


async def test_pause_and_resume_routes_persist_x_actor():
    app, store = await _app()
    async with _client(app) as client:
        await client.post("/api/controls/pause-buys", headers={"X-Actor": "dave"})
        await client.post("/api/controls/resume-buys", headers={"X-Actor": "erin"})
    assert (await _latest_payload(store, EventType.BUYS_PAUSED))["actor"] == "dave"
    assert (await _latest_payload(store, EventType.BUYS_RESUMED))["actor"] == "erin"
