"""AlpacaMarketDataStream — logic tests against a mocked SDK boundary.

No network calls: ``StockDataStream``/``StockHistoricalDataClient``
construction is offline (verified — no network at __init__), and every method
that would otherwise hit the network is replaced with a test double. Mirrors
the precedent in ``test_alpaca_paper_fills.py`` (``pytest.importorskip`` so the
standard suite stays import-safe without ``alpaca-py``; direct construction
with fake credentials; pure-logic assertions).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("alpaca")

from app.marketdata.alpaca_stream import (  # noqa: E402
    AlpacaMarketDataStream,
    _is_feed_stale,
    _seed_from_snapshot,
)

pytestmark = pytest.mark.anyio


def _stream() -> AlpacaMarketDataStream:
    # StockDataStream/StockHistoricalDataClient construction is offline (no
    # network); paper-only fake creds, matching the AlpacaPaperAdapter precedent.
    return AlpacaMarketDataStream("fake-key", "fake-secret", stale_after_minutes=5.0)


def _fake_snapshot(*, last_price=None, bid=None, ask=None, volume=None, prev_close=None):
    return SimpleNamespace(
        latest_trade=SimpleNamespace(price=last_price) if last_price is not None else None,
        latest_quote=(
            SimpleNamespace(bid_price=bid, ask_price=ask) if bid is not None else None
        ),
        daily_bar=SimpleNamespace(volume=volume) if volume is not None else None,
        previous_daily_bar=(
            SimpleNamespace(close=prev_close) if prev_close is not None else None
        ),
    )


class TestIsFeedStale:
    def test_never_started_is_not_stale(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        assert _is_feed_stale(None, now, timedelta(minutes=5)) is False

    def test_within_threshold_not_stale(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        assert _is_feed_stale(now - timedelta(minutes=4), now, timedelta(minutes=5)) is False

    def test_exactly_at_threshold_not_stale(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        assert _is_feed_stale(now - timedelta(minutes=5), now, timedelta(minutes=5)) is False

    def test_past_threshold_is_stale(self):
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        assert _is_feed_stale(now - timedelta(minutes=6), now, timedelta(minutes=5)) is True


class TestSeedFromSnapshot:
    def test_full_snapshot(self):
        raw = _fake_snapshot(last_price=103.0, bid=102.9, ask=103.1, volume=100_000, prev_close=100.0)
        assert _seed_from_snapshot(raw) == (103.0, 102.9, 103.1, 100_000, 100.0)

    def test_missing_latest_trade(self):
        raw = _fake_snapshot(bid=102.9, ask=103.1, volume=100_000, prev_close=100.0)
        last_price, bid, ask, volume, prev_close = _seed_from_snapshot(raw)
        assert last_price is None
        assert bid == 102.9

    def test_all_missing(self):
        raw = _fake_snapshot()
        assert _seed_from_snapshot(raw) == (None, None, None, None, None)


class TestSubscribe:
    async def test_seeds_snapshot_and_registers_handlers(self):
        stream = _stream()
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=103.0, bid=102.9, ask=103.1, volume=100_000, prev_close=100.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()

        await stream.subscribe(["AAPL"])

        snap = await stream.get_snapshot("AAPL")
        assert snap is not None
        assert snap.last_price == 103.0
        assert snap.prev_close == 100.0
        stream._stream.subscribe_trades.assert_called_once()
        stream._stream.subscribe_quotes.assert_called_once()
        # handler, *symbols positional args
        assert stream._stream.subscribe_trades.call_args.args[1:] == ("AAPL",)

    async def test_multi_symbol_batch_assigns_each_seed_to_the_right_symbol(self):
        """Concurrent seeding (asyncio.gather) must not scramble which result
        belongs to which symbol — a real risk when parallelizing per-symbol
        work if results aren't paired back up by position/key correctly."""

        stream = _stream()

        def fake_get_snapshot(request):
            symbol = request.symbol_or_symbols
            prices = {"AAPL": 100.0, "MSFT": 200.0, "GOOG": 300.0}
            return {symbol: _fake_snapshot(last_price=prices[symbol], prev_close=prices[symbol] - 1)}

        stream._historical.get_stock_snapshot = Mock(side_effect=fake_get_snapshot)
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()

        await stream.subscribe(["AAPL", "MSFT", "GOOG"])

        aapl = await stream.get_snapshot("AAPL")
        msft = await stream.get_snapshot("MSFT")
        goog = await stream.get_snapshot("GOOG")
        assert aapl.last_price == 100.0
        assert msft.last_price == 200.0
        assert goog.last_price == 300.0

    async def test_multi_symbol_batch_seeds_concurrently_not_sequentially(self):
        """Each REST seed call runs off-thread and concurrently — subscribing
        N symbols should take roughly ONE call's latency, not N of them."""

        import time

        stream = _stream()
        delay_seconds = 0.2
        symbols = ["AAPL", "MSFT", "GOOG", "TSLA"]

        def slow_get_snapshot(request):
            time.sleep(delay_seconds)  # runs in a worker thread (asyncio.to_thread)
            symbol = request.symbol_or_symbols
            return {symbol: _fake_snapshot(last_price=1.0, prev_close=1.0)}

        stream._historical.get_stock_snapshot = Mock(side_effect=slow_get_snapshot)
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()

        start = time.monotonic()
        await stream.subscribe(symbols)
        elapsed = time.monotonic() - start

        # Sequential would take ~4 * delay_seconds (0.8s); concurrent should
        # be close to 1 * delay_seconds. Generous margin for CI scheduling
        # jitter, but tight enough to fail if it silently regresses to serial.
        assert elapsed < delay_seconds * len(symbols) * 0.75

    async def test_already_subscribed_symbol_is_not_reseeded(self):
        stream = _stream()
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=103.0, prev_close=100.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()

        await stream.subscribe(["AAPL"])
        await stream.subscribe(["AAPL"])  # second call, same symbol

        assert stream._historical.get_stock_snapshot.call_count == 1

    async def test_seed_failure_does_not_raise_and_yields_null_fields(self):
        stream = _stream()
        stream._historical.get_stock_snapshot = Mock(side_effect=RuntimeError("network down"))
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()

        await stream.subscribe(["AAPL"])  # must not raise

        snap = await stream.get_snapshot("AAPL")
        assert snap is not None
        assert snap.last_price is None

    async def test_missing_symbol_in_response_yields_null_fields(self):
        stream = _stream()
        stream._historical.get_stock_snapshot = Mock(return_value={})  # AAPL absent
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()

        await stream.subscribe(["AAPL"])

        snap = await stream.get_snapshot("AAPL")
        assert snap.last_price is None


class TestUnsubscribe:
    async def test_removes_snapshot_and_calls_sdk(self):
        stream = _stream()
        stream._historical.get_stock_snapshot = Mock(return_value={"AAPL": _fake_snapshot(last_price=1.0, prev_close=1.0)})
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        stream._stream.unsubscribe_trades = Mock()
        stream._stream.unsubscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])

        await stream.unsubscribe(["AAPL"])

        assert await stream.get_snapshot("AAPL") is None
        stream._stream.unsubscribe_trades.assert_called_once_with("AAPL")
        stream._stream.unsubscribe_quotes.assert_called_once_with("AAPL")

    async def test_unsubscribing_a_never_subscribed_symbol_is_a_noop(self):
        stream = _stream()
        stream._stream.unsubscribe_trades = Mock()
        stream._stream.unsubscribe_quotes = Mock()

        await stream.unsubscribe(["AAPL"])  # never subscribed

        stream._stream.unsubscribe_trades.assert_not_called()
        stream._stream.unsubscribe_quotes.assert_not_called()


class TestLiveHandlers:
    async def test_trade_updates_price_and_accumulates_volume(self):
        stream = _stream()
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=100.0, volume=1_000, prev_close=99.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])

        await stream._on_trade(SimpleNamespace(symbol="AAPL", price=101.0, size=50))
        await stream._on_trade(SimpleNamespace(symbol="AAPL", price=102.0, size=25))

        snap = await stream.get_snapshot("AAPL")
        assert snap.last_price == 102.0
        assert snap.volume == 1_000 + 50 + 25

    async def test_quote_updates_bid_ask(self):
        stream = _stream()
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=100.0, prev_close=99.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])

        await stream._on_quote(SimpleNamespace(symbol="AAPL", bid_price=101.9, ask_price=102.1))

        snap = await stream.get_snapshot("AAPL")
        assert snap.bid == 101.9
        assert snap.ask == 102.1

    async def test_tick_for_unsubscribed_symbol_is_ignored(self):
        stream = _stream()
        # AAPL was never subscribed -> _on_trade must not raise or resurrect it.
        await stream._on_trade(SimpleNamespace(symbol="AAPL", price=100.0, size=10))
        assert await stream.get_snapshot("AAPL") is None

    async def test_reseed_null_prev_close_keeps_existing_value(self, monkeypatch):
        stream = _stream()
        day1 = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day1)
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=100.0, volume=1_000, prev_close=99.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])

        day2 = datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day2)
        # REST momentarily has no previous_daily_bar -> must not clobber prev_close with None.
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=103.0, volume=500)}
        )

        await stream._on_trade(SimpleNamespace(symbol="AAPL", price=104.0, size=25))

        snap = await stream.get_snapshot("AAPL")
        assert snap.prev_close == 99.0  # preserved, not clobbered with None

    async def test_tick_updates_feed_wide_staleness_clock(self):
        stream = _stream()
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=100.0, prev_close=99.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])
        # Force the feed-wide clock into the past, simulating a stale connection.
        stream._last_message_at = datetime.now(timezone.utc) - timedelta(minutes=10)

        snap_before = await stream.get_snapshot("AAPL")
        assert snap_before.stale is True

        await stream._on_trade(SimpleNamespace(symbol="AAPL", price=101.0, size=10))

        snap_after = await stream.get_snapshot("AAPL")
        assert snap_after.stale is False  # a fresh tick recovers staleness


class TestDayBoundaryReseed:
    """A continuously-armed symbol is only ever seeded once by subscribe()
    (it skips already-tracked symbols) — without a day-boundary reseed,
    prev_close and the volume baseline would silently keep referencing
    whatever day the symbol first subscribed on, forever."""

    async def test_same_trading_day_trade_does_not_reseed(self, monkeypatch):
        stream = _stream()
        day1 = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)  # 11:00 ET
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day1)
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=100.0, volume=1_000, prev_close=99.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])

        later_same_day = datetime(2026, 6, 1, 19, 0, tzinfo=timezone.utc)  # 15:00 ET, still day1
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: later_same_day)

        await stream._on_trade(SimpleNamespace(symbol="AAPL", price=101.0, size=10))

        assert stream._historical.get_stock_snapshot.call_count == 1  # only the initial seed
        snap = await stream.get_snapshot("AAPL")
        assert snap.prev_close == 99.0
        assert snap.volume == 1_000 + 10

    async def test_next_trading_day_trade_reseeds_prev_close_and_volume_baseline(self, monkeypatch):
        stream = _stream()
        day1 = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day1)
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=100.0, volume=1_000, prev_close=99.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])

        day2 = datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc)  # next ET calendar day
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day2)
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=103.0, volume=500, prev_close=102.0)}
        )

        await stream._on_trade(SimpleNamespace(symbol="AAPL", price=104.0, size=25))

        stream._historical.get_stock_snapshot.assert_called_once()  # the reseed call
        snap = await stream.get_snapshot("AAPL")
        assert snap.prev_close == 102.0  # refreshed from the day2 baseline, not day1's 99.0
        assert snap.volume == 500 + 25  # new baseline + this trade, not stacked on day1's 1,000
        assert snap.last_price == 104.0  # the live trade price is still applied

    async def test_reseed_null_prev_close_keeps_existing_value(self, monkeypatch):
        stream = _stream()
        day1 = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day1)
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=100.0, volume=1_000, prev_close=99.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])

        day2 = datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day2)
        # REST momentarily has no previous_daily_bar -> must not clobber prev_close with None.
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=103.0, volume=500)}
        )

        await stream._on_trade(SimpleNamespace(symbol="AAPL", price=104.0, size=25))

        snap = await stream.get_snapshot("AAPL")
        assert snap.prev_close == 99.0  # preserved, not clobbered with None

    async def test_unsubscribe_during_reseed_does_not_resurrect_symbol(self, monkeypatch):
        import time

        stream = _stream()
        day1 = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day1)
        stream._historical.get_stock_snapshot = Mock(
            return_value={"AAPL": _fake_snapshot(last_price=100.0, volume=1_000, prev_close=99.0)}
        )
        stream._stream.subscribe_trades = Mock()
        stream._stream.subscribe_quotes = Mock()
        stream._stream.unsubscribe_trades = Mock()
        stream._stream.unsubscribe_quotes = Mock()
        await stream.subscribe(["AAPL"])

        day2 = datetime(2026, 6, 2, 15, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("app.marketdata.alpaca_stream.utcnow", lambda: day2)

        def slow_reseed(request):
            time.sleep(0.1)  # runs in a worker thread (asyncio.to_thread)
            return {"AAPL": _fake_snapshot(last_price=103.0, volume=500, prev_close=102.0)}

        stream._historical.get_stock_snapshot = Mock(side_effect=slow_reseed)

        trade_task = asyncio.create_task(
            stream._on_trade(SimpleNamespace(symbol="AAPL", price=104.0, size=25))
        )
        await asyncio.sleep(0.02)  # let the reseed REST call start
        await stream.unsubscribe(["AAPL"])
        await trade_task  # must not raise, must not resurrect AAPL

        assert await stream.get_snapshot("AAPL") is None


class TestRunStop:
    async def test_run_catches_a_fatal_sdk_exception_without_raising(self):
        stream = _stream()
        stream._stream.run = Mock(side_effect=RuntimeError("insufficient subscription"))

        await stream.run()  # must not raise

    async def test_run_records_start_time(self):
        stream = _stream()
        stream._stream.run = Mock(return_value=None)
        assert stream._run_started_at is None

        await stream.run()

        assert stream._run_started_at is not None

    async def test_stop_before_run_has_started_is_a_noop_not_an_attributeerror(self):
        """StockDataStream._loop is None until run()'s background thread
        reaches _run_forever(); calling the SDK's stop() before that
        dereferences None (self._loop.is_running()), raising AttributeError.
        A shutdown arriving before run() has actually started must not crash."""
        stream = _stream()
        stream._stream.stop = Mock()
        assert stream._stream._loop is None  # run() never started

        await stream.stop()  # must not raise

        stream._stream.stop.assert_not_called()

    async def test_stop_calls_sdk_stop_once_run_has_started(self):
        stream = _stream()
        stream._stream._loop = Mock()  # simulates run()'s thread having started
        stream._stream.stop = Mock()

        await stream.stop()

        stream._stream.stop.assert_called_once()
