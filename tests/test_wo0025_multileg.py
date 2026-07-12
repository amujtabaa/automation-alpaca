"""WO-0025 — multi-leg envelope lifecycle (REV-0023 F4) + inferred-fill
bridge (F5), remediated together by necessity: F4's freeze masked F5's venue
leg, so fixing the livelock alone would have armed the oversell.

F4: decide()'s "working order" predicate is now LIVE-order-derived (from the
event log — FILLED/CANCELED/REJECTED terminals kill it), unified with the
write-time structural check. The old predicate ("any submit EVER") froze
every envelope's second leg with a false ENVELOPE_PLAN_DIVERGENCE.

F5: reconciliation-inferred fills route through record_envelope_fill FIRST
with the canonical dedupe key, exactly like the stream bridge — the
human-approved ceiling can no longer silently re-arm.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.broker.mock import MockBrokerAdapter
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.reconciliation import (
    ENVELOPE_EXEC_SUBMITTED,
    InferredFill,
    execute_envelope_action,
)
from app.sellside.policy import _live_working_order_id, decide
from app.sellside.types import PlannedAction

import app.monitoring as monitoring

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
T0 = datetime(2026, 7, 15, 13, 0, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def make_draft(intent_id: str, **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=8.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.5,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=10,
        expires_at=NOW + timedelta(days=2),
        allowed_session_phases=list(SessionType),
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        status=EnvelopeStatus.ACTIVE,
        activated_at=T0,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


async def seeded_envelope(store, **overrides) -> ExecutionEnvelope:
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
    draft = make_draft(si.id, **overrides)
    draft = draft.model_copy(update={"status": EnvelopeStatus.PENDING})
    return await store.approve_envelope_activation(draft, actor="operator-a")


def _action_event(order_id: str, action: str = "submit", tranche=False, seq=1):
    return ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL",
        order_id=order_id,
        envelope_id="env-1",
        payload={"action": action, "tranche": tranche, "quantity": 50},
        sequence=seq,
    )


def _order_event(order_id: str, event_type: ExecutionEventType, seq=2):
    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL",
        order_id=order_id,
        payload={},
        sequence=seq,
    )


# ================================================================== #
# F4 — the predicate, unit level (each terminal kills the working id)
# ================================================================== #


def test_predicate_no_actions_means_no_working_order():
    assert _live_working_order_id([], []) is None


def test_predicate_submit_without_terminal_is_live():
    a = _action_event("o1")
    assert _live_working_order_id([a], [a]) == "o1"


@pytest.mark.parametrize(
    "terminal",
    [
        ExecutionEventType.FILLED,
        ExecutionEventType.CANCELED,
        ExecutionEventType.REJECTED,
    ],
)
def test_predicate_each_terminal_kills_the_working_order(terminal):
    """A filled tranche, a disposition-cancelled order, and a venue-rejected
    order are all DEAD — the next leg must be a fresh SUBMIT, never a REPRICE
    of a corpse (the F4 livelock)."""

    a = _action_event("o1", tranche=True)
    t = _order_event("o1", terminal)
    assert _live_working_order_id([a], [a, t]) is None


def test_predicate_tracks_the_newest_reprice_chain():
    """After a reprice, the OLD order's terminal must not kill the NEW
    working order — liveness follows the newest action's order id."""

    a1 = _action_event("o1", "submit", seq=1)
    old_dead = _order_event("o1", ExecutionEventType.CANCELED, seq=3)
    a2 = _action_event("o2", "reprice", seq=2)
    history = [a1, a2, old_dead]
    assert _live_working_order_id([a1, a2], history) == "o2"
    # ...and a terminal on the NEW order kills it.
    new_dead = _order_event("o2", ExecutionEventType.FILLED, seq=4)
    assert _live_working_order_id([a1, a2], history + [new_dead]) is None


# ================================================================== #
# F4 — decide→stage integration: the second leg goes through (both stores)
# ================================================================== #


async def test_second_leg_after_terminal_first_order_submits_fresh(any_store):
    """The FLIPPED PIN_F4 shape, end-to-end through the REAL decide():
    leg 1 (stop exit) submits, partially fills, and the venue cancels the
    remainder (terminal). The next decide must plan a fresh SUBMIT — not a
    REPRICE of the dead order — and the seam must stage it with ZERO
    divergence events. Before WO-0025 this froze every multi-order envelope."""

    import tests.test_wo0020_envelope_tick as T20

    env = await seeded_envelope(any_store)
    adapter = MockBrokerAdapter()
    tape = T20.crash_tape()

    async def history():
        events = await any_store.get_execution_events()
        own = {
            e.order_id
            for e in events
            if e.envelope_id == env.id and e.order_id is not None
        }
        return [
            e
            for e in events
            if e.envelope_id == env.id or (e.order_id is not None and e.order_id in own)
        ]

    # Leg 1: the real policy sees the breakdown and plans the stop exit.
    d1 = decide(env, tape, now=NOW, history=await history())
    assert isinstance(d1, PlannedAction)
    r1 = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        d1,
        snapshot_fingerprint="fp-1",
        now=NOW,
    )
    assert r1.outcome == ENVELOPE_EXEC_SUBMITTED

    # Venue: 40 shares fill, remainder cancelled (terminal first order).
    await any_store.record_envelope_fill(
        env.id,
        quantity=40,
        dedupe_key=f"fill:{r1.order_id}:x1",
        order_id=r1.order_id,
        price=9.60,
    )
    await any_store.append_fill(
        r1.order_id, "AAPL", OrderSide.SELL, 40, 9.60, source_fill_id="x1"
    )
    await any_store.transition_order(
        r1.order_id, OrderStatus.CANCELED, filled_quantity=40
    )

    env2 = await any_store.get_envelope(env.id)
    assert env2.status is S.ACTIVE and env2.remaining_quantity == 60

    # Leg 2: fresh SUBMIT (not REPRICE), staged and venue-submitted cleanly.
    now2 = NOW + timedelta(seconds=60)
    d2 = decide(env2, tape, now=now2, history=await history())
    assert isinstance(d2, PlannedAction), f"expected a plan, got {d2}"
    from app.sellside.types import ActionKind

    assert d2.kind is ActionKind.SUBMIT  # the dead order is not repriced
    r2 = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        d2,
        snapshot_fingerprint="fp-2",
        now=now2,
    )
    assert r2.outcome == ENVELOPE_EXEC_SUBMITTED

    final = await any_store.get_envelope(env.id)
    assert final.status is S.ACTIVE  # never frozen
    divergences = [
        e
        for e in await any_store.get_execution_events()
        if e.envelope_id == env.id
        and e.event_type is ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE
    ]
    assert divergences == []  # the tripwire kept its meaning
    sells = [o for o in adapter.submitted if o.side is OrderSide.SELL]
    assert len(sells) == 2


# ================================================================== #
# F5 — inferred fills reach the envelope through the REAL monitoring bridge
# ================================================================== #


async def test_inferred_fill_bridge_decrements_envelope(any_store):
    """The FLIPPED PIN_F5 shape, through monitoring._apply_inferred_fills
    itself: a reconcile-inferred fill on an envelope-minted order decrements
    remaining (record-first, canonical dedupe key) — the ceiling never
    re-arms. A later stream observation of the SAME execution dedupes to one."""

    env = await seeded_envelope(any_store)
    adapter = MockBrokerAdapter()
    import tests.test_wo0020_envelope_tick as T20

    d1 = decide(
        env,
        T20.crash_tape(),
        now=NOW,
        history=[],
    )
    assert isinstance(d1, PlannedAction)
    r1 = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        d1,
        snapshot_fingerprint="fp-1",
        now=NOW,
    )
    assert r1.outcome == ENVELOPE_EXEC_SUBMITTED
    staged = await any_store.get_order(r1.order_id)

    plan = SimpleNamespace(
        inferred_fills=[
            InferredFill(
                order_id=staged.id,
                symbol="AAPL",
                side=OrderSide.SELL,
                quantity=staged.quantity,
                price=9.60,
                source_fill_id="venue-exec-1",
            )
        ]
    )
    await monitoring._apply_inferred_fills(any_store, plan)

    env2 = await any_store.get_envelope(env.id)
    assert (env2.remaining_quantity or 0) == 100 - staged.quantity, (
        "the envelope never learned about the inferred fill — the mandate "
        "re-armed (REV-0023 F5)"
    )
    # Replay of the SAME execution (stream catches up): exactly-once.
    await any_store.record_envelope_fill(
        env.id,
        quantity=staged.quantity,
        dedupe_key=f"fill:{staged.id}:venue-exec-1",
        order_id=staged.id,
        price=9.60,
    )
    env3 = await any_store.get_envelope(env.id)
    assert env3.remaining_quantity == env2.remaining_quantity
    fills = [
        e
        for e in await any_store.get_execution_events()
        if e.envelope_id == env.id and e.event_type is ExecutionEventType.FILL
    ]
    assert len(fills) == 1
