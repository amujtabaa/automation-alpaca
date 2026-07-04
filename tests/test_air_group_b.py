"""AIR remediation Group B — temporal / recovery regressions (AIR-001/002/003).

Red-then-green pins for the durable submission/fill recovery fixes:

* **B1 · AIR-001** — no order persists ``SUBMITTED`` without a non-empty broker
  order id (planner invariant + monitoring validation + adapter contract).
* **B2 · AIR-003** — a stale ``SUBMITTING`` order (``broker_order_id=None``,
  e.g. a crash between claim and submit) is re-driven through the idempotent
  ``submit_order`` on the next tick, or escalated to a durable ``needs_review``
  recovery record — never silently stranded, never blind-retried.
* **B3 · AIR-002** — a broker/local fill divergence (broker reports more filled
  than we could record) yields a durable operator-visible ``needs_review``
  reconciliation record; positions still derive only from appended fills.

Store-facing behavior is parametrized over both stores via ``any_store``.
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerError, BrokerOrderUpdate, TerminalBrokerError
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    OrderSide,
    OrderStatus,
)
from app.monitoring import run_monitoring_tick
from app.store.base import CLAIM_CLAIMED, OrderTransitionError

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _submitting_order(store):
    """A claimed order sitting in ``SUBMITTING`` with ``broker_order_id=None`` —
    exactly the durable state a crash between claim and submit leaves behind."""

    await store.initialize()
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=100, suggested_limit_price=1.0
    )
    order = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 100, limit_price=1.0
    )
    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
    assert claim.order.status is OrderStatus.SUBMITTING
    assert claim.order.broker_order_id is None
    return claim.order


async def _submitted_order(store, adapter, *, broker_order_id="broker-x"):
    """An order advanced to ``SUBMITTED`` with a real broker id (the sanctioned
    claim path), ready for reconcile-side divergence tests."""

    order = await _submitting_order(store)
    await store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id=broker_order_id
    )
    return await store.get_order(order.id)


# --------------------------------------------------------------------------- #
# B1 · AIR-001 — no SUBMITTED without a real broker id
# --------------------------------------------------------------------------- #
class TestAir001NoSubmittedWithoutBrokerId:
    @pytest.mark.parametrize("bad_id", [None, "", "   "])
    async def test_store_rejects_submitted_without_broker_id(self, any_store, bad_id):
        order = await _submitting_order(any_store)
        with pytest.raises(OrderTransitionError):
            await any_store.transition_order(
                order.id, OrderStatus.SUBMITTED, broker_order_id=bad_id
            )
        # Nothing moved: the order is still SUBMITTING, still id-less.
        fresh = await any_store.get_order(order.id)
        assert fresh.status is OrderStatus.SUBMITTING
        assert fresh.broker_order_id is None

    async def test_store_accepts_submitted_with_broker_id(self, any_store):
        order = await _submitting_order(any_store)
        updated = await any_store.transition_order(
            order.id, OrderStatus.SUBMITTED, broker_order_id="alpaca-123"
        )
        assert updated.status is OrderStatus.SUBMITTED
        assert updated.broker_order_id == "alpaca-123"
        assert updated.submitted_at is not None

    async def test_monitoring_empty_broker_id_not_marked_submitted(self, any_store):
        # A (buggy) adapter that returns an empty id must never leave an order
        # SUBMITTED-but-untrackable. The submit is treated as failed; the order
        # releases back to CREATED (re-drivable next tick), never SUBMITTED.
        await any_store.initialize()
        candidate = await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=1.0
        )
        order = await any_store.create_order_for_test(
            candidate.id, "AAPL", OrderSide.BUY, 10, limit_price=1.0
        )

        class _EmptyIdAdapter(MockBrokerAdapter):
            async def submit_order(self, order):  # noqa: D401
                self.submitted.append(order)
                return ""  # contract violation

        adapter = _EmptyIdAdapter()
        await run_monitoring_tick(any_store, adapter, Settings())

        fresh = await any_store.get_order(order.id)
        assert fresh.status is not OrderStatus.SUBMITTED
        assert fresh.broker_order_id is None


# --------------------------------------------------------------------------- #
# B2 · AIR-003 — recover stale SUBMITTING via idempotent re-drive
# --------------------------------------------------------------------------- #
class TestAir003StaleSubmittingRecovery:
    async def test_stale_submitting_redriven_to_submitted(self, any_store):
        order = await _submitting_order(any_store)
        adapter = MockBrokerAdapter()

        await run_monitoring_tick(any_store, adapter, Settings())

        fresh = await any_store.get_order(order.id)
        assert fresh.status is OrderStatus.SUBMITTED
        assert fresh.broker_order_id == f"broker-{order.id}"
        # It was re-driven through submit_order (idempotent by client_order_id).
        assert order.id in [o.id for o in adapter.submitted]

    async def test_stale_submitting_transient_error_stays_submitting(self, any_store):
        order = await _submitting_order(any_store)
        adapter = MockBrokerAdapter()
        adapter.fail_next_submit(BrokerError("transient network blip"))

        await run_monitoring_tick(any_store, adapter, Settings())

        fresh = await any_store.get_order(order.id)
        # Left SUBMITTING to retry next tick — never stranded, never a needs_review.
        assert fresh.status is OrderStatus.SUBMITTING
        assert fresh.broker_order_id is None
        assert await any_store.list_submit_recoveries() == []

    async def test_stale_submitting_terminal_error_escalates_needs_review(
        self, any_store
    ):
        order = await _submitting_order(any_store)
        adapter = MockBrokerAdapter()
        adapter.fail_next_submit(
            TerminalBrokerError("broker rejected; cannot confirm by client id")
        )

        await run_monitoring_tick(any_store, adapter, Settings())

        recoveries = await any_store.list_submit_recoveries(
            statuses=RECOVERY_OPEN_STATUSES
        )
        assert len(recoveries) == 1
        rec = recoveries[0]
        assert rec.local_order_id == order.id
        assert rec.cleanup_status == RECOVERY_NEEDS_REVIEW

    async def test_transient_livelock_escalates_after_max_attempts(self, any_store):
        # AIR-003 review backstop: a permanent rejection that an adapter MISCLASSIFIES
        # as transient (plain BrokerError) must not retry every tick forever. After
        # stale_submitting_max_redrive_attempts consecutive transient failures the
        # order is escalated to a durable needs_review record instead of re-driven.
        order = await _submitting_order(any_store)

        class _AlwaysTransient(MockBrokerAdapter):
            async def submit_order(self, order):  # noqa: D401
                self.submitted.append(order)
                raise BrokerError("permanent failure masquerading as transient")

        adapter = _AlwaysTransient()
        settings = Settings(stale_submitting_max_redrive_attempts=3)

        # Ticks 1-3: transient failures, deferred, order stays SUBMITTING, no record.
        for _ in range(3):
            await run_monitoring_tick(any_store, adapter, settings)
        assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING
        assert await any_store.list_submit_recoveries() == []
        submits_at_cap = len(adapter.submitted)

        # Tick 4: cap reached -> escalate to needs_review, do NOT submit again.
        await run_monitoring_tick(any_store, adapter, settings)
        recoveries = await any_store.list_submit_recoveries(
            statuses=RECOVERY_OPEN_STATUSES
        )
        assert len(recoveries) == 1
        assert recoveries[0].cleanup_status == RECOVERY_NEEDS_REVIEW
        assert len(adapter.submitted) == submits_at_cap  # bounded — no more re-drives

    async def test_stale_submitting_needs_review_not_redriven_again(self, any_store):
        # Once escalated, the order is not re-driven every tick (deduped by the
        # open recovery record) — no second record, no repeated submit attempt.
        await _submitting_order(any_store)
        adapter = MockBrokerAdapter()
        adapter.fail_next_submit(TerminalBrokerError("terminal"))

        await run_monitoring_tick(any_store, adapter, Settings())
        submits_after_first = len(adapter.submitted)
        await run_monitoring_tick(any_store, adapter, Settings())

        assert len(adapter.submitted) == submits_after_first  # no re-drive
        assert len(await any_store.list_submit_recoveries()) == 1


# --------------------------------------------------------------------------- #
# B3 · AIR-002 — durable broker/local fill divergence escalation
# --------------------------------------------------------------------------- #
class TestAir002FillDivergence:
    async def test_broker_reports_more_filled_than_recorded_escalates(self, any_store):
        order = await _submitted_order(any_store, None)
        adapter = MockBrokerAdapter()
        # Broker says 10 filled but emits NO recordable fill (unpriceable — the
        # adapter refused to synthesize a 0.0 price, AIR-002).
        adapter._broker_ids[order.id] = order.broker_order_id
        adapter.set_response(
            order.broker_order_id, BrokerOrderUpdate(OrderStatus.FILLED, 10, [])
        )

        await run_monitoring_tick(any_store, adapter, Settings())

        # Durable operator-visible reconciliation record.
        recoveries = await any_store.list_submit_recoveries(
            statuses=RECOVERY_OPEN_STATUSES
        )
        assert len(recoveries) == 1
        assert recoveries[0].cleanup_status == RECOVERY_NEEDS_REVIEW
        # Position still derives only from appended fills — no phantom 10 shares.
        fresh = await any_store.get_order(order.id)
        assert fresh.filled_quantity == 0
        assert fresh.status is not OrderStatus.FILLED
        assert (await any_store.get_position("AAPL")).quantity == 0

    async def test_broker_canceled_with_unrecordable_fill_not_silently_terminal(
        self, any_store
    ):
        order = await _submitted_order(any_store, None)
        adapter = MockBrokerAdapter()
        adapter._broker_ids[order.id] = order.broker_order_id
        # Broker CANCELED but reports 10 filled we could not record — the order
        # must NOT go terminal CANCELED discarding a real (untracked) position.
        adapter.set_response(
            order.broker_order_id, BrokerOrderUpdate(OrderStatus.CANCELED, 10, [])
        )

        await run_monitoring_tick(any_store, adapter, Settings())

        fresh = await any_store.get_order(order.id)
        assert fresh.status not in (OrderStatus.CANCELED, OrderStatus.FILLED)
        recoveries = await any_store.list_submit_recoveries(
            statuses=RECOVERY_OPEN_STATUSES
        )
        assert len(recoveries) == 1
        assert recoveries[0].cleanup_status == RECOVERY_NEEDS_REVIEW

    async def test_cancel_pending_divergence_stays_cancel_pending(self, any_store):
        # A fill divergence on an order already winding down must not revert it to
        # an open status (CHAOS-1) nor finalize it CANCELED discarding the shares.
        order = await _submitted_order(any_store, None)
        await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)
        adapter = MockBrokerAdapter()
        adapter._broker_ids[order.id] = order.broker_order_id
        adapter.set_response(
            order.broker_order_id, BrokerOrderUpdate(OrderStatus.CANCELED, 10, [])
        )

        await run_monitoring_tick(any_store, adapter, Settings())

        fresh = await any_store.get_order(order.id)
        assert fresh.status is OrderStatus.CANCEL_PENDING
        recoveries = await any_store.list_submit_recoveries(
            statuses=RECOVERY_OPEN_STATUSES
        )
        assert len(recoveries) == 1
        assert recoveries[0].cleanup_status == RECOVERY_NEEDS_REVIEW

    async def test_fill_divergence_deduped_across_ticks(self, any_store):
        order = await _submitted_order(any_store, None)
        adapter = MockBrokerAdapter()
        adapter._broker_ids[order.id] = order.broker_order_id
        adapter.set_response(
            order.broker_order_id, BrokerOrderUpdate(OrderStatus.FILLED, 10, [])
        )

        await run_monitoring_tick(any_store, adapter, Settings())
        await run_monitoring_tick(any_store, adapter, Settings())

        # Exactly one durable record despite two diverging ticks.
        assert len(await any_store.list_submit_recoveries()) == 1
