"""WO-0018 — volume profiler: an immutable rolling window over the feed's
cumulative session volume, yielding recent traded volume and a
participation-capped size. Pure data in, pure data out — no clock reads."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.sellside.profiler import (
    VolumeWindow,
    observe,
    participation_size,
    recent_volume,
)


def ts(minute: int, second: int = 0) -> datetime:
    return datetime(2026, 7, 8, 14, minute, second, tzinfo=timezone.utc)


def build(horizon_minutes: int = 5) -> VolumeWindow:
    return VolumeWindow(horizon=timedelta(minutes=horizon_minutes))


def test_window_starts_empty_with_zero_recent_volume():
    w = build()
    assert w.observations == ()
    assert recent_volume(w) == 0.0


def test_observe_is_immutable_append():
    w0 = build()
    w1 = observe(w0, at=ts(0), cumulative_volume=1000.0)
    assert w0.observations == ()  # the input window is untouched
    assert len(w1.observations) == 1


def test_recent_volume_is_the_delta_across_the_window():
    w = build()
    w = observe(w, at=ts(0), cumulative_volume=1000.0)
    w = observe(w, at=ts(1), cumulative_volume=1600.0)
    w = observe(w, at=ts(2), cumulative_volume=1900.0)
    assert recent_volume(w) == 900.0  # 1900 - 1000


def test_observations_older_than_the_horizon_are_pruned():
    w = build(horizon_minutes=5)
    w = observe(w, at=ts(0), cumulative_volume=1000.0)
    w = observe(w, at=ts(1), cumulative_volume=1500.0)
    w = observe(w, at=ts(7), cumulative_volume=2000.0)  # ts(0..1) now stale
    assert [o.at for o in w.observations] == [ts(7)]
    # A single observation spans no interval → no measurable recent volume.
    assert recent_volume(w) == 0.0


def test_cumulative_reset_is_treated_as_a_fresh_baseline():
    """A LOWER cumulative volume (feed restart / new session) must not produce
    negative recent volume — the window resets to the new baseline."""

    w = build()
    w = observe(w, at=ts(0), cumulative_volume=5000.0)
    w = observe(w, at=ts(1), cumulative_volume=100.0)  # reset
    w = observe(w, at=ts(2), cumulative_volume=400.0)
    assert recent_volume(w) == 300.0
    assert recent_volume(w) >= 0.0


def test_none_and_nonfinite_observations_are_ignored():
    w = build()
    w = observe(w, at=ts(0), cumulative_volume=1000.0)
    w = observe(w, at=ts(1), cumulative_volume=None)
    w = observe(w, at=ts(2), cumulative_volume=float("nan"))
    w = observe(w, at=ts(3), cumulative_volume=float("inf"))
    w = observe(w, at=ts(4), cumulative_volume=-50.0)
    w = observe(w, at=ts(5), cumulative_volume=1800.0)
    assert len(w.observations) == 2
    assert recent_volume(w) == 800.0


@pytest.mark.parametrize(
    "recent,cap,remaining,expected",
    [
        (1000.0, 0.20, 500, 200),  # 20% of 1000
        (1000.0, 0.20, 150, 150),  # capped by remaining
        (10.0, 0.20, 500, 2),
        (4.0, 0.20, 500, 0),  # floor(0.8) → 0: too thin to place
        (0.0, 1.0, 500, 0),
    ],
)
def test_participation_size_floors_and_caps(recent, cap, remaining, expected):
    assert participation_size(recent, cap, remaining) == expected
