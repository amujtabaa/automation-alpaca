"""Phase 5 config: env-var parsing, validation, and defaults for the market-data
feed and Strategy Engine knobs.

Before this file, none of MARKET_DATA_FEED, MARKET_DATA_STALE_MINUTES,
ENABLE_STRATEGY_ENGINE, or the six STRATEGY_* env vars had any dedicated
config-level test — a real gap found during a self-review sweep, distinct from
(and in addition to) the ones test_config_nonfinite.py already covers for
Phase 4's cadence/timeout.
"""

from __future__ import annotations

import pytest

from app.config import (
    ENABLE_STRATEGY_ENGINE_ENV,
    MARKET_DATA_FEED_ENV,
    MARKET_DATA_STALE_MINUTES_ENV,
    STRATEGY_DECISION_CADENCE_ENV,
    STRATEGY_DEFAULT_QUANTITY_ENV,
    STRATEGY_LIMIT_BUFFER_ENV,
    STRATEGY_MAX_SPREAD_ENV,
    STRATEGY_MIN_VOLUME_ENV,
    STRATEGY_MOMENTUM_THRESHOLD_ENV,
    load_settings,
)

_ALL_PHASE5_ENVS = [
    MARKET_DATA_FEED_ENV,
    MARKET_DATA_STALE_MINUTES_ENV,
    ENABLE_STRATEGY_ENGINE_ENV,
    STRATEGY_DECISION_CADENCE_ENV,
    STRATEGY_MOMENTUM_THRESHOLD_ENV,
    STRATEGY_MIN_VOLUME_ENV,
    STRATEGY_MAX_SPREAD_ENV,
    STRATEGY_LIMIT_BUFFER_ENV,
    STRATEGY_DEFAULT_QUANTITY_ENV,
]


def _clear(monkeypatch):
    for env in _ALL_PHASE5_ENVS:
        monkeypatch.delenv(env, raising=False)


class TestDefaults:
    def test_defaults_match_documented_values(self, monkeypatch):
        _clear(monkeypatch)
        settings = load_settings()
        assert settings.market_data_feed == "auto"
        assert settings.market_data_stale_minutes == 5.0
        assert settings.enable_strategy_engine is True
        assert settings.strategy_decision_cadence_seconds == 5.0
        assert settings.strategy_momentum_threshold_pct == 3.0
        assert settings.strategy_min_volume == 50_000.0
        assert settings.strategy_max_spread_pct == 1.0
        assert settings.strategy_limit_buffer_pct == 0.1
        assert settings.strategy_default_quantity == 10


class TestMarketDataFeed:
    @pytest.mark.parametrize("value", ["auto", "mock", "alpaca"])
    def test_valid_values_accepted(self, monkeypatch, value):
        _clear(monkeypatch)
        monkeypatch.setenv(MARKET_DATA_FEED_ENV, value)
        assert load_settings().market_data_feed == value

    def test_invalid_value_rejected(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(MARKET_DATA_FEED_ENV, "bogus")
        with pytest.raises(ValueError):
            load_settings()

    def test_case_insensitive(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(MARKET_DATA_FEED_ENV, "ALPACA")
        assert load_settings().market_data_feed == "alpaca"


class TestEnableStrategyEngine:
    @pytest.mark.parametrize("value,expected", [("true", True), ("false", False), ("0", False), ("1", True)])
    def test_parses_bool(self, monkeypatch, value, expected):
        _clear(monkeypatch)
        monkeypatch.setenv(ENABLE_STRATEGY_ENGINE_ENV, value)
        assert load_settings().enable_strategy_engine is expected


class TestNonFiniteRejected:
    """NaN/Inf must fail fast at load, same rationale as test_config_nonfinite.py:
    a NaN cadence silently stalls the loop rather than erroring visibly."""

    @pytest.mark.parametrize(
        "env",
        [
            MARKET_DATA_STALE_MINUTES_ENV,
            STRATEGY_DECISION_CADENCE_ENV,
            STRATEGY_MOMENTUM_THRESHOLD_ENV,
            STRATEGY_MIN_VOLUME_ENV,
            STRATEGY_MAX_SPREAD_ENV,
            STRATEGY_LIMIT_BUFFER_ENV,
        ],
    )
    @pytest.mark.parametrize("bad", ["nan", "inf", "-inf"])
    def test_nonfinite_rejected(self, monkeypatch, env, bad):
        _clear(monkeypatch)
        monkeypatch.setenv(env, bad)
        with pytest.raises(ValueError):
            load_settings()


class TestMarketDataStaleMinutesMinimum:
    """0 makes every snapshot permanently stale, silently zeroing out the
    Strategy Engine's entire output — must be rejected, not just NaN/Inf."""

    def test_zero_rejected(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(MARKET_DATA_STALE_MINUTES_ENV, "0")
        with pytest.raises(ValueError):
            load_settings()

    def test_negative_rejected(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(MARKET_DATA_STALE_MINUTES_ENV, "-1")
        with pytest.raises(ValueError):
            load_settings()

    def test_small_positive_accepted(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(MARKET_DATA_STALE_MINUTES_ENV, "0.5")
        assert load_settings().market_data_stale_minutes == 0.5


class TestStrategyMaxSpreadMinimum:
    """0 reads like 'no spread limit' but means the opposite (requires a
    literally-zero spread) — same footgun class as stale-minutes=0."""

    def test_zero_rejected(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_MAX_SPREAD_ENV, "0")
        with pytest.raises(ValueError):
            load_settings()

    def test_small_positive_accepted(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_MAX_SPREAD_ENV, "0.1")
        assert load_settings().strategy_max_spread_pct == 0.1

    def test_large_value_effectively_disables_the_check(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_MAX_SPREAD_ENV, "100")
        assert load_settings().strategy_max_spread_pct == 100.0


class TestStrategyDecisionCadenceMinimum:
    """Same rationale as POLL_CADENCE_ENV: zero/negative would busy-loop."""

    def test_zero_rejected(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_DECISION_CADENCE_ENV, "0")
        with pytest.raises(ValueError):
            load_settings()


class TestMomentumThresholdAndMinVolumeAllowZero:
    """Unlike stale-minutes/max-spread, 0 is a legitimate, intuitively-correct
    'no floor' setting for these two — the Strategy Engine's own move<=0 gate
    (app/strategy.py) independently prevents a zero threshold from proposing
    on a zero/negative move, so 0 does not silently break candidate output."""

    def test_zero_momentum_threshold_accepted(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_MOMENTUM_THRESHOLD_ENV, "0")
        assert load_settings().strategy_momentum_threshold_pct == 0.0

    def test_zero_min_volume_accepted(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_MIN_VOLUME_ENV, "0")
        assert load_settings().strategy_min_volume == 0.0


class TestStrategyDefaultQuantity:
    def test_must_be_a_whole_number(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_DEFAULT_QUANTITY_ENV, "2.5")
        with pytest.raises(ValueError):
            load_settings()

    def test_must_be_at_least_one(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_DEFAULT_QUANTITY_ENV, "0")
        with pytest.raises(ValueError):
            load_settings()

    def test_valid_integer_accepted(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(STRATEGY_DEFAULT_QUANTITY_ENV, "25")
        assert load_settings().strategy_default_quantity == 25
        assert isinstance(load_settings().strategy_default_quantity, int)
