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

from dataclasses import replace
from typing import Optional

from app.broker.adapter import (
    BrokerAdapter,
    BrokerFill,
    BrokerOrderReport,
    BrokerOrderUpdate,
    BrokerPositionReport,
)
from app.models import Order, OrderStatus


def _broker_id(order_id: str) -> str:
    return f"broker-{order_id}"


class MockBrokerAdapter(BrokerAdapter):
    def __init__(self) -> None:
        # Recorded calls (in order), for interaction assertions.
        self.submitted: list[Order] = []
        self.status_queries: list[str] = []
        self.canceled: list[str] = []
        self.client_queries: list[str] = []  # get_order_by_client_order_id calls

        # broker_order_id -> the update get_order_status will return.
        self._responses: dict[str, BrokerOrderUpdate] = {}
        # our order.id -> broker_order_id, so tests can set responses by order.
        self._broker_ids: dict[str, str] = {}
        # client_order_id (= order.id) -> the venue state a targeted query returns
        # (ADR-002). Seeded independently of submit_order so a test can simulate
        # "the ambiguous submit DID reach the venue" even though submit raised.
        self._venue_by_client_id: dict[str, BrokerOrderUpdate] = {}

        # §7 mass reports (wave 4a). Seeded independently — the venue's current
        # OPEN orders + positions the reconciler discovers. Recorded-call counters
        # let tests assert the reconciler polled them.
        self._open_order_reports: list[BrokerOrderReport] = []
        self._position_reports: list[BrokerPositionReport] = []
        self.open_order_report_queries: int = 0
        self.position_report_queries: int = 0

        # When set, the next submit/cancel/client-query/report raises this and clears.
        self._submit_error: Optional[BaseException] = None
        self._cancel_error: Optional[BaseException] = None
        self._client_query_error: Optional[BaseException] = None
        self._open_orders_error: Optional[BaseException] = None
        self._positions_error: Optional[BaseException] = None

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

    async def get_order_status(
        self,
        broker_order_id: str,
        *,
        recorded_quantity: int = 0,
        fallback_price: Optional[float] = None,
    ) -> BrokerOrderUpdate:
        # The mock returns explicit per-execution fills the test queued, so it
        # ignores recorded_quantity (it never needs the cumulative->delta trick)
        # and fallback_price (its fills always carry a real price — §7 accept+ignore).
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

    async def get_order_by_client_order_id(
        self, client_order_id: str
    ) -> Optional[BrokerOrderUpdate]:
        # Read-only targeted query (ADR-002). Never mutates venue state.
        self.client_queries.append(client_order_id)
        if self._client_query_error is not None:
            err, self._client_query_error = self._client_query_error, None
            raise err  # a query FAILURE — the caller must NOT read this as absent
        # An explicitly seeded venue order (e.g. an ambiguous submit that reached
        # the venue) wins; else a successfully-submitted order is findable by its
        # client id; else the venue confirms it does not exist (None).
        if client_order_id in self._venue_by_client_id:
            return self._venue_by_client_id[client_order_id]
        broker_id = self._broker_ids.get(client_order_id)
        if broker_id is not None:
            update = self._responses.get(
                broker_id, BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, [])
            )
            return replace(update, broker_order_id=broker_id)
        return None

    async def list_open_orders(self) -> list[BrokerOrderReport]:
        # §7 mass order-status report (wave 4a). A failure raises (never an empty
        # list read as "no open orders").
        self.open_order_report_queries += 1
        if self._open_orders_error is not None:
            err, self._open_orders_error = self._open_orders_error, None
            raise err
        return list(self._open_order_reports)

    async def list_positions(self) -> list[BrokerPositionReport]:
        # §7 position report (wave 4a). A failure raises (never read as flat).
        self.position_report_queries += 1
        if self._positions_error is not None:
            err, self._positions_error = self._positions_error, None
            raise err
        return list(self._position_reports)

    # ------------------------------------------------------------------ #
    # Test controls
    # ------------------------------------------------------------------ #
    def seed_open_orders(self, reports: list[BrokerOrderReport]) -> None:
        """Set the venue's current OPEN orders the mass report returns (§7)."""

        self._open_order_reports = list(reports)

    def seed_positions(self, reports: list[BrokerPositionReport]) -> None:
        """Set the venue's current positions the position report returns (§7)."""

        self._position_reports = list(reports)

    def fail_next_open_orders(self, exc: BaseException) -> None:
        """Make the next ``list_open_orders`` raise (a report FAILURE — the caller
        must skip the cycle, never read it as 'no open orders')."""

        self._open_orders_error = exc

    def fail_next_positions(self, exc: BaseException) -> None:
        """Make the next ``list_positions`` raise (a query FAILURE — the caller must
        skip the cycle, never read it as flat)."""

        self._positions_error = exc

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

    def seed_venue_order(
        self, client_order_id: str, update: BrokerOrderUpdate
    ) -> None:
        """Simulate that the venue HAS an order under ``client_order_id`` (ADR-002)
        — e.g. an ambiguous submit that actually reached Alpaca even though
        ``submit_order`` raised. Independent of the submit path, so a test can set
        it up after ``fail_next_submit(AmbiguousBrokerError(...))``. If ``update``
        carries no ``broker_order_id``, the deterministic ``broker-<id>`` is filled
        in so the caller can adopt a concrete venue id."""

        if update.broker_order_id is None:
            update = replace(update, broker_order_id=_broker_id(client_order_id))
        self._venue_by_client_id[client_order_id] = update

    def fail_next_submit(self, exc: BaseException) -> None:
        self._submit_error = exc

    def fail_next_cancel(self, exc: BaseException) -> None:
        self._cancel_error = exc

    def fail_next_client_query(self, exc: BaseException) -> None:
        """Make the next ``get_order_by_client_order_id`` raise ``exc`` (a query
        FAILURE, distinct from a confirmed not-found). The caller must keep the
        order quarantined, never treat a failed query as 'absent' (§7)."""

        self._client_query_error = exc
