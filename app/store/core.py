"""Shared store *orchestration* — the domain-core layer.

``app/policy.py`` already extracts the pure input *predicates* both
stores share; ``app/transitions.py`` the state-machine tables;
``app/position.py`` the fold. This module extends that same "pure decision in
one place, storage wiring in each store" pattern up one level, to the multi-step
*pipelines* that were otherwise duplicated near-verbatim between
``InMemoryStateStore`` and ``SqliteStateStore``.

A **planner** here is a pure function: it takes state the store has already
fetched (an order, a prior-filled total, a position quantity, a dedup flag) and
returns a small immutable *plan* describing what to write and what to raise —
without touching any store. Each store then:

1. fetches the inputs its own way (dict lookup vs. ``SELECT``),
2. calls the planner,
3. applies the plan with its own primitives (``_atomic`` + dict mutation vs.
   ``_tx`` + SQL), inside its own atomicity boundary.

The two atomicity mechanisms, the dedup mechanism (an in-memory ``set`` vs. a
partial unique index), and the row⇄model mapping stay storage-specific — only
the *decision* is shared. The 76 ``any_store`` parity tests prove the two stores
still behave identically after each method is migrated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Sequence

from app.models import (
    Candidate,
    CandidateStatus,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    EventType,
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
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_STATUSES,
    RECOVERY_TRANSITIONS,
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionRecord,
    TradingState,
    utcnow,
)
from app.position import would_go_negative
from app.sellside.policy import validate_action as _sellside_validate_action
from app.sellside.types import ActionKind as _SellsideActionKind
from app.sellside.types import PlannedAction
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    CLAIM_SKIPPED,
    COMMAND_ACTOR_SYSTEM,
    CandidateTransitionError,
    EnvelopeTransitionError,
    InvalidControlValueError,
    InvalidFillError,
    InvalidOrderError,
    InvalidStatusError,
    OrderIntentBlockedError,
    OrderTransitionError,
    RecoveryTransitionError,
    RiskLimitBlockedError,
    RiskLimits,
    SellIntentTransitionError,
    UnknownEntityError,
)
from app.transitions import (
    ENVELOPE_TIMESTAMP,
    ENVELOPE_TRANSITIONS,
    ORDER_TIMESTAMP,
    ORDER_TRANSITIONS,
)
from app.policy import (
    fill_order_match_reason,
    fill_value_reason,
    filled_quantity_reason,
    kill_switch_block_reason,
    whole_count_reason,
    limit_price_reason,
    order_intent_block_reason,
    order_session_resolution_reason,
    risk_limit_reason,
    session_submission_block_reason,
)


@dataclass(frozen=True)
class EventSpec:
    """A pure description of an audit event, decoupled from how it is written.

    Maps onto both stores' event writers — ``InMemoryStateStore.
    _append_event_unlocked`` and ``SqliteStateStore._insert_event`` share the
    identical keyword signature — via :meth:`as_kwargs` (everything except the
    positional ``event_type``).
    """

    event_type: str
    message: str = ""
    symbol: Optional[str] = None
    candidate_id: Optional[str] = None
    order_id: Optional[str] = None
    fill_id: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    # Lifecycle correlation key (D-020). Buy events leave this None and the store
    # writer defaults it to candidate_id; sell-side events (Phase 7, candidate_id
    # is None) set it explicitly to the owning sell_intent_id so a whole protective
    # exit is reconstructable via GET /api/events?correlation_id=<sell_intent_id>.
    correlation_id: Optional[str] = None

    def as_kwargs(self) -> dict[str, Any]:
        """Keyword args for a store's event writer (``event_type`` stays positional)."""
        return {
            "message": self.message,
            "symbol": self.symbol,
            "candidate_id": self.candidate_id,
            "order_id": self.order_id,
            "fill_id": self.fill_id,
            "payload": self.payload,
            "session_id": self.session_id,
            "correlation_id": self.correlation_id,
        }


# ---- append_fill ---------------------------------------------------------- #

# FillPlan.outcome values. The store dispatches on these:
FILL_REJECT = "reject"  # write `event`; raise `error`
FILL_DUPLICATE = (
    "duplicate"  # write `event`; return a FillAppendResult("duplicate", None, event)
)
FILL_APPEND = (
    "append"  # atomically write `fill` (+dedup) and `event`; return "appended"
)


@dataclass(frozen=True)
class FillPlan:
    """Pure outcome of an :meth:`StateStore.append_fill` decision.

    ``outcome`` is one of :data:`FILL_REJECT` / :data:`FILL_DUPLICATE` /
    :data:`FILL_APPEND`. ``event`` is always the audit event to write. ``error``
    is the exception to raise (reject only). ``fill`` is the constructed row to
    append (append only).
    """

    outcome: str
    event: EventSpec
    error: Optional[Exception] = None
    fill: Optional[Fill] = None
    # Spine v2: the broker-authoritative FILL ExecutionEvent appended to the event
    # log *atomically with* the fill row (append path only). Post the wave-3a
    # event-truth flip (WO-0001: the fill flow is `event_truth`), position derives
    # from folding these FILL events (app/events/projectors.py); the fill table
    # persists as a parity-checked read model, kept in lockstep by the permanent
    # dual-store parity verifier. See pkl/process/migration-history.md.
    execution_event: Optional[ExecutionEvent] = None


def execution_event_for_fill(
    fill: Fill,
    *,
    source: EventSource = EventSource.BROKER_REST,
    authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
) -> ExecutionEvent:
    """The ``FILL`` ExecutionEvent that mirrors a fill row.

    Single-sourced so the wave-3a shadow write (``plan_append_fill``) and the
    event-truth backfill (``StateStore`` init) build the SAME event for the same
    fill — a deterministic, replay-stable record. A normally-observed fill is a
    broker-reported fact (submitted orders fill and are observed via polling), so
    ``source``/``authority`` default to ``BROKER_REST``/``BROKER_AUTHORITATIVE``.
    A **reconciliation-inferred** fill (Phase 4) overrides them to
    ``RECONCILIATION``/``SYNTHETIC`` — provenance only; the ``dedupe_key`` stays the
    venue-execution identity, so a synthetic fill and the eventual real observation
    of the same execution dedup to one (INV-5), never a double-count. ``ts_event``
    is the fill time so the projected ``Position.updated_at`` matches the fold.

    **dedupe_key** must uniquely and deterministically identify the fill so the
    backfill can tell whether a fill already has an event (idempotent, additive
    reconcile — never a positional guess). For a fill with a venue
    ``source_fill_id`` (the production case — Alpaca fills always carry one), the
    key is ``fill:{order_id}:{source_fill_id}``, mirroring the fill table's
    per-(order_id, source_fill_id) dedup exactly (two orders may legitimately
    share a venue fill id — F1 — so the order id is part of the key). A fill with
    NO ``source_fill_id`` (tests / hypothetical) has no venue identity, so we key
    on its unique row id ``fill:{order_id}:@{fill.id}``: still unique per fill (so
    it never dedups against a different fill, matching the fill table's
    "null-source is never deduped") yet matchable, so backfill neither skips nor
    double-emits it. (The row-id key is store-local for null-source fills; this
    does not affect projected position, only the dedupe identity.)
    """

    if fill.source_fill_id is not None:
        dedupe_key = f"fill:{fill.order_id}:{fill.source_fill_id}"
    else:
        dedupe_key = f"fill:{fill.order_id}:@{fill.id}"
    return ExecutionEvent(
        event_type=ExecutionEventType.FILL,
        source=source,
        authority=authority,
        dedupe_key=dedupe_key,
        ts_event=fill.filled_at,
        symbol=fill.symbol,
        side=fill.side,
        quantity=fill.quantity,
        price=fill.price,
        order_id=fill.order_id,
        session_id=fill.session_id,
    )


def plan_append_fill(
    *,
    order_id: str,
    order: Optional[Order],
    prior_filled: int,
    current_quantity: int,
    is_duplicate: bool,
    symbol: str,
    side: OrderSide,
    quantity: int,
    price: float,
    source_fill_id: Optional[str],
    filled_at: Optional[Any],
    session_id: Optional[str],
    source: EventSource = EventSource.BROKER_REST,
    authority: EventAuthority = EventAuthority.BROKER_AUTHORITATIVE,
) -> FillPlan:
    """Decide the outcome of appending one fill — the shared logic that was
    duplicated between the two stores.

    ``symbol`` is already normalized and ``side`` already coerced by the caller.
    ``order`` is ``None`` when the referenced order does not exist.
    ``current_quantity`` is the symbol's derived position quantity.
    ``is_duplicate`` is whether ``(order_id, source_fill_id)`` was already
    recorded. The checks run in the same order the stores used, so a duplicate
    still short-circuits before the cumulative/overfill check (never mistaken
    for an overfill).

    ``source``/``authority`` set the FILL ExecutionEvent provenance — the default
    is a normally-observed broker fill; a reconciliation-inferred fill (Phase 4)
    passes ``RECONCILIATION``/``SYNTHETIC``. Provenance only: dedup/position are
    unchanged, so a synthetic fill still dedups against the real observation of the
    same execution (INV-5).
    """

    # 1) Intrinsic value validation: a non-finite/non-positive quantity or price
    #    would corrupt derived-position truth. Reject before anything is touched.
    value_reason = fill_value_reason(quantity, price)
    if value_reason is not None:
        return FillPlan(
            FILL_REJECT,
            EventSpec(
                "fill_rejected_invalid",
                message=f"fill for {symbol} rejected: {value_reason}",
                symbol=symbol,
                # This value check runs before the order-existence check, so the
                # order may be absent here; correlate when it is present so a
                # malformed-fill rejection still shows up in the candidate's
                # lifecycle (D-020), matching the other fill events below.
                candidate_id=order.candidate_id if order is not None else None,
                order_id=order_id,
                payload={"reason": value_reason, "quantity": quantity, "price": price},
                session_id=session_id,
            ),
            error=InvalidFillError(f"invalid fill for {symbol}: {value_reason}"),
        )

    # 2) The referenced order must exist.
    if order is None:
        return FillPlan(
            FILL_REJECT,
            EventSpec(
                "fill_rejected_invalid",
                message=f"fill rejected: unknown order {order_id}",
                symbol=symbol,
                order_id=order_id,
                payload={"reason": "unknown_order"},
                session_id=session_id,
            ),
            error=UnknownEntityError(f"order {order_id} not found"),
        )

    # 3) Duplicate protection (makes append idempotent). A replay short-circuits
    #    here before the cumulative check, so it is never mistaken for an overfill.
    if is_duplicate:
        return FillPlan(
            FILL_DUPLICATE,
            EventSpec(
                "fill_duplicate_ignored",
                message=f"duplicate fill {source_fill_id} for {symbol} ignored",
                symbol=symbol,
                candidate_id=order.candidate_id,
                order_id=order_id,
                payload={"source_fill_id": source_fill_id},
                session_id=session_id,
            ),
        )

    # 4) Symbol/side match + cumulative-quantity vs the order.
    match_reason = fill_order_match_reason(order, symbol, side, quantity, prior_filled)
    if match_reason is not None:
        return FillPlan(
            FILL_REJECT,
            EventSpec(
                "fill_rejected_invalid",
                message=f"fill for {symbol} rejected: {match_reason}",
                symbol=symbol,
                candidate_id=order.candidate_id,
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
            ),
            error=InvalidFillError(
                f"fill for {symbol} inconsistent with order {order_id}: {match_reason}"
            ),
        )

    # 5) + 6) Append. A sell that crosses a long-only position through flat is a
    #    broker-authoritative OVERFILL (ADR-001, wave 3b): intrinsic validity was
    #    already checked (step 1), so this is broker REALITY, not malformed local
    #    input. Rather than reject-and-drop it (the pre-wave-3b behavior), RECORD
    #    the fill + its FILL event and QUARANTINE the symbol. Position now derives
    #    from the event log, which projects the recorded short (apply_fill
    #    allow_short); `create_order_for_candidate` blocks autonomous BUY intent
    #    for a quarantined symbol, and the operator reconciles + manually reviews.
    #    The store writes fill row + audit event + FILL event atomically.
    is_overfill = would_go_negative(current_quantity, side, quantity)
    fill = Fill(
        order_id=order_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        source_fill_id=source_fill_id,
        session_id=session_id,
        filled_at=filled_at or utcnow(),
    )
    if is_overfill:
        event = EventSpec(
            "fill_overfill_quarantined",
            message=(
                f"broker overfill: sell of {quantity} {symbol} exceeds current "
                f"quantity {current_quantity} — recorded and quarantined (ADR-001)"
            ),
            symbol=symbol,
            candidate_id=order.candidate_id,
            order_id=order_id,
            fill_id=fill.id,
            payload={
                "side": side.value,
                "quantity": quantity,
                "price": price,
                "attempted_sell": quantity,
                "current_quantity": current_quantity,
                "quarantined": True,
            },
            session_id=session_id,
        )
    else:
        event = EventSpec(
            "fill_appended",
            message=f"fill {fill.quantity} {symbol} @ {fill.price}",
            symbol=symbol,
            candidate_id=order.candidate_id,
            order_id=order_id,
            fill_id=fill.id,
            payload={"side": side.value, "quantity": quantity, "price": price},
            session_id=session_id,
        )
    return FillPlan(
        FILL_APPEND,
        event,
        fill=fill,
        execution_event=execution_event_for_fill(
            fill, source=source, authority=authority
        ),
    )


# ---- TradingState control (§8 / wave 3d) ---------------------------------- #


def trading_state_change_event(
    session_id: str,
    *,
    prior_control: TradingState,
    kill_switch: bool,
    buys_paused: bool,
    reason: str,
) -> Optional[ExecutionEvent]:
    """The ``driver="control"`` ``TRADING_STATE_CHANGED`` ``ExecutionEvent`` for a
    kill/pause control change, or ``None`` when the CONTROL-driver state is unchanged
    (a redundant re-engage) — §8 / wave 3d.

    ``prior_control`` is the previous *control-driver* state (``control_trading_state``
    over the log), NOT the effective composed state — a control event records the
    control driver's own ``to`` and the projector composes it with the independent
    reconcile driver (wave 4f / R2). The durable truth of the control fact: the ``to``
    is what ``control_trading_state`` folds (latest-wins). The payload also stamps the
    resulting ``(kill_switch, buys_paused)`` tuple as context, but the two booleans
    remain co-written ``sessions`` columns (legacy read-models), NOT purely
    event-reconstructable: no event fires when a boolean toggle leaves the control
    state unchanged (e.g. pause toggled while already ``HALTED``), so the log alone
    cannot always rebuild them — runtime correctness (incl. independent-release) comes
    from the durable columns. A LOCAL/ENGINE control decision, not a broker fact."""

    new_state = TradingState.of(kill_switch=kill_switch, buys_paused=buys_paused)
    if new_state is prior_control:
        return None
    return ExecutionEvent(
        event_type=ExecutionEventType.TRADING_STATE_CHANGED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=utcnow(),
        session_id=session_id,
        payload={
            "driver": "control",
            "from": prior_control.value,
            "to": new_state.value,
            "kill_switch": kill_switch,
            "buys_paused": buys_paused,
            "reason": reason,
        },
    )


def reconcile_trading_state_event(
    session_id: str,
    *,
    prior_reconcile: TradingState,
    to: TradingState,
    reason: str,
) -> Optional[ExecutionEvent]:
    """The ``driver="reconcile"`` ``TRADING_STATE_CHANGED`` ``ExecutionEvent`` (wave
    4f / R2), or ``None`` when the reconcile-driver state is unchanged.

    A SECOND, independent driver of the §8 FSM: startup mass-reconcile, stream
    reconnect, and parity signals drive ``trading_state`` to ``Reducing`` (pending
    reconciliation — the §8 default under degradation) or ``Active`` (parity restored)
    WITHOUT touching the kill/pause booleans (the wave-3d control driver). The
    projector composes this with the control driver via ``compose_trading_state``
    (``Halted > Reducing > Active``), so kill still dominates a reconcile-driven
    ``Reducing`` (R3: reconcile never auto-Halts — a held position stays exitable) and
    a kill *release* can't lift a ``Reducing`` that pending reconciliation still
    requires. ``to`` must be ``Reducing`` or ``Active`` (a reconcile signal never
    drives ``Halted``)."""

    if to is TradingState.HALTED:
        raise ValueError("the reconcile driver never drives Halted (R3)")
    if to is prior_reconcile:
        return None
    return ExecutionEvent(
        event_type=ExecutionEventType.TRADING_STATE_CHANGED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=utcnow(),
        session_id=session_id,
        payload={
            "driver": "reconcile",
            "from": prior_reconcile.value,
            "to": to.value,
            "reason": reason,
        },
    )


def emergency_reduce_override_event(
    session_id: str,
    symbol: str,
    *,
    actor: str,
    reason: str,
    resolved: bool = False,
) -> ExecutionEvent:
    """The ``EMERGENCY_REDUCE_OVERRIDE`` (grant) or
    ``EMERGENCY_REDUCE_OVERRIDE_RESOLVED`` (consume) ``ExecutionEvent`` — the
    durable truth of an audited operator override that scopes ONE reduce-only exit
    while the session is ``Halted`` (ADR-003 / wave 3e).

    A LOCAL/ENGINE decision (an operator command, not a broker fact), scoped to
    ``{session_id, symbol}`` and carrying the ``actor`` + ``reason`` for audit. The
    global ``TradingState`` stays ``Halted`` throughout; the grant is what the
    claim gate consults (via ``active_emergency_reduce_overrides``) to let the one
    exit through, and ``resolved=True`` ends the scoped grant on resolution so a
    later flatten under ``Halted`` is denied again. Not deduped — each grant/resolve
    is a distinct control action; the projector folds latest-wins per symbol."""

    return ExecutionEvent(
        event_type=(
            ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE_RESOLVED
            if resolved
            else ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE
        ),
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=utcnow(),
        session_id=session_id,
        symbol=symbol,
        payload={"actor": actor, "reason": reason, "resolved": resolved},
    )


# ---- create_order_for_candidate ------------------------------------------- #

# CreateOrderPlan.outcome values:
CREATE_ORDER_REJECT = "reject"  # write `reject_event` (block case only); raise `error`
CREATE_ORDER_CREATE = (
    "create"  # write `order` + candidate ORDERED transition + `events`
)


@dataclass(frozen=True)
class CreateOrderPlan:
    """Pure outcome of the APPROVED→ORDERED handoff *after* the store has handled
    the candidate-missing and ORDERED-idempotent cases (both need store fetches).

    ``reject``: raise ``error``; write ``reject_event`` first *only* when it is
    set (the kill-switch/pause block and the Phase 6 CAPI risk-limit block each
    write an audit row; the not-approved and invalid-qty/price rejections write
    nothing, matching the original stores).
    ``create``: append ``order``, transition the candidate to ORDERED linking it,
    and write ``events`` (``order_created`` then ``candidate_transition``) — all
    atomically.

    ``expire_intent``/``expire_event`` (X-002, sell-intent path only): on a
    rejection *after* the intent was genuinely ``approved`` (oversell, a
    vanished position, bad limit/market price coherence — never the "not
    approved" precondition reject, which has no ``approved`` state to heal
    from), the intent is atomically self-healed ``approved → expired`` alongside
    the reject event, so it is never left stranded ``approved`` poisoning the
    single-flight dedup forever (the ADR's "Self-heal (blocker)" clause). The
    store applies both writes in the SAME atomic block as the reject, before
    raising ``error``.
    """

    outcome: str
    error: Optional[Exception] = None
    reject_event: Optional[EventSpec] = None
    order: Optional[Order] = None
    events: tuple[EventSpec, ...] = ()
    expire_intent: Optional[SellIntent] = None
    expire_event: Optional[EventSpec] = None


def plan_create_order_for_candidate(
    *,
    candidate: Candidate,
    session: Optional[SessionRecord],
    exposure_before_order: float = 0.0,
    risk_limits: RiskLimits = RiskLimits(),
    quarantined: bool = False,
) -> CreateOrderPlan:
    """The shared validation cascade + order construction for the candidate→order
    dispatch. ``candidate`` is known to exist and *not* already ORDERED (the store
    handles those first). ``session`` is the candidate's own originating session.

    ``exposure_before_order`` is the store's current total CAPI exposure (every
    position's cost basis plus every non-terminal order's remaining notional —
    unscoped by session, since exposure is a live, cross-session concept; see
    ``app.policy.existing_exposure``, which the store computes this
    from before calling in). ``risk_limits`` bundles the Phase 6 CAPI risk gate's
    (D-016) independently-optional limits (``RiskLimits()`` = none enforced).
    """

    # The approved-only rule D-010 deferred to the gate lands here.
    if candidate.status is not CandidateStatus.APPROVED:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=CandidateTransitionError(
                f"cannot order candidate {candidate.id} in status "
                f"{candidate.status.value}; must be approved"
            ),
        )

    # Unresolved session (F-004): a candidate whose declared session no longer
    # resolves must not produce order intent. order_session_resolution_reason is
    # a *distinct* predicate from order_intent_block_reason(session) below — that
    # one deliberately treats None as "no live session to stop" for the
    # monitoring loop's current-session emergency-stop check, so it must NOT
    # block on None. create_candidate already rejects an explicit unresolvable
    # session id up front; this is the dispatch-time backstop, audited.
    session_reason = order_session_resolution_reason(session)
    if session_reason is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=OrderIntentBlockedError(f"order intent blocked: {session_reason}"),
            reject_event=EventSpec(
                "order_intent_blocked",
                message=(
                    f"order intent for {candidate.symbol} blocked: {session_reason}"
                ),
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                payload={"reason": session_reason},
                session_id=candidate.session_id,
            ),
        )

    # Safety controls (Rule 8): refuse new order intent when kill-switched /
    # buys-paused — gated at the backend boundary (not just the UI), and audited.
    block = order_intent_block_reason(session)
    if block is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=OrderIntentBlockedError(f"order intent blocked: {block}"),
            reject_event=EventSpec(
                "order_intent_blocked",
                message=f"order intent for {candidate.symbol} blocked: {block}",
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                payload={"reason": block},
                session_id=candidate.session_id,
            ),
        )

    # ADR-001 (wave 3b): block autonomous BUY intent for a symbol quarantined by
    # a broker-authoritative overfill — no new spawn while the primary is
    # quarantined. The operator must reconcile + review before trading resumes.
    if quarantined:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=OrderIntentBlockedError(
                f"order intent for {candidate.symbol} blocked: symbol quarantined "
                f"after a broker overfill (ADR-001)"
            ),
            reject_event=EventSpec(
                "order_intent_blocked_quarantine",
                message=(
                    f"order intent for {candidate.symbol} blocked: symbol "
                    f"quarantined after a broker overfill (ADR-001)"
                ),
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                payload={"reason": "symbol_quarantined"},
                session_id=candidate.session_id,
            ),
        )

    qty = candidate.suggested_quantity
    if qty is None or qty <= 0:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=InvalidOrderError(
                f"candidate {candidate.id} has no positive suggested_quantity "
                f"to size an order"
            ),
        )

    # A LIMIT order requires a finite, positive limit price (F1 / BACKEND-1).
    limit_price = candidate.suggested_limit_price
    bad_price = limit_price_reason(limit_price)
    if bad_price is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=InvalidOrderError(
                f"candidate {candidate.id} has no valid suggested_limit_price "
                f"for a limit order ({bad_price})"
            ),
        )
    # limit_price_reason rejects None / non-finite / non-positive above, so a
    # valid finite float remains (narrows Optional for the risk gate below).
    assert limit_price is not None

    # Phase 6 CAPI pre-trade risk gate (D-016): gate-and-reject, never resize.
    # Local-derived exposure only (folded positions + non-terminal orders'
    # remaining notional) — no live broker/market-data call on the order path.
    risk_block = risk_limit_reason(
        symbol=candidate.symbol,
        order_quantity=qty,
        order_limit_price=limit_price,
        exposure_before_order=exposure_before_order,
        max_shares_per_order=risk_limits.max_shares_per_order,
        max_notional_per_order=risk_limits.max_notional_per_order,
        max_total_exposure=risk_limits.max_total_exposure,
        allowlist=risk_limits.allowlist,
    )
    if risk_block is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=RiskLimitBlockedError(f"risk limit blocked: {risk_block}"),
            reject_event=EventSpec(
                "risk_limit_blocked",
                message=f"order intent for {candidate.symbol} blocked: {risk_block}",
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                payload={
                    "reason": risk_block,
                    "order_quantity": qty,
                    "order_limit_price": limit_price,
                },
                session_id=candidate.session_id,
            ),
        )

    # Long-only buy proposal (beta). Order type LIMIT; session order-type policy
    # (Rule 12) is enforced at submission time, not here.
    order = Order(
        candidate_id=candidate.id,
        symbol=candidate.symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=qty,
        limit_price=limit_price,
        session_id=candidate.session_id,
    )
    return CreateOrderPlan(
        CREATE_ORDER_CREATE,
        order=order,
        events=(
            EventSpec(
                "order_created",
                message=f"order created for {candidate.symbol}",
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                order_id=order.id,
                session_id=candidate.session_id,
            ),
            EventSpec(
                "candidate_transition",
                message="candidate approved -> ordered",
                symbol=candidate.symbol,
                candidate_id=candidate.id,
                order_id=order.id,
                payload={"from": "approved", "to": "ordered"},
                session_id=candidate.session_id,
            ),
        ),
    )


# ---- sell-intent -> order handoff (Phase 7) ------------------------------- #

# Terminal order statuses (no outgoing transitions) — an ordered intent whose
# order has reached one of these is no longer in flight.
_TERMINAL_ORDER_STATUSES = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}
)


def sell_intent_is_active(
    intent: SellIntent,
    order: Optional[Order],
    *,
    order_needs_review: bool = False,
) -> bool:
    """Whether a sell intent is still 'in flight' for the single-flight dedup /
    ``active_sell_intent_for``. Active = ``pending``/``approved`` (not yet
    ordered), or ``ordered`` with an Order still in a non-terminal status AND
    without an open ``needs_review`` broker-submit recovery. ``rejected``/
    ``expired`` intents, ``ordered`` intents whose order reached a terminal
    state (filled/canceled/rejected), and an ``ordered`` intent whose order is
    stranded in ``needs_review`` are all inactive — the symbol is eligible for a
    fresh protective intent (the residual re-evaluation path).

    ``order_needs_review`` (X-003 / ADR "Stranded-order eligibility (blocker)"):
    the caller passes whether ``order`` currently carries an OPEN
    ``needs_review`` broker-submit recovery record (D-017) — a broker order
    accepted upstream that local state can't otherwise confirm as live.
    Treating that as still-active would let a single stuck ``needs_review``
    order permanently block re-protection for the symbol forever, even though
    the recovery record and its operator alert stay independently visible (this
    function only decides single-flight eligibility, never recovery
    visibility). This function stays pure — the store fetches the recovery
    state under its own lock and passes the boolean in, mirroring how ``order``
    itself is fetched and passed in rather than looked up here.
    """

    if intent.status in (SellIntentStatus.PENDING, SellIntentStatus.APPROVED):
        return True
    if intent.status is SellIntentStatus.ORDERED:
        if order is None or order.status in _TERMINAL_ORDER_STATUSES:
            return False
        return not order_needs_review
    return False


def plan_create_order_for_sell_intent(
    *,
    intent: SellIntent,
    live_position_quantity: int,
    order_type: OrderType,
    limit_price: Optional[float],
) -> CreateOrderPlan:
    """The shared validation cascade + SELL order construction for the
    sell-intent→order dispatch (Phase 7). ``intent`` is known to exist and *not*
    already ORDERED (the store handles those first). No CAPI risk gate and no
    kill-switch/session block here — a protective exit reduces risk and its
    submission is gated separately at claim time (see the side/reason-aware claim).

    ``live_position_quantity`` is the symbol's current derived position quantity,
    re-read by the store under its lock: a sell may never exceed it (never a
    short — Rule 7 / long-only). The order carries ``sell_intent_id`` and
    ``candidate_id=None`` (the XOR origin); the ``correlation_id`` on both events
    is the intent id, so the whole protective-exit lifecycle is one filterable key.
    """

    if intent.status is not SellIntentStatus.APPROVED:
        # A precondition violation, not a "the approved handoff failed" case —
        # there is no `approved` state to self-heal FROM (the intent is either
        # not yet approved, already ordered/terminal, or a caller-contract bug
        # elsewhere). No expire; matches the pre-X-002 behavior for this branch.
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=SellIntentTransitionError(
                f"cannot order sell intent {intent.id} in status "
                f"{intent.status.value}; must be approved"
            ),
        )

    def _reject_and_self_heal(error: Exception) -> CreateOrderPlan:
        """X-002: every rejection below is a genuine "the approved handoff
        failed" case — self-heal `approved -> expired` atomically alongside the
        rejection, so the intent is never left stranded `approved` poisoning the
        single-flight dedup forever (`no_sell_intent_stranded_approved`)."""

        now = utcnow()
        expired = intent.model_copy(deep=True)
        expired.status = SellIntentStatus.EXPIRED
        expired.expired_at = now
        expired.updated_at = now
        expire_event = EventSpec(
            "sell_intent_transition",
            message=(
                f"sell intent approved -> expired (order dispatch rejected: {error})"
            ),
            symbol=intent.symbol,
            payload={
                "from": "approved",
                "to": "expired",
                "reason": "dispatch_rejected",
            },
            session_id=intent.session_id,
            correlation_id=intent.id,
        )
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=error,
            expire_intent=expired,
            expire_event=expire_event,
        )

    qty = intent.target_quantity
    if qty is None or qty <= 0:
        return _reject_and_self_heal(
            InvalidOrderError(
                f"sell intent {intent.id} has no positive target_quantity"
            )
        )
    # Never a short (Rule 7 / long-only): the exit cannot exceed the live
    # position. Re-checked here against the freshly-read quantity so a race that
    # reduced the position (another fill) between approve and order cannot oversell.
    if qty > live_position_quantity:
        return _reject_and_self_heal(
            InvalidOrderError(
                f"sell intent {intent.id} target_quantity {qty} exceeds the live "
                f"{intent.symbol} position quantity {live_position_quantity} "
                f"(would create a short)"
            )
        )

    # Order-type/price coherence (Rule 12 exit types): a LIMIT sell needs a
    # finite positive limit; a MARKET sell must carry NO limit price. Do NOT run
    # limit_price_reason unconditionally (it would reject the MARKET exit path).
    if order_type is OrderType.LIMIT:
        bad_price = limit_price_reason(limit_price)
        if bad_price is not None:
            return _reject_and_self_heal(
                InvalidOrderError(
                    f"limit sell for intent {intent.id} needs a valid limit_price "
                    f"({bad_price})"
                )
            )
    elif limit_price is not None:
        return _reject_and_self_heal(
            InvalidOrderError(
                f"{order_type.value} sell for intent {intent.id} must not carry a "
                f"limit_price (got {limit_price!r})"
            )
        )

    order = Order(
        sell_intent_id=intent.id,
        symbol=intent.symbol,
        side=OrderSide.SELL,
        order_type=order_type,
        quantity=qty,
        limit_price=limit_price,
        session_id=intent.session_id,
    )
    return CreateOrderPlan(
        CREATE_ORDER_CREATE,
        order=order,
        events=(
            EventSpec(
                "order_created",
                message=f"protective sell order created for {intent.symbol}",
                symbol=intent.symbol,
                order_id=order.id,
                session_id=intent.session_id,
                correlation_id=intent.id,
            ),
            EventSpec(
                "sell_intent_transition",
                message="sell intent approved -> ordered",
                symbol=intent.symbol,
                order_id=order.id,
                payload={"from": "approved", "to": "ordered"},
                session_id=intent.session_id,
                correlation_id=intent.id,
            ),
        ),
    )


# ---- flatten_position (X-001, atomic manual-flatten) ---------------------- #

# FlattenPlan.outcome values:
FLATTEN_FLAT = "flat"  # no open position
FLATTEN_EXISTING = "existing"  # return an existing intent as-is
FLATTEN_SUPERSEDE_AND_CREATE = "supersede_and_create"  # stand down + create fresh
FLATTEN_DENIED_HALTED = "denied_halted"  # ADR-003: Halted, no override


@dataclass(frozen=True)
class FlattenPlan:
    """Pure outcome of the manual-flatten decision (X-001).

    Evaluated over state the store fetched ENTIRELY under ONE lock hold, so no
    concurrent writer — most critically a protection tick's own
    ``create_sell_intent`` call — can interleave between "decide" and "act".
    That interleaving was the actual defect: the route used to read the active
    intent, then LATER call ``create_sell_intent(MANUAL_FLATTEN, ...)`` as a
    SEPARATE lock hold; a protection tick's own create call could win the
    single-flight race in the gap, and the route never verified the ``reason``
    of what it got back — so a human's flatten could silently be handed a
    ``protection_floor`` intent, which a kill switch would then hold
    unsubmitted. This planner's caller (``StateStore.flatten_position``) never
    releases the lock between fetching this input and applying this plan.

    ``flat``: no open position; the caller (route) surfaces a 409.

    ``existing``: return ``existing_intent``/``existing_order`` as-is — either
    it is ALREADY the caller's own ``manual_flatten`` and has a real order
    (``ORDERED``; idempotent), or a ``protection_floor`` exit that is
    genuinely LIVE at the broker (executing; left alone, never captured or
    duplicated).

    ``supersede_and_create``: any active exit that is NOT yet live is stood
    down first (``supersede_*`` fields, applied in the SAME atomic block as
    the create below), then a fresh ``manual_flatten`` intent for
    ``target_quantity`` is inserted directly and dispatched through the same
    order-handoff machinery ``create_order_for_sell_intent`` uses — so the
    returned intent's ``reason`` is GUARANTEED ``manual_flatten``, never a
    deduped intent of a different reason. "Not yet live" covers: a
    ``protection_floor`` intent with no order at all, or a still-``created``
    order; AND a ``manual_flatten`` intent stranded ``pending``/``approved``
    with no order — reachable only via a crash between two separate commits
    in ``SqliteStateStore.flatten_position`` (see the inline comment below),
    never in ordinary operation. This is what closes X-001: nothing else can
    write to this symbol's sell intents between the supersede and the create,
    because both happen without ever releasing the lock.
    """

    outcome: str
    existing_intent: Optional[SellIntent] = None
    existing_order: Optional[Order] = None
    # Provenance for the ``existing`` deferral to a live PROTECTION_FLOOR exit
    # (INV-036): the audit record that a human flatten was received and deferred,
    # so the "click reads as success" is truthful and traceable. None on the
    # idempotent MANUAL_FLATTEN re-return (that intent is already the caller's own).
    deferral_event: Optional[EventSpec] = None
    supersede_order_cancel: Optional[Order] = None
    supersede_cancel_event: Optional[EventSpec] = None
    supersede_intent_expire: Optional[SellIntent] = None
    supersede_expire_event: Optional[EventSpec] = None
    target_quantity: int = 0


def plan_flatten_position(
    *,
    position: Position,
    active_intent: Optional[SellIntent],
    active_order: Optional[Order],
    trading_state: TradingState = TradingState.ACTIVE,
    override_active: bool = False,
    actor: str = COMMAND_ACTOR_SYSTEM,
    envelope_child: Optional[Order] = None,
    envelope_intent: Optional[SellIntent] = None,
) -> FlattenPlan:
    """Decide the manual-flatten outcome for one symbol.

    ``position`` is the LIVE derived position; ``active_intent`` is the
    symbol's current *active* sell intent (already filtered through
    :func:`sell_intent_is_active`, including the X-003 ``needs_review``
    exclusion) or ``None``; ``active_order`` is its linked order (if any). All
    three are read by the caller under the SAME lock hold this plan is applied
    under — the decision and the eventual write can never straddle a
    concurrent mutation.

    ADR-003 / wave 3e: ``trading_state`` is the current session's §8 FSM and
    ``override_active`` whether an audited emergency-reduce override is active for
    this symbol (both read under the same lock). An ordinary manual flatten is
    **denied in ``Halted``** (``FLATTEN_DENIED_HALTED`` → the store raises
    :class:`FlattenBlockedError` → 409) unless the override is active; it stays
    allowed in ``Active``/``Reducing`` (the pre-3e behavior). Gating at *creation*
    means a ``MANUAL_FLATTEN`` order is never even minted under ``Halted`` without
    authorization — and since ``flatten_position`` is the only producer of that
    reason, an existing manual-flatten order (born only when creation was allowed)
    stays claimable, so the submission gate is untouched.

    ``actor`` (REV-0002 F-002) is a pure pass-through: the store resolves the
    command actor and hands it in, and it is only stamped into the
    ``manual_flatten_deferred`` event's payload here — this planner never resolves
    identity itself, keeping it a pure function of its inputs.

    WO-0036 R2 (Codex PR#8 #4): ``envelope_child`` is the symbol's live-at-venue
    envelope child order (any ``VENUE_LIVE_ORDER_STATUSES`` order minted by a
    LIVE envelope — quarantined included, it MAY be live per ADR-002), read by
    the store under the SAME lock hold, or ``None``. An envelope-backed intent
    carries ``order_id=None`` — the child is only discoverable through the
    envelope's ENVELOPE_ACTION linkage, which is exactly why the pre-R2 planner
    double-booked it. ``envelope_intent`` is that envelope's backing intent row
    (normally ``active_intent`` itself; passed separately so a legacy orphan
    still defers safely).
    """

    if position.quantity <= 0:
        return FlattenPlan(FLATTEN_FLAT)

    if trading_state is TradingState.HALTED and not override_active:
        return FlattenPlan(FLATTEN_DENIED_HALTED)

    if envelope_child is not None:
        # A live envelope child IS the exit, already working at the venue —
        # the same INV-036 deferral as a live protection_floor order: never
        # double-exit, never blind-cancel (ADR-002). The envelope stays the
        # exclusive driver; the human's flatten is recorded, not lost.
        deferred_intent = (
            active_intent if active_intent is not None else envelope_intent
        )
        deferral_event = EventSpec(
            EventType.MANUAL_FLATTEN_DEFERRED.value,
            message=(
                f"manual flatten for {position.symbol} deferred to the live "
                f"execution-envelope child (order {envelope_child.status.value})"
            ),
            symbol=position.symbol,
            order_id=envelope_child.id,
            payload={
                "reason": "deferred_to_live_envelope_child",
                "order_status": envelope_child.status.value,
                "deferred_intent_reason": (
                    deferred_intent.reason.value if deferred_intent else None
                ),
                "actor": actor,
            },
            session_id=envelope_child.session_id,
            correlation_id=deferred_intent.id if deferred_intent else None,
        )
        return FlattenPlan(
            FLATTEN_EXISTING,
            existing_intent=deferred_intent,
            existing_order=envelope_child,
            deferral_event=deferral_event,
        )

    if active_intent is not None:
        if (
            active_intent.reason is SellReason.MANUAL_FLATTEN
            and active_intent.status is SellIntentStatus.ORDERED
        ):
            return FlattenPlan(
                FLATTEN_EXISTING,
                existing_intent=active_intent,
                existing_order=active_order,
            )
        # A protection_floor exit is active with an order that has left CREATED
        # (submitted/partially-filled/cancel-pending/timeout-quarantine): it is in
        # flight or live at the broker (INV-036), so LEAVE IT ALONE — never
        # double-exit, and never blind-cancel a possibly-live order (ADR-002:
        # a SUBMITTING / TIMEOUT_QUARANTINE order may already be working at the
        # venue, so routing it to the local-cancel supersede path below would be
        # exactly the unsafe blind action the quarantine machinery exists to
        # avoid). Deferring is the safe action for every non-CREATED status.
        # Record provenance so the human's flatten is auditable even though we
        # defer (closing the "click reads as success with no record" gap). The
        # payload carries the deferred order's status so a reader can tell a
        # confirmed-live exit from an in-flight/ambiguous one.
        if (
            active_intent.reason is SellReason.PROTECTION_FLOOR
            and active_order is not None
            and active_order.status is not OrderStatus.CREATED
        ):
            deferral_event = EventSpec(
                EventType.MANUAL_FLATTEN_DEFERRED.value,
                message=(
                    f"manual flatten for {position.symbol} deferred to the in-flight "
                    f"protection_floor exit (order {active_order.status.value})"
                ),
                symbol=position.symbol,
                order_id=active_order.id,
                payload={
                    "reason": "deferred_to_live_protection",
                    "order_status": active_order.status.value,
                    "deferred_intent_reason": active_intent.reason.value,
                    # Who commanded the flatten (REV-0002 F-002) — passed IN by the
                    # store, never resolved inside this pure planner.
                    "actor": actor,
                },
                session_id=active_order.session_id,
                correlation_id=active_intent.id,
            )
            return FlattenPlan(
                FLATTEN_EXISTING,
                existing_intent=active_intent,
                existing_order=active_order,
                deferral_event=deferral_event,
            )
        # Not live: supersede. A CREATED order cancels locally; a stranded
        # pending/approved intent with no order at all expires. This also
        # covers a MANUAL_FLATTEN intent found here at PENDING/APPROVED (not
        # ORDERED) with no order (X-001 follow-up, adversarial re-review
        # finding): in normal operation a fresh MANUAL_FLATTEN only sits at
        # PENDING/APPROVED transiently, mid-dispatch, under the SAME
        # continuous lock this function is always called within — reaching
        # here on a LATER call means a hard crash landed between the
        # intent-approve commit and the order-dispatch commit
        # (SqliteStateStore.flatten_position commits those as two separate
        # transactions; InMemoryStateStore's single _atomic() block cannot
        # produce this state at all). Treating a stranded MANUAL_FLATTEN as
        # "the existing exit" would silently no-op forever — HTTP 200,
        # order=None — and permanently poison single-flight dedup for the
        # symbol. Self-healing it here (same as a stranded protection_floor
        # intent) closes that window: the dead intent expires and a real
        # exit is created in its place.
        now = utcnow()
        supersede_order_cancel = None
        supersede_cancel_event = None
        supersede_intent_expire = None
        supersede_expire_event = None
        if active_order is not None:
            updated_order = active_order.model_copy(deep=True)
            updated_order.status = OrderStatus.CANCELED
            updated_order.canceled_at = now
            updated_order.updated_at = now
            supersede_order_cancel = updated_order
            supersede_cancel_event = EventSpec(
                "order_transition",
                message=(
                    f"order {active_order.symbol} created -> canceled "
                    f"(superseded by manual flatten)"
                ),
                symbol=active_order.symbol,
                order_id=active_order.id,
                payload={
                    "from": "created",
                    "to": "canceled",
                    "reason": "superseded_by_manual_flatten",
                },
                session_id=active_order.session_id,
                correlation_id=active_intent.id,
            )
        elif active_intent.status in (
            SellIntentStatus.PENDING,
            SellIntentStatus.APPROVED,
        ):
            updated_intent = active_intent.model_copy(deep=True)
            updated_intent.status = SellIntentStatus.EXPIRED
            updated_intent.expired_at = now
            updated_intent.updated_at = now
            supersede_intent_expire = updated_intent
            supersede_expire_event = EventSpec(
                "sell_intent_transition",
                message=(
                    f"sell intent {active_intent.status.value} -> expired "
                    f"(superseded by manual flatten)"
                ),
                symbol=active_intent.symbol,
                payload={
                    "from": active_intent.status.value,
                    "to": "expired",
                    "reason": "superseded_by_manual_flatten",
                },
                session_id=active_intent.session_id,
                correlation_id=active_intent.id,
            )
        return FlattenPlan(
            FLATTEN_SUPERSEDE_AND_CREATE,
            supersede_order_cancel=supersede_order_cancel,
            supersede_cancel_event=supersede_cancel_event,
            supersede_intent_expire=supersede_intent_expire,
            supersede_expire_event=supersede_expire_event,
            target_quantity=position.quantity,
        )

    return FlattenPlan(FLATTEN_SUPERSEDE_AND_CREATE, target_quantity=position.quantity)


# ---- submit-recovery ledger (D-017) --------------------------------------- #


def require_recovery_status(value: str, *, field: str = "cleanup_status") -> None:
    """Reject a recovery ``cleanup_status`` that is not one of the closed
    ``RECOVERY_STATUSES`` (AIR-004) — the same domain error the transition
    validator raises, so a record can never be *born* in an invalid state either.
    """

    if value not in RECOVERY_STATUSES:
        raise RecoveryTransitionError(
            f"{field} {value!r} is not a valid recovery status; "
            f"must be one of {sorted(RECOVERY_STATUSES)}"
        )


def recovery_status_event(prev_status: str, new_status: Optional[str]) -> Optional[str]:
    """Validate a recovery ``cleanup_status`` transition and return the audit
    event type to write, or ``None`` when nothing should change (AIR-004).

    ``new_status is None`` is a bump-only update (retry_count) with no status
    change — a legal no-op that emits no event, regardless of the current status.
    A same-status "change" is likewise a no-op. Otherwise the transition must be
    one of the explicit allowed moves in ``RECOVERY_TRANSITIONS``
    (``unresolved -> resolved_canceled`` / ``unresolved -> needs_review``); an
    **unknown** status value or a **disallowed** move (notably reopening a
    terminal record back to ``unresolved``) raises
    :class:`RecoveryTransitionError` and the caller must leave the record and its
    audit trail unchanged. A move to needs-review writes
    ``submit_recovery_needs_review`` (a real untracked position — not "resolved");
    a clean cancel writes ``submit_recovery_resolved``. Shared so both stores
    validate and emit identically.
    """

    if new_status is None or new_status == prev_status:
        return None
    if new_status not in RECOVERY_STATUSES:
        raise RecoveryTransitionError(
            f"unknown recovery cleanup_status {new_status!r}; "
            f"must be one of {sorted(RECOVERY_STATUSES)}"
        )
    if new_status not in RECOVERY_TRANSITIONS.get(prev_status, frozenset()):
        raise RecoveryTransitionError(
            f"illegal recovery transition {prev_status!r} -> {new_status!r} "
            f"(no silent reopen of a terminal record)"
        )
    if new_status == RECOVERY_NEEDS_REVIEW:
        return "submit_recovery_needs_review"
    return "submit_recovery_resolved"


# ---- claim_order_for_submission (D-017) ----------------------------------- #


@dataclass(frozen=True)
class ClaimPlan:
    """Pure outcome of the submission-claim decision (the store has already
    fetched the order and both sessions). ``outcome`` is one of
    :data:`CLAIM_CLAIMED` / :data:`CLAIM_BLOCKED` / :data:`CLAIM_SKIPPED`. On a
    claim, ``order`` is the updated (``SUBMITTING``) copy the store persists and
    ``event`` the ``order_submission_claimed`` audit row. On a block, ``reason``
    is set and nothing is written.
    """

    outcome: str
    order: Optional[Order] = None
    event: Optional[EventSpec] = None
    reason: Optional[str] = None


def _buy_claim_hold_reason(
    own_session: Optional[SessionRecord],
    current_session: Optional[SessionRecord],
) -> Optional[str]:
    """The original Rule 8 submission gate, unchanged: a held order is blocked
    against its OWN session (D-013a) and, failing that, the live session as a
    process-wide emergency stop. This is exactly the pre-Phase-7 logic, extracted
    verbatim so every BUY caller and its tests are provably byte-for-byte
    untouched (§5.2) — the sell-side branch is layered *around* it, never inside
    it."""

    hold = session_submission_block_reason(own_session)
    if hold is None:
        current_block = order_intent_block_reason(current_session)
        if current_block is not None:
            hold = f"current_{current_block}"
    return hold


def _claim_hold_reason(
    order: Order,
    own_session: Optional[SessionRecord],
    current_session: Optional[SessionRecord],
    sell_reason: Optional[SellReason],
    *,
    quarantined: bool = False,
) -> Optional[str]:
    """Why this ``CREATED`` order must not be claimed for submission, or ``None``.

    Phase 7 side/reason-aware gate (§5.2 / D-P2). A well-formed protective/flatten
    SELL short-circuits the BUY control checks based on its owning intent's
    ``reason``. The qualifying gate is deliberately strict — ``side is SELL`` AND
    ``sell_intent_id`` set AND ``candidate_id`` is ``None`` AND a *known* reason —
    so a mislabeled or origin-corrupt order can never inherit the bypass; it falls
    through to the strict BUY path instead (fail-safe).

    * ``MANUAL_FLATTEN`` → never held at *submission*: a manual-flatten order,
      once it EXISTS, always reaches the broker. ADR-003 (wave 3e) moved the
      ``Halted``-denial to *creation* (``plan_flatten_position``): a
      ``MANUAL_FLATTEN`` order is only ever minted when the flatten was authorized
      (``Active``/``Reducing``, or an emergency-reduce override under ``Halted``),
      and ``flatten_position`` is its sole producer — so an existing one is, by
      construction, already authorized and stays claimable here. **Deliberate,
      documented scoping (wave 3e review LOW):** an order created while ``Active``
      is still submitted if the kill switch engages before the submission sweep
      claims it — the Halted-deny is at *issuance*, and a locally-``CREATED`` order
      (not yet at the venue, so not literally "in-flight") is an exit the operator
      already commanded, not new intent. Asymmetric with autonomous
      ``PROTECTION_FLOOR`` (still held by the kill switch here) BY DESIGN: a human
      command outranks autonomous protection (D-P2). Pinned by
      ``test_manual_flatten_created_in_active_submits_under_later_halt``.
      Buys-paused / closed / unknown-session are likewise bypassed (D-P2 spirit).
    * ``PROTECTION_FLOOR`` → bypass ``buys_paused`` / ``session_closed`` /
      ``unknown_session`` (a lingering position must stay exitable after close),
      **but stays blocked by the kill switch** on EITHER the own or the current
      session — the operator's all-stop halts even autonomous protection, which is
      then wound down separately (a held protective order is expired, not left
      forever).
    * Anything else (a BUY, or a degenerate SELL) → quarantine gate, then the
      unchanged BUY gate.

    ``quarantined`` (wave 3b / ADR-001): the order's symbol is quarantined by a
    broker overfill. An autonomous exposure-increasing BUY must be HELD — "no new
    autonomous spawn while quarantined" applies to a *pre-existing* CREATED order
    too, not only to newly-created intent (``create_order_for_candidate`` already
    blocks the latter). Protective/flatten SELLs above are exempt: an exit reduces
    risk (and the position guards already stop a sell of a non-positive book), so
    the operator can always wind risk down. Checked before the buy control gate so
    the (more actionable) quarantine reason surfaces.
    """

    is_protective_sell = (
        OrderSide(order.side) is OrderSide.SELL
        and order.sell_intent_id is not None
        and order.candidate_id is None
        and sell_reason is not None
    )
    if is_protective_sell:
        if sell_reason is SellReason.MANUAL_FLATTEN:
            return None
        if sell_reason is SellReason.PROTECTION_FLOOR:
            if kill_switch_block_reason(own_session) is not None:
                return "kill_switch"
            if kill_switch_block_reason(current_session) is not None:
                return "current_kill_switch"
            return None
        # An unrecognized future reason falls through to the strict path.
    if quarantined:
        return "symbol_quarantined"
    return _buy_claim_hold_reason(own_session, current_session)


def plan_claim_order_for_submission(
    *,
    order: Optional[Order],
    own_session: Optional[SessionRecord],
    current_session: Optional[SessionRecord],
    sell_reason: Optional[SellReason] = None,
    quarantined: bool = False,
) -> ClaimPlan:
    """Decide whether a ``CREATED`` order may be claimed for submission.

    ``own_session`` is the order's originating session (D-013a: a held order is
    gated against its OWN session, not merely the live one, so a kill-switched
    order from a prior session can't slip through after a date rollover mints a
    fresh permissive session). ``current_session`` is the live session, checked
    as a process-wide emergency stop. ``sell_reason`` is the owning
    ``SellIntent.reason`` for a SELL order (``None`` for a BUY, or when the intent
    can't be resolved) — the store fetches it under the same lock. ``quarantined``
    is whether the order's symbol is quarantined by a broker overfill (ADR-001,
    wave 3b) — the store derives it from the event log under the same lock; it
    holds an autonomous BUY but never a protective/flatten exit. The store calls
    this under its lock, so the control state read here cannot change between the
    decision and the ``CREATED → SUBMITTING`` write the store then applies.
    """

    if order is None or order.status is not OrderStatus.CREATED:
        # No longer submittable: a session close cancelled it, it was already
        # claimed, or it never existed. Nothing to do.
        return ClaimPlan(CLAIM_SKIPPED)

    hold = _claim_hold_reason(
        order, own_session, current_session, sell_reason, quarantined=quarantined
    )
    if hold is not None:
        return ClaimPlan(CLAIM_BLOCKED, reason=hold)

    updated = order.model_copy(deep=True)
    updated.status = OrderStatus.SUBMITTING
    updated.updated_at = utcnow()
    event = EventSpec(
        "order_submission_claimed",
        message=f"submission claimed for {order.symbol}",
        symbol=order.symbol,
        candidate_id=order.candidate_id,
        order_id=order.id,
        payload={"from": "created", "to": "submitting"},
        session_id=order.session_id,
    )
    return ClaimPlan(CLAIM_CLAIMED, order=updated, event=event)


# ---- transition_order ----------------------------------------------------- #

# OrderTransitionPlan.outcome values:
ORDER_TRANSITION_REJECT = "reject"  # raise `error`
ORDER_TRANSITION_NOOP = "noop"  # nothing changed; store returns the order unchanged
ORDER_TRANSITION_APPLY = "apply"  # persist `order` (fully updated) + write `event`


@dataclass(frozen=True)
class OrderTransitionPlan:
    """Pure outcome of :meth:`StateStore.transition_order` (the order already
    fetched by the store). ``order`` on an ``apply`` is the fully-updated copy —
    status/filled_quantity/broker_order_id and the relevant terminal timestamp
    already set — so the store just persists it and writes ``event``.
    """

    outcome: str
    error: Optional[Exception] = None
    order: Optional[Order] = None
    event: Optional[EventSpec] = None


def require_bool(value: object, *, field: str) -> None:
    """Reject a non-``bool`` control/flag value at the store boundary (AIR-005).

    Strict: only ``True``/``False`` pass. A string (``"false"``), an int
    (``0``/``1`` — note ``isinstance(1, bool)`` is ``False``), a list/dict, or
    ``None`` is rejected with :class:`InvalidControlValueError` and no mutation.
    This is what stops a ``{"engaged": "false"}`` payload — a truthy non-empty
    string — from *engaging* the kill switch (an emergency-stop inversion).
    """

    if not isinstance(value, bool):
        raise InvalidControlValueError(
            f"{field} must be a bool, not {type(value).__name__} {value!r}"
        )


def require_status_enum(value: object, enum_cls: type, *, field: str) -> None:
    """Reject a non-enum status argument at the store boundary (AIR-009).

    ``value`` must be an actual member of ``enum_cls`` — a bare string like
    ``"pending"`` does **not** qualify even though ``enum_cls`` is a ``str``-enum
    (``isinstance("pending", CandidateStatus)`` is ``False``). This is what makes
    both stores reject strings/bools/``None`` identically instead of one silently
    coercing and the other leaking ``AttributeError``. Raises
    :class:`InvalidStatusError`; performs no mutation.
    """

    if not isinstance(value, enum_cls):
        raise InvalidStatusError(
            f"{field} must be a {enum_cls.__name__} instance, not "
            f"{type(value).__name__} {value!r}"
        )


def plan_transition_order(
    *,
    order: Order,
    new_status: OrderStatus,
    filled_quantity: Optional[int],
    broker_order_id: Optional[str],
    actor: str = COMMAND_ACTOR_SYSTEM,
) -> OrderTransitionPlan:
    """Decide an order transition — the shared logic (legality, monotonic
    filled-quantity, the true-no-op rule, and the D-008 ``order_transition`` vs
    ``order_fill_progress`` audit split) that was duplicated between the stores.

    ``new_status`` must be an ``OrderStatus`` instance (AIR-009): a bare string
    or a bool/None is rejected up front, before any legality check, so both
    stores behave identically.
    """

    require_status_enum(new_status, OrderStatus, field="new_status")
    current = order.status
    status_changed = new_status is not current
    if status_changed and new_status not in ORDER_TRANSITIONS.get(current, set()):
        return OrderTransitionPlan(
            ORDER_TRANSITION_REJECT,
            error=OrderTransitionError(
                f"illegal order transition {current.value} -> {new_status.value}"
            ),
        )

    # AIR-001: reaching SUBMITTED means the broker accepted the order and handed
    # back an id — the only key we can poll/cancel by. A status change *into*
    # SUBMITTED without a non-empty broker id would persist an untrackable
    # "submitted" order, so reject it here in the shared planner (both stores
    # enforce it identically, not just the monitoring caller). The effective id
    # is the one being assigned, falling back to whatever the order already
    # carries; a same-status no-op/reaffirm is not re-validated.
    if status_changed and new_status is OrderStatus.SUBMITTED:
        effective_broker_id = (
            broker_order_id if broker_order_id is not None else order.broker_order_id
        )
        if not (isinstance(effective_broker_id, str) and effective_broker_id.strip()):
            return OrderTransitionPlan(
                ORDER_TRANSITION_REJECT,
                error=OrderTransitionError(
                    f"cannot mark order {order.id} SUBMITTED without a non-empty "
                    f"broker_order_id (AIR-001)"
                ),
            )

    # Bound + monotonic filled_quantity (Fix 5). Out-of-range or backward progress
    # raises and writes nothing. Equality is allowed (handled as a no-op below).
    if filled_quantity is not None:
        bad = filled_quantity_reason(order, filled_quantity)
        if bad is not None:
            return OrderTransitionPlan(
                ORDER_TRANSITION_REJECT,
                error=InvalidOrderError(
                    f"invalid filled_quantity {filled_quantity} for order "
                    f"{order.id} (qty {order.quantity}, current "
                    f"{order.filled_quantity}): {bad}"
                ),
            )

    qty_changed = (
        filled_quantity is not None and filled_quantity != order.filled_quantity
    )
    broker_changed = (
        broker_order_id is not None and broker_order_id != order.broker_order_id
    )

    # True no-op (status unchanged and nothing else changed): write no audit row
    # and mutate nothing — same rule transition_candidate uses (D-008).
    if not status_changed and not qty_changed and not broker_changed:
        return OrderTransitionPlan(ORDER_TRANSITION_NOOP)

    previous_filled = order.filled_quantity
    updated = order.model_copy(deep=True)
    if qty_changed:
        assert filled_quantity is not None  # qty_changed implies filled_quantity set
        updated.filled_quantity = filled_quantity
    if broker_changed:
        updated.broker_order_id = broker_order_id
    if status_changed:
        updated.status = new_status
        ts_field = ORDER_TIMESTAMP.get(new_status)
        if ts_field and getattr(updated, ts_field) is None:
            setattr(updated, ts_field, utcnow())
    updated.updated_at = utcnow()

    if status_changed:
        event = EventSpec(
            "order_transition",
            message=f"order {current.value} -> {new_status.value}",
            symbol=updated.symbol,
            candidate_id=updated.candidate_id,
            order_id=updated.id,
            # UC-002 (REV-0002 F-002 class): stamp the command actor so a manual
            # cancel's audit event records who did it; routine engine transitions
            # default to COMMAND_ACTOR_SYSTEM.
            payload={"from": current.value, "to": new_status.value, "actor": actor},
            session_id=updated.session_id,
        )
    else:
        # Same status, but fill progressed (or a broker id was assigned). Not a
        # no-op — record it with the before/after quantity, not a generic
        # same-status row (D-008).
        payload: dict[str, Any] = {
            "status": current.value,
            "previous_filled_quantity": previous_filled,
            "filled_quantity": updated.filled_quantity,
        }
        if broker_changed:
            payload["broker_order_id"] = broker_order_id
        event = EventSpec(
            "order_fill_progress",
            message=(
                f"order {updated.symbol} fill progress "
                f"{previous_filled} -> {updated.filled_quantity}"
            ),
            symbol=updated.symbol,
            candidate_id=updated.candidate_id,
            order_id=updated.id,
            payload=payload,
            session_id=updated.session_id,
        )
    return OrderTransitionPlan(ORDER_TRANSITION_APPLY, order=updated, event=event)


# ---- routine order-status ExecutionEvent emission (WO-0007a) -------------- #
#
# Additive: `plan_transition_order`/`plan_claim_order_for_submission` above are
# UNTOUCHED (their signatures, legality, and existing test surface stay exactly
# as they were). The store applies the plan as before, then ALSO calls this
# helper and appends the resulting ExecutionEvent (if any) in the SAME atomic
# write as the existing order-row + audit-event write, so the routine
# claim/ack/fill/cancel/reject lifecycle finally has a corroborating entry in
# the durable execution_events log (closing the reconstructability gap for
# WO-0007b), without making `orders.status` itself event-sourced. See
# work/active/WO-0007a-order-status-eventing/design-decision.md.
#
# PROVENANCE (source/authority): derived per transition from `(old_status,
# new_status)` by `_routine_event_provenance` below (WO-0009 — faithful
# provenance, replacing WO-0007a's conservative uniform ENGINE/LOCAL). It follows
# the same convention the rest of the log uses (`execution_event_for_fill`,
# `plan_resolve_timeout_quarantine`, `plan_reconcile_resolve_order`):
#   * ENGINE/LOCAL for the genuinely engine-local transitions — the claim
#     (`CREATED -> SUBMITTING`, a pre-broker engine decision) and a `CANCELED` of
#     an order the broker never confirmed (no `broker_order_id`): a never-submitted
#     `CREATED` order cancelled locally (session close, flatten supersede, manual),
#     OR the `SUBMITTING -> CANCELED` release when a submit failed before the venue
#     returned an id — the no-zombie cancel of a BUY whose session closed mid-submit
#     (`app/monitoring.py`). `broker_order_id` is assigned only when `SUBMITTED` is
#     recorded, so its absence reliably means the broker never saw this order.
#   * BROKER_REST/BROKER_AUTHORITATIVE for the broker-OBSERVED facts — `SUBMITTED`
#     (only reached with a broker id, AIR-001), `PARTIALLY_FILLED`/`FILLED` (fills
#     seen via the reconcile poll), `REJECTED` (broker rejection via poll/TQ), and
#     a broker-confirmed `CANCELED` (old status past `CREATED`). `authority` is the
#     ADR-001-critical field (`BROKER_AUTHORITATIVE` wins conflicts); it is correct
#     in every case here, and the engine paths never over-claim it.
#   * `source` is `BROKER_REST` because every routine broker observation currently
#     arrives via REST poll/ack — no `transition_order`/`claim_order_for_submission`
#     caller is websocket-driven (verified: every caller in app/monitoring.py and
#     app/facade is REST/local). A future stream-ingestion path would pass
#     `BROKER_STREAM`; threading that from the callers is deferred until such a
#     path exists (WO-0009 gate, "alternative rejected"). This is NOT the read-flip
#     (WO-0007b) — `orders.status` stays authoritative; no projector consumes these.

_EXECUTION_EVENT_FOR_ROUTINE_STATUS: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.SUBMITTED: ExecutionEventType.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED: ExecutionEventType.PARTIALLY_FILLED,
    OrderStatus.FILLED: ExecutionEventType.FILLED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
}

# These three share their dedupe_key FORMAT (`f"{status.value}:{order_id}"`)
# with `plan_resolve_timeout_quarantine` / `plan_reconcile_resolve_order`
# (`_EXECUTION_EVENT_FOR_RESOLVED_STATUS` / `_RECONCILE_RESOLVE_EXEC` above).
# Safe today only because at most one writer family ever reaches a given
# terminal status for a given order (design doc item 5) — enforced below by
# the TIMEOUT_QUARANTINE guard, not merely argued in a comment.
_SHARED_FORMAT_KEY_STATUSES = frozenset(
    {OrderStatus.SUBMITTED, OrderStatus.CANCELED, OrderStatus.REJECTED}
)


def _routine_event_provenance(
    order: Order, new_status: OrderStatus
) -> tuple[EventSource, EventAuthority]:
    """Faithful ``(source, authority)`` for a routine order-status event (WO-0009).
    See the PROVENANCE note above.

    Engine-local iff the transition is the pre-broker claim, or a ``CANCELED`` of an
    order the broker never confirmed — one with no ``broker_order_id``. That covers
    both a never-submitted ``CREATED`` order (session close / flatten supersede /
    manual never-submitted cancel) AND the ``SUBMITTING -> CANCELED`` release when a
    submit failed before the venue returned an id (the no-zombie cancel of a BUY
    whose session closed mid-submit — ``app/monitoring.py``). ``broker_order_id`` is
    assigned only when ``SUBMITTED`` is recorded, so its absence reliably means the
    broker never saw this order. Every other routine-emitted status
    (``SUBMITTED``/``PARTIALLY_FILLED``/``FILLED``/``REJECTED`` and a broker-confirmed
    ``CANCELED``) is a broker-observed fact.

    (Using ``broker_order_id is None`` rather than ``old_status is CREATED`` fixes a
    real over-claim the WO-0009 adversarial-verify pass found: the
    ``SUBMITTING -> CANCELED`` submit-failure release is engine-local but has old
    status ``SUBMITTING``, so the old proxy stamped it BROKER_AUTHORITATIVE.)
    """

    # Engine-INITIATED, pre-broker-confirmation statuses: the claim
    # (CREATED->SUBMITTING), the claim release (SUBMITTING->CREATED, WO-0007b), and
    # a cancel REQUEST (->CANCEL_PENDING, WO-0007b). None of these is a
    # broker-authored fact — CANCEL_PENDING especially must not be authoritative, or
    # it would wrongly win an ADR-001 conflict against a real late broker FILL
    # (transitions.py: CANCEL_PENDING->FILLED).
    if new_status in (
        OrderStatus.SUBMITTING,
        OrderStatus.CREATED,
        OrderStatus.CANCEL_PENDING,
    ):
        return EventSource.ENGINE, EventAuthority.LOCAL
    if new_status is OrderStatus.CANCELED and order.broker_order_id is None:
        return EventSource.ENGINE, EventAuthority.LOCAL
    return EventSource.BROKER_REST, EventAuthority.BROKER_AUTHORITATIVE


def execution_event_for_routine_transition(
    order: Order,
    new_status: OrderStatus,
    filled_quantity: Optional[int],
    occurrence: Optional[int] = None,
) -> Optional[ExecutionEvent]:
    """The ``ExecutionEvent`` (if any) the ROUTINE order-lifecycle write path —
    ``claim_order_for_submission``, ``transition_order``, ``plan_close_session``'s
    CREATED-BUY cancel, and ``plan_flatten_position``'s supersede-cancel — should
    co-append alongside its existing order-row + audit-event write.

    ``order`` is the order's state BEFORE this transition (i.e. its ``.status``
    is the OLD status) — needed to (a) detect the ``PARTIALLY_FILLED ->
    PARTIALLY_FILLED`` same-status fill-progress self-loop versus first entry
    into ``PARTIALLY_FILLED``, and (b) enforce the TIMEOUT_QUARANTINE
    defense-in-depth guard below. Returns ``None`` when ``new_status`` isn't one
    this WO instruments, so a caller can invoke this unconditionally after every
    successful apply and simply skip appending on ``None``.

    ``occurrence`` is 0-based and only meaningful for ``CREATED -> SUBMITTING``
    (the claim), the one transition that can repeat (the single cycle in the
    order-status graph, design doc item 1) — the caller must supply the count of
    PRIOR ``SUBMIT_PENDING`` execution events for this order_id so each repeat
    gets a distinct, gapless dedupe_key (``submit_pending:{order_id}:{n}``).
    ``None``/omitted defaults to ``0`` (a bare first claim).

    ``source``/``authority`` are derived per transition by
    ``_routine_event_provenance`` (WO-0009) from ``(order.status, new_status)`` —
    see the PROVENANCE note above.
    """

    source, authority = _routine_event_provenance(order, new_status)

    # Defense-in-depth (WO-0007b, adversarial-verify finding): TIMEOUT_QUARANTINE is
    # a legal ORDER_TRANSITIONS edge from SUBMITTING, but it is set ONLY via the
    # evented path (plan_transition_order_evented, which co-writes the
    # TIMEOUT_QUARANTINE ExecutionEvent). A routine transition_order that reached it
    # would flip orders.status with NO event, silently diverging the order-status
    # projection (project_order_status would reconstruct the prior status). No call
    # site does this today; this refuses it loudly rather than leaving a footgun
    # for the read-flip (Stage D). The order stays un-transitioned (the helper runs
    # before the store's atomic write).
    assert new_status is not OrderStatus.TIMEOUT_QUARANTINE, (
        "execution_event_for_routine_transition: TIMEOUT_QUARANTINE must be set via "
        "the evented path (plan_transition_order_evented), not routine "
        f"transition_order (order {order.id}) — the routine path emits no "
        "TIMEOUT_QUARANTINE event, which would diverge the order-status projection"
    )

    if new_status is OrderStatus.SUBMITTING:
        n = occurrence if occurrence is not None else 0
        return ExecutionEvent(
            event_type=ExecutionEventType.SUBMIT_PENDING,
            source=source,
            authority=authority,
            dedupe_key=f"submit_pending:{order.id}:{n}",
            symbol=order.symbol,
            side=OrderSide(order.side),
            order_id=order.id,
            session_id=order.session_id,
        )

    if new_status is OrderStatus.CREATED and order.status is OrderStatus.SUBMITTING:
        # WO-0007b: the SUBMITTING -> CREATED claim release — the only ->CREATED
        # transition_order edge (transitions.py: CREATED is a target of SUBMITTING
        # alone). Guarded on old status SUBMITTING so a same-status/other call is
        # not mistaken for a release. Occurrence-keyed like the claim so repeated
        # claim/release cycles stay gapless (`release:{order_id}:{n}`, n = prior
        # SUBMIT_RELEASED count, supplied by the caller). Without this event a
        # released order projects as SUBMITTING under latest-wins and the claim
        # gate strands it.
        n = occurrence if occurrence is not None else 0
        return ExecutionEvent(
            event_type=ExecutionEventType.SUBMIT_RELEASED,
            source=source,
            authority=authority,
            dedupe_key=f"release:{order.id}:{n}",
            symbol=order.symbol,
            side=OrderSide(order.side),
            order_id=order.id,
            session_id=order.session_id,
        )

    if new_status is OrderStatus.CANCEL_PENDING:
        # WO-0007b: entry into CANCEL_PENDING (cancel requested at the broker). Emit
        # ONCE on entry so a live pending-cancel order is representable in the
        # projection. The self-loop (CANCEL_PENDING -> CANCEL_PENDING, a late fill
        # progressing) leaves status unchanged and emits nothing — latest-wins
        # already yields CANCEL_PENDING. CANCEL_PENDING is not re-enterable
        # (transitions.py), so a bare `cancel_pending:{order_id}` key is unique.
        if order.status is OrderStatus.CANCEL_PENDING:
            return None
        return ExecutionEvent(
            event_type=ExecutionEventType.CANCEL_PENDING,
            source=source,
            authority=authority,
            dedupe_key=f"cancel_pending:{order.id}",
            symbol=order.symbol,
            side=OrderSide(order.side),
            order_id=order.id,
            session_id=order.session_id,
        )

    if (
        new_status is OrderStatus.PARTIALLY_FILLED
        and order.status is OrderStatus.PARTIALLY_FILLED
    ):
        # Same-status fill-progress self-loop. `filled_quantity` is monotonic
        # (bound-checked by `plan_transition_order`), so this key is guaranteed
        # distinct per repeat.
        return ExecutionEvent(
            event_type=ExecutionEventType.PARTIALLY_FILLED,
            source=source,
            authority=authority,
            dedupe_key=f"order_fill_progress:{order.id}:{filled_quantity}",
            symbol=order.symbol,
            side=OrderSide(order.side),
            order_id=order.id,
            session_id=order.session_id,
        )

    exec_type = _EXECUTION_EVENT_FOR_ROUTINE_STATUS.get(new_status)
    if exec_type is None:
        return None

    if new_status in _SHARED_FORMAT_KEY_STATUSES:
        # Defense-in-depth (design-review Finding D): refuse to build a
        # shared-format key for an order currently in TIMEOUT_QUARANTINE — that
        # key format is reserved for `plan_resolve_timeout_quarantine` /
        # `plan_reconcile_resolve_order`. Cannot happen today (no routine call
        # site drives a TIMEOUT_QUARANTINE order through this path), but this
        # enforces the invariant in code rather than leaving it as doc-only
        # reasoning a future refactor could silently violate.
        assert order.status is not OrderStatus.TIMEOUT_QUARANTINE, (
            "execution_event_for_routine_transition: refusing to build a "
            f"shared-format {new_status.value!r} key for order {order.id} — it "
            "is currently TIMEOUT_QUARANTINE, and that key format is reserved "
            "for plan_resolve_timeout_quarantine / plan_reconcile_resolve_order "
            "(WO-0007a design doc, item 5)"
        )

    return ExecutionEvent(
        event_type=exec_type,
        source=source,
        authority=authority,
        dedupe_key=f"{new_status.value}:{order.id}",
        symbol=order.symbol,
        side=OrderSide(order.side),
        order_id=order.id,
        session_id=order.session_id,
    )


# ---- order-status backfill (WO-0007b Stage D read-flip migration) --------- #
#
# After the read-flip, get_order derives status from project_order_status. An order
# whose status predates WO-0007a eventing has NO lifecycle events, so it would
# project CREATED (the default) — a regression. At init the store backfills a
# single synthetic reconstruction event for each such order so the projection yields
# its (pre-flip authoritative) column status. Mirrors the FILL backfill
# (_backfill_fill_events) and the trading-state column heal. Only fires for orders
# with NO lifecycle events (projection==CREATED) whose column is non-CREATED — it
# never overrides an order that already has events, so it cannot mis-heal a genuine
# divergence. Deterministic dedupe_key => idempotent across re-init / replay.
_STATUS_TO_BACKFILL_EVENT: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.SUBMITTING: ExecutionEventType.SUBMIT_PENDING,
    OrderStatus.SUBMITTED: ExecutionEventType.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED: ExecutionEventType.PARTIALLY_FILLED,
    OrderStatus.CANCEL_PENDING: ExecutionEventType.CANCEL_PENDING,
    OrderStatus.FILLED: ExecutionEventType.FILLED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
    OrderStatus.TIMEOUT_QUARANTINE: ExecutionEventType.TIMEOUT_QUARANTINE,
}


def order_status_backfill_event(order: Order) -> Optional[ExecutionEvent]:
    """The synthetic reconstruction event that makes ``project_order_status`` yield
    ``order.status`` for a pre-WO-0007a order that has no lifecycle events. Returns
    ``None`` for ``CREATED`` (the projector's default — no event needed). Provenance
    is ``RECONCILIATION``/``SYNTHETIC`` (a deterministic migration-time inference,
    not a live broker/engine fact)."""

    event_type = _STATUS_TO_BACKFILL_EVENT.get(order.status)
    if event_type is None:
        return None
    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.RECONCILIATION,
        authority=EventAuthority.SYNTHETIC,
        dedupe_key=f"backfill_status:{order.id}",
        symbol=order.symbol,
        side=OrderSide(order.side),
        order_id=order.id,
        session_id=order.session_id,
    )


# ---- evented order transition (wave 3c: TIMEOUT_QUARANTINE, ADR-002) ------ #


@dataclass(frozen=True)
class OrderEventedTransitionPlan:
    """Pure outcome of an order status transition whose **first durable write is
    an ``ExecutionEvent``** (wave 3c / ADR-002), co-written atomically with a
    specific audit event and the order-row read-model flip.

    Legality + the fully-updated order come from :func:`plan_transition_order`
    (so the shared ``ORDER_TRANSITIONS`` machine and the AIR-001 broker-id guard
    still apply); this attaches the ``ExecutionEvent`` that is the durable truth
    and a caller-chosen audit event. ``outcome`` reuses the ``ORDER_TRANSITION_*``
    constants: REJECT (illegal — writes nothing, raise ``error``), NOOP (same
    status — writes nothing), APPLY (persist ``order`` + ``audit_event`` +
    ``execution_event`` in ONE atomic block).
    """

    outcome: str
    error: Optional[Exception] = None
    order: Optional[Order] = None
    audit_event: Optional[EventSpec] = None
    execution_event: Optional[ExecutionEvent] = None


def plan_transition_order_evented(
    *,
    order: Order,
    new_status: OrderStatus,
    execution_event_type: ExecutionEventType,
    audit_event_type: str,
    dedupe_key: str,
    source: EventSource,
    authority: EventAuthority,
    broker_order_id: Optional[str] = None,
    reason: Optional[str] = None,
    ts_event: Optional[datetime] = None,
) -> OrderEventedTransitionPlan:
    """Plan a status transition that records an ``ExecutionEvent`` as its durable
    truth (the status column becomes a co-written read-model — the honest scope of
    ``event_truth`` for an order-lifecycle fact; see docs/SPINE_WAVE3C_PLAN.md C5).

    Reuses :func:`plan_transition_order` for legality (the transition must be in
    ``ORDER_TRANSITIONS``) and the updated order (status/timestamps/broker id +
    the AIR-001 "SUBMITTED needs a broker id" guard). ``dedupe_key`` makes the
    append idempotent on replay (INV-5): re-applying the same quarantine/resolution
    is a no-op at the event-log layer.
    """

    base = plan_transition_order(
        order=order,
        new_status=new_status,
        filled_quantity=None,
        broker_order_id=broker_order_id,
    )
    if base.outcome == ORDER_TRANSITION_REJECT:
        return OrderEventedTransitionPlan(ORDER_TRANSITION_REJECT, error=base.error)
    if base.outcome == ORDER_TRANSITION_NOOP:
        return OrderEventedTransitionPlan(ORDER_TRANSITION_NOOP)

    execution_event = ExecutionEvent(
        event_type=execution_event_type,
        source=source,
        authority=authority,
        dedupe_key=dedupe_key,
        ts_event=ts_event,
        symbol=order.symbol,
        side=OrderSide(order.side),
        order_id=order.id,
        session_id=order.session_id,
    )
    payload: dict[str, Any] = {"from": order.status.value, "to": new_status.value}
    if reason is not None:
        payload["reason"] = reason
    if broker_order_id is not None:
        payload["broker_order_id"] = broker_order_id
    audit_event = EventSpec(
        audit_event_type,
        message=(
            f"order {order.symbol} {order.status.value} -> {new_status.value}"
            + (f" ({reason})" if reason else "")
        ),
        symbol=order.symbol,
        candidate_id=order.candidate_id,
        order_id=order.id,
        payload=payload,
        session_id=order.session_id,
    )
    return OrderEventedTransitionPlan(
        ORDER_TRANSITION_APPLY,
        order=base.order,
        audit_event=audit_event,
        execution_event=execution_event,
    )


def plan_quarantine_timed_out_order(
    order: Order, *, reason: Optional[str] = None
) -> OrderEventedTransitionPlan:
    """``SUBMITTING → TIMEOUT_QUARANTINE`` for an ambiguous submit (ADR-002). The
    quarantine is OUR local decision (the submit's outcome is unknown), hence
    ``ENGINE``/``LOCAL`` provenance — it is not a broker-reported fact."""

    return plan_transition_order_evented(
        order=order,
        new_status=OrderStatus.TIMEOUT_QUARANTINE,
        execution_event_type=ExecutionEventType.TIMEOUT_QUARANTINE,
        audit_event_type="order_timeout_quarantined",
        dedupe_key=f"timeout_quarantine:{order.id}",
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        reason=reason,
    )


_EXECUTION_EVENT_FOR_RESOLVED_STATUS: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.SUBMITTED: ExecutionEventType.SUBMITTED,
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
}


def plan_resolve_timeout_quarantine(
    order: Order,
    new_status: OrderStatus,
    *,
    broker_order_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> OrderEventedTransitionPlan:
    """``TIMEOUT_QUARANTINE → {SUBMITTED, REJECTED, CANCELED}`` resolved by a
    read-only targeted ``client_order_id`` query (ADR-002). The venue's answer is
    a broker-authoritative fact (``BROKER_REST``/``BROKER_AUTHORITATIVE``).
    Resolving to ``SUBMITTED`` requires the ``broker_order_id`` the query
    returned (AIR-001); the normal reconcile poll then ingests any fills, so
    ``FILLED`` is reached via ``SUBMITTED``, never directly (INV-9 — conflict C4)."""

    exec_type = _EXECUTION_EVENT_FOR_RESOLVED_STATUS.get(new_status)
    if exec_type is None:
        raise ValueError(
            f"cannot resolve a timeout quarantine to {new_status.value}; must be "
            f"one of {sorted(s.value for s in _EXECUTION_EVENT_FOR_RESOLVED_STATUS)}"
        )
    return plan_transition_order_evented(
        order=order,
        new_status=new_status,
        execution_event_type=exec_type,
        audit_event_type="order_timeout_quarantine_resolved",
        dedupe_key=f"{new_status.value}:{order.id}",
        source=EventSource.BROKER_REST,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        broker_order_id=broker_order_id,
        reason=reason,
    )


# ---- reconcile not-found resolution (wave 4e-3) --------------------------- #

# The only terminals the mass-report reconcile may resolve an absent open order to.
# FILLED is deliberately excluded — a position-affecting terminal must flow through
# a fill (INV-9), never a bare status flip.
_RECONCILE_RESOLVE_EXEC: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
}


def plan_reconcile_resolve_order(
    order: Order,
    new_status: OrderStatus,
    *,
    reason: Optional[str] = None,
) -> OrderEventedTransitionPlan:
    """``SUBMITTED → REJECTED`` / ``PARTIALLY_FILLED → CANCELED`` (fills preserved)
    for an open order that a read-only targeted ``client_order_id`` query confirmed
    ABSENT at the venue, after the ``open_check_missing_retries`` bound (§7 / wave
    4e-3). The venue's confirmed-absence is a broker-authoritative fact
    (``BROKER_REST`` / ``BROKER_AUTHORITATIVE``); the order-status column becomes a
    co-written read-model of the ``ExecutionEvent`` (the honest ``event_truth`` scope
    for an order-lifecycle fact, mirror of wave 3c). ``FILLED`` is never a target —
    a position-affecting terminal flows through a fill (INV-9)."""

    exec_type = _RECONCILE_RESOLVE_EXEC.get(new_status)
    if exec_type is None:
        raise ValueError(
            f"cannot reconcile-resolve an order to {new_status.value}; must be one "
            f"of {sorted(s.value for s in _RECONCILE_RESOLVE_EXEC)}"
        )
    return plan_transition_order_evented(
        order=order,
        new_status=new_status,
        execution_event_type=exec_type,
        audit_event_type="order_reconcile_resolved",
        dedupe_key=f"reconcile_resolve:{order.id}:{new_status.value}",
        source=EventSource.BROKER_REST,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        reason=reason,
    )


# ---- close_session -------------------------------------------------------- #


@dataclass(frozen=True)
class SessionClosePlan:
    """Pure plan for closing a session (the store has already resolved and
    validated the session and fetched what will be touched).

    ``candidate_events`` is parallel to the ``open_candidates`` the store passed
    in (one per candidate, same order); ``order_events`` parallel to
    ``created_orders``. ``snapshots`` are the position rows to insert.
    ``close_event`` is the single ``session_closed`` summary. The store applies
    the actual mutations (EXPIRED / CANCELED / CLOSED + timestamps) with its own
    primitive, using ``now`` — kept storage-specific because one store mutates
    live objects in place and the other UPDATEs by id.
    """

    candidate_events: tuple[EventSpec, ...]
    order_events: tuple[EventSpec, ...]
    sell_intent_events: tuple[EventSpec, ...]
    snapshots: tuple[PositionSnapshot, ...]
    close_event: EventSpec


def plan_close_session(
    *,
    session: SessionRecord,
    open_candidates: list[Candidate],
    created_orders: list[Order],
    open_sell_intents: list[SellIntent],
    nonzero_positions: list[Position],
    now: datetime,
    actor: str = COMMAND_ACTOR_SYSTEM,
    spared_sell_intents: int = 0,
) -> SessionClosePlan:
    """Build the audit events + position snapshots for a session close (D-007 /
    D-013a). ``open_candidates`` are this session's PENDING/APPROVED candidates,
    ``created_orders`` its still-CREATED (never-submitted) **BUY** orders (a
    CREATED SELL is a protective/flatten exit that must remain submittable
    post-close, Phase 7 — the store filters those out), ``open_sell_intents`` its
    PENDING/APPROVED sell intents (expired like candidates), and
    ``nonzero_positions`` every symbol with a nonzero derived position. The
    counts drive the summary event.

    WO-0036 R2 (session-close event truth, gated): an intent backed by a LIVE
    (ACTIVE/FROZEN) envelope is **spared** — the stores exclude it from
    ``open_sell_intents`` BEFORE calling this planner, because expiring it
    would orphan a still-working mandate (the audit's P0). ``spared_sell_intents``
    is that excluded count, carried in the summary payload so the close event
    stays a complete account of the boundary.
    """

    candidate_events = tuple(
        EventSpec(
            "candidate_transition",
            message=f"candidate {candidate.status.value} -> expired (session close)",
            symbol=candidate.symbol,
            candidate_id=candidate.id,
            payload={
                "from": candidate.status.value,
                "to": "expired",
                "reason": "session_close",
            },
            session_id=session.id,
        )
        for candidate in open_candidates
    )
    order_events = tuple(
        EventSpec(
            "order_transition",
            message=f"order {order.symbol} created -> canceled (session close)",
            symbol=order.symbol,
            candidate_id=order.candidate_id,
            order_id=order.id,
            payload={"from": "created", "to": "canceled", "reason": "session_close"},
            session_id=session.id,
        )
        for order in created_orders
    )
    sell_intent_events = tuple(
        EventSpec(
            "sell_intent_transition",
            message=f"sell intent {si.status.value} -> expired (session close)",
            symbol=si.symbol,
            order_id=None,
            payload={
                "from": si.status.value,
                "to": "expired",
                "reason": "session_close",
            },
            session_id=session.id,
            correlation_id=si.id,
        )
        for si in open_sell_intents
    )
    snapshots = tuple(
        PositionSnapshot(
            session_id=session.id,
            symbol=pos.symbol,
            quantity=pos.quantity,
            cost_basis=pos.cost_basis,
            average_price=pos.average_price,
            captured_at=now,
        )
        for pos in nonzero_positions
    )
    close_event = EventSpec(
        "session_closed",
        message=(
            f"session closed ({len(open_candidates)} candidates expired, "
            f"{len(created_orders)} created orders canceled, "
            f"{len(open_sell_intents)} sell intents expired, "
            f"{len(snapshots)} positions snapshotted)"
        ),
        session_id=session.id,
        payload={
            "expired_candidates": len(open_candidates),
            "canceled_orders": len(created_orders),
            "expired_sell_intents": len(open_sell_intents),
            # WO-0036 R2: intents backed by a live envelope survive the close
            # (their mandate keeps working the exit across the boundary).
            "spared_sell_intents": spared_sell_intents,
            "position_snapshots": len(snapshots),
            # W2-SESS (REV-0013): who closed the session — so the audit can
            # attribute a manual close to the operator (default "system" for an
            # engine/automatic close). Mirrors the kill-switch / buys-paused /
            # cancel (UC-002) actor stamping.
            "actor": actor,
        },
    )
    return SessionClosePlan(
        candidate_events=candidate_events,
        order_events=order_events,
        sell_intent_events=sell_intent_events,
        snapshots=snapshots,
        close_event=close_event,
    )


# --------------------------------------------------------------------------- #
# Execution envelopes (ADR-010 / WO-0016)
# --------------------------------------------------------------------------- #


# ``EnvelopeTransitionError`` was relocated to ``app.store.base`` by WO-0030
# (alongside the ``StateStore`` envelope API it belongs to) and is re-imported
# above for compatibility, so ``from app.store.core import
# EnvelopeTransitionError`` keeps working for every existing caller.


# Outcomes, mirroring the order-transition planner's dispatch contract.
ENVELOPE_TRANSITION_REJECT = "reject"  # raise `error`
ENVELOPE_TRANSITION_NOOP = "noop"  # same-status re-request; nothing written
ENVELOPE_TRANSITION_APPLY = "apply"  # persist `envelope` + append `events`


# Which ExecutionEvent a genuine transition into each status appends. ACTIVE is
# resolved by edge, not status alone: APPROVED->ACTIVE is ENVELOPE_ACTIVATED,
# FROZEN->ACTIVE is ENVELOPE_RESUMED.
_ENVELOPE_EVENT_FOR_STATUS: dict[EnvelopeStatus, ExecutionEventType] = {
    EnvelopeStatus.APPROVED: ExecutionEventType.ENVELOPE_APPROVED,
    EnvelopeStatus.FROZEN: ExecutionEventType.ENVELOPE_FROZEN,
    EnvelopeStatus.COMPLETED: ExecutionEventType.ENVELOPE_COMPLETED,
    EnvelopeStatus.EXPIRED: ExecutionEventType.ENVELOPE_EXPIRED,
    EnvelopeStatus.EXHAUSTED: ExecutionEventType.ENVELOPE_EXHAUSTED,
    EnvelopeStatus.BREACHED: ExecutionEventType.ENVELOPE_BREACHED,
    EnvelopeStatus.SUPERSEDED: ExecutionEventType.ENVELOPE_SUPERSEDED,
    EnvelopeStatus.CANCELLED: ExecutionEventType.ENVELOPE_CANCELLED,
}

# Transitions that can only ever happen once per envelope get a deterministic
# dedupe key (idempotent on replay/retry — INV-5). FROZEN/RESUMED repeat
# legitimately, so they are not deduped (None).
_ENVELOPE_ONCE_ONLY: frozenset[EnvelopeStatus] = frozenset(
    {
        EnvelopeStatus.APPROVED,
        EnvelopeStatus.COMPLETED,
        EnvelopeStatus.EXPIRED,
        EnvelopeStatus.EXHAUSTED,
        EnvelopeStatus.BREACHED,
        EnvelopeStatus.SUPERSEDED,
        EnvelopeStatus.CANCELLED,
    }
)

# --------------------------------------------------------------------------- #
# WO-0036 R2 — the SellIntent↔Envelope lifecycle link (ADR-010 amendment)
# --------------------------------------------------------------------------- #

# A LIVE envelope is a standing mandate for its symbol/intent: ACTIVE (working)
# or FROZEN (kill-paused, resumable — its child may still rest at the venue).
# PENDING/APPROVED drafts are NOT live (they own nothing until first
# activation); every terminal status is not live. This one predicate drives the
# whole link: the per-symbol clash (INV-087), the session-close spare, the
# terminal release, and the exclusive-driver guards all key on it.
LIVE_ENVELOPE_STATUSES: frozenset[EnvelopeStatus] = frozenset(
    {EnvelopeStatus.ACTIVE, EnvelopeStatus.FROZEN}
)

# Terminal statuses that RELEASE the backing intent (the mandate is finished;
# the symbol becomes eligible for fresh protection). SUPERSEDED is deliberately
# absent: supersession transfers the mandate to the successor, which keeps the
# intent (plan_supersede_envelope enforces same intent + symbol).
ENVELOPE_RELEASING_TERMINALS: frozenset[EnvelopeStatus] = frozenset(
    {
        EnvelopeStatus.COMPLETED,
        EnvelopeStatus.EXPIRED,
        EnvelopeStatus.EXHAUSTED,
        EnvelopeStatus.BREACHED,
        EnvelopeStatus.CANCELLED,
    }
)

# Order statuses that MAY be live at the venue (past CREATED, not terminal).
# TIMEOUT_QUARANTINE is included on purpose: ADR-002 — an ambiguous submit MAY
# be working, so every safe-side consumer (flatten deferral, preemption skip)
# must treat it as live, never assume it is not.
VENUE_LIVE_ORDER_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.SUBMITTING,
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.TIMEOUT_QUARANTINE,
    }
)


def envelope_backing_intent_error(
    intent: Optional[SellIntent], *, symbol: str, envelope_id: str
) -> Optional[Exception]:
    """Why an envelope may NOT enter ACTIVE for this backing intent, or None.

    The R2 link's activation-side half, shared by BOTH stores and BOTH
    activation paths (``approve_envelope_activation`` and the generic
    ``transition_envelope`` → ACTIVE, first activation and resume): the
    backing intent must exist (a typo'd ``sell_intent_id`` must never mint an
    owner-less mandate — Codex PR#8 #8), its symbol must match, and it must be
    PENDING/APPROVED — an ORDERED intent is owned by the legacy single-order
    dispatch, and a terminal intent's mandate is finished. The store
    normalizes a PENDING intent to APPROVED atomically with the activation
    (the envelope approval IS the human approval of the exit).
    """

    if intent is None:
        return InvalidOrderError(
            f"envelope {envelope_id} references unknown sell intent — an "
            "envelope must be backed by a real intent (R2 lifecycle link)"
        )
    if intent.symbol != symbol:
        return InvalidOrderError(
            f"envelope {envelope_id} symbol {symbol} does not match its "
            f"backing sell intent's symbol {intent.symbol}"
        )
    if intent.status is SellIntentStatus.ORDERED:
        return EnvelopeTransitionError(
            f"sell intent {intent.id} is already ORDERED (legacy single-order "
            "dispatch owns it); an envelope on top would double-book the exit"
        )
    if intent.status not in (SellIntentStatus.PENDING, SellIntentStatus.APPROVED):
        return EnvelopeTransitionError(
            f"sell intent {intent.id} is {intent.status.value}; only a "
            "pending/approved intent can back an envelope activation"
        )
    return None


def _envelope_event(
    envelope: ExecutionEnvelope,
    event_type: ExecutionEventType,
    *,
    dedupe_key: Optional[str],
    payload: dict[str, Any],
    ts_event: Optional[datetime] = None,
) -> ExecutionEvent:
    """An envelope lifecycle ExecutionEvent. Every envelope lifecycle fact is a
    local single-writer engine decision — never a broker report — so provenance
    is uniformly ``ENGINE``/``LOCAL`` (ADR-008 convention). ``correlation_id``
    is the owning sell intent (D-020: one key reconstructs the whole exit)."""

    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=dedupe_key,
        ts_event=ts_event,
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        envelope_id=envelope.id,
        session_id=envelope.session_id,
        correlation_id=envelope.sell_intent_id,
        payload=payload,
    )


def envelope_created_event(
    envelope: ExecutionEnvelope, *, actor: str = COMMAND_ACTOR_SYSTEM
) -> ExecutionEvent:
    """``ENVELOPE_CREATED`` — snapshots the FULL bound set in the payload so the
    approved mandate is replayable from the log alone (ADR-010 §6), and stamps
    the commanding actor (operator-* for a human-created draft; the *approval
    flow* itself is WO-0017 — this is data plumbing only)."""

    return _envelope_event(
        envelope,
        ExecutionEventType.ENVELOPE_CREATED,
        dedupe_key=f"envelope:{envelope.id}:created",
        payload={
            "actor": actor,
            "sell_intent_id": envelope.sell_intent_id,
            "qty_ceiling": envelope.qty_ceiling,
            "floor_price": envelope.floor_price,
            "trail_distance_min": envelope.trail_distance_min,
            "trail_distance_max": envelope.trail_distance_max,
            "participation_rate_cap": envelope.participation_rate_cap,
            "aggressiveness": list(envelope.aggressiveness),
            "cooldown_floor_ms": envelope.cooldown_floor_ms,
            "cancel_replace_budget": envelope.cancel_replace_budget,
            "max_outstanding_children": envelope.max_outstanding_children,
            "expires_at": envelope.expires_at.isoformat(),
            "allowed_session_phases": [
                p.value for p in envelope.allowed_session_phases
            ],
            "expiry_disposition": envelope.expiry_disposition.value,
            "stale_data_disposition": envelope.stale_data_disposition.value,
            "supersedes_id": envelope.supersedes_id,
        },
    )


def envelope_draft_reason(envelope: ExecutionEnvelope) -> Optional[str]:
    """Why a draft is NOT creatable, or None. The model's own validators already
    hold the hard rails; this covers the *lifecycle* preconditions of create:
    a draft enters the machine at PENDING with untouched counters and no
    supersession linkage (only the atomic supersede op may set that)."""

    if envelope.status is not EnvelopeStatus.PENDING:
        return f"a new envelope must be PENDING, got {envelope.status.value}"
    if envelope.remaining_quantity != envelope.qty_ceiling:
        return "a new envelope's remaining_quantity must equal qty_ceiling"
    if envelope.replaces_used != 0:
        return "a new envelope's replaces_used must be 0"
    if envelope.superseded_by_id is not None:
        return "a new envelope cannot already be superseded"
    # Codex PR#8 F2: a fresh draft must not pre-declare EITHER supersession link.
    # `supersedes_id` set on an ordinary approve/create would activate a mandate
    # that LOOKS like an amendment without any of the atomic supersede op's
    # guarantees (predecessor validated + quantity-conserved + marked SUPERSEDED)
    # — amendments must route through `supersede_envelope`.
    if envelope.supersedes_id is not None:
        return "a new envelope cannot pre-declare supersession (use supersede)"
    return None


@dataclass(frozen=True)
class EnvelopeTransitionPlan:
    """Pure outcome of a single envelope status transition."""

    outcome: str
    envelope: Optional[ExecutionEnvelope] = None
    execution_event: Optional[ExecutionEvent] = None
    audit_event: Optional[EventSpec] = None
    error: Optional[Exception] = None


def plan_envelope_transition(
    envelope: ExecutionEnvelope,
    new_status: EnvelopeStatus,
    *,
    actor: str = COMMAND_ACTOR_SYSTEM,
    reason: Optional[str] = None,
    superseded_by_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> EnvelopeTransitionPlan:
    """Plan one status transition per ``ENVELOPE_TRANSITIONS`` (ADR-010 §3).

    Same-status is an idempotent no-op; an illegal edge rejects with
    :class:`EnvelopeTransitionError` and mutates nothing. A genuine transition
    updates status + ``updated_at`` + the entered status's timestamp
    (``ENVELOPE_TIMESTAMP``; ACTIVE restamps on every resume — documented
    "most recent activation") and appends the matching §6 ExecutionEvent.
    The single-ACTIVE-per-intent check is the STORE's job (it needs
    neighboring-envelope state a pure planner cannot see).
    """

    current = envelope.status
    if new_status is current:
        return EnvelopeTransitionPlan(ENVELOPE_TRANSITION_NOOP)
    if new_status not in ENVELOPE_TRANSITIONS.get(current, set()):
        return EnvelopeTransitionPlan(
            ENVELOPE_TRANSITION_REJECT,
            error=EnvelopeTransitionError(
                f"illegal envelope transition {current.value} -> {new_status.value}"
            ),
        )

    ts = now if now is not None else utcnow()
    update: dict[str, Any] = {"status": new_status, "updated_at": ts}
    ts_field = ENVELOPE_TIMESTAMP.get(new_status)
    if ts_field:
        update[ts_field] = ts
    if new_status is EnvelopeStatus.SUPERSEDED and superseded_by_id is not None:
        update["superseded_by_id"] = superseded_by_id
    updated = envelope.model_copy(update=update)

    if new_status is EnvelopeStatus.ACTIVE:
        event_type = (
            ExecutionEventType.ENVELOPE_RESUMED
            if current is EnvelopeStatus.FROZEN
            else ExecutionEventType.ENVELOPE_ACTIVATED
        )
        # First activation is once-only (APPROVED can never be re-entered);
        # resumes repeat, so they are not deduped.
        dedupe_key = (
            f"envelope:{envelope.id}:activated"
            if current is EnvelopeStatus.APPROVED
            else None
        )
    else:
        event_type = _ENVELOPE_EVENT_FOR_STATUS[new_status]
        dedupe_key = (
            f"envelope:{envelope.id}:{new_status.value}"
            if new_status in _ENVELOPE_ONCE_ONLY
            else None
        )

    payload: dict[str, Any] = {
        "from": current.value,
        "to": new_status.value,
        "actor": actor,
    }
    if reason is not None:
        payload["reason"] = reason
    if new_status is EnvelopeStatus.EXPIRED:
        # The approval-time mandatory choice this expiry now applies (§2/§6).
        payload["expiry_disposition"] = envelope.expiry_disposition.value
    if new_status is EnvelopeStatus.SUPERSEDED and superseded_by_id is not None:
        payload["superseded_by_id"] = superseded_by_id

    # F1 (WO-0035): the lifecycle event carries the transition's clock —
    # injected when the caller ticks, so BREACHED/EXPIRED/FROZEN stamps are
    # deterministic under replay instead of falling back to ts_init wall time.
    execution_event = _envelope_event(
        updated, event_type, dedupe_key=dedupe_key, payload=payload, ts_event=ts
    )
    audit_event = EventSpec(
        "envelope_transition",
        message=(
            f"envelope {envelope.symbol} {current.value} -> {new_status.value}"
            + (f" ({reason})" if reason else "")
        ),
        symbol=envelope.symbol,
        payload=payload,
        session_id=envelope.session_id,
        correlation_id=envelope.sell_intent_id,
    )
    return EnvelopeTransitionPlan(
        ENVELOPE_TRANSITION_APPLY,
        envelope=updated,
        execution_event=execution_event,
        audit_event=audit_event,
    )


# record_envelope_fill outcomes.
ENVELOPE_FILL_REJECT = "reject"
ENVELOPE_FILL_APPLY = "apply"


@dataclass(frozen=True)
class EnvelopeFillPlan:
    """Pure outcome of applying one (deduped) fill fact to an envelope.

    ``fill_event`` is the FILL ExecutionEvent to append **through the store's
    dedupe-aware writer**; the store MUST apply ``envelope`` (and the optional
    chained ``transition``) ONLY when the append actually wrote a new event —
    a dedupe hit means this fill was already counted (exactly-once decrement,
    INV-5)."""

    outcome: str
    error: Optional[Exception] = None
    envelope: Optional[ExecutionEnvelope] = None
    fill_event: Optional[ExecutionEvent] = None
    # A status transition mechanically chained to this fill (ACTIVE envelope
    # completing at remaining==0, or breaching on overfill), planned against
    # the post-decrement envelope. None when the fill only decrements.
    transition: Optional[EnvelopeTransitionPlan] = None


def plan_envelope_fill(
    envelope: ExecutionEnvelope,
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
) -> EnvelopeFillPlan:
    """Plan the ONLY operation that may decrement ``remaining_quantity``.

    A fill is a broker fact (``BROKER_REST``/``BROKER_AUTHORITATIVE`` by
    default; reconciliation-inferred callers override) and is recorded
    faithfully in EVERY envelope state that can physically receive one:

    * ``ACTIVE`` — decrement; remaining hits 0 → chain ``COMPLETED``; a fill
      EXCEEDING remaining is a broker-authoritative overfill of the hard qty
      ceiling → remaining floors at 0 and the envelope chains ``BREACHED``
      (recorded + frozen-for-human, never hidden — ADR-001 posture).
    * ``FROZEN`` — a resting order can fill before/while frozen: decrement,
      record, NO status change (completion happens on resume — the store's
      resume path auto-completes at remaining==0; a freeze is never exited by
      a fill). Overfill while FROZEN chains ``BREACHED`` exactly like ACTIVE
      (WO-0029A / ADR-010 §2-§3 amendment): a ceiling-violated mandate must
      never reach COMPLETED via resume; the order-level quarantine (ADR-001)
      still applies on top.
    * terminal — a late fill (e.g. cancel raced a fill): recorded + decremented
      + flagged ``late_fill``; terminal status never changes.
    * ``PENDING``/``APPROVED`` — structurally impossible (no child order can
      exist before activation): REJECT with :class:`InvalidFillError`.
    """

    bad = whole_count_reason(quantity)
    if bad is not None or quantity <= 0:
        return EnvelopeFillPlan(
            ENVELOPE_FILL_REJECT,
            error=InvalidFillError(
                f"envelope fill needs a positive whole quantity, got {quantity!r}"
            ),
        )
    # completeness-1 (REV-0023 Phase-A2): the shared D-019 value guard, exactly
    # as plan_append_fill applies it — a non-finite/non-positive price would
    # append a durable FILL event that permanently poisons
    # project_symbol_position for the symbol (ProjectionError on every later
    # get_position/close_session). Reject before anything is planned.
    value_reason = fill_value_reason(quantity, price)
    if value_reason is not None:
        return EnvelopeFillPlan(
            ENVELOPE_FILL_REJECT,
            error=InvalidFillError(
                f"invalid envelope fill for {envelope.symbol}: {value_reason}"
            ),
        )
    if envelope.status in (EnvelopeStatus.PENDING, EnvelopeStatus.APPROVED):
        return EnvelopeFillPlan(
            ENVELOPE_FILL_REJECT,
            error=InvalidFillError(
                f"envelope {envelope.id} is {envelope.status.value}: no child "
                "order can exist before activation, so a fill is not a "
                "recordable fact"
            ),
        )

    ts = now if now is not None else utcnow()
    remaining = envelope.remaining_quantity or 0
    overfill = quantity > remaining
    new_remaining = max(0, remaining - quantity)
    terminal = ENVELOPE_TRANSITIONS[envelope.status] == set()

    payload: dict[str, Any] = {
        "remaining_before": remaining,
        "remaining_after": new_remaining,
    }
    if overfill:
        payload["overfill"] = True
        payload["overfill_quantity"] = quantity - remaining
    if terminal:
        payload["late_fill"] = True

    updated = envelope.model_copy(
        update={"remaining_quantity": new_remaining, "updated_at": ts}
    )
    fill_event = ExecutionEvent(
        event_type=ExecutionEventType.FILL,
        source=source,
        authority=authority,
        dedupe_key=dedupe_key,
        # F1 (WO-0035): an explicit broker fill time wins; otherwise stamp the
        # injected clock (``ts``), never a divergent bare wall read here.
        ts_event=ts_event if ts_event is not None else ts,
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        quantity=quantity,
        price=price,
        order_id=order_id,
        envelope_id=envelope.id,
        session_id=session_id if session_id is not None else envelope.session_id,
        correlation_id=envelope.sell_intent_id,
        payload=payload,
    )

    transition: Optional[EnvelopeTransitionPlan] = None
    if envelope.status in (EnvelopeStatus.ACTIVE, EnvelopeStatus.FROZEN):
        if overfill:
            transition = plan_envelope_transition(
                updated,
                EnvelopeStatus.BREACHED,
                actor="engine",
                reason=(
                    f"broker-authoritative overfill: fill of {quantity} exceeded "
                    f"remaining {remaining} (hard qty ceiling "
                    f"{envelope.qty_ceiling})"
                ),
                now=ts,
            )
        elif new_remaining == 0 and envelope.status is EnvelopeStatus.ACTIVE:
            transition = plan_envelope_transition(
                updated,
                EnvelopeStatus.COMPLETED,
                actor="engine",
                reason="quantity ceiling fully filled",
                now=ts,
            )
    return EnvelopeFillPlan(
        ENVELOPE_FILL_APPLY,
        envelope=updated,
        fill_event=fill_event,
        transition=transition,
    )


@dataclass(frozen=True)
class EnvelopeSupersedePlan:
    """Pure outcome of the atomic amendment-by-supersession operation."""

    outcome: str  # ENVELOPE_TRANSITION_REJECT | ENVELOPE_TRANSITION_APPLY
    error: Optional[Exception] = None
    # Fully-updated rows to persist together (one atomic unit).
    old_envelope: Optional[ExecutionEnvelope] = None
    new_envelope: Optional[ExecutionEnvelope] = None
    # Events in append order: created(B), approved(B), superseded(A),
    # activated(B) — B never coexists ACTIVE with A inside the unit.
    execution_events: tuple[ExecutionEvent, ...] = ()
    audit_event: Optional[EventSpec] = None


def plan_supersede_envelope(
    old: ExecutionEnvelope,
    successor: ExecutionEnvelope,
    *,
    actor: str = COMMAND_ACTOR_SYSTEM,
    reason: Optional[str] = None,
    now: Optional[datetime] = None,
    working_order: Optional[Order] = None,
) -> EnvelopeSupersedePlan:
    """Plan ADR-010 §3 amendment-by-supersession as ONE atomic unit.

    ``successor`` is a fresh PENDING draft for the SAME intent+symbol (its
    bounds are the amendment; approval context arrives via ``actor`` — the
    approval *flow* is WO-0017, this is the storage semantics). The plan walks
    the successor through its legal chain PENDING→APPROVED→ACTIVE and moves the
    old envelope ACTIVE→SUPERSEDED, linked both ways, all applied by the store
    in one lock/tx hold so no window exists with two ACTIVE envelopes for one
    intent — and a concurrent second supersede loses at "old is no longer
    ACTIVE" (single-flight, W2-CAND shape).
    """

    if old.status is not EnvelopeStatus.ACTIVE:
        return EnvelopeSupersedePlan(
            ENVELOPE_TRANSITION_REJECT,
            error=EnvelopeTransitionError(
                f"only an ACTIVE envelope can be superseded; {old.id} is "
                f"{old.status.value}"
            ),
        )
    draft_bad = envelope_draft_reason(successor)
    if draft_bad is not None:
        return EnvelopeSupersedePlan(
            ENVELOPE_TRANSITION_REJECT, error=InvalidOrderError(draft_bad)
        )
    if successor.id == old.id:
        return EnvelopeSupersedePlan(
            ENVELOPE_TRANSITION_REJECT,
            error=InvalidOrderError("an envelope cannot supersede itself"),
        )
    if successor.sell_intent_id != old.sell_intent_id:
        return EnvelopeSupersedePlan(
            ENVELOPE_TRANSITION_REJECT,
            error=InvalidOrderError(
                "a successor envelope must belong to the same sell intent "
                f"({successor.sell_intent_id!r} != {old.sell_intent_id!r})"
            ),
        )
    if successor.symbol != old.symbol:
        return EnvelopeSupersedePlan(
            ENVELOPE_TRANSITION_REJECT,
            error=InvalidOrderError(
                "a successor envelope must keep the symbol "
                f"({successor.symbol!r} != {old.symbol!r})"
            ),
        )
    # WO-0027 (REV-0023 F6 / ADR-010 §3 amendment): supersession transfers
    # the mandate, it never widens or duplicates it.
    # (a) A LIVE working order at the venue blocks supersession outright —
    #     the store cannot venue-cancel, and activating a successor next to a
    #     resting predecessor order is exactly the double exposure INV-077
    #     forbids in substance. The amendment flow cancels first (staged
    #     CREATED orders are swept locally by the store in this same unit).
    # CREATED is deliberately NOT venue-live: a staged, never-submitted order
    # is local truth only — the stores sweep it in the same atomic unit as
    # the supersession (WO-0024 machinery). Anything that may rest at the
    # venue (SUBMITTING/SUBMITTED/PARTIALLY_FILLED/CANCEL_PENDING/quarantine)
    # blocks.
    working_live = working_order is not None and working_order.status not in (
        OrderStatus.CREATED,
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
    )
    if working_live:
        assert working_order is not None
        return EnvelopeSupersedePlan(
            ENVELOPE_TRANSITION_REJECT,
            error=EnvelopeTransitionError(
                f"envelope {old.id} has a live working order "
                f"({working_order.id}, {working_order.status.value}) at the "
                "venue; cancel it before superseding — a successor next to a "
                "resting predecessor order is double exposure (INV-077)"
            ),
        )
    # (b) Conservation: the successor's ceiling may not exceed what is LEFT
    #     of the mandate the human approved (read under the caller's lock —
    #     a fill racing the amendment shrinks remaining first and the
    #     amendment re-drafts). Widening requires cancel + fresh approval.
    old_remaining = old.remaining_quantity or 0
    if successor.qty_ceiling > old_remaining:
        return EnvelopeSupersedePlan(
            ENVELOPE_TRANSITION_REJECT,
            error=EnvelopeTransitionError(
                f"successor ceiling {successor.qty_ceiling} exceeds the "
                f"predecessor's remaining {old_remaining} — supersession "
                "conserves the mandate, it never widens it (INV-077)"
            ),
        )

    ts = now if now is not None else utcnow()
    linked = successor.model_copy(
        update={"supersedes_id": old.id, "session_id": successor.session_id}
    )
    created_ev = envelope_created_event(linked, actor=actor)

    approve = plan_envelope_transition(
        linked, EnvelopeStatus.APPROVED, actor=actor, reason=reason, now=ts
    )
    assert approve.outcome == ENVELOPE_TRANSITION_APPLY  # PENDING->APPROVED is legal
    assert approve.envelope is not None and approve.execution_event is not None

    supersede_old = plan_envelope_transition(
        old,
        EnvelopeStatus.SUPERSEDED,
        actor=actor,
        reason=reason,
        superseded_by_id=linked.id,
        now=ts,
    )
    assert supersede_old.outcome == ENVELOPE_TRANSITION_APPLY  # ACTIVE checked above
    assert (
        supersede_old.envelope is not None and supersede_old.execution_event is not None
    )

    activate = plan_envelope_transition(
        approve.envelope, EnvelopeStatus.ACTIVE, actor=actor, now=ts
    )
    assert activate.outcome == ENVELOPE_TRANSITION_APPLY  # APPROVED->ACTIVE is legal
    assert activate.envelope is not None and activate.execution_event is not None

    audit_event = EventSpec(
        "envelope_superseded",
        message=(
            f"envelope for {old.symbol} superseded: {old.id} -> {linked.id}"
            + (f" ({reason})" if reason else "")
        ),
        symbol=old.symbol,
        payload={
            "old_envelope_id": old.id,
            "new_envelope_id": linked.id,
            "actor": actor,
            **({"reason": reason} if reason else {}),
        },
        session_id=old.session_id,
        correlation_id=old.sell_intent_id,
    )
    return EnvelopeSupersedePlan(
        ENVELOPE_TRANSITION_APPLY,
        old_envelope=supersede_old.envelope,
        new_envelope=activate.envelope,
        execution_events=(
            created_ev,
            approve.execution_event,
            supersede_old.execution_event,
            activate.execution_event,
        ),
        audit_event=audit_event,
    )


# --------------------------------------------------------------------------- #
# Envelope engine seam — write-time validation + divergence (WO-0019, D-3)
# --------------------------------------------------------------------------- #


class EnvelopeActionPausedError(ValueError):
    """The envelope has a working order in TIMEOUT_QUARANTINE: no further
    actions may be planned or written until the quarantine resolves (ADR-002 —
    never blind-re-replace an order whose fate is unknown)."""


STAGE_DIVERGENCE = "divergence"  # plan/write disagreement: frozen + event, no order
STAGE_STAGED = "staged"  # order minted + accounting committed; drive the venue leg
STAGE_REFUSED_STALE = "refused_stale"  # WO-0029A (ADR-010 §5 amendment): the
# plan's FACTS went stale between decide and write (a fill shrank remaining,
# order liveness flipped) — refused + evented, NO freeze; the policy replans
# next tick. Only same-inputs validator disagreement is a DEFECT.

# Rails whose write-time verdict can differ from plan time because the WORLD
# changed (state-dependent), vs rails deterministic in (envelope constants,
# action, the shared injected now, history) — where disagreement means the
# validators themselves disagree (DEFECT). reduce_only is deliberately in the
# defect/freeze set: it is not a plan/write comparison at all (the policy
# cannot see position) — a mandate the book cannot cover needs a human
# (INV-084).
_STALE_REFUSAL_RAILS = frozenset({"qty_ceiling", "structural"})


@dataclass(frozen=True)
class EnvelopeActionStagePlan:
    """Pure outcome of staging one envelope PlannedAction (WO-0019).

    ``STAGE_STAGED``: ``order`` + ``action_event`` + ``audit_event`` commit as
    ONE atomic unit — the ENVELOPE_ACTION event IS the budget/cooldown
    accounting, so it can never desynchronize from the order it paid for.
    ``STAGE_DIVERGENCE``: apply ``freeze`` then append ``divergence_event`` +
    ``audit_event`` in the same unit; NOTHING else is written and the caller
    must make ZERO venue calls (ADR-010 §5, D-3).
    ``STAGE_REFUSED_STALE`` (WO-0029A): append ``action_event`` (an
    ENVELOPE_ACTION with payload action="refused_stale" — never counted by
    budget/cooldown accounting) + ``audit_event``; no order, no freeze, zero
    venue calls; the policy replans from fresh facts next tick.
    """

    outcome: str
    error: Optional[Exception] = None
    order: Optional[Order] = None
    action_event: Optional[ExecutionEvent] = None
    audit_event: Optional[EventSpec] = None
    freeze: Optional[EnvelopeTransitionPlan] = None
    divergence_event: Optional[ExecutionEvent] = None


def _divergence(
    envelope: ExecutionEnvelope,
    *,
    rail: str,
    detail: str,
    action_payload: dict[str, Any],
    snapshot_fingerprint: str,
    now: datetime,
) -> EnvelopeActionStagePlan:
    freeze = plan_envelope_transition(
        envelope,
        EnvelopeStatus.FROZEN,
        actor="engine",
        reason=f"plan_divergence:{rail}",
        now=now,
    )
    assert freeze.outcome == ENVELOPE_TRANSITION_APPLY  # envelope is ACTIVE here
    assert freeze.envelope is not None
    divergence_event = _envelope_event(
        freeze.envelope,
        ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE,
        dedupe_key=None,
        payload={
            "rail": rail,
            "detail": detail,
            "snapshot_fingerprint": snapshot_fingerprint,
            **action_payload,
        },
    )
    audit_event = EventSpec(
        "envelope_plan_divergence",
        message=(
            f"DEFECT: plan/write validator disagreement on {envelope.symbol} "
            f"({rail}) — envelope frozen, no venue call"
        ),
        symbol=envelope.symbol,
        payload={"rail": rail, "detail": detail, "envelope_id": envelope.id},
        session_id=envelope.session_id,
        correlation_id=envelope.sell_intent_id,
    )
    return EnvelopeActionStagePlan(
        STAGE_DIVERGENCE,
        freeze=freeze,
        divergence_event=divergence_event,
        audit_event=audit_event,
    )


def _refused_stale(
    envelope: ExecutionEnvelope,
    *,
    rail: str,
    detail: str,
    action_payload: dict[str, Any],
    snapshot_fingerprint: str,
) -> EnvelopeActionStagePlan:
    """WO-0029A: a benign stale-plan refusal — the world changed between
    decide and write. Evented distinctly, envelope untouched."""

    refusal_event = _envelope_event(
        envelope,
        ExecutionEventType.ENVELOPE_ACTION,
        dedupe_key=None,
        payload={
            **action_payload,
            "action": "refused_stale",
            "refused_action": action_payload.get("action"),
            "rail": rail,
            "detail": detail,
            "snapshot_fingerprint": snapshot_fingerprint,
        },
    )
    audit_event = EventSpec(
        "envelope_action_refused_stale",
        message=(
            f"stale plan refused on {envelope.symbol} ({rail}) — facts "
            "changed between plan and write; policy replans next tick"
        ),
        symbol=envelope.symbol,
        payload={"rail": rail, "detail": detail, "envelope_id": envelope.id},
        session_id=envelope.session_id,
        correlation_id=envelope.sell_intent_id,
    )
    return EnvelopeActionStagePlan(
        STAGE_REFUSED_STALE,
        action_event=refusal_event,
        audit_event=audit_event,
    )


def plan_stage_envelope_action(
    envelope: ExecutionEnvelope,
    action: PlannedAction,
    *,
    history: Sequence[ExecutionEvent],
    working_order: Optional[Order],
    session_id: Optional[str],
    snapshot_fingerprint: str,
    actor: str,
    now: Optional[datetime] = None,
    current_position: Optional[int] = None,
) -> EnvelopeActionStagePlan:
    """Stage one PlannedAction: the WRITE-TIME half of D-3.

    Re-runs the SAME :func:`app.sellside.policy.validate_action` the policy
    ran at plan time (two mandatory call sites). Any disagreement — a rail
    violation the plan claimed was valid, or a structural mismatch (REPRICE
    with no working order / SUBMIT over a live one) — is a software-defect
    signal: freeze + ENVELOPE_PLAN_DIVERGENCE (ADR-010 §5), never a venue
    call. On pass, mints the SELL Order (CREATED; XOR origin = the envelope's
    sell intent; ``replaces_order_id`` links the reprice chain) plus the
    ENVELOPE_ACTION event carrying envelope_id, snapshot fingerprint and the
    clamped params (§6).
    """

    ts = now if now is not None else utcnow()
    action_payload: dict[str, Any] = {
        "action": action.kind.value,
        "limit_price": action.limit_price,
        "quantity": action.quantity,
        "tranche": action.tranche,
        "stop_triggered": action.stop_triggered,
        "urgency": action.urgency,
        "regime": action.regime.value if action.regime is not None else None,
        "working_stop": action.working_stop,
        "atr": action.atr,
        "clamps": [
            {"field": c.field, "computed": c.computed, "clamped_to": c.clamped_to}
            for c in action.clamps
        ],
    }

    if envelope.status is not EnvelopeStatus.ACTIVE:
        return EnvelopeActionStagePlan(
            STAGE_DIVERGENCE,
            error=EnvelopeTransitionError(
                f"envelope {envelope.id} is {envelope.status.value}: no action "
                "may be staged"
            ),
        )

    working_live = working_order is not None and working_order.status not in (
        OrderStatus.FILLED,
        OrderStatus.CANCELED,
        OrderStatus.REJECTED,
    )
    if action.kind is _SellsideActionKind.REPRICE:
        if (
            not working_live
            or working_order is None
            or (working_order.broker_order_id is None)
        ):
            # Order liveness is state that legitimately changes between plan
            # and write (a fill landed) — benign stale refusal (WO-0029A).
            return _refused_stale(
                envelope,
                rail="structural",
                detail="REPRICE planned but no live working order with a venue id",
                action_payload=action_payload,
                snapshot_fingerprint=snapshot_fingerprint,
            )
    elif working_live:
        return _refused_stale(
            envelope,
            rail="structural",
            detail="SUBMIT planned over a live working order (max outstanding=1)",
            action_payload=action_payload,
            snapshot_fingerprint=snapshot_fingerprint,
        )

    violation = _sellside_validate_action(envelope, action, history=history, now=ts)
    if violation is not None:
        if violation.rail in _STALE_REFUSAL_RAILS:
            return _refused_stale(
                envelope,
                rail=violation.rail,
                detail=violation.detail,
                action_payload=action_payload,
                snapshot_fingerprint=snapshot_fingerprint,
            )
        return _divergence(
            envelope,
            rail=violation.rail,
            detail=violation.detail,
            action_payload=action_payload,
            snapshot_fingerprint=snapshot_fingerprint,
            now=ts,
        )
    # WO-0026 (REV-0023 F1): reduce-only is a §2 HARD rail — the SELL must
    # never exceed the live fill-derived position (single-writer truth). The
    # stores read their own projection under the SAME lock/transaction as
    # this plan's application, so a fill racing the stage cannot slip an
    # oversell through (the D-3 shape, extended to position). Checked AFTER
    # the mandate rails: the envelope's own bounds adjudicate first, and
    # reduce_only fires only when the mandate says yes but the book says no.
    if current_position is not None and action.quantity > max(0, current_position):
        return _divergence(
            envelope,
            rail="reduce_only",
            detail=(
                f"SELL {action.quantity} exceeds live position "
                f"{max(0, current_position)}"
            ),
            action_payload=action_payload,
            snapshot_fingerprint=snapshot_fingerprint,
            now=ts,
        )

    if action.kind is _SellsideActionKind.REPRICE:
        assert working_order is not None  # narrowed by the structural gate above
        replaces_id: Optional[str] = working_order.id
    else:
        replaces_id = None
    order = Order(
        sell_intent_id=envelope.sell_intent_id,
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=action.quantity,
        limit_price=action.limit_price,
        replaces_order_id=replaces_id,
        session_id=session_id,
    )
    action_event = ExecutionEvent(
        event_type=ExecutionEventType.ENVELOPE_ACTION,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=ts,  # the DECISION clock — redrive's staleness ceiling and
        # the cooldown rail read this deterministically (WO-0024)
        symbol=envelope.symbol,
        side=OrderSide.SELL,
        quantity=action.quantity,
        price=action.limit_price,
        order_id=order.id,
        envelope_id=envelope.id,
        session_id=session_id,
        correlation_id=envelope.sell_intent_id,
        payload={
            **action_payload,
            "snapshot_fingerprint": snapshot_fingerprint,
            "actor": actor,
            "replaces_order_id": order.replaces_order_id,
        },
    )
    audit_event = EventSpec(
        "envelope_action_staged",
        message=(
            f"envelope action staged: {action.kind.value} {action.quantity} "
            f"{envelope.symbol} @ {action.limit_price}"
        ),
        symbol=envelope.symbol,
        order_id=order.id,
        payload={"envelope_id": envelope.id, **action_payload},
        session_id=session_id,
        correlation_id=envelope.sell_intent_id,
    )
    return EnvelopeActionStagePlan(
        STAGE_STAGED,
        order=order,
        action_event=action_event,
        audit_event=audit_event,
    )


@dataclass(frozen=True)
class EnvelopeActionStageResult:
    """What a store's ``stage_envelope_action`` returns (both stores)."""

    outcome: str  # STAGE_STAGED | STAGE_DIVERGENCE
    envelope: ExecutionEnvelope
    order: Optional[Order] = None
    working_order: Optional[Order] = None
