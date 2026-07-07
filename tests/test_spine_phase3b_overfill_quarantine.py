"""Spine v2 Phase 3 wave 3b (part 1) — broker-overfill quarantine projection.

ADR-001: a *broker-authoritative* overfill/oversell that crosses a long-only
position through flat into short is a FACT to be RECORDED and quarantined, not
rejected. This slice makes the event-log projection tolerate a recorded oversell
(project the negative quantity) and adds the quarantine detector, WITHOUT yet
changing the live ``append_fill`` reject path (still rejects local input that
would go negative — the record path + order-blocking is a later slice). So this
is additive: nothing records an oversell yet, so the live position read is
unchanged (proven by the whole position/fill corpus staying green).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.events.projectors import (
    PositionProjector,
    project_symbol_position,
    quarantined_symbols,
)
from app.events.replay import project_store_event_log, verify_dual_store_parity
from app.models import (
    CandidateStatus,
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    Fill,
    OrderSide,
    Position,
)
from app.position import NegativePositionError, apply_fill
from app.store.base import OrderIntentBlockedError
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_TS = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


def _fill(symbol, side, qty, price):
    return Fill(order_id="o", symbol=symbol, side=side, quantity=qty, price=price, filled_at=_TS)


def _fill_event(symbol, side, qty, price, seq, key):
    return ExecutionEvent(
        sequence=seq,
        event_type=ExecutionEventType.FILL,
        source=EventSource.BROKER_STREAM,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        dedupe_key=key,
        ts_event=_TS,
        symbol=symbol,
        side=side,
        quantity=qty,
        price=price,
        order_id="o",
    )


# --------------------------------------------------------------------------- #
# apply_fill: the long-only guard is preserved by default; allow_short records
# --------------------------------------------------------------------------- #
def test_apply_fill_raises_on_oversell_by_default():
    """The long-only backstop for LOCAL input is unchanged — a crossing sell
    still raises unless the caller explicitly opts into recording a short."""
    held = Position(symbol="AAPL", quantity=100, cost_basis=100.0, average_price=1.0)
    with pytest.raises(NegativePositionError):
        apply_fill(held, _fill("AAPL", OrderSide.SELL, 150, 9.0))


def test_apply_fill_records_short_when_allow_short():
    held = Position(symbol="AAPL", quantity=100, cost_basis=100.0, average_price=1.0)
    result = apply_fill(held, _fill("AAPL", OrderSide.SELL, 150, 9.0), allow_short=True)
    assert result.quantity == -50  # recorded broker fact, not hidden
    assert result.cost_basis == 0.0  # avg undefined for a short in a long-only book
    assert result.average_price is None


def test_allow_short_does_not_change_non_crossing_folds():
    """allow_short must only affect the crossing case — normal folds identical."""
    held = Position(symbol="AAPL", quantity=200, cost_basis=300.0, average_price=1.5)
    sell = _fill("AAPL", OrderSide.SELL, 50, 9.0)
    assert apply_fill(held, sell, allow_short=True) == apply_fill(held, sell)


# --------------------------------------------------------------------------- #
# Projection records a broker oversell as a negative position
# --------------------------------------------------------------------------- #
def _oversell_log():
    # BUY 100, then a broker-authoritative SELL 150 (an overfill) -> qty -50.
    return [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, 1, "k1"),
        _fill_event("AAPL", OrderSide.SELL, 150, 9.0, 2, "k2"),
    ]


def test_projector_records_broker_oversell_as_negative():
    position = project_symbol_position(_oversell_log(), "AAPL")
    assert position.quantity == -50
    # PositionProjector.project agrees.
    assert PositionProjector.project(_oversell_log()).positions["AAPL"].quantity == -50


def test_quarantined_symbols_flags_the_oversold_symbol():
    events = _oversell_log() + [_fill_event("MSFT", OrderSide.BUY, 10, 5.0, 3, "k3")]
    assert quarantined_symbols(events) == {"AAPL"}  # MSFT (long) is not quarantined


def test_quarantined_symbols_empty_for_normal_positions():
    events = [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, 1, "k1"),
        _fill_event("AAPL", OrderSide.SELL, 50, 9.0, 2, "k2"),  # down to 50, still long
        _fill_event("MSFT", OrderSide.BUY, 10, 5.0, 3, "k3"),
        _fill_event("MSFT", OrderSide.SELL, 10, 7.0, 4, "k4"),  # flat, not short
    ]
    assert quarantined_symbols(events) == set()


# --------------------------------------------------------------------------- #
# End-to-end (both stores): a broker overfill quarantines the symbol and blocks
# autonomous BUY order intent for it (ADR-001 "no new spawn while quarantined").
# --------------------------------------------------------------------------- #
async def test_broker_overfill_blocks_autonomous_buy_for_the_symbol(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id)
    await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, session_id=session.id)
    sell = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.SELL, 150, session_id=session.id)
    await any_store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0, session_id=session.id)
    assert "AAPL" in await any_store.list_quarantined_symbols()

    # A new APPROVED AAPL candidate cannot dispatch an autonomous BUY order.
    blocked = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    await any_store.transition_candidate(blocked.id, CandidateStatus.APPROVED)
    with pytest.raises(OrderIntentBlockedError):
        await any_store.create_order_for_candidate(blocked.id)

    # A different, non-quarantined symbol is unaffected.
    ok = await any_store.create_candidate(
        "MSFT", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    await any_store.transition_candidate(ok.id, CandidateStatus.APPROVED)
    order = await any_store.create_order_for_candidate(ok.id)
    assert order.symbol == "MSFT"


# --------------------------------------------------------------------------- #
# Replay reproduces the quarantine (ADR-001 required test): the recorded short
# survives a fresh event-log replay, on each store and across the two stores.
# --------------------------------------------------------------------------- #
async def _overfill_script(store):
    """BUY 100, then a broker overfill SELL 150 -> the symbol is recorded short
    (qty -50) and quarantined. Explicit ``filled_at`` so both stores stamp the
    same instant (dual-store parity)."""
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    buy = await store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 100, session_id=sess.id)
    await store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="b1", filled_at=_TS, session_id=sess.id)
    sell = await store.create_order_for_test(cand.id, "AAPL", OrderSide.SELL, 150, session_id=sess.id)
    await store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0, source_fill_id="s1", filled_at=_TS, session_id=sess.id)
    return sess


async def test_replay_reproduces_the_recorded_short(any_store):
    """The quarantine is derived purely from the event log, so replaying that log
    into a fresh projection reproduces the recorded short field-for-field against
    the store's OWN authoritative list_positions (independent derivation path)."""
    await _overfill_script(any_store)
    projection = await project_store_event_log(any_store)
    live = {p.symbol: p for p in await any_store.list_positions()}
    assert projection.positions["AAPL"].quantity == -50
    assert set(projection.positions) == set(live)
    for symbol, position in live.items():
        assert projection.positions[symbol] == position


async def test_overfill_quarantine_dual_store_parity(tmp_path):
    """Replay reproduces the quarantine identically across memory and SQLite —
    the same overfill script projects to the same (negative) read model in both."""
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "overfill.db")
    await _overfill_script(memory)
    await _overfill_script(sqlite)
    try:
        result = await verify_dual_store_parity(memory, sqlite)
        assert result.ok, result.detail
        assert "AAPL" in await memory.list_quarantined_symbols()
        assert "AAPL" in await sqlite.list_quarantined_symbols()
    finally:
        sqlite._conn.close()
        sqlite._conn = None
