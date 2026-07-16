"""ENG-002 follow-up (PR #4 review, P2) — the timeout-quarantine resolver must not
STARVE later quarantined orders under a limited query budget. Before this fix the
resolver iterated ``list_timeout_quarantined_orders()`` in the same deterministic
order every tick and broke when the shared budget was exhausted, so the earliest
orders (which may keep failing their query or sit escalated in ``needs_review``
while still ``TIMEOUT_QUARANTINE``) consumed all the tokens every tick and later
orders never received their read-only resolution query.

A loop-owned round-robin ``ReconcileFairnessCursor`` resumes each tick just after
the last order that consumed a token, so over successive ticks every quarantined
order is served. Escalated orders are NOT skipped (they still auto-recover if the
venue comes back) — they simply take their fair turn.
"""

from __future__ import annotations

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import OrderSide
from app.monitoring import _resolve_timeout_quarantine
from app.reconciliation import ReconcileFairnessCursor, ReconcileQueryBudget

pytestmark = pytest.mark.anyio


async def _quarantine_order(store, symbol, session_id):
    cand = await store.create_candidate(symbol, session_id=session_id)
    order = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, 10, session_id=session_id
    )
    claim = await store.claim_order_for_submission(order.id)
    await store.quarantine_timed_out_order(claim.order.id)
    return order.id


class _RecordingAdapter(MockBrokerAdapter):
    """Records each targeted query and always confirms absent (deferred, so the
    order stays quarantined across ticks) — a query happened, but nothing resolves."""

    def __init__(self):
        super().__init__()
        self.queried: list[str] = []

    async def get_order_by_client_order_id(self, client_order_id):
        self.queried.append(client_order_id)
        return None


async def test_fairness_cursor_prevents_starvation_across_ticks(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    ids = [
        await _quarantine_order(any_store, sym, session.id)
        for sym in ("AAA", "BBB", "CCC", "DDD")
    ]

    adapter = _RecordingAdapter()
    cursor = ReconcileFairnessCursor()
    # Budget of 2 per tick -> only 2 of the 4 can be queried each tick. A fresh
    # budget per tick models the token bucket refilling between cadences.
    for _ in range(2):
        await _resolve_timeout_quarantine(
            any_store,
            adapter,
            Settings(),
            budget=ReconcileQueryBudget(2),
            fairness=cursor,
        )

    assert set(adapter.queried) == set(ids), (
        "some quarantined orders were never queried across two budget-limited ticks "
        f"(starvation): queried={adapter.queried}, expected all of {ids}"
    )


async def test_no_fairness_cursor_reproduces_starvation(any_store):
    """Control: WITHOUT the cursor the same first two orders are re-queried every
    tick and the later two are starved — documents the behaviour the fix corrects."""
    await any_store.initialize()
    session = await any_store.get_current_session()
    ids = [
        await _quarantine_order(any_store, sym, session.id)
        for sym in ("AAA", "BBB", "CCC", "DDD")
    ]

    adapter = _RecordingAdapter()
    for _ in range(2):
        await _resolve_timeout_quarantine(
            any_store, adapter, Settings(), budget=ReconcileQueryBudget(2)
        )

    # The store returns a STABLE order (sorted by id), so without the cursor the
    # SAME two orders are served every tick — 4 queries total but only 2 DISTINCT.
    # Two of the four quarantined orders are starved.
    assert len(adapter.queried) == 4, adapter.queried
    assert len(set(adapter.queried)) == 2, (
        f"expected starvation (only 2 distinct served), got {set(adapter.queried)}"
    )
    assert set(adapter.queried) < set(ids), "starved orders should be a strict subset"


def test_fairness_cursor_rotation_unit():
    """The cursor rotates a deterministic list to resume just after the last served
    id, wrapping around; an unknown/absent cursor leaves the order unchanged."""
    from types import SimpleNamespace

    items = [SimpleNamespace(id=x) for x in ("a", "b", "c", "d")]

    def ids(rotated):
        return [o.id for o in rotated]

    cursor = ReconcileFairnessCursor()
    assert ids(cursor.rotate(items)) == ["a", "b", "c", "d"]  # cold start
    cursor.last_served_id = "b"
    assert ids(cursor.rotate(items)) == ["c", "d", "a", "b"]
    cursor.last_served_id = "d"  # last element -> wraps to the natural start
    assert ids(cursor.rotate(items)) == ["a", "b", "c", "d"]
    cursor.last_served_id = "zzz"  # no longer present -> unchanged
    assert ids(cursor.rotate(items)) == ["a", "b", "c", "d"]
