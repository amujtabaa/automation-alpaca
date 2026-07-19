"""Spine v2 Phase 0 characterization tests.

These are **characterization tests, not endorsement tests**: each one pins
CURRENT behavior for one of the five flows
``prompts/CLAUDE_CODE_PHASE_0_HANDOFF.md`` names as "most likely to be
changed later" (manual flatten, stale/submitting retry, broker-reported
overfill, fill/position derivation, kill switch/session), and cross-references
the accepted ADR that targets *different* behavior for that flow. A test
passing here documents "this is what the code does today," not "this is
correct forever" — several of these tests exist specifically to make a real,
current ADR conflict visible and regression-proof, per CLAUDE.md's Conflict
rule ("do not silently pick one... stop and record the decision gap").

See ``docs/SPINE_PHASE0_INVENTORY.md`` for the full conflict writeup this
file backs. No production behavior changes here — this file only adds tests
against existing code paths.
"""

from __future__ import annotations

import pytest

import app.monitoring as monitoring
from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
    TradingState,
)
from app.monitoring import run_monitoring_tick
from app.store.base import CLAIM_CLAIMED, FlattenBlockedError

pytestmark = pytest.mark.anyio


def _force_regular_hours(monkeypatch):
    # A protective/flatten MARKET sell only submits as-is in REGULAR hours
    # (§5.4/D-015); forcing this removes a wall-clock dependency from tests
    # that only care about kill-switch/claim-gate behavior, not session-type
    # order-type derivation (covered elsewhere, e.g.
    # tests/test_phase7_monitoring_submit.py).
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)


async def _hold(store, symbol, qty, avg=10.0):
    """A held position: BUY candidate -> order -> fill -> flat the buy order."""
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)


async def _submitting_order(store, symbol="AAPL", qty=100):
    """A claimed BUY order sitting in SUBMITTING with broker_order_id=None —
    the durable state a crash between claim and broker-ack leaves behind."""
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=1.0
    )
    order = await store.create_order_for_test(
        candidate.id, symbol, OrderSide.BUY, qty, limit_price=1.0
    )
    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
    return claim.order


# --------------------------------------------------------------------------- #
# Flow 1 — manual flatten vs. ADR-003 (Halted/Reducing policy)
# --------------------------------------------------------------------------- #
class TestCharacterizeManualFlatten:
    """MIGRATED (wave 3e — ADR-003 resolved, Option B). A manual flatten is now
    DENIED by default while ``Halted`` (the kill switch is a true all-stop): the
    operator exits via an explicit, audited emergency-reduce override that scopes a
    single reduce-only exit while the global ``TradingState`` stays ``Halted``.
    Flatten stays allowed in ``Reducing`` (buys-paused) and ``Active`` — a human
    getting out is never blocked by a control meant to stop *new* intent.
    The full graded matrix + INV-3 gate live in
    ``tests/test_spine_phase3e_manual_flatten.py``; this pins the end-to-end path.
    """

    async def test_manual_flatten_denied_under_kill_switch(self, any_store):
        await any_store.initialize()
        await _hold(any_store, "AAPL", 100)
        await any_store.set_kill_switch(True)  # -> HALTED

        with pytest.raises(FlattenBlockedError):
            await any_store.flatten_position("AAPL")
        # No order was minted — the position is untouched, nothing to submit.
        assert (await any_store.get_position("AAPL")).quantity == 100
        assert await any_store.active_sell_intent_for("AAPL") is None

    async def test_emergency_reduce_override_exits_while_halted(
        self, any_store, monkeypatch
    ):
        _force_regular_hours(monkeypatch)
        await any_store.initialize()
        await _hold(any_store, "AAPL", 100)
        await any_store.set_kill_switch(True)  # -> HALTED

        # The audited override authorizes exactly one reduce-only exit; global
        # state stays HALTED throughout.
        await any_store.authorize_emergency_reduce_override("AAPL", actor="op")
        # WO-0113 / REV-0031: only the explicit emergency path may spend the grant.
        result = await any_store.flatten_position("AAPL", emergency_override=True)
        assert result.intent.reason is SellReason.MANUAL_FLATTEN
        assert result.intent.status is SellIntentStatus.ORDERED
        assert await any_store.current_trading_state() is TradingState.HALTED

        # The created manual_flatten order still submits (an authorized, in-progress
        # exit completes — §8 in-flight resolves first).
        adapter = MockBrokerAdapter()
        await run_monitoring_tick(any_store, adapter, Settings())
        assert (
            await any_store.get_order(result.order.id)
        ).status is OrderStatus.SUBMITTED

        # Single-use: the override was consumed, so a SECOND flatten is denied again.
        with pytest.raises(FlattenBlockedError):
            await any_store.flatten_position("AAPL")

    async def test_manual_flatten_allowed_under_reducing(self, any_store):
        # Reducing (buys-paused, not killed) still permits an ordinary flatten.
        await any_store.initialize()
        await _hold(any_store, "AAPL", 100)
        await any_store.set_buys_paused(True)  # -> REDUCING
        result = await any_store.flatten_position("AAPL")
        assert result.intent.reason is SellReason.MANUAL_FLATTEN
        assert result.intent.status is SellIntentStatus.ORDERED


# --------------------------------------------------------------------------- #
# Flow 2 — stale SUBMITTING retry vs. ADR-002 (timeout/504 ambiguity)
# --------------------------------------------------------------------------- #
class TestCharacterizeStaleSubmittingRetry:
    """MIGRATED (Spine v2 wave 3c — ADR-002 resolved). The adapter now
    CLASSIFIES a submit failure (``app/broker/alpaca_paper.py``): a genuinely-safe
    transient (a pre-flight 429 rate-limit that provably never reached the book)
    stays a plain ``BrokerError`` and is still re-driven idempotently, but an
    AMBIGUOUS outcome (timeout / 504 / transport after the request may have
    reached Alpaca) is an :class:`AmbiguousBrokerError`. An ambiguous outcome is
    no longer blind-redriven — it moves the order to ``TIMEOUT_QUARANTINE`` and is
    resolved by a READ-ONLY targeted ``client_order_id`` query
    (``_resolve_timeout_quarantine``), never a resubmit-and-hope that could
    double-fire a live order.

    The first test pins the still-safe residual (a plain transient re-drives — not
    every failure quarantines); the second pins the migrated ambiguous path.
    """

    async def test_plain_transient_failure_still_blind_redrives(self, any_store):
        # A genuinely-safe transient (plain BrokerError, e.g. a pre-flight
        # 429) is NOT ambiguous — the request never reached the book — so the
        # idempotent re-drive is preserved. This documents that not every failure
        # quarantines; only an ambiguous outcome does.
        await any_store.initialize()
        order = await _submitting_order(any_store)
        adapter = MockBrokerAdapter()
        adapter.fail_next_submit(BrokerError("simulated rate limit"))

        await run_monitoring_tick(any_store, adapter, Settings())
        fresh = await any_store.get_order(order.id)
        assert fresh.status is OrderStatus.SUBMITTING  # deferred, not quarantined
        assert fresh.broker_order_id is None
        # An ordinary transient redrive creates NO broker-submit recovery record
        # (that ledger is only for definitively-stranded orders).
        assert await any_store.list_submit_recoveries() == []

        await run_monitoring_tick(any_store, adapter, Settings())
        redriven = await any_store.get_order(order.id)
        assert redriven.status is OrderStatus.SUBMITTED
        assert order.id in [o.id for o in adapter.submitted]

    async def test_ambiguous_submit_quarantines_and_resolves_by_targeted_query(
        self, any_store
    ):
        from app.broker.adapter import AmbiguousBrokerError, BrokerOrderUpdate

        await any_store.initialize()
        order = await _submitting_order(any_store)
        adapter = MockBrokerAdapter()
        adapter.fail_next_submit(AmbiguousBrokerError("simulated 504 timeout"))

        # Tick 1: ambiguous outcome -> TIMEOUT_QUARANTINE (NOT blind-redriven).
        await run_monitoring_tick(any_store, adapter, Settings())
        fresh = await any_store.get_order(order.id)
        assert fresh.status is OrderStatus.TIMEOUT_QUARANTINE
        assert order.id in [
            o.id for o in await any_store.list_timeout_quarantined_orders()
        ]
        submits_after_quarantine = len(adapter.submitted)

        # The ambiguous submit in fact reached the venue and is working there.
        adapter.seed_venue_order(
            order.id, BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, [])
        )

        # Tick 2: a READ-ONLY targeted query adopts it — with NO resubmit.
        await run_monitoring_tick(any_store, adapter, Settings())
        resolved = await any_store.get_order(order.id)
        assert resolved.status is OrderStatus.SUBMITTED
        assert resolved.broker_order_id is not None
        assert len(adapter.submitted) == submits_after_quarantine  # never resubmitted
        assert await any_store.list_timeout_quarantined_orders() == []


# --------------------------------------------------------------------------- #
# Flow 3 — broker-reported overfill/negative-position vs. ADR-001
# --------------------------------------------------------------------------- #
class TestCharacterizeBrokerOverfillHandling:
    """MIGRATED (Spine v2 wave 3b — ADR-001 resolved; this class previously
    *characterized* the pre-migration reject-and-drop behavior, now updated to
    the target behavior). A broker-authoritative overfill — a SELL that crosses
    the long-only position through flat — is now RECORDED at ``append_fill``
    (the FILL is appended, position projects the resulting short) and the symbol
    is QUARANTINED (derived from the negative event-log position); further
    autonomous BUY order intent for it is blocked. Intrinsic malformed input
    (NaN / non-positive qty or price) is *still* rejected at append
    (``fill_value_reason``) — only the broker-authoritative no-oversell case
    flipped from reject to record+quarantine.
    """

    async def test_broker_overfill_is_recorded_and_quarantines_the_symbol(
        self, any_store
    ):
        await any_store.initialize()
        session = await any_store.get_current_session()
        cand = await any_store.create_candidate("AAPL", session_id=session.id)
        buy = await any_store.create_order_for_test(
            cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
        )
        await any_store.append_fill(
            buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
        )
        sell = await any_store.create_order_for_test(
            cand.id, "AAPL", OrderSide.SELL, 150, session_id=session.id
        )

        # Broker reports this SELL fully filled at 150 while only 100 are held —
        # a broker-authoritative overfill. RECORDED, not dropped (ADR-001).
        result = await any_store.append_fill(
            sell.id, "AAPL", OrderSide.SELL, 150, 10.0, session_id=session.id
        )
        assert result.status == "appended"

        # The recorded short is projected; the symbol is quarantined; the fill
        # row exists (fact preserved, not dropped).
        assert (await any_store.get_position("AAPL")).quantity == -50
        assert "AAPL" in await any_store.list_quarantined_symbols()
        assert await any_store.list_fills(order_id=sell.id) != []


# --------------------------------------------------------------------------- #
# Flow 4 — fill/position derivation baseline vs. ADR-004
# --------------------------------------------------------------------------- #
class TestCharacterizeFillPositionDerivation:
    """CURRENT: position is folded from the append-only fill table (average
    cost, proportional cost-basis reduction on a sell), and a repeated
    ``source_fill_id`` is a no-op (never double-applied). This is the
    Rule-7/Rule-9 baseline ADR-004's event-log migration must reproduce
    EXACTLY under replay — ADR-004 does not change this folding semantic,
    only where it is durably sourced from (a legacy fill table today; an
    ``ExecutionEvent`` log once migrated, per ``docs/MIGRATION_MATRIX.md``'s
    "Fill deduplication: legacy_truth -> event_truth, preserve existing dedup
    semantics"). This test is the pin a future replay/parity verifier is
    checked against, not a conflict — the current behavior IS the target
    behavior; only its source of truth migrates.
    """

    async def test_average_cost_folding_and_duplicate_fill_dedup_baseline(
        self, any_store
    ):
        await any_store.initialize()
        session = await any_store.get_current_session()
        cand = await any_store.create_candidate("AAPL", session_id=session.id)
        buy = await any_store.create_order_for_test(
            cand.id, "AAPL", OrderSide.BUY, 200, session_id=session.id
        )
        await any_store.append_fill(
            buy.id,
            "AAPL",
            OrderSide.BUY,
            100,
            1.0,
            source_fill_id="fill-1",
            session_id=session.id,
        )
        await any_store.append_fill(
            buy.id,
            "AAPL",
            OrderSide.BUY,
            100,
            2.0,
            source_fill_id="fill-2",
            session_id=session.id,
        )
        pos = await any_store.get_position("AAPL")
        assert pos.quantity == 200
        assert pos.average_price == pytest.approx(1.5)

        # A repeated source_fill_id is a dedup no-op — folding is unaffected.
        await any_store.append_fill(
            buy.id,
            "AAPL",
            OrderSide.BUY,
            100,
            2.0,
            source_fill_id="fill-2",
            session_id=session.id,
        )
        pos_after_dup = await any_store.get_position("AAPL")
        assert pos_after_dup.quantity == 200
        assert pos_after_dup.average_price == pytest.approx(1.5)

        fills = await any_store.list_fills(order_id=buy.id)
        assert len(fills) == 2  # the duplicate never became a third row


# --------------------------------------------------------------------------- #
# Flow 5 — kill switch / session model vs. ADR-003 / Spine v2 §8
# --------------------------------------------------------------------------- #
class TestCharacterizeKillSwitchModel:
    """MIGRATED (wave 3d, event_truth): session control is now the three-state
    ``TradingState`` FSM (§8) — ``Active`` / ``Reducing`` / ``Halted`` — the two
    legacy booleans (``kill_switch`` / ``buys_paused``) are co-written read-models
    that map onto it (kill → ``Halted``, else pause → ``Reducing``, else
    ``Active``; kill dominates). ``set_kill_switch`` first-writes a
    ``TRADING_STATE_CHANGED`` ``ExecutionEvent`` (durable FSM truth); the
    predicates that gate submission read the FSM.

    A ``PROTECTION_FLOOR`` sell IS blocked in ``Halted`` (unlike
    ``MANUAL_FLATTEN`` — see ``TestCharacterizeManualFlatten`` above), matching
    ADR-003. The graded ``Reducing``-allows-reduce-only nuance the binary flag
    could not express is pinned in
    ``tests/test_spine_phase3d_trading_state.py`` (``TestReducingIsReduceOnly``);
    this test pins the end-to-end monitoring path: a kill → ``Halted`` holds an
    autonomous protection exit.
    """

    async def test_kill_switch_maps_to_halted_and_blocks_protection_floor_claim(
        self, any_store
    ):
        await any_store.initialize()
        await _hold(any_store, "AAPL", 100)
        session = await any_store.get_current_session()
        # An un-killed, un-paused session is ACTIVE; the booleans remain as
        # co-written read-models consistent with the FSM.
        assert session.trading_state is TradingState.ACTIVE
        assert session.kill_switch is False and session.buys_paused is False

        intent = await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )
        await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
        order = await any_store.create_order_for_sell_intent(
            intent.id, order_type=OrderType.MARKET
        )
        killed = await any_store.set_kill_switch(True)
        # event_truth: the setter moved the FSM to HALTED (kill dominates), and
        # the event log agrees with the co-written column.
        assert killed.trading_state is TradingState.HALTED
        assert await any_store.current_trading_state() is TradingState.HALTED

        adapter = MockBrokerAdapter()
        await run_monitoring_tick(any_store, adapter, Settings())

        # In HALTED, a protection_floor SELL IS held (ADR-003) — the exit stays
        # CREATED, wound down separately rather than autonomously submitted.
        held = await any_store.get_order(order.id)
        assert held.status is OrderStatus.CREATED

    async def test_pause_buys_maps_to_reducing(self, any_store):
        # The other FSM edge: buys-paused (no kill) is REDUCING, not HALTED.
        await any_store.initialize()
        paused = await any_store.set_buys_paused(True)
        assert paused.trading_state is TradingState.REDUCING
        assert await any_store.current_trading_state() is TradingState.REDUCING
