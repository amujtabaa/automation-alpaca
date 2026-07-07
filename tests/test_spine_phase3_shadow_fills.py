"""Spine v2 Phase 3 wave 3a — shadow-evented broker fill emission.

The fill table stays authoritative for position (`shadow_evented`, NOT yet
`event_truth`); ``append_fill`` now *also* appends a broker-authoritative
``FILL`` ExecutionEvent atomically with the fill row, so the event log mirrors
the fill history and the replay projection can be proven equal to the fill-table
position before the event-truth flip (``docs/MIGRATION_MATRIX.md``).

The load-bearing test is `test_shadow_event_log_projects_the_same_positions_as_
fill_table`: the whole point of the shadow step is that the two derivation paths
agree field-for-field.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.events.replay import project_store_event_log, verify_dual_store_parity
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEventType,
    OrderSide,
)
from app.position import NegativePositionError
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_TS = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


async def _order(store, symbol, side, qty, session_id):
    cand = await store.create_candidate(symbol, session_id=session_id)
    return await store.create_order_for_test(
        cand.id, symbol, side, qty, session_id=session_id
    )


async def _fill_script(store):
    """AAPL buy 100@1, buy 100@2, sell 50@9 (→ qty 150 avg 1.50). Explicit
    ``filled_at`` so both stores stamp the same instant (dual-store parity)."""
    await store.initialize()
    sess = await store.get_current_session()
    buy = await _order(store, "AAPL", OrderSide.BUY, 200, sess.id)
    await store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="t1", filled_at=_TS, session_id=sess.id)
    await store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 2.0, source_fill_id="t2", filled_at=_TS, session_id=sess.id)
    sell = await _order(store, "AAPL", OrderSide.SELL, 50, sess.id)
    await store.append_fill(sell.id, "AAPL", OrderSide.SELL, 50, 9.0, source_fill_id="t3", filled_at=_TS, session_id=sess.id)
    return sess, buy


# --------------------------------------------------------------------------- #
# The shadow invariant: event-log projection == fill-table position
# --------------------------------------------------------------------------- #
async def test_shadow_event_log_projects_the_same_positions_as_fill_table(any_store):
    """The reason wave 3a is safe: the shadow event log, replayed, reproduces
    the fill-table position field-for-field (including ``updated_at`` — both
    derive from the same ``fill.filled_at``). Compared per symbol against the
    store's OWN authoritative list_positions (independent derivation path)."""
    await _fill_script(any_store)
    projection = await project_store_event_log(any_store)
    live = {p.symbol: p for p in await any_store.list_positions()}
    assert set(projection.positions) == set(live)
    for symbol, position in live.items():
        assert projection.positions[symbol] == position


async def test_shadow_fill_log_dual_store_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "shadow.db")
    await _fill_script(memory)
    await _fill_script(sqlite)
    try:
        result = await verify_dual_store_parity(memory, sqlite)
        assert result.ok, result.detail
    finally:
        sqlite._conn.close()
        sqlite._conn = None


# --------------------------------------------------------------------------- #
# Emission: one broker-authoritative FILL event per appended fill
# --------------------------------------------------------------------------- #
async def test_append_fill_emits_one_broker_authoritative_fill_event(any_store):
    await _fill_script(any_store)
    events = await any_store.get_execution_events()
    assert len(events) == 3  # one per appended fill
    first = events[0]
    assert first.event_type is ExecutionEventType.FILL
    assert first.authority is EventAuthority.BROKER_AUTHORITATIVE
    assert first.source is EventSource.BROKER_REST
    assert (first.symbol, first.side, first.quantity, first.price) == (
        "AAPL", OrderSide.BUY, 100, 1.0,
    )
    assert first.ts_event == _TS


async def test_fill_execution_event_dedupe_key_mirrors_fill_table_per_order(any_store):
    """The event's dedupe_key is the composite ``fill:{order_id}:{source_fill_id}``
    — NOT the bare source_fill_id — so it matches the fill table's
    per-(order_id, source_fill_id) dedup exactly (a global bare key would wrongly
    collide two orders that share a venue fill id)."""
    _, buy = await _fill_script(any_store)
    events = await any_store.get_execution_events()
    assert events[0].dedupe_key == f"fill:{buy.id}:t1"


async def test_fill_without_source_id_emits_null_dedupe_key(any_store):
    await any_store.initialize()
    sess = await any_store.get_current_session()
    buy = await _order(any_store, "AAPL", OrderSide.BUY, 100, sess.id)
    await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, filled_at=_TS, session_id=sess.id)
    events = await any_store.get_execution_events()
    assert len(events) == 1
    assert events[0].dedupe_key is None  # never deduped, like the fill table


async def test_two_orders_sharing_a_source_fill_id_both_emit(any_store):
    """The fill table dedups per-order, so two orders reporting the same venue
    fill id both append a fill — and the composite dedupe_key keeps both events
    (they would collide under a bare-source_fill_id key)."""
    await any_store.initialize()
    sess = await any_store.get_current_session()
    o1 = await _order(any_store, "AAPL", OrderSide.BUY, 100, sess.id)
    o2 = await _order(any_store, "AAPL", OrderSide.BUY, 100, sess.id)
    await any_store.append_fill(o1.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="shared", filled_at=_TS, session_id=sess.id)
    await any_store.append_fill(o2.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="shared", filled_at=_TS, session_id=sess.id)
    events = await any_store.get_execution_events()
    assert len(events) == 2
    assert {e.dedupe_key for e in events} == {f"fill:{o1.id}:shared", f"fill:{o2.id}:shared"}


# --------------------------------------------------------------------------- #
# No emission on the non-append paths (duplicate / rejected)
# --------------------------------------------------------------------------- #
async def test_duplicate_fill_emits_no_execution_event(any_store):
    await any_store.initialize()
    sess = await any_store.get_current_session()
    buy = await _order(any_store, "AAPL", OrderSide.BUY, 100, sess.id)
    await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="dup", filled_at=_TS, session_id=sess.id)
    result = await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="dup", filled_at=_TS, session_id=sess.id)
    assert result.status == "duplicate"
    # The duplicate wrote no fill, so it must write no shadow event either.
    assert len(await any_store.get_execution_events()) == 1


async def test_rejected_negative_fill_emits_no_execution_event(any_store):
    await any_store.initialize()
    sess = await any_store.get_current_session()
    sell = await _order(any_store, "AAPL", OrderSide.SELL, 50, sess.id)
    with pytest.raises(NegativePositionError):
        await any_store.append_fill(sell.id, "AAPL", OrderSide.SELL, 50, 9.0, filled_at=_TS, session_id=sess.id)
    # A rejected fill changed no position and must leave the event log empty.
    assert await any_store.get_execution_events() == []
