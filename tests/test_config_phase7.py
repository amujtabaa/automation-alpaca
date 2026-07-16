"""Phase 7 config: env-var parsing, validation, and defaults for the Sell-Side
Protection knobs (PROTECTION_ENABLED / _STOP_LOSS_PCT / _LIMIT_BUFFER_PCT /
_CADENCE_SECONDS).
"""

from __future__ import annotations

import pytest

from app.config import (
    PROTECTION_CADENCE_SECONDS_ENV,
    PROTECTION_ENABLED_ENV,
    PROTECTION_LIMIT_BUFFER_PCT_ENV,
    PROTECTION_STOP_LOSS_PCT_ENV,
    load_settings,
)

_ALL_PHASE7_ENVS = [
    PROTECTION_ENABLED_ENV,
    PROTECTION_STOP_LOSS_PCT_ENV,
    PROTECTION_LIMIT_BUFFER_PCT_ENV,
    PROTECTION_CADENCE_SECONDS_ENV,
]


def _clear(monkeypatch):
    for env in _ALL_PHASE7_ENVS:
        monkeypatch.delenv(env, raising=False)


class TestDefaults:
    def test_defaults(self, monkeypatch):
        _clear(monkeypatch)
        s = load_settings()
        assert s.protection_enabled is True
        assert s.protection_stop_loss_pct == pytest.approx(0.08)
        assert s.protection_limit_buffer_pct == pytest.approx(0.005)
        assert s.protection_cadence_seconds is None


class TestEnabled:
    @pytest.mark.parametrize("raw", ["false", "0", "no", "off", "FALSE", "Off"])
    def test_falsey_disables(self, monkeypatch, raw):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_ENABLED_ENV, raw)
        assert load_settings().protection_enabled is False

    @pytest.mark.parametrize("raw", ["true", "1", "yes", "on", "anything"])
    def test_truthy_enables(self, monkeypatch, raw):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_ENABLED_ENV, raw)
        assert load_settings().protection_enabled is True


class TestStopLossRange:
    def test_valid(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_STOP_LOSS_PCT_ENV, "0.15")
        assert load_settings().protection_stop_loss_pct == pytest.approx(0.15)

    @pytest.mark.parametrize(
        "bad", ["0", "0.0", "-0.1", "1", "1.0", "2", "nan", "inf", "abc"]
    )
    def test_out_of_range_or_nonfinite_rejected(self, monkeypatch, bad):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_STOP_LOSS_PCT_ENV, bad)
        with pytest.raises(ValueError):
            load_settings()


class TestLimitBufferRange:
    def test_zero_allowed(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_LIMIT_BUFFER_PCT_ENV, "0")
        assert load_settings().protection_limit_buffer_pct == pytest.approx(0.0)

    @pytest.mark.parametrize("bad", ["-0.001", "1", "1.5", "nan", "inf", "xyz"])
    def test_out_of_range_or_nonfinite_rejected(self, monkeypatch, bad):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_LIMIT_BUFFER_PCT_ENV, bad)
        with pytest.raises(ValueError):
            load_settings()


class TestCadence:
    def test_unset_is_none(self, monkeypatch):
        _clear(monkeypatch)
        assert load_settings().protection_cadence_seconds is None

    def test_blank_is_none(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_CADENCE_SECONDS_ENV, "   ")
        assert load_settings().protection_cadence_seconds is None

    def test_positive_value(self, monkeypatch):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_CADENCE_SECONDS_ENV, "3")
        assert load_settings().protection_cadence_seconds == pytest.approx(3.0)

    @pytest.mark.parametrize("bad", ["0", "-1", "nan", "inf", "notanumber"])
    def test_nonpositive_or_nonfinite_rejected(self, monkeypatch, bad):
        _clear(monkeypatch)
        monkeypatch.setenv(PROTECTION_CADENCE_SECONDS_ENV, bad)
        with pytest.raises(ValueError):
            load_settings()
