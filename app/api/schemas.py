"""Request/response bodies specific to the HTTP layer.

Persisted entities (Candidate, Order, ...) are returned directly as their
Pydantic models; these schemas cover only request inputs and composite
responses that don't map to a single stored entity.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import (
    Candidate,
    Event,
    Fill,
    Order,
    Position,
    SessionRecord,
    SubmitRecoveryRecord,
)


class WatchlistCreate(BaseModel):
    """Body for ``POST /api/watchlist``.

    Upsert semantics: a new symbol is added; an existing one has its ``armed``
    flag set to the provided value (so arm/disarm goes through this endpoint).
    """

    symbol: str = Field(min_length=1)
    armed: bool = False


class KillSwitchRequest(BaseModel):
    """Body for ``POST /api/controls/kill-switch``. Defaults to engaging it."""

    engaged: bool = True


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
    suggested_quantity: int = Field(default=10, gt=0)
    # Non-optional: a JSON ``null`` must be rejected (422), not accepted and then
    # turned into a LIMIT order with no price. ``gt=0`` rejects zero/negative;
    # ``allow_inf_nan=False`` rejects ``Infinity``/``NaN`` (which slip past ``gt=0``:
    # ``inf > 0`` is ``True``) before they can reach the store (BACKEND-1).
    suggested_limit_price: float = Field(default=1.00, gt=0, allow_inf_nan=False)


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
