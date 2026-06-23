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

import os
from dataclasses import dataclass
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

DEFAULT_DB_PATH = "./data/app.db"
DEFAULT_POLL_CADENCE_SECONDS = 15.0
DEFAULT_UNFILLED_TIMEOUT_MINUTES = 60.0

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
    # Paper-only credentials. ``None`` when unset (dev/CI). Never logged.
    alpaca_api_key: Optional[str] = None
    alpaca_api_secret: Optional[str] = None
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

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)

    @property
    def has_alpaca_credentials(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_api_secret)


def _env_float(name: str, default: float, *, minimum: Optional[float] = None) -> float:
    """Parse a float env var, falling back to ``default`` if unset/blank.

    A non-numeric value, or one below ``minimum``, raises ``ValueError`` — a
    misconfigured cadence should fail fast at startup, not silently busy-loop.
    """

    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


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
    enable_dev_routes = (
        os.environ.get(DEV_ROUTES_ENV, "true").strip().lower() not in _FALSEY
    )

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

    def _clean(name: str) -> Optional[str]:
        raw = os.environ.get(name)
        return raw.strip() if raw and raw.strip() else None

    return Settings(
        state_store=state_store,
        db_path=db_path,
        enable_dev_routes=enable_dev_routes,
        alpaca_api_key=_clean(ALPACA_KEY_ENV),
        alpaca_api_secret=_clean(ALPACA_SECRET_ENV),
        broker_adapter=broker_adapter,
        poll_cadence_seconds=poll_cadence,
        unfilled_timeout_minutes=unfilled_timeout,
        enable_monitoring=enable_monitoring,
    )
