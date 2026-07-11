"""W2-SESS (CAMPAIGN-0001 Wave-2, REV-0013 P2) — the operator actor is threaded
onto the ``session_closed`` audit event, so the log attributes WHO closed the
session (previously the facade resolved the actor then dropped it before the store
write — the same class as the Wave-1 UC-002 cancel-actor drop). Default is
``"system"`` for an engine/automatic close.

Both stores (parity), plus the facade wiring.
"""

from __future__ import annotations

import pytest

from app.facade.store_backed import StoreBackedCommandFacade

pytestmark = pytest.mark.anyio


def _closed_event(events):
    closed = [e for e in events if e.event_type == "session_closed"]
    assert len(closed) == 1, f"expected exactly one session_closed event, got {closed}"
    return closed[0]


async def test_close_session_stamps_operator_actor(any_store):
    await any_store.initialize()
    await any_store.close_session(actor="operator-dave")

    ev = _closed_event(await any_store.list_events())
    assert ev.payload.get("actor") == "operator-dave", (
        f"session_closed did not record the operator actor: {ev.payload}"
    )


async def test_close_session_defaults_actor_to_system(any_store):
    """A routine/automatic close carries the default 'system' actor (no false
    operator attribution)."""
    await any_store.initialize()
    await any_store.close_session()

    ev = _closed_event(await any_store.list_events())
    assert ev.payload.get("actor") == "system", ev.payload


async def test_facade_threads_actor_to_close_session(any_store):
    """The command facade forwards the resolved operator actor to the store (it
    was dropped here before W2-SESS)."""
    await any_store.initialize()
    facade = StoreBackedCommandFacade(any_store)

    await facade.close_session(actor="operator-erin")

    ev = _closed_event(await any_store.list_events())
    assert ev.payload.get("actor") == "operator-erin", ev.payload
