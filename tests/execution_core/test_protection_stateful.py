"""Bounded generated histories for the pure WO-0148 protection reducer.

The two machines keep their expected economics and market policy in plain test
data.  They never call a production classifier or formula helper to decide an
expected result.  Every real reducer input is replayed from the same immutable
predecessor to prove determinism and input immutability.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Any

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
        self.root_quantity = 2
        self.root_units = 100
        self.root_head = SourceEventId("stateful-economics-root-source")
        self.formula_expected = True
        self.armed = _ceil_exact(Fraction(100) * Fraction(37, 40))
        self.activation = _ceil_exact(Fraction(100) * Fraction(43, 40))
        self.expected_policy = "FLOOR_ONLY"
        self.closed = False
        self.late_recovered = False
        self.late_correction_recovered = False
        self.next_identity = 0
        self.projection_history = [self.projection]
        self.last_result: object | None = None

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
        self.projection_history.append(projection)
        self.last_result = result
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
        if self.formula_expected:
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
        if len(self.projection_history) < 2:
            return
        before = self.state
        result = protection_fixtures._reduce(
            self.module,
            self.state,
            self.projection_history[-2],
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
        self.formula_expected = True
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
        self.formula_expected = False
        self.expected_policy = "HARD_BAIL"
        self.late_correction_recovered = True

    @precondition(
        lambda self: (
            not self.closed
            and self.next_identity == 0
            and self.expected_policy == "FLOOR_ONLY"
        )
    )
    @rule(
        resulting_quantity=st.integers(min_value=1, max_value=4),
        units=st.integers(min_value=80, max_value=130),
    )
    def correction_bust_and_authentic_restore_compose_with_later_history(
        self,
        resulting_quantity: int,
        units: int,
    ) -> None:
        """Revision, bust, and restore advance this machine's one history."""
        self.next_identity += 1
        correct_label = f"stateful-revision-correct-{self.next_identity}"
        _, corrected = protection_fixtures._correct_owned_root(
            self.current,
            label=correct_label,
            root_fill_id=RootFillId("stateful-economics-root-root"),
            predecessor_source_event_id=self.root_head,
            prior_root_quantity=self.root_quantity,
            resulting_quantity=resulting_quantity,
            units=units,
            prior_venue_cumulative=self.root_quantity,
        )
        corrected_result = self._sync(corrected)
        self.raw_quantity = resulting_quantity
        self.total_cost = Fraction(resulting_quantity * units)
        self.root_quantity = resulting_quantity
        self.root_units = units
        self.root_head = SourceEventId(f"{correct_label}-source")
        assert corrected_result.state.raw_quantity == self.raw_quantity
        assert corrected_result.state.formula_available is True

        bust_label = f"stateful-revision-bust-{self.next_identity}"
        _, busted = protection_fixtures._bust_owned_root(
            self.current,
            label=bust_label,
            root_fill_id=RootFillId("stateful-economics-root-root"),
            predecessor_source_event_id=self.root_head,
            prior_root_quantity=self.root_quantity,
            prior_venue_cumulative=self.root_quantity,
        )
        busted_result = self._sync(busted)
        self.root_head = SourceEventId(f"{bust_label}-source")
        self.root_quantity = 0
        self.raw_quantity = 0
        self.total_cost = Fraction(0)
        assert busted_result.state.raw_quantity == 0
        assert busted_result.goal is None

        restore_label = f"stateful-revision-restore-{self.next_identity}"
        _, restored = protection_fixtures._correct_owned_root(
            self.current,
            label=restore_label,
            root_fill_id=RootFillId("stateful-economics-root-root"),
            predecessor_source_event_id=self.root_head,
            prior_root_quantity=0,
            resulting_quantity=resulting_quantity,
            units=units,
            prior_venue_cumulative=0,
        )
        restored_result = self._sync(restored)
        self.root_head = SourceEventId(f"{restore_label}-source")
        self.root_quantity = resulting_quantity
        self.root_units = units
        self.raw_quantity = resulting_quantity
        self.total_cost = Fraction(resulting_quantity * units)
        average = self.total_cost / self.raw_quantity
        candidate = _ceil_exact(average * Fraction(37, 40))
        if candidate < average:
            self.armed = max(self.armed, candidate)
        self.activation = _ceil_exact(average * Fraction(43, 40))
        self.formula_expected = True
        assert restored_result.state.raw_quantity == self.raw_quantity
        assert restored_result.state.formula_available is True

    @precondition(
        lambda self: (
            not self.closed
            and self.root_quantity > 0
            and self.formula_expected
            and self.total_cost == Fraction(self.root_quantity * self.root_units)
        )
    )
    @rule(units=st.integers(min_value=40, max_value=65).map(lambda value: value * 2))
    def incompatible_tick_loss_and_restore_advance_shared_history(
        self,
        units: int,
    ) -> None:
        """Formula loss and restoration remain composable with later rules."""
        self.next_identity += 1
        incompatible_label = f"stateful-tick-incompatible-{self.next_identity}"
        _, incompatible = protection_fixtures._correct_owned_root(
            self.current,
            label=incompatible_label,
            root_fill_id=RootFillId("stateful-economics-root-root"),
            predecessor_source_event_id=self.root_head,
            prior_root_quantity=self.root_quantity,
            resulting_quantity=self.root_quantity,
            units=units,
            prior_venue_cumulative=self.root_quantity,
            tick_units=2,
        )
        unavailable = self._sync(incompatible)
        self.root_units = units
        self.root_head = SourceEventId(f"{incompatible_label}-source")
        self.total_cost = Fraction(self.root_quantity * units)
        self.formula_expected = False
        self.expected_policy = "HARD_BAIL"
        assert unavailable.state.raw_quantity == self.raw_quantity
        assert unavailable.state.formula_available is False
        assert unavailable.goal is None

        restored_units = units + 1
        restored_label = f"stateful-tick-restored-{self.next_identity}"
        _, restored = protection_fixtures._correct_owned_root(
            self.current,
            label=restored_label,
            root_fill_id=RootFillId("stateful-economics-root-root"),
            predecessor_source_event_id=self.root_head,
            prior_root_quantity=self.root_quantity,
            resulting_quantity=self.root_quantity,
            units=restored_units,
            prior_venue_cumulative=self.root_quantity,
        )
        available = self._sync(restored)
        self.root_units = restored_units
        self.root_head = SourceEventId(f"{restored_label}-source")
        self.total_cost = Fraction(self.root_quantity * restored_units)
        average = self.total_cost / self.raw_quantity
        candidate = _ceil_exact(average * Fraction(37, 40))
        if candidate < average:
            self.armed = max(self.armed, candidate)
        self.activation = _ceil_exact(average * Fraction(43, 40))
        self.formula_expected = True
        assert available.state.raw_quantity == self.raw_quantity
        assert available.state.formula_available is True
        assert available.goal is None

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
        if self.raw_quantity > 0:
            assert self.state.formula_available is self.formula_expected
        if self.expected_policy == "FLOOR_ONLY" and self.formula_expected:
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
        self.current = closed
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
        self.waiting = False
        self.buy_effect = None
        self.buy_leg = None
        self.buy_stage = "NONE"
        self.cross_kind_checked = False
        self.last_result: object | None = None

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
        self.last_result = result
        return result

    def _deliver(self, occurrence: object) -> object:
        result = protection_fixtures._reduce(
            self.module,
            self.state,
            self.projection,
            occurrence,
        )
        self.last_result = result
        return result

    @precondition(lambda self: self.policy in {"FLOOR_ONLY", "TRAIL_ACTIVE"})
    @rule(bid=st.integers(min_value=90, max_value=130))
    def eligible_bid(self, bid: int) -> None:
        self.sequence += 1
        self.source_time += 6
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-market-{self.market_epoch}-{self.sequence}",
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
        self.waiting = self.buy_stage in {"OPEN", "TERMINAL"}
        if self.policy != prior_policy and self.policy in {"EXIT_NORMAL", "HARD_BAIL"}:
            if self.waiting:
                assert result.state.waiting_buy_resolution is True
                assert result.goal is None
            else:
                assert result.goal is not None

    @precondition(lambda self: self.last_occurrence is not None)
    @rule()
    def changed_delivery_context_replay_is_an_exact_evidence_noop(self) -> None:
        before = self.state
        before_snapshot = protection_fixtures._leaf_sort_key(before)
        replay = replace(
            self.last_occurrence,
            evaluation_time=self.last_occurrence.evaluation_time + 1,
        )
        result = self._deliver(replay)
        (disposition,) = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
        )
        assert result.disposition is disposition.EXACT_REPLAY
        assert protection_fixtures._leaf_sort_key(result.state) == before_snapshot
        assert result.state == before
        assert result.state.commitment == before.commitment
        assert result.goal is None
        assert result.critical_alert is None

    @precondition(
        lambda self: (
            self.policy == "FLOOR_ONLY"
            and self.hard_count == 0
            and self.buy_stage == "NONE"
        )
    )
    @rule(
        first_kind=st.sampled_from(("BEST_BID", "TRADE")),
        has_sequence=st.booleans(),
    )
    def changed_context_replay_preserves_between_time_successor(
        self,
        first_kind: str,
        has_sequence: bool,
    ) -> None:
        """A redelivered fact cannot consume later delivery time or corroboration."""
        self.sequence += 1
        self.source_time += 6
        first_sequence = self.sequence if has_sequence else None
        first_evaluation_time = self.source_time + 5
        first = protection_fixtures._occurrence(
            self.module,
            f"stateful-replay-first-{first_kind.lower()}-{self.sequence}",
            kind=first_kind,
            bid=92 if first_kind == "BEST_BID" else None,
            ask=93 if first_kind == "BEST_BID" else None,
            trade=92 if first_kind == "TRADE" else None,
            sequence=first_sequence,
            source_time=self.source_time,
            evaluation_time=first_evaluation_time,
            market_epoch=self.market_epoch,
        )
        first_result = self._deliver(first)
        self.state = first_result.state
        self.hard_count = 1
        before_replay = self.state
        before_replay_snapshot = protection_fixtures._leaf_sort_key(before_replay)

        replay_evaluation_time = first_evaluation_time + 4
        replay = replace(first, evaluation_time=replay_evaluation_time)
        replay_result = self._deliver(replay)
        (disposition, policy) = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
            "ProtectionPolicy",
        )
        assert replay_result.disposition is disposition.EXACT_REPLAY
        assert (
            protection_fixtures._leaf_sort_key(replay_result.state)
            == before_replay_snapshot
        )
        assert replay_result.state == before_replay
        assert replay_result.state.commitment == before_replay.commitment
        assert replay_result.goal is None
        assert replay_result.critical_alert is None

        self.sequence += 1
        self.source_time += 6
        successor_evaluation_time = first_evaluation_time + 2
        assert (
            first_evaluation_time < successor_evaluation_time < replay_evaluation_time
        )
        successor = protection_fixtures._occurrence(
            self.module,
            f"stateful-replay-successor-{first_kind.lower()}-{self.sequence}",
            bid=91,
            ask=92,
            sequence=self.sequence if has_sequence else None,
            source_time=self.source_time,
            evaluation_time=successor_evaluation_time,
            market_epoch=self.market_epoch,
        )
        successor_result = self._deliver(successor)
        self.state = successor_result.state
        self.policy = "HARD_BAIL"
        self.hard_count = 2
        self.last_occurrence = successor
        self.last_accepted_source_time = self.source_time
        if has_sequence:
            self.last_accepted_sequence = self.sequence
        self.last_bid = 91
        self.waiting = False
        assert successor_result.state.policy is policy.HARD_BAIL
        assert successor_result.goal is not None
        assert successor_result.critical_alert is None

    @precondition(
        lambda self: (
            self.policy == "FLOOR_ONLY"
            and self.hard_count == 0
            and self.buy_stage == "NONE"
        )
    )
    @rule(first_kind=st.sampled_from(("BEST_BID", "TRADE")))
    def nonlast_sequence_less_replay_survives_restart_as_an_exact_noop(
        self,
        first_kind: str,
    ) -> None:
        """An interruption cannot make an older accepted identity authoritative again."""
        case = self.sequence + 1
        shared_source_time = self.source_time + 6
        first = protection_fixtures._occurrence(
            self.module,
            f"stateful-nonlast-replay-{first_kind.lower()}-{case}-a",
            kind=first_kind,
            bid=92 if first_kind == "BEST_BID" else None,
            ask=93 if first_kind == "BEST_BID" else None,
            trade=92 if first_kind == "TRADE" else None,
            sequence=None,
            source_time=shared_source_time,
            evaluation_time=shared_source_time + 4,
            market_epoch=self.market_epoch,
        )
        first_result = self._deliver(first)
        interrupted_occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-nonlast-replay-{first_kind.lower()}-{case}-b",
            bid=95,
            ask=96,
            sequence=None,
            source_time=shared_source_time,
            evaluation_time=shared_source_time + 5,
            market_epoch=self.market_epoch,
        )
        interrupted = protection_fixtures._reduce(
            self.module,
            first_result.state,
            self.projection,
            interrupted_occurrence,
        )
        restarted_state = protection_fixtures._clone_opaque(interrupted.state)
        replay = protection_fixtures._reduce(
            self.module,
            restarted_state,
            self.projection,
            replace(first, evaluation_time=shared_source_time + 6),
        )
        disposition, policy = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
            "ProtectionPolicy",
        )
        assert replay.disposition is disposition.EXACT_REPLAY
        assert replay.state == restarted_state
        assert replay.goal is None

        successor_source_time = shared_source_time + 6
        successor = protection_fixtures._occurrence(
            self.module,
            f"stateful-nonlast-replay-{first_kind.lower()}-{case}-c",
            bid=91,
            ask=92,
            sequence=None,
            source_time=successor_source_time,
            evaluation_time=successor_source_time + 4,
            market_epoch=self.market_epoch,
        )
        successor_result = protection_fixtures._reduce(
            self.module,
            replay.state,
            self.projection,
            successor,
        )
        assert successor_result.state.policy is policy.FLOOR_ONLY
        assert successor_result.goal is None

        self.sequence += 4
        self.source_time = successor_source_time
        self.last_accepted_source_time = successor_source_time
        self.state = successor_result.state
        self.last_occurrence = successor
        self.last_bid = 91
        self.hard_count = 1
        self.last_result = successor_result

    @rule()
    def crossed_quote_is_ineligible(self) -> None:
        self.sequence += 1
        self.source_time += 6
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-crossed-{self.market_epoch}-{self.sequence}",
            bid=101,
            ask=100,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before = self.state
        result = self._deliver(occurrence)
        protection_fixtures._assert_recorded_market_inert(
            self.module,
            before,
            result,
        )
        self.state = result.state

    @precondition(lambda self: self.last_occurrence is not None)
    @rule()
    def source_time_regression_is_ineligible(self) -> None:
        self.sequence += 1
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-time-regression-{self.market_epoch}-{self.sequence}",
            bid=92,
            ask=93,
            sequence=self.sequence,
            source_time=self.last_accepted_source_time - 1,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before = self.state
        result = self._deliver(occurrence)
        protection_fixtures._assert_recorded_market_inert(
            self.module,
            before,
            result,
        )
        self.state = result.state

    @precondition(
        lambda self: (
            self.last_occurrence is not None
            and self.last_occurrence.source_sequence is not None
        )
    )
    @rule()
    def nonadvancing_sequence_is_an_evidence_noop(self) -> None:
        """A new occurrence id cannot reuse an already-consumed sequence."""
        self.source_time += 6
        occurrence = protection_fixtures._occurrence(
            self.module,
            (
                f"stateful-nonadvancing-{self.market_epoch}-"
                f"{self.sequence}-{self.source_time}"
            ),
            bid=92,
            ask=93,
            sequence=self.last_accepted_sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before = self.state
        result = self._deliver(occurrence)
        protection_fixtures._assert_recorded_market_inert(
            self.module,
            before,
            result,
        )
        self.state = result.state

    @precondition(
        lambda self: (
            self.policy == "FLOOR_ONLY"
            and self.hard_count == 0
            and self.buy_stage == "NONE"
        )
    )
    @rule()
    def sequence_absence_preserves_the_last_present_high_water(self) -> None:
        """A sequence-less fact cannot make an older source ordinal reusable."""
        baseline_sequence = self.sequence + 7
        self.source_time += 6
        baseline = protection_fixtures._occurrence(
            self.module,
            f"stateful-mixed-sequence-baseline-{baseline_sequence}",
            bid=100,
            ask=101,
            sequence=baseline_sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        baseline_result = self._deliver(baseline)
        self.state = baseline_result.state
        self.last_occurrence = baseline
        self.last_accepted_source_time = self.source_time
        self.last_accepted_sequence = baseline_sequence
        self.last_bid = 100

        self.source_time += 6
        absent = protection_fixtures._occurrence(
            self.module,
            f"stateful-mixed-sequence-absent-{baseline_sequence}",
            bid=100,
            ask=101,
            sequence=None,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        absent_result = self._deliver(absent)
        self.state = absent_result.state
        self.last_occurrence = absent
        self.last_accepted_source_time = self.source_time

        self.source_time += 6
        reused = protection_fixtures._occurrence(
            self.module,
            f"stateful-mixed-sequence-reused-{baseline_sequence}",
            bid=92,
            ask=93,
            sequence=baseline_sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before_reuse = self.state
        reused_result = self._deliver(reused)
        protection_fixtures._assert_recorded_market_inert(
            self.module,
            before_reuse,
            reused_result,
        )
        self.state = reused_result.state

        self.source_time += 6
        first_fresh = protection_fixtures._occurrence(
            self.module,
            f"stateful-mixed-sequence-fresh-{baseline_sequence + 1}",
            bid=92,
            ask=93,
            sequence=baseline_sequence + 1,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        first_result = self._deliver(first_fresh)
        self.state = first_result.state
        self.hard_count = 1
        assert first_result.goal is None

        self.source_time += 6
        second_fresh = protection_fixtures._occurrence(
            self.module,
            f"stateful-mixed-sequence-fresh-{baseline_sequence + 2}",
            bid=91,
            ask=92,
            sequence=baseline_sequence + 2,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        second_result = self._deliver(second_fresh)
        (policy,) = protection_fixtures._required(
            self.module,
            "ProtectionPolicy",
        )
        self.state = second_result.state
        self.policy = "HARD_BAIL"
        self.hard_count = 2
        self.sequence = baseline_sequence + 2
        self.last_occurrence = second_fresh
        self.last_accepted_source_time = self.source_time
        self.last_accepted_sequence = self.sequence
        self.last_bid = 91
        assert second_result.state.policy is policy.HARD_BAIL
        assert second_result.goal is not None

    @precondition(lambda self: self.last_occurrence is not None)
    @rule()
    def max_step_jump_is_an_evidence_noop(self) -> None:
        """A fresh but implausible quote cannot corroborate or ratchet."""
        self.sequence += 1
        self.source_time += 6
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-step-jump-{self.market_epoch}-{self.sequence}",
            bid=max(160, self.last_bid * 2),
            ask=max(161, self.last_bid * 2 + 1),
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before = self.state
        result = self._deliver(occurrence)
        protection_fixtures._assert_recorded_market_inert(
            self.module,
            before,
            result,
        )
        self.state = result.state

    @precondition(
        lambda self: (
            self.policy == "FLOOR_ONLY"
            and self.hard_count == 0
            and self.buy_stage == "NONE"
            and not self.cross_kind_checked
        )
    )
    @rule(first_kind=st.sampled_from(("BEST_BID", "TRADE")))
    def cross_kind_step_limit_uses_last_eligible_primary(
        self,
        first_kind: str,
    ) -> None:
        """A large trade/bid discontinuity cannot become corroboration."""
        first_units = self.last_bid
        self.sequence += 1
        self.source_time += 6
        first = protection_fixtures._occurrence(
            self.module,
            f"stateful-cross-kind-first-{first_kind.lower()}-{self.sequence}",
            kind=first_kind,
            bid=first_units if first_kind == "BEST_BID" else None,
            ask=first_units + 1 if first_kind == "BEST_BID" else None,
            trade=first_units if first_kind == "TRADE" else None,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        first_result = self._deliver(first)
        self.state = first_result.state
        self.cross_kind_checked = True
        assert first_result.goal is None

        self.sequence += 1
        self.source_time += 6
        second_kind = "TRADE" if first_kind == "BEST_BID" else "BEST_BID"
        second_units = max(160, first_units * 2)
        second = protection_fixtures._occurrence(
            self.module,
            f"stateful-cross-kind-second-{second_kind.lower()}-{self.sequence}",
            kind=second_kind,
            bid=second_units if second_kind == "BEST_BID" else None,
            ask=second_units + 1 if second_kind == "BEST_BID" else None,
            trade=second_units if second_kind == "TRADE" else None,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before = self.state
        rejected = self._deliver(second)
        protection_fixtures._assert_recorded_market_inert(
            self.module,
            before,
            rejected,
        )
        self.state = rejected.state

        self.market_epoch += 1
        self.sequence = 1
        self.source_time += 6
        restart = protection_fixtures._occurrence(
            self.module,
            f"stateful-cross-kind-restart-{self.market_epoch}",
            bid=100,
            ask=101,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        restarted = self._deliver(restart)
        self.state = restarted.state
        self.last_occurrence = restart
        self.last_accepted_source_time = self.source_time
        self.last_accepted_sequence = self.sequence
        self.last_bid = 100
        self.hard_count = 0
        self.trail_count = 0
        assert restarted.goal is None

    @precondition(lambda self: self.policy == "TRAIL_ACTIVE")
    @rule()
    def optional_atr_and_structure_inputs_can_only_tighten_a_trail(self) -> None:
        """Optional corroborating inputs never loosen the independent percent floor."""
        assert self.high_water is not None and self.trail is not None
        self.sequence += 1
        self.source_time += 6
        percent_floor = -(-(self.high_water * 23) // 25)
        atr_floor = self.high_water - 5
        structure_floor = self.high_water - 1
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-optional-trail-{self.market_epoch}-{self.sequence}",
            bid=self.high_water,
            ask=self.high_water + 1,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
            atr_distance=2,
            structure_trail=structure_floor,
        )
        self.trail = max(
            self.trail,
            percent_floor,
            atr_floor,
            structure_floor,
        )
        result = self._deliver(occurrence)
        self.state = result.state
        self.last_occurrence = occurrence
        self.last_accepted_source_time = self.source_time
        self.last_accepted_sequence = self.sequence
        self.last_bid = self.high_water
        self.hard_count = 0
        self.trail_count = 0
        assert result.state.policy is not None
        assert result.state.trail.exact_value == self.trail
        assert result.goal is None

    @precondition(lambda self: self.policy == "FLOOR_ONLY" and self.hard_count == 0)
    @rule()
    def interruption_reopen_epoch_requires_fresh_corroboration(self) -> None:
        """A halt and new epoch reset corroboration in this shared history."""
        self.sequence += 1
        self.source_time += 6
        first = protection_fixtures._occurrence(
            self.module,
            f"stateful-epoch-first-{self.market_epoch}-{self.sequence}",
            bid=92,
            ask=93,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        first_result = self._deliver(first)
        self.state = first_result.state
        assert first_result.goal is None
        self.hard_count = 1

        self.sequence += 1
        self.source_time += 6
        interrupted = protection_fixtures._occurrence(
            self.module,
            f"stateful-epoch-halt-{self.market_epoch}-{self.sequence}",
            bid=92,
            ask=93,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
            halted=True,
        )
        halted = self._deliver(interrupted)
        self.state = halted.state
        assert halted.goal is None
        self.sequence += 1
        self.source_time += 6
        same_epoch = protection_fixtures._occurrence(
            self.module,
            f"stateful-epoch-same-{self.market_epoch}-{self.sequence}",
            bid=91,
            ask=92,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        before_reopen = self.state
        not_reopened = self._deliver(same_epoch)
        protection_fixtures._assert_recorded_market_inert(
            self.module,
            before_reopen,
            not_reopened,
        )
        self.state = not_reopened.state
        self.market_epoch += 1
        self.sequence = 1
        self.source_time += 6
        self.hard_count = 0
        reopen_first = protection_fixtures._occurrence(
            self.module,
            f"stateful-epoch-reopen-first-{self.market_epoch}",
            bid=92,
            ask=93,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        reopened = self._deliver(reopen_first)
        self.state = reopened.state
        assert reopened.goal is None
        self.hard_count = 1
        self.sequence += 1
        self.source_time += 6
        reopen_second = protection_fixtures._occurrence(
            self.module,
            f"stateful-epoch-reopen-second-{self.market_epoch}",
            bid=92,
            ask=93,
            sequence=self.sequence,
            source_time=self.source_time,
            evaluation_time=self.source_time + 4,
            market_epoch=self.market_epoch,
        )
        bailed = self._deliver(reopen_second)
        self.state = bailed.state
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        self.policy = "HARD_BAIL"
        self.hard_count = 2
        self.last_occurrence = reopen_second
        self.last_accepted_source_time = self.source_time
        self.last_accepted_sequence = self.sequence
        self.last_bid = 92
        self.waiting = self.buy_stage in {"OPEN", "TERMINAL"}
        assert bailed.state.policy is policy.HARD_BAIL
        assert bailed.state.waiting_buy_resolution is self.waiting
        if self.waiting:
            assert bailed.goal is None
        else:
            assert bailed.goal is not None

    @precondition(
        lambda self: (
            self.buy_stage == "NONE" and self.policy in {"FLOOR_ONLY", "TRAIL_ACTIVE"}
        )
    )
    @rule()
    def introduce_unresolved_buy_into_shared_history(self) -> None:
        """An owned unresolved BUY composes with later market-policy changes."""
        buy_chain, buy_effect, buy_leg, _ = (
            protection_fixtures._append_needs_review_effect(
                self.current,
                prefix="stateful-wait-buy",
                side=ExecutionSide.BUY,
                quantity=1,
            )
        )
        for transition in buy_chain:
            result = self._sync(transition)
            assert result.goal is None
        self.buy_effect = buy_effect
        self.buy_leg = buy_leg
        self.buy_stage = "OPEN"
        self.waiting = True

    @precondition(lambda self: self.buy_stage == "OPEN")
    @rule()
    def terminalize_unresolved_buy_in_shared_history(self) -> None:
        assert self.buy_effect is not None and self.buy_leg is not None
        _, terminal = protection_fixtures._terminal_fixture(
            self.current,
            effect_id=self.buy_effect,
            leg_key=self.buy_leg,
            label="stateful-wait-buy",
            cumulative_quantity=0,
        )
        result = self._sync(terminal)
        self.buy_stage = "TERMINAL"
        self.waiting = True
        assert result.state.waiting_buy_resolution is self.waiting
        assert result.goal is None

    @precondition(lambda self: self.buy_stage == "TERMINAL")
    @rule()
    def close_unresolved_buy_parent_in_shared_history(self) -> None:
        assert self.buy_effect is not None
        exit_was_waiting = self.policy in {"EXIT_NORMAL", "HARD_BAIL"}
        _, closed = protection_fixtures._close_parent_fixture(
            self.current,
            effect_id=self.buy_effect,
            label="stateful-wait-buy",
        )
        released = self._sync(closed)
        self.buy_stage = "CLOSED"
        self.waiting = False
        assert released.state.waiting_buy_resolution is False
        if exit_was_waiting:
            assert released.goal is not None
            expected_guard = (
                self.mandate.normal_guard
                if self.policy == "EXIT_NORMAL"
                else self.mandate.emergency_guard
            )
            assert released.goal.guard == expected_guard
        else:
            assert released.goal is None

    @invariant()
    def market_oracle_matches_public_state(self) -> None:
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        assert self.state.policy is getattr(policy, self.policy)
        if self.high_water is not None:
            assert self.state.high_watermark.exact_value == self.high_water
        if self.trail is not None:
            assert self.state.trail.exact_value == self.trail
        assert self.state.waiting_buy_resolution is self.waiting
        assert self.state.raw_quantity == 4
        assert self.state.execution_commitment == self.current.execution.commitment


def _registered_rule(
    machine_type: type[RuleBasedStateMachine],
    name: str,
) -> Any:
    matches = [
        registered
        for registered in machine_type.setup_state().rules
        if registered.function.__name__ == name
    ]
    assert len(matches) == 1, f"expected one registered Hypothesis rule named {name!r}"
    registered = matches[0]
    assert registered.preconditions, (
        f"high-risk rule {name!r} lost its reachability gate"
    )
    return registered


def _execute_registered(
    machine: RuleBasedStateMachine,
    name: str,
    **kwargs: object,
) -> object:
    registered = _registered_rule(type(machine), name)
    assert all(predicate(machine) for predicate in registered.preconditions), (
        f"registered high-risk rule {name!r} is unreachable in the directed history"
    )
    registered.function(machine, **kwargs)
    result = machine.last_result
    assert result is not None
    return result


def test_high_risk_stateful_rules_are_registered_with_preconditions() -> None:
    """A removed decorator or precondition cannot silently erase generated coverage."""
    expected = {
        ProtectionEconomicsMachine: {
            "correction_bust_and_authentic_restore_compose_with_later_history",
            "incompatible_tick_loss_and_restore_advance_shared_history",
        },
        ProtectionMarketMachine: {
            "changed_context_replay_preserves_between_time_successor",
            "cross_kind_step_limit_uses_last_eligible_primary",
            "interruption_reopen_epoch_requires_fresh_corroboration",
            "introduce_unresolved_buy_into_shared_history",
            "terminalize_unresolved_buy_in_shared_history",
            "close_unresolved_buy_parent_in_shared_history",
        },
    }
    for machine_type, names in expected.items():
        for name in names:
            _registered_rule(machine_type, name)


def test_high_risk_stateful_rules_advance_one_machine_history() -> None:
    """Drive registered rules through the exact risky compositions they must cover."""
    economics = ProtectionEconomicsMachine()
    _execute_registered(
        economics,
        "correction_bust_and_authentic_restore_compose_with_later_history",
        resulting_quantity=3,
        units=101,
    )
    assert economics.next_identity == 1
    assert economics.root_quantity == economics.raw_quantity == 3
    _execute_registered(
        economics,
        "incompatible_tick_loss_and_restore_advance_shared_history",
        units=120,
    )
    assert economics.next_identity == 2
    assert economics.formula_expected is True
    assert economics.expected_policy == "HARD_BAIL"

    replay_market = ProtectionMarketMachine()
    replay_successor = _execute_registered(
        replay_market,
        "changed_context_replay_preserves_between_time_successor",
        first_kind="TRADE",
        has_sequence=False,
    )
    assert replay_market.policy == "HARD_BAIL"
    assert replay_successor.goal is not None

    cross_kind_market = ProtectionMarketMachine()
    cross_kind = _execute_registered(
        cross_kind_market,
        "cross_kind_step_limit_uses_last_eligible_primary",
        first_kind="TRADE",
    )
    assert cross_kind_market.policy == "FLOOR_ONLY"
    assert cross_kind_market.market_epoch == 1
    assert cross_kind.goal is None

    market = ProtectionMarketMachine()
    _execute_registered(
        market,
        "introduce_unresolved_buy_into_shared_history",
    )
    assert market.buy_stage == "OPEN"
    interrupted = _execute_registered(
        market,
        "interruption_reopen_epoch_requires_fresh_corroboration",
    )
    assert market.policy == "HARD_BAIL"
    assert market.waiting is True
    assert interrupted.state.waiting_buy_resolution is True
    assert interrupted.goal is None
    terminal = _execute_registered(
        market,
        "terminalize_unresolved_buy_in_shared_history",
    )
    assert market.buy_stage == "TERMINAL"
    assert terminal.state.waiting_buy_resolution is True
    assert terminal.goal is None
    released = _execute_registered(
        market,
        "close_unresolved_buy_parent_in_shared_history",
    )
    assert market.buy_stage == "CLOSED"
    assert market.waiting is False
    assert released.state.waiting_buy_resolution is False
    assert released.goal is not None
    assert released.goal.guard == market.mandate.emergency_guard


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
