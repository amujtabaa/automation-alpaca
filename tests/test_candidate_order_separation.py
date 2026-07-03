"""Candidate and Order are separate lifecycles with independent status fields.

The key invariant: a candidate's status can never be a broker-execution state.
That is enforced structurally by the enums (a Candidate cannot even be
constructed with such a status), so no caller — and no test — can do it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    Candidate,
    CandidateStatus,
    Order,
    OrderSide,
    OrderStatus,
)
from app.store.base import CandidateTransitionError, OrderTransitionError

pytestmark = pytest.mark.anyio


# --- Structural separation (no store needed) ------------------------------ #
@pytest.mark.parametrize(
    "broker_state",
    ["submitted", "partially_filled", "filled", "canceled"],
)
def test_candidate_cannot_take_a_broker_execution_state(broker_state):
    with pytest.raises(ValidationError):
        Candidate(symbol="AAPL", status=broker_state)


def test_candidate_status_set_is_proposal_only():
    assert {s.value for s in CandidateStatus} == {
        "pending",
        "approved",
        "rejected",
        "expired",
        "ordered",
    }
    # Broker-execution states live only on the order.
    broker_only = {"submitted", "partially_filled", "filled", "canceled"}
    assert broker_only.isdisjoint({s.value for s in CandidateStatus})
    assert broker_only.issubset({s.value for s in OrderStatus})


def test_order_carries_candidate_link_and_replaces_field():
    order = Order(candidate_id="c1", symbol="AAPL", side=OrderSide.BUY, quantity=10)
    assert order.candidate_id == "c1"
    assert order.replaces_order_id is None  # present but unused in beta
    assert order.status is OrderStatus.CREATED


# --- Lifecycle behavior through the store --------------------------------- #
async def test_candidate_transitions_and_ordered_is_terminal(store):
    candidate = await store.create_candidate("AAPL")
    assert candidate.status is CandidateStatus.PENDING

    approved = await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    assert approved.status is CandidateStatus.APPROVED
    assert approved.approved_at is not None

    # Approve -> ordered, linking the order that was produced.
    order = await store.create_order(candidate.id, "AAPL", OrderSide.BUY, 10)
    ordered = await store.transition_candidate(
        candidate.id, CandidateStatus.ORDERED, order_id=order.id
    )
    assert ordered.status is CandidateStatus.ORDERED
    assert ordered.order_id == order.id

    # Ordered is terminal — no further transition is allowed.
    with pytest.raises(CandidateTransitionError):
        await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)


async def test_approve_reject_are_idempotent(store):
    candidate = await store.create_candidate("AAPL")
    once = await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    twice = await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    assert once.status is twice.status is CandidateStatus.APPROVED
    # Idempotency must not double-write: the no-op second approve records no
    # extra transition event.
    transitions = [
        e
        for e in await store.list_events()
        if e.event_type == "candidate_transition" and e.candidate_id == candidate.id
    ]
    assert len(transitions) == 1


async def test_rejected_candidate_cannot_be_approved(store):
    candidate = await store.create_candidate("AAPL")
    await store.transition_candidate(candidate.id, CandidateStatus.REJECTED)
    with pytest.raises(CandidateTransitionError):
        await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)


async def test_order_status_is_independent_of_candidate(store):
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order(candidate.id, "AAPL", OrderSide.BUY, 10)

    # CREATED -> SUBMITTING (the submission claim, D-017) — the order moving
    # forward is independent of its candidate either way.
    submitting = await store.transition_order(order.id, OrderStatus.SUBMITTING)
    assert submitting.status is OrderStatus.SUBMITTING
    # The candidate's status is untouched by the order moving forward.
    fresh = await store.get_candidate(candidate.id)
    assert fresh.status is CandidateStatus.PENDING


async def test_illegal_order_transition_raises(store):
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order(candidate.id, "AAPL", OrderSide.BUY, 10)
    # created -> filled is not legal; an order must pass through submitted first
    # (submitted != filled, Rule 6).
    with pytest.raises(OrderTransitionError):
        await store.transition_order(order.id, OrderStatus.FILLED)
    assert (await store.get_order(order.id)).status is OrderStatus.CREATED
