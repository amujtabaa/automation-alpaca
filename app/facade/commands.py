"""Typed command facade — Spine v2 (ADR-005 / Spine v2 §10).

``ExecutionCommandFacade`` is a ``Protocol`` defining the command surface
FastAPI routes depend on. As of Phase 6 (ARCH-002 doc refresh):

* **Every command method is real** — implemented by
  ``app.facade.store_backed.StoreBackedCommandFacade`` and wired into its
  route (order approval/reject, manual flatten, emergency-reduce, cancel,
  kill switch, pause/resume buys, close session, dev inject). None of the
  command methods raise ``NotYetImplementedError`` anymore.
* **The route→facade boundary is enforced** by import-linter Contract 5
  (`.importlinter`; ADR-005 / ADR-006) — routes reach the store/engine/broker
  only through this facade, no longer directly.
* **Provisional vocabulary only:** the ``primary``/``spawn``/``TradingState``
  Spine v2 target names have no current-codebase analogue, so the *query*-side
  ``list_primaries``/``list_spawns``/``kill_state`` are the only facade methods
  that still raise ``NotYetImplementedError`` (see ``app.facade.queries``).

Method names/signatures are provisional and use the Spine v2 target
vocabulary (``primary``/``spawn``/``TradingState``), which does not exist in
the current codebase (``docs/MIGRATION_MATRIX.md``) — don't treat this as a
stable contract for the still-unimplemented methods.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.models import (
    ExecutionEnvelope,
    SubmitRecoveryAttestation,
    SubmitRecoveryFillCommand,
    SubmitRecoveryFillResult,
    SubmitRecoveryRecord,
)

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

    async def approve_envelope(
        self, *, draft: ExecutionEnvelope, actor: str
    ) -> ExecutionEnvelope:
        """Approve + activate an execution envelope as ONE store-atomic unit
        (ADR-010 §1 / WO-0017) — THE human-gated approval surface for
        autonomous sell-side execution. ``POST /api/envelopes/approve``. 409
        while ``Halted`` (kill switch blocks new standing order intent) or on a
        terminal / duplicate-ACTIVE conflict."""
        ...

    async def cancel_envelope(
        self, *, envelope_id: str, actor: str
    ) -> ExecutionEnvelope:
        """Withdraw a pre-activation envelope (PENDING/APPROVED/FROZEN →
        CANCELLED, the ADR-010 §3 escape edges; idempotent for already-
        CANCELLED). An ACTIVE mandate is deliberately NOT cancellable here
        (409) — stopping a live mandate is the kill switch's or the flatten's
        job. ``POST /api/envelopes/{id}/cancel``; 404 if unknown."""
        ...

    async def ingest_submit_recovery_fill(
        self,
        *,
        command: SubmitRecoveryFillCommand,
        actor: str,
    ) -> SubmitRecoveryFillResult:
        """Ingest one evidenced canonical fill before recovery release."""
        ...

    async def reconcile_submit_recovery(
        self,
        *,
        attestation: SubmitRecoveryAttestation,
        actor: str,
    ) -> SubmitRecoveryRecord:
        """Release one needs-review contribution after event-truth parity."""
        ...
