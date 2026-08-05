"""Bounded generated histories for the pure WO-0148 protection reducer.

The four machines keep their expected economics and market policy in plain test
data.  They never call a production classifier or formula helper to decide an
expected result.  Every real reducer input is replayed from the same immutable
predecessor to prove determinism and input immutability.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
import pytest

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


@dataclass(frozen=True)
class _LifecycleCounterexample:
    """One literal trace and one independently named rule-breaking variant."""

    family: str
    mutation: str
    run: Callable[[bool], tuple[str, ...]]
    expected: tuple[str, ...]
    mutated: tuple[str, ...]


def _cursor_before_context_trace(mutated: bool) -> tuple[str, ...]:
    """A crossed first delivery consumes its coordinate before quote checks."""
    cursor = 0
    trace: list[str] = []
    if mutated:
        trace.append(f"REFUSED@{cursor}:crossed")
        cursor = 1
        trace.append(f"APPLIED@{cursor}:friendly-redelivery")
    else:
        cursor = 1
        trace.append(f"APPLIED@{cursor}:crossed-no-evidence")
        trace.append(f"EXACT_REPLAY@{cursor}:friendly-redelivery")
    return tuple(trace)


def _replay_conflict_before_recovery_trace(mutated: bool) -> tuple[str, ...]:
    """The retained current coordinate is classified before recovery admission."""
    expected_epoch = 1
    trace = [f"INVALIDATED:expect-{expected_epoch}"]
    if mutated:
        trace.extend(("STALE:current-replay", "STALE:current-conflict"))
    else:
        trace.extend(("EXACT_REPLAY:current", "REFUSED:current-conflict"))
    trace.append("APPLIED:epoch-1-baseline")
    return tuple(trace)


def _exact_next_recovery_trace(mutated: bool) -> tuple[str, ...]:
    """Only the already-fixed exact successor epoch may recover."""
    trace: list[str] = []
    if mutated:
        trace.append("APPLIED_RECOVERY:epoch-2")
        trace.extend(("STALE:epoch-0", "REFUSED:epoch-1-after-recovery"))
    else:
        trace.extend(
            (
                "REFUSED:epoch-2",
                "STALE:epoch-0",
                "APPLIED_RECOVERY:epoch-1",
            )
        )
    return tuple(trace)


def _halt_recovery_trace(mutated: bool) -> tuple[str, ...]:
    """A halt consumes its coordinate and requires a fresh successor epoch."""
    trace = ["APPLIED_HALT:epoch-0@1"]
    if mutated:
        trace.append("APPLIED_RECOVERY:epoch-0@2")
    else:
        trace.extend(
            (
                "STALE:epoch-0@2",
                "APPLIED_NO_RECOVERY:epoch-1@2-halted",
                "APPLIED_RECOVERY:epoch-1@3",
            )
        )
    return tuple(trace)


def _baseline_goal_suppression_trace(mutated: bool) -> tuple[str, ...]:
    """Sticky exit policy never grants a goal while recovery is incomplete."""
    trace = ["HARD_BAIL:goal", "INVALIDATED:no-goal"]
    trace.append("PROJECTION:goal" if mutated else "PROJECTION:no-goal")
    trace.extend(
        (
            "INVALID_BASELINE:no-goal",
            "VALID_BASELINE:no-goal",
            "LATER_MARKET:goal",
        )
    )
    return tuple(trace)


def _terminal_exhaustion_trace(mutated: bool) -> tuple[str, ...]:
    """Maximum is terminal for market authority but not execution economics."""
    if mutated:
        return (
            "APPLIED@0:wrapped",
            "APPLIED@1:continued",
            "PROJECTION_ECONOMICS:goal",
        )
    return (
        "APPLIED@MAX:exhausted-alert",
        "EXACT_REPLAY@MAX",
        "STALE@MAX-1",
        "REFUSED:novel-market",
        "PROJECTION_ECONOMICS:no-goal",
    )


def _sequenced_time_regression_trace(mutated: bool) -> tuple[str, ...]:
    """A greater sequence cannot move the generation source-time watermark back."""
    if mutated:
        return (
            "APPLIED@SEQ2:time-9-evidence",
            "SERVING:source-time-9",
        )
    return (
        "APPLIED@SEQ2:baseline-alert",
        "BASELINE_REQUIRED:source-time-10",
        "EXACT_REPLAY@SEQ2",
    )


def _source_time_corroboration_trace(mutated: bool) -> tuple[str, ...]:
    """Only later distinct source times can complete corroboration."""
    trace = ["BASELINE@10:count-0", "APPLIED@11:count-1"]
    if mutated:
        trace.extend(("EXACT_REPLAY@11:count-2-goal", "APPLIED@12:sticky-goal"))
    else:
        trace.extend(("EXACT_REPLAY@11:count-1", "APPLIED@12:count-2-goal"))
    return tuple(trace)


_LIFECYCLE_COUNTEREXAMPLES = (
    _LifecycleCounterexample(
        family="cursor-before-context",
        mutation="delay-cursor-reservation-until-after-context",
        run=_cursor_before_context_trace,
        expected=(
            "APPLIED@1:crossed-no-evidence",
            "EXACT_REPLAY@1:friendly-redelivery",
        ),
        mutated=("REFUSED@0:crossed", "APPLIED@1:friendly-redelivery"),
    ),
    _LifecycleCounterexample(
        family="replay-conflict-before-recovery",
        mutation="apply-recovery-epoch-gate-before-current-coordinate",
        run=_replay_conflict_before_recovery_trace,
        expected=(
            "INVALIDATED:expect-1",
            "EXACT_REPLAY:current",
            "REFUSED:current-conflict",
            "APPLIED:epoch-1-baseline",
        ),
        mutated=(
            "INVALIDATED:expect-1",
            "STALE:current-replay",
            "STALE:current-conflict",
            "APPLIED:epoch-1-baseline",
        ),
    ),
    _LifecycleCounterexample(
        family="exact-next-recovery",
        mutation="admit-any-epoch-at-or-above-successor",
        run=_exact_next_recovery_trace,
        expected=(
            "REFUSED:epoch-2",
            "STALE:epoch-0",
            "APPLIED_RECOVERY:epoch-1",
        ),
        mutated=(
            "APPLIED_RECOVERY:epoch-2",
            "STALE:epoch-0",
            "REFUSED:epoch-1-after-recovery",
        ),
    ),
    _LifecycleCounterexample(
        family="halt-recovery",
        mutation="reopen-halt-within-committed-epoch",
        run=_halt_recovery_trace,
        expected=(
            "APPLIED_HALT:epoch-0@1",
            "STALE:epoch-0@2",
            "APPLIED_NO_RECOVERY:epoch-1@2-halted",
            "APPLIED_RECOVERY:epoch-1@3",
        ),
        mutated=("APPLIED_HALT:epoch-0@1", "APPLIED_RECOVERY:epoch-0@2"),
    ),
    _LifecycleCounterexample(
        family="baseline-goal-suppression",
        mutation="emit-sticky-goal-on-projection-while-baseline-required",
        run=_baseline_goal_suppression_trace,
        expected=(
            "HARD_BAIL:goal",
            "INVALIDATED:no-goal",
            "PROJECTION:no-goal",
            "INVALID_BASELINE:no-goal",
            "VALID_BASELINE:no-goal",
            "LATER_MARKET:goal",
        ),
        mutated=(
            "HARD_BAIL:goal",
            "INVALIDATED:no-goal",
            "PROJECTION:goal",
            "INVALID_BASELINE:no-goal",
            "VALID_BASELINE:no-goal",
            "LATER_MARKET:goal",
        ),
    ),
    _LifecycleCounterexample(
        family="terminal-exhaustion",
        mutation="wrap-maximum-coordinate-and-continue-serving",
        run=_terminal_exhaustion_trace,
        expected=(
            "APPLIED@MAX:exhausted-alert",
            "EXACT_REPLAY@MAX",
            "STALE@MAX-1",
            "REFUSED:novel-market",
            "PROJECTION_ECONOMICS:no-goal",
        ),
        mutated=(
            "APPLIED@0:wrapped",
            "APPLIED@1:continued",
            "PROJECTION_ECONOMICS:goal",
        ),
    ),
    _LifecycleCounterexample(
        family="sequenced-time-regression",
        mutation="replace-source-time-high-water-with-regressed-value",
        run=_sequenced_time_regression_trace,
        expected=(
            "APPLIED@SEQ2:baseline-alert",
            "BASELINE_REQUIRED:source-time-10",
            "EXACT_REPLAY@SEQ2",
        ),
        mutated=(
            "APPLIED@SEQ2:time-9-evidence",
            "SERVING:source-time-9",
        ),
    ),
    _LifecycleCounterexample(
        family="source-time-corroboration",
        mutation="count-exact-replay-as-second-occurrence",
        run=_source_time_corroboration_trace,
        expected=(
            "BASELINE@10:count-0",
            "APPLIED@11:count-1",
            "EXACT_REPLAY@11:count-1",
            "APPLIED@12:count-2-goal",
        ),
        mutated=(
            "BASELINE@10:count-0",
            "APPLIED@11:count-1",
            "EXACT_REPLAY@11:count-2-goal",
            "APPLIED@12:sticky-goal",
        ),
    ),
)


@pytest.mark.parametrize(
    "case",
    [
        pytest.param(case, id=f"{case.family}--{case.mutation}")
        for case in _LIFECYCLE_COUNTEREXAMPLES
    ],
)
def test_adr023_lifecycle_reference_kills_its_named_mutation(
    case: _LifecycleCounterexample,
) -> None:
    """Each ordering rule has its own literal, executable counterexample."""
    reference_trace = case.run(False)
    mutated_trace = case.run(True)
    assert reference_trace == case.expected
    assert mutated_trace == case.mutated
    assert mutated_trace != reference_trace


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
        (policy,) = protection_fixtures._required(
            self.module,
            "ProtectionPolicy",
        )
        assert busted_result.state.raw_quantity == 0
        assert busted_result.state.policy is policy.HARD_BAIL
        assert busted_result.goal is None
        self.expected_policy = "HARD_BAIL"

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
        assert restored_result.state.policy is policy.HARD_BAIL
        assert restored_result.critical_alert is None
        assert restored_result.goal is None

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


class _FixedModeProtectionMarketMachine(RuleBasedStateMachine):
    """Independent cursor/lifecycle model for one immutable ADR-023 mode."""

    SEQUENCE_MODE = ""

    def __init__(self) -> None:
        super().__init__()
        self.module = protection_fixtures._protection_module()
        fill = protection_fixtures._owned_fill_transition(
            label=f"stateful-{self.SEQUENCE_MODE.lower()}-market-root",
            quantity=4,
            units=100,
            capacity=4,
        )
        mandate = protection_fixtures._mandate(
            self.module,
            sequence_mode=self.SEQUENCE_MODE,
            max_age=1_000,
        )
        self.mandate, _, state = protection_fixtures._start(
            self.module,
            fill,
            mandate,
        )
        terminal, closed = protection_fixtures._close_base_parent(fill)
        self.state, self.projection, _ = protection_fixtures._sync_transitions(
            self.module,
            state,
            self.mandate,
            (terminal, closed),
        )
        self.current = closed
        self.committed_epoch = 0
        self.occurrence_epoch = 0
        self.expected_epoch: int | None = None
        self.coordinate = 0
        self.source_time = 0
        self.evaluation_time = 0
        self.baseline_required = False
        self.halted = False
        self.exhausted = False
        self.raw_quantity = 4
        self.last_occurrence = self._make_occurrence(
            coordinate=0,
            epoch=0,
            source_time=0,
            evaluation_time=0,
        )
        self.current_identity = self.last_occurrence.occurrence_id
        self.last_result: object | None = None

    def _is_sequenced(self) -> bool:
        return self.SEQUENCE_MODE == "SEQUENCED"

    def _is_serving(self) -> bool:
        return not self.baseline_required and not self.exhausted

    def _is_floor_serving(self) -> bool:
        return self._is_serving() and self.state.policy.value == "FLOOR_ONLY"

    def _next_coordinate(self) -> int:
        return self.coordinate + 1

    def _make_occurrence(
        self,
        *,
        coordinate: int,
        epoch: int | None = None,
        source_time: int | None = None,
        evaluation_time: int | None = None,
        bid: int | None = 100,
        ask: int | None = 101,
        kind: str = "BEST_BID",
        trade: int | None = None,
        halted: bool = False,
    ) -> object:
        retained_source_time = (
            source_time
            if source_time is not None
            else (self.source_time + 1 if self._is_sequenced() else coordinate)
        )
        retained_evaluation_time = (
            evaluation_time
            if evaluation_time is not None
            else max(self.evaluation_time + 1, retained_source_time)
        )
        return protection_fixtures._occurrence(
            self.module,
            (
                f"stateful-{self.SEQUENCE_MODE.lower()}-"
                f"{self.committed_epoch}-{epoch}-{coordinate}"
            ),
            kind=kind,
            bid=bid,
            ask=ask,
            trade=trade,
            sequence=coordinate if self._is_sequenced() else None,
            source_time=retained_source_time,
            evaluation_time=retained_evaluation_time,
            market_epoch=self.committed_epoch if epoch is None else epoch,
            source_id=self.mandate.evidence_policy.source_id,
            stream_generation=self.mandate.evidence_policy.stream_generation,
            position_scope=self.mandate.position_scope,
            session_id=self.mandate.session_id,
            halted=halted,
        )

    def _deliver(self, occurrence: object) -> object:
        result = protection_fixtures._reduce_market(
            self.module,
            self.state,
            self.projection,
            occurrence,
        )
        self.last_result = result
        return result

    def _invalidate(self) -> object:
        result = protection_fixtures._invalidate_market(
            self.module,
            self.state,
            self.projection,
        )
        self.last_result = result
        return result

    def _assert_result(
        self,
        result: object,
        disposition_name: str,
        *,
        alert_name: str | None = None,
    ) -> None:
        disposition, alert = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
            "ProtectionAlert",
        )
        assert result.disposition is getattr(disposition, disposition_name)
        assert result.critical_alert is (
            None if alert_name is None else getattr(alert, alert_name)
        )
        assert result.goal is None

    def _record_occurrence(self, occurrence: object, result: object) -> None:
        coordinate = (
            occurrence.source_sequence
            if self._is_sequenced()
            else occurrence.source_time
        )
        assert type(coordinate) is int
        self.state = result.state
        self.coordinate = coordinate
        self.occurrence_epoch = occurrence.market_epoch
        self.source_time = max(self.source_time, occurrence.source_time)
        self.evaluation_time = max(
            self.evaluation_time,
            occurrence.evaluation_time,
        )
        self.current_identity = occurrence.occurrence_id
        self.last_occurrence = occurrence

    def _enter_baseline_required(self, *, halted: bool | None = None) -> None:
        self.baseline_required = True
        self.expected_epoch = self.committed_epoch + 1
        if halted is not None:
            self.halted = halted

    def _record_recovery(self, occurrence: object, result: object) -> None:
        self._record_occurrence(occurrence, result)
        self.committed_epoch = occurrence.market_epoch
        self.expected_epoch = None
        self.baseline_required = False
        self.halted = False
        assert result.state._hard_bid_identity is None
        assert result.state._trade_identity is None
        assert result.state._trail_bid_identity is None

    def _sync_projection_transition(self, transition: object) -> object:
        projection = protection_fixtures._projection(
            self.module,
            transition,
            self.mandate,
        )
        result = protection_fixtures._reduce_projection(
            self.module,
            self.state,
            projection,
        )
        self.state = result.state
        self.projection = projection
        self.current = transition
        self.last_result = result
        return result

    @precondition(lambda self: self._is_floor_serving() and self.coordinate < 10_000)
    @rule(bid=st.integers(min_value=95, max_value=107))
    def advancing_nontriggering_bid_updates_only_bounded_state(self, bid: int) -> None:
        occurrence = self._make_occurrence(
            coordinate=self._next_coordinate(),
            bid=bid,
            ask=bid + 1,
        )
        result = self._deliver(occurrence)
        self._assert_result(result, "APPLIED")
        self._record_occurrence(occurrence, result)

    @precondition(lambda self: self.last_occurrence is not None)
    @rule()
    def exact_replay_preserves_state_and_delivery_watermark(self) -> None:
        before = self.state
        replay = self.last_occurrence
        if replay.evaluation_time < protection_fixtures._U64_MAX:
            replay = replace(
                replay,
                evaluation_time=replay.evaluation_time + 1,
            )
        result = self._deliver(replay)
        self._assert_result(result, "EXACT_REPLAY")
        assert result.state == before

    @precondition(lambda self: self._is_serving() and self.coordinate < 10_000)
    @rule()
    def wrong_sequence_shape_is_refused_without_cursor_reservation(self) -> None:
        next_coordinate = self._next_coordinate()
        source_time = self.source_time + 1
        occurrence = protection_fixtures._occurrence(
            self.module,
            f"stateful-{self.SEQUENCE_MODE.lower()}-wrong-mode",
            bid=100,
            ask=101,
            sequence=None if self._is_sequenced() else next_coordinate,
            source_time=source_time if self._is_sequenced() else next_coordinate,
            evaluation_time=max(self.evaluation_time + 1, source_time),
            market_epoch=self.committed_epoch,
            source_id=self.mandate.evidence_policy.source_id,
            stream_generation=self.mandate.evidence_policy.stream_generation,
            position_scope=self.mandate.position_scope,
            session_id=self.mandate.session_id,
        )
        before = self.state
        result = self._deliver(occurrence)
        self._assert_result(result, "REFUSED")
        assert result.state == before

    @precondition(lambda self: self._is_floor_serving() and self.coordinate < 10_000)
    @rule()
    def context_denial_reserves_cursor_before_replay_or_conflict(self) -> None:
        crossed = self._make_occurrence(
            coordinate=self._next_coordinate(),
            bid=101,
            ask=100,
        )
        denied = self._deliver(crossed)
        self._assert_result(denied, "APPLIED")
        self._record_occurrence(crossed, denied)

        before_replay = self.state
        replay = replace(
            crossed,
            evaluation_time=crossed.evaluation_time + 1,
        )
        replayed = self._deliver(replay)
        self._assert_result(replayed, "EXACT_REPLAY")
        assert replayed.state == before_replay

        conflict = replace(
            crossed,
            best_bid=protection_fixtures._price(99),
            best_ask=protection_fixtures._price(100),
        )
        conflicted = self._deliver(conflict)
        self._assert_result(
            conflicted,
            "APPLIED",
            alert_name="MARKET_BASELINE_REQUIRED",
        )
        self.state = conflicted.state
        self._enter_baseline_required()
        assert self.state._market_occurrence_identity == crossed.occurrence_id

    @precondition(lambda self: self._is_floor_serving() and self.coordinate < 10_000)
    @rule()
    def replay_and_conflict_precede_recovery_epoch_admission(self) -> None:
        occurrence = self._make_occurrence(
            coordinate=self._next_coordinate(),
        )
        applied = self._deliver(occurrence)
        self._assert_result(applied, "APPLIED")
        self._record_occurrence(occurrence, applied)

        invalidated = self._invalidate()
        self._assert_result(
            invalidated,
            "APPLIED",
            alert_name="MARKET_BASELINE_REQUIRED",
        )
        self.state = invalidated.state
        self._enter_baseline_required()

        before = self.state
        replay = replace(
            occurrence,
            evaluation_time=occurrence.evaluation_time + 1,
        )
        replayed = self._deliver(replay)
        self._assert_result(replayed, "EXACT_REPLAY")
        assert replayed.state == before

        conflict = replace(
            occurrence,
            best_bid=protection_fixtures._price(99),
            best_ask=protection_fixtures._price(100),
        )
        refused = self._deliver(conflict)
        self._assert_result(refused, "REFUSED")
        assert refused.state == before

    @precondition(
        lambda self: (
            self._is_floor_serving()
            and self.committed_epoch < protection_fixtures._U64_MAX - 1
            and self.coordinate < 10_000
        )
    )
    @rule()
    def invalidation_requires_exact_next_recovery_epoch(self) -> None:
        invalidated = self._invalidate()
        self._assert_result(
            invalidated,
            "APPLIED",
            alert_name="MARKET_BASELINE_REQUIRED",
        )
        self.state = invalidated.state
        self._enter_baseline_required()

        repeated = self._invalidate()
        self._assert_result(repeated, "EXACT_REPLAY")
        assert repeated.state == self.state

        assert self.expected_epoch is not None
        before = self.state
        future = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.expected_epoch + 1,
        )
        refused = self._deliver(future)
        self._assert_result(refused, "REFUSED")
        assert refused.state == before

        old = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.committed_epoch,
        )
        stale = self._deliver(old)
        self._assert_result(stale, "STALE")
        assert stale.state == before

        crossed = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.expected_epoch,
            bid=101,
            ask=100,
        )
        consumed = self._deliver(crossed)
        self._assert_result(consumed, "APPLIED")
        self._record_occurrence(crossed, consumed)
        assert self.state._market_baseline_required is True

        recovered = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.expected_epoch,
        )
        result = self._deliver(recovered)
        self._assert_result(result, "APPLIED")
        self._record_recovery(recovered, result)

    @precondition(
        lambda self: (
            self._is_floor_serving()
            and self.committed_epoch < protection_fixtures._U64_MAX - 1
            and self.coordinate < 10_000
        )
    )
    @rule()
    def halt_reopens_only_on_exact_next_epoch_baseline(self) -> None:
        halted_occurrence = self._make_occurrence(
            coordinate=self._next_coordinate(),
            halted=True,
        )
        halted = self._deliver(halted_occurrence)
        self._assert_result(
            halted,
            "APPLIED",
            alert_name="MARKET_BASELINE_REQUIRED",
        )
        self._record_occurrence(halted_occurrence, halted)
        self._enter_baseline_required(halted=True)

        before = self.state
        same_epoch = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.committed_epoch,
        )
        stale = self._deliver(same_epoch)
        self._assert_result(stale, "STALE")
        assert stale.state == before

        assert self.expected_epoch is not None
        baseline = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.expected_epoch,
        )
        reopened = self._deliver(baseline)
        self._assert_result(reopened, "APPLIED")
        self._record_recovery(baseline, reopened)

    @precondition(lambda self: self._is_floor_serving() and self.coordinate < 10_000)
    @rule()
    def baseline_required_suppresses_sticky_goal(self) -> None:
        first = self._make_occurrence(
            coordinate=self._next_coordinate(),
            bid=92,
            ask=93,
        )
        first_result = self._deliver(first)
        self._assert_result(first_result, "APPLIED")
        self._record_occurrence(first, first_result)

        second = self._make_occurrence(
            coordinate=self._next_coordinate(),
            bid=91,
            ask=92,
        )
        second_result = self._deliver(second)
        disposition, policy = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
            "ProtectionPolicy",
        )
        assert second_result.disposition is disposition.APPLIED
        assert second_result.state.policy is policy.HARD_BAIL
        assert second_result.goal is not None
        assert second_result.critical_alert is None
        self._record_occurrence(second, second_result)

        invalidated = self._invalidate()
        self._assert_result(
            invalidated,
            "APPLIED",
            alert_name="MARKET_BASELINE_REQUIRED",
        )
        self.state = invalidated.state
        self._enter_baseline_required()

        projection_only = protection_fixtures._reduce_projection(
            self.module,
            self.state,
            self.projection,
        )
        assert projection_only.goal is None
        assert projection_only.state._market_baseline_required is True

        assert self.expected_epoch is not None
        denied = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.expected_epoch,
            bid=101,
            ask=100,
        )
        denied_result = self._deliver(denied)
        self._assert_result(denied_result, "APPLIED")
        self._record_occurrence(denied, denied_result)

    @precondition(lambda self: self._is_floor_serving() and self.coordinate < 10_000)
    @rule()
    def strict_coordinate_max_enters_terminal_exhaustion(self) -> None:
        first = self._make_occurrence(
            coordinate=self._next_coordinate(),
            bid=92,
            ask=93,
        )
        first_result = self._deliver(first)
        self._assert_result(first_result, "APPLIED")
        self._record_occurrence(first, first_result)

        second = self._make_occurrence(
            coordinate=self._next_coordinate(),
            bid=91,
            ask=92,
        )
        second_result = self._deliver(second)
        disposition, policy = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
            "ProtectionPolicy",
        )
        assert second_result.disposition is disposition.APPLIED
        assert second_result.state.policy is policy.HARD_BAIL
        assert second_result.goal is not None
        assert second_result.critical_alert is None
        self._record_occurrence(second, second_result)

        maximum = protection_fixtures._U64_MAX
        maximum_occurrence = self._make_occurrence(
            coordinate=maximum,
            source_time=(self.source_time + 1 if self._is_sequenced() else maximum),
            evaluation_time=(
                self.evaluation_time + 1 if self._is_sequenced() else maximum
            ),
        )
        exhausted = self._deliver(maximum_occurrence)
        self._assert_result(
            exhausted,
            "APPLIED",
            alert_name="MARKET_COORDINATE_EXHAUSTED",
        )
        self._record_occurrence(maximum_occurrence, exhausted)
        self.baseline_required = True
        self.exhausted = True
        self.expected_epoch = None

        before = self.state
        replayed = self._deliver(maximum_occurrence)
        self._assert_result(replayed, "EXACT_REPLAY")
        assert replayed.state == before

        lower = self._make_occurrence(
            coordinate=maximum - 1,
            source_time=(self.source_time if self._is_sequenced() else maximum - 1),
            evaluation_time=(
                self.evaluation_time if self._is_sequenced() else maximum - 1
            ),
        )
        stale = self._deliver(lower)
        self._assert_result(stale, "STALE")
        assert stale.state == before

        conflict = replace(
            maximum_occurrence,
            best_bid=protection_fixtures._price(99),
            best_ask=protection_fixtures._price(100),
        )
        refused = self._deliver(conflict)
        self._assert_result(refused, "REFUSED")
        assert refused.state == before

        repeated = self._invalidate()
        self._assert_result(repeated, "EXACT_REPLAY")
        assert repeated.state == before

        projection_only = protection_fixtures._reduce_projection(
            self.module,
            self.state,
            self.projection,
        )
        assert projection_only.goal is None
        assert projection_only.state == before

        prefix = f"stateful-{self.SEQUENCE_MODE.lower()}-exhausted-economics"
        buy_chain, effect_id, leg_key, _ = (
            protection_fixtures._append_needs_review_effect(
                self.current,
                prefix=prefix,
                side=ExecutionSide.BUY,
                quantity=1,
            )
        )
        for transition in buy_chain:
            pending = self._sync_projection_transition(transition)
            assert pending.state._market_exhausted is True
            assert pending.goal is None

        prior_execution_commitment = self.state.execution_commitment
        filled = venue_fixtures.apply_venue_recovery_input(
            buy_chain[-1].book,
            buy_chain[-1].execution,
            RecordBrokerFillEvidence(
                input_id=VenueInputId(f"{prefix}-fill-input"),
                effect_id=effect_id,
                leg_key=leg_key,
                prior_cumulative_quantity=Quantity(0),
                resulting_cumulative_quantity=Quantity(1),
                fact=venue_fixtures._broker_fill(
                    f"{prefix}-fill-source",
                    f"{prefix}-fill-root",
                    leg_key=leg_key,
                    side=ExecutionSide.BUY,
                    quantity=1,
                    units=120,
                ),
                evidence_digest=b"\xb1" * 32,
            ),
        )
        assert filled.quantity_delta == 1
        economics = self._sync_projection_transition(filled)
        assert economics.state.raw_quantity == self.raw_quantity + 1
        assert economics.state.execution_commitment != prior_execution_commitment
        assert economics.state.policy is policy.HARD_BAIL
        assert economics.state._market_exhausted is True
        assert economics.goal is None

        _, terminal = protection_fixtures._terminal_fixture(
            filled,
            effect_id=effect_id,
            leg_key=leg_key,
            label=prefix,
            cumulative_quantity=1,
        )
        terminal_result = self._sync_projection_transition(terminal)
        assert terminal_result.goal is None
        _, closed = protection_fixtures._close_parent_fixture(
            terminal,
            effect_id=effect_id,
            label=prefix,
        )
        closed_result = self._sync_projection_transition(closed)
        assert closed_result.state.waiting_buy_resolution is False
        assert closed_result.state.policy is policy.HARD_BAIL
        assert closed_result.state._market_exhausted is True
        assert closed_result.goal is None
        self.raw_quantity += 1
        self.last_result = closed_result

    @precondition(
        lambda self: (
            self.baseline_required
            and not self.exhausted
            and self.expected_epoch is not None
            and self.coordinate < 10_000
        )
    )
    @rule()
    def invalid_baseline_candidate_consumes_coordinate_without_authority(
        self,
    ) -> None:
        assert self.expected_epoch is not None
        crossed = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.expected_epoch,
            bid=101,
            ask=100,
        )
        result = self._deliver(crossed)
        self._assert_result(result, "APPLIED")
        self._record_occurrence(crossed, result)
        assert self.state._market_baseline_required is True

    @precondition(
        lambda self: (
            self.baseline_required
            and not self.exhausted
            and self.expected_epoch is not None
            and self.coordinate < 10_000
        )
    )
    @rule()
    def valid_baseline_recovers_without_goal_or_corroboration(self) -> None:
        assert self.expected_epoch is not None
        baseline = self._make_occurrence(
            coordinate=self._next_coordinate(),
            epoch=self.expected_epoch,
        )
        result = self._deliver(baseline)
        self._assert_result(result, "APPLIED")
        self._record_recovery(baseline, result)

    @invariant()
    def bounded_cursor_matches_independent_lifecycle_model(self) -> None:
        state = self.state
        assert self.mandate.evidence_policy.sequence_mode.value == self.SEQUENCE_MODE
        assert state._market_committed_epoch == self.committed_epoch
        assert state._market_expected_epoch == self.expected_epoch
        assert state._market_occurrence_epoch == self.occurrence_epoch
        assert state._market_source_sequence == (
            self.coordinate if self._is_sequenced() else None
        )
        assert state._market_source_time == self.source_time
        assert state._market_evaluation_time == self.evaluation_time
        assert state._market_occurrence_identity == self.current_identity
        assert state._market_baseline_required is self.baseline_required
        assert state._market_halted is self.halted
        assert state._market_exhausted is self.exhausted
        for identity_name, source_time_name in (
            ("_hard_bid_identity", "_hard_bid_source_time"),
            ("_trade_identity", "_trade_source_time"),
            ("_trail_bid_identity", "_trail_bid_source_time"),
        ):
            assert (getattr(state, identity_name) is None) is (
                getattr(state, source_time_name) is None
            )
        if self.baseline_required:
            assert state._hard_bid_identity is None
            assert state._trade_identity is None
            assert state._trail_bid_identity is None
        assert state.raw_quantity == self.raw_quantity
        assert state.execution_commitment == self.current.execution.commitment


class ProtectionSequencedMarketMachine(_FixedModeProtectionMarketMachine):
    """Generated market histories for one immutable SEQUENCED mandate."""

    SEQUENCE_MODE = "SEQUENCED"

    @precondition(lambda self: self._is_floor_serving() and self.coordinate < 10_000)
    @rule()
    def greater_sequence_with_lower_time_requires_recovery(self) -> None:
        warm = self._make_occurrence(
            coordinate=self._next_coordinate(),
            source_time=self.source_time + 2,
        )
        warm_result = self._deliver(warm)
        self._assert_result(warm_result, "APPLIED")
        self._record_occurrence(warm, warm_result)
        retained_source_time = self.source_time

        regressed = self._make_occurrence(
            coordinate=self._next_coordinate(),
            source_time=retained_source_time - 1,
            evaluation_time=self.evaluation_time + 1,
        )
        result = self._deliver(regressed)
        self._assert_result(
            result,
            "APPLIED",
            alert_name="MARKET_BASELINE_REQUIRED",
        )
        self._record_occurrence(regressed, result)
        self._enter_baseline_required()
        assert self.source_time == retained_source_time
        assert self.state._market_source_time == retained_source_time


class ProtectionSourceTimeMarketMachine(_FixedModeProtectionMarketMachine):
    """Generated market histories for one immutable SOURCE_TIME mandate."""

    SEQUENCE_MODE = "SOURCE_TIME"

    @precondition(lambda self: self._is_floor_serving() and self.coordinate < 10_000)
    @rule()
    def two_strict_source_times_can_corroborate(self) -> None:
        first = self._make_occurrence(
            coordinate=self._next_coordinate(),
            bid=92,
            ask=93,
        )
        first_result = self._deliver(first)
        self._assert_result(first_result, "APPLIED")
        self._record_occurrence(first, first_result)

        second = self._make_occurrence(
            coordinate=self._next_coordinate(),
            bid=91,
            ask=92,
        )
        second_result = self._deliver(second)
        disposition, policy = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
            "ProtectionPolicy",
        )
        assert second_result.disposition is disposition.APPLIED
        assert second_result.state.policy is policy.HARD_BAIL
        assert second_result.goal is not None
        assert second_result.critical_alert is None
        self._record_occurrence(second, second_result)


class RetainedMarketPolicyMachine(RuleBasedStateMachine):
    """Fixed-mode generated histories retained from the accepted ADR-021 RED."""

    def __init__(self) -> None:
        super().__init__()
        self.module = protection_fixtures._protection_module()
        fill = protection_fixtures._owned_fill_transition(
            label="stateful-retained-policy-root",
            quantity=4,
            units=100,
            capacity=8,
        )
        mandate = protection_fixtures._mandate(
            self.module,
            sequence_mode="SEQUENCED",
            max_age=1_000,
        )
        self.mandate, _, state = protection_fixtures._start(
            self.module,
            fill,
            mandate,
        )
        terminal, closed = protection_fixtures._close_base_parent(fill)
        self.state, self.projection, _ = protection_fixtures._sync_transitions(
            self.module,
            state,
            self.mandate,
            (terminal, closed),
        )
        self.current = closed
        self.coordinate = 0
        self.source_time = 0
        self.evaluation_time = 0
        self.raw_quantity = 4
        self.used = False
        self.last_result: object | None = None

    def _sync(self, transition: object) -> object:
        projection = protection_fixtures._projection(
            self.module,
            transition,
            self.mandate,
        )
        result = protection_fixtures._reduce_projection(
            self.module,
            self.state,
            projection,
        )
        self.state = result.state
        self.projection = projection
        self.current = transition
        self.last_result = result
        return result

    def _deliver(
        self,
        *,
        label: str,
        kind: str = "BEST_BID",
        units: int,
        atr_distance: int | None = None,
        structure_trail: int | None = None,
    ) -> tuple[object, object]:
        coordinate = self.coordinate + 1
        source_time = self.source_time + 6
        occurrence = protection_fixtures._routed_occurrence(
            self.module,
            self.mandate,
            label,
            kind=kind,
            bid=None if kind == "TRADE" else units,
            ask=None if kind == "TRADE" else units + 1,
            trade=units if kind == "TRADE" else None,
            sequence=coordinate,
            source_time=source_time,
            evaluation_time=source_time + 1,
            market_epoch=0,
            atr_distance=atr_distance,
            structure_trail=structure_trail,
        )
        result = protection_fixtures._reduce_market(
            self.module,
            self.state,
            self.projection,
            occurrence,
        )
        (disposition,) = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
        )
        assert result.disposition is disposition.APPLIED
        self.state = result.state
        self.coordinate = coordinate
        self.source_time = source_time
        self.evaluation_time = source_time + 1
        self.last_result = result
        return occurrence, result

    def _append_filled_buy(
        self,
        *,
        prefix: str,
        units: int,
        close: bool,
    ) -> tuple[object, object, object]:
        buy_chain, effect_id, leg_key, _ = (
            protection_fixtures._append_needs_review_effect(
                self.current,
                prefix=prefix,
                side=ExecutionSide.BUY,
                quantity=1,
            )
        )
        for transition in buy_chain:
            pending = self._sync(transition)
            assert pending.goal is None
        filled = venue_fixtures.apply_venue_recovery_input(
            buy_chain[-1].book,
            buy_chain[-1].execution,
            RecordBrokerFillEvidence(
                input_id=VenueInputId(f"{prefix}-fill-input"),
                effect_id=effect_id,
                leg_key=leg_key,
                prior_cumulative_quantity=Quantity(0),
                resulting_cumulative_quantity=Quantity(1),
                fact=venue_fixtures._broker_fill(
                    f"{prefix}-fill-source",
                    f"{prefix}-fill-root",
                    leg_key=leg_key,
                    side=ExecutionSide.BUY,
                    quantity=1,
                    units=units,
                ),
                evidence_digest=b"\xb2" * 32,
            ),
        )
        assert filled.quantity_delta == 1
        filled_result = self._sync(filled)
        self.raw_quantity += 1
        assert filled_result.state.raw_quantity == self.raw_quantity
        if not close:
            return filled, effect_id, leg_key

        _, terminal = protection_fixtures._terminal_fixture(
            filled,
            effect_id=effect_id,
            leg_key=leg_key,
            label=prefix,
            cumulative_quantity=1,
        )
        self._sync(terminal)
        _, closed = protection_fixtures._close_parent_fixture(
            terminal,
            effect_id=effect_id,
            label=prefix,
        )
        self._sync(closed)
        return closed, effect_id, leg_key

    @precondition(lambda self: not self.used)
    @rule(first_kind=st.sampled_from(("BEST_BID", "TRADE")))
    def cross_kind_step_deviation_is_cursor_only(
        self,
        first_kind: str,
    ) -> None:
        _, first = self._deliver(
            label=f"retained-cross-kind-{first_kind}-first",
            kind=first_kind,
            units=100,
        )
        assert first.goal is None
        before_policy = self.state.policy
        before_high = self.state.high_watermark
        before_trail = self.state.trail
        second_kind = "TRADE" if first_kind == "BEST_BID" else "BEST_BID"
        _, deviated = self._deliver(
            label=f"retained-cross-kind-{first_kind}-deviation",
            kind=second_kind,
            units=160,
        )
        assert deviated.state.policy is before_policy
        assert deviated.state.high_watermark == before_high
        assert deviated.state.trail == before_trail
        assert deviated.goal is None
        assert deviated.critical_alert is None
        self.used = True

    @precondition(lambda self: not self.used)
    @rule()
    def optional_atr_and_structure_tighten_independently(self) -> None:
        _, activated = self._deliver(
            label="retained-optional-activation",
            units=120,
        )
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        expected_percent = _ceil_exact(Fraction(120) * Fraction(23, 25))
        assert activated.state.policy is policy.TRAIL_ACTIVE
        assert activated.state.high_watermark.exact_value == 120
        assert activated.state.trail.exact_value == expected_percent

        _, tightened = self._deliver(
            label="retained-optional-tightening",
            units=120,
            atr_distance=2,
            structure_trail=118,
        )
        expected_atr = _ceil_exact(Fraction(120) - Fraction(5, 2) * 2)
        expected_structure = Fraction(118)
        expected = max(expected_percent, expected_atr, expected_structure)
        assert expected == 118
        assert tightened.state.policy is policy.TRAIL_ACTIVE
        assert tightened.state.high_watermark.exact_value == 120
        assert tightened.state.trail.exact_value == expected
        assert tightened.goal is None
        self.used = True

    @precondition(lambda self: not self.used)
    @rule()
    def high_water_and_percent_trail_only_ratchet(self) -> None:
        (policy,) = protection_fixtures._required(self.module, "ProtectionPolicy")
        _, activated = self._deliver(
            label="retained-ratchet-activation",
            units=108,
        )
        first_trail = _ceil_exact(Fraction(108) * Fraction(23, 25))
        assert activated.state.policy is policy.TRAIL_ACTIVE
        assert activated.state.high_watermark.exact_value == 108
        assert activated.state.trail.exact_value == first_trail

        _, raised = self._deliver(
            label="retained-ratchet-raised",
            units=125,
        )
        raised_trail = _ceil_exact(Fraction(125) * Fraction(23, 25))
        assert raised.state.high_watermark.exact_value == 125
        assert raised.state.trail.exact_value == raised_trail

        _, lower = self._deliver(
            label="retained-ratchet-lower",
            units=120,
        )
        assert lower.state.high_watermark.exact_value == 125
        assert lower.state.trail.exact_value == raised_trail
        assert lower.goal is None
        self.used = True

    @precondition(lambda self: not self.used)
    @rule()
    def trigger_change_resets_the_corroboration_branch(self) -> None:
        old_occurrence, first = self._deliver(
            label="retained-trigger-old-branch",
            units=92,
        )
        policy, disposition = protection_fixtures._required(
            self.module,
            "ProtectionPolicy",
            "ProtectionDisposition",
        )
        assert first.state.policy is policy.FLOOR_ONLY
        assert first.goal is None

        self._append_filled_buy(
            prefix="retained-trigger-ratchet",
            units=200,
            close=True,
        )
        expected_average = Fraction(4 * 100 + 200, 5)
        expected_trigger = _ceil_exact(expected_average * Fraction(37, 40))
        assert expected_trigger == 111
        assert self.state.armed_hard_bail_trigger.exact_value == expected_trigger

        replay = protection_fixtures._reduce_market(
            self.module,
            self.state,
            self.projection,
            replace(old_occurrence, evaluation_time=old_occurrence.evaluation_time + 1),
        )
        assert replay.disposition is disposition.EXACT_REPLAY
        assert replay.state == self.state
        assert replay.goal is None

        _, new_first = self._deliver(
            label="retained-trigger-new-branch-first",
            units=110,
        )
        assert new_first.state.policy is policy.FLOOR_ONLY
        assert new_first.goal is None
        _, new_second = self._deliver(
            label="retained-trigger-new-branch-second",
            units=109,
        )
        assert new_second.state.policy is policy.HARD_BAIL
        assert new_second.goal is not None
        self.used = True

    @precondition(lambda self: not self.used)
    @rule()
    def venue_rollback_and_current_execution_mismatch_fail_closed(self) -> None:
        old_projection = self.projection
        old_current = self.current
        self._append_filled_buy(
            prefix="retained-rollback-current",
            units=120,
            close=False,
        )
        before = self.state
        stale = protection_fixtures._reduce_projection(
            self.module,
            self.state,
            old_projection,
        )
        (disposition,) = protection_fixtures._required(
            self.module,
            "ProtectionDisposition",
        )
        assert stale.disposition is disposition.STALE
        assert stale.state == before
        mixed = protection_fixtures._clone_opaque(
            self.current,
            execution=old_current.execution,
        )
        with pytest.raises(ValueError):
            protection_fixtures._projection(self.module, mixed, self.mandate)
        self.last_result = stale
        self.used = True

    @precondition(lambda self: not self.used)
    @rule()
    def unresolved_buy_waits_through_terminal_and_releases_on_parent_close(
        self,
    ) -> None:
        prefix = "retained-unresolved-buy"
        buy_chain, effect_id, leg_key, _ = (
            protection_fixtures._append_needs_review_effect(
                self.current,
                prefix=prefix,
                side=ExecutionSide.BUY,
                quantity=1,
            )
        )
        for transition in buy_chain:
            pending = self._sync(transition)
            assert pending.goal is None
        assert self.state.waiting_buy_resolution is True

        _, first = self._deliver(label="retained-wait-hard-1", units=92)
        assert first.goal is None
        _, waiting = self._deliver(label="retained-wait-hard-2", units=91)
        policy, urgency = protection_fixtures._required(
            self.module,
            "ProtectionPolicy",
            "ProtectionUrgency",
        )
        assert waiting.state.policy is policy.HARD_BAIL
        assert waiting.state.waiting_buy_resolution is True
        assert waiting.goal is None

        _, terminal = protection_fixtures._terminal_fixture(
            buy_chain[-1],
            effect_id=effect_id,
            leg_key=leg_key,
            label=prefix,
            cumulative_quantity=0,
        )
        terminal_result = self._sync(terminal)
        assert terminal_result.state.waiting_buy_resolution is True
        assert terminal_result.goal is None
        _, closed = protection_fixtures._close_parent_fixture(
            terminal,
            effect_id=effect_id,
            label=prefix,
        )
        released = self._sync(closed)
        assert released.state.policy is policy.HARD_BAIL
        assert released.state.waiting_buy_resolution is False
        assert released.goal is not None
        assert released.goal.urgency is urgency.EMERGENCY
        assert released.goal.guard == self.mandate.emergency_guard
        self.used = True

    @invariant()
    def retained_policy_state_matches_its_bounded_reference(self) -> None:
        assert self.mandate.evidence_policy.sequence_mode.value == "SEQUENCED"
        assert self.state.raw_quantity == self.raw_quantity
        assert self.state.execution_commitment == self.current.execution.commitment
        assert not hasattr(self.state, "_seen_occurrence_receipts")


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
    shared_market_rules = {
        "context_denial_reserves_cursor_before_replay_or_conflict",
        "replay_and_conflict_precede_recovery_epoch_admission",
        "invalidation_requires_exact_next_recovery_epoch",
        "halt_reopens_only_on_exact_next_epoch_baseline",
        "baseline_required_suppresses_sticky_goal",
        "strict_coordinate_max_enters_terminal_exhaustion",
    }
    expected = {
        ProtectionEconomicsMachine: {
            "correction_bust_and_authentic_restore_compose_with_later_history",
            "incompatible_tick_loss_and_restore_advance_shared_history",
        },
        ProtectionSequencedMarketMachine: shared_market_rules
        | {"greater_sequence_with_lower_time_requires_recovery"},
        ProtectionSourceTimeMarketMachine: shared_market_rules
        | {"two_strict_source_times_can_corroborate"},
        RetainedMarketPolicyMachine: {
            "cross_kind_step_deviation_is_cursor_only",
            "optional_atr_and_structure_tighten_independently",
            "high_water_and_percent_trail_only_ratchet",
            "trigger_change_resets_the_corroboration_branch",
            "venue_rollback_and_current_execution_mismatch_fail_closed",
            "unresolved_buy_waits_through_terminal_and_releases_on_parent_close",
        },
    }
    for machine_type, names in expected.items():
        for name in names:
            _registered_rule(machine_type, name)


def test_high_risk_economics_rules_advance_one_machine_history() -> None:
    """Retained economics rules still compose on one directed history."""
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


@pytest.mark.parametrize(
    ("machine_type", "rule_name"),
    [
        pytest.param(
            ProtectionSequencedMarketMachine,
            "context_denial_reserves_cursor_before_replay_or_conflict",
            id="sequenced-cursor-before-context",
        ),
        pytest.param(
            ProtectionSequencedMarketMachine,
            "replay_and_conflict_precede_recovery_epoch_admission",
            id="sequenced-replay-conflict-precedence",
        ),
        pytest.param(
            ProtectionSequencedMarketMachine,
            "invalidation_requires_exact_next_recovery_epoch",
            id="sequenced-exact-next-recovery",
        ),
        pytest.param(
            ProtectionSequencedMarketMachine,
            "halt_reopens_only_on_exact_next_epoch_baseline",
            id="sequenced-halt-recovery",
        ),
        pytest.param(
            ProtectionSequencedMarketMachine,
            "baseline_required_suppresses_sticky_goal",
            id="sequenced-goal-suppression",
        ),
        pytest.param(
            ProtectionSequencedMarketMachine,
            "strict_coordinate_max_enters_terminal_exhaustion",
            id="sequenced-terminal-exhaustion",
        ),
        pytest.param(
            ProtectionSequencedMarketMachine,
            "greater_sequence_with_lower_time_requires_recovery",
            id="sequenced-time-regression",
        ),
        pytest.param(
            ProtectionSourceTimeMarketMachine,
            "context_denial_reserves_cursor_before_replay_or_conflict",
            id="source-time-cursor-before-context",
        ),
        pytest.param(
            ProtectionSourceTimeMarketMachine,
            "replay_and_conflict_precede_recovery_epoch_admission",
            id="source-time-replay-conflict-precedence",
        ),
        pytest.param(
            ProtectionSourceTimeMarketMachine,
            "invalidation_requires_exact_next_recovery_epoch",
            id="source-time-exact-next-recovery",
        ),
        pytest.param(
            ProtectionSourceTimeMarketMachine,
            "halt_reopens_only_on_exact_next_epoch_baseline",
            id="source-time-halt-recovery",
        ),
        pytest.param(
            ProtectionSourceTimeMarketMachine,
            "baseline_required_suppresses_sticky_goal",
            id="source-time-goal-suppression",
        ),
        pytest.param(
            ProtectionSourceTimeMarketMachine,
            "strict_coordinate_max_enters_terminal_exhaustion",
            id="source-time-terminal-exhaustion",
        ),
        pytest.param(
            ProtectionSourceTimeMarketMachine,
            "two_strict_source_times_can_corroborate",
            id="source-time-strict-corroboration",
        ),
    ],
)
def test_high_risk_market_rules_advance_directed_histories(
    machine_type: type[_FixedModeProtectionMarketMachine],
    rule_name: str,
) -> None:
    """Each high-risk lifecycle path remains directly executable after GREEN."""
    machine = machine_type()
    result = _execute_registered(machine, rule_name)
    assert result.state == machine.state


@pytest.mark.parametrize(
    ("rule_name", "kwargs"),
    [
        pytest.param(
            "cross_kind_step_deviation_is_cursor_only",
            {"first_kind": "BEST_BID"},
            id="cross-kind-bid-to-trade",
        ),
        pytest.param(
            "cross_kind_step_deviation_is_cursor_only",
            {"first_kind": "TRADE"},
            id="cross-kind-trade-to-bid",
        ),
        pytest.param(
            "optional_atr_and_structure_tighten_independently",
            {},
            id="optional-atr-structure",
        ),
        pytest.param(
            "high_water_and_percent_trail_only_ratchet",
            {},
            id="high-water-trail-ratchet",
        ),
        pytest.param(
            "trigger_change_resets_the_corroboration_branch",
            {},
            id="trigger-branch-reset",
        ),
        pytest.param(
            "venue_rollback_and_current_execution_mismatch_fail_closed",
            {},
            id="venue-rollback-current-execution",
        ),
        pytest.param(
            "unresolved_buy_waits_through_terminal_and_releases_on_parent_close",
            {},
            id="unresolved-buy-wait-release",
        ),
    ],
)
def test_retained_market_policy_rules_advance_directed_histories(
    rule_name: str,
    kwargs: dict[str, object],
) -> None:
    """Every retained ADR-021 family is registered and directly reachable."""
    machine = RetainedMarketPolicyMachine()
    result = _execute_registered(machine, rule_name, **kwargs)
    assert result.state == machine.state


TestProtectionEconomicsMachine = ProtectionEconomicsMachine.TestCase
TestProtectionEconomicsMachine.settings = settings(
    max_examples=20,
    stateful_step_count=12,
    deadline=None,
)

TestProtectionSequencedMarketMachine = ProtectionSequencedMarketMachine.TestCase
TestProtectionSequencedMarketMachine.settings = settings(
    max_examples=20,
    stateful_step_count=12,
    deadline=None,
)

TestProtectionSourceTimeMarketMachine = ProtectionSourceTimeMarketMachine.TestCase
TestProtectionSourceTimeMarketMachine.settings = settings(
    max_examples=20,
    stateful_step_count=12,
    deadline=None,
)

TestRetainedMarketPolicyMachine = RetainedMarketPolicyMachine.TestCase
TestRetainedMarketPolicyMachine.settings = settings(
    max_examples=20,
    stateful_step_count=1,
    deadline=None,
)
