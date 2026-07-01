"""Background strategy loop — Phase 5 candidate generation.

A single asyncio task, started at app startup (see ``app/main.py``), that on a
fixed **decision cadence** (distinct from Phase 4's order-poll cadence, per
D-005's ingestion/decision split):

1. Keeps the ``MarketDataService`` subscription set in sync with the
   **armed** watchlist symbols (subscribes newly-armed, unsubscribes
   newly-disarmed — the loop drives subscriptions from the watchlist, not the
   reverse).
2. Surfaces a feed staleness *transition* (D-005: never silently stale) as a
   ``market_data_stale``/``market_data_recovered`` audit event — the service
   implementation only reports the current ``stale`` bool on each snapshot; a
   store isn't part of its interface, so writing the transition event is the
   loop's job, mirroring how ``order_stale`` is written by the order-monitoring
   loop rather than the broker adapter.
3. Evaluates each armed symbol's current snapshot through the Strategy Engine
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
* **Subscription sync and staleness surfacing never touch session state.**
  They run every tick regardless of whether a trading session is open,
  closed, or doesn't exist yet for today — a just-disarmed symbol must always
  get unsubscribed, and a dead feed must always get surfaced, independent of
  the trading day's state. Only *candidate evaluation* — the part that
  actually needs a session to attach candidates to and to check "is trading
  stopped for today" — is skipped when the session is closed, and only that
  part fetches/creates the current session. This also means an idle tick with
  nothing armed never auto-creates an empty session purely from the loop
  ticking (``get_current_session`` is only called once armed symbols exist).
* **Dedup is session-wide, computed once per tick** (D-014c), not once per
  symbol — a single ``list_candidates`` pair of calls, not N.
* **Staleness state is cached in memory across ticks**, passed down from
  :func:`strategy_loop`'s own long-lived dict, so a live process does an O(1)
  dict lookup per symbol instead of re-scanning the entire event log every
  cadence (the event-log read remains the *correct* fallback — and is what
  every test exercises by default — for a caller that doesn't carry state
  across calls, e.g. a one-off diagnostic tick).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.config import Settings
from app.features import session_type_for
from app.marketdata.service import MarketDataService
from app.models import CandidateStatus, EventType, SessionStatus, utcnow
from app.store.base import StateStore
from app.strategy import evaluate

_log = logging.getLogger(__name__)

# An unresolved candidate for a symbol blocks a fresh proposal (D-014c);
# ORDERED/REJECTED/EXPIRED do not — see docs/00_START_HERE.md D-014.
_OPEN_CANDIDATE_STATUSES = (CandidateStatus.PENDING, CandidateStatus.APPROVED)

_STALENESS_EVENT_TYPES = frozenset(
    {EventType.MARKET_DATA_STALE.value, EventType.MARKET_DATA_RECOVERED.value}
)


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
    # Owned by this long-lived task and threaded into every tick, so staleness
    # transitions are detected via an O(1) in-memory lookup instead of
    # rescanning the whole event log every cadence (see module docstring).
    stale_state: dict[str, bool] = {}
    while True:
        try:
            await asyncio.sleep(settings.strategy_decision_cadence_seconds)
            await run_strategy_tick(store, market_data, settings, stale_state=stale_state)
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
    stale_state: Optional[dict[str, bool]] = None,
) -> None:
    """One strategy iteration: sync subscriptions and surface staleness (always),
    then evaluate armed symbols against the current session (only if there's a
    session to evaluate against).

    Exposed separately from :func:`strategy_loop` so tests drive a single,
    deterministic tick without the sleep/``while True`` wrapper. ``now``
    defaults to :func:`app.models.utcnow`; tests pass an explicit
    timezone-aware datetime for deterministic session-type classification
    (real wall-clock time would make premarket/regular/after-hours tests
    flaky depending on when they happen to run). ``stale_state`` is the
    in-memory staleness cache :func:`strategy_loop` carries across ticks;
    omitted (``None``) it falls back to the persisted-event-log read, which
    is what every direct-call test exercises (see module docstring).
    """

    watchlist = await store.list_watchlist()
    armed_symbols = [w.symbol for w in watchlist if w.armed]

    # Never gated on session state (see module docstring): a disarm must
    # always be synced, and a dead feed must always be surfaced.
    await _sync_subscriptions(market_data, armed_symbols)
    await _surface_market_data_staleness(store, market_data, stale_state)

    if not armed_symbols:
        return  # nothing to evaluate; skip WITHOUT touching session state

    session = await store.get_current_session()
    if session.status is SessionStatus.CLOSED:
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


async def _surface_market_data_staleness(
    store: StateStore,
    market_data: MarketDataService,
    stale_state: Optional[dict[str, bool]] = None,
) -> None:
    """Write a ``market_data_stale``/``market_data_recovered`` event on a
    per-symbol staleness *transition* (D-005) — not every tick a symbol
    happens to be stale, only when it changes, so the audit log records the
    incident rather than spamming one row per cadence for as long as a
    disconnect lasts.

    Feed-level, not session-scoped: a dead feed matters independent of which
    trading session is active, so this reads the full event history rather
    than filtering by ``session_id`` (unlike the candidate dedup above).

    ``stale_state``, if given, is used and updated **in place** as the prior-
    state source instead of the event log — an O(1) lookup per symbol rather
    than a full ``list_events()`` scan every cadence. It is also pruned of any
    symbol no longer subscribed, so a long-running process doesn't accumulate
    entries for symbols armed once and later removed. If omitted (``None``),
    falls back to :func:`_last_known_stale_state` (correct, just slower —
    what every test that doesn't explicitly pass a cache exercises).
    """

    snapshots = await market_data.list_snapshots()
    symbols = {s.symbol for s in snapshots}

    if stale_state is not None:
        # Prune BEFORE the empty-snapshots early return below — otherwise a
        # symbol that just got fully unsubscribed (snapshots now empty) would
        # never be pruned, since the early return would skip this entirely.
        for stale_symbol in list(stale_state.keys()):
            if stale_symbol not in symbols:
                del stale_state[stale_symbol]

    if not snapshots:
        return

    if stale_state is None:
        previously_stale: dict[str, bool] = await _last_known_stale_state(store, symbols)
    else:
        previously_stale = stale_state

    for snapshot in snapshots:
        was_stale = previously_stale.get(snapshot.symbol, False)
        if snapshot.stale and not was_stale:
            await store.append_event(
                EventType.MARKET_DATA_STALE.value,
                message=f"market data for {snapshot.symbol} is stale",
                symbol=snapshot.symbol,
                payload={"last_updated_at": snapshot.updated_at.isoformat()},
            )
            previously_stale[snapshot.symbol] = True
        elif was_stale and not snapshot.stale:
            await store.append_event(
                EventType.MARKET_DATA_RECOVERED.value,
                message=f"market data for {snapshot.symbol} recovered",
                symbol=snapshot.symbol,
            )
            previously_stale[snapshot.symbol] = False


async def _last_known_stale_state(
    store: StateStore, symbols: set[str]
) -> dict[str, bool]:
    """The most recently recorded stale/recovered state per symbol, read from
    the persisted event log — the correct-but-slower fallback used when no
    in-memory ``stale_state`` cache is available (see
    :func:`_surface_market_data_staleness`).

    A symbol absent from the result has no prior staleness event. Note this is
    NOT symmetric between the two directions: a symbol whose *first-ever*
    observation is healthy is absent (nothing was written — there is nothing
    to announce about a feed that has always been fine); a symbol whose
    first-ever observation is stale is *also* absent from this read (no event
    exists YET), which is exactly what makes the caller write the first
    ``market_data_stale`` event — establishing a baseline only in the
    becomes-stale direction, matching ``monitoring.py``'s ``_orders_with_event``
    idempotency pattern (read the persisted log so "write once per transition"
    survives a process restart).
    """

    state: dict[str, bool] = {}
    for event in await store.list_events():
        if event.event_type not in _STALENESS_EVENT_TYPES or event.symbol not in symbols:
            continue
        state[event.symbol] = event.event_type == EventType.MARKET_DATA_STALE.value
    return state
