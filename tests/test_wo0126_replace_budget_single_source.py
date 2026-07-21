"""WO-0126 — one event-derived replace-budget truth for policy and display.

The observable invariant spans the envelope lifetime and a SQLite restart:
``ENVELOPE_ACTION`` history is the only application source for the count.  The
legacy SQLite column is deliberately treated as hostile input so a future read
or cache dependency cannot silently reappear.
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest

import app.sellside.policy as sellside_policy
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.store_backed import StoreBackedQueryFacade
from app.main import create_app
from app.marketdata.fake import FakeMarketDataFeed
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    SellReason,
    SessionType,
    utcnow,
)
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


def _event(
    envelope_id: str | None,
    action: str,
    *,
    event_type: ExecutionEventType = ExecutionEventType.ENVELOPE_ACTION,
) -> ExecutionEvent:
    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL",
        side=OrderSide.SELL,
        envelope_id=envelope_id,
        payload={"action": action},
    )


def _ratified_reprice_count(events: list[ExecutionEvent], envelope_id: str) -> int:
    """D-0124: wind-down cancels are evented but only reprices spend budget."""

    return sum(
        1
        for event in events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
        and event.envelope_id == envelope_id
        and event.payload.get("action") == "reprice"
    )


def test_shared_projection_matches_the_complete_incumbent_action_corpus() -> None:
    events = [
        _event("env-1", "submit"),
        _event("env-1", "reprice"),
        _event("env-1", "cancel"),
        _event("env-1", "resize"),
        _event("env-1", "refused_stale"),
        _event("env-1", "future_unknown"),
        _event("env-2", "reprice"),
        _event(None, "cancel"),
        _event("env-1", "reprice", event_type=ExecutionEventType.ACCEPTED),
    ]

    projected = sellside_policy.project_envelope_replaces_used(events)

    assert projected == {"env-1": 1, "env-2": 1}
    assert projected["env-1"] == _ratified_reprice_count(events, "env-1")
    assert projected["env-2"] == _ratified_reprice_count(events, "env-2")
    assert _ratified_reprice_count(events, "missing") == projected.get("missing", 0)


def _draft(intent_id: str) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=750,
        cancel_replace_budget=5,
        expires_at=utcnow() + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )


async def _active_envelope(store) -> ExecutionEnvelope:
    await store.initialize()
    owner = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return await store.approve_envelope_activation(
        _draft(owner.id), actor="operator-wo0126"
    )


async def _append_action(store, envelope: ExecutionEnvelope, action: str) -> None:
    await store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.ENVELOPE_ACTION,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            symbol=envelope.symbol,
            side=OrderSide.SELL,
            envelope_id=envelope.id,
            session_id=envelope.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={"action": action},
        )
    )


def _api_app(store):
    app = create_app(store)
    app.state.store = store
    app.state.broker_adapter = MockBrokerAdapter()
    app.state.market_data = FakeMarketDataFeed()
    app.state.settings = Settings()
    return app


async def test_http_read_projects_usage_from_each_store(any_store) -> None:
    envelope = await _active_envelope(any_store)
    for action in ("submit", "reprice", "refused_stale", "cancel"):
        await _append_action(any_store, envelope, action)

    app = _api_app(any_store)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/envelopes")

    assert response.status_code == 200, response.text
    [row] = response.json()
    assert row["replaces_used"] == 1
    assert row["cancel_replace_budget"] == 5
    assert "replaces_used" not in ExecutionEnvelope.model_fields


async def test_facade_calls_the_same_projection_used_by_policy(
    any_store, monkeypatch
) -> None:
    envelope = await _active_envelope(any_store)
    calls: list[list[ExecutionEvent]] = []

    def sentinel(events) -> dict[str, int]:
        materialized = list(events)
        calls.append(materialized)
        return {envelope.id: 17}

    monkeypatch.setattr(sellside_policy, "project_envelope_replaces_used", sentinel)

    [view] = await StoreBackedQueryFacade(any_store).list_envelopes()

    assert view.replaces_used == 17
    assert len(calls) == 1


async def test_sqlite_restart_ignores_hostile_legacy_column(tmp_path) -> None:
    db_path = tmp_path / "wo0126-reopen.db"
    first = SqliteStateStore(db_path)
    envelope = await _active_envelope(first)
    for action in ("reprice", "refused_stale", "cancel"):
        await _append_action(first, envelope, action)

    assert first._conn is not None
    first._conn.execute(
        "UPDATE execution_envelopes SET replaces_used = 999 WHERE id = ?",
        (envelope.id,),
    )
    first._conn.commit()
    await first.close()

    reopened = SqliteStateStore(db_path)
    await reopened.initialize()
    try:
        [view] = await StoreBackedQueryFacade(reopened).list_envelopes()
        stored = await reopened.get_envelope(envelope.id)
        assert view.replaces_used == 1
        assert stored is not None
        assert not hasattr(stored, "replaces_used")
    finally:
        await reopened.close()
