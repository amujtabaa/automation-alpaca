"""Control flags: kill switch and pause/resume buys.

These endpoints **persist the flag** (and audit it). Enforcement — actually
blocking new order intent when the kill switch is engaged or buys are paused — is
**not yet wired**: the implementation plan assigns kill-switch enforcement on
order intent to Phase 6 (CAPI), so the flags persist now and are honoured later.

Note (Phase 3): approving a candidate now creates a paper **order record**
(`create_order_for_candidate`) — the system's first order-intent path. It still
sends nothing to a broker (paper submission is Phase 4), but it does mean the
kill switch / pause-buys flags do not yet gate it. That gating lands with Phase
6 enforcement; until then the flag surviving a restart is the property that
matters here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.schemas import KillSwitchRequest
from app.api.deps import get_store
from app.models import SessionRecord
from app.store.base import StateStore

router = APIRouter(prefix="/api/controls", tags=["controls"])


@router.post("/kill-switch", response_model=SessionRecord)
async def kill_switch(
    body: KillSwitchRequest = KillSwitchRequest(),
    store: StateStore = Depends(get_store),
) -> SessionRecord:
    return await store.set_kill_switch(body.engaged)


@router.post("/pause-buys", response_model=SessionRecord)
async def pause_buys(store: StateStore = Depends(get_store)) -> SessionRecord:
    return await store.set_buys_paused(True)


@router.post("/resume-buys", response_model=SessionRecord)
async def resume_buys(store: StateStore = Depends(get_store)) -> SessionRecord:
    return await store.set_buys_paused(False)
