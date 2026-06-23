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

from app.broker.adapter import BrokerAdapter, BrokerOrderUpdate
from app.config import Settings
from app.models import EventType, Order, OrderStatus, utcnow
from app.position import NegativePositionError
from app.store.base import (
    InvalidFillError,
    InvalidOrderError,
    OrderTransitionError,
    StateStore,
    UnknownEntityError,
)
from app.store.validation import order_intent_block_reason

_log = logging.getLogger(__name__)

# Orders the loop actively polls toward a terminal state. Includes cancel_pending
# so a late fill arriving before the broker confirms a cancel is still reconciled
# (CHAOS-1).
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


async def monitoring_loop(
    store: StateStore, adapter: BrokerAdapter, settings: Settings
) -> None:
    """Run forever: sleep one cadence, then run a tick. Never crashes.

    Sleeps *before* the first tick so app startup is not blocked and an injected
    store in a short-lived test (which is torn down well within one cadence)
    never reaches the tick body.
    """

    _log.info(
        "monitoring loop started (cadence=%.3fs, unfilled_timeout=%.1fmin)",
        settings.poll_cadence_seconds,
        settings.unfilled_timeout_minutes,
    )
    while True:
        try:
            await asyncio.sleep(settings.poll_cadence_seconds)
            await run_monitoring_tick(store, adapter, settings)
        except asyncio.CancelledError:
            _log.info("monitoring loop cancelled; shutting down")
            raise
        except Exception:  # noqa: BLE001 - a tick failure must not stop the loop
            _log.exception("monitoring tick failed; continuing on next cadence")


async def run_monitoring_tick(
    store: StateStore, adapter: BrokerAdapter, settings: Settings
) -> None:
    """One monitoring iteration: submit pending orders, then reconcile open ones.

    Exposed separately from :func:`monitoring_loop` so tests drive a single,
    deterministic tick without the sleep/``while True`` wrapper.
    """

    await _submit_pending_orders(store, adapter)
    await _reconcile_open_orders(store, adapter, settings)


async def _submit_pending_orders(store: StateStore, adapter: BrokerAdapter) -> None:
    """Submit every ``CREATED`` order to the broker and mark it ``SUBMITTED``.

    A submission failure leaves the order at ``CREATED`` to be retried on the
    next tick (no state change). The broker id returned by ``submit_order`` is
    persisted so the order can be polled and cancelled.
    """

    created = [o for o in await store.list_orders() if o.status is OrderStatus.CREATED]
    if not created:
        return

    # Safety controls (Rule 8): hold ALL submissions while the kill switch is
    # engaged / buys are paused. Re-checked here — not only at order creation —
    # so an order created *before* the stop cannot race through to the broker
    # after the user hits stop. Each held order is audited once (not per tick).
    block = order_intent_block_reason(await store.get_current_session())
    if block is not None:
        blocked_already = await _orders_with_event(
            store, EventType.ORDER_SUBMISSION_BLOCKED.value
        )
        for order in created:
            if order.id in blocked_already:
                continue
            await store.append_event(
                EventType.ORDER_SUBMISSION_BLOCKED.value,
                message=f"submission of {order.symbol} held: {block}",
                symbol=order.symbol,
                candidate_id=order.candidate_id,
                order_id=order.id,
                payload={"reason": block},
                session_id=order.session_id,
            )
        return

    for order in created:
        try:
            broker_order_id = await adapter.submit_order(order)
        except Exception as exc:  # noqa: BLE001 - retry next tick, never crash
            _log.warning(
                "submit failed for order %s (%s); leaving CREATED to retry: %s",
                order.id,
                order.symbol,
                exc,
            )
            continue
        try:
            await store.transition_order(
                order.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
            )
        except _TRANSITION_ERRORS as exc:
            # Submitted at the broker but could not be marked SUBMITTED (most
            # often a concurrent manual cancel landing during the submit call).
            # The real adapter's client_order_id makes a retry idempotent rather
            # than double-submitting; here we make the live broker order visible
            # and clean it up if it was cancelled.
            await _handle_unpersisted_submit(
                store, adapter, order, broker_order_id, exc
            )


async def _handle_unpersisted_submit(
    store: StateStore,
    adapter: BrokerAdapter,
    order: Order,
    broker_order_id: str,
    exc: Exception,
) -> None:
    """The broker accepted an order we then couldn't mark ``SUBMITTED``.

    The order is live at the broker but the DB didn't capture it. This must
    never be left silent (it is a real open position), so:

    1. record an ``order_submit_unpersisted`` audit event, and
    2. if the order is now ``CANCELED`` locally (a manual cancel raced the
       submit), best-effort cancel it at the broker so a user-cancelled order
       isn't left working upstream.

    Every step is best-effort and swallows its own errors — this runs on a
    failure path and must not crash the loop.
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
    if current is not None and current.status is OrderStatus.CANCELED:
        try:
            await adapter.cancel_order(broker_order_id)
            _log.info(
                "cleaned up stranded broker order %s (order %s was cancelled "
                "during submit)",
                broker_order_id,
                order.id,
            )
        except Exception as cancel_exc:  # noqa: BLE001
            _log.error(
                "failed to clean up stranded broker order %s: %s",
                broker_order_id,
                cancel_exc,
            )


async def _reconcile_open_orders(
    store: StateStore, adapter: BrokerAdapter, settings: Settings
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
            try:
                # Pass what we've already recorded so an adapter that only sees
                # the broker's cumulative fill can emit a correct delta.
                update = await adapter.get_order_status(
                    order.broker_order_id, recorded_quantity=order.filled_quantity
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
    """

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

    recorded = sum(f.quantity for f in await store.list_fills(order_id=order.id))
    if update.filled_quantity != recorded:
        # Surface a divergence rather than trusting the broker scalar over the
        # fills we could actually record (e.g. a fill the store rejected).
        _log.warning(
            "order %s: broker reports filled=%s but recorded fills sum to %s; "
            "reconciling order to recorded.",
            order.id,
            update.filled_quantity,
            recorded,
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
