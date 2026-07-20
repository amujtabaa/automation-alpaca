"""Spine v2 Phase 4 wave 4e slice 2 — the ACTING runtime reconcile (external orders).

Supersedes the wave-4d shadow: `_run_reconciliation` (gated by `reconciliation_enabled`,
default True) computes the §7 mass-report plan each tick and now takes its first
ACTION — surfacing external/unmanaged venue orders as durable, deduped
`reconcile_external_order` audit records (§7 "never silently absorbed"). This action is
**non-mutating** (an audit record only; no order transition, no fill, no position
change) — the oversell-critical not-found resolution is slice 4e-3, synthetic fills +
position parity + the query throttle are 4e-4.

Inertness (E5): external orders come FROM the broker report, so an empty report (the
whole existing corpus's default mock) yields none — the acting reconcile is naturally
inert until a venue order with no local match actually exists.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import (
    BrokerError,
    BrokerFill,
    BrokerOrderReport,
    BrokerPositionReport,
)
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    CandidateStatus,
    EventType,
    OrderSide,
    OrderStatus,
    utcnow,
)
from app.monitoring import (
    _run_reconciliation,
    _submit_pending_orders,
    run_monitoring_tick,
)

pytestmark = pytest.mark.anyio

EXTERNAL = EventType.RECONCILE_EXTERNAL_ORDER.value


def _off() -> Settings:
    return Settings(reconciliation_enabled=False)


async def _submitted_buy(store, *, symbol="AAPL", qty=100, limit=2.0):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(candidate.id)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(store, adapter)
    return order, adapter


async def _external_events(store):
    return [e for e in await store.list_events() if e.event_type == EXTERNAL]


# --------------------------------------------------------------------------- #
# Inertness — empty broker reports surface nothing; disabled makes no calls.
# --------------------------------------------------------------------------- #
async def test_empty_broker_reports_surface_nothing(any_store):
    # The corpus default: an open local order, an unseeded mock (reports []). The
    # acting reconcile runs (default enabled) but finds no external order → no record.
    order, adapter = await _submitted_buy(any_store)
    await run_monitoring_tick(any_store, adapter, Settings())
    assert await _external_events(any_store) == []
    # It DID run (polled the mass reports) — inertness comes from an empty report,
    # not from skipping.
    assert adapter.open_order_report_queries == 1
    assert adapter.position_report_queries == 1


async def test_disabled_makes_no_report_calls(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                "venueX", None, "TSLA", OrderSide.SELL, OrderStatus.SUBMITTED, 0
            )
        ]
    )
    await run_monitoring_tick(any_store, adapter, _off())
    assert adapter.open_order_report_queries == 0
    assert adapter.position_report_queries == 0
    assert await _external_events(any_store) == []


# --------------------------------------------------------------------------- #
# External-order surfacing — durable, deduped, never absorbs/mutates.
# --------------------------------------------------------------------------- #
async def test_external_order_surfaced_without_absorbing(any_store):
    order, adapter = await _submitted_buy(any_store, symbol="AAPL")
    # Use the mock's accepted wire-level report rather than a legacy partial
    # row. Managed correlation now validates the complete durable venue scope.
    managed = next(
        report
        for report in await adapter.list_open_orders()
        if report.client_order_id == order.id
    )
    external = BrokerOrderReport(
        "venue-unmanaged",
        None,
        "TSLA",
        OrderSide.SELL,
        OrderStatus.SUBMITTED,
        0,
    )
    adapter.seed_open_orders([managed, external])

    orders_before = {o.id for o in await any_store.list_orders()}
    await run_monitoring_tick(any_store, adapter, Settings())

    events = await _external_events(any_store)
    assert len(events) == 1
    assert events[0].payload["broker_order_id"] == "venue-unmanaged"
    assert events[0].payload["symbol"] == "TSLA"
    assert events[0].payload["side"] == "sell"
    # The managed order is matched (not external); the venue row is NOT absorbed into
    # local order state.
    assert {o.id for o in await any_store.list_orders()} == orders_before


async def test_venue_order_matching_a_known_terminal_order_is_not_external(any_store):
    # Review hardening: a venue row that ties back to a local order we KNOW in any
    # state (here a now-terminal FILLED order the venue mirror hasn't caught up on) is
    # managed, not external — never surfaced.
    order, adapter = await _submitted_buy(any_store)
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("e-1", 100, 2.0, utcnow())],
    )
    await run_monitoring_tick(any_store, adapter, Settings())  # order → FILLED locally
    # The venue report STILL lists it (a broker id we own).
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                adapter.broker_id_for(order.id),
                order.id,
                "AAPL",
                OrderSide.BUY,
                OrderStatus.SUBMITTED,
                0,
            )
        ]
    )
    await run_monitoring_tick(any_store, adapter, Settings())
    assert await _external_events(any_store) == []  # not flagged external


async def test_conflicting_concrete_identity_is_surfaced_despite_known_client_id(
    any_store,
):
    """A familiar client id cannot hide a foreign concrete broker identity."""

    order, adapter = await _submitted_buy(any_store, symbol="AAPL")
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                "foreign-broker-id",
                order.id,
                "MSFT",
                OrderSide.SELL,
                OrderStatus.SUBMITTED,
                0,
            )
        ]
    )

    plan = await _run_reconciliation(
        any_store,
        adapter,
        Settings(reconcile_recent_threshold_ms=0),
    )

    assert plan is not None
    assert [x.broker_order_id for x in plan.external_orders] == ["foreign-broker-id"]
    events = await _external_events(any_store)
    assert [e.payload["broker_order_id"] for e in events] == ["foreign-broker-id"]


async def test_exact_broker_id_with_conflicting_scope_is_surfaced(any_store):
    order, adapter = await _submitted_buy(any_store, symbol="AAPL")
    broker_order_id = adapter.broker_id_for(order.id)
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                broker_order_id,
                "foreign-client",
                "MSFT",
                OrderSide.SELL,
                OrderStatus.SUBMITTED,
                0,
            )
        ]
    )

    plan = await _run_reconciliation(
        any_store,
        adapter,
        Settings(reconcile_recent_threshold_ms=0),
    )

    assert plan is not None
    assert plan.needs_targeted_query == [order.id]
    assert [x.broker_order_id for x in plan.external_orders] == [broker_order_id]
    assert [
        e.payload["broker_order_id"] for e in await _external_events(any_store)
    ] == [broker_order_id]


async def test_external_order_deduped_by_broker_id_across_ticks(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                "venue-A", None, "TSLA", OrderSide.SELL, OrderStatus.SUBMITTED, 0
            )
        ]
    )
    for _ in range(3):
        await run_monitoring_tick(any_store, adapter, Settings())
    assert len(await _external_events(any_store)) == 1  # one per broker id, ever

    # A NEW external order surfaces its own record; the first is not re-logged.
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                "venue-A", None, "TSLA", OrderSide.SELL, OrderStatus.SUBMITTED, 0
            ),
            BrokerOrderReport(
                "venue-B", None, "NVDA", OrderSide.SELL, OrderStatus.SUBMITTED, 0
            ),
        ]
    )
    await run_monitoring_tick(any_store, adapter, Settings())
    ids = sorted(
        e.payload["broker_order_id"] for e in await _external_events(any_store)
    )
    assert ids == ["venue-A", "venue-B"]


# --------------------------------------------------------------------------- #
# Never flips truth — the acting reconcile must not perturb the legacy poll.
# --------------------------------------------------------------------------- #
async def test_reconcile_does_not_change_legacy_fill_outcome(any_store):
    order, adapter = await _submitted_buy(any_store, qty=100, limit=2.0)
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    # A matching mass report (the managed order is terminal after the poll → venue
    # open = none) + a broker position that agrees.
    adapter.seed_positions([BrokerPositionReport("AAPL", 100, 2.0)])

    await run_monitoring_tick(any_store, adapter, Settings())

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 100
    assert len(await any_store.list_fills(order_id=order.id)) == 1
    assert await _external_events(any_store) == []


# --------------------------------------------------------------------------- #
# Failure-isolated — a raised mass report skips the reconcile, never the tick.
# --------------------------------------------------------------------------- #
async def test_report_failure_skips_reconcile_not_tick(any_store):
    order, adapter = await _submitted_buy(any_store, qty=100, limit=2.0)
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    adapter.fail_next_open_orders(BrokerError("mass report down"))
    await run_monitoring_tick(any_store, adapter, Settings())
    # Legacy per-order reconcile still landed the fill; no crash.
    assert (await any_store.get_order(order.id)).status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 100


async def test_position_report_failure_skips_reconcile(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                "venue-X", None, "TSLA", OrderSide.SELL, OrderStatus.SUBMITTED, 0
            )
        ]
    )
    adapter.fail_next_positions(BrokerError("positions down"))
    await run_monitoring_tick(any_store, adapter, Settings())
    # A failed position report skips the whole reconcile this cycle — the external
    # order is NOT surfaced (never read a partial/failed report as authoritative).
    assert await _external_events(any_store) == []


async def test_run_reconciliation_returns_plan_for_observability(any_store):
    order, adapter = await _submitted_buy(any_store)
    adapter.seed_open_orders(
        [
            BrokerOrderReport(
                "venue-Z", None, "TSLA", OrderSide.SELL, OrderStatus.SUBMITTED, 0
            )
        ]
    )
    plan = await _run_reconciliation(any_store, adapter, Settings())
    assert plan is not None
    assert [x.broker_order_id for x in plan.external_orders] == ["venue-Z"]
    # Disabled → returns None, no work.
    assert await _run_reconciliation(any_store, adapter, _off()) is None
