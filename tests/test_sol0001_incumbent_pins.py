"""SOL-0001 crosswise findings against the INCUMBENT — FLIPPED GREEN by WO-0031.

Originally strict xfails (see git history); WO-0031 remediated all three and
this file now pins the FIXED behavior plus the two adjudicated additions:

  SOLF2  → lifetime-monotone working stop (per-epoch urgency; open bucket
           excluded from the ratchet)
  SOLF3  → the WHOLE active tape is screened — invalid history never drives
           features (H6)
  SOLF4  → the zero-allowance stop probe is REPORTED (participation
           ClampNote) and venue-rejected probes size UP (Ameen 2026-07-12)
  SVD2   → a refused_stale event never burns the tranche entitlement
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    SessionType,
)
from app.sellside.bars import Bar, aggregate
from app.sellside.policy import _urgency_at, decide
from app.sellside.trails import compute_working_stop
from app.sellside.types import NoAction, PlannedAction

BASE = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
ET = ZoneInfo("America/New_York")
TRAIL_ENV = SimpleNamespace(trail_distance_min=1.0, trail_distance_max=3.0)
NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)  # Wed regular


def _bar(i, price, vol=1.0):
    at = BASE + timedelta(seconds=30 * i)
    return Bar(at, at + timedelta(seconds=30), price, price, price, price, vol)


def _snap(sec, price, vol, bid=None, ask=None, stale=False, base=None):
    return SimpleNamespace(
        updated_at=(base or BASE) + timedelta(seconds=sec),
        last_price=price,
        volume=vol,
        bid=bid if bid is not None else price - 0.01,
        ask=ask if ask is not None else price + 0.01,
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
        activated_at=NOW - timedelta(hours=1),
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


# ================================================================== #
# SOL-F-002 — lifetime monotonicity (FLIPPED GREEN by WO-0031)
# ================================================================== #


def test_SOLF2_stop_never_decreases_across_phase_boundary():
    """The pre-market→regular urgency drop can no longer loosen the stop:
    historical candidates keep their own epoch's urgency (urgency_at)."""

    closes = [1.01 if i % 2 == 0 else 1.0 for i in range(21)] + [1.0]
    bars = [
        _bar(i, p, 0.0 if 17 <= i <= 20 else (1000.0 if i == 21 else 10.0))
        for i, p in enumerate(closes)
    ]
    env = envelope(expires_at=datetime(2026, 7, 13, 18, 0, tzinfo=ET))
    pre = datetime(2026, 7, 13, 9, 29, 59, tzinfo=ET)
    reg = datetime(2026, 7, 13, 9, 30, 0, tzinfo=ET)
    stop_pre = compute_working_stop(
        env, bars, urgency=_urgency_at(env, pre), urgency_at=lambda t: _urgency_at(env, t)
    ).stop
    stop_reg = compute_working_stop(
        env, bars, urgency=_urgency_at(env, reg), urgency_at=lambda t: _urgency_at(env, t)
    ).stop
    assert stop_pre is not None and stop_reg is not None
    assert stop_reg >= stop_pre - 1e-9, (
        f"stop loosened across the phase boundary: {stop_pre} -> {stop_reg}"
    )
    # Regression sanity: the OLD behavior (single current urgency for all
    # prefixes) genuinely differed — the boundary used to loosen the stop.
    old_pre = compute_working_stop(env, bars, urgency=_urgency_at(env, pre)).stop
    old_reg = compute_working_stop(env, bars, urgency=_urgency_at(env, reg)).stop
    assert old_reg < old_pre  # the defect the fix removes, kept as documentation


def test_SOLF2_stop_never_decreases_on_intra_bucket_rewrite():
    """A later print inside the still-open bucket cannot loosen the stop:
    the open bucket is excluded from the ratchet (last_bar_open)."""

    tape = [_snap(30 * i, 1 + 0.01 * i, 100 + i) for i in range(16)]

    def stop(xs):
        return compute_working_stop(
            TRAIL_ENV,
            aggregate(xs, timedelta(seconds=30)),
            urgency=0.0,
            last_bar_open=True,
        ).stop

    s1 = stop(tape)
    s2 = stop(tape + [_snap(451, 1.10, 115)])
    if s1 is not None:
        assert s2 is not None and s2 >= s1 - 1e-9, (
            f"stop loosened on intra-bucket rewrite: {s1} -> {s2}"
        )
    # And with MORE completed bars the property holds non-vacuously:
    tape2 = [_snap(30 * i, 1 + 0.01 * i, 100 + i) for i in range(20)]
    s3 = stop(tape2)
    s4 = stop(tape2 + [_snap(30 * 19 + 1, 1.02, 125)])  # rewrite open bucket low
    assert s3 is not None and s4 is not None and s4 >= s3 - 1e-9


# ================================================================== #
# SOL-F-003 — whole-tape screening (FLIPPED GREEN by WO-0031)
# ================================================================== #


def test_SOLF3_stale_crossed_history_never_drives_features():
    """decide()-level: a stale+crossed $10 print deep in history must not
    move ref-high/stop/regime — it is dropped before any feature math."""

    start = NOW - timedelta(minutes=30)
    clean = [
        _snap(10 * i, 1.0 + 0.001 * i, 1000.0 + 10 * i, base=start)
        for i in range(170)
    ]
    poisoned = list(clean)
    poisoned[40] = _snap(
        400, 10.0, 1400.0, bid=10.2, ask=10.1, stale=True, base=start
    )  # stale AND crossed AND wildly off-market
    env = envelope(activated_at=start)
    d_clean = decide(env, clean, now=NOW, history=[])
    d_poison = decide(env, poisoned, now=NOW, history=[])
    # Same decision shape and same working stop — the poison row changed nothing.
    assert type(d_clean) is type(d_poison)
    ws_clean = getattr(d_clean, "working_stop", None)
    ws_poison = getattr(d_poison, "working_stop", None)
    assert ws_clean == ws_poison
    if ws_poison is not None:
        assert ws_poison < 9.0  # never anchored to the $10 phantom


# ================================================================== #
# SOL-F-004 (+ Ameen adjudication) — reported probe + dynamic upsize
# ================================================================== #


def _frozen_volume_crash(base):
    """Rise on volume, then crash through any trail with ZERO volume deltas
    in the participation window — allowance floors to 0 while the stop fires."""

    tape = [_snap(10 * i, 10.0 + 0.005 * i, 1000.0 + 10 * i, base=base) for i in range(180)]
    cum = tape[-1].volume
    for j in range(60):
        tape.append(_snap(1800 + 10 * j, 10.9 - 0.038 * j, cum, base=base))  # bottoms ~8.66, above the 8.00 floor
    return tape


def test_SOLF4_zero_allowance_probe_is_reported():
    start = NOW - timedelta(minutes=40)
    env = envelope(activated_at=start)
    d = decide(env, _frozen_volume_crash(start), now=NOW, history=[])
    assert isinstance(d, PlannedAction) and d.stop_triggered
    assert d.quantity >= 1
    notes = [c for c in d.clamps if c.field == "participation"]
    assert notes and notes[0].computed == 0.0 and notes[0].clamped_to == float(
        d.quantity
    ), "the zero-allowance probe must carry a participation ClampNote"


def _action_event(env, order_id, action="submit", stop_triggered=True, tranche=False):
    return ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=NOW - timedelta(seconds=90),
        symbol=env.symbol,
        order_id=order_id,
        envelope_id=env.id,
        payload={
            "action": action,
            "stop_triggered": stop_triggered,
            "tranche": tranche,
            "quantity": 1,
        },
    )


def _order_event(order_id, event_type):
    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=NOW - timedelta(seconds=60),
        symbol="AAPL",
        order_id=order_id,
        payload={},
    )


def test_SOLF4_rejected_probe_sizes_up():
    """Venue rejected the 1-share probe (min-order-size armor): the next
    probe doubles its floor, still reported, still capped by remaining."""

    start = NOW - timedelta(minutes=40)
    env = envelope(activated_at=start)
    history = [
        _action_event(env, "probe-1"),
        _order_event("probe-1", ExecutionEventType.REJECTED),
        # a FILLED terminal on the same id would ALSO clear has_working_order;
        # REJECTED already does — the fold sees the probe as dead.
    ]
    d = decide(env, _frozen_volume_crash(start), now=NOW, history=history)
    assert isinstance(d, PlannedAction) and d.stop_triggered
    assert d.quantity >= 2, f"rejected probe must size up, planned {d.quantity}"
    assert any(c.field == "participation" for c in d.clamps)


# ================================================================== #
# DRIFT-SVD-2 — refused_stale never burns the tranche (WO-0031(d))
# ================================================================== #


def test_SVD2_refused_stale_does_not_consume_tranche():
    """A refused_stale event carries the refused action's tranche flag as
    PROVENANCE — the entitlement latch counts WORKING actions only, so the
    policy plans the tranche again on the next favorable tick."""

    import tests.test_wo0018_sellside_policy as T18

    env = T18.make_envelope()
    refusal = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=T18.NOW - timedelta(minutes=2),
        symbol=env.symbol,
        envelope_id=env.id,
        payload={
            "action": "refused_stale",
            "refused_action": "submit",
            "tranche": True,
            "rail": "qty_ceiling",
            "quantity": 50,
        },
    )
    out = decide(env, T18.spike_tape_snapshots(), now=T18.NOW, history=[refusal])
    assert isinstance(out, PlannedAction) and out.tranche is True, (
        f"a benign refusal burned the tranche entitlement: {out}"
    )
    # Control: a REAL working tranche submit still consumes it exactly once.
    taken = T18.action_event(
        env, action="submit", limit_price=12.0, at=T18.NOW - timedelta(minutes=2),
        tranche=True,
    )
    out2 = decide(env, T18.spike_tape_snapshots(), now=T18.NOW, history=[taken])
    assert not (isinstance(out2, PlannedAction) and out2.tranche)
