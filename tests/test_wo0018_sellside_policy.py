"""WO-0018 — the pure top-level decision function (regime-adaptive LASE core).

``decide(envelope, tape, now=..., history=...)`` consumes the session-anchored
snapshot tape (bars/VWAP/ATR are derived inside — no external feed), the
injected clock value, and this envelope's prior ExecutionEvents. Purity/rails
core: gates (phase/expiry/stale/cooldown/budget) fail closed; hard rails
breach, never clamp; accounting derives from history, never internal state.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import app.sellside.policy as sellside_policy
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
from app.sellside.policy import decide, validate_action
from app.sellside.types import (
    ActionKind,
    BreachSignal,
    ExhaustedSignal,
    ExpiredSignal,
    NoAction,
    NoActionReason,
    PlannedAction,
    StaleDataSignal,
)

# The tape runs 13:00→14:00 UTC == 09:00→10:00 ET; decisions at NOW (10:00 ET,
# regular hours).
T0 = datetime(2026, 7, 8, 13, 0, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 7, 8, 14, 0, 0, tzinfo=timezone.utc)


def make_envelope(**overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id="si-1",
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=8.00,
        trail_distance_min=1.0,  # ATR multiples (WO-0018 final)
        trail_distance_max=3.0,
        participation_rate_cap=0.20,
        aggressiveness=["patient", "urgent"],
        cooldown_floor_ms=750,
        cancel_replace_budget=3,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        status=EnvelopeStatus.ACTIVE,
        activated_at=T0,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def snap(seconds: float, price: float, volume: float, **overrides) -> MarketSnapshot:
    base = dict(
        symbol="AAPL",
        last_price=price,
        bid=round(price - 0.01, 4),
        ask=round(price + 0.01, 4),
        volume=volume,
        prev_close=9.50,
        updated_at=T0 + timedelta(seconds=seconds),
    )
    base.update(overrides)
    return MarketSnapshot(**base)


def flat_tape(n_minutes: int = 40, price: float = 10.0, vol_rate: float = 500.0):
    """A liquid, boring tape: one snapshot per 10s, gentle wiggle."""

    tape = []
    for i in range(n_minutes * 6):
        wiggle = 0.01 if i % 2 == 0 else -0.01
        tape.append(snap(10 * i, price + wiggle, 1000 + vol_rate * i / 6))
    return tape


def crash_tape():
    """Run-up then a hard breakdown through the trail — the stop must fire."""

    tape = []
    price, cum = 10.0, 1000.0
    for i in range(180):  # 30 min up-grind
        price += 0.005
        cum += 100
        tape.append(snap(10 * i, round(price, 4), cum))
    for i in range(60):  # 10 min collapse
        price -= 0.02
        cum += 300
        tape.append(snap(1800 + 10 * i, round(price, 4), cum))
    return tape


def action_event(
    envelope,
    *,
    action: str,
    limit_price: float,
    at: datetime,
    quantity: int = 50,
    tranche: bool = False,
    order_id: str = "order-working-1",
) -> ExecutionEvent:
    # order_id: every REAL envelope_action carries one (the staged order);
    # WO-0025's live working-order predicate keys on it, and with no later
    # terminal event for the id the order reads as LIVE — the same "resting
    # working order" these fixtures always meant to describe.
    return ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=at,
        symbol=envelope.symbol,
        envelope_id=envelope.id,
        order_id=order_id,
        payload={
            "action": action,
            "limit_price": limit_price,
            "quantity": quantity,
            "tranche": tranche,
        },
    )


# --- purity ------------------------------------------------------------------- #


def test_decide_is_deterministic_for_fixed_inputs():
    env, tape = make_envelope(), crash_tape()
    assert decide(env, tape, now=NOW, history=[]) == decide(
        env, tape, now=NOW, history=[]
    )


def test_decide_does_not_mutate_its_inputs():
    env, tape = make_envelope(), flat_tape()
    before = env.model_copy(deep=True)
    decide(env, tape, now=NOW, history=[])
    assert env == before


# --- gates ---------------------------------------------------------------------- #


def test_non_active_envelope_is_no_action():
    env = make_envelope(status=EnvelopeStatus.PENDING, activated_at=None)
    out = decide(env, flat_tape(), now=NOW, history=[])
    assert isinstance(out, NoAction) and out.reason is NoActionReason.NOT_ACTIVE


def test_expired_envelope_emits_the_chosen_disposition():
    env = make_envelope(expires_at=NOW - timedelta(seconds=1))
    out = decide(env, flat_tape(), now=NOW, history=[])
    assert isinstance(out, ExpiredSignal)
    assert out.disposition is EnvelopeExpiryDisposition.CANCEL_AND_RETURN


def test_disallowed_phase_is_no_action():
    env = make_envelope(allowed_session_phases=[SessionType.AFTER_HOURS])
    out = decide(env, flat_tape(), now=NOW, history=[])
    assert isinstance(out, NoAction) and out.reason is NoActionReason.OUT_OF_PHASE


def test_overnight_is_no_action():
    night = datetime(2026, 7, 8, 6, 0, tzinfo=timezone.utc)  # 02:00 ET
    env = make_envelope(expires_at=night + timedelta(hours=12))
    out = decide(env, flat_tape(), now=night, history=[])
    assert isinstance(out, NoAction) and out.reason is NoActionReason.OUT_OF_PHASE


@pytest.mark.parametrize(
    "mutation",
    [
        dict(stale=True),
        dict(last_price=None),
        dict(last_price=float("nan")),
        dict(last_price=float("inf")),
        dict(last_price=-1.0),
        dict(last_price=0.0),
        dict(bid=None),
        dict(ask=None),
        dict(bid=float("nan")),
        dict(ask=float("-inf")),
        dict(bid=10.05, ask=10.01),  # crossed
        dict(volume=None),
        dict(volume=float("nan")),
        dict(volume=-100.0),
    ],
)
def test_invalid_latest_snapshot_fails_closed_per_class(mutation):
    tape = flat_tape()
    tape.append(replace(tape[-1], **mutation))
    out = decide(make_envelope(), tape, now=NOW, history=[])
    assert isinstance(out, StaleDataSignal)
    assert out.disposition is EnvelopeStaleDataDisposition.CANCEL
    assert out.reasons


def test_empty_tape_fails_closed():
    out = decide(make_envelope(), [], now=NOW, history=[])
    assert isinstance(out, StaleDataSignal)


def test_stale_disposition_leave_resting_is_reported():
    env = make_envelope(
        stale_data_disposition=EnvelopeStaleDataDisposition.LEAVE_RESTING
    )
    tape = flat_tape()
    tape.append(replace(tape[-1], stale=True))
    out = decide(env, tape, now=NOW, history=[])
    assert isinstance(out, StaleDataSignal)
    assert out.disposition is EnvelopeStaleDataDisposition.LEAVE_RESTING


def test_zero_remaining_is_nothing_to_do():
    env = make_envelope(remaining_quantity=0)
    out = decide(env, flat_tape(), now=NOW, history=[])
    assert isinstance(out, NoAction) and out.reason is NoActionReason.NOTHING_TO_DO


def test_short_tape_is_insufficient_data():
    out = decide(make_envelope(), flat_tape(n_minutes=1), now=NOW, history=[])
    assert isinstance(out, NoAction)
    assert out.reason is NoActionReason.INSUFFICIENT_DATA


# --- monitoring / stop exit -------------------------------------------------------- #


def test_quiet_tape_monitors_with_a_working_stop():
    out = decide(make_envelope(), flat_tape(), now=NOW, history=[])
    assert isinstance(out, NoAction)
    assert out.reason is NoActionReason.MONITORING
    assert out.working_stop is not None
    assert out.regime is not None


def test_breakdown_through_the_stop_plans_a_marketable_exit():
    env, tape = make_envelope(), crash_tape()
    out = decide(env, tape, now=NOW, history=[])
    assert isinstance(out, PlannedAction)
    assert out.kind is ActionKind.SUBMIT
    assert out.stop_triggered is True
    # Marketable: priced at the bid, floor-guarded.
    assert out.limit_price == pytest.approx(tape[-1].bid)
    assert out.limit_price >= env.floor_price
    assert 1 <= out.quantity <= 100


def test_stop_exit_below_floor_is_a_breach_never_a_clamp():
    env = make_envelope(floor_price=9.75)  # crash tape bottoms near 9.70
    out = decide(env, crash_tape(), now=NOW, history=[])
    assert isinstance(out, BreachSignal)
    assert out.rail == "floor_price"


def test_existing_working_order_makes_the_exit_a_reprice():
    env, tape = make_envelope(), crash_tape()
    history = [
        action_event(
            env, action="submit", limit_price=9.90, at=NOW - timedelta(seconds=30)
        )
    ]
    out = decide(env, tape, now=NOW, history=history)
    assert isinstance(out, PlannedAction)
    assert out.kind is ActionKind.REPRICE


# --- cooldown / budget from history ------------------------------------------------- #


def test_cooldown_floor_defers_the_reprice():
    env, tape = make_envelope(), crash_tape()
    placed = NOW - timedelta(milliseconds=400)
    history = [action_event(env, action="submit", limit_price=9.90, at=placed)]
    out = decide(env, tape, now=NOW, history=history)
    assert isinstance(out, NoAction)
    assert out.reason is NoActionReason.COOLDOWN_WAIT
    assert out.wait_until == placed + timedelta(milliseconds=750)


def test_budget_exhaustion_signals_exhausted():
    env, tape = make_envelope(cancel_replace_budget=2), crash_tape()
    t = NOW - timedelta(seconds=60)
    history = [
        action_event(env, action="submit", limit_price=9.7, at=t),
        action_event(
            env, action="reprice", limit_price=9.6, at=t + timedelta(seconds=10)
        ),
        action_event(
            env, action="reprice", limit_price=9.5, at=t + timedelta(seconds=20)
        ),
    ]
    out = decide(env, tape, now=NOW, history=history)
    assert isinstance(out, ExhaustedSignal)


def test_both_budget_enforcement_sites_consume_the_shared_projection(monkeypatch):
    env, tape = make_envelope(cancel_replace_budget=1), crash_tape()
    history = [
        action_event(
            env,
            action="submit",
            limit_price=9.7,
            at=NOW - timedelta(seconds=60),
        )
    ]
    calls = []

    def exhausted_projection(events):
        calls.append(tuple(events))
        return {env.id: 1}

    monkeypatch.setattr(
        sellside_policy, "project_envelope_replaces_used", exhausted_projection
    )

    assert isinstance(decide(env, tape, now=NOW, history=history), ExhaustedSignal)
    violation = validate_action(
        env, planned(kind=ActionKind.REPRICE), history=history, now=NOW
    )
    assert violation is not None and violation.rail == "cancel_replace_budget"
    assert calls == [tuple(history), tuple(history)]


def test_other_envelopes_history_is_ignored():
    env, tape = make_envelope(), crash_tape()
    other = make_envelope()
    history = [
        action_event(
            other,
            action="submit",
            limit_price=9.9,
            at=NOW - timedelta(milliseconds=100),
        )
    ]
    out = decide(env, tape, now=NOW, history=history)
    assert isinstance(out, PlannedAction)
    assert out.kind is ActionKind.SUBMIT  # not a reprice, no cooldown borrowed


# --- tranche exits -------------------------------------------------------------------- #


def spike_tape_snapshots():
    """Calm then a violent extension far above VWAP on huge volume — tranche
    territory (FAST_SPIKE / extension >= tranche threshold)."""

    tape = []
    price, cum = 10.0, 1000.0
    for i in range(240):  # 40 min calm
        wiggle = 0.01 if i % 2 == 0 else -0.01
        tape.append(snap(10 * i, round(price + wiggle, 4), cum))
        cum += 50
    for i in range(24):  # 4 min vertical
        price += 0.15
        cum += 3000
        tape.append(snap(2400 + 10 * i, round(price, 4), cum))
    return tape


def test_extension_into_strength_takes_a_participation_capped_tranche():
    env = make_envelope()
    out = decide(env, spike_tape_snapshots(), now=NOW, history=[])
    assert isinstance(out, PlannedAction)
    assert out.tranche is True
    assert out.stop_triggered is False
    # Tranche = half the remaining, capped by participation and remaining.
    assert 1 <= out.quantity <= 50
    assert out.limit_price >= env.floor_price


def test_tranche_is_taken_once_then_the_remainder_trails():
    env = make_envelope()
    history = [
        action_event(
            env,
            action="submit",
            limit_price=12.0,
            at=NOW - timedelta(minutes=2),
            tranche=True,
        )
    ]
    out = decide(env, spike_tape_snapshots(), now=NOW, history=history)
    # No second tranche: monitoring (or a stop-exit, but this tape is rising).
    assert not (isinstance(out, PlannedAction) and out.tranche)


# --- the shared plan/write-time validator (D-3) ----------------------------------------- #


def planned(kind=ActionKind.SUBMIT, limit_price=9.95, quantity=10):
    return PlannedAction(
        kind=kind,
        limit_price=limit_price,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=None,
        atr=None,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


def test_validator_rejects_each_hard_rail():
    env = make_envelope()
    assert validate_action(
        env, planned(limit_price=7.99), history=[], now=NOW
    ).rail == ("floor_price")
    assert validate_action(env, planned(quantity=101), history=[], now=NOW).rail == (
        "qty_ceiling"
    )
    recent = [
        action_event(
            env, action="submit", limit_price=9.9, at=NOW - timedelta(milliseconds=100)
        )
    ]
    assert (
        validate_action(
            env, planned(kind=ActionKind.REPRICE), history=recent, now=NOW
        ).rail
        == "cooldown_floor"
    )
    env_small = make_envelope(cancel_replace_budget=3)
    spent = [
        action_event(
            env_small, action="submit", limit_price=9.9, at=NOW - timedelta(seconds=60)
        ),
        action_event(
            env_small, action="reprice", limit_price=9.8, at=NOW - timedelta(seconds=30)
        ),
        action_event(
            env_small, action="reprice", limit_price=9.7, at=NOW - timedelta(seconds=20)
        ),
        action_event(
            env_small, action="reprice", limit_price=9.6, at=NOW - timedelta(seconds=10)
        ),
    ]
    assert (
        validate_action(
            env_small, planned(kind=ActionKind.REPRICE), history=spent, now=NOW
        ).rail
        == "cancel_replace_budget"
    )


def test_validator_passes_a_legal_action():
    env = make_envelope()
    assert validate_action(env, planned(), history=[], now=NOW) is None
