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
from datetime import date, datetime
from typing import Any, Iterable, Iterator, Optional

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_UNRESOLVED,
    Candidate,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    CandidateStatus,
    Event,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSnapshot,
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionRecord,
    SessionStatus,
    SubmitRecoveryRecord,
    TradingMode,
    TradingState,
    WatchlistSymbol,
    utcnow,
)
from app.events.projectors import (
    ORDER_STATUS_EVENT_TYPES,
    active_emergency_reduce_overrides,
    compose_trading_state,
    control_trading_state,
    current_trading_state,
    project_order_status,
    project_symbol_position,
    quarantined_symbols,
    reconcile_trading_state,
    timeout_quarantined_order_ids,
)
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    COMMAND_ACTOR_SYSTEM,
    FLATTEN_CREATED,
    FLATTEN_EXISTING,
    FLATTEN_FLAT,
    CandidateTransitionError,
    EmergencyReduceBlockedError,
    FillAppendResult,
    FlattenBlockedError,
    FlattenResult,
    InvalidOrderError,
    OrderIntentBlockedError,
    ProtectionHaltedError,
    RiskLimits,
    SellIntentTransitionError,
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
    execution_event_for_fill,
    execution_event_for_routine_transition,
    order_status_backfill_event,
    FLATTEN_FLAT as _PLAN_FLATTEN_FLAT,
    FLATTEN_EXISTING as _PLAN_FLATTEN_EXISTING,
    FLATTEN_DENIED_HALTED,
    FLATTEN_SUPERSEDE_AND_CREATE,
    ENVELOPE_FILL_REJECT,
    ENVELOPE_TRANSITION_APPLY,
    STAGE_DIVERGENCE,
    STAGE_REFUSED_STALE,
    STAGE_STAGED,
    EnvelopeActionPausedError,
    EnvelopeActionStageResult,
    PlannedAction,
    plan_stage_envelope_action,
    ENVELOPE_TRANSITION_NOOP,
    ENVELOPE_TRANSITION_REJECT,
    EnvelopeTransitionError,
    EnvelopeTransitionPlan,
    ORDER_TRANSITION_APPLY,
    ORDER_TRANSITION_NOOP,
    ORDER_TRANSITION_REJECT,
    OrderEventedTransitionPlan,
    ENVELOPE_RELEASING_TERMINALS,
    LIVE_ENVELOPE_STATUSES,
    VENUE_LIVE_ORDER_STATUSES,
    envelope_backing_intent_error,
    envelope_created_event,
    envelope_draft_reason,
    plan_envelope_fill,
    plan_envelope_transition,
    plan_supersede_envelope,
    plan_append_fill,
    plan_claim_order_for_submission,
    plan_close_session,
    plan_create_order_for_candidate,
    plan_create_order_for_sell_intent,
    plan_flatten_position,
    plan_quarantine_timed_out_order,
    plan_reconcile_resolve_order,
    plan_resolve_timeout_quarantine,
    plan_transition_order,
    reconcile_trading_state_event,
    trading_state_change_event,
    emergency_reduce_override_event,
    require_bool,
    require_recovery_status,
    require_status_enum,
    recovery_status_event,
    sell_intent_is_active,
)
from app.transitions import (
    ENVELOPE_TRANSITIONS,
    CANDIDATE_TIMESTAMP as _CANDIDATE_TIMESTAMP,
    CANDIDATE_TRANSITIONS as _CANDIDATE_TRANSITIONS,
    SELL_INTENT_TIMESTAMP as _SELL_INTENT_TIMESTAMP,
    SELL_INTENT_TRANSITIONS as _SELL_INTENT_TRANSITIONS,
)
from app.policy import (
    NON_TERMINAL_ORDER_STATUSES,
    candidate_numeric_reason,
    existing_exposure,
    order_candidate_match_reason,
    whole_count_reason,
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
        self._sell_intents: dict[str, SellIntent] = {}  # Phase 7
        self._envelopes: dict[str, ExecutionEnvelope] = {}  # ADR-010 / WO-0016
        # Spine v2 execution-event log (Phase 2): append-only, sequence order.
        # `_execution_event_dedupe` maps a non-null dedupe_key to its event for
        # O(1) INV-5 idempotency without scanning the log.
        self._execution_events: list[ExecutionEvent] = []
        self._execution_event_dedupe: dict[str, ExecutionEvent] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    async def initialize(self) -> None:
        async with self._lock:
            with self._atomic():
                self._backfill_fill_events_unlocked()
                self._backfill_trading_state_events_unlocked()
                self._backfill_order_status_events_unlocked()
                self._ensure_current_session_unlocked()

    def _backfill_order_status_events_unlocked(self) -> None:
        """WO-0007b read-flip migration: an order whose status predates WO-0007a
        eventing has no lifecycle events, so post-flip get_order would project
        CREATED. Emit one synthetic reconstruction event per such order so the
        projection yields its (pre-flip authoritative) column status. Runs AFTER the
        fill backfill so filled_quantity's FILL events already exist. Only touches
        orders with NO status-lifecycle events (they genuinely predate eventing) —
        never overrides an order that already has lifecycle events — and is idempotent
        (deterministic dedupe_key). Mirror of the SQLite backfill."""

        for order in self._orders.values():
            # WO-0013 (F-002): reconstruct ONLY orders with zero status-lifecycle
            # events. Keying on projected.status == CREATED was wrong: a legitimately
            # released order (SUBMIT_PENDING -> SUBMIT_RELEASED) also projects CREATED
            # while holding real lifecycle events, so it was clobbered by a synthetic
            # event. A FILL is excluded from the set (a position fact, not a status
            # event), so a pre-eventing FILLED order (fills backfilled, no lifecycle
            # event) is still correctly reconstructed.
            has_status_events = any(
                e.order_id == order.id and e.event_type in ORDER_STATUS_EVENT_TYPES
                for e in self._execution_events
            )
            if not has_status_events and order.status is not OrderStatus.CREATED:
                event = order_status_backfill_event(order)
                if event is not None:
                    self._append_execution_event_unlocked(event)

    def _backfill_trading_state_events_unlocked(self) -> None:
        """Ensure each session's derived ``TradingState`` (§8 / wave 3d) is
        reflected in the event log + the ``trading_state`` column. A pre-wave-3d
        session has ``trading_state='active'`` (the migration default) even when
        ``kill_switch``/``buys_paused`` say otherwise; emit a
        ``TRADING_STATE_CHANGED`` so ``current_trading_state()`` matches the derived
        state on restart (event-truth parity). Idempotent: a session already
        consistent (derived == projected) is a no-op. In-memory rarely hits this
        (sessions are born ACTIVE); it is the mirror of the SQLite backfill below."""

        for session in self._sessions:
            new_control = TradingState.of(
                kill_switch=session.kill_switch, buys_paused=session.buys_paused
            )
            control_prior = control_trading_state(self._execution_events, session.id)
            if control_prior is not new_control:
                event = trading_state_change_event(
                    session.id,
                    prior_control=control_prior,
                    kill_switch=session.kill_switch,
                    buys_paused=session.buys_paused,
                    reason="backfill",
                )
                if event is not None:
                    self._append_execution_event_unlocked(event)
            # Effective = control composed with any independent reconcile driver
            # (wave 4f); for a pre-4f log the reconcile driver is ACTIVE → == control.
            session.trading_state = compose_trading_state(
                new_control,
                reconcile_trading_state(self._execution_events, session.id),
            )

    def _backfill_fill_events_unlocked(self) -> None:
        """Ensure every fill row has a matching `FILL` event (wave 3a-truth).
        Position now derives from the event log, so a store opened on fill rows
        that predate the log would read a wrong (understated) position unless
        those fills are backfilled.

        Additive + identity-matched: for each fill in append order, append its
        event through the DEDUPED writer. A fill whose event already exists is a
        no-op (its deterministic ``dedupe_key`` — see ``execution_event_for_fill``
        — is already present); a fill lacking one appends it. This is idempotent,
        preserves order for the realizable pre-event-log migration (0 events →
        all appended in fill order), and — critically — NEVER deletes an event
        that has no fill row, since reconciliation-inferred fills (Phase 4) and
        directly-appended FILL events legitimately have none. A fresh store (0
        fills) is a no-op.
        """

        for fill in self._fills:
            self._append_execution_event_unlocked(execution_event_for_fill(fill))

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
        saved_envelopes = {
            k: v.model_copy(deep=True) for k, v in self._envelopes.items()
        }
        saved_sell_intents = {
            k: v.model_copy(deep=True) for k, v in self._sell_intents.items()
        }
        saved_fills = list(self._fills)
        saved_source_ids = set(self._fill_source_ids)
        saved_events = list(self._events)
        saved_sessions = [s.model_copy(deep=True) for s in self._sessions]
        saved_snapshots = list(self._position_snapshots)
        # Recovery records are append-then-replace (update swaps in a fresh copy,
        # never mutates in place), so a shallow snapshot restores correctly.
        saved_recoveries = list(self._submit_recoveries)
        # Execution-event log: append-only, elements never mutated in place, so
        # a shallow list copy + dict copy of the dedupe index restores fully.
        saved_execution_events = list(self._execution_events)
        saved_execution_dedupe = dict(self._execution_event_dedupe)
        try:
            yield
        except BaseException:
            self._watchlist = saved_watchlist
            self._candidates = saved_candidates
            self._orders = saved_orders
            self._envelopes = saved_envelopes
            self._sell_intents = saved_sell_intents
            self._fills = saved_fills
            self._submit_recoveries = saved_recoveries
            self._fill_source_ids = saved_source_ids
            self._events = saved_events
            self._sessions = saved_sessions
            self._position_snapshots = saved_snapshots
            self._execution_events = saved_execution_events
            self._execution_event_dedupe = saved_execution_dedupe
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
        # The owning candidate's id is the correlation key (D-020): default it
        # from candidate_id so every event in a candidate's lifecycle shares one
        # filterable key with no per-call-site threading. Same rule in
        # SqliteStateStore._insert_event — parity.
        #
        # X-004: candidate_id is always None for a sell order (XOR origin), so
        # the buy-side default alone left every generic order/fill/recovery
        # event for a protective sell with correlation_id=None —
        # order_submission_claimed, order_transition, order_fill_progress,
        # fill_appended/fill_rejected_*/fill_duplicate_ignored, order_stale,
        # stale_submitting_redrive_deferred, submit_recovery_* all lost the
        # sell_intent_id key, so GET /api/events?correlation_id=<sell_intent_id>
        # returned only the creation events, not the claim/fill/recovery trail
        # (only the sell-intent planners in app/store/core.py that explicitly
        # pass correlation_id=intent.id were unaffected). Resolved HERE, once,
        # for every call site: when neither an explicit correlation_id nor a
        # candidate_id is available but order_id is, look up that order's
        # sell_intent_id. A non-existent/unresolvable order_id (e.g. the
        # "unknown order" fill-reject path) simply finds nothing and falls
        # through to None, same as before.
        resolved_correlation_id = correlation_id or candidate_id
        if resolved_correlation_id is None and order_id is not None:
            owning_order = self._orders.get(order_id)
            if owning_order is not None and owning_order.sell_intent_id is not None:
                resolved_correlation_id = owning_order.sell_intent_id

        event = Event(
            event_type=str(event_type),
            message=message,
            symbol=symbol,
            candidate_id=candidate_id,
            order_id=order_id,
            fill_id=fill_id,
            payload=payload or {},
            session_id=session_id,
            correlation_id=resolved_correlation_id,
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
        # Event-truth (wave 3a-truth): position is derived from the append-only
        # execution-event log, not the fill table (a compatibility read-model).
        # Rule 7's "only fill events change position" now holds structurally over
        # the event log. Backfill (see initialize) guarantees a FILL event exists
        # for every fill row, so this reproduces the legacy fold exactly.
        return project_symbol_position(self._execution_events, symbol)

    def _fill_event_symbols_unlocked(self) -> set[str]:
        return {
            e.symbol
            for e in self._execution_events
            if e.event_type is ExecutionEventType.FILL and e.symbol is not None
        }

    def _current_exposure_unlocked(self) -> float:
        positions = [
            self._position_unlocked(s)
            for s in sorted(self._fill_event_symbols_unlocked())
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
                found = next((s for s in self._sessions if s.id == session_id), None)
                if found is None:
                    raise UnknownEntityError(
                        f"session {session_id} does not exist; cannot create candidate"
                    )
                session = found
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
            # W2-CAND (REV-0013/0014 / single-flight): refuse a SECOND active
            # (PENDING/APPROVED) candidate for the same symbol+session — return the
            # existing one idempotently, under the SAME lock as the insert, mirroring
            # create_sell_intent. Closes the strategy-loop TOCTOU / dev-inject /
            # retry double-candidate -> double-BUY-intent gap: buy-side single-flight
            # is now a store invariant, not a caller-side convention. "Active" =
            # PENDING/APPROVED (strategy_loop._OPEN_CANDIDATE_STATUSES); an ORDERED/
            # rejected/expired candidate no longer blocks a fresh proposal (re-buy).
            active = self._active_candidate_unlocked(key, session_id)
            if active is not None:
                return active.model_copy(deep=True)
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
    # Sell intents (Phase 7 — Sell-Side Protection)
    # ------------------------------------------------------------------ #
    def _order_needs_review_unlocked(self, order_id: str) -> bool:
        """X-003: whether ``order_id`` currently carries an OPEN
        ``needs_review`` broker-submit recovery record (D-017) — a broker order
        accepted upstream that local state can't otherwise confirm as live.
        Deliberately narrower than every open recovery status: an
        ``unresolved`` record is the recovery loop actively still working it
        (a normal, likely-transient in-progress cancel) and stays active for
        dedup; only the terminal-for-automation ``needs_review`` escalation
        (a real untracked position needing a human) frees the symbol."""

        return any(
            r.local_order_id == order_id and r.cleanup_status == RECOVERY_NEEDS_REVIEW
            for r in self._submit_recoveries
        )

    def _active_candidate_unlocked(
        self, symbol: str, session_id: str
    ) -> Optional[Candidate]:
        """The current active (PENDING/APPROVED) candidate for symbol+session, or
        None — the single-flight predicate for create_candidate (W2-CAND), the
        buy-side analogue of _active_sell_intent_unlocked. Newest-first so a legacy
        pre-invariant duplicate resolves deterministically to the latest."""
        for candidate in reversed(list(self._candidates.values())):
            if (
                candidate.symbol == symbol
                and candidate.session_id == session_id
                and candidate.status
                in (CandidateStatus.PENDING, CandidateStatus.APPROVED)
            ):
                return candidate
        return None

    def _active_sell_intent_unlocked(self, symbol: str) -> Optional[SellIntent]:
        for si in self._sell_intents.values():
            if si.symbol != symbol:
                continue
            order = self._orders.get(si.order_id) if si.order_id is not None else None
            needs_review = order is not None and self._order_needs_review_unlocked(
                order.id
            )
            if sell_intent_is_active(si, order, order_needs_review=needs_review):
                return si
        return None

    def _insert_sell_intent_unlocked(
        self,
        *,
        symbol: str,
        reason: SellReason,
        target_quantity: int,
        floor_price: Optional[float] = None,
        observed_price: Optional[float] = None,
        session_id: Optional[str] = None,
        actor: str = COMMAND_ACTOR_SYSTEM,
    ) -> SellIntent:
        """Build + insert a fresh sell intent row + its ``sell_intent_created``
        event (assumes the lock and an ``_atomic()`` block are already held by
        the caller — either the public ``create_sell_intent`` or
        ``flatten_position``, X-001). No input validation: a caller that
        accepts external input (``create_sell_intent``) validates before
        calling this; a caller building the intent from trusted internal state
        (``flatten_position``, sizing from the live position) does not need to.
        """

        intent = SellIntent(
            symbol=symbol,
            reason=reason,
            target_quantity=target_quantity,
            floor_price=floor_price,
            observed_price=observed_price,
            session_id=session_id,
        )
        self._sell_intents[intent.id] = intent
        self._append_event_unlocked(
            "sell_intent_created",
            message=f"sell intent ({reason.value}) created for {symbol}",
            symbol=symbol,
            session_id=session_id,
            correlation_id=intent.id,
            payload={
                "reason": reason.value,
                "target_quantity": target_quantity,
                # Who commanded a created MANUAL_FLATTEN (REV-0002 F-002); the
                # default keeps a protection-tick create_sell_intent at "system".
                "actor": actor,
            },
        )
        return intent

    def _transition_sell_intent_unlocked(
        self,
        intent: SellIntent,
        new_status: SellIntentStatus,
        *,
        order_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """Apply a sell-intent status transition in place (assumes the lock and
        an ``_atomic()`` block are already held by the caller). Returns
        ``False`` for a same-status no-op (nothing applied, no event written);
        ``True`` if it actually transitioned. Raises
        :class:`SellIntentTransitionError` for an illegal transition (nothing
        mutated). ``reason`` (WO-0036 R2) lands in the event payload so an
        envelope-driven transition is distinguishable from a legacy one.
        """

        current = intent.status
        if new_status is current:
            return False
        if new_status not in _SELL_INTENT_TRANSITIONS.get(current, set()):
            raise SellIntentTransitionError(
                f"illegal sell intent transition {current.value} -> {new_status.value}"
            )
        intent.status = new_status
        intent.updated_at = utcnow()
        ts_field = _SELL_INTENT_TIMESTAMP.get(new_status)
        if ts_field:
            setattr(intent, ts_field, utcnow())
        if new_status is SellIntentStatus.ORDERED and order_id is not None:
            intent.order_id = order_id
        payload: dict = {"from": current.value, "to": new_status.value}
        if reason is not None:
            payload["reason"] = reason
        self._append_event_unlocked(
            "sell_intent_transition",
            message=f"sell intent {current.value} -> {new_status.value}",
            symbol=intent.symbol,
            order_id=order_id,
            payload=payload,
            session_id=intent.session_id,
            correlation_id=intent.id,
        )
        return True

    async def create_sell_intent(
        self,
        *,
        symbol: str,
        reason: SellReason,
        target_quantity: int,
        floor_price: Optional[float] = None,
        observed_price: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> SellIntent:
        if not isinstance(reason, SellReason):
            raise InvalidOrderError(
                f"sell intent reason must be a SellReason, not {reason!r}"
            )
        key = normalize_symbol(symbol)
        bad = whole_count_reason(target_quantity)
        if bad is not None or target_quantity <= 0:
            raise InvalidOrderError(
                f"sell intent for {key} needs a positive whole target_quantity "
                f"(got {target_quantity!r})"
            )
        async with self._lock:
            # Single-flight (atomic dedup): the active-check and the insert are one
            # lock hold, so a flatten POST and a protection tick cannot both create
            # an intent for the same symbol.
            active = self._active_sell_intent_unlocked(key)
            if active is not None:
                return active.model_copy(deep=True)
            # ENG-001 / INV-060: the kill switch blocks NEW autonomous order intent.
            # A PROTECTION_FLOOR exit must not be created while Halted — checked here
            # under the SAME lock as the insert so a kill landing during the
            # protection tick's own awaits cannot race the create (the tick's
            # pre-check can go stale). An already-active exit was returned above and
            # stays idempotent; manual flatten has its own Halted-deny.
            if reason is SellReason.PROTECTION_FLOOR:
                session = self._ensure_current_session_unlocked()
                if (
                    current_trading_state(self._execution_events, session.id)
                    is TradingState.HALTED
                ):
                    raise ProtectionHaltedError(
                        f"autonomous protection exit for {key} refused: trading "
                        "halted (kill switch engaged)"
                    )
            with self._atomic():
                intent = self._insert_sell_intent_unlocked(
                    symbol=key,
                    reason=reason,
                    target_quantity=target_quantity,
                    floor_price=floor_price,
                    observed_price=observed_price,
                    session_id=session_id,
                )
            return intent.model_copy(deep=True)

    async def transition_sell_intent(
        self,
        intent_id: str,
        new_status: SellIntentStatus,
        *,
        order_id: Optional[str] = None,
    ) -> SellIntent:
        require_status_enum(new_status, SellIntentStatus, field="new_status")
        async with self._lock:
            intent = self._sell_intents.get(intent_id)
            if intent is None:
                raise UnknownEntityError(f"sell intent {intent_id} not found")
            # WO-0036 R2 exclusive driver: while a LIVE envelope backs the
            # intent, the envelope alone drives its lifecycle (activation
            # normalizes it, terminal release expires it) — an out-of-band
            # transition here would desync the two lifecycles.
            live_env = self._live_envelope_for_intent_unlocked(intent_id)
            if live_env is not None:
                raise SellIntentTransitionError(
                    f"sell intent {intent_id} is bound to live execution "
                    f"envelope {live_env.id}; its lifecycle is driven by the "
                    "envelope (WO-0036 R2 link)"
                )
            with self._atomic():
                self._transition_sell_intent_unlocked(
                    intent, new_status, order_id=order_id
                )
            return intent.model_copy(deep=True)

    async def get_sell_intent(self, intent_id: str) -> Optional[SellIntent]:
        async with self._lock:
            si = self._sell_intents.get(intent_id)
            return si.model_copy(deep=True) if si else None

    async def list_sell_intents(
        self,
        *,
        session_id: Optional[str] = None,
        status: Optional[SellIntentStatus] = None,
        symbol: Optional[str] = None,
    ) -> list[SellIntent]:
        if status is not None:
            require_status_enum(status, SellIntentStatus, field="status filter")
        key = normalize_symbol(symbol) if symbol is not None else None
        async with self._lock:
            out = []
            for si in self._sell_intents.values():
                if session_id is not None and si.session_id != session_id:
                    continue
                if status is not None and si.status is not status:
                    continue
                if key is not None and si.symbol != key:
                    continue
                out.append(si.model_copy(deep=True))
            return out

    async def active_sell_intent_for(self, symbol: str) -> Optional[SellIntent]:
        key = normalize_symbol(symbol)
        async with self._lock:
            active = self._active_sell_intent_unlocked(key)
            return active.model_copy(deep=True) if active else None

    # ------------------------------------------------------------------ #
    # Execution envelopes (ADR-010 / WO-0016)
    # ------------------------------------------------------------------ #
    def _other_live_envelope_for_symbol_unlocked(
        self, symbol: str, *, excluding: str
    ) -> Optional[ExecutionEnvelope]:
        """Any OTHER envelope for this SYMBOL currently LIVE (ACTIVE or
        FROZEN) — the per-symbol single-mandate rail (WO-0032 / REV-0023 P0,
        INV-087; the SQLite partial unique index on ACTIVE stays the storage
        backstop).

        Scoped to symbol, NOT ``sell_intent_id``: at most one live selling
        mandate per symbol/position — two mandates could each stage a
        full-size SELL against one position. FROZEN counts as live (WO-0036
        R2): a kill-frozen mandate's child may still rest at the venue, so
        activating a SECOND envelope next to it is the same double-booking the
        ACTIVE clash forbids — the frozen one must be resumed or wound down
        (cancel refuses while its child is live) first."""

        key = normalize_symbol(symbol)
        for env in self._envelopes.values():
            if (
                env.id != excluding
                and env.symbol == key
                and env.status in LIVE_ENVELOPE_STATUSES
            ):
                return env
        return None

    def _live_envelope_for_intent_unlocked(
        self, intent_id: str
    ) -> Optional[ExecutionEnvelope]:
        """The LIVE (ACTIVE/FROZEN) envelope backing ``intent_id``, or None —
        the R2 exclusive-driver predicate: while it exists, the envelope alone
        drives the intent's lifecycle and dispatch."""

        for env in self._envelopes.values():
            if env.sell_intent_id == intent_id and env.status in LIVE_ENVELOPE_STATUSES:
                return env
        return None

    def _validate_backing_intent_unlocked(
        self, envelope: ExecutionEnvelope
    ) -> SellIntent:
        """Load + validate the backing intent for an activation (WO-0036 R2 /
        Codex PR#8 #8): it must exist, match the symbol, and be PENDING or
        APPROVED. Returns the LIVE intent object (the caller normalizes
        PENDING→APPROVED inside its atomic block via
        ``_link_backing_intent_unlocked``); raises the shared planner error
        otherwise. Runs on EVERY entry into ACTIVE — approve, generic
        transition, resume — so no activation path can mint an owner-less or
        mismatched mandate."""

        intent = self._sell_intents.get(envelope.sell_intent_id)
        error = envelope_backing_intent_error(
            intent, symbol=envelope.symbol, envelope_id=envelope.id
        )
        if error is not None:
            raise error
        assert intent is not None  # narrowed by the validator
        return intent

    def _link_backing_intent_unlocked(self, intent: SellIntent) -> None:
        """Normalize a PENDING backing intent to APPROVED atomically with the
        envelope's activation (the envelope approval IS the human approval of
        the exit — WO-0036 R2). Assumes the lock and an ``_atomic()`` block are
        held; a no-op for an already-APPROVED intent."""

        if intent.status is SellIntentStatus.PENDING:
            self._transition_sell_intent_unlocked(
                intent, SellIntentStatus.APPROVED, reason="envelope_activation"
            )

    def _release_intent_for_terminal_envelope_unlocked(
        self, envelope: ExecutionEnvelope
    ) -> None:
        """WO-0036 R2 terminal propagation: an envelope entering a RELEASING
        terminal (COMPLETED/EXPIRED/EXHAUSTED/BREACHED/CANCELLED — never
        SUPERSEDED, the successor keeps the intent) expires its backing intent
        so the symbol becomes eligible for fresh protection. Assumes the lock
        and an ``_atomic()`` block are held (runs inside the same atomic unit
        as the envelope's own transition). Skips when: the envelope never
        activated (a rejected/expired draft never owned the intent), the
        intent is already terminal/ORDERED, ANOTHER live envelope still
        carries the mandate, or a child of THIS envelope may still be live at
        the venue — BREACHED/EXHAUSTED/REST_AT_FLOOR (and an EXPIRED cancel
        mid-convergence) leave the working order resting, and releasing the
        symbol then would let fresh protection double-book it; the
        child-terminal hook below completes the release when that last
        obligation ends."""

        if envelope.status not in ENVELOPE_RELEASING_TERMINALS:
            return
        if envelope.activated_at is None:
            return  # never activated — it never owned the intent
        intent = self._sell_intents.get(envelope.sell_intent_id)
        if intent is None or intent.status not in (
            SellIntentStatus.PENDING,
            SellIntentStatus.APPROVED,
        ):
            return
        for other in self._envelopes.values():
            if (
                other.id != envelope.id
                and other.sell_intent_id == envelope.sell_intent_id
                and other.status in LIVE_ENVELOPE_STATUSES
            ):
                return  # the mandate lives on in another envelope
        if self._envelope_has_live_child_unlocked(envelope):
            return  # a resting/ambiguous child is still a live obligation
        self._transition_sell_intent_unlocked(
            intent, SellIntentStatus.EXPIRED, reason="envelope_terminal"
        )

    def _release_intent_for_terminal_child_unlocked(self, order: Order) -> None:
        """The child-terminal half of the R2 release: an envelope in a
        releasing terminal may still hold the symbol through a RESTING child
        (see above) — when that child reaches a venue terminal, re-run the
        release against its envelope in the SAME atomic unit as the order
        write. No-ops for non-envelope orders and for envelopes still live."""

        if order.status not in (
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
        ):
            return
        for event in self._execution_events:
            if (
                event.order_id == order.id
                and event.event_type is ExecutionEventType.ENVELOPE_ACTION
                and event.envelope_id is not None
            ):
                env = self._envelopes.get(event.envelope_id)
                if env is not None:
                    self._release_intent_for_terminal_envelope_unlocked(env)
                return

    def _envelope_has_live_child_unlocked(self, envelope: ExecutionEnvelope) -> bool:
        """Whether ANY child of the envelope MAY be live at the venue.
        CREATED is NOT live (local-only staging — the preemption sweep cancels
        it atomically, WO-0024); TIMEOUT_QUARANTINE IS live (ADR-002: an
        ambiguous submit may be working). Used by the flatten preemption and
        the terminal release, so an envelope is never CANCELLED — and its
        intent never released — out from under a possibly-live child.

        Deliberately scans EVERY child, never the single "newest working
        order": a staged CREATED reprice replacement is newer than the live
        predecessor it would replace, and a newest-wins view would MASK that
        predecessor (the Codex PR#8 #6 shape) — reading "no live child" while
        a SELL still rests at the venue."""

        for event in self._execution_events:
            if (
                event.envelope_id != envelope.id
                or event.event_type is not ExecutionEventType.ENVELOPE_ACTION
                or event.order_id is None
            ):
                continue
            order = self._orders.get(event.order_id)
            if order is not None and order.status in VENUE_LIVE_ORDER_STATUSES:
                return True
        return False

    def _live_envelope_exit_unlocked(
        self, symbol: str
    ) -> tuple[Optional[Order], Optional[SellIntent]]:
        """(live-at-venue child order, its envelope's backing intent) for the
        symbol's LIVE envelopes, or (None, None) — the flatten planner's R2
        input (Codex PR#8 #4). The newest venue-live child wins, mirroring the
        working-order convention (latest action sequence)."""

        live_env_ids = {
            env.id: env
            for env in self._envelopes.values()
            if env.symbol == symbol and env.status in LIVE_ENVELOPE_STATUSES
        }
        if not live_env_ids:
            return None, None
        child: Optional[Order] = None
        owner: Optional[ExecutionEnvelope] = None
        for event in self._execution_events:
            if (
                event.envelope_id not in live_env_ids
                or event.event_type is not ExecutionEventType.ENVELOPE_ACTION
                or event.order_id is None
            ):
                continue
            order = self._orders.get(event.order_id)
            if order is not None and order.status in VENUE_LIVE_ORDER_STATUSES:
                child = order
                owner = live_env_ids[event.envelope_id]
        if child is None or owner is None:
            return None, None
        return child, self._sell_intents.get(owner.sell_intent_id)

    def _apply_envelope_transition_unlocked(
        self, plan: EnvelopeTransitionPlan
    ) -> ExecutionEnvelope:
        """Persist an APPLY-outcome transition plan (assumes lock + _atomic).
        The caller has already dispatched NOOP/REJECT and run the
        single-ACTIVE check where the target is ACTIVE.

        WO-0036 R2: this is the ONE choke point every envelope status write
        flows through (supersession excepted — SUPERSEDED transfers, never
        releases), so the terminal propagation lives here: entering a
        releasing terminal expires the backing intent in the SAME atomic unit,
        sequenced after the envelope's own events."""

        assert plan.envelope is not None
        assert plan.execution_event is not None and plan.audit_event is not None
        stored = plan.envelope.model_copy(deep=True)
        self._envelopes[stored.id] = stored
        self._append_execution_event_unlocked(plan.execution_event)
        self._append_event_unlocked(
            plan.audit_event.event_type, **plan.audit_event.as_kwargs()
        )
        self._release_intent_for_terminal_envelope_unlocked(stored)
        return stored

    async def create_envelope(
        self,
        envelope: ExecutionEnvelope,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
    ) -> ExecutionEnvelope:
        bad = envelope_draft_reason(envelope)
        if bad is not None:
            raise InvalidOrderError(bad)
        key = normalize_symbol(envelope.symbol)
        async with self._lock:
            if envelope.id in self._envelopes:
                raise InvalidOrderError(f"envelope {envelope.id} already exists")
            stored = envelope.model_copy(deep=True, update={"symbol": key})
            with self._atomic():
                self._envelopes[stored.id] = stored
                self._append_execution_event_unlocked(
                    envelope_created_event(stored, actor=actor)
                )
                self._append_event_unlocked(
                    "envelope_created",
                    message=f"execution envelope created for {key}",
                    symbol=key,
                    session_id=stored.session_id,
                    correlation_id=stored.sell_intent_id,
                    payload={"actor": actor, "envelope_id": stored.id},
                )
            return stored.model_copy(deep=True)

    async def get_envelope(self, envelope_id: str) -> Optional[ExecutionEnvelope]:
        async with self._lock:
            env = self._envelopes.get(envelope_id)
            return env.model_copy(deep=True) if env else None

    async def list_envelopes(
        self,
        *,
        sell_intent_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[EnvelopeStatus] = None,
    ) -> list[ExecutionEnvelope]:
        if status is not None:
            require_status_enum(status, EnvelopeStatus, field="status filter")
        key = normalize_symbol(symbol) if symbol is not None else None
        async with self._lock:
            return [
                env.model_copy(deep=True)
                for env in self._envelopes.values()
                if (sell_intent_id is None or env.sell_intent_id == sell_intent_id)
                and (key is None or env.symbol == key)
                and (status is None or env.status is status)
            ]

    async def transition_envelope(
        self,
        envelope_id: str,
        new_status: EnvelopeStatus,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
        reason: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> ExecutionEnvelope:
        require_status_enum(new_status, EnvelopeStatus, field="new_status")
        async with self._lock:
            env = self._envelopes.get(envelope_id)
            if env is None:
                raise UnknownEntityError(f"envelope {envelope_id} not found")
            plan = plan_envelope_transition(
                env, new_status, actor=actor, reason=reason, now=now
            )
            if plan.outcome == ENVELOPE_TRANSITION_REJECT:
                assert plan.error is not None
                raise plan.error
            if plan.outcome == ENVELOPE_TRANSITION_NOOP:
                return env.model_copy(deep=True)
            if new_status is EnvelopeStatus.ACTIVE:
                # ADR-010 §4 / INV-060: activation OR resume is new standing
                # order intent — refused while HALTED, checked under the SAME
                # lock hold as the write (resume after release is an explicit
                # human action; it is never automatic).
                session = self._ensure_current_session_unlocked()
                if (
                    current_trading_state(self._execution_events, session.id)
                    is TradingState.HALTED
                ):
                    raise OrderIntentBlockedError(
                        f"envelope {env.id} cannot enter ACTIVE: trading "
                        "halted (kill switch engaged)"
                    )
                clash = self._other_live_envelope_for_symbol_unlocked(
                    env.symbol, excluding=env.id
                )
                if clash is not None:
                    raise EnvelopeTransitionError(
                        f"envelope {clash.id} is already live "
                        f"({clash.status.value}) for symbol {env.symbol} "
                        "(per-symbol single-ACTIVE mandate, INV-087)"
                    )
                # WO-0036 R2: EVERY entry into ACTIVE (first activation AND
                # resume) validates the backing-intent link — this generic
                # edge must not be the one activation path with a bypass.
                backing_intent = self._validate_backing_intent_unlocked(env)
            if new_status is EnvelopeStatus.CANCELLED:
                # Codex PR#8 #5: a FROZEN envelope may still have a LIVE child at
                # the venue (kill-switch froze a formerly-ACTIVE mandate whose
                # submitted SELL is still working). A store-only CANCELLED would
                # stop monitoring it while the order keeps working — refuse; the
                # live order must be wound down first (flatten/kill precedence).
                # A quarantined (ambiguous) child counts as live.
                try:
                    _, working = self._envelope_action_context_unlocked(env)
                    live_child = working is not None
                except EnvelopeActionPausedError:
                    live_child = True
                if live_child:
                    raise EnvelopeTransitionError(
                        f"envelope {env.id} cannot be CANCELLED while a child "
                        "order is live at the venue — wind it down first "
                        "(flatten / kill switch), then cancel"
                    )
            with self._atomic():
                if new_status is EnvelopeStatus.ACTIVE:
                    # R2 link: the envelope approval IS the intent approval —
                    # normalized atomically with the activation write.
                    self._link_backing_intent_unlocked(backing_intent)
                stored = self._apply_envelope_transition_unlocked(plan)
                # A freeze is never exited by a fill: an envelope fully filled
                # while FROZEN completes HERE, on resume, atomically with it.
                if (
                    stored.status is EnvelopeStatus.ACTIVE
                    and (stored.remaining_quantity or 0) == 0
                ):
                    chain = plan_envelope_transition(
                        stored,
                        EnvelopeStatus.COMPLETED,
                        actor="engine",
                        reason="fully filled while frozen; completed on resume",
                        now=now,
                    )
                    assert chain.outcome == ENVELOPE_TRANSITION_APPLY
                    stored = self._apply_envelope_transition_unlocked(chain)
            return stored.model_copy(deep=True)

    async def supersede_envelope(
        self,
        old_envelope_id: str,
        successor: ExecutionEnvelope,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
        reason: Optional[str] = None,
    ) -> ExecutionEnvelope:
        async with self._lock:
            old = self._envelopes.get(old_envelope_id)
            if old is None:
                raise UnknownEntityError(f"envelope {old_envelope_id} not found")
            if successor.id in self._envelopes:
                raise InvalidOrderError(
                    f"successor envelope {successor.id} already exists"
                )
            normalized = successor.model_copy(
                update={"symbol": normalize_symbol(successor.symbol)}
            )
            _, working = self._envelope_action_context_unlocked(old)
            # WO-0036 R2 (masked-predecessor class): the planner's live-order
            # block evaluates the single NEWEST working order — a staged
            # CREATED replacement would mask a still-resting predecessor and
            # wave the amendment through next to it (the INV-077 double
            # exposure WO-0027 rule (i) exists to prevent). Belt with the
            # every-child scan before planning.
            if self._envelope_has_live_child_unlocked(old):
                raise EnvelopeTransitionError(
                    f"envelope {old.id} may still have a live working order "
                    "at the venue; cancel it before superseding — a successor "
                    "next to a resting predecessor order is double exposure "
                    "(INV-077)"
                )
            plan = plan_supersede_envelope(
                old, normalized, actor=actor, reason=reason, working_order=working
            )
            if plan.outcome == ENVELOPE_TRANSITION_REJECT:
                assert plan.error is not None
                raise plan.error
            assert plan.old_envelope is not None and plan.new_envelope is not None
            # Belt over the planner's braces: no OTHER envelope for the symbol
            # may be live while the successor takes over (the old one is
            # leaving ACTIVE inside this same atomic unit).
            clash = self._other_live_envelope_for_symbol_unlocked(
                old.symbol, excluding=old.id
            )
            if clash is not None:
                raise EnvelopeTransitionError(
                    f"envelope {clash.id} is already live "
                    f"({clash.status.value}) for symbol {old.symbol} "
                    "(per-symbol single-ACTIVE mandate, INV-087)"
                )
            with self._atomic():
                self._envelopes[plan.old_envelope.id] = plan.old_envelope.model_copy(
                    deep=True
                )
                self._envelopes[plan.new_envelope.id] = plan.new_envelope.model_copy(
                    deep=True
                )
                for event in plan.execution_events:
                    self._append_execution_event_unlocked(event)
                assert plan.audit_event is not None
                self._append_event_unlocked(
                    plan.audit_event.event_type, **plan.audit_event.as_kwargs()
                )
                # WO-0027: the superseded mandate's staged CREATED orders die
                # with it, in the SAME atomic unit (live venue orders were
                # refused above — nothing of the old mandate survives).
                self._cancel_staged_envelope_orders_unlocked(
                    [plan.old_envelope.id], actor=actor
                )
            return plan.new_envelope.model_copy(deep=True)

    async def record_envelope_fill(
        self,
        envelope_id: str,
        *,
        quantity: int,
        dedupe_key: str,
        price: float,
        order_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ts_event: Optional[datetime] = None,
        source: EventSource = EventSource.BROKER_REST,
        authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
        now: Optional[datetime] = None,
    ) -> ExecutionEnvelope:
        """Apply one deduped fill fact — the ONLY remaining_quantity writer.
        A dedupe hit (same ``dedupe_key`` already in the log) applies NOTHING:
        that fill was already counted (exactly-once, INV-5)."""

        async with self._lock:
            env = self._envelopes.get(envelope_id)
            if env is None:
                raise UnknownEntityError(f"envelope {envelope_id} not found")
            plan = plan_envelope_fill(
                env,
                quantity=quantity,
                dedupe_key=dedupe_key,
                price=price,
                order_id=order_id,
                session_id=session_id,
                ts_event=ts_event,
                source=source,
                authority=authority,
                now=now,
            )
            if plan.outcome == ENVELOPE_FILL_REJECT:
                assert plan.error is not None
                raise plan.error
            assert plan.envelope is not None and plan.fill_event is not None
            if self._execution_event_dedupe.get(dedupe_key) is not None:
                return env.model_copy(deep=True)
            with self._atomic():
                self._append_execution_event_unlocked(plan.fill_event)
                stored = plan.envelope.model_copy(deep=True)
                self._envelopes[stored.id] = stored
                if plan.transition is not None:
                    assert plan.transition.outcome == ENVELOPE_TRANSITION_APPLY
                    stored = self._apply_envelope_transition_unlocked(plan.transition)
            return stored.model_copy(deep=True)

    def _envelope_action_context_unlocked(
        self, envelope: ExecutionEnvelope
    ) -> tuple[list[ExecutionEvent], Optional[Order]]:
        """(action events, current working order) for one envelope, read under
        the lock. Raises :class:`EnvelopeActionPausedError` if any of the
        envelope's orders is in TIMEOUT_QUARANTINE (ADR-002 pause)."""

        actions = [
            e
            for e in self._execution_events
            if e.envelope_id == envelope.id
            and e.event_type is ExecutionEventType.ENVELOPE_ACTION
        ]
        working: Optional[Order] = None
        for event in actions:  # sequence order: latest live order wins
            if event.order_id is None:
                continue
            order = self._orders.get(event.order_id)
            if order is None:
                continue
            if order.status is OrderStatus.TIMEOUT_QUARANTINE:
                raise EnvelopeActionPausedError(
                    f"envelope {envelope.id} is paused: order {order.id} is in "
                    "timeout quarantine (resolve it before any further action)"
                )
            if order.status not in (
                OrderStatus.FILLED,
                OrderStatus.CANCELED,
                OrderStatus.REJECTED,
            ):
                working = order
        return actions, working

    async def stage_envelope_action(
        self,
        envelope_id: str,
        action: PlannedAction,
        *,
        snapshot_fingerprint: str,
        actor: str = COMMAND_ACTOR_SYSTEM,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> EnvelopeActionStageResult:
        """WO-0019: the write-time half of D-3, one lock hold + one atomic
        block. ``now`` is the injected validation clock (engine discipline —
        cooldown math never reads a bare wall clock when the caller ticks).
        See :func:`app.store.core.plan_stage_envelope_action`."""

        async with self._lock:
            env = self._envelopes.get(envelope_id)
            if env is None:
                raise UnknownEntityError(f"envelope {envelope_id} not found")
            # INV-060: staging is new order intent — refused while HALTED,
            # checked under the SAME lock as the writes below.
            session = self._ensure_current_session_unlocked()
            if (
                current_trading_state(self._execution_events, session.id)
                is TradingState.HALTED
            ):
                raise OrderIntentBlockedError(
                    "envelope action refused: trading halted (kill switch engaged)"
                )
            actions, working = self._envelope_action_context_unlocked(env)
            if session_id is None:
                session_id = session.id
            plan = plan_stage_envelope_action(
                env,
                action,
                history=actions,
                working_order=working,
                session_id=session_id,
                snapshot_fingerprint=snapshot_fingerprint,
                actor=actor,
                now=now,
                # WO-0026: live fill-derived position, read under the SAME
                # lock as the writes — the reduce-only hard rail's truth.
                current_position=self._position_unlocked(env.symbol).quantity,
            )
            if plan.error is not None:
                raise plan.error
            with self._atomic():
                if plan.outcome == STAGE_DIVERGENCE:
                    assert plan.freeze is not None
                    frozen = self._apply_envelope_transition_unlocked(plan.freeze)
                    assert plan.divergence_event is not None
                    assert plan.audit_event is not None
                    self._append_execution_event_unlocked(plan.divergence_event)
                    self._append_event_unlocked(
                        plan.audit_event.event_type, **plan.audit_event.as_kwargs()
                    )
                    return EnvelopeActionStageResult(
                        STAGE_DIVERGENCE, envelope=frozen.model_copy(deep=True)
                    )
                if plan.outcome == STAGE_REFUSED_STALE:
                    # WO-0029A: benign stale-plan refusal — evented, envelope
                    # untouched, no order, zero venue calls.
                    assert plan.action_event is not None
                    assert plan.audit_event is not None
                    self._append_execution_event_unlocked(plan.action_event)
                    self._append_event_unlocked(
                        plan.audit_event.event_type, **plan.audit_event.as_kwargs()
                    )
                    return EnvelopeActionStageResult(
                        STAGE_REFUSED_STALE, envelope=env.model_copy(deep=True)
                    )
                assert plan.order is not None and plan.action_event is not None
                assert plan.audit_event is not None
                self._orders[plan.order.id] = plan.order.model_copy(deep=True)
                self._append_execution_event_unlocked(plan.action_event)
                self._append_event_unlocked(
                    plan.audit_event.event_type, **plan.audit_event.as_kwargs()
                )
            return EnvelopeActionStageResult(
                STAGE_STAGED,
                envelope=env.model_copy(deep=True),
                order=plan.order.model_copy(deep=True),
                working_order=(
                    working.model_copy(deep=True) if working is not None else None
                ),
            )

    async def approve_envelope_activation(
        self,
        draft: ExecutionEnvelope,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
    ) -> ExecutionEnvelope:
        """The WO-0017 approval surface: dedup/idempotency → HALTED check →
        create → approve → activate → events, ONE lock hold + ONE atomic block
        (ENG-001 shape). A kill that lands first blocks the op with ZERO
        artifacts; re-approving an ACTIVE envelope is an idempotent no-op."""

        async with self._lock:
            stored = self._envelopes.get(draft.id)
            if stored is not None:
                if stored.status is EnvelopeStatus.ACTIVE:
                    return stored.model_copy(deep=True)  # idempotent re-approve
                if stored.status not in (
                    EnvelopeStatus.PENDING,
                    EnvelopeStatus.APPROVED,
                ):
                    raise EnvelopeTransitionError(
                        f"cannot approve envelope {draft.id}: it is "
                        f"{stored.status.value}"
                    )
            else:
                bad = envelope_draft_reason(draft)
                if bad is not None:
                    raise InvalidOrderError(bad)
            # INV-060: the kill switch blocks NEW standing order intent — the
            # check shares this lock hold with every write below (no await
            # window), so a kill either lands before (zero artifacts) or after
            # (the kill hook freezes the activated envelope).
            session = self._ensure_current_session_unlocked()
            if (
                current_trading_state(self._execution_events, session.id)
                is TradingState.HALTED
            ):
                raise OrderIntentBlockedError(
                    "envelope activation refused: trading halted (kill switch engaged)"
                )
            symbol = (stored or draft).symbol
            clash = self._other_live_envelope_for_symbol_unlocked(
                symbol, excluding=draft.id
            )
            if clash is not None:
                raise EnvelopeTransitionError(
                    f"envelope {clash.id} is already live "
                    f"({clash.status.value}) for symbol {symbol} "
                    "(per-symbol single-ACTIVE mandate, INV-087)"
                )
            # WO-0036 R2 (Codex PR#8 #8): LOAD + validate the backing intent
            # before anything is minted — a typo'd sell_intent_id or symbol
            # must never produce an owner-less ACTIVE mandate. Read-only here;
            # the PENDING→APPROVED normalization joins the atomic block below.
            backing_intent = self._validate_backing_intent_unlocked(
                (stored or draft).model_copy(
                    update={"symbol": normalize_symbol(symbol)}
                )
            )
            with self._atomic():
                if stored is None:
                    key = normalize_symbol(draft.symbol)
                    stored = draft.model_copy(deep=True, update={"symbol": key})
                    self._envelopes[stored.id] = stored
                    self._append_execution_event_unlocked(
                        envelope_created_event(stored, actor=actor)
                    )
                    self._append_event_unlocked(
                        "envelope_created",
                        message=f"execution envelope created for {stored.symbol}",
                        symbol=stored.symbol,
                        session_id=stored.session_id,
                        correlation_id=stored.sell_intent_id,
                        payload={"actor": actor, "envelope_id": stored.id},
                    )
                # R2 link: the envelope approval IS the intent approval —
                # normalized atomically with the activation chain below.
                self._link_backing_intent_unlocked(backing_intent)
                current = stored
                if current.status is EnvelopeStatus.PENDING:
                    plan = plan_envelope_transition(
                        current, EnvelopeStatus.APPROVED, actor=actor
                    )
                    assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                    current = self._apply_envelope_transition_unlocked(plan)
                plan = plan_envelope_transition(
                    current, EnvelopeStatus.ACTIVE, actor=actor
                )
                assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                current = self._apply_envelope_transition_unlocked(plan)
            return current.model_copy(deep=True)

    def _cancel_symbol_envelopes_unlocked(
        self, symbol: str, *, actor: str, reason: str
    ) -> None:
        """ADR-010 §4 / D-2: cancel every non-terminal envelope for ``symbol``
        through legal edges (ACTIVE goes via FROZEN) — the manual-flatten
        preemption. Assumes the lock and an ``_atomic()`` block are held, so
        the preemption commits in the SAME atomic unit as the flatten's own
        writes and its events sequence BEFORE them.

        WO-0036 R2: an envelope whose child MAY be live at the venue is
        SKIPPED (evented), never cancelled out from under it — the internal
        twin of the public transition_envelope→CANCELLED live-child guard
        (Codex PR#8 #5). The flatten's own deferral makes this unreachable on
        the create branch; it stands as the choke-point rule so the FLAT
        branch (and any future caller) cannot strand a live order under a
        terminal envelope either."""

        preempted: list[str] = []
        for env in list(self._envelopes.values()):
            if env.symbol != symbol:
                continue
            if not ENVELOPE_TRANSITIONS.get(env.status):
                continue  # terminal — nothing to preempt
            if self._envelope_has_live_child_unlocked(env):
                self._append_event_unlocked(
                    "envelope_preemption_deferred",
                    message=(
                        f"envelope {env.id} preemption deferred: its child may "
                        "be live at the venue (wind it down first)"
                    ),
                    symbol=symbol,
                    payload={
                        "envelope_id": env.id,
                        "reason": "live_child_at_venue",
                        "preemption_reason": reason,
                        "actor": actor,
                    },
                    session_id=env.session_id,
                    correlation_id=env.sell_intent_id,
                )
                continue
            current = env
            if current.status is EnvelopeStatus.ACTIVE:
                plan = plan_envelope_transition(
                    current, EnvelopeStatus.FROZEN, actor=actor, reason=reason
                )
                assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                current = self._apply_envelope_transition_unlocked(plan)
            plan = plan_envelope_transition(
                current, EnvelopeStatus.CANCELLED, actor=actor, reason=reason
            )
            assert plan.outcome == ENVELOPE_TRANSITION_APPLY
            self._apply_envelope_transition_unlocked(plan)
            preempted.append(env.id)
        # WO-0024: a preempted mandate's obligations die with it — its staged
        # CREATED orders are cancelled in the SAME atomic unit, sequenced
        # AFTER the envelope cancellation events
        # (FINDING-W3-staged-order-outlives-preemption).
        self._cancel_staged_envelope_orders_unlocked(preempted, actor=actor)

    def _cancel_staged_envelope_orders_unlocked(
        self, envelope_ids: list[str], *, actor: str
    ) -> None:
        """Locally CANCEL every CREATED order staged by the given envelopes
        (WO-0024). Assumes the lock and an ``_atomic()`` block are held.
        CREATED means never venue-submitted, so this is a pure local-truth
        write — no venue call belongs here. SUBMITTING/SUBMITTED orders are
        untouched: venue-side wind-down stays with the monitoring loop."""

        if not envelope_ids:
            return
        wanted = set(envelope_ids)
        seen: set[str] = set()
        for event in self._execution_events:
            if (
                event.envelope_id not in wanted
                or event.event_type is not ExecutionEventType.ENVELOPE_ACTION
                or event.order_id is None
                or event.order_id in seen
            ):
                continue
            seen.add(event.order_id)
            order = self._orders.get(event.order_id)
            if order is None or order.status is not OrderStatus.CREATED:
                continue
            plan = plan_transition_order(
                order=order,
                new_status=OrderStatus.CANCELED,
                filled_quantity=None,
                broker_order_id=None,
                actor=actor,
            )
            assert plan.outcome == ORDER_TRANSITION_APPLY
            assert plan.order is not None and plan.event is not None
            self._orders[order.id] = plan.order
            self._append_event_unlocked(plan.event.event_type, **plan.event.as_kwargs())
            exec_event = execution_event_for_routine_transition(
                order, plan.order.status, plan.order.filled_quantity
            )
            if exec_event is not None:
                self._append_execution_event_unlocked(exec_event)

    def _dispatch_order_for_sell_intent_unlocked(
        self,
        intent: SellIntent,
        *,
        order_type: OrderType,
        limit_price: Optional[float],
    ) -> Order:
        """The plan+apply body of the APPROVED->ORDERED handoff (assumes the
        lock is already held by the caller — either the public
        ``create_order_for_sell_intent`` or ``flatten_position``, X-001, which
        needs this same dispatch inlined into its own single lock hold rather
        than calling the public method and re-acquiring the lock).

        Re-reads the LIVE position so a race that reduced it cannot oversell.
        On reject, atomically applies the X-002 self-heal (``expire_intent``/
        ``expire_event``) alongside any ``reject_event`` before raising — an
        intent is never left stranded ``approved``. On create, atomically
        inserts the order + transitions the intent to ``ordered`` + writes both
        events.
        """

        live_qty = self._position_unlocked(intent.symbol).quantity
        plan = plan_create_order_for_sell_intent(
            intent=intent,
            live_position_quantity=live_qty,
            order_type=order_type,
            limit_price=limit_price,
        )
        if plan.outcome == CREATE_ORDER_REJECT:
            with self._atomic():
                if plan.reject_event is not None:
                    self._append_event_unlocked(
                        plan.reject_event.event_type, **plan.reject_event.as_kwargs()
                    )
                if plan.expire_intent is not None:
                    self._sell_intents[intent.id] = plan.expire_intent
                    assert plan.expire_event is not None
                    self._append_event_unlocked(
                        plan.expire_event.event_type, **plan.expire_event.as_kwargs()
                    )
            assert plan.error is not None
            raise plan.error
        assert plan.order is not None  # non-REJECT dispatch sets the order
        order = plan.order
        now = utcnow()
        with self._atomic():
            self._orders[order.id] = order
            intent.status = SellIntentStatus.ORDERED
            intent.order_id = order.id
            intent.ordered_at = now
            intent.updated_at = now
            for spec in plan.events:
                self._append_event_unlocked(spec.event_type, **spec.as_kwargs())
        return order

    async def create_order_for_sell_intent(
        self,
        intent_id: str,
        *,
        order_type: OrderType,
        limit_price: Optional[float] = None,
    ) -> Order:
        async with self._lock:
            intent = self._sell_intents.get(intent_id)
            if intent is None:
                raise UnknownEntityError(f"sell intent {intent_id} not found")
            # WO-0036 R2 exclusive driver: an envelope-backed intent is
            # dispatched ONLY by the envelope executor (staged, budgeted,
            # write-time re-validated) — the legacy single-order handoff on
            # top of it would be a second exit for the same mandate.
            live_env = self._live_envelope_for_intent_unlocked(intent_id)
            if live_env is not None:
                raise SellIntentTransitionError(
                    f"sell intent {intent_id} is bound to live execution "
                    f"envelope {live_env.id}; the envelope drives its dispatch "
                    "(WO-0036 R2 link)"
                )
            # Idempotent: an intent already dispatched returns its existing order.
            if intent.status is SellIntentStatus.ORDERED:
                existing = (
                    self._orders.get(intent.order_id)
                    if intent.order_id is not None
                    else None
                )
                if existing is None:
                    raise InvalidOrderError(
                        f"sell intent {intent_id} is ORDERED but has no linked order"
                    )
                # WO-0007b: project status on this idempotent read-return too, so
                # EVERY order-returning path derives status from the event log (the
                # flip's stale-column defense is uniform).
                return self._project_order_unlocked(existing)
            order = self._dispatch_order_for_sell_intent_unlocked(
                intent, order_type=order_type, limit_price=limit_price
            )
            return order.model_copy(deep=True)

    async def open_protection_exit(
        self,
        *,
        symbol: str,
        target_quantity: int,
        floor_price: Optional[float] = None,
        observed_price: Optional[float] = None,
        average_price: Optional[float] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Order]:
        key = normalize_symbol(symbol)
        bad = whole_count_reason(target_quantity)
        if bad is not None or target_quantity <= 0:
            raise InvalidOrderError(
                f"protection exit for {key} needs a positive whole "
                f"target_quantity (got {target_quantity!r})"
            )
        async with self._lock:
            # Single-flight (atomic dedup): an exit already in flight for this
            # symbol short-circuits — nothing new is written, mirroring
            # create_sell_intent's active-check. Checked BEFORE the kill gate so an
            # exit created while ACTIVE (before the kill) still returns idempotently.
            active = self._active_sell_intent_unlocked(key)
            if active is not None:
                existing = (
                    self._orders.get(active.order_id)
                    if active.order_id is not None
                    else None
                )
                return existing.model_copy(deep=True) if existing is not None else None
            # ENG-001 / INV-060 (REV-0019-F-001): the kill switch blocks NEW
            # autonomous order intent. The whole create+approve+dispatch+audit
            # below runs under THIS single lock hold with no await after this
            # check, so a kill landing during the tick's earlier awaits is caught
            # here (nothing written) and one landing later cannot interleave — the
            # decomposed sequence's post-create HALTED window is closed.
            session = self._ensure_current_session_unlocked()
            if (
                current_trading_state(self._execution_events, session.id)
                is TradingState.HALTED
            ):
                raise ProtectionHaltedError(
                    f"autonomous protection exit for {key} refused: trading "
                    "halted (kill switch engaged)"
                )
            if session_id is None:
                session_id = session.id
            with self._atomic():
                intent = self._insert_sell_intent_unlocked(
                    symbol=key,
                    reason=SellReason.PROTECTION_FLOOR,
                    target_quantity=target_quantity,
                    floor_price=floor_price,
                    observed_price=observed_price,
                    session_id=session_id,
                )
                self._transition_sell_intent_unlocked(intent, SellIntentStatus.APPROVED)
                order = self._dispatch_order_for_sell_intent_unlocked(
                    intent, order_type=OrderType.MARKET, limit_price=None
                )
                # The trigger audit joins the SAME atomic block: a dispatch reject
                # (oversell) rolls the intent+approve back with it, so no
                # protection_triggered event ever describes a non-existent exit.
                self._append_event_unlocked(
                    "protection_triggered",
                    message=(
                        f"protection floor breached for {key}: last "
                        f"{observed_price} <= floor {floor_price}; exiting "
                        f"{target_quantity} shares"
                    ),
                    symbol=key,
                    order_id=order.id,
                    payload={
                        "average_price": average_price,
                        "floor_price": floor_price,
                        "observed_price": observed_price,
                        "quantity": target_quantity,
                    },
                    session_id=session_id,
                    correlation_id=intent.id,
                )
            return order.model_copy(deep=True)

    async def flatten_position(
        self,
        symbol: str,
        *,
        session_id: Optional[str] = None,
        actor: str = COMMAND_ACTOR_SYSTEM,
    ) -> FlattenResult:
        key = normalize_symbol(symbol)
        async with self._lock:
            # Every read this decision depends on happens under this ONE lock
            # hold, continuously through to the write below — a concurrent
            # protection tick's own create_sell_intent call cannot interleave
            # anywhere in between (X-001).
            position = self._position_unlocked(key)
            active = self._active_sell_intent_unlocked(key)
            active_order = (
                self._orders.get(active.order_id)
                if active is not None and active.order_id is not None
                else None
            )
            # WO-0036 R2 (Codex PR#8 #4): an envelope-backed exit's live child
            # is invisible on the intent (order_id=None) — read it via the
            # envelope linkage under this SAME lock hold so the planner can
            # defer to it instead of double-booking a second SELL.
            envelope_child, envelope_intent = self._live_envelope_exit_unlocked(key)
            # ADR-003 / wave 3e: read the current session's §8 FSM + whether an
            # emergency-reduce override is active for this symbol, both under this
            # same lock so the deny decision can't straddle a concurrent control
            # change or override grant.
            current_session = self._ensure_current_session_unlocked()
            trading_state = current_trading_state(
                self._execution_events, current_session.id
            )
            override_active = key in active_emergency_reduce_overrides(
                self._execution_events, current_session.id
            )
            plan = plan_flatten_position(
                position=position,
                active_intent=active,
                active_order=active_order,
                trading_state=trading_state,
                override_active=override_active,
                actor=actor,
                envelope_child=envelope_child,
                envelope_intent=envelope_intent,
            )

            if plan.outcome == FLATTEN_DENIED_HALTED:
                raise FlattenBlockedError(
                    f"manual flatten of {key} denied: trading halted "
                    "(issue an emergency reduce override to exit)"
                )
            # ADR-003 / wave 3e (review MEDIUM fix): the override authorized THIS
            # flatten call, so it is spent by it on ANY authorized outcome —
            # create, existing, OR flat. Consuming only on the create branch
            # leaked the grant when the flatten dedup'd to an existing/already-flat
            # exit, later letting an ordinary flatten slip past the Halted-deny.
            if override_active:
                with self._atomic():
                    self._write_emergency_reduce_override_unlocked(
                        key,
                        actor="engine",
                        reason="flatten_authorized",
                        resolved=True,
                    )

            if plan.outcome == _PLAN_FLATTEN_FLAT:
                # ADR-010 §4 / D-2: even with nothing to exit, a stale envelope
                # must never outlive the human's direct backstop.
                with self._atomic():
                    self._cancel_symbol_envelopes_unlocked(
                        key, actor=actor, reason="manual_flatten_preemption"
                    )
                return FlattenResult(FLATTEN_FLAT)
            if plan.outcome == _PLAN_FLATTEN_EXISTING:
                # An intent is always present except on an envelope-child
                # deferral over legacy pre-R2 data whose intent row is gone.
                assert plan.existing_intent is not None or (
                    plan.deferral_event is not None
                )
                # Provenance for a deferral to a live PROTECTION_FLOOR exit or
                # a live envelope child (INV-036): record that a human flatten
                # was received and deferred (no state mutated, one audit row),
                # in the same lock hold.
                if plan.deferral_event is not None:
                    with self._atomic():
                        self._append_event_unlocked(
                            plan.deferral_event.event_type,
                            **plan.deferral_event.as_kwargs(),
                        )
                return FlattenResult(
                    FLATTEN_EXISTING,
                    intent=(
                        plan.existing_intent.model_copy(deep=True)
                        if plan.existing_intent is not None
                        else None
                    ),
                    order=(
                        plan.existing_order.model_copy(deep=True)
                        if plan.existing_order is not None
                        else None
                    ),
                    # A deferral to a live protection exit (REV-0002 F-001) — key
                    # on the deferral event, NOT the outcome: the idempotent
                    # own-manual-flatten re-return is ALSO FLATTEN_EXISTING but has
                    # no deferral_event, so it correctly reads deferred=False.
                    deferred=plan.deferral_event is not None,
                )

            # FLATTEN_SUPERSEDE_AND_CREATE — the whole supersede (if any) +
            # create + approve + dispatch sequence is ONE atomic block: nothing
            # else can write to this symbol's sell intents/orders until this
            # entire method returns, which is what guarantees the returned
            # intent's reason is manual_flatten, never a raced-in dedup target.
            assert plan.outcome == FLATTEN_SUPERSEDE_AND_CREATE
            if session_id is None:
                session_id = self._ensure_current_session_unlocked().id
            superseded = False
            with self._atomic():
                # ADR-010 §4: envelope preemption FIRST, same atomic unit —
                # the preemption events sequence before the flatten's own
                # supersede/create writes (asserted by WO-0017 tests).
                self._cancel_symbol_envelopes_unlocked(
                    key, actor=actor, reason="manual_flatten_preemption"
                )
                if plan.supersede_order_cancel is not None:
                    # A supersede-cancel implies the stranded active_order exists
                    # and the planner produced its cancel audit event (narrows both).
                    assert (
                        active_order is not None
                        and plan.supersede_cancel_event is not None
                    )
                    # WO-0007a Stage 3: co-write the routine CANCELED
                    # ExecutionEvent (SAME shared helper + dedupe_key format as
                    # transition_order's ->CANCELED) in the SAME atomic block
                    # as the order-row + audit-event write. `active_order` is
                    # the PRE-transition order (its `.status` is still
                    # CREATED — `plan.supersede_order_cancel` is a separate
                    # deep copy already mutated to CANCELED by the planner),
                    # exactly what the helper needs.
                    exec_event = execution_event_for_routine_transition(
                        active_order,
                        OrderStatus.CANCELED,
                        active_order.filled_quantity,
                    )
                    self._orders[plan.supersede_order_cancel.id] = (
                        plan.supersede_order_cancel
                    )
                    self._append_event_unlocked(
                        plan.supersede_cancel_event.event_type,
                        **plan.supersede_cancel_event.as_kwargs(),
                    )
                    if exec_event is not None:
                        self._append_execution_event_unlocked(exec_event)
                    superseded = True
                if plan.supersede_intent_expire is not None:
                    assert plan.supersede_expire_event is not None
                    # WO-0036 R2: the envelope preemption above may have ALREADY
                    # expired this intent (terminal propagation). Re-read the
                    # live row and only apply the planner's expiry if it is
                    # still pending/approved — the event log must carry exactly
                    # ONE terminal transition per intent, never two.
                    live_row = self._sell_intents.get(plan.supersede_intent_expire.id)
                    if live_row is not None and live_row.status in (
                        SellIntentStatus.PENDING,
                        SellIntentStatus.APPROVED,
                    ):
                        self._sell_intents[plan.supersede_intent_expire.id] = (
                            plan.supersede_intent_expire
                        )
                        self._append_event_unlocked(
                            plan.supersede_expire_event.event_type,
                            **plan.supersede_expire_event.as_kwargs(),
                        )
                    superseded = True
                intent = self._insert_sell_intent_unlocked(
                    symbol=key,
                    reason=SellReason.MANUAL_FLATTEN,
                    target_quantity=plan.target_quantity,
                    session_id=session_id,
                    actor=actor,
                )
                self._transition_sell_intent_unlocked(intent, SellIntentStatus.APPROVED)
                order = self._dispatch_order_for_sell_intent_unlocked(
                    intent, order_type=OrderType.MARKET, limit_price=None
                )
            return FlattenResult(
                FLATTEN_CREATED,
                intent=intent.model_copy(deep=True),
                order=order.model_copy(deep=True),
                superseded=superseded,
            )

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
                session_id=session_id
                if session_id is not None
                else candidate.session_id,
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
                quarantined=candidate.symbol
                in quarantined_symbols(self._execution_events),
            )
            if plan.outcome == CREATE_ORDER_REJECT:
                # The kill-switch/pause block and the Phase 6 CAPI risk-limit
                # block each write an audit row before raising; the not-approved
                # and invalid-qty/price rejections don't.
                if plan.reject_event is not None:
                    self._append_event_unlocked(
                        plan.reject_event.event_type, **plan.reject_event.as_kwargs()
                    )
                assert plan.error is not None
                raise plan.error

            # CREATE — APPROVED -> ORDERED, linking the order. Wrapped in _atomic
            # (unifying what was previously a hand-rolled snapshot/restore here) so
            # the order insert + candidate transition + both audit events are
            # all-or-nothing, matching SqliteStateStore's single-transaction
            # guarantee for the "approval + order creation + audit" group (docs/02).
            assert plan.order is not None  # APPROVED create path sets it
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
            if order is not None:
                # WO-0013 (F-001): the double-submit gate reads event-log TRUTH, not
                # the co-written orders.status column. The read-flip (WO-0007b Stage D)
                # redirected get_order/list_orders; the claim gate must derive status
                # from the same projection under this lock, else a column drifted to
                # CREATED would re-claim an already-submitted order and blind-resubmit.
                # The projected order flows into BOTH the gate and the SUBMIT_PENDING
                # co-write below, so a claimable order is CREATED per the log there too.
                projected = self._project_order_unlocked(order)
                # Defense-in-depth (REV-0002 adversarial-verify): the gate now trusts
                # the projection absolutely, so pin the co-write invariant in code
                # (mirrors execution_event_for_routine_transition's asserts). A raw
                # column past CREATED that still projects CREATED means the log is
                # missing this order's lifecycle events — claiming it would blind-
                # resubmit a possibly-live order. Unreachable today (every writer co-
                # writes; init backfill heals migration); fail loud, never re-submit.
                assert not (
                    order.status is not OrderStatus.CREATED
                    and projected.status is OrderStatus.CREATED
                ), (
                    f"claim_order_for_submission: order {order_id} column status "
                    f"{order.status.value!r} projects CREATED (no lifecycle events) — "
                    "co-write invariant violated; refusing to avoid a blind re-submit"
                )
                order = projected
            own_session = (
                next((s for s in self._sessions if s.id == order.session_id), None)
                if order is not None
                else None
            )
            current_session = self._ensure_current_session_unlocked()
            # Phase 7 §5.2: the owning intent's reason drives the side/reason-aware
            # gate. Fetched under the same lock so a concurrent transition can't
            # change it between the read and the CREATED -> SUBMITTING write.
            sell_reason = None
            if order is not None and order.sell_intent_id is not None:
                intent = self._sell_intents.get(order.sell_intent_id)
                sell_reason = intent.reason if intent is not None else None
            # ADR-001 (wave 3b): hold an autonomous BUY whose symbol is quarantined
            # by a broker overfill (derived from the event log under this lock).
            quarantined = order is not None and order.symbol in quarantined_symbols(
                self._execution_events
            )
            plan = plan_claim_order_for_submission(
                order=order,
                own_session=own_session,
                current_session=current_session,
                sell_reason=sell_reason,
                quarantined=quarantined,
            )
            if plan.outcome == CLAIM_CLAIMED:
                # CLAIM_CLAIMED guarantees a claimable order + its plan artifacts
                # (narrows the Optionals mypy can't infer from the outcome).
                assert (
                    order is not None
                    and plan.order is not None
                    and plan.event is not None
                )
                # WO-0007a Stage 1: co-write a SUBMIT_PENDING ExecutionEvent in
                # the SAME atomic block as the order-row + audit-event write.
                # `occurrence` = count of PRIOR SUBMIT_PENDING events for this
                # order_id, read under the same lock this whole method already
                # holds (no concurrent claim can interleave), so repeats via
                # the claim/release cycle get gapless, uniquely-keyed events.
                occurrence = sum(
                    1
                    for e in self._execution_events
                    if e.order_id == order_id
                    and e.event_type is ExecutionEventType.SUBMIT_PENDING
                )
                exec_event = execution_event_for_routine_transition(
                    order, OrderStatus.SUBMITTING, None, occurrence=occurrence
                )
                with self._atomic():
                    self._orders[order_id] = plan.order
                    self._append_event_unlocked(
                        plan.event.event_type, **plan.event.as_kwargs()
                    )
                    if exec_event is not None:
                        self._append_execution_event_unlocked(exec_event)
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
                            local_order.candidate_id
                            if local_order is not None
                            else None
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
                out.append(self._project_order_unlocked(o))
            return out

    def _project_order_unlocked(self, order: Order) -> Order:
        """Return ``order`` with ``status`` derived from the ExecutionEvent log
        (WO-0007b read-flip): the event log is truth for order status
        (project_order_status folds the lifecycle events), and the ``orders.status``
        column is a co-written read-model kept in sync (WO-0007a co-write + init
        heal). Callers get the event-derived status, so a stale/corrupted column can
        never surface as an order's status.

        ``filled_quantity`` stays column-sourced here (co-written, monotonic-bound-
        checked by plan_transition_order). It is NOT universally the FILL-event sum
        — the store lets a caller set it directly without matching fills — so
        event-sourcing filled_quantity is a separate follow-up (design-decision.md);
        the projector computes it (proven in Stage C1) but the read-flip does not
        redirect it yet."""

        proj = project_order_status(self._execution_events, order.id, order.quantity)
        projected = order.model_copy(deep=True)
        projected.status = proj.status
        return projected

    async def get_order(self, order_id: str) -> Optional[Order]:
        async with self._lock:
            o = self._orders.get(order_id)
            return self._project_order_unlocked(o) if o else None

    async def transition_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        filled_quantity: Optional[int] = None,
        broker_order_id: Optional[str] = None,
        actor: str = COMMAND_ACTOR_SYSTEM,
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
                actor=actor,
            )
            if plan.outcome == ORDER_TRANSITION_REJECT:
                assert plan.error is not None
                raise plan.error
            if plan.outcome == ORDER_TRANSITION_NOOP:
                return order.model_copy(deep=True)
            # APPLY: plan.order + plan.event are set for this outcome (narrows the
            # Optional plan fields for the rest of the method; mypy can't infer it
            # from the outcome check).
            assert plan.order is not None and plan.event is not None
            # WO-0007a Stage 2: also co-write the routine order-status
            # ExecutionEvent (if any) in the SAME atomic block, mirroring
            # Stage 1's claim-path pattern. `order` here is still the
            # PRE-transition order (fetched above, before plan.order), which is
            # exactly what `execution_event_for_routine_transition` needs — both
            # for the TIMEOUT_QUARANTINE defense-in-depth guard and to tell a
            # first entry into PARTIALLY_FILLED apart from the same-status
            # fill-progress self-loop.
            #
            # `plan.event.event_type` is plan_transition_order's own signal for
            # which branch it took: "order_transition" (status_changed) vs
            # "order_fill_progress" (same status, filled_quantity and/or
            # broker_order_id changed) — using it here keeps this call in exact
            # lockstep with the planner's branching instead of re-deriving it.
            exec_event = None
            if plan.event.event_type == "order_transition":
                # WO-0007b: the SUBMITTING -> CREATED release is occurrence-keyed
                # like the claim, so a repeated claim/release cycle stays gapless.
                # Count prior SUBMIT_RELEASED events under the lock this method
                # already holds (no concurrent transition can interleave).
                occurrence = None
                if plan.order.status is OrderStatus.CREATED:
                    occurrence = sum(
                        1
                        for e in self._execution_events
                        if e.order_id == order_id
                        and e.event_type is ExecutionEventType.SUBMIT_RELEASED
                    )
                exec_event = execution_event_for_routine_transition(
                    order,
                    plan.order.status,
                    plan.order.filled_quantity,
                    occurrence=occurrence,
                )
            elif (
                plan.event.event_type == "order_fill_progress"
                and order.status is OrderStatus.PARTIALLY_FILLED
                and plan.order.status is OrderStatus.PARTIALLY_FILLED
                and plan.order.filled_quantity != order.filled_quantity
            ):
                exec_event = execution_event_for_routine_transition(
                    order, plan.order.status, plan.order.filled_quantity
                )
            # APPLY — swap in the fully-updated order and write its one audit row
            # (order_transition or order_fill_progress), plus the ExecutionEvent
            # (if any), atomically.
            with self._atomic():
                self._orders[order_id] = plan.order
                self._append_event_unlocked(
                    plan.event.event_type, **plan.event.as_kwargs()
                )
                if exec_event is not None:
                    self._append_execution_event_unlocked(exec_event)
                # WO-0036 R2: a venue-terminal envelope child may be its
                # mandate's LAST live obligation — complete the intent release
                # in the same atomic unit (no-op for non-envelope orders).
                self._release_intent_for_terminal_child_unlocked(plan.order)
            return plan.order.model_copy(deep=True)

    # ------------------------------------------------------------------ #
    # Timeout-quarantine (ADR-002 / wave 3c) — evented order transitions
    # ------------------------------------------------------------------ #
    def _apply_order_evented_plan_unlocked(
        self, plan: "OrderEventedTransitionPlan", order: Order
    ) -> Order:
        """Apply an :class:`OrderEventedTransitionPlan`: co-write the order-row
        flip + audit event + ExecutionEvent (durable truth) in ONE atomic block."""

        if plan.outcome == ORDER_TRANSITION_REJECT:
            assert plan.error is not None
            raise plan.error
        if plan.outcome == ORDER_TRANSITION_NOOP:
            return order.model_copy(deep=True)
        assert (
            plan.order is not None
            and plan.audit_event is not None
            and plan.execution_event is not None
        )
        with self._atomic():
            self._orders[plan.order.id] = plan.order
            self._append_event_unlocked(
                plan.audit_event.event_type, **plan.audit_event.as_kwargs()
            )
            self._append_execution_event_unlocked(plan.execution_event)
            # WO-0036 R2: same child-terminal release as transition_order —
            # the evented paths (quarantine resolution, reconcile) are the
            # other door a child takes to a venue terminal.
            self._release_intent_for_terminal_child_unlocked(plan.order)
        return plan.order.model_copy(deep=True)

    async def quarantine_timed_out_order(
        self, order_id: str, *, reason: Optional[str] = None
    ) -> Order:
        async with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise UnknownEntityError(f"order {order_id} not found")
            plan = plan_quarantine_timed_out_order(order, reason=reason)
            return self._apply_order_evented_plan_unlocked(plan, order)

    async def resolve_timeout_quarantine(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        broker_order_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Order:
        async with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise UnknownEntityError(f"order {order_id} not found")
            plan = plan_resolve_timeout_quarantine(
                order, new_status, broker_order_id=broker_order_id, reason=reason
            )
            return self._apply_order_evented_plan_unlocked(plan, order)

    async def list_timeout_quarantined_orders(self) -> list[Order]:
        async with self._lock:
            ids = timeout_quarantined_order_ids(self._execution_events)
            return [
                self._project_order_unlocked(self._orders[oid])
                for oid in sorted(ids)
                if oid in self._orders
            ]

    async def reconcile_resolve_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        reason: Optional[str] = None,
    ) -> Order:
        async with self._lock:
            order = self._orders.get(order_id)
            if order is None:
                raise UnknownEntityError(f"order {order_id} not found")
            plan = plan_reconcile_resolve_order(order, new_status, reason=reason)
            return self._apply_order_evented_plan_unlocked(plan, order)

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
        source: EventSource = EventSource.BROKER_REST,
        authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
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
            # concurrency-0 ROOT form (WO-0035): the overfill check evaluates
            # against the position EXCLUDING this fill's own event — the
            # record-first envelope bridge may have already folded THIS fill
            # (same canonical dedupe identity), and comparing the incoming
            # quantity against the post-fold position fabricated
            # fill_overfill_quarantined on every clean bridged exit. Deriving
            # the exclusion HERE (instead of a caller-supplied prior_position)
            # kills the forget-the-param bug class: with no bridged event the
            # exclusion is a no-op and this equals the live position.
            self_key = (
                f"fill:{order_id}:{source_fill_id}"
                if source_fill_id is not None
                else None
            )
            overfill_position = project_symbol_position(
                [
                    e
                    for e in self._execution_events
                    if self_key is None or e.dedupe_key != self_key
                ],
                key,
            ).quantity
            plan = plan_append_fill(
                order_id=order_id,
                order=order,
                prior_filled=prior_filled,
                current_quantity=overfill_position,
                is_duplicate=is_duplicate,
                symbol=key,
                side=side,
                quantity=quantity,
                price=price,
                source_fill_id=source_fill_id,
                filled_at=filled_at,
                session_id=session_id,
                source=source,
                authority=authority,
            )

            if plan.outcome == FILL_REJECT:
                # A single rejection event is one row — no atomic wrapper needed;
                # it must persist even though we then raise.
                self._append_event_unlocked(
                    plan.event.event_type, **plan.event.as_kwargs()
                )
                assert plan.error is not None
                raise plan.error

            if plan.outcome == FILL_DUPLICATE:
                event = self._append_event_unlocked(
                    plan.event.event_type, **plan.event.as_kwargs()
                )
                return FillAppendResult(status="duplicate", fill=None, event=event)

            # FILL_APPEND — atomically append the fill + dedup key + audit event
            # + the shadow ExecutionEvent (wave 3a), so a failed write can't leave
            # a position-changing fill with no fill_appended row, a poisoned dedup
            # set, or a fill/event-log divergence (Item 4 + shadow parity).
            assert plan.fill is not None  # FILL_APPEND builds the fill row
            fill = plan.fill
            with self._atomic():
                self._fills.append(fill)
                if fill.source_fill_id is not None:
                    self._fill_source_ids.add((fill.order_id, fill.source_fill_id))
                event = self._append_event_unlocked(
                    plan.event.event_type, **plan.event.as_kwargs()
                )
                if plan.execution_event is not None:
                    self._append_execution_event_unlocked(plan.execution_event)
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
            symbols = sorted(self._fill_event_symbols_unlocked())
            return [self._position_unlocked(s) for s in symbols]

    async def list_quarantined_symbols(self) -> set[str]:
        async with self._lock:
            return quarantined_symbols(self._execution_events)

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
    # Execution-event log (Spine v2 — Phase 2)
    # ------------------------------------------------------------------ #
    def _append_execution_event_unlocked(self, event: ExecutionEvent) -> ExecutionEvent:
        """Assign a sequence + append (dedupe-aware), assuming the lock is held
        and an ``_atomic()`` block is active. Shared by the public
        :meth:`append_execution_event` and the shadow write inside
        :meth:`append_fill` (which already holds the lock + atomic block), so the
        fill row and its shadow event commit together (wave 3a)."""

        dedupe_key = event.dedupe_key
        if dedupe_key is not None:
            existing = self._execution_event_dedupe.get(dedupe_key)
            if existing is not None:
                # INV-5: same dedupe_key is a no-op; no sequence consumed.
                return existing.model_copy(deep=True)
        next_sequence = (
            self._execution_events[-1].sequence if self._execution_events else 0
        ) + 1
        stored = event.model_copy(deep=True, update={"sequence": next_sequence})
        self._execution_events.append(stored)
        if dedupe_key is not None:
            self._execution_event_dedupe[dedupe_key] = stored
        return stored.model_copy(deep=True)

    async def append_execution_event(self, event: ExecutionEvent) -> ExecutionEvent:
        async with self._lock:
            with self._atomic():
                return self._append_execution_event_unlocked(event)

    async def get_execution_events(
        self, *, after_sequence: int = 0, limit: Optional[int] = None
    ) -> list[ExecutionEvent]:
        # A negative limit must be rejected in BOTH stores identically — a
        # Python slice out[:-1] would drop the tail while SQL LIMIT -1 means
        # unlimited (dual-store parity, see base.py).
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative")
        async with self._lock:
            # Appends assign strictly increasing sequences under the lock, so the
            # list is already in ascending sequence order — no sort needed.
            out = [
                e.model_copy(deep=True)
                for e in self._execution_events
                if e.sequence > after_sequence
            ]
            if limit is not None:
                out = out[:limit]
            return out

    async def get_max_execution_sequence(self) -> int:
        async with self._lock:
            return self._execution_events[-1].sequence if self._execution_events else 0

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

    def _apply_control_change_unlocked(
        self,
        session: SessionRecord,
        *,
        kill_switch: bool,
        buys_paused: bool,
        audit_event_type: str,
        audit_message: str,
        audit_payload: dict[str, Any],
        reason: str,
    ) -> None:
        """Apply a control change (§8 / wave 3d): co-write the derived
        ``trading_state`` + the legacy boolean(s), the legacy audit event
        (UNCHANGED, for continuity), and — only on a real state transition — the
        ``TRADING_STATE_CHANGED`` ``ExecutionEvent`` (the durable FSM truth). Called
        inside ``_atomic()``."""

        prior_control = control_trading_state(self._execution_events, session.id)
        exec_event = trading_state_change_event(
            session.id,
            prior_control=prior_control,
            kill_switch=kill_switch,
            buys_paused=buys_paused,
            reason=reason,
        )
        session.kill_switch = kill_switch
        session.buys_paused = buys_paused
        # Effective state composes the new control state with the INDEPENDENT
        # reconcile driver (wave 4f / R2) — kill still dominates a reconcile Reducing,
        # and a kill release can't lift a Reducing pending reconciliation still needs.
        session.trading_state = compose_trading_state(
            TradingState.of(kill_switch=kill_switch, buys_paused=buys_paused),
            reconcile_trading_state(self._execution_events, session.id),
        )
        session.updated_at = utcnow()
        self._append_event_unlocked(
            audit_event_type,
            message=audit_message,
            session_id=session.id,
            payload=audit_payload,
        )
        if exec_event is not None:
            self._append_execution_event_unlocked(exec_event)

    def _apply_reconcile_state_unlocked(
        self, session: SessionRecord, *, to: TradingState, reason: str
    ) -> None:
        """Apply a RECONCILE-driver TradingState change (wave 4f / R2): co-write the
        composed effective ``trading_state`` + a ``driver="reconcile"``
        ``TRADING_STATE_CHANGED`` ``ExecutionEvent`` — WITHOUT touching the kill/pause
        booleans. Called inside ``_atomic()``."""

        prior_reconcile = reconcile_trading_state(self._execution_events, session.id)
        exec_event = reconcile_trading_state_event(
            session.id,
            prior_reconcile=prior_reconcile,
            to=to,
            reason=reason,
        )
        if exec_event is None:
            # Reconcile driver already at `to` — a no-op re-assert. The loop drives
            # this EVERY steady-parity tick, so appending an audit row + rewriting the
            # column here would grow the log unbounded (and quadratically slow the
            # per-tick log folds). Skip it: the composed effective column is already
            # correct (neither driver changed), matching the repo's "a transition that
            # doesn't change status writes no new audit row" discipline (docs/02).
            return
        session.trading_state = compose_trading_state(
            control_trading_state(self._execution_events, session.id), to
        )
        session.updated_at = utcnow()
        self._append_event_unlocked(
            "trading_state_reconcile",
            message=f"reconcile-driven trading state -> {to.value} ({reason})",
            session_id=session.id,
            payload={"to": to.value, "reason": reason},
        )
        self._append_execution_event_unlocked(exec_event)

    async def set_kill_switch(
        self, engaged: bool, *, actor: str = COMMAND_ACTOR_SYSTEM
    ) -> SessionRecord:
        require_bool(engaged, field="engaged")
        async with self._lock:
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                self._apply_control_change_unlocked(
                    session,
                    kill_switch=engaged,
                    buys_paused=session.buys_paused,
                    audit_event_type="kill_switch_engaged"
                    if engaged
                    else "kill_switch_released",
                    audit_message=f"kill switch {'engaged' if engaged else 'released'}",
                    audit_payload={"kill_switch": engaged, "actor": actor},
                    reason="kill_switch",
                )
                if engaged:
                    # ADR-010 §4: the kill freezes every ACTIVE envelope in
                    # the SAME atomic unit as the control change. Release
                    # never auto-resumes (FROZEN -> ACTIVE is an explicit
                    # human action, itself refused while HALTED).
                    frozen: list[str] = []
                    for env in list(self._envelopes.values()):
                        if env.status is EnvelopeStatus.ACTIVE:
                            plan = plan_envelope_transition(
                                env,
                                EnvelopeStatus.FROZEN,
                                actor=actor,
                                reason="kill_switch",
                            )
                            assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                            self._apply_envelope_transition_unlocked(plan)
                            frozen.append(env.id)
                    # WO-0024: the kill blocks new order intent (INV-060) — a
                    # staged CREATED order IS pending order intent, so it dies
                    # in the same atomic unit as the freeze.
                    self._cancel_staged_envelope_orders_unlocked(frozen, actor=actor)
            return session.model_copy(deep=True)

    async def set_buys_paused(
        self, paused: bool, *, actor: str = COMMAND_ACTOR_SYSTEM
    ) -> SessionRecord:
        require_bool(paused, field="paused")
        async with self._lock:
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                self._apply_control_change_unlocked(
                    session,
                    kill_switch=session.kill_switch,
                    buys_paused=paused,
                    audit_event_type="buys_paused" if paused else "buys_resumed",
                    audit_message=f"buys {'paused' if paused else 'resumed'}",
                    audit_payload={"buys_paused": paused, "actor": actor},
                    reason="buys_paused",
                )
            return session.model_copy(deep=True)

    async def set_reconcile_trading_state(
        self, to: TradingState, *, reason: str
    ) -> SessionRecord:
        if to is TradingState.HALTED:
            raise ValueError("the reconcile driver never drives Halted (R3)")
        async with self._lock:
            with self._atomic():
                session = self._ensure_current_session_unlocked()
                self._apply_reconcile_state_unlocked(session, to=to, reason=reason)
            return session.model_copy(deep=True)

    async def current_trading_state(self) -> TradingState:
        async with self._lock:
            session = self._ensure_current_session_unlocked()
            return current_trading_state(self._execution_events, session.id)

    def _write_emergency_reduce_override_unlocked(
        self, symbol: str, *, actor: str, reason: str, resolved: bool
    ) -> None:
        session = self._ensure_current_session_unlocked()
        event = emergency_reduce_override_event(
            session.id,
            symbol,
            actor=actor,
            reason=reason,
            resolved=resolved,
        )
        self._append_execution_event_unlocked(event)
        self._append_event_unlocked(
            "emergency_reduce_override_resolved"
            if resolved
            else "emergency_reduce_override_granted",
            message=(
                f"emergency reduce override {'resolved' if resolved else 'granted'} "
                f"for {symbol} by {actor}"
            ),
            symbol=symbol,
            session_id=session.id,
            payload={"actor": actor, "reason": reason},
        )

    async def grant_emergency_reduce_override(
        self, symbol: str, *, actor: str, reason: str
    ) -> None:
        async with self._lock:
            with self._atomic():
                self._write_emergency_reduce_override_unlocked(
                    normalize_symbol(symbol), actor=actor, reason=reason, resolved=False
                )

    async def resolve_emergency_reduce_override(
        self, symbol: str, *, actor: str, reason: str
    ) -> None:
        async with self._lock:
            with self._atomic():
                self._write_emergency_reduce_override_unlocked(
                    normalize_symbol(symbol), actor=actor, reason=reason, resolved=True
                )

    async def list_emergency_reduce_overrides(self) -> set[str]:
        async with self._lock:
            session = self._ensure_current_session_unlocked()
            return active_emergency_reduce_overrides(self._execution_events, session.id)

    async def authorize_emergency_reduce_override(
        self, symbol: str, *, actor: str
    ) -> None:
        key = normalize_symbol(symbol)
        async with self._lock:
            session = self._ensure_current_session_unlocked()
            if current_trading_state(self._execution_events, session.id) is not (
                TradingState.HALTED
            ):
                raise EmergencyReduceBlockedError(
                    f"emergency reduce of {key} refused: session is not halted "
                    "(use an ordinary flatten)"
                )
            if self._position_unlocked(key).quantity <= 0:
                raise EmergencyReduceBlockedError(
                    f"emergency reduce of {key} refused: no open position"
                )
            quarantined_ids = timeout_quarantined_order_ids(self._execution_events)
            if any(
                oid in self._orders and self._orders[oid].symbol == key
                for oid in quarantined_ids
            ):
                raise EmergencyReduceBlockedError(
                    f"emergency reduce of {key} refused: an ambiguous "
                    "TIMEOUT_QUARANTINE order is unresolved (INV-3)"
                )
            # Defensive (review): never stack a second grant on top of an active
            # one — an override authorizes exactly one flatten and is consumed by
            # it. A still-active grant means the prior authorization hasn't been
            # spent; refuse rather than double-grant.
            if key in active_emergency_reduce_overrides(
                self._execution_events, session.id
            ):
                raise EmergencyReduceBlockedError(
                    f"emergency reduce of {key} refused: an override is already active"
                )
            with self._atomic():
                self._write_emergency_reduce_override_unlocked(
                    key, actor=actor, reason="emergency_reduce", resolved=False
                )

    async def close_session(
        self,
        session_id: Optional[str] = None,
        *,
        actor: str = COMMAND_ACTOR_SYSTEM,
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
                session = next((s for s in self._sessions if s.id == session_id), None)
                if session is None:
                    raise UnknownEntityError(f"session {session_id} not found")
                if session.status is SessionStatus.CLOSED:
                    raise SessionAlreadyClosedError(
                        f"session {session.id} is already closed"
                    )

            # The whole close (expire candidates + cancel CREATED orders +
            # snapshot positions + mark closed + audit) is one atomic group.
            with self._atomic():
                return self._close_session_unlocked(session, actor=actor)

    def _close_session_unlocked(
        self, session: SessionRecord, *, actor: str = COMMAND_ACTOR_SYSTEM
    ) -> SessionRecord:
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
        # Only CREATED **BUY** orders are canceled at close (D-013a). A CREATED
        # SELL is a protective/flatten exit that must remain submittable after the
        # session closes — protection is always-on and doesn't stop at the bell
        # (Phase 7 §5.2). Filter those out here, before the planner.
        created_orders = [
            o
            for o in self._orders.values()
            if o.session_id == session.id
            and o.status is OrderStatus.CREATED
            and OrderSide(o.side) is OrderSide.BUY
        ]
        # PENDING/APPROVED sell intents expire at close, like candidates —
        # EXCEPT one backed by a LIVE (ACTIVE/FROZEN) envelope (WO-0036 R2):
        # its mandate keeps working the exit across the boundary, so expiring
        # it would orphan the envelope (the treadmill audit's P0). Spared
        # intents are counted into the close event's payload.
        open_sell_intents = []
        spared_sell_intents = 0
        for si in self._sell_intents.values():
            if si.session_id != session.id or si.status not in (
                SellIntentStatus.PENDING,
                SellIntentStatus.APPROVED,
            ):
                continue
            if self._live_envelope_for_intent_unlocked(si.id) is not None:
                spared_sell_intents += 1
                continue
            open_sell_intents.append(si)
        nonzero_positions = []
        # Enumerate position symbols from the event log (the Rule-7 truth), not
        # the fills read-model — so a FILL event with no fill row (reconciliation
        # -inferred fill) is snapshotted too, and memory/sqlite agree.
        for sym in sorted(self._fill_event_symbols_unlocked()):
            pos = self._position_unlocked(sym)
            if pos.quantity != 0:
                nonzero_positions.append(pos)

        plan = plan_close_session(
            session=session,
            open_candidates=open_candidates,
            created_orders=created_orders,
            open_sell_intents=open_sell_intents,
            nonzero_positions=nonzero_positions,
            now=now,
            actor=actor,
            spared_sell_intents=spared_sell_intents,
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
            # WO-0007a Stage 3: co-write the routine CANCELED ExecutionEvent
            # (SAME shared helper + dedupe_key format as transition_order's
            # ->CANCELED, `f"canceled:{order_id}"`) in the SAME atomic block as
            # the order-row + audit-event write. Must be computed BEFORE
            # mutating `order.status` below, since the helper's OLD-status
            # (CREATED) reasoning — the same argument transition_order relies
            # on for its TIMEOUT_QUARANTINE defense-in-depth guard — depends on
            # seeing the pre-transition order.
            exec_event = execution_event_for_routine_transition(
                order, OrderStatus.CANCELED, order.filled_quantity
            )
            order.status = OrderStatus.CANCELED
            order.canceled_at = now
            order.updated_at = now
            self._append_event_unlocked(event.event_type, **event.as_kwargs())
            if exec_event is not None:
                self._append_execution_event_unlocked(exec_event)
        for intent, event in zip(open_sell_intents, plan.sell_intent_events):
            intent.status = SellIntentStatus.EXPIRED
            intent.expired_at = now
            intent.updated_at = now
            self._append_event_unlocked(event.event_type, **event.as_kwargs())
        self._position_snapshots.extend(plan.snapshots)
        session.status = SessionStatus.CLOSED
        session.closed_at = now
        session.updated_at = now
        self._append_event_unlocked(
            plan.close_event.event_type, **plan.close_event.as_kwargs()
        )
        return session.model_copy(deep=True)

    async def list_position_snapshots(self, session_id: str) -> list[PositionSnapshot]:
        async with self._lock:
            return [
                s.model_copy(deep=True)
                for s in self._position_snapshots
                if s.session_id == session_id
            ]
