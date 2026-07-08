"""Spine v2 Phase 4 wave 4e slice 4 — reconciliation-inferred synthetic fills +
the §7/§9 query throttle.

* **Synthetic fills (INV-5 / R8):** when the venue's mass report carries a PRICED
  execution the local log is missing, the acting reconcile appends it as a
  SYNTHETIC/RECONCILIATION fill — moving position exactly once, and dedup-safe
  against the eventual real observation of the same execution (same source_fill_id).
  Never a $0 synthetic (the engine routes an unpriced delta to a targeted query).
* **Query throttle (E6/E7):** a persistent per-minute `ReconcileQueryBudget` gates
  the reconcile REST calls. An exhausted budget SKIPS the cycle (never a partial read;
  never read as flat); a budget that covers the mass reports but not the targeted
  queries defers the not-found resolution rather than skipping the query silently.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerFill, BrokerOrderReport
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    CandidateStatus,
    EventAuthority,
    EventSource,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    utcnow,
)
from app.monitoring import (
    _reconcile_open_orders,
    _run_reconciliation,
    _submit_pending_orders,
)
from app.reconciliation import ReconcileQueryBudget

pytestmark = pytest.mark.anyio

_LEGACY = Settings(reconciliation_enabled=False)
_NO_RECENT = Settings(reconcile_recent_threshold_ms=0)


async def _submitted_buy(store, *, symbol="AAPL", qty=100, limit=2.0):
    await store.initialize()
    cand = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(store, adapter)
    return order, adapter


def _priced_report(adapter, order, *, filled, exec_id="v-exec-1", price=2.0):
    return BrokerOrderReport(
        broker_order_id=adapter.broker_id_for(order.id),
        client_order_id=order.id,
        symbol=order.symbol,
        side=OrderSide.BUY,
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=filled,
        fills=[BrokerFill(exec_id, filled, price, utcnow())],
    )


def _fill_events(events):
    return [e for e in events if e.event_type is ExecutionEventType.FILL]


# --------------------------------------------------------------------------- #
# Synthetic fills
# --------------------------------------------------------------------------- #
async def test_inferred_priced_fill_moves_position_marked_synthetic(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders([_priced_report(adapter, order, filled=40)])

    await _run_reconciliation(any_store, adapter, _NO_RECENT)

    assert (await any_store.get_position("AAPL")).quantity == 40
    fills = _fill_events(await any_store.get_execution_events())
    assert len(fills) == 1
    assert fills[0].authority is EventAuthority.SYNTHETIC
    assert fills[0].source is EventSource.RECONCILIATION


async def test_synthetic_then_real_same_execution_dedups_no_double_count(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders([_priced_report(adapter, order, filled=40, exec_id="ex-9")])
    await _run_reconciliation(any_store, adapter, _NO_RECENT)   # synthetic 40
    assert (await any_store.get_position("AAPL")).quantity == 40

    # The per-order poll later observes the SAME execution (same source_fill_id).
    adapter.make_fill(
        order.id, status=OrderStatus.PARTIALLY_FILLED, filled_quantity=40,
        fills=[BrokerFill("ex-9", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(any_store, adapter, _LEGACY)
    # Deduped — position moved ONCE, not twice (INV-5 / R8).
    assert (await any_store.get_position("AAPL")).quantity == 40
    assert len(_fill_events(await any_store.get_execution_events())) == 1


async def test_priced_fill_without_source_id_is_not_inferred(any_store):
    # Review hardening: a PRICED execution with a null/empty source_fill_id would
    # defeat the INV-5 dedup key and double-count. It must NOT be inferred — routed to
    # the targeted poll (which dedups by its own key) instead. Here the venue still
    # has the order, so nothing resolves and position is unmoved.
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders([
        BrokerOrderReport(
            adapter.broker_id_for(order.id), order.id, "AAPL", OrderSide.BUY,
            OrderStatus.PARTIALLY_FILLED, 40,
            fills=[BrokerFill("", 40, 2.0, utcnow())],   # priced, but no source id
        )
    ])
    await _run_reconciliation(any_store, adapter, _NO_RECENT)
    assert (await any_store.get_position("AAPL")).quantity == 0
    assert _fill_events(await any_store.get_execution_events()) == []


async def test_no_synthetic_fill_from_an_empty_derived_report(any_store):
    # The corpus default: an unseeded mock derives a report with filled_quantity=0
    # and no fills → no inferred fill (the reconcile is inert for synthetic fills).
    order, adapter = await _submitted_buy(any_store)
    await _run_reconciliation(any_store, adapter, _NO_RECENT)
    assert (await any_store.get_position("AAPL")).quantity == 0
    assert _fill_events(await any_store.get_execution_events()) == []


# --------------------------------------------------------------------------- #
# Query throttle
# --------------------------------------------------------------------------- #
async def test_exhausted_budget_skips_the_whole_cycle(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders(
        [BrokerOrderReport("venueX", None, "TSLA", OrderSide.SELL,
                           OrderStatus.SUBMITTED, 0)]
    )
    budget = ReconcileQueryBudget(1)   # can't cover the 2 mass-report calls
    plan = await _run_reconciliation(any_store, adapter, Settings(), budget=budget)

    assert plan is None                                  # cycle skipped
    assert adapter.open_order_report_queries == 0        # never even polled
    assert adapter.position_report_queries == 0
    external = [
        e for e in await any_store.list_events()
        if e.event_type == "reconcile_external_order"
    ]
    assert external == []


async def test_budget_covers_a_normal_cycle(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders(
        [BrokerOrderReport("venueZ", None, "TSLA", OrderSide.SELL,
                           OrderStatus.SUBMITTED, 0)]
    )
    budget = ReconcileQueryBudget(200)
    plan = await _run_reconciliation(any_store, adapter, Settings(), budget=budget)

    assert plan is not None
    assert adapter.open_order_report_queries == 1
    external = [
        e for e in await any_store.list_events()
        if e.event_type == "reconcile_external_order"
    ]
    assert len(external) == 1


async def test_targeted_query_throttle_defers_when_budget_only_covers_mass(any_store):
    # Budget = exactly the 2 mass-report tokens → no budget left for the targeted
    # query, so an absent order is NOT queried and NOT resolved this cycle (deferred).
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate(
        "AAPL", suggested_quantity=100, suggested_limit_price=2.0, session_id=session.id
    )
    await any_store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await any_store.create_order_for_candidate(cand.id)
    throwaway = MockBrokerAdapter()
    await _submit_pending_orders(any_store, throwaway)   # SUBMITTED, broker id it owns

    adapter = MockBrokerAdapter()                         # fresh: doesn't know the order
    budget = ReconcileQueryBudget(2)
    await _run_reconciliation(
        any_store, adapter,
        Settings(reconcile_recent_threshold_ms=0, reconcile_open_check_missing_retries=1),
        budget=budget,
    )
    # Mass reports consumed both tokens → the targeted query was skipped, so the order
    # was neither queried nor resolved (never read as absent under budget pressure).
    assert adapter.client_queries == []
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED
