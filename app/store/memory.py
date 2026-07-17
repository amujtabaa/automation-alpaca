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
    RECOVERY_OPEN_STATUSES,
    RECOVERY_RESOLVED,
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
    InvalidFillError,
    InvalidOrderError,
    OrderIntentBlockedError,
    ProtectionHaltedError,
    RecoveryTransitionError,
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
    envelope_created_event,
    envelope_claim_hard_rail_reason,
    envelope_action_logical_now,
    envelope_draft_reason,
    envelope_owner_binding_reason,
    envelope_owner_scope_reason,
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
    recovery_resolution_execution_event,
    recovery_creation_audit_matches,
    recovery_terminal_fact_matches,
    claim_occurrence_at,
    direct_sell_order_may_execute,
    project_envelope_obligation,
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
                # R2 migration/convergence: a pre-link database may contain an
                # APPROVED owner whose entire Envelope lineage already ended.
                # Re-project persisted facts on every open; idempotency makes a
                # healthy database a no-op.
                now = utcnow()
                for intent_id in sorted(
                    {envelope.sell_intent_id for envelope in self._envelopes.values()}
                ):
                    self._reconcile_envelope_owner_unlocked(intent_id, now=now)
                self._reconcile_envelope_symbol_conflicts_unlocked(now=now)
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
        # C4 parity fix (WO-0036 R2 consolidation, Part B step 1): one shared
        # per-call cache threaded through every _envelope_obligation_unlocked
        # invocation this method triggers, directly and via the two helpers
        # below -- mirrors the sqlite store's identical fix. Safe because it
        # never outlives this single synchronous call (no write is possible
        # between reads under one lock hold).
        cache: dict[tuple, Any] = {}
        symbol_obligation = self._envelope_obligation_unlocked(
            symbol=symbol, _cache=cache
        )
        if symbol_obligation.retains_intent:
            owner_ids = self._retained_envelope_owner_ids_unlocked(symbol, _cache=cache)
            if (
                self._envelope_symbol_owner_problem_unlocked(symbol, _cache=cache)
                is not None
                or len(owner_ids) != 1
            ):
                # A missing/malformed owner or two pre-R2 retained owners is an
                # ambiguity, not permission to pick whichever row was inserted
                # last.  Mint/flatten/claim choke points diagnose and block it.
                return None
            return self._sell_intents[owner_ids[0]]

        fallback: Optional[SellIntent] = None
        for si in reversed(list(self._sell_intents.values())):
            if si.symbol != symbol:
                continue
            raw_order = (
                self._orders.get(si.order_id) if si.order_id is not None else None
            )
            order = (
                self._project_order_unlocked(raw_order)
                if raw_order is not None
                else None
            )
            needs_review = order is not None and self._order_needs_review_unlocked(
                order.id
            )
            envelope_linked, envelope_retains = (
                self._valid_envelope_owner_state_unlocked(si)
            )
            is_active = sell_intent_is_active(
                si,
                order,
                order_needs_review=needs_review,
                envelope_linked=envelope_linked,
                envelope_obligation=envelope_retains,
            )
            if not is_active:
                continue
            if fallback is None:
                fallback = si
        return fallback

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
        now: Optional[datetime] = None,
        reason: Optional[str] = None,
        allow_envelope_restore: bool = False,
    ) -> bool:
        """Apply a sell-intent status transition in place (assumes the lock and
        an ``_atomic()`` block are already held by the caller). Returns
        ``False`` for a same-status no-op (nothing applied, no event written);
        ``True`` if it actually transitioned. Raises
        :class:`SellIntentTransitionError` for an illegal transition (nothing
        mutated).
        """

        current = intent.status
        if new_status is current:
            return False
        restoring = (
            allow_envelope_restore
            and current is SellIntentStatus.EXPIRED
            and new_status is SellIntentStatus.APPROVED
        )
        if not restoring and new_status not in _SELL_INTENT_TRANSITIONS.get(
            current, set()
        ):
            raise SellIntentTransitionError(
                f"illegal sell intent transition {current.value} -> {new_status.value}"
            )
        ts = now if now is not None else utcnow()
        intent.status = new_status
        intent.updated_at = ts
        ts_field = _SELL_INTENT_TIMESTAMP.get(new_status)
        if ts_field and (not restoring or getattr(intent, ts_field) is None):
            setattr(intent, ts_field, ts)
        if restoring:
            intent.expired_at = None
        if new_status is SellIntentStatus.ORDERED and order_id is not None:
            intent.order_id = order_id
        payload = {"from": current.value, "to": new_status.value}
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
            direct_ids = self._unresolved_direct_sell_exposure_ids_unlocked(key)
            if direct_ids:
                raise SellIntentTransitionError(
                    f"cannot create a sell intent for {key}: unresolved direct "
                    "SELL exposure exists (" + ", ".join(direct_ids) + ")"
                )
            if self._envelope_obligation_unlocked(symbol=key).retains_intent:
                raise SellIntentTransitionError(
                    f"cannot create a sell intent for {key}: an unresolved "
                    "envelope delegation has no usable owner"
                )
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
            envelope_linked = self._valid_envelope_owner_state_unlocked(intent)[0]
            if new_status is not intent.status and envelope_linked:
                raise SellIntentTransitionError(
                    f"sell intent {intent.id} is controlled by an envelope "
                    "delegation; its lifecycle may only be released by the "
                    "shared envelope-obligation projection"
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
    def _envelope_obligation_unlocked(
        self,
        *,
        sell_intent_id: Optional[str] = None,
        symbol: Optional[str] = None,
        envelope_id: Optional[str] = None,
        excluding_envelope_id: Optional[str] = None,
        valid_owner: Optional[SellIntent] = None,
        _cache: Optional[dict[tuple, Any]] = None,
    ):
        """Project one owner/symbol lineage from event-truth order state.

        C4 (WO-0036 R2 consolidation, Part B step 1 -- parity fix, mirrors the
        sqlite store's memoization): ``_active_sell_intent_unlocked`` and
        ``_reconcile_envelope_symbol_conflicts_unlocked`` each re-derive the same
        symbol's lineage 3+ times per logical call via the helpers below. ``_cache``,
        when the caller threads one shared dict through the whole call, memoizes by
        selector so each distinct (sell_intent_id, symbol, envelope_id,
        excluding_envelope_id) is computed once. Optional and per-call only --
        never persisted, never shared across a write, so it cannot see a stale
        answer.

        ``valid_owner`` deliberately opts a call OUT of caching (no current
        caller combines ``_cache`` with ``valid_owner`` -- the sole caller that
        passes ``valid_owner``, ``_valid_envelope_owner_state_unlocked``, never
        passes ``_cache``). ``valid_owner`` is a ``SellIntent`` object, not a
        stable id; keying on it would require ``id(valid_owner)``, which risks
        a false cache hit if a future caller combined the two and a garbage-
        collected object's id were reused within the same cache's lifetime.
        Simpler and equally correct to just never cache this shape -- it is
        only ever called once per intent today, so caching would not help
        even if wired up safely.
        """

        cache_key = (sell_intent_id, symbol, envelope_id, excluding_envelope_id)
        cacheable = valid_owner is None
        if _cache is not None and cacheable and cache_key in _cache:
            return _cache[cache_key]

        envelopes = [
            envelope
            for envelope in self._envelopes.values()
            if (sell_intent_id is None or envelope.sell_intent_id == sell_intent_id)
            and (symbol is None or envelope.symbol == symbol)
            and (envelope_id is None or envelope.id == envelope_id)
            and (excluding_envelope_id is None or envelope.id != excluding_envelope_id)
            and (
                valid_owner is None
                or envelope_owner_scope_reason(envelope, valid_owner) is None
            )
        ]
        envelope_ids = {envelope.id for envelope in envelopes}
        all_envelope_ids = set(self._envelopes)

        def action_in_scope(event: ExecutionEvent) -> bool:
            """Select by every immutable identity available on the link.

            A malformed action must not disappear merely because its event-side
            symbol/owner disagrees with the referenced order.  In particular,
            symbol-wide safety gates must still see an AAPL order that a corrupt
            MSFT action or parent points at; the shared projector then diagnoses
            the mismatch and fails closed.
            """

            if event.envelope_id in envelope_ids:
                return True
            if envelope_id is not None and event.envelope_id != envelope_id:
                return False
            if (
                excluding_envelope_id is not None
                and event.envelope_id == excluding_envelope_id
            ):
                return False
            order = (
                self._orders.get(event.order_id) if event.order_id is not None else None
            )
            if sell_intent_id is not None and not (
                event.correlation_id == sell_intent_id
                or (order is not None and order.sell_intent_id == sell_intent_id)
            ):
                return False
            if symbol is not None and not (
                event.symbol == symbol or (order is not None and order.symbol == symbol)
            ):
                return False
            if (
                envelope_id is None
                and sell_intent_id is None
                and symbol is None
                and event.envelope_id in all_envelope_ids
            ):
                return True
            return True

        action_events = [
            event
            for event in self._execution_events
            if event.event_type is ExecutionEventType.ENVELOPE_ACTION
            and (action_in_scope(event))
        ]
        order_ids = {
            event.order_id for event in action_events if event.order_id is not None
        }
        orders = {
            order_id: self._project_order_unlocked(order)
            for order_id, order in self._orders.items()
            if order_id in order_ids
        }
        order_events = [
            event
            for event in self._execution_events
            if event.order_id in order_ids
            and event.event_type is not ExecutionEventType.ENVELOPE_ACTION
        ]
        open_recovery_order_ids = frozenset(
            record.local_order_id
            for record in self._submit_recoveries
            if record.local_order_id in order_ids
            and record.cleanup_status == RECOVERY_UNRESOLVED
        )
        needs_review_order_ids = frozenset(
            record.local_order_id
            for record in self._submit_recoveries
            if record.local_order_id in order_ids
            and record.cleanup_status == RECOVERY_NEEDS_REVIEW
        )
        # C1 (WO-0036 R2 consolidation, Part B step 1): mirror the sqlite store's
        # bounded known_envelopes scope. project_envelope_obligation only resolves
        # each in-scope envelope's direct supersession neighbours from this map, so
        # passing the whole self._envelopes forced the pure function's
        # `dict(known_envelopes_by_id)` copy to be O(all-envelopes) on every call.
        # The in-scope envelopes plus their direct neighbours yield a byte-identical
        # projection (pinned by the scoped-vs-full parity test).
        known_envelopes_by_id = {envelope.id: envelope for envelope in envelopes}
        for envelope in envelopes:
            for neighbour_id in (envelope.superseded_by_id, envelope.supersedes_id):
                if (
                    neighbour_id is not None
                    and neighbour_id not in known_envelopes_by_id
                ):
                    neighbour_envelope = self._envelopes.get(neighbour_id)
                    if neighbour_envelope is not None:
                        known_envelopes_by_id[neighbour_id] = neighbour_envelope
        result = project_envelope_obligation(
            envelopes=envelopes,
            action_events=action_events,
            orders_by_id=orders,
            order_events=order_events,
            open_recovery_order_ids=open_recovery_order_ids,
            needs_review_order_ids=needs_review_order_ids,
            known_envelopes_by_id=known_envelopes_by_id,
        )
        if _cache is not None and cacheable:
            _cache[cache_key] = result
        return result

    def _validate_envelope_owner_unlocked(
        self, envelope: ExecutionEnvelope
    ) -> SellIntent:
        intent = self._sell_intents.get(envelope.sell_intent_id)
        reason = envelope_owner_binding_reason(envelope, intent)
        if reason is not None:
            raise InvalidOrderError(reason)
        assert intent is not None
        return intent

    def _valid_envelope_owner_state_unlocked(
        self, intent: SellIntent
    ) -> tuple[bool, bool]:
        """Linked/retained state from only scope-valid envelopes for ``intent``.

        A malformed envelope that merely reuses an intent id remains a
        symbol-local ambiguity, but it cannot restore or keep alive an unrelated
        valid owner.  This is the owner-side half of the structural link.
        """

        has_valid_envelope = any(
            envelope.sell_intent_id == intent.id
            and envelope_owner_scope_reason(envelope, intent) is None
            for envelope in self._envelopes.values()
        )
        if not has_valid_envelope:
            return False, False
        projection = self._envelope_obligation_unlocked(
            sell_intent_id=intent.id,
            valid_owner=intent,
        )
        return projection.linked, projection.retains_intent

    def _symbol_envelopes_and_intents_unlocked(
        self, symbol: str, *, _cache: Optional[dict[tuple, Any]] = None
    ) -> list[tuple[ExecutionEnvelope, Optional[SellIntent]]]:
        """C4 parity fix: the (envelope, its intent) pairs for ``symbol``, memoized.

        ``_retained_envelope_owner_ids_unlocked`` and
        ``_envelope_symbol_owner_problem_unlocked`` both scan this exact set (the
        latter calls the former too) -- one shared, per-call-cached pass over
        ``self._envelopes`` instead of re-scanning it repeatedly.
        """
        cache_key = ("symbol_envelopes_and_intents", symbol)
        if _cache is not None and cache_key in _cache:
            return _cache[cache_key]
        pairs = [
            (envelope, self._sell_intents.get(envelope.sell_intent_id))
            for envelope in self._envelopes.values()
            if envelope.symbol == symbol
        ]
        if _cache is not None:
            _cache[cache_key] = pairs
        return pairs

    def _retained_envelope_owner_ids_unlocked(
        self, symbol: str, *, _cache: Optional[dict[tuple, Any]] = None
    ) -> tuple[str, ...]:
        """Valid owners of every retained Envelope lineage for ``symbol``.

        The aggregate obligation says whether anything may still execute; this
        helper answers whether that obligation has exactly one structurally
        valid owner.  It never guesses through missing/malformed legacy data.
        """

        owner_ids: set[str] = set()
        for envelope, intent in self._symbol_envelopes_and_intents_unlocked(
            symbol, _cache=_cache
        ):
            if not self._envelope_obligation_unlocked(
                envelope_id=envelope.id, _cache=_cache
            ).retains_intent:
                continue
            if envelope_owner_scope_reason(envelope, intent) is None:
                owner_ids.add(envelope.sell_intent_id)
        return tuple(sorted(owner_ids))

    def _envelope_symbol_owner_problem_unlocked(
        self, symbol: str, *, _cache: Optional[dict[tuple, Any]] = None
    ) -> Optional[str]:
        """Why a retained symbol obligation cannot be assigned to one owner."""

        obligation = self._envelope_obligation_unlocked(symbol=symbol, _cache=_cache)
        ambiguous = self._envelope_obligation_ambiguity(obligation)
        if ambiguous:
            return "missing or malformed envelope lineage: " + ", ".join(ambiguous)
        for envelope, intent in self._symbol_envelopes_and_intents_unlocked(
            symbol, _cache=_cache
        ):
            if not self._envelope_obligation_unlocked(
                envelope_id=envelope.id, _cache=_cache
            ).retains_intent:
                continue
            reason = envelope_owner_scope_reason(envelope, intent)
            if reason is not None:
                return reason
        owner_ids = self._retained_envelope_owner_ids_unlocked(symbol, _cache=_cache)
        if len(owner_ids) != 1:
            return (
                f"retained envelope obligation has {len(owner_ids)} valid owners "
                f"({', '.join(owner_ids) or 'none'})"
            )
        return None

    @staticmethod
    def _envelope_obligation_ambiguity(obligation: Any) -> tuple[str, ...]:
        """Missing/malformed action children that must fail closed."""

        return tuple(
            dict.fromkeys(
                (
                    *obligation.missing_envelope_ids,
                    *obligation.missing_order_ids,
                    *obligation.invalid_order_ids,
                )
            )
        )

    def _reconcile_envelope_owner_unlocked(
        self, intent_id: str, *, now: Optional[datetime] = None
    ) -> None:
        """Converge a valid owner without ever rejecting broker truth.

        Missing/mismatched/ORDERED legacy owners are deliberately left alone:
        ingress validation prevents new corruption, while a terminal Envelope or
        fill/order fact must never roll back merely because old metadata is bad.
        """

        intent = self._sell_intents.get(intent_id)
        if intent is None:
            return
        linked, retains = self._valid_envelope_owner_state_unlocked(intent)
        if not linked:
            return
        if retains:
            if intent.status is SellIntentStatus.PENDING:
                self._transition_sell_intent_unlocked(
                    intent,
                    SellIntentStatus.APPROVED,
                    now=now,
                    reason="envelope_delegation_linked",
                )
            elif intent.status is SellIntentStatus.EXPIRED:
                self._transition_sell_intent_unlocked(
                    intent,
                    SellIntentStatus.APPROVED,
                    now=now,
                    reason="envelope_delegation_restored",
                    allow_envelope_restore=True,
                )
            return
        if intent.status not in (
            SellIntentStatus.PENDING,
            SellIntentStatus.APPROVED,
        ):
            return
        self._transition_sell_intent_unlocked(
            intent,
            SellIntentStatus.EXPIRED,
            now=now,
            reason="envelope_delegation_released",
        )

    def _reconcile_envelope_symbol_conflicts_unlocked(
        self, *, now: Optional[datetime] = None
    ) -> None:
        """Expire pre-R2 unlinked duplicates behind one retained delegation."""

        for symbol in sorted(
            {envelope.symbol for envelope in self._envelopes.values()}
        ):
            # C4 parity fix: one cache per symbol iteration (never reused across
            # symbols, and this symbol's own facts aren't re-read after this
            # block's writes) -- mirrors the sqlite store's identical fix.
            symbol_cache: dict[tuple, Any] = {}
            if not self._envelope_obligation_unlocked(
                symbol=symbol, _cache=symbol_cache
            ).retains_intent:
                continue
            if (
                self._envelope_symbol_owner_problem_unlocked(
                    symbol, _cache=symbol_cache
                )
                is not None
            ):
                continue
            owner_ids = {
                envelope.sell_intent_id
                for envelope, intent in self._symbol_envelopes_and_intents_unlocked(
                    symbol, _cache=symbol_cache
                )
                if self._envelope_obligation_unlocked(
                    envelope_id=envelope.id, _cache=symbol_cache
                ).retains_intent
                and envelope_owner_scope_reason(envelope, intent) is None
            }
            if len(owner_ids) != 1:
                continue
            owner_id = next(iter(owner_ids))
            for intent_id in sorted(self._sell_intents):
                intent = self._sell_intents[intent_id]
                if (
                    intent.symbol == symbol
                    and intent.id != owner_id
                    and intent.status
                    in (SellIntentStatus.PENDING, SellIntentStatus.APPROVED)
                ):
                    self._transition_sell_intent_unlocked(
                        intent,
                        SellIntentStatus.EXPIRED,
                        now=now,
                        reason="envelope_delegation_conflict",
                    )

    def _reconcile_envelope_owners_for_order_unlocked(
        self, order_id: str, *, now: Optional[datetime] = None
    ) -> None:
        intent_ids: list[str] = []
        seen: set[str] = set()
        order = self._orders.get(order_id)
        if order is not None and order.sell_intent_id is not None:
            seen.add(order.sell_intent_id)
            intent_ids.append(order.sell_intent_id)
        for event in self._execution_events:
            if (
                event.event_type is not ExecutionEventType.ENVELOPE_ACTION
                or event.order_id != order_id
            ):
                continue
            candidate_ids: list[str] = []
            if event.correlation_id is not None:
                candidate_ids.append(event.correlation_id)
            envelope = (
                self._envelopes.get(event.envelope_id)
                if event.envelope_id is not None
                else None
            )
            if envelope is not None:
                candidate_ids.append(envelope.sell_intent_id)
            for intent_id in candidate_ids:
                if intent_id in seen:
                    continue
                seen.add(intent_id)
                intent_ids.append(intent_id)
        for intent_id in intent_ids:
            self._reconcile_envelope_owner_unlocked(intent_id, now=now)

    def _other_active_envelope_for_symbol_unlocked(
        self, symbol: str, *, excluding: str
    ) -> Optional[ExecutionEnvelope]:
        """Any OTHER envelope for this SYMBOL currently ACTIVE — the per-symbol
        single-ACTIVE mandate (WO-0032 / REV-0023 P0; the SQLite twin is a
        partial unique index on ``symbol``).

        Scoped to symbol, NOT ``sell_intent_id``: at most one live selling
        mandate per symbol/position. A second intent for the same symbol (e.g.
        across a session boundary that EXPIREd the first intent while its
        envelope stayed ACTIVE) must not be able to activate a second envelope
        and double-book the exit — two ACTIVE mandates could each stage a
        full-size SELL against one position (INV-087)."""

        key = normalize_symbol(symbol)
        for env in self._envelopes.values():
            if (
                env.id != excluding
                and env.symbol == key
                and env.status is EnvelopeStatus.ACTIVE
            ):
                return env
        return None

    def _apply_envelope_transition_unlocked(
        self,
        plan: EnvelopeTransitionPlan,
        *,
        reconcile_owner: bool = True,
    ) -> ExecutionEnvelope:
        """Persist an APPLY-outcome transition plan (assumes lock + _atomic).
        The caller has already dispatched NOOP/REJECT and run the
        single-ACTIVE check where the target is ACTIVE."""

        assert plan.envelope is not None
        assert plan.execution_event is not None and plan.audit_event is not None
        stored = plan.envelope.model_copy(deep=True)
        self._envelopes[stored.id] = stored
        self._append_execution_event_unlocked(plan.execution_event)
        self._append_event_unlocked(
            plan.audit_event.event_type, **plan.audit_event.as_kwargs()
        )
        if reconcile_owner:
            self._reconcile_envelope_owner_unlocked(
                stored.sell_intent_id, now=stored.updated_at
            )
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
            transition_now = now if now is not None else utcnow()
            plan = plan_envelope_transition(
                env, new_status, actor=actor, reason=reason, now=transition_now
            )
            if plan.outcome == ENVELOPE_TRANSITION_REJECT:
                assert plan.error is not None
                raise plan.error
            owner = None
            if new_status in (EnvelopeStatus.APPROVED, EnvelopeStatus.ACTIVE):
                owner = self._validate_envelope_owner_unlocked(env)
                direct_ids = self._unresolved_direct_sell_exposure_ids_unlocked(
                    env.symbol
                )
                if direct_ids:
                    raise EnvelopeTransitionError(
                        f"envelope {env.id} cannot enter {new_status.value}: "
                        "unresolved direct SELL exposure exists ("
                        + ", ".join(direct_ids)
                        + ")"
                    )
                foreign = self._envelope_obligation_unlocked(
                    symbol=env.symbol, excluding_envelope_id=env.id
                )
                if foreign.retains_intent:
                    raise EnvelopeTransitionError(
                        f"envelope {env.id} cannot enter {new_status.value}: "
                        "another envelope lineage for the symbol retains its "
                        "delegation"
                    )
            if plan.outcome == ENVELOPE_TRANSITION_NOOP:
                if owner is not None:
                    with self._atomic():
                        self._reconcile_envelope_owner_unlocked(
                            owner.id, now=transition_now
                        )
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
                clash = self._other_active_envelope_for_symbol_unlocked(
                    env.symbol, excluding=env.id
                )
                if clash is not None:
                    raise EnvelopeTransitionError(
                        f"envelope {clash.id} is already ACTIVE for symbol "
                        f"{env.symbol} (per-symbol single-ACTIVE invariant)"
                    )
            if new_status is EnvelopeStatus.CANCELLED:
                # Codex PR#8 #5: a FROZEN envelope may still have a LIVE child at
                # the venue (kill-switch froze a formerly-ACTIVE mandate whose
                # submitted SELL is still working). A store-only CANCELLED would
                # stop monitoring it while the order keeps working — refuse; the
                # live order must be wound down first (flatten/kill precedence).
                # A quarantined (ambiguous) child counts as live.
                exact = self._envelope_obligation_unlocked(envelope_id=env.id)
                if self._envelope_obligation_ambiguity(exact) or exact.venue_orders:
                    raise EnvelopeTransitionError(
                        f"envelope {env.id} cannot be CANCELLED while a child "
                        "order is live at the venue — wind it down first "
                        "(flatten / kill switch), then cancel"
                    )
            with self._atomic():
                auto_complete = (
                    plan.envelope is not None
                    and plan.envelope.status is EnvelopeStatus.ACTIVE
                    and (plan.envelope.remaining_quantity or 0) == 0
                )
                terminal = plan.envelope is not None and not ENVELOPE_TRANSITIONS.get(
                    plan.envelope.status
                )
                stored = self._apply_envelope_transition_unlocked(
                    plan,
                    reconcile_owner=not auto_complete and not terminal,
                )
                # A freeze is never exited by a fill: an envelope fully filled
                # while FROZEN completes HERE, on resume, atomically with it.
                if auto_complete:
                    chain = plan_envelope_transition(
                        stored,
                        EnvelopeStatus.COMPLETED,
                        actor="engine",
                        reason="fully filled while frozen; completed on resume",
                        now=transition_now,
                        _fill_completion=True,
                    )
                    assert chain.outcome == ENVELOPE_TRANSITION_APPLY
                    stored = self._apply_envelope_transition_unlocked(chain)
                elif terminal:
                    # No terminal mandate leaves a never-submitted child behind.
                    # Venue-capable children remain projected and retain the owner.
                    self._cancel_staged_envelope_orders_unlocked(
                        [stored.id], actor=actor
                    )
                    self._reconcile_envelope_owner_unlocked(
                        stored.sell_intent_id, now=stored.updated_at
                    )
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
            self._validate_envelope_owner_unlocked(old)
            self._validate_envelope_owner_unlocked(normalized)
            direct_ids = self._unresolved_direct_sell_exposure_ids_unlocked(old.symbol)
            if direct_ids:
                raise EnvelopeTransitionError(
                    f"envelope {old.id} cannot be superseded: unresolved direct "
                    "SELL exposure exists (" + ", ".join(direct_ids) + ")"
                )
            exact = self._envelope_obligation_unlocked(envelope_id=old.id)
            ambiguous = self._envelope_obligation_ambiguity(exact)
            if ambiguous or len(exact.unresolved_order_ids) > 1:
                detail = ambiguous or exact.unresolved_order_ids
                raise EnvelopeTransitionError(
                    f"envelope {old.id} cannot be superseded: ambiguous linked "
                    f"child set ({', '.join(detail)})"
                )
            if exact.venue_orders:
                raise EnvelopeTransitionError(
                    f"envelope {old.id} cannot be superseded while live working order(s) "
                    + ", ".join(order.id for order in exact.venue_orders)
                    + " may be live at the venue"
                )
            foreign = self._envelope_obligation_unlocked(
                symbol=old.symbol, excluding_envelope_id=old.id
            )
            if foreign.retains_intent:
                raise EnvelopeTransitionError(
                    f"envelope {old.id} cannot be superseded: another envelope "
                    "lineage for the symbol retains its delegation"
                )
            _, working = self._envelope_action_context_unlocked(old)
            plan = plan_supersede_envelope(
                old, normalized, actor=actor, reason=reason, working_order=working
            )
            if plan.outcome == ENVELOPE_TRANSITION_REJECT:
                assert plan.error is not None
                raise plan.error
            assert plan.old_envelope is not None and plan.new_envelope is not None
            # Belt over the planner's braces: no OTHER envelope for the symbol
            # may be ACTIVE while the successor takes over (the old one is
            # leaving ACTIVE inside this same atomic unit).
            clash = self._other_active_envelope_for_symbol_unlocked(
                old.symbol, excluding=old.id
            )
            if clash is not None:
                raise EnvelopeTransitionError(
                    f"envelope {clash.id} is already ACTIVE for symbol "
                    f"{old.symbol} (per-symbol single-ACTIVE invariant)"
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
                self._reconcile_envelope_owner_unlocked(
                    plan.new_envelope.sell_intent_id,
                    now=plan.new_envelope.updated_at,
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
            if order_id is not None:
                action_links = [
                    event
                    for event in self._execution_events
                    if event.event_type is ExecutionEventType.ENVELOPE_ACTION
                    and event.order_id == order_id
                ]
                raw_order = self._orders.get(order_id)
                if action_links or raw_order is not None:
                    parent_ids = {event.envelope_id for event in action_links}
                    projection = self._envelope_obligation_unlocked(envelope_id=env.id)
                    if (
                        raw_order is None
                        or parent_ids != {env.id}
                        or order_id in projection.invalid_order_ids
                        or order_id in projection.missing_order_ids
                        or projection.missing_envelope_ids
                    ):
                        raise InvalidFillError(
                            f"fill order {order_id} is not a uniquely bounded child "
                            f"of envelope {env.id}"
                        )
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
                    assert plan.transition.envelope is not None
                    terminal = not ENVELOPE_TRANSITIONS.get(
                        plan.transition.envelope.status
                    )
                    stored = self._apply_envelope_transition_unlocked(
                        plan.transition, reconcile_owner=not terminal
                    )
                    if terminal:
                        self._cancel_staged_envelope_orders_unlocked(
                            [stored.id], actor="engine"
                        )
                        self._reconcile_envelope_owner_unlocked(
                            stored.sell_intent_id, now=stored.updated_at
                        )
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
                raise EnvelopeActionPausedError(
                    f"envelope {envelope.id} is paused: action-linked order "
                    f"{event.order_id} is missing"
                )
            order = self._project_order_unlocked(order)
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
            self._validate_envelope_owner_unlocked(env)
            direct_ids = self._unresolved_direct_sell_exposure_ids_unlocked(env.symbol)
            if direct_ids:
                raise EnvelopeActionPausedError(
                    f"envelope {env.id} is paused: unresolved direct SELL "
                    "exposure exists (" + ", ".join(direct_ids) + ")"
                )
            foreign = self._envelope_obligation_unlocked(
                symbol=env.symbol, excluding_envelope_id=env.id
            )
            if foreign.retains_intent:
                raise EnvelopeActionPausedError(
                    f"envelope {env.id} is paused: another envelope lineage "
                    "for the symbol retains its delegation"
                )
            obligation = self._envelope_obligation_unlocked(envelope_id=env.id)
            ambiguous = self._envelope_obligation_ambiguity(obligation)
            uncertain = (
                *obligation.recovery_order_ids,
                *obligation.uncertain_claim_order_ids,
            )
            if ambiguous or uncertain or len(obligation.unresolved_order_ids) > 1:
                detail = ambiguous or uncertain or obligation.unresolved_order_ids
                raise EnvelopeActionPausedError(
                    f"envelope {env.id} is paused: ambiguous linked child "
                    f"set ({', '.join(detail)})"
                )
            if session_id is not None and session_id != env.session_id:
                raise EnvelopeActionPausedError(
                    f"envelope {env.id} is paused: action session {session_id!r} "
                    f"does not match immutable envelope session {env.session_id!r}"
                )
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
            # The current session controls the global kill state only. Child
            # identity always comes from the Envelope's immutable scope.
            session_id = env.session_id
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
            candidate = stored or draft.model_copy(
                deep=True, update={"symbol": normalize_symbol(draft.symbol)}
            )
            if stored is not None:
                if stored.status not in (
                    EnvelopeStatus.PENDING,
                    EnvelopeStatus.APPROVED,
                    EnvelopeStatus.ACTIVE,
                ):
                    raise EnvelopeTransitionError(
                        f"cannot approve envelope {draft.id}: it is "
                        f"{stored.status.value}"
                    )
            else:
                bad = envelope_draft_reason(draft)
                if bad is not None:
                    raise InvalidOrderError(bad)
            owner = self._validate_envelope_owner_unlocked(candidate)
            direct_ids = self._unresolved_direct_sell_exposure_ids_unlocked(
                candidate.symbol
            )
            if direct_ids:
                raise EnvelopeTransitionError(
                    f"cannot activate envelope {candidate.id}: unresolved direct "
                    "SELL exposure exists (" + ", ".join(direct_ids) + ")"
                )
            foreign = self._envelope_obligation_unlocked(
                symbol=candidate.symbol, excluding_envelope_id=candidate.id
            )
            if foreign.retains_intent:
                raise EnvelopeTransitionError(
                    f"cannot activate envelope {candidate.id}: another envelope "
                    "lineage for the symbol retains its delegation"
                )
            if stored is not None and stored.status is EnvelopeStatus.ACTIVE:
                with self._atomic():
                    self._reconcile_envelope_owner_unlocked(owner.id)
                return stored.model_copy(deep=True)  # idempotent re-approve
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
            clash = self._other_active_envelope_for_symbol_unlocked(
                symbol, excluding=draft.id
            )
            if clash is not None:
                raise EnvelopeTransitionError(
                    f"envelope {clash.id} is already ACTIVE for symbol "
                    f"{symbol} (per-symbol single-ACTIVE invariant)"
                )
            with self._atomic():
                if stored is None:
                    stored = candidate
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
                ts = utcnow()
                current = stored
                if current.status is EnvelopeStatus.PENDING:
                    plan = plan_envelope_transition(
                        current, EnvelopeStatus.APPROVED, actor=actor, now=ts
                    )
                    assert plan.outcome == ENVELOPE_TRANSITION_APPLY
                    current = self._apply_envelope_transition_unlocked(plan)
                plan = plan_envelope_transition(
                    current, EnvelopeStatus.ACTIVE, actor=actor, now=ts
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
        writes and its events sequence BEFORE them."""

        lineage_ids = [
            envelope.id
            for envelope in self._envelopes.values()
            if envelope.symbol == symbol
        ]
        for env in list(self._envelopes.values()):
            if env.symbol != symbol:
                continue
            if not ENVELOPE_TRANSITIONS.get(env.status):
                continue  # terminal — nothing to preempt
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
        # WO-0024: a preempted mandate's obligations die with it — its staged
        # CREATED orders are cancelled in the SAME atomic unit, sequenced
        # AFTER the envelope cancellation events
        # (FINDING-W3-staged-order-outlives-preemption).
        self._cancel_staged_envelope_orders_unlocked(lineage_ids, actor=actor)

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
            raw_order = self._orders.get(event.order_id)
            if raw_order is None:
                continue
            if not self._order_has_valid_envelope_link_unlocked(raw_order):
                # Terminal cleanup is a mutation choke point: never let a
                # malformed/foreign action make this Envelope cancel another
                # lineage's local order. The invalid fact remains projected and
                # retains the owner for quarantine/reconciliation.
                continue
            order = self._project_order_unlocked(raw_order)
            if order.status is not OrderStatus.CREATED:
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
            self._reconcile_envelope_owners_for_order_unlocked(
                order.id, now=plan.order.updated_at
            )

    def _assert_symbol_envelope_preempted_unlocked(self, symbol: str) -> None:
        residual = self._envelope_obligation_unlocked(symbol=symbol)
        if residual.retains_intent:
            detail = self._envelope_obligation_ambiguity(residual)
            if not detail:
                detail = tuple(residual.unresolved_order_ids)
            raise FlattenBlockedError(
                f"manual flatten of {symbol} blocked: envelope preemption "
                "left a retained obligation"
                + (f" ({', '.join(detail)})" if detail else "")
            )

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

        own_linked = self._valid_envelope_owner_state_unlocked(intent)[0]
        symbol_obligation = self._envelope_obligation_unlocked(symbol=intent.symbol)
        if own_linked or symbol_obligation.retains_intent:
            raise SellIntentTransitionError(
                f"sell intent {intent.id} cannot use legacy single-order "
                f"dispatch while an envelope delegation for {intent.symbol} "
                "is retained"
            )
        direct_ids = self._unresolved_direct_sell_exposure_ids_unlocked(intent.symbol)
        if direct_ids:
            raise SellIntentTransitionError(
                f"sell intent {intent.id} cannot dispatch while unresolved direct "
                "SELL exposure exists (" + ", ".join(direct_ids) + ")"
            )
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
            if self._valid_envelope_owner_state_unlocked(intent)[0]:
                raise SellIntentTransitionError(
                    f"sell intent {intent.id} has an envelope delegation; "
                    "legacy single-order dispatch is structurally unavailable"
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
            direct_ids = self._unresolved_direct_sell_exposure_ids_unlocked(key)
            if direct_ids:
                raise SellIntentTransitionError(
                    f"cannot open a protection exit for {key}: unresolved direct "
                    "SELL exposure exists (" + ", ".join(direct_ids) + ")"
                )
            if self._envelope_obligation_unlocked(symbol=key).retains_intent:
                raise SellIntentTransitionError(
                    f"cannot open a protection exit for {key}: an unresolved "
                    "envelope delegation has no unambiguous usable owner"
                )
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

    def _order_has_valid_envelope_link_unlocked(self, order: Order) -> bool:
        """Whether ``order`` is a structurally valid Envelope child.

        A bare action reference is not enough: malformed/cross-symbol links must
        remain visible to the direct-order safety rail instead of hiding venue
        exposure from flatten, mint, stage, or claim.
        """

        actions = [
            event
            for event in self._execution_events
            if event.event_type is ExecutionEventType.ENVELOPE_ACTION
            and event.order_id == order.id
        ]
        envelope_ids = {event.envelope_id for event in actions}
        if not actions or None in envelope_ids or len(envelope_ids) != 1:
            return False
        envelope_id = next(iter(envelope_ids))
        assert envelope_id is not None  # narrowed by the fail-closed check above
        envelope = self._envelopes.get(envelope_id)
        if envelope is None:
            return False
        if (
            envelope_owner_scope_reason(
                envelope, self._sell_intents.get(envelope.sell_intent_id)
            )
            is not None
        ):
            return False
        projection = self._envelope_obligation_unlocked(envelope_id=envelope.id)
        return (
            order.id not in projection.invalid_order_ids
            and order.id not in projection.missing_order_ids
            and not projection.missing_envelope_ids
        )

    def _unresolved_direct_sell_orders_unlocked(self, symbol: str) -> tuple[Order, ...]:
        open_recovery_ids = {
            record.local_order_id
            for record in self._submit_recoveries
            if record.cleanup_status == RECOVERY_UNRESOLVED
        }
        needs_review_ids = {
            record.local_order_id
            for record in self._submit_recoveries
            if record.cleanup_status == RECOVERY_NEEDS_REVIEW
        }
        orders: list[Order] = []
        for raw_order in self._orders.values():
            if (
                raw_order.symbol != symbol
                or raw_order.side is not OrderSide.SELL
                or self._order_has_valid_envelope_link_unlocked(raw_order)
            ):
                continue
            order = self._project_order_unlocked(raw_order)
            order_events = [
                event
                for event in self._execution_events
                if event.order_id == order.id
                and event.event_type is not ExecutionEventType.ENVELOPE_ACTION
            ]
            if direct_sell_order_may_execute(
                order,
                order_events,
                has_open_recovery=order.id in open_recovery_ids,
                needs_review=order.id in needs_review_ids,
            ):
                orders.append(order)
        return tuple(orders)

    def _open_direct_sell_recovery_ids_unlocked(self, symbol: str) -> tuple[str, ...]:
        """Open SELL recoveries not protected by a valid Envelope lineage.

        Recovery truth can outlive or exist without its local order row.  Such
        venue exposure must remain symbol-visible rather than disappearing from
        an order-table scan.
        """

        ids: list[str] = []
        seen: set[str] = set()
        for record in self._submit_recoveries:
            if (
                record.symbol != symbol
                or record.side is not OrderSide.SELL
                or record.cleanup_status != RECOVERY_UNRESOLVED
                or record.local_order_id in seen
            ):
                continue
            order = self._orders.get(record.local_order_id)
            if order is not None:
                recovery_matches_order_scope = (
                    record.symbol == order.symbol
                    and record.side is order.side
                    and record.quantity == order.quantity
                    and record.limit_price == order.limit_price
                    and record.session_id == order.session_id
                )
                if (
                    recovery_matches_order_scope
                    and self._order_has_valid_envelope_link_unlocked(order)
                ):
                    continue
            seen.add(record.local_order_id)
            ids.append(record.local_order_id)
        return tuple(ids)

    def _unresolved_direct_sell_exposure_ids_unlocked(
        self, symbol: str
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                (
                    *(
                        order.id
                        for order in self._unresolved_direct_sell_orders_unlocked(
                            symbol
                        )
                    ),
                    *self._open_direct_sell_recovery_ids_unlocked(symbol),
                )
            )
        )

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
                self._project_order_unlocked(self._orders[active.order_id])
                if active is not None
                and active.order_id is not None
                and active.order_id in self._orders
                else None
            )
            obligation = self._envelope_obligation_unlocked(symbol=key)
            direct_orders = self._unresolved_direct_sell_orders_unlocked(key)
            direct_recovery_ids = self._open_direct_sell_recovery_ids_unlocked(key)
            unsafe_direct = (
                bool(direct_recovery_ids)
                or bool(direct_orders)
                and (
                    obligation.retains_intent
                    or position.quantity <= 0
                    or len(direct_orders) != 1
                    or active_order is None
                    or active_order.id != direct_orders[0].id
                    or direct_orders[0].status
                    in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED)
                )
            )
            if unsafe_direct:
                direct_ids = tuple(
                    dict.fromkeys(
                        (
                            *(order.id for order in direct_orders),
                            *direct_recovery_ids,
                        )
                    )
                )
                raise FlattenBlockedError(
                    f"manual flatten of {key} blocked: unresolved direct SELL "
                    "exposure cannot be safely deduplicated ("
                    + ", ".join(direct_ids)
                    + ")"
                )
            ambiguous = self._envelope_obligation_ambiguity(obligation)
            if ambiguous:
                raise FlattenBlockedError(
                    f"manual flatten of {key} blocked: envelope lineage is "
                    "missing or malformed (" + ", ".join(ambiguous) + ")"
                )
            if obligation.retains_intent:
                owner_problem = self._envelope_symbol_owner_problem_unlocked(key)
                if owner_problem is not None:
                    raise FlattenBlockedError(
                        f"manual flatten of {key} blocked: {owner_problem}"
                    )
            if len(obligation.venue_orders) > 1:
                raise FlattenBlockedError(
                    f"manual flatten of {key} blocked: multiple envelope "
                    "children may be live at the venue ("
                    + ", ".join(order.id for order in obligation.venue_orders)
                    + ")"
                )
            if obligation.venue_orders:
                envelope_order = obligation.venue_orders[0]
                if position.quantity <= 0:
                    raise FlattenBlockedError(
                        f"manual flatten of {key} blocked: position is flat but "
                        f"envelope order {envelope_order.id} may still be live"
                    )
                envelope_owner = self._sell_intents.get(
                    envelope_order.sell_intent_id or ""
                )
                if (
                    envelope_owner is None
                    or active is None
                    or active.id != envelope_owner.id
                ):
                    raise FlattenBlockedError(
                        f"manual flatten of {key} blocked: envelope order "
                        f"{envelope_order.id} has no unique owning intent"
                    )
                if active_order is not None and active_order.id != envelope_order.id:
                    raise FlattenBlockedError(
                        f"manual flatten of {key} blocked: direct order "
                        f"{active_order.id} and envelope order {envelope_order.id} "
                        "are both unresolved"
                    )
                active = envelope_owner
                active_order = envelope_order
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
                    self._assert_symbol_envelope_preempted_unlocked(key)
                return FlattenResult(FLATTEN_FLAT)
            if plan.outcome == _PLAN_FLATTEN_EXISTING:
                assert plan.existing_intent is not None
                # Provenance for a deferral to a live PROTECTION_FLOOR exit
                # (INV-036): record that a human flatten was received and deferred
                # (no state mutated, one audit row), in the same lock hold.
                if plan.deferral_event is not None:
                    with self._atomic():
                        self._append_event_unlocked(
                            plan.deferral_event.event_type,
                            **plan.deferral_event.as_kwargs(),
                        )
                return FlattenResult(
                    FLATTEN_EXISTING,
                    intent=plan.existing_intent.model_copy(deep=True),
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
                self._assert_symbol_envelope_preempted_unlocked(key)
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
                    current_intent = self._sell_intents.get(
                        plan.supersede_intent_expire.id
                    )
                    # Envelope preemption may already have released the owner
                    # through the shared projection.  Never overwrite that
                    # transition or append a duplicate audit event.
                    if current_intent is not None and current_intent.status in (
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

    def _envelope_claim_block_reason_unlocked(
        self,
        order: Order,
        *,
        accepted: bool = False,
    ) -> Optional[str]:
        if any(
            record.local_order_id == order.id
            and record.cleanup_status in RECOVERY_OPEN_STATUSES
            for record in self._submit_recoveries
        ):
            return "order has unresolved broker-submit recovery"
        actions = [
            event
            for event in self._execution_events
            if event.event_type is ExecutionEventType.ENVELOPE_ACTION
            and event.order_id == order.id
        ]
        if not actions:
            if order.side is OrderSide.SELL:
                if self._envelope_obligation_unlocked(
                    symbol=order.symbol
                ).retains_intent:
                    return (
                        "legacy/direct sell submission is blocked while an envelope "
                        "delegation for the symbol is retained"
                    )
                sibling_ids = tuple(
                    exposure_id
                    for exposure_id in self._unresolved_direct_sell_exposure_ids_unlocked(
                        order.symbol
                    )
                    if exposure_id != order.id
                )
                if sibling_ids:
                    return (
                        "unresolved direct SELL sibling exposure exists: "
                        + ", ".join(sibling_ids)
                    )
            return None
        envelope_ids = {
            event.envelope_id for event in actions if event.envelope_id is not None
        }
        if len(envelope_ids) != 1 or any(
            event.envelope_id is None for event in actions
        ):
            return "envelope action has no unique parent envelope"
        envelope_id = next(iter(envelope_ids))
        envelope = self._envelopes.get(envelope_id)
        if envelope is None:
            return f"parent envelope {envelope_id} is missing"
        if envelope.status is not EnvelopeStatus.ACTIVE:
            return (
                f"parent envelope {envelope.id} is {envelope.status.value}; "
                "submission requires active"
            )
        owner = self._sell_intents.get(envelope.sell_intent_id)
        reason = envelope_owner_binding_reason(envelope, owner)
        if reason is not None:
            return reason
        assert owner is not None
        if owner.status is not SellIntentStatus.APPROVED:
            return f"envelope owner {owner.id} is not approved"
        exact = self._envelope_obligation_unlocked(envelope_id=envelope.id)
        ambiguous = self._envelope_obligation_ambiguity(exact)
        if ambiguous:
            return "envelope lineage is missing or malformed: " + ", ".join(ambiguous)
        if exact.recovery_order_ids:
            return "envelope child has unresolved submission/recovery uncertainty"
        if order.id not in exact.unresolved_order_ids:
            return f"order {order.id} is not an unresolved child of its envelope"
        eligible_ids = (
            exact.acknowledgeable_order_ids if accepted else exact.claimable_order_ids
        )
        if accepted:
            if set(exact.uncertain_claim_order_ids) != {order.id}:
                return (
                    "accepted envelope child does not own exactly one current "
                    "submission claim"
                )
        elif exact.uncertain_claim_order_ids:
            return "envelope child has unresolved submission/recovery uncertainty"
        if order.id not in eligible_ids:
            sibling_ids = tuple(
                child_id
                for child_id in exact.unresolved_order_ids
                if child_id != order.id
            )
            return (
                "envelope child is not the projection's sole submit or exact "
                "same-lineage reprice candidate"
                + (f" ({', '.join(sibling_ids)})" if sibling_ids else "")
            )
        action = next(event for event in actions if event.envelope_id == envelope.id)
        logical_now, clock_reason = envelope_action_logical_now(
            action, wall_now=utcnow()
        )
        if clock_reason is not None:
            return clock_reason
        assert logical_now is not None
        hard_rail = envelope_claim_hard_rail_reason(
            envelope=envelope,
            order=order,
            action_event=action,
            history=self._execution_events,
            current_position=self._position_unlocked(order.symbol).quantity,
            now=logical_now,
        )
        if hard_rail is not None:
            return "envelope hard rail changed after staging: " + hard_rail
        direct_ids = self._unresolved_direct_sell_exposure_ids_unlocked(order.symbol)
        if direct_ids:
            return "unresolved direct SELL exposure exists: " + ", ".join(direct_ids)
        foreign = self._envelope_obligation_unlocked(
            symbol=envelope.symbol, excluding_envelope_id=envelope.id
        )
        if foreign.retains_intent:
            return "another envelope lineage for the symbol retains its delegation"
        return None

    def _released_terminal_envelope_child_can_cancel_unlocked(
        self, order: Order
    ) -> bool:
        """Whether a just-released CREATED child is now purely local dead work."""

        if order.status is not OrderStatus.CREATED:
            return False
        actions = [
            event
            for event in self._execution_events
            if event.event_type is ExecutionEventType.ENVELOPE_ACTION
            and event.order_id == order.id
        ]
        parent_ids = {event.envelope_id for event in actions}
        if not actions or None in parent_ids or len(parent_ids) != 1:
            return False
        parent_id = next(iter(parent_ids))
        assert parent_id is not None  # narrowed by the fail-closed check above
        parent = self._envelopes.get(parent_id)
        if parent is None or ENVELOPE_TRANSITIONS.get(parent.status):
            return False
        projection = self._envelope_obligation_unlocked(envelope_id=parent.id)
        if self._envelope_obligation_ambiguity(projection):
            return False
        return (
            order.id in projection.unresolved_order_ids
            and order.id not in projection.recovery_order_ids
            and order.id not in projection.uncertain_claim_order_ids
            and all(venue.id != order.id for venue in projection.venue_orders)
        )

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
                envelope_block = self._envelope_claim_block_reason_unlocked(order)
                if envelope_block is not None:
                    with self._atomic():
                        self._append_event_unlocked(
                            "envelope_submission_claim_blocked",
                            message=(
                                f"envelope child {order.id} submission blocked: "
                                f"{envelope_block}"
                            ),
                            symbol=order.symbol,
                            order_id=order.id,
                            payload={"reason": envelope_block},
                            session_id=order.session_id,
                            correlation_id=order.sell_intent_id,
                        )
                    return SubmissionClaim(CLAIM_BLOCKED, reason=envelope_block)
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
            claim_occurrence = claim_occurrence_at(
                self._execution_events,
                order_id=local_order_id,
                at=record.created_at,
            )
            payload: dict[str, Any] = dict(extra_payload or {})
            payload.update(
                {
                    "broker_order_id": broker_order_id,
                    "recovery_id": record.id,
                    "failure_reason": failure_reason,
                    "cleanup_status": cleanup_status,
                }
            )
            payload.pop("claim_occurrence", None)
            if claim_occurrence is not None:
                payload["claim_occurrence"] = claim_occurrence
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
                if record.cleanup_status == RECOVERY_RESOLVED:
                    stored_resolution = self._append_execution_event_unlocked(
                        recovery_resolution_execution_event(
                            record,
                            now=record.created_at,
                            claim_occurrence=claim_occurrence,
                        )
                    )
                    if not recovery_terminal_fact_matches(
                        record,
                        stored_resolution,
                        claim_occurrence=claim_occurrence,
                    ):
                        raise RecoveryTransitionError(
                            "recovery resolution event identity conflicts with "
                            f"existing dedupe fact for {record.id}"
                        )
                self._reconcile_envelope_owners_for_order_unlocked(
                    local_order_id, now=record.created_at
                )
            return record.model_copy(deep=True)

    def _recovery_claim_occurrence_unlocked(
        self, record: SubmitRecoveryRecord
    ) -> Optional[int]:
        # Creation and audit append are atomic.  Read the first mention of this
        # recovery id and accept it only when its immutable scope matches; a
        # later operator/audit message cannot retarget the captured occurrence.
        for event in self._events:
            if event.payload.get("recovery_id") != record.id:
                continue
            if recovery_creation_audit_matches(record, event):
                raw = event.payload.get("claim_occurrence")
                if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
                    return raw
            break
        return claim_occurrence_at(
            self._execution_events,
            order_id=record.local_order_id,
            at=record.created_at,
        )

    def _has_recovery_terminal_fact_unlocked(
        self,
        record: SubmitRecoveryRecord,
        *,
        claim_occurrence: Optional[int],
    ) -> bool:
        return any(
            recovery_terminal_fact_matches(
                record,
                event,
                claim_occurrence=claim_occurrence,
            )
            for event in self._execution_events
        )

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
            claim_occurrence = self._recovery_claim_occurrence_unlocked(record)
            # Replace, never mutate in place (keeps _atomic's shallow snapshot valid).
            updated = record.model_copy(deep=True)
            if bump_attempt:
                updated.retry_count += 1
                updated.last_attempt_at = utcnow()
            if cleanup_status is not None:
                updated.cleanup_status = cleanup_status
            resolution_now = (
                utcnow()
                if terminal_event is not None
                and updated.cleanup_status == RECOVERY_RESOLVED
                else None
            )
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
                    if (
                        updated.cleanup_status == RECOVERY_RESOLVED
                        and not self._has_recovery_terminal_fact_unlocked(
                            updated,
                            claim_occurrence=claim_occurrence,
                        )
                    ):
                        stored_resolution = self._append_execution_event_unlocked(
                            recovery_resolution_execution_event(
                                updated,
                                now=resolution_now,
                                claim_occurrence=claim_occurrence,
                            )
                        )
                        if not recovery_terminal_fact_matches(
                            updated,
                            stored_resolution,
                            claim_occurrence=claim_occurrence,
                        ):
                            raise RecoveryTransitionError(
                                "recovery resolution event identity conflicts with "
                                f"existing dedupe fact for {updated.id}"
                            )
                self._reconcile_envelope_owners_for_order_unlocked(
                    updated.local_order_id, now=resolution_now or utcnow()
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
            raw_order = self._orders.get(order_id)
            if raw_order is None:
                raise UnknownEntityError(f"order {order_id} not found")
            order = self._project_order_unlocked(raw_order)
            if (
                order.status is OrderStatus.SUBMITTING
                and new_status is OrderStatus.SUBMITTED
            ):
                envelope_block = self._envelope_claim_block_reason_unlocked(
                    order, accepted=True
                )
                if envelope_block is not None:
                    raise InvalidOrderError(
                        f"accepted envelope order {order.id} no longer satisfies "
                        f"its venue authorization: {envelope_block}"
                    )
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
                with self._atomic():
                    self._reconcile_envelope_owners_for_order_unlocked(
                        order_id, now=utcnow()
                    )
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
                final_order = plan.order
                if self._released_terminal_envelope_child_can_cancel_unlocked(
                    final_order
                ):
                    cancel_plan = plan_transition_order(
                        order=final_order,
                        new_status=OrderStatus.CANCELED,
                        filled_quantity=None,
                        broker_order_id=None,
                        actor=actor,
                    )
                    assert (
                        cancel_plan.outcome == ORDER_TRANSITION_APPLY
                        and cancel_plan.order is not None
                        and cancel_plan.event is not None
                    )
                    cancel_event = execution_event_for_routine_transition(
                        final_order,
                        OrderStatus.CANCELED,
                        cancel_plan.order.filled_quantity,
                    )
                    self._orders[order_id] = cancel_plan.order
                    self._append_event_unlocked(
                        cancel_plan.event.event_type,
                        **cancel_plan.event.as_kwargs(),
                    )
                    if cancel_event is not None:
                        self._append_execution_event_unlocked(cancel_event)
                    final_order = cancel_plan.order
                self._reconcile_envelope_owners_for_order_unlocked(
                    order_id, now=final_order.updated_at
                )
            return final_order.model_copy(deep=True)

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
            with self._atomic():
                self._reconcile_envelope_owners_for_order_unlocked(
                    order.id, now=utcnow()
                )
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
            self._reconcile_envelope_owners_for_order_unlocked(
                plan.order.id, now=plan.order.updated_at
            )
        return plan.order.model_copy(deep=True)

    async def quarantine_timed_out_order(
        self, order_id: str, *, reason: Optional[str] = None
    ) -> Order:
        async with self._lock:
            raw_order = self._orders.get(order_id)
            if raw_order is None:
                raise UnknownEntityError(f"order {order_id} not found")
            order = self._project_order_unlocked(raw_order)
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
            raw_order = self._orders.get(order_id)
            if raw_order is None:
                raise UnknownEntityError(f"order {order_id} not found")
            order = self._project_order_unlocked(raw_order)
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
            raw_order = self._orders.get(order_id)
            if raw_order is None:
                raise UnknownEntityError(f"order {order_id} not found")
            order = self._project_order_unlocked(raw_order)
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
                stored = self._append_execution_event_unlocked(event)
                if stored.order_id is not None:
                    self._reconcile_envelope_owners_for_order_unlocked(
                        stored.order_id, now=stored.ts_event or stored.ts_init
                    )
                # A malformed ENVELOPE_ACTION may have lost its child id.  Its
                # parent/correlation identities still change the shared owner
                # projection and must converge immediately, not only on restart.
                event_owner_ids: set[str] = set()
                if stored.correlation_id is not None:
                    event_owner_ids.add(stored.correlation_id)
                parent = (
                    self._envelopes.get(stored.envelope_id)
                    if stored.envelope_id is not None
                    else None
                )
                if parent is not None:
                    event_owner_ids.add(parent.sell_intent_id)
                for intent_id in sorted(event_owner_ids):
                    self._reconcile_envelope_owner_unlocked(
                        intent_id, now=stored.ts_event or stored.ts_init
                    )
                return stored

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
        # PENDING/APPROVED sell intents expire at close, like candidates.
        open_sell_intents = [
            si
            for si in self._sell_intents.values()
            if si.session_id == session.id
            and si.status in (SellIntentStatus.PENDING, SellIntentStatus.APPROVED)
            and not self._valid_envelope_owner_state_unlocked(si)[1]
        ]
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
