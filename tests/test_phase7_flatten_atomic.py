"""X-001 — the atomic ``StateStore.flatten_position`` (both stores, parity).

The whole "read the live position, stand down any non-live PROTECTION_FLOOR
exit, create + approve + dispatch a fresh MANUAL_FLATTEN" sequence happens
under ONE lock hold, so the returned intent's ``reason`` is guaranteed
``manual_flatten`` — never a deduped intent of a different reason, even when a
competing writer (a protection tick's own ``create_sell_intent`` call) is
racing for the same symbol. See ``tests/test_hypothesis_lifecycle.py`` /
the state-machine harness for the generated-interleaving version of this
property, and ``tests/test_phase7_routes.py`` for the HTTP-level tests.
"""

from __future__ import annotations

import asyncio

import pytest

from app.models import (
    CandidateStatus,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
)
from app.store.base import FLATTEN_CREATED, FLATTEN_EXISTING, FLATTEN_FLAT

pytestmark = pytest.mark.anyio


async def _hold(store, symbol, qty, avg=10.0, *, session_id=None):
    if session_id is None:
        session = await store.get_current_session()
        session_id = session.id
    cand = await store.create_candidate(symbol, session_id=session_id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session_id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session_id
    )
    return buy


async def _protective_floor_order(store, symbol, qty, *, session_id=None):
    """A CREATED PROTECTION_FLOOR exit for ``symbol`` — not yet live."""
    if session_id is None:
        session_id = (await store.get_current_session()).id
    si = await store.create_sell_intent(
        symbol=symbol, reason=SellReason.PROTECTION_FLOOR, target_quantity=qty,
        session_id=session_id,
    )
    await store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    order = await store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    return si, order


# ---- FLAT --------------------------------------------------------------- #


async def test_flat_position_returns_flat(any_store):
    await any_store.initialize()
    result = await any_store.flatten_position("AAPL")
    assert result.outcome == FLATTEN_FLAT
    assert result.intent is None
    assert result.order is None


# ---- fresh create --------------------------------------------------------- #


async def test_fresh_create_when_no_active_intent(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    result = await any_store.flatten_position("AAPL")
    assert result.outcome == FLATTEN_CREATED
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert result.intent.status is SellIntentStatus.ORDERED
    assert result.intent.target_quantity == 100
    assert result.order.side is OrderSide.SELL
    assert result.order.order_type is OrderType.MARKET
    assert result.order.quantity == 100
    assert result.order.candidate_id is None
    assert result.order.sell_intent_id == result.intent.id
    assert result.order.status is OrderStatus.CREATED
    assert result.superseded is False


async def test_symbol_normalized(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 50)
    result = await any_store.flatten_position("aapl")
    assert result.outcome == FLATTEN_CREATED
    assert result.intent.symbol == "AAPL"


# ---- idempotent (own manual_flatten already active) ----------------------- #


async def test_idempotent_when_own_manual_flatten_active(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    first = await any_store.flatten_position("AAPL")
    second = await any_store.flatten_position("AAPL")
    assert second.outcome == FLATTEN_EXISTING
    assert second.intent.id == first.intent.id
    assert second.intent.reason is SellReason.MANUAL_FLATTEN
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert len(sells) == 1


# ---- a stranded MANUAL_FLATTEN (crash between commits) self-heals -------- #


async def test_stranded_manual_flatten_with_no_order_self_heals(any_store):
    """Adversarial re-review finding on the X-001 diff: ``SqliteStateStore.
    flatten_position`` commits the fresh intent's insert+approve in one
    transaction, then dispatches the order in a SEPARATE transaction. A crash
    landing between those two commits durably strands a ``MANUAL_FLATTEN``
    intent at APPROVED with no order at all. Before this fix, a later flatten
    call trusted ANY MANUAL_FLATTEN active intent as "the existing exit" and
    returned it as-is — silently no-op'ing forever (HTTP 200, order=None)
    while permanently poisoning single-flight dedup for the symbol. Simulates
    the stranded state directly (bypassing the atomic dispatch, exactly as a
    crash would leave it) rather than trying to interrupt a real transaction
    mid-flight."""

    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    session = await any_store.get_current_session()
    stranded = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(stranded.id, SellIntentStatus.APPROVED)
    assert stranded.order_id is None

    result = await any_store.flatten_position("AAPL")

    assert result.outcome == FLATTEN_CREATED
    assert result.superseded is True
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert result.intent.id != stranded.id
    assert result.order is not None
    assert result.order.status is OrderStatus.CREATED
    assert (await any_store.get_sell_intent(stranded.id)).status is SellIntentStatus.EXPIRED
    # A THIRD call is idempotent against the freshly-created (real) exit —
    # not against the now-expired stranded one.
    third = await any_store.flatten_position("AAPL")
    assert third.outcome == FLATTEN_EXISTING
    assert third.intent.id == result.intent.id


# ---- supersede an unsent PROTECTION_FLOOR exit ---------------------------- #


async def test_supersedes_created_protection_floor_order(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    prot_intent, prot_order = await _protective_floor_order(any_store, "AAPL", 100)
    assert prot_order.status is OrderStatus.CREATED

    result = await any_store.flatten_position("AAPL")

    assert result.outcome == FLATTEN_CREATED
    assert result.superseded is True
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert result.intent.id != prot_intent.id
    # The old protective order is canceled; its intent stays ORDERED (that's
    # the intent's OWN terminal-for-its-lifecycle state — the order itself is
    # what got stood down).
    assert (await any_store.get_order(prot_order.id)).status is OrderStatus.CANCELED
    # A fresh MANUAL_FLATTEN order now exists.
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert len(sells) == 2  # the canceled protective one + the new flatten one
    assert result.order.id != prot_order.id
    assert result.order.status is OrderStatus.CREATED


async def test_supersedes_stranded_intent_with_no_order(any_store):
    # A PROTECTION_FLOOR intent APPROVED but with NO order at all (order_id
    # None) — the narrowest, most-unsent form; must still be superseded, not
    # returned as-is (the X-001 remediation's specific major finding on the
    # route, now impossible via the atomic method since there is no gap
    # between "check" and "create" for a competing writer to exploit).
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    session = await any_store.get_current_session()
    stranded = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(stranded.id, SellIntentStatus.APPROVED)
    assert stranded.order_id is None

    result = await any_store.flatten_position("AAPL")

    assert result.outcome == FLATTEN_CREATED
    assert result.superseded is True
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert result.intent.id != stranded.id
    assert (await any_store.get_sell_intent(stranded.id)).status is SellIntentStatus.EXPIRED


# ---- a genuinely LIVE protection_floor exit is left alone ----------------- #


async def test_live_protection_floor_order_is_left_alone(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    prot_intent, prot_order = await _protective_floor_order(any_store, "AAPL", 100)
    # Make it LIVE (submitted at the broker).
    claim = await any_store.claim_order_for_submission(prot_order.id)
    await any_store.transition_order(
        claim.order.id, OrderStatus.SUBMITTED, broker_order_id="broker-x"
    )

    result = await any_store.flatten_position("AAPL")

    assert result.outcome == FLATTEN_EXISTING
    assert result.intent.id == prot_intent.id
    assert result.intent.reason is SellReason.PROTECTION_FLOOR
    assert result.order.id == prot_order.id
    assert result.order.status is OrderStatus.SUBMITTED
    # Nothing new was created.
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert len(sells) == 1


# ---- correlation / audit trail --------------------------------------------- #


async def test_supersede_event_correlates_on_old_intent(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    prot_intent, prot_order = await _protective_floor_order(any_store, "AAPL", 100)
    result = await any_store.flatten_position("AAPL")

    old_events = await any_store.list_events(correlation_id=prot_intent.id)
    superseded_events = [
        e
        for e in old_events
        if e.event_type == "order_transition"
        and e.payload.get("reason") == "superseded_by_manual_flatten"
    ]
    assert len(superseded_events) == 1

    new_events = await any_store.list_events(correlation_id=result.intent.id)
    assert any(e.event_type == "sell_intent_created" for e in new_events)
    assert any(e.event_type == "order_created" for e in new_events)


# ---- flat position after superseding everything --------------------------- #


async def test_flat_after_all_exits_terminal_returns_flat_not_stale(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    result = await any_store.flatten_position("AAPL")
    # Fully fill the flatten sell -> position goes flat.
    await any_store.append_fill(
        result.order.id, "AAPL", OrderSide.SELL, 100, 9.0,
        session_id=result.intent.session_id,
    )
    second = await any_store.flatten_position("AAPL")
    assert second.outcome == FLATTEN_FLAT


# --------------------------------------------------------------------------- #
# X-001 deterministic concurrency regression: a human's flatten and a
# protection tick's own create_sell_intent call, launched as GENUINELY
# CONCURRENT asyncio tasks racing for the same store lock on the same symbol.
# The whole point of the atomic flatten_position (vs. the old route's separate
# "check active" + "create" calls) is that there is no gap inside its own
# critical section for a competing writer to land in — the two tasks can only
# ever interleave as one FULLY completing before the other STARTS (neither
# method has an await point inside its own `async with self._lock:` block).
# Both possible orderings are exercised by swapping which coroutine is passed
# to asyncio.gather first.
# --------------------------------------------------------------------------- #


async def _racing_protection_create(store, symbol, qty):
    """Simulates the first half of `_open_protective_exit`'s own
    create_sell_intent call — the minimal store-level call that can race
    flatten_position for the same symbol's single-flight slot."""

    return await store.create_sell_intent(
        symbol=symbol, reason=SellReason.PROTECTION_FLOOR, target_quantity=qty
    )


async def test_concurrent_flatten_and_protection_create_flatten_first(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)

    flatten_result, protection_result = await asyncio.gather(
        any_store.flatten_position("AAPL"),
        _racing_protection_create(any_store, "AAPL", 100),
    )

    # Regardless of which coroutine's lock acquisition actually won, the
    # flatten call's own result must ALWAYS carry a manual_flatten intent — it
    # can never be silently captured by the racing protection create.
    assert flatten_result.intent is not None
    assert flatten_result.intent.reason is SellReason.MANUAL_FLATTEN
    # The racing protection create either made its own PENDING intent (if it
    # ran first and got expired/superseded by flatten) or got deduped onto
    # flatten's own already-ordered manual_flatten intent (if flatten ran
    # first) — either way, it must never end up as the thing flatten reports.
    assert protection_result is not None


async def test_concurrent_flatten_and_protection_create_protection_first(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)

    # Same race, opposite argument order (asyncio.gather schedules coroutines'
    # first steps in the order given) — exercising the other interleaving.
    protection_result, flatten_result = await asyncio.gather(
        _racing_protection_create(any_store, "AAPL", 100),
        any_store.flatten_position("AAPL"),
    )

    assert flatten_result.intent is not None
    assert flatten_result.intent.reason is SellReason.MANUAL_FLATTEN
    assert protection_result is not None


async def test_concurrent_flatten_never_leaves_symbol_without_manual_exit(any_store):
    """The X-001 property stated positively: after the race, exactly one
    ACTIVE sell intent exists for the symbol, and it is manual_flatten (never
    left owned by a racing protection_floor intent, and never a state with two
    simultaneously-active intents for the same symbol)."""

    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)

    await asyncio.gather(
        any_store.flatten_position("AAPL"),
        _racing_protection_create(any_store, "AAPL", 100),
    )

    active = await any_store.active_sell_intent_for("AAPL")
    assert active is not None
    assert active.reason is SellReason.MANUAL_FLATTEN
