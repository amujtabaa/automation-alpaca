"""Legal lifecycle transitions, shared by both StateStore implementations.

Keeping these in one place guarantees ``InMemoryStateStore`` and
``SqliteStateStore`` enforce the *same* state machines (the candidate machine
stops at ``ordered``; the order machine carries the broker states). Same-status
transitions are handled as idempotent no-ops by the stores, not encoded here.
"""

from __future__ import annotations

from app.models import (
    CandidateStatus,
    EnvelopeStatus,
    OrderStatus,
    SellIntentStatus,
)

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

# Execution-envelope machine (ADR-010 §3, incl. the 2026-07-11 pre-activation
# escape-edge amendment). BREACHED / EXHAUSTED are terminal-pending-human:
# recorded, never hidden, and deliberately have NO outgoing edges — resumption
# of a breached/exhausted mandate is not a transition, it is a new envelope
# through the approval gate. FROZEN (kill switch / Halted) is the only
# resumable non-terminal detour; FROZEN -> COMPLETED intentionally does NOT
# exist — a frozen envelope whose remaining quantity hits 0 completes on
# RESUME (the store's resume path auto-completes at remaining == 0), so a
# freeze can never be silently exited by a fill.
ENVELOPE_TRANSITIONS: dict[EnvelopeStatus, set[EnvelopeStatus]] = {
    EnvelopeStatus.PENDING: {
        EnvelopeStatus.APPROVED,
        EnvelopeStatus.CANCELLED,  # operator withdraws a proposal
        EnvelopeStatus.EXPIRED,  # TTL lapsed before approval
    },
    EnvelopeStatus.APPROVED: {
        EnvelopeStatus.ACTIVE,
        EnvelopeStatus.CANCELLED,  # operator withdraws before activation
        EnvelopeStatus.EXPIRED,  # TTL lapsed before activation
    },
    EnvelopeStatus.ACTIVE: {
        EnvelopeStatus.COMPLETED,
        EnvelopeStatus.EXPIRED,
        EnvelopeStatus.EXHAUSTED,
        EnvelopeStatus.BREACHED,
        EnvelopeStatus.SUPERSEDED,
        EnvelopeStatus.FROZEN,
    },
    EnvelopeStatus.FROZEN: {
        EnvelopeStatus.ACTIVE,  # kill switch released — resume
        EnvelopeStatus.CANCELLED,
        # WO-0029A (ADR-010 §2/§3 amendment, accepted 2026-07-12): a
        # broker-authoritative overfill of the hard qty ceiling is a BREACH
        # in every state that can receive a fill — a violated mandate must
        # never terminate in the success state.
        EnvelopeStatus.BREACHED,
    },
    EnvelopeStatus.COMPLETED: set(),
    EnvelopeStatus.EXPIRED: set(),
    EnvelopeStatus.EXHAUSTED: set(),
    EnvelopeStatus.BREACHED: set(),
    EnvelopeStatus.SUPERSEDED: set(),
    EnvelopeStatus.CANCELLED: set(),
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
        OrderStatus.CREATED,  # release the claim on a transient submit failure
        # (next tick re-runs the full control gate)
        OrderStatus.CANCELED,  # manual cancel raced the submit / terminal
        OrderStatus.REJECTED,  # broker rejected
        # Ambiguous submit outcome (ADR-002 / wave 3c): timeout/504/transport
        # after the request may have reached the venue. Driven ONLY by the
        # evented store path (`transition_order_evented`), which co-writes the
        # TIMEOUT_QUARANTINE ExecutionEvent atomically. See docs/SPINE_WAVE3C_PLAN.md.
        OrderStatus.TIMEOUT_QUARANTINE,
    },
    OrderStatus.TIMEOUT_QUARANTINE: {
        # Resolved ONLY by a read-only targeted client_order_id query
        # (`_resolve_timeout_quarantine`): the venue has it working/filled
        # (-> SUBMITTED, then the normal reconcile poll ingests fills, preserving
        # INV-9 "submitted != filled" — conflict C4), definitively never arrived
        # (-> REJECTED), or an external/late cancel (-> CANCELED). Each resolution
        # co-writes the matching ExecutionEvent via `transition_order_evented`.
        OrderStatus.SUBMITTED,
        OrderStatus.REJECTED,
        OrderStatus.CANCELED,
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

# Envelope transition timestamps. ACTIVE maps to activated_at and is restamped
# on every FROZEN -> ACTIVE resume (documented "most recent activation").
ENVELOPE_TIMESTAMP: dict[EnvelopeStatus, str] = {
    EnvelopeStatus.APPROVED: "approved_at",
    EnvelopeStatus.ACTIVE: "activated_at",
    EnvelopeStatus.FROZEN: "frozen_at",
    EnvelopeStatus.COMPLETED: "completed_at",
    EnvelopeStatus.EXPIRED: "expired_at",
    EnvelopeStatus.EXHAUSTED: "exhausted_at",
    EnvelopeStatus.BREACHED: "breached_at",
    EnvelopeStatus.SUPERSEDED: "superseded_at",
    EnvelopeStatus.CANCELLED: "cancelled_at",
}

ORDER_TIMESTAMP: dict[OrderStatus, str] = {
    OrderStatus.SUBMITTED: "submitted_at",
    OrderStatus.FILLED: "filled_at",
    OrderStatus.CANCELED: "canceled_at",
    OrderStatus.REJECTED: "rejected_at",
}
