"""Strategy loop — end-to-end candidate generation (Phase 5).

Run through ``any_store`` where it proves the loop behaves identically against
both StateStore implementations; store-agnostic scenarios (subscription sync,
dedup mechanics that don't depend on store internals) use InMemoryStateStore
directly to keep the suite fast.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.models import CandidateStatus
from app.store.memory import InMemoryStateStore
from app.strategy_loop import run_strategy_tick

pytestmark = pytest.mark.anyio

# 2026-01-07 (Wednesday) 05:00 ET = 10:00 UTC -> PRE_MARKET.
_PRE_MARKET_NOW = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
# Same day, 11:00 ET = 16:00 UTC -> REGULAR.
_REGULAR_NOW = datetime(2026, 1, 7, 16, 0, tzinfo=timezone.utc)

_HEALTHY = dict(last_price=103.0, prev_close=100.0, bid=102.9, ask=103.1, volume=100_000)


async def _armed_store(*symbols: str) -> InMemoryStateStore:
    store = InMemoryStateStore()
    await store.initialize()
    for symbol in symbols:
        await store.add_watchlist_symbol(symbol, armed=True)
    return store


async def test_armed_symbol_with_healthy_snapshot_creates_candidate(any_store):
    await any_store.initialize()
    await any_store.add_watchlist_symbol("AAPL", armed=True)
    feed = FakeMarketDataFeed()
    await feed.subscribe(["AAPL"])
    feed.set_snapshot("AAPL", **_HEALTHY)

    await run_strategy_tick(any_store, feed, Settings(), now=_PRE_MARKET_NOW)

    candidates = await any_store.list_candidates()
    assert len(candidates) == 1
    c = candidates[0]
    assert c.symbol == "AAPL"
    assert c.strategy == "premarket_momentum_v1"
    assert c.status is CandidateStatus.PENDING
    assert c.suggested_quantity == 10
    assert c.suggested_limit_price is not None
    assert "phase5_fixed_size_pending_capi" == c.risk_decision


async def test_unarmed_symbol_never_evaluated():
    store = await _armed_store()  # nothing armed
    await store.add_watchlist_symbol("AAPL", armed=False)
    feed = FakeMarketDataFeed()

    await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

    assert feed.subscribe_calls == []
    assert await store.list_candidates() == []


async def test_freshly_armed_symbol_is_subscribed_but_not_proposed_first_tick():
    store = await _armed_store("AAPL")
    feed = FakeMarketDataFeed()  # not yet subscribed to AAPL

    await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

    assert feed.subscribe_calls == [["AAPL"]]
    # A freshly-subscribed symbol has no data yet (all None) -> no proposal.
    assert await store.list_candidates() == []

    # Second tick, now with real snapshot data -> proposes.
    feed.set_snapshot("AAPL", **_HEALTHY)
    await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
    assert len(await store.list_candidates()) == 1


async def test_disarmed_symbol_is_unsubscribed():
    store = await _armed_store("AAPL")
    feed = FakeMarketDataFeed()
    await feed.subscribe(["AAPL"])
    feed.set_snapshot("AAPL", **_HEALTHY)

    await store.set_watchlist_armed("AAPL", False)
    await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

    assert feed.unsubscribe_calls == [["AAPL"]]
    assert await store.list_candidates() == []


async def test_regular_session_never_proposes():
    store = await _armed_store("AAPL")
    feed = FakeMarketDataFeed()
    await feed.subscribe(["AAPL"])
    feed.set_snapshot("AAPL", **_HEALTHY)

    await run_strategy_tick(store, feed, Settings(), now=_REGULAR_NOW)

    assert await store.list_candidates() == []


class TestDedup:
    async def test_pending_candidate_blocks_a_second_proposal(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", **_HEALTHY)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        assert len(await store.list_candidates()) == 1  # not duplicated

    async def test_approved_candidate_still_blocks(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", **_HEALTHY)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        [c] = await store.list_candidates()
        await store.transition_candidate(c.id, CandidateStatus.APPROVED)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        assert len(await store.list_candidates()) == 1

    async def test_rejected_candidate_allows_a_fresh_proposal(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", **_HEALTHY)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        [c] = await store.list_candidates()
        await store.transition_candidate(c.id, CandidateStatus.REJECTED)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        assert len(await store.list_candidates()) == 2

    async def test_ordered_candidate_allows_a_fresh_proposal(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", **_HEALTHY)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        [c] = await store.list_candidates()
        await store.transition_candidate(c.id, CandidateStatus.APPROVED)
        await store.create_order_for_candidate(c.id)  # -> ORDERED

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        assert len(await store.list_candidates()) == 2


class TestSessionClose:
    async def test_closed_session_skips_the_whole_tick(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])  # setup call, before the tick under test
        feed.set_snapshot("AAPL", **_HEALTHY)
        await store.close_session()
        calls_before = len(feed.subscribe_calls)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        assert len(feed.subscribe_calls) == calls_before  # loop made no new calls
        assert feed.unsubscribe_calls == []
        assert await store.list_candidates() == []


class TestNotGatedBySafetyControls:
    """Regression test for D-014a: candidate generation is NOT gated by the
    kill switch or pause-buys — only order intent is (Rule 8)."""

    async def test_kill_switch_engaged_still_proposes(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", **_HEALTHY)
        await store.set_kill_switch(True)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        assert len(await store.list_candidates()) == 1

    async def test_buys_paused_still_proposes(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", **_HEALTHY)
        await store.set_buys_paused(True)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        assert len(await store.list_candidates()) == 1


async def test_one_symbols_failure_does_not_block_others():
    store = await _armed_store("AAPL", "MSFT")
    feed = FakeMarketDataFeed()
    await feed.subscribe(["AAPL", "MSFT"])
    feed.set_snapshot("AAPL", **_HEALTHY)
    feed.set_snapshot("MSFT", **_HEALTHY)

    orig_get_snapshot = feed.get_snapshot

    async def flaky_get_snapshot(symbol):
        if symbol == "AAPL":
            raise RuntimeError("simulated feed error for AAPL")
        return await orig_get_snapshot(symbol)

    feed.get_snapshot = flaky_get_snapshot

    await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

    candidates = await store.list_candidates()
    assert len(candidates) == 1
    assert candidates[0].symbol == "MSFT"  # AAPL's failure didn't block MSFT
