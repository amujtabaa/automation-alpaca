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
    SUBMIT_RECOVERY_RECORDED = "submit_recovery_recorded"  # a stranded broker order logged
    SUBMIT_RECOVERY_RESOLVED = "submit_recovery_resolved"  # recovery loop cleanly cancelled it
    SUBMIT_RECOVERY_NEEDS_REVIEW = "submit_recovery_needs_review"  # stranded order had fills
    # A stale SUBMITTING order's idempotent re-drive hit a transient broker error
    # and was deferred to the next tick (AIR-003). Counted to bound livelock.
    STALE_SUBMITTING_REDRIVE_DEFERRED = "stale_submitting_redrive_deferred"
    # A broker/local fill divergence (broker filled > locally recorded) escalated
    # to a durable needs_review reconciliation record (AIR-002).
    FILL_RECONCILIATION_NEEDED = "fill_reconciliation_needed"

    FILL_APPENDED = "fill_appended"
    FILL_DUPLICATE_IGNORED = "fill_duplicate_ignored"
    FILL_REJECTED_NEGATIVE = "fill_rejected_negative_position"
    FILL_REJECTED_INVALID = "fill_rejected_invalid"

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
    PROTECTION_TRIGGERED = "protection_triggered"      # floor breach -> auto exit
    PROTECTION_PAUSED = "protection_paused"            # kill switch froze auto exit
    PROTECTION_RESUMED = "protection_resumed"          # kill switch released
    PROTECTION_STALLED = "protection_stalled"          # a protective order sits unfilled


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
    whole migration. **Phase 2 only projects ``FILL``** (position, via
    ``app/events/projectors.py``). The order/spawn lifecycle and
    ``TRADING_STATE_CHANGED``/``QUARANTINED`` types are declared here for schema
    stability but their projectors (primary/spawn/TradingState) land in Phase 3,
    where those state machines are actually built — see
    ``docs/SPINE_MIGRATION_PROGRESS.md``. Declaring vocabulary is not
    implementing behavior; nothing in Phase 2 *emits* or *projects* these yet.
    """

    # Position-affecting fact — INV-1: only fill events change quantity.
    FILL = "fill"
    # Spawn/order venue lifecycle (§4 state model) — Phase 3 projectors.
    SUBMIT_PENDING = "submit_pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REPLACED = "replaced"
    TIMEOUT_QUARANTINE = "timeout_quarantine"            # ADR-002, Phase 3
    UNKNOWN_RECONCILE_REQUIRED = "unknown_reconcile_required"
    # TradingState transition (§8) — Phase 3.
    TRADING_STATE_CHANGED = "trading_state_changed"
    # Overfill / negative-position quarantine fact (ADR-001) — Phase 3.
    QUARANTINED = "quarantined"


class EventSource(str, Enum):
    """Where an ``ExecutionEvent`` originated (provenance for reconciliation).

    ``ts_init - ts_event`` is the staleness signal (§11); ``source`` records
    which ingestion path produced the event.
    """

    ENGINE = "engine"                  # local single-writer engine decision
    BROKER_STREAM = "broker_stream"    # Alpaca trade-update websocket
    BROKER_REST = "broker_rest"        # Alpaca REST (status/position fetch)
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
RECOVERY_UNRESOLVED = "unresolved"          # the recovery loop is still working it
RECOVERY_RESOLVED = "resolved_canceled"     # cleanly cancelled at the broker — no position
RECOVERY_NEEDS_REVIEW = "needs_review"      # the broker order had fills — a real untracked
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

    opened_at: datetime = Field(default_factory=utcnow)
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
