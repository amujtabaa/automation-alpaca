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
from datetime import timedelta

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

_log = logging.getLogger(__name__)

# Orders the loop actively tracks toward a terminal state.
_OPEN_STATUSES = frozenset({OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED})

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
            # Submitted at the broker but could not be persisted as SUBMITTED.
            # The real adapter sets a deterministic client_order_id so a retry is
            # rejected as a duplicate rather than double-submitting; we surface
            # this loudly because it should not happen in normal operation.
            _log.error(
                "order %s submitted to broker as %s but could not be marked "
                "SUBMITTED: %s",
                order.id,
                broker_order_id,
                exc,
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

    already_stale = await _orders_with_stale_event(store)
    timeout = timedelta(minutes=settings.unfilled_timeout_minutes)
    now = utcnow()

    for order in open_orders:
        if order.broker_order_id is not None:
            try:
                update = await adapter.get_order_status(order.broker_order_id)
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
        # have moved it to a terminal state, in which case it is no longer stale.
        fresh = await store.get_order(order.id)
        if fresh is None or fresh.status not in _OPEN_STATUSES:
            continue
        if fresh.id in already_stale:
            continue
        age = now - fresh.created_at
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
    """Append the broker's reported fills, then advance the order's status.

    Fills are appended first so the derived position reflects exactly what
    filled; the store dedups by ``source_fill_id`` (a replayed fill is ignored,
    not double-counted) and rejects any fill inconsistent with the order. The
    status/``filled_quantity`` update then runs through ``transition_order``,
    which enforces the legal state machine and monotonic, in-range fill progress
    — so a glitchy broker value is rejected and logged, never allowed to corrupt
    the order.
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

    try:
        await store.transition_order(
            order.id, update.status, filled_quantity=update.filled_quantity
        )
    except _TRANSITION_ERRORS as exc:
        _log.warning(
            "order %s update to %s (filled=%s) rejected: %s",
            order.id,
            update.status,
            update.filled_quantity,
            exc,
        )


async def _orders_with_stale_event(store: StateStore) -> set[str]:
    """Order ids that already carry an ``order_stale`` event.

    Reads the persisted event log so the "flag stale once" guarantee survives a
    process restart. Acceptable at beta's single-user scale; an indexed query is
    the upgrade if the event log ever grows large.
    """

    return {
        e.order_id
        for e in await store.list_events()
        if e.event_type == EventType.ORDER_STALE.value and e.order_id is not None
    }
