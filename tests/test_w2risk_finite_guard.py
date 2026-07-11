"""W2-RISK (CAMPAIGN-0001 Wave-2, REV-0010 P3, defense-in-depth) — the CAPI risk
gate ``risk_limit_reason`` fails CLOSED on a non-finite exposure/price instead of
silently approving. Every ingress is finite-gated upstream today, but a NaN/±Inf
slipping through a future ungated path would make each ``> cap`` comparison False,
approving under the cap on garbage — the inverse of the safety invariant. This
pins the belt-and-suspenders guard.
"""

from __future__ import annotations

import math

from app.policy import risk_limit_reason

_LIMITS = dict(
    max_shares_per_order=1000.0,
    max_notional_per_order=100_000.0,
    max_total_exposure=100_000.0,
    allowlist=None,
)


def test_finite_inputs_still_approve_under_cap():
    assert (
        risk_limit_reason(
            symbol="AAPL",
            order_quantity=10,
            order_limit_price=5.0,
            exposure_before_order=0.0,
            **_LIMITS,
        )
        is None
    )


def test_nan_exposure_fails_closed():
    reason = risk_limit_reason(
        symbol="AAPL",
        order_quantity=10,
        order_limit_price=5.0,
        exposure_before_order=math.nan,
        **_LIMITS,
    )
    assert reason is not None and reason.startswith("nonfinite_risk_input"), reason


def test_inf_price_fails_closed():
    reason = risk_limit_reason(
        symbol="AAPL",
        order_quantity=10,
        order_limit_price=math.inf,
        exposure_before_order=0.0,
        **_LIMITS,
    )
    assert reason is not None and reason.startswith("nonfinite_risk_input"), reason


def test_nonfinite_guard_runs_even_with_no_configured_limits():
    """The guard is independent of whether CAPI limits are set — a NaN must halt
    even in the interface's unrestricted mode."""
    reason = risk_limit_reason(
        symbol="AAPL",
        order_quantity=10,
        order_limit_price=math.nan,
        exposure_before_order=0.0,
        max_shares_per_order=None,
        max_notional_per_order=None,
        max_total_exposure=None,
        allowlist=None,
    )
    assert reason is not None and reason.startswith("nonfinite_risk_input"), reason
