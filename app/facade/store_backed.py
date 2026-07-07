"""Store-backed concrete facade implementation — Spine v2 Phase 1 (ADR-005).

Implements :class:`~app.facade.queries.ExecutionQueryFacade` and
:class:`~app.facade.commands.ExecutionCommandFacade` by delegating to an
existing :class:`~app.store.base.StateStore` — Phase 1's "wrap existing
behavior, don't migrate it" rule. Every method implemented for real here
must produce byte-for-byte the same result the route previously got calling
the store directly; see
``tests/test_phase1_facade_equivalence.py`` for the behavior-equivalence
proof.

Only two methods are real wraps this phase: ``list_positions`` (query) and
``pause_buys``/``resume_buys`` (command) — the two low-risk routes
``docs/SPINE_PHASE0_MIGRATION_PLAN.md`` names as the Phase 1 candidates.
Every other Protocol method raises :class:`~app.facade.errors.
NotYetImplementedError`, either because it has no current-codebase analogue
(``primary``/``spawn``/``TradingState`` — Spine v2 §4/§8) or because
migrating it now would freeze an ADR-conflicted behavior (manual flatten,
kill-switch — ``docs/SPINE_PHASE0_INVENTORY.md`` §3.1/§3.4) as the facade's
contract before Phase 3 makes a deliberate decision.
"""

from __future__ import annotations

from typing import Any, Optional

from app.facade.errors import NotYetImplementedError
from app.models import Position, SessionRecord
from app.store.base import StateStore

# No auth/actor-tracking system exists yet (docs/MIGRATION_MATRIX.md: "Auth
# for command endpoints: absent/limited"). The command Protocol's `actor`
# parameter names the target audited-command shape (ADR-005: "command/kill
# endpoints are a sensitive control surface even in paper"), but nothing
# persists it today — routes pass this placeholder rather than inventing a
# fake identity. Migrating this is tracked by the Migration Matrix's own
# "Auth for command endpoints" row, not Phase 1.
UNAUTHENTICATED_ACTOR = "unauthenticated"


class StoreBackedQueryFacade:
    """``ExecutionQueryFacade`` implementation wrapping an existing store."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    async def list_positions(self) -> list[Position]:
        """Unchanged wrap of ``StateStore.list_positions`` — the exact call
        ``GET /api/positions`` made directly before this facade existed."""
        return await self._store.list_positions()

    async def list_primaries(self, *, symbol: Optional[str] = None) -> Any:
        raise NotYetImplementedError(
            "list_primaries: no primary/spawn model exists yet (Spine v2 §4); "
            "see docs/MIGRATION_MATRIX.md"
        )

    async def list_spawns(self, *, primary_id: str) -> Any:
        raise NotYetImplementedError(
            "list_spawns: no spawn model exists yet (Spine v2 §4)"
        )

    async def kill_state(self) -> Any:
        raise NotYetImplementedError(
            "kill_state: no TradingState model exists yet (ADR-003 / Spine v2 "
            "§8); today's session.kill_switch/buys_paused booleans are not "
            "migrated behind this facade in Phase 1 — see "
            "docs/SPINE_PHASE0_INVENTORY.md §3.4"
        )

    async def list_external_orders(self) -> Any:
        raise NotYetImplementedError(
            "list_external_orders: no reconciliation engine of that shape "
            "exists yet (Spine v2 §7)"
        )


class StoreBackedCommandFacade:
    """``ExecutionCommandFacade`` implementation wrapping an existing store."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    async def pause_buys(self, *, actor: str) -> SessionRecord:
        """Unchanged wrap of ``StateStore.set_buys_paused(True)`` — the exact
        call ``POST /api/controls/pause-buys`` made directly before this
        facade existed. ``actor`` is accepted (Protocol shape) but not yet
        persisted anywhere — see module docstring."""
        return await self._store.set_buys_paused(True)

    async def resume_buys(self, *, actor: str) -> SessionRecord:
        """Unchanged wrap of ``StateStore.set_buys_paused(False)``."""
        return await self._store.set_buys_paused(False)

    async def create_exit(self, *, symbol: str, reason: str, actor: str) -> Any:
        raise NotYetImplementedError(
            "create_exit: manual flatten is not migrated behind the facade "
            "in Phase 1 — see docs/SPINE_PHASE0_INVENTORY.md §3.1 (ADR-003 "
            "conflict); routes still call StateStore.flatten_position "
            "directly"
        )

    async def cancel(self, *, order_id: str, actor: str) -> Any:
        raise NotYetImplementedError(
            "cancel: not migrated behind the facade in Phase 1; "
            "POST /api/orders/{id}/cancel still calls the store and broker "
            "adapter directly"
        )

    async def set_kill_switch(self, *, engaged: bool, actor: str) -> Any:
        raise NotYetImplementedError(
            "set_kill_switch: not migrated behind the facade in Phase 1 — "
            "see docs/SPINE_PHASE0_INVENTORY.md §3.4 (ADR-003/§8 conflict); "
            "POST /api/controls/kill-switch still calls the store directly"
        )

    async def emergency_reduce_override(self, *, symbol: str, actor: str) -> Any:
        raise NotYetImplementedError(
            "emergency_reduce_override: has no current-codebase analogue; "
            "Phase 3 scope (ADR-003)"
        )
