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

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from app.events.projectors import (
    PositionProjection,
    PositionProjector,
    active_emergency_reduce_overrides,
    current_trading_state,
    quarantined_symbols,
    timeout_quarantined_order_ids,
)
from app.models import ExecutionEvent, TradingState
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


# --------------------------------------------------------------------------- #
# Read-model parity beyond position (Phase 6 — legacy-table demotion).
#
# Position is one event-truth read model; Phase 3/4 added more, each folded from
# the same append-only ``ExecutionEvent`` log by a pure projector: the
# overfill-quarantine set (wave 3b), the timeout-quarantine set (wave 3c), the
# effective ``TradingState`` per session (wave 3d/4f), and the emergency-reduce
# override grants per session (wave 3e). Their persisted columns
# (``orders.status``, ``sessions.trading_state``) are co-written READ MODELS: the
# first durable write is the ``ExecutionEvent``, and the column is reconstructable
# from the log. This verifier proves that reconstructability the same way the
# position verifier does — replay the log and assert the two stores agree —
# extending the "strict parity" enforcement to the full event-truth read-model
# surface, not position alone.
#
# NOT covered here: a full order-status / spawn state-machine projection. That
# projector is a deliberate, documented deferral to the Spine §4 primary/spawn
# phase (docs/MIGRATION_MATRIX.md: "order-status/spawn projector deferred, mirror
# of 3c-C5") — the order-row ``status`` column stays a co-written read-model whose
# safety-critical *derived quantity*, position, IS projected and parity-checked.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ReadModelProjection:
    """The event-truth read models derivable purely from an ``ExecutionEvent``
    log, other than position (which has its own :class:`PositionProjection`).
    Session-scoped models (``trading_state``, ``emergency_overrides``) are keyed
    by ``session_id`` so a multi-session log is compared session-by-session."""

    quarantined_symbols: frozenset[str]
    timeout_quarantined_order_ids: frozenset[str]
    trading_state: Mapping[str, TradingState] = field(default_factory=dict)
    emergency_overrides: Mapping[str, frozenset[str]] = field(default_factory=dict)


def _session_ids(events: Sequence[ExecutionEvent]) -> list[str]:
    """Every ``session_id`` appearing on any event, insertion-ordered (stable,
    deterministic) — the sessions whose per-session read models must be compared."""

    seen: dict[str, None] = {}
    for event in events:
        if event.session_id is not None:
            seen.setdefault(event.session_id, None)
    return list(seen)


def project_read_models(events: Iterable[ExecutionEvent]) -> ReadModelProjection:
    """Fold the non-position event-truth read models from ``events`` (pure). Each
    field delegates to the SAME projector the stores fold through, so this is the
    canonical replay reconstruction of every co-written read-model column."""

    materialized = list(events)
    sessions = _session_ids(materialized)
    return ReadModelProjection(
        quarantined_symbols=frozenset(quarantined_symbols(materialized)),
        timeout_quarantined_order_ids=frozenset(
            timeout_quarantined_order_ids(materialized)
        ),
        trading_state={
            sid: current_trading_state(materialized, sid) for sid in sessions
        },
        emergency_overrides={
            sid: frozenset(active_emergency_reduce_overrides(materialized, sid))
            for sid in sessions
        },
    )


def _describe_read_model_diff(
    label_a: str, a: ReadModelProjection, label_b: str, b: ReadModelProjection
) -> str:
    if a.quarantined_symbols != b.quarantined_symbols:
        return (
            f"quarantined_symbols differ: {label_a}={sorted(a.quarantined_symbols)} "
            f"{label_b}={sorted(b.quarantined_symbols)}"
        )
    if a.timeout_quarantined_order_ids != b.timeout_quarantined_order_ids:
        return (
            f"timeout_quarantined_order_ids differ: "
            f"{label_a}={sorted(a.timeout_quarantined_order_ids)} "
            f"{label_b}={sorted(b.timeout_quarantined_order_ids)}"
        )
    for sid in sorted(set(a.trading_state) | set(b.trading_state)):
        sa = a.trading_state.get(sid)
        sb = b.trading_state.get(sid)
        if sa != sb:
            return (
                f"trading_state for session {sid!r} differs: "
                f"{label_a}={sa} {label_b}={sb}"
            )
    for sid in sorted(set(a.emergency_overrides) | set(b.emergency_overrides)):
        oa = a.emergency_overrides.get(sid, frozenset())
        ob = b.emergency_overrides.get(sid, frozenset())
        if oa != ob:
            return (
                f"emergency_overrides for session {sid!r} differ: "
                f"{label_a}={sorted(oa)} {label_b}={sorted(ob)}"
            )
    # Unreachable from compare_read_models (only called when a != b, and an
    # unequal ReadModelProjection must differ on one field above); defensive.
    return ""  # pragma: no cover


def compare_read_models(
    label_a: str, a: ReadModelProjection, label_b: str, b: ReadModelProjection
) -> ParityResult:
    """Field-for-field comparison of two non-position read-model projections
    (order-independent over symbols/sessions)."""

    if a == b:
        return ParityResult(ok=True)
    return ParityResult(
        ok=False, detail=_describe_read_model_diff(label_a, a, label_b, b)
    )


async def verify_dual_store_readmodel_parity(
    memory_store: StateStore, sqlite_store: StateStore
) -> ParityResult:
    """Assert the in-memory and SQLite event logs project to the same NON-position
    read models — quarantine, timeout-quarantine, per-session ``TradingState``, and
    per-session emergency-reduce overrides (Phase 6). Complements
    :func:`verify_dual_store_parity` (position) so the dual-store "strict parity"
    rule covers the full event-truth read-model surface, proving every co-written
    read-model column is reconstructable identically from either store's log."""

    mem = project_read_models(await memory_store.get_execution_events())
    sqlite = project_read_models(await sqlite_store.get_execution_events())
    return compare_read_models("memory", mem, "sqlite", sqlite)
