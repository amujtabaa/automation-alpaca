"""WO-0124 — durable, bounded envelope-disposition cancel convergence.

The contract spans the whole cancellation lifetime: the decision is persisted
before venue IO, survives a restart even when stale market data later clears,
targets only an exact projection-validated child identity, spends no reprice
budget, and escalates to the existing recovery ledger after a bounded number of
direct attempts.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import app.monitoring as monitoring
import app.store.core as store_core
from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
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
            "target_snapshot": [
                {
                    "order_id": order.id,
                    "broker_order_id": target_broker_id,
                }
            ],
        },
    )


@pytest.mark.parametrize(
    "target_snapshot",
    [
        ["not-an-identity-pair"],
        [
            {"order_id": "order-b", "broker_order_id": "broker-b"},
            {"order_id": "order-a", "broker_order_id": "broker-a"},
        ],
        [
            {"order_id": "order-a", "broker_order_id": "broker-a"},
            {"order_id": "order-a", "broker_order_id": "broker-b"},
        ],
        [
            {"order_id": "order-a", "broker_order_id": "broker-a"},
            {"order_id": "order-b", "broker_order_id": "broker-a"},
        ],
    ],
    ids=[
        "malformed-pair",
        "noncanonical-order",
        "duplicate-local-order",
        "duplicate-broker-order",
    ],
)
async def test_cancel_target_snapshot_rejects_noncanonical_identity_sets(
    target_snapshot,
):
    """Exact venue authority requires one canonical one-to-one identity set."""

    assert (
        store_core._cancel_target_snapshot({"target_snapshot": target_snapshot}) is None
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
        "target_snapshot": [
            {
                "order_id": order.id,
                "broker_order_id": order.broker_order_id,
            }
        ],
    }
    assert event.envelope_id == envelope.id
    assert event.order_id == order.id
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCEL_PENDING


async def test_concurrent_exact_cancel_attempt_accepts_dedupe_winner_timestamp(
    any_store, monkeypatch
):
    """A benign same-key loser must stand down, not turn into a policy fault."""

    envelope, order = await _submitted_child(any_store)
    assert order.broker_order_id is not None
    events = await any_store.get_execution_events()
    original_append = any_store.append_execution_event
    arrivals = 0
    release = asyncio.Event()
    clock_tick = 0

    def advancing_clock():
        nonlocal clock_tick
        value = NOW + timedelta(microseconds=clock_tick)
        clock_tick += 1
        return value

    async def collide_after_both_drafts_exist(event: ExecutionEvent):
        nonlocal arrivals
        arrivals += 1
        if arrivals == 2:
            release.set()
        await release.wait()
        return await original_append(event)

    monkeypatch.setattr(monitoring, "utcnow", advancing_clock)
    monkeypatch.setattr(
        any_store, "append_execution_event", collide_after_both_drafts_exist
    )
    target_snapshot = ((order.id, order.broker_order_id),)

    results = await asyncio.gather(
        monitoring._persist_disposition_cancel_attempt(
            any_store,
            envelope=envelope,
            order=order,
            disposition=STALE_CANCEL,
            events=list(events),
            target_snapshot=target_snapshot,
        ),
        monitoring._persist_disposition_cancel_attempt(
            any_store,
            envelope=envelope,
            order=order,
            disposition=STALE_CANCEL,
            events=list(events),
            target_snapshot=target_snapshot,
        ),
    )

    assert sorted(results, key=lambda item: item is None) == [1, None]
    attempts = _cancel_events(
        await any_store.get_execution_events(), envelope.id, order.id
    )
    assert len(attempts) == 1
    assert attempts[0].payload["attempt"] == 1


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


async def _close_first_child(
    store,
    adapter: MockBrokerAdapter | None = None,
) -> tuple[ExecutionEnvelope, Order, MockBrokerAdapter]:
    """Close child A with a durable cancel and broker-authoritative terminal."""

    envelope, first = await _submitted_child(store)
    adapter = adapter or MockBrokerAdapter()
    await monitoring._cancel_envelope_working_order(
        store,
        adapter,
        envelope,
        disposition=STALE_CANCEL,
    )
    assert adapter.canceled == [first.broker_order_id]
    await monitoring._reconcile_open_orders(store, adapter, Settings())
    closed = await store.get_order(first.id)
    assert closed is not None and closed.status is OrderStatus.CANCELED
    return envelope, first, adapter


async def _submit_future_child(
    store,
    envelope: ExecutionEnvelope,
    adapter: MockBrokerAdapter,
) -> Order:
    """Submit child B after A's exact cancel obligation has converged."""

    result = await execute_envelope_action(
        store,
        adapter,
        envelope.id,
        _planned(),
        snapshot_fingerprint="wo0124-future-child",
        now=NOW + timedelta(seconds=2),
    )
    assert result.outcome == ENVELOPE_EXEC_SUBMITTED, result.detail
    assert result.order_id is not None
    future = await store.get_order(result.order_id)
    assert future is not None and future.broker_order_id is not None
    return future


async def _assert_historical_cancel_does_not_retarget_future_child(store) -> None:
    envelope, first, adapter = await _close_first_child(store)
    future = await _submit_future_child(store, envelope, adapter)
    assert future.id != first.id

    await monitoring._converge_envelope_disposition_cancels(store, adapter)

    # The durable cancel fact names child A. It is not standing envelope-wide
    # authority and must never be reused against later child B.
    assert adapter.canceled == [first.broker_order_id]
    fresh_future = await store.get_order(future.id)
    assert fresh_future is not None and fresh_future.status is OrderStatus.SUBMITTED
    assert (
        _cancel_events(await store.get_execution_events(), envelope.id, future.id) == []
    )


async def test_historical_cancel_never_retargets_future_child(any_store):
    await _assert_historical_cancel_does_not_retarget_future_child(any_store)


async def test_historical_cancel_never_retargets_future_child_after_sqlite_restart(
    tmp_path,
):
    db_path = tmp_path / "wo0124-historical-cancel-scope.db"
    first_store = SqliteStateStore(db_path)
    envelope, first, _adapter = await _close_first_child(first_store)
    await first_store.close()

    reopened = SqliteStateStore(db_path)
    await reopened.initialize()
    try:
        # Mint B only after restart. The persisted event for A, not an in-memory
        # selection, is therefore the only old cancel authority available.
        adapter = MockBrokerAdapter()
        future = await _submit_future_child(reopened, envelope, adapter)
        assert future.id != first.id
        await monitoring._converge_envelope_disposition_cancels(reopened, adapter)

        assert adapter.canceled == []
        fresh_future = await reopened.get_order(future.id)
        assert fresh_future is not None
        assert fresh_future.status is OrderStatus.SUBMITTED
        assert (
            _cancel_events(
                await reopened.get_execution_events(), envelope.id, future.id
            )
            == []
        )
    finally:
        await reopened.close()


async def test_expiry_without_current_child_event_scopes_before_venue_io(any_store):
    class EventObservingAdapter(MockBrokerAdapter):
        target_broker_order_id: str | None = None
        target_order_id: str | None = None
        observed_exact_event = False

        async def cancel_order(self, broker_order_id: str) -> None:
            if broker_order_id == self.target_broker_order_id:
                events = await any_store.get_execution_events()
                [event] = _cancel_events(
                    events,
                    envelope.id,
                    self.target_order_id or "<missing-target>",
                )
                self.observed_exact_event = (
                    event.envelope_id == envelope.id
                    and event.order_id == self.target_order_id
                    and event.payload.get("disposition") == EXPIRY_CANCEL
                    and event.payload.get("broker_order_id") == broker_order_id
                )
            await super().cancel_order(broker_order_id)

    adapter = EventObservingAdapter()
    envelope, first, _ = await _close_first_child(any_store, adapter)
    future = await _submit_future_child(any_store, envelope, adapter)
    adapter.target_broker_order_id = future.broker_order_id
    adapter.target_order_id = future.id
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        actor="engine",
        reason="wo0124-expiry-after-prior-stale-cancel",
        now=NOW + timedelta(seconds=3),
    )

    # Model a crash after the terminal envelope transition but before the first
    # child-B expiry event. Convergence must discover only current child B, then
    # persist its exact identity before acquiring venue authority.
    assert (
        _cancel_events(await any_store.get_execution_events(), envelope.id, future.id)
        == []
    )
    await monitoring._converge_envelope_disposition_cancels(any_store, adapter)

    assert adapter.observed_exact_event is True
    assert adapter.canceled == [first.broker_order_id, future.broker_order_id]
    assert (
        len(
            _cancel_events(
                await any_store.get_execution_events(), envelope.id, first.id
            )
        )
        == 1
    )
    [future_cancel] = _cancel_events(
        await any_store.get_execution_events(), envelope.id, future.id
    )
    assert future_cancel.payload["disposition"] == EXPIRY_CANCEL
    fresh_future = await any_store.get_order(future.id)
    assert fresh_future is not None
    assert fresh_future.status is OrderStatus.CANCEL_PENDING


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


@pytest.mark.parametrize(
    "terminal_status",
    [OrderStatus.CANCELED, OrderStatus.FILLED],
    ids=["cancel-ack", "fill"],
)
@pytest.mark.parametrize(
    "response_lost",
    [False, True],
    ids=["adapter-returned", "adapter-raised-after-terminal"],
)
async def test_third_cancel_transition_race_revalidates_terminal_truth(
    any_store, terminal_status, response_lost
):
    envelope, order = await _submitted_child(any_store)
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.EXPIRED,
        actor="engine",
        reason="wo0124-third-attempt-terminal-race",
        now=NOW + timedelta(seconds=1),
    )

    class TerminalOnThirdCancelAdapter(MockBrokerAdapter):
        async def cancel_order(self, broker_order_id: str) -> None:
            self.canceled.append(broker_order_id)
            if len(self.canceled) < 3:
                raise BrokerError("injected pre-terminal cancel failure")
            if terminal_status is OrderStatus.FILLED:
                fill_id = "wo0124-third-cancel-race-fill"
                await any_store.record_envelope_fill(
                    envelope.id,
                    quantity=order.quantity,
                    dedupe_key=fill_id,
                    order_id=order.id,
                    price=order.limit_price,
                    now=NOW + timedelta(seconds=4),
                )
                await any_store.append_fill(
                    order.id,
                    order.symbol,
                    order.side,
                    order.quantity,
                    order.limit_price,
                    source_fill_id=fill_id,
                    filled_at=NOW + timedelta(seconds=4),
                    session_id=order.session_id,
                )
                await any_store.transition_order(
                    order.id,
                    OrderStatus.FILLED,
                    filled_quantity=order.quantity,
                )
            else:
                await any_store.transition_order(order.id, OrderStatus.CANCELED)
            if response_lost:
                raise BrokerError("injected lost response after terminal truth")

    adapter = TerminalOnThirdCancelAdapter()
    for _ in range(4):
        await monitoring._converge_envelope_disposition_cancels(any_store, adapter)

    assert adapter.canceled == [order.broker_order_id] * 3
    terminal = await any_store.get_order(order.id)
    assert terminal is not None and terminal.status is terminal_status
    attempts = _cancel_events(
        await any_store.get_execution_events(), envelope.id, order.id
    )
    assert [event.payload["attempt"] for event in attempts] == [1, 2, 3]
    assert await any_store.list_submit_recoveries() == []


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
