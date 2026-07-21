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
from app.facade.store_backed import StoreBackedCommandFacade
from app.main import create_app
from app.broker.mock import MockBrokerAdapter
from app.monitoring import _recover_unpersisted_submits
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    RECOVERY_OPERATOR_RECONCILED,
    RECOVERY_STATUSES,
    RECOVERY_TRANSITIONS,
    EventAuthority,
    EventSource,
    EventType,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
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
from app.store.core import recovery_status_event
from app.sellside.types import ActionKind, PlannedAction
from app.store.core import EnvelopeActionPausedError
from app.store.sqlite import SqliteStateStore


pytestmark = pytest.mark.anyio


async def _needs_review_order(store, *, quantity: int = 10, symbol: str = "AAPL"):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )
    claimed = await store.claim_order_for_submission(order.id)
    assert claimed.order is not None
    await store.transition_order(order.id, OrderStatus.CANCELED)
    recovery = await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"broker-{order.id}",
        client_order_id=f"client-{order.id}",
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=quantity,
        failure_reason="WO-0114 red fixture",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
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
