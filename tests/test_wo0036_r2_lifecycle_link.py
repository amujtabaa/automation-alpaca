"""WO-0036 R2 — the SellIntent↔Envelope structural lifecycle link (both stores).

The root the quarantine-treadmill audit confirmed: the two lifecycles were
UNLINKED — no envelope operation ever advanced its backing intent, session
close blindly expired every PENDING/APPROVED intent, and the flatten planner
never saw an envelope's live child. These pins close the CLASS at its choke
points ("Option A+", ADR-010 amendment):

  A. Every entry into ACTIVE validates + links the backing intent
     (exists, symbol matches, PENDING/APPROVED; PENDING is normalized).
  B. Session close SPARES an intent backed by a live (ACTIVE/FROZEN) envelope.
  C. A releasing terminal (COMPLETED/EXPIRED/EXHAUSTED/BREACHED/CANCELLED —
     not SUPERSEDED) expires the backing intent when no live envelope remains.
  D. Manual flatten defers to a live envelope child (never double-books it);
     preemption never cancels an envelope out from under a live child.
  E. The envelope is the EXCLUSIVE driver of its intent: legacy dispatch and
     the public intent-transition API refuse a live-envelope-backed intent.
  F. The per-symbol clash counts FROZEN as live (a frozen mandate is a live
     mandate — INV-087 covers the resume-vs-fresh-approval sibling).

Gated surfaces (order-intent lifecycle, session-close event truth) — approved
scope of WO-0036 ("implement all 8", Ameen 2026-07-15).
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
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import (
    EnvelopeTransitionError,
    InvalidOrderError,
    SellIntentTransitionError,
)
from tests.store_helpers import submit_created_order

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
SI = SellIntentStatus
T = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
FP = "fp-r2-link"


def _draft(intent_id: str, symbol: str = "AAPL", **ov) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=100,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=T + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(ov)
    return ExecutionEnvelope(**base)


def _planned(kind=ActionKind.SUBMIT, limit_price=9.9, quantity=10) -> PlannedAction:
    return PlannedAction(
        kind=kind,
        limit_price=limit_price,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


async def _seed_position(store, symbol="AAPL", qty=100):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, 10.0, session_id=session.id
    )
    return session


async def _intent(store, symbol="AAPL", qty=100):
    session = await store.get_current_session()
    return await store.create_sell_intent(
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=qty,
        session_id=session.id,
    )


async def _active_env(store, symbol="AAPL", qty=100):
    """Seed a position + real intent, approve an envelope for it."""

    await store.initialize()
    await _seed_position(store, symbol, qty)
    si = await _intent(store, symbol, qty)
    env = await store.approve_envelope_activation(
        _draft(si.id, symbol=symbol, qty_ceiling=qty), actor="op"
    )
    return si, env


async def _intent_events(store, intent_id):
    return [
        e
        for e in await store.list_events()
        if e.event_type == "sell_intent_transition" and e.correlation_id == intent_id
    ]


# =========================================================================== #
# A. Activation validates + links the backing intent (closes Codex PR#8 #8)
# =========================================================================== #


async def test_a1_approve_refuses_unknown_intent_with_zero_artifacts(any_store):
    await any_store.initialize()
    draft = _draft("si-ghost")
    with pytest.raises(InvalidOrderError):
        await any_store.approve_envelope_activation(draft, actor="op")
    assert await any_store.get_envelope(draft.id) is None
    assert [
        e for e in await any_store.get_execution_events() if e.envelope_id == draft.id
    ] == []


async def test_a2_approve_refuses_symbol_mismatch(any_store):
    await any_store.initialize()
    si = await _intent(any_store, symbol="MSFT")
    draft = _draft(si.id, symbol="AAPL")
    with pytest.raises(InvalidOrderError):
        await any_store.approve_envelope_activation(draft, actor="op")
    assert await any_store.get_envelope(draft.id) is None


async def test_a3_approve_refuses_ordered_intent(any_store):
    """An ORDERED intent is owned by the legacy single-order dispatch — an
    envelope on top of it would be a second exit for the same mandate."""

    await any_store.initialize()
    await _seed_position(any_store)
    si = await _intent(any_store)
    await any_store.transition_sell_intent(si.id, SI.APPROVED)
    await any_store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    with pytest.raises(EnvelopeTransitionError):
        await any_store.approve_envelope_activation(_draft(si.id), actor="op")


async def test_a4_approve_refuses_terminal_intent(any_store):
    await any_store.initialize()
    si = await _intent(any_store)
    await any_store.transition_sell_intent(si.id, SI.EXPIRED)
    with pytest.raises(EnvelopeTransitionError):
        await any_store.approve_envelope_activation(_draft(si.id), actor="op")
    assert (await any_store.get_sell_intent(si.id)).status is SI.EXPIRED


async def test_a5_approve_normalizes_pending_intent_to_approved(any_store):
    """The envelope approval IS the human approval of the exit: activation
    normalizes a PENDING backing intent to APPROVED (evented), and the
    single-flight predicate agrees the exit is in flight."""

    await any_store.initialize()
    si = await _intent(any_store)
    assert si.status is SI.PENDING
    env = await any_store.approve_envelope_activation(_draft(si.id), actor="op")
    assert env.status is S.ACTIVE

    linked = await any_store.get_sell_intent(si.id)
    assert linked.status is SI.APPROVED
    events = await _intent_events(any_store, si.id)
    assert events[-1].payload == {
        "from": "pending",
        "to": "approved",
        "reason": "envelope_activation",
    }
    active = await any_store.active_sell_intent_for("AAPL")
    assert active is not None and active.id == si.id


async def test_a6_generic_transition_activation_validates_the_link_too(any_store):
    """The sibling activation path: create_envelope + transition_envelope
    (PENDING→APPROVED→ACTIVE) must enforce the SAME link — HALTED and the
    per-symbol clash are already checked on this edge; the intent link is not
    allowed to be the one activation invariant with a bypass."""

    await any_store.initialize()
    ghost = _draft("si-ghost")
    await any_store.create_envelope(ghost, actor="op")
    await any_store.transition_envelope(ghost.id, S.APPROVED, actor="op")
    with pytest.raises(InvalidOrderError):
        await any_store.transition_envelope(ghost.id, S.ACTIVE, actor="op")
    assert (await any_store.get_envelope(ghost.id)).status is S.APPROVED


# =========================================================================== #
# B. Session close spares live-envelope-backed intents (the P0 orphan root)
# =========================================================================== #


async def test_b1_close_spares_intent_backed_by_active_envelope(any_store):
    si, env = await _active_env(any_store)
    closed = await any_store.close_session(actor="op")
    assert closed.status.value == "closed"

    spared = await any_store.get_sell_intent(si.id)
    assert spared.status is SI.APPROVED, (
        "session close orphaned the envelope: its backing intent was expired "
        "while the mandate stayed ACTIVE"
    )
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE
    # Day-2 coherence: the symbol is still owned by the live mandate — a fresh
    # protection tick dedups to it instead of minting a duplicate exit.
    active = await any_store.active_sell_intent_for("AAPL")
    assert active is not None and active.id == si.id

    close_events = [
        e for e in await any_store.list_events() if e.event_type == "session_closed"
    ]
    assert close_events[-1].payload["expired_sell_intents"] == 0
    assert close_events[-1].payload["spared_sell_intents"] == 1


async def test_b2_close_spares_intent_backed_by_frozen_envelope(any_store):
    """FROZEN is live (kill-paused, resumable): the close must not expire the
    intent out from under a mandate the human may resume tomorrow."""

    si, env = await _active_env(any_store)
    await any_store.transition_envelope(env.id, S.FROZEN, actor="op")
    await any_store.close_session(actor="op")
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED
    assert (await any_store.get_envelope(env.id)).status is S.FROZEN


async def test_b3_close_still_expires_unbacked_and_draft_backed_intents(any_store):
    """The legacy expiry is unchanged for intents with no LIVE envelope: a bare
    intent and one backed only by a PENDING draft both expire (the draft can
    never activate afterwards — the A-pins refuse a terminal backing intent)."""

    await any_store.initialize()
    session = await any_store.get_current_session()
    bare = await any_store.create_sell_intent(
        symbol="MSFT",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=10,
        session_id=session.id,
    )
    drafted = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=10,
        session_id=session.id,
    )
    draft = _draft(drafted.id)
    await any_store.create_envelope(draft, actor="op")

    await any_store.close_session(actor="op")
    assert (await any_store.get_sell_intent(bare.id)).status is SI.EXPIRED
    assert (await any_store.get_sell_intent(drafted.id)).status is SI.EXPIRED
    # The stale draft is inert: activation now refuses its expired owner.
    with pytest.raises(EnvelopeTransitionError):
        await any_store.approve_envelope_activation(draft, actor="op")


# =========================================================================== #
# C. Terminal propagation — the envelope's end releases the intent
# =========================================================================== #


async def test_c1_completed_envelope_expires_intent_and_releases_symbol(any_store):
    si, env = await _active_env(any_store)
    done = await any_store.record_envelope_fill(
        env.id, quantity=100, dedupe_key="fill:r2:c1", price=9.9, order_id="o-c1"
    )
    assert done.status is S.COMPLETED

    released = await any_store.get_sell_intent(si.id)
    assert released.status is SI.EXPIRED
    events = await _intent_events(any_store, si.id)
    assert events[-1].payload == {
        "from": "approved",
        "to": "expired",
        "reason": "envelope_terminal",
    }
    # The symbol is released: fresh protection mints a FRESH intent.
    fresh = await _intent(any_store)
    assert fresh.id != si.id and fresh.status is SI.PENDING


async def test_c2_expired_envelope_expires_backing_intent(any_store):
    si, env = await _active_env(any_store)
    await any_store.transition_envelope(
        env.id, S.EXPIRED, actor="engine", reason="ttl_lapsed", now=T
    )
    assert (await any_store.get_sell_intent(si.id)).status is SI.EXPIRED


async def test_c3_supersession_keeps_the_intent_until_the_successor_ends(any_store):
    si, env = await _active_env(any_store)
    successor = _draft(si.id, qty_ceiling=90)
    new_env = await any_store.supersede_envelope(
        env.id, successor, actor="op", reason="amendment"
    )
    # SUPERSEDED is NOT a releasing terminal: the successor carries the mandate.
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED

    await any_store.transition_envelope(new_env.id, S.FROZEN, actor="op")
    await any_store.transition_envelope(new_env.id, S.CANCELLED, actor="op")
    assert (await any_store.get_sell_intent(si.id)).status is SI.EXPIRED


async def test_c4_breached_envelope_releases_the_symbol_for_fresh_protection(
    any_store,
):
    si, env = await _active_env(any_store)
    await any_store.transition_envelope(
        env.id, S.BREACHED, actor="engine", reason="floor violation", now=T
    )
    assert (await any_store.get_sell_intent(si.id)).status is SI.EXPIRED
    assert await any_store.active_sell_intent_for("AAPL") is None


async def test_c5_release_defers_while_a_child_may_rest_at_the_venue(any_store):
    """Adversarial self-review find: BREACHED/EXHAUSTED/REST_AT_FLOOR leave the
    working order RESTING at the venue. Releasing the intent at envelope-
    terminal would re-open the symbol to fresh protection while that child can
    still fill — a double-sell. The release must wait for the mandate's LAST
    live obligation: intent stays APPROVED (dedup keeps blocking) until the
    child reaches a venue terminal, and releases exactly then."""

    si, env = await _active_env(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, actor="engine", now=T
    )
    child = staged.order
    await submit_created_order(any_store, child.id, broker_order_id="brk-c5")

    await any_store.transition_envelope(
        env.id, S.BREACHED, actor="engine", reason="floor violation", now=T
    )
    held = await any_store.get_sell_intent(si.id)
    assert held.status is SI.APPROVED, (
        "intent released while the breached mandate's child still rests at "
        "the venue — fresh protection could double-book it"
    )
    active = await any_store.active_sell_intent_for("AAPL")
    assert active is not None and active.id == si.id

    # The child terminalizes at the venue → the mandate's last obligation ends.
    await any_store.transition_order(child.id, OrderStatus.CANCELED)
    released = await any_store.get_sell_intent(si.id)
    assert released.status is SI.EXPIRED
    assert await any_store.active_sell_intent_for("AAPL") is None


async def test_c6_rest_at_floor_expiry_releases_only_when_the_child_fills(
    any_store,
):
    """The REST_AT_FLOOR sibling: the expired mandate's child deliberately
    keeps resting — the intent must keep owning the symbol until that child
    terminalizes (here: fills)."""

    si, env = await _active_env(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, _planned(quantity=100), snapshot_fingerprint=FP, actor="engine", now=T
    )
    child = staged.order
    await submit_created_order(any_store, child.id, broker_order_id="brk-c6")
    await any_store.transition_envelope(
        env.id, S.EXPIRED, actor="engine", reason="ttl_lapsed:rest_at_floor", now=T
    )
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED

    await any_store.transition_order(child.id, OrderStatus.FILLED, filled_quantity=100)
    assert (await any_store.get_sell_intent(si.id)).status is SI.EXPIRED


async def test_c7_staged_replacement_never_masks_a_live_predecessor(any_store):
    """Fresh-eyes review find (the Codex #6 shape recurring in the release
    predicate): with predecessor A SUBMITTED-live and a staged CREATED reprice
    replacement B, the 'newest working order' view is B — a predicate keyed on
    it would read 'no live child' and release the intent while A still rests
    at the venue. The live-child scan must consider EVERY child: release only
    after BOTH B (local cancel) and A (venue terminal) are gone."""

    si, env = await _active_env(any_store)
    staged_a = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, actor="engine", now=T
    )
    a = staged_a.order
    await submit_created_order(any_store, a.id, broker_order_id="brk-c7a")
    staged_b = await any_store.stage_envelope_action(
        env.id,
        _planned(kind=ActionKind.REPRICE, limit_price=9.8),
        snapshot_fingerprint=FP,
        actor="engine",
        now=T + timedelta(seconds=5),
    )
    b = staged_b.order
    assert b is not None and b.status is OrderStatus.CREATED
    assert (await any_store.get_order(a.id)).status is OrderStatus.SUBMITTED

    await any_store.transition_envelope(
        env.id, S.BREACHED, actor="engine", reason="floor violation", now=T
    )
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED, (
        "the staged CREATED replacement masked the still-live predecessor — "
        "the intent released while A rests at the venue (double-book window)"
    )

    # B dies locally: A still rests — the release must keep deferring.
    await any_store.transition_order(b.id, OrderStatus.CANCELED)
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED

    # A reaches its venue terminal: the mandate's last obligation ends.
    await any_store.transition_order(a.id, OrderStatus.CANCELED)
    assert (await any_store.get_sell_intent(si.id)).status is SI.EXPIRED


async def test_c8_supersede_refused_while_a_masked_predecessor_rests(any_store):
    """The same masked-predecessor shape at the supersession choke point: with
    predecessor A SUBMITTED-live and a staged CREATED reprice replacement B,
    the newest-working-order view is B — the WO-0027 live-order supersession
    block would wave the amendment through, activating a successor next to
    the still-resting A (the INV-077 double exposure it exists to prevent).
    Supersession must refuse while ANY child may rest at the venue."""

    si, env = await _active_env(any_store)
    staged_a = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, actor="engine", now=T
    )
    await submit_created_order(any_store, staged_a.order.id, broker_order_id="brk-c8")
    staged_b = await any_store.stage_envelope_action(
        env.id,
        _planned(kind=ActionKind.REPRICE, limit_price=9.8),
        snapshot_fingerprint=FP,
        actor="engine",
        now=T + timedelta(seconds=5),
    )
    assert staged_b.order is not None and staged_b.order.status is OrderStatus.CREATED

    with pytest.raises(EnvelopeTransitionError):
        await any_store.supersede_envelope(
            env.id, _draft(si.id, qty_ceiling=90), actor="op", reason="amendment"
        )
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE


# =========================================================================== #
# D. Flatten defers to a live envelope child (closes Codex PR#8 #4)
# =========================================================================== #


async def test_d1_flatten_defers_to_live_envelope_child(any_store):
    si, env = await _active_env(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, actor="engine", now=T
    )
    child = staged.order
    await submit_created_order(any_store, child.id, broker_order_id="brk-d1")
    orders_before = len(await any_store.list_orders())

    result = await any_store.flatten_position("AAPL", actor="operator-a")

    assert result.deferred is True
    assert result.order is not None and result.order.id == child.id
    assert result.intent is not None and result.intent.id == si.id
    assert len(await any_store.list_orders()) == orders_before, (
        "flatten minted a second SELL next to the live envelope child — double exposure"
    )
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED
    deferrals = [
        e
        for e in await any_store.list_events()
        if e.event_type == "manual_flatten_deferred"
    ]
    assert deferrals[-1].payload["reason"] == "deferred_to_live_envelope_child"
    assert deferrals[-1].payload["order_status"] == OrderStatus.SUBMITTED.value


async def test_d2_flatten_preempts_envelope_with_only_a_staged_child(any_store):
    """No live child (CREATED is local-only): the human's backstop preempts —
    envelope cancelled, staged child swept, intent expired EXACTLY once, and a
    fresh MANUAL_FLATTEN exit is created."""

    si, env = await _active_env(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, actor="engine", now=T
    )
    result = await any_store.flatten_position("AAPL", actor="operator-a")

    assert result.outcome == "created"
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert (await any_store.get_envelope(env.id)).status is S.CANCELLED
    assert (await any_store.get_order(staged.order.id)).status is OrderStatus.CANCELED
    released = await any_store.get_sell_intent(si.id)
    assert released.status is SI.EXPIRED
    transitions = [
        e.payload for e in await _intent_events(any_store, si.id) if e.payload
    ]
    expiries = [p for p in transitions if p.get("to") == "expired"]
    assert len(expiries) == 1, (
        f"the old intent must expire exactly once (event-log truth); got {expiries}"
    )


async def test_d3_flatten_defers_on_a_quarantined_child(any_store):
    """A TIMEOUT_QUARANTINE child MAY be live at the venue (ADR-002): the
    flatten must defer — never crash, never double-book, never blind-cancel."""

    si, env = await _active_env(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, actor="engine", now=T
    )
    child = staged.order
    claim = await any_store.claim_order_for_submission(child.id)
    assert claim.outcome == "claimed"
    await any_store.quarantine_timed_out_order(child.id, reason="submit_timeout")

    result = await any_store.flatten_position("AAPL", actor="operator-a")
    assert result.deferred is True
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED


# =========================================================================== #
# E. The envelope is the exclusive driver of its intent
# =========================================================================== #


async def test_e1_legacy_dispatch_refuses_a_live_envelope_backed_intent(any_store):
    si, env = await _active_env(any_store)
    with pytest.raises(SellIntentTransitionError):
        await any_store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED
    assert (await any_store.get_sell_intent(si.id)).order_id is None


async def test_e2_public_transition_refuses_a_live_envelope_backed_intent(any_store):
    si, env = await _active_env(any_store)
    with pytest.raises(SellIntentTransitionError):
        await any_store.transition_sell_intent(si.id, SI.EXPIRED)
    assert (await any_store.get_sell_intent(si.id)).status is SI.APPROVED


# =========================================================================== #
# F. A FROZEN mandate is a live mandate (INV-087 clash extension)
# =========================================================================== #


async def test_f1_second_mandate_refused_while_one_is_frozen(any_store):
    """Freeze does not release the symbol: approving a SECOND envelope next to
    a FROZEN one (whose child may still rest at the venue) is the same
    double-mandate INV-087 forbids for ACTIVE."""

    si, env = await _active_env(any_store)
    await any_store.transition_envelope(env.id, S.FROZEN, actor="op")
    with pytest.raises(EnvelopeTransitionError, match="per-symbol"):
        await any_store.approve_envelope_activation(_draft(si.id), actor="op")
    # The frozen mandate itself still resumes (self-exclusion unchanged).
    resumed = await any_store.transition_envelope(env.id, S.ACTIVE, actor="op")
    assert resumed.status is S.ACTIVE
