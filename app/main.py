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
from fastapi.responses import JSONResponse

from app import __version__
from app.api import (
    routes_candidates,
    routes_controls,
    routes_dev,
    routes_marketdata,
    routes_review,
    routes_signals,
    routes_system,
    routes_trading,
    routes_watchlist,
)
from app.api.deps import (
    DEFAULT_ACTOR,
    OPERATOR_KEY_HEADER,
    PRODUCER_KEY_HEADER,
    operator_key_valid,
    producer_key_valid,
)
from app.approval.human import HumanApprovalGate
from app.broker.factory import create_broker_adapter
from app.config import Settings, load_settings, operator_producer_key_overlap
from app.facade.signal_rails import is_conforming_rails
from app.launch_guard import is_sanctioned
from app.marketdata.factory import create_market_data_service
from app.monitoring import monitoring_loop, run_startup_reconcile
from app.store import create_state_store
from app.store.base import StateStore
from app.strategy_loop import strategy_loop

# Sensitive-route auth exemptions when the Signal Seat flag is on (ADR-009 A-1a):
# health is the only public route; the producer route enforces its own producer
# credential via route deps, so the operator-enforcement middleware skips it.
_PUBLIC_PATHS = frozenset({"/api/health"})
# The producer ingest route is EXACTLY POST /api/signals — the only route the
# operator-enforcement middleware skips (producer-credentialed). Everything else
# under /api/signals* (the GET list, WO-0103's approve/reject) is operator-only
# and must pass through the middleware so authenticated_actor is stamped.
_PRODUCER_INGEST_PATH = "/api/signals"

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
    shutdown; an injected one is left to its owner. ``settings`` may be injected
    (tests); otherwise it is loaded from the environment.

    **ADR-009 A-1 clause 6 (REV-0025-F-001) — construction-time bind boundary.**
    With ``signal_seat_enabled`` on, the app may be built ONLY through the
    backend-owned launcher (``app/server.py`` / ``python -m app``), which mints a
    launch-provenance capability and passes it here. Constructing without that
    capability RAISES — so a bare ``uvicorn app.main:app`` (which imports the
    module-level ``app`` with no capability) fails at import and never opens a
    listener. This is the primary control; the request-time 503 guard is
    defense-in-depth. Flag OFF ⇒ construction is unrestricted (unchanged beta).
    """

    owns_store = store is None
    if settings is None:
        settings = load_settings()

    # ADR-009 A-1/A-4 construction-time guards, in force ONLY when the flag is on.
    # These are STANDING invariants: the seat is structurally un-enable-able until
    # the launcher (capability), the operator+producer credentials, and WO-0104's
    # real rails are ALL wired. Flag off ⇒ none apply (beta dev unchanged).
    sanctioned = is_sanctioned(launch_capability)
    if settings.signal_seat_enabled:
        # (1) A-1 clause 6 — no listener without the backend-owned launcher.
        if not sanctioned:
            raise RuntimeError(
                "signal_seat_enabled requires the backend-owned launcher "
                "(`python -m app`); constructing the app without a launch "
                "capability is unsupported for the enabled seat, so a bare "
                "`uvicorn app.main:app` cannot serve it (ADR-009 A-1 clause 6)."
            )
        # (2) A-1.4 credential-presence — else every sensitive route is a
        # permanent 401 with no credential to supply (the lockout A-1 forbids).
        if not settings.operator_api_key or not settings.signal_producer_keys:
            raise RuntimeError(
                "signal_seat_enabled requires OPERATOR_API_KEY and a non-empty "
                "SIGNAL_PRODUCER_KEYS map (ADR-009 A-1 credential-presence guard)."
            )
        # (2b) A-1 role separation — re-checked HERE, not only in load_settings, so
        # an INJECTED Settings (constructed directly, bypassing load_settings)
        # cannot ship an operator key that equals a producer key. Otherwise that
        # producer could present its own secret as X-Operator-Key and pass every
        # operator-only route, defeating the producer/operator split (round 10).
        if operator_producer_key_overlap(
            settings.operator_api_key, settings.signal_producer_keys
        ):
            raise RuntimeError(
                "signal_seat_enabled forbids OPERATOR_API_KEY equal to any "
                "SIGNAL_PRODUCER_KEYS entry (ADR-009 A-1 role separation)."
            )
        # (3) A-4 rails-presence — the seat cannot run without finite-audit flood
        # protection. WO-0104 SATISFIES this by wiring the real provider; a fake
        # is confined to a test-only construction path production cannot select.
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
        # Signal Seat rails seam (ADR-009 A-4). None when the flag is off; the
        # rails-presence guard above guarantees a conforming provider when on.
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

    # ADR-009 A-1.5: with the flag on, FastAPI's auto-docs routes are DISABLED —
    # they disclose the API surface to reachable producers (never public). Flag
    # off keeps FastAPI's defaults.
    docs_on = not settings.signal_seat_enabled
    app = FastAPI(
        title="Alpaca Clean-Sheet CAPI Option 2.5 — Backend",
        version=__version__,
        summary="Paper-first durable engine. Alpaca paper only — no live trading.",
        lifespan=lifespan,
        docs_url="/docs" if docs_on else None,
        redoc_url="/redoc" if docs_on else None,
        openapi_url="/openapi.json" if docs_on else None,
    )

    if settings.signal_seat_enabled:
        # ADR-009 A-1 fail-closed request guard (defense-in-depth, runs regardless
        # of --lifespan): if a flag-on app were ever constructed without the launch
        # capability, every request is refused. The construction refusal above is
        # the PRIMARY control; this is the backstop.
        @app.middleware("http")
        async def _fail_closed_launch_guard(request, call_next):
            if not sanctioned:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "signal seat not sanctioned (A-1)"},
                )
            return await call_next(request)

        # ADR-009 A-1a: with the flag on, EVERY sensitive route — reads included —
        # requires the operator credential, EXCEPT public health and the producer
        # route (which enforces its own producer credential via route deps). This
        # is the auth flip that lands WITH the flag; the cockpit sends
        # X-Operator-Key from the same change so the operator is never locked out.
        @app.middleware("http")
        async def _operator_enforcement(request, call_next):
            path = request.url.path
            # Skip ONLY the exact producer ingest route (POST /api/signals), which
            # carries its own producer credential — NOT the whole /api/signals*
            # subtree. A broad startswith() skip would leave WO-0103's operator-only
            # POST /api/signals/{producer}/{signal}/approve|reject unauthenticated
            # by this middleware AND, worse, never stamp request.state.authenticated_actor
            # — so get_actor would fall back to the caller-controlled X-Actor and the
            # approval audit (who authorized a real order) would be spoofable, exactly
            # the round-5 hole. GET /api/signals + the future approve/reject routes go
            # through the operator branch below (independent review F-1).
            is_producer_ingest = request.method == "POST" and path == _PRODUCER_INGEST_PATH
            if path in _PUBLIC_PATHS or is_producer_ingest:
                return await call_next(request)
            if path.startswith("/api"):
                if operator_key_valid(
                    request.headers.get(OPERATOR_KEY_HEADER), settings
                ):
                    # A-1: the audited actor derives from the authenticated
                    # principal, not a caller-controlled X-Actor header. Stamp it
                    # so get_actor binds kill-switch/flatten/etc. audit to the
                    # operator and demotes X-Actor to an optional sub-label
                    # (auto-review round 5 P1).
                    request.state.authenticated_actor = DEFAULT_ACTOR
                    return await call_next(request)
                # A VALID producer key on an operator route is the wrong-role
                # 403; an unknown/garbage X-Producer-Key is an unrecognized
                # credential -> 401 (A-1 matrix: invalid credentials are 401,
                # not 403). Presence alone must NOT earn a 403.
                if producer_key_valid(
                    request.headers.get(PRODUCER_KEY_HEADER), settings
                ):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "producer credential is not valid for this "
                            "operator route"
                        },
                    )
                return JSONResponse(
                    status_code=401,
                    content={"detail": "operator credential required"},
                )
            return await call_next(request)

    app.include_router(routes_system.router)
    app.include_router(routes_watchlist.router)
    app.include_router(routes_candidates.router)
    app.include_router(routes_trading.router)
    app.include_router(routes_controls.router)
    app.include_router(routes_review.router)
    app.include_router(routes_marketdata.router)
    # Signal Seat routes — mounted ONLY when the flag is on (flag off ⇒ 404, no
    # auth surface, no store writes possible).
    if settings.signal_seat_enabled:
        app.include_router(routes_signals.router)
    # DEV/MOCK scaffolding — mounted only when enabled (default on in beta so the
    # candidate flow is exercisable; ENABLE_DEV_ROUTES=false keeps it off).
    if settings.enable_dev_routes:
        app.include_router(routes_dev.router)

    return app


# Module-level app for the bare `uvicorn app.main:app` dev command (ADR-009 A-1
# clause 6 / slice-1 bug fix). Importing this module (and ``create_app``) must NOT
# raise under the flag — the backend-owned launcher (`app/server.py`) needs to
# import ``create_app`` to build its OWN capability-bearing app. So:
#   * flag OFF  → define the module-level ``app`` (bare uvicorn works unchanged);
#   * flag ON   → do NOT define ``app`` at all (no assignment, not even ``None``).
#     Setting it to ``None`` is INSUFFICIENT (auto-reviewer P1 #7, empirically
#     reproduced): uvicorn's ``getattr(module, "app")`` would happily return
#     ``None``, pass Config.load()'s `self.loaded_app = self.loaded_app()` /
#     ASGI-interface checks in a way that still lets the server bind a socket and
#     report "startup complete" while erroring per-request — the forbidden port
#     stays reachable (TCP accepts). Leaving the name UNDEFINED makes
#     ``uvicorn.importer.import_from_string``'s ``getattr(instance, attr_str)``
#     raise ``AttributeError`` -> ``ImportFromStringError`` inside
#     ``Config.load()``, which runs synchronously BEFORE ``Server._serve``/
#     ``startup()`` ever binds a listening socket — true pre-serve failure,
#     connection refused, nothing on the network port (REV-0025-F-002).
#     ``python -m app`` (the sanctioned launcher) never references this module
#     attribute — it calls ``create_app()`` directly with its own capability.
if not load_settings().signal_seat_enabled:
    app = create_app()
