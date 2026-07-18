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
    SessionStatus,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import SessionAlreadyClosedError
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

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


def _canon_streams(audit_dumps, execution_dumps):
    """Canonicalize a store's (audit, execution) FULL model-dump streams for
    cross-store / cross-restart comparison (REV-0029 P1-2). Random 32-hex ids map
    to stable placeholders in FIRST-APPEARANCE order — so identity RELATIONSHIPS
    across the two streams still must match, not just shapes — and wall-clock
    timestamps collapse to a sentinel. Sequence numbers are kept verbatim: they
    ARE the ordering truth. A single ``id_map`` spans both streams so an id that
    appears in audit and execution maps to the same placeholder."""

    id_map: dict = {}

    def _canon(value):
        if isinstance(value, str):
            value = re.sub(
                r"[0-9a-f]{32}",
                lambda m: id_map.setdefault(m.group(0), f"<id{len(id_map)}>"),
                value,
            )
            return re.sub(
                r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[0-9:.+\-Z]*",
                "<ts>",
                value,
            )
        if isinstance(value, dict):
            return {k: _canon(v) for k, v in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [_canon(v) for v in value]
        if hasattr(value, "isoformat"):
            return "<ts>"
        return value

    return [_canon(d) for d in audit_dumps], [_canon(d) for d in execution_dumps]


async def _build_close_with_sweep_state(store):
    """The canonical close-with-sweep fixture (pre-close): a swept pre-activation
    APPROVED envelope (AAPL), a spared ACTIVE envelope (MSFT, own held position),
    and an open candidate (TSLA). Returns ``(session, swept_intent)``; the caller
    drives ``close_session`` (or injects a failure first)."""

    await store.initialize()
    session = await _hold(store)
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
    return session, swept


async def _canon_store_streams(store):
    return _canon_streams(
        [e.model_dump() for e in await store.list_events()],
        [e.model_dump() for e in await store.get_execution_events()],
    )


async def _drive_close_with_sweep(store):
    """Build the fixture, close the session, and return the canonicalized
    (audit, execution) streams."""

    await _build_close_with_sweep_state(store)
    await store.close_session(actor="operator-a")
    return await _canon_store_streams(store)


async def test_close_with_sweep_emits_identical_streams_on_both_stores(tmp_path):
    # Review advisory A-1 (P2 event-log-truth lens): the P-A sweep writes
    # ENVELOPE_EXPIRED execution+audit events MID-CLOSE — pin that both stores
    # emit the same normalized event streams in the same relative order for an
    # identical close-with-sweep script. REV-0029 P1-2: compare canonicalized
    # FULL model dumps (payload/reason/actor/session/correlation/identity/qty/
    # price/source/authority all pinned), not lossy (type, symbol, key) tuples.
    mem_audit, mem_exec = await _drive_close_with_sweep(InMemoryStateStore())
    sq = SqliteStateStore(tmp_path / "a1-parity.db")
    try:
        sq_audit, sq_exec = await _drive_close_with_sweep(sq)
    finally:
        if sq._conn is not None:
            sq._conn.close()
            sq._conn = None
    assert mem_audit == sq_audit
    assert mem_exec == sq_exec
    # The sweep's expiry is present exactly once, identically keyed.
    assert (
        sum(1 for e in mem_exec if (e.get("dedupe_key") or "").endswith(":expired"))
        == 1
    )


async def test_close_with_sweep_stream_survives_sqlite_restart(tmp_path):
    # REV-0029 P1-2 (restart variant): the full canonical close+sweep stream is a
    # property of the PERSISTED log, not a live in-process projection. A sqlite
    # store reopened on the same file replays a byte-identical audit+execution
    # stream (same relative order), so no reload/re-projection step silently
    # rewrites event truth across a restart. Cross-checked against the memory
    # store's stream for the same script.
    db_path = tmp_path / "restart-parity.db"
    store = SqliteStateStore(db_path)
    try:
        before_audit, before_exec = await _drive_close_with_sweep(store)
    finally:
        if store._conn is not None:
            store._conn.close()
            store._conn = None

    reopened = SqliteStateStore(db_path)
    try:
        await reopened.initialize()
        after_audit, after_exec = await _canon_store_streams(reopened)
    finally:
        if reopened._conn is not None:
            reopened._conn.close()
            reopened._conn = None

    assert after_audit == before_audit
    assert after_exec == before_exec
    mem_audit, mem_exec = await _drive_close_with_sweep(InMemoryStateStore())
    assert after_audit == mem_audit
    assert after_exec == mem_exec


async def test_close_with_sweep_retry_is_idempotent(any_store):
    # REV-0029 P1-2 (retry variant): a retried close on an already-closed session
    # is rejected (SessionAlreadyClosedError) and appends/rewrites NOTHING — the
    # canonical event stream is byte-identical before and after the retry, so a
    # duplicated close can never emit a second sweep or a divergent stream.
    before_audit, before_exec = await _drive_close_with_sweep(any_store)
    with pytest.raises(SessionAlreadyClosedError):
        await any_store.close_session(actor="operator-a")
    after_audit, after_exec = await _canon_store_streams(any_store)
    assert after_audit == before_audit
    assert after_exec == before_exec


async def test_close_with_sweep_rolls_back_atomically_on_injected_failure(
    any_store, monkeypatch
):
    # REV-0029 P1-2 (rollback-injection variant): the close-with-sweep is a SINGLE
    # atomic unit on both stores (memory `_atomic()` snapshot/restore; sqlite
    # `_tx()` BEGIN/ROLLBACK). A failure injected mid-close — after at least one
    # close event has been staged — rolls the WHOLE close back identically: no
    # partial event stream, session still ACTIVE, swept owner still APPROVED.
    # This pins that both stores fail ATOMICALLY the same way, not merely that
    # they agree on the happy path (the lossy predecessor could not see a
    # half-applied close at all).
    session, swept = await _build_close_with_sweep_state(any_store)
    before_audit = [e.model_dump() for e in await any_store.list_events()]
    before_exec = [e.model_dump() for e in await any_store.get_execution_events()]

    class _InjectedRollback(RuntimeError):
        pass

    # Fail on the SECOND audit-event write during close, so ≥1 close event is
    # already staged in the atomic block before the failure — proving rollback of
    # staged state, not a pre-write bail-out. Store-agnostic: memory appends audit
    # events via `_append_event_unlocked(event_type, ...)`, sqlite via
    # `_insert_event(cur, event_type, ...)`; both re-dispatch through *args.
    calls = {"n": 0}

    def _boom(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise _InjectedRollback("injected mid-close failure")
        return _original(*args, **kwargs)

    if hasattr(any_store, "_append_event_unlocked"):  # memory
        _original = any_store._append_event_unlocked
        monkeypatch.setattr(any_store, "_append_event_unlocked", _boom)
    else:  # sqlite
        _original = any_store._insert_event
        monkeypatch.setattr(any_store, "_insert_event", _boom)

    with pytest.raises(_InjectedRollback):
        await any_store.close_session(actor="operator-a")

    # Full rollback: not one close event leaked onto either stream, the session
    # is still ACTIVE, and the swept owner is still APPROVED (the sweep undone).
    assert [e.model_dump() for e in await any_store.list_events()] == before_audit
    assert [
        e.model_dump() for e in await any_store.get_execution_events()
    ] == before_exec
    current = await any_store.get_current_session()
    assert current is not None
    assert current.id == session.id
    assert current.status is SessionStatus.ACTIVE
    assert (
        await any_store.get_sell_intent(swept.id)
    ).status is SellIntentStatus.APPROVED


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

    # A GUARANTEED reconcile-bearing operation must NOT resurrect the expired
    # owner. REV-0029 P0-4 (fixed): the original touch here was a
    # BREACHED -> BREACHED same-status no-op, which never reaches the owner
    # reconcile (both stores reconcile a same-status no-op only for
    # APPROVED/ACTIVE targets) — the pin could not fail. ``initialize()``
    # re-projects EVERY envelope owner via the R2 startup convergence block, so
    # the strict-keyed restore path provably RUNS here and must decline.
    await any_store.initialize()

    assert (
        await any_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
    # And the decline is total: no restore transition was ever emitted.
    restored = [
        e
        for e in await any_store.list_events()
        if e.event_type == "sell_intent_transition"
        and e.payload.get("reason") == "envelope_delegation_restored"
    ]
    assert restored == []
