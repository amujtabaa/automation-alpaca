"""Request/response bodies specific to the HTTP layer.

Persisted entities (Candidate, Order, ...) are returned directly as their
Pydantic models; these schemas cover only request inputs and composite
responses that don't map to a single stored entity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, StrictBool

# ExternalOrderView / PositionMismatchView are the reconciliation facade's own
# typed return DTOs (app.facade.dtos). Imported here so ReconciliationStatusResponse
# can compose them and routes can reference them; api → facade is the allowed
# dependency direction (ADR-005 / Phase 5 import boundaries).
from app.facade.dtos import ExternalOrderView, PositionMismatchView
from app.models import (
    Candidate,
    Event,
    Fill,
    Order,
    Position,
    SellIntent,
    SessionRecord,
    SubmitRecoveryRecord,
)


class WatchlistCreate(BaseModel):
    """Body for ``POST /api/watchlist``.

    Upsert semantics: a new symbol is added; an existing one has its ``armed``
    flag set to the provided value (so arm/disarm goes through this endpoint).
    """

    symbol: str = Field(min_length=1)
    # StrictBool (AIR-005): a JSON string like "true"/"false" or a number 0/1 is
    # rejected (422), never coerced — the arm state is a control flag.
    armed: StrictBool = False


class KillSwitchRequest(BaseModel):
    """Body for ``POST /api/controls/kill-switch``. Defaults to engaging it."""

    # StrictBool (AIR-005): `{"engaged": "false"}` meant to DISENGAGE must be a
    # clean 422, not a truthy-string coercion that *engages* the emergency stop.
    engaged: StrictBool = True


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str
    time: datetime


class MockCandidateCreate(BaseModel):
    """Body for POST /api/dev/candidates — DEV/MOCK scaffolding only.

    A minimal way to hand-inject an arbitrary candidate for manual testing —
    NOT strategy logic. Phase 5's real Strategy Engine (``app/strategy.py`` +
    ``app/strategy_loop.py``) now generates real candidates independently; this
    route remains useful for testing states the strategy wouldn't naturally
    produce (an exact symbol/price/quantity on demand).
    """

    symbol: str = Field(min_length=1)
    strategy: Optional[str] = "mock"
    reason: Optional[str] = "injected mock candidate for manual testing"
    # ``strict=True`` (D-021 / D-023): a lax int/float field silently coerces
    # a JSON ``true``/``"5"`` (bool/numeric-string) to ``1``/``5`` *before* this
    # request even reaches the store — by the time
    # ``app.policy.candidate_numeric_reason`` runs inside ``create_candidate``,
    # the original type is already gone, so that store-boundary guard can't
    # catch it on this path. Strict mode rejects bool/string outright (422)
    # while still accepting a genuine JSON number (including a whole-number int
    # for the float field) — closing the same silent-coercion gap for this
    # route that the store-call boundary closes with ``candidate_numeric_reason``.
    suggested_quantity: int = Field(default=10, gt=0, strict=True)
    # Non-optional: a JSON ``null`` must be rejected (422), not accepted and then
    # turned into a LIMIT order with no price. ``gt=0`` rejects zero/negative;
    # ``allow_inf_nan=False`` rejects ``Infinity``/``NaN`` (which slip past ``gt=0``:
    # ``inf > 0`` is ``True``) before they can reach the store (BACKEND-1).
    suggested_limit_price: float = Field(
        default=1.00, gt=0, allow_inf_nan=False, strict=True
    )


class MarketSnapshotResponse(BaseModel):
    """One symbol's current market-data snapshot (Phase 5).

    Mirrors ``app.marketdata.service.MarketSnapshot`` as a Pydantic model for
    the HTTP layer — the dataclass itself is working data (never persisted,
    ``docs/02_DATA_AND_PERSISTENCE.md``) and stays IO/framework-agnostic.
    ``pct_move`` is computed by the route via ``app.features.pct_move`` (the
    same function the Strategy Engine decides on) and included here so the
    cockpit never has to recompute it — Streamlit stays a pure display client
    instead of re-deriving a number a decision was actually made from.
    """

    symbol: str
    last_price: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    volume: Optional[int]
    prev_close: Optional[float]
    pct_move: Optional[float]
    updated_at: datetime
    stale: bool


class ReviewResponse(BaseModel):
    """Everything needed to review one session (current or a past date)."""

    date: str
    session: Optional[SessionRecord]
    candidates: list[Candidate]
    orders: list[Order]
    fills: list[Fill]
    positions: list[Position]
    events: list[Event]
    # Phase 7: the sell-intent lifecycle for the queried session (additive) — a
    # closed session's protective/flatten exits are reviewable alongside its
    # candidates and orders.
    sell_intents: list[SellIntent] = Field(default_factory=list)


# --- Phase 7: Sell-Side Protection ---------------------------------------- #
class FlattenResponse(BaseModel):
    """Result of ``POST /api/positions/{symbol}/flatten`` — the sell intent that
    now owns the exit and the SELL order it produced (``order`` is ``None`` only
    in the degenerate case where the intent exists but its order can't be read)."""

    intent: SellIntent
    order: Optional[Order] = None


class ProtectionConfigView(BaseModel):
    """The effective protection configuration (``GET /api/protection``)."""

    enabled: bool
    stop_loss_pct: float
    limit_buffer_pct: float
    # enabled AND the monitoring loop is actually running (so a breach would be
    # acted on) — the cockpit's "protection is live" light.
    protection_active: bool


class ProtectionPositionView(BaseModel):
    """Per open position, classified server-side (D-020: the cockpit renders,
    never re-derives). ``floor_price``/``observed_price`` are ``None`` when they
    can't be computed (no average cost / no trustworthy snapshot)."""

    symbol: str
    quantity: int
    average_price: Optional[float] = None
    floor_price: Optional[float] = None
    observed_price: Optional[float] = None
    breaching: bool = False
    paused_by_kill_switch: bool = False
    stalled: bool = False
    active_sell_intent: Optional[SellIntent] = None


class ProtectionStatusResponse(BaseModel):
    """``GET /api/protection`` — effective config + the protection state of every
    open position, for the cockpit's Position Monitor "protection mode"."""

    config: ProtectionConfigView
    positions: list[ProtectionPositionView]


class OperatorOrderView(BaseModel):
    """One durable non-terminal order, classified server-side (D-020).

    The cockpit used to interpret ``order.status`` + the latest submission-block
    audit event into a human operational state and owned the "which statuses are
    still open" filter. This carries the backend's own classification so the UI
    renders it verbatim — ``operational_status`` (from
    ``app.policy.operational_status_for``), the ``reason`` behind a held state
    (raw block-reason code, ``None`` when not held), whether a manual cancel is
    offerable, and whether the order is flagged stale — and never re-derives
    lifecycle. The full ``order`` is included for the display fields (symbol,
    quantity, price, filled, age).
    """

    order: Order
    operational_status: str
    reason: Optional[str] = None
    cancelable: bool
    stale: bool = False


class OperatorRecoveryView(BaseModel):
    """One unresolved broker-submit recovery record, classified (D-017 / D-020).

    A broker order accepted upstream that local order state can't otherwise
    show. ``operational_status`` is ``broker_submission_failed`` while the
    recovery loop is still working it or ``recovery_required`` once escalated to
    ``needs_review`` (a real untracked position a human must reconcile).
    """

    record: SubmitRecoveryRecord
    operational_status: str
    reason: Optional[str] = None


class OperatorOrdersResponse(BaseModel):
    """The operator's single source of order-lifecycle truth (``GET
    /api/operator/orders``). Every durable non-terminal order and every open
    recovery record, each already classified — read-only; no mutation lives
    here (the existing ``/orders`` raw read and the ``/orders/{id}/cancel``
    action are unchanged)."""

    orders: list[OperatorOrderView]
    recoveries: list[OperatorRecoveryView]


class ReconciliationStatusResponse(BaseModel):
    """``GET /api/reconciliation`` — the operator's read-only view of what the
    reconciliation engine has surfaced but *not* absorbed: external/unmanaged
    venue orders and broker-vs-local position drifts (Spine v2 §7). Both are
    durable, deduped audit records; neither mutates managed state or position.
    An empty response is the healthy steady state.

    The item views (``ExternalOrderView``/``PositionMismatchView``) are the
    facade's own typed return DTOs — defined in ``app.facade.dtos`` and imported
    here (api → facade is the allowed dependency direction; ADR-005 / Phase 5
    import boundaries). The route only composes them into this HTTP response."""

    external_orders: list[ExternalOrderView]
    position_mismatches: list[PositionMismatchView]
