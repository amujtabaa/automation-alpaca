"""Read-only view over the current market-data snapshots (Phase 5).

The Strategy Engine consumes ``MarketDataService`` internally (via the
strategy loop, ``app/strategy_loop.py``); this route exists only so the
cockpit can display last price / % move next to armed watchlist symbols. No
mutating endpoint here — subscriptions are driven by the watchlist's armed
state (see ``app/strategy_loop.py``'s ``_sync_subscriptions``), not by a
direct API call.

Phase 6 (ADR-005): the market-data read + ``pct_move`` computation move behind
the query facade (``list_market_snapshots`` → ``MarketSnapshotView``), so this
route no longer imports the market-data port or ``app.features``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_query_facade
from app.facade.dtos import MarketSnapshotView
from app.facade.queries import ExecutionQueryFacade

router = APIRouter(prefix="/api/marketdata", tags=["marketdata"])


@router.get("/snapshots", response_model=list[MarketSnapshotView])
async def list_snapshots(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[MarketSnapshotView]:
    return await query_facade.list_market_snapshots()
