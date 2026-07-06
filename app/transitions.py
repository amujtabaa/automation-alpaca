"""Legal lifecycle transitions, shared by both StateStore implementations.

Keeping these in one place guarantees ``InMemoryStateStore`` and
``SqliteStateStore`` enforce the *same* state machines (the candidate machine
stops at ``ordered``; the order machine carries the broker states). Same-status
transitions are handled as idempotent no-ops by the stores, not encoded here.
"""

from __future__ import annotations

from app.models import CandidateStatus, OrderStatus, SellIntentStatus

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

# Sell-intent lifecycle (Phase 7) — a PARALLEL table of identical shape to the
# candidate machine (not a literal reuse: CANDIDATE_TRANSITIONS is typed on
# CandidateStatus and cannot key on SellIntentStatus). approved -> expired is a
# real path (the self-heal when the intent->order handoff is rejected, e.g. the
# position vanished): an intent is never left stranded APPROVED with no order.
SELL_INTENT_TRANSITIONS: dict[SellIntentStatus, set[SellIntentStatus]] = {
    SellIntentStatus.PENDING: {
        SellIntentStatus.APPROVED,
        SellIntentStatus.REJECTED,
        SellIntentStatus.EXPIRED,
    },
    SellIntentStatus.APPROVED: {
        SellIntentStatus.ORDERED,
        SellIntentStatus.EXPIRED,  # self-heal on a rejected intent->order handoff
    },
    SellIntentStatus.REJECTED: set(),
    SellIntentStatus.EXPIRED: set(),
    SellIntentStatus.ORDERED: set(),
}

ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {
        # NOTE (AIR-007): CREATED -> SUBMITTING is deliberately ABSENT here.
        # The atomic submission claim (D-017, claim_order_for_submission) is the
        # sole entry into SUBMITTING and writes that status *directly* (memory:
        # self._orders[id] = plan.order; SQLite: raw UPDATE ... SET status),
        # never consulting this table. Only the *generic* transition_order reads
        # this table, so listing SUBMITTING here would make transition_order a
        # back door into SUBMITTING that bypasses the claim's atomic control
        # re-check (kill switch / buys paused / session) — a control-flip
        # bypass. Leaving it out closes that door without affecting the claim
        # path. (SUBMITTING -> CREATED, the transient-submit-failure release,
        # still goes through transition_order and stays listed below.)
        OrderStatus.CANCELED,  # never-submitted order cancelled locally
        OrderStatus.REJECTED,
    },
    OrderStatus.SUBMITTING: {
        OrderStatus.SUBMITTED,  # broker acked the submission
        OrderStatus.CREATED,    # release the claim on a transient submit failure
                                # (next tick re-runs the full control gate)
        OrderStatus.CANCELED,   # manual cancel raced the submit / terminal
        OrderStatus.REJECTED,   # broker rejected
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

# Sell-intent transition timestamps (parallel to CANDIDATE_TIMESTAMP).
SELL_INTENT_TIMESTAMP: dict[SellIntentStatus, str] = {
    SellIntentStatus.APPROVED: "approved_at",
    SellIntentStatus.REJECTED: "rejected_at",
    SellIntentStatus.EXPIRED: "expired_at",
    SellIntentStatus.ORDERED: "ordered_at",
}

ORDER_TIMESTAMP: dict[OrderStatus, str] = {
    OrderStatus.SUBMITTED: "submitted_at",
    OrderStatus.FILLED: "filled_at",
    OrderStatus.CANCELED: "canceled_at",
    OrderStatus.REJECTED: "rejected_at",
}
