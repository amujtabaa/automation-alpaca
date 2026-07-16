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
    # The only writer of the append-only FILLS TABLE is append_fill (list_fills
    # is its read side). ``record_envelope_fill`` also matches the "fill"
    # substring — WO-0030 lifted the envelope API onto this ABC, making it
    # visible to ``dir`` — but it is NOT a fills-table mutator: it records an
    # execution-fill FACT into the event log and decrements an envelope's
    # remaining_quantity; it never inserts/updates/deletes a fills row. So it is
    # enumerated here for honesty but is neither append_fill's peer nor a
    # forbidden mutator (asserted disjoint below and by the SQLite-source test).
    fill_methods = {
        name
        for name in dir(StateStore)
        if "fill" in name.lower() and not name.startswith("__")
    }
    assert fill_methods == {"append_fill", "list_fills", "record_envelope_fill"}
    forbidden = {
        "update_fill",
        "delete_fill",
        "remove_fill",
        "edit_fill",
        "set_fill",
        "mutate_fill",
    }
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
