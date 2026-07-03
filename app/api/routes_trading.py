"""Read-only views over positions, orders, and the event log.

These endpoints provide the cockpit's Position and Order monitors with live
data from the backend. Candidate views have moved to ``routes_candidates.py``
(which also owns the approve/reject endpoints). Positions remain read-only;
order creation happens via the candidate approval flow (Phase 3/4).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_broker_adapter, get_store
from app.api.schemas import (
    OperatorOrdersResponse,
    OperatorOrderView,
    OperatorRecoveryView,
)
from app.broker.adapter import BrokerAdapter, BrokerError
from app.models import (
    RECOVERY_OPEN_STATUSES,
    Event,
    Order,
    OrderStatus,
    Position,
    SubmitRecoveryRecord,
)
from app.policy import (
    NON_TERMINAL_ORDER_STATUSES,
    operational_status_for,
    order_is_cancelable,
    recovery_operational_status,
)
from app.store.base import (
    OrderTransitionError,
    StateStore,
    UnknownEntityError,
)

router = APIRouter(prefix="/api", tags=["trading"])

# Order statuses that can no longer be cancelled — already resolved.
_TERMINAL_ORDER_STATUSES = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}
)


@router.get("/positions", response_model=list[Position])
async def list_positions(
    store: StateStore = Depends(get_store),
) -> list[Position]:
    return await store.list_positions()


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
    store: StateStore = Depends(get_store),
) -> list[Event]:
    return await store.list_events(limit=limit, event_type=event_type)
