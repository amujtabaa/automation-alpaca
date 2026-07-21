"""WO-0125: envelope lifecycle replay and dual-store read-model parity."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.events.projectors import (
    ENVELOPE_EVENT_TYPES,
    ProjectionError,
    project_envelopes,
)
from app.events.replay import (
    ReadModelProjection,
    compare_read_models,
    project_read_models,
    verify_dual_store_readmodel_parity,
)
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore
from app.transitions import ENVELOPE_TRANSITIONS

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _created_payload() -> dict[str, object]:
    return {
        "actor": "operator-a",
        "sell_intent_id": "intent-1",
        "qty_ceiling": 100,
        "floor_price": 9.5,
        "trail_distance_min": 0.05,
        "trail_distance_max": 0.25,
        "participation_rate_cap": 0.2,
        "aggressiveness": ["passive", "mid"],
        "cooldown_floor_ms": 750,
        "cancel_replace_budget": 40,
        "max_outstanding_children": 1,
        "expires_at": (NOW + timedelta(hours=2)).isoformat(),
        "allowed_session_phases": ["regular"],
        "expiry_disposition": "rest_at_floor",
        "stale_data_disposition": "leave_resting",
        "supersedes_id": None,
    }


def _event(
    event_type: ExecutionEventType,
    sequence: int,
    *,
    payload: dict[str, object] | None = None,
    quantity: int | None = None,
    envelope_id: str | None = "env-1",
) -> ExecutionEvent:
    return ExecutionEvent(
        sequence=sequence,
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL" if envelope_id is not None else None,
        side=OrderSide.SELL if envelope_id is not None else None,
        quantity=quantity,
        envelope_id=envelope_id,
        session_id="session-1" if envelope_id is not None else None,
        correlation_id="intent-1" if envelope_id is not None else None,
        payload=payload or {},
    )


def _transition(
    event_type: ExecutionEventType,
    sequence: int,
    before: EnvelopeStatus,
    after: EnvelopeStatus,
    **extra: object,
) -> ExecutionEvent:
    return _event(
        event_type,
        sequence,
        payload={"from": before.value, "to": after.value, "actor": "engine", **extra},
    )


def _active_prefix() -> list[ExecutionEvent]:
    return [
        _event(ExecutionEventType.ENVELOPE_CREATED, 1, payload=_created_payload()),
        _transition(
            ExecutionEventType.ENVELOPE_APPROVED,
            2,
            EnvelopeStatus.PENDING,
            EnvelopeStatus.APPROVED,
        ),
        _transition(
            ExecutionEventType.ENVELOPE_ACTIVATED,
            3,
            EnvelopeStatus.APPROVED,
            EnvelopeStatus.ACTIVE,
        ),
    ]


_TRANSITION_EVENT_BY_TARGET = {
    EnvelopeStatus.APPROVED: ExecutionEventType.ENVELOPE_APPROVED,
    EnvelopeStatus.ACTIVE: ExecutionEventType.ENVELOPE_ACTIVATED,
    EnvelopeStatus.FROZEN: ExecutionEventType.ENVELOPE_FROZEN,
    EnvelopeStatus.COMPLETED: ExecutionEventType.ENVELOPE_COMPLETED,
    EnvelopeStatus.EXPIRED: ExecutionEventType.ENVELOPE_EXPIRED,
    EnvelopeStatus.EXHAUSTED: ExecutionEventType.ENVELOPE_EXHAUSTED,
    EnvelopeStatus.BREACHED: ExecutionEventType.ENVELOPE_BREACHED,
    EnvelopeStatus.SUPERSEDED: ExecutionEventType.ENVELOPE_SUPERSEDED,
    EnvelopeStatus.CANCELLED: ExecutionEventType.ENVELOPE_CANCELLED,
}


def _transition_event_type(
    before: EnvelopeStatus, after: EnvelopeStatus
) -> ExecutionEventType:
    if before is EnvelopeStatus.FROZEN and after is EnvelopeStatus.ACTIVE:
        return ExecutionEventType.ENVELOPE_RESUMED
    return _TRANSITION_EVENT_BY_TARGET[after]


def _transition_extra(after: EnvelopeStatus) -> dict[str, object]:
    return {"superseded_by_id": "env-2"} if after is EnvelopeStatus.SUPERSEDED else {}


def _prefix_to_status(status: EnvelopeStatus) -> list[ExecutionEvent]:
    created = _event(ExecutionEventType.ENVELOPE_CREATED, 1, payload=_created_payload())
    if status is EnvelopeStatus.PENDING:
        return [created]
    if status is EnvelopeStatus.APPROVED:
        return [
            created,
            _transition(
                ExecutionEventType.ENVELOPE_APPROVED,
                2,
                EnvelopeStatus.PENDING,
                EnvelopeStatus.APPROVED,
            ),
        ]
    active = _active_prefix()
    if status is EnvelopeStatus.ACTIVE:
        return active
    if status is EnvelopeStatus.FROZEN:
        return [
            *active,
            _transition(
                ExecutionEventType.ENVELOPE_FROZEN,
                4,
                EnvelopeStatus.ACTIVE,
                EnvelopeStatus.FROZEN,
            ),
        ]
    if status is EnvelopeStatus.CANCELLED:
        return [
            created,
            _transition(
                ExecutionEventType.ENVELOPE_CANCELLED,
                2,
                EnvelopeStatus.PENDING,
                EnvelopeStatus.CANCELLED,
            ),
        ]
    return [
        *active,
        _transition(
            _transition_event_type(EnvelopeStatus.ACTIVE, status),
            4,
            EnvelopeStatus.ACTIVE,
            status,
            **_transition_extra(status),
        ),
    ]


_LEGAL_TRANSITION_CASES = tuple(
    (before, after)
    for before in EnvelopeStatus
    for after in _TRANSITION_EVENT_BY_TARGET
    if after in ENVELOPE_TRANSITIONS[before]
)
_ILLEGAL_TRANSITION_CASES = tuple(
    (before, after)
    for before in EnvelopeStatus
    for after in _TRANSITION_EVENT_BY_TARGET
    if after not in ENVELOPE_TRANSITIONS[before]
)


def _transition_case_id(case: tuple[EnvelopeStatus, EnvelopeStatus]) -> str:
    before, after = case
    return f"{before.value}-to-{after.value}"


def test_envelope_vocabulary_is_explicitly_classified() -> None:
    current = frozenset(
        event_type
        for event_type in ExecutionEventType
        if event_type.value.startswith("envelope_")
    )
    assert ENVELOPE_EVENT_TYPES == current


def test_replay_folds_actions_fills_attribution_freeze_and_resume() -> None:
    events = [
        *_active_prefix(),
        _event(ExecutionEventType.ENVELOPE_ACTION, 4, payload={"action": "submit"}),
        _event(
            ExecutionEventType.FILL,
            5,
            quantity=20,
            payload={"remaining_before": 100, "remaining_after": 80},
        ),
        _event(
            ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            6,
            quantity=5,
            payload={"remaining_before": 80, "remaining_after": 75},
        ),
        _transition(
            ExecutionEventType.ENVELOPE_FROZEN,
            7,
            EnvelopeStatus.ACTIVE,
            EnvelopeStatus.FROZEN,
        ),
        _event(
            ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE,
            8,
            payload={"rail": "reduce_only"},
        ),
        _transition(
            ExecutionEventType.ENVELOPE_RESUMED,
            9,
            EnvelopeStatus.FROZEN,
            EnvelopeStatus.ACTIVE,
        ),
    ]

    projection = project_envelopes(events)["env-1"]

    assert projection.status is EnvelopeStatus.ACTIVE
    assert projection.remaining_quantity == 75
    assert projection.qty_ceiling == 100
    assert projection.up_to_sequence == 9
    assert projection.folded_event_types == tuple(event.event_type for event in events)
    assert dict(projection.bound_snapshot)["aggressiveness"] == ("passive", "mid")


@pytest.mark.parametrize(
    ("event_type", "before", "terminal"),
    [
        (
            ExecutionEventType.ENVELOPE_COMPLETED,
            EnvelopeStatus.ACTIVE,
            EnvelopeStatus.COMPLETED,
        ),
        (
            ExecutionEventType.ENVELOPE_BREACHED,
            EnvelopeStatus.ACTIVE,
            EnvelopeStatus.BREACHED,
        ),
        (
            ExecutionEventType.ENVELOPE_EXHAUSTED,
            EnvelopeStatus.ACTIVE,
            EnvelopeStatus.EXHAUSTED,
        ),
        (
            ExecutionEventType.ENVELOPE_EXPIRED,
            EnvelopeStatus.ACTIVE,
            EnvelopeStatus.EXPIRED,
        ),
        (
            ExecutionEventType.ENVELOPE_SUPERSEDED,
            EnvelopeStatus.ACTIVE,
            EnvelopeStatus.SUPERSEDED,
        ),
        (
            ExecutionEventType.ENVELOPE_CANCELLED,
            EnvelopeStatus.FROZEN,
            EnvelopeStatus.CANCELLED,
        ),
    ],
)
def test_terminal_lifecycle_event_folds_status(
    event_type: ExecutionEventType,
    before: EnvelopeStatus,
    terminal: EnvelopeStatus,
) -> None:
    prefix = _prefix_to_status(before)
    extra = _transition_extra(terminal)
    events = [
        *prefix,
        _transition(event_type, len(prefix) + 1, before, terminal, **extra),
    ]
    projection = project_envelopes(events)["env-1"]
    assert projection.status is terminal
    assert projection.superseded_by_id == extra.get("superseded_by_id")


def test_transition_event_vocabulary_covers_every_representable_target() -> None:
    assert set(_TRANSITION_EVENT_BY_TARGET) == set(EnvelopeStatus) - {
        EnvelopeStatus.PENDING
    }
    assert set(_LEGAL_TRANSITION_CASES) | set(_ILLEGAL_TRANSITION_CASES) == {
        (before, after)
        for before in EnvelopeStatus
        for after in _TRANSITION_EVENT_BY_TARGET
    }


@pytest.mark.parametrize(
    ("before", "after"),
    _LEGAL_TRANSITION_CASES,
    ids=tuple(_transition_case_id(case) for case in _LEGAL_TRANSITION_CASES),
)
def test_replay_accepts_every_fsm_legal_envelope_transition(
    before: EnvelopeStatus,
    after: EnvelopeStatus,
) -> None:
    prefix = _prefix_to_status(before)
    event = _transition(
        _transition_event_type(before, after),
        len(prefix) + 1,
        before,
        after,
        **_transition_extra(after),
    )

    projection = project_envelopes([*prefix, event])["env-1"]

    assert projection.status is after


@pytest.mark.parametrize(
    ("before", "after"),
    _ILLEGAL_TRANSITION_CASES,
    ids=tuple(_transition_case_id(case) for case in _ILLEGAL_TRANSITION_CASES),
)
def test_replay_rejects_every_fsm_illegal_envelope_transition(
    before: EnvelopeStatus,
    after: EnvelopeStatus,
) -> None:
    prefix = _prefix_to_status(before)
    event = _transition(
        _transition_event_type(before, after),
        len(prefix) + 1,
        before,
        after,
        **_transition_extra(after),
    )

    with pytest.raises(ProjectionError, match="illegal envelope transition"):
        project_envelopes([*prefix, event])


def test_repair_checkpoint_is_classified_global_metadata() -> None:
    checkpoint = _event(
        ExecutionEventType.ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT,
        1,
        envelope_id=None,
        payload={"last_sequence": 42},
    )
    assert project_envelopes([checkpoint]) == {}


def test_replay_rejects_a_broken_remaining_quantity_chain() -> None:
    events = [
        *_active_prefix(),
        _event(
            ExecutionEventType.FILL,
            4,
            quantity=20,
            payload={"remaining_before": 99, "remaining_after": 79},
        ),
    ]
    with pytest.raises(ProjectionError, match="remaining_before"):
        project_envelopes(events)


async def _active_envelope(store) -> ExecutionEnvelope:
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
        source_fill_id=f"wo0125-hold:{candidate.id}",
        session_id=session.id,
        filled_at=NOW,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    owner = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    draft = ExecutionEnvelope(
        sell_intent_id=owner.id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.5,
        trail_distance_min=0.05,
        trail_distance_max=0.25,
        participation_rate_cap=0.2,
        aggressiveness=["passive", "mid"],
        cooldown_floor_ms=750,
        cancel_replace_budget=40,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[
            SessionType.PRE_MARKET,
            SessionType.REGULAR,
            SessionType.AFTER_HOURS,
        ],
        expiry_disposition=EnvelopeExpiryDisposition.REST_AT_FLOOR,
        stale_data_disposition=EnvelopeStaleDataDisposition.LEAVE_RESTING,
        session_id=session.id,
    )
    created = await store.create_envelope(draft, actor="operator-a")
    await store.transition_envelope(
        created.id, EnvelopeStatus.APPROVED, actor="operator-a", now=NOW
    )
    return await store.transition_envelope(
        created.id, EnvelopeStatus.ACTIVE, actor="operator-a", now=NOW
    )


async def test_projection_matches_each_store_read_model(any_store) -> None:
    envelope = await _active_envelope(any_store)
    staged = await any_store.stage_envelope_action(
        envelope.id,
        PlannedAction(
            kind=ActionKind.SUBMIT,
            limit_price=9.9,
            quantity=100,
            regime=None,
            urgency=0.0,
            working_stop=9.5,
            atr=0.05,
            tranche=False,
            stop_triggered=False,
        ),
        snapshot_fingerprint="wo0125-replay",
        now=NOW,
    )
    assert staged.order is not None, [
        (event.event_type, event.payload)
        for event in await any_store.get_execution_events()
        if event.envelope_id == envelope.id
    ]
    await any_store.record_envelope_fill(
        envelope.id,
        quantity=25,
        dedupe_key=f"fill:{staged.order.id}:wo0125",
        price=9.9,
        order_id=staged.order.id,
        now=NOW,
    )
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.FROZEN, reason="wo0125", now=NOW
    )
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.ACTIVE, reason="wo0125", now=NOW
    )

    events = await any_store.get_execution_events()
    projection = project_envelopes(events)[envelope.id]
    persisted = await any_store.get_envelope(envelope.id)
    replay = project_read_models(events)

    assert projection == replay.envelopes[envelope.id]
    assert projection.status is persisted.status is EnvelopeStatus.ACTIVE
    assert projection.remaining_quantity == persisted.remaining_quantity == 75
    assert projection.qty_ceiling == persisted.qty_ceiling
    assert projection.sell_intent_id == persisted.sell_intent_id
    assert projection.session_id == persisted.session_id
    bounds = dict(projection.bound_snapshot)
    assert bounds["cancel_replace_budget"] == persisted.cancel_replace_budget
    assert bounds["expires_at"] == persisted.expires_at.isoformat()


async def test_dual_store_verifier_detects_envelope_stream_divergence(tmp_path) -> None:
    memory = InMemoryStateStore()
    envelope = await _active_envelope(memory)
    sqlite = SqliteStateStore(tmp_path / "wo0125-parity.db")
    await sqlite.initialize()
    for event in await memory.get_execution_events():
        await sqlite.append_execution_event(event)
    try:
        equal = await verify_dual_store_readmodel_parity(memory, sqlite)
        assert equal.ok, equal.detail

        await sqlite.append_execution_event(
            ExecutionEvent(
                event_type=ExecutionEventType.ENVELOPE_ACTION,
                source=EventSource.ENGINE,
                authority=EventAuthority.LOCAL,
                symbol=envelope.symbol,
                side=OrderSide.SELL,
                envelope_id=envelope.id,
                session_id=envelope.session_id,
                correlation_id=envelope.sell_intent_id,
                payload={"action": "refused_stale", "mutation": "sqlite-only"},
            )
        )

        drifted = await verify_dual_store_readmodel_parity(memory, sqlite)
        assert not drifted.ok
        assert "envelope" in drifted.detail
    finally:
        sqlite._conn.close()
        sqlite._conn = None


def test_read_model_comparator_detects_envelope_divergence() -> None:
    envelope = project_envelopes(_active_prefix())["env-1"]
    base = ReadModelProjection(
        quarantined_symbols=frozenset(),
        timeout_quarantined_order_ids=frozenset(),
        envelopes={"env-1": envelope},
    )
    drifted = replace(
        base,
        envelopes={"env-1": replace(envelope, remaining_quantity=99)},
    )

    result = compare_read_models("memory", base, "sqlite", drifted)

    assert not result.ok
    assert "envelope" in result.detail
