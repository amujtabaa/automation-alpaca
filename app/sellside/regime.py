"""Regime classifier (WO-0018, research notes): ATR-ratio (current vs rolling
baseline) + trend strength + volume/fade behavior over the internal 30s bars.

Exactly five regimes; UNCERTAIN is the conservative default (widest trail).
Thresholds below are W4-tunable mechanism constants — the CLASS structure
(which signal dominates, the precedence order) is the tested contract.
Precedence: fade/rollover beats everything (protect first), then the
spike/surge/trend ladder from most to least specific.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Sequence

from app.sellside.bars import Bar
from app.sellside.indicators import fade_flag

# Minimum bars before any non-UNCERTAIN claim (warmup).
MIN_CLASSIFY_BARS = 16
# Trend measurement window (30s bars → 4 minutes).
TREND_BARS = 8
# Fade detector window / quantile (nonparametric).
FADE_WINDOW = 16
FADE_QUANTILE = 0.10
# ATR expansion ratios.
SPIKE_ATR_RATIO = 2.0
MATURE_MAX_ATR_RATIO = 1.5
# Net move (in ATR units) gates.
SPIKE_NET_ATR = 2.0
SURGE_NET_ATR = 1.0
FADE_NET_ATR = -1.0
# Directional persistence (up-bars / (up+down), flat bars excluded).
STRONG_UP_FRAC = 0.6
MILD_UP_FRAC = 0.5


class Regime(str, Enum):
    FAST_SPIKE = "fast_spike"
    STEADY_SURGE = "steady_surge"
    MATURE_TREND = "mature_trend"
    STALL_FADE = "stall_fade"
    UNCERTAIN = "uncertain"


def classify(
    bars: Sequence[Bar],
    *,
    atr_now: Optional[float],
    atr_baseline: Optional[float],
) -> Regime:
    if (
        len(bars) < MIN_CLASSIFY_BARS
        or atr_now is None
        or atr_now <= 0
        or atr_baseline is None
        or atr_baseline <= 0
    ):
        return Regime.UNCERTAIN

    window = bars[-TREND_BARS:]
    net = window[-1].close - window[0].open
    net_atr = net / atr_now
    ups = sum(1 for b in window if b.close > b.open)
    downs = sum(1 for b in window if b.close < b.open)
    up_frac = ups / max(1, ups + downs)
    atr_ratio = atr_now / atr_baseline

    if fade_flag(bars, window=FADE_WINDOW, quantile=FADE_QUANTILE) or (
        net_atr <= FADE_NET_ATR
    ):
        return Regime.STALL_FADE
    if (
        atr_ratio >= SPIKE_ATR_RATIO
        and net_atr >= SPIKE_NET_ATR
        and up_frac >= STRONG_UP_FRAC
    ):
        return Regime.FAST_SPIKE
    if net_atr >= SURGE_NET_ATR and up_frac >= STRONG_UP_FRAC:
        return Regime.STEADY_SURGE
    if net_atr > 0 and up_frac >= MILD_UP_FRAC and atr_ratio <= MATURE_MAX_ATR_RATIO:
        return Regime.MATURE_TREND
    return Regime.UNCERTAIN
