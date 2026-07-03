"""FastAPI application — the single async process that owns and persists truth.

A ``StateStore`` is created at startup (SQLite for the running app, in-memory
when tests pass one in), its schema is initialized idempotently, and it is held
on ``app.state`` for the process lifetime.

Phase 4 adds two startup-owned collaborators on ``app.state``:

* a **BrokerAdapter** (paper-only Alpaca adapter when credentials are present,
  otherwise an IO-free mock), and
* a single **background monitoring task** running :func:`app.monitoring.monitoring_loop`
  — the first real background loop in the project. It submits approved orders to
  the broker and reconciles fills on a fixed cadence (D-011). The task is
  cancelled and awaited on shutdown so nothing is left dangling.

Phase 5 adds two more:

* a **MarketDataService** (real Alpaca SIP stream when credentials are present,
  otherwise an IO-free fake) with its own background **feed task** running
  :meth:`~app.marketdata.service.MarketDataService.run` (the connection/reconnect
  lifecycle), and
* a single **background strategy task** running :func:`app.strategy_loop.strategy_loop`
  — evaluates armed watchlist symbols on a fixed decision cadence and creates
  candidates (D-005's ingestion/decision cadence split). Shut down in dependency
  order on exit: strategy task first (it calls into the feed every tick), then
  the feed (``stop()`` then cancel, so a real websocket gets a clean close
  signal rather than only a bare task cancellation), then the order-monitoring
  task — all awaited so nothing is left dangling before the store closes.

The lock-guarded concurrency model still holds: the loops and the request
handlers share one ``StateStore`` whose mutating operations are serialized.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from app import __version__
from app.api import (
    routes_candidates,
    routes_controls,
    routes_dev,
    routes_marketdata,
    routes_review,
    routes_system,
    routes_trading,
    routes_watchlist,
)
from app.approval.human import HumanApprovalGate
from app.broker import create_broker_adapter
from app.config import load_settings
from app.marketdata import create_market_data_service
from app.monitoring import monitoring_loop
from app.store import create_state_store
from app.store.base import StateStore
from app.strategy_loop import strategy_loop

_log = logging.getLogger(__name__)


def create_app(store: Optional[StateStore] = None) -> FastAPI:
    """Build the FastAPI app.

    If ``store`` is provided (tests), it is used as-is; otherwise the configured
    implementation is built from the environment. A store we create is closed on
    shutdown; an injected one is left to its owner.
    """

    owns_store = store is None
    settings = load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_store = store or create_state_store(settings)
        await active_store.initialize()
        app.state.store = active_store
        app.state.settings = settings
        app.state.approval_gate = HumanApprovalGate(active_store)
        app.state.broker_adapter = create_broker_adapter(settings)
        app.state.market_data = create_market_data_service(settings)

        monitor_task: Optional[asyncio.Task] = None
        if settings.enable_monitoring:
            monitor_task = asyncio.create_task(
                monitoring_loop(active_store, app.state.broker_adapter, settings),
                name="monitoring-loop",
            )
        # The feed's own connection/reconnect lifecycle runs for the process
        # lifetime, independent of whether the strategy loop is enabled — other
        # future consumers (e.g. a Position Monitor P/L feed) can read snapshots
        # off it without the strategy loop existing.
        feed_task = asyncio.create_task(
            app.state.market_data.run(), name="market-data-feed"
        )
        strategy_task: Optional[asyncio.Task] = None
        if settings.enable_strategy_engine:
            strategy_task = asyncio.create_task(
                strategy_loop(active_store, app.state.market_data, settings),
                name="strategy-loop",
            )
        try:
            yield
        finally:
            # Shutdown in dependency order: the strategy loop calls into the
            # feed every tick, so stop it first; then release the feed itself
            # (stop() gives a real websocket a clean close signal, not just a
            # bare task cancellation) before falling back to cancel; then the
            # independent order-monitoring task.
            if strategy_task is not None:
                strategy_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await strategy_task
            await app.state.market_data.stop()
            feed_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await feed_task
            if monitor_task is not None:
                monitor_task.cancel()
                # Await the cancellation so the task is fully torn down before
                # the store closes — no "task was destroyed but pending" noise.
                with contextlib.suppress(asyncio.CancelledError):
                    await monitor_task
            if owns_store:
                await active_store.close()

    app = FastAPI(
        title="Alpaca Clean-Sheet CAPI Option 2.5 — Backend",
        version=__version__,
        summary="Paper-first durable engine. Alpaca paper only — no live trading.",
        lifespan=lifespan,
    )

    app.include_router(routes_system.router)
    app.include_router(routes_watchlist.router)
    app.include_router(routes_candidates.router)
    app.include_router(routes_trading.router)
    app.include_router(routes_controls.router)
    app.include_router(routes_review.router)
    app.include_router(routes_marketdata.router)
    # DEV/MOCK scaffolding — mounted only when enabled (default on in beta so the
    # candidate flow is exercisable; ENABLE_DEV_ROUTES=false keeps it off).
    if settings.enable_dev_routes:
        app.include_router(routes_dev.router)

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app()
