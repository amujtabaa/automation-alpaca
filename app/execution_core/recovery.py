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
    _book_close_attempt,
    _book_to_execution,
    _book_with_input,
    _book_with_input_and_execution,
    _demote_operator_effects_for_scope,
    _maybe_finalize_effect,
)


def _require_exact_type(name: str, value: object, expected: type[object]) -> None:
    if not isinstance(value, expected):
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
        has_evidence = (
            self.broker_fact is not None
            and self.broker_evidence_digest is not None
            and self.broker_source_input_id is not None
        )
        if self.broker_corroborated != has_evidence:
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
    revision_source_input_ids: tuple[VenueInputId, ...] = ()
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
        if type(self.revision_source_input_ids) is not tuple or any(
            not isinstance(input_id, VenueInputId)
            for input_id in self.revision_source_input_ids
        ):
            raise TypeError("revision_source_input_ids must be VenueInputId tuple")
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


def _transition(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    disposition: VenueRecoveryDisposition,
    *,
    quantity_delta: int = 0,
) -> VenueRecoveryTransition:
    return VenueRecoveryTransition(
        book=book,
        execution=execution,
        disposition=disposition,
        quantity_delta=quantity_delta,
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
    effect = book.effect(effect_id)
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
    human_coverages = cast(tuple[HumanCoverage, ...], book.coverage_for_leg(leg_key))
    broker_coverages = cast(
        tuple[_BrokerCoverage, ...], book.broker_coverage_for_leg(leg_key)
    )
    human = [
        coverage.fact.resulting_cumulative_quantity.value
        for coverage in human_coverages
    ]
    broker = [
        coverage.resulting_cumulative_quantity.value for coverage in broker_coverages
    ]
    return max((*human, *broker), default=0)


def _leg_canonical_total(book: VenueRecoveryBook, leg_key: VenueLegKey) -> int:
    total = _coverage_frontier(book, leg_key)
    for record in book.reconciliations:
        if (
            isinstance(record, RevisionReconciliationRecord)
            and record.leg_key == leg_key
            and record.canonical_applied
        ):
            total = record.resulting_venue_cumulative_quantity.value
    return total


def _effect_canonical_total(
    book: VenueRecoveryBook,
    effect_id: EffectId,
) -> int:
    return sum(
        _leg_canonical_total(book, owner.leg_key)
        for owner in book.owners
        if owner.effect_id == effect_id
    )


def _leg_economic_high_water(
    book: VenueRecoveryBook,
    leg_key: VenueLegKey,
) -> int:
    high_water = max(
        (
            *(
                coverage.fact.resulting_cumulative_quantity.value
                for coverage in book.human_coverages
                if coverage.leg_key == leg_key
            ),
            *(
                coverage.prior_cumulative_quantity.value + coverage.fact.quantity.value
                for coverage in book.broker_coverages
                if coverage.leg_key == leg_key
            ),
        ),
        default=0,
    )
    rejected_revision_inputs = {
        record.input_id
        for record in book.reconciliations
        if isinstance(record, RevisionReconciliationRecord)
        and not record.canonical_applied
    }
    for record in book.input_records:
        item = record.item
        if (
            isinstance(item, RecordBrokerRevisionEvidence)
            and item.leg_key == leg_key
            and item.input_id not in rejected_revision_inputs
        ):
            high_water = max(
                high_water,
                item.prior_venue_cumulative_quantity.value,
                item.resulting_venue_cumulative_quantity.value,
            )
    return high_water


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
    coverages = cast(tuple[HumanCoverage, ...], book.coverage_for_leg(fact.leg_key))
    return next(
        (
            coverage
            for coverage in coverages
            if coverage.effect_id == effect_id and coverage.fact == fact
        ),
        None,
    )


def _has_unattributed_broker_root(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    fact: HumanAttestedFillFact,
) -> bool:
    """Detect same-order broker economics the venue book cannot attribute."""

    represented_broker_roots = {
        coverage.fact.root_key
        for coverage in book.broker_coverages
        if coverage.fact.scope == fact.scope
    }
    return execution.root_heads.broker_root_count(fact.scope) > len(
        represented_broker_roots
    )


def _apply_human_fill(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: IngestHumanAttestedFill,
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
                _book_with_input(book, item),
                execution,
                VenueRecoveryDisposition.APPLIED,
            )
        if replayed.disposition is TransitionDisposition.FACT_CONFLICT:
            return _transition(
                _book_to_execution(book, replayed_execution),
                replayed_execution,
                VenueRecoveryDisposition.CONFLICT,
            )
        return _transition(
            _book_to_execution(book, replayed_execution),
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
        book,
        item,
        next_execution,
        active_attempts=tuple(
            updated_attempt if entry.leg_key == updated_attempt.leg_key else entry
            for entry in book.active_attempts
        ),
        human_coverages=book.human_coverages + (coverage,),
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
    if not book._execution_matches(execution, effect.scope.position_scope):
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
        or any(
            record.effect_id == item.effect_id and record.leg_key == item.leg_key
            for record in book.reconciliations
        )
        or any(
            record.position_scope == effect.scope.position_scope
            and not record.attribution_resolved
            for record in book.execution_reconciliations
        )
    ):
        return _transition(
            book,
            execution,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        )

    next_book = _maybe_finalize_effect(
        _book_close_attempt(
            book,
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


def _intervals_overlap(
    left_prior: int,
    left_resulting: int,
    right_prior: int,
    right_resulting: int,
) -> bool:
    return max(left_prior, right_prior) < min(left_resulting, right_resulting)


def _reconciliation(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RecordBrokerFillEvidence,
    reason: str,
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
        book,
        item,
        next_execution,
        reconciliations=book.reconciliations + (record,),
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

    prior_commands = tuple(
        record
        for record in book.input_records
        if isinstance(record.item, RecordBrokerFillEvidence)
        and record.item.fact.key == item.fact.key
    )
    if prior_commands:
        same_payload = next(
            (
                record
                for record in prior_commands
                if replace(
                    cast(RecordBrokerFillEvidence, record.item),
                    input_id=item.input_id,
                )
                == item
            ),
            None,
        )
        if same_payload is None:
            return _reconciliation(
                book,
                execution,
                item,
                "seen broker fact identity carries changed attribution or evidence",
            )
        if any(
            reconciliation.input_id == same_payload.input_id
            for reconciliation in book.reconciliations
        ):
            return _transition(
                _book_with_input(book, item),
                execution,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            )
        return _transition(
            _book_with_input(book, item),
            execution,
            VenueRecoveryDisposition.APPLIED,
        )

    width_matches = resulting - prior == item.fact.quantity.value
    human = cast(tuple[HumanCoverage, ...], book.coverage_for_leg(item.leg_key))
    exact = next(
        (
            coverage
            for coverage in human
            if coverage.fact.prior_cumulative_quantity.value == prior
            and coverage.fact.resulting_cumulative_quantity.value == resulting
        ),
        None,
    )
    overlaps = any(
        _intervals_overlap(
            prior,
            resulting,
            coverage.fact.prior_cumulative_quantity.value,
            coverage.fact.resulting_cumulative_quantity.value,
        )
        for coverage in human
    )
    mapped_to_another_interval = any(
        coverage is not exact
        and coverage.broker_fact is not None
        and coverage.broker_fact.key == item.fact.key
        for coverage in human
    )

    if exact is not None and width_matches and item.fact.price == exact.fact.price:
        if mapped_to_another_interval:
            return _reconciliation(
                book,
                execution,
                item,
                "broker fact identity is already mapped to another human interval",
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
            )
        next_execution = _snapshot_from_transition(reserved)
        next_coverages = book.human_coverages
        if not exact.broker_corroborated:
            corroborated = replace(
                exact,
                broker_corroborated=True,
                broker_fact=item.fact,
                broker_evidence_digest=item.evidence_digest,
                broker_source_input_id=item.input_id,
            )
            next_coverages = tuple(
                corroborated if coverage == exact else coverage
                for coverage in book.human_coverages
            )
        next_book = _book_with_input_and_execution(
            book,
            item,
            next_execution,
            human_coverages=next_coverages,
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
            book,
            item,
            next_execution,
            active_attempts=tuple(
                updated_attempt if entry.leg_key == updated_attempt.leg_key else entry
                for entry in book.active_attempts
            ),
            broker_coverages=book.broker_coverages + (coverage,),
        )
    else:
        assert closure_head is not None
        assert item.closure_id is not None
        assert item.evidence_reference is not None
        next_book = _book_close_attempt(
            book,
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
            execution=next_execution,
            evidence_digest=item.evidence_digest,
            evolution_changes={"broker_coverages": book.broker_coverages + (coverage,)},
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
    later_human = any(
        coverage.leg_key == target.leg_key
        and coverage.fact.prior_cumulative_quantity.value
        >= target.resulting_cumulative_quantity.value
        for coverage in book.human_coverages
    )
    later_broker = any(
        coverage.leg_key == target.leg_key
        and coverage is not target
        and coverage.prior_cumulative_quantity.value
        >= target.resulting_cumulative_quantity.value
        for coverage in book.broker_coverages
    )
    return not (later_human or later_broker)


def _revision_reconciliation(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RecordBrokerRevisionEvidence,
    *,
    reason: str,
    canonical_applied: bool,
    quantity_delta: int,
    broker_coverages: tuple[_BrokerCoverage, ...] | None = None,
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
        "reconciliations": book.reconciliations + (record,),
        "effects": _demote_operator_effects_for_scope(
            book,
            item.fact.scope.position_scope,
        ),
    }
    if broker_coverages is not None:
        changes["broker_coverages"] = broker_coverages
    next_book = _book_with_input_and_execution(
        book,
        item,
        execution,
        **changes,
    )
    return _transition(
        next_book,
        execution,
        VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        quantity_delta=quantity_delta,
    )


def _apply_broker_revision_evidence(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RecordBrokerRevisionEvidence,
) -> VenueRecoveryTransition:
    effect, owner = _bound_effect_and_owner(book, item.effect_id, item.leg_key)
    if (
        effect is None
        or owner is None
        or not _broker_fact_matches_owner(owner, item.fact)
    ):
        return _transition(book, execution, VenueRecoveryDisposition.REFUSED)

    prior_commands = tuple(
        record
        for record in book.input_records
        if isinstance(record.item, RecordBrokerRevisionEvidence)
        and record.item.fact.key == item.fact.key
    )
    same_payload = next(
        (
            record
            for record in prior_commands
            if replace(
                cast(RecordBrokerRevisionEvidence, record.item),
                input_id=item.input_id,
            )
            == item
        ),
        None,
    )
    if prior_commands:
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
            unresolved = any(
                isinstance(record, RevisionReconciliationRecord)
                and record.input_id == same_payload.input_id
                for record in book.reconciliations
            )
            return _transition(
                _book_with_input(book, item),
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
            replayed_execution,
            item,
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
            next_execution,
            item,
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
    coverage = next(
        (
            entry
            for entry in book.broker_coverages
            if entry.effect_id == item.effect_id
            and entry.leg_key == item.leg_key
            and entry.fact.root_key == item.fact.root_key
        ),
        None,
    )
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
        and all(
            entry.mapping_exact
            for entry in book.broker_coverages
            if entry.leg_key == item.leg_key
        )
        and not any(
            isinstance(record, RevisionReconciliationRecord)
            and record.leg_key == item.leg_key
            and record.canonical_applied
            for record in book.reconciliations
        )
    )

    next_coverages = book.broker_coverages
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
            revision_source_input_ids=(
                coverage.revision_source_input_ids + (item.input_id,)
            ),
            mapping_exact=exact_mapping,
        )
        next_coverages = tuple(
            updated_coverage if entry is coverage else entry
            for entry in book.broker_coverages
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
    next_reconciliations = (
        book.reconciliations
        if reconciliation is None
        else book.reconciliations + (reconciliation,)
    )
    next_effects = (
        book.effects
        if reconciliation is None
        else _demote_operator_effects_for_scope(
            book,
            item.fact.scope.position_scope,
        )
    )

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
            book,
            item,
            next_execution,
            active_attempts=tuple(
                updated_attempt if entry.leg_key == item.leg_key else entry
                for entry in book.active_attempts
            ),
            broker_coverages=next_coverages,
            reconciliations=next_reconciliations,
            effects=next_effects,
        )
    else:
        assert closure_head is not None
        assert item.closure_id is not None
        assert item.evidence_reference is not None
        next_book = _book_close_attempt(
            book,
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
            execution=next_execution,
            evidence_digest=item.evidence_digest,
            evolution_changes={
                "broker_coverages": next_coverages,
                "reconciliations": next_reconciliations,
                "effects": next_effects,
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
) -> ExecutionSnapshot:
    """Re-derive one symbol while authenticating recovery-only observations."""

    account_seen = SeenFactIndex.empty(scope)
    symbol_snapshots: dict[PositionScope, ExecutionSnapshot] = {}
    for index in range(seen_facts.count):
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
    if (
        replayed.seen_facts.entries != seen_facts.entries
        or replayed.seen_facts.commitment != seen_facts.commitment
    ):
        raise ValueError("seen-fact replay did not close exactly")
    return replayed


def bind_venue_execution_snapshot(
    book: VenueRecoveryBook,
    position: PositionState,
    integrity: PositionIntegrity,
    root_heads: RootHeadIndex,
    seen_facts: SeenFactIndex,
) -> ExecutionSnapshot:
    """Bind restart state using exact human/corroboration venue provenance."""

    _require_exact_type("book", book, VenueRecoveryBook)
    _require_exact_type("position", position, PositionState)
    _require_exact_type("integrity", integrity, PositionIntegrity)
    _require_exact_type("root_heads", root_heads, RootHeadIndex)
    _require_exact_type("seen_facts", seen_facts, SeenFactIndex)
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
    )
    if not book._execution_matches(snapshot, position.scope):
        raise ValueError("hydrated execution does not match venue high-water")
    return snapshot


def _apply_recovery_input(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> VenueRecoveryTransition:
    """Apply one recovery command after venue-wide replay/conflict checks."""

    effect_id = getattr(item, "effect_id", None)
    if isinstance(effect_id, EffectId):
        effect = book.effect(effect_id)
        if effect is not None:
            if not book._execution_matches(execution, effect.scope.position_scope):
                return _transition(
                    book,
                    execution,
                    VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
                )

    if isinstance(item, IngestHumanAttestedFill):
        return _apply_human_fill(book, execution, item)
    if isinstance(item, ReleaseVenueLeg):
        return _apply_release(book, execution, item)
    if isinstance(item, RecordBrokerFillEvidence):
        return _apply_broker_evidence(book, execution, item)
    if isinstance(item, RecordBrokerRevisionEvidence):
        return _apply_broker_revision_evidence(book, execution, item)
    raise TypeError("item must be a venue-recovery input")
