"""WO-0018 — sell-side session context: pure classification of an injected
timestamp into a trading phase + time-to-phase-close.

`app.sellside` may not import the engine layer (`app.features`), so it carries
its own session-window logic; these tests pin the SAME Eastern boundaries the
engine uses (pre 04:00–09:30, regular 09:30–16:00, after 16:00–20:00,
inclusive-start/exclusive-end, weekends None) so the two cannot drift silently.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import SessionType
from app.sellside.session import session_context

EASTERN = ZoneInfo("America/New_York")


def et(y, m, d, hh, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=EASTERN)


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError):
        session_context(datetime(2026, 7, 8, 10, 0, 0))


@pytest.mark.parametrize(
    "now,phase",
    [
        (et(2026, 7, 8, 4, 0), SessionType.PRE_MARKET),  # boundary inclusive
        (et(2026, 7, 8, 9, 29, 59), SessionType.PRE_MARKET),
        (et(2026, 7, 8, 9, 30), SessionType.REGULAR),  # boundary flips
        (et(2026, 7, 8, 15, 59, 59), SessionType.REGULAR),
        (et(2026, 7, 8, 16, 0), SessionType.AFTER_HOURS),
        (et(2026, 7, 8, 19, 59, 59), SessionType.AFTER_HOURS),
    ],
)
def test_phase_classification(now, phase):
    ctx = session_context(now)
    assert ctx.phase is phase


@pytest.mark.parametrize(
    "now",
    [
        et(2026, 7, 8, 3, 59, 59),  # overnight
        et(2026, 7, 8, 20, 0),  # after-hours end is exclusive
        et(2026, 7, 8, 23, 30),
        et(2026, 7, 11, 12, 0),  # Saturday
        et(2026, 7, 12, 12, 0),  # Sunday
    ],
)
def test_outside_all_windows_is_no_phase(now):
    ctx = session_context(now)
    assert ctx.phase is None
    assert ctx.time_to_phase_close is None


def test_time_to_phase_close_counts_down_to_the_phase_end():
    assert session_context(et(2026, 7, 8, 9, 0)).time_to_phase_close == timedelta(
        minutes=30
    )
    assert session_context(et(2026, 7, 8, 15, 30)).time_to_phase_close == timedelta(
        minutes=30
    )
    assert session_context(et(2026, 7, 8, 19, 0)).time_to_phase_close == timedelta(
        hours=1
    )


def test_utc_input_is_classified_in_eastern_terms():
    # 2026-07-08 14:00 UTC == 10:00 ET (EDT) → regular hours.
    ctx = session_context(datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc))
    assert ctx.phase is SessionType.REGULAR
    assert ctx.time_to_phase_close == timedelta(hours=6)
