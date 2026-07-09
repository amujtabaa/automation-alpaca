"""WO-0007b Stage D — the read-flip: orders.status is now event_truth.

get_order/list_orders derive status + filled_quantity from project_order_status over
the ExecutionEvent log (mirroring how position derives from FILL events). The
orders.status/filled_quantity columns are co-written read-models. These tests prove
the flip: a hand-corrupted column does NOT surface — reads return the event-derived value.
"""

from __future__ import annotations

import pytest

from app.models import OrderSide, OrderStatus
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


async def _submitted(store, qty=10):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    order = await store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, qty, session_id=sess.id)
    await store.claim_order_for_submission(order.id)
    await store.transition_order(order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1")
    return order


async def test_memory_get_order_derives_status_from_log_not_column():
    store = InMemoryStateStore()
    order = await _submitted(store)
    # Corrupt the co-written STATUS column directly, bypassing the write path.
    # (filled_quantity stays column-sourced by design — see _project_order_unlocked.)
    store._orders[order.id].status = OrderStatus.CREATED

    got = await store.get_order(order.id)
    assert got is not None
    assert got.status is OrderStatus.SUBMITTED  # event-derived, ignores the column
    # list_orders reflects the projection too.
    listed = {o.id: o for o in await store.list_orders()}
    assert listed[order.id].status is OrderStatus.SUBMITTED


async def test_sqlite_get_order_derives_status_from_log_not_column(tmp_path):
    store = SqliteStateStore(tmp_path / "flip.db")
    try:
        order = await _submitted(store)
        # Corrupt the STATUS column directly (raw UPDATE, bypassing the write path).
        assert store._conn is not None
        store._conn.execute(
            "UPDATE orders SET status = 'created' WHERE id = ?", (order.id,)
        )
        store._conn.commit()

        got = await store.get_order(order.id)
        assert got is not None
        assert got.status is OrderStatus.SUBMITTED
        listed = {o.id: o for o in await store.list_orders()}
        assert listed[order.id].status is OrderStatus.SUBMITTED
    finally:
        await store.close()


async def test_flip_status_matches_projection_through_full_lifecycle(any_store):
    # After the flip, get_order's status equals project_order_status at every step —
    # already proven pointwise in Stage C1; here as an end-to-end sanity on the flipped read.
    await any_store.initialize()
    sess = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=sess.id)
    order = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 10, session_id=sess.id)

    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED
    await any_store.claim_order_for_submission(order.id)
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING
    await any_store.transition_order(order.id, OrderStatus.CREATED)  # release
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1")
    await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCEL_PENDING
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCELED
