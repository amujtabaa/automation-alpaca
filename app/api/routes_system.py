"""System endpoints: health and session/control-flag state."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app import __version__
from app.api.deps import get_store
from app.api.schemas import HealthResponse
from app.models import SessionRecord, utcnow
from app.store.base import SessionAlreadyClosedError, StateStore

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        service="alpaca-capi-backend", version=__version__, time=utcnow()
    )


@router.get("/session", response_model=SessionRecord)
async def session(store: StateStore = Depends(get_store)) -> SessionRecord:
    """Current mode / session type / control-flag state.

    Reflects *state*, not user identity — there is no auth in beta
    (single-user localhost). Mode is always ``paper``.
    """

    return await store.get_current_session()


@router.post("/session/close", response_model=SessionRecord)
async def close_session(store: StateStore = Depends(get_store)) -> SessionRecord:
    """Close the active session (manual trigger).

    Expires open candidates, snapshots positions into ``position_snapshots``,
    and marks the session closed (see ``docs/02_DATA_AND_PERSISTENCE.md``,
    "Session Close Mechanics"). Automatic, window-driven close is a later phase.
    """

    try:
        return await store.close_session()
    except SessionAlreadyClosedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
