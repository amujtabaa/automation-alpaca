"""The atomic ``APPROVED → ORDERED`` handoff (``create_order_for_candidate``).

Run through ``any_store`` so InMemoryStateStore and SqliteStateStore are proven
to behave identically (the handoff is a multi-row mutation — order row +
candidate row + two audit events — that must be atomic in both: D-006 / docs/02
"candidate approval + order creation + audit event").
"""

from __future__ import annotations

import pytest

from app.models import CandidateStatus, OrderSide, OrderStatus, OrderType
from app.store.base import (
    CandidateTransitionError,
    InvalidOrderError,
    SessionClosedError,
    UnknownEntityError,
)

pytestmark = pytest.mark.anyio


async def _approved_candidate(store, *, symbol="AAPL", quantity=10, limit=1.50):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol,
        strategy="mock",
        reason="exercise the flow",
        suggested_quantity=quantity,
        suggested_limit_price=limit,
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.get_candidate(candidate.id)


async def test_handoff_creates_order_and_marks_candidate_ordered(any_store):
    candidate = await _approved_candidate(
        any_store, symbol="aapl", quantity=25, limit=2.0
    )

    order = await any_store.create_order_for_candidate(candidate.id)

    # The order reflects the candidate's proposal: long-only BUY LIMIT, sized
    # from suggested_*; no fills yet (submitted != filled — Rule 6 untouched here).
    assert order.candidate_id == candidate.id
    assert order.symbol == "AAPL"
    assert order.side is OrderSide.BUY
    assert order.order_type is OrderType.LIMIT
    assert order.quantity == 25
    assert order.limit_price == 2.0
    assert order.status is OrderStatus.CREATED
    assert order.filled_quantity == 0
    assert order.session_id == candidate.session_id

    # The candidate is now ORDERED (terminal) and linked to the order.
    fresh = await any_store.get_candidate(candidate.id)
    assert fresh.status is CandidateStatus.ORDERED
    assert fresh.order_id == order.id
    assert fresh.ordered_at is not None

    # Both audit events were written.
    events = await any_store.list_events()
    types_for_order = [e.event_type for e in events if e.order_id == order.id]
    assert "order_created" in types_for_order
    transition = [
        e
        for e in events
        if e.event_type == "candidate_transition"
        and e.candidate_id == candidate.id
        and e.payload.get("to") == "ordered"
    ]
    assert len(transition) == 1
    assert transition[0].payload == {"from": "approved", "to": "ordered"}


async def test_handoff_is_idempotent_no_second_order(any_store):
    candidate = await _approved_candidate(any_store)

    first = await any_store.create_order_for_candidate(candidate.id)
    second = await any_store.create_order_for_candidate(candidate.id)

    # Same order returned; exactly one order exists; no duplicate audit rows.
    assert second.id == first.id
    assert len(await any_store.list_orders()) == 1
    ordered_transitions = [
        e
        for e in await any_store.list_events()
        if e.event_type == "candidate_transition"
        and e.candidate_id == candidate.id
        and e.payload.get("to") == "ordered"
    ]
    assert len(ordered_transitions) == 1
    order_created = [
        e for e in await any_store.list_events() if e.event_type == "order_created"
    ]
    assert len(order_created) == 1


async def test_handoff_requires_approved_candidate(any_store):
    await any_store.initialize()
    pending = await any_store.create_candidate("AAPL", suggested_quantity=10)
    # Still PENDING — not yet approved.
    with pytest.raises(CandidateTransitionError):
        await any_store.create_order_for_candidate(pending.id)
    # Nothing was created.
    assert await any_store.list_orders() == []
    assert (await any_store.get_candidate(pending.id)).status is CandidateStatus.PENDING


async def test_handoff_rejects_terminal_candidate(any_store):
    await any_store.initialize()
    rejected = await any_store.create_candidate("AAPL", suggested_quantity=10)
    await any_store.transition_candidate(rejected.id, CandidateStatus.REJECTED)
    with pytest.raises(CandidateTransitionError):
        await any_store.create_order_for_candidate(rejected.id)
    assert await any_store.list_orders() == []


async def test_handoff_unknown_candidate_raises(any_store):
    await any_store.initialize()
    with pytest.raises(UnknownEntityError):
        await any_store.create_order_for_candidate("no-such-candidate")


async def test_handoff_without_suggested_quantity_raises(any_store):
    await any_store.initialize()
    candidate = await any_store.create_candidate("AAPL")  # no suggested_quantity
    await any_store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    with pytest.raises(InvalidOrderError):
        await any_store.create_order_for_candidate(candidate.id)
    # Rejected before any state changed: no order, candidate stays APPROVED.
    assert await any_store.list_orders() == []
    assert (
        await any_store.get_candidate(candidate.id)
    ).status is CandidateStatus.APPROVED


# AIR-008: a non-positive quantity/price is now rejected at the *candidate*
# boundary (both stores identically), before any row is persisted — earlier and
# stronger than the old order-creation reject. The handoff guard below still
# stands as defense-in-depth for the one value the candidate boundary allows
# (a genuinely-absent None price on an unsized candidate).
@pytest.mark.parametrize("bad_qty", [0, -5])
async def test_create_candidate_rejects_non_positive_quantity(any_store, bad_qty):
    await any_store.initialize()
    with pytest.raises(InvalidOrderError):
        await any_store.create_candidate("AAPL", suggested_quantity=bad_qty)
    assert await any_store.list_candidates() == []
    assert await any_store.list_orders() == []


@pytest.mark.parametrize("bad_price", [0, -1.0])
async def test_create_candidate_rejects_non_positive_limit_price(any_store, bad_price):
    await any_store.initialize()
    with pytest.raises(InvalidOrderError):
        await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=bad_price
        )
    assert await any_store.list_candidates() == []
    assert await any_store.list_orders() == []


# A LIMIT order must never be persisted without a positive limit price (F1). A
# None price is a *valid* candidate (unsized/unpriced), so the candidate
# boundary allows it — the handoff is the last line of defense that refuses to
# build a LIMIT order with no price.
async def test_handoff_rejects_missing_limit_price(any_store):
    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=None
    )
    await any_store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    with pytest.raises(InvalidOrderError):
        await any_store.create_order_for_candidate(candidate.id)
    # Rejected before any state changed: no order, candidate stays APPROVED.
    assert await any_store.list_orders() == []
    assert (
        await any_store.get_candidate(candidate.id)
    ).status is CandidateStatus.APPROVED


# No new candidates may be created in a closed session (D-009 / F2).
async def test_create_candidate_refused_in_closed_session(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    await any_store.close_session(session.id)

    # Explicit closed session_id is refused ...
    with pytest.raises(SessionClosedError):
        await any_store.create_candidate(
            "AAPL",
            suggested_quantity=10,
            suggested_limit_price=1.0,
            session_id=session.id,
        )
    # ... and so is the default path, which resolves to the closed session
    # post-close (D-009 keeps the day's session closed, no auto-create).
    with pytest.raises(SessionClosedError):
        await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=1.0
        )
    # Nothing was created either way.
    assert await any_store.list_candidates() == []
