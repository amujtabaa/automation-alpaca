"""Typed query facade — Spine v2 (ADR-005 / Spine v2 §10).

As of Phase 6 (ARCH-002 doc refresh): every query method is real and wired
to its route EXCEPT ``list_primaries``/``list_spawns``/``kill_state`` — the
Spine v2 ``primary``/``spawn``/``TradingState`` target vocabulary that has no
current-codebase analogue yet — which still raise ``NotYetImplementedError``.
See ``app.facade.commands`` for the shared route→facade boundary/enforcement note.
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

    async def list_watchlist(self) -> Any:
        """All watchlist symbols — ``GET /api/watchlist`` (P6a)."""
        ...

    async def list_market_snapshots(self) -> Any:
        """Current per-symbol market snapshots + ``pct_move`` as
        ``MarketSnapshotView`` — ``GET /api/marketdata/snapshots`` (P6a)."""
        ...

    async def get_current_session_view(self) -> Any:
        """Current session with the live ``session_type`` overlay —
        ``GET /api/session`` (P6b)."""
        ...

    async def get_review(self, *, target_date: Any) -> Any:
        """Full session review for a date (closed-vs-active point-in-time) as a
        ``ReviewView`` — ``GET /api/review`` (P6b)."""
        ...

    async def list_candidates(self) -> Any:
        """Candidates for the active session — ``GET /api/candidates`` (P6c)."""
        ...

    async def get_candidate(self, *, candidate_id: str) -> Any:
        """One candidate; 404 if absent — ``GET /api/candidates/{id}`` (P6c)."""
        ...

    async def get_position(self, *, symbol: str) -> Any:
        """One symbol's derived position (flat if no fills); an out-of-domain
        symbol → 422 — ``GET /api/positions/{symbol}`` (P6d)."""
        ...

    async def list_sell_intents(
        self, *, session_id: Optional[str] = None, symbol: Optional[str] = None
    ) -> Any:
        """The sell-intent lifecycle, optionally filtered by session/symbol —
        ``GET /api/sell-intents`` (P6d)."""
        ...

    async def list_orders(self) -> Any:
        """Every order — ``GET /api/orders`` (P6d)."""
        ...

    async def list_submit_recoveries(self, *, open_only: bool = True) -> Any:
        """Broker-submit recovery records (D-017); ``open_only`` (default)
        returns unresolved + needs-review — ``GET /api/order-recoveries``
        (P6d)."""
        ...

    async def get_order(self, *, order_id: str) -> Any:
        """One order; 404 if unknown — ``GET /api/orders/{order_id}`` (P6d)."""
        ...

    async def list_events(
        self,
        *,
        limit: Optional[int] = None,
        event_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Any:
        """The append-only audit event log, optionally filtered —
        ``GET /api/events`` (P6d)."""
        ...

    async def operator_orders(self) -> Any:
        """The operator's classified order-lifecycle truth (D-020), returned as
        ``OperatorOrdersResponse`` — ``GET /api/operator/orders`` (P6d)."""
        ...

    async def protection_status(self) -> Any:
        """The live Sell-Side Protection state (Phase 7), classified
        server-side, returned as ``ProtectionStatusResponse`` —
        ``GET /api/protection`` (P6d)."""
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
