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
