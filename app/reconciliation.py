"""Pure reconciliation engine — §7 / Spine v2 §2 module 5 (Phase 4 wave 4b).

Deterministic and IO-free: it folds a snapshot of

  (local open orders, local positions, broker order-status report, broker
   position report, ``now``)

into a :class:`ReconciliationPlan` the impure caller (the monitoring loop)
then acts on — running the targeted single-order queries the plan requests and
applying the transitions / synthetic fills through the single-writer store.

**Why a pure engine.** All decisions come from the reports + an injected clock —
no network, no wall-clock, no RNG (§12). That is what makes the §7 invariants
(no oversell via a spurious not-found→REJECTED; never treat a query failure as
flat; deterministic synthetic ids) property-testable over thousands of
interleavings, exactly as the single-writer core made the §5 invariants testable.

**What it does NOT do (by design, load-bearing safeguards).**
- It never resolves a locally-open order that is *absent* from the mass report to
  ``REJECTED`` itself: absence only produces a ``needs_targeted_query`` request.
  The §7 "targeted-query-before-not-found→REJECTED" safeguard lives with the
  impure caller (which owns the ``open_check_missing_retries`` budget and the
  read-only ``get_order_by_client_order_id`` call), so a transient missing row can
  never become an oversell path here.
- It never *overwrites* a local position from the broker report: a divergence
  beyond tolerance surfaces as a :class:`PositionMismatch` for review — position
  truth stays the deduped fill log (Rule 7 / INV-1).
- It never fabricates a fill price. A broker ``filled_quantity`` above what we have
  recorded, with no priced execution in the report, surfaces as a
  ``needs_targeted_query`` (fetch the price via the per-order poll) — never a $0
  synthetic fill (mirrors the adapter's AIR-002 stance).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from app.broker.adapter import BrokerOrderReport, BrokerPositionReport
from app.models import Order, OrderSide, OrderStatus, Position

# Local order statuses that are "open at the venue" and therefore reconcilable
# against the mass report (mirrors monitoring._OPEN_STATUSES). CANCEL_PENDING is
# included: the venue may have finalized the cancel (or a late fill).
OPEN_STATUSES = frozenset(
    {
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
    }
)

# Broker terminal statuses the engine may resolve DIRECTLY from the mass report,
# because they do not change position quantity (Rule 7): a cancel/reject only
# releases the reservation. FILLED/PARTIALLY_FILLED are deliberately excluded —
# those must flow through a fill (with a real price), never a bare status flip.
# (OrderStatus has no EXPIRED — that is a candidate/sell-intent status.)
_NON_POSITION_TERMINALS = frozenset(
    {OrderStatus.CANCELED, OrderStatus.REJECTED}
)

# Default parity/threshold values (the §7 verified defaults land in config.py in
# wave 4e; these keep the pure engine usable + testable standalone).
DEFAULT_RECENT_ORDER_THRESHOLD_MS = 5000  # open_check_threshold_ms (§7)
DEFAULT_AVG_PRICE_TOLERANCE = 0.0001      # 0.01% (§7)


@dataclass(frozen=True)
class InferredFill:
    """A fill the reconciler infers from the broker report (a priced execution the
    local log is missing). ``quantity`` is the DELTA over what we already recorded;
    ``dedupe_key`` is a deterministic synthetic id (§3 / R8) so a restart replay —
    or a real fill later observed for the same shares — dedups to one, never
    double-counting the position (INV-5)."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    dedupe_key: str


@dataclass(frozen=True)
class OrderResolution:
    """A status transition the reconciler resolved from the mass report (a broker
    terminal the local order hasn't caught up to). Position-affecting terminals
    (FILLED) are never emitted here — only cancel/reject."""

    order_id: str
    new_status: OrderStatus
    reason: str


@dataclass(frozen=True)
class ExternalOrder:
    """A venue order that matches no local order — external/unmanaged. Surfaced,
    never silently absorbed into managed state or folded into position (§7)."""

    broker_order_id: str
    client_order_id: Optional[str]
    symbol: str
    side: OrderSide
    status: OrderStatus
    filled_quantity: int


@dataclass(frozen=True)
class PositionMismatch:
    """A per-symbol divergence between the locally fill-derived position and the
    broker position report, beyond tolerance (qty exact, avg-px within
    ``avg_price_tolerance``). Surfaced for review — never a silent overwrite."""

    symbol: str
    kind: str  # "quantity" | "avg_price"
    local_quantity: int
    broker_quantity: int
    local_avg: Optional[float]
    broker_avg: Optional[float]


@dataclass(frozen=True)
class ReconciliationPlan:
    """The pure outcome of one reconciliation pass. Every list is deterministic
    and insertion-ordered (§12). The caller applies it: run the targeted queries
    for ``needs_targeted_query``, apply ``resolutions`` + ``inferred_fills`` through
    the store, surface ``external_orders`` + ``position_mismatches``."""

    resolutions: list[OrderResolution] = field(default_factory=list)
    inferred_fills: list[InferredFill] = field(default_factory=list)
    needs_targeted_query: list[str] = field(default_factory=list)
    external_orders: list[ExternalOrder] = field(default_factory=list)
    position_mismatches: list[PositionMismatch] = field(default_factory=list)
    skipped_recent: list[str] = field(default_factory=list)


def synthetic_fill_dedupe_key(
    *, broker_order_id: Optional[str], client_order_id: str, cumulative_qty: int
) -> str:
    """Deterministic id for a reconciliation-inferred fill (§3 / R8).

    Keyed on the venue id when known (else our stable ``client_order_id``) + the
    cumulative filled level — mirroring the real-fill scheme
    (``{broker_order_id}:{filled_qty}`` in ``alpaca_paper._get_fills``) so a real
    fill and a synthetic one for the *same* shares collide on the same key and
    dedup, rather than double-counting."""

    anchor = broker_order_id or client_order_id
    return f"recon:{anchor}:{cumulative_qty}"


def _price_tolerance_ok(local: Optional[float], broker: Optional[float], tol: float) -> bool:
    if local is None or broker is None:
        return local is None and broker is None
    if local == 0:
        return broker == 0
    return abs(local - broker) / abs(local) <= tol


def plan_reconciliation(
    *,
    local_open_orders: list[Order],
    local_positions: list[Position],
    broker_orders: list[BrokerOrderReport],
    broker_positions: list[BrokerPositionReport],
    now: datetime,
    recent_threshold_ms: int = DEFAULT_RECENT_ORDER_THRESHOLD_MS,
    avg_price_tolerance: float = DEFAULT_AVG_PRICE_TOLERANCE,
) -> ReconciliationPlan:
    """Fold the local + broker snapshots into a :class:`ReconciliationPlan` (§7).

    ``local_open_orders`` should be the orders open at the venue (status in
    :data:`OPEN_STATUSES`); the engine tolerates others (it simply won't reconcile
    a terminal one). Matching is by ``broker_order_id`` first, then by
    ``client_order_id == order.id`` (our deterministic submit id) — so an order we
    submitted but whose ack we lost is still matched. ``now`` is injected (§12).
    """

    by_broker_id: dict[str, BrokerOrderReport] = {}
    by_client_id: dict[str, BrokerOrderReport] = {}
    for report in broker_orders:
        by_broker_id[report.broker_order_id] = report
        if report.client_order_id is not None:
            by_client_id[report.client_order_id] = report

    plan = ReconciliationPlan()
    recent_cutoff = now - timedelta(milliseconds=recent_threshold_ms)
    matched_report_ids: set[str] = set()

    for order in local_open_orders:
        if order.status not in OPEN_STATUSES:
            continue
        # Recent-order protection (§7): an order touched within the threshold is
        # still settling — skip it this cycle rather than race the venue.
        if order.updated_at is not None and order.updated_at > recent_cutoff:
            plan.skipped_recent.append(order.id)
            continue

        report = None
        if order.broker_order_id is not None and order.broker_order_id in by_broker_id:
            report = by_broker_id[order.broker_order_id]
        elif order.id in by_client_id:
            report = by_client_id[order.id]

        if report is None:
            # Open locally but ABSENT from the mass report. The engine does NOT
            # reject here (§7 safeguard) — it requests a targeted confirm; the
            # impure caller owns the retry budget + read-only query.
            plan.needs_targeted_query.append(order.id)
            continue

        matched_report_ids.add(report.broker_order_id)

        # A broker fill level above what we recorded → infer the priced execution
        # if the report carries one; otherwise ask for a targeted poll (which
        # fetches the price) rather than fabricating a $0 fill.
        if report.filled_quantity > order.filled_quantity:
            priced = [f for f in report.fills if f.price is not None]
            covered = sum(f.quantity for f in priced)
            if priced and covered >= (report.filled_quantity - order.filled_quantity):
                for fill in priced:
                    plan.inferred_fills.append(
                        InferredFill(
                            order_id=order.id,
                            symbol=order.symbol,
                            side=OrderSide(order.side),
                            quantity=fill.quantity,
                            price=fill.price,
                            dedupe_key=synthetic_fill_dedupe_key(
                                broker_order_id=order.broker_order_id,
                                client_order_id=order.id,
                                cumulative_qty=order.filled_quantity + fill.quantity,
                            ),
                        )
                    )
            else:
                plan.needs_targeted_query.append(order.id)
                continue

        # A non-position-affecting terminal the local order hasn't caught up to
        # (cancel/reject/expire). FILLED is never resolved by a bare status flip.
        if (
            report.status in _NON_POSITION_TERMINALS
            and order.status != report.status
        ):
            plan.resolutions.append(
                OrderResolution(
                    order_id=order.id,
                    new_status=report.status,
                    reason=f"broker_reports_{report.status.value}",
                )
            )

    # External/unmanaged orders: venue rows matching no local order (by neither
    # broker id nor client id). Surfaced, never absorbed.
    local_ids = {o.id for o in local_open_orders}
    local_broker_ids = {
        o.broker_order_id for o in local_open_orders if o.broker_order_id is not None
    }
    for report in broker_orders:
        if report.broker_order_id in matched_report_ids:
            continue
        if report.broker_order_id in local_broker_ids:
            continue
        if report.client_order_id is not None and report.client_order_id in local_ids:
            continue
        plan.external_orders.append(
            ExternalOrder(
                broker_order_id=report.broker_order_id,
                client_order_id=report.client_order_id,
                symbol=report.symbol,
                side=OrderSide(report.side),
                status=report.status,
                filled_quantity=report.filled_quantity,
            )
        )

    # Position parity (§7): qty exact, avg-px within tolerance. A symbol present in
    # one side but not the other is a quantity mismatch (0 vs n). Surfaced only.
    local_by_symbol = {p.symbol: p for p in local_positions if p.quantity != 0}
    broker_by_symbol = {p.symbol: p for p in broker_positions if p.quantity != 0}
    for symbol in sorted(set(local_by_symbol) | set(broker_by_symbol)):
        lp = local_by_symbol.get(symbol)
        bp = broker_by_symbol.get(symbol)
        local_qty = lp.quantity if lp is not None else 0
        broker_qty = bp.quantity if bp is not None else 0
        local_avg = lp.average_price if lp is not None else None
        broker_avg = bp.average_price if bp is not None else None
        if local_qty != broker_qty:
            plan.position_mismatches.append(
                PositionMismatch(
                    symbol=symbol, kind="quantity",
                    local_quantity=local_qty, broker_quantity=broker_qty,
                    local_avg=local_avg, broker_avg=broker_avg,
                )
            )
        elif not _price_tolerance_ok(local_avg, broker_avg, avg_price_tolerance):
            plan.position_mismatches.append(
                PositionMismatch(
                    symbol=symbol, kind="avg_price",
                    local_quantity=local_qty, broker_quantity=broker_qty,
                    local_avg=local_avg, broker_avg=broker_avg,
                )
            )

    return plan
