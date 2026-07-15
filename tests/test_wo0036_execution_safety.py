"""WO-0036 — envelope execution safety (Codex PR #8 review + AUDIT-0001 roots).

RED→GREEN regressions for the 8 findings. Grouped by finding id (Codex #N).
All gated surfaces (order submission / cancel / flatten / event-log truth) —
approved by Ameen 2026-07-15 ("Approve expanded WO-0036 — implement all 8").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
)

pytestmark = pytest.mark.anyio

T = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def _action(order_id: str, action: str, at: datetime, **payload) -> ExecutionEvent:
    return ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=at,
        symbol="AAPL",
        order_id=order_id,
        envelope_id="env-1",
        payload={"action": action, **payload},
    )


def _terminal(order_id: str, event_type: ExecutionEventType, at: datetime):
    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=at,
        symbol="AAPL",
        order_id=order_id,
        payload={},
    )


# ------------------------------------------------------------------------- #
# Codex #6 (P1) — the working-order predicate must not lose a still-live
# PREDECESSOR when a newer reprice replacement goes terminal without cancelling
# it. It used to inspect only the newest action -> returned None once that was
# terminal -> policy plans a fresh SUBMIT while the predecessor is live at the
# venue -> the store refuses it as stale (max-1-outstanding) -> envelope stuck.
# ------------------------------------------------------------------------- #
def test_c6_live_working_order_tracks_predecessor_after_rejected_reprice():
    from app.sellside.policy import _live_working_order_id

    # Order A submitted (live), then a reprice mints B; B is REJECTED at the
    # venue (the atomic replace failed) so A was never cancelled — A is LIVE.
    actions = [
        _action("A", "submit", T - timedelta(seconds=120)),
        _action("B", "reprice", T - timedelta(seconds=60)),
    ]
    history = actions + [
        _terminal("B", ExecutionEventType.REJECTED, T - timedelta(seconds=30)),
    ]
    assert _live_working_order_id(actions, history) == "A", (
        "predecessor A is still live at the venue but the predicate dropped it "
        "when replacement B went terminal"
    )


def test_c6_successful_reprice_returns_the_live_replacement():
    from app.sellside.policy import _live_working_order_id

    # Normal reprice: B goes live, A is CANCELED by the atomic replace.
    actions = [
        _action("A", "submit", T - timedelta(seconds=120)),
        _action("B", "reprice", T - timedelta(seconds=60)),
    ]
    history = actions + [
        _terminal("A", ExecutionEventType.CANCELED, T - timedelta(seconds=59)),
    ]
    assert _live_working_order_id(actions, history) == "B"


def test_c6_all_terminal_returns_none():
    from app.sellside.policy import _live_working_order_id

    actions = [_action("A", "submit", T - timedelta(seconds=120))]
    history = actions + [_terminal("A", ExecutionEventType.FILLED, T)]
    assert _live_working_order_id(actions, history) is None


# ------------------------------------------------------------------------- #
# Store-backed helpers for the monitoring/store findings (#1, #7).
# ------------------------------------------------------------------------- #

from app.broker.mock import MockBrokerAdapter  # noqa: E402
from app.models import (  # noqa: E402
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction  # noqa: E402

FP = "fp-wo0036"


def _draft(intent_id: str, **ov) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol="AAPL",
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


async def _active_env(store):
    await store.initialize()
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return await store.approve_envelope_activation(_draft(si.id), actor="op")


# Codex #1 (P1) — the generic submit sweep must SKIP envelope-minted orders.
async def test_c1_generic_sweep_skips_envelope_minted_orders(any_store):
    from app.monitoring import _submit_pending_orders

    env = await _active_env(any_store)
    # Stage a SUBMIT: mints a CREATED envelope order (no venue call).
    staged = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, now=T
    )
    order_id = staged.order.id
    assert (await any_store.get_order(order_id)).status is OrderStatus.CREATED

    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)

    # The envelope order must NOT be generically submitted — only the envelope
    # executor's redrive drives it (else a released reprice double-books).
    assert order_id not in [o.id for o in adapter.submitted], (
        "generic sweep submitted an envelope-minted order, bypassing redrive"
    )
    assert (await any_store.get_order(order_id)).status is OrderStatus.CREATED


# Codex PR#8 round-2 F1 (P1) — the SUBMITTING-redrive sibling of #1. A crash
# between the envelope claim and `replace_order` leaves the reprice replacement
# SUBMITTING+idless; the generic stale-SUBMITTING recovery must NOT blind
# `submit_order` it (that mints a SECOND live SELL beside the still-working
# predecessor, because the atomic replace's venue cancel never ran). Envelope
# orders route to TIMEOUT_QUARANTINE for ADR-002 targeted reconciliation — the
# venue's atomic replace makes that resolution consistent (A and B are never
# both live at the venue; only a blind submit could create that).
async def test_c1b_stale_submitting_redrive_skips_envelope_orders(any_store):
    from app.config import Settings
    from app.monitoring import _redrive_stale_submitting

    env = await _active_env(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, now=T
    )
    order_id = staged.order.id
    # The crash window: the claim moves CREATED -> SUBMITTING durably, but the
    # broker call never persisted a broker_order_id.
    await any_store.claim_order_for_submission(order_id)
    o = await any_store.get_order(order_id)
    assert o.status is OrderStatus.SUBMITTING and not o.broker_order_id

    adapter = MockBrokerAdapter()
    await _redrive_stale_submitting(any_store, adapter, Settings(), market_data=None)

    assert order_id not in [o.id for o in adapter.submitted], (
        "stale-submitting redrive blind-submitted an envelope order (double-book)"
    )
    assert (
        await any_store.get_order(order_id)
    ).status is OrderStatus.TIMEOUT_QUARANTINE, (
        "crash-stranded envelope order was not routed to targeted reconciliation"
    )


# Codex PR#8 round-2 F3 (P2), sqlite-specific (memory already returns on NOOP
# before any session work) — a NOOP ACTIVE->ACTIVE transition must NOT call the
# session bootstrap. The sqlite twin ran `_ensure_current_session_locked` before
# the in-tx NOOP early-return, so on a DATE ROLLOVER (today has no session yet)
# an idempotent re-activation minted a spurious session/`session_opened`. Forced
# here by ageing the current session's date so today has none.
async def test_c_f3_noop_active_transition_does_not_mint_a_session_on_rollover(
    tmp_path,
):
    from app.models import EnvelopeStatus
    from app.store.sqlite import SqliteStateStore

    store = SqliteStateStore(tmp_path / "f3.db")
    try:
        env = await _active_env(store)  # initialize + ACTIVE envelope (today)
        # Rollover: age the only session so `today` has none -> the buggy
        # bootstrap WOULD mint a fresh session on the NOOP.
        store._conn.execute("UPDATE sessions SET session_date = '2000-01-01'")
        store._conn.commit()
        before = len(await store.list_sessions())
        out = await store.transition_envelope(
            env.id, EnvelopeStatus.ACTIVE, actor="op"
        )
        assert out.status is EnvelopeStatus.ACTIVE  # idempotent NOOP
        assert len(await store.list_sessions()) == before, (
            "NOOP ACTIVE minted a session on a date rollover (parity break)"
        )
    finally:
        if store._conn is not None:
            store._conn.close()
            store._conn = None


# Codex #7 (P2) — reconciliation-inferred envelope fills must carry SYNTHETIC/
# RECONCILIATION provenance on the sole durable FILL event (the record-first
# bridge writes it; append_fill's shadow dedupes to it), not the broker default.
async def test_c7_inferred_envelope_fill_keeps_synthetic_provenance(any_store):
    from app.models import EventAuthority, EventSource, ExecutionEventType
    from app.monitoring import _apply_inferred_fills
    from app.reconciliation import InferredFill, ReconciliationPlan

    env = await _active_env(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, _planned(), snapshot_fingerprint=FP, now=T
    )
    order_id = staged.order.id

    plan = ReconciliationPlan(
        inferred_fills=[
            InferredFill(
                order_id=order_id,
                symbol="AAPL",
                side=OrderSide.SELL,
                quantity=10,
                price=9.9,
                source_fill_id="x1",
            )
        ]
    )
    await _apply_inferred_fills(any_store, plan)

    fills = [
        e
        for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.FILL and e.envelope_id == env.id
    ]
    assert len(fills) == 1, fills
    assert fills[0].authority is EventAuthority.SYNTHETIC, (
        f"inferred fill mis-stamped as {fills[0].authority}"
    )
    assert fills[0].source is EventSource.RECONCILIATION


# Codex #5 (P1) — cancelling a FROZEN envelope with a LIVE child must be refused.
async def test_c5_cancel_frozen_with_live_child_refused(any_store):
    from app.reconciliation import ENVELOPE_EXEC_SUBMITTED, execute_envelope_action
    from app.models import EnvelopeStatus
    from app.store.base import EnvelopeTransitionError

    env = await _active_env(any_store)
    adapter = MockBrokerAdapter()
    r = await execute_envelope_action(
        any_store, adapter, env.id, _planned(), snapshot_fingerprint=FP, now=T
    )
    assert r.outcome == ENVELOPE_EXEC_SUBMITTED  # child now live at the venue
    await any_store.transition_envelope(env.id, EnvelopeStatus.FROZEN, actor="op")

    with pytest.raises(EnvelopeTransitionError, match="live at the venue"):
        await any_store.transition_envelope(
            env.id, EnvelopeStatus.CANCELLED, actor="op"
        )
    # Untouched: still FROZEN, child still live.
    assert (await any_store.get_envelope(env.id)).status is EnvelopeStatus.FROZEN


async def test_c5_cancel_frozen_without_live_child_allowed(any_store):
    # A FROZEN envelope whose only child is terminal (or none) still cancels.
    from app.models import EnvelopeStatus

    env = await _active_env(any_store)
    await any_store.transition_envelope(env.id, EnvelopeStatus.FROZEN, actor="op")
    out = await any_store.transition_envelope(
        env.id, EnvelopeStatus.CANCELLED, actor="op"
    )
    assert out.status is EnvelopeStatus.CANCELLED


# Codex #3 (P1, R6) — a transient cancel failure on an EXPIRED CANCEL_AND_RETURN
# envelope must be re-driven to convergence, not stranded live forever.
async def test_c3_expired_cancel_converges_after_transient_failure(any_store):
    from app.reconciliation import ENVELOPE_EXEC_SUBMITTED, execute_envelope_action
    from app.models import EnvelopeStatus, OrderStatus
    from app.monitoring import _converge_expired_envelope_cancels

    env = await _active_env(any_store)
    adapter = MockBrokerAdapter()
    r = await execute_envelope_action(
        any_store, adapter, env.id, _planned(), snapshot_fingerprint=FP, now=T
    )
    assert r.outcome == ENVELOPE_EXEC_SUBMITTED
    order_id = r.order_id

    # Post-transient-failure state: envelope EXPIRED (CANCEL_AND_RETURN default),
    # working order STILL live at the venue (the one-shot cancel raised).
    await any_store.transition_envelope(env.id, EnvelopeStatus.EXPIRED, actor="op")
    assert (await any_store.get_order(order_id)).status is OrderStatus.SUBMITTED

    # The convergence arm (working adapter now) re-drives the cancel.
    await _converge_expired_envelope_cancels(any_store, MockBrokerAdapter())
    assert (await any_store.get_order(order_id)).status is OrderStatus.CANCEL_PENDING, (
        "expired-envelope working order was left live — cancel never re-driven"
    )
