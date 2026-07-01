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
from datetime import datetime, timezone
from typing import Optional

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import TimeInForce
from alpaca.trading.requests import LimitOrderRequest

from app.broker.adapter import BrokerAdapter, BrokerError, BrokerFill, BrokerOrderUpdate
from app.features import session_type_for
from app.models import Order, OrderSide, OrderStatus, SessionType, utcnow

_log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Alpaca order-status → our OrderStatus
# --------------------------------------------------------------------------- #

# Map every documented Alpaca order status to our canonical OrderStatus.
# Source: https://docs.alpaca.markets/reference/getallorders-1 (status field).
# Unknown / unrecognised statuses default to SUBMITTED (still open) with a
# warning — we never raise on an unmapped status so a new status from Alpaca
# doesn't crash the monitoring loop.
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
    "done_for_day": OrderStatus.CANCELED,
    "replaced": OrderStatus.CANCELED,
    # Terminal — broker-rejected or administratively stopped
    "rejected": OrderStatus.REJECTED,
    "suspended": OrderStatus.REJECTED,
    "stopped": OrderStatus.REJECTED,
}


def _map_status(raw_status: object) -> OrderStatus:
    """Normalise an Alpaca status (enum *or* str) to our ``OrderStatus``.

    The SDK may return an ``AlpacaOrderStatus`` enum or a plain string depending
    on SDK version; ``getattr(v, "value", v)`` handles both.
    """
    normalised = str(getattr(raw_status, "value", raw_status)).lower()
    mapped = _ALPACA_STATUS_MAP.get(normalised)
    if mapped is None:
        _log.warning(
            "Unrecognised Alpaca order status %r — treating as SUBMITTED (still open).",
            normalised,
        )
        return OrderStatus.SUBMITTED
    return mapped


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_fill_price(
    filled_avg_price: Optional[object], limit_price: Optional[object]
) -> float:
    """Best available price for a synthetic delta fill: the broker's filled
    average if present, else the order's limit, else 0.0. Tolerant of the SDK's
    string/Decimal/None shapes."""

    for candidate in (filled_avg_price, limit_price):
        if candidate is None:
            continue
        try:
            return float(candidate)
        except (TypeError, ValueError):
            continue
    return 0.0


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

    async def submit_order(self, order: Order) -> str:
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
        extended_hours = current_session in (
            SessionType.PRE_MARKET,
            SessionType.AFTER_HOURS,
        )

        req = LimitOrderRequest(
            symbol=order.symbol,
            qty=order.quantity,
            side=alpaca_side,
            time_in_force=TimeInForce.DAY,
            extended_hours=extended_hours,
            limit_price=order.limit_price,
            client_order_id=order.id,  # idempotency key — see docstring
        )

        try:
            resp = await asyncio.to_thread(self._client.submit_order, req)
            return str(resp.id)
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
                    existing = await asyncio.to_thread(
                        self._client.get_order_by_client_order_id, order.id
                    )
                    return str(existing.id)
                except Exception as lookup_exc:
                    raise BrokerError(
                        f"Duplicate submit for order {order.id!r}: original submit "
                        f"rejected but lookup of existing order also failed."
                    ) from lookup_exc
            # Do NOT include exc in the message string — it may echo back request
            # params that could include keys if the SDK surfaces them.
            raise BrokerError(
                f"Failed to submit order {order.id!r} ({order.symbol} "
                f"{order.quantity} shares)."
            ) from exc
        except Exception as exc:
            # Network/timeout/unknown — a real failure, surfaced (never silent).
            raise BrokerError(
                f"Failed to submit order {order.id!r} ({order.symbol} "
                f"{order.quantity} shares)."
            ) from exc

    async def get_order_status(
        self, broker_order_id: str, *, recorded_quantity: int = 0
    ) -> BrokerOrderUpdate:
        """Poll Alpaca for the current state of one open order.

        Prefers the activities API for per-execution fill ids (stable, dedup-safe).
        Falls back to a synthesised fill if the activities call fails or returns
        nothing while ``filled_qty > 0`` — sized as the **delta** over
        ``recorded_quantity`` so it never re-reports already-counted shares.
        """
        try:
            alpaca_order = await asyncio.to_thread(
                self._client.get_order_by_id, broker_order_id
            )
        except Exception as exc:
            raise BrokerError(
                f"Failed to fetch order status for broker_order_id={broker_order_id!r}."
            ) from exc

        status = _map_status(alpaca_order.status)
        filled_qty = int(float(alpaca_order.filled_qty or 0))

        fills = await self._get_fills(
            broker_order_id=broker_order_id,
            filled_qty=filled_qty,
            recorded_quantity=recorded_quantity,
            filled_avg_price=alpaca_order.filled_avg_price,
            limit_price=alpaca_order.limit_price,
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
            await asyncio.to_thread(
                self._client.cancel_order_by_id, broker_order_id
            )
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
        fill_price = _resolve_fill_price(filled_avg_price, limit_price)
        return [
            BrokerFill(
                source_fill_id=f"{broker_order_id}:{filled_qty}",
                quantity=delta,
                price=fill_price,
                filled_at=_utcnow(),
            )
        ]
