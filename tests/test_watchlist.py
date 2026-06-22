"""Watchlist CRUD against the in-memory store (IO-free)."""

from __future__ import annotations

import pytest

from app.store.base import UnknownEntityError

pytestmark = pytest.mark.anyio


async def test_add_normalizes_and_lists(store):
    entry = await store.add_watchlist_symbol("  aapl ")
    assert entry.symbol == "AAPL"
    assert entry.armed is False

    listed = await store.list_watchlist()
    assert [e.symbol for e in listed] == ["AAPL"]


async def test_add_is_idempotent(store):
    first = await store.add_watchlist_symbol("AAPL")
    again = await store.add_watchlist_symbol("aapl")  # same symbol, normalized
    assert again.symbol == first.symbol
    assert len(await store.list_watchlist()) == 1


async def test_arm_disarm(store):
    await store.add_watchlist_symbol("AAPL")
    armed = await store.set_watchlist_armed("aapl", True)
    assert armed.armed is True
    assert armed.armed_at is not None

    disarmed = await store.set_watchlist_armed("AAPL", False)
    assert disarmed.armed is False
    assert disarmed.armed_at is None


async def test_arm_unknown_symbol_raises(store):
    with pytest.raises(UnknownEntityError):
        await store.set_watchlist_armed("ZZZZ", True)


async def test_remove(store):
    await store.add_watchlist_symbol("AAPL")
    assert await store.remove_watchlist_symbol("aapl") is True
    assert await store.list_watchlist() == []
    # Removing again is a no-op returning False (not an error).
    assert await store.remove_watchlist_symbol("AAPL") is False


async def test_mutations_write_audit_events(store):
    await store.add_watchlist_symbol("AAPL")
    await store.set_watchlist_armed("AAPL", True)
    await store.remove_watchlist_symbol("AAPL")
    types = [e.event_type for e in await store.list_events()]
    assert "watchlist_added" in types
    assert "watchlist_armed" in types
    assert "watchlist_removed" in types
