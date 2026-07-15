"""WO-0033 — REV-0023 Phase-A2 non-gated cleanup batch (regression tests).

RED→GREEN: each test fails on the pre-fix code and passes after the fix (these
are ordinary regressions, not the review's strict-xfail pins).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.broker.mock import MockBrokerAdapter
from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    ExecutionEnvelope,
    OrderSide,
    SellReason,
    SessionType,
)

pytestmark = pytest.mark.anyio

T_NOW = datetime(2026, 7, 15, 14, 0, 0, tzinfo=timezone.utc)


def _draft(intent_id: str, **overrides) -> ExecutionEnvelope:
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


async def _seed_position(store, quantity: int = 100):
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, quantity, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, quantity, 10.0, session_id=session.id
    )


async def _active_envelope(store):
    await store.initialize()
    await _seed_position(store, 100)
    si = await store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    return await store.approve_envelope_activation(_draft(si.id), actor="op")


# ------------------------------------------------------------------------- #
# parity-0 (P1) — the tick must forward its injected clock to the redrive
# re-validation; a bare wall-clock fallback breaks determinism (H11).
# ------------------------------------------------------------------------- #
async def test_parity0_tick_forwards_injected_clock_to_redrive(any_store):
    from app.monitoring import EnvelopeTapeBuffer, _run_one_envelope

    env = await _active_envelope(any_store)
    market_data = AsyncMock()
    market_data.get_snapshot = AsyncMock(
        return_value=None
    )  # empty tape -> decide holds
    tick_now = T_NOW + timedelta(minutes=5)

    with patch(
        "app.monitoring.redrive_staged_envelope_action",
        new=AsyncMock(return_value=None),
    ) as redrive:
        await _run_one_envelope(
            any_store,
            MockBrokerAdapter(),
            market_data,
            env,
            tapes=EnvelopeTapeBuffer(),
            snap_memo={},
            now=tick_now,
        )

    assert redrive.await_count == 1
    # The injected tick clock MUST be forwarded (else redrive re-validates
    # TTL/session-phase/reduce-only against a bare utcnow()).
    assert redrive.await_args.kwargs.get("now") == tick_now, (
        "redrive_staged_envelope_action was called without now=now — its "
        "re-validation would run on wall-clock time, not the tick's clock"
    )


# ------------------------------------------------------------------------- #
# parity-1 (P2) — staging against an UNKNOWN envelope id must not have a
# session side-effect. sqlite ensured the current session (own committed tx)
# BEFORE the envelope lookup, so on a date rollover it leaked a new session row
# + session_opened event that memory never wrote (dual-store divergence, H10).
# ------------------------------------------------------------------------- #
def _planned():
    from app.sellside.types import ActionKind, PlannedAction

    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=10,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
        clamps=(),
    )


async def test_parity1_stage_unknown_envelope_has_no_session_side_effect(any_store):
    from app.store.base import UnknownEntityError

    day_n = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
    day_n1 = day_n + timedelta(days=1)

    # Both stores read the session date via their module-local ``utcnow``.
    with (
        patch("app.store.sqlite.utcnow", return_value=day_n),
        patch("app.store.memory.utcnow", return_value=day_n),
    ):
        await any_store.initialize()
        before = len(await any_store.list_sessions())

    # Date rolls to N+1, then a stage against a NON-EXISTENT envelope arrives.
    with (
        patch("app.store.sqlite.utcnow", return_value=day_n1),
        patch("app.store.memory.utcnow", return_value=day_n1),
    ):
        with pytest.raises(UnknownEntityError):
            await any_store.stage_envelope_action(
                "nonexistent-id", _planned(), snapshot_fingerprint="fp"
            )
        after = len(await any_store.list_sessions())

    # A failed (unknown-id) stage must not persist a session — validate the
    # entity BEFORE any session-ensure side-effect, identically in both stores.
    assert after == before, (
        f"stage against an unknown envelope leaked a session row "
        f"({before} -> {after}) — session-ensure ran before the envelope check"
    )


# ------------------------------------------------------------------------- #
# mutation-0 (P1) — the WO-0025 own_order_ids union in _run_one_envelope
# (so the policy's working-order predicate SEES an order's FILLED/CANCELED/
# REJECTED terminal, which carries order_id but NOT envelope_id) had no killing
# test: a mutant reverting it to `envelope_id == env.id` only stayed green. This
# drives the real assembly and asserts the terminal reaches decide()'s history.
# ------------------------------------------------------------------------- #
async def test_mutation0_run_one_envelope_history_includes_order_terminals(any_store):
    from app.models import (
        EventAuthority,
        EventSource,
        ExecutionEvent,
        ExecutionEventType,
    )
    from app.monitoring import EnvelopeTapeBuffer, _run_one_envelope
    from app.sellside.types import NoAction, NoActionReason

    env = await _active_envelope(any_store)

    # A staged action for order oW (envelope_id set, carries order_id)...
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.ENVELOPE_ACTION,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            ts_event=T_NOW - timedelta(seconds=90),
            symbol=env.symbol,
            order_id="oW",
            envelope_id=env.id,
            payload={"action": "submit", "quantity": 10},
        )
    )
    # ...then oW's REJECTED terminal — order_id set, envelope_id NONE (the exact
    # shape the union exists to recover; a naive envelope_id filter drops it).
    await any_store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.REJECTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            ts_event=T_NOW - timedelta(seconds=60),
            symbol=env.symbol,
            order_id="oW",
            envelope_id=None,
            payload={},
        )
    )

    captured: dict = {}

    def _capture_decide(envelope, snapshots, *, now, history):
        captured["history"] = list(history)
        return NoAction(reason=NoActionReason.MONITORING)

    market_data = AsyncMock()
    market_data.get_snapshot = AsyncMock(return_value=None)
    with (
        patch("app.monitoring.decide", side_effect=_capture_decide),
        patch(
            "app.monitoring.redrive_staged_envelope_action",
            new=AsyncMock(return_value=None),
        ),
    ):
        await _run_one_envelope(
            any_store,
            MockBrokerAdapter(),
            market_data,
            env,
            tapes=EnvelopeTapeBuffer(),
            snap_memo={},
            now=T_NOW,
        )

    hist = captured.get("history", [])
    assert any(
        e.order_id == "oW"
        and e.envelope_id is None
        and e.event_type is ExecutionEventType.REJECTED
        for e in hist
    ), (
        "the order's REJECTED terminal (order_id set, envelope_id=None) was NOT "
        "forwarded to the policy — the WO-0025 own_order_ids union is not wired, "
        "so the working-order predicate can't see the order died"
    )


# ------------------------------------------------------------------------- #
# completeness-1 (P1/P2, deferred→completed) — a fill's price is REQUIRED and
# value-guarded at the planner. A price=None FILL event used to append durably
# and then permanently poison project_symbol_position for the symbol
# (ProjectionError on every later get_position/close_session). Root form: the
# signature no longer admits None (deferred-log planning item), and a
# non-finite/non-positive price rejects exactly like plan_append_fill (D-019
# shared guard), with nothing written.
# ------------------------------------------------------------------------- #
async def test_completeness1_envelope_fill_price_is_required(any_store):
    env = await _active_envelope(any_store)
    with pytest.raises(TypeError):
        await any_store.record_envelope_fill(  # type: ignore[call-arg]
            env.id, quantity=10, dedupe_key="fill:o1:nopx"
        )
    # nothing written: remaining untouched, position projection healthy
    assert (await any_store.get_envelope(env.id)).remaining_quantity == 100
    assert (await any_store.get_position("AAPL")).quantity == 100


@pytest.mark.parametrize("bad_price", [0.0, -1.5, float("nan"), float("inf")])
async def test_completeness1_envelope_fill_rejects_invalid_price(any_store, bad_price):
    from app.store.base import InvalidFillError

    env = await _active_envelope(any_store)
    with pytest.raises(InvalidFillError):
        await any_store.record_envelope_fill(
            env.id, quantity=10, dedupe_key="fill:o1:badpx", price=bad_price
        )
    assert (await any_store.get_envelope(env.id)).remaining_quantity == 100
    # the poison never lands: projection still folds cleanly
    assert (await any_store.get_position("AAPL")).quantity == 100
