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
from app.models import Candidate, CandidateStatus
from app.store.base import (
    CandidateTransitionError,
    InvalidOrderError,
    OrderIntentBlockedError,
    StateStore,
    StoreError,
    UnknownEntityError,
)
from app.store.validation import order_intent_block_reason

router = APIRouter(prefix="/api", tags=["candidates"])

# Store/gate errors the candidate endpoints translate to HTTP. Anything else is
# a genuine bug and is left to surface as a 500.
_MAPPED_ERRORS = (
    UnknownEntityError,
    CandidateTransitionError,
    InvalidOrderError,
    OrderIntentBlockedError,
)


def _http_error(exc: StoreError) -> HTTPException:
    """Map a known store/gate error to its HTTP status.

    ``UnknownEntityError`` → 404; ``CandidateTransitionError`` /
    ``InvalidOrderError`` → 409. Any *other* store error is left to propagate as
    a 500 — it signals a genuine bug, not a client mistake. Returning (not
    raising) keeps the caller's control flow explicit (``raise _http_error(...)``),
    so the success path's return value never depends on this helper raising.
    """

    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, UnknownEntityError)
        else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=code, detail=str(exc))


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
    """Approve a candidate and dispatch the order.

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

    These two steps are distinct store operations (the handoff is kept separate
    from the gate by design — D-006). To stop a failed dispatch from stranding a
    candidate at ``approved`` (a state the candidate machine can only leave via
    ``ordered`` or a session-close expiry), the candidate is checked for
    dispatchability *before* it is approved: a candidate that cannot be sized
    into a valid LIMIT order — no positive ``suggested_quantity`` **or** no
    positive ``suggested_limit_price`` — is rejected up front (422) and stays
    ``pending`` (still rejectable) rather than being approved into a dead end.
    """

    candidate = await store.get_candidate(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"candidate {candidate_id} not found",
        )
    # Dispatchability pre-check (see docstring). Skip it for an already-ordered
    # candidate: re-approving it is an idempotent no-op that needs no sizing.
    if candidate.status is not CandidateStatus.ORDERED and not (
        candidate.suggested_quantity
        and candidate.suggested_quantity > 0
        and candidate.suggested_limit_price
        and candidate.suggested_limit_price > 0
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"candidate {candidate_id} cannot be ordered: a positive "
                f"suggested_quantity and suggested_limit_price are required"
            ),
        )

    # Safety controls pre-check (Rule 8): don't approve a candidate the backend
    # would then refuse to dispatch (kill switch engaged / buys paused) — that
    # would strand it at APPROVED. Mirrors the enforcement inside
    # create_order_for_candidate; checked here so a blocked candidate stays
    # PENDING (still rejectable). Skipped for an already-ORDERED candidate (a
    # re-approve is an idempotent no-op that creates no new intent).
    if candidate.status is not CandidateStatus.ORDERED:
        block = order_intent_block_reason(await store.get_current_session())
        if block is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"order intent blocked: {block}",
            )

    try:
        await gate.approve(candidate_id)
        await store.create_order_for_candidate(candidate_id)
    except OrderIntentBlockedError as exc:
        # Race (D-013): a safety control flipped between the pre-check above and
        # the store handoff. The store refused the order, so roll the approval
        # back to PENDING — never leave the candidate stranded APPROVED with no
        # order under a safety stop. The revert is a no-op if the candidate
        # actually became ORDERED, so this is safe even without the pre-check.
        await store.revert_candidate_approval(candidate_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except _MAPPED_ERRORS as exc:
        raise _http_error(exc) from exc

    # The candidate exists (fetched above) and is never deleted, so the refreshed
    # read is non-None.
    refreshed = await store.get_candidate(candidate_id)
    assert refreshed is not None
    return refreshed


@router.post("/candidates/{candidate_id}/reject", response_model=Candidate)
async def reject_candidate(
    candidate_id: str,
    gate: ApprovalGate = Depends(get_approval_gate),
) -> Candidate:
    """Reject a candidate (idempotent; terminal — no order is created)."""

    try:
        return await gate.reject(candidate_id)
    except _MAPPED_ERRORS as exc:
        raise _http_error(exc) from exc
