"""Re-export surface for the Spine v2 facade protocols — Phase 0 skeleton.

The two protocols live in their own modules (``app.facade.commands``,
``app.facade.queries``) so each can grow independently; this module exists
as the single place to import both from, matching
``prompts/CLAUDE_CODE_PHASE_0_HANDOFF.md``'s expected file list
(``app/facade/protocols.py``, ``commands.py``, ``queries.py``, ``errors.py``).

Phase 0 scope note: see ``app.facade.commands``' module docstring for the
unimplemented/unwired/unenforced caveats that apply to everything re-exported
here.
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
