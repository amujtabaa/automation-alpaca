"""WO-0007a Stage 2 — routine `transition_order`-driven ExecutionEvent emission.

Scope (see work/active/WO-0007a-order-status-eventing/design-decision.md):
after a successful APPLY outcome from `plan_transition_order`, both stores'
`transition_order` now ALSO co-write, in the SAME atomic block as the
existing order-row + audit-event write, an `ExecutionEvent` for:

  ->SUBMITTED          (any source)                  dedupe f"submitted:{id}"
  ->PARTIALLY_FILLED   (first entry, status-changed)  dedupe f"partially_filled:{id}"
  ->FILLED              (any source)                  dedupe f"filled:{id}"
  ->CANCELED            (direct, via transition_order) dedupe f"canceled:{id}"
  ->REJECTED             (direct, not via TQ)           dedupe f"rejected:{id}"
  PARTIALLY_FILLED->PARTIALLY_FILLED (fill progress, same status)
                                        dedupe f"order_fill_progress:{id}:{filled_quantity}"

`CANCEL_PENDING` entry/self-loop and the `SUBMITTING->CREATED` release remain
OUT OF SCOPE (no ExecutionEvent emitted for them) per the design doc's
explicit scope decision — the map lookup naturally returns None for those.

`plan_close_session`/`plan_flatten_position`'s direct CANCELED writers are
Stage 3, NOT exercised here.
"""

from __future__ import annotations

import pytest

from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
async def _created_buy_order(store, quantity: int = 10):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    order = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, quantity, session_id=sess.id
    )
    return sess, order


async def _submitting_order(store, quantity: int = 10):
    """CREATED -> SUBMITTING via the real claim path (the only legal entry)."""
    _, order = await _created_buy_order(store, quantity=quantity)
    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == "claimed"
    return order


async def _submitted_order(store, quantity: int = 10, broker_order_id: str = "brk-1"):
    order = await _submitting_order(store, quantity=quantity)
    updated = await store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
    )
    assert updated.status is OrderStatus.SUBMITTED
    return updated


def _events_of(events, event_type: ExecutionEventType):
    return [e for e in events if e.event_type is event_type]


# --------------------------------------------------------------------------- #
# ->SUBMITTED (any source)
# --------------------------------------------------------------------------- #
async def test_transition_to_submitted_emits_submitted_execution_event(any_store):
    order = await _submitted_order(any_store)

    events = await any_store.get_execution_events()
    submitted = _events_of(events, ExecutionEventType.SUBMITTED)
    assert len(submitted) == 1
    ev = submitted[0]
    assert ev.order_id == order.id
    assert ev.dedupe_key == f"submitted:{order.id}"
    assert ev.symbol == "AAPL"
    assert ev.side is OrderSide.BUY
    # WO-0009: SUBMITTED is a broker-observed fact (broker accepted + returned an
    # id, AIR-001), so provenance is BROKER_REST/BROKER_AUTHORITATIVE — no longer
    # WO-0007a's conservative ENGINE/LOCAL. Full provenance matrix:
    # tests/test_wo0009_provenance.py.
    assert ev.source is EventSource.BROKER_REST
    assert ev.authority is EventAuthority.BROKER_AUTHORITATIVE


# --------------------------------------------------------------------------- #
# ->PARTIALLY_FILLED (first entry, status-changed)
# --------------------------------------------------------------------------- #
async def test_transition_to_partially_filled_first_entry_emits_event(any_store):
    order = await _submitted_order(any_store, quantity=10)

    updated = await any_store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=3
    )
    assert updated.status is OrderStatus.PARTIALLY_FILLED
    assert updated.filled_quantity == 3

    events = await any_store.get_execution_events()
    partial = _events_of(events, ExecutionEventType.PARTIALLY_FILLED)
    assert len(partial) == 1
    ev = partial[0]
    assert ev.order_id == order.id
    assert ev.dedupe_key == f"partially_filled:{order.id}"


# --------------------------------------------------------------------------- #
# ->FILLED (any source: from SUBMITTED directly, and from PARTIALLY_FILLED)
# --------------------------------------------------------------------------- #
async def test_transition_to_filled_from_submitted_emits_event(any_store):
    order = await _submitted_order(any_store, quantity=10)

    updated = await any_store.transition_order(
        order.id, OrderStatus.FILLED, filled_quantity=10
    )
    assert updated.status is OrderStatus.FILLED

    events = await any_store.get_execution_events()
    filled = _events_of(events, ExecutionEventType.FILLED)
    assert len(filled) == 1
    assert filled[0].dedupe_key == f"filled:{order.id}"
    # No spurious PARTIALLY_FILLED event for a direct SUBMITTED -> FILLED jump.
    assert _events_of(events, ExecutionEventType.PARTIALLY_FILLED) == []


async def test_transition_to_filled_from_partially_filled_emits_event(any_store):
    order = await _submitted_order(any_store, quantity=10)
    await any_store.transition_order(order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=4)

    updated = await any_store.transition_order(
        order.id, OrderStatus.FILLED, filled_quantity=10
    )
    assert updated.status is OrderStatus.FILLED

    events = await any_store.get_execution_events()
    filled = _events_of(events, ExecutionEventType.FILLED)
    assert len(filled) == 1
    assert filled[0].dedupe_key == f"filled:{order.id}"
    # The earlier first-entry PARTIALLY_FILLED event is still there, untouched.
    partial = _events_of(events, ExecutionEventType.PARTIALLY_FILLED)
    assert len(partial) == 1
    assert partial[0].dedupe_key == f"partially_filled:{order.id}"


# --------------------------------------------------------------------------- #
# ->CANCELED (direct, via transition_order)
# --------------------------------------------------------------------------- #
async def test_transition_to_canceled_from_created_emits_event(any_store):
    # CREATED -> CANCELED: never-submitted order cancelled locally (legal per
    # ORDER_TRANSITIONS[CREATED]); does not go through claim at all.
    _, order = await _created_buy_order(any_store)

    updated = await any_store.transition_order(order.id, OrderStatus.CANCELED)
    assert updated.status is OrderStatus.CANCELED

    events = await any_store.get_execution_events()
    canceled = _events_of(events, ExecutionEventType.CANCELED)
    assert len(canceled) == 1
    assert canceled[0].dedupe_key == f"canceled:{order.id}"


async def test_transition_to_canceled_from_submitted_emits_event(any_store):
    order = await _submitted_order(any_store)

    updated = await any_store.transition_order(order.id, OrderStatus.CANCELED)
    assert updated.status is OrderStatus.CANCELED

    events = await any_store.get_execution_events()
    canceled = _events_of(events, ExecutionEventType.CANCELED)
    assert len(canceled) == 1
    assert canceled[0].dedupe_key == f"canceled:{order.id}"


# --------------------------------------------------------------------------- #
# ->REJECTED (direct, not via TQ)
# --------------------------------------------------------------------------- #
async def test_transition_to_rejected_from_created_emits_event(any_store):
    _, order = await _created_buy_order(any_store)

    updated = await any_store.transition_order(order.id, OrderStatus.REJECTED)
    assert updated.status is OrderStatus.REJECTED

    events = await any_store.get_execution_events()
    rejected = _events_of(events, ExecutionEventType.REJECTED)
    assert len(rejected) == 1
    assert rejected[0].dedupe_key == f"rejected:{order.id}"


async def test_transition_to_rejected_from_submitting_emits_event(any_store):
    order = await _submitting_order(any_store)

    updated = await any_store.transition_order(order.id, OrderStatus.REJECTED)
    assert updated.status is OrderStatus.REJECTED

    events = await any_store.get_execution_events()
    rejected = _events_of(events, ExecutionEventType.REJECTED)
    assert len(rejected) == 1
    assert rejected[0].dedupe_key == f"rejected:{order.id}"


# --------------------------------------------------------------------------- #
# PARTIALLY_FILLED -> PARTIALLY_FILLED (fill-progress self-loop)
# --------------------------------------------------------------------------- #
async def test_repeated_partial_fills_produce_distinct_dedupe_keyed_events(any_store):
    order = await _submitted_order(any_store, quantity=20)

    # First entry into PARTIALLY_FILLED (status-changed branch).
    await any_store.transition_order(order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=5)
    # Two further partial fills — the same-status self-loop, each strictly
    # increasing filled_quantity (monotonic, bound-checked upstream).
    await any_store.transition_order(order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=9)
    await any_store.transition_order(order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=14)

    events = await any_store.get_execution_events()
    partial = _events_of(events, ExecutionEventType.PARTIALLY_FILLED)
    assert len(partial) == 3

    keys = [e.dedupe_key for e in partial]
    assert keys == [
        f"partially_filled:{order.id}",
        f"order_fill_progress:{order.id}:9",
        f"order_fill_progress:{order.id}:14",
    ]
    # No collision / silent drop: all three keys distinct, all three appended.
    assert len(set(keys)) == 3
    assert all(e.order_id == order.id for e in partial)


# --------------------------------------------------------------------------- #
# Defense-in-depth guard (Stage 1, exercised here): a routine ->SUBMITTED
# emission must never succeed on a TIMEOUT_QUARANTINE order. No current call
# site does this (TQ resolution uses the separate evented path), but if some
# future/other code DID call generic transition_order(order, SUBMITTED) on a
# TQ order, the helper's assertion must fire loudly rather than silently
# constructing a colliding shared-format key.
# --------------------------------------------------------------------------- #
async def test_routine_submitted_on_timeout_quarantine_order_raises_not_silently_drops(any_store):
    order = await _submitting_order(any_store)
    await any_store.quarantine_timed_out_order(order.id)

    with pytest.raises(AssertionError):
        await any_store.transition_order(
            order.id, OrderStatus.SUBMITTED, broker_order_id="brk-late"
        )

    # No partial write: the order is still TIMEOUT_QUARANTINE and no spurious
    # SUBMITTED execution event was appended.
    events = await any_store.get_execution_events()
    assert _events_of(events, ExecutionEventType.SUBMITTED) == []


# --------------------------------------------------------------------------- #
# Out of scope, explicitly documented as inert here: CANCEL_PENDING.
# --------------------------------------------------------------------------- #
async def test_transition_to_cancel_pending_emits_cancel_pending_event(any_store):
    # WO-0007b brought CANCEL_PENDING entry INTO scope (it was WO-0007a-out-of-scope):
    # a live pending-cancel order must be representable in the projection, so entry
    # now co-writes exactly one CANCEL_PENDING event (see tests/test_wo0007b_*).
    order = await _submitted_order(any_store)
    before_keys = {e.dedupe_key for e in await any_store.get_execution_events()}

    updated = await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
    assert updated.status is OrderStatus.CANCEL_PENDING

    after_keys = {e.dedupe_key for e in await any_store.get_execution_events()}
    assert after_keys - before_keys == {f"cancel_pending:{order.id}"}


# --------------------------------------------------------------------------- #
# Dual-store parity for the emitted order-status stream.
# --------------------------------------------------------------------------- #
async def test_dual_store_transition_order_eventing_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007a_stage2.db")
    try:
        for store in (memory, sqlite):
            order = await _submitted_order(store, quantity=20)
            await store.transition_order(order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=5)
            await store.transition_order(order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=12)
            await store.transition_order(order.id, OrderStatus.FILLED, filled_quantity=20)

        for store, label in ((memory, "memory"), (sqlite, "sqlite")):
            events = await store.get_execution_events()
            shapes = [
                (e.event_type.value, e.dedupe_key.split(":", 1)[0])
                for e in events
                if e.event_type
                in (
                    ExecutionEventType.SUBMITTED,
                    ExecutionEventType.PARTIALLY_FILLED,
                    ExecutionEventType.FILLED,
                )
            ]
            assert shapes == [
                ("submitted", "submitted"),
                ("partially_filled", "partially_filled"),
                ("partially_filled", "order_fill_progress"),
                ("filled", "filled"),
            ], f"{label} store produced unexpected event shape: {shapes}"
    finally:
        await sqlite.close()
