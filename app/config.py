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
STALE_SUBMITTING_MAX_REDRIVE_ATTEMPTS_ENV = "STALE_SUBMITTING_MAX_REDRIVE_ATTEMPTS"
TIMEOUT_QUARANTINE_MAX_QUERY_ATTEMPTS_ENV = "TIMEOUT_QUARANTINE_MAX_QUERY_ATTEMPTS"
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

# Phase 6 — Capital Intelligence Layer (CAPI) pre-trade risk gate (D-016).
# Enforced in app.store.core's create_order_for_candidate (authoritative) and
# pre-checked in the approve route (UX) — see app.policy.risk_limit_reason.
CAPI_MAX_SHARES_PER_ORDER_ENV = "CAPI_MAX_SHARES_PER_ORDER"
CAPI_MAX_NOTIONAL_PER_ORDER_ENV = "CAPI_MAX_NOTIONAL_PER_ORDER"
CAPI_MAX_TOTAL_EXPOSURE_ENV = "CAPI_MAX_TOTAL_EXPOSURE"
# Comma-separated tickers; empty (default) = no restriction beyond the
# watchlist itself, a genuinely meaningful empty state (unlike the three
# numeric limits above, which reject 0 — see load_settings).
CAPI_TRADING_ALLOWLIST_ENV = "CAPI_TRADING_ALLOWLIST"

# Phase 7 — Sell-Side Protection (always-on safety exits). The floor is a fixed
# percentage below average cost; a breach auto-submits a full-exit protective
# sell behind the Approval Gate seam (D-P1). See app/protection.py.
PROTECTION_ENABLED_ENV = "PROTECTION_ENABLED"
PROTECTION_STOP_LOSS_PCT_ENV = "PROTECTION_STOP_LOSS_PCT"
PROTECTION_LIMIT_BUFFER_PCT_ENV = "PROTECTION_LIMIT_BUFFER_PCT"
PROTECTION_CADENCE_SECONDS_ENV = "PROTECTION_CADENCE_SECONDS"

# Phase 4 wave 4e — runtime mass-report reconciliation (§7). The acting reconcile
# (targeted-query-before-not-found, external-order + position-parity surfacing) and
# its deterministic per-minute query budget. Slice 4e-1 lands config + budget only.
RECONCILIATION_ENABLED_ENV = "RECONCILIATION_ENABLED"
RECONCILE_RECENT_THRESHOLD_MS_ENV = "RECONCILE_RECENT_THRESHOLD_MS"
RECONCILE_AVG_PRICE_TOLERANCE_ENV = "RECONCILE_AVG_PRICE_TOLERANCE"
RECONCILE_OPEN_CHECK_MISSING_RETRIES_ENV = "RECONCILE_OPEN_CHECK_MISSING_RETRIES"
RECONCILE_QUERY_BUDGET_PER_MIN_ENV = "RECONCILE_QUERY_BUDGET_PER_MIN"
RECONCILE_STARTUP_DELAY_SECS_ENV = "RECONCILE_STARTUP_DELAY_SECS"

DEFAULT_DB_PATH = "./data/app.db"
DEFAULT_POLL_CADENCE_SECONDS = 15.0
DEFAULT_UNFILLED_TIMEOUT_MINUTES = 60.0
# AIR-003 backstop: how many consecutive transient re-drive failures a stale
# SUBMITTING order tolerates before it is escalated to a durable needs_review
# recovery record — a bound so a permanent broker rejection *misclassified* as
# transient can never livelock (retry every tick, inflating exposure forever).
DEFAULT_STALE_SUBMITTING_MAX_REDRIVE_ATTEMPTS = 10
# ADR-002: targeted-query attempts a TIMEOUT_QUARANTINE order tolerates before a
# CONFIRMED-absent order is resolved to REJECTED (§7: a single not-found could be
# venue lag) / a persistently-inconclusive query is surfaced for manual review.
DEFAULT_TIMEOUT_QUARANTINE_MAX_QUERY_ATTEMPTS = 3
DEFAULT_MARKET_DATA_STALE_MINUTES = 5.0
DEFAULT_STRATEGY_DECISION_CADENCE_SECONDS = 5.0
DEFAULT_STRATEGY_MOMENTUM_THRESHOLD_PCT = 3.0
DEFAULT_STRATEGY_MIN_VOLUME = 50_000.0
DEFAULT_STRATEGY_MAX_SPREAD_PCT = 1.0
DEFAULT_STRATEGY_LIMIT_BUFFER_PCT = 0.1
DEFAULT_STRATEGY_DEFAULT_QUANTITY = 10
# Placeholder paper-trading guardrails, not a real capital plan — a beta
# operator running the default 10-share strategy has ample headroom under
# these; they exist so CAPI is a real, always-on gate from day one rather
# than something an operator has to remember to configure before it does
# anything.
DEFAULT_CAPI_MAX_SHARES_PER_ORDER = 500.0
DEFAULT_CAPI_MAX_NOTIONAL_PER_ORDER = 5_000.0
DEFAULT_CAPI_MAX_TOTAL_EXPOSURE = 25_000.0

# Phase 7 — Sell-Side Protection. An 8% hard floor below average cost; a
# protective pre/after-hours limit placed 0.5% below the marketable reference so
# it crosses the spread and fills in thin liquidity.
DEFAULT_PROTECTION_STOP_LOSS_PCT = 0.08
DEFAULT_PROTECTION_LIMIT_BUFFER_PCT = 0.005

# Phase 4 wave 4e — §7 verified reconciliation defaults (Nautilus
# LiveExecEngineConfig, source-checked in docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §7).
DEFAULT_RECONCILE_RECENT_THRESHOLD_MS = 5000  # open_check_threshold_ms
DEFAULT_RECONCILE_AVG_PRICE_TOLERANCE = 0.0001  # 0.01% avg-px parity tolerance
DEFAULT_RECONCILE_OPEN_CHECK_MISSING_RETRIES = (
    3  # confirms before not-found -> terminal
)
DEFAULT_RECONCILE_QUERY_BUDGET_PER_MIN = 200  # §9 trading/query budget (200/min)
DEFAULT_RECONCILE_STARTUP_DELAY_SECS = 10.0  # reconciliation_startup_delay_secs (4f)

_FALSEY = {"false", "0", "no", "off"}


@dataclass(frozen=True)
class Settings:
    """Resolved, immutable backend settings."""

    state_store: str = "sqlite"
    db_path: str = DEFAULT_DB_PATH
    # Whether the DEV/MOCK scaffolding routes (e.g. POST /api/dev/candidates) are
    # mounted. On by default so the candidate flow is exercisable in beta; set
    # ``ENABLE_DEV_ROUTES=false`` to keep the mock-injection path off a given
    # deployment. Phase 5's real Strategy Engine (``app/strategy.py`` +
    # ``app/strategy_loop.py``) is now the primary candidate producer, but this
    # route stays useful for hand-testing an exact symbol/price/quantity the
    # strategy wouldn't naturally produce — it doesn't remove the need for it.
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
    # AIR-003 backstop: durably recorded no-progress re-drive attempts a stale
    # SUBMITTING order tolerates before escalation to a needs_review record.
    stale_submitting_max_redrive_attempts: int = (
        DEFAULT_STALE_SUBMITTING_MAX_REDRIVE_ATTEMPTS
    )
    # ADR-002: targeted-query attempts before a confirmed-absent TIMEOUT_QUARANTINE
    # order is resolved to REJECTED / a stuck one is surfaced for manual review.
    timeout_quarantine_max_query_attempts: int = (
        DEFAULT_TIMEOUT_QUARANTINE_MAX_QUERY_ATTEMPTS
    )
    # Whether the background monitoring loop starts at app startup.
    enable_monitoring: bool = True
    # Phase 4 wave 4e — the ACTING runtime mass-report reconciliation (§7). When on
    # (default), every monitoring tick computes the §7 reconciliation plan
    # (``app/reconciliation.py``) from ``list_open_orders``/``list_positions``
    # alongside the legacy per-order poll and acts on it. **Slice 4e-2** surfaces
    # external/unmanaged venue orders (non-mutating audit records); later slices add
    # the oversell-critical not-found resolution (4e-3), synthetic fills + position
    # parity + the query throttle (4e-4). Naturally inert against the existing corpus:
    # external orders come from the broker report, so an empty report yields none.
    reconciliation_enabled: bool = True
    reconcile_recent_threshold_ms: int = DEFAULT_RECONCILE_RECENT_THRESHOLD_MS
    reconcile_avg_price_tolerance: float = DEFAULT_RECONCILE_AVG_PRICE_TOLERANCE
    reconcile_open_check_missing_retries: int = (
        DEFAULT_RECONCILE_OPEN_CHECK_MISSING_RETRIES
    )
    reconcile_query_budget_per_min: int = DEFAULT_RECONCILE_QUERY_BUDGET_PER_MIN
    reconcile_startup_delay_secs: float = DEFAULT_RECONCILE_STARTUP_DELAY_SECS

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

    # --- Phase 6: CAPI pre-trade risk gate (D-016) ------------------------- #
    capi_max_shares_per_order: float = DEFAULT_CAPI_MAX_SHARES_PER_ORDER
    capi_max_notional_per_order: float = DEFAULT_CAPI_MAX_NOTIONAL_PER_ORDER
    capi_max_total_exposure: float = DEFAULT_CAPI_MAX_TOTAL_EXPOSURE
    # Empty = no restriction beyond the watchlist itself.
    capi_trading_allowlist: frozenset[str] = field(default_factory=frozenset)

    # --- Phase 7: Sell-Side Protection (always-on safety exits) ----------- #
    # On by default: a beta operator shouldn't have to opt in to a stop-loss.
    protection_enabled: bool = True
    # Hard floor as a fraction below average cost (0.08 = 8%); in (0, 1).
    protection_stop_loss_pct: float = DEFAULT_PROTECTION_STOP_LOSS_PCT
    # How far below the marketable reference a pre/after-hours protective limit
    # is placed (0.005 = 0.5%); in [0, 1).
    protection_limit_buffer_pct: float = DEFAULT_PROTECTION_LIMIT_BUFFER_PCT
    # None (default) = protection runs inside the monitoring tick (documented
    # ~poll-cadence detection latency). A positive value is reserved for a future
    # dedicated fast loop; beta keeps it in the tick.
    protection_cadence_seconds: Optional[float] = None

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
    # At least 1 attempt before escalation (0 would escalate before ever trying
    # a re-drive, defeating the idempotent-recovery path).
    stale_submitting_max_redrive_attempts = _env_int(
        STALE_SUBMITTING_MAX_REDRIVE_ATTEMPTS_ENV,
        DEFAULT_STALE_SUBMITTING_MAX_REDRIVE_ATTEMPTS,
        minimum=1,
    )
    # At least 1 targeted query before resolving a confirmed-absent quarantine.
    timeout_quarantine_max_query_attempts = _env_int(
        TIMEOUT_QUARANTINE_MAX_QUERY_ATTEMPTS_ENV,
        DEFAULT_TIMEOUT_QUARANTINE_MAX_QUERY_ATTEMPTS,
        minimum=1,
    )
    enable_monitoring = (
        os.environ.get(ENABLE_MONITORING_ENV, "true").strip().lower() not in _FALSEY
    )
    # Phase 4 wave 4e — the acting runtime reconciliation config + §7 defaults.
    reconciliation_enabled = (
        os.environ.get(RECONCILIATION_ENABLED_ENV, "true").strip().lower()
        not in _FALSEY
    )
    reconcile_recent_threshold_ms = _env_int(
        RECONCILE_RECENT_THRESHOLD_MS_ENV,
        DEFAULT_RECONCILE_RECENT_THRESHOLD_MS,
        minimum=0,
    )
    reconcile_avg_price_tolerance = _env_float(
        RECONCILE_AVG_PRICE_TOLERANCE_ENV,
        DEFAULT_RECONCILE_AVG_PRICE_TOLERANCE,
        minimum=0.0,
    )
    reconcile_open_check_missing_retries = _env_int(
        RECONCILE_OPEN_CHECK_MISSING_RETRIES_ENV,
        DEFAULT_RECONCILE_OPEN_CHECK_MISSING_RETRIES,
        minimum=1,
    )
    reconcile_query_budget_per_min = _env_int(
        RECONCILE_QUERY_BUDGET_PER_MIN_ENV,
        DEFAULT_RECONCILE_QUERY_BUDGET_PER_MIN,
        minimum=1,
    )
    reconcile_startup_delay_secs = _env_float(
        RECONCILE_STARTUP_DELAY_SECS_ENV,
        DEFAULT_RECONCILE_STARTUP_DELAY_SECS,
        minimum=0.0,
    )

    market_data_feed = os.environ.get(MARKET_DATA_FEED_ENV, "auto").strip().lower()
    if market_data_feed not in {"auto", "mock", "alpaca"}:
        raise ValueError(
            f"{MARKET_DATA_FEED_ENV} must be 'auto', 'mock', or 'alpaca', "
            f"got {market_data_feed!r}"
        )
    # Strictly positive (matches POLL_CADENCE_ENV's minimum=0.001), NOT >= 0.0:
    # unlike the order-unfilled-timeout (where 0 is a deliberately meaningful
    # "flag every open order immediately" setting), a stale-minutes of exactly
    # 0 makes every market snapshot permanently stale, which silently zeroes
    # out the Strategy Engine's entire candidate output — far more likely to
    # be an operator typo than an intentional configuration.
    market_data_stale_minutes = _env_float(
        MARKET_DATA_STALE_MINUTES_ENV, DEFAULT_MARKET_DATA_STALE_MINUTES, minimum=0.001
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
    # Strictly positive, NOT >= 0.0: 0 reads like "no spread limit" but means
    # the opposite (a MAXIMUM of exactly 0 requires a literally-zero spread —
    # a real two-sided quote essentially never has one), so it would silently
    # fail every symbol's spread gate forever. To effectively disable the
    # check, use a large value (e.g. 100) instead of 0.
    strategy_max_spread = _env_float(
        STRATEGY_MAX_SPREAD_ENV, DEFAULT_STRATEGY_MAX_SPREAD_PCT, minimum=0.001
    )
    strategy_limit_buffer = _env_float(
        STRATEGY_LIMIT_BUFFER_ENV, DEFAULT_STRATEGY_LIMIT_BUFFER_PCT, minimum=0.0
    )
    strategy_default_quantity = _env_int(
        STRATEGY_DEFAULT_QUANTITY_ENV, DEFAULT_STRATEGY_DEFAULT_QUANTITY, minimum=1
    )

    # Strictly positive for all three (matches STRATEGY_MAX_SPREAD_ENV's
    # reasoning): a limit of exactly 0 doesn't mean "unlimited," it means
    # "reject every order," which would silently disable all trading rather
    # than obviously breaking something — the same class of footgun the other
    # *_minimum=0.001 checks above guard against.
    capi_max_shares_per_order = _env_float(
        CAPI_MAX_SHARES_PER_ORDER_ENV, DEFAULT_CAPI_MAX_SHARES_PER_ORDER, minimum=0.001
    )
    capi_max_notional_per_order = _env_float(
        CAPI_MAX_NOTIONAL_PER_ORDER_ENV,
        DEFAULT_CAPI_MAX_NOTIONAL_PER_ORDER,
        minimum=0.001,
    )
    capi_max_total_exposure = _env_float(
        CAPI_MAX_TOTAL_EXPOSURE_ENV, DEFAULT_CAPI_MAX_TOTAL_EXPOSURE, minimum=0.001
    )
    capi_trading_allowlist = frozenset(
        s.strip().upper()
        for s in os.environ.get(CAPI_TRADING_ALLOWLIST_ENV, "").split(",")
        if s.strip()
    )

    # --- Phase 7: Sell-Side Protection ----------------------------------- #
    protection_enabled = (
        os.environ.get(PROTECTION_ENABLED_ENV, "true").strip().lower() not in _FALSEY
    )
    # Strictly inside (0, 1): a floor at 0% (== average cost) would trip on the
    # first tick at or below cost, and a floor at >= 100% would put the floor at
    # or below zero (never breaches) — both misconfigurations, rejected at load.
    # _env_float already rejects non-numeric/NaN/Inf; the strict range is here.
    protection_stop_loss_pct = _env_float(
        PROTECTION_STOP_LOSS_PCT_ENV, DEFAULT_PROTECTION_STOP_LOSS_PCT
    )
    if not (0.0 < protection_stop_loss_pct < 1.0):
        raise ValueError(
            f"{PROTECTION_STOP_LOSS_PCT_ENV} must be in (0, 1), got "
            f"{protection_stop_loss_pct}"
        )
    # [0, 1): 0 = price the protective limit exactly at the reference (still
    # marketable); >= 1 would price it at or below zero.
    protection_limit_buffer_pct = _env_float(
        PROTECTION_LIMIT_BUFFER_PCT_ENV,
        DEFAULT_PROTECTION_LIMIT_BUFFER_PCT,
        minimum=0.0,
    )
    if not (protection_limit_buffer_pct < 1.0):
        raise ValueError(
            f"{PROTECTION_LIMIT_BUFFER_PCT_ENV} must be in [0, 1), got "
            f"{protection_limit_buffer_pct}"
        )
    # Optional: unset/blank = None (run in the monitoring tick). When set it must
    # be strictly positive (a zero/negative dedicated cadence is meaningless).
    _raw_cadence = os.environ.get(PROTECTION_CADENCE_SECONDS_ENV)
    if _raw_cadence is None or not _raw_cadence.strip():
        protection_cadence_seconds: Optional[float] = None
    else:
        protection_cadence_seconds = _env_float(PROTECTION_CADENCE_SECONDS_ENV, 0.0)
        if protection_cadence_seconds <= 0:
            raise ValueError(
                f"{PROTECTION_CADENCE_SECONDS_ENV} must be > 0 when set, got "
                f"{protection_cadence_seconds}"
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
        stale_submitting_max_redrive_attempts=stale_submitting_max_redrive_attempts,
        timeout_quarantine_max_query_attempts=timeout_quarantine_max_query_attempts,
        enable_monitoring=enable_monitoring,
        reconciliation_enabled=reconciliation_enabled,
        reconcile_recent_threshold_ms=reconcile_recent_threshold_ms,
        reconcile_avg_price_tolerance=reconcile_avg_price_tolerance,
        reconcile_open_check_missing_retries=reconcile_open_check_missing_retries,
        reconcile_query_budget_per_min=reconcile_query_budget_per_min,
        reconcile_startup_delay_secs=reconcile_startup_delay_secs,
        market_data_feed=market_data_feed,
        market_data_stale_minutes=market_data_stale_minutes,
        enable_strategy_engine=enable_strategy_engine,
        strategy_decision_cadence_seconds=strategy_decision_cadence,
        strategy_momentum_threshold_pct=strategy_momentum_threshold,
        strategy_min_volume=strategy_min_volume,
        strategy_max_spread_pct=strategy_max_spread,
        strategy_limit_buffer_pct=strategy_limit_buffer,
        strategy_default_quantity=strategy_default_quantity,
        capi_max_shares_per_order=capi_max_shares_per_order,
        capi_max_notional_per_order=capi_max_notional_per_order,
        capi_max_total_exposure=capi_max_total_exposure,
        capi_trading_allowlist=capi_trading_allowlist,
        protection_enabled=protection_enabled,
        protection_stop_loss_pct=protection_stop_loss_pct,
        protection_limit_buffer_pct=protection_limit_buffer_pct,
        protection_cadence_seconds=protection_cadence_seconds,
    )
