"""WO-0016 — envelope state machine (ADR-010 §3, incl. the 2026-07-11
pre-activation escape-edge amendment), enforced identically by BOTH stores.

The full legal/illegal transition matrix is derived from ``ENVELOPE_TRANSITIONS``
itself and cross-checked here against a hand-written copy of the ADR edges, so
a drift in either direction (table vs spec) fails loudly rather than silently
retuning the machine.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    SellReason,
    SessionType,
    utcnow,
)
from app.store.core import EnvelopeTransitionError
from app.transitions import ENVELOPE_TIMESTAMP, ENVELOPE_TRANSITIONS

pytestmark = pytest.mark.anyio

S = EnvelopeStatus

# The ADR-010 §3 edges, hand-written from the spec text (amended 2026-07-11:
# pre-activation escape edges). If ENVELOPE_TRANSITIONS drifts from the ADR,
# THIS is the test that must be consciously edited together with the ADR.
ADR_EDGES: dict[EnvelopeStatus, set[EnvelopeStatus]] = {
    S.PENDING: {S.APPROVED, S.CANCELLED, S.EXPIRED},
    S.APPROVED: {S.ACTIVE, S.CANCELLED, S.EXPIRED},
    S.ACTIVE: {
        S.COMPLETED,
        S.EXPIRED,
        S.EXHAUSTED,
        S.BREACHED,
        S.SUPERSEDED,
        S.FROZEN,
    },
    # WO-0029A (ADR-010 §2/§3 amendment accepted 2026-07-12): overfill
    # while FROZEN breaches — the edge exists so a violated mandate can
    # never resume into COMPLETED.
    S.FROZEN: {S.ACTIVE, S.CANCELLED, S.BREACHED},
    S.COMPLETED: set(),
    S.EXPIRED: set(),
    S.EXHAUSTED: set(),
    S.BREACHED: set(),
    S.SUPERSEDED: set(),
    S.CANCELLED: set(),
}


def test_transition_table_matches_the_adr_exactly():
    assert ENVELOPE_TRANSITIONS == ADR_EDGES


def test_every_status_has_a_row_and_terminals_are_terminal():
    assert set(ENVELOPE_TRANSITIONS) == set(EnvelopeStatus)
    for terminal in (
        S.COMPLETED,
        S.EXPIRED,
        S.EXHAUSTED,
        S.BREACHED,
        S.SUPERSEDED,
        S.CANCELLED,
    ):
        assert ENVELOPE_TRANSITIONS[terminal] == set()


def test_timestamp_map_covers_every_entered_status():
    entered = {to for targets in ENVELOPE_TRANSITIONS.values() for to in targets}
    assert set(ENVELOPE_TIMESTAMP) == entered


def make_draft(intent_id: str = "si-1", symbol: str = "AAPL") -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=100,
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


async def create_owned_draft(store, *, symbol: str = "AAPL"):
    session = await store.get_current_session()
    owner = await store.create_sell_intent(
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    draft = make_draft(owner.id, symbol).model_copy(update={"session_id": session.id})
    return owner, draft


# Paths that drive an envelope from PENDING into each source status using only
# legal edges (so the matrix test can start anywhere).
PATH_TO: dict[EnvelopeStatus, list[EnvelopeStatus]] = {
    S.PENDING: [],
    S.APPROVED: [S.APPROVED],
    S.ACTIVE: [S.APPROVED, S.ACTIVE],
    S.FROZEN: [S.APPROVED, S.ACTIVE, S.FROZEN],
    # ACTIVE -> COMPLETED is fill-driven, not a generic status command.
    S.COMPLETED: [S.APPROVED, S.ACTIVE],
    S.EXPIRED: [S.EXPIRED],
    S.EXHAUSTED: [S.APPROVED, S.ACTIVE, S.EXHAUSTED],
    S.BREACHED: [S.APPROVED, S.ACTIVE, S.BREACHED],
    # ACTIVE -> SUPERSEDED is a legal state-machine edge but is reachable only
    # through the atomic supersede operation, never generic transition_envelope.
    S.SUPERSEDED: [S.APPROVED, S.ACTIVE],
    S.CANCELLED: [S.CANCELLED],
}


@pytest.mark.parametrize("source", list(EnvelopeStatus))
@pytest.mark.parametrize("target", list(EnvelopeStatus))
async def test_full_transition_matrix_both_stores(any_store, source, target):
    """Every (source, target) pair: legal edges apply (status + timestamp),
    illegal edges raise EnvelopeTransitionError and mutate nothing, and a
    same-status re-request is an idempotent no-op."""

    await any_store.initialize()
    _, draft = await create_owned_draft(any_store)
    env = await any_store.create_envelope(draft)
    for step in PATH_TO[source]:
        env = await any_store.transition_envelope(env.id, step)
    if source is S.COMPLETED:
        await any_store.record_envelope_fill(
            env.id,
            quantity=env.remaining_quantity or 0,
            dedupe_key=f"matrix-complete:{env.id}",
            price=10.0,
        )
        env = await any_store.get_envelope(env.id)
        assert env is not None
    elif source is S.SUPERSEDED:
        old_id = env.id
        successor = make_draft(env.sell_intent_id).model_copy(
            update={"session_id": env.session_id}
        )
        await any_store.supersede_envelope(old_id, successor, actor="operator-a")
        env = await any_store.get_envelope(old_id)
        assert env is not None
    assert env.status is source

    if target is source:
        again = await any_store.transition_envelope(env.id, target)
        assert again.status is source
        return

    if target in (S.COMPLETED, S.SUPERSEDED):
        # These are causal edges with dedicated atomic writers: fill-driven
        # completion and predecessor+successor supersession. The generic seam
        # must never fabricate either terminal state.
        with pytest.raises(EnvelopeTransitionError):
            await any_store.transition_envelope(env.id, target)
        unchanged = await any_store.get_envelope(env.id)
        assert unchanged is not None and unchanged.status is source
    elif target in ENVELOPE_TRANSITIONS[source]:
        moved = await any_store.transition_envelope(env.id, target)
        assert moved.status is target
        ts_field = ENVELOPE_TIMESTAMP[target]
        assert getattr(moved, ts_field) is not None
        assert moved.updated_at >= env.updated_at
    else:
        with pytest.raises(EnvelopeTransitionError):
            await any_store.transition_envelope(env.id, target)
        unchanged = await any_store.get_envelope(env.id)
        assert unchanged is not None and unchanged.status is source


async def test_resume_reenters_active_and_restamps_activation(any_store):
    await any_store.initialize()
    _, draft = await create_owned_draft(any_store)
    env = await any_store.create_envelope(draft)
    await any_store.transition_envelope(env.id, S.APPROVED)
    active = await any_store.transition_envelope(env.id, S.ACTIVE)
    frozen = await any_store.transition_envelope(env.id, S.FROZEN)
    assert frozen.frozen_at is not None
    resumed = await any_store.transition_envelope(env.id, S.ACTIVE)
    assert resumed.status is S.ACTIVE
    # activated_at reflects the MOST RECENT activation (documented semantics).
    assert resumed.activated_at is not None
    assert resumed.activated_at >= active.activated_at


async def test_unknown_envelope_raises(any_store):
    from app.store.base import UnknownEntityError

    await any_store.initialize()
    with pytest.raises(UnknownEntityError):
        await any_store.transition_envelope("nope", S.APPROVED)


async def test_transitions_emit_the_envelope_event_family(any_store):
    """Lifecycle walk PENDING→APPROVED→ACTIVE→FROZEN→ACTIVE→FROZEN→CANCELLED
    leaves a replayable ExecutionEvent trail (ADR-010 §6)."""

    await any_store.initialize()
    owner, draft = await create_owned_draft(any_store)
    env = await any_store.create_envelope(draft)
    for step in (S.APPROVED, S.ACTIVE, S.FROZEN, S.ACTIVE, S.FROZEN, S.CANCELLED):
        await any_store.transition_envelope(env.id, step)

    events = await any_store.get_execution_events()
    mine = [e for e in events if e.envelope_id == env.id]
    kinds = [e.event_type for e in mine]
    assert kinds == [
        ExecutionEventType.ENVELOPE_CREATED,
        ExecutionEventType.ENVELOPE_APPROVED,
        ExecutionEventType.ENVELOPE_ACTIVATED,
        ExecutionEventType.ENVELOPE_FROZEN,
        ExecutionEventType.ENVELOPE_RESUMED,
        ExecutionEventType.ENVELOPE_FROZEN,
        ExecutionEventType.ENVELOPE_CANCELLED,
    ]
    # Every event correlates the owning intent (D-020 sell-side correlation).
    assert all(e.correlation_id == owner.id for e in mine)
    assert all(e.symbol == "AAPL" for e in mine)
