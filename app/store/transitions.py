"""Legal lifecycle transitions, shared by both StateStore implementations.

Keeping these in one place guarantees ``InMemoryStateStore`` and
``SqliteStateStore`` enforce the *same* state machines (the candidate machine
stops at ``ordered``; the order machine carries the broker states). Same-status
transitions are handled as idempotent no-ops by the stores, not encoded here.
"""

from __future__ import annotations

from app.models import CandidateStatus, OrderStatus

CANDIDATE_TRANSITIONS: dict[CandidateStatus, set[CandidateStatus]] = {
    CandidateStatus.PENDING: {
        CandidateStatus.APPROVED,
        CandidateStatus.REJECTED,
        CandidateStatus.EXPIRED,
    },
    CandidateStatus.APPROVED: {CandidateStatus.ORDERED},
    CandidateStatus.REJECTED: set(),
    CandidateStatus.EXPIRED: set(),
    CandidateStatus.ORDERED: set(),
}

ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {
        OrderStatus.SUBMITTED,
        OrderStatus.CANCELED,  # never-submitted order cancelled locally
        OrderStatus.REJECTED,
    },
    OrderStatus.SUBMITTED: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,  # cancel requested at the broker (CHAOS-1)
        OrderStatus.CANCELED,  # broker-confirmed/external cancel
        OrderStatus.REJECTED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.PARTIALLY_FILLED,  # further partial fills
        OrderStatus.FILLED,
        OrderStatus.CANCEL_PENDING,  # cancel requested with a partial already filled
        OrderStatus.CANCELED,
    },
    OrderStatus.CANCEL_PENDING: {
        OrderStatus.CANCEL_PENDING,  # still pending; a late partial fill progressed
        OrderStatus.FILLED,  # a late fill completed it before the cancel landed
        OrderStatus.CANCELED,  # broker confirmed the cancel
        OrderStatus.REJECTED,
    },
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELED: set(),
    OrderStatus.REJECTED: set(),
}

CANDIDATE_TIMESTAMP: dict[CandidateStatus, str] = {
    CandidateStatus.APPROVED: "approved_at",
    CandidateStatus.REJECTED: "rejected_at",
    CandidateStatus.EXPIRED: "expired_at",
    CandidateStatus.ORDERED: "ordered_at",
}

ORDER_TIMESTAMP: dict[OrderStatus, str] = {
    OrderStatus.SUBMITTED: "submitted_at",
    OrderStatus.FILLED: "filled_at",
    OrderStatus.CANCELED: "canceled_at",
    OrderStatus.REJECTED: "rejected_at",
}
