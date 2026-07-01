"""Real Alpaca market-data feed — the ONE place in this package that imports
the ``alpaca`` SDK.

Safety contract mirrors ``app.broker.alpaca_paper`` (the only other module
that touches the SDK): paper-only credentials, never logged; this module is
integration-tested only (env-gated); the standard unit-test suite never
imports it (``app.marketdata.create_market_data_service`` imports it lazily,
only when actually selected).

**Threading, not asyncio, for the SDK connection.** ``alpaca-py``'s
``StockDataStream.run()`` is a *synchronous* method that internally calls
``asyncio.run(self._run_forever())`` — it insists on owning its own fresh
event loop, so it cannot be ``await``-ed directly from within FastAPI's
already-running loop (``asyncio.run()`` raises if called from inside a running
loop). This is why ``run()`` here is a background thread
(``asyncio.to_thread(self._stream.run)``): the SDK's own thread spins its own
loop for the websocket; the ``subscribe_trades``/``subscribe_quotes`` methods
are explicitly designed for cross-thread calls (they use
``asyncio.run_coroutine_threadsafe`` internally once the stream is running),
and the trade/quote handlers execute *on the stream's thread*, so all shared
snapshot state is guarded by a plain ``threading.Lock`` (not ``asyncio.Lock``,
which has no cross-thread meaning) rather than trusting the GIL alone for the
multi-field ``MarketSnapshot`` replacement.

**Reconnect (D-005) is mostly the SDK's job, verified by reading its source**
(``alpaca.data.live.stock.StockDataStream._run_forever``): on a
``websockets.WebSocketException`` it closes the socket, clears its internal
``_running`` flag, and loops back to reconnect — indefinitely, without
``run()`` ever returning. This module does not need its own retry loop around
transient websocket drops. What it *does* need to detect: the connection
going quiet without the SDK's own reconnect noticing (a `run()` that has
actually died — the `"insufficient subscription"` case is the one documented
fatal error the SDK's loop `return`s on, letting `run()` complete) — surfaced
here as permanent staleness (see the module docstring's "fatal vs transient"
note on :meth:`run`), never silently trusted as still-live.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.live.stock import StockDataStream
from alpaca.data.models.quotes import Quote
from alpaca.data.models.trades import Trade
from alpaca.data.requests import StockSnapshotRequest

from app.marketdata.service import MarketDataService, MarketSnapshot
from app.models import utcnow

_log = logging.getLogger(__name__)


def _is_feed_stale(
    reference: Optional[datetime], now: datetime, stale_after: timedelta
) -> bool:
    """Pure staleness predicate — testable without a live connection.

    ``reference`` is the last time the feed produced *any* message (or, before
    the first message, when ``run()`` started). ``None`` (``run()`` never
    started) is never stale — there is nothing to judge staleness against yet.
    """

    if reference is None:
        return False
    return (now - reference) > stale_after


def _seed_from_snapshot(raw) -> tuple[
    Optional[float], Optional[float], Optional[float], Optional[int], Optional[float]
]:
    """Extract ``(last_price, bid, ask, volume, prev_close)`` from an Alpaca
    ``Snapshot``. Any missing sub-object yields ``None`` for its fields — a
    freshly-listed or illiquid symbol may lack a latest trade/quote."""

    last_price = raw.latest_trade.price if raw.latest_trade is not None else None
    bid = raw.latest_quote.bid_price if raw.latest_quote is not None else None
    ask = raw.latest_quote.ask_price if raw.latest_quote is not None else None
    volume = raw.daily_bar.volume if raw.daily_bar is not None else None
    prev_close = (
        raw.previous_daily_bar.close if raw.previous_daily_bar is not None else None
    )
    return last_price, bid, ask, volume, prev_close


class AlpacaMarketDataStream(MarketDataService):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        stale_after_minutes: float = 5.0,
        feed: DataFeed = DataFeed.SIP,
    ) -> None:
        # Real-time SIP (not the free-tier IEX default — docs/02: "the paper
        # account still receives the full real-time SIP feed, not a delayed
        # one" under the Algo Trader Plus subscription).
        self._stream = StockDataStream(api_key, api_secret, feed=feed)
        self._historical = StockHistoricalDataClient(api_key, api_secret)
        self._feed = feed
        self._stale_after = timedelta(minutes=stale_after_minutes)

        self._lock = threading.Lock()
        self._snapshots: dict[str, MarketSnapshot] = {}
        # Feed-wide "is the connection alive" clock: updated by ANY trade/quote
        # handler firing for ANY symbol. Deliberately not per-symbol — an
        # illiquid symbol legitimately not trading for minutes is not the same
        # thing as the websocket connection itself being down.
        self._last_message_at: Optional[datetime] = None
        self._run_started_at: Optional[datetime] = None

    # ------------------------------------------------------------------ #
    # MarketDataService
    # ------------------------------------------------------------------ #
    async def subscribe(self, symbols: list[str]) -> None:
        with self._lock:
            new_symbols = [s for s in symbols if s not in self._snapshots]
        if not new_symbols:
            return

        # NOTE: assumes a single caller drives subscribe()/unsubscribe() calls
        # sequentially (true today — only strategy_loop.py's per-tick diff
        # calls these, and it awaits one tick fully before the next; a symbol
        # is never in both a subscribe and an unsubscribe batch in the same
        # tick). A concurrent unsubscribe() for the same symbol from a
        # different caller, landing during the awaited REST seed below, would
        # resurrect it. Not guarded against — would need a separate "still
        # wanted" set if a second caller is ever introduced.
        now = utcnow()
        for symbol in new_symbols:
            last_price, bid, ask, volume, prev_close = await asyncio.to_thread(
                self._fetch_seed, symbol
            )
            with self._lock:
                self._snapshots[symbol] = MarketSnapshot(
                    symbol=symbol,
                    last_price=last_price,
                    bid=bid,
                    ask=ask,
                    volume=volume,
                    prev_close=prev_close,
                    updated_at=now,
                )

        # Register live updates. Safe to call before run() has started (the SDK
        # just records the handler) or after (it dispatches onto the stream's
        # own loop via run_coroutine_threadsafe and blocks briefly for the ack
        # — hence to_thread, so it never blocks our loop).
        await asyncio.to_thread(self._stream.subscribe_trades, self._on_trade, *new_symbols)
        await asyncio.to_thread(self._stream.subscribe_quotes, self._on_quote, *new_symbols)

    async def unsubscribe(self, symbols: list[str]) -> None:
        with self._lock:
            existing = [s for s in symbols if s in self._snapshots]
        if not existing:
            return
        await asyncio.to_thread(self._stream.unsubscribe_trades, *existing)
        await asyncio.to_thread(self._stream.unsubscribe_quotes, *existing)
        with self._lock:
            for symbol in existing:
                self._snapshots.pop(symbol, None)

    async def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        with self._lock:
            snap = self._snapshots.get(symbol)
            if snap is None:
                return None
            return dataclasses.replace(snap, stale=self._is_stale_locked())

    async def list_snapshots(self) -> list[MarketSnapshot]:
        with self._lock:
            stale = self._is_stale_locked()
            return [dataclasses.replace(s, stale=stale) for s in self._snapshots.values()]

    async def run(self) -> None:
        with self._lock:
            self._run_started_at = utcnow()
        try:
            # StockDataStream.run() is sync and owns its own event loop
            # (asyncio.run(...) internally) — must run off-thread; see the
            # module docstring. Its internal _run_forever() already retries
            # transient websocket errors forever without returning, so a
            # normal return/exception here means something genuinely fatal
            # (e.g. "insufficient subscription", a bad API key) — not a
            # transient drop the SDK would have recovered from on its own.
            # We deliberately do NOT loop-and-retry run() ourselves in that
            # case: repeatedly reconnecting with the same fatal misconfiguration
            # would just hammer Alpaca's auth/subscription endpoint. Instead we
            # stop updating _last_message_at, so every snapshot correctly
            # reports stale=True forever after (D-005: surfaced, never silent)
            # until an operator fixes the root cause and restarts the process.
            await asyncio.to_thread(self._stream.run)
        except Exception:
            _log.exception(
                "Alpaca market data stream terminated (see module docstring: "
                "this is treated as fatal, not retried automatically)"
            )

    async def stop(self) -> None:
        await asyncio.to_thread(self._stream.stop)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #
    def _is_stale_locked(self) -> bool:
        """Assumes ``self._lock`` is held."""

        reference = self._last_message_at or self._run_started_at
        return _is_feed_stale(reference, utcnow(), self._stale_after)

    def _fetch_seed(
        self, symbol: str
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[int], Optional[float]]:
        """REST-seed one symbol's snapshot fields (sync; called via to_thread).

        One symbol at a time, not a batched multi-symbol request: a batch
        call's partial-failure semantics (one bad/delisted symbol among many)
        aren't something this module can verify without a live account, so it
        favors the more defensive per-symbol call — a failure here never
        blocks seeding the other symbols in the same ``subscribe()`` batch.
        """

        try:
            request = StockSnapshotRequest(symbol_or_symbols=symbol, feed=self._feed)
            result = self._historical.get_stock_snapshot(request)
            raw = result.get(symbol) if isinstance(result, dict) else None
            if raw is None:
                return None, None, None, None, None
            return _seed_from_snapshot(raw)
        except Exception:
            _log.exception("failed to seed snapshot for %s; proceeding with nulls", symbol)
            return None, None, None, None, None

    async def _on_trade(self, trade: Trade) -> None:
        with self._lock:
            self._last_message_at = utcnow()
            existing = self._snapshots.get(trade.symbol)
            if existing is None:
                return  # unsubscribed between the tick being sent and received
            self._snapshots[trade.symbol] = dataclasses.replace(
                existing,
                last_price=trade.price,
                # Approximate session volume: REST-seeded baseline (today's
                # cumulative volume as of the last completed daily bar) plus
                # observed trade sizes since subscribing. Not settlement-grade
                # exact cumulative volume (a brief disconnect could under-count
                # trades that occurred during the gap) — adequate for a
                # threshold gate (Strategy Engine's min-volume check), not for
                # precise reporting.
                volume=(existing.volume or 0) + trade.size,
                updated_at=utcnow(),
            )

    async def _on_quote(self, quote: Quote) -> None:
        with self._lock:
            self._last_message_at = utcnow()
            existing = self._snapshots.get(quote.symbol)
            if existing is None:
                return
            self._snapshots[quote.symbol] = dataclasses.replace(
                existing,
                bid=quote.bid_price,
                ask=quote.ask_price,
                updated_at=utcnow(),
            )
