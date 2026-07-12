"""WO-0017 — the envelope approval surface (ADR-010 §1), BOTH stores.

``approve_envelope_activation`` is ONE store-atomic unit in the ENG-001 shape:
dedup/idempotency → HALTED check → create → approve → activate → events, with
no await between the control check and the durable writes. A kill landing
before the op blocks it with ZERO artifacts (the REV-0020 last-await mirror);
landing after it leaves an ACTIVE envelope that the kill hook then freezes.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app.approval.envelope import EnvelopeApprovalGate
from app.approval.gate import GateDecision
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    SessionType,
    utcnow,
)
from app.store.base import OrderIntentBlockedError
from app.store.core import EnvelopeTransitionError

pytestmark = pytest.mark.anyio

S = EnvelopeStatus


def make_draft(intent_id: str = "si-1", **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.50,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.20,
        aggressiveness=["passive"],
        cooldown_floor_ms=750,
        cancel_replace_budget=40,
        expires_at=utcnow() + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


async def envelope_events(store, envelope_id):
    return [
        e for e in await store.get_execution_events() if e.envelope_id == envelope_id
    ]


async def test_approve_activation_is_one_atomic_unit_with_full_trail(any_store):
    await any_store.initialize()
    draft = make_draft()
    active = await any_store.approve_envelope_activation(draft, actor="operator-ameen")
    assert active.status is S.ACTIVE
    assert active.approved_at is not None and active.activated_at is not None

    events = await envelope_events(any_store, draft.id)
    kinds = [e.event_type for e in events]
    assert kinds == [
        ExecutionEventType.ENVELOPE_CREATED,
        ExecutionEventType.ENVELOPE_APPROVED,
        ExecutionEventType.ENVELOPE_ACTIVATED,
    ]
    # Approval provenance is the commanding operator (autonomous-side events
    # elsewhere stay system/engine-actor).
    assert events[0].payload["actor"] == "operator-ameen"
    assert events[1].payload["actor"] == "operator-ameen"


async def test_reapprove_of_active_is_an_idempotent_noop(any_store):
    await any_store.initialize()
    draft = make_draft()
    first = await any_store.approve_envelope_activation(draft, actor="operator-a")
    before = len(await envelope_events(any_store, draft.id))
    again = await any_store.approve_envelope_activation(draft, actor="operator-a")
    assert again.status is S.ACTIVE
    assert again.id == first.id
    assert len(await envelope_events(any_store, draft.id)) == before  # no new rows


async def test_approve_of_a_preexisting_pending_draft_completes_the_chain(
    any_store,
):
    await any_store.initialize()
    draft = make_draft()
    await any_store.create_envelope(draft, actor="operator-a")
    active = await any_store.approve_envelope_activation(draft, actor="operator-a")
    assert active.status is S.ACTIVE
    kinds = [e.event_type for e in await envelope_events(any_store, draft.id)]
    assert kinds == [
        ExecutionEventType.ENVELOPE_CREATED,  # from create_envelope
        ExecutionEventType.ENVELOPE_APPROVED,
        ExecutionEventType.ENVELOPE_ACTIVATED,
    ]


async def test_approve_of_a_terminal_envelope_is_illegal(any_store):
    await any_store.initialize()
    draft = make_draft()
    await any_store.create_envelope(draft)
    await any_store.transition_envelope(draft.id, S.CANCELLED)
    with pytest.raises(EnvelopeTransitionError):
        await any_store.approve_envelope_activation(draft, actor="operator-a")


async def test_halted_blocks_approval_with_zero_artifacts(any_store):
    """The REV-0020 mirror: the kill lands BEFORE the op — the HALTED check is
    atomic with the would-be writes, so nothing exists afterwards."""

    await any_store.initialize()
    await any_store.set_kill_switch(True, actor="operator-a")
    draft = make_draft()
    with pytest.raises(OrderIntentBlockedError):
        await any_store.approve_envelope_activation(draft, actor="operator-a")
    assert await any_store.get_envelope(draft.id) is None  # zero artifacts
    assert await envelope_events(any_store, draft.id) == []


@pytest.mark.parametrize(
    "kill_first", [True, False], ids=["kill-first", "approve-first"]
)
async def test_kill_race_never_ends_with_an_active_envelope_under_halted(
    any_store, kill_first
):
    """Both serializations of kill×approve, each with its EXACT outcome
    asserted. (WO-0028/TC-05: the old single-gather version had an either/or
    branch whose approve-first arm was structurally unreachable — gather +
    the store lock deterministically serialized kill first, so a deleted
    kill-freeze hook passed 20/20. gather schedules tasks in argument order
    and the store lock is FIFO, so ordering the arguments forces the
    serialization; if that scheduling guarantee ever changes, these exact
    assertions fail loudly instead of silently passing.)"""

    await any_store.initialize()
    draft = make_draft()
    kill = any_store.set_kill_switch(True, actor="operator-a")
    approve = any_store.approve_envelope_activation(draft, actor="operator-a")
    first, second = (kill, approve) if kill_first else (approve, kill)
    results = await asyncio.gather(first, second, return_exceptions=True)
    stored = await any_store.get_envelope(draft.id)

    if kill_first:
        # Kill wins the lock: approval must refuse with ZERO artifacts.
        approval = results[1]
        assert isinstance(approval, OrderIntentBlockedError)
        assert stored is None
        assert await envelope_events(any_store, draft.id) == []
    else:
        # Approval wins the lock: it lands ACTIVE, then the kill hook freezes
        # it atomically with the control change — the branch the old test
        # never reached, and the one that pins the hook itself.
        assert not isinstance(results[0], BaseException)
        assert stored is not None
        assert stored.status is S.FROZEN
    if stored is not None:
        assert stored.status is not S.ACTIVE


async def test_concurrent_approvals_of_one_intent_are_single_flight(any_store):
    await any_store.initialize()
    drafts = [make_draft() for _ in range(5)]
    results = await asyncio.gather(
        *(any_store.approve_envelope_activation(d, actor="operator-a") for d in drafts),
        return_exceptions=True,
    )
    winners = [r for r in results if isinstance(r, ExecutionEnvelope)]
    losers = [r for r in results if isinstance(r, EnvelopeTransitionError)]
    assert len(winners) == 1 and len(losers) == 4
    active = await any_store.list_envelopes(sell_intent_id="si-1", status=S.ACTIVE)
    assert [e.id for e in active] == [winners[0].id]


async def test_concurrent_same_draft_approvals_yield_one_trail(any_store):
    await any_store.initialize()
    draft = make_draft()
    results = await asyncio.gather(
        *(
            any_store.approve_envelope_activation(draft, actor="operator-a")
            for _ in range(4)
        ),
        return_exceptions=True,
    )
    assert all(isinstance(r, ExecutionEnvelope) for r in results)  # idempotent
    assert all(r.status is S.ACTIVE for r in results)
    kinds = [e.event_type for e in await envelope_events(any_store, draft.id)]
    assert kinds == [
        ExecutionEventType.ENVELOPE_CREATED,
        ExecutionEventType.ENVELOPE_APPROVED,
        ExecutionEventType.ENVELOPE_ACTIVATED,
    ]


async def test_tampered_non_pending_draft_is_rejected(any_store):
    from app.store.base import InvalidOrderError

    await any_store.initialize()
    tampered = make_draft().model_copy(update={"status": S.APPROVED})
    with pytest.raises(InvalidOrderError):
        await any_store.approve_envelope_activation(tampered, actor="operator-a")


def test_dispositions_are_structurally_mandatory_at_approval_time():
    """The approval surface cannot even RECEIVE a draft without both
    approval-time dispositions or the TTL — construction fails first."""

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_draft(expiry_disposition=None)
    with pytest.raises(ValidationError):
        make_draft(stale_data_disposition=None)
    with pytest.raises(ValidationError):
        make_draft(expires_at=None)


# --- the gate object (ApprovalGate conventions) ------------------------------- #


async def test_envelope_gate_defers_evaluate_and_delegates_approve(any_store):
    await any_store.initialize()
    gate = EnvelopeApprovalGate(any_store)
    draft = make_draft()
    assert await gate.evaluate(draft) is GateDecision.DEFER
    active = await gate.approve(draft, actor="operator-ameen")
    assert active.status is S.ACTIVE


async def test_envelope_gate_reject_cancels_a_pending_draft(any_store):
    await any_store.initialize()
    gate = EnvelopeApprovalGate(any_store)
    draft = make_draft()
    await any_store.create_envelope(draft, actor="operator-a")
    rejected = await gate.reject(draft.id, actor="operator-a")
    assert rejected.status is S.CANCELLED
    # Idempotent re-reject; rejecting an ACTIVE envelope is illegal (that is
    # a freeze/cancel through the precedence paths, not a gate rejection).
    again = await gate.reject(draft.id, actor="operator-a")
    assert again.status is S.CANCELLED
    other = make_draft(intent_id="si-2")
    await any_store.approve_envelope_activation(other, actor="operator-a")
    with pytest.raises(EnvelopeTransitionError):
        await gate.reject(other.id, actor="operator-a")
