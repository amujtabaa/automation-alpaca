"""Typed query facade — Spine v2 (ADR-005 / Spine v2 §10).

Same status as ``app.facade.commands.ExecutionCommandFacade``: one method
(``list_positions``) is real as of Phase 1, wired into
``GET /api/positions``; everything else still raises
``NotYetImplementedError`` and every other route still bypasses this
facade. See that module's docstring for the full explanation.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

__all__ = ["ExecutionQueryFacade"]


@runtime_checkable
class ExecutionQueryFacade(Protocol):
    """Typed read surface for FastAPI routes."""

    async def list_positions(self) -> Any:
        """Real as of Phase 1 — see
        ``app.facade.store_backed.StoreBackedQueryFacade.list_positions``,
        wired into ``GET /api/positions``."""
        ...

    async def list_primaries(self, *, symbol: Optional[str] = None) -> Any:
        """The eventual migrated analogue of today's sell-intent + order
        views (``GET /api/sell-intents``, ``GET /api/orders``) once
        primary/spawn state exists (Spine v2 §4). No ``primary``/``spawn``
        model exists in this repo yet — see ``docs/MIGRATION_MATRIX.md``.
        """
        ...

    async def list_spawns(self, *, primary_id: str) -> Any:
        """No ``spawn`` model exists in this repo yet."""
        ...

    async def kill_state(self) -> Any:
        """Target model: the ``TradingState`` (``Active``/``Reducing``/
        ``Halted``), not today's ``session.kill_switch``/``buys_paused``
        booleans (``app/models.py``)."""
        ...

    async def list_external_orders(self) -> Any:
        """External/unmanaged venue orders surfaced by reconciliation (Spine v2
        §7). Real as of wave 4h — reads the durable, deduped
        ``reconcile_external_order`` audit records and returns typed
        ``ExternalOrderView`` rows. Never absorbed into managed state or folded
        into position; an empty list is the healthy steady state."""
        ...

    async def list_position_mismatches(self) -> Any:
        """Broker-vs-local position drifts surfaced by reconciliation (Spine v2
        §7 / wave 4h). Reads the durable, deduped ``reconcile_position_mismatch``
        audit records and returns typed ``PositionMismatchView`` rows. Position
        truth is never overwritten (Rule 7) — these are needs-review records that
        also hold trading reduce-only until cleared. Empty = healthy."""
        ...
