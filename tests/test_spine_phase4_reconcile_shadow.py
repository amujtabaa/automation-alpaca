"""Spine v2 Phase 4 wave 4d — SHADOW the runtime reconcile (§7).

The monitoring tick now computes the §7 mass-report reconciliation plan
(``app/reconciliation.plan_reconciliation``) alongside the legacy per-order poll
and emits an observability ``reconcile_shadow_divergence`` audit event when the
mass report diverges from managed state — **without flipping any truth**.

Load-bearing properties this module pins (so wave 4e's truth flip is provably
behavior-preserving):

* **Inert by default** — off unless ``reconciliation_shadow_enabled``; when off,
  the tick makes zero mass-report calls and emits no shadow event (the whole
  existing corpus is unperturbed).
* **Never flips truth** — with the shadow ON, the legacy reconcile outcome
  (fills → position, terminal → status) is byte-identical to shadow-OFF; the
  shadow appends no fills, transitions no orders, mutates no position.
* **Surfaces what the per-order poll can't** — an external/unmanaged venue order
  and a broker-vs-local position drift both raise a shadow event; position truth
  is never overwritten (Rule 7 / §7).
* **Deduped** — a persistent, unchanged divergence logs once, not once per tick.
* **Failure-isolated** — a failed mass report (§7: never read as flat) skips the
  shadow for that cycle and never disturbs the legacy reconcile.
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
    _emit_shadow_divergence,
    _shadow_fingerprint,
    _submit_pending_orders,
    run_monitoring_tick,
)
from app.reconciliation import (
    ExternalOrder,
    InferredFill,
    OrderResolution,
    PositionMismatch,
    ReconciliationPlan,
)

pytestmark = pytest.mark.anyio

SHADOW = EventType.RECONCILE_SHADOW_DIVERGENCE.value


def _shadow_on() -> Settings:
    return Settings(reconciliation_shadow_enabled=True)


async def _submitted_buy(store, *, symbol="AAPL", qty=100, limit=2.0):
    """A managed BUY order taken through the approval handoff + submit (SUBMITTED,
    holds a broker id, no fills yet)."""

    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(candidate.id)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(store, adapter)
    return order, adapter


async def _shadow_events(store):
    return [e for e in await store.list_events() if e.event_type == SHADOW]


# --------------------------------------------------------------------------- #
# Off by default — the shadow is opt-in scaffolding until wave 4e.
# --------------------------------------------------------------------------- #
async def test_shadow_off_makes_no_report_calls_and_no_event(any_store):
    order, adapter = await _submitted_buy(any_store)
    # Even with a divergent venue picture seeded, a default (shadow-off) tick
    # must neither poll the mass reports nor emit a shadow event.
    adapter.seed_open_orders(
        [BrokerOrderReport("venueX", None, "TSLA", OrderSide.SELL,
                           OrderStatus.SUBMITTED, 0)]
    )
    adapter.seed_positions([BrokerPositionReport("AAPL", 999, 1.0)])

    await run_monitoring_tick(any_store, adapter, Settings())

    assert adapter.open_order_report_queries == 0
    assert adapter.position_report_queries == 0
    assert await _shadow_events(any_store) == []


# --------------------------------------------------------------------------- #
# Never flips truth — the shadow must not perturb the legacy reconcile outcome.
# --------------------------------------------------------------------------- #
async def test_shadow_on_does_not_change_legacy_reconcile_outcome(any_store):
    order, adapter = await _submitted_buy(any_store, qty=100, limit=2.0)
    # The venue reports the managed order filled — the LEGACY per-order poll
    # applies it. The shadow runs too, but must add nothing.
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    # A matching mass report (so the shadow sees agreement, not a phantom divergence).
    adapter.seed_open_orders([])  # order is terminal after the poll → venue open = none
    adapter.seed_positions([BrokerPositionReport("AAPL", 100, 2.0)])

    await run_monitoring_tick(any_store, adapter, _shadow_on())

    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.FILLED           # legacy poll did its job
    assert fresh.filled_quantity == 100
    pos = await any_store.get_position("AAPL")
    assert pos.quantity == 100                          # exactly one fill's worth
    assert pos.average_price == 2.0
    # Exactly one fill row — the shadow appended nothing.
    assert len(await any_store.list_fills(order_id=order.id)) == 1
    # The shadow DID run (it polled the reports) but found agreement → no event.
    assert adapter.open_order_report_queries == 1
    assert adapter.position_report_queries == 1
    assert await _shadow_events(any_store) == []


# --------------------------------------------------------------------------- #
# Surfaces divergence the per-order poll structurally cannot capture.
# --------------------------------------------------------------------------- #
async def test_external_order_surfaced_without_flipping_truth(any_store):
    order, adapter = await _submitted_buy(any_store, symbol="AAPL")
    managed = BrokerOrderReport(
        adapter.broker_id_for(order.id), order.id, "AAPL",
        OrderSide.BUY, OrderStatus.SUBMITTED, 0,
    )
    external = BrokerOrderReport(
        "venue-unmanaged", None, "TSLA", OrderSide.SELL,
        OrderStatus.SUBMITTED, 0,
    )
    adapter.seed_open_orders([managed, external])

    orders_before = {o.id for o in await any_store.list_orders()}
    await run_monitoring_tick(any_store, adapter, _shadow_on())

    events = await _shadow_events(any_store)
    assert len(events) == 1
    ext = events[0].payload["external_orders"]
    assert [x["broker_order_id"] for x in ext] == ["venue-unmanaged"]
    # The managed order is NOT flagged external (matched by broker + client id).
    # Truth untouched: no new local order was absorbed from the venue row.
    assert {o.id for o in await any_store.list_orders()} == orders_before


async def test_position_mismatch_surfaced_never_overwrites(any_store):
    # Establish a local long of 100 via a real fill (the legacy poll).
    order, adapter = await _submitted_buy(any_store, symbol="AAPL", qty=100, limit=2.0)
    adapter.make_fill(
        order.id, status=OrderStatus.FILLED, filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    await run_monitoring_tick(any_store, adapter, Settings())  # shadow off: land the fill
    assert (await any_store.get_position("AAPL")).quantity == 100

    # Now the venue reports a DIFFERENT quantity — a drift the per-order poll can't see.
    adapter.seed_positions([BrokerPositionReport("AAPL", 150, 2.0)])
    await run_monitoring_tick(any_store, adapter, _shadow_on())

    events = await _shadow_events(any_store)
    assert len(events) == 1
    mism = events[0].payload["position_mismatches"]
    assert mism[0]["symbol"] == "AAPL"
    assert mism[0]["kind"] == "quantity"
    assert mism[0]["local_quantity"] == 100
    assert mism[0]["broker_quantity"] == 150
    # Position truth is the deduped fill log — NEVER overwritten from the report.
    assert (await any_store.get_position("AAPL")).quantity == 100


# --------------------------------------------------------------------------- #
# Dedup — a persistent, unchanged divergence logs once; a changed one re-logs.
# --------------------------------------------------------------------------- #
async def test_persistent_divergence_logs_once_then_relogs_on_change(any_store):
    order, adapter = await _submitted_buy(any_store, symbol="AAPL")
    adapter.seed_open_orders(
        [BrokerOrderReport("venue-A", None, "TSLA", OrderSide.SELL,
                           OrderStatus.SUBMITTED, 0)]
    )
    settings = _shadow_on()

    await run_monitoring_tick(any_store, adapter, settings)
    await run_monitoring_tick(any_store, adapter, settings)
    await run_monitoring_tick(any_store, adapter, settings)
    # Same external order every tick → exactly one event.
    assert len(await _shadow_events(any_store)) == 1

    # The divergence picture CHANGES (a second external order appears) → re-log.
    adapter.seed_open_orders(
        [
            BrokerOrderReport("venue-A", None, "TSLA", OrderSide.SELL,
                              OrderStatus.SUBMITTED, 0),
            BrokerOrderReport("venue-B", None, "NVDA", OrderSide.SELL,
                              OrderStatus.SUBMITTED, 0),
        ]
    )
    await run_monitoring_tick(any_store, adapter, settings)
    assert len(await _shadow_events(any_store)) == 2


# --------------------------------------------------------------------------- #
# Failure-isolated — a failed mass report skips the shadow, never the tick.
# --------------------------------------------------------------------------- #
async def test_open_orders_report_failure_skips_shadow_not_tick(any_store):
    order, adapter = await _submitted_buy(any_store, qty=100, limit=2.0)
    adapter.make_fill(
        order.id, status=OrderStatus.FILLED, filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    adapter.fail_next_open_orders(BrokerError("mass report down"))

    # Must not raise; the legacy per-order reconcile still lands the fill.
    await run_monitoring_tick(any_store, adapter, _shadow_on())

    assert (await any_store.get_order(order.id)).status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 100
    assert await _shadow_events(any_store) == []  # shadow skipped this cycle


async def test_position_report_failure_skips_shadow_not_tick(any_store):
    order, adapter = await _submitted_buy(any_store, qty=100, limit=2.0)
    adapter.make_fill(
        order.id, status=OrderStatus.FILLED, filled_quantity=100,
        fills=[BrokerFill("exec-1", 100, 2.0, utcnow())],
    )
    adapter.fail_next_positions(BrokerError("positions down"))

    await run_monitoring_tick(any_store, adapter, _shadow_on())

    assert (await any_store.get_order(order.id)).status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 100
    assert await _shadow_events(any_store) == []


# --------------------------------------------------------------------------- #
# _shadow_fingerprint — pure, deterministic identity over the plan's divergences.
# --------------------------------------------------------------------------- #
def test_fingerprint_none_for_empty_and_skipped_recent_only():
    assert _shadow_fingerprint(ReconciliationPlan()) is None
    # skipped_recent is a settling order, NOT a divergence → still None.
    assert (
        _shadow_fingerprint(ReconciliationPlan(skipped_recent=["o1", "o2"])) is None
    )


def test_fingerprint_covers_every_divergence_category_and_is_stable():
    plan = ReconciliationPlan(
        resolutions=[OrderResolution("o1", OrderStatus.CANCELED, "broker_reports_canceled")],
        inferred_fills=[InferredFill("o2", "AAPL", OrderSide.BUY, 5, 1.0, "exec-9")],
        needs_targeted_query=["o3"],
        external_orders=[ExternalOrder("bX", None, "TSLA", OrderSide.SELL,
                                       OrderStatus.SUBMITTED, 0)],
        position_mismatches=[PositionMismatch("MSFT", "quantity", 1, 2, None, None)],
        skipped_recent=["o9"],  # excluded from the fingerprint
    )
    fp = _shadow_fingerprint(plan)
    assert fp is not None
    # Deterministic (sorted) and includes each category once; excludes skipped_recent.
    assert fp == "|".join(
        sorted(
            [
                "res:o1:canceled",
                "inf:o2:exec-9",
                "ntq:o3",
                "ext:bX",
                "pos:MSFT:quantity",
            ]
        )
    )
    assert "o9" not in fp
    # Pure: same input → same output.
    assert _shadow_fingerprint(plan) == fp


async def test_emit_is_noop_for_empty_plan(any_store):
    await any_store.initialize()
    await _emit_shadow_divergence(any_store, ReconciliationPlan())
    assert await _shadow_events(any_store) == []


async def test_emit_serializes_every_category_into_the_payload(any_store):
    # A fully-populated plan (all five categories) — pins the shadow event's
    # payload schema so an operator/DTO can read each divergence kind. Emitting
    # directly (no clock/recency dance) also covers the resolution + inferred-fill
    # payload builders the wiring tests leave empty.
    await any_store.initialize()
    plan = ReconciliationPlan(
        resolutions=[OrderResolution("o1", OrderStatus.CANCELED, "broker_reports_canceled")],
        inferred_fills=[InferredFill("o2", "AAPL", OrderSide.BUY, 5, 1.25, "exec-9")],
        needs_targeted_query=["o3"],
        external_orders=[ExternalOrder("bX", "cX", "TSLA", OrderSide.SELL,
                                       OrderStatus.PARTIALLY_FILLED, 7)],
        position_mismatches=[PositionMismatch("MSFT", "avg_price", 10, 10, 2.0, 3.0)],
    )
    await _emit_shadow_divergence(any_store, plan)

    events = await _shadow_events(any_store)
    assert len(events) == 1
    p = events[0].payload
    assert p["resolutions"] == [
        {"order_id": "o1", "new_status": "canceled", "reason": "broker_reports_canceled"}
    ]
    assert p["inferred_fills"] == [
        {"order_id": "o2", "symbol": "AAPL", "side": "buy", "quantity": 5,
         "price": 1.25, "source_fill_id": "exec-9"}
    ]
    assert p["needs_targeted_query"] == ["o3"]
    assert p["external_orders"] == [
        {"broker_order_id": "bX", "client_order_id": "cX", "symbol": "TSLA",
         "side": "sell", "status": "partially_filled", "filled_quantity": 7}
    ]
    assert p["position_mismatches"] == [
        {"symbol": "MSFT", "kind": "avg_price", "local_quantity": 10,
         "broker_quantity": 10, "local_avg": 2.0, "broker_avg": 3.0}
    ]
