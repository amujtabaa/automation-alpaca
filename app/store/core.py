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
from typing import Any, Optional

from app.models import (
    Candidate,
    CandidateStatus,
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
    SessionRecord,
    utcnow,
)
from app.position import NegativePositionError, would_go_negative
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    CLAIM_SKIPPED,
    CandidateTransitionError,
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
from app.transitions import ORDER_TIMESTAMP, ORDER_TRANSITIONS
from app.policy import (
    fill_order_match_reason,
    fill_value_reason,
    filled_quantity_reason,
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
FILL_REJECT = "reject"        # write `event`; raise `error`
FILL_DUPLICATE = "duplicate"  # write `event`; return a FillAppendResult("duplicate", None, event)
FILL_APPEND = "append"        # atomically write `fill` (+dedup) and `event`; return "appended"


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

    # 5) Long-only integrity: a sell can never drive quantity negative.
    if would_go_negative(current_quantity, side, quantity):
        return FillPlan(
            FILL_REJECT,
            EventSpec(
                "fill_rejected_negative_position",
                message=(
                    f"sell of {quantity} {symbol} rejected: exceeds current "
                    f"quantity {current_quantity}"
                ),
                symbol=symbol,
                candidate_id=order.candidate_id,
                order_id=order_id,
                payload={"attempted_sell": quantity, "current_quantity": current_quantity},
                session_id=session_id,
            ),
            error=NegativePositionError(symbol, current_quantity, quantity),
        )

    # 6) Append. Build the fill row + its audit event; the store writes both
    #    atomically (a failed audit event must not leave a position-changing fill
    #    with no fill_appended row and a poisoned dedup set).
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
    return FillPlan(
        FILL_APPEND,
        EventSpec(
            "fill_appended",
            message=f"fill {fill.quantity} {symbol} @ {fill.price}",
            symbol=symbol,
            candidate_id=order.candidate_id,
            order_id=order_id,
            fill_id=fill.id,
            payload={"side": side.value, "quantity": quantity, "price": price},
            session_id=session_id,
        ),
        fill=fill,
    )


# ---- create_order_for_candidate ------------------------------------------- #

# CreateOrderPlan.outcome values:
CREATE_ORDER_REJECT = "reject"  # write `reject_event` (block case only); raise `error`
CREATE_ORDER_CREATE = "create"  # write `order` + candidate ORDERED transition + `events`


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
    """

    outcome: str
    error: Optional[Exception] = None
    reject_event: Optional[EventSpec] = None
    order: Optional[Order] = None
    events: tuple[EventSpec, ...] = ()


def plan_create_order_for_candidate(
    *,
    candidate: Candidate,
    session: Optional[SessionRecord],
    exposure_before_order: float = 0.0,
    risk_limits: RiskLimits = RiskLimits(),
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


def sell_intent_is_active(intent: SellIntent, order: Optional[Order]) -> bool:
    """Whether a sell intent is still 'in flight' for the single-flight dedup /
    ``active_sell_intent_for``. Active = ``pending``/``approved`` (not yet
    ordered), or ``ordered`` with an Order still in a non-terminal status.
    ``rejected``/``expired`` intents, and ``ordered`` intents whose order reached
    a terminal state (filled/canceled/rejected), are inactive — the symbol is
    eligible for a fresh protective intent (the residual re-evaluation path)."""

    if intent.status in (SellIntentStatus.PENDING, SellIntentStatus.APPROVED):
        return True
    if intent.status is SellIntentStatus.ORDERED:
        return order is not None and order.status not in _TERMINAL_ORDER_STATUSES
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
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=SellIntentTransitionError(
                f"cannot order sell intent {intent.id} in status "
                f"{intent.status.value}; must be approved"
            ),
        )

    qty = intent.target_quantity
    if qty is None or qty <= 0:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=InvalidOrderError(
                f"sell intent {intent.id} has no positive target_quantity"
            ),
        )
    # Never a short (Rule 7 / long-only): the exit cannot exceed the live
    # position. Re-checked here against the freshly-read quantity so a race that
    # reduced the position (another fill) between approve and order cannot oversell.
    if qty > live_position_quantity:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=InvalidOrderError(
                f"sell intent {intent.id} target_quantity {qty} exceeds the live "
                f"{intent.symbol} position quantity {live_position_quantity} "
                f"(would create a short)"
            ),
        )

    # Order-type/price coherence (Rule 12 exit types): a LIMIT sell needs a
    # finite positive limit; a MARKET sell must carry NO limit price. Do NOT run
    # limit_price_reason unconditionally (it would reject the MARKET exit path).
    if order_type is OrderType.LIMIT:
        bad_price = limit_price_reason(limit_price)
        if bad_price is not None:
            return CreateOrderPlan(
                CREATE_ORDER_REJECT,
                error=InvalidOrderError(
                    f"limit sell for intent {intent.id} needs a valid limit_price "
                    f"({bad_price})"
                ),
            )
    elif limit_price is not None:
        return CreateOrderPlan(
            CREATE_ORDER_REJECT,
            error=InvalidOrderError(
                f"{order_type.value} sell for intent {intent.id} must not carry a "
                f"limit_price (got {limit_price!r})"
            ),
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


def recovery_status_event(
    prev_status: str, new_status: Optional[str]
) -> Optional[str]:
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


def plan_claim_order_for_submission(
    *,
    order: Optional[Order],
    own_session: Optional[SessionRecord],
    current_session: Optional[SessionRecord],
) -> ClaimPlan:
    """Decide whether a ``CREATED`` order may be claimed for submission.

    ``own_session`` is the order's originating session (D-013a: a held order is
    gated against its OWN session, not merely the live one, so a kill-switched
    order from a prior session can't slip through after a date rollover mints a
    fresh permissive session). ``current_session`` is the live session, checked
    as a process-wide emergency stop. The store calls this under its lock, so
    the control state read here cannot change between the decision and the
    ``CREATED → SUBMITTING`` write the store then applies.
    """

    if order is None or order.status is not OrderStatus.CREATED:
        # No longer submittable: a session close cancelled it, it was already
        # claimed, or it never existed. Nothing to do.
        return ClaimPlan(CLAIM_SKIPPED)

    hold = session_submission_block_reason(own_session)
    if hold is None:
        current_block = order_intent_block_reason(current_session)
        if current_block is not None:
            hold = f"current_{current_block}"
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
ORDER_TRANSITION_NOOP = "noop"      # nothing changed; store returns the order unchanged
ORDER_TRANSITION_APPLY = "apply"    # persist `order` (fully updated) + write `event`


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

    qty_changed = filled_quantity is not None and filled_quantity != order.filled_quantity
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
            payload={"from": current.value, "to": new_status.value},
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
) -> SessionClosePlan:
    """Build the audit events + position snapshots for a session close (D-007 /
    D-013a). ``open_candidates`` are this session's PENDING/APPROVED candidates,
    ``created_orders`` its still-CREATED (never-submitted) **BUY** orders (a
    CREATED SELL is a protective/flatten exit that must remain submittable
    post-close, Phase 7 — the store filters those out), ``open_sell_intents`` its
    PENDING/APPROVED sell intents (expired like candidates), and
    ``nonzero_positions`` every symbol with a nonzero derived position. The
    counts drive the summary event.
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
            "position_snapshots": len(snapshots),
        },
    )
    return SessionClosePlan(
        candidate_events=candidate_events,
        order_events=order_events,
        sell_intent_events=sell_intent_events,
        snapshots=snapshots,
        close_event=close_event,
    )
