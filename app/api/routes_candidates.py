"""Candidate lifecycle endpoints — list, fetch, approve, and reject.

The approve endpoint triggers the order dispatch as a distinct step immediately
after the gate approves (the component that triggers order creation on approval
— Phase 3 prompt §3). The gate seam (ApprovalGate) is the dependency, not the
concrete HumanApprovalGate, so a different implementation is honoured with zero
route edits.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_approval_gate, get_store
from app.approval.gate import ApprovalGate
from app.models import Candidate
from app.store.base import (
    CandidateTransitionError,
    InvalidOrderError,
    StateStore,
    UnknownEntityError,
)

router = APIRouter(prefix="/api", tags=["candidates"])


def _raise_http(exc: Exception) -> None:
    """Map store/gate errors to appropriate HTTP exceptions."""

    if isinstance(exc, UnknownEntityError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if isinstance(exc, (CandidateTransitionError, InvalidOrderError)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    raise exc


@router.get("/candidates", response_model=list[Candidate])
async def list_candidates(
    store: StateStore = Depends(get_store),
) -> list[Candidate]:
    """List candidates scoped to the active session."""

    session = await store.get_current_session()
    return await store.list_candidates(session_id=session.id)


@router.get("/candidates/{candidate_id}", response_model=Candidate)
async def get_candidate(
    candidate_id: str,
    store: StateStore = Depends(get_store),
) -> Candidate:
    """Fetch a single candidate by id."""

    candidate = await store.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"candidate {candidate_id} not found",
        )
    return candidate


@router.post("/candidates/{candidate_id}/approve", response_model=Candidate)
async def approve_candidate(
    candidate_id: str,
    store: StateStore = Depends(get_store),
    gate: ApprovalGate = Depends(get_approval_gate),
) -> Candidate:
    """Approve a candidate and dispatch the order atomically.

    The approve endpoint triggers the order dispatch as a distinct step
    immediately after the gate approves (the component that triggers order
    creation on approval — Phase 3 prompt §3).

    Flow:
    1. ``gate.approve(candidate_id)`` — carries out the pending→approved
       gate decision (idempotent).
    2. ``store.create_order_for_candidate(candidate_id)`` — the distinct
       dispatch step: transitions approved→ordered and creates the paper order,
       atomically.
    3. Returns the final ORDERED candidate.
    """

    try:
        await gate.approve(candidate_id)
        await store.create_order_for_candidate(candidate_id)
        candidate = await store.get_candidate(candidate_id)
    except (UnknownEntityError, CandidateTransitionError, InvalidOrderError) as exc:
        _raise_http(exc)

    # candidate is non-None here: create_order_for_candidate would have raised
    # UnknownEntityError if the candidate did not exist.
    return candidate  # type: ignore[return-value]


@router.post("/candidates/{candidate_id}/reject", response_model=Candidate)
async def reject_candidate(
    candidate_id: str,
    gate: ApprovalGate = Depends(get_approval_gate),
) -> Candidate:
    """Reject a candidate (idempotent; terminal — no order is created)."""

    try:
        return await gate.reject(candidate_id)
    except (UnknownEntityError, CandidateTransitionError, InvalidOrderError) as exc:
        _raise_http(exc)
