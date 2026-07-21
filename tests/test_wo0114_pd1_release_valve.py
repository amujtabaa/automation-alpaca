"""WO-0114 — PD-1 human-attested ``needs_review`` release valve.

Red-first contract for the ratified D-PD1-1..4 decisions.  The release command
is deliberately tested at the store boundary first: identity/parity checks and
the status/audit/execution-event writes must share the store's serialization
boundary.  HTTP and cockpit tests then pin the thin typed boundary separately.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.api.deps import get_command_facade
from app.facade.errors import ConflictError, InvalidInputError
from app.facade.store_backed import StoreBackedCommandFacade, StoreBackedQueryFacade
from app.main import create_app
from app.broker.mock import MockBrokerAdapter
from app.monitoring import _recover_unpersisted_submits
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    RECOVERY_OPERATOR_RECONCILED,
    RECOVERY_RESOLVED,
    RECOVERY_STATUSES,
    RECOVERY_TRANSITIONS,
    EventAuthority,
    EventSource,
    EventType,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderType,
    OrderSide,
    OrderStatus,
    SellIntentStatus,
    SellReason,
    SessionType,
    SubmitRecoveryAttestation,
    SubmitRecoveryFillCommand,
)
from app.store.base import (
    FlattenBlockedError,
    RecoveryTransitionError,
    SellIntentTransitionError,
    UnknownEntityError,
)
from app.store.core import (
    EnvelopeActionPausedError,
    canonical_recovery_fill_quantity,
    recovery_status_event,
    validate_recovery_attested_facts,
    validate_recovery_fill_facts,
    validate_submit_recovery_identity,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore


pytestmark = pytest.mark.anyio


async def _needs_review_order(
    store,
    *,
    quantity: int = 10,
    symbol: str = "AAPL",
    side: OrderSide = OrderSide.BUY,
    cleanup_status: str = RECOVERY_NEEDS_REVIEW,
    order_broker_order_id: str | None = None,
):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        symbol,
        side,
        quantity,
        session_id=session.id,
    )
    claimed = await store.claim_order_for_submission(order.id)
    assert claimed.order is not None
    await store.transition_order(
        order.id,
        OrderStatus.CANCELED,
        broker_order_id=order_broker_order_id,
    )
    recovery = await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"broker-{order.id}",
        client_order_id=f"client-{order.id}",
        symbol=symbol,
        side=side,
        quantity=quantity,
        failure_reason="WO-0114 red fixture",
        session_id=session.id,
        cleanup_status=cleanup_status,
    )
    return session, candidate, order, recovery


def _attestation(candidate, order, recovery, **changes) -> SubmitRecoveryAttestation:
    values = {
        "recovery_id": recovery.id,
        "local_order_id": recovery.local_order_id,
        "broker_order_id": recovery.broker_order_id,
        "client_order_id": recovery.client_order_id,
        "symbol": recovery.symbol,
        "side": recovery.side,
        "candidate_id": candidate.id,
        "sell_intent_id": None,
        "envelope_id": None,
        "broker_terminal_state": OrderStatus.CANCELED,
        "cumulative_filled_quantity": 0,
        "reason": "venue activity reconciled by operator",
        "evidence_ref": "paper://orders/evidence-0114",
    }
    values.update(changes)
    return SubmitRecoveryAttestation(**values)


def _fill_command(candidate, order, recovery, **changes) -> SubmitRecoveryFillCommand:
    values = {
        "recovery_id": recovery.id,
        "local_order_id": recovery.local_order_id,
        "broker_order_id": recovery.broker_order_id,
        "client_order_id": recovery.client_order_id,
        "symbol": recovery.symbol,
        "side": recovery.side,
        "candidate_id": candidate.id,
        "sell_intent_id": None,
        "envelope_id": None,
        "fill_quantity": 4,
        "cumulative_filled_quantity": 4,
        "price": 10.25,
        "reason": "operator imported broker execution",
        "evidence_ref": "paper://fills/evidence-0114",
    }
    values.update(changes)
    return SubmitRecoveryFillCommand(**values)


async def _truth_counts(store) -> tuple[int, int, int, tuple[str, ...]]:
    return (
        len(await store.list_events()),
        len(await store.get_execution_events()),
        len(await store.list_fills()),
        tuple(r.cleanup_status for r in await store.list_submit_recoveries()),
    )


def test_operator_reconciled_is_one_way_terminal_vocabulary():
    assert RECOVERY_OPERATOR_RECONCILED in RECOVERY_STATUSES
    assert RECOVERY_OPERATOR_RECONCILED not in RECOVERY_OPEN_STATUSES
    assert RECOVERY_TRANSITIONS[RECOVERY_NEEDS_REVIEW] == frozenset(
        {RECOVERY_OPERATOR_RECONCILED}
    )
    assert RECOVERY_TRANSITIONS[RECOVERY_OPERATOR_RECONCILED] == frozenset()
    assert (
        recovery_status_event(RECOVERY_NEEDS_REVIEW, RECOVERY_OPERATOR_RECONCILED)
        == EventType.SUBMIT_RECOVERY_RECONCILED.value
    )


async def test_generic_update_cannot_bypass_operator_attestation(any_store):
    _, _, _, recovery = await _needs_review_order(any_store)
    before = await _truth_counts(any_store)

    with pytest.raises(RecoveryTransitionError, match="attestation"):
        await any_store.update_submit_recovery(
            recovery.id, cleanup_status=RECOVERY_OPERATOR_RECONCILED
        )

    assert await _truth_counts(any_store) == before


async def test_zero_fill_release_is_atomic_visible_and_position_neutral(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    attestation = _attestation(candidate, order, recovery)
    before_position = (await any_store.get_position(order.symbol)).model_dump(
        mode="json"
    )

    released = await any_store.reconcile_submit_recovery(
        attestation, actor="operator-a"
    )

    assert released.cleanup_status == RECOVERY_OPERATOR_RECONCILED
    after_position = (await any_store.get_position(order.symbol)).model_dump(
        mode="json"
    )
    assert after_position == before_position
    assert await any_store.list_submit_recoveries(statuses=RECOVERY_OPEN_STATUSES) == []
    assert (await any_store.list_submit_recoveries())[0].id == recovery.id

    audits = [
        event
        for event in await any_store.list_events()
        if event.event_type == EventType.SUBMIT_RECOVERY_RECONCILED.value
    ]
    assert len(audits) == 1
    assert audits[0].payload["actor"] == "operator-a"
    assert audits[0].payload["reason"] == attestation.reason
    assert audits[0].payload["evidence_ref"] == attestation.evidence_ref
    assert audits[0].payload["broker_terminal_state"] == "canceled"
    assert audits[0].payload["cumulative_filled_quantity"] == 0

    facts = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.SUBMIT_RECOVERY_OPERATOR_RECONCILED
    ]
    assert len(facts) == 1
    assert facts[0].source is EventSource.ENGINE
    assert facts[0].authority is EventAuthority.LOCAL
    assert facts[0].order_id == order.id
    assert facts[0].payload["recovery_id"] == recovery.id


async def test_exact_repeat_is_write_free_conflicting_repeat_is_refused(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    attestation = _attestation(candidate, order, recovery)
    first = await any_store.reconcile_submit_recovery(attestation, actor="operator-a")
    after_first = await _truth_counts(any_store)

    repeated = await any_store.reconcile_submit_recovery(
        attestation, actor="operator-a"
    )
    assert repeated == first
    assert await _truth_counts(any_store) == after_first

    conflicting = attestation.model_copy(update={"evidence_ref": "paper://different"})
    with pytest.raises(RecoveryTransitionError, match="conflicting"):
        await any_store.reconcile_submit_recovery(conflicting, actor="operator-a")
    assert await _truth_counts(any_store) == after_first


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("recovery_id", "wrong-recovery"),
        ("local_order_id", "wrong-order"),
        ("broker_order_id", "wrong-broker"),
        ("client_order_id", "wrong-client"),
        ("symbol", "MSFT"),
        ("side", OrderSide.SELL),
        ("candidate_id", "wrong-owner"),
        ("sell_intent_id", "wrong-sell-intent"),
        ("envelope_id", "wrong-envelope"),
        ("cumulative_filled_quantity", 1),
        ("broker_terminal_state", OrderStatus.SUBMITTED),
    ],
)
async def test_attestation_mismatch_fails_closed_zero_writes(any_store, field, bad):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    command = _attestation(candidate, order, recovery).model_copy(update={field: bad})
    before = await _truth_counts(any_store)

    with pytest.raises((RecoveryTransitionError, UnknownEntityError)):
        await any_store.reconcile_submit_recovery(command, actor="operator-a")

    assert await _truth_counts(any_store) == before


async def test_filled_attestation_cannot_be_partial(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store, quantity=10)
    command = _fill_command(candidate, order, recovery)
    await any_store.ingest_submit_recovery_fill(command, actor="operator-a")
    before = await _truth_counts(any_store)

    with pytest.raises(RecoveryTransitionError, match="FILLED.*quantity"):
        await any_store.reconcile_submit_recovery(
            _attestation(
                candidate,
                order,
                recovery,
                broker_terminal_state=OrderStatus.FILLED,
                cumulative_filled_quantity=4,
            ),
            actor="operator-a",
        )

    assert await _truth_counts(any_store) == before


async def test_recovery_without_durable_claim_occurrence_fails_closed(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        session_id=session.id,
    )
    recovery = await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"broker-{order.id}",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        failure_reason="malformed recovery without a submission claim",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    before = await _truth_counts(any_store)

    with pytest.raises(RecoveryTransitionError, match="claim occurrence"):
        await any_store.reconcile_submit_recovery(
            _attestation(
                candidate,
                order,
                recovery,
                client_order_id=None,
            ),
            actor="operator-a",
        )

    assert await _truth_counts(any_store) == before


@pytest.mark.parametrize("actor", ["", "   "])
async def test_release_denies_blank_actor(any_store, actor):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    before = await _truth_counts(any_store)
    with pytest.raises(RecoveryTransitionError, match="actor"):
        await any_store.reconcile_submit_recovery(
            _attestation(candidate, order, recovery), actor=actor
        )
    assert await _truth_counts(any_store) == before


@pytest.mark.parametrize(("field", "bad"), [("reason", "   "), ("evidence_ref", "")])
async def test_release_denies_incomplete_evidence(any_store, field, bad):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    command = _attestation(candidate, order, recovery).model_copy(update={field: bad})
    before = await _truth_counts(any_store)
    with pytest.raises(RecoveryTransitionError, match=field):
        await any_store.reconcile_submit_recovery(command, actor="operator-a")
    assert await _truth_counts(any_store) == before


async def test_discovered_fill_is_human_attested_deduped_and_releasable(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    command = _fill_command(candidate, order, recovery)

    first = await any_store.ingest_submit_recovery_fill(command, actor="operator-a")
    repeated = await any_store.ingest_submit_recovery_fill(command, actor="operator-a")
    after_repeat = await _truth_counts(any_store)

    with pytest.raises(RecoveryTransitionError, match="conflicting"):
        await any_store.ingest_submit_recovery_fill(
            command.model_copy(update={"price": 11.25}), actor="operator-a"
        )

    assert first.status == "appended"
    assert repeated.status == "duplicate"
    assert await _truth_counts(any_store) == after_repeat
    assert (await any_store.get_position(order.symbol)).quantity == 4
    fills = await any_store.list_fills(order_id=order.id)
    assert len(fills) == 1
    assert fills[0].source_fill_id == f"{recovery.broker_order_id}:4"
    facts = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.FILL and event.order_id == order.id
    ]
    assert len(facts) == 1
    assert facts[0].source is EventSource.OPERATOR
    assert facts[0].authority is EventAuthority.HUMAN_ATTESTED
    assert facts[0].payload["actor"] == "operator-a"
    assert facts[0].payload["broker_order_id"] == recovery.broker_order_id
    assert facts[0].payload["evidence_ref"] == command.evidence_ref

    before_release = (await any_store.get_position(order.symbol)).model_dump(
        mode="json"
    )
    attestation = _attestation(
        candidate,
        order,
        recovery,
        cumulative_filled_quantity=command.cumulative_filled_quantity,
    )
    await any_store.reconcile_submit_recovery(attestation, actor="operator-a")
    assert (await any_store.get_position(order.symbol)).model_dump(
        mode="json"
    ) == before_release


async def test_fully_filled_terminal_attestation_matches_two_canonical_fills(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store, quantity=10)
    await any_store.ingest_submit_recovery_fill(
        _fill_command(candidate, order, recovery), actor="operator-a"
    )
    await any_store.ingest_submit_recovery_fill(
        _fill_command(
            candidate,
            order,
            recovery,
            fill_quantity=6,
            cumulative_filled_quantity=10,
            price=10.5,
        ),
        actor="operator-a",
    )

    released = await any_store.reconcile_submit_recovery(
        _attestation(
            candidate,
            order,
            recovery,
            broker_terminal_state=OrderStatus.FILLED,
            cumulative_filled_quantity=10,
        ),
        actor="operator-a",
    )

    assert released.cleanup_status == RECOVERY_OPERATOR_RECONCILED
    assert (await any_store.get_position("AAPL")).quantity == 10
    assert len(await any_store.list_fills(order_id=order.id)) == 2


async def test_operator_fill_over_order_capacity_is_rejected(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store, quantity=5)
    before_position = (await any_store.get_position(order.symbol)).model_dump(
        mode="json"
    )
    with pytest.raises(RecoveryTransitionError, match="cumulative"):
        await any_store.ingest_submit_recovery_fill(
            _fill_command(
                candidate,
                order,
                recovery,
                fill_quantity=6,
                cumulative_filled_quantity=6,
            ),
            actor="operator-a",
        )
    assert (await any_store.get_position(order.symbol)).model_dump(
        mode="json"
    ) == before_position
    assert await any_store.list_fills(order_id=order.id) == []


async def test_interleaved_conflicting_attestations_exactly_one_applies(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    first = _attestation(candidate, order, recovery, evidence_ref="paper://first")
    second = _attestation(candidate, order, recovery, evidence_ref="paper://second")

    results = await asyncio.gather(
        any_store.reconcile_submit_recovery(first, actor="operator-a"),
        any_store.reconcile_submit_recovery(second, actor="operator-b"),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    failures = [result for result in results if isinstance(result, Exception)]
    assert len(failures) == 1 and isinstance(failures[0], RecoveryTransitionError)
    audits = await any_store.list_events(
        event_type=EventType.SUBMIT_RECOVERY_RECONCILED.value
    )
    assert len(audits) == 1


async def test_concurrent_recovery_tick_never_touches_needs_review_record(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    broker = MockBrokerAdapter()

    released, _ = await asyncio.gather(
        any_store.reconcile_submit_recovery(
            _attestation(candidate, order, recovery), actor="operator-a"
        ),
        _recover_unpersisted_submits(any_store, broker),
    )

    assert released.cleanup_status == RECOVERY_OPERATOR_RECONCILED
    assert broker.status_queries == []
    assert broker.canceled == []
    assert (
        len(
            await any_store.list_events(
                event_type=EventType.SUBMIT_RECOVERY_RECONCILED.value
            )
        )
        == 1
    )


async def test_sqlite_reopen_preserves_fill_and_release_idempotency(tmp_path):
    path = tmp_path / "wo0114.db"
    first_store = SqliteStateStore(path)
    _, candidate, order, recovery = await _needs_review_order(first_store)
    fill_command = _fill_command(candidate, order, recovery)
    attestation = _attestation(candidate, order, recovery, cumulative_filled_quantity=4)
    await first_store.ingest_submit_recovery_fill(fill_command, actor="operator-a")
    await first_store.reconcile_submit_recovery(attestation, actor="operator-a")
    before = await _truth_counts(first_store)
    await first_store.close()

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    duplicate_fill = await reopened.ingest_submit_recovery_fill(
        fill_command, actor="operator-a"
    )
    repeated_release = await reopened.reconcile_submit_recovery(
        attestation, actor="operator-a"
    )

    assert duplicate_fill.status == "duplicate"
    assert repeated_release.cleanup_status == RECOVERY_OPERATOR_RECONCILED
    assert await _truth_counts(reopened) == before
    assert (await reopened.get_position(order.symbol)).quantity == 4
    await reopened.close()


async def test_facade_maps_malformed_to_422_and_state_conflict_to_409(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    facade = StoreBackedCommandFacade(any_store)

    with pytest.raises(InvalidInputError):
        await facade.reconcile_submit_recovery(
            attestation=_attestation(candidate, order, recovery), actor=" "
        )

    await facade.reconcile_submit_recovery(
        attestation=_attestation(candidate, order, recovery), actor="operator-a"
    )
    with pytest.raises(ConflictError):
        await facade.reconcile_submit_recovery(
            attestation=_attestation(
                candidate, order, recovery, evidence_ref="paper://conflict"
            ),
            actor="operator-a",
        )


async def test_http_requires_actor_and_uses_typed_command_facade():
    class SpyFacade:
        def __init__(self):
            self.calls = []

        async def reconcile_submit_recovery(self, *, attestation, actor):
            self.calls.append((attestation, actor))
            return {
                "id": attestation.recovery_id,
                "local_order_id": attestation.local_order_id,
                "broker_order_id": attestation.broker_order_id,
                "client_order_id": attestation.client_order_id,
                "symbol": attestation.symbol,
                "side": attestation.side,
                "quantity": 1,
                "failure_reason": "test",
                "cleanup_status": "operator_reconciled",
            }

        async def ingest_submit_recovery_fill(self, *, command, actor):
            self.calls.append((command, actor))
            return {
                "status": "appended",
                "recovery": {
                    "id": command.recovery_id,
                    "local_order_id": command.local_order_id,
                    "broker_order_id": command.broker_order_id,
                    "client_order_id": command.client_order_id,
                    "symbol": command.symbol,
                    "side": command.side,
                    "quantity": 1,
                    "failure_reason": "test",
                    "cleanup_status": "needs_review",
                },
                "fill": None,
            }

    spy = SpyFacade()
    app = create_app()
    app.dependency_overrides[get_command_facade] = lambda: spy
    payload = {
        "recovery_id": "r1",
        "local_order_id": "o1",
        "broker_order_id": "b1",
        "client_order_id": None,
        "symbol": "AAPL",
        "side": "buy",
        "candidate_id": "c1",
        "sell_intent_id": None,
        "envelope_id": None,
        "broker_terminal_state": "canceled",
        "cumulative_filled_quantity": 0,
        "reason": "checked",
        "evidence_ref": "paper://evidence",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        missing = await client.post("/api/order-recoveries/r1/reconcile", json=payload)
        assert missing.status_code == 422
        ok = await client.post(
            "/api/order-recoveries/r1/reconcile",
            json=payload,
            headers={"X-Actor": "operator-a"},
        )

    assert ok.status_code == 200, ok.text
    assert len(spy.calls) == 1
    assert spy.calls[0][0].recovery_id == "r1"
    assert spy.calls[0][1] == "operator-a"

    fill_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"broker_terminal_state", "cumulative_filled_quantity"}
    }
    fill_payload.update(
        fill_quantity=1,
        cumulative_filled_quantity=1,
        price=10.0,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        fill = await client.post(
            "/api/order-recoveries/r1/fills",
            json=fill_payload,
            headers={"X-Actor": "operator-a"},
        )
        malformed = await client.post(
            "/api/order-recoveries/r1/fills",
            json={**fill_payload, "fill_quantity": "1"},
            headers={"X-Actor": "operator-a"},
        )

    assert fill.status_code == 200, fill.text
    assert malformed.status_code == 422
    assert len(spy.calls) == 2
    assert spy.calls[1][0].recovery_id == "r1"
    assert spy.calls[1][1] == "operator-a"


_NOW = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)


def _envelope_draft(intent_id: str, session_id: str, *, quantity: int = 10):
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=quantity,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=_NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _envelope_action(quantity: int = 10):
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _envelope_needs_review(store):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 10, session_id=session.id
    )
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        10,
        10.0,
        source_fill_id="wo0114-held",
        session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=10,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _envelope_draft(intent.id, session.id), actor="operator-a"
    )
    staged = await store.stage_envelope_action(
        envelope.id,
        _envelope_action(),
        snapshot_fingerprint="wo0114-envelope",
        now=_NOW,
    )
    claimed = await store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await store.transition_order(staged.order.id, OrderStatus.CANCELED)
    recovery = await store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id=f"broker-{staged.order.id}",
        client_order_id=f"client-{staged.order.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=10,
        limit_price=9.9,
        failure_reason="envelope child needs review",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    return session, intent, envelope, staged.order, recovery


def _envelope_attestation(intent, envelope, order, recovery, **changes):
    values = {
        "recovery_id": recovery.id,
        "local_order_id": order.id,
        "broker_order_id": recovery.broker_order_id,
        "client_order_id": recovery.client_order_id,
        "symbol": "AAPL",
        "side": OrderSide.SELL,
        "candidate_id": None,
        "sell_intent_id": intent.id,
        "envelope_id": envelope.id,
        "broker_terminal_state": OrderStatus.CANCELED,
        "cumulative_filled_quantity": 0,
        "reason": "paper venue reconciled",
        "evidence_ref": "paper://envelope/recovery",
    }
    values.update(changes)
    return SubmitRecoveryAttestation(**values)


def _envelope_fill(intent, envelope, order, recovery, **changes):
    values = {
        "recovery_id": recovery.id,
        "local_order_id": order.id,
        "broker_order_id": recovery.broker_order_id,
        "client_order_id": recovery.client_order_id,
        "symbol": "AAPL",
        "side": OrderSide.SELL,
        "candidate_id": None,
        "sell_intent_id": intent.id,
        "envelope_id": envelope.id,
        "fill_quantity": 4,
        "cumulative_filled_quantity": 4,
        "price": 9.9,
        "reason": "paper fill imported",
        "evidence_ref": "paper://envelope/fill",
    }
    values.update(changes)
    return SubmitRecoveryFillCommand(**values)


async def test_envelope_fill_and_release_preserve_lineage_and_apply_once(any_store):
    _, intent, envelope, order, recovery = await _envelope_needs_review(any_store)
    command = _envelope_fill(intent, envelope, order, recovery)

    await any_store.ingest_submit_recovery_fill(command, actor="operator-a")
    await any_store.ingest_submit_recovery_fill(command, actor="operator-a")

    assert (await any_store.get_position("AAPL")).quantity == 6
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 6
    before_release = (await any_store.get_position("AAPL")).model_dump(mode="json")
    await any_store.reconcile_submit_recovery(
        _envelope_attestation(
            intent,
            envelope,
            order,
            recovery,
            cumulative_filled_quantity=4,
        ),
        actor="operator-a",
    )
    assert (await any_store.get_position("AAPL")).model_dump(
        mode="json"
    ) == before_release

    # The released child no longer pauses the SAME envelope's next bounded slice.
    next_stage = await any_store.stage_envelope_action(
        envelope.id,
        _envelope_action(quantity=6),
        snapshot_fingerprint="wo0114-envelope-next",
        now=_NOW + timedelta(seconds=5),
    )
    assert next_stage.order.quantity == 6


async def test_second_needs_review_predicate_keeps_envelope_paused(any_store):
    session, intent, envelope, order, recovery = await _envelope_needs_review(any_store)
    second_recovery = await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"broker-second-{order.id}",
        client_order_id=f"client-{order.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=10,
        limit_price=9.9,
        failure_reason="independent same-symbol uncertainty",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )

    await any_store.reconcile_submit_recovery(
        _envelope_attestation(intent, envelope, order, recovery), actor="operator-a"
    )
    with pytest.raises(EnvelopeActionPausedError, match="needs_review"):
        await any_store.stage_envelope_action(
            envelope.id,
            _envelope_action(),
            snapshot_fingerprint="still-paused",
            now=_NOW + timedelta(seconds=5),
        )

    await any_store.reconcile_submit_recovery(
        _envelope_attestation(intent, envelope, order, second_recovery),
        actor="operator-a",
    )
    staged = await any_store.stage_envelope_action(
        envelope.id,
        _envelope_action(),
        snapshot_fingerprint="last-predicate-cleared",
        now=_NOW + timedelta(seconds=10),
    )
    assert staged.order is not None


async def test_multiple_broker_legs_refuse_unscoped_legacy_fill(any_store):
    session, candidate, order, first = await _needs_review_order(any_store)
    second = await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"broker-second-{order.id}",
        client_order_id=f"client-{order.id}",
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        failure_reason="second accepted leg",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    await any_store.append_fill(
        order.id,
        order.symbol,
        order.side,
        1,
        10.0,
        source_fill_id="legacy-unscoped-execution",
        session_id=session.id,
    )
    before = await _truth_counts(any_store)

    with pytest.raises(RecoveryTransitionError, match="ambiguous"):
        await any_store.reconcile_submit_recovery(
            _attestation(candidate, order, first, cumulative_filled_quantity=1),
            actor="operator-a",
        )
    assert await _truth_counts(any_store) == before
    assert second.cleanup_status == RECOVERY_NEEDS_REVIEW


async def test_adr001_overfill_latch_survives_operator_release(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    held_candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    held = await any_store.create_order_for_test(
        held_candidate.id, "AAPL", OrderSide.BUY, 5, session_id=session.id
    )
    await any_store.append_fill(
        held.id,
        "AAPL",
        OrderSide.BUY,
        5,
        10.0,
        source_fill_id="held-five",
        session_id=session.id,
    )
    await any_store.transition_order(held.id, OrderStatus.CANCELED)
    exit_candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    exit_order = await any_store.create_order_for_test(
        exit_candidate.id, "AAPL", OrderSide.SELL, 5, session_id=session.id
    )
    await any_store.claim_order_for_submission(exit_order.id)
    await any_store.transition_order(exit_order.id, OrderStatus.CANCELED)
    recovery = await any_store.create_submit_recovery(
        local_order_id=exit_order.id,
        broker_order_id=f"broker-{exit_order.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=5,
        failure_reason="broker overfill",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    await any_store.append_fill(
        exit_order.id,
        "AAPL",
        OrderSide.SELL,
        6,
        9.0,
        source_fill_id=f"{recovery.broker_order_id}:6",
        session_id=session.id,
    )
    assert "AAPL" in await any_store.list_quarantined_symbols()

    await any_store.reconcile_submit_recovery(
        _attestation(
            exit_candidate,
            exit_order,
            recovery,
            client_order_id=None,
            side=OrderSide.SELL,
            cumulative_filled_quantity=6,
        ),
        actor="operator-a",
    )
    assert "AAPL" in await any_store.list_quarantined_symbols()


async def test_facade_release_makes_zero_venue_calls(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    broker = MockBrokerAdapter()
    facade = StoreBackedCommandFacade(any_store, broker=broker)

    await facade.reconcile_submit_recovery(
        attestation=_attestation(candidate, order, recovery), actor="operator-a"
    )

    assert broker.submitted == []
    assert broker.canceled == []
    assert broker.replaced == []
    assert broker.status_queries == []


async def test_direct_sell_recovery_blocks_fresh_owner_until_release(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    held_candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    held = await any_store.create_order_for_test(
        held_candidate.id, "AAPL", OrderSide.BUY, 10, session_id=session.id
    )
    await any_store.append_fill(
        held.id,
        "AAPL",
        OrderSide.BUY,
        10,
        10.0,
        source_fill_id="wo0114-direct-held",
        session_id=session.id,
    )
    await any_store.transition_order(held.id, OrderStatus.CANCELED)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=10,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    order = await any_store.create_order_for_sell_intent(
        intent.id, order_type=OrderType.LIMIT, limit_price=9.9
    )
    claimed = await any_store.claim_order_for_submission(order.id)
    assert claimed.order is not None
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    recovery = await any_store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"broker-{order.id}",
        client_order_id=f"client-{order.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=10,
        limit_price=9.9,
        failure_reason="direct sell needs review",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )

    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=10,
            session_id=session.id,
        )

    await any_store.reconcile_submit_recovery(
        SubmitRecoveryAttestation(
            recovery_id=recovery.id,
            local_order_id=order.id,
            broker_order_id=recovery.broker_order_id,
            client_order_id=recovery.client_order_id,
            symbol="AAPL",
            side=OrderSide.SELL,
            candidate_id=None,
            sell_intent_id=intent.id,
            envelope_id=None,
            broker_terminal_state=OrderStatus.CANCELED,
            cumulative_filled_quantity=0,
            reason="paper venue terminal confirmed",
            evidence_ref="paper://direct/recovery",
        ),
        actor="operator-a",
    )

    fresh = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=10,
        session_id=session.id,
    )
    assert fresh.id != intent.id


async def test_release_of_last_predicate_lifts_flatten_quarantine(any_store):
    _, intent, envelope, order, recovery = await _envelope_needs_review(any_store)
    await any_store.transition_envelope(
        envelope.id,
        EnvelopeStatus.BREACHED,
        reason="test terminal mandate",
        now=_NOW + timedelta(seconds=1),
    )
    with pytest.raises(FlattenBlockedError, match="retained obligation"):
        await any_store.flatten_position("AAPL", actor="operator-a")

    await any_store.reconcile_submit_recovery(
        _envelope_attestation(intent, envelope, order, recovery),
        actor="operator-a",
    )

    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.order is not None


def _operator_http_payloads() -> tuple[dict, dict]:
    attestation = {
        "recovery_id": "r1",
        "local_order_id": "o1",
        "broker_order_id": "b1",
        "client_order_id": None,
        "symbol": "AAPL",
        "side": "buy",
        "candidate_id": "c1",
        "sell_intent_id": None,
        "envelope_id": None,
        "broker_terminal_state": "canceled",
        "cumulative_filled_quantity": 0,
        "reason": "operator checked venue truth",
        "evidence_ref": "paper://wo0114/http",
    }
    fill = {
        key: value
        for key, value in attestation.items()
        if key not in {"broker_terminal_state", "cumulative_filled_quantity"}
    }
    fill.update(
        fill_quantity=1,
        cumulative_filled_quantity=1,
        price=10.0,
    )
    return attestation, fill


async def test_operator_routes_reject_path_mismatch_and_map_facade_conflicts():
    """Both human-gated routes own identity binding and typed error mapping."""

    class RejectingFacade:
        async def ingest_submit_recovery_fill(self, *, command, actor):
            raise ConflictError(f"fill refused for {command.recovery_id} by {actor}")

        async def reconcile_submit_recovery(self, *, attestation, actor):
            raise ConflictError(
                f"release refused for {attestation.recovery_id} by {actor}"
            )

    app = create_app()
    app.dependency_overrides[get_command_facade] = lambda: RejectingFacade()
    attestation, fill = _operator_http_payloads()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for suffix, payload in (("fills", fill), ("reconcile", attestation)):
            mismatched = await client.post(
                f"/api/order-recoveries/wrong/{suffix}",
                json=payload,
                headers={"X-Actor": "operator-a"},
            )
            conflict = await client.post(
                f"/api/order-recoveries/r1/{suffix}",
                json=payload,
                headers={"X-Actor": "operator-a"},
            )
            assert mismatched.status_code == 422
            assert conflict.status_code == 409


async def _append_ambiguous_envelope_parent(store, order) -> None:
    action = next(
        event
        for event in await store.get_execution_events()
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
        and event.order_id == order.id
    )
    await store.append_execution_event(
        action.model_copy(
            deep=True,
            update={
                "id": f"ambiguous-parent-{order.id}",
                "sequence": 0,
                "dedupe_key": f"ambiguous-parent:{order.id}",
                "envelope_id": None,
            },
        )
    )


async def test_operator_view_classifies_none_single_and_ambiguous_envelope_lineage(
    store,
):
    _, _, _, direct_recovery = await _needs_review_order(store, symbol="MSFT")
    _, _, envelope, envelope_order, envelope_recovery = await _envelope_needs_review(
        store
    )
    facade = StoreBackedQueryFacade(store)

    initial = {
        view.record.id: view for view in (await facade.operator_orders()).recoveries
    }
    assert initial[direct_recovery.id].lineage_valid is True
    assert initial[direct_recovery.id].envelope_id is None
    assert initial[envelope_recovery.id].lineage_valid is True
    assert initial[envelope_recovery.id].envelope_id == envelope.id

    await _append_ambiguous_envelope_parent(store, envelope_order)
    ambiguous = {
        view.record.id: view for view in (await facade.operator_orders()).recoveries
    }
    assert ambiguous[envelope_recovery.id].lineage_valid is False
    assert (
        ambiguous[envelope_recovery.id].lineage_error == "envelope lineage is ambiguous"
    )


async def test_fill_facade_validates_all_evidence_text_before_delegating(store):
    _, candidate, order, recovery = await _needs_review_order(store)
    command = _fill_command(candidate, order, recovery)
    facade = StoreBackedCommandFacade(store)

    for actor, candidate_command, field in (
        (" ", command, "actor"),
        (
            "operator-a",
            command.model_copy(update={"reason": " "}),
            "reason",
        ),
        (
            "operator-a",
            command.model_copy(update={"evidence_ref": ""}),
            "evidence_ref",
        ),
    ):
        with pytest.raises(InvalidInputError, match=field):
            await facade.ingest_submit_recovery_fill(
                command=candidate_command,
                actor=actor,
            )

    result = await facade.ingest_submit_recovery_fill(
        command=command,
        actor="operator-a",
    )
    assert result.status == "appended"


async def test_core_identity_guards_reject_untrusted_or_drifted_scope(store):
    _, candidate, order, recovery = await _needs_review_order(store)
    identity = _attestation(candidate, order, recovery)
    expected = {
        "expected_candidate_id": candidate.id,
        "expected_sell_intent_id": None,
        "expected_envelope_id": None,
    }

    with pytest.raises(RecoveryTransitionError, match="lineage is not trustworthy"):
        validate_submit_recovery_identity(
            recovery,
            order,
            identity,
            lineage_error="candidate owner is missing",
            **expected,
        )
    with pytest.raises(RecoveryTransitionError, match="missing local order"):
        validate_submit_recovery_identity(
            recovery,
            None,
            identity,
            **expected,
        )
    with pytest.raises(RecoveryTransitionError, match="durable local order scope"):
        validate_submit_recovery_identity(
            recovery,
            order.model_copy(update={"symbol": "MSFT"}),
            identity,
            **expected,
        )


def _model_construct_with(model, **changes):
    values = model.model_dump()
    values.update(changes)
    return type(model).model_construct(**values)


async def test_core_attestation_and_fill_fact_guards_reject_invalid_values(store):
    _, candidate, order, recovery = await _needs_review_order(store)
    attestation = _attestation(candidate, order, recovery)
    fill = _fill_command(candidate, order, recovery)

    with pytest.raises(RecoveryTransitionError, match="non-negative whole number"):
        validate_recovery_attested_facts(
            _model_construct_with(attestation, cumulative_filled_quantity=True),
            recovery,
            canonical_filled_quantity=0,
        )
    with pytest.raises(RecoveryTransitionError, match="invalid human-attested fill"):
        validate_recovery_fill_facts(
            _model_construct_with(fill, fill_quantity=0),
            recovery,
            canonical_filled_quantity=0,
            exact_replay=False,
        )
    with pytest.raises(RecoveryTransitionError, match="positive whole number"):
        validate_recovery_fill_facts(
            _model_construct_with(fill, cumulative_filled_quantity=True),
            recovery,
            canonical_filled_quantity=0,
            exact_replay=False,
        )
    with pytest.raises(RecoveryTransitionError, match="cumulative parity failed"):
        validate_recovery_fill_facts(
            fill.model_copy(update={"cumulative_filled_quantity": 5}),
            recovery,
            canonical_filled_quantity=0,
            exact_replay=False,
        )


def _canonical_fill_event(recovery, *, dedupe_key: str, broker_order_id=None):
    payload = (
        {"broker_order_id": broker_order_id} if broker_order_id is not None else {}
    )
    return ExecutionEvent(
        event_type=ExecutionEventType.FILL,
        source=EventSource.BROKER_STREAM,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        dedupe_key=dedupe_key,
        symbol=recovery.symbol,
        side=recovery.side,
        quantity=1,
        price=10.0,
        order_id=recovery.local_order_id,
        session_id=recovery.session_id,
        payload=payload,
    )


async def test_canonical_fill_quantity_separates_explicit_legacy_and_unscoped_legs(
    store,
):
    _, _, order, recovery = await _needs_review_order(store)
    prefix = f"fill:{order.id}:"

    explicit_other = _canonical_fill_event(
        recovery,
        dedupe_key=f"{prefix}explicit-other",
        broker_order_id="other-leg",
    )
    assert (
        canonical_recovery_fill_quantity(
            [explicit_other],
            recovery,
            known_broker_order_ids=[recovery.broker_order_id, "other-leg"],
        )
        == 0
    )

    legacy_other = _canonical_fill_event(
        recovery,
        dedupe_key=f"{prefix}other-leg:1",
    )
    assert (
        canonical_recovery_fill_quantity(
            [legacy_other],
            recovery,
            known_broker_order_ids=[recovery.broker_order_id, "other-leg"],
        )
        == 0
    )

    unscoped = _canonical_fill_event(
        recovery,
        dedupe_key=f"{prefix}legacy-unscoped",
    )
    assert (
        canonical_recovery_fill_quantity(
            [unscoped],
            recovery,
            known_broker_order_ids=[recovery.broker_order_id],
        )
        == 1
    )


async def _corrupt_recovery_lineage(
    store,
    corruption: str,
    *,
    candidate_id: str | None,
    order_id: str,
    sell_intent_id: str | None,
    envelope_id: str | None,
) -> None:
    if corruption == "ambiguous_parent":
        order = await store.get_order(order_id)
        assert order is not None
        await _append_ambiguous_envelope_parent(store, order)
        return

    if isinstance(store, InMemoryStateStore):
        async with store._lock:
            if corruption == "missing_order":
                store._orders.pop(order_id)
            elif corruption == "missing_candidate":
                assert candidate_id is not None
                store._candidates.pop(candidate_id)
            elif corruption == "missing_sell_intent":
                assert sell_intent_id is not None
                store._sell_intents.pop(sell_intent_id)
            elif corruption == "missing_envelope":
                assert envelope_id is not None
                store._envelopes.pop(envelope_id)
            elif corruption == "projection_mismatch":
                assert envelope_id is not None
                store._envelopes[envelope_id] = store._envelopes[
                    envelope_id
                ].model_copy(update={"symbol": "MSFT"})
            else:  # pragma: no cover - parameter list is closed below.
                raise AssertionError(corruption)
        return

    assert isinstance(store, SqliteStateStore)
    async with store._lock:
        with store._tx() as cur:
            if corruption == "missing_order":
                cur.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            elif corruption == "missing_candidate":
                assert candidate_id is not None
                cur.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
            elif corruption == "missing_sell_intent":
                assert sell_intent_id is not None
                cur.execute("DELETE FROM sell_intents WHERE id = ?", (sell_intent_id,))
            elif corruption == "missing_envelope":
                assert envelope_id is not None
                cur.execute(
                    "DELETE FROM execution_envelopes WHERE id = ?", (envelope_id,)
                )
            elif corruption == "projection_mismatch":
                assert envelope_id is not None
                cur.execute(
                    "UPDATE execution_envelopes SET symbol = ? WHERE id = ?",
                    ("MSFT", envelope_id),
                )
            else:  # pragma: no cover - parameter list is closed below.
                raise AssertionError(corruption)


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_order",
        "missing_candidate",
        "missing_sell_intent",
        "ambiguous_parent",
        "missing_envelope",
        "projection_mismatch",
    ],
)
async def test_corrupt_recovery_lineage_fails_closed_without_truth_writes(
    any_store,
    corruption,
):
    if corruption in {"missing_order", "missing_candidate"}:
        _, candidate, order, recovery = await _needs_review_order(any_store)
        attestation = _attestation(candidate, order, recovery)
        candidate_id = candidate.id
        sell_intent_id = None
        envelope_id = None
    else:
        _, intent, envelope, order, recovery = await _envelope_needs_review(any_store)
        attestation = _envelope_attestation(intent, envelope, order, recovery)
        candidate_id = None
        sell_intent_id = intent.id
        envelope_id = envelope.id

    await _corrupt_recovery_lineage(
        any_store,
        corruption,
        candidate_id=candidate_id,
        order_id=order.id,
        sell_intent_id=sell_intent_id,
        envelope_id=envelope_id,
    )
    before = await _truth_counts(any_store)

    with pytest.raises(RecoveryTransitionError, match="lineage is not trustworthy"):
        await any_store.reconcile_submit_recovery(
            attestation,
            actor="operator-a",
        )

    assert await _truth_counts(any_store) == before


async def _recovery_without_claim(store):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        session_id=session.id,
    )
    recovery = await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"broker-{order.id}",
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        failure_reason="coverage guard: no durable claim",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    return candidate, order, recovery


@pytest.mark.parametrize(
    "guard",
    [
        "known_order_broker_leg",
        "unknown_recovery",
        "missing_claim",
        "new_fill_after_release",
        "sell_below_zero",
        "release_from_non_review_state",
    ],
)
async def test_recovery_command_state_guards_are_dual_store_and_write_free(
    any_store,
    guard,
):
    if guard == "missing_claim":
        candidate, order, recovery = await _recovery_without_claim(any_store)
        command = _fill_command(candidate, order, recovery)
        before = await _truth_counts(any_store)
        with pytest.raises(RecoveryTransitionError, match="claim occurrence"):
            await any_store.ingest_submit_recovery_fill(command, actor="operator-a")
        assert await _truth_counts(any_store) == before
        return

    if guard == "sell_below_zero":
        _, candidate, order, recovery = await _needs_review_order(
            any_store,
            side=OrderSide.SELL,
        )
        before = await _truth_counts(any_store)
        with pytest.raises(RecoveryTransitionError, match="negative position"):
            await any_store.ingest_submit_recovery_fill(
                _fill_command(candidate, order, recovery),
                actor="operator-a",
            )
        assert await _truth_counts(any_store) == before
        return

    if guard == "release_from_non_review_state":
        _, candidate, order, recovery = await _needs_review_order(
            any_store,
            cleanup_status=RECOVERY_RESOLVED,
        )
        before = await _truth_counts(any_store)
        with pytest.raises(RecoveryTransitionError, match="requires needs_review"):
            await any_store.reconcile_submit_recovery(
                _attestation(candidate, order, recovery),
                actor="operator-a",
            )
        assert await _truth_counts(any_store) == before
        return

    _, candidate, order, recovery = await _needs_review_order(
        any_store,
        order_broker_order_id=(
            "order-owned-broker-leg" if guard == "known_order_broker_leg" else None
        ),
    )
    command = _fill_command(candidate, order, recovery)

    if guard == "known_order_broker_leg":
        other_leg = await any_store.append_fill(
            order.id,
            recovery.symbol,
            recovery.side,
            1,
            10.0,
            source_fill_id="order-owned-broker-leg:1",
            session_id=recovery.session_id,
        )
        assert other_leg.status == "appended"
        result = await any_store.ingest_submit_recovery_fill(
            command,
            actor="operator-a",
        )
        assert result.status == "appended"
        assert len(await any_store.list_fills()) == 2
        assert (await any_store.get_position(recovery.symbol)).quantity == 5
        return

    if guard == "unknown_recovery":
        before = await _truth_counts(any_store)
        with pytest.raises(UnknownEntityError, match="not found"):
            await any_store.ingest_submit_recovery_fill(
                command.model_copy(update={"recovery_id": "missing-recovery"}),
                actor="operator-a",
            )
        assert await _truth_counts(any_store) == before
        return

    assert guard == "new_fill_after_release"
    await any_store.reconcile_submit_recovery(
        _attestation(candidate, order, recovery),
        actor="operator-a",
    )
    before = await _truth_counts(any_store)
    with pytest.raises(RecoveryTransitionError, match="new fill ingestion"):
        await any_store.ingest_submit_recovery_fill(command, actor="operator-a")
    assert await _truth_counts(any_store) == before


def _later_recovery_fill(
    command: SubmitRecoveryFillCommand,
) -> SubmitRecoveryFillCommand:
    return command.model_copy(
        update={
            "fill_quantity": 2,
            "cumulative_filled_quantity": 6,
            "price": 10.5,
            "evidence_ref": "paper://fills/evidence-0114-later",
        }
    )


async def _corrupt_recovery_fill_symbol(store, *, order_id: str, source_fill_id: str):
    if isinstance(store, InMemoryStateStore):
        async with store._lock:
            index, fill = next(
                (index, fill)
                for index, fill in enumerate(store._fills)
                if fill.order_id == order_id and fill.source_fill_id == source_fill_id
            )
            store._fills[index] = fill.model_copy(update={"symbol": "MSFT"})
        return

    assert isinstance(store, SqliteStateStore)
    async with store._lock:
        with store._tx() as cur:
            cur.execute(
                "UPDATE fills SET symbol = ? WHERE order_id = ? AND source_fill_id = ?",
                ("MSFT", order_id, source_fill_id),
            )


async def _assert_older_fill_retry_is_idempotent(store) -> None:
    _, candidate, order, recovery = await _needs_review_order(store)
    first = _fill_command(candidate, order, recovery)
    later = _later_recovery_fill(first)
    assert (
        await store.ingest_submit_recovery_fill(first, actor="operator-a")
    ).status == "appended"
    assert (
        await store.ingest_submit_recovery_fill(later, actor="operator-a")
    ).status == "appended"
    before = (
        await _truth_counts(store),
        (await store.get_position(order.symbol)).model_dump(mode="json"),
    )

    replay = await store.ingest_submit_recovery_fill(first, actor="operator-a")

    assert replay.status == "duplicate"
    assert (
        await _truth_counts(store),
        (await store.get_position(order.symbol)).model_dump(mode="json"),
    ) == before
    conflicting = first.model_copy(
        update={
            "evidence_ref": "paper://fills/conflicting-replay",
        }
    )
    with pytest.raises(RecoveryTransitionError, match="conflicting"):
        await store.ingest_submit_recovery_fill(conflicting, actor="operator-a")
    assert (
        await _truth_counts(store),
        (await store.get_position(order.symbol)).model_dump(mode="json"),
    ) == before


async def test_older_fill_exact_retry_remains_write_free_after_later_fill(any_store):
    await _assert_older_fill_retry_is_idempotent(any_store)


async def test_exact_replay_rejects_corrupt_fill_read_model(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store)
    command = _fill_command(candidate, order, recovery)
    assert (
        await any_store.ingest_submit_recovery_fill(command, actor="operator-a")
    ).status == "appended"
    source_fill_id = f"{recovery.broker_order_id}:{command.cumulative_filled_quantity}"
    await _corrupt_recovery_fill_symbol(
        any_store,
        order_id=order.id,
        source_fill_id=source_fill_id,
    )
    before = (
        await _truth_counts(any_store),
        [fill.model_dump(mode="json") for fill in await any_store.list_fills()],
        (await any_store.get_position(order.symbol)).model_dump(mode="json"),
    )

    with pytest.raises(RecoveryTransitionError, match="conflicting fill-row replay"):
        await any_store.ingest_submit_recovery_fill(command, actor="operator-a")

    assert (
        await _truth_counts(any_store),
        [fill.model_dump(mode="json") for fill in await any_store.list_fills()],
        (await any_store.get_position(order.symbol)).model_dump(mode="json"),
    ) == before


async def test_older_fill_exact_retry_remains_write_free_after_sqlite_reopen(tmp_path):
    db_path = tmp_path / "wo0114-older-fill-retry.db"
    first_store = SqliteStateStore(db_path)
    _, candidate, order, recovery = await _needs_review_order(first_store)
    first = _fill_command(candidate, order, recovery)
    later = _later_recovery_fill(first)
    await first_store.ingest_submit_recovery_fill(first, actor="operator-a")
    await first_store.ingest_submit_recovery_fill(later, actor="operator-a")
    await first_store.close()

    reopened = SqliteStateStore(db_path)
    await reopened.initialize()
    before = (
        await _truth_counts(reopened),
        (await reopened.get_position(order.symbol)).model_dump(mode="json"),
    )
    replay = await reopened.ingest_submit_recovery_fill(first, actor="operator-a")
    assert replay.status == "duplicate"
    assert (
        await _truth_counts(reopened),
        (await reopened.get_position(order.symbol)).model_dump(mode="json"),
    ) == before
    with pytest.raises(RecoveryTransitionError, match="conflicting"):
        await reopened.ingest_submit_recovery_fill(
            first.model_copy(
                update={"evidence_ref": "paper://fills/conflicting-replay"}
            ),
            actor="operator-a",
        )
    assert (
        await _truth_counts(reopened),
        (await reopened.get_position(order.symbol)).model_dump(mode="json"),
    ) == before
    await reopened.close()
