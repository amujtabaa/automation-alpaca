"""Typed query facade — Spine v2 Phase 0 skeleton (ADR-005 / Spine v2 §10).

Same Phase 0 caveats as ``app.facade.commands.ExecutionCommandFacade``:
unimplemented, unwired, unenforced. See that module's docstring.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

__all__ = ["ExecutionQueryFacade"]


@runtime_checkable
class ExecutionQueryFacade(Protocol):
    """Typed read surface for FastAPI routes."""

    async def list_positions(self) -> Any:
        """Analogue of today's ``GET /api/positions``."""
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
        """Unmanaged/external venue orders surfaced by reconciliation (Spine
        v2 §7). No reconciliation engine of that shape exists yet — today's
        closest analogue is the submit-recovery ledger
        (``StateStore.list_submit_recoveries``), which is narrower in scope.
        """
        ...
