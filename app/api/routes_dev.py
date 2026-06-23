"""DEV/MOCK scaffolding — candidate injection for manual flow testing.

This module exists solely to make the candidate approval flow exercisable before
Phase 5's real Strategy Engine is built. It is NOT strategy logic; Phase 5
replaces it with real candidate generation. Nothing here should be called from
production paths.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_store
from app.api.schemas import MockCandidateCreate
from app.models import Candidate
from app.store.base import StateStore

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post("/candidates", response_model=Candidate, status_code=status.HTTP_201_CREATED)
async def inject_mock_candidate(
    body: MockCandidateCreate,
    store: StateStore = Depends(get_store),
) -> Candidate:
    """Inject a mock candidate — DEV/MOCK scaffolding only.

    Creates a ``pending`` candidate in the active session so the approve/reject
    flow can be exercised manually before Phase 5's Strategy Engine exists.
    NOT strategy logic; Phase 5 replaces this with real candidate generation.
    """

    return await store.create_candidate(
        body.symbol,
        strategy=body.strategy,
        reason=body.reason,
        suggested_quantity=body.suggested_quantity,
        suggested_limit_price=body.suggested_limit_price,
    )
