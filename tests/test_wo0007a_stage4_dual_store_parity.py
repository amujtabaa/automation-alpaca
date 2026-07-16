"""WO-0007a Stage 4 (final) — comprehensive dual-store parity for the FULL set
of order-status ExecutionEvent emission sites added across Stages 1-3.

Stages 1-3 (see work/active/WO-0007a-order-status-eventing/design-decision.md)
already added, and per-stage dual-store parity tests already pinned, each
emission site in isolation:

  - Stage 1 (``tests/test_wo0007a_claim_eventing.py``): the claim path
    (``claim_order_for_submission``) and the claim/release/re-claim cycle.
  - Stage 2 (``tests/test_wo0007a_transition_order_eventing.py``): every
    routine ``transition_order``-driven status, including the
    ``PARTIALLY_FILLED -> PARTIALLY_FILLED`` fill-progress self-loop.
  - Stage 3 (``tests/test_wo0007a_cancel_paths_eventing.py``): the two
    ``plan_close_session`` / ``plan_flatten_position`` direct-CANCELED
    writers that bypass ``transition_order`` entirely.

This module is the FINAL INTEGRATION pass: it does not add any new
production emission site. Instead it drives four representative,
end-to-end lifecycle SCRIPTS — combining several emission sites per run,
which no earlier stage's test did in one script — independently on a fresh
``InMemoryStateStore()`` and a fresh ``SqliteStateStore()``, and asserts the
two stores' ``get_execution_events()`` streams, filtered to the new
order-status event types (``SUBMIT_PENDING``, ``SUBMITTED``,
``PARTIALLY_FILLED``, ``FILLED``, ``CANCELED``, ``REJECTED``), are IDENTICAL
in **event_type sequence** and **dedupe_key sequence** — order-independent
set-equality is explicitly NOT accepted here; the point of this pass is to
prove the two storage engines replay the same order-status story in the same
order, which is the property WO-0007b's future projector will depend on.

Because ``dedupe_key`` embeds the store-local order id (minted independently
by each store instance), keys are normalized by substituting each event's
OWN ``order_id`` with a stable role label (``<ORDER>``, or ``<BUY>``/
``<PROT>`` for the two-order flatten script) before comparison — mirroring
the id-agnostic comparison idiom already used by
``test_wo0007a_claim_eventing.py::test_dual_store_claim_release_reclaim_parity``
and by ``test_spine_phase3c_timeout_quarantine.py::test_dual_store_quarantine_parity``.
"""

from __future__ import annotations

import pytest

from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_ORDER_STATUS_EVENT_TYPES = {
    ExecutionEventType.SUBMIT_PENDING,
    ExecutionEventType.SUBMITTED,
    ExecutionEventType.PARTIALLY_FILLED,
    ExecutionEventType.FILLED,
    ExecutionEventType.CANCELED,
    ExecutionEventType.REJECTED,
}

# WO-0009 faithful provenance (see tests/test_wo0009_provenance.py): the claim and
# never-submitted (CREATED) cancels are engine-local; every broker-observed status
# is broker-authoritative.
_ENG = (EventSource.ENGINE, EventAuthority.LOCAL)
_BRK = (EventSource.BROKER_REST, EventAuthority.BROKER_AUTHORITATIVE)


def _stream(events, id_to_role: dict[str, str]):
    """The order-status-event-type-filtered (event_type, normalized dedupe_key,
    source, authority) sequence, in append (i.e. store) order. ``id_to_role``
    maps each store-local order id present in the script to a stable label so the
    two independently-minted-id stores can be compared positionally.

    WO-0009 extends the compared shape to include provenance (``source``,
    ``authority``): the two storage engines must replay not just the same
    order-status story in the same order, but with identical faithful provenance
    on every event."""

    out = []
    for e in events:
        if e.event_type not in _ORDER_STATUS_EVENT_TYPES:
            continue
        role = id_to_role.get(e.order_id)
        if role is None:
            # Not one of the orders this script drives (shouldn't happen on a
            # fresh store dedicated to one script, but fail loudly rather than
            # silently mis-comparing if it ever does).
            raise AssertionError(
                f"event for untracked order_id={e.order_id!r} in stream: {e}"
            )
        out.append(
            (
                e.event_type,
                e.dedupe_key.replace(e.order_id, role),
                e.source,
                e.authority,
            )
        )
    return out


def _assert_parity(
    memory_events, sqlite_events, mem_ids: dict, sql_ids: dict, label: str
):
    mem_stream = _stream(memory_events, mem_ids)
    sql_stream = _stream(sqlite_events, sql_ids)
    assert mem_stream == sql_stream, (
        f"{label}: dual-store event stream mismatch\n"
        f"  memory: {mem_stream}\n"
        f"  sqlite: {sql_stream}"
    )
    # Sanity: the scripts below are non-trivial — make sure we didn't just
    # compare two empty lists.
    assert len(mem_stream) > 0, f"{label}: unexpectedly empty stream"


# --------------------------------------------------------------------------- #
# Script 1 — comprehensive order lifecycle ending in FILLED.
#
# claim -> release (SUBMITTING->CREATED) -> re-claim -> ack (->SUBMITTED) ->
# two separate partial fills -> FILLED.
#
# Exercises: Stage 1 claim emission (twice, occurrence 0 and 1, across a
# release/re-claim), Stage 2 ->SUBMITTED, Stage 2 first-entry
# ->PARTIALLY_FILLED, Stage 2 PARTIALLY_FILLED->PARTIALLY_FILLED self-loop
# (twice fills == one first-entry + one self-loop), and Stage 2 ->FILLED —
# five distinct emission call sites in one script.
# --------------------------------------------------------------------------- #
async def _script_full_lifecycle_to_filled(store, quantity: int = 20):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    order = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, quantity, session_id=sess.id
    )

    claim1 = await store.claim_order_for_submission(order.id)
    assert claim1.outcome == "claimed"

    # release: SUBMITTING -> CREATED (out-of-scope, emits nothing)
    await store.transition_order(order.id, OrderStatus.CREATED)

    claim2 = await store.claim_order_for_submission(order.id)
    assert claim2.outcome == "claimed"

    # ack -> SUBMITTED
    acked = await store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-full"
    )
    assert acked.status is OrderStatus.SUBMITTED

    # two separate partial fills, strictly increasing filled_quantity
    p1 = await store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=6
    )
    assert p1.status is OrderStatus.PARTIALLY_FILLED
    p2 = await store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=15
    )
    assert p2.status is OrderStatus.PARTIALLY_FILLED

    filled = await store.transition_order(
        order.id, OrderStatus.FILLED, filled_quantity=quantity
    )
    assert filled.status is OrderStatus.FILLED

    return order


async def test_dual_store_parity_full_lifecycle_to_filled(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007a_stage4_filled.db")
    try:
        mem_order = await _script_full_lifecycle_to_filled(memory)
        sql_order = await _script_full_lifecycle_to_filled(sqlite)

        mem_events = await memory.get_execution_events()
        sql_events = await sqlite.get_execution_events()
        _assert_parity(
            mem_events,
            sql_events,
            {mem_order.id: "<ORDER>"},
            {sql_order.id: "<ORDER>"},
            "full_lifecycle_to_filled",
        )

        # Pin the exact expected shape too (not just mem==sqlite) so a future
        # regression that changes BOTH stores identically (e.g. a dropped
        # emission site copy-pasted into both) still fails loudly.
        expected = [
            (ExecutionEventType.SUBMIT_PENDING, "submit_pending:<ORDER>:0", *_ENG),
            (ExecutionEventType.SUBMIT_PENDING, "submit_pending:<ORDER>:1", *_ENG),
            (ExecutionEventType.SUBMITTED, "submitted:<ORDER>", *_BRK),
            (ExecutionEventType.PARTIALLY_FILLED, "partially_filled:<ORDER>", *_BRK),
            (
                ExecutionEventType.PARTIALLY_FILLED,
                "order_fill_progress:<ORDER>:15",
                *_BRK,
            ),
            (ExecutionEventType.FILLED, "filled:<ORDER>", *_BRK),
        ]
        assert _stream(mem_events, {mem_order.id: "<ORDER>"}) == expected
        assert _stream(sql_events, {sql_order.id: "<ORDER>"}) == expected
    finally:
        await sqlite.close()


# --------------------------------------------------------------------------- #
# Script 2 — lifecycle ending in CANCELED via the routine `transition_order`
# path (direct cancel of a SUBMITTED order — "normal cancel").
# --------------------------------------------------------------------------- #
async def _script_transition_order_cancel(store, quantity: int = 10):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    order = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, quantity, session_id=sess.id
    )

    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == "claimed"

    acked = await store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-cancel"
    )
    assert acked.status is OrderStatus.SUBMITTED

    canceled = await store.transition_order(order.id, OrderStatus.CANCELED)
    assert canceled.status is OrderStatus.CANCELED

    return order


async def test_dual_store_parity_transition_order_cancel(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007a_stage4_txn_cancel.db")
    try:
        mem_order = await _script_transition_order_cancel(memory)
        sql_order = await _script_transition_order_cancel(sqlite)

        mem_events = await memory.get_execution_events()
        sql_events = await sqlite.get_execution_events()
        _assert_parity(
            mem_events,
            sql_events,
            {mem_order.id: "<ORDER>"},
            {sql_order.id: "<ORDER>"},
            "transition_order_cancel",
        )

        expected = [
            (ExecutionEventType.SUBMIT_PENDING, "submit_pending:<ORDER>:0", *_ENG),
            (ExecutionEventType.SUBMITTED, "submitted:<ORDER>", *_BRK),
            # CANCELED from a SUBMITTED order = broker-confirmed cancel.
            (ExecutionEventType.CANCELED, "canceled:<ORDER>", *_BRK),
        ]
        assert _stream(mem_events, {mem_order.id: "<ORDER>"}) == expected
        assert _stream(sql_events, {sql_order.id: "<ORDER>"}) == expected
    finally:
        await sqlite.close()


# --------------------------------------------------------------------------- #
# Script 3 — lifecycle ending in CANCELED via session-close cancellation
# (`plan_close_session`'s still-CREATED-BUY cancel selection — never claimed,
# never submitted).
# --------------------------------------------------------------------------- #
async def _script_session_close_cancel(store, quantity: int = 10):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    order = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, quantity, session_id=sess.id
    )

    await store.close_session()

    closed = await store.get_order(order.id)
    assert closed.status is OrderStatus.CANCELED

    return order


async def test_dual_store_parity_session_close_cancel(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007a_stage4_close_cancel.db")
    try:
        mem_order = await _script_session_close_cancel(memory)
        sql_order = await _script_session_close_cancel(sqlite)

        mem_events = await memory.get_execution_events()
        sql_events = await sqlite.get_execution_events()
        _assert_parity(
            mem_events,
            sql_events,
            {mem_order.id: "<ORDER>"},
            {sql_order.id: "<ORDER>"},
            "session_close_cancel",
        )

        # CANCELED of a never-submitted CREATED order (session close) = engine-local.
        expected = [(ExecutionEventType.CANCELED, "canceled:<ORDER>", *_ENG)]
        assert _stream(mem_events, {mem_order.id: "<ORDER>"}) == expected
        assert _stream(sql_events, {sql_order.id: "<ORDER>"}) == expected
    finally:
        await sqlite.close()


# --------------------------------------------------------------------------- #
# Script 4 — lifecycle ending in CANCELED via manual-flatten supersede
# cancellation (`plan_flatten_position`'s supersede branch standing down a
# stranded CREATED protective exit order). Two orders in play: the BUY that
# establishes the held position (claimed/acked/filled — exercises Stage
# 1+2 emission sites too, alongside the flatten target), and the protective
# SELL order that gets superseded/canceled (Stage 3 emission site).
# --------------------------------------------------------------------------- #
async def _hold(store, symbol: str, qty: int, avg: float = 10.0):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )
    claim = await store.claim_order_for_submission(buy.id)
    assert claim.outcome == "claimed"
    await store.transition_order(
        buy.id, OrderStatus.SUBMITTED, broker_order_id="brk-hold"
    )
    await store.transition_order(buy.id, OrderStatus.FILLED, filled_quantity=qty)
    return buy


async def _protective_floor_order(store, symbol: str, qty: int):
    session_id = (await store.get_current_session()).id
    si = await store.create_sell_intent(
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=qty,
        session_id=session_id,
    )
    await store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    order = await store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    return order


async def _script_flatten_supersede_cancel(store, symbol: str = "AAPL", qty: int = 100):
    await store.initialize()
    buy_order = await _hold(store, symbol, qty)
    prot_order = await _protective_floor_order(store, symbol, qty)
    assert prot_order.status is OrderStatus.CREATED

    result = await store.flatten_position(symbol)
    assert result.superseded is True

    superseded = await store.get_order(prot_order.id)
    assert superseded.status is OrderStatus.CANCELED

    return buy_order, prot_order


async def test_dual_store_parity_flatten_supersede_cancel(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007a_stage4_flatten_cancel.db")
    try:
        mem_buy, mem_prot = await _script_flatten_supersede_cancel(memory)
        sql_buy, sql_prot = await _script_flatten_supersede_cancel(sqlite)

        mem_events = await memory.get_execution_events()
        sql_events = await sqlite.get_execution_events()
        mem_ids = {mem_buy.id: "<BUY>", mem_prot.id: "<PROT>"}
        sql_ids = {sql_buy.id: "<BUY>", sql_prot.id: "<PROT>"}
        _assert_parity(
            mem_events, sql_events, mem_ids, sql_ids, "flatten_supersede_cancel"
        )

        expected = [
            (ExecutionEventType.SUBMIT_PENDING, "submit_pending:<BUY>:0", *_ENG),
            (ExecutionEventType.SUBMITTED, "submitted:<BUY>", *_BRK),
            (ExecutionEventType.FILLED, "filled:<BUY>", *_BRK),
            # PROT is a never-submitted CREATED protective order superseded by the
            # flatten = engine-local cancel.
            (ExecutionEventType.CANCELED, "canceled:<PROT>", *_ENG),
        ]
        assert _stream(mem_events, mem_ids) == expected
        assert _stream(sql_events, sql_ids) == expected
    finally:
        await sqlite.close()
