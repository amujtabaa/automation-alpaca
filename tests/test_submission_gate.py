"""Submission gate: a held order is gated on its OWN session (Item 1 / D-013a).

Closes the date-rollover kill-switch bypass and the post-close submission leak
the independent review reproduced: ``_submit_pending_orders`` previously gated on
``get_current_session()``, which auto-mints a fresh, permissive session on UTC
date rollover, letting a kill-switched/closed-session order reach the broker.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerFill
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import CandidateStatus, OrderStatus, SessionStatus, utcnow
from app.monitoring import _reconcile_open_orders, _submit_pending_orders
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _created_order(store, *, symbol="AAPL", qty=10, limit=1.0):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(candidate.id)


def _force_rollover(store):
    """Simulate a UTC date rollover: make every existing session belong to the
    past so ``get_current_session`` mints a fresh one for 'today'. Store-aware
    (test-only); both stores resolve the current session by today's date."""

    past = "2000-01-01"
    if isinstance(store, InMemoryStateStore):
        for s in store._sessions:
            s.session_date = past
    else:  # SqliteStateStore — autocommit (isolation_level=None)
        store._connect().execute("UPDATE sessions SET session_date = ?", (past,))


# --------------------------------------------------------------------------- #
# The bypass: a kill-switched order must not submit after a date rollover
# --------------------------------------------------------------------------- #
async def test_date_rollover_does_not_release_kill_switched_order(any_store):
    order = await _created_order(any_store)
    await any_store.set_kill_switch(True)  # kills the order's own session
    adapter = MockBrokerAdapter()

    # Same-day tick: held (baseline).
    await _submit_pending_orders(any_store, adapter)
    assert adapter.submitted == []
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED

    # UTC rollover -> get_current_session mints a fresh, default-OFF session.
    _force_rollover(any_store)
    current = await any_store.get_current_session()
    assert current.kill_switch is False
    assert current.id != order.session_id

    # The held order STILL must not submit (gated on its own kill-switched session).
    await _submit_pending_orders(any_store, adapter)
    assert adapter.submitted == []
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED
    assert any(
        e.event_type == "order_submission_blocked"
        and e.order_id == order.id
        and e.payload.get("reason") == "kill_switch"
        for e in await any_store.list_events()
    )


# --------------------------------------------------------------------------- #
# Post-close: a CREATED order is cancelled at close, never submitted afterward
# --------------------------------------------------------------------------- #
async def test_created_order_canceled_at_close_not_submitted(any_store):
    order = await _created_order(any_store)
    await any_store.close_session()  # no kill switch engaged

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.CANCELED
    assert any(
        e.event_type == "order_transition"
        and e.order_id == order.id
        and e.payload.get("reason") == "session_close"
        for e in await any_store.list_events()
    )

    # And the loop never submits it (it is terminal, not CREATED).
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)
    assert adapter.submitted == []
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCELED


async def test_closed_session_yields_session_closed_hold_reason(any_store):
    # Defense-in-depth backstop to the close-cancel above: the gate predicate
    # itself holds any order whose own session is closed (independent of whether
    # close-cancel already terminated it).
    from app.store.validation import session_submission_block_reason

    order = await _created_order(any_store)
    await any_store.close_session()
    closed = await any_store.get_session_by_id(order.session_id)
    assert closed.status is SessionStatus.CLOSED
    assert session_submission_block_reason(closed) == "session_closed"


# --------------------------------------------------------------------------- #
# The current/live session is an additional, process-wide emergency stop
# --------------------------------------------------------------------------- #
async def test_current_session_kill_is_global_emergency_stop(any_store):
    order = await _created_order(any_store)  # session S, unblocked
    _force_rollover(any_store)  # S now past; a fresh current session opens
    await any_store.set_kill_switch(True)  # kills the *current* session, not S
    adapter = MockBrokerAdapter()

    await _submit_pending_orders(any_store, adapter)

    # Order's own session S is fine, but the live session is killed -> held.
    assert adapter.submitted == []
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED
    assert any(
        e.event_type == "order_submission_blocked"
        and e.order_id == order.id
        and e.payload.get("reason") == "current_kill_switch"
        for e in await any_store.list_events()
    )


# --------------------------------------------------------------------------- #
# Normal flow still submits; D-011 (post-close reconciliation) not regressed
# --------------------------------------------------------------------------- #
async def test_normal_open_unblocked_session_still_submits(any_store):
    order = await _created_order(any_store)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)
    assert [o.id for o in adapter.submitted] == [order.id]
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED


async def test_submitted_order_still_reconciles_after_close(any_store):
    order = await _created_order(any_store, qty=100, limit=2.0)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED

    # Close must NOT cancel an already-submitted order (only CREATED ones).
    await any_store.close_session()
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED

    # And reconciliation still fills it to terminal after close (D-011).
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("f1", 100, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, Settings())
    assert (await any_store.get_order(order.id)).status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 100
