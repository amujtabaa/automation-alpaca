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
from app.broker.factory import create_broker_adapter
from app.config import Settings, load_settings, validate_signal_seat_settings
from app.facade.signal_rails import is_conforming_rails
from app.launch_guard import is_sanctioned
from app.marketdata.factory import create_market_data_service
from app.monitoring import monitoring_loop, run_startup_reconcile
from app.store import create_state_store
from app.store.base import StateStore
from app.strategy_loop import strategy_loop

_log = logging.getLogger(__name__)


def create_app(
    store: Optional[StateStore] = None,
    *,
    settings: Optional[Settings] = None,
    launch_capability: object = None,
    signal_rails: object = None,
) -> FastAPI:
    """Build the FastAPI app.

    If ``store`` is provided (tests), it is used as-is; otherwise the configured
    implementation is built from the environment. A store we create is closed on
    shutdown; an injected one is left to its owner. Tests and the sanctioned
    launcher may inject resolved settings.

    Under the Signal Seat flag, construction requires the bind-bound launch
    capability carried forward from archive REV-0025-F-001 @
    origin/archive/claude-wo-0001-install-checks-2x5ys8, valid signal settings,
    and a conforming rails provider, in that order.
    """

    owns_store = store is None
    if settings is None:
        settings = load_settings()

    if settings.signal_seat_enabled:
        if not is_sanctioned(launch_capability):
            raise RuntimeError(
                "signal_seat_enabled requires the backend-owned launcher "
                "(`python -m app`); constructing without its launch capability "
                "is unsupported (ADR-009 A-1 clause 6)."
            )
        try:
            validate_signal_seat_settings(settings)
        except ValueError as exc:
            raise RuntimeError(f"signal_seat_enabled: {exc}") from exc
        if not is_conforming_rails(signal_rails):
            raise RuntimeError(
                "signal_seat_enabled requires a conforming signal rails provider "
                "(ADR-009 A-4 rails-presence guard); WO-0104 wires the real one."
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_store = store or create_state_store(settings)
        await active_store.initialize()
        app.state.store = active_store
        app.state.settings = settings
        if settings.signal_seat_enabled:
            app.state.signal_rails = signal_rails
        app.state.approval_gate = HumanApprovalGate(active_store)
        app.state.broker_adapter = create_broker_adapter(settings)
        app.state.market_data = create_market_data_service(settings)

        monitor_task: Optional[asyncio.Task] = None
        if settings.enable_monitoring:
            # Wave 4f / §7: gate trading behind a startup mass-status reconcile —
            # enter reduce-only (Reducing) until a reconcile pass confirms parity,
            # BEFORE the monitoring loop enables normal trading. Best-effort; the
            # loop keeps re-checking each tick.
            await run_startup_reconcile(
                active_store, app.state.broker_adapter, settings
            )
            monitor_task = asyncio.create_task(
                monitoring_loop(
                    active_store,
                    app.state.broker_adapter,
                    settings,
                    # Phase 7: the monitoring tick prices protective sells (§5.4)
                    # and supplies fill-price fallbacks (§7) off the live feed.
                    market_data=app.state.market_data,
                ),
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


# Module-level app for the bare `uvicorn app.main:app` development command.
# Flag off keeps the existing export. Flag on deliberately leaves the NAME
# undefined (not ``None``), so Uvicorn's import lookup fails synchronously before
# any socket binds. This preserves the construction-time control proven by
# archive REV-0025-F-002 @
# origin/archive/claude-wo-0001-install-checks-2x5ys8 while allowing
# ``app.server`` to import and call ``create_app`` directly.
_module_settings = load_settings()
if not _module_settings.signal_seat_enabled:
    app = create_app(settings=_module_settings)
del _module_settings
