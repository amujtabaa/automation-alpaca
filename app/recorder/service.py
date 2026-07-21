"""Read-only recorder service built solely on the MarketDataService port."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime

from app.marketdata.service import MarketDataService
from app.recorder.models import TapeRecord
from app.recorder.store import TapeStore


class TapeRecorder:
    """Capture snapshot observations without a broker adapter or execution store."""

    def __init__(
        self,
        *,
        market_data: MarketDataService,
        store: TapeStore,
        enabled: bool,
        clock: Callable[[], datetime],
    ) -> None:
        self._market_data = market_data
        self._store = store
        self._enabled = enabled
        self._clock = clock

    async def capture_once(self) -> list[TapeRecord]:
        """Append every current snapshot, retaining invalid observations verbatim."""
        if not self._enabled:
            return []
        observed_at = self._clock()
        records = [
            TapeRecord.capture(snapshot, observed_at=observed_at)
            for snapshot in await self._market_data.list_snapshots()
        ]
        for record in records:
            self._store.append(record)
        return records

    async def capture_forever(self, interval_seconds: float) -> None:
        """Poll the already-running market-data feed until the task is cancelled."""
        while True:
            await self.capture_once()
            await asyncio.sleep(interval_seconds)
