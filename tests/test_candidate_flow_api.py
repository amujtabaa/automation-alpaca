"""Full API coverage for the candidate lifecycle — inject, list, approve, reject.

IO-free: all tests drive everything through HTTP (FastAPI TestClient + injected
InMemoryStateStore). The dev endpoint (POST /api/dev/candidates) is used to
inject candidates so tests remain black-box with respect to the store.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.approval.gate import ApprovalGate, GateDecision
from app.approval.human import HumanApprovalGate
from app.api.deps import get_approval_gate
from app.main import create_app
from app.models import Candidate
from app.store.memory import InMemoryStateStore


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def client():
    """A fresh TestClient with an injected in-memory store."""

    app = create_app(InMemoryStateStore())
    with TestClient(app) as c:
        yield c


def _inject(client: TestClient, symbol: str = "AAPL", **kwargs) -> dict:
    """Helper: POST /api/dev/candidates and return the parsed JSON body."""

    payload = {"symbol": symbol, **kwargs}
    resp = client.post("/api/dev/candidates", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# 1. Inject + list scoped to session
# --------------------------------------------------------------------------- #


def test_inject_and_list_scoped_to_session(client):
    """Injected candidate appears in /api/candidates; symbol is normalised."""

    body = _inject(client, symbol="aapl")

    # Symbol is normalised to uppercase.
    assert body["symbol"] == "AAPL"
    assert body["status"] == "pending"

    candidates = client.get("/api/candidates").json()
    assert len(candidates) == 1
    assert candidates[0]["id"] == body["id"]
    assert candidates[0]["symbol"] == "AAPL"
    assert candidates[0]["status"] == "pending"


# --------------------------------------------------------------------------- #
# 2. Get single + 404
# --------------------------------------------------------------------------- #


def test_get_single_candidate(client):
    """GET /api/candidates/{id} returns 200 for a known id."""

    body = _inject(client)
    resp = client.get(f"/api/candidates/{body['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == body["id"]


def test_get_unknown_candidate_returns_404(client):
    """GET /api/candidates/{id} returns 404 for an unknown id."""

    resp = client.get("/api/candidates/does-not-exist")
    assert resp.status_code == 404
    assert "does-not-exist" in resp.json()["detail"]


# --------------------------------------------------------------------------- #
# 3. Approve happy path -> ordered + order created
# --------------------------------------------------------------------------- #


def test_approve_happy_path(client):
    """Approving a pending candidate returns ordered status and creates an order.

    No fill or position is created (Rule 6/7: submitted != filled).
    """

    body = _inject(
        client, symbol="TSLA", suggested_quantity=10, suggested_limit_price=1.00
    )
    candidate_id = body["id"]

    resp = client.post(f"/api/candidates/{candidate_id}/approve")
    assert resp.status_code == 200
    approved = resp.json()
    assert approved["status"] == "ordered"
    assert approved["order_id"] is not None

    # The order exists and is correctly shaped.
    orders = client.get("/api/orders").json()
    assert len(orders) == 1
    order = orders[0]
    assert order["candidate_id"] == candidate_id
    assert order["side"] == "buy"
    assert order["order_type"] == "limit"
    assert order["quantity"] == 10

    # No fill -> no position (Rule 6/7).
    positions = client.get("/api/positions").json()
    assert positions == []


# --------------------------------------------------------------------------- #
# 4. Approve is idempotent
# --------------------------------------------------------------------------- #


def test_approve_is_idempotent(client):
    """Approving twice returns 200 both times; exactly one order is created."""

    body = _inject(client)
    candidate_id = body["id"]

    r1 = client.post(f"/api/candidates/{candidate_id}/approve")
    r2 = client.post(f"/api/candidates/{candidate_id}/approve")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["status"] == "ordered"
    assert r2.json()["status"] == "ordered"

    # Only one order must have been created.
    orders = client.get("/api/orders").json()
    assert len(orders) == 1


# --------------------------------------------------------------------------- #
# 5. Reject happy path
# --------------------------------------------------------------------------- #


def test_reject_happy_path(client):
    """Rejecting a pending candidate returns rejected status; no order is created."""

    body = _inject(client)
    candidate_id = body["id"]

    resp = client.post(f"/api/candidates/{candidate_id}/reject")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    orders = client.get("/api/orders").json()
    assert orders == []


# --------------------------------------------------------------------------- #
# 6. Reject is idempotent
# --------------------------------------------------------------------------- #


def test_reject_is_idempotent(client):
    """Rejecting twice returns 200 both times; status stays rejected."""

    body = _inject(client)
    candidate_id = body["id"]

    r1 = client.post(f"/api/candidates/{candidate_id}/reject")
    r2 = client.post(f"/api/candidates/{candidate_id}/reject")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["status"] == "rejected"
    assert r2.json()["status"] == "rejected"


# --------------------------------------------------------------------------- #
# 7. Rejected candidate cannot be approved -> 409
# --------------------------------------------------------------------------- #


def test_rejected_candidate_cannot_be_approved(client):
    """A rejected candidate cannot be approved — expect HTTP 409."""

    body = _inject(client)
    candidate_id = body["id"]

    client.post(f"/api/candidates/{candidate_id}/reject")
    resp = client.post(f"/api/candidates/{candidate_id}/approve")
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# 8. Approved/ordered candidate cannot be rejected -> 409
# --------------------------------------------------------------------------- #


def test_ordered_candidate_cannot_be_rejected(client):
    """An ordered candidate cannot be rejected — expect HTTP 409."""

    body = _inject(client)
    candidate_id = body["id"]

    client.post(f"/api/candidates/{candidate_id}/approve")
    resp = client.post(f"/api/candidates/{candidate_id}/reject")
    assert resp.status_code == 409


# --------------------------------------------------------------------------- #
# 9. Approve/reject unknown id -> 404
# --------------------------------------------------------------------------- #


def test_approve_unknown_returns_404(client):
    """Approving an unknown candidate id returns HTTP 404."""

    resp = client.post("/api/candidates/no-such-id/approve")
    assert resp.status_code == 404


def test_reject_unknown_returns_404(client):
    """Rejecting an unknown candidate id returns HTTP 404."""

    resp = client.post("/api/candidates/no-such-id/reject")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# 10. Gate pluggability
# --------------------------------------------------------------------------- #


class RecordingGate(ApprovalGate):
    """Wraps an inner gate and records every approve/reject call."""

    def __init__(self, inner: ApprovalGate) -> None:
        self._inner = inner
        self.calls: list[tuple[str, str]] = []

    async def evaluate(self, candidate: Candidate) -> GateDecision:
        return await self._inner.evaluate(candidate)

    async def approve(self, candidate_id: str) -> Candidate:
        self.calls.append(("approve", candidate_id))
        return await self._inner.approve(candidate_id)

    async def reject(self, candidate_id: str) -> Candidate:
        self.calls.append(("reject", candidate_id))
        return await self._inner.reject(candidate_id)


def test_gate_pluggability_approve(client):
    """The approve route honours a substituted ApprovalGate implementation.

    This test proves that the route depends on the *interface* (ApprovalGate),
    not the concrete HumanApprovalGate — a different implementation is used
    with zero route edits.
    """

    store = InMemoryStateStore()
    app = create_app(store)

    inner_gate = HumanApprovalGate(store)
    recording = RecordingGate(inner_gate)

    app.dependency_overrides[get_approval_gate] = lambda: recording

    with TestClient(app) as c:
        body = c.post(
            "/api/dev/candidates",
            json={
                "symbol": "AAPL",
                "suggested_quantity": 10,
                "suggested_limit_price": 1.00,
            },
        )
        assert body.status_code == 201
        candidate_id = body.json()["id"]

        resp = c.post(f"/api/candidates/{candidate_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ordered"

    assert ("approve", candidate_id) in recording.calls


def test_gate_pluggability_reject(client):
    """The reject route honours a substituted ApprovalGate implementation."""

    store = InMemoryStateStore()
    app = create_app(store)

    inner_gate = HumanApprovalGate(store)
    recording = RecordingGate(inner_gate)

    app.dependency_overrides[get_approval_gate] = lambda: recording

    with TestClient(app) as c:
        body = c.post(
            "/api/dev/candidates",
            json={
                "symbol": "MSFT",
                "suggested_quantity": 5,
                "suggested_limit_price": 2.00,
            },
        )
        assert body.status_code == 201
        candidate_id = body.json()["id"]

        resp = c.post(f"/api/candidates/{candidate_id}/reject")
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    assert ("reject", candidate_id) in recording.calls
