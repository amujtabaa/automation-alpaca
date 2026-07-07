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
        """Real as of Phase 1 — see
        ``app.facade.store_backed.StoreBackedCommandFacade.pause_buys``,
        wired into ``POST /api/controls/pause-buys``."""
        ...

    async def resume_buys(self, *, actor: str) -> Any:
        """Real as of Phase 1 — see
        ``app.facade.store_backed.StoreBackedCommandFacade.resume_buys``,
        wired into ``POST /api/controls/resume-buys``."""
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
