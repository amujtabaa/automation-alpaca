"""Facade package — the Spine v2 typed command/query boundary (ADR-005).

**Phase 0 skeleton only.** Nothing in this package is implemented, wired
into a route, or enforced yet — see ``docs/SPINE_PHASE0_INVENTORY.md`` for
the current (unmediated) route -> store/broker/monitoring dependency map
this package is meant to eventually sit in front of, and
``prompts/CLAUDE_CODE_PHASE_1_FACADE_SEAM.md`` for the phase that starts
wiring it. Importing this package has no side effects and changes no
behavior.
"""

from __future__ import annotations

from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import EngineNotReadyError, FacadeError
from app.facade.queries import ExecutionQueryFacade

__all__ = [
    "ExecutionCommandFacade",
    "ExecutionQueryFacade",
    "EngineNotReadyError",
    "FacadeError",
]
