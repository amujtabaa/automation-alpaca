"""Regime→trail mapping + the monotonic working-stop ratchet (WO-0018).

All trail distances are ATR MULTIPLES: the envelope's soft trail range
``trail_distance_min/max`` is ``[min_atr_mult, max_atr_mult]`` under ADR-009
as specified by WO-0018 (final) — one policy self-calibrates across price
levels and volatility.

Two invariants live here:

* **Ratchet** — the working stop is the RUNNING MAX of per-step candidates
  since activation. Monotone non-decreasing by construction, and derivable
  purely from the tape (no hidden state to lose on restart).
* **Trail floor** — every step's CANDIDATE keeps at least ``min_atr_mult ×
  ATR(step)`` of room from that step's trail reference (over-tight stops
  systematically exit pre-continuation — research notes). The RATCHETED stop
  may end up closer to price after a crash: that is the stop firing, not a
  floor violation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from app.sellside.bars import Bar
from app.sellside.indicators import atr, fade_flag
from app.sellside.regime import (
    FADE_QUANTILE,
    FADE_WINDOW,
    MIN_CLASSIFY_BARS,
    Regime,
    classify,
)
from app.sellside.types import ClampNote
from app.models import ExecutionEnvelope

# Trail ATR: last TRAIL_ATR_PERIOD true ranges of the whole prefix (a longer,
# steadier window than the classifier's short ATR — Chandelier convention).
TRAIL_ATR_PERIOD = 14
# Classifier windows (short/current vs rolling baseline).
CLASSIFY_ATR_SHORT = 8
CLASSIFY_ATR_BASELINE = 14
# Regime → chandelier multiple (clamped into the envelope's soft range).
REGIME_MULTIPLE: dict[Regime, float] = {
    Regime.STEADY_SURGE: 2.5,
    Regime.MATURE_TREND: 2.0,
    Regime.STALL_FADE: 2.0,  # decays with the adverse run (Recovery-style)
}
# STALL_FADE: multiple halves per consecutive adverse bar (exponential
# tightening toward the floor on failed recoveries).
RECOVERY_DECAY = 0.5
# Pullback discrimination: last-bar volume vs the mean of the prior bars.
VOLUME_EXPAND_RATIO = 1.5
VOLUME_LOOKBACK = 4


@dataclass(frozen=True)
class WorkingStopResult:
    """The ratcheted stop plus this step's diagnostics (candidate/ref_high/
    regime/atr/tightened/clamps all describe the FINAL step)."""

    stop: Optional[float]
    candidate: Optional[float]
    ref_high: Optional[float]
    regime: Regime
    atr: Optional[float]
    tightened: bool
    clamps: tuple[ClampNote, ...] = ()


def _step_candidate(
    envelope: ExecutionEnvelope,
    prefix: Sequence[Bar],
    *,
    urgency: float,
) -> tuple[
    Optional[float],
    Optional[float],
    Optional[float],
    Regime,
    bool,
    tuple[ClampNote, ...],
]:
    """(candidate, ref_high, trail_atr, regime, tightened, clamps) for one
    bar-prefix step, or Nones while warming up."""

    if len(prefix) < MIN_CLASSIFY_BARS:
        return None, None, None, Regime.UNCERTAIN, False, ()
    trail_atr = atr(prefix, TRAIL_ATR_PERIOD)
    if trail_atr is None or trail_atr <= 0:
        return None, None, None, Regime.UNCERTAIN, False, ()

    atr_now = atr(prefix[-CLASSIFY_ATR_SHORT:], CLASSIFY_ATR_SHORT)
    atr_baseline = atr(prefix[:-CLASSIFY_ATR_SHORT], CLASSIFY_ATR_BASELINE)
    regime = classify(prefix, atr_now=atr_now, atr_baseline=atr_baseline)

    ref_high = max(b.high for b in prefix)
    min_mult = envelope.trail_distance_min
    max_mult = envelope.trail_distance_max

    # Pullback discrimination: pulling back AND (expanding volume OR fade
    # flag) → tighten to the floor multiple immediately; contracting-volume
    # pullbacks are tolerated at the regime's own multiple.
    pulling_back = len(prefix) >= 2 and prefix[-1].close < prefix[-2].close
    lookback = [b.volume for b in prefix[-(VOLUME_LOOKBACK + 1) : -1]]
    base_vol = sum(lookback) / len(lookback) if lookback else 0.0
    expanding = base_vol > 0 and prefix[-1].volume >= VOLUME_EXPAND_RATIO * base_vol
    faded = fade_flag(prefix, window=FADE_WINDOW, quantile=FADE_QUANTILE)
    tightened = pulling_back and (expanding or faded)

    clamps: list[ClampNote] = []

    if tightened:
        distance = min_mult * trail_atr
    elif regime is Regime.FAST_SPIKE:
        # One-bar trail: the prior internal bar's low, floored at min_mult ×
        # ATR (trail-floor invariant) and capped at the widest allowed trail.
        one_bar = ref_high - prefix[-2].low
        distance = min(max(one_bar, min_mult * trail_atr), max_mult * trail_atr)
        if distance != one_bar:
            clamps.append(
                ClampNote(
                    field="trail_distance",
                    computed=one_bar,
                    clamped_to=distance,
                )
            )
    else:
        if regime is Regime.UNCERTAIN:
            multiple = max_mult  # conservative default: the widest trail
        else:
            multiple = REGIME_MULTIPLE[regime]
            if regime is Regime.STALL_FADE:
                adverse = 0
                for b in reversed(prefix):
                    if b.close < b.open:
                        adverse += 1
                    else:
                        break
                multiple = multiple * (RECOVERY_DECAY**adverse)
            # Structural exit check (chandelier regimes): closing below the
            # bar-VWAP anchor is exit pressure → floor multiple.
            if regime in (Regime.STEADY_SURGE, Regime.MATURE_TREND):
                vol_total = sum(b.volume for b in prefix)
                if vol_total > 0:
                    bar_vwap = sum(b.close * b.volume for b in prefix) / vol_total
                    if prefix[-1].close < bar_vwap:
                        multiple = min_mult
        # Urgency slides the multiple toward the floor, never through it.
        effective = multiple - urgency * (multiple - min_mult)
        bounded = min(max(effective, min_mult), max_mult)
        if bounded != effective:
            clamps.append(
                ClampNote(
                    field="trail_multiple", computed=effective, clamped_to=bounded
                )
            )
        distance = bounded * trail_atr

    return (
        ref_high - distance,
        ref_high,
        trail_atr,
        regime,
        tightened,
        tuple(clamps),
    )


def compute_working_stop(
    envelope: ExecutionEnvelope,
    bars: Sequence[Bar],
    *,
    urgency: float,
) -> WorkingStopResult:
    """Ratchet the per-step candidates over the whole bar sequence (pure —
    recomputable from the tape after any restart; O(n²) in bars, fine at the
    tick's 30s-bar scale, revisit in W4 if tapes grow)."""

    stop: Optional[float] = None
    last: tuple = (None, None, None, Regime.UNCERTAIN, False, ())
    for step in range(MIN_CLASSIFY_BARS, len(bars) + 1):
        last = _step_candidate(envelope, bars[:step], urgency=urgency)
        candidate = last[0]
        if candidate is not None:
            stop = candidate if stop is None else max(stop, candidate)
    candidate, ref_high, trail_atr, regime, tightened, clamps = last
    return WorkingStopResult(
        stop=stop,
        candidate=candidate,
        ref_high=ref_high,
        regime=regime,
        atr=trail_atr,
        tightened=tightened,
        clamps=clamps,
    )
