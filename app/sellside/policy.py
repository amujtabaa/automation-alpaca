"""The top-level pure decision function + the shared hard-rail validator
(WO-0018; ADR-010 §1, D-3).

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
    ClampNote,
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
# pure-math-0 (REV-0023 Phase-A2): maximum per-step price deviation vs the
# immediate raw predecessor before a print is screened as unprintable. 25% per
# ~10-30s step is an order of magnitude outside LULD trading bands, so a
# legitimately printable move never trips it while fat-finger/corrupt prints
# (the probe's 500,000x) always do. Calibration recorded as a planning note in
# INV-088 (Ameen directed completion 2026-07-15).
MAX_STEP_DEVIATION = 0.25
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


def _urgency_at(envelope: ExecutionEnvelope, t: datetime) -> float:
    """Time-to-close urgency AS OF ``t`` (pure). WO-0031: historical ratchet
    candidates use the urgency of their OWN epoch so a session-phase boundary
    (which widens time-to-close and drops current urgency) can never loosen
    an already-ratcheted stop (SOL-F-002)."""

    ttc = session_context(t).time_to_phase_close
    if ttc is None or (envelope.expires_at - t) < ttc:
        ttc = envelope.expires_at - t
    return 1.0 - min(max(ttc / URGENCY_RAMP, 0.0), 1.0)


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


def project_envelope_replaces_used(
    history: Sequence[ExecutionEvent],
) -> dict[str, int]:
    """Project lifetime replace-budget usage from execution truth.

    This is the single computation consumed by both policy enforcement and the
    operator read model. It deliberately filters the complete event ingress:
    only envelope-scoped ``ENVELOPE_ACTION`` facts with an incumbent
    budget-consuming action count. ``refused_stale`` and unknown/future action
    values therefore remain non-consuming by construction.
    """

    projected: dict[str, int] = {}
    for event in history:
        if (
            event.event_type is not ExecutionEventType.ENVELOPE_ACTION
            or event.envelope_id is None
            or event.payload.get("action") not in _BUDGET_ACTIONS
        ):
            continue
        projected[event.envelope_id] = projected.get(event.envelope_id, 0) + 1
    return projected


def _last_action_at(actions: Sequence[ExecutionEvent]) -> Optional[datetime]:
    working = [e for e in actions if e.payload.get("action") in _WORKING_ACTIONS]
    return _event_time(working[-1]) if working else None


# Order-terminal event types: the working order is DEAD once the log shows one
# of these for it (mirrors the write-time structural check's not-live set —
# FILLED / CANCELED / REJECTED).
_TERMINAL_ORDER_EVENTS = frozenset(
    {
        ExecutionEventType.FILLED,
        ExecutionEventType.CANCELED,
        ExecutionEventType.REJECTED,
    }
)


def _live_working_order_id(
    actions: Sequence[ExecutionEvent], history: Sequence[ExecutionEvent]
) -> Optional[str]:
    """WO-0025 (REV-0023 F4): "working order" means LIVE AT THE VENUE NOW —
    the newest submit/reprice action's order, unless the log already shows it
    terminal. The old predicate ("any submit event EVER", monotone in the
    event history) forced every envelope's second leg into a REPRICE of a
    dead order, which the write-time structural check rightly refused —
    freezing healthy tranche exits with a false ENVELOPE_PLAN_DIVERGENCE.
    Derived purely from the event log (H10: the log is the truth) so the
    frozen decide() contract keeps its signature."""

    working = [
        e
        for e in actions
        if e.payload.get("action") in _WORKING_ACTIONS and e.order_id is not None
    ]
    if not working:
        return None
    # Codex PR#8 #6: return the NEWEST working order that is not yet terminal —
    # scanning back past a dead replacement. A reprice whose replacement B is
    # REJECTED/CANCELED at the venue may leave predecessor A still LIVE (the
    # atomic replace never terminated it), and A must still count as the working
    # order; otherwise the policy plans a fresh submit that the write-time
    # max-1-outstanding check then refuses as stale, stranding the envelope.
    terminal_ids = {
        e.order_id
        for e in history
        if e.event_type in _TERMINAL_ORDER_EVENTS and e.order_id is not None
    }
    for e in reversed(working):
        if e.order_id not in terminal_ids:
            return e.order_id
    return None


def _rejected_probe_count(
    actions: Sequence[ExecutionEvent], history: Sequence[ExecutionEvent]
) -> int:
    """How many of this envelope's own stop-probe SUBMITs were venue-REJECTED
    (WO-0031(c), Ameen 2026-07-12): low-price venues can enforce minimum order
    sizes above one share, so a rejected protective probe doubles the next
    probe's floor (capped by remaining, always ClampNote-reported) instead of
    re-submitting the same too-small order forever. Venue-agnostic: ANY
    terminal rejection of a stop probe escalates — harmless when the true
    cause was elsewhere (the size stays remaining/floor/qty railed). Alpaca
    equities today have no whole-share minimum above 1 (verified
    docs.alpaca.markets 2026-07-12); this is forward-armor."""

    rejected_ids = {
        e.order_id
        for e in history
        if e.event_type is ExecutionEventType.REJECTED and e.order_id is not None
    }
    return sum(
        1
        for e in actions
        if e.payload.get("action") == "submit"
        and e.payload.get("stop_triggered")
        and e.order_id in rejected_ids
    )


def validate_action(
    envelope: ExecutionEnvelope,
    action: PlannedAction,
    *,
    history: Sequence[ExecutionEvent],
    now: datetime,
) -> Optional[RailViolation]:
    """The shared plan-time/write-time hard-rail check (D-3). Rails only —
    soft bounds were already clamped (and reported) upstream.

    WO-0024 (REV-0023 F3): TTL and session-phase are §2 HARD rails, so they
    are checked HERE — at both D-3 call sites and at redrive — not only in
    ``decide``'s gates. Before this, "bounds checked twice" (ADR-010 §1) was
    untrue for these two rails and a staged order could reach the venue after
    ``expires_at`` or out of phase via the redrive leg.
    """

    if now >= envelope.expires_at:
        return RailViolation(
            rail="ttl",
            detail=f"mandate expired at {envelope.expires_at.isoformat()}",
        )
    ctx = session_context(now)
    if ctx.phase is None or ctx.phase not in envelope.allowed_session_phases:
        return RailViolation(
            rail="session_phase",
            detail=(
                f"phase {ctx.phase.value if ctx.phase else 'none'} not in "
                f"allowed {[p.value for p in envelope.allowed_session_phases]}"
            ),
        )
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
        used = project_envelope_replaces_used(history).get(envelope.id, 0)
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
    # WO-0031 (SOL-F-003, H6): EVERY row that feeds features is screened, not
    # just the latest — a stale/crossed/non-finite historical print must never
    # drive bars, ATR, VWAP, regime, or sizing. Invalid history is dropped
    # (the latest row already failed closed above via the disposition gate).
    #
    # pure-math-0 (REV-0023 Phase-A2): a FINITE but absurd print passes every
    # per-row screen yet would pin ref_high via the running max and hold the
    # stop at the phantom level. Screen by STEP DEVIATION against the
    # immediate RAW predecessor (> MAX_STEP_DEVIATION is not a printable
    # move). Raw-predecessor comparison self-heals: an isolated phantom costs
    # at most two rows, a genuine gap (halt reopen) at most one — the prints
    # after a real gap agree with each other and pass.
    active_window = [
        s
        for s in snapshots
        if envelope.activated_at is None or s.updated_at >= envelope.activated_at
    ]
    suspect: set[int] = set()
    for i in range(1, len(active_window)):
        prev, cur = active_window[i - 1].last_price, active_window[i].last_price
        if (
            prev is not None
            and cur is not None
            and math.isfinite(prev)
            and math.isfinite(cur)
            and prev > 0
            and abs(cur / prev - 1.0) > MAX_STEP_DEVIATION
        ):
            suspect.add(i)
    if active_window and (len(active_window) - 1) in suspect:
        latest_raw = active_window[-1].last_price
        if latest_raw is not None and latest_raw <= envelope.floor_price:
            # Deviation-suspect AND at/below the floor: fail SAFE with an
            # EXPLICIT floor breach. We must NOT fall through to the trigger
            # logic — it keys on ``latest.last_price`` (this very phantom) and
            # then prices the order off ``latest.bid``, so a still-healthy bid
            # above the floor would sail past ``validate_action`` and let a
            # phantom below-floor print drive a real SELL (Codex PR#8 P1). A
            # genuine crash gap below the floor is a real breach; a phantom
            # here yields a spurious-but-frozen-for-human breach — never an
            # order, never silence (the WO-0021 pin). The suspect print stays
            # excluded from the feature tape either way.
            return BreachSignal(
                rail="floor_price",
                detail=(
                    f"deviation-suspect latest {latest_raw} at/below floor "
                    f"{envelope.floor_price}"
                ),
            )
        # The LATEST print is deviation-suspect and above the floor: actions
        # are priced off it, so fail quiet this tick — never size or submit
        # against a phantom.
        return StaleDataSignal(
            disposition=envelope.stale_data_disposition,
            reasons=("price_deviation",),
        )
    tape = [
        s
        for i, s in enumerate(active_window)
        if i not in suspect and not _snapshot_invalid_reasons(s)
    ]
    bars = aggregate(tape, BAR_INTERVAL)
    if len(bars) < MIN_CLASSIFY_BARS:
        return NoAction(
            reason=NoActionReason.INSUFFICIENT_DATA,
            detail=f"{len(bars)} bars < {MIN_CLASSIFY_BARS} warmup",
        )

    urgency = _urgency_at(envelope, now)

    ws = compute_working_stop(
        envelope,
        bars,
        urgency=urgency,
        # WO-0031 (SOL-F-002): historical candidates keep their own epoch's
        # urgency; the still-filling bucket never enters the ratchet.
        urgency_at=lambda t: _urgency_at(envelope, t),
        last_bar_open=bool(bars) and bars[-1].end > now,
    )

    # --- history accounting (never internal state) ------------------------- #
    actions = _own_actions(envelope, history)
    has_working_order = _live_working_order_id(actions, history) is not None
    # WO-0031 (DRIFT-SVD-2): only WORKING actions consume the tranche
    # entitlement — a refused_stale event still carries the refused action's
    # tranche flag (provenance) and must NOT burn the envelope's one tranche.
    tranche_taken = any(
        e.payload.get("tranche")
        for e in actions
        if e.payload.get("action") in _WORKING_ACTIONS
    )

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
        # marketable at the bid. A probe above the participation allowance is
        # allowed here — protection beats participation politeness on the way
        # out — but NEVER silently (WO-0031(c)/SOL-F-004, adjudicated by the
        # human seat: incumbent behavior, REPORTED): exceeding the allowance
        # carries a participation ClampNote, and a venue-REJECTED probe
        # doubles the next probe's floor (min-order-size armor for low-price
        # venues), still capped by remaining.
        probe_floor = min(remaining, 2 ** _rejected_probe_count(actions, history))
        quantity = min(remaining, max(probe_floor, absorbable))
        clamps = ws.clamps
        if quantity > absorbable:
            clamps = (
                *clamps,
                ClampNote(
                    field="participation",
                    computed=float(absorbable),
                    clamped_to=float(quantity),
                ),
            )
        desired = PlannedAction(
            kind=ActionKind.SUBMIT,
            limit_price=latest.bid,
            quantity=quantity,
            regime=ws.regime,
            urgency=urgency,
            working_stop=ws.stop,
            atr=ws.atr,
            tranche=False,
            stop_triggered=True,
            clamps=clamps,
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
        project_envelope_replaces_used(history).get(envelope.id, 0)
        >= envelope.cancel_replace_budget
    ):
        return ExhaustedSignal(
            detail=(f"cancel/replace budget {envelope.cancel_replace_budget} spent")
        )

    # --- the plan-time half of D-3 ------------------------------------------ #
    violation = validate_action(envelope, desired, history=history, now=now)
    if violation is not None:
        return BreachSignal(rail=violation.rail, detail=violation.detail)
    return desired
