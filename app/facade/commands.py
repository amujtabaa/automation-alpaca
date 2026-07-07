"""Typed command facade — Spine v2 Phase 0 skeleton (ADR-005 / Spine v2 §10).

**Phase 0 scope note (do not remove until Phase 1 lands a concrete
implementation):** ``ExecutionCommandFacade`` is a ``Protocol`` defining the
intended *shape* of the command surface FastAPI routes will eventually depend
on. It is:

* **unimplemented** — every method body is ``...``; no concrete class
  satisfies this protocol yet;
* **unwired** — no route imports or calls this. Every current command route
  (``POST /api/candidates/{id}/approve``, ``POST /api/positions/{symbol}/
  flatten``, ``POST /api/controls/kill-switch``, etc.) still calls
  ``app.store``/``app.broker``/``app.monitoring`` directly — see
  ``docs/SPINE_PHASE0_INVENTORY.md``'s dependency map;
* **unenforced** — nothing blocks a route from bypassing this.

Method names/signatures are provisional and use the Spine v2 target
vocabulary (``primary``/``spawn``/``TradingState``), which does not exist in
the current codebase (``docs/MIGRATION_MATRIX.md``). Do not treat this as a
stable contract before Phase 1 forces the real shape against a concrete
implementation.
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

    async def create_exit(self, *, symbol: str, reason: str, actor: str) -> Any:
        """Open (or return the existing) reduce-only exit for ``symbol``.

        The eventual migrated analogue of today's
        ``StateStore.flatten_position`` (``app/store/core.py``'s
        ``plan_flatten_position``). ADR-003 targets different behavior under
        ``Halted``/``Reducing`` than the current implementation — see
        ``docs/SPINE_PHASE0_INVENTORY.md``'s conflict list before treating
        this signature as final.
        """
        ...

    async def cancel(self, *, order_id: str, actor: str) -> Any:
        """Cancel an open order/spawn. Analogue of today's
        ``POST /api/orders/{order_id}/cancel``."""
        ...

    async def pause_buys(self, *, actor: str) -> Any:
        """Analogue of today's ``POST /api/controls/pause-buys``."""
        ...

    async def resume_buys(self, *, actor: str) -> Any:
        """Analogue of today's ``POST /api/controls/resume-buys``."""
        ...

    async def set_kill_switch(self, *, engaged: bool, actor: str) -> Any:
        """Analogue of today's ``POST /api/controls/kill-switch``.

        Target model (Spine v2 §8 / ADR-003): a ``TradingState`` transition
        among ``Active``/``Reducing``/``Halted``, not today's binary
        ``kill_switch`` flag flip on ``SessionRecord`` (``app/models.py``).
        No ``TradingState`` type exists in this repo yet.
        """
        ...

    async def emergency_reduce_override(self, *, symbol: str, actor: str) -> Any:
        """ADR-003's explicit, audited override to reduce risk while
        ``Halted``. Has no current-codebase analogue — today's manual
        flatten already bypasses the kill switch unconditionally (see
        ``docs/SPINE_PHASE0_INVENTORY.md``), so there is nothing to wrap
        yet. Phase 3 scope.
        """
        ...
