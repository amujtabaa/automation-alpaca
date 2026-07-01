"""The Feature Engine: pure functions deriving trading signals from a raw
:class:`~app.marketdata.service.MarketSnapshot`.

No IO, no state, no async — mirrors ``app/position.py``'s style so it is
trivially unit-testable with synthetic inputs. Every function returns ``None``
rather than fabricating a value when its inputs don't support a real answer
(missing prior close, crossed/missing quote, outside all defined trading
sessions) — the Strategy Engine treats ``None`` as "can't evaluate this
symbol right now," never as zero.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from app.models import SessionType

_EASTERN = ZoneInfo("America/New_York")

# US equity session boundaries, Eastern time (docs/02: premarket/after-hours
# feed quality is an empirical unknown to verify separately — these boundaries
# are the standard Alpaca/exchange convention, not something to verify here).
_PRE_MARKET_START = time(4, 0)
_REGULAR_START = time(9, 30)
_REGULAR_END = time(16, 0)
_AFTER_HOURS_END = time(20, 0)


def pct_move(last_price: Optional[float], prev_close: Optional[float]) -> Optional[float]:
    """Percent move of ``last_price`` versus ``prev_close`` (e.g. ``3.2`` = +3.2%).

    ``None`` if either input is missing or ``prev_close`` is non-positive (a
    percentage against zero/negative is not a meaningful number, not zero).
    """

    if last_price is None or prev_close is None or prev_close <= 0:
        return None
    return (last_price - prev_close) / prev_close * 100.0


def spread(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    """Absolute bid/ask spread, or ``None`` on a missing or crossed quote."""

    if bid is None or ask is None or bid >= ask:
        return None
    return ask - bid


def spread_pct(bid: Optional[float], ask: Optional[float]) -> Optional[float]:
    """Spread as a percent of the midpoint, or ``None`` on a missing/crossed quote."""

    s = spread(bid, ask)
    if s is None:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return s / mid * 100.0


def session_type_for(dt: datetime) -> Optional[SessionType]:
    """Classify ``dt`` into a trading session by US/Eastern time-of-day.

    ``dt`` must be timezone-aware (naive input is ambiguous and rejected via
    :class:`ValueError` rather than silently assumed to be UTC or Eastern).
    Returns ``None`` outside all three windows (overnight/weekend by clock
    time — this is a time-of-day classification only; it does not check the
    exchange holiday calendar). The Strategy Engine simply does not evaluate
    when this is ``None``.

    Boundaries (Eastern): pre-market 04:00–09:30, regular 09:30–16:00,
    after-hours 16:00–20:00. Each window is inclusive of its start, exclusive
    of its end, so the boundaries themselves resolve to exactly one session.
    Saturday/Sunday (by Eastern local date) always return ``None`` — equities
    do not trade on weekends regardless of clock time. Exchange holidays are
    NOT checked (no holiday calendar here); a holiday's true state is that the
    feed simply never ticks, which the staleness check surfaces instead.
    """

    if dt.tzinfo is None:
        raise ValueError("session_type_for requires a timezone-aware datetime")
    local_dt = dt.astimezone(_EASTERN)
    if local_dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return None
    local = local_dt.time()
    if _PRE_MARKET_START <= local < _REGULAR_START:
        return SessionType.PRE_MARKET
    if _REGULAR_START <= local < _REGULAR_END:
        return SessionType.REGULAR
    if _REGULAR_END <= local < _AFTER_HOURS_END:
        return SessionType.AFTER_HOURS
    return None
