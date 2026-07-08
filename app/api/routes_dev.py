"""DEV/MOCK scaffolding — candidate injection for manual flow testing.

Phase 5's real Strategy Engine (``app/strategy.py`` + ``app/strategy_loop.py``)
is now the primary candidate producer. This module remains as a way to
hand-inject an exact symbol/price/quantity for testing a state the strategy
wouldn't naturally produce — it is NOT strategy logic, and nothing here should
be called from a real trading-decision path.

Phase 6 (ADR-005): reaches the store only through the typed command facade.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import get_actor, get_command_facade
from app.api.schemas import MockCandidateCreate
from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
from app.models import Candidate

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post("/candidates", response_model=Candidate, status_code=status.HTTP_201_CREATED)
async def inject_mock_candidate(
    body: MockCandidateCreate,
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> Candidate:
    """Inject a mock candidate — DEV/MOCK scaffolding only.

    Creates a ``pending`` candidate in the active session for manual testing —
    NOT strategy logic. The real Strategy Engine (Phase 5) generates candidates
    independently of this route; this exists for hand-testing exact states. A
    closed session is refused (409); a blank/out-of-domain symbol → 422 — both
    via the facade's domain errors.
    """

    try:
        return await command_facade.inject_mock_candidate(
            symbol=body.symbol,
            strategy=body.strategy,
            reason=body.reason,
            suggested_quantity=body.suggested_quantity,
            suggested_limit_price=body.suggested_limit_price,
            actor=actor,
        )
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc
