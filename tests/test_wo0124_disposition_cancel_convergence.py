"""WO-0124 — durable, bounded envelope-disposition cancel convergence.

The contract spans the whole cancellation lifetime: the decision is persisted
before venue IO, survives a restart even when stale market data later clears,
targets only an exact projection-validated child identity, spends no reprice
budget, and escalates to the existing recovery ledger after a bounded number of
direct attempts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import app.monitoring as monitoring
from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.marketdata.fake import FakeMarketDataFeed
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.reconciliation import ENVELOPE_EXEC_SUBMITTED, execute_envelope_action
from app.sellside import policy as sellside_policy
from app.sellside.types import ActionKind, PlannedAction, StaleDataSignal
from app.store.core import project_envelope_obligation
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

# Wednesday 2026-07-15 14:00 UTC = 10:00 ET REGULAR.  Keep the injected
# decision clock behind local ingest time and inside the session rails.
NOW = datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc)
EXPIRY_CANCEL = "expiry_cancel_and_return"
STALE_CANCEL = "stale_data_cancel"


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
        cooldown_floor_ms=1,
        cancel_replace_budget=1,
        expires_at=NOW + timedelta(days=1),
        allowed_session_phases=list(SessionType),
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )


def _planned() -> PlannedAction:
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=10,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


async def _active_envelope(store) -> ExecutionEnvelope:
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )
    intent = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return await store.approve_envelope_activation(
        _draft(intent.id), actor="operator-wo0124"
    )


async def _submitted_child(store) -> tuple[ExecutionEnvelope, Order]:
    envelope = await _active_envelope(store)
    result = await execute_envelope_action(
        store,
        MockBrokerAdapter(),
        envelope.id,
        _planned(),
        snapshot_fingerprint="wo0124-submit",
        now=NOW,
    )
    assert result.outcome == ENVELOPE_EXEC_SUBMITTED, result.detail
    assert result.order_id is not None
    order = await store.get_order(result.order_id)
    assert order is not None and order.broker_order_id is not None
    return envelope, order


def _cancel_events(
    events: list[ExecutionEvent], envelope_id: str, order_id: str
) -> list[ExecutionEvent]:
    return [
        event
        for event in events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
        and event.envelope_id == envelope_id
        and event.order_id == order_id
        and event.payload.get("action") == "cancel"
    ]


def _manual_cancel_event(
    envelope: ExecutionEnvelope,
    order: Order,
    *,
    broker_order_id: str | None = None,
    attempt: int = 1,
) -> ExecutionEvent:
    target_broker_id = broker_order_id or order.broker_order_id
    assert target_broker_id is not None
    return ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=(
            f"envelope:{envelope.id}:disposition_cancel:"
            f"{order.id}:{EXPIRY_CANCEL}:{attempt}"
        ),
        ts_event=NOW + timedelta(seconds=attempt),
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        quantity=order.quantity,
        price=order.limit_price,
        order_id=order.id,
        envelope_id=envelope.id,
        session_id=envelope.session_id,
        correlation_id=envelope.sell_intent_id,
        payload={
            "action": "cancel",
            "actor": "engine",
            "disposition": EXPIRY_CANCEL,
            "broker_order_id": target_broker_id,
            "attempt": attempt,
        },
    )


def test_disposition_cancel_does_not_spend_reprice_budget() -> None:
    events = [
        ExecutionEvent(
            event_type=ExecutionEventType.ENVELOPE_ACTION,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            envelope_id="env",
            payload={"action": "cancel"},
        ),
        ExecutionEvent(
            event_type=ExecutionEventType.ENVELOPE_ACTION,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            envelope_id="env",
            payload={"action": "reprice"},
        ),
    ]

    assert sellside_policy.project_envelope_replaces_used(events) == {"env": 1}


async def test_cancel_event_is_durable_before_venue_io_and_replayable(any_store):
    envelope, order = await _submitted_child(any_store)
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        actor="engine",
        reason="wo0124-expiry",
        now=NOW + timedelta(seconds=1),
    )

    class EventObservingAdapter(MockBrokerAdapter):
        observed_before_call = False

        async def cancel_order(self, broker_order_id: str) -> None:
            events = await any_store.get_execution_events()
            self.observed_before_call = bool(
                _cancel_events(events, envelope.id, order.id)
            )
            await super().cancel_order(broker_order_id)

    adapter = EventObservingAdapter()
    await monitoring._converge_expired_envelope_cancels(any_store, adapter)

    assert adapter.observed_before_call is True
    [event] = _cancel_events(
        await any_store.get_execution_events(), envelope.id, order.id
    )
    assert event.payload == {
        "action": "cancel",
        "actor": "engine",
        "disposition": EXPIRY_CANCEL,
        "broker_order_id": order.broker_order_id,
        "attempt": 1,
    }
    assert event.envelope_id == envelope.id
    assert event.order_id == order.id
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCEL_PENDING


async def test_cancel_event_is_non_minting_and_preserves_exact_child_projection(
    any_store,
):
    envelope, order = await _submitted_child(any_store)
    events = await any_store.get_execution_events()
    action_events = [
        event
        for event in events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
    ]
    action_events.append(_manual_cancel_event(envelope, order))

    projection = project_envelope_obligation(
        envelopes=[envelope],
        action_events=action_events,
        orders_by_id={order.id: order},
        order_events=[
            event
            for event in events
            if event.order_id == order.id
            and event.event_type is not ExecutionEventType.ENVELOPE_ACTION
        ],
    )

    assert projection.invalid_order_ids == ()
    assert [item.id for item in projection.venue_orders] == [order.id]


async def test_cancel_event_with_foreign_broker_identity_fails_projection_closed(
    any_store,
):
    envelope, order = await _submitted_child(any_store)
    events = await any_store.get_execution_events()
    action_events = [
        event
        for event in events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
    ]
    action_events.append(
        _manual_cancel_event(envelope, order, broker_order_id="foreign-broker-id")
    )

    projection = project_envelope_obligation(
        envelopes=[envelope],
        action_events=action_events,
        orders_by_id={order.id: order},
        order_events=[
            event
            for event in events
            if event.order_id == order.id
            and event.event_type is not ExecutionEventType.ENVELOPE_ACTION
        ],
    )

    assert projection.invalid_order_ids == (order.id,)


async def test_stale_cancel_failure_persists_intent_and_retries_after_data_clears(
    any_store, monkeypatch
):
    envelope, order = await _submitted_child(any_store)
    market_data = FakeMarketDataFeed()
    market_data.set_snapshot("AAPL", last_price=9.8, bid=9.79, ask=9.81)
    adapter = MockBrokerAdapter()
    adapter.fail_next_cancel(BrokerError("injected stale-disposition failure"))
    monkeypatch.setattr(
        monitoring,
        "decide",
        lambda *_args, **_kwargs: StaleDataSignal(EnvelopeStaleDataDisposition.CANCEL),
    )

    await monitoring._run_one_envelope(
        any_store,
        adapter,
        market_data,
        envelope,
        tapes=monitoring.EnvelopeTapeBuffer(),
        snap_memo={},
        now=NOW + timedelta(seconds=1),
    )

    [event] = _cancel_events(
        await any_store.get_execution_events(), envelope.id, order.id
    )
    assert event.payload["disposition"] == STALE_CANCEL
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED

    # No stale signal is presented again. Durable intent alone must drive retry.
    converger = getattr(
        monitoring,
        "_converge_envelope_disposition_cancels",
        monitoring._converge_expired_envelope_cancels,
    )
    retry_adapter = MockBrokerAdapter()
    await converger(any_store, retry_adapter)
    assert retry_adapter.canceled == [order.broker_order_id]
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCEL_PENDING


async def test_stale_cancel_failure_then_sqlite_restart_converges(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "wo0124-stale-restart.db"
    first = SqliteStateStore(db_path)
    envelope, order = await _submitted_child(first)
    market_data = FakeMarketDataFeed()
    market_data.set_snapshot("AAPL", last_price=9.8, bid=9.79, ask=9.81)
    adapter = MockBrokerAdapter()
    adapter.fail_next_cancel(BrokerError("injected pre-crash cancel failure"))
    monkeypatch.setattr(
        monitoring,
        "decide",
        lambda *_args, **_kwargs: StaleDataSignal(EnvelopeStaleDataDisposition.CANCEL),
    )
    await monitoring._run_one_envelope(
        first,
        adapter,
        market_data,
        envelope,
        tapes=monitoring.EnvelopeTapeBuffer(),
        snap_memo={},
        now=NOW + timedelta(seconds=1),
    )
    assert (
        len(_cancel_events(await first.get_execution_events(), envelope.id, order.id))
        == 1
    )
    await first.close()

    reopened = SqliteStateStore(db_path)
    await reopened.initialize()
    try:
        retry_adapter = MockBrokerAdapter()
        converger = getattr(
            monitoring,
            "_converge_envelope_disposition_cancels",
            monitoring._converge_expired_envelope_cancels,
        )
        await converger(reopened, retry_adapter)
        assert retry_adapter.canceled == [order.broker_order_id]
        assert (await reopened.get_order(order.id)).status is OrderStatus.CANCEL_PENDING
        attempts = _cancel_events(
            await reopened.get_execution_events(), envelope.id, order.id
        )
        assert [event.payload["attempt"] for event in attempts] == [1, 2]
    finally:
        await reopened.close()


async def test_direct_cancel_retries_are_bounded_then_escalate_once(any_store):
    envelope, order = await _submitted_child(any_store)
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        actor="engine",
        reason="wo0124-expiry",
        now=NOW + timedelta(seconds=1),
    )

    class AlwaysFailCancelAdapter(MockBrokerAdapter):
        async def cancel_order(self, broker_order_id: str) -> None:
            attempts = _cancel_events(
                await any_store.get_execution_events(), envelope.id, order.id
            )
            assert len(attempts) == len(self.canceled) + 1
            self.canceled.append(broker_order_id)
            raise BrokerError("injected persistent disposition-cancel failure")

    adapter = AlwaysFailCancelAdapter()
    for _ in range(5):
        await monitoring._converge_expired_envelope_cancels(any_store, adapter)

    assert adapter.canceled == [order.broker_order_id] * 3
    attempts = _cancel_events(
        await any_store.get_execution_events(), envelope.id, order.id
    )
    assert [event.payload["attempt"] for event in attempts] == [1, 2, 3]
    recoveries = await any_store.list_submit_recoveries(
        statuses={RECOVERY_NEEDS_REVIEW}
    )
    assert len(recoveries) == 1
    [recovery] = recoveries
    assert recovery.cleanup_status == RECOVERY_NEEDS_REVIEW
    assert recovery.local_order_id == order.id
    assert recovery.broker_order_id == order.broker_order_id
    assert recovery.session_id == order.session_id == envelope.session_id
    assert recovery.symbol == order.symbol == envelope.symbol
    assert recovery.side is order.side is OrderSide.SELL
    assert recovery.quantity == order.quantity
    assert recovery.limit_price == order.limit_price
    assert recovery.failure_reason == "envelope_disposition_cancel_exhausted"

    audits = [
        event
        for event in await any_store.list_events()
        if event.payload.get("action_kind") == "envelope_disposition_cancel_exhausted"
    ]
    assert len(audits) == 1
    assert audits[0].payload["envelope_id"] == envelope.id

    # A terminal human-review latch is visible but excluded from the automatic
    # submit-recovery loop, whose semantics are for otherwise-untracked submits.
    await monitoring._recover_unpersisted_submits(any_store, adapter)
    assert adapter.canceled == [order.broker_order_id] * 3


async def test_failed_human_escalation_never_reopens_venue_authority(
    any_store, monkeypatch
):
    envelope, order = await _submitted_child(any_store)
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        actor="engine",
        reason="wo0124-expiry",
        now=NOW + timedelta(seconds=1),
    )

    class AlwaysFailCancelAdapter(MockBrokerAdapter):
        async def cancel_order(self, broker_order_id: str) -> None:
            self.canceled.append(broker_order_id)
            raise BrokerError("injected persistent disposition-cancel failure")

    async def fail_escalation(**_kwargs):
        raise RuntimeError("injected recovery-ledger write failure")

    monkeypatch.setattr(any_store, "create_submit_recovery", fail_escalation)
    adapter = AlwaysFailCancelAdapter()
    for _ in range(5):
        await monitoring._converge_envelope_disposition_cancels(any_store, adapter)

    assert adapter.canceled == [order.broker_order_id] * 3
    attempts = _cancel_events(
        await any_store.get_execution_events(), envelope.id, order.id
    )
    assert [event.payload["attempt"] for event in attempts] == [1, 2, 3]
    assert await any_store.list_submit_recoveries() == []
