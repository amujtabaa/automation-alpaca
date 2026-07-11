"""App-startup wiring for the Phase 5 market-data feed + strategy loop.

Drives ``app.router.lifespan_context`` directly (the same mechanism
``TestClient`` uses internally) rather than a live ``TestClient`` + real-clock
wait: no precedent exists in this suite for asserting on a live background
task's real-clock behavior (every existing monitoring-loop test either
bypasses the lifespan entirely or calls its tick function directly) — that
sync/async-threading combination is fragile to test deterministically. This
file instead asserts the wiring itself: the right collaborator is constructed
and attached to ``app.state``, and startup/shutdown completes cleanly (no
hang, no unsuppressed exception) under every ``enable_strategy_engine``
setting.
"""

from __future__ import annotations

import asyncio

import pytest

from app.config import Settings
from app.main import create_app
from app.marketdata.fake import FakeMarketDataFeed
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def test_market_data_service_attached_and_typed(monkeypatch):
    monkeypatch.delenv("MARKET_DATA_FEED", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_PAPER_API_SECRET", raising=False)
    app = create_app(InMemoryStateStore())

    async with app.router.lifespan_context(app):
        assert isinstance(app.state.market_data, FakeMarketDataFeed)
        # create_task only schedules the feed's run() — yield once so it
        # actually gets its first turn before asserting on it.
        await asyncio.sleep(0)
        assert app.state.market_data.run_started is True

    # Clean shutdown: stop() was called on the feed.
    assert app.state.market_data.stopped is True


async def test_strategy_engine_disabled_still_starts_and_stops_cleanly(monkeypatch):
    monkeypatch.setenv("ENABLE_STRATEGY_ENGINE", "false")
    app = create_app(InMemoryStateStore())

    async with app.router.lifespan_context(app):
        # The feed still runs even with the strategy loop disabled (a future
        # consumer, e.g. Position Monitor P/L, can read snapshots off it).
        await asyncio.sleep(0)
        assert app.state.market_data.run_started is True

    assert app.state.market_data.stopped is True


async def test_strategy_engine_enabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_STRATEGY_ENGINE", raising=False)
    settings = Settings()
    assert (
        settings.enable_strategy_engine is True
    )  # default-on, matches enable_monitoring


async def test_lifespan_completes_with_monitoring_and_strategy_both_disabled(
    monkeypatch,
):
    monkeypatch.setenv("ENABLE_MONITORING", "false")
    monkeypatch.setenv("ENABLE_STRATEGY_ENGINE", "false")
    app = create_app(InMemoryStateStore())

    async with app.router.lifespan_context(app):
        # The feed task still runs regardless (it's not gated by either flag).
        await asyncio.sleep(0)
        assert app.state.market_data.run_started is True

    assert app.state.market_data.stopped is True
