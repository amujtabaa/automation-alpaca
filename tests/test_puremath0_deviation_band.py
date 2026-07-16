"""pure-math-0 (REV-0023 Phase-A2, P2) — magnitude/step-deviation screening.

A FINITE, positive, non-crossed, non-stale — but absurd — print used to pass
``_snapshot_invalid_reasons`` untouched, pin ``ref_high`` via the running max,
and hold the working stop at the phantom level (perpetual ``stop_triggered``
SUBMIT). The band screens any print whose step deviation vs its immediate raw
predecessor exceeds ``MAX_STEP_DEVIATION``:

* mid-tape phantom → dropped from features (decision identical to clean tape);
* phantom as the LATEST print → fail-quiet ``StaleDataSignal`` this tick
  (never priced against) — UNLESS the print sits at/below the floor, where the
  hard floor rail outranks the band (BreachSignal, never silence: a real crash
  gap gets immediate protection; a phantom yields a spurious-but-frozen
  breach, never an order);
* the band self-heals: comparisons run against the raw predecessor, so a
  genuine gap costs at most one row and an isolated phantom at most two.

Calibration (planning record, Ameen directed completion 2026-07-15):
``MAX_STEP_DEVIATION = 0.25`` per ~10-30s step — an order of magnitude outside
LULD trading bands, so a legitimately printable move never trips it, while
fat-finger/corrupt prints (the probe's 500,000x) always do.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    SessionType,
)
from app.sellside.policy import decide
from app.sellside.types import PlannedAction, StaleDataSignal

NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)  # Wed regular
START = NOW - timedelta(minutes=30)


def _snap(sec, price, vol, stale=False):
    return SimpleNamespace(
        updated_at=START + timedelta(seconds=sec),
        last_price=price,
        volume=vol,
        bid=price - 0.01,
        ask=price + 0.01,
        stale=stale,
    )


def envelope(**overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id="si-1",
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=8.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.5,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=10,
        expires_at=NOW + timedelta(hours=6),
        allowed_session_phases=list(SessionType),
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        status=EnvelopeStatus.ACTIVE,
        activated_at=START,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def _tape(n=170):
    # Price scale ABOVE the 8.00 floor (the WO-0031 vacuous-pin lesson: a
    # below-floor tape returns BreachSignal for clean AND poisoned alike).
    return [_snap(10 * i, 10.0 + 0.001 * i, 1000.0 + 10 * i) for i in range(n)]


def test_mid_tape_absurd_print_never_pins_ref_high():
    clean = _tape()
    poisoned = list(clean)
    # Finite, positive, non-crossed, non-stale — passes every per-row screen.
    poisoned[40] = _snap(400, 1_000_000.0, 1400.0)
    env = envelope()
    d_clean = decide(env, clean, now=NOW, history=[])
    d_poison = decide(env, poisoned, now=NOW, history=[])
    assert type(d_clean) is type(d_poison)
    ws_clean = getattr(d_clean, "working_stop", None)
    ws_poison = getattr(d_poison, "working_stop", None)
    assert ws_clean == ws_poison
    if ws_poison is not None:
        assert ws_poison < 11.0, f"stop anchored to the phantom: {ws_poison}"
    # And never a phantom-driven stop_triggered SUBMIT:
    if isinstance(d_poison, PlannedAction):
        assert not d_poison.stop_triggered or isinstance(d_clean, PlannedAction)


def test_absurd_latest_print_fails_quiet_not_priced():
    tape = _tape()
    tape.append(_snap(1700, 1_000_000.0, 3000.0))  # phantom is the LATEST print
    env = envelope()
    d = decide(env, tape, now=NOW, history=[])
    assert isinstance(d, StaleDataSignal), (
        f"an absurd LATEST print must fail quiet, got {type(d).__name__}"
    )
    assert "price_deviation" in d.reasons


def test_band_self_heals_after_isolated_phantom():
    # phantom mid-tape, then normal prints: the row after the phantom deviates
    # from IT (also dropped), everything later is clean — decide still works.
    tape = _tape()
    tape[80] = _snap(800, 1_000_000.0, 1800.0)
    env = envelope()
    d = decide(env, tape, now=NOW, history=[])
    assert not isinstance(d, StaleDataSignal)  # latest rows are fine


def test_legitimate_moves_inside_band_untouched():
    # A steady drift and a sharp-but-printable 3% step never trip the band.
    tape = _tape(120)
    tape.append(_snap(1200, tape[-1].last_price * 1.03, 2300.0))
    for j in range(1, 40):
        tape.append(_snap(1200 + 10 * j, tape[-1].last_price, 2300.0 + j))
    env = envelope()
    d = decide(env, tape, now=NOW, history=[])
    assert not isinstance(d, StaleDataSignal)


def test_deviation_yields_to_floor_breach_never_silence():
    """Precedence pin (found by the WO-0021 gap tape breaking the first band
    cut): a deviation-suspect LATEST print AT/BELOW the floor must fall
    through to the hard floor rail — BreachSignal, never StaleDataSignal,
    never a submit. Fail-safe beats fail-quiet below the floor."""

    from app.sellside.types import BreachSignal

    tape = _tape(120)  # ~10.0-10.12, floor 8.00
    tape.append(_snap(1200, 7.50, 3000.0))  # one-tick -26% gap UNDER the floor
    env = envelope()
    d = decide(env, tape, now=NOW, history=[])
    assert isinstance(d, BreachSignal), f"got {type(d).__name__}: {d}"
    assert d.rail == "floor_price"


def _snap_split(sec, last, bid, vol):
    """A snapshot whose last_price and bid can diverge (the healthy-quote /
    phantom-last case ``_snap`` cannot express, since it pins bid=last-0.01)."""
    return SimpleNamespace(
        updated_at=START + timedelta(seconds=sec),
        last_price=last,
        volume=vol,
        bid=bid,
        ask=bid + 0.02,
        stale=False,
    )


def test_suspect_below_floor_last_with_healthy_bid_still_fails_closed():
    """Codex PR#8 P1 (policy.py:356): a deviation-suspect LATEST print BELOW the
    floor must fail closed EVEN WHEN the bid is still above the floor. The old
    `pass` fell through to the stop-trigger, which keys on the phantom
    ``latest.last_price`` and then prices the order off the healthy bid — so
    ``validate_action`` (which checks the bid-priced LIMIT vs the floor) saw no
    breach, and a phantom below-floor last drove a real SELL. Invalid market
    data must never drive a submission (safety rail); below the floor that is a
    BreachSignal, never an order, never silence."""

    from app.sellside.types import BreachSignal

    tape = _tape(120)  # ~10.0-10.12, floor 8.00
    # Phantom LATEST: last crashes to 1.00 (below the 8.00 floor, a >25% step
    # deviation) while the quote stays healthy at 9.50 (ABOVE the floor).
    tape.append(_snap_split(1200, last=1.00, bid=9.50, vol=3000.0))
    env = envelope()
    d = decide(env, tape, now=NOW, history=[])
    assert isinstance(d, BreachSignal), (
        f"a suspect below-floor last with a healthy bid must fail closed, "
        f"got {type(d).__name__}: {d}"
    )
    assert d.rail == "floor_price"
