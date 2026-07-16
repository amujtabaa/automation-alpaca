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
from app.models import Order, OrderSide, OrderStatus


def _broker_id(order_id: str) -> str:
    return f"broker-{order_id}"


# A venue order in one of these statuses is no longer "open at the venue" — a
# mass order-status report (get_orders(status=OPEN)) would not return it.
_VENUE_TERMINAL = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED}
)


class MockBrokerAdapter(BrokerAdapter):
    def __init__(self) -> None:
        # Recorded calls (in order), for interaction assertions.
        self.submitted: list[Order] = []
        self.status_queries: list[str] = []
        self.canceled: list[str] = []
        self.client_queries: list[str] = []  # get_order_by_client_order_id calls
        # replace_order calls: (old_broker_id, client_order_id, limit, qty).
        self.replaced: list[tuple[str, str, Optional[float], Optional[int]]] = []

        # broker_order_id -> the update get_order_status will return.
        self._responses: dict[str, BrokerOrderUpdate] = {}
        # our order.id -> broker_order_id, so tests can set responses by order.
        self._broker_ids: dict[str, str] = {}
        # client_order_id (= order.id) -> the venue state a targeted query returns
        # (ADR-002). Seeded independently of submit_order so a test can simulate
        # "the ambiguous submit DID reach the venue" even though submit raised.
        self._venue_by_client_id: dict[str, BrokerOrderUpdate] = {}

        # §7 mass reports (wave 4a). Recorded-call counters let tests assert the
        # reconciler polled them.
        #
        # ``_open_order_reports`` is a SENTINEL: ``None`` (default) means "derive the
        # venue's open orders from this adapter's own known-live submits" (wave 4e-3
        # E5 fidelity — a self-consistent venue mirror, so a locally-open order the
        # adapter accepted is never spuriously *absent* from its own mass report). An
        # explicit ``seed_open_orders`` overrides it with a fixed list (e.g. to inject
        # an external/unmanaged order, or model an order the venue dropped).
        self._open_order_reports: Optional[list[BrokerOrderReport]] = None
        self._position_reports: list[BrokerPositionReport] = []
        self.open_order_report_queries: int = 0
        self.position_report_queries: int = 0

        # When set, the next submit/cancel/replace/client-query/report raises
        # this and clears.
        self._submit_error: Optional[BaseException] = None
        self._cancel_error: Optional[BaseException] = None
        self._replace_error: Optional[BaseException] = None
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

    async def replace_order(
        self,
        broker_order_id: str,
        *,
        client_order_id: str,
        limit_price: Optional[float] = None,
        quantity: Optional[int] = None,
    ) -> str:
        # WO-0019a: deterministic venue-side replace. The old order goes
        # terminal (Alpaca marks it "replaced"; our OrderStatus vocabulary maps
        # that to CANCELED) with its observed fills preserved; the replacement
        # gets the deterministic ``broker-<client_order_id>`` id and is
        # discoverable by client id (the ADR-002 ambiguous-replace recovery).
        self.replaced.append((broker_order_id, client_order_id, limit_price, quantity))
        if self._replace_error is not None:
            err, self._replace_error = self._replace_error, None
            raise err
        prior = self._responses.get(broker_order_id)
        filled = prior.filled_quantity if prior else 0
        fills = prior.fills if prior else []
        self._responses[broker_order_id] = BrokerOrderUpdate(
            OrderStatus.CANCELED, filled, fills
        )
        new_broker_id = _broker_id(client_order_id)
        self._broker_ids[client_order_id] = new_broker_id
        self._responses.setdefault(
            new_broker_id, BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, [])
        )
        return new_broker_id

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
        # list read as "no open orders"). Unseeded → DERIVE from known-live submits
        # (wave 4e-3 E5): the venue mirror is self-consistent with what this adapter
        # accepted, so a locally-open managed order is reported open (matched, not a
        # false not-found). An explicit seed overrides the derivation.
        self.open_order_report_queries += 1
        if self._open_orders_error is not None:
            err, self._open_orders_error = self._open_orders_error, None
            raise err
        if self._open_order_reports is not None:
            return list(self._open_order_reports)
        return self._derive_open_order_reports()

    def _derive_open_order_reports(self) -> list[BrokerOrderReport]:
        """The venue's open orders inferred from this adapter's own submits: every
        successfully-submitted order (has a minted broker id) whose current venue
        status is non-terminal. Keyed on the deterministic client_order_id (= our
        order id), so the reconciler matches it to the local order."""

        submitted_by_id = {o.id: o for o in self.submitted}
        reports: list[BrokerOrderReport] = []
        for order_id, broker_id in self._broker_ids.items():
            status, filled = self._venue_view(broker_id)
            if status in _VENUE_TERMINAL:
                continue
            order = submitted_by_id.get(order_id)
            if order is None:  # can't build a report without symbol/side
                continue
            reports.append(
                BrokerOrderReport(
                    broker_order_id=broker_id,
                    client_order_id=order_id,
                    symbol=order.symbol,
                    side=OrderSide(order.side),
                    status=status,
                    filled_quantity=filled,
                )
            )
        return reports

    def _venue_view(self, broker_id: str) -> tuple[OrderStatus, int]:
        """The venue's current (status, filled_quantity) for a broker id — the mock
        reads its ``_responses`` map (default: SUBMITTED / 0). ``SimBrokerAdapter``
        overrides this to prefer a consumed script update, mirroring ``is_live``."""

        resp = self._responses.get(broker_id)
        if resp is None:
            return OrderStatus.SUBMITTED, 0
        return resp.status, resp.filled_quantity

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
        """Override the derived venue mirror with a fixed OPEN-orders list (§7) —
        e.g. to inject an external/unmanaged order or model an order the venue
        dropped. Without this, ``list_open_orders`` derives from known-live submits."""

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

    def seed_venue_order(self, client_order_id: str, update: BrokerOrderUpdate) -> None:
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

    def fail_next_replace(self, exc: BaseException) -> None:
        """Make the next ``replace_order`` raise ``exc`` (then clear) — e.g. an
        :class:`AmbiguousBrokerError` to exercise the quarantine-not-blind-
        re-replace path."""

        self._replace_error = exc

    def fail_next_client_query(self, exc: BaseException) -> None:
        """Make the next ``get_order_by_client_order_id`` raise ``exc`` (a query
        FAILURE, distinct from a confirmed not-found). The caller must keep the
        order quarantined, never treat a failed query as 'absent' (§7)."""

        self._client_query_error = exc
