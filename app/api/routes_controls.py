"""Control flags: kill switch and pause/resume buys.

These endpoints **persist the flag** (and audit it). As of Phase 4 the flags are
also **enforced on the order path** (Rule 8): with the kill switch engaged, new
order intent is refused at the backend boundary (`create_order_for_candidate`,
surfaced as 409 by the approve route) and the monitoring loop holds all order
submissions; buys-paused does the same for BUY intent (beta orders are long-only
buys). Both refusals are recorded as audit events (`order_intent_blocked` /
`order_submission_blocked`), so a block is never UI-only state.

The broader Phase 6 CAPI risk limits (max shares, max notional, max total
exposure, allowlist, duplicate prevention) remain out of scope here — Phase 4
wires only the on/off safety controls, not the sizing/risk engine.
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
