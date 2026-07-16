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
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=qty,
        session_id=session_id,
    )
    await store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    order = await store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    return si, order


async def _live_protection_at_status(store, symbol, qty, status, *, session_id=None):
    """A PROTECTION_FLOOR exit for ``symbol`` driven PAST ``CREATED`` to
    ``status`` (SUBMITTED / CANCEL_PENDING / TIMEOUT_QUARANTINE) — the in-flight/
    live-at-broker states a manual flatten must DEFER to (INV-036), never
    double-exit or blind-cancel."""
    si, order = await _protective_floor_order(store, symbol, qty, session_id=session_id)
    claim = await store.claim_order_for_submission(order.id)
    if status is OrderStatus.TIMEOUT_QUARANTINE:
        await store.quarantine_timed_out_order(claim.order.id)
    else:
        await store.transition_order(
            claim.order.id, OrderStatus.SUBMITTED, broker_order_id="broker-x"
        )
        if status is OrderStatus.CANCEL_PENDING:
            await store.transition_order(claim.order.id, OrderStatus.CANCEL_PENDING)
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


# ---- a stranded MANUAL_FLATTEN with no order self-heals ------------------ #


async def test_stranded_manual_flatten_with_no_order_self_heals(any_store):
    """Defense-in-depth self-heal for a ``MANUAL_FLATTEN`` intent left APPROVED
    with no order. ``flatten_position`` itself no longer strands one — its whole
    supersede+create+approve+dispatch sequence is a single transaction
    (REV-0006-F-001), so a crash or dispatch reject inside it rolls back cleanly.
    But a stranded APPROVED-no-order intent can still arise from ANOTHER route
    (e.g. a direct create_sell_intent + transition, as simulated here). Before the
    self-heal, a later flatten call trusted ANY active MANUAL_FLATTEN intent as
    "the existing exit" and returned it as-is — silently no-op'ing forever (HTTP
    200, order=None) while permanently poisoning single-flight dedup for the
    symbol. This pins that a later flatten SUPERSEDES the stranded intent and opens
    a real exit. Simulates the stranded state directly rather than interrupting a
    transaction mid-flight."""

    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    session = await any_store.get_current_session()
    stranded = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.MANUAL_FLATTEN,
        target_quantity=100,
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
    assert (
        await any_store.get_sell_intent(stranded.id)
    ).status is SellIntentStatus.EXPIRED
    # A THIRD call is idempotent against the freshly-created (real) exit —
    # not against the now-expired stranded one.
    third = await any_store.flatten_position("AAPL")
    assert third.outcome == FLATTEN_EXISTING
    assert third.intent.id == result.intent.id


async def test_flatten_dispatch_crash_leaves_no_partial(any_store, monkeypatch):
    """REV-0006-F-001 (INV-050, single-writer atomicity): a hard crash at the
    order-dispatch boundary of a create-flatten must leave NO durable partial —
    no APPROVED ``MANUAL_FLATTEN`` intent with no order, no orphan SELL order.
    The whole supersede + create + approve + dispatch sequence is ONE
    all-or-nothing unit. The in-memory store already rolls back atomically; the
    sqlite store split it across transactions and durably stranded the approved
    intent (which then also stands the autonomous protection tick down on a
    non-existent exit). This pins BOTH stores to the atomic behaviour."""

    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)

    # Model a hard crash at the dispatch step, AFTER the fresh intent's
    # insert+approve: the dispatch helper raises. Under one transaction this
    # rolls the whole flatten back; a split-transaction store strands the
    # already-committed APPROVED intent.
    def _crash(*args, **kwargs):
        raise RuntimeError("injected dispatch crash")

    patched = False
    for name in (
        "_dispatch_order_for_sell_intent_locked",  # sqlite
        "_dispatch_order_for_sell_intent_unlocked",  # memory
    ):
        if hasattr(any_store, name):
            monkeypatch.setattr(any_store, name, _crash)
            patched = True
            break
    assert patched, "no dispatch helper found to inject the crash into"

    with pytest.raises(RuntimeError, match="injected dispatch crash"):
        await any_store.flatten_position("AAPL")

    # INV-050 all-or-nothing: nothing durable survived the failed flatten.
    intents = await any_store.list_sell_intents(symbol="AAPL")
    assert intents == [], f"stranded sell intent(s) after failed flatten: {intents}"
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert sells == [], f"stranded SELL order(s) after failed flatten: {sells}"


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
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(stranded.id, SellIntentStatus.APPROVED)
    assert stranded.order_id is None

    result = await any_store.flatten_position("AAPL")

    assert result.outcome == FLATTEN_CREATED
    assert result.superseded is True
    assert result.intent.reason is SellReason.MANUAL_FLATTEN
    assert result.intent.id != stranded.id
    assert (
        await any_store.get_sell_intent(stranded.id)
    ).status is SellIntentStatus.EXPIRED


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


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.SUBMITTED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.TIMEOUT_QUARANTINE,
    ],
)
async def test_live_protection_floor_deferral_records_provenance(any_store, status):
    # INV-036 leaves a live/in-flight protection exit alone — but the human's
    # flatten must (a) leave an audit trail (a manual_flatten_deferred event
    # correlated to the deferred intent, carrying the order it deferred to and
    # that order's status) AND (b) be reported DISTINCTLY (REV-0002 F-001):
    # result.deferred is True so the caller knows NO manual order was submitted.
    # Holds for every non-CREATED status the exit can be sitting in.
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    prot_intent, prot_order = await _live_protection_at_status(
        any_store, "AAPL", 100, status
    )

    result = await any_store.flatten_position("AAPL")
    assert result.outcome == FLATTEN_EXISTING
    assert result.deferred is True
    assert result.intent.reason is SellReason.PROTECTION_FLOOR

    events = await any_store.list_events(correlation_id=prot_intent.id)
    deferrals = [e for e in events if e.event_type == "manual_flatten_deferred"]
    assert len(deferrals) == 1
    assert deferrals[0].order_id == prot_order.id
    assert deferrals[0].payload.get("order_status") == status.value

    # No new SELL order/intent was created; the position is untouched.
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert len(sells) == 1
    assert (await any_store.get_position("AAPL")).quantity == 100


async def test_flatten_not_deferred_on_create_or_idempotent_return(any_store):
    # The `deferred` flag keys on the deferral event, NOT the FLATTEN_EXISTING
    # outcome (REV-0002 F-001 pre-mortem): a fresh create and the idempotent
    # own-manual-flatten re-return (also FLATTEN_EXISTING, but no deferral) must
    # both read deferred=False.
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    first = await any_store.flatten_position("AAPL")
    assert first.outcome == FLATTEN_CREATED
    assert first.deferred is False
    second = await any_store.flatten_position("AAPL")
    assert second.outcome == FLATTEN_EXISTING
    assert second.deferred is False


async def test_deferral_records_command_actor(any_store):
    # REV-0002 F-002: the deferral provenance event records WHO commanded the
    # flatten (actor threaded in, never resolved inside the pure planner).
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    prot_intent, _ = await _live_protection_at_status(
        any_store, "AAPL", 100, OrderStatus.SUBMITTED
    )
    await any_store.flatten_position("AAPL", actor="alice")
    events = await any_store.list_events(correlation_id=prot_intent.id)
    deferrals = [e for e in events if e.event_type == "manual_flatten_deferred"]
    assert len(deferrals) == 1
    assert deferrals[0].payload.get("actor") == "alice"


async def test_deferral_actor_defaults_to_system(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    prot_intent, _ = await _live_protection_at_status(
        any_store, "AAPL", 100, OrderStatus.SUBMITTED
    )
    await any_store.flatten_position("AAPL")  # no actor -> COMMAND_ACTOR_SYSTEM
    events = await any_store.list_events(correlation_id=prot_intent.id)
    deferrals = [e for e in events if e.event_type == "manual_flatten_deferred"]
    assert deferrals[0].payload.get("actor") == "system"


async def test_created_manual_flatten_records_command_actor(any_store):
    # REV-0002 F-002: the created-manual-flatten path stamps the actor on the
    # fresh intent's sell_intent_created event too.
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    result = await any_store.flatten_position("AAPL", actor="alice")
    assert result.outcome == FLATTEN_CREATED
    events = await any_store.list_events(correlation_id=result.intent.id)
    created = [e for e in events if e.event_type == "sell_intent_created"]
    assert len(created) == 1
    assert created[0].payload.get("actor") == "alice"


async def test_protection_tick_create_sell_intent_actor_stays_system(any_store):
    # The shared _insert_sell_intent helper defaults to "system": a protection
    # tick's create_sell_intent must NOT inherit a real operator actor.
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    events = await any_store.list_events(correlation_id=si.id)
    created = [e for e in events if e.event_type == "sell_intent_created"]
    assert created[0].payload.get("actor") == "system"


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
        result.order.id,
        "AAPL",
        OrderSide.SELL,
        100,
        9.0,
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
