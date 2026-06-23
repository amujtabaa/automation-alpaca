"""Read-only views over positions, orders, and the event log.

These endpoints provide the cockpit's Position and Order monitors with live
data from the backend. Candidate views have moved to ``routes_candidates.py``
(which also owns the approve/reject endpoints). Positions remain read-only;
order creation happens via the candidate approval flow (Phase 3/4).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_store
from app.models import Event, Order, Position
from app.store.base import StateStore

router = APIRouter(prefix="/api", tags=["trading"])


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


@router.get("/events", response_model=list[Event])
async def list_events(
    limit: Optional[int] = Query(default=None, ge=1, le=1000),
    store: StateStore = Depends(get_store),
) -> list[Event]:
    return await store.list_events(limit=limit)
