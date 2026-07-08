"""X-004 — the full protective-exit lifecycle shares one correlation_id.

Before this fix, the generic event writer defaulted ``correlation_id`` from
``candidate_id`` only — always ``None`` for a sell order (XOR origin) — so
every order/fill/recovery event downstream of creation (claim, blocked-claim,
submitted, stale, fill, recovery) lost the ``sell_intent_id`` key.
``GET /api/events?correlation_id=<sell_intent_id>`` returned only the creation
events, never the actual execution trail. Both stores now resolve
``correlation_id`` from the owning order's ``sell_intent_id`` whenever
``candidate_id`` is absent, for every event that carries an ``order_id`` —
verified end-to-end here through the real monitoring-loop functions (not just
the sell-intent planners, which already set it explicitly).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import app.monitoring as monitoring
from app.broker.adapter import BrokerFill
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
    utcnow,
)
from app.monitoring import _reconcile_open_orders, _submit_pending_orders

pytestmark = pytest.mark.anyio


async def _hold(store, symbol, qty, avg=10.0):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)


async def _events_for(store, intent_id):
    return await store.list_events(correlation_id=intent_id)


async def test_full_protective_exit_lifecycle_shares_correlation_id(
    any_store, monkeypatch
):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    session = await any_store.get_current_session()

    # created -> approved -> ordered.
    intent = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    order = await any_store.create_order_for_sell_intent(
        intent.id, order_type=OrderType.MARKET
    )
    assert order.status is OrderStatus.CREATED

    adapter = MockBrokerAdapter()
    settings = Settings()
    # Force regular-hours so the MARKET sell submits as-is (§5.4) regardless
    # of the sandbox's real wall-clock time.
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)

    # blocked-claim: kill-switched, so a PROTECTION_FLOOR claim is held.
    await any_store.set_kill_switch(True)
    await _submit_pending_orders(any_store, adapter, settings, market_data=None)
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED

    # claim -> submitted: release the switch and submit.
    await any_store.set_kill_switch(False)
    await _submit_pending_orders(any_store, adapter, settings, market_data=None)
    submitted = await any_store.get_order(order.id)
    assert submitted.status is OrderStatus.SUBMITTED
    broker_id = submitted.broker_order_id
    assert broker_id is not None

    # stale: a frozen, deterministic "now" well past created_at (see the B-2
    # fix in test_monitoring.py for why a real unfrozen clock is flaky here).
    frozen_now = submitted.created_at + timedelta(minutes=120)
    monkeypatch.setattr("app.monitoring.utcnow", lambda: frozen_now)
    await _reconcile_open_orders(
        any_store, adapter, Settings(unfilled_timeout_minutes=1.0), market_data=None
    )

    # fill: queue a partial fill and reconcile again.
    adapter.make_fill(
        order.id,
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=40,
        fills=[BrokerFill("exec-1", 40, 9.5, utcnow())],
    )
    await _reconcile_open_orders(
        any_store, adapter, Settings(unfilled_timeout_minutes=1.0), market_data=None
    )

    # needs_review: escalate a broker-submit divergence for this same order.
    await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=broker_id,
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        failure_reason="submit accepted but local persist failed",
        cleanup_status=RECOVERY_NEEDS_REVIEW,
        candidate_id=None,
    )

    events = await _events_for(any_store, intent.id)
    event_types = {e.event_type for e in events}

    # Every stage of the lifecycle is present AND correlated.
    assert "sell_intent_created" in event_types
    assert "sell_intent_transition" in event_types
    assert "order_created" in event_types
    assert "order_submission_blocked" in event_types
    assert "order_submission_claimed" in event_types
    assert "order_transition" in event_types  # CREATED->SUBMITTING/SUBMITTED
    assert "order_stale" in event_types
    assert "fill_appended" in event_types
    assert "submit_recovery_recorded" in event_types

    # Every one of these events (fetched BY correlation_id) really does carry
    # it — a sanity check that list_events' filter isn't silently permissive.
    for event in events:
        assert event.correlation_id == intent.id


async def test_manual_flatten_lifecycle_also_correlates(any_store, monkeypatch):
    """The same property for a MANUAL_FLATTEN exit (not just PROTECTION_FLOOR) —
    flatten_position (X-001) produces events through the identical shared
    dispatch helper, so this is mostly a parity/regression guard."""

    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    result = await any_store.flatten_position("AAPL")
    assert result.intent.reason is SellReason.MANUAL_FLATTEN

    adapter = MockBrokerAdapter()
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)
    await _submit_pending_orders(any_store, adapter, Settings(), market_data=None)
    submitted = await any_store.get_order(result.order.id)
    assert submitted.status is OrderStatus.SUBMITTED

    events = await _events_for(any_store, result.intent.id)
    event_types = {e.event_type for e in events}
    assert "sell_intent_created" in event_types
    assert "order_created" in event_types
    assert "order_submission_claimed" in event_types
    for event in events:
        assert event.correlation_id == result.intent.id
