"""Approve/dispatch atomicity under a control toggle (Item 2 / D-013).

If the kill switch (or pause-buys) flips between the approve route's pre-check
and the store handoff, the store refuses the order but the candidate is already
APPROVED — stranded APPROVED with no order under a safety stop. The route now
rolls the approval back to PENDING via ``revert_candidate_approval``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import CandidateStatus
from app.store.base import OrderIntentBlockedError
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _approved(store, **kw):
    await store.initialize()
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0, **kw
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return candidate


# --------------------------------------------------------------------------- #
# Store-level: revert recovers a stranded APPROVED candidate
# --------------------------------------------------------------------------- #
async def test_revert_recovers_stranded_approved(any_store):
    candidate = await _approved(any_store)
    await any_store.set_kill_switch(True)  # the race: stop after approve

    with pytest.raises(OrderIntentBlockedError):
        await any_store.create_order_for_candidate(candidate.id)
    assert (
        await any_store.get_candidate(candidate.id)
    ).status is CandidateStatus.APPROVED  # stranded

    reverted = await any_store.revert_candidate_approval(candidate.id)
    assert reverted.status is CandidateStatus.PENDING
    assert reverted.approved_at is None
    assert reverted.order_id is None
    assert await any_store.list_orders() == []
    assert any(
        e.event_type == "candidate_transition"
        and e.candidate_id == candidate.id
        and e.payload.get("reason") == "dispatch_blocked"
        for e in await any_store.list_events()
    )

    # Back to a clean PENDING state: still rejectable.
    await any_store.transition_candidate(candidate.id, CandidateStatus.REJECTED)
    assert (
        await any_store.get_candidate(candidate.id)
    ).status is CandidateStatus.REJECTED


async def test_revert_is_noop_on_ordered_candidate(any_store):
    candidate = await _approved(any_store)  # kill switch off
    order = await any_store.create_order_for_candidate(candidate.id)  # -> ORDERED
    events_before = len(await any_store.list_events())

    reverted = await any_store.revert_candidate_approval(candidate.id)
    # Must NOT disturb a genuinely ordered candidate.
    assert reverted.status is CandidateStatus.ORDERED
    assert reverted.order_id == order.id
    assert len(await any_store.list_events()) == events_before  # no spurious event


async def test_revert_is_noop_on_pending_candidate(any_store):
    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    events_before = len(await any_store.list_events())

    reverted = await any_store.revert_candidate_approval(candidate.id)
    assert reverted.status is CandidateStatus.PENDING
    assert len(await any_store.list_events()) == events_before


# --------------------------------------------------------------------------- #
# Route-level: the race interleaving ends PENDING + 409, never stranded
# --------------------------------------------------------------------------- #
def test_approve_race_reverts_to_pending_and_returns_409():
    store = InMemoryStateStore()
    app = create_app(store)
    with TestClient(app) as client:
        resp = client.post(
            "/api/dev/candidates",
            json={
                "symbol": "AAPL",
                "suggested_quantity": 10,
                "suggested_limit_price": 1.0,
            },
        )
        assert resp.status_code == 201
        cid = resp.json()["id"]

        # Simulate the race: flip the kill switch in the gap between the route's
        # pre-check (passes — switch still off) and the dispatch, by wrapping the
        # store's handoff to engage it immediately before the real call.
        orig = store.create_order_for_candidate

        async def racing(candidate_id, **kwargs):
            await store.set_kill_switch(True)
            return await orig(candidate_id, **kwargs)

        store.create_order_for_candidate = racing

        approve = client.post(f"/api/candidates/{cid}/approve")
        assert approve.status_code == 409

        # Not stranded: rolled back to PENDING, no order created.
        assert client.get(f"/api/candidates/{cid}").json()["status"] == "pending"
        assert client.get("/api/orders").json() == []
