"""Read-only views over candidates, orders, positions, and the event log.

These endpoints exist now so the cockpit's Candidate/Position monitors render
against *real* (currently empty) backend data, not mock data. Nothing here
creates candidates or orders — that's Phase 3/4. There is deliberately no
approve/reject or flatten endpoint yet (out of scope; both require logic this
phase does not build).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_store
from app.models import Candidate, Event, Order, Position
from app.store.base import StateStore

router = APIRouter(prefix="/api", tags=["trading"])


@router.get("/candidates", response_model=list[Candidate])
async def list_candidates(
    store: StateStore = Depends(get_store),
) -> list[Candidate]:
    return await store.list_candidates()


@router.get("/candidates/{candidate_id}", response_model=Candidate)
async def get_candidate(
    candidate_id: str,
    store: StateStore = Depends(get_store),
) -> Candidate:
    candidate = await store.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"candidate {candidate_id} not found",
        )
    return candidate


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
