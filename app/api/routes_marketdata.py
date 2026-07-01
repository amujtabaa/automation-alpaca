"""Read-only view over the current market-data snapshots (Phase 5).

The Strategy Engine consumes ``MarketDataService`` internally (via the
strategy loop, ``app/strategy_loop.py``); this route exists only so the
cockpit can display last price / % move next to armed watchlist symbols. No
mutating endpoint here — subscriptions are driven by the watchlist's armed
state (see ``app/strategy_loop.py``'s ``_sync_subscriptions``), not by a
direct API call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_market_data_service
from app.api.schemas import MarketSnapshotResponse
from app.marketdata.service import MarketDataService

router = APIRouter(prefix="/api/marketdata", tags=["marketdata"])


@router.get("/snapshots", response_model=list[MarketSnapshotResponse])
async def list_snapshots(
    market_data: MarketDataService = Depends(get_market_data_service),
) -> list[MarketSnapshotResponse]:
    snapshots = await market_data.list_snapshots()
    return [MarketSnapshotResponse(**s.__dict__) for s in snapshots]
