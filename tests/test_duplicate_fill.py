"""Duplicate-fill protection via source_fill_id."""

from __future__ import annotations

import pytest

from app.models import OrderSide

pytestmark = pytest.mark.anyio


async def test_duplicate_source_fill_id_is_ignored(store):
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 100)

    first = await store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 100, 1.00, source_fill_id="exec-1"
    )
    assert first.status == "appended"

    # Same execution id observed again (e.g. overlapping poll / reconnect).
    dup = await store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 100, 9.99, source_fill_id="exec-1"
    )
    assert dup.status == "duplicate"
    assert dup.fill is None

    # Exactly one fill row.
    fills = await store.list_fills(symbol="AAPL")
    assert len(fills) == 1
    assert fills[0].source_fill_id == "exec-1"

    # Position reflects only the first fill (the duplicate's 9.99 is ignored).
    position = await store.get_position("AAPL")
    assert position.quantity == 100
    assert position.average_price == pytest.approx(1.00)

    # Exactly one duplicate-ignored audit event.
    dup_events = [
        e for e in await store.list_events() if e.event_type == "fill_duplicate_ignored"
    ]
    assert len(dup_events) == 1
    assert dup_events[0].payload.get("source_fill_id") == "exec-1"


async def test_distinct_source_fill_ids_both_append(store):
    candidate = await store.create_candidate("AAPL")
    # Order is sized for both fills (cumulative 200) so the distinct-id check is
    # what's exercised, not the cumulative-quantity guard (D-010).
    order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 200)
    await store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="a"
    )
    await store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="b"
    )
    assert len(await store.list_fills(symbol="AAPL")) == 2


async def test_null_source_fill_id_is_not_deduped(store):
    """Fills without a source id are distinct facts, not duplicates."""
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 200)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0)
    await store.append_fill(order.id, "AAPL", OrderSide.BUY, 100, 1.0)
    assert len(await store.list_fills(symbol="AAPL")) == 2
