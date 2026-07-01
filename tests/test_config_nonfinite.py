"""Config rejects non-finite timing values at load (Item 3 / BE-1).

``float()`` accepts ``"nan"``/``"inf"``; left in, a NaN cadence makes the
monitoring loop's ``asyncio.sleep(nan)`` never fire (silent stall) and an
infinite timeout disables stale-order surfacing. ``_env_float`` now fails fast.
"""

from __future__ import annotations

import pytest

from app.config import (
    POLL_CADENCE_ENV,
    UNFILLED_TIMEOUT_ENV,
    load_settings,
)


def _clear(monkeypatch):
    monkeypatch.delenv(POLL_CADENCE_ENV, raising=False)
    monkeypatch.delenv(UNFILLED_TIMEOUT_ENV, raising=False)


@pytest.mark.parametrize("env", [POLL_CADENCE_ENV, UNFILLED_TIMEOUT_ENV])
@pytest.mark.parametrize("bad", ["nan", "NaN", "inf", "Infinity", "-inf"])
def test_nonfinite_timing_rejected_at_load(monkeypatch, env, bad):
    _clear(monkeypatch)
    monkeypatch.setenv(env, bad)
    with pytest.raises(ValueError):
        load_settings()


def test_finite_timing_still_loads(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(POLL_CADENCE_ENV, "5")
    monkeypatch.setenv(UNFILLED_TIMEOUT_ENV, "30")
    settings = load_settings()
    assert settings.poll_cadence_seconds == 5.0
    assert settings.unfilled_timeout_minutes == 30.0


def test_defaults_apply_when_unset(monkeypatch):
    _clear(monkeypatch)
    settings = load_settings()
    # Finite, positive defaults — no exception.
    assert settings.poll_cadence_seconds > 0
    assert settings.unfilled_timeout_minutes >= 0
