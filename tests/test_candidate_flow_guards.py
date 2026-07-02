"""Regression tests for the guards added after the independent Phase 3 review.

- **M1** — the approve endpoint must not strand a candidate at ``approved``:
  a candidate that cannot be sized into an order (no positive
  ``suggested_quantity``) is rejected up front (422) and stays ``pending`` and
  rejectable, instead of being approved into a state the candidate machine can
  only leave via ``ordered`` or session-close expiry.
- **M3** — the DEV/MOCK injection router is gated by ``ENABLE_DEV_ROUTES`` so a
  deployment can keep it off (it is on by default in beta).
- **M4** — the dev endpoint refuses to inject candidates into a *closed* session.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.approval.human import HumanApprovalGate
from app.config import Settings
from app.main import create_app
from app.models import CandidateStatus
from app.store.memory import InMemoryStateStore


# --------------------------------------------------------------------------- #
# M1 — approve never strands a candidate at `approved`
# --------------------------------------------------------------------------- #
# A candidate with no `suggested_quantity` cannot be created through the dev
# endpoint (it enforces qty > 0), so this drives the app over ASGI with such a
# candidate seeded directly in the store — all within one event loop so the
# in-memory store's lock stays bound to a single loop.


@pytest.mark.anyio
async def test_approve_non_dispatchable_candidate_422_and_recoverable():
    store = InMemoryStateStore()
    await store.initialize()
    app = create_app(store)
    # Lifespan isn't run under ASGITransport, so wire app.state explicitly.
    app.state.store = store
    app.state.approval_gate = HumanApprovalGate(store)
    app.state.settings = Settings()

    candidate = await store.create_candidate("AAPL")  # no suggested_quantity
    assert candidate.suggested_quantity is None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t"
    ) as ac:
        # Up-front rejection — not approved into a dead end.
        resp = await ac.post(f"/api/candidates/{candidate.id}/approve")
        assert resp.status_code == 422

        # It stayed PENDING ...
        got = await ac.get(f"/api/candidates/{candidate.id}")
        assert got.json()["status"] == "pending"
        # ... and is therefore still rejectable (the strand is gone).
        assert (await ac.post(f"/api/candidates/{candidate.id}/reject")).status_code == 200
        # No order was ever created.
        assert (await ac.get("/api/orders")).json() == []


# --------------------------------------------------------------------------- #
# M3 — the dev router is gated by ENABLE_DEV_ROUTES
# --------------------------------------------------------------------------- #


def test_dev_routes_present_by_default():
    app = create_app(InMemoryStateStore())
    with TestClient(app) as client:
        # Default beta config mounts the dev router.
        assert client.post("/api/dev/candidates", json={"symbol": "AAPL"}).status_code == 201


def test_dev_routes_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_DEV_ROUTES", "false")
    app = create_app(InMemoryStateStore())
    with TestClient(app) as client:
        # With dev routes off, the path is simply not mounted -> 404.
        assert client.post("/api/dev/candidates", json={"symbol": "AAPL"}).status_code == 404
        # The real candidate endpoints are unaffected.
        assert client.get("/api/candidates").status_code == 200


# --------------------------------------------------------------------------- #
# M4 — dev injection is refused on a closed session
# --------------------------------------------------------------------------- #


def test_dev_inject_refused_after_session_close():
    app = create_app(InMemoryStateStore())
    with TestClient(app) as client:
        # Injecting into the active session is fine ...
        assert client.post("/api/dev/candidates", json={"symbol": "AAPL"}).status_code == 201
        # ... but once the session is closed, injection is refused.
        assert client.post("/api/session/close").status_code == 200
        resp = client.post("/api/dev/candidates", json={"symbol": "MSFT"})
        assert resp.status_code == 409
        assert "closed" in resp.json()["detail"]


# --------------------------------------------------------------------------- #
# F1 — the dev endpoint must reject a missing/zero/negative limit price
# --------------------------------------------------------------------------- #
# A JSON `null` price previously slipped past `Optional[float] + gt=0` and became
# a LIMIT order with `limit_price=None`. The schema is now non-optional.


@pytest.mark.parametrize(
    "payload",
    [
        {"symbol": "AAPL", "suggested_limit_price": None},
        {"symbol": "AAPL", "suggested_limit_price": 0},
        {"symbol": "AAPL", "suggested_limit_price": -1},
    ],
)
def test_dev_inject_rejects_bad_limit_price(payload):
    app = create_app(InMemoryStateStore())
    with TestClient(app) as client:
        assert client.post("/api/dev/candidates", json=payload).status_code == 422
        assert client.get("/api/candidates").json() == []


# --------------------------------------------------------------------------- #
# F3 — the in-memory handoff is all-or-nothing, matching SQLite
# --------------------------------------------------------------------------- #


@pytest.mark.anyio
async def test_inmemory_handoff_rolls_back_on_audit_failure(monkeypatch):
    store = InMemoryStateStore()
    await store.initialize()
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    events_before = len(await store.list_events())

    # Inject a failure midway through the handoff (the first audit write).
    def boom(*args, **kwargs):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(store, "_append_event_unlocked", boom)

    with pytest.raises(RuntimeError):
        await store.create_order_for_candidate(candidate.id)

    # All-or-nothing: candidate stays APPROVED, no order, no partial events —
    # the same outcome SQLite gives via its transaction.
    fresh = await store.get_candidate(candidate.id)
    assert fresh.status is CandidateStatus.APPROVED
    assert fresh.order_id is None
    assert await store.list_orders() == []
    assert len(await store.list_events()) == events_before
