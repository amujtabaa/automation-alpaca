"""Candidate lifecycle endpoints — list, fetch, approve, and reject.

The approve endpoint triggers the order dispatch as a distinct step immediately
after the gate approves (the component that triggers order creation on approval
— Phase 3 prompt §3). The gate seam (ApprovalGate) is the dependency, not the
concrete HumanApprovalGate, so a different implementation is honoured with zero
route edits.

Phase 6 (ADR-005): the whole BUY-dispatch orchestration — the dispatchability /
Rule-8 / CAPI-risk pre-checks, ``gate.approve`` + ``create_order_for_candidate``,
and the atomic revert-on-failure — moves behind ``ExecutionCommandFacade``, so
this route no longer imports ``app.store``, ``app.policy``, or the approval gate.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_actor, get_command_facade, get_query_facade
from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
from app.facade.queries import ExecutionQueryFacade
from app.models import Candidate

router = APIRouter(prefix="/api", tags=["candidates"])


@router.get("/candidates", response_model=list[Candidate])
async def list_candidates(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> list[Candidate]:
    """List candidates scoped to the active session."""

    return await query_facade.list_candidates()


@router.get("/candidates/{candidate_id}", response_model=Candidate)
async def get_candidate(
    candidate_id: str,
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> Candidate:
    """Fetch a single candidate by id (404 if absent)."""

    try:
        return await query_facade.get_candidate(candidate_id=candidate_id)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.post("/candidates/{candidate_id}/approve", response_model=Candidate)
async def approve_candidate(
    candidate_id: str,
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> Candidate:
    """Approve a candidate and dispatch the order.

    The facade carries out the full flow (see
    ``StoreBackedCommandFacade.approve_candidate``): a dispatchability pre-check
    (422), the Rule-8 order-intent (409) and CAPI risk-limit (409) pre-checks,
    then ``gate.approve`` + the authoritative ``create_order_for_candidate``
    (D-016), reverting the approval on ANY post-approval dispatch failure so a
    candidate is never stranded ``APPROVED`` with no order (F-002 / D-013).
    """

    try:
        return await command_facade.approve_candidate(
            candidate_id=candidate_id, actor=actor
        )
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.post("/candidates/{candidate_id}/reject", response_model=Candidate)
async def reject_candidate(
    candidate_id: str,
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> Candidate:
    """Reject a candidate (idempotent; terminal — no order is created)."""

    try:
        return await command_facade.reject_candidate(
            candidate_id=candidate_id, actor=actor
        )
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc
