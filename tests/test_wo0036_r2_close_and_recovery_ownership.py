"""WO-0036 R2 Part B (P2): session-close sparing + needs-review owner retention.

Two operator-ratified spec properties (RATIFICATION-partb-completion.md D2, from
the cross-investigator conformance oracle):

**P-A** — an ``APPROVED`` (pre-activation, never-activated) envelope is NOT a live
delegated exit obligation: at session close its owner intent expires with the
other open intents, and the envelope itself is swept ``APPROVED -> EXPIRED`` in
the same atomic close (leaving it delegating beside an expired owner would both
manufacture the pre-R2 orphan shape and invite the reconcile restore to
resurrect the closed owner). Sparing at close is reserved for mandates that are
genuinely still working: ACTIVE/FROZEN delegation, or terminal envelopes whose
children carry unresolved venue uncertainty.

**P-B** — a child order latched ``needs_review`` (a stranded broker order that
HAD fills) is unresolved venue exposure, not proof of absence: an envelope going
terminal must NOT release its owner while that recovery is open. Retention here
is release-prevention only — it never resurrects an owner a human has since
stood down (the restore path stays keyed on the strict pre-P-B predicate).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_UNRESOLVED,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
FP = "wo0036-r2-p2-ownership"


def _draft(
    intent_id: str,
    *,
    symbol: str = "AAPL",
    quantity: int = 100,
    session_id: str | None = None,
) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=quantity,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _action() -> PlannedAction:
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=100,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _hold(store, *, symbol: str = "AAPL", quantity: int = 100):
    """A held position whose establishing BUY is terminal (realistic; matches
    the P1-reseeded oracle so no flatten/BUYS_OPEN interaction can leak in)."""
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id, symbol, OrderSide.BUY, quantity, session_id=session.id
    )
    await store.append_fill(
        buy.id,
        symbol,
        OrderSide.BUY,
        quantity,
        10.0,
        source_fill_id=f"{FP}:hold:{candidate.id}",
        session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    return session


async def _activate(store):
    await store.initialize()
    session = await _hold(store)
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _draft(intent.id, session_id=session.id), actor="operator-a"
    )
    return session, intent, envelope


async def _terminal_child_with_recovery(store, session, envelope, *, cleanup_status):
    """Stage + claim a child, cancel it locally, and latch a submit-recovery
    documenting the (possibly live) broker-side order."""
    staged = await store.stage_envelope_action(
        envelope.id, _action(), snapshot_fingerprint=FP, now=NOW
    )
    claimed = await store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await store.transition_order(staged.order.id, OrderStatus.CANCELED)
    await store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id=f"broker-{FP}-{staged.order.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="p2 ownership pin",
        session_id=session.id,
        cleanup_status=cleanup_status,
    )
    return staged.order


# --------------------------------------------------------------------------- #
# P-A: session-close sparing
# --------------------------------------------------------------------------- #


async def test_close_expires_owner_of_pre_activation_approved_envelope(any_store):
    # APPROVED is pre-activation authorization, not a working mandate: at the
    # session boundary the owner expires like any open intent, and the envelope
    # is swept APPROVED -> EXPIRED in the SAME atomic close (no orphan, and the
    # reconcile restore can never resurrect the closed owner from a still-
    # delegating envelope).
    await any_store.initialize()
    session = await _hold(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    draft = _draft(intent.id, session_id=session.id)
    await any_store.create_envelope(draft, actor="operator-a")
    await any_store.transition_envelope(
        draft.id, EnvelopeStatus.APPROVED, actor="operator-a", now=NOW
    )

    await any_store.close_session(actor="operator-a")

    assert await any_store.active_sell_intent_for("AAPL") is None
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
    swept = await any_store.get_envelope(draft.id)
    assert swept.status is EnvelopeStatus.EXPIRED
    expiry_events = [
        e
        for e in await any_store.get_execution_events()
        if e.envelope_id == draft.id
        and e.event_type is ExecutionEventType.ENVELOPE_EXPIRED
    ]
    assert len(expiry_events) == 1


async def test_close_spares_owner_of_active_envelope(any_store):
    # The long-standing sparing behavior, preserved exactly: a genuinely working
    # (ACTIVE) mandate survives the close with its owner.
    session, intent, envelope = await _activate(any_store)

    await any_store.close_session(actor="operator-a")

    active = await any_store.active_sell_intent_for("AAPL")
    assert active is not None and active.id == intent.id
    assert (await any_store.get_envelope(envelope.id)).status is EnvelopeStatus.ACTIVE


async def test_close_spares_owner_when_terminal_envelope_has_unresolved_recovery(
    any_store,
):
    # Fail-closed venue uncertainty: the envelope is terminal but its child has
    # an UNRESOLVED submit-recovery (broker order possibly live). Expiring the
    # owner at close would orphan real exposure — spare it.
    session, intent, envelope = await _activate(any_store)
    await _terminal_child_with_recovery(
        any_store, session, envelope, cleanup_status=RECOVERY_UNRESOLVED
    )
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="p2 hard-rail", now=NOW
    )
    retained = await any_store.get_sell_intent(intent.id)
    assert retained.status is SellIntentStatus.APPROVED  # precondition

    await any_store.close_session(actor="operator-a")

    active = await any_store.active_sell_intent_for("AAPL")
    assert active is not None and active.id == intent.id


async def test_flatten_deferral_to_envelope_child_uses_granular_audit_reason(
    any_store,
):
    # F.2 graft (P3b): the manual_flatten_deferred provenance event
    # distinguishes deferral to a live ENVELOPE CHILD from deferral to the
    # intent's own live protection order. Pre-graft both emitted
    # "deferred_to_live_protection", which under-describes the envelope case —
    # an auditor reading the trail could not tell which machinery held the
    # flatten. Direct-order deferral coverage keeps its original reason (pinned
    # by the pre-existing 3e/phase7 suites).
    session, intent, envelope = await _activate(any_store)
    staged = await any_store.stage_envelope_action(
        envelope.id, _action(), snapshot_fingerprint=FP, now=NOW
    )
    claimed = await any_store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await any_store.transition_order(
        staged.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{FP}-defer",
    )

    result = await any_store.flatten_position("AAPL", actor="operator-a")

    assert result.outcome == "existing" and result.deferred is True
    deferrals = [
        e
        for e in await any_store.list_events()
        if e.event_type == "manual_flatten_deferred"
    ]
    assert len(deferrals) == 1
    payload = deferrals[0].payload
    assert payload["reason"] == "deferred_to_live_envelope_child"
    assert payload["order_status"] == "submitted"
    assert payload["actor"] == "operator-a"


async def test_close_summary_carries_spared_sell_intents_count(any_store):
    # F.2 graft (P3a, after P2 so it counts the FINAL sparing semantics): the
    # session-close summary event carries how many sell intents were SPARED by
    # the projection's close predicate, so the close audit is a complete account
    # of the boundary — the expired count alone under-reports when a working
    # mandate survives.
    session, spared_intent, _env = await _activate(any_store)
    plain = await any_store.create_sell_intent(
        symbol="MSFT",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=50,
        session_id=session.id,
    )

    await any_store.close_session(actor="operator-a")

    closes = [
        e for e in await any_store.list_events() if e.event_type == "session_closed"
    ]
    assert len(closes) == 1
    payload = closes[0].payload
    assert payload["expired_sell_intents"] == 1  # the plain MSFT intent
    assert payload["spared_sell_intents"] == 1  # the ACTIVE-envelope owner
    # The spared owner genuinely survived; the plain intent expired.
    assert (
        await any_store.get_sell_intent(spared_intent.id)
    ).status is SellIntentStatus.APPROVED
    assert (
        await any_store.get_sell_intent(plain.id)
    ).status is SellIntentStatus.EXPIRED


async def test_close_with_sweep_emits_identical_streams_on_both_stores(tmp_path):
    # Review advisory A-1 (P2 event-log-truth lens): the P-A sweep writes
    # ENVELOPE_EXPIRED execution+audit events MID-CLOSE — pin that both stores
    # emit the same normalized event streams in the same relative order for an
    # identical close-with-sweep script (swept pre-activation owner + spared
    # ACTIVE owner + an open candidate), so replay/parity can never drift here.
    from app.store.memory import InMemoryStateStore
    from app.store.sqlite import SqliteStateStore

    async def drive(store):
        await store.initialize()
        session = await _hold(store)
        # Swept: pre-activation APPROVED envelope on AAPL.
        swept = await store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
        draft = _draft(swept.id, session_id=session.id)
        await store.create_envelope(draft, actor="operator-a")
        await store.transition_envelope(
            draft.id, EnvelopeStatus.APPROVED, actor="operator-a", now=NOW
        )
        # Spared: ACTIVE envelope on MSFT (own held position).
        session2 = await _hold(store, symbol="MSFT")
        spared = await store.create_sell_intent(
            symbol="MSFT",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session2.id,
        )
        await store.approve_envelope_activation(
            _draft(spared.id, symbol="MSFT", session_id=session2.id),
            actor="operator-a",
        )
        await store.create_candidate("TSLA", session_id=session2.id)
        await store.close_session(actor="operator-a")

        def _norm(key):
            # Entity ids are random per store instance; normalize them so the
            # comparison pins STRUCTURE and ORDER, not uuid values.
            return re.sub(r"[0-9a-f]{32}", "*", key) if key else key

        audit = [(e.event_type, e.symbol) for e in await store.list_events()]
        execution = [
            (e.event_type.value, e.symbol, _norm(e.dedupe_key))
            for e in await store.get_execution_events()
        ]
        return audit, execution

    mem_audit, mem_exec = await drive(InMemoryStateStore())
    sq = SqliteStateStore(tmp_path / "a1-parity.db")
    try:
        sq_audit, sq_exec = await drive(sq)
    finally:
        if sq._conn is not None:
            sq._conn.close()
            sq._conn = None
    assert mem_audit == sq_audit
    assert mem_exec == sq_exec
    # The sweep's expiry is present exactly once, identically keyed.
    assert sum(1 for _t, _s, key in mem_exec if key and ":expired" in key) == 1


# --------------------------------------------------------------------------- #
# P-B: needs-review retention
# --------------------------------------------------------------------------- #


async def test_envelope_terminal_with_open_needs_review_recovery_retains_owner(
    any_store,
):
    # "Human escalation is unresolved venue exposure, not proof of absence":
    # the stranded broker order HAD fills, so the symbol's exit obligation is
    # not discharged — going terminal must not release the owner while the
    # needs_review recovery is open. (Freeing the symbol here would authorize a
    # SECOND automated SELL against possibly-already-sold shares.)
    session, intent, envelope = await _activate(any_store)
    await _terminal_child_with_recovery(
        any_store, session, envelope, cleanup_status=RECOVERY_NEEDS_REVIEW
    )

    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="p2 delegation ended", now=NOW
    )

    retained = await any_store.get_sell_intent(intent.id)
    assert retained.status is SellIntentStatus.APPROVED
    active = await any_store.active_sell_intent_for("AAPL")
    assert active is not None and active.id == intent.id


async def test_needs_review_retention_is_fail_closed_but_not_monopolizing(any_store):
    # The operational posture of P-B retention, pinned end-to-end:
    #   (a) the retained owner is projection-CONTROLLED — a direct human
    #       stand-down via the generic intent transition is refused (the shared
    #       projection is the only release authority);
    #   (b) manual flatten FAILS CLOSED while the needs_review exposure is
    #       unreconciled (minting a full-size MANUAL_FLATTEN SELL beside
    #       possibly-already-sold shares is the §5.3-class double-sell); and
    #   (c) the quarantine is COMPLETE and single-identified: creating "another"
    #       protection intent idempotently returns the retained owner (single
    #       mandate identity), and a NEW envelope delegation on the symbol is
    #       refused for the same reason flatten is — any fresh automated SELL
    #       beside an unreconciled stranded SELL risks the double-sell. This is
    #       the repo's standing ambiguity posture (TIMEOUT_QUARANTINE precedent:
    #       ambiguous broker truth quarantines the flow, never drives sizing).
    # The release valve for the whole quarantine (reconciling the needs_review
    # record itself) is a parked operator decision — see BLOCKED-DECISIONS.md.
    from app.store.base import (
        EnvelopeTransitionError,
        FlattenBlockedError,
        SellIntentTransitionError,
    )

    session, intent, envelope = await _activate(any_store)
    await _terminal_child_with_recovery(
        any_store, session, envelope, cleanup_status=RECOVERY_NEEDS_REVIEW
    )
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="p2 delegation ended", now=NOW
    )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED  # retained (P-B)

    with pytest.raises(SellIntentTransitionError, match="envelope delegation"):
        await any_store.transition_sell_intent(intent.id, SellIntentStatus.EXPIRED)

    with pytest.raises(FlattenBlockedError, match="retained obligation"):
        await any_store.flatten_position("AAPL", actor="operator-a")

    # Single-mandate identity: creating "another" protection intent for the
    # symbol idempotently returns the retained owner, not a duplicate.
    dedup = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    assert dedup.id == intent.id

    # And a NEW envelope delegation is refused while the exposure is
    # unreconciled — the sell side of the symbol is fully quarantined.
    with pytest.raises(EnvelopeTransitionError, match="retains its delegation"):
        await any_store.approve_envelope_activation(
            _draft(intent.id, session_id=session.id), actor="operator-a"
        )
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.APPROVED


async def test_needs_review_retention_never_resurrects_an_expired_owner(any_store):
    # The hold-vs-resurrect asymmetry, on the legacy/corrupt shape it protects
    # against: an owner already EXPIRED (pre-P2 release, drift, or operator
    # action recorded before this change) whose lineage retains ONLY via an
    # open needs_review child must STAY expired — the reconcile restore path is
    # keyed on the strict (pre-P2) predicate, so human escalation holds live
    # owners but never resurrects stood-down ones.
    session, intent, envelope = await _activate(any_store)
    await _terminal_child_with_recovery(
        any_store, session, envelope, cleanup_status=RECOVERY_NEEDS_REVIEW
    )
    await any_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="p2 delegation ended", now=NOW
    )

    # Force the legacy shape raw (hostile-suite idiom): owner EXPIRED beside the
    # needs-review-retained terminal lineage.
    if hasattr(any_store, "_sell_intents"):
        row = any_store._sell_intents[intent.id]
        row.status = SellIntentStatus.EXPIRED
        row.expired_at = NOW
    else:
        any_store._conn.execute(
            "UPDATE sell_intents SET status=?, expired_at=? WHERE id=?",
            (SellIntentStatus.EXPIRED.value, NOW.isoformat(), intent.id),
        )
        any_store._conn.commit()

    # A reconcile-bearing touch (idempotent same-status transition) must NOT
    # resurrect the expired owner.
    try:
        await any_store.transition_envelope(
            envelope.id, EnvelopeStatus.BREACHED, reason="noop", now=NOW
        )
    except Exception:
        pass
    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
