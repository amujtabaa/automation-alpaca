"""Spine v2 Phase 4 wave 4c — reconciliation-inferred (synthetic) fill append.

`append_fill` gains `source`/`authority` provenance overrides so a Phase-4
reconciliation-inferred fill is marked RECONCILIATION/SYNTHETIC on the FILL
ExecutionEvent — WITHOUT changing dedup/position semantics. The load-bearing
property: a synthetic fill and the eventual REAL observation of the SAME execution
(same source_fill_id) dedup to one — never a double-count (INV-5 / §7 / R8).

Additive: nothing emits synthetic fills yet (the reconcile wiring is wave 4e).
"""

from __future__ import annotations

import pytest

from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEventType,
    OrderSide,
)

pytestmark = pytest.mark.anyio


async def _order(store, symbol="AAPL", qty=100):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    return await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )


async def test_synthetic_fill_moves_position_and_is_marked(any_store):
    await any_store.initialize()
    order = await _order(any_store)
    await any_store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 40, 9.5,
        source_fill_id="b1:40",
        source=EventSource.RECONCILIATION,
        authority=EventAuthority.SYNTHETIC,
    )
    # Position moved (a synthetic fill is still a position-affecting fact).
    assert (await any_store.get_position("AAPL")).quantity == 40
    # The FILL ExecutionEvent carries the reconciliation provenance.
    fill_events = [
        e for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.FILL
    ]
    assert len(fill_events) == 1
    assert fill_events[0].authority is EventAuthority.SYNTHETIC
    assert fill_events[0].source is EventSource.RECONCILIATION


async def test_synthetic_then_real_fill_same_execution_dedups_no_double_count(any_store):
    # The safety property: a synthetic fill inferred from the mass report, then the
    # SAME execution later observed for real (default provenance) with the SAME
    # source_fill_id, must dedup — position moves ONCE, not twice.
    await any_store.initialize()
    order = await _order(any_store)
    await any_store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 40, 9.5,
        source_fill_id="b1:40",
        source=EventSource.RECONCILIATION, authority=EventAuthority.SYNTHETIC,
    )
    result = await any_store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 40, 9.5, source_fill_id="b1:40",
    )  # the real observation of the same execution
    assert result.status == "duplicate"
    assert (await any_store.get_position("AAPL")).quantity == 40  # NOT 80
    # Exactly one FILL event survived (INV-5).
    fills = [
        e for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.FILL
    ]
    assert len(fills) == 1


async def test_real_then_synthetic_same_execution_also_dedups(any_store):
    # Order-independence: real first, then a synthetic re-inference of the same
    # execution, also dedups.
    await any_store.initialize()
    order = await _order(any_store)
    await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, 40, 9.5, source_fill_id="b1:40")
    result = await any_store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 40, 9.5, source_fill_id="b1:40",
        source=EventSource.RECONCILIATION, authority=EventAuthority.SYNTHETIC,
    )
    assert result.status == "duplicate"
    assert (await any_store.get_position("AAPL")).quantity == 40


async def test_default_provenance_unchanged(any_store):
    # A normal append_fill (no provenance args) still writes a broker-authoritative
    # FILL event — the defaults preserve pre-Phase-4 behavior.
    await any_store.initialize()
    order = await _order(any_store)
    await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, 10, 1.0, source_fill_id="s1")
    fill_events = [
        e for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.FILL
    ]
    assert fill_events[0].authority is EventAuthority.BROKER_AUTHORITATIVE
    assert fill_events[0].source is EventSource.BROKER_REST
