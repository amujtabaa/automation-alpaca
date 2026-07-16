"""Shared test helpers for driving a store through the order lifecycle."""

from __future__ import annotations

from datetime import datetime

from app.models import EnvelopeStatus, OrderStatus
from app.store.base import CLAIM_CLAIMED


async def activate_envelope_at(store, draft, *, now: datetime, actor="operator-a"):
    """Create + approve + activate ``draft`` with an INJECTED activation clock
    (``activated_at = now``). ``approve_envelope_activation`` stamps lifecycle
    timestamps with the wall clock; a test whose tape/decide universe is
    anchored to a fixed NOW must anchor ``activated_at`` the same way — the
    policy's since-activation window (INV-086: only prints from THIS mandate's
    life) otherwise EMPTIES the moment the wall clock passes the tape's fixed
    timestamps, and the suite turns red by time of day (found 2026-07-15:
    green every morning run, red after ~13:20 UTC — the tape anchors'
    wall-clock crossover; permanently red from 2026-07-16)."""

    env = await store.create_envelope(draft, actor=actor)
    await store.transition_envelope(
        env.id, EnvelopeStatus.APPROVED, actor=actor, now=now
    )
    return await store.transition_envelope(
        env.id, EnvelopeStatus.ACTIVE, actor=actor, now=now
    )


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
