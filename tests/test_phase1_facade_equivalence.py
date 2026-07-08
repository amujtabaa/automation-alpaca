"""Spine v2 Phase 1 — facade seam behavior-equivalence + boundary tests.

Proves the two routes migrated behind the facade
(``GET /api/positions``, ``POST /api/controls/{pause,resume}-buys`` — see
``docs/SPINE_PHASE1_FACADE_REPORT.md``) are byte-for-byte unchanged, plus
unit-level coverage of the facade plumbing itself (the concrete
store-backed implementation, the HTTP error mapping, and the DI providers).

Async (httpx ASGI), app state wired by hand (no lifespan -> no background
loop) — same idiom as ``tests/test_phase7_routes.py``.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException, status

from app.api.deps import get_command_facade, get_query_facade
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.commands import ExecutionCommandFacade
from app.facade.errors import EngineNotReadyError, FacadeError, NotYetImplementedError
from app.facade.http_mapping import facade_error_to_http
from app.facade.queries import ExecutionQueryFacade
from app.facade.store_backed import (
    UNAUTHENTICATED_ACTOR,
    StoreBackedCommandFacade,
    StoreBackedQueryFacade,
)
from app.main import create_app
from app.marketdata.fake import FakeMarketDataFeed
from app.models import OrderSide, OrderStatus
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _app():
    store = InMemoryStateStore()
    await store.initialize()
    adapter = MockBrokerAdapter()
    market_data = FakeMarketDataFeed()
    app = create_app(store)
    app.state.store = store
    app.state.broker_adapter = adapter
    app.state.market_data = market_data
    app.state.settings = Settings()
    return app, store


def _client(app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def _hold(store, symbol, qty, avg=10.0):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id)
    await store.transition_order(buy.id, OrderStatus.CANCELED)


# --------------------------------------------------------------------------- #
# Behavior-equivalence: GET /api/positions through the facade
# --------------------------------------------------------------------------- #
async def test_list_positions_route_matches_direct_store_call():
    app, store = await _app()
    await _hold(store, "AAPL", 100, avg=12.5)
    await _hold(store, "MSFT", 50, avg=300.0)

    async with _client(app) as client:
        response = await client.get("/api/positions")
    assert response.status_code == 200

    expected = await store.list_positions()
    expected_json = [p.model_dump(mode="json") for p in expected]
    assert response.json() == expected_json
    # Sanity: the fixture actually produced non-trivial data, so an equal-but-
    # both-empty false positive is impossible.
    assert len(response.json()) == 2


async def test_list_positions_route_empty_matches_direct_store_call():
    app, store = await _app()
    async with _client(app) as client:
        response = await client.get("/api/positions")
    assert response.status_code == 200
    assert response.json() == []
    assert await store.list_positions() == []


# --------------------------------------------------------------------------- #
# Behavior-equivalence: pause/resume-buys through the facade
# --------------------------------------------------------------------------- #
async def test_pause_buys_route_flips_the_same_store_flag():
    app, store = await _app()
    session_before = await store.get_current_session()
    assert session_before.buys_paused is False

    async with _client(app) as client:
        response = await client.post("/api/controls/pause-buys")

    assert response.status_code == 200
    session_after = await store.get_current_session()
    assert session_after.buys_paused is True
    assert response.json() == session_after.model_dump(mode="json")


async def test_resume_buys_route_flips_the_same_store_flag():
    app, store = await _app()
    await store.set_buys_paused(True)

    async with _client(app) as client:
        response = await client.post("/api/controls/resume-buys")

    assert response.status_code == 200
    session_after = await store.get_current_session()
    assert session_after.buys_paused is False
    assert response.json() == session_after.model_dump(mode="json")


async def test_pause_buys_repeated_call_is_stable():
    """Adversarial-review finding (test-quality lens): the original name of
    this test claimed it was a "behavior-equivalence" check, but it only
    diffed the two responses against EACH OTHER, never against a store-truth
    ground value — so it couldn't have caught a regression that changed BOTH
    calls identically. Renamed to describe what it actually checks
    (repeat-call stability), and left narrow on purpose — the store-truth
    comparison already lives in ``test_pause_buys_route_flips_the_same_
    store_flag`` above."""
    app, store = await _app()
    async with _client(app) as client:
        first = await client.post("/api/controls/pause-buys")
        second = await client.post("/api/controls/pause-buys")
    assert first.status_code == second.status_code == 200
    # buys_paused stays True on the second call; updated_at legitimately
    # re-stamps on every set_buys_paused call (pre-existing store behavior,
    # unrelated to the facade), so that field is excluded from the compare.
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["buys_paused"] == second.json()["buys_paused"] is True


# --------------------------------------------------------------------------- #
# Adversarial-review finding (test-quality lens, empirically confirmed): the
# behavior-equivalence tests above compare route output to store-truth, but
# never prove the ROUTE actually went THROUGH the facade to get there — a
# route silently reverted to call the store directly would produce identical
# output and pass every test above unnoticed (verified by literally doing
# that revert and re-running the suite: all tests still passed). These two
# tests close that gap with a dependency-override spy, so a facade-bypass
# regression fails loudly instead of silently.
# --------------------------------------------------------------------------- #
async def test_list_positions_route_actually_calls_the_query_facade():
    app, store = await _app()
    calls: list[str] = []

    class _SpyQueryFacade:
        async def list_positions(self):
            calls.append("list_positions")
            return await store.list_positions()

    app.dependency_overrides[get_query_facade] = lambda: _SpyQueryFacade()
    try:
        async with _client(app) as client:
            response = await client.get("/api/positions")
        assert response.status_code == 200
        assert calls == ["list_positions"]
    finally:
        app.dependency_overrides.pop(get_query_facade, None)


async def test_pause_and_resume_buys_routes_actually_call_the_command_facade():
    app, store = await _app()
    calls: list[tuple[str, str]] = []

    class _SpyCommandFacade:
        async def pause_buys(self, *, actor):
            calls.append(("pause_buys", actor))
            return await store.set_buys_paused(True)

        async def resume_buys(self, *, actor):
            calls.append(("resume_buys", actor))
            return await store.set_buys_paused(False)

    app.dependency_overrides[get_command_facade] = lambda: _SpyCommandFacade()
    try:
        async with _client(app) as client:
            pause_response = await client.post("/api/controls/pause-buys")
            resume_response = await client.post("/api/controls/resume-buys")
        assert pause_response.status_code == resume_response.status_code == 200
        assert calls == [
            ("pause_buys", UNAUTHENTICATED_ACTOR),
            ("resume_buys", UNAUTHENTICATED_ACTOR),
        ]
    finally:
        app.dependency_overrides.pop(get_command_facade, None)


async def test_kill_switch_route_is_unmigrated_and_unaffected():
    """The kill-switch route deliberately still calls the store directly
    (docs/SPINE_PHASE0_INVENTORY.md §3.4's live ADR-003 conflict) — confirm
    it still works exactly as before, proving the facade migration of its
    sibling routes didn't disturb it."""
    app, store = await _app()
    async with _client(app) as client:
        response = await client.post("/api/controls/kill-switch", json={"engaged": True})
    assert response.status_code == 200
    session = await store.get_current_session()
    assert session.kill_switch is True


# --------------------------------------------------------------------------- #
# Unit: StoreBackedQueryFacade / StoreBackedCommandFacade
# --------------------------------------------------------------------------- #
async def test_store_backed_query_facade_list_positions_forwards_unchanged():
    store = InMemoryStateStore()
    await store.initialize()
    await _hold(store, "AAPL", 10, avg=5.0)
    facade = StoreBackedQueryFacade(store)

    result = await facade.list_positions()
    expected = await store.list_positions()
    assert result == expected


@pytest.mark.parametrize(
    "method_call",
    [
        lambda f: f.list_primaries(),
        lambda f: f.list_spawns(primary_id="x"),
        lambda f: f.kill_state(),
        # NOTE: list_external_orders + list_position_mismatches were MIGRATED in
        # wave 4h (reconciliation read surface) — they now read durable audit
        # records instead of raising. See test_spine_phase4h_reconcile_read.py.
    ],
)
async def test_store_backed_query_facade_unmigrated_methods_raise(method_call):
    facade = StoreBackedQueryFacade(store=None)
    with pytest.raises(NotYetImplementedError):
        await method_call(facade)


async def test_store_backed_command_facade_pause_resume_forward_unchanged():
    store = InMemoryStateStore()
    await store.initialize()
    facade = StoreBackedCommandFacade(store)

    paused = await facade.pause_buys(actor=UNAUTHENTICATED_ACTOR)
    assert paused.buys_paused is True
    assert paused == await store.get_current_session()

    resumed = await facade.resume_buys(actor=UNAUTHENTICATED_ACTOR)
    assert resumed.buys_paused is False
    assert resumed == await store.get_current_session()


@pytest.mark.parametrize(
    "method_call",
    [
        lambda f: f.create_exit(symbol="AAPL", reason="manual_flatten", actor="x"),
        lambda f: f.cancel(order_id="o1", actor="x"),
        lambda f: f.set_kill_switch(engaged=True, actor="x"),
        lambda f: f.emergency_reduce_override(symbol="AAPL", actor="x"),
    ],
)
async def test_store_backed_command_facade_unmigrated_methods_raise(method_call):
    facade = StoreBackedCommandFacade(store=None)
    with pytest.raises(NotYetImplementedError):
        await method_call(facade)


# --------------------------------------------------------------------------- #
# Unit: facade_error_to_http
# --------------------------------------------------------------------------- #
def test_engine_not_ready_maps_to_503():
    http_exc = facade_error_to_http(EngineNotReadyError("startup reconciliation pending"))
    assert isinstance(http_exc, HTTPException)
    assert http_exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_not_yet_implemented_maps_to_501():
    http_exc = facade_error_to_http(NotYetImplementedError("not migrated yet"))
    assert http_exc.status_code == status.HTTP_501_NOT_IMPLEMENTED


def test_generic_facade_error_maps_to_500():
    http_exc = facade_error_to_http(FacadeError("something else"))
    assert http_exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# --------------------------------------------------------------------------- #
# Unit: DI providers construct the right concrete type
# --------------------------------------------------------------------------- #
def _fake_request(**state):
    """A stand-in Request exposing only ``.app.state`` — the facade providers
    read collaborators off it defensively (Phase 6). Absent attrs resolve to
    None via getattr, which is all the store-only providers need."""

    from types import SimpleNamespace

    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**state)))


async def test_get_query_facade_returns_store_backed_instance():
    store = InMemoryStateStore()
    await store.initialize()
    facade = get_query_facade(_fake_request(), store)
    assert isinstance(facade, StoreBackedQueryFacade)
    assert isinstance(facade, ExecutionQueryFacade)


async def test_get_command_facade_returns_store_backed_instance():
    store = InMemoryStateStore()
    await store.initialize()
    facade = get_command_facade(_fake_request(), store)
    assert isinstance(facade, StoreBackedCommandFacade)
    assert isinstance(facade, ExecutionCommandFacade)
