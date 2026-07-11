"""Pydantic v2 models for every persisted entity.

These mirror the entities named in ``docs/02_DATA_AND_PERSISTENCE.md``. The
shapes encode the non-negotiable structural rules:

* **Candidate and Order are separate lifecycles.** Candidate status stops at
  ``ordered`` (proposal/review only); broker-execution states live on the Order.
  The two enums share no members, so there is no code path that can set a
  candidate's status to ``submitted`` or ``filled``.
* **A Fill has no status field** — it is an append-only fact. It carries a
  nullable ``source_fill_id`` (Alpaca's execution id) for duplicate detection.
* **An Order carries ``candidate_id`` and a nullable, self-referencing**
  ``replaces_order_id`` (forward-compat for a future Auto-Sell engine; never
  populated in beta).
* **Position is a derived read model** (symbol, quantity, average price) — it is
  never stored as a directly mutable quantity. Only folding fills produces it.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator


def new_id() -> str:
    """A fresh opaque identifier (uuid4 hex)."""

    return uuid.uuid4().hex


def _finite_or_none(value: Optional[float]) -> Optional[float]:
    """Map a non-finite float to ``None`` for JSON serialization (AIR-008).

    A non-finite ``suggested_limit_price``/``limit_price``/``price`` can only
    reach a model from legacy or non-boundary-validated persisted data — the
    write paths now reject NaN/Inf — but an API *response* must be valid JSON
    regardless: ``json.dumps(float("inf"))`` emits ``Infinity`` (invalid JSON)
    on 3.12 and raises on 3.13. Emitting ``null`` instead makes both impossible.
    """

    return value if value is None or math.isfinite(value) else None


# A float that serializes to ``null`` rather than an invalid ``Infinity``/``NaN``
# in a JSON response. Validation is unchanged; only the JSON serialization is
# guarded. ``when_used="json"`` leaves ``model_dump()`` (Python) untouched so
# internal derivations are unaffected. Two variants for the optional vs required
# float fields.
ResponseSafeFloat = Annotated[
    Optional[float], PlainSerializer(_finite_or_none, when_used="json")
]
ResponseSafeRequiredFloat = Annotated[
    float,
    PlainSerializer(_finite_or_none, when_used="json", return_type=Optional[float]),
]


def utcnow() -> datetime:
    """Timezone-aware current UTC time (all persisted timestamps use this)."""

    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class TradingMode(str, Enum):
    """Beta is paper-only. ``live`` intentionally does not exist (Rule 1)."""

    PAPER = "paper"


class SessionType(str, Enum):
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class TradingState(str, Enum):
    """Session control state (Spine v2 §8 / wave 3d) — the 3-state FSM the two
    legacy booleans (``kill_switch`` / ``buys_paused``) map onto:

    * ``ACTIVE``  — normal (¬kill ∧ ¬pause).
    * ``REDUCING`` — deny exposure-INCREASING (BUY) intent; ALLOW reducing sells +
      cancels (¬kill ∧ pause). The default under stream degradation / pending
      reconciliation once those triggers exist (Phase 4).
    * ``HALTED`` — no new submissions; cancels still allowed (kill; pause
      irrelevant to enforcement, but still remembered for independent release).

    ``kill`` dominates ``pause`` (checked first everywhere today), so the four
    boolean combinations collapse to this total order with no loss of enforced
    behavior. The FSM's durable truth is the ``TRADING_STATE_CHANGED``
    ``ExecutionEvent`` (which carries the full ``(kill, pause)`` control tuple);
    ``SessionRecord.trading_state`` is a co-written read-model. See
    ``docs/SPINE_WAVE3D_PLAN.md``.
    """

    ACTIVE = "active"
    REDUCING = "reducing"
    HALTED = "halted"

    @classmethod
    def of(cls, *, kill_switch: bool, buys_paused: bool) -> "TradingState":
        """Derive the FSM state from the two control booleans (kill dominates)."""

        if kill_switch:
            return cls.HALTED
        if buys_paused:
            return cls.REDUCING
        return cls.ACTIVE


class CandidateStatus(str, Enum):
    """Proposal/review lifecycle only — stops at ``ordered`` (terminal).

    Broker-execution states are deliberately absent here; they belong to
    :class:`OrderStatus`. See ``docs/02_DATA_AND_PERSISTENCE.md``.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ORDERED = "ordered"


class SellReason(str, Enum):
    """Why a position is being exited (Phase 7 — Sell-Side Protection).

    ``manual_flatten`` is operator-initiated (always exits — the click is the
    approval, and it bypasses the kill switch as a risk-reducing exit).
    ``protection_floor`` is an autonomous hard-floor breach (pauses under the
    kill switch). A future ``auto_sell`` (Phase 8 profit-taking) attaches here
    without a new lifecycle.
    """

    MANUAL_FLATTEN = "manual_flatten"
    PROTECTION_FLOOR = "protection_floor"


class SellIntentStatus(str, Enum):
    """Sell-intent proposal/review lifecycle — parallel to
    :class:`CandidateStatus` (stops at ``ordered``; broker-execution states live
    on the Order). The sell-side analogue of the candidate lifecycle, so an exit
    decision is a first-class entity and not a sell bolted onto the buy path
    (``docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_7.md``).
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ORDERED = "ordered"


class EnvelopeStatus(str, Enum):
    """Execution-envelope lifecycle (ADR-009 §3).

    ``BREACHED`` and ``EXHAUSTED`` are terminal-pending-human — quarantine-
    flavored: recorded, never hidden, never auto-resumed. Amendment is by
    supersession only (``SUPERSEDED``); bounds never mutate in place. The
    pre-activation escape edges (``PENDING/APPROVED -> CANCELLED/EXPIRED``)
    were amended into §3 on 2026-07-11 at the WO-0016 gate.
    """

    PENDING = "pending"
    APPROVED = "approved"
    ACTIVE = "active"
    FROZEN = "frozen"  # kill switch / Halted — resumable, not terminal
    COMPLETED = "completed"
    EXPIRED = "expired"
    EXHAUSTED = "exhausted"  # cancel/replace budget spent — terminal-pending-human
    BREACHED = "breached"  # hard-rail violation attempt — terminal-pending-human
    SUPERSEDED = "superseded"  # amended: replaced by a successor envelope
    CANCELLED = "cancelled"


class EnvelopeExpiryDisposition(str, Enum):
    """Mandatory approval-time choice: what happens to the working order when
    the envelope's TTL lapses (ADR-009 §2 — a hard rail; solves the stuck
    protective LIMIT by construction)."""

    CANCEL_AND_RETURN = "cancel_and_return"
    REST_AT_FLOOR = "rest_at_floor"


class EnvelopeStaleDataDisposition(str, Enum):
    """Mandatory approval-time choice: what happens on stale/NaN/out-of-range
    market data. The policy always stops repricing (fail-closed per the safety
    rails); this only decides the resting order's fate."""

    LEAVE_RESTING = "leave_resting"
    CANCEL = "cancel"


class OrderStatus(str, Enum):
    """Broker-order lifecycle. ``submitted`` != ``filled`` (Rule 6).

    ``cancel_pending`` is a non-terminal state: a cancel has been requested at the
    broker but not yet confirmed, so the order keeps being polled — a late fill
    arriving before the venue finalizes the cancel is still recorded, never
    missed (CHAOS-1). It resolves to ``canceled`` (broker confirms) or ``filled``
    (a late fill completes it).
    """

    CREATED = "created"
    # Intermediate submission-claim state (D-017): the monitoring loop has
    # atomically claimed a CREATED order for submission — re-checked every
    # control under one store-lock hold and committed to sending it — but the
    # broker call has not yet returned. It is the *only* path from CREATED to
    # SUBMITTED, which is what makes the kill-switch/session-close race
    # unwinnable (F-001/F-002): a control flip either lands before the claim
    # (order stays CREATED, held) or after it (already committed to submission).
    # Non-terminal (it has outgoing transitions) so it counts toward CAPI
    # exposure; it carries no broker_order_id yet, so reconcile naturally skips
    # it.
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    CANCEL_PENDING = "cancel_pending"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    # Ambiguous submit outcome (ADR-002 / Spine v2 wave 3c): a timeout / HTTP 504
    # / transport failure after the submit request may have reached Alpaca. The
    # order may be live, filled, rejected, or never-arrived — we do NOT know and
    # must NOT blind-resubmit. Non-terminal (it may be live, so it counts toward
    # CAPI exposure) and carries no broker_order_id (the open-order reconcile
    # naturally skips it); it is resolved ONLY by a read-only targeted query by
    # client_order_id (monitoring `_resolve_timeout_quarantine`) into SUBMITTED /
    # REJECTED / CANCELED. The durable truth is a TIMEOUT_QUARANTINE
    # ExecutionEvent co-written with this status flip; this column is the
    # read-model. Both submit sweeps skip this status, so a quarantined order is
    # structurally unreachable by any resubmit (double-submit-safe). See
    # docs/SPINE_WAVE3C_PLAN.md.
    TIMEOUT_QUARANTINE = "timeout_quarantine"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order types.

    Beta's submission path (``app.broker.alpaca_paper.AlpacaPaperAdapter.
    submit_order``) always constructs a ``LIMIT`` order and sets Alpaca's
    ``extended_hours`` flag based on the current session at submission time
    (D-015) — the limit-only half of Rule 12 is enforced. The other half —
    actually selecting ``MARKET``/``TRAILING_STOP`` during regular hours when
    a strategy calls for it — is not yet wired up; those members exist so the
    enum can already express the allowed types once that selection logic is
    built, without a model change.
    """

    LIMIT = "limit"
    MARKET = "market"
    TRAILING_STOP = "trailing_stop"


class EventType(str, Enum):
    """Well-known audit/event types. Stored as a string so new types can be
    added without a migration; these are the ones the StateStore emits now."""

    WATCHLIST_ADDED = "watchlist_added"
    WATCHLIST_ARMED = "watchlist_armed"
    WATCHLIST_DISARMED = "watchlist_disarmed"
    WATCHLIST_REMOVED = "watchlist_removed"

    CANDIDATE_CREATED = "candidate_created"
    CANDIDATE_TRANSITION = "candidate_transition"

    ORDER_CREATED = "order_created"
    ORDER_TRANSITION = "order_transition"
    ORDER_FILL_PROGRESS = "order_fill_progress"
    ORDER_STALE = "order_stale"  # open order past the unfilled timeout (Phase 4)
    # Broker accepted an order the DB could not then mark SUBMITTED (Phase 4) —
    # a real open broker order the local state didn't capture; surfaced, never
    # left silent.
    ORDER_SUBMIT_UNPERSISTED = "order_submit_unpersisted"
    # Safety controls (Rule 8) blocking the order path (Phase 4 enforcement).
    ORDER_INTENT_BLOCKED = "order_intent_blocked"  # creation blocked by kill/pause
    ORDER_SUBMISSION_BLOCKED = "order_submission_blocked"  # loop held a submission
    # Submission-claim + durable broker-submit recovery (D-017 / Wave 0).
    ORDER_SUBMISSION_CLAIMED = "order_submission_claimed"  # CREATED -> SUBMITTING
    SUBMIT_RECOVERY_RECORDED = (
        "submit_recovery_recorded"  # a stranded broker order logged
    )
    SUBMIT_RECOVERY_RESOLVED = (
        "submit_recovery_resolved"  # recovery loop cleanly cancelled it
    )
    SUBMIT_RECOVERY_NEEDS_REVIEW = (
        "submit_recovery_needs_review"  # stranded order had fills
    )
    # A stale SUBMITTING order's idempotent re-drive hit a transient broker error
    # and was deferred to the next tick (AIR-003). Counted to bound livelock.
    STALE_SUBMITTING_REDRIVE_DEFERRED = "stale_submitting_redrive_deferred"
    # Ambiguous submit (timeout/504/transport) quarantined the order (ADR-002,
    # wave 3c); resolved once a targeted client_order_id query confirms venue
    # reality. ORDER_TIMEOUT_QUARANTINE_DEFERRED counts bounded query retries.
    ORDER_TIMEOUT_QUARANTINED = "order_timeout_quarantined"
    ORDER_TIMEOUT_QUARANTINE_RESOLVED = "order_timeout_quarantine_resolved"
    ORDER_TIMEOUT_QUARANTINE_DEFERRED = "order_timeout_quarantine_deferred"

    # Phase 4 wave 4e (acting reconcile): a venue order matching no local order —
    # external/unmanaged. Surfaced for operator review, NEVER silently absorbed into
    # managed state or folded into position (§7). Deduped by broker_order_id (one
    # record per external order, ever). Non-mutating (an audit record only).
    RECONCILE_EXTERNAL_ORDER = "reconcile_external_order"
    # Phase 4 wave 4e-3: an open order ABSENT from the venue's mass report was
    # confirmed-absent by a read-only targeted client_order_id query and, after the
    # open_check_missing_retries bound, resolved to a terminal (SUBMITTED→REJECTED /
    # PARTIALLY_FILLED→CANCELED, fills preserved). The order-status flip is
    # event-authoritative; this is the co-written audit trail.
    ORDER_RECONCILE_RESOLVED = "order_reconcile_resolved"
    # A targeted-query resolution was DEFERRED this tick — a single not-found could
    # be venue lag (§7), and a query FAILURE is never read as absent. Counts, per
    # reason, toward the retry bound; `needs_review` marks a persistently-stuck one.
    ORDER_RECONCILE_DEFERRED = "order_reconcile_deferred"
    # Phase 4 wave 4h: the broker position report diverged from the local
    # fill-derived position beyond tolerance (§7 — qty exact, avg-px 0.01%). Surfaced
    # as a durable needs_review record; position truth is NEVER overwritten from the
    # report (Rule 7). Deduped by symbol+kind so a persistent drift logs once.
    RECONCILE_POSITION_MISMATCH = "reconcile_position_mismatch"
    # A broker/local fill divergence (broker filled > locally recorded) escalated
    # to a durable needs_review reconciliation record (AIR-002).
    FILL_RECONCILIATION_NEEDED = "fill_reconciliation_needed"

    FILL_APPENDED = "fill_appended"
    FILL_DUPLICATE_IGNORED = "fill_duplicate_ignored"
    FILL_REJECTED_NEGATIVE = "fill_rejected_negative_position"
    FILL_REJECTED_INVALID = "fill_rejected_invalid"
    # ADR-001 (Spine v2 wave 3b): a broker-authoritative overfill that crosses a
    # long-only position through flat into short is RECORDED (not rejected) and
    # the symbol is QUARANTINED — autonomous order intent for it is then blocked.
    FILL_OVERFILL_QUARANTINED = "fill_overfill_quarantined"
    ORDER_INTENT_BLOCKED_QUARANTINE = "order_intent_blocked_quarantine"

    KILL_SWITCH_ENGAGED = "kill_switch_engaged"
    KILL_SWITCH_RELEASED = "kill_switch_released"
    BUYS_PAUSED = "buys_paused"
    BUYS_RESUMED = "buys_resumed"

    SESSION_OPENED = "session_opened"
    SESSION_CLOSED = "session_closed"

    # Market data feed (Phase 5): the feed has been disconnected longer than
    # the configured staleness threshold — surfaced, never silently stale
    # (D-005).
    MARKET_DATA_STALE = "market_data_stale"
    MARKET_DATA_RECOVERED = "market_data_recovered"

    # Sell-Side Protection Engine (Phase 7). The sell-intent lifecycle mirrors
    # the candidate lifecycle; protection_* events are the safety engine's own.
    SELL_INTENT_CREATED = "sell_intent_created"
    SELL_INTENT_TRANSITION = "sell_intent_transition"
    # A human flatten (X-001) deferred to an already in-flight/live PROTECTION_FLOOR
    # exit rather than duplicating it (INV-036) — the provenance record that closes
    # the "flatten click reads as success with no audit trail" gap.
    MANUAL_FLATTEN_DEFERRED = "manual_flatten_deferred"
    PROTECTION_TRIGGERED = "protection_triggered"  # floor breach -> auto exit
    PROTECTION_PAUSED = "protection_paused"  # kill switch froze auto exit
    PROTECTION_RESUMED = "protection_resumed"  # kill switch released
    PROTECTION_STALLED = "protection_stalled"  # a protective order sits unfilled


# --------------------------------------------------------------------------- #
# Spine v2 execution-event vocabulary (Phase 2 — event-sourcing scaffolding)
#
# These enums belong to the append-only ``ExecutionEvent`` log (see the
# ``ExecutionEvent`` model below and ``docs/SPINE_EXECUTION_ARCHITECTURE_v2.md``
# §4/§5/§11). They are DISTINCT from the audit ``EventType`` above: the audit
# log is a human-facing incident trail; the execution-event log is the
# replayable event-sourcing truth. Kept deliberately separate to avoid
# conflating the two logs (root ``CLAUDE.md`` conflict rule).
# --------------------------------------------------------------------------- #


class ExecutionEventType(str, Enum):
    """Vocabulary for the append-only ``ExecutionEvent`` log (Spine v2 §4/§5).

    Declared from the architecture spec so the *schema* is stable across the
    whole migration. Position projection folds only ``FILL`` (INV-1, via
    ``app/events/projectors.py``). Emission has since caught up to the schema:
    ``TRADING_STATE_CHANGED``/``QUARANTINED``/``TIMEOUT_QUARANTINE`` are emitted by
    the wave-3c/3d/3e evented paths, and the routine order-status lifecycle
    (``SUBMIT_PENDING``/``SUBMITTED``/``PARTIALLY_FILLED``/``FILLED``/``CANCELED``/
    ``REJECTED``) is emitted by both stores since WO-0007a (with faithful
    provenance, WO-0009). The order-status/spawn *projector* + read-flip is still
    open (WO-0007b): these order-status events are recorded and replay-parity-checked
    but ``orders.status`` remains authoritative until that flip. A few types remain
    declared-only vocabulary (e.g. ``ACCEPTED``, ``EXPIRED``, ``REPLACED``).
    """

    # Position-affecting fact — INV-1: only fill events change quantity.
    FILL = "fill"
    # Spawn/order venue lifecycle (§4 state model) — Phase 3 projectors.
    SUBMIT_PENDING = "submit_pending"
    # WO-0007b: the SUBMITTING -> CREATED release (claim released on a transient
    # submit failure). Completes the CREATED<->SUBMITTING cycle in the log so the
    # order-status projector's latest-event-wins fold can regress to CREATED
    # (without it, a released order projects as SUBMITTING and the claim gate
    # strands it). Occurrence-keyed like SUBMIT_PENDING.
    SUBMIT_RELEASED = "submit_released"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    # WO-0007b: entry into CANCEL_PENDING (cancel requested at the broker, not yet
    # confirmed). Emitted once on entry so a LIVE pending-cancel order is
    # representable in the projection; the self-loop (late fill progress) needs no
    # status event. Engine-initiated request => ENGINE/LOCAL, not broker-authoritative.
    CANCEL_PENDING = "cancel_pending"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REPLACED = "replaced"
    TIMEOUT_QUARANTINE = "timeout_quarantine"  # ADR-002, Phase 3
    UNKNOWN_RECONCILE_REQUIRED = "unknown_reconcile_required"
    # TradingState transition (§8) — Phase 3.
    TRADING_STATE_CHANGED = "trading_state_changed"
    # Overfill / negative-position quarantine fact (ADR-001) — Phase 3.
    QUARANTINED = "quarantined"
    # Audited operator override that scopes a single reduce-only exit while the
    # session is Halted (ADR-003 / wave 3e). A grant is scoped to {session, symbol}
    # and consumed on resolution; the global TradingState stays Halted throughout.
    EMERGENCY_REDUCE_OVERRIDE = "emergency_reduce_override"
    EMERGENCY_REDUCE_OVERRIDE_RESOLVED = "emergency_reduce_override_resolved"
    # Execution-envelope family (ADR-009 §6, provenance per ADR-008). Lifecycle
    # events carry `envelope_id` + the owning sell_intent_id as correlation_id;
    # ENVELOPE_CREATED snapshots the full bound set in `payload` so every
    # autonomous decision is replayable from the log. ENVELOPE_ACTIVATED /
    # ENVELOPE_COMPLETED / ENVELOPE_CANCELLED were amended into §6 on 2026-07-11
    # (WO-0016 gate): without them the status machine is not reconstructable
    # from events — §6's own replayability requirement.
    ENVELOPE_CREATED = "envelope_created"
    ENVELOPE_APPROVED = "envelope_approved"
    ENVELOPE_ACTIVATED = "envelope_activated"
    ENVELOPE_ACTION = "envelope_action"  # executor submit/reprice/resize/cancel
    ENVELOPE_COMPLETED = "envelope_completed"
    ENVELOPE_BREACHED = "envelope_breached"
    ENVELOPE_EXHAUSTED = "envelope_exhausted"
    ENVELOPE_EXPIRED = "envelope_expired"  # payload carries the chosen disposition
    ENVELOPE_FROZEN = "envelope_frozen"
    ENVELOPE_RESUMED = "envelope_resumed"
    ENVELOPE_SUPERSEDED = "envelope_superseded"
    ENVELOPE_CANCELLED = "envelope_cancelled"
    # Plan-time vs write-time validator disagreement (ADR-009 §5, D-3): a
    # software-defect tripwire, distinct from ENVELOPE_BREACHED.
    ENVELOPE_PLAN_DIVERGENCE = "envelope_plan_divergence"


class EventSource(str, Enum):
    """Where an ``ExecutionEvent`` originated (provenance for reconciliation).

    ``ts_init - ts_event`` is the staleness signal (§11); ``source`` records
    which ingestion path produced the event.
    """

    ENGINE = "engine"  # local single-writer engine decision
    BROKER_STREAM = "broker_stream"  # Alpaca trade-update websocket
    BROKER_REST = "broker_rest"  # Alpaca REST (status/position fetch)
    RECONCILIATION = "reconciliation"  # inferred by the reconciliation engine


class EventAuthority(str, Enum):
    """How authoritative a fact is (ADR-001).

    A ``BROKER_AUTHORITATIVE`` overfill/negative-position fact is *recorded*
    even when it violates local no-oversell expectations (Phase 3 quarantines
    rather than hides it). ``LOCAL``/``SYNTHETIC`` inputs may still be rejected
    before append. ``SYNTHETIC`` = deterministic reconciliation-inferred fact
    (§3 ``trade_id``), so restart replays dedupe identically.
    """

    BROKER_AUTHORITATIVE = "broker_authoritative"
    LOCAL = "local"
    SYNTHETIC = "synthetic"


# Replay is only valid within a single schema version; a semantics change to
# the event envelope requires a migration path (§11). Bump on any incompatible
# change to ``ExecutionEvent``'s persisted shape.
EXECUTION_EVENT_SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# Persisted entities
# --------------------------------------------------------------------------- #


class _Entity(BaseModel):
    """Base config shared by persisted models."""

    model_config = ConfigDict(use_enum_values=False, extra="forbid")


class WatchlistSymbol(_Entity):
    symbol: str
    armed: bool = False
    added_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    armed_at: Optional[datetime] = None


class Candidate(_Entity):
    id: str = Field(default_factory=new_id)
    symbol: str
    status: CandidateStatus = CandidateStatus.PENDING

    # Explanation / sizing fields (populated by the Strategy Engine in Phase 5).
    strategy: Optional[str] = None
    reason: Optional[str] = None
    risk_decision: Optional[str] = None
    suggested_quantity: Optional[int] = None
    suggested_limit_price: ResponseSafeFloat = None

    session_id: Optional[str] = None
    # Set when the candidate reaches ``ordered`` — links to the Order it produced.
    order_id: Optional[str] = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    # Transition timestamps (each set when the matching transition happens).
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    ordered_at: Optional[datetime] = None


class Order(_Entity):
    id: str = Field(default_factory=new_id)
    # An order originates from EXACTLY ONE of: a Candidate (a BUY) or a SellIntent
    # (a SELL — Phase 7). The XOR is enforced by the validator below and again at
    # the store boundary. ``candidate_id`` was required pre-Phase-7; it is now
    # nullable so a protective/flatten sell can carry ``sell_intent_id`` instead.
    candidate_id: Optional[str] = None
    sell_intent_id: Optional[str] = None
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    quantity: int
    limit_price: ResponseSafeFloat = None

    status: OrderStatus = OrderStatus.CREATED
    filled_quantity: int = 0

    # Forward-compat: a future Auto-Sell engine may cancel/replace an order.
    # Beta never populates this (see docs/02_DATA_AND_PERSISTENCE.md).
    replaces_order_id: Optional[str] = None

    # Alpaca's order id — populated only once a paper adapter exists (Phase 4).
    broker_order_id: Optional[str] = None

    session_id: Optional[str] = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _exactly_one_origin(self) -> "Order":
        """Enforce the order-origin XOR (Phase 7): an order comes from EXACTLY one
        of a Candidate (buy) or a SellIntent (sell). Both-set or neither-set is a
        structural error — a sell with no intent, or a buy mislabeled with an
        intent, must never persist. The stores re-check at their boundary too."""

        has_candidate = self.candidate_id is not None
        has_sell_intent = self.sell_intent_id is not None
        if has_candidate == has_sell_intent:
            raise ValueError(
                "order must have exactly one origin: candidate_id XOR "
                f"sell_intent_id (got candidate_id={self.candidate_id!r}, "
                f"sell_intent_id={self.sell_intent_id!r})"
            )
        return self


class SellIntent(_Entity):
    """A decision to reduce/exit an open long position (Phase 7 — Sell-Side
    Protection). The sell-side analogue of :class:`Candidate`: its own lifecycle
    (``pending → approved → ordered``), producing one SELL :class:`Order`. A
    ``manual_flatten`` intent is operator-initiated; a ``protection_floor`` intent
    is an autonomous hard-floor breach. See
    ``docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_7.md``.
    """

    id: str = Field(default_factory=new_id)
    symbol: str
    reason: SellReason
    status: SellIntentStatus = SellIntentStatus.PENDING

    # Shares to exit (capped at the live position at order-creation time — never
    # a short). For a full flatten / floor exit this is the whole position.
    target_quantity: int

    # Protection context (set for PROTECTION_FLOOR; None for MANUAL_FLATTEN):
    # the breached hard floor and the last price that triggered it.
    floor_price: ResponseSafeFloat = None
    observed_price: ResponseSafeFloat = None

    session_id: Optional[str] = None
    # Set when the intent reaches ``ordered`` — links to the SELL Order it produced.
    order_id: Optional[str] = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    ordered_at: Optional[datetime] = None


class ExecutionEnvelope(_Entity):
    """A pre-approved execution mandate for one :class:`SellIntent` (ADR-009).

    The human approves this bounded, immutable box of allowed venue behavior —
    not each order. Every field is a *hard rail* (violation attempt →
    ``BREACHED``) or a *soft bound* (policy output clamped + logged); see the
    ADR-009 §2 table. Bounds are validated at construction and NEVER mutate —
    no store exposes a bound-update path; amendment is a new envelope via
    supersession. Only ``status``, ``remaining_quantity``, ``replaces_used``,
    supersession linkage, and timestamps change after creation, each through
    a dedicated audited store operation.

    ``remaining_quantity`` is a read-model counter: it starts at
    ``qty_ceiling`` and is decremented ONLY by deduped fill events
    (``record_envelope_fill`` in both stores). Submission/ack paths
    structurally cannot touch it — there is no API that does.
    """

    id: str = Field(default_factory=new_id)

    # --- Scope (hard rails) ------------------------------------------------ #
    sell_intent_id: str
    symbol: str
    side: OrderSide = OrderSide.SELL  # locked to SELL by validator
    reduce_only: bool = True  # locked True by validator
    qty_ceiling: int
    remaining_quantity: Optional[int] = None  # defaults to qty_ceiling (validator)

    # --- Price --------------------------------------------------------------#
    # Hard: worst tolerated print; a submission below this is a breach, never
    # a clamp.
    floor_price: ResponseSafeRequiredFloat
    # Soft: policy outputs are clamped into [min, max] and logged.
    trail_distance_min: ResponseSafeRequiredFloat
    trail_distance_max: ResponseSafeRequiredFloat
    participation_rate_cap: ResponseSafeRequiredFloat  # soft, (0, 1]
    aggressiveness: list[str]  # soft: allowed aggressiveness set

    # --- Rate (hard rails) -------------------------------------------------- #
    cooldown_floor_ms: int  # min ms between reprices
    cancel_replace_budget: int  # lifetime budget; exhaustion → EXHAUSTED
    replaces_used: int = 0  # read-model counter (engine seam increments)
    max_outstanding_children: int = 1  # v1: 1

    # --- Time / data (hard rails) -------------------------------------------#
    expires_at: datetime  # TTL as an absolute deadline (injected-clock compares)
    allowed_session_phases: list[SessionType]
    expiry_disposition: EnvelopeExpiryDisposition
    stale_data_disposition: EnvelopeStaleDataDisposition

    # --- Lifecycle ----------------------------------------------------------#
    status: EnvelopeStatus = EnvelopeStatus.PENDING
    # Amendment-by-supersession linkage (both directions, set atomically by
    # the store's supersede operation).
    supersedes_id: Optional[str] = None
    superseded_by_id: Optional[str] = None
    session_id: Optional[str] = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    approved_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None  # most RECENT activation (resume restamps)
    frozen_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    exhausted_at: Optional[datetime] = None
    breached_at: Optional[datetime] = None
    superseded_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _hard_rails(self) -> "ExecutionEnvelope":
        """Reject construction that violates any ADR-009 §2 rail. Soft bounds
        still validate their *shape* — soft means clamped at runtime, not
        malformed at rest. Raising here is the fail-closed safety rail: bad
        data can never become an approved mandate."""

        if not self.sell_intent_id:
            raise ValueError("envelope requires an owning sell_intent_id")
        if not self.symbol or not self.symbol.strip():
            raise ValueError("envelope requires a symbol")
        if self.side is not OrderSide.SELL:
            raise ValueError("envelope side is locked to SELL (ADR-009 scope rail)")
        if self.reduce_only is not True:
            raise ValueError("envelope is reduce-only by construction (ADR-009)")
        if self.qty_ceiling <= 0:
            raise ValueError(f"qty_ceiling must be positive, got {self.qty_ceiling}")
        if self.remaining_quantity is None:
            self.remaining_quantity = self.qty_ceiling
        if not 0 <= self.remaining_quantity <= self.qty_ceiling:
            raise ValueError(
                f"remaining_quantity {self.remaining_quantity} outside "
                f"[0, {self.qty_ceiling}]"
            )
        if not math.isfinite(self.floor_price) or self.floor_price <= 0:
            raise ValueError(
                f"floor_price must be finite and > 0, got {self.floor_price}"
            )
        if (
            not math.isfinite(self.trail_distance_min)
            or not math.isfinite(self.trail_distance_max)
            or self.trail_distance_min <= 0
            or self.trail_distance_max < self.trail_distance_min
        ):
            raise ValueError(
                "trail distance must be a finite range with "
                f"0 < min <= max, got [{self.trail_distance_min}, "
                f"{self.trail_distance_max}]"
            )
        if (
            not math.isfinite(self.participation_rate_cap)
            or not 0 < self.participation_rate_cap <= 1
        ):
            raise ValueError(
                "participation_rate_cap must be in (0, 1], got "
                f"{self.participation_rate_cap}"
            )
        if not self.aggressiveness or any(
            not isinstance(a, str) or not a.strip() for a in self.aggressiveness
        ):
            raise ValueError("aggressiveness must be a non-empty set of names")
        if self.cooldown_floor_ms <= 0:
            raise ValueError(
                f"cooldown_floor_ms must be positive, got {self.cooldown_floor_ms}"
            )
        if self.cancel_replace_budget <= 0:
            raise ValueError(
                "cancel_replace_budget must be positive, got "
                f"{self.cancel_replace_budget}"
            )
        if not 0 <= self.replaces_used <= self.cancel_replace_budget:
            raise ValueError(
                f"replaces_used {self.replaces_used} outside "
                f"[0, {self.cancel_replace_budget}]"
            )
        if self.max_outstanding_children < 1:
            raise ValueError(
                "max_outstanding_children must be >= 1, got "
                f"{self.max_outstanding_children}"
            )
        if not self.allowed_session_phases:
            raise ValueError("allowed_session_phases must be non-empty")
        if self.supersedes_id == self.id and self.supersedes_id is not None:
            raise ValueError("an envelope cannot supersede itself")
        if self.superseded_by_id == self.id and self.superseded_by_id is not None:
            raise ValueError("an envelope cannot be superseded by itself")
        return self


class Fill(_Entity):
    """An append-only fact — no status, no transitions, no mutation.

    Repeats are handled by ``source_fill_id`` (unique when present), not by
    updating a row. See ``docs/02_DATA_AND_PERSISTENCE.md``, "Duplicate Fill
    Protection".
    """

    id: str = Field(default_factory=new_id)
    order_id: str  # the order this fill belongs to
    symbol: str
    side: OrderSide
    quantity: int
    price: ResponseSafeRequiredFloat

    # Alpaca's own fill/execution id. Unique when present; used to detect and
    # ignore duplicate observations during polling-based reconciliation.
    source_fill_id: Optional[str] = None

    # The session this fill belongs to. Stored on the row (not only threaded to
    # the audit event) so fills are date-filterable directly, without a join
    # through Order (D-007).
    session_id: Optional[str] = None

    filled_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class Position(_Entity):
    """Derived read model — folded from the append-only fill history.

    There is no setter for ``quantity``: it only ever comes from folding fills
    (Rule 7, enforced structurally). ``average_price`` is ``None`` when flat.
    """

    symbol: str
    quantity: int = 0
    cost_basis: ResponseSafeRequiredFloat = 0.0
    average_price: ResponseSafeFloat = None
    updated_at: Optional[datetime] = None  # timestamp of the most recent fill


class PositionSnapshot(_Entity):
    """A point-in-time copy of a position, captured at session close.

    Lets ``GET /api/review?date=`` answer "what did this position look like when
    the session ended" for a *closed* session, instead of re-folding today's
    live fill history (D-007). One row per symbol with a nonzero position at
    close.
    """

    id: str = Field(default_factory=new_id)
    session_id: str
    symbol: str
    quantity: int
    cost_basis: ResponseSafeRequiredFloat
    average_price: ResponseSafeFloat = None
    captured_at: datetime = Field(default_factory=utcnow)


# SubmitRecoveryRecord.cleanup_status values (D-017 / F-002).
RECOVERY_UNRESOLVED = "unresolved"  # the recovery loop is still working it
RECOVERY_RESOLVED = "resolved_canceled"  # cleanly cancelled at the broker — no position
RECOVERY_NEEDS_REVIEW = "needs_review"  # the broker order had fills — a real untracked
# position exists; a human must reconcile it
# Statuses the operator must still SEE (not cleanly resolved). The recovery loop
# itself acts only on RECOVERY_UNRESOLVED — a needs_review record is done being
# worked automatically and must not be re-cancelled.
RECOVERY_OPEN_STATUSES = frozenset({RECOVERY_UNRESOLVED, RECOVERY_NEEDS_REVIEW})

# The complete, closed set of legal cleanup_status values, and the allowed
# transitions between them (AIR-004). Free-form status strings are gone: an
# unknown value ("typo_resolved") or a silent reopen of a terminal record
# (resolved_canceled/needs_review -> unresolved) is a RecoveryTransitionError, not
# a hidden mutation. Only the recovery loop's two automatic outcomes are legal
# moves; both terminal states stay terminal (no automatic un-resolve path — a
# human clearing a needs_review record is out of band and not modeled in beta).
RECOVERY_STATUSES = frozenset(
    {RECOVERY_UNRESOLVED, RECOVERY_RESOLVED, RECOVERY_NEEDS_REVIEW}
)
RECOVERY_TRANSITIONS: dict[str, frozenset[str]] = {
    RECOVERY_UNRESOLVED: frozenset({RECOVERY_RESOLVED, RECOVERY_NEEDS_REVIEW}),
    RECOVERY_RESOLVED: frozenset(),
    RECOVERY_NEEDS_REVIEW: frozenset(),
}


class SubmitRecoveryRecord(_Entity):
    """A durable record of a broker order that was accepted upstream but whose
    local ``SUBMITTING -> SUBMITTED`` persist failed (D-017 / F-002).

    The order is *live at the broker* while the local state does not track it as
    open (it went CANCELED/REJECTED locally, e.g. a manual cancel raced the
    submit). A single best-effort cancel is not enough — if that cancel fails the
    broker order is orphaned. This record is written instead, and the monitoring
    tick's recovery step polls/cancels its ``broker_order_id`` on every cadence
    until it is confirmed resolved (not one attempt). Unresolved records are
    surfaced prominently to the operator.
    """

    id: str = Field(default_factory=new_id)
    local_order_id: str
    broker_order_id: str
    # Alpaca's client_order_id (idempotency key); the paper adapter may not
    # expose one for a given order, so it is nullable.
    client_order_id: Optional[str] = None
    symbol: str
    side: OrderSide
    quantity: int
    limit_price: ResponseSafeFloat = None
    failure_reason: str
    # RECOVERY_UNRESOLVED until the recovery loop confirms the broker order is no
    # longer live (RECOVERY_RESOLVED), or RECOVERY_NEEDS_REVIEW if it turns out to
    # have any fills (a real untracked position — surfaced, never silently
    # dropped). See app/monitoring.py's recovery step.
    cleanup_status: str = RECOVERY_UNRESOLVED
    retry_count: int = 0
    session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    last_attempt_at: Optional[datetime] = None


class Event(_Entity):
    """Append-only audit/event row."""

    id: str = Field(default_factory=new_id)
    event_type: str
    message: str = ""
    symbol: Optional[str] = None
    candidate_id: Optional[str] = None
    order_id: Optional[str] = None
    fill_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None
    # One key that ties a whole candidate (or sell-intent) lifecycle together
    # for incident reconstruction (D-020): candidate creation stamps it, and
    # every downstream event (approval, order creation, claim, submission,
    # blocked/recovery, fills, transitions) carries the same value. It is the
    # owning candidate's id — the store resolves it from the event's
    # candidate_id when not passed explicitly — OR, when candidate_id is also
    # absent, from the owning order's sell_intent_id (X-004), so a protective
    # sell's claim/submit/stale/fill/recovery events correlate too, not just
    # its creation events. One filter (GET /api/events?correlation_id=) returns
    # the full lifecycle either way. Nullable + additive: pre-D-020 rows and
    # non-candidate/non-sell-intent events (e.g. market_data_stale) are None.
    correlation_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class ExecutionEvent(_Entity):
    """Append-only event-sourcing record — the Spine v2 durable-truth log (§11).

    **Distinct from the audit :class:`Event`.** The audit log is a human-facing
    incident trail; this log is replayed through the projectors
    (``app/events/projectors.py``) to *reconstruct* state — position now, and
    primary/spawn/TradingState in Phase 3. Replay is only valid within a single
    ``schema_version``.

    Phase 2 is additive/shadow: the log exists and is proven correct in
    isolation, but no production flow writes to it yet and nothing treats it as
    authoritative. Phase 3 makes the first durable write of a migrated flow an
    ``ExecutionEvent`` (``docs/MIGRATION_MATRIX.md`` Decision 4).

    A ``FILL`` event carries ``symbol``/``side``/``quantity``/``price``/
    ``ts_event`` so the :class:`~app.events.projectors.PositionProjector` can
    reconstruct a :class:`Fill` and fold it via ``app/position.py:fold_fills``
    without a join — the folding formula is never duplicated.
    """

    id: str = Field(default_factory=new_id)
    # Monotonic per store, assigned by the store at append (1-based, gapless,
    # never reused). The replay/ordering key (§11). ``0`` means "unassigned
    # draft, not yet appended"; the store overwrites it with ``max_sequence + 1``
    # under its write lock, so a persisted event always has ``sequence >= 1``.
    sequence: int = 0
    schema_version: int = EXECUTION_EVENT_SCHEMA_VERSION
    event_type: ExecutionEventType
    source: EventSource
    authority: EventAuthority
    # Idempotency/dedup key (INV-5). For a FILL: the venue ``trade_id`` (real)
    # or a deterministic synthetic id (reconciliation). A duplicate append with
    # the same non-null ``dedupe_key`` is a no-op that returns the existing
    # event. ``None`` for events that are not deduped.
    dedupe_key: Optional[str] = None
    # Venue event time (when the broker says it happened); ``ts_init`` is local
    # ingest time. ``ts_init - ts_event`` is the latency/staleness signal (§11).
    ts_event: Optional[datetime] = None
    ts_init: datetime = Field(default_factory=utcnow)
    # Domain correlation (all nullable — an event need not name every entity).
    symbol: Optional[str] = None
    side: Optional[OrderSide] = None
    quantity: Optional[int] = None
    price: ResponseSafeFloat = None
    order_id: Optional[str] = None
    # The execution envelope this event belongs to (ADR-009 §6). Additive and
    # nullable — pre-envelope events simply have None, so replay of an existing
    # log stays valid within EXECUTION_EVENT_SCHEMA_VERSION 1 (no bump: the
    # version marks INCOMPATIBLE shape changes, models.py:~430).
    envelope_id: Optional[str] = None
    # primary/spawn ids are the §4 durable-supervisor / venue-attempt handles;
    # unused in Phase 2 (no state machine emits them yet), declared for schema
    # stability so Phase 3 does not churn the envelope.
    primary_id: Optional[str] = None
    spawn_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SessionRecord(_Entity):
    """A trading session and its control flags.

    The *active* session is what ``GET /api/session`` reflects; closed sessions
    are queried by date via ``GET /api/review?date=`` (history persists across
    days). Mode is always ``paper`` in beta.
    """

    id: str = Field(default_factory=new_id)
    session_date: str  # ISO date "YYYY-MM-DD"
    mode: TradingMode = TradingMode.PAPER
    # Not persisted meaningfully — GET /api/session overlays this live from
    # session_type_for(utcnow()) on every read rather than a stored value,
    # since a single day's session spans all three windows as wall-clock time
    # passes (see routes_system.py's session() docstring). Left as a plain
    # column here (not removed) only because the field/model shape is shared
    # with reading rows back out of storage.
    session_type: Optional[SessionType] = None
    status: SessionStatus = SessionStatus.ACTIVE

    kill_switch: bool = False
    buys_paused: bool = False
    # Spine v2 §8 / wave 3d: the 3-state control FSM enforcement decides off. Its
    # durable truth is the TRADING_STATE_CHANGED ExecutionEvent log; this column is
    # a co-written read-model. TODAY (wave 3d) the two booleans are its ONLY driver
    # so it equals TradingState.of(kill, buys_paused); the store setters are the
    # single mutation seam that co-writes it (see _apply_control_change in both
    # stores). It is deliberately an INDEPENDENT field, NOT a pure derivation of the
    # booleans: §8 makes `Reducing` "the default under stream degradation or pending
    # reconciliation", so Phase 4 will drive it to REDUCING from stream/reconcile
    # signals WITHOUT touching buys_paused — a validator/@property that forced
    # trading_state == of(kill, pause) would silently heal that away (an all-stop
    # bypass). Construct it consistently (the store always does); tests that build a
    # record directly derive it via TradingState.of the same way the store would.
    trading_state: TradingState = TradingState.ACTIVE

    opened_at: datetime = Field(default_factory=utcnow)
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
