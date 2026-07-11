"""WO-0018 — regime classifier + regime→trail mapping + the monotonic
working-stop ratchet and trail-floor invariant (research notes, WO-0018).

Synthetic 30s-bar tapes are engineered deep inside each regime's territory so
the tests pin MECHANISMS (which rule fires, which trail formula applies, the
ratchet/floor invariants) rather than threshold constants — those are W4-
tunable module constants by design.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    SessionType,
)
from app.sellside.bars import Bar
from app.sellside.indicators import atr
from app.sellside.regime import Regime, classify
from app.sellside.trails import compute_working_stop

T0 = datetime(2026, 7, 8, 14, 0, 0, tzinfo=timezone.utc)
NOW = T0 + timedelta(hours=1)


def bar(i, o, h, lo, c, v=100.0):
    start = T0 + timedelta(seconds=30 * i)
    return Bar(
        start=start,
        end=start + timedelta(seconds=30),
        open=o,
        high=h,
        low=lo,
        close=c,
        volume=v,
    )


def flat_bars(n, price=10.0, wiggle=0.02, v=100.0, start=0):
    return [
        bar(start + i, price, price + wiggle, price - wiggle, price, v=v)
        for i in range(n)
    ]


def make_envelope(**overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id="si-1",
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=5.00,
        trail_distance_min=1.0,  # ATR multiples under WO-0018 (final)
        trail_distance_max=3.0,
        participation_rate_cap=0.20,
        aggressiveness=["patient", "urgent"],
        cooldown_floor_ms=750,
        cancel_replace_budget=10,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        status=EnvelopeStatus.ACTIVE,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


# --- classifier per regime ------------------------------------------------------- #


def spike_tape():
    """Calm baseline then a violent expansion: ATR ratio and net move both
    far beyond any sane spike threshold, on huge volume."""

    calm = flat_bars(40, price=10.0, wiggle=0.02, v=100.0)
    burst = [
        bar(40, 10.00, 10.60, 9.98, 10.55, v=2000.0),
        bar(41, 10.55, 11.20, 10.50, 11.15, v=2500.0),
        bar(42, 11.15, 11.90, 11.10, 11.85, v=3000.0),
        bar(43, 11.85, 12.60, 11.80, 12.55, v=3500.0),
    ]
    return calm + burst


def surge_tape():
    """Persistent one-directional grind: strong trend, mild range expansion."""

    out = flat_bars(30, price=10.0, wiggle=0.03, v=100.0)
    price = 10.0
    for i in range(12):
        nxt = price + 0.05
        out.append(bar(30 + i, price, nxt + 0.01, price - 0.01, nxt, v=180.0))
        price = nxt
    return out


def fade_tape():
    """An up-move that stalls and rolls over on expanding volume."""

    out = flat_bars(24, price=10.0, wiggle=0.03, v=100.0)
    price = 10.0
    for i in range(8):
        nxt = price + 0.06
        out.append(bar(24 + i, price, nxt + 0.01, price - 0.01, nxt, v=150.0))
        price = nxt
    for i in range(8):
        nxt = price - 0.08
        out.append(bar(32 + i, price, price + 0.01, nxt - 0.01, nxt, v=400.0))
        price = nxt
    return out


def test_fast_spike_is_classified():
    bars = spike_tape()
    assert (
        classify(
            bars,
            atr_now=atr(bars[-8:], period=8),
            atr_baseline=atr(bars[:40], period=14),
        )
        is Regime.FAST_SPIKE
    )


def test_steady_surge_is_classified():
    bars = surge_tape()
    assert (
        classify(
            bars,
            atr_now=atr(bars[-8:], period=8),
            atr_baseline=atr(bars[:30], period=14),
        )
        is Regime.STEADY_SURGE
    )


def test_stall_fade_is_classified():
    bars = fade_tape()
    assert (
        classify(
            bars,
            atr_now=atr(bars[-8:], period=8),
            atr_baseline=atr(bars[:24], period=14),
        )
        is Regime.STALL_FADE
    )


def test_insufficient_bars_default_uncertain():
    bars = flat_bars(3)
    assert classify(bars, atr_now=None, atr_baseline=None) is Regime.UNCERTAIN


def test_directionless_chop_is_uncertain():
    bars = []
    for i in range(40):
        p = 10.0 + (0.03 if i % 2 == 0 else -0.03)
        bars.append(bar(i, 10.0, p + 0.02, p - 0.02, p, v=100.0))
    assert (
        classify(
            bars,
            atr_now=atr(bars[-8:], period=8),
            atr_baseline=atr(bars[:30], period=14),
        )
        is Regime.UNCERTAIN
    )


# --- working stop: ratchet + trail floor ------------------------------------------- #


def test_working_stop_is_monotone_across_a_spike_then_crash():
    """The ratchet must never give back progress — even when the regime flips
    from FAST_SPIKE to STALL_FADE and ATR explodes."""

    env = make_envelope()
    tape = fade_tape()
    stops = []
    for cut in range(30, len(tape) + 1):
        result = compute_working_stop(env, tape[:cut], urgency=0.0)
        if result.stop is not None:
            stops.append(result.stop)
    assert len(stops) > 5
    assert all(b >= a - 1e-9 for a, b in zip(stops, stops[1:]))


def test_trail_floor_candidate_never_tighter_than_min_atr_multiple():
    """FAST_SPIKE's one-bar trail would sit just under the prior bar low —
    when that is TIGHTER than min_atr_mult × ATR, the floor wins (over-tight
    stops systematically exit pre-continuation)."""

    env = make_envelope(trail_distance_min=2.0, trail_distance_max=4.0)
    bars = spike_tape()
    result = compute_working_stop(env, bars, urgency=0.0)
    assert result.candidate is not None and result.atr is not None
    # This step's candidate keeps at least min_mult × ATR(step) of room from
    # the trail reference (the ratcheted stop may sit closer after a crash —
    # that is the stop FIRING, not a floor violation).
    assert result.ref_high - result.candidate >= 2.0 * result.atr - 1e-9


def test_uncertain_regime_uses_the_conservative_end_of_the_range():
    env = make_envelope(trail_distance_min=1.0, trail_distance_max=3.0)
    bars = []
    for i in range(40):
        p = 10.0 + (0.03 if i % 2 == 0 else -0.03)
        bars.append(bar(i, 10.0, p + 0.02, p - 0.02, p, v=100.0))
    result = compute_working_stop(env, bars, urgency=0.0)
    assert result.regime is Regime.UNCERTAIN
    assert result.candidate is not None and result.atr is not None
    # Conservative end = the WIDEST allowed trail (max multiple).
    assert result.candidate == pytest.approx(
        result.ref_high - 3.0 * result.atr, abs=1e-6
    )


def test_urgency_tightens_within_bounds_but_respects_the_floor():
    env = make_envelope(trail_distance_min=1.0, trail_distance_max=3.0)
    bars = surge_tape()
    patient = compute_working_stop(env, bars, urgency=0.0)
    urgent = compute_working_stop(env, bars, urgency=1.0)
    assert patient.candidate is not None and urgent.candidate is not None
    assert urgent.candidate >= patient.candidate  # tighter (higher) under urgency
    assert urgent.ref_high - urgent.candidate >= 1.0 * urgent.atr - 1e-9  # floor holds


def test_pullback_on_contracting_volume_is_tolerated():
    """A shallow pullback on CONTRACTING volume must not tighten the trail:
    the stop stays where the ratchet put it, no min-mult snap."""

    env = make_envelope()
    up = surge_tape()
    peak_result = compute_working_stop(env, up, urgency=0.0)
    price = up[-1].close
    pull = list(up)
    for i in range(3):
        nxt = price - 0.02  # shallow vs the ~0.05 ATR
        pull.append(
            bar(len(pull), price, price + 0.005, nxt - 0.005, nxt, v=40.0)
        )  # contracting volume
        price = nxt
    pulled_result = compute_working_stop(env, pull, urgency=0.0)
    assert pulled_result.tightened is False
    assert pulled_result.stop >= peak_result.stop - 1e-9  # ratchet holds
    # Crucially NOT snapped to the tightest allowed distance — the candidate
    # keeps trailing at the regime's own multiple, well wider than the floor.
    assert (
        pulled_result.ref_high - pulled_result.candidate
        > env.trail_distance_min * pulled_result.atr + 1e-9
    )


def test_pullback_on_expanding_volume_tightens_immediately():
    env = make_envelope()
    up = surge_tape()
    base = compute_working_stop(env, up, urgency=0.0)
    price = up[-1].close
    push = list(up)
    for i in range(3):
        nxt = price - 0.04
        push.append(
            bar(len(push), price, price + 0.005, nxt - 0.005, nxt, v=900.0)
        )  # expanding volume
        price = nxt
    tightened = compute_working_stop(env, push, urgency=0.0)
    assert tightened.tightened is True
    assert tightened.stop >= base.stop - 1e-9  # ratchet still monotone
    # Tighten means: the candidate snapped to the tightest allowed distance —
    # exactly min_mult × ATR from the reference, no closer.
    assert tightened.ref_high - tightened.candidate == pytest.approx(
        env.trail_distance_min * tightened.atr, abs=1e-6
    )
