"""REV-0022 Phase A — findings pinned as strict xfails + held probes promoted.

Every OPEN Phase A finding gets an ``xfail(strict=True)`` pin asserting the
DESIRED behavior: the pin fails today (that's the finding), and the moment a
remediation WO lands the fix, the pin XPASSes loudly and gets flipped to a
plain test in that WO. Nothing here fixes anything (WO-0022 charter).

Pin → finding → remediation map:
  PIN_F1_*  → FINDING-W3-reduce-only-unenforced.md            → WO-0026
  PIN_F3_*  → FINDING-W3-redrive-revalidation-bypass.md       → WO-0024 (amended)
  PIN_F4_*  → FINDING-W3-multileg-false-divergence-livelock.md → WO-0025
  PIN_F5_*  → FINDING-W3-synthetic-fill-envelope-bypass.md    → WO-0025
  PIN_F6_*  → FINDING-W3-supersession-exposure.md             → WO-0027

The HELD_* tests promote the interleaving-attacker's green probes into the
permanent suite: they pinned the interleavings that HELD at review time and
must keep holding (triple races, dedupe storms, single-claim redrive...).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    SellReason,
    SessionType,
)
from app.reconciliation import (
    ENVELOPE_EXEC_DIVERGENCE,
    ENVELOPE_EXEC_RELEASED,
    ENVELOPE_EXEC_SUBMITTED,
    execute_envelope_action,
    redrive_staged_envelope_action,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import OrderIntentBlockedError
from app.store.core import EnvelopeTransitionError

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
FP = "fp-rev0022-0001"

# Deterministic decision clock (Wed 2026-07-15 14:00 UTC = 10:00 ET REGULAR) —
# validate_action rails on TTL + session phase since WO-0024, so wall-clock
# nows would spuriously rail on weekends/out-of-hours containers.
T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def later(seconds: int = 30):
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


async def active_envelope(
    store, *, seed_position: bool = True, **overrides
) -> ExecutionEnvelope:
    await store.initialize()
    # WO-0026: staging now rails on the live position (reduce-only), so a
    # realistic envelope test holds the shares it is mandated to sell.
    if seed_position:
        await _seed_position(store, 100)
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return await store.approve_envelope_activation(
        make_draft(si.id, **overrides), actor="operator-a"
    )


async def _seed_position(store, quantity: int = 100):
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, quantity, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, quantity, 10.0, session_id=session.id
    )


async def _envelope_events(store, envelope_id, event_type=None):
    return [
        e
        for e in await store.get_execution_events()
        if e.envelope_id == envelope_id
        and (event_type is None or e.event_type is event_type)
    ]


# ================================================================== #
# F1 — reduce-only — FLIPPED GREEN by WO-0026
# ================================================================== #


async def test_PIN_F1_sell_against_zero_position_never_reaches_venue(any_store):
    # FLIPPED GREEN by WO-0026 (reduce-only write-time rail).
    env = await active_envelope(any_store, seed_position=False)  # flat book
    adapter = MockBrokerAdapter()
    result = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=10),
        snapshot_fingerprint=FP,
        now=later(),
    )
    assert adapter.submitted == [], (
        "reduce-only is a HARD rail: a SELL with no position must refuse "
        "before the venue call"
    )
    assert result.outcome == ENVELOPE_EXEC_DIVERGENCE
    assert (await any_store.get_envelope(env.id)).status is S.FROZEN


# ================================================================== #
# F3 — redrive re-validation bypass — FLIPPED GREEN by WO-0024
# ================================================================== #


async def test_PIN_F3_redrive_respects_current_remaining(any_store):
    # FLIPPED GREEN by WO-0024 (redrive re-validation): the raced fill shrinks
    # remaining below the staged qty; redrive must refuse + locally cancel.
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

    after_fill = await any_store.record_envelope_fill(
        env.id, quantity=60, dedupe_key="fill:oW:exec1", order_id="oW", price=9.95
    )
    assert after_fill.remaining_quantity == 40
    assert after_fill.status is S.ACTIVE  # a status-only guard would NOT stop this

    fresh = MockBrokerAdapter()
    refused = await redrive_staged_envelope_action(
        any_store, fresh, env.id, now=later(60)
    )
    assert fresh.submitted == [] and fresh.replaced == []
    assert refused is not None and refused.outcome == "cancelled"
    assert (await any_store.get_order(refused.order_id)).status is OrderStatus.CANCELED
    # The envelope is untouched (a raced fill is not a defect) and its
    # remaining reflects only the fill.
    final = await any_store.get_envelope(env.id)
    assert final.status is S.ACTIVE and final.remaining_quantity == 40


async def test_PIN_F3_redrive_gather_variant_fill_racing_redrive(any_store):
    # FLIPPED GREEN by WO-0024.
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=80),
        snapshot_fingerprint=FP,
        now=later(),
    )
    fresh = MockBrokerAdapter()

    async def fill():
        return await any_store.record_envelope_fill(
            env.id, quantity=60, dedupe_key="fill:oW:g1", order_id="oW", price=9.95
        )

    async def redrive():
        await asyncio.sleep(0)  # let the fill take the lock first
        return await redrive_staged_envelope_action(
            any_store, fresh, env.id, now=later(60)
        )

    await asyncio.gather(fill(), redrive())
    final = await any_store.get_envelope(env.id)
    submitted_qty = [o.quantity for o in fresh.submitted]
    assert submitted_qty == [] or max(submitted_qty) <= (final.remaining_quantity or 0)


async def test_PIN_F3_redrive_after_ttl_makes_no_venue_call(any_store):
    # FLIPPED GREEN by WO-0024: TTL is now a validate_action rail, re-checked
    # at redrive with the injected clock (no wall-clock sleep needed).
    env = await active_envelope(any_store, expires_at=T_NOW + timedelta(seconds=60))
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    released = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=10),
        snapshot_fingerprint=FP,
        now=later(1),
    )
    assert released.outcome == ENVELOPE_EXEC_RELEASED

    fresh = MockBrokerAdapter()
    refused = await redrive_staged_envelope_action(
        any_store,
        fresh,
        env.id,
        now=later(90),  # past the 60s TTL
    )
    assert fresh.submitted == [] and fresh.replaced == [], (
        "an EXPIRED mandate's staged order reached the venue via redrive"
    )
    assert refused is not None and refused.outcome == "cancelled"
    assert "ttl" in refused.detail


# ================================================================== #
# F4 — multi-leg false-divergence livelock — FLIPPED GREEN by WO-0025
# ================================================================== #


async def test_PIN_F4_second_leg_after_full_fill_never_false_divergence(any_store):
    # FLIPPED GREEN by WO-0025: the working-order predicate is live-derived
    # (dead orders are not repriced). Full decide→stage integration lives in
    # tests/test_wo0025_multileg.py; this pin keeps the original repro shape.
    from app.sellside.policy import _live_working_order_id, _own_actions

    env = await active_envelope(any_store, cooldown_floor_ms=1)
    adapter = MockBrokerAdapter()

    # Leg 1: 50-share tranche, submitted then FULLY filled via the correct
    # stream-bridge sequence (record-first, then position fold, then terminal).
    r1 = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=50),
        snapshot_fingerprint=FP,
        now=later(),
    )
    assert r1.outcome == ENVELOPE_EXEC_SUBMITTED
    await any_store.record_envelope_fill(
        env.id,
        quantity=50,
        dedupe_key=f"fill:{r1.order_id}:x1",
        order_id=r1.order_id,
        price=9.90,
    )
    await any_store.append_fill(
        r1.order_id, "AAPL", OrderSide.SELL, 50, 9.90, source_fill_id="x1"
    )
    await any_store.transition_order(
        r1.order_id, OrderStatus.FILLED, filled_quantity=50
    )
    env2 = await any_store.get_envelope(env.id)
    assert env2.status is S.ACTIVE and env2.remaining_quantity == 50

    # Leg 2, with the kind selected THE WAY decide() selects it (history-based;
    # policy.py flips to REPRICE once any submit has EVER happened).
    events = await any_store.get_execution_events()
    has_working = (
        _live_working_order_id(_own_actions(env2, events), events) is not None
    )
    assert not has_working  # the filled first order is DEAD, not "working"
    kind = ActionKind.REPRICE if has_working else ActionKind.SUBMIT
    r2 = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(kind=kind, quantity=25),
        snapshot_fingerprint="fp-2",
        now=later(60),
    )
    env3 = await any_store.get_envelope(env.id)
    divergences = await _envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_PLAN_DIVERGENCE
    )
    assert r2.outcome != ENVELOPE_EXEC_DIVERGENCE, (
        "second leg of a healthy multi-order envelope tripped the "
        "software-defect tripwire"
    )
    assert env3.status is not S.FROZEN
    assert divergences == []


# ================================================================== #
# F5 — synthetic-fill envelope bypass — FLIPPED GREEN by WO-0025
# ================================================================== #


async def test_PIN_F5_inferred_fill_decrements_envelope_remaining(any_store):
    env = await active_envelope(any_store)
    await _seed_position(any_store, 100)
    adapter = MockBrokerAdapter()
    r1 = await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=100),
        snapshot_fingerprint=FP,
        now=later(),
    )
    assert r1.outcome == ENVELOPE_EXEC_SUBMITTED

    # FLIPPED GREEN by WO-0025: the venue filled it but the stream missed
    # it; reconcile's REAL bridge (monitoring._apply_inferred_fills) now
    # routes envelope-minted orders through record_envelope_fill first.
    from types import SimpleNamespace

    import app.monitoring as monitoring
    from app.reconciliation import InferredFill

    plan = SimpleNamespace(
        inferred_fills=[
            InferredFill(
                order_id=r1.order_id,
                symbol="AAPL",
                side=OrderSide.SELL,
                quantity=100,
                price=9.90,
                source_fill_id="venue-exec-1",
            )
        ]
    )
    await monitoring._apply_inferred_fills(any_store, plan)
    await any_store.transition_order(
        r1.order_id, OrderStatus.FILLED, filled_quantity=100
    )
    env2 = await any_store.get_envelope(env.id)
    assert env2.remaining_quantity == 0, (
        f"envelope never learned about the inferred fill: remaining="
        f"{env2.remaining_quantity} (ceiling={env2.qty_ceiling}) — the mandate "
        f"re-armed and a second full-size SELL would pass both D-3 rails"
    )


# ================================================================== #
# F6 — supersession exposure (P1-latent, SPEC-02/INT-002) → WO-0027
# ================================================================== #


@pytest.mark.xfail(
    strict=True,
    reason="FINDING-W3-supersession-exposure (REV-0022 F6): successor resets "
    "remaining to its full ceiling; a racing fill's decrement is erased. "
    "WO-0027.",
)
async def test_PIN_F6_supersede_conserves_remaining_fill_first(any_store):
    env = await active_envelope(any_store)
    await _seed_position(any_store)

    async def fill():
        return await any_store.record_envelope_fill(
            env.id, quantity=40, dedupe_key="fill:oA:s1", order_id="oA", price=9.9
        )

    successor = make_draft(env.sell_intent_id, qty_ceiling=100)

    async def supersede():
        await asyncio.sleep(0)  # fill wins the lock
        return await any_store.supersede_envelope(
            env.id, successor, actor="operator-a", reason="amendment"
        )

    filled, new_env = await asyncio.gather(fill(), supersede())
    assert filled.remaining_quantity == 60
    stored = await any_store.get_envelope(new_env.id)
    assert (stored.remaining_quantity or 0) <= 60, (
        f"successor ACTIVE with remaining={stored.remaining_quantity} while "
        f"only 60 shares remain unsold (fill decrement erased by supersession)"
    )


async def test_PIN_F6_supersede_first_late_fill_venue_followthrough(any_store):
    # FLIPPED GREEN by WO-0026, not WO-0027: envelope-attributed FILL events
    # fold into the position projection, so the reduce-only rail blocks THIS
    # repro's venue leg (fills 40 + submit 100 > position). The supersession
    # RESET defect itself is still open — pinned by
    # test_PIN_F6_supersede_conserves_remaining_fill_first above (WO-0027).
    env = await active_envelope(any_store)  # helper seeds the 100-share book
    successor = make_draft(env.sell_intent_id, qty_ceiling=100)

    async def supersede():
        return await any_store.supersede_envelope(
            env.id, successor, actor="operator-a", reason="amendment"
        )

    async def fill():
        await asyncio.sleep(0)
        return await any_store.record_envelope_fill(
            env.id, quantity=40, dedupe_key="fill:oA:s2", order_id="oA", price=9.9
        )

    new_env, _ = await asyncio.gather(supersede(), fill())
    adapter = MockBrokerAdapter()
    result = await execute_envelope_action(
        any_store,
        adapter,
        new_env.id,
        planned(quantity=100),
        snapshot_fingerprint=FP,
        now=later(),
    )
    total_mandated = 40 + sum(o.quantity for o in adapter.submitted)
    assert result.outcome != ENVELOPE_EXEC_SUBMITTED or total_mandated <= 100


# ================================================================== #
# HELD probes, promoted — these were GREEN at review time and pin the
# interleavings that must KEEP holding.
# ================================================================== #


async def test_HELD_kill_vs_approve_vs_supersede_triple(any_store):
    """gather(kill, approve(new draft same intent), supersede(old)): end state
    must never be an ACTIVE envelope under HALTED, or two ACTIVE per intent."""

    env = await active_envelope(any_store)
    draft_b = make_draft(env.sell_intent_id)
    successor = make_draft(env.sell_intent_id)

    async def kill():
        return await any_store.set_kill_switch(True, actor="op")

    async def approve():
        try:
            return await any_store.approve_envelope_activation(draft_b, actor="op")
        except (OrderIntentBlockedError, EnvelopeTransitionError) as e:
            return e

    async def supersede():
        try:
            return await any_store.supersede_envelope(env.id, successor, actor="op")
        except (OrderIntentBlockedError, EnvelopeTransitionError) as e:
            return e

    await asyncio.gather(kill(), approve(), supersede())
    assert (await any_store.get_current_session()).kill_switch
    actives = await any_store.list_envelopes(
        sell_intent_id=env.sell_intent_id, status=S.ACTIVE
    )
    assert actives == []


async def test_HELD_concurrent_double_stage_single_venue_order(any_store):
    env = await active_envelope(any_store)
    a1, a2 = MockBrokerAdapter(), MockBrokerAdapter()

    async def exec_one(adapter, now):
        try:
            return await execute_envelope_action(
                any_store,
                adapter,
                env.id,
                planned(quantity=10),
                snapshot_fingerprint=FP,
                now=now,
            )
        except (OrderIntentBlockedError, EnvelopeTransitionError) as e:
            return e

    await asyncio.gather(exec_one(a1, later()), exec_one(a2, later(60)))
    assert len(a1.submitted) + len(a2.submitted) <= 1


async def test_HELD_duplicate_fill_gather_exactly_once(any_store):
    env = await active_envelope(any_store)

    async def fill():
        return await any_store.record_envelope_fill(
            env.id, quantity=30, dedupe_key="fill:oX:dup", order_id="oX", price=9.9
        )

    await asyncio.gather(fill(), fill())
    assert (await any_store.get_envelope(env.id)).remaining_quantity == 70


async def test_HELD_concurrent_overfill_breaches_never_negative(any_store):
    env = await active_envelope(any_store)

    async def f(k, q):
        return await any_store.record_envelope_fill(
            env.id, quantity=q, dedupe_key=f"fill:o:{k}", order_id="o", price=9.9
        )

    await asyncio.gather(f("a", 70), f("b", 70))
    final = await any_store.get_envelope(env.id)
    assert (final.remaining_quantity or 0) >= 0
    assert final.status is S.BREACHED


async def test_HELD_fill_vs_cancel_transition(any_store):
    env = await active_envelope(any_store)

    async def fill():
        return await any_store.record_envelope_fill(
            env.id, quantity=25, dedupe_key="fill:o:late", order_id="o", price=9.9
        )

    async def freeze_cancel():
        await any_store.transition_envelope(env.id, S.FROZEN, actor="op")
        return await any_store.transition_envelope(env.id, S.CANCELLED, actor="op")

    await asyncio.gather(fill(), freeze_cancel())
    final = await any_store.get_envelope(env.id)
    assert final.status is S.CANCELLED
    fills = await _envelope_events(any_store, env.id, ExecutionEventType.FILL)
    assert len(fills) == 1 and final.remaining_quantity == 75


async def test_HELD_freeze_fill_to_zero_resume_storm(any_store):
    env = await active_envelope(any_store)
    await any_store.transition_envelope(env.id, S.FROZEN, actor="op")
    frozen = await any_store.record_envelope_fill(
        env.id, quantity=100, dedupe_key="fill:o:all", order_id="o", price=9.9
    )
    assert frozen.status is S.FROZEN and frozen.remaining_quantity == 0

    async def resume():
        try:
            return await any_store.transition_envelope(env.id, S.ACTIVE, actor="op")
        except EnvelopeTransitionError as e:
            return e

    await asyncio.gather(resume(), resume())
    final = await any_store.get_envelope(env.id)
    assert final.status is S.COMPLETED
    completed = await _envelope_events(
        any_store, env.id, ExecutionEventType.ENVELOPE_COMPLETED
    )
    assert len(completed) == 1


async def test_HELD_redrive_vs_redrive_single_claim(any_store):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=10),
        snapshot_fingerprint=FP,
        now=later(),
    )
    a1, a2 = MockBrokerAdapter(), MockBrokerAdapter()
    await asyncio.gather(
        redrive_staged_envelope_action(any_store, a1, env.id),
        redrive_staged_envelope_action(any_store, a2, env.id),
    )
    assert len(a1.submitted) + len(a2.submitted) <= 1


async def test_HELD_kill_between_staging_and_redrive_blocks_at_claim(any_store):
    env = await active_envelope(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("transient"))
    await execute_envelope_action(
        any_store,
        adapter,
        env.id,
        planned(quantity=10),
        snapshot_fingerprint=FP,
        now=later(),
    )
    await any_store.set_kill_switch(True, actor="op")
    fresh = MockBrokerAdapter()
    await redrive_staged_envelope_action(any_store, fresh, env.id)
    assert fresh.submitted == [] and fresh.replaced == []
