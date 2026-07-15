"""WO-0021 — stack-level chaos catalog: races, budget exhaustion, dispositions
and data-quality injections against the ASSEMBLED envelope stack
(WO-0016..0020), both stores. Tests only — failures become FINDINGs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import app.monitoring as monitoring
from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.monitoring import EnvelopeTapeBuffer
from app.reconciliation import (
    ENVELOPE_EXEC_RELEASED,
    execute_envelope_action,
    redrive_staged_envelope_action,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import OrderIntentBlockedError
from app.store.core import STAGE_DIVERGENCE
from tests.store_helpers import activate_envelope_at

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
FP = "fp-chaos"


def later(seconds: float = 30.0) -> datetime:
    # NOW-based (not wall clock): validate_action rails on TTL + session
    # phase since WO-0024, and the container may sit on a weekend.
    return NOW + timedelta(seconds=seconds)


def make_draft(intent_id: str, symbol: str = "AAPL", **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=100,
        floor_price=8.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.5,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=2,
        # Past BOTH clocks in play: the wall clock (staging paths use
        # later()) and the deterministic decision clock NOW (Jul 15).
        expires_at=NOW + timedelta(days=2),
        allowed_session_phases=list(SessionType),
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def planned(kind=ActionKind.SUBMIT, limit_price=9.90, quantity=10) -> PlannedAction:
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


async def active_envelope(store, **overrides) -> ExecutionEnvelope:
    await store.initialize()
    # WO-0026: staging rails on the live position (reduce-only).
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )
    si = await store.create_sell_intent(
        symbol=overrides.get("symbol", "AAPL"),
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
    )
    # Injected activation clock, anchored BEFORE the NOW-anchored tapes: the
    # policy's since-activation window (INV-086) must contain the tape rows
    # regardless of wall-clock time of day (see activate_envelope_at).
    return await activate_envelope_at(
        store, make_draft(si.id, **overrides), now=NOW - timedelta(hours=1)
    )


# --- partial-fill / race interleavings -------------------------------------------- #


async def test_partial_fill_between_plan_and_write_hits_the_qty_rail(any_store):
    """The policy planned against remaining=100; a 60-share fill lands before
    the write. The WRITE-TIME rail (D-3) rejects the now-oversized action —
    divergence, frozen, zero venue calls."""

    env = await active_envelope(any_store)
    stale_view_action = planned(quantity=80)  # valid when planned...
    await any_store.record_envelope_fill(
        env.id, quantity=60, dedupe_key="fill:o0:race", order_id="o0", price=9.9
    )  # ...then the fill lands (remaining 40)

    adapter = MockBrokerAdapter()
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        stale_view_action,
        snapshot_fingerprint=FP,
        now=later(),
    )
    # WO-0029A (ADR-010 §5 amendment accepted 2026-07-12): a benign fill
    # racing the plan is NOT a software defect — refused + evented, zero
    # venue calls, envelope stays ACTIVE and replans next tick. (This test
    # is the case SPEC-09 cited when it falsified the old §5 claim.)
    assert result.outcome == "refused_stale"
    assert adapter.submitted == [] and adapter.replaced == []
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE


async def test_replayed_fill_on_the_replace_leg_never_double_counts(any_store):
    """Fill/cancel-ack race on a replace: the SAME venue fill observed before
    AND after the replace decrements the envelope exactly once (deduped fill
    events are the only quantity writers)."""

    env = await active_envelope(any_store)
    first = await any_store.record_envelope_fill(
        env.id, quantity=30, dedupe_key="fill:oX:exec1", order_id="oX", price=9.9
    )
    assert first.remaining_quantity == 70
    replay = await any_store.record_envelope_fill(
        env.id, quantity=30, dedupe_key="fill:oX:exec1", order_id="oX", price=9.9
    )
    assert replay.remaining_quantity == 70  # exactly once
    fills = [
        e
        for e in await any_store.get_execution_events()
        if e.envelope_id == env.id and e.event_type is ExecutionEventType.FILL
    ]
    assert len(fills) == 1


async def test_kill_between_snapshot_read_and_action_write(any_store):
    """REV-0020 shape, envelope edition: the decision was computed against a
    snapshot; the kill lands BEFORE the write. Zero artifacts."""

    env = await active_envelope(any_store)
    decision = planned()  # 'computed' before the kill
    await any_store.set_kill_switch(True, actor="operator-a")
    adapter = MockBrokerAdapter()
    with pytest.raises(OrderIntentBlockedError):
        await execute_envelope_action(
            any_store,
            adapter,
            env.id,
            decision,
            snapshot_fingerprint=FP,
            now=later(),
        )
    assert adapter.submitted == [] and adapter.replaced == []
    assert [
        e
        for e in await any_store.get_execution_events()
        if e.envelope_id == env.id
        and e.event_type is ExecutionEventType.ENVELOPE_ACTION
    ] == []


async def test_flatten_mid_reprice_staged_order_never_reaches_the_venue(any_store):
    # FLIPPED GREEN by WO-0024 (was the strict-xfail P1 finding pin:
    # FINDING-W3-staged-order-outlives-preemption).
    """Flatten preemption vs an in-flight STAGED (CREATED, unexecuted) action:
    after the flatten cancels the envelope, the staged order must never
    submit — not even through the redrive path."""

    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await any_store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    # Injected activation clock before the tape (see activate_envelope_at).
    env = await activate_envelope_at(
        any_store, make_draft(si.id), now=NOW - timedelta(hours=1)
    )

    # Stage without executing (the mid-reprice window: transient release).
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    released = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    assert released.outcome == ENVELOPE_EXEC_RELEASED
    staged_order = await any_store.get_order(released.order_id)
    assert staged_order.status is OrderStatus.CREATED

    # The human flattens: envelope preempted (cancelled) before the flatten
    # proceeds (INV-081).
    await any_store.flatten_position("AAPL", actor="operator-ameen")
    assert (await any_store.get_envelope(env.id)).status is S.CANCELLED

    # The staged order of a CANCELLED envelope must be dead: a redrive makes
    # ZERO venue calls and the order never leaves CREATED via this path.
    # WO-0024: the flatten's preemption sweep already cancelled the staged
    # order in the SAME atomic unit; the redrive finds nothing to drive.
    fresh_adapter = MockBrokerAdapter()
    redriven = await redrive_staged_envelope_action(
        any_store, fresh_adapter, env.id, now=later(60)
    )
    assert redriven is None
    assert fresh_adapter.submitted == [] and fresh_adapter.replaced == [], (
        "a cancelled envelope's staged order reached the venue"
    )
    final = await any_store.get_order(released.order_id)
    assert final.status is OrderStatus.CANCELED  # swept with the preemption
    # Ordering: envelope cancellation sequences BEFORE its staged order's
    # cancel, both BEFORE any flatten dispatch events (same atomic unit).
    events = await any_store.get_execution_events()
    env_cancel_seq = next(
        e.sequence
        for e in events
        if e.envelope_id == env.id
        and e.event_type is ExecutionEventType.ENVELOPE_CANCELLED
    )
    order_cancel_seq = next(
        e.sequence
        for e in events
        if e.order_id == released.order_id
        and e.event_type is ExecutionEventType.CANCELED
    )
    assert env_cancel_seq < order_cancel_seq


# --- time & session edges ----------------------------------------------------------- #


async def test_ttl_rest_at_floor_leaves_the_working_order_resting(any_store):
    env = await active_envelope(
        any_store, expiry_disposition=EnvelopeExpiryDisposition.REST_AT_FLOOR
    )
    adapter = MockBrokerAdapter()
    submitted = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    md = FakeMarketDataFeed()
    md.set_snapshot("AAPL", last_price=9.7, bid=9.69, ask=9.71, volume=1000.0)
    tapes = EnvelopeTapeBuffer()
    await monitoring._run_envelopes(
        any_store,
        adapter,
        md,
        Settings(protection_enabled=False),
        tapes=tapes,
        now=env.expires_at + timedelta(seconds=1),
    )
    assert (await any_store.get_envelope(env.id)).status is S.EXPIRED
    order = await any_store.get_order(submitted.order_id)
    assert order.status is OrderStatus.SUBMITTED  # deliberately left resting
    assert adapter.canceled == []


async def test_phase_flip_outside_allowed_set_is_no_action_pinned(any_store):
    """Outside the allowed phase set the policy holds (NoAction). PINS the
    current contract: NO disposition executes on a phase exit — only TTL and
    stale-data have dispositions (ADR-010 §2). Recorded as a spec observation
    for the wave review (the WO-0021 catalog wording assumed one)."""

    env = await active_envelope(
        any_store, allowed_session_phases=[SessionType.PRE_MARKET]
    )
    adapter = MockBrokerAdapter()
    md = FakeMarketDataFeed()
    md.set_snapshot("AAPL", last_price=9.7, bid=9.69, ask=9.71, volume=1000.0)
    await monitoring._run_envelopes(
        any_store,
        adapter,
        md,
        Settings(protection_enabled=False),
        tapes=EnvelopeTapeBuffer(),
        now=NOW,  # regular hours — outside the envelope's allowed set
    )
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE
    assert adapter.submitted == [] and adapter.canceled == []


# --- data quality (stack pass-through) ------------------------------------------------ #


@pytest.mark.parametrize(
    "bad",
    [
        dict(last_price=float("nan")),
        dict(last_price=-1.0),
        dict(bid=None),
        dict(bid=10.05, ask=10.01),  # crossed
        dict(volume=-5.0),
        dict(stale=True),
    ],
)
async def test_bad_data_classes_never_reach_the_venue(any_store, bad):
    env = await active_envelope(
        any_store,
        stale_data_disposition=EnvelopeStaleDataDisposition.LEAVE_RESTING,
    )
    adapter = MockBrokerAdapter()
    md = FakeMarketDataFeed()
    fields = dict(last_price=9.7, bid=9.69, ask=9.71, volume=1000.0)
    fields.update(bad)
    md.set_snapshot("AAPL", **fields)
    await monitoring._run_envelopes(
        any_store,
        adapter,
        md,
        Settings(protection_enabled=False),
        tapes=EnvelopeTapeBuffer(),
        now=NOW,
    )
    assert adapter.submitted == [] and adapter.replaced == []
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE


# --- budget / exhaustion ---------------------------------------------------------------- #


async def test_budget_drain_exhausts_and_survives_restart(tmp_path):
    """A volatile tape drains the replace budget ⇒ EXHAUSTED, no further venue
    calls — and a crash-restart CANNOT reset the budget (the accounting is the
    durable event log)."""

    from app.store.sqlite import SqliteStateStore

    store = SqliteStateStore(tmp_path / "budget.db")
    env = await active_envelope(store)  # cancel_replace_budget = 2
    adapter = MockBrokerAdapter()

    await execute_envelope_action(
        store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later(1)
    )
    for i, px in enumerate((9.85, 9.80)):
        result = await execute_envelope_action(
            store,
            adapter,
            env.id,
            planned(kind=ActionKind.REPRICE, limit_price=px),
            snapshot_fingerprint=f"fp-{i}",
            now=later(10 + i * 10),
        )
        assert result.outcome == "repriced"

    # Budget (2) spent: the write-time rail refuses the third reprice.
    calls_before = len(adapter.replaced)
    third = await store.stage_envelope_action(
        env.id,
        planned(kind=ActionKind.REPRICE, limit_price=9.75),
        snapshot_fingerprint="fp-x",
        now=later(60),
    )
    assert third.outcome == STAGE_DIVERGENCE  # plan claimed validity: defect path
    assert len(adapter.replaced) == calls_before
    frozen = await store.get_envelope(env.id)
    assert frozen.status is S.FROZEN

    # Restart: reopen the SAME database — the spent budget persists.
    store._conn.close()
    store._conn = None
    reopened = SqliteStateStore(tmp_path / "budget.db")
    await reopened.initialize()
    actions = [
        e
        for e in await reopened.get_execution_events()
        if e.envelope_id == env.id
        and e.event_type is ExecutionEventType.ENVELOPE_ACTION
        and e.payload.get("action") == "reprice"
    ]
    assert len(actions) == 2  # crash-restart cannot mint budget back
    reopened._conn.close()
    reopened._conn = None


async def test_exhausted_signal_path_via_the_tick(any_store):
    """When the POLICY sees the spent budget first (the normal path), it emits
    ExhaustedSignal and the tick lands EXHAUSTED — terminal-pending-human."""

    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    # Drain clocks sit BEFORE the tick's NOW: ENVELOPE_ACTION events carry
    # the injected decision clock (WO-0024), so the tick's cooldown check
    # measures from the LAST of these.
    await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later(-120)
    )
    for i, px in enumerate((9.85, 9.80)):
        await execute_envelope_action(
            any_store,
            adapter,
            env.id,
            planned(kind=ActionKind.REPRICE, limit_price=px),
            snapshot_fingerprint=f"fp-{i}",
            now=later(-110 + i * 10),
        )
    # Now drive the REAL policy through a crashing tape so it WANTS a reprice
    # and finds the budget gone.
    import tests.test_wo0020_envelope_tick as T20

    md, tapes = T20._wired(T20.crash_tape())
    await monitoring._run_envelopes(
        any_store,
        adapter,
        md,
        Settings(protection_enabled=False),
        tapes=tapes,
        now=T20.NOW,
    )
    after = await any_store.get_envelope(env.id)
    # WO-0028/TC-07: the union (EXHAUSTED, FROZEN) let a plan-time miss that
    # lands FROZEN via write-time divergence pass a test named for the
    # exhausted SIGNAL. Pin the mechanism: the policy itself must emit
    # ExhaustedSignal -> EXHAUSTED terminal.
    assert after.status is S.EXHAUSTED
    assert len(adapter.replaced) == 2
