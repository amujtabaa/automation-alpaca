"""``HumanApprovalGate`` unit behavior (the human-in-the-loop mode).

The gate executes approve/reject against the candidate lifecycle and never
auto-decides. Route-level pluggability (that the routes depend on the
``ApprovalGate`` interface, not the concrete gate) is asserted separately in
``test_candidate_flow_api.py``.
"""

from __future__ import annotations

import pytest

from app.approval import ApprovalGate, GateDecision, HumanApprovalGate
from app.models import Candidate, CandidateStatus
from app.store.base import CandidateTransitionError, UnknownEntityError

pytestmark = pytest.mark.anyio


def test_human_gate_is_an_approval_gate():
    # The pluggability contract: the concrete gate is a subclass of the ABC, so
    # a future automatic mode is a drop-in sibling, not a rewrite.
    assert issubclass(HumanApprovalGate, ApprovalGate)


async def test_evaluate_always_defers(store):
    gate = HumanApprovalGate(store)
    # Human mode never auto-decides, regardless of the candidate.
    decision = await gate.evaluate(Candidate(symbol="AAPL"))
    assert decision is GateDecision.DEFER


async def test_approve_transitions_pending_to_approved(store):
    gate = HumanApprovalGate(store)
    candidate = await store.create_candidate("AAPL", suggested_quantity=10)
    approved = await gate.approve(candidate.id)
    assert approved.status is CandidateStatus.APPROVED
    assert approved.approved_at is not None


async def test_approve_is_idempotent(store):
    gate = HumanApprovalGate(store)
    candidate = await store.create_candidate("AAPL", suggested_quantity=10)
    await gate.approve(candidate.id)
    await gate.approve(candidate.id)
    transitions = [
        e
        for e in await store.list_events()
        if e.event_type == "candidate_transition" and e.candidate_id == candidate.id
    ]
    # The second approve is a no-op: only one approve transition recorded.
    assert len(transitions) == 1


async def test_approve_after_ordered_is_noop_success(store):
    gate = HumanApprovalGate(store)
    candidate = await store.create_candidate("AAPL", suggested_quantity=10)
    await gate.approve(candidate.id)
    await store.create_order_for_candidate(candidate.id)  # now ORDERED
    # Re-approving a dispatched candidate succeeds as a no-op rather than erroring
    # on the terminal ORDERED state.
    result = await gate.approve(candidate.id)
    assert result.status is CandidateStatus.ORDERED
    # No second approve transition, no second order.
    assert len(await store.list_orders()) == 1


async def test_approve_rejected_candidate_raises(store):
    gate = HumanApprovalGate(store)
    candidate = await store.create_candidate("AAPL", suggested_quantity=10)
    await gate.reject(candidate.id)
    with pytest.raises(CandidateTransitionError):
        await gate.approve(candidate.id)


async def test_approve_unknown_candidate_raises(store):
    gate = HumanApprovalGate(store)
    with pytest.raises(UnknownEntityError):
        await gate.approve("no-such-candidate")


async def test_reject_transitions_pending_to_rejected(store):
    gate = HumanApprovalGate(store)
    candidate = await store.create_candidate("AAPL", suggested_quantity=10)
    rejected = await gate.reject(candidate.id)
    assert rejected.status is CandidateStatus.REJECTED
    assert rejected.rejected_at is not None


async def test_reject_is_idempotent(store):
    gate = HumanApprovalGate(store)
    candidate = await store.create_candidate("AAPL", suggested_quantity=10)
    await gate.reject(candidate.id)
    await gate.reject(candidate.id)
    transitions = [
        e
        for e in await store.list_events()
        if e.event_type == "candidate_transition" and e.candidate_id == candidate.id
    ]
    assert len(transitions) == 1


async def test_reject_approved_candidate_raises(store):
    gate = HumanApprovalGate(store)
    candidate = await store.create_candidate("AAPL", suggested_quantity=10)
    await gate.approve(candidate.id)
    with pytest.raises(CandidateTransitionError):
        await gate.reject(candidate.id)


async def test_reject_unknown_candidate_raises(store):
    gate = HumanApprovalGate(store)
    with pytest.raises(UnknownEntityError):
        await gate.reject("no-such-candidate")
