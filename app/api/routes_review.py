"""Daily review — query a session (the current one, or a past date).

Serves the across-days history requirement: history persists, and a past
session is queryable by date. With no data yet, this returns the session (if one
exists for that date) plus empty lists — a real empty state, not mock data.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_store
from app.api.schemas import ReviewResponse
from app.models import utcnow
from app.store.base import StateStore

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/review", response_model=ReviewResponse)
async def review(
    date: Optional[date_cls] = Query(
        default=None, description="Session date (YYYY-MM-DD); defaults to today"
    ),
    store: StateStore = Depends(get_store),
) -> ReviewResponse:
    target = date or utcnow().date()
    session = await store.get_session_by_date(target)

    if session is None:
        return ReviewResponse(
            date=target.isoformat(),
            session=None,
            candidates=[],
            orders=[],
            fills=[],
            positions=[],
            events=[],
        )

    candidates = await store.list_candidates(session_id=session.id)
    orders = await store.list_orders(session_id=session.id)
    events = await store.list_events(session_id=session.id)
    # Fills/positions are derived from the append-only fill history. Positions
    # carry forward across sessions (they are not date-scoped), so the current
    # derived view is returned.
    positions = await store.list_positions()
    fills = await store.list_fills()

    return ReviewResponse(
        date=target.isoformat(),
        session=session,
        candidates=candidates,
        orders=orders,
        fills=fills,
        positions=positions,
        events=events,
    )
