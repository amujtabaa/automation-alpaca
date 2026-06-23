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

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide as AlpacaOrderSide
from alpaca.trading.enums import TimeInForce
from alpaca.trading.requests import LimitOrderRequest

from app.broker.adapter import BrokerAdapter, BrokerError, BrokerFill, BrokerOrderUpdate
from app.models import Order, OrderSide, OrderStatus

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
    # Partial execution (still working remainder)
    "partially_filled": OrderStatus.PARTIALLY_FILLED,
    # Terminal — fully executed
    "filled": OrderStatus.FILLED,
    # Terminal — no longer active, not filled (treat as canceled)
    "canceled": OrderStatus.CANCELED,
    "expired": OrderStatus.CANCELED,
    "done_for_day": OrderStatus.CANCELED,
    "replaced": OrderStatus.CANCELED,
    "pending_cancel": OrderStatus.CANCELED,
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
        candidate/order model only produces limit orders in Phase 4).

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

        req = LimitOrderRequest(
            symbol=order.symbol,
            qty=order.quantity,
            side=alpaca_side,
            time_in_force=TimeInForce.DAY,
            limit_price=order.limit_price,
            client_order_id=order.id,  # idempotency key — see docstring
        )

        try:
            resp = await asyncio.to_thread(self._client.submit_order, req)
            return str(resp.id)
        except Exception as exc:
            exc_msg = str(exc).lower()
            # Alpaca rejects duplicate client_order_ids with a 422 or a message
            # mentioning "duplicate" or "client_order_id already exists".
            if "duplicate" in exc_msg or "client_order_id" in exc_msg:
                _log.info(
                    "Duplicate client_order_id detected for order %s; "
                    "looking up existing Alpaca order.",
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
            # Do NOT include exc in the message string — it may echo back
            # request params that could include keys if the SDK surfaces them.
            raise BrokerError(
                f"Failed to submit order {order.id!r} ({order.symbol} "
                f"{order.side} {order.quantity} shares)."
            ) from exc

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderUpdate:
        """Poll Alpaca for the current state of one open order.

        Prefers the activities API for per-execution fill ids (stable, dedup-safe).
        Falls back to a synthesised fill if the activities call fails or returns
        nothing while ``filled_qty > 0``.
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
        except Exception as exc:
            exc_msg = str(exc).lower()
            # Alpaca returns 404 or error messages like "not found",
            # "already canceled", "order is not cancelable", or similar
            # when the order is already in a terminal state.
            terminal_indicators = (
                "not found",
                "404",
                "already",
                "cannot be cancelled",
                "cannot be canceled",
                "not cancelable",
                "order is no longer",
                "terminal",
                "filled",
            )
            if any(indicator in exc_msg for indicator in terminal_indicators):
                _log.debug(
                    "cancel_order no-op: broker_order_id=%r is already terminal (%s).",
                    broker_order_id,
                    type(exc).__name__,
                )
                return  # idempotent — not an error
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
        filled_avg_price: Optional[object],
        limit_price: Optional[object],
    ) -> list[BrokerFill]:
        """Return fill records for this order.

        Preferred path: query account trade activities of type FILL for this
        order via ``TradingClient.get_activities``. Each activity carries
        Alpaca's own execution id (``activity.id``), which is the stable
        ``source_fill_id`` the StateStore uses for duplicate protection
        (dedup-safe across repeated polls).

        Fallback path (if the activities call fails or returns nothing while the
        order has fills): synthesise a single ``BrokerFill`` with a *stable*
        composite id ``"<broker_order_id>:<filled_qty>"``. This id is stable per
        cumulative-fill level — a repeated poll at the same fill level produces
        the same id (idempotent, dedup-safe), and advancing to a higher fill
        level produces a new id so the new partial fill is recorded. It is less
        precise than real execution ids (one synthetic fill vs. multiple
        partials), but it keeps the position truthful and the StateStore's
        duplicate-protection rule intact.
        """
        if filled_qty == 0:
            return []

        # --- Preferred: real activity records with Alpaca execution ids ---
        raw_activities = await self._fetch_fill_activities(broker_order_id)

        if raw_activities:
            fills: list[BrokerFill] = []
            for act in raw_activities:
                try:
                    act_id = str(act.id)
                    act_qty = int(float(getattr(act, "qty", 0) or 0))
                    act_price = float(getattr(act, "price", 0) or 0)
                    act_time: datetime = getattr(act, "transaction_time", None) or _utcnow()
                    if act_qty > 0:
                        fills.append(
                            BrokerFill(
                                source_fill_id=act_id,
                                quantity=act_qty,
                                price=act_price,
                                filled_at=act_time,
                            )
                        )
                except Exception:
                    _log.debug(
                        "Could not parse activity record for order %r — skipping.",
                        broker_order_id,
                    )
            if fills:
                return fills

        # --- Fallback: synthesise one fill from the order-level summary ---
        # The synthetic id is stable per (order, cumulative fill qty) so
        # repeated polls at the same fill level produce the same id (dedup-safe)
        # and a new fill level produces a new id (incremental fill detected).
        _log.debug(
            "Falling back to synthetic fill for order %r (filled_qty=%d).",
            broker_order_id,
            filled_qty,
        )
        fill_price: float
        if filled_avg_price is not None:
            try:
                fill_price = float(filled_avg_price)
            except (TypeError, ValueError):
                fill_price = float(limit_price or 0)
        elif limit_price is not None:
            try:
                fill_price = float(limit_price)
            except (TypeError, ValueError):
                fill_price = 0.0
        else:
            fill_price = 0.0

        return [
            BrokerFill(
                source_fill_id=f"{broker_order_id}:{filled_qty}",
                quantity=filled_qty,
                price=fill_price,
                filled_at=_utcnow(),
            )
        ]

    async def _fetch_fill_activities(self, broker_order_id: str) -> list[object]:
        """Fetch FILL-type account activities for ``broker_order_id``.

        ``TradingClient.get_activities`` is the correct alpaca-py endpoint for
        trade execution records. The SDK surface changed slightly between
        versions, so we try the most common call shapes and return an empty list
        on any failure — the caller falls back to a synthetic fill rather than
        crashing the monitoring loop.
        """
        # Attempt 1: pass activity_type and order_id filter directly (newer SDK).
        try:
            from alpaca.trading.requests import GetActivitiesRequest  # type: ignore[import]

            req = GetActivitiesRequest(
                activity_type="FILL",  # type: ignore[arg-type]
            )
            acts = await asyncio.to_thread(self._client.get_activities, req)
            if acts:
                # Filter to this specific order; Alpaca may not support order_id
                # filter in all SDK versions, so we do it client-side.
                matched = [
                    a for a in acts
                    if str(getattr(a, "order_id", "")) == broker_order_id
                ]
                if matched:
                    return matched
        except Exception:
            pass

        # Attempt 2: keyword-argument style (some SDK versions).
        try:
            acts = await asyncio.to_thread(
                self._client.get_activities,
                activity_type="FILL",
            )
            if acts:
                return [
                    a for a in acts
                    if str(getattr(a, "order_id", "")) == broker_order_id
                ]
        except Exception:
            pass

        return []
