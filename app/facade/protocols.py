"""Re-export surface for the Spine v2 facade protocols.

The two protocols live in their own modules (``app.facade.commands``,
``app.facade.queries``) so each can grow independently; this module exists
as the single place to import both from, matching
``prompts/CLAUDE_CODE_PHASE_0_HANDOFF.md``'s expected file list
(``app/facade/protocols.py``, ``commands.py``, ``queries.py``, ``errors.py``).

As of Phase 1, two methods across both protocols have a real concrete
implementation (``app.facade.store_backed``), wired into two routes
(``GET /api/positions``, ``POST /api/controls/{pause,resume}-buys``) — see
``docs/SPINE_PHASE1_FACADE_REPORT.md``. Every other method still raises
:class:`~app.facade.errors.NotYetImplementedError`; see each protocol
module's docstring for which and why.
"""

from __future__ import annotations

from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import EngineNotReadyError, FacadeError, NotYetImplementedError
from app.facade.queries import ExecutionQueryFacade

__all__ = [
    "ExecutionCommandFacade",
    "ExecutionQueryFacade",
    "EngineNotReadyError",
    "FacadeError",
    "NotYetImplementedError",
]
