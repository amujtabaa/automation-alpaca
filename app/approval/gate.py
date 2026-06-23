"""The Approval Gate — the candidate → order decision seam (D-004).

Every candidate the Strategy Engine generates passes through one decision point
that answers *"who approves this — a human, or a rule?"* In beta the only answer
is "a human," but the **seam** is built from the start so that Phase 8/9 can add
an automatic mode as a new :class:`ApprovalGate` implementation, without
restructuring the candidate state machine or editing the routes.

The interface is deliberately small (see the Phase 3 prompt: *"Keep the surface
small; do not over-engineer for hypothetical auto-mode needs we haven't
designed."*). It has exactly two responsibilities:

* :meth:`ApprovalGate.evaluate` — the mode-specific *decision*. Human mode always
  returns :attr:`GateDecision.DEFER` (a person decides via the API); a future
  automatic mode returns :attr:`GateDecision.APPROVE` / :attr:`GateDecision.REJECT`
  from a rule.
* :meth:`ApprovalGate.approve` / :meth:`ApprovalGate.reject` — *carrying out* an
  approve/reject decision against the candidate lifecycle. Routes call these (not
  ``store.transition_candidate`` directly), so the approve/reject path flows
  through the gate seam.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from app.models import Candidate


class GateDecision(str, Enum):
    """What the gate decides should happen to a freshly-generated candidate.

    Human mode answers :attr:`DEFER` (a person decides through the API). A future
    automatic mode (Auto-Buy/Auto-Sell, Phase 8/9) answers :attr:`APPROVE` or
    :attr:`REJECT` from a strategy/risk rule. Modelling all three now means that
    mode is a new implementation behind this interface, not a state-machine
    rewrite.
    """

    APPROVE = "approve"
    REJECT = "reject"
    DEFER = "defer"


class ApprovalGate(ABC):
    """The pluggable candidate→order approval decision point.

    Beta ships exactly one implementation,
    :class:`~app.approval.human.HumanApprovalGate`. Route handlers depend on this
    abstract type (never on a concrete gate), so adding an automatic mode later
    is a drop-in subclass — no route or candidate-state-machine edits. That
    pluggability is the whole point of the seam (D-004) and is asserted directly
    in the tests.
    """

    @abstractmethod
    async def evaluate(self, candidate: Candidate) -> GateDecision:
        """Decide what should happen to a freshly-generated candidate.

        Human mode returns :attr:`GateDecision.DEFER` unconditionally — it never
        auto-decides; a person approves/rejects through the API. An automatic
        mode returns :attr:`GateDecision.APPROVE` / :attr:`GateDecision.REJECT`.
        """

    @abstractmethod
    async def approve(self, candidate_id: str) -> Candidate:
        """Carry out an approval: ``pending → approved`` (idempotent).

        Does **not** create the order — the ``approved → ordered`` handoff is a
        separate, explicit step (``store.create_order_for_candidate``), kept
        distinct on purpose (see the Phase 3 prompt / D-006). Re-approving an
        already-approved (or already-ordered) candidate is a no-op success;
        approving a terminal ``rejected``/``expired`` candidate raises
        :class:`~app.store.base.CandidateTransitionError`.
        """

    @abstractmethod
    async def reject(self, candidate_id: str) -> Candidate:
        """Carry out a rejection: ``pending → rejected`` (idempotent).

        Re-rejecting an already-rejected candidate is a no-op success; rejecting
        an ``approved``/``ordered``/``expired`` candidate raises
        :class:`~app.store.base.CandidateTransitionError`.
        """
