"""Backend configuration, sourced from the environment.

Deliberately dependency-light (plain ``os.environ`` rather than
pydantic-settings) so the skeleton has no extra runtime dependency.

Phase 4 introduces the first credentials this project reads: **paper-only**
Alpaca keys (``ALPACA_PAPER_API_KEY`` / ``ALPACA_PAPER_API_SECRET``). There is
intentionally no live-key variable anywhere — the adapter only ever builds a
*paper* TradingClient (Rules 1-3, ``docs/01_ARCHITECTURE.md``). Keys are read
here but never logged; ``.env`` (gitignored) holds the real values.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Which StateStore implementation the running app uses.
#   "sqlite" -> SqliteStateStore (durable, default for the app)
#   "memory" -> InMemoryStateStore (used by tests; chosen via env there)
STATE_STORE_ENV = "STATE_STORE"
DB_PATH_ENV = "ALPACA_DB_PATH"
DEV_ROUTES_ENV = "ENABLE_DEV_ROUTES"

# Phase 4 — Alpaca Paper Adapter + monitoring loop.
# Credentials are PAPER ONLY (Rules 1-3). There is intentionally no live-key
# env var anywhere; the adapter only ever constructs a paper TradingClient.
ALPACA_KEY_ENV = "ALPACA_PAPER_API_KEY"
ALPACA_SECRET_ENV = "ALPACA_PAPER_API_SECRET"
POLL_CADENCE_ENV = "ALPACA_POLL_CADENCE_SECONDS"
UNFILLED_TIMEOUT_ENV = "ALPACA_UNFILLED_TIMEOUT_MINUTES"
# Which BrokerAdapter the running app uses:
#   "auto"   -> AlpacaPaperAdapter when both paper keys are present, else mock
#   "mock"   -> MockBrokerAdapter always (no network; default-safe for dev/CI)
#   "alpaca" -> AlpacaPaperAdapter always (requires paper keys)
BROKER_ENV = "BROKER_ADAPTER"
ENABLE_MONITORING_ENV = "ENABLE_MONITORING"

# Phase 5 — Market Data Service + Strategy Engine. Same paper-only Alpaca
# credentials as Phase 4 (the data subscription is independent of paper vs.
# live trading mode, per docs/02_DATA_AND_PERSISTENCE.md) — no new creds.
MARKET_DATA_FEED_ENV = "MARKET_DATA_FEED"  # "auto" | "mock" | "alpaca"
MARKET_DATA_STALE_MINUTES_ENV = "MARKET_DATA_STALE_MINUTES"
ENABLE_STRATEGY_ENGINE_ENV = "ENABLE_STRATEGY_ENGINE"
STRATEGY_DECISION_CADENCE_ENV = "STRATEGY_DECISION_CADENCE_SECONDS"
STRATEGY_MOMENTUM_THRESHOLD_ENV = "STRATEGY_MOMENTUM_THRESHOLD_PCT"
STRATEGY_MIN_VOLUME_ENV = "STRATEGY_MIN_VOLUME"
STRATEGY_MAX_SPREAD_ENV = "STRATEGY_MAX_SPREAD_PCT"
STRATEGY_LIMIT_BUFFER_ENV = "STRATEGY_LIMIT_BUFFER_PCT"
STRATEGY_DEFAULT_QUANTITY_ENV = "STRATEGY_DEFAULT_QUANTITY"

DEFAULT_DB_PATH = "./data/app.db"
DEFAULT_POLL_CADENCE_SECONDS = 15.0
DEFAULT_UNFILLED_TIMEOUT_MINUTES = 60.0
DEFAULT_MARKET_DATA_STALE_MINUTES = 5.0
DEFAULT_STRATEGY_DECISION_CADENCE_SECONDS = 5.0
DEFAULT_STRATEGY_MOMENTUM_THRESHOLD_PCT = 3.0
DEFAULT_STRATEGY_MIN_VOLUME = 50_000.0
DEFAULT_STRATEGY_MAX_SPREAD_PCT = 1.0
DEFAULT_STRATEGY_LIMIT_BUFFER_PCT = 0.1
DEFAULT_STRATEGY_DEFAULT_QUANTITY = 10

_FALSEY = {"false", "0", "no", "off"}


@dataclass(frozen=True)
class Settings:
    """Resolved, immutable backend settings."""

    state_store: str = "sqlite"
    db_path: str = DEFAULT_DB_PATH
    # Whether the DEV/MOCK scaffolding routes (e.g. POST /api/dev/candidates) are
    # mounted. On by default so the candidate flow is exercisable in beta; set
    # ``ENABLE_DEV_ROUTES=false`` to keep the mock-injection path off a given
    # deployment. Phase 5's real Strategy Engine removes the need for it.
    enable_dev_routes: bool = True

    # --- Phase 4: broker + monitoring loop ------------------------------- #
    # Paper-only credentials. ``None`` when unset (dev/CI). ``repr=False`` keeps
    # them out of any ``repr(settings)``/log line as defense-in-depth — they are
    # never intentionally logged anywhere.
    alpaca_api_key: Optional[str] = field(default=None, repr=False)
    alpaca_api_secret: Optional[str] = field(default=None, repr=False)
    # "auto" | "mock" | "alpaca" — see BROKER_ENV above.
    broker_adapter: str = "auto"
    # How often the monitoring loop submits pending orders + reconciles open
    # ones (D-011: REST polling, not websocket).
    poll_cadence_seconds: float = DEFAULT_POLL_CADENCE_SECONDS
    # An open order older than this is surfaced as a stale ``order_stale`` audit
    # event (D-011: surface only, no auto-cancel).
    unfilled_timeout_minutes: float = DEFAULT_UNFILLED_TIMEOUT_MINUTES
    # Whether the background monitoring loop starts at app startup.
    enable_monitoring: bool = True

    # --- Phase 5: market data + strategy loop ----------------------------- #
    # "auto" | "mock" | "alpaca" — see MARKET_DATA_FEED_ENV above.
    market_data_feed: str = "auto"
    # How long the feed may be disconnected before affected snapshots are
    # marked stale (D-005: never silently serve a stale snapshot as current).
    market_data_stale_minutes: float = DEFAULT_MARKET_DATA_STALE_MINUTES
    # Whether the background strategy loop starts at app startup.
    enable_strategy_engine: bool = True
    # How often armed watchlist symbols are re-evaluated against the current
    # snapshot (D-005: decision cadence, distinct from the ingestion stream and
    # from Phase 4's order-poll cadence).
    strategy_decision_cadence_seconds: float = DEFAULT_STRATEGY_DECISION_CADENCE_SECONDS
    # First strategy target's thresholds (D-014b: placeholder, not CAPI).
    strategy_momentum_threshold_pct: float = DEFAULT_STRATEGY_MOMENTUM_THRESHOLD_PCT
    strategy_min_volume: float = DEFAULT_STRATEGY_MIN_VOLUME
    strategy_max_spread_pct: float = DEFAULT_STRATEGY_MAX_SPREAD_PCT
    strategy_limit_buffer_pct: float = DEFAULT_STRATEGY_LIMIT_BUFFER_PCT
    strategy_default_quantity: int = DEFAULT_STRATEGY_DEFAULT_QUANTITY

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)

    @property
    def has_alpaca_credentials(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_api_secret)


def _env_float(name: str, default: float, *, minimum: Optional[float] = None) -> float:
    """Parse a float env var, falling back to ``default`` if unset/blank.

    A non-numeric value, a non-finite one (``NaN``/``Inf``), or one below
    ``minimum`` raises ``ValueError`` — a misconfigured cadence should fail fast
    at startup. ``float()`` accepts ``"nan"``/``"inf"`` and they slip past a bare
    ``< minimum`` guard (``nan < x`` and ``inf < x`` are both ``False``); left in,
    a ``NaN`` cadence makes the monitoring loop's ``asyncio.sleep(nan)`` never
    fire (the loop silently stalls), and an infinite timeout disables stale-order
    surfacing — both rejected here (BE-1).
    """

    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _env_int(name: str, default: int, *, minimum: Optional[int] = None) -> int:
    """Parse an integer env var via :func:`_env_float`, then require it be whole.

    Reuses the non-finite/minimum validation rather than duplicating it;
    rejects a fractional value explicitly (e.g. ``"2.5"``) instead of silently
    truncating it, which would otherwise hide a likely typo.
    """

    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    value = _env_float(name, float(default), minimum=minimum)
    if not value.is_integer():
        raise ValueError(f"{name} must be a whole number, got {value}")
    return int(value)


def load_settings() -> Settings:
    """Build :class:`Settings` from the current environment.

    ``STATE_STORE`` defaults to ``sqlite`` for the running app; tests set it to
    ``memory`` (and use the in-memory store directly), keeping unit tests
    IO-free per Rule 9.
    """

    state_store = os.environ.get(STATE_STORE_ENV, "sqlite").strip().lower()
    if state_store not in {"sqlite", "memory"}:
        raise ValueError(
            f"{STATE_STORE_ENV} must be 'sqlite' or 'memory', got {state_store!r}"
        )
    db_path = os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH).strip() or DEFAULT_DB_PATH

    def _clean(name: str) -> Optional[str]:
        raw = os.environ.get(name)
        return raw.strip() if raw and raw.strip() else None

    alpaca_api_key = _clean(ALPACA_KEY_ENV)
    alpaca_api_secret = _clean(ALPACA_SECRET_ENV)
    has_creds = bool(alpaca_api_key and alpaca_api_secret)

    # DEV/MOCK candidate-injection routes. Explicit ENABLE_DEV_ROUTES always wins.
    # When unset, the default is *credential-aware* (SECOPS-1): OFF once real paper
    # keys are configured (don't expose a mock-injection surface alongside a live
    # paper broker), ON otherwise so credential-free dev can still exercise the
    # candidate flow.
    dev_raw = os.environ.get(DEV_ROUTES_ENV)
    if dev_raw is None or not dev_raw.strip():
        enable_dev_routes = not has_creds
    else:
        enable_dev_routes = dev_raw.strip().lower() not in _FALSEY

    broker_adapter = os.environ.get(BROKER_ENV, "auto").strip().lower()
    if broker_adapter not in {"auto", "mock", "alpaca"}:
        raise ValueError(
            f"{BROKER_ENV} must be 'auto', 'mock', or 'alpaca', got {broker_adapter!r}"
        )
    # Cadence must be strictly positive (a zero/negative sleep would busy-loop);
    # the timeout may be 0 (treats any open order as immediately stale).
    poll_cadence = _env_float(
        POLL_CADENCE_ENV, DEFAULT_POLL_CADENCE_SECONDS, minimum=0.001
    )
    unfilled_timeout = _env_float(
        UNFILLED_TIMEOUT_ENV, DEFAULT_UNFILLED_TIMEOUT_MINUTES, minimum=0.0
    )
    enable_monitoring = (
        os.environ.get(ENABLE_MONITORING_ENV, "true").strip().lower() not in _FALSEY
    )

    market_data_feed = os.environ.get(MARKET_DATA_FEED_ENV, "auto").strip().lower()
    if market_data_feed not in {"auto", "mock", "alpaca"}:
        raise ValueError(
            f"{MARKET_DATA_FEED_ENV} must be 'auto', 'mock', or 'alpaca', "
            f"got {market_data_feed!r}"
        )
    market_data_stale_minutes = _env_float(
        MARKET_DATA_STALE_MINUTES_ENV, DEFAULT_MARKET_DATA_STALE_MINUTES, minimum=0.0
    )
    enable_strategy_engine = (
        os.environ.get(ENABLE_STRATEGY_ENGINE_ENV, "true").strip().lower()
        not in _FALSEY
    )
    strategy_decision_cadence = _env_float(
        STRATEGY_DECISION_CADENCE_ENV,
        DEFAULT_STRATEGY_DECISION_CADENCE_SECONDS,
        minimum=0.001,
    )
    strategy_momentum_threshold = _env_float(
        STRATEGY_MOMENTUM_THRESHOLD_ENV,
        DEFAULT_STRATEGY_MOMENTUM_THRESHOLD_PCT,
        minimum=0.0,
    )
    strategy_min_volume = _env_float(
        STRATEGY_MIN_VOLUME_ENV, DEFAULT_STRATEGY_MIN_VOLUME, minimum=0.0
    )
    strategy_max_spread = _env_float(
        STRATEGY_MAX_SPREAD_ENV, DEFAULT_STRATEGY_MAX_SPREAD_PCT, minimum=0.0
    )
    strategy_limit_buffer = _env_float(
        STRATEGY_LIMIT_BUFFER_ENV, DEFAULT_STRATEGY_LIMIT_BUFFER_PCT, minimum=0.0
    )
    strategy_default_quantity = _env_int(
        STRATEGY_DEFAULT_QUANTITY_ENV, DEFAULT_STRATEGY_DEFAULT_QUANTITY, minimum=1
    )

    return Settings(
        state_store=state_store,
        db_path=db_path,
        enable_dev_routes=enable_dev_routes,
        alpaca_api_key=alpaca_api_key,
        alpaca_api_secret=alpaca_api_secret,
        broker_adapter=broker_adapter,
        poll_cadence_seconds=poll_cadence,
        unfilled_timeout_minutes=unfilled_timeout,
        enable_monitoring=enable_monitoring,
        market_data_feed=market_data_feed,
        market_data_stale_minutes=market_data_stale_minutes,
        enable_strategy_engine=enable_strategy_engine,
        strategy_decision_cadence_seconds=strategy_decision_cadence,
        strategy_momentum_threshold_pct=strategy_momentum_threshold,
        strategy_min_volume=strategy_min_volume,
        strategy_max_spread_pct=strategy_max_spread,
        strategy_limit_buffer_pct=strategy_limit_buffer,
        strategy_default_quantity=strategy_default_quantity,
    )
