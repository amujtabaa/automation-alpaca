"""The ``BrokerAdapter`` interface — the only seam through which the backend
talks to a broker.

Same pluggable-ABC pattern as :class:`~app.approval.gate.ApprovalGate`: route
handlers and the monitoring loop depend on this interface, never on a concrete
adapter. Beta ships exactly one real implementation
(:class:`~app.broker.alpaca_paper.AlpacaPaperAdapter`, paper-only) plus a fully
controllable :class:`~app.broker.mock.MockBrokerAdapter` for IO-free unit tests
(Rule 9). A future live adapter is a drop-in here — no caller changes.

Nothing in this module imports the ``alpaca`` SDK; the interface is pure so it
can be imported anywhere (including the standard test suite) without the SDK or
any credentials present.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.models import Order, OrderStatus


class BrokerError(Exception):
    """A broker operation failed (network error, bad broker response, ...).

    Adapters raise this (or a subclass) for failures the caller may want to
    handle. The monitoring loop logs-and-continues on these; it never lets one
    transient broker error stop the loop.

    **Transient by default.** A plain ``BrokerError`` is treated as a *retryable*
    failure — a network blip, a timeout, a momentary 5xx. The stale-``SUBMITTING``
    recovery step (AIR-003) leaves the order ``SUBMITTING`` and re-drives it on the
    next tick (safe: the stable ``client_order_id`` makes re-submit idempotent).
    Raise :class:`TerminalBrokerError` instead when the failure is *definitive*.
    """


class TerminalBrokerError(BrokerError):
    """A broker submit failed definitively and cannot be safely retried (AIR-003).

    The submit was rejected in a way that will not succeed on retry, *or* the
    order's fate cannot be confirmed (e.g. a duplicate ``client_order_id`` whose
    existing order could not then be looked up). The stale-``SUBMITTING`` recovery
    step does **not** keep re-driving one of these — it escalates the order to a
    durable, operator-visible ``needs_review`` recovery record instead of guessing.
    """


@dataclass(frozen=True)
class BrokerFill:
    """A single execution report from the broker.

    ``source_fill_id`` is the broker's own execution/fill id; it is what the
    StateStore uses to make ``append_fill`` idempotent (D-006 duplicate
    protection). ``quantity`` is whole shares — beta is long-only, whole-share
    (Order.quantity is an int), so the adapter maps the broker's filled amount
    to an int rather than carrying fractional shares the rest of the system
    can't represent.
    """

    source_fill_id: str
    quantity: int
    price: float
    filled_at: datetime


@dataclass(frozen=True)
class BrokerOrderUpdate:
    """The broker-side state of an order at one point in time.

    ``status`` is already mapped to our :class:`OrderStatus` by the adapter (the
    loop never sees raw broker strings). ``filled_quantity`` is the broker's
    cumulative filled amount. ``fills`` are the executions the adapter observed;
    the loop appends each one and relies on the store's ``source_fill_id`` dedup,
    so an adapter may safely return all known fills every poll rather than
    tracking "new since last poll" itself.
    """

    status: OrderStatus
    filled_quantity: int
    fills: list[BrokerFill] = field(default_factory=list)


class BrokerAdapter(ABC):
    """Abstract broker interface. All methods are async."""

    @abstractmethod
    async def submit_order(self, order: Order) -> str:
        """Submit ``order`` to the broker. Returns the broker's order id.

        **Contract (AIR-001):** an implementation MUST return a **non-empty**
        ``str`` broker id, or raise :class:`BrokerError`. It must never return
        ``None``, ``""``, or a whitespace-only string — the returned id is stored
        as ``broker_order_id`` and is the *only* key used to poll and cancel, so an
        empty id would create an untrackable "submitted" order. The store enforces
        the mirror of this invariant: a ``SUBMITTING → SUBMITTED`` transition with
        a missing/empty ``broker_order_id`` is rejected.

        Raise :class:`BrokerError` for a transient failure (the caller leaves the
        order unsubmitted / ``SUBMITTING`` and retries next tick) or
        :class:`TerminalBrokerError` for a definitive one (the caller escalates to
        a durable ``needs_review`` record rather than retrying).

        **Idempotency (AIR-003):** the implementation submits with a stable
        ``client_order_id`` (``order.id``) so a retry after a crash between
        submit-and-persist recovers the already-accepted broker order rather than
        double-submitting. This is what makes re-driving a stale ``SUBMITTING``
        order safe.
        """

    @abstractmethod
    async def get_order_status(
        self,
        broker_order_id: str,
        *,
        recorded_quantity: int = 0,
        fallback_price: Optional[float] = None,
    ) -> BrokerOrderUpdate:
        """Poll the broker for the current state of an order.

        Called on the monitoring cadence for every open order. ``recorded_quantity``
        is how many shares the backend has *already* recorded as filled for this
        order (its current ``filled_quantity``). An adapter that has true
        per-execution fill ids ignores it; one that can only see the broker's
        *cumulative* filled amount uses it to emit a single fill for the **delta**
        (``cumulative - recorded_quantity``) rather than re-reporting the whole
        cumulative (which the store would reject as an overfill). Raises
        :class:`BrokerError` on failure.

        ``fallback_price`` (Phase 7 §7) is a last-resort *audit* price for a fill
        the broker reports with no trustworthy ``filled_avg_price`` **and** no
        ``limit_price`` — i.e. a MARKET order (which has no limit). The monitoring
        reconcile path passes the reconcile-time snapshot ``last_price`` here for a
        MARKET order so a transiently-absent execution price never withholds a
        position-critical protective-sell fill (which, with the single-flight
        dedup, would strand protection). A long-only fill's exact price does not
        change the quantity/cost-basis fold — it is for the record. Adapters whose
        fills always carry a real price (the mock/sim) accept and ignore it.
        """

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> None:
        """Cancel an open order.

        Idempotent: cancelling an order that is already terminal (filled,
        canceled, gone) is a no-op success, not an error — the order is no longer
        live either way. Raises :class:`BrokerError` only on a genuine failure.
        """
