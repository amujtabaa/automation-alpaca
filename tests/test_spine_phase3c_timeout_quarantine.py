"""Spine v2 Phase 3 wave 3c (part 1) — TIMEOUT_QUARANTINE scaffolding (ADR-002).

Additive/inert: this slice adds the OrderStatus + transitions, the
AmbiguousBrokerError classification, the read-only targeted-query adapter method,
the store's evented quarantine/resolve transitions, and the
`timeout_quarantined_order_ids` projector — but nothing in the monitoring loop
routes to them yet (that wiring, and the Flow-2 characterization migration, is
part 2). The whole existing corpus stays green because nothing calls these yet.

The event-truth claim (docs/SPINE_WAVE3C_PLAN.md C5): the FIRST durable write of a
quarantine is a TIMEOUT_QUARANTINE ExecutionEvent; the order-row status is a
co-written read-model reconstructable from the log — proven by the replay +
dual-store parity tests here.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.broker.adapter import (
    AmbiguousBrokerError,
    BrokerError,
    BrokerFill,
    BrokerOrderUpdate,
    TerminalBrokerError,
)
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.monitoring import run_monitoring_tick
from app.events.projectors import timeout_quarantined_order_ids
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
)
from app.store.base import OrderTransitionError
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_TS = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


def _lifecycle_event(
    order_id: str, event_type: ExecutionEventType, seq: int
) -> ExecutionEvent:
    return ExecutionEvent(
        sequence=seq,
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=f"{event_type.value}:{order_id}:{seq}",
        order_id=order_id,
    )


# --------------------------------------------------------------------------- #
# AmbiguousBrokerError — classification (a BrokerError subclass, distinct)
# --------------------------------------------------------------------------- #
def test_ambiguous_broker_error_is_a_broker_error_but_not_terminal():
    exc = AmbiguousBrokerError("timeout")
    assert isinstance(
        exc, BrokerError
    )  # existing `except BrokerError` still catches it
    assert not isinstance(exc, TerminalBrokerError)  # distinct from a definitive reject


# --------------------------------------------------------------------------- #
# Projector — timeout_quarantined_order_ids (latest lifecycle event wins)
# --------------------------------------------------------------------------- #
def test_projector_flags_a_quarantined_order():
    events = [_lifecycle_event("o1", ExecutionEventType.TIMEOUT_QUARANTINE, 1)]
    assert timeout_quarantined_order_ids(events) == {"o1"}


def test_projector_clears_on_resolution_to_submitted():
    events = [
        _lifecycle_event("o1", ExecutionEventType.TIMEOUT_QUARANTINE, 1),
        _lifecycle_event("o1", ExecutionEventType.SUBMITTED, 2),  # resolved -> working
    ]
    assert timeout_quarantined_order_ids(events) == set()


def test_projector_clears_on_resolution_to_rejected():
    events = [
        _lifecycle_event("o1", ExecutionEventType.TIMEOUT_QUARANTINE, 1),
        _lifecycle_event(
            "o1", ExecutionEventType.REJECTED, 2
        ),  # resolved -> never arrived
    ]
    assert timeout_quarantined_order_ids(events) == set()


def test_projector_is_order_sensitive_latest_wins():
    # A re-quarantine AFTER a resolution latches again (latest lifecycle wins).
    events = [
        _lifecycle_event("o1", ExecutionEventType.TIMEOUT_QUARANTINE, 1),
        _lifecycle_event("o1", ExecutionEventType.SUBMITTED, 2),
        _lifecycle_event("o1", ExecutionEventType.TIMEOUT_QUARANTINE, 3),
    ]
    assert timeout_quarantined_order_ids(events) == {"o1"}


def test_projector_ignores_fill_events_and_other_orders():
    events = [
        _lifecycle_event("o1", ExecutionEventType.TIMEOUT_QUARANTINE, 1),
        # A FILL never resolves a quarantine (it would ingest AFTER a SUBMITTED
        # resolution); a stray fill leaves the order quarantined (the safe latch).
        ExecutionEvent(
            sequence=2,
            event_type=ExecutionEventType.FILL,
            source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE,
            dedupe_key="fill:o1:x",
            order_id="o1",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1,
            price=1.0,
            ts_event=_TS,
        ),
        _lifecycle_event("o2", ExecutionEventType.SUBMITTED, 3),  # never quarantined
    ]
    assert timeout_quarantined_order_ids(events) == {"o1"}


def test_projector_empty_for_no_lifecycle_events():
    assert timeout_quarantined_order_ids([]) == set()


# --------------------------------------------------------------------------- #
# Store — quarantine / resolve / list (both stores via any_store)
# --------------------------------------------------------------------------- #
async def _submitting_order(store):
    """A fresh store with one BUY order claimed to SUBMITTING (the legal source
    state for a quarantine)."""
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    order = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 10, session_id=sess.id
    )
    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == "claimed"
    return sess, order


async def test_quarantine_flips_status_records_event_and_lists(any_store):
    _, order = await _submitting_order(any_store)
    q = await any_store.quarantine_timed_out_order(order.id, reason="timeout")
    assert q.status is OrderStatus.TIMEOUT_QUARANTINE

    # The FIRST durable write is the TIMEOUT_QUARANTINE ExecutionEvent (truth).
    events = await any_store.get_execution_events()
    tq = [e for e in events if e.event_type is ExecutionEventType.TIMEOUT_QUARANTINE]
    assert len(tq) == 1
    assert tq[0].order_id == order.id
    assert tq[0].dedupe_key == f"timeout_quarantine:{order.id}"
    assert tq[0].source is EventSource.ENGINE  # our local ambiguity decision
    assert tq[0].authority is EventAuthority.LOCAL

    # An operator-visible audit event too.
    audit = [
        e
        for e in await any_store.list_events()
        if e.event_type == "order_timeout_quarantined"
    ]
    assert len(audit) == 1

    # Derived-from-log listing.
    listed = await any_store.list_timeout_quarantined_orders()
    assert [o.id for o in listed] == [order.id]


async def test_quarantine_is_idempotent_noop_on_repeat(any_store):
    _, order = await _submitting_order(any_store)
    await any_store.quarantine_timed_out_order(order.id)
    # Already TIMEOUT_QUARANTINE -> same-status NOOP: no second event, still listed.
    await any_store.quarantine_timed_out_order(order.id)
    tq = [
        e
        for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.TIMEOUT_QUARANTINE
    ]
    assert len(tq) == 1
    assert len(await any_store.list_timeout_quarantined_orders()) == 1


async def test_quarantine_rejects_a_non_submitting_order(any_store):
    # A CREATED order (never claimed) cannot be quarantined: SUBMITTING is the
    # only legal source (transitions table), so this raises and writes nothing.
    await any_store.initialize()
    sess = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=sess.id)
    order = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 10, session_id=sess.id
    )
    with pytest.raises(OrderTransitionError):
        await any_store.quarantine_timed_out_order(order.id)
    assert await any_store.get_execution_events() == []
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED


async def test_resolve_to_submitted_requires_broker_id_then_clears(any_store):
    _, order = await _submitting_order(any_store)
    await any_store.quarantine_timed_out_order(order.id)

    # AIR-001: resolving to SUBMITTED without a broker id is rejected.
    with pytest.raises(OrderTransitionError):
        await any_store.resolve_timeout_quarantine(order.id, OrderStatus.SUBMITTED)

    r = await any_store.resolve_timeout_quarantine(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
    )
    assert r.status is OrderStatus.SUBMITTED
    assert r.broker_order_id == "brk-1"
    # A SUBMITTED lifecycle ExecutionEvent (broker-authoritative) resolves it.
    submitted = [
        e
        for e in await any_store.get_execution_events()
        if e.event_type is ExecutionEventType.SUBMITTED
    ]
    assert len(submitted) == 1
    assert submitted[0].authority is EventAuthority.BROKER_AUTHORITATIVE
    assert await any_store.list_timeout_quarantined_orders() == []


async def test_resolve_to_rejected_when_never_arrived(any_store):
    _, order = await _submitting_order(any_store)
    await any_store.quarantine_timed_out_order(order.id)
    r = await any_store.resolve_timeout_quarantine(
        order.id, OrderStatus.REJECTED, reason="not_found"
    )
    assert r.status is OrderStatus.REJECTED
    assert await any_store.list_timeout_quarantined_orders() == []


async def test_resolve_rejects_an_illegal_target_status(any_store):
    _, order = await _submitting_order(any_store)
    await any_store.quarantine_timed_out_order(order.id)
    # FILLED is not a legal direct resolution (INV-9 — it must go via SUBMITTED).
    with pytest.raises(ValueError):
        await any_store.resolve_timeout_quarantine(order.id, OrderStatus.FILLED)


# --------------------------------------------------------------------------- #
# Replay + dual-store parity (event-truth): the quarantine survives replay and
# is identical across memory and SQLite.
# --------------------------------------------------------------------------- #
async def test_quarantine_survives_and_matches_the_event_log(any_store):
    _, order = await _submitting_order(any_store)
    await any_store.quarantine_timed_out_order(order.id)
    # The store's own list (event-log-derived) == a fresh projection of the log.
    fresh = timeout_quarantined_order_ids(await any_store.get_execution_events())
    assert fresh == {order.id}
    assert {o.id for o in await any_store.list_timeout_quarantined_orders()} == fresh


async def test_dual_store_quarantine_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "tq.db")
    try:
        for store in (memory, sqlite):
            _, order = await _submitting_order(store)
            await store.quarantine_timed_out_order(order.id)
        mem_ids = timeout_quarantined_order_ids(await memory.get_execution_events())
        sql_ids = timeout_quarantined_order_ids(await sqlite.get_execution_events())
        # Same shape (one quarantined order each); both derive it from the log.
        assert len(mem_ids) == len(sql_ids) == 1
        assert len(await memory.list_timeout_quarantined_orders()) == 1
        assert len(await sqlite.list_timeout_quarantined_orders()) == 1
    finally:
        await sqlite.close()


async def test_quarantine_survives_sqlite_reopen(tmp_path):
    store = SqliteStateStore(tmp_path / "reopen.db")
    _, order = await _submitting_order(store)
    await store.quarantine_timed_out_order(order.id)
    await store.close()

    reopened = SqliteStateStore(tmp_path / "reopen.db")
    await reopened.initialize()
    assert [o.id for o in await reopened.list_timeout_quarantined_orders()] == [
        order.id
    ]
    assert (await reopened.get_order(order.id)).status is OrderStatus.TIMEOUT_QUARANTINE
    await reopened.close()


# --------------------------------------------------------------------------- #
# Read-only targeted query — get_order_by_client_order_id (mock adapter)
# --------------------------------------------------------------------------- #
async def test_targeted_query_returns_none_for_unknown_client_id():
    adapter = MockBrokerAdapter()
    assert await adapter.get_order_by_client_order_id("never-submitted") is None
    assert adapter.client_queries == ["never-submitted"]


async def test_targeted_query_finds_a_seeded_venue_order():
    # Simulate "the ambiguous submit DID reach the venue" independently of submit.
    adapter = MockBrokerAdapter()
    adapter.seed_venue_order("o1", BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, []))
    found = await adapter.get_order_by_client_order_id("o1")
    assert found is not None
    assert found.status is OrderStatus.SUBMITTED
    assert found.broker_order_id == "broker-o1"  # auto-filled deterministic id


async def test_targeted_query_finds_a_successfully_submitted_order():
    from app.models import Order, OrderType

    adapter = MockBrokerAdapter()
    order = Order(
        candidate_id="c1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=1.0,
    )
    broker_id = await adapter.submit_order(order)
    found = await adapter.get_order_by_client_order_id(order.id)
    assert found is not None
    assert found.broker_order_id == broker_id


async def test_targeted_query_failure_raises_never_absent():
    # A query FAILURE must raise (BrokerError), never be read as "absent" (§7).
    adapter = MockBrokerAdapter()
    adapter.fail_next_client_query(BrokerError("simulated query failure"))
    with pytest.raises(BrokerError):
        await adapter.get_order_by_client_order_id("o1")


# --------------------------------------------------------------------------- #
# Part 2 — monitoring wiring (the behavior change): ambiguous submit ->
# quarantine -> targeted read-only resolution. All the resolution outcomes.
# --------------------------------------------------------------------------- #
async def _quarantined_via_tick(store, adapter, settings, symbol="AAPL", qty=10):
    """Drive a fresh BUY order into TIMEOUT_QUARANTINE through a real tick by
    making its submit raise AmbiguousBrokerError."""
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=1.0, session_id=sess.id
    )
    order = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=sess.id
    )
    adapter.fail_next_submit(AmbiguousBrokerError("simulated 504 timeout"))
    await run_monitoring_tick(store, adapter, settings)
    assert (await store.get_order(order.id)).status is OrderStatus.TIMEOUT_QUARANTINE
    return cand, order


async def test_ambiguous_submit_is_not_resubmitted_and_blocks_replacement(any_store):
    # ADR-002: the quarantined order is never resubmitted (no double-fire), and no
    # replacement order is created for its candidate while quarantined (the order
    # stays non-terminal -> the candidate stays ORDERED -> INV-2).
    adapter = MockBrokerAdapter()
    settings = Settings()
    cand, order = await _quarantined_via_tick(any_store, adapter, settings)
    submits = len(adapter.submitted)

    # Several more ticks while the order stays genuinely quarantined (an
    # inconclusive query never resolves it): it is NEVER resubmitted, and no
    # replacement order is created for its candidate.
    for _ in range(3):
        adapter.fail_next_client_query(BrokerError("venue unreachable"))
        await run_monitoring_tick(any_store, adapter, settings)
    assert (
        await any_store.get_order(order.id)
    ).status is OrderStatus.TIMEOUT_QUARANTINE
    assert len(adapter.submitted) == submits  # read-only resolution, no resubmit
    # No replacement order for the candidate.
    orders = [o for o in await any_store.list_orders() if o.candidate_id == cand.id]
    assert [o.id for o in orders] == [order.id]


async def test_resolution_adopts_a_filled_venue_order_via_submitted(any_store):
    # A venue order the ambiguous submit actually filled resolves to SUBMITTED
    # first (INV-9 — never a direct jump to FILLED); the reconcile poll then
    # ingests the fill in the SAME tick, moving it to FILLED and the position.
    adapter = MockBrokerAdapter()
    settings = Settings()
    _, order = await _quarantined_via_tick(any_store, adapter, settings, qty=10)
    broker_id = f"broker-{order.id}"
    filled = BrokerOrderUpdate(
        OrderStatus.FILLED,
        10,
        [BrokerFill(source_fill_id="f1", quantity=10, price=1.0, filled_at=_TS)],
        broker_order_id=broker_id,
    )
    adapter.seed_venue_order(order.id, filled)  # the targeted query sees FILLED
    adapter.set_response(broker_id, filled)  # the reconcile poll ingests it

    await run_monitoring_tick(any_store, adapter, settings)
    resolved = await any_store.get_order(order.id)
    assert resolved.status is OrderStatus.FILLED
    assert (await any_store.get_position("AAPL")).quantity == 10
    assert await any_store.list_timeout_quarantined_orders() == []


async def test_resolution_to_canceled_when_venue_canceled(any_store):
    adapter = MockBrokerAdapter()
    settings = Settings()
    _, order = await _quarantined_via_tick(any_store, adapter, settings)
    adapter.seed_venue_order(order.id, BrokerOrderUpdate(OrderStatus.CANCELED, 0, []))
    await run_monitoring_tick(any_store, adapter, settings)
    assert (await any_store.get_order(order.id)).status is OrderStatus.CANCELED
    assert await any_store.list_timeout_quarantined_orders() == []


async def test_not_found_resolves_to_rejected_after_the_bound(any_store):
    # A confirmed-absent order (query returns None) is REJECTED only after the
    # bounded number of confirmations (§7: a single not-found could be venue lag).
    adapter = MockBrokerAdapter()
    settings = Settings()
    # The quarantine tick already does the FIRST not-found query (same tick), so
    # max_attempts total not-found queries are reached after max_attempts-1 more.
    _, order = await _quarantined_via_tick(any_store, adapter, settings)
    for _ in range(settings.timeout_quarantine_max_query_attempts - 1):
        # Before reaching the bound it stays quarantined (deferred), not rejected.
        assert (
            await any_store.get_order(order.id)
        ).status is OrderStatus.TIMEOUT_QUARANTINE
        await run_monitoring_tick(any_store, adapter, settings)
    # The query that reaches the bound resolves to REJECTED (§7: confirmed absent).
    assert (await any_store.get_order(order.id)).status is OrderStatus.REJECTED


async def test_query_error_leaves_quarantined_and_flags_needs_review(any_store):
    # A query FAILURE is inconclusive: never resolve (never "absent"). Past the
    # bound the order is surfaced for manual review but stays quarantined.
    adapter = MockBrokerAdapter()
    settings = Settings()
    _, order = await _quarantined_via_tick(any_store, adapter, settings)
    for _ in range(settings.timeout_quarantine_max_query_attempts + 1):
        adapter.fail_next_client_query(BrokerError("venue unreachable"))
        await run_monitoring_tick(any_store, adapter, settings)
    # Still quarantined (never auto-resolved on an inconclusive query).
    assert (
        await any_store.get_order(order.id)
    ).status is OrderStatus.TIMEOUT_QUARANTINE
    # A needs_review deferral was surfaced.
    deferrals = [
        e
        for e in await any_store.list_events()
        if e.event_type == "order_timeout_quarantine_deferred"
        and e.payload.get("needs_review")
    ]
    assert deferrals, "expected a needs_review deferral after the bound"


async def test_query_errors_do_not_erode_the_not_found_reject_bound(any_store):
    # Review M1: the not-found REJECT bound and the query-error bound must be
    # INDEPENDENT (§7) — a run of query failures must NOT let a single confirmed
    # not-found reject a possibly-live order. It still takes max_attempts CONFIRMED
    # not-founds regardless of how many query errors happened.
    adapter = MockBrokerAdapter()
    settings = Settings()
    _, order = await _quarantined_via_tick(any_store, adapter, settings)  # not_found #1
    for _ in range(settings.timeout_quarantine_max_query_attempts + 2):
        adapter.fail_next_client_query(BrokerError("venue flapping"))
        await run_monitoring_tick(any_store, adapter, settings)
    assert (
        await any_store.get_order(order.id)
    ).status is OrderStatus.TIMEOUT_QUARANTINE
    # Now genuine not-founds reach the bound (the quarantine tick was not_found #1).
    for _ in range(settings.timeout_quarantine_max_query_attempts - 2):
        await run_monitoring_tick(any_store, adapter, settings)
        assert (
            await any_store.get_order(order.id)
        ).status is OrderStatus.TIMEOUT_QUARANTINE
    await run_monitoring_tick(any_store, adapter, settings)  # reaches max_attempts
    assert (await any_store.get_order(order.id)).status is OrderStatus.REJECTED


async def test_canceled_with_partial_fills_preserves_the_fills(any_store):
    # Review M2: a quarantine that resolves to a venue-terminal CANCELED but with
    # PARTIAL FILLS must not drop those broker-authoritative shares. It adopts
    # SUBMITTED first so the reconcile poll ingests the fills, then finalizes.
    adapter = MockBrokerAdapter()
    settings = Settings()
    _, order = await _quarantined_via_tick(any_store, adapter, settings, qty=10)
    broker_id = f"broker-{order.id}"
    # Venue: canceled, but 4 of 10 shares actually filled (e.g. expired remainder).
    adapter.seed_venue_order(
        order.id,
        BrokerOrderUpdate(OrderStatus.CANCELED, 4, [], broker_order_id=broker_id),
    )
    # The reconcile poll reports the same canceled + the 4-share fill.
    adapter.set_response(
        broker_id,
        BrokerOrderUpdate(OrderStatus.CANCELED, 4, [BrokerFill("f1", 4, 1.0, _TS)]),
    )
    await run_monitoring_tick(any_store, adapter, settings)
    resolved = await any_store.get_order(order.id)
    assert resolved.status is OrderStatus.CANCELED  # finalized via reconcile
    assert (await any_store.get_position("AAPL")).quantity == 4  # fills NOT dropped


async def test_persistent_query_error_deferral_log_is_bounded(any_store):
    # Review L1: a persistent venue outage must NOT append a deferral event every
    # tick forever — the query-error deferrals are bounded at max_attempts (a single
    # needs_review marker), never unbounded growth.
    adapter = MockBrokerAdapter()
    settings = Settings()
    _, order = await _quarantined_via_tick(any_store, adapter, settings)
    for _ in range(settings.timeout_quarantine_max_query_attempts + 5):
        adapter.fail_next_client_query(BrokerError("venue down"))
        await run_monitoring_tick(any_store, adapter, settings)
    query_error_deferrals = [
        e
        for e in await any_store.list_events()
        if e.event_type == "order_timeout_quarantine_deferred"
        and (e.payload or {}).get("reason") == "query_error"
    ]
    assert len(query_error_deferrals) == settings.timeout_quarantine_max_query_attempts
    assert any(e.payload.get("needs_review") for e in query_error_deferrals)
    assert (
        await any_store.get_order(order.id)
    ).status is OrderStatus.TIMEOUT_QUARANTINE


async def test_ambiguous_redrive_of_stale_submitting_quarantines(any_store):
    # The stale-SUBMITTING re-drive path is the other submit choke point: an
    # ambiguous re-drive outcome quarantines too (never blind re-drives).
    await any_store.initialize()
    sess = await any_store.get_current_session()
    cand = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0, session_id=sess.id
    )
    order = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 10, session_id=sess.id
    )
    # Claim it to SUBMITTING with no broker id (the stale-redrive precondition).
    await any_store.claim_order_for_submission(order.id)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(AmbiguousBrokerError("ambiguous redrive"))
    await run_monitoring_tick(any_store, adapter, Settings())
    assert (
        await any_store.get_order(order.id)
    ).status is OrderStatus.TIMEOUT_QUARANTINE
