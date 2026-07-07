"""Spine v2 Phase 3 wave 3d — TradingState FSM (§8) as event_truth.

Behavior-preserving refactor: the two legacy booleans (kill_switch / buys_paused)
map onto the 3-state FSM (kill dominates pause), and each control change
first-writes a TRADING_STATE_CHANGED ExecutionEvent carrying the full (kill, pause)
control tuple. The trading_state column is a co-written read-model reconstructable
from the log (proven here); independent-release (pause surviving a kill-release) is
preserved because the log remembers pause.

Enforcement still reads the booleans (equivalent to the derived FSM) in this slice;
the enforcement-reads-trading_state refactor + the Flow-1/ADR-003 manual-flatten
denial are later slices/waves. This file pins the FSM representation + event_truth.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.events.projectors import current_trading_state
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    SellReason,
    SessionRecord,
    SessionStatus,
    TradingState,
)
from app.policy import (
    kill_switch_block_reason,
    order_intent_block_reason,
    session_submission_block_reason,
)
from app.store import core
from app.store.base import CLAIM_BLOCKED, CLAIM_CLAIMED
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# TradingState.of — the boolean -> FSM mapping (kill dominates pause)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "kill,pause,expected",
    [
        (False, False, TradingState.ACTIVE),
        (False, True, TradingState.REDUCING),
        (True, False, TradingState.HALTED),
        (True, True, TradingState.HALTED),  # kill dominates
    ],
)
def test_trading_state_of_mapping(kill, pause, expected):
    assert TradingState.of(kill_switch=kill, buys_paused=pause) is expected


# --------------------------------------------------------------------------- #
# Projector — current_trading_state (latest-wins, session-scoped)
# --------------------------------------------------------------------------- #
def _tsc(session_id: str, to: str, seq: int) -> ExecutionEvent:
    return ExecutionEvent(
        sequence=seq,
        event_type=ExecutionEventType.TRADING_STATE_CHANGED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        session_id=session_id,
        payload={"to": to},
    )


def test_projector_defaults_active_with_no_events():
    assert current_trading_state([], "s1") is TradingState.ACTIVE


def test_projector_latest_wins():
    events = [_tsc("s1", "reducing", 1), _tsc("s1", "halted", 2), _tsc("s1", "reducing", 3)]
    assert current_trading_state(events, "s1") is TradingState.REDUCING


def test_projector_is_session_scoped():
    events = [_tsc("s1", "halted", 1), _tsc("s2", "reducing", 2)]
    assert current_trading_state(events, "s1") is TradingState.HALTED
    assert current_trading_state(events, "s2") is TradingState.REDUCING
    assert current_trading_state(events, "s3") is TradingState.ACTIVE  # unknown -> default


# --------------------------------------------------------------------------- #
# Store — setters derive the FSM, emit the event, and stay event-truth
# --------------------------------------------------------------------------- #
async def test_setters_derive_state_and_column_equals_projection(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    assert session.trading_state is TradingState.ACTIVE
    assert await any_store.current_trading_state() is TradingState.ACTIVE

    s = await any_store.set_buys_paused(True)
    assert s.trading_state is TradingState.REDUCING
    # event_truth: the column == the log projection.
    assert await any_store.current_trading_state() is TradingState.REDUCING

    s = await any_store.set_kill_switch(True)
    assert s.trading_state is TradingState.HALTED
    assert await any_store.current_trading_state() is TradingState.HALTED


async def test_independent_release_pause_survives_kill_release(any_store):
    # The load-bearing case: pause + kill, then release kill -> back to REDUCING
    # (not ACTIVE). Requires the log/column to remember pause independently.
    await any_store.initialize()
    await any_store.set_buys_paused(True)
    await any_store.set_kill_switch(True)
    assert await any_store.current_trading_state() is TradingState.HALTED

    s = await any_store.set_kill_switch(False)
    assert s.buys_paused is True
    assert s.trading_state is TradingState.REDUCING
    assert await any_store.current_trading_state() is TradingState.REDUCING


async def test_event_carries_the_full_control_tuple(any_store):
    await any_store.initialize()
    await any_store.set_kill_switch(True)  # ACTIVE -> HALTED
    tsc = [
        e for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.TRADING_STATE_CHANGED
    ]
    assert len(tsc) == 1
    assert tsc[0].payload == {
        "from": "active", "to": "halted",
        "kill_switch": True, "buys_paused": False, "reason": "kill_switch",
    }
    assert tsc[0].authority is EventAuthority.LOCAL  # our decision, not a broker fact


async def test_redundant_reengage_emits_no_state_change_event(any_store):
    # Re-engaging an already-HALTED kill switch changes no derived state -> no new
    # TRADING_STATE_CHANGED event (the projector's latest-wins stays correct).
    await any_store.initialize()
    await any_store.set_kill_switch(True)
    await any_store.set_kill_switch(True)  # redundant
    tsc = [
        e for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.TRADING_STATE_CHANGED
    ]
    assert len(tsc) == 1  # only the real ACTIVE->HALTED transition


async def test_legacy_audit_events_preserved(any_store):
    # The kill_switch_engaged / buys_paused audit events (and their reason strings)
    # are UNCHANGED — the operator surface + _HELD_REASON_LABELS keep working.
    await any_store.initialize()
    await any_store.set_kill_switch(True)
    await any_store.set_buys_paused(True)
    types = {e.event_type for e in await any_store.list_events()}
    assert "kill_switch_engaged" in types
    assert "buys_paused" in types


# --------------------------------------------------------------------------- #
# Dual-store parity + backfill (restart correctness)
# --------------------------------------------------------------------------- #
async def test_dual_store_trading_state_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "ts.db")
    try:
        for store in (memory, sqlite):
            await store.initialize()
            await store.set_buys_paused(True)
            await store.set_kill_switch(True)
            await store.set_kill_switch(False)  # -> REDUCING
        assert await memory.current_trading_state() is TradingState.REDUCING
        assert await sqlite.current_trading_state() is TradingState.REDUCING
    finally:
        await sqlite.close()


async def test_backfill_makes_a_pre_wave3d_killed_session_consistent(tmp_path):
    # A DB created before wave 3d (sessions has no trading_state column) with a
    # KILLED session: _migrate adds the column ('active' default), then the init
    # backfill emits a TRADING_STATE_CHANGED + fixes the column to HALTED so the
    # projector and the read-model agree on restart.
    path = tmp_path / "old.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        """CREATE TABLE sessions (
               id TEXT PRIMARY KEY, session_date TEXT NOT NULL, mode TEXT NOT NULL,
               session_type TEXT, status TEXT NOT NULL,
               kill_switch INTEGER NOT NULL DEFAULT 0,
               buys_paused INTEGER NOT NULL DEFAULT 0,
               opened_at TEXT NOT NULL, closed_at TEXT,
               created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    conn.execute(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("s1", "2026-07-07", "paper", None, "active", 1, 0, _NOW, None, _NOW, _NOW),
    )
    conn.commit()
    conn.close()

    store = SqliteStateStore(path)
    await store.initialize()
    s1 = next(s for s in await store.list_sessions() if s.id == "s1")
    assert s1.trading_state is TradingState.HALTED
    assert current_trading_state(await store.get_execution_events(), "s1") is TradingState.HALTED

    # Idempotent: reopening does not append a second backfill event.
    await store.close()
    reopened = SqliteStateStore(path)
    await reopened.initialize()
    tsc = [
        e for e in await reopened.get_execution_events()
        if e.event_type is ExecutionEventType.TRADING_STATE_CHANGED
    ]
    assert len(tsc) == 1
    await reopened.close()


# --------------------------------------------------------------------------- #
# SessionRecord.trading_state — the co-written read-model self-heals (validator)
# --------------------------------------------------------------------------- #
def _session(*, kill: bool = False, paused: bool = False) -> SessionRecord:
    return SessionRecord(session_date="2026-07-07", kill_switch=kill, buys_paused=paused)


@pytest.mark.parametrize(
    "kill,paused,expected",
    [
        (False, False, TradingState.ACTIVE),
        (False, True, TradingState.REDUCING),
        (True, False, TradingState.HALTED),
        (True, True, TradingState.HALTED),
    ],
)
def test_model_validator_derives_trading_state_from_booleans(kill, paused, expected):
    # A directly-constructed record can never drift: trading_state is healed to
    # TradingState.of(kill, paused) by the model validator, regardless of what a
    # caller passes (here: nothing) — the §8 read-model invariant is structural.
    assert _session(kill=kill, paused=paused).trading_state is expected


def test_model_validator_heals_an_inconsistent_explicit_trading_state():
    # Passing a trading_state that contradicts the booleans does NOT persist a
    # drifted record — the validator overrides it with the derived value.
    s = SessionRecord(
        session_date="2026-07-07", kill_switch=True, trading_state=TradingState.ACTIVE
    )
    assert s.trading_state is TradingState.HALTED


# --------------------------------------------------------------------------- #
# Slice 5 — the pre-trade predicates READ the FSM (reason strings preserved)
# --------------------------------------------------------------------------- #
class TestEnforcementReadsFsm:
    """The three Rule 8 predicates now decide off ``session.trading_state`` (the
    §8 FSM), not the two legacy booleans. Behavior is identical because the
    validator keeps ``trading_state == TradingState.of(kill, pause)``; these pin
    the FSM→reason-string mapping so a future change to it is caught."""

    def test_order_intent_block_reason_maps_each_fsm_state(self):
        assert order_intent_block_reason(_session()) is None  # ACTIVE
        assert order_intent_block_reason(_session(paused=True)) == "buys_paused"  # REDUCING
        assert order_intent_block_reason(_session(kill=True)) == "kill_switch"  # HALTED
        # kill dominates pause -> HALTED -> kill_switch (not buys_paused)
        assert order_intent_block_reason(_session(kill=True, paused=True)) == "kill_switch"

    def test_kill_switch_block_reason_holds_only_in_halted(self):
        # The protection-floor gate: only HALTED (kill) holds a reduce-only exit;
        # REDUCING (pause) does not.
        assert kill_switch_block_reason(_session()) is None
        assert kill_switch_block_reason(_session(paused=True)) is None  # REDUCING
        assert kill_switch_block_reason(_session(kill=True)) == "kill_switch"  # HALTED

    def test_submission_block_reason_delegates_to_fsm_but_closed_wins(self):
        assert session_submission_block_reason(_session(paused=True)) == "buys_paused"
        assert session_submission_block_reason(_session(kill=True)) == "kill_switch"
        closed = SessionRecord(session_date="2026-07-07", status=SessionStatus.CLOSED)
        assert session_submission_block_reason(closed) == "session_closed"


# --------------------------------------------------------------------------- #
# INV-7 / §8 / ADR-003 — REDUCING is reduce-only; HALTED denies everything
# --------------------------------------------------------------------------- #
def _buy_order() -> Order:
    return Order(
        candidate_id="c1", sell_intent_id=None, symbol="AAPL", side=OrderSide.BUY,
        order_type=OrderType.LIMIT, quantity=10, limit_price=1.0,
        status=OrderStatus.CREATED,
    )


def _protective_sell() -> Order:
    return Order(
        candidate_id=None, sell_intent_id="si1", symbol="AAPL", side=OrderSide.SELL,
        order_type=OrderType.MARKET, quantity=10, limit_price=None,
        status=OrderStatus.CREATED,
    )


class TestReducingIsReduceOnly:
    """The graded semantics the two booleans always encoded but never named
    (§8 / INV-7 / ADR-003): ``REDUCING`` permits a reduce-only PROTECTION_FLOOR
    exit while denying an exposure-increasing BUY; ``HALTED`` denies both. The
    claim planner reads the same FSM-backed predicates as the pure gates above."""

    def test_reducing_allows_reduce_only_sell_but_denies_buy(self):
        reducing = _session(paused=True)
        assert reducing.trading_state is TradingState.REDUCING

        buy = core.plan_claim_order_for_submission(
            order=_buy_order(), own_session=reducing, current_session=reducing
        )
        assert buy.outcome == CLAIM_BLOCKED
        assert buy.reason == "buys_paused"

        sell = core.plan_claim_order_for_submission(
            order=_protective_sell(), own_session=reducing, current_session=reducing,
            sell_reason=SellReason.PROTECTION_FLOOR,
        )
        assert sell.outcome == CLAIM_CLAIMED  # reduce-only exit is permitted

    def test_halted_denies_both_buy_and_reduce_only_sell(self):
        halted = _session(kill=True)
        assert halted.trading_state is TradingState.HALTED

        buy = core.plan_claim_order_for_submission(
            order=_buy_order(), own_session=halted, current_session=halted
        )
        assert buy.outcome == CLAIM_BLOCKED

        sell = core.plan_claim_order_for_submission(
            order=_protective_sell(), own_session=halted, current_session=halted,
            sell_reason=SellReason.PROTECTION_FLOOR,
        )
        assert sell.outcome == CLAIM_BLOCKED
        assert sell.reason == "kill_switch"
