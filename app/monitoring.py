"""Background monitoring loop — Phase 4 order submission + reconciliation.

A single asyncio task, started at app startup (see ``app/main.py``), that on a
fixed cadence (D-011: REST polling, not websocket):

1. **Submits** claim-eligible orders projected at ``OrderStatus.CREATED`` (including
   a claim released after a definite transient failure), and
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
    VenueOrderScope,
)
from app.config import Settings
from app.events.projectors import reconcile_trading_state
from app.features import session_type_for
from app.marketdata.service import MarketDataService, MarketSnapshot
from app.models import (
    ACCEPTED_SUBMIT_UNPERSISTED_REASON,
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    RECOVERY_RESOLVED,
    RECOVERY_UNRESOLVED,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    EventType,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    SessionStatus,
    SessionType,
    SubmitRecoveryRecord,
    TradingState,
    utcnow,
)
from app.policy import canonical_accepted_submit_broker_id, finite_number_reason
from app.position import NegativePositionError
from app.protection import (
    FloorBreach,
    ProtectionConfig,
    floor_breach_reason,
    protective_limit_price,
)
from app.reconciliation import (
    ENVELOPE_EXEC_BLOCKED,
    ENVELOPE_EXEC_RELEASED,
    ReconcileFairnessCursor,
    ReconciliationPlan,
    ReconcileQueryBudget,
    VenueScopeOwner,
    accepted_broker_identity_is_durably_tracked,
    accepted_broker_identity_is_tracked,
    await_accepted_submit_finalizer,
    current_venue_order_scope,
    execute_envelope_action,
    get_or_record_venue_order_scope,
    load_venue_order_scopes,
    market_snapshot_fingerprint,
    order_has_dynamic_venue_type,
    plan_reconciliation,
    quarantine_or_own_ambiguous_submit as _quarantine_or_own_ambiguous_submit,
    record_accepted_submit_uncertainty as _record_accepted_submit_uncertainty,
    redrive_staged_envelope_action,
    rendered_order_from_scope,
    venue_scope_matches_order,
)
from app.sellside.policy import decide
from app.sellside.types import (
    BreachSignal,
    ExhaustedSignal,
    ExpiredSignal,
    PlannedAction,
    StaleDataSignal,
)
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    InvalidFillError,
    InvalidOrderError,
    OrderTransitionError,
    ProtectionHaltedError,
    RecoveryTransitionError,
    RiskLimits,
    StateStore,
    UnknownEntityError,
)
from app.store.core import (
    OPEN_BUY_STATUSES,
    EnvelopeActionPausedError,
    EnvelopeObligationProjection,
    claim_occurrence_at,
    project_envelope_obligation,
    recovery_terminal_fact_matches,
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
_STALEABLE_STATUSES = frozenset({OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED})

# WO-0124 / D-0124: disposition cancels are exact-child, durable attempts. The
# event is written before venue IO and is the only retry counter, so restart and
# store implementations cannot disagree. Three persisted direct attempts
# exhaust automatic authority; the tracked order is then latched needs_review.
_DISPOSITION_CANCEL_RETRY_LIMIT = 3
_EXPIRY_DISPOSITION_CANCEL = "expiry_cancel_and_return"
_STALE_DATA_DISPOSITION_CANCEL = "stale_data_cancel"
_DISPOSITION_CANCEL_REQUEST_ACTION = "cancel_request"
_DISPOSITION_CANCEL_KINDS = frozenset(
    {_EXPIRY_DISPOSITION_CANCEL, _STALE_DATA_DISPOSITION_CANCEL}
)

# Cadence repair work is page-bounded. A poison fact blocks only its current
# page while every fully inspected earlier page retains a durable high-water.
_EXECUTION_REPAIR_BATCH_SIZE = 256
_REPAIR_CHECKPOINT_TYPES = frozenset(
    {
        ExecutionEventType.ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT,
        ExecutionEventType.SUBMIT_ACCEPTANCE_REPAIR_CHECKPOINT,
    }
)

# Fill-append failures that are recoverable per-order (logged, then skipped).
_FILL_ERRORS = (InvalidFillError, UnknownEntityError, NegativePositionError)
# Order-transition failures that are recoverable per-order.
_TRANSITION_ERRORS = (OrderTransitionError, InvalidOrderError, UnknownEntityError)


class _ReconcileGateEstablishmentError(RuntimeError):
    """The reconcile driver did not durably enter its required safe state."""


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


def _capi_risk_limits(settings: Optional[Settings]) -> RiskLimits:
    """CAPI configuration used again at the final BUY submission claim."""

    if settings is None:
        return RiskLimits()
    return RiskLimits(
        max_shares_per_order=settings.capi_max_shares_per_order,
        max_notional_per_order=settings.capi_max_notional_per_order,
        max_total_exposure=settings.capi_max_total_exposure,
        allowlist=settings.capi_trading_allowlist,
    )


async def _effective_submit_order(
    order: Order,
    market_data: Optional[MarketDataService],
    settings: Optional[Settings],
    *,
    submission_session: Optional[SessionType] = None,
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
    active_session = submission_session or session_type_for(utcnow())
    if active_session is SessionType.REGULAR:
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


async def _prepare_managed_venue_order(
    store: StateStore,
    order: Order,
    market_data: Optional[MarketDataService],
    settings: Optional[Settings],
) -> Optional[tuple[Order, VenueOrderScope]]:
    """Replay or durably write the exact request before a submit venue call."""

    existing = current_venue_order_scope(
        await store.get_order_execution_events(order.id), order.id
    )
    if existing is not None:
        return rendered_order_from_scope(order, existing), existing

    submission_session = session_type_for(utcnow())
    effective = await _effective_submit_order(
        order,
        market_data,
        settings,
        submission_session=submission_session,
    )
    if effective is None:
        return None
    extended_hours = OrderType(
        effective.order_type
    ) is OrderType.LIMIT and submission_session in {
        SessionType.PRE_MARKET,
        SessionType.AFTER_HOURS,
    }
    scope = await get_or_record_venue_order_scope(
        store,
        order=order,
        rendered_order=effective,
        extended_hours=extended_hours,
    )
    return rendered_order_from_scope(order, scope), scope


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
    if finite_number_reason(last_price) is not None:
        return None
    # finite_number_reason rejects None (and every non-finite value) above, so
    # last_price is a real, finite float here — the <= 0 guard can't see None.
    assert last_price is not None
    if last_price <= 0:
        return None
    return last_price


# --------------------------------------------------------------------------- #
# Sell-Side Protection (Phase 7 §5) — the autonomous breach -> exit driver.
# --------------------------------------------------------------------------- #

# Non-terminal BUY statuses a protective exit must clear so it truly reaches flat
# (§5.3). SUBMITTING (mid-claim, no broker id yet) and CANCEL_PENDING (already
# winding down) are left for the normal pipeline; everything else is terminal.
# The open-BUY set cancel_open_buys acts on IS the set the store's flatten
# decision detects (WO-0036 R2 Option B): one shared definition
# (app.store.core.OPEN_BUY_STATUSES) so the store's FLATTEN_BUYS_OPEN signal and
# this cancel step can never name different orders — the retry always converges.
_CANCELLABLE_BUY_STATUSES = OPEN_BUY_STATUSES


async def cancel_open_buys(
    store: StateStore, adapter: BrokerAdapter, symbol: str
) -> None:
    """Cancel every open BUY for ``symbol`` before a protective exit (§5.3).

    Position derives only from *filled* shares, so an open unfilled BUY is
    invisible to the exit size — leaving one live would let a BUY fill and a
    protective SELL execute at the same time (a self-cross), or re-grow the very
    position being exited. A projected ``CREATED`` buy is canceled locally only
    when the store proves no broker id or open recovery owner; a live
    ``SUBMITTED``/``PARTIALLY_FILLED`` buy is canceled at the broker and moved to
    ``CANCEL_PENDING`` (a late fill still reconciles). Idempotent and audited via
    the store's transitions; shared with the flatten route."""

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
                # The snapshot can race the submission claim. Cancel locally
                # only if the current row is STILL CREATED under the store lock;
                # otherwise continue with the current venue-aware state below.
                order = await store.transition_order(
                    order.id,
                    OrderStatus.CANCELED,
                    expected_from=OrderStatus.CREATED,
                )
            if (
                order.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)
                and order.broker_order_id is not None
            ):
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
    paused_breaching: set[str] = set()

    for position in positions:
        try:
            snapshot = await market_data.get_snapshot(position.symbol)
            breach = floor_breach_reason(position, snapshot, config)
            if breach is None:
                continue
            # ENG-001: re-read the §8 FSM FRESH per symbol (not once before the
            # loop). Only HALTED (the kill-switch state, which dominates pause)
            # pauses autonomous protection per D-P2; REDUCING (buys-paused) does
            # not. A kill that landed during an earlier await must pause THIS symbol
            # here — not be decided on a stale read — and skipping now also avoids a
            # needless buy-cancel under the kill.
            session = await store.get_current_session()
            if session.trading_state is TradingState.HALTED:
                # D-P2: record the symbol as paused-and-breaching; the
                # paused/resumed transition is reconciled after the loop. Manual
                # flatten still works (routes).
                paused_breaching.add(position.symbol)
                continue
            # Atomic backstop (ENG-001): a kill landing DURING _open_protective_exit's
            # own awaits makes the store refuse the new PROTECTION_FLOOR intent —
            # that pauses the symbol too, and nothing spurious is created.
            if await _open_protective_exit(
                store, adapter, position, breach, session.id
            ):
                paused_breaching.add(position.symbol)
        except Exception:  # noqa: BLE001 - one symbol must not block the others
            _log.exception("protection tick failed for %s", position.symbol)

    await _reconcile_protection_pause(store, paused_breaching)


async def _open_protective_exit(
    store: StateStore,
    adapter: BrokerAdapter,
    position: Position,
    breach: FloorBreach,
    session_id: str,
) -> bool:
    """Open one protective exit for a breaching symbol: cancel open buys, then open
    the whole exit — single-flight ``PROTECTION_FLOOR`` intent, auto-approve,
    dispatch a MARKET order (type re-derived at submission — §5.4), and audit
    ``protection_triggered`` — via the ONE store-atomic ``open_protection_exit``
    call (ENG-001 / REV-0019-F-001), never the separate public steps. Idempotent:
    an already-active exit for the symbol short-circuits inside the store.

    Returns ``True`` iff the kill switch (Halted) engaged before the atomic
    exit-open and the store refused the new PROTECTION_FLOOR exit (ENG-001) — the
    caller then records the symbol as paused. Because the create+approve+dispatch+
    audit is one atomic unit with no await after the HALTED check, a concurrent
    kill can never leave a partial exit under Halted. Returns ``False`` otherwise
    (exit opened, or already in flight, or nothing to size)."""

    # Dedup: an exit is already in flight for this symbol (single-flight also
    # enforces this atomically in the store, but skipping here avoids re-cancelling
    # buys and re-auditing every tick while the first exit works).
    if await store.active_sell_intent_for(position.symbol) is not None:
        return False

    # §5.3: clear open buys FIRST so the exit reaches — and stays — flat.
    await cancel_open_buys(store, adapter, position.symbol)

    # Re-read the live position after cancelling buys (a partial buy fill may have
    # landed); never size an exit above what is actually held (Rule 7 / no short).
    live = await store.get_position(position.symbol)
    if live.quantity <= 0:
        return False

    try:
        # ONE store-atomic operation: create + approve + dispatch + audit under a
        # single lock hold with the HALTED check (ENG-001 / REV-0019-F-001). The
        # decomposed public sequence used here before left a post-create window in
        # which a concurrent kill could strand an ORDERED intent + CREATED order +
        # protection_triggered event under Halted; folding it removes every await
        # between the check and the writes.
        await store.open_protection_exit(
            symbol=position.symbol,
            target_quantity=live.quantity,
            floor_price=breach.floor_price,
            observed_price=breach.observed_price,
            average_price=breach.average_price,
            session_id=session_id,
        )
    except ProtectionHaltedError:
        # A kill landed before the atomic exit-open ran; the store refused it under
        # the single lock — nothing was created. Pause the symbol.
        return True
    return False


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


class EnvelopeTapeBuffer:
    """Per-symbol session snapshot tape for the pure sell-side policy.

    WORKING DATA, not persisted (the same ruling as ``MarketSnapshot`` itself,
    docs/02): a restart empties it and the policy simply re-warms
    (INSUFFICIENT_DATA → conservative no-action for the warmup window) —
    fail-quiet, never fail-open. Appends dedupe on ``updated_at`` so a quiet
    feed doesn't stutter duplicate ticks into the bars; bounded so a
    long-lived session cannot grow memory without limit.
    """

    def __init__(self, max_len: int = 4096) -> None:
        self._tapes: dict[str, list[MarketSnapshot]] = {}
        self._max = max_len

    def append(self, snapshot: MarketSnapshot) -> None:
        tape = self._tapes.setdefault(snapshot.symbol, [])
        if tape and tape[-1].updated_at == snapshot.updated_at:
            tape[-1] = snapshot  # same tick refreshed, not a new observation
            return
        tape.append(snapshot)
        if len(tape) > self._max:
            del tape[: len(tape) - self._max]

    def tape(self, symbol: str) -> list[MarketSnapshot]:
        return list(self._tapes.get(symbol, ()))


async def _validated_envelope_lineage(
    store: StateStore,
    envelope_id: str,
    *,
    events: Optional[list[ExecutionEvent]] = None,
) -> Optional[tuple[ExecutionEnvelope, EnvelopeObligationProjection, dict[str, Order]]]:
    """Load one Envelope lineage through the shared bounded projection."""

    envelope = await store.get_envelope(envelope_id)
    if envelope is None:
        return None
    all_events = events if events is not None else await store.get_execution_events()
    owner_intent_id = envelope.sell_intent_id
    all_actions = [
        event
        for event in all_events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
    ]
    # REV-0029 P1-1: discover actions through the store's OWNER-SCOPED identity
    # universe, not an exact-``envelope_id`` subset. The store's gates select an
    # action by parent envelope OR owner correlation OR referenced-order owner
    # (``app/store/memory.py`` ``action_in_scope``; the ``sqlite`` twin), so a
    # malformed action whose parent is wrong/missing but which still claims this
    # envelope's intent — via ``correlation_id`` or its order's ``sell_intent_id``
    # — is quarantined by the store. Keying monitoring only on exact envelope_id
    # let that action project clean-empty here, losing the R6 malformed-lineage
    # diagnostic and silently declining to fail the cancel closed. The symbol key
    # the store adds for SYMBOL-scoped gates is deliberately NOT used to select
    # cancel targets: symbol alone never establishes child ownership. Cancellation
    # separately consumes a diagnostic-only symbol projection so store-quarantined
    # corruption cannot disappear silently. Owners are resolved for every order
    # any action references (bounded by action count, beta scale), so the
    # referenced-order-owner key resolves exactly as the gates see it.
    action_order_ids = {
        event.order_id for event in all_actions if event.order_id is not None
    }
    all_action_orders: dict[str, Order] = {}
    for order_id in action_order_ids:
        order = await store.get_order(order_id)
        if order is not None:
            all_action_orders[order_id] = order
    parent_order_ids = {
        event.order_id
        for event in all_actions
        if event.envelope_id == envelope_id and event.order_id is not None
    }
    # PR#9 Codex Finding 1: the owner-scoped discovery below reaches a MALFORMED
    # action — one whose parent linkage is broken/missing yet still claims this
    # envelope's intent (correlation_id or referenced-order owner) — so the store-
    # quarantined R6 corruption is not lost by monitoring's exact-envelope_id scan.
    # It must NOT reach a WELL-FORMED sibling's action: one parented by another
    # KNOWN envelope (e.g. a superseded predecessor that shares this sell_intent_id).
    # That action is the sibling's own obligation. Pulling it into this single-
    # envelope projection (``envelopes=[envelope]`` below) flags the sibling as a
    # "missing envelope" — it is not in that one-element set — and ``_envelope_id_
    # for_order`` then disowns THIS envelope's real order, silently skipping its
    # fills. The sibling's own lineage validation still audits its action under the
    # correct parent, so no corruption escapes.
    known_envelopes = await store.list_envelopes()
    known_sibling_ids = {item.id for item in known_envelopes if item.id != envelope_id}

    def _owner_scoped(event: ExecutionEvent) -> bool:
        if event.envelope_id == envelope_id:  # parent envelope
            return True
        if event.envelope_id in known_sibling_ids:
            return (
                False  # a well-formed sibling's action — audited under its own parent
            )
        if owner_intent_id is not None and event.correlation_id == owner_intent_id:
            return True  # owner correlation (parent broken/missing)
        referenced = (
            all_action_orders.get(event.order_id)
            if event.order_id is not None
            else None
        )
        if (
            owner_intent_id is not None
            and referenced is not None
            and referenced.sell_intent_id == owner_intent_id
        ):
            return True  # referenced-order owner (parent broken/missing)
        if event.order_id is not None and event.order_id in parent_order_ids:
            return True  # co-order of a parent action (multi-action-per-order)
        return False

    actions = [event for event in all_actions if _owner_scoped(event)]
    order_ids = {event.order_id for event in actions if event.order_id is not None}
    orders: dict[str, Order] = {
        order_id: order
        for order_id, order in all_action_orders.items()
        if order_id in order_ids
    }
    recoveries = await store.list_submit_recoveries(statuses=RECOVERY_OPEN_STATUSES)
    projection = project_envelope_obligation(
        envelopes=[envelope],
        action_events=actions,
        orders_by_id=orders,
        order_events=[
            event
            for event in all_events
            if event.order_id in order_ids
            and event.event_type is not ExecutionEventType.ENVELOPE_ACTION
        ],
        open_recovery_order_ids=frozenset(
            record.local_order_id
            for record in recoveries
            if record.cleanup_status == RECOVERY_UNRESOLVED
        ),
        needs_review_order_ids=frozenset(
            record.local_order_id
            for record in recoveries
            if record.cleanup_status == RECOVERY_NEEDS_REVIEW
        ),
        known_envelopes_by_id={item.id: item for item in known_envelopes},
    )
    return envelope, projection, orders


async def _envelope_working_order(
    store: StateStore, envelope_id: str
) -> Optional[Order]:
    """The envelope's latest non-terminal order, discovered from its
    ENVELOPE_ACTION events (the event log IS the envelope→order linkage)."""

    loaded = await _validated_envelope_lineage(store, envelope_id)
    if loaded is None:
        return None
    _, projection, orders = loaded
    if (
        projection.missing_envelope_ids
        or projection.missing_order_ids
        or projection.invalid_order_ids
        or projection.recovery_order_ids
        or projection.uncertain_claim_order_ids
    ):
        return None
    if len(projection.venue_orders) == 1:
        return projection.venue_orders[0]
    if projection.venue_orders:
        return None
    local = [
        orders[order_id]
        for order_id in projection.unresolved_order_ids
        if order_id in orders and orders[order_id].status is OrderStatus.CREATED
    ]
    return local[0] if len(local) == 1 else None


async def _envelope_id_for_order(store: StateStore, order_id: str) -> Optional[str]:
    """The envelope that minted ``order_id`` (via its ENVELOPE_ACTION event),
    or None for every non-envelope order."""

    events = await store.get_execution_events()
    actions = [
        event
        for event in events
        if event.order_id == order_id
        and event.event_type is ExecutionEventType.ENVELOPE_ACTION
    ]
    parent_ids = {event.envelope_id for event in actions}
    if not actions or None in parent_ids or len(parent_ids) != 1:
        return None
    envelope_id = next(iter(parent_ids))
    assert envelope_id is not None
    loaded = await _validated_envelope_lineage(store, envelope_id, events=events)
    if loaded is None:
        return None
    _, projection, _ = loaded
    if (
        order_id in projection.invalid_order_ids
        or order_id in projection.missing_order_ids
        or projection.missing_envelope_ids
    ):
        return None
    return envelope_id


async def _record_envelope_fill_for_parent(
    store: StateStore,
    *,
    envelope_id: str,
    order_id: str,
    quantity: int,
    dedupe_key: str,
    price: float,
    session_id: Optional[str],
    ts_event: Optional[datetime] = None,
    source: EventSource = EventSource.BROKER_REST,
    authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
    strict: bool = False,
) -> bool:
    """Apply one fill when lineage was already resolved for this batch."""

    try:
        await store.record_envelope_fill(
            envelope_id,
            quantity=quantity,
            dedupe_key=dedupe_key,
            price=price,
            order_id=order_id,
            session_id=session_id,
            ts_event=ts_event,
            source=source,
            authority=authority,
        )
        return True
    except Exception:  # noqa: BLE001 - canonical fill ingestion remains first truth
        _log.exception(
            "envelope fill bridge failed for order %s; fill ingest/repair continues",
            order_id,
        )
        if strict:
            raise
        return False


def _repair_checkpoint_identity(
    repair_name: str, up_to_sequence: int, audit_cursor: int
) -> str:
    return f"repair-checkpoint:{repair_name}:{up_to_sequence}:{audit_cursor}"


def _repair_checkpoint_values(
    checkpoint: ExecutionEvent,
    *,
    checkpoint_type: ExecutionEventType,
    repair_name: str,
) -> tuple[int, int]:
    """Validate and decode one canonical execution-truth repair cursor."""

    payload = checkpoint.payload or {}
    up_to_sequence = payload.get("up_to_sequence")
    audit_cursor = payload.get("audit_cursor")
    valid_numbers = (
        isinstance(up_to_sequence, int)
        and not isinstance(up_to_sequence, bool)
        and up_to_sequence >= 0
        and isinstance(audit_cursor, int)
        and not isinstance(audit_cursor, bool)
        and audit_cursor >= 0
    )
    if not valid_numbers:
        raise RecoveryTransitionError(
            f"malformed {repair_name} checkpoint {checkpoint.id}"
        )
    assert isinstance(up_to_sequence, int)
    assert isinstance(audit_cursor, int)
    identity = _repair_checkpoint_identity(repair_name, up_to_sequence, audit_cursor)
    if not (
        checkpoint.event_type is checkpoint_type
        and checkpoint.source is EventSource.ENGINE
        and checkpoint.authority is EventAuthority.LOCAL
        and checkpoint.id == identity
        and checkpoint.dedupe_key == identity
        and checkpoint.order_id is None
        and checkpoint.envelope_id is None
        and payload.get("repair") == repair_name
        and up_to_sequence < checkpoint.sequence
    ):
        raise RecoveryTransitionError(
            f"malformed {repair_name} checkpoint {checkpoint.id}"
        )
    return up_to_sequence, audit_cursor


async def _execution_repair_cursor(
    store: StateStore,
    *,
    checkpoint_type: ExecutionEventType,
    repair_name: str,
) -> tuple[Optional[ExecutionEvent], int, int]:
    checkpoint = await store.get_latest_execution_event(checkpoint_type)
    if checkpoint is None:
        return None, 0, 0
    high_water, audit_cursor = _repair_checkpoint_values(
        checkpoint,
        checkpoint_type=checkpoint_type,
        repair_name=repair_name,
    )
    max_sequence = await store.get_max_execution_sequence()
    if high_water > max_sequence:
        raise RecoveryTransitionError(
            f"{repair_name} checkpoint {high_water} exceeds execution log "
            f"maximum {max_sequence}"
        )
    return checkpoint, high_water, audit_cursor


async def _execution_repair_tail(
    store: StateStore,
    *,
    checkpoint_type: ExecutionEventType,
    repair_name: str,
) -> tuple[Optional[ExecutionEvent], int, int, list[ExecutionEvent]]:
    """Read one bounded durable execution-log page for a repair consumer.

    Checkpoints are transport metadata, not repair work.  Skip complete pages
    containing only either consumer's checkpoint so a historical checkpoint
    chain cannot hide a later real fact; if the tail is checkpoint-only, report
    it as idle without appending another event.
    """

    checkpoint, high_water, audit_cursor = await _execution_repair_cursor(
        store,
        checkpoint_type=checkpoint_type,
        repair_name=repair_name,
    )
    scan_after = high_water
    while True:
        events = await store.get_execution_events(
            after_sequence=scan_after,
            limit=_EXECUTION_REPAIR_BATCH_SIZE,
        )
        if not events:
            return checkpoint, high_water, audit_cursor, []
        if any(event.event_type not in _REPAIR_CHECKPOINT_TYPES for event in events):
            return checkpoint, high_water, audit_cursor, events
        if len(events) < _EXECUTION_REPAIR_BATCH_SIZE:
            return checkpoint, high_water, audit_cursor, []
        scan_after = events[-1].sequence


async def _advance_execution_repair_checkpoint(
    store: StateStore,
    *,
    checkpoint_type: ExecutionEventType,
    repair_name: str,
    up_to_sequence: int,
    audit_cursor: int = 0,
    now: Optional[datetime] = None,
) -> ExecutionEvent:
    """Advance a repair cursor only after one complete selected page is clean."""

    identity = _repair_checkpoint_identity(repair_name, up_to_sequence, audit_cursor)
    stored = await store.append_execution_event(
        ExecutionEvent(
            id=identity,
            event_type=checkpoint_type,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=identity,
            ts_event=now,
            ts_init=now or utcnow(),
            payload={
                "repair": repair_name,
                "up_to_sequence": up_to_sequence,
                "audit_cursor": audit_cursor,
            },
        )
    )
    _repair_checkpoint_values(
        stored,
        checkpoint_type=checkpoint_type,
        repair_name=repair_name,
    )
    return stored


def _repair_page_needs_checkpoint(
    events: list[ExecutionEvent], checkpoint_type: ExecutionEventType
) -> bool:
    """Advance a non-empty page selected by the repair-tail loader.

    ``_execution_repair_tail`` guarantees a returned page contains real repair
    input rather than checkpoint-only transport metadata.  The type argument
    keeps each caller explicit about which durable cursor it owns.
    """

    _ = checkpoint_type
    return bool(events)


async def _repair_unattributed_envelope_fills(store: StateStore) -> None:
    """Validate/repair envelope fill attribution from a durable log tail.

    Terminal orders are no longer venue-polled, so an immutable envelope-less
    FILL with one action parent is a repair seed. Direct-attributed FILLs and
    attribution markers are replayed too so raw append-only corruption cannot
    hide outside the orphan-only path. The checkpoint advances only after the
    whole selected tail succeeds; a conflict is therefore retried after restart.
    """

    checkpoint_type = ExecutionEventType.ENVELOPE_ATTRIBUTION_REPAIR_CHECKPOINT
    while True:
        _checkpoint, _high_water, _audit_cursor, events = await _execution_repair_tail(
            store,
            checkpoint_type=checkpoint_type,
            repair_name="envelope_attribution",
        )
        if not events:
            return

        for event in events:
            if event.event_type in _REPAIR_CHECKPOINT_TYPES:
                continue
            canonical = event
            envelope_id = event.envelope_id
            repair_now = event.ts_init

            if event.event_type is ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED:
                fill_key = event.payload.get("fill_dedupe_key")
                if not isinstance(fill_key, str) or not fill_key or envelope_id is None:
                    raise InvalidFillError(
                        f"attribution marker {event.id} has no repairable fill identity"
                    )
                matched = await store.get_execution_event_by_dedupe_key(fill_key)
                if matched is None or matched.event_type is not ExecutionEventType.FILL:
                    raise InvalidFillError(
                        f"attribution marker {event.id} does not name one canonical FILL"
                    )
                canonical = matched
            elif event.event_type is not ExecutionEventType.FILL:
                continue

            if (
                canonical.dedupe_key is None
                or canonical.order_id is None
                or canonical.quantity is None
                or canonical.price is None
            ):
                if envelope_id is None:
                    # An ordinary/unscoped malformed FILL has no envelope ownership
                    # claim for this repair consumer to act on.
                    continue
                raise InvalidFillError(
                    f"direct-attributed FILL {canonical.id} is not repairable"
                )

            if envelope_id is None:
                actions = [
                    item
                    for item in await store.get_order_execution_events(
                        canonical.order_id
                    )
                    if item.event_type is ExecutionEventType.ENVELOPE_ACTION
                ]
                if not actions:
                    # Ordinary order fill, outside envelope accounting.
                    continue
                parent_ids = {item.envelope_id for item in actions}
                if None in parent_ids or len(parent_ids) != 1:
                    raise InvalidFillError(
                        f"fill {canonical.dedupe_key!r} has ambiguous envelope lineage"
                    )
                envelope_id = next(iter(parent_ids))
                assert envelope_id is not None

            try:
                await store.record_envelope_fill(
                    envelope_id,
                    quantity=canonical.quantity,
                    dedupe_key=canonical.dedupe_key,
                    price=canonical.price,
                    order_id=canonical.order_id,
                    session_id=canonical.session_id,
                    ts_event=canonical.ts_event,
                    source=canonical.source,
                    authority=canonical.authority,
                    now=repair_now,
                )
            except Exception:  # noqa: BLE001 - poison keeps cursor stationary
                _log.exception(
                    "invalid envelope attribution blocks cadence for fill %s",
                    canonical.dedupe_key,
                )
                raise

        if _repair_page_needs_checkpoint(events, checkpoint_type):
            await _advance_execution_repair_checkpoint(
                store,
                checkpoint_type=checkpoint_type,
                repair_name="envelope_attribution",
                up_to_sequence=events[-1].sequence,
                now=events[-1].ts_init,
            )
        if len(events) < _EXECUTION_REPAIR_BATCH_SIZE:
            return


async def _envelope_order_ids(store: StateStore) -> set[str]:
    """Every order id minted by an envelope action (an ENVELOPE_ACTION event
    carrying an order id). These orders are driven ONLY by the
    envelope executor's redrive (atomic replace + write-time re-validation);
    the generic submit sweep must never claim/submit them (Codex PR#8 #1)."""

    return {
        e.order_id
        for e in await store.get_execution_events()
        if e.event_type is ExecutionEventType.ENVELOPE_ACTION and e.order_id is not None
    }


def _disposition_cancel_events(
    events: list[ExecutionEvent], *, envelope_id: str, order_id: str
) -> list[ExecutionEvent]:
    """Durable cancel-attempt facts for one exact envelope child."""

    return [
        event
        for event in events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
        and event.envelope_id == envelope_id
        and event.order_id == order_id
        and event.payload.get("action") == "cancel"
    ]


_CancelTargetSnapshot = tuple[tuple[str, str], ...]


def _cancel_target_snapshot_for_orders(
    orders: list[Order],
) -> _CancelTargetSnapshot:
    """Canonical exact venue scope persisted before any cancel IO."""

    pairs = [
        (order.id, order.broker_order_id)
        for order in orders
        if order.broker_order_id is not None
    ]
    return tuple(sorted(pairs))


def _cancel_target_snapshot_from_event(
    event: ExecutionEvent,
) -> Optional[_CancelTargetSnapshot]:
    """Parse only the payload shape; projection owns authority validation."""

    raw = event.payload.get("target_snapshot")
    if not isinstance(raw, list) or not raw:
        return None
    parsed: list[tuple[str, str]] = []
    for item in raw:
        if (
            not isinstance(item, dict)
            or set(item) != {"order_id", "broker_order_id"}
            or not isinstance(item.get("order_id"), str)
            or not item["order_id"]
            or not isinstance(item.get("broker_order_id"), str)
            or not item["broker_order_id"]
        ):
            return None
        parsed.append((item["order_id"], item["broker_order_id"]))
    return tuple(parsed)


def _cancel_request_target_order_ids(
    event: ExecutionEvent,
) -> Optional[tuple[str, ...]]:
    """Parse the local-only scope held by a brokerless cancel request."""

    raw = event.payload.get("target_order_ids")
    if (
        not isinstance(raw, list)
        or not raw
        or any(not isinstance(order_id, str) or not order_id for order_id in raw)
    ):
        return None
    parsed = tuple(raw)
    if parsed != tuple(sorted(parsed)) or len(set(parsed)) != len(parsed):
        return None
    return parsed


def _cancel_target_snapshot_payload(
    snapshot: _CancelTargetSnapshot,
) -> list[dict[str, str]]:
    return [
        {"order_id": order_id, "broker_order_id": broker_order_id}
        for order_id, broker_order_id in snapshot
    ]


def _stored_cancel_attempt_matches(
    stored: ExecutionEvent, draft: ExecutionEvent
) -> bool:
    """A dedupe replay may authorize IO only when its immutable scope matches."""

    return all(
        (
            stored.event_type is draft.event_type,
            stored.source is draft.source,
            stored.authority is draft.authority,
            stored.dedupe_key == draft.dedupe_key,
            stored.ts_event == draft.ts_event,
            stored.symbol == draft.symbol,
            stored.side is draft.side,
            stored.quantity == draft.quantity,
            stored.price == draft.price,
            stored.order_id == draft.order_id,
            stored.envelope_id == draft.envelope_id,
            stored.session_id == draft.session_id,
            stored.correlation_id == draft.correlation_id,
            stored.payload == draft.payload,
        )
    )


async def _persist_disposition_cancel_request(
    store: StateStore,
    *,
    envelope: ExecutionEnvelope,
    order: Order,
    disposition: str,
    events: list[ExecutionEvent],
    target_order_ids: tuple[str, ...],
    claim_occurrence: int,
) -> ExecutionEvent:
    """Hold a disposition while one exact submit claim has no broker id.

    This is not a venue attempt and grants no cancel authority.  It only keeps
    the already-made disposition decision durable until accepted-submit truth
    either supplies a concrete broker identity or proves that the claim ended
    without acceptance.
    """

    if (
        not isinstance(claim_occurrence, int)
        or isinstance(claim_occurrence, bool)
        or claim_occurrence < 0
    ):
        raise RecoveryTransitionError(
            "brokerless disposition-cancel request requires a non-negative "
            f"claim occurrence for envelope {envelope.id} child {order.id}"
        )
    if (
        not target_order_ids
        or target_order_ids != tuple(sorted(target_order_ids))
        or len(set(target_order_ids)) != len(target_order_ids)
        or order.id not in target_order_ids
    ):
        raise RecoveryTransitionError(
            "brokerless disposition-cancel request requires one canonical, "
            f"complete local target scope containing child {order.id}"
        )
    dedupe_key = (
        f"envelope:{envelope.id}:disposition_cancel_request:"
        f"{order.id}:{disposition}:{claim_occurrence}"
    )
    prior = next((event for event in events if event.dedupe_key == dedupe_key), None)
    decision_time = prior.ts_event if prior is not None else utcnow()
    draft = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=dedupe_key,
        ts_event=decision_time,
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        quantity=order.quantity,
        price=order.limit_price,
        order_id=order.id,
        envelope_id=envelope.id,
        session_id=envelope.session_id,
        correlation_id=envelope.sell_intent_id,
        payload={
            "action": _DISPOSITION_CANCEL_REQUEST_ACTION,
            "actor": "engine",
            "disposition": disposition,
            "claim_occurrence": claim_occurrence,
            "target_order_ids": list(target_order_ids),
        },
    )
    stored = await store.append_execution_event(draft)
    if not _stored_cancel_attempt_matches(stored, draft):
        raise RecoveryTransitionError(
            "disposition-cancel request dedupe identity conflicts with persisted "
            f"fact for envelope {envelope.id} child {order.id} claim "
            f"{claim_occurrence}"
        )
    return stored


async def _persist_disposition_cancel_attempt(
    store: StateStore,
    *,
    envelope: ExecutionEnvelope,
    order: Order,
    disposition: str,
    events: list[ExecutionEvent],
    target_snapshot: _CancelTargetSnapshot,
) -> Optional[int]:
    """Append the next exact cancel attempt before IO.

    ``None`` means another caller won the same dedupe key. That caller alone
    owns the venue call; a later cadence derives the next attempt from the log.
    """

    existing = _disposition_cancel_events(
        events, envelope_id=envelope.id, order_id=order.id
    )
    requests = [
        event
        for event in events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
        and event.envelope_id == envelope.id
        and event.order_id == order.id
        and event.payload.get("action") == _DISPOSITION_CANCEL_REQUEST_ACTION
    ]
    if existing:
        effective_disposition = str(existing[0].payload["disposition"])
    elif requests:
        effective_disposition = str(requests[0].payload["disposition"])
    else:
        effective_disposition = disposition
    if existing:
        persisted_snapshot = _cancel_target_snapshot_from_event(existing[0])
        if persisted_snapshot is None:
            raise RecoveryTransitionError(
                "disposition-cancel target snapshot is malformed for "
                f"envelope {envelope.id} child {order.id}"
            )
        effective_snapshot = persisted_snapshot
    else:
        effective_snapshot = target_snapshot
    attempt = len(existing) + 1
    if attempt > _DISPOSITION_CANCEL_RETRY_LIMIT:
        return None
    now = utcnow()
    draft = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=(
            f"envelope:{envelope.id}:disposition_cancel:"
            f"{order.id}:{effective_disposition}:{attempt}"
        ),
        ts_event=now,
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        quantity=order.quantity,
        price=order.limit_price,
        order_id=order.id,
        envelope_id=envelope.id,
        session_id=envelope.session_id,
        correlation_id=envelope.sell_intent_id,
        payload={
            "action": "cancel",
            "actor": "engine",
            "disposition": effective_disposition,
            "broker_order_id": order.broker_order_id,
            "attempt": attempt,
            "target_snapshot": _cancel_target_snapshot_payload(effective_snapshot),
        },
    )
    stored = await store.append_execution_event(draft)
    if not _stored_cancel_attempt_matches(stored, draft):
        raise RecoveryTransitionError(
            "disposition-cancel dedupe identity conflicts with persisted fact "
            f"for envelope {envelope.id} child {order.id} attempt {attempt}"
        )
    if stored.id != draft.id:
        return None
    events.append(stored)
    return attempt


async def _escalate_disposition_cancel_exhausted(
    store: StateStore,
    *,
    envelope: ExecutionEnvelope,
    order: Order,
    disposition: str,
) -> None:
    """Latch one tracked, exact child for human review after direct retries."""

    await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=order.broker_order_id or "",
        client_order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason="envelope_disposition_cancel_exhausted",
        session_id=order.session_id,
        candidate_id=order.candidate_id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
        event_type=EventType.SUBMIT_RECOVERY_NEEDS_REVIEW.value,
        extra_payload={
            "envelope_id": envelope.id,
            "action_kind": "envelope_disposition_cancel_exhausted",
            "disposition": disposition,
            "attempts": _DISPOSITION_CANCEL_RETRY_LIMIT,
        },
    )


async def _refresh_disposition_cancel_target_state(
    store: StateStore,
    *,
    envelope_id: str,
    order_id: str,
) -> str:
    """Classify a post-cancel transition race from fresh durable truth."""

    loaded = await _validated_envelope_lineage(store, envelope_id)
    if loaded is None:
        return "invalid"
    _, projection, orders = loaded
    if (
        projection.missing_envelope_ids
        or projection.missing_order_ids
        or projection.invalid_order_ids
    ):
        return "invalid"
    current = orders.get(order_id)
    if current is None:
        return "invalid"
    open_ids = {
        *(order.id for order in projection.venue_orders),
        *projection.unresolved_order_ids,
        *projection.recovery_order_ids,
        *projection.uncertain_claim_order_ids,
        *projection.needs_review_child_order_ids,
    }
    if current.status is OrderStatus.CANCEL_PENDING:
        return "converging"
    if current.status in (
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
    ):
        return "terminal" if order_id not in open_ids else "invalid"
    if order_id in open_ids and current.status in (
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
    ):
        return "open"
    return "invalid"


async def _cancel_envelope_working_order(
    store: StateStore,
    adapter: BrokerAdapter,
    envelope: ExecutionEnvelope,
    *,
    disposition: str = _EXPIRY_DISPOSITION_CANCEL,
    target_order_ids: Optional[frozenset[str]] = None,
) -> None:
    """Best-effort cancel of every projection-valid child obligation.

    New staging enforces one working child, but cancellation is a recovery
    boundary and must safely wind down a pre-R2/legacy lineage that already has
    multiple broker-confirmed children.  Missing, malformed, recovery-owned, or
    claim-uncertain lineages remain fail-closed; no target is guessed.  Each
    valid target is isolated so one failed cancel cannot strand its sibling.
    A replay supplies ``target_order_ids`` from a prior durable target snapshot;
    ``None`` is reserved for a fresh disposition decision or terminal-envelope
    recovery, which discovers the then-current projection-valid children.
    """

    if disposition not in _DISPOSITION_CANCEL_KINDS:
        raise ValueError(f"unknown envelope cancel disposition {disposition!r}")
    all_events = await store.get_execution_events()
    loaded = await _validated_envelope_lineage(store, envelope.id, events=all_events)
    if loaded is None:
        # WO-0036 R2 consolidation (E.3.2): fail closed loudly, not silently.
        # `envelope` was handed in already-loaded (by _converge_expired_envelope_
        # cancels or _run_one_envelope), so a None reload means it VANISHED from
        # the store between visits -- a should-not-happen inconsistency, never a
        # benign no-op. Fires at most once (the EXPIRED lister stops visiting an
        # absent envelope), so no per-tick spam.
        _log.warning(
            "envelope %s: cancel-convergence fail-closed -- lineage no longer "
            "resolves (envelope absent from store); no child cancelled",
            envelope.id,
        )
        return
    reloaded, projection, orders = loaded
    owner_ambiguity_ids = {
        *projection.missing_envelope_ids,
        *projection.missing_order_ids,
        *projection.invalid_order_ids,
    }
    symbol_ambiguity_ids = await store.envelope_obligation_ambiguity_for_symbol(
        reloaded.symbol
    )
    symbol_only_ambiguity = tuple(
        item for item in symbol_ambiguity_ids if item not in owner_ambiguity_ids
    )
    if symbol_only_ambiguity:
        _log.warning(
            "envelope %s: cancel-convergence fail-closed on symbol-scoped "
            "malformed lineage (symbol=%s ambiguity=%s); no unvalidated child "
            "targeted",
            reloaded.id,
            reloaded.symbol,
            symbol_only_ambiguity,
        )
    if (
        projection.missing_envelope_ids
        or projection.missing_order_ids
        or projection.invalid_order_ids
    ):
        # WO-0036 R2 consolidation (E.3.2): the core of the finding. A malformed/
        # legacy-corrupt lineage (dangling envelope refs, orders with no row, or
        # scope/shape/replacement-chain-invalid children) fails the cancel closed
        # -- correct (no target is guessed) -- but SILENTLY, so a stranded live
        # SELL never surfaced. Match the warning discipline of the sibling arm at
        # the failed-cancel branch below. A genuinely-corrupt lineage never
        # converges, so this recurs per tick by design: a persistent, non-self-
        # healing integrity fault SHOULD keep alerting until an operator repairs
        # it. (A durable, deduped needs_review event would be the quieter, fuller
        # remedy, but that writes the event log -- a human-gated surface -- and is
        # beyond this additive-logging fix; flagged for a separate decision.)
        _log.warning(
            "envelope %s: cancel-convergence fail-closed on a malformed lineage "
            "(missing_envelopes=%s missing_orders=%s invalid_orders=%s); no child "
            "cancelled -- corrupt lineage stranded, needs operator review",
            envelope.id,
            projection.missing_envelope_ids,
            projection.missing_order_ids,
            projection.invalid_order_ids,
        )
        return
    excluded_ids = set(projection.recovery_order_ids) | set(
        projection.uncertain_claim_order_ids
    )
    targets = {
        order.id: order
        for order in projection.venue_orders
        if order.id not in excluded_ids
    }
    request_only_targets: dict[str, Order] = {}
    for order_id in projection.uncertain_claim_order_ids:
        local = orders.get(order_id)
        if (
            local is not None
            and local.status is OrderStatus.SUBMITTING
            and local.broker_order_id is None
        ):
            request_only_targets[local.id] = local
    for order_id in projection.unresolved_order_ids:
        local = orders.get(order_id)
        if (
            local is not None
            and local.status is OrderStatus.CREATED
            and local.id not in excluded_ids
        ):
            targets[local.id] = local

    # Validate the complete lineage before applying the durable exact-id scope.
    # A malformed snapshot must remain visible as a projection failure, never be
    # made to look harmless by filtering its bad identity away first.
    if target_order_ids is not None:
        targets = {
            order_id: order
            for order_id, order in targets.items()
            if order_id in target_order_ids
        }
        request_only_targets = {
            order_id: order
            for order_id, order in request_only_targets.items()
            if order_id in target_order_ids
        }

    # Pre-arm every safely-local child before its compare-and-swap. The request
    # is a non-I/O hold for the next exact claim occurrence and carries the
    # complete local-order decision scope. If a claim wins after this append,
    # restart retains the disposition; if the local cancel wins, the historical
    # request clears logically against terminal truth without any venue call.
    request_candidates = {**targets, **request_only_targets}
    decision_target_order_ids = tuple(sorted(request_candidates))
    for order in request_candidates.values():
        if order.status not in (OrderStatus.CREATED, OrderStatus.SUBMITTING):
            continue
        prior_requests = [
            event
            for event in all_events
            if event.event_type is ExecutionEventType.ENVELOPE_ACTION
            and event.envelope_id == reloaded.id
            and event.order_id == order.id
            and event.payload.get("action") == _DISPOSITION_CANCEL_REQUEST_ACTION
        ]
        if prior_requests:
            continue
        prior_occurrence = claim_occurrence_at(
            all_events,
            order_id=order.id,
            at=datetime.max.replace(tzinfo=timezone.utc),
        )
        if order.status is OrderStatus.SUBMITTING and prior_occurrence is None:
            raise RecoveryTransitionError(
                "brokerless disposition-cancel request cannot bind SUBMITTING "
                f"child {order.id} to a durable claim occurrence"
            )
        if order.status is OrderStatus.SUBMITTING:
            assert prior_occurrence is not None
            request_claim_occurrence = prior_occurrence
        else:
            request_claim_occurrence = (
                0 if prior_occurrence is None else prior_occurrence + 1
            )
        stored_request = await _persist_disposition_cancel_request(
            store,
            envelope=reloaded,
            order=order,
            disposition=disposition,
            events=all_events,
            target_order_ids=decision_target_order_ids,
            claim_occurrence=request_claim_occurrence,
        )
        if not any(event.id == stored_request.id for event in all_events):
            all_events.append(stored_request)

    # Resolve every safely-local child. A submission claim can win this
    # compare-and-swap and return a broker-backed row; that raced identity must
    # join the same exact pre-IO snapshot as every incumbent venue child.
    refresh_after_created_race = False
    for order_id, order in list(targets.items()):
        if order.status is OrderStatus.CREATED:
            resolved = await store.transition_order(
                order.id,
                OrderStatus.CANCELED,
                expected_from=OrderStatus.CREATED,
            )
            targets[order_id] = resolved
            if resolved.status is not OrderStatus.CANCELED:
                refresh_after_created_race = True

    if refresh_after_created_race:
        # The CREATED projection lost its CAS. Re-read the complete durable
        # lineage before deciding whether the winner is venue-live, uncertain,
        # or broker-terminal; the stale pre-CAS projection grants no authority.
        return await _cancel_envelope_working_order(
            store,
            adapter,
            reloaded,
            disposition=disposition,
            target_order_ids=target_order_ids,
        )

    venue_call_orders = [
        order
        for order in targets.values()
        if order.broker_order_id is not None
        and order.status not in (OrderStatus.CREATED, OrderStatus.CANCEL_PENDING)
    ]
    current_target_snapshot = _cancel_target_snapshot_for_orders(venue_call_orders)
    historical_snapshot_by_order: dict[str, _CancelTargetSnapshot] = {}
    for event in all_events:
        if (
            event.event_type is not ExecutionEventType.ENVELOPE_ACTION
            or event.envelope_id != reloaded.id
            or event.payload.get("action") != "cancel"
        ):
            continue
        snapshot = _cancel_target_snapshot_from_event(event)
        if snapshot is None:
            continue
        for snapshot_order_id, _ in snapshot:
            historical_snapshot_by_order.setdefault(snapshot_order_id, snapshot)

    # Phase 1: prepare every exact target before the first venue call. The full
    # target snapshot is carried by each attempt, so even a crash/fault between
    # sibling appends leaves the first fact able to recover the remaining
    # pre-decision child without granting authority over a later child.
    prepared_open: dict[str, tuple[int, str]] = {}
    prepared_terminal: set[str] = set()
    for order in targets.values():
        if order.broker_order_id is None or order.status is OrderStatus.CANCEL_PENDING:
            continue
        target_snapshot = historical_snapshot_by_order.get(
            order.id, current_target_snapshot
        )
        if not target_snapshot:
            raise RecoveryTransitionError(
                "disposition-cancel target snapshot is empty for "
                f"envelope {reloaded.id} child {order.id}"
            )
        if order.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED):
            prior_attempts = _disposition_cancel_events(
                all_events, envelope_id=reloaded.id, order_id=order.id
            )
            effective_disposition = (
                str(prior_attempts[0].payload["disposition"])
                if prior_attempts
                else disposition
            )
            if len(prior_attempts) >= _DISPOSITION_CANCEL_RETRY_LIMIT:
                await _escalate_disposition_cancel_exhausted(
                    store,
                    envelope=reloaded,
                    order=order,
                    disposition=effective_disposition,
                )
                continue
            attempt = await _persist_disposition_cancel_attempt(
                store,
                envelope=reloaded,
                order=order,
                disposition=effective_disposition,
                events=all_events,
                target_snapshot=target_snapshot,
            )
            if attempt is not None:
                prepared_open[order.id] = (attempt, effective_disposition)
            continue

        # The projection, not the terminal local column, says this broker
        # interval is still open. Give it its durable recovery owner before any
        # best-effort venue call; the recovery loop then confirms terminal truth.
        attempt = await _persist_disposition_cancel_attempt(
            store,
            envelope=reloaded,
            order=order,
            disposition=disposition,
            events=all_events,
            target_snapshot=target_snapshot,
        )
        await store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=order.broker_order_id,
            client_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason=(
                "envelope cancel found a broker-open interval behind "
                f"local {order.status.value}"
            ),
            session_id=order.session_id,
            candidate_id=order.candidate_id,
            extra_payload={
                "envelope_id": envelope.id,
                "action_kind": "cancel_terminal_venue_interval",
            },
        )
        if attempt is not None:
            prepared_terminal.add(order.id)

    # Phase 2: only fully prepared exact children may acquire venue authority.
    for order in targets.values():
        try:
            if (
                order.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)
                and order.broker_order_id is not None
            ):
                prepared = prepared_open.get(order.id)
                if prepared is None:
                    continue
                attempt, effective_disposition = prepared
                try:
                    await adapter.cancel_order(order.broker_order_id)
                except BrokerError:
                    if attempt == _DISPOSITION_CANCEL_RETRY_LIMIT:
                        refreshed_state = (
                            await _refresh_disposition_cancel_target_state(
                                store,
                                envelope_id=reloaded.id,
                                order_id=order.id,
                            )
                        )
                        if refreshed_state in ("terminal", "converging"):
                            continue
                        if refreshed_state == "open":
                            await _escalate_disposition_cancel_exhausted(
                                store,
                                envelope=reloaded,
                                order=order,
                                disposition=effective_disposition,
                            )
                    raise
                try:
                    await store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
                except _TRANSITION_ERRORS:
                    refreshed_state = await _refresh_disposition_cancel_target_state(
                        store,
                        envelope_id=reloaded.id,
                        order_id=order.id,
                    )
                    if refreshed_state in ("terminal", "converging"):
                        continue
                    if (
                        refreshed_state == "open"
                        and attempt == _DISPOSITION_CANCEL_RETRY_LIMIT
                    ):
                        await _escalate_disposition_cancel_exhausted(
                            store,
                            envelope=reloaded,
                            order=order,
                            disposition=effective_disposition,
                        )
                    raise
                continue
            if order.id in prepared_terminal and order.broker_order_id is not None:
                await adapter.cancel_order(order.broker_order_id)
        except (BrokerError, *_TRANSITION_ERRORS) as exc:
            _log.warning(
                "envelope %s: child %s cancel failed (%s); reconcile will converge it",
                envelope.id,
                order.id,
                exc,
            )


# A persisted cancel event remains a convergence obligation after stale data
# clears or a process restarts. EXPIRED envelopes also enter here when a crash
# landed between their transition and the first durable attempt.
async def _converge_envelope_disposition_cancels(
    store: StateStore, adapter: BrokerAdapter
) -> None:
    """Re-drive exact, durable expiry and stale-data cancel obligations."""

    try:
        envelopes = await store.list_envelopes()
        events = await store.get_execution_events()
    except Exception:  # noqa: BLE001 — never crash the tick
        _log.exception("envelope disposition cancel-convergence: listing failed")
        return

    persisted_by_envelope: dict[str, str] = {}
    persisted_target_ids: dict[str, set[str]] = {}
    for event in events:
        if (
            event.event_type is ExecutionEventType.ENVELOPE_ACTION
            and event.envelope_id is not None
            and event.payload.get("action")
            in ("cancel", _DISPOSITION_CANCEL_REQUEST_ACTION)
        ):
            raw_disposition = event.payload.get("disposition")
            persisted_by_envelope.setdefault(
                event.envelope_id,
                raw_disposition
                if isinstance(raw_disposition, str)
                and raw_disposition in _DISPOSITION_CANCEL_KINDS
                else _EXPIRY_DISPOSITION_CANCEL,
            )
            target_ids = persisted_target_ids.setdefault(event.envelope_id, set())
            if event.payload.get("action") == _DISPOSITION_CANCEL_REQUEST_ACTION:
                request_target_ids = _cancel_request_target_order_ids(event)
                if request_target_ids is None:
                    if event.order_id is not None:
                        target_ids.add(event.order_id)
                else:
                    target_ids.update(request_target_ids)
                continue
            snapshot = _cancel_target_snapshot_from_event(event)
            if snapshot is None:
                # Keep malformed history in the candidate set so the shared
                # projection can fail it closed and surface diagnostics.
                if event.order_id is not None:
                    target_ids.add(event.order_id)
            else:
                target_ids.update(order_id for order_id, _ in snapshot)

    for env in envelopes:
        disposition = persisted_by_envelope.get(env.id)
        target_order_ids: Optional[frozenset[str]] = None
        if (
            env.status is EnvelopeStatus.EXPIRED
            and env.expiry_disposition is EnvelopeExpiryDisposition.CANCEL_AND_RETURN
        ):
            disposition = _EXPIRY_DISPOSITION_CANCEL
            # Terminal envelope truth independently cancels every then-current
            # valid child. This also repairs a crash between EXPIRED and the
            # first exact child event. Per-child persisted request/attempt facts
            # retain their earlier disposition when the same child overlaps.
        elif disposition is not None:
            # Non-terminal replay is bounded by the exact pre-IO snapshot. A
            # later child can never inherit an older child's cancel authority.
            target_order_ids = frozenset(persisted_target_ids.get(env.id, set()))
        if disposition is None:
            continue
        try:
            await _cancel_envelope_working_order(
                store,
                adapter,
                env,
                disposition=disposition,
                target_order_ids=target_order_ids,
            )
        except Exception:  # noqa: BLE001 — isolate per envelope
            _log.exception("envelope %s: disposition cancel-convergence failed", env.id)


async def _converge_expired_envelope_cancels(
    store: StateStore, adapter: BrokerAdapter
) -> None:
    """Compatibility seam; convergence now includes persisted stale cancels."""

    await _converge_envelope_disposition_cancels(store, adapter)


async def _run_envelopes(
    store: StateStore,
    adapter: BrokerAdapter,
    market_data: Optional[MarketDataService],
    settings: Optional[Settings],
    *,
    tapes: Optional[EnvelopeTapeBuffer],
    now: Optional[datetime] = None,
) -> None:
    """The envelope pass (ADR-010 §1): runs immediately after protection —
    protection always outranks autonomous repricing. Per-envelope failure
    isolation matches the protection conventions: a policy exception freezes
    ONLY that envelope (event-logged via the transition) and the tick
    continues; the pass as a whole never raises."""

    if market_data is None or tapes is None:
        return
    try:
        envelopes = await store.list_envelopes(status=EnvelopeStatus.ACTIVE)
    except Exception:  # noqa: BLE001 — never crash the tick
        _log.exception("envelope pass: listing active envelopes failed")
        return
    if not envelopes:
        return
    ts = now if now is not None else utcnow()
    snap_memo: dict[str, Optional[MarketSnapshot]] = {}
    for envelope in envelopes:
        try:
            await _run_one_envelope(
                store,
                adapter,
                market_data,
                envelope,
                tapes=tapes,
                snap_memo=snap_memo,
                now=ts,
            )
        except EnvelopeActionPausedError:
            # Codex PR#8 F4: a child in TIMEOUT_QUARANTINE PAUSES the envelope —
            # no action may be planned/written until ADR-002 targeted
            # reconciliation resolves the ambiguity. That is an EXPECTED transient
            # wait, NOT a policy crash: leave the envelope ACTIVE (skip this
            # tick's action) so it resumes automatically once the quarantine
            # clears. Freezing here (the broad handler below) would force a manual
            # human resume after a recoverable submit/replace timeout.
            _log.info(
                "envelope %s (%s): paused this tick (child in TIMEOUT_QUARANTINE); "
                "left ACTIVE for reconciliation to resolve",
                envelope.id,
                envelope.symbol,
            )
            continue
        except Exception as exc:  # noqa: BLE001 — isolate per envelope
            _log.exception(
                "envelope %s (%s): pass failed; freezing that envelope only",
                envelope.id,
                envelope.symbol,
            )
            try:
                await store.transition_envelope(
                    envelope.id,
                    EnvelopeStatus.FROZEN,
                    actor="engine",
                    reason=f"policy_error:{type(exc).__name__}",
                    now=ts,  # Codex #2: injected tick clock, not wall clock
                )
            except Exception:  # noqa: BLE001
                _log.exception(
                    "envelope %s: freeze after policy error ALSO failed",
                    envelope.id,
                )


async def _run_one_envelope(
    store: StateStore,
    adapter: BrokerAdapter,
    market_data: MarketDataService,
    envelope: ExecutionEnvelope,
    *,
    tapes: EnvelopeTapeBuffer,
    snap_memo: dict[str, Optional[MarketSnapshot]],
    now: datetime,
) -> None:
    symbol = envelope.symbol
    if symbol not in snap_memo:
        # One fetch per symbol per pass, shared across the symbol's envelopes.
        snap_memo[symbol] = await market_data.get_snapshot(symbol)
    snapshot = snap_memo[symbol]
    if snapshot is not None:
        tapes.append(snapshot)

    events = await store.get_execution_events()
    cancel_events = [
        event
        for event in events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
        and event.envelope_id == envelope.id
        and event.payload.get("action")
        in ("cancel", _DISPOSITION_CANCEL_REQUEST_ACTION)
    ]
    if cancel_events:
        # A stale-data decision survives restart and data recovery. Do not let
        # fresh policy work overtake it while its exact child is still live,
        # recovery-owned, or malformed. Once broker-terminal truth closes that
        # child, an ACTIVE envelope may resume from the same durable history.
        loaded = await _validated_envelope_lineage(store, envelope.id, events=events)
        if loaded is None:
            return
        _, projection, _ = loaded
        cancel_unresolved_ids = {
            *projection.unresolved_order_ids,
            *projection.recovery_order_ids,
            *projection.uncertain_claim_order_ids,
            *projection.needs_review_child_order_ids,
        }
        if (
            any(event.order_id is None for event in cancel_events)
            or projection.missing_envelope_ids
            or projection.missing_order_ids
            or projection.invalid_order_ids
        ):
            return
        cancel_target_ids: set[str] = set()
        for event in cancel_events:
            if event.payload.get("action") == _DISPOSITION_CANCEL_REQUEST_ACTION:
                request_target_ids = _cancel_request_target_order_ids(event)
                if request_target_ids is None:
                    return
                cancel_target_ids.update(request_target_ids)
                continue
            cancel_snapshot = _cancel_target_snapshot_from_event(event)
            if cancel_snapshot is None:
                return
            cancel_target_ids.update(order_id for order_id, _ in cancel_snapshot)
        if cancel_target_ids & cancel_unresolved_ids:
            return

    # A staged-but-unexecuted action (transient release / crash between
    # staging and the venue call) resumes FIRST, with no new accounting —
    # the budget was spent when it was staged (INV-083).
    # Forward the tick's injected clock: redrive RE-VALIDATES the staged action
    # (TTL / session-phase / reduce-only) and must use the tick's `now`, not a
    # bare utcnow() fallback (engine determinism — H11 / REV-0023 parity-0).
    redriven = await redrive_staged_envelope_action(
        store, adapter, envelope.id, now=now
    )
    if redriven is not None and redriven.outcome not in (
        ENVELOPE_EXEC_BLOCKED,
        ENVELOPE_EXEC_RELEASED,
    ):
        return  # one venue action per envelope per tick

    # WO-0025: the policy's working-order predicate needs the envelope's
    # ORDERS' lifecycle events too (FILLED/CANCELED/REJECTED terminals carry
    # order_id but no envelope_id) — include them alongside the envelope's
    # own events.
    own_order_ids = {
        e.order_id
        for e in events
        if e.envelope_id == envelope.id and e.order_id is not None
    }
    history = [
        e
        for e in events
        if e.envelope_id == envelope.id
        or (e.order_id is not None and e.order_id in own_order_ids)
    ]
    decision = decide(envelope, tapes.tape(symbol), now=now, history=history)

    if isinstance(decision, PlannedAction):
        if snapshot is None:
            return  # no live snapshot to fingerprint — hold this tick
        await execute_envelope_action(
            store,
            adapter,
            envelope.id,
            decision,
            snapshot_fingerprint=market_snapshot_fingerprint(snapshot),
            actor="engine",
            now=now,
        )
    elif isinstance(decision, BreachSignal):
        # A real market-vs-mandate breach (e.g. exit only executable below
        # floor): terminal-pending-human, quarantine posture.
        await store.transition_envelope(
            envelope.id,
            EnvelopeStatus.BREACHED,
            actor="engine",
            reason=f"{decision.rail}: {decision.detail}",
            now=now,  # Codex #2: persisted breached_at matches the decision clock
        )
    elif isinstance(decision, ExhaustedSignal):
        await store.transition_envelope(
            envelope.id,
            EnvelopeStatus.EXHAUSTED,
            actor="engine",
            reason=decision.detail,
            now=now,  # Codex #2
        )
    elif isinstance(decision, ExpiredSignal):
        await store.transition_envelope(
            envelope.id,
            EnvelopeStatus.EXPIRED,
            actor="engine",
            reason=f"ttl_lapsed:{decision.disposition.value}",
            now=now,  # Codex #2
        )
        if decision.disposition is EnvelopeExpiryDisposition.CANCEL_AND_RETURN:
            await _cancel_envelope_working_order(
                store,
                adapter,
                envelope,
                disposition=_EXPIRY_DISPOSITION_CANCEL,
            )
        # REST_AT_FLOOR: the working order deliberately keeps resting.
    elif isinstance(decision, StaleDataSignal):
        # Fail closed: repricing already stopped (the policy returned no
        # plan). The envelope stays ACTIVE — staleness is transient — and the
        # approval-time choice decides the resting order's fate.
        if decision.disposition is EnvelopeStaleDataDisposition.CANCEL:
            await _cancel_envelope_working_order(
                store,
                adapter,
                envelope,
                disposition=_STALE_DATA_DISPOSITION_CANCEL,
            )
    # NoAction (monitoring / cooldown / warmup / out-of-phase): nothing.


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
    # PR #4 review (P2): loop-owned round-robin cursor so the shared budget can't let
    # the earliest TIMEOUT_QUARANTINE orders starve later ones — spans ticks like the
    # budget; direct run_monitoring_tick callers (tests) pass none.
    reconcile_fairness = ReconcileFairnessCursor()
    # WO-0020: the loop owns the per-symbol snapshot tape the envelope policy
    # consumes (working data — a restart re-warms; see EnvelopeTapeBuffer).
    envelope_tapes = EnvelopeTapeBuffer()
    # Wave 4f gate: the startup reduce-only gate is owned by ``run_startup_reconcile``
    # (called in the app lifespan BEFORE this loop, so trading is Reducing-until-parity
    # before the first tick). This loop then MAINTAINS the reconcile driver each tick
    # (parity → Active, divergence/failure → Reducing) via ``drive_reconcile_state``.
    while True:
        try:
            await asyncio.sleep(settings.poll_cadence_seconds)
            await run_monitoring_tick(
                store,
                adapter,
                settings,
                market_data=market_data,
                reconcile_budget=reconcile_budget,
                reconcile_fairness=reconcile_fairness,
                drive_reconcile_state=True,
                envelope_tapes=envelope_tapes,
            )
        except asyncio.CancelledError:
            _log.info("monitoring loop cancelled; shutting down")
            raise
        except Exception:  # noqa: BLE001 - a tick failure must not stop the loop
            _log.exception("monitoring tick failed; continuing on next cadence")


async def run_startup_reconcile(
    store: StateStore, adapter: BrokerAdapter, settings: Settings
) -> None:
    """§7 startup mass-status reconcile + gate (wave 4f). Run ONCE at app startup
    (``app/main.py`` lifespan) BEFORE normal trading is enabled:

    * Enter reduce-only (drive the reconcile TradingState driver → ``Reducing``) —
      "if startup reconciliation fails, trading is not enabled" (§7); ``Reducing`` is
      the §8 default under pending reconciliation (reduce-only: no new BUY intent,
      exits allowed).
    * Run one mass-report reconcile pass. On confirmed parity it lifts the driver to
      ``Active`` (normal trading enabled); on divergence or FAILURE it stays
      ``Reducing`` (R3: never auto-``Halted`` — a held position stays exitable at
      boot) and the monitoring loop keeps re-checking each tick until parity.

    No-op when reconciliation is disabled. Failures are contained at startup only
    after the effective state is verified reduce-only; failure to establish that
    gate aborts startup. The normal cadence retries repair/reconciliation."""

    _log.info("startup reconcile: entering reduce-only until parity confirmed")
    try:
        await _reconcile_and_gate(store, adapter, settings, reason="startup_pending")
    except _ReconcileGateEstablishmentError:
        # A kill switch may make the composed state HALTED even though the
        # reconcile-driver write itself failed.  HALTED cannot be used as proof
        # that the required startup gate was durably established.
        raise
    except Exception as exc:  # noqa: BLE001 - contain only behind a verified gate
        if not await _effective_state_is_reduce_only(store):
            raise _ReconcileGateEstablishmentError(
                "startup could not establish the required reduce-only gate"
            ) from exc
        _log.exception("startup reconcile failed; trading remains reduce-only")


async def on_stream_reconnect(
    store: StateStore, adapter: BrokerAdapter, settings: Settings
) -> None:
    """§7 stream-reconnect handler (wave 4g / R1). A trade-update stream reconnect has
    NO replay, so our locally-cached order/position state may have drifted while the
    stream was down — enter reduce-only (reconcile driver → ``Reducing``) and trigger a
    mass-status reconcile; the monitoring loop then maintains ``Reducing`` until parity,
    then lifts to ``Active`` (§7 "reconcile-after-reconnect ... until parity, Reducing").

    **R1 (sim seam):** the spine is REST-poll (D-011) — there is no real trade-update
    stream yet. This is the seam a real stream's reconnect callback WILL call; for now
    it is invoked deterministically from the sim/tests, and real-stream wiring is
    deferred with real creds (see docs/SPINE_PHASE4_PLAN.md R1). No-op when
    reconciliation is disabled. Repair/reconcile faults are contained after the
    effective state is verified reduce-only; failure to establish that gate raises
    so the caller cannot treat an ACTIVE reconnect as safely handled."""

    _log.warning("stream reconnect — entering reduce-only + reconciling (§7 / wave 4g)")
    try:
        await _reconcile_and_gate(store, adapter, settings, reason="stream_reconnect")
    except _ReconcileGateEstablishmentError:
        # See startup: a pre-existing HALTED control state does not prove the
        # reconnect's reconcile-driver write committed.
        raise
    except Exception as exc:  # noqa: BLE001 - callback isolation behind a safe gate
        if not await _effective_state_is_reduce_only(store):
            raise _ReconcileGateEstablishmentError(
                "stream reconnect could not establish the required reduce-only gate"
            ) from exc
        _log.exception("stream reconnect reconcile failed; trading remains reduce-only")


async def _reconcile_and_gate(
    store: StateStore, adapter: BrokerAdapter, settings: Settings, *, reason: str
) -> None:
    """Shared reduce-only-until-parity gate (wave 4f/4g): drive the reconcile
    TradingState driver → ``Reducing`` (``reason``), then run one mass-reconcile pass
    that lifts to ``Active`` on confirmed parity (or holds ``Reducing`` on divergence /
    failure — R3). No-op when reconciliation is disabled."""

    if not settings.reconciliation_enabled:
        return
    set_succeeded = await _safe_set_reconcile_state(
        store, TradingState.REDUCING, reason=reason
    )
    if not set_succeeded or not await _effective_state_is_reduce_only(store):
        raise _ReconcileGateEstablishmentError(
            "reconcile could not establish the required reduce-only gate"
        )
    # Repair durable broker acceptance before parity may lift REDUCING.
    await _repair_unpersisted_submit_audits(store)
    await _repair_unattributed_envelope_fills(store)

    budget = ReconcileQueryBudget(settings.reconcile_query_budget_per_min)
    await _run_reconciliation(store, adapter, settings, budget=budget, drive_state=True)


async def run_monitoring_tick(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Settings,
    *,
    market_data: Optional[MarketDataService] = None,
    reconcile_budget: Optional[ReconcileQueryBudget] = None,
    reconcile_fairness: Optional[ReconcileFairnessCursor] = None,
    drive_reconcile_state: bool = False,
    envelope_tapes: Optional[EnvelopeTapeBuffer] = None,
    envelope_now: Optional[datetime] = None,
) -> None:
    """One monitoring iteration: submit pending orders, then reconcile open ones.

    Exposed separately from :func:`monitoring_loop` so tests drive a single,
    deterministic tick without the sleep/``while True`` wrapper. ``market_data``
    is **keyword-only with a ``None`` default** so every existing positional
    caller (tests, the Hypothesis state machine) is untouched; it feeds §5.4
    protective-sell order-type re-derivation and §7 fill-price fallback.
    """

    # Repair durable broker acceptance before any new venue action this tick.
    await _repair_unpersisted_submit_audits(store)
    # A canonical FILL may survive a crash after position ingestion but before
    # parent accounting. Repair terminal children before any new venue action.
    await _repair_unattributed_envelope_fills(store)

    # The loop-owned cadence establishes/refreshes reconciliation truth before
    # any protection, envelope, or submission venue action.  A failed driver
    # write or failed verification therefore aborts this tick while it is still
    # side-effect-free at the venue.  Direct test/API ticks keep their historic
    # end-of-pass observability reconcile and never drive the state machine.
    if drive_reconcile_state:
        await _run_reconciliation(
            store,
            adapter,
            settings,
            budget=reconcile_budget,
            drive_state=True,
        )

    # Phase 7: protection runs FIRST so a protective order it creates is claimed
    # + submitted in the SAME tick (no extra cadence of latency). No-op when there
    # is no market-data handle or protection is disabled.
    await _run_protection(store, adapter, market_data, settings)
    # ADR-010 §1 (WO-0020): the envelope pass runs immediately AFTER protection
    # (protection always first) and BEFORE the submit sweep, so a stop-exit the
    # policy stages is claimed + submitted in this same tick. No-op without a
    # market-data handle or a tape buffer (the loop owns one; direct tick
    # callers that don't pass one are untouched).
    await _run_envelopes(
        store,
        adapter,
        market_data,
        settings,
        tapes=envelope_tapes,
        now=envelope_now,  # injected policy clock; None = wall clock (loop)
    )
    await _submit_pending_orders(store, adapter, settings, market_data=market_data)
    await _redrive_stale_submitting(store, adapter, settings, market_data=market_data)
    # ADR-002: resolve any TIMEOUT_QUARANTINE order with a read-only targeted query
    # BEFORE the open-order reconcile — a resolution to SUBMITTED hands the order a
    # broker_order_id that the reconcile poll then tracks (and ingests fills for)
    # this same tick.
    await _resolve_timeout_quarantine(
        store,
        adapter,
        settings,
        budget=reconcile_budget,
        fairness=reconcile_fairness,
    )
    await _reconcile_open_orders(store, adapter, settings, market_data=market_data)
    # Codex #3 (R6): re-drive any EXPIRED CANCEL_AND_RETURN envelope whose
    # working-order cancel didn't complete — AFTER reconcile so a CANCEL_PENDING
    # from a prior tick is confirmed first (and this arm no-ops once terminal).
    await _converge_envelope_disposition_cancels(store, adapter)
    await _recover_unpersisted_submits(store, adapter)
    # Phase 4 wave 4e: the ACTING §7 mass-report reconcile. Runs LAST so it sees the
    # fully-reconciled post-tick state — a divergence it acts on is then one the
    # per-order poll structurally *couldn't* capture (an external venue order).
    # Slice 4e-2 surfaces external/unmanaged orders (non-mutating); later slices add
    # not-found resolution (4e-3) + broker-authoritative fills/parity/throttle (4e-4).
    # Failure-isolated; gated by ``reconciliation_enabled`` (default on).
    # ``drive_reconcile_state`` (loop/startup only) lets it drive the §8 reconcile
    # TradingState driver (Reducing while divergent, Active on parity — wave 4f / R2);
    # direct tick callers leave it False, so the corpus never flips trading_state.
    if not drive_reconcile_state:
        await _run_reconciliation(
            store,
            adapter,
            settings,
            budget=reconcile_budget,
            drive_state=False,
        )


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
    # Codex PR#8 #1: envelope-minted orders are driven ONLY by the envelope
    # executor (redrive: atomic replace + write-time re-validation). Exclude them
    # from the generic submit sweep — a reprice released to CREATED (transient
    # BrokerError after replace_order, or a crash before redrive) must NOT be
    # independently submit_order'd here, which would place a second live SELL
    # beside its still-working predecessor (double exposure) and bypass the
    # atomic-replace path.
    envelope_ids = await _envelope_order_ids(store)
    created = [o for o in created if o.id not in envelope_ids]
    if not created:
        return

    blocked_already: Optional[set[str]] = None

    for order in created:
        claim = await store.claim_order_for_submission(
            order.id,
            risk_limits=_capi_risk_limits(settings),
        )
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
        # CLAIM_CLAIMED (checked just above) guarantees a claimed order.
        assert claim.order is not None
        claimed = claim.order

        # §5.4 (Rule 12 / D-015): decide a protective sell's session-conditional
        # order type HERE, at the single submission choke point, not at creation.
        # A MARKET sell stays MARKET in regular hours, downgrades to a live-priced
        # LIMIT in pre/after-hours; an un-priceable pre/after-hours sell holds.
        prepared = await _prepare_managed_venue_order(
            store, claimed, market_data, settings
        )
        if prepared is None:
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
        effective, venue_scope = prepared

        try:
            broker_order_id = await adapter.submit_order(
                effective, venue_scope=venue_scope
            )
            # AIR-001: a well-behaved adapter returns a non-empty id or raises.
            # The venue call already happened, so a malformed id is ambiguous
            # acceptance, never a preflight failure that may release and resend.
            if not isinstance(broker_order_id, str) or not broker_order_id.strip():
                raise AmbiguousBrokerError(
                    f"adapter returned an empty broker id for order {claimed.id}"
                )
            broker_order_id = broker_order_id.strip()
        except asyncio.CancelledError:
            # Cancellation during the adapter await is an unknown send: an SDK
            # worker may still complete the venue mutation. Own that ambiguity
            # before the monitoring task is allowed to terminate.
            await await_accepted_submit_finalizer(
                _quarantine_or_own_ambiguous_submit(
                    store,
                    claimed,
                    AmbiguousBrokerError(
                        "submit cancelled after its venue call may have started"
                    ),
                    context="first_submit_cancelled",
                )
            )
            raise
        except TerminalBrokerError as exc:
            # AIR-003 (review follow-up): a *definitive* broker rejection on the
            # first submit (403/422/delisted). A duplicate whose lookup fails is
            # ambiguous because the venue confirmed an existing order.
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
            await await_accepted_submit_finalizer(
                _quarantine_or_own_ambiguous_submit(
                    store,
                    claimed,
                    exc,
                    context="first_submit",
                )
            )
            continue
        except Exception as exc:  # noqa: BLE001 - release the claim, retry next tick
            # Releasing SUBMITTING -> CREATED lets the next tick re-run the full
            # gate. But if the order's OWN session closed during the submit await
            # (close skips SUBMITTING, so the claim shielded it from the safe-local
            # CREATED-BUY sweep), releasing to CREATED would
            # strand a zombie CREATED order in a closed session forever — close
            # is one-shot and never runs again, and no other path cleans it up,
            # so it would count toward CAPI exposure indefinitely (regressing
            # D-013a's no-zombie-CREATED-after-close invariant). In that definite
            # pre-ack failure case, cancel it instead — the same terminal
            # disposition close applies to an eligible local CREATED buy. A merely
            # kill-switched/paused session still releases to
            # CREATED (reversible: the next claim holds it until the stop clears).
            # §5.5 (side-aware release): a SELL is legitimately submittable in a
            # closed session (§5.2) and keeps reconciling post-close (D-011), so it
            # ALWAYS releases SUBMITTING -> CREATED to retry next tick — never
            # CANCELED. Only a BUY keeps D-013a's no-zombie CANCELED when its own
            # session closed during the submit await (close is one-shot and would
            # otherwise leave a CREATED buy counting toward exposure forever).
            release_target = OrderStatus.CREATED
            if (
                OrderSide(claimed.side) is OrderSide.BUY
                and claimed.session_id is not None
            ):
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
        await await_accepted_submit_finalizer(
            _finalize_accepted_submit(store, adapter, claimed, broker_order_id)
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
    * A :class:`TerminalBrokerError` → escalate to a durable ``needs_review``
      recovery record rather than guessing.
    * An empty or whitespace-only id returned *after* the venue call is an
      :class:`AmbiguousBrokerError` → quarantine it; if quarantine persistence
      itself fails, create the durable ``needs_review`` owner instead. It is never
      released as a preflight failure.

    Deduped: an order already carrying an open recovery record or canonical
    accepted-submit fallback is neither re-driven nor re-recorded.

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
    # A canonical fallback is already durable proof that this local order was
    # accepted at the venue.  Repair normally runs before redrive, but the
    # producer boundary must remain safe under overlapping ticks/processes and
    # direct recovery invocation: never call the venue again for that row.
    for order in stale:
        order_events = await store.get_order_execution_events(order.id)
        if any(
            canonical_accepted_submit_broker_id(event, order) is not None
            for event in order_events
        ):
            already_covered.add(order.id)
    max_attempts = settings.stale_submitting_max_redrive_attempts
    # Codex PR#8 round-2 F1 (P1): envelope-minted orders must NEVER be blind
    # `submit_order`'d here (the SUBMITTING sibling of the CREATED-sweep exclusion
    # in `_submit_pending_orders`). A crash between the envelope claim and
    # `replace_order` strands a reprice replacement SUBMITTING+idless; a bare
    # submit would mint a SECOND live SELL beside the still-working predecessor,
    # because the atomic replace's venue cancel never ran. Route them to
    # TIMEOUT_QUARANTINE instead so the ADR-002 targeted `client_order_id` query
    # resolves them — the venue's replace is atomic, so predecessor A and
    # replacement B are never both live there (only a blind submit creates that).
    envelope_ids = await _envelope_order_ids(store)

    for order in stale:
        if order.id in already_covered:
            continue
        if order.id in envelope_ids:
            try:
                await store.quarantine_timed_out_order(
                    order.id, reason="envelope_stale_submit"
                )
            except _TRANSITION_ERRORS as q_exc:
                _log.warning(
                    "could not quarantine stale envelope submit %s: %s",
                    order.id,
                    q_exc,
                )
            continue
        # Backstop: too many durable no-progress attempts (broker errors or an
        # unpriceable snapshot) → escalate rather than loop indefinitely.
        prior_attempts = await _stale_redrive_attempt_count(store, order.id)
        if prior_attempts >= max_attempts:
            _log.error(
                "stale SUBMITTING order %s exhausted %s no-progress re-drive "
                "attempts; escalating to needs_review",
                order.id,
                prior_attempts,
            )
            await _escalate_stale_submitting(
                store,
                order,
                RuntimeError(
                    f"exhausted {prior_attempts} no-progress re-drive attempts "
                    f"(>= max {max_attempts})"
                ),
            )
            continue
        # §5.4: re-derive a protective sell's order type at THIS submission too
        # (the stale-re-drive is one of the three submit choke points). An
        # un-priceable pre/after-hours sell is left SUBMITTING to retry next tick
        # It consumes the same durable no-progress budget as BrokerError below.
        prepared = await _prepare_managed_venue_order(
            store, order, market_data, settings
        )
        if prepared is None:
            _log.info(
                "stale protective sell %s (%s): no priceable snapshot; leaving "
                "SUBMITTING to retry next tick",
                order.id,
                order.symbol,
            )
            await _record_redrive_deferral(
                store,
                order,
                prior_attempts + 1,
                RuntimeError("no priceable snapshot"),
                reason="unpriceable",
            )
            continue
        effective, venue_scope = prepared
        # Write-ahead progress: never call the broker unless the durable attempt
        # reservation commits. A broken audit store therefore fails closed on
        # every cadence instead of silently reissuing the request forever.
        if not await _record_redrive_attempt_started(store, order, prior_attempts + 1):
            continue
        try:
            broker_order_id = await adapter.submit_order(
                effective, venue_scope=venue_scope
            )
            if not isinstance(broker_order_id, str) or not broker_order_id.strip():
                raise AmbiguousBrokerError(
                    f"adapter returned an empty broker id re-driving stale "
                    f"SUBMITTING order {order.id}"
                )
            broker_order_id = broker_order_id.strip()
        except asyncio.CancelledError:
            await await_accepted_submit_finalizer(
                _quarantine_or_own_ambiguous_submit(
                    store,
                    order,
                    AmbiguousBrokerError(
                        "stale re-drive cancelled after its venue call may have started"
                    ),
                    context="stale_redrive_cancelled",
                )
            )
            raise
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
            await await_accepted_submit_finalizer(
                _quarantine_or_own_ambiguous_submit(
                    store,
                    order,
                    exc,
                    context="stale_redrive",
                )
            )
            continue
        except BrokerError as exc:
            # Transient — leave it SUBMITTING; the next tick re-drives idempotently.
            # The write-ahead STARTED fact already advanced the durable cap.
            _log.warning(
                "stale SUBMITTING order %s re-drive failed (transient, attempt "
                "%s/%s), will retry next tick: %s",
                order.id,
                prior_attempts + 1,
                max_attempts,
                exc,
            )
            continue

        await await_accepted_submit_finalizer(
            _finalize_accepted_submit(store, adapter, order, broker_order_id)
        )
        _log.info(
            "re-drove stale SUBMITTING order %s to SUBMITTED as broker %s",
            order.id,
            broker_order_id,
        )


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
    *,
    budget: Optional[ReconcileQueryBudget] = None,
    fairness: Optional[ReconcileFairnessCursor] = None,
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
    quarantined = await store.list_timeout_quarantined_orders()
    scope_by_order = await load_venue_order_scopes(store, quarantined)
    # PR #4 review (P2): round-robin the deterministic list so a limited budget
    # cannot let the earliest orders (persistently failing / escalated) starve the
    # later ones — resume just after the last order that consumed a token last tick.
    if fairness is not None:
        quarantined = fairness.rotate(quarantined)
    for order in quarantined:
        # ENG-002: each targeted resolution query is a §7/§9 REST call, so consume
        # the loop's shared reconcile budget before each one — a large quarantine
        # burst can no longer exceed the venue rate budget the mass-report and
        # targeted-reconcile calls already share. Exhausted → defer the remaining
        # quarantined orders to a later tick (they persist until resolved).
        if budget is not None and not budget.try_consume(utcnow()):
            break
        # This order got a token this tick — record it so the NEXT tick resumes
        # after it (fair rotation), before the query so a mid-loop error/return
        # still advances the cursor.
        if fairness is not None:
            fairness.record(order.id)
        try:
            update = await adapter.get_order_by_client_order_id(
                order.id,
                expected_symbol=order.symbol,
                expected_side=OrderSide(order.side),
                expected_quantity=order.quantity,
                expected_limit_price=order.limit_price,
                expected_order_type=(
                    None
                    if order_has_dynamic_venue_type(order)
                    else OrderType(order.order_type)
                ),
                expected_time_in_force="day",
                expected_order_class="simple",
                expected_scope=scope_by_order.get(order.id),
                allow_dynamic_market_sell=(
                    scope_by_order.get(order.id) is None
                    and order_has_dynamic_venue_type(order)
                ),
            )
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
                    store,
                    order,
                    errors + 1,
                    "query_error",
                    needs_review=errors + 1 >= max_attempts,
                    error=str(exc),
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
                    order.id,
                    update.status.value,
                    target.value,
                )
            except _TRANSITION_ERRORS as exc:
                # e.g. resolving to SUBMITTED with no broker id (AIR-001), or the
                # order left TIMEOUT_QUARANTINE another way — leave it, retry.
                _log.warning(
                    "could not resolve quarantined order %s to %s: %s",
                    order.id,
                    target.value,
                    exc,
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
                "resolving to REJECTED (never landed).",
                order.id,
                attempts,
            )
            try:
                await store.resolve_timeout_quarantine(
                    order.id, OrderStatus.REJECTED, reason="not_found_at_venue"
                )
            except _TRANSITION_ERRORS as exc:
                _log.warning(
                    "could not reject absent quarantined %s: %s", order.id, exc
                )
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
    store: StateStore,
    order: Order,
    attempt: int,
    exc: Exception,
    *,
    reason: str,
) -> None:
    """Record one no-progress re-drive attempt for the durable shared cap."""

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
            payload={"attempt": attempt, "error": str(exc), "reason": reason},
            session_id=order.session_id,
        )
    except Exception:  # noqa: BLE001 - audit is best-effort on a failure path
        _log.exception("could not record re-drive deferral for order %s", order.id)


async def _record_redrive_attempt_started(
    store: StateStore, order: Order, attempt: int
) -> bool:
    """Reserve a broker re-drive durably before any venue action."""

    try:
        await store.append_event(
            EventType.STALE_SUBMITTING_REDRIVE_STARTED.value,
            message=(
                f"stale SUBMITTING order {order.symbol} re-drive started "
                f"(attempt {attempt})"
            ),
            symbol=order.symbol,
            candidate_id=order.candidate_id,
            order_id=order.id,
            payload={"attempt": attempt, "reason": "broker_redrive"},
            session_id=order.session_id,
        )
        return True
    except Exception:  # noqa: BLE001 - fail closed before the broker call
        _log.exception(
            "could not reserve stale SUBMITTING re-drive for order %s; "
            "broker call suppressed",
            order.id,
        )
        return False


async def _stale_redrive_attempt_count(store: StateStore, order_id: str) -> int:
    """Count old deferrals plus write-ahead attempts across upgrades/restarts."""

    deferred = await _order_event_count(
        store, order_id, EventType.STALE_SUBMITTING_REDRIVE_DEFERRED.value
    )
    started = await _order_event_count(
        store, order_id, EventType.STALE_SUBMITTING_REDRIVE_STARTED.value
    )
    return deferred + started


async def _order_event_count(store: StateStore, order_id: str, event_type: str) -> int:
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


async def _finalize_accepted_submit(
    store: StateStore,
    adapter: BrokerAdapter,
    order: Order,
    broker_order_id: str,
) -> None:
    """Adopt one accepted id or install recovery before control can unwind."""

    try:
        await store.transition_order(
            order.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
        )
    except asyncio.CancelledError as exc:
        # The shielded ownership task itself observed cancellation at the store
        # boundary. Complete the same recovery path, then preserve cancellation.
        try:
            await _handle_unpersisted_submit(
                store, adapter, order, broker_order_id, exc
            )
        except Exception:  # noqa: BLE001 - fallback may already be durable
            _log.exception(
                "accepted-submit cancellation recovery failed for order %s",
                order.id,
            )
        raise
    except Exception as exc:  # noqa: BLE001 - broker acceptance needs ownership
        await _handle_unpersisted_submit(store, adapter, order, broker_order_id, exc)


async def _handle_unpersisted_submit(
    store: StateStore,
    adapter: BrokerAdapter,
    order: Order,
    broker_order_id: str,
    exc: BaseException,
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

    The audit append is diagnostic and best-effort; it is not an execution
    exposure owner. If recovery ownership cannot be committed, a separately
    deduped UNKNOWN_RECONCILE_REQUIRED execution fact always retains exact
    broker identity and blocks opposite-side work until repair, whether or not
    the ordinary audit happened to succeed. Any recovery-write failure still
    raises so the current cadence cannot continue into later venue actions.
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

    if accepted_broker_identity_is_tracked(current, broker_order_id):
        # The transition committed and only its response was lost. It is already
        # a normal poll/cancel owner; a recovery row would later cancel it as an
        # orphan and corrupt the valid local/venue state.
        return

    if status is OrderStatus.SUBMITTING:
        # Order is legitimately open at the broker; retry recording SUBMITTED.
        try:
            await store.transition_order(
                order.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
            )
            _log.info("recovered unpersisted submit for order %s on retry", order.id)
            return
        except Exception as retry_exc:  # noqa: BLE001 - fall through to recovery owner
            if await accepted_broker_identity_is_durably_tracked(
                store, order.id, broker_order_id
            ):
                _log.info(
                    "recovered unpersisted submit for order %s despite a lost "
                    "retry response",
                    order.id,
                )
                return
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
            client_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason=str(exc),
            session_id=order.session_id,
            candidate_id=order.candidate_id,
        )
    except Exception as recovery_exc:  # noqa: BLE001 - fail closed below
        _log.exception(
            "could not write submit-recovery record for order %s (broker %s)",
            order.id,
            broker_order_id,
        )
        await _record_accepted_submit_uncertainty(
            store, order, broker_order_id, recovery_exc
        )
        raise RuntimeError(
            "accepted broker submit has durable uncertainty but no recovery owner"
        ) from recovery_exc


async def _repair_accepted_submit_seed(
    store: StateStore, seed_kind: str, event: Any
) -> None:
    """Repair one accepted-submit audit or canonical execution fallback."""

    payload = event.payload or {}
    raw_broker_order_id = payload.get("broker_order_id")
    if (
        not event.order_id
        or not isinstance(raw_broker_order_id, str)
        or not raw_broker_order_id.strip()
    ):
        raise RecoveryTransitionError(
            f"accepted-submit {seed_kind} {event.id} has no repairable identity"
        )
    broker_order_id = raw_broker_order_id.strip()

    # Legacy audits may legitimately outlive a lost order row after a recovery
    # has already adopted the pair. Execution fallback truth is stricter: its
    # complete immutable provenance must validate before any represented-owner
    # release can make it disappear from venue-exposure scope.
    represented = await store.get_submit_recovery_by_identity(
        event.order_id, broker_order_id
    )
    if seed_kind == "audit" and represented is not None:
        return

    order = await store.get_order(event.order_id)
    if order is None:
        raise RecoveryTransitionError(
            f"accepted-submit {seed_kind} {event.id} references missing order "
            f"{event.order_id}"
        )
    if seed_kind == "execution_fallback":
        canonical_broker_id = canonical_accepted_submit_broker_id(event, order)
        if canonical_broker_id != broker_order_id:
            raise RecoveryTransitionError(
                f"accepted-submit execution fallback {event.id} has "
                "conflicting scope or provenance"
            )
        if represented is not None:
            return

    # A successful retry permanently represents this broker acceptance,
    # regardless of any later terminal lifecycle event.
    if order.broker_order_id == broker_order_id:
        return
    if order.status is OrderStatus.SUBMITTING:
        try:
            await store.transition_order(
                order.id,
                OrderStatus.SUBMITTED,
                broker_order_id=broker_order_id,
            )
            return
        except Exception:  # noqa: BLE001 - recovery ledger owns failed adoption
            if await accepted_broker_identity_is_durably_tracked(
                store, order.id, broker_order_id
            ):
                return

    extra_payload: dict[str, Any] = {
        "repaired_from_event_id": event.id,
        "repair_seed": seed_kind,
    }
    for key in ("envelope_id", "kind", "replaces_order_id"):
        if key in payload:
            extra_payload[key] = payload[key]
    await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=broker_order_id,
        client_order_id=order.id,
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason=f"repaired from accepted-submit {seed_kind} {event.id}",
        session_id=order.session_id,
        candidate_id=order.candidate_id,
        extra_payload=extra_payload,
    )


async def _repair_unpersisted_submit_audits(store: StateStore) -> None:
    """Restore durable ownership from bounded audit/execution truth pages.

    No broker call occurs here. Normal ``SUBMITTED`` identity is retried first;
    a recovery record owns convergence when the local lifecycle cannot adopt
    the accepted venue order. Global audit pages advance a durable cursor only
    after every row in that page is inspected, so unrelated history is never
    rescanned and a malformed seed remains stationary.
    """

    checkpoint_type = ExecutionEventType.SUBMIT_ACCEPTANCE_REPAIR_CHECKPOINT
    _checkpoint, execution_high_water, audit_cursor = await _execution_repair_cursor(
        store,
        checkpoint_type=checkpoint_type,
        repair_name="accepted_submit",
    )

    while True:
        next_cursor, audits = await store.get_audit_event_page(
            after_cursor=audit_cursor,
            limit=_EXECUTION_REPAIR_BATCH_SIZE,
        )
        if not audits:
            break
        for event in audits:
            if event.event_type == EventType.ORDER_SUBMIT_UNPERSISTED.value:
                await _repair_accepted_submit_seed(store, "audit", event)
        audit_cursor = next_cursor
        await _advance_execution_repair_checkpoint(
            store,
            checkpoint_type=checkpoint_type,
            repair_name="accepted_submit",
            up_to_sequence=execution_high_water,
            audit_cursor=audit_cursor,
            now=audits[-1].created_at,
        )
        if len(audits) < _EXECUTION_REPAIR_BATCH_SIZE:
            break

    while True:
        (
            _checkpoint,
            execution_high_water,
            persisted_audit_cursor,
            events,
        ) = await _execution_repair_tail(
            store,
            checkpoint_type=checkpoint_type,
            repair_name="accepted_submit",
        )
        audit_cursor = persisted_audit_cursor
        if not events:
            return
        for execution_event in events:
            if execution_event.event_type in _REPAIR_CHECKPOINT_TYPES:
                continue
            if (
                execution_event.event_type
                is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
                and execution_event.payload.get("reason")
                == ACCEPTED_SUBMIT_UNPERSISTED_REASON
            ):
                await _repair_accepted_submit_seed(
                    store, "execution_fallback", execution_event
                )
        if _repair_page_needs_checkpoint(events, checkpoint_type):
            await _advance_execution_repair_checkpoint(
                store,
                checkpoint_type=checkpoint_type,
                repair_name="accepted_submit",
                up_to_sequence=events[-1].sequence,
                audit_cursor=audit_cursor,
                now=events[-1].ts_init,
            )
        if len(events) < _EXECUTION_REPAIR_BATCH_SIZE:
            return


def _broker_filled(update: BrokerOrderUpdate) -> int:
    """How many shares the broker reports filled on a recovery poll — the
    order's cumulative ``filled_quantity`` plus any per-execution fills it
    carries, whichever is larger (adapters differ on which they populate)."""

    from_fills = sum(f.quantity for f in (update.fills or []))
    return max(update.filled_quantity or 0, from_fills)


async def _record_recovery_terminal_fact(
    store: StateStore,
    record: SubmitRecoveryRecord,
    status: OrderStatus,
) -> None:
    """Persist the broker's actual terminal fact before releasing recovery.

    ``RECOVERY_RESOLVED`` historically means ``resolved_canceled``, but the
    broker can also report REJECTED.  Recording the observed status first keeps
    event truth source-faithful; the store then sees the recovery-id fact and
    does not synthesize a second CANCELED event.  The claim occurrence is derived
    from the immutable recovery creation time so an old terminal cannot close a
    later claim of the same local order.
    """

    assert status in (OrderStatus.CANCELED, OrderStatus.REJECTED)
    events = await store.get_execution_events()
    occurrence = claim_occurrence_at(
        events,
        order_id=record.local_order_id,
        at=record.created_at,
    )
    payload: dict[str, Any] = {
        "broker_order_id": record.broker_order_id,
        "recovery_id": record.id,
        "cleanup_status": RECOVERY_RESOLVED,
    }
    if occurrence is not None:
        payload["claim_occurrence"] = occurrence
    expected_type = (
        ExecutionEventType.CANCELED
        if status is OrderStatus.CANCELED
        else ExecutionEventType.REJECTED
    )
    stored = await store.append_execution_event(
        ExecutionEvent(
            event_type=(expected_type),
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=f"submit_recovery_terminal:{record.id}:{status.value}",
            ts_event=utcnow(),
            symbol=record.symbol,
            side=record.side,
            quantity=record.quantity,
            order_id=record.local_order_id,
            session_id=record.session_id,
            payload=payload,
        )
    )
    if stored.event_type is not expected_type or not recovery_terminal_fact_matches(
        record,
        stored,
        claim_occurrence=occurrence,
    ):
        raise RecoveryTransitionError(
            "recovery terminal event identity conflicts with existing dedupe fact "
            f"for {record.id}"
        )


async def _resolve_recovery_terminal(
    store: StateStore,
    record: SubmitRecoveryRecord,
    status: OrderStatus,
) -> bool:
    """Atomically ordered terminal-fact/ledger work, isolated per recovery."""

    try:
        await _record_recovery_terminal_fact(store, record, status)
        await store.update_submit_recovery(
            record.id, cleanup_status=RECOVERY_RESOLVED, bump_attempt=True
        )
    except Exception:  # noqa: BLE001 - poison must not abort later records
        _log.exception(
            "recovery terminal persistence failed for broker order %s; "
            "leaving it unresolved",
            record.broker_order_id,
        )
        return False
    return True


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
    scope_by_order = await load_venue_order_scopes(
        store,
        [
            VenueScopeOwner(
                order_id=record.local_order_id,
                symbol=record.symbol,
                side=OrderSide(record.side),
                quantity=record.quantity,
                order_type=(
                    OrderType.LIMIT
                    if record.limit_price is not None
                    else OrderType.MARKET
                ),
                limit_price=record.limit_price,
                allow_dynamic_venue_type=(
                    record.limit_price is None
                    and OrderSide(record.side) is OrderSide.SELL
                ),
            )
            for record in records
        ],
    )
    for rec in records:
        expected_client_order_id = rec.client_order_id or rec.local_order_id
        try:
            update = await adapter.get_order_status(
                rec.broker_order_id,
                recorded_quantity=0,
                expected_client_order_id=expected_client_order_id,
                expected_symbol=rec.symbol,
                expected_side=OrderSide(rec.side),
                expected_quantity=rec.quantity,
                expected_limit_price=rec.limit_price,
                expected_order_type=(
                    None
                    if rec.limit_price is None and OrderSide(rec.side) is OrderSide.SELL
                    else OrderType.LIMIT
                    if rec.limit_price is not None
                    else OrderType.MARKET
                ),
                expected_time_in_force="day",
                expected_order_class="simple",
                expected_scope=scope_by_order.get(rec.local_order_id),
                allow_dynamic_market_sell=(
                    scope_by_order.get(rec.local_order_id) is None
                    and rec.limit_price is None
                    and OrderSide(rec.side) is OrderSide.SELL
                ),
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
            if not await _resolve_recovery_terminal(store, rec, update.status):
                continue
            _log.info(
                "recovered stranded broker order %s (terminal at broker)",
                rec.broker_order_id,
            )
            continue

        # Zero fills and still live → request a cancel and confirm.
        try:
            await adapter.cancel_order(rec.broker_order_id)
            confirm = await adapter.get_order_status(
                rec.broker_order_id,
                recorded_quantity=0,
                expected_client_order_id=expected_client_order_id,
                expected_symbol=rec.symbol,
                expected_side=OrderSide(rec.side),
                expected_quantity=rec.quantity,
                expected_limit_price=rec.limit_price,
                expected_order_type=(
                    None
                    if rec.limit_price is None and OrderSide(rec.side) is OrderSide.SELL
                    else OrderType.LIMIT
                    if rec.limit_price is not None
                    else OrderType.MARKET
                ),
                expected_time_in_force="day",
                expected_order_class="simple",
                expected_scope=scope_by_order.get(rec.local_order_id),
                allow_dynamic_market_sell=(
                    scope_by_order.get(rec.local_order_id) is None
                    and rec.limit_price is None
                    and OrderSide(rec.side) is OrderSide.SELL
                ),
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
            if not await _resolve_recovery_terminal(store, rec, confirm.status):
                continue
            _log.info(
                "recovered stranded broker order %s (cancel confirmed)",
                rec.broker_order_id,
            )
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
    scope_by_order = await load_venue_order_scopes(store, open_orders)

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
                recorded_raw = sum(
                    fill.quantity for fill in await store.list_fills(order_id=order.id)
                )
                update = await adapter.get_order_status(
                    order.broker_order_id,
                    recorded_quantity=recorded_raw,
                    fallback_price=fallback_price,
                    expected_client_order_id=order.id,
                    expected_symbol=order.symbol,
                    expected_side=OrderSide(order.side),
                    expected_quantity=order.quantity,
                    expected_limit_price=(
                        None
                        if order_has_dynamic_venue_type(order)
                        else order.limit_price
                    ),
                    expected_order_type=(
                        None
                        if order_has_dynamic_venue_type(order)
                        else OrderType(order.order_type)
                    ),
                    expected_time_in_force="day",
                    expected_order_class="simple",
                    expected_scope=scope_by_order.get(order.id),
                    allow_dynamic_market_sell=(
                        scope_by_order.get(order.id) is None
                        and order_has_dynamic_venue_type(order)
                    ),
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

    # WO-0020 envelope bridge: if this order was minted by an envelope, apply
    # each broker fill to the envelope FIRST with the SAME canonical dedupe
    # key the fill append uses. Record-first means the log gets ONE FILL event
    # (envelope-attributed); append_fill's own shadow event append then dedupes
    # to it while still writing the fill ROW — position folds exactly once and
    # the envelope's remaining decrements exactly once (INV-076). Fills without
    # a source_fill_id cannot be bridged deterministically (no venue identity
    # before the row exists) — production Alpaca fills always carry one.
    rejected: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    envelope_id: Optional[str] = None
    retry_parent_lookup = any(bf.source_fill_id is not None for bf in update.fills)
    if retry_parent_lookup:
        try:
            # Every fill in one broker update belongs to the same order. Resolve
            # its immutable ENVELOPE_ACTION lineage once, not once per fill.
            envelope_id = await _envelope_id_for_order(store, order.id)
        except Exception:  # noqa: BLE001 - canonical fill ingest still proceeds
            _log.exception(
                "envelope lineage lookup failed for order %s; retrying after ingest",
                order.id,
            )
        else:
            # A valid parent is stable for the batch. A missing parent gets one
            # fresh post-ingest retry for the terminal first-observation fault.
            retry_parent_lookup = envelope_id is None
    for bf in update.fills:
        # concurrency-0 root form (WO-0035): append_fill SELF-derives the
        # pre-fill position by excluding this fill's own dedupe identity from
        # the fold, so the record-first bridge below needs no prior-position
        # bookkeeping here (and no call site can fabricate the phantom
        # fill_overfill_quarantined by forgetting it).
        fill_key = (
            f"fill:{order.id}:{bf.source_fill_id}"
            if bf.source_fill_id is not None
            else None
        )
        bridged = False
        if fill_key is not None and envelope_id is not None:
            bridged = await _record_envelope_fill_for_parent(
                store,
                envelope_id=envelope_id,
                order_id=order.id,
                quantity=bf.quantity,
                dedupe_key=fill_key,
                price=bf.price,
                session_id=order.session_id,
                ts_event=bf.filled_at,
            )
        try:
            append_result = await store.append_fill(
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
            continue

        if append_result.status == "conflict":
            conflicts.append(
                {
                    "source_fill_id": bf.source_fill_id,
                    "quantity": bf.quantity,
                    "price": bf.price,
                    "reason": "source_fill_id_reused_with_conflicting_economics",
                }
            )
            # Never attribute or repair a payload whose canonical identity
            # already belongs to different fill economics.
            continue

        # Same-pass terminal repair runs outside append_fill's recoverable-error
        # handler. Once the canonical FILL is durable, a conflicting attribution
        # marker is durable corruption and must propagate instead of being
        # misclassified as a rejected broker fill.
        if fill_key is not None and not bridged:
            if envelope_id is None and retry_parent_lookup:
                retry_parent_lookup = False
                try:
                    envelope_id = await _envelope_id_for_order(store, order.id)
                except Exception:  # noqa: BLE001 - cadence retries durable seed
                    _log.exception(
                        "post-ingest envelope lineage lookup failed for order %s",
                        order.id,
                    )
            if envelope_id is not None:
                await _record_envelope_fill_for_parent(
                    store,
                    envelope_id=envelope_id,
                    order_id=order.id,
                    quantity=bf.quantity,
                    dedupe_key=fill_key,
                    price=bf.price,
                    session_id=order.session_id,
                    ts_event=bf.filled_at,
                    strict=True,
                )

    recorded_raw = sum(f.quantity for f in await store.list_fills(order_id=order.id))
    recorded_capped = min(recorded_raw, order.quantity)
    if update.filled_quantity > recorded_raw or conflicts:
        # Broker executed more than we could record — a durable, unrecordable
        # divergence (AIR-002). Escalate and hold the order non-terminal so the
        # untracked position is never buried under a terminal state.
        _log.error(
            "order %s: broker reports filled=%s but only %s recorded; escalating "
            "to a needs_review reconciliation record.",
            order.id,
            update.filled_quantity,
            recorded_raw,
        )
        await _escalate_fill_divergence(
            store,
            order,
            update,
            recorded_raw,
            rejected,
            conflicts,
        )
        target = _divergence_safe_status(order, recorded_capped)
    else:
        if update.filled_quantity != recorded_raw:
            # recorded > broker (should not happen for a monotonic broker feed);
            # trust the recorded fills, which are the position's source of truth.
            _log.warning(
                "order %s: recorded fills (%s) exceed broker filled (%s); "
                "reconciling to recorded.",
                order.id,
                recorded_raw,
                update.filled_quantity,
            )
        target = _reconciled_status(order, update.status, recorded_capped)
    try:
        await store.transition_order(order.id, target, filled_quantity=recorded_capped)
    except _TRANSITION_ERRORS as exc:
        _log.warning(
            "order %s reconcile to %s (recorded filled=%s) rejected: %s",
            order.id,
            target,
            recorded_capped,
            exc,
        )


async def _escalate_fill_divergence(
    store: StateStore,
    order: Order,
    update: BrokerOrderUpdate,
    recorded: int,
    rejected: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> None:
    """Durably record an unrecorded or conflicting broker fill as needs-review.

    Deduped by exact accepted broker leg: a
    recovery for a distinct broker id on the same local order cannot own this
    divergence, while the same pair is not re-recorded every diverging tick.
    """

    try:
        broker_order_id = order.broker_order_id or ""
        represented = await store.get_submit_recovery_by_identity(
            order.id, broker_order_id
        )
        if (
            represented is not None
            and represented.cleanup_status in RECOVERY_OPEN_STATUSES
        ):
            return
        await store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=broker_order_id,
            client_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason=(
                f"broker/local fill divergence: broker reports filled="
                f"{update.filled_quantity} ({update.status.value}) but only "
                f"{recorded} shares recorded locally"
                + (
                    "; duplicate fill identity carried conflicting economics"
                    if conflicts
                    else "; a real untracked position"
                )
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
                "conflicting_fills": conflicts,
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


def _has_unresolved_divergence(plan: ReconciliationPlan) -> bool:
    """True if the reconcile plan still shows the local + venue pictures out of sync
    (wave 4f gate): an open order absent from the venue (``needs_targeted_query``), an
    unmanaged venue order, or a broker-vs-local position drift. ``inferred_fills`` /
    ``resolutions`` are actions the reconcile TOOK this pass, not unresolved gaps."""

    return bool(
        plan.needs_targeted_query or plan.external_orders or plan.position_mismatches
    )


async def _safe_set_reconcile_state(
    store: StateStore, to: TradingState, *, reason: str
) -> bool:
    """Drive the reconcile TradingState driver (wave 4f / R2), best-effort — a store
    error here must never crash the ordinary tick.  The boolean lets startup and
    reconnect require a committed REDUCING gate. Redundant sets are store no-ops."""

    try:
        await store.set_reconcile_trading_state(to, reason=reason)
    except Exception:  # noqa: BLE001 - caller decides whether failure is fatal
        _log.exception("reconcile: could not drive trading_state -> %s", to.value)
        return False
    try:
        session = await store.get_current_session()
        events = await store.get_execution_events()
    except Exception:  # noqa: BLE001 - inability to verify is not success
        _log.exception("reconcile: could not verify the reconcile driver write")
        return False
    if reconcile_trading_state(events, session.id) is not to:
        _log.error("reconcile: driver verification failed after write -> %s", to.value)
        return False
    return True


async def _effective_state_is_reduce_only(store: StateStore) -> bool:
    """Whether the composed trading state currently blocks new BUY intent."""

    try:
        state = await store.current_trading_state()
    except Exception:  # noqa: BLE001 - inability to verify is not a safe gate
        _log.exception("reconcile: could not verify effective trading state")
        return False
    return state in {TradingState.REDUCING, TradingState.HALTED}


async def _run_reconciliation(
    store: StateStore,
    adapter: BrokerAdapter,
    settings: Settings,
    *,
    budget: Optional[ReconcileQueryBudget] = None,
    drive_state: bool = False,
) -> Optional[ReconciliationPlan]:
    """Wave 4e: the ACTING §7 mass-report reconcile. Computes the reconciliation
    plan from the venue's mass reports and acts on it:

    * surface external/unmanaged venue orders (4e-2, non-mutating);
    * resolve open orders confirmed-absent at the venue → terminal (4e-3, the
      oversell-critical targeted-query-before-reject path);
    * apply priced broker-authoritative reconciliation fills (4e-4, dedup-safe —
      INV-5/R8).

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
        if drive_state:
            reducing_committed = await _safe_set_reconcile_state(
                store,
                TradingState.REDUCING,
                reason="reconcile_budget_exhausted",
            )
            if not reducing_committed or not await _effective_state_is_reduce_only(
                store
            ):
                raise RuntimeError(
                    "reconcile query budget exhausted and reduce-only state "
                    "could not be verified"
                )
            raise RuntimeError(
                "reconcile query budget exhausted before a fresh parity check"
            )
        return None

    try:
        broker_orders = await adapter.list_open_orders()
        broker_positions = await adapter.list_positions()
        local_open = [
            o for o in await store.list_orders() if o.status in _OPEN_STATUSES
        ]
        local_positions = await store.list_positions()
        venue_scopes = await load_venue_order_scopes(store, local_open)
        plan = plan_reconciliation(
            local_open_orders=local_open,
            local_positions=local_positions,
            broker_orders=broker_orders,
            broker_positions=broker_positions,
            now=now,
            venue_scopes_by_order_id=venue_scopes,
            recent_threshold_ms=settings.reconcile_recent_threshold_ms,
            avg_price_tolerance=settings.reconcile_avg_price_tolerance,
        )
        await _surface_external_orders(store, plan, scope_by_order=venue_scopes)
        await _resolve_reconcile_not_found(
            store, adapter, settings, plan.needs_targeted_query, budget=budget
        )
        inferred_fills_persisted = await _apply_inferred_fills(store, plan)
        # `plan.resolutions` (a MATCHED order the mass report reports terminal) is
        # deliberately NOT applied here: a matched order carries a broker_order_id, so
        # the legacy per-order poll owns its terminal transition + fill ingestion —
        # acting on it here too would be a redundant double-actor write (E1). Alpaca's
        # open-only mass report never surfaces a matched terminal anyway; worst case an
        # order stays open locally one extra cycle if the poll is momentarily down (a
        # self-healing liveness gap, never an oversell). Observability-only on this path.
        if drive_state:
            if not inferred_fills_persisted:
                raise RuntimeError(
                    "reconcile inferred fill persistence incomplete; "
                    "parity cannot be established"
                )
            # Wave 4h: surface broker-vs-local position drift as a durable
            # needs_review record (§7 — never a position overwrite). Gated by
            # drive_state (loop/startup) so a direct tick against an adapter that
            # doesn't mirror positions never false-positives on every local position.
            await _surface_position_mismatches(store, plan)
            # Wave 4f / R2 gate: parity → Active (enable normal trading), any
            # unresolved divergence → Reducing (reduce-only until reconciled). Only
            # the loop / startup pass drive_state; direct tick callers (tests) don't.
            target_state = (
                TradingState.REDUCING
                if _has_unresolved_divergence(plan)
                else TradingState.ACTIVE
            )
            state_committed = await _safe_set_reconcile_state(
                store,
                target_state,
                reason="reconcile_parity"
                if not _has_unresolved_divergence(plan)
                else "reconcile_divergence",
            )
            if not state_committed:
                raise RuntimeError(
                    f"reconcile driver did not commit {target_state.value}"
                )
            if (
                target_state is TradingState.REDUCING
                and not await _effective_state_is_reduce_only(store)
            ):
                raise RuntimeError(
                    "reconcile driver committed Reducing but effective state "
                    "verification failed"
                )
        return plan
    except Exception as exc:  # noqa: BLE001 - reconcile is non-fatal; a failure never flips truth
        _log.warning("reconciliation skipped this cycle (non-fatal): %s", exc)
        if drive_state:
            # A reconcile FAILURE is not parity — stay reduce-only (R3: never
            # auto-Halt, a held position stays exitable), loud for the operator.
            _log.error(
                "reconcile failed — trading_state held at Reducing (reduce-only)"
            )
            reducing_committed = await _safe_set_reconcile_state(
                store, TradingState.REDUCING, reason="reconcile_failed"
            )
            if not reducing_committed or not await _effective_state_is_reduce_only(
                store
            ):
                raise RuntimeError(
                    "reconcile failure could not establish verified reduce-only state"
                ) from exc
            # The driver is safely REDUCING, but this cadence still stops.
            # Startup/reconnect contain the error only because their gate was
            # established before reconciliation began.
            raise
        return None


async def _apply_inferred_fills(store: StateStore, plan: ReconciliationPlan) -> bool:
    """Append each priced mass-report execution as broker-authoritative truth with
    RECONCILIATION ingress provenance (wave 4e-4). The engine never fabricates a
    zero-price fill, and ``source_fill_id`` is the execution's own venue id, so a
    later direct observation dedups to ONE (INV-5 / R8), never a double-count.
    Per-item faults are isolated so later observations still run, and the return
    value tells a driven reconciliation gate whether every planned fill reached
    durable truth."""

    parent_by_order: dict[str, Optional[str]] = {}
    post_ingest_lookup_done: set[str] = set()
    repair_needed = False
    all_persisted = True

    for f in plan.inferred_fills:
        # WO-0025 (REV-0023 F5): the RECORD-FIRST bridge applies to inferred
        # fills exactly as to streamed ones. Every operation for one inference,
        # including its order lookup, is isolated so a transient fault cannot
        # discard later independently valid items in the reconciliation batch.
        try:
            inferred_order = await store.get_order(f.order_id)
            inferred_session_id = (
                inferred_order.session_id if inferred_order is not None else None
            )
        except Exception:  # noqa: BLE001 - one inference must not abort the batch
            all_persisted = False
            _log.exception(
                "reconcile: could not load order %s for inferred fill; skipping item",
                f.order_id,
            )
            continue

        if f.order_id not in parent_by_order:
            try:
                parent_by_order[f.order_id] = await _envelope_id_for_order(
                    store, f.order_id
                )
            except Exception:  # noqa: BLE001 - retry once after canonical ingest
                _log.exception(
                    "envelope lineage lookup for inferred fill on order %s failed",
                    f.order_id,
                )
                parent_by_order[f.order_id] = None

        fill_key = (
            f"fill:{f.order_id}:{f.source_fill_id}"
            if f.source_fill_id is not None
            else None
        )
        bridged = False
        envelope_id = parent_by_order[f.order_id]
        if fill_key is not None and envelope_id is not None:
            bridged = await _record_envelope_fill_for_parent(
                store,
                envelope_id=envelope_id,
                quantity=f.quantity,
                dedupe_key=fill_key,
                price=f.price,
                order_id=f.order_id,
                session_id=inferred_session_id,
                source=EventSource.RECONCILIATION,
                authority=f.authority,
            )

        try:
            append_result = await store.append_fill(
                f.order_id,
                f.symbol,
                f.side,
                f.quantity,
                f.price,
                source_fill_id=f.source_fill_id,
                session_id=inferred_session_id,
                source=EventSource.RECONCILIATION,
                authority=f.authority,
            )
        except _FILL_ERRORS as exc:
            all_persisted = False
            _log.warning(
                "reconcile: inferred fill for order %s (%s) rejected: %s",
                f.order_id,
                f.symbol,
                exc,
            )
            continue

        except Exception:  # noqa: BLE001 - isolate unexpected per-item store faults
            all_persisted = False
            _log.exception(
                "reconcile: inferred fill for order %s failed; continuing batch",
                f.order_id,
            )
            continue

        if append_result.status == "conflict":
            all_persisted = False
            _log.error(
                "reconcile: conflicting duplicate fill identity for order %s; "
                "keeping parity gate reduce-only",
                f.order_id,
            )
            continue

        if fill_key is not None and not bridged:
            if envelope_id is None and f.order_id not in post_ingest_lookup_done:
                post_ingest_lookup_done.add(f.order_id)
                try:
                    envelope_id = await _envelope_id_for_order(store, f.order_id)
                except Exception:  # noqa: BLE001 - cadence retries durable seed
                    _log.exception(
                        "post-ingest envelope lineage lookup failed for inferred "
                        "fill on order %s",
                        f.order_id,
                    )
                else:
                    parent_by_order[f.order_id] = envelope_id
            if envelope_id is not None:
                bridged = await _record_envelope_fill_for_parent(
                    store,
                    envelope_id=envelope_id,
                    quantity=f.quantity,
                    dedupe_key=fill_key,
                    price=f.price,
                    order_id=f.order_id,
                    session_id=inferred_session_id,
                    source=EventSource.RECONCILIATION,
                    authority=f.authority,
                    strict=True,
                )
            repair_needed = repair_needed or not bridged

    # A batch performs at most one global durable-seed sweep, never one full-log
    # scan per inferred item. Normal record-first/post-ingest success needs none.
    if repair_needed:
        await _repair_unattributed_envelope_fills(store)
    return all_persisted


async def _surface_external_orders(
    store: StateStore,
    plan: ReconciliationPlan,
    *,
    scope_by_order: Optional[dict[str, VenueOrderScope]] = None,
) -> None:
    """Surface each external/unmanaged venue order as a durable, deduped
    ``reconcile_external_order`` audit record (§7: surfaced, NEVER silently
    absorbed into managed state or folded into position). Deduped by
    ``broker_order_id`` — one record per external order, ever (survives restart via
    the persisted event log). Non-mutating: only an audit record is written.

    Robustness: suppress a lagging/terminal row only when its concrete broker id
    is locally owned, or when an id-less local order has the same client id and
    immutable symbol/side. A foreign identity or scope collision remains surfaced
    evidence; a familiar client id alone never hides it."""

    if not plan.external_orders:
        return

    all_orders = await store.list_orders()
    if scope_by_order is None:
        scope_by_order = await load_venue_order_scopes(store, all_orders)
    known_orders_by_id = {o.id: o for o in all_orders}
    known_orders_by_broker_id = {
        o.broker_order_id: o for o in all_orders if o.broker_order_id is not None
    }
    seen = {
        (e.payload or {}).get("broker_order_id")
        for e in await store.list_events(
            event_type=EventType.RECONCILE_EXTERNAL_ORDER.value
        )
    }
    for x in plan.external_orders:
        if x.broker_order_id in seen:
            continue
        client_match = (
            known_orders_by_id.get(x.client_order_id)
            if x.client_order_id is not None
            else None
        )
        idless_immutable_match = (
            client_match is not None
            and client_match.broker_order_id is None
            and venue_scope_matches_order(
                client_match,
                symbol=x.symbol,
                side=x.side,
                quantity=x.quantity,
                filled_quantity=x.filled_quantity,
                order_type=x.order_type,
                limit_price=x.limit_price,
                time_in_force=x.time_in_force,
                order_class=x.order_class,
                asset_class=x.asset_class,
                quantity_mode=x.quantity_mode,
                extended_hours=x.extended_hours,
                has_legs=x.has_legs,
                position_intent=x.position_intent,
                replaces_broker_order_id=x.replaces_broker_order_id,
                advanced_fields=x.advanced_fields,
                expected_scope=scope_by_order.get(client_match.id),
            )
        )
        broker_match = known_orders_by_broker_id.get(x.broker_order_id)
        exact_broker_scope_match = (
            broker_match is not None
            and (
                x.client_order_id == broker_match.id
                if scope_by_order.get(broker_match.id) is not None
                else x.client_order_id is None or x.client_order_id == broker_match.id
            )
            and venue_scope_matches_order(
                broker_match,
                symbol=x.symbol,
                side=x.side,
                quantity=x.quantity,
                filled_quantity=x.filled_quantity,
                order_type=x.order_type,
                limit_price=x.limit_price,
                time_in_force=x.time_in_force,
                order_class=x.order_class,
                asset_class=x.asset_class,
                quantity_mode=x.quantity_mode,
                extended_hours=x.extended_hours,
                has_legs=x.has_legs,
                position_intent=x.position_intent,
                replaces_broker_order_id=x.replaces_broker_order_id,
                advanced_fields=x.advanced_fields,
                expected_scope=scope_by_order.get(broker_match.id),
            )
        )
        if exact_broker_scope_match or idless_immutable_match:
            # Suppress only an exact local owner. A client-id collision with a
            # foreign broker id or immutable scope remains external evidence.
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
                "quantity": x.quantity,
                "order_type": x.order_type,
                "limit_price": x.limit_price,
                "time_in_force": x.time_in_force,
                "order_class": x.order_class,
                "asset_class": x.asset_class,
                "quantity_mode": x.quantity_mode,
                "extended_hours": x.extended_hours,
                "has_legs": x.has_legs,
                "position_intent": x.position_intent,
                "replaces_broker_order_id": x.replaces_broker_order_id,
                "advanced_fields": list(x.advanced_fields),
            },
        )
        seen.add(x.broker_order_id)


async def _surface_position_mismatches(
    store: StateStore, plan: ReconciliationPlan
) -> None:
    """Surface each broker-vs-local position drift as a durable, deduped
    ``reconcile_position_mismatch`` needs-review record (§7: qty exact, avg-px within
    tolerance). **Position truth is NEVER overwritten here (Rule 7 — only fill events
    change position):** this is an audit-only safeguard that flags the drift for an
    operator and — via ``_has_unresolved_divergence`` — holds trading reduce-only until
    it clears. Deduped by ``(symbol, kind)`` so a persistent drift is recorded once, not
    re-logged every tick; survives restart via the persisted event log.

    Gated behind ``drive_state`` at the call site (loop/startup only): a direct tick
    against an adapter that doesn't mirror positions must not false-positive a mismatch
    on every held local position."""

    if not plan.position_mismatches:
        return

    seen = {
        ((e.payload or {}).get("symbol"), (e.payload or {}).get("kind"))
        for e in await store.list_events(
            event_type=EventType.RECONCILE_POSITION_MISMATCH.value
        )
    }
    for m in plan.position_mismatches:
        if (m.symbol, m.kind) in seen:
            continue
        await store.append_event(
            EventType.RECONCILE_POSITION_MISMATCH.value,
            message=(
                f"position drift {m.symbol} ({m.kind}): "
                f"local qty={m.local_quantity} avg={m.local_avg} vs "
                f"broker qty={m.broker_quantity} avg={m.broker_avg} — "
                f"surfaced for review, position NOT overwritten"
            ),
            symbol=m.symbol,
            payload={
                "symbol": m.symbol,
                "kind": m.kind,
                "local_quantity": m.local_quantity,
                "broker_quantity": m.broker_quantity,
                "local_avg": m.local_avg,
                "broker_avg": m.broker_avg,
            },
        )
        seen.add((m.symbol, m.kind))


# An open order the reconcile may resolve to a terminal when the venue confirms it
# ABSENT. CANCEL_PENDING is excluded (§7 / R4): it is already being wound down and
# the per-order poll (which holds its broker id) owns its resolution — the mass
# report never drives it to a terminal.
_RECONCILE_RESOLVABLE = frozenset({OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED})
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
    orders: list[Order] = []
    for order_id in order_ids:
        order = await store.get_order(order_id)
        if order is not None and order.status in _RECONCILE_RESOLVABLE:
            orders.append(order)
    scope_by_order = await load_venue_order_scopes(store, orders)
    retries = settings.reconcile_open_check_missing_retries
    for order in orders:
        order_id = order.id
        if order is None or order.status not in _RECONCILE_RESOLVABLE:
            # Left CANCEL_PENDING / already terminal / vanished — nothing to resolve.
            continue
        # Each targeted query is one REST call against the §7/§9 budget (E6). When
        # exhausted, STOP querying this cycle and defer the rest to the next tick —
        # an un-queried order is NEVER resolved (never read as absent, §7). The
        # resolvable filter above runs first so a filtered-out order costs no token.
        if budget is not None and not budget.try_consume(utcnow()):
            _log.debug(
                "reconcile: query budget exhausted; deferring remaining not-found"
            )
            return
        try:
            await _resolve_one_not_found(
                store,
                adapter,
                order,
                retries,
                expected_scope=scope_by_order.get(order.id),
                budget=budget,
            )
        except Exception:  # noqa: BLE001 - one order's failure never stops the loop/tick
            _log.exception(
                "reconcile: not-found resolution errored for order %s", order_id
            )


async def _resolve_one_not_found(
    store: StateStore,
    adapter: BrokerAdapter,
    order: Order,
    retries: int,
    *,
    expected_scope: Optional[VenueOrderScope] = None,
    budget: Optional[ReconcileQueryBudget] = None,
) -> None:
    """Run the READ-ONLY targeted query for one order absent from the mass report
    and resolve/defer it (see :func:`_resolve_reconcile_not_found`)."""

    order_id = order.id
    try:
        update = await adapter.get_order_by_client_order_id(
            order_id,
            expected_symbol=order.symbol,
            expected_side=OrderSide(order.side),
            expected_quantity=order.quantity,
            expected_limit_price=(
                None if order_has_dynamic_venue_type(order) else order.limit_price
            ),
            expected_order_type=(
                None
                if order_has_dynamic_venue_type(order)
                else OrderType(order.order_type)
            ),
            expected_time_in_force="day",
            expected_order_class="simple",
            expected_scope=expected_scope,
            allow_dynamic_market_sell=(
                expected_scope is None and order_has_dynamic_venue_type(order)
            ),
        )
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
                store,
                order,
                errors + 1,
                "query_error",
                needs_review=errors + 1 >= retries,
                error=str(exc),
            )
        return

    if update is not None:
        # The venue HAS the order. Adopt its concrete identity if this is a
        # legacy id-less owner, then poll that identity immediately: a targeted
        # lookup carries cumulative state but no priced fill executions, so merely
        # returning here could strand a scalar fill forever.
        broker_order_id = update.broker_order_id
        if not isinstance(broker_order_id, str) or not broker_order_id.strip():
            await _record_reconcile_deferral(
                store,
                order,
                1,
                "present_without_broker_identity",
                needs_review=True,
            )
            return
        broker_order_id = broker_order_id.strip()
        if (
            order.broker_order_id is not None
            and order.broker_order_id != broker_order_id
        ):
            await _record_reconcile_deferral(
                store,
                order,
                1,
                "present_identity_conflict",
                needs_review=True,
                error=(
                    f"local broker id {order.broker_order_id!r} != targeted "
                    f"broker id {broker_order_id!r}"
                ),
            )
            return
        if order.broker_order_id is None:
            order = await store.transition_order(
                order.id,
                order.status,
                broker_order_id=broker_order_id,
                expected_from=order.status,
            )
            if order.broker_order_id != broker_order_id:
                raise RuntimeError("targeted broker identity adoption did not commit")

        # RESET the consecutive not-found streak so the reject bound needs
        # consecutive confirmed absences, not intermittent lifetime observations.
        if await _reconcile_not_found_streak(store, order_id) > 0:
            await _record_reconcile_streak_reset(store, order)
        if budget is not None and not budget.try_consume(utcnow()):
            return
        recorded_raw = sum(
            fill.quantity for fill in await store.list_fills(order_id=order.id)
        )
        try:
            direct = await adapter.get_order_status(
                broker_order_id,
                recorded_quantity=recorded_raw,
                expected_client_order_id=order.id,
                expected_symbol=order.symbol,
                expected_side=OrderSide(order.side),
                expected_quantity=order.quantity,
                expected_limit_price=(
                    None if order_has_dynamic_venue_type(order) else order.limit_price
                ),
                expected_order_type=(
                    None
                    if order_has_dynamic_venue_type(order)
                    else OrderType(order.order_type)
                ),
                expected_time_in_force="day",
                expected_order_class="simple",
                expected_scope=expected_scope,
                allow_dynamic_market_sell=(
                    expected_scope is None and order_has_dynamic_venue_type(order)
                ),
            )
        except BrokerError as exc:
            await _record_reconcile_deferral(
                store,
                order,
                1,
                "present_direct_poll_error",
                needs_review=True,
                error=str(exc),
            )
            return
        await _apply_update(store, order, direct)
        return

    # Confirmed absent. The bound counts CONSECUTIVE confirmed-not-founds (reset by a
    # prior 'present' observation) — and query errors use a SEPARATE counter — so
    # neither a run of query errors nor an intermittently-present venue can erode the
    # venue-lag tolerance and prematurely resolve a possibly-live order.
    attempts = await _reconcile_not_found_streak(store, order_id) + 1
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
                "reconcile: order %s confirmed absent after %s consecutive queries -> %s",
                order_id,
                attempts,
                target.value,
            )
        except _TRANSITION_ERRORS as exc:
            # A fill that raced the resolve makes the transition illegal (e.g. the
            # order FILLED first) — refused under the store lock, never a dropped
            # fill or oversell. Leave it; the next tick re-evaluates.
            _log.warning(
                "reconcile: could not resolve absent order %s to %s: %s",
                order_id,
                target.value,
                exc,
            )
    else:
        await _record_reconcile_deferral(store, order, attempts, "not_found")


async def _reconcile_not_found_streak(store: StateStore, order_id: str) -> int:
    """Consecutive confirmed-not-found count for an order — the trailing run of
    ``not_found`` reconcile deferrals, RESET by any ``cleared_present`` marker (a tick
    whose targeted query found the order present). Consecutive, not lifetime: an
    intermittently-present venue can never sum non-consecutive not-founds toward the
    reject bound (a review-hardening over a plain lifetime count)."""

    streak = 0
    for e in await store.list_events(event_type=_RECONCILE_DEFERRED_EVENT):
        if e.order_id != order_id:
            continue
        reason = (e.payload or {}).get("reason")
        if reason == "not_found":
            streak += 1
        elif reason == "cleared_present":
            streak = 0
    return streak


async def _record_reconcile_streak_reset(store: StateStore, order: Order) -> None:
    """Record a ``cleared_present`` marker (the venue confirmed the order present),
    resetting the consecutive not-found streak. Best-effort."""

    try:
        await store.append_event(
            _RECONCILE_DEFERRED_EVENT,
            message=(
                f"reconcile: {order.symbol} found present at venue — "
                "not-found streak reset"
            ),
            symbol=order.symbol,
            candidate_id=order.candidate_id,
            order_id=order.id,
            payload={"reason": "cleared_present"},
            session_id=order.session_id,
        )
    except Exception:  # noqa: BLE001 - audit is best-effort on a resolution path
        _log.exception("could not record reconcile streak reset for order %s", order.id)


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
        _log.exception("could not record reconcile deferral for order %s", order.id)


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
