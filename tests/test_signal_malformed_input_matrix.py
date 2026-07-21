"""WO-0102 — the malformed-input -> quarantine boundary, closed as a class
(auto-reviewer round 3).

ROOT INVARIANT under test: for an AUTHENTICATED producer, ANY parseable
request body (valid JSON of any shape) that fails SignalProposal validation is
recorded as a terminal SIGNAL_QUARANTINED (HTTP 422) with the offending content
preserved in raw_fields — never a 400/500-and-forget. Only a genuinely
UNparseable body (or an unauthenticated request) is a no-event boundary reject
(400/401). Building the quarantine record must NEVER itself raise.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from tests.signal_seat_helpers import OPERATOR_KEY, PRODUCER_KEY, build_flag_on_app
from app.store.memory import InMemoryStateStore

_PROD_H = {"X-Producer-Key": PRODUCER_KEY}
_OP_H = {"X-Operator-Key": OPERATOR_KEY}


@pytest.fixture
def client():
    app = build_flag_on_app(store=InMemoryStateStore())
    with TestClient(app) as c:
        yield c


def _post_raw(client, content: bytes, **headers):
    return client.post(
        "/api/signals",
        content=content,
        headers={**_PROD_H, "Content-Type": "application/json", **headers},
    )


# --------------------------------------------------------------------------- #
# The broad malformed-input matrix: EVERY parseable-but-invalid JSON shape a
# producer could send is a recorded 422 quarantine, never a 400/500-and-forget.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "raw_body,label",
    [
        (b"[]", "empty-array"),
        (b"[1,2,3]", "array-of-ints"),
        (b"null", "literal-null"),
        (b"123", "bare-number"),
        (b'"hello"', "bare-string"),
        (b"true", "bare-bool"),
        (b"{}", "empty-object"),
        (b'{"foo": 1}', "unrelated-object"),
    ],
)
def test_every_malformed_shape_is_recorded_quarantine(client, raw_body, label):
    r = _post_raw(client, raw_body)
    assert r.status_code == 422, f"{label}: expected 422, got {r.status_code}: {r.text}"
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["quarantine_reason"] == "validation"
    assert body["raw_fields"]  # the offending content is preserved, never dropped


def test_two_distinct_non_object_bodies_are_distinct_records(client):
    # Mirrors the earlier no-signal_id fix: two distinct non-object bodies must
    # not collide onto one record via a shared sentinel identity.
    r1 = _post_raw(client, b"[1,2,3]")
    r2 = _post_raw(client, b'"a different string"')
    assert r1.status_code == 422
    assert r2.status_code == 422
    assert r1.json()["id"] != r2.json()["id"]
    # Default list is the RECEIVED queue (04 §2); filter for the quarantines.
    records = client.get(
        "/api/signals", params={"status": "quarantined"}, headers=_OP_H
    ).json()
    assert len(records) == 2


def test_whitespace_only_signal_id_is_treated_as_missing(client):
    # Auto-review round 4 (P2): a whitespace-only "signal_id" must NOT count as a
    # usable identity — otherwise two distinct malformed bodies both sending
    # "   " collide onto one (producer_id, signal_id) key, and the second is a
    # 409 duplicate-conflict with no new terminal quarantine (a lost fact).
    r1 = _post_raw(client, b'{"signal_id": "   ", "foo": 1}')
    r2 = _post_raw(client, b'{"signal_id": "   ", "foo": 2}')
    assert r1.status_code == 422
    assert r2.status_code == 422  # NOT a 409 conflict / 200 replay
    assert r1.json()["id"] != r2.json()["id"]  # distinct content-hashed ids
    records = client.get(
        "/api/signals", params={"status": "quarantined"}, headers=_OP_H
    ).json()
    assert len(records) == 2


def test_truly_empty_body_stays_unparseable_400_no_event(client):
    # Zero bytes is not a JSON document at all — the one case that stays a
    # genuine unparseable boundary reject (matches non-JSON garbage).
    r = _post_raw(client, b"")
    assert r.status_code == 400
    assert client.get("/api/signals", headers=_OP_H).json() == []


def test_actually_unparseable_json_stays_400_no_event(client):
    r = _post_raw(client, b"{not json at all")
    assert r.status_code == 400
    assert client.get("/api/signals", headers=_OP_H).json() == []


def test_unauthenticated_request_is_401_no_event(client):
    r = client.post("/api/signals", json={"foo": 1})
    assert r.status_code == 401
    assert client.get("/api/signals", headers=_OP_H).json() == []


# --------------------------------------------------------------------------- #
# P1 #1 — non-string provenance values must never crash record construction.
# --------------------------------------------------------------------------- #
def test_non_string_provenance_value_is_quarantine_not_500(client):
    r = client.post(
        "/api/signals",
        json={
            "signal_id": "sig-p1",
            "issued_at": "not-a-real-date",  # also invalid, forces the branch
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {"model": 1},  # int value — dict[str, str] violation
        },
        headers=_PROD_H,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["provenance"] == {"model": "1"}  # normalized, never dropped raw


def test_non_string_provenance_value_alone_is_quarantine_not_500(client):
    # provenance is the ONLY invalid field (everything else well-formed) —
    # SignalProposal's own dict[str, str] field validation rejects this alone.
    r = client.post(
        "/api/signals",
        json={
            "signal_id": "sig-p1b",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {"model": True, "source": None},
        },
        headers=_PROD_H,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["provenance"] == {"model": "True", "source": "None"}


# --------------------------------------------------------------------------- #
# P2 #4 — a digit-only issued_at STRING must not be coerced as a Unix timestamp.
# --------------------------------------------------------------------------- #
def test_digit_string_issued_at_is_quarantine_not_unix_coercion(client):
    r = client.post(
        "/api/signals",
        json={
            "signal_id": "sig-p2-4",
            "issued_at": "1784059129",  # digit-only string
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {},
        },
        headers=_PROD_H,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["quarantine_reason"] == "validation"


def test_digit_string_with_decimal_issued_at_is_quarantine(client):
    r = client.post(
        "/api/signals",
        json={
            "signal_id": "sig-p2-4b",
            "issued_at": "1784059129.5",
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {},
        },
        headers=_PROD_H,
    )
    assert r.status_code == 422


def test_real_iso_string_issued_at_still_accepted(client):
    # Regression guard: a genuine ISO-8601 string (with separators) is unaffected.
    r = client.post(
        "/api/signals",
        json={
            "signal_id": "sig-p2-4c",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {},
        },
        headers=_PROD_H,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "received"

