"""WO-0021 — regime scenario tapes (policy level).

Each tape asserts the WO-0018 regime→trail mapping end-to-end at the decide()
seam: which regime fires, which trail rule applies, and that every exit the
policy plans respects the hard rails. (The W4 five-metric scorer grades these
same tapes once the harness exists; here the assertions are the ADR rails.)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.marketdata.service import MarketSnapshot
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    SessionType,
)
from app.sellside.bars import aggregate
from app.sellside.policy import decide, validate_action
from app.sellside.trails import compute_working_stop
from app.sellside.types import (
    BreachSignal,
    NoAction,
    PlannedAction,
    StaleDataSignal,
)

pytestmark = pytest.mark.anyio

# Wednesday 10:00 ET (14:00 UTC) — deterministic regular hours.
T0 = datetime(2026, 7, 15, 13, 0, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
BAR = timedelta(seconds=30)


def envelope(**overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id="si-1",
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=8.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.5,
        aggressiveness=["passive"],
        cooldown_floor_ms=750,
        cancel_replace_budget=40,
        expires_at=NOW + timedelta(hours=6),
        allowed_session_phases=list(SessionType),
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        status=EnvelopeStatus.ACTIVE,
        activated_at=T0,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def snap(i: int, price: float, cum: float, **kw) -> MarketSnapshot:
    base = dict(
        symbol="AAPL",
        last_price=round(price, 4),
        bid=round(price - 0.01, 4),
        ask=round(price + 0.01, 4),
        volume=cum,
        prev_close=9.50,
        updated_at=T0 + timedelta(seconds=10 * i),
    )
    base.update(kw)
    return MarketSnapshot(**base)


def walk(n, start_price, step_fn, vol_fn, start_i=0, start_cum=1000.0):
    tape, price, cum = [], start_price, start_cum
    for j in range(n):
        price = max(0.5, price + step_fn(j))
        cum += vol_fn(j)
        tape.append(snap(start_i + j, price, cum))
    return tape


def _action_event(env, decision, at):
    from app.models import (
        EventAuthority,
        EventSource,
        ExecutionEvent,
        ExecutionEventType,
    )

    return ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=at,
        envelope_id=env.id,
        symbol=env.symbol,
        payload={
            "action": decision.kind.value,
            "limit_price": decision.limit_price,
            "quantity": decision.quantity,
            "tranche": decision.tranche,
        },
    )


def first_stop_exit(env, tape, history=()):
    """Walk the tape tick by tick THE WAY THE ENGINE DOES: tranche actions are
    consumed into history (once-only, cooldown-gated) and the walk continues;
    returns (index, decision) at the first stop-triggered exit or
    BreachSignal, else (None, last_decision)."""

    events = list(history)
    last = None
    for cut in range(60, len(tape) + 1):
        now = tape[cut - 1].updated_at + timedelta(seconds=1)
        last = decide(env, tape[:cut], now=now, history=events)
        if isinstance(last, BreachSignal):
            return cut, last
        if isinstance(last, PlannedAction):
            if last.stop_triggered:
                return cut, last
            events.append(_action_event(env, last, tape[cut - 1].updated_at))
    return None, last


# --- 1. vertical spike then instant crash ------------------------------------- #


def test_fast_spike_one_bar_trail_exits_near_the_peak():
    calm = walk(120, 10.0, lambda j: 0.002 * (-1) ** j, lambda j: 100)
    spike = walk(24, calm[-1].last_price, lambda j: 0.15, lambda j: 3000, 120)
    crash = walk(18, spike[-1].last_price, lambda j: -0.30, lambda j: 4000, 144)
    tape = calm + spike + crash
    peak = max(s.last_price for s in tape)

    env = envelope()
    cut, decision = first_stop_exit(env, tape)
    assert cut is not None, "the crash must trigger an exit"
    assert isinstance(decision, PlannedAction)
    assert decision.stop_triggered is True
    # One-bar trail territory: the exit fires within the first crash bars and
    # the working stop sits near the peak (>= peak minus the widest allowed
    # trail at that step).
    bars = aggregate(tape[:cut], BAR)
    ws = compute_working_stop(env, bars, urgency=0.0)
    assert ws.stop is not None and ws.atr is not None
    assert ws.stop >= peak - env.trail_distance_max * ws.atr - 1e-9
    # Hard rails hold on the planned exit itself.
    assert (
        validate_action(env, decision, history=[], now=tape[cut - 1].updated_at) is None
    )


# --- 2. grinder: ratchet holds through noise ----------------------------------- #


def test_grinder_never_shaken_out_and_ratchet_monotone():
    tape = walk(
        240,
        10.0,
        lambda j: 0.01 + (0.008 if j % 3 == 0 else -0.006),  # net-up grind
        lambda j: 120,
    )
    env = envelope()
    stops = []
    for cut in range(60, len(tape) + 1, 6):
        now = tape[cut - 1].updated_at + timedelta(seconds=1)
        decision = decide(env, tape[:cut], now=now, history=[])
        assert not isinstance(decision, BreachSignal)
        if isinstance(decision, PlannedAction):
            assert decision.stop_triggered is False  # no shakeout exit
        ws = compute_working_stop(env, aggregate(tape[:cut], BAR), urgency=0.0)
        if ws.stop is not None:
            stops.append(ws.stop)
    assert stops and all(b >= a - 1e-9 for a, b in zip(stops, stops[1:]))


def test_ratchet_holds_when_atr_expands_and_candidates_collapse():
    """WO-0028/TC-02 — the tape that actually pins the ratchet.

    The grinder above re-ratchets per cut, so `stop = candidate` (ratchet
    deleted) survived it: on a smooth tape the LAST candidate is itself
    monotone. Here ATR expands violently AFTER a tight rise while ref_high
    stays put, so the last per-step candidate collapses far below an earlier
    one — only the running max (the ratchet) keeps the working stop from
    LOOSENING exactly when it must not."""

    calm = walk(120, 10.0, lambda j: 0.02, lambda j: 120)
    # Whipsaw below the peak: first step down, then ±0.25 oscillation — the
    # running high never advances, but 30s-bar true ranges explode.
    whip = walk(
        120,
        calm[-1].last_price,
        lambda j: -0.25 if j % 2 == 0 else 0.25,
        lambda j: 120,
        start_i=120,
        start_cum=calm[-1].volume,
    )
    env = envelope()
    ws_calm = compute_working_stop(env, aggregate(calm, BAR), urgency=0.0)
    ws_full = compute_working_stop(env, aggregate(calm + whip, BAR), urgency=0.0)
    assert ws_calm.stop is not None and ws_full.stop is not None
    # Sanity: the tape genuinely distinguishes — the final unratcheted
    # candidate sits strictly below the calm-phase stop.
    assert ws_full.candidate is not None
    assert ws_full.candidate < ws_calm.stop - 1e-6
    # The pin: extending the tape can NEVER loosen the working stop.
    assert ws_full.stop >= ws_calm.stop - 1e-9


# --- 3. trend-then-pullback: tranche into strength, remainder survives ----------- #


@pytest.mark.xfail(
    strict=True,
    reason=(
        "FINDING-W3-lase-pullback-structural-hold: an ATR-multiple chandelier "
        "on a low-volatility grind is far tighter than a pull-to-VWAP, so the "
        "remainder stops out — the research notes' structural-exit intent "
        "(hold above anchored VWAP on contracting-volume pullbacks) is not "
        "yet a mechanism. Follow-up WO drafted; prime W4/SOL bake-off input."
    ),
)
def test_trend_pullback_resume_takes_one_tranche_and_survives():
    up = walk(160, 10.0, lambda j: 0.02, lambda j: 400)  # clean drive
    pull = walk(
        30, up[-1].last_price, lambda j: -0.015, lambda j: 60, 160
    )  # contracting-volume pullback toward VWAP
    resume = walk(30, pull[-1].last_price, lambda j: 0.015, lambda j: 300, 190)
    tape = up + pull + resume

    env = envelope()
    # First action must be the tranche into strength...
    for cut in range(60, len(tape) + 1):
        now = tape[cut - 1].updated_at + timedelta(seconds=1)
        first = decide(env, tape[:cut], now=now, history=[])
        if isinstance(first, PlannedAction):
            break
    assert isinstance(first, PlannedAction)
    assert first.tranche is True and first.stop_triggered is False
    assert first.quantity <= 50  # first-objective tranche, half remaining
    decision, cut = first, cut

    # With the tranche recorded, the pullback does NOT stop out the remainder.
    from tests.test_wo0019_engine_seam import (  # canonical event helper
        planned as _planned,  # noqa: F401
    )

    from app.models import (
        EventAuthority,
        EventSource,
        ExecutionEvent,
        ExecutionEventType,
    )

    tranche_event = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=tape[cut - 1].updated_at,
        envelope_id=env.id,
        symbol="AAPL",
        payload={
            "action": "submit",
            "limit_price": decision.limit_price,
            "quantity": decision.quantity,
            "tranche": True,
        },
    )
    stops = []
    for cut2 in range(cut, len(tape) + 1, 6):
        now = tape[cut2 - 1].updated_at + timedelta(seconds=1)
        d2 = decide(env, tape[:cut2], now=now, history=[tranche_event])
        assert not (isinstance(d2, PlannedAction) and d2.tranche)  # once only
        assert not (isinstance(d2, PlannedAction) and d2.stop_triggered), (
            "shallow contracting-volume pullback must not stop out the remainder"
        )
        ws = compute_working_stop(env, aggregate(tape[:cut2], BAR), urgency=0.0)
        if ws.stop is not None:
            stops.append(ws.stop)
    assert all(b >= a - 1e-9 for a, b in zip(stops, stops[1:]))  # monotone


# --- 4. fakeout pump: expanding-volume fade tightens and exits above floor -------- #


def test_fakeout_pump_tightens_immediately_and_exits_above_floor():
    calm = walk(120, 10.0, lambda j: 0.002 * (-1) ** j, lambda j: 100)
    thin_spike = walk(18, calm[-1].last_price, lambda j: 0.10, lambda j: 80, 120)
    heavy_fade = walk(
        24, thin_spike[-1].last_price, lambda j: -0.12, lambda j: 2500, 138
    )
    tape = calm + thin_spike + heavy_fade
    env = envelope()

    cut, decision = first_stop_exit(env, tape)
    assert cut is not None and isinstance(decision, PlannedAction)
    assert decision.stop_triggered is True
    assert decision.limit_price >= env.floor_price  # exit ABOVE the floor
    ws = compute_working_stop(env, aggregate(tape[:cut], BAR), urgency=0.0)
    # The expanding-volume fade snapped the candidate to the floor multiple
    # at some step — visible as tightened=True on the final pre-exit step or
    # a stop within min-mult reach of the reference.
    assert ws.tightened or (
        ws.ref_high is not None
        and ws.atr is not None
        and ws.ref_high - ws.stop <= env.trail_distance_max * ws.atr + 1e-9
    )


# --- 5. stall/fade into session close: urgency + floor ---------------------------- #


def test_stall_into_close_tightens_within_the_trail_floor():
    tape = walk(200, 10.0, lambda j: 0.01 if j < 120 else -0.004, lambda j: 150)
    env = envelope()
    bars = aggregate(tape, BAR)
    patient = compute_working_stop(env, bars, urgency=0.0)
    urgent = compute_working_stop(env, bars, urgency=1.0)  # ~close
    assert patient.candidate is not None and urgent.candidate is not None
    assert urgent.candidate >= patient.candidate  # urgency tightens
    assert (
        urgent.ref_high - urgent.candidate >= env.trail_distance_min * urgent.atr - 1e-9
    )  # never through the floor


# --- 6. halt-resume gap far below the working stop --------------------------------- #


def test_gap_below_floor_is_a_breach_signal_never_a_submit():
    up = walk(180, 10.0, lambda j: 0.005, lambda j: 200)
    gap = [snap(180, 7.50, up[-1].volume + 5000)]  # one-tick gap under the 8.00 floor
    tape = up + gap
    env = envelope()
    now = tape[-1].updated_at + timedelta(seconds=1)
    decision = decide(env, tape, now=now, history=[])
    assert isinstance(decision, BreachSignal)
    assert decision.rail == "floor_price"

    # Stale variant: same gap flagged stale ⇒ the stale gate wins (fail
    # closed, disposition signal) — still never a submit.
    stale_tape = up + [
        snap(180, 7.50, up[-1].volume + 5000, stale=True),
    ]
    stale_decision = decide(env, stale_tape, now=now, history=[])
    assert isinstance(stale_decision, StaleDataSignal)


# --- thin-market extras -------------------------------------------------------------- #


def test_wide_spread_never_breaches_and_stays_within_rails():
    # NOTE: WO-0018(final) has no spread-widening soft bound (the research
    # notes' "evasive widening" was not adopted); a wide-but-uncrossed quote
    # is simply valid data. This pins that it neither breaches nor produces a
    # rail-violating plan. (Gap observation recorded for the wave review.)
    tape = walk(200, 10.0, lambda j: -0.02 if j > 150 else 0.01, lambda j: 300)
    wide = tape[:-1] + [
        snap(
            199,
            tape[-1].last_price,
            tape[-1].volume,
            bid=tape[-1].last_price - 0.40,
            ask=tape[-1].last_price + 0.40,
        )
    ]
    env = envelope()
    now = wide[-1].updated_at + timedelta(seconds=1)
    decision = decide(env, wide, now=now, history=[])
    if isinstance(decision, PlannedAction):
        assert validate_action(env, decision, history=[], now=now) is None
    else:
        assert not isinstance(decision, BreachSignal) or (
            decision.rail == "floor_price"
        )


def test_zero_volume_never_produces_a_zero_qty_submit():
    tape = walk(200, 10.0, lambda j: -0.02 if j > 150 else 0.01, lambda j: 0.0)
    env = envelope()
    now = tape[-1].updated_at + timedelta(seconds=1)
    decision = decide(env, tape, now=now, history=[])
    if isinstance(decision, PlannedAction):
        assert decision.quantity >= 1  # stop path may probe with 1 share
    elif isinstance(decision, NoAction):
        pass  # NO_LIQUIDITY / monitoring — acceptable fail-quiet outcomes
    else:
        assert not isinstance(decision, BreachSignal)


def test_cooldown_boundary_exactly_at_floor_is_allowed():
    from app.models import (
        EventAuthority,
        EventSource,
        ExecutionEvent,
        ExecutionEventType,
    )
    from app.sellside.types import ActionKind

    env = envelope(cooldown_floor_ms=750)
    placed_at = NOW - timedelta(milliseconds=750)  # EXACTLY the floor
    prior = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=placed_at,
        envelope_id=env.id,
        symbol="AAPL",
        payload={"action": "submit", "limit_price": 9.9, "quantity": 10},
    )
    action = PlannedAction(
        kind=ActionKind.REPRICE,
        limit_price=9.85,
        quantity=10,
        regime=None,
        urgency=0.0,
        working_stop=None,
        atr=None,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )
    # elapsed == floor ⇒ NOT inside the floor ⇒ allowed (deterministic).
    assert validate_action(env, action, history=[prior], now=NOW) is None
    # one millisecond earlier ⇒ inside ⇒ denied.
    just_inside = validate_action(
        env, action, history=[prior], now=NOW - timedelta(milliseconds=1)
    )
    assert just_inside is not None and just_inside.rail == "cooldown_floor"
