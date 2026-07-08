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

import contextlib
from typing import TYPE_CHECKING, Any, Iterator, Optional

from app.facade.dtos import ExternalOrderView, PositionMismatchView
from app.facade.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidInputError,
    NotYetImplementedError,
)
from app.models import EventType, Position, SessionRecord
from app.store.base import (
    CandidateTransitionError,
    EmergencyReduceBlockedError,
    FlattenBlockedError,
    InvalidControlValueError,
    InvalidFillError,
    InvalidOrderError,
    InvalidStatusError,
    OrderIntentBlockedError,
    OrderTransitionError,
    RecoveryTransitionError,
    RiskLimitBlockedError,
    SellIntentTransitionError,
    SessionAlreadyClosedError,
    SessionClosedError,
    StateStore,
    UnknownEntityError,
)

if TYPE_CHECKING:  # annotations only — no runtime import edge added until a wave uses them
    from app.approval.gate import ApprovalGate
    from app.broker.adapter import BrokerAdapter
    from app.config import Settings
    from app.marketdata.service import MarketDataService

# Store errors whose semantic kind maps to HTTP 409 once a route stops catching
# them directly (Phase 6 / ADR-005). See app.facade.errors for the full policy.
_CONFLICT_STORE_ERRORS = (
    CandidateTransitionError,
    OrderTransitionError,
    SellIntentTransitionError,
    RecoveryTransitionError,
    InvalidOrderError,
    InvalidFillError,
    SessionAlreadyClosedError,
    SessionClosedError,
    OrderIntentBlockedError,
    RiskLimitBlockedError,
    FlattenBlockedError,
    EmergencyReduceBlockedError,
)
# Store errors (and the bare ValueError normalize_symbol raises) that map to 422.
_INVALID_INPUT_STORE_ERRORS = (InvalidControlValueError, InvalidStatusError)


@contextlib.contextmanager
def _translate_store_errors() -> Iterator[None]:
    """Re-raise the store's ``StoreError`` subclasses as the status-carrying
    facade errors, so a migrated route catches only ``FacadeError`` (never
    ``app.store.base`` — a Contract-5 forbidden import) yet gets the exact HTTP
    status it produced before. An UNMAPPED store error is left to propagate as a
    raw 500 (a genuine bug, not a client mistake — matches today's routes).

    ``ValueError`` (from ``normalize_symbol``'s out-of-domain ticker rejection,
    DATA-2) becomes a 422, mirroring the routes' inline ``except ValueError``."""

    try:
        yield
    except UnknownEntityError as exc:
        raise EntityNotFoundError(str(exc)) from exc
    except _CONFLICT_STORE_ERRORS as exc:
        raise ConflictError(str(exc)) from exc
    except _INVALID_INPUT_STORE_ERRORS as exc:
        raise InvalidInputError(str(exc)) from exc
    except ValueError as exc:
        raise InvalidInputError(str(exc)) from exc

# No auth/actor-tracking system exists yet (docs/MIGRATION_MATRIX.md: "Auth
# for command endpoints: absent/limited"). The command Protocol's `actor`
# parameter names the target audited-command shape (ADR-005: "command/kill
# endpoints are a sensitive control surface even in paper"), but nothing
# persists it today — routes pass this placeholder rather than inventing a
# fake identity. Migrating this is tracked by the Migration Matrix's own
# "Auth for command endpoints" row, not Phase 1.
UNAUTHENTICATED_ACTOR = "unauthenticated"


class StoreBackedQueryFacade:
    """``ExecutionQueryFacade`` implementation wrapping an existing store.

    ``market_data`` is injected (Phase 6) so read routes that today compute over
    the ``MarketDataService`` port (e.g. snapshot ``pct_move``, protection status)
    can move that behind the facade. It is optional/keyword so unit tests that
    only need store-backed reads still construct ``StoreBackedQueryFacade(store)``.
    """

    def __init__(
        self, store: StateStore, *, market_data: "MarketDataService | None" = None
    ) -> None:
        self._store = store
        self._market_data = market_data

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

    async def list_external_orders(self) -> list[ExternalOrderView]:
        """External/unmanaged venue orders surfaced by reconciliation (§7 / wave
        4e). Reads the durable, deduped ``reconcile_external_order`` audit records
        — the reconcile writer already deduped them by ``broker_order_id`` — and
        maps each verbatim to an ``ExternalOrderView``. Read-only; this never
        absorbs or mutates anything. ``created_at`` is the surfacing time."""

        events = await self._store.list_events(
            event_type=EventType.RECONCILE_EXTERNAL_ORDER.value
        )
        views: list[ExternalOrderView] = []
        for e in events:
            p = e.payload or {}
            views.append(
                ExternalOrderView(
                    broker_order_id=p.get("broker_order_id"),
                    client_order_id=p.get("client_order_id"),
                    symbol=p.get("symbol"),
                    side=p.get("side"),
                    status=p.get("status"),
                    filled_quantity=p.get("filled_quantity"),
                    surfaced_at=e.created_at,
                )
            )
        return views

    async def list_position_mismatches(self) -> list[PositionMismatchView]:
        """Broker-vs-local position drifts surfaced by reconciliation (§7 / wave
        4h). Reads the durable, deduped ``reconcile_position_mismatch`` audit
        records (deduped by ``(symbol, kind)`` at write time) and maps each to a
        ``PositionMismatchView``. Position truth is never overwritten (Rule 7) —
        these are needs-review records only."""

        events = await self._store.list_events(
            event_type=EventType.RECONCILE_POSITION_MISMATCH.value
        )
        views: list[PositionMismatchView] = []
        for e in events:
            p = e.payload or {}
            views.append(
                PositionMismatchView(
                    symbol=p.get("symbol"),
                    kind=p.get("kind"),
                    local_quantity=p.get("local_quantity"),
                    broker_quantity=p.get("broker_quantity"),
                    local_avg=p.get("local_avg"),
                    broker_avg=p.get("broker_avg"),
                    surfaced_at=e.created_at,
                )
            )
        return views


class StoreBackedCommandFacade:
    """``ExecutionCommandFacade`` implementation wrapping an existing store.

    Phase 6 injects the extra collaborators the command routes need so the routes
    stop touching them directly (ADR-005): ``broker`` + ``market_data`` for the
    exit/cancel broker calls, ``approval_gate`` + ``settings`` for the candidate
    approve/reject orchestration. All are optional/keyword so a store-only unit
    test still constructs ``StoreBackedCommandFacade(store)``.
    """

    def __init__(
        self,
        store: StateStore,
        *,
        broker: "BrokerAdapter | None" = None,
        market_data: "MarketDataService | None" = None,
        approval_gate: "ApprovalGate | None" = None,
        settings: "Settings | None" = None,
    ) -> None:
        self._store = store
        self._broker = broker
        self._market_data = market_data
        self._approval_gate = approval_gate
        self._settings = settings

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
