"""Spine v2 Phase 4 wave 4h — reconciliation read surface (facade + route).

``GET /api/reconciliation`` (ADR-005 facade-backed) exposes what the reconcile
engine surfaced but never absorbed: external/unmanaged venue orders and
broker-vs-local position drifts (§7). The query facade
(``StoreBackedQueryFacade.list_external_orders`` / ``list_position_mismatches``)
maps the durable, deduped audit records to typed view DTOs; the route only
composes them. An empty response is the healthy steady state.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.facade.store_backed import StoreBackedQueryFacade
from app.main import create_app
from app.models import EventType
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

EXTERNAL = EventType.RECONCILE_EXTERNAL_ORDER.value
MISMATCH = EventType.RECONCILE_POSITION_MISMATCH.value


async def _seed_external(store, broker_id="venue-X", symbol="TSLA"):
    await store.append_event(
        EXTERNAL,
        symbol=symbol,
        payload={
            "broker_order_id": broker_id,
            "client_order_id": None,
            "symbol": symbol,
            "side": "sell",
            "status": "submitted",
            "filled_quantity": 0,
        },
    )


async def _seed_mismatch(store, symbol="AAPL", kind="quantity"):
    await store.append_event(
        MISMATCH,
        symbol=symbol,
        payload={
            "symbol": symbol,
            "kind": kind,
            "local_quantity": 100,
            "broker_quantity": 150,
            "local_avg": 2.0,
            "broker_avg": 2.0,
        },
    )


# --------------------------------------------------------------------------- #
# Facade mapping (dual-store).
# --------------------------------------------------------------------------- #
async def test_facade_maps_external_order_records_to_views(any_store):
    await any_store.initialize()
    await _seed_external(any_store, "venue-A", "TSLA")
    facade = StoreBackedQueryFacade(any_store)

    views = await facade.list_external_orders()
    assert len(views) == 1
    assert views[0].broker_order_id == "venue-A"
    assert views[0].symbol == "TSLA"
    assert views[0].side == "sell"
    assert views[0].surfaced_at is not None


async def test_facade_maps_position_mismatch_records_to_views(any_store):
    await any_store.initialize()
    await _seed_mismatch(any_store, "AAPL", "quantity")
    facade = StoreBackedQueryFacade(any_store)

    views = await facade.list_position_mismatches()
    assert len(views) == 1
    assert views[0].symbol == "AAPL"
    assert views[0].kind == "quantity"
    assert views[0].local_quantity == 100
    assert views[0].broker_quantity == 150


async def test_facade_empty_when_nothing_surfaced(any_store):
    await any_store.initialize()
    facade = StoreBackedQueryFacade(any_store)
    assert await facade.list_external_orders() == []
    assert await facade.list_position_mismatches() == []


# --------------------------------------------------------------------------- #
# HTTP route wiring.
# --------------------------------------------------------------------------- #
def test_route_healthy_empty_on_fresh_app():
    from app.store.memory import InMemoryStateStore

    app = create_app(InMemoryStateStore())
    with TestClient(app) as c:
        resp = c.get("/api/reconciliation")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"external_orders": [], "position_mismatches": []}


def test_route_surfaces_seeded_records(tmp_path):
    """Seed a SQLite store on disk (its own loop), then point a fresh app at the
    same file so the durable records are read back over HTTP — avoids binding an
    in-memory store's lock to a different loop than the TestClient's."""

    db = tmp_path / "recon.db"

    async def _seed():
        store = SqliteStateStore(db)
        await store.initialize()
        await _seed_external(store, "venue-Z", "NVDA")
        await _seed_mismatch(store, "AAPL", "avg_price")
        if store._conn is not None:
            store._conn.close()
            store._conn = None

    asyncio.run(_seed())

    app = create_app(SqliteStateStore(db))
    with TestClient(app) as c:
        body = c.get("/api/reconciliation").json()
    assert [x["broker_order_id"] for x in body["external_orders"]] == ["venue-Z"]
    assert [m["kind"] for m in body["position_mismatches"]] == ["avg_price"]
