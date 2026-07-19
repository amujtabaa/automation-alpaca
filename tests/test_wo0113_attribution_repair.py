"""WO-0113 append-only repair for fills first persisted without an envelope.

The canonical position ``FILL`` is immutable.  If its record-first envelope
bridge was missed, replay may apply that fact to exactly one uniquely bounded
envelope by appending a separately deduped, non-position-folding attribution
marker.  Every pin runs against both stores.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.broker.adapter import BrokerFill, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    CandidateStatus,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellReason,
    SessionType,
)
from app.monitoring import (
    _apply_inferred_fills,
    _apply_update,
    _repair_unattributed_envelope_fills,
    run_monitoring_tick,
)
from app.reconciliation import InferredFill
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import CLAIM_CLAIMED, InvalidFillError

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 17, 18, 0, tzinfo=timezone.utc)
FILL_TIME = NOW + timedelta(minutes=1)
APPLY_TIME = NOW + timedelta(minutes=2)
ATTRIBUTION_TYPE = "envelope_fill_attributed"


@pytest.fixture(autouse=True)
def _regular_session_clock(monkeypatch):
    """Keep claim-time revalidation inside the deterministic regular session."""

    monkeypatch.setattr("app.store.memory.utcnow", lambda: NOW)
    monkeypatch.setattr("app.store.sqlite.utcnow", lambda: NOW)


def _draft(intent_id: str, session_id: str) -> ExecutionEnvelope:
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
        cancel_replace_budget=3,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _submit_action() -> PlannedAction:
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=100,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _submitted_envelope_child(store):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        100,
        session_id=session.id,
    )
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        100,
        10.0,
        source_fill_id=f"wo0113-hold:{candidate.id}",
        filled_at=NOW,
        session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    await store.transition_candidate(candidate.id, CandidateStatus.EXPIRED)

    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _draft(intent.id, session.id), actor="wo0113"
    )
    staged = await store.stage_envelope_action(
        envelope.id,
        _submit_action(),
        snapshot_fingerprint="wo0113-attribution-repair",
        now=NOW,
    )
    claim = await store.claim_order_for_submission(staged.order.id)
    assert claim.outcome == CLAIM_CLAIMED, claim.reason
    submitted = await store.transition_order(
        staged.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{staged.order.id}",
    )
    return session, envelope, submitted


def _canonical_key(order_id: str, source_fill_id: str) -> str:
    return f"fill:{order_id}:{source_fill_id}"


def _marker_key(fill_dedupe_key: str) -> str:
    return f"envelope_fill_attributed:{fill_dedupe_key}"


async def _append_unattributed_fill(
    store,
    order,
    *,
    source_fill_id: str,
    source=EventSource.BROKER_REST,
    authority=EventAuthority.BROKER_AUTHORITATIVE,
):
    return await store.append_fill(
        order.id,
        order.symbol,
        OrderSide.SELL,
        10,
        9.9,
        source_fill_id=source_fill_id,
        filled_at=FILL_TIME,
        session_id=order.session_id,
        source=source,
        authority=authority,
    )


async def test_unattributed_fill_is_applied_once_by_append_only_marker(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "missed-record-first"
    fill_key = _canonical_key(order.id, source_fill_id)
    await _append_unattributed_fill(any_store, order, source_fill_id=source_fill_id)

    assert (await any_store.get_position("AAPL")).quantity == 90
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100

    repaired = await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=fill_key,
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME,
    )

    assert repaired.remaining_quantity == 90
    assert (await any_store.get_position("AAPL")).quantity == 90
    # Order fill-progress remains a lifecycle-column concern until the
    # documented read flip; this repair must not synthesize such a transition.
    assert (await any_store.get_order(order.id)).filled_quantity == 0
    events = await any_store.get_execution_events()
    fills = [event for event in events if event.dedupe_key == fill_key]
    markers = [
        event
        for event in events
        if event.event_type.value == ATTRIBUTION_TYPE
        and event.dedupe_key == _marker_key(fill_key)
    ]
    assert len(fills) == 1 and fills[0].envelope_id is None
    assert fills[0].quantity == 10
    assert len(markers) == 1
    marker = markers[0]
    assert marker.source is EventSource.ENGINE
    assert marker.authority is EventAuthority.LOCAL
    assert marker.envelope_id == envelope.id
    assert marker.order_id == order.id
    assert marker.quantity == 10
    assert marker.price == 9.9
    assert marker.ts_event == FILL_TIME
    assert marker.ts_init == APPLY_TIME
    assert marker.payload == {
        "fill_dedupe_key": fill_key,
        "fill_event_id": fills[0].id,
        "fill_event_sequence": fills[0].sequence,
        "remaining_before": 100,
        "remaining_after": 90,
        "repair": "missed_envelope_attribution",
    }

    event_count = len(events)
    replayed = await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=fill_key,
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME + timedelta(minutes=1),
    )
    assert replayed.remaining_quantity == 90
    assert len(await any_store.get_execution_events()) == event_count


async def test_record_first_keeps_one_fill_and_marker_alone_cannot_move_position(
    any_store,
):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "normal-record-first"
    fill_key = _canonical_key(order.id, source_fill_id)

    recorded = await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=fill_key,
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME,
    )
    await _append_unattributed_fill(any_store, order, source_fill_id=source_fill_id)

    assert recorded.remaining_quantity == 90
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 90
    assert (await any_store.get_position("AAPL")).quantity == 90
    fill_rows = await any_store.list_fills(order_id=order.id)
    assert len(fill_rows) == 1 and fill_rows[0].quantity == 10
    events = await any_store.get_execution_events()
    fills = [event for event in events if event.dedupe_key == fill_key]
    assert len(fills) == 1
    assert fills[0].event_type is ExecutionEventType.FILL
    assert fills[0].envelope_id == envelope.id
    assert not [event for event in events if event.event_type.value == ATTRIBUTION_TYPE]

    # The repair marker carries quantity for replayable envelope accounting, but
    # it is not a broker FILL and therefore cannot fold position/order quantity
    # or mutate the envelope when appended outside record_envelope_fill.
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType(ATTRIBUTION_TYPE),
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=_marker_key("marker-alone"),
            ts_event=FILL_TIME,
            ts_init=APPLY_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=90,
            price=9.8,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={"repair": "projection-pin"},
        )
    )
    assert (await any_store.get_position("AAPL")).quantity == 90
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 90


async def test_monitoring_replay_repairs_first_poll_without_parent(
    any_store, monkeypatch
):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "monitoring-replay"
    answers = iter((None, envelope.id, envelope.id, envelope.id))

    async def resolve_on_second_poll(_store, _order_id):
        return next(answers)

    monkeypatch.setattr("app.monitoring._envelope_id_for_order", resolve_on_second_poll)
    update = BrokerOrderUpdate(
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=10,
        fills=[
            BrokerFill(
                source_fill_id=source_fill_id,
                quantity=10,
                price=9.9,
                filled_at=FILL_TIME,
            )
        ],
    )

    await _apply_update(any_store, order, update)
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 90
    await _apply_update(any_store, await any_store.get_order(order.id), update)

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 90
    assert (await any_store.get_position("AAPL")).quantity == 90
    fill_key = _canonical_key(order.id, source_fill_id)
    events = await any_store.get_execution_events()
    assert sum(event.dedupe_key == fill_key for event in events) == 1
    assert sum(event.dedupe_key == _marker_key(fill_key) for event in events) == 1


async def test_terminal_monitoring_fill_repairs_parent_in_same_poll(
    any_store, monkeypatch
):
    """A first-and-only FILLED observation cannot wait for another poll."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "terminal-monitoring-repair"
    answers = iter((None, envelope.id))

    async def resolve_after_ingest(_store, _order_id):
        return next(answers)

    monkeypatch.setattr("app.monitoring._envelope_id_for_order", resolve_after_ingest)
    update = BrokerOrderUpdate(
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[
            BrokerFill(
                source_fill_id=source_fill_id,
                quantity=100,
                price=9.9,
                filled_at=FILL_TIME,
            )
        ],
    )

    await _apply_update(any_store, order, update)

    assert (await any_store.get_order(order.id)).status is OrderStatus.FILLED
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 0
    fill_key = _canonical_key(order.id, source_fill_id)
    events = await any_store.get_execution_events()
    assert sum(event.dedupe_key == fill_key for event in events) == 1
    assert sum(event.dedupe_key == _marker_key(fill_key) for event in events) == 1


async def test_inferred_fill_repairs_parent_after_record_first_fault(
    any_store, monkeypatch
):
    """The reconciliation producer gets the same post-ingest repair seam."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "inferred-record-first-fault"
    real_record = any_store.record_envelope_fill
    calls = 0

    async def fail_first_record(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected record-first attribution fault")
        return await real_record(*args, **kwargs)

    monkeypatch.setattr(any_store, "record_envelope_fill", fail_first_record)
    plan = SimpleNamespace(
        inferred_fills=[
            InferredFill(
                order_id=order.id,
                symbol=order.symbol,
                side=OrderSide.SELL,
                quantity=10,
                price=9.9,
                source_fill_id=source_fill_id,
            )
        ]
    )

    await _apply_inferred_fills(any_store, plan)

    assert calls == 2
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 90
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_cadence_repairs_terminal_unattributed_fill(any_store):
    """A persisted canonical fill remains a repair seed after process failure."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "terminal-cadence-repair"
    await _append_unattributed_fill(any_store, order, source_fill_id=source_fill_id)
    await any_store.transition_order(order.id, OrderStatus.FILLED, filled_quantity=10)
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100

    await run_monitoring_tick(
        any_store,
        MockBrokerAdapter(),
        Settings(protection_enabled=False, reconciliation_enabled=False),
    )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 90
    fill_key = _canonical_key(order.id, source_fill_id)
    events = await any_store.get_execution_events()
    assert sum(event.dedupe_key == fill_key for event in events) == 1
    assert sum(event.dedupe_key == _marker_key(fill_key) for event in events) == 1


async def test_cadence_revalidates_foreign_marker_and_fails_closed(any_store):
    """A marker payload alone cannot suppress validation of its canonical fill."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "foreign-marker-cadence"
    fill_key = _canonical_key(order.id, source_fill_id)
    await _append_unattributed_fill(any_store, order, source_fill_id=source_fill_id)
    canonical = next(
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == fill_key
    )
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-foreign-cadence-marker",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=_marker_key(fill_key),
            ts_event=FILL_TIME,
            ts_init=APPLY_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id="foreign-order",
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={
                "fill_dedupe_key": fill_key,
                "fill_event_id": canonical.id,
                "fill_event_sequence": canonical.sequence,
                "remaining_before": 100,
                "remaining_after": 90,
                "repair": "missed_envelope_attribution",
            },
        )
    )
    candidate = await any_store.create_candidate(
        "MSFT", suggested_quantity=1, suggested_limit_price=1.0
    )
    await any_store.create_order_for_test(
        candidate.id,
        "MSFT",
        OrderSide.BUY,
        1,
        order_type=OrderType.LIMIT,
        limit_price=1.0,
    )
    adapter = MockBrokerAdapter()

    with pytest.raises(InvalidFillError):
        await run_monitoring_tick(
            any_store,
            adapter,
            Settings(protection_enabled=False, reconciliation_enabled=False),
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert adapter.submitted == []


async def test_inferred_fill_lookup_fault_isolated_to_one_item(any_store, monkeypatch):
    """A single order-read fault cannot discard later inferred fills in the batch."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    real_get_order = any_store.get_order
    lookup_calls = 0

    async def fail_first_lookup(order_id):
        nonlocal lookup_calls
        lookup_calls += 1
        if lookup_calls == 1:
            raise RuntimeError("injected first inferred-fill order lookup fault")
        return await real_get_order(order_id)

    monkeypatch.setattr(any_store, "get_order", fail_first_lookup)
    plan = SimpleNamespace(
        inferred_fills=[
            InferredFill(
                order_id="faulted-order",
                symbol="MSFT",
                side=OrderSide.BUY,
                quantity=1,
                price=1.0,
                source_fill_id="faulted-inference",
            ),
            InferredFill(
                order_id=order.id,
                symbol=order.symbol,
                side=OrderSide.SELL,
                quantity=10,
                price=9.9,
                source_fill_id="surviving-inference",
            ),
        ]
    )

    await _apply_inferred_fills(any_store, plan)

    assert lookup_calls >= 2
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 90
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_streamed_fill_batch_resolves_envelope_lineage_once(
    any_store, monkeypatch
):
    """One broker update must not amplify one full-log scan per fill and retry."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    real_get_events = any_store.get_execution_events
    scan_calls = 0

    async def count_full_log_scans(*args, **kwargs):
        nonlocal scan_calls
        scan_calls += 1
        return await real_get_events(*args, **kwargs)

    monkeypatch.setattr(any_store, "get_execution_events", count_full_log_scans)
    update = BrokerOrderUpdate(
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=30,
        fills=[
            BrokerFill(
                source_fill_id=f"batched-fill-{index}",
                quantity=10,
                price=9.9,
                filled_at=FILL_TIME + timedelta(seconds=index),
            )
            for index in range(3)
        ],
    )

    await _apply_update(any_store, order, update)

    assert scan_calls == 1
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 70
    assert (await any_store.get_position("AAPL")).quantity == 70


async def test_attribution_repair_fails_closed_on_fill_identity_conflict(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "identity-conflict"
    fill_key = _canonical_key(order.id, source_fill_id)
    await _append_unattributed_fill(any_store, order, source_fill_id=source_fill_id)
    before_envelope = await any_store.get_envelope(envelope.id)
    before_events = await any_store.get_execution_events()

    with pytest.raises(InvalidFillError):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=11,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert await any_store.get_envelope(envelope.id) == before_envelope
    assert await any_store.get_execution_events() == before_events


async def test_attribution_repair_fails_closed_on_foreign_envelope(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "foreign-envelope")
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=fill_key,
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id="foreign-envelope",
            session_id=order.session_id,
            correlation_id="foreign-owner",
        )
    )
    before_envelope = await any_store.get_envelope(envelope.id)
    before_events = await any_store.get_execution_events()

    with pytest.raises(InvalidFillError):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert await any_store.get_envelope(envelope.id) == before_envelope
    assert await any_store.get_execution_events() == before_events
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_attribution_marker_dedupe_collision_fails_closed(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "poisoned-marker"
    fill_key = _canonical_key(order.id, source_fill_id)
    await _append_unattributed_fill(any_store, order, source_fill_id=source_fill_id)
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=_marker_key(fill_key),
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            payload={"poison": True},
        )
    )
    before_envelope = await any_store.get_envelope(envelope.id)
    before_events = await any_store.get_execution_events()

    with pytest.raises(InvalidFillError):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert await any_store.get_envelope(envelope.id) == before_envelope
    assert await any_store.get_execution_events() == before_events


async def test_repair_accepts_real_reobservation_of_synthetic_fill(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "synthetic-then-real"
    fill_key = _canonical_key(order.id, source_fill_id)
    await _append_unattributed_fill(
        any_store,
        order,
        source_fill_id=source_fill_id,
        source=EventSource.RECONCILIATION,
        authority=EventAuthority.SYNTHETIC,
    )

    repaired = await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=fill_key,
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME + timedelta(seconds=1),
        source=EventSource.BROKER_REST,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        now=APPLY_TIME,
    )

    assert repaired.remaining_quantity == 90
    assert (await any_store.get_position("AAPL")).quantity == 90
    events = await any_store.get_execution_events()
    assert sum(event.dedupe_key == fill_key for event in events) == 1
    assert sum(event.dedupe_key == _marker_key(fill_key) for event in events) == 1


async def test_attribution_rejects_marker_without_canonical_fill(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "missing-canonical")
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-marker-without-fill",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=_marker_key(fill_key),
            ts_event=FILL_TIME,
            ts_init=APPLY_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={"fill_dedupe_key": fill_key},
        )
    )

    with pytest.raises(InvalidFillError, match="without its canonical FILL"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 100


async def test_attribution_rejects_non_fill_canonical_dedupe_owner(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "non-fill-owner")
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-non-fill-owner",
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=fill_key,
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
        )
    )

    with pytest.raises(InvalidFillError, match="non-FILL"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100


async def test_attribution_rejects_malformed_already_attributed_fill(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "malformed-attributed")
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-malformed-attributed-fill",
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=fill_key,
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={},
        )
    )

    with pytest.raises(InvalidFillError, match="malformed remaining-quantity"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_attribution_repair_requires_order_scoped_fill_identity(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = "legacy-unscoped-fill"
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-unscoped-fill",
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=fill_key,
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
        )
    )

    with pytest.raises(InvalidFillError, match="order-scoped"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_attribution_rejects_marker_referencing_wrong_fill_event(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "wrong-fill-reference")
    await _append_unattributed_fill(
        any_store,
        order,
        source_fill_id="wrong-fill-reference",
    )
    canonical = next(
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == fill_key
    )
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-wrong-fill-marker",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=_marker_key(fill_key),
            ts_event=FILL_TIME,
            ts_init=APPLY_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={
                "fill_dedupe_key": fill_key,
                "fill_event_id": "foreign-fill-event",
                "fill_event_sequence": canonical.sequence,
            },
        )
    )

    with pytest.raises(InvalidFillError, match="another FILL event"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_attribution_rejects_impossible_attributed_remaining_facts(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "impossible-attributed-remaining")
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-impossible-attributed-fill",
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=fill_key,
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={"remaining_before": 100, "remaining_after": 95},
        )
    )

    with pytest.raises(InvalidFillError, match="remaining-quantity facts"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100


async def test_attribution_rejects_impossible_marker_remaining_facts(any_store):
    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "impossible-marker-remaining")
    await _append_unattributed_fill(
        any_store,
        order,
        source_fill_id="impossible-marker-remaining",
    )
    canonical = next(
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == fill_key
    )
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-impossible-remaining-marker",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=_marker_key(fill_key),
            ts_event=FILL_TIME,
            ts_init=APPLY_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={
                "fill_dedupe_key": fill_key,
                "fill_event_id": canonical.id,
                "fill_event_sequence": canonical.sequence,
                "remaining_before": 100,
                "remaining_after": 95,
            },
        )
    )

    with pytest.raises(InvalidFillError, match="remaining-quantity facts"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100


async def test_attribution_rejects_fill_for_missing_raw_order_lineage(any_store):
    """A caller cannot lend a real envelope to a ghost canonical order."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    ghost_order_id = "wo0113-ghost-envelope-child"
    fill_key = _canonical_key(ghost_order_id, "raw-ghost-fill")
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-raw-ghost-fill",
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=fill_key,
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=ghost_order_id,
            session_id=order.session_id,
        )
    )

    with pytest.raises(InvalidFillError, match="not a uniquely bounded child"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=ghost_order_id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_attribution_rejects_marker_not_reflected_in_envelope_state(any_store):
    """A raw marker is not proof that its claimed envelope write committed."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "unreflected-marker")
    await _append_unattributed_fill(
        any_store,
        order,
        source_fill_id="unreflected-marker",
    )
    canonical = next(
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == fill_key
    )
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-unreflected-attribution-marker",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=_marker_key(fill_key),
            ts_event=FILL_TIME,
            ts_init=APPLY_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={
                "fill_dedupe_key": fill_key,
                "fill_event_id": canonical.id,
                "fill_event_sequence": canonical.sequence,
                "remaining_before": 100,
                "remaining_after": 90,
                "repair": "missed_envelope_attribution",
            },
        )
    )

    with pytest.raises(InvalidFillError, match="not reflected in envelope state"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_attribution_marker_replay_allows_later_valid_decrements(any_store):
    """A marker remains valid after a later fill lowers remaining quantity."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    first_key = _canonical_key(order.id, "marker-before-later-fill")
    await _append_unattributed_fill(
        any_store,
        order,
        source_fill_id="marker-before-later-fill",
    )
    first = await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=first_key,
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME,
    )
    assert first.remaining_quantity == 90

    second_key = _canonical_key(order.id, "later-valid-fill")
    await _append_unattributed_fill(
        any_store,
        order,
        source_fill_id="later-valid-fill",
    )
    second = await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=second_key,
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME + timedelta(minutes=1),
    )
    assert second.remaining_quantity == 80

    replayed = await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=first_key,
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME + timedelta(minutes=2),
    )
    assert replayed.remaining_quantity == 80


async def test_attribution_rejects_raw_scoped_fill_without_envelope_write(any_store):
    """A well-shaped raw FILL cannot impersonate the store's atomic co-write."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "raw-scoped-without-decrement")
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-raw-scoped-fill-without-decrement",
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=fill_key,
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={"remaining_before": 100, "remaining_after": 90},
        )
    )

    with pytest.raises(InvalidFillError, match="not reflected in envelope state"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=fill_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME,
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_attribution_rejects_marker_masked_by_another_valid_fill(any_store):
    """Another decrement cannot make a forged marker look atomically applied."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    first_key = _canonical_key(order.id, "masked-forged-marker")
    second_key = _canonical_key(order.id, "legitimate-other-decrement")
    await _append_unattributed_fill(
        any_store, order, source_fill_id="masked-forged-marker"
    )
    await _append_unattributed_fill(
        any_store, order, source_fill_id="legitimate-other-decrement"
    )
    first_event = next(
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == first_key
    )
    applied_second = await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=second_key,
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME,
    )
    assert applied_second.remaining_quantity == 90

    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-marker-masked-by-other-decrement",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=_marker_key(first_key),
            ts_event=FILL_TIME,
            ts_init=APPLY_TIME + timedelta(minutes=1),
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={
                "fill_dedupe_key": first_key,
                "fill_event_id": first_event.id,
                "fill_event_sequence": first_event.sequence,
                "remaining_before": 100,
                "remaining_after": 90,
                "repair": "missed_envelope_attribution",
            },
        )
    )

    with pytest.raises(InvalidFillError, match="not reflected in envelope state"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=first_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME + timedelta(minutes=2),
        )

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 90
    assert (await any_store.get_position("AAPL")).quantity == 80


async def test_new_repair_rejects_an_existing_unreflected_marker(any_store):
    """A forged marker for A blocks a later NEW repair of canonical fill B."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    first_key = _canonical_key(order.id, "forged-before-new-repair")
    second_key = _canonical_key(order.id, "new-repair-after-forged-marker")
    await _append_unattributed_fill(
        any_store, order, source_fill_id="forged-before-new-repair"
    )
    await _append_unattributed_fill(
        any_store, order, source_fill_id="new-repair-after-forged-marker"
    )
    first_event = next(
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == first_key
    )
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-forged-marker-before-new-repair",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=_marker_key(first_key),
            ts_event=FILL_TIME,
            ts_init=APPLY_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={
                "fill_dedupe_key": first_key,
                "fill_event_id": first_event.id,
                "fill_event_sequence": first_event.sequence,
                "remaining_before": 100,
                "remaining_after": 90,
                "repair": "missed_envelope_attribution",
            },
        )
    )

    with pytest.raises(InvalidFillError, match="not reflected in envelope state"):
        await any_store.record_envelope_fill(
            envelope.id,
            quantity=10,
            dedupe_key=second_key,
            price=9.9,
            order_id=order.id,
            session_id=order.session_id,
            ts_event=FILL_TIME,
            now=APPLY_TIME + timedelta(minutes=1),
        )

    events = await any_store.get_execution_events()
    assert not any(event.dedupe_key == _marker_key(second_key) for event in events)
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 80


async def test_cadence_validates_direct_attributed_fill_chain(any_store):
    """Cadence validates canonical direct attribution, not only orphan fills."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    fill_key = _canonical_key(order.id, "cadence-direct-chain")
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-cadence-direct-chain",
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=fill_key,
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={"remaining_before": 100, "remaining_after": 90},
        )
    )

    with pytest.raises(InvalidFillError, match="not reflected in envelope state"):
        await _repair_unattributed_envelope_fills(any_store)

    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 90


async def test_attribution_repair_uses_durable_tail_checkpoint(any_store, monkeypatch):
    """A steady cadence does not rescan the complete append-only execution log."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=_canonical_key(order.id, "checkpointed-direct-fill"),
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME,
    )
    real_get_events = any_store.get_execution_events
    after_sequences: list[int] = []

    async def observed_get_events(*, after_sequence=0, limit=None):
        after_sequences.append(after_sequence)
        return await real_get_events(after_sequence=after_sequence, limit=limit)

    monkeypatch.setattr(any_store, "get_execution_events", observed_get_events)
    await _repair_unattributed_envelope_fills(any_store)
    await _repair_unattributed_envelope_fills(any_store)

    assert after_sequences[0] == 0
    assert after_sequences[-1] > 0


async def test_attribution_checkpoint_does_not_advance_past_invalid_tail(any_store):
    """A poison tail remains selected after cadence fails its validation."""

    _session, envelope, order = await _submitted_envelope_child(any_store)
    await any_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=_canonical_key(order.id, "before-poison-checkpoint"),
        price=9.9,
        order_id=order.id,
        session_id=order.session_id,
        ts_event=FILL_TIME,
        now=APPLY_TIME,
    )
    await _repair_unattributed_envelope_fills(any_store)
    checkpoint_type = ExecutionEventType.ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT
    before = await any_store.get_latest_execution_event(checkpoint_type)
    assert before is not None
    high_water = before.payload["up_to_sequence"]

    poison_key = _canonical_key(order.id, "poison-after-checkpoint")
    poison = await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-poison-after-checkpoint",
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=poison_key,
            ts_event=FILL_TIME + timedelta(minutes=1),
            ts_init=FILL_TIME + timedelta(minutes=1),
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id=order.id,
            envelope_id=envelope.id,
            session_id=order.session_id,
            correlation_id=envelope.sell_intent_id,
            payload={"remaining_before": 90, "remaining_after": 80},
        )
    )
    assert poison.sequence > high_water

    for _ in range(2):
        with pytest.raises(InvalidFillError, match="not reflected in envelope state"):
            await _repair_unattributed_envelope_fills(any_store)
        checkpoint = await any_store.get_latest_execution_event(checkpoint_type)
        assert checkpoint is not None
        assert checkpoint.payload["up_to_sequence"] == high_water
