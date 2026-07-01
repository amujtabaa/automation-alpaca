"""Feature Engine — pure functions, no IO (Rule 9). Phase 5."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.features import pct_move, session_type_for, spread, spread_pct
from app.models import SessionType


class TestPctMove:
    def test_positive_move(self):
        assert pct_move(103.0, 100.0) == pytest.approx(3.0)

    def test_negative_move(self):
        assert pct_move(97.0, 100.0) == pytest.approx(-3.0)

    def test_no_move(self):
        assert pct_move(100.0, 100.0) == pytest.approx(0.0)

    def test_missing_last_price(self):
        assert pct_move(None, 100.0) is None

    def test_missing_prev_close(self):
        assert pct_move(103.0, None) is None

    def test_zero_prev_close(self):
        assert pct_move(103.0, 0.0) is None

    def test_negative_prev_close(self):
        assert pct_move(103.0, -5.0) is None


class TestSpread:
    def test_normal_quote(self):
        assert spread(10.0, 10.05) == pytest.approx(0.05)

    def test_crossed_quote(self):
        assert spread(10.05, 10.0) is None

    def test_locked_quote(self):
        assert spread(10.0, 10.0) is None  # bid == ask, not a real two-sided market

    def test_missing_bid(self):
        assert spread(None, 10.05) is None

    def test_missing_ask(self):
        assert spread(10.0, None) is None


class TestSpreadPct:
    def test_normal(self):
        # spread 0.05 over midpoint 10.025 -> ~0.4988%
        assert spread_pct(10.0, 10.05) == pytest.approx(0.05 / 10.025 * 100.0)

    def test_crossed_quote(self):
        assert spread_pct(10.05, 10.0) is None

    def test_zero_midpoint(self):
        assert spread_pct(-0.05, 0.05) is None  # midpoint 0 — degenerate


class TestSessionTypeFor:
    def _et(self, y, m, d, h, minute, *, dst):
        # UTC offset: EST = UTC-5 (winter), EDT = UTC-4 (summer/DST). Use
        # timedelta arithmetic (not raw hour addition) so a late-evening ET
        # time near midnight UTC doesn't overflow datetime's hour bound.
        offset_hours = 4 if dst else 5
        local_naive = datetime(y, m, d, h, minute)
        return (local_naive + timedelta(hours=offset_hours)).replace(tzinfo=timezone.utc)

    def test_naive_datetime_rejected(self):
        with pytest.raises(ValueError):
            session_type_for(datetime(2026, 1, 7, 14, 30))

    def test_premarket_start_inclusive(self):
        assert session_type_for(self._et(2026, 1, 7, 4, 0, dst=False)) is SessionType.PRE_MARKET

    def test_just_before_premarket(self):
        assert session_type_for(self._et(2026, 1, 7, 3, 59, dst=False)) is None

    def test_regular_open_inclusive(self):
        assert session_type_for(self._et(2026, 1, 7, 9, 30, dst=False)) is SessionType.REGULAR

    def test_just_before_regular_open_is_premarket(self):
        assert session_type_for(self._et(2026, 1, 7, 9, 29, dst=False)) is SessionType.PRE_MARKET

    def test_regular_close_exclusive_is_afterhours(self):
        assert session_type_for(self._et(2026, 1, 7, 16, 0, dst=False)) is SessionType.AFTER_HOURS

    def test_just_before_regular_close(self):
        assert session_type_for(self._et(2026, 1, 7, 15, 59, dst=False)) is SessionType.REGULAR

    def test_afterhours_end_exclusive_is_none(self):
        assert session_type_for(self._et(2026, 1, 7, 20, 0, dst=False)) is None

    def test_just_before_afterhours_end(self):
        assert session_type_for(self._et(2026, 1, 7, 19, 59, dst=False)) is SessionType.AFTER_HOURS

    def test_overnight_is_none(self):
        assert session_type_for(self._et(2026, 1, 7, 2, 0, dst=False)) is None

    @pytest.mark.parametrize("dst", [False, True])
    def test_dst_transparency_regular_open(self, dst):
        # 9:30 ET local time resolves to REGULAR regardless of EST/EDT UTC offset.
        assert session_type_for(self._et(2026, 6, 1, 9, 30, dst=dst)) is SessionType.REGULAR

    def test_saturday_is_none(self):
        # 2026-01-10 is a Saturday.
        assert session_type_for(self._et(2026, 1, 10, 10, 30, dst=False)) is None

    def test_sunday_is_none(self):
        # 2026-01-11 is a Sunday.
        assert session_type_for(self._et(2026, 1, 11, 10, 30, dst=False)) is None

    def test_friday_still_evaluates(self):
        # 2026-01-09 is a Friday.
        assert session_type_for(self._et(2026, 1, 9, 10, 30, dst=False)) is SessionType.REGULAR
