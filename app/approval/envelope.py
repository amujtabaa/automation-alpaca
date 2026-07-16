"""``EnvelopeApprovalGate`` — the human-in-the-loop gate for execution
envelopes (ADR-010 §1, WO-0017).

Same conventions as :class:`~app.approval.human.HumanApprovalGate`:
``evaluate`` never auto-decides (beta is human-only — the envelope is
precisely the unit of HUMAN approval), the gate owns no persistence, and all
durability lives in ONE store-atomic operation
(``StateStore.approve_envelope_activation``, the ENG-001 shape) so the gate
itself has no window in which a kill or a concurrent approval can interleave.

It is deliberately NOT a subclass of :class:`~app.approval.gate.ApprovalGate`
— that ABC is typed on ``Candidate``; this is the parallel seam for
``ExecutionEnvelope`` with the same evaluate/approve/reject surface.
"""

from __future__ import annotations

from app.approval.gate import GateDecision
from app.models import EnvelopeStatus, ExecutionEnvelope
from app.store.base import COMMAND_ACTOR_SYSTEM, StateStore


class EnvelopeApprovalGate:
    """Human-in-the-loop envelope approval. Defers every decision to a person."""

    def __init__(self, store: StateStore) -> None:
        self._store = store

    async def evaluate(self, draft: ExecutionEnvelope) -> GateDecision:
        # Human mode never auto-decides: the approved envelope IS the mandate.
        return GateDecision.DEFER

    async def approve(
        self, draft: ExecutionEnvelope, *, actor: str = COMMAND_ACTOR_SYSTEM
    ) -> ExecutionEnvelope:
        """Approve + activate ``draft`` as one store-atomic unit. Idempotent
        past the activation point (re-approve of ACTIVE is a no-op); illegal
        for terminal envelopes; refused with zero artifacts while HALTED."""

        return await self._store.approve_envelope_activation(draft, actor=actor)

    async def reject(
        self, envelope_id: str, *, actor: str = COMMAND_ACTOR_SYSTEM
    ) -> ExecutionEnvelope:
        """Withdraw a PRE-ACTIVATION envelope (PENDING/APPROVED → CANCELLED,
        the ADR-010 §3 escape edges; idempotent for already-CANCELLED). An
        ACTIVE envelope is not gate-rejectable — stopping a live mandate goes
        through the precedence paths (kill freeze, flatten preemption, or an
        explicit freeze-then-cancel), never a quiet gate call."""

        return await self._store.transition_envelope(
            envelope_id,
            EnvelopeStatus.CANCELLED,
            actor=actor,
            reason="gate_rejected",
        )
