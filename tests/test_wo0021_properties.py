"""WO-0021 — wave-level properties over the assembled envelope stack.

1. NO reachable action sequence produces a venue call that violates a hard
   rail (arbitrary valid/invalid PlannedActions driven through the real
   stage→claim→venue pipeline against the stub broker).
2. Replaying the event log reconstructs the envelope's state (status +
   remaining) — the log IS the truth (ADR-009 §6 replayability).
3. Memory and sqlite stores agree on final state for arbitrary generated
   scenarios (the parity mandate).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import (
    HealthCheck,
    example,
    given,
    settings as hyp_settings,
    strategies as st,
)

from app.broker.mock import MockBrokerAdapter
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    ExecutionEventType,
    SellReason,
)
from app.reconciliation import execute_envelope_action
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import OrderIntentBlockedError
from app.store.core import EnvelopeActionPausedError, EnvelopeTransitionError
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

S = EnvelopeStatus
T0 = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def make_draft(intent_id: str, ceiling: int = 100) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=ceiling,
        floor_price=8.00,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.5,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=4,
        expires_at=T0 + timedelta(days=2),
        allowed_session_phases=["pre_market", "regular", "after_hours"],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )


def action(kind, limit, qty) -> PlannedAction:
    return PlannedAction(
        kind=kind,
        limit_price=limit,
        quantity=qty,
        regime=None,
        urgency=0.0,
        working_stop=None,
        atr=None,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


ACTION_STRATEGY = st.tuples(
    st.sampled_from([ActionKind.SUBMIT, ActionKind.REPRICE]),
    st.floats(min_value=1.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    st.integers(min_value=-5, max_value=150),
)


async def _drive_script(store, script):
    """Drive one action script through the REAL pipeline; return the adapter."""

    await store.initialize()
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    env = await store.approve_envelope_activation(make_draft(si.id), actor="operator-a")
    adapter = MockBrokerAdapter()
    now = T0
    for i, (kind, limit, qty) in enumerate(script):
        now = now + timedelta(seconds=10)
        if qty <= 0:
            continue  # unconstructible PlannedAction quantities are the
            # policy's own problem; the pipeline only sees real actions
        try:
            await execute_envelope_action(
                store,
                adapter,
                env.id,
                action(kind, round(limit, 2), qty),
                snapshot_fingerprint=f"fp-{i}",
                now=now,
            )
        except (
            EnvelopeTransitionError,
            EnvelopeActionPausedError,
            OrderIntentBlockedError,
        ):
            break  # refused/frozen — no further actions reachable
    return env, adapter


@given(script=st.lists(ACTION_STRATEGY, min_size=1, max_size=6))
# WO-0028/TC-06: the random strategy essentially never produces the exact
# all-valid [SUBMIT, REPRICE×5] drain that reaches the budget edge (an
# off-by-one in the budget rail survived 3/3 full runs), so the edge is
# pinned as an explicit directed example — hypothesis always runs it.
@example(
    script=[
        (ActionKind.SUBMIT, 9.90, 10),
        (ActionKind.REPRICE, 9.80, 10),
        (ActionKind.REPRICE, 9.70, 10),
        (ActionKind.REPRICE, 9.60, 10),
        (ActionKind.REPRICE, 9.50, 10),
        (ActionKind.REPRICE, 9.40, 10),
    ]
)
@hyp_settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
async def test_no_reachable_sequence_makes_a_rail_violating_venue_call(script):
    store = InMemoryStateStore()
    env, adapter = await _drive_script(store, script)
    # EVERY venue call that happened respected every hard rail.
    for order in adapter.submitted:
        assert order.limit_price >= 8.00  # floor
        assert 0 < order.quantity <= 100  # qty ceiling
    for _, _, limit, qty in adapter.replaced:
        if limit is not None:
            assert limit >= 8.00
        if qty is not None:
            assert 0 < qty <= 100
    replace_calls = len(adapter.replaced)
    assert replace_calls <= 4  # lifetime budget is a hard rail


def _replay_envelope(events, envelope_id, ceiling):
    """Fold ONLY the event log back into (status, remaining) — written here,
    independently of the stores, so the test is an oracle, not an echo."""

    status = None
    remaining = ceiling
    for e in sorted(events, key=lambda e: e.sequence):
        if e.envelope_id != envelope_id:
            continue
        t = e.event_type
        if t is ExecutionEventType.ENVELOPE_CREATED:
            status = S.PENDING
        elif t is ExecutionEventType.ENVELOPE_APPROVED:
            status = S.APPROVED
        elif t in (
            ExecutionEventType.ENVELOPE_ACTIVATED,
            ExecutionEventType.ENVELOPE_RESUMED,
        ):
            status = S.ACTIVE
        elif t is ExecutionEventType.ENVELOPE_FROZEN:
            status = S.FROZEN
        elif t is ExecutionEventType.ENVELOPE_COMPLETED:
            status = S.COMPLETED
        elif t is ExecutionEventType.ENVELOPE_EXPIRED:
            status = S.EXPIRED
        elif t is ExecutionEventType.ENVELOPE_EXHAUSTED:
            status = S.EXHAUSTED
        elif t is ExecutionEventType.ENVELOPE_BREACHED:
            status = S.BREACHED
        elif t is ExecutionEventType.ENVELOPE_SUPERSEDED:
            status = S.SUPERSEDED
        elif t is ExecutionEventType.ENVELOPE_CANCELLED:
            status = S.CANCELLED
        elif t is ExecutionEventType.FILL and e.quantity:
            remaining = max(0, remaining - e.quantity)
    return status, remaining


LIFECYCLE_STEP = st.sampled_from(
    ["approve_activate", "freeze", "resume", "fill_30", "fill_120", "cancel"]
)


@given(steps=st.lists(LIFECYCLE_STEP, min_size=1, max_size=8))
@hyp_settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
async def test_event_log_replay_reconstructs_envelope_state(steps):
    store = InMemoryStateStore()
    await store.initialize()
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    draft = make_draft(si.id)
    env = await store.create_envelope(draft)
    fills = 0
    for step in steps:
        try:
            if step == "approve_activate":
                await store.approve_envelope_activation(draft, actor="op")
            elif step == "freeze":
                await store.transition_envelope(env.id, S.FROZEN)
            elif step == "resume":
                await store.transition_envelope(env.id, S.ACTIVE)
            elif step.startswith("fill_"):
                fills += 1
                await store.record_envelope_fill(
                    env.id,
                    quantity=int(step.split("_")[1]),
                    dedupe_key=f"fill:p:{fills}",
                )
            elif step == "cancel":
                await store.transition_envelope(env.id, S.CANCELLED)
        except Exception:  # noqa: BLE001 — illegal steps are part of the walk
            continue

    stored = await store.get_envelope(env.id)
    events = await store.get_execution_events()
    replayed_status, replayed_remaining = _replay_envelope(
        events, env.id, draft.qty_ceiling
    )
    assert replayed_status is stored.status
    assert replayed_remaining == stored.remaining_quantity


@given(
    script=st.lists(ACTION_STRATEGY, min_size=1, max_size=5),
    data=st.data(),
)
@hyp_settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
async def test_memory_and_sqlite_agree_on_final_state(tmp_path_factory, script, data):
    mem = InMemoryStateStore()
    sql = SqliteStateStore(
        tmp_path_factory.mktemp("parity") / f"p{data.draw(st.integers(0, 10**9))}.db"
    )
    env_mem, adapter_mem = await _drive_script(mem, script)
    env_sql, adapter_sql = await _drive_script(sql, script)

    m = await mem.get_envelope(env_mem.id)
    s = await sql.get_envelope(env_sql.id)
    assert m.status is s.status
    assert m.remaining_quantity == s.remaining_quantity
    mem_kinds = [
        e.event_type
        for e in await mem.get_execution_events()
        if e.envelope_id == env_mem.id
    ]
    sql_kinds = [
        e.event_type
        for e in await sql.get_execution_events()
        if e.envelope_id == env_sql.id
    ]
    assert mem_kinds == sql_kinds
    assert len(adapter_mem.submitted) == len(adapter_sql.submitted)
    assert len(adapter_mem.replaced) == len(adapter_sql.replaced)
    if sql._conn is not None:
        sql._conn.close()
        sql._conn = None
