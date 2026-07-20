"""WO-0113 durable ownership whenever accepted-submit recovery cannot persist."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.broker.adapter import AmbiguousBrokerError, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_RESOLVED,
    CandidateStatus,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EventAuthority,
    EventSource,
    EventType,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.monitoring import (
    _escalate_fill_divergence,
    _record_accepted_submit_uncertainty,
    _redrive_stale_submitting,
    _recover_unpersisted_submits,
    _repair_unpersisted_submit_audits,
    _submit_pending_orders,
)
from app.reconciliation import (
    ENVELOPE_EXEC_QUARANTINED,
    ENVELOPE_EXEC_REPRICED,
    ENVELOPE_EXEC_SUBMITTED,
    execute_envelope_action,
    quarantine_or_own_ambiguous_submit,
    redrive_staged_envelope_action,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import (
    OrderIntentBlockedError,
    OrderTransitionError,
    RecoveryTransitionError,
    SellIntentTransitionError,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

# Wednesday 10:00 ET.  The envelope validator derives the session phase from
# this injected clock, so a weekend wall-clock date would exercise the
# session-phase rail instead of the accepted-submit boundary under test.
ENVELOPE_NOW = datetime(2026, 7, 15, 14, tzinfo=UTC)


async def _held_position(store) -> None:
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        100,
        limit_price=10.0,
        session_id=session.id,
    )
    await store.append_fill(
        order.id,
        "AAPL",
        OrderSide.BUY,
        100,
        10.0,
        session_id=session.id,
    )
    await store.transition_order(order.id, OrderStatus.CANCELED)
    await store.transition_candidate(candidate.id, CandidateStatus.EXPIRED)


def _envelope_draft(intent_id: str, session_id: str) -> ExecutionEnvelope:
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
        expires_at=ENVELOPE_NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _envelope_action(
    kind: ActionKind = ActionKind.SUBMIT,
    *,
    price: float = 9.9,
) -> PlannedAction:
    return PlannedAction(
        kind=kind,
        limit_price=price,
        quantity=10,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _active_envelope(store):
    await _held_position(store)
    session = await store.get_current_session()
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _envelope_draft(intent.id, session.id), actor="operator"
    )
    return intent, envelope


async def _prepare_envelope_acceptance(store, adapter, kind: ActionKind):
    intent, envelope = await _active_envelope(store)
    predecessor = None
    if kind is ActionKind.REPRICE:
        first = await execute_envelope_action(
            store,
            adapter,
            envelope.id,
            _envelope_action(),
            snapshot_fingerprint="wo0113-envelope-first",
            now=ENVELOPE_NOW,
        )
        assert first.outcome == ENVELOPE_EXEC_SUBMITTED
        predecessor = await store.get_order(first.order_id)
        assert predecessor is not None
    return intent, envelope, predecessor


@pytest.mark.parametrize(
    "producer",
    ["first_submit", "stale_redrive", "envelope_submit", "envelope_reprice"],
)
@pytest.mark.parametrize(
    "cancel_point",
    [
        "venue_call",
        "ambiguity_persist",
        "accepted_persist",
        "accepted_persist_recovery_fails",
    ],
)
async def test_cancellation_after_possible_send_keeps_durable_owner(
    any_store,
    monkeypatch,
    producer,
    cancel_point,
):
    """Shutdown propagates only after an unknown/accepted send has durable truth."""

    await any_store.initialize()
    adapter = MockBrokerAdapter()
    target_order_id = None
    if producer in {"first_submit", "stale_redrive"}:
        order, claim = await _created_buy_claim(any_store)
        assert claim.order is not None
        target_order_id = order.id
        if producer == "first_submit":
            await any_store.transition_order(order.id, OrderStatus.CREATED)

        async def run_producer():
            if producer == "first_submit":
                await _submit_pending_orders(any_store, adapter, Settings())
            else:
                await _redrive_stale_submitting(any_store, adapter, Settings())

        venue_method = "submit_order"
    else:
        kind = (
            ActionKind.REPRICE if producer == "envelope_reprice" else ActionKind.SUBMIT
        )
        _intent, envelope, _predecessor = await _prepare_envelope_acceptance(
            any_store, adapter, kind
        )

        async def run_producer():
            await execute_envelope_action(
                any_store,
                adapter,
                envelope.id,
                _envelope_action(
                    kind, price=9.8 if kind is ActionKind.REPRICE else 9.9
                ),
                snapshot_fingerprint=(f"wo0113-cancel-{cancel_point}-{producer}"),
                now=(
                    ENVELOPE_NOW + timedelta(minutes=1)
                    if kind is ActionKind.REPRICE
                    else ENVELOPE_NOW
                ),
            )

        venue_method = "replace_order" if kind is ActionKind.REPRICE else "submit_order"

    ambiguity_entered = asyncio.Event()
    ambiguity_release = asyncio.Event()
    if cancel_point in {"venue_call", "ambiguity_persist"}:
        real_venue_call = getattr(adapter, venue_method)

        async def accept_then_cancel(*args, **kwargs):
            await real_venue_call(*args, **kwargs)
            if cancel_point == "venue_call":
                raise asyncio.CancelledError
            raise AmbiguousBrokerError("accepted response became ambiguous")

        monkeypatch.setattr(adapter, venue_method, accept_then_cancel)
        if cancel_point == "ambiguity_persist":
            real_quarantine = any_store.quarantine_timed_out_order

            async def block_ambiguity_persist(*args, **kwargs):
                ambiguity_entered.set()
                await ambiguity_release.wait()
                return await real_quarantine(*args, **kwargs)

            monkeypatch.setattr(
                any_store,
                "quarantine_timed_out_order",
                block_ambiguity_persist,
            )
    else:
        real_transition = any_store.transition_order

        async def cancel_during_accepted_persist(order_id, new_status, *args, **kwargs):
            nonlocal target_order_id
            if new_status is OrderStatus.SUBMITTED:
                target_order_id = order_id
                await real_transition(order_id, OrderStatus.CANCELED)
                raise asyncio.CancelledError
            return await real_transition(order_id, new_status, *args, **kwargs)

        monkeypatch.setattr(
            any_store, "transition_order", cancel_during_accepted_persist
        )
        if cancel_point == "accepted_persist_recovery_fails":

            async def fail_recovery(**_kwargs):
                raise RuntimeError("injected cancellation recovery failure")

            monkeypatch.setattr(any_store, "create_submit_recovery", fail_recovery)

    if cancel_point == "ambiguity_persist":
        producer_task = asyncio.create_task(run_producer())
        await ambiguity_entered.wait()
        producer_task.cancel()
        ambiguity_release.set()
        with pytest.raises(asyncio.CancelledError):
            await producer_task
    else:
        with pytest.raises(asyncio.CancelledError):
            await run_producer()

    if target_order_id is None:
        target_order_id = (
            adapter.replaced[-1][1]
            if venue_method == "replace_order"
            else adapter.submitted[-1].id
        )
    persisted = await any_store.get_order(target_order_id)
    assert persisted is not None
    if cancel_point in {"venue_call", "ambiguity_persist"}:
        assert persisted.status is OrderStatus.TIMEOUT_QUARANTINE
        assert persisted.broker_order_id is None
    elif cancel_point == "accepted_persist":
        assert persisted.status is OrderStatus.CANCELED
        recoveries = [
            recovery
            for recovery in await any_store.list_submit_recoveries()
            if recovery.local_order_id == target_order_id
        ]
        assert len(recoveries) == 1
        assert recoveries[0].broker_order_id == f"broker-{target_order_id}"
        assert recoveries[0].client_order_id == target_order_id
    else:
        assert persisted.status is OrderStatus.CANCELED
        assert not [
            recovery
            for recovery in await any_store.list_submit_recoveries()
            if recovery.local_order_id == target_order_id
        ]
        fallbacks = [
            event
            for event in await any_store.get_execution_events()
            if event.order_id == target_order_id
            and event.payload.get("reason") == "accepted_submit_unpersisted"
        ]
        assert len(fallbacks) == 1
        assert fallbacks[0].payload["broker_order_id"] == (f"broker-{target_order_id}")

    assert len(adapter.replaced) == (1 if producer == "envelope_reprice" else 0)
    assert len(adapter.submitted) == 1


@pytest.mark.parametrize(
    "producer",
    ["first_submit", "stale_redrive", "envelope_submit", "envelope_reprice"],
)
@pytest.mark.parametrize("commit_attempt", ["primary", "retry"])
async def test_commit_then_raise_recognizes_tracked_acceptance(
    any_store, monkeypatch, producer, commit_attempt
):
    """A lost primary/retry response cannot invent cleanup for an adopted id."""

    await any_store.initialize()
    adapter = MockBrokerAdapter()
    target_order_id = None
    if producer in {"first_submit", "stale_redrive"}:
        order, claim = await _created_buy_claim(any_store)
        assert claim.order is not None
        target_order_id = order.id
        if producer == "first_submit":
            await any_store.transition_order(order.id, OrderStatus.CREATED)

        async def run_producer():
            if producer == "first_submit":
                await _submit_pending_orders(any_store, adapter, Settings())
            else:
                await _redrive_stale_submitting(any_store, adapter, Settings())

    else:
        kind = (
            ActionKind.REPRICE if producer == "envelope_reprice" else ActionKind.SUBMIT
        )
        _intent, envelope, _predecessor = await _prepare_envelope_acceptance(
            any_store, adapter, kind
        )

        async def run_producer():
            await execute_envelope_action(
                any_store,
                adapter,
                envelope.id,
                _envelope_action(
                    kind, price=9.8 if kind is ActionKind.REPRICE else 9.9
                ),
                snapshot_fingerprint=(
                    f"wo0113-lost-response-{commit_attempt}-{producer}"
                ),
                now=(
                    ENVELOPE_NOW + timedelta(minutes=1)
                    if kind is ActionKind.REPRICE
                    else ENVELOPE_NOW
                ),
            )

    real_transition = any_store.transition_order
    submitted_calls = 0

    async def commit_then_raise(order_id, new_status, *args, **kwargs):
        nonlocal submitted_calls, target_order_id
        if new_status is not OrderStatus.SUBMITTED:
            return await real_transition(order_id, new_status, *args, **kwargs)
        target_order_id = order_id
        submitted_calls += 1
        if commit_attempt == "retry" and submitted_calls == 1:
            raise RuntimeError("injected pre-commit primary failure")
        await real_transition(order_id, new_status, *args, **kwargs)
        raise RuntimeError("injected lost SUBMITTED response")

    monkeypatch.setattr(any_store, "transition_order", commit_then_raise)
    await run_producer()

    assert target_order_id is not None
    persisted = await any_store.get_order(target_order_id)
    assert persisted is not None
    assert persisted.status is OrderStatus.SUBMITTED
    assert persisted.broker_order_id == f"broker-{target_order_id}"
    assert submitted_calls == (2 if commit_attempt == "retry" else 1)
    assert not [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == target_order_id
    ]

    await _recover_unpersisted_submits(any_store, adapter)
    assert adapter.canceled == []


async def _accepted_sell_without_local_owner(store, monkeypatch):
    """Broker-accept a SELL while forcing both ordinary ownership writes to fail."""

    await _held_position(store)
    spare_buy_candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.MANUAL_FLATTEN,
        target_quantity=100,
    )
    await store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    sell = await store.create_order_for_sell_intent(
        intent.id,
        order_type=OrderType.LIMIT,
        limit_price=10.0,
    )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order

    async def accept_then_cancel_local(order, *, venue_scope):
        broker_id = await real_submit(order, venue_scope=venue_scope)
        await store.transition_order(order.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("injected accepted-submit audit failure")

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected accepted-submit recovery failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(store, "append_event", fail_audit)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError, match="durable uncertainty"):
        await _submit_pending_orders(store, adapter, Settings())

    fallback = next(
        event
        for event in await store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == sell.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    )
    assert fallback.side is OrderSide.SELL
    assert len(adapter.submitted) == 1
    return sell, fallback, spare_buy_candidate.id


async def _created_buy_claim(store, *, candidate_id=None):
    if candidate_id is None:
        candidate = await store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=10.0
        )
        candidate_id = candidate.id
    buy = await store.create_order_for_test(
        candidate_id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    return buy, await store.claim_order_for_submission(buy.id)


async def _accepted_order_with_audit_only(store, side, monkeypatch):
    """Persist the ordinary audit, but fail the recovery ownership write."""

    await _held_position(store)
    spare_buy_candidate_id = None
    if side is OrderSide.BUY:
        candidate = await store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=10.0
        )
        order = await store.create_order_for_test(
            candidate.id,
            "AAPL",
            OrderSide.BUY,
            10,
            limit_price=10.0,
        )
    else:
        spare_buy_candidate = await store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=10.0
        )
        spare_buy_candidate_id = spare_buy_candidate.id
        intent = await store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.MANUAL_FLATTEN,
            target_quantity=100,
        )
        await store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
        order = await store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.LIMIT,
            limit_price=10.0,
        )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order

    async def accept_then_cancel_local(submitted, *, venue_scope):
        broker_id = await real_submit(submitted, venue_scope=venue_scope)
        await store.transition_order(submitted.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected accepted-submit recovery failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError):
        await _submit_pending_orders(store, adapter, Settings())

    assert any(
        event.event_type == EventType.ORDER_SUBMIT_UNPERSISTED.value
        and event.order_id == order.id
        for event in await store.list_events()
    )
    fallback = [
        event
        for event in await store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == order.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    ]
    return order, fallback, spare_buy_candidate_id


@pytest.mark.parametrize(
    "kind", [ActionKind.SUBMIT, ActionKind.REPRICE], ids=["submit", "reprice"]
)
@pytest.mark.parametrize("audit_fails", [False, True], ids=["audit-ok", "audit-fails"])
async def test_envelope_acceptance_double_persist_failure_has_last_write_owner(
    any_store,
    monkeypatch,
    kind,
    audit_fails,
):
    """Every envelope acceptance keeps exact ownership after both primary writes fail."""

    adapter = MockBrokerAdapter()
    intent, envelope, predecessor = await _prepare_envelope_acceptance(
        any_store, adapter, kind
    )
    predecessor_id = predecessor.id if predecessor is not None else None
    real_transition = any_store.transition_order
    real_append_event = any_store.append_event
    failures = 0

    async def fail_accepted_transition(order_id, new_status, *args, **kwargs):
        nonlocal failures
        if (
            order_id != predecessor_id
            and new_status is OrderStatus.SUBMITTED
            and failures < 2
        ):
            failures += 1
            raise RuntimeError("injected envelope SUBMITTED persistence failure")
        return await real_transition(order_id, new_status, *args, **kwargs)

    async def maybe_fail_audit(event_type, *args, **kwargs):
        if audit_fails and event_type == EventType.ORDER_SUBMIT_UNPERSISTED.value:
            raise RuntimeError("injected envelope acceptance audit failure")
        return await real_append_event(event_type, *args, **kwargs)

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected envelope recovery persistence failure")

    monkeypatch.setattr(any_store, "transition_order", fail_accepted_transition)
    monkeypatch.setattr(any_store, "append_event", maybe_fail_audit)
    monkeypatch.setattr(any_store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError):
        await execute_envelope_action(
            any_store,
            adapter,
            envelope.id,
            _envelope_action(kind, price=9.8 if kind is ActionKind.REPRICE else 9.9),
            snapshot_fingerprint=f"wo0113-envelope-fallback:{kind.value}",
            now=(
                ENVELOPE_NOW + timedelta(minutes=1)
                if kind is ActionKind.REPRICE
                else ENVELOPE_NOW
            ),
        )

    accepted_order_id = (
        adapter.replaced[-1][1]
        if kind is ActionKind.REPRICE
        else adapter.submitted[-1].id
    )
    broker_order_id = f"broker-{accepted_order_id}"
    fallbacks = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == accepted_order_id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    ]

    assert failures == 2
    assert len(fallbacks) == 1
    fallback = fallbacks[0]
    assert fallback.source is EventSource.ENGINE
    assert fallback.authority is EventAuthority.LOCAL
    assert fallback.dedupe_key == (
        f"accepted_submit_unpersisted:{accepted_order_id}:{broker_order_id}"
    )
    assert fallback.payload["broker_order_id"] == broker_order_id
    assert fallback.payload["envelope_id"] == envelope.id
    assert fallback.payload["kind"] == kind.value
    assert fallback.payload["replaces_order_id"] == predecessor_id
    assert fallback.correlation_id == intent.id
    assert not [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == accepted_order_id
    ]
    assert len(adapter.submitted) == 1
    assert len(adapter.replaced) == (1 if kind is ActionKind.REPRICE else 0)


@pytest.mark.parametrize(
    "kind", [ActionKind.SUBMIT, ActionKind.REPRICE], ids=["submit", "reprice"]
)
async def test_envelope_acceptance_normalizes_broker_identity_at_ingress(
    any_store,
    monkeypatch,
    kind,
):
    """Envelope submit and replace use one canonical broker identity everywhere."""

    adapter = MockBrokerAdapter()
    _intent, envelope, _predecessor = await _prepare_envelope_acceptance(
        any_store, adapter, kind
    )
    if kind is ActionKind.REPRICE:
        real_replace = adapter.replace_order

        async def padded_replace(broker_order_id, **kwargs):
            accepted = await real_replace(broker_order_id, **kwargs)
            return f"  {accepted}  "

        monkeypatch.setattr(adapter, "replace_order", padded_replace)
    else:
        real_submit = adapter.submit_order

        async def padded_submit(order, *, venue_scope):
            accepted = await real_submit(order, venue_scope=venue_scope)
            return f"  {accepted}  "

        monkeypatch.setattr(adapter, "submit_order", padded_submit)

    result = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _envelope_action(kind, price=9.8 if kind is ActionKind.REPRICE else 9.9),
        snapshot_fingerprint=f"wo0113-envelope-normalize:{kind.value}",
        now=(
            ENVELOPE_NOW + timedelta(minutes=1)
            if kind is ActionKind.REPRICE
            else ENVELOPE_NOW
        ),
    )

    expected_outcome = (
        ENVELOPE_EXEC_REPRICED
        if kind is ActionKind.REPRICE
        else ENVELOPE_EXEC_SUBMITTED
    )
    canonical_broker_id = f"broker-{result.order_id}"
    assert result.outcome == expected_outcome
    assert result.broker_order_id == canonical_broker_id
    assert (await any_store.get_order(result.order_id)).broker_order_id == (
        canonical_broker_id
    )


@pytest.mark.parametrize(
    "kind", [ActionKind.SUBMIT, ActionKind.REPRICE], ids=["submit", "reprice"]
)
@pytest.mark.parametrize("raw_broker_id", ["", "   "], ids=["empty", "whitespace"])
async def test_envelope_acceptance_with_no_concrete_identity_is_quarantined(
    any_store,
    monkeypatch,
    kind,
    raw_broker_id,
):
    """A malformed post-call identity is ambiguous acceptance, never pre-flight."""

    adapter = MockBrokerAdapter()
    _intent, envelope, _predecessor = await _prepare_envelope_acceptance(
        any_store, adapter, kind
    )
    if kind is ActionKind.REPRICE:
        real_replace = adapter.replace_order

        async def malformed_replace(broker_order_id, **kwargs):
            await real_replace(broker_order_id, **kwargs)
            return raw_broker_id

        monkeypatch.setattr(adapter, "replace_order", malformed_replace)
    else:
        real_submit = adapter.submit_order

        async def malformed_submit(order, *, venue_scope):
            await real_submit(order, venue_scope=venue_scope)
            return raw_broker_id

        monkeypatch.setattr(adapter, "submit_order", malformed_submit)

    result = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _envelope_action(kind, price=9.8 if kind is ActionKind.REPRICE else 9.9),
        snapshot_fingerprint=f"wo0113-envelope-malformed:{kind.value}",
        now=(
            ENVELOPE_NOW + timedelta(minutes=1)
            if kind is ActionKind.REPRICE
            else ENVELOPE_NOW
        ),
    )

    assert result.outcome == ENVELOPE_EXEC_QUARANTINED
    assert (await any_store.get_order(result.order_id)).status is (
        OrderStatus.TIMEOUT_QUARANTINE
    )
    before = (len(adapter.submitted), len(adapter.replaced))
    await redrive_staged_envelope_action(
        any_store,
        adapter,
        envelope.id,
        now=ENVELOPE_NOW + timedelta(minutes=2),
    )
    assert (len(adapter.submitted), len(adapter.replaced)) == before


async def test_ambiguous_owner_falls_back_when_quarantine_read_also_fails(
    any_store, monkeypatch
):
    """A diagnostic read fault cannot bypass the mandatory recovery write."""

    await any_store.initialize()
    order, claim = await _created_buy_claim(any_store)
    assert claim.order is not None

    async def fail_quarantine(*_args, **_kwargs):
        raise RuntimeError("quarantine unavailable")

    async def fail_read(*_args, **_kwargs):
        raise RuntimeError("read unavailable")

    monkeypatch.setattr(any_store, "quarantine_timed_out_order", fail_quarantine)
    monkeypatch.setattr(any_store, "get_order", fail_read)

    await quarantine_or_own_ambiguous_submit(
        any_store,
        claim.order,
        AmbiguousBrokerError("unknown venue send"),
        context="read_fault_probe",
    )

    recoveries = await any_store.list_submit_recoveries()
    assert len(recoveries) == 1
    assert recoveries[0].local_order_id == order.id
    assert recoveries[0].broker_order_id == ""
    assert recoveries[0].cleanup_status == RECOVERY_NEEDS_REVIEW


@pytest.mark.parametrize(
    "kind", [ActionKind.SUBMIT, ActionKind.REPRICE], ids=["submit", "reprice"]
)
@pytest.mark.parametrize("raw_broker_id", ["", "   "], ids=["empty", "whitespace"])
async def test_envelope_ambiguous_quarantine_race_gets_durable_owner(
    any_store,
    monkeypatch,
    kind,
    raw_broker_id,
):
    """A concurrent local terminalization cannot erase an unknown envelope send."""

    adapter = MockBrokerAdapter()
    _intent, envelope, _predecessor = await _prepare_envelope_acceptance(
        any_store, adapter, kind
    )
    if kind is ActionKind.REPRICE:
        real_replace = adapter.replace_order

        async def raced_replace(broker_order_id, **kwargs):
            await real_replace(broker_order_id, **kwargs)
            await any_store.transition_order(
                kwargs["client_order_id"], OrderStatus.CANCELED
            )
            return raw_broker_id

        monkeypatch.setattr(adapter, "replace_order", raced_replace)
    else:
        real_submit = adapter.submit_order

        async def raced_submit(order, *, venue_scope):
            await real_submit(order, venue_scope=venue_scope)
            await any_store.transition_order(order.id, OrderStatus.CANCELED)
            return raw_broker_id

        monkeypatch.setattr(adapter, "submit_order", raced_submit)

    result = await execute_envelope_action(
        any_store,
        adapter,
        envelope.id,
        _envelope_action(kind, price=9.8 if kind is ActionKind.REPRICE else 9.9),
        snapshot_fingerprint=f"wo0113-envelope-ambiguous-race:{kind.value}",
        now=(
            ENVELOPE_NOW + timedelta(minutes=1)
            if kind is ActionKind.REPRICE
            else ENVELOPE_NOW
        ),
    )

    assert result.outcome == ENVELOPE_EXEC_QUARANTINED
    fresh = await any_store.get_order(result.order_id)
    assert fresh is not None
    assert fresh.status is OrderStatus.CANCELED
    recoveries = [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == result.order_id
    ]
    assert len(recoveries) == 1
    assert recoveries[0].cleanup_status == RECOVERY_NEEDS_REVIEW
    assert recoveries[0].broker_order_id == ""

    before = (len(adapter.submitted), len(adapter.replaced))
    await redrive_staged_envelope_action(
        any_store,
        adapter,
        envelope.id,
        now=ENVELOPE_NOW + timedelta(minutes=2),
    )
    assert (len(adapter.submitted), len(adapter.replaced)) == before


@pytest.mark.parametrize(
    "kind", [ActionKind.SUBMIT, ActionKind.REPRICE], ids=["submit", "reprice"]
)
async def test_sqlite_restart_repairs_envelope_acceptance_without_venue_replay(
    tmp_path,
    monkeypatch,
    kind,
):
    """The envelope fallback survives restart and repairs without another venue call."""

    database = tmp_path / f"envelope-accepted-{kind.value}.db"
    store = SqliteStateStore(database)
    adapter = MockBrokerAdapter()
    _intent, envelope, predecessor = await _prepare_envelope_acceptance(
        store, adapter, kind
    )
    predecessor_id = predecessor.id if predecessor is not None else None
    real_transition = store.transition_order
    failures = 0

    async def fail_accepted_transition(order_id, new_status, *args, **kwargs):
        nonlocal failures
        if (
            order_id != predecessor_id
            and new_status is OrderStatus.SUBMITTED
            and failures < 2
        ):
            failures += 1
            raise RuntimeError("injected envelope SUBMITTED persistence failure")
        return await real_transition(order_id, new_status, *args, **kwargs)

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("injected envelope acceptance audit failure")

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected envelope recovery persistence failure")

    monkeypatch.setattr(store, "transition_order", fail_accepted_transition)
    monkeypatch.setattr(store, "append_event", fail_audit)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery)

    try:
        with pytest.raises(RuntimeError):
            await execute_envelope_action(
                store,
                adapter,
                envelope.id,
                _envelope_action(
                    kind, price=9.8 if kind is ActionKind.REPRICE else 9.9
                ),
                snapshot_fingerprint=f"wo0113-envelope-restart:{kind.value}",
                now=(
                    ENVELOPE_NOW + timedelta(minutes=1)
                    if kind is ActionKind.REPRICE
                    else ENVELOPE_NOW
                ),
            )
        accepted_order_id = (
            adapter.replaced[-1][1]
            if kind is ActionKind.REPRICE
            else adapter.submitted[-1].id
        )
        broker_order_id = f"broker-{accepted_order_id}"
        assert any(
            event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
            and event.order_id == accepted_order_id
            and event.payload.get("broker_order_id") == broker_order_id
            for event in await store.get_execution_events()
        )
    finally:
        await store.close()

    submitted_calls = len(adapter.submitted)
    replace_calls = len(adapter.replaced)
    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        await _repair_unpersisted_submit_audits(reopened)
        repaired = await reopened.get_order(accepted_order_id)
        assert repaired is not None
        recoveries = await reopened.list_submit_recoveries()
        normal_owner = (
            repaired.status is OrderStatus.SUBMITTED
            and repaired.broker_order_id == broker_order_id
        )
        recovery_owner = any(
            recovery.local_order_id == accepted_order_id
            and recovery.broker_order_id == broker_order_id
            for recovery in recoveries
        )
        assert normal_owner or recovery_owner
        assert len(adapter.submitted) == submitted_calls
        assert len(adapter.replaced) == replace_calls
    finally:
        await reopened.close()


async def test_accepted_fallback_prevents_stale_redrive_from_reclaiming_order(
    any_store,
    monkeypatch,
):
    """A last-write owner is itself a no-resubmit barrier, even before repair."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    adapter = MockBrokerAdapter()
    real_transition = any_store.transition_order
    venue_calls = 0

    async def hostile_distinct_acceptance(_submitted, *, venue_scope):
        nonlocal venue_calls
        assert venue_scope is not None
        venue_calls += 1
        return f"hostile-acceptance-{venue_calls}-{order.id}"

    async def fail_adoption(order_id, new_status, *args, **kwargs):
        if order_id == order.id and new_status is OrderStatus.SUBMITTED:
            raise RuntimeError("injected persistent SUBMITTED failure")
        return await real_transition(order_id, new_status, *args, **kwargs)

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected persistent recovery failure")

    monkeypatch.setattr(adapter, "submit_order", hostile_distinct_acceptance)
    monkeypatch.setattr(any_store, "transition_order", fail_adoption)
    monkeypatch.setattr(any_store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError, match="durable uncertainty"):
        await _submit_pending_orders(any_store, adapter, Settings())

    assert venue_calls == 1
    await _redrive_stale_submitting(any_store, adapter, Settings())
    assert venue_calls == 1
    fallbacks = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == order.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    ]
    assert [event.payload["broker_order_id"] for event in fallbacks] == [
        f"hostile-acceptance-1-{order.id}"
    ]


@pytest.mark.parametrize("raw_broker_id", ["", "   "], ids=["empty", "whitespace"])
@pytest.mark.parametrize("entrypoint", ["first_submit", "stale_redrive"])
async def test_generic_post_call_missing_broker_identity_is_quarantined(
    any_store,
    monkeypatch,
    raw_broker_id,
    entrypoint,
):
    """Every generic post-call identity failure is ambiguous, never retryable."""

    await any_store.initialize()
    order, claim = await _created_buy_claim(any_store)
    if entrypoint == "first_submit":
        await any_store.transition_order(order.id, OrderStatus.CREATED)
    else:
        assert claim.order is not None

    adapter = MockBrokerAdapter()
    venue_calls = 0

    async def malformed_acceptance(_order, *, venue_scope):
        nonlocal venue_calls
        assert venue_scope is not None
        venue_calls += 1
        return raw_broker_id

    monkeypatch.setattr(adapter, "submit_order", malformed_acceptance)
    if entrypoint == "first_submit":
        await _submit_pending_orders(any_store, adapter, Settings())
        await _submit_pending_orders(any_store, adapter, Settings())
    else:
        await _redrive_stale_submitting(any_store, adapter, Settings())
        await _redrive_stale_submitting(any_store, adapter, Settings())

    fresh = await any_store.get_order(order.id)
    assert fresh is not None
    assert fresh.status is OrderStatus.TIMEOUT_QUARANTINE
    assert venue_calls == 1
    assert not [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == order.id
    ]


async def test_repair_rejects_broker_identity_owned_by_another_local_order(
    any_store,
):
    """Canonical repair fails closed rather than adopting one venue id twice."""

    await any_store.initialize()
    owner, owner_claim = await _created_buy_claim(any_store)
    assert owner_claim.order is not None
    broker_order_id = f"shared-repair-broker-{owner.id}"
    await any_store.transition_order(
        owner.id,
        OrderStatus.SUBMITTED,
        broker_order_id=broker_order_id,
    )

    contender, contender_claim = await _created_buy_claim(any_store)
    assert contender_claim.order is not None
    await _record_accepted_submit_uncertainty(
        any_store,
        contender_claim.order,
        broker_order_id,
        RuntimeError("injected cross-local accepted identity"),
    )

    with pytest.raises(
        (OrderTransitionError, RecoveryTransitionError),
        match="broker identity|conflicts with existing",
    ):
        await _repair_unpersisted_submit_audits(any_store)

    refreshed_owner = await any_store.get_order(owner.id)
    refreshed_contender = await any_store.get_order(contender.id)
    assert refreshed_owner is not None and refreshed_contender is not None
    assert refreshed_owner.broker_order_id == broker_order_id
    assert refreshed_contender.status is OrderStatus.SUBMITTING
    assert refreshed_contender.broker_order_id is None
    assert not [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == contender.id
    ]


async def test_fallback_writer_canonicalizes_broker_identity(any_store):
    """The shared last-write owner does not rely on every caller stripping first."""

    await any_store.initialize()
    order, claim = await _created_buy_claim(any_store)
    assert claim.order is not None
    await _record_accepted_submit_uncertainty(
        any_store,
        claim.order,
        "  fallback-canonical-id  ",
        RuntimeError("injected padded identity"),
    )

    accepted = [
        event
        for event in await any_store.get_order_execution_events(order.id)
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
    ]
    assert len(accepted) == 1
    assert accepted[0].payload["broker_order_id"] == "fallback-canonical-id"
    assert accepted[0].dedupe_key == (
        f"accepted_submit_unpersisted:{order.id}:fallback-canonical-id"
    )

    await _record_accepted_submit_uncertainty(
        any_store,
        claim.order,
        "fallback-canonical-id",
        RuntimeError("canonical replay"),
    )
    replay = [
        event
        for event in await any_store.get_order_execution_events(order.id)
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
    ]
    assert len(replay) == 1


async def test_fallback_broker_identity_blocks_foreign_order_and_recovery_owner(
    any_store,
):
    """Canonical fallback participates in global concrete-id exclusivity."""

    await any_store.initialize()
    fallback_owner, fallback_claim = await _created_buy_claim(any_store)
    assert fallback_claim.order is not None
    broker_order_id = f"fallback-owned-broker-{fallback_owner.id}"
    await _record_accepted_submit_uncertainty(
        any_store,
        fallback_claim.order,
        broker_order_id,
        RuntimeError("injected fallback-only owner"),
    )

    contender, contender_claim = await _created_buy_claim(any_store)
    assert contender_claim.order is not None
    with pytest.raises(OrderTransitionError, match="broker identity"):
        await any_store.transition_order(
            contender.id,
            OrderStatus.SUBMITTED,
            broker_order_id=broker_order_id,
        )
    with pytest.raises(RecoveryTransitionError, match="broker identity"):
        await any_store.create_submit_recovery(
            local_order_id=contender.id,
            broker_order_id=broker_order_id,
            client_order_id=contender.id,
            symbol=contender.symbol,
            side=contender.side,
            quantity=contender.quantity,
            limit_price=contender.limit_price,
            failure_reason="foreign recovery must not alias fallback owner",
            session_id=contender.session_id,
        )


async def test_fallback_identity_conflict_lookup_never_scans_all_facts(any_store):
    """Concrete-id enforcement is broker-keyed, not proportional to the log."""

    await any_store.initialize()
    fallback_owner, fallback_claim = await _created_buy_claim(any_store)
    contender, _contender_claim = await _created_buy_claim(any_store)
    assert fallback_claim.order is not None
    broker_order_id = f"key-bounded-fallback-{fallback_owner.id}"
    await _record_accepted_submit_uncertainty(
        any_store,
        fallback_claim.order,
        broker_order_id,
        RuntimeError("seed key-bounded fallback"),
    )

    class NoGlobalIteration(list):
        def __iter__(self):
            raise AssertionError("global accepted-fallback scan")

    any_store._accepted_submit_uncertainty_events = NoGlobalIteration(
        any_store._accepted_submit_uncertainty_events
    )
    with pytest.raises(RecoveryTransitionError, match="broker identity"):
        await any_store.create_submit_recovery(
            local_order_id=contender.id,
            broker_order_id=broker_order_id,
            client_order_id=contender.id,
            symbol=contender.symbol,
            side=contender.side,
            quantity=contender.quantity,
            limit_price=contender.limit_price,
            failure_reason="foreign contender must hit keyed fallback owner",
            session_id=contender.session_id,
        )


async def test_memory_order_identity_conflict_lookup_never_scans_all_orders():
    """The in-memory store uses the same broker-keyed ordinary-owner lookup."""

    store = InMemoryStateStore()
    await store.initialize()
    owner, owner_claim = await _created_buy_claim(store)
    contender, _contender_claim = await _created_buy_claim(store)
    assert owner_claim.order is not None
    broker_order_id = f"key-bounded-order-{owner.id}"
    await store.transition_order(
        owner.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
    )

    class NoGlobalValues(dict):
        def values(self):
            raise AssertionError("global order-owner scan")

    store._orders = NoGlobalValues(store._orders)
    with pytest.raises(RecoveryTransitionError, match="broker identity"):
        await store.create_submit_recovery(
            local_order_id=contender.id,
            broker_order_id=broker_order_id,
            client_order_id=contender.id,
            symbol=contender.symbol,
            side=contender.side,
            quantity=contender.quantity,
            limit_price=contender.limit_price,
            failure_reason="foreign contender must hit keyed order owner",
            session_id=contender.session_id,
        )


async def test_fallback_identity_index_discards_rolled_back_append(
    any_store, monkeypatch
):
    """A failed accepted-fact transaction cannot poison the process cache."""

    await any_store.initialize()
    owner, owner_claim = await _created_buy_claim(any_store)
    contender, _contender_claim = await _created_buy_claim(any_store)
    assert owner_claim.order is not None
    broker_order_id = f"rolled-back-fallback-{owner.id}"
    method = (
        "_reconcile_envelope_owners_for_order_unlocked"
        if hasattr(any_store, "_reconcile_envelope_owners_for_order_unlocked")
        else "_reconcile_envelope_owners_for_order_locked"
    )
    real_reconcile = getattr(any_store, method)

    def fail_after_append(*_args, **_kwargs):
        raise RuntimeError("injected post-append rollback")

    monkeypatch.setattr(any_store, method, fail_after_append)
    with pytest.raises(RuntimeError, match="post-append rollback"):
        await _record_accepted_submit_uncertainty(
            any_store,
            owner_claim.order,
            broker_order_id,
            RuntimeError("seed rolled-back fallback"),
        )
    monkeypatch.setattr(any_store, method, real_reconcile)

    adopted = await any_store.create_submit_recovery(
        local_order_id=contender.id,
        broker_order_id=broker_order_id,
        client_order_id=contender.id,
        symbol=contender.symbol,
        side=contender.side,
        quantity=contender.quantity,
        limit_price=contender.limit_price,
        failure_reason="rolled-back fallback must not retain ownership",
        session_id=contender.session_id,
    )
    assert adopted.local_order_id == contender.id


async def test_memory_order_identity_index_discards_rolled_back_assignment(
    monkeypatch,
):
    """Order-owner indexing shares the in-memory transition rollback boundary."""

    store = InMemoryStateStore()
    await store.initialize()
    owner, owner_claim = await _created_buy_claim(store)
    contender, _contender_claim = await _created_buy_claim(store)
    assert owner_claim.order is not None
    broker_order_id = f"rolled-back-order-{owner.id}"
    real_append = store._append_event_unlocked

    def fail_transition_audit(*_args, **_kwargs):
        raise RuntimeError("injected order assignment rollback")

    monkeypatch.setattr(store, "_append_event_unlocked", fail_transition_audit)
    with pytest.raises(RuntimeError, match="assignment rollback"):
        await store.transition_order(
            owner.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
        )
    monkeypatch.setattr(store, "_append_event_unlocked", real_append)

    adopted = await store.create_submit_recovery(
        local_order_id=contender.id,
        broker_order_id=broker_order_id,
        client_order_id=contender.id,
        symbol=contender.symbol,
        side=contender.side,
        quantity=contender.quantity,
        limit_price=contender.limit_price,
        failure_reason="rolled-back order assignment must not retain ownership",
        session_id=contender.session_id,
    )
    assert adopted.local_order_id == contender.id


async def test_sqlite_restart_preserves_cross_owner_broker_identity_exclusivity(
    tmp_path,
):
    """Order and fallback ownership indexes rebuild from durable truth."""

    database = tmp_path / "cross-owner-broker-identity.db"
    store = SqliteStateStore(database)
    await store.initialize()
    order_owner, order_claim = await _created_buy_claim(store)
    assert order_claim.order is not None
    await store.transition_order(
        order_owner.id,
        OrderStatus.SUBMITTED,
        broker_order_id="restart-order-owned-broker",
    )
    fallback_owner, fallback_claim = await _created_buy_claim(store)
    assert fallback_claim.order is not None
    await _record_accepted_submit_uncertainty(
        store,
        fallback_claim.order,
        "restart-fallback-owned-broker",
        RuntimeError("restart fallback owner"),
    )
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        for index, broker_order_id in enumerate(
            ["restart-order-owned-broker", "restart-fallback-owned-broker"]
        ):
            with pytest.raises(RecoveryTransitionError, match="broker identity"):
                await reopened.create_submit_recovery(
                    local_order_id=f"restart-foreign-local-{index}",
                    broker_order_id=broker_order_id,
                    client_order_id=f"restart-foreign-local-{index}",
                    symbol="AAPL",
                    side=OrderSide.BUY,
                    quantity=10,
                    limit_price=10.0,
                    failure_reason="foreign owner after restart",
                )
    finally:
        await reopened.close()


async def test_sqlite_restart_rejects_legacy_cross_local_broker_assignments(
    tmp_path,
):
    """Pre-remediation duplicate adopted ids fail closed during startup."""

    database = tmp_path / "legacy-cross-local-broker-collision.db"
    store = SqliteStateStore(database)
    await store.initialize()
    first, _first_claim = await _created_buy_claim(store)
    second, _second_claim = await _created_buy_claim(store)
    connection = store._connect()
    connection.execute(
        "UPDATE orders SET broker_order_id = ? WHERE id IN (?, ?)",
        ("legacy-shared-broker", first.id, second.id),
    )
    connection.commit()
    await store.close()

    reopened = SqliteStateStore(database)
    with pytest.raises(RecoveryTransitionError, match="multiple local owners"):
        await reopened.initialize()
    await reopened.close()


@pytest.mark.parametrize("assigned_owner", ["order", "recovery"])
async def test_sqlite_restart_rejects_assignment_fallback_identity_collision(
    tmp_path, assigned_owner
):
    """Conflicting immutable fallback truth is retained but startup fails closed."""

    database = tmp_path / f"restart-{assigned_owner}-fallback-collision.db"
    store = SqliteStateStore(database)
    await store.initialize()
    assigned, assigned_claim = await _created_buy_claim(store)
    fallback, fallback_claim = await _created_buy_claim(store)
    assert assigned_claim.order is not None
    assert fallback_claim.order is not None
    broker_order_id = f"restart-{assigned_owner}-fallback-shared"
    if assigned_owner == "order":
        await store.transition_order(
            assigned.id,
            OrderStatus.SUBMITTED,
            broker_order_id=broker_order_id,
        )
    else:
        await store.create_submit_recovery(
            local_order_id=assigned.id,
            broker_order_id=broker_order_id,
            client_order_id=assigned.id,
            symbol=assigned.symbol,
            side=assigned.side,
            quantity=assigned.quantity,
            limit_price=assigned.limit_price,
            failure_reason="assigned owner before conflicting fallback",
            session_id=assigned.session_id,
        )
    await _record_accepted_submit_uncertainty(
        store,
        fallback_claim.order,
        broker_order_id,
        RuntimeError("retain conflicting immutable fallback"),
    )
    await store.close()

    reopened = SqliteStateStore(database)
    with pytest.raises(RecoveryTransitionError, match="multiple local owners"):
        await reopened.initialize()
    await reopened.close()


async def test_distinct_accepted_fallbacks_repair_to_distinct_recovery_owners(
    any_store,
    monkeypatch,
):
    """Repair never merges or wedges two concrete acceptances for one local row."""

    await any_store.initialize()
    order, claim = await _created_buy_claim(any_store)
    assert claim.order is not None
    broker_ids = [f"accepted-one-{order.id}", f"accepted-two-{order.id}"]
    for broker_id in broker_ids:
        await _record_accepted_submit_uncertainty(
            any_store,
            claim.order,
            broker_id,
            RuntimeError(f"injected owner loss for {broker_id}"),
        )

    real_transition = any_store.transition_order

    async def fail_adoption(order_id, new_status, *args, **kwargs):
        if order_id == order.id and new_status is OrderStatus.SUBMITTED:
            raise RuntimeError("injected repair adoption failure")
        return await real_transition(order_id, new_status, *args, **kwargs)

    monkeypatch.setattr(any_store, "transition_order", fail_adoption)
    await _repair_unpersisted_submit_audits(any_store)

    recoveries = [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == order.id
    ]
    assert [recovery.broker_order_id for recovery in recoveries] == broker_ids
    checkpoint = await any_store.get_latest_execution_event(
        ExecutionEventType.SUBMIT_ACCEPTANCE_REPAIR_CHECKPOINT
    )
    assert checkpoint is not None
    assert checkpoint.payload["up_to_sequence"] >= 2

    await _repair_unpersisted_submit_audits(any_store)
    assert [
        recovery.broker_order_id
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == order.id
    ] == broker_ids

    recovery_adapter = MockBrokerAdapter()
    await _recover_unpersisted_submits(any_store, recovery_adapter)
    repaired = [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == order.id
    ]
    assert [recovery.cleanup_status for recovery in repaired] == [
        RECOVERY_RESOLVED,
        RECOVERY_RESOLVED,
    ]
    assert recovery_adapter.canceled == broker_ids
    assert recovery_adapter.status_queries == [
        broker_ids[0],
        broker_ids[0],
        broker_ids[1],
        broker_ids[1],
    ]


async def test_fallback_repair_commit_then_raise_keeps_tracked_owner(
    any_store, monkeypatch
):
    """Repair adoption re-reads a lost response before minting cleanup."""

    await any_store.initialize()
    order, claim = await _created_buy_claim(any_store)
    assert claim.order is not None
    broker_order_id = f"repair-lost-response-{order.id}"
    await _record_accepted_submit_uncertainty(
        any_store,
        claim.order,
        broker_order_id,
        RuntimeError("seed restart/repair adoption"),
    )
    real_transition = any_store.transition_order

    async def commit_then_raise(order_id, new_status, *args, **kwargs):
        result = await real_transition(order_id, new_status, *args, **kwargs)
        if order_id == order.id and new_status is OrderStatus.SUBMITTED:
            raise RuntimeError("injected lost repair response")
        return result

    monkeypatch.setattr(any_store, "transition_order", commit_then_raise)
    await _repair_unpersisted_submit_audits(any_store)

    persisted = await any_store.get_order(order.id)
    assert persisted is not None
    assert persisted.status is OrderStatus.SUBMITTED
    assert persisted.broker_order_id == broker_order_id
    assert not [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == order.id
    ]


async def test_sqlite_restart_fallback_repair_lost_response_keeps_tracked_owner(
    tmp_path, monkeypatch
):
    """The same lost-response check protects the durable restart repair path."""

    database = tmp_path / "restart-repair-lost-response.db"
    store = SqliteStateStore(database)
    await store.initialize()
    order, claim = await _created_buy_claim(store)
    assert claim.order is not None
    broker_order_id = f"restart-repair-lost-response-{order.id}"
    await _record_accepted_submit_uncertainty(
        store,
        claim.order,
        broker_order_id,
        RuntimeError("seed durable restart repair"),
    )
    await store.close()

    reopened = SqliteStateStore(database)
    await reopened.initialize()
    real_transition = reopened.transition_order

    async def commit_then_raise(order_id, new_status, *args, **kwargs):
        result = await real_transition(order_id, new_status, *args, **kwargs)
        if order_id == order.id and new_status is OrderStatus.SUBMITTED:
            raise RuntimeError("injected lost restart repair response")
        return result

    monkeypatch.setattr(reopened, "transition_order", commit_then_raise)
    try:
        await _repair_unpersisted_submit_audits(reopened)
        persisted = await reopened.get_order(order.id)
        assert persisted is not None
        assert persisted.status is OrderStatus.SUBMITTED
        assert persisted.broker_order_id == broker_order_id
        assert not [
            recovery
            for recovery in await reopened.list_submit_recoveries()
            if recovery.local_order_id == order.id
        ]
    finally:
        await reopened.close()


async def test_sqlite_restart_preserves_distinct_accepted_recovery_owners(
    tmp_path,
    monkeypatch,
):
    """Distinct accepted identities repair once and remain converged on reopen."""

    database = tmp_path / "accepted-submit-distinct-owners.db"
    store = SqliteStateStore(database)
    await store.initialize()
    order, claim = await _created_buy_claim(store)
    assert claim.order is not None
    broker_ids = [f"restart-one-{order.id}", f"restart-two-{order.id}"]
    for broker_id in broker_ids:
        await _record_accepted_submit_uncertainty(
            store,
            claim.order,
            broker_id,
            RuntimeError(f"injected restart owner loss for {broker_id}"),
        )
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        real_transition = reopened.transition_order

        async def fail_adoption(order_id, new_status, *args, **kwargs):
            if order_id == order.id and new_status is OrderStatus.SUBMITTED:
                raise RuntimeError("injected restart adoption failure")
            return await real_transition(order_id, new_status, *args, **kwargs)

        monkeypatch.setattr(reopened, "transition_order", fail_adoption)
        await _repair_unpersisted_submit_audits(reopened)
        assert [
            recovery.broker_order_id
            for recovery in await reopened.list_submit_recoveries()
            if recovery.local_order_id == order.id
        ] == broker_ids
    finally:
        await reopened.close()

    after_restart = SqliteStateStore(database)
    try:
        await after_restart.initialize()
        await _repair_unpersisted_submit_audits(after_restart)
        assert [
            recovery.broker_order_id
            for recovery in await after_restart.list_submit_recoveries()
            if recovery.local_order_id == order.id
        ] == broker_ids
    finally:
        await after_restart.close()


async def test_fill_divergence_dedupes_by_exact_accepted_identity(any_store):
    """A recovery for broker leg B cannot suppress divergence ownership for A."""

    await any_store.initialize()
    order, claim = await _created_buy_claim(any_store)
    assert claim.order is not None
    broker_a = f"broker-fill-a-{order.id}"
    broker_b = f"broker-fill-b-{order.id}"
    await any_store.transition_order(
        order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=broker_a,
    )
    refreshed = await any_store.get_order(order.id)
    assert refreshed is not None
    await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=broker_b,
        client_order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason="independent accepted broker leg B",
        session_id=order.session_id,
    )

    await _escalate_fill_divergence(
        any_store,
        refreshed,
        BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 1, []),
        0,
        [{"reason": "unpriceable broker fill for leg A"}],
        [],
    )

    leg_a = await any_store.get_submit_recovery_by_identity(order.id, broker_a)
    leg_b = await any_store.get_submit_recovery_by_identity(order.id, broker_b)
    assert leg_a is not None
    assert leg_a.cleanup_status == RECOVERY_NEEDS_REVIEW
    assert leg_b is not None


async def test_recovery_cleanup_uses_immutable_record_scope_without_order_lookup(
    any_store, monkeypatch
):
    """An orphan recovery remains independently pollable/cancelable."""

    await any_store.initialize()
    order, _ = await _created_buy_claim(any_store)
    broker_order_id = f"broker-orphan-{order.id}"
    await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=broker_order_id,
        client_order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason="orphan cleanup scope pin",
        session_id=order.session_id,
    )
    adapter = MockBrokerAdapter()
    adapter.set_response(
        broker_order_id,
        BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, []),
    )

    async def forbidden_order_lookup(_order_id):
        raise RuntimeError("recovery cleanup must not depend on local row lookup")

    monkeypatch.setattr(any_store, "get_order", forbidden_order_lookup)
    await _recover_unpersisted_submits(any_store, adapter)

    [recovery] = await any_store.list_submit_recoveries()
    assert recovery.cleanup_status == RECOVERY_RESOLVED
    assert adapter.canceled == [broker_order_id]


async def test_double_persist_failure_keeps_accepted_buy_owned(any_store, monkeypatch):
    """An accepted BUY remains exposure when audit and recovery writes both fail."""

    await _held_position(any_store)
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    buy = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order
    real_append_event = any_store.append_event
    real_create_recovery = any_store.create_submit_recovery

    async def accept_then_cancel_local(order, *, venue_scope):
        broker_id = await real_submit(order, venue_scope=venue_scope)
        await any_store.transition_order(order.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("injected accepted-submit audit failure")

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected accepted-submit recovery failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(any_store, "append_event", fail_audit)
    monkeypatch.setattr(any_store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError):
        await _submit_pending_orders(any_store, adapter, Settings())

    accepted = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == buy.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    ]
    assert len(accepted) == 1
    assert accepted[0].source is EventSource.ENGINE
    assert accepted[0].authority is EventAuthority.LOCAL
    assert accepted[0].symbol == buy.symbol
    assert accepted[0].side is OrderSide.BUY
    broker_id = accepted[0].payload["broker_order_id"]

    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    with pytest.raises(SellIntentTransitionError, match="same-symbol BUY may execute"):
        await any_store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.MARKET,
        )

    monkeypatch.setattr(any_store, "append_event", real_append_event)
    monkeypatch.setattr(any_store, "create_submit_recovery", real_create_recovery)
    await _repair_unpersisted_submit_audits(any_store)

    recoveries = await any_store.list_submit_recoveries()
    assert [
        (record.local_order_id, record.broker_order_id)
        for record in recoveries
        if record.local_order_id == buy.id
    ] == [(buy.id, broker_id)]
    assert len(adapter.submitted) == 1


async def test_sqlite_restart_repairs_accepted_submit_uncertainty(
    tmp_path, monkeypatch
):
    """The last-write uncertainty owner survives a process restart."""

    database = tmp_path / "accepted-submit-uncertainty.db"
    store = SqliteStateStore(database)
    await _held_position(store)
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    buy = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order

    async def accept_then_cancel_local(order, *, venue_scope):
        broker_id = await real_submit(order, venue_scope=venue_scope)
        await store.transition_order(order.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_audit(*_args, **_kwargs):
        raise RuntimeError("injected accepted-submit audit failure")

    async def fail_recovery(**_kwargs):
        raise RuntimeError("injected accepted-submit recovery failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(store, "append_event", fail_audit)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery)

    with pytest.raises(RuntimeError, match="durable uncertainty"):
        await _submit_pending_orders(store, adapter, Settings())

    fallback = next(
        event
        for event in await store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == buy.id
        and event.payload.get("reason") == "accepted_submit_unpersisted"
    )
    broker_id = fallback.payload["broker_order_id"]
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        await _repair_unpersisted_submit_audits(reopened)
        recoveries = await reopened.list_submit_recoveries()
        assert [
            (record.local_order_id, record.broker_order_id)
            for record in recoveries
            if record.local_order_id == buy.id
        ] == [(buy.id, broker_id)]
        assert len(adapter.submitted) == 1
    finally:
        await reopened.close()


async def test_double_persist_failure_keeps_accepted_sell_owned(any_store, monkeypatch):
    """An accepted SELL fallback blocks an opposite-side BUY claim on both stores."""

    sell, _fallback, candidate_id = await _accepted_sell_without_local_owner(
        any_store, monkeypatch
    )

    with pytest.raises(OrderIntentBlockedError, match="same-symbol exit may execute"):
        await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=10.0
        )
    buy, claim = await _created_buy_claim(any_store, candidate_id=candidate_id)

    assert claim.outcome == "blocked"
    assert claim.order is None
    assert claim.reason == f"same-symbol exit may execute ({sell.id})"
    assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED


async def test_sqlite_restart_keeps_accepted_sell_as_exit_exposure(
    tmp_path, monkeypatch
):
    """A SELL fallback still blocks BUY submission after a SQLite restart."""

    database = tmp_path / "accepted-sell-uncertainty.db"
    store = SqliteStateStore(database)
    sell, fallback, candidate_id = await _accepted_sell_without_local_owner(
        store, monkeypatch
    )
    broker_id = fallback.payload["broker_order_id"]
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        with pytest.raises(
            OrderIntentBlockedError, match="same-symbol exit may execute"
        ):
            await reopened.create_candidate(
                "AAPL", suggested_quantity=10, suggested_limit_price=10.0
            )
        buy, claim = await _created_buy_claim(reopened, candidate_id=candidate_id)

        assert claim.outcome == "blocked"
        assert claim.order is None
        assert claim.reason == f"same-symbol exit may execute ({sell.id})"
        assert (await reopened.get_order(buy.id)).status is OrderStatus.CREATED
        assert any(
            event.order_id == sell.id
            and event.payload.get("broker_order_id") == broker_id
            for event in await reopened.get_execution_events()
        )
    finally:
        await reopened.close()


@pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
async def test_audit_only_acceptance_still_gets_execution_uncertainty_owner(
    any_store, monkeypatch, side
):
    """The ordinary audit is diagnostic, not a substitute for an exposure owner."""

    accepted, fallback, candidate_id = await _accepted_order_with_audit_only(
        any_store, side, monkeypatch
    )

    assert len(fallback) == 1
    assert fallback[0].side is side
    if side is OrderSide.BUY:
        intent = await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
        )
        await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
        with pytest.raises(
            SellIntentTransitionError, match="same-symbol BUY may execute"
        ):
            await any_store.create_order_for_sell_intent(
                intent.id,
                order_type=OrderType.MARKET,
            )
    else:
        with pytest.raises(
            OrderIntentBlockedError, match="same-symbol exit may execute"
        ):
            await any_store.create_candidate(
                "AAPL", suggested_quantity=10, suggested_limit_price=10.0
            )
        assert candidate_id is not None
        buy, claim = await _created_buy_claim(any_store, candidate_id=candidate_id)
        assert claim.outcome == "blocked"
        assert claim.order is None
        assert claim.reason == f"same-symbol exit may execute ({accepted.id})"
        assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED


@pytest.mark.parametrize(
    "malformation",
    ["scope", "source", "authority", "dedupe"],
)
async def test_malformed_accepted_submit_truth_cannot_disappear_from_scope(
    any_store, malformation
):
    """Only canonical fallback truth may be released by a represented broker id."""

    await _held_position(any_store)
    reference_symbol = "MSFT" if malformation == "scope" else "AAPL"
    reference_side = OrderSide.SELL if malformation == "scope" else OrderSide.BUY
    candidate = await any_store.create_candidate(
        reference_symbol,
        suggested_quantity=10,
        suggested_limit_price=10.0,
    )
    referenced = await any_store.create_order_for_test(
        candidate.id,
        reference_symbol,
        reference_side,
        10,
        limit_price=10.0,
    )
    claim = await any_store.claim_order_for_submission(referenced.id)
    assert claim.order is not None
    broker_id = f"broker-{malformation}"
    await any_store.transition_order(
        referenced.id,
        OrderStatus.SUBMITTED,
        broker_order_id=broker_id,
    )
    await any_store.transition_order(referenced.id, OrderStatus.CANCELED)

    dedupe_key = f"accepted_submit_unpersisted:{referenced.id}:{broker_id}"
    await any_store.append_execution_event(
        ExecutionEvent(
            id=f"malformed-accepted-{malformation}",
            event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
            source=(
                EventSource.BROKER_REST
                if malformation == "source"
                else EventSource.ENGINE
            ),
            authority=(
                EventAuthority.SYNTHETIC
                if malformation == "authority"
                else EventAuthority.LOCAL
            ),
            dedupe_key=(
                f"wrong:{referenced.id}:{broker_id}"
                if malformation == "dedupe"
                else dedupe_key
            ),
            ts_init=datetime(2026, 7, 19, 12, tzinfo=UTC),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            price=10.0,
            order_id=referenced.id,
            session_id=referenced.session_id,
            payload={
                "reason": "accepted_submit_unpersisted",
                "broker_order_id": broker_id,
                "error": "forged fallback",
            },
        )
    )

    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    with pytest.raises(SellIntentTransitionError, match="same-symbol BUY may execute"):
        await any_store.create_order_for_sell_intent(
            intent.id,
            order_type=OrderType.MARKET,
        )


async def test_fallback_dedupe_collision_validates_complete_immutable_scope(
    any_store,
):
    """A reserved dedupe collision cannot bless mismatched quantity truth."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=10.0
    )
    order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
    )
    broker_id = f"broker-{order.id}"
    dedupe_key = f"accepted_submit_unpersisted:{order.id}:{broker_id}"
    await any_store.append_execution_event(
        ExecutionEvent(
            id="forged-accepted-submit-collision",
            event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=dedupe_key,
            ts_init=datetime(2026, 7, 19, 12, tzinfo=UTC),
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity + 1,
            price=order.limit_price,
            order_id=order.id,
            session_id=order.session_id,
            correlation_id=order.candidate_id,
            payload={
                "reason": "accepted_submit_unpersisted",
                "broker_order_id": broker_id,
                "error": "forged quantity",
            },
        )
    )
    with pytest.raises(RecoveryTransitionError, match="conflicting truth"):
        await _record_accepted_submit_uncertainty(
            any_store,
            order,
            broker_id,
            RuntimeError("injected accepted-submit recovery failure"),
        )

    collisions = [
        event
        for event in await any_store.get_execution_events()
        if event.dedupe_key == dedupe_key
    ]
    assert len(collisions) == 1
    assert collisions[0].quantity == order.quantity + 1
