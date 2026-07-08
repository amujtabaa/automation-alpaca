"""Read-only views over positions, orders, and the event log.

These endpoints provide the cockpit's Position and Order monitors with live
data from the backend. Candidate views have moved to ``routes_candidates.py``
(which also owns the approve/reject endpoints). Positions remain read-only;
order creation happens via the candidate approval flow (Phase 3/4).
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_actor, get_command_facade, get_query_facade
from app.api.schemas import ReconciliationStatusResponse
from app.facade.commands import ExecutionCommandFacade
from app.facade.dtos import (
    FlattenResponse,
    OperatorOrdersResponse,
    ProtectionStatusResponse,
)
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
from app.facade.queries import ExecutionQueryFacade
from app.models import (
    Event,
    Order,
    Position,
    SellIntent,
    SubmitRecoveryRecord,
)

router = APIRouter(prefix="/api", tags=["trading"])


@router.get("/positions", response_model=list[Position])
async def list_positions(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[Position]:
    """Phase 1 facade migration (ADR-005): calls ``ExecutionQueryFacade.
    list_positions`` instead of the store directly. The concrete
    implementation (``app.facade.store_backed.StoreBackedQueryFacade``)
    forwards unchanged to ``StateStore.list_positions`` — see
    ``docs/SPINE_PHASE1_FACADE_REPORT.md`` for the behavior-equivalence
    proof. ``except FacadeError`` is defensive/future-proofing: this
    specific method never raises one today, but the mapping exists so a
    later facade change surfaces as a clean HTTP response rather than an
    unhandled exception.
    """
    try:
        return await query_facade.list_positions()
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.get("/reconciliation", response_model=ReconciliationStatusResponse)
async def reconciliation_status(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> ReconciliationStatusResponse:
    """Read-only reconciliation surface (ADR-005 facade / Spine v2 §7, wave 4h):
    the external/unmanaged venue orders and broker-vs-local position drifts the
    reconciliation engine surfaced but never absorbed. Both come from durable,
    deduped audit records via the query facade — the route only composes them.
    An empty response is the healthy steady state; anything here needs operator
    review and holds trading reduce-only until it clears."""
    try:
        return ReconciliationStatusResponse(
            external_orders=await query_facade.list_external_orders(),
            position_mismatches=await query_facade.list_position_mismatches(),
        )
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.get("/positions/{symbol}", response_model=Position)
async def get_position(
    symbol: str,
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> Position:
    """Derived from fills; a symbol with no fills returns a flat position.
    An out-of-domain ticker (``normalize_symbol``'s ``ValueError``) is surfaced
    as a clean 422 rather than a leaked 500 (matches the watchlist routes)."""
    try:
        return await query_facade.get_position(symbol=symbol)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.post("/positions/{symbol}/flatten", response_model=FlattenResponse)
async def flatten_position(
    symbol: str,
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> FlattenResponse:
    """Manually flatten a position (Phase 7 / D-P2, refined by ADR-003) — an
    operator-commanded full exit. Bypasses buys-paused and a closed session (§5.2);
    ADR-003 (wave 3e) DENIES an ordinary flatten while ``Halted`` (409, kill switch
    is a true all-stop) — the operator exits via ``POST .../emergency-reduce`` —
    and keeps it allowed in ``Reducing``.

    Phase 6 (ADR-005): the whole flow — the X-001 atomic
    ``StateStore.flatten_position`` decision + the best-effort open-buy cancel
    (a broker call, never under the store lock) — lives behind
    ``ExecutionCommandFacade.create_exit``; this route no longer touches the store
    or broker. 409 on a flat symbol / ADR-003 Halted-deny / oversell; 422 on a bad
    ticker.
    """
    try:
        return await command_facade.create_exit(symbol=symbol, actor=actor)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.post("/positions/{symbol}/emergency-reduce", response_model=FlattenResponse)
async def emergency_reduce(
    symbol: str,
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> FlattenResponse:
    """Emergency reduce-only exit while the kill switch is engaged (ADR-003 /
    wave 3e). Under ``Halted`` an ordinary flatten is denied; this is the explicit,
    audited operator override to exit risk anyway. It does NOT lift the kill
    switch — it grants a scoped, single-use ``{session, symbol}`` override so
    exactly one reduce-only flatten is authorized while ``TradingState`` stays
    ``Halted``.

    Phase 6 (ADR-005): the atomic ``authorize_emergency_reduce_override`` (ADR-003 /
    INV-3 preconditions, stamping the real ``actor``) + open-buy stand-down + the
    reduce-only flatten live behind ``ExecutionCommandFacade.emergency_reduce_override``.
    409 when not Halted / an INV-3 quarantine blocks it / nothing to flatten;
    422 on a bad ticker.
    """
    try:
        return await command_facade.emergency_reduce_override(
            symbol=symbol, actor=actor
        )
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.get("/protection", response_model=ProtectionStatusResponse)
async def protection_status(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> ProtectionStatusResponse:
    """The live Sell-Side Protection state (Phase 7), classified server-side so the
    cockpit renders it verbatim (D-020). Effective config plus, per open position:
    its hard floor, the observed last price, whether it is breaching, whether an
    autonomous exit is paused by the kill switch, whether a protective order is
    stalled (unfilled past the timeout), and any active sell intent. The full
    classification lives behind the query facade (P6d) —
    ``StoreBackedQueryFacade.protection_status``."""

    return await query_facade.protection_status()


@router.get("/sell-intents", response_model=list[SellIntent])
async def list_sell_intents(
    session_id: Optional[str] = Query(default=None),
    symbol: Optional[str] = Query(default=None),
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[SellIntent]:
    """Read-only view of the sell-intent lifecycle (Phase 7). Optional
    ``session_id`` / ``symbol`` filters mirror the store method."""

    try:
        return await query_facade.list_sell_intents(session_id=session_id, symbol=symbol)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.get("/orders", response_model=list[Order])
async def list_orders(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[Order]:
    return await query_facade.list_orders()


@router.get("/order-recoveries", response_model=list[SubmitRecoveryRecord])
async def list_order_recoveries(
    open_only: bool = Query(default=True),
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[SubmitRecoveryRecord]:
    """Read-only view of broker-submit recovery records (D-017 / F-002).

    Defaults to the *open* ones — everything still needing attention: records
    the recovery loop is actively working (``unresolved``) **and** records it has
    escalated because the broker order had fills (``needs_review`` — a real
    untracked position a human must reconcile). Both must stay visible to the
    operator; only cleanly-cancelled records (``resolved_canceled``) drop out.
    ``open_only=false`` returns the full history. This is the minimal Wave 0
    surface; a full operational-status classification endpoint is Wave 2 (D-020).
    Defined before ``/orders/{order_id}`` so the literal path isn't captured as
    an ``order_id``.
    """

    return await query_facade.list_submit_recoveries(open_only=open_only)


@router.get("/operator/orders", response_model=OperatorOrdersResponse)
async def operator_orders(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> OperatorOrdersResponse:
    """The operator's single source of order-lifecycle truth (D-020).

    Classifies every durable non-terminal order **server-side** — its
    ``operational_status`` (``app.policy.operational_status_for``), the hold
    ``reason`` behind a ``created`` order (from that order's latest
    ``order_submission_blocked`` audit event), a ``cancelable`` flag (the same
    rule the cancel route enforces), and a ``stale`` flag (from ``order_stale``
    events) — plus every open broker-submit recovery record, so the cockpit (and
    any future UI) renders lifecycle instead of re-deriving it. Read-only: the
    raw ``/orders`` read and the ``/orders/{id}/cancel`` action are unchanged.

    Terminal orders (filled/canceled/rejected) are excluded via the same
    ``NON_TERMINAL_ORDER_STATUSES`` the CAPI exposure calc uses, so "what still
    needs an operator's eyes" is defined in exactly one place. The full
    classification lives behind the query facade (P6d) —
    ``StoreBackedQueryFacade.operator_orders``.
    """

    return await query_facade.operator_orders()


@router.get("/orders/{order_id}", response_model=Order)
async def get_order(
    order_id: str,
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> Order:
    try:
        return await query_facade.get_order(order_id=order_id)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.post("/orders/{order_id}/cancel", response_model=Order)
async def cancel_order(
    order_id: str,
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> Order:
    """Manually cancel an open order (D-011: human-triggered, no auto-cancel).

    404 if the order is unknown; 409 if it is already terminal (filled, canceled,
    or rejected) or timeout-quarantined (ADR-002 — an ambiguous submit that MAY be
    live at the venue is resolved by targeted reconciliation, not a manual cancel).
    A cancel **request** does not immediately mark the order terminal: a submitted
    order moves to ``cancel_pending`` and stays in the monitoring loop's polling
    set until the broker confirms a terminal state — so a late fill arriving before
    the venue finalizes the cancel is still recorded (CHAOS-1). A never-submitted
    order (CREATED, no broker id) has nothing at the broker and is cancelled locally
    to ``canceled`` immediately. Re-cancelling an already ``cancel_pending`` order
    is an idempotent no-op. A broker-call failure leaves the order unchanged → 502.

    Phase 6 (ADR-005): the whole flow lives behind
    ``ExecutionCommandFacade.cancel``; this route no longer touches the store or
    broker.
    """
    try:
        return await command_facade.cancel(order_id=order_id, actor=actor)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.get("/events", response_model=list[Event])
async def list_events(
    limit: Optional[int] = Query(default=None, ge=1, le=1000),
    event_type: Optional[str] = Query(default=None),
    correlation_id: Optional[str] = Query(default=None),
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[Event]:
    """``correlation_id`` (D-020) returns the complete lifecycle of one
    candidate OR one sell intent (X-004) — creation, approval, order creation,
    claim, submission, blocked/recovery, fills, and transitions — in one
    query, for incident reconstruction."""

    return await query_facade.list_events(
        limit=limit, event_type=event_type, correlation_id=correlation_id
    )
