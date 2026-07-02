"""HTTP tests for the Phase 4 order endpoints — GET one + cancel.

Async (httpx ASGI) so order state can be set up precisely through the injected
store and a controllable ``MockBrokerAdapter``: the app state is wired by hand
(no lifespan, so no background loop) and every order status the cancel endpoint
cares about is reached deterministically.

The cancel route depends on the ``BrokerAdapter`` *interface* (via
``get_broker_adapter``); injecting a mock and asserting it is/ isn't called
proves that and exercises the broker-cancel + transition handshake.
"""

from __future__ import annotations

import httpx
import pytest

from app.broker.adapter import BrokerError, BrokerFill, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.main import create_app
from app.models import CandidateStatus, OrderStatus, utcnow
from app.monitoring import _reconcile_open_orders, _submit_pending_orders
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _app_store_adapter():
    """A wired app with state set by hand (no lifespan -> no background loop)."""

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


# --------------------------------------------------------------------------- #
# GET /api/order-recoveries (D-017 / F-002, F-006)
# --------------------------------------------------------------------------- #
async def test_list_order_recoveries_returns_unresolved_by_default():
    from app.models import OrderSide

    app, store, adapter = await _app_store_adapter()
    rec = await store.create_submit_recovery(
        local_order_id="o1",
        broker_order_id="bk-1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        limit_price=1.0,
        failure_reason="unpersisted",
    )
    async with _client(app) as client:
        resp = await client.get("/api/order-recoveries")
        assert resp.status_code == 200
        body = resp.json()
        assert [r["id"] for r in body] == [rec.id]
        assert body[0]["broker_order_id"] == "bk-1"
        assert body[0]["cleanup_status"] == "unresolved"

        # The literal path is not captured as an order_id by /orders/{order_id}.
        assert (await client.get("/api/orders/order-recoveries")).status_code == 404

    # Once resolved, it drops out of the default (unresolved-only) view.
    await store.update_submit_recovery(rec.id, cleanup_status="resolved_canceled")
    async with _client(app) as client:
        assert (await client.get("/api/order-recoveries")).json() == []
        allrecs = await client.get("/api/order-recoveries?unresolved_only=false")
        assert [r["id"] for r in allrecs.json()] == [rec.id]


# --------------------------------------------------------------------------- #
# GET /api/orders/{id}
# --------------------------------------------------------------------------- #
async def test_get_order_known_and_unknown():
    app, store, adapter = await _app_store_adapter()
    order = await _created_order(store)
    async with _client(app) as client:
        ok = await client.get(f"/api/orders/{order.id}")
        assert ok.status_code == 200
        assert ok.json()["id"] == order.id

        missing = await client.get("/api/orders/nope")
        assert missing.status_code == 404


# --------------------------------------------------------------------------- #
# POST /api/orders/{id}/cancel
# --------------------------------------------------------------------------- #
async def test_cancel_submitted_order_goes_cancel_pending_and_is_idempotent():
    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter)
    async with _client(app) as client:
        resp = await client.post(f"/api/orders/{order.id}/cancel")
        assert resp.status_code == 200
        # A cancel REQUEST is not terminal: the order is cancel_pending and stays
        # reconcilable until the broker confirms (CHAOS-1).
        assert resp.json()["status"] == "cancel_pending"
        # Re-cancelling is an idempotent no-op — the broker is not hit again.
        again = await client.post(f"/api/orders/{order.id}/cancel")
        assert again.status_code == 200
        assert again.json()["status"] == "cancel_pending"
    # The broker was asked to cancel the right broker id, exactly once.
    assert adapter.canceled == [order.broker_order_id]


async def test_cancel_created_order_skips_broker():
    """A not-yet-submitted order (no broker id) cancels locally with no broker
    call — there is nothing at the broker to cancel."""

    app, store, adapter = await _app_store_adapter()
    order = await _created_order(store)
    assert order.broker_order_id is None
    async with _client(app) as client:
        resp = await client.post(f"/api/orders/{order.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "canceled"
    assert adapter.canceled == []  # broker never called


async def test_cancel_partially_filled_order_is_allowed():
    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter, qty=100, limit=2.0)
    adapter.make_fill(
        order.id,
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=40,
        fills=[BrokerFill("exec-1", 40, 2.0, utcnow())],
    )
    await _reconcile_open_orders(store, adapter, Settings())
    assert (await store.get_order(order.id)).status is OrderStatus.PARTIALLY_FILLED

    async with _client(app) as client:
        resp = await client.post(f"/api/orders/{order.id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancel_pending"


async def test_cancel_terminal_order_returns_409():
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
        resp = await client.post(f"/api/orders/{order.id}/cancel")
    assert resp.status_code == 409
    assert adapter.canceled == []  # never asked to cancel a filled order


async def test_cancel_unknown_order_returns_404():
    app, store, adapter = await _app_store_adapter()
    async with _client(app) as client:
        resp = await client.post("/api/orders/no-such-order/cancel")
    assert resp.status_code == 404


async def test_cancel_broker_error_surfaces_as_502_order_unchanged():
    """A genuine broker failure on cancel is not swallowed and not reported as
    success: it surfaces as 502 (upstream broker failed) and the order is left
    open and unchanged."""

    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter)
    adapter.fail_next_cancel(BrokerError("alpaca cancel endpoint down"))
    async with _client(app) as client:
        resp = await client.post(f"/api/orders/{order.id}/cancel")
    assert resp.status_code == 502
    # The order stays open (the transition never ran).
    assert (await store.get_order(order.id)).status is OrderStatus.SUBMITTED


class _CancelRaisesNonBrokerError(MockBrokerAdapter):
    """A misbehaving adapter that raises a non-BrokerError on cancel — the route
    must still keep the order unchanged and report 502, not leak a 500."""

    async def cancel_order(self, broker_order_id: str) -> None:
        raise RuntimeError("unexpected adapter failure")


async def test_cancel_non_broker_exception_also_502_order_unchanged():
    app, store, adapter = await _app_store_adapter()
    order = await _submitted_order(store, adapter)
    # Swap in an adapter whose cancel raises something other than BrokerError.
    app.state.broker_adapter = _CancelRaisesNonBrokerError()
    async with _client(app) as client:
        resp = await client.post(f"/api/orders/{order.id}/cancel")
    assert resp.status_code == 502
    assert (await store.get_order(order.id)).status is OrderStatus.SUBMITTED
