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

from datetime import datetime, timedelta, timezone

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
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
    utcnow,
)
from app.reconciliation import (
    ENVELOPE_EXEC_DIVERGENCE,
    ENVELOPE_EXEC_CANCELLED,
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
    STAGE_REFUSED_STALE,
    STAGE_STAGED,
    EnvelopeActionPausedError,
)

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
FP = "fp-test-0001"

# Deterministic decision clock: Wednesday 2026-07-15 14:00 UTC = 10:00 ET,
# REGULAR hours. validate_action now rails on TTL + session phase (WO-0024),
# so wall-clock-derived nows (this container sits on a weekend) would
# spuriously rail out of phase.
T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def later(seconds: int = 30):
    """The injected validation clock, seconds past the fixed T_NOW basis."""

    return T_NOW + timedelta(seconds=seconds)


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
    # WO-0026: staging rails on the live position (reduce-only) — a
    # realistic envelope test holds the shares it is mandated to sell.
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
        # WO-0029A (ADR-010 §5 amendment accepted 2026-07-12): only rails
        # DETERMINISTIC at the seam (same inputs -> the validators themselves
        # disagree) are DEFECTS. State-dependent rails (qty vs remaining,
        # structural order-liveness) are benign stale-plan refusals — see
        # test_write_time_stale_facts_refuse_without_freezing below.
        (dict(limit_price=8.99), "floor_price"),  # below floor — a defect
    ],
)
async def test_write_time_rejection_freezes_with_divergence_event(
    any_store, bad_action, rail
):
    env = await active_envelope(any_store)
    action = planned(**bad_action)
    result = await any_store.stage_envelope_action(
        env.id, action, snapshot_fingerprint=FP, actor="engine", now=later()
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
        now=later(),
    )
    assert result.outcome == ENVELOPE_EXEC_DIVERGENCE
    assert adapter.submitted == []
    assert adapter.replaced == []
    assert adapter.canceled == []


async def test_write_time_stale_facts_refuse_without_freezing(any_store):
    """WO-0029A (ADR-010 §5 amendment): a rail that only fails against
    CURRENT state — a fill shrank remaining between plan and write — is a
    BENIGN STALE-PLAN REFUSAL: evented (action=refused_stale), envelope
    UNTOUCHED, no order, zero venue calls; the policy replans next tick."""

    env = await active_envelope(any_store)
    await any_store.record_envelope_fill(
        env.id, quantity=95, dedupe_key="fill:o:race", order_id="o", price=9.9
    )  # remaining 100 -> 5; the plan below was sized against 100
    result = await any_store.stage_envelope_action(
        env.id, planned(quantity=10), snapshot_fingerprint=FP, now=later()
    )
    assert result.outcome == STAGE_REFUSED_STALE
    after = await any_store.get_envelope(env.id)
    assert after.status is S.ACTIVE  # NOT frozen — nothing is defective
    refusals = [
        e
        for e in await envelope_events(
            any_store, env.id, ExecutionEventType.ENVELOPE_ACTION
        )
        if e.payload.get("action") == "refused_stale"
    ]
    assert len(refusals) == 1 and refusals[0].payload["rail"] == "qty_ceiling"
    assert (
        await envelope_events(
            any_store, env.id, ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE
        )
        == []
    )  # the defect tripwire did NOT fire
    # The refusal spends no budget and blocks no cooldown: a correctly-sized
    # replan stages cleanly right after.
    retry = await any_store.stage_envelope_action(
        env.id, planned(quantity=5), snapshot_fingerprint="fp-retry", now=later(60)
    )
    assert retry.outcome == STAGE_STAGED


async def test_structural_disagreement_is_a_stale_refusal(any_store):
    """WO-0029A: order liveness is state that legitimately changes between
    plan and write — a REPRICE meeting a dead/absent working order refuses
    WITHOUT freezing (was: divergence+FROZEN under the pre-amendment §5)."""

    env = await active_envelope(any_store)
    result = await any_store.stage_envelope_action(
        env.id,
        planned(kind=ActionKind.REPRICE),
        snapshot_fingerprint=FP,
        now=later(),
    )
    assert result.outcome == STAGE_REFUSED_STALE
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE


async def test_write_time_ttl_rail_bites_at_the_seam(any_store):
    """WO-0024: TTL is a §2 HARD rail — validate_action (both D-3 call sites)
    now rails on it, so a plan that crosses expires_at between decide and
    stage is caught at write time ("bounds checked twice" made true)."""

    env = await active_envelope(any_store)
    result = await any_store.stage_envelope_action(
        env.id,
        planned(),
        snapshot_fingerprint=FP,
        now=T_NOW + timedelta(hours=3),  # past the 2h expires_at
    )
    assert result.outcome == STAGE_DIVERGENCE
    divergences = await envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE
    )
    assert len(divergences) == 1 and divergences[0].payload["rail"] == "ttl"


async def test_write_time_session_phase_rail_bites_at_the_seam(any_store):
    """WO-0024: session phase is a §2 HARD rail at write time too — staged
    in-phase at 15:59, written out-of-phase at 20:30 must refuse."""

    # TTL must outlive the phase flip so the PHASE rail is what bites.
    env = await active_envelope(any_store, expires_at=T_NOW + timedelta(days=1))
    result = await any_store.stage_envelope_action(
        env.id,
        planned(),
        snapshot_fingerprint=FP,
        now=T_NOW.replace(hour=22),  # 18:00 ET — after-hours, not REGULAR
    )
    assert result.outcome == STAGE_DIVERGENCE
    divergences = await envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE
    )
    assert len(divergences) == 1
    assert divergences[0].payload["rail"] == "session_phase"


async def test_position_shrink_between_plan_and_write_hits_reduce_only(any_store):
    """WO-0026: the D-3 race shape, extended to POSITION. The plan was sized
    against a 100-share book; a non-envelope SELL (manual flatten leg,
    external reconcile fill) shrinks it to 20 before the write. The envelope
    counter alone would pass (80 <= remaining 100) — the reduce-only rail is
    what refuses, which is exactly why BOTH counters must gate (F1×F5)."""

    env = await active_envelope(any_store)
    session = await any_store.get_current_session()
    flat_cand = await any_store.create_candidate("AAPL", session_id=session.id)
    sell = await any_store.create_order_for_test(
        flat_cand.id, "AAPL", OrderSide.SELL, 80, session_id=session.id
    )
    await any_store.append_fill(
        sell.id, "AAPL", OrderSide.SELL, 80, 10.5, session_id=session.id
    )  # book: 100 -> 20; envelope remaining untouched (100)

    adapter = MockBrokerAdapter()
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=80),  # valid against the envelope counter
        snapshot_fingerprint=FP,
        now=later(),
    )
    assert result.outcome == ENVELOPE_EXEC_DIVERGENCE
    assert adapter.submitted == [] and adapter.replaced == []
    divergences = await envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE
    )
    assert len(divergences) == 1
    assert divergences[0].payload["rail"] == "reduce_only"
    assert (await any_store.get_envelope(env.id)).status is S.FROZEN


async def test_redrive_recheck_catches_position_shrink(any_store):
    """WO-0026 at the redrive seam: staged valid against a full book, book
    shrinks while the order waits (transient release) — the redrive refuses
    and locally cancels; zero venue calls."""

    env = await active_envelope(any_store)
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
    assert released.outcome == ENVELOPE_EXEC_RELEASED

    session = await any_store.get_current_session()
    flat_cand = await any_store.create_candidate("AAPL", session_id=session.id)
    sell = await any_store.create_order_for_test(
        flat_cand.id, "AAPL", OrderSide.SELL, 95, session_id=session.id
    )
    await any_store.append_fill(
        sell.id, "AAPL", OrderSide.SELL, 95, 10.5, session_id=session.id
    )  # book: 100 -> 5

    fresh = MockBrokerAdapter()
    refused = await redrive_staged_envelope_action(
        any_store, fresh, env.id, now=later(60)
    )
    assert refused is not None and refused.outcome == ENVELOPE_EXEC_CANCELLED
    assert "reduce_only" in refused.detail
    assert fresh.submitted == [] and fresh.replaced == []
    assert (await any_store.get_order(refused.order_id)).status is OrderStatus.CANCELED


# --- staging: control precedence -------------------------------------------------- #


async def test_halted_blocks_staging_with_zero_artifacts(any_store):
    env = await active_envelope(any_store)
    await any_store.set_kill_switch(True, actor="operator-a")
    # The kill hook already froze the envelope; staging must refuse on the
    # control check (the envelope is no longer ACTIVE either — both gates
    # yield a refusal, never a venue call, never an artifact). ONLY the two
    # named refusal types count: anything else (KeyError, RuntimeError…) is a
    # crash-shaped bug, not a refusal (WO-0028/TC-04 — this was
    # `(OrderIntentBlockedError, Exception)`, which caught anything).
    from app.store.core import EnvelopeTransitionError

    with pytest.raises((OrderIntentBlockedError, EnvelopeTransitionError)):
        await any_store.stage_envelope_action(
            env.id, planned(), snapshot_fingerprint=FP, now=later()
        )
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
            env.id, planned(), snapshot_fingerprint=FP, now=later()
        )


# --- happy paths: submit + reprice through the venue ------------------------------ #


async def test_submit_leg_end_to_end(any_store):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    result = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
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
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    # Capture the working order's venue id BEFORE the reprice: the replace
    # MUST target exactly this order at the venue. (WO-0028/TC-01: this
    # assertion was `... or True` — a tautology; a replace aimed at the wrong
    # venue order survived the whole suite. Never suppress this again.)
    expected_target = (await any_store.get_order(first.order_id)).broker_order_id
    assert expected_target  # first submit produced a real venue id
    second = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(kind=ActionKind.REPRICE, limit_price=9.80),
        snapshot_fingerprint="fp-2",
        now=later(60),
    )
    assert second.outcome == ENVELOPE_EXEC_REPRICED
    # Venue: exactly one replace, aimed at the first order's broker id.
    assert len(adapter.replaced) == 1
    old_broker_id, client_id, limit, qty = adapter.replaced[0]
    assert old_broker_id == expected_target
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
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    adapter.fail_next_replace(AmbiguousBrokerError("504 mid-replace"))
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(kind=ActionKind.REPRICE, limit_price=9.80),
        snapshot_fingerprint="fp-2",
        now=later(45),
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
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    adapter.fail_next_replace(BrokerError("429 pre-flight"))
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(kind=ActionKind.REPRICE, limit_price=9.80),
        snapshot_fingerprint="fp-2",
        now=later(45),
    )
    assert result.outcome == ENVELOPE_EXEC_RELEASED
    released = await any_store.get_order(result.order_id)
    assert released.status is OrderStatus.CREATED  # held for redrive

    # Redrive completes the SAME staged action — no new ENVELOPE_ACTION event.
    # (Next tick's clock; WO-0024 gave redrive its own re-validation pass, so
    # it takes the injected clock like everything else on this seam.)
    redriven = await redrive_staged_envelope_action(
        any_store, adapter, env.id, now=later(60)
    )
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
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    order = await any_store.get_order(result.order_id)
    assert order.status is OrderStatus.REJECTED


async def test_kill_between_staging_and_venue_call_blocks_at_the_claim(any_store):
    """The REV-0020 last-await shape for the venue leg: the kill lands AFTER
    staging but BEFORE the venue call. WO-0024 changed the contract here: the
    kill hook now cancels the staged CREATED order in the SAME atomic unit as
    the envelope freeze (a staged order IS pending order intent, INV-060), so
    the redrive finds nothing pending — zero venue calls, and release gives
    the frozen envelope nothing to silently resubmit. (The OLD behavior —
    order held CREATED, then venue-submitted after release while the envelope
    was still FROZEN — was itself a variant of the staged-order finding.)"""

    env = await active_envelope(any_store)
    staged = await any_store.stage_envelope_action(
        env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    assert staged.order is not None
    await any_store.set_kill_switch(True, actor="operator-a")

    # The sweep already killed the staged order, atomically with the freeze.
    held = await any_store.get_order(staged.order.id)
    assert held.status is OrderStatus.CANCELED
    assert (await any_store.get_envelope(env.id)).status is S.FROZEN
    # Ordering: the envelope freeze sequences BEFORE the staged-order cancel
    # (the sweep runs after the freezes, inside the same atomic unit).
    events = await any_store.get_execution_events()
    frozen_seq = next(
        e.sequence
        for e in events
        if e.envelope_id == env.id
        and e.event_type is ExecutionEventType.ENVELOPE_FROZEN
    )
    cancel_seq = next(
        e.sequence
        for e in events
        if e.order_id == staged.order.id and e.event_type is ExecutionEventType.CANCELED
    )
    assert frozen_seq < cancel_seq

    adapter = MockBrokerAdapter()
    redriven = await redrive_staged_envelope_action(
        any_store, adapter, env.id, now=later(60)
    )
    assert redriven is None  # nothing pending to drive
    assert adapter.submitted == [] and adapter.replaced == []

    # Release: never auto-resumes, and there is NOTHING staged left to leak
    # to the venue while the envelope awaits its human.
    await any_store.set_kill_switch(False, actor="operator-a")
    assert (await any_store.get_envelope(env.id)).status is S.FROZEN
    done = await redrive_staged_envelope_action(
        any_store, adapter, env.id, now=later(90)
    )
    assert done is None
    assert adapter.submitted == [] and adapter.replaced == []


async def test_redrive_of_a_frozen_envelopes_staged_order_cancels_locally(any_store):
    """WO-0024 belt #1 (the original FINDING scope): an envelope that leaves
    ACTIVE by a path with NO sweep (a direct operator freeze) still cannot
    have its staged order driven — the redrive re-reads the envelope, refuses,
    and locally cancels with an event trail. Zero venue calls."""

    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    released = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    assert released.outcome == ENVELOPE_EXEC_RELEASED
    await any_store.transition_envelope(env.id, S.FROZEN, actor="operator-a")

    fresh = MockBrokerAdapter()
    refused = await redrive_staged_envelope_action(
        any_store, fresh, env.id, now=later(60)
    )
    assert refused is not None
    assert refused.outcome == ENVELOPE_EXEC_CANCELLED
    assert "frozen" in refused.detail
    assert fresh.submitted == [] and fresh.replaced == []
    cancelled = await any_store.get_order(refused.order_id)
    assert cancelled.status is OrderStatus.CANCELED
    # The cancel is event-logged (order-transition ExecutionEvent).
    events = await any_store.get_execution_events()
    assert any(
        e.order_id == refused.order_id and e.event_type is ExecutionEventType.CANCELED
        for e in events
    )


async def test_redrive_past_staleness_ceiling_cancels_locally(any_store):
    """WO-0024: a staged action older than the redrive ceiling is a STALE
    decision (crash-restart warm-up, freeze->resume stretch) — refused and
    locally cancelled; the policy re-decides from current data instead."""

    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    released = await execute_envelope_action(
        any_store, adapter, env.id, planned(), snapshot_fingerprint=FP, now=later()
    )
    assert released.outcome == ENVELOPE_EXEC_RELEASED

    fresh = MockBrokerAdapter()
    refused = await redrive_staged_envelope_action(
        any_store,
        fresh,
        env.id,
        now=later(30 + 121),  # past the 120s ceiling
    )
    assert refused is not None
    assert refused.outcome == ENVELOPE_EXEC_CANCELLED
    assert "old" in refused.detail
    assert fresh.submitted == [] and fresh.replaced == []
    assert (await any_store.get_order(refused.order_id)).status is OrderStatus.CANCELED
    # The envelope itself is untouched — staleness is not a defect.
    assert (await any_store.get_envelope(env.id)).status is S.ACTIVE
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
        await store.stage_envelope_action(
            env.id, planned(), snapshot_fingerprint=FP, now=later()
        )
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


# --- memory: same all-or-nothing guarantees (WO-0028 / TC-03) ---------------------- #
# The sqlite test above had no memory twin, which concealed a real defect:
# memory _atomic() did not snapshot _envelopes, so a crash between the envelope
# mutation and its event append left state and log disagreeing (H10 broken).
# FINDING-W3-memory-atomic-envelope-rollback.md. Each unit below injects a crash
# into the execution-event append and asserts FULL rollback.


def _explode_on(monkeypatch, event_type):
    from app.store.memory import InMemoryStateStore

    original = InMemoryStateStore._append_execution_event_unlocked

    def explode(self, event):
        if event.event_type is event_type:
            raise RuntimeError(f"injected crash on {event_type}")
        return original(self, event)

    monkeypatch.setattr(InMemoryStateStore, "_append_execution_event_unlocked", explode)
    return original


async def test_memory_envelope_transition_is_all_or_nothing(monkeypatch):
    from app.store.memory import InMemoryStateStore

    store = InMemoryStateStore()
    await store.initialize()
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    env = await store.create_envelope(make_draft(si.id))
    _explode_on(monkeypatch, ExecutionEventType.ENVELOPE_APPROVED)
    with pytest.raises(RuntimeError):
        await store.transition_envelope(env.id, S.APPROVED)

    # Envelope state rolled back WITH the log — replaying events must
    # reconstruct exactly what the store says (the log is the truth).
    assert (await store.get_envelope(env.id)).status is S.PENDING
    kinds = [e.event_type for e in await envelope_events(store, env.id)]
    assert kinds == [ExecutionEventType.ENVELOPE_CREATED]


async def test_memory_staging_is_all_or_nothing(monkeypatch):
    from app.store.memory import InMemoryStateStore

    store = InMemoryStateStore()
    env = await active_envelope(store)
    _explode_on(monkeypatch, ExecutionEventType.ENVELOPE_ACTION)
    with pytest.raises(RuntimeError):
        await store.stage_envelope_action(
            env.id, planned(), snapshot_fingerprint=FP, now=later()
        )

    orders = await store.list_orders()
    assert all(o.sell_intent_id != env.sell_intent_id for o in orders)
    assert (
        await envelope_events(store, env.id, ExecutionEventType.ENVELOPE_ACTION) == []
    )
    assert (await store.get_envelope(env.id)).status is S.ACTIVE


async def test_memory_envelope_fill_is_all_or_nothing_and_dedupe_unpoisoned(
    monkeypatch,
):
    from app.store.memory import InMemoryStateStore

    store = InMemoryStateStore()
    env = await active_envelope(store)
    original = _explode_on(monkeypatch, ExecutionEventType.FILL)
    with pytest.raises(RuntimeError):
        await store.record_envelope_fill(env.id, quantity=30, dedupe_key="fill:o1:1")

    after_crash = await store.get_envelope(env.id)
    assert after_crash.remaining_quantity == 100  # decrement rolled back
    assert await envelope_events(store, env.id, ExecutionEventType.FILL) == []

    # The dedupe index rolled back too: the SAME key applies cleanly once.
    monkeypatch.setattr(
        InMemoryStateStore, "_append_execution_event_unlocked", original
    )
    retried = await store.record_envelope_fill(
        env.id, quantity=30, dedupe_key="fill:o1:1"
    )
    assert retried.remaining_quantity == 70
    assert len(await envelope_events(store, env.id, ExecutionEventType.FILL)) == 1


async def test_memory_supersede_is_all_or_nothing(monkeypatch):
    from app.store.memory import InMemoryStateStore

    store = InMemoryStateStore()
    env = await active_envelope(store)
    successor = make_draft(env.sell_intent_id)
    _explode_on(monkeypatch, ExecutionEventType.ENVELOPE_SUPERSEDED)
    with pytest.raises(RuntimeError):
        await store.supersede_envelope(env.id, successor, actor="operator-a")

    assert (await store.get_envelope(env.id)).status is S.ACTIVE
    assert await store.get_envelope(successor.id) is None  # successor rolled back
    kinds = {e.event_type for e in await envelope_events(store, env.id)}
    assert ExecutionEventType.ENVELOPE_SUPERSEDED not in kinds


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
