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


async def test_shadow_parity_holds_across_symbols_and_a_fold_to_flat(any_store):
    """The single-symbol script never folds a symbol to quantity 0 — exactly
    where a projection could diverge from the fill-table fold (flat cost_basis
    reset, average_price None, and whether a flat symbol appears in the map).
    Sell AAPL fully down to flat and interleave MSFT, then compare the shadow
    projection to the store's own list_positions field-for-field."""
    await any_store.initialize()
    sess = await any_store.get_current_session()
    a = await _order(any_store, "AAPL", OrderSide.BUY, 100, sess.id)
    await any_store.append_fill(a.id, "AAPL", OrderSide.BUY, 100, 4.0, source_fill_id="a1", filled_at=_TS, session_id=sess.id)
    m = await _order(any_store, "MSFT", OrderSide.BUY, 20, sess.id)
    await any_store.append_fill(m.id, "MSFT", OrderSide.BUY, 20, 5.0, source_fill_id="m1", filled_at=_TS, session_id=sess.id)
    asell = await _order(any_store, "AAPL", OrderSide.SELL, 100, sess.id)
    await any_store.append_fill(asell.id, "AAPL", OrderSide.SELL, 100, 9.0, source_fill_id="a2", filled_at=_TS, session_id=sess.id)

    projection = await project_store_event_log(any_store)
    live = {p.symbol: p for p in await any_store.list_positions()}
    assert set(projection.positions) == set(live)  # flat AAPL present in both
    assert live["AAPL"].quantity == 0 and live["AAPL"].average_price is None
    for symbol, position in live.items():
        assert projection.positions[symbol] == position


@pytest.mark.parametrize("helper", ["_append_execution_event_unlocked", "_insert_execution_event"])
async def test_shadow_write_failure_rolls_back_the_fill(any_store, monkeypatch, helper):
    """Regression guard for the atomicity coupling: the shadow-event write lives
    INSIDE the fill's atomic block, so if it fails the fill row must roll back
    too. Without this, a future edit moving the shadow write outside the
    _atomic/_tx block would silently break shadow parity while the suite stayed
    green. Fault-inject the store's shadow-write helper and assert the fill AND
    the event log are both left empty."""
    if not hasattr(any_store, helper):
        pytest.skip(f"{type(any_store).__name__} has no {helper}")

    await any_store.initialize()
    sess = await any_store.get_current_session()
    buy = await _order(any_store, "AAPL", OrderSide.BUY, 100, sess.id)

    def _boom(*args, **kwargs):
        raise RuntimeError("injected shadow-write failure")

    monkeypatch.setattr(any_store, helper, _boom)
    with pytest.raises(RuntimeError):
        await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="t1", filled_at=_TS, session_id=sess.id)
    # The fill row rolled back with the failed shadow event — neither persisted.
    assert await any_store.list_fills() == []
    assert await any_store.get_execution_events() == []

    # And the dedup state wasn't poisoned: undo the injection and confirm the
    # same fill now appends cleanly (one fill, one shadow event).
    monkeypatch.undo()
    result = await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="t1", filled_at=_TS, session_id=sess.id)
    assert result.status == "appended"
    assert len(await any_store.list_fills()) == 1
    assert len(await any_store.get_execution_events()) == 1


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
    assert (first.symbol, first.side, first.quantity, first.price, first.ts_event) == (
        "AAPL", OrderSide.BUY, 100, 1.0, _TS,
    )
    # Assert the SELL event's full tuple too — the parity test CANNOT catch a
    # wrong SELL price (apply_fill's proportional cost-basis reduction never
    # reads fill.price on a sell), so a SELL-price regression would only surface
    # at a later PnL/TCA consumer without this direct assertion.
    sell = events[2]
    assert (sell.symbol, sell.side, sell.quantity, sell.price, sell.ts_event) == (
        "AAPL", OrderSide.SELL, 50, 9.0, _TS,
    )


async def test_fill_execution_event_dedupe_key_mirrors_fill_table_per_order(any_store):
    """The event's dedupe_key is the composite ``fill:{order_id}:{source_fill_id}``
    — NOT the bare source_fill_id — so it matches the fill table's
    per-(order_id, source_fill_id) dedup exactly (a global bare key would wrongly
    collide two orders that share a venue fill id)."""
    _, buy = await _fill_script(any_store)
    events = await any_store.get_execution_events()
    assert events[0].dedupe_key == f"fill:{buy.id}:t1"


async def test_fill_without_source_id_emits_a_unique_row_id_dedupe_key(any_store):
    """A fill with no venue source_fill_id has no venue identity, so its event is
    keyed on the fill's unique row id (``fill:{order_id}:@{fill.id}``): unique per
    fill (so it never dedups against a different fill, matching the fill table's
    "null-source is never deduped") yet still matchable, so the event-truth
    backfill neither skips nor double-emits it."""
    await any_store.initialize()
    sess = await any_store.get_current_session()
    buy = await _order(any_store, "AAPL", OrderSide.BUY, 100, sess.id)
    result = await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, filled_at=_TS, session_id=sess.id)
    events = await any_store.get_execution_events()
    assert len(events) == 1
    assert events[0].dedupe_key == f"fill:{buy.id}:@{result.fill.id}"


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


async def test_rejected_invalid_fill_emits_no_execution_event(any_store):
    # A fill REJECTED for intrinsic malformed values (non-positive price) writes
    # no fill row and so must emit no shadow event. (A broker OVERFILL is no
    # longer a reject as of wave 3b — it records + quarantines — so the
    # no-emission-on-reject property is pinned via a still-rejected path.)
    from app.store.base import InvalidFillError

    await any_store.initialize()
    sess = await any_store.get_current_session()
    buy = await _order(any_store, "AAPL", OrderSide.BUY, 100, sess.id)
    with pytest.raises(InvalidFillError):
        await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 0.0, filled_at=_TS, session_id=sess.id)
    assert await any_store.get_execution_events() == []
