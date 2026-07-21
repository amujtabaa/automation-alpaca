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

from pydantic import BaseModel, Field

from app.models import (
    Candidate,
    Event,
    ExecutionEnvelope,
    Fill,
    Order,
    Position,
    SellIntent,
    SessionRecord,
    SubmitRecoveryRecord,
)


class EnvelopeView(ExecutionEnvelope):
    """Read-only envelope plus its event-derived replace-budget usage.

    The persisted mandate intentionally has no ``replaces_used`` field. This
    required read-model value is computed from the execution-event log by the
    query facade and may exceed the approved budget if durable truth ever shows
    an overrun; display never clamps or hides that fact.
    """

    replaces_used: int = Field(ge=0)


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


class ReviewView(BaseModel):
    """Everything needed to review one session (current or a past date) — the
    facade's return for ``GET /api/review`` (P6b). The facade owns the multi-read
    + the D-012 closed-vs-active point-in-time branching (snapshot rows for a
    closed session, the live fold for the active one); the route just maps this to
    the ``ReviewResponse`` HTTP schema (identical fields). Lives here, not in
    ``app.api.schemas``, so the facade never imports up into the API layer."""

    date: str
    session: Optional[SessionRecord]
    candidates: list[Candidate]
    orders: list[Order]
    fills: list[Fill]
    positions: list[Position]
    events: list[Event]
    sell_intents: list[SellIntent] = Field(default_factory=list)


class MarketSnapshotView(BaseModel):
    """One symbol's current market-data snapshot for the cockpit (Phase 5/6).

        The facade's typed read surface for ``GET /api/marketdata/snapshots``: mirrors
        ``app.marketdata.service.MarketSnapshot`` (working data, never persisted) plus
        ``pct_move``, which the facade computes with the SAME ``app.features.pct_move``
        the Strategy Engine decides on — so the route stops importing ``app.features``
        and the market-data port, and the cockpit never re-derives the number. Field
        order matches the former ``MarketSnapshotResponse``. (``volume`` is a float —
    REV-0002 F-003 — so a whole-share value renders as ``100000.0``; no consumer of
    this endpoint relies on an integer JSON token.)"""

    symbol: str
    last_price: Optional[float]
    bid: Optional[float]
    ask: Optional[float]
    # float, mirroring MarketSnapshot.volume — a fractional session volume must
    # round-trip without a Pydantic int-coercion ValidationError (REV-0002 F-003).
    volume: Optional[float]
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


class FlattenResponse(BaseModel):
    """Result of ``POST /api/positions/{symbol}/flatten`` (and .../emergency-reduce)
    — the sell intent that now owns the exit and the SELL order it produced
    (``order`` is ``None`` only in the degenerate case where the intent exists but
    its order can't be read). The command facade returns this; the route uses it as
    ``response_model`` (P6e). Moved from ``app.api.schemas`` (ADR-006 direction)."""

    intent: SellIntent
    order: Optional[Order] = None
    # deferred=True means NO manual order was submitted: the flatten was safely
    # deferred to an already in-flight protection exit (INV-036 / REV-0002 F-001).
    # Both fields default (a non-deferral response just adds deferred=false /
    # deferred_order_status=null) — additive and backward-compatible for clients.
    deferred: bool = False
    deferred_order_status: Optional[str] = None


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
    # Additive convenience echo for the cockpit.  The store revalidates every
    # field under its write lock; this view never authorizes the command.
    candidate_id: Optional[str] = None
    sell_intent_id: Optional[str] = None
    envelope_id: Optional[str] = None
    lineage_valid: bool = True
    lineage_error: Optional[str] = None


class OperatorOrdersResponse(BaseModel):
    """The operator's single source of order-lifecycle truth (``GET
    /api/operator/orders``). Every durable non-terminal order and every open
    recovery record, each already classified — read-only; no mutation lives
    here (the existing ``/orders`` raw read and the ``/orders/{id}/cancel``
    action are unchanged)."""

    orders: list[OperatorOrderView]
    recoveries: list[OperatorRecoveryView]
