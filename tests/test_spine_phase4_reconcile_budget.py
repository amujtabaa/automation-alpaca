"""Spine v2 Phase 4 wave 4e slice 1 — §7 reconciliation config + query budget.

Additive/inert: the §7 config defaults and the deterministic per-minute query
budget (`ReconcileQueryBudget`) the acting reconcile will consume from in slice
4e-4. Nothing wires them into the loop yet. The budget is a pure token bucket
with an INJECTED clock (§12) — no wall-clock, no RNG — so throttling is replayable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import config as cfg
from app.config import load_settings
from app.reconciliation import ReconcileQueryBudget

_T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _at(seconds: float) -> datetime:
    return _T0 + timedelta(seconds=seconds)


# --------------------------------------------------------------------------- #
# ReconcileQueryBudget — deterministic per-minute token bucket
# --------------------------------------------------------------------------- #
def test_budget_starts_full_and_consumes():
    b = ReconcileQueryBudget(200)
    assert b.available == 200.0
    assert b.try_consume(_at(0)) is True
    assert b.available == 199.0


def test_budget_exhausts_then_denies_within_the_window():
    b = ReconcileQueryBudget(3)
    now = _at(0)
    assert [b.try_consume(now) for _ in range(3)] == [True, True, True]
    # Fourth in the same instant is denied — the caller must skip this cycle.
    assert b.try_consume(now) is False
    assert b.available == 0.0


def test_budget_refills_continuously_on_forward_time():
    b = ReconcileQueryBudget(60)  # 1 token/sec
    for _ in range(60):
        assert b.try_consume(_at(0)) is True
    assert b.try_consume(_at(0)) is False       # empty at t=0
    assert b.try_consume(_at(1)) is True         # ~1 token refilled after 1s
    assert b.try_consume(_at(1)) is False        # and only one


def test_budget_refill_caps_at_limit():
    b = ReconcileQueryBudget(10)
    b.try_consume(_at(0))                         # 9 left
    # A long gap refills, but never above the cap.
    assert b.try_consume(_at(3600)) is True
    assert b.available == 9.0                     # capped at 10, then -1


def test_budget_non_increasing_clock_never_over_credits():
    b = ReconcileQueryBudget(5)
    assert b.try_consume(_at(10)) is True         # anchors _last at t=10
    # A backwards timestamp must not refill or rewind the bucket.
    for _ in range(4):
        assert b.try_consume(_at(5)) is True      # spends the remaining 4
    assert b.try_consume(_at(5)) is False         # exhausted; backwards time gave nothing
    assert b.try_consume(_at(0)) is False


def test_budget_multi_token_consume():
    b = ReconcileQueryBudget(10)
    assert b.try_consume(_at(0), 4) is True
    assert b.available == 6.0
    assert b.try_consume(_at(0), 7) is False      # not enough for 7
    assert b.available == 6.0                      # a denied consume takes nothing


def test_budget_rejects_bad_args():
    with pytest.raises(ValueError):
        ReconcileQueryBudget(0)
    with pytest.raises(ValueError):
        ReconcileQueryBudget(-5)
    with pytest.raises(ValueError):
        ReconcileQueryBudget(10).try_consume(_at(0), 0)


def test_budget_grants_bounded_by_tokens_ever_available():
    # The real token-bucket invariant across an arbitrary forward-time schedule:
    # `available` stays within [0, cap], and total grants can never exceed the
    # tokens ever made available (initial full bucket + continuous refill over the
    # elapsed window). This is the conservation property a throttle must satisfy.
    limit = 20
    b = ReconcileQueryBudget(limit)
    granted = denied = 0
    t = 0.0
    for step in range(500):
        t += (step % 7) * 0.5  # non-decreasing, irregular cadence (some zero-gap bursts)
        ok = b.try_consume(_at(t))
        assert 0.0 <= b.available <= limit + 1e-9     # bucket bounds always hold
        granted += int(ok)
        denied += int(not ok)
    max_possible = limit + (limit / 60.0) * t          # initial + total refill
    assert granted <= max_possible + 1e-6
    # The schedule outpaces the 20/min refill, so both branches are exercised.
    assert granted > 0 and denied > 0


# --------------------------------------------------------------------------- #
# Config — §7 defaults + env parsing
# --------------------------------------------------------------------------- #
def test_reconcile_config_defaults():
    s = cfg.Settings()
    assert s.reconciliation_enabled is True
    assert s.reconcile_recent_threshold_ms == cfg.DEFAULT_RECONCILE_RECENT_THRESHOLD_MS == 5000
    assert s.reconcile_avg_price_tolerance == cfg.DEFAULT_RECONCILE_AVG_PRICE_TOLERANCE == 0.0001
    assert s.reconcile_open_check_missing_retries == 3
    assert s.reconcile_query_budget_per_min == 200
    assert s.reconcile_startup_delay_secs == 10.0


def test_reconcile_config_env_overrides(monkeypatch):
    monkeypatch.setenv("RECONCILIATION_ENABLED", "false")
    monkeypatch.setenv("RECONCILE_RECENT_THRESHOLD_MS", "2000")
    monkeypatch.setenv("RECONCILE_AVG_PRICE_TOLERANCE", "0.0005")
    monkeypatch.setenv("RECONCILE_OPEN_CHECK_MISSING_RETRIES", "5")
    monkeypatch.setenv("RECONCILE_QUERY_BUDGET_PER_MIN", "120")
    monkeypatch.setenv("RECONCILE_STARTUP_DELAY_SECS", "3.5")
    s = load_settings()
    assert s.reconciliation_enabled is False
    assert s.reconcile_recent_threshold_ms == 2000
    assert s.reconcile_avg_price_tolerance == 0.0005
    assert s.reconcile_open_check_missing_retries == 5
    assert s.reconcile_query_budget_per_min == 120
    assert s.reconcile_startup_delay_secs == 3.5


def test_reconcile_retries_and_budget_reject_below_minimum(monkeypatch):
    # retries/budget must be >= 1: a zero retry would reject on the FIRST not-found
    # (an oversell path — §7 wants a bounded number of confirmations first); a zero
    # budget would silently disable every reconcile query. A misconfigured 0 fails
    # fast (raises), matching timeout_quarantine_max_query_attempts — never clamps
    # silently to a value the operator didn't ask for.
    monkeypatch.setenv("RECONCILE_OPEN_CHECK_MISSING_RETRIES", "0")
    with pytest.raises(ValueError):
        load_settings()
    monkeypatch.setenv("RECONCILE_OPEN_CHECK_MISSING_RETRIES", "3")
    monkeypatch.setenv("RECONCILE_QUERY_BUDGET_PER_MIN", "0")
    with pytest.raises(ValueError):
        load_settings()
