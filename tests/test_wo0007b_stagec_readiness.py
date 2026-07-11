"""WO-0007b Stage C1 — readiness proof (the flip is provably sound, WITHOUT flipping).

Proves Migration-rule point 2 (replay reproduces the live projection) for order status:
`project_order_status(store.get_execution_events(), order.id)` reconstructs the live
`orders.status` column — across every lifecycle, INCLUDING the two intermediates a
max-status-reached fold gets wrong (released -> CREATED; live CANCEL_PENDING) — in BOTH
stores, plus the event-truth proof (a status event with no `orders` row moves the projection).

Stage D (the actual read-flip: make get_order derive status from this projection + init
backfill/heal + matrix-terminal) is HUMAN-GATED and NOT done here.
"""

from __future__ import annotations

import pytest

from app.events.projectors import project_order_status
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


async def _new_order(store, symbol="AAPL", qty=10):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=sess.id)
    return await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=sess.id
    )


async def _project_status(store, order):
    events = await store.get_execution_events()
    return project_order_status(events, order.id, quantity=order.quantity)


async def _assert_matches(store, order):
    row = await store.get_order(order.id)
    proj = await _project_status(store, order)
    assert proj.status is row.status, (
        f"projection {proj.status} != column {row.status} for order {order.id}"
    )
    return proj, row


# --------------------------------------------------------------------------- #
# projection == live column, every lifecycle, both stores
# --------------------------------------------------------------------------- #
async def test_projection_matches_column_created(any_store):
    order = await _new_order(any_store)
    await _assert_matches(any_store, order)  # no lifecycle events yet -> CREATED


async def test_projection_matches_column_submitting(any_store):
    order = await _new_order(any_store)
    await any_store.claim_order_for_submission(order.id)
    proj, row = await _assert_matches(any_store, order)
    assert proj.status is OrderStatus.SUBMITTING


async def test_projection_matches_column_released_to_created(any_store):
    # The cycle: claim then release. The column is CREATED (re-claimable); the
    # projection must ALSO be CREATED (latest event SUBMIT_RELEASED), not SUBMITTING.
    order = await _new_order(any_store)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(order.id, OrderStatus.CREATED)
    proj, row = await _assert_matches(any_store, order)
    assert proj.status is OrderStatus.CREATED


async def test_projection_matches_column_live_cancel_pending(any_store):
    # The live pending-cancel: SUBMITTED -> CANCEL_PENDING (not yet CANCELED).
    order = await _new_order(any_store)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
    )
    await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
    proj, row = await _assert_matches(any_store, order)
    assert proj.status is OrderStatus.CANCEL_PENDING


async def test_projection_matches_column_filled_with_quantity(any_store):
    order = await _new_order(any_store, qty=10)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
    )
    await any_store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 4, 10.0, session_id=order.session_id
    )
    await any_store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=4
    )
    await any_store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 6, 10.0, session_id=order.session_id
    )
    await any_store.transition_order(order.id, OrderStatus.FILLED, filled_quantity=10)

    proj, row = await _assert_matches(any_store, order)
    assert proj.status is OrderStatus.FILLED
    # filled_quantity reconstructs from the FILL events and matches the column.
    assert proj.filled_quantity == row.filled_quantity == 10


async def test_projection_matches_column_canceled_via_cancel_pending(any_store):
    order = await _new_order(any_store)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
    )
    await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    proj, row = await _assert_matches(any_store, order)
    assert proj.status is OrderStatus.CANCELED


async def test_projection_matches_column_rejected(any_store):
    order = await _new_order(any_store)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(order.id, OrderStatus.REJECTED)
    proj, row = await _assert_matches(any_store, order)
    assert proj.status is OrderStatus.REJECTED


async def test_projection_matches_column_never_submitted_cancel(any_store):
    order = await _new_order(any_store)
    await any_store.transition_order(
        order.id, OrderStatus.CANCELED
    )  # CREATED -> CANCELED
    proj, row = await _assert_matches(any_store, order)
    assert proj.status is OrderStatus.CANCELED


# --------------------------------------------------------------------------- #
# Event-truth proof — a status event with NO orders row moves the projection.
# --------------------------------------------------------------------------- #
async def test_status_projects_from_log_without_an_orders_row(any_store):
    await any_store.initialize()
    oid = "ghost-order-1"

    def _ev(et, seq):
        return ExecutionEvent(
            sequence=seq,
            event_type=et,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key=f"{et.value}:{oid}",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_id=oid,
        )

    # No create_order — only events, appended straight to the log.
    await any_store.append_execution_event(_ev(ExecutionEventType.SUBMITTED, 0))
    await any_store.append_execution_event(_ev(ExecutionEventType.FILLED, 0))

    events = await any_store.get_execution_events()
    proj = project_order_status(events, oid)
    assert proj.status is OrderStatus.FILLED
    assert await any_store.get_order(oid) is None  # truly no row


# --------------------------------------------------------------------------- #
# Dual-store: the projected status stream reconstructs identically.
# --------------------------------------------------------------------------- #
async def test_dual_store_projection_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007b_c.db")
    try:
        results = {}
        for name, store in (("memory", memory), ("sqlite", sqlite)):
            order = await _new_order(store)
            await store.claim_order_for_submission(order.id)
            await store.transition_order(order.id, OrderStatus.CREATED)  # release
            await store.claim_order_for_submission(order.id)
            await store.transition_order(
                order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
            )
            await store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
            proj = project_order_status(
                await store.get_execution_events(), order.id, order.quantity
            )
            results[name] = (proj.status, proj.filled_quantity)
        assert results["memory"] == results["sqlite"] == (OrderStatus.CANCEL_PENDING, 0)
    finally:
        await sqlite.close()
