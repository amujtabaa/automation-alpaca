"""WO-0007a Stage 1 — CREATED -> SUBMITTING (claim) ExecutionEvent emission.

Scope (see work/active/WO-0007a-order-status-eventing/design-decision.md):
only the claim path. A successful `claim_order_for_submission` now ALSO
appends a `SUBMIT_PENDING` ExecutionEvent, atomically with the existing
order-row + audit-event write, keyed `submit_pending:{order_id}:{n}` where
`n` is the 0-based count of prior SUBMIT_PENDING events for that order — the
only transition in the order-status graph that can repeat (the
CREATED <-> SUBMITTING cycle), so `n` disambiguates each repeat.

Other statuses (SUBMITTED/PARTIALLY_FILLED/FILLED/CANCELED/REJECTED) are
wired into `execution_event_for_routine_transition` per the full design but
are Stage 2+ concerns — not exercised here beyond "the helper compiles".
"""

from __future__ import annotations

import pytest

from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.store.core import execution_event_for_routine_transition
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------- #
# Pure helper — app/store/core.py::execution_event_for_routine_transition
# --------------------------------------------------------------------------- #
def _created_order(order_id: str = "o1") -> Order:
    return Order(
        id=order_id,
        candidate_id="c1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=1.0,
        status=OrderStatus.CREATED,
    )


def test_helper_returns_submit_pending_event_for_claim_occurrence_zero():
    order = _created_order()
    event = execution_event_for_routine_transition(
        order, OrderStatus.SUBMITTING, None, occurrence=0
    )
    assert event is not None
    assert event.event_type is ExecutionEventType.SUBMIT_PENDING
    assert event.dedupe_key == "submit_pending:o1:0"
    assert event.order_id == "o1"
    assert event.symbol == "AAPL"
    assert event.side is OrderSide.BUY
    assert event.source is EventSource.ENGINE
    assert event.authority is EventAuthority.LOCAL


def test_helper_defaults_occurrence_to_zero_when_omitted():
    order = _created_order()
    event = execution_event_for_routine_transition(order, OrderStatus.SUBMITTING, None)
    assert event is not None
    assert event.dedupe_key == "submit_pending:o1:0"


def test_helper_encodes_occurrence_n_into_the_dedupe_key():
    order = _created_order()
    event = execution_event_for_routine_transition(
        order, OrderStatus.SUBMITTING, None, occurrence=3
    )
    assert event is not None
    assert event.dedupe_key == "submit_pending:o1:3"


def test_helper_returns_none_for_a_status_it_does_not_instrument_yet():
    # SUBMITTING is the only branch Stage 1 asserts fully-correct; anything not
    # in the routine-status map and not the claim/fill-progress special cases
    # returns None so the store can call this unconditionally.
    order = _created_order()
    order.status = OrderStatus.CREATED
    assert (
        execution_event_for_routine_transition(order, OrderStatus.CREATED, None) is None
    )


def test_helper_guard_rejects_shared_format_key_from_timeout_quarantine():
    # Defense-in-depth (design doc item 5 / review Finding D): the helper must
    # refuse to build a submitted:/canceled:/rejected: key for an order that is
    # currently TIMEOUT_QUARANTINE, even though no call site does this today.
    order = _created_order()
    order.status = OrderStatus.TIMEOUT_QUARANTINE
    with pytest.raises(AssertionError):
        execution_event_for_routine_transition(order, OrderStatus.SUBMITTED, None)


# --------------------------------------------------------------------------- #
# Store wiring — claim_order_for_submission (both stores via any_store)
# --------------------------------------------------------------------------- #
async def _created_buy_order(store):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    order = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 10, session_id=sess.id
    )
    return sess, order


async def test_claim_emits_exactly_one_submit_pending_event_at_occurrence_zero(
    any_store,
):
    _, order = await _created_buy_order(any_store)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == "claimed"
    assert claim.order.status is OrderStatus.SUBMITTING

    events = await any_store.get_execution_events()
    submit_pending = [
        e for e in events if e.event_type is ExecutionEventType.SUBMIT_PENDING
    ]
    assert len(submit_pending) == 1
    ev = submit_pending[0]
    assert ev.order_id == order.id
    assert ev.dedupe_key == f"submit_pending:{order.id}:0"
    assert ev.symbol == "AAPL"
    assert ev.side is OrderSide.BUY
    assert ev.source is EventSource.ENGINE
    assert ev.authority is EventAuthority.LOCAL

    # Still recorded exactly once in the append-only log.
    assert len([e for e in events if e.order_id == order.id]) == 1


async def test_claim_release_reclaim_produces_gapless_uniquely_keyed_events(any_store):
    """Explicit test requirement (design doc, review Task 3): drive an order
    through claim -> release (SUBMITTING -> CREATED via transition_order) ->
    re-claim at least twice; the resulting SUBMIT_PENDING execution events must
    be gapless, uniquely keyed (occurrence 0,1,2,...), and all present in
    get_execution_events()."""

    _, order = await _created_buy_order(any_store)

    claim1 = await any_store.claim_order_for_submission(order.id)
    assert claim1.outcome == "claimed"

    await any_store.transition_order(order.id, OrderStatus.CREATED)

    claim2 = await any_store.claim_order_for_submission(order.id)
    assert claim2.outcome == "claimed"

    await any_store.transition_order(order.id, OrderStatus.CREATED)

    claim3 = await any_store.claim_order_for_submission(order.id)
    assert claim3.outcome == "claimed"

    events = await any_store.get_execution_events()
    submit_pending = [
        e for e in events if e.event_type is ExecutionEventType.SUBMIT_PENDING
    ]
    assert len(submit_pending) == 3
    assert [e.dedupe_key for e in submit_pending] == [
        f"submit_pending:{order.id}:0",
        f"submit_pending:{order.id}:1",
        f"submit_pending:{order.id}:2",
    ]
    assert all(e.order_id == order.id for e in submit_pending)
    # Gapless, strictly increasing sequence numbers (append-only log order).
    seqs = [e.sequence for e in submit_pending]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == 3


async def test_dual_store_claim_release_reclaim_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007a.db")
    try:
        for store in (memory, sqlite):
            _, order = await _created_buy_order(store)
            await store.claim_order_for_submission(order.id)
            await store.transition_order(order.id, OrderStatus.CREATED)
            await store.claim_order_for_submission(order.id)
            await store.transition_order(order.id, OrderStatus.CREATED)
            await store.claim_order_for_submission(order.id)

        mem_events = [
            e
            for e in await memory.get_execution_events()
            if e.event_type is ExecutionEventType.SUBMIT_PENDING
        ]
        sql_events = [
            e
            for e in await sqlite.get_execution_events()
            if e.event_type is ExecutionEventType.SUBMIT_PENDING
        ]
        assert len(mem_events) == len(sql_events) == 3
        # dedupe_key embeds the store-local order id, which the two stores
        # mint independently, so compare the occurrence suffix (the part that
        # matters: gapless 0,1,2,... in append order) rather than the literal
        # string.
        mem_occurrences = [e.dedupe_key.rsplit(":", 1)[-1] for e in mem_events]
        sql_occurrences = [e.dedupe_key.rsplit(":", 1)[-1] for e in sql_events]
        assert mem_occurrences == sql_occurrences == ["0", "1", "2"]
        assert all(
            e.dedupe_key.startswith(f"submit_pending:{e.order_id}:")
            for e in (*mem_events, *sql_events)
        )
        mem_shape = [
            (e.event_type.value, e.source.value, e.authority.value) for e in mem_events
        ]
        sql_shape = [
            (e.event_type.value, e.source.value, e.authority.value) for e in sql_events
        ]
        assert mem_shape == sql_shape
    finally:
        await sqlite.close()
