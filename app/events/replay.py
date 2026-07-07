"""Replay + parity verification for the ``ExecutionEvent`` log (Spine v2 §11).

This is how the dual-store "strict parity" rule is *enforced* rather than hoped
for: replay the append-only event log into a fresh projection and assert it
matches — across the in-memory store, the SQLite store, and a from-scratch
replay — plus the snapshot+replay equivalence that bounds recovery time.

Phase 2 verifies the **position** projection (the one projector that exists).
The helpers return structured :class:`ParityResult` values rather than asserting,
so they serve both CI tests (assert on ``.ok``) and a future runtime health
check (log on mismatch) — §11's "run it in CI and periodically at runtime".

Pure except for :func:`project_store_event_log`, which only *reads* a store's
event log (never writes) and hands the events to the pure projector.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.events.projectors import PositionProjection, PositionProjector
from app.models import ExecutionEvent
from app.store.base import StateStore


@dataclass(frozen=True)
class ParityResult:
    """Outcome of a parity/replay check. ``ok`` is the pass/fail; ``detail`` is
    a human-readable explanation of the first divergence when ``ok`` is False.
    """

    ok: bool
    detail: str = ""


def _describe_projection_diff(
    label_a: str, a: PositionProjection, label_b: str, b: PositionProjection
) -> str:
    if a.up_to_sequence != b.up_to_sequence:
        return (
            f"up_to_sequence differs: {label_a}={a.up_to_sequence} "
            f"{label_b}={b.up_to_sequence}"
        )
    symbols = sorted(set(a.positions) | set(b.positions))
    for symbol in symbols:
        pa = a.positions.get(symbol)
        pb = b.positions.get(symbol)
        if pa != pb:
            return (
                f"position for {symbol!r} differs: "
                f"{label_a}={pa!r} {label_b}={pb!r}"
            )
    # Unreachable from compare_projections (it only calls this when a != b, and
    # an unequal projection must differ on up_to_sequence or some position);
    # a defensive fallback for any direct caller passing equal projections.
    return ""  # pragma: no cover


def compare_projections(
    label_a: str, a: PositionProjection, label_b: str, b: PositionProjection
) -> ParityResult:
    """Field-for-field comparison of two projections (order-independent over
    symbols). Used for dual-store parity and snapshot/replay equivalence."""

    if a == b:
        return ParityResult(ok=True)
    return ParityResult(ok=False, detail=_describe_projection_diff(label_a, a, label_b, b))


def verify_snapshot_replay(
    events: Sequence[ExecutionEvent], *, snapshot_at: int
) -> ParityResult:
    """Assert ``project(all) == resume(snapshot@snapshot_at, all)`` (§11).

    A full from-scratch replay must equal taking a projection snapshot at
    sequence ``snapshot_at`` and resuming it with the whole event list (resume
    applies only the tail beyond the snapshot). This is the property that lets
    recovery replay only events since the last snapshot instead of all history.
    """

    full = PositionProjector.project(events)
    snapshot = PositionProjector.project(
        [e for e in events if e.sequence <= snapshot_at]
    )
    resumed = PositionProjector.resume(snapshot, events)
    return compare_projections("full_replay", full, "snapshot+resume", resumed)


async def project_store_event_log(store: StateStore) -> PositionProjection:
    """Read a store's entire execution-event log and project position from it.

    The only non-pure helper — it *reads* (never writes) via
    ``get_execution_events`` and delegates to the pure projector.
    """

    events = await store.get_execution_events()
    return PositionProjector.project(events)


async def verify_dual_store_parity(
    memory_store: StateStore, sqlite_store: StateStore
) -> ParityResult:
    """Assert the in-memory and SQLite event logs project to the same position
    read model (the dual-store "strict parity" rule, §1/§11)."""

    mem_projection = await project_store_event_log(memory_store)
    sqlite_projection = await project_store_event_log(sqlite_store)
    return compare_projections(
        "memory", mem_projection, "sqlite", sqlite_projection
    )
