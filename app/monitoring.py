"""Background monitoring loop — Phase 4 order submission + reconciliation.

A single asyncio task, started at app startup (see ``app/main.py``), that on a
fixed cadence (D-011: REST polling, not websocket):

1. **Submits** orders the approval flow created but that have not yet reached the
   broker (orders at ``OrderStatus.CREATED`` — their candidate is ``ORDERED`` but
   the order itself is freshly created), and
2. **Reconciles** open orders (``SUBMITTED`` / ``PARTIALLY_FILLED``) by polling
   the broker, appending any fills (the store dedups by ``source_fill_id``),
   advancing the order's status, and surfacing orders that have sat unfilled
   past the configured timeout as an ``order_stale`` audit event.

Design rules this module follows:

* **Position is only ever moved by ``append_fill``** (Rule 7). This loop never
  touches position directly — it appends fills and lets the derived fold change.
* **Duplicate fills are the store's job.** The loop appends every fill the broker
  reports and relies on ``source_fill_id`` dedup (D-006); it does not pre-check.
* **The loop never crashes.** A transient broker error on one order is logged and
  skipped; a failure anywhere in a tick is logged and the loop sleeps and tries
  again. Only ``CancelledError`` (clean shutdown) propagates.
* **The lock is never held across a network call.** Store methods acquire the
  store lock internally and the adapter calls are separate awaits, so a slow
  broker call never blocks other coroutines (``01_ARCHITECTURE.md`` concurrency
  model).
* **Polling continues regardless of session close** (D-011): a submitted order is
  a real open position that must be tracked to a terminal state even after its
  session has closed.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.broker.adapter import (
    AmbiguousBrokerError,
    BrokerAdapter,
    BrokerError,
    BrokerOrderUpdate,
    TerminalBrokerError,
)
from app.config import Settings
from app.features import session_type_for
from app.marketdata.service import MarketDataService
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    RECOVERY_RESOLVED,
    RECOVERY_UNRESOLVED,
    EventAuthority,
    EventSource,
    EventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    SellIntentStatus,
    SellReason,
    SessionStatus,
    SessionType,
    TradingState,
    utcnow,
)
from app.policy import finite_number_reason
from app.position import NegativePositionError
from app.protection import (
    FloorBreach,
    ProtectionConfig,
    floor_breach_reason,
    protective_limit_price,
)
from app.reconciliation import (
    ReconciliationPlan,
    ReconcileQueryBudget,
    plan_reconciliation,
)
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    InvalidFillError,
    InvalidOrderError,
    OrderTransitionError,
    StateStore,
    UnknownEntityError,
)

_log = logging.getLogger(__name__)

# Orders the loop actively polls toward a terminal state. Includes cancel_pending
# so a late fill arriving before the broker confirms a cancel is still reconciled
# (CHAOS-1). Deliberately excludes SUBMITTING (D-017): a claimed order has no
# broker_order_id yet, so there is nothing to poll — it advances to SUBMITTED
# (or releases to CREATED) inside the same submit tick, never via reconcile.
_OPEN_STATUSES = frozenset(
    {
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
    }
)
# Open orders eligible for the unfilled-timeout stale flag — NOT cancel_pending
# (it is already being wound down, not "stuck unfilled").
_STALEABLE_STATUSES = frozenset(
    {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}
)

# Fill-append failures that are recoverable per-order (logged, then skipped).
_FILL_ERRORS = (InvalidFillError, UnknownEntityError, NegativePositionError)
# Order-transition failures that are recoverable per-order.
_TRANSITION_ERRORS = (OrderTransitionError, InvalidOrderError, UnknownEntityError)


def _protection_config(settings: Optional[Settings]) -> ProtectionConfig:
    """Build the pure-engine :class:`ProtectionConfig` from ``settings`` (only its
    ``limit_buffer_pct`` matters for pricing a protective sell). Defaults when
    ``settings`` is ``None`` — the private submit helpers accept ``settings=None``
    for the handful of legacy direct test callers that submit only BUYs, where no
    protective pricing is ever needed."""

    if settings is None:
        return ProtectionConfig()
    return ProtectionConfig(
        enabled=settings.protection_enabled,
        stop_loss_pct=settings.protection_stop_loss_pct,
        limit_buffer_pct=settings.protection_limit_buffer_pct,
    )


async def _effective_submit_order(
    order: Order,
    market_data: Optional[MarketDataService],
    settings: Optional[Settings],
) -> Optional[Order]:
    """The order to ACTUALLY submit (§5.4 / D-015 / Rule 12) — the single choke
    point where a protective sell's session-conditional order type is decided.

    A protective sell is created ``MARKET`` (the "full exit" intent). Only at
    submission, against the live session:

    * **REGULAR hours** → submit ``MARKET`` unchanged.
    * **PRE_MARKET / AFTER_HOURS** → a MARKET is forbidden (Rule 12), so return a
      COPY downgraded to ``LIMIT`` priced live by ``protective_limit_price`` — an
      aggressive marketable limit that fills in thin liquidity. Returns ``None``
      when it can't be priced (no market-data handle, or an untrustworthy/stale
      snapshot) — the caller HOLDS the order this tick rather than send a market
      order into a limit-only session or an un-priceable limit.

    A BUY, or any order that isn't a ``MARKET`` sell, is returned unchanged (the
    persisted order is never mutated here — the downgrade is a per-submit
    rendering; the stored order stays ``MARKET`` so the §7 reconcile fill-price
    fallback keys off it)."""

    if OrderSide(order.side) is not OrderSide.SELL:
        return order
    if OrderType(order.order_type) is not OrderType.MARKET:
        return order
    if session_type_for(utcnow()) is SessionType.REGULAR:
        return order
    snapshot = (
        await market_data.get_snapshot(order.symbol)
        if market_data is not None
        else None
    )
    # A stale feed can't price a marketable limit safely — a price off stale data
    # could place the sell limit far above the live market and never fill (a failed
    # protective exit). Treat stale as un-priceable and hold + retry (consistent
    # with the §7 fill-price fallback, which also refuses a stale snapshot); the
    # feed's staleness is surfaced separately as market_data_stale.
    if snapshot is not None and snapshot.stale:
        snapshot = None
    price = protective_limit_price(snapshot, _protection_config(settings))
    if price is None:
        return None
    downgraded = order.model_copy(deep=True)
    downgraded.order_type = OrderType.LIMIT
    downgraded.limit_price = price
    return downgraded


async def _snapshot_fill_fallback(
    market_data: Optional[MarketDataService], symbol: str
) -> Optional[float]:
    """A trustworthy reconcile-time ``last_price`` for a MARKET order's fill-price
    fallback (§7), or ``None`` if the feed is absent / stale / untrustworthy. A
    stale or missing snapshot yields no fallback (never trade through bad data);
    the fill is then withheld and escalated exactly as before."""

    if market_data is None:
        return None
    snapshot = await market_data.get_snapshot(symbol)
    if snapshot is None or snapshot.stale:
        return None
    last_price = snapshot.last_price
    if finite_number_reason(last_price) is not None or last_price <= 0:
        return None
    return last_price


# --------------------------------------------------------------------------- #
# Sell-Side Protection (Phase 7 §5) — the autonomous breach -> exit driver.
# --------------------------------------------------------------------------- #

# Non-terminal BUY statuses a protective exit must clear so it truly reaches flat
# (§5.3). SUBMITTING (mid-claim, no broker id yet) and CANCEL_PENDING (already
# winding down) are left for the normal pipeline; everything else is terminal.
_CANCELLABLE_BUY_STATUSES = frozenset(
    {OrderStatus.CREATED, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}
)


async def cancel_open_buys(
    store: StateStore, adapter: BrokerAdapter, symbol: str
) -> None:
    """Cancel every open BUY for ``symbol`` before a protective exit (§5.3).

    Position derives only from *filled* shares, so an open unfilled BUY is
    invisible to the exit size — leaving one live would let a BUY fill and a
    protective SELL execute at the same time (a self-cross), or re-grow the very
    position being exited. A never-submitted ``CREATED`` buy is canceled locally;
    a live ``SUBMITTED``/``PARTIALLY_FILLED`` buy is canceled at the broker and
    moved to ``CANCEL_PENDING`` (a late fill still reconciles). Idempotent and
    audited via the store's transitions; shared with the flatten route."""

    orders = await store.list_orders()
    for order in orders:
        if order.symbol != symbol:
            continue
        if OrderSide(order.side) is not OrderSide.BUY:
            continue
        if order.status not in _CANCELLABLE_BUY_STATUSES:
            continue
        try:
            if order.status is OrderStatus.CREATED:
                # Never sent to the broker — cancel locally (D-013a style).
                await store.transition_order(order.id, OrderStatus.CANCELED)
            elif order.broker_order_id is not None:
                await adapter.cancel_order(order.broker_order_id)
                await store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
        except (BrokerError, *_TRANSITION_ERRORS) as exc:
            # Best-effort per order — a failure here must not crash the tick; the
            # next tick re-attempts (the order is still open).
            _log.warning(
                "protection: could not cancel open buy %s (%s): %s",
                order.id,
                symbol,
                exc,
            )


async def _run_protection(
    store: StateStore,
    adapter: BrokerAdapter,
    market_data: Optional[MarketDataService],
    settings: Settings,
) -> None:
    """The first monitoring phase (§5): detect hard-floor breaches on held
    positions and open protective exits behind the Approval Gate.

    A no-op when there is no market-data handle or protection is disabled. Never
    raises out of the tick (per-symbol try/except) — the loop's never-crash
    contract. Session auto-mint discipline: ``get_current_session`` is only called
    once there is a held position to evaluate, never on an idle tick."""

    if market_data is None or not settings.protection_enabled:
        return
    positions = [p for p in await store.list_positions() if p.quantity > 0]
    if not positions:
        # Even with nothing held, close out any lingering pause: a previously
        # paused symbol that went flat (e.g. a manual flatten under the kill
        # switch, D-P2) must still get its PAIRED protection_resumed rather than
        # leave an unpaired protection_paused in the durable log. Nothing is held,
        # so nothing is paused-and-breaching -> every currently-paused symbol
        # resumes. (No-op write when nothing was paused.)
        await _reconcile_protection_pause(store, set())
        return

    held = sorted({p.symbol for p in positions})
    # §5.1: make the monitoring loop the authority that keeps held symbols
    # subscribed (additive/idempotent) — protection covers a held-but-unarmed
    # symbol even when the strategy engine is disabled.
    try:
        await market_data.subscribe(held)
    except Exception:  # noqa: BLE001 - a feed hiccup must not crash the tick
        _log.exception("protection: subscribe(held=%s) failed", held)

    config = _protection_config(settings)
    session = await store.get_current_session()
    # Wave 3d (event_truth): read the §8 FSM. Only HALTED (the kill-switch state,
    # which dominates pause) pauses autonomous protection per D-P2; REDUCING
    # (buys-paused) does not. Equivalent to the prior ``session.kill_switch`` read.
    kill_switched = session.trading_state is TradingState.HALTED
    paused_breaching: set[str] = set()

    for position in positions:
        try:
            snapshot = await market_data.get_snapshot(position.symbol)
            breach = floor_breach_reason(position, snapshot, config)
            if breach is None:
                continue
            if kill_switched:
                # D-P2: the kill switch pauses autonomous protection. Record the
                # symbol as paused-and-breaching; the paused/resumed transition is
                # reconciled after the loop. Manual flatten still works (routes).
                paused_breaching.add(position.symbol)
                continue
            await _open_protective_exit(store, adapter, position, breach, session.id)
        except Exception:  # noqa: BLE001 - one symbol must not block the others
            _log.exception("protection tick failed for %s", position.symbol)

    await _reconcile_protection_pause(store, paused_breaching)


async def _open_protective_exit(
    store: StateStore,
    adapter: BrokerAdapter,
    position: Position,
    breach: FloorBreach,
    session_id: str,
) -> None:
    """Open one protective exit for a breaching symbol: cancel open buys, create a
    single-flight ``PROTECTION_FLOOR`` intent, auto-approve it, dispatch a MARKET
    order (type re-derived at submission — §5.4), and audit ``protection_triggered``.
    Idempotent: an already-active sell intent for the symbol short-circuits."""

    # Dedup: an exit is already in flight for this symbol (single-flight also
    # enforces this atomically in the store, but skipping here avoids re-cancelling
    # buys and re-auditing every tick while the first exit works).
    if await store.active_sell_intent_for(position.symbol) is not None:
        return

    # §5.3: clear open buys FIRST so the exit reaches — and stays — flat.
    await cancel_open_buys(store, adapter, position.symbol)

    # Re-read the live position after cancelling buys (a partial buy fill may have
    # landed); never size an exit above what is actually held (Rule 7 / no short).
    live = await store.get_position(position.symbol)
    if live.quantity <= 0:
        return

    intent = await store.create_sell_intent(
        symbol=position.symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=live.quantity,
        floor_price=breach.floor_price,
        observed_price=breach.observed_price,
        session_id=session_id,
    )
    # create_sell_intent is single-flight: if it returned a pre-existing active
    # intent that is already past PENDING, don't re-drive it.
    if intent.status is SellIntentStatus.PENDING:
        await store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    refreshed = await store.get_sell_intent(intent.id)
    if refreshed is None or refreshed.status is not SellIntentStatus.APPROVED:
        return

    order = await store.create_order_for_sell_intent(
        intent.id, order_type=OrderType.MARKET
    )
    await store.append_event(
        EventType.PROTECTION_TRIGGERED.value,
        message=(
            f"protection floor breached for {position.symbol}: last "
            f"{breach.observed_price} <= floor {breach.floor_price}; exiting "
            f"{live.quantity} shares"
        ),
        symbol=position.symbol,
        order_id=order.id,
        payload={
            "average_price": breach.average_price,
            "floor_price": breach.floor_price,
            "observed_price": breach.observed_price,
            "quantity": live.quantity,
        },
        session_id=session_id,
        correlation_id=intent.id,
    )


async def _currently_paused_symbols(store: StateStore) -> set[str]:
    """Symbols whose latest protection pause/resume event is a PAUSE — the durable
    "currently frozen by the kill switch" set, read from the append-only log so it
    survives a restart (mirrors the market-data stale/recovered pattern)."""

    paused: set[str] = set()
    for event in await store.list_events():
        if event.symbol is None:
            continue
        if event.event_type == EventType.PROTECTION_PAUSED.value:
            paused.add(event.symbol)
        elif event.event_type == EventType.PROTECTION_RESUMED.value:
            paused.discard(event.symbol)
    return paused


async def _reconcile_protection_pause(
    store: StateStore, paused_breaching: set[str]
) -> None:
    """Emit a per-symbol ``protection_paused`` when a symbol newly enters the
    kill-switched-and-breaching set, and ``protection_resumed`` when it leaves —
    a paired transition, never an unpaired once-ever flag (§5 step 4). So the
    operator sees exactly which positions are frozen, and the freeze clears (in
    the log) the moment the kill switch releases or the breach ends."""

    previously = await _currently_paused_symbols(store)
    for symbol in sorted(paused_breaching - previously):
        await store.append_event(
            EventType.PROTECTION_PAUSED.value,
            message=(
                f"protection for {symbol} is PAUSED while the kill switch is "
                f"engaged (floor breached; autonomous exit held)"
            ),
            symbol=symbol,
        )
    for symbol in sorted(previously - paused_breaching):
        await store.append_event(
            EventType.PROTECTION_RESUMED.value,
            message=(
                f"protection for {symbol} RESUMED (no longer kill-switched-and-"
                f"breaching)"
            ),
            symbol=symbol,
        )


async def monitoring_loop(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Settings,
    *,
    market_data: Optional[MarketDataService] = None,
) -> None:
    """Run forever: sleep one cadence, then run a tick. Never crashes.

    Sleeps *before* the first tick so app startup is not blocked and an injected
    store in a short-lived test (which is torn down well within one cadence)
    never reaches the tick body. ``market_data`` (Phase 7) is threaded to the
    tick for protective-sell pricing (§5.4) and fill-price fallback (§7); ``None``
    disables those paths (the loop still submits/reconciles BUYs unchanged).
    """

    _log.info(
        "monitoring loop started (cadence=%.3fs, unfilled_timeout=%.1fmin)",
        settings.poll_cadence_seconds,
        settings.unfilled_timeout_minutes,
    )
    # One persistent §7/§9 query budget shared across ALL of this loop's reconcile
    # REST calls (mass reports + targeted queries), refilling continuously across
    # ticks (wave 4e-4 / R6). Owned by the loop so it spans ticks; direct
    # ``run_monitoring_tick`` callers (tests) pass none and are unthrottled.
    reconcile_budget = ReconcileQueryBudget(settings.reconcile_query_budget_per_min)
    while True:
        try:
            await asyncio.sleep(settings.poll_cadence_seconds)
            await run_monitoring_tick(
                store, adapter, settings,
                market_data=market_data,
                reconcile_budget=reconcile_budget,
            )
        except asyncio.CancelledError:
            _log.info("monitoring loop cancelled; shutting down")
            raise
        except Exception:  # noqa: BLE001 - a tick failure must not stop the loop
            _log.exception("monitoring tick failed; continuing on next cadence")


async def run_monitoring_tick(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Settings,
    *,
    market_data: Optional[MarketDataService] = None,
    reconcile_budget: Optional[ReconcileQueryBudget] = None,
) -> None:
    """One monitoring iteration: submit pending orders, then reconcile open ones.

    Exposed separately from :func:`monitoring_loop` so tests drive a single,
    deterministic tick without the sleep/``while True`` wrapper. ``market_data``
    is **keyword-only with a ``None`` default** so every existing positional
    caller (tests, the Hypothesis state machine) is untouched; it feeds §5.4
    protective-sell order-type re-derivation and §7 fill-price fallback.
    """

    # Phase 7: protection runs FIRST so a protective order it creates is claimed
    # + submitted in the SAME tick (no extra cadence of latency). No-op when there
    # is no market-data handle or protection is disabled.
    await _run_protection(store, adapter, market_data, settings)
    await _submit_pending_orders(
        store, adapter, settings, market_data=market_data
    )
    await _redrive_stale_submitting(
        store, adapter, settings, market_data=market_data
    )
    # ADR-002: resolve any TIMEOUT_QUARANTINE order with a read-only targeted query
    # BEFORE the open-order reconcile — a resolution to SUBMITTED hands the order a
    # broker_order_id that the reconcile poll then tracks (and ingests fills for)
    # this same tick.
    await _resolve_timeout_quarantine(store, adapter, settings)
    await _reconcile_open_orders(
        store, adapter, settings, market_data=market_data
    )
    await _recover_unpersisted_submits(store, adapter)
    # Phase 4 wave 4e: the ACTING §7 mass-report reconcile. Runs LAST so it sees the
    # fully-reconciled post-tick state — a divergence it acts on is then one the
    # per-order poll structurally *couldn't* capture (an external venue order).
    # Slice 4e-2 surfaces external/unmanaged orders (non-mutating); later slices add
    # not-found resolution (4e-3) + synthetic fills/parity/throttle (4e-4).
    # Failure-isolated; gated by ``reconciliation_enabled`` (default on).
    await _run_reconciliation(store, adapter, settings, budget=reconcile_budget)


async def _submit_pending_orders(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Optional[Settings] = None,
    *,
    market_data: Optional[MarketDataService] = None,
) -> None:
    """Claim eligible ``CREATED`` orders atomically, then submit only the claims.

    The submission-claim (D-017) closes the F-001/F-002 race: instead of reading
    the controls, awaiting the broker, and *then* marking the order (a window in
    which a kill-switch flip or a session close could slip in undetected), the
    loop asks the store to **atomically** re-check every control and move the
    order ``CREATED → SUBMITTING`` under one lock hold. Only a claimed
    (``SUBMITTING``) order reaches ``adapter.submit_order``. Because the claim
    and every control mutation serialize through the same lock, a flip lands
    either before the claim (order stays ``CREATED``, held) or after it (already
    committed to submission) — never in between.

    A transient submit failure releases the claim (``SUBMITTING → CREATED``) so
    the next tick re-runs the full gate. A broker-accepted order the store then
    can't mark ``SUBMITTED`` (e.g. a manual cancel raced the submit) is handed to
    the durable recovery ledger, not a lone best-effort cancel.
    """

    created = [o for o in await store.list_orders() if o.status is OrderStatus.CREATED]
    if not created:
        return

    blocked_already: Optional[set[str]] = None

    for order in created:
        claim = await store.claim_order_for_submission(order.id)
        if claim.outcome == CLAIM_BLOCKED:
            # Held by a control — audited once per order (not per tick), matching
            # the prior behavior. The claim wrote no state change.
            if blocked_already is None:
                blocked_already = await _orders_with_event(
                    store, EventType.ORDER_SUBMISSION_BLOCKED.value
                )
            if order.id not in blocked_already:
                await store.append_event(
                    EventType.ORDER_SUBMISSION_BLOCKED.value,
                    message=f"submission of {order.symbol} held: {claim.reason}",
                    symbol=order.symbol,
                    candidate_id=order.candidate_id,
                    order_id=order.id,
                    payload={"reason": claim.reason},
                    session_id=order.session_id,
                )
                blocked_already.add(order.id)
            continue
        if claim.outcome != CLAIM_CLAIMED:
            # CLAIM_SKIPPED: no longer CREATED (a session close cancelled it, or
            # it was already claimed). Nothing to submit.
            continue

        # The order is now SUBMITTING — the backend has committed to sending it.
        claimed = claim.order

        # §5.4 (Rule 12 / D-015): decide a protective sell's session-conditional
        # order type HERE, at the single submission choke point, not at creation.
        # A MARKET sell stays MARKET in regular hours, downgrades to a live-priced
        # LIMIT in pre/after-hours; an un-priceable pre/after-hours sell holds.
        effective = await _effective_submit_order(claimed, market_data, settings)
        if effective is None:
            _log.info(
                "holding protective sell %s (%s): no priceable snapshot this tick; "
                "releasing claim to retry",
                claimed.id,
                claimed.symbol,
            )
            # A SELL always releases to CREATED (never CANCELED) — §5.5.
            try:
                await store.transition_order(claimed.id, OrderStatus.CREATED)
            except _TRANSITION_ERRORS as rel_exc:
                _log.warning(
                    "could not release un-priceable sell %s: %s", claimed.id, rel_exc
                )
            continue

        try:
            broker_order_id = await adapter.submit_order(effective)
            # AIR-001: a well-behaved adapter returns a non-empty id or raises.
            # Defend against a contract violation here too — an empty id must
            # never reach the SUBMITTING -> SUBMITTED transition (it would strand
            # an untrackable "submitted" order). Treat it as a submit failure so
            # the claim releases and the next tick re-drives idempotently.
            if not isinstance(broker_order_id, str) or not broker_order_id.strip():
                raise BrokerError(
                    f"adapter returned an empty broker id for order {claimed.id}"
                )
        except TerminalBrokerError as exc:
            # AIR-003 (review follow-up): a *definitive* broker rejection on the
            # first submit (403/422/delisted, or a duplicate whose lookup fails).
            # Releasing SUBMITTING -> CREATED here would re-submit a doomed order
            # every tick forever (a CREATED<->SUBMITTING livelock hammering the
            # broker, never escalated) — the same class this wave closed on the
            # re-drive path. Escalate to a durable needs_review record instead, so
            # a human reconciles rather than the loop guessing. Deduped/skipped by
            # the stale-SUBMITTING re-drive step (it carries an open recovery now).
            _log.error(
                "submit of order %s (%s) definitively rejected (terminal); "
                "escalating to needs_review instead of retrying: %s",
                claimed.id,
                claimed.symbol,
                exc,
            )
            await _escalate_stale_submitting(store, claimed, exc)
            continue
        except AmbiguousBrokerError as exc:
            # ADR-002: the submit's outcome is UNKNOWN (timeout/504/transport after
            # the request may have reached Alpaca). Do NOT release to CREATED — the
            # next tick would blind-resubmit an order that may already be live (a
            # double-fire / oversell path) — and do NOT escalate it as a definitive
            # failure. Quarantine it (SUBMITTING -> TIMEOUT_QUARANTINE, event-truth)
            # and let _resolve_timeout_quarantine reconcile it with a READ-ONLY
            # targeted client_order_id query. The order stays non-terminal (it may
            # be live, so it keeps counting toward exposure) and is structurally
            # unreachable by any resubmit sweep while quarantined.
            _log.warning(
                "submit of order %s (%s) is AMBIGUOUS (may be live at the venue); "
                "quarantining for targeted reconciliation, not resubmitting: %s",
                claimed.id,
                claimed.symbol,
                exc,
            )
            try:
                await store.quarantine_timed_out_order(
                    claimed.id, reason="ambiguous_submit"
                )
            except _TRANSITION_ERRORS as q_exc:
                # The order left SUBMITTING some other way (e.g. a manual cancel
                # during the broker call) — nothing to quarantine. Safe to skip.
                _log.warning(
                    "could not quarantine ambiguous submit %s: %s", claimed.id, q_exc
                )
            continue
        except Exception as exc:  # noqa: BLE001 - release the claim, retry next tick
            # Releasing SUBMITTING -> CREATED lets the next tick re-run the full
            # gate. But if the order's OWN session closed during the submit await
            # (session close skips SUBMITTING orders, so the claim shielded it
            # from close's CREATED-order cancel), releasing to CREATED would
            # strand a zombie CREATED order in a closed session forever — close
            # is one-shot and never runs again, and no other path cleans it up,
            # so it would count toward CAPI exposure indefinitely (regressing
            # D-013a's no-zombie-CREATED-after-close invariant). In that case
            # cancel it instead — exactly what close would have done to a CREATED
            # order. A merely kill-switched/paused session still releases to
            # CREATED (reversible: the next claim holds it until the stop clears).
            # §5.5 (side-aware release): a SELL is legitimately submittable in a
            # closed session (§5.2) and keeps reconciling post-close (D-011), so it
            # ALWAYS releases SUBMITTING -> CREATED to retry next tick — never
            # CANCELED. Only a BUY keeps D-013a's no-zombie CANCELED when its own
            # session closed during the submit await (close is one-shot and would
            # otherwise leave a CREATED buy counting toward exposure forever).
            release_target = OrderStatus.CREATED
            if OrderSide(claimed.side) is OrderSide.BUY:
                own_session = await store.get_session_by_id(claimed.session_id)
                if (
                    own_session is not None
                    and own_session.status is SessionStatus.CLOSED
                ):
                    release_target = OrderStatus.CANCELED
            _log.warning(
                "submit failed for order %s (%s); releasing claim to %s: %s",
                claimed.id,
                claimed.symbol,
                release_target.value,
                exc,
            )
            try:
                await store.transition_order(claimed.id, release_target)
            except _TRANSITION_ERRORS as rel_exc:
                # The order left SUBMITTING some other way (e.g. a manual cancel
                # during the broker call) — nothing to release. Safe to skip.
                _log.warning(
                    "could not release claim on order %s: %s", claimed.id, rel_exc
                )
            continue
        try:
            await store.transition_order(
                claimed.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
            )
        except _TRANSITION_ERRORS as exc:
            # Broker accepted it but the store couldn't mark it SUBMITTED (most
            # often a manual cancel landing during the submit call: SUBMITTING →
            # CANCELED, so SUBMITTING → SUBMITTED is now illegal). The order is
            # live upstream but locally terminal — record it durably so the
            # recovery loop cancels it, not a single best-effort attempt.
            await _handle_unpersisted_submit(
                store, adapter, claimed, broker_order_id, exc
            )


async def _redrive_stale_submitting(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Settings,
    *,
    market_data: Optional[MarketDataService] = None,
) -> None:
    """Recover ``SUBMITTING`` orders left id-less by a crash between claim and
    submit (AIR-003).

    A claim (D-017) writes ``SUBMITTING`` durably *before* the broker call; if the
    process dies before ``submit_order`` returns and is persisted, the order is
    stuck ``SUBMITTING`` with ``broker_order_id=None`` — excluded from both the
    ``CREATED`` submit sweep and the open-order reconcile poll, so nothing else
    ever touches it. It inflates CAPI exposure (correct — it may be live at the
    broker) but is otherwise invisible and never advances.

    The durable ``SUBMITTING`` row plus the stable ``client_order_id`` (``order.id``)
    IS the outbox — no separate table needed. Re-driving each such order through
    ``adapter.submit_order`` is inherently double-submit-safe: a fresh submit either
    creates the broker order or recovers the already-accepted one by client id.

    * A non-empty broker id back → ``SUBMITTING → SUBMITTED`` with it; reconcile
      then tracks it normally.
    * A transient :class:`BrokerError` → leave it ``SUBMITTING`` to retry next tick
      (idempotent, not a blind double-submit).
    * A :class:`TerminalBrokerError` (or an empty id, or the store rejecting the
      transition) → escalate to a durable ``needs_review`` recovery record rather
      than guessing. Deduped: an order already carrying an open recovery record is
      neither re-driven nor re-recorded.

    **Livelock backstop (AIR-003 review).** The transient path retries every tick.
    A *permanent* broker rejection that a (buggy or unknown-error) adapter reports
    as a plain ``BrokerError`` would otherwise retry forever, inflating exposure and
    never surfacing. So each transient failure records a durable
    ``stale_submitting_redrive_deferred`` audit event; once an order accumulates
    ``settings.stale_submitting_max_redrive_attempts`` of them it is escalated to a
    ``needs_review`` record instead of re-driven again — a bound the correct
    :class:`TerminalBrokerError` classification should normally beat, but which no
    misclassification can slip past.
    """

    stale = [
        o
        for o in await store.list_orders()
        if o.status is OrderStatus.SUBMITTING and not o.broker_order_id
    ]
    if not stale:
        return

    open_recoveries = await store.list_submit_recoveries(
        statuses=RECOVERY_OPEN_STATUSES
    )
    already_covered = {r.local_order_id for r in open_recoveries}
    max_attempts = settings.stale_submitting_max_redrive_attempts

    for order in stale:
        if order.id in already_covered:
            continue
        # Backstop: too many transient re-drive failures already → treat as a
        # permanent failure the classifier missed and escalate rather than loop.
        prior_attempts = await _order_event_count(
            store, order.id, EventType.STALE_SUBMITTING_REDRIVE_DEFERRED.value
        )
        if prior_attempts >= max_attempts:
            _log.error(
                "stale SUBMITTING order %s exhausted %s transient re-drive "
                "attempts; escalating to needs_review",
                order.id,
                prior_attempts,
            )
            await _escalate_stale_submitting(
                store,
                order,
                RuntimeError(
                    f"exhausted {prior_attempts} transient re-drive attempts "
                    f"(>= max {max_attempts})"
                ),
            )
            continue
        # §5.4: re-derive a protective sell's order type at THIS submission too
        # (the stale-re-drive is one of the three submit choke points). An
        # un-priceable pre/after-hours sell is left SUBMITTING to retry next tick
        # (identical to the transient-BrokerError disposition below).
        effective = await _effective_submit_order(order, market_data, settings)
        if effective is None:
            _log.info(
                "stale protective sell %s (%s): no priceable snapshot; leaving "
                "SUBMITTING to retry next tick",
                order.id,
                order.symbol,
            )
            continue
        try:
            broker_order_id = await adapter.submit_order(effective)
            if not isinstance(broker_order_id, str) or not broker_order_id.strip():
                raise TerminalBrokerError(
                    f"adapter returned an empty broker id re-driving stale "
                    f"SUBMITTING order {order.id}"
                )
        except TerminalBrokerError as exc:
            _log.error(
                "stale SUBMITTING order %s could not be re-driven (terminal); "
                "escalating to needs_review: %s",
                order.id,
                exc,
            )
            await _escalate_stale_submitting(store, order, exc)
            continue
        except AmbiguousBrokerError as exc:
            # ADR-002: an ambiguous re-drive outcome is QUARANTINED, not re-deferred
            # — blind-re-driving an order that may now be live at the venue is the
            # oversell/double-fire path the ADR exists to close. Same targeted
            # read-only reconciliation as a first-submit ambiguity resolves it.
            _log.warning(
                "re-drive of stale SUBMITTING order %s is AMBIGUOUS; quarantining "
                "for targeted reconciliation, not re-driving: %s",
                order.id,
                exc,
            )
            try:
                await store.quarantine_timed_out_order(
                    order.id, reason="ambiguous_submit"
                )
            except _TRANSITION_ERRORS as q_exc:
                _log.warning(
                    "could not quarantine ambiguous re-drive %s: %s", order.id, q_exc
                )
            continue
        except BrokerError as exc:
            # Transient — leave it SUBMITTING; the next tick re-drives idempotently.
            # Record the attempt durably so the backstop above can bound it.
            _log.warning(
                "stale SUBMITTING order %s re-drive failed (transient, attempt "
                "%s/%s), will retry next tick: %s",
                order.id,
                prior_attempts + 1,
                max_attempts,
                exc,
            )
            await _record_redrive_deferral(store, order, prior_attempts + 1, exc)
            continue

        try:
            await store.transition_order(
                order.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
            )
            _log.info(
                "re-drove stale SUBMITTING order %s to SUBMITTED as broker %s",
                order.id,
                broker_order_id,
            )
        except _TRANSITION_ERRORS as exc:
            # The order left SUBMITTING some other way (e.g. a manual cancel) while
            # we re-drove it — the broker order is live but locally terminal. Same
            # durable path as the primary submit's unpersisted case.
            await _handle_unpersisted_submit(store, adapter, order, broker_order_id, exc)


# Venue-terminal statuses a targeted query can resolve a quarantine to directly
# (no fills to ingest). A working/filled venue order is instead adopted as
# SUBMITTED so the reconcile poll ingests fills (FILLED via SUBMITTED — INV-9).
_QUARANTINE_TERMINAL_RESOLUTIONS = frozenset(
    {OrderStatus.CANCELED, OrderStatus.REJECTED}
)


async def _resolve_timeout_quarantine(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Optional[Settings] = None,
) -> None:
    """Resolve ``TIMEOUT_QUARANTINE`` orders (ADR-002) with a READ-ONLY targeted
    query — the whole point is to NEVER resubmit an order that may already be live.

    For each quarantined order, ask the venue "do you have the order I submitted
    under this ``client_order_id``?" (``get_order_by_client_order_id``, keyed on the
    stable ``order.id``):

    * venue HAS it, working/filled → adopt as ``SUBMITTED`` with its broker id; the
      open-order reconcile (same tick) then tracks it and ingests fills;
    * venue HAS it, already canceled/rejected → resolve to that terminal state;
    * venue CONFIRMS absent (``None``) → the submit never landed, but only after a
      bounded number of confirmations (§7: a single not-found could be venue lag)
      resolve to ``REJECTED``; else defer and retry next tick;
    * query FAILS (``BrokerError``) → inconclusive; leave quarantined and retry —
      NEVER read a failed query as "absent" (§7 safeguard: that is an oversell
      path). Past the same bound, surface it for **manual review** (a durable
      deferral marked ``needs_review``) rather than guessing; the order stays
      quarantined and operator-visible (full stuck-reconciliation alerting is
      Phase 4).

    The order-status flip is event-authoritative (a ``SUBMITTED``/``REJECTED``/
    ``CANCELED`` ``ExecutionEvent`` co-written by ``resolve_timeout_quarantine``).
    Best-effort per order — a store/broker error on one never stops the loop.
    """

    max_attempts = (settings or Settings()).timeout_quarantine_max_query_attempts
    for order in await store.list_timeout_quarantined_orders():
        try:
            update = await adapter.get_order_by_client_order_id(order.id)
        except BrokerError as exc:
            # Inconclusive — a query FAILURE is NEVER read as "absent" (§7): it only
            # retries. Surface for manual review once we've failed to get a clean
            # answer max_attempts times, then STOP appending — bounded, so a
            # persistent venue outage does not grow the event log every tick forever
            # (full stuck-reconciliation alerting is Phase 4). Counts ONLY
            # query_error deferrals, independent of the not-found bound below.
            errors = await _order_deferral_count(store, order.id, "query_error")
            if errors < max_attempts:
                await _record_timeout_query_deferral(
                    store, order, errors + 1, "query_error",
                    needs_review=errors + 1 >= max_attempts, error=str(exc),
                )
            continue

        if update is not None:
            # Route to SUBMITTED (adopt the venue id) unless the venue order is a
            # CLEAN terminal — canceled/rejected with ZERO fills. A canceled/rejected
            # order that PARTIALLY FILLED still carries broker-authoritative shares
            # (get_order_by_client_order_id reports filled_quantity), so it must go
            # through SUBMITTED first and let the reconcile poll INGEST those fills
            # (§7 "fills preserved"; INV-9) before finalizing — never drop a real
            # fill by jumping straight to a terminal (that strands an untracked long).
            clean_terminal = (
                update.status in _QUARANTINE_TERMINAL_RESOLUTIONS
                and update.filled_quantity == 0
            )
            if clean_terminal:
                target, broker_id = update.status, None
            else:
                target, broker_id = OrderStatus.SUBMITTED, update.broker_order_id
            try:
                await store.resolve_timeout_quarantine(
                    order.id, target, broker_order_id=broker_id, reason="targeted_query"
                )
                _log.info(
                    "resolved quarantined order %s via targeted query: venue %s -> %s",
                    order.id, update.status.value, target.value,
                )
            except _TRANSITION_ERRORS as exc:
                # e.g. resolving to SUBMITTED with no broker id (AIR-001), or the
                # order left TIMEOUT_QUARANTINE another way — leave it, retry.
                _log.warning(
                    "could not resolve quarantined order %s to %s: %s",
                    order.id, target.value, exc,
                )
            continue

        # Confirmed absent at the venue. Only a CONFIRMED not-found advances this
        # bound (query FAILURES use a SEPARATE counter), so the venue-lag tolerance
        # is exactly max_attempts confirmations (§7) — a run of query errors can
        # never erode it and prematurely REJECT a possibly-live order.
        attempts = await _order_deferral_count(store, order.id, "not_found") + 1
        if attempts >= max_attempts:
            _log.info(
                "quarantined order %s confirmed absent after %s queries; "
                "resolving to REJECTED (never landed).", order.id, attempts,
            )
            try:
                await store.resolve_timeout_quarantine(
                    order.id, OrderStatus.REJECTED, reason="not_found_at_venue"
                )
            except _TRANSITION_ERRORS as exc:
                _log.warning("could not reject absent quarantined %s: %s", order.id, exc)
        else:
            await _record_timeout_query_deferral(store, order, attempts, "not_found")


async def _record_timeout_query_deferral(
    store: StateStore,
    order: Order,
    attempt: int,
    reason: str,
    *,
    needs_review: bool = False,
    error: Optional[str] = None,
) -> None:
    """Durably record one targeted-query deferral so the bound can count them across
    ticks and restarts (ADR-002). ``needs_review`` marks a persistently-inconclusive
    order for operator attention. Best-effort (never crashes the tick)."""

    payload: dict[str, object] = {"attempt": attempt, "reason": reason}
    if needs_review:
        payload["needs_review"] = True
    if error is not None:
        payload["error"] = error
    try:
        await store.append_event(
            EventType.ORDER_TIMEOUT_QUARANTINE_DEFERRED.value,
            message=(
                f"timeout-quarantine resolution deferred for {order.symbol} "
                f"({reason}, attempt {attempt})"
                + (" — NEEDS REVIEW" if needs_review else "")
            ),
            symbol=order.symbol,
            candidate_id=order.candidate_id,
            order_id=order.id,
            payload=payload,
            session_id=order.session_id,
        )
    except Exception:  # noqa: BLE001 - audit is best-effort on a resolution path
        _log.exception(
            "could not record timeout-quarantine deferral for order %s", order.id
        )


async def _escalate_stale_submitting(
    store: StateStore, order: Order, exc: Exception
) -> None:
    """Write a durable ``needs_review`` recovery record for a stale ``SUBMITTING``
    order whose idempotent re-drive hit a terminal error (or exhausted the transient
    retry bound) — the broker's acceptance can't be confirmed, so a human must
    reconcile rather than the loop guessing. Best-effort: a store error here must
    not crash the tick (the order stays SUBMITTING and is retried next cadence)."""

    try:
        await store.create_submit_recovery(
            local_order_id=order.id,
            # The re-drive could not confirm a broker id (terminal error / failed
            # duplicate lookup); the client_order_id (order.id) is the only handle.
            broker_order_id=order.broker_order_id or "",
            client_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason=f"stale SUBMITTING re-drive could not be resolved: {exc}",
            session_id=order.session_id,
            candidate_id=order.candidate_id,
            cleanup_status=RECOVERY_NEEDS_REVIEW,
            event_type=EventType.SUBMIT_RECOVERY_NEEDS_REVIEW.value,
        )
    except Exception:  # noqa: BLE001 - escalation is best-effort on a failure path
        _log.exception(
            "could not escalate stale SUBMITTING order %s to needs_review", order.id
        )


async def _record_redrive_deferral(
    store: StateStore, order: Order, attempt: int, exc: Exception
) -> None:
    """Durably record one transient re-drive deferral so the livelock backstop can
    count them across ticks and restarts. Best-effort (never crashes the tick)."""

    try:
        await store.append_event(
            EventType.STALE_SUBMITTING_REDRIVE_DEFERRED.value,
            message=(
                f"stale SUBMITTING order {order.symbol} re-drive deferred "
                f"(transient, attempt {attempt})"
            ),
            symbol=order.symbol,
            candidate_id=order.candidate_id,
            order_id=order.id,
            payload={"attempt": attempt, "error": str(exc)},
            session_id=order.session_id,
        )
    except Exception:  # noqa: BLE001 - audit is best-effort on a failure path
        _log.exception(
            "could not record re-drive deferral for order %s", order.id
        )


async def _order_event_count(
    store: StateStore, order_id: str, event_type: str
) -> int:
    """How many events of ``event_type`` are recorded for ``order_id`` (durable,
    survives restart). Uses the store-side ``event_type`` filter, then counts the
    order's own rows — the beta-scale event log is small; an indexed query is the
    upgrade if it ever grows large."""

    events = await store.list_events(event_type=event_type)
    return sum(1 for e in events if e.order_id == order_id)


async def _order_deferral_count(
    store: StateStore,
    order_id: str,
    reason: str,
    *,
    event_type: str = EventType.ORDER_TIMEOUT_QUARANTINE_DEFERRED.value,
) -> int:
    """Count deferrals of a SPECIFIC ``reason`` for one order, within one deferral
    ``event_type`` (ADR-002 timeout-quarantine, or wave-4e-3 reconcile not-found).
    The not-found bound and the query-error bound must be INDEPENDENT — §7 forbids a
    query FAILURE from advancing the confirmed-not-found bound (that would let a run
    of failures prematurely reject a possibly-live order). Filtering on
    ``payload.reason`` keeps the two bounds separate through one event type."""

    events = await store.list_events(event_type=event_type)
    return sum(
        1
        for e in events
        if e.order_id == order_id and (e.payload or {}).get("reason") == reason
    )


async def _handle_unpersisted_submit(
    store: StateStore,
    adapter: BrokerAdapter,
    order: Order,
    broker_order_id: str,
    exc: Exception,
) -> None:
    """The broker accepted an order we then couldn't mark ``SUBMITTED``.

    Two distinct situations reach here, and they need opposite handling:

    * **Transient persist failure, order still ``SUBMITTING``.** The order is
      genuinely open at the broker — we just failed to record ``SUBMITTED``.
      *Retry* the transition so reconcile can track it; do **not** cancel a
      legitimately-open order. This is the common, benign case.
    * **A manual cancel raced the submit, order now ``CANCELED``/``REJECTED``
      locally.** The order is live at the broker but the local state treats it
      as terminal — the true F-002 orphan. A single best-effort cancel is not
      enough (if it fails the broker order is orphaned), so write a **durable
      recovery record**: the recovery loop (``_recover_unpersisted_submits``)
      then polls/cancels ``broker_order_id`` every cadence until it is confirmed
      no longer live. The same durable path is used if the retry above also
      fails — an order we cannot track is safer cancelled than left live and
      invisible.

    Best-effort and swallows its own errors — this runs on a failure path and
    must not crash the loop.
    """

    _log.error(
        "order %s submitted to broker as %s but could not be marked SUBMITTED: %s",
        order.id,
        broker_order_id,
        exc,
    )
    try:
        await store.append_event(
            EventType.ORDER_SUBMIT_UNPERSISTED.value,
            message=(
                f"order {order.symbol} accepted by broker as {broker_order_id} "
                f"but could not be marked SUBMITTED"
            ),
            symbol=order.symbol,
            candidate_id=order.candidate_id,
            order_id=order.id,
            payload={"broker_order_id": broker_order_id, "error": str(exc)},
            session_id=order.session_id,
        )
    except Exception:  # noqa: BLE001 - audit is best-effort on a failure path
        _log.exception(
            "could not record order_submit_unpersisted for order %s", order.id
        )

    try:
        current = await store.get_order(order.id)
    except Exception:  # noqa: BLE001
        current = None
    status = current.status if current is not None else None

    if status is OrderStatus.SUBMITTING:
        # Order is legitimately open at the broker; retry recording SUBMITTED.
        try:
            await store.transition_order(
                order.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
            )
            _log.info(
                "recovered unpersisted submit for order %s on retry", order.id
            )
            return
        except _TRANSITION_ERRORS as retry_exc:
            _log.error(
                "retry to mark order %s SUBMITTED failed; recording recovery: %s",
                order.id,
                retry_exc,
            )

    # Locally terminal (manual cancel raced) or the retry failed: the broker
    # order is live but untrackable locally. Record it durably so the recovery
    # loop cancels it — not a single best-effort attempt (the F-002 fix).
    try:
        await store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=broker_order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason=str(exc),
            session_id=order.session_id,
            candidate_id=order.candidate_id,
        )
    except Exception:  # noqa: BLE001 - even the recovery write is best-effort here
        _log.exception(
            "could not write submit-recovery record for order %s (broker %s)",
            order.id,
            broker_order_id,
        )


def _broker_filled(update: BrokerOrderUpdate) -> int:
    """How many shares the broker reports filled on a recovery poll — the
    order's cumulative ``filled_quantity`` plus any per-execution fills it
    carries, whichever is larger (adapters differ on which they populate)."""

    from_fills = sum(f.quantity for f in (update.fills or []))
    return max(update.filled_quantity or 0, from_fills)


async def _recover_unpersisted_submits(
    store: StateStore, adapter: BrokerAdapter
) -> None:
    """Drive every unresolved broker-submit recovery record toward resolution.

    For each record (D-017 / F-002):

    * **Any fills** (partial *or* full) → the broker order executed some shares
      the local state never tracked: a **real untracked position**. Mark it
      ``needs_review`` and surface it loudly — never cancel-and-drop it. This is
      the key fix over the naive "cancel anything not already terminal" loop,
      which silently discarded a partial fill's already-executed shares.
    * **Zero fills, terminal at broker** (``CANCELED``/``REJECTED``) → nothing
      live: ``resolved_canceled``.
    * **Zero fills, still live** → request a cancel and re-poll; if the confirm
      shows fills, escalate to ``needs_review``; if terminal, resolve; else
      leave unresolved to retry next cadence (not a single attempt).

    Only ``RECOVERY_UNRESOLVED`` records are acted on — a ``needs_review`` record
    is done being worked automatically and stays visible to the operator until a
    human reconciles it. Best-effort per record; a broker error leaves it
    unresolved for the next tick and never crashes the loop.
    """

    records = await store.list_submit_recoveries(statuses={RECOVERY_UNRESOLVED})
    for rec in records:
        try:
            update = await adapter.get_order_status(
                rec.broker_order_id, recorded_quantity=0
            )
        except Exception as exc:  # noqa: BLE001 - retry next tick
            _log.warning(
                "recovery poll failed for broker order %s: %s",
                rec.broker_order_id,
                exc,
            )
            await store.update_submit_recovery(rec.id, bump_attempt=True)
            continue

        if _broker_filled(update) > 0:
            # Partial OR full fill: a real untracked position. Do not cancel the
            # remainder and mark it "resolved" — that would silently discard the
            # already-executed shares. Flag for human reconciliation.
            _log.error(
                "stranded broker order %s has %s filled shares before recovery "
                "could cancel it — a real untracked position needs manual review",
                rec.broker_order_id,
                _broker_filled(update),
            )
            await store.update_submit_recovery(
                rec.id, cleanup_status=RECOVERY_NEEDS_REVIEW, bump_attempt=True
            )
            continue
        if update.status in (OrderStatus.CANCELED, OrderStatus.REJECTED):
            await store.update_submit_recovery(
                rec.id, cleanup_status=RECOVERY_RESOLVED, bump_attempt=True
            )
            _log.info("recovered stranded broker order %s (terminal at broker)", rec.broker_order_id)
            continue

        # Zero fills and still live → request a cancel and confirm.
        try:
            await adapter.cancel_order(rec.broker_order_id)
            confirm = await adapter.get_order_status(
                rec.broker_order_id, recorded_quantity=0
            )
        except Exception as exc:  # noqa: BLE001 - retry next tick
            _log.warning(
                "recovery cancel failed for broker order %s: %s",
                rec.broker_order_id,
                exc,
            )
            await store.update_submit_recovery(rec.id, bump_attempt=True)
            continue

        if _broker_filled(confirm) > 0:
            # A fill landed during the cancel window — same untracked-position
            # concern; escalate to needs_review rather than resolved.
            await store.update_submit_recovery(
                rec.id, cleanup_status=RECOVERY_NEEDS_REVIEW, bump_attempt=True
            )
        elif confirm.status in (OrderStatus.CANCELED, OrderStatus.REJECTED):
            await store.update_submit_recovery(
                rec.id, cleanup_status=RECOVERY_RESOLVED, bump_attempt=True
            )
            _log.info("recovered stranded broker order %s (cancel confirmed)", rec.broker_order_id)
        else:
            # Cancel requested but not yet confirmed terminal — retry next tick.
            await store.update_submit_recovery(rec.id, bump_attempt=True)


async def _reconcile_open_orders(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Settings,
    *,
    market_data: Optional[MarketDataService] = None,
) -> None:
    """Poll each open order, apply fills + status, and flag stale ones.

    Open = ``SUBMITTED`` or ``PARTIALLY_FILLED``, regardless of whether the
    order's session is closed (D-011). Stale = open past the unfilled timeout;
    flagged exactly once per order (the check reads the persisted event log, so
    it survives a restart and never spams one event per tick).
    """

    open_orders = [o for o in await store.list_orders() if o.status in _OPEN_STATUSES]
    if not open_orders:
        return

    already_stale = await _orders_with_event(store, EventType.ORDER_STALE.value)
    timeout = timedelta(minutes=settings.unfilled_timeout_minutes)
    now = utcnow()

    for order in open_orders:
        if order.broker_order_id is not None:
            # §7: a MARKET order (only ever a protective sell) has no limit_price,
            # so a transiently-absent broker fill price would withhold a
            # position-critical fill and — with the single-flight dedup — strand
            # protection. Supply the reconcile-time snapshot last_price as the
            # last-resort audit price (a long-only sell's price doesn't change the
            # quantity/cost-basis fold). Only for a MARKET order; a BUY/LIMIT keeps
            # the filled_avg -> limit resolution untouched.
            fallback_price = None
            if OrderType(order.order_type) is OrderType.MARKET:
                fallback_price = await _snapshot_fill_fallback(
                    market_data, order.symbol
                )
            try:
                # Pass what we've already recorded so an adapter that only sees
                # the broker's cumulative fill can emit a correct delta.
                update = await adapter.get_order_status(
                    order.broker_order_id,
                    recorded_quantity=order.filled_quantity,
                    fallback_price=fallback_price,
                )
            except Exception as exc:  # noqa: BLE001 - skip this order, never crash
                _log.warning(
                    "status poll failed for order %s (%s): %s",
                    order.id,
                    order.symbol,
                    exc,
                )
            else:
                await _apply_update(store, order, update)

        # Stale check on the *refreshed* order — applying the update above may
        # have moved it to a terminal state (or to cancel_pending), in which case
        # it is no longer eligible for the unfilled-timeout flag.
        fresh = await store.get_order(order.id)
        if fresh is None or fresh.status not in _STALEABLE_STATUSES:
            continue
        if fresh.id in already_stale:
            continue
        age = _order_age(now, fresh.created_at)
        if age > timeout:
            await store.append_event(
                EventType.ORDER_STALE.value,
                message=(
                    f"order {fresh.symbol} unfilled after "
                    f"{age.total_seconds() / 60:.1f} min (timeout "
                    f"{settings.unfilled_timeout_minutes:.1f} min)"
                ),
                symbol=fresh.symbol,
                candidate_id=fresh.candidate_id,
                order_id=fresh.id,
                payload={
                    "age_seconds": age.total_seconds(),
                    "unfilled_timeout_minutes": settings.unfilled_timeout_minutes,
                    "status": fresh.status.value,
                    "filled_quantity": fresh.filled_quantity,
                },
                session_id=fresh.session_id,
            )
            already_stale.add(fresh.id)


async def _apply_update(
    store: StateStore, order: Order, update: BrokerOrderUpdate
) -> None:
    """Append the broker's reported fills, then reconcile the order to the
    fills we actually **recorded** — never to the broker's raw scalar.

    Fills are appended first so the derived position reflects exactly what
    filled; the store dedups by ``source_fill_id`` (a replayed fill is ignored,
    not double-counted) and rejects any fill inconsistent with the order.

    The order's ``filled_quantity`` and status are then set from the *recorded*
    fill sum, not from ``update.filled_quantity``. This keeps the two truths in
    lockstep: ``order.filled_quantity`` always equals the sum of appended fills
    (= the derived position for a long-only buy), so a dropped or rejected fill
    can never let the order claim more filled than the position supports — and
    the order is never marked FILLED without the fills to back it. A broker
    cancel/reject is still honoured as a terminal state.

    **AIR-002 divergence escalation:** if, after appending, the broker's cumulative
    ``filled_quantity`` still *exceeds* what we could record (a fill the store
    rejected, or one the adapter withheld as un-priceable), that is a real
    untracked position — the broker executed shares we have no fill for. Rather
    than silently reconciling to the local number (which would strand the order
    forever, or worse mark it terminal CANCELED and discard the executed shares),
    write a durable operator-visible ``needs_review`` reconciliation record and
    hold the order in a non-terminal, still-visible state. Positions still derive
    only from appended fills — the record is the truth-divergence signal, not a
    position mutation.
    """

    rejected: list[dict[str, Any]] = []
    for bf in update.fills:
        try:
            await store.append_fill(
                order.id,
                order.symbol,
                order.side,
                bf.quantity,
                bf.price,
                source_fill_id=bf.source_fill_id,
                filled_at=bf.filled_at,
                session_id=order.session_id,
            )
        except _FILL_ERRORS as exc:
            _log.warning(
                "broker fill rejected for order %s (%s): %s",
                order.id,
                order.symbol,
                exc,
            )
            rejected.append(
                {
                    "source_fill_id": bf.source_fill_id,
                    "quantity": bf.quantity,
                    "price": bf.price,
                    "error": str(exc),
                }
            )

    recorded = sum(f.quantity for f in await store.list_fills(order_id=order.id))
    if update.filled_quantity > recorded:
        # Broker executed more than we could record — a durable, unrecordable
        # divergence (AIR-002). Escalate and hold the order non-terminal so the
        # untracked position is never buried under a terminal state.
        _log.error(
            "order %s: broker reports filled=%s but only %s recorded; escalating "
            "to a needs_review reconciliation record.",
            order.id,
            update.filled_quantity,
            recorded,
        )
        await _escalate_fill_divergence(store, order, update, recorded, rejected)
        target = _divergence_safe_status(order, recorded)
    else:
        if update.filled_quantity != recorded:
            # recorded > broker (should not happen for a monotonic broker feed);
            # trust the recorded fills, which are the position's source of truth.
            _log.warning(
                "order %s: recorded fills (%s) exceed broker filled (%s); "
                "reconciling to recorded.",
                order.id,
                recorded,
                update.filled_quantity,
            )
        target = _reconciled_status(order, update.status, recorded)
    try:
        await store.transition_order(
            order.id, target, filled_quantity=recorded
        )
    except _TRANSITION_ERRORS as exc:
        _log.warning(
            "order %s reconcile to %s (recorded filled=%s) rejected: %s",
            order.id,
            target,
            recorded,
            exc,
        )


async def _escalate_fill_divergence(
    store: StateStore,
    order: Order,
    update: BrokerOrderUpdate,
    recorded: int,
    rejected: list[dict[str, Any]],
) -> None:
    """Durably record a broker>local fill divergence as a ``needs_review``
    reconciliation record (AIR-002). Deduped per order: an order already carrying
    an open recovery record is not re-recorded on every subsequent diverging tick.
    """

    try:
        open_recoveries = await store.list_submit_recoveries(
            statuses=RECOVERY_OPEN_STATUSES
        )
        if any(r.local_order_id == order.id for r in open_recoveries):
            return
        await store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=order.broker_order_id or "",
            client_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason=(
                f"broker/local fill divergence: broker reports filled="
                f"{update.filled_quantity} ({update.status.value}) but only "
                f"{recorded} shares recorded locally — a real untracked position"
            ),
            session_id=order.session_id,
            candidate_id=order.candidate_id,
            cleanup_status=RECOVERY_NEEDS_REVIEW,
            event_type=EventType.FILL_RECONCILIATION_NEEDED.value,
            extra_payload={
                "broker_status": update.status.value,
                "broker_filled_quantity": update.filled_quantity,
                "recorded_filled_quantity": recorded,
                "rejected_fills": rejected,
            },
        )
    except Exception:  # noqa: BLE001 - escalation is best-effort; retried next tick
        # Per-order isolation on a failure path: a store error here must not abort
        # reconciliation of the other open orders in this tick (matches
        # _handle_unpersisted_submit). The divergence re-escalates next cadence.
        _log.exception(
            "could not escalate fill divergence for order %s to needs_review",
            order.id,
        )


def _divergence_safe_status(order: Order, recorded: int) -> OrderStatus:
    """A NON-terminal status to hold a fill-diverged order in, so the untracked
    position stays visible and polled and is never buried under a terminal
    CANCELED/FILLED. A ``cancel_pending`` order keeps winding down (CHAOS-1);
    otherwise it reflects the recorded fills without ever finalizing."""

    if order.status is OrderStatus.CANCEL_PENDING:
        return OrderStatus.CANCEL_PENDING
    if recorded > 0:
        return OrderStatus.PARTIALLY_FILLED
    return OrderStatus.SUBMITTED


def _reconciled_status(
    order: Order, broker_status: OrderStatus, recorded: int
) -> OrderStatus:
    """The order status implied by the fills we have actually recorded.

    Never claims FILLED without the recorded fills to back it; honours a broker
    cancel/reject as terminal when the order isn't already fully recorded as
    filled. (A buy that the broker reports CANCELED after the full quantity has
    actually filled is treated as FILLED — the recorded fills are the truth.)

    An order already in ``cancel_pending`` (or one the broker now reports as
    ``pending_cancel``) stays ``cancel_pending`` until the broker confirms a
    terminal state — a late partial fill must not revert it to an open status
    (CHAOS-1).
    """

    if recorded >= order.quantity:
        return OrderStatus.FILLED
    if broker_status in (OrderStatus.CANCELED, OrderStatus.REJECTED):
        return broker_status
    if (
        broker_status is OrderStatus.CANCEL_PENDING
        or order.status is OrderStatus.CANCEL_PENDING
    ):
        return OrderStatus.CANCEL_PENDING
    if recorded > 0:
        return OrderStatus.PARTIALLY_FILLED
    return OrderStatus.SUBMITTED


def _order_age(now: datetime, created_at: datetime):
    """``now - created_at``, tolerant of a tz-naive ``created_at`` (treated as
    UTC).

    Every timestamp the stores write is tz-aware, but a hand-inserted or legacy
    row could be naive; without this guard the subtraction would raise
    ``TypeError`` and abort the entire reconcile tick for every order.
    """

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return now - created_at


async def _run_reconciliation(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Settings,
    *,
    budget: Optional[ReconcileQueryBudget] = None,
) -> Optional[ReconciliationPlan]:
    """Wave 4e: the ACTING §7 mass-report reconcile. Computes the reconciliation
    plan from the venue's mass reports and acts on it:

    * surface external/unmanaged venue orders (4e-2, non-mutating);
    * resolve open orders confirmed-absent at the venue → terminal (4e-3, the
      oversell-critical targeted-query-before-reject path);
    * apply reconciliation-inferred synthetic fills (4e-4, dedup-safe — INV-5/R8).

    (Position parity surfacing is a deferred post-4e follow-up — an audit-only
    safeguard that never flips truth.)

    Load-bearing properties:

    * **Failure-isolated.** A failed mass report RAISES (§7: a query failure is never
      read as "flat"/"no open orders"). Caught here, logged, and the whole reconcile
      is skipped this cycle — the legacy per-order reconcile that already ran is
      untouched, and no partial/failed report is ever treated as authoritative.
    * **Query-budgeted (E6/E7).** When a persistent ``budget`` is supplied (the loop
      owns one), the two mass-report calls are consumed up front; if the budget can't
      cover them the whole cycle is SKIPPED — never a partial read, and a skipped
      report is never read as flat. Direct callers pass no budget (unthrottled).
    * **Gated + naturally inert.** ``reconciliation_enabled`` (default on) guards it;
      external orders + inferred fills come from the broker report, so an empty report
      (the corpus default) yields none — the reconcile runs but changes nothing.

    Returns the plan for observability/tests; the tick ignores the return value.
    """

    if not settings.reconciliation_enabled:
        return None

    now = utcnow()
    # The two mass-report REST calls this cycle. Skip the whole cycle (never a
    # partial read) if the budget can't cover them — a skipped report is NOT flat.
    if budget is not None and not budget.try_consume(now, 2):
        _log.debug("reconciliation skipped this cycle: query budget exhausted")
        return None

    try:
        broker_orders = await adapter.list_open_orders()
        broker_positions = await adapter.list_positions()
        local_open = [
            o for o in await store.list_orders() if o.status in _OPEN_STATUSES
        ]
        local_positions = await store.list_positions()
        plan = plan_reconciliation(
            local_open_orders=local_open,
            local_positions=local_positions,
            broker_orders=broker_orders,
            broker_positions=broker_positions,
            now=now,
            recent_threshold_ms=settings.reconcile_recent_threshold_ms,
            avg_price_tolerance=settings.reconcile_avg_price_tolerance,
        )
        await _surface_external_orders(store, plan)
        await _resolve_reconcile_not_found(
            store, adapter, settings, plan.needs_targeted_query, budget=budget
        )
        await _apply_inferred_fills(store, plan)
        return plan
    except Exception as exc:  # noqa: BLE001 - reconcile is non-fatal; a failure never flips truth
        _log.warning("reconciliation skipped this cycle (non-fatal): %s", exc)
        return None


async def _apply_inferred_fills(
    store: StateStore, plan: ReconciliationPlan
) -> None:
    """Append each reconciliation-inferred fill as a SYNTHETIC/RECONCILIATION fill
    (wave 4e-4). The engine only infers a fill from a PRICED execution in the mass
    report (never a $0 synthetic), and ``source_fill_id`` is the execution's OWN
    venue id — so a synthetic fill and the eventual real observation of the same
    execution dedup to ONE (INV-5 / R8), never a double-count. Best-effort: a fill
    the store rejects is logged, never crashes the tick."""

    for f in plan.inferred_fills:
        try:
            await store.append_fill(
                f.order_id,
                f.symbol,
                f.side,
                f.quantity,
                f.price,
                source_fill_id=f.source_fill_id,
                source=EventSource.RECONCILIATION,
                authority=EventAuthority.SYNTHETIC,
            )
        except _FILL_ERRORS as exc:
            _log.warning(
                "reconcile: inferred fill for order %s (%s) rejected: %s",
                f.order_id, f.symbol, exc,
            )


async def _surface_external_orders(
    store: StateStore, plan: ReconciliationPlan
) -> None:
    """Surface each external/unmanaged venue order as a durable, deduped
    ``reconcile_external_order`` audit record (§7: surfaced, NEVER silently
    absorbed into managed state or folded into position). Deduped by
    ``broker_order_id`` — one record per external order, ever (survives restart via
    the persisted event log). Non-mutating: only an audit record is written."""

    if not plan.external_orders:
        return

    seen = {
        (e.payload or {}).get("broker_order_id")
        for e in await store.list_events(
            event_type=EventType.RECONCILE_EXTERNAL_ORDER.value
        )
    }
    for x in plan.external_orders:
        if x.broker_order_id in seen:
            continue
        await store.append_event(
            EventType.RECONCILE_EXTERNAL_ORDER.value,
            message=(
                f"external/unmanaged venue order {x.broker_order_id} "
                f"({x.symbol} {x.side.value} {x.status.value}, "
                f"filled={x.filled_quantity}) — surfaced for review, not absorbed"
            ),
            symbol=x.symbol,
            payload={
                "broker_order_id": x.broker_order_id,
                "client_order_id": x.client_order_id,
                "symbol": x.symbol,
                "side": x.side.value,
                "status": x.status.value,
                "filled_quantity": x.filled_quantity,
            },
        )
        seen.add(x.broker_order_id)


# An open order the reconcile may resolve to a terminal when the venue confirms it
# ABSENT. CANCEL_PENDING is excluded (§7 / R4): it is already being wound down and
# the per-order poll (which holds its broker id) owns its resolution — the mass
# report never drives it to a terminal.
_RECONCILE_RESOLVABLE = frozenset(
    {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}
)
_RECONCILE_DEFERRED_EVENT = EventType.ORDER_RECONCILE_DEFERRED.value


async def _resolve_reconcile_not_found(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Settings,
    order_ids: list[str],
    *,
    budget: Optional[ReconcileQueryBudget] = None,
) -> None:
    """Resolve open orders ABSENT from the venue's mass report — the oversell-critical
    §7 path (wave 4e-3). A mass-report absence is NEVER a reject on its own; each
    order gets a READ-ONLY targeted ``client_order_id`` query first, and only a
    venue-CONFIRMED absence, sustained past ``open_check_missing_retries``, resolves
    to a terminal:

    * venue HAS it (working/filled/terminal) → NOT actually absent (the mass report
      was incomplete). Leave it to the per-order poll, which holds its broker id and
      ingests fills — take no action here (never a bare terminal flip that could drop
      a fill; INV-9).
    * venue CONFIRMS absent (``None``) → after ``open_check_missing_retries``
      confirmations (a single not-found could be venue lag, §7): ``SUBMITTED →
      REJECTED`` / ``PARTIALLY_FILLED → CANCELED`` (fills preserved). Before the
      bound → record a not-found deferral and retry next tick.
    * query FAILS (``BrokerError``) → inconclusive; NEVER read as absent (§7 — that is
      an oversell path). Retry; past the same bound surface a ``needs_review``
      deferral (a distinct counter — a run of failures can't erode the not-found
      tolerance).

    Best-effort per order — a store/broker error on one never stops the loop.
    """

    if not order_ids:
        return
    retries = settings.reconcile_open_check_missing_retries
    for order_id in order_ids:
        order = await store.get_order(order_id)
        if order is None or order.status not in _RECONCILE_RESOLVABLE:
            # Left CANCEL_PENDING / already terminal / vanished — nothing to resolve.
            continue
        # Each targeted query is one REST call against the §7/§9 budget (E6). When
        # exhausted, STOP querying this cycle and defer the rest to the next tick —
        # an un-queried order is NEVER resolved (never read as absent, §7).
        if budget is not None and not budget.try_consume(utcnow()):
            _log.debug("reconcile: query budget exhausted; deferring remaining not-found")
            return
        try:
            update = await adapter.get_order_by_client_order_id(order_id)
        except BrokerError as exc:
            # A query FAILURE is inconclusive — NEVER read as absent (§7). Retry;
            # surface needs_review once persistently stuck (bounded so a venue outage
            # doesn't grow the log forever). Counts ONLY query_error, independent of
            # the not-found bound.
            errors = await _order_deferral_count(
                store, order_id, "query_error", event_type=_RECONCILE_DEFERRED_EVENT
            )
            if errors < retries:
                await _record_reconcile_deferral(
                    store, order, errors + 1, "query_error",
                    needs_review=errors + 1 >= retries, error=str(exc),
                )
            continue

        if update is not None:
            # The venue HAS the order — it was not absent, only missing from this
            # mass report. The per-order poll (holds the broker id) owns its status +
            # fills; do NOT flip it here.
            continue

        # Confirmed absent. Only a CONFIRMED not-found advances this bound (query
        # errors use a SEPARATE counter), so the venue-lag tolerance is exactly
        # ``retries`` confirmations — a run of query errors can never erode it and
        # prematurely resolve a possibly-live order.
        attempts = (
            await _order_deferral_count(
                store, order_id, "not_found", event_type=_RECONCILE_DEFERRED_EVENT
            )
            + 1
        )
        if attempts >= retries:
            target = (
                OrderStatus.REJECTED
                if order.status is OrderStatus.SUBMITTED
                else OrderStatus.CANCELED  # PARTIALLY_FILLED → CANCELED (fills kept)
            )
            try:
                await store.reconcile_resolve_order(
                    order_id, target, reason="not_found_at_venue"
                )
                _log.info(
                    "reconcile: order %s confirmed absent after %s queries -> %s",
                    order_id, attempts, target.value,
                )
            except _TRANSITION_ERRORS as exc:
                _log.warning(
                    "reconcile: could not resolve absent order %s to %s: %s",
                    order_id, target.value, exc,
                )
        else:
            await _record_reconcile_deferral(store, order, attempts, "not_found")


async def _record_reconcile_deferral(
    store: StateStore,
    order: Order,
    attempt: int,
    reason: str,
    *,
    needs_review: bool = False,
    error: Optional[str] = None,
) -> None:
    """Durably record one reconcile targeted-query deferral so the bound counts
    across ticks and restarts (§7). ``needs_review`` marks a persistently-stuck
    order. Best-effort (never crashes the tick)."""

    payload: dict[str, object] = {"attempt": attempt, "reason": reason}
    if needs_review:
        payload["needs_review"] = True
    if error is not None:
        payload["error"] = error
    try:
        await store.append_event(
            _RECONCILE_DEFERRED_EVENT,
            message=(
                f"reconcile not-found resolution deferred for {order.symbol} "
                f"({reason}, attempt {attempt})"
                + (" — NEEDS REVIEW" if needs_review else "")
            ),
            symbol=order.symbol,
            candidate_id=order.candidate_id,
            order_id=order.id,
            payload=payload,
            session_id=order.session_id,
        )
    except Exception:  # noqa: BLE001 - audit is best-effort on a resolution path
        _log.exception(
            "could not record reconcile deferral for order %s", order.id
        )


async def _orders_with_event(store: StateStore, event_type: str) -> set[str]:
    """Order ids that already carry an event of ``event_type``.

    Reads the persisted event log so "do this once per order" guarantees (flag
    stale once; audit a held submission once) survive a process restart.
    Acceptable at beta's single-user scale; an indexed query is the upgrade if
    the event log ever grows large.
    """

    return {
        e.order_id
        for e in await store.list_events()
        if e.event_type == event_type and e.order_id is not None
    }
