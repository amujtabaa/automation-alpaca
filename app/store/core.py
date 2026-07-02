"""Shared store *orchestration* — the domain-core layer.

``app/store/validation.py`` already extracts the pure input *predicates* both
stores share; ``app/store/transitions.py`` the state-machine tables;
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
    SessionRecord,
    utcnow,
)
from app.position import NegativePositionError, would_go_negative
from app.store.base import (
    CandidateTransitionError,
    InvalidFillError,
    InvalidOrderError,
    OrderIntentBlockedError,
    OrderTransitionError,
    UnknownEntityError,
)
from app.store.transitions import ORDER_TIMESTAMP, ORDER_TRANSITIONS
from app.store.validation import (
    fill_order_match_reason,
    fill_value_reason,
    filled_quantity_reason,
    limit_price_reason,
    order_intent_block_reason,
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
    set (the kill-switch/pause block writes an audit row; the not-approved and
    invalid-qty/price rejections write nothing, matching the original stores).
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
    *, candidate: Candidate, session: Optional[SessionRecord]
) -> CreateOrderPlan:
    """The shared validation cascade + order construction for the candidate→order
    dispatch. ``candidate`` is known to exist and *not* already ORDERED (the store
    handles those first). ``session`` is the candidate's own originating session.
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
    """

    current = order.status
    status_changed = new_status is not current
    if status_changed and new_status not in ORDER_TRANSITIONS.get(current, set()):
        return OrderTransitionPlan(
            ORDER_TRANSITION_REJECT,
            error=OrderTransitionError(
                f"illegal order transition {current.value} -> {new_status.value}"
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
    snapshots: tuple[PositionSnapshot, ...]
    close_event: EventSpec


def plan_close_session(
    *,
    session: SessionRecord,
    open_candidates: list[Candidate],
    created_orders: list[Order],
    nonzero_positions: list[Position],
    now: datetime,
) -> SessionClosePlan:
    """Build the audit events + position snapshots for a session close (D-007 /
    D-013a). ``open_candidates`` are this session's PENDING/APPROVED candidates,
    ``created_orders`` its still-CREATED (never-submitted) orders, and
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
            f"{len(snapshots)} positions snapshotted)"
        ),
        session_id=session.id,
        payload={
            "expired_candidates": len(open_candidates),
            "canceled_orders": len(created_orders),
            "position_snapshots": len(snapshots),
        },
    )
    return SessionClosePlan(
        candidate_events=candidate_events,
        order_events=order_events,
        snapshots=snapshots,
        close_event=close_event,
    )
