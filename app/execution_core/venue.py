"""Pure venue-effect ownership and recovery lifecycle semantic center.

The types in this module are immutable reducer inputs and compact current-state
records.  They perform no I/O and do not infer broker completeness.  Recovery
commands are lazily delegated to :mod:`app.execution_core.recovery` so both
economic and non-economic paths share one public transition seam.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, replace
from enum import Enum, IntFlag
from typing import TYPE_CHECKING, Any, Iterable, cast

from .fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionAuthority,
    ExecutionSide,
    HumanAttestedFillFact,
    PositionScope,
)
from .identity import (
    AccountId,
    ActorId,
    ApplicationGenerationId,
    BrokerId,
    ClaimOccurrenceId,
    ClientOrderId,
    ClosureId,
    EffectId,
    EnvironmentId,
    EvidenceReference,
    MandateId,
    RequestOccurrenceId,
    SourceEventId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from .position import (
    ExecutionSnapshot,
    PositionIntegrity,
    _project_execution_registry,
)
from .values import Quantity

if TYPE_CHECKING:
    from .recovery import (
        HumanCoverage,
        ReconciliationRecord,
        RevisionReconciliationRecord,
        _BrokerCoverage,
    )


_BOOK_CONSTRUCTION_TOKEN = object()


def _require(name: str, value: object, expected: type[object]) -> None:
    if not isinstance(value, expected):
        raise TypeError(f"{name} must be {expected.__name__}")


def _require_tuple(name: str, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be a tuple")


def _require_digest(name: str, value: object) -> None:
    if type(value) is not bytes:
        raise TypeError(f"{name} must be bytes")
    if len(value) != 32:
        raise ValueError(f"{name} must contain exactly 32 bytes")


def _require_input_id(name: str, value: object) -> VenueInputId:
    if not isinstance(value, VenueInputId):
        raise TypeError(f"{name} must be VenueInputId")
    return value


def _execution_head_matches_fact(head: object, fact: object) -> bool:
    """Compare one compact root head with its retained canonical source fact."""

    from .fills import RootHead

    if not isinstance(head, RootHead) or not isinstance(
        fact,
        (
            BrokerFillFact,
            BrokerTradeCorrectFact,
            BrokerTradeBustFact,
            HumanAttestedFillFact,
        ),
    ):
        return False
    authority = (
        ExecutionAuthority.HUMAN_ATTESTED
        if isinstance(fact, HumanAttestedFillFact)
        else ExecutionAuthority.BROKER_AUTHORITATIVE
    )
    if (
        head.root_key != fact.root_key
        or head.scope != fact.scope
        or head.authority is not authority
        or head.current_source_event_id != fact.key.source_event_id
        or head.kind is not fact.kind
    ):
        return False
    if isinstance(fact, (BrokerFillFact, HumanAttestedFillFact)):
        return head.quantity == fact.quantity and head.price == fact.price
    if isinstance(fact, BrokerTradeCorrectFact):
        return (
            head.quantity == fact.revised_quantity
            and head.price == fact.revised_price
        )
    return head.quantity.value == 0 and head.price == fact.reported_price


class EffectKind(str, Enum):
    """A mutating transport request kind."""

    SUBMIT = "SUBMIT"
    CANCEL = "CANCEL"
    REPLACE = "REPLACE"


class BrokerEffectState(str, Enum):
    """Durable lifecycle of one transport occurrence."""

    REQUESTED = "REQUESTED"
    CANCELED_BEFORE_DISPATCH = "CANCELED_BEFORE_DISPATCH"
    DISPATCH_CLAIMED = "DISPATCH_CLAIMED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REJECTED = "REJECTED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    OPERATOR_RECONCILED = "OPERATOR_RECONCILED"


class AcceptanceSetState(str, Enum):
    """Occurrence-level classification of possible concrete acceptances."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    INVALIDATED = "INVALIDATED"


class AcceptanceProofKind(str, Enum):
    """Externally established ways an acceptance set can be closed."""

    NEVER_DISPATCHED = "NEVER_DISPATCHED"
    CONTRACT_COMPLETE_RESPONSE = "CONTRACT_COMPLETE_RESPONSE"
    COVERED_RECONCILIATION = "COVERED_RECONCILIATION"


class VenueAttemptState(str, Enum):
    """Canonical order status, separate from a pending operation."""

    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REPLACED = "REPLACED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    OPERATOR_RECONCILED = "OPERATOR_RECONCILED"


class PendingVenueOperation(str, Enum):
    """Orthogonal operation ambiguity retained beside order status."""

    NONE = "NONE"
    SUBMIT = "SUBMIT"
    CANCEL = "CANCEL"
    REPLACE = "REPLACE"


class VenueRecoveryDisposition(str, Enum):
    """Deterministic classification of one reducer input."""

    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    CONFLICT = "CONFLICT"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    REFUSED = "REFUSED"


class VenueIntegrity(IntFlag):
    """Sticky venue-level integrity evidence for later composed gates."""

    CONSISTENT = 0
    RECONCILIATION_REQUIRED = 1
    ACCEPTANCE_INVALIDATED = 2


class VenueClosureKind(str, Enum):
    """Why an active leg became a terminal immutable closure."""

    BROKER_TERMINAL = "BROKER_TERMINAL"
    BROKER_ECONOMIC = "BROKER_ECONOMIC"
    OPERATOR_RECONCILED = "OPERATOR_RECONCILED"


@dataclass(frozen=True, slots=True)
class VenueScope:
    """Exact generation and Paper-account scope of one recovery book."""

    generation: ApplicationGenerationId
    broker: BrokerId
    environment: EnvironmentId
    account: AccountId

    def __post_init__(self) -> None:
        _require("generation", self.generation, ApplicationGenerationId)
        _require("broker", self.broker, BrokerId)
        _require("environment", self.environment, EnvironmentId)
        _require("account", self.account, AccountId)


@dataclass(frozen=True, slots=True)
class ClientIdentityBinding:
    """Generation/account/occurrence binding of one creating client ID."""

    generation: ApplicationGenerationId
    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    request_occurrence_id: RequestOccurrenceId
    client_order_id: ClientOrderId


@dataclass(frozen=True, slots=True)
class VenueEffectScope:
    """Immutable complete economic and identity scope of one effect."""

    generation: ApplicationGenerationId
    broker: BrokerId
    environment: EnvironmentId
    account: AccountId
    effect_id: EffectId
    request_occurrence_id: RequestOccurrenceId
    mandate_id: MandateId
    kind: EffectKind
    client_order_id: ClientOrderId
    symbol_id: SymbolId
    side: ExecutionSide
    quantity: Quantity
    economic_scope: bytes

    @property
    def client_identity(self) -> ClientIdentityBinding:
        return ClientIdentityBinding(
            generation=self.generation,
            broker=self.broker,
            environment=self.environment,
            account=self.account,
            request_occurrence_id=self.request_occurrence_id,
            client_order_id=self.client_order_id,
        )

    @property
    def position_scope(self) -> PositionScope:
        return PositionScope(
            broker=self.broker,
            environment=self.environment,
            account=self.account,
            symbol_id=self.symbol_id,
        )


@dataclass(frozen=True, slots=True)
class RequestedEffect:
    input_id: VenueInputId
    effect_id: EffectId
    request_occurrence_id: RequestOccurrenceId
    mandate_id: MandateId
    kind: EffectKind
    client_order_id: ClientOrderId
    symbol_id: SymbolId
    side: ExecutionSide
    quantity: Quantity
    economic_scope: bytes

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("effect_id", self.effect_id, EffectId)
        _require(
            "request_occurrence_id", self.request_occurrence_id, RequestOccurrenceId
        )
        _require("mandate_id", self.mandate_id, MandateId)
        _require("kind", self.kind, EffectKind)
        _require("client_order_id", self.client_order_id, ClientOrderId)
        _require("symbol_id", self.symbol_id, SymbolId)
        _require("side", self.side, ExecutionSide)
        _require("quantity", self.quantity, Quantity)
        if self.quantity.value <= 0:
            raise ValueError("quantity must be positive")
        if type(self.economic_scope) is not bytes:
            raise TypeError("economic_scope must be bytes")
        if not self.economic_scope:
            raise ValueError("economic_scope must be nonempty")


@dataclass(frozen=True, slots=True)
class RecordDispatchClaim:
    input_id: VenueInputId
    effect_id: EffectId
    claim_occurrence_id: ClaimOccurrenceId

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("effect_id", self.effect_id, EffectId)
        _require("claim_occurrence_id", self.claim_occurrence_id, ClaimOccurrenceId)


@dataclass(frozen=True, slots=True)
class CancelBeforeDispatch:
    input_id: VenueInputId
    effect_id: EffectId

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("effect_id", self.effect_id, EffectId)


@dataclass(frozen=True, slots=True)
class RecordTransportOutcome:
    input_id: VenueInputId
    effect_id: EffectId
    state: BrokerEffectState

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("effect_id", self.effect_id, EffectId)
        _require("state", self.state, BrokerEffectState)


@dataclass(frozen=True, slots=True)
class RecoverClaimedEffect:
    input_id: VenueInputId
    effect_id: EffectId

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("effect_id", self.effect_id, EffectId)


@dataclass(frozen=True, slots=True)
class DiscoverVenueLeg:
    input_id: VenueInputId
    effect_id: EffectId
    leg_key: VenueLegKey
    observation_id: VenueObservationId

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("effect_id", self.effect_id, EffectId)
        _require("leg_key", self.leg_key, VenueLegKey)
        _require("observation_id", self.observation_id, VenueObservationId)


@dataclass(frozen=True, slots=True)
class RecordPendingVenueOperation:
    input_id: VenueInputId
    leg_key: VenueLegKey
    operation: PendingVenueOperation

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("leg_key", self.leg_key, VenueLegKey)
        _require("operation", self.operation, PendingVenueOperation)


@dataclass(frozen=True, slots=True)
class ObserveVenueStatus:
    input_id: VenueInputId
    leg_key: VenueLegKey
    status: VenueAttemptState
    observation_id: VenueObservationId
    cumulative_quantity: Quantity
    closure_id: ClosureId | None = None
    evidence_reference: EvidenceReference | None = None

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("leg_key", self.leg_key, VenueLegKey)
        _require("status", self.status, VenueAttemptState)
        _require("observation_id", self.observation_id, VenueObservationId)
        _require("cumulative_quantity", self.cumulative_quantity, Quantity)
        if self.closure_id is not None:
            _require("closure_id", self.closure_id, ClosureId)
        if self.evidence_reference is not None:
            _require("evidence_reference", self.evidence_reference, EvidenceReference)


@dataclass(frozen=True, slots=True)
class AcceptanceProof:
    kind: AcceptanceProofKind
    effect_scope: VenueEffectScope
    claim_occurrence_id: ClaimOccurrenceId | None
    evidence_reference: EvidenceReference
    evidence_digest: bytes

    def __post_init__(self) -> None:
        _require("kind", self.kind, AcceptanceProofKind)
        _require("effect_scope", self.effect_scope, VenueEffectScope)
        if self.claim_occurrence_id is not None:
            _require("claim_occurrence_id", self.claim_occurrence_id, ClaimOccurrenceId)
        if self.kind is AcceptanceProofKind.NEVER_DISPATCHED:
            if self.claim_occurrence_id is not None:
                raise ValueError("never-dispatched proof cannot name a claim")
        elif self.claim_occurrence_id is None:
            raise ValueError("external completeness proof must name the exact claim")
        _require("evidence_reference", self.evidence_reference, EvidenceReference)
        _require_digest("evidence_digest", self.evidence_digest)


@dataclass(frozen=True, slots=True)
class CloseAcceptanceSet:
    input_id: VenueInputId
    effect_id: EffectId
    proof: AcceptanceProof

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("effect_id", self.effect_id, EffectId)
        _require("proof", self.proof, AcceptanceProof)


@dataclass(frozen=True, slots=True)
class AcceptanceContradiction:
    leg_key: VenueLegKey
    observation_id: VenueObservationId


@dataclass(frozen=True, slots=True)
class BrokerEffect:
    scope: VenueEffectScope
    state: BrokerEffectState = BrokerEffectState.REQUESTED
    acceptance_set_state: AcceptanceSetState = AcceptanceSetState.OPEN
    claim_occurrence_id: ClaimOccurrenceId | None = None
    acceptance_proof: AcceptanceProof | None = None
    contradiction_evidence: tuple[AcceptanceContradiction, ...] = ()

    @property
    def effect_id(self) -> EffectId:
        return self.scope.effect_id


@dataclass(frozen=True, slots=True)
class DispatchClaim:
    effect_scope: VenueEffectScope
    claim_occurrence_id: ClaimOccurrenceId

    @property
    def effect_id(self) -> EffectId:
        return self.effect_scope.effect_id


@dataclass(frozen=True, slots=True)
class VenueIdentityOwner:
    leg_key: VenueLegKey
    effect_scope: VenueEffectScope
    observation_id: VenueObservationId

    @property
    def effect_id(self) -> EffectId:
        return self.effect_scope.effect_id


@dataclass(frozen=True, slots=True)
class VenueAttempt:
    leg_key: VenueLegKey
    status: VenueAttemptState
    pending_operation: PendingVenueOperation | None
    cumulative_quantity: Quantity
    last_observation_id: VenueObservationId


@dataclass(frozen=True, slots=True)
class VenueTerminalClosure:
    leg_key: VenueLegKey
    closure_id: ClosureId
    ordinal: int
    predecessor_closure_id: ClosureId | None
    status: VenueAttemptState
    cumulative_quantity: Quantity
    observed_cumulative_quantity: Quantity
    evidence_reference: EvidenceReference
    kind: VenueClosureKind
    source_input_id: VenueInputId
    observation_id: VenueObservationId | None = None
    source_event_id: SourceEventId | None = None
    broker_terminal_state: VenueAttemptState | None = None
    actor: ActorId | None = None
    reason: str | None = None
    evidence_digest: bytes | None = None


@dataclass(frozen=True, slots=True)
class VenueInputRecord:
    input_id: VenueInputId
    item: object
    semantic_alias_of: VenueInputId | None = None


@dataclass(frozen=True, slots=True)
class VenueExecutionBinding:
    """Exact execution high-water paired with one current symbol checkpoint."""

    position_scope: PositionScope
    position_commitment: bytes
    root_heads_commitment: bytes
    integrity_bits: int

    def __post_init__(self) -> None:
        _require("position_scope", self.position_scope, PositionScope)
        _require_digest("position_commitment", self.position_commitment)
        _require_digest("root_heads_commitment", self.root_heads_commitment)
        if type(self.integrity_bits) is not int or self.integrity_bits < 0:
            raise ValueError("integrity_bits must be a non-negative exact integer")


@dataclass(frozen=True, slots=True)
class CatchUpExecutionRegistry:
    """Project one proven monotonic account registry into a venue checkpoint."""

    input_id: VenueInputId
    source_execution: ExecutionSnapshot

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("source_execution", self.source_execution, ExecutionSnapshot)


@dataclass(frozen=True, slots=True)
class ExecutionRegistryReconciliationRecord:
    """Blocking attribution evidence for canonical same-symbol catch-up."""

    input_id: VenueInputId
    position_scope: PositionScope
    prior_registry_count: int
    resulting_registry_count: int
    prior_registry_commitment: bytes
    resulting_registry_commitment: bytes
    prior_position_commitment: bytes
    resulting_position_commitment: bytes
    prior_root_heads_commitment: bytes
    resulting_root_heads_commitment: bytes
    prior_integrity_bits: int
    resulting_integrity_bits: int
    canonical_applied: bool
    attribution_resolved: bool
    reason: str

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("position_scope", self.position_scope, PositionScope)
        if type(self.prior_registry_count) is not int or self.prior_registry_count < 0:
            raise ValueError("prior_registry_count must be a non-negative exact integer")
        if (
            type(self.resulting_registry_count) is not int
            or self.resulting_registry_count <= self.prior_registry_count
        ):
            raise ValueError(
                "resulting_registry_count must strictly exceed the prior count"
            )
        for name in (
            "prior_registry_commitment",
            "resulting_registry_commitment",
            "prior_position_commitment",
            "resulting_position_commitment",
            "prior_root_heads_commitment",
            "resulting_root_heads_commitment",
        ):
            _require_digest(name, getattr(self, name))
        if type(self.prior_integrity_bits) is not int or self.prior_integrity_bits < 0:
            raise ValueError("prior_integrity_bits must be a non-negative exact integer")
        if (
            type(self.resulting_integrity_bits) is not int
            or self.resulting_integrity_bits < 0
        ):
            raise ValueError(
                "resulting_integrity_bits must be a non-negative exact integer"
            )
        if type(self.canonical_applied) is not bool:
            raise TypeError("canonical_applied must be bool")
        if not self.canonical_applied:
            raise ValueError("registry reconciliation records canonical applied truth")
        if type(self.attribution_resolved) is not bool:
            raise TypeError("attribution_resolved must be bool")
        if type(self.reason) is not str or not self.reason.strip():
            raise ValueError("reason must be a nonblank string")


@dataclass(frozen=True, slots=True)
class VenueRecoveryTransition:
    book: VenueRecoveryBook
    execution: ExecutionSnapshot
    disposition: VenueRecoveryDisposition
    quantity_delta: int


@dataclass(frozen=True, slots=True)
class VenueRecoveryBook:
    """Immutable compact venue checkpoint plus append-only proof material."""

    scope: VenueScope
    effects: tuple[BrokerEffect, ...] = ()
    claims: tuple[DispatchClaim, ...] = ()
    owners: tuple[VenueIdentityOwner, ...] = ()
    active_attempts: tuple[VenueAttempt, ...] = ()
    closure_heads: tuple[VenueTerminalClosure, ...] = ()
    closure_history: tuple[VenueTerminalClosure, ...] = ()
    input_records: tuple[VenueInputRecord, ...] = ()
    execution_registry_commitment: bytes | None = None
    execution_bindings: tuple[VenueExecutionBinding, ...] = ()
    execution_reconciliations: tuple[
        ExecutionRegistryReconciliationRecord, ...
    ] = ()
    human_coverages: tuple[HumanCoverage, ...] = ()
    broker_coverages: tuple[_BrokerCoverage, ...] = ()
    reconciliations: tuple[
        ReconciliationRecord | RevisionReconciliationRecord, ...
    ] = ()
    _construction_token: InitVar[object] = None

    def __post_init__(self, _construction_token: object) -> None:
        if _construction_token is not _BOOK_CONSTRUCTION_TOKEN:
            raise ValueError(
                "venue checkpoint claim/provenance requires verified construction"
            )
        _require("scope", self.scope, VenueScope)
        for name in (
            "effects",
            "claims",
            "owners",
            "active_attempts",
            "closure_heads",
            "closure_history",
            "input_records",
            "execution_bindings",
            "execution_reconciliations",
            "human_coverages",
            "broker_coverages",
            "reconciliations",
        ):
            _require_tuple(name, getattr(self, name))

        self._require_recovery_entry_types()
        if self.execution_registry_commitment is not None:
            _require_digest(
                "execution_registry_commitment",
                self.execution_registry_commitment,
            )
        effects = self._validated_effects()
        self._validated_execution_bindings(effects)
        claims = self._validated_claims(effects)
        owners = self._validated_owners(effects)
        active = self._validated_active_attempts(owners)
        heads = self._validated_closures(owners, active)
        inputs = self._validated_inputs(effects, claims, owners)
        self._validated_recovery_entries(effects, owners, inputs)

        if set(active) & set(heads) or set(active) | set(heads) != set(owners):
            raise ValueError("each owner must have one active attempt or closure head")
        self._validate_effect_edges(effects, claims, owners, heads)

    def _require_recovery_entry_types(self) -> None:
        """Keep the checkpoint concrete even though recovery types import venue."""

        from .recovery import (
            HumanCoverage,
            ReconciliationRecord,
            RevisionReconciliationRecord,
            _BrokerCoverage,
        )

        self._require_entries("effect", self.effects, BrokerEffect)
        self._require_entries("claim", self.claims, DispatchClaim)
        self._require_entries("owner", self.owners, VenueIdentityOwner)
        self._require_entries("active attempt", self.active_attempts, VenueAttempt)
        self._require_entries("closure head", self.closure_heads, VenueTerminalClosure)
        self._require_entries(
            "closure history", self.closure_history, VenueTerminalClosure
        )
        self._require_entries("input record", self.input_records, VenueInputRecord)
        self._require_entries(
            "execution binding", self.execution_bindings, VenueExecutionBinding
        )
        self._require_entries(
            "execution reconciliation",
            self.execution_reconciliations,
            ExecutionRegistryReconciliationRecord,
        )
        self._require_entries("human coverage", self.human_coverages, HumanCoverage)
        self._require_entries("broker coverage", self.broker_coverages, _BrokerCoverage)
        if any(
            not isinstance(
                entry,
                (ReconciliationRecord, RevisionReconciliationRecord),
            )
            for entry in self.reconciliations
        ):
            raise TypeError("reconciliation entries must be typed reconciliation records")

    @staticmethod
    def _require_entries(
        name: str, entries: tuple[object, ...], expected: type[object]
    ) -> None:
        if any(not isinstance(entry, expected) for entry in entries):
            raise TypeError(f"{name} entries must be {expected.__name__}")

    def _validated_effects(self) -> dict[EffectId, BrokerEffect]:
        self._require_unique("effect", (entry.effect_id for entry in self.effects))
        self._require_unique(
            "request occurrence",
            (entry.scope.request_occurrence_id for entry in self.effects),
        )
        self._require_unique(
            "client identity", (entry.scope.client_identity for entry in self.effects)
        )
        effects: dict[EffectId, BrokerEffect] = {}
        for effect in self.effects:
            scope = effect.scope
            self._validate_effect_scope(scope)
            _require("state", effect.state, BrokerEffectState)
            _require(
                "acceptance_set_state",
                effect.acceptance_set_state,
                AcceptanceSetState,
            )
            if effect.claim_occurrence_id is not None:
                _require(
                    "claim_occurrence_id",
                    effect.claim_occurrence_id,
                    ClaimOccurrenceId,
                )
            if effect.acceptance_proof is not None:
                _require("acceptance_proof", effect.acceptance_proof, AcceptanceProof)
                _require(
                    "proof.kind", effect.acceptance_proof.kind, AcceptanceProofKind
                )
                _require(
                    "proof.effect_scope",
                    effect.acceptance_proof.effect_scope,
                    VenueEffectScope,
                )
                if effect.acceptance_proof.claim_occurrence_id is not None:
                    _require(
                        "proof.claim_occurrence_id",
                        effect.acceptance_proof.claim_occurrence_id,
                        ClaimOccurrenceId,
                    )
                _require(
                    "proof.evidence_reference",
                    effect.acceptance_proof.evidence_reference,
                    EvidenceReference,
                )
                _require_digest(
                    "proof.evidence_digest",
                    effect.acceptance_proof.evidence_digest,
                )
            _require_tuple("contradiction_evidence", effect.contradiction_evidence)
            for contradiction in effect.contradiction_evidence:
                _require(
                    "contradiction evidence",
                    contradiction,
                    AcceptanceContradiction,
                )
                _require("contradiction.leg_key", contradiction.leg_key, VenueLegKey)
                _require(
                    "contradiction.observation_id",
                    contradiction.observation_id,
                    VenueObservationId,
                )
            effects[effect.effect_id] = effect
        return effects

    def _validate_effect_scope(self, scope: VenueEffectScope) -> None:
        _require("effect scope", scope, VenueEffectScope)
        for name, value, expected in (
            ("effect scope.generation", scope.generation, ApplicationGenerationId),
            ("effect scope.broker", scope.broker, BrokerId),
            ("effect scope.environment", scope.environment, EnvironmentId),
            ("effect scope.account", scope.account, AccountId),
            ("effect scope.effect_id", scope.effect_id, EffectId),
            (
                "effect scope.request_occurrence_id",
                scope.request_occurrence_id,
                RequestOccurrenceId,
            ),
            ("effect scope.mandate_id", scope.mandate_id, MandateId),
            ("effect scope.kind", scope.kind, EffectKind),
            ("effect scope.client_order_id", scope.client_order_id, ClientOrderId),
            ("effect scope.symbol_id", scope.symbol_id, SymbolId),
            ("effect scope.side", scope.side, ExecutionSide),
            ("effect scope.quantity", scope.quantity, Quantity),
        ):
            _require(name, value, expected)
        if (
            scope.generation != self.scope.generation
            or scope.broker != self.scope.broker
            or scope.environment != self.scope.environment
            or scope.account != self.scope.account
        ):
            raise ValueError("effect scope must match the exact book scope")
        if scope.quantity.value <= 0:
            raise ValueError("effect scope quantity must be positive")
        if type(scope.economic_scope) is not bytes or not scope.economic_scope:
            raise ValueError("effect scope economic_scope must be nonempty bytes")

    def _validated_execution_bindings(
        self, effects: dict[EffectId, BrokerEffect]
    ) -> None:
        self._require_unique(
            "execution binding",
            (binding.position_scope for binding in self.execution_bindings),
        )
        bound_scopes = {binding.position_scope for binding in self.execution_bindings}
        effect_scopes = {effect.scope.position_scope for effect in effects.values()}
        if bound_scopes != effect_scopes:
            raise ValueError(
                "every effect symbol requires exactly one execution high-water binding"
            )
        if bool(effects) != (self.execution_registry_commitment is not None):
            raise ValueError(
                "effect checkpoints require one account execution-registry commitment"
            )

    def _validated_claims(
        self, effects: dict[EffectId, BrokerEffect]
    ) -> dict[EffectId, DispatchClaim]:
        self._require_unique("claim effect", (entry.effect_id for entry in self.claims))
        self._require_unique(
            "claim occurrence", (entry.claim_occurrence_id for entry in self.claims)
        )
        claims: dict[EffectId, DispatchClaim] = {}
        for claim in self.claims:
            effect = effects.get(claim.effect_id)
            if effect is None or claim.effect_scope != effect.scope:
                raise ValueError(
                    "claim must bind the registered canonical effect scope"
                )
            _require("claim occurrence", claim.claim_occurrence_id, ClaimOccurrenceId)
            claims[claim.effect_id] = claim
        return claims

    def _validated_owners(
        self, effects: dict[EffectId, BrokerEffect]
    ) -> dict[VenueLegKey, VenueIdentityOwner]:
        self._require_unique("owner", (entry.leg_key for entry in self.owners))
        owners: dict[VenueLegKey, VenueIdentityOwner] = {}
        for owner in self.owners:
            _require("owner.leg_key", owner.leg_key, VenueLegKey)
            _require("owner.observation_id", owner.observation_id, VenueObservationId)
            if not _same_leg_scope(self.scope, owner.leg_key):
                raise ValueError("owner leg must match the exact book scope")
            effect = effects.get(owner.effect_id)
            if effect is None or owner.effect_scope != effect.scope:
                raise ValueError(
                    "owner must bind the canonical registered effect scope"
                )
            owners[owner.leg_key] = owner
        return owners

    def _validated_active_attempts(
        self, owners: dict[VenueLegKey, VenueIdentityOwner]
    ) -> dict[VenueLegKey, VenueAttempt]:
        self._require_unique(
            "active attempt", (entry.leg_key for entry in self.active_attempts)
        )
        active: dict[VenueLegKey, VenueAttempt] = {}
        for attempt in self.active_attempts:
            _require("attempt.leg_key", attempt.leg_key, VenueLegKey)
            _require("attempt.status", attempt.status, VenueAttemptState)
            _require(
                "attempt.cumulative_quantity", attempt.cumulative_quantity, Quantity
            )
            _require(
                "attempt.last_observation_id",
                attempt.last_observation_id,
                VenueObservationId,
            )
            if attempt.leg_key not in owners:
                raise ValueError("active attempt must belong to an immutable owner")
            if attempt.status in _TERMINAL_ATTEMPT_STATES:
                raise ValueError("active attempt cannot carry a terminal status")
            if attempt.pending_operation is not None:
                _require(
                    "attempt.pending_operation",
                    attempt.pending_operation,
                    PendingVenueOperation,
                )
                if attempt.pending_operation is PendingVenueOperation.NONE:
                    raise ValueError("pending operation absence must be None")
            if attempt.cumulative_quantity.value < 0:
                raise ValueError("attempt cumulative quantity cannot be negative")
            active[attempt.leg_key] = attempt
        return active

    def _validated_closures(
        self,
        owners: dict[VenueLegKey, VenueIdentityOwner],
        active: dict[VenueLegKey, VenueAttempt],
    ) -> dict[VenueLegKey, VenueTerminalClosure]:
        self._require_unique(
            "closure head", (entry.leg_key for entry in self.closure_heads)
        )
        self._require_unique(
            "closure identity", (entry.closure_id for entry in self.closure_history)
        )
        histories: dict[VenueLegKey, list[VenueTerminalClosure]] = {}
        for closure in self.closure_history:
            self._validate_closure(closure, owners)
            histories.setdefault(closure.leg_key, []).append(closure)

        heads: dict[VenueLegKey, VenueTerminalClosure] = {}
        for head in self.closure_heads:
            self._validate_closure(head, owners)
            history = histories.get(head.leg_key)
            if history is None or history[-1] != head:
                raise ValueError(
                    "closure head must be the latest closure-history entry"
                )
            heads[head.leg_key] = head

        for leg_key, history in histories.items():
            if leg_key in active:
                raise ValueError(
                    "closure history cannot coexist with an active attempt"
                )
            for ordinal, closure in enumerate(history, start=1):
                if closure.ordinal != ordinal:
                    raise ValueError("closure history ordinals must be contiguous")
                predecessor = None if ordinal == 1 else history[ordinal - 2].closure_id
                if closure.predecessor_closure_id != predecessor:
                    raise ValueError(
                        "closure history must name its immediate predecessor"
                    )
                if closure.kind is VenueClosureKind.BROKER_ECONOMIC:
                    if ordinal == 1:
                        raise ValueError(
                            "broker-economic closure must succeed a terminal closure"
                        )
                    prior = history[ordinal - 2]
                    if (
                        closure.status is not prior.status
                        or closure.broker_terminal_state
                        is not prior.broker_terminal_state
                        or closure.observed_cumulative_quantity
                        != prior.observed_cumulative_quantity
                    ):
                        raise ValueError(
                            "broker-economic closure must preserve terminal identity"
                        )
            if leg_key not in heads:
                raise ValueError("closure history must have exactly one current head")
        return heads

    @staticmethod
    def _validate_closure(
        closure: VenueTerminalClosure,
        owners: dict[VenueLegKey, VenueIdentityOwner],
    ) -> None:
        _require("closure.leg_key", closure.leg_key, VenueLegKey)
        _require("closure.closure_id", closure.closure_id, ClosureId)
        _require("closure.status", closure.status, VenueAttemptState)
        _require("closure.cumulative_quantity", closure.cumulative_quantity, Quantity)
        _require(
            "closure.observed_cumulative_quantity",
            closure.observed_cumulative_quantity,
            Quantity,
        )
        _require(
            "closure.evidence_reference", closure.evidence_reference, EvidenceReference
        )
        _require("closure.kind", closure.kind, VenueClosureKind)
        _require("closure.source_input_id", closure.source_input_id, VenueInputId)
        if closure.leg_key not in owners:
            raise ValueError("closure must belong to an immutable owner")
        if type(closure.ordinal) is not int or closure.ordinal <= 0:
            raise ValueError("closure ordinal must be a positive integer")
        if closure.predecessor_closure_id is not None:
            _require(
                "closure.predecessor_closure_id",
                closure.predecessor_closure_id,
                ClosureId,
            )
        if closure.observation_id is not None:
            _require(
                "closure.observation_id", closure.observation_id, VenueObservationId
            )
        if closure.source_event_id is not None:
            _require(
                "closure.source_event_id", closure.source_event_id, SourceEventId
            )
        if closure.broker_terminal_state is not None:
            _require(
                "closure.broker_terminal_state",
                closure.broker_terminal_state,
                VenueAttemptState,
            )
        if closure.actor is not None:
            _require("closure.actor", closure.actor, ActorId)
        if closure.reason is not None and type(closure.reason) is not str:
            raise TypeError("closure.reason must be a string")
        if (
            closure.cumulative_quantity.value < 0
            or closure.observed_cumulative_quantity.value < 0
        ):
            raise ValueError("closure cumulative quantities cannot be negative")
        if closure.kind is VenueClosureKind.BROKER_TERMINAL:
            if (
                closure.status not in _BROKER_TERMINAL_ATTEMPT_STATES
                or closure.broker_terminal_state is not closure.status
                or closure.observation_id is None
                or closure.source_event_id is not None
                or closure.actor is not None
                or closure.reason is not None
                or closure.evidence_digest is not None
            ):
                raise ValueError(
                    "broker closure must carry its exact broker terminal state"
                )
        elif closure.kind is VenueClosureKind.BROKER_ECONOMIC:
            if (
                closure.source_event_id is None
                or closure.observation_id is not None
                or closure.broker_terminal_state
                not in _BROKER_TERMINAL_ATTEMPT_STATES
                or closure.actor is not None
                or closure.reason is not None
                or closure.evidence_digest is None
            ):
                raise ValueError(
                    "broker-economic closure must carry exact execution evidence"
                )
        elif (
            closure.status is not VenueAttemptState.OPERATOR_RECONCILED
            or closure.broker_terminal_state not in _BROKER_TERMINAL_ATTEMPT_STATES
            or closure.source_event_id is not None
            or closure.actor is None
            or closure.reason is None
            or not closure.reason.strip()
            or closure.evidence_digest is None
        ):
            raise ValueError(
                "operator closure must carry an external broker terminal state"
            )
        if closure.evidence_digest is not None:
            _require_digest("closure.evidence_digest", closure.evidence_digest)

    def _validated_inputs(
        self,
        effects: dict[EffectId, BrokerEffect],
        claims: dict[EffectId, DispatchClaim],
        owners: dict[VenueLegKey, VenueIdentityOwner],
    ) -> dict[VenueInputId, object]:
        from .recovery import (
            IngestHumanAttestedFill,
            RecordBrokerFillEvidence,
            RecordBrokerRevisionEvidence,
            ReleaseVenueLeg,
        )

        self._require_unique("input", (entry.input_id for entry in self.input_records))
        input_types = _VENUE_INPUTS + (
            IngestHumanAttestedFill,
            RecordBrokerFillEvidence,
            RecordBrokerRevisionEvidence,
            ReleaseVenueLeg,
        )
        prior_input_records: dict[VenueInputId, VenueInputRecord] = {}
        for record in self.input_records:
            _require("input record.input_id", record.input_id, VenueInputId)
            if not isinstance(record.item, input_types):
                raise TypeError("input record item must be a venue-recovery input")
            if record.item.input_id != record.input_id:
                raise ValueError("input record identity must match its immutable item")
            if record.semantic_alias_of is not None:
                _require(
                    "input record.semantic_alias_of",
                    record.semantic_alias_of,
                    VenueInputId,
                )
                semantic_source = prior_input_records.get(record.semantic_alias_of)
                if (
                    semantic_source is None
                    or semantic_source.semantic_alias_of is not None
                    or type(semantic_source.item) is not type(record.item)
                    or replace(
                        semantic_source.item,
                        input_id=record.input_id,
                    )
                    != record.item
                ):
                    raise ValueError(
                        "semantic input alias requires an earlier direct source"
                    )
            prior_input_records[record.input_id] = record

        items = tuple(record.item for record in self.input_records)
        requests = tuple(item for item in items if isinstance(item, RequestedEffect))
        claim_inputs = tuple(
            item for item in items if isinstance(item, RecordDispatchClaim)
        )
        discoveries = tuple(
            item for item in items if isinstance(item, DiscoverVenueLeg)
        )
        acceptance_closures = tuple(
            item for item in items if isinstance(item, CloseAcceptanceSet)
        )
        observations = tuple(
            item for item in items if isinstance(item, ObserveVenueStatus)
        )
        releases = tuple(item for item in items if isinstance(item, ReleaseVenueLeg))
        broker_evidence = tuple(
            item for item in items if isinstance(item, RecordBrokerFillEvidence)
        )
        broker_revisions = tuple(
            item for item in items if isinstance(item, RecordBrokerRevisionEvidence)
        )

        for request in requests:
            effect = effects.get(request.effect_id)
            if effect is None or _effect_scope(self, request) != effect.scope:
                raise ValueError(
                    "requested-effect input provenance must match canonical scope"
                )
        for effect in effects.values():
            if not any(request.effect_id == effect.effect_id for request in requests):
                raise ValueError("effect requires requested-effect input provenance")

        for claim_input in claim_inputs:
            claim = claims.get(claim_input.effect_id)
            if (
                claim is None
                or claim.claim_occurrence_id != claim_input.claim_occurrence_id
            ):
                raise ValueError(
                    "dispatch-claim input provenance must match claim edge"
                )
        for claim in claims.values():
            if not any(
                item.effect_id == claim.effect_id
                and item.claim_occurrence_id == claim.claim_occurrence_id
                for item in claim_inputs
            ):
                raise ValueError("claim edge requires dispatch-claim input provenance")

        lifecycle_states: dict[EffectId, BrokerEffectState] = {}
        for item in items:
            if isinstance(item, RequestedEffect):
                if item.effect_id in lifecycle_states:
                    raise ValueError("effect lifecycle cannot contain two requests")
                lifecycle_states[item.effect_id] = BrokerEffectState.REQUESTED
            elif isinstance(item, CancelBeforeDispatch):
                if lifecycle_states.get(item.effect_id) is not BrokerEffectState.REQUESTED:
                    raise ValueError("cancel lifecycle input has no requested predecessor")
                lifecycle_states[item.effect_id] = (
                    BrokerEffectState.CANCELED_BEFORE_DISPATCH
                )
            elif isinstance(item, RecordDispatchClaim):
                if lifecycle_states.get(item.effect_id) is not BrokerEffectState.REQUESTED:
                    raise ValueError("claim lifecycle input has no requested predecessor")
                lifecycle_states[item.effect_id] = BrokerEffectState.DISPATCH_CLAIMED
            elif isinstance(item, RecoverClaimedEffect):
                if (
                    lifecycle_states.get(item.effect_id)
                    is not BrokerEffectState.DISPATCH_CLAIMED
                ):
                    raise ValueError("recovery lifecycle input has no claimed predecessor")
                lifecycle_states[item.effect_id] = BrokerEffectState.OUTCOME_UNKNOWN
            elif isinstance(item, RecordTransportOutcome):
                current = lifecycle_states.get(item.effect_id)
                allowed = {
                    BrokerEffectState.DISPATCH_CLAIMED: {
                        BrokerEffectState.ACKNOWLEDGED,
                        BrokerEffectState.REJECTED,
                        BrokerEffectState.OUTCOME_UNKNOWN,
                    },
                    BrokerEffectState.OUTCOME_UNKNOWN: {
                        BrokerEffectState.ACKNOWLEDGED,
                        BrokerEffectState.REJECTED,
                        BrokerEffectState.NEEDS_REVIEW,
                    },
                }
                if current is None or item.state not in allowed.get(current, set()):
                    raise ValueError("transport lifecycle input has no valid predecessor")
                lifecycle_states[item.effect_id] = item.state
        for effect in effects.values():
            expected_state = (
                BrokerEffectState.NEEDS_REVIEW
                if effect.state is BrokerEffectState.OPERATOR_RECONCILED
                else effect.state
            )
            if lifecycle_states.get(effect.effect_id) is not expected_state:
                raise ValueError(
                    "effect state requires complete lifecycle input provenance"
                )

        for discovery in discoveries:
            owner = owners.get(discovery.leg_key)
            if (
                owner is None
                or owner.effect_id != discovery.effect_id
                or owner.observation_id != discovery.observation_id
            ):
                raise ValueError("leg-discovery input provenance must match owner edge")
        for owner in owners.values():
            if not any(
                item.leg_key == owner.leg_key
                and item.effect_id == owner.effect_id
                and item.observation_id == owner.observation_id
                for item in discoveries
            ):
                raise ValueError("owner edge requires leg-discovery input provenance")

        ordered_effect_states: dict[EffectId, BrokerEffectState] = {}
        ordered_leg_effects: dict[VenueLegKey, EffectId] = {}
        ordered_leg_states: dict[VenueLegKey, VenueAttemptState] = {}
        ordered_closed_legs: set[VenueLegKey] = set()
        admitted_human_sources: set[VenueInputId] = set()
        direct_human_sources = {
            coverage.source_input_id for coverage in self.human_coverages
        }
        human_sources_by_leg: dict[VenueLegKey, set[VenueInputId]] = {}
        for coverage in self.human_coverages:
            human_sources_by_leg.setdefault(coverage.leg_key, set()).add(
                coverage.source_input_id
            )

        for record in self.input_records:
            item = record.item
            if isinstance(item, RequestedEffect):
                ordered_effect_states[item.effect_id] = BrokerEffectState.REQUESTED
            elif isinstance(item, CancelBeforeDispatch):
                ordered_effect_states[item.effect_id] = (
                    BrokerEffectState.CANCELED_BEFORE_DISPATCH
                )
            elif isinstance(item, RecordDispatchClaim):
                ordered_effect_states[item.effect_id] = (
                    BrokerEffectState.DISPATCH_CLAIMED
                )
            elif isinstance(item, RecoverClaimedEffect):
                ordered_effect_states[item.effect_id] = BrokerEffectState.OUTCOME_UNKNOWN
            elif isinstance(item, RecordTransportOutcome):
                ordered_effect_states[item.effect_id] = item.state
            elif isinstance(item, DiscoverVenueLeg):
                prior_effect_id = ordered_leg_effects.get(item.leg_key)
                if prior_effect_id is None:
                    ordered_leg_effects[item.leg_key] = item.effect_id
                    ordered_leg_states[item.leg_key] = VenueAttemptState.WORKING
                elif prior_effect_id != item.effect_id:
                    raise ValueError("venue leg cannot change its owning effect")
            elif isinstance(item, ObserveVenueStatus):
                prior_status = ordered_leg_states.get(item.leg_key)
                if prior_status is None:
                    raise ValueError("venue observation precedes leg discovery")
                if item.leg_key in ordered_closed_legs:
                    if item.status not in _TERMINAL_ATTEMPT_STATES:
                        raise ValueError("closed venue leg cannot become active again")
                elif item.status in _TERMINAL_ATTEMPT_STATES:
                    ordered_closed_legs.add(item.leg_key)
                    ordered_leg_states[item.leg_key] = item.status
                else:
                    if (
                        _NONTERMINAL_PRECEDENCE[item.status]
                        < _NONTERMINAL_PRECEDENCE[prior_status]
                    ):
                        raise ValueError("venue status history cannot regress")
                    ordered_leg_states[item.leg_key] = item.status
            elif isinstance(item, IngestHumanAttestedFill):
                if item.input_id not in direct_human_sources:
                    continue
                if (
                    ordered_effect_states.get(item.effect_id)
                    is not BrokerEffectState.NEEDS_REVIEW
                    or ordered_leg_effects.get(item.fact.leg_key) != item.effect_id
                    or ordered_leg_states.get(item.fact.leg_key)
                    is not VenueAttemptState.NEEDS_REVIEW
                    or item.fact.leg_key in ordered_closed_legs
                ):
                    raise ValueError(
                        "human execution source requires contemporaneous review gates"
                    )
                admitted_human_sources.add(item.input_id)
            elif isinstance(item, ReleaseVenueLeg):
                if (
                    ordered_effect_states.get(item.effect_id)
                    is not BrokerEffectState.NEEDS_REVIEW
                    or ordered_leg_effects.get(item.leg_key) != item.effect_id
                    or ordered_leg_states.get(item.leg_key)
                    is not VenueAttemptState.NEEDS_REVIEW
                    or item.leg_key in ordered_closed_legs
                    or not human_sources_by_leg.get(item.leg_key, set()).issubset(
                        admitted_human_sources
                    )
                ):
                    raise ValueError(
                        "operator release requires prior ordered review authority"
                    )
                ordered_closed_legs.add(item.leg_key)
                ordered_leg_states[item.leg_key] = (
                    VenueAttemptState.OPERATOR_RECONCILED
                )

        active_by_leg = {attempt.leg_key: attempt for attempt in self.active_attempts}
        for owner in owners.values():
            attempt = active_by_leg.get(owner.leg_key)
            if attempt is None:
                continue
            derived_status = VenueAttemptState.WORKING
            derived_pending: PendingVenueOperation | None = None
            derived_cumulative = Quantity(0)
            derived_observation = owner.observation_id
            for record in self.input_records:
                item = record.item
                if (
                    isinstance(item, RecordPendingVenueOperation)
                    and item.leg_key == owner.leg_key
                ):
                    derived_pending = item.operation
                elif (
                    isinstance(item, ObserveVenueStatus)
                    and item.leg_key == owner.leg_key
                    and item.status not in _TERMINAL_ATTEMPT_STATES
                ):
                    derived_status = item.status
                    derived_cumulative = Quantity(
                        max(
                            derived_cumulative.value,
                            item.cumulative_quantity.value,
                        )
                    )
                    derived_observation = item.observation_id
                elif (
                    isinstance(item, IngestHumanAttestedFill)
                    and item.effect_id == owner.effect_id
                    and item.fact.leg_key == owner.leg_key
                    and any(
                        coverage.effect_id == item.effect_id
                        and coverage.fact == item.fact
                        for coverage in self.human_coverages
                    )
                ):
                    derived_cumulative = Quantity(
                        max(
                            derived_cumulative.value,
                            item.fact.resulting_cumulative_quantity.value,
                        )
                    )
                elif (
                    isinstance(item, RecordBrokerFillEvidence)
                    and item.effect_id == owner.effect_id
                    and item.leg_key == owner.leg_key
                    and any(
                        coverage.effect_id == item.effect_id
                        and coverage.leg_key == item.leg_key
                        and coverage.prior_cumulative_quantity
                        == item.prior_cumulative_quantity
                        and coverage.fact == item.fact
                        and coverage.evidence_digest == item.evidence_digest
                        for coverage in self.broker_coverages
                    )
                ):
                    derived_cumulative = Quantity(
                        max(
                            derived_cumulative.value,
                            item.resulting_cumulative_quantity.value,
                        )
                    )
                elif (
                    isinstance(item, RecordBrokerRevisionEvidence)
                    and item.effect_id == owner.effect_id
                    and item.leg_key == owner.leg_key
                    and any(
                        coverage.effect_id == item.effect_id
                        and coverage.leg_key == item.leg_key
                        and coverage.head_fact == item.fact
                        for coverage in self.broker_coverages
                    )
                ):
                    derived_cumulative = Quantity(
                        max(
                            derived_cumulative.value,
                            item.resulting_venue_cumulative_quantity.value,
                        )
                    )
            if (
                attempt.status is not derived_status
                or attempt.pending_operation is not derived_pending
                or attempt.cumulative_quantity != derived_cumulative
                or attempt.last_observation_id != derived_observation
            ):
                raise ValueError(
                    "active attempt requires exact observation and pending provenance"
                )

        for close in acceptance_closures:
            effect = effects.get(close.effect_id)
            if effect is None or effect.acceptance_proof != close.proof:
                raise ValueError(
                    "acceptance-close input provenance must match immutable proof"
                )
        for effect in effects.values():
            if effect.acceptance_proof is not None and not any(
                item.effect_id == effect.effect_id
                and item.proof == effect.acceptance_proof
                for item in acceptance_closures
            ):
                raise ValueError("acceptance proof requires close-input provenance")

        for closure in self.closure_history:
            owner = owners[closure.leg_key]
            if closure.kind is VenueClosureKind.BROKER_TERMINAL:
                has_source = any(
                    item.leg_key == closure.leg_key
                    and item.status is closure.status
                    and item.observation_id == closure.observation_id
                    and item.cumulative_quantity
                    == closure.observed_cumulative_quantity
                    and item.closure_id == closure.closure_id
                    and item.evidence_reference == closure.evidence_reference
                    and item.input_id == closure.source_input_id
                    for item in observations
                )
            elif closure.kind is VenueClosureKind.BROKER_ECONOMIC:
                predecessor = next(
                    (
                        entry
                        for entry in self.closure_history
                        if entry.closure_id == closure.predecessor_closure_id
                    ),
                    None,
                )
                has_source = predecessor is not None and (
                    any(
                        item.effect_id == owner.effect_id
                        and item.leg_key == closure.leg_key
                        and item.resulting_cumulative_quantity
                        == closure.cumulative_quantity
                        and item.fact.key.source_event_id == closure.source_event_id
                        and item.evidence_reference == closure.evidence_reference
                        and item.evidence_digest == closure.evidence_digest
                        and item.closure_id == closure.closure_id
                        and item.input_id == closure.source_input_id
                        for item in broker_evidence
                    )
                    or any(
                        item.effect_id == owner.effect_id
                        and item.leg_key == closure.leg_key
                        and item.resulting_venue_cumulative_quantity
                        == closure.cumulative_quantity
                        and item.fact.key.source_event_id == closure.source_event_id
                        and item.evidence_reference == closure.evidence_reference
                        and item.evidence_digest == closure.evidence_digest
                        and item.closure_id == closure.closure_id
                        and item.input_id == closure.source_input_id
                        for item in broker_revisions
                    )
                )
            else:
                effect = effects[owner.effect_id]
                has_source = any(
                    item.effect_id == owner.effect_id
                    and item.leg_key == closure.leg_key
                    and item.claim_occurrence_id == effect.claim_occurrence_id
                    and item.venue_cumulative_quantity == closure.cumulative_quantity
                    and item.broker_terminal_state is closure.broker_terminal_state
                    and item.evidence_reference == closure.evidence_reference
                    and item.closure_id == closure.closure_id
                    and item.input_id == closure.source_input_id
                    and item.actor == closure.actor
                    and item.reason == closure.reason
                    and item.evidence_digest == closure.evidence_digest
                    for item in releases
                )
            if not has_source:
                raise ValueError("closure requires exact source-input provenance")

        return {record.input_id: record.item for record in self.input_records}

    def _validated_recovery_entries(
        self,
        effects: dict[EffectId, BrokerEffect],
        owners: dict[VenueLegKey, VenueIdentityOwner],
        input_by_id: dict[VenueInputId, object],
    ) -> None:
        from .recovery import (
            IngestHumanAttestedFill,
            RecordBrokerFillEvidence,
            RecordBrokerRevisionEvidence,
            ReconciliationRecord,
            ReleaseVenueLeg,
            RevisionReconciliationRecord,
        )

        self._require_unique(
            "human coverage fact", (item.fact.key for item in self.human_coverages)
        )
        self._require_unique(
            "execution reconciliation input",
            (item.input_id for item in self.execution_reconciliations),
        )
        for registry_record in self.execution_reconciliations:
            source = input_by_id.get(registry_record.input_id)
            if not isinstance(source, CatchUpExecutionRegistry):
                raise ValueError(
                    "execution reconciliation requires exact catch-up provenance"
                )
            execution = source.source_execution
            scope = execution.position.scope
            if (
                scope != registry_record.position_scope
                or scope.broker != self.scope.broker
                or scope.environment != self.scope.environment
                or scope.account != self.scope.account
                or execution.seen_facts.count
                != registry_record.resulting_registry_count
                or execution.seen_facts.commitment
                != registry_record.resulting_registry_commitment
                or execution.position.commitment
                != registry_record.resulting_position_commitment
                or execution.root_heads.commitment
                != registry_record.resulting_root_heads_commitment
                or execution.integrity.value
                != registry_record.resulting_integrity_bits
                or not execution.seen_facts.has_prefix(
                    registry_record.prior_registry_count,
                    registry_record.prior_registry_commitment,
                )
            ):
                raise ValueError(
                    "execution reconciliation does not close its canonical catch-up"
                )
            source_state_changed = any(
                (
                    registry_record.prior_position_commitment
                    != registry_record.resulting_position_commitment,
                    registry_record.prior_root_heads_commitment
                    != registry_record.resulting_root_heads_commitment,
                    registry_record.prior_integrity_bits
                    != registry_record.resulting_integrity_bits,
                )
            )
            if source_state_changed == registry_record.attribution_resolved:
                raise ValueError(
                    "catch-up attribution result contradicts its symbol commitments"
                )
            if any(
                execution.seen_facts.observation_at(index).position_scope != scope
                for index in range(
                    registry_record.prior_registry_count,
                    registry_record.resulting_registry_count,
                )
            ):
                raise ValueError(
                    "execution reconciliation suffix must belong to its source symbol"
                )
        self._require_unique(
            "mapped broker fact",
            (
                *(
                    item.broker_fact.key
                    for item in self.human_coverages
                    if item.broker_fact is not None
                ),
                *(item.fact.key for item in self.broker_coverages),
                *(
                    item.head_fact.key
                    for item in self.broker_coverages
                    if item.head_fact != item.fact
                ),
            ),
        )
        self._require_unique(
            "covered execution root",
            (
                *(item.fact.root_key for item in self.human_coverages),
                *(item.fact.root_key for item in self.broker_coverages),
                *(
                    item.broker_fact.root_key
                    for item in self.human_coverages
                    if item.broker_fact is not None
                ),
            ),
        )

        def validate_coverage_binding(
            coverage: HumanCoverage | _BrokerCoverage,
        ) -> None:
            effect = effects.get(coverage.effect_id)
            owner = owners.get(coverage.leg_key)
            if effect is None or owner is None or owner.effect_id != coverage.effect_id:
                raise ValueError("coverage must bind an owned canonical effect")
            if coverage.fact.scope.broker != effect.scope.broker or (
                coverage.fact.scope.environment != effect.scope.environment
                or coverage.fact.scope.account != effect.scope.account
                or coverage.fact.scope.order_id != coverage.leg_key.order_id
                or coverage.fact.scope.symbol_id != effect.scope.symbol_id
                or coverage.fact.scope.side is not effect.scope.side
            ):
                raise ValueError("coverage fact must match the owner economic scope")

        for human_coverage in self.human_coverages:
            validate_coverage_binding(human_coverage)
            if (
                human_coverage.fact.resulting_cumulative_quantity.value
                > effects[human_coverage.effect_id].scope.quantity.value
            ):
                raise ValueError("human coverage cannot exceed immutable effect capacity")
        for broker_coverage in self.broker_coverages:
            validate_coverage_binding(broker_coverage)
        for human_coverage in self.human_coverages:
            effect = effects[human_coverage.effect_id]
            if (
                human_coverage.fact.leg_key != human_coverage.leg_key
                or human_coverage.fact.request_occurrence_id
                != effect.scope.request_occurrence_id
                or human_coverage.fact.claim_occurrence_id != effect.claim_occurrence_id
            ):
                raise ValueError("human coverage must bind the exact claim occurrence")
            human_source = input_by_id.get(human_coverage.source_input_id)
            if not (
                isinstance(human_source, IngestHumanAttestedFill)
                and human_source.effect_id == human_coverage.effect_id
                and human_source.fact == human_coverage.fact
            ):
                raise ValueError(
                    "human coverage requires exact source-input provenance"
                )
            if human_coverage.broker_corroborated:
                assert human_coverage.broker_fact is not None
                assert human_coverage.broker_evidence_digest is not None
                assert human_coverage.broker_source_input_id is not None
                if (
                    human_coverage.broker_fact.quantity != human_coverage.fact.quantity
                    or human_coverage.broker_fact.price != human_coverage.fact.price
                ):
                    raise ValueError(
                        "broker corroboration must match committed human economics"
                    )
                broker_source = input_by_id.get(
                    human_coverage.broker_source_input_id
                )
                if not (
                    isinstance(broker_source, RecordBrokerFillEvidence)
                    and broker_source.effect_id == human_coverage.effect_id
                    and broker_source.leg_key == human_coverage.leg_key
                    and broker_source.prior_cumulative_quantity
                    == human_coverage.fact.prior_cumulative_quantity
                    and broker_source.resulting_cumulative_quantity
                    == human_coverage.fact.resulting_cumulative_quantity
                    and broker_source.fact == human_coverage.broker_fact
                    and broker_source.evidence_digest
                    == human_coverage.broker_evidence_digest
                ):
                    raise ValueError(
                        "broker corroboration requires exact source-input provenance"
                    )
        for broker_coverage in self.broker_coverages:
            root_source = input_by_id.get(broker_coverage.root_source_input_id)
            if not (
                isinstance(root_source, RecordBrokerFillEvidence)
                and root_source.effect_id == broker_coverage.effect_id
                and root_source.leg_key == broker_coverage.leg_key
                and root_source.prior_cumulative_quantity
                    == broker_coverage.prior_cumulative_quantity
                and root_source.resulting_cumulative_quantity.value
                    == (
                        broker_coverage.prior_cumulative_quantity.value
                        + broker_coverage.fact.quantity.value
                    )
                and root_source.fact == broker_coverage.fact
                and root_source.evidence_digest == broker_coverage.evidence_digest
            ):
                raise ValueError(
                    "broker coverage requires exact source-input provenance"
                )
            head_quantity = (
                broker_coverage.head_fact.revised_quantity.value
                if isinstance(broker_coverage.head_fact, BrokerTradeCorrectFact)
                else (
                    0
                    if isinstance(broker_coverage.head_fact, BrokerTradeBustFact)
                    else broker_coverage.head_fact.quantity.value
                )
            )
            if broker_coverage.mapping_exact and (
                broker_coverage.resulting_cumulative_quantity.value
                - broker_coverage.prior_cumulative_quantity.value
                != head_quantity
            ):
                raise ValueError(
                    "exact broker coverage interval must match its current root head"
                )
            predecessor_source_event_id = broker_coverage.fact.key.source_event_id
            for revision_input_id in broker_coverage.revision_source_input_ids:
                revision_source = input_by_id.get(revision_input_id)
                if not (
                    isinstance(revision_source, RecordBrokerRevisionEvidence)
                    and revision_source.effect_id == broker_coverage.effect_id
                    and revision_source.leg_key == broker_coverage.leg_key
                    and revision_source.fact.root_key
                    == broker_coverage.fact.root_key
                    and revision_source.fact.predecessor_source_event_id
                    == predecessor_source_event_id
                ):
                    raise ValueError(
                        "broker revision history requires exact lineage provenance"
                    )
                predecessor_source_event_id = (
                    revision_source.fact.key.source_event_id
                )
            if broker_coverage.head_fact == broker_coverage.fact:
                if (
                    broker_coverage.head_evidence_digest
                    != broker_coverage.evidence_digest
                    or broker_coverage.head_source_input_id
                    != broker_coverage.root_source_input_id
                    or broker_coverage.revision_source_input_ids
                    or not broker_coverage.mapping_exact
                ):
                    raise ValueError(
                        "unrevised broker coverage must retain exact root evidence"
                    )
            else:
                head_source = input_by_id.get(
                    broker_coverage.head_source_input_id
                )
                if not (
                    isinstance(head_source, RecordBrokerRevisionEvidence)
                    and head_source.effect_id == broker_coverage.effect_id
                    and head_source.leg_key == broker_coverage.leg_key
                    and head_source.fact == broker_coverage.head_fact
                    and head_source.evidence_digest
                    == broker_coverage.head_evidence_digest
                    and broker_coverage.revision_source_input_ids
                    and broker_coverage.revision_source_input_ids[-1]
                    == broker_coverage.head_source_input_id
                ):
                    raise ValueError(
                        "broker coverage head requires exact revision provenance"
                    )
                head_reconciliation = next(
                    (
                        record
                        for record in self.reconciliations
                        if isinstance(record, RevisionReconciliationRecord)
                        and record.input_id == head_source.input_id
                    ),
                    None,
                )
                if broker_coverage.mapping_exact == (
                    head_reconciliation is not None
                    and head_reconciliation.canonical_applied
                ):
                    raise ValueError(
                        "broker coverage mapping flag must match revision reconciliation"
                    )

        intervals: dict[
            VenueLegKey, list[tuple[int, int, EffectId, bool]]
        ] = {}
        for human_coverage in self.human_coverages:
            intervals.setdefault(human_coverage.leg_key, []).append(
                (
                    human_coverage.fact.prior_cumulative_quantity.value,
                    human_coverage.fact.resulting_cumulative_quantity.value,
                    human_coverage.effect_id,
                    False,
                )
            )
        for broker_coverage in self.broker_coverages:
            intervals.setdefault(broker_coverage.leg_key, []).append(
                (
                    broker_coverage.prior_cumulative_quantity.value,
                    broker_coverage.resulting_cumulative_quantity.value,
                    broker_coverage.effect_id,
                    broker_coverage.mapping_exact
                    and isinstance(
                        broker_coverage.head_fact,
                        BrokerTradeBustFact,
                    ),
                )
            )
        for leg_intervals in intervals.values():
            frontier = 0
            for prior, resulting, _effect_id, allow_zero in sorted(
                leg_intervals,
                key=lambda interval: (interval[0], interval[1], interval[3]),
            ):
                if (
                    prior != frontier
                    or resulting < prior
                    or (resulting == prior and not allow_zero)
                ):
                    raise ValueError(
                        "coverage intervals must be positive, contiguous, and disjoint"
                    )
                frontier = resulting

        for record in self.reconciliations:
            reconciliation_effect = effects.get(record.effect_id)
            owner = owners.get(record.leg_key)
            if (
                reconciliation_effect is None
                or owner is None
                or owner.effect_id != record.effect_id
            ):
                raise ValueError("reconciliation must bind an owned canonical effect")
            source = input_by_id.get(record.input_id)
            if isinstance(record, ReconciliationRecord):
                exact_source = (
                    isinstance(source, RecordBrokerFillEvidence)
                    and source.effect_id == record.effect_id
                    and source.leg_key == record.leg_key
                    and source.prior_cumulative_quantity
                    == record.prior_cumulative_quantity
                    and source.resulting_cumulative_quantity
                    == record.resulting_cumulative_quantity
                    and source.fact == record.fact
                    and source.evidence_digest == record.evidence_digest
                )
            else:
                assert isinstance(record, RevisionReconciliationRecord)
                exact_source = (
                    isinstance(source, RecordBrokerRevisionEvidence)
                    and source.effect_id == record.effect_id
                    and source.leg_key == record.leg_key
                    and source.prior_root_quantity == record.prior_root_quantity
                    and source.prior_venue_cumulative_quantity
                    == record.prior_venue_cumulative_quantity
                    and source.resulting_venue_cumulative_quantity
                    == record.resulting_venue_cumulative_quantity
                    and source.fact == record.fact
                    and source.evidence_digest == record.evidence_digest
                )
            if not exact_source:
                raise ValueError(
                    "reconciliation must retain its exact source-input provenance"
                )

        direct_recovery_inputs = {
            *(coverage.source_input_id for coverage in self.human_coverages),
            *(
                coverage.broker_source_input_id
                for coverage in self.human_coverages
                if coverage.broker_source_input_id is not None
            ),
            *(coverage.root_source_input_id for coverage in self.broker_coverages),
            *(coverage.head_source_input_id for coverage in self.broker_coverages),
            *(
                input_id
                for coverage in self.broker_coverages
                for input_id in coverage.revision_source_input_ids
            ),
            *(record.input_id for record in self.reconciliations),
            *(record.input_id for record in self.execution_reconciliations),
            *(
                closure.source_input_id
                for closure in self.closure_history
                if closure.source_input_id is not None
            ),
        }
        recovery_input_types = (
            IngestHumanAttestedFill,
            RecordBrokerFillEvidence,
            RecordBrokerRevisionEvidence,
            ReleaseVenueLeg,
            CatchUpExecutionRegistry,
        )
        for input_record in self.input_records:
            item = input_record.item
            if not isinstance(item, recovery_input_types):
                continue
            is_direct = input_record.input_id in direct_recovery_inputs
            if is_direct and input_record.semantic_alias_of is not None:
                raise ValueError(
                    "semantic recovery alias cannot replace its direct source"
                )
            if not is_direct and (
                input_record.semantic_alias_of is None
                or input_record.semantic_alias_of not in direct_recovery_inputs
            ):
                raise ValueError(
                    "recovery input requires a direct outcome or backward alias"
                )

    def _validate_effect_edges(
        self,
        effects: dict[EffectId, BrokerEffect],
        claims: dict[EffectId, DispatchClaim],
        owners: dict[VenueLegKey, VenueIdentityOwner],
        heads: dict[VenueLegKey, VenueTerminalClosure],
    ) -> None:
        for effect_id, effect in effects.items():
            claim = claims.get(effect_id)
            requires_claim = effect.state not in {
                BrokerEffectState.REQUESTED,
                BrokerEffectState.CANCELED_BEFORE_DISPATCH,
            }
            if requires_claim != (effect.claim_occurrence_id is not None):
                raise ValueError("effect state and immutable claim edge disagree")
            if (claim is None) != (effect.claim_occurrence_id is None):
                raise ValueError("effect claim edge must have exactly one claim record")
            if (
                claim is not None
                and claim.claim_occurrence_id != effect.claim_occurrence_id
            ):
                raise ValueError("claim record must match the effect claim occurrence")

            proof = effect.acceptance_proof
            if effect.acceptance_set_state is AcceptanceSetState.OPEN:
                if proof is not None or effect.contradiction_evidence:
                    raise ValueError(
                        "open acceptance set cannot carry proof or contradiction"
                    )
            elif proof is None:
                raise ValueError("closed or invalidated acceptance set requires proof")
            elif (
                proof.effect_scope != effect.scope
                or proof.claim_occurrence_id != effect.claim_occurrence_id
            ):
                raise ValueError(
                    "acceptance proof must bind exact effect scope and claim"
                )
            elif proof.kind is AcceptanceProofKind.NEVER_DISPATCHED:
                if (
                    effect.state is not BrokerEffectState.CANCELED_BEFORE_DISPATCH
                    or effect.claim_occurrence_id is not None
                ):
                    raise ValueError(
                        "never-dispatched proof requires local cancellation"
                    )
            elif effect.claim_occurrence_id is None:
                raise ValueError("claimed acceptance proof requires an immutable claim")

            if effect.acceptance_set_state is AcceptanceSetState.INVALIDATED and (
                not effect.contradiction_evidence
            ):
                raise ValueError(
                    "invalidated acceptance set requires contradiction evidence"
                )
            for contradiction in effect.contradiction_evidence:
                owner = owners.get(contradiction.leg_key)
                if owner is None or owner.effect_id != effect_id:
                    raise ValueError(
                        "contradiction must name an owned leg of its effect"
                    )
                if owner.observation_id != contradiction.observation_id:
                    raise ValueError("contradiction must name the owner observation")

            if effect.state is BrokerEffectState.OPERATOR_RECONCILED:
                owned_legs = [
                    leg_key
                    for leg_key, owner in owners.items()
                    if owner.effect_id == effect_id
                ]
                if not owned_legs:
                    raise ValueError(
                        "operator-reconciled effect requires at least one owned leg"
                    )
                binding = self.execution_binding(effect.scope.position_scope)
                unresolved_execution = (
                    PositionIntegrity.EXECUTION_FACT_CONFLICT
                    | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
                )
                if effect.acceptance_set_state is not AcceptanceSetState.CLOSED:
                    raise ValueError(
                        "operator-reconciled effect requires closed acceptance"
                    )
                if binding is None or binding.integrity_bits & unresolved_execution.value:
                    raise ValueError(
                        "operator-reconciled effect requires clean execution integrity"
                    )
                if any(
                    record.effect_id == effect_id for record in self.reconciliations
                ) or any(
                    record.position_scope == effect.scope.position_scope
                    and not record.attribution_resolved
                    for record in self.execution_reconciliations
                ):
                    raise ValueError(
                        "operator-reconciled effect cannot retain unresolved evidence"
                    )
                if any(
                    coverage.effect_id == effect_id and not coverage.mapping_exact
                    for coverage in self.broker_coverages
                ):
                    raise ValueError(
                        "operator-reconciled effect requires exact venue mapping"
                    )
                for leg_key in owned_legs:
                    head = heads.get(leg_key)
                    if head is None:
                        raise ValueError(
                            "operator-reconciled effect requires every leg closed"
                        )
                    covered_cumulative = _covered_cumulative(self, leg_key)
                    if head.cumulative_quantity.value != covered_cumulative:
                        raise ValueError(
                            "operator closure must equal canonical covered quantity"
                        )
                    if (
                        head.status is VenueAttemptState.FILLED
                        or head.broker_terminal_state is VenueAttemptState.FILLED
                    ) and covered_cumulative != effect.scope.quantity.value:
                        raise ValueError(
                            "filled operator closure must equal effect capacity"
                        )

    @staticmethod
    def _require_unique(name: str, values: Iterable[object]) -> None:
        materialized = tuple(values)
        if len(materialized) != len(set(materialized)):
            raise ValueError(f"{name} identities must be unique")

    @classmethod
    def empty(cls, scope: VenueScope) -> VenueRecoveryBook:
        _require("scope", scope, VenueScope)
        return cls(scope=scope, _construction_token=_BOOK_CONSTRUCTION_TOKEN)

    def effect(self, effect_id: EffectId) -> BrokerEffect | None:
        return next(
            (item for item in self.effects if item.effect_id == effect_id), None
        )

    def execution_binding(
        self, position_scope: PositionScope
    ) -> VenueExecutionBinding | None:
        return next(
            (
                item
                for item in self.execution_bindings
                if item.position_scope == position_scope
            ),
            None,
        )

    def _execution_matches(
        self,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> bool:
        """Return whether execution is the exact bound account/symbol high-water."""

        if (
            self.execution_registry_commitment
            != execution.seen_facts.commitment
            or not self._execution_symbol_matches(execution, position_scope)
        ):
            return False

        return True

    def _execution_symbol_matches(
        self,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> bool:
        """Return whether one symbol matches its bound venue high-water."""

        binding = self.execution_binding(position_scope)
        if (
            execution.position.scope != position_scope
            or binding is None
            or binding.position_commitment != execution.position.commitment
            or binding.root_heads_commitment != execution.root_heads.commitment
            or binding.integrity_bits != execution.integrity.value
        ):
            return False
        human_roots_match = all(
            _execution_head_matches_fact(
                execution.root_heads.get(coverage.fact.root_key),
                coverage.fact,
            )
            for coverage in self.human_coverages
            if coverage.fact.scope.position_scope == position_scope
        )
        broker_roots_match = all(
            _execution_head_matches_fact(
                execution.root_heads.get(coverage.head_fact.root_key),
                coverage.head_fact,
            )
            for coverage in self.broker_coverages
            if coverage.fact.scope.position_scope == position_scope
        )
        return human_roots_match and broker_roots_match

    def owner(self, leg_key: VenueLegKey) -> VenueIdentityOwner | None:
        return next((item for item in self.owners if item.leg_key == leg_key), None)

    def active_attempt(self, leg_key: VenueLegKey) -> VenueAttempt | None:
        return next(
            (item for item in self.active_attempts if item.leg_key == leg_key), None
        )

    def closure_head(self, leg_key: VenueLegKey) -> VenueTerminalClosure | None:
        return next(
            (item for item in self.closure_heads if item.leg_key == leg_key), None
        )

    def coverage_for_leg(self, leg_key: VenueLegKey) -> tuple[object, ...]:
        return tuple(
            item
            for item in self.human_coverages
            if getattr(item, "leg_key", None) == leg_key
        )

    def broker_coverage_for_leg(self, leg_key: VenueLegKey) -> tuple[object, ...]:
        return tuple(
            item
            for item in self.broker_coverages
            if getattr(item, "leg_key", None) == leg_key
        )

    def _input_record(self, input_id: VenueInputId) -> VenueInputRecord | None:
        return next(
            (item for item in self.input_records if item.input_id == input_id), None
        )

def _rebuild_book(book: VenueRecoveryBook, **changes: Any) -> VenueRecoveryBook:
    """Rebuild one verified checkpoint; never exposed on the public book object."""

    return replace(
        book,
        _construction_token=_BOOK_CONSTRUCTION_TOKEN,
        **changes,
    )


def _next_execution_bindings(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
) -> tuple[VenueExecutionBinding, ...]:
    next_binding = VenueExecutionBinding(
        position_scope=execution.position.scope,
        position_commitment=execution.position.commitment,
        root_heads_commitment=execution.root_heads.commitment,
        integrity_bits=execution.integrity.value,
    )
    current = book.execution_binding(next_binding.position_scope)
    if current is None:
        return book.execution_bindings + (next_binding,)
    return tuple(
        next_binding if item.position_scope == next_binding.position_scope else item
        for item in book.execution_bindings
    )


def _book_with_input(
    book: VenueRecoveryBook,
    item: object,
    **changes: Any,
) -> VenueRecoveryBook:
    input_id = _require_input_id("input_id", getattr(item, "input_id", None))
    if book._input_record(input_id) is not None:
        raise ValueError("input identity already exists")
    semantic_source = next(
        (
            record
            for record in book.input_records
            if record.semantic_alias_of is None
            and type(record.item) is type(item)
            and replace(cast(Any, record.item), input_id=input_id) == item
        ),
        None,
    )
    return _rebuild_book(
        book,
        input_records=book.input_records
        + (
            VenueInputRecord(
                input_id,
                item,
                semantic_alias_of=(
                    None if semantic_source is None else semantic_source.input_id
                ),
            ),
        ),
        **changes,
    )


def _book_with_input_and_execution(
    book: VenueRecoveryBook,
    item: object,
    execution: ExecutionSnapshot,
    **changes: Any,
) -> VenueRecoveryBook:
    unresolved_execution = (
        PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    if execution.integrity & unresolved_execution and "effects" not in changes:
        changes["effects"] = _demote_operator_effects_for_scope(
            book,
            execution.position.scope,
        )
    return _book_with_input(
        book,
        item,
        execution_registry_commitment=execution.seen_facts.commitment,
        execution_bindings=_next_execution_bindings(book, execution),
        **changes,
    )


def _book_to_execution(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
) -> VenueRecoveryBook:
    unresolved_execution = (
        PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    effects = (
        _demote_operator_effects_for_scope(book, execution.position.scope)
        if execution.integrity & unresolved_execution
        else book.effects
    )
    return _rebuild_book(
        book,
        effects=effects,
        execution_registry_commitment=execution.seen_facts.commitment,
        execution_bindings=_next_execution_bindings(book, execution),
    )


def _demote_operator_effects_for_scope(
    book: VenueRecoveryBook,
    position_scope: PositionScope,
) -> tuple[BrokerEffect, ...]:
    return tuple(
        replace(effect, state=BrokerEffectState.NEEDS_REVIEW)
        if effect.scope.position_scope == position_scope
        and effect.state is BrokerEffectState.OPERATOR_RECONCILED
        else effect
        for effect in book.effects
    )


def _book_replace_effect(
    book: VenueRecoveryBook,
    effect: BrokerEffect,
) -> VenueRecoveryBook:
    if book.effect(effect.effect_id) is None:
        raise KeyError("effect is not registered")
    return _rebuild_book(
        book,
        effects=tuple(
            effect if item.effect_id == effect.effect_id else item
            for item in book.effects
        ),
    )


def _book_close_attempt(
    book: VenueRecoveryBook,
    *,
    leg_key: VenueLegKey,
    closure_id: ClosureId,
    status: VenueAttemptState,
    cumulative_quantity: Quantity,
    observed_cumulative_quantity: Quantity,
    evidence_reference: EvidenceReference,
    kind: VenueClosureKind,
    observation_id: VenueObservationId | None = None,
    source_event_id: SourceEventId | None = None,
    broker_terminal_state: VenueAttemptState | None = None,
    source_input: object | None = None,
    execution: ExecutionSnapshot | None = None,
    evolution_changes: dict[str, Any] | None = None,
    actor: ActorId | None = None,
    reason: str | None = None,
    evidence_digest: bytes | None = None,
) -> VenueRecoveryBook:
    owner = book.owner(leg_key)
    active = book.active_attempt(leg_key)
    head = book.closure_head(leg_key)
    if owner is None or (active is None) == (head is None):
        raise ValueError("owner must have exactly one current leg representation")
    if any(entry.closure_id == closure_id for entry in book.closure_history):
        raise ValueError("closure identity already exists")
    if source_input is None:
        raise ValueError("closure requires one immutable source input")
    source_input_id = _require_input_id(
        "source_input.input_id",
        getattr(source_input, "input_id", None),
    )
    closure = VenueTerminalClosure(
        leg_key=leg_key,
        closure_id=closure_id,
        ordinal=1 if head is None else head.ordinal + 1,
        predecessor_closure_id=None if head is None else head.closure_id,
        status=status,
        cumulative_quantity=cumulative_quantity,
        observed_cumulative_quantity=observed_cumulative_quantity,
        evidence_reference=evidence_reference,
        kind=kind,
        source_input_id=source_input_id,
        observation_id=observation_id,
        source_event_id=source_event_id,
        broker_terminal_state=broker_terminal_state,
        actor=actor,
        reason=reason,
        evidence_digest=evidence_digest,
    )
    attempts = tuple(
        item for item in book.active_attempts if item.leg_key != leg_key
    )
    heads = tuple(item for item in book.closure_heads if item.leg_key != leg_key)
    changes: dict[str, Any] = {
        "active_attempts": attempts,
        "closure_heads": heads + (closure,),
        "closure_history": book.closure_history + (closure,),
    }
    if evolution_changes is not None:
        changes.update(evolution_changes)
    if execution is not None:
        return _book_with_input_and_execution(
            book,
            source_input,
            execution,
            **changes,
        )
    return _book_with_input(book, source_input, **changes)


_TERMINAL_ATTEMPT_STATES = {
    VenueAttemptState.FILLED,
    VenueAttemptState.CANCELED,
    VenueAttemptState.REJECTED,
    VenueAttemptState.EXPIRED,
    VenueAttemptState.REPLACED,
    VenueAttemptState.OPERATOR_RECONCILED,
}
_BROKER_TERMINAL_ATTEMPT_STATES = _TERMINAL_ATTEMPT_STATES - {
    VenueAttemptState.OPERATOR_RECONCILED,
}
_NONTERMINAL_PRECEDENCE = {
    VenueAttemptState.WORKING: 0,
    VenueAttemptState.PARTIALLY_FILLED: 1,
    VenueAttemptState.NEEDS_REVIEW: 2,
}


def _covered_cumulative(book: VenueRecoveryBook, leg_key: VenueLegKey) -> int:
    """Return current canonical covered economics, never status high-water."""

    return max(
        (
            *(
                coverage.fact.resulting_cumulative_quantity.value
                for coverage in book.human_coverages
                if coverage.leg_key == leg_key
            ),
            *(
                coverage.resulting_cumulative_quantity.value
                for coverage in book.broker_coverages
                if coverage.leg_key == leg_key
            ),
        ),
        default=0,
    )


def _transition(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    disposition: VenueRecoveryDisposition,
) -> VenueRecoveryTransition:
    return VenueRecoveryTransition(book, execution, disposition, 0)


def _effect_scope(book: VenueRecoveryBook, item: RequestedEffect) -> VenueEffectScope:
    return VenueEffectScope(
        generation=book.scope.generation,
        broker=book.scope.broker,
        environment=book.scope.environment,
        account=book.scope.account,
        effect_id=item.effect_id,
        request_occurrence_id=item.request_occurrence_id,
        mandate_id=item.mandate_id,
        kind=item.kind,
        client_order_id=item.client_order_id,
        symbol_id=item.symbol_id,
        side=item.side,
        quantity=item.quantity,
        economic_scope=item.economic_scope,
    )


def _register_effect(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RequestedEffect,
) -> VenueRecoveryBook | None:
    if book.effect(item.effect_id) is not None:
        return None
    if any(
        effect.scope.client_order_id == item.client_order_id
        or effect.scope.request_occurrence_id == item.request_occurrence_id
        for effect in book.effects
    ):
        return None
    effect = BrokerEffect(scope=_effect_scope(book, item))
    return _book_with_input_and_execution(
        book,
        item,
        execution,
        effects=book.effects + (effect,),
    )


def _same_leg_scope(scope: VenueScope, leg_key: VenueLegKey) -> bool:
    return (
        scope.broker == leg_key.broker
        and scope.environment == leg_key.environment
        and scope.account == leg_key.account
    )


def _record_claim(
    book: VenueRecoveryBook, item: RecordDispatchClaim
) -> VenueRecoveryBook | None:
    effect = book.effect(item.effect_id)
    if (
        effect is None
        or effect.state is not BrokerEffectState.REQUESTED
        or effect.claim_occurrence_id is not None
        or any(
            claim.claim_occurrence_id == item.claim_occurrence_id
            for claim in book.claims
        )
    ):
        return None
    claimed = replace(
        effect,
        state=BrokerEffectState.DISPATCH_CLAIMED,
        claim_occurrence_id=item.claim_occurrence_id,
    )
    claim = DispatchClaim(effect.scope, item.claim_occurrence_id)
    return _book_with_input(
        book,
        item,
        effects=tuple(
            claimed if entry.effect_id == item.effect_id else entry
            for entry in book.effects
        ),
        claims=book.claims + (claim,),
    )


def _replace_effect_state(
    book: VenueRecoveryBook,
    effect: BrokerEffect,
    state: BrokerEffectState,
    item: object,
) -> VenueRecoveryBook:
    updated = replace(effect, state=state)
    return _book_with_input(
        book,
        item,
        effects=tuple(
            updated if entry.effect_id == effect.effect_id else entry
            for entry in book.effects
        ),
    )


def _discover_leg(
    book: VenueRecoveryBook, item: DiscoverVenueLeg
) -> tuple[VenueRecoveryBook | None, VenueRecoveryDisposition]:
    effect = book.effect(item.effect_id)
    if effect is None or not _same_leg_scope(book.scope, item.leg_key):
        return None, VenueRecoveryDisposition.REFUSED
    current_owner = book.owner(item.leg_key)
    if current_owner is not None:
        if current_owner.effect_id != item.effect_id:
            return None, VenueRecoveryDisposition.CONFLICT
        if current_owner.observation_id == item.observation_id:
            return _book_with_input(book, item), VenueRecoveryDisposition.APPLIED
        return None, VenueRecoveryDisposition.CONFLICT
    if effect.state not in {
        BrokerEffectState.DISPATCH_CLAIMED,
        BrokerEffectState.ACKNOWLEDGED,
        BrokerEffectState.OUTCOME_UNKNOWN,
        BrokerEffectState.NEEDS_REVIEW,
    } and effect.acceptance_set_state not in {
        AcceptanceSetState.CLOSED,
        AcceptanceSetState.INVALIDATED,
    }:
        return None, VenueRecoveryDisposition.REFUSED

    owner = VenueIdentityOwner(item.leg_key, effect.scope, item.observation_id)
    attempt = VenueAttempt(
        leg_key=item.leg_key,
        status=VenueAttemptState.WORKING,
        pending_operation=None,
        cumulative_quantity=Quantity(0),
        last_observation_id=item.observation_id,
    )
    next_effect = effect
    disposition = VenueRecoveryDisposition.APPLIED
    if effect.acceptance_set_state is AcceptanceSetState.CLOSED:
        next_effect = replace(
            effect,
            state=(
                BrokerEffectState.NEEDS_REVIEW
                if effect.state is BrokerEffectState.OPERATOR_RECONCILED
                else effect.state
            ),
            acceptance_set_state=AcceptanceSetState.INVALIDATED,
            contradiction_evidence=effect.contradiction_evidence
            + (AcceptanceContradiction(item.leg_key, item.observation_id),),
        )
        disposition = VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    elif effect.acceptance_set_state is AcceptanceSetState.INVALIDATED:
        next_effect = replace(
            effect,
            contradiction_evidence=effect.contradiction_evidence
            + (AcceptanceContradiction(item.leg_key, item.observation_id),),
        )
    next_book = _book_with_input(
        book,
        item,
        effects=tuple(
            next_effect if entry.effect_id == item.effect_id else entry
            for entry in book.effects
        ),
        owners=book.owners + (owner,),
        active_attempts=book.active_attempts + (attempt,),
    )
    return next_book, disposition


def _observe_status(
    book: VenueRecoveryBook, item: ObserveVenueStatus
) -> VenueRecoveryBook | None:
    if not _same_leg_scope(book.scope, item.leg_key):
        return None
    attempt = book.active_attempt(item.leg_key)
    head = book.closure_head(item.leg_key)
    if item.status is VenueAttemptState.OPERATOR_RECONCILED:
        return None
    is_terminal = item.status in _TERMINAL_ATTEMPT_STATES
    if is_terminal != (
        item.closure_id is not None and item.evidence_reference is not None
    ):
        return None

    if attempt is not None:
        if item.cumulative_quantity.value < attempt.cumulative_quantity.value:
            return None
        if is_terminal:
            assert item.closure_id is not None
            assert item.evidence_reference is not None
            return _book_close_attempt(
                book,
                leg_key=item.leg_key,
                closure_id=item.closure_id,
                status=item.status,
                cumulative_quantity=Quantity(
                    _covered_cumulative(book, item.leg_key)
                ),
                observed_cumulative_quantity=item.cumulative_quantity,
                evidence_reference=item.evidence_reference,
                kind=VenueClosureKind.BROKER_TERMINAL,
                observation_id=item.observation_id,
                broker_terminal_state=item.status,
                source_input=item,
            )
        prior_rank = _NONTERMINAL_PRECEDENCE.get(attempt.status)
        next_rank = _NONTERMINAL_PRECEDENCE.get(item.status)
        if prior_rank is None or next_rank is None or next_rank < prior_rank:
            return None
        updated = replace(
            attempt,
            status=item.status,
            cumulative_quantity=item.cumulative_quantity,
            last_observation_id=item.observation_id,
        )
        return _book_with_input(
            book,
            item,
            active_attempts=tuple(
                updated if entry.leg_key == updated.leg_key else entry
                for entry in book.active_attempts
            ),
        )

    if head is None or not is_terminal:
        return None
    if (
        item.cumulative_quantity.value
        <= head.observed_cumulative_quantity.value
    ):
        return None
    assert item.closure_id is not None
    assert item.evidence_reference is not None
    return _book_close_attempt(
        book,
        leg_key=item.leg_key,
        closure_id=item.closure_id,
        status=item.status,
        cumulative_quantity=Quantity(_covered_cumulative(book, item.leg_key)),
        observed_cumulative_quantity=item.cumulative_quantity,
        evidence_reference=item.evidence_reference,
        kind=VenueClosureKind.BROKER_TERMINAL,
        observation_id=item.observation_id,
        broker_terminal_state=item.status,
        source_input=item,
    )


def _maybe_finalize_effect(
    book: VenueRecoveryBook,
    effect_id: EffectId,
    execution: ExecutionSnapshot,
) -> VenueRecoveryBook:
    """Close the recovery lifecycle only after its independent closure gates."""

    effect = book.effect(effect_id)
    if (
        effect is None
        or effect.state is not BrokerEffectState.NEEDS_REVIEW
        or effect.acceptance_set_state is not AcceptanceSetState.CLOSED
    ):
        return book
    if not book._execution_matches(execution, effect.scope.position_scope):
        return book
    unresolved_execution = (
        PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    if (
        execution.integrity & unresolved_execution
        or any(record.effect_id == effect_id for record in book.reconciliations)
        or any(
            record.position_scope == effect.scope.position_scope
            and not record.attribution_resolved
            for record in book.execution_reconciliations
        )
    ):
        return book
    owned_legs = [
        owner.leg_key for owner in book.owners if owner.effect_id == effect_id
    ]
    if not owned_legs:
        return book
    for leg_key in owned_legs:
        head = book.closure_head(leg_key)
        if head is None:
            return book
        covered_cumulative = _covered_cumulative(book, leg_key)
        if head.cumulative_quantity.value != covered_cumulative:
            return book
        if (
            head.status is VenueAttemptState.FILLED
            or head.broker_terminal_state is VenueAttemptState.FILLED
        ) and covered_cumulative != effect.scope.quantity.value:
            return book
    return _book_replace_effect(
        book,
        replace(effect, state=BrokerEffectState.OPERATOR_RECONCILED)
    )


def _close_acceptance_set(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: CloseAcceptanceSet,
) -> VenueRecoveryBook | None:
    effect = book.effect(item.effect_id)
    if effect is None or effect.acceptance_set_state is not AcceptanceSetState.OPEN:
        return None
    proof = item.proof
    if (
        proof.effect_scope != effect.scope
        or proof.claim_occurrence_id != effect.claim_occurrence_id
    ):
        return None
    if any(
        owner.effect_id == item.effect_id
        and book.active_attempt(owner.leg_key) is not None
        for owner in book.owners
    ):
        return None
    if proof.kind is AcceptanceProofKind.NEVER_DISPATCHED:
        if (
            effect.state is not BrokerEffectState.CANCELED_BEFORE_DISPATCH
            or effect.claim_occurrence_id is not None
            or any(claim.effect_id == item.effect_id for claim in book.claims)
        ):
            return None
    elif effect.claim_occurrence_id is None:
        return None
    closed = replace(
        effect,
        acceptance_set_state=AcceptanceSetState.CLOSED,
        acceptance_proof=proof,
    )
    closed_book = _book_with_input(
        book,
        item,
        effects=tuple(
            closed if entry.effect_id == item.effect_id else entry
            for entry in book.effects
        ),
    )
    return _maybe_finalize_effect(closed_book, item.effect_id, execution)


_VENUE_INPUTS = (
    RequestedEffect,
    RecordDispatchClaim,
    CancelBeforeDispatch,
    RecordTransportOutcome,
    RecoverClaimedEffect,
    DiscoverVenueLeg,
    RecordPendingVenueOperation,
    ObserveVenueStatus,
    CloseAcceptanceSet,
    CatchUpExecutionRegistry,
)


def _binding_matches_execution(
    binding: VenueExecutionBinding,
    execution: ExecutionSnapshot,
) -> bool:
    return (
        binding.position_scope == execution.position.scope
        and binding.position_commitment == execution.position.commitment
        and binding.root_heads_commitment == execution.root_heads.commitment
        and binding.integrity_bits == execution.integrity.value
    )


def _replace_execution_binding(
    bindings: tuple[VenueExecutionBinding, ...],
    execution: ExecutionSnapshot,
) -> tuple[VenueExecutionBinding, ...]:
    replacement = VenueExecutionBinding(
        position_scope=execution.position.scope,
        position_commitment=execution.position.commitment,
        root_heads_commitment=execution.root_heads.commitment,
        integrity_bits=execution.integrity.value,
    )
    return tuple(
        replacement if item.position_scope == replacement.position_scope else item
        for item in bindings
    )


def _apply_execution_registry_catch_up(
    book: VenueRecoveryBook,
    target: ExecutionSnapshot,
    item: CatchUpExecutionRegistry,
) -> VenueRecoveryTransition:
    """Apply one monotonic account-registry projection without replaying economics."""

    source = item.source_execution
    target_scope = target.position.scope
    source_scope = source.position.scope
    target_binding = book.execution_binding(target_scope)
    same_account = (
        target_scope.broker == source_scope.broker == book.scope.broker
        and target_scope.environment
        == source_scope.environment
        == book.scope.environment
        and target_scope.account == source_scope.account == book.scope.account
    )
    if not same_account:
        return _transition(book, target, VenueRecoveryDisposition.REFUSED)
    if (
        target_binding is None
        or not book._execution_symbol_matches(target, target_scope)
        or not source.seen_facts.has_prefix(
            target.seen_facts.count,
            target.seen_facts.commitment,
        )
        or book.execution_registry_commitment
        not in {
            target.seen_facts.commitment,
            source.seen_facts.commitment,
        }
        or any(
            source.seen_facts.observation_at(index).position_scope != source_scope
            for index in range(target.seen_facts.count, source.seen_facts.count)
        )
    ):
        return _transition(
            book,
            target,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        )

    replay = book._input_record(item.input_id)
    if replay is not None and replay.item != item:
        return _transition(book, target, VenueRecoveryDisposition.CONFLICT)

    source_binding = book.execution_binding(source_scope)
    source_binding_changed = (
        source_binding is not None
        and not _binding_matches_execution(source_binding, source)
    )
    if (
        book.execution_registry_commitment == source.seen_facts.commitment
        and source_binding_changed
    ):
        return _transition(
            book,
            target,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        )

    if source_scope == target_scope:
        next_execution = source
    else:
        try:
            next_execution = _project_execution_registry(target, source)
        except ValueError:
            return _transition(
                book,
                target,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            )

    if replay is not None:
        if not book._execution_matches(next_execution, target_scope):
            return _transition(
                book,
                target,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            )
        return _transition(
            book,
            next_execution,
            VenueRecoveryDisposition.EXACT_REPLAY,
        )

    if source.seen_facts.count == target.seen_facts.count:
        return _transition(book, target, VenueRecoveryDisposition.REFUSED)

    next_bindings = _replace_execution_binding(
        book.execution_bindings,
        next_execution,
    )
    prior_source_binding = source_binding or VenueExecutionBinding(
        position_scope=source_scope,
        position_commitment=source.position.commitment,
        root_heads_commitment=source.root_heads.commitment,
        integrity_bits=source.integrity.value,
    )
    if source_binding_changed:
        assert source_binding is not None
        next_bindings = _replace_execution_binding(next_bindings, source)
    registry_record = ExecutionRegistryReconciliationRecord(
        input_id=item.input_id,
        position_scope=source_scope,
        prior_registry_count=target.seen_facts.count,
        resulting_registry_count=source.seen_facts.count,
        prior_registry_commitment=target.seen_facts.commitment,
        resulting_registry_commitment=source.seen_facts.commitment,
        prior_position_commitment=prior_source_binding.position_commitment,
        resulting_position_commitment=source.position.commitment,
        prior_root_heads_commitment=prior_source_binding.root_heads_commitment,
        resulting_root_heads_commitment=source.root_heads.commitment,
        prior_integrity_bits=prior_source_binding.integrity_bits,
        resulting_integrity_bits=source.integrity.value,
        canonical_applied=True,
        attribution_resolved=not source_binding_changed,
        reason=(
            "account registry projection retained exact source attribution"
            if not source_binding_changed
            else "canonical source advanced before venue ownership attribution"
        ),
    )
    next_reconciliations = book.execution_reconciliations + (registry_record,)
    disposition = (
        VenueRecoveryDisposition.RECONCILIATION_REQUIRED
        if source_binding_changed
        else VenueRecoveryDisposition.APPLIED
    )

    next_book = _book_with_input(
        book,
        item,
        effects=(
            _demote_operator_effects_for_scope(book, source_scope)
            if source_binding_changed
            else book.effects
        ),
        execution_registry_commitment=source.seen_facts.commitment,
        execution_bindings=next_bindings,
        execution_reconciliations=next_reconciliations,
    )
    return _transition(next_book, next_execution, disposition)


def apply_venue_recovery_input(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> VenueRecoveryTransition:
    """Apply one exact immutable venue or recovery input without I/O."""

    _require("book", book, VenueRecoveryBook)
    _require("execution", execution, ExecutionSnapshot)
    input_id = _require_input_id("item.input_id", getattr(item, "input_id", None))
    if isinstance(item, CatchUpExecutionRegistry):
        return _apply_execution_registry_catch_up(book, execution, item)
    target_effect_id = getattr(item, "effect_id", None)
    if not isinstance(target_effect_id, EffectId):
        target_leg_key = getattr(item, "leg_key", None)
        owner = (
            book.owner(target_leg_key)
            if isinstance(target_leg_key, VenueLegKey)
            else None
        )
        target_effect_id = owner.effect_id if owner is not None else None
    if isinstance(target_effect_id, EffectId) and book.effect(target_effect_id):
        target_effect = book.effect(target_effect_id)
        assert target_effect is not None
        if not book._execution_matches(
            execution,
            target_effect.scope.position_scope,
        ):
            return _transition(
                book,
                execution,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            )
    if isinstance(item, RequestedEffect):
        position_scope = execution.position.scope
        if (
            position_scope.broker != book.scope.broker
            or position_scope.environment != book.scope.environment
            or position_scope.account != book.scope.account
            or position_scope.symbol_id != item.symbol_id
        ):
            return _transition(book, execution, VenueRecoveryDisposition.REFUSED)
        item_effect_scope = _effect_scope(book, item).position_scope
        existing_binding = book.execution_binding(item_effect_scope)
        if (
            execution.position.scope != item_effect_scope
            or (
                book.execution_registry_commitment is not None
                and book.execution_registry_commitment
                != execution.seen_facts.commitment
            )
            or (
                existing_binding is not None
                and not book._execution_matches(execution, item_effect_scope)
            )
        ):
            return _transition(
                book,
                execution,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            )
    replay = book._input_record(input_id)
    if replay is not None:
        disposition = (
            VenueRecoveryDisposition.EXACT_REPLAY
            if replay.item == item
            else VenueRecoveryDisposition.CONFLICT
        )
        return _transition(book, execution, disposition)

    if isinstance(item, RequestedEffect):
        next_book = _register_effect(book, execution, item)
        disposition = (
            VenueRecoveryDisposition.APPLIED
            if next_book is not None
            else VenueRecoveryDisposition.CONFLICT
        )
    elif isinstance(item, RecordDispatchClaim):
        effect = book.effect(item.effect_id)
        duplicate_claim_occurrence = any(
            claim.claim_occurrence_id == item.claim_occurrence_id
            for claim in book.claims
        )
        next_book = _record_claim(book, item)
        disposition = (
            VenueRecoveryDisposition.APPLIED
            if next_book is not None
            else (
                VenueRecoveryDisposition.CONFLICT
                if duplicate_claim_occurrence
                or (
                    effect is not None
                    and effect.state is BrokerEffectState.DISPATCH_CLAIMED
                    and effect.claim_occurrence_id is not None
                )
                else VenueRecoveryDisposition.REFUSED
            )
        )
    elif isinstance(item, CancelBeforeDispatch):
        effect = book.effect(item.effect_id)
        if (
            effect is not None
            and effect.state is BrokerEffectState.REQUESTED
            and effect.claim_occurrence_id is None
        ):
            next_book = _replace_effect_state(
                book, effect, BrokerEffectState.CANCELED_BEFORE_DISPATCH, item
            )
            disposition = VenueRecoveryDisposition.APPLIED
        else:
            next_book = None
            disposition = VenueRecoveryDisposition.REFUSED
    elif isinstance(item, RecordTransportOutcome):
        effect = book.effect(item.effect_id)
        allowed = {
            BrokerEffectState.DISPATCH_CLAIMED: {
                BrokerEffectState.ACKNOWLEDGED,
                BrokerEffectState.REJECTED,
                BrokerEffectState.OUTCOME_UNKNOWN,
            },
            BrokerEffectState.OUTCOME_UNKNOWN: {
                BrokerEffectState.ACKNOWLEDGED,
                BrokerEffectState.REJECTED,
                BrokerEffectState.NEEDS_REVIEW,
            },
        }
        if effect is not None and item.state in allowed.get(effect.state, set()):
            next_book = _maybe_finalize_effect(
                _replace_effect_state(book, effect, item.state, item),
                item.effect_id,
                execution,
            )
            disposition = VenueRecoveryDisposition.APPLIED
        else:
            next_book = None
            disposition = VenueRecoveryDisposition.REFUSED
    elif isinstance(item, RecoverClaimedEffect):
        effect = book.effect(item.effect_id)
        if effect is not None and effect.state is BrokerEffectState.DISPATCH_CLAIMED:
            next_book = _replace_effect_state(
                book, effect, BrokerEffectState.OUTCOME_UNKNOWN, item
            )
            disposition = VenueRecoveryDisposition.APPLIED
        else:
            next_book = None
            disposition = VenueRecoveryDisposition.REFUSED
    elif isinstance(item, DiscoverVenueLeg):
        next_book, disposition = _discover_leg(book, item)
    elif isinstance(item, RecordPendingVenueOperation):
        attempt = book.active_attempt(item.leg_key)
        if (
            attempt is None
            or item.operation is PendingVenueOperation.NONE
            or not _same_leg_scope(book.scope, item.leg_key)
        ):
            next_book = None
            disposition = VenueRecoveryDisposition.REFUSED
        else:
            updated = replace(attempt, pending_operation=item.operation)
            next_book = _book_with_input(
                book,
                item,
                active_attempts=tuple(
                    updated if entry.leg_key == updated.leg_key else entry
                    for entry in book.active_attempts
                ),
            )
            disposition = VenueRecoveryDisposition.APPLIED
    elif isinstance(item, ObserveVenueStatus):
        next_book = _observe_status(book, item)
        disposition = (
            VenueRecoveryDisposition.APPLIED
            if next_book is not None
            else VenueRecoveryDisposition.REFUSED
        )
    elif isinstance(item, CloseAcceptanceSet):
        next_book = _close_acceptance_set(book, execution, item)
        disposition = (
            VenueRecoveryDisposition.APPLIED
            if next_book is not None
            else VenueRecoveryDisposition.REFUSED
        )
    else:
        from .recovery import _apply_recovery_input

        return _apply_recovery_input(book, execution, item)

    return _transition(next_book or book, execution, disposition)


__all__ = [
    "AcceptanceProof",
    "AcceptanceProofKind",
    "AcceptanceSetState",
    "BrokerEffectState",
    "CatchUpExecutionRegistry",
    "CancelBeforeDispatch",
    "ClientIdentityBinding",
    "CloseAcceptanceSet",
    "DiscoverVenueLeg",
    "EffectKind",
    "ExecutionRegistryReconciliationRecord",
    "ObserveVenueStatus",
    "PendingVenueOperation",
    "RecordDispatchClaim",
    "RecordPendingVenueOperation",
    "RecordTransportOutcome",
    "RecoverClaimedEffect",
    "RequestedEffect",
    "VenueAttemptState",
    "VenueClosureKind",
    "VenueEffectScope",
    "VenueRecoveryBook",
    "VenueRecoveryDisposition",
    "VenueRecoveryTransition",
    "VenueScope",
    "VenueIntegrity",
    "VenueTerminalClosure",
    "apply_venue_recovery_input",
]
