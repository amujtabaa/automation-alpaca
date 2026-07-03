"""Wave 2 Part 2 (D-020) — GET /api/operator/orders classifies lifecycle
server-side, so the cockpit (and any future UI) renders truth instead of
re-deriving it.

Async (httpx ASGI) so each order state the endpoint classifies is reached
deterministically through the injected store + a controllable
``MockBrokerAdapter``, with no lifespan (no background loop mutating state).
"""

from __future__ import annotations

import httpx
import pytest

from app.broker.adapter import BrokerFill
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.main import create_app
from app.models import CandidateStatus, OrderSide, OrderStatus, utcnow
from app.monitoring import _reconcile_open_orders, _submit_pending_orders
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _app_store_adapter():
    store = InMemoryStateStore()
    await store.initialize()
    adapter = MockBrokerAdapter()
    app = create_app(store)
    app.state.store = store
    app.state.broker_adapter = adapter
    return app, store, adapter


def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def _created_order(store, *, symbol="AAPL", qty=10, limit=1.0):
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(candidate.id)


async def _submitted_order(store, adapter, **kw):
    order = await _created_order(store, **kw)
    await _submit_pending_orders(store, adapter)
    return await store.get_order(order.id)


async def _block(store, order, reason):
    await store.append_event(
        "order_submission_blocked",
        message=f"held: {reason}",
        symbol=order.symbol,
        order_id=order.id,
        payload={"reason": reason},
        session_id=order.session_id,
    )


async def _operator_orders(client):
    resp = await client.get("/api/operator/orders")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _by_id(body):
    return {v["order"]["id"]: v for v in body["orders"]}


# --------------------------------------------------------------------------- #
# operational_status classification, one order per label
# --------------------------------------------------------------------------- #
async def test_awaiting_submission_when_created_and_unblocked():
    app, store, _ = await _app_store_adapter()
    order = await _created_order(store)
    async with _client(app) as client:
        view = _by_id(await _operator_orders(client))[order.id]
    assert view["operational_status"] == "awaiting_submission"
    assert view["reason"] is None
    assert view["cancelable"] is True


@pytest.mark.parametrize(
    "reason,expected",
    [
        ("kill_switch", "held_kill_switch"),
        ("buys_paused", "held_buys_paused"),
        ("session_closed", "held_session_closed"),
        ("unknown_session", "held_session_closed"),
        # The D-013a cross-session hold reasons plan_claim_order_for_submission
        # actually emits (own session permissive, live session stopped) — a kill
        # switch is a kill switch regardless of which session tripped it.
        ("current_kill_switch", "held_kill_switch"),
        ("current_buys_paused", "held_buys_paused"),
        ("something_new", "held"),  # unrecognized reason -> generic held, reason kept
    ],
)
async def test_created_order_held_maps_reason_to_label(reason, expected):
    app, store, _ = await _app_store_adapter()
    order = await _created_order(store)
    await _block(store, order, reason)
    async with _client(app) as client:
        view = _by_id(await _operator_orders(client))[order.id]
    assert view["operational_status"] == expected
    assert view["reason"] == reason  # raw reason always surfaced for a held order
    assert view["cancelable"] is True


async def test_latest_block_event_wins():
    app, store, _ = await _app_store_adapter()
    order = await _created_order(store)
    await _block(store, order, "kill_switch")
    await _block(store, order, "buys_paused")  # later event overwrites
    async with _client(app) as client:
        view = _by_id(await _operator_orders(client))[order.id]
    assert view["operational_status"] == "held_buys_paused"


async def test_submitting_label_and_no_reason():
    app, store, _ = await _app_store_adapter()
    order = await _created_order(store)
    claim = await store.claim_order_for_submission(order.id)
    assert claim.order.status is OrderStatus.SUBMITTING
    # A stale block event from a prior hold must NOT label a claimed order held —
    # once past CREATED the status is the truth.
    await _block(store, order, "kill_switch")
    async with _client(app) as client:
        view = _by_id(await _operator_orders(client))[order.id]
    assert view["operational_status"] == "submitting"
    assert view["reason"] is None
    assert view["cancelable"] is True


async def test_submitted_label():
    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter)
    async with _client(app) as client:
        view = _by_id(await _operator_orders(client))[order.id]
    assert view["operational_status"] == "submitted"
    assert view["cancelable"] is True


async def test_partially_filled_label():
    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter, qty=100, limit=2.0)
    adapter.make_fill(
        order.id,
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=40,
        fills=[BrokerFill("exec-1", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(store, adapter, Settings())
    async with _client(app) as client:
        view = _by_id(await _operator_orders(client))[order.id]
    assert view["operational_status"] == "partially_filled"
    assert view["cancelable"] is True


async def test_cancel_pending_label_is_not_cancelable():
    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter)
    await store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
    async with _client(app) as client:
        view = _by_id(await _operator_orders(client))[order.id]
    assert view["operational_status"] == "cancel_pending"
    assert view["cancelable"] is False  # cancel already requested


# --------------------------------------------------------------------------- #
# Terminal orders excluded; stale flag; recovery records
# --------------------------------------------------------------------------- #
async def test_terminal_orders_are_excluded():
    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter, qty=10, limit=2.0)
    adapter.make_fill(
        order.id,
        status=OrderStatus.FILLED,
        filled_quantity=10,
        fills=[BrokerFill("exec-1", 10, 2.0, utcnow())],
    )
    await _reconcile_open_orders(store, adapter, Settings())
    assert (await store.get_order(order.id)).status is OrderStatus.FILLED
    async with _client(app) as client:
        body = await _operator_orders(client)
    assert order.id not in _by_id(body)  # settled -> not an operator concern


async def test_stale_flag_reflects_order_stale_event():
    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter)
    async with _client(app) as client:
        assert _by_id(await _operator_orders(client))[order.id]["stale"] is False
        await store.append_event(
            "order_stale", order_id=order.id, symbol=order.symbol, payload={}
        )
        assert _by_id(await _operator_orders(client))[order.id]["stale"] is True


async def test_recovery_records_classified_and_surfaced():
    app, store, _ = await _app_store_adapter()
    unresolved = await store.create_submit_recovery(
        local_order_id="o1",
        broker_order_id="bk-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        limit_price=1.0,
        failure_reason="unpersisted submit",
    )
    needs = await store.create_submit_recovery(
        local_order_id="o2",
        broker_order_id="bk-2",
        symbol="MSFT",
        side=OrderSide.BUY,
        quantity=5,
        limit_price=2.0,
        failure_reason="partial fill orphan",
    )
    await store.update_submit_recovery(needs.id, cleanup_status="needs_review")

    async with _client(app) as client:
        body = await _operator_orders(client)

    recs = {r["record"]["id"]: r for r in body["recoveries"]}
    assert recs[unresolved.id]["operational_status"] == "broker_submission_failed"
    assert recs[unresolved.id]["reason"] == "unpersisted submit"
    assert recs[needs.id]["operational_status"] == "recovery_required"

    # A cleanly-resolved record drops out of the operator view (open-only).
    await store.update_submit_recovery(unresolved.id, cleanup_status="resolved_canceled")
    async with _client(app) as client:
        body = await _operator_orders(client)
    assert unresolved.id not in {r["record"]["id"] for r in body["recoveries"]}


async def test_operator_endpoint_is_read_only_get_only():
    app, _, _ = await _app_store_adapter()
    async with _client(app) as client:
        assert (await client.post("/api/operator/orders")).status_code == 405
