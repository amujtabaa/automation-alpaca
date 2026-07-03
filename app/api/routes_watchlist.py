"""Watchlist CRUD — the input the rest of the system is driven from.

The armed subset of this list is what the Strategy Engine (Phase 5) evaluates
and the Market Data Service subscribes to (`docs/01_ARCHITECTURE.md`); it is
the only entity with a mutating create/update/delete surface here, since
candidates/orders/positions are all produced downstream (by approval,
submission, and fills respectively) rather than directly authored.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_store
from app.api.schemas import WatchlistCreate
from app.models import WatchlistSymbol
from app.store.base import StateStore

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistSymbol])
async def list_watchlist(
    store: StateStore = Depends(get_store),
) -> list[WatchlistSymbol]:
    return await store.list_watchlist()


@router.post("", response_model=WatchlistSymbol, status_code=status.HTTP_201_CREATED)
async def add_or_update_watchlist(
    body: WatchlistCreate,
    store: StateStore = Depends(get_store),
) -> WatchlistSymbol:
    """Upsert a symbol.

    * Absent  -> created with the requested ``armed`` state.
    * Present -> ``armed`` is set to the requested value (this is how the UI
      arms/disarms, keeping to the POST/GET/DELETE surface).
    """

    try:
        existing = await store.get_watchlist_symbol(body.symbol)
        if existing is None:
            return await store.add_watchlist_symbol(body.symbol, armed=body.armed)
        if existing.armed != body.armed:
            return await store.set_watchlist_armed(body.symbol, body.armed)
        return existing
    except ValueError as exc:
        # normalize_symbol rejects a blank/out-of-domain ticker (DATA-2). Surface
        # it as a clean 422, not a 500.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watchlist(
    symbol: str,
    store: StateStore = Depends(get_store),
) -> None:
    try:
        removed = await store.remove_watchlist_symbol(symbol)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"symbol {symbol} not on watchlist",
        )
    return None
