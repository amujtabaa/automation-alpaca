"""Spine v2 Phase 4 wave 4e slice 3b — not-found → targeted-query-before-terminal.

The oversell-critical §7 path: an open order ABSENT from the venue's mass report is
NEVER rejected on that absence alone. Each gets a READ-ONLY targeted client_order_id
query first, and only a venue-CONFIRMED absence sustained past
`open_check_missing_retries` resolves it (SUBMITTED→REJECTED / PARTIALLY_FILLED→
CANCELED, fills preserved). A query FAILURE is never read as absent. The status flip
is event-authoritative (a REJECTED/CANCELED ExecutionEvent).

Setup: a locally-SUBMITTED order the *reconcile* adapter doesn't know (a broker id it
never minted) is both absent from the derived mass report AND confirmed-absent by the
targeted query — the exact "the submit never landed / the venue dropped it" case.
`reconcile_recent_threshold_ms=0` turns off recent-order protection so the absence is
processed immediately (in production the 5s window defers a just-touched order).
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerError, BrokerFill, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    CandidateStatus,
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

pytestmark = pytest.mark.anyio

# The legacy per-order poll only (reconciliation off) — used to set up state.
_LEGACY = Settings(reconciliation_enabled=False)


def _settings(retries=3):
    # Recent-order protection off so an absent order is processed at once.
    return Settings(
        reconcile_recent_threshold_ms=0, reconcile_open_check_missing_retries=retries
    )


async def _absent_submitted(store, *, symbol="AAPL", qty=100, partial=0):
    """A locally-SUBMITTED order taken through the real submit path (via a THROWAWAY
    adapter), so a *separate* fresh reconcile adapter neither reports it open nor
    finds it by targeted query — the exact "submit never landed / venue dropped it"
    case (absent from the mass report AND confirmed-absent by the query)."""

    session = await store.get_current_session()
    cand = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=2.0, session_id=session.id
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)
    throwaway = MockBrokerAdapter()
    await _submit_pending_orders(store, throwaway)  # CREATED→SUBMITTING→SUBMITTED
    if partial:
        throwaway.make_fill(
            order.id, status=OrderStatus.PARTIALLY_FILLED, filled_quantity=partial,
            fills=[BrokerFill("p1", partial, 1.0, utcnow())],
        )
        await _reconcile_open_orders(store, throwaway, _LEGACY)  # ingest the partial
    return order


async def _deferrals(store, order_id):
    return [
        e
        for e in await store.list_events()
        if e.event_type == "order_reconcile_deferred" and e.order_id == order_id
    ]


# --------------------------------------------------------------------------- #
# No premature reject — the load-bearing oversell safeguard.
# --------------------------------------------------------------------------- #
async def test_absent_submitted_not_rejected_until_bound(any_store):
    await any_store.initialize()
    order = await _absent_submitted(any_store)
    adapter = MockBrokerAdapter()
    s = _settings(retries=3)

    # Confirmed-absent, but under the bound → deferred, NOT rejected. A single
    # not-found could be venue lag (§7).
    for _ in range(2):
        await _run_reconciliation(any_store, adapter, s)
        assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED
    assert len(await _deferrals(any_store, order.id)) == 2

    # The bound is reached → REJECTED (never landed).
    await _run_reconciliation(any_store, adapter, s)
    assert (await any_store.get_order(order.id)).status is OrderStatus.REJECTED


async def test_absent_partial_resolves_to_canceled_fills_preserved(any_store):
    await any_store.initialize()
    order = await _absent_submitted(any_store, qty=100, partial=40)
    adapter = MockBrokerAdapter()
    s = _settings(retries=2)

    for _ in range(2):
        await _run_reconciliation(any_store, adapter, s)
    fresh = await any_store.get_order(order.id)
    assert fresh.status is OrderStatus.CANCELED         # not REJECTED — it had fills
    assert fresh.filled_quantity == 40
    # Fills are preserved: the derived position still reflects the 40 that filled.
    assert (await any_store.get_position("AAPL")).quantity == 40


# --------------------------------------------------------------------------- #
# Present at the venue → never resolved (the mass report was just incomplete).
# --------------------------------------------------------------------------- #
async def test_venue_has_the_order_so_it_is_never_resolved(any_store):
    await any_store.initialize()
    order = await _absent_submitted(any_store)
    adapter = MockBrokerAdapter()
    # The targeted query finds it working — it was not absent, only missing from the
    # mass report. The per-order poll owns it; the reconcile must NOT flip it.
    adapter.seed_venue_order(order.id, BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, []))
    s = _settings(retries=1)

    for _ in range(5):
        await _run_reconciliation(any_store, adapter, s)
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED
    assert await _deferrals(any_store, order.id) == []   # nothing deferred/rejected


# --------------------------------------------------------------------------- #
# A query FAILURE is never read as absent (§7) — never rejects; flags needs_review.
# --------------------------------------------------------------------------- #
async def test_query_failure_never_rejects_and_surfaces_needs_review(any_store):
    await any_store.initialize()
    order = await _absent_submitted(any_store)
    adapter = MockBrokerAdapter()
    s = _settings(retries=2)

    for _ in range(5):
        adapter.fail_next_client_query(BrokerError("query endpoint down"))
        await _run_reconciliation(any_store, adapter, s)
        # A query failure is inconclusive — the order is NEVER rejected.
        assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED

    errors = [
        e for e in await _deferrals(any_store, order.id)
        if (e.payload or {}).get("reason") == "query_error"
    ]
    assert errors and any((e.payload or {}).get("needs_review") for e in errors)


async def test_query_errors_do_not_erode_the_not_found_bound(any_store):
    # §7: a run of query FAILURES must not advance the confirmed-not-found bound.
    await any_store.initialize()
    order = await _absent_submitted(any_store)
    adapter = MockBrokerAdapter()
    s = _settings(retries=2)

    # Three query errors (past the bound for query_error) — still SUBMITTED.
    for _ in range(3):
        adapter.fail_next_client_query(BrokerError("down"))
        await _run_reconciliation(any_store, adapter, s)
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED

    # Now clean confirmed-absent: still needs the FULL not_found bound (2), proving
    # the query errors didn't erode it.
    await _run_reconciliation(any_store, adapter, s)   # not_found #1 → defer
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED
    await _run_reconciliation(any_store, adapter, s)   # not_found #2 → REJECT
    assert (await any_store.get_order(order.id)).status is OrderStatus.REJECTED


# --------------------------------------------------------------------------- #
# Event-authoritative + not-touched cases.
# --------------------------------------------------------------------------- #
async def test_reject_is_event_authoritative(any_store):
    await any_store.initialize()
    order = await _absent_submitted(any_store)
    adapter = MockBrokerAdapter()
    s = _settings(retries=1)

    await _run_reconciliation(any_store, adapter, s)   # retries=1 → reject at once
    assert (await any_store.get_order(order.id)).status is OrderStatus.REJECTED
    exec_events = [
        e for e in await any_store.get_execution_events() if e.order_id == order.id
    ]
    assert any(e.event_type is ExecutionEventType.REJECTED for e in exec_events)


async def test_cancel_pending_is_left_to_the_per_order_poll(any_store):
    await any_store.initialize()
    order = await _absent_submitted(any_store)
    await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
    adapter = MockBrokerAdapter()
    s = _settings(retries=1)

    for _ in range(5):
        await _run_reconciliation(any_store, adapter, s)
    # CANCEL_PENDING is excluded from reconcile resolution (§7 / R4) — untouched.
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCEL_PENDING
    assert await _deferrals(any_store, order.id) == []


async def test_managed_open_order_reported_by_venue_is_not_touched(any_store):
    # A normal managed order submitted THROUGH the adapter is reported open by the
    # adapter's derived mass report → matched → not needs_targeted_query → never
    # a not-found candidate, even with recent-protection off (the E5 fidelity fix).
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate(
        "AAPL", suggested_quantity=100, suggested_limit_price=2.0, session_id=session.id
    )
    await any_store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await any_store.create_order_for_candidate(cand.id)
    adapter = MockBrokerAdapter()
    await _submit_pending_orders(any_store, adapter)   # real submit → adapter knows it
    s = _settings(retries=1)

    for _ in range(5):
        await _run_reconciliation(any_store, adapter, s)
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED
    assert await _deferrals(any_store, order.id) == []


# --------------------------------------------------------------------------- #
# Store method: reconcile_resolve_order legality.
# --------------------------------------------------------------------------- #
async def test_reconcile_resolve_order_rejects_filled_target(any_store):
    await any_store.initialize()
    order = await _absent_submitted(any_store)
    # FILLED is not a legal reconcile-resolve target (a position-affecting terminal
    # must flow through a fill — INV-9).
    with pytest.raises(ValueError):
        await any_store.reconcile_resolve_order(order.id, OrderStatus.FILLED)
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTED
