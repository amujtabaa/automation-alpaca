"""Spine v2 Phase 3 wave 3e slice 1 — emergency-reduce override scaffolding.

ADR-003: an audited operator override that scopes a SINGLE reduce-only exit while
the session is ``Halted``. The override is a separate ``{session, symbol}`` grant
recorded as an ``EMERGENCY_REDUCE_OVERRIDE`` ``ExecutionEvent`` (durable truth),
consumed by an ``EMERGENCY_REDUCE_OVERRIDE_RESOLVED`` event; the global
``TradingState`` stays ``Halted`` (kill dominates — a global flip is unsafe, plan
E3). This slice is INERT: the grant is recorded + queryable but nothing reads it
yet (the claim-gate wiring is slice 3/4), so the whole corpus stays green.

Pins the projector, dual-store parity, and replay-stability of the grant fact.
"""

from __future__ import annotations

import pytest

from app.events.projectors import active_emergency_reduce_overrides
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------- #
# Projector — active_emergency_reduce_overrides (latest-wins, {session, symbol})
# --------------------------------------------------------------------------- #
def _ovr(session_id: str, symbol: str, seq: int, *, resolved: bool = False) -> ExecutionEvent:
    return ExecutionEvent(
        sequence=seq,
        event_type=(
            ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE_RESOLVED if resolved
            else ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE
        ),
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        session_id=session_id,
        symbol=symbol,
        payload={"actor": "op", "reason": "manual", "resolved": resolved},
    )


def test_projector_empty_is_empty():
    assert active_emergency_reduce_overrides([], "s1") == set()


def test_projector_grant_activates_resolve_consumes():
    grant = [_ovr("s1", "AAPL", 1)]
    assert active_emergency_reduce_overrides(grant, "s1") == {"AAPL"}

    consumed = [_ovr("s1", "AAPL", 1), _ovr("s1", "AAPL", 2, resolved=True)]
    assert active_emergency_reduce_overrides(consumed, "s1") == set()

    # A re-grant after a resolve re-activates (latest-wins).
    regranted = consumed + [_ovr("s1", "AAPL", 3)]
    assert active_emergency_reduce_overrides(regranted, "s1") == {"AAPL"}


def test_projector_is_session_and_symbol_scoped():
    events = [_ovr("s1", "AAPL", 1), _ovr("s1", "MSFT", 2), _ovr("s2", "AAPL", 3)]
    assert active_emergency_reduce_overrides(events, "s1") == {"AAPL", "MSFT"}
    assert active_emergency_reduce_overrides(events, "s2") == {"AAPL"}
    assert active_emergency_reduce_overrides(events, "s3") == set()  # unknown -> empty


def test_authority_is_local_not_broker():
    # An operator command, not a broker fact.
    assert _ovr("s1", "AAPL", 1).authority is EventAuthority.LOCAL


# --------------------------------------------------------------------------- #
# Store — grant/resolve are event-truth; list == the log projection
# --------------------------------------------------------------------------- #
async def test_store_grant_then_resolve_round_trip(any_store):
    await any_store.initialize()
    assert await any_store.list_emergency_reduce_overrides() == set()

    await any_store.grant_emergency_reduce_override("AAPL", actor="op1", reason="halt exit")
    assert await any_store.list_emergency_reduce_overrides() == {"AAPL"}
    # event_truth: the list == the fold of the event log.
    session = await any_store.get_current_session()
    assert active_emergency_reduce_overrides(
        await any_store.get_execution_events(), session.id
    ) == {"AAPL"}

    await any_store.resolve_emergency_reduce_override("AAPL", actor="op1", reason="done")
    assert await any_store.list_emergency_reduce_overrides() == set()


async def test_store_grant_writes_execution_event_and_audit(any_store):
    await any_store.initialize()
    await any_store.grant_emergency_reduce_override("aapl", actor="op1", reason="halt exit")

    ov = [
        e for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE
    ]
    assert len(ov) == 1
    assert ov[0].symbol == "AAPL"  # normalized
    assert ov[0].authority is EventAuthority.LOCAL
    assert ov[0].payload == {"actor": "op1", "reason": "halt exit", "resolved": False}

    audit = {e.event_type for e in await any_store.list_events()}
    assert "emergency_reduce_override_granted" in audit


async def test_store_grant_is_symbol_scoped(any_store):
    await any_store.initialize()
    await any_store.grant_emergency_reduce_override("AAPL", actor="op", reason="r")
    await any_store.grant_emergency_reduce_override("MSFT", actor="op", reason="r")
    await any_store.resolve_emergency_reduce_override("AAPL", actor="op", reason="r")
    assert await any_store.list_emergency_reduce_overrides() == {"MSFT"}


# --------------------------------------------------------------------------- #
# Dual-store parity (memory == sqlite) + inert (no behavior wired)
# --------------------------------------------------------------------------- #
async def test_dual_store_override_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "ovr.db")
    try:
        for store in (memory, sqlite):
            await store.initialize()
            await store.grant_emergency_reduce_override("AAPL", actor="op", reason="r")
            await store.grant_emergency_reduce_override("MSFT", actor="op", reason="r")
            await store.resolve_emergency_reduce_override("MSFT", actor="op", reason="r")
        assert await memory.list_emergency_reduce_overrides() == {"AAPL"}
        assert await sqlite.list_emergency_reduce_overrides() == {"AAPL"}
    finally:
        await sqlite.close()


async def test_grant_is_inert_does_not_block_or_alter_position(any_store):
    # Slice 1 is additive: recording a grant changes NO other flow. A held
    # position + a granted override leaves the position untouched and no order
    # exists — nothing reads the override yet (claim-gate wiring is slice 3/4).
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    from app.models import OrderSide, OrderStatus

    buy = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id)
    await any_store.transition_order(buy.id, OrderStatus.CANCELED)

    await any_store.grant_emergency_reduce_override("AAPL", actor="op", reason="r")

    pos = await any_store.get_position("AAPL")
    assert pos.quantity == 100  # unchanged
    assert await any_store.active_sell_intent_for("AAPL") is None  # nothing fired
