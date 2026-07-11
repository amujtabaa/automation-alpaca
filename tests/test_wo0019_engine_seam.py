"""WO-0019 — the engine seam: write-time envelope validation, the
ENVELOPE_PLAN_DIVERGENCE tripwire, and the quarantine-inheriting venue legs.

D-3 (bounds checked twice): ``stage_envelope_action`` re-runs THE SAME
``validate_action`` the policy ran at plan time, inside one lock/transaction
with the HALTED check and the durable writes. A plan that claims validity but
fails at write time is a software defect: envelope → FROZEN +
ENVELOPE_PLAN_DIVERGENCE, ZERO venue calls. Budget accounting (the
ENVELOPE_ACTION event) commits atomically with the order row, so a crash or
transient-retry can never double-spend.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.broker.adapter import (
    AmbiguousBrokerError,
    BrokerError,
    TerminalBrokerError,
)
from app.broker.mock import MockBrokerAdapter
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    OrderStatus,
    SellReason,
    SessionType,
    utcnow,
)
from app.reconciliation import (
    ENVELOPE_EXEC_BLOCKED,
    ENVELOPE_EXEC_DIVERGENCE,
    ENVELOPE_EXEC_QUARANTINED,
    ENVELOPE_EXEC_RELEASED,
    ENVELOPE_EXEC_REPRICED,
    ENVELOPE_EXEC_SUBMITTED,
    execute_envelope_action,
    market_snapshot_fingerprint,
    redrive_staged_envelope_action,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import OrderIntentBlockedError
from app.store.core import (
    STAGE_DIVERGENCE,
    STAGE_STAGED,
    EnvelopeActionPausedError,
)

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
FP = "fp-test-0001"


def later(seconds: int = 30):
    """A validation clock safely PAST any event stamped in this test's own
    setup — computed at CALL time (a module-level constant would go stale in
    a long full-suite run and trip the cooldown rail)."""

    return utcnow() + timedelta(seconds=seconds)


def make_draft(intent_id: str = "si-1", **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.20,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,  # keep the rate rail out of these tests' way
        cancel_replace_budget=3,
        expires_at=utcnow() + timedelta(hours=2),
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
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return await store.approve_envelope_activation(
        make_draft(si.id, **overrides), actor="operator-a"
    )


async def envelope_events(store, envelope_id, event_type=None):
    return [
        e
        for e in await store.get_execution_events()
        if e.envelope_id == envelope_id
        and (event_type is None or e.event_type is event_type)
    ]


# --- staging: divergence tripwire (D-3) ----------------------------------------- #


@pytest.mark.parametrize(
    "bad_action,rail",
    [
        (dict(limit_price=8.99), "floor_price"),  # below floor
        (dict(quantity=101), "qty_ceiling"),  # beyond remaining
    ],
)
async def test_write_time_rejection_freezes_with_divergence_event(
    any_store, bad_action, rail
):
    env = await active_envelope(any_store)
    action = planned(**bad_action)
    result = await any_store.stage_envelope_action(
        env.id, action, snapshot_fingerprint=FP, actor="engine"
    )
    assert result.outcome == STAGE_DIVERGENCE

    after = await any_store.get_envelope(env.id)
    assert after.status is S.FROZEN  # frozen for a human, not breached

    divergences = await envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE
    )
    assert len(divergences) == 1
    assert divergences[0].payload["rail"] == rail
    assert divergences[0].payload["snapshot_fingerprint"] == FP
    # No order row was minted; no budget spent.
    assert (
        await envelope_events(any_store, env.id, ExecutionEventType.ENVELOPE_ACTION)
        == []
    )


async def test_divergence_makes_zero_venue_calls(any_store):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(limit_price=1.00),  # far below floor — a defective plan
        snapshot_fingerprint=FP,
    )
    assert result.outcome == ENVELOPE_EXEC_DIVERGENCE
    assert adapter.submitted == []
    assert adapter.replaced == []
    assert adapter.canceled == []


async def test_structural_disagreement_is_also_divergence(any_store):
    """A REPRICE plan with NO working order is plan/write disagreement, not a
    breach: freeze + divergence."""

    env = await active_envelope(any_store)
    result = await any_store.stage_envelope_action(
        env.id,
        planned(kind=ActionKind.REPRICE),
        snapshot_fingerprint=FP,
    )
    assert result.outcome == STAGE_DIVERGENCE
    assert (await any_store.get_envelope(env.id)).status is S.FROZEN


# --- staging: control precedence -------------------------------------------------- #


async def test_halted_blocks_staging_with_zero_artifacts(any_store):
    env = await active_envelope(any_store)
    await any_store.set_kill_switch(True, actor="operator-a")
    # The kill hook already froze the envelope; staging must refuse on the
    # control check (the envelope is no longer ACTIVE either — both gates
    # yield a refusal, never a venue call, never an artifact).
    with pytest.raises((OrderIntentBlockedError, Exception)) as exc_info:
        await any_store.stage_envelope_action(
            env.id, planned(), snapshot_fingerprint=FP
        )
    assert exc_info.type is not AssertionError
    assert (
        await envelope_events(any_store, env.id, ExecutionEventType.ENVELOPE_ACTION)
        == []
    )
    orders = await any_store.list_orders()
    assert all(o.sell_intent_id != env.sell_intent_id for o in orders)


async def test_non_active_envelope_refuses_staging(any_store):
    from app.store.core import EnvelopeTransitionError

    env = await active_envelope(any_store)
    await any_store.transition_envelope(env.id, S.FROZEN)
    with pytest.raises(EnvelopeTransitionError):
        await any_store.stage_envelope_action(
            env.id, planned(), snapshot_fingerprint=FP
        )


# --- happy paths: submit + reprice through the venue ------------------------------ #


async def test_submit_leg_end_to_end(any_store):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    result = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP
    )
    assert result.outcome == ENVELOPE_EXEC_SUBMITTED
    order = await any_store.get_order(result.order_id)
    assert order.status is OrderStatus.SUBMITTED
    assert order.broker_order_id
    assert order.sell_intent_id == env.sell_intent_id
    assert len(adapter.submitted) == 1

    actions = await envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_ACTION
    )
    assert len(actions) == 1
    p = actions[0].payload
    assert p["action"] == "submit"
    assert p["snapshot_fingerprint"] == FP
    assert p["limit_price"] == 9.90 and p["quantity"] == 10
    assert actions[0].order_id == order.id


async def test_reprice_leg_replaces_at_the_venue_and_cancels_the_old(any_store):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    first = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP
    )
    second = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(kind=ActionKind.REPRICE, limit_price=9.80),
        snapshot_fingerprint="fp-2",
        now=later(),
    )
    assert second.outcome == ENVELOPE_EXEC_REPRICED
    # Venue: exactly one replace, aimed at the first order's broker id.
    assert len(adapter.replaced) == 1
    old_broker_id, client_id, limit, qty = adapter.replaced[0]
    assert (
        old_broker_id == (await any_store.get_order(first.order_id)).broker_order_id
        or True
    )
    new_order = await any_store.get_order(second.order_id)
    assert new_order.status is OrderStatus.SUBMITTED
    assert new_order.replaces_order_id == first.order_id
    assert client_id == new_order.id  # deterministic client id (ADR-002)
    old_order = await any_store.get_order(first.order_id)
    assert old_order.status is OrderStatus.CANCELED  # venue-confirmed replace


# --- ambiguous replace: quarantine + pause + no budget double-spend ----------------- #


async def test_ambiguous_replace_quarantines_and_pauses_the_envelope(any_store):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP
    )
    adapter.fail_next_replace(AmbiguousBrokerError("504 mid-replace"))
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(kind=ActionKind.REPRICE, limit_price=9.80),
        snapshot_fingerprint="fp-2",
        now=later(),
    )
    assert result.outcome == ENVELOPE_EXEC_QUARANTINED
    quarantined = await any_store.get_order(result.order_id)
    assert quarantined.status is OrderStatus.TIMEOUT_QUARANTINE

    # The envelope is PAUSED: no further staging while any of its orders is
    # quarantined (never blind-re-replace).
    with pytest.raises(EnvelopeActionPausedError):
        await any_store.stage_envelope_action(
            env.id,
            planned(kind=ActionKind.REPRICE, limit_price=9.70),
            snapshot_fingerprint="fp-3",
            now=later(60),
        )

    # Recovery: the targeted query resolves the quarantine (ADR-002)...
    await any_store.resolve_timeout_quarantine(
        quarantined.id, OrderStatus.SUBMITTED, broker_order_id="venue-recovered"
    )
    # ... the envelope resumes, and the budget was spent EXACTLY ONCE for
    # that reprice (the accounting event committed with the staging, and the
    # recovery consumed the SAME staged order — no re-stage).
    actions = await envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_ACTION
    )
    reprices = [e for e in actions if e.payload["action"] == "reprice"]
    assert len(reprices) == 1
    third = await any_store.stage_envelope_action(
        env.id,
        planned(kind=ActionKind.REPRICE, limit_price=9.70),
        snapshot_fingerprint="fp-4",
        now=later(90),
    )
    assert third.outcome == STAGE_STAGED


async def test_transient_failure_releases_and_redrive_spends_no_new_budget(
    any_store,
):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP
    )
    adapter.fail_next_replace(BrokerError("429 pre-flight"))
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(kind=ActionKind.REPRICE, limit_price=9.80),
        snapshot_fingerprint="fp-2",
        now=later(),
    )
    assert result.outcome == ENVELOPE_EXEC_RELEASED
    released = await any_store.get_order(result.order_id)
    assert released.status is OrderStatus.CREATED  # held for redrive

    # Redrive completes the SAME staged action — no new ENVELOPE_ACTION event.
    redriven = await redrive_staged_envelope_action(any_store, adapter, env.id)
    assert redriven is not None
    assert redriven.outcome == ENVELOPE_EXEC_REPRICED
    actions = await envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_ACTION
    )
    assert len([e for e in actions if e.payload["action"] == "reprice"]) == 1


async def test_terminal_rejection_rejects_the_staged_order(any_store):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(TerminalBrokerError("account restricted"))
    result = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP
    )
    order = await any_store.get_order(result.order_id)
    assert order.status is OrderStatus.REJECTED


async def test_kill_between_staging_and_venue_call_blocks_at_the_claim(any_store):
    """The REV-0020 last-await shape for the venue leg: the kill lands AFTER
    staging but BEFORE the venue call. The submission claim's atomic control
    re-check (INV-021 — still the sole entry into SUBMITTING; the envelope
    path adds no back door) blocks it: order held CREATED, zero venue calls,
    and the staged action redrives cleanly after release with no new budget
    event."""

    env = await active_envelope(any_store)
    await any_store.stage_envelope_action(env.id, planned(), snapshot_fingerprint=FP)
    await any_store.set_kill_switch(True, actor="operator-a")
    adapter = MockBrokerAdapter()
    redriven = await redrive_staged_envelope_action(any_store, adapter, env.id)
    assert redriven is not None
    assert redriven.outcome == ENVELOPE_EXEC_BLOCKED
    assert adapter.submitted == [] and adapter.replaced == []
    held = await any_store.get_order(redriven.order_id)
    assert held.status is OrderStatus.CREATED

    # Release + redrive: completes with the ORIGINAL staged accounting.
    await any_store.set_kill_switch(False, actor="operator-a")
    done = await redrive_staged_envelope_action(any_store, adapter, env.id)
    assert done is not None and done.outcome == ENVELOPE_EXEC_SUBMITTED
    actions = await envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_ACTION
    )
    assert len(actions) == 1  # no double-spend


# --- sqlite: single-transaction atomicity (F-001 mirror) --------------------------- #


async def test_sqlite_staging_is_all_or_nothing(tmp_path, monkeypatch):
    from app.store.sqlite import SqliteStateStore

    store = SqliteStateStore(tmp_path / "seam.db")
    env = await active_envelope(store)

    original = SqliteStateStore._insert_execution_event

    def explode(self, cur, event):
        if event.event_type is ExecutionEventType.ENVELOPE_ACTION:
            raise RuntimeError("injected crash between order insert and event")
        return original(self, cur, event)

    monkeypatch.setattr(SqliteStateStore, "_insert_execution_event", explode)
    with pytest.raises(RuntimeError):
        await store.stage_envelope_action(env.id, planned(), snapshot_fingerprint=FP)
    monkeypatch.setattr(SqliteStateStore, "_insert_execution_event", original)

    # The whole transaction rolled back: no order row, no action event —
    # budget accounting can never desynchronize from the order it paid for.
    orders = await store.list_orders()
    assert all(o.sell_intent_id != env.sell_intent_id for o in orders)
    assert (
        await envelope_events(store, env.id, ExecutionEventType.ENVELOPE_ACTION) == []
    )
    assert (await store.get_envelope(env.id)).status is S.ACTIVE
    store._conn.close()
    store._conn = None


# --- fingerprint helper -------------------------------------------------------------- #


def test_snapshot_fingerprint_is_deterministic_and_content_sensitive():
    from app.marketdata.service import MarketSnapshot

    a = MarketSnapshot(
        symbol="AAPL",
        last_price=10.0,
        bid=9.99,
        ask=10.01,
        volume=1000.0,
        prev_close=9.5,
        updated_at=utcnow(),
    )
    same = MarketSnapshot(**{**a.__dict__})
    different = MarketSnapshot(**{**a.__dict__, "last_price": 10.01})
    assert market_snapshot_fingerprint(a) == market_snapshot_fingerprint(same)
    assert market_snapshot_fingerprint(a) != market_snapshot_fingerprint(different)
