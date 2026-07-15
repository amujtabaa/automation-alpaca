"""WO-0032 — per-symbol single-ACTIVE mandate (REV-0023 Phase-A2 P0 / INV-087).

The single-mandate guard is scoped per SYMBOL, not per sell_intent_id: a second
envelope for a symbol that already has a live mandate is refused (activation
and resume), while legitimate supersession within a symbol and concurrent
mandates on DIFFERENT symbols still work. Both stores.

WO-0036 R2 reframing: the intent lifecycle is now structurally linked to the
envelope's, so the ORIGINAL double-mandate recipe (a session boundary expires
the intent while its envelope stays ACTIVE; a fresh day-2 intent then activates
a second envelope) can no longer even reach this guard — single-flight intent
dedup blocks the second same-symbol intent while the first is alive, and the
close SPARES a live-envelope-backed intent. INV-087 stays the defense-in-depth
backstop and is exercised here directly via a second draft for the SAME intent
(the one shape that still reaches the clash check). FROZEN now counts as live
(a kill-frozen mandate's child may still rest at the venue — WO-0036 R2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    SellIntentStatus,
    SessionType,
)
from app.store.base import EnvelopeTransitionError
from tests.store_helpers import backing_intent_id

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def make_draft(intent_id: str, symbol: str = "AAPL", **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=100,
        floor_price=9.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.20,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=T_NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


async def _active_envelopes(store) -> list[ExecutionEnvelope]:
    return [
        e for e in await store.list_envelopes() if e.status is EnvelopeStatus.ACTIVE
    ]


async def test_second_active_envelope_same_symbol_is_refused(any_store):
    """A second draft for the symbol's live mandate is refused (the P0
    mechanism, checked directly). Same intent id on purpose: with the R2 link,
    intent-layer single-flight already blocks a second same-symbol INTENT, so
    a second draft for the SAME intent is the shape that reaches this rail."""

    await any_store.initialize()
    intent_id = await backing_intent_id(any_store, symbol="AAPL")
    await any_store.approve_envelope_activation(
        make_draft(intent_id, symbol="AAPL"), actor="op"
    )
    with pytest.raises(EnvelopeTransitionError, match="per-symbol"):
        await any_store.approve_envelope_activation(
            make_draft(intent_id, symbol="AAPL"), actor="op"
        )
    active = await _active_envelopes(any_store)
    assert len(active) == 1 and active[0].sell_intent_id == intent_id


async def test_second_same_symbol_intent_is_structurally_deduped(any_store):
    """The R2 link's primary defense one layer down: while a live envelope
    backs the symbol's intent, single-flight dedup returns THAT intent instead
    of minting a second one — the double-mandate recipe never gets two intents
    to work with."""

    await any_store.initialize()
    intent_id = await backing_intent_id(any_store, symbol="AAPL")
    await any_store.approve_envelope_activation(
        make_draft(intent_id, symbol="AAPL"), actor="op"
    )
    assert await backing_intent_id(any_store, symbol="AAPL") == intent_id


async def test_different_symbols_can_both_be_active(any_store):
    """The guard is per SYMBOL, not global: AAPL and MSFT mandates coexist."""

    await any_store.initialize()
    await any_store.approve_envelope_activation(
        make_draft(await backing_intent_id(any_store, "AAPL"), symbol="AAPL"),
        actor="op",
    )
    await any_store.approve_envelope_activation(
        make_draft(await backing_intent_id(any_store, "MSFT"), symbol="MSFT"),
        actor="op",
    )
    active = {e.symbol for e in await _active_envelopes(any_store)}
    assert active == {"AAPL", "MSFT"}


async def test_supersession_within_symbol_still_permitted(any_store):
    """Supersession replaces the mandate for a symbol in one atomic unit — the
    per-symbol guard excludes the outgoing envelope, so it is NOT self-blocked."""

    await any_store.initialize()
    intent_id = await backing_intent_id(any_store, "AAPL")
    old = await any_store.approve_envelope_activation(
        make_draft(intent_id, symbol="AAPL"), actor="op"
    )
    successor = make_draft(intent_id, symbol="AAPL", qty_ceiling=90)
    new_env = await any_store.supersede_envelope(
        old.id, successor, actor="op", reason="amendment"
    )
    assert (await any_store.get_envelope(new_env.id)).status is S.ACTIVE
    assert (await any_store.get_envelope(old.id)).status is not S.ACTIVE
    active = await _active_envelopes(any_store)
    assert len(active) == 1 and active[0].id == new_env.id


async def test_resume_from_frozen_not_blocked_by_self(any_store):
    """Resuming a FROZEN envelope (transition -> ACTIVE) must not be blocked by
    the per-symbol guard seeing ITSELF — it excludes the resuming envelope."""

    await any_store.initialize()
    env = await any_store.approve_envelope_activation(
        make_draft(await backing_intent_id(any_store, "AAPL"), symbol="AAPL"),
        actor="op",
    )
    await any_store.transition_envelope(env.id, S.FROZEN, actor="op")
    resumed = await any_store.transition_envelope(env.id, S.ACTIVE, actor="op")
    assert resumed.status is S.ACTIVE
    assert len(await _active_envelopes(any_store)) == 1


async def test_session_boundary_cannot_mint_a_second_mandate(any_store):
    """The ORIGINAL WO-0032 scenario, extended per WO-0036 R2's done-when: a
    session close no longer expires the live mandate's intent (spared), so the
    day-boundary recipe for a duplicate mandate is closed one layer BEFORE the
    envelope clash — and the clash still refuses a second draft afterwards."""

    from app.models import SellReason

    await any_store.initialize()
    session = await any_store.get_current_session()
    # Bind the intent to the closing session so the close actually considers
    # it (an unbound intent would dodge the boundary instead of proving it).
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    intent_id = intent.id
    env = await any_store.approve_envelope_activation(
        make_draft(intent_id, symbol="AAPL"), actor="op"
    )

    await any_store.close_session(session.id, actor="op")

    # The intent survived the boundary (post-close state, WO-0036 R2)...
    spared = await any_store.get_sell_intent(intent_id)
    assert spared is not None and spared.status is SellIntentStatus.APPROVED
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE
    # ...and the envelope clash still refuses a second mandate for the symbol.
    with pytest.raises(EnvelopeTransitionError, match="per-symbol"):
        await any_store.approve_envelope_activation(
            make_draft(intent_id, symbol="AAPL"), actor="op"
        )
