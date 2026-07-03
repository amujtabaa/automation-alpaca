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
from typing import Optional

from app.broker.adapter import BrokerAdapter, BrokerOrderUpdate
from app.config import Settings
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_RESOLVED,
    RECOVERY_UNRESOLVED,
    EventType,
    Order,
    OrderStatus,
    SessionStatus,
    utcnow,
)
from app.position import NegativePositionError
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
    await _recover_unpersisted_submits(store, adapter)


async def _submit_pending_orders(store: StateStore, adapter: BrokerAdapter) -> None:
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
        try:
            broker_order_id = await adapter.submit_order(claimed)
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
            own_session = await store.get_session_by_id(claimed.session_id)
            release_target = (
                OrderStatus.CANCELED
                if own_session is not None
                and own_session.status is SessionStatus.CLOSED
                else OrderStatus.CREATED
            )
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
