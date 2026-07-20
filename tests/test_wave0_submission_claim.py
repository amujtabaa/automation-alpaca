"""Wave 0 — F-001 / F-002 (D-017): the atomic submission claim closes the
kill-switch/session-close race against broker submission.

The claim (``CREATED -> SUBMITTING`` under one store-lock hold, re-checking every
control) is the *only* path to the broker, so a control flip lands either before
the claim (order held) or after it (already committed to submission) — never in
the undetectable window the old read-then-await-then-mark flow left open.

Store-level cases run through ``any_store`` for memory/SQLite parity. Loop-level
cases use the controllable ``MockBrokerAdapter`` (no network, Rule 9).
"""

from __future__ import annotations

import pytest

from app.broker.adapter import BrokerError
from app.broker.mock import MockBrokerAdapter
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_OPEN_STATUSES,
    RECOVERY_RESOLVED,
    RECOVERY_UNRESOLVED,
    CandidateStatus,
    OrderSide,
    OrderStatus,
)
from app.monitoring import _submit_pending_orders
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    CLAIM_SKIPPED,
    UnknownEntityError,
)
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


async def _created_order(store, *, symbol="AAPL", qty=10, limit=1.0):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(candidate.id)


# --------------------------------------------------------------------------- #
# Store-level claim mechanics (parity)
# --------------------------------------------------------------------------- #
class TestClaimMechanics:
    async def test_claim_moves_created_to_submitting_and_audits(self, any_store):
        order = await _created_order(any_store)
        claim = await any_store.claim_order_for_submission(order.id)
        assert claim.outcome == CLAIM_CLAIMED
        assert claim.order.status is OrderStatus.SUBMITTING
        assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING
        assert any(
            e.event_type == "order_submission_claimed" and e.order_id == order.id
            for e in await any_store.list_events()
        )

    async def test_claim_blocked_under_kill_switch_leaves_created(self, any_store):
        order = await _created_order(any_store)
        await any_store.set_kill_switch(True)
        claim = await any_store.claim_order_for_submission(order.id)
        assert claim.outcome == CLAIM_BLOCKED
        assert claim.reason == "kill_switch" or claim.reason == "current_kill_switch"
        # No state change: still CREATED, re-claimable once the stop clears.
        assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED

    async def test_claim_blocked_under_buys_paused(self, any_store):
        order = await _created_order(any_store)
        await any_store.set_buys_paused(True)
        claim = await any_store.claim_order_for_submission(order.id)
        assert claim.outcome == CLAIM_BLOCKED
        assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED

    async def test_reclaim_of_claimed_order_is_skipped(self, any_store):
        order = await _created_order(any_store)
        assert (
            await any_store.claim_order_for_submission(order.id)
        ).outcome == CLAIM_CLAIMED
        # Already SUBMITTING -> a second claim is a no-op skip (no double submit).
        again = await any_store.claim_order_for_submission(order.id)
        assert again.outcome == CLAIM_SKIPPED

    async def test_session_close_does_not_cancel_a_submitting_order(self, any_store):
        """A claimed (SUBMITTING) order must survive a session close — it is
        committed to submission. Only never-claimed CREATED orders are cancelled
        at close (D-013a). This is the F-002 fix: close can't race the submit."""

        claimed = await _created_order(any_store, symbol="AAPL")
        await any_store.claim_order_for_submission(claimed.id)  # -> SUBMITTING
        held = await _created_order(any_store, symbol="MSFT")  # stays CREATED

        await any_store.close_session()

        assert (await any_store.get_order(claimed.id)).status is OrderStatus.SUBMITTING
        assert (await any_store.get_order(held.id)).status is OrderStatus.CANCELED


# --------------------------------------------------------------------------- #
# Broker-submit recovery ledger CRUD (parity, D-017 / F-002)
# --------------------------------------------------------------------------- #
class TestRecoveryLedger:
    async def _record(self, store):
        await store.initialize()
        return await store.create_submit_recovery(
            local_order_id="o1",
            broker_order_id="bk-1",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            limit_price=1.5,
            failure_reason="unpersisted",
            session_id="s1",
        )

    async def test_create_records_and_audits(self, any_store):
        rec = await self._record(any_store)
        assert rec.cleanup_status == "unresolved"
        assert rec.retry_count == 0
        listed = await any_store.list_submit_recoveries()
        assert [r.id for r in listed] == [rec.id]
        assert any(
            e.event_type == "submit_recovery_recorded" and e.order_id == "o1"
            for e in await any_store.list_events()
        )

    async def test_status_filter(self, any_store):
        rec = await self._record(any_store)
        # Open view (the operator/loop filter) includes unresolved.
        assert (
            len(await any_store.list_submit_recoveries(statuses=RECOVERY_OPEN_STATUSES))
            == 1
        )
        await any_store.update_submit_recovery(rec.id, cleanup_status=RECOVERY_RESOLVED)
        # A cleanly-resolved record drops out of the open view but stays in history.
        assert (
            await any_store.list_submit_recoveries(statuses=RECOVERY_OPEN_STATUSES)
            == []
        )
        assert len(await any_store.list_submit_recoveries()) == 1

    async def test_needs_review_stays_in_the_open_operator_view(self, any_store):
        """A needs_review record (a real untracked position) must NOT drop out of
        the operator surface the way a cleanly-cancelled one does — the operator
        has to see it until a human reconciles it (F-006/#4)."""

        rec = await self._record(any_store)
        await any_store.update_submit_recovery(
            rec.id, cleanup_status=RECOVERY_NEEDS_REVIEW
        )
        open_records = await any_store.list_submit_recoveries(
            statuses=RECOVERY_OPEN_STATUSES
        )
        assert [r.id for r in open_records] == [rec.id]
        # But the recovery loop's own filter (strictly unresolved) excludes it —
        # it must not keep re-cancelling a needs-review record.
        assert (
            await any_store.list_submit_recoveries(statuses={RECOVERY_UNRESOLVED}) == []
        )
        # And it wrote a needs-review event, not a "resolved" one.
        types = {e.event_type for e in await any_store.list_events()}
        assert "submit_recovery_needs_review" in types
        assert "submit_recovery_resolved" not in types

    async def test_bump_attempt_increments_and_stamps(self, any_store):
        rec = await self._record(any_store)
        updated = await any_store.update_submit_recovery(rec.id, bump_attempt=True)
        assert updated.retry_count == 1
        assert updated.last_attempt_at is not None

    async def test_resolve_writes_resolved_event_once(self, any_store):
        rec = await self._record(any_store)
        await any_store.update_submit_recovery(
            rec.id, cleanup_status=RECOVERY_RESOLVED, bump_attempt=True
        )
        resolved_events = [
            e
            for e in await any_store.list_events()
            if e.event_type == "submit_recovery_resolved"
        ]
        assert len(resolved_events) == 1
        assert resolved_events[0].payload["cleanup_status"] == RECOVERY_RESOLVED

    async def test_update_unknown_raises(self, any_store):
        await any_store.initialize()
        with pytest.raises(UnknownEntityError):
            await any_store.update_submit_recovery("nope", bump_attempt=True)


# --------------------------------------------------------------------------- #
# Loop-level races (F-001)
# --------------------------------------------------------------------------- #
async def test_kill_switch_before_scan_blocks_submission():
    store = InMemoryStateStore()
    order = await _created_order(store)
    adapter = MockBrokerAdapter()
    await store.set_kill_switch(True)

    await _submit_pending_orders(store, adapter)

    assert adapter.submitted == []  # never reached the broker
    assert (await store.get_order(order.id)).status is OrderStatus.CREATED


class _FlipKillDuringSubmit(MockBrokerAdapter):
    """Flips the kill switch *inside* submit_order — i.e. after the claim has
    already committed the order to SUBMITTING. The correct semantics is that the
    order still submits (it was atomically claimed before the stop)."""

    def __init__(self, store) -> None:
        super().__init__()
        self._store = store

    async def submit_order(self, order, *, venue_scope):
        assert venue_scope is not None
        await self._store.set_kill_switch(True)
        return await super().submit_order(order, venue_scope=venue_scope)


async def test_kill_switch_flip_after_claim_still_submits():
    """The claim already committed the order (CREATED -> SUBMITTING) before the
    broker call, so a flip during the call does not un-claim it — the human
    approved it and the backend claimed it before the stop landed."""

    store = InMemoryStateStore()
    order = await _created_order(store)
    adapter = _FlipKillDuringSubmit(store)

    await _submit_pending_orders(store, adapter)

    assert [o.id for o in adapter.submitted] == [order.id]
    assert (await store.get_order(order.id)).status is OrderStatus.SUBMITTED
    assert (await store.get_current_session()).kill_switch is True  # flip took effect


class _CloseSessionThenFailSubmit(MockBrokerAdapter):
    """Closes the order's session *inside* submit_order (after the claim moved
    it to SUBMITTING, which close skips), then raises — reproducing a session
    close racing the submit call."""

    def __init__(self, store) -> None:
        super().__init__()
        self._store = store

    async def submit_order(self, order, *, venue_scope):
        assert venue_scope is not None
        self.submitted.append(order)  # record the attempt, as the real mock does
        await self._store.close_session()
        raise BrokerError("network blip during a closing session")


async def test_release_after_submit_failure_into_closed_session_cancels_not_strands():
    """If the order's own session closed during the submit await, releasing the
    claim to CREATED would strand a zombie CREATED order in a closed session
    forever (close is one-shot; nothing else cleans it up), permanently inflating
    exposure. Instead it must be CANCELED — what close would have done to a
    CREATED order (regression guard for the pre-merge review's finding #2)."""

    store = InMemoryStateStore()
    order = await _created_order(store)
    adapter = _CloseSessionThenFailSubmit(store)

    await _submit_pending_orders(store, adapter)

    fresh = await store.get_order(order.id)
    assert fresh.status is OrderStatus.CANCELED  # not stranded CREATED
    assert [o.id for o in adapter.submitted] == [order.id]  # the broker was attempted


async def test_transient_submit_failure_releases_claim_and_reruns_gate():
    store = InMemoryStateStore()
    order = await _created_order(store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("network blip"))

    # First tick: claimed, submit raises, claim released back to CREATED.
    await _submit_pending_orders(store, adapter)
    assert (await store.get_order(order.id)).status is OrderStatus.CREATED

    # Second tick: submit succeeds, order reaches SUBMITTED.
    await _submit_pending_orders(store, adapter)
    fresh = await store.get_order(order.id)
    assert fresh.status is OrderStatus.SUBMITTED
    assert fresh.broker_order_id == adapter.broker_id_for(order.id)


async def test_transient_submit_failure_reruns_gate_and_holds_if_stopped():
    """If the kill switch flips while a transient submit failure has the order
    back at CREATED, the next tick's re-claim holds it — the release re-runs the
    FULL gate, so a flip during the retry window is honored."""

    store = InMemoryStateStore()
    order = await _created_order(store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("network blip"))

    await _submit_pending_orders(store, adapter)  # released back to CREATED
    await store.set_kill_switch(True)
    await _submit_pending_orders(store, adapter)  # re-claim now blocked

    assert (await store.get_order(order.id)).status is OrderStatus.CREATED
    # The one broker submit that failed is the only one attempted; the held
    # retry never reached the broker.
    assert len(adapter.submitted) == 1
