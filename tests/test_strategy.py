"""Strategy Engine — pure evaluate(), no IO (Rule 9). Phase 5.

Each gate is tested independently so a future strategy change that loosens
one gate can't silently loosen another.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.marketdata.service import MarketSnapshot
from app.models import SessionType
from app.strategy import RISK_DECISION_PLACEHOLDER, STRATEGY_ID, evaluate

_DEFAULTS = dict(
    momentum_threshold_pct=3.0,
    min_volume=50_000,
    max_spread_pct=1.0,
    limit_buffer_pct=0.1,
    default_quantity=10,
)


def _snapshot(**kw) -> MarketSnapshot:
    defaults = dict(
        symbol="AAPL",
        last_price=None,
        bid=None,
        ask=None,
        volume=None,
        prev_close=None,
        updated_at=datetime.now(timezone.utc),
        stale=False,
    )
    defaults.update(kw)
    return MarketSnapshot(**defaults)


def _evaluate(snapshot, session_type=SessionType.PRE_MARKET, *, has_open_candidate=False, **overrides):
    kwargs = dict(_DEFAULTS)
    kwargs.update(overrides)
    return evaluate(
        "AAPL", snapshot, session_type, has_open_candidate=has_open_candidate, **kwargs
    )


_HEALTHY = dict(last_price=103.0, prev_close=100.0, bid=102.9, ask=103.1, volume=100_000)


class TestHappyPath:
    def test_proposes_when_all_gates_pass(self):
        proposal = _evaluate(_snapshot(**_HEALTHY))
        assert proposal is not None
        assert proposal.symbol == "AAPL"
        assert proposal.strategy == STRATEGY_ID
        assert proposal.risk_decision == RISK_DECISION_PLACEHOLDER
        assert proposal.suggested_quantity == 10
        assert "3.0%" in proposal.reason
        assert "pre_market" in proposal.reason

    def test_limit_price_is_last_price_plus_buffer(self):
        # suggested_limit_price is rounded to cents (a real order needs a
        # cents-precision limit, not a floating-point fraction of a cent).
        proposal = _evaluate(_snapshot(**_HEALTHY), limit_buffer_pct=0.5)
        assert proposal.suggested_limit_price == pytest.approx(round(103.0 * 1.005, 2))

    def test_after_hours_also_eligible(self):
        assert _evaluate(_snapshot(**_HEALTHY), SessionType.AFTER_HOURS) is not None


class TestSessionGate:
    def test_regular_session_excluded(self):
        assert _evaluate(_snapshot(**_HEALTHY), SessionType.REGULAR) is None

    def test_none_session_excluded(self):
        assert _evaluate(_snapshot(**_HEALTHY), None) is None


class TestSnapshotGate:
    def test_missing_snapshot(self):
        assert _evaluate(None) is None

    def test_stale_snapshot_blocks(self):
        assert _evaluate(_snapshot(**_HEALTHY, stale=True)) is None


class TestMomentumGate:
    def test_below_threshold(self):
        s = _snapshot(last_price=101.0, prev_close=100.0, bid=100.9, ask=101.1, volume=100_000)
        assert _evaluate(s) is None

    def test_exactly_at_threshold_proposes(self):
        s = _snapshot(last_price=103.0, prev_close=100.0, bid=102.9, ask=103.1, volume=100_000)
        assert _evaluate(s) is not None  # move is exactly 3.0%, threshold 3.0%

    def test_negative_move_never_proposes(self):
        s = _snapshot(last_price=95.0, prev_close=100.0, bid=94.9, ask=95.1, volume=100_000)
        assert _evaluate(s) is None

    def test_zero_move_never_proposes_even_with_zero_threshold(self):
        s = _snapshot(last_price=100.0, prev_close=100.0, bid=99.9, ask=100.1, volume=100_000)
        assert _evaluate(s, momentum_threshold_pct=0.0) is None

    def test_missing_prev_close_blocks(self):
        s = _snapshot(last_price=103.0, prev_close=None, bid=102.9, ask=103.1, volume=100_000)
        assert _evaluate(s) is None


class TestVolumeGate:
    def test_below_min_volume(self):
        s = _snapshot(**{**_HEALTHY, "volume": 1_000})
        assert _evaluate(s) is None

    def test_missing_volume_blocks(self):
        s = _snapshot(**{**_HEALTHY, "volume": None})
        assert _evaluate(s) is None

    def test_exactly_at_min_volume_proposes(self):
        s = _snapshot(**{**_HEALTHY, "volume": 50_000})
        assert _evaluate(s) is not None


class TestSpreadGate:
    def test_wide_spread_blocks(self):
        s = _snapshot(**{**_HEALTHY, "bid": 100.0, "ask": 106.0})
        assert _evaluate(s) is None

    def test_crossed_quote_blocks(self):
        s = _snapshot(**{**_HEALTHY, "bid": 103.5, "ask": 103.0})
        assert _evaluate(s) is None

    def test_missing_quote_blocks(self):
        s = _snapshot(**{**_HEALTHY, "bid": None, "ask": None})
        assert _evaluate(s) is None


class TestDedupGate:
    def test_open_candidate_blocks(self):
        assert _evaluate(_snapshot(**_HEALTHY), has_open_candidate=True) is None
