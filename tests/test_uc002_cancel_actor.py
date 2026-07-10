"""UC-002 (REV-0002 F-002 class) — the operator ``actor`` must be threaded onto
the audit trail of a manual cancel. The cancel route resolves ``X-Actor`` and
passes it to ``StoreBackedCommandFacade.cancel``, but the actor was dropped at
``_cancel_transition`` -> ``transition_order`` -> ``plan_transition_order`` (whose
``order_transition`` payload carried only ``from``/``to``). Cancel is a human-gated
surface (cancel/replace); its audit event must record who did it.
"""

from __future__ import annotations

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.store_backed import StoreBackedCommandFacade
from app.models import OrderSide, OrderStatus
from app.store.base import COMMAND_ACTOR_SYSTEM

pytestmark = pytest.mark.anyio


async def _created_order(store, symbol="AAPL", qty=100):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    return await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )


async def _order_transition_events(store, order_id):
    return [
        e
        for e in await store.list_events()
        if e.event_type == "order_transition" and e.order_id == order_id
    ]


async def test_transition_order_threads_actor_into_audit_event(any_store):
    await any_store.initialize()
    order = await _created_order(any_store)
    await any_store.transition_order(
        order.id, OrderStatus.CANCELED, actor="operator-alice"
    )
    events = await _order_transition_events(any_store, order.id)
    assert events, "no order_transition audit event was written"
    assert events[-1].payload.get("actor") == "operator-alice", events[-1].payload


async def test_transition_order_actor_defaults_to_system(any_store):
    """A routine engine transition (no actor supplied) records ``system`` — the
    default must not become ``None`` or an empty string."""
    await any_store.initialize()
    order = await _created_order(any_store)
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    events = await _order_transition_events(any_store, order.id)
    assert events[-1].payload.get("actor") == COMMAND_ACTOR_SYSTEM, events[-1].payload


async def test_facade_cancel_threads_operator_actor(any_store):
    """End-to-end: the facade cancel of a never-submitted (CREATED) order records
    the operator actor on the resulting ``order_transition`` event."""
    await any_store.initialize()
    order = await _created_order(any_store)
    facade = StoreBackedCommandFacade(
        any_store, broker=MockBrokerAdapter(), settings=Settings()
    )
    result = await facade.cancel(order_id=order.id, actor="operator-bob")
    assert result.status is OrderStatus.CANCELED
    events = await _order_transition_events(any_store, order.id)
    assert events and events[-1].payload.get("actor") == "operator-bob", (
        events[-1].payload if events else "no order_transition event"
    )
