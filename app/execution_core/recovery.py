"""Pure operator and broker-evidence recovery commands for venue legs.

This module owns command shape and the narrowly authorized economic recovery
rules.  It performs no discovery or I/O: callers must supply exact identities,
quantities, evidence, and observations as immutable command data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

from .fills import (
    BrokerExecutionFact,
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionAuthority,
    ExecutionSide,
    FirstObservationClassification,
    HumanAttestedFillFact,
    PositionScope,
    RootHeadIndex,
    SeenFactIndex,
)
from .identity import (
    ActorId,
    ClaimOccurrenceId,
    ClosureId,
    EffectId,
    EvidenceReference,
    VenueInputId,
    VenueLegKey,
)
from .position import (
    ExecutionReconciliationCursor,
    ExecutionSnapshot,
    ExecutionTransition,
    PositionIntegrity,
    PositionState,
    TransitionDisposition,
    _apply_human_attested_fill_fact,
    _bind_components,
    _latch_execution_integrity,
    _record_broker_corroboration,
    _record_execution_reconciliation,
    _require_hydration_match,
    apply_broker_execution_fact,
)
from .values import Quantity
from .venue import (
    AcceptanceSetState,
    BrokerEffect,
    BrokerEffectState,
    VenueAttemptState,
    VenueClosureKind,
    VenueIdentityOwner,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueRecoveryTransition,
    _BookEvolver,
    _TransitionFactory,
    _book_close_attempt,
    _book_to_execution,
    _book_with_input,
    _book_with_input_and_execution,
    _input_commands_equal,
    _maybe_finalize_effect,
)


def _require_exact_type(name: str, value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be {expected.__name__}")


def _require_digest(value: object) -> None:
    if type(value) is not bytes:
        raise TypeError("evidence_digest must be bytes")
    if len(value) != 32:
        raise ValueError("evidence_digest must contain exactly 32 bytes")


def _require_reason(value: object) -> None:
    if type(value) is not str:
        raise TypeError("reason must be a string")
    if not value.strip():
        raise ValueError("reason must be nonblank")


@dataclass(frozen=True, slots=True)
class IngestHumanAttestedFill:
    """Request application of one capacity-bounded human root fill."""

    input_id: VenueInputId
    effect_id: EffectId
    fact: HumanAttestedFillFact

    def __post_init__(self) -> None:
        _require_exact_type("input_id", self.input_id, VenueInputId)
        _require_exact_type("effect_id", self.effect_id, EffectId)
        _require_exact_type("fact", self.fact, HumanAttestedFillFact)


@dataclass(frozen=True, slots=True)
class ReleaseVenueLeg:
    """Non-economic operator release of one exactly reconciled venue leg."""

    input_id: VenueInputId
    effect_id: EffectId
    leg_key: VenueLegKey
    claim_occurrence_id: ClaimOccurrenceId
    venue_cumulative_quantity: Quantity
    broker_terminal_state: VenueAttemptState
    actor: ActorId
    reason: str
    evidence_reference: EvidenceReference
    closure_id: ClosureId
    evidence_digest: bytes

    def __post_init__(self) -> None:
        _require_exact_type("input_id", self.input_id, VenueInputId)
        _require_exact_type("effect_id", self.effect_id, EffectId)
        _require_exact_type("leg_key", self.leg_key, VenueLegKey)
        _require_exact_type(
            "claim_occurrence_id", self.claim_occurrence_id, ClaimOccurrenceId
        )
        _require_exact_type(
            "venue_cumulative_quantity", self.venue_cumulative_quantity, Quantity
        )
        _require_exact_type(
            "broker_terminal_state", self.broker_terminal_state, VenueAttemptState
        )
        _require_exact_type("actor", self.actor, ActorId)
        _require_reason(self.reason)
        _require_exact_type(
            "evidence_reference", self.evidence_reference, EvidenceReference
        )
        _require_exact_type("closure_id", self.closure_id, ClosureId)
        _require_digest(self.evidence_digest)


@dataclass(frozen=True, slots=True)
class RecordBrokerFillEvidence:
    """Correlate one broker fill interval to an exact owned venue leg."""

    input_id: VenueInputId
    effect_id: EffectId
    leg_key: VenueLegKey
    prior_cumulative_quantity: Quantity
    resulting_cumulative_quantity: Quantity
    fact: BrokerFillFact
    evidence_digest: bytes
    closure_id: ClosureId | None = None
    evidence_reference: EvidenceReference | None = None

    def __post_init__(self) -> None:
        _require_exact_type("input_id", self.input_id, VenueInputId)
        _require_exact_type("effect_id", self.effect_id, EffectId)
        _require_exact_type("leg_key", self.leg_key, VenueLegKey)
        _require_exact_type(
            "prior_cumulative_quantity", self.prior_cumulative_quantity, Quantity
        )
        _require_exact_type(
            "resulting_cumulative_quantity",
            self.resulting_cumulative_quantity,
            Quantity,
        )
        _require_exact_type("fact", self.fact, BrokerFillFact)
        _require_digest(self.evidence_digest)
        if (self.closure_id is None) != (self.evidence_reference is None):
            raise ValueError(
                "closure_id and evidence_reference must be supplied together"
            )
        if self.closure_id is not None:
            _require_exact_type("closure_id", self.closure_id, ClosureId)
            _require_exact_type(
                "evidence_reference", self.evidence_reference, EvidenceReference
            )


@dataclass(frozen=True, slots=True)
class RecordBrokerRevisionEvidence:
    """Apply one broker correction or bust through the bound venue aggregate."""

    input_id: VenueInputId
    effect_id: EffectId
    leg_key: VenueLegKey
    prior_root_quantity: Quantity
    prior_venue_cumulative_quantity: Quantity
    resulting_venue_cumulative_quantity: Quantity
    fact: BrokerTradeCorrectFact | BrokerTradeBustFact
    evidence_digest: bytes
    closure_id: ClosureId | None = None
    evidence_reference: EvidenceReference | None = None

    def __post_init__(self) -> None:
        _require_exact_type("input_id", self.input_id, VenueInputId)
        _require_exact_type("effect_id", self.effect_id, EffectId)
        _require_exact_type("leg_key", self.leg_key, VenueLegKey)
        _require_exact_type("prior_root_quantity", self.prior_root_quantity, Quantity)
        _require_exact_type(
            "prior_venue_cumulative_quantity",
            self.prior_venue_cumulative_quantity,
            Quantity,
        )
        _require_exact_type(
            "resulting_venue_cumulative_quantity",
            self.resulting_venue_cumulative_quantity,
            Quantity,
        )
        if not isinstance(self.fact, (BrokerTradeCorrectFact, BrokerTradeBustFact)):
            raise TypeError(
                "fact must be BrokerTradeCorrectFact or BrokerTradeBustFact"
            )
        _require_digest(self.evidence_digest)
        if (self.closure_id is None) != (self.evidence_reference is None):
            raise ValueError(
                "closure_id and evidence_reference must be supplied together"
            )
        if self.closure_id is not None:
            _require_exact_type("closure_id", self.closure_id, ClosureId)
            _require_exact_type(
                "evidence_reference", self.evidence_reference, EvidenceReference
            )
        revised_root_quantity = (
            self.fact.revised_quantity.value
            if isinstance(self.fact, BrokerTradeCorrectFact)
            else 0
        )
        expected_resulting = (
            self.prior_venue_cumulative_quantity.value
            - self.prior_root_quantity.value
            + revised_root_quantity
        )
        if expected_resulting < 0 or (
            self.resulting_venue_cumulative_quantity.value != expected_resulting
        ):
            raise ValueError(
                "resulting venue cumulative must equal prior total minus prior root plus revised root"
            )


@dataclass(frozen=True, slots=True)
class HumanCoverage:
    """Committed human economics for one half-open cumulative interval."""

    effect_id: EffectId
    leg_key: VenueLegKey
    fact: HumanAttestedFillFact
    source_input_id: VenueInputId
    broker_corroborated: bool = False
    broker_fact: BrokerFillFact | None = None
    broker_evidence_digest: bytes | None = None
    broker_source_input_id: VenueInputId | None = None

    def __post_init__(self) -> None:
        _require_exact_type("effect_id", self.effect_id, EffectId)
        _require_exact_type("leg_key", self.leg_key, VenueLegKey)
        _require_exact_type("fact", self.fact, HumanAttestedFillFact)
        _require_exact_type("source_input_id", self.source_input_id, VenueInputId)
        if type(self.broker_corroborated) is not bool:
            raise TypeError("broker_corroborated must be bool")
        if self.broker_fact is not None:
            _require_exact_type("broker_fact", self.broker_fact, BrokerFillFact)
        if self.broker_evidence_digest is not None:
            _require_digest(self.broker_evidence_digest)
        if self.broker_source_input_id is not None:
            _require_exact_type(
                "broker_source_input_id",
                self.broker_source_input_id,
                VenueInputId,
            )
        evidence_presence = (
            self.broker_fact is not None,
            self.broker_evidence_digest is not None,
            self.broker_source_input_id is not None,
        )
        has_evidence = all(evidence_presence)
        if self.broker_corroborated != has_evidence or any(
            evidence_presence
        ) != has_evidence:
            raise ValueError("broker corroboration requires fact and evidence digest")


@dataclass(frozen=True, slots=True)
class _BrokerCoverage:
    """Internal attributed coverage for a disjoint broker interval."""

    effect_id: EffectId
    leg_key: VenueLegKey
    prior_cumulative_quantity: Quantity
    resulting_cumulative_quantity: Quantity
    fact: BrokerFillFact
    evidence_digest: bytes
    root_source_input_id: VenueInputId
    head_fact: BrokerExecutionFact
    head_evidence_digest: bytes
    head_source_input_id: VenueInputId
    mapping_exact: bool = True

    def __post_init__(self) -> None:
        _require_exact_type("effect_id", self.effect_id, EffectId)
        _require_exact_type("leg_key", self.leg_key, VenueLegKey)
        _require_exact_type(
            "prior_cumulative_quantity", self.prior_cumulative_quantity, Quantity
        )
        _require_exact_type(
            "resulting_cumulative_quantity",
            self.resulting_cumulative_quantity,
            Quantity,
        )
        _require_exact_type("fact", self.fact, BrokerFillFact)
        _require_digest(self.evidence_digest)
        _require_exact_type(
            "root_source_input_id", self.root_source_input_id, VenueInputId
        )
        if not isinstance(
            self.head_fact,
            (BrokerFillFact, BrokerTradeCorrectFact, BrokerTradeBustFact),
        ):
            raise TypeError("head_fact must be a canonical broker execution fact")
        _require_digest(self.head_evidence_digest)
        _require_exact_type(
            "head_source_input_id", self.head_source_input_id, VenueInputId
        )
        if type(self.mapping_exact) is not bool:
            raise TypeError("mapping_exact must be bool")
        if self.head_fact.root_key != self.fact.root_key:
            raise ValueError("broker coverage head must preserve its immutable root")


@dataclass(frozen=True, slots=True)
class ReconciliationRecord:
    """Append-only evidence that was unsafe to turn into an economic delta."""

    input_id: VenueInputId
    effect_id: EffectId
    leg_key: VenueLegKey
    prior_cumulative_quantity: Quantity
    resulting_cumulative_quantity: Quantity
    fact: BrokerFillFact
    evidence_digest: bytes
    reason: str

    def __post_init__(self) -> None:
        _require_exact_type("input_id", self.input_id, VenueInputId)
        _require_exact_type("effect_id", self.effect_id, EffectId)
        _require_exact_type("leg_key", self.leg_key, VenueLegKey)
        _require_exact_type(
            "prior_cumulative_quantity", self.prior_cumulative_quantity, Quantity
        )
        _require_exact_type(
            "resulting_cumulative_quantity",
            self.resulting_cumulative_quantity,
            Quantity,
        )
        _require_exact_type("fact", self.fact, BrokerFillFact)
        _require_digest(self.evidence_digest)
        _require_reason(self.reason)


@dataclass(frozen=True, slots=True)
class RevisionReconciliationRecord:
    """Append-only evidence for an unresolved broker revision mapping."""

    input_id: VenueInputId
    effect_id: EffectId
    leg_key: VenueLegKey
    prior_root_quantity: Quantity
    prior_venue_cumulative_quantity: Quantity
    resulting_venue_cumulative_quantity: Quantity
    fact: BrokerTradeCorrectFact | BrokerTradeBustFact
    evidence_digest: bytes
    canonical_applied: bool
    reason: str

    def __post_init__(self) -> None:
        _require_exact_type("input_id", self.input_id, VenueInputId)
        _require_exact_type("effect_id", self.effect_id, EffectId)
        _require_exact_type("leg_key", self.leg_key, VenueLegKey)
        _require_exact_type("prior_root_quantity", self.prior_root_quantity, Quantity)
        _require_exact_type(
            "prior_venue_cumulative_quantity",
            self.prior_venue_cumulative_quantity,
            Quantity,
        )
        _require_exact_type(
            "resulting_venue_cumulative_quantity",
            self.resulting_venue_cumulative_quantity,
            Quantity,
        )
        if not isinstance(self.fact, (BrokerTradeCorrectFact, BrokerTradeBustFact)):
            raise TypeError(
                "fact must be BrokerTradeCorrectFact or BrokerTradeBustFact"
            )
        _require_digest(self.evidence_digest)
        if type(self.canonical_applied) is not bool:
            raise TypeError("canonical_applied must be bool")
        _require_reason(self.reason)


def _snapshot_from_transition(transition: ExecutionTransition) -> ExecutionSnapshot:
    return ExecutionSnapshot(
        position=transition.position,
        integrity=transition.integrity,
        root_heads=transition.root_heads,
        seen_facts=transition.seen_facts,
    )


def _same_leg_scope(book: VenueRecoveryBook, leg_key: VenueLegKey) -> bool:
    return (
        leg_key.broker == book.scope.broker
        and leg_key.environment == book.scope.environment
        and leg_key.account == book.scope.account
    )


def _bound_effect_and_owner(
    book: VenueRecoveryBook,
    effect_id: EffectId,
    leg_key: VenueLegKey,
) -> tuple[BrokerEffect | None, VenueIdentityOwner | None]:
    effect = book._current_effect(effect_id)
    owner = book.owner(leg_key)
    if (
        effect is None
        or owner is None
        or owner.effect_id != effect_id
        or not _same_leg_scope(book, leg_key)
    ):
        return None, None
    return effect, owner


def _coverage_frontier(book: VenueRecoveryBook, leg_key: VenueLegKey) -> int:
    return book._coverage_current(leg_key).frontier


def _leg_canonical_total(book: VenueRecoveryBook, leg_key: VenueLegKey) -> int:
    return book._coverage_current(leg_key).canonical_total


def _effect_canonical_total(
    book: VenueRecoveryBook,
    effect_id: EffectId,
) -> int:
    return book._effect_canonical_total(effect_id)


def _leg_economic_high_water(
    book: VenueRecoveryBook,
    leg_key: VenueLegKey,
) -> int:
    return book._economic_high_water(leg_key)


def _fact_matches_owner(
    effect: BrokerEffect,
    owner: VenueIdentityOwner,
    fact: HumanAttestedFillFact,
) -> bool:
    scope = fact.scope
    effect_scope = owner.effect_scope
    return (
        fact.leg_key == owner.leg_key
        and scope.broker == effect_scope.broker
        and scope.environment == effect_scope.environment
        and scope.account == effect_scope.account
        and scope.order_id == owner.leg_key.order_id
        and scope.symbol_id == effect_scope.symbol_id
        and scope.side is effect_scope.side
        and fact.request_occurrence_id == effect_scope.request_occurrence_id
        and fact.claim_occurrence_id == effect.claim_occurrence_id
    )


def _broker_fact_matches_owner(
    owner: VenueIdentityOwner,
    fact: BrokerExecutionFact,
) -> bool:
    scope = fact.scope
    effect_scope = owner.effect_scope
    return (
        scope.broker == effect_scope.broker
        and scope.environment == effect_scope.environment
        and scope.account == effect_scope.account
        and scope.order_id == owner.leg_key.order_id
        and scope.symbol_id == effect_scope.symbol_id
        and scope.side is effect_scope.side
    )


def _matching_human_coverage(
    book: VenueRecoveryBook,
    effect_id: EffectId,
    fact: HumanAttestedFillFact,
) -> HumanCoverage | None:
    coverage = book._human_coverage_for_root(fact.root_key)
    if coverage is None or coverage.effect_id != effect_id or coverage.fact != fact:
        return None
    return coverage


def _has_unattributed_broker_root(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    fact: HumanAttestedFillFact,
) -> bool:
    """Detect same-order broker economics the venue book cannot attribute."""

    return execution.root_heads.broker_root_count(
        fact.scope
    ) > book._attributed_broker_root_count(fact.scope)


def _apply_human_fill(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: IngestHumanAttestedFill,
    evolve: _BookEvolver,
    _transition: _TransitionFactory,
) -> VenueRecoveryTransition:
    effect, owner = _bound_effect_and_owner(book, item.effect_id, item.fact.leg_key)
    fact = item.fact
    first_observation = execution.seen_facts.get(fact.key)
    if first_observation is not None:
        replayed = _apply_human_attested_fill_fact(
            execution.position,
            execution.integrity,
            execution.root_heads,
            execution.seen_facts,
            fact,
        )
        replayed_execution = _snapshot_from_transition(replayed)
        if replayed.disposition is TransitionDisposition.EXACT_REPLAY:
            if _matching_human_coverage(book, item.effect_id, fact) is None:
                return _transition(
                    book,
                    execution,
                    VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
                )
            return _transition(
                _book_with_input(evolve, book, execution, item),
                execution,
                VenueRecoveryDisposition.APPLIED,
            )
        if replayed.disposition is TransitionDisposition.FACT_CONFLICT:
            return _transition(
                _book_to_execution(
                    evolve,
                    book,
                    execution,
                    replayed_execution,
                ),
                replayed_execution,
                VenueRecoveryDisposition.CONFLICT,
            )
        return _transition(
            _book_to_execution(evolve, book, execution, replayed_execution),
            replayed_execution,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        )

    attempt = book.active_attempt(fact.leg_key)
    if (
        effect is None
        or owner is None
        or attempt is None
        or effect.state is not BrokerEffectState.NEEDS_REVIEW
        or attempt.status is not VenueAttemptState.NEEDS_REVIEW
        or not _fact_matches_owner(effect, owner, fact)
        or fact.key.broker != book.scope.broker
        or fact.key.environment != book.scope.environment
        or fact.key.account != book.scope.account
        or fact.quantity.value <= 0
        or fact.resulting_cumulative_quantity.value
        - fact.prior_cumulative_quantity.value
        != fact.quantity.value
        or fact.prior_cumulative_quantity.value
        != _coverage_frontier(book, fact.leg_key)
        or fact.resulting_cumulative_quantity.value > effect.scope.quantity.value
        or (
            _effect_canonical_total(book, item.effect_id) + fact.quantity.value
            > effect.scope.quantity.value
        )
        or _has_unattributed_broker_root(book, execution, fact)
        or (
            fact.scope.side is ExecutionSide.SELL
            and execution.position.raw_quantity - fact.quantity.value < 0
        )
    ):
        return _transition(book, execution, VenueRecoveryDisposition.REFUSED)

    applied = _apply_human_attested_fill_fact(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
        fact,
    )
    if applied.disposition is not TransitionDisposition.APPLIED:
        return _transition(book, execution, VenueRecoveryDisposition.REFUSED)
    next_execution = _snapshot_from_transition(applied)
    updated_attempt = replace(
        attempt,
        cumulative_quantity=Quantity(
            max(
                attempt.cumulative_quantity.value,
                fact.resulting_cumulative_quantity.value,
            )
        ),
    )
    coverage = HumanCoverage(
        effect_id=item.effect_id,
        leg_key=fact.leg_key,
        fact=fact,
        source_input_id=item.input_id,
    )
    next_book = _book_with_input_and_execution(
        evolve,
        book,
        item,
        execution,
        next_execution,
        canonical_economic_input=True,
        _attempt_replace=updated_attempt,
        _human_coverage_append=coverage,
    )
    return _transition(
        next_book,
        next_execution,
        VenueRecoveryDisposition.APPLIED,
        quantity_delta=applied.quantity_delta,
    )


def _apply_release(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: ReleaseVenueLeg,
    evolve: _BookEvolver,
    _transition: _TransitionFactory,
) -> VenueRecoveryTransition:
    effect, owner = _bound_effect_and_owner(book, item.effect_id, item.leg_key)
    attempt = book.active_attempt(item.leg_key)
    terminal = item.broker_terminal_state in {
        VenueAttemptState.FILLED,
        VenueAttemptState.CANCELED,
        VenueAttemptState.REJECTED,
        VenueAttemptState.EXPIRED,
        VenueAttemptState.REPLACED,
    }
    coverage_frontier = _coverage_frontier(book, item.leg_key)
    if (
        effect is None
        or owner is None
        or attempt is None
        or effect.state is not BrokerEffectState.NEEDS_REVIEW
        or effect.acceptance_set_state is AcceptanceSetState.INVALIDATED
        or attempt.status is not VenueAttemptState.NEEDS_REVIEW
        or effect.claim_occurrence_id != item.claim_occurrence_id
        or not terminal
        or item.venue_cumulative_quantity.value != coverage_frontier
        or attempt.cumulative_quantity.value
        != _leg_economic_high_water(book, item.leg_key)
        or (
            item.broker_terminal_state is VenueAttemptState.FILLED
            and coverage_frontier != effect.scope.quantity.value
        )
    ):
        return _transition(book, execution, VenueRecoveryDisposition.REFUSED)
    if (
        execution.position.scope != effect.scope.position_scope
        or not book._execution_pair_matches_fast(execution)
    ):
        return _transition(
            book,
            execution,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        )
    unresolved_execution = (
        PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    if (
        execution.integrity & unresolved_execution
        or book._has_unresolved_reconciliation(item.leg_key)
        or book._has_unresolved_execution_reconciliation(effect.scope.position_scope)
    ):
        return _transition(
            book,
            execution,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        )

    next_book = _maybe_finalize_effect(
        evolve,
        _book_close_attempt(
            evolve,
            book,
            prior_execution=execution,
            leg_key=item.leg_key,
            closure_id=item.closure_id,
            status=VenueAttemptState.OPERATOR_RECONCILED,
            cumulative_quantity=item.venue_cumulative_quantity,
            observed_cumulative_quantity=attempt.cumulative_quantity,
            evidence_reference=item.evidence_reference,
            kind=VenueClosureKind.OPERATOR_RECONCILED,
            broker_terminal_state=item.broker_terminal_state,
            source_input=item,
            actor=item.actor,
            reason=item.reason,
            evidence_digest=item.evidence_digest,
        ),
        item.effect_id,
        execution,
    )
    return _transition(next_book, execution, VenueRecoveryDisposition.APPLIED)


def _reconciliation(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RecordBrokerFillEvidence,
    reason: str,
    evolve: _BookEvolver,
    _transition: _TransitionFactory,
) -> VenueRecoveryTransition:
    recorded = _record_execution_reconciliation(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
        item.fact,
    )
    next_execution = _snapshot_from_transition(recorded)
    record = ReconciliationRecord(
        input_id=item.input_id,
        effect_id=item.effect_id,
        leg_key=item.leg_key,
        prior_cumulative_quantity=item.prior_cumulative_quantity,
        resulting_cumulative_quantity=item.resulting_cumulative_quantity,
        fact=item.fact,
        evidence_digest=item.evidence_digest,
        reason=reason,
    )
    next_book = _book_with_input_and_execution(
        evolve,
        book,
        item,
        execution,
        next_execution,
        _reconciliation_append=record,
    )
    return _transition(
        next_book,
        next_execution,
        VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
    )


def _apply_broker_evidence(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RecordBrokerFillEvidence,
    evolve: _BookEvolver,
    _transition: _TransitionFactory,
) -> VenueRecoveryTransition:
    effect, owner = _bound_effect_and_owner(book, item.effect_id, item.leg_key)
    prior = item.prior_cumulative_quantity.value
    resulting = item.resulting_cumulative_quantity.value
    if (
        effect is None
        or owner is None
        or not _broker_fact_matches_owner(owner, item.fact)
        or prior < 0
        or resulting <= prior
    ):
        return _transition(book, execution, VenueRecoveryDisposition.REFUSED)

    prior_command = book._fact_input_record(item.fact.key)
    if prior_command is not None:
        same_payload = (
            prior_command
            if isinstance(prior_command.item, RecordBrokerFillEvidence)
            and _input_commands_equal(
                prior_command.item,
                item,
                include_input_id=False,
            )
            else None
        )
        if same_payload is None:
            return _reconciliation(
                book,
                execution,
                item,
                "seen broker fact identity carries changed attribution or evidence",
                evolve,
                _transition,
            )
        if book._reconciliation_for_input(same_payload.input_id) is not None:
            return _transition(
                _book_with_input(evolve, book, execution, item),
                execution,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            )
        return _transition(
            _book_with_input(evolve, book, execution, item),
            execution,
            VenueRecoveryDisposition.APPLIED,
        )

    width_matches = resulting - prior == item.fact.quantity.value
    exact = book._human_coverage_for_interval(
        item.leg_key,
        prior,
        resulting,
    )
    overlaps = exact is None and prior < _coverage_frontier(book, item.leg_key)
    mapped = book._human_coverage_for_broker_fact(item.fact.key)
    mapped_to_another_interval = mapped is not None and mapped is not exact

    if exact is not None and width_matches and item.fact.price == exact.fact.price:
        if mapped_to_another_interval:
            return _reconciliation(
                book,
                execution,
                item,
                "broker fact identity is already mapped to another human interval",
                evolve,
                _transition,
            )
        if exact.broker_corroborated:
            if not (
                exact.broker_fact == item.fact
                and exact.broker_evidence_digest == item.evidence_digest
            ):
                return _reconciliation(
                    book,
                    execution,
                    item,
                    "human interval already has different broker corroboration",
                    evolve,
                    _transition,
                )
        reserved = _record_broker_corroboration(
            execution.position,
            execution.integrity,
            execution.root_heads,
            execution.seen_facts,
            item.fact,
        )
        if reserved.disposition not in {
            TransitionDisposition.APPLIED,
            TransitionDisposition.EXACT_REPLAY,
        }:
            return _reconciliation(
                book,
                execution,
                item,
                "broker corroboration identity conflicts with canonical execution facts",
                evolve,
                _transition,
            )
        next_execution = _snapshot_from_transition(reserved)
        coverage_replacement: tuple[HumanCoverage, HumanCoverage] | None = None
        if not exact.broker_corroborated:
            corroborated = replace(
                exact,
                broker_corroborated=True,
                broker_fact=item.fact,
                broker_evidence_digest=item.evidence_digest,
                broker_source_input_id=item.input_id,
            )
            coverage_replacement = (exact, corroborated)
        next_book = _book_with_input_and_execution(
            evolve,
            book,
            item,
            execution,
            next_execution,
            _human_coverage_replace=coverage_replacement,
        )
        return _transition(
            next_book,
            next_execution,
            VenueRecoveryDisposition.APPLIED,
        )

    if exact is not None or overlaps or not width_matches:
        return _reconciliation(
            book,
            execution,
            item,
            "broker interval overlaps or disagrees with committed human economics",
            evolve,
            _transition,
        )

    attempt = book.active_attempt(item.leg_key)
    closure_head = book.closure_head(item.leg_key)
    if (
        (attempt is None) == (closure_head is None)
        or prior != _coverage_frontier(book, item.leg_key)
        or (attempt is not None and item.closure_id is not None)
        or (closure_head is not None and item.closure_id is None)
    ):
        return _reconciliation(
            book,
            execution,
            item,
            "broker interval cannot be mapped to an active next uncovered capacity",
            evolve,
            _transition,
        )

    applied = apply_broker_execution_fact(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
        item.fact,
    )
    if applied.disposition is not TransitionDisposition.APPLIED:
        return _reconciliation(
            book,
            execution,
            item,
            "broker reducer did not admit the attributed disjoint fill",
            evolve,
            _transition,
        )
    next_execution = _snapshot_from_transition(applied)
    if (
        resulting > effect.scope.quantity.value
        or _effect_canonical_total(book, item.effect_id) + (resulting - prior)
        > effect.scope.quantity.value
    ):
        next_execution = _latch_execution_integrity(
            next_execution,
            PositionIntegrity.OVERFILL_QUARANTINE,
        )
    coverage = _BrokerCoverage(
        effect_id=item.effect_id,
        leg_key=item.leg_key,
        prior_cumulative_quantity=item.prior_cumulative_quantity,
        resulting_cumulative_quantity=item.resulting_cumulative_quantity,
        fact=item.fact,
        evidence_digest=item.evidence_digest,
        root_source_input_id=item.input_id,
        head_fact=item.fact,
        head_evidence_digest=item.evidence_digest,
        head_source_input_id=item.input_id,
    )
    if attempt is not None:
        updated_attempt = replace(
            attempt,
            cumulative_quantity=Quantity(
                max(attempt.cumulative_quantity.value, resulting)
            ),
        )
        next_book = _book_with_input_and_execution(
            evolve,
            book,
            item,
            execution,
            next_execution,
            canonical_economic_input=True,
            _attempt_replace=updated_attempt,
            _broker_coverage_append=coverage,
        )
    else:
        assert closure_head is not None
        assert item.closure_id is not None
        assert item.evidence_reference is not None
        next_book = _book_close_attempt(
            evolve,
            book,
            prior_execution=execution,
            leg_key=item.leg_key,
            closure_id=item.closure_id,
            status=closure_head.status,
            cumulative_quantity=item.resulting_cumulative_quantity,
            observed_cumulative_quantity=(closure_head.observed_cumulative_quantity),
            evidence_reference=item.evidence_reference,
            kind=VenueClosureKind.BROKER_ECONOMIC,
            source_event_id=item.fact.key.source_event_id,
            broker_terminal_state=closure_head.broker_terminal_state,
            source_input=item,
            resulting_execution=next_execution,
            canonical_economic_input=True,
            evidence_digest=item.evidence_digest,
            evolution_changes={"_broker_coverage_append": coverage},
        )
    return _transition(
        next_book,
        next_execution,
        VenueRecoveryDisposition.APPLIED,
        quantity_delta=applied.quantity_delta,
    )


def _revision_root_quantity(
    fact: BrokerExecutionFact,
) -> int:
    if isinstance(fact, BrokerFillFact):
        return fact.quantity.value
    if isinstance(fact, BrokerTradeCorrectFact):
        return fact.revised_quantity.value
    return 0


def _revision_venue_cumulative(
    book: VenueRecoveryBook,
    leg_key: VenueLegKey,
) -> int:
    return _leg_canonical_total(book, leg_key)


def _is_tail_broker_coverage(
    book: VenueRecoveryBook,
    target: _BrokerCoverage,
) -> bool:
    return book._coverage_current(target.leg_key).tail_root_key == target.fact.root_key


def _revision_reconciliation(
    book: VenueRecoveryBook,
    prior_execution: ExecutionSnapshot,
    resulting_execution: ExecutionSnapshot,
    item: RecordBrokerRevisionEvidence,
    evolve: _BookEvolver,
    _transition: _TransitionFactory,
    *,
    reason: str,
    canonical_applied: bool,
    quantity_delta: int,
) -> VenueRecoveryTransition:
    record = RevisionReconciliationRecord(
        input_id=item.input_id,
        effect_id=item.effect_id,
        leg_key=item.leg_key,
        prior_root_quantity=item.prior_root_quantity,
        prior_venue_cumulative_quantity=item.prior_venue_cumulative_quantity,
        resulting_venue_cumulative_quantity=(item.resulting_venue_cumulative_quantity),
        fact=item.fact,
        evidence_digest=item.evidence_digest,
        canonical_applied=canonical_applied,
        reason=reason,
    )
    changes: dict[str, object] = {
        "_reconciliation_append": record,
        "_demote_scope": item.fact.scope.position_scope,
    }
    next_book = _book_with_input_and_execution(
        evolve,
        book,
        item,
        prior_execution,
        resulting_execution,
        canonical_economic_input=canonical_applied,
        **changes,
    )
    return _transition(
        next_book,
        resulting_execution,
        VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        quantity_delta=quantity_delta,
    )


def _apply_broker_revision_evidence(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RecordBrokerRevisionEvidence,
    evolve: _BookEvolver,
    _transition: _TransitionFactory,
) -> VenueRecoveryTransition:
    effect, owner = _bound_effect_and_owner(book, item.effect_id, item.leg_key)
    if (
        effect is None
        or owner is None
        or not _broker_fact_matches_owner(owner, item.fact)
    ):
        return _transition(book, execution, VenueRecoveryDisposition.REFUSED)

    prior_command = book._fact_input_record(item.fact.key)
    same_payload = (
        prior_command
        if prior_command is not None
        and isinstance(prior_command.item, RecordBrokerRevisionEvidence)
        and _input_commands_equal(
            prior_command.item,
            item,
            include_input_id=False,
        )
        else None
    )
    if prior_command is not None:
        replayed = apply_broker_execution_fact(
            execution.position,
            execution.integrity,
            execution.root_heads,
            execution.seen_facts,
            item.fact,
        )
        replayed_execution = _snapshot_from_transition(replayed)
        if (
            replayed.disposition is TransitionDisposition.EXACT_REPLAY
            and same_payload is not None
        ):
            unresolved = (
                book._reconciliation_for_input(same_payload.input_id) is not None
            )
            return _transition(
                _book_with_input(evolve, book, execution, item),
                execution,
                (
                    VenueRecoveryDisposition.RECONCILIATION_REQUIRED
                    if unresolved
                    else VenueRecoveryDisposition.APPLIED
                ),
            )
        if replayed.disposition is TransitionDisposition.EXACT_REPLAY:
            replayed_execution = _latch_execution_integrity(
                replayed_execution,
                PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED,
            )
        return _revision_reconciliation(
            book,
            execution,
            replayed_execution,
            item,
            evolve,
            _transition,
            reason="seen broker revision identity carries changed attribution or evidence",
            canonical_applied=False,
            quantity_delta=0,
        )

    attempt = book.active_attempt(item.leg_key)
    closure_head = book.closure_head(item.leg_key)
    if (
        (attempt is None) == (closure_head is None)
        or (attempt is not None and item.closure_id is not None)
        or (closure_head is not None and item.closure_id is None)
    ):
        return _transition(book, execution, VenueRecoveryDisposition.REFUSED)

    applied = apply_broker_execution_fact(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
        item.fact,
    )
    next_execution = _snapshot_from_transition(applied)
    if applied.disposition is not TransitionDisposition.APPLIED:
        return _revision_reconciliation(
            book,
            execution,
            next_execution,
            item,
            evolve,
            _transition,
            reason="broker revision lineage or authority is not canonically applicable",
            canonical_applied=False,
            quantity_delta=0,
        )

    prospective_effect_total = (
        _effect_canonical_total(book, item.effect_id)
        - item.prior_venue_cumulative_quantity.value
        + item.resulting_venue_cumulative_quantity.value
    )
    if (
        item.resulting_venue_cumulative_quantity.value > effect.scope.quantity.value
        or prospective_effect_total > effect.scope.quantity.value
    ):
        next_execution = _latch_execution_integrity(
            next_execution,
            PositionIntegrity.OVERFILL_QUARANTINE,
        )

    prior_head = execution.root_heads.get(item.fact.root_key)
    coverage = book._broker_coverage_for_root(item.fact.root_key)
    if coverage is not None and (
        coverage.effect_id != item.effect_id or coverage.leg_key != item.leg_key
    ):
        coverage = None
    current_total = _revision_venue_cumulative(book, item.leg_key)
    exact_mapping = (
        prior_head is not None
        and prior_head.authority is ExecutionAuthority.BROKER_AUTHORITATIVE
        and prior_head.current_source_event_id == item.fact.predecessor_source_event_id
        and prior_head.quantity == item.prior_root_quantity
        and item.prior_venue_cumulative_quantity.value == current_total
        and coverage is not None
        and coverage.mapping_exact
        and _is_tail_broker_coverage(book, coverage)
        and book._coverage_current(item.leg_key).inexact_broker_count == 0
        and not book._has_canonical_revision(item.leg_key)
    )

    coverage_change = {}
    if coverage is not None:
        updated_coverage = replace(
            coverage,
            resulting_cumulative_quantity=(
                item.resulting_venue_cumulative_quantity
                if exact_mapping
                else coverage.resulting_cumulative_quantity
            ),
            head_fact=item.fact,
            head_evidence_digest=item.evidence_digest,
            head_source_input_id=item.input_id,
            mapping_exact=exact_mapping,
        )
        coverage_change["_broker_coverage_replace"] = (
            coverage,
            updated_coverage,
        )

    reconciliation = None
    if not exact_mapping:
        reconciliation = RevisionReconciliationRecord(
            input_id=item.input_id,
            effect_id=item.effect_id,
            leg_key=item.leg_key,
            prior_root_quantity=item.prior_root_quantity,
            prior_venue_cumulative_quantity=item.prior_venue_cumulative_quantity,
            resulting_venue_cumulative_quantity=(
                item.resulting_venue_cumulative_quantity
            ),
            fact=item.fact,
            evidence_digest=item.evidence_digest,
            canonical_applied=True,
            reason="broker revision applied but venue interval mapping is unresolved",
        )
    demote_scope = None if reconciliation is None else item.fact.scope.position_scope

    if attempt is not None:
        updated_attempt = replace(
            attempt,
            cumulative_quantity=Quantity(
                max(
                    attempt.cumulative_quantity.value,
                    item.resulting_venue_cumulative_quantity.value,
                )
            ),
        )
        next_book = _book_with_input_and_execution(
            evolve,
            book,
            item,
            execution,
            next_execution,
            canonical_economic_input=True,
            _attempt_replace=updated_attempt,
            **coverage_change,
            _reconciliation_append=reconciliation,
            _demote_scope=demote_scope,
        )
    else:
        assert closure_head is not None
        assert item.closure_id is not None
        assert item.evidence_reference is not None
        next_book = _book_close_attempt(
            evolve,
            book,
            prior_execution=execution,
            leg_key=item.leg_key,
            closure_id=item.closure_id,
            status=closure_head.status,
            cumulative_quantity=item.resulting_venue_cumulative_quantity,
            observed_cumulative_quantity=(closure_head.observed_cumulative_quantity),
            evidence_reference=item.evidence_reference,
            kind=VenueClosureKind.BROKER_ECONOMIC,
            source_event_id=item.fact.key.source_event_id,
            broker_terminal_state=closure_head.broker_terminal_state,
            source_input=item,
            resulting_execution=next_execution,
            canonical_economic_input=True,
            evidence_digest=item.evidence_digest,
            evolution_changes={
                **coverage_change,
                "_reconciliation_append": reconciliation,
                "_demote_scope": demote_scope,
            },
        )

    return _transition(
        next_book,
        next_execution,
        (
            VenueRecoveryDisposition.APPLIED
            if exact_mapping
            else VenueRecoveryDisposition.RECONCILIATION_REQUIRED
        ),
        quantity_delta=applied.quantity_delta,
    )


def _replay_venue_hydration_snapshot(
    scope: PositionScope,
    seen_facts: SeenFactIndex,
    *,
    authorized_human_facts: tuple[HumanAttestedFillFact, ...],
    authorized_corroborations: tuple[BrokerFillFact, ...],
    limit: int | None = None,
) -> ExecutionSnapshot:
    """Re-derive one symbol while authenticating recovery-only observations."""

    if limit is None:
        limit = seen_facts.count
    if type(limit) is not int or limit < 0 or limit > seen_facts.count:
        raise ValueError("limit must be within the retained registry")
    account_seen = SeenFactIndex.empty(scope)
    symbol_snapshots: dict[PositionScope, ExecutionSnapshot] = {}
    for index in range(limit):
        observation = seen_facts.observation_at(index)
        observation_scope = observation.position_scope
        if observation_scope is None:
            raise ValueError("seen fact has no evaluation position scope")
        replayed = symbol_snapshots.get(observation_scope)
        if replayed is None:
            replayed = ExecutionSnapshot.flat(observation_scope)
        replayed = _bind_components(
            replayed.position,
            replayed.integrity,
            replayed.root_heads,
            account_seen,
        )
        fact = observation.fact
        if isinstance(fact, HumanAttestedFillFact):
            if fact not in authorized_human_facts:
                raise ValueError("human execution fact lacks venue-book provenance")
            transition = _apply_human_attested_fill_fact(
                replayed.position,
                replayed.integrity,
                replayed.root_heads,
                replayed.seen_facts,
                fact,
            )
        elif isinstance(fact, BrokerFillFact) and (
            observation.classification
            is FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC
        ):
            if fact not in authorized_corroborations:
                raise ValueError("broker corroboration lacks venue-book provenance")
            transition = _record_broker_corroboration(
                replayed.position,
                replayed.integrity,
                replayed.root_heads,
                replayed.seen_facts,
                fact,
            )
        elif isinstance(
            fact,
            (BrokerFillFact, BrokerTradeCorrectFact, BrokerTradeBustFact),
        ):
            transition = apply_broker_execution_fact(
                replayed.position,
                replayed.integrity,
                replayed.root_heads,
                replayed.seen_facts,
                fact,
            )
        else:
            raise ValueError("seen fact is not an admitted execution fact")

        expected_disposition = (
            TransitionDisposition.RECONCILIATION_REQUIRED
            if observation.classification
            is FirstObservationClassification.RECONCILIATION_REQUIRED
            else TransitionDisposition.APPLIED
        )
        if (
            transition.disposition is not expected_disposition
            or transition.original_classification is not observation.classification
        ):
            raise ValueError("seen-fact classification is not reproducible")
        account_seen = transition.seen_facts
        symbol_snapshots[observation_scope] = ExecutionSnapshot(
            position=transition.position,
            integrity=transition.integrity,
            root_heads=transition.root_heads,
            seen_facts=transition.seen_facts,
        )

    replayed = symbol_snapshots.get(scope)
    if replayed is None:
        replayed = ExecutionSnapshot.flat(scope)
    replayed = _bind_components(
        replayed.position,
        replayed.integrity,
        replayed.root_heads,
        account_seen,
    )
    if not seen_facts.has_prefix(limit, replayed.seen_facts.commitment):
        raise ValueError("seen-fact replay did not close exactly")
    return replayed


def bind_venue_execution_snapshot(
    book: VenueRecoveryBook,
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
    *,
    expected_reconciliation_cursor: ExecutionReconciliationCursor,
) -> ExecutionSnapshot:
    """Bind restart state against independently retained reconciliation authority."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be the exact opaque VenueRecoveryBook type")
    _require_exact_type("position", position, PositionState)
    _require_exact_type("integrity", integrity, PositionIntegrity)
    _require_exact_type("root_heads", root_heads, RootHeadIndex)
    _require_exact_type("seen_facts", seen_facts, SeenFactIndex)
    _require_exact_type("position.scope", position.scope, PositionScope)
    _require_exact_type(
        "root_heads.position_scope",
        root_heads.position_scope,
        PositionScope,
    )
    _require_exact_type(
        "expected_reconciliation_cursor",
        expected_reconciliation_cursor,
        ExecutionReconciliationCursor,
    )
    seen_facts = seen_facts._for_position_scope(position.scope)
    if root_heads.position_scope != position.scope:
        raise ValueError("root index and position must share exact scope")
    if root_heads.signed_quantity != position.raw_quantity:
        raise ValueError("root economics and position quantity disagree")
    if position.root_fill_sequence != root_heads._root_sequence.to_tuple():
        raise ValueError("position root order and root index disagree")
    if position.effective_head_ids != root_heads._head_sequence.to_tuple():
        raise ValueError("position head IDs and root index disagree")

    authorized_human_facts = tuple(coverage.fact for coverage in book.human_coverages)
    authorized_corroborations = tuple(
        cast(BrokerFillFact, coverage.broker_fact)
        for coverage in book.human_coverages
        if coverage.broker_corroborated and coverage.broker_fact is not None
    )
    replayed = _replay_venue_hydration_snapshot(
        position.scope,
        seen_facts,
        authorized_human_facts=authorized_human_facts,
        authorized_corroborations=authorized_corroborations,
    )
    _require_hydration_match(position, root_heads, replayed)
    required_integrity = replayed.integrity | position.integrity_floor
    if integrity & required_integrity != required_integrity:
        raise ValueError("supplied integrity clears historical evidence")
    rebound_position = replace(
        position,
        _root_fill_sequence=root_heads._root_sequence,
        _effective_head_ids=root_heads._head_sequence,
        _binding=None,
    )
    snapshot = _bind_components(
        rebound_position,
        integrity,
        root_heads,
        seen_facts,
        account_reconciliation_required=(
            expected_reconciliation_cursor.account_reconciliation_required
        ),
        reconciliation_transition_count=(
            expected_reconciliation_cursor.transition_count
        ),
        reconciliation_transition_head=(
            expected_reconciliation_cursor.transition_head
        ),
    )
    if snapshot.commitment != expected_reconciliation_cursor.snapshot_commitment:
        raise ValueError(
            "hydrated execution does not match the independently retained snapshot"
        )
    if not book._execution_matches(snapshot, position.scope):
        raise ValueError("hydrated execution does not match venue high-water")
    return snapshot


def _apply_recovery_input(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
    evolve: _BookEvolver,
    transition: _TransitionFactory,
) -> VenueRecoveryTransition:
    """Apply one recovery command after venue-wide replay/conflict checks."""

    def _transition(
        resulting_book: VenueRecoveryBook,
        resulting_execution: ExecutionSnapshot,
        disposition: VenueRecoveryDisposition,
        *,
        quantity_delta: int = 0,
    ) -> VenueRecoveryTransition:
        return transition(
            resulting_book,
            execution,
            resulting_execution,
            disposition,
            item=item,
            quantity_delta=quantity_delta,
        )

    effect_id = getattr(item, "effect_id", None)
    if isinstance(effect_id, EffectId):
        effect = book._current_effect(effect_id)
        if effect is not None:
            if (
                execution.position.scope != effect.scope.position_scope
                or not book._execution_pair_matches_fast(execution)
            ):
                return _transition(
                    book,
                    execution,
                    VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
                )

    if isinstance(item, IngestHumanAttestedFill):
        return _apply_human_fill(book, execution, item, evolve, _transition)
    if isinstance(item, ReleaseVenueLeg):
        return _apply_release(book, execution, item, evolve, _transition)
    if isinstance(item, RecordBrokerFillEvidence):
        return _apply_broker_evidence(book, execution, item, evolve, _transition)
    if isinstance(item, RecordBrokerRevisionEvidence):
        return _apply_broker_revision_evidence(
            book,
            execution,
            item,
            evolve,
            _transition,
        )
    raise TypeError("item must be a venue-recovery input")
