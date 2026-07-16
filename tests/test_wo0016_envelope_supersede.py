"""WO-0016 — amendment-by-supersession atomicity (ADR-010 §3), BOTH stores.

The invariant: bounds never mutate in place; a change is a NEW envelope that
atomically replaces the old one — no observable window with two ACTIVE
envelopes for one intent, and CONCURRENT supersede attempts yield exactly one
ACTIVE successor (single-flight, mirroring the W2-CAND shape).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    SessionType,
    utcnow,
)
from app.store.base import InvalidOrderError, UnknownEntityError
from app.store.core import EnvelopeTransitionError

pytestmark = pytest.mark.anyio

S = EnvelopeStatus


def make_draft(
    intent_id: str = "si-1", symbol: str = "AAPL", floor: float = 9.50
) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=100,
        floor_price=floor,
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


async def make_active(store, **kwargs) -> ExecutionEnvelope:
    env = await store.create_envelope(make_draft(**kwargs))
    await store.transition_envelope(env.id, S.APPROVED)
    return await store.transition_envelope(env.id, S.ACTIVE)


async def test_supersede_swaps_active_atomically_and_links_both(any_store):
    await any_store.initialize()
    old = await make_active(any_store)
    successor = make_draft(floor=9.75)  # the amendment: a tighter floor

    new = await any_store.supersede_envelope(
        old.id, successor, actor="operator-ameen", reason="tighten floor"
    )

    assert new.status is S.ACTIVE
    assert new.supersedes_id == old.id
    old_after = await any_store.get_envelope(old.id)
    assert old_after.status is S.SUPERSEDED
    assert old_after.superseded_by_id == new.id

    # Exactly one ACTIVE envelope for the intent — before, during, after.
    active = await any_store.list_envelopes(sell_intent_id="si-1", status=S.ACTIVE)
    assert [e.id for e in active] == [new.id]

    # Replayable trail: created(B), approved(B), superseded(A), activated(B).
    events = await any_store.get_execution_events()
    tail = [
        e.event_type
        for e in events
        if e.envelope_id in (old.id, new.id)
        and e.event_type
        in (
            ExecutionEventType.ENVELOPE_CREATED,
            ExecutionEventType.ENVELOPE_APPROVED,
            ExecutionEventType.ENVELOPE_SUPERSEDED,
            ExecutionEventType.ENVELOPE_ACTIVATED,
        )
    ][-4:]
    assert tail == [
        ExecutionEventType.ENVELOPE_CREATED,
        ExecutionEventType.ENVELOPE_APPROVED,
        ExecutionEventType.ENVELOPE_SUPERSEDED,
        ExecutionEventType.ENVELOPE_ACTIVATED,
    ]
    superseded_ev = next(
        e for e in events if e.event_type is ExecutionEventType.ENVELOPE_SUPERSEDED
    )
    assert superseded_ev.payload["superseded_by_id"] == new.id
    assert superseded_ev.payload["actor"] == "operator-ameen"


async def test_concurrent_supersedes_yield_exactly_one_active_successor(any_store):
    """The W2-CAND single-flight shape: N concurrent amendments of the same
    ACTIVE envelope — exactly one wins; every loser raises; exactly one
    envelope is ACTIVE afterwards."""

    await any_store.initialize()
    old = await make_active(any_store)
    drafts = [make_draft(floor=9.50 + i / 100) for i in range(1, 6)]

    results = await asyncio.gather(
        *(any_store.supersede_envelope(old.id, d) for d in drafts),
        return_exceptions=True,
    )
    winners = [r for r in results if isinstance(r, ExecutionEnvelope)]
    losers = [r for r in results if isinstance(r, EnvelopeTransitionError)]
    assert len(winners) == 1
    assert len(losers) == len(drafts) - 1

    active = await any_store.list_envelopes(sell_intent_id="si-1", status=S.ACTIVE)
    assert [e.id for e in active] == [winners[0].id]
    old_after = await any_store.get_envelope(old.id)
    assert old_after.status is S.SUPERSEDED
    assert old_after.superseded_by_id == winners[0].id


async def test_supersede_rejects_non_active_old(any_store):
    await any_store.initialize()
    env = await any_store.create_envelope(make_draft())  # PENDING
    with pytest.raises(EnvelopeTransitionError):
        await any_store.supersede_envelope(env.id, make_draft(floor=9.60))
    await any_store.transition_envelope(env.id, S.APPROVED)
    with pytest.raises(EnvelopeTransitionError):
        await any_store.supersede_envelope(env.id, make_draft(floor=9.60))
    # Nothing was written: the failed successor drafts do not exist.
    assert len(await any_store.list_envelopes(sell_intent_id="si-1")) == 1


async def test_supersede_rejects_cross_intent_and_cross_symbol_successors(any_store):
    await any_store.initialize()
    old = await make_active(any_store)
    with pytest.raises(InvalidOrderError):
        await any_store.supersede_envelope(old.id, make_draft(intent_id="si-OTHER"))
    with pytest.raises(InvalidOrderError):
        await any_store.supersede_envelope(old.id, make_draft(symbol="MSFT"))
    assert (await any_store.get_envelope(old.id)).status is S.ACTIVE


async def test_supersede_rejects_non_pending_or_prelinked_drafts(any_store):
    await any_store.initialize()
    old = await make_active(any_store)
    tampered = make_draft().model_copy(update={"status": S.APPROVED})
    with pytest.raises(InvalidOrderError):
        await any_store.supersede_envelope(old.id, tampered)
    with pytest.raises(UnknownEntityError):
        await any_store.supersede_envelope("nope", make_draft())


async def test_fresh_draft_cannot_predeclare_supersedes_id(any_store):
    """Codex PR#8 F2: ``envelope_draft_reason`` rejected a fresh draft that
    pre-declared ``superseded_by_id`` but NOT one that pre-declared
    ``supersedes_id`` — so a client could POST a draft with a foreign
    ``supersedes_id`` and have it go ACTIVE as an ORDINARY envelope, bypassing
    the atomic supersede op (which validates the predecessor is ACTIVE + same
    intent/symbol, conserves ``successor.qty_ceiling <= old.remaining``, and
    marks the predecessor SUPERSEDED). Both link fields are now rejected on a
    fresh draft; amendments must route through ``supersede_envelope``."""

    await any_store.initialize()
    prelinked = make_draft().model_copy(update={"supersedes_id": "env-ghost"})
    with pytest.raises(InvalidOrderError):
        await any_store.create_envelope(prelinked)
    with pytest.raises(InvalidOrderError):
        await any_store.approve_envelope_activation(prelinked, actor="op")


async def test_second_activation_for_same_intent_is_blocked(any_store):
    """Single-ACTIVE-per-intent holds outside supersession too: a second
    envelope activated directly (not via supersede) is refused while the
    first is ACTIVE — and becomes activatable once it no longer is."""

    await any_store.initialize()
    first = await make_active(any_store)
    second = await any_store.create_envelope(make_draft(floor=9.60))
    await any_store.transition_envelope(second.id, S.APPROVED)
    with pytest.raises(EnvelopeTransitionError):
        await any_store.transition_envelope(second.id, S.ACTIVE)

    await any_store.transition_envelope(first.id, S.FROZEN)
    await any_store.transition_envelope(first.id, S.CANCELLED)
    activated = await any_store.transition_envelope(second.id, S.ACTIVE)
    assert activated.status is S.ACTIVE
