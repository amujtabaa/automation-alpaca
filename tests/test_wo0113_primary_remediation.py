"""WO-0113 primary-seat regression pins.

Cluster A closes the exit-preemption gap class found by REV-0032: every BUY intent
born before or during an exit is terminally stood down, every recovery-free
projected CREATED BUY is locally canceled, venue-uncertain BUYs defer envelope
staging, and the stage's injected clock owns the companion mutations.

Mutation record is maintained in WO-0113's progress log. Every safety test is
parametrized through ``any_store`` unless it is a pure shared-planner test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    Candidate,
    CandidateStatus,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    RECOVERY_UNRESOLVED,
    SellReason,
    SessionType,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import OrderIntentBlockedError
from app.store.core import EnvelopeActionPausedError

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc)


def _draft(intent_id: str, session_id: str, *, quantity: int = 100):
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=quantity,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _submit_action(quantity: int = 100):
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _hold(store, quantity: int = 100):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )
    await store.append_fill(
        order.id,
        "AAPL",
        OrderSide.BUY,
        quantity,
        10.0,
        source_fill_id="wo0113-hold",
        session_id=session.id,
    )
    await store.transition_order(order.id, OrderStatus.CANCELED)
    await store.transition_candidate(candidate.id, CandidateStatus.EXPIRED)
    return session


async def _held_with_created_buy(store, *, buy_quantity: int = 40):
    session = await _hold(store)
    candidate = await store.create_candidate(
        "AAPL",
        suggested_quantity=buy_quantity,
        suggested_limit_price=9.9,
        session_id=session.id,
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(candidate.id)
    assert order.status is OrderStatus.CREATED
    return session, candidate, order


async def _activate_envelope(store, session, *, quantity: int = 100):
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=quantity,
        session_id=session.id,
    )
    return await store.approve_envelope_activation(
        _draft(intent.id, session.id, quantity=quantity), actor="wo0113"
    )


async def _open_protection(store, session, *, quantity: int = 100):
    order = await store.open_protection_exit(
        symbol="AAPL",
        target_quantity=quantity,
        floor_price=9.0,
        observed_price=8.5,
        average_price=10.0,
        session_id=session.id,
    )
    assert order is not None
    return order


def _raw_drift_order_status(store, order_id: str, status: OrderStatus) -> None:
    """Distinguishing event-truth state: raw column drifts, projection stays true."""

    if hasattr(store, "_orders"):
        store._orders[order_id] = store._orders[order_id].model_copy(
            update={"status": status}
        )
        return
    store._conn.execute(
        "UPDATE orders SET status = ? WHERE id = ?", (status.value, order_id)
    )
    store._conn.commit()


def _raw_insert_approved_candidate(store, session_id: str) -> Candidate:
    candidate = Candidate(
        symbol="AAPL",
        suggested_quantity=20,
        suggested_limit_price=9.9,
        session_id=session_id,
    ).model_copy(
        update={
            "status": CandidateStatus.APPROVED,
            "approved_at": NOW,
            "updated_at": NOW,
        }
    )
    if hasattr(store, "_candidates"):
        store._candidates[candidate.id] = candidate
        return candidate
    with store._tx() as cur:
        store._insert_candidate(cur, candidate)
    return candidate


async def test_exit_preempt_cancels_nonzero_filled_created_buy(any_store):
    """REV-0032 P1: nonzero-filled CREATED is still future-claimable."""

    session, _candidate, buy = await _held_with_created_buy(any_store)
    await any_store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        10,
        9.8,
        source_fill_id="wo0113-preexisting-buy-fill",
        session_id=session.id,
    )
    await any_store.transition_order(buy.id, OrderStatus.CREATED, filled_quantity=10)
    envelope = await _activate_envelope(any_store, session, quantity=110)

    await any_store.stage_envelope_action(
        envelope.id,
        _submit_action(110),
        snapshot_fingerprint="wo0113-nonzero-created",
        now=NOW,
    )

    after = await any_store.get_order(buy.id)
    assert after.status is OrderStatus.CANCELED
    assert after.filled_quantity == 10
    assert (await any_store.get_position("AAPL")).quantity == 110


async def test_envelope_stage_defers_without_canceling_recovery_owned_created_buy(
    any_store,
):
    """REV-0032 P1: recovery truth outranks a local CREATED column."""

    session, candidate, buy = await _held_with_created_buy(any_store)
    recovery = await any_store.create_submit_recovery(
        local_order_id=buy.id,
        broker_order_id=f"broker-{buy.id}",
        client_order_id=buy.id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=buy.quantity,
        limit_price=buy.limit_price,
        failure_reason="wo0113 recovery-owned CREATED",
        session_id=session.id,
        candidate_id=candidate.id,
    )
    envelope = await _activate_envelope(any_store, session)

    with pytest.raises(EnvelopeActionPausedError, match="same-symbol BUY may execute"):
        await any_store.stage_envelope_action(
            envelope.id,
            _submit_action(),
            snapshot_fingerprint="wo0113-recovery-created",
            now=NOW,
        )

    assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED
    records = await any_store.list_submit_recoveries()
    assert [(item.id, item.cleanup_status) for item in records] == [
        (recovery.id, RECOVERY_UNRESOLVED)
    ]


async def test_exit_preempt_selects_event_projected_created_buy(any_store):
    """REV-0032 P1: both stores decide from event truth, never raw status."""

    session, _candidate, buy = await _held_with_created_buy(any_store)
    claim = await any_store.claim_order_for_submission(buy.id)
    assert claim.order is not None and claim.order.status is OrderStatus.SUBMITTING
    await any_store.transition_order(buy.id, OrderStatus.CREATED)
    _raw_drift_order_status(any_store, buy.id, OrderStatus.SUBMITTING)
    assert (await any_store.get_order(buy.id)).status is OrderStatus.CREATED
    envelope = await _activate_envelope(any_store, session)

    await any_store.stage_envelope_action(
        envelope.id,
        _submit_action(),
        snapshot_fingerprint="wo0113-event-projection",
        now=NOW,
    )

    assert (await any_store.get_order(buy.id)).status is OrderStatus.CANCELED


async def test_envelope_stage_defers_on_venue_uncertain_buy(any_store):
    """C1 symmetric twin: never persist a stale-sized envelope SELL."""

    session, _candidate, buy = await _held_with_created_buy(any_store)
    claim = await any_store.claim_order_for_submission(buy.id)
    assert claim.order is not None and claim.order.status is OrderStatus.SUBMITTING
    envelope = await _activate_envelope(any_store, session)
    order_ids_before = {order.id for order in await any_store.list_orders()}

    with pytest.raises(EnvelopeActionPausedError, match="same-symbol BUY may execute"):
        await any_store.stage_envelope_action(
            envelope.id,
            _submit_action(),
            snapshot_fingerprint="wo0113-stage-buy-uncertain",
            now=NOW,
        )

    assert {order.id for order in await any_store.list_orders()} == order_ids_before
    await any_store.transition_order(buy.id, OrderStatus.CANCELED)
    staged = await any_store.stage_envelope_action(
        envelope.id,
        _submit_action(),
        snapshot_fingerprint="wo0113-stage-after-buy-terminal",
        now=NOW + timedelta(seconds=1),
    )
    assert staged.order is not None and staged.order.quantity == 100


async def test_candidate_creation_is_refused_during_exit_preemption(any_store):
    """C1: a candidate born during a working exit cannot outlive the exit."""

    session = await _hold(any_store)
    await _open_protection(any_store, session)

    with pytest.raises(OrderIntentBlockedError, match="same-symbol exit may execute"):
        await any_store.create_candidate(
            "AAPL",
            suggested_quantity=20,
            suggested_limit_price=9.9,
            session_id=session.id,
        )


async def test_exit_blocked_candidate_dispatch_expires_instead_of_reviving(any_store):
    """C1: the dispatch backstop is terminal, not a temporary parking rail."""

    session = await _hold(any_store)
    await _open_protection(any_store, session)
    candidate = _raw_insert_approved_candidate(any_store, session.id)

    with pytest.raises(OrderIntentBlockedError, match="same-symbol exit may execute"):
        await any_store.create_order_for_candidate(candidate.id)

    after = await any_store.get_candidate(candidate.id)
    assert after.status is CandidateStatus.EXPIRED
    assert after.expired_at is not None


async def test_exit_preempt_companion_cancel_uses_injected_stage_clock(any_store):
    """REV-0032 P2: one logical stage clock owns every atomic companion write."""

    session, _candidate, buy = await _held_with_created_buy(any_store)
    envelope = await _activate_envelope(any_store, session)

    await any_store.stage_envelope_action(
        envelope.id,
        _submit_action(),
        snapshot_fingerprint="wo0113-injected-clock",
        now=NOW,
    )

    after = await any_store.get_order(buy.id)
    assert after.status is OrderStatus.CANCELED
    assert after.canceled_at == NOW
    assert after.updated_at == NOW
