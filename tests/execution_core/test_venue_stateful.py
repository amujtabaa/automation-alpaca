"""RED-first generated histories for the WO-0146 venue-recovery kernel.

The oracle below is deliberately smaller than the production model: plain
strings and dictionaries describe effect, acceptance, ownership, attempt, and
closure facts.  It does not call production helpers to decide an expected
transition.  The suite performs no I/O and its execution snapshot must remain
economically unchanged throughout every generated history.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from app.execution_core.fills import ExecutionSide, PositionScope
from app.execution_core.identity import (
    AccountId,
    ApplicationGenerationId,
    BrokerId,
    ClaimOccurrenceId,
    ClientOrderId,
    ClosureId,
    EffectId,
    EnvironmentId,
    EvidenceReference,
    MandateId,
    OrderId,
    RequestOccurrenceId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.position import ExecutionSnapshot
from app.execution_core.values import Quantity
from app.execution_core.venue import (
    AcceptanceProof,
    AcceptanceProofKind,
    BrokerEffectState,
    CancelBeforeDispatch,
    CloseAcceptanceSet,
    DiscoverVenueLeg,
    EffectKind,
    ObserveVenueStatus,
    PendingVenueOperation,
    RecordDispatchClaim,
    RecordPendingVenueOperation,
    RecordTransportOutcome,
    RecoverClaimedEffect,
    RequestedEffect,
    VenueAttemptState,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
    apply_venue_recovery_input,
)


_BROKER = BrokerId("alpaca")
_ENVIRONMENT = EnvironmentId("paper")
_ACCOUNT = AccountId("stateful-paper-account")
_GENERATION = ApplicationGenerationId("reset-generation-stateful")
_SYMBOL = SymbolId("AAPL")
_VENUE_SCOPE = VenueScope(
    generation=_GENERATION,
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
)
_POSITION_SCOPE = PositionScope(
    broker=_BROKER,
    environment=_ENVIRONMENT,
    account=_ACCOUNT,
    symbol_id=_SYMBOL,
)


@dataclass
class _ModelEffect:
    state: str = "REQUESTED"
    acceptance: str = "OPEN"
    claim: ClaimOccurrenceId | None = None
    proof_kind: str | None = None
    proof_reference: EvidenceReference | None = None


@dataclass
class _ModelAttempt:
    status: str = "WORKING"
    pending: str | None = None
    cumulative: int = 0


@dataclass
class _ModelClosure:
    closure_id: ClosureId
    ordinal: int
    predecessor: ClosureId | None
    status: str
    cumulative: int


_NONTERMINAL_PRECEDENCE = {
    "WORKING": 0,
    "PARTIALLY_FILLED": 1,
}
_TERMINAL_STATUSES = ("FILLED", "CANCELED", "REJECTED")


def _enum_value(value: object) -> str:
    return str(getattr(value, "value"))


class VenueRecoveryMachine(RuleBasedStateMachine):
    """Exercise multiple effects and one-to-many venue legs against a tiny oracle."""

    def __init__(self) -> None:
        super().__init__()
        self.book = VenueRecoveryBook.empty(_VENUE_SCOPE)
        self.execution = ExecutionSnapshot.flat(_POSITION_SCOPE)
        self.original_execution = self.execution
        self.effects: dict[EffectId, _ModelEffect] = {}
        self.owners: dict[VenueLegKey, EffectId] = {}
        self.active: dict[VenueLegKey, _ModelAttempt] = {}
        self.closures: dict[VenueLegKey, _ModelClosure] = {}
        self.applied_inputs: list[object] = []
        self._next_input = 0
        self._next_effect = 0
        self._next_claim = 0
        self._next_leg = 0
        self._next_observation = 0
        self._next_closure = 0

    def _input_id(self, label: str) -> VenueInputId:
        self._next_input += 1
        return VenueInputId(f"{label}-{self._next_input}")

    def _observation_id(self, label: str) -> VenueObservationId:
        self._next_observation += 1
        return VenueObservationId(f"{label}-{self._next_observation}")

    def _closure_id(self) -> ClosureId:
        self._next_closure += 1
        return ClosureId(f"closure-{self._next_closure}")

    def _leg_key(self) -> VenueLegKey:
        self._next_leg += 1
        return VenueLegKey(
            broker=_BROKER,
            environment=_ENVIRONMENT,
            account=_ACCOUNT,
            order_id=OrderId(f"venue-order-{self._next_leg}"),
        )

    def _commit(
        self,
        item: object,
        disposition: VenueRecoveryDisposition = VenueRecoveryDisposition.APPLIED,
    ) -> None:
        """Apply one legal input twice from identical immutable predecessors."""

        before = (self.book, self.execution, item)
        first = apply_venue_recovery_input(self.book, self.execution, item)
        second = apply_venue_recovery_input(self.book, self.execution, item)
        assert first == second
        assert before == (self.book, self.execution, item)
        assert first.disposition is disposition
        assert first.quantity_delta == 0
        assert first.execution == self.original_execution
        self.book = first.book
        self.execution = first.execution
        self.applied_inputs.append(item)

    def _refused(self, item: object, disposition: VenueRecoveryDisposition) -> None:
        before = (self.book, self.execution)
        transition = apply_venue_recovery_input(self.book, self.execution, item)
        assert transition.disposition is disposition
        assert transition.quantity_delta == 0
        assert (transition.book, transition.execution) == before

    def _has_active_leg(self, effect_id: EffectId) -> bool:
        return any(
            owner == effect_id and leg_key in self.active
            for leg_key, owner in self.owners.items()
        )

    def _acceptance_proof(
        self,
        effect_id: EffectId,
        kind: AcceptanceProofKind,
        evidence: EvidenceReference,
    ) -> AcceptanceProof:
        effect = self.book.effect(effect_id)
        assert effect is not None
        return AcceptanceProof(
            kind=kind,
            effect_scope=effect.scope,
            claim_occurrence_id=(
                None
                if kind is AcceptanceProofKind.NEVER_DISPATCHED
                else effect.claim_occurrence_id
            ),
            evidence_reference=evidence,
            evidence_digest=b"\xa6" * 32,
        )

    @rule()
    def request_effect(self) -> None:
        self._next_effect += 1
        number = self._next_effect
        effect_id = EffectId(f"effect-{number}")
        item = RequestedEffect(
            input_id=self._input_id("request"),
            effect_id=effect_id,
            request_occurrence_id=RequestOccurrenceId(f"request-{number}"),
            mandate_id=MandateId(f"mandate-{number}"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId(f"client-{number}"),
            symbol_id=_SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(10 + number),
            economic_scope=f"AAPL|BUY|effect-{number}".encode(),
        )
        self._commit(item)
        self.effects[effect_id] = _ModelEffect()

    @precondition(
        lambda self: any(
            effect.state == "REQUESTED" for effect in self.effects.values()
        )
    )
    @rule(data=st.data())
    def cancel_before_dispatch(self, data) -> None:
        candidates = [
            effect_id
            for effect_id, effect in self.effects.items()
            if effect.state == "REQUESTED"
        ]
        effect_id = data.draw(st.sampled_from(candidates))
        self._commit(
            CancelBeforeDispatch(
                input_id=self._input_id("cancel-local"),
                effect_id=effect_id,
            )
        )
        self.effects[effect_id].state = "CANCELED_BEFORE_DISPATCH"

    @precondition(
        lambda self: any(
            effect.state == "REQUESTED" for effect in self.effects.values()
        )
    )
    @rule(data=st.data())
    def claim_for_dispatch(self, data) -> None:
        candidates = [
            effect_id
            for effect_id, effect in self.effects.items()
            if effect.state == "REQUESTED"
        ]
        effect_id = data.draw(st.sampled_from(candidates))
        self._next_claim += 1
        claim = ClaimOccurrenceId(f"claim-{self._next_claim}")
        self._commit(
            RecordDispatchClaim(
                input_id=self._input_id("claim"),
                effect_id=effect_id,
                claim_occurrence_id=claim,
            )
        )
        model = self.effects[effect_id]
        model.state = "DISPATCH_CLAIMED"
        model.claim = claim

    @precondition(
        lambda self: any(
            effect.state == "DISPATCH_CLAIMED" for effect in self.effects.values()
        )
    )
    @rule(data=st.data())
    def recover_stranded_claim_without_resend(self, data) -> None:
        candidates = [
            effect_id
            for effect_id, effect in self.effects.items()
            if effect.state == "DISPATCH_CLAIMED"
        ]
        effect_id = data.draw(st.sampled_from(candidates))
        self._commit(
            RecoverClaimedEffect(
                input_id=self._input_id("recover"),
                effect_id=effect_id,
            )
        )
        self.effects[effect_id].state = "OUTCOME_UNKNOWN"

    @precondition(
        lambda self: any(
            effect.state in {"DISPATCH_CLAIMED", "OUTCOME_UNKNOWN"}
            for effect in self.effects.values()
        )
    )
    @rule(data=st.data())
    def record_transport_outcome(self, data) -> None:
        candidates = [
            effect_id
            for effect_id, effect in self.effects.items()
            if effect.state in {"DISPATCH_CLAIMED", "OUTCOME_UNKNOWN"}
        ]
        effect_id = data.draw(st.sampled_from(candidates))
        prior = self.effects[effect_id].state
        allowed = (
            ("ACKNOWLEDGED", "REJECTED", "OUTCOME_UNKNOWN")
            if prior == "DISPATCH_CLAIMED"
            else ("ACKNOWLEDGED", "REJECTED", "NEEDS_REVIEW")
        )
        outcome = data.draw(st.sampled_from(allowed))
        self._commit(
            RecordTransportOutcome(
                input_id=self._input_id("transport"),
                effect_id=effect_id,
                state=getattr(BrokerEffectState, outcome),
            )
        )
        self.effects[effect_id].state = outcome

    @precondition(
        lambda self: any(
            effect.state
            in {
                "DISPATCH_CLAIMED",
                "ACKNOWLEDGED",
                "OUTCOME_UNKNOWN",
                "NEEDS_REVIEW",
            }
            for effect in self.effects.values()
        )
    )
    @rule(data=st.data())
    def discover_another_concrete_leg(self, data) -> None:
        candidates = [
            effect_id
            for effect_id, effect in self.effects.items()
            if effect.state
            in {
                "DISPATCH_CLAIMED",
                "ACKNOWLEDGED",
                "OUTCOME_UNKNOWN",
                "NEEDS_REVIEW",
            }
        ]
        effect_id = data.draw(st.sampled_from(candidates))
        leg_key = self._leg_key()
        model = self.effects[effect_id]
        expected = (
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED
            if model.acceptance == "CLOSED"
            else VenueRecoveryDisposition.APPLIED
        )
        self._commit(
            DiscoverVenueLeg(
                input_id=self._input_id("discover"),
                effect_id=effect_id,
                leg_key=leg_key,
                observation_id=self._observation_id("acceptance"),
            ),
            expected,
        )
        self.owners[leg_key] = effect_id
        self.active[leg_key] = _ModelAttempt()
        if model.acceptance == "CLOSED":
            model.acceptance = "INVALIDATED"

    @precondition(lambda self: bool(self.active))
    @rule(
        data=st.data(),
        pending=st.sampled_from(("CANCEL", "REPLACE")),
    )
    def record_pending_operation(self, data, pending: str) -> None:
        leg_key = data.draw(st.sampled_from(tuple(self.active)))
        status_before = self.active[leg_key].status
        self._commit(
            RecordPendingVenueOperation(
                input_id=self._input_id("pending"),
                leg_key=leg_key,
                operation=getattr(PendingVenueOperation, pending),
            )
        )
        self.active[leg_key].pending = pending
        assert self.active[leg_key].status == status_before

    @precondition(lambda self: bool(self.active))
    @rule(
        data=st.data(),
        observed=st.sampled_from(("WORKING", "PARTIALLY_FILLED")),
        increase=st.integers(min_value=0, max_value=3),
    )
    def observe_nonterminal_without_status_regression(
        self, data, observed: str, increase: int
    ) -> None:
        leg_key = data.draw(st.sampled_from(tuple(self.active)))
        model = self.active[leg_key]
        prior_pending = model.pending
        cumulative = model.cumulative + increase
        item = ObserveVenueStatus(
            input_id=self._input_id("status"),
            leg_key=leg_key,
            status=getattr(VenueAttemptState, observed),
            observation_id=self._observation_id("status"),
            cumulative_quantity=Quantity(
                model.cumulative
                if _NONTERMINAL_PRECEDENCE[observed]
                < _NONTERMINAL_PRECEDENCE[model.status]
                else cumulative
            ),
        )
        if _NONTERMINAL_PRECEDENCE[observed] < _NONTERMINAL_PRECEDENCE[model.status]:
            self._refused(item, VenueRecoveryDisposition.REFUSED)
            return
        self._commit(item)
        model.status = observed
        model.cumulative = cumulative
        assert model.pending == prior_pending

    @precondition(lambda self: bool(self.active))
    @rule(
        data=st.data(),
        terminal=st.sampled_from(_TERMINAL_STATUSES),
        increase=st.integers(min_value=0, max_value=3),
    )
    def compact_terminal_leg_to_one_closure_head(
        self, data, terminal: str, increase: int
    ) -> None:
        leg_key = data.draw(st.sampled_from(tuple(self.active)))
        cumulative = self.active[leg_key].cumulative + increase
        closure_id = self._closure_id()
        self._commit(
            ObserveVenueStatus(
                input_id=self._input_id("terminal"),
                leg_key=leg_key,
                status=getattr(VenueAttemptState, terminal),
                observation_id=self._observation_id("terminal"),
                cumulative_quantity=Quantity(cumulative),
                closure_id=closure_id,
                evidence_reference=EvidenceReference(
                    f"terminal-evidence-{closure_id.value}"
                ),
            )
        )
        del self.active[leg_key]
        self.closures[leg_key] = _ModelClosure(
            closure_id=closure_id,
            ordinal=1,
            predecessor=None,
            status=terminal,
            cumulative=cumulative,
        )

    @precondition(lambda self: bool(self.closures))
    @rule(data=st.data(), increase=st.integers(min_value=1, max_value=3))
    def append_immediate_terminal_closure_successor(self, data, increase: int) -> None:
        leg_key = data.draw(st.sampled_from(tuple(self.closures)))
        old = self.closures[leg_key]
        closure_id = self._closure_id()
        cumulative = old.cumulative + increase
        self._commit(
            ObserveVenueStatus(
                input_id=self._input_id("terminal-successor"),
                leg_key=leg_key,
                status=getattr(VenueAttemptState, old.status),
                observation_id=self._observation_id("terminal-successor"),
                cumulative_quantity=Quantity(cumulative),
                closure_id=closure_id,
                evidence_reference=EvidenceReference(
                    f"successor-evidence-{closure_id.value}"
                ),
            )
        )
        self.closures[leg_key] = _ModelClosure(
            closure_id=closure_id,
            ordinal=old.ordinal + 1,
            predecessor=old.closure_id,
            status=old.status,
            cumulative=cumulative,
        )

    @precondition(
        lambda self: any(
            effect.state == "CANCELED_BEFORE_DISPATCH" and effect.acceptance == "OPEN"
            for effect in self.effects.values()
        )
    )
    @rule(data=st.data())
    def close_never_dispatched_only_after_local_cancel(self, data) -> None:
        candidates = [
            effect_id
            for effect_id, effect in self.effects.items()
            if effect.state == "CANCELED_BEFORE_DISPATCH"
            and effect.acceptance == "OPEN"
        ]
        effect_id = data.draw(st.sampled_from(candidates))
        evidence = EvidenceReference(f"absence-proof-{effect_id.value}")
        self._commit(
            CloseAcceptanceSet(
                input_id=self._input_id("close-never-dispatched"),
                effect_id=effect_id,
                proof=self._acceptance_proof(
                    effect_id,
                    AcceptanceProofKind.NEVER_DISPATCHED,
                    evidence,
                ),
            )
        )
        model = self.effects[effect_id]
        model.acceptance = "CLOSED"
        model.proof_kind = "NEVER_DISPATCHED"
        model.proof_reference = evidence

    @precondition(
        lambda self: any(
            effect.claim is not None
            and effect.acceptance == "OPEN"
            and not self._has_active_leg(effect_id)
            for effect_id, effect in self.effects.items()
        )
    )
    @rule(data=st.data())
    def close_only_from_typed_external_completeness(self, data) -> None:
        candidates = [
            effect_id
            for effect_id, effect in self.effects.items()
            if effect.claim is not None
            and effect.acceptance == "OPEN"
            and not self._has_active_leg(effect_id)
        ]
        effect_id = data.draw(st.sampled_from(candidates))
        proof_kind = data.draw(
            st.sampled_from(("CONTRACT_COMPLETE_RESPONSE", "COVERED_RECONCILIATION"))
        )
        evidence = EvidenceReference(f"coverage-proof-{effect_id.value}-{proof_kind}")
        self._commit(
            CloseAcceptanceSet(
                input_id=self._input_id("close-covered"),
                effect_id=effect_id,
                proof=self._acceptance_proof(
                    effect_id,
                    getattr(AcceptanceProofKind, proof_kind),
                    evidence,
                ),
            )
        )
        model = self.effects[effect_id]
        model.acceptance = "CLOSED"
        model.proof_kind = proof_kind
        model.proof_reference = evidence

    @precondition(
        lambda self: any(
            effect.claim is not None and effect.acceptance == "OPEN"
            for effect in self.effects.values()
        )
    )
    @rule(data=st.data())
    def claimed_effect_can_never_manufacture_never_dispatched(self, data) -> None:
        candidates = [
            effect_id
            for effect_id, effect in self.effects.items()
            if effect.claim is not None and effect.acceptance == "OPEN"
        ]
        effect_id = data.draw(st.sampled_from(candidates))
        self._refused(
            CloseAcceptanceSet(
                input_id=self._input_id("false-never-dispatched"),
                effect_id=effect_id,
                proof=self._acceptance_proof(
                    effect_id,
                    AcceptanceProofKind.NEVER_DISPATCHED,
                    EvidenceReference("invalid-absence-proof"),
                ),
            ),
            VenueRecoveryDisposition.REFUSED,
        )

    @precondition(lambda self: len(self.effects) >= 2 and bool(self.owners))
    @rule(data=st.data())
    def immutable_owner_cannot_be_rebound(self, data) -> None:
        leg_key = data.draw(st.sampled_from(tuple(self.owners)))
        current_owner = self.owners[leg_key]
        other_effects = [
            effect_id for effect_id in self.effects if effect_id != current_owner
        ]
        if not other_effects:
            return
        other_effect = data.draw(st.sampled_from(other_effects))
        before_owner = self.book.owner(leg_key)
        self._refused(
            DiscoverVenueLeg(
                input_id=self._input_id("owner-rebind"),
                effect_id=other_effect,
                leg_key=leg_key,
                observation_id=self._observation_id("owner-rebind"),
            ),
            VenueRecoveryDisposition.CONFLICT,
        )
        assert self.book.owner(leg_key) == before_owner

    @precondition(lambda self: bool(self.applied_inputs))
    @rule(data=st.data())
    def exact_input_replay_is_a_total_noop(self, data) -> None:
        item = data.draw(st.sampled_from(tuple(self.applied_inputs)))
        before = (self.book, self.execution)
        replay = apply_venue_recovery_input(self.book, self.execution, item)
        assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
        assert replay.quantity_delta == 0
        assert (replay.book, replay.execution) == before

    @invariant()
    def public_read_model_matches_the_independent_oracle(self) -> None:
        assert len(self.book.effects) == len(self.effects)
        assert len(self.book.owners) == len(self.owners)
        assert len(self.book.active_attempts) == len(self.active)
        assert len(self.book.closure_heads) == len(self.closures)

        for effect_id, model in self.effects.items():
            effect = self.book.effect(effect_id)
            assert effect is not None
            assert _enum_value(effect.state) == model.state
            assert _enum_value(effect.acceptance_set_state) == model.acceptance
            assert effect.claim_occurrence_id == model.claim
            if model.proof_kind is None:
                assert effect.acceptance_proof is None
            else:
                assert effect.acceptance_proof is not None
                assert _enum_value(effect.acceptance_proof.kind) == model.proof_kind
                assert (
                    effect.acceptance_proof.evidence_reference == model.proof_reference
                )

        for leg_key, effect_id in self.owners.items():
            owner = self.book.owner(leg_key)
            assert owner is not None
            assert owner.effect_scope.effect_id == effect_id
            assert (leg_key in self.active) != (leg_key in self.closures)

        for leg_key, model in self.active.items():
            attempt = self.book.active_attempt(leg_key)
            assert attempt is not None
            assert _enum_value(attempt.status) == model.status
            if model.pending is None:
                assert attempt.pending_operation is None
            else:
                assert _enum_value(attempt.pending_operation) == model.pending
            assert attempt.cumulative_quantity == Quantity(model.cumulative)
            assert self.book.closure_head(leg_key) is None

        for leg_key, model in self.closures.items():
            assert self.book.active_attempt(leg_key) is None
            closure = self.book.closure_head(leg_key)
            assert closure is not None
            assert closure.closure_id == model.closure_id
            assert closure.ordinal == model.ordinal
            assert closure.predecessor_closure_id == model.predecessor
            assert _enum_value(closure.status) == model.status
            assert closure.cumulative_quantity == Quantity(model.cumulative)

    @invariant()
    def venue_history_is_quantity_neutral_and_checkpoint_bounded(self) -> None:
        assert self.execution == self.original_execution
        assert len(self.book.active_attempts) <= len(self.book.owners)
        assert len(self.book.closure_heads) <= len(self.book.owners)
        assert len(self.book.active_attempts) + len(self.book.closure_heads) == len(
            self.book.owners
        )


TestVenueRecoveryStateful = VenueRecoveryMachine.TestCase
TestVenueRecoveryStateful.settings = settings(
    max_examples=40,
    stateful_step_count=30,
    deadline=None,
    derandomize=True,
    database=None,
)


def test_restart_converts_a_stranded_claim_to_unknown_without_resending() -> None:
    """A recovered immutable claim is ambiguity, never permission to submit again."""

    execution = ExecutionSnapshot.flat(_POSITION_SCOPE)
    book = VenueRecoveryBook.empty(_VENUE_SCOPE)
    effect_id = EffectId("restart-effect")
    claim_id = ClaimOccurrenceId("restart-claim")
    inputs = (
        RequestedEffect(
            input_id=VenueInputId("restart-request"),
            effect_id=effect_id,
            request_occurrence_id=RequestOccurrenceId("restart-occurrence"),
            mandate_id=MandateId("restart-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("restart-client"),
            symbol_id=_SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(7),
            economic_scope=b"restart|AAPL|BUY|7",
        ),
        RecordDispatchClaim(
            input_id=VenueInputId("restart-claim-input"),
            effect_id=effect_id,
            claim_occurrence_id=claim_id,
        ),
    )
    for item in inputs:
        transition = apply_venue_recovery_input(book, execution, item)
        assert transition.disposition is VenueRecoveryDisposition.APPLIED
        assert transition.quantity_delta == 0
        book = transition.book
        execution = transition.execution

    checkpoint_after_restart = book
    recovered = RecoverClaimedEffect(
        input_id=VenueInputId("restart-recover"),
        effect_id=effect_id,
    )
    transition = apply_venue_recovery_input(
        checkpoint_after_restart,
        execution,
        recovered,
    )

    assert transition.disposition is VenueRecoveryDisposition.APPLIED
    assert transition.quantity_delta == 0
    assert transition.execution == execution
    assert transition.book.effect(effect_id).state is BrokerEffectState.OUTCOME_UNKNOWN
    assert transition.book.effect(effect_id).claim_occurrence_id == claim_id
    assert transition.book.owners == ()
    assert transition.book.active_attempts == ()

    replay = apply_venue_recovery_input(transition.book, execution, recovered)
    assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    assert replay.book == transition.book
    assert replay.execution == execution
