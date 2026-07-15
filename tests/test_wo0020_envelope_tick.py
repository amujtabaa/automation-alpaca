"""WO-0020 — the envelope pass inside the monitoring tick, BOTH stores.

Protection always runs first; the envelope pass consumes the WO-0018 policy
and the WO-0019 seam; a policy exception freezes ONLY that envelope and never
crashes the tick; fills observed by reconciliation decrement the envelope
(record-first bridging, so the single FILL event carries envelope_id and
position never double-counts).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

import app.monitoring as monitoring
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.marketdata.service import MarketSnapshot
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
    utcnow,
)
from app.monitoring import EnvelopeTapeBuffer, run_monitoring_tick
from tests.store_helpers import activate_envelope_at

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
# 10:00 ET on a Wednesday — regular hours, deterministic (the container clock
# may be a weekend; the policy's session gate is real).
from datetime import datetime, timezone  # noqa: E402

NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def settings() -> Settings:
    return Settings(protection_enabled=False)


def make_draft(intent_id: str, symbol: str = "AAPL", **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=100,
        floor_price=8.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.50,
        aggressiveness=["passive"],
        cooldown_floor_ms=600_000,  # no reprice churn inside a test
        cancel_replace_budget=5,
        expires_at=NOW + timedelta(hours=6),
        allowed_session_phases=list(SessionType),
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def snap(symbol: str, seconds_ago: float, price: float, cum_volume: float):
    return MarketSnapshot(
        symbol=symbol,
        last_price=round(price, 4),
        bid=round(price - 0.01, 4),
        ask=round(price + 0.01, 4),
        volume=cum_volume,
        prev_close=9.50,
        updated_at=NOW - timedelta(seconds=seconds_ago),
    )


def crash_tape(symbol: str = "AAPL"):
    """30-min grind up then a 10-min collapse through any sane trail."""

    tape = []
    price, cum = 10.0, 1000.0
    total = 240
    for i in range(180):
        price += 0.005
        cum += 200
        tape.append(snap(symbol, (total - i) * 10, price, cum))
    for i in range(60):
        price -= 0.02
        cum += 600
        tape.append(snap(symbol, (total - 180 - i) * 10, price, cum))
    return tape


async def _hold(store, symbol, qty, avg=10.0):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )


async def _active_envelope(store, symbol="AAPL", **overrides):
    si = await store.create_sell_intent(
        symbol=symbol, reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    # Injected activation clock, anchored BEFORE the NOW-anchored tapes: the
    # policy's since-activation window (INV-086) must contain the tape rows
    # regardless of wall-clock time of day (see activate_envelope_at).
    return await activate_envelope_at(
        store, make_draft(si.id, symbol, **overrides), now=NOW - timedelta(hours=1)
    )


def _wired(tape_snaps):
    """(market_data, tapes) pre-loaded with a tape whose last snapshot is live."""

    md = FakeMarketDataFeed()
    tapes = EnvelopeTapeBuffer()
    for s in tape_snaps:
        tapes.append(s)
    last = tape_snaps[-1]
    md.set_snapshot(
        last.symbol,
        last_price=last.last_price,
        bid=last.bid,
        ask=last.ask,
        volume=last.volume,
        prev_close=last.prev_close,
    )
    return md, tapes


async def test_full_loop_stop_exit_fill_completes_envelope(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    # LEAVE_RESTING so tick 2 (deliberately fed a STALE snapshot) fails closed
    # and leaves the working exit alone while reconcile ingests its fill.
    env = await _active_envelope(
        any_store, stale_data_disposition=EnvelopeStaleDataDisposition.LEAVE_RESTING
    )
    adapter = MockBrokerAdapter()
    md, tapes = _wired(crash_tape())

    # Tick 1: the policy sees the breakdown, the seam stages + submits.
    await run_monitoring_tick(
        any_store,
        adapter,
        settings(),
        market_data=md,
        envelope_tapes=tapes,
        envelope_now=NOW,
    )
    sells = [
        o
        for o in await any_store.list_orders()
        if o.sell_intent_id == env.sell_intent_id
    ]
    assert len(sells) == 1
    assert sells[0].status is OrderStatus.SUBMITTED
    # Exactly ONE venue submit for the envelope's exit (the _hold BUY is swept
    # by the same tick's submit pass — that one is not ours to count).
    assert [o.id for o in adapter.submitted if o.side is OrderSide.SELL] == [
        sells[0].id
    ]

    # Venue fills the whole exit; tick 2's reconcile ingests it and the
    # bridge decrements the envelope (single FILL event, envelope_id set).
    from app.broker.adapter import BrokerFill

    adapter.make_fill(
        sells[0].id,
        status=OrderStatus.FILLED,
        filled_quantity=sells[0].quantity,
        fills=[
            BrokerFill(
                source_fill_id="x-1",
                quantity=sells[0].quantity,
                price=9.60,
                filled_at=utcnow(),
            )
        ],
    )
    md.set_snapshot("AAPL", last_price=9.7, bid=9.69, ask=9.71, stale=True)
    await run_monitoring_tick(
        any_store,
        adapter,
        settings(),
        market_data=md,
        envelope_tapes=tapes,
        envelope_now=NOW + timedelta(seconds=30),
    )

    after = await any_store.get_envelope(env.id)
    assert after.remaining_quantity == 100 - sells[0].quantity
    if sells[0].quantity == 100:
        assert after.status is S.COMPLETED  # full exit auto-completes
    fill_events = [
        e
        for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.FILL and e.order_id == sells[0].id
    ]
    assert len(fill_events) == 1  # ONE event: envelope-attributed, no double
    assert fill_events[0].envelope_id == env.id
    # Position folded exactly once.
    position = await any_store.get_position("AAPL")
    assert position.quantity == 100 - sells[0].quantity


async def test_policy_exception_freezes_only_that_envelope(any_store, monkeypatch):
    await any_store.initialize()
    env_a = await _active_envelope(any_store, symbol="AAPL")
    await _hold(any_store, "MSFT", 100)  # WO-0026: reduce-only needs a book
    env_b = await _active_envelope(any_store, symbol="MSFT")
    adapter = MockBrokerAdapter()
    md, tapes = _wired(crash_tape("AAPL"))
    for s in crash_tape("MSFT"):
        tapes.append(s)
    md.set_snapshot("MSFT", last_price=9.7, bid=9.69, ask=9.71, volume=50_000.0)

    real_decide = monitoring.decide

    def explode(envelope, *args, **kwargs):
        if envelope.symbol == "AAPL":
            raise RuntimeError("injected policy bug")
        return real_decide(envelope, *args, **kwargs)

    monkeypatch.setattr(monitoring, "decide", explode)

    await run_monitoring_tick(
        any_store,
        adapter,
        settings(),
        market_data=md,
        envelope_tapes=tapes,
        envelope_now=NOW,
    )  # must NOT raise

    frozen = await any_store.get_envelope(env_a.id)
    assert frozen.status is S.FROZEN  # the broken one froze...
    b_after = await any_store.get_envelope(env_b.id)
    assert b_after.status is not S.FROZEN  # ...the healthy one was processed
    msft_sells = [
        o
        for o in await any_store.list_orders()
        if o.sell_intent_id == env_b.sell_intent_id
    ]
    assert len(msft_sells) == 1  # B's stop-exit went through this same tick


async def test_quarantined_child_pauses_not_freezes_the_envelope(any_store):
    """Codex PR#8 F4: a working child in TIMEOUT_QUARANTINE PAUSES the envelope
    (``stage_envelope_action`` raises ``EnvelopeActionPausedError``) until
    ADR-002 targeted reconciliation resolves the ambiguity — an EXPECTED
    transient wait, not a policy crash. The per-envelope handler must leave the
    envelope ACTIVE (skip this tick), never FREEZE it as ``policy_error`` —
    otherwise a recoverable submit timeout demands a manual human resume even
    after the quarantine cleanly resolves."""

    from app.sellside.types import ActionKind, PlannedAction

    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    env = await _active_envelope(any_store, symbol="AAPL", cooldown_floor_ms=1)

    # Stage a SUBMIT, claim it to SUBMITTING, then quarantine it (the ADR-002
    # ambiguous-submit pause posture) so it is the live-but-paused working order.
    action = PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=10,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )
    staged = await any_store.stage_envelope_action(
        env.id, action, snapshot_fingerprint="fp-f4", now=NOW
    )
    await any_store.claim_order_for_submission(staged.order.id)
    await any_store.quarantine_timed_out_order(staged.order.id, reason="submit_timeout")
    assert (
        await any_store.get_order(staged.order.id)
    ).status is OrderStatus.TIMEOUT_QUARANTINE

    # The crash continues, so the policy wants to reprice the (paused) working
    # order -> staging raises EnvelopeActionPausedError. Drive the pass directly
    # with an injected `now` past the cooldown.
    adapter = MockBrokerAdapter()
    md, tapes = _wired(crash_tape())
    await monitoring._run_envelopes(
        any_store,
        adapter,
        md,
        settings(),
        tapes=tapes,
        now=NOW + timedelta(seconds=120),
    )

    after = await any_store.get_envelope(env.id)
    assert after.status is S.ACTIVE, (
        f"quarantine pause froze the envelope instead of pausing it: {after.status}"
    )


async def test_expiry_disposition_cancel_and_return(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    env = await _active_envelope(any_store)
    adapter = MockBrokerAdapter()
    md, tapes = _wired(crash_tape())
    await run_monitoring_tick(
        any_store,
        adapter,
        settings(),
        market_data=md,
        envelope_tapes=tapes,
        envelope_now=NOW,
    )
    working = [
        o
        for o in await any_store.list_orders()
        if o.sell_intent_id == env.sell_intent_id
    ][0]

    # Force expiry: next tick the policy emits ExpiredSignal; the pass applies
    # the CANCEL_AND_RETURN disposition — venue cancel + envelope EXPIRED.
    import app.store.core  # noqa: F401  (imported for monkeypatch surface parity)

    expired_env = await any_store.get_envelope(env.id)
    assert expired_env.expires_at > utcnow()  # not yet — so simulate via time
    # Rather than monkeypatching clocks store-deep, drive the pass directly
    # with an injected now PAST the TTL:
    await monitoring._run_envelopes(
        any_store,
        adapter,
        md,
        settings(),
        tapes=tapes,
        now=env.expires_at + timedelta(seconds=1),
    )
    after = await any_store.get_envelope(env.id)
    assert after.status is S.EXPIRED
    assert working.broker_order_id in adapter.canceled  # CANCEL_AND_RETURN
    cancelled = await any_store.get_order(working.id)
    assert cancelled.status is OrderStatus.CANCEL_PENDING


async def test_no_market_data_or_tapes_is_a_noop(any_store):
    await any_store.initialize()
    env = await _active_envelope(any_store)
    adapter = MockBrokerAdapter()
    await run_monitoring_tick(any_store, adapter, settings())  # no md, no tapes
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE
    assert adapter.submitted == []


async def test_tape_buffer_dedupes_and_bounds(any_store):
    tapes = EnvelopeTapeBuffer(max_len=10)
    base = crash_tape()[:15]
    for s in base:
        tapes.append(s)
    tape = tapes.tape("AAPL")
    assert len(tape) == 10  # bounded, oldest dropped
    tapes.append(base[-1])  # same updated_at — deduped, not appended
    assert len(tapes.tape("AAPL")) == 10
