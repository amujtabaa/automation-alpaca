"""WO-0138/WO-0139 — Signal Seat ingest, read, and attribution behavior.

R5b-1 owns the producer-ingest cases. R5b-2 adds the operator read-back and
principal-bound audit cases without weakening the ingest assertions.
"""

from __future__ import annotations

import functools
import json
from datetime import datetime, timedelta, timezone
from types import MappingProxyType, SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import Settings
from app.facade.signal_rails import RailsDecision
from app.main import create_app
from app.models import EventType, ExecutionEventType
from app.store.memory import InMemoryStateStore
from tests.signal_seat_helpers import (
    OPERATOR_KEY,
    PRODUCER_ID,
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
        self.http_headers: list[dict[bytes, bytes]] = []

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        async def counted_receive():
            self.http_receive_calls += 1
            return await receive()

        if scope["type"] == "http":
            self.http_headers.append(dict(scope["headers"]))
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


class _MalformedRails:
    async def check_ingest(self, producer_id: str) -> object:
        return object()


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


@pytest.mark.parametrize(
    "signal_id",
    ["malformed:deadbeef", "x" * 65],
    ids=["reserved-malformed-namespace", "over-64-characters"],
)
def test_signal_id_outside_wire_domain_is_validation_quarantine(client, signal_id):
    response = client.post(
        "/api/signals",
        json=_proposal(signal_id=signal_id),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    assert response.json()["quarantine_reason"] == "validation"


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


def test_numeric_string_issued_at_is_validation_quarantine(client):
    response = client.post(
        "/api/signals",
        json=_proposal(issued_at="1752505200"),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    assert response.json()["quarantine_reason"] == "validation"


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


def test_infinite_suggested_limit_price_is_validation_quarantine(client):
    response = client.post(
        "/api/signals",
        content=json.dumps(_proposal(suggested_limit_price=float("inf"))).encode(),
        headers={**_PROD_H, "Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["quarantine_reason"] == "validation"


def test_non_ascii_symbol_is_validation_quarantine(client):
    # Auto-reviewer P2 #7: str.isalpha() accepts Unicode (full-width 'ＡＡＰＬ',
    # dotless 'ı') — the documented domain is ASCII [A-Z.]+. A non-ASCII symbol
    # must be quarantined at ingest, not slip through to a later normalization.
    r = client.post("/api/signals", json=_proposal(symbol="ＡＡＰＬ"), headers=_PROD_H)
    assert r.status_code == 422
    assert r.json()["quarantine_reason"] == "validation"


def test_case_expanding_non_ascii_symbol_is_validation_quarantine(client):
    r = client.post("/api/signals", json=_proposal(symbol="ıBM"), headers=_PROD_H)
    assert r.status_code == 422
    assert r.json()["quarantine_reason"] == "validation"


@pytest.mark.parametrize("symbol", ["A1", "BRK-B"])
def test_ascii_symbol_outside_signal_wire_domain_is_validation_quarantine(
    client,
    symbol,
):
    response = client.post(
        "/api/signals",
        json=_proposal(symbol=symbol),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    assert response.json()["quarantine_reason"] == "validation"


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


@pytest.mark.parametrize(
    "extra",
    [{}, {"unknown_top_level": True}],
    ids=["otherwise-valid", "validation-fallback"],
)
def test_max_issued_at_is_recorded_validation_quarantine(client, extra):
    response = client.post(
        "/api/signals",
        json=_proposal(
            issued_at="9999-12-31T23:59:59+00:00",
            **extra,
        ),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "quarantined"
    assert body["quarantine_reason"] == "validation"
    assert body["issued_at"] is None
    assert body["expires_at"] is None
    events = _events(client)
    assert [event.event_type for event in events] == [
        ExecutionEventType.SIGNAL_QUARANTINED
    ]


def test_allowed_upper_issued_at_is_normalized_before_freshness_math(client):
    response = client.post(
        "/api/signals",
        json=_proposal(
            issued_at="9999-12-31T00:59:59.999999+01:00",
            ttl_seconds=86400,
        ),
        headers=_PROD_H,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "quarantined"
    assert body["quarantine_reason"] == "issued_at_future"
    assert body["issued_at"] == "9999-12-30T23:59:59.999999Z"


def test_unknown_top_level_key_is_validation_quarantine(client):
    response = client.post(
        "/api/signals",
        json=_proposal(unknown_top_level=True),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    assert response.json()["quarantine_reason"] == "validation"


def test_empty_thesis_is_validation_quarantine(client):
    response = client.post(
        "/api/signals",
        json=_proposal(thesis=""),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    assert response.json()["quarantine_reason"] == "validation"


@pytest.mark.parametrize(
    "provenance",
    [
        {f"key-{index}": "value" for index in range(21)},
        {"source": "x" * 501},
    ],
    ids=["over-20-entries", "value-over-500-characters"],
)
def test_provenance_over_wire_caps_is_validation_quarantine(client, provenance):
    response = client.post(
        "/api/signals",
        json=_proposal(provenance=provenance),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    assert response.json()["quarantine_reason"] == "validation"


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
    assert conflict.json() == first.json()
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
    "body",
    [b"null", b"[]", b'"scalar"', b"7", b"true"],
    ids=["null", "array", "string", "number", "boolean"],
)
def test_every_parseable_top_level_shape_is_recorded_quarantine(client, body):
    response = client.post(
        "/api/signals",
        content=body,
        headers={**_PROD_H, "Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["status"] == "quarantined"
    assert [event.event_type for event in _events(client)] == [
        ExecutionEventType.SIGNAL_QUARANTINED
    ]


def test_non_string_body_producer_id_is_recorded_not_trusted(client):
    response = client.post(
        "/api/signals",
        json=_proposal(producer_id=123),
        headers=_PROD_H,
    )

    assert response.status_code == 422
    assert response.json()["producer_id"] == "vibe-trading"
    assert [event.event_type for event in _events(client)] == [
        ExecutionEventType.SIGNAL_QUARANTINED
    ]


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


def test_malformed_rails_decision_fails_closed_without_reading_body():
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        rails=_MalformedRails(),
    )
    probe = _ReceiveProbe(app)
    with TestClient(probe) as client:
        response = client.post(
            "/api/signals",
            content=b"x" * (65 * 1024),
            headers=_PROD_H,
        )

    assert response.status_code == 503
    assert probe.http_receive_calls == 0


def test_streamed_oversize_is_rejected_without_content_length_or_event():
    store = InMemoryStateStore()
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        store=store,
    )
    probe = _ReceiveProbe(app)
    chunks = iter([b"x" * (32 * 1024), b"y" * (33 * 1024)])
    with TestClient(probe) as client:
        response = client.post(
            "/api/signals",
            content=chunks,
            headers=_PROD_H,
        )
        assert client.portal is not None
        events = client.portal.call(store.get_execution_events)

    assert b"content-length" not in probe.http_headers[-1]
    assert response.status_code == 413
    assert probe.http_receive_calls > 0
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


# --------------------------------------------------------------------------- #
# R5b-2 signal reads, credential outcomes, and audit attribution.
# --------------------------------------------------------------------------- #
def test_get_signals_is_operator_only(client):
    assert client.get("/api/signals").status_code == 401
    assert client.get("/api/signals", headers=_PROD_H).status_code == 403
    assert client.get("/api/signals", headers=_OP_H).status_code == 200


def test_health_is_the_only_public_flag_on_api_operation(client):
    assert client.get("/api/health").status_code == 200
    assert client.post("/api/health").status_code == 401


def test_existing_sensitive_read_requires_operator(client):
    assert client.get("/api/positions").status_code == 401
    assert client.get("/api/positions", headers=_PROD_H).status_code == 403
    assert client.get("/api/positions", headers=_OP_H).status_code == 200


def test_unknown_producer_key_on_operator_route_is_401(client):
    unknown = {"X-Producer-Key": "not-a-real-key"}
    assert client.get("/api/positions", headers=unknown).status_code == 401
    assert client.get("/api/signals", headers=unknown).status_code == 401
    assert client.get("/api/positions", headers=_PROD_H).status_code == 403
    assert client.get("/api/signals", headers=_PROD_H).status_code == 403


def test_non_ascii_credentials_are_invalid_not_errors():
    from app.api.deps import (
        operator_key_valid,
        producer_key_valid,
        resolve_producer_id,
    )

    settings = Settings(
        signal_seat_enabled=True,
        operator_api_key=OPERATOR_KEY,
        signal_producer_keys={PRODUCER_KEY: "vibe"},
    )
    assert operator_key_valid("é", settings) is False
    assert producer_key_valid("é", settings) is False
    with pytest.raises(HTTPException) as exc:
        resolve_producer_id(producer_key="é", operator_key=None, settings=settings)
    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    ("supplied", "producer_id"),
    [
        ("first-key", "first-producer"),
        ("middle-key", "middle-producer"),
        ("last-key", "last-producer"),
        ("unknown-key", None),
    ],
)
def test_producer_credential_helpers_visit_the_complete_key_map(
    monkeypatch,
    supplied,
    producer_id,
):
    from app.api import deps

    settings = Settings(
        signal_seat_enabled=True,
        operator_api_key=OPERATOR_KEY,
        signal_producer_keys={
            "first-key": "first-producer",
            "middle-key": "middle-producer",
            "last-key": "last-producer",
        },
    )
    configured_keys = list(settings.signal_producer_keys)
    calls: list[str] = []
    real_compare = deps._credentials_equal

    def tracked_compare(candidate: str, configured: str) -> bool:
        calls.append(configured)
        return real_compare(candidate, configured)

    monkeypatch.setattr(deps, "_credentials_equal", tracked_compare)

    assert deps.producer_key_valid(supplied, settings) is (producer_id is not None)
    assert calls == configured_keys

    calls.clear()
    if producer_id is None:
        with pytest.raises(HTTPException) as exc:
            deps.resolve_producer_id(
                producer_key=supplied,
                operator_key=None,
                settings=settings,
            )
        assert exc.value.status_code == 401
    else:
        assert (
            deps.resolve_producer_id(
                producer_key=supplied,
                operator_key=None,
                settings=settings,
            )
            == producer_id
        )
    assert calls == configured_keys


def test_get_signals_defaults_to_received_and_filters(client):
    first = client.post(
        "/api/signals",
        json=_proposal(signal_id="received"),
        headers=_PROD_H,
    )
    second = client.post(
        "/api/signals",
        json=_proposal(signal_id="quarantined", ttl_seconds=5),
        headers=_PROD_H,
    )
    third = client.post(
        "/api/signals",
        json=_proposal(signal_id="received-msft", symbol="MSFT"),
        headers=_PROD_H,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 201

    default_records = client.get("/api/signals", headers=_OP_H)
    assert default_records.status_code == 200
    assert [record["signal_id"] for record in default_records.json()] == [
        "received",
        "received-msft",
    ]

    quarantined = client.get(
        "/api/signals",
        params={"status": "quarantined"},
        headers=_OP_H,
    )
    assert quarantined.status_code == 200
    assert [record["signal_id"] for record in quarantined.json()] == ["quarantined"]

    aapl = client.get(
        "/api/signals",
        params={"symbol": "aapl"},
        headers=_OP_H,
    )
    assert aapl.status_code == 200
    assert [record["signal_id"] for record in aapl.json()] == ["received"]

    producer = client.get(
        "/api/signals",
        params={"producer_id": PRODUCER_ID},
        headers=_OP_H,
    )
    assert producer.status_code == 200
    assert [record["signal_id"] for record in producer.json()] == [
        "received",
        "received-msft",
    ]
    other_producer = client.get(
        "/api/signals",
        params={"producer_id": "not-this-producer"},
        headers=_OP_H,
    )
    assert other_producer.status_code == 200
    assert other_producer.json() == []


def test_get_signals_bad_filters_are_422(client):
    assert (
        client.get(
            "/api/signals",
            params={"symbol": "bad$"},
            headers=_OP_H,
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/signals",
            params={"status": "not-a-real-status"},
            headers=_OP_H,
        ).status_code
        == 422
    )


def test_get_signals_reads_back_distinct_malformed_records(client):
    first = client.post("/api/signals", json={"foo": 1}, headers=_PROD_H)
    second = client.post("/api/signals", json={"bar": 2}, headers=_PROD_H)
    replay = client.post("/api/signals", json={"foo": 1}, headers=_PROD_H)
    assert (first.status_code, second.status_code, replay.status_code) == (
        422,
        422,
        200,
    )

    records = client.get(
        "/api/signals",
        params={"status": "quarantined"},
        headers=_OP_H,
    )
    assert records.status_code == 200
    assert len(records.json()) == 2
    assert len({record["signal_id"] for record in records.json()}) == 2


def test_unparseable_body_has_empty_signal_readback(client):
    response = client.post(
        "/api/signals",
        content=b"not json",
        headers={**_PROD_H, "Content-Type": "application/json"},
    )
    assert response.status_code == 400
    listed = client.get("/api/signals", headers=_OP_H)
    assert listed.status_code == 200
    assert listed.json() == []


def test_operator_command_audit_actor_is_principal_bound():
    store = InMemoryStateStore()
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        store=store,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/controls/kill-switch",
            json={"engaged": True},
            headers={**_OP_H, "X-Actor": "desk-3"},
        )
        assert response.status_code == 200, response.text
        assert client.portal is not None
        events = client.portal.call(
            functools.partial(
                store.list_events,
                event_type=EventType.KILL_SWITCH_ENGAGED.value,
            )
        )

    assert events
    assert events[-1].payload["actor"] == "operator:authenticated:desk-3"


def test_operator_command_without_optional_label_uses_distinct_principal():
    store = InMemoryStateStore()
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        store=store,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/controls/kill-switch",
            json={"engaged": True},
            headers=_OP_H,
        )
        assert response.status_code == 200, response.text
        assert client.portal is not None
        events = client.portal.call(
            functools.partial(
                store.list_events,
                event_type=EventType.KILL_SWITCH_ENGAGED.value,
            )
        )

    assert events
    assert events[-1].payload["actor"] == "operator:authenticated"


def test_get_actor_flag_off_preserves_internal_control_characters():
    from app.api.deps import get_actor

    request = SimpleNamespace(state=SimpleNamespace())
    assert get_actor(request=request, x_actor="desk\tlabel\n2") == "desk\tlabel\n2"


def test_get_actor_flag_on_sanitizes_only_the_optional_label():
    from app.api.deps import get_actor

    request = SimpleNamespace(
        state=SimpleNamespace(authenticated_actor="operator:authenticated")
    )
    assert (
        get_actor(request=request, x_actor="desk\tlabel\n2")
        == "operator:authenticated:desklabel2"
    )
