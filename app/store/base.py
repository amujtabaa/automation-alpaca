"""The ``StateStore`` interface — the only way callers touch persisted truth.

Two implementations exist: :class:`~app.store.memory.InMemoryStateStore` (tests,
IO-free) and :class:`~app.store.sqlite.SqliteStateStore` (the running app).
Swapping SQLite for Postgres later touches only the implementation, not these
signatures or any caller.

Key structural guarantees the interface is shaped to enforce:

* Candidate transitions accept only :class:`CandidateStatus`; order transitions
  only :class:`OrderStatus`. There is no method to put a broker-execution state
  on a candidate.
* Fills are *append-only*: there is exactly one fill-writing method
  (:meth:`StateStore.append_fill`) and no update/delete for fills.
* Position is read-only and derived — no ``set_position`` exists.
* Every mutating method that writes more than one row is atomic (see each
  implementation) and writes an audit/event row.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, Optional

from app.models import (
    Candidate,
    CandidateStatus,
    Event,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSnapshot,
    SessionRecord,
    WatchlistSymbol,
)


# A bounded ticker domain: a leading letter then up to nine more of
# letters/digits/dot/dash (covers e.g. AAPL, BRK.B, BF-B). Keeps overly long,
# unicode, whitespace, path-like, or SQL-looking strings out of durable trading
# data (DATA-2). SQL is already parameterized; this is a data-quality/blast-
# radius guard, not an injection fix.
_SYMBOL_RE = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")


def normalize_symbol(symbol: str) -> str:
    """Canonical symbol form used as the watchlist/position key.

    Normalization lives in the store so every caller (and both
    implementations) keys symbols identically — the UI never has to. Rejects a
    blank or out-of-domain symbol with ``ValueError`` (route handlers surface it
    as 422).
    """

    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol must be a non-empty string")
    if not _SYMBOL_RE.fullmatch(normalized):
        raise ValueError(
            f"symbol {symbol!r} is not a valid ticker (expected 1-10 chars: a "
            f"leading letter then letters/digits/'.'/'-')"
        )
    return normalized


class StoreError(Exception):
    """Base class for StateStore errors."""


class UnknownEntityError(StoreError):
    """Referenced entity (candidate, order, ...) does not exist."""


class CandidateTransitionError(StoreError):
    """An illegal candidate lifecycle transition was attempted.

    e.g. approving a candidate that is already ``rejected``/``expired`` without
    an explicit return to ``pending`` (beta provides no such return).
    """


class OrderTransitionError(StoreError):
    """An illegal order lifecycle transition was attempted."""


class InvalidFillError(StoreError):
    """A fill was rejected at the store boundary for a bad value or a mismatch
    against its order (D-010).

    Covers: non-positive ``quantity``/``price``; a fill whose symbol or side
    does not match the referenced order; and cumulative filled quantity for an
    order exceeding the order's quantity. A *missing* order is reported as
    :class:`UnknownEntityError`, and a sell that would go short remains
    :class:`~app.position.NegativePositionError`; this error is specifically
    "the fill itself is malformed or inconsistent with its order."
    """


class InvalidOrderError(StoreError):
    """An order operation was rejected for invalid inputs (D-010).

    Raised by ``create_order`` when the order's symbol does not match its
    candidate, and by ``transition_order`` when ``filled_quantity`` is out of
    range (`0 <= filled_quantity <= order.quantity`) or would move backward
    (no broker-correction path exists in beta). A *missing* candidate is
    reported as :class:`UnknownEntityError`.
    """


class SessionAlreadyClosedError(StoreError):
    """``close_session`` was called on a session that is already closed.

    Closing is deliberately not idempotent (unlike candidate approve/reject):
    re-closing would re-snapshot a position that may have changed, so the second
    call is rejected explicitly.
    """


class OrderIntentBlockedError(StoreError):
    """New order intent was blocked by a safety control (Rule 8).

    Raised by ``create_order_for_candidate`` when the candidate's session has the
    kill switch engaged (blocks *all* new order intent) or buys paused (blocks
    new BUY intent — beta orders are long-only buys). The flag is persisted state
    the backend owns; enforcing it here (not only in the UI) means every order-
    intent producer — the approve route now, a future auto-buy engine — is gated,
    and the block is recorded as an audit event. Distinct from the Phase 6 CAPI
    risk limits (max shares/notional/exposure), which remain out of scope.
    """


class SessionClosedError(StoreError):
    """A new candidate was attempted against a *closed* session.

    Closing a session ends the trading day (D-009): ``create_candidate`` refuses
    to attach a fresh candidate to a closed session, since it would sit outside
    the point-in-time review snapshot captured at close. This guard is on
    candidate *creation* only. It deliberately does **not** block order dispatch,
    fill append, or order transitions for an order that already exists — those
    must keep working after close so an in-flight order is tracked to a terminal
    state (D-011). In practice dispatch can't happen in a closed session anyway,
    because close expires every open (pending/approved) candidate first. Distinct
    from :class:`SessionAlreadyClosedError`, which is specifically about
    re-closing.
    """


@dataclass(frozen=True)
class FillAppendResult:
    """Outcome of :meth:`StateStore.append_fill`.

    ``status`` is ``"appended"`` when a new fill row was written, or
    ``"duplicate"`` when a fill with the same ``source_fill_id`` already existed
    (no row written, position untouched, a duplicate-ignored audit event
    recorded). A sell that would go negative does not return here — it raises
    :class:`~app.position.NegativePositionError`.
    """

    status: Literal["appended", "duplicate"]
    fill: Optional[Fill]
    event: Event


class StateStore(ABC):
    """Abstract persistence interface. All methods are async."""

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def initialize(self) -> None:
        """Idempotent setup (create schema, ensure a current session exists).

        Safe to call on every startup.
        """

    async def close(self) -> None:  # pragma: no cover - default no-op
        """Release resources (e.g. a SQLite connection). Default: no-op."""

    # ------------------------------------------------------------------ #
    # Watchlist
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def add_watchlist_symbol(
        self, symbol: str, *, armed: bool = False
    ) -> WatchlistSymbol:
        """Add a symbol (idempotent: returns the existing row if present)."""

    @abstractmethod
    async def list_watchlist(self) -> list[WatchlistSymbol]:
        ...

    @abstractmethod
    async def get_watchlist_symbol(self, symbol: str) -> Optional[WatchlistSymbol]:
        ...

    @abstractmethod
    async def set_watchlist_armed(
        self, symbol: str, armed: bool
    ) -> WatchlistSymbol:
        """Arm/disarm a symbol. Raises :class:`UnknownEntityError` if absent."""

    @abstractmethod
    async def remove_watchlist_symbol(self, symbol: str) -> bool:
        """Delete a symbol (explicit command). Returns True if it existed."""

    # ------------------------------------------------------------------ #
    # Candidates (proposal lifecycle: pending/approved/rejected/expired/ordered)
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def create_candidate(
        self,
        symbol: str,
        *,
        strategy: Optional[str] = None,
        reason: Optional[str] = None,
        risk_decision: Optional[str] = None,
        suggested_quantity: Optional[int] = None,
        suggested_limit_price: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> Candidate:
        ...

    @abstractmethod
    async def list_candidates(
        self,
        *,
        session_id: Optional[str] = None,
        status: Optional[CandidateStatus] = None,
    ) -> list[Candidate]:
        ...

    @abstractmethod
    async def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        ...

    @abstractmethod
    async def transition_candidate(
        self,
        candidate_id: str,
        new_status: CandidateStatus,
        *,
        order_id: Optional[str] = None,
    ) -> Candidate:
        """Atomically transition a candidate and write an audit event.

        ``new_status`` is typed as :class:`CandidateStatus`, so a broker state
        cannot be passed here.
        """

    # ------------------------------------------------------------------ #
    # Orders (broker lifecycle: created/submitted/partially_filled/filled/...)
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def create_order(
        self,
        candidate_id: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        *,
        order_type: OrderType = OrderType.LIMIT,
        limit_price: Optional[float] = None,
        replaces_order_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Order:
        ...

    @abstractmethod
    async def create_order_for_candidate(self, candidate_id: str) -> Order:
        """Atomic ``APPROVED → ORDERED`` handoff — the candidate→order dispatch.

        ``docs/02_DATA_AND_PERSISTENCE.md`` lists *"candidate approval + order
        creation + audit event"* as one atomic group, so this is a single store
        operation (one SQL transaction in :class:`SqliteStateStore`; one lock
        acquisition in :class:`InMemoryStateStore`), not two sequential calls.
        It is deliberately separate from ``transition_candidate`` and from the
        Approval Gate: the ``ordered`` transition is never buried inside either
        (Phase 3 prompt §3 / D-006).

        On an ``APPROVED`` candidate it: creates the paper order (a long-only
        ``BUY`` ``LIMIT`` order whose quantity/limit come from the candidate's
        ``suggested_quantity`` / ``suggested_limit_price``), transitions the
        candidate to ``ORDERED`` linking the new order, and writes both the
        ``order_created`` and ``candidate_transition`` audit events — all
        atomically. No network call (Phase 4 submits to Alpaca).

        **Idempotent:** a candidate already ``ORDERED`` returns its existing order
        and writes nothing (no second order). This is what keeps the approve
        endpoint idempotent.

        Raises :class:`UnknownEntityError` if the candidate does not exist;
        :class:`CandidateTransitionError` if it is not ``APPROVED`` (e.g. still
        ``PENDING``, or ``REJECTED``/``EXPIRED``); :class:`InvalidOrderError` if it
        carries no positive ``suggested_quantity`` to size the order. This is
        where the *approved-only* rule that ``create_order`` deliberately deferred
        (D-010) is finally enforced.
        """

    @abstractmethod
    async def revert_candidate_approval(self, candidate_id: str) -> Candidate:
        """Atomically revert ``APPROVED → PENDING`` when dispatch was refused.

        Recovery for the approve/dispatch race (D-013): if a safety control flips
        between the approve transition and the order-creation handoff, the store
        refuses the order (``OrderIntentBlockedError``) but the candidate is
        already ``APPROVED`` — stranded ``APPROVED`` with no order under a safety
        stop. The approve route calls this to put it back to ``PENDING`` (still
        rejectable / re-approvable). Acts **only** on an ``APPROVED`` candidate
        with no linked order; otherwise it is an idempotent no-op (so a candidate
        that actually became ``ORDERED`` is never disturbed). Atomic + audited.
        """

    @abstractmethod
    async def list_orders(
        self,
        *,
        session_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
    ) -> list[Order]:
        ...

    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        ...

    @abstractmethod
    async def transition_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        filled_quantity: Optional[int] = None,
        broker_order_id: Optional[str] = None,
    ) -> Order:
        """Atomically transition an order and write an audit event."""

    # ------------------------------------------------------------------ #
    # Fills (append-only; the only thing that mutates position)
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def append_fill(
        self,
        order_id: str,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        *,
        source_fill_id: Optional[str] = None,
        filled_at: Optional[Any] = None,
        session_id: Optional[str] = None,
    ) -> FillAppendResult:
        """Append a fill atomically (append + dedup check + audit event).

        * If ``source_fill_id`` duplicates an existing fill: no row is written,
          position is untouched, a duplicate-ignored event is recorded, and the
          result's ``status`` is ``"duplicate"``.
        * If the fill is a sell that would drive the symbol's quantity below
          zero: no row is written, a rejection event is recorded, and
          :class:`~app.position.NegativePositionError` is raised.
        * Otherwise the fill is appended and ``status`` is ``"appended"``.
        """

    @abstractmethod
    async def list_fills(
        self,
        *,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[Fill]:
        ...

    # ------------------------------------------------------------------ #
    # Positions (derived, read-only — folded from fills)
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def get_position(self, symbol: str) -> Position:
        """Derived position for one symbol (flat Position if no fills)."""

    @abstractmethod
    async def list_positions(self) -> list[Position]:
        """Derived positions for every symbol that has fills."""

    # ------------------------------------------------------------------ #
    # Events / audit log (append-only)
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def append_event(
        self,
        event_type: str,
        *,
        message: str = "",
        symbol: Optional[str] = None,
        candidate_id: Optional[str] = None,
        order_id: Optional[str] = None,
        fill_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Event:
        ...

    @abstractmethod
    async def list_events(
        self,
        *,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        ...

    # ------------------------------------------------------------------ #
    # Sessions / control flags
    # ------------------------------------------------------------------ #
    @abstractmethod
    async def get_current_session(self) -> SessionRecord:
        """The active session (creating today's if none is active)."""

    @abstractmethod
    async def get_session_by_date(self, day: date) -> Optional[SessionRecord]:
        ...

    @abstractmethod
    async def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        """The session with this id, or ``None``.

        Used by the monitoring loop to gate a held order's submission against its
        **own** originating session (D-013a), independent of which session is
        currently live.
        """

    @abstractmethod
    async def list_sessions(self) -> list[SessionRecord]:
        ...

    @abstractmethod
    async def set_kill_switch(self, engaged: bool) -> SessionRecord:
        """Persist the kill-switch flag on the active session (atomic + audit).

        Beta only persists the flag; enforcement on order intent arrives with
        the order path (out of scope now — see the implementation prompt).
        """

    @abstractmethod
    async def set_buys_paused(self, paused: bool) -> SessionRecord:
        """Persist the pause-buys flag on the active session (atomic + audit)."""

    @abstractmethod
    async def close_session(
        self, session_id: Optional[str] = None
    ) -> SessionRecord:
        """Close a session (default: the active one). Atomically:

        1. Transition every ``PENDING``/``APPROVED`` candidate in this session
           to ``EXPIRED`` (terminal candidates are left untouched).
        2. Cancel every still-``CREATED`` (never-submitted) order in this
           session (D-013a) — a clean terminal state instead of a zombie
           ``CREATED`` order the per-order-session submission gate would
           otherwise hold forever. Already-``SUBMITTED`` orders are untouched
           and keep reconciling after close (D-011).
        3. Snapshot current positions — every symbol with a nonzero derived
           quantity — into ``position_snapshots``, keyed by this session id.
        4. Set ``status=CLOSED`` and ``closed_at=now``.
        5. Write one audit event recording the close, how many candidates
           were expired, and how many orders were canceled.

        Raises :class:`SessionAlreadyClosedError` if the session is already
        closed, and :class:`UnknownEntityError` if ``session_id`` is unknown.
        Automatic, window-driven close is out of scope here (needs a monitoring
        loop) — this is the manual trigger only.
        """

    @abstractmethod
    async def list_position_snapshots(
        self, session_id: str
    ) -> list[PositionSnapshot]:
        """The position snapshots captured when ``session_id`` was closed."""
