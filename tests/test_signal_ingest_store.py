"""WO-0102 — Signal ingestion at the store layer (ADR-009 spec 01/02).

Dual-store (memory + sqlite via ``any_store``) + replay: accept→RECEIVED, dedupe
on (producer_id, signal_id) incl. cross-producer, malformed→quarantine, freshness
skew/ttl quarantine, dead-on-arrival expiry, and event-truth replay parity.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.events.projectors import PositionProjector, project_signal_records
from app.models import ExecutionEventType, SignalStatus
from app.store.core import (
    SIGNAL_CONFLICT,
    SIGNAL_EXPIRED_AT_INGEST,
    SIGNAL_QUARANTINED_FRESHNESS,
    SIGNAL_QUARANTINED_VALIDATION,
    SIGNAL_RECEIVED_OK,
    SIGNAL_REPLAYED,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 14, 15, 0, tzinfo=timezone.utc)
_MAX_TTL = 3600
_BUDGET = 50


def _valid_kwargs(**over):
    base = dict(
        producer_id="vibe",
        signal_id="sig-1",
        symbol="AAPL",
        direction="buy",
        issued_at=_NOW,
        ttl_seconds=300,
        suggested_quantity=10,
        suggested_limit_price=100.0,
        thesis="momentum breakout",
        provenance={"model": "gpt"},
        server_max_ttl_seconds=_MAX_TTL,
        cycle_budget_limit=_BUDGET,
        received_at=_NOW,
    )
    base.update(over)
    return base


async def _events_of(store, etype):
    return [e for e in await store.get_execution_events() if e.event_type is etype]


async def test_accept_received(any_store):
    await any_store.initialize()
    res = await any_store.ingest_signal(**_valid_kwargs())
    assert res.outcome == SIGNAL_RECEIVED_OK
    assert res.record.status is SignalStatus.RECEIVED
    # expires_at = min(received + max_ttl, issued + ttl) = issued + 300s here.
    assert res.record.expires_at == _NOW + timedelta(seconds=300)
    got = await any_store.get_signal("vibe", "sig-1")
    assert got == res.record
    assert len(await _events_of(any_store, ExecutionEventType.SIGNAL_RECEIVED)) == 1


async def test_idempotent_replay_same_payload(any_store):
    await any_store.initialize()
    first = await any_store.ingest_signal(**_valid_kwargs())
    again = await any_store.ingest_signal(**_valid_kwargs())
    assert again.outcome == SIGNAL_REPLAYED
    assert again.record.id == first.record.id
    # No second SIGNAL_RECEIVED event (idempotent, mirrors client_order_id).
    assert len(await _events_of(any_store, ExecutionEventType.SIGNAL_RECEIVED)) == 1


async def test_duplicate_conflict_audit_only(any_store):
    await any_store.initialize()
    first = await any_store.ingest_signal(**_valid_kwargs())
    # Same (producer_id, signal_id), different content → conflict.
    conflict = await any_store.ingest_signal(**_valid_kwargs(thesis="different"))
    assert conflict.outcome == SIGNAL_CONFLICT
    # Original record untouched, no second row.
    rows = await any_store.list_signals()
    assert len(rows) == 1
    assert rows[0].thesis == "momentum breakout"
    assert rows[0].id == first.record.id
    # One audit-only conflict event; still only one SIGNAL_RECEIVED.
    assert (
        len(await _events_of(any_store, ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT))
        == 1
    )
    assert len(await _events_of(any_store, ExecutionEventType.SIGNAL_RECEIVED)) == 1


async def test_conflict_replay_coalesced(any_store):
    await any_store.initialize()
    await any_store.ingest_signal(**_valid_kwargs())
    await any_store.ingest_signal(**_valid_kwargs(thesis="different"))
    await any_store.ingest_signal(**_valid_kwargs(thesis="different"))
    # Same (producer, signal, new_hash) conflict is coalesced to ONE event.
    assert (
        len(await _events_of(any_store, ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT))
        == 1
    )


async def test_cross_producer_same_signal_id_distinct(any_store):
    await any_store.initialize()
    a = await any_store.ingest_signal(**_valid_kwargs(producer_id="A", signal_id="x"))
    b = await any_store.ingest_signal(**_valid_kwargs(producer_id="B", signal_id="x"))
    assert a.outcome == SIGNAL_RECEIVED_OK
    assert b.outcome == SIGNAL_RECEIVED_OK  # NOT a conflict — distinct namespace
    assert a.record.id != b.record.id
    assert len(await any_store.list_signals()) == 2


async def test_malformed_validation_quarantine(any_store):
    await any_store.initialize()
    res = await any_store.ingest_signal(
        **_valid_kwargs(
            signal_id="bad",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "not-a-date"},
        )
    )
    assert res.outcome == SIGNAL_QUARANTINED_VALIDATION
    assert res.record.status is SignalStatus.QUARANTINED
    assert res.record.quarantine_reason == "validation"
    assert res.record.issued_at is None
    assert res.record.expires_at is None
    assert res.record.raw_fields == {"issued_at": "not-a-date"}
    events = await _events_of(any_store, ExecutionEventType.SIGNAL_QUARANTINED)
    assert len(events) == 1
    # Attributable-rejection event carries cycle_budget_limit (WO-0104 folds it).
    assert events[0].payload["cycle_budget_limit"] == _BUDGET


async def test_distinct_malformed_content_same_signal_id_is_conflict_not_replay(
    any_store,
):
    # Auto-reviewer P1 #1: the malformed-with-usable-signal_id case. The route
    # normalizes issued_at/ttl_seconds to None for EVERY malformed body
    # regardless of what was actually sent, so two requests differing only in
    # their raw offending content (issued_at="not-date" vs "also-not-date")
    # must NOT hash identically — that would make the second a silent 200
    # replay with no new event and no invalid-budget debit, discarding a
    # distinct attributable fact. Including raw_fields in the hash makes the
    # second correctly a SIGNAL_DUPLICATE_CONFLICT (audit-only, budget-debiting,
    # per 02-lifecycle §2's "novel-hash SIGNAL_DUPLICATE_CONFLICT" — NOT a second
    # SIGNAL_QUARANTINED row: (producer_id, signal_id) stays a true unique key,
    # 01-schema §3, "works in every signal status").
    await any_store.initialize()
    first = await any_store.ingest_signal(
        **_valid_kwargs(
            signal_id="sig-x",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "not-date"},
        )
    )
    assert first.outcome == SIGNAL_QUARANTINED_VALIDATION

    second = await any_store.ingest_signal(
        **_valid_kwargs(
            signal_id="sig-x",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "also-not-date"},
        )
    )
    assert second.outcome == SIGNAL_CONFLICT  # NOT SIGNAL_REPLAYED (the P1 #1 bug)

    quarantine_events = await _events_of(any_store, ExecutionEventType.SIGNAL_QUARANTINED)
    assert len(quarantine_events) == 1  # only the first creation

    conflict_events = await _events_of(
        any_store, ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT
    )
    assert len(conflict_events) == 1  # the second distinct fact IS recorded
    assert conflict_events[0].payload["cycle_budget_limit"] == _BUDGET

    # (producer_id, signal_id) stays a true unique key — one row, the original.
    rows = await any_store.list_signals()
    assert len(rows) == 1
    assert rows[0].raw_fields == {"issued_at": "not-date"}  # untouched by the conflict


async def test_identical_malformed_content_same_signal_id_still_idempotent(any_store):
    # Regression guard: an EXACT resubmission (same raw_fields) of the malformed
    # body is still a legitimate idempotent replay, not a conflict.
    await any_store.initialize()
    kwargs = _valid_kwargs(
        signal_id="sig-y",
        issued_at=None,
        ttl_seconds=None,
        validation_failed=True,
        raw_fields={"issued_at": "not-date"},
    )
    first = await any_store.ingest_signal(**kwargs)
    second = await any_store.ingest_signal(**kwargs)
    assert first.outcome == SIGNAL_QUARANTINED_VALIDATION
    assert second.outcome == SIGNAL_REPLAYED
    assert first.record.id == second.record.id
    assert len(await any_store.list_signals()) == 1


async def test_dedupe_key_no_ambiguous_collision_across_signal_ids(any_store):
    # Auto-reviewer P1 #2: a naive ':'-joined dedupe key makes ('a:b', 'c') and
    # ('a', 'b:c') both encode to "signal_create:a:b:c" — a validation-quarantine
    # can carry an arbitrary raw signal_id containing ':'. Both must produce
    # DISTINCT ExecutionEvent dedupe keys, so both creation events are appended
    # (not silently swallowed as a false duplicate) and BOTH rows persist.
    await any_store.initialize()
    r1 = await any_store.ingest_signal(**_valid_kwargs(producer_id="a:b", signal_id="c"))
    r2 = await any_store.ingest_signal(**_valid_kwargs(producer_id="a", signal_id="b:c"))
    assert r1.outcome == SIGNAL_RECEIVED_OK
    assert r2.outcome == SIGNAL_RECEIVED_OK  # NOT a false duplicate of r1
    assert r1.record.id != r2.record.id

    received_events = await _events_of(any_store, ExecutionEventType.SIGNAL_RECEIVED)
    assert len(received_events) == 2  # both creation events actually appended

    rows = await any_store.list_signals()
    assert len(rows) == 2
    keys = {(r.producer_id, r.signal_id) for r in rows}
    assert keys == {("a:b", "c"), ("a", "b:c")}

    # Replay parity: both stores reconstruct both distinct records identically.
    projected = project_signal_records(await any_store.get_execution_events())
    assert set(projected) == {("a:b", "c"), ("a", "b:c")}


@pytest.mark.parametrize(
    "over,reason",
    [
        (dict(ttl_seconds=10), "ttl_out_of_range"),
        (dict(ttl_seconds=999999), "ttl_out_of_range"),
        (dict(issued_at=_NOW + timedelta(minutes=5)), "issued_at_future"),
        (dict(issued_at=_NOW - timedelta(hours=48)), "issued_at_stale"),
    ],
)
async def test_freshness_quarantine(any_store, over, reason):
    await any_store.initialize()
    res = await any_store.ingest_signal(**_valid_kwargs(signal_id="f", **over))
    assert res.outcome == SIGNAL_QUARANTINED_FRESHNESS
    assert res.record.status is SignalStatus.QUARANTINED
    assert res.record.quarantine_reason == reason


async def test_dead_on_arrival_expired(any_store):
    await any_store.initialize()
    # issued 60s ago, ttl 30s → issued+ttl = now-30s <= now → DOA (and not stale).
    res = await any_store.ingest_signal(
        **_valid_kwargs(
            signal_id="doa", issued_at=_NOW - timedelta(seconds=60), ttl_seconds=30
        )
    )
    assert res.outcome == SIGNAL_EXPIRED_AT_INGEST
    assert res.record.status is SignalStatus.EXPIRED
    events = await _events_of(any_store, ExecutionEventType.SIGNAL_EXPIRED)
    assert events[0].payload["detected_by"] == "ingest"


async def test_signals_do_not_touch_position(any_store):
    await any_store.initialize()
    await any_store.ingest_signal(**_valid_kwargs())
    # INV-1/INV-9: no SIGNAL_* event folds into position.
    proj = PositionProjector.project(await any_store.get_execution_events())
    assert proj.positions == {}
    assert await any_store.list_positions() == []


async def test_replay_reconstructs_records(any_store):
    await any_store.initialize()
    await any_store.ingest_signal(**_valid_kwargs(signal_id="s1"))
    await any_store.ingest_signal(**_valid_kwargs(signal_id="s2", symbol="MSFT"))
    await any_store.ingest_signal(
        **_valid_kwargs(signal_id="s3", validation_failed=True,
                        issued_at=None, ttl_seconds=None, raw_fields={"x": "y"})
    )
    # A duplicate-conflict must NOT disturb the original on replay.
    await any_store.ingest_signal(**_valid_kwargs(signal_id="s1", thesis="changed"))

    projected = project_signal_records(await any_store.get_execution_events())
    live = {(r.producer_id, r.signal_id): r for r in await any_store.list_signals()}
    assert projected == live
    # s1 stayed RECEIVED with the original thesis despite the conflict.
    assert projected[("vibe", "s1")].thesis == "momentum breakout"
    assert projected[("vibe", "s1")].status is SignalStatus.RECEIVED


async def test_dual_store_parity(tmp_path):
    mem = InMemoryStateStore()
    sql = SqliteStateStore(tmp_path / "signals.db")
    for store in (mem, sql):
        await store.initialize()
        await store.ingest_signal(**_valid_kwargs(signal_id="s1"))
        await store.ingest_signal(**_valid_kwargs(signal_id="s2", symbol="MSFT"))
        await store.ingest_signal(**_valid_kwargs(signal_id="s1", thesis="changed"))
        await store.ingest_signal(
            **_valid_kwargs(signal_id="doa",
                            issued_at=_NOW - timedelta(seconds=60), ttl_seconds=30)
        )
    # Cross-store: content is identical modulo the random server ``id`` (both
    # stores independently mint a uuid — legitimately non-deterministic). Every
    # deterministic field, including the created/updated timestamps tied to the
    # injected clock, matches. (Within each store, replay is byte-identical incl.
    # id — proven by test_replay_reconstructs_records.)
    def _content(records):
        return {
            (r.producer_id, r.signal_id): r.model_dump(exclude={"id"})
            for r in records.values()
        }

    mem_proj = project_signal_records(await mem.get_execution_events())
    sql_proj = project_signal_records(await sql.get_execution_events())
    assert _content(mem_proj) == _content(sql_proj)
    mem_live = {(r.producer_id, r.signal_id): r for r in await mem.list_signals()}
    sql_live = {(r.producer_id, r.signal_id): r for r in await sql.list_signals()}
    assert _content(mem_live) == _content(sql_live)
    if sql._conn is not None:
        sql._conn.close()


async def test_sqlite_survives_reopen(tmp_path):
    path = tmp_path / "reopen.db"
    store = SqliteStateStore(path)
    await store.initialize()
    await store.ingest_signal(**_valid_kwargs())
    store._conn.close()
    store._conn = None

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    got = await reopened.get_signal("vibe", "sig-1")
    assert got is not None and got.status is SignalStatus.RECEIVED
    # expires_at reconstructs identically after restart (persisted, never re-derived).
    assert got.expires_at == _NOW + timedelta(seconds=300)
    reopened._conn.close()
