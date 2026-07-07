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
)
from app.monitoring import run_monitoring_tick
from app.position import NegativePositionError
from app.store.base import CLAIM_CLAIMED

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
    await store.append_fill(buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id)
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
    """CURRENT: a manual flatten unconditionally bypasses the kill switch —
    see ``app/store/core.py``'s claim-gate docstring: "MANUAL_FLATTEN -> never
    held: a human-commanded flatten always exits, even kill-switched
    /buys-paused/closed/unknown-session (D-P2)."

    ADR-003 CONFLICT (recorded, not resolved here): the target model denies
    ordinary manual flatten by default when ``TradingState`` is ``Halted``,
    permitting an exit only via an explicit, audited emergency-reduce
    override that scopes into ``Reducing``. This repo has no ``TradingState``
    and no such override — kill-switched today plays the role ``Halted``
    would, and manual flatten currently exits through it unconditionally.
    Migrating this is Phase 3 scope (``docs/REARCHITECTURE_ROADMAP.md``);
    this test exists so that migration has to consciously break this
    assertion, not silently drift past it.
    """

    async def test_manual_flatten_dispatches_and_submits_under_kill_switch(
        self, any_store, monkeypatch
    ):
        _force_regular_hours(monkeypatch)
        await any_store.initialize()
        await _hold(any_store, "AAPL", 100)
        await any_store.set_kill_switch(True)

        result = await any_store.flatten_position("AAPL")

        assert result.intent.reason is SellReason.MANUAL_FLATTEN
        assert result.intent.status is SellIntentStatus.ORDERED
        assert result.order.status is OrderStatus.CREATED

        # The claim gate also lets a CREATED manual_flatten SELL through the
        # submission claim itself, unmodified by the kill switch.
        adapter = MockBrokerAdapter()
        await run_monitoring_tick(any_store, adapter, Settings())
        submitted = await any_store.get_order(result.order.id)
        assert submitted.status is OrderStatus.SUBMITTED


# --------------------------------------------------------------------------- #
# Flow 2 — stale SUBMITTING retry vs. ADR-002 (timeout/504 ambiguity)
# --------------------------------------------------------------------------- #
class TestCharacterizeStaleSubmittingRetry:
    """CURRENT: a stale ``SUBMITTING`` order (submit's outcome is unknown — the
    exact ambiguity ADR-002 is about) is re-driven by calling
    ``adapter.submit_order`` again with the SAME ``client_order_id``, relying
    on Alpaca's own duplicate-client-order-id dedup to recover an
    already-accepted order rather than double-submitting. A transient
    ``BrokerError`` (which the adapter raises uniformly for network errors,
    429, AND 5xx/504 — see ``app/broker/alpaca_paper.py``'s ``submit_order``,
    which does not distinguish "definitely still in flight" from "definitely
    never reached the venue") just leaves the order ``SUBMITTING`` to retry
    next tick.

    ADR-002 CONFLICT (recorded, not resolved here): ADR-002's own Context
    section names this exact pattern as insufficient — "stable
    ``client_order_id`` and redrive logic... is valuable, but blind redrive
    is too permissive for ambiguous broker outcomes." The target model routes
    a timeout/504/ambiguous submit to a distinct ``TIMEOUT_QUARANTINE``
    spawn status and blocks a replacement spawn until a TARGETED
    reconciliation query (not just a resubmit-and-hope) confirms venue
    reality. No ``TIMEOUT_QUARANTINE`` status, and no pre-resubmit targeted
    query, exists in this repo. This test pins the current
    redrive-until-attempts-exhausted shape so that migrating it is a
    conscious Phase 3 decision.
    """

    async def test_transient_submit_failure_leaves_submitting_for_blind_redrive(
        self, any_store
    ):
        await any_store.initialize()
        order = await _submitting_order(any_store)
        adapter = MockBrokerAdapter()
        adapter.fail_next_submit(BrokerError("simulated network timeout"))

        await run_monitoring_tick(any_store, adapter, Settings())

        fresh = await any_store.get_order(order.id)
        # No TIMEOUT_QUARANTINE status exists; the order just stays SUBMITTING
        # (indistinguishable from "claimed, about to submit for the first
        # time") for an ordinary blind retry next tick.
        assert fresh.status is OrderStatus.SUBMITTING
        assert fresh.broker_order_id is None
        assert await any_store.list_submit_recoveries() == []

        # The blind redrive succeeds by re-submitting the SAME client_order_id
        # (order.id) — no targeted "does this already exist at the venue?"
        # query happens first.
        await run_monitoring_tick(any_store, adapter, Settings())
        redriven = await any_store.get_order(order.id)
        assert redriven.status is OrderStatus.SUBMITTED
        assert order.id in [o.id for o in adapter.submitted]


# --------------------------------------------------------------------------- #
# Flow 3 — broker-reported overfill/negative-position vs. ADR-001
# --------------------------------------------------------------------------- #
class TestCharacterizeBrokerOverfillHandling:
    """CURRENT: a fill that would drive the local position negative is
    REJECTED at ``append_fill`` — raises :class:`NegativePositionError`,
    appends no fill row, leaves the position untouched. This guard makes no
    distinction between a malformed/synthetic local input and a
    broker-authoritative fact reported through the real reconciliation path
    (``app.monitoring``'s fill-ingestion loop catches this exact exception via
    its ``_FILL_ERRORS`` tuple and treats it as "rejected," logging a warning
    and feeding the separate, narrower fill-divergence/``needs_review``
    escalation — see D-022 B3/AIR-002, ``app.monitoring._escalate_fill_
    divergence``) — but the broker's fill FACT itself is dropped from the
    fill/position ledger either way. There is no primary-level ``QUARANTINED``
    status, and no "block further autonomous spawned orders for this symbol"
    enforcement tied specifically to this fact.

    ADR-001 CONFLICT (recorded, not resolved here): the target model requires
    the broker-authoritative fact to be RECORDED (even though it violates the
    local no-oversell invariant), with the primary explicitly ``QUARANTINED``
    and blocked from further autonomous orders. Current behavior instead
    drops the broker fact from the position/fill ledger entirely. This test
    pins that reject-and-drop shape directly at the store boundary where the
    decision is actually made — the full broker/monitoring escalation path
    it triggers is separately covered by ``tests/test_air_group_b.py``'s
    ``TestAir002FillDivergence``.
    """

    async def test_fill_that_would_go_negative_is_rejected_and_position_unaffected(
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

        # The broker reports this SELL order fully filled at 150 shares — but
        # only 100 are actually held. A genuine broker-authoritative
        # overfill/negative-position fact, exactly like ADR-001 describes.
        with pytest.raises(NegativePositionError):
            await any_store.append_fill(
                sell.id, "AAPL", OrderSide.SELL, 150, 10.0, session_id=session.id
            )

        # The fact is dropped, not recorded-and-quarantined: no fill row, no
        # position change, no QUARANTINED status anywhere (none exists).
        position = await any_store.get_position("AAPL")
        assert position.quantity == 100
        fills = await any_store.list_fills(order_id=sell.id)
        assert fills == []


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
            buy.id, "AAPL", OrderSide.BUY, 100, 1.0,
            source_fill_id="fill-1", session_id=session.id,
        )
        await any_store.append_fill(
            buy.id, "AAPL", OrderSide.BUY, 100, 2.0,
            source_fill_id="fill-2", session_id=session.id,
        )
        pos = await any_store.get_position("AAPL")
        assert pos.quantity == 200
        assert pos.average_price == pytest.approx(1.5)

        # A repeated source_fill_id is a dedup no-op — folding is unaffected.
        await any_store.append_fill(
            buy.id, "AAPL", OrderSide.BUY, 100, 2.0,
            source_fill_id="fill-2", session_id=session.id,
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
    """CURRENT: session control is two independent booleans
    (``SessionRecord.kill_switch``, ``.buys_paused``) — there is no
    ``TradingState`` enum. A ``PROTECTION_FLOOR`` sell IS blocked by the kill
    switch (unlike ``MANUAL_FLATTEN`` — see
    ``TestCharacterizeManualFlatten`` above); a plain BUY is blocked by
    either flag.

    ADR-003/Spine v2 §8 CONFLICT (recorded, not resolved here): the target
    model is a three-state ``TradingState`` (``Active``/``Reducing``/
    ``Halted``) where ``Reducing`` explicitly ALLOWS reduce-only orders
    (cancels + reducing sells) while denying exposure-increasing ones — a
    graded state the current binary ``kill_switch`` flag cannot express.
    Migrating this is Phase 3 scope; this test pins today's binary-flag
    behavior for both the exempted (manual flatten) and non-exempted
    (protection floor) sell paths.
    """

    async def test_kill_switch_is_a_binary_flag_and_blocks_protection_floor_claim(
        self, any_store
    ):
        await any_store.initialize()
        await _hold(any_store, "AAPL", 100)
        session = await any_store.get_current_session()
        assert isinstance(session.kill_switch, bool)
        assert isinstance(session.buys_paused, bool)
        assert not hasattr(session, "trading_state")

        intent = await any_store.create_sell_intent(
            symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
            session_id=session.id,
        )
        await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
        order = await any_store.create_order_for_sell_intent(
            intent.id, order_type=OrderType.MARKET
        )
        await any_store.set_kill_switch(True)

        adapter = MockBrokerAdapter()
        await run_monitoring_tick(any_store, adapter, Settings())

        # Unlike manual_flatten, a protection_floor SELL IS held by the kill
        # switch today — there is no "Reducing allows reduce-only" nuance,
        # just blocked-or-not.
        held = await any_store.get_order(order.id)
        assert held.status is OrderStatus.CREATED
