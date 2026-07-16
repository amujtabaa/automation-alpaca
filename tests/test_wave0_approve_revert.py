"""Wave 0 — F-002 (first-doc): the approve route must never strand a candidate
at APPROVED with no order and no path forward.

Two guarantees:

1. A post-approval dispatch failure of *any* kind (not just the block/risk
   errors) reverts the candidate to PENDING via ``revert_candidate_approval``.
   Before the fix, ``except _MAPPED_ERRORS`` (which includes
   ``InvalidOrderError``) re-raised without reverting.
2. A malformed ``suggested_limit_price`` (e.g. ``inf``, which passes a bare
   ``inf > 0`` truthiness check) is caught by the pre-check via the shared
   ``limit_price_reason`` predicate *before* approval — 422, candidate stays
   PENDING, never approved into a dead end.
"""

from __future__ import annotations

import math

from fastapi.testclient import TestClient

from app.main import create_app
from app.store.base import InvalidOrderError
from app.store.memory import InMemoryStateStore


def _inject(client: TestClient, **kwargs) -> str:
    payload = {
        "symbol": "AAPL",
        "suggested_quantity": 10,
        "suggested_limit_price": 1.0,
        **kwargs,
    }
    resp = client.post("/api/dev/candidates", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_approve_reverts_on_any_post_approval_dispatch_failure():
    """gate.approve() succeeds (candidate -> APPROVED), then dispatch raises a
    non-block InvalidOrderError. The candidate must roll back to PENDING, not
    strand at APPROVED."""

    store = InMemoryStateStore()
    app = create_app(store)
    with TestClient(app) as client:
        cid = _inject(client)

        orig = store.create_order_for_candidate

        async def failing(candidate_id, **kwargs):
            raise InvalidOrderError("simulated post-approval dispatch failure")

        store.create_order_for_candidate = failing

        resp = client.post(f"/api/candidates/{cid}/approve")
        assert resp.status_code == 409  # InvalidOrderError -> 409

        # Not stranded: reverted to PENDING (still rejectable), no order.
        refreshed = client.get(f"/api/candidates/{cid}").json()
        assert refreshed["status"] == "pending"
        assert refreshed["order_id"] is None
        assert client.get("/api/orders").json() == []

        # And it is genuinely re-actionable afterward.
        store.create_order_for_candidate = orig
        reject = client.post(f"/api/candidates/{cid}/reject")
        assert reject.status_code == 200
        assert reject.json()["status"] == "rejected"


def test_approve_precheck_rejects_non_finite_limit_before_approval():
    """An ``inf`` suggested_limit_price passes ``inf > 0`` but must be caught by
    the pre-check (via limit_price_reason) — 422, and the candidate is never
    approved (stays PENDING)."""

    store = InMemoryStateStore()
    app = create_app(store)
    with TestClient(app) as client:
        cid = _inject(client)
        # The dev schema rejects a non-finite price, so simulate a non-schema
        # producer by writing inf directly onto the stored candidate (same
        # in-memory store instance the app uses).
        store._candidates[cid].suggested_limit_price = math.inf

        resp = client.post(f"/api/candidates/{cid}/approve")
        assert resp.status_code == 422

        # Never approved: still PENDING, no order, not stranded.
        assert client.get(f"/api/candidates/{cid}").json()["status"] == "pending"
        assert client.get("/api/orders").json() == []
