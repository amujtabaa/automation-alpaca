"""D-008: order-transition audit events must not fire on true no-ops, but a
fill-progress (filled_quantity change without a status change) is still recorded.

Parametrized over both stores to prove identical behavior.
"""

from __future__ import annotations

import pytest

from app.models import OrderSide, OrderStatus
from tests.store_helpers import submit_created_order

pytestmark = pytest.mark.anyio


async def _new_order(store):
    await store.initialize()
    candidate = await store.create_candidate("AAPL")
    return await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 100)


def _order_audit(events, order_id):
    return [
        e
        for e in events
        if e.order_id == order_id
        and e.event_type in ("order_transition", "order_fill_progress")
    ]


async def test_noop_transition_writes_zero_events(any_store):
    order = await _new_order(any_store)
    # Reach a submitted order the sanctioned way (claim -> SUBMITTED, AIR-007).
    await submit_created_order(any_store, order.id)
    before = len(await any_store.list_events())

    # Same status, nothing else changed -> true no-op.
    result = await any_store.transition_order(order.id, OrderStatus.SUBMITTED)

    assert len(await any_store.list_events()) == before
    assert result.status is OrderStatus.SUBMITTED


async def test_filled_quantity_change_writes_one_progress_event(any_store):
    order = await _new_order(any_store)
    await submit_created_order(any_store, order.id)
    await any_store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=40
    )
    n_before = len(await any_store.list_events())

    # Same status (partially_filled), but more has filled: 40 -> 70.
    updated = await any_store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=70
    )
    assert updated.filled_quantity == 70

    new_events = (await any_store.list_events())[n_before:]
    progress = [e for e in new_events if e.event_type == "order_fill_progress"]
    assert len(progress) == 1
    assert progress[0].payload["previous_filled_quantity"] == 40
    assert progress[0].payload["filled_quantity"] == 70
    # It was NOT logged as a generic same-status transition.
    assert not [e for e in new_events if e.event_type == "order_transition"]


async def test_genuine_transition_still_writes_one_transition_event(any_store):
    order = await _new_order(any_store)
    # The claim (CREATED -> SUBMITTING) is audited as order_submission_claimed,
    # not order_transition; the genuine order_transition here is the subsequent
    # SUBMITTING -> SUBMITTED (which now requires a real broker id, AIR-001).
    await any_store.claim_order_for_submission(order.id)
    n_before = len(await any_store.list_events())

    await any_store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="bk-1"
    )

    new_events = (await any_store.list_events())[n_before:]
    transitions = [e for e in new_events if e.event_type == "order_transition"]
    assert len(transitions) == 1
    assert transitions[0].payload == {"from": "submitting", "to": "submitted"}
