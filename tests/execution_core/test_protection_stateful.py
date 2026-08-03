"""Bounded generated histories for the pure WO-0148 protection reducer.

The two machines keep their expected economics and market policy in plain test
data.  They never call a production classifier or formula helper to decide an
expected result.  Every real reducer input is replayed from the same immutable
predecessor to prove determinism and input immutability.
"""

from __future__ import annotations

from fractions import Fraction

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from app.execution_core.fills import ExecutionSide
from app.execution_core.identity import VenueInputId
from app.execution_core.recovery import RecordBrokerFillEvidence
from app.execution_core.values import Quantity
from tests.execution_core import test_protection as protection_fixtures
from tests.execution_core import test_venue_recovery as venue_fixtures


def _ceil_exact(value: Fraction) -> Fraction:
    return Fraction(-(-value.numerator // value.denominator))


class ProtectionEconomicsMachine(RuleBasedStateMachine):
    """Generated execution-first economics, flatness, and late-fill histories."""

    def __init__(self) -> None:
        super().__init__()
        self.module = protection_fixtures._protection_module()
        self.current = protection_fixtures._owned_fill_transition(
            label="stateful-economics-root",
            quantity=2,
            units=100,
            capacity=20,
        )
        self.mandate, self.projection, self.state = protection_fixtures._start(
            self.module,
            self.current,
        )
        self.raw_quantity = 2
        self.total_cost = Fraction(200)
        self.armed = _ceil_exact(Fraction(100) * Fraction(37, 40))
        self.activation = _ceil_exact(Fraction(100) * Fraction(43, 40))
        self.expected_policy = "FLOOR_ONLY"
        self.closed = False
        self.late_recovered = False
        self.next_identity = 0
        self.first_projection = self.projection

    def _sync(self, transition: object) -> object:
        projection = protection_fixtures._projection(
            self.module,
            transition,
            self.mandate,
        )
        result = protection_fixtures._reduce(
            self.module,
            self.state,
            projection,
        )
        self.state = result.state
        self.projection = projection
        self.current = transition
        return result

    def _sync_many(self, transitions: tuple[object, ...]) -> object:
        result = None
        for transition in transitions:
            result = self._sync(transition)
        assert result is not None
        return result

    @precondition(lambda self: not self.closed and self.raw_quantity < 10)
    @rule(quantity=st.integers(min_value=1, max_value=3), units=st.integers(80, 130))
    def append_owned_buy(self, quantity: int, units: int) -> None:
        self.next_identity += 1
        transition = protection_fixtures._advance_owned_fill(
            self.current,
            label=f"stateful-economics-buy-{self.next_identity}",
            quantity=quantity,
            units=units,
            prior_cumulative=self.raw_quantity,
        )
        self.raw_quantity += quantity
        self.total_cost += Fraction(quantity * units)
        average = self.total_cost / self.raw_quantity
        candidate = _ceil_exact(average * Fraction(37, 40))
        if candidate < average:
            self.armed = max(self.armed, candidate)
        self.activation = _ceil_exact(average * Fraction(43, 40))
        result = self._sync(transition)
        assert result.goal is None
        assert result.critical_alert is None

    @precondition(lambda self: not self.closed)
    @rule()
    def stale_projection_cannot_roll_back_current_state(self) -> None:
        if self.projection == self.first_projection:
            return
        before = self.state
        result = protection_fixtures._reduce(
            self.module,
            self.state,
            self.first_projection,
        )
        (disposition,) = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
        )
        assert result.disposition is disposition.STALE
        assert result.state == before
        assert result.goal is None
        assert result.critical_alert is None

    @precondition(lambda self: not self.closed and self.raw_quantity > 0)
    @rule()
    def close_all_effects_and_flatten(self) -> None:
        terminal, closed = protection_fixtures._close_base_parent(self.current)
        self._sync_many((terminal, closed))
        sell_chain, sell_effect, sell_leg, _ = (
            protection_fixtures._append_needs_review_effect(
                closed,
                prefix=f"stateful-flat-sell-{self.next_identity}",
                side=ExecutionSide.SELL,
                quantity=self.raw_quantity,
            )
        )
        self._sync_many(sell_chain)
        sell = venue_fixtures.apply_venue_recovery_input(
            sell_chain[-1].book,
            sell_chain[-1].execution,
            RecordBrokerFillEvidence(
                input_id=VenueInputId(f"stateful-flat-sell-fill-{self.next_identity}"),
                effect_id=sell_effect,
                leg_key=sell_leg,
                prior_cumulative_quantity=Quantity(0),
                resulting_cumulative_quantity=Quantity(self.raw_quantity),
                fact=venue_fixtures._broker_fill(
                    f"stateful-flat-sell-source-{self.next_identity}",
                    f"stateful-flat-sell-root-{self.next_identity}",
                    leg_key=sell_leg,
                    side=ExecutionSide.SELL,
                    quantity=self.raw_quantity,
                    units=110,
                ),
                evidence_digest=b"\xa1" * 32,
            ),
        )
        assert sell.execution.position.raw_quantity == 0
        live_zero = self._sync(sell)
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert live_zero.state.policy is not policy.FLAT
        _, sell_terminal = protection_fixtures._terminal_fixture(
            sell,
            effect_id=sell_effect,
            leg_key=sell_leg,
            label=f"stateful-flat-sell-{self.next_identity}",
            cumulative_quantity=self.raw_quantity,
        )
        terminal_result = self._sync(sell_terminal)
        assert terminal_result.state.policy is not policy.FLAT
        _, sell_closed = protection_fixtures._close_parent_fixture(
            sell_terminal,
            effect_id=sell_effect,
            label=f"stateful-flat-sell-{self.next_identity}",
        )
        flat = self._sync(sell_closed)
        assert flat.state.policy is policy.FLAT
        self.raw_quantity = 0
        self.total_cost = Fraction(0)
        self.expected_policy = "FLAT"
        self.closed = True

    @precondition(lambda self: self.closed and not self.late_recovered)
    @rule(quantity=st.integers(min_value=1, max_value=3), units=st.integers(80, 130))
    def late_buy_restores_hard_bail(self, quantity: int, units: int) -> None:
        self.next_identity += 1
        buy_chain, effect_id, leg_key, _ = (
            protection_fixtures._append_needs_review_effect(
                self.current,
                prefix=f"stateful-late-buy-{self.next_identity}",
                side=ExecutionSide.BUY,
                quantity=quantity,
            )
        )
        self._sync_many(buy_chain)
        late = venue_fixtures.apply_venue_recovery_input(
            buy_chain[-1].book,
            buy_chain[-1].execution,
            RecordBrokerFillEvidence(
                input_id=VenueInputId(f"stateful-late-buy-fill-{self.next_identity}"),
                effect_id=effect_id,
                leg_key=leg_key,
                prior_cumulative_quantity=Quantity(0),
                resulting_cumulative_quantity=Quantity(quantity),
                fact=venue_fixtures._broker_fill(
                    f"stateful-late-buy-source-{self.next_identity}",
                    f"stateful-late-buy-root-{self.next_identity}",
                    leg_key=leg_key,
                    side=ExecutionSide.BUY,
                    quantity=quantity,
                    units=units,
                ),
                evidence_digest=b"\xa2" * 32,
            ),
        )
        recovered = self._sync(late)
        self.raw_quantity = quantity
        self.total_cost = Fraction(quantity * units)
        self.expected_policy = "HARD_BAIL"
        self.late_recovered = True
        assert recovered.critical_alert is not None
        assert recovered.goal is None

    @invariant()
    def economics_oracle_matches_public_state(self) -> None:
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert self.state.raw_quantity == self.raw_quantity
        assert self.state.policy is getattr(policy, self.expected_policy)
        assert self.state.execution_commitment == self.current.execution.commitment
        assert self.state.mandate == self.mandate
        if self.expected_policy == "FLOOR_ONLY":
            assert self.state.formula_available is True
            assert self.state.armed_hard_bail_trigger.exact_value == self.armed
            assert self.state.activation_price.exact_value == self.activation
        if self.raw_quantity > 0:
            assert self.state.policy is not policy.FLAT


class ProtectionMarketMachine(RuleBasedStateMachine):
    """Generated evidence eligibility, priority, and trail-ratchet histories."""

    def __init__(self) -> None:
        super().__init__()
        self.module = protection_fixtures._protection_module()
        fill = protection_fixtures._owned_fill_transition(
            label="stateful-market-root",
            quantity=4,
            units=100,
            capacity=4,
        )
        self.mandate, _, state = protection_fixtures._start(self.module, fill)
        terminal, closed = protection_fixtures._close_base_parent(fill)
        self.state, self.projection, _ = protection_fixtures._sync_transitions(
            self.module,
            state,
            self.mandate,
            (terminal, closed),
        )
        self.policy = "FLOOR_ONLY"
        self.hard_trigger = 93
        self.activation = 108
        self.high_water: int | None = None
        self.trail: int | None = None
        self.hard_count = 0
        self.trail_count = 0
        self.sequence = 0
        self.source_time = 94
        self.last_accepted_source_time = 94
        self.last_occurrence: object | None = None

    def _deliver(self, occurrence: object) -> object:
        return protection_fixtures._reduce(
            self.module,
            self.state,
            self.projection,
            occurrence,
        )

    @rule(bid=st.integers(min_value=90, max_value=130))
    def eligible_bid(self, bid: int) -> None:
        self.sequence += 1
        self.source_time += 6
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-market-{self.sequence}",
            bid=bid,
            ask=bid + 1,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
        )
        prior_policy = self.policy
        if bid <= self.hard_trigger:
            self.hard_count += 1
        else:
            self.hard_count = 0
        if self.policy == "FLOOR_ONLY" and bid >= self.activation:
            self.policy = "TRAIL_ACTIVE"
            self.high_water = bid
            self.trail = -(-(bid * 23) // 25)
            self.trail_count = 0
        elif self.policy == "TRAIL_ACTIVE":
            assert self.high_water is not None and self.trail is not None
            self.high_water = max(self.high_water, bid)
            self.trail = max(self.trail, -(-(self.high_water * 23) // 25))
            if bid <= self.trail:
                self.trail_count += 1
            else:
                self.trail_count = 0
        if self.hard_count >= 2:
            self.policy = "HARD_BAIL"
        elif self.policy == "TRAIL_ACTIVE" and self.trail_count >= 2:
            self.policy = "EXIT_NORMAL"
        result = self._deliver(occurrence)
        self.state = result.state
        self.last_occurrence = occurrence
        self.last_accepted_source_time = self.source_time
        if self.policy != prior_policy and self.policy in {"EXIT_NORMAL", "HARD_BAIL"}:
            assert result.goal is not None

    @precondition(lambda self: self.last_occurrence is not None)
    @rule()
    def duplicate_occurrence_is_an_evidence_noop(self) -> None:
        before = self.state
        result = self._deliver(self.last_occurrence)
        assert result.state == before
        assert result.goal is None

    @rule()
    def crossed_quote_is_ineligible(self) -> None:
        self.sequence += 1
        self.source_time += 6
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-crossed-{self.sequence}",
            bid=101,
            ask=100,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
        )
        before = self.state
        result = self._deliver(occurrence)
        assert result.state == before
        assert result.goal is None

    @precondition(lambda self: self.last_occurrence is not None)
    @rule()
    def source_time_regression_is_ineligible(self) -> None:
        self.sequence += 1
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-time-regression-{self.sequence}",
            bid=92,
            ask=93,
            sequence=self.sequence,
            source_time=self.last_accepted_source_time - 1,
            evaluation_time=self.source_time + 4,
        )
        before = self.state
        result = self._deliver(occurrence)
        assert result.state == before
        assert result.goal is None

    @invariant()
    def market_oracle_matches_public_state(self) -> None:
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert self.state.policy is getattr(policy, self.policy)
        if self.high_water is not None:
            assert self.state.high_watermark.exact_value == self.high_water
        if self.trail is not None:
            assert self.state.trail.exact_value == self.trail
        assert self.state.waiting_buy_resolution is False
        assert self.state.raw_quantity == 4


TestProtectionEconomicsMachine = ProtectionEconomicsMachine.TestCase
TestProtectionEconomicsMachine.settings = settings(
    max_examples=20,
    stateful_step_count=12,
    deadline=None,
)

TestProtectionMarketMachine = ProtectionMarketMachine.TestCase
TestProtectionMarketMachine.settings = settings(
    max_examples=30,
    stateful_step_count=18,
    deadline=None,
)
