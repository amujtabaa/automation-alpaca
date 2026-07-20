"""REV-0023 Phase-A2 internal-review pins (the assembled W3 remediation+WO-0030
delta, f092ca7..HEAD).

House pattern: a review pin starts as a strict xfail documenting the defect,
then is FLIPPED to a hard assertion when the fix lands.

The one CONFIRMED **P0** (completeness-0) was first contained by WO-0032's
per-symbol single-ACTIVE guard (INV-087). R2 closes the class at its root: a
live Envelope delegation retains its APPROVED SellIntent across session close,
so single-flight returns the same coherent owner and a second activation is
still refused.
The other nine Phase-A2 findings are recorded in
``work/review/REV-0023/phase-a2.md``; the non-gated ones were addressed by
WO-0033 and the event-log ones by WO-0034.

------------------------------------------------------------------------------
P0 — completeness-0: the single-ACTIVE-mandate invariant was scoped per
``sell_intent_id``, not per ``symbol``, and ``close_session`` orphaned an
ACTIVE Envelope by expiring its backing intent. R2's regression below pins
both the root lifecycle link and the independent per-symbol backstop.

REACHABILITY (verified by the implementer seat, recorded honestly): the defect
requires the backing intent to be APPROVED (not ORDERED) AND carry the closing
session's ``session_id``. The two *automatic* production intent creators
(``open_protection_exit``, ``flatten_position``) dispatch a legacy order and
leave the intent ORDERED, which ``close_session`` does NOT expire — so this is
NOT an active oversell in today's shipped wiring. It is a store-contract-level
single-mandate violation that becomes live the moment the envelope-native exit
flow (create sell_intent -> approve an envelope for it, no legacy order
dispatch) is wired. Treat as a MUST-FIX-BEFORE-WIRING / pre-T5-merge item.

The pin asserts the full invariant after the boundary: the live mandate keeps
its APPROVED owner, single-flight cannot mint a replacement owner, and at most
one ACTIVE Envelope exists for the symbol.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    OrderSide,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.store.base import EnvelopeTransitionError

pytestmark = pytest.mark.anyio

T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def _draft(intent_id: str, **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol="AAPL",
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


async def _seed_position(store, quantity: int = 100):
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, quantity, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, quantity, 10.0, session_id=session.id
    )


async def test_PIN_P0_no_two_active_envelopes_per_symbol_across_session_boundary(
    any_store,
):
    # FLIPPED GREEN by WO-0032 (per-symbol single-ACTIVE guard). The scenario
    # that used to yield two ACTIVE envelopes for one symbol now REFUSES the
    # second activation while the first is still ACTIVE.
    await any_store.initialize()
    await _seed_position(any_store, 100)

    # An APPROVED-not-ORDERED, session-stamped intent backs the first envelope.
    session1 = await any_store.get_current_session()
    si1 = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session1.id,
    )
    env1 = await any_store.approve_envelope_activation(
        _draft(
            si1.id,
            qty_ceiling=si1.target_quantity,
            session_id=si1.session_id,
        ),
        actor="operator-a",
    )

    # Ordinary end-of-day close must retain the owner of a live delegation.
    await any_store.close_session()
    owner = await any_store.get_sell_intent(si1.id)
    assert owner is not None
    assert owner.status is SellIntentStatus.APPROVED
    active_owner = await any_store.active_sell_intent_for("AAPL")
    assert active_owner is not None and active_owner.id == si1.id
    assert (await any_store.get_envelope(env1.id)).status is EnvelopeStatus.ACTIVE

    # Next session, same still-held symbol: single-flight sees the retained owner
    # and returns it instead of minting a replacement SellIntent.
    session2 = await any_store.get_current_session()
    si2 = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session2.id,
    )
    assert si2.id == si1.id
    assert si2.session_id == session1.id
    assert len(await any_store.list_sell_intents(symbol="AAPL")) == 1

    # The per-symbol single-ACTIVE guard remains an independent backstop even if
    # a caller attempts a second Envelope for the same coherent owner.
    with pytest.raises(EnvelopeTransitionError):
        await any_store.approve_envelope_activation(
            _draft(
                si2.id,
                qty_ceiling=si2.target_quantity,
                session_id=si2.session_id,
            ),
            actor="operator-a",
        )

    active = [
        e
        for e in await any_store.list_envelopes(symbol="AAPL")
        if e.status is EnvelopeStatus.ACTIVE
    ]
    # At most one live mandate per symbol; no owner or Envelope was orphaned.
    assert len(active) == 1, (
        f"expected exactly one ACTIVE envelope for AAPL, got {[e.id for e in active]}"
    )
