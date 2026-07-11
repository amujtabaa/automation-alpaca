"""Session context — pure classification of an injected timestamp.

Deliberately DUPLICATES the Eastern session windows from ``app/features.py``
(pre 04:00–09:30, regular 09:30–16:00, after 16:00–20:00; inclusive start,
exclusive end; weekends None): the import contract forbids this package from
reaching the engine layer, and ``tests/test_wo0018_sellside_session.py`` pins
the same boundaries so the two copies cannot drift silently. Same holiday /
early-close caveats as the engine's copy (feed staleness surfaces those).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.models import SessionType

EASTERN = ZoneInfo("America/New_York")

_PRE_MARKET_START = time(4, 0)
_REGULAR_START = time(9, 30)
_REGULAR_END = time(16, 0)
_AFTER_HOURS_END = time(20, 0)

_PHASE_END: dict[SessionType, time] = {
    SessionType.PRE_MARKET: _REGULAR_START,
    SessionType.REGULAR: _REGULAR_END,
    SessionType.AFTER_HOURS: _AFTER_HOURS_END,
}


@dataclass(frozen=True)
class SessionContext:
    """The trading phase ``now`` falls in (None outside all windows) and the
    time remaining until that phase ends — the urgency ramp's input."""

    phase: Optional[SessionType]
    time_to_phase_close: Optional[timedelta]


def session_context(now: datetime) -> SessionContext:
    if now.tzinfo is None:
        raise ValueError("session_context requires a timezone-aware datetime")
    local_dt = now.astimezone(EASTERN)
    if local_dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return SessionContext(phase=None, time_to_phase_close=None)
    local = local_dt.time()
    if _PRE_MARKET_START <= local < _REGULAR_START:
        phase = SessionType.PRE_MARKET
    elif _REGULAR_START <= local < _REGULAR_END:
        phase = SessionType.REGULAR
    elif _REGULAR_END <= local < _AFTER_HOURS_END:
        phase = SessionType.AFTER_HOURS
    else:
        return SessionContext(phase=None, time_to_phase_close=None)
    end_local = local_dt.replace(
        hour=_PHASE_END[phase].hour,
        minute=_PHASE_END[phase].minute,
        second=0,
        microsecond=0,
    )
    return SessionContext(phase=phase, time_to_phase_close=end_local - local_dt)
