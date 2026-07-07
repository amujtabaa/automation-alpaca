"""Pure projectors — reconstruct state from the ``ExecutionEvent`` log.

A *projector* folds an ordered event stream into a read model. Phase 2 ships one
concrete projector, :class:`PositionProjector`, which derives per-symbol
positions from ``FILL`` events by reusing ``app/position.py:apply_fill`` — the
folding formula lives in exactly one place (Rule 7), whether the fills come from
the legacy fill table or (Phase 3) the event log.

Everything here is pure: no IO, no async, no clock. Projectors consume an
already-read ``list[ExecutionEvent]`` (the store owns reading), which keeps them
deterministic and trivially unit-testable, and lets the replay verifier
(``app/events/replay.py``) drive them offline.

**Precondition:** events must be supplied in ascending ``sequence`` order (the
store's ``get_execution_events`` guarantees this). The fold is order-dependent;
projectors do not re-sort, so an ordering violation is a caller bug, not
silently masked.

Projectors for primary / spawn / TradingState / quarantine are Phase 3 — they
implement the same "fold events → read model" shape once those state machines
exist (see ``docs/SPINE_MIGRATION_PROGRESS.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models import ExecutionEvent, ExecutionEventType, Fill, Position
from app.policy import fill_value_reason
from app.position import apply_fill


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
    """Symbols quarantined by a broker-authoritative overfill (ADR-001): a
    recorded ``FILL`` that crossed the long-only position through flat into short.
    Autonomous spawns are blocked and manual review is required.

    **Latched, not live.** A symbol is quarantined once its ``FILL``-event fold
    reaches a negative running quantity *at any point* — NOT merely when the
    *current* projected quantity is negative. A later covering BUY (from a
    pre-existing order, a reconciliation-inferred cover, or manual review) returns
    the projection to ``>= 0`` but MUST NOT silently lift the quarantine: ADR-001
    requires the symbol stay quarantined (autonomous trading halted) until an
    audited reconciliation/review explicitly clears it, else covering the short
    would resume autonomous trading from an unreconciled state ("The system must
    not continue autonomous trading from such a state"). Deriving from the fold
    *history* (a crossing that happened stays in the sequence) makes the latch
    durable and replay-stable without a separate mutable flag.

    (The explicit operator/reconciliation *clear* path is Phase 4; until it
    exists a quarantine is sticky for the session — the conservative,
    capital-preserving default. §6 "stuck reconciliation" alerting is the
    operator-visibility counterpart, also Phase 4.)

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
    quarantined: set[str] = set()
    for symbol in symbols:
        position = Position(symbol=symbol)
        for event in events:
            if event.event_type is not ExecutionEventType.FILL or event.symbol != symbol:
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
    (docs/SPINE_WAVE3C_PLAN.md C5). Only the wave-3c evented transitions emit
    these order-lifecycle events, so a normally-submitted order (whose
    ``SUBMITTING → SUBMITTED`` writes no ExecutionEvent) never appears here.
    """

    latest: dict[str, ExecutionEventType] = {}
    for event in events:
        if event.event_type in _ORDER_LIFECYCLE_EVENT_TYPES and event.order_id is not None:
            latest[event.order_id] = event.event_type
    return {
        order_id
        for order_id, event_type in latest.items()
        if event_type is ExecutionEventType.TIMEOUT_QUARANTINE
    }


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
