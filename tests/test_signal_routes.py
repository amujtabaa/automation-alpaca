"""WO-0138 rev-3 — Signal Seat producer-ingest HTTP behavior.

This ingest-only subset terminates at the HTTP response. Read-back assertions,
operator-route enforcement, and the truncated actor-audit case remain in R5b-2.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest
from fastapi.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings
from app.facade.signal_rails import RailsDecision
from app.main import create_app
from app.models import ExecutionEventType
from app.store.memory import InMemoryStateStore
from tests.signal_seat_helpers import (
    OPERATOR_KEY,
    PRODUCER_KEY,
    _IN_PROCESS_TEST_AUTHORITY,
    build_flag_on_app,
    flag_on_settings,
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


def _events(client: TestClient):
    assert client.portal is not None
    return client.portal.call(client.app.state.store.get_execution_events)


class _ReceiveProbe:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.http_receive_calls = 0

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        async def counted_receive():
            self.http_receive_calls += 1
            return await receive()

        await self.app(
            scope,
            counted_receive if scope["type"] == "http" else receive,
            send,
        )


class _QuarantinedRails:
    async def check_ingest(self, producer_id: str) -> RailsDecision:
        return RailsDecision(
            allowed=False,
            http_status=403,
            reason="producer is quarantined",
        )


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
    r = client.post("/api/signals", json=_proposal(ttl_seconds="300"), headers=_PROD_H)
    assert r.status_code == 422
    assert r.json()["status"] == "quarantined"
    assert r.json()["quarantine_reason"] == "validation"


def test_well_typed_out_of_range_ttl_still_freshness_quarantine(client):
    # Regression guard: strict typing must not disturb the RANGE-based
    # ttl_out_of_range path for a well-typed (real JSON int) out-of-range value.
    r = client.post("/api/signals", json=_proposal(ttl_seconds=5), headers=_PROD_H)
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
    r = client.post("/api/signals", json=_proposal(symbol="ＡＡＰＬ"), headers=_PROD_H)
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
        client.post("/api/signals", json=_proposal(), headers=_OP_H).status_code == 403
    )
    # unknown producer key → 401
    assert (
        client.post(
            "/api/signals", json=_proposal(), headers={"X-Producer-Key": "nope"}
        ).status_code
        == 401
    )


# --------------------------------------------------------------------------- #
# Failure-capable M2 proofs: event truth, boundary ordering, and identity pins.
# --------------------------------------------------------------------------- #
def test_validation_quarantine_appends_exactly_one_terminal_event(client):
    response = client.post(
        "/api/signals",
        json=_proposal(suggested_quantity=True),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    events = _events(client)
    assert [event.event_type for event in events] == [
        ExecutionEventType.SIGNAL_QUARANTINED
    ]
    assert events[0].payload["record"]["status"] == "quarantined"


def test_dead_on_arrival_is_expired_by_ingest(client):
    response = client.post(
        "/api/signals",
        json=_proposal(
            issued_at=(datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat(),
            ttl_seconds=30,
        ),
        headers=_PROD_H,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "expired"
    events = _events(client)
    assert [event.event_type for event in events] == [ExecutionEventType.SIGNAL_EXPIRED]
    assert events[0].payload["detected_by"] == "ingest"


def test_replay_is_write_free_and_conflict_is_audit_only(client):
    proposal = _proposal()
    first = client.post("/api/signals", json=proposal, headers=_PROD_H)
    replay = client.post("/api/signals", json=proposal, headers=_PROD_H)
    conflict = client.post(
        "/api/signals",
        json={**proposal, "thesis": "different"},
        headers=_PROD_H,
    )

    assert (first.status_code, replay.status_code, conflict.status_code) == (
        201,
        200,
        409,
    )
    assert replay.json()["id"] == first.json()["id"]
    assert conflict.json()["id"] == first.json()["id"]
    assert conflict.json()["status"] == first.json()["status"]
    events = _events(client)
    assert [event.event_type for event in events] == [
        ExecutionEventType.SIGNAL_RECEIVED,
        ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
    ]
    assert events[1].payload["original_record_id"] == first.json()["id"]


def test_malformed_body_identity_is_content_addressed_in_event_truth(client):
    first = client.post("/api/signals", json={"foo": 1}, headers=_PROD_H)
    replay = client.post("/api/signals", json={"foo": 1}, headers=_PROD_H)
    distinct = client.post("/api/signals", json={"bar": 2}, headers=_PROD_H)

    assert (first.status_code, replay.status_code, distinct.status_code) == (
        422,
        200,
        422,
    )
    assert replay.json()["id"] == first.json()["id"]
    assert distinct.json()["id"] != first.json()["id"]
    events = _events(client)
    assert [event.event_type for event in events] == [
        ExecutionEventType.SIGNAL_QUARANTINED,
        ExecutionEventType.SIGNAL_QUARANTINED,
    ]
    assert events[0].payload["signal_id"] != events[1].payload["signal_id"]


@pytest.mark.parametrize(
    ("content", "headers", "expected_status"),
    [
        (b"not json", {**_PROD_H, "Content-Type": "application/json"}, 400),
        (
            b'{"signal_id":"big","junk":"' + b"z" * (65 * 1024) + b'"}',
            {**_PROD_H, "Content-Type": "application/json"},
            413,
        ),
        (
            b"{}",
            {"X-Producer-Key": "unknown", "Content-Type": "application/json"},
            401,
        ),
        (
            b"{}",
            {"X-Operator-Key": OPERATOR_KEY, "Content-Type": "application/json"},
            403,
        ),
    ],
    ids=[
        "invalid-json",
        "oversized",
        "unknown-producer",
        "wrong-role",
    ],
)
def test_boundary_rejections_append_no_event(
    client,
    content,
    headers,
    expected_status,
):
    response = client.post("/api/signals", content=content, headers=headers)

    assert response.status_code == expected_status
    assert _events(client) == []


def test_identity_mismatch_rejects_before_namespace_accounting(client):
    response = client.post(
        "/api/signals",
        json=_proposal(producer_id="someone-else"),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    assert _events(client) == []


def test_unknown_credential_is_rejected_without_reading_body():
    app = build_flag_on_app(test_authority=_IN_PROCESS_TEST_AUTHORITY)
    probe = _ReceiveProbe(app)
    with TestClient(probe) as client:
        response = client.post(
            "/api/signals",
            content=b"x" * (65 * 1024),
            headers={"X-Producer-Key": "unknown"},
        )

    assert response.status_code == 401
    assert probe.http_receive_calls == 0


def test_quarantined_producer_is_rejected_without_reading_or_recording():
    store = InMemoryStateStore()
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        store=store,
        rails=_QuarantinedRails(),
    )
    probe = _ReceiveProbe(app)
    with TestClient(probe) as client:
        response = client.post(
            "/api/signals",
            content=b"x" * (65 * 1024),
            headers=_PROD_H,
        )
        assert client.portal is not None
        events = client.portal.call(store.get_execution_events)

    assert response.status_code == 403
    assert probe.http_receive_calls == 0
    assert events == []


def test_request_lookup_uses_normalized_immutable_producer_map():
    source = {PRODUCER_KEY: "vibe-trading"}
    settings = flag_on_settings(signal_producer_keys=source)
    assert type(settings.signal_producer_keys) is MappingProxyType
    source[PRODUCER_KEY] = "mutated-after-settings-construction"
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        settings=settings,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/signals",
            json=_proposal(),
            headers=_PROD_H,
        )

    assert response.status_code == 201
    assert response.json()["producer_id"] == "vibe-trading"


def test_hostile_text_is_returned_verbatim_without_interpretation(client):
    thesis = '<b>market thesis & "quoted"</b>'
    provenance = {
        "source": "../opaque/reference",
        "annotation": "<tag>&literal",
    }

    response = client.post(
        "/api/signals",
        json=_proposal(thesis=thesis, provenance=provenance),
        headers=_PROD_H,
    )

    assert response.status_code == 201
    assert response.json()["thesis"] == thesis
    assert response.json()["provenance"] == provenance
