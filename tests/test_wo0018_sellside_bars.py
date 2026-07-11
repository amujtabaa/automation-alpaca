"""WO-0018 — market-structure inputs: bar aggregator, ATR, anchored VWAP,
RVOL, and the historical-quantile fade detector. All pure functions of the
snapshot tape / bar sequence — no clock reads, no IO."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.marketdata.service import MarketSnapshot
from app.sellside.bars import Bar, aggregate
from app.sellside.indicators import (
    anchored_vwap,
    atr,
    fade_flag,
    rvol,
)

T0 = datetime(2026, 7, 8, 14, 0, 0, tzinfo=timezone.utc)


def snap(seconds: float, price: float, volume: float) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="AAPL",
        last_price=price,
        bid=price - 0.01,
        ask=price + 0.01,
        volume=volume,
        prev_close=9.0,
        updated_at=T0 + timedelta(seconds=seconds),
    )


def bar(i: int, o: float, h: float, lo: float, c: float, v: float = 100.0) -> Bar:
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


# --- aggregator -------------------------------------------------------------- #


def test_aggregate_buckets_ohlcv_on_the_interval_grid():
    tape = [
        snap(0, 10.00, 1000),
        snap(2, 10.10, 1200),
        snap(4, 9.95, 1500),  # bar 1: o=10.00 h=10.10 l=9.95 c=9.95 v=500
        snap(5, 10.05, 1600),
        snap(9, 10.20, 2100),  # bar 2: o=10.05 h=10.20 l=10.05 c=10.20 v=600
    ]
    bars = aggregate(tape, timedelta(seconds=5))
    assert len(bars) == 2
    b1, b2 = bars
    assert (b1.open, b1.high, b1.low, b1.close) == (10.00, 10.10, 9.95, 9.95)
    assert b1.volume == 500.0  # cumulative 1500 - baseline 1000
    assert (b2.open, b2.high, b2.low, b2.close) == (10.05, 10.20, 10.05, 10.20)
    assert b2.volume == 600.0


def test_aggregate_skips_invalid_snapshots_and_empty_buckets():
    tape = [
        snap(0, 10.00, 1000),
        MarketSnapshot(
            symbol="AAPL",
            last_price=float("nan"),
            bid=None,
            ask=None,
            volume=1100.0,
            prev_close=9.0,
            updated_at=T0 + timedelta(seconds=1),
        ),
        snap(2, 10.06, 1200),
        # 5s..15s: silence — no bucket rows emitted
        snap(16, 10.02, 1300),
    ]
    bars = aggregate(tape, timedelta(seconds=5))
    assert [b.close for b in bars] == [10.06, 10.02]


def test_aggregate_volume_reset_floors_at_zero():
    tape = [snap(0, 10.0, 5000), snap(6, 10.1, 100), snap(7, 10.1, 200)]
    bars = aggregate(tape, timedelta(seconds=5))
    assert all(b.volume >= 0 for b in bars)


# --- ATR ---------------------------------------------------------------------- #


def test_atr_is_mean_true_range_over_the_period():
    bars = [
        bar(0, 10.0, 10.2, 9.9, 10.1),  # TR seed: high-low = 0.3
        bar(1, 10.1, 10.4, 10.0, 10.3),  # TR = max(0.4, 0.3, 0.1) = 0.4
        bar(2, 10.3, 10.5, 10.2, 10.4),  # TR = max(0.3, 0.2, 0.1) = 0.3
    ]
    assert atr(bars, period=3) == pytest.approx((0.3 + 0.4 + 0.3) / 3)


def test_atr_uses_gap_aware_true_range():
    bars = [
        bar(0, 10.0, 10.1, 9.9, 10.0),
        bar(1, 12.0, 12.1, 11.9, 12.0),  # gap up: TR = |12.1 - 10.0| = 2.1
    ]
    assert atr(bars, period=2) == pytest.approx((0.2 + 2.1) / 2)


def test_atr_insufficient_bars_is_none():
    assert atr([], period=3) is None
    assert atr([bar(0, 10, 10.1, 9.9, 10.0)], period=3) is None


# --- anchored VWAP ------------------------------------------------------------ #


def test_anchored_vwap_weights_price_by_volume_delta_from_the_anchor():
    tape = [
        snap(0, 10.00, 1000),  # anchor/baseline — no delta yet
        snap(5, 10.00, 2000),  # 1000 shares @ 10.00
        snap(10, 11.00, 2500),  # 500 shares @ 11.00
    ]
    # (1000*10 + 500*11) / 1500
    assert anchored_vwap(tape) == pytest.approx(10.3333333, rel=1e-6)


def test_anchored_vwap_with_no_traded_volume_is_none():
    assert anchored_vwap([snap(0, 10.0, 1000)]) is None
    assert anchored_vwap([]) is None


# --- RVOL ---------------------------------------------------------------------- #


def test_rvol_compares_short_window_rate_to_long_baseline():
    bars = [bar(i, 10, 10.1, 9.9, 10.0, v=100.0) for i in range(8)]
    bars += [bar(8, 10, 10.1, 9.9, 10.0, v=300.0), bar(9, 10, 10.1, 9.9, 10.0, v=300.0)]
    # short window (2 bars): 300 avg; long window (10 bars): 140 avg.
    assert rvol(bars, short_bars=2, long_bars=10) == pytest.approx(300 / 140)


def test_rvol_insufficient_history_is_none():
    bars = [bar(0, 10, 10.1, 9.9, 10.0)]
    assert rvol(bars, short_bars=2, long_bars=10) is None


# --- quantile fade detector ----------------------------------------------------- #


def test_fade_flag_fires_only_on_a_lowest_quantile_negative_return():
    # 20 flat-to-up bars, then one hard down bar → its return sits in the
    # bottom decile of the trailing distribution AND is negative → flag.
    closes = [10.0 + 0.01 * i for i in range(20)]
    bars = [bar(i, c, c + 0.02, c - 0.02, c) for i, c in enumerate(closes)]
    down = bar(20, closes[-1], closes[-1], closes[-1] - 0.5, closes[-1] - 0.5)
    assert fade_flag(bars + [down], window=16, quantile=0.10) is True
    # The same tape WITHOUT the crash bar does not flag.
    assert fade_flag(bars, window=16, quantile=0.10) is False


def test_fade_flag_needs_enough_history():
    bars = [bar(i, 10, 10.1, 9.9, 10.0 - 0.1 * i) for i in range(4)]
    assert fade_flag(bars, window=16, quantile=0.10) is False


def test_fade_flag_never_fires_on_a_positive_return():
    closes = [10.0 - 0.05 * i for i in range(20)]  # steady decline...
    bars = [bar(i, c, c + 0.02, c - 0.02, c) for i, c in enumerate(closes)]
    up = bar(20, closes[-1], closes[-1] + 0.3, closes[-1], closes[-1] + 0.3)
    assert fade_flag(bars + [up], window=16, quantile=0.10) is False
