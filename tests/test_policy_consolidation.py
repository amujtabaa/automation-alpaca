"""Wave 2 Part 1 (D-019) — the pre-trade policy module is the single source.

These tests pin the *consolidation* itself: every layer that used to fork its
own check now reads the identical decision from ``app.policy``, and the one
deliberate non-uniformity (``order_intent_block_reason(None)`` vs
``order_session_resolution_reason(None)``) is preserved, not accidentally flattened
by centralizing. Pure, IO-free (Rule 9).
"""

from __future__ import annotations

import math

import pytest

from app import features
from app.models import CandidateStatus, SessionRecord, TradingState
from app.policy import (
    finite_number_reason,
    market_data_field_reason,
    order_intent_block_reason,
    order_session_resolution_reason,
)
from app.store import core


# A battery of tricky numeric inputs that have historically diverged between
# ad-hoc checks: NaN/Inf slip past bare `<= 0`, bool is an int subclass, a
# string raises from math.isfinite, None is a missing field.
_NUMERIC_CASES = [
    0,
    1,
    1.5,
    -1,
    -2.5,
    0.0,
    1e308,
    float("nan"),
    float("inf"),
    float("-inf"),
    True,
    False,
    "5",
    None,
]


@pytest.mark.parametrize("value", _NUMERIC_CASES)
def test_market_data_field_reason_is_the_numeric_source(value):
    # The market-data-named guard is exactly the shared numeric guard — one
    # decision, two readable names, never two implementations.
    assert market_data_field_reason(value) == finite_number_reason(value)


@pytest.mark.parametrize("value", _NUMERIC_CASES)
def test_features_finite_delegates_to_the_single_source(value):
    # features._finite must agree with the policy source on every input: a
    # feature is usable iff the policy module says the number is real. This is
    # the de-fork — features.py no longer owns its own math.isfinite check.
    assert features._finite(value) == (market_data_field_reason(value) is None)


def test_features_finite_matches_legacy_semantics_on_real_inputs():
    # Behavior-preserving vs the pre-refactor `value is not None and
    # math.isfinite(value)` for the only inputs the Optional[float] contract
    # actually admits (bool is excluded by the type; its handling is the sole
    # intentional divergence and is covered above).
    for value in (0.0, 1.0, 1.5, -3.0, 1e308, float("nan"), float("inf"), None):
        legacy = value is not None and math.isfinite(value)
        assert features._finite(value) is legacy


def test_session_resolution_distinct_from_intent_block_on_none():
    # The load-bearing distinction D-019 must NOT flatten by centralizing:
    #  * order_intent_block_reason(None) stays None — the monitoring loop's
    #    current-session emergency-stop reads a missing session as nothing to
    #    halt (must not block).
    #  * order_session_resolution_reason(None) blocks as unresolved_session — an
    #    APPROVED candidate whose declared session vanished must not order.
    assert order_intent_block_reason(None) is None
    assert order_session_resolution_reason(None) == "unresolved_session"


def test_session_resolution_passes_a_real_session():
    live = SessionRecord(session_date="2026-07-03")
    assert order_session_resolution_reason(live) is None
    # A kill-switched but resolvable session resolves here (resolution != control
    # block — the control block is a separate, later predicate).
    stopped = SessionRecord(
        session_date="2026-07-03", kill_switch=True,
        trading_state=TradingState.HALTED,
    )
    assert order_session_resolution_reason(stopped) is None


def test_planner_unresolved_session_uses_the_shared_reason():
    # The create-order planner's F-004 backstop emits exactly the predicate's
    # reason code — proving the planner reads the single source, not a literal.
    from app.models import Candidate

    cand = Candidate(
        symbol="AAPL",
        status=CandidateStatus.APPROVED,
        suggested_quantity=10,
        suggested_limit_price=1.0,
        session_id="s1",
    )
    plan = core.plan_create_order_for_candidate(candidate=cand, session=None)
    assert plan.outcome == core.CREATE_ORDER_REJECT
    assert plan.reject_event is not None
    assert plan.reject_event.payload["reason"] == order_session_resolution_reason(None)
    assert plan.reject_event.payload["reason"] == "unresolved_session"
