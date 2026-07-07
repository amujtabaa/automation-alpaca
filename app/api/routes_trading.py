"""Read-only views over positions, orders, and the event log.

These endpoints provide the cockpit's Position and Order monitors with live
data from the backend. Candidate views have moved to ``routes_candidates.py``
(which also owns the approve/reject endpoints). Positions remain read-only;
order creation happens via the candidate approval flow (Phase 3/4).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_broker_adapter,
    get_market_data_service,
    get_query_facade,
    get_settings,
    get_store,
)
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
from app.facade.queries import ExecutionQueryFacade
from app.api.schemas import (
    FlattenResponse,
    OperatorOrdersResponse,
    OperatorOrderView,
    OperatorRecoveryView,
    ProtectionConfigView,
    ProtectionPositionView,
    ProtectionStatusResponse,
)
from app.broker.adapter import BrokerAdapter, BrokerError
from app.config import Settings
from app.marketdata.service import MarketDataService
from app.models import (
    RECOVERY_OPEN_STATUSES,
    Event,
    Order,
    OrderStatus,
    Position,
    SellIntent,
    SubmitRecoveryRecord,
)
from app.monitoring import cancel_open_buys
from app.policy import (
    NON_TERMINAL_ORDER_STATUSES,
    finite_number_reason,
    operational_status_for,
    order_is_cancelable,
    recovery_operational_status,
)
from app.protection import ProtectionConfig, floor_breach_reason, floor_price
from app.store.base import (
    FLATTEN_FLAT,
    InvalidOrderError,
    OrderTransitionError,
    StateStore,
    UnknownEntityError,
    normalize_symbol,
)

router = APIRouter(prefix="/api", tags=["trading"])

# Order statuses that can no longer be cancelled — already resolved.
_TERMINAL_ORDER_STATUSES = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}
)


@router.get("/positions", response_model=list[Position])
async def list_positions(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[Position]:
    """Phase 1 facade migration (ADR-005): calls ``ExecutionQueryFacade.
    list_positions`` instead of the store directly. The concrete
    implementation (``app.facade.store_backed.StoreBackedQueryFacade``)
    forwards unchanged to ``StateStore.list_positions`` — see
    ``docs/SPINE_PHASE1_FACADE_REPORT.md`` for the behavior-equivalence
    proof. ``except FacadeError`` is defensive/future-proofing: this
    specific method never raises one today, but the mapping exists so a
    later facade change surfaces as a clean HTTP response rather than an
    unhandled exception.
    """
    try:
        return await query_facade.list_positions()
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.get("/positions/{symbol}", response_model=Position)
async def get_position(
    symbol: str,
    store: StateStore = Depends(get_store),
) -> Position:
    # Derived from fills; a symbol with no fills returns a flat position.
    try:
        return await store.get_position(symbol)
    except ValueError as exc:
        # normalize_symbol rejects an out-of-domain ticker (DATA-2). Surface it as
        # a clean 422 rather than a leaked 500 (matches the watchlist routes).
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/positions/{symbol}/flatten", response_model=FlattenResponse)
async def flatten_position(
    symbol: str,
    store: StateStore = Depends(get_store),
    adapter: BrokerAdapter = Depends(get_broker_adapter),
) -> FlattenResponse:
    """Manually flatten a position (Phase 7 / D-P2) — an operator-commanded full
    exit that **always works**: it bypasses the kill switch, buys-paused, and a
    closed session (§5.2), because a human getting out must never be blocked by a
    control meant to stop *new* intent.

    A THIN caller (X-001): the whole "stand down a non-live autonomous exit,
    then create + approve + dispatch a fresh MANUAL_FLATTEN" decision lives in
    ``StateStore.flatten_position`` as ONE atomic, single-lock-hold operation —
    NOT here. An earlier version of this route made that decision across
    several separate store calls (read active intent, then later create one);
    a protection tick's own intent-creation could win the single-flight race in
    the gap between them, silently handing a human's flatten a
    ``protection_floor`` intent instead (which a kill switch then holds
    unsubmitted). ``flatten_position`` closes that gap structurally — see its
    docstring in ``app/store/base.py``.

    Cancels every open BUY for the symbol first (§5.3, best-effort — this needs
    a broker call, which must never happen under the store's lock) so the exit
    reaches — and stays — flat; ``flatten_position`` re-reads the live position
    under its own lock regardless, so sizing always reflects whatever this
    achieved, never a stale read.

    * No position (flat) → ``409`` (checked before AND after the buy-cancel
      step, so a flat symbol has no side effects at all — a stray unrelated
      pending buy for a symbol with nothing to flatten is left untouched).
    * An in-flight ``MANUAL_FLATTEN`` already owns the exit → **idempotent**
      (returns it, no second order).
    * An in-flight autonomous ``PROTECTION_FLOOR`` exit whose order is not yet
      live at the broker is superseded so the human's flatten takes over; one
      already live is returned as-is (already exiting — cancel it via
      ``/orders/{id}/cancel`` first to re-issue).
    """

    try:
        key = normalize_symbol(symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    position = await store.get_position(key)
    if position.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"no open {key} position to flatten",
        )

    # §5.3: clear open buys so the exit truly reaches flat. Best-effort/
    # idempotent; a broker failure here is logged by cancel_open_buys itself
    # and does not block the flatten attempt below.
    await cancel_open_buys(store, adapter, key)

    try:
        result = await store.flatten_position(key)
    except InvalidOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    if result.outcome == FLATTEN_FLAT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"no open {key} position to flatten",
        )

    return FlattenResponse(intent=result.intent, order=result.order)


@router.get("/protection", response_model=ProtectionStatusResponse)
async def protection_status(
    store: StateStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
    market_data: MarketDataService = Depends(get_market_data_service),
) -> ProtectionStatusResponse:
    """The live Sell-Side Protection state (Phase 7), classified server-side so the
    cockpit renders it verbatim (D-020). Effective config plus, per open position:
    its hard floor, the observed last price, whether it is breaching, whether an
    autonomous exit is paused by the kill switch, whether a protective order is
    stalled (unfilled past the timeout), and any active sell intent."""

    config = ProtectionConfig(
        enabled=settings.protection_enabled,
        stop_loss_pct=settings.protection_stop_loss_pct,
        limit_buffer_pct=settings.protection_limit_buffer_pct,
    )
    session = await store.get_current_session()
    stale_order_ids = {
        e.order_id
        for e in await store.list_events(event_type="order_stale")
        if e.order_id
    }

    positions = [p for p in await store.list_positions() if p.quantity > 0]
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
        active = await store.active_sell_intent_for(position.symbol)
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
                # Frozen only when the switch is engaged AND this position would
                # otherwise be exiting (it is breaching).
                paused_by_kill_switch=session.kill_switch and breach is not None,
                stalled=stalled,
                active_sell_intent=active,
            )
        )

    return ProtectionStatusResponse(
        config=ProtectionConfigView(
            enabled=settings.protection_enabled,
            stop_loss_pct=settings.protection_stop_loss_pct,
            limit_buffer_pct=settings.protection_limit_buffer_pct,
            protection_active=settings.protection_enabled and settings.enable_monitoring,
        ),
        positions=views,
    )


@router.get("/sell-intents", response_model=list[SellIntent])
async def list_sell_intents(
    session_id: Optional[str] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
    store: StateStore = Depends(get_store),
) -> list[SellIntent]:
    """Read-only view of the sell-intent lifecycle (Phase 7). Optional
    ``session_id`` / ``symbol`` filters mirror the store method."""

    try:
        return await store.list_sell_intents(session_id=session_id, symbol=symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/orders", response_model=list[Order])
async def list_orders(
    store: StateStore = Depends(get_store),
) -> list[Order]:
    return await store.list_orders()


@router.get("/order-recoveries", response_model=list[SubmitRecoveryRecord])
async def list_order_recoveries(
    open_only: bool = Query(default=True),
    store: StateStore = Depends(get_store),
) -> list[SubmitRecoveryRecord]:
    """Read-only view of broker-submit recovery records (D-017 / F-002).

    Defaults to the *open* ones — everything still needing attention: records
    the recovery loop is actively working (``unresolved``) **and** records it has
    escalated because the broker order had fills (``needs_review`` — a real
    untracked position a human must reconcile). Both must stay visible to the
    operator; only cleanly-cancelled records (``resolved_canceled``) drop out.
    ``open_only=false`` returns the full history. This is the minimal Wave 0
    surface; a full operational-status classification endpoint is Wave 2 (D-020).
    Defined before ``/orders/{order_id}`` so the literal path isn't captured as
    an ``order_id``.
    """

    statuses = RECOVERY_OPEN_STATUSES if open_only else None
    return await store.list_submit_recoveries(statuses=statuses)


@router.get("/operator/orders", response_model=OperatorOrdersResponse)
async def operator_orders(
    store: StateStore = Depends(get_store),
) -> OperatorOrdersResponse:
    """The operator's single source of order-lifecycle truth (D-020).

    Classifies every durable non-terminal order **server-side** — its
    ``operational_status`` (``app.policy.operational_status_for``), the hold
    ``reason`` behind a ``created`` order (from that order's latest
    ``order_submission_blocked`` audit event), a ``cancelable`` flag (the same
    rule the cancel route enforces), and a ``stale`` flag (from ``order_stale``
    events) — plus every open broker-submit recovery record, so the cockpit (and
    any future UI) renders lifecycle instead of re-deriving it. Read-only: the
    raw ``/orders`` read and the ``/orders/{id}/cancel`` action are unchanged.

    Terminal orders (filled/canceled/rejected) are excluded via the same
    ``NON_TERMINAL_ORDER_STATUSES`` the CAPI exposure calc uses, so "what still
    needs an operator's eyes" is defined in exactly one place.
    """

    orders = await store.list_orders()
    non_terminal = [o for o in orders if o.status in NON_TERMINAL_ORDER_STATUSES]

    # Latest submission-block reason per order (later events overwrite earlier),
    # exactly what the cockpit used to assemble itself.
    block_reason_by_order: dict[str, str] = {}
    for event in await store.list_events(event_type="order_submission_blocked"):
        reason = (event.payload or {}).get("reason")
        if event.order_id and reason:
            block_reason_by_order[event.order_id] = reason

    stale_order_ids = {
        event.order_id
        for event in await store.list_events(event_type="order_stale")
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
        for record in await store.list_submit_recoveries(
            statuses=RECOVERY_OPEN_STATUSES
        )
    ]

    return OperatorOrdersResponse(orders=order_views, recoveries=recovery_views)


@router.get("/orders/{order_id}", response_model=Order)
async def get_order(
    order_id: str,
    store: StateStore = Depends(get_store),
) -> Order:
    order = await store.get_order(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"order {order_id} not found",
        )
    return order


@router.post("/orders/{order_id}/cancel", response_model=Order)
async def cancel_order(
    order_id: str,
    store: StateStore = Depends(get_store),
    adapter: BrokerAdapter = Depends(get_broker_adapter),
) -> Order:
    """Manually cancel an open order (D-011: human-triggered, no auto-cancel).

    404 if the order is unknown; 409 if it is already terminal (filled, canceled,
    or rejected). A cancel **request** does not immediately mark the order
    terminal: a submitted order moves to ``cancel_pending`` and stays in the
    monitoring loop's polling set until the broker confirms a terminal state — so
    a late fill arriving before the venue finalizes the cancel is still recorded
    (CHAOS-1). A never-submitted order (CREATED, no broker id) has nothing at the
    broker and is cancelled locally to ``canceled`` immediately. Re-cancelling an
    already ``cancel_pending`` order is an idempotent no-op.
    """

    order = await store.get_order(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"order {order_id} not found",
        )
    if order.status in _TERMINAL_ORDER_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"order {order_id} is already {order.status.value}; cannot cancel",
        )
    if order.status is OrderStatus.CANCEL_PENDING:
        # Cancel already requested — idempotent no-op (don't re-hit the broker).
        return order

    # A never-submitted order (CREATED, no broker id) has nothing at the broker;
    # cancel it locally and it is terminal immediately.
    if order.broker_order_id is None:
        return await _transition_cancel(store, order_id, OrderStatus.CANCELED)

    # Submitted/partially-filled: request the broker cancel, then move to
    # cancel_pending. A genuine broker failure surfaces as 502 (upstream) with the
    # order left unchanged (still open) rather than an opaque 500 — the adapter
    # already treats an already-terminal order as an idempotent no-op, so this is
    # a real failure, not "the order was already gone".
    try:
        await adapter.cancel_order(order.broker_order_id)
    except BrokerError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"broker cancel failed; order unchanged: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        # Any other adapter failure is still an upstream/broker problem: the local
        # order must be left unchanged, not transitioned. Don't rely on adapters
        # always wrapping failures in BrokerError.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="broker cancel failed; order unchanged",
        ) from exc

    # Move to cancel_pending; the loop reconciles it to a terminal state. If this
    # transition races a terminal state (a fill landed first), the 409 is a
    # transient-window response — the broker cancel is a no-op against a filled
    # order and the next poll reconciles local state.
    return await _transition_cancel(store, order_id, OrderStatus.CANCEL_PENDING)


async def _transition_cancel(
    store: StateStore, order_id: str, new_status: OrderStatus
) -> Order:
    try:
        return await store.transition_order(order_id, new_status)
    except UnknownEntityError as exc:  # pragma: no cover - fetched above
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except OrderTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("/events", response_model=list[Event])
async def list_events(
    limit: Optional[int] = Query(default=None, ge=1, le=1000),
    event_type: Optional[str] = Query(default=None),
    correlation_id: Optional[str] = Query(default=None),
    store: StateStore = Depends(get_store),
) -> list[Event]:
    """``correlation_id`` (D-020) returns the complete lifecycle of one
    candidate OR one sell intent (X-004) — creation, approval, order creation,
    claim, submission, blocked/recovery, fills, and transitions — in one
    query, for incident reconstruction."""

    return await store.list_events(
        limit=limit, event_type=event_type, correlation_id=correlation_id
    )
