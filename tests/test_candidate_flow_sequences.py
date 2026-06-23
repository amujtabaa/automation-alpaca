"""Adversarial regression coverage for the Phase 3 candidate flow.

Two lenses the prompt calls out, kept as permanent tests so the fixes don't
regress:

* **Input-boundary** — hostile inputs to the new ``POST /api/dev/candidates``
  endpoint return clean 4xx, never a 500.
* **Sequence / lifecycle** — approve → close → review orderings, and the
  interaction with session close (D-007/D-009): an ``ordered`` candidate survives
  close, an open one is expired, and a terminal candidate can be neither approved
  nor rejected.
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


# --------------------------------------------------------------------------- #
# Input-boundary lens — hostile inputs to the dev injection endpoint
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload",
    [
        {"symbol": "   "},  # whitespace-only -> normalizes to empty
        {"symbol": "\t\n"},  # other whitespace
        {"symbol": ""},  # empty (pydantic min_length=1)
        {},  # missing symbol
        {"symbol": "AAPL", "suggested_quantity": 0},  # gt=0
        {"symbol": "AAPL", "suggested_quantity": -5},
        {"symbol": "AAPL", "suggested_limit_price": -1.0},  # gt=0
    ],
)
def test_dev_inject_rejects_bad_input_without_500(client, payload):
    resp = client.post("/api/dev/candidates", json=payload)
    # A clean validation rejection, never an uncaught 500.
    assert resp.status_code == 422, resp.text
    # And nothing was created.
    assert client.get("/api/candidates").json() == []


# --------------------------------------------------------------------------- #
# Sequence / lifecycle lens
# --------------------------------------------------------------------------- #


def test_approve_then_close_preserves_ordered_expires_open(client):
    """Session close expires open candidates but leaves an ordered one intact.

    (The approve endpoint fuses approve + dispatch, so the API never parks a
    candidate at bare ``approved`` — the two states reaching close are ``ordered``
    and ``pending``.)
    """

    ordered_id = client.post("/api/dev/candidates", json={"symbol": "NVDA"}).json()["id"]
    pending_a = client.post("/api/dev/candidates", json={"symbol": "MSFT"}).json()["id"]
    pending_b = client.post("/api/dev/candidates", json={"symbol": "AMD"}).json()["id"]

    # Drive one to ORDERED; leave the other two PENDING.
    assert client.post(f"/api/candidates/{ordered_id}/approve").status_code == 200

    assert client.post("/api/session/close").status_code == 200

    # ORDERED is terminal and survives close; open candidates are expired.
    assert client.get(f"/api/candidates/{ordered_id}").json()["status"] == "ordered"
    assert client.get(f"/api/candidates/{pending_a}").json()["status"] == "expired"
    assert client.get(f"/api/candidates/{pending_b}").json()["status"] == "expired"


def test_expired_candidate_cannot_be_approved_or_rejected(client):
    """A candidate expired by session close is terminal: approve/reject -> 409."""

    cid = client.post("/api/dev/candidates", json={"symbol": "TSLA"}).json()["id"]
    assert client.post("/api/session/close").status_code == 200
    assert client.get(f"/api/candidates/{cid}").json()["status"] == "expired"

    assert client.post(f"/api/candidates/{cid}/approve").status_code == 409
    assert client.post(f"/api/candidates/{cid}/reject").status_code == 409


def test_approve_close_review_round_trip(client):
    """approve -> close -> review: the closed session reports the ordered
    candidate and its order (the snapshot/review path, D-007)."""

    cid = client.post("/api/dev/candidates", json={"symbol": "NVDA"}).json()["id"]
    client.post(f"/api/candidates/{cid}/approve")
    client.post("/api/session/close")

    review = client.get("/api/review").json()
    statuses = sorted(c["status"] for c in review["candidates"])
    assert statuses == ["ordered"]
    assert len(review["orders"]) == 1
    assert review["orders"][0]["candidate_id"] == cid
    # No fills were ever recorded, so the closed session snapshots no positions
    # (approval/order creation never touches position — Rule 6/7).
    assert review["positions"] == []


def test_approve_does_not_create_a_position(client):
    """Approval creates an order but never a fill, so no position appears."""

    cid = client.post("/api/dev/candidates", json={"symbol": "AAPL"}).json()["id"]
    client.post(f"/api/candidates/{cid}/approve")
    assert client.get("/api/positions").json() == []
    assert client.get("/api/positions/AAPL").json()["quantity"] == 0
