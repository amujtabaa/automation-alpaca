"""DEV/MOCK scaffolding — candidate injection for manual flow testing.

Phase 5's real Strategy Engine (``app/strategy.py`` + ``app/strategy_loop.py``)
is now the primary candidate producer. This module remains as a way to
hand-inject an exact symbol/price/quantity for testing a state the strategy
wouldn't naturally produce — it is NOT strategy logic, and nothing here should
be called from a real trading-decision path.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_store
from app.api.schemas import MockCandidateCreate
from app.models import Candidate, SessionStatus
from app.store.base import StateStore

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post("/candidates", response_model=Candidate, status_code=status.HTTP_201_CREATED)
async def inject_mock_candidate(
    body: MockCandidateCreate,
    store: StateStore = Depends(get_store),
) -> Candidate:
    """Inject a mock candidate — DEV/MOCK scaffolding only.

    Creates a ``pending`` candidate in the active session for manual testing —
    NOT strategy logic. The real Strategy Engine (Phase 5) generates candidates
    independently of this route; this exists for hand-testing exact states.
    """

    # Don't inject into a closed session: after a manual close (D-009 keeps the
    # day's session closed until a new one), a fresh candidate would attach to a
    # closed session and sit outside its captured snapshot. The trading day is
    # over — refuse rather than create orphaned post-close state.
    session = await store.get_current_session()
    if session.status is SessionStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="session is closed; cannot inject candidates",
        )

    try:
        return await store.create_candidate(
            body.symbol,
            strategy=body.strategy,
            reason=body.reason,
            suggested_quantity=body.suggested_quantity,
            suggested_limit_price=body.suggested_limit_price,
        )
    except ValueError as exc:
        # `normalize_symbol` rejects a blank/whitespace-only symbol (min_length=1
        # passes pydantic but strips to empty). Surface it as a clean 422, not a
        # 500.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
