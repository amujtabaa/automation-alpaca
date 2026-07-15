"""WO-0035 — root-cause batch from the quarantine-treadmill audit (2026-07-15).

Four verified residuals, each the ROOT form of a defect this session had
previously fixed at one call site only:

  F2   sqlite nested-tx crash: the FIRST envelope approval (or FROZEN->ACTIVE
       resume) of a new calendar day hit ``_ensure_current_session_locked``'s
       own transaction INSIDE the method's open transaction ->
       ``sqlite3.OperationalError: cannot start a transaction within a
       transaction`` — a crash on THE human-gated approval surface, hidden by
       every test's same-day ``initialize()``. (Reproduced directly.)
  F3   the reconciliation inferred-fill bridge repeated the record-first
       pattern with no pre-fill position -> spurious
       ``fill_overfill_quarantined`` on a clean full exit recovered via
       reconcile. ROOT FORM: ``append_fill`` now SELF-derives the pre-fill
       position by excluding its own dedupe identity from the fold — the
       caller-burden ``prior_position`` parameter class dies entirely.
  F1   ``transition_envelope`` / ``record_envelope_fill`` had no clock
       parameter at all, so BREACHED/EXHAUSTED/EXPIRED/policy-freeze stamps
       inside the deterministic tick were wall-clock (H11).
  S1   the venue leg dropped broker rejection reasons: TerminalBrokerError ->
       bare ``transition_order(REJECTED)``; the WHY never reached the durable
       log ("recorded, never hidden" violated for a broker-authoritative
       fact). Extends the approved WO-0034 spec-1 pattern to the venue leg.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.broker.mock import MockBrokerAdapter
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    OrderSide,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction

pytestmark = pytest.mark.anyio

T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
NEXT_DAY = T_NOW + timedelta(days=1)


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
        expires_at=T_NOW + timedelta(days=3),
        allowed_session_phases=list(SessionType),
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def _planned(quantity=100, limit_price=9.90) -> PlannedAction:
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=limit_price,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=9.50,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


async def _seed_position(store, quantity: int = 100):
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, quantity, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, quantity, 10.0, session_id=session.id
    )


async def _active_envelope(store, intent_suffix="1"):
    await _seed_position(store, 100)
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return await store.approve_envelope_activation(_draft(si.id), actor="op")


def _both_clocks(at):
    return (
        patch("app.store.sqlite.utcnow", return_value=at),
        patch("app.store.memory.utcnow", return_value=at),
    )


# ------------------------------------------------------------------------- #
# F2 — date-rollover session bootstrap must not crash the approval surface
# ------------------------------------------------------------------------- #
async def test_F2_first_approval_of_a_new_day_does_not_crash(any_store):
    p1, p2 = _both_clocks(T_NOW)
    with p1, p2:
        await any_store.initialize()
        # The backing intent is minted on DAY 1 (WO-0036 R2: activation
        # validates it) — creating it on day 2 would itself bootstrap the new
        # session and defeat this pin's "first call of the day" premise.
        si = await any_store.create_sell_intent(
            symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
        )
    # Next calendar day; NO other store call has bootstrapped the new session.
    p1, p2 = _both_clocks(NEXT_DAY)
    with p1, p2:
        env = await any_store.approve_envelope_activation(_draft(si.id), actor="op")
        assert env.status is EnvelopeStatus.ACTIVE
        # and the new day's session actually exists (created, not skipped)
        assert len(await any_store.list_sessions()) == 2


async def test_F2_first_resume_of_a_new_day_does_not_crash(any_store):
    p1, p2 = _both_clocks(T_NOW)
    with p1, p2:
        await any_store.initialize()
        si = await any_store.create_sell_intent(
            symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
        )
        env = await any_store.approve_envelope_activation(_draft(si.id), actor="op")
        await any_store.transition_envelope(env.id, EnvelopeStatus.FROZEN, actor="op")
    p1, p2 = _both_clocks(NEXT_DAY)
    with p1, p2:
        resumed = await any_store.transition_envelope(
            env.id, EnvelopeStatus.ACTIVE, actor="op"
        )
        assert resumed.status is EnvelopeStatus.ACTIVE


async def test_F2_unknown_envelope_transition_still_has_no_session_side_effect(
    any_store,
):
    # The C2 guard must survive the fix: an unknown-id transition on the new
    # day raises with NO session row leaked (memory parity).
    from app.store.base import UnknownEntityError

    p1, p2 = _both_clocks(T_NOW)
    with p1, p2:
        await any_store.initialize()
        before = len(await any_store.list_sessions())
    p1, p2 = _both_clocks(NEXT_DAY)
    with p1, p2:
        with pytest.raises(UnknownEntityError):
            await any_store.transition_envelope(
                "nonexistent", EnvelopeStatus.ACTIVE, actor="op"
            )
        assert len(await any_store.list_sessions()) == before


# ------------------------------------------------------------------------- #
# F3 — inferred-fill bridge: clean full exit, recovered via reconcile, must
# not fabricate an overfill quarantine (root: self-derived pre-fill position)
# ------------------------------------------------------------------------- #
async def test_F3_inferred_fill_clean_exit_never_fabricates_overfill(any_store):
    from app.monitoring import _apply_inferred_fills
    from app.reconciliation import InferredFill, ReconciliationPlan

    await any_store.initialize()
    env = await _active_envelope(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, _planned(quantity=100), snapshot_fingerprint="fp", now=T_NOW
    )
    assert staged.order is not None
    order = staged.order

    plan = ReconciliationPlan(
        inferred_fills=[
            InferredFill(
                order_id=order.id,
                symbol="AAPL",
                side=OrderSide.SELL,
                quantity=100,
                price=9.95,
                source_fill_id="exec-1",
            )
        ]
    )
    await _apply_inferred_fills(any_store, plan)

    # The clean exit landed exactly once...
    assert (await any_store.get_envelope(env.id)).remaining_quantity == 0
    assert (await any_store.get_position("AAPL")).quantity == 0
    # ...and NO phantom overfill was fabricated on the reconcile path.
    events = await any_store.list_events(event_type="fill_overfill_quarantined")
    assert events == [], (
        "clean reconcile-recovered exit fabricated fill_overfill_quarantined"
    )
    assert await any_store.list_quarantined_symbols() == set()


async def test_F3_real_overfill_still_quarantines(any_store):
    # The self-derivation must NOT weaken ADR-001: a genuine broker overfill
    # (sell exceeding the held position, DISTINCT execution id — no dedupe)
    # still records + quarantines.
    from app.position import NegativePositionError  # noqa: F401 (import guard)

    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 50, session_id=session.id
    )
    await any_store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 50, 10.0, session_id=session.id
    )
    sell = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.SELL, 80, session_id=session.id
    )
    await any_store.append_fill(
        sell.id,
        "AAPL",
        OrderSide.SELL,
        80,
        9.9,
        source_fill_id="over-1",
        session_id=session.id,
    )
    events = await any_store.list_events(event_type="fill_overfill_quarantined")
    assert len(events) == 1
    assert "AAPL" in await any_store.list_quarantined_symbols()


# ------------------------------------------------------------------------- #
# F1 — the deterministic tick's terminal transitions and fill folds carry the
# injected clock (transition_envelope / record_envelope_fill gain now=)
# ------------------------------------------------------------------------- #
async def test_F1_transition_envelope_stamps_injected_clock(any_store):
    await any_store.initialize()
    env = await _active_envelope(any_store)
    stamp = T_NOW + timedelta(minutes=7)
    await any_store.transition_envelope(
        env.id, EnvelopeStatus.FROZEN, actor="engine", reason="test", now=stamp
    )
    ev = [
        e
        for e in await any_store.get_execution_events()
        if e.envelope_id == env.id
        and e.event_type is ExecutionEventType.ENVELOPE_FROZEN
    ]
    assert ev and ev[-1].ts_event == stamp, (
        f"FROZEN event ts {ev[-1].ts_event if ev else None} != injected {stamp}"
    )


async def test_F1_record_envelope_fill_stamps_injected_clock(any_store):
    await any_store.initialize()
    env = await _active_envelope(any_store)
    stamp = T_NOW + timedelta(minutes=9)
    await any_store.record_envelope_fill(
        env.id, quantity=10, dedupe_key="fill:oX:c1", price=9.9, now=stamp
    )
    ev = [
        e
        for e in await any_store.get_execution_events()
        if e.envelope_id == env.id and e.event_type is ExecutionEventType.FILL
    ]
    assert ev and ev[-1].ts_event == stamp


# ------------------------------------------------------------------------- #
# S1 — a broker-authoritative rejection reason is recorded, never hidden
# ------------------------------------------------------------------------- #
async def test_S1_terminal_broker_rejection_reason_is_durably_evented(any_store):
    from app.broker.adapter import TerminalBrokerError
    from app.reconciliation import ENVELOPE_EXEC_REJECTED, execute_envelope_action

    await any_store.initialize()
    env = await _active_envelope(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(TerminalBrokerError("pdt_restriction: account flagged"))
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        _planned(quantity=10),
        snapshot_fingerprint="fp",
        now=T_NOW + timedelta(seconds=30),
    )
    assert result.outcome == ENVELOPE_EXEC_REJECTED
    events = await any_store.list_events(event_type="envelope_venue_rejected")
    assert events, "broker rejection reason never reached the durable log"
    assert "pdt_restriction" in (events[-1].payload or {}).get("detail", "")
