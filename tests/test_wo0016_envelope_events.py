"""WO-0016 — envelope event provenance (ADR-008/ADR-010 §6) round-trip, BOTH
stores, plus the additive ``envelope_id`` schema migration.

Provenance contract: every envelope LIFECYCLE fact is a local single-writer
engine decision (``ENGINE``/``LOCAL``) with the commanding actor stamped in
the payload (operator-* rows for create/approve are data plumbing here; the
approval *flow* is WO-0017). Envelope FILL facts stay broker-authoritative
(``BROKER_REST``/``BROKER_AUTHORITATIVE``) exactly like order fills.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EXECUTION_EVENT_SCHEMA_VERSION,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
    utcnow,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
NOW = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)


def make_draft(intent_id: str = "si-1") -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.50,
        trail_distance_min=0.05,
        trail_distance_max=0.25,
        participation_rate_cap=0.20,
        aggressiveness=["passive", "mid"],
        cooldown_floor_ms=750,
        cancel_replace_budget=40,
        expires_at=utcnow() + timedelta(hours=2),
        allowed_session_phases=[SessionType.PRE_MARKET, SessionType.AFTER_HOURS],
        expiry_disposition=EnvelopeExpiryDisposition.REST_AT_FLOOR,
        stale_data_disposition=EnvelopeStaleDataDisposition.LEAVE_RESTING,
        session_id="sess-1",
    )


async def create_owned_envelope(store, *, actor: str = "system"):
    draft = make_draft()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        draft.qty_ceiling,
        session_id=session.id,
    )
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        draft.qty_ceiling,
        10.0,
        source_fill_id=f"wo0016-event-hold:{candidate.id}",
        session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    owner = await store.create_sell_intent(
        symbol=draft.symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=draft.qty_ceiling,
        session_id=session.id,
    )
    return await store.create_envelope(
        draft.model_copy(
            update={
                "sell_intent_id": owner.id,
                "session_id": session.id,
                "expires_at": NOW + timedelta(hours=2),
            }
        ),
        actor=actor,
    )


async def stage_child(store, env: ExecutionEnvelope):
    staged = await store.stage_envelope_action(
        env.id,
        PlannedAction(
            kind=ActionKind.SUBMIT,
            limit_price=9.9,
            quantity=env.qty_ceiling,
            regime=None,
            urgency=0.0,
            working_stop=9.5,
            atr=0.05,
            tranche=False,
            stop_triggered=False,
        ),
        snapshot_fingerprint=f"wo0016-events:{env.id}",
        now=NOW,
    )
    return staged.order


async def test_created_event_snapshots_full_bounds_with_operator_actor(any_store):
    await any_store.initialize()
    env = await any_store.create_envelope(make_draft(), actor="operator-ameen")

    events = await any_store.get_execution_events()
    created = next(
        e for e in events if e.event_type is ExecutionEventType.ENVELOPE_CREATED
    )
    assert created.source is EventSource.ENGINE
    assert created.authority is EventAuthority.LOCAL
    assert created.envelope_id == env.id
    assert created.correlation_id == "si-1"
    assert created.session_id == "sess-1"
    assert created.schema_version == EXECUTION_EVENT_SCHEMA_VERSION
    assert created.dedupe_key == f"envelope:{env.id}:created"
    # The payload alone reconstructs the approved mandate (replayability, §6).
    p = created.payload
    assert p["actor"] == "operator-ameen"
    assert p["qty_ceiling"] == 100
    assert p["floor_price"] == 9.50
    assert p["trail_distance_min"] == 0.05
    assert p["trail_distance_max"] == 0.25
    assert p["participation_rate_cap"] == 0.20
    assert p["aggressiveness"] == ["passive", "mid"]
    assert p["cooldown_floor_ms"] == 750
    assert p["cancel_replace_budget"] == 40
    assert p["max_outstanding_children"] == 1
    assert p["allowed_session_phases"] == ["pre_market", "after_hours"]
    assert p["expiry_disposition"] == "rest_at_floor"
    assert p["stale_data_disposition"] == "leave_resting"


async def test_lifecycle_provenance_and_expiry_disposition_round_trip(any_store):
    await any_store.initialize()
    env = await create_owned_envelope(any_store, actor="operator-ameen")
    await any_store.transition_envelope(env.id, S.APPROVED, actor="operator-ameen")
    await any_store.transition_envelope(env.id, S.ACTIVE)
    await any_store.transition_envelope(env.id, S.EXPIRED, reason="ttl lapsed")

    events = [
        e for e in await any_store.get_execution_events() if e.envelope_id == env.id
    ]
    assert all(e.source is EventSource.ENGINE for e in events)
    assert all(e.authority is EventAuthority.LOCAL for e in events)

    approved = next(
        e for e in events if e.event_type is ExecutionEventType.ENVELOPE_APPROVED
    )
    assert approved.payload["actor"] == "operator-ameen"
    assert approved.dedupe_key == f"envelope:{env.id}:approved"

    expired = next(
        e for e in events if e.event_type is ExecutionEventType.ENVELOPE_EXPIRED
    )
    # The approval-time mandatory choice this expiry now applies (§6).
    assert expired.payload["expiry_disposition"] == "rest_at_floor"
    assert expired.payload["reason"] == "ttl lapsed"


async def test_fill_events_stay_broker_authoritative(any_store):
    await any_store.initialize()
    env = await create_owned_envelope(any_store)
    await any_store.transition_envelope(env.id, S.APPROVED)
    await any_store.transition_envelope(env.id, S.ACTIVE)
    order = await stage_child(any_store, env)
    await any_store.record_envelope_fill(
        env.id,
        quantity=10,
        dedupe_key=f"fill:{order.id}:p1",
        price=9.9,
        order_id=order.id,
    )
    fill = next(
        e
        for e in await any_store.get_execution_events()
        if e.envelope_id == env.id and e.event_type is ExecutionEventType.FILL
    )
    assert fill.source is EventSource.BROKER_REST
    assert fill.authority is EventAuthority.BROKER_AUTHORITATIVE
    assert fill.order_id == order.id
    assert fill.quantity == 10


async def test_envelope_survives_reopen_with_events_intact(tmp_path):
    """SQLite only: the persisted envelope + its event trail survive a real
    close/reopen (restart persistence), and the reopened store keeps
    enforcing the machine."""

    path = tmp_path / "envelopes.db"
    store = SqliteStateStore(path)
    await store.initialize()
    env = await create_owned_envelope(store, actor="operator-ameen")
    await store.transition_envelope(env.id, S.APPROVED)
    await store.transition_envelope(env.id, S.ACTIVE)
    order = await stage_child(store, env)
    await store.record_envelope_fill(
        env.id,
        quantity=25,
        dedupe_key=f"fill:{order.id}:r1",
        order_id=order.id,
        price=9.9,
    )
    store._conn.close()
    store._conn = None

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    back = await reopened.get_envelope(env.id)
    assert back is not None
    assert back.status is S.ACTIVE
    assert back.remaining_quantity == 75
    assert back.aggressiveness == ["passive", "mid"]
    assert back.allowed_session_phases == [
        SessionType.PRE_MARKET,
        SessionType.AFTER_HOURS,
    ]
    assert back.expiry_disposition is EnvelopeExpiryDisposition.REST_AT_FLOOR

    # Dedupe map survives restart: the same fill replayed is still a no-op.
    again = await reopened.record_envelope_fill(
        env.id,
        quantity=25,
        dedupe_key=f"fill:{order.id}:r1",
        order_id=order.id,
        price=9.9,
    )
    assert again.remaining_quantity == 75

    events = await reopened.get_execution_events()
    kinds = [e.event_type for e in events if e.envelope_id == env.id]
    assert kinds == [
        ExecutionEventType.ENVELOPE_CREATED,
        ExecutionEventType.ENVELOPE_APPROVED,
        ExecutionEventType.ENVELOPE_ACTIVATED,
        ExecutionEventType.ENVELOPE_ACTION,
        ExecutionEventType.FILL,
    ]
    reopened._conn.close()
    reopened._conn = None


async def test_pre_envelope_db_gains_envelope_id_column_by_migration(tmp_path):
    """A database created BEFORE WO-0016 (execution_events without
    envelope_id, no execution_envelopes table) must open cleanly: _migrate
    adds the nullable column, old events read back with envelope_id=None,
    and envelope operations work immediately."""

    import sqlite3 as sqlite3_mod

    path = tmp_path / "legacy.db"
    conn = sqlite3_mod.connect(path)
    # A minimal pre-W3 execution_events table (the WO-0007-era shape).
    conn.executescript(
        """
        CREATE TABLE execution_events (
            id              TEXT PRIMARY KEY,
            sequence        INTEGER NOT NULL UNIQUE,
            schema_version  INTEGER NOT NULL,
            event_type      TEXT NOT NULL,
            source          TEXT NOT NULL,
            authority       TEXT NOT NULL,
            dedupe_key      TEXT UNIQUE,
            ts_event        TEXT,
            ts_init         TEXT NOT NULL,
            symbol          TEXT,
            side            TEXT,
            quantity        INTEGER,
            price           REAL,
            order_id        TEXT,
            primary_id      TEXT,
            spawn_id        TEXT,
            session_id      TEXT,
            correlation_id  TEXT,
            payload         TEXT NOT NULL DEFAULT '{}'
        );
        INSERT INTO execution_events
            (id, sequence, schema_version, event_type, source, authority,
             dedupe_key, ts_event, ts_init, symbol, side, quantity, price,
             order_id, primary_id, spawn_id, session_id, correlation_id, payload)
        VALUES
            ('ev-legacy', 1, 1, 'fill', 'broker_rest', 'broker_authoritative',
             'fill:o0:legacy', NULL, '2026-07-01T00:00:00+00:00', 'AAPL',
             'sell', 5, 10.0, 'o0', NULL, NULL, NULL, NULL, '{}');
        """
    )
    conn.commit()
    conn.close()

    store = SqliteStateStore(path)
    await store.initialize()
    legacy = next(e for e in await store.get_execution_events() if e.id == "ev-legacy")
    assert legacy.envelope_id is None  # additive column, NULL for old rows

    env = await store.create_envelope(make_draft())
    assert (await store.get_envelope(env.id)).status is S.PENDING
    store._conn.close()
    store._conn = None
