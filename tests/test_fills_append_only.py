"""Fills are append-only: there is no update/delete path, in the interface or
the SQLite implementation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models import OrderSide
from app.store.base import StateStore

pytestmark = pytest.mark.anyio


def test_interface_has_no_fill_mutators():
    # The only fill-writing method is append_fill.
    fill_methods = {
        name
        for name in dir(StateStore)
        if "fill" in name.lower() and not name.startswith("__")
    }
    assert fill_methods == {"append_fill", "list_fills"}
    forbidden = {"update_fill", "delete_fill", "remove_fill", "edit_fill",
                 "set_fill", "mutate_fill"}
    assert forbidden.isdisjoint(set(dir(StateStore)))


def test_sqlite_source_never_updates_or_deletes_fills():
    # Structural guarantee: no SQL mutates the append-only fills table.
    src = Path("app/store/sqlite.py").read_text(encoding="utf-8").lower()
    assert "update fills" not in src
    assert "delete from fills" not in src


async def test_append_only_grows_by_one(store):
    candidate = await store.create_candidate("AAPL")
    # Order sized for the cumulative 150 of both fills (D-010 cumulative guard).
    order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 200)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 50, 2.0)
    fills = await store.list_fills(symbol="AAPL")
    assert len(fills) == 2
    # Fills carry no status field — they are immutable facts.
    assert not hasattr(fills[0], "status")
