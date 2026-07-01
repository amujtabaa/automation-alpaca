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
from app.models import Position, SessionStatus, utcnow
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
    # Fills are scoped to this session directly (D-007), not returned in full
    # regardless of date.
    fills = await store.list_fills(session_id=session.id)

    if session.status is SessionStatus.CLOSED:
        # Point-in-time: return the snapshot captured at close, not today's live
        # fold over the full fill history. Per D-012 this is intended: a fill that
        # lands after close (e.g. a cancel_pending order completing post-close,
        # D-011) updates the live position but is NOT retro-applied to the frozen
        # snapshot, so a closed day's review can legitimately differ from the
        # order's final filled quantity. Do not "fix" this divergence here.
        snapshots = await store.list_position_snapshots(session.id)
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
        # Active session: the live derived view, same as before.
        positions = await store.list_positions()

    return ReviewResponse(
        date=target.isoformat(),
        session=session,
        candidates=candidates,
        orders=orders,
        fills=fills,
        positions=positions,
        events=events,
    )
