"""WO-0102 — the malformed-input → quarantine boundary as a TOTAL invariant.

This closes the "one quarantine finding per review round" treadmill by asserting
the whole class at once, over a broad corpus of hostile/malformed bodies:

  For ANY authenticated producer sending ANY parseable JSON body, the endpoint
  records a terminal SIGNAL_QUARANTINED (HTTP 422) whose SignalRecord
    (a) constructs without raising,
    (b) has EVERY typed field domain-valid OR a documented sentinel/None — never
        out-of-domain typed data,
    (c) round-trips through the JSON response AND the operator read path with no
        UnicodeEncodeError / 500, and
    (d) has a stable identity: distinct bodies never collide as idempotent
        replays, and a producer cannot squat the synthetic-id namespace.

Any new field or edge that violates this fails HERE, immediately — instead of
surfacing as the next round's review comment.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.store.base import _SYMBOL_RE
from app.store.core import SIGNAL_TTL_MAX_SECONDS, SIGNAL_TTL_MIN_SECONDS
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore
from tests.signal_seat_helpers import OPERATOR_KEY, PRODUCER_KEY, build_flag_on_app

_PROD_H = {"X-Producer-Key": PRODUCER_KEY}
_OP_H = {"X-Operator-Key": OPERATOR_KEY}


# BOTH stores (proactive review P1-2): the SQLite quarantine path overflowed on a
# huge int while memory accepted it — a parity break the memory-only test missed.
# The totality invariant must hold identically on both.
@pytest.fixture(params=["memory", "sqlite"])
def client(request, tmp_path):
    if request.param == "memory":
        store = InMemoryStateStore()
    else:
        store = SqliteStateStore(tmp_path / "totality.db")
    with TestClient(build_flag_on_app(store=store)) as c:
        yield c


def _post(client, body):
    # Send raw bytes with the surrogate as a \udXXX escape (ensure_ascii=True) so
    # the value reaches the SERVER exactly as a real producer's wire bytes would —
    # httpx's own json= encoder (ensure_ascii=False) would itself raise on it.
    return client.post(
        "/api/signals",
        content=json.dumps(body).encode("ascii"),
        headers={**_PROD_H, "Content-Type": "application/json"},
    )


def _is_utf8_safe(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        value.encode("utf-8")
        return True
    except UnicodeEncodeError:
        return False


def _assert_representable_quarantine(rec: dict) -> None:
    """Every typed field is domain-valid or a documented sentinel/None, and the
    whole record is UTF-8-serializable (the operator read path won't 500)."""

    assert rec["status"] == "quarantined"
    assert isinstance(rec["quarantine_reason"], str) and rec["quarantine_reason"]

    # Identity: wire-valid signal_id OR the synthetic "malformed:" namespace.
    sid = rec["signal_id"]
    assert isinstance(sid, str) and sid
    import re

    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", sid) or sid.startswith("malformed:")

    # symbol: store ticker domain OR the UNKNOWN sentinel.
    assert rec["symbol"] == "UNKNOWN" or _SYMBOL_RE.fullmatch(rec["symbol"])
    # direction: strictly the enum.
    assert rec["direction"] in ("buy", "sell")
    # ttl_seconds: None OR in the server range.
    assert rec["ttl_seconds"] is None or (
        SIGNAL_TTL_MIN_SECONDS <= rec["ttl_seconds"] <= SIGNAL_TTL_MAX_SECONDS
    )
    # advisory: None OR strictly positive.
    for adv in ("suggested_quantity", "suggested_limit_price"):
        assert rec[adv] is None or rec[adv] > 0
    # thesis + provenance: UTF-8-safe.
    assert _is_utf8_safe(rec["thesis"])
    prov = rec["provenance"]
    assert isinstance(prov, dict)
    for k, v in prov.items():
        assert _is_utf8_safe(k) and _is_utf8_safe(v)
    # raw_fields: a non-empty, UTF-8-safe dict (the offenders, preserved).
    assert isinstance(rec["raw_fields"], dict) and rec["raw_fields"]
    for k, v in rec["raw_fields"].items():
        assert _is_utf8_safe(k) and _is_utf8_safe(v)
    # The whole record must UTF-8-encode the way FastAPI serializes it.
    json.dumps(rec, ensure_ascii=False).encode("utf-8")


# A broad corpus of malformed-but-parseable bodies (each fails validation for at
# least one reason). Every one must satisfy the totality invariant.
_ISO = "2026-07-14T15:00:00+00:00"
_BASE = {
    "signal_id": "sig-x",
    "issued_at": _ISO,
    "ttl_seconds": 300,
    "symbol": "AAPL",
    "direction": "buy",
    "thesis": "x",
    "provenance": {},
}


def _m(**over):
    return {**_BASE, **over}


_MALFORMED_CORPUS = [
    # Non-object top-level shapes.
    [], [1, 2, 3], "hello", 123, 12.5, True, None, {},
    # Unrelated / missing required fields.
    {"foo": 1}, {"signal_id": "s"}, {"bar": 2},
    # signal_id domain.
    _m(signal_id=""), _m(signal_id="   "), _m(signal_id=" sig-x "),
    _m(signal_id="has space"), _m(signal_id="malformed:forged"),
    _m(signal_id="a" * 65), _m(signal_id="bad/slash"), _m(signal_id=123),
    # symbol domain (case, non-ASCII, no-leading-letter, oversize, upper-to-ascii).
    _m(symbol="aapl"), _m(symbol="."), _m(symbol="$BAD"), _m(symbol="1X"),
    _m(symbol="TOOLONGSYMBOL"), _m(symbol="ß"), _m(symbol="ı"), _m(symbol="Å"),
    _m(symbol="ＡＡＰＬ"), _m(symbol=""), _m(symbol=42),
    # direction — incl. UNHASHABLE types (must not TypeError->500, review P1-1).
    _m(direction="hold"), _m(direction=""), _m(direction=1), _m(direction=None),
    _m(direction=["buy"]), _m(direction={"buy": 1}),
    # issued_at.
    _m(issued_at=1752505200), _m(issued_at="1784059129"),
    _m(issued_at="2026-07-14T15:00:00"), _m(issued_at="not-a-date"),
    _m(issued_at=None),
    # ttl.
    _m(ttl_seconds=0), _m(ttl_seconds=-5), _m(ttl_seconds=5),
    _m(ttl_seconds=999999), _m(ttl_seconds="300"), _m(ttl_seconds=True),
    # advisory — incl. an int ABOVE SQLite's signed-64-bit range (must not
    # OverflowError->500 on sqlite / diverge from memory, review P1-2).
    _m(suggested_quantity=0), _m(suggested_quantity=-1), _m(suggested_quantity=True),
    _m(suggested_quantity="5"), _m(suggested_quantity=10**20),
    _m(suggested_quantity=2**63), _m(suggested_limit_price=0),
    _m(suggested_limit_price=-1.5), _m(suggested_limit_price="1.0"),
    _m(suggested_limit_price=1e308),
    # thesis / provenance (incl. surrogates + oversize + bad types).
    _m(thesis=""), _m(thesis="\ud800"), _m(thesis="x" * 5000),
    _m(provenance={"\ud800": "v"}), _m(provenance={"k": "\ud800"}),
    _m(provenance={"model": 1}), _m(provenance="notadict"),
    _m(provenance={"k": "v" * 600}), _m(provenance={str(i): "v" for i in range(25)}),
    # combined multi-field malformed.
    {"signal_id": "  ", "symbol": "ß", "direction": "hold", "ttl_seconds": 0,
     "issued_at": 5, "provenance": {"\ud800": 1}, "thesis": "\ud800"},
]


@pytest.mark.parametrize(
    "body", _MALFORMED_CORPUS, ids=[str(i) for i in range(len(_MALFORMED_CORPUS))]
)
def test_any_body_yields_a_representable_record(client, body):
    # The UNIVERSAL invariant across all outcomes: a parseable body is either a
    # validation-quarantine (422), a well-formed-but-unfresh quarantine or a valid
    # signal (201), or an idempotent replay (200) — NEVER a 400/500-and-forget.
    r = _post(client, body)
    assert r.status_code in (200, 201, 422), f"{body!r} -> {r.status_code}: {r.text[:200]}"
    rec = r.json()
    if rec.get("status") == "quarantined":
        _assert_representable_quarantine(rec)
    # Neither operator read path may 500 on any stored record, and every
    # quarantined record listed must be representable.
    for status_filter in ("quarantined", "received"):
        listed = client.get(
            "/api/signals", params={"status": status_filter}, headers=_OP_H
        )
        assert listed.status_code == 200
        if status_filter == "quarantined":
            for q in listed.json():
                _assert_representable_quarantine(q)


def test_distinct_malformed_bodies_never_collide_as_replays(client):
    # Every distinct body in the corpus that lacks a wire-valid signal_id must get
    # its OWN record (distinct identity), never coalesce into one another as an
    # idempotent 200 replay — the "lost distinct fact" class.
    seen_ids = set()
    distinct_bodies = [
        {"foo": 1}, {"bar": 2}, {"baz": 3},
        _m(signal_id="  "), _m(signal_id=" pad "), _m(signal_id="malformed:forged"),
        [1], [2], "a", "b",
    ]
    for i, body in enumerate(distinct_bodies):
        r = _post(client, body)
        assert r.status_code == 422, f"{body!r}"
        sid = r.json()["id"]  # store row id
        assert sid not in seen_ids, f"collision: {body!r} reused id {sid}"
        seen_ids.add(sid)


def test_identical_malformed_body_is_idempotent_replay(client):
    # The flip side: an EXACT resend of the same malformed body is a legitimate
    # idempotent replay (200), not a second record.
    body = {"foo": 1, "same": "content"}
    r1 = _post(client, body)
    r2 = _post(client, body)
    assert r1.status_code == 422
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
