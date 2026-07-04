"""Shared test helpers for driving a store through the order lifecycle."""

from __future__ import annotations

from app.models import OrderStatus
from app.store.base import CLAIM_CLAIMED


async def submit_created_order(store, order_id, *, broker_order_id="broker-test"):
    """Move a ``CREATED`` order to ``SUBMITTED`` via the mandatory ``SUBMITTING``
    claim state (D-017 / AIR-007).

    ``CREATED`` reaches ``SUBMITTED`` *only* through the atomic submission claim
    (``claim_order_for_submission``); since AIR-007 the generic
    ``transition_order`` can no longer enter ``SUBMITTING`` at all, so this helper
    drives the real claim (the order must therefore carry an open, permissive
    session — ``create_order_for_test`` inherits the candidate's, matching
    production) and then records the broker ack.
    """

    claim = await store.claim_order_for_submission(order_id)
    assert claim.outcome == CLAIM_CLAIMED, (
        f"submit_created_order: order {order_id} could not be claimed "
        f"(outcome={claim.outcome!r}, reason={getattr(claim, 'reason', None)!r})"
    )
    return await store.transition_order(
        order_id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
    )
