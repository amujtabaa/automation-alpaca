"""Typed command facade — Spine v2 (ADR-005 / Spine v2 §10).

``ExecutionCommandFacade`` is a ``Protocol`` defining the command surface
FastAPI routes depend on. As of Phase 1:

* **``pause_buys``/``resume_buys`` are real** — implemented by
  ``app.facade.store_backed.StoreBackedCommandFacade`` and wired into
  ``POST /api/controls/{pause,resume}-buys`` (see
  ``docs/SPINE_PHASE1_FACADE_REPORT.md``).
* **Every other method still raises ``NotYetImplementedError``** — either
  because it has no current-codebase analogue (``primary``/``spawn``/
  ``TradingState`` don't exist yet), or because migrating it now would
  freeze an ADR-conflicted behavior (manual flatten, kill-switch) as the
  facade's contract before Phase 3 makes a deliberate decision — see
  ``docs/SPINE_PHASE0_INVENTORY.md`` §3.1/§3.4.
* **Every other route still bypasses this facade entirely**, calling
  ``app.store``/``app.broker``/``app.monitoring`` directly — see
  ``docs/SPINE_PHASE0_INVENTORY.md``'s dependency map. Nothing enforces the
  boundary yet (Phase 5).

Method names/signatures are provisional and use the Spine v2 target
vocabulary (``primary``/``spawn``/``TradingState``), which does not exist in
the current codebase (``docs/MIGRATION_MATRIX.md``) — don't treat this as a
stable contract for the still-unimplemented methods.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["ExecutionCommandFacade"]


@runtime_checkable
class ExecutionCommandFacade(Protocol):
    """Typed command surface for FastAPI routes.

    Per ADR-005, a route may validate HTTP shape, authenticate, construct a
    command, call the facade, and map the resulting domain error to an HTTP
    response — it must not mutate a store, call a broker adapter, or call a
    monitoring helper directly. Every route currently does at least one of
    those; migrating them is Phase 1+, not this skeleton.

    Each command is expected to raise :class:`~app.facade.errors.
    EngineNotReadyError` when the engine isn't ready, and a structured
    :class:`~app.facade.errors.FacadeError` subclass otherwise — never a raw
    exception a route would have to interpret.
    """

    async def create_exit(self, *, symbol: str, actor: str) -> Any:
        """Operator-commanded full exit (manual flatten) for ``symbol`` — real as
        of P6e. Wraps ``StateStore.flatten_position`` (X-001 atomic) after clearing
        open buys; ADR-003 denies it while ``Halted`` (409). ``POST
        /api/positions/{symbol}/flatten``."""
        ...

    async def cancel(self, *, order_id: str, actor: str) -> Any:
        """Manually cancel an open order (P6e) — ``POST
        /api/orders/{order_id}/cancel``. 404 unknown / 409 terminal-or-quarantined
        / 502 broker-failure; CHAOS-1 cancel_pending semantics preserved."""
        ...

    async def pause_buys(self, *, actor: str) -> Any:
        """Real as of Phase 1 — see
        ``app.facade.store_backed.StoreBackedCommandFacade.pause_buys``,
        wired into ``POST /api/controls/pause-buys``."""
        ...

    async def resume_buys(self, *, actor: str) -> Any:
        """Real as of Phase 1 — see
        ``app.facade.store_backed.StoreBackedCommandFacade.resume_buys``,
        wired into ``POST /api/controls/resume-buys``."""
        ...

    async def upsert_watchlist_symbol(
        self, *, symbol: str, armed: bool, actor: str
    ) -> Any:
        """Upsert a watchlist symbol — ``POST /api/watchlist`` (P6a)."""
        ...

    async def remove_watchlist_symbol(self, *, symbol: str, actor: str) -> Any:
        """Remove a watchlist symbol — ``DELETE /api/watchlist/{symbol}`` (P6a)."""
        ...

    async def inject_mock_candidate(
        self,
        *,
        symbol: str,
        strategy: str,
        reason: str,
        suggested_quantity: Any,
        suggested_limit_price: Any,
        actor: str,
    ) -> Any:
        """Inject a dev/mock candidate — ``POST /api/dev/candidates`` (P6a)."""
        ...

    async def approve_candidate(self, *, candidate_id: str, actor: str) -> Any:
        """Approve a candidate + dispatch its order with revert-on-failure —
        ``POST /api/candidates/{id}/approve`` (P6c). The store's
        ``create_order_for_candidate`` stays the authoritative risk check."""
        ...

    async def reject_candidate(self, *, candidate_id: str, actor: str) -> Any:
        """Reject a candidate (idempotent, terminal) —
        ``POST /api/candidates/{id}/reject`` (P6c)."""
        ...

    async def set_kill_switch(self, *, engaged: bool, actor: str) -> Any:
        """``POST /api/controls/kill-switch`` (real as of P6b). Wraps
        ``StateStore.set_kill_switch``; the wave-3d TradingState FSM already made
        it event_truth (folds to ``Halted``), so this is a boundary move, not a
        behavior change."""
        ...

    async def close_session(self, *, actor: str) -> Any:
        """``POST /api/session/close`` (P6b): close the active session (expire
        candidates, cancel CREATED orders, snapshot positions)."""
        ...

    async def emergency_reduce_override(self, *, symbol: str, actor: str) -> Any:
        """ADR-003's explicit, audited override to reduce risk while
        ``Halted``. Has no current-codebase analogue — today's manual
        flatten already bypasses the kill switch unconditionally (see
        ``docs/SPINE_PHASE0_INVENTORY.md``), so there is nothing to wrap
        yet. Phase 3 scope.
        """
        ...
