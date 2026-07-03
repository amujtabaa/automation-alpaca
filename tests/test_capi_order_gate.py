"""CAPI pre-trade risk gate (D-016) — store-level authoritative check.

Run through ``any_store`` so InMemoryStateStore and SqliteStateStore reject
identical inputs (the parity the store-hardening interlude exists to
guarantee) — the CAPI check is now part of ``create_order_for_candidate``'s
atomic "candidate approval + order creation + audit event" group, same as
every other guard in that handoff.
"""

from __future__ import annotations

import pytest

from app.models import CandidateStatus, OrderSide, OrderStatus
from app.store.base import RiskLimitBlockedError, RiskLimits
from tests.store_helpers import submit_created_order

pytestmark = pytest.mark.anyio


async def _approved_candidate(store, *, symbol="AAPL", quantity=10, limit=1.50):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol,
        strategy="mock",
        reason="exercise CAPI",
        suggested_quantity=quantity,
        suggested_limit_price=limit,
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.get_candidate(candidate.id)


class TestNoLimitsConfigured:
    async def test_default_none_limits_never_block(self, any_store):
        """The back-compat default (every limit None) behaves exactly as
        before Phase 6 — this is what keeps ~20 pre-existing test call sites
        unchanged."""

        candidate = await _approved_candidate(any_store, quantity=1_000_000, limit=999.0)

        order = await any_store.create_order_for_candidate(candidate.id)

        assert order.quantity == 1_000_000


class TestMaxSharesPerOrder:
    async def test_within_limit_succeeds(self, any_store):
        candidate = await _approved_candidate(any_store, quantity=50)

        order = await any_store.create_order_for_candidate(
            candidate.id, risk_limits=RiskLimits(max_shares_per_order=100)
        )

        assert order.quantity == 50

    async def test_exactly_at_limit_succeeds(self, any_store):
        """The cap is inclusive (``>``, not ``>=``) — an order of exactly
        max_shares_per_order shares must NOT block. Nothing in the example
        tests above exercises this exact boundary; without it, a regression
        that silently tightened the comparison to ``>=`` would go unnoticed."""

        candidate = await _approved_candidate(any_store, quantity=100)

        order = await any_store.create_order_for_candidate(
            candidate.id, risk_limits=RiskLimits(max_shares_per_order=100)
        )

        assert order.quantity == 100

    async def test_over_limit_blocks_and_leaves_candidate_pending(self, any_store):
        candidate = await _approved_candidate(any_store, quantity=150)

        with pytest.raises(RiskLimitBlockedError):
            await any_store.create_order_for_candidate(
                candidate.id, risk_limits=RiskLimits(max_shares_per_order=100)
            )

        # Not stranded APPROVED — the caller (route) reverts on this error;
        # at the store level we just assert no order was created and no
        # partial state change happened.
        assert await any_store.list_orders() == []

    async def test_blocked_order_writes_risk_limit_blocked_event(self, any_store):
        candidate = await _approved_candidate(any_store, quantity=150)

        with pytest.raises(RiskLimitBlockedError):
            await any_store.create_order_for_candidate(
                candidate.id, risk_limits=RiskLimits(max_shares_per_order=100)
            )

        events = await any_store.list_events(event_type="risk_limit_blocked")
        assert len(events) == 1
        assert events[0].payload["reason"] == "exceeds_max_shares_per_order"
        assert events[0].candidate_id == candidate.id


class TestMaxNotionalPerOrder:
    async def test_exactly_at_limit_succeeds(self, any_store):
        candidate = await _approved_candidate(any_store, quantity=100, limit=5.0)  # $500

        order = await any_store.create_order_for_candidate(
            candidate.id, risk_limits=RiskLimits(max_notional_per_order=500.0)
        )

        assert order.quantity == 100

    async def test_over_limit_blocks(self, any_store):
        candidate = await _approved_candidate(any_store, quantity=100, limit=10.0)  # $1000

        with pytest.raises(RiskLimitBlockedError):
            await any_store.create_order_for_candidate(
                candidate.id, risk_limits=RiskLimits(max_notional_per_order=500.0)
            )


class TestMaxTotalExposure:
    async def test_existing_position_counts_toward_the_cap(self, any_store):
        """A held position's cost basis is part of exposure — a new order
        that alone would be small can still breach the cap once existing
        exposure is accounted for."""

        await any_store.initialize()
        # Seed an existing $900 position via a real fill against a filled
        # order, then transition the order to FILLED with the matching
        # filled_quantity — exactly the two-call sequence app/monitoring.py's
        # _apply_update always performs (append_fill, then transition_order).
        # Skipping the transition_order call would leave the order SUBMITTED
        # with filled_quantity=0, silently double-counting the $900 fill (see
        # test_fill_without_order_transition_is_not_double_counted below) and
        # this test's own numeric assertion below exists specifically to
        # catch that regression, not just the raise.
        seed_candidate = await any_store.create_candidate(
            "MSFT", suggested_quantity=10, suggested_limit_price=90.0
        )
        await any_store.transition_candidate(seed_candidate.id, CandidateStatus.APPROVED)
        seed_order = await any_store.create_order_for_candidate(seed_candidate.id)
        await submit_created_order(any_store, seed_order.id)
        await any_store.append_fill(seed_order.id, "MSFT", OrderSide.BUY, 10, 90.0)
        await any_store.transition_order(
            seed_order.id, OrderStatus.FILLED, filled_quantity=10
        )
        assert (await any_store.get_position("MSFT")).cost_basis == 900.0
        assert await any_store.current_exposure() == 900.0

        candidate = await _approved_candidate(any_store, symbol="AAPL", quantity=10, limit=20.0)  # $200

        with pytest.raises(RiskLimitBlockedError):
            # 900 (existing) + 200 (new) = 1100 > 1000 cap
            await any_store.create_order_for_candidate(
                candidate.id, risk_limits=RiskLimits(max_total_exposure=1000.0)
            )

    async def test_fill_without_order_transition_is_not_double_counted(self, any_store):
        """A fill recorded via append_fill(), before the matching
        transition_order() call catches the order's filled_quantity up, must
        not be counted twice (once via the position's already-updated cost
        basis, again via the order's stale 'remaining' notional) — the exact
        window app/monitoring.py's _apply_update leaves open between its two
        separate calls for a single broker fill."""

        await any_store.initialize()
        candidate = await any_store.create_candidate(
            "MSFT", suggested_quantity=100, suggested_limit_price=9.0
        )
        await any_store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
        order = await any_store.create_order_for_candidate(candidate.id)
        await submit_created_order(any_store, order.id)

        await any_store.append_fill(order.id, "MSFT", OrderSide.BUY, 100, 9.0)
        # transition_order deliberately NOT called yet: order.filled_quantity
        # is still 0 even though the fill is fully recorded.
        assert await any_store.current_exposure() == 900.0  # not 1800.0

    async def test_open_order_notional_counts_toward_the_cap(self, any_store):
        """A still-open (non-terminal) order's remaining notional is live
        risk too — it must count even though nothing has filled yet."""

        first = await _approved_candidate(any_store, symbol="MSFT", quantity=10, limit=90.0)
        await any_store.create_order_for_candidate(first.id)  # CREATED, $900, unfilled

        second = await _approved_candidate(any_store, symbol="AAPL", quantity=10, limit=20.0)

        with pytest.raises(RiskLimitBlockedError):
            await any_store.create_order_for_candidate(
                second.id, risk_limits=RiskLimits(max_total_exposure=1000.0)
            )

    async def test_exactly_at_limit_succeeds(self, any_store):
        candidate = await _approved_candidate(any_store, symbol="AAPL", quantity=100, limit=10.0)  # $1000

        order = await any_store.create_order_for_candidate(
            candidate.id, risk_limits=RiskLimits(max_total_exposure=1000.0)
        )

        assert order.quantity == 100

    async def test_terminal_order_does_not_count(self, any_store):
        """A CANCELED order's notional must not linger in the exposure total."""

        first = await _approved_candidate(any_store, symbol="MSFT", quantity=10, limit=90.0)
        first_order = await any_store.create_order_for_candidate(first.id)
        await any_store.transition_order(first_order.id, OrderStatus.CANCELED)

        second = await _approved_candidate(any_store, symbol="AAPL", quantity=10, limit=20.0)

        # 0 (canceled doesn't count) + 200 (new) = 200 <= 1000 cap -> allowed
        order = await any_store.create_order_for_candidate(
            second.id, risk_limits=RiskLimits(max_total_exposure=1000.0)
        )
        assert order.symbol == "AAPL"


class TestAllowlist:
    async def test_symbol_on_allowlist_succeeds(self, any_store):
        candidate = await _approved_candidate(any_store, symbol="AAPL")

        order = await any_store.create_order_for_candidate(
            candidate.id, risk_limits=RiskLimits(allowlist=frozenset({"AAPL", "MSFT"}))
        )

        assert order.symbol == "AAPL"

    async def test_symbol_not_on_allowlist_blocks(self, any_store):
        candidate = await _approved_candidate(any_store, symbol="TSLA")

        with pytest.raises(RiskLimitBlockedError):
            await any_store.create_order_for_candidate(
                candidate.id, risk_limits=RiskLimits(allowlist=frozenset({"AAPL", "MSFT"}))
            )

    async def test_empty_allowlist_means_unrestricted(self, any_store):
        candidate = await _approved_candidate(any_store, symbol="ZZZZ")

        order = await any_store.create_order_for_candidate(
            candidate.id, risk_limits=RiskLimits(allowlist=frozenset())
        )

        assert order.symbol == "ZZZZ"


class TestIdempotency:
    async def test_already_ordered_candidate_is_idempotent_even_under_tight_limits(
        self, any_store
    ):
        """A candidate that's already ORDERED returns its existing order and
        writes nothing (matching the pre-Phase-6 idempotency contract) even
        when the limits passed on the re-call would have blocked a *new*
        order — idempotent replay must never retroactively fail."""

        candidate = await _approved_candidate(any_store, quantity=50)
        first = await any_store.create_order_for_candidate(candidate.id)

        second = await any_store.create_order_for_candidate(
            candidate.id,
            risk_limits=RiskLimits(max_shares_per_order=1),  # would block if evaluated fresh
        )

        assert second.id == first.id
