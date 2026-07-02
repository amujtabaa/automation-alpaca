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
from typing import Optional, Sequence

from app.models import (
    Candidate,
    Fill,
    Order,
    OrderSide,
    Position,
    SessionRecord,
    SessionStatus,
)
from app.store.transitions import ORDER_TRANSITIONS

# An order still in one of these statuses represents live risk: it could fill
# at any moment, so it counts toward exposure exactly like an already-filled
# position. Everything else (FILLED/CANCELED/REJECTED) is terminal and settled.
# Derived from app/store/transitions.py's ORDER_TRANSITIONS rather than
# hand-copied, so the two can never silently drift apart: a status is
# non-terminal exactly when it has at least one legal outgoing transition.
NON_TERMINAL_ORDER_STATUSES = frozenset(
    status for status, transitions in ORDER_TRANSITIONS.items() if transitions
)


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


# --------------------------------------------------------------------------- #
# Phase 6 — Capital Intelligence Layer (CAPI) pre-trade risk gate (D-016)
# --------------------------------------------------------------------------- #


def existing_exposure(
    positions: Sequence[Position],
    open_orders: Sequence[Order],
    fills: Sequence[Fill] = (),
) -> float:
    """Current dollar exposure *before* the order being evaluated: every
    position's cost basis, plus the notional of every non-terminal order's
    remaining (unfilled) quantity.

    Local-derived only (D-016): no live broker/market-data call. Position
    exposure uses cost basis, not mark-to-market — beta explicitly defers
    unrealized P/L elsewhere (``docs/03_UI_WORKFLOW.md``'s Position Monitor),
    and cost basis is exactly what the store already has without a new
    dependency on live prices. A flat (fully-sold) position's cost_basis is
    ``0`` by the folding formula (``docs/02``), so no explicit quantity filter
    is needed here — summing every position is already correct.

    This is a *directional* approximation, not a neutral one: cost basis
    over-counts a position that has since dropped in value (the cap is
    conservative — it binds sooner than a mark-to-market total would) and
    under-counts one that has risen (the cap is permissive — it binds later
    than mark-to-market would). Because this strategy set targets momentum
    winners, the realistic failure mode is the permissive direction: a
    position that ran up since entry reads as less exposure than it actually
    represents, letting a new order through that a mark-to-market total would
    have blocked. Acceptable for beta's gate-and-reject cap, but worth knowing
    before leaning on this number for anything more precise.

    Order exposure is priced at each order's own ``limit_price`` (``None`` only
    for a non-LIMIT order type, which beta never creates — treated as ``0`` to
    stay total, not raise, since this is a read-only aggregate, not a
    validation gate itself).

    ``fills`` — every fill currently in the store, not filtered to
    ``open_orders`` — is used to derive each order's *actual* filled quantity
    directly from the append-only fill table, in preference to trusting
    ``Order.filled_quantity``. This matters because "append a fill" and "update
    the order's filled_quantity/status to match" are two *separate* atomic
    operation groups (``docs/02_DATA_AND_PERSISTENCE.md`` lists "fill append +
    duplicate-fill check + audit event" and "order status transition + audit
    event" as distinct groups on purpose — see ``app/monitoring.py``'s
    ``_apply_update``, which always calls ``append_fill`` and only afterward,
    as a separate call, ``transition_order``). Between those two calls there is
    a real window where a fill has already moved a position's cost basis but
    ``Order.filled_quantity`` hasn't caught up yet; reading the stale field
    there would double-count the just-filled shares (once via the position,
    again via the order's not-yet-decremented "remaining" notional). An order
    with no recorded fills falls back to its own ``filled_quantity`` (``0`` for
    a fresh order, identical to the pre-fix behavior), so omitting ``fills``
    entirely (the default, used by callers with no fill table to hand — e.g.
    the Hypothesis property tests below) reproduces the old behavior exactly.
    """

    position_exposure = sum(p.cost_basis for p in positions)
    filled_by_order: dict[str, int] = {}
    for f in fills:
        filled_by_order[f.order_id] = filled_by_order.get(f.order_id, 0) + f.quantity
    order_exposure = sum(
        (o.quantity - filled_by_order.get(o.id, o.filled_quantity)) * (o.limit_price or 0.0)
        for o in open_orders
        if o.status in NON_TERMINAL_ORDER_STATUSES
    )
    return position_exposure + order_exposure


def risk_limit_reason(
    *,
    symbol: str,
    order_quantity: int,
    order_limit_price: float,
    exposure_before_order: float,
    max_shares_per_order: Optional[float],
    max_notional_per_order: Optional[float],
    max_total_exposure: Optional[float],
    allowlist: Optional[frozenset[str]],
) -> Optional[str]:
    """Why a proposed order breaches a configured CAPI limit, or ``None`` if it
    doesn't.

    Every limit is independently optional (``None`` = not enforced) — the
    *interface* supports an unrestricted mode (existing tests and any future
    caller that doesn't care about CAPI), but production always passes real,
    validated-positive values from ``Settings`` (``app.config``), which rejects
    a non-finite/non-positive limit at load, the same footgun class as
    ``MARKET_DATA_STALE_MINUTES``/``STRATEGY_MAX_SPREAD_PCT``. ``allowlist``
    empty or ``None`` both mean "no restriction beyond the watchlist" — a
    genuinely meaningful empty state, unlike the numeric limits.

    Beta gates-and-rejects (D-016): a breach blocks the order outright, never
    silently resizes it down to fit. Order of checks: allowlist (cheapest,
    categorical) -> per-order share/notional caps -> total exposure (needs the
    full position/order-book picture the caller assembled).
    """

    if allowlist and symbol not in allowlist:
        return "not_on_allowlist"
    if max_shares_per_order is not None and order_quantity > max_shares_per_order:
        return "exceeds_max_shares_per_order"
    order_notional = order_quantity * order_limit_price
    if max_notional_per_order is not None and order_notional > max_notional_per_order:
        return "exceeds_max_notional_per_order"
    if (
        max_total_exposure is not None
        and exposure_before_order + order_notional > max_total_exposure
    ):
        return "exceeds_max_total_exposure"
    return None
