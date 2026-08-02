"""Pure venue-effect ownership and recovery lifecycle semantic center.

The types in this module are immutable reducer inputs and compact current-state
records.  They perform no I/O and do not infer broker completeness.  Recovery
commands are lazily delegated to :mod:`app.execution_core.recovery` so both
economic and non-economic paths share one public transition seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from decimal import Decimal
from enum import Enum, IntFlag
from fractions import Fraction
from typing import TYPE_CHECKING, Any, Callable, Iterable, cast

from .fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionAuthority,
    ExecutionScope,
    ExecutionSide,
    FirstObservationClassification,
    HumanAttestedFillFact,
    PositionScope,
    _PersistentKeyMap,
    _PersistentSequence,
    _commit_parts,
    _encode_text,
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
    ExecutionFactKey,
    MandateId,
    RequestOccurrenceId,
    RootFillKey,
    SourceEventId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from .position import (
    ExecutionSnapshot,
    PositionIntegrity,
    _RECONCILIATION_GENESIS_HEAD,
    _bind_execution_reconciliation_cursor,
    _project_execution_registry,
    _require_execution_components,
)
from .values import Quantity

if TYPE_CHECKING:
    from .recovery import (
        HumanCoverage,
        ReconciliationRecord,
        RevisionReconciliationRecord,
        _BrokerCoverage,
    )


_BookEvolver = Callable[..., "VenueRecoveryBook"]
_TransitionFactory = Callable[..., "VenueRecoveryTransition"]


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
            head.quantity == fact.revised_quantity and head.price == fact.revised_price
        )
    return head.quantity.value == 0 and head.price == fact.reported_price


def _canonical_value_commitment(value: object) -> bytes:
    """Commit one bounded immutable value without recursive audit history."""

    value_type = type(value)
    type_name = _encode_text(f"{value_type.__module__}.{value_type.__qualname__}")
    if value is None:
        return _commit_parts(b"execution-core/canonical-none/v1")
    if value_type is bool:
        return _commit_parts(
            b"execution-core/canonical-bool/v1",
            b"1" if value else b"0",
        )
    if value_type is int:
        return _commit_parts(
            b"execution-core/canonical-int/v1",
            _encode_text(str(value)),
        )
    if value_type is str:
        return _commit_parts(
            b"execution-core/canonical-text/v1",
            _encode_text(cast(str, value)),
        )
    if value_type is bytes:
        return _commit_parts(
            b"execution-core/canonical-bytes/v1",
            cast(bytes, value),
        )
    if value_type is Decimal:
        decimal_value = cast(Decimal, value)
        numerator, denominator = decimal_value.as_integer_ratio()
        return _commit_parts(
            b"execution-core/canonical-decimal/v1",
            _encode_text(str(numerator)),
            _encode_text(str(denominator)),
        )
    if value_type is Fraction:
        fraction_value = cast(Fraction, value)
        return _commit_parts(
            b"execution-core/canonical-fraction/v1",
            _encode_text(str(fraction_value.numerator)),
            _encode_text(str(fraction_value.denominator)),
        )
    if isinstance(value, Enum):
        return _commit_parts(
            b"execution-core/canonical-enum/v1",
            type_name,
            _canonical_value_commitment(value.value),
        )
    if value_type is ExecutionSnapshot:
        snapshot = cast(ExecutionSnapshot, value)
        return _commit_parts(
            b"execution-core/canonical-execution-snapshot/v1",
            _canonical_value_commitment(snapshot.position.scope),
            snapshot.commitment,
            snapshot.position.commitment,
            snapshot.root_heads.commitment,
            _encode_text(str(snapshot.integrity.value)),
            _encode_text(str(snapshot.seen_facts.count)),
            snapshot.seen_facts.commitment,
        )
    if is_dataclass(value) and not isinstance(value, type):
        parts: list[bytes] = [type_name]
        for item_field in fields(value):
            parts.extend(
                (
                    _encode_text(item_field.name),
                    _canonical_value_commitment(getattr(value, item_field.name)),
                )
            )
        return _commit_parts(b"execution-core/canonical-dataclass/v1", *parts)
    raise TypeError(f"unsupported canonical audit value: {value_type.__qualname__}")


def _input_command_identity(
    item: object,
    *,
    include_input_id: bool,
) -> tuple[bytes, ...]:
    """Return one bounded, type-exact command identity."""

    from .recovery import (
        IngestHumanAttestedFill,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
        ReleaseVenueLeg,
    )

    admitted_types = {
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
        IngestHumanAttestedFill,
        ReleaseVenueLeg,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
    }
    if type(item) not in admitted_types:
        raise TypeError("item must be an exact venue-recovery command type")
    identity: list[bytes] = [
        _encode_text(f"{type(item).__module__}.{type(item).__qualname__}")
    ]
    for item_field in fields(cast(Any, item)):
        if item_field.name == "input_id" and not include_input_id:
            continue
        identity.extend(
            (
                _encode_text(item_field.name),
                _canonical_value_commitment(getattr(item, item_field.name)),
            )
        )
    return tuple(identity)


def _input_commands_equal(
    left: object,
    right: object,
    *,
    include_input_id: bool,
) -> bool:
    """Compare exact command payloads through bounded canonical identities."""

    return type(left) is type(right) and _input_command_identity(
        left,
        include_input_id=include_input_id,
    ) == _input_command_identity(right, include_input_id=include_input_id)


def _input_record_commitment(record: VenueInputRecord) -> bytes:
    return _commit_parts(
        b"execution-core/venue-input-record/v2",
        _canonical_value_commitment(record.input_id),
        _canonical_value_commitment(record.semantic_alias_of),
        *_input_command_identity(record.item, include_input_id=True),
    )


def _closure_commitment(closure: VenueTerminalClosure) -> bytes:
    return _commit_parts(
        b"execution-core/venue-terminal-closure/v2",
        _canonical_value_commitment(closure),
    )


def _input_index_key(input_id: VenueInputId) -> bytes:
    return _commit_parts(
        b"execution-core/venue-input-index-key/v1",
        _encode_text(input_id.value),
    )


def _closure_index_key(closure_id: ClosureId) -> bytes:
    return _commit_parts(
        b"execution-core/venue-closure-index-key/v1",
        _encode_text(closure_id.value),
    )


def _fact_index_key(fact_key: ExecutionFactKey) -> bytes:
    return _commit_parts(
        b"execution-core/venue-fact-input-index-key/v1",
        _encode_text(fact_key.broker.value),
        _encode_text(fact_key.environment.value),
        _encode_text(fact_key.account.value),
        _encode_text(fact_key.source_event_id.value),
    )


def _leg_index_key(leg_key: VenueLegKey) -> bytes:
    return _commit_parts(
        b"execution-core/venue-leg-index-key/v1",
        _encode_text(leg_key.broker.value),
        _encode_text(leg_key.environment.value),
        _encode_text(leg_key.account.value),
        _encode_text(leg_key.order_id.value),
    )


def _position_scope_index_key(position_scope: PositionScope) -> bytes:
    return _commit_parts(
        b"execution-core/venue-position-scope-index-key/v1",
        _encode_text(position_scope.broker.value),
        _encode_text(position_scope.environment.value),
        _encode_text(position_scope.account.value),
        _encode_text(position_scope.symbol_id.value),
    )


def _coverage_root_index_key(root_key: RootFillKey) -> bytes:
    return _commit_parts(
        b"execution-core/venue-coverage-root-index-key/v1",
        _encode_text(root_key.broker.value),
        _encode_text(root_key.environment.value),
        _encode_text(root_key.account.value),
        _encode_text(root_key.root_fill_id.value),
    )


def _coverage_interval_index_key(
    leg_key: VenueLegKey,
    prior: int,
    resulting: int,
) -> bytes:
    return _commit_parts(
        b"execution-core/venue-coverage-interval-index-key/v1",
        _leg_index_key(leg_key),
        _encode_text(str(prior)),
        _encode_text(str(resulting)),
    )


def _effect_index_key(effect_id: EffectId) -> bytes:
    return _commit_parts(
        b"execution-core/venue-effect-index-key/v1",
        _encode_text(effect_id.value),
    )


def _request_occurrence_index_key(
    request_occurrence_id: RequestOccurrenceId,
) -> bytes:
    return _commit_parts(
        b"execution-core/venue-request-occurrence-index-key/v1",
        _encode_text(request_occurrence_id.value),
    )


def _client_order_index_key(client_order_id: ClientOrderId) -> bytes:
    return _commit_parts(
        b"execution-core/venue-client-order-index-key/v1",
        _encode_text(client_order_id.value),
    )


def _claim_occurrence_index_key(
    claim_occurrence_id: ClaimOccurrenceId,
) -> bytes:
    return _commit_parts(
        b"execution-core/venue-claim-occurrence-index-key/v1",
        _encode_text(claim_occurrence_id.value),
    )


def _execution_scope_index_key(execution_scope: ExecutionScope) -> bytes:
    return _commit_parts(
        b"execution-core/venue-execution-scope-index-key/v1",
        _position_scope_index_key(execution_scope.position_scope),
        _encode_text(execution_scope.order_id.value),
        _encode_text(execution_scope.side.value),
    )


def _semantic_input_key(item: object) -> bytes:
    """Return the stable semantic key for one command, excluding its input id."""

    _require_input_id("input_id", getattr(item, "input_id", None))
    return _commit_parts(
        b"execution-core/venue-semantic-input-key/v2",
        *_input_command_identity(item, include_input_id=False),
    )


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
        if type(self.position_scope) is not PositionScope:
            raise TypeError("position_scope must be the exact PositionScope type")
        _require_digest("position_commitment", self.position_commitment)
        _require_digest("root_heads_commitment", self.root_heads_commitment)
        if type(self.integrity_bits) is not int or self.integrity_bits < 0:
            raise ValueError("integrity_bits must be a non-negative exact integer")


@dataclass(frozen=True, slots=True)
class VenueExecutionCheckpoint:
    """Compact exact symbol checkpoint at one account-registry point."""

    position_scope: PositionScope
    registry_count: int
    registry_commitment: bytes
    position_commitment: bytes
    root_heads_commitment: bytes
    integrity_bits: int
    account_reconciliation_required: bool
    reconciliation_transition_count: int
    reconciliation_transition_head: bytes

    def __post_init__(self) -> None:
        if type(self.position_scope) is not PositionScope:
            raise TypeError("position_scope must be the exact PositionScope type")
        if type(self.registry_count) is not int or self.registry_count < 0:
            raise ValueError("registry_count must be a non-negative exact integer")
        for name in (
            "registry_commitment",
            "position_commitment",
            "root_heads_commitment",
        ):
            _require_digest(name, getattr(self, name))
        if type(self.integrity_bits) is not int or self.integrity_bits < 0:
            raise ValueError("integrity_bits must be a non-negative exact integer")
        if type(self.account_reconciliation_required) is not bool:
            raise TypeError("account_reconciliation_required must be bool")
        if (
            type(self.reconciliation_transition_count) is not int
            or self.reconciliation_transition_count < 0
        ):
            raise ValueError(
                "reconciliation_transition_count must be a non-negative exact integer"
            )
        _require_digest(
            "reconciliation_transition_head",
            self.reconciliation_transition_head,
        )

    @classmethod
    def from_execution(cls, execution: ExecutionSnapshot) -> VenueExecutionCheckpoint:
        if type(execution) is not ExecutionSnapshot:
            raise TypeError("execution must be the exact ExecutionSnapshot type")
        _require_execution_components(
            execution.position,
            execution.integrity,
            execution.root_heads,
            execution.seen_facts,
        )
        return cls(
            position_scope=execution.position.scope,
            registry_count=execution.seen_facts.count,
            registry_commitment=execution.seen_facts.commitment,
            position_commitment=execution.position.commitment,
            root_heads_commitment=execution.root_heads.commitment,
            integrity_bits=execution.integrity.value,
            account_reconciliation_required=(
                execution.account_reconciliation_required
            ),
            reconciliation_transition_count=(
                execution.reconciliation_transition_count
            ),
            reconciliation_transition_head=(
                execution.reconciliation_transition_head
            ),
        )

    @property
    def binding(self) -> VenueExecutionBinding:
        return VenueExecutionBinding(
            position_scope=self.position_scope,
            position_commitment=self.position_commitment,
            root_heads_commitment=self.root_heads_commitment,
            integrity_bits=self.integrity_bits,
        )


@dataclass(frozen=True, slots=True)
class CatchUpExecutionRegistry:
    """Project one proven monotonic account registry into a venue checkpoint."""

    input_id: VenueInputId
    target_checkpoint: VenueExecutionCheckpoint
    prior_account_registry_count: int
    prior_account_registry_commitment: bytes
    prior_source_binding: VenueExecutionBinding | None
    source_execution: ExecutionSnapshot

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        if type(self.target_checkpoint) is not VenueExecutionCheckpoint:
            raise TypeError(
                "target_checkpoint must be the exact VenueExecutionCheckpoint type"
            )
        if (
            type(self.prior_account_registry_count) is not int
            or self.prior_account_registry_count < 0
        ):
            raise ValueError(
                "prior_account_registry_count must be a non-negative exact integer"
            )
        _require_digest(
            "prior_account_registry_commitment",
            self.prior_account_registry_commitment,
        )
        if (
            self.prior_source_binding is not None
            and type(self.prior_source_binding) is not VenueExecutionBinding
        ):
            raise TypeError(
                "prior_source_binding must be the exact VenueExecutionBinding type"
            )
        if type(self.source_execution) is not ExecutionSnapshot:
            raise TypeError("source_execution must be the exact ExecutionSnapshot type")

    @property
    def target_scope(self) -> PositionScope:
        return self.target_checkpoint.position_scope


def _catch_up_input_commitment(item: CatchUpExecutionRegistry) -> bytes:
    if type(item) is not CatchUpExecutionRegistry:
        raise TypeError("item must be the exact CatchUpExecutionRegistry type")
    return _commit_parts(
        b"execution-core/catch-up-input/v1",
        *_input_command_identity(item, include_input_id=True),
    )


def _validate_registry_outcome_common(
    *,
    input_id: VenueInputId,
    command_commitment: bytes,
    target_checkpoint: VenueExecutionCheckpoint,
    resulting_registry_count: int,
    resulting_registry_commitment: bytes,
    reason: str,
) -> None:
    _require("input_id", input_id, VenueInputId)
    _require_digest("command_commitment", command_commitment)
    if type(target_checkpoint) is not VenueExecutionCheckpoint:
        raise TypeError(
            "target_checkpoint must be the exact VenueExecutionCheckpoint type"
        )
    if (
        type(resulting_registry_count) is not int
        or resulting_registry_count <= target_checkpoint.registry_count
    ):
        raise ValueError(
            "resulting_registry_count must strictly exceed the target checkpoint"
        )
    _require_digest("resulting_registry_commitment", resulting_registry_commitment)
    if type(reason) is not str or not reason.strip():
        raise ValueError("reason must be a nonblank string")


@dataclass(frozen=True, slots=True)
class _ResolvedRegistryProjectionOutcome:
    """Registry-only target projection whose account truth was already canonical."""

    input_id: VenueInputId
    command_commitment: bytes
    target_checkpoint: VenueExecutionCheckpoint
    source_binding: VenueExecutionBinding
    resulting_registry_count: int
    resulting_registry_commitment: bytes
    reason: str

    def __post_init__(self) -> None:
        _validate_registry_outcome_common(
            input_id=self.input_id,
            command_commitment=self.command_commitment,
            target_checkpoint=self.target_checkpoint,
            resulting_registry_count=self.resulting_registry_count,
            resulting_registry_commitment=self.resulting_registry_commitment,
            reason=self.reason,
        )
        if type(self.source_binding) is not VenueExecutionBinding:
            raise TypeError("source_binding must be the exact VenueExecutionBinding type")

    @property
    def canonical_applied(self) -> bool:
        return True

    @property
    def attribution_resolved(self) -> bool:
        return True

    @property
    def position_scope(self) -> PositionScope:
        return self.target_checkpoint.position_scope

    @property
    def prior_registry_count(self) -> int:
        return self.target_checkpoint.registry_count

    @property
    def prior_registry_commitment(self) -> bytes:
        return self.target_checkpoint.registry_commitment

    @property
    def prior_position_commitment(self) -> bytes:
        return self.target_checkpoint.position_commitment

    @property
    def resulting_position_commitment(self) -> bytes:
        return self.target_checkpoint.position_commitment

    @property
    def prior_root_heads_commitment(self) -> bytes:
        return self.target_checkpoint.root_heads_commitment

    @property
    def resulting_root_heads_commitment(self) -> bytes:
        return self.target_checkpoint.root_heads_commitment

    @property
    def prior_integrity_bits(self) -> int:
        return self.target_checkpoint.integrity_bits

    @property
    def resulting_integrity_bits(self) -> int:
        return self.target_checkpoint.integrity_bits


@dataclass(frozen=True, slots=True)
class _UnresolvedRegistryAdvanceOutcome:
    """New source-symbol truth admitted without venue attribution."""

    input_id: VenueInputId
    command_commitment: bytes
    target_checkpoint: VenueExecutionCheckpoint
    prior_account_registry_count: int
    prior_account_registry_commitment: bytes
    prior_source_binding: VenueExecutionBinding
    resulting_source_binding: VenueExecutionBinding
    resulting_registry_count: int
    resulting_registry_commitment: bytes
    reason: str

    def __post_init__(self) -> None:
        _validate_registry_outcome_common(
            input_id=self.input_id,
            command_commitment=self.command_commitment,
            target_checkpoint=self.target_checkpoint,
            resulting_registry_count=self.resulting_registry_count,
            resulting_registry_commitment=self.resulting_registry_commitment,
            reason=self.reason,
        )
        if (
            type(self.prior_account_registry_count) is not int
            or self.prior_account_registry_count < 0
            or self.prior_account_registry_count >= self.resulting_registry_count
        ):
            raise ValueError(
                "prior account registry must be a strict prefix of the result"
            )
        _require_digest(
            "prior_account_registry_commitment",
            self.prior_account_registry_commitment,
        )
        if type(self.prior_source_binding) is not VenueExecutionBinding:
            raise TypeError(
                "prior_source_binding must be the exact VenueExecutionBinding type"
            )
        if type(self.resulting_source_binding) is not VenueExecutionBinding:
            raise TypeError(
                "resulting_source_binding must be the exact VenueExecutionBinding type"
            )
        if (
            self.prior_source_binding.position_scope
            != self.resulting_source_binding.position_scope
        ):
            raise ValueError("source advance must retain one exact position scope")

    @property
    def canonical_applied(self) -> bool:
        return True

    @property
    def attribution_resolved(self) -> bool:
        return False

    @property
    def position_scope(self) -> PositionScope:
        return self.resulting_source_binding.position_scope

    @property
    def prior_registry_count(self) -> int:
        return self.prior_account_registry_count

    @property
    def prior_registry_commitment(self) -> bytes:
        return self.prior_account_registry_commitment

    @property
    def prior_position_commitment(self) -> bytes:
        return self.prior_source_binding.position_commitment

    @property
    def resulting_position_commitment(self) -> bytes:
        return self.resulting_source_binding.position_commitment

    @property
    def prior_root_heads_commitment(self) -> bytes:
        return self.prior_source_binding.root_heads_commitment

    @property
    def resulting_root_heads_commitment(self) -> bytes:
        return self.resulting_source_binding.root_heads_commitment

    @property
    def prior_integrity_bits(self) -> int:
        return self.prior_source_binding.integrity_bits

    @property
    def resulting_integrity_bits(self) -> int:
        return self.resulting_source_binding.integrity_bits


ExecutionRegistryReconciliationRecord = (
    _ResolvedRegistryProjectionOutcome | _UnresolvedRegistryAdvanceOutcome
)


class _RegistryTransitionKind(Enum):
    RESOLVED_TARGET_PROJECTION = "RESOLVED_TARGET_PROJECTION"
    UNRESOLVED_SOURCE_ADVANCE = "UNRESOLVED_SOURCE_ADVANCE"


@dataclass(frozen=True, slots=True)
class _RegistryTransitionProof:
    """Opaque predecessor-linked proof of one admitted CatchUp transition."""

    ordinal: int
    predecessor_commitment: bytes | None
    venue_scope: VenueScope
    input_id: VenueInputId
    command_commitment: bytes
    outcome_commitment: bytes
    kind: _RegistryTransitionKind
    prior_account_registry_count: int
    prior_account_registry_commitment: bytes
    resulting_registry_count: int
    resulting_registry_commitment: bytes
    prior_target_checkpoint: VenueExecutionCheckpoint
    resulting_target_binding: VenueExecutionBinding
    prior_source_binding: VenueExecutionBinding
    resulting_source_binding: VenueExecutionBinding

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/registry-transition-proof/v1",
            _canonical_value_commitment(self),
        )


def _registry_transition_proof_for(
    *,
    ordinal: int,
    predecessor_commitment: bytes | None,
    venue_scope: VenueScope,
    item: CatchUpExecutionRegistry,
    outcome: ExecutionRegistryReconciliationRecord,
) -> _RegistryTransitionProof:
    if type(venue_scope) is not VenueScope:
        raise TypeError("venue_scope must be the exact VenueScope type")
    if type(item) is not CatchUpExecutionRegistry:
        raise TypeError("registry transition requires an exact CatchUp command")
    if item.prior_source_binding is None:
        raise ValueError("admitted CatchUp transition requires a prior source binding")
    if type(outcome) is _ResolvedRegistryProjectionOutcome:
        kind = _RegistryTransitionKind.RESOLVED_TARGET_PROJECTION
        resulting_source_binding = outcome.source_binding
        if (
            item.prior_account_registry_count != outcome.resulting_registry_count
            or item.prior_account_registry_commitment
            != outcome.resulting_registry_commitment
            or item.prior_source_binding != resulting_source_binding
        ):
            raise ValueError("resolved projection contradicts its exact prior heads")
        resulting_target_binding = item.target_checkpoint.binding
    elif type(outcome) is _UnresolvedRegistryAdvanceOutcome:
        kind = _RegistryTransitionKind.UNRESOLVED_SOURCE_ADVANCE
        resulting_source_binding = outcome.resulting_source_binding
        if (
            item.prior_account_registry_count
            != outcome.prior_account_registry_count
            or item.prior_account_registry_commitment
            != outcome.prior_account_registry_commitment
            or item.prior_source_binding != outcome.prior_source_binding
        ):
            raise ValueError("source advance contradicts its exact prior heads")
        resulting_target_binding = (
            resulting_source_binding
            if item.target_scope == resulting_source_binding.position_scope
            else item.target_checkpoint.binding
        )
    else:
        raise TypeError("registry transition outcome type is not admitted")
    return _RegistryTransitionProof(
        ordinal=ordinal,
        predecessor_commitment=predecessor_commitment,
        venue_scope=venue_scope,
        input_id=item.input_id,
        command_commitment=_catch_up_input_commitment(item),
        outcome_commitment=_execution_reconciliation_value_commitment(outcome),
        kind=kind,
        prior_account_registry_count=item.prior_account_registry_count,
        prior_account_registry_commitment=item.prior_account_registry_commitment,
        resulting_registry_count=outcome.resulting_registry_count,
        resulting_registry_commitment=outcome.resulting_registry_commitment,
        prior_target_checkpoint=item.target_checkpoint,
        resulting_target_binding=resulting_target_binding,
        prior_source_binding=item.prior_source_binding,
        resulting_source_binding=resulting_source_binding,
    )


def _validate_registry_transition_chain(
    proofs: tuple[_RegistryTransitionProof, ...],
    inputs: tuple[VenueInputRecord, ...],
    outcomes: tuple[ExecutionRegistryReconciliationRecord, ...],
    head_commitment: bytes | None,
    venue_scope: VenueScope,
) -> None:
    input_by_id = {record.input_id: record.item for record in inputs}
    catch_up_input_ids = tuple(
        record.input_id
        for record in inputs
        if type(record.item) is CatchUpExecutionRegistry
    )
    if catch_up_input_ids != tuple(outcome.input_id for outcome in outcomes):
        raise ValueError("CatchUp input order contradicts registry outcomes")
    if len(proofs) != len(outcomes):
        raise ValueError("registry transition chain length contradicts outcomes")
    predecessor: bytes | None = None
    prior_result_count = -1
    prior_result_commitment: bytes | None = None
    for ordinal, (proof, outcome) in enumerate(zip(proofs, outcomes), start=1):
        if type(proof) is not _RegistryTransitionProof:
            raise TypeError("registry transition proof type is not admitted")
        item = input_by_id.get(outcome.input_id)
        if type(item) is not CatchUpExecutionRegistry:
            raise ValueError("registry transition lacks its exact CatchUp input")
        expected = _registry_transition_proof_for(
            ordinal=ordinal,
            predecessor_commitment=predecessor,
            venue_scope=venue_scope,
            item=cast(CatchUpExecutionRegistry, item),
            outcome=outcome,
        )
        if proof != expected:
            raise ValueError(
                "registry transition chain contradicts its predecessor or outcome"
            )
        if outcome.resulting_registry_count < prior_result_count or (
            outcome.resulting_registry_count == prior_result_count
            and prior_result_commitment is not None
            and outcome.resulting_registry_commitment != prior_result_commitment
        ):
            raise ValueError("registry transition order regresses its account head")
        prior_result_count = outcome.resulting_registry_count
        prior_result_commitment = outcome.resulting_registry_commitment
        predecessor = proof.commitment
    if predecessor != head_commitment:
        raise ValueError("registry transition chain head does not close exactly")


@dataclass(frozen=True, slots=True, init=False)
class VenueRecoveryTransition:
    book: VenueRecoveryBook
    execution: ExecutionSnapshot
    disposition: VenueRecoveryDisposition
    quantity_delta: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError(
            "VenueRecoveryTransition is opaque and reducer-constructed only"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("VenueRecoveryTransition cannot be subclassed")


@dataclass(frozen=True, slots=True)
class _CoverageProvenance:
    """Persistent covered-root proof paired to one exact symbol root state."""

    roots: _PersistentKeyMap[bytes]
    root_heads_commitment: bytes | None

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-coverage-provenance/v1",
            self.roots.commitment,
            (
                self.root_heads_commitment
                if self.root_heads_commitment is not None
                else _commit_parts(
                    b"execution-core/venue-coverage-provenance/unbound/v1"
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class _CoverageLegCurrent:
    frontier: int = 0
    canonical_total: int = 0
    tail_root_key: RootFillKey | None = None
    inexact_broker_count: int = 0

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-coverage-leg-current/v1",
            _encode_text(str(self.frontier)),
            _encode_text(str(self.canonical_total)),
            (
                _coverage_root_index_key(self.tail_root_key)
                if self.tail_root_key is not None
                else _commit_parts(b"execution-core/coverage-tail-root/none/v1")
            ),
            _encode_text(str(self.inexact_broker_count)),
        )


@dataclass(frozen=True, slots=True)
class _EffectCurrent:
    effect: BrokerEffect
    operator_epoch: int | None = None
    account_epoch: int | None = None

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-effect-current/v2",
            _commit_parts(
                b"execution-core/venue-effect-value/v1",
                _canonical_value_commitment(self.effect.scope),
                _canonical_value_commitment(self.effect.state),
                _canonical_value_commitment(self.effect.acceptance_set_state),
                _canonical_value_commitment(self.effect.claim_occurrence_id),
                _canonical_value_commitment(self.effect.acceptance_proof),
            ),
            _canonical_value_commitment(self.operator_epoch),
            _canonical_value_commitment(self.account_epoch),
        )


@dataclass(frozen=True, slots=True)
class _LegCurrent:
    attempt: VenueAttempt | None

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-leg-current/v1",
            _canonical_value_commitment(self.attempt),
        )


@dataclass(frozen=True, slots=True)
class _EffectLegSummary:
    owner_count: int = 0
    active_count: int = 0
    finalization_ready_count: int = 0

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-effect-leg-summary/v1",
            _encode_text(str(self.owner_count)),
            _encode_text(str(self.active_count)),
            _encode_text(str(self.finalization_ready_count)),
        )


@dataclass(frozen=True, slots=True, init=False)
class VenueRecoveryBook:
    """Immutable compact venue checkpoint plus append-only proof material."""

    scope: VenueScope
    _effect_order: _PersistentSequence[EffectId] = field(
        default_factory=_PersistentSequence.empty
    )
    _effect_by_id: _PersistentKeyMap[_EffectCurrent] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _effect_by_request_occurrence: _PersistentKeyMap[EffectId] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _effect_by_client_order: _PersistentKeyMap[EffectId] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _authority_epoch_by_scope: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _account_authority_epoch: int = 0
    _contradiction_order_by_effect: _PersistentKeyMap[
        _PersistentSequence[AcceptanceContradiction]
    ] = field(default_factory=_PersistentKeyMap.empty)
    _claim_order: _PersistentSequence[EffectId] = field(
        default_factory=_PersistentSequence.empty
    )
    _claim_by_effect: _PersistentKeyMap[DispatchClaim] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _claim_by_occurrence: _PersistentKeyMap[EffectId] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _owner_order: _PersistentSequence[VenueLegKey] = field(
        default_factory=_PersistentSequence.empty
    )
    _owner_by_leg: _PersistentKeyMap[VenueIdentityOwner] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _leg_current_by_leg: _PersistentKeyMap[_LegCurrent] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _leg_summary_by_effect: _PersistentKeyMap[_EffectLegSummary] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _reconciliation_count_by_effect: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _closure_ledger: _PersistentSequence[VenueTerminalClosure] = field(
        default_factory=_PersistentSequence.empty
    )
    _closure_by_id: _PersistentKeyMap[VenueTerminalClosure] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _closure_head_by_leg: _PersistentKeyMap[VenueTerminalClosure] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _input_ledger: _PersistentSequence[VenueInputRecord] = field(
        default_factory=_PersistentSequence.empty
    )
    _input_by_id: _PersistentKeyMap[VenueInputRecord] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _direct_input_by_semantic: _PersistentKeyMap[VenueInputRecord] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _first_input_by_fact: _PersistentKeyMap[VenueInputRecord] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _economic_high_water_by_leg: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _human_coverage_ledger: _PersistentSequence[HumanCoverage] = field(
        default_factory=_PersistentSequence.empty
    )
    _human_coverage_by_root: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _broker_coverage_ledger: _PersistentSequence[_BrokerCoverage] = field(
        default_factory=_PersistentSequence.empty
    )
    _broker_coverage_by_root: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _coverage_provenance_by_scope: _PersistentKeyMap[_CoverageProvenance] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _coverage_current_by_leg: _PersistentKeyMap[_CoverageLegCurrent] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _coverage_total_by_effect: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _attributed_broker_root_count_by_scope: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _human_interval_index: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _human_broker_fact_index: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _reconciliation_ledger: _PersistentSequence[
        ReconciliationRecord | RevisionReconciliationRecord
    ] = field(default_factory=_PersistentSequence.empty)
    _reconciliation_by_input: _PersistentKeyMap[
        ReconciliationRecord | RevisionReconciliationRecord
    ] = field(default_factory=_PersistentKeyMap.empty)
    _unresolved_reconciliation_count_by_leg: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _canonical_revision_count_by_leg: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _execution_reconciliation_ledger: _PersistentSequence[
        ExecutionRegistryReconciliationRecord
    ] = field(default_factory=_PersistentSequence.empty)
    _execution_reconciliation_by_input: _PersistentKeyMap[
        ExecutionRegistryReconciliationRecord
    ] = field(default_factory=_PersistentKeyMap.empty)
    _registry_transition_ledger: _PersistentSequence[
        _RegistryTransitionProof
    ] = field(default_factory=_PersistentSequence.empty)
    _registry_transition_head_commitment: bytes | None = None
    _unresolved_execution_reconciliation_count_by_scope: _PersistentKeyMap[int] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _unresolved_account_execution_reconciliation_count: int = 0
    execution_registry_count: int | None = None
    execution_registry_commitment: bytes | None = None
    _binding_order: _PersistentSequence[PositionScope] = field(
        default_factory=_PersistentSequence.empty
    )
    _binding_by_scope: _PersistentKeyMap[VenueExecutionBinding] = field(
        default_factory=_PersistentKeyMap.empty
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError(
            "VenueRecoveryBook is opaque; use empty() and the verified reducer"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("VenueRecoveryBook is opaque and cannot be subclassed")

    def _authority_epoch(self, position_scope: PositionScope) -> int:
        retained = self._authority_epoch_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        return 0 if retained is None else retained

    def _effective_effect(self, current: _EffectCurrent) -> BrokerEffect:
        effect = current.effect
        if (
            effect.state is BrokerEffectState.OPERATOR_RECONCILED
            and (
                current.operator_epoch
                != self._authority_epoch(effect.scope.position_scope)
                or current.account_epoch != self._account_authority_epoch
            )
        ):
            return replace(effect, state=BrokerEffectState.NEEDS_REVIEW)
        return effect

    def _current_effect(self, effect_id: EffectId) -> BrokerEffect | None:
        current = self._effect_by_id.get(_effect_index_key(effect_id))
        return None if current is None else self._effective_effect(current)

    def _contradictions_for(
        self,
        effect_id: EffectId,
    ) -> tuple[AcceptanceContradiction, ...]:
        retained = self._contradiction_order_by_effect.get(_effect_index_key(effect_id))
        return () if retained is None else retained.to_tuple()

    @property
    def effects(self) -> tuple[BrokerEffect, ...]:
        """Materialize current effects only for explicit slow audit consumers."""

        materialized: list[BrokerEffect] = []
        for index in range(self._effect_order.length):
            effect_id = self._effect_order.get(index)
            current = self._effect_by_id.get(_effect_index_key(effect_id))
            if current is None:
                raise RuntimeError("effect order is missing its current value")
            materialized.append(
                replace(
                    self._effective_effect(current),
                    contradiction_evidence=self._contradictions_for(effect_id),
                )
            )
        return tuple(materialized)

    @property
    def claims(self) -> tuple[DispatchClaim, ...]:
        """Materialize immutable claims only for explicit slow audit consumers."""

        materialized: list[DispatchClaim] = []
        for index in range(self._claim_order.length):
            effect_id = self._claim_order.get(index)
            claim = self._claim_by_effect.get(_effect_index_key(effect_id))
            if claim is None:
                raise RuntimeError("claim order is missing its retained value")
            materialized.append(claim)
        return tuple(materialized)

    @property
    def owners(self) -> tuple[VenueIdentityOwner, ...]:
        """Materialize immutable owners only for explicit slow audit consumers."""

        materialized: list[VenueIdentityOwner] = []
        for index in range(self._owner_order.length):
            leg_key = self._owner_order.get(index)
            owner = self._owner_by_leg.get(_leg_index_key(leg_key))
            if owner is None:
                raise RuntimeError("owner order is missing its retained value")
            materialized.append(owner)
        return tuple(materialized)

    @property
    def active_attempts(self) -> tuple[VenueAttempt, ...]:
        """Materialize active leg state only for explicit slow audit consumers."""

        materialized: list[VenueAttempt] = []
        for index in range(self._owner_order.length):
            leg_key = self._owner_order.get(index)
            current = self._leg_current_by_leg.get(_leg_index_key(leg_key))
            if current is None:
                raise RuntimeError("owner is missing its current leg state")
            if current.attempt is not None:
                materialized.append(current.attempt)
        return tuple(materialized)

    @property
    def closure_heads(self) -> tuple[VenueTerminalClosure, ...]:
        """Materialize current closure heads only for explicit slow audit consumers."""

        materialized: list[VenueTerminalClosure] = []
        for index in range(self._owner_order.length):
            leg_key = self._owner_order.get(index)
            head = self._closure_head_by_leg.get(_leg_index_key(leg_key))
            if head is not None:
                materialized.append(head)
        return tuple(materialized)

    @property
    def execution_bindings(self) -> tuple[VenueExecutionBinding, ...]:
        """Materialize symbol bindings only for explicit slow audit consumers."""

        materialized: list[VenueExecutionBinding] = []
        for index in range(self._binding_order.length):
            position_scope = self._binding_order.get(index)
            binding = self._binding_by_scope.get(
                _position_scope_index_key(position_scope)
            )
            if binding is None:
                raise RuntimeError("binding order is missing its retained value")
            materialized.append(binding)
        return tuple(materialized)

    @property
    def closure_history(self) -> tuple[VenueTerminalClosure, ...]:
        """Materialize terminal history only for explicit slow audit consumers."""

        return self._closure_ledger.to_tuple()

    @property
    def input_records(self) -> tuple[VenueInputRecord, ...]:
        """Materialize input history only for explicit slow audit consumers."""

        return self._input_ledger.to_tuple()

    @property
    def human_coverages(self) -> tuple[HumanCoverage, ...]:
        """Materialize human coverage only for explicit slow audit consumers."""

        return self._human_coverage_ledger.to_tuple()

    @property
    def broker_coverages(self) -> tuple[_BrokerCoverage, ...]:
        """Materialize broker coverage only for explicit slow audit consumers."""

        return self._broker_coverage_ledger.to_tuple()

    @property
    def reconciliations(
        self,
    ) -> tuple[ReconciliationRecord | RevisionReconciliationRecord, ...]:
        """Materialize reconciliation history only for explicit slow audit."""

        return self._reconciliation_ledger.to_tuple()

    @property
    def execution_reconciliations(
        self,
    ) -> tuple[ExecutionRegistryReconciliationRecord, ...]:
        """Materialize registry outcomes only for explicit slow audit."""

        return self._execution_reconciliation_ledger.to_tuple()

    def _validate_full(self) -> None:
        """Perform the explicit slow fold used only by verified hydration/audit."""

        _require("scope", self.scope, VenueScope)
        for name in (
            "effects",
            "claims",
            "owners",
            "active_attempts",
            "closure_heads",
            "execution_bindings",
            "execution_reconciliations",
            "human_coverages",
            "broker_coverages",
            "reconciliations",
        ):
            _require_tuple(name, getattr(self, name))

        self._require_recovery_entry_types()
        if self.execution_registry_count is not None:
            if (
                type(self.execution_registry_count) is not int
                or self.execution_registry_count < 0
            ):
                raise ValueError(
                    "execution_registry_count must be a non-negative exact integer"
                )
        if self.execution_registry_commitment is not None:
            _require_digest(
                "execution_registry_commitment",
                self.execution_registry_commitment,
            )
        if (self.execution_registry_count is None) != (
            self.execution_registry_commitment is None
        ):
            raise ValueError(
                "execution registry count and commitment must be retained together"
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
        if any(
            type(entry)
            not in {
                _ResolvedRegistryProjectionOutcome,
                _UnresolvedRegistryAdvanceOutcome,
            }
            for entry in self.execution_reconciliations
        ):
            raise TypeError(
                "execution reconciliation entries must be exact outcome types"
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
            raise TypeError(
                "reconciliation entries must be typed reconciliation records"
            )

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
            _require("closure.source_event_id", closure.source_event_id, SourceEventId)
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
                or closure.broker_terminal_state not in _BROKER_TERMINAL_ATTEMPT_STATES
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
                if (
                    lifecycle_states.get(item.effect_id)
                    is not BrokerEffectState.REQUESTED
                ):
                    raise ValueError(
                        "cancel lifecycle input has no requested predecessor"
                    )
                lifecycle_states[item.effect_id] = (
                    BrokerEffectState.CANCELED_BEFORE_DISPATCH
                )
            elif isinstance(item, RecordDispatchClaim):
                if (
                    lifecycle_states.get(item.effect_id)
                    is not BrokerEffectState.REQUESTED
                ):
                    raise ValueError(
                        "claim lifecycle input has no requested predecessor"
                    )
                lifecycle_states[item.effect_id] = BrokerEffectState.DISPATCH_CLAIMED
            elif isinstance(item, RecoverClaimedEffect):
                if (
                    lifecycle_states.get(item.effect_id)
                    is not BrokerEffectState.DISPATCH_CLAIMED
                ):
                    raise ValueError(
                        "recovery lifecycle input has no claimed predecessor"
                    )
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
                    raise ValueError(
                        "transport lifecycle input has no valid predecessor"
                    )
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
                ordered_effect_states[item.effect_id] = (
                    BrokerEffectState.OUTCOME_UNKNOWN
                )
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
                ordered_leg_states[item.leg_key] = VenueAttemptState.OPERATOR_RECONCILED

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
                    and item.cumulative_quantity == closure.observed_cumulative_quantity
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
            _replay_venue_hydration_snapshot,
        )

        self._require_unique(
            "human coverage fact", (item.fact.key for item in self.human_coverages)
        )
        self._require_unique(
            "execution reconciliation input",
            (item.input_id for item in self.execution_reconciliations),
        )
        _validate_registry_transition_chain(
            self._registry_transition_ledger.to_tuple(),
            self.input_records,
            self.execution_reconciliations,
            self._registry_transition_head_commitment,
            self.scope,
        )
        expected_unresolved_account_count = sum(
            1
            for item in self.execution_reconciliations
            if not item.attribution_resolved
        )
        if (
            type(self._unresolved_account_execution_reconciliation_count) is not int
            or self._unresolved_account_execution_reconciliation_count
            != expected_unresolved_account_count
        ):
            raise ValueError(
                "account execution reconciliation count contradicts retained outcomes"
            )
        if (
            type(self._account_authority_epoch) is not int
            or self._account_authority_epoch != expected_unresolved_account_count
        ):
            raise ValueError(
                "account authority epoch contradicts unresolved registry outcomes"
            )
        revision_reconciliations = {
            record.input_id: record
            for record in self.reconciliations
            if isinstance(record, RevisionReconciliationRecord)
        }
        broker_coverage_by_root = {
            coverage.fact.root_key: coverage for coverage in self.broker_coverages
        }
        applied_revision_inputs: dict[
            RootFillKey, list[RecordBrokerRevisionEvidence]
        ] = {root_key: [] for root_key in broker_coverage_by_root}
        predecessor_by_root = {
            root_key: coverage.fact.key.source_event_id
            for root_key, coverage in broker_coverage_by_root.items()
        }
        for input_record in self.input_records:
            source = input_record.item
            if not isinstance(source, RecordBrokerRevisionEvidence):
                continue
            root_key = source.fact.root_key
            if root_key not in broker_coverage_by_root:
                continue
            reconciliation = revision_reconciliations.get(source.input_id)
            if reconciliation is not None and not reconciliation.canonical_applied:
                continue
            if source.fact.predecessor_source_event_id != predecessor_by_root[root_key]:
                continue
            applied_revision_inputs[root_key].append(source)
            predecessor_by_root[root_key] = source.fact.key.source_event_id
        authorized_human_facts = tuple(
            coverage.fact for coverage in self.human_coverages
        )
        authorized_corroborations = tuple(
            cast(BrokerFillFact, coverage.broker_fact)
            for coverage in self.human_coverages
            if coverage.broker_corroborated and coverage.broker_fact is not None
        )
        for registry_record in self.execution_reconciliations:
            source = input_by_id.get(registry_record.input_id)
            if type(source) is not CatchUpExecutionRegistry:
                raise ValueError(
                    "execution reconciliation requires exact catch-up provenance"
                )
            source = cast(CatchUpExecutionRegistry, source)
            execution = source.source_execution
            scope = execution.position.scope
            if (
                scope.broker != self.scope.broker
                or scope.environment != self.scope.environment
                or scope.account != self.scope.account
                or registry_record.command_commitment
                != _catch_up_input_commitment(source)
                or registry_record.target_checkpoint != source.target_checkpoint
                or execution.seen_facts.count
                != registry_record.resulting_registry_count
                or execution.seen_facts.commitment
                != registry_record.resulting_registry_commitment
                or not execution.seen_facts.has_prefix(
                    source.prior_account_registry_count,
                    source.prior_account_registry_commitment,
                )
                or not execution.seen_facts.has_prefix(
                    source.target_checkpoint.registry_count,
                    source.target_checkpoint.registry_commitment,
                )
            ):
                raise ValueError(
                    "execution reconciliation does not close its canonical catch-up"
                )
            target_prior = _replay_venue_hydration_snapshot(
                source.target_scope,
                execution.seen_facts,
                authorized_human_facts=authorized_human_facts,
                authorized_corroborations=authorized_corroborations,
                limit=source.target_checkpoint.registry_count,
            )
            target_prior = _bind_execution_reconciliation_cursor(
                target_prior,
                transition_count=(
                    source.target_checkpoint.reconciliation_transition_count
                ),
                transition_head=(
                    source.target_checkpoint.reconciliation_transition_head
                ),
                account_reconciliation_required=(
                    source.target_checkpoint.account_reconciliation_required
                ),
            )
            if (
                not self._execution_reconciliation_cursor_is_prefix(target_prior)
                or
                VenueExecutionCheckpoint.from_execution(target_prior)
                != source.target_checkpoint
            ):
                raise ValueError(
                    "catch-up target checkpoint is not derivable from its registry prefix"
                )
            target_result = _replay_venue_hydration_snapshot(
                source.target_scope,
                execution.seen_facts,
                authorized_human_facts=authorized_human_facts,
                authorized_corroborations=authorized_corroborations,
            )
            resulting_source_binding = _execution_binding_for_snapshot(execution)
            if type(registry_record) is _ResolvedRegistryProjectionOutcome:
                if (
                    source.prior_account_registry_count
                    != execution.seen_facts.count
                    or source.prior_account_registry_commitment
                    != execution.seen_facts.commitment
                    or source.prior_source_binding is None
                    or source.prior_source_binding != registry_record.source_binding
                    or registry_record.source_binding != resulting_source_binding
                    or _execution_binding_for_snapshot(target_result)
                    != source.target_checkpoint.binding
                ):
                    raise ValueError(
                        "resolved catch-up outcome lacks exact target/source proof"
                    )
                continue
            if type(registry_record) is not _UnresolvedRegistryAdvanceOutcome:
                raise TypeError("execution reconciliation outcome type is not admitted")
            source_prior = _replay_venue_hydration_snapshot(
                scope,
                execution.seen_facts,
                authorized_human_facts=authorized_human_facts,
                authorized_corroborations=authorized_corroborations,
                limit=source.prior_account_registry_count,
            )
            prior_source_binding = _execution_binding_for_snapshot(source_prior)
            expected_target_result_binding = (
                resulting_source_binding
                if source.target_scope == scope
                else source.target_checkpoint.binding
            )
            if (
                source.prior_account_registry_count
                != registry_record.prior_account_registry_count
                or source.prior_account_registry_commitment
                != registry_record.prior_account_registry_commitment
                or source.prior_source_binding is None
                or source.prior_source_binding
                != registry_record.prior_source_binding
                or registry_record.prior_source_binding != prior_source_binding
                or registry_record.resulting_source_binding
                != resulting_source_binding
                or prior_source_binding == resulting_source_binding
                or _execution_binding_for_snapshot(target_result)
                != expected_target_result_binding
                or not execution.seen_facts.suffix_belongs_to(
                    source.prior_account_registry_count,
                    scope,
                )
            ):
                raise ValueError(
                    "unresolved catch-up outcome lacks exact source-advance proof"
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
                raise ValueError(
                    "human coverage cannot exceed immutable effect capacity"
                )
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
                broker_source = input_by_id.get(human_coverage.broker_source_input_id)
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
            revision_sources = applied_revision_inputs[broker_coverage.fact.root_key]
            predecessor_source_event_id = broker_coverage.fact.key.source_event_id
            for revision_source in revision_sources:
                if not (
                    revision_source.effect_id == broker_coverage.effect_id
                    and revision_source.leg_key == broker_coverage.leg_key
                    and revision_source.fact.root_key == broker_coverage.fact.root_key
                    and revision_source.fact.predecessor_source_event_id
                    == predecessor_source_event_id
                ):
                    raise ValueError(
                        "broker revision history requires exact lineage provenance"
                    )
                predecessor_source_event_id = revision_source.fact.key.source_event_id
            if broker_coverage.head_fact == broker_coverage.fact:
                if (
                    broker_coverage.head_evidence_digest
                    != broker_coverage.evidence_digest
                    or broker_coverage.head_source_input_id
                    != broker_coverage.root_source_input_id
                    or revision_sources
                    or not broker_coverage.mapping_exact
                ):
                    raise ValueError(
                        "unrevised broker coverage must retain exact root evidence"
                    )
            else:
                head_source = input_by_id.get(broker_coverage.head_source_input_id)
                if not (
                    isinstance(head_source, RecordBrokerRevisionEvidence)
                    and head_source.effect_id == broker_coverage.effect_id
                    and head_source.leg_key == broker_coverage.leg_key
                    and head_source.fact == broker_coverage.head_fact
                    and head_source.evidence_digest
                    == broker_coverage.head_evidence_digest
                    and revision_sources
                    and revision_sources[-1].input_id
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

        intervals: dict[VenueLegKey, list[tuple[int, int, EffectId, bool]]] = {}
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
                source.input_id
                for sources in applied_revision_inputs.values()
                for source in sources
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
                if (
                    binding is None
                    or binding.integrity_bits & unresolved_execution.value
                ):
                    raise ValueError(
                        "operator-reconciled effect requires clean execution integrity"
                    )
                if any(
                    record.effect_id == effect_id for record in self.reconciliations
                ) or any(
                    not record.attribution_resolved
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
        result = object.__new__(cls)
        for name, value in (
            ("scope", scope),
            ("_effect_order", _PersistentSequence.empty()),
            ("_effect_by_id", _PersistentKeyMap.empty()),
            ("_effect_by_request_occurrence", _PersistentKeyMap.empty()),
            ("_effect_by_client_order", _PersistentKeyMap.empty()),
            ("_authority_epoch_by_scope", _PersistentKeyMap.empty()),
            ("_account_authority_epoch", 0),
            ("_contradiction_order_by_effect", _PersistentKeyMap.empty()),
            ("_claim_order", _PersistentSequence.empty()),
            ("_claim_by_effect", _PersistentKeyMap.empty()),
            ("_claim_by_occurrence", _PersistentKeyMap.empty()),
            ("_owner_order", _PersistentSequence.empty()),
            ("_owner_by_leg", _PersistentKeyMap.empty()),
            ("_leg_current_by_leg", _PersistentKeyMap.empty()),
            ("_leg_summary_by_effect", _PersistentKeyMap.empty()),
            ("_reconciliation_count_by_effect", _PersistentKeyMap.empty()),
            ("_closure_ledger", _PersistentSequence.empty()),
            ("_closure_by_id", _PersistentKeyMap.empty()),
            ("_closure_head_by_leg", _PersistentKeyMap.empty()),
            ("_input_ledger", _PersistentSequence.empty()),
            ("_input_by_id", _PersistentKeyMap.empty()),
            ("_direct_input_by_semantic", _PersistentKeyMap.empty()),
            ("_first_input_by_fact", _PersistentKeyMap.empty()),
            ("_economic_high_water_by_leg", _PersistentKeyMap.empty()),
            ("_human_coverage_ledger", _PersistentSequence.empty()),
            ("_human_coverage_by_root", _PersistentKeyMap.empty()),
            ("_broker_coverage_ledger", _PersistentSequence.empty()),
            ("_broker_coverage_by_root", _PersistentKeyMap.empty()),
            ("_coverage_provenance_by_scope", _PersistentKeyMap.empty()),
            ("_coverage_current_by_leg", _PersistentKeyMap.empty()),
            ("_coverage_total_by_effect", _PersistentKeyMap.empty()),
            ("_attributed_broker_root_count_by_scope", _PersistentKeyMap.empty()),
            ("_human_interval_index", _PersistentKeyMap.empty()),
            ("_human_broker_fact_index", _PersistentKeyMap.empty()),
            ("_reconciliation_ledger", _PersistentSequence.empty()),
            ("_reconciliation_by_input", _PersistentKeyMap.empty()),
            ("_unresolved_reconciliation_count_by_leg", _PersistentKeyMap.empty()),
            ("_canonical_revision_count_by_leg", _PersistentKeyMap.empty()),
            ("_execution_reconciliation_ledger", _PersistentSequence.empty()),
            ("_execution_reconciliation_by_input", _PersistentKeyMap.empty()),
            ("_registry_transition_ledger", _PersistentSequence.empty()),
            ("_registry_transition_head_commitment", None),
            (
                "_unresolved_execution_reconciliation_count_by_scope",
                _PersistentKeyMap.empty(),
            ),
            ("_unresolved_account_execution_reconciliation_count", 0),
            ("execution_registry_count", None),
            ("execution_registry_commitment", None),
            ("_binding_order", _PersistentSequence.empty()),
            ("_binding_by_scope", _PersistentKeyMap.empty()),
        ):
            object.__setattr__(result, name, value)
        return result

    def effect(self, effect_id: EffectId) -> BrokerEffect | None:
        """Materialize one effect's contradiction history for inspection/audit."""

        effect = self._current_effect(effect_id)
        if effect is None:
            return None
        return replace(
            effect,
            contradiction_evidence=self._contradictions_for(effect_id),
        )

    def execution_binding(
        self, position_scope: PositionScope
    ) -> VenueExecutionBinding | None:
        return self._binding_by_scope.get(_position_scope_index_key(position_scope))

    def _reconciliation_cursor(self) -> tuple[int, bytes]:
        return (
            self._registry_transition_ledger.length,
            self._registry_transition_head_commitment
            or _RECONCILIATION_GENESIS_HEAD,
        )

    def _execution_reconciliation_cursor_matches(
        self,
        execution: ExecutionSnapshot,
    ) -> bool:
        count, head = self._reconciliation_cursor()
        return (
            execution.reconciliation_transition_count == count
            and execution.reconciliation_transition_head == head
            and execution.account_reconciliation_required
            == (self._unresolved_account_execution_reconciliation_count > 0)
        )

    def _execution_reconciliation_cursor_is_prefix(
        self,
        execution: ExecutionSnapshot,
    ) -> bool:
        count = execution.reconciliation_transition_count
        if count < 0 or count > self._registry_transition_ledger.length:
            return False
        expected_head = (
            _RECONCILIATION_GENESIS_HEAD
            if count == 0
            else self._registry_transition_ledger.get(count - 1).commitment
        )
        return execution.reconciliation_transition_head == expected_head

    def _execution_matches(
        self,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> bool:
        """Return whether execution is the exact bound account/symbol high-water."""

        if (
            self.execution_registry_count != execution.seen_facts.count
            or self.execution_registry_commitment != execution.seen_facts.commitment
            or not self._execution_symbol_matches(execution, position_scope)
            or not self._execution_reconciliation_cursor_matches(execution)
        ):
            return False

        return True

    def _execution_pair_matches_fast(self, execution: ExecutionSnapshot) -> bool:
        """Authenticate one usable transition without touching either audit ledger."""

        if not self._effect_order.length:
            return (
                self.execution_registry_count is None
                and self.execution_registry_commitment is None
                and not self._binding_order.length
                and self._execution_reconciliation_cursor_matches(execution)
            )
        return (
            self.execution_registry_count == execution.seen_facts.count
            and self.execution_registry_commitment == execution.seen_facts.commitment
            and self._execution_binding_matches(execution)
            and self._execution_reconciliation_cursor_matches(execution)
        )

    def _execution_binding_matches(self, execution: ExecutionSnapshot) -> bool:
        binding = self.execution_binding(execution.position.scope)
        return bool(
            binding is not None
            and binding.position_commitment == execution.position.commitment
            and binding.root_heads_commitment == execution.root_heads.commitment
            and binding.integrity_bits == execution.integrity.value
        )

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
        provenance = self._coverage_provenance_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        return provenance is None or (
            provenance.root_heads_commitment == execution.root_heads.commitment
        )

    def owner(self, leg_key: VenueLegKey) -> VenueIdentityOwner | None:
        return self._owner_by_leg.get(_leg_index_key(leg_key))

    def active_attempt(self, leg_key: VenueLegKey) -> VenueAttempt | None:
        current = self._leg_current_by_leg.get(_leg_index_key(leg_key))
        return None if current is None else current.attempt

    def closure_head(self, leg_key: VenueLegKey) -> VenueTerminalClosure | None:
        return self._closure_head_by_leg.get(_leg_index_key(leg_key))

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

    def _human_coverage_for_root(self, root_key: RootFillKey) -> HumanCoverage | None:
        index = self._human_coverage_by_root.get(_coverage_root_index_key(root_key))
        return None if index is None else self._human_coverage_ledger.get(index)

    def _broker_coverage_for_root(
        self,
        root_key: RootFillKey,
    ) -> _BrokerCoverage | None:
        index = self._broker_coverage_by_root.get(_coverage_root_index_key(root_key))
        return None if index is None else self._broker_coverage_ledger.get(index)

    def _human_coverage_for_interval(
        self,
        leg_key: VenueLegKey,
        prior: int,
        resulting: int,
    ) -> HumanCoverage | None:
        index = self._human_interval_index.get(
            _coverage_interval_index_key(leg_key, prior, resulting)
        )
        return None if index is None else self._human_coverage_ledger.get(index)

    def _human_coverage_for_broker_fact(
        self,
        fact_key: ExecutionFactKey,
    ) -> HumanCoverage | None:
        index = self._human_broker_fact_index.get(_fact_index_key(fact_key))
        return None if index is None else self._human_coverage_ledger.get(index)

    def _coverage_current(self, leg_key: VenueLegKey) -> _CoverageLegCurrent:
        current = self._coverage_current_by_leg.get(_leg_index_key(leg_key))
        return _CoverageLegCurrent() if current is None else current

    def _effect_canonical_total(self, effect_id: EffectId) -> int:
        total = self._coverage_total_by_effect.get(_effect_index_key(effect_id))
        return 0 if total is None else total

    def _attributed_broker_root_count(self, execution_scope: ExecutionScope) -> int:
        count = self._attributed_broker_root_count_by_scope.get(
            _execution_scope_index_key(execution_scope)
        )
        return 0 if count is None else count

    def _has_request_occurrence(
        self,
        request_occurrence_id: RequestOccurrenceId,
    ) -> bool:
        return (
            self._effect_by_request_occurrence.get(
                _request_occurrence_index_key(request_occurrence_id)
            )
            is not None
        )

    def _has_client_order(self, client_order_id: ClientOrderId) -> bool:
        return (
            self._effect_by_client_order.get(_client_order_index_key(client_order_id))
            is not None
        )

    def _claim_for_effect(self, effect_id: EffectId) -> DispatchClaim | None:
        return self._claim_by_effect.get(_effect_index_key(effect_id))

    def _has_claim_occurrence(
        self,
        claim_occurrence_id: ClaimOccurrenceId,
    ) -> bool:
        return (
            self._claim_by_occurrence.get(
                _claim_occurrence_index_key(claim_occurrence_id)
            )
            is not None
        )

    def _leg_summary(self, effect_id: EffectId) -> _EffectLegSummary:
        retained = self._leg_summary_by_effect.get(_effect_index_key(effect_id))
        return _EffectLegSummary() if retained is None else retained

    def _has_effect_reconciliation(self, effect_id: EffectId) -> bool:
        retained = self._reconciliation_count_by_effect.get(
            _effect_index_key(effect_id)
        )
        return retained is not None and retained > 0

    def _reconciliation_for_input(
        self,
        input_id: VenueInputId,
    ) -> ReconciliationRecord | RevisionReconciliationRecord | None:
        return self._reconciliation_by_input.get(_input_index_key(input_id))

    def _execution_reconciliation_for_input(
        self,
        input_id: VenueInputId,
    ) -> ExecutionRegistryReconciliationRecord | None:
        return self._execution_reconciliation_by_input.get(_input_index_key(input_id))

    def _has_unresolved_reconciliation(self, leg_key: VenueLegKey) -> bool:
        count = self._unresolved_reconciliation_count_by_leg.get(
            _leg_index_key(leg_key)
        )
        return count is not None and count > 0

    def _has_canonical_revision(self, leg_key: VenueLegKey) -> bool:
        count = self._canonical_revision_count_by_leg.get(_leg_index_key(leg_key))
        return count is not None and count > 0

    def _has_unresolved_execution_reconciliation(
        self,
        position_scope: PositionScope,
    ) -> bool:
        if self._unresolved_account_execution_reconciliation_count > 0:
            return True
        count = self._unresolved_execution_reconciliation_count_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        return count is not None and count > 0

    def _input_record(self, input_id: VenueInputId) -> VenueInputRecord | None:
        return self._input_by_id.get(_input_index_key(input_id))

    def _direct_semantic_input(self, item: object) -> VenueInputRecord | None:
        record = self._direct_input_by_semantic.get(_semantic_input_key(item))
        if record is None:
            return None
        if record.semantic_alias_of is None and _input_commands_equal(
            record.item,
            item,
            include_input_id=False,
        ):
            return record
        raise ValueError("semantic input index commitment collision")

    def _fact_input_record(
        self,
        fact_key: ExecutionFactKey,
    ) -> VenueInputRecord | None:
        _require("fact_key", fact_key, ExecutionFactKey)
        return self._first_input_by_fact.get(_fact_index_key(fact_key))

    def _economic_high_water(self, leg_key: VenueLegKey) -> int:
        retained = self._economic_high_water_by_leg.get(_leg_index_key(leg_key))
        return 0 if retained is None else retained


_EVOLVABLE_BOOK_FIELDS = frozenset(
    {
        "scope",
        "execution_registry_count",
        "execution_registry_commitment",
    }
)


def _coverage_value_commitment(coverage: object) -> bytes:
    return _commit_parts(
        b"execution-core/venue-coverage-value/v1",
        _canonical_value_commitment(coverage),
    )


def _reconciliation_value_commitment(record: object) -> bytes:
    return _commit_parts(
        b"execution-core/venue-reconciliation-value/v1",
        _canonical_value_commitment(record),
    )


def _execution_reconciliation_value_commitment(record: object) -> bytes:
    return _commit_parts(
        b"execution-core/execution-registry-reconciliation-value/v1",
        _canonical_value_commitment(record),
    )


def _effect_value_commitment(effect_id: EffectId) -> bytes:
    return _commit_parts(
        b"execution-core/venue-effect-order-value/v1",
        _canonical_value_commitment(effect_id),
    )


def _leg_value_commitment(leg_key: VenueLegKey) -> bytes:
    return _commit_parts(
        b"execution-core/venue-owner-order-value/v1",
        _canonical_value_commitment(leg_key),
    )


def _binding_scope_value_commitment(position_scope: PositionScope) -> bytes:
    return _commit_parts(
        b"execution-core/venue-binding-order-value/v1",
        _canonical_value_commitment(position_scope),
    )


def _claim_value_commitment(claim: DispatchClaim) -> bytes:
    return _commit_parts(
        b"execution-core/venue-claim-value/v1",
        _canonical_value_commitment(claim),
    )


def _owner_value_commitment(owner: VenueIdentityOwner) -> bytes:
    return _commit_parts(
        b"execution-core/venue-owner-value/v1",
        _canonical_value_commitment(owner),
    )


def _binding_value_commitment(binding: VenueExecutionBinding) -> bytes:
    return _commit_parts(
        b"execution-core/venue-execution-binding-value/v1",
        _canonical_value_commitment(binding),
    )


def _append_coverage_value(
    ledger: _PersistentSequence[Any],
    by_root: _PersistentKeyMap[int],
    coverage: object,
) -> tuple[_PersistentSequence[Any], _PersistentKeyMap[int]]:
    root_key = getattr(getattr(coverage, "fact", None), "root_key", None)
    if not isinstance(root_key, RootFillKey):
        raise TypeError("coverage must retain an exact root-fill key")
    encoded_root = _coverage_root_index_key(root_key)
    if by_root.get(encoded_root) is not None:
        raise ValueError("coverage root already exists")
    index = ledger.length
    value_commitment = _coverage_value_commitment(coverage)
    return (
        ledger.append(coverage, value_commitment),
        by_root.insert_new(
            encoded_root,
            index,
            _commit_parts(
                b"execution-core/venue-coverage-index/v1",
                encoded_root,
                _encode_text(str(index)),
                value_commitment,
            ),
        ),
    )


def _replace_coverage_value(
    ledger: _PersistentSequence[Any],
    by_root: _PersistentKeyMap[int],
    prior: object,
    replacement: object,
) -> _PersistentSequence[Any]:
    prior_root = getattr(getattr(prior, "fact", None), "root_key", None)
    replacement_root = getattr(
        getattr(replacement, "fact", None),
        "root_key",
        None,
    )
    if not isinstance(prior_root, RootFillKey) or replacement_root != prior_root:
        raise ValueError("coverage replacement must preserve its exact root key")
    index = by_root.get(_coverage_root_index_key(prior_root))
    if index is None or ledger.get(index) != prior:
        raise ValueError("coverage replacement does not match retained current truth")
    return ledger.set(index, replacement, _coverage_value_commitment(replacement))


def _set_coverage_provenance(
    retained: _PersistentKeyMap[_CoverageProvenance],
    position_scope: PositionScope,
    provenance: _CoverageProvenance,
) -> _PersistentKeyMap[_CoverageProvenance]:
    key = _position_scope_index_key(position_scope)
    if retained.get(key) is None:
        return retained.insert_new(key, provenance, provenance.commitment)
    return retained.replace_existing(key, provenance, provenance.commitment)


def _evolve_coverage_provenance(
    retained: _PersistentKeyMap[_CoverageProvenance],
    prior_execution: ExecutionSnapshot,
    resulting_execution: ExecutionSnapshot,
    item: object | None,
    *,
    canonical_economic_input: bool,
) -> _PersistentKeyMap[_CoverageProvenance]:
    """Advance one covered-root proof without scanning retained coverage."""

    position_scope = resulting_execution.position.scope
    key = _position_scope_index_key(position_scope)
    current = retained.get(key)
    roots_changed = (
        prior_execution.root_heads.commitment
        != resulting_execution.root_heads.commitment
    )
    if not canonical_economic_input:
        if not roots_changed or current is None:
            return retained
        return _set_coverage_provenance(
            retained,
            position_scope,
            _CoverageProvenance(
                roots=current.roots,
                root_heads_commitment=None,
            ),
        )

    fact = getattr(item, "fact", None)
    root_key = getattr(fact, "root_key", None)
    if not isinstance(root_key, RootFillKey) or not _execution_head_matches_fact(
        resulting_execution.root_heads.get(root_key),
        fact,
    ):
        raise ValueError("canonical coverage input lacks its exact resulting root")
    roots = current.roots if current is not None else _PersistentKeyMap.empty()
    encoded_root = _coverage_root_index_key(root_key)
    fact_commitment = _canonical_value_commitment(fact)
    if roots.get(encoded_root) is None:
        roots = roots.insert_new(encoded_root, fact_commitment, fact_commitment)
    else:
        roots = roots.replace_existing(encoded_root, fact_commitment, fact_commitment)
    prior_provenance_valid = current is None or (
        current.root_heads_commitment == prior_execution.root_heads.commitment
    )
    return _set_coverage_provenance(
        retained,
        position_scope,
        _CoverageProvenance(
            roots=roots,
            root_heads_commitment=(
                resulting_execution.root_heads.commitment
                if prior_provenance_valid
                else None
            ),
        ),
    )


def _set_int_index(
    retained: _PersistentKeyMap[int],
    key: bytes,
    value: int,
    *,
    domain: bytes,
) -> _PersistentKeyMap[int]:
    if value < 0:
        raise ValueError("indexed aggregate cannot become negative")
    commitment = _commit_parts(domain, key, _encode_text(str(value)))
    if retained.get(key) is None:
        return retained.insert_new(key, value, commitment)
    return retained.replace_existing(key, value, commitment)


def _set_leg_current(
    retained: _PersistentKeyMap[_CoverageLegCurrent],
    leg_key: VenueLegKey,
    current: _CoverageLegCurrent,
) -> _PersistentKeyMap[_CoverageLegCurrent]:
    key = _leg_index_key(leg_key)
    if retained.get(key) is None:
        return retained.insert_new(key, current, current.commitment)
    return retained.replace_existing(key, current, current.commitment)


def _set_effect_leg_summary(
    retained: _PersistentKeyMap[_EffectLegSummary],
    effect_id: EffectId,
    summary: _EffectLegSummary,
) -> _PersistentKeyMap[_EffectLegSummary]:
    key = _effect_index_key(effect_id)
    if retained.get(key) is None:
        return retained.insert_new(key, summary, summary.commitment)
    return retained.replace_existing(key, summary, summary.commitment)


def _stored_effect_current(
    effect: BrokerEffect,
    authority_epochs: _PersistentKeyMap[int],
    account_authority_epoch: int,
) -> _EffectCurrent:
    effect = replace(effect, contradiction_evidence=())
    operator_epoch: int | None = None
    account_epoch: int | None = None
    if effect.state is BrokerEffectState.OPERATOR_RECONCILED:
        operator_epoch = (
            authority_epochs.get(_position_scope_index_key(effect.scope.position_scope))
            or 0
        )
        account_epoch = account_authority_epoch
    return _EffectCurrent(
        effect=effect,
        operator_epoch=operator_epoch,
        account_epoch=account_epoch,
    )


def _append_effect_value(
    order: _PersistentSequence[EffectId],
    by_id: _PersistentKeyMap[_EffectCurrent],
    by_request: _PersistentKeyMap[EffectId],
    by_client_order: _PersistentKeyMap[EffectId],
    authority_epochs: _PersistentKeyMap[int],
    account_authority_epoch: int,
    effect: object,
) -> tuple[
    _PersistentSequence[EffectId],
    _PersistentKeyMap[_EffectCurrent],
    _PersistentKeyMap[EffectId],
    _PersistentKeyMap[EffectId],
]:
    if not isinstance(effect, BrokerEffect):
        raise TypeError("effect append must be BrokerEffect")
    effect_key = _effect_index_key(effect.effect_id)
    request_key = _request_occurrence_index_key(effect.scope.request_occurrence_id)
    client_key = _client_order_index_key(effect.scope.client_order_id)
    if (
        by_id.get(effect_key) is not None
        or by_request.get(request_key) is not None
        or by_client_order.get(client_key) is not None
    ):
        raise ValueError(
            "effect identity, request occurrence, and client ID are unique"
        )
    current = _stored_effect_current(
        effect,
        authority_epochs,
        account_authority_epoch,
    )
    id_commitment = _effect_value_commitment(effect.effect_id)
    return (
        order.append(effect.effect_id, id_commitment),
        by_id.insert_new(effect_key, current, current.commitment),
        by_request.insert_new(request_key, effect.effect_id, id_commitment),
        by_client_order.insert_new(client_key, effect.effect_id, id_commitment),
    )


def _replace_effect_value(
    by_id: _PersistentKeyMap[_EffectCurrent],
    authority_epochs: _PersistentKeyMap[int],
    account_authority_epoch: int,
    effect: object,
) -> _PersistentKeyMap[_EffectCurrent]:
    if not isinstance(effect, BrokerEffect):
        raise TypeError("effect replacement must be BrokerEffect")
    key = _effect_index_key(effect.effect_id)
    if by_id.get(key) is None:
        raise KeyError("effect is not registered")
    current = _stored_effect_current(
        effect,
        authority_epochs,
        account_authority_epoch,
    )
    return by_id.replace_existing(key, current, current.commitment)


def _append_claim_value(
    order: _PersistentSequence[EffectId],
    by_effect: _PersistentKeyMap[DispatchClaim],
    by_occurrence: _PersistentKeyMap[EffectId],
    claim: object,
) -> tuple[
    _PersistentSequence[EffectId],
    _PersistentKeyMap[DispatchClaim],
    _PersistentKeyMap[EffectId],
]:
    if not isinstance(claim, DispatchClaim):
        raise TypeError("claim append must be DispatchClaim")
    effect_key = _effect_index_key(claim.effect_id)
    occurrence_key = _claim_occurrence_index_key(claim.claim_occurrence_id)
    if (
        by_effect.get(effect_key) is not None
        or by_occurrence.get(occurrence_key) is not None
    ):
        raise ValueError("claim effect and occurrence identities are unique")
    claim_commitment = _claim_value_commitment(claim)
    return (
        order.append(claim.effect_id, _effect_value_commitment(claim.effect_id)),
        by_effect.insert_new(effect_key, claim, claim_commitment),
        by_occurrence.insert_new(
            occurrence_key,
            claim.effect_id,
            _effect_value_commitment(claim.effect_id),
        ),
    )


def _append_contradiction_value(
    retained: _PersistentKeyMap[_PersistentSequence[AcceptanceContradiction]],
    effect_id: EffectId,
    contradiction: object,
) -> _PersistentKeyMap[_PersistentSequence[AcceptanceContradiction]]:
    if not isinstance(contradiction, AcceptanceContradiction):
        raise TypeError("contradiction append must be AcceptanceContradiction")
    key = _effect_index_key(effect_id)
    sequence = retained.get(key) or _PersistentSequence.empty()
    commitment = _commit_parts(
        b"execution-core/venue-acceptance-contradiction/v1",
        _canonical_value_commitment(contradiction),
    )
    sequence = sequence.append(contradiction, commitment)
    if retained.get(key) is None:
        return retained.insert_new(key, sequence, sequence.commitment)
    return retained.replace_existing(key, sequence, sequence.commitment)


def _append_owner_value(
    order: _PersistentSequence[VenueLegKey],
    by_leg: _PersistentKeyMap[VenueIdentityOwner],
    leg_current: _PersistentKeyMap[_LegCurrent],
    summaries: _PersistentKeyMap[_EffectLegSummary],
    owner_and_attempt: object,
) -> tuple[
    _PersistentSequence[VenueLegKey],
    _PersistentKeyMap[VenueIdentityOwner],
    _PersistentKeyMap[_LegCurrent],
    _PersistentKeyMap[_EffectLegSummary],
]:
    if (
        type(owner_and_attempt) is not tuple
        or len(owner_and_attempt) != 2
        or not isinstance(owner_and_attempt[0], VenueIdentityOwner)
        or not isinstance(owner_and_attempt[1], VenueAttempt)
    ):
        raise TypeError("owner append must pair VenueIdentityOwner and VenueAttempt")
    owner, attempt = cast(tuple[VenueIdentityOwner, VenueAttempt], owner_and_attempt)
    if owner.leg_key != attempt.leg_key:
        raise ValueError("owner and initial attempt must name the same leg")
    leg_key = _leg_index_key(owner.leg_key)
    if by_leg.get(leg_key) is not None or leg_current.get(leg_key) is not None:
        raise ValueError("venue leg already has an owner")
    current = _LegCurrent(attempt)
    summary = summaries.get(_effect_index_key(owner.effect_id)) or _EffectLegSummary()
    summary = replace(
        summary,
        owner_count=summary.owner_count + 1,
        active_count=summary.active_count + 1,
    )
    return (
        order.append(owner.leg_key, _leg_value_commitment(owner.leg_key)),
        by_leg.insert_new(leg_key, owner, _owner_value_commitment(owner)),
        leg_current.insert_new(leg_key, current, current.commitment),
        _set_effect_leg_summary(summaries, owner.effect_id, summary),
    )


def _replace_attempt_value(
    retained: _PersistentKeyMap[_LegCurrent],
    attempt: object,
) -> _PersistentKeyMap[_LegCurrent]:
    if not isinstance(attempt, VenueAttempt):
        raise TypeError("attempt replacement must be VenueAttempt")
    key = _leg_index_key(attempt.leg_key)
    prior = retained.get(key)
    if prior is None or prior.attempt is None:
        raise ValueError("attempt replacement requires one active leg")
    current = _LegCurrent(attempt)
    return retained.replace_existing(key, current, current.commitment)


def _upsert_binding_value(
    order: _PersistentSequence[PositionScope],
    by_scope: _PersistentKeyMap[VenueExecutionBinding],
    binding: object,
) -> tuple[
    _PersistentSequence[PositionScope],
    _PersistentKeyMap[VenueExecutionBinding],
]:
    if not isinstance(binding, VenueExecutionBinding):
        raise TypeError("binding upsert must be VenueExecutionBinding")
    key = _position_scope_index_key(binding.position_scope)
    commitment = _binding_value_commitment(binding)
    if by_scope.get(key) is None:
        return (
            order.append(
                binding.position_scope,
                _binding_scope_value_commitment(binding.position_scope),
            ),
            by_scope.insert_new(key, binding, commitment),
        )
    return order, by_scope.replace_existing(key, binding, commitment)


def _closure_is_finalization_ready(
    effect: BrokerEffect,
    closure: VenueTerminalClosure | None,
    covered_cumulative: int,
) -> bool:
    if closure is None or closure.cumulative_quantity.value != covered_cumulative:
        return False
    is_filled = (
        closure.status is VenueAttemptState.FILLED
        or closure.broker_terminal_state is VenueAttemptState.FILLED
    )
    return not is_filled or covered_cumulative == effect.scope.quantity.value


def _append_reconciliation_value(
    ledger: _PersistentSequence[Any],
    by_input: _PersistentKeyMap[Any],
    unresolved_by_leg: _PersistentKeyMap[int],
    reconciliation_by_effect: _PersistentKeyMap[int],
    canonical_revision_by_leg: _PersistentKeyMap[int],
    coverage_by_leg: _PersistentKeyMap[_CoverageLegCurrent],
    coverage_by_effect: _PersistentKeyMap[int],
    record: object,
) -> tuple[
    _PersistentSequence[Any],
    _PersistentKeyMap[Any],
    _PersistentKeyMap[int],
    _PersistentKeyMap[int],
    _PersistentKeyMap[int],
    _PersistentKeyMap[_CoverageLegCurrent],
    _PersistentKeyMap[int],
]:
    """Append one reconciliation and advance its bounded current indexes."""

    from .recovery import ReconciliationRecord, RevisionReconciliationRecord

    if not isinstance(record, (ReconciliationRecord, RevisionReconciliationRecord)):
        raise TypeError("reconciliation append must be a typed reconciliation record")
    input_key = _input_index_key(record.input_id)
    if by_input.get(input_key) is not None:
        raise ValueError("reconciliation input identity already exists")
    commitment = _reconciliation_value_commitment(record)
    ledger = ledger.append(record, commitment)
    by_input = by_input.insert_new(input_key, record, commitment)

    leg_key = _leg_index_key(record.leg_key)
    unresolved_by_leg = _set_int_index(
        unresolved_by_leg,
        leg_key,
        (unresolved_by_leg.get(leg_key) or 0) + 1,
        domain=b"execution-core/unresolved-reconciliation-count/v1",
    )
    effect_key = _effect_index_key(record.effect_id)
    reconciliation_by_effect = _set_int_index(
        reconciliation_by_effect,
        effect_key,
        (reconciliation_by_effect.get(effect_key) or 0) + 1,
        domain=b"execution-core/reconciliation-count-by-effect/v1",
    )
    if isinstance(record, RevisionReconciliationRecord) and record.canonical_applied:
        canonical_revision_by_leg = _set_int_index(
            canonical_revision_by_leg,
            leg_key,
            (canonical_revision_by_leg.get(leg_key) or 0) + 1,
            domain=b"execution-core/canonical-revision-count/v1",
        )
        current = coverage_by_leg.get(leg_key) or _CoverageLegCurrent()
        resulting_total = record.resulting_venue_cumulative_quantity.value
        delta = resulting_total - current.canonical_total
        coverage_by_leg = _set_leg_current(
            coverage_by_leg,
            record.leg_key,
            replace(current, canonical_total=resulting_total),
        )
        coverage_by_effect = _set_int_index(
            coverage_by_effect,
            effect_key,
            (coverage_by_effect.get(effect_key) or 0) + delta,
            domain=b"execution-core/coverage-effect-total/v1",
        )
    return (
        ledger,
        by_input,
        unresolved_by_leg,
        reconciliation_by_effect,
        canonical_revision_by_leg,
        coverage_by_leg,
        coverage_by_effect,
    )


def _append_execution_reconciliation_value(
    ledger: _PersistentSequence[ExecutionRegistryReconciliationRecord],
    by_input: _PersistentKeyMap[ExecutionRegistryReconciliationRecord],
    unresolved_by_scope: _PersistentKeyMap[int],
    record: object,
) -> tuple[
    _PersistentSequence[ExecutionRegistryReconciliationRecord],
    _PersistentKeyMap[ExecutionRegistryReconciliationRecord],
    _PersistentKeyMap[int],
]:
    """Append one registry outcome and advance its unresolved-scope index."""

    if type(record) not in {
        _ResolvedRegistryProjectionOutcome,
        _UnresolvedRegistryAdvanceOutcome,
    }:
        raise TypeError(
            "execution reconciliation append must be an exact registry outcome"
        )
    record = cast(ExecutionRegistryReconciliationRecord, record)
    input_key = _input_index_key(record.input_id)
    if by_input.get(input_key) is not None:
        raise ValueError("execution reconciliation input identity already exists")
    commitment = _execution_reconciliation_value_commitment(record)
    ledger = ledger.append(record, commitment)
    by_input = by_input.insert_new(input_key, record, commitment)
    if not record.attribution_resolved:
        scope_key = _position_scope_index_key(record.position_scope)
        unresolved_by_scope = _set_int_index(
            unresolved_by_scope,
            scope_key,
            (unresolved_by_scope.get(scope_key) or 0) + 1,
            domain=b"execution-core/unresolved-execution-reconciliation-count/v1",
        )
    return ledger, by_input, unresolved_by_scope


def _evolve_coverage_current_indexes(
    current: VenueRecoveryBook,
    human_coverage_ledger: _PersistentSequence[Any],
    broker_coverage_ledger: _PersistentSequence[Any],
    *,
    human_append: object | None,
    human_replace: object | None,
    broker_append: object | None,
    broker_replace: object | None,
) -> tuple[
    _PersistentKeyMap[_CoverageLegCurrent],
    _PersistentKeyMap[int],
    _PersistentKeyMap[int],
    _PersistentKeyMap[int],
    _PersistentKeyMap[int],
]:
    """Advance bounded coverage lookup and aggregate indexes."""

    from .recovery import HumanCoverage, _BrokerCoverage

    legs = current._coverage_current_by_leg
    effect_totals = current._coverage_total_by_effect
    broker_scope_counts = current._attributed_broker_root_count_by_scope
    human_intervals = current._human_interval_index
    human_broker_facts = current._human_broker_fact_index

    if human_append is not None:
        if not isinstance(human_append, HumanCoverage):
            raise TypeError("human coverage append must be HumanCoverage")
        coverage = human_append
        index = human_coverage_ledger.length - 1
        interval_key = _coverage_interval_index_key(
            coverage.leg_key,
            coverage.fact.prior_cumulative_quantity.value,
            coverage.fact.resulting_cumulative_quantity.value,
        )
        if human_intervals.get(interval_key) is not None:
            raise ValueError("human coverage interval already exists")
        human_intervals = human_intervals.insert_new(
            interval_key,
            index,
            _commit_parts(
                b"execution-core/human-coverage-interval-index/v1",
                interval_key,
                _encode_text(str(index)),
            ),
        )
        width = coverage.fact.quantity.value
        leg = current._coverage_current(coverage.leg_key)
        legs = _set_leg_current(
            legs,
            coverage.leg_key,
            replace(
                leg,
                frontier=max(
                    leg.frontier,
                    coverage.fact.resulting_cumulative_quantity.value,
                ),
                canonical_total=leg.canonical_total + width,
                tail_root_key=coverage.fact.root_key,
            ),
        )
        effect_key = _effect_index_key(coverage.effect_id)
        effect_totals = _set_int_index(
            effect_totals,
            effect_key,
            (effect_totals.get(effect_key) or 0) + width,
            domain=b"execution-core/coverage-effect-total/v1",
        )

    if human_replace is not None:
        prior, replacement = cast(tuple[object, object], human_replace)
        if not isinstance(prior, HumanCoverage) or not isinstance(
            replacement,
            HumanCoverage,
        ):
            raise TypeError("human coverage replacement must retain HumanCoverage")
        if prior.broker_fact is None and replacement.broker_fact is not None:
            human_index = current._human_coverage_by_root.get(
                _coverage_root_index_key(prior.fact.root_key)
            )
            assert human_index is not None
            fact_key = _fact_index_key(replacement.broker_fact.key)
            if human_broker_facts.get(fact_key) is not None:
                raise ValueError("broker fact already corroborates another interval")
            human_broker_facts = human_broker_facts.insert_new(
                fact_key,
                human_index,
                _commit_parts(
                    b"execution-core/human-broker-fact-index/v1",
                    fact_key,
                    _encode_text(str(human_index)),
                ),
            )

    if broker_append is not None:
        if not isinstance(broker_append, _BrokerCoverage):
            raise TypeError("broker coverage append must be _BrokerCoverage")
        broker_coverage = broker_append
        width = (
            broker_coverage.resulting_cumulative_quantity.value
            - broker_coverage.prior_cumulative_quantity.value
        )
        leg = current._coverage_current(broker_coverage.leg_key)
        legs = _set_leg_current(
            legs,
            broker_coverage.leg_key,
            replace(
                leg,
                frontier=max(
                    leg.frontier,
                    broker_coverage.resulting_cumulative_quantity.value,
                ),
                canonical_total=leg.canonical_total + width,
                tail_root_key=broker_coverage.fact.root_key,
                inexact_broker_count=(
                    leg.inexact_broker_count
                    + (0 if broker_coverage.mapping_exact else 1)
                ),
            ),
        )
        effect_key = _effect_index_key(broker_coverage.effect_id)
        effect_totals = _set_int_index(
            effect_totals,
            effect_key,
            (effect_totals.get(effect_key) or 0) + width,
            domain=b"execution-core/coverage-effect-total/v1",
        )
        scope_key = _execution_scope_index_key(broker_coverage.fact.scope)
        broker_scope_counts = _set_int_index(
            broker_scope_counts,
            scope_key,
            (broker_scope_counts.get(scope_key) or 0) + 1,
            domain=b"execution-core/attributed-broker-root-count/v1",
        )

    if broker_replace is not None:
        prior, replacement = cast(tuple[object, object], broker_replace)
        if not isinstance(prior, _BrokerCoverage) or not isinstance(
            replacement,
            _BrokerCoverage,
        ):
            raise TypeError("broker coverage replacement must retain _BrokerCoverage")
        leg = current._coverage_current(prior.leg_key)
        delta = (
            replacement.resulting_cumulative_quantity.value
            - prior.resulting_cumulative_quantity.value
        )
        legs = _set_leg_current(
            legs,
            prior.leg_key,
            replace(
                leg,
                frontier=(
                    replacement.resulting_cumulative_quantity.value
                    if leg.tail_root_key == prior.fact.root_key and delta
                    else leg.frontier
                ),
                canonical_total=leg.canonical_total + delta,
                inexact_broker_count=(
                    leg.inexact_broker_count
                    - (0 if prior.mapping_exact else 1)
                    + (0 if replacement.mapping_exact else 1)
                ),
            ),
        )
        effect_key = _effect_index_key(prior.effect_id)
        effect_totals = _set_int_index(
            effect_totals,
            effect_key,
            (effect_totals.get(effect_key) or 0) + delta,
            domain=b"execution-core/coverage-effect-total/v1",
        )

    return (
        legs,
        effect_totals,
        broker_scope_counts,
        human_intervals,
        human_broker_facts,
    )


def _audit_build_coverage_current_indexes(
    human_coverages: tuple[object, ...],
    broker_coverages: tuple[object, ...],
) -> tuple[
    _PersistentKeyMap[_CoverageLegCurrent],
    _PersistentKeyMap[int],
    _PersistentKeyMap[int],
    _PersistentKeyMap[int],
    _PersistentKeyMap[int],
]:
    """Rebuild bounded current indexes during the explicit slow audit fold."""

    from .recovery import HumanCoverage, _BrokerCoverage

    leg_values: dict[VenueLegKey, _CoverageLegCurrent] = {}
    effect_values: dict[EffectId, int] = {}
    broker_scope_values: dict[ExecutionScope, int] = {}
    interval_values: list[tuple[bytes, int]] = []
    broker_fact_values: list[tuple[bytes, int]] = []

    for index, value in enumerate(human_coverages):
        if not isinstance(value, HumanCoverage):
            raise TypeError("human coverage audit value has the wrong type")
        width = value.fact.quantity.value
        prior = value.fact.prior_cumulative_quantity.value
        resulting = value.fact.resulting_cumulative_quantity.value
        current = leg_values.get(value.leg_key, _CoverageLegCurrent())
        if prior >= current.frontier or current.tail_root_key is None:
            tail_root_key = value.fact.root_key
        else:
            tail_root_key = current.tail_root_key
        leg_values[value.leg_key] = replace(
            current,
            frontier=max(current.frontier, resulting),
            canonical_total=current.canonical_total + width,
            tail_root_key=tail_root_key,
        )
        effect_values[value.effect_id] = effect_values.get(value.effect_id, 0) + width
        interval_values.append(
            (
                _coverage_interval_index_key(value.leg_key, prior, resulting),
                index,
            )
        )
        if value.broker_fact is not None:
            broker_fact_values.append((_fact_index_key(value.broker_fact.key), index))

    for value in broker_coverages:
        if not isinstance(value, _BrokerCoverage):
            raise TypeError("broker coverage audit value has the wrong type")
        prior = value.prior_cumulative_quantity.value
        resulting = value.resulting_cumulative_quantity.value
        width = resulting - prior
        current = leg_values.get(value.leg_key, _CoverageLegCurrent())
        if prior >= current.frontier or current.tail_root_key is None:
            tail_root_key = value.fact.root_key
        else:
            tail_root_key = current.tail_root_key
        leg_values[value.leg_key] = replace(
            current,
            frontier=max(current.frontier, resulting),
            canonical_total=current.canonical_total + width,
            tail_root_key=tail_root_key,
            inexact_broker_count=(
                current.inexact_broker_count + (0 if value.mapping_exact else 1)
            ),
        )
        effect_values[value.effect_id] = effect_values.get(value.effect_id, 0) + width
        broker_scope_values[value.fact.scope] = (
            broker_scope_values.get(value.fact.scope, 0) + 1
        )

    leg_index: _PersistentKeyMap[_CoverageLegCurrent] = _PersistentKeyMap.empty()
    for leg_key, current in leg_values.items():
        leg_index = _set_leg_current(leg_index, leg_key, current)
    effect_index: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    for effect_id, total in effect_values.items():
        effect_index = _set_int_index(
            effect_index,
            _effect_index_key(effect_id),
            total,
            domain=b"execution-core/coverage-effect-total/v1",
        )
    broker_scope_index: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    for execution_scope, count in broker_scope_values.items():
        broker_scope_index = _set_int_index(
            broker_scope_index,
            _execution_scope_index_key(execution_scope),
            count,
            domain=b"execution-core/attributed-broker-root-count/v1",
        )
    interval_index: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    for key, index in interval_values:
        if interval_index.get(key) is not None:
            raise ValueError("human coverage intervals must be unique")
        interval_index = interval_index.insert_new(
            key,
            index,
            _commit_parts(
                b"execution-core/human-coverage-interval-index/v1",
                key,
                _encode_text(str(index)),
            ),
        )
    broker_fact_index: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    for key, index in broker_fact_values:
        if broker_fact_index.get(key) is not None:
            raise ValueError("broker fact cannot corroborate multiple intervals")
        broker_fact_index = broker_fact_index.insert_new(
            key,
            index,
            _commit_parts(
                b"execution-core/human-broker-fact-index/v1",
                key,
                _encode_text(str(index)),
            ),
        )
    return (
        leg_index,
        effect_index,
        broker_scope_index,
        interval_index,
        broker_fact_index,
    )


def _append_input_proof(
    book: VenueRecoveryBook,
    item: object,
) -> tuple[
    _PersistentSequence[VenueInputRecord],
    _PersistentKeyMap[VenueInputRecord],
    _PersistentKeyMap[VenueInputRecord],
    _PersistentKeyMap[VenueInputRecord],
]:
    input_id = _require_input_id("input_id", getattr(item, "input_id", None))
    input_key = _input_index_key(input_id)
    if book._input_by_id.get(input_key) is not None:
        raise ValueError("input identity already exists")
    semantic_source = book._direct_semantic_input(item)
    record = VenueInputRecord(
        input_id=input_id,
        item=item,
        semantic_alias_of=(
            None if semantic_source is None else semantic_source.input_id
        ),
    )
    record_commitment = _input_record_commitment(record)
    next_ledger = book._input_ledger.append(record, record_commitment)
    next_by_id = book._input_by_id.insert_new(
        input_key,
        record,
        record_commitment,
    )
    next_semantics = book._direct_input_by_semantic
    if semantic_source is None:
        next_semantics = next_semantics.insert_new(
            _semantic_input_key(item),
            record,
            record_commitment,
        )
    next_facts = book._first_input_by_fact
    fact_key = getattr(getattr(item, "fact", None), "key", None)
    if isinstance(fact_key, ExecutionFactKey):
        encoded_fact_key = _fact_index_key(fact_key)
        if next_facts.get(encoded_fact_key) is None:
            next_facts = next_facts.insert_new(
                encoded_fact_key,
                record,
                record_commitment,
            )
    return (
        next_ledger,
        next_by_id,
        next_semantics,
        next_facts,
    )


def _advance_economic_high_water(
    retained: _PersistentKeyMap[int],
    item: object,
    execution: ExecutionSnapshot,
) -> _PersistentKeyMap[int]:
    """Index only economics proven canonical in the resulting execution pair."""

    from .recovery import (
        IngestHumanAttestedFill,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
    )

    fact = getattr(item, "fact", None)
    if not isinstance(
        item,
        (
            IngestHumanAttestedFill,
            RecordBrokerFillEvidence,
            RecordBrokerRevisionEvidence,
        ),
    ) or not isinstance(
        fact,
        (
            BrokerFillFact,
            BrokerTradeCorrectFact,
            BrokerTradeBustFact,
            HumanAttestedFillFact,
        ),
    ):
        return retained
    if not _execution_head_matches_fact(
        execution.root_heads.get(fact.root_key),
        fact,
    ):
        return retained

    if isinstance(item, IngestHumanAttestedFill):
        leg_key = item.fact.leg_key
        candidate = item.fact.resulting_cumulative_quantity.value
    elif isinstance(item, RecordBrokerFillEvidence):
        leg_key = item.leg_key
        candidate = max(
            item.prior_cumulative_quantity.value,
            item.resulting_cumulative_quantity.value,
        )
    else:
        leg_key = item.leg_key
        candidate = max(
            item.prior_venue_cumulative_quantity.value,
            item.resulting_venue_cumulative_quantity.value,
        )
    encoded_leg_key = _leg_index_key(leg_key)
    prior_high_water = retained.get(encoded_leg_key)
    next_high_water = max(prior_high_water or 0, candidate)
    if prior_high_water == next_high_water:
        return retained
    commitment = _commit_parts(
        b"execution-core/venue-economic-high-water/v1",
        _encode_text(str(next_high_water)),
    )
    if prior_high_water is None:
        return retained.insert_new(
            encoded_leg_key,
            next_high_water,
            commitment,
        )
    return retained.replace_existing(
        encoded_leg_key,
        next_high_water,
        commitment,
    )


def _append_closure_proof(
    book: VenueRecoveryBook,
    closure: VenueTerminalClosure,
) -> tuple[
    _PersistentSequence[VenueTerminalClosure],
    _PersistentKeyMap[VenueTerminalClosure],
    _PersistentKeyMap[VenueTerminalClosure],
]:
    closure_key = _closure_index_key(closure.closure_id)
    if book._closure_by_id.get(closure_key) is not None:
        raise ValueError("closure identity already exists")
    leg_key = _leg_index_key(closure.leg_key)
    prior = book._closure_head_by_leg.get(leg_key)
    expected_ordinal = 1 if prior is None else prior.ordinal + 1
    expected_predecessor = None if prior is None else prior.closure_id
    if (
        closure.ordinal != expected_ordinal
        or closure.predecessor_closure_id != expected_predecessor
    ):
        raise ValueError("closure must name the indexed current predecessor")
    if closure.kind is VenueClosureKind.BROKER_ECONOMIC:
        if prior is None or (
            closure.status is not prior.status
            or closure.broker_terminal_state is not prior.broker_terminal_state
            or closure.observed_cumulative_quantity
            != prior.observed_cumulative_quantity
        ):
            raise ValueError(
                "broker-economic closure must preserve indexed terminal identity"
            )
    closure_commitment = _closure_commitment(closure)
    next_ledger = book._closure_ledger.append(closure, closure_commitment)
    next_by_id = book._closure_by_id.insert_new(
        closure_key,
        closure,
        closure_commitment,
    )
    if prior is None:
        next_heads = book._closure_head_by_leg.insert_new(
            leg_key,
            closure,
            closure_commitment,
        )
    else:
        next_heads = book._closure_head_by_leg.replace_existing(
            leg_key,
            closure,
            closure_commitment,
        )
    return next_ledger, next_by_id, next_heads


def _audit_hydrate_book(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    **changes: Any,
) -> VenueRecoveryBook:
    """Explicit slow reconstruction with a complete fold and exact pair proof."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be the exact opaque VenueRecoveryBook type")
    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    _require_execution_components(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
    )

    allowed = _EVOLVABLE_BOOK_FIELDS | {
        "effects",
        "claims",
        "owners",
        "active_attempts",
        "closure_heads",
        "execution_bindings",
        "closure_history",
        "input_records",
        "human_coverages",
        "broker_coverages",
        "reconciliations",
        "execution_reconciliations",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise TypeError(f"unsupported audit hydration fields: {sorted(unknown)!r}")
    if (
        "execution_registry_commitment" in changes
        and "execution_registry_count" not in changes
        and changes["execution_registry_commitment"] == execution.seen_facts.commitment
    ):
        changes["execution_registry_count"] = execution.seen_facts.count
    closure_history = changes.pop("closure_history", book.closure_history)
    effects = changes.pop("effects", book.effects)
    claims = changes.pop("claims", book.claims)
    owners = changes.pop("owners", book.owners)
    active_attempts = changes.pop("active_attempts", book.active_attempts)
    closure_heads = changes.pop("closure_heads", book.closure_heads)
    execution_bindings = changes.pop(
        "execution_bindings",
        book.execution_bindings,
    )
    input_records = changes.pop("input_records", book.input_records)
    human_coverages = changes.pop("human_coverages", book.human_coverages)
    broker_coverages = changes.pop("broker_coverages", book.broker_coverages)
    reconciliations = changes.pop("reconciliations", book.reconciliations)
    execution_reconciliations = changes.pop(
        "execution_reconciliations",
        book.execution_reconciliations,
    )
    _require_tuple("closure_history", closure_history)
    _require_tuple("effects", effects)
    _require_tuple("claims", claims)
    _require_tuple("owners", owners)
    _require_tuple("active_attempts", active_attempts)
    _require_tuple("closure_heads", closure_heads)
    _require_tuple("execution_bindings", execution_bindings)
    _require_tuple("input_records", input_records)
    _require_tuple("human_coverages", human_coverages)
    _require_tuple("broker_coverages", broker_coverages)
    _require_tuple("reconciliations", reconciliations)
    _require_tuple("execution_reconciliations", execution_reconciliations)
    if any(
        type(entry)
        not in {
            _ResolvedRegistryProjectionOutcome,
            _UnresolvedRegistryAdvanceOutcome,
        }
        for entry in execution_reconciliations
    ):
        raise TypeError(
            "execution reconciliation entries must be exact outcome types"
        )

    closure_ledger: _PersistentSequence[VenueTerminalClosure] = (
        _PersistentSequence.empty()
    )
    closure_by_id: _PersistentKeyMap[VenueTerminalClosure] = _PersistentKeyMap.empty()
    closure_heads_by_leg: _PersistentKeyMap[VenueTerminalClosure] = (
        _PersistentKeyMap.empty()
    )
    for closure in closure_history:
        _require("closure", closure, VenueTerminalClosure)
        closure_key = _closure_index_key(closure.closure_id)
        if closure_by_id.get(closure_key) is not None:
            raise ValueError("closure identities must be unique")
        commitment = _closure_commitment(closure)
        closure_ledger = closure_ledger.append(closure, commitment)
        closure_by_id = closure_by_id.insert_new(
            closure_key,
            closure,
            commitment,
        )
        leg_key = _leg_index_key(closure.leg_key)
        if closure_heads_by_leg.get(leg_key) is None:
            closure_heads_by_leg = closure_heads_by_leg.insert_new(
                leg_key,
                closure,
                commitment,
            )
        else:
            closure_heads_by_leg = closure_heads_by_leg.replace_existing(
                leg_key,
                closure,
                commitment,
            )

    authority_epoch_by_scope: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    account_authority_epoch = sum(
        1
        for reconciliation in execution_reconciliations
        if not reconciliation.attribution_resolved
    )
    effect_order: _PersistentSequence[EffectId] = _PersistentSequence.empty()
    effect_by_id: _PersistentKeyMap[_EffectCurrent] = _PersistentKeyMap.empty()
    effect_by_request_occurrence: _PersistentKeyMap[EffectId] = (
        _PersistentKeyMap.empty()
    )
    effect_by_client_order: _PersistentKeyMap[EffectId] = _PersistentKeyMap.empty()
    contradiction_order_by_effect: _PersistentKeyMap[
        _PersistentSequence[AcceptanceContradiction]
    ] = _PersistentKeyMap.empty()
    for effect in effects:
        (
            effect_order,
            effect_by_id,
            effect_by_request_occurrence,
            effect_by_client_order,
        ) = _append_effect_value(
            effect_order,
            effect_by_id,
            effect_by_request_occurrence,
            effect_by_client_order,
            authority_epoch_by_scope,
            account_authority_epoch,
            effect,
        )
        for contradiction in effect.contradiction_evidence:
            contradiction_order_by_effect = _append_contradiction_value(
                contradiction_order_by_effect,
                effect.effect_id,
                contradiction,
            )

    claim_order: _PersistentSequence[EffectId] = _PersistentSequence.empty()
    claim_by_effect: _PersistentKeyMap[DispatchClaim] = _PersistentKeyMap.empty()
    claim_by_occurrence: _PersistentKeyMap[EffectId] = _PersistentKeyMap.empty()
    for claim in claims:
        claim_order, claim_by_effect, claim_by_occurrence = _append_claim_value(
            claim_order,
            claim_by_effect,
            claim_by_occurrence,
            claim,
        )

    active_by_leg: dict[VenueLegKey, VenueAttempt] = {}
    for attempt in active_attempts:
        _require("active attempt", attempt, VenueAttempt)
        if attempt.leg_key in active_by_leg:
            raise ValueError("active attempt legs must be unique")
        active_by_leg[attempt.leg_key] = attempt
    owner_order: _PersistentSequence[VenueLegKey] = _PersistentSequence.empty()
    owner_by_leg: _PersistentKeyMap[VenueIdentityOwner] = _PersistentKeyMap.empty()
    leg_current_by_leg: _PersistentKeyMap[_LegCurrent] = _PersistentKeyMap.empty()
    leg_summary_by_effect: _PersistentKeyMap[_EffectLegSummary] = (
        _PersistentKeyMap.empty()
    )
    owner_keys: set[VenueLegKey] = set()
    for owner in owners:
        _require("owner", owner, VenueIdentityOwner)
        if owner.leg_key in owner_keys:
            raise ValueError("owner legs must be unique")
        owner_keys.add(owner.leg_key)
        encoded_leg = _leg_index_key(owner.leg_key)
        owner_order = owner_order.append(
            owner.leg_key,
            _leg_value_commitment(owner.leg_key),
        )
        owner_by_leg = owner_by_leg.insert_new(
            encoded_leg,
            owner,
            _owner_value_commitment(owner),
        )
        leg_current = _LegCurrent(active_by_leg.get(owner.leg_key))
        leg_current_by_leg = leg_current_by_leg.insert_new(
            encoded_leg,
            leg_current,
            leg_current.commitment,
        )
        summary = (
            leg_summary_by_effect.get(_effect_index_key(owner.effect_id))
            or _EffectLegSummary()
        )
        leg_summary_by_effect = _set_effect_leg_summary(
            leg_summary_by_effect,
            owner.effect_id,
            replace(
                summary,
                owner_count=summary.owner_count + 1,
                active_count=(
                    summary.active_count + (1 if owner.leg_key in active_by_leg else 0)
                ),
            ),
        )
    if set(active_by_leg) - owner_keys:
        raise ValueError("active attempts require retained owners")
    if any(closure.leg_key not in owner_keys for closure in closure_history):
        raise ValueError("closure history requires retained owners")
    derived_closure_heads = tuple(
        closure_heads_by_leg.get(_leg_index_key(owner.leg_key))
        for owner in owners
        if closure_heads_by_leg.get(_leg_index_key(owner.leg_key)) is not None
    )
    if derived_closure_heads != closure_heads:
        raise ValueError("closure heads must equal the current closure history heads")

    binding_order: _PersistentSequence[PositionScope] = _PersistentSequence.empty()
    binding_by_scope: _PersistentKeyMap[VenueExecutionBinding] = (
        _PersistentKeyMap.empty()
    )
    for binding in execution_bindings:
        if not isinstance(binding, VenueExecutionBinding):
            raise TypeError("execution binding must be VenueExecutionBinding")
        if (
            binding_by_scope.get(_position_scope_index_key(binding.position_scope))
            is not None
        ):
            raise ValueError("execution binding scopes must be unique")
        binding_order, binding_by_scope = _upsert_binding_value(
            binding_order,
            binding_by_scope,
            binding,
        )

    input_ledger: _PersistentSequence[VenueInputRecord] = _PersistentSequence.empty()
    input_by_id: _PersistentKeyMap[VenueInputRecord] = _PersistentKeyMap.empty()
    direct_semantics: _PersistentKeyMap[VenueInputRecord] = _PersistentKeyMap.empty()
    first_inputs_by_fact: _PersistentKeyMap[VenueInputRecord] = (
        _PersistentKeyMap.empty()
    )
    economic_high_water_by_leg: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    from .recovery import (
        HumanCoverage,
        IngestHumanAttestedFill,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
        _BrokerCoverage,
    )

    for record in input_records:
        _require("input record", record, VenueInputRecord)
        key = _input_index_key(record.input_id)
        if input_by_id.get(key) is not None:
            raise ValueError("input identities must be unique")
        commitment = _input_record_commitment(record)
        if record.semantic_alias_of is None:
            semantic_key = _semantic_input_key(record.item)
            if direct_semantics.get(semantic_key) is not None:
                raise ValueError("duplicate direct semantic input")
            direct_semantics = direct_semantics.insert_new(
                semantic_key,
                record,
                commitment,
            )
        input_ledger = input_ledger.append(record, commitment)
        input_by_id = input_by_id.insert_new(key, record, commitment)
        fact_key = getattr(getattr(record.item, "fact", None), "key", None)
        if isinstance(fact_key, ExecutionFactKey):
            encoded_fact_key = _fact_index_key(fact_key)
            if first_inputs_by_fact.get(encoded_fact_key) is None:
                first_inputs_by_fact = first_inputs_by_fact.insert_new(
                    encoded_fact_key,
                    record,
                    commitment,
                )

    human_coverage_ledger: _PersistentSequence[Any] = _PersistentSequence.empty()
    human_coverage_by_root: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    for coverage in human_coverages:
        _require("human coverage", coverage, HumanCoverage)
        (
            human_coverage_ledger,
            human_coverage_by_root,
        ) = _append_coverage_value(
            human_coverage_ledger,
            human_coverage_by_root,
            coverage,
        )
    broker_coverage_ledger: _PersistentSequence[Any] = _PersistentSequence.empty()
    broker_coverage_by_root: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    for coverage in broker_coverages:
        _require("broker coverage", coverage, _BrokerCoverage)
        (
            broker_coverage_ledger,
            broker_coverage_by_root,
        ) = _append_coverage_value(
            broker_coverage_ledger,
            broker_coverage_by_root,
            coverage,
        )
    (
        coverage_current_by_leg,
        coverage_total_by_effect,
        attributed_broker_root_count_by_scope,
        human_interval_index,
        human_broker_fact_index,
    ) = _audit_build_coverage_current_indexes(
        human_coverages,
        broker_coverages,
    )

    reconciliation_ledger: _PersistentSequence[Any] = _PersistentSequence.empty()
    reconciliation_by_input: _PersistentKeyMap[Any] = _PersistentKeyMap.empty()
    unresolved_reconciliation_count_by_leg: _PersistentKeyMap[int] = (
        _PersistentKeyMap.empty()
    )
    reconciliation_count_by_effect: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    canonical_revision_count_by_leg: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    for reconciliation in reconciliations:
        (
            reconciliation_ledger,
            reconciliation_by_input,
            unresolved_reconciliation_count_by_leg,
            reconciliation_count_by_effect,
            canonical_revision_count_by_leg,
            coverage_current_by_leg,
            coverage_total_by_effect,
        ) = _append_reconciliation_value(
            reconciliation_ledger,
            reconciliation_by_input,
            unresolved_reconciliation_count_by_leg,
            reconciliation_count_by_effect,
            canonical_revision_count_by_leg,
            coverage_current_by_leg,
            coverage_total_by_effect,
            reconciliation,
        )

    execution_reconciliation_ledger: _PersistentSequence[
        ExecutionRegistryReconciliationRecord
    ] = _PersistentSequence.empty()
    execution_reconciliation_by_input: _PersistentKeyMap[
        ExecutionRegistryReconciliationRecord
    ] = _PersistentKeyMap.empty()
    unresolved_execution_reconciliation_count_by_scope: _PersistentKeyMap[int] = (
        _PersistentKeyMap.empty()
    )
    unresolved_account_execution_reconciliation_count = 0
    for reconciliation in execution_reconciliations:
        (
            execution_reconciliation_ledger,
            execution_reconciliation_by_input,
            unresolved_execution_reconciliation_count_by_scope,
        ) = _append_execution_reconciliation_value(
            execution_reconciliation_ledger,
            execution_reconciliation_by_input,
            unresolved_execution_reconciliation_count_by_scope,
            reconciliation,
        )
        if not reconciliation.attribution_resolved:
            unresolved_account_execution_reconciliation_count += 1

    for owner in owners:
        head = closure_heads_by_leg.get(_leg_index_key(owner.leg_key))
        current_effect = effect_by_id.get(_effect_index_key(owner.effect_id))
        if current_effect is None:
            continue
        current_coverage = (
            coverage_current_by_leg.get(_leg_index_key(owner.leg_key))
            or _CoverageLegCurrent()
        )
        if not _closure_is_finalization_ready(
            current_effect.effect,
            head,
            current_coverage.canonical_total,
        ):
            continue
        summary = (
            leg_summary_by_effect.get(_effect_index_key(owner.effect_id))
            or _EffectLegSummary()
        )
        leg_summary_by_effect = _set_effect_leg_summary(
            leg_summary_by_effect,
            owner.effect_id,
            replace(
                summary,
                finalization_ready_count=summary.finalization_ready_count + 1,
            ),
        )

    result = object.__new__(VenueRecoveryBook)
    for name in _EVOLVABLE_BOOK_FIELDS:
        object.__setattr__(result, name, changes.get(name, getattr(book, name)))
    object.__setattr__(result, "_effect_order", effect_order)
    object.__setattr__(result, "_effect_by_id", effect_by_id)
    object.__setattr__(
        result,
        "_effect_by_request_occurrence",
        effect_by_request_occurrence,
    )
    object.__setattr__(
        result,
        "_effect_by_client_order",
        effect_by_client_order,
    )
    object.__setattr__(
        result,
        "_authority_epoch_by_scope",
        authority_epoch_by_scope,
    )
    object.__setattr__(result, "_account_authority_epoch", account_authority_epoch)
    object.__setattr__(
        result,
        "_contradiction_order_by_effect",
        contradiction_order_by_effect,
    )
    object.__setattr__(result, "_claim_order", claim_order)
    object.__setattr__(result, "_claim_by_effect", claim_by_effect)
    object.__setattr__(result, "_claim_by_occurrence", claim_by_occurrence)
    object.__setattr__(result, "_owner_order", owner_order)
    object.__setattr__(result, "_owner_by_leg", owner_by_leg)
    object.__setattr__(result, "_leg_current_by_leg", leg_current_by_leg)
    object.__setattr__(result, "_leg_summary_by_effect", leg_summary_by_effect)
    object.__setattr__(result, "_binding_order", binding_order)
    object.__setattr__(result, "_binding_by_scope", binding_by_scope)
    object.__setattr__(result, "_closure_ledger", closure_ledger)
    object.__setattr__(result, "_closure_by_id", closure_by_id)
    object.__setattr__(result, "_closure_head_by_leg", closure_heads_by_leg)
    object.__setattr__(result, "_input_ledger", input_ledger)
    object.__setattr__(result, "_input_by_id", input_by_id)
    object.__setattr__(result, "_direct_input_by_semantic", direct_semantics)
    object.__setattr__(result, "_first_input_by_fact", first_inputs_by_fact)
    object.__setattr__(
        result,
        "_economic_high_water_by_leg",
        economic_high_water_by_leg,
    )
    object.__setattr__(result, "_human_coverage_ledger", human_coverage_ledger)
    object.__setattr__(
        result,
        "_human_coverage_by_root",
        human_coverage_by_root,
    )
    object.__setattr__(result, "_broker_coverage_ledger", broker_coverage_ledger)
    object.__setattr__(
        result,
        "_broker_coverage_by_root",
        broker_coverage_by_root,
    )
    object.__setattr__(
        result,
        "_coverage_provenance_by_scope",
        _PersistentKeyMap.empty(),
    )
    object.__setattr__(
        result,
        "_coverage_current_by_leg",
        coverage_current_by_leg,
    )
    object.__setattr__(
        result,
        "_coverage_total_by_effect",
        coverage_total_by_effect,
    )
    object.__setattr__(
        result,
        "_attributed_broker_root_count_by_scope",
        attributed_broker_root_count_by_scope,
    )
    object.__setattr__(result, "_human_interval_index", human_interval_index)
    object.__setattr__(
        result,
        "_human_broker_fact_index",
        human_broker_fact_index,
    )
    object.__setattr__(result, "_reconciliation_ledger", reconciliation_ledger)
    object.__setattr__(
        result,
        "_reconciliation_by_input",
        reconciliation_by_input,
    )
    object.__setattr__(
        result,
        "_unresolved_reconciliation_count_by_leg",
        unresolved_reconciliation_count_by_leg,
    )
    object.__setattr__(
        result,
        "_reconciliation_count_by_effect",
        reconciliation_count_by_effect,
    )
    object.__setattr__(
        result,
        "_canonical_revision_count_by_leg",
        canonical_revision_count_by_leg,
    )
    object.__setattr__(
        result,
        "_execution_reconciliation_ledger",
        execution_reconciliation_ledger,
    )
    object.__setattr__(
        result,
        "_execution_reconciliation_by_input",
        execution_reconciliation_by_input,
    )
    object.__setattr__(
        result,
        "_registry_transition_ledger",
        book._registry_transition_ledger,
    )
    object.__setattr__(
        result,
        "_registry_transition_head_commitment",
        book._registry_transition_head_commitment,
    )
    object.__setattr__(
        result,
        "_unresolved_execution_reconciliation_count_by_scope",
        unresolved_execution_reconciliation_count_by_scope,
    )
    object.__setattr__(
        result,
        "_unresolved_account_execution_reconciliation_count",
        unresolved_account_execution_reconciliation_count,
    )
    result._validate_full()
    if not result._execution_reconciliation_cursor_matches(execution):
        raise ValueError(
            "external execution reconciliation cursor does not close the audit book"
        )

    from .recovery import RevisionReconciliationRecord

    canonical_economic_inputs = {
        *(coverage.source_input_id for coverage in result.human_coverages),
        *(
            coverage.broker_source_input_id
            for coverage in result.human_coverages
            if coverage.broker_source_input_id is not None
        ),
        *(coverage.root_source_input_id for coverage in result.broker_coverages),
        *(
            record.input_id
            for record in input_records
            if isinstance(record.item, RecordBrokerRevisionEvidence)
            and result._broker_coverage_for_root(record.item.fact.root_key) is not None
            and (first := result._fact_input_record(record.item.fact.key)) is not None
            and first.input_id == record.input_id
            and (observation := execution.seen_facts.get(record.item.fact.key))
            is not None
            and observation.classification
            is not FirstObservationClassification.RECONCILIATION_REQUIRED
        ),
        *(
            record.input_id
            for record in result.reconciliations
            if isinstance(record, RevisionReconciliationRecord)
            and record.canonical_applied
        ),
    }
    for record in input_records:
        if record.input_id not in canonical_economic_inputs:
            continue
        item = record.item
        if isinstance(item, IngestHumanAttestedFill):
            economic_leg_key = item.fact.leg_key
            candidate = item.fact.resulting_cumulative_quantity.value
        elif isinstance(item, RecordBrokerFillEvidence):
            economic_leg_key = item.leg_key
            candidate = max(
                item.prior_cumulative_quantity.value,
                item.resulting_cumulative_quantity.value,
            )
        elif isinstance(item, RecordBrokerRevisionEvidence):
            economic_leg_key = item.leg_key
            candidate = max(
                item.prior_venue_cumulative_quantity.value,
                item.resulting_venue_cumulative_quantity.value,
            )
        else:
            continue
        economic_key = _leg_index_key(economic_leg_key)
        prior_high_water = economic_high_water_by_leg.get(economic_key)
        retained_high_water = max(prior_high_water or 0, candidate)
        if retained_high_water == prior_high_water:
            continue
        high_water_commitment = _commit_parts(
            b"execution-core/venue-economic-high-water/v1",
            _encode_text(str(retained_high_water)),
        )
        if prior_high_water is None:
            economic_high_water_by_leg = economic_high_water_by_leg.insert_new(
                economic_key,
                retained_high_water,
                high_water_commitment,
            )
        else:
            economic_high_water_by_leg = economic_high_water_by_leg.replace_existing(
                economic_key,
                retained_high_water,
                high_water_commitment,
            )
    object.__setattr__(
        result,
        "_economic_high_water_by_leg",
        economic_high_water_by_leg,
    )
    if result.effects:
        if (
            result.execution_registry_count != execution.seen_facts.count
            or result.execution_registry_commitment != execution.seen_facts.commitment
        ):
            raise ValueError(
                "verified audit hydration requires the exact account registry"
            )
        from .recovery import _replay_venue_hydration_snapshot

        authorized_human_facts = tuple(
            coverage.fact for coverage in result.human_coverages
        )
        authorized_corroborations = tuple(
            cast(BrokerFillFact, coverage.broker_fact)
            for coverage in result.human_coverages
            if coverage.broker_corroborated and coverage.broker_fact is not None
        )
        replayed_by_scope: dict[PositionScope, ExecutionSnapshot] = {}
        for binding in result.execution_bindings:
            binding_replay = _replay_venue_hydration_snapshot(
                binding.position_scope,
                execution.seen_facts,
                authorized_human_facts=authorized_human_facts,
                authorized_corroborations=authorized_corroborations,
            )
            replayed_by_scope[binding.position_scope] = binding_replay
            if not _binding_matches_execution(binding, binding_replay):
                raise ValueError(
                    "verified audit hydration found a stale symbol binding"
                )
        supplied = replayed_by_scope.get(execution.position.scope)
        if supplied is None or not result._execution_matches(
            execution,
            execution.position.scope,
        ):
            raise ValueError(
                "verified audit hydration requires exact execution/root provenance pair"
            )
        for human_coverage in result.human_coverages:
            human_replay = replayed_by_scope.get(
                human_coverage.fact.scope.position_scope
            )
            if human_replay is None or not _execution_head_matches_fact(
                human_replay.root_heads.get(human_coverage.fact.root_key),
                human_coverage.fact,
            ):
                raise ValueError(
                    "human coverage is absent from its paired account registry"
                )
        for broker_coverage in result.broker_coverages:
            broker_replay = replayed_by_scope.get(
                broker_coverage.fact.scope.position_scope
            )
            if broker_replay is None or not _execution_head_matches_fact(
                broker_replay.root_heads.get(broker_coverage.head_fact.root_key),
                broker_coverage.head_fact,
            ):
                raise ValueError(
                    "broker coverage is absent from its paired account registry"
                )

        coverage_provenance: _PersistentKeyMap[_CoverageProvenance] = (
            _PersistentKeyMap.empty()
        )
        coverage_facts = (
            *(coverage.fact for coverage in result.human_coverages),
            *(coverage.head_fact for coverage in result.broker_coverages),
        )
        for coverage_fact in coverage_facts:
            position_scope = coverage_fact.scope.position_scope
            replayed_execution = replayed_by_scope[position_scope]
            existing = coverage_provenance.get(
                _position_scope_index_key(position_scope)
            )
            roots = (
                existing.roots if existing is not None else _PersistentKeyMap.empty()
            )
            encoded_root = _coverage_root_index_key(coverage_fact.root_key)
            fact_commitment = _canonical_value_commitment(coverage_fact)
            if roots.get(encoded_root) is not None:
                raise ValueError("coverage provenance roots must be unique")
            roots = roots.insert_new(
                encoded_root,
                fact_commitment,
                fact_commitment,
            )
            coverage_provenance = _set_coverage_provenance(
                coverage_provenance,
                position_scope,
                _CoverageProvenance(
                    roots=roots,
                    root_heads_commitment=(replayed_execution.root_heads.commitment),
                ),
            )
        object.__setattr__(
            result,
            "_coverage_provenance_by_scope",
            coverage_provenance,
        )

        attributed_broker_facts = {
            *(
                coverage.broker_fact.key
                for coverage in result.human_coverages
                if coverage.broker_fact is not None
            ),
            *(coverage.fact.key for coverage in result.broker_coverages),
            *(record.fact.key for record in result.reconciliations),
        }
        for record in input_records:
            source_fact = getattr(record.item, "fact", None)
            if not isinstance(
                source_fact,
                (BrokerTradeCorrectFact, BrokerTradeBustFact),
            ):
                continue
            first = result._fact_input_record(source_fact.key)
            observation = execution.seen_facts.get(source_fact.key)
            if (
                first is not None
                and first.input_id == record.input_id
                and observation is not None
                and observation.classification
                is not FirstObservationClassification.RECONCILIATION_REQUIRED
            ):
                attributed_broker_facts.add(source_fact.key)

        first_catch_up = next(
            (
                record.item
                for record in input_records
                if type(record.item) is CatchUpExecutionRegistry
            ),
            None,
        )
        externally_attributable_start = (
            execution.seen_facts.count
            if first_catch_up is None
            else cast(
                CatchUpExecutionRegistry,
                first_catch_up,
            ).prior_account_registry_count
        )

        for index in range(execution.seen_facts.count):
            observation = execution.seen_facts.observation_at(index)
            fact = observation.fact
            if not isinstance(
                fact,
                (BrokerFillFact, BrokerTradeCorrectFact, BrokerTradeBustFact),
            ):
                continue
            observed_leg_key = VenueLegKey(
                broker=fact.scope.broker,
                environment=fact.scope.environment,
                account=fact.scope.account,
                order_id=fact.scope.order_id,
            )
            owner = result.owner(observed_leg_key)
            covering_registry_outcomes = tuple(
                record
                for record in result.execution_reconciliations
                if record.position_scope == fact.scope.position_scope
                and record.prior_registry_count <= index
                and index < record.resulting_registry_count
            )
            unresolved_origins = tuple(
                record
                for record in covering_registry_outcomes
                if not record.attribution_resolved
            )
            if owner is None:
                if (
                    index >= externally_attributable_start
                    and fact.key not in attributed_broker_facts
                    and len(unresolved_origins) != 1
                ):
                    raise ValueError(
                        "unowned broker observation lacks one exact external source origin"
                    )
                continue
            effect = result.effect(owner.effect_id)
            if effect is None or (
                fact.scope.symbol_id != effect.scope.symbol_id
                or fact.scope.side is not effect.scope.side
            ):
                if len(unresolved_origins) != 1:
                    raise ValueError(
                        "owned broker observation contradicts its venue effect scope"
                    )
                continue
            if fact.key in attributed_broker_facts:
                continue
            if len(unresolved_origins) != 1:
                raise ValueError(
                    "owned broker observation lacks one exact external source origin"
                )
    return result


def _execution_binding_for_snapshot(
    execution: ExecutionSnapshot,
) -> VenueExecutionBinding:
    return VenueExecutionBinding(
        position_scope=execution.position.scope,
        position_commitment=execution.position.commitment,
        root_heads_commitment=execution.root_heads.commitment,
        integrity_bits=execution.integrity.value,
    )


def _book_with_input(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
    **changes: Any,
) -> VenueRecoveryBook:
    return evolve(
        book,
        execution,
        execution,
        item=item,
        **changes,
    )


def _book_with_input_and_execution(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    item: object,
    prior_execution: ExecutionSnapshot,
    resulting_execution: ExecutionSnapshot,
    *,
    canonical_economic_input: bool = False,
    **changes: Any,
) -> VenueRecoveryBook:
    unresolved_execution = (
        PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    if (
        resulting_execution.integrity & unresolved_execution
        and changes.get("_demote_scope") is None
    ):
        changes["_demote_scope"] = resulting_execution.position.scope
    return evolve(
        book,
        prior_execution,
        resulting_execution,
        item=item,
        canonical_economic_input=canonical_economic_input,
        execution_registry_count=resulting_execution.seen_facts.count,
        execution_registry_commitment=resulting_execution.seen_facts.commitment,
        _binding_upserts=(_execution_binding_for_snapshot(resulting_execution),),
        **changes,
    )


def _book_to_execution(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    prior_execution: ExecutionSnapshot,
    resulting_execution: ExecutionSnapshot,
) -> VenueRecoveryBook:
    unresolved_execution = (
        PositionIntegrity.EXECUTION_FACT_CONFLICT
        | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
    )
    return evolve(
        book,
        prior_execution,
        resulting_execution,
        _demote_scope=(
            resulting_execution.position.scope
            if resulting_execution.integrity & unresolved_execution
            else None
        ),
        execution_registry_count=resulting_execution.seen_facts.count,
        execution_registry_commitment=resulting_execution.seen_facts.commitment,
        _binding_upserts=(_execution_binding_for_snapshot(resulting_execution),),
    )


def _book_replace_effect(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    effect: BrokerEffect,
) -> VenueRecoveryBook:
    if book._current_effect(effect.effect_id) is None:
        raise KeyError("effect is not registered")
    return evolve(
        book,
        execution,
        execution,
        _effect_replace=effect,
    )


def _book_close_attempt(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    *,
    prior_execution: ExecutionSnapshot,
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
    resulting_execution: ExecutionSnapshot | None = None,
    evolution_changes: dict[str, Any] | None = None,
    actor: ActorId | None = None,
    reason: str | None = None,
    evidence_digest: bytes | None = None,
    canonical_economic_input: bool = False,
) -> VenueRecoveryBook:
    owner = book.owner(leg_key)
    active = book.active_attempt(leg_key)
    head = book.closure_head(leg_key)
    if owner is None or (active is None) == (head is None):
        raise ValueError("owner must have exactly one current leg representation")
    if book._closure_by_id.get(_closure_index_key(closure_id)) is not None:
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
    changes: dict[str, Any] = {}
    if evolution_changes is not None:
        changes.update(evolution_changes)
    if resulting_execution is not None:
        unresolved_execution = (
            PositionIntegrity.EXECUTION_FACT_CONFLICT
            | PositionIntegrity.EXECUTION_RECONCILIATION_REQUIRED
        )
        if (
            resulting_execution.integrity & unresolved_execution
            and changes.get("_demote_scope") is None
        ):
            changes["_demote_scope"] = resulting_execution.position.scope
        next_book = evolve(
            book,
            prior_execution,
            resulting_execution,
            item=source_input,
            closure=closure,
            canonical_economic_input=canonical_economic_input,
            execution_registry_count=resulting_execution.seen_facts.count,
            execution_registry_commitment=resulting_execution.seen_facts.commitment,
            _binding_upserts=(_execution_binding_for_snapshot(resulting_execution),),
            **changes,
        )
        return _maybe_finalize_effect(
            evolve,
            next_book,
            owner.effect_id,
            resulting_execution,
        )
    next_book = evolve(
        book,
        prior_execution,
        prior_execution,
        item=source_input,
        closure=closure,
        canonical_economic_input=canonical_economic_input,
        **changes,
    )
    return _maybe_finalize_effect(
        evolve,
        next_book,
        owner.effect_id,
        prior_execution,
    )


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

    return book._coverage_current(leg_key).canonical_total


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
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RequestedEffect,
) -> VenueRecoveryBook | None:
    if book._current_effect(item.effect_id) is not None:
        return None
    if book._has_client_order(item.client_order_id) or book._has_request_occurrence(
        item.request_occurrence_id
    ):
        return None
    effect = BrokerEffect(scope=_effect_scope(book, item))
    return _book_with_input_and_execution(
        evolve,
        book,
        item,
        execution,
        execution,
        _effect_append=effect,
    )


def _same_leg_scope(scope: VenueScope, leg_key: VenueLegKey) -> bool:
    return (
        scope.broker == leg_key.broker
        and scope.environment == leg_key.environment
        and scope.account == leg_key.account
    )


def _record_claim(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RecordDispatchClaim,
) -> VenueRecoveryBook | None:
    effect = book._current_effect(item.effect_id)
    if (
        effect is None
        or effect.state is not BrokerEffectState.REQUESTED
        or effect.claim_occurrence_id is not None
        or book._has_claim_occurrence(item.claim_occurrence_id)
    ):
        return None
    claimed = replace(
        effect,
        state=BrokerEffectState.DISPATCH_CLAIMED,
        claim_occurrence_id=item.claim_occurrence_id,
    )
    claim = DispatchClaim(effect.scope, item.claim_occurrence_id)
    return _book_with_input(
        evolve,
        book,
        execution,
        item,
        _effect_replace=claimed,
        _claim_append=claim,
    )


def _replace_effect_state(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    effect: BrokerEffect,
    state: BrokerEffectState,
    item: object,
) -> VenueRecoveryBook:
    updated = replace(effect, state=state)
    return _book_with_input(
        evolve,
        book,
        execution,
        item,
        _effect_replace=updated,
    )


def _discover_leg(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: DiscoverVenueLeg,
) -> tuple[VenueRecoveryBook | None, VenueRecoveryDisposition]:
    effect = book._current_effect(item.effect_id)
    if effect is None or not _same_leg_scope(book.scope, item.leg_key):
        return None, VenueRecoveryDisposition.REFUSED
    current_owner = book.owner(item.leg_key)
    if current_owner is not None:
        if current_owner.effect_id != item.effect_id:
            return None, VenueRecoveryDisposition.CONFLICT
        if current_owner.observation_id == item.observation_id:
            return (
                _book_with_input(evolve, book, execution, item),
                VenueRecoveryDisposition.APPLIED,
            )
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
    contradiction: AcceptanceContradiction | None = None
    disposition = VenueRecoveryDisposition.APPLIED
    if effect.acceptance_set_state is AcceptanceSetState.CLOSED:
        contradiction = AcceptanceContradiction(
            item.leg_key,
            item.observation_id,
        )
        next_effect = replace(
            effect,
            state=(
                BrokerEffectState.NEEDS_REVIEW
                if effect.state is BrokerEffectState.OPERATOR_RECONCILED
                else effect.state
            ),
            acceptance_set_state=AcceptanceSetState.INVALIDATED,
        )
        disposition = VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    elif effect.acceptance_set_state is AcceptanceSetState.INVALIDATED:
        contradiction = AcceptanceContradiction(
            item.leg_key,
            item.observation_id,
        )
    next_book = _book_with_input(
        evolve,
        book,
        execution,
        item,
        _effect_replace=next_effect,
        _contradiction_append=(
            (item.effect_id, contradiction) if contradiction is not None else None
        ),
        _owner_and_attempt_append=(owner, attempt),
    )
    return next_book, disposition


def _observe_status(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: ObserveVenueStatus,
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
                evolve,
                book,
                prior_execution=execution,
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
            evolve,
            book,
            execution,
            item,
            _attempt_replace=updated,
        )

    if head is None or not is_terminal:
        return None
    if item.cumulative_quantity.value <= head.observed_cumulative_quantity.value:
        return None
    assert item.closure_id is not None
    assert item.evidence_reference is not None
    return _book_close_attempt(
        evolve,
        book,
        prior_execution=execution,
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
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    effect_id: EffectId,
    execution: ExecutionSnapshot,
) -> VenueRecoveryBook:
    """Close the recovery lifecycle only after its independent closure gates."""

    effect = book._current_effect(effect_id)
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
        or book._has_effect_reconciliation(effect_id)
        or book._has_unresolved_execution_reconciliation(effect.scope.position_scope)
    ):
        return book
    summary = book._leg_summary(effect_id)
    if (
        summary.owner_count == 0
        or summary.active_count != 0
        or summary.finalization_ready_count != summary.owner_count
    ):
        return book
    return _book_replace_effect(
        evolve,
        book,
        execution,
        replace(effect, state=BrokerEffectState.OPERATOR_RECONCILED),
    )


def _close_acceptance_set(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: CloseAcceptanceSet,
) -> VenueRecoveryBook | None:
    effect = book._current_effect(item.effect_id)
    if effect is None or effect.acceptance_set_state is not AcceptanceSetState.OPEN:
        return None
    proof = item.proof
    if (
        proof.effect_scope != effect.scope
        or proof.claim_occurrence_id != effect.claim_occurrence_id
    ):
        return None
    if book._leg_summary(item.effect_id).active_count:
        return None
    if proof.kind is AcceptanceProofKind.NEVER_DISPATCHED:
        if (
            effect.state is not BrokerEffectState.CANCELED_BEFORE_DISPATCH
            or effect.claim_occurrence_id is not None
            or book._claim_for_effect(item.effect_id) is not None
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
        evolve,
        book,
        execution,
        item,
        _effect_replace=closed,
    )
    return _maybe_finalize_effect(
        evolve,
        closed_book,
        item.effect_id,
        execution,
    )


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


def _execution_is_exact_genesis(execution: ExecutionSnapshot) -> bool:
    """Authenticate the only snapshot admitted to a brand-new venue book."""

    genesis = ExecutionSnapshot.flat(execution.position.scope)
    return execution.commitment == genesis.commitment


def _apply_execution_registry_catch_up(
    book: VenueRecoveryBook,
    target: ExecutionSnapshot,
    item: CatchUpExecutionRegistry,
    evolve: _BookEvolver,
    transition: _TransitionFactory,
) -> VenueRecoveryTransition:
    """Apply one monotonic account-registry projection without replaying economics."""

    if type(item.source_execution) is not ExecutionSnapshot:
        raise TypeError("source_execution must be the exact ExecutionSnapshot type")
    source = item.source_execution
    _require_execution_components(
        source.position,
        source.integrity,
        source.root_heads,
        source.seen_facts,
    )
    target_scope = target.position.scope
    source_scope = source.position.scope
    target_binding = book.execution_binding(target_scope)
    book_transition_count, book_transition_head = book._reconciliation_cursor()
    account_reconciliation_required = (
        book._unresolved_account_execution_reconciliation_count > 0
    )
    replay = book._input_record(item.input_id)
    if replay is not None:
        if not _input_commands_equal(
            replay.item,
            item,
            include_input_id=True,
        ):
            return transition(
                book,
                target,
                target,
                VenueRecoveryDisposition.CONFLICT,
                item=item,
                quantity_delta=0,
            )
    if item.target_scope != target_scope:
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.REFUSED,
            item=item,
            quantity_delta=0,
        )
    if replay is not None:
        if book._execution_pair_matches_fast(target):
            reconciliation = book._execution_reconciliation_for_input(item.input_id)
            disposition = (
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED
                if reconciliation is not None
                and not reconciliation.attribution_resolved
                else VenueRecoveryDisposition.EXACT_REPLAY
            )
            return transition(
                book,
                target,
                target,
                disposition,
                item=item,
                quantity_delta=0,
            )

    same_account = (
        target_scope.broker == source_scope.broker == book.scope.broker
        and target_scope.environment
        == source_scope.environment
        == book.scope.environment
        and target_scope.account == source_scope.account == book.scope.account
    )
    if not same_account:
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.REFUSED,
            item=item,
            quantity_delta=0,
        )
    if (
        not book._execution_reconciliation_cursor_is_prefix(target)
        or not book._execution_reconciliation_cursor_is_prefix(source)
    ):
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            item=item,
            quantity_delta=0,
        )
    if (
        item.target_checkpoint != VenueExecutionCheckpoint.from_execution(target)
        or item.prior_account_registry_count != book.execution_registry_count
        or item.prior_account_registry_commitment
        != book.execution_registry_commitment
    ):
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.REFUSED,
            item=item,
            quantity_delta=0,
        )
    source_binding = book.execution_binding(source_scope)
    if item.prior_source_binding != source_binding:
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.REFUSED,
            item=item,
            quantity_delta=0,
        )
    if source_binding is None:
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.REFUSED,
            item=item,
            quantity_delta=0,
        )

    if (
        target_binding is None
        or not book._execution_symbol_matches(target, target_scope)
        or not source.seen_facts.has_prefix(
            target.seen_facts.count,
            target.seen_facts.commitment,
        )
        or book.execution_registry_count is None
        or book.execution_registry_commitment is None
        or not source.seen_facts.has_prefix(
            book.execution_registry_count,
            book.execution_registry_commitment,
        )
        or not source.seen_facts.suffix_belongs_to(
            book.execution_registry_count,
            source_scope,
        )
    ):
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            item=item,
            quantity_delta=0,
        )

    source_binding_changed = not _binding_matches_execution(source_binding, source)
    if (
        source.seen_facts.count > book.execution_registry_count
        and not source_binding_changed
    ):
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            item=item,
            quantity_delta=0,
        )
    if (
        book.execution_registry_count == source.seen_facts.count
        and book.execution_registry_commitment == source.seen_facts.commitment
        and source_binding_changed
    ):
        return transition(
            book,
            target,
            target,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
            item=item,
            quantity_delta=0,
        )

    if source_scope == target_scope:
        next_execution = source
    else:
        try:
            next_execution = _project_execution_registry(
                target,
                source,
                reconciliation_transition_count=book_transition_count,
                reconciliation_transition_head=book_transition_head,
            )
        except ValueError:
            return transition(
                book,
                target,
                target,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
                item=item,
                quantity_delta=0,
            )

    next_execution = _bind_execution_reconciliation_cursor(
        next_execution,
        transition_count=book_transition_count,
        transition_head=book_transition_head,
        account_reconciliation_required=account_reconciliation_required,
    )

    if replay is not None:
        if not book._execution_matches(next_execution, target_scope):
            return transition(
                book,
                target,
                target,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
                item=item,
                quantity_delta=0,
            )
        reconciliation = book._execution_reconciliation_for_input(item.input_id)
        disposition = (
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED
            if reconciliation is not None and not reconciliation.attribution_resolved
            else VenueRecoveryDisposition.EXACT_REPLAY
        )
        return transition(
            book,
            target,
            next_execution,
            disposition,
            item=item,
            quantity_delta=0,
        )

    if source.seen_facts.count == book.execution_registry_count:
        if target.seen_facts.count == source.seen_facts.count:
            return transition(
                book,
                target,
                target,
                VenueRecoveryDisposition.REFUSED,
                item=item,
                quantity_delta=0,
            )
        projection_outcome = _ResolvedRegistryProjectionOutcome(
            input_id=item.input_id,
            command_commitment=_catch_up_input_commitment(item),
            target_checkpoint=item.target_checkpoint,
            source_binding=source_binding,
            resulting_registry_count=source.seen_facts.count,
            resulting_registry_commitment=source.seen_facts.commitment,
            reason="target registry projection retained exact source and binding proof",
        )
        projection_proof = _registry_transition_proof_for(
            ordinal=book_transition_count + 1,
            predecessor_commitment=book._registry_transition_head_commitment,
            venue_scope=book.scope,
            item=item,
            outcome=projection_outcome,
        )
        next_execution = _bind_execution_reconciliation_cursor(
            next_execution,
            transition_count=book_transition_count + 1,
            transition_head=projection_proof.commitment,
            account_reconciliation_required=account_reconciliation_required,
        )
        next_book = evolve(
            book,
            target,
            next_execution,
            item=item,
            execution_registry_count=source.seen_facts.count,
            execution_registry_commitment=source.seen_facts.commitment,
            _binding_upserts=(_execution_binding_for_snapshot(next_execution),),
            _execution_reconciliation_append=projection_outcome,
        )
        return transition(
            next_book,
            target,
            next_execution,
            VenueRecoveryDisposition.APPLIED,
            item=item,
            quantity_delta=0,
        )

    prior_source_binding = source_binding
    registry_record = _UnresolvedRegistryAdvanceOutcome(
        input_id=item.input_id,
        command_commitment=_catch_up_input_commitment(item),
        target_checkpoint=item.target_checkpoint,
        prior_account_registry_count=book.execution_registry_count,
        prior_account_registry_commitment=book.execution_registry_commitment,
        prior_source_binding=prior_source_binding,
        resulting_source_binding=_execution_binding_for_snapshot(source),
        resulting_registry_count=source.seen_facts.count,
        resulting_registry_commitment=source.seen_facts.commitment,
        reason="canonical source advanced before venue ownership attribution",
    )
    registry_proof = _registry_transition_proof_for(
        ordinal=book_transition_count + 1,
        predecessor_commitment=book._registry_transition_head_commitment,
        venue_scope=book.scope,
        item=item,
        outcome=registry_record,
    )
    next_execution = _bind_execution_reconciliation_cursor(
        next_execution,
        transition_count=book_transition_count + 1,
        transition_head=registry_proof.commitment,
        account_reconciliation_required=True,
    )
    next_bindings = [_execution_binding_for_snapshot(next_execution)]
    if source_binding_changed:
        assert source_binding is not None
        if source_scope != next_execution.position.scope:
            next_bindings.append(_execution_binding_for_snapshot(source))
    disposition = (
        VenueRecoveryDisposition.RECONCILIATION_REQUIRED
        if source_binding_changed
        else VenueRecoveryDisposition.APPLIED
    )

    next_book = evolve(
        book,
        target,
        next_execution,
        item=item,
        _demote_scope=source_scope if source_binding_changed else None,
        execution_registry_count=source.seen_facts.count,
        execution_registry_commitment=source.seen_facts.commitment,
        _binding_upserts=tuple(next_bindings),
        _execution_reconciliation_append=registry_record,
    )
    return transition(
        next_book,
        target,
        next_execution,
        disposition,
        item=item,
        quantity_delta=0,
    )


def apply_venue_recovery_input(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> VenueRecoveryTransition:
    """Apply one exact immutable venue or recovery input without I/O."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be the exact opaque VenueRecoveryBook type")
    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    _require_execution_components(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
    )

    def evolve(
        current: VenueRecoveryBook,
        prior_execution: ExecutionSnapshot,
        resulting_execution: ExecutionSnapshot,
        *,
        item: object | None = None,
        closure: VenueTerminalClosure | None = None,
        canonical_economic_input: bool = False,
        **changes: Any,
    ) -> VenueRecoveryBook:
        """Turn one reducer-owned delta into the next authenticated checkpoint."""

        human_coverage_append = changes.pop("_human_coverage_append", None)
        human_coverage_replace = changes.pop("_human_coverage_replace", None)
        broker_coverage_append = changes.pop("_broker_coverage_append", None)
        broker_coverage_replace = changes.pop("_broker_coverage_replace", None)
        reconciliation_append = changes.pop("_reconciliation_append", None)
        execution_reconciliation_append = changes.pop(
            "_execution_reconciliation_append",
            None,
        )
        effect_append = changes.pop("_effect_append", None)
        effect_replace = changes.pop("_effect_replace", None)
        contradiction_append = changes.pop("_contradiction_append", None)
        claim_append = changes.pop("_claim_append", None)
        owner_and_attempt_append = changes.pop("_owner_and_attempt_append", None)
        attempt_replace = changes.pop("_attempt_replace", None)
        binding_upserts = changes.pop("_binding_upserts", ())
        demote_scope = changes.pop("_demote_scope", None)
        unknown = set(changes) - _EVOLVABLE_BOOK_FIELDS
        if unknown:
            raise TypeError(
                f"unsupported venue checkpoint evolution: {sorted(unknown)!r}"
            )
        prior_pair_matches = current._execution_pair_matches_fast(prior_execution)
        registering_new_symbol = bool(
            isinstance(item, RequestedEffect)
            and current.execution_registry_count == prior_execution.seen_facts.count
            and current.execution_registry_commitment
            == prior_execution.seen_facts.commitment
            and current.execution_binding(prior_execution.position.scope) is None
        )
        catching_up_registry = bool(
            isinstance(item, CatchUpExecutionRegistry)
            and current._execution_binding_matches(prior_execution)
            and resulting_execution.seen_facts.commitment
            == item.source_execution.seen_facts.commitment
            and changes.get("execution_registry_commitment")
            == resulting_execution.seen_facts.commitment
            and changes.get("execution_registry_count")
            == resulting_execution.seen_facts.count
        )
        if current._effect_order.length and not (
            prior_pair_matches or registering_new_symbol or catching_up_registry
        ):
            raise ValueError(
                "venue checkpoint evolution requires its exact prior execution pair"
            )

        input_ledger = current._input_ledger
        input_by_id = current._input_by_id
        direct_semantics = current._direct_input_by_semantic
        first_inputs_by_fact = current._first_input_by_fact
        economic_high_water_by_leg = current._economic_high_water_by_leg
        if item is not None:
            (
                input_ledger,
                input_by_id,
                direct_semantics,
                first_inputs_by_fact,
            ) = _append_input_proof(current, item)
            if canonical_economic_input:
                economic_high_water_by_leg = _advance_economic_high_water(
                    economic_high_water_by_leg,
                    item,
                    resulting_execution,
                )

        closure_ledger = current._closure_ledger
        closure_by_id = current._closure_by_id
        closure_heads_by_leg = current._closure_head_by_leg
        if closure is not None:
            (
                closure_ledger,
                closure_by_id,
                closure_heads_by_leg,
            ) = _append_closure_proof(current, closure)

        human_coverage_ledger = current._human_coverage_ledger
        human_coverage_by_root = current._human_coverage_by_root
        if human_coverage_append is not None:
            if human_coverage_replace is not None:
                raise ValueError("human coverage cannot append and replace together")
            (
                human_coverage_ledger,
                human_coverage_by_root,
            ) = _append_coverage_value(
                human_coverage_ledger,
                human_coverage_by_root,
                human_coverage_append,
            )
        elif human_coverage_replace is not None:
            if (
                type(human_coverage_replace) is not tuple
                or len(human_coverage_replace) != 2
            ):
                raise TypeError("human coverage replacement must be a pair")
            human_coverage_ledger = _replace_coverage_value(
                human_coverage_ledger,
                human_coverage_by_root,
                human_coverage_replace[0],
                human_coverage_replace[1],
            )

        broker_coverage_ledger = current._broker_coverage_ledger
        broker_coverage_by_root = current._broker_coverage_by_root
        if broker_coverage_append is not None:
            if broker_coverage_replace is not None:
                raise ValueError("broker coverage cannot append and replace together")
            (
                broker_coverage_ledger,
                broker_coverage_by_root,
            ) = _append_coverage_value(
                broker_coverage_ledger,
                broker_coverage_by_root,
                broker_coverage_append,
            )
        elif broker_coverage_replace is not None:
            if (
                type(broker_coverage_replace) is not tuple
                or len(broker_coverage_replace) != 2
            ):
                raise TypeError("broker coverage replacement must be a pair")
            broker_coverage_ledger = _replace_coverage_value(
                broker_coverage_ledger,
                broker_coverage_by_root,
                broker_coverage_replace[0],
                broker_coverage_replace[1],
            )

        (
            coverage_current_by_leg,
            coverage_total_by_effect,
            attributed_broker_root_count_by_scope,
            human_interval_index,
            human_broker_fact_index,
        ) = _evolve_coverage_current_indexes(
            current,
            human_coverage_ledger,
            broker_coverage_ledger,
            human_append=human_coverage_append,
            human_replace=human_coverage_replace,
            broker_append=broker_coverage_append,
            broker_replace=broker_coverage_replace,
        )

        reconciliation_ledger = current._reconciliation_ledger
        reconciliation_by_input = current._reconciliation_by_input
        unresolved_reconciliation_count_by_leg = (
            current._unresolved_reconciliation_count_by_leg
        )
        reconciliation_count_by_effect = current._reconciliation_count_by_effect
        canonical_revision_count_by_leg = current._canonical_revision_count_by_leg
        if reconciliation_append is not None:
            (
                reconciliation_ledger,
                reconciliation_by_input,
                unresolved_reconciliation_count_by_leg,
                reconciliation_count_by_effect,
                canonical_revision_count_by_leg,
                coverage_current_by_leg,
                coverage_total_by_effect,
            ) = _append_reconciliation_value(
                reconciliation_ledger,
                reconciliation_by_input,
                unresolved_reconciliation_count_by_leg,
                reconciliation_count_by_effect,
                canonical_revision_count_by_leg,
                coverage_current_by_leg,
                coverage_total_by_effect,
                reconciliation_append,
            )

        execution_reconciliation_ledger = current._execution_reconciliation_ledger
        execution_reconciliation_by_input = current._execution_reconciliation_by_input
        unresolved_execution_reconciliation_count_by_scope = (
            current._unresolved_execution_reconciliation_count_by_scope
        )
        unresolved_account_execution_reconciliation_count = (
            current._unresolved_account_execution_reconciliation_count
        )
        account_authority_epoch = current._account_authority_epoch
        registry_transition_ledger = current._registry_transition_ledger
        registry_transition_head_commitment = (
            current._registry_transition_head_commitment
        )
        if execution_reconciliation_append is not None:
            (
                execution_reconciliation_ledger,
                execution_reconciliation_by_input,
                unresolved_execution_reconciliation_count_by_scope,
            ) = _append_execution_reconciliation_value(
                execution_reconciliation_ledger,
                execution_reconciliation_by_input,
                unresolved_execution_reconciliation_count_by_scope,
                execution_reconciliation_append,
            )
            if type(item) is not CatchUpExecutionRegistry:
                raise TypeError(
                    "registry reconciliation requires its exact CatchUp command"
                )
            registry_transition = _registry_transition_proof_for(
                ordinal=registry_transition_ledger.length + 1,
                predecessor_commitment=registry_transition_head_commitment,
                venue_scope=current.scope,
                item=cast(CatchUpExecutionRegistry, item),
                outcome=execution_reconciliation_append,
            )
            registry_transition_ledger = registry_transition_ledger.append(
                registry_transition,
                registry_transition.commitment,
            )
            registry_transition_head_commitment = registry_transition.commitment
            if not execution_reconciliation_append.attribution_resolved:
                unresolved_account_execution_reconciliation_count += 1
                account_authority_epoch += 1

        authority_epoch_by_scope = current._authority_epoch_by_scope
        if demote_scope is not None:
            if not isinstance(demote_scope, PositionScope):
                raise TypeError("demotion scope must be PositionScope")
            scope_key = _position_scope_index_key(demote_scope)
            authority_epoch_by_scope = _set_int_index(
                authority_epoch_by_scope,
                scope_key,
                (authority_epoch_by_scope.get(scope_key) or 0) + 1,
                domain=b"execution-core/venue-authority-epoch/v1",
            )

        effect_order = current._effect_order
        effect_by_id = current._effect_by_id
        effect_by_request_occurrence = current._effect_by_request_occurrence
        effect_by_client_order = current._effect_by_client_order
        if effect_append is not None and effect_replace is not None:
            raise ValueError("effect cannot append and replace in one transition")
        if effect_append is not None:
            (
                effect_order,
                effect_by_id,
                effect_by_request_occurrence,
                effect_by_client_order,
            ) = _append_effect_value(
                effect_order,
                effect_by_id,
                effect_by_request_occurrence,
                effect_by_client_order,
                authority_epoch_by_scope,
                account_authority_epoch,
                effect_append,
            )
        elif effect_replace is not None:
            effect_by_id = _replace_effect_value(
                effect_by_id,
                authority_epoch_by_scope,
                account_authority_epoch,
                effect_replace,
            )
        contradiction_order_by_effect = current._contradiction_order_by_effect
        if contradiction_append is not None:
            if (
                type(contradiction_append) is not tuple
                or len(contradiction_append) != 2
            ):
                raise TypeError("contradiction append must pair effect and evidence")
            contradiction_effect_id, contradiction = contradiction_append
            if not isinstance(contradiction_effect_id, EffectId):
                raise TypeError("contradiction effect identity must be EffectId")
            contradiction_order_by_effect = _append_contradiction_value(
                contradiction_order_by_effect,
                contradiction_effect_id,
                contradiction,
            )

        claim_order = current._claim_order
        claim_by_effect = current._claim_by_effect
        claim_by_occurrence = current._claim_by_occurrence
        if claim_append is not None:
            claim_order, claim_by_effect, claim_by_occurrence = _append_claim_value(
                claim_order,
                claim_by_effect,
                claim_by_occurrence,
                claim_append,
            )

        owner_order = current._owner_order
        owner_by_leg = current._owner_by_leg
        leg_current_by_leg = current._leg_current_by_leg
        leg_summary_by_effect = current._leg_summary_by_effect
        if owner_and_attempt_append is not None:
            (
                owner_order,
                owner_by_leg,
                leg_current_by_leg,
                leg_summary_by_effect,
            ) = _append_owner_value(
                owner_order,
                owner_by_leg,
                leg_current_by_leg,
                leg_summary_by_effect,
                owner_and_attempt_append,
            )
        if attempt_replace is not None:
            leg_current_by_leg = _replace_attempt_value(
                leg_current_by_leg,
                attempt_replace,
            )
        if closure is not None:
            encoded_leg = _leg_index_key(closure.leg_key)
            owner = owner_by_leg.get(encoded_leg)
            current_leg = leg_current_by_leg.get(encoded_leg)
            if owner is None or current_leg is None:
                raise ValueError("closure requires a current owned leg")
            effect_current = effect_by_id.get(_effect_index_key(owner.effect_id))
            if effect_current is None:
                raise ValueError("closure owner requires a current effect")
            prior_head = current._closure_head_by_leg.get(encoded_leg)
            prior_coverage = (
                current._coverage_current_by_leg.get(encoded_leg)
                or _CoverageLegCurrent()
            )
            next_coverage = (
                coverage_current_by_leg.get(encoded_leg) or _CoverageLegCurrent()
            )
            prior_ready = _closure_is_finalization_ready(
                effect_current.effect,
                prior_head,
                prior_coverage.canonical_total,
            )
            next_ready = _closure_is_finalization_ready(
                effect_current.effect,
                closure,
                next_coverage.canonical_total,
            )
            if (
                prior_ready
                and not next_ready
                and effect_current.effect.state
                is BrokerEffectState.OPERATOR_RECONCILED
            ):
                scope_key = _position_scope_index_key(
                    effect_current.effect.scope.position_scope
                )
                authority_epoch = authority_epoch_by_scope.get(scope_key) or 0
                if effect_current.operator_epoch == authority_epoch:
                    effect_by_id = _replace_effect_value(
                        effect_by_id,
                        authority_epoch_by_scope,
                        account_authority_epoch,
                        replace(
                            effect_current.effect,
                            state=BrokerEffectState.NEEDS_REVIEW,
                        ),
                    )
            summary = (
                leg_summary_by_effect.get(_effect_index_key(owner.effect_id))
                or _EffectLegSummary()
            )
            summary = replace(
                summary,
                active_count=(
                    summary.active_count - (1 if current_leg.attempt is not None else 0)
                ),
                finalization_ready_count=(
                    summary.finalization_ready_count
                    - (1 if prior_ready else 0)
                    + (1 if next_ready else 0)
                ),
            )
            if summary.active_count < 0 or summary.finalization_ready_count < 0:
                raise ValueError("effect leg summary cannot become negative")
            leg_summary_by_effect = _set_effect_leg_summary(
                leg_summary_by_effect,
                owner.effect_id,
                summary,
            )
            closed_current = _LegCurrent(None)
            leg_current_by_leg = leg_current_by_leg.replace_existing(
                encoded_leg,
                closed_current,
                closed_current.commitment,
            )

        if type(binding_upserts) is not tuple or len(binding_upserts) > 2:
            raise TypeError("binding upserts must be a bounded tuple")
        binding_order = current._binding_order
        binding_by_scope = current._binding_by_scope
        seen_binding_scopes: set[PositionScope] = set()
        for binding in binding_upserts:
            if not isinstance(binding, VenueExecutionBinding):
                raise TypeError("binding upsert must be VenueExecutionBinding")
            if binding.position_scope in seen_binding_scopes:
                raise ValueError("binding scope cannot be updated twice")
            seen_binding_scopes.add(binding.position_scope)
            binding_order, binding_by_scope = _upsert_binding_value(
                binding_order,
                binding_by_scope,
                binding,
            )

        coverage_provenance_by_scope = _evolve_coverage_provenance(
            current._coverage_provenance_by_scope,
            prior_execution,
            resulting_execution,
            item,
            canonical_economic_input=canonical_economic_input,
        )

        result = object.__new__(VenueRecoveryBook)
        for name in _EVOLVABLE_BOOK_FIELDS:
            object.__setattr__(
                result,
                name,
                changes.get(name, getattr(current, name)),
            )
        object.__setattr__(result, "_effect_order", effect_order)
        object.__setattr__(result, "_effect_by_id", effect_by_id)
        object.__setattr__(
            result,
            "_effect_by_request_occurrence",
            effect_by_request_occurrence,
        )
        object.__setattr__(
            result,
            "_effect_by_client_order",
            effect_by_client_order,
        )
        object.__setattr__(
            result,
            "_authority_epoch_by_scope",
            authority_epoch_by_scope,
        )
        object.__setattr__(result, "_account_authority_epoch", account_authority_epoch)
        object.__setattr__(
            result,
            "_contradiction_order_by_effect",
            contradiction_order_by_effect,
        )
        object.__setattr__(result, "_claim_order", claim_order)
        object.__setattr__(result, "_claim_by_effect", claim_by_effect)
        object.__setattr__(result, "_claim_by_occurrence", claim_by_occurrence)
        object.__setattr__(result, "_owner_order", owner_order)
        object.__setattr__(result, "_owner_by_leg", owner_by_leg)
        object.__setattr__(result, "_leg_current_by_leg", leg_current_by_leg)
        object.__setattr__(
            result,
            "_leg_summary_by_effect",
            leg_summary_by_effect,
        )
        object.__setattr__(result, "_binding_order", binding_order)
        object.__setattr__(result, "_binding_by_scope", binding_by_scope)
        object.__setattr__(result, "_closure_ledger", closure_ledger)
        object.__setattr__(result, "_closure_by_id", closure_by_id)
        object.__setattr__(result, "_closure_head_by_leg", closure_heads_by_leg)
        object.__setattr__(result, "_input_ledger", input_ledger)
        object.__setattr__(result, "_input_by_id", input_by_id)
        object.__setattr__(result, "_direct_input_by_semantic", direct_semantics)
        object.__setattr__(result, "_first_input_by_fact", first_inputs_by_fact)
        object.__setattr__(
            result,
            "_economic_high_water_by_leg",
            economic_high_water_by_leg,
        )
        object.__setattr__(result, "_human_coverage_ledger", human_coverage_ledger)
        object.__setattr__(
            result,
            "_human_coverage_by_root",
            human_coverage_by_root,
        )
        object.__setattr__(result, "_broker_coverage_ledger", broker_coverage_ledger)
        object.__setattr__(
            result,
            "_broker_coverage_by_root",
            broker_coverage_by_root,
        )
        object.__setattr__(
            result,
            "_coverage_provenance_by_scope",
            coverage_provenance_by_scope,
        )
        object.__setattr__(
            result,
            "_coverage_current_by_leg",
            coverage_current_by_leg,
        )
        object.__setattr__(
            result,
            "_coverage_total_by_effect",
            coverage_total_by_effect,
        )
        object.__setattr__(
            result,
            "_attributed_broker_root_count_by_scope",
            attributed_broker_root_count_by_scope,
        )
        object.__setattr__(result, "_human_interval_index", human_interval_index)
        object.__setattr__(
            result,
            "_human_broker_fact_index",
            human_broker_fact_index,
        )
        object.__setattr__(
            result,
            "_reconciliation_ledger",
            reconciliation_ledger,
        )
        object.__setattr__(
            result,
            "_reconciliation_by_input",
            reconciliation_by_input,
        )
        object.__setattr__(
            result,
            "_unresolved_reconciliation_count_by_leg",
            unresolved_reconciliation_count_by_leg,
        )
        object.__setattr__(
            result,
            "_reconciliation_count_by_effect",
            reconciliation_count_by_effect,
        )
        object.__setattr__(
            result,
            "_canonical_revision_count_by_leg",
            canonical_revision_count_by_leg,
        )
        object.__setattr__(
            result,
            "_execution_reconciliation_ledger",
            execution_reconciliation_ledger,
        )
        object.__setattr__(
            result,
            "_execution_reconciliation_by_input",
            execution_reconciliation_by_input,
        )
        object.__setattr__(
            result,
            "_registry_transition_ledger",
            registry_transition_ledger,
        )
        object.__setattr__(
            result,
            "_registry_transition_head_commitment",
            registry_transition_head_commitment,
        )
        object.__setattr__(
            result,
            "_unresolved_execution_reconciliation_count_by_scope",
            unresolved_execution_reconciliation_count_by_scope,
        )
        object.__setattr__(
            result,
            "_unresolved_account_execution_reconciliation_count",
            unresolved_account_execution_reconciliation_count,
        )

        if result._effect_order.length and not result._execution_pair_matches_fast(
            resulting_execution
        ):
            raise ValueError(
                "venue checkpoint evolution produced a stale execution pair"
            )
        return result

    def transition(
        resulting_book: VenueRecoveryBook,
        prior_execution: ExecutionSnapshot,
        resulting_execution: ExecutionSnapshot,
        disposition: VenueRecoveryDisposition,
        *,
        item: object,
        quantity_delta: int,
    ) -> VenueRecoveryTransition:
        """Allocate one authenticated result with reducer-derived economics."""

        from .recovery import (
            IngestHumanAttestedFill,
            RecordBrokerFillEvidence,
            RecordBrokerRevisionEvidence,
        )

        if type(resulting_book) is not VenueRecoveryBook:
            raise TypeError("transition book must be the exact VenueRecoveryBook type")
        if type(prior_execution) is not ExecutionSnapshot:
            raise TypeError("prior execution must be the exact ExecutionSnapshot type")
        if type(resulting_execution) is not ExecutionSnapshot:
            raise TypeError(
                "resulting execution must be the exact ExecutionSnapshot type"
            )
        if type(disposition) is not VenueRecoveryDisposition:
            raise TypeError("transition disposition must be VenueRecoveryDisposition")
        if type(quantity_delta) is not int:
            raise TypeError("transition quantity_delta must be an exact integer")

        economic_command = type(item) in {
            IngestHumanAttestedFill,
            RecordBrokerFillEvidence,
            RecordBrokerRevisionEvidence,
        }
        derived_delta = 0
        if economic_command and disposition in {
            VenueRecoveryDisposition.APPLIED,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        }:
            derived_delta = (
                resulting_execution.position.raw_quantity
                - prior_execution.position.raw_quantity
            )
        if quantity_delta != derived_delta:
            raise ValueError(
                "transition quantity_delta disagrees with reducer-derived economics"
            )
        if disposition in {
            VenueRecoveryDisposition.APPLIED,
            VenueRecoveryDisposition.EXACT_REPLAY,
        } and not resulting_book._execution_pair_matches_fast(resulting_execution):
            raise ValueError(
                "usable venue transition requires its exact book/execution pair"
            )

        result = object.__new__(VenueRecoveryTransition)
        object.__setattr__(result, "book", resulting_book)
        object.__setattr__(result, "execution", resulting_execution)
        object.__setattr__(result, "disposition", disposition)
        object.__setattr__(result, "quantity_delta", derived_delta)
        return result

    input_id = _require_input_id("item.input_id", getattr(item, "input_id", None))
    if isinstance(item, CatchUpExecutionRegistry):
        return _apply_execution_registry_catch_up(
            book,
            execution,
            item,
            evolve,
            transition,
        )
    if (
        isinstance(item, RequestedEffect)
        and not book._effect_order.length
        and not _execution_is_exact_genesis(execution)
    ):
        return transition(
            book,
            execution,
            execution,
            VenueRecoveryDisposition.REFUSED,
            item=item,
            quantity_delta=0,
        )
    if book._execution_reconciliation_cursor_is_prefix(execution):
        transition_count, transition_head = book._reconciliation_cursor()
        execution = _bind_execution_reconciliation_cursor(
            execution,
            transition_count=transition_count,
            transition_head=transition_head,
            account_reconciliation_required=(
                book._unresolved_account_execution_reconciliation_count > 0
            ),
        )
    target_effect_id = getattr(item, "effect_id", None)
    if not isinstance(target_effect_id, EffectId):
        target_leg_key = getattr(item, "leg_key", None)
        owner = (
            book.owner(target_leg_key)
            if isinstance(target_leg_key, VenueLegKey)
            else None
        )
        target_effect_id = owner.effect_id if owner is not None else None
    if isinstance(target_effect_id, EffectId) and book._current_effect(
        target_effect_id
    ):
        target_effect = book._current_effect(target_effect_id)
        assert target_effect is not None
        if (
            execution.position.scope != target_effect.scope.position_scope
            or not book._execution_pair_matches_fast(execution)
        ):
            return transition(
                book,
                execution,
                execution,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
                item=item,
                quantity_delta=0,
            )
    if isinstance(item, RequestedEffect):
        if not book._execution_reconciliation_cursor_is_prefix(execution):
            return transition(
                book,
                execution,
                execution,
                VenueRecoveryDisposition.REFUSED,
                item=item,
                quantity_delta=0,
            )
        position_scope = execution.position.scope
        if (
            position_scope.broker != book.scope.broker
            or position_scope.environment != book.scope.environment
            or position_scope.account != book.scope.account
            or position_scope.symbol_id != item.symbol_id
        ):
            return transition(
                book,
                execution,
                execution,
                VenueRecoveryDisposition.REFUSED,
                item=item,
                quantity_delta=0,
            )
        item_effect_scope = _effect_scope(book, item).position_scope
        existing_binding = book.execution_binding(item_effect_scope)
        if (
            execution.position.scope != item_effect_scope
            or (
                book.execution_registry_commitment is not None
                and (
                    book.execution_registry_count != execution.seen_facts.count
                    or book.execution_registry_commitment
                    != execution.seen_facts.commitment
                )
            )
            or (
                existing_binding is not None
                and not book._execution_pair_matches_fast(execution)
            )
        ):
            return transition(
                book,
                execution,
                execution,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
                item=item,
                quantity_delta=0,
            )
    replay = book._input_record(input_id)
    if replay is not None:
        disposition = (
            VenueRecoveryDisposition.EXACT_REPLAY
            if _input_commands_equal(
                replay.item,
                item,
                include_input_id=True,
            )
            else VenueRecoveryDisposition.CONFLICT
        )
        return transition(
            book,
            execution,
            execution,
            disposition,
            item=item,
            quantity_delta=0,
        )

    if isinstance(item, RequestedEffect):
        next_book = _register_effect(evolve, book, execution, item)
        disposition = (
            VenueRecoveryDisposition.APPLIED
            if next_book is not None
            else VenueRecoveryDisposition.CONFLICT
        )
    elif isinstance(item, RecordDispatchClaim):
        effect = book._current_effect(item.effect_id)
        duplicate_claim_occurrence = book._has_claim_occurrence(
            item.claim_occurrence_id
        )
        next_book = _record_claim(evolve, book, execution, item)
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
        effect = book._current_effect(item.effect_id)
        if (
            effect is not None
            and effect.state is BrokerEffectState.REQUESTED
            and effect.claim_occurrence_id is None
        ):
            next_book = _replace_effect_state(
                evolve,
                book,
                execution,
                effect,
                BrokerEffectState.CANCELED_BEFORE_DISPATCH,
                item,
            )
            disposition = VenueRecoveryDisposition.APPLIED
        else:
            next_book = None
            disposition = VenueRecoveryDisposition.REFUSED
    elif isinstance(item, RecordTransportOutcome):
        effect = book._current_effect(item.effect_id)
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
                evolve,
                _replace_effect_state(
                    evolve,
                    book,
                    execution,
                    effect,
                    item.state,
                    item,
                ),
                item.effect_id,
                execution,
            )
            disposition = VenueRecoveryDisposition.APPLIED
        else:
            next_book = None
            disposition = VenueRecoveryDisposition.REFUSED
    elif isinstance(item, RecoverClaimedEffect):
        effect = book._current_effect(item.effect_id)
        if effect is not None and effect.state is BrokerEffectState.DISPATCH_CLAIMED:
            next_book = _replace_effect_state(
                evolve,
                book,
                execution,
                effect,
                BrokerEffectState.OUTCOME_UNKNOWN,
                item,
            )
            disposition = VenueRecoveryDisposition.APPLIED
        else:
            next_book = None
            disposition = VenueRecoveryDisposition.REFUSED
    elif isinstance(item, DiscoverVenueLeg):
        next_book, disposition = _discover_leg(evolve, book, execution, item)
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
                evolve,
                book,
                execution,
                item,
                _attempt_replace=updated,
            )
            disposition = VenueRecoveryDisposition.APPLIED
    elif isinstance(item, ObserveVenueStatus):
        next_book = _observe_status(evolve, book, execution, item)
        disposition = (
            VenueRecoveryDisposition.APPLIED
            if next_book is not None
            else VenueRecoveryDisposition.REFUSED
        )
    elif isinstance(item, CloseAcceptanceSet):
        next_book = _close_acceptance_set(evolve, book, execution, item)
        disposition = (
            VenueRecoveryDisposition.APPLIED
            if next_book is not None
            else VenueRecoveryDisposition.REFUSED
        )
    else:
        from .recovery import _apply_recovery_input

        return _apply_recovery_input(
            book,
            execution,
            item,
            evolve,
            transition,
        )

    return transition(
        next_book or book,
        execution,
        execution,
        disposition,
        item=item,
        quantity_delta=0,
    )


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
    "VenueExecutionCheckpoint",
    "VenueRecoveryBook",
    "VenueRecoveryDisposition",
    "VenueRecoveryTransition",
    "VenueScope",
    "VenueIntegrity",
    "VenueTerminalClosure",
    "apply_venue_recovery_input",
]
