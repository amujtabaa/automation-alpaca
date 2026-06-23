"""A fully controllable, in-memory ``BrokerAdapter`` for unit tests (Rule 9).

It makes no network calls and imports no SDK. Tests drive it explicitly:

* ``submit_order`` records the order and returns a deterministic broker id
  (``"broker-<order.id>"``), so assertions never depend on a random uuid.
* ``get_order_status`` returns whatever the test queued for that broker id
  (default: SUBMITTED, nothing filled).
* ``cancel_order`` records the call and marks the order canceled.
* Every call is recorded (``submitted`` / ``status_queries`` / ``canceled``) so
  tests can assert exact adapter interactions.
* ``fail_submit`` / ``fail_cancel`` make the next such call raise, to exercise
  the loop's log-and-continue error handling.
"""

from __future__ import annotations

from typing import Optional

from app.broker.adapter import BrokerAdapter, BrokerFill, BrokerOrderUpdate
from app.models import Order, OrderStatus


def _broker_id(order_id: str) -> str:
    return f"broker-{order_id}"


class MockBrokerAdapter(BrokerAdapter):
    def __init__(self) -> None:
        # Recorded calls (in order), for interaction assertions.
        self.submitted: list[Order] = []
        self.status_queries: list[str] = []
        self.canceled: list[str] = []

        # broker_order_id -> the update get_order_status will return.
        self._responses: dict[str, BrokerOrderUpdate] = {}
        # our order.id -> broker_order_id, so tests can set responses by order.
        self._broker_ids: dict[str, str] = {}

        # When set, the next submit/cancel raises this and then clears.
        self._submit_error: Optional[BaseException] = None
        self._cancel_error: Optional[BaseException] = None

    # ------------------------------------------------------------------ #
    # BrokerAdapter
    # ------------------------------------------------------------------ #
    async def submit_order(self, order: Order) -> str:
        self.submitted.append(order)
        if self._submit_error is not None:
            err, self._submit_error = self._submit_error, None
            raise err
        broker_order_id = _broker_id(order.id)
        self._broker_ids[order.id] = broker_order_id
        # Default broker view of a freshly-submitted order: accepted, no fills.
        self._responses.setdefault(
            broker_order_id, BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, [])
        )
        return broker_order_id

    async def get_order_status(self, broker_order_id: str) -> BrokerOrderUpdate:
        self.status_queries.append(broker_order_id)
        return self._responses.get(
            broker_order_id, BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, [])
        )

    async def cancel_order(self, broker_order_id: str) -> None:
        self.canceled.append(broker_order_id)
        if self._cancel_error is not None:
            err, self._cancel_error = self._cancel_error, None
            raise err
        # Reflect the cancel in subsequent polls (idempotent: keep any fills).
        prior = self._responses.get(broker_order_id)
        filled = prior.filled_quantity if prior else 0
        fills = prior.fills if prior else []
        self._responses[broker_order_id] = BrokerOrderUpdate(
            OrderStatus.CANCELED, filled, fills
        )

    # ------------------------------------------------------------------ #
    # Test controls
    # ------------------------------------------------------------------ #
    def broker_id_for(self, order_id: str) -> str:
        """The broker id assigned to a submitted order."""

        return self._broker_ids[order_id]

    def set_response(self, broker_order_id: str, update: BrokerOrderUpdate) -> None:
        """Queue the update a future ``get_order_status`` will return."""

        self._responses[broker_order_id] = update

    def set_response_for_order(self, order_id: str, update: BrokerOrderUpdate) -> None:
        """Queue an update keyed by our order id (must have been submitted)."""

        self._responses[self._broker_ids[order_id]] = update

    def make_fill(
        self,
        order_id: str,
        *,
        status: OrderStatus,
        filled_quantity: int,
        fills: list[BrokerFill],
    ) -> None:
        """Convenience: set a fill response for a submitted order."""

        self.set_response_for_order(
            order_id, BrokerOrderUpdate(status, filled_quantity, fills)
        )

    def fail_next_submit(self, exc: BaseException) -> None:
        self._submit_error = exc

    def fail_next_cancel(self, exc: BaseException) -> None:
        self._cancel_error = exc
