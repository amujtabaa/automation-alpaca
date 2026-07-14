"""WO-0032 — per-symbol single-ACTIVE mandate (REV-0023 Phase-A2 P0 / INV-087).

The single-ACTIVE guard is scoped per SYMBOL, not per sell_intent_id: a second
envelope for a symbol that already has a live ACTIVE mandate is refused
(activation and resume), while legitimate supersession within a symbol and
concurrent mandates on DIFFERENT symbols still work. Both stores.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    SessionType,
)
from app.store.base import EnvelopeTransitionError

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
    """Two different intents, same symbol: the second activation is refused
    (this is the P0 mechanism, checked directly — no session boundary needed)."""

    await any_store.initialize()
    await any_store.approve_envelope_activation(
        make_draft("intent-A", symbol="AAPL"), actor="op"
    )
    with pytest.raises(EnvelopeTransitionError, match="per-symbol single-ACTIVE"):
        await any_store.approve_envelope_activation(
            make_draft("intent-B", symbol="AAPL"), actor="op"
        )
    active = await _active_envelopes(any_store)
    assert len(active) == 1 and active[0].sell_intent_id == "intent-A"


async def test_different_symbols_can_both_be_active(any_store):
    """The guard is per SYMBOL, not global: AAPL and MSFT mandates coexist."""

    await any_store.initialize()
    await any_store.approve_envelope_activation(
        make_draft("intent-A", symbol="AAPL"), actor="op"
    )
    await any_store.approve_envelope_activation(
        make_draft("intent-B", symbol="MSFT"), actor="op"
    )
    active = {e.symbol for e in await _active_envelopes(any_store)}
    assert active == {"AAPL", "MSFT"}


async def test_supersession_within_symbol_still_permitted(any_store):
    """Supersession replaces the mandate for a symbol in one atomic unit — the
    per-symbol guard excludes the outgoing envelope, so it is NOT self-blocked."""

    await any_store.initialize()
    old = await any_store.approve_envelope_activation(
        make_draft("intent-A", symbol="AAPL"), actor="op"
    )
    successor = make_draft("intent-A", symbol="AAPL", qty_ceiling=90)
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
        make_draft("intent-A", symbol="AAPL"), actor="op"
    )
    await any_store.transition_envelope(env.id, S.FROZEN, actor="op")
    resumed = await any_store.transition_envelope(env.id, S.ACTIVE, actor="op")
    assert resumed.status is S.ACTIVE
    assert len(await _active_envelopes(any_store)) == 1
