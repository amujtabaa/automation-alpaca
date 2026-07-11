"""Wave 2 Part 3 (D-020) — one correlation_id ties a candidate's whole
lifecycle together for incident reconstruction.

The parity test drives candidate -> approve -> order -> claim -> submit -> fill
through BOTH stores and asserts every event in that chain shares one key (the
candidate's id); the route test proves GET /api/events?correlation_id= returns
exactly that lifecycle.
"""

from __future__ import annotations

import httpx
import pytest

from app.main import create_app
from app.models import CandidateStatus, OrderSide, OrderStatus
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _drive_lifecycle(store, *, symbol="AAPL", sfid="s1"):
    """candidate -> approved -> order -> claimed(SUBMITTING) -> submitted -> fill."""
    cand = await store.create_candidate(
        symbol, suggested_quantity=10, suggested_limit_price=1.0
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)
    await store.claim_order_for_submission(order.id)
    await store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="bk-" + symbol
    )
    await store.append_fill(
        order.id, symbol, OrderSide.BUY, 10, 1.0, source_fill_id=sfid
    )
    return cand, order


# --------------------------------------------------------------------------- #
# Store parity: the full lifecycle shares one correlation_id, both stores
# --------------------------------------------------------------------------- #
async def test_full_lifecycle_shares_one_correlation_id(any_store):
    store = any_store
    await store.initialize()
    cand, _ = await _drive_lifecycle(store)

    corr = await store.list_events(correlation_id=cand.id)
    types = {e.event_type for e in corr}
    # Creation, approval, order creation, claim, submission-transition, and the
    # fill are all reachable under the one key.
    assert {
        "candidate_created",
        "candidate_transition",
        "order_created",
        "order_submission_claimed",
        "order_transition",
        "fill_appended",
    } <= types, types

    # Every event the filter returns carries exactly that key...
    assert all(e.correlation_id == cand.id for e in corr)
    # ...and the key IS the candidate's id, stamped at creation.
    created = next(e for e in corr if e.event_type == "candidate_created")
    assert created.correlation_id == cand.id


async def test_correlation_id_isolates_candidates(any_store):
    store = any_store
    await store.initialize()
    cand_a, _ = await _drive_lifecycle(store, symbol="AAPL", sfid="a1")
    cand_b, _ = await _drive_lifecycle(store, symbol="MSFT", sfid="b1")

    a_events = await store.list_events(correlation_id=cand_a.id)
    assert a_events, "expected events for candidate A"
    # None of B's events leak into A's correlation view.
    assert all(e.correlation_id == cand_a.id for e in a_events)
    assert cand_b.id not in {e.correlation_id for e in a_events}
    # Both symbols were driven, so B has its own non-empty, disjoint view.
    b_events = await store.list_events(correlation_id=cand_b.id)
    assert {e.id for e in a_events}.isdisjoint({e.id for e in b_events})


async def test_rejected_fill_against_known_order_still_correlates(any_store):
    store = any_store
    await store.initialize()
    cand, order = await _drive_lifecycle(store, sfid="ok")
    # A malformed fill (non-positive quantity) against the same, known order is
    # rejected by the value guard — which runs before the order-existence check.
    # It must still correlate under the candidate's key, like every other fill
    # event, so incident reconstruction sees the rejection.
    with pytest.raises(Exception):
        await store.append_fill(
            order.id, "AAPL", OrderSide.BUY, 0, 1.0, source_fill_id="bad"
        )

    corr = await store.list_events(correlation_id=cand.id)
    rejected = [e for e in corr if e.event_type == "fill_rejected_invalid"]
    assert rejected, (
        "the malformed-fill rejection must appear under the candidate's key"
    )
    assert all(e.correlation_id == cand.id for e in rejected)


async def test_submit_recovery_ledger_events_correlate(any_store):
    """A Phase-7 readiness audit found the F-002 submit-recovery ledger's own
    bookkeeping events (submit_recovery_recorded / _needs_review / _resolved)
    carried no candidate_id and so silently dropped out of the correlation
    filter — an operator reconstructing an incident via correlation_id would
    miss the recovery outcome entirely. create_submit_recovery now threads
    candidate_id through (order.candidate_id is available at the call site);
    update_submit_recovery resolves it from the local order (orders are never
    deleted, so this reliably resolves) for its later terminal-status events."""

    store = any_store
    await store.initialize()
    cand, order = await _drive_lifecycle(store, sfid="orig")
    # Simulate the F-002 orphan: order accepted by the broker but locally
    # terminal (a manual cancel raced the submit).
    await store.transition_order(order.id, OrderStatus.CANCELED)
    rec = await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id="bk-orphan",
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        limit_price=order.limit_price,
        failure_reason="unpersisted",
        session_id=order.session_id,
        candidate_id=order.candidate_id,
    )
    await store.update_submit_recovery(
        rec.id, cleanup_status="needs_review", bump_attempt=True
    )

    corr = await store.list_events(correlation_id=cand.id)
    types = {e.event_type for e in corr}
    assert "submit_recovery_recorded" in types, types
    assert "submit_recovery_needs_review" in types, types
    assert all(e.correlation_id == cand.id for e in corr)


async def test_non_candidate_events_have_no_correlation_id(any_store):
    store = any_store
    await store.initialize()
    # A market-data-style event names no candidate -> correlation_id stays None.
    await store.append_event("market_data_stale", symbol="AAPL", payload={"minutes": 6})
    events = await store.list_events(event_type="market_data_stale")
    assert events and all(e.correlation_id is None for e in events)


async def test_explicit_correlation_id_overrides_candidate_default(any_store):
    store = any_store
    await store.initialize()
    # An explicit correlation_id wins over the candidate_id default (the escape
    # hatch for a caller that wants to correlate under a different key).
    ev = await store.append_event(
        "candidate_created", candidate_id="c1", correlation_id="explicit-key"
    )
    assert ev.correlation_id == "explicit-key"
    assert (await store.list_events(correlation_id="explicit-key"))[0].id == ev.id


# --------------------------------------------------------------------------- #
# Route: GET /api/events?correlation_id= returns the lifecycle
# --------------------------------------------------------------------------- #
async def test_events_route_filters_by_correlation_id():
    store = InMemoryStateStore()
    await store.initialize()
    cand, _ = await _drive_lifecycle(store)
    # An unrelated event that must NOT appear under the candidate's key.
    await store.append_event("market_data_stale", symbol="TSLA", payload={})

    app = create_app(store)
    app.state.store = store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/events", params={"correlation_id": cand.id})
        assert resp.status_code == 200
        body = resp.json()

    assert body, "expected the candidate's lifecycle events"
    assert all(e["correlation_id"] == cand.id for e in body)
    assert "market_data_stale" not in {e["event_type"] for e in body}
