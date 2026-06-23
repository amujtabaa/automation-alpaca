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
from app.broker.adapter import BrokerAdapter, BrokerError
from app.models import Event, Order, OrderStatus, Position
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
    return await store.get_position(symbol)


@router.get("/orders", response_model=list[Order])
async def list_orders(
    store: StateStore = Depends(get_store),
) -> list[Order]:
    return await store.list_orders()


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
    or rejected) — there is nothing to cancel. Otherwise the broker is asked to
    cancel (idempotent; skipped when the order was never submitted and so has no
    broker id), then the order transitions to ``CANCELED``.
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

    # Cancel at the broker first. A not-yet-submitted order (CREATED, no broker
    # id) has nothing at the broker to cancel — just transition it locally.
    # A genuine broker failure surfaces as 502 (upstream) with the order left
    # unchanged (still open) rather than an opaque 500 — the adapter already
    # treats an already-terminal order as an idempotent no-op, so this is a real
    # failure, not "the order was already gone".
    if order.broker_order_id is not None:
        try:
            await adapter.cancel_order(order.broker_order_id)
        except BrokerError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"broker cancel failed; order unchanged: {exc}",
            ) from exc
        except Exception as exc:  # noqa: BLE001
            # Any other adapter failure is still an upstream/broker problem: the
            # local order must be left unchanged, not transitioned. Don't rely on
            # adapters always wrapping failures in BrokerError.
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="broker cancel failed; order unchanged",
            ) from exc

    # The local transition runs only after a successful broker cancel. If it then
    # fails (a concurrent race to a terminal state), the broker order is already
    # cancelled and the next monitoring poll reconciles local state — so the 409
    # below is a transient-window response, not a durable inconsistency.

    try:
        return await store.transition_order(order_id, OrderStatus.CANCELED)
    except UnknownEntityError as exc:  # pragma: no cover - fetched above
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except OrderTransitionError as exc:
        # Raced to a terminal state between the check and the transition.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.get("/events", response_model=list[Event])
async def list_events(
    limit: Optional[int] = Query(default=None, ge=1, le=1000),
    store: StateStore = Depends(get_store),
) -> list[Event]:
    return await store.list_events(limit=limit)
