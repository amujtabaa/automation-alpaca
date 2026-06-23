"""In-memory StateStore — used by unit tests, never touches disk or network.

All mutating operations run under a single ``asyncio.Lock`` (serializing
coroutines), **and** every multi-row mutation runs inside ``self._atomic()`` so a
failed audit-event write rolls the whole operation back — all-or-nothing exactly
like ``SqliteStateStore``'s SQL transaction (see ``docs/02_DATA_AND_PERSISTENCE.md``,
"Mutating Operations Are Atomic"). The lock alone is *not* sufficient: it prevents
interleaving but not a half-applied write if a mutation raises after the state
change but before (or during) its audit event — ``_atomic`` snapshots state on
enter and restores it on any exception (Item 4 / BE-1).

The lock is **not** reentrant, so public methods acquire it once and then call
private ``*_unlocked`` helpers (which never re-acquire it) to do the raw work,
including writing audit events.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import date
from typing import Any, Iterator, Optional

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
    SessionStatus,
    SessionType,
    TradingMode,
    WatchlistSymbol,
    utcnow,
)
from app.position import NegativePositionError, fold_fills, would_go_negative
from app.store.base import (
    CandidateTransitionError,
    FillAppendResult,
    InvalidFillError,
    InvalidOrderError,
    OrderIntentBlockedError,
    OrderTransitionError,
    SessionAlreadyClosedError,
    SessionClosedError,
    StateStore,
    UnknownEntityError,
    normalize_symbol,
)
from app.store.transitions import (
    CANDIDATE_TIMESTAMP as _CANDIDATE_TIMESTAMP,
    CANDIDATE_TRANSITIONS as _CANDIDATE_TRANSITIONS,
    ORDER_TIMESTAMP as _ORDER_TIMESTAMP,
    ORDER_TRANSITIONS as _ORDER_TRANSITIONS,
)
from app.store.validation import (
    fill_order_match_reason,
    fill_value_reason,
    filled_quantity_reason,
    limit_price_reason,
    order_candidate_match_reason,
    order_intent_block_reason,
)


class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._watchlist: dict[str, WatchlistSymbol] = {}
        self._candidates: dict[str, Candidate] = {}
        self._orders: dict[str, Order] = {}
        self._fills: list[Fill] = []  # append-only, insertion order
        # Dedup keyed per-(order_id, source_fill_id) (Item 5 / F1): two different
        # orders reporting a fill with the same source_fill_id must not swallow
        # the second. Same-order replays are still ignored.
        self._fill_source_ids: set[tuple[str, str]] = set()
        self._events: list[Event] = []  # append-only, insertion order
        self._sessions: list[SessionRecord] = []
        self._position_snapshots: list[PositionSnapshot] = []

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def initialize(self) -> None:
        async with self._lock:
            with self._atomic():
                self._ensure_current_session_unlocked()

    # ------------------------------------------------------------------ #
    # Internal helpers (assume the lock is held)
    # ------------------------------------------------------------------ #
    @contextlib.contextmanager
    def _atomic(self) -> Iterator[None]:
        """All-or-nothing for a multi-row in-memory mutation (Item 4 / BE-1).

        Snapshots store state on enter; on ANY exception restores it, so a failed
        audit-event append can't leave a half-applied mutation (a fill recorded
        without its ``fill_appended`` event and a poisoned dedup set; a flipped
        control flag with no audit row). Mirrors ``SqliteStateStore``'s
        BEGIN/COMMIT/ROLLBACK.

        Collections whose elements are mutated in place (watchlist, candidates,
        orders, sessions) are deep-copied; append-only collections (fills,
        events, snapshots) and the dedup set are shallow-copied — restoring the
        prior contents is enough since their elements are never mutated. The
        snapshot cost is negligible at beta's single-user scale; correctness and
        SQLite parity matter more.
        """

        saved_watchlist = {
            k: v.model_copy(deep=True) for k, v in self._watchlist.items()
        }
        saved_candidates = {
            k: v.model_copy(deep=True) for k, v in self._candidates.items()
        }
        saved_orders = {k: v.model_copy(deep=True) for k, v in self._orders.items()}
        saved_fills = list(self._fills)
        saved_source_ids = set(self._fill_source_ids)
        saved_events = list(self._events)
        saved_sessions = [s.model_copy(deep=True) for s in self._sessions]
        saved_snapshots = list(self._position_snapshots)
        try:
            yield
        except BaseException:
            self._watchlist = saved_watchlist
            self._candidates = saved_candidates
            self._orders = saved_orders
            self._fills = saved_fills
            self._fill_source_ids = saved_source_ids
            self._events = saved_events
            self._sessions = saved_sessions
            self._position_snapshots = saved_snapshots
            raise

    def _append_event_unlocked(
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
        event = Event(
            event_type=str(event_type),
            message=message,
            symbol=symbol,
            candidate_id=candidate_id,
            order_id=order_id,
            fill_id=fill_id,
            payload=payload or {},
            session_id=session_id,
        )
        self._events.append(event)
        return event.model_copy(deep=True)

    def _ensure_current_session_unlocked(self) -> SessionRecord:
        # One session per calendar date (D-009). If today already has a session
        # — active *or* closed — return it; never conjure a second one. Closing
        # a session ends the trading day, so a closed today-session is a valid
        # thing to return (and to show in the UI) until a genuinely new day.
        today = utcnow().date().isoformat()
        for session in reversed(self._sessions):
            if session.session_date == today:
                return session
        session = SessionRecord(session_date=today, mode=TradingMode.PAPER)
        self._sessions.append(session)
        self._append_event_unlocked(
            "session_opened",
            message=f"session opened for {today}",
            session_id=session.id,
        )
        return session

    def _fills_for_symbol_unlocked(self, symbol: str) -> list[Fill]:
        return [f for f in self._fills if f.symbol == symbol]

    def _position_unlocked(self, symbol: str) -> Position:
        return fold_fills(symbol, self._fills_for_symbol_unlocked(symbol))

    # ------------------------------------------------------------------ #
    # Watchlist
    # ------------------------------------------------------------------ #
    async def add_watchlist_symbol(
        self, symbol: str, *, armed: bool = False
    ) -> WatchlistSymbol:
        key = normalize_symbol(symbol)
        async with self._lock:
            existing = self._watchlist.get(key)
            if existing is not None:
                return existing.model_copy(deep=True)
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                now = utcnow()
                entry = WatchlistSymbol(
                    symbol=key,
                    armed=armed,
                    added_at=now,
                    updated_at=now,
                    armed_at=now if armed else None,
                )
                self._watchlist[key] = entry
                self._append_event_unlocked(
                    "watchlist_added",
                    message=f"{key} added",
                    symbol=key,
                    session_id=session.id,
                )
            return entry.model_copy(deep=True)

    async def list_watchlist(self) -> list[WatchlistSymbol]:
        async with self._lock:
            return [e.model_copy(deep=True) for e in self._watchlist.values()]

    async def get_watchlist_symbol(self, symbol: str) -> Optional[WatchlistSymbol]:
        key = normalize_symbol(symbol)
        async with self._lock:
            entry = self._watchlist.get(key)
            return entry.model_copy(deep=True) if entry else None

    async def set_watchlist_armed(self, symbol: str, armed: bool) -> WatchlistSymbol:
        key = normalize_symbol(symbol)
        async with self._lock:
            entry = self._watchlist.get(key)
            if entry is None:
                raise UnknownEntityError(f"watchlist symbol {key} not found")
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                entry.armed = armed
                entry.armed_at = utcnow() if armed else None
                entry.updated_at = utcnow()
                self._append_event_unlocked(
                    "watchlist_armed" if armed else "watchlist_disarmed",
                    message=f"{key} {'armed' if armed else 'disarmed'}",
                    symbol=key,
                    session_id=session.id,
                )
            return entry.model_copy(deep=True)

    async def remove_watchlist_symbol(self, symbol: str) -> bool:
        key = normalize_symbol(symbol)
        async with self._lock:
            if key not in self._watchlist:
                return False
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                del self._watchlist[key]
                self._append_event_unlocked(
                    "watchlist_removed",
                    message=f"{key} removed",
                    symbol=key,
                    session_id=session.id,
                )
            return True

    # ------------------------------------------------------------------ #
    # Candidates
    # ------------------------------------------------------------------ #
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
        key = normalize_symbol(symbol)
        async with self._lock:
            # Default to the active session so close/expiry and date-scoped
            # review see this candidate (Fix 7). An explicit session_id wins.
            if session_id is None:
                session = self._ensure_current_session_unlocked()
                session_id = session.id
            else:
                session = next(
                    (s for s in self._sessions if s.id == session_id), None
                )
            # No new candidates in a closed session (D-009 / F2): the trading day
            # is over, and a post-close candidate would sit outside the captured
            # review snapshot. Guard at the store boundary so every future
            # producer (Phase 5) is covered, not only the dev route.
            if session is not None and session.status is SessionStatus.CLOSED:
                raise SessionClosedError(
                    f"session {session_id} is closed; cannot create candidate"
                )
            candidate = Candidate(
                symbol=key,
                strategy=strategy,
                reason=reason,
                risk_decision=risk_decision,
                suggested_quantity=suggested_quantity,
                suggested_limit_price=suggested_limit_price,
                session_id=session_id,
            )
            with self._atomic():
                self._candidates[candidate.id] = candidate
                self._append_event_unlocked(
                    "candidate_created",
                    message=f"candidate created for {key}",
                    symbol=key,
                    candidate_id=candidate.id,
                    session_id=session_id,
                )
            return candidate.model_copy(deep=True)

    async def list_candidates(
        self,
        *,
        session_id: Optional[str] = None,
        status: Optional[CandidateStatus] = None,
    ) -> list[Candidate]:
        async with self._lock:
            out = []
            for c in self._candidates.values():
                if session_id is not None and c.session_id != session_id:
                    continue
                if status is not None and c.status is not status:
                    continue
                out.append(c.model_copy(deep=True))
            return out

    async def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        async with self._lock:
            c = self._candidates.get(candidate_id)
            return c.model_copy(deep=True) if c else None

    async def transition_candidate(
        self,
        candidate_id: str,
        new_status: CandidateStatus,
        *,
        order_id: Optional[str] = None,
    ) -> Candidate:
        async with self._lock:
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                raise UnknownEntityError(f"candidate {candidate_id} not found")
            current = candidate.status
            if new_status is current:
                # Idempotent no-op (e.g. approving an already-approved
                # candidate): write no event and mutate nothing — including
                # order_id, which is set only on the real APPROVED -> ORDERED
                # transition. A stray order_id arg here is ignored, not applied
                # (Fix 6 / D-008 philosophy).
                return candidate.model_copy(deep=True)
            if new_status not in _CANDIDATE_TRANSITIONS.get(current, set()):
                raise CandidateTransitionError(
                    f"illegal candidate transition {current.value} -> "
                    f"{new_status.value}"
                )
            with self._atomic():
                candidate.status = new_status
                candidate.updated_at = utcnow()
                ts_field = _CANDIDATE_TIMESTAMP.get(new_status)
                if ts_field:
                    setattr(candidate, ts_field, utcnow())
                if new_status is CandidateStatus.ORDERED and order_id is not None:
                    candidate.order_id = order_id
                self._append_event_unlocked(
                    "candidate_transition",
                    message=f"candidate {current.value} -> {new_status.value}",
                    symbol=candidate.symbol,
                    candidate_id=candidate.id,
                    order_id=order_id,
                    payload={"from": current.value, "to": new_status.value},
                    session_id=candidate.session_id,
                )
            return candidate.model_copy(deep=True)

    # ------------------------------------------------------------------ #
    # Orders
    # ------------------------------------------------------------------ #
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
        key = normalize_symbol(symbol)
        async with self._lock:
            # Validate the order against its candidate (Fix 4). Existence +
            # symbol match only — the approved-only rule and the auto-ORDERED
            # transition belong to Phase 3's Approval Gate (D-010), not here.
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                raise UnknownEntityError(f"candidate {candidate_id} not found")
            mismatch = order_candidate_match_reason(candidate, key)
            if mismatch is not None:
                raise InvalidOrderError(
                    f"order symbol {key} does not match candidate "
                    f"{candidate.symbol} ({mismatch})"
                )
            order = Order(
                candidate_id=candidate_id,
                symbol=key,
                side=OrderSide(side),
                order_type=OrderType(order_type),
                quantity=quantity,
                limit_price=limit_price,
                replaces_order_id=replaces_order_id,
                session_id=session_id,
            )
            with self._atomic():
                self._orders[order.id] = order
                self._append_event_unlocked(
                    "order_created",
                    message=f"order created for {key}",
                    symbol=key,
                    candidate_id=candidate_id,
                    order_id=order.id,
                    session_id=session_id,
                )
            return order.model_copy(deep=True)

    async def create_order_for_candidate(self, candidate_id: str) -> Order:
        async with self._lock:
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                raise UnknownEntityError(f"candidate {candidate_id} not found")
            # Idempotent: a candidate already dispatched returns its existing
            # order and writes nothing — no second order, no extra audit rows.
            if candidate.status is CandidateStatus.ORDERED:
                existing = (
                    self._orders.get(candidate.order_id)
                    if candidate.order_id is not None
                    else None
                )
                if existing is None:  # ordered but unlinked — a corrupt invariant
                    raise InvalidOrderError(
                        f"candidate {candidate_id} is ORDERED but has no linked order"
                    )
                return existing.model_copy(deep=True)
            # The approved-only rule D-010 deferred to the gate lands here: only
            # an APPROVED candidate may be dispatched to an order.
            if candidate.status is not CandidateStatus.APPROVED:
                raise CandidateTransitionError(
                    f"cannot order candidate {candidate_id} in status "
                    f"{candidate.status.value}; must be approved"
                )
            # Safety controls (Rule 8): refuse new order intent when the kill
            # switch is engaged / buys are paused. Enforced at the backend
            # boundary so every producer is gated (not just the UI), and audited.
            session = next(
                (s for s in self._sessions if s.id == candidate.session_id), None
            )
            block = order_intent_block_reason(session)
            if block is not None:
                self._append_event_unlocked(
                    "order_intent_blocked",
                    message=f"order intent for {candidate.symbol} blocked: {block}",
                    symbol=candidate.symbol,
                    candidate_id=candidate_id,
                    payload={"reason": block},
                    session_id=candidate.session_id,
                )
                raise OrderIntentBlockedError(f"order intent blocked: {block}")
            qty = candidate.suggested_quantity
            if qty is None or qty <= 0:
                raise InvalidOrderError(
                    f"candidate {candidate_id} has no positive suggested_quantity "
                    f"to size an order"
                )
            # A LIMIT order requires a finite, positive limit price (F1 / BACKEND-1):
            # never persist a LIMIT order with a missing/NaN/Inf/zero/negative price.
            limit_price = candidate.suggested_limit_price
            bad_price = limit_price_reason(limit_price)
            if bad_price is not None:
                raise InvalidOrderError(
                    f"candidate {candidate_id} has no valid suggested_limit_price "
                    f"for a limit order ({bad_price})"
                )
            # Long-only buy proposal (beta). Order type LIMIT; session order-type
            # policy (Rule 12) is enforced later, not here.
            order = Order(
                candidate_id=candidate_id,
                symbol=candidate.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=qty,
                limit_price=limit_price,
                session_id=candidate.session_id,
            )
            # APPROVED -> ORDERED, linking the order. The lock serializes other
            # coroutines, but this block must also be all-or-nothing if a write
            # raises mid-way (F3) — so mutate a candidate *copy* and commit the
            # order/candidate/events together, rolling back on any failure. This
            # matches SqliteStateStore's single-transaction guarantee for the
            # "candidate approval + order creation + audit event" group (docs/02).
            now = utcnow()
            updated = candidate.model_copy(deep=True)
            updated.status = CandidateStatus.ORDERED
            updated.order_id = order.id
            updated.updated_at = now
            updated.ordered_at = now
            events_before = len(self._events)
            try:
                self._orders[order.id] = order
                self._candidates[candidate_id] = updated
                self._append_event_unlocked(
                    "order_created",
                    message=f"order created for {candidate.symbol}",
                    symbol=candidate.symbol,
                    candidate_id=candidate_id,
                    order_id=order.id,
                    session_id=candidate.session_id,
                )
                self._append_event_unlocked(
                    "candidate_transition",
                    message="candidate approved -> ordered",
                    symbol=candidate.symbol,
                    candidate_id=candidate_id,
                    order_id=order.id,
                    payload={"from": "approved", "to": "ordered"},
                    session_id=candidate.session_id,
                )
            except BaseException:
                # Restore the pre-handoff state: drop the order, restore the
                # original candidate, and truncate any events appended so far.
                self._orders.pop(order.id, None)
                self._candidates[candidate_id] = candidate
                del self._events[events_before:]
                raise
            return order.model_copy(deep=True)

    async def revert_candidate_approval(self, candidate_id: str) -> Candidate:
        async with self._lock:
            candidate = self._candidates.get(candidate_id)
            if candidate is None:
                raise UnknownEntityError(f"candidate {candidate_id} not found")
            # No-op unless the candidate is genuinely stranded APPROVED-with-no-
            # order: never disturb one that became ORDERED, or a PENDING one.
            if (
                candidate.status is not CandidateStatus.APPROVED
                or candidate.order_id is not None
            ):
                return candidate.model_copy(deep=True)
            now = utcnow()
            with self._atomic():
                candidate.status = CandidateStatus.PENDING
                candidate.approved_at = None
                candidate.updated_at = now
                self._append_event_unlocked(
                    "candidate_transition",
                    message="candidate approved -> pending (dispatch blocked)",
                    symbol=candidate.symbol,
                    candidate_id=candidate.id,
                    payload={
                        "from": "approved",
                        "to": "pending",
                        "reason": "dispatch_blocked",
                    },
                    session_id=candidate.session_id,
                )
            return candidate.model_copy(deep=True)

    async def list_orders(
        self,
        *,
        session_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
    ) -> list[Order]:
        async with self._lock:
            out = []
            for o in self._orders.values():
                if session_id is not None and o.session_id != session_id:
                    continue
                if candidate_id is not None and o.candidate_id != candidate_id:
                    continue
                out.append(o.model_copy(deep=True))
            return out

    async def get_order(self, order_id: str) -> Optional[Order]:
        async with self._lock:
            o = self._orders.get(order_id)
            return o.model_copy(deep=True) if o else None

    async def transition_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        filled_quantity: Optional[int] = None,
        broker_order_id: Optional[str] = None,
    ) -> Order:
        async with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise UnknownEntityError(f"order {order_id} not found")
            current = order.status
            status_changed = new_status is not current
            if status_changed and new_status not in _ORDER_TRANSITIONS.get(
                current, set()
            ):
                raise OrderTransitionError(
                    f"illegal order transition {current.value} -> {new_status.value}"
                )
            # Bound + monotonic filled_quantity (Fix 5). Out-of-range or backward
            # progress raises and writes nothing; D-008 audit behavior below is
            # untouched. Equality is allowed (handled as a no-op).
            if filled_quantity is not None:
                bad = filled_quantity_reason(order, filled_quantity)
                if bad is not None:
                    raise InvalidOrderError(
                        f"invalid filled_quantity {filled_quantity} for order "
                        f"{order.id} (qty {order.quantity}, current "
                        f"{order.filled_quantity}): {bad}"
                    )
            qty_changed = (
                filled_quantity is not None
                and filled_quantity != order.filled_quantity
            )
            broker_changed = (
                broker_order_id is not None
                and broker_order_id != order.broker_order_id
            )

            # True no-op (status unchanged and nothing else changed): write no
            # audit row and mutate nothing — same rule transition_candidate uses.
            if not status_changed and not qty_changed and not broker_changed:
                return order.model_copy(deep=True)

            previous_filled = order.filled_quantity
            with self._atomic():
                if qty_changed:
                    order.filled_quantity = filled_quantity
                if broker_changed:
                    order.broker_order_id = broker_order_id
                if status_changed:
                    order.status = new_status
                    ts_field = _ORDER_TIMESTAMP.get(new_status)
                    if ts_field and getattr(order, ts_field) is None:
                        setattr(order, ts_field, utcnow())
                order.updated_at = utcnow()

                if status_changed:
                    self._append_event_unlocked(
                        "order_transition",
                        message=f"order {current.value} -> {new_status.value}",
                        symbol=order.symbol,
                        candidate_id=order.candidate_id,
                        order_id=order.id,
                        payload={"from": current.value, "to": new_status.value},
                        session_id=order.session_id,
                    )
                else:
                    # Same status, but fill progressed (or broker id assigned).
                    # Not a no-op — record it with the before/after quantity, not
                    # a generic same-status row (D-008).
                    payload: dict[str, Any] = {
                        "status": current.value,
                        "previous_filled_quantity": previous_filled,
                        "filled_quantity": order.filled_quantity,
                    }
                    if broker_changed:
                        payload["broker_order_id"] = broker_order_id
                    self._append_event_unlocked(
                        "order_fill_progress",
                        message=(
                            f"order {order.symbol} fill progress "
                            f"{previous_filled} -> {order.filled_quantity}"
                        ),
                        symbol=order.symbol,
                        candidate_id=order.candidate_id,
                        order_id=order.id,
                        payload=payload,
                        session_id=order.session_id,
                    )
            return order.model_copy(deep=True)

    # ------------------------------------------------------------------ #
    # Fills (append-only) — the only mutation of position
    # ------------------------------------------------------------------ #
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
        key = normalize_symbol(symbol)
        side = OrderSide(side)
        async with self._lock:
            # 1) Intrinsic value validation (Fix 1): a non-positive quantity or
            #    price would corrupt derived-position truth. Reject before any
            #    state is touched; record why.
            value_reason = fill_value_reason(quantity, price)
            if value_reason is not None:
                self._append_event_unlocked(
                    "fill_rejected_invalid",
                    message=f"fill for {key} rejected: {value_reason}",
                    symbol=key,
                    order_id=order_id,
                    payload={
                        "reason": value_reason,
                        "quantity": quantity,
                        "price": price,
                    },
                    session_id=session_id,
                )
                raise InvalidFillError(f"invalid fill for {key}: {value_reason}")

            # 2) The referenced order must exist (Fix 2).
            order = self._orders.get(order_id)
            if order is None:
                self._append_event_unlocked(
                    "fill_rejected_invalid",
                    message=f"fill rejected: unknown order {order_id}",
                    symbol=key,
                    order_id=order_id,
                    payload={"reason": "unknown_order"},
                    session_id=session_id,
                )
                raise UnknownEntityError(f"order {order_id} not found")

            # 3) Duplicate protection (makes append idempotent, not optional).
            #    A replay of an already-accepted fill short-circuits here before
            #    the cumulative check, so it is never mistaken for an overfill.
            if (
                source_fill_id is not None
                and (order_id, source_fill_id) in self._fill_source_ids
            ):
                event = self._append_event_unlocked(
                    "fill_duplicate_ignored",
                    message=(
                        f"duplicate fill {source_fill_id} for {key} ignored"
                    ),
                    symbol=key,
                    order_id=order_id,
                    payload={"source_fill_id": source_fill_id},
                    session_id=session_id,
                )
                return FillAppendResult(status="duplicate", fill=None, event=event)

            # 4) Symbol/side match + cumulative-quantity vs the order (Fix 2).
            prior_filled = sum(
                f.quantity for f in self._fills if f.order_id == order_id
            )
            match_reason = fill_order_match_reason(
                order, key, side, quantity, prior_filled
            )
            if match_reason is not None:
                self._append_event_unlocked(
                    "fill_rejected_invalid",
                    message=f"fill for {key} rejected: {match_reason}",
                    symbol=key,
                    order_id=order_id,
                    payload={
                        "reason": match_reason,
                        "order_symbol": order.symbol,
                        "order_side": OrderSide(order.side).value,
                        "order_quantity": order.quantity,
                        "prior_filled_quantity": prior_filled,
                        "quantity": quantity,
                    },
                    session_id=session_id,
                )
                raise InvalidFillError(
                    f"fill for {key} inconsistent with order {order_id}: "
                    f"{match_reason}"
                )

            # 5) Long-only integrity: a sell can never drive quantity negative.
            current = self._position_unlocked(key)
            if would_go_negative(current.quantity, side, quantity):
                event = self._append_event_unlocked(
                    "fill_rejected_negative_position",
                    message=(
                        f"sell of {quantity} {key} rejected: exceeds current "
                        f"quantity {current.quantity}"
                    ),
                    symbol=key,
                    order_id=order_id,
                    payload={
                        "attempted_sell": quantity,
                        "current_quantity": current.quantity,
                    },
                    session_id=session_id,
                )
                raise NegativePositionError(key, current.quantity, quantity)

            # 6) Append the fill and record it — atomically, so a failed audit
            #    event can't leave a position-changing fill with no fill_appended
            #    row AND a poisoned dedup set (Item 4). Only this success region is
            #    wrapped; the rejection events above must persist.
            fill = Fill(
                order_id=order_id,
                symbol=key,
                side=side,
                quantity=quantity,
                price=price,
                source_fill_id=source_fill_id,
                session_id=session_id,
                filled_at=filled_at or utcnow(),
            )
            with self._atomic():
                self._fills.append(fill)
                if source_fill_id is not None:
                    self._fill_source_ids.add((order_id, source_fill_id))
                event = self._append_event_unlocked(
                    "fill_appended",
                    message=f"fill {fill.quantity} {key} @ {fill.price}",
                    symbol=key,
                    order_id=order_id,
                    fill_id=fill.id,
                    payload={
                        "side": side.value,
                        "quantity": quantity,
                        "price": price,
                    },
                    session_id=session_id,
                )
            return FillAppendResult(
                status="appended", fill=fill.model_copy(deep=True), event=event
            )

    async def list_fills(
        self,
        *,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[Fill]:
        key = normalize_symbol(symbol) if symbol else None
        async with self._lock:
            out = []
            for f in self._fills:
                if key is not None and f.symbol != key:
                    continue
                if order_id is not None and f.order_id != order_id:
                    continue
                if session_id is not None and f.session_id != session_id:
                    continue
                out.append(f.model_copy(deep=True))
            return out

    # ------------------------------------------------------------------ #
    # Positions (derived)
    # ------------------------------------------------------------------ #
    async def get_position(self, symbol: str) -> Position:
        key = normalize_symbol(symbol)
        async with self._lock:
            return self._position_unlocked(key)

    async def list_positions(self) -> list[Position]:
        async with self._lock:
            symbols = sorted({f.symbol for f in self._fills})
            return [self._position_unlocked(s) for s in symbols]

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
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
        async with self._lock:
            return self._append_event_unlocked(
                event_type,
                message=message,
                symbol=symbol,
                candidate_id=candidate_id,
                order_id=order_id,
                fill_id=fill_id,
                payload=payload,
                session_id=session_id,
            )

    async def list_events(
        self,
        *,
        session_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        async with self._lock:
            out = [
                e.model_copy(deep=True)
                for e in self._events
                if session_id is None or e.session_id == session_id
            ]
            if limit is not None:
                out = out[-limit:]
            return out

    # ------------------------------------------------------------------ #
    # Sessions / control flags
    # ------------------------------------------------------------------ #
    async def get_current_session(self) -> SessionRecord:
        async with self._lock:
            with self._atomic():
                session = self._ensure_current_session_unlocked()
            return session.model_copy(deep=True)

    async def get_session_by_date(self, day: date) -> Optional[SessionRecord]:
        target = day.isoformat()
        async with self._lock:
            for session in reversed(self._sessions):
                if session.session_date == target:
                    return session.model_copy(deep=True)
            return None

    async def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        async with self._lock:
            for session in self._sessions:
                if session.id == session_id:
                    return session.model_copy(deep=True)
            return None

    async def list_sessions(self) -> list[SessionRecord]:
        async with self._lock:
            return [s.model_copy(deep=True) for s in self._sessions]

    async def set_session_type(self, session_type: SessionType) -> SessionRecord:
        async with self._lock:
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                session.session_type = SessionType(session_type)
                session.updated_at = utcnow()
                self._append_event_unlocked(
                    "session_opened",
                    message=f"session type set to {session.session_type.value}",
                    session_id=session.id,
                    payload={"session_type": session.session_type.value},
                )
            return session.model_copy(deep=True)

    async def set_kill_switch(self, engaged: bool) -> SessionRecord:
        async with self._lock:
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                session.kill_switch = engaged
                session.updated_at = utcnow()
                self._append_event_unlocked(
                    "kill_switch_engaged" if engaged else "kill_switch_released",
                    message=f"kill switch {'engaged' if engaged else 'released'}",
                    session_id=session.id,
                    payload={"kill_switch": engaged},
                )
            return session.model_copy(deep=True)

    async def set_buys_paused(self, paused: bool) -> SessionRecord:
        async with self._lock:
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                session.buys_paused = paused
                session.updated_at = utcnow()
                self._append_event_unlocked(
                    "buys_paused" if paused else "buys_resumed",
                    message=f"buys {'paused' if paused else 'resumed'}",
                    session_id=session.id,
                    payload={"buys_paused": paused},
                )
            return session.model_copy(deep=True)

    async def close_session(
        self, session_id: Optional[str] = None
    ) -> SessionRecord:
        async with self._lock:
            if session_id is None:
                # The active session, but do NOT auto-create one — closing when
                # nothing is active means there is nothing to close.
                session = next(
                    (
                        s
                        for s in reversed(self._sessions)
                        if s.status is SessionStatus.ACTIVE
                    ),
                    None,
                )
                if session is None:
                    raise SessionAlreadyClosedError("no active session to close")
            else:
                session = next(
                    (s for s in self._sessions if s.id == session_id), None
                )
                if session is None:
                    raise UnknownEntityError(f"session {session_id} not found")
                if session.status is SessionStatus.CLOSED:
                    raise SessionAlreadyClosedError(
                        f"session {session.id} is already closed"
                    )

            # The whole close (expire candidates + cancel CREATED orders +
            # snapshot positions + mark closed + audit) is one atomic group.
            with self._atomic():
                return self._close_session_unlocked(session)

    def _close_session_unlocked(self, session: SessionRecord) -> SessionRecord:
        """The close mutations (assumes the lock is held and ``session`` is the
        validated, still-open session). Wrapped by ``_atomic`` so the whole close
        is all-or-nothing."""

        now = utcnow()

        # 1) Expire open (pending/approved) candidates in this session.
        expired = 0
        for candidate in self._candidates.values():
            if candidate.session_id == session.id and candidate.status in (
                CandidateStatus.PENDING,
                CandidateStatus.APPROVED,
            ):
                prev = candidate.status
                candidate.status = CandidateStatus.EXPIRED
                candidate.expired_at = now
                candidate.updated_at = now
                expired += 1
                self._append_event_unlocked(
                    "candidate_transition",
                    message=f"candidate {prev.value} -> expired (session close)",
                    symbol=candidate.symbol,
                    candidate_id=candidate.id,
                    payload={
                        "from": prev.value,
                        "to": "expired",
                        "reason": "session_close",
                    },
                    session_id=session.id,
                )

        # 1b) Cancel still-CREATED (never-submitted) orders in this session
        #     so they cannot sit submittable after close (D-013a). The loop's
        #     per-order-session gate also holds them, but cancelling here
        #     leaves a clean terminal state instead of a zombie CREATED order.
        #     Already-submitted orders are untouched and keep reconciling
        #     (D-011).
        canceled_orders = 0
        for order in self._orders.values():
            if (
                order.session_id == session.id
                and order.status is OrderStatus.CREATED
            ):
                order.status = OrderStatus.CANCELED
                order.canceled_at = now
                order.updated_at = now
                canceled_orders += 1
                self._append_event_unlocked(
                    "order_transition",
                    message=(
                        f"order {order.symbol} created -> canceled "
                        f"(session close)"
                    ),
                    symbol=order.symbol,
                    candidate_id=order.candidate_id,
                    order_id=order.id,
                    payload={
                        "from": "created",
                        "to": "canceled",
                        "reason": "session_close",
                    },
                    session_id=session.id,
                )

        # 2) Snapshot every nonzero position (the live fold over fills).
        snapshots = 0
        for sym in sorted({f.symbol for f in self._fills}):
            pos = self._position_unlocked(sym)
            if pos.quantity != 0:
                self._position_snapshots.append(
                    PositionSnapshot(
                        session_id=session.id,
                        symbol=pos.symbol,
                        quantity=pos.quantity,
                        cost_basis=pos.cost_basis,
                        average_price=pos.average_price,
                        captured_at=now,
                    )
                )
                snapshots += 1

        # 3) Mark the session closed.
        session.status = SessionStatus.CLOSED
        session.closed_at = now
        session.updated_at = now

        # 4) One audit event for the close.
        self._append_event_unlocked(
            "session_closed",
            message=(
                f"session closed ({expired} candidates expired, "
                f"{canceled_orders} created orders canceled, "
                f"{snapshots} positions snapshotted)"
            ),
            session_id=session.id,
            payload={
                "expired_candidates": expired,
                "canceled_orders": canceled_orders,
                "position_snapshots": snapshots,
            },
        )
        return session.model_copy(deep=True)

    async def list_position_snapshots(
        self, session_id: str
    ) -> list[PositionSnapshot]:
        async with self._lock:
            return [
                s.model_copy(deep=True)
                for s in self._position_snapshots
                if s.session_id == session_id
            ]
