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

import functools
import json

import pytest
from fastapi import HTTPException
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


def test_distinct_malformed_no_signal_id_bodies_do_not_collide(client):
    # Auto-reviewer P1 #5: two structurally-different malformed bodies, both
    # lacking a usable signal_id, must each be recorded as their OWN terminal
    # quarantine — never conflated via a shared "unknown" sentinel identity
    # (which would make the second request an idempotent 200 replay of the
    # first, silently losing a distinct malformed-but-attributable fact).
    r1 = client.post("/api/signals", json={"foo": 1}, headers=_PROD_H)
    r2 = client.post("/api/signals", json={"bar": 2}, headers=_PROD_H)
    assert r1.status_code == 422
    assert r2.status_code == 422
    assert r1.json()["id"] != r2.json()["id"]

    records = client.get(
        "/api/signals", params={"status": "quarantined"}, headers=_OP_H
    ).json()
    assert len(records) == 2
    signal_ids = {r["signal_id"] for r in records}
    assert len(signal_ids) == 2  # distinct identities, not both "unknown"
    for r in records:
        assert r["status"] == "quarantined"
        assert r["quarantine_reason"] == "validation"


def test_identical_malformed_body_replayed_idempotently(client):
    # The flip side: an EXACT resubmission of the same malformed body is a
    # legitimate idempotent replay (mirrors the well-formed dedupe contract),
    # not a second distinct record.
    body = {"foo": 1, "same": "content"}
    r1 = client.post("/api/signals", json=body, headers=_PROD_H)
    r2 = client.post("/api/signals", json=body, headers=_PROD_H)
    assert r1.status_code == 422
    assert r2.status_code == 200  # idempotent replay of the same quarantine
    assert r1.json()["id"] == r2.json()["id"]
    assert (
        len(
            client.get(
                "/api/signals", params={"status": "quarantined"}, headers=_OP_H
            ).json()
        )
        == 1
    )


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


def test_invalid_producer_key_on_operator_route_is_401_not_403(client):
    # Auto-review round 4 (P2): the A-1 matrix distinguishes an UNKNOWN
    # credential (401) from a VALID producer key used on the wrong route (403).
    # A garbage X-Producer-Key is not an authenticated producer, so it must be
    # 401 — the 403 branch keys off producer-key VALIDITY, not header presence.
    assert (
        client.get(
            "/api/positions", headers={"X-Producer-Key": "not-a-real-key"}
        ).status_code
        == 401
    )
    # And the signals list route (middleware path) agrees.
    assert (
        client.get(
            "/api/signals", headers={"X-Producer-Key": "not-a-real-key"}
        ).status_code
        == 401
    )
    # A VALID producer key on the same operator routes stays the wrong-role 403.
    assert client.get("/api/positions", headers=_PROD_H).status_code == 403
    assert client.get("/api/signals", headers=_PROD_H).status_code == 403


def test_non_ascii_credentials_are_invalid_not_error():
    # Auto-review round 5 (P2): secrets.compare_digest raises TypeError on a
    # non-ASCII str, which at request time would surface as a 500 instead of the
    # A-1 matrix's clean 401/403. Verified at the validator level (an HTTP client
    # ASCII-encodes header values, so the byte can only arrive via a raw client;
    # the reviewer's own evidence was operator_key_valid('é', ...) throwing).
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
    # No TypeError — a non-ASCII value is simply an unequal (invalid) credential.
    assert operator_key_valid("é", settings) is False
    assert producer_key_valid("é", settings) is False
    # And resolve_producer_id maps a non-ASCII producer key to a clean 401.
    with pytest.raises(HTTPException) as exc:
        resolve_producer_id(producer_key="é", operator_key=None, settings=settings)
    assert exc.value.status_code == 401


def test_operator_command_audit_actor_is_principal_not_forged_x_actor():
    # Auto-review round 5 (P1): with the seat flag ON, an operator command
    # route's AUDITED actor derives from the authenticated principal; a forged
    # X-Actor can only sub-label it, never replace it (LOCKED 04 §2 / A-1).
    # Proven end-to-end through middleware -> get_actor -> command facade ->
    # audit event. Uses the sync TestClient (runs lifespan) + its portal to read
    # the async store in the app's own loop.
    from app.models import EventType
    from app.store.memory import InMemoryStateStore

    store = InMemoryStateStore()
    app = build_flag_on_app(store=store)
    with TestClient(app) as c:
        r = c.post(
            "/api/controls/kill-switch",
            json={"engaged": True},
            headers={**_OP_H, "X-Actor": "totally-someone-else"},
        )
        assert r.status_code == 200, r.text
        events = c.portal.call(
            functools.partial(
                store.list_events, event_type=EventType.KILL_SWITCH_ENGAGED.value
            )
        )
    assert events, "no kill-switch audit event was written"
    # The forged X-Actor did NOT replace the authenticated operator principal.
    assert events[-1].payload["actor"] == "operator:totally-someone-else"


def test_invalid_operator_key_on_producer_route_is_401_not_403(client):
    # Auto-review round 5 (P2): resolve_producer_id returned 403 for ANY operator
    # key on POST /api/signals without validating it. 403 is reserved for a VALID
    # opposite-role credential; an unknown operator key is 401.
    r = client.post(
        "/api/signals", json=_proposal(), headers={"X-Operator-Key": "not-real"}
    )
    assert r.status_code == 401
    # A VALID operator key on the producer route stays the wrong-role 403.
    r2 = client.post("/api/signals", json=_proposal(), headers=_OP_H)
    assert r2.status_code == 403


def test_operator_middleware_covers_signals_subroutes_not_just_ingest(client):
    # Independent review F-1: the middleware skip is the EXACT producer ingest
    # (POST /api/signals) ONLY — not the whole /api/signals* subtree. A sub-path
    # (WO-0103's future approve/reject) must pass through operator enforcement so
    # authenticated_actor is stamped and the approval audit can't be X-Actor
    # spoofed. Proven via a nonexistent sub-path: the middleware answers before
    # routing, so no-auth is 401 (not a skipped-through 404).
    assert (
        client.post("/api/signals", json=_proposal(), headers=_PROD_H).status_code
        == 201  # the exact producer ingest is still skipped + producer-authed
    )
    assert client.get("/api/signals/vibe/sig-1/whatever").status_code == 401
    assert (
        client.get(
            "/api/signals/vibe/sig-1/whatever", headers=_PROD_H
        ).status_code
        == 403  # a producer key on an operator sub-route is the wrong-role 403
    )


def test_quarantine_symbol_is_normalized_and_findable(client):
    # Independent review F-2: a quarantine record's symbol is normalized (strip
    # +upper) like the well-formed path + the store filter, so it is findable by
    # GET /api/signals?symbol=AAPL rather than stored un-normalized as "aapl".
    r = client.post(
        "/api/signals",
        json={
            "signal_id": "sym-norm",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 300,
            "symbol": "aapl",
            "direction": "buy",
            "thesis": "x",
            "provenance": {"model": 1},  # the offender
        },
        headers=_PROD_H,
    )
    assert r.status_code == 422
    assert r.json()["symbol"] == "AAPL"
    found = client.get(
        "/api/signals",
        params={"status": "quarantined", "symbol": "AAPL"},
        headers=_OP_H,
    ).json()
    assert any(rec["signal_id"] == "sym-norm" for rec in found)


def test_synthetic_malformed_identity_is_colon_namespaced_and_unforgeable(client):
    # Independent review F-3: a no-signal_id malformed body gets a "malformed:"
    # identity, and the wire signal_id pattern (^[A-Za-z0-9_-]+$) forbids ':',
    # so a producer can never supply a well-formed signal_id that collides.
    r = client.post("/api/signals", json={"foo": 1}, headers=_PROD_H)
    assert r.status_code == 422
    assert r.json()["signal_id"].startswith("malformed:")
    r2 = client.post(
        "/api/signals", json=_proposal(signal_id="malformed:forged"), headers=_PROD_H
    )
    assert r2.status_code == 422  # ':' violates the wire pattern -> quarantined


def test_invalid_wire_signal_id_falls_back_to_synthetic_identity(client):
    # Round-12 A: a malformed body whose signal_id violates the wire pattern
    # (e.g. a forged "malformed:<hash>") must NOT be reused as the record identity
    # — it falls back to the content-hashed synthetic id, so a producer cannot
    # collide a second distinct malformed fact into a 409 with no new record.
    no_id = client.post("/api/signals", json={"foo": 1}, headers=_PROD_H)
    assert no_id.status_code == 422
    forged = no_id.json()["signal_id"]  # "malformed:<hash>"
    assert forged.startswith("malformed:")
    # A DIFFERENT malformed body carrying that value as signal_id must record its
    # OWN quarantine (distinct synthetic id), not 409-conflict onto the first.
    r = client.post(
        "/api/signals", json={"bar": 2, "signal_id": forged}, headers=_PROD_H
    )
    assert r.status_code == 422
    assert r.json()["signal_id"] != forged  # fell back to its own content hash


@pytest.mark.parametrize("bad_symbol", ["ß", "ı", "Å", "ＡＡＰＬ"])
def test_non_ascii_symbol_uppercasing_to_ascii_is_quarantined(client, bad_symbol):
    # Round-12 B: a Unicode symbol whose upper-case form is ASCII ('ß'->'SS',
    # 'ı'->'I') must be quarantined, NOT silently rewritten into a different
    # real ticker as a RECEIVED signal.
    r = client.post(
        "/api/signals", json=_proposal(symbol=bad_symbol), headers=_PROD_H
    )
    assert r.status_code == 422
    assert r.json()["quarantine_reason"] == "validation"


@pytest.mark.parametrize("bad_symbol", [".", ".AAPL", "-X", "1AAPL"])
def test_symbol_without_leading_letter_is_quarantined(client, bad_symbol):
    # Round-12 C: the wire symbol domain now matches the store's ?symbol= filter
    # (leading letter required), so an impossible instrument like "." is
    # quarantined, not stored RECEIVED and then unfilterable.
    r = client.post(
        "/api/signals", json=_proposal(symbol=bad_symbol), headers=_PROD_H
    )
    assert r.status_code == 422
    assert r.json()["quarantine_reason"] == "validation"


def test_valid_ticker_with_digits_or_dot_still_accepted(client):
    # Regression guard: real tickers with digits/'.'/'-' (BRK.B) are accepted.
    r = client.post("/api/signals", json=_proposal(symbol="BRK.B"), headers=_PROD_H)
    assert r.status_code == 201
    assert r.json()["symbol"] == "BRK.B"


def test_invalid_direction_is_not_surfaced_as_typed_data(client):
    # Round-12 D: a quarantine caused by an invalid direction must not surface the
    # out-of-domain value ("hold") as the record's typed direction.
    r = _post_json_bytes(
        client,
        {
            "signal_id": "dir-bad",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "hold",
            "thesis": "x",
            "provenance": {},
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["direction"] in ("buy", "sell")  # a representable enum value
    assert any("direction" in k for k in body["raw_fields"])  # offender kept


def test_surrogate_provenance_key_is_quarantined(client):
    # Round-12 E: a surrogate in a provenance KEY (not just a value) must take the
    # validation-quarantine path, not land as a RECEIVED signal that later 500s.
    r = _post_json_bytes(
        client,
        {
            "signal_id": "prov-key",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {"\ud800": "v"},
        },
    )
    assert r.status_code == 422
    assert r.json()["status"] == "quarantined"
    assert (
        client.get(
            "/api/signals", params={"status": "quarantined"}, headers=_OP_H
        ).status_code
        == 200
    )


def test_non_positive_ttl_on_combined_malformed_is_recorded(client):
    # Round-12 F: ttl_seconds has no wire gt=0 (range is server-owned), so a
    # non-positive ttl (0/negative) on a body quarantined for another field must
    # be nulled AND recorded as an offender — not silently dropped.
    r = _post_json_bytes(
        client,
        {
            "signal_id": "ttl-zero",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 0,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {"model": 1},  # the Pydantic offender
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["ttl_seconds"] is None
    assert any("ttl_seconds" in k for k in body["raw_fields"])  # 0 recorded


def test_valid_operator_with_stale_producer_header_is_403_not_401(client):
    # Auto-review round 6 (P2): a VALID operator key on the producer route is the
    # wrong-role 403 even when a stale/invalid X-Producer-Key is ALSO present —
    # the earlier `and producer_key is None` guard wrongly downgraded this to 401.
    r = client.post(
        "/api/signals",
        json=_proposal(),
        headers={**_OP_H, "X-Producer-Key": "stale-junk"},
    )
    assert r.status_code == 403


def test_out_of_range_advisory_is_nulled_on_quarantine_record_kept_in_raw_fields(
    client,
):
    # Auto-review round 6 (P2): a non-positive advisory (violating the schema's
    # gt=0) must be stored as None on the quarantine record — the offender is
    # already preserved verbatim in raw_fields, so surfacing it as normalized
    # typed data would contradict the field's own contract.
    r = client.post(
        "/api/signals",
        json={**_proposal(signal_id="adv"), "suggested_quantity": 0},
        headers=_PROD_H,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["suggested_quantity"] is None  # NOT surfaced as 0
    assert any("suggested_quantity" in k for k in body["raw_fields"])  # kept verbatim


def test_quarantine_for_other_field_preserves_valid_freshness_fields(client):
    # Auto-review round 8 (P2): a quarantine caused by a DIFFERENT field must
    # preserve valid issued_at/ttl_seconds on the record — SignalRecord nulls
    # freshness fields ONLY when the field itself is malformed.
    iso = datetime.now(timezone.utc).isoformat()
    r = client.post(
        "/api/signals",
        json={
            "signal_id": "adv-fresh",
            "issued_at": iso,
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {"model": 1},  # the ONLY offender
        },
        headers=_PROD_H,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["issued_at"] is not None  # valid freshness field preserved
    assert body["ttl_seconds"] == 300
    assert any("provenance" in k for k in body["raw_fields"])  # offender kept


def test_same_id_distinct_valid_issued_at_is_conflict_not_idempotent_replay(client):
    # The hash-distinctness half: two bodies, same signal_id + same offender,
    # differing ONLY in a VALID issued_at, must not collapse into one idempotent
    # 200 replay (which silently drops the second distinct fact) — the valid
    # issued_at is now folded into the dedup hash, so the second is a 409 conflict.
    base = {
        "signal_id": "dup-fresh",
        "ttl_seconds": 300,
        "symbol": "AAPL",
        "direction": "buy",
        "thesis": "x",
        "provenance": {"model": 1},  # offender in both
    }
    r1 = client.post(
        "/api/signals",
        json={**base, "issued_at": "2026-07-14T15:00:00+00:00"},
        headers=_PROD_H,
    )
    r2 = client.post(
        "/api/signals",
        json={**base, "issued_at": "2026-07-14T16:00:00+00:00"},
        headers=_PROD_H,
    )
    assert r1.status_code == 422
    assert r2.status_code == 409  # distinct payload -> conflict, NOT a 200 replay


def test_out_of_range_ttl_on_combined_malformed_is_nulled_and_recorded(client):
    # Auto-review round 10 (P2): a positive but OUT-OF-RANGE ttl_seconds on a body
    # quarantined for a DIFFERENT field must be nulled + recorded as an offender,
    # matching the freshness path's ttl_out_of_range handling — not surfaced as
    # normalized typed data.
    r = client.post(
        "/api/signals",
        json={
            "signal_id": "ttl-oor",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 5,  # positive but below the 30s minimum
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {"model": 1},  # the Pydantic offender
        },
        headers=_PROD_H,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["status"] == "quarantined"
    assert body["ttl_seconds"] is None  # out-of-range nulled
    assert any("ttl_seconds" in k for k in body["raw_fields"])  # recorded offender


def _post_json_bytes(client, body: dict):
    # A real producer's wire bytes: JSON with the surrogate as a \udXXX escape
    # (ensure_ascii=True → pure-ASCII bytes). The httpx client's own json=
    # encoder uses ensure_ascii=False and would itself raise on the surrogate, so
    # the value can only reach the SERVER via raw content, exactly as over HTTP.
    return client.post(
        "/api/signals",
        content=json.dumps(body).encode("ascii"),
        headers={**_PROD_H, "Content-Type": "application/json"},
    )


def test_unpaired_surrogate_string_does_not_poison_read_path(client):
    # Auto-review round 10 (P1): a thesis with an unpaired surrogate ("\ud800") is
    # rejected by Pydantic (validation branch); the raw value must NOT be copied
    # onto the stored record, or serializing the 422 response — and later
    # GET /api/signals?status=quarantined — would raise UnicodeEncodeError (500)
    # and poison the operator read path.
    r = _post_json_bytes(
        client,
        {
            "signal_id": "surr",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "\ud800",
            "provenance": {},
        },
    )
    assert r.status_code == 422
    assert r.json()["status"] == "quarantined"
    assert r.json()["thesis"] == ""  # surrogate NOT stored on the normalized field
    # The operator read path must stay 200, not 500 on the poisoned value.
    listed = client.get(
        "/api/signals", params={"status": "quarantined"}, headers=_OP_H
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_surrogate_in_provenance_value_is_escaped_not_500(client):
    # The same poisoning via a provenance VALUE must be escaped, not stored raw.
    r = _post_json_bytes(
        client,
        {
            "signal_id": "surr-prov",
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "ttl_seconds": 300,
            "symbol": "AAPL",
            "direction": "buy",
            "thesis": "x",
            "provenance": {"model": "\ud800", "bad": 1},  # surrogate + a real offender
        },
    )
    assert r.status_code == 422
    assert r.json()["status"] == "quarantined"
    # Escaped form is UTF-8-safe; the read path does not 500.
    assert (
        client.get(
            "/api/signals", params={"status": "quarantined"}, headers=_OP_H
        ).status_code
        == 200
    )


def test_get_signals_status_query_param_actually_filters(client):
    # Auto-reviewer P2 #2: the query param is documented/contracted as `status`
    # (04-auth-and-api.md §2: "parameters: [status: SignalStatus = received, ...]")
    # — it must actually filter, not be silently ignored under a mismatched
    # internal parameter name.
    client.post("/api/signals", json=_proposal(signal_id="a"), headers=_PROD_H)
    client.post(
        "/api/signals",
        json=_proposal(signal_id="b", ttl_seconds=5),  # -> quarantined (ttl range)
        headers=_PROD_H,
    )
    # The DEFAULT (no `?status=`) is the RECEIVED actionable queue, per the
    # LOCKED 04 §2 contract — NOT every status. So a bare list returns only "a".
    default_records = client.get("/api/signals", headers=_OP_H).json()
    assert len(default_records) == 1
    assert default_records[0]["signal_id"] == "a"

    received_only = client.get(
        "/api/signals", params={"status": "received"}, headers=_OP_H
    ).json()
    assert len(received_only) == 1
    assert received_only[0]["signal_id"] == "a"

    quarantined_only = client.get(
        "/api/signals", params={"status": "quarantined"}, headers=_OP_H
    ).json()
    assert len(quarantined_only) == 1
    assert quarantined_only[0]["signal_id"] == "b"


def test_get_signals_bad_symbol_is_422_not_500(client):
    # Auto-reviewer P2 #4: normalize_symbol's bare ValueError must never leak
    # as an unmapped 500.
    r = client.get("/api/signals", params={"symbol": "bad$"}, headers=_OP_H)
    assert r.status_code == 422


def test_get_signals_invalid_status_value_rejected(client):
    r = client.get(
        "/api/signals", params={"status": "not-a-real-status"}, headers=_OP_H
    )
    assert r.status_code == 422


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


def test_module_app_attribute_absent_under_flag():
    # Auto-reviewer P1 #7: a module-level `app = None` is INSUFFICIENT — uvicorn's
    # `getattr(module, "app")` happily returns None and can still end up binding a
    # socket. The name must be UNDEFINED so `getattr` raises AttributeError inside
    # uvicorn's `Config.load()`, before any listener opens (see
    # test_signal_seat_launcher.py for the socket-level empirical proof).
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.main; print('HAS_APP', hasattr(app.main, 'app'))",
        ],
        env={"SIGNAL_SEAT_ENABLED": "true", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert proc.returncode == 0, proc.stderr
    assert "HAS_APP False" in proc.stdout
