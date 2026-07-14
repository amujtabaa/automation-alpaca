"""WO-0102 — Signal ingestion endpoint HTTP behavior (ADR-009 A-1/A-4).

Mounted-app integration via the test seam (fake rails + minted capability +
operator/producer credentials). Covers accept/replay/conflict/malformed, the
body-blind auth+rails ordering, identity binding, the 64 KiB cap, flag-off 404,
and the WO-0102-scoped route-authorization matrix (health public, producer route
producer-only, operator routes operator-only). The FULL reads-included matrix +
paced-flood are the joint WO-0102+0104 milestone against WO-0104's real rails.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.store.memory import InMemoryStateStore
from tests.signal_seat_helpers import (
    OPERATOR_KEY,
    PRODUCER_KEY,
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
    app = build_flag_on_app(store=InMemoryStateStore())
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


def test_unparseable_body_is_400_no_event(client):
    r = client.post(
        "/api/signals",
        content=b"not json",
        headers={**_PROD_H, "Content-Type": "application/json"},
    )
    assert r.status_code == 400
    # No signal recorded (unattributable garbage).
    assert client.get("/api/signals", headers=_OP_H).json() == []


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
    big["provenance"] = {f"k{i}": "y" * 400 for i in range(20)}  # within field bounds
    # Pad an allowed-shape body past 64 KiB via a large (forbidden-extra) — instead
    # send a raw oversized JSON blob.
    payload = b'{"signal_id":"big","junk":"' + b"z" * (65 * 1024) + b'"}'
    r = client.post(
        "/api/signals",
        content=payload,
        headers={**_PROD_H, "Content-Type": "application/json"},
    )
    assert r.status_code == 413


# --------------------------------------------------------------------------- #
# WO-0102-scoped route-authorization matrix (against the real mounted app).
# --------------------------------------------------------------------------- #
def test_producer_route_requires_producer_key(client):
    # none → 401
    assert client.post("/api/signals", json=_proposal()).status_code == 401
    # operator key on the producer route → 403 (wrong credential type)
    assert client.post("/api/signals", json=_proposal(), headers=_OP_H).status_code == 403
    # unknown producer key → 401
    assert (
        client.post(
            "/api/signals", json=_proposal(), headers={"X-Producer-Key": "nope"}
        ).status_code
        == 401
    )


def test_get_signals_is_operator_only(client):
    assert client.get("/api/signals").status_code == 401
    assert client.get("/api/signals", headers=_PROD_H).status_code == 403
    assert client.get("/api/signals", headers=_OP_H).status_code == 200


def test_health_is_public_under_flag(client):
    assert client.get("/api/health").status_code == 200


def test_existing_read_route_requires_operator(client):
    # Read exposure is exposure (A-1.3): positions require the operator key too.
    assert client.get("/api/positions").status_code == 401
    assert client.get("/api/positions", headers=_PROD_H).status_code == 403
    assert client.get("/api/positions", headers=_OP_H).status_code == 200


def test_docs_disabled_under_flag(client):
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404


# --------------------------------------------------------------------------- #
# Slice-1 bug fix (1): module import under the flag must NOT raise; module `app`
# is None so a bare `uvicorn app.main:app` fails to serve (no listener).
# --------------------------------------------------------------------------- #
def test_import_under_flag_does_not_raise():
    proc = subprocess.run(
        [sys.executable, "-c", "from app.main import create_app; print('ok')"],
        env={"SIGNAL_SEAT_ENABLED": "true", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


def test_module_app_is_none_under_flag():
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.main; print('APP_IS', app.main.app is None)",
        ],
        env={"SIGNAL_SEAT_ENABLED": "true", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert proc.returncode == 0, proc.stderr
    assert "APP_IS True" in proc.stdout
