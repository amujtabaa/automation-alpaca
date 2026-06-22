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
    SessionType,
    WatchlistSymbol,
)


def normalize_symbol(symbol: str) -> str:
    """Canonical symbol form used as the watchlist/position key.

    Normalization lives in the store so every caller (and both
    implementations) keys symbols identically — the UI never has to.
    """

    normalized = symbol.strip().upper()
    if not normalized:
        raise ValueError("symbol must be a non-empty string")
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


class SessionAlreadyClosedError(StoreError):
    """``close_session`` was called on a session that is already closed.

    Closing is deliberately not idempotent (unlike candidate approve/reject):
    re-closing would re-snapshot a position that may have changed, so the second
    call is rejected explicitly.
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
    async def list_sessions(self) -> list[SessionRecord]:
        ...

    @abstractmethod
    async def set_session_type(self, session_type: SessionType) -> SessionRecord:
        """Set the active session's type (atomic + audit event)."""

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
        2. Snapshot current positions — every symbol with a nonzero derived
           quantity — into ``position_snapshots``, keyed by this session id.
        3. Set ``status=CLOSED`` and ``closed_at=now``.
        4. Write one audit event recording the close and how many candidates
           were expired.

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
