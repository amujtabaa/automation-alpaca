"""WO-0016 — ExecutionEnvelope entity validation (ADR-010 §2).

Every *hard rail* must reject bad construction outright: an envelope that
could be built with a nonsensical bound would let the executor treat garbage
as an approved mandate. Soft bounds still validate their own shape (a range
must be a range) — "soft" means the policy clamps into them at runtime, not
that they may be malformed.

Pure model tests — no store, no IO (Rule 9).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    OrderSide,
    SessionType,
    utcnow,
)


def make_envelope(**overrides) -> ExecutionEnvelope:
    """A valid envelope draft; tests override one field at a time."""

    base = dict(
        sell_intent_id="si-1",
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.50,
        trail_distance_min=0.05,
        trail_distance_max=0.25,
        participation_rate_cap=0.20,
        aggressiveness=["passive", "mid"],
        cooldown_floor_ms=750,
        cancel_replace_budget=40,
        expires_at=utcnow() + timedelta(hours=2),
        allowed_session_phases=[SessionType.PRE_MARKET, SessionType.AFTER_HOURS],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def test_valid_draft_constructs_with_expected_defaults():
    env = make_envelope()
    assert env.status is EnvelopeStatus.PENDING
    assert env.side is OrderSide.SELL
    assert env.reduce_only is True
    # remaining starts at the ceiling and only fill application may move it.
    assert env.remaining_quantity == env.qty_ceiling == 100
    assert "replaces_used" not in ExecutionEnvelope.model_fields
    assert env.max_outstanding_children == 1
    assert env.supersedes_id is None and env.superseded_by_id is None


def test_remaining_quantity_may_not_exceed_ceiling_or_go_negative():
    with pytest.raises(ValidationError):
        make_envelope(remaining_quantity=101)
    with pytest.raises(ValidationError):
        make_envelope(remaining_quantity=-1)
    assert make_envelope(remaining_quantity=0).remaining_quantity == 0


# --- Scope hard rails ------------------------------------------------------ #


def test_side_is_locked_to_sell():
    with pytest.raises(ValidationError):
        make_envelope(side=OrderSide.BUY)


def test_reduce_only_is_locked_true():
    with pytest.raises(ValidationError):
        make_envelope(reduce_only=False)


def test_sell_intent_id_and_symbol_must_be_nonempty():
    with pytest.raises(ValidationError):
        make_envelope(sell_intent_id="")
    with pytest.raises(ValidationError):
        make_envelope(symbol="")
    with pytest.raises(ValidationError):
        make_envelope(symbol="   ")


@pytest.mark.parametrize("qty", [0, -5])
def test_qty_ceiling_must_be_positive(qty):
    with pytest.raises(ValidationError):
        make_envelope(qty_ceiling=qty)


# --- Price hard rails ------------------------------------------------------ #


@pytest.mark.parametrize("floor", [0.0, -1.0, float("nan"), float("inf")])
def test_floor_price_must_be_positive_and_finite(floor):
    with pytest.raises(ValidationError):
        make_envelope(floor_price=floor)


@pytest.mark.parametrize(
    "lo,hi",
    [
        (0.0, 0.25),  # empty-from-below
        (-0.1, 0.25),  # negative
        (0.30, 0.25),  # inverted range
        (float("nan"), 0.25),
        (0.05, float("inf")),
    ],
)
def test_trail_distance_range_must_be_a_positive_finite_range(lo, hi):
    with pytest.raises(ValidationError):
        make_envelope(trail_distance_min=lo, trail_distance_max=hi)


def test_trail_distance_degenerate_single_point_is_legal():
    env = make_envelope(trail_distance_min=0.10, trail_distance_max=0.10)
    assert env.trail_distance_min == env.trail_distance_max == 0.10


@pytest.mark.parametrize("cap", [0.0, -0.2, 1.01, float("nan")])
def test_participation_rate_cap_must_be_in_zero_one(cap):
    with pytest.raises(ValidationError):
        make_envelope(participation_rate_cap=cap)


def test_aggressiveness_set_must_be_nonempty_strings():
    with pytest.raises(ValidationError):
        make_envelope(aggressiveness=[])
    with pytest.raises(ValidationError):
        make_envelope(aggressiveness=["passive", ""])


# --- Rate hard rails ------------------------------------------------------- #


@pytest.mark.parametrize("ms", [0, -100])
def test_cooldown_floor_must_be_positive(ms):
    with pytest.raises(ValidationError):
        make_envelope(cooldown_floor_ms=ms)


@pytest.mark.parametrize("budget", [0, -1])
def test_cancel_replace_budget_must_be_positive(budget):
    with pytest.raises(ValidationError):
        make_envelope(cancel_replace_budget=budget)


@pytest.mark.parametrize("value", [0, 1, -1, 6])
def test_replaces_used_is_not_accepted_as_domain_state(value):
    with pytest.raises(ValidationError, match="replaces_used"):
        make_envelope(replaces_used=value)


@pytest.mark.parametrize("n", [0, -1])
def test_max_outstanding_children_must_be_at_least_one(n):
    with pytest.raises(ValidationError):
        make_envelope(max_outstanding_children=n)


# --- Time / disposition hard rails ---------------------------------------- #


def test_expires_at_is_required():
    with pytest.raises(ValidationError):
        make_envelope(expires_at=None)


def test_expires_at_must_be_timezone_aware():
    # Codex PR#8 F6: a NAIVE expires_at used to pass create/approve, then the
    # first tick compares the aware injected `now` against it and raises
    # TypeError -> the mandate freezes as policy_error on tick 1 despite being
    # "accepted". Reject the naive TTL at construction (fail-closed -> 422).
    with pytest.raises(ValidationError):
        make_envelope(expires_at=datetime(2026, 7, 15, 20, 0, 0))  # no tzinfo
    # An aware TTL still constructs fine.
    ok = make_envelope(expires_at=datetime(2026, 7, 15, 20, 0, 0, tzinfo=timezone.utc))
    assert ok.expires_at.tzinfo is not None


def test_allowed_session_phases_must_be_nonempty():
    with pytest.raises(ValidationError):
        make_envelope(allowed_session_phases=[])


def test_dispositions_are_mandatory_approval_time_choices():
    with pytest.raises(ValidationError):
        make_envelope(expiry_disposition=None)
    with pytest.raises(ValidationError):
        make_envelope(stale_data_disposition=None)


def test_self_supersession_linkage_is_rejected():
    env = make_envelope()
    with pytest.raises(ValidationError):
        make_envelope(id=env.id, supersedes_id=env.id)


def test_unknown_fields_are_rejected():
    # extra="forbid" — a typo'd bound must never silently vanish.
    with pytest.raises(ValidationError):
        make_envelope(floor_pricee=1.0)
