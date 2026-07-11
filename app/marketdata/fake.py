"""A fully controllable, in-memory ``MarketDataService`` for unit tests (Rule 9).

It makes no network calls and imports no SDK. Tests drive it explicitly:

* ``subscribe``/``unsubscribe`` behave like the real feed (idempotent, snapshot
  created/dropped) and are recorded for interaction assertions.
* ``set_snapshot`` lets a test set exact field values for a symbol in one call
  (auto-subscribing it if not already), mirroring ``MockBrokerAdapter.set_response``.
* ``set_previous_close`` seeds the reference price a later ``subscribe`` will
  use, and patches any already-subscribed symbol's live snapshot.
* ``run``/``stop`` are a controllable connection-lifecycle stand-in: ``run``
  blocks until ``stop`` is called (or the task is cancelled), so app-wiring /
  shutdown tests can exercise the same start/cancel/await pattern as the real
  feed without a network connection.
"""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime
from typing import Optional

from app.marketdata.service import MarketDataService, MarketSnapshot
from app.models import utcnow


class FakeMarketDataFeed(MarketDataService):
    def __init__(self) -> None:
        self._snapshots: dict[str, MarketSnapshot] = {}
        self._prev_closes: dict[str, float] = {}
        self._stop_event = asyncio.Event()

        # Recorded calls, for interaction assertions.
        self.subscribe_calls: list[list[str]] = []
        self.unsubscribe_calls: list[list[str]] = []
        self.run_started = False
        self.stopped = False

    # ------------------------------------------------------------------ #
    # MarketDataService
    # ------------------------------------------------------------------ #
    async def subscribe(self, symbols: list[str]) -> None:
        self.subscribe_calls.append(list(symbols))
        for symbol in symbols:
            if symbol in self._snapshots:
                continue
            self._snapshots[symbol] = MarketSnapshot(
                symbol=symbol,
                last_price=None,
                bid=None,
                ask=None,
                volume=None,
                prev_close=self._prev_closes.get(symbol),
                updated_at=utcnow(),
            )

    async def unsubscribe(self, symbols: list[str]) -> None:
        self.unsubscribe_calls.append(list(symbols))
        for symbol in symbols:
            self._snapshots.pop(symbol, None)

    async def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        return self._snapshots.get(symbol)

    async def list_snapshots(self) -> list[MarketSnapshot]:
        return list(self._snapshots.values())

    async def run(self) -> None:
        self.run_started = True
        await self._stop_event.wait()

    async def stop(self) -> None:
        self.stopped = True
        self._stop_event.set()

    # ------------------------------------------------------------------ #
    # Test controls
    # ------------------------------------------------------------------ #
    def set_snapshot(
        self,
        symbol: str,
        *,
        last_price: Optional[float] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        volume: Optional[float] = None,
        prev_close: Optional[float] = None,
        stale: bool = False,
        updated_at: Optional[datetime] = None,
    ) -> None:
        """Set exact snapshot field values for ``symbol``, auto-subscribing it.

        Any field left ``None`` here is genuinely ``None`` on the resulting
        snapshot (not "unchanged") — this sets the whole snapshot, it does not
        patch one field of an existing one. Use ``set_previous_close`` to patch
        just ``prev_close`` on an existing snapshot.
        """

        self._snapshots[symbol] = MarketSnapshot(
            symbol=symbol,
            last_price=last_price,
            bid=bid,
            ask=ask,
            volume=volume,
            prev_close=prev_close
            if prev_close is not None
            else self._prev_closes.get(symbol),
            updated_at=updated_at or utcnow(),
            stale=stale,
        )

    def set_previous_close(self, symbol: str, price: float) -> None:
        """Seed the prev_close a future ``subscribe`` will use, and patch it
        onto ``symbol``'s live snapshot if already subscribed."""

        self._prev_closes[symbol] = price
        existing = self._snapshots.get(symbol)
        if existing is not None:
            self._snapshots[symbol] = dataclasses.replace(existing, prev_close=price)
