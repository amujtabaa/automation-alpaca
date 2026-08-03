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

from app.execution_core.fills import (
    BrokerTradeCorrectFact,
    ExecutionFactKey,
    ExecutionSide,
)
from app.execution_core.identity import (
    ClosureId,
    EvidenceReference,
    RootFillId,
    SourceEventId,
    VenueInputId,
)
from app.execution_core.recovery import (
    RecordBrokerFillEvidence,
    RecordBrokerRevisionEvidence,
)
from app.execution_core.values import PriceUnits, Quantity, TickMetadata
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
        self.late_correction_recovered = False
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

    @precondition(
        lambda self: (
            self.closed
            and not self.late_recovered
            and not self.late_correction_recovered
        )
    )
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

    @precondition(
        lambda self: (
            self.closed
            and not self.late_recovered
            and not self.late_correction_recovered
            and self.next_identity == 0
        )
    )
    @rule()
    def late_correction_after_flat_restores_hard_bail(self) -> None:
        """A late valid correction is as dangerous as a late first fill."""
        fact = BrokerTradeCorrectFact(
            key=ExecutionFactKey(
                broker=venue_fixtures.BROKER,
                environment=venue_fixtures.ENVIRONMENT,
                account=venue_fixtures.ACCOUNT,
                source_event_id=SourceEventId("stateful-late-correction-source"),
            ),
            scope=venue_fixtures._execution_scope(),
            root_fill_id=RootFillId("stateful-economics-root-root"),
            predecessor_source_event_id=SourceEventId("stateful-economics-root-source"),
            revised_quantity=Quantity(3),
            revised_price=protection_fixtures._price(100),
        )
        corrected = venue_fixtures.apply_venue_recovery_input(
            self.current.book,
            self.current.execution,
            RecordBrokerRevisionEvidence(
                input_id=VenueInputId("stateful-late-correction-input"),
                effect_id=protection_fixtures.BASE_EFFECT,
                leg_key=protection_fixtures.BASE_LEG,
                prior_root_quantity=Quantity(2),
                prior_venue_cumulative_quantity=Quantity(2),
                resulting_venue_cumulative_quantity=Quantity(3),
                fact=fact,
                evidence_digest=b"\xa3" * 32,
                closure_id=ClosureId("stateful-late-correction-closure"),
                evidence_reference=EvidenceReference(
                    "stateful-late-correction-evidence"
                ),
            ),
        )
        assert corrected.quantity_delta == 1
        recovered = self._sync(corrected)
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert recovered.state.raw_quantity == 1
        assert recovered.state.policy is policy.HARD_BAIL
        assert recovered.critical_alert is not None
        assert recovered.goal is None
        self.raw_quantity = 1
        self.total_cost = Fraction(100)
        self.expected_policy = "HARD_BAIL"
        self.late_correction_recovered = True

    @rule()
    def correction_bust_and_authentic_restore_preserve_execution_truth(self) -> None:
        """A revision chain changes economics before any protection conclusion.

        This is deliberately a small, independent history rather than an oracle
        copied from the execution reducer: the assertions are only the public
        quantity/formula consequences that protection must retain.
        """
        initial = protection_fixtures._owned_fill_transition(
            label="stateful-revision-root",
            quantity=2,
            units=100,
            capacity=4,
        )
        mandate, _, state = protection_fixtures._start(self.module, initial)
        _, corrected = protection_fixtures._correct_owned_root(
            initial,
            label="stateful-revision-correct",
            root_fill_id=RootFillId("stateful-revision-root-root"),
            predecessor_source_event_id=SourceEventId("stateful-revision-root-source"),
            prior_root_quantity=2,
            resulting_quantity=3,
            units=102,
            prior_venue_cumulative=2,
        )
        corrected_result = protection_fixtures._reduce(
            self.module,
            state,
            protection_fixtures._projection(self.module, corrected, mandate),
        )
        assert corrected_result.state.raw_quantity == 3
        assert corrected_result.state.formula_available is True

        _, busted = protection_fixtures._bust_owned_root(
            corrected,
            label="stateful-revision-bust",
            root_fill_id=RootFillId("stateful-revision-root-root"),
            predecessor_source_event_id=SourceEventId(
                "stateful-revision-correct-source"
            ),
            prior_root_quantity=3,
            prior_venue_cumulative=3,
        )
        busted_result = protection_fixtures._reduce(
            self.module,
            corrected_result.state,
            protection_fixtures._projection(self.module, busted, mandate),
        )
        assert busted_result.state.raw_quantity == 0
        assert busted_result.goal is None

        _, restored = protection_fixtures._correct_owned_root(
            busted,
            label="stateful-revision-restore",
            root_fill_id=RootFillId("stateful-revision-root-root"),
            predecessor_source_event_id=SourceEventId("stateful-revision-bust-source"),
            prior_root_quantity=0,
            resulting_quantity=2,
            units=104,
            prior_venue_cumulative=0,
        )
        restored_result = protection_fixtures._reduce(
            self.module,
            busted_result.state,
            protection_fixtures._projection(self.module, restored, mandate),
        )
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert restored_result.state.raw_quantity == 2
        assert restored_result.state.formula_available is True
        assert restored_result.state.policy is not policy.FLAT

    @rule()
    def incompatible_tick_withholds_only_formula_then_restores_it(self) -> None:
        """An authoritative correction stays economic even when its tick is bad."""
        incompatible_tick = TickMetadata(
            tick_units=PriceUnits(2),
            scale=protection_fixtures.SCALE,
        )
        initial = protection_fixtures._owned_fill_transition(
            label="stateful-tick-root",
            quantity=2,
            units=100,
            capacity=4,
            tick_units=2,
        )
        mandate = protection_fixtures._mandate(self.module, tick=incompatible_tick)
        _, _, state = protection_fixtures._start(self.module, initial, mandate)
        assert state.formula_available is True

        _, incompatible = protection_fixtures._correct_owned_root(
            initial,
            label="stateful-tick-incompatible",
            root_fill_id=RootFillId("stateful-tick-root-root"),
            predecessor_source_event_id=SourceEventId("stateful-tick-root-source"),
            prior_root_quantity=2,
            resulting_quantity=2,
            units=101,
            prior_venue_cumulative=2,
        )
        unavailable = protection_fixtures._reduce(
            self.module,
            state,
            protection_fixtures._projection(self.module, incompatible, mandate),
        )
        assert unavailable.state.raw_quantity == 2
        assert unavailable.state.formula_available is False
        assert unavailable.goal is None

        _, restored = protection_fixtures._correct_owned_root(
            incompatible,
            label="stateful-tick-restored",
            root_fill_id=RootFillId("stateful-tick-root-root"),
            predecessor_source_event_id=SourceEventId(
                "stateful-tick-incompatible-source"
            ),
            prior_root_quantity=2,
            resulting_quantity=2,
            units=102,
            prior_venue_cumulative=2,
            tick_units=2,
        )
        available = protection_fixtures._reduce(
            self.module,
            unavailable.state,
            protection_fixtures._projection(self.module, restored, mandate),
        )
        assert available.state.raw_quantity == 2
        assert available.state.formula_available is True

    @rule()
    def authentic_projection_cannot_be_substituted_or_mixed(self) -> None:
        """A real transition from another history cannot advance this state."""
        other = protection_fixtures._owned_fill_transition(
            label="stateful-substitution-other",
            quantity=2,
            units=101,
            capacity=4,
        )
        foreign_projection = protection_fixtures._projection(
            self.module,
            other,
            self.mandate,
        )
        before = self.state
        foreign = protection_fixtures._reduce(
            self.module,
            before,
            foreign_projection,
        )
        assert foreign.state == before
        assert foreign.goal is None
        assert foreign.critical_alert is None

        mixed = protection_fixtures._clone_opaque(
            self.current,
            execution=other.execution,
        )
        try:
            projection = protection_fixtures._projection(
                self.module,
                mixed,
                self.mandate,
            )
        except (TypeError, ValueError):
            return
        rejected = protection_fixtures._reduce(self.module, before, projection)
        assert rejected.state == before
        assert rejected.goal is None
        assert rejected.critical_alert is None

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
        self.last_accepted_sequence = 0
        self.last_bid = 100
        self.last_occurrence: object | None = None
        self.market_epoch = 0
        self.optional_tightening_seen = False

    def _deliver(self, occurrence: object) -> object:
        return protection_fixtures._reduce(
            self.module,
            self.state,
            self.projection,
            occurrence,
        )

    @precondition(lambda self: not self.optional_tightening_seen)
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
            market_epoch=self.market_epoch,
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
        self.last_accepted_sequence = self.sequence
        self.last_bid = bid
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

    @precondition(lambda self: self.last_occurrence is not None)
    @rule()
    def nonadvancing_sequence_is_an_evidence_noop(self) -> None:
        """A new occurrence id cannot reuse an already-consumed sequence."""
        self.source_time += 6
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-nonadvancing-{self.sequence}",
            bid=92,
            ask=93,
            sequence=self.last_accepted_sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before = self.state
        result = self._deliver(occurrence)
        assert result.state == before
        assert result.goal is None

    @precondition(lambda self: self.last_occurrence is not None)
    @rule()
    def max_step_jump_is_an_evidence_noop(self) -> None:
        """A fresh but implausible quote cannot corroborate or ratchet."""
        self.sequence += 1
        self.source_time += 6
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-step-jump-{self.sequence}",
            bid=max(160, self.last_bid * 2),
            ask=max(161, self.last_bid * 2 + 1),
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before = self.state
        result = self._deliver(occurrence)
        assert result.state == before
        assert result.goal is None

    @precondition(lambda self: self.policy == "TRAIL_ACTIVE")
    @rule()
    def optional_atr_and_structure_inputs_can_only_tighten_a_trail(self) -> None:
        """Optional corroborating inputs never loosen the independent percent floor."""
        assert self.high_water is not None and self.trail is not None
        self.sequence += 1
        self.source_time += 6
        percent_floor = -(-(self.high_water * 23) // 25)
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-optional-trail-{self.sequence}",
            bid=self.high_water,
            ask=self.high_water + 1,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
            atr_distance=2,
            structure_trail=max(percent_floor, self.high_water - 1),
        )
        result = self._deliver(occurrence)
        self.state = result.state
        self.last_occurrence = occurrence
        self.last_accepted_source_time = self.source_time
        self.last_accepted_sequence = self.sequence
        self.optional_tightening_seen = True
        assert result.state.policy is not None
        assert result.state.trail.exact_value >= percent_floor
        assert result.goal is None

    @rule()
    def interruption_reopen_epoch_requires_fresh_corroboration(self) -> None:
        """A halt and new epoch cannot carry a one-observation exit across it."""
        fill = protection_fixtures._owned_fill_transition(
            label="stateful-epoch-root",
            quantity=4,
            units=100,
            capacity=4,
        )
        mandate, _, state = protection_fixtures._start(self.module, fill)
        terminal, closed = protection_fixtures._close_base_parent(fill)
        state, projection, _ = protection_fixtures._sync_transitions(
            self.module,
            state,
            mandate,
            (terminal, closed),
        )
        first = protection_fixtures._occurrence(
            self.module,
            "stateful-epoch-first",
            bid=92,
            ask=93,
            sequence=1,
            source_time=100,
            evaluation_time=104,
            market_epoch=0,
        )
        first_result = protection_fixtures._reduce(
            self.module, state, projection, first
        )
        assert first_result.goal is None
        interrupted = protection_fixtures._occurrence(
            self.module,
            "stateful-epoch-halt",
            bid=92,
            ask=93,
            sequence=2,
            source_time=106,
            evaluation_time=110,
            market_epoch=0,
            halted=True,
        )
        halted = protection_fixtures._reduce(
            self.module,
            first_result.state,
            projection,
            interrupted,
        )
        assert halted.goal is None
        reopen_first = protection_fixtures._occurrence(
            self.module,
            "stateful-epoch-reopen-first",
            bid=92,
            ask=93,
            sequence=1,
            source_time=112,
            evaluation_time=116,
            market_epoch=1,
        )
        reopened = protection_fixtures._reduce(
            self.module,
            halted.state,
            projection,
            reopen_first,
        )
        assert reopened.goal is None
        reopen_second = protection_fixtures._occurrence(
            self.module,
            "stateful-epoch-reopen-second",
            bid=92,
            ask=93,
            sequence=2,
            source_time=118,
            evaluation_time=122,
            market_epoch=1,
        )
        bailed = protection_fixtures._reduce(
            self.module,
            reopened.state,
            projection,
            reopen_second,
        )
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert bailed.state.policy is policy.HARD_BAIL
        assert bailed.goal is not None

    @rule()
    def normal_exit_wait_survives_restart_until_exact_buy_closure(self) -> None:
        """Normal urgency remains normal while an owned BUY is unresolved."""
        fill = protection_fixtures._owned_fill_transition(
            label="stateful-wait-root",
            quantity=4,
            units=100,
            capacity=4,
        )
        mandate, _, state = protection_fixtures._start(self.module, fill)
        base_terminal, base_closed = protection_fixtures._close_base_parent(fill)
        state, _, _ = protection_fixtures._sync_transitions(
            self.module,
            state,
            mandate,
            (base_terminal, base_closed),
        )
        buy_chain, buy_effect, buy_leg, _ = (
            protection_fixtures._append_needs_review_effect(
                base_closed,
                prefix="stateful-wait-buy",
                side=ExecutionSide.BUY,
                quantity=1,
            )
        )
        state, projection, _ = protection_fixtures._sync_transitions(
            self.module,
            state,
            mandate,
            buy_chain,
        )
        activate = protection_fixtures._occurrence(
            self.module,
            "stateful-wait-activate",
            bid=120,
            ask=121,
            sequence=1,
            source_time=100,
            evaluation_time=104,
        )
        trailed = protection_fixtures._reduce(self.module, state, projection, activate)
        first_exit = protection_fixtures._occurrence(
            self.module,
            "stateful-wait-first-exit",
            bid=110,
            ask=111,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        )
        first = protection_fixtures._reduce(
            self.module,
            trailed.state,
            projection,
            first_exit,
        )
        second_exit = protection_fixtures._occurrence(
            self.module,
            "stateful-wait-second-exit",
            bid=110,
            ask=111,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        )
        waiting = protection_fixtures._reduce(
            self.module,
            first.state,
            projection,
            second_exit,
        )
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert waiting.state.policy is policy.EXIT_NORMAL
        assert waiting.state.waiting_buy_resolution is True
        assert waiting.goal is None

        restarted = protection_fixtures._reduce(self.module, waiting.state, projection)
        assert restarted.state == waiting.state
        assert restarted.goal is None
        _, terminal = protection_fixtures._terminal_fixture(
            buy_chain[-1],
            effect_id=buy_effect,
            leg_key=buy_leg,
            label="stateful-wait-buy",
            cumulative_quantity=0,
        )
        after_terminal = protection_fixtures._reduce(
            self.module,
            restarted.state,
            protection_fixtures._projection(self.module, terminal, mandate),
        )
        assert after_terminal.state.waiting_buy_resolution is True
        _, closed = protection_fixtures._close_parent_fixture(
            terminal,
            effect_id=buy_effect,
            label="stateful-wait-buy",
        )
        released = protection_fixtures._reduce(
            self.module,
            after_terminal.state,
            protection_fixtures._projection(self.module, closed, mandate),
        )
        assert released.state.policy is policy.EXIT_NORMAL
        assert released.state.waiting_buy_resolution is False
        assert released.goal is not None
        assert released.goal.guard == mandate.normal_guard

    @invariant()
    def market_oracle_matches_public_state(self) -> None:
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert self.state.policy is getattr(policy, self.policy)
        if self.high_water is not None:
            assert self.state.high_watermark.exact_value == self.high_water
        if self.trail is not None:
            if self.optional_tightening_seen:
                assert self.state.trail.exact_value >= self.trail
            else:
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
