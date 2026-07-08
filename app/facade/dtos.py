"""Typed return DTOs for the query facade — Spine v2 (ADR-005 / §10).

These are the facade's own typed read surface: a route depends on the facade
Protocol and gets these back, then composes them into its HTTP response. They
live in the facade package (not ``app.api.schemas``) so the dependency direction
stays ``api → facade`` — the facade never imports up into the API layer, which
keeps the Phase 5 import-linter contract clean.

Wave 4h: the reconciliation read surface — external/unmanaged venue orders and
broker-vs-local position drifts that reconciliation surfaced but never absorbed
(Spine v2 §7). Both are read verbatim from durable, deduped audit records; an
empty list is the healthy steady state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ExternalOrderView(BaseModel):
    """One external/unmanaged venue order surfaced by reconciliation (§7 / wave
    4e). A venue order that ties back to no local order — surfaced for review,
    **never** absorbed into managed state or folded into position. Read verbatim
    from the durable ``reconcile_external_order`` audit record (deduped at write
    time by ``broker_order_id``)."""

    broker_order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    status: Optional[str] = None
    filled_quantity: Optional[int] = None
    surfaced_at: datetime


class MarketSnapshotView(BaseModel):
    """One symbol's current market-data snapshot for the cockpit (Phase 5/6).

    The facade's typed read surface for ``GET /api/marketdata/snapshots``: mirrors
    ``app.marketdata.service.MarketSnapshot`` (working data, never persisted) plus
    ``pct_move``, which the facade computes with the SAME ``app.features.pct_move``
    the Strategy Engine decides on — so the route stops importing ``app.features``
    and the market-data port, and the cockpit never re-derives the number. Field
    order matches the former ``MarketSnapshotResponse`` so the JSON is unchanged."""

    symbol: str
    last_price: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    volume: Optional[int]
    prev_close: Optional[float]
    pct_move: Optional[float]
    updated_at: datetime
    stale: bool


class PositionMismatchView(BaseModel):
    """One broker-vs-local position drift surfaced by reconciliation (§7 / wave
    4h). Qty must match exactly; avg-px within tolerance. **Position truth is
    never overwritten** (Rule 7): this is a needs-review record that also holds
    trading reduce-only until it clears. Read verbatim from the durable
    ``reconcile_position_mismatch`` audit record (deduped at write time by
    ``(symbol, kind)``)."""

    symbol: Optional[str] = None
    kind: Optional[str] = None
    local_quantity: Optional[int] = None
    broker_quantity: Optional[int] = None
    local_avg: Optional[float] = None
    broker_avg: Optional[float] = None
    surfaced_at: datetime
