"""WO-0018 — hypothesis properties over arbitrary envelopes + snapshot tapes.

The four wave-level guarantees:
1. ``decide`` NEVER returns a plan violating a hard rail (floor / qty /
   cooldown / budget) — checked with the same shared validator the engine
   seam will reuse at write time (D-3), so plan-time and write-time cannot
   disagree by construction here.
2. Determinism: same inputs ⇒ same output.
3. The working-stop sequence over a growing tape is monotonically
   non-decreasing.
4. The working trail is never tighter than the envelope's minimum ATR
   multiple at any step.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st

from app.marketdata.service import MarketSnapshot
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    SessionType,
)
from app.sellside.policy import decide, validate_action
from app.sellside.trails import compute_working_stop
from app.sellside.bars import aggregate
from app.sellside.types import PlannedAction

T0 = datetime(2026, 7, 8, 13, 0, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 7, 8, 14, 0, 0, tzinfo=timezone.utc)


@st.composite
def envelopes(draw):
    ceiling = draw(st.integers(min_value=1, max_value=10_000))
    floor = draw(
        st.floats(min_value=0.01, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    t_min = draw(
        st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    t_span = draw(
        st.floats(min_value=0.0, max_value=5.0, allow_nan=False, allow_infinity=False)
    )
    return ExecutionEnvelope(
        sell_intent_id="si-prop",
        symbol="AAPL",
        qty_ceiling=ceiling,
        remaining_quantity=draw(st.integers(min_value=0, max_value=ceiling)),
        floor_price=floor,
        trail_distance_min=t_min,
        trail_distance_max=t_min + t_span,
        participation_rate_cap=draw(
            st.floats(
                min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False
            )
        ),
        aggressiveness=["patient", "urgent"],
        cooldown_floor_ms=draw(st.integers(min_value=1, max_value=5_000)),
        cancel_replace_budget=draw(st.integers(min_value=1, max_value=50)),
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        status=EnvelopeStatus.ACTIVE,
        activated_at=T0,
    )


@st.composite
def tapes(draw):
    """Random walks with occasional bursts; always finite, positive prices,
    non-decreasing cumulative volume with occasional resets."""

    n = draw(st.integers(min_value=0, max_value=240))
    price = draw(
        st.floats(min_value=1.0, max_value=40.0, allow_nan=False, allow_infinity=False)
    )
    steps = draw(
        st.lists(
            st.floats(
                min_value=-0.08, max_value=0.09, allow_nan=False, allow_infinity=False
            ),
            min_size=n,
            max_size=n,
        )
    )
    vols = draw(
        st.lists(
            st.floats(
                min_value=0.0, max_value=5_000.0, allow_nan=False, allow_infinity=False
            ),
            min_size=n,
            max_size=n,
        )
    )
    tape = []
    cum = 1_000.0
    for i, (dp, dv) in enumerate(zip(steps, vols)):
        price = max(0.5, price * (1.0 + dp))
        cum += dv
        tape.append(
            MarketSnapshot(
                symbol="AAPL",
                last_price=round(price, 4),
                bid=round(price * 0.999, 4),
                ask=round(price * 1.001, 4),
                volume=cum,
                prev_close=10.0,
                updated_at=T0 + timedelta(seconds=10 * i),
            )
        )
    return tape


@given(env=envelopes(), tape=tapes())
@settings(max_examples=60, deadline=None)
def test_no_plan_ever_violates_a_hard_rail(env, tape):
    out = decide(env, tape, now=NOW, history=[])
    if isinstance(out, PlannedAction):
        assert validate_action(env, out, history=[], now=NOW) is None
        assert out.limit_price >= env.floor_price
        assert 0 < out.quantity <= (env.remaining_quantity or 0)


@given(env=envelopes(), tape=tapes())
@settings(max_examples=30, deadline=None)
def test_determinism(env, tape):
    assert decide(env, tape, now=NOW, history=[]) == decide(
        env, tape, now=NOW, history=[]
    )


@given(env=envelopes(), tape=tapes())
@settings(max_examples=30, deadline=None)
def test_working_stop_is_monotone_over_a_growing_tape(env, tape):
    stops = []
    for cut in range(0, len(tape) + 1, 12):
        result = compute_working_stop(
            env, aggregate(tape[:cut], timedelta(seconds=30)), urgency=0.0
        )
        if result.stop is not None:
            stops.append(result.stop)
    assert all(b >= a - 1e-9 for a, b in zip(stops, stops[1:]))


@given(env=envelopes(), tape=tapes())
@settings(max_examples=30, deadline=None)
def test_trail_floor_holds_at_every_step(env, tape):
    """Each step's CANDIDATE keeps min_atr_mult × ATR(step) of room from that
    step's trail reference — max urgency is the worst case. (The ratcheted
    stop may legitimately sit closer after a crash: that is the stop firing.)"""

    bars = aggregate(tape, timedelta(seconds=30))
    for cut in range(2, len(bars) + 1, 6):
        result = compute_working_stop(env, bars[:cut], urgency=1.0)
        if result.candidate is not None and result.atr is not None and result.atr > 0:
            assert (
                result.ref_high - result.candidate
                >= env.trail_distance_min * result.atr - 1e-6
            )
