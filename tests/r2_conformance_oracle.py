"""Spec-derived R2 SellIntent<->ExecutionEnvelope conformance oracle.

This file is intentionally named without the default ``test_`` prefix during
Part A.  The consolidation branch is still the pre-R2 base, so the suite is run
explicitly against each candidate implementation::

    pytest -q tests/r2_conformance_oracle.py

Part B must run this exact file as an acceptance gate.  The assertions are
phrased over observable ownership, exposure, event truth, and safety rails;
they do not depend on either candidate's internal R2 helper functions.

Formal core property
--------------------

For every symbol and every point in an envelope-backed exit's lifetime,
``active_sell_intent_for(symbol)`` identifies exactly one owner iff a
non-terminal exit obligation exists: an ACTIVE/FROZEN envelope, a staged
handoff that has not been safely preempted, or a child order whose venue fate
is unresolved.  Releasing terminals free the owner only after the last such
obligation is terminal.  No session, restart, reprice, quarantine, flatten,
kill/resume, or supersession boundary may produce either zero owners beside
possibly-live exposure or two independently actionable owners.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.broker.mock import MockBrokerAdapter
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.monitoring import _converge_expired_envelope_cancels
from app.sellside.policy import decide
from app.sellside.types import ActionKind, BreachSignal, PlannedAction
from app.store.base import (
    EnvelopeTransitionError,
    InvalidOrderError,
    OrderIntentBlockedError,
    SellIntentTransitionError,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 15, 18, 0, 0, tzinfo=timezone.utc)
TAPE_START = NOW - timedelta(minutes=30)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(params=["memory", "sqlite"])
def oracle_store(request, tmp_path):
    if request.param == "memory":
        yield InMemoryStateStore()
        return
    store = SqliteStateStore(tmp_path / "r2-oracle.db")
    yield store
    if store._conn is not None:
        store._conn.close()
        store._conn = None


def _draft(
    intent_id: str,
    *,
    symbol: str = "AAPL",
    quantity: int = 100,
    expiry: EnvelopeExpiryDisposition = EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
    session_id: str | None = None,
) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol=symbol,
        qty_ceiling=quantity,
        floor_price=8.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.25,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=5,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=expiry,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _action(
    kind: ActionKind = ActionKind.SUBMIT,
    *,
    quantity: int = 100,
    price: float = 9.9,
) -> PlannedAction:
    return PlannedAction(
        kind=kind,
        limit_price=price,
        quantity=quantity,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


async def _seed_long(store, *, symbol: str = "AAPL", quantity: int = 100):
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )
    await store.append_fill(
        order.id,
        symbol,
        OrderSide.BUY,
        quantity,
        10.0,
        session_id=session.id,
    )
    # Setup-only reseed (operator-ratified spec change, 2026-07-17 — see
    # work/review/CAMPAIGN-0002-claude/RATIFICATION-partb-completion.md D1):
    # terminalize the establishing BUY so the seeded long is a realistic held
    # position with no lingering open buy. Under the ratified WO-0107 store
    # contract, `flatten_position` refuses to act while an open BUY rests on a
    # held symbol (`FLATTEN_BUYS_OPEN` — the §5.3 self-cross guard; the real
    # caller cancels the buys and retries). Leaving this buy CREATED would make
    # every flatten scenario exercise that signal instead of the deferral /
    # preemption properties this oracle pins. Assertions are untouched.
    await store.transition_order(order.id, OrderStatus.CANCELED)
    return session


async def _activate(
    store,
    *,
    symbol: str = "AAPL",
    quantity: int = 100,
    expiry: EnvelopeExpiryDisposition = EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
):
    await store.initialize()
    session = await _seed_long(store, symbol=symbol, quantity=quantity)
    intent = await store.create_sell_intent(
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=quantity,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _draft(
            intent.id,
            symbol=symbol,
            quantity=quantity,
            expiry=expiry,
            session_id=session.id,
        ),
        actor="oracle-operator",
    )
    return session, intent, envelope


async def _stage(
    store,
    envelope_id: str,
    kind: ActionKind = ActionKind.SUBMIT,
    *,
    at: datetime = NOW,
):
    return await store.stage_envelope_action(
        envelope_id,
        _action(kind),
        snapshot_fingerprint=f"oracle:{kind.value}",
        actor="oracle-engine",
        now=at,
    )


async def _submitted_child(store, envelope_id: str):
    staged = await _stage(store, envelope_id)
    claimed = await store.claim_order_for_submission(staged.order.id)
    assert claimed.outcome == "claimed", claimed.reason
    return await store.transition_order(
        staged.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{staged.order.id}",
    )


async def _child_in_status(store, envelope_id: str, status: OrderStatus):
    staged = await _stage(store, envelope_id)
    claimed = await store.claim_order_for_submission(staged.order.id)
    assert claimed.outcome == "claimed", claimed.reason
    if status is OrderStatus.SUBMITTING:
        return claimed.order
    if status is OrderStatus.TIMEOUT_QUARANTINE:
        return await store.quarantine_timed_out_order(
            staged.order.id, reason="oracle_ambiguous_submit"
        )
    submitted = await store.transition_order(
        staged.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{staged.order.id}",
    )
    if status is OrderStatus.SUBMITTED:
        return submitted
    if status is OrderStatus.PARTIALLY_FILLED:
        await store.record_envelope_fill(
            envelope_id,
            quantity=10,
            dedupe_key=f"oracle:envelope-fill:{submitted.id}",
            price=9.9,
            order_id=submitted.id,
            now=NOW,
        )
        await store.append_fill(
            submitted.id,
            submitted.symbol,
            OrderSide.SELL,
            10,
            9.9,
            source_fill_id=f"oracle-broker-fill-{submitted.id}",
        )
        return await store.transition_order(
            submitted.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=10
        )
    assert status is OrderStatus.CANCEL_PENDING
    return await store.transition_order(submitted.id, OrderStatus.CANCEL_PENDING)


async def _resolve_child(store, order) -> None:
    if order.status is OrderStatus.TIMEOUT_QUARANTINE:
        await store.resolve_timeout_quarantine(order.id, OrderStatus.CANCELED)
    else:
        await store.transition_order(order.id, OrderStatus.CANCELED)


async def _assert_owner(store, intent_id: str, *, present: bool) -> None:
    active = await store.active_sell_intent_for("AAPL")
    intent = await store.get_sell_intent(intent_id)
    if present:
        assert active is not None and active.id == intent_id
        assert intent.status is SellIntentStatus.APPROVED
    else:
        assert active is None
        assert intent.status is SellIntentStatus.EXPIRED


async def test_activation_binds_one_real_owner_and_closes_legacy_ingresses(
    oracle_store,
):
    await oracle_store.initialize()
    session = await _seed_long(oracle_store)
    intent = await oracle_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )

    before = await oracle_store.list_envelopes()
    with pytest.raises((InvalidOrderError, EnvelopeTransitionError)):
        await oracle_store.approve_envelope_activation(_draft("missing-owner"))
    with pytest.raises((InvalidOrderError, EnvelopeTransitionError)):
        await oracle_store.approve_envelope_activation(
            _draft(intent.id, symbol="MSFT", session_id=session.id)
        )
    assert await oracle_store.list_envelopes() == before

    envelope = await oracle_store.approve_envelope_activation(
        _draft(intent.id, session_id=session.id), actor="oracle-operator"
    )
    assert envelope.status is EnvelopeStatus.ACTIVE
    await _assert_owner(oracle_store, intent.id, present=True)

    with pytest.raises(SellIntentTransitionError):
        await oracle_store.create_order_for_sell_intent(
            intent.id, order_type=OrderType.MARKET
        )
    with pytest.raises(SellIntentTransitionError):
        await oracle_store.transition_sell_intent(intent.id, SellIntentStatus.EXPIRED)


@pytest.mark.parametrize("frozen", [False, True], ids=["active", "frozen"])
async def test_session_close_never_orphans_a_nonterminal_mandate(oracle_store, frozen):
    session, intent, envelope = await _activate(oracle_store)
    if frozen:
        await oracle_store.transition_envelope(
            envelope.id, EnvelopeStatus.FROZEN, now=NOW
        )
    await oracle_store.close_session(session.id, actor="oracle-operator")
    await _assert_owner(oracle_store, intent.id, present=True)


@pytest.mark.parametrize(
    "terminal",
    [
        EnvelopeStatus.COMPLETED,
        EnvelopeStatus.EXPIRED,
        EnvelopeStatus.EXHAUSTED,
        EnvelopeStatus.BREACHED,
        EnvelopeStatus.CANCELLED,
    ],
)
async def test_releasing_terminal_frees_owner_when_no_child_can_execute(
    oracle_store, terminal
):
    _, intent, envelope = await _activate(oracle_store)
    if terminal is EnvelopeStatus.COMPLETED:
        completed = await oracle_store.record_envelope_fill(
            envelope.id,
            quantity=100,
            dedupe_key=f"oracle:complete:{envelope.id}",
            price=9.9,
            now=NOW,
        )
        assert completed.status is EnvelopeStatus.COMPLETED
    elif terminal is EnvelopeStatus.CANCELLED:
        await oracle_store.transition_envelope(
            envelope.id, EnvelopeStatus.FROZEN, now=NOW
        )
        await oracle_store.transition_envelope(
            envelope.id, EnvelopeStatus.CANCELLED, now=NOW
        )
    else:
        await oracle_store.transition_envelope(envelope.id, terminal, now=NOW)
    await _assert_owner(oracle_store, intent.id, present=False)


@pytest.mark.parametrize(
    "child_status",
    [
        OrderStatus.SUBMITTING,
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.TIMEOUT_QUARANTINE,
    ],
)
async def test_releasing_terminal_retains_owner_until_uncertain_child_resolves(
    oracle_store, child_status
):
    _, intent, envelope = await _activate(oracle_store)
    child = await _child_in_status(oracle_store, envelope.id, child_status)

    await oracle_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="oracle-hard-rail", now=NOW
    )
    await _assert_owner(oracle_store, intent.id, present=True)

    if child_status is OrderStatus.SUBMITTING:
        # A local cancel after the submission claim does not prove the request
        # stayed local.  Until targeted recovery proves venue absence, the
        # child may still rest and the owner must remain retained.
        await oracle_store.transition_order(child.id, OrderStatus.CANCELED)
        await _assert_owner(oracle_store, intent.id, present=True)
    else:
        await _resolve_child(oracle_store, child)
        await _assert_owner(oracle_store, intent.id, present=False)


async def test_created_replacement_never_masks_a_possibly_live_predecessor(
    oracle_store,
):
    _, intent, envelope = await _activate(oracle_store)
    predecessor = await _submitted_child(oracle_store, envelope.id)
    replacement = await _stage(
        oracle_store,
        envelope.id,
        ActionKind.REPRICE,
        at=NOW + timedelta(seconds=5),
    )
    assert replacement.order.status is OrderStatus.CREATED

    await oracle_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="oracle-hard-rail", now=NOW
    )
    await _assert_owner(oracle_store, intent.id, present=True)

    await oracle_store.transition_order(replacement.order.id, OrderStatus.CANCELED)
    await _assert_owner(oracle_store, intent.id, present=True)
    await oracle_store.transition_order(predecessor.id, OrderStatus.CANCELED)
    await _assert_owner(oracle_store, intent.id, present=False)


async def _releasing_envelope_with_live_child(store):
    _, intent, envelope = await _activate(store)
    child = await _submitted_child(store, envelope.id)
    await store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="oracle-hard-rail", now=NOW
    )
    await _assert_owner(store, intent.id, present=True)
    return intent, envelope, child


async def test_flatten_defers_after_envelope_terminal_while_child_may_rest(
    oracle_store,
):
    intent, envelope, child = await _releasing_envelope_with_live_child(oracle_store)
    before = len(await oracle_store.list_orders())

    result = await oracle_store.flatten_position("AAPL", actor="oracle-operator")

    assert result.deferred is True
    assert result.intent.id == intent.id
    assert result.order.id == child.id
    assert len(await oracle_store.list_orders()) == before
    assert (
        await oracle_store.get_envelope(envelope.id)
    ).status is EnvelopeStatus.BREACHED


async def test_session_close_retains_owner_after_envelope_terminal_with_live_child(
    oracle_store,
):
    intent, _, _ = await _releasing_envelope_with_live_child(oracle_store)

    await oracle_store.close_session(actor="oracle-operator")

    await _assert_owner(oracle_store, intent.id, present=True)


async def test_legacy_dispatch_refused_after_envelope_terminal_with_live_child(
    oracle_store,
):
    intent, _, _ = await _releasing_envelope_with_live_child(oracle_store)

    with pytest.raises(SellIntentTransitionError):
        await oracle_store.create_order_for_sell_intent(
            intent.id, order_type=OrderType.MARKET
        )
    await _assert_owner(oracle_store, intent.id, present=True)


async def test_supersession_transfers_exactly_one_owner_without_release_gap(
    oracle_store,
):
    session, intent, original = await _activate(oracle_store)
    successor = await oracle_store.supersede_envelope(
        original.id,
        _draft(intent.id, quantity=90, session_id=session.id),
        actor="oracle-operator",
        reason="narrow-only",
    )
    assert (
        await oracle_store.get_envelope(original.id)
    ).status is EnvelopeStatus.SUPERSEDED
    assert successor.status is EnvelopeStatus.ACTIVE
    await _assert_owner(oracle_store, intent.id, present=True)

    await oracle_store.transition_envelope(
        successor.id, EnvelopeStatus.BREACHED, reason="oracle-hard-rail", now=NOW
    )
    await _assert_owner(oracle_store, intent.id, present=False)


@pytest.mark.parametrize(
    "child_status", [OrderStatus.SUBMITTED, OrderStatus.TIMEOUT_QUARANTINE]
)
async def test_flatten_defers_to_every_possibly_live_envelope_child(
    oracle_store, child_status
):
    _, intent, envelope = await _activate(oracle_store)
    child = await _child_in_status(oracle_store, envelope.id, child_status)
    sell_count = len(
        [o for o in await oracle_store.list_orders() if o.side is OrderSide.SELL]
    )

    result = await oracle_store.flatten_position("AAPL", actor="oracle-operator")
    assert result.deferred is True
    assert result.intent.id == intent.id
    assert result.order.id == child.id
    assert (
        len([o for o in await oracle_store.list_orders() if o.side is OrderSide.SELL])
        == sell_count
    )
    assert (
        await oracle_store.get_envelope(envelope.id)
    ).status is EnvelopeStatus.ACTIVE


async def test_flatten_preempts_local_staging_without_leaving_a_second_owner(
    oracle_store,
):
    _, intent, envelope = await _activate(oracle_store)
    staged = await _stage(oracle_store, envelope.id)

    result = await oracle_store.flatten_position("AAPL", actor="oracle-operator")
    assert result.deferred is False
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert (
        await oracle_store.get_envelope(envelope.id)
    ).status is EnvelopeStatus.CANCELLED
    assert (
        await oracle_store.get_order(staged.order.id)
    ).status is OrderStatus.CANCELED
    assert (
        await oracle_store.get_sell_intent(intent.id)
    ).status is SellIntentStatus.EXPIRED
    active = await oracle_store.active_sell_intent_for("AAPL")
    assert active is not None and active.id == result.intent.id


async def test_kill_freezes_and_preserves_owner_without_automatic_resume(
    oracle_store,
):
    _, intent, envelope = await _activate(oracle_store)
    staged = await _stage(oracle_store, envelope.id)
    await oracle_store.set_kill_switch(True, actor="oracle-operator")

    assert (
        await oracle_store.get_envelope(envelope.id)
    ).status is EnvelopeStatus.FROZEN
    assert (
        await oracle_store.get_order(staged.order.id)
    ).status is OrderStatus.CANCELED
    await _assert_owner(oracle_store, intent.id, present=True)

    with pytest.raises((EnvelopeTransitionError, OrderIntentBlockedError)):
        await oracle_store.approve_envelope_activation(
            _draft(intent.id, session_id=envelope.session_id), actor="oracle-operator"
        )
    await oracle_store.set_kill_switch(False, actor="oracle-operator")
    assert (
        await oracle_store.get_envelope(envelope.id)
    ).status is EnvelopeStatus.FROZEN
    await _assert_owner(oracle_store, intent.id, present=True)


async def test_emergency_reduce_under_halted_defers_to_resting_envelope_child(
    oracle_store,
):
    _, intent, envelope = await _activate(oracle_store)
    child = await _submitted_child(oracle_store, envelope.id)
    before = len(await oracle_store.list_orders())
    await oracle_store.set_kill_switch(True, actor="oracle-operator")
    await oracle_store.authorize_emergency_reduce_override(
        "AAPL", actor="oracle-operator"
    )

    result = await oracle_store.flatten_position("AAPL", actor="oracle-operator")

    assert result.deferred is True
    assert result.intent.id == intent.id
    assert result.order.id == child.id
    assert len(await oracle_store.list_orders()) == before


async def test_fill_truth_alone_moves_position_and_mandate_quantity(
    oracle_store,
):
    _, _, envelope = await _activate(oracle_store)
    child = await _submitted_child(oracle_store, envelope.id)
    before_position = await oracle_store.get_position("AAPL")
    before_envelope = await oracle_store.get_envelope(envelope.id)

    assert before_position.quantity == 100
    assert before_envelope.remaining_quantity == 100
    assert child.status is OrderStatus.SUBMITTED

    source_fill_id = f"oracle-{child.id}"
    dedupe = f"fill:{child.id}:{source_fill_id}"
    await oracle_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=dedupe,
        price=9.9,
        order_id=child.id,
        now=NOW,
    )
    await oracle_store.record_envelope_fill(
        envelope.id,
        quantity=10,
        dedupe_key=dedupe,
        price=9.9,
        order_id=child.id,
        now=NOW,
    )
    await oracle_store.append_fill(
        child.id,
        "AAPL",
        OrderSide.SELL,
        10,
        9.9,
        source_fill_id=source_fill_id,
    )
    await oracle_store.append_fill(
        child.id,
        "AAPL",
        OrderSide.SELL,
        10,
        9.9,
        source_fill_id=source_fill_id,
    )
    await oracle_store.transition_order(
        child.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=10
    )

    after = await oracle_store.get_envelope(envelope.id)
    position = await oracle_store.get_position("AAPL")
    assert after.remaining_quantity == 90
    assert position.quantity == 90
    assert after.qty_ceiling == before_envelope.qty_ceiling == 100
    assert after.floor_price == before_envelope.floor_price == 8.0


async def test_rollover_keeps_child_bound_to_the_approved_session(oracle_store):
    session, _, envelope = await _activate(oracle_store)
    if hasattr(oracle_store, "_sessions"):
        for record in oracle_store._sessions:
            record.session_date = "2000-01-01"
    else:
        oracle_store._conn.execute("UPDATE sessions SET session_date = '2000-01-01'")
        oracle_store._conn.commit()

    staged = await _stage(oracle_store, envelope.id)
    current = await oracle_store.get_current_session()
    assert current.id != session.id
    assert staged.order.session_id == envelope.session_id == session.id
    claim = await oracle_store.claim_order_for_submission(staged.order.id)
    assert claim.outcome == "claimed", claim.reason


async def test_pre_activation_approved_envelope_does_not_survive_session_close(
    oracle_store,
):
    """APPROVED is pre-activation, not a live delegated exit obligation."""

    await oracle_store.initialize()
    session = await _seed_long(oracle_store)
    intent = await oracle_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    draft = _draft(intent.id, session_id=session.id)
    await oracle_store.create_envelope(draft, actor="oracle-operator")
    await oracle_store.transition_envelope(
        draft.id, EnvelopeStatus.APPROVED, actor="oracle-operator", now=NOW
    )

    await oracle_store.close_session(actor="oracle-operator")
    await _assert_owner(oracle_store, intent.id, present=False)


async def test_needs_review_recovery_retains_owner_after_envelope_terminal(
    oracle_store,
):
    """Human escalation is unresolved venue exposure, not proof of absence."""

    session, intent, envelope = await _activate(oracle_store)
    staged = await _stage(oracle_store, envelope.id)
    claimed = await oracle_store.claim_order_for_submission(staged.order.id)
    assert claimed.outcome == "claimed", claimed.reason
    await oracle_store.transition_order(staged.order.id, OrderStatus.CANCELED)
    await oracle_store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id=f"broker-needs-review-{staged.order.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="oracle operator escalation",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )

    await oracle_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="oracle-hard-rail", now=NOW
    )
    await _assert_owner(oracle_store, intent.id, present=True)


async def test_restart_repairs_both_pre_r2_owner_drift_directions(oracle_store):
    _, intent, envelope = await _activate(oracle_store)

    # Pre-R2 orphan shape: a live envelope beside an EXPIRED owner.
    if hasattr(oracle_store, "_sell_intents"):
        row = oracle_store._sell_intents[intent.id]
        row.status = SellIntentStatus.EXPIRED
        row.expired_at = NOW
    else:
        oracle_store._conn.execute(
            "UPDATE sell_intents SET status = ?, expired_at = ? WHERE id = ?",
            (SellIntentStatus.EXPIRED.value, NOW.isoformat(), intent.id),
        )
        oracle_store._conn.commit()
    await oracle_store.initialize()
    await _assert_owner(oracle_store, intent.id, present=True)

    # Opposite stale projection: a terminal envelope beside an APPROVED owner.
    await oracle_store.transition_envelope(
        envelope.id, EnvelopeStatus.BREACHED, reason="oracle-hard-rail", now=NOW
    )
    if hasattr(oracle_store, "_sell_intents"):
        row = oracle_store._sell_intents[intent.id]
        row.status = SellIntentStatus.APPROVED
        row.expired_at = None
    else:
        oracle_store._conn.execute(
            "UPDATE sell_intents SET status = ?, expired_at = NULL WHERE id = ?",
            (SellIntentStatus.APPROVED.value, intent.id),
        )
        oracle_store._conn.commit()
    await oracle_store.initialize()
    await _assert_owner(oracle_store, intent.id, present=False)


async def test_event_truth_not_stale_order_column_controls_release(oracle_store):
    _, intent, envelope = await _activate(oracle_store)
    child = await _submitted_child(oracle_store, envelope.id)
    if hasattr(oracle_store, "_orders"):
        oracle_store._orders[child.id].status = OrderStatus.CANCELED
    else:
        oracle_store._conn.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            (OrderStatus.CANCELED.value, child.id),
        )
        oracle_store._conn.commit()
    assert (await oracle_store.get_order(child.id)).status is OrderStatus.SUBMITTED

    await oracle_store.transition_envelope(
        envelope.id, EnvelopeStatus.EXPIRED, reason="oracle-ttl", now=NOW
    )
    await _assert_owner(oracle_store, intent.id, present=True)


async def test_monitoring_newest_view_converges_masked_predecessor_cancel(
    oracle_store,
):
    _, intent, envelope = await _activate(oracle_store)
    predecessor = await _submitted_child(oracle_store, envelope.id)
    replacement = await _stage(
        oracle_store,
        envelope.id,
        ActionKind.REPRICE,
        at=NOW + timedelta(seconds=5),
    )
    await oracle_store.transition_envelope(
        envelope.id, EnvelopeStatus.EXPIRED, reason="oracle-ttl", now=NOW
    )
    adapter = MockBrokerAdapter()

    # Candidate mechanisms may choose the local replacement or the venue-live
    # predecessor first.  Repeated ticks must converge both without release.
    await _converge_expired_envelope_cancels(oracle_store, adapter)
    await _converge_expired_envelope_cancels(oracle_store, adapter)
    await _assert_owner(oracle_store, intent.id, present=True)

    current_predecessor = await oracle_store.get_order(predecessor.id)
    if current_predecessor.status is OrderStatus.CANCEL_PENDING:
        await oracle_store.transition_order(predecessor.id, OrderStatus.CANCELED)
    elif current_predecessor.status is not OrderStatus.CANCELED:
        await oracle_store.transition_order(predecessor.id, OrderStatus.CANCELED)
    await _converge_expired_envelope_cancels(oracle_store, adapter)
    assert (
        await oracle_store.get_order(replacement.order.id)
    ).status is OrderStatus.CANCELED
    await _assert_owner(oracle_store, intent.id, present=False)


def _snapshot(seconds: int, *, last: float, bid: float, volume: float):
    return SimpleNamespace(
        updated_at=TAPE_START + timedelta(seconds=seconds),
        last_price=last,
        volume=volume,
        bid=bid,
        ask=bid + 0.02,
        stale=False,
    )


def _policy_envelope() -> ExecutionEnvelope:
    return _draft("spec-owner").model_copy(
        update={
            "status": EnvelopeStatus.ACTIVE,
            "activated_at": TAPE_START,
            "expires_at": NOW + timedelta(hours=6),
            "allowed_session_phases": list(SessionType),
        }
    )


def _clean_tape(length: int = 170):
    return [
        _snapshot(
            10 * i,
            last=10.0 + 0.001 * i,
            bid=9.99 + 0.001 * i,
            volume=1000.0 + i,
        )
        for i in range(length)
    ]


def test_invalid_and_deviation_suspect_prices_never_drive_submission():
    envelope = _policy_envelope()

    below_floor = _clean_tape(120)
    below_floor.append(_snapshot(1200, last=1.0, bid=9.5, volume=3000.0))
    decision = decide(envelope, below_floor, now=NOW, history=[])
    assert isinstance(decision, BreachSignal)
    assert decision.rail == "floor_price"

    clean = _clean_tape()
    poisoned = list(clean)
    poisoned[40] = _snapshot(400, last=1_000_000.0, bid=999_999.99, volume=2000.0)
    clean_decision = decide(envelope, clean, now=NOW, history=[])
    poisoned_decision = decide(envelope, poisoned, now=NOW, history=[])
    assert type(poisoned_decision) is type(clean_decision)
    assert getattr(poisoned_decision, "working_stop", None) == getattr(
        clean_decision, "working_stop", None
    )
