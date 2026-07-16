"""Wave 0 — F-003 / F-005: hostile numeric input is rejected cleanly at BOTH
the store boundary and the market-data → feature → strategy boundary, via one
shared predicate (``app.policy.finite_number_reason``).

F-003 (reproduced firsthand pre-fix): a ``NaN`` ``filled_quantity`` slipped past
``transition_order``'s bare ``<``/``>`` comparisons (every comparison against
``NaN`` is ``False``) and persisted as ``nan`` in memory / raised a low-level
``IntegrityError`` in SQLite — a parity break where neither store gave a clean
domain rejection. F-005: non-finite market data produced a candidate with
``suggested_limit_price=inf`` instead of no candidate.

Store cases run through ``any_store`` so InMemoryStateStore and SqliteStateStore
reject identically with no persisted mutation. Market-data cases are pure.
"""

from __future__ import annotations

import math

import pytest

from app.features import pct_move, spread, spread_pct
from app.marketdata.service import MarketSnapshot
from app.models import CandidateStatus, OrderSide, OrderStatus, SessionType, utcnow
from app.store.base import InvalidFillError, InvalidOrderError
from app.strategy import evaluate
from tests.store_helpers import submit_created_order

pytestmark = pytest.mark.anyio

# Values that must be rejected as a share *count* (finite whole non-negative).
_HOSTILE_COUNTS = [math.nan, math.inf, -math.inf, 0.5, True, False, "5", -1]
# Values that must be rejected as a *price* (finite, fractional allowed).
_HOSTILE_PRICES = [math.nan, math.inf, -math.inf, True, "5", 0, -1]


async def _submitted_order(store, *, symbol="AAPL", qty=100, limit=2.0):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(candidate.id)
    await submit_created_order(store, order.id)
    return order


# --------------------------------------------------------------------------- #
# F-003 — store boundary, both stores, no persisted mutation
# --------------------------------------------------------------------------- #
class TestFilledQuantityHostileInput:
    @pytest.mark.parametrize(
        "bad", [math.nan, math.inf, -math.inf, 0.5, True, False, "5", -1]
    )
    async def test_transition_order_rejects_and_persists_nothing(self, any_store, bad):
        order = await _submitted_order(any_store)

        with pytest.raises(InvalidOrderError):
            await any_store.transition_order(
                order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=bad
            )

        # No partial mutation: still SUBMITTED, filled_quantity untouched (no
        # persisted `nan`, no IntegrityError leak — a clean domain rejection).
        refreshed = await any_store.get_order(order.id)
        assert refreshed.status is OrderStatus.SUBMITTED
        assert refreshed.filled_quantity == 0

    async def test_overfill_still_rejected(self, any_store):
        order = await _submitted_order(any_store, qty=100)
        with pytest.raises(InvalidOrderError):
            await any_store.transition_order(
                order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=101
            )


class TestFillQuantityHostileInput:
    @pytest.mark.parametrize(
        "bad", [math.nan, math.inf, -math.inf, 0, -1, 0.5, True, "5"]
    )
    async def test_append_fill_rejects_bad_quantity(self, any_store, bad):
        order = await _submitted_order(any_store)
        with pytest.raises(InvalidFillError):
            await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, bad, 2.0)
        assert await any_store.list_fills(order_id=order.id) == []
        assert (await any_store.get_position("AAPL")).quantity == 0


class TestFillPriceHostileInput:
    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 0, -1, "5", True])
    async def test_append_fill_rejects_bad_price(self, any_store, bad):
        order = await _submitted_order(any_store)
        with pytest.raises(InvalidFillError):
            await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, 10, bad)
        assert await any_store.list_fills(order_id=order.id) == []


# --------------------------------------------------------------------------- #
# F-005 — market-data / feature / strategy boundary (pure)
# --------------------------------------------------------------------------- #
class TestFeatureFiniteGuards:
    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_pct_move_none_on_non_finite(self, bad):
        assert pct_move(bad, 100.0) is None
        assert pct_move(100.0, bad) is None

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_spread_none_on_non_finite(self, bad):
        assert spread(bad, 2.0) is None
        assert spread(1.0, bad) is None

    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_spread_pct_none_on_non_finite(self, bad):
        assert spread_pct(bad, 2.0) is None
        assert spread_pct(1.0, bad) is None


class TestStrategyRejectsNonFiniteSnapshot:
    def _snapshot(self, **overrides):
        base = dict(
            symbol="AAPL",
            last_price=10.0,
            bid=9.99,
            ask=10.01,
            volume=1_000_000,
            prev_close=9.0,  # +11% move — would normally propose
            updated_at=utcnow(),
        )
        base.update(overrides)
        return MarketSnapshot(**base)

    def _evaluate(self, snapshot):
        return evaluate(
            "AAPL",
            snapshot,
            SessionType.PRE_MARKET,
            has_open_candidate=False,
            momentum_threshold_pct=2.0,
            min_volume=1000,
            max_spread_pct=1.0,
            limit_buffer_pct=0.5,
            default_quantity=10,
        )

    def test_baseline_finite_snapshot_proposes(self):
        # Sanity: a clean snapshot with these gates DOES propose, so the
        # non-finite cases below are genuinely suppressing a real proposal.
        assert self._evaluate(self._snapshot()) is not None

    @pytest.mark.parametrize(
        "field", ["last_price", "prev_close", "bid", "ask", "volume"]
    )
    @pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
    def test_non_finite_field_yields_no_candidate(self, field, bad):
        proposal = self._evaluate(self._snapshot(**{field: bad}))
        assert proposal is None  # never a candidate, never suggested_limit_price=inf


# --------------------------------------------------------------------------- #
# Phase-7 readiness follow-up — whole_count_reason genuinely wired in, not dead
# code, and the two silent-coercion gaps (bool/numeric-string suggested_quantity
# / suggested_limit_price surviving all the way to a persisted order with zero
# rejection) closed at the create_candidate boundary, both stores.
# --------------------------------------------------------------------------- #
class TestWholeCountReasonIsWiredIn:
    """``whole_count_reason`` was defined but had zero call sites — the two
    functions it exists to back (``fill_value_reason``/``filled_quantity_reason``)
    each re-implemented its finite/integer/non-negative logic inline instead of
    delegating. A Phase-7 readiness audit found this contradicts D-019's own
    "one shared guard" claim. Both now delegate; these pin that the reason codes
    produced are byte-identical to the pre-delegation strings (behavior-preserving)."""

    @pytest.mark.parametrize(
        "quantity,expected",
        [
            (True, "non_numeric_quantity"),
            ("5", "non_numeric_quantity"),
            (math.nan, "non_finite_quantity"),
            (math.inf, "non_finite_quantity"),
            (2.5, "non_integer_quantity"),
            (-5, "non_positive_quantity"),
            (0, "non_positive_quantity"),
            (10, None),
        ],
    )
    def test_fill_value_reason_quantity_reason_codes_unchanged(
        self, quantity, expected
    ):
        from app.policy import fill_value_reason

        assert fill_value_reason(quantity, 1.0) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (True, "non_numeric_filled_quantity"),
            ("5", "non_numeric_filled_quantity"),
            (math.nan, "non_finite_filled_quantity"),
            (2.5, "non_integer_filled_quantity"),
            (-5, "negative_filled_quantity"),
        ],
    )
    def test_filled_quantity_reason_reason_codes_unchanged(self, value, expected):
        from app.models import Order, OrderSide, OrderType
        from app.policy import filled_quantity_reason

        order = Order(
            candidate_id="c1",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            limit_price=1.0,
            filled_quantity=40,
        )
        assert filled_quantity_reason(order, value) == expected

    def test_whole_count_reason_has_real_callers(self):
        # Regression guard for the "orphaned single-source" finding itself:
        # both consolidated functions must route through it, not reimplement it.
        import inspect

        from app.policy import fill_value_reason, filled_quantity_reason

        assert "whole_count_reason" in inspect.getsource(fill_value_reason)
        assert "whole_count_reason" in inspect.getsource(filled_quantity_reason)


class TestCandidateCreationRejectsSilentTypeCoercion:
    """A ``bool`` or numeric ``str`` raw ``suggested_quantity``/
    ``suggested_limit_price`` silently coerces once pydantic builds the
    ``Candidate`` (``True`` -> ``1``, ``"5"`` -> ``5``, no error) — and once
    coerced, the type is unrecoverable, so a REAL PERSISTED ORDER could be
    created from it with zero rejection anywhere (a Phase-7 readiness audit
    reproduced this live against both stores). ``NaN``/``Inf``/fractional are
    unaffected (pydantic's own field validators already reject those on
    construction) and negative/zero suggested_quantity remain deferred to
    order-creation time (unchanged, existing behavior) — this guard is scoped
    exactly to the two genuinely silent cases."""

    @pytest.mark.parametrize("bad_quantity", [True, False, "5"])
    async def test_bool_or_string_suggested_quantity_rejected(
        self, any_store, bad_quantity
    ):
        from app.store.base import InvalidOrderError

        await any_store.initialize()
        with pytest.raises(InvalidOrderError):
            await any_store.create_candidate(
                "AAPL", suggested_quantity=bad_quantity, suggested_limit_price=1.0
            )
        assert await any_store.list_candidates() == []  # no persisted mutation

    @pytest.mark.parametrize("bad_price", [True, "5.0"])
    async def test_bool_or_string_suggested_limit_price_rejected(
        self, any_store, bad_price
    ):
        from app.store.base import InvalidOrderError

        await any_store.initialize()
        with pytest.raises(InvalidOrderError):
            await any_store.create_candidate(
                "AAPL", suggested_quantity=10, suggested_limit_price=bad_price
            )
        assert await any_store.list_candidates() == []

    async def test_none_and_valid_numbers_still_pass(self, any_store):
        # The guard must not become a new footgun: unset (None) and genuine
        # int/float values are unaffected.
        await any_store.initialize()
        cand = await any_store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=1.5
        )
        assert cand.suggested_quantity == 10
        assert cand.suggested_limit_price == 1.5

        cand2 = await any_store.create_candidate("MSFT")
        assert cand2.suggested_quantity is None
        assert cand2.suggested_limit_price is None

    async def test_previously_silent_bool_quantity_no_longer_reaches_an_order(
        self, any_store
    ):
        # The concrete failure the audit reproduced: True silently became
        # quantity=1 on a real, persisted Order. Now it never gets that far.
        from app.store.base import InvalidOrderError

        await any_store.initialize()
        with pytest.raises(InvalidOrderError):
            await any_store.create_candidate(
                "AAPL", suggested_quantity=True, suggested_limit_price=1.0
            )
        assert await any_store.list_orders() == []
