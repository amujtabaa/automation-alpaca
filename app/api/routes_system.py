"""System endpoints: health and session/control-flag state.

Phase 6 (ADR-005): ``/session`` and ``/session/close`` reach the store only
through the typed facade — the ``session_type`` live overlay (``app.features``)
and the close orchestration move behind it, so this route drops both
``app.store`` and ``app.features``. ``/health`` is pure and touches nothing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_actor, get_command_facade, get_query_facade
from app.api.schemas import HealthResponse
from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
from app.facade.queries import ExecutionQueryFacade
from app.models import SessionRecord, utcnow

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        service="alpaca-capi-backend", version=__version__, time=utcnow()
    )


@router.get("/session", response_model=SessionRecord)
async def session(
    query_facade: ExecutionQueryFacade = Depends(get_query_facade),
) -> SessionRecord:
    """Current mode / session type / control-flag state.

    Reflects *state*, not user identity — there is no auth in beta
    (single-user localhost). Mode is always ``paper``. ``session_type`` is
    overlaid live by the facade from ``session_type_for(utcnow())`` (the same
    Feature Engine classification the Strategy Engine evaluates against), since a
    day's session spans all three windows as wall-clock time passes.
    """

    return await query_facade.get_current_session_view()


@router.post("/session/close", response_model=SessionRecord)
async def close_session(
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
    actor: str = Depends(get_actor),
) -> SessionRecord:
    """Close the active session (manual trigger).

    Expires open candidates, cancels still-``CREATED`` orders (D-013a),
    snapshots positions into ``position_snapshots``, and marks the session
    closed (see ``docs/02_DATA_AND_PERSISTENCE.md``, "Session Close
    Mechanics"). Re-closing an already-closed session is a 409. Automatic,
    window-driven close is a later phase.
    """

    try:
        return await command_facade.close_session(actor=actor)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc
