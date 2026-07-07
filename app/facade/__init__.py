"""Facade package — the Spine v2 typed command/query boundary (ADR-005).

Phase 0 added this as an inert skeleton (nothing implemented, wired, or
enforced). Phase 1 (``prompts/CLAUDE_CODE_PHASE_1_FACADE_SEAM.md``) added a
concrete, store-backed implementation (``app.facade.store_backed``) and an
HTTP-error mapping (``app.facade.http_mapping``), and wired exactly two
routes through it — ``GET /api/positions`` and
``POST /api/controls/{pause,resume}-buys`` — with no behavior change (see
``docs/SPINE_PHASE1_FACADE_REPORT.md`` for the behavior-equivalence
evidence). Every other route still calls
``app.store``/``app.broker``/``app.monitoring`` directly; every other
facade method raises :class:`NotYetImplementedError`. Import boundary
enforcement (nothing yet prevents a route from bypassing this package) is
Phase 5.
"""

from __future__ import annotations

from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import EngineNotReadyError, FacadeError, NotYetImplementedError
from app.facade.http_mapping import facade_error_to_http
from app.facade.queries import ExecutionQueryFacade
from app.facade.store_backed import StoreBackedCommandFacade, StoreBackedQueryFacade

__all__ = [
    "ExecutionCommandFacade",
    "ExecutionQueryFacade",
    "EngineNotReadyError",
    "FacadeError",
    "NotYetImplementedError",
    "StoreBackedCommandFacade",
    "StoreBackedQueryFacade",
    "facade_error_to_http",
]
