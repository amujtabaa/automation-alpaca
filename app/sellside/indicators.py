"""Pure indicators over internal bars / the snapshot tape (WO-0018).

Mechanisms per pkl/architecture/sellside-research-notes.md: ATR (gap-aware
true range, simple mean — Wilder smoothing is a W4 tuning question),
session-anchored VWAP from cumulative-volume deltas, RVOL as a
self-calibrating short/long volume-rate ratio, and the nonparametric
historical-quantile fade detector.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from app.marketdata.service import MarketSnapshot

from app.sellside.bars import Bar


def atr(bars: Sequence[Bar], period: int) -> Optional[float]:
    """Mean true range of the last ``period`` TRs; None when there are fewer.
    TR is gap-aware (uses the prior close); the first bar seeds with its own
    range."""

    if period <= 0 or len(bars) < 2:
        return None
    trs: list[float] = [bars[0].high - bars[0].low]
    for prev, cur in zip(bars, bars[1:]):
        trs.append(
            max(
                cur.high - cur.low,
                abs(cur.high - prev.close),
                abs(cur.low - prev.close),
            )
        )
    if len(trs) < period:
        return None
    window = trs[-period:]
    return sum(window) / period


def ema(values: Sequence[float], period: int) -> Optional[float]:
    """Standard EMA seeded on the first value; None on empty input."""

    if not values or period <= 0:
        return None
    alpha = 2.0 / (period + 1.0)
    out = values[0]
    for v in values[1:]:
        out = alpha * v + (1.0 - alpha) * out
    return out


def anchored_vwap(snapshots: Sequence[MarketSnapshot]) -> Optional[float]:
    """Volume-weighted average price anchored at the start of the provided
    tape (the caller anchors the tape at the extended-session open). Weights
    are CUMULATIVE-volume deltas; a reset re-baselines without contributing."""

    prev_cum: Optional[float] = None
    sum_pv = 0.0
    sum_v = 0.0
    for snap in snapshots:
        price, cum = snap.last_price, snap.volume
        if cum is None or not math.isfinite(cum) or cum < 0:
            continue
        if price is None or not math.isfinite(price) or price <= 0:
            continue
        if prev_cum is not None:
            delta = cum - prev_cum
            if delta > 0:
                sum_pv += price * delta
                sum_v += delta
        prev_cum = cum
    return sum_pv / sum_v if sum_v > 0 else None


def rvol(bars: Sequence[Bar], *, short_bars: int, long_bars: int) -> Optional[float]:
    """Relative volume: short-window average bar volume over the long-window
    baseline — self-calibrating from the tape itself (no external baseline
    data exists for extended-hours penny names). None until warm."""

    if short_bars <= 0 or long_bars <= short_bars or len(bars) < long_bars:
        return None
    short = [b.volume for b in bars[-short_bars:]]
    long = [b.volume for b in bars[-long_bars:]]
    base = sum(long) / long_bars
    if base <= 0:
        return None
    return (sum(short) / short_bars) / base


def fade_flag(bars: Sequence[Bar], *, window: int, quantile: float) -> bool:
    """True when the LATEST bar return is negative AND strictly below the
    empirical ``quantile`` of its own trailing ``window`` returns —
    nonparametric pullback-vs-reversal discriminator. Strict inequality so a
    return merely EQUAL to the tape's routine wiggle never flags (chop
    immunity); needs a full window of history, else False (fail quiet — the
    trail floor still protects)."""

    closes = [b.close for b in bars]
    if len(closes) < window + 2:
        return False
    returns = [(b / a) - 1.0 for a, b in zip(closes, closes[1:]) if a > 0]
    if len(returns) < window + 1:
        return False
    last = returns[-1]
    if last >= 0:
        return False
    dist = sorted(returns[-(window + 1) : -1])
    idx = int(quantile * (len(dist) - 1))
    if not last < dist[idx]:
        return False
    # Median-scale gate: after a monotone grind the distribution holds almost
    # no negatives, so every sub-noise dip is "record-breaking" — require the
    # move to also exceed the window's median absolute return (self-scaling,
    # no tuned constant), so only tape-scale moves flag.
    magnitudes = sorted(abs(r) for r in dist)
    median_move = magnitudes[len(magnitudes) // 2]
    return abs(last) > median_move
