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

**Spine v2 Phase 1 facade migration (ADR-005):** `pause-buys`/`resume-buys`
call `ExecutionCommandFacade` instead of the store directly — one of the two
low-risk routes `docs/SPINE_PHASE0_MIGRATION_PLAN.md` names for Phase 1. The
`kill-switch` route deliberately stays calling the store directly: it is one
of the two live ADR-003 conflicts (`docs/SPINE_PHASE0_INVENTORY.md` §3.4) —
wrapping it now would freeze today's binary-flag semantics as the facade's
contract before Phase 3 makes a deliberate `TradingState` migration decision.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_command_facade, get_store
from app.api.schemas import KillSwitchRequest
from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
from app.facade.store_backed import UNAUTHENTICATED_ACTOR
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
async def pause_buys(
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
) -> SessionRecord:
    try:
        return await command_facade.pause_buys(actor=UNAUTHENTICATED_ACTOR)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc


@router.post("/resume-buys", response_model=SessionRecord)
async def resume_buys(
    command_facade: ExecutionCommandFacade = Depends(get_command_facade),
) -> SessionRecord:
    try:
        return await command_facade.resume_buys(actor=UNAUTHENTICATED_ACTOR)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc
