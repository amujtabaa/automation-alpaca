"""System endpoints: health and session/control-flag state."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import __version__
from app.api.deps import get_store
from app.api.schemas import HealthResponse
from app.models import SessionRecord, utcnow
from app.store.base import StateStore

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
