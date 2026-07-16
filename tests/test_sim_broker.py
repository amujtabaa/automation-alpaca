"""``SimBrokerAdapter`` unit tests — Wave 1 Part A.

IO-free (Rule 9): everything is driven directly against the adapter, no
StateStore, no network, no SDK. Each capability from the docstring in
``app/broker/sim.py`` gets a focused test, plus a couple of "inherited
MockBrokerAdapter behavior still works" checks since SimBrokerAdapter extends
it rather than replacing it.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerError, BrokerFill, BrokerOrderUpdate
from app.broker.sim import SimBrokerAdapter
from app.models import Order, OrderSide, OrderStatus, utcnow

pytestmark = pytest.mark.anyio


def _order(**kw) -> Order:
    defaults = dict(
        candidate_id="c1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        limit_price=2.0,
    )
    defaults.update(kw)
    return Order(**defaults)


# --------------------------------------------------------------------------- #
# Inherited MockBrokerAdapter behavior still works
# --------------------------------------------------------------------------- #
async def test_inherited_submit_and_default_status():
    adapter = SimBrokerAdapter()
    order = _order()

    broker_id = await adapter.submit_order(order)

    assert broker_id == f"broker-{order.id}"
    assert adapter.submitted == [order]
    assert adapter.broker_id_for(order.id) == broker_id

    update = await adapter.get_order_status(broker_id)
    assert update.status is OrderStatus.SUBMITTED
    assert update.filled_quantity == 0
    assert adapter.status_queries == [broker_id]


async def test_inherited_cancel_and_fail_next_helpers():
    adapter = SimBrokerAdapter()
    order = _order()
    broker_id = await adapter.submit_order(order)

    await adapter.cancel_order(broker_id)
    assert adapter.canceled == [broker_id]
    update = await adapter.get_order_status(broker_id)
    assert update.status is OrderStatus.CANCELED

    order2 = _order()
    adapter.fail_next_submit(BrokerError("down"))
    with pytest.raises(BrokerError):
        await adapter.submit_order(order2)
    # Recorded the attempt but minted no id.
    assert order2 in adapter.submitted
    with pytest.raises(KeyError):
        adapter.broker_id_for(order2.id)


# --------------------------------------------------------------------------- #
# 1. Accept-then-signal hook
# --------------------------------------------------------------------------- #
async def test_on_submit_hook_fires_mid_submit_with_id_already_live():
    adapter = SimBrokerAdapter()
    order = _order()
    captured = {}

    async def hook(hooked_order, broker_order_id):
        captured["order"] = hooked_order
        captured["broker_order_id"] = broker_order_id
        # The whole point: the id is already live from inside the hook.
        captured["was_live"] = adapter.is_live(broker_order_id)
        captured["broker_id_for_matches"] = (
            adapter.broker_id_for(hooked_order.id) == broker_order_id
        )

    adapter.set_on_submit(hook)
    broker_id = await adapter.submit_order(order)

    assert captured["order"] is order
    assert captured["broker_order_id"] == broker_id
    assert captured["was_live"] is True
    assert captured["broker_id_for_matches"] is True


async def test_on_submit_hook_does_not_fire_on_failed_submit():
    adapter = SimBrokerAdapter()
    order = _order()
    calls = []

    async def hook(hooked_order, broker_order_id):
        calls.append((hooked_order, broker_order_id))

    adapter.set_on_submit(hook)
    adapter.fail_next_submit(BrokerError("down"))

    with pytest.raises(BrokerError):
        await adapter.submit_order(order)

    assert calls == []


async def test_on_submit_hook_cleared_with_none():
    adapter = SimBrokerAdapter()
    calls = []

    async def hook(hooked_order, broker_order_id):
        calls.append(broker_order_id)

    adapter.set_on_submit(hook)
    adapter.set_on_submit(None)
    await adapter.submit_order(_order())

    assert calls == []


# --------------------------------------------------------------------------- #
# 2. Reject/raise at a point
# --------------------------------------------------------------------------- #
async def test_fail_submit_when_matches_call_index():
    adapter = SimBrokerAdapter()
    seen_indices = []

    def predicate(order, call_index):
        seen_indices.append(call_index)
        return call_index == 1  # fail only the second call

    adapter.fail_submit_when(predicate)

    # Call 0: succeeds.
    order0 = _order()
    broker_id0 = await adapter.submit_order(order0)
    assert broker_id0 == f"broker-{order0.id}"

    # Call 1: predicate fires -> generic BrokerError, no id minted.
    order1 = _order()
    with pytest.raises(BrokerError):
        await adapter.submit_order(order1)
    assert order1 in adapter.submitted
    with pytest.raises(KeyError):
        adapter.broker_id_for(order1.id)

    # Call 2: back to succeeding.
    order2 = _order()
    broker_id2 = await adapter.submit_order(order2)
    assert broker_id2 == f"broker-{order2.id}"

    assert seen_indices == [0, 1, 2]


async def test_fail_submit_when_raises_the_given_exception_instance():
    adapter = SimBrokerAdapter()
    boom = ValueError("custom failure")
    adapter.fail_submit_when(lambda order, call_index: boom)

    with pytest.raises(ValueError) as exc_info:
        await adapter.submit_order(_order())
    assert exc_info.value is boom


async def test_fail_cancel_when_matches_call_index():
    adapter = SimBrokerAdapter()
    order = _order()
    broker_id = await adapter.submit_order(order)

    adapter.fail_cancel_when(lambda broker_order_id, call_index: call_index == 0)

    with pytest.raises(BrokerError):
        await adapter.cancel_order(broker_id)
    assert adapter.canceled == [broker_id]
    # The order is still live: the cancel never actually took effect.
    assert adapter.is_live(broker_id) is True

    # Second attempt (call_index 1) is not matched by the predicate -> succeeds.
    await adapter.cancel_order(broker_id)
    assert adapter.canceled == [broker_id, broker_id]
    assert adapter.is_live(broker_id) is False


# --------------------------------------------------------------------------- #
# 3. Scripted lifecycles
# --------------------------------------------------------------------------- #
async def test_script_drives_submitted_partial_filled_and_sticks_at_terminal():
    adapter = SimBrokerAdapter()
    order = _order(quantity=100)
    broker_id = await adapter.submit_order(order)

    fill1 = BrokerFill("exec-1", 40, 2.0, utcnow())
    fill2 = BrokerFill("exec-2", 60, 2.0, utcnow())
    adapter.script(
        order.id,
        [
            BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 40, [fill1]),
            BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 40, [fill1]),
            BrokerOrderUpdate(OrderStatus.FILLED, 100, [fill1, fill2]),
        ],
    )

    u1 = await adapter.get_order_status(broker_id)
    assert u1.status is OrderStatus.PARTIALLY_FILLED
    assert u1.filled_quantity == 40

    u2 = await adapter.get_order_status(broker_id)
    assert u2.status is OrderStatus.PARTIALLY_FILLED

    u3 = await adapter.get_order_status(broker_id)
    assert u3.status is OrderStatus.FILLED
    assert u3.filled_quantity == 100

    # Exhausted: the terminal update keeps being returned.
    u4 = await adapter.get_order_status(broker_id)
    u5 = await adapter.get_order_status(broker_id)
    assert u4.status is OrderStatus.FILLED
    assert u5.status is OrderStatus.FILLED
    assert adapter.status_queries == [broker_id] * 5
    assert adapter.is_live(broker_id) is False


async def test_script_can_be_set_before_submit_by_order_id():
    adapter = SimBrokerAdapter()
    order = _order()

    adapter.script(order.id, [BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, [])])
    broker_id = await adapter.submit_order(order)

    update = await adapter.get_order_status(broker_id)
    assert update.status is OrderStatus.SUBMITTED


async def test_script_duplicate_source_fill_id():
    adapter = SimBrokerAdapter()
    order = _order(quantity=50)
    broker_id = await adapter.submit_order(order)

    dup_fill = BrokerFill("exec-dup", 50, 2.0, utcnow())
    adapter.script(
        order.id,
        [
            BrokerOrderUpdate(OrderStatus.FILLED, 50, [dup_fill]),
            BrokerOrderUpdate(OrderStatus.FILLED, 50, [dup_fill]),
        ],
    )

    u1 = await adapter.get_order_status(broker_id)
    u2 = await adapter.get_order_status(broker_id)
    assert u1.fills[0].source_fill_id == "exec-dup"
    assert u2.fills[0].source_fill_id == "exec-dup"
    # Same source_fill_id on both polls -- it's on the store's dedup (D-006)
    # to collapse these; the adapter just faithfully replays what "the
    # broker" reported.
    assert u1.fills[0] is dup_fill
    assert u2.fills[0] is dup_fill


async def test_script_late_fill_after_cancel_pending_chaos_1():
    adapter = SimBrokerAdapter()
    order = _order(quantity=25)
    broker_id = await adapter.submit_order(order)

    late_fill = BrokerFill("exec-late", 25, 2.0, utcnow())
    adapter.script(
        order.id,
        [
            BrokerOrderUpdate(OrderStatus.CANCEL_PENDING, 0, []),
            BrokerOrderUpdate(OrderStatus.FILLED, 25, [late_fill]),
        ],
    )

    u1 = await adapter.get_order_status(broker_id)
    assert u1.status is OrderStatus.CANCEL_PENDING
    assert adapter.is_live(broker_id) is True  # cancel_pending is non-terminal

    u2 = await adapter.get_order_status(broker_id)
    assert u2.status is OrderStatus.FILLED
    assert u2.fills == [late_fill]
    assert adapter.is_live(broker_id) is False


# --------------------------------------------------------------------------- #
# 4. Disconnect / delay window
# --------------------------------------------------------------------------- #
async def test_disconnect_status_for_raises_then_recovers():
    adapter = SimBrokerAdapter()
    order = _order()
    broker_id = await adapter.submit_order(order)

    adapter.disconnect_status_for(2)

    with pytest.raises(BrokerError):
        await adapter.get_order_status(broker_id)
    with pytest.raises(BrokerError):
        await adapter.get_order_status(broker_id)

    # Third call recovers, back to the default response.
    update = await adapter.get_order_status(broker_id)
    assert update.status is OrderStatus.SUBMITTED
    # Every attempt, including the raising ones, was recorded.
    assert adapter.status_queries == [broker_id] * 3


async def test_disconnect_status_takes_precedence_over_a_script():
    adapter = SimBrokerAdapter()
    order = _order()
    broker_id = await adapter.submit_order(order)
    adapter.script(order.id, [BrokerOrderUpdate(OrderStatus.FILLED, 10, [])])
    adapter.disconnect_status_for(1)

    with pytest.raises(BrokerError):
        await adapter.get_order_status(broker_id)

    # The script is untouched -- the disconnected call didn't consume it.
    update = await adapter.get_order_status(broker_id)
    assert update.status is OrderStatus.FILLED


# --------------------------------------------------------------------------- #
# 5. Liveness introspection
# --------------------------------------------------------------------------- #
async def test_is_live_true_while_open_false_after_cancel():
    adapter = SimBrokerAdapter()
    order = _order()
    broker_id = await adapter.submit_order(order)

    assert adapter.is_live(broker_id) is True
    await adapter.cancel_order(broker_id)
    assert adapter.is_live(broker_id) is False


async def test_is_live_false_after_terminal_script_update():
    adapter = SimBrokerAdapter()
    order = _order()
    broker_id = await adapter.submit_order(order)
    adapter.script(order.id, [BrokerOrderUpdate(OrderStatus.FILLED, 10, [])])

    # Not consumed yet -- falls back to the submitted-but-unpolled default.
    assert adapter.is_live(broker_id) is True

    await adapter.get_order_status(broker_id)
    assert adapter.is_live(broker_id) is False


async def test_is_live_false_for_never_submitted_id():
    adapter = SimBrokerAdapter()
    assert adapter.is_live("broker-never-submitted") is False


async def test_cancel_makes_scripted_order_not_live_and_keeps_prior_fills():
    adapter = SimBrokerAdapter()
    order = _order(quantity=40)
    broker_id = await adapter.submit_order(order)

    fill = BrokerFill("exec-1", 15, 2.0, utcnow())
    adapter.script(
        order.id, [BrokerOrderUpdate(OrderStatus.PARTIALLY_FILLED, 15, [fill])]
    )
    await adapter.get_order_status(broker_id)
    assert adapter.is_live(broker_id) is True

    await adapter.cancel_order(broker_id)

    assert adapter.is_live(broker_id) is False
    update = await adapter.get_order_status(broker_id)
    assert update.status is OrderStatus.CANCELED
    assert update.filled_quantity == 15
    assert update.fills == [fill]
