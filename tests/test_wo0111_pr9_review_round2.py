"""WO-0111 — the two round-2 P1 findings from the PR #9 Codex review.

Both are correctness twins the round-3 (WO-0109) diff-scoped review did not reach,
exercised through ``any_store`` so memory and SQLite carry identical behavior.
Each pin is red on the pre-fix tree and mutation-verified in the commit.

Finding 1 — monitoring's single-envelope lineage projection is fed owner-scoped
sibling actions. After a legitimate supersession (predecessor -> successor, same
sell_intent), the predecessor's own ENVELOPE_ACTION (it carries the shared intent
as ``correlation_id``) is pulled into ``project_envelope_obligation(envelopes=
[successor])`` and, since the predecessor is not in that one-element set, flagged a
"missing envelope" — so ``_envelope_id_for_order`` disowns the successor's real
order and its fills would skip ``record_envelope_fill`` (the successor envelope
never decrements / COMPLETES).

Finding 2 — the emergency-reduce override grant wedges the operator's retry. The
grant is consumed only on an authorized create/existing/flat flatten outcome; the
store's WO-0108/REV-0029 hardening makes the flatten fail closed (409) whenever a
venue-uncertain BUY remains, leaving the grant ACTIVE and un-consumed. The
documented "retry after reconciliation" then hit "an override is already active".
Re-authorizing must REUSE the still-active grant (idempotent, never stacked).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.monitoring import _envelope_id_for_order
from app.reconciliation import (
    ENVELOPE_EXEC_RELEASED,
    ENVELOPE_EXEC_SUBMITTED,
    execute_envelope_action,
)
from app.sellside.types import ActionKind, PlannedAction

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc)
FP = "fp-wo0111"


def _later(seconds: int = 30) -> datetime:
    return _NOW + timedelta(seconds=seconds)


def _draft(intent_id: str, *, session_id, symbol: str = "AAPL", **overrides):
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
        expires_at=_NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def _planned(kind=ActionKind.SUBMIT, limit_price=9.90, quantity=10) -> PlannedAction:
    return PlannedAction(
        kind=kind,
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


async def _hold(store, *, symbol: str = "AAPL", qty: int = 100):
    await store.initialize()
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, 10.0, session_id=session.id
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    return session


# --------------------------------------------------------------------------- #
# Finding 1 — a superseded predecessor must not disown the successor's order
# --------------------------------------------------------------------------- #
async def test_finding1_supersession_successor_order_is_attributed(any_store):
    session = await _hold(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )

    # Predecessor envelope stages a child that FAILS to submit -> RELEASED (a
    # staged CREATED, swept by the supersession). This leaves a persisted
    # ENVELOPE_ACTION whose correlation_id is the shared intent — exactly the
    # owner-scoped identity monitoring's lineage discovery keys on.
    predecessor = await any_store.approve_envelope_activation(
        _draft(intent.id, session_id=session.id), actor="operator-a"
    )
    failing = MockBrokerAdapter()
    failing.fail_next_submit(BrokerError("transient"))
    released = await execute_envelope_action(
        any_store,
        failing,
        predecessor.id,
        _planned(),
        snapshot_fingerprint=FP,
        now=_later(),
    )
    assert released.outcome == ENVELOPE_EXEC_RELEASED

    # Legitimate supersession: same intent, predecessor -> SUPERSEDED, successor ACTIVE.
    successor = await any_store.supersede_envelope(
        predecessor.id,
        _draft(intent.id, session_id=session.id, qty_ceiling=100),
        actor="operator-a",
        reason="amendment",
    )
    assert (
        await any_store.get_envelope(predecessor.id)
    ).status is EnvelopeStatus.SUPERSEDED
    assert (await any_store.get_envelope(successor.id)).status is EnvelopeStatus.ACTIVE

    # The successor stages its own child and rests it at the venue.
    submitted = await execute_envelope_action(
        any_store,
        MockBrokerAdapter(),
        successor.id,
        _planned(),
        snapshot_fingerprint=FP,
        now=_later(120),
    )
    assert submitted.outcome == ENVELOPE_EXEC_SUBMITTED

    # Monitoring must attribute the successor's order to the SUCCESSOR envelope.
    # Pre-fix: the predecessor's owner-scoped action pollutes the one-element
    # projection, flags the predecessor "missing", and this returns None — so the
    # successor's fills would silently skip record_envelope_fill.
    resolved = await _envelope_id_for_order(any_store, submitted.order_id)
    assert resolved == successor.id, (
        "monitoring disowned the successor's own order after a legitimate "
        f"supersession (got {resolved!r}); its fills would skip record_envelope_fill"
    )


# --------------------------------------------------------------------------- #
# Finding 2 — an active emergency-reduce grant is REUSED by the retry, not refused
# --------------------------------------------------------------------------- #
async def test_finding2_reauthorize_reuses_active_grant_without_stacking(any_store):
    # The grant authorizes exactly one reduce-only exit and is consumed by it. But
    # the store's hardening makes the flatten fail closed (409) while a venue-
    # uncertain BUY remains, leaving the grant ACTIVE and un-consumed. The
    # operator's documented "retry after reconciliation" must REUSE that grant.
    session = await _hold(any_store)
    await any_store.set_kill_switch(True)  # -> HALTED
    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    assert await any_store.list_emergency_reduce_overrides() == {"AAPL"}

    # The retry must NOT wedge on "an override is already active" (pre-fix: raises).
    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
    # Exactly one grant — reused, never stacked.
    assert await any_store.list_emergency_reduce_overrides() == {"AAPL"}

    # And a single flatten still consumes the one grant (no leak, no double exit).
    result = await any_store.flatten_position("AAPL", actor="op")
    assert result.intent is not None
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert await any_store.list_emergency_reduce_overrides() == set()
    del session
