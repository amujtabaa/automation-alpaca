"""Re-export surface for the Spine v2 facade protocols.

The two protocols live in their own modules (``app.facade.commands``,
``app.facade.queries``) so each can grow independently; this module exists
as the single place to import both from, matching
``prompts/CLAUDE_CODE_PHASE_0_HANDOFF.md``'s expected file list
(``app/facade/protocols.py``, ``commands.py``, ``queries.py``, ``errors.py``).

As of Phase 6 (ARCH-002 doc refresh), the command surface is fully
implemented and nearly all query methods are, by ``app.facade.store_backed``;
only ``list_primaries``/``list_spawns``/``kill_state`` (the not-yet-existent
``primary``/``spawn``/``TradingState`` vocabulary) still raise
:class:`~app.facade.errors.NotYetImplementedError`. See each protocol
module's docstring for specifics.
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
