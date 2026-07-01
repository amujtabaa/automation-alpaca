"""Pure input-validation predicates shared by both StateStore implementations.

These functions encode the D-010 input-boundary rules in *one* place so
``InMemoryStateStore`` and ``SqliteStateStore`` reject identical inputs — the
parity the ``any_store`` tests assert. They are pure (no IO, no async, no
state): each returns a short, greppable *reason code* string when the input is
invalid, or ``None`` when it is acceptable. The stores translate a reason into
the appropriate audit event + ``StoreError`` subclass; keeping the *decision*
here and the *event/raise wiring* in each store avoids the one thing that would
break parity — the two stores drifting on what counts as invalid.

The reason codes are also written into rejection-event payloads, so the audit
log says *why* a fill/order was rejected, not just that it was.
"""

from __future__ import annotations

import math
from typing import Optional

from app.models import Candidate, Order, OrderSide, SessionRecord, SessionStatus


def order_intent_block_reason(
    session: Optional[SessionRecord],
) -> Optional[str]:
    """Why new order intent is blocked for ``session``, or ``None`` if allowed.

    Rule 8 safety controls: the kill switch blocks *all* new order intent; buys
    paused blocks new BUY intent (beta orders are long-only buys, so it blocks
    them too). Shared by both stores and the monitoring loop so "is trading
    stopped" is decided in exactly one place.
    """

    if session is None:
        return None
    if session.kill_switch:
        return "kill_switch"
    if session.buys_paused:
        return "buys_paused"
    return None


def session_submission_block_reason(
    session: Optional[SessionRecord],
) -> Optional[str]:
    """Why a CREATED order from ``session`` must NOT be submitted, or ``None``.

    A held order is gated against its **own** originating session (D-013a), not
    merely the live/current one: ``get_current_session`` auto-mints a fresh,
    permissive session on UTC date rollover, so gating submission only on the
    current session let a kill-switched order from a prior session slip through
    to the broker (a Rule 8 bypass). This predicate adds the closed-session case
    that ``order_intent_block_reason`` does not cover — a closed session blocks
    *new* submissions, while already-submitted orders still reconcile to a
    terminal state (D-011). An unknown session is treated as blocked, never
    submitted.
    """

    if session is None:
        return "unknown_session"
    if session.status is SessionStatus.CLOSED:
        return "session_closed"
    return order_intent_block_reason(session)


def fill_value_reason(quantity: int, price: float) -> Optional[str]:
    """Reject a fill whose intrinsic values would corrupt position truth.

    A non-finite (``NaN``/``Infinity``) or non-positive quantity or price
    directly violates the derived-position invariant — ``NaN``/``Inf`` slip past
    a bare ``<= 0`` check (``nan <= 0`` and ``inf <= 0`` are both ``False``) and
    would poison ``cost_basis``/``average_price``, so they are rejected first.
    """

    if not math.isfinite(quantity):
        return "non_finite_quantity"
    if not math.isfinite(price):
        return "non_finite_price"
    if quantity <= 0:
        return "non_positive_quantity"
    if price <= 0:
        return "non_positive_price"
    return None


def limit_price_reason(limit_price: Optional[float]) -> Optional[str]:
    """Reject a missing/non-finite/non-positive limit price for a LIMIT order.

    A LIMIT order must carry a real, positive price; ``None``, ``NaN``, ``Inf``,
    zero, and negative are all rejected (the ``NaN``/``Inf`` cases would
    otherwise pass a bare ``<= 0`` guard).
    """

    if limit_price is None:
        return "missing_limit_price"
    if not math.isfinite(limit_price):
        return "non_finite_limit_price"
    if limit_price <= 0:
        return "non_positive_limit_price"
    return None


def fill_order_match_reason(
    order: Order,
    symbol: str,
    side: OrderSide,
    quantity: int,
    prior_filled_quantity: int,
) -> Optional[str]:
    """Reject a fill that is inconsistent with the order it claims to fill.

    ``symbol`` must already be normalized. ``prior_filled_quantity`` is the sum
    of quantities of fills already recorded against this order (excluding this
    one and any duplicate). Cumulative fill quantity may not exceed the order's
    quantity. Side must match — beta models no correction/reversal fill.
    """

    if order.symbol != symbol:
        return "symbol_mismatch"
    if OrderSide(order.side) is not OrderSide(side):
        return "side_mismatch"
    if prior_filled_quantity + quantity > order.quantity:
        return "cumulative_exceeds_order_quantity"
    return None


def order_candidate_match_reason(
    candidate: Candidate, order_symbol: str
) -> Optional[str]:
    """Reject an order whose symbol does not match its candidate.

    ``order_symbol`` must already be normalized. Existence of the candidate is
    checked by the caller (a missing candidate is ``UnknownEntityError``). The
    approved-only rule is intentionally *not* enforced here — it belongs to
    Phase 3's Approval Gate (see D-010 / Fix 4).
    """

    if candidate.symbol != order_symbol:
        return "symbol_mismatch"
    return None


def filled_quantity_reason(order: Order, new_filled_quantity: int) -> Optional[str]:
    """Reject an out-of-range or backward ``filled_quantity`` on an order.

    Must satisfy ``0 <= new_filled_quantity <= order.quantity`` and be
    monotonic non-decreasing relative to the order's current
    ``filled_quantity`` (no broker-correction path exists in beta). Equality is
    allowed (it is handled upstream as a no-op).
    """

    if new_filled_quantity < 0:
        return "negative_filled_quantity"
    if new_filled_quantity > order.quantity:
        return "filled_quantity_exceeds_order_quantity"
    if new_filled_quantity < order.filled_quantity:
        return "filled_quantity_decreased"
    return None
