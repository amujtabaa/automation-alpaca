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

import hashlib
from typing import Protocol

from app.broker.adapter import (
    AmbiguousBrokerError,
    BrokerAdapter,
    BrokerError,
    BrokerOrderReport,
    BrokerPositionReport,
    TerminalBrokerError,
)
from app.marketdata.service import MarketSnapshot
from app.models import (
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEvent,
    Order,
    OrderSide,
    OrderStatus,
    Position,
    utcnow,
)
from app.sellside.policy import validate_action
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import CLAIM_CLAIMED, SubmissionClaim
from app.store.core import STAGE_DIVERGENCE, EnvelopeActionStageResult

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
_NON_POSITION_TERMINALS = frozenset({OrderStatus.CANCELED, OrderStatus.REJECTED})

# Default parity/threshold values (the §7 verified defaults also land in config.py in
# wave 4e; these keep the pure engine usable + testable standalone).
DEFAULT_RECENT_ORDER_THRESHOLD_MS = 5000  # open_check_threshold_ms (§7)
DEFAULT_AVG_PRICE_TOLERANCE = 0.0001  # 0.01% (§7)


class ReconcileQueryBudget:
    """Deterministic per-minute query budget for the reconciliation REST calls
    (§9 "proactive token bucket" for the 200/min budget; §7 "respect the budget").

    A continuous token bucket with an **injected clock** (§12) — no wall-clock, no
    IO, no RNG — so a throttled cycle is replayable and property-testable exactly
    like the rest of the reconcile engine. Tokens refill at ``limit_per_min / 60``
    per second, capped at ``limit_per_min``; the bucket starts full.

    ``try_consume(now, n)`` grants ``n`` tokens iff available. When it returns
    ``False`` the caller **skips** that reconcile REST call this cycle — and a
    skipped order/position query is **never** read as "flat"/"absent" (§7 / wave-4e
    E7): the absence of a fresh report is never turned into a fact. The clock only
    advances forward (a non-increasing ``now`` neither refills nor rewinds state),
    so out-of-order calls cannot over-credit the budget.

    Wave 4e-1 lands this inert (nothing consumes from it yet — the acting reconcile
    wires it in slice 4e-4).
    """

    def __init__(self, limit_per_min: int) -> None:
        if limit_per_min < 1:
            raise ValueError("limit_per_min must be >= 1")
        self.limit_per_min = limit_per_min
        self._tokens = float(limit_per_min)
        self._last: Optional[datetime] = None

    def try_consume(self, now: datetime, n: int = 1) -> bool:
        if n < 1:
            raise ValueError("n must be >= 1")
        if self._last is None:
            self._last = now
        else:
            elapsed = (now - self._last).total_seconds()
            if elapsed > 0:  # refill only on forward time; never rewind
                self._tokens = min(
                    float(self.limit_per_min),
                    self._tokens + elapsed * (self.limit_per_min / 60.0),
                )
                self._last = now
        if self._tokens >= n:
            self._tokens -= n
            return True
        return False

    @property
    def available(self) -> float:
        """Tokens available as of the last ``try_consume`` (no implicit refill)."""

        return self._tokens


class ReconcileFairnessCursor:
    """Round-robin cursor so a limited shared query budget cannot let the EARLIEST
    ``TIMEOUT_QUARANTINE`` orders starve the later ones forever (PR #4 review, P2 —
    the ENG-002 budget follow-up).

    ``_resolve_timeout_quarantine`` iterates ``list_timeout_quarantined_orders()``
    in a deterministic order and stops when the budget is exhausted. If the first
    orders keep failing their targeted query (or sit escalated in ``needs_review``
    while still ``TIMEOUT_QUARANTINE``) they consume every token every tick, so the
    later orders never receive their read-only resolution query. This cursor makes
    the resolver **resume just after the last order that consumed a token** each
    tick, wrapping around, so over successive ticks every quarantined order is
    served. Escalated orders are NOT skipped — they still auto-recover if the venue
    comes back; they merely take their fair turn.

    Pure + deterministic (no clock/IO/RNG) — owned by the monitoring loop so it
    spans ticks, exactly like :class:`ReconcileQueryBudget`; direct tick callers
    (tests) pass none and keep the plain deterministic order."""

    def __init__(self) -> None:
        self.last_served_id: Optional[str] = None

    def rotate(self, orders: list[Order]) -> list[Order]:
        """Return ``orders`` rotated to resume just after ``last_served_id``,
        wrapping around. A cold cursor (``None``) or a ``last_served_id`` no longer
        present (that order resolved/left the quarantine set) leaves the order
        unchanged — the natural deterministic order."""

        if self.last_served_id is None:
            return orders
        ids = [o.id for o in orders]
        if self.last_served_id not in ids:
            return orders
        i = ids.index(self.last_served_id) + 1
        return orders[i:] + orders[:i]

    def record(self, order_id: str) -> None:
        """Mark ``order_id`` as the most recent order to consume a token, so the
        next tick resumes after it."""

        self.last_served_id = order_id


@dataclass(frozen=True)
class InferredFill:
    """A fill the reconciler infers from a priced execution in the broker report
    that the local log is missing. ``quantity`` is that execution's share count.

    ``source_fill_id`` is the report execution's OWN id — deliberately the same
    identity a later per-order poll (``get_order_status``) would carry for the same
    shares (both derive the fill-event dedup key ``fill:{order_id}:{source_fill_id}``).
    That is what makes a reconciliation-inferred fill and the eventual real
    observation of the *same* execution dedup to ONE (INV-5 / R8) — never a
    double-count. The event's ``authority=SYNTHETIC`` marks it as reconciliation-
    inferred *provenance*; the *identity* stays the venue execution id so it can't
    diverge from the real fill's identity."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    source_fill_id: str


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


def _price_tolerance_ok(
    local: Optional[float], broker: Optional[float], tol: float
) -> bool:
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
    for br in broker_orders:
        by_broker_id[br.broker_order_id] = br
        if br.client_order_id is not None:
            by_client_id[br.client_order_id] = br

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

        report: Optional[BrokerOrderReport] = None
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
            # A priced execution is only inferable if it ALSO carries its own
            # ``source_fill_id`` — that id is the sole INV-5 dedup key against the
            # eventual real observation of the same shares. A priced fill with a
            # null/empty id would defeat dedup and double-count into an overstated
            # long (→ oversell on flatten); route it to the targeted poll instead
            # (which advances the recorded fill and dedups by its own key).
            priced = [
                f for f in report.fills if f.price is not None and f.source_fill_id
            ]
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
                            # The execution's OWN venue id — same identity a later
                            # real poll would carry, so the two dedup (INV-5), never
                            # double-count.
                            source_fill_id=fill.source_fill_id,
                        )
                    )
            else:
                plan.needs_targeted_query.append(order.id)
                continue

        # A non-position-affecting terminal the local order hasn't caught up to
        # (cancel/reject/expire). FILLED is never resolved by a bare status flip.
        if report.status in _NON_POSITION_TERMINALS and order.status != report.status:
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
                    symbol=symbol,
                    kind="quantity",
                    local_quantity=local_qty,
                    broker_quantity=broker_qty,
                    local_avg=local_avg,
                    broker_avg=broker_avg,
                )
            )
        elif not _price_tolerance_ok(local_avg, broker_avg, avg_price_tolerance):
            plan.position_mismatches.append(
                PositionMismatch(
                    symbol=symbol,
                    kind="avg_price",
                    local_quantity=local_qty,
                    broker_quantity=broker_qty,
                    local_avg=local_avg,
                    broker_avg=broker_avg,
                )
            )

    return plan


# --------------------------------------------------------------------------- #
# Envelope executor — the venue leg of the engine seam (WO-0019, ADR-009 §1/§5)
# --------------------------------------------------------------------------- #
#
# The DECISION half (write-time validation, order minting, budget accounting,
# the ENVELOPE_PLAN_DIVERGENCE tripwire) lives in the stores'
# ``stage_envelope_action`` — one lock/transaction, no await between the
# control check and the durable writes. This module owns only the VENUE leg:
# claim the staged order through the EXISTING submission claim (INV-021: the
# claim stays the sole entry into SUBMITTING — the envelope path adds no back
# door), call the abstract adapter (submit or the WO-0019a atomic replace),
# and map the outcome through the same ADR-002 discipline as every other
# submit: ambiguous → TIMEOUT_QUARANTINE (deterministic client_order_id = the
# order id), transient → release for redrive, terminal → REJECTED.


class _EnvelopeSeamStore(Protocol):
    """The store surface the envelope executor drives. The abstract
    ``StateStore`` does not declare the envelope API yet (``app/store/base.py``
    has stayed outside every W3 WO's scope — the ABC lift is deferred-logged
    for its own small WO); a structural Protocol keeps the seam honestly
    typed against BOTH concrete stores meanwhile."""

    async def stage_envelope_action(
        self,
        envelope_id: str,
        action: PlannedAction,
        *,
        snapshot_fingerprint: str,
        actor: str = ...,
        session_id: Optional[str] = ...,
        now: Optional[datetime] = ...,
    ) -> EnvelopeActionStageResult: ...

    async def claim_order_for_submission(self, order_id: str) -> SubmissionClaim: ...

    async def quarantine_timed_out_order(
        self, order_id: str, *, reason: Optional[str] = ...
    ) -> Order: ...

    async def transition_order(
        self,
        order_id: str,
        new_status: OrderStatus,
        *,
        filled_quantity: Optional[int] = ...,
        broker_order_id: Optional[str] = ...,
    ) -> Order: ...

    async def get_order(self, order_id: str) -> Optional[Order]: ...

    async def get_execution_events(
        self, *, after_sequence: int = ..., limit: Optional[int] = ...
    ) -> list[ExecutionEvent]: ...

    async def get_envelope(self, envelope_id: str) -> Optional[ExecutionEnvelope]: ...

    async def get_position(self, symbol: str) -> Position: ...


ENVELOPE_EXEC_SUBMITTED = "submitted"
ENVELOPE_EXEC_REPRICED = "repriced"
ENVELOPE_EXEC_DIVERGENCE = "divergence"  # frozen + event; zero venue calls
ENVELOPE_EXEC_BLOCKED = "blocked"  # claim control gate held it; order stays CREATED
ENVELOPE_EXEC_QUARANTINED = "quarantined"  # ambiguous venue outcome (ADR-002)
ENVELOPE_EXEC_RELEASED = "released"  # transient failure; order back to CREATED
ENVELOPE_EXEC_REJECTED = "rejected"  # definitive venue rejection
ENVELOPE_EXEC_CANCELLED = "cancelled"  # redrive refusal: staged order locally
# CANCELED with zero venue calls (WO-0024 — non-ACTIVE envelope, stale staging,
# or a rail the CURRENT state no longer satisfies)

# A staged-but-undriven action is only redrivable while it is FRESH: past this
# ceiling the decision that produced it is stale (crash-restart warm-up,
# freeze->resume stretch, long outage) and the policy must re-decide from
# current data instead. Two 30s ticks + slack. (WO-0024 / REV-0022 F3 — the
# tape itself is monitoring-owned; this age bound subsumes the
# restart-with-empty-tape scenario at the executor seam.)
REDRIVE_MAX_STAGED_AGE_S = 120.0


@dataclass(frozen=True)
class EnvelopeExecutionResult:
    outcome: str
    order_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    detail: str = ""


def market_snapshot_fingerprint(snapshot: MarketSnapshot) -> str:
    """Deterministic fingerprint of the snapshot a decision was made against —
    stamped into every ENVELOPE_ACTION event (ADR-009 §6) so an action is
    auditable against the exact market state that justified it."""

    raw = "|".join(
        str(part)
        for part in (
            snapshot.symbol,
            snapshot.last_price,
            snapshot.bid,
            snapshot.ask,
            snapshot.volume,
            snapshot.prev_close,
            snapshot.updated_at.isoformat(),
            snapshot.stale,
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def _drive_staged_order(
    store: _EnvelopeSeamStore,
    adapter: BrokerAdapter,
    *,
    order: Order,
    kind: ActionKind,
    working_order: Optional[Order],
) -> EnvelopeExecutionResult:
    """The venue leg for one already-staged order (fresh or redriven)."""

    claim = await store.claim_order_for_submission(order.id)
    if claim.outcome != CLAIM_CLAIMED:
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_BLOCKED,
            order_id=order.id,
            detail=claim.reason or claim.outcome,
        )
    try:
        if kind is ActionKind.REPRICE:
            assert working_order is not None
            assert working_order.broker_order_id is not None  # staged guarantees
            new_broker_id = await adapter.replace_order(
                working_order.broker_order_id,
                client_order_id=order.id,  # deterministic (ADR-002 recovery key)
                limit_price=order.limit_price,
                quantity=order.quantity,
            )
        else:
            assert claim.order is not None  # CLAIM_CLAIMED carries the order
            new_broker_id = await adapter.submit_order(claim.order)
    except AmbiguousBrokerError:
        # The venue MAY have the replacement/submission. Quarantine; the
        # targeted client_order_id query resolves it; the envelope pauses
        # (stage refuses) until then — never blind-re-replace.
        await store.quarantine_timed_out_order(order.id)
        return EnvelopeExecutionResult(ENVELOPE_EXEC_QUARANTINED, order_id=order.id)
    except TerminalBrokerError as exc:
        await store.transition_order(order.id, OrderStatus.REJECTED)
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_REJECTED, order_id=order.id, detail=str(exc)
        )
    except BrokerError as exc:
        # Provably-pre-flight transient: release the claim; the SAME staged
        # order (and its already-committed budget accounting) redrives later.
        await store.transition_order(order.id, OrderStatus.CREATED)
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_RELEASED, order_id=order.id, detail=str(exc)
        )

    await store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id=new_broker_id
    )
    if kind is ActionKind.REPRICE:
        assert working_order is not None
        # The venue's replace terminated the old order (broker-confirmed fact;
        # the old order HAS a broker id, so ADR-008 stamps this
        # BROKER_REST/BROKER_AUTHORITATIVE).
        await store.transition_order(working_order.id, OrderStatus.CANCELED)
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_REPRICED,
            order_id=order.id,
            broker_order_id=new_broker_id,
        )
    return EnvelopeExecutionResult(
        ENVELOPE_EXEC_SUBMITTED, order_id=order.id, broker_order_id=new_broker_id
    )


async def execute_envelope_action(
    store: _EnvelopeSeamStore,
    adapter: BrokerAdapter,
    envelope_id: str,
    action: PlannedAction,
    *,
    snapshot_fingerprint: str,
    actor: str = "engine",
    now: Optional[datetime] = None,
) -> EnvelopeExecutionResult:
    """Stage (write-time D-3 validation, atomic) then drive the venue leg.
    ``now`` is the injected validation clock (the tick's clock)."""

    staged = await store.stage_envelope_action(
        envelope_id,
        action,
        snapshot_fingerprint=snapshot_fingerprint,
        actor=actor,
        now=now,
    )
    if staged.outcome == STAGE_DIVERGENCE:
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_DIVERGENCE,
            detail="plan/write validator disagreement — envelope frozen",
        )
    assert staged.order is not None
    return await _drive_staged_order(
        store,
        adapter,
        order=staged.order,
        kind=action.kind,
        working_order=staged.working_order,
    )


async def redrive_staged_envelope_action(
    store: _EnvelopeSeamStore,
    adapter: BrokerAdapter,
    envelope_id: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[EnvelopeExecutionResult]:
    """Resume a staged-but-not-executed action (transient release / crash
    between staging and the venue call) WITHOUT re-staging — the budget
    accounting committed with the original staging and must not be spent
    twice. Returns None when there is nothing to redrive.

    WO-0024 (REV-0022 F3, FINDING-W3-redrive-revalidation-bypass): before any
    venue call, the staged order is RE-VALIDATED against CURRENT state and
    CURRENT time — the original staging validated against the world as it was,
    and fills, TTL, session phase, or a long gap may have invalidated it since:

    * envelope no longer ACTIVE (preempted/frozen/terminal) → refuse;
    * staged action older than ``REDRIVE_MAX_STAGED_AGE_S`` → the decision is
      stale (crash-restart warm-up, freeze→resume stretch) → refuse;
    * the shared hard-rail validator (``validate_action`` — floor, qty vs
      CURRENT remaining, TTL, session phase, budget) rejects it → refuse.

    A refusal makes ZERO venue calls and locally CANCELs the staged order
    (CREATED → CANCELED, event-logged) so it can never be driven later; the
    policy re-decides from current data on the next tick. Refusals are NOT
    plan/write divergences — nothing here is a software defect, just staleness
    — so the envelope is never frozen by this path (INV-082 stays a defect
    signal).
    """

    ts = now if now is not None else utcnow()
    events = await store.get_execution_events()
    staged_events = [
        e
        for e in events
        if e.envelope_id == envelope_id
        and e.event_type.value == "envelope_action"
        and e.order_id is not None
    ]
    if not staged_events:
        return None
    last = staged_events[-1]
    assert last.order_id is not None
    order = await store.get_order(last.order_id)
    if order is None or order.status is not OrderStatus.CREATED:
        return None  # nothing pending — executed, quarantined, or cancelled
    kind = (
        ActionKind.REPRICE
        if last.payload.get("action") == "reprice"
        else ActionKind.SUBMIT
    )

    refusal: Optional[str] = None
    envelope = await store.get_envelope(envelope_id)
    if envelope is None or envelope.status is not EnvelopeStatus.ACTIVE:
        refusal = (
            "envelope is "
            f"{envelope.status.value if envelope is not None else 'missing'}"
        )
    else:
        staged_at = last.ts_event or last.ts_init
        age = (ts - staged_at).total_seconds()
        if age > REDRIVE_MAX_STAGED_AGE_S:
            refusal = (
                f"staged action is {age:.0f}s old "
                f"(redrive ceiling {REDRIVE_MAX_STAGED_AGE_S:.0f}s)"
            )
        else:
            replayed = PlannedAction(
                kind=kind,
                limit_price=order.limit_price or 0.0,
                quantity=order.quantity,
                regime=None,
                urgency=0.0,
                working_stop=None,
                atr=None,
                tranche=bool(last.payload.get("tranche", False)),
                stop_triggered=bool(last.payload.get("stop_triggered", False)),
                clamps=(),
            )
            # Validate as if deciding this action NOW — excluding the staged
            # action's OWN event, whose committed budget/cooldown accounting
            # must not refuse its own completion.
            history = [e for e in events if e.sequence != last.sequence]
            violation = validate_action(envelope, replayed, history=history, now=ts)
            if violation is not None:
                refusal = f"{violation.rail}: {violation.detail}"
            else:
                # WO-0026: reduce-only re-check — the position may have
                # shrunk (fills, manual flatten) since staging.
                position = await store.get_position(envelope.symbol)
                if order.quantity > max(0, position.quantity):
                    refusal = (
                        f"reduce_only: SELL {order.quantity} exceeds live "
                        f"position {max(0, position.quantity)}"
                    )

    if refusal is not None:
        await store.transition_order(order.id, OrderStatus.CANCELED)
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_CANCELLED,
            order_id=order.id,
            detail=f"redrive refused — {refusal}; staged order locally cancelled",
        )

    working_order: Optional[Order] = None
    if kind is ActionKind.REPRICE and order.replaces_order_id is not None:
        working_order = await store.get_order(order.replaces_order_id)
    return await _drive_staged_order(
        store, adapter, order=order, kind=kind, working_order=working_order
    )
