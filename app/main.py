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

The lock-guarded concurrency model still holds: the loop and the request
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
    routes_review,
    routes_system,
    routes_trading,
    routes_watchlist,
)
from app.approval.human import HumanApprovalGate
from app.broker import create_broker_adapter
from app.config import load_settings
from app.monitoring import monitoring_loop
from app.store import create_state_store
from app.store.base import StateStore

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
        app.state.approval_gate = HumanApprovalGate(active_store)
        app.state.broker_adapter = create_broker_adapter(settings)

        monitor_task: Optional[asyncio.Task] = None
        if settings.enable_monitoring:
            monitor_task = asyncio.create_task(
                monitoring_loop(active_store, app.state.broker_adapter, settings),
                name="monitoring-loop",
            )
        try:
            yield
        finally:
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
    # DEV/MOCK scaffolding — mounted only when enabled (default on in beta so the
    # candidate flow is exercisable; ENABLE_DEV_ROUTES=false keeps it off).
    if settings.enable_dev_routes:
        app.include_router(routes_dev.router)

    return app


# Module-level app for `uvicorn app.main:app`.
app = create_app()
