"""Fills are append-only: there is no update/delete path, in the interface or
the SQLite implementation.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app.models import OrderSide
from app.store.base import StateStore

pytestmark = pytest.mark.anyio


def test_interface_has_no_fill_mutators():
    # ``append_fill`` remains the sole primitive that writes the append-only
    # FILLS TABLE (``list_fills`` is its read side). ``record_envelope_fill``
    # writes event/envelope truth, not a fills row. WO-0114 deliberately adds
    # ``ingest_submit_recovery_fill`` as an evidence-bearing command boundary;
    # the structural test below pins that both stores delegate its economic
    # write to the canonical primitives instead of opening a second table writer.
    fill_methods = {
        name
        for name in dir(StateStore)
        if "fill" in name.lower() and not name.startswith("__")
    }
    assert fill_methods == {
        "append_fill",
        "ingest_submit_recovery_fill",
        "list_fills",
        "record_envelope_fill",
    }
    forbidden = {
        "update_fill",
        "delete_fill",
        "remove_fill",
        "edit_fill",
        "set_fill",
        "mutate_fill",
    }
    assert forbidden.isdisjoint(set(dir(StateStore)))


def test_recovery_fill_command_uses_only_canonical_fill_writers():
    from app.store.memory import InMemoryStateStore
    from app.store.sqlite import SqliteStateStore

    for store_type in (InMemoryStateStore, SqliteStateStore):
        source = inspect.getsource(store_type.ingest_submit_recovery_fill)
        assert "await self.append_fill(" in source
        assert "await self.record_envelope_fill(" in source
        assert "self._fills.append(" not in source
        assert "INSERT INTO fills" not in source


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
