"""Independent tests for the SOL-0001 rival sell-side policy.

All tapes are deterministic and synthetic.  Numeric values are test fixtures,
not trading recommendations or calibrated parameters.
"""

from __future__ import annotations

import re
import sys
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from app.marketdata.service import MarketSnapshot
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    SessionType,
)
from app.sellside.policy import validate_action
from app.sellside.types import (
    ActionKind,
    BreachSignal,
    ExhaustedSignal,
    NoAction,
    NoActionReason,
    PlannedAction,
    RailViolation,
    StaleDataSignal,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sol_policy as sol  # noqa: E402
from sol_policy import compute_working_stop, decide  # noqa: E402


T0 = datetime(2026, 7, 8, 13, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 7, 8, 14, 0, tzinfo=timezone.utc)


def envelope(**overrides) -> ExecutionEnvelope:
    values = {
        "sell_intent_id": "si-sol",
        "symbol": "AAPL",
        "qty_ceiling": 100,
        "floor_price": 7.0,
        "trail_distance_min": 1.0,
        "trail_distance_max": 3.0,
        "participation_rate_cap": 0.20,
        "aggressiveness": ["patient", "urgent"],
        "cooldown_floor_ms": 750,
        "cancel_replace_budget": 3,
        "expires_at": NOW + timedelta(hours=2),
        "allowed_session_phases": [SessionType.REGULAR],
        "expiry_disposition": EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        "stale_data_disposition": EnvelopeStaleDataDisposition.CANCEL,
        "status": EnvelopeStatus.ACTIVE,
        "activated_at": T0,
    }
    values.update(overrides)
    return ExecutionEnvelope(**values)


def snapshot(
    seconds: float,
    price: float,
    volume: float,
    *,
    spread: float = 0.02,
    symbol: str = "AAPL",
) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        last_price=price,
        bid=round(price - spread / 2, 4),
        ask=round(price + spread / 2, 4),
        volume=volume,
        prev_close=9.5,
        updated_at=T0 + timedelta(seconds=seconds),
    )


def flat_tape(minutes: int = 40) -> list[MarketSnapshot]:
    return [
        snapshot(10 * i, 10.0 + (0.01 if i % 2 == 0 else -0.01), 1000 + 80 * i)
        for i in range(minutes * 6)
    ]


def crash_tape() -> list[MarketSnapshot]:
    tape: list[MarketSnapshot] = []
    price = 10.0
    volume = 1000.0
    for i in range(180):
        price += 0.005
        volume += 100
        tape.append(snapshot(10 * i, round(price, 4), volume))
    for i in range(60):
        price -= 0.02
        volume += 300
        tape.append(snapshot(1800 + 10 * i, round(price, 4), volume))
    return tape


def spike_tape(*, spread: float = 0.02) -> list[MarketSnapshot]:
    tape = flat_tape()
    price = tape[-1].last_price or 10.0
    volume = tape[-1].volume or 1000.0
    for i in range(24):
        price += 0.15
        volume += 3000
        tape.append(snapshot(2400 + 10 * i, round(price, 4), volume, spread=spread))
    return tape


def action_event(
    env: ExecutionEnvelope,
    action: str,
    at: datetime,
    *,
    working_stop: float | None = None,
    tranche: bool = False,
    order_id: str | None = None,
) -> ExecutionEvent:
    payload: dict[str, object] = {"action": action, "tranche": tranche}
    if working_stop is not None:
        payload["working_stop"] = working_stop
    return ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=at,
        envelope_id=env.id,
        symbol=env.symbol,
        order_id=order_id,
        payload=payload,
    )


def test_deterministic_and_does_not_mutate_inputs():
    env = envelope()
    tape = crash_tape()
    history = [action_event(env, "submit", NOW - timedelta(minutes=2))]
    before = deepcopy((env, tape, history))
    assert decide(env, tape, now=NOW, history=history) == decide(
        env, tape, now=NOW, history=history
    )
    assert (env, tape, history) == before


def test_a_b_a_calls_have_no_hidden_cross_envelope_state():
    env_a, env_b = envelope(), envelope(symbol="MSFT")
    tape_a = crash_tape()
    tape_b = [replace(row, symbol="MSFT") for row in spike_tape()]
    first = decide(env_a, tape_a, now=NOW, history=[])
    decide(env_b, tape_b, now=NOW, history=[])
    assert decide(env_a, tape_a, now=NOW, history=[]) == first


@pytest.mark.parametrize(
    "mutation",
    [
        {"stale": True},
        {"last_price": None},
        {"last_price": float("nan")},
        {"bid": None},
        {"ask": float("inf")},
        {"bid": 10.1, "ask": 10.0},
        {"bid": 10.0, "ask": 10.0},
        {"volume": -1.0},
        {"symbol": "MSFT"},
    ],
)
def test_latest_invalid_or_wrong_symbol_fails_closed(mutation):
    tape = flat_tape()
    tape.append(replace(tape[-1], **mutation))
    out = decide(envelope(), tape, now=NOW, history=[])
    assert isinstance(out, StaleDataSignal)
    assert out.reasons


def test_out_of_order_tape_fails_closed():
    tape = flat_tape()
    tape[-1], tape[-2] = tape[-2], tape[-1]
    out = decide(envelope(), tape, now=NOW, history=[])
    assert isinstance(out, StaleDataSignal)
    assert "non_monotonic_tape" in out.reasons


def test_crash_exit_is_legal_and_validated():
    env = envelope()
    out = decide(env, crash_tape(), now=NOW, history=[])
    assert isinstance(out, PlannedAction)
    assert out.stop_triggered
    assert validate_action(env, out, history=[], now=NOW) is None


def test_protective_exit_respects_zero_participation_capacity():
    env = envelope(participation_rate_cap=1e-8)
    out = decide(env, crash_tape(), now=NOW, history=[])
    assert isinstance(out, NoAction)
    assert out.reason is NoActionReason.NO_LIQUIDITY


def test_protective_exit_reports_participation_clamp():
    env = envelope(participation_rate_cap=0.001)
    out = decide(env, crash_tape(), now=NOW, history=[])
    assert isinstance(out, PlannedAction)
    assert out.stop_triggered
    assert out.quantity < env.remaining_quantity
    assert any(note.field == "participation_quantity" for note in out.clamps)


def test_cancel_request_without_confirmation_blocks_new_action():
    env = envelope()
    history = [
        action_event(env, "submit", NOW - timedelta(minutes=2)),
        action_event(env, "cancel", NOW - timedelta(minutes=1)),
    ]
    out = decide(env, crash_tape(), now=NOW, history=history)
    assert isinstance(out, NoAction)
    assert "cancel" in out.detail


def test_confirmed_cancel_releases_child_and_next_action_is_submit():
    env = envelope()
    history = [
        action_event(
            env,
            "submit",
            NOW - timedelta(minutes=2),
            order_id="order-1",
        ),
        action_event(
            env,
            "cancel",
            NOW - timedelta(minutes=1),
            order_id="order-1",
        ),
        ExecutionEvent(
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            ts_event=NOW - timedelta(seconds=30),
            envelope_id=env.id,
            order_id="order-1",
        ),
    ]
    out = decide(env, crash_tape(), now=NOW, history=history)
    assert isinstance(out, PlannedAction)
    assert out.kind is ActionKind.SUBMIT


def test_history_stop_survives_resume_timestamp_reset():
    env = envelope(activated_at=NOW - timedelta(minutes=2))
    prior_stop = 10.75
    history = [
        action_event(
            env,
            "submit",
            NOW - timedelta(minutes=10),
            working_stop=prior_stop,
        )
    ]
    out = decide(env, flat_tape(), now=NOW, history=history)
    assert isinstance(out, (NoAction, PlannedAction))
    assert out.working_stop is not None
    assert out.working_stop >= prior_stop


def test_valid_but_off_market_historical_print_does_not_ratchet_stop():
    clean = flat_tape()
    dirty = list(clean)
    odd = dirty[100]
    dirty[100] = replace(odd, last_price=25.0)  # quote remains around $10
    a = compute_working_stop(envelope(), clean, now=NOW, history=[])
    b = compute_working_stop(envelope(), dirty, now=NOW, history=[])
    assert a.stop is not None and b.stop is not None
    assert b.stop == pytest.approx(a.stop, abs=0.10)


def test_partial_current_bar_cannot_rewrite_an_established_stop():
    tape = flat_tape()
    before = compute_working_stop(envelope(), tape, now=NOW, history=[])
    extra = snapshot(2391, 9.50, (tape[-1].volume or 0) + 10)
    after = compute_working_stop(envelope(), tape + [extra], now=NOW, history=[])
    assert before.stop is not None
    assert after.stop == before.stop


def test_decision_time_change_does_not_reprice_historical_urgency():
    tape = flat_tape()
    first = compute_working_stop(
        envelope(), tape, now=NOW - timedelta(minutes=1), history=[]
    )
    second = compute_working_stop(envelope(), tape, now=NOW, history=[])
    assert first.stop == second.stop


def test_wide_spread_spike_suppresses_opportunistic_tranche():
    out = decide(envelope(), spike_tape(spread=1.0), now=NOW, history=[])
    assert not (isinstance(out, PlannedAction) and out.tranche)


def test_tight_liquid_spike_can_take_one_capped_tranche():
    env = envelope(participation_rate_cap=0.0001)
    out = decide(env, spike_tape(), now=NOW, history=[])
    assert isinstance(out, PlannedAction)
    assert out.tranche
    assert 1 <= out.quantity <= 50
    assert any(note.field == "participation_quantity" for note in out.clamps)


def test_unfilled_tranche_can_retry_after_confirmed_cancel():
    env = envelope()
    history = [
        action_event(
            env,
            "submit",
            NOW - timedelta(minutes=2),
            tranche=True,
            order_id="tranche-1",
        ),
        action_event(
            env,
            "cancel",
            NOW - timedelta(minutes=1),
            order_id="tranche-1",
        ),
        ExecutionEvent(
            event_type=ExecutionEventType.CANCELED,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            ts_event=NOW - timedelta(seconds=30),
            envelope_id=env.id,
            order_id="tranche-1",
        ),
    ]
    out = decide(env, spike_tape(), now=NOW, history=history)
    assert isinstance(out, PlannedAction)
    assert out.tranche
    assert out.kind is ActionKind.SUBMIT


def test_deduped_tranche_fill_consumes_entitlement():
    env = envelope()
    history = [
        action_event(
            env,
            "submit",
            NOW - timedelta(minutes=3),
            tranche=True,
            order_id="tranche-1",
        ),
        ExecutionEvent(
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_STREAM,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key="trade-1",
            ts_event=NOW - timedelta(minutes=2),
            envelope_id=env.id,
            order_id="tranche-1",
            quantity=10,
            price=12.0,
        ),
        ExecutionEvent(
            event_type=ExecutionEventType.FILLED,
            source=EventSource.BROKER_STREAM,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            ts_event=NOW - timedelta(minutes=1),
            envelope_id=env.id,
            order_id="tranche-1",
        ),
    ]
    out = decide(env, spike_tape(), now=NOW, history=history)
    assert not (isinstance(out, PlannedAction) and out.tranche)


def test_cooldown_and_budget_derive_only_from_own_history():
    env = envelope(cancel_replace_budget=2)
    recent = [action_event(env, "submit", NOW - timedelta(milliseconds=100))]
    out = decide(env, crash_tape(), now=NOW, history=recent)
    assert isinstance(out, NoAction)
    assert out.reason is NoActionReason.COOLDOWN_WAIT

    spent = [
        action_event(env, "submit", NOW - timedelta(minutes=3)),
        action_event(env, "reprice", NOW - timedelta(minutes=2)),
        action_event(env, "reprice", NOW - timedelta(minutes=1)),
    ]
    assert isinstance(
        decide(env, crash_tape(), now=NOW, history=spent), ExhaustedSignal
    )


def test_cooldown_exact_boundary_is_allowed_and_other_envelope_is_ignored():
    env = envelope()
    other = envelope()
    history = [
        action_event(env, "submit", NOW - timedelta(milliseconds=750)),
        action_event(other, "submit", NOW - timedelta(milliseconds=1)),
    ]
    out = decide(env, crash_tape(), now=NOW, history=history)
    assert isinstance(out, PlannedAction)


def test_shared_validator_is_mandatory_not_decorative(monkeypatch):
    monkeypatch.setattr(
        sol,
        "validate_action",
        lambda *args, **kwargs: RailViolation("sentinel", "mutation-control"),
    )
    out = sol.decide(envelope(), crash_tape(), now=NOW, history=[])
    assert isinstance(out, BreachSignal)
    assert out.rail == "sentinel"


@given(
    remaining=st.integers(min_value=1, max_value=500),
    floor=st.floats(
        min_value=0.5, max_value=8.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=30, deadline=None)
def test_any_plan_passes_the_shared_validator(remaining, floor):
    env = envelope(qty_ceiling=500, remaining_quantity=remaining, floor_price=floor)
    out = decide(env, crash_tape(), now=NOW, history=[])
    if isinstance(out, PlannedAction):
        assert validate_action(env, out, history=[], now=NOW) is None


def test_working_stop_is_monotone_and_respects_step_trail_floor():
    env = envelope(trail_distance_min=1.5, trail_distance_max=4.0)
    tape = crash_tape()
    stops: list[float] = []
    for cut in range(100, len(tape) + 1, 10):
        result = compute_working_stop(env, tape[:cut], now=NOW, history=[])
        if result.stop is not None:
            stops.append(result.stop)
        if result.candidate is not None and result.atr is not None:
            assert result.reference - result.candidate >= 1.5 * result.atr - 1e-6
    assert len(stops) > 5
    assert all(b >= a - 1e-9 for a, b in zip(stops, stops[1:]))


def test_black_box_decide_reports_a_monotone_stop_over_prefixes():
    env = envelope(allowed_session_phases=[SessionType.PRE_MARKET, SessionType.REGULAR])
    tape = crash_tape()
    stops: list[float] = []
    for cut in range(100, len(tape) + 1, 10):
        out = decide(env, tape[:cut], now=NOW, history=[])
        if isinstance(out, (NoAction, PlannedAction)) and out.working_stop is not None:
            stops.append(out.working_stop)
    assert len(stops) > 5
    assert all(b >= a - 1e-9 for a, b in zip(stops, stops[1:]))


def test_below_floor_action_is_breach_not_clamp():
    env = envelope(floor_price=9.75)
    out = decide(env, crash_tape(), now=NOW, history=[])
    assert isinstance(out, BreachSignal)
    assert out.rail == "floor_price"


def test_source_has_no_bare_clock_or_forbidden_imports():
    source = (Path(__file__).resolve().parent / "sol_policy.py").read_text()
    assert not re.search(r"datetime\.now\(|time\.time\(|utcnow\(", source)
    imports = [
        line
        for line in source.splitlines()
        if line.startswith("from app.") or line.startswith("import app.")
    ]
    assert imports
    assert all(
        line.startswith(
            (
                "from app.models import",
                "from app.marketdata.service import",
                "from app.sellside.types import",
                "from app.sellside.policy import validate_action",
            )
        )
        for line in imports
    )
