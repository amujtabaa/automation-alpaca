"""Hypothesis property tests for the Phase 6 CAPI risk gate (D-016).

Example-based tests (``tests/test_store_core.py``, the store parity tests)
pin specific scenarios; these pin the *invariants* — properties that must
hold for every input in the domain, not just the cases someone thought to
write down. Exposure/limit math is exactly the kind of logic where an
off-by-one or a sign error slips past hand-picked examples but shows up
immediately under randomized search.

No IO, no store, no async — pure functions over synthetic ``Position``/
``Order`` objects (Rule 9).
"""

from __future__ import annotations

from hypothesis import example, given, settings
from hypothesis import strategies as st

from app.models import Order, OrderSide, OrderStatus, OrderType, Position
from app.policy import existing_exposure, risk_limit_reason

# Realistic domains, not adversarial ones: existing_exposure/risk_limit_reason
# assume valid domain objects (Rule: validate at the boundary, trust internal
# data) — matching every other predicate in this module (fill_value_reason
# etc. are tested against realistic inputs elsewhere, not garbage).
_QUANTITY = st.integers(min_value=0, max_value=100_000)
_PRICE = st.floats(
    min_value=0.01, max_value=100_000, allow_nan=False, allow_infinity=False
)
_COST_BASIS = st.floats(
    min_value=0.0, max_value=10_000_000, allow_nan=False, allow_infinity=False
)
_SYMBOL = st.sampled_from(["AAPL", "MSFT", "TSLA", "GOOG", "AMZN"])
_ORDER_STATUS = st.sampled_from(list(OrderStatus))


@st.composite
def _positions(draw, max_size=5):
    return [
        Position(
            symbol=draw(_SYMBOL),
            quantity=draw(_QUANTITY),
            cost_basis=draw(_COST_BASIS),
        )
        for _ in range(draw(st.integers(min_value=0, max_value=max_size)))
    ]


@st.composite
def _orders(draw, max_size=5):
    out = []
    for _ in range(draw(st.integers(min_value=0, max_value=max_size))):
        quantity = draw(_QUANTITY)
        filled = draw(st.integers(min_value=0, max_value=quantity)) if quantity else 0
        out.append(
            Order(
                candidate_id="c1",
                symbol=draw(_SYMBOL),
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                limit_price=draw(_PRICE),
                status=draw(_ORDER_STATUS),
                filled_quantity=filled,
            )
        )
    return out


class TestExistingExposureInvariants:
    @given(positions=_positions(), open_orders=_orders())
    @settings(max_examples=200)
    def test_never_negative(self, positions, open_orders):
        assert existing_exposure(positions, open_orders) >= 0.0

    @given(
        positions=_positions(),
        open_orders=_orders(),
        extra_cost_basis=_COST_BASIS,
    )
    @settings(max_examples=200)
    def test_monotonic_in_positions(self, positions, open_orders, extra_cost_basis):
        """Adding one more position can only raise (never lower) exposure —
        every position's cost_basis is a non-negative contribution."""

        before = existing_exposure(positions, open_orders)
        extra = Position(symbol="ZZZZ", quantity=1, cost_basis=extra_cost_basis)
        after = existing_exposure(positions + [extra], open_orders)
        assert after >= before

    @given(positions=_positions(), open_orders=_orders())
    @settings(max_examples=200)
    def test_terminal_orders_never_contribute(self, positions, open_orders):
        """Only non-terminal orders count — swap every order to FILLED
        (terminal) and exposure must drop to exactly the position total."""

        terminal_orders = [
            o.model_copy(update={"status": OrderStatus.FILLED}) for o in open_orders
        ]
        position_only = sum(p.cost_basis for p in positions)
        assert existing_exposure(positions, terminal_orders) == position_only


class TestRiskLimitReasonInvariants:
    @given(
        symbol=_SYMBOL,
        order_quantity=st.integers(min_value=1, max_value=100_000),
        order_limit_price=_PRICE,
        exposure_before_order=st.floats(
            min_value=0.0, max_value=10_000_000, allow_nan=False, allow_infinity=False
        ),
        max_total_exposure=st.floats(
            min_value=0.01, max_value=10_000_000, allow_nan=False, allow_infinity=False
        ),
    )
    @example(
        symbol="AAPL",
        order_quantity=100,
        order_limit_price=10.0,
        exposure_before_order=0.0,
        max_total_exposure=1000.0,
    )
    @settings(max_examples=300)
    def test_total_exposure_cap_is_never_exceeded_by_an_accepted_order(
        self,
        symbol,
        order_quantity,
        order_limit_price,
        exposure_before_order,
        max_total_exposure,
    ):
        """The core safety property: if risk_limit_reason allows the order
        (returns None), the resulting exposure must not exceed the cap. This
        isolates the exposure check — the other two limits are disabled so a
        share/notional block can't produce a false pass on this property."""

        reason = risk_limit_reason(
            symbol=symbol,
            order_quantity=order_quantity,
            order_limit_price=order_limit_price,
            exposure_before_order=exposure_before_order,
            max_shares_per_order=None,
            max_notional_per_order=None,
            max_total_exposure=max_total_exposure,
            allowlist=None,
        )
        resulting_exposure = exposure_before_order + order_quantity * order_limit_price
        if reason is None:
            assert resulting_exposure <= max_total_exposure
        else:
            # And the converse must also hold — a real breach is never missed.
            assert resulting_exposure > max_total_exposure
            assert reason == "exceeds_max_total_exposure"

    @given(
        symbol=_SYMBOL,
        order_quantity=st.integers(min_value=1, max_value=1_000_000),
        max_shares_per_order=st.floats(
            min_value=0.01, max_value=1_000_000, allow_nan=False, allow_infinity=False
        ),
    )
    # Random int/float generation almost never lands on an exact
    # order_quantity == max_shares_per_order boundary on its own (unlike the
    # notional/exposure checks, whose quantity*price multiplication makes
    # Hypothesis collide on the boundary far more often) — pinned explicitly
    # so a `>` -> `>=` regression on this specific comparison can't slip past
    # an entire @settings(max_examples=300) run undetected.
    @example(symbol="AAPL", order_quantity=500, max_shares_per_order=500.0)
    @settings(max_examples=300)
    def test_max_shares_per_order_is_a_hard_iff_cap(
        self, symbol, order_quantity, max_shares_per_order
    ):
        reason = risk_limit_reason(
            symbol=symbol,
            order_quantity=order_quantity,
            order_limit_price=1.0,
            exposure_before_order=0.0,
            max_shares_per_order=max_shares_per_order,
            max_notional_per_order=None,
            max_total_exposure=None,
            allowlist=None,
        )
        if order_quantity > max_shares_per_order:
            assert reason == "exceeds_max_shares_per_order"
        else:
            assert reason is None

    @given(
        symbol=_SYMBOL,
        order_quantity=st.integers(min_value=1, max_value=10_000),
        order_limit_price=_PRICE,
        max_notional_per_order=st.floats(
            min_value=0.01, max_value=100_000_000, allow_nan=False, allow_infinity=False
        ),
    )
    @example(
        symbol="AAPL",
        order_quantity=100,
        order_limit_price=5.0,
        max_notional_per_order=500.0,
    )
    @settings(max_examples=300)
    def test_max_notional_per_order_is_a_hard_iff_cap(
        self, symbol, order_quantity, order_limit_price, max_notional_per_order
    ):
        reason = risk_limit_reason(
            symbol=symbol,
            order_quantity=order_quantity,
            order_limit_price=order_limit_price,
            exposure_before_order=0.0,
            max_shares_per_order=None,
            max_notional_per_order=max_notional_per_order,
            max_total_exposure=None,
            allowlist=None,
        )
        notional = order_quantity * order_limit_price
        if notional > max_notional_per_order:
            assert reason == "exceeds_max_notional_per_order"
        else:
            assert reason is None

    @given(
        symbol=_SYMBOL,
        allowlist=st.frozensets(_SYMBOL, min_size=1, max_size=4),
    )
    @settings(max_examples=100)
    def test_allowlist_membership_is_a_hard_iff_gate(self, symbol, allowlist):
        reason = risk_limit_reason(
            symbol=symbol,
            order_quantity=1,
            order_limit_price=1.0,
            exposure_before_order=0.0,
            max_shares_per_order=None,
            max_notional_per_order=None,
            max_total_exposure=None,
            allowlist=allowlist,
        )
        if symbol in allowlist:
            assert reason is None
        else:
            assert reason == "not_on_allowlist"

    @given(symbol=_SYMBOL, order_quantity=st.integers(min_value=1, max_value=100))
    @settings(max_examples=50)
    def test_no_limits_configured_never_blocks(self, symbol, order_quantity):
        """Every limit None (the default, back-compat interface state) must
        never block — this is what keeps ~20 pre-existing store call sites
        that don't pass CAPI params working unchanged."""

        reason = risk_limit_reason(
            symbol=symbol,
            order_quantity=order_quantity,
            order_limit_price=1.0,
            exposure_before_order=0.0,
            max_shares_per_order=None,
            max_notional_per_order=None,
            max_total_exposure=None,
            allowlist=None,
        )
        assert reason is None
