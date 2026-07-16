"""Strategy loop — end-to-end candidate generation (Phase 5).

Run through ``any_store`` where it proves the loop behaves identically against
both StateStore implementations; store-agnostic scenarios (subscription sync,
dedup mechanics that don't depend on store internals) use InMemoryStateStore
directly to keep the suite fast.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timezone

import pytest

from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.models import CandidateStatus
from app.store.memory import InMemoryStateStore
from app.strategy_loop import run_strategy_tick, strategy_loop

pytestmark = pytest.mark.anyio

# 2026-01-07 (Wednesday) 05:00 ET = 10:00 UTC -> PRE_MARKET.
_PRE_MARKET_NOW = datetime(2026, 1, 7, 10, 0, tzinfo=timezone.utc)
# Same day, 11:00 ET = 16:00 UTC -> REGULAR.
_REGULAR_NOW = datetime(2026, 1, 7, 16, 0, tzinfo=timezone.utc)

_HEALTHY = dict(
    last_price=103.0, prev_close=100.0, bid=102.9, ask=103.1, volume=100_000
)


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
    async def test_closed_session_skips_candidate_evaluation(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])  # setup call, before the tick under test
        feed.set_snapshot("AAPL", **_HEALTHY)
        await store.close_session()
        calls_before = len(feed.subscribe_calls)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        # No NEW subscribe call (AAPL was already subscribed and stays armed —
        # sync is a no-op here, not skipped; see the two tests below for sync/
        # staleness genuinely still running during a closed session).
        assert len(feed.subscribe_calls) == calls_before
        assert feed.unsubscribe_calls == []
        assert await store.list_candidates() == []  # no candidate created

    async def test_sync_subscriptions_still_runs_during_a_closed_session(self):
        """Subscription sync is NOT gated on session state — a newly-armed
        symbol still gets subscribed even while the session is closed, so the
        feed doesn't go blind just because trading is stopped for the day."""

        store = InMemoryStateStore()
        await store.initialize()
        await store.close_session()
        await store.add_watchlist_symbol("AAPL", armed=True)
        feed = FakeMarketDataFeed()  # AAPL not yet subscribed

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        assert feed.subscribe_calls == [["AAPL"]]  # synced despite the closed session
        assert await store.list_candidates() == []  # still no candidate, though

    async def test_staleness_surfacing_still_runs_during_a_closed_session(self):
        """A dead feed is surfaced even while the session is closed — D-005's
        'never silently stale' doesn't pause just because trading has stopped
        for the day (e.g. an overnight outage before the next session opens)."""

        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", stale=True)
        await store.close_session()

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        events = await store.list_events()
        assert any(
            e.event_type == "market_data_stale" and e.symbol == "AAPL" for e in events
        )


class TestIdleTickDoesNotCreateASession:
    async def test_empty_watchlist_never_touches_session_state(self):
        store = InMemoryStateStore()
        await store.initialize()  # creates today's session once, at boot
        sessions_before = len(await store.list_sessions())
        feed = FakeMarketDataFeed()

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        # No additional session created by ticking with nothing armed.
        assert len(await store.list_sessions()) == sessions_before

    async def test_all_disarmed_never_touches_session_state(self):
        store = InMemoryStateStore()
        await store.initialize()
        await store.add_watchlist_symbol("AAPL", armed=False)
        sessions_before = len(await store.list_sessions())
        feed = FakeMarketDataFeed()

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        assert len(await store.list_sessions()) == sessions_before


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


class TestMarketDataStaleness:
    """D-005: staleness transitions are surfaced as audit events, once per
    transition, not once per tick."""

    async def test_stale_snapshot_writes_one_event(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", stale=True)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)
        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        events = await store.list_events()
        stale_events = [e for e in events if e.event_type == "market_data_stale"]
        assert len(stale_events) == 1  # not one per tick
        assert stale_events[0].symbol == "AAPL"

    async def test_recovery_writes_a_recovered_event(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", stale=True)
        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        feed.set_snapshot("AAPL", **_HEALTHY, stale=False)
        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        events = await store.list_events()
        assert any(
            e.event_type == "market_data_recovered" and e.symbol == "AAPL"
            for e in events
        )

    async def test_never_stale_writes_no_events(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", **_HEALTHY, stale=False)

        await run_strategy_tick(store, feed, Settings(), now=_PRE_MARKET_NOW)

        events = await store.list_events()
        assert not any(
            e.event_type in ("market_data_stale", "market_data_recovered")
            for e in events
        )


class TestStaleStateCache:
    """The in-memory stale_state cache (perf fix: avoids a full list_events()
    scan every tick) must produce IDENTICAL results to the event-log fallback,
    and stay correctly pruned as symbols come and go."""

    async def test_cache_produces_same_result_as_event_log_fallback(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", stale=True)
        cache: dict[str, bool] = {}

        # Tick 1: becomes stale -> one event, cache updated.
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=cache
        )
        assert cache == {"AAPL": True}
        stale_events = [
            e for e in await store.list_events() if e.event_type == "market_data_stale"
        ]
        assert len(stale_events) == 1

        # Tick 2: still stale, using the CACHE (not the event log) -> no new event.
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=cache
        )
        stale_events = [
            e for e in await store.list_events() if e.event_type == "market_data_stale"
        ]
        assert len(stale_events) == 1  # unchanged

        # Tick 3: recovers -> one recovered event, cache flips.
        feed.set_snapshot("AAPL", **_HEALTHY, stale=False)
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=cache
        )
        assert cache == {"AAPL": False}
        recovered = [
            e
            for e in await store.list_events()
            if e.event_type == "market_data_recovered"
        ]
        assert len(recovered) == 1

    async def test_cache_and_no_cache_agree_across_ticks(self):
        """Two independent stores/feeds, one driven with a cache and one
        without, must reach the same final event counts."""

        async def _drive(cache):
            store = await _armed_store("AAPL")
            feed = FakeMarketDataFeed()
            await feed.subscribe(["AAPL"])
            feed.set_snapshot("AAPL", stale=True)
            await run_strategy_tick(
                store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=cache
            )
            await run_strategy_tick(
                store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=cache
            )
            feed.set_snapshot("AAPL", **_HEALTHY, stale=False)
            await run_strategy_tick(
                store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=cache
            )
            events = await store.list_events()
            return (
                len([e for e in events if e.event_type == "market_data_stale"]),
                len([e for e in events if e.event_type == "market_data_recovered"]),
            )

        with_cache = await _drive({})
        without_cache = await _drive(None)
        assert with_cache == without_cache == (1, 1)

    async def test_fresh_cache_after_restart_seeds_from_log_no_duplicate(self):
        """F-007: on the first tick after a process restart the in-memory cache
        is a non-None but EMPTY dict. An already-stale feed (its
        market_data_stale already in the durable log) must NOT be re-announced —
        the empty cache is seeded from the log for unknown symbols first."""

        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", stale=True)

        # Pre-restart process: records the stale transition in its own cache.
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state={}
        )
        stale = [
            e for e in await store.list_events() if e.event_type == "market_data_stale"
        ]
        assert len(stale) == 1

        # Restart: a brand-new empty cache, feed still stale -> NO duplicate.
        fresh_cache: dict[str, bool] = {}
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=fresh_cache
        )
        stale = [
            e for e in await store.list_events() if e.event_type == "market_data_stale"
        ]
        assert len(stale) == 1  # not re-announced
        assert fresh_cache["AAPL"] is True  # seeded from the durable log

    async def test_fresh_cache_after_restart_still_detects_recovery(self):
        """After a restart-seed, a stale->healthy transition is still surfaced
        exactly once (the seed establishes the correct prior baseline)."""

        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", stale=True)
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state={}
        )

        # Restart with an empty cache; feed has since recovered.
        feed.set_snapshot("AAPL", **_HEALTHY, stale=False)
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state={}
        )
        recovered = [
            e
            for e in await store.list_events()
            if e.event_type == "market_data_recovered"
        ]
        assert len(recovered) == 1

    async def test_cache_is_pruned_when_symbol_unsubscribed(self):
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        feed.set_snapshot("AAPL", stale=True)
        cache: dict[str, bool] = {}
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=cache
        )
        assert "AAPL" in cache

        await store.set_watchlist_armed("AAPL", False)  # disarm -> unsubscribed
        await run_strategy_tick(
            store, feed, Settings(), now=_PRE_MARKET_NOW, stale_state=cache
        )

        assert "AAPL" not in cache  # pruned, not leaked forever

    async def _count_list_events_over_ticks(self, stale: bool) -> int:
        store = await _armed_store("AAPL")
        feed = FakeMarketDataFeed()
        await feed.subscribe(["AAPL"])
        if stale:
            feed.set_snapshot("AAPL", stale=True)
        else:
            feed.set_snapshot("AAPL", **_HEALTHY, stale=False)

        list_events_calls = 0
        orig_list_events = store.list_events

        async def counting_list_events(*args, **kwargs):
            nonlocal list_events_calls
            list_events_calls += 1
            return await orig_list_events(*args, **kwargs)

        store.list_events = counting_list_events

        settings = Settings(strategy_decision_cadence_seconds=0.01)
        task = asyncio.create_task(strategy_loop(store, feed, settings))
        try:
            await asyncio.sleep(0.06)  # several ticks
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        return list_events_calls

    async def test_loop_owns_a_persistent_cache_across_ticks(self):
        """strategy_loop itself (not just run_strategy_tick) must carry the
        cache across iterations. The event log is read exactly ONCE — the first
        tick seeds the empty cache from the durable log for the not-yet-observed
        symbol (the F-007 restart seed) — and never again. A per-tick full scan
        (the perf regression this guards) would make this grow with ticks."""

        assert await self._count_list_events_over_ticks(stale=True) == 1

    async def test_healthy_symbol_does_not_rescan_the_log_every_tick(self):
        """Regression guard for the F-007 seed: a never-stale symbol has no
        staleness event, so it must still be cached (as a healthy baseline) on
        the first seed — otherwise it stays 'unknown' and forces a full
        list_events() scan on EVERY tick. With several ticks running, the log is
        read exactly once, not once per tick."""

        assert await self._count_list_events_over_ticks(stale=False) == 1


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


async def test_outer_loop_survives_a_whole_tick_failure_and_continues():
    """A whole-TICK failure (e.g. the store itself raising, not just one
    symbol's evaluation) must not kill the background task — this exercises
    strategy_loop's own `except Exception: continue` guard, distinct from
    run_strategy_tick's per-symbol try/except covered above."""

    store = await _armed_store("AAPL")
    feed = FakeMarketDataFeed()
    await feed.subscribe(["AAPL"])
    feed.set_snapshot("AAPL", **_HEALTHY)

    orig_list_watchlist = store.list_watchlist
    call_count = 0

    async def flaky_list_watchlist(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated whole-tick failure")
        return await orig_list_watchlist(*args, **kwargs)

    store.list_watchlist = flaky_list_watchlist

    settings = Settings(strategy_decision_cadence_seconds=0.01)
    task = asyncio.create_task(strategy_loop(store, feed, settings))
    try:
        await asyncio.sleep(0.05)  # let several ticks happen, including the failure
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task  # would re-raise RuntimeError here if the loop hadn't
            # caught it — suppress() only swallows CancelledError

    assert call_count >= 2  # the loop kept ticking past the first failure
    assert task.cancelled()  # torn down cleanly by our cancel(), not crashed
