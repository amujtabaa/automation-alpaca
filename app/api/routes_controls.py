"""Control flags: kill switch and pause/resume buys.

In this phase these endpoints **persist the flag** (and audit it). Enforcement
— actually blocking new order intent when the kill switch is engaged — has no
meaning yet because nothing submits orders; it arrives with the order path
(out of scope now, per the implementation prompt). The flag surviving a restart
is the property that matters here.
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
