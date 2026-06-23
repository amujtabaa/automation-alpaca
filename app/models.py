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

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


def new_id() -> str:
    """A fresh opaque identifier (uuid4 hex)."""

    return uuid.uuid4().hex


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


class OrderStatus(str, Enum):
    """Broker-order lifecycle. ``submitted`` != ``filled`` (Rule 6)."""

    CREATED = "created"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order types. Session policy (Rule 12) is enforced later, not in beta;
    the enum simply has to be able to express the allowed types."""

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
    suggested_limit_price: Optional[float] = None

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
    candidate_id: str  # the candidate this order was produced from
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    quantity: int
    limit_price: Optional[float] = None

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
    price: float

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
    cost_basis: float = 0.0
    average_price: Optional[float] = None
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
    cost_basis: float
    average_price: Optional[float] = None
    captured_at: datetime = Field(default_factory=utcnow)


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
    created_at: datetime = Field(default_factory=utcnow)


class SessionRecord(_Entity):
    """A trading session and its control flags.

    The *active* session is what ``GET /api/session`` reflects; closed sessions
    are queried by date via ``GET /api/review?date=`` (history persists across
    days). Mode is always ``paper`` in beta.
    """

    id: str = Field(default_factory=new_id)
    session_date: str  # ISO date "YYYY-MM-DD"
    mode: TradingMode = TradingMode.PAPER
    session_type: Optional[SessionType] = None
    status: SessionStatus = SessionStatus.ACTIVE

    kill_switch: bool = False
    buys_paused: bool = False

    opened_at: datetime = Field(default_factory=utcnow)
    closed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
