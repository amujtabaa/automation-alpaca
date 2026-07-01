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
(``alpaca.data.live.websocket.DataStream._run_forever``): on a
``websockets.WebSocketException`` it closes the socket, clears its internal
``_running`` flag, and loops back to reconnect — indefinitely, without
``run()`` ever returning. This module does not need its own retry loop around
transient websocket drops. What it *does* need to detect: the connection
going quiet without the SDK's own reconnect noticing (a `run()` that has
actually died — the `"insufficient subscription"` case is the one documented
fatal error the SDK's loop `return`s on, letting `run()` complete) — surfaced
here as permanent staleness (see the module docstring's "fatal vs transient"
note on :meth:`run`), never silently trusted as still-live.

**A bad API key is NOT the same case as "insufficient subscription"** —
verified by reading the same source. ``_run_forever``'s ``except ValueError``
branch only closes the socket and `return`s when the message contains the
literal substring ``"insufficient subscription"``; any other ``ValueError``
(including the one ``_auth()`` raises on a rejected key: ``"failed to
authenticate"``) is logged and falls through to the top of the `while True`
loop *without* resetting `_running` or backing off. Because `_running` was
never set `True` for a connection that never got past `_auth()`, the next
iteration immediately retries `_connect()` + `_auth()` again — an unbounded,
back-off-free reconnect-and-auth-retry storm against Alpaca's endpoint, not a
clean `return` like the subscription case. This module has no hook into that
inner loop to detect or throttle it (`run()` doesn't return until the process
is killed). What *is* still guaranteed: no live message ever arrives during
the storm, so `_last_message_at`/`_run_started_at` never advance and the
staleness check (below) correctly reports every snapshot as permanently
stale — the user-visible "never silently stale" contract (D-005) holds even
though the retry storm itself continues in the background until an operator
notices and restarts the process with a corrected key.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import threading
from datetime import date, datetime, timedelta
from typing import Optional

from alpaca.data.enums import DataFeed
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.live.stock import StockDataStream
from alpaca.data.models.quotes import Quote
from alpaca.data.models.trades import Trade
from alpaca.data.requests import StockSnapshotRequest

from app.features import EASTERN
from app.marketdata.service import MarketDataService, MarketSnapshot
from app.models import utcnow

_log = logging.getLogger(__name__)

_STOP_READY_TIMEOUT_SECONDS = 5.0
_STOP_READY_POLL_INTERVAL_SECONDS = 0.05


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


def _trading_day(dt: datetime) -> date:
    """The US/Eastern calendar date ``dt`` falls on.

    Used to detect a day-boundary crossing for a continuously-subscribed
    symbol (see :meth:`AlpacaMarketDataStream._reseed_symbol`). Deliberately
    Eastern, not UTC: a UTC-date comparison would fire up to an hour early
    for EST (UTC midnight = 7pm ET, still inside that day's after-hours
    session), incorrectly treating an in-progress trading day as over.
    """

    return dt.astimezone(EASTERN).date()


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
        # Trading day each symbol's prev_close/volume baseline was last
        # REST-seeded on — see _reseed_symbol. Without this, a symbol that
        # stays continuously armed never gets a second seed (subscribe()
        # skips already-tracked symbols), so prev_close and the volume
        # accumulator would silently keep referencing a prior trading day
        # forever.
        self._seeded_on: dict[str, date] = {}
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
        #
        # Seeded CONCURRENTLY, not sequentially: each _fetch_seed already
        # catches its own exceptions and returns an all-None tuple rather than
        # raising (never propagates), so gather() without return_exceptions
        # is safe — one symbol's failure can't take down the batch, and
        # arming a large watchlist doesn't pay N sequential REST round-trips.
        now = utcnow()
        seeds = await asyncio.gather(
            *(asyncio.to_thread(self._fetch_seed, symbol) for symbol in new_symbols)
        )
        with self._lock:
            for symbol, (last_price, bid, ask, volume, prev_close) in zip(
                new_symbols, seeds
            ):
                self._snapshots[symbol] = MarketSnapshot(
                    symbol=symbol,
                    last_price=last_price,
                    bid=bid,
                    ask=ask,
                    volume=volume,
                    prev_close=prev_close,
                    updated_at=now,
                )
                self._seeded_on[symbol] = _trading_day(now)

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
                self._seeded_on.pop(symbol, None)

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
            # normal return/exception here means "insufficient subscription"
            # (the one case the SDK's loop actually `return`s on) — not a
            # transient drop the SDK would have recovered from on its own.
            # NOTE: a bad API key does NOT reach this except/return path at
            # all — see the module docstring's "bad API key is NOT the same
            # case" note. It retries forever *inside* run(), so this call
            # simply never returns for that failure mode; there is nothing
            # for us to catch or retry here. We deliberately do NOT
            # loop-and-retry run() ourselves for the case that *does* return
            # (insufficient subscription): repeatedly reconnecting with the
            # same fatal misconfiguration would just hammer Alpaca's
            # subscription endpoint. Instead we stop updating
            # _last_message_at, so every snapshot correctly reports
            # stale=True forever after (D-005: surfaced, never silent) until
            # an operator fixes the root cause and restarts the process.
            await asyncio.to_thread(self._stream.run)
        except Exception:
            _log.exception(
                "Alpaca market data stream terminated (see module docstring: "
                "this is treated as fatal, not retried automatically)"
            )

    async def stop(self) -> None:
        # Guards a startup/shutdown race: StockDataStream.stop() dereferences
        # its internal _loop unconditionally (self._loop.is_running()), and
        # _loop stays None until run()'s background thread reaches
        # _run_forever()'s first line. Calling stop() before that point (e.g.
        # app shutdown arriving moments after startup, before the run() task
        # has actually started executing on its to_thread worker) would
        # otherwise raise an unhandled AttributeError.
        #
        # A bare "return if not ready yet" is NOT safe here: the run() task's
        # underlying to_thread worker cannot be killed by Task.cancel() once
        # it has actually started (a known asyncio.to_thread limitation), so
        # silently skipping the SDK's real stop() in this window would trade
        # the AttributeError crash for a worse failure — a live websocket
        # connection leaked forever, fully detached from the exited process.
        # Instead, poll briefly for _loop to appear (thread-scheduling delay
        # is normally milliseconds) before giving up.
        #
        # Known tradeoff: this reaches into alpaca-py's private `_loop`
        # attribute, since the SDK exposes no public "has run() started"
        # signal to poll instead. An SDK upgrade that renames/removes it
        # would make this loop always time out (never actually stopping the
        # connection) rather than crash — a silent regression back to the
        # leak this fix addresses, discoverable only by testing against a
        # new alpaca-py version, not by this module's own logic.
        deadline = utcnow() + timedelta(seconds=_STOP_READY_TIMEOUT_SECONDS)
        while getattr(self._stream, "_loop", None) is None:
            if utcnow() >= deadline:
                _log.warning(
                    "stop() timed out waiting for the market data stream to "
                    "start; run() may never have been scheduled — nothing to "
                    "stop."
                )
                return
            await asyncio.sleep(_STOP_READY_POLL_INTERVAL_SECONDS)
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

    async def _reseed_symbol(self, symbol: str, now: datetime) -> None:
        """Re-seed ``prev_close`` and the volume baseline for one symbol on a
        trading-day rollover.

        ``subscribe()`` only seeds a symbol once — a continuously-armed
        symbol (never unsubscribed/re-subscribed) would otherwise keep
        ``prev_close`` pinned to whatever day it first subscribed on forever,
        and keep accumulating ``volume`` on top of a stale baseline across
        day boundaries. Triggered from :meth:`_on_trade` only, on the first
        trade observed after the trading day changes (see ``_trading_day``).

        Only ``prev_close``/``volume`` are touched — ``last_price``/``bid``/
        ``ask``/``updated_at`` are left as whatever the live feed already
        has, so a REST call that lags the live tick can never regress those.

        **Two known, accepted tradeoffs, not oversights** (found in review,
        deliberately not fixed given the beta/single-user scope):

        1. A symbol with zero trades on a given day never reseeds — quotes
           alone (``_on_quote``) don't trigger it. ``prev_close`` stays
           pinned to the prior day until (unless) a trade eventually lands,
           which would then compute ``pct_move`` against a stale baseline for
           that one evaluation. This only affects a symbol illiquid enough to
           go a full session without a print, which the momentum strategies
           this beta targets are unlikely to be watching in practice.
        2. The REST call here is *awaited inline* from ``_on_trade``, which
           the SDK dispatches strictly serially (one message fully processed
           before the next is even read — see the module docstring). During
           a real day-boundary rollover with many armed symbols, each one's
           first post-rollover trade blocks delivery of every other symbol's
           trades/quotes for that REST round-trip's duration, so reseeds
           landing close together can compound into a multi-second delay.
           Making this non-blocking (e.g. `asyncio.create_task`) would
           reintroduce a genuine concurrent-reseed race that today's
           strictly-serial dispatch structurally prevents — not a free fix.
        """

        _, _, _, volume, prev_close = await asyncio.to_thread(self._fetch_seed, symbol)
        with self._lock:
            existing = self._snapshots.get(symbol)
            if existing is None:
                return  # unsubscribed while the REST call was in flight
            self._snapshots[symbol] = dataclasses.replace(
                existing,
                prev_close=prev_close if prev_close is not None else existing.prev_close,
                volume=volume,
            )
            self._seeded_on[symbol] = _trading_day(now)

    async def _on_trade(self, trade: Trade) -> None:
        now = utcnow()
        with self._lock:
            self._last_message_at = now
            existing = self._snapshots.get(trade.symbol)
            if existing is None:
                return  # unsubscribed between the tick being sent and received
            needs_reseed = self._seeded_on.get(trade.symbol) != _trading_day(now)

        if needs_reseed:
            await self._reseed_symbol(trade.symbol, now)

        with self._lock:
            existing = self._snapshots.get(trade.symbol)
            if existing is None:
                return  # unsubscribed while the reseed REST call was in flight
            self._snapshots[trade.symbol] = dataclasses.replace(
                existing,
                last_price=trade.price,
                # Approximate session volume: REST-seeded baseline (today's
                # cumulative volume as of the last completed daily bar) plus
                # observed trade sizes since subscribing (or since the last
                # day-boundary reseed above). Not settlement-grade exact
                # cumulative volume (a brief disconnect could under-count
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
