"""Background strategy loop — Phase 5 candidate generation.

A single asyncio task, started at app startup (see ``app/main.py``), that on a
fixed **decision cadence** (distinct from Phase 4's order-poll cadence, per
D-005's ingestion/decision split):

1. Keeps the ``MarketDataService`` subscription set in sync with the
   **armed** watchlist symbols (subscribes newly-armed, unsubscribes
   newly-disarmed — the loop drives subscriptions from the watchlist, not the
   reverse).
2. Evaluates each armed symbol's current snapshot through the Strategy Engine
   (``app/strategy.py``) and creates a candidate for any proposal.

Design rules this module follows:

* **The loop never crashes.** A single symbol's evaluation failure is logged
  and skipped, same as Phase 4's per-order error handling; a failure anywhere
  in a tick is logged and the loop sleeps and tries again. Only
  ``CancelledError`` (clean shutdown) propagates.
* **Not gated by the kill switch / pause-buys (D-014a).** Rule 8 blocks order
  *intent*, not candidate *visibility* — this loop keeps proposing regardless
  of those flags; the existing enforcement (D-013a) blocks any resulting
  order downstream.
* **Skips entirely when the session is closed** — there is nothing to propose
  against (``create_candidate`` would refuse it anyway; checked once per tick
  rather than once per symbol).
* **Dedup is session-wide, computed once per tick** (D-014c), not once per
  symbol — a single ``list_candidates`` pair of calls, not N.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.config import Settings
from app.features import session_type_for
from app.marketdata.service import MarketDataService
from app.models import CandidateStatus, SessionStatus, utcnow
from app.store.base import StateStore
from app.strategy import evaluate

_log = logging.getLogger(__name__)

# An unresolved candidate for a symbol blocks a fresh proposal (D-014c);
# ORDERED/REJECTED/EXPIRED do not — see docs/00_START_HERE.md D-014.
_OPEN_CANDIDATE_STATUSES = (CandidateStatus.PENDING, CandidateStatus.APPROVED)


async def strategy_loop(
    store: StateStore, market_data: MarketDataService, settings: Settings
) -> None:
    """Run forever: sleep one cadence, then run a tick. Never crashes.

    Sleeps *before* the first tick, matching ``monitoring_loop`` — app startup
    is not blocked and a short-lived injected store never reaches the tick body.
    """

    _log.info(
        "strategy loop started (cadence=%.3fs)",
        settings.strategy_decision_cadence_seconds,
    )
    while True:
        try:
            await asyncio.sleep(settings.strategy_decision_cadence_seconds)
            await run_strategy_tick(store, market_data, settings)
        except asyncio.CancelledError:
            _log.info("strategy loop cancelled; shutting down")
            raise
        except Exception:  # noqa: BLE001 - a tick failure must not stop the loop
            _log.exception("strategy tick failed; continuing on next cadence")


async def run_strategy_tick(
    store: StateStore,
    market_data: MarketDataService,
    settings: Settings,
    *,
    now: Optional[datetime] = None,
) -> None:
    """One strategy iteration: sync subscriptions, then evaluate armed symbols.

    Exposed separately from :func:`strategy_loop` so tests drive a single,
    deterministic tick without the sleep/``while True`` wrapper. ``now``
    defaults to :func:`app.models.utcnow`; tests pass an explicit
    timezone-aware datetime for deterministic session-type classification
    (real wall-clock time would make premarket/regular/after-hours tests
    flaky depending on when they happen to run).
    """

    session = await store.get_current_session()
    if session.status is SessionStatus.CLOSED:
        return

    watchlist = await store.list_watchlist()
    armed_symbols = [w.symbol for w in watchlist if w.armed]

    await _sync_subscriptions(market_data, armed_symbols)

    if not armed_symbols:
        return

    open_symbols = await _open_candidate_symbols(store, session.id)
    session_type = session_type_for(now or utcnow())

    for symbol in armed_symbols:
        try:
            snapshot = await market_data.get_snapshot(symbol)
            proposal = evaluate(
                symbol,
                snapshot,
                session_type,
                has_open_candidate=symbol in open_symbols,
                momentum_threshold_pct=settings.strategy_momentum_threshold_pct,
                min_volume=settings.strategy_min_volume,
                max_spread_pct=settings.strategy_max_spread_pct,
                limit_buffer_pct=settings.strategy_limit_buffer_pct,
                default_quantity=settings.strategy_default_quantity,
            )
            if proposal is None:
                continue
            await store.create_candidate(
                proposal.symbol,
                strategy=proposal.strategy,
                reason=proposal.reason,
                risk_decision=proposal.risk_decision,
                suggested_quantity=proposal.suggested_quantity,
                suggested_limit_price=proposal.suggested_limit_price,
                session_id=session.id,
            )
        except Exception:  # noqa: BLE001 - one symbol's failure must not block others
            _log.exception("strategy evaluation failed for %s", symbol)


async def _sync_subscriptions(
    market_data: MarketDataService, armed_symbols: list[str]
) -> None:
    """Subscribe newly-armed symbols; unsubscribe newly-disarmed ones.

    Derives "currently subscribed" from the feed's own snapshot list rather
    than tracking separate loop-side state, so it can never drift out of sync
    with what the service actually has subscribed.
    """

    subscribed = {s.symbol for s in await market_data.list_snapshots()}
    armed_set = set(armed_symbols)
    to_subscribe = sorted(armed_set - subscribed)
    to_unsubscribe = sorted(subscribed - armed_set)
    if to_subscribe:
        await market_data.subscribe(to_subscribe)
    if to_unsubscribe:
        await market_data.unsubscribe(to_unsubscribe)


async def _open_candidate_symbols(store: StateStore, session_id: str) -> set[str]:
    """Symbols with an unresolved (PENDING/APPROVED) candidate this session."""

    open_symbols: set[str] = set()
    for status in _OPEN_CANDIDATE_STATUSES:
        for candidate in await store.list_candidates(session_id=session_id, status=status):
            open_symbols.add(candidate.symbol)
    return open_symbols
