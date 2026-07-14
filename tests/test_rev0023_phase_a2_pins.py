"""REV-0023 Phase-A2 internal-review pins (the assembled W3 remediation+WO-0030
delta, f092ca7..HEAD).

House pattern: each pin is a strict xfail that flips loudly (xpass -> strict
failure) when the fix lands, so the gate tells us to promote it to a hard
assertion. Fix NOTHING here — this is review output.

Currently pinned: the one CONFIRMED **P0** (completeness-0). The other nine
Phase-A2 findings are recorded in ``work/review/REV-0023/phase-a2.md``; their
pins are queued for the remediation work order (several are human-gated or
planning-seat decision-gaps and must not be pinned directionally yet).

------------------------------------------------------------------------------
P0 — completeness-0: the single-ACTIVE-mandate invariant is scoped per
``sell_intent_id``, not per ``symbol``, and ``close_session`` orphans an
ACTIVE envelope by EXPIRing its backing intent. Reproduced (below) on BOTH
stores: an APPROVED, session-stamped SellIntent backs an ACTIVE envelope; the
session closes (the intent -> EXPIRED, the envelope stays ACTIVE with full
remaining); next session a fresh ``create_sell_intent`` for the same symbol is
no longer deduped (the old intent is EXPIRED), so a SECOND envelope activates
for the same symbol/position -> two ACTIVE mandates, each independently able to
stage a full-size SELL (each reduce-only check reads the still-100% position and
cannot see the sibling's in-flight order).

REACHABILITY (verified by the implementer seat, recorded honestly): the defect
requires the backing intent to be APPROVED (not ORDERED) AND carry the closing
session's ``session_id``. The two *automatic* production intent creators
(``open_protection_exit``, ``flatten_position``) dispatch a legacy order and
leave the intent ORDERED, which ``close_session`` does NOT expire — so this is
NOT an active oversell in today's shipped wiring. It is a store-contract-level
single-mandate violation that becomes live the moment the envelope-native exit
flow (create sell_intent -> approve an envelope for it, no legacy order
dispatch) is wired. Treat as a MUST-FIX-BEFORE-WIRING / pre-T5-merge item.

Fix direction is human-gated (order-intent + session-close semantics): options
include per-symbol single-ACTIVE exclusivity at activation, and/or freezing (not
orphaning) an envelope-backed intent's envelope at session close. This pin
asserts the invariant that ANY chosen fix must satisfy: at most one ACTIVE
envelope per symbol after the boundary.
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
    SellReason,
    SessionType,
)

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


@pytest.mark.xfail(
    strict=True,
    reason="REV-0023 P0 completeness-0: single-ACTIVE mandate is per-intent, "
    "not per-symbol; close_session orphans an ACTIVE envelope whose intent it "
    "expires, so two ACTIVE envelopes for one symbol are reachable across a "
    "session boundary. Fix is human-gated; pin flips when the per-symbol "
    "invariant is enforced.",
)
async def test_PIN_P0_no_two_active_envelopes_per_symbol_across_session_boundary(
    any_store,
):
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
    await any_store.approve_envelope_activation(_draft(si1.id), actor="operator-a")

    # Ordinary end-of-day close: expires si1, leaves the envelope ACTIVE.
    await any_store.close_session()

    # Next session, same still-held symbol: dedup is blind (si1 is EXPIRED), so a
    # fresh intent + a SECOND envelope activate for the same symbol/position.
    session2 = await any_store.get_current_session()
    si2 = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session2.id,
    )
    await any_store.approve_envelope_activation(_draft(si2.id), actor="operator-a")

    active = [
        e
        for e in await any_store.list_envelopes(symbol="AAPL")
        if e.status is EnvelopeStatus.ACTIVE
    ]
    # THE INVARIANT any fix must restore: at most one live mandate per symbol.
    assert len(active) <= 1, (
        f"two ACTIVE envelopes for one symbol/position: {[e.id for e in active]} "
        "— overlapping full-size SELL mandates (single-ACTIVE bypass)"
    )
