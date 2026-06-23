"""``HumanApprovalGate`` — the human-in-the-loop gate, beta's only mode.

It never auto-decides: :meth:`evaluate` always defers to a person. A human's
approve/reject arrives through the API (``POST /api/candidates/{id}/approve`` /
``/reject``) and drives the *existing* candidate transitions — this gate simply
executes them against the store. Like every other backend service it holds a
:class:`~app.store.base.StateStore`; it owns no persistence of its own.

The deliberate non-responsibility: the gate does **not** create the order. The
``approved → ordered`` handoff is a separate, atomic store operation
(``create_order_for_candidate``), so the approval decision and the order dispatch
stay distinct steps (Phase 3 prompt §3 / D-006).
"""

from __future__ import annotations

from app.approval.gate import ApprovalGate, GateDecision
from app.models import Candidate, CandidateStatus
from app.store.base import StateStore, UnknownEntityError


class HumanApprovalGate(ApprovalGate):
    """Human-in-the-loop approval. Defers every decision to a person."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    async def evaluate(self, candidate: Candidate) -> GateDecision:
        # Human mode never auto-decides — a person approves/rejects via the API.
        return GateDecision.DEFER

    async def approve(self, candidate_id: str) -> Candidate:
        candidate = await self._store.get_candidate(candidate_id)
        if candidate is None:
            raise UnknownEntityError(f"candidate {candidate_id} not found")
        # Idempotent past the approval point: a candidate already ORDERED
        # (approved *and* dispatched) re-approves as a no-op success, rather than
        # erroring because ORDERED is terminal in the candidate state machine.
        if candidate.status is CandidateStatus.ORDERED:
            return candidate
        # PENDING -> APPROVED, or APPROVED -> APPROVED as an idempotent no-op.
        # A terminal REJECTED/EXPIRED candidate raises CandidateTransitionError
        # (the route maps it to HTTP 409). The store owns that legality check.
        return await self._store.transition_candidate(
            candidate_id, CandidateStatus.APPROVED
        )

    async def reject(self, candidate_id: str) -> Candidate:
        # The store handles everything cleanly: PENDING -> REJECTED; REJECTED ->
        # REJECTED as an idempotent no-op; APPROVED/ORDERED/EXPIRED -> illegal
        # (CandidateTransitionError -> 409); unknown id -> UnknownEntityError ->
        # 404. No pre-fetch needed.
        return await self._store.transition_candidate(
            candidate_id, CandidateStatus.REJECTED
        )
