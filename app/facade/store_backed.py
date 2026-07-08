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

from datetime import date as date_cls

from app.facade.dtos import (
    ExternalOrderView,
    MarketSnapshotView,
    OperatorOrdersResponse,
    OperatorOrderView,
    OperatorRecoveryView,
    PositionMismatchView,
    ProtectionConfigView,
    ProtectionPositionView,
    ProtectionStatusResponse,
    ReviewView,
)
from app.facade.errors import (
    ConflictError,
    EntityNotFoundError,
    InvalidInputError,
    NotYetImplementedError,
)
from app.features import pct_move, session_type_for
from app.models import (
    RECOVERY_OPEN_STATUSES,
    Candidate,
    CandidateStatus,
    Event,
    EventType,
    Order,
    OrderStatus,
    Position,
    SellIntent,
    SessionRecord,
    SessionStatus,
    SubmitRecoveryRecord,
    TradingState,
    WatchlistSymbol,
    utcnow,
)
from app.policy import (
    NON_TERMINAL_ORDER_STATUSES,
    finite_number_reason,
    limit_price_reason,
    operational_status_for,
    order_intent_block_reason,
    order_is_cancelable,
    recovery_operational_status,
    risk_limit_reason,
)
from app.protection import ProtectionConfig, floor_breach_reason, floor_price
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
    RiskLimits,
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

# The store/gate errors the candidate approve/reject flow translates to HTTP —
# mirrors the old route's ``_MAPPED_ERRORS`` (anything else is a genuine bug → 500).
_APPROVE_MAPPED_ERRORS = (
    UnknownEntityError,
    CandidateTransitionError,
    InvalidOrderError,
    OrderIntentBlockedError,
    RiskLimitBlockedError,
)


def _facade_error_for(exc: Exception) -> "ConflictError | EntityNotFoundError | InvalidInputError":
    """Map a known store ``StoreError`` (or ``normalize_symbol``'s ``ValueError``)
    to its status-carrying facade error, BY SEMANTIC KIND — the single source of
    truth for the 404/409/422 policy (see ``app.facade.errors``). Callers that
    must run cleanup (e.g. the approve flow's revert-on-failure) call this
    directly; the ``_translate_store_errors`` context manager wraps it for the
    common no-cleanup case."""

    if isinstance(exc, UnknownEntityError):
        return EntityNotFoundError(str(exc))
    if isinstance(exc, _CONFLICT_STORE_ERRORS):
        return ConflictError(str(exc))
    # InvalidControlValueError / InvalidStatusError / ValueError
    return InvalidInputError(str(exc))


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
    except (
        UnknownEntityError,
        *_CONFLICT_STORE_ERRORS,
        *_INVALID_INPUT_STORE_ERRORS,
        ValueError,
    ) as exc:
        raise _facade_error_for(exc) from exc

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
    can move that behind the facade. ``settings`` is injected (P6d) for the same
    reason ``protection_status`` needs the effective ``ProtectionConfig``. Both are
    optional/keyword so unit tests that only need store-backed reads still
    construct ``StoreBackedQueryFacade(store)``.
    """

    def __init__(
        self,
        store: StateStore,
        *,
        market_data: "MarketDataService | None" = None,
        settings: "Settings | None" = None,
    ) -> None:
        self._store = store
        self._market_data = market_data
        self._settings = settings

    async def list_positions(self) -> list[Position]:
        """Unchanged wrap of ``StateStore.list_positions`` — the exact call
        ``GET /api/positions`` made directly before this facade existed."""
        return await self._store.list_positions()

    async def list_watchlist(self) -> list[WatchlistSymbol]:
        """Wrap of ``StateStore.list_watchlist`` — ``GET /api/watchlist`` (P6a)."""
        return await self._store.list_watchlist()

    async def list_market_snapshots(self) -> list[MarketSnapshotView]:
        """``GET /api/marketdata/snapshots`` (P6a): read the current per-symbol
        snapshots off the injected ``MarketDataService`` port and attach
        ``pct_move`` (same ``app.features`` function the Strategy Engine uses), so
        the route no longer imports ``app.features`` or the market-data port."""
        if self._market_data is None:  # always injected in the real app (lifespan)
            raise RuntimeError("market data service not available")
        snapshots = await self._market_data.list_snapshots()
        return [
            MarketSnapshotView(
                symbol=s.symbol,
                last_price=s.last_price,
                bid=s.bid,
                ask=s.ask,
                volume=s.volume,
                prev_close=s.prev_close,
                pct_move=pct_move(s.last_price, s.prev_close),
                updated_at=s.updated_at,
                stale=s.stale,
            )
            for s in snapshots
        ]

    async def get_current_session_view(self) -> SessionRecord:
        """``GET /api/session`` (P6b): the current session with ``session_type``
        overlaid live from ``session_type_for(utcnow())`` — the same Feature
        Engine classification the Strategy Engine uses — rather than the stored
        value, since a day's session spans all three windows as time passes. Moves
        the ``app.features`` overlay behind the facade so the route drops it."""
        record = await self._store.get_current_session()
        return record.model_copy(update={"session_type": session_type_for(utcnow())})

    async def get_review(self, *, target_date: date_cls) -> ReviewView:
        """``GET /api/review`` (P6b): the full session review for ``target_date``.
        Owns the multi-read AND the D-012 closed-vs-active point-in-time branch —
        a CLOSED session returns the position snapshot captured at close (NOT a
        live re-fold, which a post-close fill would diverge), an active one the
        live derived positions. Behavior copied verbatim from the old route."""
        session = await self._store.get_session_by_date(target_date)
        if session is None:
            return ReviewView(
                date=target_date.isoformat(),
                session=None,
                candidates=[],
                orders=[],
                fills=[],
                positions=[],
                events=[],
            )
        candidates = await self._store.list_candidates(session_id=session.id)
        orders = await self._store.list_orders(session_id=session.id)
        events = await self._store.list_events(session_id=session.id)
        fills = await self._store.list_fills(session_id=session.id)
        sell_intents = await self._store.list_sell_intents(session_id=session.id)
        if session.status is SessionStatus.CLOSED:
            snapshots = await self._store.list_position_snapshots(session.id)
            positions = [
                Position(
                    symbol=s.symbol,
                    quantity=s.quantity,
                    cost_basis=s.cost_basis,
                    average_price=s.average_price,
                    updated_at=s.captured_at,
                )
                for s in snapshots
            ]
        else:
            positions = await self._store.list_positions()
        return ReviewView(
            date=target_date.isoformat(),
            session=session,
            candidates=candidates,
            orders=orders,
            fills=fills,
            positions=positions,
            events=events,
            sell_intents=sell_intents,
        )

    async def list_candidates(self) -> list[Candidate]:
        """``GET /api/candidates`` (P6c): candidates scoped to the active
        session (the facade owns the get_current_session → list_candidates
        two-call sequence)."""
        session = await self._store.get_current_session()
        return await self._store.list_candidates(session_id=session.id)

    async def get_candidate(self, *, candidate_id: str) -> Candidate:
        """``GET /api/candidates/{id}`` (P6c): a single candidate; 404 if absent."""
        candidate = await self._store.get_candidate(candidate_id)
        if candidate is None:
            raise EntityNotFoundError(f"candidate {candidate_id} not found")
        return candidate

    async def get_position(self, *, symbol: str) -> Position:
        """``GET /api/positions/{symbol}`` (P6d): derived from fills; a symbol
        with no fills returns a flat position. An out-of-domain ticker
        (``normalize_symbol``'s ``ValueError``) becomes a 422."""
        with _translate_store_errors():
            return await self._store.get_position(symbol)

    async def list_sell_intents(
        self, *, session_id: Optional[str] = None, symbol: Optional[str] = None
    ) -> list[SellIntent]:
        """``GET /api/sell-intents`` (P6d): read-only view of the sell-intent
        lifecycle (Phase 7). Optional ``session_id``/``symbol`` filters mirror
        the store method; an out-of-domain ticker → 422."""
        with _translate_store_errors():
            return await self._store.list_sell_intents(
                session_id=session_id, symbol=symbol
            )

    async def list_orders(self) -> list[Order]:
        """``GET /api/orders`` (P6d): unchanged wrap of ``StateStore.list_orders``."""
        return await self._store.list_orders()

    async def list_submit_recoveries(
        self, *, open_only: bool = True
    ) -> list[SubmitRecoveryRecord]:
        """``GET /api/order-recoveries`` (P6d): read-only view of broker-submit
        recovery records (D-017 / F-002). Defaults to the *open* ones — records
        the recovery loop is actively working (``unresolved``) **and** records
        it has escalated because the broker order had fills (``needs_review`` —
        a real untracked position a human must reconcile). ``open_only=False``
        returns the full history."""
        statuses = RECOVERY_OPEN_STATUSES if open_only else None
        return await self._store.list_submit_recoveries(statuses=statuses)

    async def get_order(self, *, order_id: str) -> Order:
        """``GET /api/orders/{order_id}`` (P6d): a single order; 404 if absent."""
        order = await self._store.get_order(order_id)
        if order is None:
            raise EntityNotFoundError(f"order {order_id} not found")
        return order

    async def list_events(
        self,
        *,
        limit: Optional[int] = None,
        event_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> list[Event]:
        """``GET /api/events`` (P6d): unchanged wrap of ``StateStore.list_events``.
        ``correlation_id`` (D-020) returns the complete lifecycle of one
        candidate OR one sell intent (X-004) in one query, for incident
        reconstruction."""
        return await self._store.list_events(
            limit=limit, event_type=event_type, correlation_id=correlation_id
        )

    async def operator_orders(self) -> OperatorOrdersResponse:
        """``GET /api/operator/orders`` (P6d): the operator's single source of
        order-lifecycle truth (D-020), moved verbatim from the old route.

        Classifies every durable non-terminal order — its ``operational_status``
        (``app.policy.operational_status_for``), the hold ``reason`` behind a
        ``created`` order (from that order's latest ``order_submission_blocked``
        audit event), a ``cancelable`` flag (the same rule the cancel route
        enforces), and a ``stale`` flag (from ``order_stale`` events) — plus
        every open broker-submit recovery record. Terminal orders
        (filled/canceled/rejected) are excluded via the same
        ``NON_TERMINAL_ORDER_STATUSES`` the CAPI exposure calc uses.
        """
        orders = await self._store.list_orders()
        non_terminal = [o for o in orders if o.status in NON_TERMINAL_ORDER_STATUSES]

        # Latest submission-block reason per order (later events overwrite
        # earlier), exactly what the cockpit used to assemble itself.
        block_reason_by_order: dict[str, str] = {}
        for event in await self._store.list_events(
            event_type="order_submission_blocked"
        ):
            reason = (event.payload or {}).get("reason")
            if event.order_id and reason:
                block_reason_by_order[event.order_id] = reason

        stale_order_ids = {
            event.order_id
            for event in await self._store.list_events(event_type="order_stale")
            if event.order_id
        }

        order_views = [
            OperatorOrderView(
                order=order,
                operational_status=operational_status_for(
                    order.status, block_reason_by_order.get(order.id)
                ),
                # The hold reason is only meaningful while the order is still
                # CREATED (held); once claimed/submitted the status is the truth.
                reason=(
                    block_reason_by_order.get(order.id)
                    if order.status is OrderStatus.CREATED
                    else None
                ),
                cancelable=order_is_cancelable(order.status),
                stale=order.id in stale_order_ids,
            )
            for order in non_terminal
        ]

        recovery_views = [
            OperatorRecoveryView(
                record=record,
                operational_status=recovery_operational_status(record.cleanup_status),
                reason=record.failure_reason,
            )
            for record in await self._store.list_submit_recoveries(
                statuses=RECOVERY_OPEN_STATUSES
            )
        ]

        return OperatorOrdersResponse(orders=order_views, recoveries=recovery_views)

    async def protection_status(self) -> ProtectionStatusResponse:
        """``GET /api/protection`` (P6d): the live Sell-Side Protection state
        (Phase 7), classified server-side so the cockpit renders it verbatim
        (D-020), moved verbatim from the old route. Effective config plus, per
        open position: its hard floor, the observed last price, whether it is
        breaching, whether an autonomous exit is paused by the kill switch,
        whether a protective order is stalled (unfilled past the timeout), and
        any active sell intent."""
        if self._market_data is None or self._settings is None:
            raise RuntimeError("market data service / settings not available")
        market_data = self._market_data
        settings = self._settings

        config = ProtectionConfig(
            enabled=settings.protection_enabled,
            stop_loss_pct=settings.protection_stop_loss_pct,
            limit_buffer_pct=settings.protection_limit_buffer_pct,
        )
        session = await self._store.get_current_session()
        stale_order_ids = {
            e.order_id
            for e in await self._store.list_events(event_type="order_stale")
            if e.order_id
        }

        positions = [p for p in await self._store.list_positions() if p.quantity > 0]
        views: list[ProtectionPositionView] = []
        for position in positions:
            snapshot = await market_data.get_snapshot(position.symbol)
            breach = floor_breach_reason(position, snapshot, config)
            avg = position.average_price
            floor = (
                floor_price(avg, config.stop_loss_pct)
                if avg is not None
                and finite_number_reason(avg) is None
                and avg > 0
                else None
            )
            observed = None
            if snapshot is not None and not snapshot.stale:
                last = snapshot.last_price
                if finite_number_reason(last) is None and last > 0:
                    observed = last
            active = await self._store.active_sell_intent_for(position.symbol)
            stalled = (
                active is not None
                and active.order_id is not None
                and active.order_id in stale_order_ids
            )
            views.append(
                ProtectionPositionView(
                    symbol=position.symbol,
                    quantity=position.quantity,
                    average_price=avg,
                    floor_price=floor,
                    observed_price=observed,
                    breaching=breach is not None,
                    # Frozen only when the switch is engaged AND this position
                    # would otherwise be exiting (it is breaching). Wave 3d: reads
                    # the §8 FSM (HALTED == kill-switched) to stay consistent with
                    # the monitoring loop's enforcement; equivalent to the prior
                    # boolean.
                    paused_by_kill_switch=(
                        session.trading_state is TradingState.HALTED
                        and breach is not None
                    ),
                    stalled=stalled,
                    active_sell_intent=active,
                )
            )

        return ProtectionStatusResponse(
            config=ProtectionConfigView(
                enabled=settings.protection_enabled,
                stop_loss_pct=settings.protection_stop_loss_pct,
                limit_buffer_pct=settings.protection_limit_buffer_pct,
                protection_active=settings.protection_enabled
                and settings.enable_monitoring,
            ),
            positions=views,
        )

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

    async def upsert_watchlist_symbol(
        self, *, symbol: str, armed: bool, actor: str
    ) -> WatchlistSymbol:
        """``POST /api/watchlist`` upsert (P6a): create the symbol with the
        requested ``armed`` state, else set ``armed`` to it. Preserves the route's
        exact read-then-write semantics; an out-of-domain ticker (``ValueError``)
        becomes an ``InvalidInputError`` (422)."""
        with _translate_store_errors():
            existing = await self._store.get_watchlist_symbol(symbol)
            if existing is None:
                return await self._store.add_watchlist_symbol(symbol, armed=armed)
            if existing.armed != armed:
                return await self._store.set_watchlist_armed(symbol, armed)
            return existing

    async def remove_watchlist_symbol(self, *, symbol: str, actor: str) -> None:
        """``DELETE /api/watchlist/{symbol}`` (P6a): remove the symbol. An
        out-of-domain ticker → 422; a symbol not on the list →
        ``EntityNotFoundError`` (404), matching the route."""
        with _translate_store_errors():
            removed = await self._store.remove_watchlist_symbol(symbol)
        if not removed:
            raise EntityNotFoundError(f"symbol {symbol} not on watchlist")

    async def inject_mock_candidate(
        self,
        *,
        symbol: str,
        strategy: str,
        reason: str,
        suggested_quantity: Optional[int],
        suggested_limit_price: Optional[float],
        actor: str,
    ) -> Candidate:
        """``POST /api/dev/candidates`` (P6a, dev-only): inject a pending
        candidate into the active session. Refuses a closed session (409, the
        route's explicit message) and maps a bad symbol ``ValueError`` → 422."""
        session = await self._store.get_current_session()
        if session.status is SessionStatus.CLOSED:
            raise ConflictError("session is closed; cannot inject candidates")
        with _translate_store_errors():
            return await self._store.create_candidate(
                symbol,
                strategy=strategy,
                reason=reason,
                suggested_quantity=suggested_quantity,
                suggested_limit_price=suggested_limit_price,
            )

    async def approve_candidate(self, *, candidate_id: str, actor: str) -> Candidate:
        """``POST /api/candidates/{id}/approve`` (P6c): the BUY dispatch flow —
        approve the candidate through the gate, then create its order atomically,
        reverting the approval on ANY post-approval dispatch failure so a
        candidate is never stranded ``APPROVED`` with no order (F-002 / D-013).

        Behavior copied verbatim from the old route: dispatchability pre-check
        (422), Rule-8 order-intent pre-check (409), CAPI risk-limit pre-check
        (409) — all skipped for an already-ORDERED candidate (idempotent
        re-approve) — then gate.approve + create_order_for_candidate, with
        revert-on-failure. The store's ``create_order_for_candidate`` remains the
        AUTHORITATIVE risk check (D-016); the pre-checks are for clean UX.
        """
        if self._approval_gate is None or self._settings is None:
            raise RuntimeError("approval gate / settings not available")
        gate = self._approval_gate
        settings = self._settings

        candidate = await self._store.get_candidate(candidate_id)
        if candidate is None:
            raise EntityNotFoundError(f"candidate {candidate_id} not found")

        # Dispatchability pre-check — a candidate that can't be sized into a valid
        # LIMIT order is refused up front (422) and stays PENDING (still
        # rejectable) rather than approved into a dead end. Uses the SAME
        # limit_price_reason predicate the store's authoritative check uses (an inf
        # price passes `inf > 0` but is rejected here — F-005/F-002). Skipped for
        # an already-ORDERED candidate (re-approve is an idempotent no-op).
        if candidate.status is not CandidateStatus.ORDERED and (
            not candidate.suggested_quantity
            or candidate.suggested_quantity <= 0
            or limit_price_reason(candidate.suggested_limit_price) is not None
        ):
            raise InvalidInputError(
                f"candidate {candidate_id} cannot be ordered: a positive "
                f"suggested_quantity and a valid positive suggested_limit_price "
                f"are required"
            )

        risk_limits = RiskLimits(
            max_shares_per_order=settings.capi_max_shares_per_order,
            max_notional_per_order=settings.capi_max_notional_per_order,
            max_total_exposure=settings.capi_max_total_exposure,
            allowlist=settings.capi_trading_allowlist,
        )
        if candidate.status is not CandidateStatus.ORDERED:
            # Rule-8 safety-control pre-check (kill switch / buys paused) — surface
            # a clean 409 with the candidate left PENDING instead of stranding it.
            block = order_intent_block_reason(await self._store.get_current_session())
            if block is not None:
                raise ConflictError(f"order intent blocked: {block}")
            # CAPI risk-limit pre-check (D-016) — mirrors the authoritative store
            # check exactly (same predicate + risk_limits). current_exposure() is
            # one atomic snapshot, so no torn read between two store calls.
            risk_block = risk_limit_reason(
                symbol=candidate.symbol,
                order_quantity=candidate.suggested_quantity,
                order_limit_price=candidate.suggested_limit_price,
                exposure_before_order=await self._store.current_exposure(),
                max_shares_per_order=risk_limits.max_shares_per_order,
                max_notional_per_order=risk_limits.max_notional_per_order,
                max_total_exposure=risk_limits.max_total_exposure,
                allowlist=risk_limits.allowlist,
            )
            if risk_block is not None:
                raise ConflictError(f"risk limit blocked: {risk_block}")

        try:
            await gate.approve(candidate_id)
            await self._store.create_order_for_candidate(
                candidate_id, risk_limits=risk_limits
            )
        except _APPROVE_MAPPED_ERRORS as exc:
            # ANY post-approval dispatch failure reverts the approval to PENDING
            # (F-002 / D-013 race): OrderIntentBlocked/RiskLimitBlocked from a
            # control/limit that changed between the pre-check and the handoff, or
            # an InvalidOrderError that slipped a pre-check. revert is a guaranteed
            # no-op unless the candidate is genuinely stranded APPROVED-with-no-order
            # — so it is also safe when the failure came from gate.approve() itself
            # (the candidate never reached APPROVED).
            await self._store.revert_candidate_approval(candidate_id)
            raise _facade_error_for(exc) from exc

        refreshed = await self._store.get_candidate(candidate_id)
        assert refreshed is not None  # fetched above; candidates are never deleted
        return refreshed

    async def reject_candidate(self, *, candidate_id: str, actor: str) -> Candidate:
        """``POST /api/candidates/{id}/reject`` (P6c): reject through the gate
        (idempotent; terminal — no order). Maps the gate's store errors (404/409)."""
        if self._approval_gate is None:
            raise RuntimeError("approval gate not available")
        try:
            return await self._approval_gate.reject(candidate_id)
        except _APPROVE_MAPPED_ERRORS as exc:
            raise _facade_error_for(exc) from exc

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

    async def set_kill_switch(self, *, engaged: bool, actor: str) -> SessionRecord:
        """``POST /api/controls/kill-switch`` (P6b): wrap of
        ``StateStore.set_kill_switch``. The wave-3d TradingState FSM already made
        this event_truth (first-writes a ``TRADING_STATE_CHANGED`` event, folds to
        ``Halted``), so this is a pure boundary move — the Phase-1 deferral (freeze
        binary-flag semantics before the TradingState decision) is resolved. A
        non-bool (guarded by the route's ``StrictBool`` body) → 422."""
        with _translate_store_errors():
            return await self._store.set_kill_switch(engaged)

    async def close_session(self, *, actor: str) -> SessionRecord:
        """``POST /api/session/close`` (P6b): wrap of ``StateStore.close_session``
        (expire open candidates, cancel CREATED orders, snapshot positions, mark
        closed). Re-closing an already-closed session → 409
        (``SessionAlreadyClosedError`` → ``ConflictError``)."""
        with _translate_store_errors():
            return await self._store.close_session()

    async def emergency_reduce_override(self, *, symbol: str, actor: str) -> Any:
        raise NotYetImplementedError(
            "emergency_reduce_override: has no current-codebase analogue; "
            "Phase 3 scope (ADR-003)"
        )
