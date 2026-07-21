"""WO-0114 — PD-1 human-attested ``needs_review`` release valve.

Red-first contract for the ratified D-PD1-1..4 decisions.  The release command
is deliberately tested at the store boundary first: identity/parity checks and
the status/audit/execution-event writes must share the store's serialization
boundary.  HTTP and cockpit tests then pin the thin typed boundary separately.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx
import pytest

from app.api.deps import get_command_facade
from app.facade.errors import ConflictError, InvalidInputError
from app.facade.store_backed import StoreBackedCommandFacade
from app.main import create_app
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    RECOVERY_OPERATOR_RECONCILED,
    RECOVERY_STATUSES,
    RECOVERY_TRANSITIONS,
    EventAuthority,
    EventSource,
    EventType,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SubmitRecoveryAttestation,
    SubmitRecoveryFillCommand,
)
from app.store.base import RecoveryTransitionError
from app.store.core import recovery_status_event
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
    before_position = (await any_store.get_position(order.symbol)).model_dump(mode="json")

    released = await any_store.reconcile_submit_recovery(
        attestation, actor="operator-a"
    )

    assert released.cleanup_status == RECOVERY_OPERATOR_RECONCILED
    after_position = (await any_store.get_position(order.symbol)).model_dump(mode="json")
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
        if event.event_type
        is ExecutionEventType.SUBMIT_RECOVERY_OPERATOR_RECONCILED
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
        await any_store.reconcile_submit_recovery(
            conflicting, actor="operator-a"
        )
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

    with pytest.raises(RecoveryTransitionError):
        await any_store.reconcile_submit_recovery(command, actor="operator-a")

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


@pytest.mark.parametrize(
    ("field", "bad"), [("reason", "   "), ("evidence_ref", "")]
)
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
    repeated = await any_store.ingest_submit_recovery_fill(
        command, actor="operator-a"
    )

    assert first.status == "appended"
    assert repeated.status == "duplicate"
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

    before_release = (await any_store.get_position(order.symbol)).model_dump(mode="json")
    attestation = _attestation(
        candidate,
        order,
        recovery,
        cumulative_filled_quantity=command.cumulative_filled_quantity,
    )
    await any_store.reconcile_submit_recovery(attestation, actor="operator-a")
    assert (await any_store.get_position(order.symbol)).model_dump(mode="json") == before_release


async def test_operator_fill_over_order_capacity_is_rejected(any_store):
    _, candidate, order, recovery = await _needs_review_order(any_store, quantity=5)
    before_position = (await any_store.get_position(order.symbol)).model_dump(mode="json")
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
    assert (await any_store.get_position(order.symbol)).model_dump(mode="json") == before_position
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


async def test_sqlite_reopen_preserves_fill_and_release_idempotency(tmp_path):
    path = tmp_path / "wo0114.db"
    first_store = SqliteStateStore(path)
    _, candidate, order, recovery = await _needs_review_order(first_store)
    fill_command = _fill_command(candidate, order, recovery)
    attestation = _attestation(
        candidate, order, recovery, cumulative_filled_quantity=4
    )
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
            return {"id": attestation.recovery_id, "cleanup_status": "operator_reconciled"}

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

