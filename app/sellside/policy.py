"""The top-level pure decision function + the shared hard-rail validator
(WO-0018; ADR-009 §1, D-3).

``decide(envelope, snapshots, now=..., history=...)`` is a pure function of
its arguments: the session-anchored snapshot tape (bars/ATR/VWAP derived
internally), the injected clock value, and this envelope's prior
ExecutionEvents (cooldown/budget/tranche/working-order accounting — never
internal mutable state).

``validate_action`` is THE hard-rail check: the policy runs it at plan time
and the engine seam (WO-0019) re-runs the SAME function at write time —
bounds checked twice, and a disagreement between the two runs is a software
defect (ENVELOPE_PLAN_DIVERGENCE), not merely a breach.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional, Sequence

from app.marketdata.service import MarketSnapshot
from app.models import (
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
)

from app.sellside.bars import aggregate
from app.sellside.indicators import anchored_vwap
from app.sellside.profiler import (
    VolumeWindow,
    observe,
    participation_size,
    recent_volume,
)
from app.sellside.regime import MIN_CLASSIFY_BARS, Regime
from app.sellside.session import session_context
from app.sellside.trails import compute_working_stop
from app.sellside.types import (
    ActionKind,
    BreachSignal,
    ExhaustedSignal,
    ExpiredSignal,
    NoAction,
    NoActionReason,
    PlannedAction,
    RailViolation,
    StaleDataSignal,
)

# Internal bar interval (the trail/classifier granularity).
BAR_INTERVAL = timedelta(seconds=30)
# Participation sizing window over the raw tape.
PARTICIPATION_HORIZON = timedelta(minutes=5)
# Time-to-close urgency ramp length.
URGENCY_RAMP = timedelta(minutes=30)
# Tranche trigger: extension above anchored VWAP, in trail-ATR multiples.
TRANCHE_EXTENSION_MULT = 1.5
# First-objective tranche fraction of the remaining quantity.
TRANCHE_FRACTION = 0.5
# Budget-consuming actions (a cancel/replace pair or an explicit cancel).
_BUDGET_ACTIONS = frozenset({"reprice", "cancel"})
_WORKING_ACTIONS = frozenset({"submit", "reprice"})


def _snapshot_invalid_reasons(snap: Optional[MarketSnapshot]) -> tuple[str, ...]:
    """Every way the LATEST snapshot can be unusable (fail closed on any)."""

    if snap is None:
        return ("no_snapshot",)
    reasons = []
    if snap.stale:
        reasons.append("stale")
    for name, value in (
        ("last_price", snap.last_price),
        ("bid", snap.bid),
        ("ask", snap.ask),
    ):
        if value is None or not math.isfinite(value) or value <= 0:
            reasons.append(f"{name}_invalid")
    if snap.volume is None or not math.isfinite(snap.volume) or snap.volume < 0:
        reasons.append("volume_invalid")
    if (
        snap.bid is not None
        and snap.ask is not None
        and math.isfinite(snap.bid)
        and math.isfinite(snap.ask)
        and snap.bid >= snap.ask
    ):
        reasons.append("crossed_quote")
    return tuple(reasons)


def _event_time(event: ExecutionEvent) -> datetime:
    return event.ts_event if event.ts_event is not None else event.ts_init


def _own_actions(
    envelope: ExecutionEnvelope, history: Sequence[ExecutionEvent]
) -> list[ExecutionEvent]:
    return sorted(
        (
            e
            for e in history
            if e.envelope_id == envelope.id
            and e.event_type is ExecutionEventType.ENVELOPE_ACTION
        ),
        key=_event_time,
    )


def _replaces_used(actions: Sequence[ExecutionEvent]) -> int:
    return sum(1 for e in actions if e.payload.get("action") in _BUDGET_ACTIONS)


def _last_action_at(actions: Sequence[ExecutionEvent]) -> Optional[datetime]:
    working = [e for e in actions if e.payload.get("action") in _WORKING_ACTIONS]
    return _event_time(working[-1]) if working else None


def validate_action(
    envelope: ExecutionEnvelope,
    action: PlannedAction,
    *,
    history: Sequence[ExecutionEvent],
    now: datetime,
) -> Optional[RailViolation]:
    """The shared plan-time/write-time hard-rail check (D-3). Rails only —
    soft bounds were already clamped (and reported) upstream."""

    if action.limit_price < envelope.floor_price:
        return RailViolation(
            rail="floor_price",
            detail=(f"limit {action.limit_price} below floor {envelope.floor_price}"),
        )
    remaining = envelope.remaining_quantity or 0
    if action.quantity <= 0 or action.quantity > remaining:
        return RailViolation(
            rail="qty_ceiling",
            detail=f"size {action.quantity} outside (0, {remaining}]",
        )
    actions = _own_actions(envelope, history)
    last_at = _last_action_at(actions)
    if last_at is not None:
        elapsed = now - last_at
        floor = timedelta(milliseconds=envelope.cooldown_floor_ms)
        if elapsed < floor:
            return RailViolation(
                rail="cooldown_floor",
                detail=f"{elapsed.total_seconds() * 1000:.0f}ms since last action",
            )
    if action.kind is ActionKind.REPRICE:
        used = _replaces_used(actions)
        if used >= envelope.cancel_replace_budget:
            return RailViolation(
                rail="cancel_replace_budget",
                detail=(f"{used} of {envelope.cancel_replace_budget} replaces used"),
            )
    return None


def decide(
    envelope: ExecutionEnvelope,
    snapshots: Sequence[MarketSnapshot],
    *,
    now: datetime,
    history: Sequence[ExecutionEvent],
):
    """One tick's pure decision. See the package docstring for the contract;
    the returned shape is one of the ``app.sellside.types`` variants."""

    # --- gates (cheap → expensive, all fail closed) ----------------------- #
    if envelope.status is not EnvelopeStatus.ACTIVE:
        return NoAction(
            reason=NoActionReason.NOT_ACTIVE,
            detail=f"envelope is {envelope.status.value}",
        )
    if now >= envelope.expires_at:
        return ExpiredSignal(disposition=envelope.expiry_disposition)
    ctx = session_context(now)
    if ctx.phase is None or ctx.phase not in envelope.allowed_session_phases:
        return NoAction(
            reason=NoActionReason.OUT_OF_PHASE,
            detail=f"phase {ctx.phase.value if ctx.phase else 'none'}",
        )
    latest = snapshots[-1] if snapshots else None
    bad = _snapshot_invalid_reasons(latest)
    if bad:
        return StaleDataSignal(disposition=envelope.stale_data_disposition, reasons=bad)
    assert latest is not None  # narrowed by the gate above
    assert latest.bid is not None and latest.last_price is not None
    remaining = envelope.remaining_quantity or 0
    if remaining <= 0:
        return NoAction(
            reason=NoActionReason.NOTHING_TO_DO, detail="remaining quantity is 0"
        )

    # --- market structure since activation -------------------------------- #
    tape = [
        s
        for s in snapshots
        if envelope.activated_at is None or s.updated_at >= envelope.activated_at
    ]
    bars = aggregate(tape, BAR_INTERVAL)
    if len(bars) < MIN_CLASSIFY_BARS:
        return NoAction(
            reason=NoActionReason.INSUFFICIENT_DATA,
            detail=f"{len(bars)} bars < {MIN_CLASSIFY_BARS} warmup",
        )

    ttc = ctx.time_to_phase_close
    if ttc is None or (envelope.expires_at - now) < ttc:
        ttc = envelope.expires_at - now
    urgency = 1.0 - min(max(ttc / URGENCY_RAMP, 0.0), 1.0)

    ws = compute_working_stop(envelope, bars, urgency=urgency)

    # --- history accounting (never internal state) ------------------------- #
    actions = _own_actions(envelope, history)
    has_working_order = any(
        e.payload.get("action") in _WORKING_ACTIONS for e in actions
    )
    tranche_taken = any(e.payload.get("tranche") for e in actions)

    # --- participation sizing off the raw tape ----------------------------- #
    window = VolumeWindow(horizon=PARTICIPATION_HORIZON)
    for s in tape:
        window = observe(window, at=s.updated_at, cumulative_volume=s.volume)
    absorbable = participation_size(
        recent_volume(window), envelope.participation_rate_cap, remaining
    )

    # --- triggers ----------------------------------------------------------- #
    desired: Optional[PlannedAction] = None
    if (
        ws.stop is not None
        and latest.last_price is not None
        and (latest.last_price <= ws.stop)
    ):
        # Breakdown through the working stop: exit what the tape absorbs,
        # marketable at the bid (a 1-share probe is allowed here — protection
        # beats participation politeness on the way out).
        desired = PlannedAction(
            kind=ActionKind.SUBMIT,
            limit_price=latest.bid,
            quantity=min(remaining, max(1, absorbable)),
            regime=ws.regime,
            urgency=urgency,
            working_stop=ws.stop,
            atr=ws.atr,
            tranche=False,
            stop_triggered=True,
            clamps=ws.clamps,
        )
    elif not tranche_taken and ws.regime in (
        Regime.FAST_SPIKE,
        Regime.STEADY_SURGE,
    ):
        vwap = anchored_vwap(tape)
        if (
            vwap is not None
            and ws.atr is not None
            and latest.last_price is not None
            and latest.last_price - vwap >= TRANCHE_EXTENSION_MULT * ws.atr
        ):
            size = min(absorbable, max(1, math.ceil(remaining * TRANCHE_FRACTION)))
            if size < 1:
                return NoAction(
                    reason=NoActionReason.NO_LIQUIDITY,
                    detail="participation cap floors the tranche to 0",
                    working_stop=ws.stop,
                    regime=ws.regime,
                )
            desired = PlannedAction(
                kind=ActionKind.SUBMIT,
                limit_price=latest.bid,
                quantity=size,
                regime=ws.regime,
                urgency=urgency,
                working_stop=ws.stop,
                atr=ws.atr,
                tranche=True,
                stop_triggered=False,
                clamps=ws.clamps,
            )

    if desired is None:
        return NoAction(
            reason=NoActionReason.MONITORING,
            working_stop=ws.stop,
            regime=ws.regime,
        )

    # --- rate/budget gates from history -------------------------------------- #
    last_at = _last_action_at(actions)
    cooldown = timedelta(milliseconds=envelope.cooldown_floor_ms)
    if last_at is not None and (now - last_at) < cooldown:
        return NoAction(
            reason=NoActionReason.COOLDOWN_WAIT,
            wait_until=last_at + cooldown,
            working_stop=ws.stop,
            regime=ws.regime,
        )
    if has_working_order:
        desired = PlannedAction(**{**desired.__dict__, "kind": ActionKind.REPRICE})
    if desired.kind is ActionKind.REPRICE and (
        _replaces_used(actions) >= envelope.cancel_replace_budget
    ):
        return ExhaustedSignal(
            detail=(f"cancel/replace budget {envelope.cancel_replace_budget} spent")
        )

    # --- the plan-time half of D-3 ------------------------------------------ #
    violation = validate_action(envelope, desired, history=history, now=now)
    if violation is not None:
        return BreachSignal(rail=violation.rail, detail=violation.detail)
    return desired
