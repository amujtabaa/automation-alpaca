"""Shared test helpers for driving a store through the order lifecycle."""

from __future__ import annotations

from app.models import OrderStatus


async def submit_created_order(store, order_id, *, broker_order_id="broker-test"):
    """Move a ``CREATED`` order to ``SUBMITTED`` via the mandatory ``SUBMITTING``
    claim state (D-017).

    Since Wave 0, ``CREATED`` no longer transitions straight to ``SUBMITTED`` —
    the atomic submission claim (``CREATED -> SUBMITTING``) is the only path to
    the broker — so test setup that just needs an order "as if the loop
    submitted it" uses this two-step helper instead of a single
    ``transition_order(..., SUBMITTED)`` call.
    """

    await store.transition_order(order_id, OrderStatus.SUBMITTING)
    return await store.transition_order(
        order_id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
    )
