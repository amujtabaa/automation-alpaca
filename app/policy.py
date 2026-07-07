"""The single source of pre-trade policy — pure reason-code predicates (D-019).

Both post-Phase-6 reviews named the same root cause: "each layer invents its own
check." Wave 0 planted one shared numeric predicate; Wave 2 (D-019) finishes the
job by making this module the *one* home every layer imports from — routes, both
StateStore implementations, the strategy engine, and the market-data path — so a
policy decision (is this a real number, a valid limit price, a resolvable
session, a stopped control, a breached CAPI limit, a usable market-data field) is
made in exactly one place and can never drift between callers. That is why it
lives at ``app/policy.py`` and not under ``app/store/`` (it was
``app/store/validation.py`` through Wave 1): it is not store-specific.

They are pure (no IO, no async, no state): each returns a short, greppable
*reason code* string when the input is invalid/blocked, or ``None`` when it is
acceptable. The stores translate a reason into the appropriate audit event +
``StoreError`` subclass; keeping the *decision* here and the *event/raise wiring*
in each caller is what preserves parity — the one thing that would break it is
two callers drifting on what counts as invalid, which a single source prevents.
The reason codes are also written into rejection-event payloads, so the audit
log says *why* a fill/order was rejected, not just that it was.

This is deliberately a module of pure functions, **not** a ``PolicyEngine``/ABC
or an async seam (D-016c): nothing needs a second implementation yet, and the
approve-route pre-check and the authoritative store check must keep calling the
*same* function with the *same* inputs. Consolidation is de-duplication, not a
new indirection layer.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    Candidate,
    Fill,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    SessionRecord,
    SessionStatus,
    TradingState,
)
from app.transitions import ORDER_TRANSITIONS

# An order still in one of these statuses represents live risk: it could fill
# at any moment, so it counts toward exposure exactly like an already-filled
# position. Everything else (FILLED/CANCELED/REJECTED) is terminal and settled.
# Derived from app/transitions.py's ORDER_TRANSITIONS rather than
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

    Wave 3d (event_truth): the decision now reads ``session.trading_state`` — the
    §8 FSM co-written from the TRADING_STATE_CHANGED event log — rather than the
    two legacy booleans. This is behavior-identical because ``trading_state ==
    TradingState.of(kill_switch, buys_paused)`` by construction (kill dominates
    pause), and the returned reason strings are kept for label continuity: HALTED
    surfaces as ``"kill_switch"`` (the all-stop) and REDUCING as ``"buys_paused"``.
    """

    if session is None:
        return None
    if session.trading_state is TradingState.HALTED:
        return "kill_switch"
    if session.trading_state is TradingState.REDUCING:
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


def kill_switch_block_reason(session: Optional[SessionRecord]) -> Optional[str]:
    """Only the **kill-switch** component of the Rule 8 controls, or ``None``.

    Phase 7 / D-P2: a ``PROTECTION_FLOOR`` autonomous exit bypasses ``buys_paused``
    and closed/unknown-session holds (a lingering position must stay exitable) but
    **must still be held by the kill switch** — the operator's all-stop. This is a
    deliberately narrower predicate than ``order_intent_block_reason`` (which also
    blocks on ``buys_paused``); keeping it separate means the existing BUY gate
    predicates stay byte-for-byte unchanged (§5.2). ``None`` session ⇒ ``None``
    (no session to stop), matching ``order_intent_block_reason``'s convention.

    Wave 3d (event_truth): reads the §8 FSM — only ``HALTED`` (the kill-switch
    state, which dominates pause) holds a protection-floor exit; ``REDUCING``
    (buys-paused) does not. Equivalent to the prior ``session.kill_switch`` read
    because ``trading_state is HALTED`` iff ``kill_switch`` is set.
    """

    if session is None:
        return None
    if session.trading_state is TradingState.HALTED:
        return "kill_switch"
    return None


def order_session_resolution_reason(
    session: Optional[SessionRecord],
) -> Optional[str]:
    """Why an APPROVED candidate's declared session can't back new order intent
    at dispatch, or ``None`` if it resolves.

    The F-004 dispatch-time backstop, centralized (D-019): an APPROVED candidate
    whose declared ``session_id`` no longer resolves (``session is None``) must
    not produce order intent — it is blocked as ``unresolved_session`` and
    audited. ``create_candidate`` already rejects an explicit unresolvable
    session id up front; this covers the order-creation path.

    This is a **distinct** predicate from ``order_intent_block_reason``, and the
    difference is load-bearing: that one deliberately treats ``None`` as "no live
    session to stop" (returns ``None``/unblocked) so the monitoring loop's
    current-session emergency-stop check reads a missing current session as
    nothing to halt. Blocking on ``None`` belongs *only* to the order-creation
    path, which is exactly why it is its own function rather than a change to
    ``order_intent_block_reason``.
    """

    if session is None:
        return "unresolved_session"
    return None


def market_data_field_reason(value: object) -> Optional[str]:
    """Why a market-data snapshot field is unusable, or ``None`` if it is a real,
    finite number.

    The F-005 guard, centralized (D-019): a ``NaN``/``Inf``/``None``/boolean/
    non-numeric last-price, previous-close, bid, or ask must never flow into a
    feature computation or a candidate's ``suggested_limit_price``. This is just
    :func:`finite_number_reason` under a market-data name so the strategy/feature
    layer reads from the same single source as the order/fill layer instead of
    forking its own ``math.isfinite`` check. ``None`` (a missing field) is
    reported as ``non_numeric`` — a missing snapshot value is not usable.
    """

    return finite_number_reason(value)


# --------------------------------------------------------------------------- #
# Shared numeric guards (F-003/F-005)
#
# One place decides "is this a real, usable number" so the store, the routes,
# the strategy engine, and the market-data path stop each inventing their own
# check (the root cause both Phase 6 reviews named). These return a short reason
# code or ``None``, exactly like every other predicate in this module; callers
# suffix the field name (``non_finite`` -> ``non_finite_filled_quantity``).
# --------------------------------------------------------------------------- #


def finite_number_reason(value: object) -> Optional[str]:
    """Reject a value that is not a real, finite number.

    Rejects, in order:

    * **booleans** — ``True``/``False`` are ``int`` subclasses and would
      otherwise sail through every numeric comparison as ``1``/``0``
      (``filled_quantity=True`` silently persisting as ``1`` was a reproduced
      defect);
    * **non-numeric types** — e.g. ``"5"`` yields a clean domain reason instead
      of the raw ``TypeError`` that ``math.isfinite("5")`` would raise;
    * **``NaN`` / ``±Inf``** — which slip past a bare ``<= 0`` guard
      (``nan <= 0`` and ``inf <= 0`` are both ``False``) and would poison a
      derived position, an order row, or a candidate's suggested price.

    A finite ``int`` or ``float`` returns ``None``.
    """

    if isinstance(value, bool):
        return "non_numeric"
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if not math.isfinite(value):
        return "non_finite"
    return None


def whole_count_reason(value: object) -> Optional[str]:
    """Reject a value that is not a finite, whole (integer-valued), non-negative
    share count. Builds on :func:`finite_number_reason`, then rejects a
    fractional value (``0.5``) and a negative one. ``0`` is allowed here — a
    caller that needs *strictly positive* (a fill quantity) checks that itself.
    """

    base = finite_number_reason(value)
    if base is not None:
        return base
    if isinstance(value, float) and not value.is_integer():
        return "non_integer"
    if value < 0:
        return "negative"
    return None


def fill_value_reason(quantity: object, price: object) -> Optional[str]:
    """Reject a fill whose intrinsic values would corrupt position truth.

    Quantity must be a finite, whole, strictly-positive share count; price a
    finite, strictly-positive number (a fractional price is fine). Non-finite,
    boolean, and non-numeric inputs are all rejected via the shared guards above
    with a clean domain reason (never a raw ``TypeError``), since a corrupt
    quantity/price directly violates the derived-position invariant.
    """

    qty_bad = whole_count_reason(quantity)
    if qty_bad is not None:
        # whole_count_reason permits 0 and reports a negative value as
        # "negative" (it has no strict-positivity opinion); a fill's quantity
        # must be strictly positive, so both collapse into the same
        # "non_positive_quantity" reason a plain 0 gets below — quantity's
        # sign, unlike its type/finiteness/wholeness, isn't a distinct reason
        # code here (preserves the pre-D-019 reason vocabulary exactly).
        return "non_positive_quantity" if qty_bad == "negative" else f"{qty_bad}_quantity"
    if quantity <= 0:
        return "non_positive_quantity"

    price_bad = finite_number_reason(price)
    if price_bad is not None:
        return f"{price_bad}_price"
    if price <= 0:
        return "non_positive_price"
    return None


def limit_price_reason(limit_price: object) -> Optional[str]:
    """Reject a missing/non-finite/non-numeric/non-positive limit price for a
    LIMIT order.

    A LIMIT order must carry a real, positive price; ``None``, ``NaN``, ``Inf``,
    a boolean, a non-numeric type, zero, and negative are all rejected. A
    fractional price is valid (unlike a share count). The ``NaN``/``Inf`` cases
    would otherwise pass a bare ``<= 0`` guard.
    """

    if limit_price is None:
        return "missing_limit_price"
    bad = finite_number_reason(limit_price)
    if bad is not None:
        return f"{bad}_limit_price"
    if limit_price <= 0:
        return "non_positive_limit_price"
    return None


def candidate_numeric_reason(
    *, suggested_quantity: object, suggested_limit_price: object
) -> Optional[tuple[str, str]]:
    """Reject malformed candidate numerics at the store boundary (AIR-008).

    A genuinely-absent value is ``None`` (allowed — a candidate need not be
    sized/priced yet). A **present** ``suggested_quantity`` must be a positive
    whole share count; a **present** ``suggested_limit_price`` must be a finite,
    positive number. So this rejects the full coercion class —
    ``NaN``/``Inf``/``-Inf``, zero, negative, a fractional quantity, a ``bool``,
    and a string — *before* the pydantic ``Candidate`` is constructed, so both
    stores reject identically with a clean domain error rather than one
    roundtripping ``nan`` (memory) while the other roundtrips ``None`` (SQLite
    stores ``NaN`` as ``NULL``), and neither leaks a raw pydantic
    ``ValidationError``. Returns ``(field, reason)`` or ``None``.
    """

    if suggested_quantity is not None:
        reason = whole_count_reason(suggested_quantity)
        if reason is None and suggested_quantity <= 0:
            reason = "non_positive"
        if reason is not None:
            return ("suggested_quantity", reason)
    if suggested_limit_price is not None:
        reason = limit_price_reason(suggested_limit_price)
        if reason is not None:
            return ("suggested_limit_price", reason)
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


def filled_quantity_reason(order: Order, new_filled_quantity: object) -> Optional[str]:
    """Reject an out-of-range, malformed, or backward ``filled_quantity`` on an
    order.

    Must first be a finite, whole, non-negative number (F-003: a ``NaN`` slipped
    past the bare ``<``/``>`` comparisons — every comparison against ``NaN`` is
    ``False`` — and persisted as ``nan`` in memory / an ``IntegrityError`` in
    SQLite; a boolean persisted as ``1``). Then must satisfy
    ``0 <= new_filled_quantity <= order.quantity`` and be monotonic
    non-decreasing relative to the order's current ``filled_quantity`` (no
    broker-correction path exists in beta). Equality is allowed (handled
    upstream as a no-op).
    """

    base = whole_count_reason(new_filled_quantity)
    if base is not None:
        # whole_count_reason's reasons (non_numeric/non_finite/non_integer/
        # negative) suffix identically to the pre-D-019 checks this replaces —
        # e.g. "negative" + "_filled_quantity" == "negative_filled_quantity".
        return f"{base}_filled_quantity"
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
        # A pending/in-flight SELL (Phase 7 protective exit / flatten) REDUCES
        # risk, not adds it — counting its remaining notional as positive CAPI
        # exposure could push a concurrent legitimate BUY over max_total_exposure
        # and wrongly reject it. Only open BUY orders add exposure here.
        and OrderSide(o.side) is OrderSide.BUY
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


# --------------------------------------------------------------------------- #
# Operational status — the single server-side lifecycle classification (D-020)
#
# The cockpit used to interpret (order.status + latest submission-block reason)
# into a human operational state, and it owned the "which statuses are still
# open" filter. Wave 2 moves both here so no UI re-derives lifecycle and the next
# UI (Dash) inherits the same truth for free. Pure: a status (+ the reason from
# the latest audit event) in, a stable label out. The labels are a small closed
# vocabulary the operator endpoint and its schema share.
# --------------------------------------------------------------------------- #

# Durable non-terminal order states, operator-facing.
OP_AWAITING_SUBMISSION = "awaiting_submission"  # CREATED, no control holding it
OP_HELD_KILL_SWITCH = "held_kill_switch"
OP_HELD_BUYS_PAUSED = "held_buys_paused"
OP_HELD_SESSION_CLOSED = "held_session_closed"  # closed or unresolvable session
OP_HELD_OTHER = "held"  # a held CREATED order with an unrecognized reason
OP_SUBMITTING = "submitting"
OP_SUBMITTED = "submitted"
OP_PARTIALLY_FILLED = "partially_filled"
OP_CANCEL_PENDING = "cancel_pending"
# ADR-002: an ambiguous submit (timeout/504) quarantined the order; a read-only
# targeted client_order_id query is resolving its true venue state.
OP_TIMEOUT_QUARANTINE = "timeout_quarantine"

# Broker-submit recovery-ledger states (D-017 records surfaced in the operator
# view), sharing the same label space.
OP_BROKER_SUBMISSION_FAILED = "broker_submission_failed"  # unresolved: live at broker, being reconciled
OP_RECOVERY_REQUIRED = "recovery_required"  # needs_review: real untracked position, human must act

# Maps a submission-block reason (from an order_submission_blocked audit event)
# to a held label. Two families of reason reach here:
#   * the order's OWN session being stopped — session_submission_block_reason:
#     kill_switch / buys_paused / session_closed / unknown_session;
#   * the LIVE/current session being stopped while the order's own session is
#     permissive — plan_claim_order_for_submission wraps those as
#     f"current_{...}", i.e. current_kill_switch / current_buys_paused (the
#     D-013a cross-session emergency-stop after a date rollover). A kill switch
#     is a kill switch regardless of which session tripped it, so both prefixes
#     map to the same operational label (only order_intent_block_reason feeds the
#     current_ path, so only kill_switch/buys_paused have current_ variants —
#     session_closed does not).
_HELD_REASON_LABELS = {
    "kill_switch": OP_HELD_KILL_SWITCH,
    "current_kill_switch": OP_HELD_KILL_SWITCH,
    "buys_paused": OP_HELD_BUYS_PAUSED,
    "current_buys_paused": OP_HELD_BUYS_PAUSED,
    "session_closed": OP_HELD_SESSION_CLOSED,
    "unknown_session": OP_HELD_SESSION_CLOSED,
}

_STATUS_OP_LABELS = {
    OrderStatus.SUBMITTING: OP_SUBMITTING,
    OrderStatus.SUBMITTED: OP_SUBMITTED,
    OrderStatus.PARTIALLY_FILLED: OP_PARTIALLY_FILLED,
    OrderStatus.CANCEL_PENDING: OP_CANCEL_PENDING,
    OrderStatus.TIMEOUT_QUARANTINE: OP_TIMEOUT_QUARANTINE,
}

# A manual cancel is offerable on any non-terminal order that has not already
# been asked to cancel — mirrors POST /orders/{id}/cancel exactly (terminal ->
# 409; cancel_pending -> idempotent no-op, so no button).
_CANCELABLE_ORDER_STATUSES = frozenset(
    {
        OrderStatus.CREATED,
        OrderStatus.SUBMITTING,
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
    }
)


def operational_status_for(
    order_status: OrderStatus, block_reason: Optional[str]
) -> str:
    """The operator-facing lifecycle label for a durable non-terminal order.

    ``block_reason`` is the reason from that order's latest
    ``order_submission_blocked`` audit event (``None`` if it was never blocked)
    and only matters while the order is still ``CREATED`` — once it is claimed
    (``SUBMITTING``) or beyond, the status itself is the truth. A terminal status
    has no operational label (the endpoint filters terminals out first); if one
    is passed anyway this returns its raw value defensively rather than raising.
    """

    if order_status is OrderStatus.CREATED:
        if block_reason is None:
            return OP_AWAITING_SUBMISSION
        return _HELD_REASON_LABELS.get(block_reason, OP_HELD_OTHER)
    return _STATUS_OP_LABELS.get(order_status, order_status.value)


def order_is_cancelable(order_status: OrderStatus) -> bool:
    """Whether the operator endpoint should offer a manual cancel — the same
    rule the cancel route enforces (non-terminal and not already
    ``cancel_pending``)."""

    return order_status in _CANCELABLE_ORDER_STATUSES


def recovery_operational_status(cleanup_status: str) -> str:
    """Operational label for a broker-submit recovery record (D-017): a
    ``needs_review`` record is a real untracked position a human must reconcile
    (``recovery_required``); anything else still open is being worked by the
    recovery loop (``broker_submission_failed``)."""

    if cleanup_status == RECOVERY_NEEDS_REVIEW:
        return OP_RECOVERY_REQUIRED
    return OP_BROKER_SUBMISSION_FAILED
