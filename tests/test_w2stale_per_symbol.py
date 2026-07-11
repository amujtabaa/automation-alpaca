"""W2-STALE (CAMPAIGN-0001 Wave-2, REV-0012 P1) — market-data staleness is judged
PER-SYMBOL, not feed-wide. Previously the ``stale`` flag every consumer gates on
derived from a single feed-wide clock advanced by ANY symbol, so one actively
ticking symbol kept the whole feed "fresh" and a quiet/halted held symbol's stale
price passed the protective-floor gate — masking a real breach or driving a
spurious exit. The fix ORs the feed-wide connection-liveness term with a per-symbol
freshness term (``now - snapshot.updated_at > stale_after``).

Drives the REAL ``AlpacaMarketDataStream`` (construction is network-free) — the
``FakeMarketDataFeed`` returns ``stale`` verbatim and cannot model the feed-wide
computation, which is why unit tests + the review missed this.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.marketdata.alpaca_stream import AlpacaMarketDataStream
from app.marketdata.service import MarketSnapshot
from app.models import utcnow

pytestmark = pytest.mark.anyio


def _stream(stale_after_minutes: float = 5.0) -> AlpacaMarketDataStream:
    # Construction only stores creds + builds SDK clients (no network).
    return AlpacaMarketDataStream("k", "s", stale_after_minutes=stale_after_minutes)


def _put(stream, symbol, *, age_minutes):
    now = utcnow()
    stream._snapshots[symbol] = MarketSnapshot(
        symbol=symbol,
        last_price=100.0,
        bid=99.9,
        ask=100.1,
        volume=1000.0,
        prev_close=100.0,
        updated_at=now - timedelta(minutes=age_minutes),
    )


async def test_quiet_symbol_is_stale_even_when_feed_is_fresh():
    """The core defect: BBB has not updated in an hour; AAA just ticked and keeps
    the feed-wide clock fresh. BBB must still read stale (per-symbol)."""
    stream = _stream()
    now = utcnow()
    stream._run_started_at = now
    stream._last_message_at = now  # feed-wide clock is FRESH (AAA is ticking)
    _put(stream, "AAA", age_minutes=0)
    _put(stream, "BBB", age_minutes=60)

    aaa = await stream.get_snapshot("AAA")
    bbb = await stream.get_snapshot("BBB")
    assert aaa is not None and bbb is not None
    assert aaa.stale is False, "fresh, actively-ticking symbol must not be stale"
    assert bbb.stale is True, (
        "a quiet symbol stale for 60 min must be gated stale even though the "
        "feed-wide clock is fresh (this was the REV-0012 masking bug)"
    )


async def test_total_feed_outage_marks_every_symbol_stale():
    """The feed-wide connection-liveness term is preserved: if NOTHING has ticked
    feed-wide within the window, even a symbol that updated recently is stale."""
    stream = _stream()
    now = utcnow()
    stream._run_started_at = now - timedelta(minutes=60)
    stream._last_message_at = now - timedelta(minutes=60)  # connection dead
    _put(stream, "AAA", age_minutes=0)  # per-symbol looks fresh...

    aaa = await stream.get_snapshot("AAA")
    assert aaa is not None
    assert aaa.stale is True, "a total feed outage must mark every symbol stale"


async def test_fresh_symbol_and_fresh_feed_not_stale():
    stream = _stream()
    now = utcnow()
    stream._run_started_at = now
    stream._last_message_at = now
    _put(stream, "AAA", age_minutes=1)

    aaa = await stream.get_snapshot("AAA")
    assert aaa is not None and aaa.stale is False


async def test_list_snapshots_reports_per_symbol_staleness():
    stream = _stream()
    now = utcnow()
    stream._run_started_at = now
    stream._last_message_at = now
    _put(stream, "AAA", age_minutes=0)
    _put(stream, "BBB", age_minutes=60)

    by_symbol = {s.symbol: s.stale for s in await stream.list_snapshots()}
    assert by_symbol == {"AAA": False, "BBB": True}
