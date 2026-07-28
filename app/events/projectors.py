"""Pure projectors — reconstruct state from the ``ExecutionEvent`` log.

A *projector* folds an ordered event stream into a read model. Position replay
derives per-symbol state from ``FILL`` events by reusing
``app/position.py:apply_fill`` — the folding formula lives in exactly one place
(Rule 7), whether the fills come from the legacy fill table or the event log.
Envelope replay reconstructs immutable mandate bounds, lifecycle status,
remaining quantity, and supersession linkage from the existing event family.

Everything here is pure: no IO, no async, no clock. Projectors consume an
already-read ``list[ExecutionEvent]`` (the store owns reading), which keeps them
deterministic and trivially unit-testable, and lets the replay verifier
(``app/events/replay.py``) drive them offline.

**Precondition:** events must be supplied in ascending ``sequence`` order (the
store's ``get_execution_events`` guarantees this). The fold is order-dependent;
projectors do not re-sort, so an ordering violation is a caller bug, not
silently masked.

Primary/spawn projection remains deferred; TradingState and quarantine folds
below implement the same "events → read model" shape (see
``docs/SPINE_MIGRATION_PROGRESS.md``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Iterable, Literal

from app.models import (
    SIGNAL_EXPIRY_DETECTORS,
    SIGNAL_QUARANTINE_REASONS,
    ExecutionEvent,
    ExecutionEventType,
    EnvelopeStatus,
    Fill,
    OrderSide,
    OrderStatus,
    Position,
    SignalRecord,
    SignalStatus,
    TradingState,
)
from app.policy import fill_value_reason
from app.position import apply_fill
from app.transitions import ENVELOPE_TRANSITIONS


class ProjectionError(ValueError):
    """A malformed event cannot be projected — fail-fast (Spine v2 §1).

    Raised when a ``FILL`` event is missing a field the fold needs
    (``symbol``/``side``/``quantity``/``price``). A bad event must halt the
    projection rather than silently corrupt the derived position.
    """


@dataclass(frozen=True)
class PositionProjection:
    """Result of projecting position from the event log.

    ``positions`` maps symbol → derived :class:`Position` for **every symbol
    that appears in a FILL event**, including symbols now flat (quantity 0) —
    matching ``StateStore.list_positions`` semantics ("a position for every
    symbol that has fills"), so a fresh replay can be compared to the live
    store field-for-field. ``up_to_sequence`` is the highest event sequence
    folded in (the snapshot/resume boundary).
    """

    positions: dict[str, Position]
    up_to_sequence: int


def _fill_from_event(event: ExecutionEvent) -> Fill:
    """Reconstruct the :class:`Fill` a ``FILL`` event represents.

    ``order_id`` is not needed by the fold (position derivation ignores it), so
    a ``FILL`` event without one still projects; ``symbol``/``side``/
    ``quantity``/``price`` are required and their absence is a
    :class:`ProjectionError`. ``filled_at`` prefers the venue event time
    (``ts_event``), falling back to local ingest time (``ts_init``).

    Intrinsic value validity (finite, whole, strictly-positive quantity; finite,
    strictly-positive price) is enforced via the SAME shared predicate the store
    uses for ``append_fill`` (``fill_value_reason``) — a NaN/Inf/negative value
    would fold into a ``NaN``/garbage position and silently corrupt the derived
    truth, which the fail-fast principle (Spine v2 §1) and this class's contract
    forbid. Keeping the check on the shared predicate means the event-log path
    and the legacy fill path reject the same malformed numbers identically.
    """

    missing = [
        name
        for name, value in (
            ("symbol", event.symbol),
            ("side", event.side),
            ("quantity", event.quantity),
            ("price", event.price),
        )
        if value is None
    ]
    if missing:
        raise ProjectionError(
            f"FILL event sequence={event.sequence} missing required "
            f"field(s): {', '.join(missing)}"
        )
    value_reason = fill_value_reason(event.quantity, event.price)
    if value_reason is not None:
        raise ProjectionError(
            f"FILL event sequence={event.sequence} has invalid values "
            f"({value_reason}): quantity={event.quantity!r} price={event.price!r}"
        )
    return Fill(
        order_id=event.order_id or "",
        symbol=event.symbol,
        side=event.side,
        quantity=event.quantity,
        price=event.price,
        source_fill_id=event.dedupe_key,
        session_id=event.session_id,
        filled_at=event.ts_event or event.ts_init,
    )


def project_symbol_position(events: Iterable[ExecutionEvent], symbol: str) -> Position:
    """Fold one symbol's ``FILL`` events into its :class:`Position` — the
    event-truth position read path (wave 3a-truth).

    The store's ``get_position``/``list_positions`` derive position from the
    append-only event log via this function instead of the legacy fill table,
    making the event log the Rule-7 source of truth (the fill table is a
    compatibility read-model). Events must be in ascending sequence order (the
    store guarantees it); non-FILL and other-symbol events are skipped.
    """

    position = Position(symbol=symbol)
    for event in events:
        if event.event_type is not ExecutionEventType.FILL or event.symbol != symbol:
            continue
        # allow_short: a recorded FILL is a broker-authoritative FACT. If it
        # drives the position negative (a broker overfill, ADR-001) the projector
        # RECORDS the resulting short — it does not raise — so the quarantine
        # detector can surface it. Local malformed input is rejected earlier, at
        # append time (would_go_negative), before any event is recorded.
        position = apply_fill(position, _fill_from_event(event), allow_short=True)
    return position


def quarantined_symbols(events: Iterable[ExecutionEvent]) -> set[str]:
    """Symbols quarantined by a broker-authoritative overfill (ADR-001).

    Explicit ``QUARANTINED`` facts cover order-level overfills that can leave a
    positive position; the legacy negative-position fold remains supported.
    Autonomous spawns are blocked and manual review is required.

    **Latched, not live.** A symbol is quarantined once its ``FILL``-event fold
    reaches a negative running quantity *at any point* — NOT merely when the
    *current* projected quantity is negative. A later covering BUY (from a
    pre-existing order, a reconciliation-inferred cover, or manual review) returns
    the projection to ``>= 0`` but MUST NOT lift the quarantine: for beta,
    ADR-001 defines a permanent, append-only, cross-session latch with no clear or
    release event. Covering the short therefore cannot resume autonomous trading
    from the unreconciled database. Deriving from the fold *history* (a crossing
    that happened stays in the sequence) makes that permanent latch durable and
    replay-stable without a separate mutable flag.

    Operator visibility and alerting may surface the latch for remediation, but
    they do not clear it. Any release design is separate, explicitly approved
    future work rather than part of the beta projection model.

    Pure over the log (reuses ``apply_fill`` — the fold formula lives in one
    place), so it is replay-stable and identical across both stores. Events must
    be in ascending ``sequence`` order (the store guarantees it).
    """

    events = list(events)
    symbols = {
        e.symbol
        for e in events
        if e.event_type is ExecutionEventType.FILL and e.symbol is not None
    }
    quarantined = {
        event.symbol
        for event in events
        if event.event_type is ExecutionEventType.QUARANTINED
        and event.symbol is not None
    }
    for symbol in symbols:
        position = Position(symbol=symbol)
        for event in events:
            if (
                event.event_type is not ExecutionEventType.FILL
                or event.symbol != symbol
            ):
                continue
            position = apply_fill(position, _fill_from_event(event), allow_short=True)
            if position.quantity < 0:
                quarantined.add(symbol)  # latched — the crossing is durable
                break
    return quarantined


# Order-lifecycle ExecutionEvent types that resolve/set a TIMEOUT_QUARANTINE.
# A FILL is deliberately NOT here: a fill never resolves a quarantine (the
# quarantine is resolved to SUBMITTED first, then the fill ingests — §C4), so a
# stray fill leaves the order quarantined (the safe latch).
_ORDER_LIFECYCLE_EVENT_TYPES = frozenset(
    {
        ExecutionEventType.TIMEOUT_QUARANTINE,
        ExecutionEventType.SUBMITTED,
        ExecutionEventType.REJECTED,
        ExecutionEventType.CANCELED,
        ExecutionEventType.FILLED,
    }
)


def timeout_quarantined_order_ids(events: Iterable[ExecutionEvent]) -> set[str]:
    """Order ids currently in ``TIMEOUT_QUARANTINE`` (ADR-002 / wave 3c): those
    whose LATEST order-lifecycle ``ExecutionEvent`` is ``TIMEOUT_QUARANTINE`` —
    i.e. quarantined by an ambiguous submit and not yet resolved by a later
    ``SUBMITTED``/``REJECTED``/``CANCELED`` event.

    Derived purely from the append-only log (events in ascending ``sequence``
    order, latest wins), so it is replay-stable and event-truth: the order-row
    ``status`` column is a co-written read-model reconstructable from this set
    (docs/SPINE_WAVE3C_PLAN.md C5). Since WO-0007a the ROUTINE order lifecycle
    also emits these types (a normal ``SUBMITTING → SUBMITTED`` now writes a
    ``SUBMITTED`` event, fills write ``FILLED``, etc.), but the "latest wins"
    fold still yields the correct set: a normally-submitted order's latest
    lifecycle event is ``SUBMITTED``/``FILLED``/``CANCELED`` (never
    ``TIMEOUT_QUARANTINE``), so it is excluded; and a quarantined order is never
    driven back through the routine emitter (``execution_event_for_routine_transition``
    refuses a shared-format key for a ``TIMEOUT_QUARANTINE`` order, and no
    routine call site transitions a quarantined order), so its latest stays
    ``TIMEOUT_QUARANTINE`` until a wave-3c resolve event supersedes it.
    (Regression coverage: tests/test_wo0007a_quarantine_consumer_unaffected.py.)
    """

    latest: dict[str, ExecutionEventType] = {}
    for event in events:
        if (
            event.event_type in _ORDER_LIFECYCLE_EVENT_TYPES
            and event.order_id is not None
        ):
            latest[event.order_id] = event.event_type
    return {
        order_id
        for order_id, event_type in latest.items()
        if event_type is ExecutionEventType.TIMEOUT_QUARANTINE
    }


# ---- order-status projector (WO-0007b) ----------------------------------- #
#
# The read model for the sole remaining legacy_truth flow ("Atomic submit
# claim"). `status` is a LATEST-lifecycle-event-wins fold (generalizing
# timeout_quarantined_order_ids above), NOT max-status-reached: the CREATED<->
# SUBMITTING cycle means a released order must be able to REGRESS to CREATED, and
# a live CANCEL_PENDING must be representable — both require the events WO-0007b
# Stage A added (SUBMIT_RELEASED / CANCEL_PENDING). A max fold would strand a
# released order at SUBMITTING (the claim gate needs CREATED). `filled_quantity`
# is a separate Σ over the order's FILL events (INV-1), capped at the order's
# quantity to match the store's overfill-capped column (policy.filled_quantity_reason).
_LIFECYCLE_EVENT_TO_STATUS: dict[ExecutionEventType, OrderStatus] = {
    ExecutionEventType.SUBMIT_PENDING: OrderStatus.SUBMITTING,
    ExecutionEventType.SUBMIT_RELEASED: OrderStatus.CREATED,
    ExecutionEventType.SUBMITTED: OrderStatus.SUBMITTED,
    ExecutionEventType.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
    ExecutionEventType.CANCEL_PENDING: OrderStatus.CANCEL_PENDING,
    ExecutionEventType.FILLED: OrderStatus.FILLED,
    ExecutionEventType.CANCELED: OrderStatus.CANCELED,
    ExecutionEventType.REJECTED: OrderStatus.REJECTED,
    ExecutionEventType.TIMEOUT_QUARANTINE: OrderStatus.TIMEOUT_QUARANTINE,
}

# Public view of the status-lifecycle event types (the keys of the fold map above).
# An order is "evented for status" iff it carries >=1 event of one of these types.
# A FILL is deliberately EXCLUDED — it is a position fact, never a status-lifecycle
# event (see project_order_status). The stores' init backfill uses this to decide
# whether an order predates eventing (zero lifecycle events) and needs a synthetic
# reconstruction, keeping that decision single-sourced with the fold's vocabulary.
ORDER_STATUS_EVENT_TYPES: frozenset[ExecutionEventType] = frozenset(
    _LIFECYCLE_EVENT_TO_STATUS
)


@dataclass(frozen=True)
class OrderStatusProjection:
    """The order-status read model derived from the event log for one order."""

    order_id: str
    status: OrderStatus
    filled_quantity: int


def project_order_status(
    events: Iterable[ExecutionEvent],
    order_id: str,
    quantity: int | None = None,
) -> OrderStatusProjection:
    """Fold one order's lifecycle + FILL events into its status + filled_quantity.

    ``status`` = the OrderStatus of the LATEST order-status lifecycle event for
    ``order_id`` (empty stream -> ``CREATED``, the pre-lifecycle default). A ``FILL``
    is a position fact, never a status-lifecycle event, so it does not move status.

    ``filled_quantity`` = Σ of this order's ``FILL`` event quantities, capped at
    ``quantity`` when supplied (the store passes ``order.quantity`` so a
    broker-overfill fold matches the column, which ``filled_quantity_reason`` caps;
    ``None`` yields the raw sum). Pure; events must be in ascending sequence order.
    """

    status = OrderStatus.CREATED
    filled = 0
    for event in events:
        if event.order_id != order_id:
            continue
        if event.event_type is ExecutionEventType.FILL:
            filled += event.quantity or 0
            continue
        mapped = _LIFECYCLE_EVENT_TO_STATUS.get(event.event_type)
        if mapped is not None:
            status = mapped
    if quantity is not None:
        filled = min(filled, quantity)
    return OrderStatusProjection(
        order_id=order_id, status=status, filled_quantity=filled
    )


# §8 severity ordering for composing independent TradingState drivers (wave 4f / R2):
# the more restrictive state wins. Halted (kill — a true all-stop) dominates Reducing
# (reduce-only — stream degradation / pending reconciliation), which dominates Active.
_TRADING_STATE_RANK: dict[TradingState, int] = {
    TradingState.ACTIVE: 0,
    TradingState.REDUCING: 1,
    TradingState.HALTED: 2,
}


def compose_trading_state(*states: TradingState) -> TradingState:
    """The effective ``TradingState`` from N independent drivers: the most
    restrictive (``Halted > Reducing > Active``, §8). This is how the wave-3d
    control driver (kill/pause booleans) and the wave-4f reconcile driver (startup /
    reconnect / parity signals) compose WITHOUT either clobbering the other — kill
    still dominates a reconcile-driven Reducing, and a control change can't lift a
    Reducing that pending reconciliation still requires (R2)."""

    return max(
        states, key=lambda s: _TRADING_STATE_RANK[s], default=TradingState.ACTIVE
    )


def _driver_trading_state(
    events: Iterable[ExecutionEvent], session_id: str, *, reconcile: bool
) -> TradingState:
    """Latest ``to`` among a session's ``TRADING_STATE_CHANGED`` events for ONE
    driver — the ``reconcile`` driver (``payload.driver == "reconcile"``) or the
    ``control`` driver (any other value, incl. legacy events with no ``driver``
    stamp, which are all control decisions). Default ``ACTIVE``. Latest-wins per
    driver, so each driver's own history folds independently before composition."""

    state = TradingState.ACTIVE
    for event in events:
        if (
            event.event_type is ExecutionEventType.TRADING_STATE_CHANGED
            and event.session_id == session_id
        ):
            is_reconcile = (event.payload or {}).get("driver") == "reconcile"
            if is_reconcile == reconcile:
                state = TradingState(event.payload["to"])
    return state


def control_trading_state(
    events: Iterable[ExecutionEvent], session_id: str
) -> TradingState:
    """The session's CONTROL-driven TradingState (kill/pause booleans, §8 / wave 3d).
    Legacy ``TRADING_STATE_CHANGED`` events (no ``driver`` stamp) fold here."""

    return _driver_trading_state(events, session_id, reconcile=False)


def reconcile_trading_state(
    events: Iterable[ExecutionEvent], session_id: str
) -> TradingState:
    """The session's RECONCILE-driven TradingState (wave 4f / R2): startup /
    reconnect / parity signals drive this to ``Reducing`` (pending reconciliation)
    or ``Active`` (parity restored) WITHOUT touching the kill/pause booleans."""

    return _driver_trading_state(events, session_id, reconcile=True)


def current_trading_state(
    events: Iterable[ExecutionEvent], session_id: str
) -> TradingState:
    """The session's EFFECTIVE ``TradingState`` (§8): the composition of its two
    independent drivers — control (kill/pause, wave 3d) and reconcile (wave 4f) —
    via :func:`compose_trading_state` (``Halted > Reducing > Active``).

    Derived purely from the append-only log (events in ascending ``sequence`` order,
    latest-wins PER driver), so it is replay-stable and event-truth — the
    ``SessionRecord.trading_state`` column is a co-written read-model reconstructable
    from this fold. With no reconcile events (the wave-3d world) the reconcile driver
    is ``ACTIVE`` and the composition reduces to the control state, so the wave-3d
    behavior is preserved exactly. The kill/pause booleans remain co-written
    ``sessions``-table columns (not purely event-reconstructable — no event fires
    when a boolean toggle leaves the derived state unchanged). Session-scoped."""

    return compose_trading_state(
        control_trading_state(events, session_id),
        reconcile_trading_state(events, session_id),
    )


def active_emergency_reduce_overrides(
    events: Iterable[ExecutionEvent], session_id: str
) -> set[str]:
    """Symbols in ``session_id`` with an ACTIVE emergency-reduce override grant
    (ADR-003 / wave 3e): those whose LATEST override event is an
    ``EMERGENCY_REDUCE_OVERRIDE`` grant, not yet consumed by a matching
    ``EMERGENCY_REDUCE_OVERRIDE_RESOLVED``.

    The grant is the audited operator authority that lets a SINGLE reduce-only
    exit through the claim gate while the session is ``Halted`` — the global
    ``TradingState`` stays ``Halted`` throughout (ADR-003 "scoped Reducing" is
    NOT a global state flip; §8 kill dominates). Scoped to ``{session, symbol}``;
    consumed on resolution so a later flatten under ``Halted`` is denied again.
    Derived purely from the append-only log (ascending ``sequence``, latest wins),
    so it is replay-stable and event-truth. Session-scoped.
    """

    active: dict[str, bool] = {}
    for event in events:
        if event.session_id != session_id or event.symbol is None:
            continue
        if event.event_type is ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE:
            active[event.symbol] = True
        elif event.event_type is ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE_RESOLVED:
            active[event.symbol] = False
    return {symbol for symbol, is_active in active.items() if is_active}


# Every event in the current envelope namespace is classified explicitly. This
# intentionally stays a literal set (rather than deriving from the enum): a new
# ``envelope_*`` event must make the coverage pin fail until its replay semantics
# are consciously assigned.
ENVELOPE_EVENT_TYPES: frozenset[ExecutionEventType] = frozenset(
    {
        ExecutionEventType.ENVELOPE_CREATED,
        ExecutionEventType.ENVELOPE_APPROVED,
        ExecutionEventType.ENVELOPE_ACTIVATED,
        ExecutionEventType.ENVELOPE_ACTION,
        ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
        ExecutionEventType.ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT,
        ExecutionEventType.ENVELOPE_COMPLETED,
        ExecutionEventType.ENVELOPE_BREACHED,
        ExecutionEventType.ENVELOPE_EXHAUSTED,
        ExecutionEventType.ENVELOPE_EXPIRED,
        ExecutionEventType.ENVELOPE_FROZEN,
        ExecutionEventType.ENVELOPE_RESUMED,
        ExecutionEventType.ENVELOPE_SUPERSEDED,
        ExecutionEventType.ENVELOPE_CANCELLED,
        ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE,
    }
)

_ENVELOPE_STATUS_EVENTS: dict[ExecutionEventType, EnvelopeStatus] = {
    ExecutionEventType.ENVELOPE_APPROVED: EnvelopeStatus.APPROVED,
    ExecutionEventType.ENVELOPE_ACTIVATED: EnvelopeStatus.ACTIVE,
    ExecutionEventType.ENVELOPE_COMPLETED: EnvelopeStatus.COMPLETED,
    ExecutionEventType.ENVELOPE_BREACHED: EnvelopeStatus.BREACHED,
    ExecutionEventType.ENVELOPE_EXHAUSTED: EnvelopeStatus.EXHAUSTED,
    ExecutionEventType.ENVELOPE_EXPIRED: EnvelopeStatus.EXPIRED,
    ExecutionEventType.ENVELOPE_FROZEN: EnvelopeStatus.FROZEN,
    ExecutionEventType.ENVELOPE_RESUMED: EnvelopeStatus.ACTIVE,
    ExecutionEventType.ENVELOPE_SUPERSEDED: EnvelopeStatus.SUPERSEDED,
    ExecutionEventType.ENVELOPE_CANCELLED: EnvelopeStatus.CANCELLED,
}

_ENVELOPE_NO_STATE_EVENTS = frozenset(
    {
        ExecutionEventType.ENVELOPE_ACTION,
        ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE,
    }
)

_ENVELOPE_BOUND_KEYS = (
    "qty_ceiling",
    "floor_price",
    "trail_distance_min",
    "trail_distance_max",
    "participation_rate_cap",
    "aggressiveness",
    "cooldown_floor_ms",
    "cancel_replace_budget",
    "max_outstanding_children",
    "expires_at",
    "allowed_session_phases",
    "expiry_disposition",
    "stale_data_disposition",
    "supersedes_id",
)


def _freeze_projection_value(value: object) -> object:
    """Make nested payload values immutable and equality-stable."""

    if isinstance(value, dict):
        return tuple(
            (key, _freeze_projection_value(item)) for key, item in sorted(value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_projection_value(item) for item in value)
    return value


@dataclass(frozen=True)
class EnvelopeProjection:
    """Replay-derived state for one execution envelope.

    The immutable mandate bounds come from ``ENVELOPE_CREATED``'s complete
    snapshot. Mutable state is limited to lifecycle status, remaining quantity,
    and supersession linkage. ``folded_event_types`` records every envelope
    decision/fact consumed, including action and divergence events that do not
    themselves mutate the read model.
    """

    envelope_id: str
    sell_intent_id: str
    symbol: str
    session_id: str | None
    status: EnvelopeStatus
    qty_ceiling: int
    remaining_quantity: int
    supersedes_id: str | None
    superseded_by_id: str | None
    bound_snapshot: tuple[tuple[str, object], ...]
    folded_event_types: tuple[ExecutionEventType, ...]
    up_to_sequence: int


def _created_envelope_projection(event: ExecutionEvent) -> EnvelopeProjection:
    if event.envelope_id is None:
        raise ProjectionError("ENVELOPE_CREATED is missing envelope_id")
    if event.symbol is None:
        raise ProjectionError(
            f"ENVELOPE_CREATED for {event.envelope_id!r} is missing symbol"
        )
    if event.side is not OrderSide.SELL:
        raise ProjectionError(
            f"ENVELOPE_CREATED for {event.envelope_id!r} must have SELL side"
        )
    if event.correlation_id is None:
        raise ProjectionError(
            f"ENVELOPE_CREATED for {event.envelope_id!r} is missing sell-intent correlation"
        )
    missing = [key for key in _ENVELOPE_BOUND_KEYS if key not in event.payload]
    if missing:
        raise ProjectionError(
            f"ENVELOPE_CREATED for {event.envelope_id!r} missing bound field(s): "
            f"{', '.join(missing)}"
        )
    if event.payload.get("sell_intent_id") != event.correlation_id:
        raise ProjectionError(
            f"ENVELOPE_CREATED for {event.envelope_id!r} has conflicting sell-intent identity"
        )
    qty_ceiling = event.payload["qty_ceiling"]
    if type(qty_ceiling) is not int or qty_ceiling <= 0:
        raise ProjectionError(
            f"ENVELOPE_CREATED for {event.envelope_id!r} has invalid qty_ceiling "
            f"{qty_ceiling!r}"
        )
    supersedes_id = event.payload["supersedes_id"]
    if supersedes_id is not None and not isinstance(supersedes_id, str):
        raise ProjectionError(
            f"ENVELOPE_CREATED for {event.envelope_id!r} has invalid supersedes_id"
        )
    bounds = tuple(
        (key, _freeze_projection_value(event.payload[key]))
        for key in _ENVELOPE_BOUND_KEYS
    )
    return EnvelopeProjection(
        envelope_id=event.envelope_id,
        sell_intent_id=event.correlation_id,
        symbol=event.symbol,
        session_id=event.session_id,
        status=EnvelopeStatus.PENDING,
        qty_ceiling=qty_ceiling,
        remaining_quantity=qty_ceiling,
        supersedes_id=supersedes_id,
        superseded_by_id=None,
        bound_snapshot=bounds,
        folded_event_types=(event.event_type,),
        up_to_sequence=event.sequence,
    )


def _validate_envelope_event_identity(
    projection: EnvelopeProjection, event: ExecutionEvent
) -> None:
    if (
        event.envelope_id != projection.envelope_id
        or event.symbol != projection.symbol
        or event.side is not OrderSide.SELL
        or event.session_id != projection.session_id
        or event.correlation_id != projection.sell_intent_id
    ):
        raise ProjectionError(
            f"envelope event sequence={event.sequence} has foreign or malformed identity "
            f"for {projection.envelope_id!r}"
        )


def _touch_envelope_projection(
    projection: EnvelopeProjection, event: ExecutionEvent
) -> EnvelopeProjection:
    return replace(
        projection,
        folded_event_types=(*projection.folded_event_types, event.event_type),
        up_to_sequence=max(projection.up_to_sequence, event.sequence),
    )


def _apply_envelope_debit(
    projection: EnvelopeProjection, event: ExecutionEvent
) -> EnvelopeProjection:
    quantity = event.quantity
    before = event.payload.get("remaining_before")
    after = event.payload.get("remaining_after")
    if type(quantity) is not int or quantity <= 0:
        raise ProjectionError(
            f"envelope debit sequence={event.sequence} has invalid quantity {quantity!r}"
        )
    if type(before) is not int or before != projection.remaining_quantity:
        raise ProjectionError(
            f"envelope debit sequence={event.sequence} remaining_before {before!r} "
            f"does not match projected {projection.remaining_quantity}"
        )
    expected_after = max(0, before - quantity)
    if type(after) is not int or after != expected_after:
        raise ProjectionError(
            f"envelope debit sequence={event.sequence} remaining_after {after!r} "
            f"does not match expected {expected_after}"
        )
    return replace(projection, remaining_quantity=after)


def project_envelopes(
    events: Iterable[ExecutionEvent],
) -> dict[str, EnvelopeProjection]:
    """Fold the complete current envelope event family into read models.

    Canonical envelope-attributed ``FILL`` events and repair-only
    ``ENVELOPE_FILL_ATTRIBUTED`` markers both debit remaining quantity exactly
    once using their persisted before/after chain. Repair checkpoints are global
    cursor metadata, so they are explicitly classified but do not create or
    mutate a per-envelope projection. Any malformed identity, missing creation
    snapshot, broken debit chain, or contradictory lifecycle edge fails closed.
    """

    projected: dict[str, EnvelopeProjection] = {}
    for event in events:
        if (
            event.event_type
            is ExecutionEventType.ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT
        ):
            continue
        is_envelope_fill = (
            event.event_type is ExecutionEventType.FILL
            and event.envelope_id is not None
        )
        if event.event_type not in ENVELOPE_EVENT_TYPES and not is_envelope_fill:
            continue
        if event.event_type is ExecutionEventType.ENVELOPE_CREATED:
            if event.envelope_id is not None and event.envelope_id in projected:
                raise ProjectionError(
                    f"duplicate ENVELOPE_CREATED for {event.envelope_id!r}"
                )
            created = _created_envelope_projection(event)
            projected[created.envelope_id] = created
            continue
        if event.envelope_id is None or event.envelope_id not in projected:
            raise ProjectionError(
                f"envelope event sequence={event.sequence} appears before ENVELOPE_CREATED"
            )

        current = projected[event.envelope_id]
        _validate_envelope_event_identity(current, event)
        if event.event_type in {
            ExecutionEventType.FILL,
            ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
        }:
            current = _apply_envelope_debit(current, event)
        elif event.event_type in _ENVELOPE_STATUS_EVENTS:
            expected = _ENVELOPE_STATUS_EVENTS[event.event_type]
            if event.payload.get("from") != current.status.value:
                raise ProjectionError(
                    f"envelope transition sequence={event.sequence} from "
                    f"{event.payload.get('from')!r} does not match projected "
                    f"{current.status.value!r}"
                )
            if event.payload.get("to") != expected.value:
                raise ProjectionError(
                    f"envelope transition sequence={event.sequence} to "
                    f"{event.payload.get('to')!r} does not match {expected.value!r}"
                )
            if expected not in ENVELOPE_TRANSITIONS[current.status]:
                raise ProjectionError(
                    f"illegal envelope transition sequence={event.sequence}: "
                    f"{current.status.value!r} -> {expected.value!r}"
                )
            superseded_by_id = current.superseded_by_id
            if event.event_type is ExecutionEventType.ENVELOPE_SUPERSEDED:
                superseded_by_id = event.payload.get("superseded_by_id")
                if not isinstance(superseded_by_id, str) or not superseded_by_id:
                    raise ProjectionError(
                        f"ENVELOPE_SUPERSEDED sequence={event.sequence} is missing "
                        "superseded_by_id"
                    )
            current = replace(
                current,
                status=expected,
                superseded_by_id=superseded_by_id,
            )
        elif event.event_type not in _ENVELOPE_NO_STATE_EVENTS:
            raise ProjectionError(
                f"unclassified envelope event type {event.event_type.value!r}"
            )
        projected[event.envelope_id] = _touch_envelope_projection(current, event)
    return projected


class PositionProjector:
    """Fold ``FILL`` events into per-symbol positions (pure)."""

    @classmethod
    def project(cls, events: Iterable[ExecutionEvent]) -> PositionProjection:
        """Project from scratch (empty book, sequence 0)."""

        return cls._apply({}, 0, events)

    @classmethod
    def resume(
        cls, snapshot: PositionProjection, events: Iterable[ExecutionEvent]
    ) -> PositionProjection:
        """Continue a projection from ``snapshot``, applying only events with
        ``sequence > snapshot.up_to_sequence``.

        This is the bounded snapshot+replay recovery path (§11): a persisted
        projection snapshot plus the event tail reproduces the full replay
        without re-folding history. ``project(events) ==
        resume(project(events[:k]), events)`` for any split ``k`` — verified in
        ``app/events/replay.py``.
        """

        # Copy the snapshot's positions so the caller's projection is not
        # mutated (Position values are immutable-by-convention read models).
        return cls._apply(
            dict(snapshot.positions),
            snapshot.up_to_sequence,
            (e for e in events if e.sequence > snapshot.up_to_sequence),
        )

    @staticmethod
    def _apply(
        positions: dict[str, Position],
        up_to_sequence: int,
        events: Iterable[ExecutionEvent],
    ) -> PositionProjection:
        for event in events:
            if event.sequence > up_to_sequence:
                up_to_sequence = event.sequence
            if event.event_type is not ExecutionEventType.FILL:
                # Phase 2 projects only position; other lifecycle event types
                # advance the sequence boundary but do not affect the book.
                continue
            fill = _fill_from_event(event)
            current = positions.get(fill.symbol) or Position(symbol=fill.symbol)
            # allow_short (wave 3b / ADR-001): a recorded FILL is a broker fact.
            # An overfill that crosses flat is RECORDED as a negative (quarantine)
            # position, not rejected — see project_symbol_position + the
            # quarantine detector. Local malformed input is rejected at append.
            positions[fill.symbol] = apply_fill(current, fill, allow_short=True)
        return PositionProjection(positions=positions, up_to_sequence=up_to_sequence)


# --------------------------------------------------------------------------- #
# Signal Seat read-model fold (ADR-009 / WO-0134).
#
# Creation events carry a full record snapshot. Later R5/R7 transition events
# carry only identity + changed terminal/correlation fields. Duplicate conflicts
# are audit-only and structurally excluded from this fold.
# --------------------------------------------------------------------------- #

_SIGNAL_CREATION_EVENT_TYPES = frozenset(
    {
        ExecutionEventType.SIGNAL_RECEIVED,
        ExecutionEventType.SIGNAL_QUARANTINED,
        ExecutionEventType.SIGNAL_EXPIRED,
    }
)

_SIGNAL_TRANSITION_STATUS: dict[ExecutionEventType, SignalStatus] = {
    ExecutionEventType.SIGNAL_QUARANTINED: SignalStatus.QUARANTINED,
    ExecutionEventType.SIGNAL_EXPIRED: SignalStatus.EXPIRED,
    ExecutionEventType.SIGNAL_REJECTED: SignalStatus.REJECTED,
    ExecutionEventType.SIGNAL_APPROVED: SignalStatus.APPROVED,
}

_SIGNAL_TRANSITION_TIMESTAMP_FIELD: dict[ExecutionEventType, str] = {
    ExecutionEventType.SIGNAL_QUARANTINED: "quarantined_at",
    ExecutionEventType.SIGNAL_EXPIRED: "expired_at",
    ExecutionEventType.SIGNAL_REJECTED: "rejected_at",
    ExecutionEventType.SIGNAL_APPROVED: "approved_at",
}

_SIGNAL_TRANSITION_DIRECT_FIELDS = (
    "converted_kind",
    "converted_id",
    "quarantine_reason",
)

_SIGNAL_TRANSITION_ALIASES: dict[ExecutionEventType, dict[str, str]] = {
    ExecutionEventType.SIGNAL_APPROVED: {"actor": "approved_by"},
}


def project_signal_records(
    events: Iterable[ExecutionEvent],
) -> dict[tuple[str, str], SignalRecord]:
    """Fold ordered ``SIGNAL_*`` events by ``(producer_id, signal_id)``."""

    records: dict[tuple[str, str], SignalRecord] = {}
    for event in events:
        event_type = event.event_type
        payload = event.payload or {}
        snapshot = payload.get("record")
        if event_type in _SIGNAL_CREATION_EVENT_TYPES and isinstance(snapshot, dict):
            record = SignalRecord.model_validate(snapshot)
            records[(record.producer_id, record.signal_id)] = record
            continue
        if event_type is ExecutionEventType.SIGNAL_RECEIVED:
            raise ProjectionError(
                f"SIGNAL_RECEIVED creation event sequence={event.sequence} is "
                "missing a record snapshot (payload['record'])"
            )
        if event_type is ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT:
            continue

        mapped_status = _SIGNAL_TRANSITION_STATUS.get(event_type)
        if mapped_status is None:
            continue
        producer_id = payload.get("producer_id")
        signal_id = payload.get("signal_id")
        if not isinstance(producer_id, str) or not isinstance(signal_id, str):
            raise ProjectionError(
                f"{event_type.value} event sequence={event.sequence} is missing "
                "required record identity (producer_id/signal_id)"
            )
        existing = records.get((producer_id, signal_id))
        if existing is None:
            continue
        record_id = payload.get("record_id")
        if not isinstance(record_id, str) or record_id != existing.id:
            raise ProjectionError(
                f"{event_type.value} event sequence={event.sequence} has a "
                "missing or mismatched record_id"
            )
        if existing.status is not SignalStatus.RECEIVED:
            continue

        transition_ts = event.ts_event or event.ts_init
        update: dict[str, object] = {
            "status": mapped_status,
            "updated_at": transition_ts,
        }
        timestamp_field = _SIGNAL_TRANSITION_TIMESTAMP_FIELD.get(event_type)
        if timestamp_field is not None:
            update[timestamp_field] = transition_ts
        for field_name in _SIGNAL_TRANSITION_DIRECT_FIELDS:
            if field_name in payload:
                update[field_name] = payload[field_name]
        for source_key, destination_field in _SIGNAL_TRANSITION_ALIASES.get(
            event_type, {}
        ).items():
            if source_key in payload:
                update[destination_field] = payload[source_key]
        records[(producer_id, signal_id)] = existing.model_copy(update=update)
    return records


# --------------------------------------------------------------------------- #
# Signal Seat producer-rail fold (ADR-009 / WO-0104a).
#
# Only the budget/quarantine columns are event-derived. The paced-arrival
# bucket is primary durable state because authenticated replays consume tokens
# without necessarily appending an event, so it deliberately does not appear in
# this projection.
# --------------------------------------------------------------------------- #

_PRODUCER_RAIL_SIGNAL_EVENT_TYPES = frozenset(
    {
        ExecutionEventType.SIGNAL_RECEIVED,
        ExecutionEventType.SIGNAL_QUARANTINED,
        ExecutionEventType.SIGNAL_EXPIRED,
        ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
        ExecutionEventType.SIGNAL_REJECTED,
        ExecutionEventType.SIGNAL_APPROVED,
    }
)

# WO-0140 D-R R-5: read-structural. The fold judges logged values against
# structural bounds only; the ratified caps bind at write time (builders and
# validate_producer_rate_inputs). Vocabulary sets ARE log truth and stay.
_SQLITE_MAX_SIGNED_INT = 2**63 - 1


_PRODUCER_QUARANTINE_COMMON_FIELDS = frozenset(
    {
        "producer_id",
        "breach_trigger",
        "epoch_start",
        "epoch_sequence",
    }
)

_PRODUCER_RELEASE_FIELDS = frozenset(
    {
        "producer_id",
        "actor",
        "rejected_count",
        "epoch_start",
        "released_at",
    }
)


@dataclass(frozen=True)
class ProducerRailProjection:
    """Replay-derived budget and quarantine state for one signal producer.

    ``cycle_budget_*`` and ``quarantine_*`` are reconstructed from the
    append-only event log. The paced-arrival token bucket is intentionally
    absent: requests can debit it without appending an event, so replay has no
    independent evidence from which to rebuild those primary-durable columns.
    """

    producer_id: str
    cycle_budget_limit: int | None = None
    cycle_budget_consumed: int = 0
    quarantine_epoch_open: bool = False
    quarantine_epoch_sequence: int = 0
    quarantine_epoch_started_at: datetime | None = None
    quarantine_breach_trigger: Literal["budget_exhausted", "rate_breach"] | None = None


def _producer_id_from_event(event: ExecutionEvent) -> str:
    """Read and cross-check the producer identity carried by a rail event."""

    payload = event.payload
    direct = payload.get("producer_id")
    if direct is not None and not isinstance(direct, str):
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has invalid "
            "producer_id"
        )

    snapshot = payload.get("record")
    snapshot_producer: object = None
    if isinstance(snapshot, dict):
        snapshot_producer = snapshot.get("producer_id")
        if snapshot_producer is not None and not isinstance(snapshot_producer, str):
            raise ProjectionError(
                f"{event.event_type.value} event sequence={event.sequence} has "
                "invalid record producer_id"
            )
    if (
        isinstance(direct, str)
        and isinstance(snapshot_producer, str)
        and direct != snapshot_producer
    ):
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has "
            "conflicting producer identity"
        )

    producer_id = direct if isinstance(direct, str) else snapshot_producer
    if not isinstance(producer_id, str):
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} is missing "
            "required producer_id"
        )
    return producer_id


def _required_str(
    payload: dict[str, object],
    field_name: str,
    *,
    event: ExecutionEvent,
) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has invalid "
            f"{field_name}"
        )
    return value


def _required_int(
    payload: dict[str, object],
    field_name: str,
    *,
    event: ExecutionEvent,
    minimum: int,
    maximum: int,
) -> int:
    value = payload.get(field_name)
    if type(value) is not int or not minimum <= value <= maximum:
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has invalid "
            f"{field_name}"
        )
    return value


def _required_aware_datetime(
    payload: dict[str, object],
    field_name: str,
    *,
    event: ExecutionEvent,
) -> datetime:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has invalid "
            f"{field_name}"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has invalid "
            f"{field_name}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has naive "
            f"{field_name}"
        )
    return parsed


def _require_exact_payload_fields(
    event: ExecutionEvent, expected: frozenset[str]
) -> None:
    actual = frozenset(event.payload)
    if actual != expected:
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has "
            f"unratified payload fields: expected={sorted(expected)!r} "
            f"actual={sorted(actual)!r}"
        )


def _is_attributable_signal_event(event: ExecutionEvent) -> bool:
    payload = event.payload
    quarantine_reasons, expiry_detectors = (
        SIGNAL_QUARANTINE_REASONS,
        SIGNAL_EXPIRY_DETECTORS,
    )
    if event.event_type is ExecutionEventType.SIGNAL_QUARANTINED:
        reason = _required_str(payload, "quarantine_reason", event=event)
        if reason == "producer_sweep":
            return False
        if reason not in quarantine_reasons:
            raise ProjectionError(
                f"SIGNAL_QUARANTINED event sequence={event.sequence} has "
                f"unrecognized quarantine_reason {reason!r}"
            )
        return True
    if event.event_type is ExecutionEventType.SIGNAL_EXPIRED:
        detected_by = _required_str(payload, "detected_by", event=event)
        if detected_by not in expiry_detectors:
            raise ProjectionError(
                f"SIGNAL_EXPIRED event sequence={event.sequence} has "
                f"unrecognized detected_by {detected_by!r}"
            )
        return detected_by == "ingest"
    return event.event_type is ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT


def _apply_attributable_signal_event(
    current: ProducerRailProjection, event: ExecutionEvent
) -> ProducerRailProjection:
    if current.quarantine_epoch_open:
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} attempts a "
            "budget debit while the producer quarantine epoch is open"
        )

    limit = _required_int(
        event.payload,
        "cycle_budget_limit",
        event=event,
        minimum=1,
        maximum=_SQLITE_MAX_SIGNED_INT,
    )
    pinned_limit = current.cycle_budget_limit
    if pinned_limit is None:
        pinned_limit = limit
    elif limit != pinned_limit:
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} has "
            f"cycle_budget_limit={limit}, expected pinned value {pinned_limit}"
        )
    if current.cycle_budget_consumed >= pinned_limit:
        raise ProjectionError(
            f"{event.event_type.value} event sequence={event.sequence} exceeds "
            "the projected cycle budget"
        )
    return replace(
        current,
        cycle_budget_limit=pinned_limit,
        cycle_budget_consumed=current.cycle_budget_consumed + 1,
    )


def _apply_producer_quarantined(
    current: ProducerRailProjection, event: ExecutionEvent
) -> ProducerRailProjection:
    payload = event.payload
    trigger = payload.get("breach_trigger")
    if trigger == "budget_exhausted":
        expected_fields = _PRODUCER_QUARANTINE_COMMON_FIELDS | {
            "cycle_budget_consumed",
            "cycle_budget_limit",
        }
    elif trigger == "rate_breach":
        expected_fields = _PRODUCER_QUARANTINE_COMMON_FIELDS | {"bucket_capacity"}
    else:
        raise ProjectionError(
            f"PRODUCER_QUARANTINED event sequence={event.sequence} has invalid "
            "breach_trigger"
        )
    _require_exact_payload_fields(event, frozenset(expected_fields))

    if current.quarantine_epoch_open:
        raise ProjectionError(
            f"PRODUCER_QUARANTINED event sequence={event.sequence} attempts to "
            "open an already-open quarantine epoch"
        )
    epoch_sequence = _required_int(
        payload,
        "epoch_sequence",
        event=event,
        minimum=1,
        maximum=_SQLITE_MAX_SIGNED_INT,
    )
    expected_sequence = current.quarantine_epoch_sequence + 1
    if epoch_sequence != expected_sequence:
        raise ProjectionError(
            f"PRODUCER_QUARANTINED event sequence={event.sequence} has "
            f"epoch_sequence={epoch_sequence}, expected {expected_sequence}"
        )
    epoch_start = _required_aware_datetime(
        payload,
        "epoch_start",
        event=event,
    )

    if trigger == "budget_exhausted":
        consumed = _required_int(
            payload,
            "cycle_budget_consumed",
            event=event,
            minimum=1,
            maximum=_SQLITE_MAX_SIGNED_INT,
        )
        limit = _required_int(
            payload,
            "cycle_budget_limit",
            event=event,
            minimum=1,
            maximum=_SQLITE_MAX_SIGNED_INT,
        )
        if (
            consumed != limit
            or consumed != current.cycle_budget_consumed
            or limit != current.cycle_budget_limit
        ):
            raise ProjectionError(
                f"PRODUCER_QUARANTINED event sequence={event.sequence} budget "
                "counters disagree with the attributable-event fold"
            )
    else:
        _required_int(
            payload,
            "bucket_capacity",
            event=event,
            minimum=1,
            maximum=_SQLITE_MAX_SIGNED_INT,
        )

    return replace(
        current,
        quarantine_epoch_open=True,
        quarantine_epoch_sequence=epoch_sequence,
        quarantine_epoch_started_at=epoch_start,
        quarantine_breach_trigger=trigger,
    )


_ASCII_DIGITS = frozenset("0123456789")


def _canonical_ascii_int(text: str) -> int | None:
    """Return the value of a canonical ASCII decimal literal, else ``None``.

    Deliberately stricter than ``str.isdigit()``, which accepts non-ASCII
    decimal forms (e.g. Arabic-Indic digits) that ``int()`` also parses —
    two distinct strings would then decode to one value and the encoding
    would stop being injective. Leading zeros are rejected for the same
    reason (``"07"`` and ``"7"`` must not both decode to 7).
    """

    if not text or not _ASCII_DIGITS.issuperset(text):
        return None
    if len(text) > 1 and text[0] == "0":
        return None
    return int(text)


def _decode_length_prefixed_parts(body: str) -> list[str]:
    """Invert ``signal_dedupe_key``'s length-prefixed encoding exactly.

    REV-0045 addendum-02 P0-5. The encoder joins ``{len}:{part}`` groups with
    ``|`` *because* length prefixes preserve tuple boundaries for every
    string — including parts that themselves contain ``|`` or ``:``. A
    decoder that splits the body on ``|`` throws that guarantee away and
    cannot read back keys the store legitimately minted. This decoder instead
    consumes each declared character count and only then requires the next
    separator, so it is a total inverse over arbitrary parts.

    Raises :class:`ProjectionError` on any input that is not exactly the
    image of some tuple under the encoder.
    """

    parts: list[str] = []
    index = 0
    length_of_body = len(body)
    while True:
        cursor = index
        while cursor < length_of_body and body[cursor] in _ASCII_DIGITS:
            cursor += 1
        declared_length = _canonical_ascii_int(body[index:cursor])
        if declared_length is None:
            raise ProjectionError("length-prefixed key has a malformed length prefix")
        if cursor >= length_of_body or body[cursor] != ":":
            raise ProjectionError("length-prefixed key is missing a length separator")
        cursor += 1
        end = cursor + declared_length
        if end > length_of_body:
            raise ProjectionError("length-prefixed key declares more text than it has")
        parts.append(body[cursor:end])
        if end == length_of_body:
            return parts
        if body[end] != "|":
            raise ProjectionError("length-prefixed key has a misaligned part boundary")
        index = end + 1


def sequence_from_release_dedupe_key(
    dedupe_key: str | None, *, producer_id: str
) -> int:
    """Parse the epoch sequence a ``PRODUCER_RELEASED`` dedupe key consumed,
    binding it to the producer that is expected to own it.

    WO-0140 D-R R-3: the no-epoch (zero-width) release consumes the next
    epoch sequence, and the payload deliberately carries no sequence — the
    ratified field list is closed. The dedupe key is the one place the
    consumed sequence structurally lives (``producer_release:{len}:{pid}|
    {len}:{seq}``, length-prefixed), so every consumer derives it from the
    key: stores when computing the release floor, the fold when applying a
    zero-width heal.

    This function is the exact inverse of ``signal_dedupe_key`` for that
    prefix, over EVERY producer id configuration admits (REV-0045
    addendum-02 P0-5 — the previous separator-splitting decoder could not
    read back keys the store itself minted for ids containing ``|``, which
    made those producers open and release live and then diverge on replay and
    restart, unhealably). It raises :class:`ProjectionError` on a missing key
    (``None`` — nullable on both the model and the column, so both floors
    must ignore it identically rather than one raising ``AttributeError``),
    on any key that is not the image of the ratified mint, on a key whose
    encoded producer does not match ``producer_id``, and on a sequence
    outside the SQLite-representable signed range.
    """

    if dedupe_key is None:
        raise ProjectionError("release dedupe key is absent")
    prefix = "producer_release:"
    if not dedupe_key.startswith(prefix):
        raise ProjectionError(f"release dedupe key {dedupe_key!r} has the wrong prefix")
    try:
        parts = _decode_length_prefixed_parts(dedupe_key[len(prefix) :])
    except ProjectionError as exc:
        raise ProjectionError(f"release dedupe key {dedupe_key!r}: {exc}") from exc
    if len(parts) != 2:
        raise ProjectionError(
            f"release dedupe key {dedupe_key!r} does not have exactly two parts"
        )
    key_producer, sequence_text = parts
    if key_producer != producer_id:
        raise ProjectionError(
            f"release dedupe key {dedupe_key!r} is bound to producer "
            f"{key_producer!r}, not {producer_id!r}"
        )
    sequence = _canonical_ascii_int(sequence_text)
    if sequence is None:
        raise ProjectionError(
            f"release dedupe key {dedupe_key!r} has a malformed sequence part"
        )
    if sequence < 1 or sequence > _SQLITE_MAX_SIGNED_INT:
        raise ProjectionError(
            f"release dedupe key {dedupe_key!r} carries an out-of-range sequence"
        )
    return sequence


def contributed_epoch_sequence(
    event: ExecutionEvent, *, producer_id: str
) -> int | None:
    """The epoch sequence an event structurally PROVES for ``producer_id``.

    REV-0045 addendum-02 P0-3/P0-4. This is the single source of derived
    sequence truth: every consumer — the tolerant fold's high-water
    bookkeeping, both stores' release floors, and the invalid-marker heal
    next-sequence check — must agree on what a logged event proves, or the
    same append-only history yields different results across live, replay,
    restart, memory and SQLite.

    The rule is event-type-specific, and no other field of any other event
    contributes anything:

    * ``PRODUCER_QUARANTINED`` ratifies ``epoch_sequence`` in its payload, so
      it contributes that value — but only as a real, bounded Python ``int``
      belonging to this producer. ``bool`` is excluded (JSON ``true`` is not
      an epoch), as are floats, digit strings, and values outside the
      SQLite-representable signed range.
    * ``PRODUCER_RELEASED`` has a CLOSED payload that does NOT ratify
      ``epoch_sequence``; its only structural source is its own
      producer-bound dedupe key. Reading a forbidden payload field here let
      an unratifiable value raise the high-water while the live floors
      ignored it, so live recovery and replay stopped agreeing on the
      predecessor sequence.

    Returns ``None`` when the event proves nothing for this producer.
    """

    if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED:
        if event.payload.get("producer_id") != producer_id:
            return None
        raw = event.payload.get("epoch_sequence")
        if not isinstance(raw, int) or isinstance(raw, bool):
            return None
        if raw < 1 or raw > _SQLITE_MAX_SIGNED_INT:
            return None
        return raw
    if event.event_type is ExecutionEventType.PRODUCER_RELEASED:
        try:
            return sequence_from_release_dedupe_key(
                event.dedupe_key, producer_id=producer_id
            )
        except ProjectionError:
            return None
    return None


def _validated_release_event_shape(
    event: ExecutionEvent,
) -> tuple[datetime, datetime]:
    """Validate a ``PRODUCER_RELEASED`` event's full structural shape —
    closed payload, actor hygiene, bounded rejected_count, aware timestamps
    ordered correctly — independent of any prior folded producer state.

    REV-0045 P0-4: shared by the strict applier AND the invalid-marker heal fast
    path in :func:`project_producer_rails_tolerant`, so a release event
    cannot clear a invalid-projection marker by any lesser standard than a normal
    release must meet. Returns ``(epoch_start, released_at)``.
    """

    _require_exact_payload_fields(event, _PRODUCER_RELEASE_FIELDS)

    actor = _required_str(event.payload, "actor", event=event)
    if not actor.strip() or actor != actor.strip():
        raise ProjectionError(
            f"PRODUCER_RELEASED event sequence={event.sequence} has invalid actor"
        )
    _required_int(
        event.payload,
        "rejected_count",
        event=event,
        minimum=0,
        maximum=_SQLITE_MAX_SIGNED_INT,
    )
    epoch_start = _required_aware_datetime(
        event.payload,
        "epoch_start",
        event=event,
    )
    released_at = _required_aware_datetime(
        event.payload,
        "released_at",
        event=event,
    )
    if released_at < epoch_start:
        raise ProjectionError(
            f"PRODUCER_RELEASED event sequence={event.sequence} has released_at "
            "before epoch_start"
        )
    return epoch_start, released_at


def _apply_producer_released(
    current: ProducerRailProjection, event: ExecutionEvent
) -> ProducerRailProjection:
    epoch_start, released_at = _validated_release_event_shape(event)

    if current.quarantine_epoch_open:
        # The open-epoch drift net: the release must name the exact epoch it
        # closes. A zero-width false claim while an epoch is open fails here
        # (epoch_start == released_at != true start). REV-0045 expanded
        # P1-1: a normal close does not MINT a new sequence, it closes the
        # currently open one — so the dedupe key must be parsed and bound
        # here too, and must name that exact (not "next") sequence.
        if epoch_start != current.quarantine_epoch_started_at:
            raise ProjectionError(
                f"PRODUCER_RELEASED event sequence={event.sequence} epoch_start "
                "does not match the open quarantine epoch"
            )
        closed_sequence = sequence_from_release_dedupe_key(
            event.dedupe_key, producer_id=current.producer_id
        )
        if closed_sequence != current.quarantine_epoch_sequence:
            raise ProjectionError(
                f"PRODUCER_RELEASED event sequence={event.sequence} closes epoch "
                f"sequence {closed_sequence}, expected the open epoch's own "
                f"{current.quarantine_epoch_sequence}"
            )
        return replace(
            current,
            cycle_budget_limit=None,
            cycle_budget_consumed=0,
            quarantine_epoch_open=False,
            quarantine_epoch_started_at=None,
            quarantine_breach_trigger=None,
        )

    # WO-0140 D-R R-3: the no-epoch (zero-width) release. Accepted ONLY as a
    # zero-width window, and ONLY from the zero state or the legacy wedge
    # (consumed >= pinned limit with no opener — a pre-R6a shape). The
    # interior shape (0 < consumed < limit) would be an UNRATIFIED CYCLE
    # RESET of a partially consumed budget in replay and is refused
    # (pass-2 F-H). The consumed
    # sequence lives in the dedupe key — the ratified payload carries none.
    if epoch_start != released_at:
        raise ProjectionError(
            f"PRODUCER_RELEASED event sequence={event.sequence} has no open "
            "quarantine epoch and is not a zero-width heal"
        )
    is_zero_state = (
        current.cycle_budget_limit is None and current.cycle_budget_consumed == 0
    )
    is_wedge = (
        current.cycle_budget_limit is not None
        and current.cycle_budget_consumed >= current.cycle_budget_limit
    )
    if not (is_zero_state or is_wedge):
        raise ProjectionError(
            f"PRODUCER_RELEASED event sequence={event.sequence} is a zero-width "
            "heal of a mid-cycle rail (unratified cycle reset refused)"
        )
    consumed_sequence = sequence_from_release_dedupe_key(
        event.dedupe_key, producer_id=current.producer_id
    )
    # REV-0045 expanded P1-1: the ratified rule mints the NEXT sequence, not
    # merely a higher one — accepting any upward jump would let a mismatched or
    # gapped key skip sequences no opener or prior release ever claimed.
    if consumed_sequence != current.quarantine_epoch_sequence + 1:
        raise ProjectionError(
            f"PRODUCER_RELEASED event sequence={event.sequence} consumes epoch "
            f"sequence {consumed_sequence}, expected the exact next "
            f"{current.quarantine_epoch_sequence + 1}"
        )
    return replace(
        current,
        cycle_budget_limit=None,
        cycle_budget_consumed=0,
        quarantine_epoch_open=False,
        quarantine_epoch_started_at=None,
        quarantine_breach_trigger=None,
        quarantine_epoch_sequence=consumed_sequence,
    )


def project_producer_rails(
    events: Iterable[ExecutionEvent],
) -> dict[str, ProducerRailProjection]:
    """Fold ordered signal/producer events into per-producer rail projections.

    Every encountered signal producer remains in the mapping, including one
    whose only event is excluded from budget accounting or whose epoch has been
    released. Malformed required payloads, counter drift, illegal post-open
    debits, and non-monotonic epoch identities fail closed.
    """

    projected: dict[str, ProducerRailProjection] = {}
    for event in events:
        if (
            event.event_type not in _PRODUCER_RAIL_SIGNAL_EVENT_TYPES
            and event.event_type
            not in {
                ExecutionEventType.PRODUCER_QUARANTINED,
                ExecutionEventType.PRODUCER_RELEASED,
            }
        ):
            continue

        producer_id = _producer_id_from_event(event)
        current = projected.setdefault(
            producer_id,
            ProducerRailProjection(producer_id=producer_id),
        )

        if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED:
            projected[producer_id] = _apply_producer_quarantined(current, event)
        elif event.event_type is ExecutionEventType.PRODUCER_RELEASED:
            projected[producer_id] = _apply_producer_released(current, event)
        elif _is_attributable_signal_event(event):
            projected[producer_id] = _apply_attributable_signal_event(current, event)
    return projected


def fold_producer_rail(
    seed: ProducerRailProjection,
    events: Iterable[ExecutionEvent],
) -> ProducerRailProjection:
    """Fold ONE producer's rail events from a caller-supplied seed.

    WO-0140 D-R R-2: the bounded verification fold. The caller supplies the
    segment (this producer's events after its last ``PRODUCER_RELEASED``,
    exclusive) and the state-conditional seed; the STRICT appliers run
    unchanged, so every fail-closed property of the full fold holds here.
    Events for other producers are skipped, not an error — the SQL-side
    filter and this guard are belt and braces.
    """

    current = seed
    for event in events:
        if (
            event.event_type not in _PRODUCER_RAIL_SIGNAL_EVENT_TYPES
            and event.event_type
            not in {
                ExecutionEventType.PRODUCER_QUARANTINED,
                ExecutionEventType.PRODUCER_RELEASED,
            }
        ):
            continue
        if _producer_id_from_event(event) != seed.producer_id:
            continue
        if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED:
            current = _apply_producer_quarantined(current, event)
        elif event.event_type is ExecutionEventType.PRODUCER_RELEASED:
            current = _apply_producer_released(current, event)
        elif _is_attributable_signal_event(event):
            current = _apply_attributable_signal_event(current, event)
    return current


@dataclass(frozen=True)
class InvalidProjectionMarker:
    """Derived record of one producer whose rail history cannot be folded.

    WO-0140 D-R R-1: the marker is DERIVED, in-memory state — recomputed
    identically by both stores and by replay from the same log, never
    persisted. ``last_known_epoch_sequence`` is the max readable payload
    ``epoch_sequence`` among the producer's ``PRODUCER_*`` events (0 if none);
    the stores combine it with the durable rail row under the never-regress
    rule before minting any later dedupe key.
    """

    producer_id: str
    offending_sequence: int
    reason: str
    last_known_epoch_sequence: int


def project_producer_rails_tolerant(
    events: Iterable[ExecutionEvent],
) -> tuple[dict[str, ProducerRailProjection], dict[str, InvalidProjectionMarker]]:
    """Per-producer tolerant fold (WO-0140 D-R R-1).

    Mirrors :func:`project_producer_rails` event-for-event, but a
    ``ProjectionError`` invalidates ONLY the producer it arose on: that producer
    leaves the projection and gains a marker; every other producer folds
    exactly as the strict fold would. An event whose producer identity is
    itself unreadable still raises store-wide — there is no producer to
    invalidation (the one disclosed exception; not producible by pre-R6a writers).

    ``project_producer_rails`` itself stays strict on purpose: the replay
    conformance pins and the payload-exactness ratchet rely on it raising.
    """

    projected: dict[str, ProducerRailProjection] = {}
    invalid_at: dict[str, tuple[int, str]] = {}
    last_known: dict[str, int] = {}
    for event in events:
        if (
            event.event_type not in _PRODUCER_RAIL_SIGNAL_EVENT_TYPES
            and event.event_type
            not in {
                ExecutionEventType.PRODUCER_QUARANTINED,
                ExecutionEventType.PRODUCER_RELEASED,
            }
        ):
            continue

        producer_id = _producer_id_from_event(event)
        prior_high_water = last_known.get(producer_id, 0)

        # REV-0045 addendum-02 P0-4: high-water advances ONLY from a source
        # the event type structurally ratifies, judged before the event is
        # otherwise trusted. An opener contributes its bounded payload
        # carrier; a release contributes only its producer-bound key.
        contributed = contributed_epoch_sequence(event, producer_id=producer_id)
        if contributed is not None:
            last_known[producer_id] = max(prior_high_water, contributed)

        if producer_id in invalid_at:
            if event.event_type is ExecutionEventType.PRODUCER_RELEASED:
                # REV-0045 P0-4: the heal is a release like any other one —
                # it must pass the SAME structural validator (closed
                # payload, actor hygiene, bounded counters, aware
                # timestamps) before its zero-width shape or sequence are
                # even inspected. A malformed recovery event must never
                # clear a invalid-projection marker just because it happens to look
                # zero-width.
                try:
                    epoch_start, released_at = _validated_release_event_shape(event)
                except ProjectionError:
                    continue
                if epoch_start == released_at:
                    # WO-0140 D-R R-3 state 3: the zero-width release IS the
                    # heal — the fold boundary. The producer clears its marker and
                    # folding restarts from the zero state at the consumed
                    # sequence, which must be EXACTLY the next sequence the
                    # log has ever proven for this producer (not merely
                    # higher) — an unparseable key or a non-next sequence
                    # leaves it invalidated.
                    try:
                        healed_sequence = sequence_from_release_dedupe_key(
                            event.dedupe_key, producer_id=producer_id
                        )
                    except ProjectionError:
                        continue
                    if healed_sequence != prior_high_water + 1:
                        continue
                    del invalid_at[producer_id]
                    projected[producer_id] = ProducerRailProjection(
                        producer_id=producer_id,
                        quarantine_epoch_sequence=healed_sequence,
                    )
            continue

        current = projected.setdefault(
            producer_id,
            ProducerRailProjection(producer_id=producer_id),
        )
        try:
            if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED:
                projected[producer_id] = _apply_producer_quarantined(current, event)
            elif event.event_type is ExecutionEventType.PRODUCER_RELEASED:
                projected[producer_id] = _apply_producer_released(current, event)
            elif _is_attributable_signal_event(event):
                projected[producer_id] = _apply_attributable_signal_event(
                    current, event
                )
        except ProjectionError as exc:
            projected.pop(producer_id, None)
            invalid_at[producer_id] = (event.sequence, str(exc))

    invalidated = {
        producer_id: InvalidProjectionMarker(
            producer_id=producer_id,
            offending_sequence=sequence,
            reason=reason,
            last_known_epoch_sequence=last_known.get(producer_id, 0),
        )
        for producer_id, (sequence, reason) in invalid_at.items()
    }
    return projected, invalidated
