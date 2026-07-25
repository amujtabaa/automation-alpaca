"""WO-0138 rev-3 — Signal Seat producer-ingest HTTP behavior.

This ingest-only subset terminates at the HTTP response. Read-back assertions,
operator-route enforcement, and the truncated actor-audit case remain in R5b-2.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store.memory import InMemoryStateStore
from tests.signal_seat_helpers import (
    OPERATOR_KEY,
    PRODUCER_KEY,
    _IN_PROCESS_TEST_AUTHORITY,
    build_flag_on_app,
)

_PROD_H = {"X-Producer-Key": PRODUCER_KEY}
_OP_H = {"X-Operator-Key": OPERATOR_KEY}


def _proposal(**over):
    base = dict(
        signal_id="sig-1",
        issued_at=datetime.now(timezone.utc).isoformat(),
        ttl_seconds=300,
        symbol="AAPL",
        direction="buy",
        thesis="momentum breakout",
        provenance={"model": "gpt"},
    )
    base.update(over)
    return base


@pytest.fixture
def client():
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        store=InMemoryStateStore(),
    )
    with TestClient(app) as c:
        yield c


# --------------------------------------------------------------------------- #
# Flag OFF ⇒ endpoint absent (404), no auth surface.
# --------------------------------------------------------------------------- #
def test_flag_off_endpoint_absent():
    app = create_app(settings=Settings(signal_seat_enabled=False, state_store="memory"))
    with TestClient(app) as c:
        assert c.post("/api/signals", json=_proposal()).status_code == 404
        assert c.get("/api/signals").status_code == 404
        # Flag off ⇒ localhost no-auth posture unchanged (existing routes open).
        assert c.get("/api/health").status_code == 200


# --------------------------------------------------------------------------- #
# Ingest behavior (producer-authenticated).
# --------------------------------------------------------------------------- #
def test_accept_received(client):
    r = client.post("/api/signals", json=_proposal(), headers=_PROD_H)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "received"
    assert body["producer_id"] == "vibe-trading"  # credential-derived


def test_idempotent_replay_then_conflict(client):
    prop = _proposal()  # one fixed payload — an identical resend must dedupe
    assert client.post("/api/signals", json=prop, headers=_PROD_H).status_code == 201
    # identical payload → 200 replay
    assert client.post("/api/signals", json=prop, headers=_PROD_H).status_code == 200
    # different payload, same id → 409 conflict
    conflict = {**prop, "thesis": "different"}
    r = client.post("/api/signals", json=conflict, headers=_PROD_H)
    assert r.status_code == 409


def test_string_ttl_seconds_is_validation_quarantine_not_lax_coercion(client):
    # Auto-reviewer P2 #3: a lax int field coerces JSON "300" to 300, silently
    # accepting a type-malformed TTL as RECEIVED. ttl_seconds must be a STRICT
    # int — a JSON string, even a numeric-looking one, is a 422 validation
    # failure (recorded quarantine), never coerced.
    r = client.post(
        "/api/signals", json=_proposal(ttl_seconds="300"), headers=_PROD_H
    )
    assert r.status_code == 422
    assert r.json()["status"] == "quarantined"
    assert r.json()["quarantine_reason"] == "validation"


def test_well_typed_out_of_range_ttl_still_freshness_quarantine(client):
    # Regression guard: strict typing must not disturb the RANGE-based
    # ttl_out_of_range path for a well-typed (real JSON int) out-of-range value.
    r = client.post(
        "/api/signals", json=_proposal(ttl_seconds=5), headers=_PROD_H
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["quarantine_reason"] == "ttl_out_of_range"


def test_numeric_issued_at_is_validation_quarantine(client):
    # Auto-reviewer P2 #5: a lax datetime field accepts a JSON number (Unix
    # timestamp) and silently produces a normal RECEIVED signal. issued_at must
    # be an ISO-8601 STRING — a number is a 422 validation-quarantine.
    r = client.post(
        "/api/signals", json=_proposal(issued_at=1752505200), headers=_PROD_H
    )
    assert r.status_code == 422
    assert r.json()["status"] == "quarantined"
    assert r.json()["quarantine_reason"] == "validation"


def test_boolean_suggested_quantity_is_validation_quarantine(client):
    # Auto-reviewer P2 #6: strict-type the advisory numerics — a bool/string
    # must not be silently coerced into a plausible-looking value.
    r = client.post(
        "/api/signals",
        json=_proposal(suggested_quantity=True),
        headers=_PROD_H,
    )
    assert r.status_code == 422
    assert r.json()["quarantine_reason"] == "validation"


def test_string_suggested_limit_price_is_validation_quarantine(client):
    r = client.post(
        "/api/signals",
        json=_proposal(suggested_limit_price="12.5"),
        headers=_PROD_H,
    )
    assert r.status_code == 422
    assert r.json()["quarantine_reason"] == "validation"


def test_non_ascii_symbol_is_validation_quarantine(client):
    # Auto-reviewer P2 #7: str.isalpha() accepts Unicode (full-width 'ＡＡＰＬ',
    # Nordic 'Å') — the documented domain is ASCII [A-Z.]+. A non-ASCII symbol
    # must be quarantined at ingest, not slip through to a later normalization.
    r = client.post(
        "/api/signals", json=_proposal(symbol="ＡＡＰＬ"), headers=_PROD_H
    )
    assert r.status_code == 422
    assert r.json()["quarantine_reason"] == "validation"


def test_nordic_non_ascii_symbol_is_validation_quarantine(client):
    r = client.post("/api/signals", json=_proposal(symbol="Å"), headers=_PROD_H)
    assert r.status_code == 422
    assert r.json()["quarantine_reason"] == "validation"


def test_malformed_naive_datetime_quarantined(client):
    # Naive issued_at (no offset) → 422 recorded as SIGNAL_QUARANTINED.
    r = client.post(
        "/api/signals",
        json=_proposal(issued_at="2026-07-14T15:00:00"),
        headers=_PROD_H,
    )
    assert r.status_code == 422
    assert r.json()["status"] == "quarantined"
    assert r.json()["quarantine_reason"] == "validation"


def test_identity_binding_mismatch_rejected(client):
    r = client.post(
        "/api/signals",
        json=_proposal(producer_id="someone-else"),
        headers=_PROD_H,
    )
    assert r.status_code == 422


def test_identity_binding_matching_ignored(client):
    r = client.post(
        "/api/signals",
        json=_proposal(producer_id="vibe-trading"),
        headers=_PROD_H,
    )
    assert r.status_code == 201


def test_body_over_64kib_rejected(client):
    big = _proposal(thesis="x" * 100)
    big["provenance"] = {f"k{i}": "y" * 400 for i in range(20)}  # within bounds
    # Pad an allowed-shape body past 64 KiB via a large forbidden extra.
    payload = b'{"signal_id":"big","junk":"' + b"z" * (65 * 1024) + b'"}'
    r = client.post(
        "/api/signals",
        content=payload,
        headers={**_PROD_H, "Content-Type": "application/json"},
    )
    assert r.status_code == 413


def test_producer_route_requires_producer_key(client):
    # none → 401
    assert client.post("/api/signals", json=_proposal()).status_code == 401
    # operator key on the producer route → 403 (wrong credential type)
    assert (
        client.post("/api/signals", json=_proposal(), headers=_OP_H).status_code
        == 403
    )
    # unknown producer key → 401
    assert (
        client.post(
            "/api/signals", json=_proposal(), headers={"X-Producer-Key": "nope"}
        ).status_code
        == 401
    )
