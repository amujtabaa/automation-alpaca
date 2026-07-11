"""ENG-002 — the timeout-quarantine targeted resolution queries consume the
loop's shared reconcile query budget, so a large quarantine burst cannot exceed
the venue REST rate budget the mass-report / targeted-reconcile calls already
share. Once the budget is exhausted the remaining quarantined orders defer to a
later tick.
"""

from __future__ import annotations

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import OrderSide
from app.monitoring import _resolve_timeout_quarantine
from app.reconciliation import ReconcileQueryBudget

pytestmark = pytest.mark.anyio


async def _quarantine_order(store, symbol, session_id):
    cand = await store.create_candidate(symbol, session_id=session_id)
    order = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, 10, session_id=session_id
    )
    claim = await store.claim_order_for_submission(order.id)
    await store.quarantine_timed_out_order(claim.order.id)


class _CountingAdapter(MockBrokerAdapter):
    def __init__(self):
        super().__init__()
        self.query_count = 0

    async def get_order_by_client_order_id(self, client_order_id):
        self.query_count += 1
        return None  # venue confirms absent → deferred (not resolved), still a query


async def test_resolve_timeout_quarantine_consumes_budget(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    for symbol in ("AAA", "BBB", "CCC"):
        await _quarantine_order(any_store, symbol, session.id)

    adapter = _CountingAdapter()
    budget = ReconcileQueryBudget(2)  # only 2 tokens → 2 queries this tick
    await _resolve_timeout_quarantine(
        any_store, adapter, Settings(), budget=budget
    )
    assert adapter.query_count == 2, (
        f"budget of 2 should cap this tick at 2 targeted queries, "
        f"got {adapter.query_count}"
    )


async def test_resolve_timeout_quarantine_unbounded_without_budget(any_store):
    """No budget supplied (direct-call/test path) → every quarantined order is
    queried, unchanged from before ENG-002."""
    await any_store.initialize()
    session = await any_store.get_current_session()
    for symbol in ("AAA", "BBB", "CCC"):
        await _quarantine_order(any_store, symbol, session.id)

    adapter = _CountingAdapter()
    await _resolve_timeout_quarantine(any_store, adapter, Settings())
    assert adapter.query_count == 3, adapter.query_count
