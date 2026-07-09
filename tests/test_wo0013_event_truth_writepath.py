"""WO-0013 — complete the event-truth flip on the order-status WRITE path.

REV-0001 (independent review) confirmed two P0 gaps left by the WO-0007b Stage D
read-flip, which only redirected the READ surface (get_order/list_orders):

- **F-001** — ``claim_order_for_submission`` (the double-submit gate) still read the
  raw ``orders.status`` column, not the event-log projection. A column that drifts to
  ``CREATED`` while the log says ``SUBMITTED`` would let an already-submitted order be
  re-claimed and re-sent. The gate must derive status from the log under the same lock.
- **F-002** — the init backfill keyed on ``projected.status is CREATED``, which is ALSO
  true for a legitimately released order (``SUBMIT_PENDING -> SUBMIT_RELEASED`` projects
  ``CREATED`` while holding lifecycle events). Such an order was wrongly re-backfilled,
  stacking a synthetic terminal event over a real lifecycle stream. The predicate must
  key on the ABSENCE of status-lifecycle events (a FILL is a position fact, never a
  status event), not on the projected value.

These are dual-store (memory + sqlite) parity properties; the corruption technique
(writing the co-written column directly, bypassing the atomic write path) mirrors
tests/test_wo0007b_staged_readflip.py.
"""

from __future__ import annotations

import pytest

from app.events.projectors import project_order_status
from app.models import ExecutionEventType, OrderSide, OrderStatus
from app.store.base import CLAIM_CLAIMED, CLAIM_SKIPPED
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


def _corrupt_status_column(store, order_id: str, status: OrderStatus) -> None:
    """Force the co-written ``orders.status`` column to ``status``, bypassing the
    atomic write path (which would co-append a lifecycle event). Simulates the
    column drifting away from the event-log truth — the exact hazard REV-0001 raised."""
    if isinstance(store, InMemoryStateStore):
        store._orders[order_id].status = status
    else:  # SqliteStateStore
        assert store._conn is not None
        store._conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?", (status.value, order_id)
        )
        store._conn.commit()


async def _created_order(store, symbol="AAPL", qty=10):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=sess.id)
    return await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=sess.id
    )


async def _submit_pending_count(store, order_id: str) -> int:
    return len(
        [
            e
            for e in await store.get_execution_events()
            if e.order_id == order_id
            and e.event_type is ExecutionEventType.SUBMIT_PENDING
        ]
    )


# --------------------------------------------------------------------------- #
# F-001 — the double-submit claim gate must read the projection, not the column.
# --------------------------------------------------------------------------- #
async def test_claim_refuses_stale_created_column_when_log_says_submitted(any_store):
    """A submitted order whose column is corrupted back to CREATED must NOT be
    re-claimable — the claim gate reads the event-log projection (SUBMITTED)."""
    order = await _created_order(any_store)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
    )
    before = await _submit_pending_count(any_store, order.id)

    # The column drifts back to CREATED while the log still says SUBMITTED.
    _corrupt_status_column(any_store, order.id, OrderStatus.CREATED)
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED

    claim = await any_store.claim_order_for_submission(order.id)

    # Event-truth: the projection says SUBMITTED, so the order is no longer claimable.
    assert claim.outcome == CLAIM_SKIPPED
    # And no second SUBMIT_PENDING was appended (no blind re-submit path opened).
    assert await _submit_pending_count(any_store, order.id) == before


async def test_claim_still_claims_a_genuinely_created_order(any_store):
    """Guard: the fix must not over-refuse — a truly CREATED order still claims."""
    order = await _created_order(any_store)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING


async def test_claim_fails_loud_on_column_drift_without_lifecycle_events(any_store):
    """Defense-in-depth: a non-CREATED column with ZERO lifecycle events violates the
    co-write invariant the projection-gate depends on (unreachable in normal operation
    — every writer co-appends an event and init backfill heals migration). Rather than
    silently blind-resubmit, the claim gate fails LOUD."""
    order = await _created_order(any_store)
    # Inject the invariant violation directly: column past CREATED, but no events.
    _corrupt_status_column(any_store, order.id, OrderStatus.SUBMITTED)
    with pytest.raises(AssertionError):
        await any_store.claim_order_for_submission(order.id)


# --------------------------------------------------------------------------- #
# F-002 — the backfill must key on status-lifecycle-event ABSENCE, not projected==CREATED.
# --------------------------------------------------------------------------- #
async def test_backfill_does_not_reconstruct_a_released_cycle_order(any_store):
    """A released order (SUBMIT_PENDING -> SUBMIT_RELEASED) projects CREATED but HAS
    lifecycle events. A stale terminal column must NOT trigger a synthetic backfill
    event that would clobber the real lifecycle stream (the F-002 P0)."""
    order = await _created_order(any_store)
    await any_store.claim_order_for_submission(order.id)  # SUBMIT_PENDING
    await any_store.transition_order(
        order.id, OrderStatus.CREATED
    )  # release -> SUBMIT_RELEASED
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED

    # Corrupt the column to a terminal status, then re-run the init backfill.
    _corrupt_status_column(any_store, order.id, OrderStatus.FILLED)
    await any_store.initialize()

    # The order already has lifecycle events, so NO synthetic backfill event fires,
    # and the projection stays CREATED (event truth), not the stale FILLED column.
    bf = [
        e
        for e in await any_store.get_execution_events()
        if e.dedupe_key == f"backfill_status:{order.id}"
    ]
    assert bf == []
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED


async def test_backfill_still_reconstructs_a_filled_order_with_fill_events(any_store):
    """Guard (pre-mortem): a pre-eventing FILLED order carries FILL events (from the
    fill backfill) but NO status-lifecycle event. A FILL is not a status event, so the
    absence check must still treat this order as un-evented and reconstruct FILLED —
    the predicate must EXCLUDE FILL, not skip on 'has any events'."""
    order = await _created_order(any_store)
    # A fill records a FILL execution event but no order-status lifecycle event.
    await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, 10, 10.0)
    # Precondition: fills do not move the projected order status.
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED

    # Simulate the pre-eventing filled column, then re-run the backfill.
    _corrupt_status_column(any_store, order.id, OrderStatus.FILLED)
    await any_store.initialize()

    assert (await any_store.get_order(order.id)).status is OrderStatus.FILLED
    bf = [
        e
        for e in await any_store.get_execution_events()
        if e.dedupe_key == f"backfill_status:{order.id}"
    ]
    assert len(bf) == 1


async def test_backfill_is_idempotent_for_released_cycle_on_reinit(any_store):
    """Re-running init on a released-cycle order never accumulates backfill events."""
    order = await _created_order(any_store)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(order.id, OrderStatus.CREATED)  # release
    _corrupt_status_column(any_store, order.id, OrderStatus.FILLED)

    await any_store.initialize()
    await any_store.initialize()

    bf = [
        e
        for e in await any_store.get_execution_events()
        if e.dedupe_key == f"backfill_status:{order.id}"
    ]
    assert bf == []
    # The full projection is unchanged by the double init.
    assert (
        project_order_status(await any_store.get_execution_events(), order.id).status
        is OrderStatus.CREATED
    )
