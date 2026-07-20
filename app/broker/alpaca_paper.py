"""Paper-only Alpaca broker adapter — the ONE place in this codebase that imports
the ``alpaca`` SDK.

Safety contract:
- PAPER ONLY, ALWAYS. ``TradingClient`` is always constructed with ``paper=True``.
  There is no live endpoint, no live key variable, no conditional.
- Credentials must NEVER appear in logs, exceptions, or any printed output.
- This module is integration-tested only (env-gated, ``ALPACA_PAPER_API_KEY`` /
  ``ALPACA_PAPER_API_SECRET`` required). The standard unit-test suite never
  imports this module; ``app.broker.__init__.create_broker_adapter`` imports it
  lazily only when building the real adapter.

Rule 9 compliance: unit tests use ``MockBrokerAdapter`` exclusively.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, cast

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import QueryOrderStatus, TimeInForce
from alpaca.trading.models import Order as AlpacaOrder
from alpaca.trading.models import Position as AlpacaPosition
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    OrderRequest,
    ReplaceOrderRequest,
)

from app.broker.adapter import (
    AmbiguousBrokerError,
    BrokerAdapter,
    BrokerError,
    BrokerFill,
    BrokerOrderReport,
    BrokerOrderUpdate,
    BrokerPositionReport,
    TerminalBrokerError,
    VenueOrderScope,
)
from app.features import session_type_for
from app.models import Order, OrderSide, OrderStatus, OrderType, SessionType, utcnow

_log = logging.getLogger(__name__)


def _canonical_broker_id(raw_id: Any, *, context: str) -> str:
    """Return one concrete venue identity or fail as ambiguity."""
    broker_order_id = "" if raw_id is None else str(raw_id).strip()
    if not broker_order_id:
        raise AmbiguousBrokerError(
            f"{context} returned no concrete broker id after the venue call"
        )
    return broker_order_id


def _canonical_ack_broker_id(
    raw_id: Any,
    *,
    raw_client_order_id: Any,
    expected_client_order_id: str,
    context: str,
) -> str:
    """Return one concrete, request-correlated venue identity or ambiguity."""

    broker_order_id = _canonical_broker_id(raw_id, context=context)
    response_client_order_id = (
        raw_client_order_id.strip() if isinstance(raw_client_order_id, str) else ""
    )
    if response_client_order_id != expected_client_order_id:
        raise AmbiguousBrokerError(
            f"{context} returned a missing or mismatched client_order_id"
        )
    return broker_order_id


def _strict_whole_quantity(
    raw_quantity: Any,
    *,
    context: str,
    allow_negative: bool = False,
) -> int:
    """Decode venue quantity without truncating or masking unsupported truth."""

    try:
        quantity = Decimal(str(raw_quantity))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BrokerError(f"{context} returned a malformed quantity") from exc
    if (
        not quantity.is_finite()
        or quantity != quantity.to_integral_value()
        or (quantity < 0 and not allow_negative)
    ):
        raise BrokerError(f"{context} returned a malformed quantity")
    return int(quantity)


def _report_quantity(
    raw_quantity: Any,
    *,
    context: str,
    required: bool = True,
) -> Optional[float]:
    """Preserve valid fractional unmanaged truth without truncation.

    Managed whole-share rows are checked against their exact durable scope by
    reconciliation.  This parser only rejects nonnumeric, nonfinite, or negative
    venue data so one valid external fractional order cannot abort the report.
    """

    if raw_quantity is None and not required:
        return None
    try:
        quantity = Decimal(str(raw_quantity))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BrokerError(f"{context} returned a malformed quantity") from exc
    if not quantity.is_finite() or quantity < 0:
        raise BrokerError(f"{context} returned a malformed quantity")
    if quantity == quantity.to_integral_value():
        return float(int(quantity))
    return float(quantity)


def _canonical_report_text(raw_value: Any, *, context: str, field: str) -> str:
    value = str(getattr(raw_value, "value", raw_value)).strip().lower()
    if not value or value == "none":
        raise BrokerError(f"{context} returned a malformed {field}")
    return value


def _canonical_report_side(raw_side: Any, *, context: str) -> OrderSide:
    """Map only explicit BUY/SELL venue values; never guess the opposite side."""

    normalised = str(getattr(raw_side, "value", raw_side)).lower()
    if normalised == AlpacaOrderSide.BUY.value:
        return OrderSide.BUY
    if normalised == AlpacaOrderSide.SELL.value:
        return OrderSide.SELL
    raise BrokerError(f"{context} returned a malformed order side")


def _canonical_report_order_type(raw_type: Any, *, context: str) -> OrderType:
    normalised = str(getattr(raw_type, "value", raw_type)).lower()
    if normalised == OrderType.LIMIT.value:
        return OrderType.LIMIT
    if normalised == OrderType.MARKET.value:
        return OrderType.MARKET
    raise BrokerError(f"{context} returned a malformed order type")


def _canonical_raw_order_type(raw_type: Any, *, context: str) -> str:
    return _canonical_report_text(raw_type, context=context, field="order type")


def _canonical_report_time_in_force(raw_value: Any, *, context: str) -> str:
    value = str(getattr(raw_value, "value", raw_value)).strip().lower()
    if not value:
        raise BrokerError(f"{context} returned a malformed time in force")
    return value


def _canonical_report_order_class(raw_value: Any, *, context: str) -> str:
    value = str(getattr(raw_value, "value", raw_value)).strip().lower()
    if not value:
        raise BrokerError(f"{context} returned a malformed order class")
    return value


def _canonical_report_symbol(raw_symbol: Any, *, context: str) -> str:
    symbol = raw_symbol.strip().upper() if isinstance(raw_symbol, str) else ""
    if not symbol:
        raise BrokerError(f"{context} returned a malformed symbol")
    return symbol


def _optional_client_order_id(raw_client_order_id: Any) -> Optional[str]:
    if raw_client_order_id is None:
        return None
    if not isinstance(raw_client_order_id, str):
        raise BrokerError("open-orders report row returned a malformed client id")
    client_order_id = raw_client_order_id.strip()
    return client_order_id or None


def _optional_positive_price(raw_price: Any, *, context: str) -> Optional[float]:
    if raw_price is None:
        return None
    try:
        price = float(raw_price)
    except (TypeError, ValueError) as exc:
        raise BrokerError(f"{context} returned a malformed average price") from exc
    if not math.isfinite(price) or price <= 0:
        raise BrokerError(f"{context} returned a malformed average price")
    return price


def _validate_ack_scope(
    response: Any,
    *,
    expected_symbol: Optional[str],
    expected_side: Optional[OrderSide],
    expected_quantity: Optional[int],
    expected_limit_price: Optional[float],
    expected_order_type: Optional[OrderType],
    expected_time_in_force: Optional[str],
    expected_order_class: Optional[str],
    context: str,
    expected_scope: Optional[VenueOrderScope] = None,
    allow_dynamic_market_sell: bool = False,
) -> None:
    """Reject a request-correlated acknowledgement with contradictory scope."""

    try:
        if allow_dynamic_market_sell:
            if expected_scope is None:
                raise BrokerError(
                    f"{context} acknowledgement scope is unavailable: dynamic "
                    "order requires current persisted venue scope"
                )
            # A current rendered scope is exact authority.  Never let the legacy
            # dynamic-type flag widen its order-type or limit-price checks.
            allow_dynamic_market_sell = False
        if expected_scope is not None:
            expected_symbol = expected_scope.symbol
            expected_side = expected_scope.side
            expected_quantity = expected_scope.quantity
            expected_limit_price = expected_scope.limit_price
            expected_order_type = expected_scope.order_type
            expected_time_in_force = expected_scope.time_in_force
            expected_order_class = expected_scope.order_class
        managed_scope = (
            expected_scope is not None
            or any(
                value is not None
                for value in (
                    expected_symbol,
                    expected_side,
                    expected_quantity,
                    expected_order_type,
                    expected_time_in_force,
                    expected_order_class,
                )
            )
            or allow_dynamic_market_sell
        )
        if managed_scope:
            raw_asset_class = getattr(response, "asset_class", None)
            asset_class = (
                str(getattr(raw_asset_class, "value", raw_asset_class)).strip().lower()
            )
            if asset_class != "us_equity":
                raise BrokerError(f"{context} returned a mismatched asset class")
            if getattr(response, "notional", None) is not None:
                raise BrokerError(f"{context} returned notional quantity mode")
            legs = getattr(response, "legs", None)
            if legs not in (None, []):
                raise BrokerError(f"{context} returned unexpected order legs")
            for advanced_field in (
                "stop_price",
                "trail_price",
                "trail_percent",
                "hwm",
                "ratio_qty",
            ):
                if getattr(response, advanced_field, None) is not None:
                    raise BrokerError(
                        f"{context} returned unexpected {advanced_field} scope"
                    )
            managed_extended = getattr(response, "extended_hours", None)
            if not isinstance(managed_extended, bool):
                raise BrokerError(f"{context} returned malformed extended-hours scope")
            raw_position_intent = getattr(response, "position_intent", None)
            if raw_position_intent is not None:
                position_intent = _canonical_report_text(
                    raw_position_intent,
                    context=context,
                    field="position intent",
                )
                managed_side = (
                    expected_scope.side
                    if expected_scope is not None
                    else OrderSide(expected_side)
                    if expected_side is not None
                    else None
                )
                expected_intent = (
                    "buy_to_open"
                    if managed_side is OrderSide.BUY
                    else "sell_to_close"
                    if managed_side is OrderSide.SELL
                    else None
                )
                if expected_intent is None or position_intent != expected_intent:
                    raise BrokerError(f"{context} returned mismatched position intent")
        if (
            expected_symbol is not None
            and _canonical_report_symbol(
                getattr(response, "symbol", None), context=context
            )
            != expected_symbol
        ):
            raise BrokerError(f"{context} returned a mismatched symbol")
        if expected_side is not None and _canonical_report_side(
            getattr(response, "side", None), context=context
        ) is not OrderSide(expected_side):
            raise BrokerError(f"{context} returned a mismatched side")
        if (
            expected_quantity is not None
            and _strict_whole_quantity(getattr(response, "qty", None), context=context)
            != expected_quantity
        ):
            raise BrokerError(f"{context} returned a mismatched quantity")
        raw_type = getattr(response, "type", None)
        raw_deprecated_type = getattr(response, "order_type", None)
        if raw_type is not None and raw_deprecated_type is not None:
            if _canonical_report_order_type(
                raw_type, context=context
            ) is not _canonical_report_order_type(raw_deprecated_type, context=context):
                raise BrokerError(f"{context} returned contradictory order types")
        response_type: Optional[OrderType] = None
        if expected_order_type is not None or allow_dynamic_market_sell:
            response_type = _canonical_report_order_type(raw_type, context=context)
        if expected_order_type is not None and response_type is not OrderType(
            expected_order_type
        ):
            raise BrokerError(f"{context} returned a mismatched order type")
        if (
            expected_time_in_force is not None
            and _canonical_report_time_in_force(
                getattr(response, "time_in_force", None), context=context
            )
            != expected_time_in_force.strip().lower()
        ):
            raise BrokerError(f"{context} returned a mismatched time in force")
        if (
            expected_order_class is not None
            and _canonical_report_order_class(
                getattr(response, "order_class", None), context=context
            )
            != expected_order_class.strip().lower()
        ):
            raise BrokerError(f"{context} returned a mismatched order class")
        if allow_dynamic_market_sell:
            raw_limit = getattr(response, "limit_price", None)
            if response_type is OrderType.MARKET:
                if raw_limit is not None:
                    raise BrokerError(
                        f"{context} returned a limit price for a market order"
                    )
            elif response_type is OrderType.LIMIT:
                if _optional_positive_price(raw_limit, context=context) is None:
                    raise BrokerError(f"{context} returned no price for a limit order")
            else:
                raise BrokerError(f"{context} returned an unsupported order type")
        elif expected_limit_price is not None:
            raw_limit = getattr(response, "limit_price", None)
            try:
                response_limit = Decimal(str(raw_limit))
                expected_limit = Decimal(str(expected_limit_price))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise BrokerError(
                    f"{context} returned a malformed limit price"
                ) from exc
            if (
                not response_limit.is_finite()
                or response_limit <= 0
                or response_limit != expected_limit
            ):
                raise BrokerError(f"{context} returned a mismatched limit price")
        elif (
            expected_order_type is not None
            and OrderType(expected_order_type) is OrderType.MARKET
            and getattr(response, "limit_price", None) is not None
        ):
            raise BrokerError(f"{context} returned a limit price for a market order")
        if expected_scope is not None:
            extended = managed_extended
            if (
                expected_scope.extended_hours is not None
                and extended != expected_scope.extended_hours
            ) or (expected_scope.order_type is OrderType.MARKET and extended):
                raise BrokerError(f"{context} returned mismatched extended-hours scope")
            raw_replaces = getattr(response, "replaces", None)
            if expected_scope.replaces_broker_order_id is not None:
                if (
                    raw_replaces is None
                    or _canonical_broker_id(raw_replaces, context=context)
                    != expected_scope.replaces_broker_order_id
                ):
                    raise BrokerError(f"{context} returned a mismatched predecessor")
            elif raw_replaces is not None:
                raise BrokerError(f"{context} returned an unexpected predecessor")
        elif managed_scope and response_type is OrderType.MARKET and managed_extended:
            raise BrokerError(f"{context} returned impossible MARKET extended hours")
    except BrokerError as exc:
        raise AmbiguousBrokerError(
            f"{context} returned request-contradictory acknowledgement scope"
        ) from exc


def _default_venue_scope(
    order: Order,
    *,
    current_session: Optional[SessionType],
    replaces_broker_order_id: Optional[str] = None,
) -> VenueOrderScope:
    order_type = OrderType(order.order_type)
    extended_hours = order_type is OrderType.LIMIT and current_session in {
        SessionType.PRE_MARKET,
        SessionType.AFTER_HOURS,
    }
    return VenueOrderScope(
        client_order_id=order.id,
        symbol=order.symbol,
        side=OrderSide(order.side),
        quantity=order.quantity,
        order_type=order_type,
        limit_price=order.limit_price,
        extended_hours=extended_hours,
        replaces_broker_order_id=replaces_broker_order_id,
    )


def _validate_rendered_order_against_scope(
    order: Order, scope: VenueOrderScope
) -> None:
    if (
        scope.client_order_id != order.id
        or scope.symbol != order.symbol
        or scope.side is not OrderSide(order.side)
        or scope.quantity != order.quantity
        or scope.order_type is not OrderType(order.order_type)
        or scope.limit_price != order.limit_price
        or scope.asset_class != "us_equity"
        or scope.quantity_mode != "qty"
        or scope.time_in_force != TimeInForce.DAY.value
        or scope.order_class != "simple"
        or scope.replaces_broker_order_id is not None
        or not isinstance(scope.extended_hours, bool)
        or (scope.order_type is OrderType.MARKET and scope.extended_hours)
        or (
            scope.order_type is OrderType.LIMIT
            and (
                scope.limit_price is None
                or not math.isfinite(scope.limit_price)
                or scope.limit_price <= 0
            )
        )
    ):
        raise BrokerError("venue scope contradicts rendered managed order")


# --------------------------------------------------------------------------- #
# Alpaca order-status → our OrderStatus
# --------------------------------------------------------------------------- #

# Map every documented Alpaca order status to our canonical OrderStatus.
# Source: https://docs.alpaca.markets/reference/getallorders-1 (status field).
# Unknown / unrecognised statuses fail closed as ``BrokerError``. A new venue
# lifecycle value must be classified explicitly before it can drive local state.
_ALPACA_STATUS_MAP: dict[str, OrderStatus] = {
    # Still open / working
    "new": OrderStatus.SUBMITTED,
    "accepted": OrderStatus.SUBMITTED,
    "pending_new": OrderStatus.SUBMITTED,
    "accepted_for_bidding": OrderStatus.SUBMITTED,
    # Open but not yet routed/executable (e.g. held for a stop trigger, or being
    # calculated). Real Alpaca statuses — map explicitly so they don't hit the
    # unknown-status warning path in normal operation (F4).
    "held": OrderStatus.SUBMITTED,
    "calculated": OrderStatus.SUBMITTED,
    # Partial execution (still working remainder)
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    # Terminal — fully executed
    "filled": OrderStatus.FILLED,
    # Cancel requested but not yet finalized — NON-terminal, keep polling so a
    # late fill before the venue confirms the cancel is still recorded (CHAOS-1).
    "pending_cancel": OrderStatus.CANCEL_PENDING,
    # Terminal — no longer active, not filled (treat as canceled)
    "canceled": OrderStatus.CANCELED,
    "expired": OrderStatus.CANCELED,
    "replaced": OrderStatus.CANCELED,
    # Nonterminal lifecycle states.  Alpaca documents ``stopped`` as a trade
    # that is guaranteed but has not occurred, ``suspended`` as temporarily
    # ineligible, and ``done_for_day`` as able to receive updates next trading
    # day.  Keep all three pollable until an actual terminal status/fill arrives.
    "done_for_day": OrderStatus.SUBMITTED,
    "suspended": OrderStatus.SUBMITTED,
    "stopped": OrderStatus.SUBMITTED,
    # Terminal — definitively rejected by the venue
    "rejected": OrderStatus.REJECTED,
}


def _map_status(raw_status: object) -> OrderStatus:
    """Normalise an Alpaca status (enum *or* str) to our ``OrderStatus``.

    The SDK may return an ``AlpacaOrderStatus`` enum or a plain string depending
    on SDK version; ``getattr(v, "value", v)`` handles both.
    """
    if raw_status is None:
        raise BrokerError("Alpaca response returned a missing order status")
    normalised = str(getattr(raw_status, "value", raw_status)).lower()
    mapped = _ALPACA_STATUS_MAP.get(normalised)
    if mapped is None:
        raise BrokerError(
            f"Unrecognised Alpaca order status {normalised!r}; "
            "lifecycle classification is required before it can drive local state"
        )
    return mapped


def _validate_ack_state(response: Any, *, context: str) -> None:
    """Validate ACK lifecycle fields without suppressing broker overfill truth."""

    try:
        _map_status(getattr(response, "status", None))
        _strict_whole_quantity(
            getattr(response, "filled_qty", None),
            context=f"{context} acknowledgement",
        )
    except BrokerError as exc:
        # The venue call returned a concrete correlated identity, so malformed
        # lifecycle state is an accepted-but-uncertain outcome, never a safe
        # pre-flight failure that may release the claim and resend.
        raise AmbiguousBrokerError(
            f"{context} returned malformed acknowledgement state"
        ) from exc


def _map_open_report_status(raw_status: object) -> OrderStatus:
    status = _map_status(raw_status)
    if status not in {
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
    }:
        raise BrokerError("Alpaca open-orders report returned a terminal order status")
    return status


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_fill_price(
    filled_avg_price: Optional[object],
    limit_price: Optional[object],
    fallback_price: Optional[object] = None,
) -> Optional[float]:
    """Best *trustworthy* price for a delta fill: the broker's filled average if
    present and usable, else the order's limit, else a caller-supplied
    ``fallback_price``. Returns ``None`` when none is a finite, strictly-positive
    number.

    AIR-002: this used to fall back to ``0.0`` when no price was available, which
    fabricated a $0 execution — corrupting cost basis / average price and letting
    a bogus fill append silently. A ``0.0``/negative/``NaN``/``Inf`` average is
    *untrustworthy*, not a real price, so it is rejected here too. The caller
    surfaces an un-priceable fill as unrecordable (the divergence is escalated to
    a durable reconciliation record), never as a normal ``0.0`` fill. Tolerant of
    the SDK's string/Decimal/None shapes.

    Phase 7 §7: ``fallback_price`` is the reconcile-time snapshot ``last_price``
    the monitoring path supplies for a MARKET order (which has no ``limit_price``),
    so a transiently-absent ``filled_avg_price`` on a protective market-sell never
    withholds a position-critical fill (which, with the single-flight dedup, would
    strand protection). Tried LAST, so a real execution price always wins."""

    for candidate in (filled_avg_price, limit_price, fallback_price):
        if candidate is None:
            continue
        try:
            # candidate is deliberately `object` — the SDK hands back str/Decimal/
            # float shapes; the try/except is the real guard, so cast for the type
            # checker and let a non-floatable raise into the except below.
            price = float(cast(Any, candidate))
        except (TypeError, ValueError):
            continue
        if math.isfinite(price) and price > 0:
            return price
    return None


# --------------------------------------------------------------------------- #
# Adapter
# --------------------------------------------------------------------------- #


class AlpacaPaperAdapter(BrokerAdapter):
    """Real paper-only Alpaca adapter.

    Constructed by :func:`app.broker.create_broker_adapter` when paper
    credentials are present. Never instantiated in unit tests.

    PAPER ONLY — ``TradingClient`` is always constructed with ``paper=True``.
    This is permanent, unconditional, non-overridable.
    """

    def __init__(self, api_key: str, api_secret: str) -> None:
        # PAPER ONLY: paper=True is hardcoded. Keys are stored but never logged.
        self._client = TradingClient(api_key, api_secret, paper=True)

    # ---------------------------------------------------------------------- #
    # BrokerAdapter interface
    # ---------------------------------------------------------------------- #

    async def submit_order(
        self, order: Order, *, venue_scope: Optional[VenueOrderScope] = None
    ) -> str:
        """Submit ``order`` to Alpaca paper and return Alpaca's order UUID.

        Beta only ever creates LIMIT orders (Rule 12: pre/after-hours require
        limit-only; regular-hours other types are permitted but the current
        candidate/order model only produces limit orders). ``extended_hours``
        is set based on the CURRENT session at submission time (Rule 12), so a
        limit order submitted during premarket/after-hours is actually
        eligible to execute in that session rather than silently queued until
        regular hours.

        ``client_order_id`` is set to ``order.id`` (our internal UUID hex) so
        that a retry after a crash between submit-and-persist is rejected by
        Alpaca as a duplicate rather than double-submitting. On a
        duplicate-id rejection we look up the existing order and return its
        Alpaca UUID — making re-submit idempotent.
        """
        alpaca_side = (
            AlpacaOrderSide.BUY
            if order.side is OrderSide.BUY or order.side == OrderSide.BUY.value
            else AlpacaOrderSide.SELL
        )

        # extended_hours (BACKEND-2, resolved in Phase 5): a LIMIT+DAY order
        # submitted to Alpaca WITHOUT extended_hours=True is not eligible to
        # execute during premarket (04:00-09:30 ET) or after-hours
        # (16:00-20:00 ET) — only during regular hours. Phase 5's Strategy
        # Engine (app/strategy.py) proposes candidates EXCLUSIVELY during those
        # two windows (premarket_momentum_v1's whole purpose), so submitting
        # without this flag would make its approved candidates silently
        # ineligible to fill in the very session they were proposed for —
        # found during a post-Phase-5 self-review, not caught at the time
        # Phase 5 shipped, since the order-submission side was never revisited
        # when the Strategy Engine was built.
        #
        # Determined at SUBMISSION time (session_type_for(utcnow()), not
        # candidate-creation time): no Order/Candidate schema change needed,
        # and it's the more correct reading of Rule 12's "session-conditional"
        # anyway — extended-hours eligibility is a property of when the order
        # actually reaches the exchange, not when the proposal was generated.
        # A candidate whose approval is delayed past its original session's
        # close naturally falls back to a regular DAY limit (extended_hours
        # not needed then) rather than incorrectly carrying a stale premarket
        # intent forward.
        current_session = session_type_for(utcnow())
        scope = venue_scope or _default_venue_scope(
            order,
            current_session=current_session,
        )
        _validate_rendered_order_against_scope(order, scope)

        # Phase 7 §7: side/type-aware request. A MARKET order (only ever a
        # protective SELL, and only submitted in REGULAR hours by §5.4) becomes a
        # MarketOrderRequest — no limit_price, no extended_hours (market orders are
        # regular-session only). Everything else stays the existing LimitOrderRequest
        # path (BUYs, and protective sells downgraded to LIMIT in pre/after-hours).
        if scope.order_type is OrderType.MARKET:
            # Defensive backstop for the D-015/Rule-12 guarantee: the submit path
            # (§5.4) must have downgraded to LIMIT outside regular hours, so a
            # MARKET request reaching here in a limit-only session is a bug. Fail
            # closed (retryable) rather than send a market order into thin
            # premarket/after-hours liquidity.
            if current_session is not SessionType.REGULAR:
                raise BrokerError(
                    f"refusing to submit MARKET order {order.id!r} outside regular "
                    f"hours ({current_session}); Rule 12 requires limit-only"
                )
            req: OrderRequest = MarketOrderRequest(
                symbol=order.symbol,
                qty=scope.quantity,
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
                client_order_id=scope.client_order_id,
            )
        else:
            req = LimitOrderRequest(
                symbol=order.symbol,
                qty=scope.quantity,
                side=alpaca_side,
                time_in_force=TimeInForce.DAY,
                extended_hours=scope.extended_hours,
                limit_price=scope.limit_price,
                client_order_id=scope.client_order_id,
            )

        try:
            # The SDK types its returns as `Model | dict[str, Any]` for its
            # raw_data mode; this client is not raw, so it always returns the typed
            # model. Cast reflects that (runtime no-op) so attribute access typechecks.
            resp = cast(
                AlpacaOrder, await asyncio.to_thread(self._client.submit_order, req)
            )
            broker_order_id = _canonical_ack_broker_id(
                resp.id,
                raw_client_order_id=getattr(resp, "client_order_id", None),
                expected_client_order_id=order.id,
                context=f"submit for order {order.id!r}",
            )
            _validate_ack_scope(
                resp,
                expected_symbol=order.symbol,
                expected_side=OrderSide(order.side),
                expected_quantity=order.quantity,
                expected_limit_price=(
                    order.limit_price
                    if OrderType(order.order_type) is OrderType.LIMIT
                    else None
                ),
                expected_order_type=OrderType(order.order_type),
                expected_time_in_force=TimeInForce.DAY.value,
                expected_order_class="simple",
                context=f"submit for order {order.id!r}",
                expected_scope=scope,
            )
            _validate_ack_state(resp, context=f"submit for order {order.id!r}")
            return broker_order_id
        except APIError as exc:
            code = getattr(exc, "status_code", None)
            exc_msg = str(exc).lower()
            # A duplicate client_order_id is a 409/422 that names the duplicate.
            # Recover the already-created order so a crash-then-retry is idempotent
            # (never a second broker order). Anything else is a real failure.
            if code in (409, 422) and (
                "duplicate" in exc_msg or "client_order_id" in exc_msg
            ):
                _log.info(
                    "Duplicate client_order_id for order %s; recovering existing "
                    "Alpaca order.",
                    order.id,
                )
                try:
                    existing = cast(
                        AlpacaOrder,
                        await asyncio.to_thread(
                            self._client.get_order_by_client_id, order.id
                        ),
                    )
                    broker_order_id = _canonical_ack_broker_id(
                        existing.id,
                        raw_client_order_id=getattr(existing, "client_order_id", None),
                        expected_client_order_id=order.id,
                        context=f"duplicate recovery for order {order.id!r}",
                    )
                    _validate_ack_scope(
                        existing,
                        expected_symbol=order.symbol,
                        expected_side=OrderSide(order.side),
                        expected_quantity=order.quantity,
                        expected_limit_price=(
                            order.limit_price
                            if OrderType(order.order_type) is OrderType.LIMIT
                            else None
                        ),
                        expected_order_type=OrderType(order.order_type),
                        expected_time_in_force=TimeInForce.DAY.value,
                        expected_order_class="simple",
                        context=f"duplicate recovery for order {order.id!r}",
                        expected_scope=scope,
                    )
                    _validate_ack_state(
                        existing,
                        context=f"duplicate recovery for order {order.id!r}",
                    )
                    return broker_order_id
                except AmbiguousBrokerError:
                    raise
                except Exception as lookup_exc:
                    # The broker says this client_order_id is a duplicate but we
                    # cannot look up the existing order. The duplicate proves a
                    # venue order exists, so rejection is not definitive: route
                    # to ambiguity quarantine and targeted reconciliation.
                    raise AmbiguousBrokerError(
                        f"Duplicate submit for order {order.id!r}: original submit "
                        f"reported an existing order but its lookup failed."
                    ) from lookup_exc
            # Do NOT include exc in the message string — it may echo back request
            # params that could include keys if the SDK surfaces them.
            #
            # AIR-003 classification: a definitive 4xx rejection (bad request,
            # auth, forbidden/restricted account, unprocessable — e.g. insufficient
            # buying power, non-tradable/delisted symbol) will NOT succeed on
            # retry, so surface it as TerminalBrokerError. A stale-SUBMITTING
            # re-drive then escalates it to a durable needs_review record instead
            # of livelocking every tick and inflating exposure forever. Everything
            # else (429 rate-limit, 5xx, unknown) is transient -> plain BrokerError.
            if code in (400, 401, 403, 404, 422):
                raise TerminalBrokerError(
                    f"Broker definitively rejected order {order.id!r} "
                    f"({order.symbol} {order.quantity} shares, HTTP {code})."
                ) from exc
            # ADR-002 classification (§6):
            #  * 429 rate-limit — pre-flight reject, the order provably never
            #    reached the book, so it is a SAFE transient retry (plain
            #    BrokerError; conflict C2 keeps it transient vs §6's letter).
            #  * 5xx (incl. 504) or any other unexpected code — the request
            #    reached Alpaca's servers which then failed; the order MAY have
            #    been accepted. Ambiguous -> quarantine + targeted reconcile, never
            #    blind-resubmit.
            if code == 429:
                raise BrokerError(
                    f"Rate-limited submitting order {order.id!r} ({order.symbol} "
                    f"{order.quantity} shares, HTTP 429)."
                ) from exc
            raise AmbiguousBrokerError(
                f"Ambiguous submit outcome for order {order.id!r} ({order.symbol} "
                f"{order.quantity} shares, HTTP {code}) — may be live at the venue."
            ) from exc
        except BrokerError:
            raise
        except Exception as exc:
            # Network/timeout/transport/parse failure AFTER the request may have
            # left the process (ADR-002): we cannot tell whether it reached the
            # venue, so the outcome is AMBIGUOUS. Quarantine + targeted reconcile,
            # never blind-resubmit (a resubmit could double-fire a live order).
            raise AmbiguousBrokerError(
                f"Ambiguous submit outcome for order {order.id!r} ({order.symbol} "
                f"{order.quantity} shares) — transport/timeout, may be live."
            ) from exc

    async def get_order_status(
        self,
        broker_order_id: str,
        *,
        recorded_quantity: int = 0,
        fallback_price: Optional[float] = None,
        expected_client_order_id: Optional[str] = None,
        expected_symbol: Optional[str] = None,
        expected_side: Optional[OrderSide] = None,
        expected_quantity: Optional[int] = None,
        expected_limit_price: Optional[float] = None,
        expected_order_type: Optional[OrderType] = None,
        expected_time_in_force: Optional[str] = None,
        expected_order_class: Optional[str] = None,
        expected_scope: Optional[VenueOrderScope] = None,
        allow_dynamic_market_sell: bool = False,
    ) -> BrokerOrderUpdate:
        """Poll Alpaca for the current state of one open order.

        Alpaca's cumulative ``filled_qty`` is converted to one deterministic
        cumulative-delta fill, sized over ``recorded_quantity`` so it never
        re-reports already-counted shares under a second identity scheme.

        ``fallback_price`` (§7) is the last-resort audit price for a fill with no
        trustworthy ``filled_avg_price`` and no ``limit_price`` (a MARKET order) —
        see :func:`_resolve_fill_price`.
        """
        expected_broker_order_id = _canonical_broker_id(
            broker_order_id,
            context="Alpaca order-status request",
        )
        try:
            alpaca_order = cast(
                AlpacaOrder,
                await asyncio.to_thread(
                    self._client.get_order_by_id,
                    expected_broker_order_id,
                ),
            )
        except Exception as exc:
            raise BrokerError(
                "Failed to fetch order status for "
                f"broker_order_id={expected_broker_order_id!r}."
            ) from exc

        response_broker_order_id = _canonical_broker_id(
            getattr(alpaca_order, "id", None),
            context="Alpaca order-status response",
        )
        if response_broker_order_id != expected_broker_order_id:
            raise BrokerError(
                "Alpaca order-status response returned a mismatched broker id "
                f"for requested broker_order_id={expected_broker_order_id!r}."
            )
        if expected_client_order_id is not None:
            response_client_order_id = getattr(alpaca_order, "client_order_id", None)
            if (
                not isinstance(response_client_order_id, str)
                or response_client_order_id.strip() != expected_client_order_id
            ):
                raise BrokerError(
                    "Alpaca order-status response returned a mismatched client id"
                )
        if (
            expected_symbol is not None
            and _canonical_report_symbol(
                getattr(alpaca_order, "symbol", None),
                context="Alpaca order-status response",
            )
            != expected_symbol
        ):
            raise BrokerError(
                "Alpaca order-status response returned a mismatched symbol"
            )
        if expected_side is not None and _canonical_report_side(
            getattr(alpaca_order, "side", None),
            context="Alpaca order-status response",
        ) is not OrderSide(expected_side):
            raise BrokerError("Alpaca order-status response returned a mismatched side")
        _validate_ack_scope(
            alpaca_order,
            expected_symbol=None,
            expected_side=None,
            expected_quantity=expected_quantity,
            expected_limit_price=expected_limit_price,
            expected_order_type=expected_order_type,
            expected_time_in_force=expected_time_in_force,
            expected_order_class=expected_order_class,
            context="Alpaca order-status response",
            expected_scope=expected_scope,
            allow_dynamic_market_sell=allow_dynamic_market_sell,
        )

        status = _map_status(getattr(alpaca_order, "status", None))
        filled_qty = _strict_whole_quantity(
            getattr(alpaca_order, "filled_qty", None),
            context="Alpaca order-status response",
        )

        fills = await self._get_fills(
            broker_order_id=expected_broker_order_id,
            filled_qty=filled_qty,
            recorded_quantity=recorded_quantity,
            filled_avg_price=alpaca_order.filled_avg_price,
            limit_price=alpaca_order.limit_price,
            fallback_price=fallback_price,
        )

        return BrokerOrderUpdate(
            status=status,
            filled_quantity=filled_qty,
            fills=fills,
        )

    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel an open Alpaca paper order.

        Idempotent: if Alpaca says the order is already terminal (404, already
        canceled/filled, etc.) we treat it as a no-op success — the order is
        no longer live either way. Raises ``BrokerError`` only on a genuine
        network or API failure.
        """
        try:
            await asyncio.to_thread(self._client.cancel_order_by_id, broker_order_id)
        except APIError as exc:
            # Decide idempotency by HTTP STATUS, not by sniffing free-text — a
            # false positive here would silently mark a *live* order canceled.
            #   404 = order not found (already gone)
            #   422 = not cancelable (already in a terminal state)
            # Both mean the order is no longer live -> idempotent no-op. Every
            # other code (401/403/429/5xx, ...) is a real failure and is raised,
            # so a transient error never masquerades as a successful cancel.
            code = getattr(exc, "status_code", None)
            if code in (404, 422):
                _log.debug(
                    "cancel_order no-op: %r already terminal (HTTP %s).",
                    broker_order_id,
                    code,
                )
                return
            raise BrokerError(
                f"Failed to cancel order broker_order_id={broker_order_id!r}."
            ) from exc
        except Exception as exc:
            # Network/timeout/unknown — a real failure. NEVER treated as a no-op.
            raise BrokerError(
                f"Failed to cancel order broker_order_id={broker_order_id!r}."
            ) from exc

    async def replace_order(
        self,
        broker_order_id: str,
        *,
        client_order_id: str,
        expected_symbol: Optional[str] = None,
        expected_side: Optional[OrderSide] = None,
        expected_order_type: Optional[OrderType] = OrderType.LIMIT,
        expected_time_in_force: Optional[str] = TimeInForce.DAY.value,
        expected_order_class: Optional[str] = "simple",
        venue_scope: Optional[VenueOrderScope] = None,
        limit_price: Optional[float] = None,
        quantity: Optional[int] = None,
    ) -> str:
        """Venue-side atomic cancel/replace via the SDK's
        ``replace_order_by_id`` (the REAL method name — see
        work/review/FINDING-alpaca-adapter-wrong-sdk-method.md for why the
        tests pin it). Returns the REPLACEMENT order's Alpaca UUID.

        ``client_order_id`` is the replacement's idempotency key: a duplicate
        rejection (a crash-then-retry of the same replace) recovers the
        already-created replacement by client id instead of erroring or
        minting a second order — the same D-017 discipline as submit. The
        error taxonomy mirrors ``submit_order`` exactly (ADR-002): definitive
        4xx → Terminal; 429 pre-flight → transient; 5xx/timeout/transport →
        Ambiguous (the replacement MAY be live — quarantine + reconcile by
        client id, never blind-re-replace).
        """

        if venue_scope is not None:
            if (
                venue_scope.client_order_id != client_order_id
                or venue_scope.replaces_broker_order_id != broker_order_id
                or venue_scope.order_type is not OrderType.LIMIT
            ):
                raise BrokerError("replace venue scope contradicts request identity")
            quantity = venue_scope.quantity
            limit_price = venue_scope.limit_price

        req = ReplaceOrderRequest(
            qty=quantity,
            limit_price=limit_price,
            client_order_id=client_order_id,
        )
        try:
            resp = cast(
                AlpacaOrder,
                await asyncio.to_thread(
                    self._client.replace_order_by_id, broker_order_id, req
                ),
            )
            replacement_broker_order_id = _canonical_ack_broker_id(
                resp.id,
                raw_client_order_id=getattr(resp, "client_order_id", None),
                expected_client_order_id=client_order_id,
                context=f"replace of {broker_order_id!r}",
            )
            if replacement_broker_order_id == broker_order_id:
                raise AmbiguousBrokerError(
                    "replace acknowledgement reused the predecessor broker identity"
                )
            _validate_ack_scope(
                resp,
                expected_symbol=expected_symbol,
                expected_side=expected_side,
                expected_quantity=quantity,
                expected_limit_price=limit_price,
                expected_order_type=expected_order_type,
                expected_time_in_force=expected_time_in_force,
                expected_order_class=expected_order_class,
                context=f"replace of {broker_order_id!r}",
                expected_scope=venue_scope,
            )
            _validate_ack_state(resp, context=f"replace of {broker_order_id!r}")
            return replacement_broker_order_id
        except APIError as exc:
            code = getattr(exc, "status_code", None)
            exc_msg = str(exc).lower()
            if code in (409, 422) and (
                "duplicate" in exc_msg or "client_order_id" in exc_msg
            ):
                _log.info(
                    "Duplicate client_order_id for replacement %s; recovering "
                    "existing Alpaca order.",
                    client_order_id,
                )
                try:
                    existing = cast(
                        AlpacaOrder,
                        await asyncio.to_thread(
                            self._client.get_order_by_client_id, client_order_id
                        ),
                    )
                    replacement_broker_order_id = _canonical_ack_broker_id(
                        existing.id,
                        raw_client_order_id=getattr(existing, "client_order_id", None),
                        expected_client_order_id=client_order_id,
                        context=f"duplicate replace recovery for {client_order_id!r}",
                    )
                    if replacement_broker_order_id == broker_order_id:
                        raise AmbiguousBrokerError(
                            "duplicate replace recovery reused the predecessor "
                            "broker identity"
                        )
                    _validate_ack_scope(
                        existing,
                        expected_symbol=expected_symbol,
                        expected_side=expected_side,
                        expected_quantity=quantity,
                        expected_limit_price=limit_price,
                        expected_order_type=expected_order_type,
                        expected_time_in_force=expected_time_in_force,
                        expected_order_class=expected_order_class,
                        context=(f"duplicate replace recovery for {client_order_id!r}"),
                        expected_scope=venue_scope,
                    )
                    _validate_ack_state(
                        existing,
                        context=(f"duplicate replace recovery for {client_order_id!r}"),
                    )
                    return replacement_broker_order_id
                except AmbiguousBrokerError:
                    raise
                except Exception as lookup_exc:
                    raise AmbiguousBrokerError(
                        f"Duplicate replace for {client_order_id!r}: original "
                        f"replace reported an existing replacement but its "
                        f"lookup failed."
                    ) from lookup_exc
            if code in (400, 401, 403, 404, 422):
                raise TerminalBrokerError(
                    f"Broker definitively rejected replace of "
                    f"{broker_order_id!r} (HTTP {code})."
                ) from exc
            if code == 429:
                raise BrokerError(
                    f"Rate-limited replacing {broker_order_id!r} (HTTP 429)."
                ) from exc
            raise AmbiguousBrokerError(
                f"Ambiguous replace outcome for {broker_order_id!r} "
                f"(HTTP {code}) — the replacement may be live at the venue."
            ) from exc
        except BrokerError:
            raise
        except Exception as exc:
            # Network/timeout/transport/parse failure AFTER the request may
            # have reached Alpaca — the replacement may exist. Ambiguous:
            # quarantine + reconcile by client_order_id, never blind-retry.
            raise AmbiguousBrokerError(
                f"Ambiguous replace outcome for {broker_order_id!r} "
                f"(transport failure) — the replacement may be live."
            ) from exc

    async def get_order_by_client_order_id(
        self,
        client_order_id: str,
        *,
        expected_symbol: Optional[str] = None,
        expected_side: Optional[OrderSide] = None,
        expected_quantity: Optional[int] = None,
        expected_limit_price: Optional[float] = None,
        expected_order_type: Optional[OrderType] = None,
        expected_time_in_force: Optional[str] = None,
        expected_order_class: Optional[str] = None,
        expected_scope: Optional[VenueOrderScope] = None,
        allow_dynamic_market_sell: bool = False,
    ) -> Optional[BrokerOrderUpdate]:
        """Read-only targeted query by our ``client_order_id`` (ADR-002 / wave 3c).

        Used to resolve a ``TIMEOUT_QUARANTINE`` order whose ambiguous submit left
        no ``broker_order_id``. Returns the venue order's state (with its
        ``broker_order_id`` so the caller can adopt it), ``None`` ONLY on a
        confirmed 404 (the order never existed), and raises ``BrokerError`` on any
        query failure — a failed query must never be read as 'absent' (§7). This
        never mutates a venue order, so it can never double-submit.
        """
        try:
            alpaca_order = cast(
                "Optional[AlpacaOrder]",
                await asyncio.to_thread(
                    self._client.get_order_by_client_id, client_order_id
                ),
            )
        except APIError as exc:
            if getattr(exc, "status_code", None) == 404:
                return None  # the venue confirms this client_order_id never landed
            raise BrokerError(
                f"Targeted query failed for client_order_id={client_order_id!r}."
            ) from exc
        except Exception as exc:
            raise BrokerError(
                f"Targeted query failed for client_order_id={client_order_id!r}."
            ) from exc
        if alpaca_order is None:
            raise BrokerError(
                "Alpaca returned a malformed targeted query response for "
                f"client_order_id={client_order_id!r}."
            )
        if (
            expected_symbol is not None
            and _canonical_report_symbol(
                getattr(alpaca_order, "symbol", None),
                context="Alpaca targeted query response",
            )
            != expected_symbol
        ):
            raise BrokerError(
                "Alpaca targeted query response returned a mismatched symbol"
            )
        if expected_side is not None and _canonical_report_side(
            getattr(alpaca_order, "side", None),
            context="Alpaca targeted query response",
        ) is not OrderSide(expected_side):
            raise BrokerError(
                "Alpaca targeted query response returned a mismatched side"
            )
        _validate_ack_scope(
            alpaca_order,
            expected_symbol=None,
            expected_side=None,
            expected_quantity=expected_quantity,
            expected_limit_price=expected_limit_price,
            expected_order_type=expected_order_type,
            expected_time_in_force=expected_time_in_force,
            expected_order_class=expected_order_class,
            context="Alpaca targeted query response",
            expected_scope=expected_scope,
            allow_dynamic_market_sell=allow_dynamic_market_sell,
        )
        try:
            return BrokerOrderUpdate(
                status=_map_status(getattr(alpaca_order, "status", None)),
                filled_quantity=_strict_whole_quantity(
                    getattr(alpaca_order, "filled_qty", None),
                    context="Alpaca targeted query response",
                ),
                fills=[],
                broker_order_id=_canonical_ack_broker_id(
                    getattr(alpaca_order, "id", None),
                    raw_client_order_id=getattr(alpaca_order, "client_order_id", None),
                    expected_client_order_id=client_order_id,
                    context=(f"targeted query for client_order_id={client_order_id!r}"),
                ),
            )
        except BrokerError:
            raise
        except Exception as exc:
            raise BrokerError(
                "Alpaca returned a malformed targeted query response for "
                f"client_order_id={client_order_id!r}."
            ) from exc

    async def list_open_orders(self) -> list[BrokerOrderReport]:
        """The venue's current OPEN orders — the §7 mass order-status report.

        Wraps ``get_orders(status=OPEN)``. Read-only. Raises ``BrokerError`` on
        failure (the caller must NOT read a failed report as "no open orders").
        Fills are left empty here. If a managed row's cumulative quantity exceeds
        local truth, reconciliation requests a strict per-order poll to obtain a
        priced deterministic delta; it never fabricates a mass-report fill.
        """
        try:
            alpaca_orders = cast(
                "list[AlpacaOrder]",
                await asyncio.to_thread(
                    self._client.get_orders,
                    GetOrdersRequest(status=QueryOrderStatus.OPEN),
                ),
            )
        except Exception as exc:
            raise BrokerError("Failed to fetch the open-orders report.") from exc
        if not isinstance(alpaca_orders, list):
            raise BrokerError("Alpaca returned a malformed open-orders report.")
        reports: list[BrokerOrderReport] = []
        seen_broker_ids: set[str] = set()
        seen_client_order_ids: set[str] = set()
        for order in alpaca_orders:
            broker_order_id = _canonical_broker_id(
                getattr(order, "id", None), context="open-orders report row"
            )
            raw_notional = getattr(order, "notional", None)
            quantity_mode = "notional" if raw_notional is not None else "qty"
            quantity = _report_quantity(
                getattr(order, "qty", None),
                context="open-orders report row",
                required=quantity_mode == "qty",
            )
            filled_quantity = _report_quantity(
                getattr(order, "filled_qty", None),
                context="open-orders report row",
            )
            assert filled_quantity is not None
            if quantity_mode == "qty" and (quantity is None or quantity <= 0):
                raise BrokerError(
                    "Alpaca open-orders report returned contradictory quantity"
                )
            raw_type = getattr(order, "type", None)
            raw_deprecated_type = getattr(order, "order_type", None)
            order_type = _canonical_raw_order_type(
                raw_type, context="open-orders report row"
            )
            if (
                raw_deprecated_type is not None
                and order_type
                != _canonical_raw_order_type(
                    raw_deprecated_type, context="open-orders report row"
                )
            ):
                raise BrokerError(
                    "Alpaca open-orders report returned contradictory order types"
                )
            time_in_force = _canonical_report_time_in_force(
                getattr(order, "time_in_force", None),
                context="open-orders report row",
            )
            order_class = _canonical_report_order_class(
                getattr(order, "order_class", None),
                context="open-orders report row",
            )
            limit_price = _optional_positive_price(
                getattr(order, "limit_price", None),
                context="open-orders report row",
            )
            asset_class = _canonical_report_text(
                getattr(order, "asset_class", None),
                context="open-orders report row",
                field="asset class",
            )
            extended_hours = getattr(order, "extended_hours", None)
            if not isinstance(extended_hours, bool):
                raise BrokerError(
                    "Alpaca open-orders report returned malformed extended-hours scope"
                )
            legs = getattr(order, "legs", None)
            if legs is not None and not isinstance(legs, list):
                raise BrokerError("Alpaca open-orders report returned malformed legs")
            raw_position_intent = getattr(order, "position_intent", None)
            position_intent = (
                None
                if raw_position_intent is None
                else _canonical_report_text(
                    raw_position_intent,
                    context="open-orders report row",
                    field="position intent",
                )
            )
            advanced_fields = tuple(
                field
                for field in (
                    "stop_price",
                    "trail_price",
                    "trail_percent",
                    "hwm",
                    "ratio_qty",
                )
                if getattr(order, field, None) is not None
            )
            raw_replaces = getattr(order, "replaces", None)
            replaces_broker_order_id = (
                None
                if raw_replaces is None
                else _canonical_broker_id(
                    raw_replaces, context="open-orders report row predecessor"
                )
            )
            client_order_id = _optional_client_order_id(
                getattr(order, "client_order_id", None)
            )
            if broker_order_id in seen_broker_ids or (
                client_order_id is not None and client_order_id in seen_client_order_ids
            ):
                raise BrokerError(
                    "Alpaca returned a malformed open-orders report with "
                    "duplicate identity"
                )
            seen_broker_ids.add(broker_order_id)
            if client_order_id is not None:
                seen_client_order_ids.add(client_order_id)
            reports.append(
                BrokerOrderReport(
                    broker_order_id=broker_order_id,
                    client_order_id=client_order_id,
                    symbol=_canonical_report_symbol(
                        getattr(order, "symbol", None),
                        context="open-orders report row",
                    ),
                    side=_canonical_report_side(
                        getattr(order, "side", None),
                        context="open-orders report row",
                    ),
                    status=_map_open_report_status(getattr(order, "status", None)),
                    filled_quantity=filled_quantity,
                    fills=[],
                    quantity=quantity,
                    order_type=order_type,
                    limit_price=limit_price,
                    time_in_force=time_in_force,
                    order_class=order_class,
                    asset_class=asset_class,
                    quantity_mode=quantity_mode,
                    extended_hours=extended_hours,
                    has_legs=bool(legs),
                    position_intent=position_intent,
                    replaces_broker_order_id=replaces_broker_order_id,
                    advanced_fields=advanced_fields,
                )
            )
        return reports

    async def list_positions(self) -> list[BrokerPositionReport]:
        """The venue's current positions — the §7 position report.

        Wraps ``get_all_positions()``. Read-only. Raises ``BrokerError`` on failure
        (the caller must NOT read a failed query as flat). ``quantity`` is whole
        shares (beta is long-only, whole-share).
        """
        try:
            positions = cast(
                "list[AlpacaPosition]",
                await asyncio.to_thread(self._client.get_all_positions),
            )
        except Exception as exc:
            raise BrokerError("Failed to fetch the position report.") from exc
        if not isinstance(positions, list):
            raise BrokerError("Alpaca returned a malformed position report.")
        reports: list[BrokerPositionReport] = []
        seen_symbols: set[str] = set()
        for p in positions:
            symbol = _canonical_report_symbol(
                getattr(p, "symbol", None), context="position report row"
            )
            if symbol in seen_symbols:
                raise BrokerError(
                    "Alpaca returned a malformed position report with duplicate symbol"
                )
            seen_symbols.add(symbol)
            reports.append(
                BrokerPositionReport(
                    symbol=symbol,
                    quantity=_strict_whole_quantity(
                        getattr(p, "qty", None),
                        context="position report row",
                        allow_negative=True,
                    ),
                    average_price=_optional_positive_price(
                        getattr(p, "avg_entry_price", None),
                        context="position report row",
                    ),
                )
            )
        return reports

    # ---------------------------------------------------------------------- #
    # Internal helpers
    # ---------------------------------------------------------------------- #

    async def _get_fills(
        self,
        *,
        broker_order_id: str,
        filled_qty: int,
        recorded_quantity: int,
        filled_avg_price: Optional[object],
        limit_price: Optional[object],
        fallback_price: Optional[float] = None,
    ) -> list[BrokerFill]:
        """Return this order's fills as a single scalar **delta** over what's
        already recorded, under ONE consistent fill-identity scheme.

        The id is ``"<broker_order_id>:<cumulative filled_qty>"`` — stable per
        cumulative-fill level. So the StateStore's ``source_fill_id`` dedup is
        airtight: a repeated poll at the same level is ignored (delta 0), a new
        level appends exactly the increment, and a given share can never be
        counted twice.

        **Why not the per-execution activities API?** Mixing two id schemes — a
        synthetic id and a real Alpaca execution id for the *same* shares — would
        miss dedup and double-count the position (a real data-integrity defect:
        the activities API can be momentarily empty on one poll and recover on the
        next, re-reporting an already-counted fill under a different id). Beta uses
        average-cost math and defers realized/unrealized P/L, so per-execution
        price precision buys nothing here. Reintroducing the activities path for
        precision later requires making it *sticky per order* (an order never
        switches id schemes mid-life) before it is safe.
        """

        delta = filled_qty - recorded_quantity
        if delta <= 0:
            return []
        fill_price = _resolve_fill_price(filled_avg_price, limit_price, fallback_price)
        if fill_price is None:
            # AIR-002: the broker executed `delta` shares but exposes no
            # trustworthy price for them. Do NOT fabricate a 0.0 fill — omit it.
            # The BrokerOrderUpdate's `filled_quantity` still carries the broker's
            # cumulative truth, so monitoring sees `broker_filled > recorded` and
            # escalates to a durable needs_review reconciliation record instead of
            # recording a corrupt $0 execution.
            _log.error(
                "broker order %s reports filled_qty=%s but no trustworthy price "
                "(filled_avg_price=%r, limit_price=%r); surfacing as unrecordable.",
                broker_order_id,
                filled_qty,
                filled_avg_price,
                limit_price,
            )
            return []
        return [
            BrokerFill(
                source_fill_id=f"{broker_order_id}:{filled_qty}",
                quantity=delta,
                price=fill_price,
                filled_at=_utcnow(),
            )
        ]
