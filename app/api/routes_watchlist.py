"""Watchlist CRUD — the input the rest of the system is driven from.

The armed subset of this list is what the Strategy Engine (Phase 5) evaluates
and the Market Data Service subscribes to (`docs/01_ARCHITECTURE.md`); it is
the only entity with a mutating create/update/delete surface here, since
candidates/orders/positions are all produced downstream (by approval,
submission, and fills respectively) rather than directly authored.

Phase 6 (ADR-005): the routes reach the store only through the typed facade —
they no longer import ``app.store``. Domain errors are surfaced by the facade as
``FacadeError`` subclasses and mapped to HTTP here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_actor, get_command_facade, get_query_facade
from app.api.schemas import WatchlistCreate
from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
from app.facade.queries import ExecutionQueryFacade
from app.models import WatchlistSymbol

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistSymbol])
async def list_watchlist(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[WatchlistSymbol]:
    return await query_facade.list_watchlist()


@router.post("", response_model=WatchlistSymbol, status_code=status.HTTP_201_CREATED)
async def add_or_update_watchlist(
    body: WatchlistCreate,
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> WatchlistSymbol:
    """Upsert a symbol.

    * Absent  -> created with the requested ``armed`` state.
    * Present -> ``armed`` is set to the requested value (this is how the UI
      arms/disarms, keeping to the POST/GET/DELETE surface).

    An out-of-domain ticker (``normalize_symbol``, DATA-2) surfaces as a 422 via
    the facade's ``InvalidInputError``.
    """

    try:
        return await command_facade.upsert_watchlist_symbol(
            symbol=body.symbol, armed=body.armed, actor=actor
        )
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.delete("/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watchlist(
    symbol: str,
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> None:
    try:
        await command_facade.remove_watchlist_symbol(symbol=symbol, actor=actor)
    except FacadeError as exc:
        # 422 on an invalid ticker, 404 when the symbol was not on the list.
        raise facade_error_to_http(exc) from exc
    return None
