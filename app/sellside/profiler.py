"""Volume profiler — an immutable rolling window over the feed's cumulative
session volume (WO-0018). Feeds participation-aware sizing: never plan a
size the observed tape could not absorb (liquidity-aware by construction).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass(frozen=True)
class VolumeObservation:
    at: datetime
    cumulative_volume: float


@dataclass(frozen=True)
class VolumeWindow:
    horizon: timedelta
    observations: tuple[VolumeObservation, ...] = field(default_factory=tuple)


def observe(
    window: VolumeWindow, *, at: datetime, cumulative_volume: Optional[float]
) -> VolumeWindow:
    """Append one cumulative-volume observation and prune everything older
    than the horizon. Invalid observations (None / non-finite / negative) are
    ignored — bad data never enters sizing (safety rails). Pure: returns a
    NEW window."""

    if (
        cumulative_volume is None
        or not math.isfinite(cumulative_volume)
        or cumulative_volume < 0
    ):
        return window
    kept = tuple(o for o in window.observations if o.at >= at - window.horizon) + (
        VolumeObservation(at=at, cumulative_volume=cumulative_volume),
    )
    return VolumeWindow(horizon=window.horizon, observations=kept)


def recent_volume(window: VolumeWindow) -> float:
    """Traded volume across the window: the sum of POSITIVE consecutive
    deltas. A cumulative reset (feed restart / new session) re-baselines
    instead of producing negative volume."""

    total = 0.0
    for a, b in zip(window.observations, window.observations[1:]):
        delta = b.cumulative_volume - a.cumulative_volume
        if delta > 0:
            total += delta
    return total


def participation_size(recent: float, cap: float, remaining: int) -> int:
    """Largest size the participation cap allows: floor(cap × recent volume),
    never beyond the envelope's remaining quantity. 0 = the tape is too thin
    to place anything (the policy returns NO_LIQUIDITY, not a 1-share probe —
    probing is the STOP path's prerogative, not the tranche path's)."""

    if recent <= 0 or cap <= 0 or remaining <= 0:
        return 0
    return min(remaining, int(cap * recent))
