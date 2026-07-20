"""WO-0034 — REV-0023 Phase-A2 event-log fidelity (human-gated: event-log truth).

- concurrency-0 (P1): the envelope fill bridge record-first FOLDS the fill, so
  append_fill's broker-overfill check must evaluate against the PRE-fill
  position — otherwise it fabricates a ``fill_overfill_quarantined`` event on
  every clean exit. A REAL overfill still quarantines. (Mechanism upgraded by
  WO-0035 to the root form: append_fill SELF-derives the pre-fill position by
  excluding its own dedupe identity; the interim caller-supplied
  ``prior_position`` parameter is gone. These pins assert the SEMANTIC, which
  is mechanism-independent.)
- spec-1 (P1): a redrive rail refusal (incl. reduce_only) writes a durable
  ``envelope_redrive_refused`` audit event carrying the rail + detail.
- spec-0 (P1): a late fill on an ALREADY-terminal envelope is recorded, not
  chained to BREACHED (INV-085 narrowed to ACTIVE/FROZEN).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.broker.adapter import BrokerError, BrokerFill, BrokerOrderUpdate
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
from app.monitoring import _apply_update
from app.reconciliation import (
    execute_envelope_action,
    redrive_staged_envelope_action,
)
from app.sellside.types import ActionKind, PlannedAction

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
FP = "fp-wo0034"


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


async def active_envelope(store, position: int = 100, **overrides):
    await store.initialize()
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, position, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, position, 10.0, session_id=session.id
    )
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=position
    )
    return await store.approve_envelope_activation(
        make_draft(si.id, **overrides), actor="op"
    )


async def active_envelope_with_late_sell_source(store, *, quantity: int):
    """Prepare a terminal SELL before the envelope owns the symbol."""

    await store.initialize()
    session = await store.get_current_session()
    seed = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        seed.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )
    source_candidate = await store.create_candidate("AAPL", session_id=session.id)
    late_sell = await store.create_order_for_test(
        source_candidate.id,
        "AAPL",
        OrderSide.SELL,
        quantity,
        session_id=session.id,
    )
    await store.transition_order(late_sell.id, OrderStatus.CANCELED)
    intent = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    envelope = await store.approve_envelope_activation(
        make_draft(intent.id), actor="op"
    )
    return envelope, late_sell


async def _submitted_envelope_order(store, env, quantity: int):
    """Stage + submit a SELL for the envelope via the real claim/submit path (an
    envelope-minted SUBMITTED order the fill bridge will attribute)."""
    result = await execute_envelope_action(
        store,
        MockBrokerAdapter(),
        env.id,
        planned(quantity=quantity),
        snapshot_fingerprint=FP,
        now=later(),
    )
    assert result.outcome == "submitted", result.outcome
    order = await store.get_order(result.order_id)
    assert order is not None
    return order


async def _event_types(store):
    return [e.event_type for e in await store.list_events()]


# ============================ concurrency-0 ============================ #


async def test_concurrency0_clean_full_exit_emits_no_overfill_event(any_store):
    env = await active_envelope(any_store)
    order = await _submitted_envelope_order(any_store, env, 100)

    # Full exit: the bridge folds the fill (envelope -> COMPLETED, position -> 0)
    # then append_fill checks overfill against the PRE-fill position (100), so a
    # clean exit is NOT a fabricated overfill.
    await _apply_update(
        any_store,
        order,
        BrokerOrderUpdate(
            OrderStatus.FILLED,
            100,
            [
                BrokerFill(
                    source_fill_id="f1", quantity=100, price=9.9, filled_at=later()
                )
            ],
        ),
    )

    assert "fill_overfill_quarantined" not in await _event_types(any_store), (
        "a clean full exit fabricated a fill_overfill_quarantined event"
    )
    assert (await any_store.get_envelope(env.id)).status is S.COMPLETED
    assert (await any_store.get_position("AAPL")).quantity == 0
    assert "AAPL" not in await any_store.list_quarantined_symbols()


async def test_concurrency0_real_overfill_via_bridge_still_quarantines(any_store):
    env, late_sell = await active_envelope_with_late_sell_source(any_store, quantity=50)
    order = await _submitted_envelope_order(any_store, env, 100)

    # After submission the position drops to 50 (an unrelated exit), so when the
    # broker fills the full 100 on THIS order it drives the position short — a
    # genuine broker-authoritative overfill (ADR-001). The concurrency-0 fix must
    # NOT suppress it: the event fires and the symbol quarantines.
    session = await any_store.get_current_session()
    await any_store.append_fill(
        late_sell.id,
        "AAPL",
        OrderSide.SELL,
        50,
        9.9,
        session_id=session.id,
    )

    await _apply_update(
        any_store,
        order,
        BrokerOrderUpdate(
            OrderStatus.FILLED,
            100,
            [
                BrokerFill(
                    source_fill_id="f1", quantity=100, price=9.9, filled_at=later()
                )
            ],
        ),
    )

    assert "fill_overfill_quarantined" in await _event_types(any_store)
    assert "AAPL" in await any_store.list_quarantined_symbols()


# ============================ spec-1 ============================ #


async def test_spec1_redrive_reduce_only_refusal_is_durably_evented(any_store):
    env, late_sell = await active_envelope_with_late_sell_source(any_store, quantity=95)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    released = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=80),
        snapshot_fingerprint=FP,
        now=later(),
    )
    assert released.outcome == "released"

    # Shrink the POSITION (not the envelope's remaining) via an UNRELATED SELL
    # fill, so validate_action(80 vs remaining 100) passes and the reduce_only
    # re-check (80 vs live position 5) is the refusing rail.
    session = await any_store.get_current_session()
    await any_store.append_fill(
        late_sell.id,
        "AAPL",
        OrderSide.SELL,
        95,
        9.9,
        session_id=session.id,
    )
    refused = await redrive_staged_envelope_action(
        any_store, MockBrokerAdapter(), env.id, now=later(60)
    )
    assert refused is not None and refused.outcome == "cancelled"

    evts = [
        e
        for e in await any_store.list_events()
        if e.event_type == "envelope_redrive_refused"
    ]
    assert evts, (
        "redrive reduce_only refusal left no durable envelope_redrive_refused event"
    )
    assert evts[-1].payload.get("rail") == "reduce_only"
    assert "reduce_only" in (evts[-1].payload.get("detail") or "")


# ============================ spec-0 ============================ #


async def test_spec0_late_fill_on_terminal_envelope_is_recorded_not_breached(any_store):
    env = await active_envelope(any_store)
    order = await _submitted_envelope_order(any_store, env, 100)
    # Clean completion first (ACTIVE -> COMPLETED at remaining 0).
    completed = await any_store.record_envelope_fill(
        env.id,
        quantity=100,
        dedupe_key=f"fill:{order.id}:done",
        order_id=order.id,
        price=9.9,
    )
    assert completed.status is S.COMPLETED

    # A straggler broker execution arrives AFTER terminal: recorded as a late
    # fill, terminal status unchanged — NOT retroactively chained to BREACHED
    # (INV-085 narrowed to ACTIVE/FROZEN; the position-level ADR-001 quarantine
    # is the independent backstop for any real short).
    after = await any_store.record_envelope_fill(
        env.id,
        quantity=20,
        dedupe_key=f"fill:{order.id}:late",
        order_id=order.id,
        price=9.9,
    )
    assert after.status is S.COMPLETED, (
        f"a late fill on a terminal envelope flipped status to {after.status}"
    )
