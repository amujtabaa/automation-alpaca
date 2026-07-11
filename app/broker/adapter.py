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

from app.models import Order, OrderSide, OrderStatus


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


class AmbiguousBrokerError(BrokerError):
    """A submit whose outcome is genuinely UNKNOWN (ADR-002 / Spine v2 wave 3c).

    A timeout, HTTP 504, transport failure, disconnect, or a response parse
    failure *after the request may have reached Alpaca* — the order may be live,
    filled, rejected, or never-arrived, and we cannot tell. This is neither a
    safe-to-retry transient (plain :class:`BrokerError` — the request provably did
    not reach the book, e.g. a pre-flight 429 rate-limit) nor a definitive reject
    (:class:`TerminalBrokerError`). The monitoring loop must move the order to
    ``TIMEOUT_QUARANTINE`` and reconcile it with a **read-only targeted query by
    ``client_order_id``** (``get_order_by_client_order_id``) rather than blind-
    resubmitting — a resubmit could double-fire an order that is already live
    (oversell/short-flip risk). The adapter classifies (§6): only IT knows whether
    the HTTP/transport failure happened before or after the request left. Being a
    ``BrokerError`` subclass, existing ``except BrokerError`` handlers still catch
    it; callers that must NOT blind-redrive route on the subclass explicitly.
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

    ``broker_order_id`` is populated ONLY by ``get_order_by_client_order_id``
    (ADR-002): the whole point of that targeted query is to learn the venue id of
    an order we submitted under a ``client_order_id`` but whose ack we never got,
    so the caller can adopt it. ``get_order_status`` leaves it ``None`` — its
    caller already holds the id it polled by.
    """

    status: OrderStatus
    filled_quantity: int
    fills: list[BrokerFill] = field(default_factory=list)
    broker_order_id: Optional[str] = None


@dataclass(frozen=True)
class BrokerOrderReport:
    """One row of the broker's **mass** order-status report (§7 reconciliation).

    Unlike :meth:`BrokerAdapter.get_order_status` (keyed on a venue id we already
    hold), the mass report is how reconciliation DISCOVERS the venue's order set —
    including an order the backend does not know about (external/unmanaged, surfaced
    never silently absorbed) — and confirms/denies the presence of cached ones. It
    carries BOTH ids so the reconciler can match a report row to a local order by
    ``client_order_id`` (our deterministic ``order.id``) or ``broker_order_id``.
    ``status`` is already mapped to our :class:`OrderStatus`; ``fills`` lets the
    reconciler infer missing executions (deterministic synthetic ids, §3).
    """

    broker_order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: OrderSide
    status: OrderStatus
    filled_quantity: int
    fills: list[BrokerFill] = field(default_factory=list)


@dataclass(frozen=True)
class BrokerPositionReport:
    """One row of the broker's position report (§7 position parity).

    ``quantity`` is whole shares (beta is long-only, whole-share). ``average_price``
    is the venue's average entry price (``None`` if the venue reports none). The
    reconciler compares this against the locally-derived position within tolerance
    (qty exact, avg-px 0.01%) and surfaces a mismatch for review — it never silently
    overwrites the local fill-derived position.
    """

    symbol: str
    quantity: int
    average_price: Optional[float] = None


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

    @abstractmethod
    async def replace_order(
        self,
        broker_order_id: str,
        *,
        client_order_id: str,
        limit_price: Optional[float] = None,
        quantity: Optional[int] = None,
    ) -> str:
        """Venue-side atomic cancel/replace of a live order (WO-0019a, the
        envelope executor's reprice seam — ADR-009 §1).

        One venue round-trip: the working order is replaced without a window
        in which zero orders (lost queue position, unprotected book) or two
        orders (double exposure) rest. Returns the broker id of the
        **replacement** order (Alpaca's replace creates a new order); the old
        ``broker_order_id`` becomes terminal at the venue.

        **Contract (mirrors ``submit_order``):**

        * MUST return a non-empty ``str`` id for the replacement, never
          ``None``/empty (AIR-001 — the returned id becomes the only poll/
          cancel key for the working order).
        * ``client_order_id`` is REQUIRED and must be deterministic per
          replace attempt: it is the replacement's idempotency key, so a
          crash-then-retry of the SAME replace adopts the already-created
          replacement (duplicate-id recovery) instead of minting a second
          one, and an ambiguous outcome is resolvable by the existing
          read-only ``get_order_by_client_order_id`` query (ADR-002) — the
          caller must NEVER blind-re-replace.
        * Error taxonomy is identical to submit: plain :class:`BrokerError`
          for a provably-pre-flight transient (e.g. 429), a
          :class:`TerminalBrokerError` for a definitive rejection, and
          :class:`AmbiguousBrokerError` when the request may have reached the
          venue (timeout/5xx/transport) — the caller quarantines and
          reconciles by ``client_order_id``, exactly like an ambiguous
          submit.
        """

    @abstractmethod
    async def get_order_by_client_order_id(
        self, client_order_id: str
    ) -> Optional[BrokerOrderUpdate]:
        """Read-only targeted query by our deterministic ``client_order_id``
        (ADR-002 / Spine v2 wave 3c).

        After an ambiguous submit (:class:`AmbiguousBrokerError`) the order has
        NO ``broker_order_id``, so ``get_order_status`` (keyed on the venue id)
        cannot be used to find out what actually happened. This method asks the
        venue "do you have the order I submitted under ``client_order_id``?" using
        the stable ``client_order_id = order.id`` (AIR-003), and is the ONLY way a
        ``TIMEOUT_QUARANTINE`` order is resolved.

        **Contract:**
        * returns the mapped :class:`BrokerOrderUpdate` when the venue HAS the
          order (working/filled/etc.) — the caller adopts it (no resubmit);
        * returns ``None`` ONLY when the venue *confirms* the order does not exist
          (a definitive not-found / 404) — the submit never landed;
        * raises :class:`BrokerError` on a query FAILURE (network/5xx/etc.). A
          failed query must NEVER be read as "absent" (§7 safeguard: treating an
          inconclusive query as flat/rejected is an oversell path) — the caller
          keeps the order quarantined and retries.

        This is strictly read-only: it never creates, cancels, or mutates a venue
        order, so it can never double-submit.
        """

    @abstractmethod
    async def list_open_orders(self) -> list["BrokerOrderReport"]:
        """The venue's current OPEN orders — the mass order-status report (§7).

        Read-only. Reconciliation uses this (not the per-order ``get_order_status``,
        which needs a venue id we already hold) to DISCOVER the full venue open-order
        set: to confirm/deny the presence of cached orders and to surface an order the
        venue has that the backend does not (external/unmanaged — never silently
        absorbed). Raises :class:`BrokerError` on failure. **A failed report must NEVER
        be read as "no open orders"** (§7 safeguard: treating an inconclusive query as
        empty is a not-found→reject / oversell path) — the caller skips the cycle and
        retries, it does not resolve absences from a failed report.
        """

    @abstractmethod
    async def list_positions(self) -> list["BrokerPositionReport"]:
        """The venue's current positions — the position report (§7 position parity).

        Read-only. The reconciler compares each row against the locally fill-derived
        position within tolerance (qty exact, avg-px 0.01%). Raises
        :class:`BrokerError` on failure. **A failed position query must NEVER be read
        as flat** (§7 safeguard) — the caller skips this cycle, never inferring a
        flatten/close from a missing report.
        """
