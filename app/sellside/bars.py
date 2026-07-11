"""Pure bar aggregation from the snapshot tape (WO-0018).

The policy has no external bar feed: internal bars are built from the
session-anchored ``MarketSnapshot`` sequence the tick passes in. A snapshot
contributes a price point iff ``last_price`` is finite and positive; volume
derives from deltas of the feed's CUMULATIVE session volume (resets — feed
restarts / new session — floor at the intra-bar delta, never negative).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence

from app.marketdata.service import MarketSnapshot


@dataclass(frozen=True)
class Bar:
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def _finite_positive(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(value) and value > 0


def _finite_volume(value: Optional[float]) -> bool:
    return value is not None and math.isfinite(value) and value >= 0


def aggregate(
    snapshots: Sequence[MarketSnapshot], interval: timedelta
) -> tuple[Bar, ...]:
    """OHLCV bars on the ``interval`` grid. Buckets with no valid price are
    skipped (thin extended-hours tape: silence is silence, not a zero bar)."""

    seconds = interval.total_seconds()
    if seconds <= 0:
        raise ValueError("bar interval must be positive")

    buckets: dict[int, list[MarketSnapshot]] = {}
    for snap in snapshots:
        if not _finite_positive(snap.last_price):
            continue
        buckets.setdefault(int(snap.updated_at.timestamp() // seconds), []).append(snap)

    bars: list[Bar] = []
    prev_cum: Optional[float] = None
    for index in sorted(buckets):
        rows = sorted(buckets[index], key=lambda s: s.updated_at)
        # Bucket membership already required a finite positive last_price /
        # valid volume; the `is not None` re-checks are for the type narrower.
        prices = [s.last_price for s in rows if s.last_price is not None]
        cums = [
            s.volume for s in rows if s.volume is not None and _finite_volume(s.volume)
        ]
        if cums:
            first_cum, last_cum = cums[0], cums[-1]
            if prev_cum is None:
                volume = max(0.0, last_cum - first_cum)
            else:
                delta = last_cum - prev_cum
                # Cumulative reset: fall back to the intra-bar delta.
                volume = delta if delta >= 0 else max(0.0, last_cum - first_cum)
            prev_cum = last_cum
        else:
            volume = 0.0
        start = datetime.fromtimestamp(index * seconds, tz=rows[0].updated_at.tzinfo)
        bars.append(
            Bar(
                start=start,
                end=start + interval,
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=volume,
            )
        )
    return tuple(bars)
