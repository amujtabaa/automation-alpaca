"""SOL-0001 Causal Quote-Mid Ratchet (CQMR) sell-side policy.

The rival keeps the frozen public contract but deliberately uses different
mechanisms from the incumbent:

* quote-mid structure instead of raw last-print highs;
* robust ATR + signed path efficiency instead of a return quantile alone;
* causal per-step urgency instead of applying today's urgency to old bars;
* spread/gap stress as explicit uncertainty;
* working-stop continuity recovered from event history after freeze/resume.

All numeric constants are harness-tunable defaults, not calibrated claims.
There is no IO, mutable module state, or wall-clock read.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from statistics import median
from typing import Any, Optional, Sequence, TypeGuard
from zoneinfo import ZoneInfo

from app.marketdata.service import MarketSnapshot
from app.models import (
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    SessionType,
)
from app.sellside.policy import validate_action
from app.sellside.types import (
    ActionKind,
    BreachSignal,
    ClampNote,
    ExhaustedSignal,
    ExpiredSignal,
    NoAction,
    NoActionReason,
    PlannedAction,
    Regime,
    StaleDataSignal,
)


# Harness-tunable defaults.  Mechanisms transfer; these values do not.
BAR_INTERVAL = timedelta(seconds=30)
MIN_BARS = 12
ATR_PERIOD = 12
BASELINE_BARS = 24
TREND_BARS = 8
PARTICIPATION_HORIZON = timedelta(minutes=5)
URGENCY_RAMP = timedelta(minutes=30)
TRANCHE_FRACTION = 0.50
TRANCHE_EXTENSION_ATR = 1.25
SPIKE_ATR_RATIO = 1.75
SPIKE_VOLUME_RATIO = 1.75
SURGE_EFFICIENCY = 0.62
MATURE_EFFICIENCY = 0.35
FADE_EFFICIENCY = -0.25
DOWNSIDE_IMPULSE_ATR = -0.75
FAST_SPIKE_NET_ATR = 1.50
SURGE_NET_ATR = 1.00
TIGHTEN_DOWNSIDE_ATR = -0.50
SURGE_TRAIL_RANGE_FRACTION = 0.70
MATURE_TRAIL_RANGE_FRACTION = 0.50
STRESS_TRAIL_RANGE_FRACTION = 0.80
SPREAD_STRESS_ATR = 0.75
MAX_BAR_GAP_MULTIPLE = 3.0
LAST_QUOTE_TOLERANCE_SPREADS = 2.0

EASTERN = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Bar:
    start: datetime
    end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: float = 0.0


@dataclass(frozen=True)
class WorkingStopResult:
    stop: Optional[float]
    candidate: Optional[float]
    reference: Optional[float]
    regime: Regime
    atr: Optional[float]
    tightened: bool
    liquidity_stressed: bool
    clamps: tuple[ClampNote, ...] = ()

    @property
    def ref_high(self) -> Optional[float]:
        """Compatibility name used by the incumbent invariant suite."""

        return self.reference


@dataclass(frozen=True)
class _Observation:
    at: datetime
    price: float
    spread: float
    cumulative_volume: float


@dataclass(frozen=True)
class _ChildState:
    working: bool
    blocked: bool = False
    detail: str = ""
    violation: Optional[str] = None


def _finite_positive(value: object) -> TypeGuard[int | float]:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _phase_and_close(at: datetime) -> tuple[Optional[SessionType], Optional[datetime]]:
    if at.tzinfo is None:
        return None, None
    local = at.astimezone(EASTERN)
    if local.weekday() >= 5:
        return None, None
    value = local.time()
    if time(4, 0) <= value < time(9, 30):
        phase, close = SessionType.PRE_MARKET, time(9, 30)
    elif time(9, 30) <= value < time(16, 0):
        phase, close = SessionType.REGULAR, time(16, 0)
    elif time(16, 0) <= value < time(20, 0):
        phase, close = SessionType.AFTER_HOURS, time(20, 0)
    else:
        return None, None
    return phase, local.replace(
        hour=close.hour, minute=close.minute, second=0, microsecond=0
    )


def _latest_invalid_reasons(
    envelope: ExecutionEnvelope,
    snapshots: Sequence[MarketSnapshot],
) -> tuple[str, ...]:
    if not snapshots:
        return ("no_snapshot",)
    if any(b.updated_at < a.updated_at for a, b in zip(snapshots, snapshots[1:])):
        return ("non_monotonic_tape",)
    snap = snapshots[-1]
    reasons: list[str] = []
    if snap.symbol != envelope.symbol:
        reasons.append("symbol_mismatch")
    if snap.stale:
        reasons.append("stale")
    for name, value in (
        ("last_price", snap.last_price),
        ("bid", snap.bid),
        ("ask", snap.ask),
    ):
        if not _finite_positive(value):
            reasons.append(f"{name}_invalid")
    if (
        not isinstance(snap.volume, (int, float))
        or isinstance(snap.volume, bool)
        or not math.isfinite(snap.volume)
        or snap.volume < 0
    ):
        reasons.append("volume_invalid")
    if _finite_positive(snap.bid) and _finite_positive(snap.ask):
        assert snap.bid is not None and snap.ask is not None
        if snap.bid >= snap.ask:
            reasons.append("crossed_quote")
        elif _finite_positive(snap.last_price):
            assert snap.last_price is not None
            spread = snap.ask - snap.bid
            lo = snap.bid - LAST_QUOTE_TOLERANCE_SPREADS * spread
            hi = snap.ask + LAST_QUOTE_TOLERANCE_SPREADS * spread
            if not lo <= snap.last_price <= hi:
                reasons.append("last_outside_quote")
    return tuple(reasons)


def _observation(snap: MarketSnapshot, symbol: str) -> Optional[_Observation]:
    if snap.symbol != symbol or snap.stale:
        return None
    if not all(_finite_positive(v) for v in (snap.last_price, snap.bid, snap.ask)):
        return None
    if (
        not isinstance(snap.volume, (int, float))
        or isinstance(snap.volume, bool)
        or not math.isfinite(snap.volume)
        or snap.volume < 0
    ):
        return None
    assert snap.bid is not None and snap.ask is not None and snap.last_price is not None
    if snap.bid >= snap.ask:
        return None
    spread = snap.ask - snap.bid
    lo = snap.bid - LAST_QUOTE_TOLERANCE_SPREADS * spread
    hi = snap.ask + LAST_QUOTE_TOLERANCE_SPREADS * spread
    # A lone off-market print never becomes a structural high.  The quote mid
    # remains usable; a wildly inconsistent latest row was already failed closed.
    price = (snap.bid + snap.ask) / 2.0
    if not lo <= snap.last_price <= hi:
        price = (snap.bid + snap.ask) / 2.0
    return _Observation(
        at=snap.updated_at,
        price=price,
        spread=spread,
        cumulative_volume=float(snap.volume),
    )


def _event_time(event: ExecutionEvent) -> datetime:
    return event.ts_event if event.ts_event is not None else event.ts_init


def _own_actions(
    envelope: ExecutionEnvelope, history: Sequence[ExecutionEvent]
) -> tuple[ExecutionEvent, ...]:
    return tuple(
        sorted(
            (
                event
                for event in history
                if event.envelope_id == envelope.id
                and event.event_type is ExecutionEventType.ENVELOPE_ACTION
            ),
            key=_event_time,
        )
    )


def _own_history(
    envelope: ExecutionEnvelope, history: Sequence[ExecutionEvent]
) -> tuple[ExecutionEvent, ...]:
    def key(event: ExecutionEvent) -> tuple[int, datetime, str]:
        sequence = event.sequence if event.sequence > 0 else 2**63 - 1
        return sequence, _event_time(event), event.id

    return tuple(
        sorted(
            (event for event in history if event.envelope_id == envelope.id),
            key=key,
        )
    )


def _child_state(
    envelope: ExecutionEnvelope, history: Sequence[ExecutionEvent]
) -> _ChildState:
    """Conservative max-one-child fold over the envelope's own event history."""

    working_ids: set[str] = set()
    anonymous_working = False
    cancel_pending = False
    ambiguous = False
    terminal = {
        ExecutionEventType.CANCELED,
        ExecutionEventType.REJECTED,
        ExecutionEventType.FILLED,
        ExecutionEventType.EXPIRED,
        ExecutionEventType.REPLACED,
    }
    for event in _own_history(envelope, history):
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION:
            action = event.payload.get("action")
            if action == "submit":
                if event.order_id is not None:
                    if working_ids or anonymous_working:
                        return _ChildState(
                            working=True,
                            violation="more than one submit is outstanding",
                        )
                    working_ids.add(event.order_id)
                elif anonymous_working or working_ids:
                    return _ChildState(
                        working=True,
                        violation="more than one anonymous submit is outstanding",
                    )
                else:
                    anonymous_working = True
            elif action == "reprice":
                anonymous_working = anonymous_working or not working_ids
            elif action == "cancel":
                cancel_pending = True
        elif event.event_type is ExecutionEventType.CANCEL_PENDING:
            cancel_pending = True
        elif event.event_type in (
            ExecutionEventType.TIMEOUT_QUARANTINE,
            ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
        ):
            ambiguous = True
        elif event.event_type in terminal:
            if event.order_id is not None:
                working_ids.discard(event.order_id)
            else:
                anonymous_working = False
            cancel_pending = False
            ambiguous = False

    working = bool(working_ids) or anonymous_working
    if len(working_ids) + int(anonymous_working) > envelope.max_outstanding_children:
        return _ChildState(
            working=True,
            violation="history exceeds max_outstanding_children",
        )
    if ambiguous:
        return _ChildState(working=working, blocked=True, detail="child is ambiguous")
    if cancel_pending:
        return _ChildState(
            working=working,
            blocked=True,
            detail="cancel is not broker-confirmed",
        )
    return _ChildState(working=working)


def _tape_start(
    envelope: ExecutionEnvelope, history: Sequence[ExecutionEvent]
) -> Optional[datetime]:
    times = [
        _event_time(event)
        for event in history
        if event.envelope_id == envelope.id
        and event.event_type
        in (
            ExecutionEventType.ENVELOPE_ACTIVATED,
            ExecutionEventType.ENVELOPE_RESUMED,
            ExecutionEventType.ENVELOPE_ACTION,
        )
    ]
    if envelope.activated_at is not None:
        times.append(envelope.activated_at)
    return min(times) if times else envelope.activated_at


def _prior_working_stop(
    envelope: ExecutionEnvelope, history: Sequence[ExecutionEvent]
) -> Optional[float]:
    values = [
        event.payload.get("working_stop") for event in _own_actions(envelope, history)
    ]
    finite = [float(value) for value in values if _finite_positive(value)]
    return max(finite) if finite else None


def aggregate(
    snapshots: Sequence[MarketSnapshot], interval: timedelta = BAR_INTERVAL
) -> tuple[Bar, ...]:
    """Build quote-mid bars; cumulative-volume resets re-baseline at zero."""

    seconds = interval.total_seconds()
    if seconds <= 0:
        raise ValueError("bar interval must be positive")
    if not snapshots:
        return ()
    symbol = snapshots[-1].symbol
    observations = [
        obs for snap in snapshots if (obs := _observation(snap, symbol)) is not None
    ]
    if not observations:
        return ()
    observations.sort(key=lambda row: row.at)

    buckets: dict[int, list[tuple[_Observation, float]]] = {}
    prior_volume: Optional[float] = None
    for obs in observations:
        delta = 0.0
        if prior_volume is not None and obs.cumulative_volume >= prior_volume:
            delta = obs.cumulative_volume - prior_volume
        prior_volume = obs.cumulative_volume
        index = int(obs.at.timestamp() // seconds)
        buckets.setdefault(index, []).append((obs, delta))

    result: list[Bar] = []
    for index in sorted(buckets):
        rows = buckets[index]
        prices = [row.price for row, _ in rows]
        spreads = [row.spread for row, _ in rows]
        start = datetime.fromtimestamp(index * seconds, tz=rows[0][0].at.tzinfo)
        result.append(
            Bar(
                start=start,
                end=start + interval,
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=sum(delta for _, delta in rows),
                spread=median(spreads),
            )
        )
    return tuple(result)


def _true_ranges(bars: Sequence[Any]) -> list[float]:
    if not bars:
        return []
    first = bars[0]
    ranges = [float(first.high) - float(first.low)]
    for previous, current in zip(bars, bars[1:]):
        ranges.append(
            max(
                float(current.high) - float(current.low),
                abs(float(current.high) - float(previous.close)),
                abs(float(current.low) - float(previous.close)),
            )
        )
    return [value for value in ranges if math.isfinite(value) and value >= 0]


def robust_atr(bars: Sequence[Any], period: int = ATR_PERIOD) -> Optional[float]:
    ranges = _true_ranges(bars)
    if period <= 0 or len(ranges) < period:
        return None
    value = median(ranges[-period:])
    return value if value > 0 else None


def _path_efficiency(bars: Sequence[Any]) -> float:
    if len(bars) < 2:
        return 0.0
    closes = [float(bar.close) for bar in bars]
    travel = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
    return (closes[-1] - closes[0]) / travel if travel > 0 else 0.0


def _volume_ratio(bars: Sequence[Any]) -> float:
    if len(bars) < 2 * TREND_BARS:
        return 1.0
    recent = median(float(bar.volume) for bar in bars[-TREND_BARS:])
    baseline = median(float(bar.volume) for bar in bars[-2 * TREND_BARS : -TREND_BARS])
    return recent / baseline if baseline > 0 else (math.inf if recent > 0 else 1.0)


def classify(
    bars: Sequence[Any],
    *,
    atr_now: Optional[float] = None,
    atr_baseline: Optional[float] = None,
) -> Regime:
    """Five-way robust classifier; thresholds are harness-tunable defaults."""

    if len(bars) < MIN_BARS:
        return Regime.UNCERTAIN
    current_atr = atr_now if _finite_positive(atr_now) else robust_atr(bars)
    earlier = bars[:-TREND_BARS]
    baseline_atr = (
        atr_baseline
        if _finite_positive(atr_baseline)
        else robust_atr(earlier[-BASELINE_BARS:])
    )
    if not _finite_positive(current_atr) or not _finite_positive(baseline_atr):
        return Regime.UNCERTAIN
    assert current_atr is not None and baseline_atr is not None

    window = bars[-TREND_BARS:]
    efficiency = _path_efficiency(window)
    net_atr = (float(window[-1].close) - float(window[0].open)) / current_atr
    last_move_atr = (float(window[-1].close) - float(window[-2].close)) / current_atr
    atr_ratio = current_atr / baseline_atr
    volume_ratio = _volume_ratio(bars)

    if efficiency <= FADE_EFFICIENCY or last_move_atr <= DOWNSIDE_IMPULSE_ATR:
        return Regime.STALL_FADE
    if (
        atr_ratio >= SPIKE_ATR_RATIO
        and volume_ratio >= SPIKE_VOLUME_RATIO
        and efficiency >= SURGE_EFFICIENCY
        and net_atr > FAST_SPIKE_NET_ATR
    ):
        return Regime.FAST_SPIKE
    if efficiency >= SURGE_EFFICIENCY and net_atr > SURGE_NET_ATR:
        return Regime.STEADY_SURGE
    if efficiency >= MATURE_EFFICIENCY and net_atr > 0:
        return Regime.MATURE_TREND
    return Regime.UNCERTAIN


def _gap_stressed(bars: Sequence[Any]) -> bool:
    if len(bars) < 2:
        return False
    gaps = [
        (b.start - a.start).total_seconds()
        for a, b in zip(bars, bars[1:])
        if b.start > a.start
    ]
    if not gaps:
        return False
    expected = BAR_INTERVAL.total_seconds()
    return max(gaps[-TREND_BARS:]) > MAX_BAR_GAP_MULTIPLE * expected


def _spread_stressed(bars: Sequence[Any], atr_value: float) -> bool:
    spreads = [float(getattr(bar, "spread", 0.0)) for bar in bars[-TREND_BARS:]]
    return bool(spreads) and median(spreads) >= SPREAD_STRESS_ATR * atr_value


def _urgency_at(envelope: ExecutionEnvelope, at: datetime) -> float:
    _, phase_close = _phase_and_close(at)
    deadline = envelope.expires_at
    if phase_close is not None:
        deadline = min(deadline, phase_close.astimezone(deadline.tzinfo))
    remaining = max(0.0, (deadline - at).total_seconds())
    ramp = URGENCY_RAMP.total_seconds()
    return 1.0 - min(remaining / ramp, 1.0)


def _coerce_bars(data: Sequence[Any]) -> tuple[Any, ...]:
    if not data:
        return ()
    if hasattr(data[0], "last_price"):
        bars = aggregate(data)  # type: ignore[arg-type]
        latest = data[-1]
        # A partial wall-clock bucket is mutable as more snapshots arrive.
        # Never ratchet from it; the latest price can still trigger the stop
        # established by completed causal bars.
        if bars and latest.updated_at < bars[-1].end:
            return bars[:-1]
        return bars
    return tuple(data)


def compute_working_stop(
    envelope: ExecutionEnvelope,
    data: Sequence[Any],
    *,
    now: Optional[datetime] = None,
    history: Sequence[ExecutionEvent] = (),
    urgency: Optional[float] = None,
) -> WorkingStopResult:
    """Causal monotone stop over a growing bar/snapshot tape."""

    bars = _coerce_bars(data)
    stop = _prior_working_stop(envelope, history)
    final_candidate: Optional[float] = None
    final_reference: Optional[float] = None
    final_atr: Optional[float] = None
    final_regime = Regime.UNCERTAIN
    final_tightened = False
    final_stressed = False
    final_clamps: tuple[ClampNote, ...] = ()

    for cut in range(MIN_BARS, len(bars) + 1):
        prefix = bars[:cut]
        atr_value = robust_atr(prefix)
        if atr_value is None:
            continue
        baseline = robust_atr(prefix[:-TREND_BARS][-BASELINE_BARS:])
        regime = classify(prefix, atr_now=atr_value, atr_baseline=baseline)
        reference = max(float(bar.high) for bar in prefix)
        efficiency = _path_efficiency(prefix[-TREND_BARS:])
        last_move = float(prefix[-1].close) - float(prefix[-2].close)
        stressed = _gap_stressed(prefix) or _spread_stressed(prefix, atr_value)
        tightening = (
            regime is Regime.STALL_FADE
            or last_move < TIGHTEN_DOWNSIDE_ATR * atr_value
        )

        lo = envelope.trail_distance_min
        hi = envelope.trail_distance_max
        if tightening:
            raw_multiple = lo
        elif regime is Regime.FAST_SPIKE:
            # Let an accelerating spike breathe; tighten only when velocity fails.
            raw_multiple = hi if efficiency > SURGE_EFFICIENCY else (lo + hi) / 2
        elif regime is Regime.STEADY_SURGE:
            raw_multiple = lo + SURGE_TRAIL_RANGE_FRACTION * (hi - lo)
        elif regime is Regime.MATURE_TREND:
            raw_multiple = lo + MATURE_TRAIL_RANGE_FRACTION * (hi - lo)
        else:
            raw_multiple = hi
        if stressed:
            raw_multiple = max(
                raw_multiple,
                lo + STRESS_TRAIL_RANGE_FRACTION * (hi - lo),
            )

        step_urgency = (
            min(max(urgency, 0.0), 1.0)
            if urgency is not None
            else _urgency_at(envelope, prefix[-1].end)
        )
        effective = raw_multiple - step_urgency * (raw_multiple - lo)
        bounded = min(max(effective, lo), hi)
        clamps: list[ClampNote] = []
        if bounded != effective:
            clamps.append(
                ClampNote(
                    field="trail_multiple",
                    computed=effective,
                    clamped_to=bounded,
                )
            )
        candidate = reference - bounded * atr_value
        # Explicit floor assertion by construction: never closer than lo * ATR.
        candidate = min(candidate, reference - lo * atr_value)
        stop = candidate if stop is None else max(stop, candidate)

        final_candidate = candidate
        final_reference = reference
        final_atr = atr_value
        final_regime = regime
        final_tightened = tightening
        final_stressed = stressed
        final_clamps = tuple(clamps)

    return WorkingStopResult(
        stop=stop,
        candidate=final_candidate,
        reference=final_reference,
        regime=final_regime,
        atr=final_atr,
        tightened=final_tightened,
        liquidity_stressed=final_stressed,
        clamps=final_clamps,
    )


def _recent_volume(observations: Sequence[_Observation], now: datetime) -> float:
    rows = [row for row in observations if row.at >= now - PARTICIPATION_HORIZON]
    total = 0.0
    for previous, current in zip(rows, rows[1:]):
        delta = current.cumulative_volume - previous.cumulative_volume
        if delta > 0:
            total += delta
    return total


def _anchored_vwap(observations: Sequence[_Observation]) -> Optional[float]:
    weighted = 0.0
    volume = 0.0
    for previous, current in zip(observations, observations[1:]):
        delta = current.cumulative_volume - previous.cumulative_volume
        if delta > 0:
            weighted += current.price * delta
            volume += delta
    return weighted / volume if volume > 0 else None


def _last_action_at(actions: Sequence[ExecutionEvent]) -> Optional[datetime]:
    timed = [
        event
        for event in actions
        if event.payload.get("action") in ("submit", "reprice")
    ]
    return _event_time(timed[-1]) if timed else None


def _budget_used(actions: Sequence[ExecutionEvent]) -> int:
    return sum(
        event.payload.get("action") in ("reprice", "cancel") for event in actions
    )


def _tranche_filled(
    envelope: ExecutionEnvelope, history: Sequence[ExecutionEvent]
) -> bool:
    """Consume tranche entitlement on a deduped fill, never on intent alone."""

    tranche_orders: set[str] = set()
    anonymous_tranche = False
    seen_fills: set[str] = set()
    for event in _own_history(envelope, history):
        if (
            event.event_type is ExecutionEventType.ENVELOPE_ACTION
            and event.payload.get("tranche") is True
        ):
            if event.order_id is None:
                anonymous_tranche = True
            else:
                tranche_orders.add(event.order_id)
            continue
        if event.event_type is not ExecutionEventType.FILL:
            continue
        fill_key = event.dedupe_key or event.id
        if fill_key in seen_fills:
            continue
        seen_fills.add(fill_key)
        if (
            event.quantity is not None
            and event.quantity > 0
            and (event.order_id in tranche_orders or anonymous_tranche)
        ):
            return True
    return False


def decide(
    envelope: ExecutionEnvelope,
    snapshots: Sequence[MarketSnapshot],
    *,
    now: datetime,
    history: Sequence[ExecutionEvent],
) -> (
    PlannedAction
    | NoAction
    | BreachSignal
    | ExhaustedSignal
    | ExpiredSignal
    | StaleDataSignal
):
    """Return one frozen-contract decision for the current synthetic/live tick."""

    if envelope.status is not EnvelopeStatus.ACTIVE:
        return NoAction(
            reason=NoActionReason.NOT_ACTIVE,
            detail=f"envelope is {envelope.status.value}",
        )
    if now >= envelope.expires_at:
        return ExpiredSignal(disposition=envelope.expiry_disposition)
    phase, _ = _phase_and_close(now)
    if phase is None or phase not in envelope.allowed_session_phases:
        return NoAction(
            reason=NoActionReason.OUT_OF_PHASE,
            detail=f"phase {phase.value if phase else 'none'}",
        )
    invalid = _latest_invalid_reasons(envelope, snapshots)
    if invalid:
        return StaleDataSignal(
            disposition=envelope.stale_data_disposition,
            reasons=invalid,
        )
    remaining = envelope.remaining_quantity or 0
    if remaining <= 0:
        return NoAction(
            reason=NoActionReason.NOTHING_TO_DO,
            detail="remaining quantity is 0",
        )

    child = _child_state(envelope, history)
    if child.violation is not None:
        return BreachSignal(
            rail="max_outstanding_children",
            detail=child.violation,
        )
    if child.blocked:
        return NoAction(
            reason=NoActionReason.MONITORING,
            detail=child.detail,
        )

    start = _tape_start(envelope, history)
    relevant = [
        snap
        for snap in snapshots
        if (start is None or snap.updated_at >= start)
        and (_phase_and_close(snap.updated_at)[0] in envelope.allowed_session_phases)
    ]
    observations = [
        obs
        for snap in relevant
        if (obs := _observation(snap, envelope.symbol)) is not None
    ]
    bars = _coerce_bars(relevant)
    ws = compute_working_stop(
        envelope,
        relevant,
        now=now,
        history=history,
    )
    if len(bars) < MIN_BARS and ws.stop is None:
        return NoAction(
            reason=NoActionReason.INSUFFICIENT_DATA,
            detail=f"{len(bars)} bars < {MIN_BARS} warmup",
        )

    actions = _own_actions(envelope, history)
    latest = snapshots[-1]
    assert latest.last_price is not None and latest.bid is not None
    recent = _recent_volume(
        observations,
        observations[-1].at if observations else now,
    )
    participation_limit = min(
        remaining,
        int(envelope.participation_rate_cap * recent),
    )
    desired: Optional[PlannedAction] = None
    action_clamps = list(ws.clamps)

    if ws.stop is not None and latest.last_price <= ws.stop:
        target = remaining
        size = min(target, participation_limit)
        if size <= 0:
            return NoAction(
                reason=NoActionReason.NO_LIQUIDITY,
                detail="participation cap floors the protective exit to 0",
                working_stop=ws.stop,
                regime=ws.regime,
            )
        if size != target:
            action_clamps.append(
                ClampNote(
                    field="participation_quantity",
                    computed=float(target),
                    clamped_to=float(size),
                )
            )
        desired = PlannedAction(
            kind=ActionKind.SUBMIT,
            limit_price=latest.bid,
            quantity=size,
            regime=ws.regime,
            urgency=_urgency_at(envelope, now),
            working_stop=ws.stop,
            atr=ws.atr,
            tranche=False,
            stop_triggered=True,
            clamps=tuple(action_clamps),
        )
    elif (
        ws.regime in (Regime.FAST_SPIKE, Regime.STEADY_SURGE)
        and not ws.liquidity_stressed
        and not child.working
        and not _tranche_filled(envelope, history)
    ):
        vwap = _anchored_vwap(observations)
        if (
            vwap is not None
            and ws.atr is not None
            and latest.last_price - vwap >= TRANCHE_EXTENSION_ATR * ws.atr
        ):
            target = max(1, math.ceil(remaining * TRANCHE_FRACTION))
            size = min(target, participation_limit)
            if size <= 0:
                return NoAction(
                    reason=NoActionReason.NO_LIQUIDITY,
                    detail="participation cap floors the tranche to 0",
                    working_stop=ws.stop,
                    regime=ws.regime,
                )
            if size != target:
                action_clamps.append(
                    ClampNote(
                        field="participation_quantity",
                        computed=float(target),
                        clamped_to=float(size),
                    )
                )
            desired = PlannedAction(
                kind=ActionKind.SUBMIT,
                limit_price=latest.bid,
                quantity=size,
                regime=ws.regime,
                urgency=_urgency_at(envelope, now),
                working_stop=ws.stop,
                atr=ws.atr,
                tranche=True,
                stop_triggered=False,
                clamps=tuple(action_clamps),
            )

    if desired is None:
        return NoAction(
            reason=NoActionReason.MONITORING,
            working_stop=ws.stop,
            regime=ws.regime,
        )

    last_at = _last_action_at(actions)
    cooldown = timedelta(milliseconds=envelope.cooldown_floor_ms)
    if last_at is not None and now - last_at < cooldown:
        return NoAction(
            reason=NoActionReason.COOLDOWN_WAIT,
            wait_until=last_at + cooldown,
            working_stop=ws.stop,
            regime=ws.regime,
        )
    if child.working:
        desired = PlannedAction(**{**desired.__dict__, "kind": ActionKind.REPRICE})
    if (
        desired.kind is ActionKind.REPRICE
        and _budget_used(actions) >= envelope.cancel_replace_budget
    ):
        return ExhaustedSignal(
            detail=f"cancel/replace budget {envelope.cancel_replace_budget} spent"
        )

    violation = validate_action(envelope, desired, history=history, now=now)
    if violation is not None:
        return BreachSignal(rail=violation.rail, detail=violation.detail)
    return desired
