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

from typing import Optional

from app.models import Candidate, Order, OrderSide


def fill_value_reason(quantity: int, price: float) -> Optional[str]:
    """Reject a fill whose intrinsic values would corrupt position truth.

    A non-positive quantity (a negative buy is a negative position) or a
    non-positive price (negative cost basis / average price) directly violates
    the derived-position invariant.
    """

    if quantity <= 0:
        return "non_positive_quantity"
    if price <= 0:
        return "non_positive_price"
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
