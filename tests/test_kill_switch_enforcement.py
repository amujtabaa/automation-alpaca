"""Kill-switch / pause-buys enforcement on the order path (SEC-1/ARCH-1).

Phase 4 wires the Rule 8 safety controls into the backend order boundary: with
the kill switch engaged (or buys paused) no new order intent is created and the
monitoring loop holds all submissions — enforced in the store/loop, not the UI,
and audited. Covered at the store, API, and loop levels.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.broker.mock import MockBrokerAdapter
from app.main import create_app
from app.models import CandidateStatus, OrderStatus
from app.monitoring import _submit_pending_orders
from app.store.base import OrderIntentBlockedError
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _approved(store, *, symbol="AAPL", qty=10, limit=1.0):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return candidate


async def _created_order(store, **kw):
    candidate = await _approved(store, **kw)
    return await store.create_order_for_candidate(candidate.id)


# --------------------------------------------------------------------------- #
# Store boundary: create_order_for_candidate refuses blocked intent
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "engage, reason",
    [("kill_switch", "kill_switch"), ("buys_paused", "buys_paused")],
)
async def test_order_creation_blocked_by_safety_control(any_store, engage, reason):
    candidate = await _approved(any_store)
    if engage == "kill_switch":
        await any_store.set_kill_switch(True)
    else:
        await any_store.set_buys_paused(True)

    with pytest.raises(OrderIntentBlockedError):
        await any_store.create_order_for_candidate(candidate.id)

    # No order created; candidate stays APPROVED (rejectable / dispatchable once
    # the control is released); the block is audited with its reason.
    assert await any_store.list_orders() == []
    assert (
        await any_store.get_candidate(candidate.id)
    ).status is CandidateStatus.APPROVED
    assert any(
        e.event_type == "order_intent_blocked" and e.payload.get("reason") == reason
        for e in await any_store.list_events()
    )


async def test_order_creation_allowed_after_release(any_store):
    candidate = await _approved(any_store)
    await any_store.set_kill_switch(True)
    with pytest.raises(OrderIntentBlockedError):
        await any_store.create_order_for_candidate(candidate.id)
    await any_store.set_kill_switch(False)
    order = await any_store.create_order_for_candidate(candidate.id)
    assert order.status is OrderStatus.CREATED
    assert (
        await any_store.get_candidate(candidate.id)
    ).status is CandidateStatus.ORDERED


# --------------------------------------------------------------------------- #
# API: approve returns 409 and leaves the candidate PENDING (not stranded)
# --------------------------------------------------------------------------- #
@pytest.fixture
def client():
    app = create_app(InMemoryStateStore())
    with TestClient(app) as c:
        yield c


def _inject(client, **kw):
    payload = {
        "symbol": "AAPL",
        "suggested_quantity": 10,
        "suggested_limit_price": 1.0,
        **kw,
    }
    resp = client.post("/api/dev/candidates", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_approve_409_when_kill_switch_engaged_and_stays_pending(client):
    cid = _inject(client)["id"]
    client.post("/api/controls/kill-switch", json={"engaged": True})

    resp = client.post(f"/api/candidates/{cid}/approve")
    assert resp.status_code == 409
    assert "kill_switch" in resp.json()["detail"]
    # Not stranded at APPROVED — still pending, still rejectable.
    assert client.get(f"/api/candidates/{cid}").json()["status"] == "pending"
    assert client.get("/api/orders").json() == []

    # Release and approve succeeds.
    client.post("/api/controls/kill-switch", json={"engaged": False})
    ok = client.post(f"/api/candidates/{cid}/approve")
    assert ok.status_code == 200
    assert ok.json()["status"] == "ordered"


def test_approve_409_when_buys_paused(client):
    cid = _inject(client)["id"]
    client.post("/api/controls/pause-buys")
    resp = client.post(f"/api/candidates/{cid}/approve")
    assert resp.status_code == 409
    assert "buys_paused" in resp.json()["detail"]


# --------------------------------------------------------------------------- #
# Monitoring loop: holds CREATED orders while a control is active
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("engage", ["kill_switch", "buys_paused"])
async def test_loop_holds_submission_while_active_then_submits(any_store, engage):
    order = await _created_order(any_store)  # created while controls were off
    if engage == "kill_switch":
        await any_store.set_kill_switch(True)
    else:
        await any_store.set_buys_paused(True)

    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    # Held: not submitted, stays CREATED, broker never called, audited once.
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED
    assert adapter.submitted == []
    blocked = [
        e
        for e in await any_store.list_events()
        if e.event_type == "order_submission_blocked" and e.order_id == order.id
    ]
    assert len(blocked) == 1

    # A second held tick does not spam another block event.
    await _submit_pending_orders(any_store, adapter)
    blocked = [
        e
        for e in await any_store.list_events()
        if e.event_type == "order_submission_blocked" and e.order_id == order.id
    ]
    assert len(blocked) == 1

    # Release -> the order submits on the next tick.
    if engage == "kill_switch":
        await any_store.set_kill_switch(False)
    else:
        await any_store.set_buys_paused(False)
    await _submit_pending_orders(any_store, adapter)
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.SUBMITTED
    assert [o.id for o in adapter.submitted] == [order.id]
