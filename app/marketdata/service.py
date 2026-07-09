"""The ``MarketDataService`` interface — the only seam through which the
backend gets live prices.

Same pluggable-ABC pattern as :class:`~app.broker.adapter.BrokerAdapter` and
:class:`~app.approval.gate.ApprovalGate`: the strategy loop and any route
depend on this interface, never on a concrete implementation. Beta ships one
real implementation (:class:`~app.marketdata.alpaca_stream.AlpacaMarketDataStream`,
paper-only credentials, real-time SIP data) plus a fully controllable
:class:`~app.marketdata.fake.FakeMarketDataFeed` for IO-free unit tests (Rule 9).

Nothing in this module imports the ``alpaca`` SDK; the interface is pure so it
can be imported anywhere (including the standard test suite) without the SDK
or any credentials present.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class MarketSnapshot:
    """The last known market state for one symbol.

    Working data, not a persisted entity (``docs/02_DATA_AND_PERSISTENCE.md``:
    "stale market-derived features... are working data, not durable records") —
    it lives only in the service implementation's memory, recomputed on the
    monitoring cadence, never written to the StateStore.

    ``prev_close`` is the prior regular session's closing price, seeded once per
    symbol on subscribe; it is the reference ``pct_move`` is computed against
    (see ``app/features.py``). ``bid``/``ask``/``volume`` are ``None`` until the
    feed has observed at least one quote/trade for the symbol.
    """

    symbol: str
    last_price: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    # Session volume is accumulated from observed trade sizes; the SDK types
    # Trade.size / Bar.volume as float (fractional / odd-lot prints occur), so
    # volume is float — an int would truncate sub-share prints (REV-0002 F-003).
    volume: Optional[float]
    prev_close: Optional[float]
    updated_at: datetime
    stale: bool = False


class MarketDataService(ABC):
    """Abstract market-data interface. All methods are async."""

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None:
        """Start tracking ``symbols`` (idempotent for already-subscribed ones).

        A real implementation seeds ``prev_close`` for each newly-subscribed
        symbol (one REST call per symbol) and adds it to the live feed
        subscription. Symbols not in the watchlist's armed set are never
        subscribed — the strategy loop drives subscription state from the
        watchlist, not the reverse.
        """

    @abstractmethod
    async def unsubscribe(self, symbols: list[str]) -> None:
        """Stop tracking ``symbols`` (idempotent for already-unsubscribed ones)."""

    @abstractmethod
    async def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """The current snapshot for ``symbol``, or ``None`` if never subscribed."""

    @abstractmethod
    async def list_snapshots(self) -> list[MarketSnapshot]:
        """Every currently-subscribed symbol's snapshot."""

    @abstractmethod
    async def run(self) -> None:
        """Own the ingestion connection for the process lifetime.

        Started as a background task at app startup (mirrors
        ``app.monitoring.monitoring_loop``). A real implementation's reconnect
        loop lives here: on disconnect, detect it, reconnect with backoff, and
        re-subscribe to the current symbol set — a snapshot must never go
        silently stale (D-005). Returns only on cancellation (clean shutdown);
        must not raise on a transient connection error.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Release the connection. Called once, on shutdown."""
