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


class ReviewResponse(BaseModel):
    """Everything needed to review one session (current or a past date)."""

    date: str
    session: Optional[SessionRecord]
    candidates: list[Candidate]
    orders: list[Order]
    fills: list[Fill]
    positions: list[Position]
    events: list[Event]
