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
from typing import Any, Optional

from app.models import Fill, Order, OrderSide, utcnow
from app.position import NegativePositionError, would_go_negative
from app.store.base import InvalidFillError, UnknownEntityError
from app.store.validation import fill_order_match_reason, fill_value_reason


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
