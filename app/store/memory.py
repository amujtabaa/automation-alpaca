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
from typing import Any, Iterable, Iterator, Optional

from app.models import (
    RECOVERY_UNRESOLVED,
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
    SubmitRecoveryRecord,
    TradingMode,
    WatchlistSymbol,
    utcnow,
)
from app.position import fold_fills
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    CandidateTransitionError,
    FillAppendResult,
    InvalidOrderError,
    RiskLimits,
    SessionAlreadyClosedError,
    SessionClosedError,
    StateStore,
    SubmissionClaim,
    UnknownEntityError,
    normalize_symbol,
)
from app.store.core import (
    CREATE_ORDER_REJECT,
    FILL_DUPLICATE,
    FILL_REJECT,
    ORDER_TRANSITION_NOOP,
    ORDER_TRANSITION_REJECT,
    plan_append_fill,
    plan_claim_order_for_submission,
    plan_close_session,
    plan_create_order_for_candidate,
    plan_transition_order,
    require_bool,
    require_recovery_status,
    require_status_enum,
    recovery_status_event,
)
from app.transitions import (
    CANDIDATE_TIMESTAMP as _CANDIDATE_TIMESTAMP,
    CANDIDATE_TRANSITIONS as _CANDIDATE_TRANSITIONS,
)
from app.policy import (
    NON_TERMINAL_ORDER_STATUSES,
    candidate_numeric_reason,
    existing_exposure,
    order_candidate_match_reason,
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
        self._submit_recoveries: list[SubmitRecoveryRecord] = []  # D-017

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
        # Recovery records are append-then-replace (update swaps in a fresh copy,
        # never mutates in place), so a shallow snapshot restores correctly.
        saved_recoveries = list(self._submit_recoveries)
        try:
            yield
        except BaseException:
            self._watchlist = saved_watchlist
            self._candidates = saved_candidates
            self._orders = saved_orders
            self._fills = saved_fills
            self._submit_recoveries = saved_recoveries
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
        correlation_id: Optional[str] = None,
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
            # The owning candidate's id is the correlation key (D-020): default it
            # from candidate_id so every event in a candidate's lifecycle shares
            # one filterable key with no per-call-site threading. Same rule in
            # SqliteStateStore._insert_event — parity.
            correlation_id=correlation_id or candidate_id,
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
        # Self-atomic so a caller that auto-creates today's session OUTSIDE its
        # own _atomic block (e.g. create_candidate) can't leak a half-created
        # session if the session_opened event write fails — matches SQLite, where
        # _ensure_current_session_locked wraps both writes in one _tx. _atomic
        # nests safely inside a caller that is already atomic.
        with self._atomic():
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

    def _current_exposure_unlocked(self) -> float:
        positions = [
            self._position_unlocked(s) for s in sorted({f.symbol for f in self._fills})
        ]
        open_orders = [
            o for o in self._orders.values() if o.status in NON_TERMINAL_ORDER_STATUSES
        ]
        return existing_exposure(positions, open_orders, self._fills)

    # ------------------------------------------------------------------ #
    # Watchlist
    # ------------------------------------------------------------------ #
    async def add_watchlist_symbol(
        self, symbol: str, *, armed: bool = False
    ) -> WatchlistSymbol:
        require_bool(armed, field="armed")
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
        require_bool(armed, field="armed")
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
            # review see this candidate (Fix 7). An explicit session_id wins —
            # but it must actually resolve: an explicit id that names no session
            # is rejected (F-004), never allowed to create an orphan candidate
            # whose declared session doesn't exist (which then dispatches an
            # orphan order). The `None` -> current-session default is unchanged.
            if session_id is None:
                session = self._ensure_current_session_unlocked()
                session_id = session.id
            else:
                session = next(
                    (s for s in self._sessions if s.id == session_id), None
                )
                if session is None:
                    raise UnknownEntityError(
                        f"session {session_id} does not exist; cannot create candidate"
                    )
            # No new candidates in a closed session (D-009 / F2): the trading day
            # is over, and a post-close candidate would sit outside the captured
            # review snapshot. Guard at the store boundary so every future
            # producer (Phase 5) is covered, not only the dev route.
            if session is not None and session.status is SessionStatus.CLOSED:
                raise SessionClosedError(
                    f"session {session_id} is closed; cannot create candidate"
                )
            # Validate candidate numerics at the boundary (AIR-008): a present
            # quantity/price must be a positive whole share count / a finite
            # positive number. Rejects the full coercion class (NaN/Inf/zero/
            # negative/fractional/bool/string) with a clean domain error, while
            # its raw type is still recoverable and before a non-finite value
            # could roundtrip differently across the two stores.
            bad = candidate_numeric_reason(
                suggested_quantity=suggested_quantity,
                suggested_limit_price=suggested_limit_price,
            )
            if bad is not None:
                field, why = bad
                value = (
                    suggested_quantity
                    if field == "suggested_quantity"
                    else suggested_limit_price
                )
                raise InvalidOrderError(
                    f"candidate {key} has an invalid {field} ({why}: {value!r})"
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
        if status is not None:
            require_status_enum(status, CandidateStatus, field="status filter")
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
        require_status_enum(new_status, CandidateStatus, field="new_status")
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
    async def create_order_for_test(
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
        """TEST-ONLY order-setup helper — NOT part of the public ``StateStore``
        contract (AIR-006). Production orders are created *only* via
        ``create_order_for_candidate`` (approved-only rule + CAPI/control gates).
        This low-level insert validates existence + symbol match only and does
        not gate quantity/side, so it must never be reachable from a route or the
        monitoring loop — it exists to let tests set an order into an arbitrary
        starting state directly."""

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
                # Inherit the candidate's session when not given, exactly as a
                # production order does (plan_create_order_for_candidate) — so a
                # test order can be claimed for submission like a real one.
                session_id=session_id if session_id is not None else candidate.session_id,
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

    async def current_exposure(self) -> float:
        async with self._lock:
            return self._current_exposure_unlocked()

    async def create_order_for_candidate(
        self,
        candidate_id: str,
        *,
        risk_limits: RiskLimits = RiskLimits(),
    ) -> Order:
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
            # Shared validation cascade + order construction (app/store/core.py);
            # the candidate-missing and ORDERED-idempotent cases above stay here
            # since they need store-specific fetches. Exposure is computed
            # unconditionally (cheap at beta scale) — the planner only uses it
            # when a CAPI limit above is actually configured.
            session = next(
                (s for s in self._sessions if s.id == candidate.session_id), None
            )
            plan = plan_create_order_for_candidate(
                candidate=candidate,
                session=session,
                exposure_before_order=self._current_exposure_unlocked(),
                risk_limits=risk_limits,
            )
            if plan.outcome == CREATE_ORDER_REJECT:
                # The kill-switch/pause block and the Phase 6 CAPI risk-limit
                # block each write an audit row before raising; the not-approved
                # and invalid-qty/price rejections don't.
                if plan.reject_event is not None:
                    self._append_event_unlocked(
                        plan.reject_event.event_type, **plan.reject_event.as_kwargs()
                    )
                raise plan.error

            # CREATE — APPROVED -> ORDERED, linking the order. Wrapped in _atomic
            # (unifying what was previously a hand-rolled snapshot/restore here) so
            # the order insert + candidate transition + both audit events are
            # all-or-nothing, matching SqliteStateStore's single-transaction
            # guarantee for the "approval + order creation + audit" group (docs/02).
            order = plan.order
            now = utcnow()
            updated = candidate.model_copy(deep=True)
            updated.status = CandidateStatus.ORDERED
            updated.order_id = order.id
            updated.updated_at = now
            updated.ordered_at = now
            with self._atomic():
                self._orders[order.id] = order
                self._candidates[candidate_id] = updated
                for event in plan.events:
                    self._append_event_unlocked(event.event_type, **event.as_kwargs())
            return order.model_copy(deep=True)

    async def claim_order_for_submission(self, order_id: str) -> SubmissionClaim:
        async with self._lock:
            order = self._orders.get(order_id)
            own_session = (
                next(
                    (s for s in self._sessions if s.id == order.session_id), None
                )
                if order is not None
                else None
            )
            current_session = self._ensure_current_session_unlocked()
            plan = plan_claim_order_for_submission(
                order=order,
                own_session=own_session,
                current_session=current_session,
            )
            if plan.outcome == CLAIM_CLAIMED:
                with self._atomic():
                    self._orders[order_id] = plan.order
                    self._append_event_unlocked(
                        plan.event.event_type, **plan.event.as_kwargs()
                    )
                return SubmissionClaim(
                    CLAIM_CLAIMED, order=plan.order.model_copy(deep=True)
                )
            if plan.outcome == CLAIM_BLOCKED:
                return SubmissionClaim(CLAIM_BLOCKED, reason=plan.reason)
            return SubmissionClaim(plan.outcome)  # CLAIM_SKIPPED

    async def create_submit_recovery(
        self,
        *,
        local_order_id: str,
        broker_order_id: str,
        client_order_id: Optional[str] = None,
        symbol: str,
        side: OrderSide,
        quantity: int,
        limit_price: Optional[float] = None,
        failure_reason: str,
        session_id: Optional[str] = None,
        candidate_id: Optional[str] = None,
        cleanup_status: str = RECOVERY_UNRESOLVED,
        event_type: str = "submit_recovery_recorded",
        extra_payload: Optional[dict[str, Any]] = None,
    ) -> SubmitRecoveryRecord:
        require_recovery_status(cleanup_status)
        key = normalize_symbol(symbol)
        async with self._lock:
            record = SubmitRecoveryRecord(
                local_order_id=local_order_id,
                broker_order_id=broker_order_id,
                client_order_id=client_order_id,
                symbol=key,
                side=OrderSide(side),
                quantity=quantity,
                limit_price=limit_price,
                failure_reason=failure_reason,
                cleanup_status=cleanup_status,
                session_id=session_id,
            )
            payload: dict[str, Any] = {
                "broker_order_id": broker_order_id,
                "failure_reason": failure_reason,
                "cleanup_status": cleanup_status,
            }
            if extra_payload:
                payload.update(extra_payload)
            with self._atomic():
                self._submit_recoveries.append(record)
                self._append_event_unlocked(
                    event_type,
                    message=(
                        f"broker order {broker_order_id} for {key} needs "
                        f"recovery: {failure_reason}"
                    ),
                    symbol=key,
                    candidate_id=candidate_id,
                    order_id=local_order_id,
                    payload=payload,
                    session_id=session_id,
                )
            return record.model_copy(deep=True)

    async def list_submit_recoveries(
        self, *, statuses: Optional[Iterable[str]] = None
    ) -> list[SubmitRecoveryRecord]:
        wanted = None if statuses is None else set(statuses)
        async with self._lock:
            return [
                r.model_copy(deep=True)
                for r in self._submit_recoveries
                if wanted is None or r.cleanup_status in wanted
            ]

    async def update_submit_recovery(
        self,
        recovery_id: str,
        *,
        cleanup_status: Optional[str] = None,
        bump_attempt: bool = False,
    ) -> SubmitRecoveryRecord:
        async with self._lock:
            idx = next(
                (
                    i
                    for i, r in enumerate(self._submit_recoveries)
                    if r.id == recovery_id
                ),
                None,
            )
            if idx is None:
                raise UnknownEntityError(f"submit recovery {recovery_id} not found")
            record = self._submit_recoveries[idx]
            terminal_event = recovery_status_event(
                record.cleanup_status, cleanup_status
            )
            # Replace, never mutate in place (keeps _atomic's shallow snapshot valid).
            updated = record.model_copy(deep=True)
            if bump_attempt:
                updated.retry_count += 1
                updated.last_attempt_at = utcnow()
            if cleanup_status is not None:
                updated.cleanup_status = cleanup_status
            with self._atomic():
                self._submit_recoveries[idx] = updated
                if terminal_event is not None:
                    # SubmitRecoveryRecord carries no candidate_id (D-020 stays
                    # to one nullable Event field); resolve it from the local
                    # order for correlation — orders are never deleted, so this
                    # reliably resolves for the lifetime of the record.
                    local_order = self._orders.get(updated.local_order_id)
                    self._append_event_unlocked(
                        terminal_event,
                        message=(
                            f"broker order {updated.broker_order_id} recovery "
                            f"{cleanup_status}"
                        ),
                        symbol=updated.symbol,
                        candidate_id=(
                            local_order.candidate_id if local_order is not None else None
                        ),
                        order_id=updated.local_order_id,
                        payload={
                            "broker_order_id": updated.broker_order_id,
                            "cleanup_status": cleanup_status,
                            "retry_count": updated.retry_count,
                        },
                        session_id=updated.session_id,
                    )
            return updated.model_copy(deep=True)

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
            plan = plan_transition_order(
                order=order,
                new_status=new_status,
                filled_quantity=filled_quantity,
                broker_order_id=broker_order_id,
            )
            if plan.outcome == ORDER_TRANSITION_REJECT:
                raise plan.error
            if plan.outcome == ORDER_TRANSITION_NOOP:
                return order.model_copy(deep=True)
            # APPLY — swap in the fully-updated order and write its one audit row
            # (order_transition or order_fill_progress) atomically.
            with self._atomic():
                self._orders[order_id] = plan.order
                self._append_event_unlocked(
                    plan.event.event_type, **plan.event.as_kwargs()
                )
            return plan.order.model_copy(deep=True)

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
            # Fetch the state the shared planner decides over (dict-lookup form),
            # then apply its plan. Decision logic lives once in app/store/core.py;
            # only the fetch + the write primitive are store-specific here.
            order = self._orders.get(order_id)
            prior_filled = sum(
                f.quantity for f in self._fills if f.order_id == order_id
            )
            is_duplicate = (
                source_fill_id is not None
                and (order_id, source_fill_id) in self._fill_source_ids
            )
            current = self._position_unlocked(key)
            plan = plan_append_fill(
                order_id=order_id,
                order=order,
                prior_filled=prior_filled,
                current_quantity=current.quantity,
                is_duplicate=is_duplicate,
                symbol=key,
                side=side,
                quantity=quantity,
                price=price,
                source_fill_id=source_fill_id,
                filled_at=filled_at,
                session_id=session_id,
            )

            if plan.outcome == FILL_REJECT:
                # A single rejection event is one row — no atomic wrapper needed;
                # it must persist even though we then raise.
                self._append_event_unlocked(plan.event.event_type, **plan.event.as_kwargs())
                raise plan.error

            if plan.outcome == FILL_DUPLICATE:
                event = self._append_event_unlocked(
                    plan.event.event_type, **plan.event.as_kwargs()
                )
                return FillAppendResult(status="duplicate", fill=None, event=event)

            # FILL_APPEND — atomically append the fill + dedup key + audit event,
            # so a failed audit write can't leave a position-changing fill with no
            # fill_appended row AND a poisoned dedup set (Item 4).
            fill = plan.fill
            with self._atomic():
                self._fills.append(fill)
                if fill.source_fill_id is not None:
                    self._fill_source_ids.add((fill.order_id, fill.source_fill_id))
                event = self._append_event_unlocked(
                    plan.event.event_type, **plan.event.as_kwargs()
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
        correlation_id: Optional[str] = None,
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
                correlation_id=correlation_id,
            )

    async def list_events(
        self,
        *,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        correlation_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Event]:
        async with self._lock:
            out = [
                e.model_copy(deep=True)
                for e in self._events
                if (session_id is None or e.session_id == session_id)
                and (event_type is None or e.event_type == event_type)
                and (correlation_id is None or e.correlation_id == correlation_id)
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

    async def set_kill_switch(self, engaged: bool) -> SessionRecord:
        require_bool(engaged, field="engaged")
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
        require_bool(paused, field="paused")
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

        # Select what the shared planner decides over (dict-scan form). Order
        # preserved: candidates/orders in insertion order, positions by symbol —
        # matching the pre-refactor loops so audit-event order is unchanged.
        open_candidates = [
            c
            for c in self._candidates.values()
            if c.session_id == session.id
            and c.status in (CandidateStatus.PENDING, CandidateStatus.APPROVED)
        ]
        created_orders = [
            o
            for o in self._orders.values()
            if o.session_id == session.id and o.status is OrderStatus.CREATED
        ]
        nonzero_positions = []
        for sym in sorted({f.symbol for f in self._fills}):
            pos = self._position_unlocked(sym)
            if pos.quantity != 0:
                nonzero_positions.append(pos)

        plan = plan_close_session(
            session=session,
            open_candidates=open_candidates,
            created_orders=created_orders,
            nonzero_positions=nonzero_positions,
            now=now,
        )

        # Apply (in-place mutation form). D-013a: expire open candidates, cancel
        # still-CREATED orders, snapshot nonzero positions, mark the session
        # closed. Under _atomic() (see the caller) so the whole close is
        # all-or-nothing.
        for candidate, event in zip(open_candidates, plan.candidate_events):
            candidate.status = CandidateStatus.EXPIRED
            candidate.expired_at = now
            candidate.updated_at = now
            self._append_event_unlocked(event.event_type, **event.as_kwargs())
        for order, event in zip(created_orders, plan.order_events):
            order.status = OrderStatus.CANCELED
            order.canceled_at = now
            order.updated_at = now
            self._append_event_unlocked(event.event_type, **event.as_kwargs())
        self._position_snapshots.extend(plan.snapshots)
        session.status = SessionStatus.CLOSED
        session.closed_at = now
        session.updated_at = now
        self._append_event_unlocked(
            plan.close_event.event_type, **plan.close_event.as_kwargs()
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
