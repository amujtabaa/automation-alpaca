"""FastAPI application — the single async process that owns and persists truth.

A ``StateStore`` is created at startup (SQLite for the running app, in-memory
when tests pass one in), its schema is initialized idempotently, and it is held
on ``app.state`` for the process lifetime. There is **no background monitoring
task** in this phase: nothing to monitor exists until the Market Data Service
(Phase 4) and Strategy Engine (Phase 5) are built, so stubbing a loop now would
be guessing at a shape we don't know (per the implementation prompt). The
lock-guarded concurrency pattern is demonstrated through the StateStore.
"""

from __future__ import annotations

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
from app.config import load_settings
from app.store import create_state_store
from app.store.base import StateStore


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
        try:
            yield
        finally:
            if owns_store:
                await active_store.close()

    app = FastAPI(
        title="Alpaca Clean-Sheet CAPI Option 2.5 — Backend",
        version=__version__,
        summary="Paper-first durable engine. No live trading, no Alpaca calls yet.",
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
