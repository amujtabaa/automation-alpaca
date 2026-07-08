"""Daily review — query a session (the current one, or a past date).

Serves the across-days history requirement: history persists, and a past
session is queryable by date. With no data yet, this returns the session (if one
exists for that date) plus empty lists — a real empty state, not mock data.

Phase 6 (ADR-005): the multi-read and the D-012 closed-vs-active point-in-time
branching move behind the query facade (``get_review`` → ``ReviewView``); this
route just maps the view to the ``ReviewResponse`` HTTP schema and no longer
imports ``app.store``.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_query_facade
from app.api.schemas import ReviewResponse
from app.facade.queries import ExecutionQueryFacade
from app.models import utcnow

router = APIRouter(prefix="/api", tags=["review"])


@router.get("/review", response_model=ReviewResponse)
async def review(
    date: Optional[date_cls] = Query(
        default=None, description="Session date (YYYY-MM-DD); defaults to today"
    ),
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> ReviewResponse:
    target = date or utcnow().date()
    view = await query_facade.get_review(target_date=target)
    return ReviewResponse(
        date=view.date,
        session=view.session,
        candidates=view.candidates,
        orders=view.orders,
        fills=view.fills,
        positions=view.positions,
        events=view.events,
        sell_intents=view.sell_intents,
    )
