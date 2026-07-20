"""Pure reconciliation engine — §7 / Spine v2 §2 module 5 (Phase 4 wave 4b).

Deterministic and IO-free: it folds a snapshot of

  (local open orders, local positions, broker order-status report, broker
   position report, ``now``)

into a :class:`ReconciliationPlan` the impure caller (the monitoring loop)
then acts on — running the targeted single-order queries the plan requests and
applying transitions and broker-authoritative reconciliation fills through the
single-writer store.

**Why a pure engine.** All decisions come from the reports + an injected clock —
no network, no wall-clock, no RNG (§12). That is what makes the §7 invariants
(no oversell via a spurious not-found→REJECTED; never treat a query failure as
flat; deterministic reconciliation ids) property-testable over thousands of
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

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Coroutine, Mapping, Optional, Sequence, TypeVar

import hashlib

from app.broker.adapter import (
    AmbiguousBrokerError,
    BrokerAdapter,
    BrokerError,
    BrokerOrderReport,
    BrokerPositionReport,
    TerminalBrokerError,
    VenueOrderScope,
)
from app.features import session_type_for
from app.marketdata.service import MarketSnapshot
from app.models import (
    ACCEPTED_SUBMIT_UNPERSISTED_REASON,
    RECOVERY_NEEDS_REVIEW,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    EventType,
    ExecutionEvent,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    SessionType,
    utcnow,
)
from app.policy import canonical_accepted_submit_broker_id, finite_number_reason
from app.sellside.policy import validate_action
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import (
    CLAIM_CLAIMED,
    RecoveryTransitionError,
    StateStore,
    normalize_broker_order_id,
)
from app.store.core import (
    ENVELOPE_MAX_STAGED_AGE_S,
    STAGE_DIVERGENCE,
    STAGE_REFUSED_STALE,
    envelope_claim_hard_rail_reason,
)

_log = logging.getLogger(__name__)
_FinalizerResult = TypeVar("_FinalizerResult")


def _claim_occurrence(event: ExecutionEvent, fallback: int) -> Optional[int]:
    raw = event.payload.get("claim_occurrence")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return raw
    if raw is not None:
        return None
    if event.dedupe_key is None or not event.dedupe_key.startswith("submit_pending:"):
        return fallback
    try:
        occurrence = int(event.dedupe_key.rsplit(":", 1)[-1])
    except ValueError:
        return None
    return occurrence if occurrence >= 0 else None


def _is_legacy_submit_backfill(event: ExecutionEvent, order_id: str) -> bool:
    """The sole synthetic SUBMIT_PENDING producer accepted by migration."""

    return (
        event.source is EventSource.RECONCILIATION
        and event.authority is EventAuthority.SYNTHETIC
        and event.dedupe_key == f"backfill_status:{order_id}"
        and "claim_occurrence" not in event.payload
    )


def _current_claim_occurrence(
    events: Sequence[ExecutionEvent], order_id: str
) -> Optional[int]:
    current: Optional[int] = None
    expected = 0
    for event in events:
        if (
            event.order_id != order_id
            or event.event_type is not ExecutionEventType.SUBMIT_PENDING
        ):
            continue
        parsed = _claim_occurrence(event, expected)
        legacy_backfill = expected == 0 and _is_legacy_submit_backfill(event, order_id)
        if (
            parsed is None
            or parsed != expected
            or (
                not legacy_backfill
                and (
                    event.source is not EventSource.ENGINE
                    or event.authority is not EventAuthority.LOCAL
                    or event.dedupe_key != f"submit_pending:{order_id}:{parsed}"
                )
            )
            or not isinstance(event.symbol, str)
            or not event.symbol.strip()
            or event.side not in (OrderSide.BUY, OrderSide.SELL)
            or event.quantity is not None
            or event.price is not None
        ):
            raise RecoveryTransitionError(
                f"order {order_id!r} has malformed claim-occurrence truth"
            )
        current = parsed
        expected += 1
    return current


def _venue_scope_from_event(event: ExecutionEvent) -> VenueOrderScope:
    payload = event.payload or {}
    try:
        claim_occurrence = payload["claim_occurrence"]
        client_order_id = payload["client_order_id"]
        symbol = payload["symbol"]
        side = OrderSide(payload["side"])
        quantity = payload["quantity"]
        order_type = OrderType(payload["order_type"])
        limit_price = payload.get("limit_price")
        extended_hours = payload["extended_hours"]
        asset_class = payload["asset_class"]
        quantity_mode = payload["quantity_mode"]
        time_in_force = payload["time_in_force"]
        order_class = payload["order_class"]
        replaces_broker_order_id = payload.get("replaces_broker_order_id")
    except (KeyError, TypeError, ValueError) as exc:
        raise RecoveryTransitionError("malformed venue-order scope event") from exc
    if (
        event.event_type is not ExecutionEventType.VENUE_ORDER_SCOPE
        or event.source is not EventSource.ENGINE
        or event.authority is not EventAuthority.LOCAL
        or event.order_id is None
        or not isinstance(claim_occurrence, int)
        or isinstance(claim_occurrence, bool)
        or claim_occurrence < 0
        or event.dedupe_key != f"venue_order_scope:{event.order_id}:{claim_occurrence}"
        or not isinstance(client_order_id, str)
        or not client_order_id.strip()
        or not isinstance(symbol, str)
        or not symbol.strip()
        or not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity <= 0
        or not (
            isinstance(extended_hours, bool)
            or (extended_hours is None and replaces_broker_order_id is not None)
        )
        or asset_class != "us_equity"
        or quantity_mode != "qty"
        or time_in_force != "day"
        or order_class != "simple"
        or (
            replaces_broker_order_id is not None
            and (
                not isinstance(replaces_broker_order_id, str)
                or not replaces_broker_order_id.strip()
            )
        )
        or (order_type is OrderType.MARKET and limit_price is not None)
        or (
            order_type is OrderType.LIMIT
            and (
                limit_price is None
                or finite_number_reason(limit_price) is not None
                or limit_price <= 0
            )
        )
        or (order_type is OrderType.MARKET and extended_hours is not False)
        or (replaces_broker_order_id is None and not isinstance(extended_hours, bool))
        or event.order_id != client_order_id.strip()
        or event.symbol != symbol.strip().upper()
        or event.side is not side
        or event.quantity != quantity
        or event.price != limit_price
    ):
        raise RecoveryTransitionError("malformed venue-order scope event")
    return VenueOrderScope(
        client_order_id=client_order_id.strip(),
        symbol=symbol.strip().upper(),
        side=side,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
        extended_hours=extended_hours,
        asset_class=asset_class,
        quantity_mode=quantity_mode,
        time_in_force=time_in_force,
        order_class=order_class,
        replaces_broker_order_id=(
            replaces_broker_order_id.strip()
            if isinstance(replaces_broker_order_id, str)
            else None
        ),
    )


def venue_order_scope_map(
    events: Sequence[ExecutionEvent],
) -> dict[str, VenueOrderScope]:
    """Current durable rendered scope per order, failing closed on poison.

    Historical occurrences remain valid history but cannot override the current
    submission claim.  Every scope must name an actual claim occurrence and be
    the sole canonical event for that ``(order, occurrence)`` pair.
    """

    claims_by_order: dict[str, dict[int, ExecutionEvent]] = {}
    current_by_order: dict[str, int] = {}
    expected_by_order: dict[str, int] = {}
    for event in events:
        if event.event_type is not ExecutionEventType.SUBMIT_PENDING:
            continue
        if event.order_id is None:
            raise RecoveryTransitionError("submission claim event has no order id")
        expected = expected_by_order.get(event.order_id, 0)
        occurrence = _claim_occurrence(event, expected)
        legacy_backfill = expected == 0 and _is_legacy_submit_backfill(
            event, event.order_id
        )
        if (
            occurrence is None
            or occurrence != expected
            or (
                not legacy_backfill
                and (
                    event.source is not EventSource.ENGINE
                    or event.authority is not EventAuthority.LOCAL
                    or event.dedupe_key
                    != f"submit_pending:{event.order_id}:{occurrence}"
                )
            )
            or not isinstance(event.symbol, str)
            or not event.symbol.strip()
            or event.side not in (OrderSide.BUY, OrderSide.SELL)
            or event.quantity is not None
            or event.price is not None
        ):
            raise RecoveryTransitionError(
                f"order {event.order_id!r} has malformed claim-occurrence truth"
            )
        claims_by_order.setdefault(event.order_id, {})[occurrence] = event
        current_by_order[event.order_id] = occurrence
        expected_by_order[event.order_id] = expected + 1

    by_occurrence: dict[tuple[str, int], VenueOrderScope] = {}
    for event in events:
        if event.event_type is not ExecutionEventType.VENUE_ORDER_SCOPE:
            continue
        if event.order_id is None:
            raise RecoveryTransitionError("venue-order scope event has no order id")
        scope = _venue_scope_from_event(event)
        occurrence = event.payload["claim_occurrence"]
        assert isinstance(occurrence, int) and not isinstance(occurrence, bool)
        claim = claims_by_order.get(event.order_id, {}).get(occurrence)
        if claim is None:
            raise RecoveryTransitionError(
                "venue-order scope event names no durable submission claim"
            )
        if (
            event.symbol != claim.symbol
            or event.side is not claim.side
            or event.session_id != claim.session_id
        ):
            raise RecoveryTransitionError(
                "venue-order scope event contradicts its submission claim"
            )
        key = (event.order_id, occurrence)
        if key in by_occurrence:
            raise RecoveryTransitionError(
                "multiple venue-order scope events name one submission claim"
            )
        by_occurrence[key] = scope

    scopes: dict[str, VenueOrderScope] = {}
    for order_id, occurrence in current_by_order.items():
        current_scope = by_occurrence.get((order_id, occurrence))
        if current_scope is not None:
            scopes[order_id] = current_scope
    return scopes


def current_venue_order_scope(
    events: Sequence[ExecutionEvent], order_id: str
) -> Optional[VenueOrderScope]:
    return venue_order_scope_map(events).get(order_id)


@dataclass(frozen=True)
class VenueScopeOwner:
    """Immutable local identity used to authenticate persisted wire scope.

    A normal owner is an :class:`Order`; an accepted-submit recovery can outlive
    its Order row, so recovery cadence supplies the same immutable tuple from the
    durable recovery record.  No consumer may receive a scope that has only been
    validated against another event written in the same potentially-poisoned log.
    """

    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    order_type: Optional[OrderType] = None
    limit_price: Optional[float] = None
    allow_dynamic_venue_type: bool = False

    @classmethod
    def from_order(cls, order: Order) -> "VenueScopeOwner":
        return cls(
            order_id=order.id,
            symbol=order.symbol,
            side=OrderSide(order.side),
            quantity=order.quantity,
            order_type=OrderType(order.order_type),
            limit_price=order.limit_price,
            allow_dynamic_venue_type=order_has_dynamic_venue_type(order),
        )


def _validate_venue_scope_owner(scope: VenueOrderScope, owner: VenueScopeOwner) -> None:
    if (
        scope.client_order_id != owner.order_id
        or scope.symbol != owner.symbol
        or scope.side is not owner.side
        or scope.quantity != owner.quantity
    ):
        raise RecoveryTransitionError(
            f"venue scope contradicts immutable order {owner.order_id!r}"
        )
    if owner.allow_dynamic_venue_type:
        rendered_type_is_valid = (
            scope.order_type is OrderType.MARKET and scope.limit_price is None
        ) or (
            scope.order_type is OrderType.LIMIT
            and scope.limit_price is not None
            and finite_number_reason(scope.limit_price) is None
            and scope.limit_price > 0
        )
        if not rendered_type_is_valid:
            raise RecoveryTransitionError(
                f"venue scope has invalid rendered type for order {owner.order_id!r}"
            )
    elif owner.order_type is not None and (
        scope.order_type is not owner.order_type
        or scope.limit_price != owner.limit_price
    ):
        raise RecoveryTransitionError(
            f"venue scope contradicts immutable order type for {owner.order_id!r}"
        )


async def load_venue_order_scopes(
    store: StateStore, owners: Sequence[Order | VenueScopeOwner]
) -> dict[str, VenueOrderScope]:
    """Load indexed scope truth and authenticate it against immutable owners."""

    owner_by_id: dict[str, VenueScopeOwner] = {}
    events: list[ExecutionEvent] = []
    for value in owners:
        owner = VenueScopeOwner.from_order(value) if isinstance(value, Order) else value
        prior = owner_by_id.setdefault(owner.order_id, owner)
        if prior != owner:
            raise RecoveryTransitionError(
                f"conflicting immutable owners for order {owner.order_id!r}"
            )
    for order_id in owner_by_id:
        events.extend(await store.get_order_execution_events(order_id))
    scopes = venue_order_scope_map(events)
    for order_id, scope in scopes.items():
        scope_owner = owner_by_id.get(order_id)
        if scope_owner is None:
            raise RecoveryTransitionError(
                f"venue scope has no immutable owner {order_id!r}"
            )
        _validate_venue_scope_owner(scope, scope_owner)
    return scopes


def venue_scope_for_rendered_order(
    order: Order,
    *,
    extended_hours: Optional[bool],
    replaces_broker_order_id: Optional[str] = None,
) -> VenueOrderScope:
    order_type = OrderType(order.order_type)
    if order_type is OrderType.MARKET and order.limit_price is not None:
        raise RecoveryTransitionError("rendered MARKET order has a limit price")
    if order_type is OrderType.LIMIT and (
        order.limit_price is None
        or finite_number_reason(order.limit_price) is not None
        or order.limit_price <= 0
    ):
        raise RecoveryTransitionError("rendered LIMIT order lacks a finite price")
    if order_type is OrderType.MARKET and extended_hours is not False:
        raise RecoveryTransitionError("rendered MARKET order cannot use extended hours")
    if not (
        isinstance(extended_hours, bool)
        or (extended_hours is None and replaces_broker_order_id is not None)
    ):
        raise RecoveryTransitionError(
            "new submission requires exact extended-hours scope"
        )
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


def rendered_order_from_scope(order: Order, scope: VenueOrderScope) -> Order:
    _validate_venue_scope_owner(scope, VenueScopeOwner.from_order(order))
    rendered = order.model_copy(deep=True)
    rendered.order_type = scope.order_type
    rendered.limit_price = scope.limit_price
    return rendered


async def get_or_record_venue_order_scope(
    store: StateStore,
    *,
    order: Order,
    rendered_order: Order,
    extended_hours: Optional[bool],
    replaces_broker_order_id: Optional[str] = None,
) -> VenueOrderScope:
    """Write-ahead and replay the exact managed venue request for this claim."""

    events = await store.get_order_execution_events(order.id)
    existing_scopes = venue_order_scope_map(events)
    occurrence = _current_claim_occurrence(events, order.id)
    if occurrence is None:
        raise RecoveryTransitionError(
            f"order {order.id!r} has no durable submission claim"
        )
    claims = [
        event
        for event in events
        if event.event_type is ExecutionEventType.SUBMIT_PENDING
        and event.order_id == order.id
    ]
    claim = claims[-1]
    if (
        claim.symbol != order.symbol
        or claim.side is not OrderSide(order.side)
        or claim.session_id != order.session_id
    ):
        raise RecoveryTransitionError(
            f"submission claim contradicts immutable order {order.id!r}"
        )
    scope = existing_scopes.get(order.id)
    if scope is not None:
        rendered_order_from_scope(order, scope)
        if scope.replaces_broker_order_id != replaces_broker_order_id:
            raise RecoveryTransitionError(
                f"venue scope predecessor contradicts order {order.id!r}"
            )
        return scope

    scope = venue_scope_for_rendered_order(
        rendered_order,
        extended_hours=extended_hours,
        replaces_broker_order_id=replaces_broker_order_id,
    )
    stored = await store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.VENUE_ORDER_SCOPE,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=f"venue_order_scope:{order.id}:{occurrence}",
            symbol=scope.symbol,
            side=scope.side,
            quantity=scope.quantity,
            price=scope.limit_price,
            order_id=order.id,
            session_id=order.session_id,
            payload={
                "claim_occurrence": occurrence,
                "client_order_id": scope.client_order_id,
                "symbol": scope.symbol,
                "side": scope.side.value,
                "quantity": scope.quantity,
                "asset_class": scope.asset_class,
                "quantity_mode": scope.quantity_mode,
                "order_type": scope.order_type.value,
                "limit_price": scope.limit_price,
                "time_in_force": scope.time_in_force,
                "order_class": scope.order_class,
                "extended_hours": scope.extended_hours,
                "replaces_broker_order_id": scope.replaces_broker_order_id,
            },
        )
    )
    persisted = _venue_scope_from_event(stored)
    if persisted != scope:
        raise RecoveryTransitionError(
            f"venue scope dedupe conflicts for order {order.id!r}"
        )
    return scope


async def await_accepted_submit_finalizer(
    finalizer: Coroutine[Any, Any, _FinalizerResult],
) -> _FinalizerResult:
    """Finish accepted/unknown-send ownership before propagating cancellation.

    The finalizer runs in its own task under ``shield``.  If shutdown cancels the
    producer, repeated cancellation requests are consumed until the ownership
    task finishes; the original cancellation still propagates afterward.  This
    is the accepted-submit equivalent of the candidate-approval compensation
    discipline in ``StoreBackedFacade``.
    """

    task = asyncio.create_task(finalizer)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        try:
            task.result()
        except asyncio.CancelledError:
            _log.error("accepted-submit ownership finalizer was cancelled")
        except Exception:  # noqa: BLE001 - preserve producer cancellation
            _log.exception("accepted-submit ownership finalizer failed")
        raise


def accepted_broker_identity_is_tracked(
    order: Optional[Order], broker_order_id: str
) -> bool:
    """Whether durable order state already adopted this accepted venue id."""

    return (
        order is not None
        and order.broker_order_id == broker_order_id
        and order.status
        in {
            OrderStatus.SUBMITTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.CANCEL_PENDING,
            OrderStatus.FILLED,
        }
    )


async def accepted_broker_identity_is_durably_tracked(
    store: StateStore, order_id: str, broker_order_id: str
) -> bool:
    """Re-read after a lost write response and recognize a committed adoption."""

    try:
        current = await store.get_order(order_id)
    except Exception:  # noqa: BLE001 - absence of proof falls through to recovery
        return False
    return accepted_broker_identity_is_tracked(current, broker_order_id)


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
    That is what makes a reconciliation-observed fill and a later direct poll of
    the *same* execution dedup to ONE (INV-5 / R8) — never a double-count. A
    priced venue execution is ``BROKER_AUTHORITATIVE`` truth even when the ingress
    is ``RECONCILIATION``; the *identity* stays the venue execution id so the two
    observations cannot diverge."""

    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    source_fill_id: str
    authority: EventAuthority = EventAuthority.SYNTHETIC


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
    filled_quantity: float
    quantity: Optional[float] = None
    order_type: Optional[str] = None
    limit_price: Optional[float] = None
    time_in_force: Optional[str] = None
    order_class: Optional[str] = None
    asset_class: Optional[str] = None
    quantity_mode: Optional[str] = None
    extended_hours: Optional[bool] = None
    has_legs: Optional[bool] = None
    position_intent: Optional[str] = None
    replaces_broker_order_id: Optional[str] = None
    advanced_fields: tuple[str, ...] = ()


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


def order_has_dynamic_venue_type(order: Order) -> bool:
    """Whether submission may render the persisted intent as another wire type.

    Protective MARKET sells remain MARKET in durable intent state but are sent as
    live-priced LIMIT orders outside regular hours.  Later broker correlation
    therefore cannot derive their exact type/limit from the Order row alone.
    Direct acknowledgements are still validated against the rendered copy.
    """

    return (
        OrderSide(order.side) is OrderSide.SELL
        and OrderType(order.order_type) is OrderType.MARKET
    )


def venue_scope_matches_order(
    order: Order,
    *,
    symbol: str,
    side: OrderSide,
    quantity: Optional[float],
    filled_quantity: Optional[float],
    order_type: Optional[str],
    limit_price: Optional[float],
    time_in_force: Optional[str],
    order_class: Optional[str],
    asset_class: Optional[str] = None,
    quantity_mode: Optional[str] = None,
    extended_hours: Optional[bool] = None,
    has_legs: Optional[bool] = None,
    position_intent: Optional[str] = None,
    replaces_broker_order_id: Optional[str] = None,
    advanced_fields: Sequence[str] = (),
    expected_scope: Optional[VenueOrderScope] = None,
) -> bool:
    """Compare venue scope without inventing a rendered protective-sell type.

    A protective MARKET sell can be rendered as MARKET or as a live-priced LIMIT
    order.  Only the current claim occurrence's persisted ``VenueOrderScope`` can
    authenticate that choice.  If the current occurrence has no scope, fail
    closed so the report remains on the uncertainty/targeted-recovery path.
    """

    type_value = (
        str(getattr(order_type, "value", order_type)).strip().lower()
        if order_type is not None
        else None
    )
    expected_position_intent = (
        "buy_to_open" if OrderSide(order.side) is OrderSide.BUY else "sell_to_close"
    )
    if expected_scope is not None:
        type_and_price_match = (
            type_value == expected_scope.order_type.value
            and limit_price == expected_scope.limit_price
            and time_in_force == expected_scope.time_in_force
            and order_class == expected_scope.order_class
            and asset_class == expected_scope.asset_class
            and quantity_mode == expected_scope.quantity_mode
            and (
                expected_scope.extended_hours is None
                or extended_hours == expected_scope.extended_hours
            )
            and has_legs is False
            and not advanced_fields
            and replaces_broker_order_id == expected_scope.replaces_broker_order_id
        )
    elif order_has_dynamic_venue_type(order):
        type_and_price_match = False
    else:
        type_and_price_match = (
            type_value is None or type_value == OrderType(order.order_type).value
        ) and (limit_price is None or limit_price == order.limit_price)
    managed_filled_quantity = (
        filled_quantity is not None
        and not isinstance(filled_quantity, bool)
        and finite_number_reason(filled_quantity) is None
        and filled_quantity >= 0
        and float(filled_quantity).is_integer()
    )
    return (
        symbol == order.symbol
        and OrderSide(side) is OrderSide(order.side)
        and (
            quantity == order.quantity
            if expected_scope is not None
            else quantity is None or quantity == order.quantity
        )
        and type_and_price_match
        and managed_filled_quantity
        and (
            expected_scope is not None
            or time_in_force is None
            or time_in_force == "day"
        )
        and (
            expected_scope is not None or order_class is None or order_class == "simple"
        )
        and (
            expected_scope is not None
            or asset_class is None
            or asset_class == "us_equity"
        )
        and (
            expected_scope is not None
            or quantity_mode is None
            or quantity_mode == "qty"
        )
        and (expected_scope is not None or has_legs in (None, False))
        and (expected_scope is not None or not advanced_fields)
        and position_intent in (None, expected_position_intent)
        and (
            expected_scope is not None
            or extended_hours is None
            or (type_value == OrderType.MARKET.value and extended_hours is False)
            or type_value == OrderType.LIMIT.value
        )
    )


def _client_identity_matches_order(
    report: BrokerOrderReport,
    order: Order,
    expected_scope: Optional[VenueOrderScope] = None,
) -> bool:
    """Return whether a client-id candidate agrees with immutable order scope."""

    return report.client_order_id == order.id and venue_scope_matches_order(
        order,
        symbol=report.symbol,
        side=report.side,
        quantity=report.quantity,
        filled_quantity=report.filled_quantity,
        order_type=report.order_type,
        limit_price=report.limit_price,
        time_in_force=report.time_in_force,
        order_class=report.order_class,
        asset_class=report.asset_class,
        quantity_mode=report.quantity_mode,
        extended_hours=report.extended_hours,
        has_legs=report.has_legs,
        position_intent=report.position_intent,
        replaces_broker_order_id=report.replaces_broker_order_id,
        advanced_fields=report.advanced_fields,
        expected_scope=expected_scope,
    )


def _broker_identity_matches_order(
    report: BrokerOrderReport,
    order: Order,
    expected_scope: Optional[VenueOrderScope] = None,
) -> bool:
    """Require an exact broker id row to agree with immutable local scope."""

    return (
        report.broker_order_id == order.broker_order_id
        and (
            report.client_order_id == order.id
            if expected_scope is not None
            else report.client_order_id is None or report.client_order_id == order.id
        )
        and venue_scope_matches_order(
            order,
            symbol=report.symbol,
            side=report.side,
            quantity=report.quantity,
            filled_quantity=report.filled_quantity,
            order_type=report.order_type,
            limit_price=report.limit_price,
            time_in_force=report.time_in_force,
            order_class=report.order_class,
            asset_class=report.asset_class,
            quantity_mode=report.quantity_mode,
            extended_hours=report.extended_hours,
            has_legs=report.has_legs,
            position_intent=report.position_intent,
            replaces_broker_order_id=report.replaces_broker_order_id,
            advanced_fields=report.advanced_fields,
            expected_scope=expected_scope,
        )
    )


def plan_reconciliation(
    *,
    local_open_orders: list[Order],
    local_positions: list[Position],
    broker_orders: list[BrokerOrderReport],
    broker_positions: list[BrokerPositionReport],
    now: datetime,
    venue_scopes_by_order_id: Optional[Mapping[str, VenueOrderScope]] = None,
    recent_threshold_ms: int = DEFAULT_RECENT_ORDER_THRESHOLD_MS,
    avg_price_tolerance: float = DEFAULT_AVG_PRICE_TOLERANCE,
) -> ReconciliationPlan:
    """Fold the local + broker snapshots into a :class:`ReconciliationPlan` (§7).

    ``local_open_orders`` should be the orders open at the venue (status in
    :data:`OPEN_STATUSES`); the engine tolerates others (it simply won't reconcile
    a terminal one). A known ``broker_order_id`` is authoritative. Orders whose ack
    was lost and therefore have no broker id may match the deterministic client id,
    but only when the report's immutable symbol and side agree. ``now`` is injected
    (§12).
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
        if order.broker_order_id is not None:
            broker_candidate = by_broker_id.get(order.broker_order_id)
            if broker_candidate is not None and _broker_identity_matches_order(
                broker_candidate,
                order,
                (venue_scopes_by_order_id or {}).get(order.id),
            ):
                report = broker_candidate
        else:
            client_candidate = by_client_id.get(order.id)
            if client_candidate is not None and _client_identity_matches_order(
                client_candidate,
                order,
                (venue_scopes_by_order_id or {}).get(order.id),
            ):
                report = client_candidate

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
                            # This is an explicit priced venue execution carried
                            # by the broker report, not a fabricated scalar delta.
                            authority=EventAuthority.BROKER_AUTHORITATIVE,
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
    local_by_id = {o.id: o for o in local_open_orders}
    local_by_broker_id = {
        o.broker_order_id: o for o in local_open_orders if o.broker_order_id is not None
    }
    for report in broker_orders:
        if report.broker_order_id in matched_report_ids:
            continue
        broker_order = local_by_broker_id.get(report.broker_order_id)
        if broker_order is not None and _broker_identity_matches_order(
            report,
            broker_order,
            (venue_scopes_by_order_id or {}).get(broker_order.id),
        ):
            continue
        if report.client_order_id is not None:
            client_order = local_by_id.get(report.client_order_id)
            if (
                client_order is not None
                and client_order.broker_order_id is None
                and _client_identity_matches_order(
                    report,
                    client_order,
                    (venue_scopes_by_order_id or {}).get(client_order.id),
                )
            ):
                continue
        plan.external_orders.append(
            ExternalOrder(
                broker_order_id=report.broker_order_id,
                client_order_id=report.client_order_id,
                symbol=report.symbol,
                side=OrderSide(report.side),
                status=report.status,
                filled_quantity=report.filled_quantity,
                quantity=report.quantity,
                order_type=report.order_type,
                limit_price=report.limit_price,
                time_in_force=report.time_in_force,
                order_class=report.order_class,
                asset_class=report.asset_class,
                quantity_mode=report.quantity_mode,
                extended_hours=report.extended_hours,
                has_legs=report.has_legs,
                position_intent=report.position_intent,
                replaces_broker_order_id=report.replaces_broker_order_id,
                advanced_fields=report.advanced_fields,
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
# Envelope executor — the venue leg of the engine seam (WO-0019, ADR-010 §1/§5)
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


ENVELOPE_EXEC_SUBMITTED = "submitted"
ENVELOPE_EXEC_REPRICED = "repriced"
ENVELOPE_EXEC_DIVERGENCE = "divergence"  # frozen + event; zero venue calls
ENVELOPE_EXEC_BLOCKED = "blocked"  # claim control gate held it; order stays CREATED
ENVELOPE_EXEC_QUARANTINED = "quarantined"  # ambiguous venue outcome (ADR-002)
ENVELOPE_EXEC_RELEASED = "released"  # transient failure; order back to CREATED
ENVELOPE_EXEC_REJECTED = "rejected"  # definitive venue rejection
ENVELOPE_EXEC_REFUSED_STALE = "refused_stale"  # WO-0029A: benign stale-plan
# refusal at the write seam — evented, no freeze, policy replans next tick
ENVELOPE_EXEC_CANCELLED = "cancelled"  # redrive refusal: staged order locally
# CANCELED with zero venue calls (WO-0024 — non-ACTIVE envelope, stale staging,
# or a rail the CURRENT state no longer satisfies)

# A staged-but-undriven action is only redrivable while it is FRESH: past this
# ceiling the decision that produced it is stale (crash-restart warm-up,
# freeze->resume stretch, long outage) and the policy must re-decide from
# current data instead. Two 30s ticks + slack. (WO-0024 / REV-0023 F3 — the
# tape itself is monitoring-owned; this age bound subsumes the
# restart-with-empty-tape scenario at the executor seam.)
REDRIVE_MAX_STAGED_AGE_S = ENVELOPE_MAX_STAGED_AGE_S


@dataclass(frozen=True)
class EnvelopeExecutionResult:
    outcome: str
    order_id: Optional[str] = None
    broker_order_id: Optional[str] = None
    detail: str = ""


async def quarantine_or_own_ambiguous_submit(
    store: StateStore,
    order: Order,
    exc: AmbiguousBrokerError,
    *,
    context: str,
    extra_payload: Optional[Mapping[str, object]] = None,
) -> None:
    """Make an unknown venue send durably unreachable by every resubmit path.

    TIMEOUT_QUARANTINE is the normal owner. If a concurrent local transition
    makes that projection impossible, an open needs-review recovery retains the
    local/client identity. Both ordinary and envelope producers share this seam.
    """

    try:
        await store.quarantine_timed_out_order(order.id, reason="ambiguous_submit")
        return
    except Exception as quarantine_exc:  # noqa: BLE001 - ownership is mandatory
        try:
            current = await store.get_order(order.id)
        except Exception:  # noqa: BLE001 - original immutable scope is sufficient
            current = None
        scoped = current if current is not None else order
        payload = dict(extra_payload or {})
        payload.update(
            {
                "ambiguous_submit": True,
                "context": context,
                "quarantine_failed": True,
                "quarantine_error": str(quarantine_exc),
            }
        )
        await store.create_submit_recovery(
            local_order_id=scoped.id,
            broker_order_id=scoped.broker_order_id or "",
            client_order_id=scoped.id,
            symbol=scoped.symbol,
            side=scoped.side,
            quantity=scoped.quantity,
            limit_price=scoped.limit_price,
            failure_reason=(
                f"ambiguous {context} could not enter timeout quarantine: {exc}"
            ),
            session_id=scoped.session_id,
            candidate_id=scoped.candidate_id,
            cleanup_status=RECOVERY_NEEDS_REVIEW,
            event_type=EventType.SUBMIT_RECOVERY_NEEDS_REVIEW.value,
            extra_payload=payload,
        )


async def record_accepted_submit_uncertainty(
    store: StateStore,
    order: Order,
    broker_order_id: str,
    exc: BaseException,
    *,
    extra_payload: Optional[Mapping[str, object]] = None,
) -> None:
    """Persist the last owner for a venue acceptance with no recovery row.

    This lower-level seam is shared by ordinary and envelope submissions.  The
    immutable order scope and reserved payload keys always win over optional
    producer context so no caller can mint conflicting accepted-submit truth.
    """

    try:
        broker_order_id = normalize_broker_order_id(broker_order_id)
    except ValueError as identity_exc:
        raise RecoveryTransitionError(
            "accepted-submit uncertainty requires a string broker identity"
        ) from identity_exc
    if not broker_order_id:
        raise RecoveryTransitionError(
            "accepted-submit uncertainty requires a concrete broker identity"
        )
    payload = dict(extra_payload or {})
    payload.update(
        {
            "reason": ACCEPTED_SUBMIT_UNPERSISTED_REASON,
            "broker_order_id": broker_order_id,
            "error": str(exc),
        }
    )
    dedupe_key = f"accepted_submit_unpersisted:{order.id}:{broker_order_id}"
    stored = await store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=dedupe_key,
            ts_init=order.updated_at,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.limit_price,
            order_id=order.id,
            session_id=order.session_id,
            correlation_id=order.sell_intent_id or order.candidate_id,
            payload=payload,
        )
    )
    if canonical_accepted_submit_broker_id(stored, order) != broker_order_id:
        raise RecoveryTransitionError(
            "accepted-submit uncertainty dedupe belongs to conflicting truth"
        )


async def _persist_or_recover_envelope_venue_order(
    store: StateStore,
    *,
    order: Order,
    broker_order_id: str,
    envelope_id: Optional[str],
    kind: ActionKind,
    exc: BaseException,
) -> bool:
    """Make a broker-accepted Envelope order durably visible.

    Returns ``True`` when a retry persisted the normal ``SUBMITTED`` state.
    Returns ``False`` when an unresolved recovery record now owns cleanup of
    the venue order.  A failure to persist *either* representation is raised:
    after venue acceptance, silently continuing without durable truth would be
    an invisible live-order orphan.
    """

    try:
        await store.append_event(
            "order_submit_unpersisted",
            message=(
                f"envelope order {order.symbol} accepted by broker as "
                f"{broker_order_id} but could not be marked SUBMITTED"
            ),
            symbol=order.symbol,
            order_id=order.id,
            payload={
                "broker_order_id": broker_order_id,
                "envelope_id": envelope_id,
                "kind": kind.value,
                "error": str(exc),
            },
            session_id=order.session_id,
            correlation_id=order.sell_intent_id,
        )
    except Exception:  # noqa: BLE001 - recovery ledger below is authoritative
        pass

    try:
        current = await store.get_order(order.id)
    except Exception:  # noqa: BLE001 - still attempt the durable recovery write
        current = None
    if current is not None:
        if accepted_broker_identity_is_tracked(current, broker_order_id):
            return True
        if current.status is OrderStatus.SUBMITTING:
            try:
                await store.transition_order(
                    order.id,
                    OrderStatus.SUBMITTED,
                    broker_order_id=broker_order_id,
                )
                return True
            except Exception:  # noqa: BLE001 - recovery is the required fallback
                if await accepted_broker_identity_is_durably_tracked(
                    store, order.id, broker_order_id
                ):
                    return True

    try:
        await store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=broker_order_id,
            client_order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason=str(exc),
            session_id=order.session_id,
            candidate_id=order.candidate_id,
            extra_payload={
                "envelope_id": envelope_id,
                "action_kind": kind.value,
                "replaces_order_id": order.replaces_order_id,
            },
        )
    except Exception as recovery_exc:  # noqa: BLE001 - fail loudly, never mask orphan
        await record_accepted_submit_uncertainty(
            store,
            order,
            broker_order_id,
            recovery_exc,
            extra_payload={
                "envelope_id": envelope_id,
                "kind": kind.value,
                "replaces_order_id": order.replaces_order_id,
            },
        )
        raise RuntimeError(
            "accepted envelope submit has durable uncertainty but no recovery owner"
        ) from recovery_exc
    return False


async def _finalize_accepted_envelope_order(
    store: StateStore,
    *,
    order: Order,
    broker_order_id: str,
    envelope_id: Optional[str],
    kind: ActionKind,
) -> bool:
    """Adopt one accepted Envelope id or install its durable recovery owner."""

    try:
        await store.transition_order(
            order.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
        )
        return True
    except asyncio.CancelledError as exc:
        # A cancellation raised by the persistence await is still post-accept.
        # Finish ownership in this shielded finalizer, then preserve shutdown.
        try:
            await _persist_or_recover_envelope_venue_order(
                store,
                order=order,
                broker_order_id=broker_order_id,
                envelope_id=envelope_id,
                kind=kind,
                exc=exc,
            )
        except Exception:  # noqa: BLE001 - fallback may already be durable
            _log.exception(
                "envelope accepted-submit cancellation recovery failed for %s",
                order.id,
            )
        raise
    except Exception as exc:  # noqa: BLE001 - venue acceptance needs ownership
        return await _persist_or_recover_envelope_venue_order(
            store,
            order=order,
            broker_order_id=broker_order_id,
            envelope_id=envelope_id,
            kind=kind,
            exc=exc,
        )


def market_snapshot_fingerprint(snapshot: MarketSnapshot) -> str:
    """Deterministic fingerprint of the snapshot a decision was made against —
    stamped into every ENVELOPE_ACTION event (ADR-010 §6) so an action is
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


async def _explicit_envelope_claim_rail_reason(
    store: StateStore,
    *,
    order: Order,
    envelope_id: Optional[str],
    now: datetime,
) -> Optional[str]:
    """Replay the shared rails for an explicitly injected executor clock.

    Structural identity remains store-authoritative at the atomic claim.  This
    preflight only preserves deterministic/replay clocks for the same hard-rail
    function; current quantity and position are checked again under the store
    claim, so this read cannot authorize a race.
    """

    events = await store.get_execution_events()
    actions = [
        event
        for event in events
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION
        and event.order_id == order.id
    ]
    parent_ids = {event.envelope_id for event in actions}
    if not actions or None in parent_ids or len(parent_ids) != 1:
        return None
    parent_id = next(iter(parent_ids))
    assert parent_id is not None
    if envelope_id is not None and parent_id != envelope_id:
        return None
    envelope = await store.get_envelope(parent_id)
    if envelope is None:
        return None
    position = await store.get_position(order.symbol)
    return envelope_claim_hard_rail_reason(
        envelope=envelope,
        order=order,
        action_event=actions[0],
        history=events,
        current_position=position.quantity,
        now=now,
    )


async def _drive_staged_order(
    store: StateStore,
    adapter: BrokerAdapter,
    *,
    order: Order,
    kind: ActionKind,
    working_order: Optional[Order],
    envelope_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> EnvelopeExecutionResult:
    """The venue leg for one already-staged order (fresh or redriven)."""

    if now is not None:
        explicit_rail = await _explicit_envelope_claim_rail_reason(
            store,
            order=order,
            envelope_id=envelope_id,
            now=now,
        )
        if explicit_rail is not None:
            return EnvelopeExecutionResult(
                ENVELOPE_EXEC_BLOCKED,
                order_id=order.id,
                detail="envelope hard rail changed after staging: " + explicit_rail,
            )
    claim = await store.claim_order_for_submission(order.id)
    if claim.outcome != CLAIM_CLAIMED:
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_BLOCKED,
            order_id=order.id,
            detail=claim.reason or claim.outcome,
        )
    assert claim.order is not None
    # The final claim authorized one persisted action/order edge.  Derive the
    # venue operation and predecessor from that claimed row; ``kind`` and
    # ``working_order`` are plan-time conveniences, never a second authority.
    order = claim.order
    kind = (
        ActionKind.REPRICE if order.replaces_order_id is not None else ActionKind.SUBMIT
    )
    if kind is ActionKind.REPRICE:
        assert order.replaces_order_id is not None
        working_order = await store.get_order(order.replaces_order_id)
        if (
            working_order is None
            or working_order.broker_order_id is None
            or working_order.status
            not in (OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED)
        ):
            # The predecessor changed after the atomic claim but before the
            # venue call. No broker request has occurred, so release this exact
            # claim for a fresh policy decision instead of guessing.
            await store.transition_order(order.id, OrderStatus.CREATED)
            return EnvelopeExecutionResult(
                ENVELOPE_EXEC_RELEASED,
                order_id=order.id,
                detail="reprice predecessor changed after claim; released",
            )
    else:
        working_order = None
    submission_now = now or utcnow()
    submission_session = session_type_for(submission_now)
    extended_hours: Optional[bool] = OrderType(
        order.order_type
    ) is OrderType.LIMIT and submission_session in {
        SessionType.PRE_MARKET,
        SessionType.AFTER_HOURS,
    }
    if working_order is not None:
        predecessor_scope = (await load_venue_order_scopes(store, [working_order])).get(
            working_order.id
        )
        extended_hours = (
            predecessor_scope.extended_hours if predecessor_scope is not None else None
        )
    venue_scope = await get_or_record_venue_order_scope(
        store,
        order=order,
        rendered_order=order,
        extended_hours=extended_hours,
        replaces_broker_order_id=(
            working_order.broker_order_id if working_order is not None else None
        ),
    )
    venue_order = rendered_order_from_scope(order, venue_scope)
    try:
        if kind is ActionKind.REPRICE:
            assert working_order is not None
            assert working_order.broker_order_id is not None  # staged guarantees
            new_broker_id = await adapter.replace_order(
                working_order.broker_order_id,
                client_order_id=order.id,  # deterministic (ADR-002 recovery key)
                expected_symbol=order.symbol,
                expected_side=OrderSide(order.side),
                expected_order_type=OrderType(order.order_type),
                expected_time_in_force="day",
                expected_order_class="simple",
                venue_scope=venue_scope,
                limit_price=venue_order.limit_price,
                quantity=venue_order.quantity,
            )
        else:
            new_broker_id = await adapter.submit_order(
                venue_order, venue_scope=venue_scope
            )
        if not isinstance(new_broker_id, str) or not new_broker_id.strip():
            # The venue call already returned, so a missing identity is an
            # unknown-send outcome, never proof of a pre-flight failure.
            raise AmbiguousBrokerError("broker returned an invalid order id")
        new_broker_id = new_broker_id.strip()
    except asyncio.CancelledError:
        # Cancellation during an adapter await is an unknown-send outcome: the
        # SDK/thread may have completed the venue mutation. Persist quarantine
        # (or a terminal-race recovery owner) before propagating shutdown.
        await await_accepted_submit_finalizer(
            quarantine_or_own_ambiguous_submit(
                store,
                order,
                AmbiguousBrokerError(
                    f"{kind.value} cancelled after its venue call may have started"
                ),
                context=f"envelope_{kind.value}_cancelled",
                extra_payload={
                    "envelope_id": envelope_id,
                    "kind": kind.value,
                    "replaces_order_id": order.replaces_order_id,
                },
            )
        )
        raise
    except AmbiguousBrokerError as exc:
        # The venue MAY have the replacement/submission. Quarantine; the
        # targeted client_order_id query resolves it; the envelope pauses
        # (stage refuses) until then — never blind-re-replace.
        await await_accepted_submit_finalizer(
            quarantine_or_own_ambiguous_submit(
                store,
                order,
                exc,
                context=f"envelope_{kind.value}",
                extra_payload={
                    "envelope_id": envelope_id,
                    "kind": kind.value,
                    "replaces_order_id": order.replaces_order_id,
                },
            )
        )
        return EnvelopeExecutionResult(ENVELOPE_EXEC_QUARANTINED, order_id=order.id)
    except TerminalBrokerError as exc:
        # S1 (WO-0035, extends the WO-0034 spec-1 pattern to the venue leg): a
        # broker-authoritative rejection REASON is recorded, never hidden — the
        # bare transition_order(REJECTED) row carries no detail and the caller
        # used to drop the result entirely.
        await store.append_event(
            "envelope_venue_rejected",
            message=f"venue rejected {kind.value}: {exc}",
            symbol=order.symbol,
            order_id=order.id,
            payload={
                "detail": str(exc),
                "envelope_id": envelope_id,
                "kind": kind.value,
            },
            session_id=order.session_id,
        )
        await store.transition_order(order.id, OrderStatus.REJECTED)
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_REJECTED, order_id=order.id, detail=str(exc)
        )
    except BrokerError as exc:
        # Provably-pre-flight transient: release the claim; the SAME staged
        # order (and its already-committed budget accounting) redrives later.
        # S1: the release reason is evented so a repeatedly-releasing order's
        # history is reconstructible from the durable log alone.
        await store.append_event(
            "envelope_venue_released",
            message=f"venue call failed pre-flight; released for redrive: {exc}",
            symbol=order.symbol,
            order_id=order.id,
            payload={
                "detail": str(exc),
                "envelope_id": envelope_id,
                "kind": kind.value,
            },
            session_id=order.session_id,
        )
        await store.transition_order(order.id, OrderStatus.CREATED)
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_RELEASED, order_id=order.id, detail=str(exc)
        )

    tracked = await await_accepted_submit_finalizer(
        _finalize_accepted_envelope_order(
            store,
            order=order,
            broker_order_id=new_broker_id,
            envelope_id=envelope_id,
            kind=kind,
        )
    )
    if not tracked:
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_QUARANTINED,
            order_id=order.id,
            broker_order_id=new_broker_id,
            detail=(
                "venue accepted order but local transition failed; durable "
                "recovery owns cleanup"
            ),
        )
    if kind is ActionKind.REPRICE:
        assert working_order is not None
        # A successful replace acknowledgement proves only that the replacement
        # was accepted. Alpaca may still leave the predecessor working, fill it
        # before the replace reaches the venue, or reject the child. Preserve the
        # predecessor's last authoritative local status and keep polling it until
        # its own venue response confirms cancel/reject/fill. The two unresolved
        # lineage children also pause further staging until one converges.
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_REPRICED,
            order_id=order.id,
            broker_order_id=new_broker_id,
        )
    return EnvelopeExecutionResult(
        ENVELOPE_EXEC_SUBMITTED, order_id=order.id, broker_order_id=new_broker_id
    )


async def execute_envelope_action(
    store: StateStore,
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
    if staged.outcome == STAGE_REFUSED_STALE:
        # WO-0029A: facts changed between plan and write — refused + evented,
        # no freeze; the policy replans from fresh data next tick.
        return EnvelopeExecutionResult(
            ENVELOPE_EXEC_REFUSED_STALE,
            detail="stale plan refused — facts changed between plan and write",
        )
    assert staged.order is not None
    return await _drive_staged_order(
        store,
        adapter,
        order=staged.order,
        kind=action.kind,
        working_order=staged.working_order,
        envelope_id=envelope_id,
        now=now,
    )


async def redrive_staged_envelope_action(
    store: StateStore,
    adapter: BrokerAdapter,
    envelope_id: str,
    *,
    now: Optional[datetime] = None,
) -> Optional[EnvelopeExecutionResult]:
    """Resume a staged-but-not-executed action (transient release / crash
    between staging and the venue call) WITHOUT re-staging — the budget
    accounting committed with the original staging and must not be spent
    twice. Returns None when there is nothing to redrive.

    WO-0024 (REV-0023 F3, FINDING-W3-redrive-revalidation-bypass): before any
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
    rail: Optional[str] = None
    envelope = await store.get_envelope(envelope_id)
    if envelope is None or envelope.status is not EnvelopeStatus.ACTIVE:
        rail = "envelope_state"
        refusal = (
            "envelope is "
            f"{envelope.status.value if envelope is not None else 'missing'}"
        )
    else:
        staged_at = last.ts_event or last.ts_init
        age = (ts - staged_at).total_seconds()
        if age < 0:
            rail = "staleness"
            refusal = f"staged action is {-age:.0f}s in the future"
        elif age > REDRIVE_MAX_STAGED_AGE_S:
            rail = "staleness"
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
                rail = violation.rail
                refusal = f"{violation.rail}: {violation.detail}"
            else:
                # WO-0026: reduce-only re-check — the position may have
                # shrunk (fills, manual flatten) since staging.
                position = await store.get_position(envelope.symbol)
                if order.quantity > max(0, position.quantity):
                    rail = "reduce_only"
                    refusal = (
                        f"reduce_only: SELL {order.quantity} exceeds live "
                        f"position {max(0, position.quantity)}"
                    )

    if refusal is not None:
        # spec-1 (REV-0023 Phase-A2): durably EVENT the refusal (rail + detail)
        # before the local cancel — a redrive rail refusal (incl. the reduce_only
        # safety refusal) must leave an audit trail, not vanish into a bare
        # transition_order(CANCELED) whose caller drops the detail.
        await store.append_event(
            "envelope_redrive_refused",
            message=f"redrive refused — {refusal}; staged order locally cancelled",
            symbol=envelope.symbol if envelope is not None else order.symbol,
            order_id=order.id,
            payload={
                "rail": rail,
                "detail": refusal,
                "envelope_id": envelope_id,
                "kind": kind.value,
            },
            session_id=order.session_id,
        )
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
        store,
        adapter,
        order=order,
        kind=kind,
        working_order=working_order,
        envelope_id=envelope_id,
        now=ts,
    )
