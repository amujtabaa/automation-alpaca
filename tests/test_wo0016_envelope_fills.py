"""WO-0016 — remaining-quantity semantics: ONLY deduped fill events decrement
(ADR-010 §2 scope rail), in BOTH stores.

The structural claim under test: ``record_envelope_fill`` is the sole writer
of ``remaining_quantity``; submission/ack-shaped operations (envelope
transitions, event appends of SUBMITTED/ACCEPTED kinds) cannot move it; a
replayed fill (same dedupe_key) is counted exactly once (INV-5).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEvent,
    ExecutionEventType,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    SessionType,
    utcnow,
)
from app.store.base import InvalidFillError, UnknownEntityError
from app.transitions import ENVELOPE_TRANSITIONS
from tests.store_helpers import backing_intent_id

pytestmark = pytest.mark.anyio

S = EnvelopeStatus


def make_draft(intent_id: str = "si-1", qty: int = 100) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=qty,
        floor_price=9.50,
        trail_distance_min=0.05,
        trail_distance_max=0.25,
        participation_rate_cap=0.20,
        aggressiveness=["passive"],
        cooldown_floor_ms=750,
        cancel_replace_budget=40,
        expires_at=utcnow() + timedelta(hours=2),
        allowed_session_phases=[SessionType.PRE_MARKET],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )


async def activate(store, env: ExecutionEnvelope) -> ExecutionEnvelope:
    await store.transition_envelope(env.id, S.APPROVED)
    return await store.transition_envelope(env.id, S.ACTIVE)


async def test_fill_decrements_and_full_fill_completes(any_store):
    await any_store.initialize()
    # WO-0036 R2: activation validates the backing intent — a real one is
    # required wherever the envelope enters ACTIVE.
    intent_id = await backing_intent_id(any_store)
    env = await any_store.create_envelope(make_draft(intent_id))
    await activate(any_store, env)

    after = await any_store.record_envelope_fill(
        env.id, quantity=40, dedupe_key="fill:o1:x1", price=9.80, order_id="o1"
    )
    assert after.remaining_quantity == 60
    assert after.status is S.ACTIVE

    done = await any_store.record_envelope_fill(
        env.id, quantity=60, dedupe_key="fill:o1:x2", price=9.75, order_id="o1"
    )
    assert done.remaining_quantity == 0
    assert done.status is S.COMPLETED
    assert done.completed_at is not None

    events = await any_store.get_execution_events()
    mine = [e for e in events if e.envelope_id == env.id]
    kinds = [e.event_type for e in mine]
    assert kinds.count(ExecutionEventType.FILL) == 2
    assert kinds[-1] is ExecutionEventType.ENVELOPE_COMPLETED


async def test_duplicate_fill_is_counted_exactly_once(any_store):
    await any_store.initialize()
    intent_id = await backing_intent_id(any_store)
    env = await any_store.create_envelope(make_draft(intent_id))
    await activate(any_store, env)

    await any_store.record_envelope_fill(
        env.id, quantity=30, dedupe_key="fill:o1:dup", order_id="o1", price=9.9
    )
    again = await any_store.record_envelope_fill(
        env.id, quantity=30, dedupe_key="fill:o1:dup", order_id="o1", price=9.9
    )
    assert again.remaining_quantity == 70  # NOT 40 — replay is a no-op

    events = await any_store.get_execution_events()
    fills = [
        e
        for e in events
        if e.envelope_id == env.id and e.event_type is ExecutionEventType.FILL
    ]
    assert len(fills) == 1


async def test_overfill_of_the_hard_ceiling_breaches(any_store):
    """A broker-authoritative fill EXCEEDING remaining is recorded faithfully
    (never hidden), remaining floors at 0, and the envelope goes BREACHED —
    terminal-pending-human (ADR-001 posture, ADR-010 hard rail)."""

    await any_store.initialize()
    intent_id = await backing_intent_id(any_store, qty=50)
    env = await any_store.create_envelope(make_draft(intent_id, qty=50))
    await activate(any_store, env)

    after = await any_store.record_envelope_fill(
        env.id, quantity=80, dedupe_key="fill:o1:over", order_id="o1", price=9.9
    )
    assert after.remaining_quantity == 0
    assert after.status is S.BREACHED
    assert after.breached_at is not None
    # Terminal-pending-human: no outgoing edges, resumption is a NEW envelope.
    assert ENVELOPE_TRANSITIONS[S.BREACHED] == set()

    events = await any_store.get_execution_events()
    mine = [e for e in events if e.envelope_id == env.id]
    fill_ev = next(e for e in mine if e.event_type is ExecutionEventType.FILL)
    assert fill_ev.payload["overfill"] is True
    assert fill_ev.payload["overfill_quantity"] == 30
    assert mine[-1].event_type is ExecutionEventType.ENVELOPE_BREACHED


async def test_fill_while_frozen_decrements_but_never_unfreezes(any_store):
    await any_store.initialize()
    intent_id = await backing_intent_id(any_store)
    env = await any_store.create_envelope(make_draft(intent_id))
    await activate(any_store, env)
    await any_store.transition_envelope(env.id, S.FROZEN)

    after = await any_store.record_envelope_fill(
        env.id, quantity=100, dedupe_key="fill:o1:frozen", order_id="o1", price=9.9
    )
    assert after.remaining_quantity == 0
    assert after.status is S.FROZEN  # a fill NEVER exits a freeze

    # ... completion happens on RESUME, atomically.
    resumed = await any_store.transition_envelope(env.id, S.ACTIVE)
    assert resumed.status is S.COMPLETED
    events = await any_store.get_execution_events()
    kinds = [e.event_type for e in events if e.envelope_id == env.id]
    assert kinds[-2:] == [
        ExecutionEventType.ENVELOPE_RESUMED,
        ExecutionEventType.ENVELOPE_COMPLETED,
    ]


async def test_late_fill_on_terminal_envelope_is_recorded_not_hidden(any_store):
    await any_store.initialize()
    intent_id = await backing_intent_id(any_store)
    env = await any_store.create_envelope(make_draft(intent_id))
    await activate(any_store, env)
    await any_store.transition_envelope(env.id, S.FROZEN)
    await any_store.transition_envelope(env.id, S.CANCELLED)

    after = await any_store.record_envelope_fill(
        env.id, quantity=10, dedupe_key="fill:o1:late", order_id="o1", price=9.9
    )
    assert after.status is S.CANCELLED  # terminal never changes
    assert after.remaining_quantity == 90
    events = await any_store.get_execution_events()
    fill_ev = next(
        e
        for e in events
        if e.envelope_id == env.id and e.event_type is ExecutionEventType.FILL
    )
    assert fill_ev.payload["late_fill"] is True


async def test_fill_before_activation_is_structurally_impossible(any_store):
    await any_store.initialize()
    env = await any_store.create_envelope(make_draft())
    with pytest.raises(InvalidFillError):
        await any_store.record_envelope_fill(
            env.id, quantity=10, dedupe_key="fill:o1:early", price=9.9
        )
    await any_store.transition_envelope(env.id, S.APPROVED)
    with pytest.raises(InvalidFillError):
        await any_store.record_envelope_fill(
            env.id, quantity=10, dedupe_key="fill:o1:early2", price=9.9
        )
    unchanged = await any_store.get_envelope(env.id)
    assert unchanged.remaining_quantity == 100


@pytest.mark.parametrize("qty", [0, -5])
async def test_nonpositive_fill_quantity_rejected(any_store, qty):
    await any_store.initialize()
    intent_id = await backing_intent_id(any_store)
    env = await any_store.create_envelope(make_draft(intent_id))
    await activate(any_store, env)
    with pytest.raises(InvalidFillError):
        await any_store.record_envelope_fill(
            env.id, quantity=qty, dedupe_key="fill:o1:bad", price=9.9
        )


async def test_unknown_envelope_fill_raises(any_store):
    await any_store.initialize()
    with pytest.raises(UnknownEntityError):
        await any_store.record_envelope_fill(
            "nope", quantity=1, dedupe_key="fill:o1:none", price=9.9
        )


async def test_transitions_and_raw_event_appends_cannot_move_remaining(any_store):
    """Submitted/ack-shaped facts structurally cannot change quantity: walk a
    freeze/resume cycle AND append raw SUBMITTED/ACCEPTED events naming the
    envelope — remaining_quantity must not move (invariant 8/9 analogue)."""

    await any_store.initialize()
    intent_id = await backing_intent_id(any_store)
    env = await any_store.create_envelope(make_draft(intent_id))
    await activate(any_store, env)
    await any_store.transition_envelope(env.id, S.FROZEN)
    await any_store.transition_envelope(env.id, S.ACTIVE)
    for event_type in (ExecutionEventType.SUBMITTED, ExecutionEventType.ACCEPTED):
        await any_store.append_execution_event(
            ExecutionEvent(
                event_type=event_type,
                source=EventSource.BROKER_REST,
                authority=EventAuthority.BROKER_AUTHORITATIVE,
                symbol="AAPL",
                envelope_id=env.id,
                quantity=100,
            )
        )
    after = await any_store.get_envelope(env.id)
    assert after.remaining_quantity == 100
    assert after.status is S.ACTIVE
