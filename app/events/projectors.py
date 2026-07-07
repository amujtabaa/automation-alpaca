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
            positions[fill.symbol] = apply_fill(current, fill)
        return PositionProjection(positions=positions, up_to_sequence=up_to_sequence)
