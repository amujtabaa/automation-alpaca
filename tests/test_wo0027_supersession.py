"""WO-0027 — supersession transfers the mandate (REV-0022 F6, ADR-009 §3).

Three teeth, both stores:
1. A venue-live working order BLOCKS supersession (the store cannot venue-
   cancel; a successor next to a resting predecessor SELL is the double
   exposure INV-077 forbids in substance). Cancel first, then supersede.
2. Conservation: successor ceiling ≤ the predecessor's CURRENT remaining —
   a racing fill's decrement is never erased; widening requires cancel +
   fresh human approval.
3. A staged CREATED (never-submitted) order does NOT block — it is swept in
   the same atomic unit (nothing of the old mandate survives).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.reconciliation import (
    ENVELOPE_EXEC_RELEASED,
    ENVELOPE_EXEC_SUBMITTED,
    execute_envelope_action,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.core import EnvelopeTransitionError

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
FP = "fp-wo0027"


def later(seconds: int = 30):
    return T_NOW + timedelta(seconds=seconds)


def make_draft(intent_id: str, **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.20,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=T_NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


def planned(kind=ActionKind.SUBMIT, limit_price=9.90, quantity=10) -> PlannedAction:
    return PlannedAction(
        kind=kind,
        limit_price=limit_price,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=9.50,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


async def active_envelope(store, **overrides) -> ExecutionEnvelope:
    await store.initialize()
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return await store.approve_envelope_activation(
        make_draft(si.id, **overrides), actor="operator-a"
    )


async def test_live_working_order_blocks_supersession(any_store):
    """The SPEC-02 repro inverted: with a SELL resting at the venue, the
    amendment must be REFUSED — never two live orders for one approval."""

    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    r1 = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    assert r1.outcome == ENVELOPE_EXEC_SUBMITTED  # resting at the venue

    successor = make_draft(env.sell_intent_id, qty_ceiling=90)
    with pytest.raises(EnvelopeTransitionError, match="live working order"):
        await any_store.supersede_envelope(
            env.id, successor, actor="operator-a", reason="amendment"
        )
    # Nothing changed: old ACTIVE, order resting, successor absent.
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE
    assert (await any_store.get_order(r1.order_id)).status is OrderStatus.SUBMITTED
    assert await any_store.get_envelope(successor.id) is None


async def test_conservation_binds_at_commit_time(any_store):
    env = await active_envelope(any_store)
    await any_store.record_envelope_fill(
        env.id, quantity=40, dedupe_key="fill:o:1", order_id="o", price=9.9
    )
    too_wide = make_draft(env.sell_intent_id, qty_ceiling=61)
    with pytest.raises(EnvelopeTransitionError, match="conserves"):
        await any_store.supersede_envelope(env.id, too_wide, actor="op")
    exact = make_draft(env.sell_intent_id, qty_ceiling=60)
    new_env = await any_store.supersede_envelope(env.id, exact, actor="op")
    assert (await any_store.get_envelope(new_env.id)).remaining_quantity == 60


async def test_staged_created_order_is_swept_not_blocking(any_store):
    """A staged, never-submitted order is local truth — supersession sweeps
    it in the SAME atomic unit instead of refusing (nothing of the old
    mandate survives; the WO-0024 sweep machinery)."""

    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    released = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    assert released.outcome == ENVELOPE_EXEC_RELEASED  # staged CREATED

    successor = make_draft(env.sell_intent_id, qty_ceiling=100)
    new_env = await any_store.supersede_envelope(
        env.id, successor, actor="operator-a", reason="amendment"
    )
    assert (await any_store.get_envelope(new_env.id)).status is S.ACTIVE
    assert (await any_store.get_envelope(env.id)).status is S.SUPERSEDED
    swept = await any_store.get_order(released.order_id)
    assert swept.status is OrderStatus.CANCELED  # died with its mandate
