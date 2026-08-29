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
    SeenFact,
    _PersistentKeyMap,
    _PersistentSequence,
    _commit_parts,
    _encode_int,
    _encode_position_scope,
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
    BasisAuthority,
    ExecutionSnapshot,
    PositionIntegrity,
    _RECONCILIATION_GENESIS_HEAD,
    _bind_execution_reconciliation_cursor,
    _project_execution_registry,
    _require_execution_components,
    apply_broker_execution_fact as _apply_broker_execution_fact,
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
    if type(value) is not expected:
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
    if type(value) is not VenueInputId:
        raise TypeError(f"{name} must be VenueInputId")
    return cast(VenueInputId, value)


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
    if value_type is tuple:
        return _commit_parts(
            b"execution-core/canonical-tuple/v1",
            *(
                _canonical_value_commitment(item)
                for item in cast(tuple[object, ...], value)
            ),
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


def _require_exact_venue_recovery_input(item: object) -> None:
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
        _BrokerExecutionRegistryCatchUp,
        _BootstrapTargetRegistryInput,
        IngestHumanAttestedFill,
        ReleaseVenueLeg,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
    }
    if type(item) not in admitted_types:
        raise TypeError("item must be an exact venue-recovery command type")


def _input_command_identity(
    item: object,
    *,
    include_input_id: bool,
) -> tuple[bytes, ...]:
    """Return one bounded, type-exact command identity."""

    _require_exact_venue_recovery_input(item)
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
    _require_input_record_shape(record)
    return _commit_parts(
        b"execution-core/venue-input-record/v2",
        _canonical_value_commitment(record.input_id),
        _canonical_value_commitment(record.semantic_alias_of),
        *_input_command_identity(record.item, include_input_id=True),
    )


def _closure_commitment(closure: VenueTerminalClosure) -> bytes:
    _require_closure_shape(closure)
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
    """Retained closure-evidence kinds; construction never authenticates a producer."""

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


def _validate_effect_identity_shape(
    kind: EffectKind,
    client_order_id: ClientOrderId | None,
    target_leg_key: VenueLegKey | None,
) -> None:
    """Validate the creating identity and exact target carried by one effect."""

    _require("kind", kind, EffectKind)
    if client_order_id is not None:
        _require("client_order_id", client_order_id, ClientOrderId)
    if target_leg_key is not None:
        _require("target_leg_key", target_leg_key, VenueLegKey)
    if kind is EffectKind.SUBMIT:
        if client_order_id is None:
            raise ValueError("SUBMIT requires a client_order_id")
        if target_leg_key is not None:
            raise ValueError("SUBMIT cannot target a venue leg")
    elif kind is EffectKind.CANCEL:
        if client_order_id is not None:
            raise ValueError("CANCEL cannot carry a client_order_id")
        if target_leg_key is None:
            raise ValueError("CANCEL requires a target_leg_key")
    else:
        if client_order_id is None:
            raise ValueError("REPLACE requires a client_order_id")
        if target_leg_key is None:
            raise ValueError("REPLACE requires a target_leg_key")


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
    client_order_id: ClientOrderId | None
    symbol_id: SymbolId
    side: ExecutionSide
    quantity: Quantity
    economic_scope: bytes
    target_leg_key: VenueLegKey | None = None

    def __post_init__(self) -> None:
        for name, value, expected in (
            ("generation", self.generation, ApplicationGenerationId),
            ("broker", self.broker, BrokerId),
            ("environment", self.environment, EnvironmentId),
            ("account", self.account, AccountId),
            ("effect_id", self.effect_id, EffectId),
            ("request_occurrence_id", self.request_occurrence_id, RequestOccurrenceId),
            ("mandate_id", self.mandate_id, MandateId),
            ("kind", self.kind, EffectKind),
            ("symbol_id", self.symbol_id, SymbolId),
            ("side", self.side, ExecutionSide),
            ("quantity", self.quantity, Quantity),
        ):
            _require(name, value, expected)
        _validate_effect_identity_shape(
            self.kind,
            self.client_order_id,
            self.target_leg_key,
        )

    @property
    def client_identity(self) -> ClientIdentityBinding | None:
        if self.client_order_id is None:
            return None
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
    client_order_id: ClientOrderId | None
    symbol_id: SymbolId
    side: ExecutionSide
    quantity: Quantity
    economic_scope: bytes
    target_leg_key: VenueLegKey | None = None

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        _require("effect_id", self.effect_id, EffectId)
        _require(
            "request_occurrence_id", self.request_occurrence_id, RequestOccurrenceId
        )
        _require("mandate_id", self.mandate_id, MandateId)
        _require("kind", self.kind, EffectKind)
        _require("symbol_id", self.symbol_id, SymbolId)
        _require("side", self.side, ExecutionSide)
        _require("quantity", self.quantity, Quantity)
        if self.quantity.value <= 0:
            raise ValueError("quantity must be positive")
        if type(self.economic_scope) is not bytes:
            raise TypeError("economic_scope must be bytes")
        if not self.economic_scope:
            raise ValueError("economic_scope must be nonempty")
        _validate_effect_identity_shape(
            self.kind,
            self.client_order_id,
            self.target_leg_key,
        )


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
    """Internal replay representation of independently certified closure evidence."""

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
    """Internal replay input; the public reducer never admits this capability."""

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

    def __post_init__(self) -> None:
        _require("scope", self.scope, VenueEffectScope)
        _require("state", self.state, BrokerEffectState)
        _require("acceptance_set_state", self.acceptance_set_state, AcceptanceSetState)
        if self.claim_occurrence_id is not None:
            _require("claim_occurrence_id", self.claim_occurrence_id, ClaimOccurrenceId)
        if self.acceptance_proof is not None:
            _require("acceptance_proof", self.acceptance_proof, AcceptanceProof)
        _require_tuple("contradiction_evidence", self.contradiction_evidence)
        for contradiction in self.contradiction_evidence:
            _require(
                "contradiction_evidence entry",
                contradiction,
                AcceptanceContradiction,
            )

    @property
    def effect_id(self) -> EffectId:
        return self.scope.effect_id


@dataclass(frozen=True, slots=True)
class DispatchClaim:
    effect_scope: VenueEffectScope
    claim_occurrence_id: ClaimOccurrenceId

    def __post_init__(self) -> None:
        _require("effect_scope", self.effect_scope, VenueEffectScope)
        _require("claim_occurrence_id", self.claim_occurrence_id, ClaimOccurrenceId)

    @property
    def effect_id(self) -> EffectId:
        return self.effect_scope.effect_id


@dataclass(frozen=True, slots=True)
class VenueIdentityOwner:
    leg_key: VenueLegKey
    effect_scope: VenueEffectScope
    observation_id: VenueObservationId

    def __post_init__(self) -> None:
        _require("leg_key", self.leg_key, VenueLegKey)
        _require("effect_scope", self.effect_scope, VenueEffectScope)
        _require("observation_id", self.observation_id, VenueObservationId)

    @property
    def effect_id(self) -> EffectId:
        return self.effect_scope.effect_id


def _acquisition_correlation_commitment(
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    request_occurrence_id: RequestOccurrenceId,
    effect_id: EffectId,
    leg_key: VenueLegKey | None,
    root_key: RootFillKey | None,
) -> bytes:
    return _commit_parts(
        b"execution-core/venue-acquisition-correlation/v1",
        _encode_text(application_generation_id.value),
        _position_scope_index_key(position_scope),
        _request_occurrence_index_key(request_occurrence_id),
        _effect_index_key(effect_id),
        (
            _leg_index_key(leg_key)
            if leg_key is not None
            else _commit_parts(
                b"execution-core/venue-acquisition-correlation/no-leg/v1"
            )
        ),
        (
            _coverage_root_index_key(root_key)
            if root_key is not None
            else _commit_parts(
                b"execution-core/venue-acquisition-correlation/no-root/v1"
            )
        ),
    )


@dataclass(frozen=True, slots=True, init=False)
class VenueAcquisitionCorrelation:
    """Read-only direct provenance bridge for a venue-owned broker root."""

    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    request_occurrence_id: RequestOccurrenceId = field(init=False)
    effect_id: EffectId = field(init=False)
    leg_key: VenueLegKey | None = field(init=False)
    root_key: RootFillKey | None = field(init=False)
    correlation_commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("VenueAcquisitionCorrelation is reducer-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("VenueAcquisitionCorrelation cannot be subclassed")


class AcquisitionVenueSourceKind(Enum):
    """The bounded source class for an acquisition-facing venue projection."""

    BOOTSTRAP = "BOOTSTRAP"
    CANONICAL_ECONOMIC_FACT = "CANONICAL_ECONOMIC_FACT"
    CANONICAL_ECONOMIC_FACT_RECONCILIATION = "CANONICAL_ECONOMIC_FACT_RECONCILIATION"


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionFactRelation:
    """Venue-sealed direct provenance for one canonical economic fact.

    The public shape deliberately contains keys only.  It is not a capability,
    a history reader, or a factory for a new fact relation.
    """

    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    fact_key: ExecutionFactKey = field(init=False)
    root_key: RootFillKey = field(init=False)
    effect_id: EffectId = field(init=False)
    request_occurrence_id: RequestOccurrenceId = field(init=False)
    leg_key: VenueLegKey = field(init=False)
    source_commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionFactRelation is venue-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionFactRelation cannot be subclassed")


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionVenueContext:
    """Exact target-scope context with full-input freshness checked at use time."""

    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _source_execution_commitment: bytes = field(init=False, repr=False)
    _source_protection_cursor_ordinal: int = field(init=False, repr=False)
    _source_protection_cursor_head: bytes = field(init=False, repr=False)
    _serving: bool = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionVenueContext is venue-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionVenueContext cannot be subclassed")

    def matches_current(
        self,
        book: VenueRecoveryBook,
        execution: ExecutionSnapshot,
        application_generation_id: ApplicationGenerationId,
        position_scope: PositionScope,
    ) -> bool:
        if (
            type(book) is not VenueRecoveryBook
            or type(execution) is not ExecutionSnapshot
            or type(application_generation_id) is not ApplicationGenerationId
            or type(position_scope) is not PositionScope
            or not _acquisition_venue_context_is_authentic(self)
            or not self._serving
        ):
            return False
        if (
            self.application_generation_id != application_generation_id
            or self.position_scope != position_scope
        ):
            return False
        current = book.project_acquisition_context(execution, position_scope)
        return (
            _acquisition_venue_context_is_authentic(current)
            and current._serving
            and current.application_generation_id == self.application_generation_id
            and current.position_scope == self.position_scope
            and current.scope_execution_commitment == self.scope_execution_commitment
            and current.commitment == self.commitment
            and current._source_execution_commitment
            == self._source_execution_commitment
            and current._source_protection_cursor_ordinal
            == self._source_protection_cursor_ordinal
            and current._source_protection_cursor_head
            == self._source_protection_cursor_head
        )


@dataclass(frozen=True, slots=True, init=False)
class AcquisitionVenueProjection:
    """Opaque target-only bootstrap or canonical-fact venue proof."""

    source_kind: AcquisitionVenueSourceKind = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    predecessor_execution_snapshot_commitment: bytes | None = field(init=False)
    execution_snapshot_commitment: bytes = field(init=False)
    predecessor_scope_execution_commitment: bytes | None = field(init=False)
    scope_execution_commitment: bytes = field(init=False)
    predecessor_venue_commitment: bytes | None = field(init=False)
    venue_commitment: bytes = field(init=False)
    source_commitment: bytes = field(init=False)
    _fact_relation: AcquisitionFactRelation | None = field(init=False, repr=False)
    _serving: bool = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionVenueProjection is venue-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionVenueProjection cannot be subclassed")

    def fact_relation(self) -> AcquisitionFactRelation | None:
        if not _acquisition_venue_projection_is_authentic(self) or not self._serving:
            return None
        relation = self._fact_relation
        return relation if _acquisition_fact_relation_is_authentic(relation) else None

    def matches_bootstrap(
        self,
        execution: ExecutionSnapshot,
        book: VenueRecoveryBook,
        position_scope: PositionScope,
    ) -> bool:
        if (
            type(execution) is not ExecutionSnapshot
            or type(book) is not VenueRecoveryBook
            or type(position_scope) is not PositionScope
            or not _acquisition_venue_projection_is_authentic(self)
            or not self._serving
            or self.source_kind is not AcquisitionVenueSourceKind.BOOTSTRAP
            or self.position_scope != position_scope
        ):
            return False
        context = book.project_acquisition_context(execution, position_scope)
        return (
            context.matches_current(
                book,
                execution,
                self.application_generation_id,
                position_scope,
            )
            and context.scope_execution_commitment == self.scope_execution_commitment
            and context.commitment == self.venue_commitment
            and execution.commitment == self.execution_snapshot_commitment
            and self.source_commitment
            == _commit_parts(
                b"execution-core/acquisition-venue/bootstrap/v1",
                context._seal,
            )
        )

    def matches_fact_transition(
        self,
        transition: VenueRecoveryTransition,
        position_scope: PositionScope,
    ) -> bool:
        if (
            type(transition) is not VenueRecoveryTransition
            or type(position_scope) is not PositionScope
            or not _acquisition_venue_projection_is_authentic(self)
            or not self._serving
            or self.source_kind
            not in {
                AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT,
                AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION,
            }
            or self.position_scope != position_scope
        ):
            return False
        expected = transition.book.project_acquisition_fact(transition)
        relation = self.fact_relation()
        expected_relation = expected.fact_relation()
        return (
            _acquisition_fact_proof_matches_transition(transition.book, transition)
            and _acquisition_venue_projection_is_authentic(expected)
            and expected._serving
            and self.source_kind is expected.source_kind
            and self.application_generation_id == expected.application_generation_id
            and self.position_scope == expected.position_scope
            and self.predecessor_execution_snapshot_commitment
            == expected.predecessor_execution_snapshot_commitment
            and self.execution_snapshot_commitment
            == expected.execution_snapshot_commitment
            and self.predecessor_scope_execution_commitment
            == expected.predecessor_scope_execution_commitment
            and self.scope_execution_commitment == expected.scope_execution_commitment
            and self.predecessor_venue_commitment
            == expected.predecessor_venue_commitment
            and self.venue_commitment == expected.venue_commitment
            and self.source_commitment == expected.source_commitment
            and relation is not None
            and expected_relation is not None
            and relation._seal == expected_relation._seal
        )

    def matches_predecessor_book(
        self,
        book: VenueRecoveryBook,
        position_scope: PositionScope,
    ) -> bool:
        if (
            type(book) is not VenueRecoveryBook
            or type(position_scope) is not PositionScope
        ):
            return False
        predecessor_scope_execution_commitment = (
            _bound_acquisition_scope_execution_commitment(book, position_scope)
        )
        return bool(
            _acquisition_venue_projection_is_authentic(self)
            and self.position_scope == position_scope
            and self.application_generation_id == book.scope.generation
            and predecessor_scope_execution_commitment is not None
            and self.predecessor_scope_execution_commitment
            == predecessor_scope_execution_commitment
            and self.predecessor_venue_commitment
            == _acquisition_venue_book_token(
                book,
                position_scope,
                predecessor_scope_execution_commitment,
            )
        )


def _acquisition_scope_execution_commitment(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
) -> bytes:
    binding = book.execution_binding(position_scope)
    binding_value = (
        _commit_parts(b"execution-core/acquisition-venue/no-binding/v1")
        if binding is None
        else _commit_parts(
            b"execution-core/acquisition-venue/binding/v1",
            _position_scope_index_key(binding.position_scope),
            binding.position_commitment,
            binding.root_heads_commitment,
            _encode_text(str(binding.integrity_bits)),
        )
    )
    return _commit_parts(
        b"execution-core/acquisition-venue/scope-execution/v1",
        _encode_text(book.scope.generation.value),
        _position_scope_index_key(position_scope),
        execution.position.commitment,
        execution.root_heads.commitment,
        _encode_text(str(execution.integrity.value)),
        binding_value,
    )


def _bound_acquisition_scope_execution_commitment(
    book: VenueRecoveryBook,
    position_scope: PositionScope,
) -> bytes | None:
    """Rebuild the target scope token from the book-owned direct binding only."""

    binding = book.execution_binding(position_scope)
    if binding is None:
        return None
    binding_value = _commit_parts(
        b"execution-core/acquisition-venue/binding/v1",
        _position_scope_index_key(binding.position_scope),
        binding.position_commitment,
        binding.root_heads_commitment,
        _encode_text(str(binding.integrity_bits)),
    )
    return _commit_parts(
        b"execution-core/acquisition-venue/scope-execution/v1",
        _encode_text(book.scope.generation.value),
        _position_scope_index_key(position_scope),
        binding.position_commitment,
        binding.root_heads_commitment,
        _encode_text(str(binding.integrity_bits)),
        binding_value,
    )


def _acquisition_venue_book_token(
    book: VenueRecoveryBook,
    position_scope: PositionScope,
    scope_execution_commitment: bytes,
) -> bytes:
    _require_digest("scope_execution_commitment", scope_execution_commitment)
    summary = book._authority_summary_by_scope.get(
        _position_scope_index_key(position_scope)
    )
    if summary is None:
        summary = _SymbolAuthoritySummary()
    bootstrap_record = book._bootstrap_bound_target_by_scope.get(
        _position_scope_index_key(position_scope)
    )
    bootstrap_commitment = (
        _commit_parts(b"execution-core/acquisition-venue/no-bootstrap-record/v1")
        if bootstrap_record is None
        else (
            cast(_BootstrapBoundTargetRecord, bootstrap_record).commitment
            if _bootstrap_bound_target_record_is_authentic(bootstrap_record)
            else _commit_parts(
                b"execution-core/acquisition-venue/invalid-bootstrap-record/v1"
            )
        )
    )
    return _commit_parts(
        b"execution-core/acquisition-venue/context/v1",
        _encode_text(book.scope.generation.value),
        _position_scope_index_key(position_scope),
        scope_execution_commitment,
        _encode_text(str(summary.effect_count)),
        _encode_text(str(summary.blocking_effect_count)),
        _encode_text(str(summary.blocking_buy_effect_count)),
        _encode_text(str(summary.stand_downable_buy_count)),
        _encode_text(str(summary.waiting_buy_parent_count)),
        _encode_text(str(summary.unknown_buy_effect_count)),
        bootstrap_commitment,
    )


def _new_acquisition_venue_context(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
    serving: bool,
) -> AcquisitionVenueContext:
    scope_execution_commitment = _acquisition_scope_execution_commitment(
        book,
        execution,
        position_scope,
    )
    venue_commitment = _acquisition_venue_book_token(
        book,
        position_scope,
        scope_execution_commitment,
    )
    cursor = book._protection_cursor_by_scope.get(
        _position_scope_index_key(position_scope)
    )
    if cursor is None:
        cursor = _protection_genesis_cursor()
    commitment = _commit_parts(
        b"execution-core/acquisition-venue/context-seal/v1",
        _encode_text(book.scope.generation.value),
        _position_scope_index_key(position_scope),
        scope_execution_commitment,
        venue_commitment,
        execution.commitment,
        _encode_int(cursor.ordinal),
        cursor.head,
        b"1" if serving else b"0",
    )
    result = object.__new__(AcquisitionVenueContext)
    object.__setattr__(result, "application_generation_id", book.scope.generation)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(result, "scope_execution_commitment", scope_execution_commitment)
    object.__setattr__(result, "commitment", venue_commitment)
    object.__setattr__(result, "_source_execution_commitment", execution.commitment)
    object.__setattr__(result, "_source_protection_cursor_ordinal", cursor.ordinal)
    object.__setattr__(result, "_source_protection_cursor_head", cursor.head)
    object.__setattr__(result, "_serving", serving)
    object.__setattr__(result, "_seal", commitment)
    return result


def _acquisition_venue_context_is_authentic(value: object) -> bool:
    if type(value) is not AcquisitionVenueContext:
        return False
    try:
        application_generation_id = value.application_generation_id
        position_scope = value.position_scope
        scope_execution_commitment = value.scope_execution_commitment
        commitment = value.commitment
        source_execution_commitment = value._source_execution_commitment
        source_protection_cursor_ordinal = value._source_protection_cursor_ordinal
        source_protection_cursor_head = value._source_protection_cursor_head
        serving = value._serving
        seal = value._seal
    except AttributeError:
        return False
    return (
        type(application_generation_id) is ApplicationGenerationId
        and type(position_scope) is PositionScope
        and type(scope_execution_commitment) is bytes
        and len(scope_execution_commitment) == 32
        and type(commitment) is bytes
        and len(commitment) == 32
        and type(source_execution_commitment) is bytes
        and len(source_execution_commitment) == 32
        and type(source_protection_cursor_ordinal) is int
        and source_protection_cursor_ordinal >= 0
        and type(source_protection_cursor_head) is bytes
        and len(source_protection_cursor_head) == 32
        and type(serving) is bool
        and type(seal) is bytes
        and seal
        == _commit_parts(
            b"execution-core/acquisition-venue/context-seal/v1",
            _encode_text(application_generation_id.value),
            _position_scope_index_key(position_scope),
            scope_execution_commitment,
            commitment,
            source_execution_commitment,
            _encode_int(source_protection_cursor_ordinal),
            source_protection_cursor_head,
            b"1" if serving else b"0",
        )
    )


def _acquisition_fact_relation_is_authentic(value: object) -> bool:
    if type(value) is not AcquisitionFactRelation:
        return False
    try:
        application_generation_id = value.application_generation_id
        position_scope = value.position_scope
        fact_key = value.fact_key
        root_key = value.root_key
        effect_id = value.effect_id
        request_occurrence_id = value.request_occurrence_id
        leg_key = value.leg_key
        source = value.source_commitment
        seal = value._seal
    except AttributeError:
        return False
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(fact_key) is not ExecutionFactKey
        or type(root_key) is not RootFillKey
        or type(effect_id) is not EffectId
        or type(request_occurrence_id) is not RequestOccurrenceId
        or type(leg_key) is not VenueLegKey
        or type(source) is not bytes
        or len(source) != 32
        or type(seal) is not bytes
        or len(seal) != 32
    ):
        return False
    if (
        application_generation_id.value == ""
        or fact_key.broker != position_scope.broker
        or fact_key.environment != position_scope.environment
        or fact_key.account != position_scope.account
        or root_key.broker != position_scope.broker
        or root_key.environment != position_scope.environment
        or root_key.account != position_scope.account
        or leg_key.broker != position_scope.broker
        or leg_key.environment != position_scope.environment
        or leg_key.account != position_scope.account
    ):
        return False
    return seal == _commit_parts(
        b"execution-core/acquisition-fact-relation-seal/v1",
        _encode_text(application_generation_id.value),
        _position_scope_index_key(position_scope),
        _canonical_value_commitment(fact_key),
        _canonical_value_commitment(root_key),
        _canonical_value_commitment(effect_id),
        _canonical_value_commitment(request_occurrence_id),
        _canonical_value_commitment(leg_key),
        source,
    )


def _optional_acquisition_digest_is_exact(value: object) -> bool:
    return value is None or (type(value) is bytes and len(value) == 32)


def _acquisition_venue_projection_seal(
    source_kind: AcquisitionVenueSourceKind,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    predecessor_execution_snapshot_commitment: bytes | None,
    execution_snapshot_commitment: bytes,
    predecessor_scope_execution_commitment: bytes | None,
    scope_execution_commitment: bytes,
    predecessor_venue_commitment: bytes | None,
    venue_commitment: bytes,
    source_commitment: bytes,
    fact_relation: AcquisitionFactRelation | None,
    serving: bool,
) -> bytes:
    return _commit_parts(
        b"execution-core/acquisition-venue/projection-seal/v2",
        _encode_text(source_kind.value),
        _encode_text(application_generation_id.value),
        _position_scope_index_key(position_scope),
        predecessor_execution_snapshot_commitment or b"",
        execution_snapshot_commitment,
        predecessor_scope_execution_commitment or b"",
        scope_execution_commitment,
        predecessor_venue_commitment or b"",
        venue_commitment,
        source_commitment,
        b"" if fact_relation is None else fact_relation._seal,
        b"1" if serving else b"0",
    )


def _acquisition_venue_projection_is_authentic(value: object) -> bool:
    if type(value) is not AcquisitionVenueProjection:
        return False
    try:
        source_kind = value.source_kind
        application_generation_id = value.application_generation_id
        position_scope = value.position_scope
        predecessor_execution_snapshot_commitment = (
            value.predecessor_execution_snapshot_commitment
        )
        execution_snapshot_commitment = value.execution_snapshot_commitment
        predecessor_scope_execution_commitment = (
            value.predecessor_scope_execution_commitment
        )
        scope_execution_commitment = value.scope_execution_commitment
        predecessor_venue_commitment = value.predecessor_venue_commitment
        venue_commitment = value.venue_commitment
        source_commitment = value.source_commitment
        fact_relation = value._fact_relation
        serving = value._serving
        seal = value._seal
    except AttributeError:
        return False
    return bool(
        type(source_kind) is AcquisitionVenueSourceKind
        and type(application_generation_id) is ApplicationGenerationId
        and type(position_scope) is PositionScope
        and type(execution_snapshot_commitment) is bytes
        and len(execution_snapshot_commitment) == 32
        and type(scope_execution_commitment) is bytes
        and len(scope_execution_commitment) == 32
        and type(venue_commitment) is bytes
        and len(venue_commitment) == 32
        and type(source_commitment) is bytes
        and len(source_commitment) == 32
        and _optional_acquisition_digest_is_exact(
            predecessor_execution_snapshot_commitment
        )
        and _optional_acquisition_digest_is_exact(
            predecessor_scope_execution_commitment
        )
        and _optional_acquisition_digest_is_exact(predecessor_venue_commitment)
        and (
            fact_relation is None
            or _acquisition_fact_relation_is_authentic(fact_relation)
        )
        and type(serving) is bool
        and type(seal) is bytes
        and len(seal) == 32
        and (
            not serving
            or (
                source_kind is AcquisitionVenueSourceKind.BOOTSTRAP
                and fact_relation is None
            )
            or (
                source_kind
                in {
                    AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT,
                    AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION,
                }
                and fact_relation is not None
                and fact_relation.application_generation_id == application_generation_id
                and fact_relation.position_scope == position_scope
            )
        )
        and seal
        == _acquisition_venue_projection_seal(
            source_kind,
            application_generation_id,
            position_scope,
            predecessor_execution_snapshot_commitment,
            execution_snapshot_commitment,
            predecessor_scope_execution_commitment,
            scope_execution_commitment,
            predecessor_venue_commitment,
            venue_commitment,
            source_commitment,
            fact_relation,
            serving,
        )
    )


def _new_acquisition_venue_projection(
    *,
    source_kind: AcquisitionVenueSourceKind,
    context: AcquisitionVenueContext,
    predecessor_execution_snapshot_commitment: bytes | None,
    predecessor_scope_execution_commitment: bytes | None,
    predecessor_venue_commitment: bytes | None,
    source_commitment: bytes,
    fact_relation: AcquisitionFactRelation | None,
    serving: bool,
) -> AcquisitionVenueProjection:
    if (
        type(source_kind) is not AcquisitionVenueSourceKind
        or not _acquisition_venue_context_is_authentic(context)
        or type(source_commitment) is not bytes
        or len(source_commitment) != 32
        or not _optional_acquisition_digest_is_exact(
            predecessor_execution_snapshot_commitment
        )
        or not _optional_acquisition_digest_is_exact(
            predecessor_scope_execution_commitment
        )
        or not _optional_acquisition_digest_is_exact(predecessor_venue_commitment)
        or (
            fact_relation is not None
            and not _acquisition_fact_relation_is_authentic(fact_relation)
        )
    ):
        raise TypeError("acquisition venue projection requires owner-sealed inputs")
    if serving:
        if (
            source_kind is AcquisitionVenueSourceKind.BOOTSTRAP
            and fact_relation is not None
        ):
            raise ValueError("bootstrap projection cannot retain a fact relation")
        if (
            source_kind
            in {
                AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT,
                AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION,
            }
            and fact_relation is None
        ):
            raise ValueError("serving fact projection requires a fact relation")
    elif fact_relation is not None:
        raise ValueError("non-serving projection cannot retain a fact relation")
    result = object.__new__(AcquisitionVenueProjection)
    object.__setattr__(result, "source_kind", source_kind)
    object.__setattr__(
        result, "application_generation_id", context.application_generation_id
    )
    object.__setattr__(result, "position_scope", context.position_scope)
    object.__setattr__(
        result,
        "predecessor_execution_snapshot_commitment",
        predecessor_execution_snapshot_commitment,
    )
    object.__setattr__(
        result,
        "execution_snapshot_commitment",
        context._source_execution_commitment,
    )
    object.__setattr__(
        result,
        "predecessor_scope_execution_commitment",
        predecessor_scope_execution_commitment,
    )
    object.__setattr__(
        result,
        "scope_execution_commitment",
        context.scope_execution_commitment,
    )
    object.__setattr__(
        result,
        "predecessor_venue_commitment",
        predecessor_venue_commitment,
    )
    object.__setattr__(result, "venue_commitment", context.commitment)
    object.__setattr__(result, "source_commitment", source_commitment)
    object.__setattr__(result, "_fact_relation", fact_relation)
    object.__setattr__(result, "_serving", serving)
    object.__setattr__(
        result,
        "_seal",
        _acquisition_venue_projection_seal(
            source_kind,
            context.application_generation_id,
            context.position_scope,
            predecessor_execution_snapshot_commitment,
            context._source_execution_commitment,
            predecessor_scope_execution_commitment,
            context.scope_execution_commitment,
            predecessor_venue_commitment,
            context.commitment,
            source_commitment,
            fact_relation,
            serving,
        ),
    )
    return result


def _new_acquisition_fact_relation(
    proof: _AcquisitionFactProof,
) -> AcquisitionFactRelation:
    if not _acquisition_fact_proof_is_authentic(proof):
        raise ValueError("acquisition fact proof is not authentic")
    result = object.__new__(AcquisitionFactRelation)
    object.__setattr__(
        result, "application_generation_id", proof.application_generation_id
    )
    object.__setattr__(result, "position_scope", proof.position_scope)
    object.__setattr__(result, "fact_key", proof.fact_key)
    object.__setattr__(result, "root_key", proof.root_key)
    object.__setattr__(result, "effect_id", proof.effect_id)
    object.__setattr__(result, "request_occurrence_id", proof.request_occurrence_id)
    object.__setattr__(result, "leg_key", proof.leg_key)
    object.__setattr__(result, "source_commitment", proof.commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition-fact-relation-seal/v1",
            _encode_text(proof.application_generation_id.value),
            _position_scope_index_key(proof.position_scope),
            _canonical_value_commitment(proof.fact_key),
            _canonical_value_commitment(proof.root_key),
            _canonical_value_commitment(proof.effect_id),
            _canonical_value_commitment(proof.request_occurrence_id),
            _canonical_value_commitment(proof.leg_key),
            proof.commitment,
        ),
    )
    return result


def _acquisition_fact_source_item_is_exact(item: object) -> bool:
    from .recovery import RecordBrokerFillEvidence, RecordBrokerRevisionEvidence

    if type(item) is _BrokerExecutionRegistryCatchUp:
        return type(cast(_BrokerExecutionRegistryCatchUp, item).fact) in {
            BrokerFillFact,
            BrokerTradeCorrectFact,
            BrokerTradeBustFact,
        }
    if type(item) is RecordBrokerFillEvidence:
        return type(cast(RecordBrokerFillEvidence, item).fact) is BrokerFillFact
    return type(item) is RecordBrokerRevisionEvidence and type(
        cast(RecordBrokerRevisionEvidence, item).fact
    ) in {BrokerTradeCorrectFact, BrokerTradeBustFact}


def _acquisition_fact_proof_is_authentic(value: object) -> bool:
    from .recovery import RecordBrokerFillEvidence, RecordBrokerRevisionEvidence

    if type(value) is not _AcquisitionFactProof:
        return False
    try:
        application_generation_id = value.application_generation_id
        position_scope = value.position_scope
        fact_key = value.fact_key
        root_key = value.root_key
        effect_id = value.effect_id
        request_occurrence_id = value.request_occurrence_id
        leg_key = value.leg_key
        predecessor_execution_snapshot_commitment = (
            value.predecessor_execution_snapshot_commitment
        )
        execution_snapshot_commitment = value.execution_snapshot_commitment
        predecessor_scope_execution_commitment = (
            value.predecessor_scope_execution_commitment
        )
        scope_execution_commitment = value.scope_execution_commitment
        predecessor_venue_commitment = value.predecessor_venue_commitment
        venue_commitment = value.venue_commitment
        command_commitment = value.command_commitment
        source_kind = value.source_kind
        source_item = value._source_item
    except AttributeError:
        return False
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(fact_key) is not ExecutionFactKey
        or type(root_key) is not RootFillKey
        or type(effect_id) is not EffectId
        or type(request_occurrence_id) is not RequestOccurrenceId
        or type(leg_key) is not VenueLegKey
        or type(source_kind) is not AcquisitionVenueSourceKind
        or not _acquisition_fact_source_item_is_exact(source_item)
    ):
        return False
    exact_source = cast(
        RecordBrokerFillEvidence
        | RecordBrokerRevisionEvidence
        | _BrokerExecutionRegistryCatchUp,
        source_item,
    )
    for digest in (
        predecessor_execution_snapshot_commitment,
        execution_snapshot_commitment,
        predecessor_scope_execution_commitment,
        scope_execution_commitment,
        predecessor_venue_commitment,
        venue_commitment,
        command_commitment,
    ):
        if type(digest) is not bytes or len(digest) != 32:
            return False
    fact = exact_source.fact
    if (
        fact.key != fact_key
        or fact.root_key != root_key
        or fact.scope.position_scope != position_scope
        or exact_source.effect_id != effect_id
        or exact_source.leg_key != leg_key
        or _protection_command_commitment(exact_source) != command_commitment
        or fact_key.broker != position_scope.broker
        or fact_key.environment != position_scope.environment
        or fact_key.account != position_scope.account
        or root_key.broker != position_scope.broker
        or root_key.environment != position_scope.environment
        or root_key.account != position_scope.account
        or leg_key.broker != position_scope.broker
        or leg_key.environment != position_scope.environment
        or leg_key.account != position_scope.account
    ):
        return False
    return source_kind in {
        AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT,
        AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION,
    }


def _canonical_acquisition_fact_observation_matches(
    execution: ExecutionSnapshot,
    proof: _AcquisitionFactProof,
) -> bool:
    from .recovery import RecordBrokerFillEvidence, RecordBrokerRevisionEvidence

    source = cast(
        RecordBrokerFillEvidence
        | RecordBrokerRevisionEvidence
        | _BrokerExecutionRegistryCatchUp,
        proof._source_item,
    )
    observation = execution.seen_facts.get(proof.fact_key)
    if type(observation) is not SeenFact:
        return False
    if (
        observation.fact != source.fact
        or observation.position_scope != proof.position_scope
        or observation.classification
        in {
            FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC,
            FirstObservationClassification.RECONCILIATION_REQUIRED,
        }
    ):
        return False
    return _execution_head_matches_fact(
        execution.root_heads.get(proof.root_key),
        source.fact,
    )


def _direct_acquisition_relation_matches_book(
    book: VenueRecoveryBook,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    request_occurrence_id: RequestOccurrenceId,
    effect_id: EffectId,
    leg_key: VenueLegKey,
    root_key: RootFillKey,
) -> bool:
    """Recheck one fact relation through bounded, current venue indexes only."""

    if (
        type(book) is not VenueRecoveryBook
        or type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(request_occurrence_id) is not RequestOccurrenceId
        or type(effect_id) is not EffectId
        or type(leg_key) is not VenueLegKey
        or type(root_key) is not RootFillKey
        or application_generation_id != book.scope.generation
    ):
        return False
    entry = book._acquisition_correlation_by_root.get(
        _coverage_root_index_key(root_key)
    )
    current = book._effect_by_id.get(_effect_index_key(effect_id))
    owner = book._owner_by_leg.get(_leg_index_key(leg_key))
    mapped_effect_id = book._effect_by_request_occurrence.get(
        _request_occurrence_index_key(request_occurrence_id)
    )
    if (
        type(entry) is not _AcquisitionCorrelationEntry
        or type(current) is not _EffectCurrent
        or type(owner) is not VenueIdentityOwner
        or mapped_effect_id != effect_id
    ):
        return False
    effect_scope = current.effect.scope
    return (
        entry.application_generation_id == application_generation_id
        and entry.position_scope == position_scope
        and entry.request_occurrence_id == request_occurrence_id
        and entry.effect_id == effect_id
        and entry.leg_key == leg_key
        and entry.root_key == root_key
        and effect_scope.generation == application_generation_id
        and effect_scope.position_scope == position_scope
        and effect_scope.request_occurrence_id == request_occurrence_id
        and effect_scope.effect_id == effect_id
        and owner.leg_key == leg_key
        and owner.effect_id == effect_id
        and owner.effect_scope == effect_scope
    )


def _mint_acquisition_fact_proof(
    predecessor_book: VenueRecoveryBook,
    predecessor_execution: ExecutionSnapshot,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
    protection_proof: _ProtectionTransitionProof,
    disposition: VenueRecoveryDisposition,
) -> _AcquisitionFactProof | None:
    """Capture one direct canonical-fact relation at the reducer boundary."""

    from .recovery import RecordBrokerFillEvidence, RecordBrokerRevisionEvidence

    if (
        type(predecessor_book) is not VenueRecoveryBook
        or type(predecessor_execution) is not ExecutionSnapshot
        or type(book) is not VenueRecoveryBook
        or type(execution) is not ExecutionSnapshot
        or not _acquisition_fact_source_item_is_exact(item)
        or not _protection_transition_proof_is_authentic(protection_proof)
        or disposition
        not in {
            VenueRecoveryDisposition.APPLIED,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        }
    ):
        return None
    exact_item = cast(
        RecordBrokerFillEvidence
        | RecordBrokerRevisionEvidence
        | _BrokerExecutionRegistryCatchUp,
        item,
    )
    fact = exact_item.fact
    position_scope = fact.scope.position_scope
    if (
        position_scope != protection_proof.position_scope
        or book.scope.generation != protection_proof.book_scope.generation
        or protection_proof.execution_commitment != execution.commitment
        or protection_proof.predecessor_execution_commitment
        != predecessor_execution.commitment
        or protection_proof.disposition is not disposition
        or protection_proof.command_commitment
        != _protection_command_commitment(exact_item)
    ):
        return None
    predecessor_context = predecessor_book.project_acquisition_context(
        predecessor_execution,
        position_scope,
    )
    context = book.project_acquisition_context(execution, position_scope)
    if not predecessor_context._serving or not context._serving:
        return None
    entry = book._acquisition_correlation_by_root.get(
        _coverage_root_index_key(fact.root_key)
    )
    if (
        type(entry) is not _AcquisitionCorrelationEntry
        or entry.application_generation_id != book.scope.generation
        or entry.position_scope != position_scope
        or entry.effect_id != exact_item.effect_id
        or entry.leg_key != exact_item.leg_key
        or entry.root_key != fact.root_key
    ):
        return None
    if not _direct_acquisition_relation_matches_book(
        book,
        entry.application_generation_id,
        entry.position_scope,
        entry.request_occurrence_id,
        entry.effect_id,
        entry.leg_key,
        entry.root_key,
    ):
        return None
    source_kind = (
        AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION
        if disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
        else AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT
    )
    proof = _AcquisitionFactProof(
        application_generation_id=book.scope.generation,
        position_scope=position_scope,
        fact_key=fact.key,
        root_key=fact.root_key,
        effect_id=exact_item.effect_id,
        request_occurrence_id=entry.request_occurrence_id,
        leg_key=exact_item.leg_key,
        predecessor_execution_snapshot_commitment=predecessor_execution.commitment,
        execution_snapshot_commitment=execution.commitment,
        predecessor_scope_execution_commitment=(
            predecessor_context.scope_execution_commitment
        ),
        scope_execution_commitment=context.scope_execution_commitment,
        predecessor_venue_commitment=predecessor_context.commitment,
        venue_commitment=context.commitment,
        command_commitment=protection_proof.command_commitment,
        source_kind=source_kind,
        _source_item=exact_item,
    )
    if not _acquisition_fact_proof_is_authentic(
        proof
    ) or not _canonical_acquisition_fact_observation_matches(execution, proof):
        return None
    return proof


def _acquisition_fact_proof_matches_transition(
    book: VenueRecoveryBook,
    transition: VenueRecoveryTransition,
) -> bool:
    if (
        type(book) is not VenueRecoveryBook
        or type(transition) is not VenueRecoveryTransition
    ):
        return False
    if book is not transition.book:
        return False
    proof = transition._acquisition_fact_proof
    proof_commitment = transition._acquisition_fact_proof_commitment
    protection_proof = transition._protection_proof
    protection_commitment = transition._protection_proof_commitment
    if (
        type(proof) is not _AcquisitionFactProof
        or type(proof_commitment) is not bytes
        or len(proof_commitment) != 32
        or proof.commitment != proof_commitment
        or type(protection_proof) is not _ProtectionTransitionProof
        or type(protection_commitment) is not bytes
        or len(protection_commitment) != 32
        or protection_proof.commitment != protection_commitment
        or not _acquisition_fact_proof_is_authentic(proof)
        or not _protection_transition_proof_is_authentic(protection_proof)
    ):
        return False
    if (
        proof.application_generation_id != book.scope.generation
        or proof.position_scope != protection_proof.position_scope
        or proof.predecessor_execution_snapshot_commitment
        != protection_proof.predecessor_execution_commitment
        or proof.execution_snapshot_commitment != transition.execution.commitment
        or proof.execution_snapshot_commitment != protection_proof.execution_commitment
        or proof.command_commitment != protection_proof.command_commitment
        or proof.source_kind
        != (
            AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION
            if transition.disposition
            is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
            else AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT
        )
        or transition.disposition
        not in {
            VenueRecoveryDisposition.APPLIED,
            VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
        }
    ):
        return False
    context = book.project_acquisition_context(
        transition.execution, proof.position_scope
    )
    if (
        not context._serving
        or context.scope_execution_commitment != proof.scope_execution_commitment
        or context.commitment != proof.venue_commitment
    ):
        return False
    if not _direct_acquisition_relation_matches_book(
        book,
        proof.application_generation_id,
        proof.position_scope,
        proof.request_occurrence_id,
        proof.effect_id,
        proof.leg_key,
        proof.root_key,
    ):
        return False
    return _canonical_acquisition_fact_observation_matches(transition.execution, proof)


@dataclass(frozen=True, slots=True)
class _AcquisitionCorrelationEntry:
    """Private immutable root provenance retained by the venue reducer."""

    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    request_occurrence_id: RequestOccurrenceId
    effect_id: EffectId
    leg_key: VenueLegKey
    root_key: RootFillKey

    def __post_init__(self) -> None:
        for name, value, expected in (
            (
                "application_generation_id",
                self.application_generation_id,
                ApplicationGenerationId,
            ),
            ("position_scope", self.position_scope, PositionScope),
            ("request_occurrence_id", self.request_occurrence_id, RequestOccurrenceId),
            ("effect_id", self.effect_id, EffectId),
            ("leg_key", self.leg_key, VenueLegKey),
            ("root_key", self.root_key, RootFillKey),
        ):
            _require(name, value, expected)

    @property
    def commitment(self) -> bytes:
        return _acquisition_correlation_commitment(
            self.application_generation_id,
            self.position_scope,
            self.request_occurrence_id,
            self.effect_id,
            self.leg_key,
            self.root_key,
        )


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
            account_reconciliation_required=(execution.account_reconciliation_required),
            reconciliation_transition_count=(execution.reconciliation_transition_count),
            reconciliation_transition_head=(execution.reconciliation_transition_head),
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


_DIRECT_BROKER_FACT_CLASSIFICATIONS = (
    FirstObservationClassification.APPLIED_AVAILABLE,
    FirstObservationClassification.APPLIED_BASIS_PENDING,
    FirstObservationClassification.APPLIED_OVERFILL_QUARANTINE,
    FirstObservationClassification.APPLIED_PENDING_OVERFILL,
)


@dataclass(frozen=True, slots=True)
class _BrokerExecutionRegistryCatchUp:
    """Owner-derived registry catch-up for one direct broker execution fact."""

    input_id: VenueInputId
    target_checkpoint: VenueExecutionCheckpoint
    prior_account_registry_count: int
    prior_account_registry_commitment: bytes
    prior_source_binding: VenueExecutionBinding
    source_execution: ExecutionSnapshot
    fact: BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact
    effect_id: EffectId
    leg_key: VenueLegKey

    def __post_init__(self) -> None:
        _require("input_id", self.input_id, VenueInputId)
        if type(self.target_checkpoint) is not VenueExecutionCheckpoint:
            raise TypeError("target_checkpoint must be exact")
        if (
            type(self.prior_account_registry_count) is not int
            or self.prior_account_registry_count < 0
        ):
            raise ValueError("prior registry count must be non-negative")
        _require_digest(
            "prior_account_registry_commitment",
            self.prior_account_registry_commitment,
        )
        if type(self.prior_source_binding) is not VenueExecutionBinding:
            raise TypeError("prior_source_binding must be exact")
        if type(self.source_execution) is not ExecutionSnapshot:
            raise TypeError("source_execution must be exact")
        if type(self.fact) not in {
            BrokerFillFact,
            BrokerTradeCorrectFact,
            BrokerTradeBustFact,
        }:
            raise TypeError("fact must be an exact broker execution fact")
        _require("effect_id", self.effect_id, EffectId)
        _require("leg_key", self.leg_key, VenueLegKey)
        observation = self.source_execution.seen_facts.get(self.fact.key)
        if (
            self.target_checkpoint.registry_count != self.prior_account_registry_count
            or self.target_checkpoint.registry_commitment
            != self.prior_account_registry_commitment
            or self.target_checkpoint.binding != self.prior_source_binding
            or self.target_checkpoint.position_scope != self.fact.scope.position_scope
            or self.source_execution.position.scope
            != self.target_checkpoint.position_scope
            or self.source_execution.seen_facts.count
            != self.prior_account_registry_count + 1
            or not self.source_execution.seen_facts.has_prefix(
                self.prior_account_registry_count,
                self.prior_account_registry_commitment,
            )
            or self.source_execution.seen_facts.observation_at(
                self.prior_account_registry_count
            )
            != observation
            or observation is None
            or observation.fact != self.fact
            or observation.classification not in _DIRECT_BROKER_FACT_CLASSIFICATIONS
            or self.fact.scope.order_id != self.leg_key.order_id
            or self.fact.scope.broker != self.leg_key.broker
            or self.fact.scope.environment != self.leg_key.environment
            or self.fact.scope.account != self.leg_key.account
        ):
            raise ValueError(
                "broker catch-up must retain one exact owner-attributed observation"
            )

    @property
    def target_scope(self) -> PositionScope:
        return self.target_checkpoint.position_scope


def _require_effect_shape(value: object) -> BrokerEffect:
    _require("effect", value, BrokerEffect)
    effect = cast(BrokerEffect, value)
    BrokerEffect.__post_init__(effect)
    VenueEffectScope.__post_init__(effect.scope)
    return effect


def _require_claim_shape(value: object) -> DispatchClaim:
    _require("claim", value, DispatchClaim)
    claim = cast(DispatchClaim, value)
    DispatchClaim.__post_init__(claim)
    VenueEffectScope.__post_init__(claim.effect_scope)
    return claim


def _require_owner_shape(value: object) -> VenueIdentityOwner:
    _require("owner", value, VenueIdentityOwner)
    owner = cast(VenueIdentityOwner, value)
    VenueIdentityOwner.__post_init__(owner)
    VenueEffectScope.__post_init__(owner.effect_scope)
    return owner


def _require_contradiction_shape(value: object) -> AcceptanceContradiction:
    _require("contradiction", value, AcceptanceContradiction)
    contradiction = cast(AcceptanceContradiction, value)
    _require("contradiction.leg_key", contradiction.leg_key, VenueLegKey)
    _require(
        "contradiction.observation_id",
        contradiction.observation_id,
        VenueObservationId,
    )
    return contradiction


def _require_attempt_shape(value: object) -> VenueAttempt:
    _require("active attempt", value, VenueAttempt)
    attempt = cast(VenueAttempt, value)
    _require("attempt.leg_key", attempt.leg_key, VenueLegKey)
    _require("attempt.status", attempt.status, VenueAttemptState)
    if attempt.pending_operation is not None:
        _require(
            "attempt.pending_operation",
            attempt.pending_operation,
            PendingVenueOperation,
        )
    _require("attempt.cumulative_quantity", attempt.cumulative_quantity, Quantity)
    if type(attempt.cumulative_quantity.value) is not int:
        raise TypeError("attempt.cumulative_quantity.value must be an exact integer")
    if attempt.cumulative_quantity.value < 0:
        raise ValueError("attempt cumulative quantity cannot be negative")
    _require(
        "attempt.last_observation_id",
        attempt.last_observation_id,
        VenueObservationId,
    )
    return attempt


def _require_closure_shape(value: object) -> VenueTerminalClosure:
    _require("closure", value, VenueTerminalClosure)
    closure = cast(VenueTerminalClosure, value)
    for name, component, expected in (
        ("closure.leg_key", closure.leg_key, VenueLegKey),
        ("closure.closure_id", closure.closure_id, ClosureId),
        ("closure.status", closure.status, VenueAttemptState),
        ("closure.cumulative_quantity", closure.cumulative_quantity, Quantity),
        (
            "closure.observed_cumulative_quantity",
            closure.observed_cumulative_quantity,
            Quantity,
        ),
        (
            "closure.evidence_reference",
            closure.evidence_reference,
            EvidenceReference,
        ),
        ("closure.kind", closure.kind, VenueClosureKind),
        ("closure.source_input_id", closure.source_input_id, VenueInputId),
    ):
        _require(name, component, expected)
    if type(closure.ordinal) is not int or closure.ordinal <= 0:
        raise ValueError(
            "closure ordinal must be a positive integer (exact type required)"
        )
    for name, optional_component, optional_expected in (
        (
            "closure.predecessor_closure_id",
            closure.predecessor_closure_id,
            ClosureId,
        ),
        ("closure.observation_id", closure.observation_id, VenueObservationId),
        ("closure.source_event_id", closure.source_event_id, SourceEventId),
        (
            "closure.broker_terminal_state",
            closure.broker_terminal_state,
            VenueAttemptState,
        ),
        ("closure.actor", closure.actor, ActorId),
    ):
        if optional_component is not None:
            _require(name, optional_component, optional_expected)
    if closure.reason is not None and type(closure.reason) is not str:
        raise TypeError("closure.reason must be a string")
    if closure.evidence_digest is not None:
        _require_digest("closure.evidence_digest", closure.evidence_digest)
    return closure


def _require_input_record_shape(value: object) -> VenueInputRecord:
    from .recovery import (
        IngestHumanAttestedFill,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
        ReleaseVenueLeg,
    )

    _require("input record", value, VenueInputRecord)
    record = cast(VenueInputRecord, value)
    _require("input record.input_id", record.input_id, VenueInputId)
    if record.semantic_alias_of is not None:
        _require(
            "input record.semantic_alias_of",
            record.semantic_alias_of,
            VenueInputId,
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
        _BrokerExecutionRegistryCatchUp,
        _BootstrapTargetRegistryInput,
        IngestHumanAttestedFill,
        ReleaseVenueLeg,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
    }
    if type(record.item) not in admitted_types:
        raise TypeError("input record item must be an exact venue-recovery command")
    post_init = getattr(type(record.item), "__post_init__", None)
    if post_init is None:
        raise TypeError("input record item must define exact shape validation")
    post_init(record.item)
    _input_command_identity(record.item, include_input_id=True)
    return record


def _catch_up_input_commitment(
    item: CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
) -> bytes:
    if type(item) not in {
        CatchUpExecutionRegistry,
        _BrokerExecutionRegistryCatchUp,
    }:
        raise TypeError("item must be one exact registry catch-up type")
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
    allow_equal_registry_count: bool = False,
) -> None:
    _require("input_id", input_id, VenueInputId)
    _require_digest("command_commitment", command_commitment)
    if type(target_checkpoint) is not VenueExecutionCheckpoint:
        raise TypeError(
            "target_checkpoint must be the exact VenueExecutionCheckpoint type"
        )
    if type(resulting_registry_count) is not int or (
        resulting_registry_count < target_checkpoint.registry_count
        if allow_equal_registry_count
        else resulting_registry_count <= target_checkpoint.registry_count
    ):
        relation = "precede" if allow_equal_registry_count else "strictly exceed"
        raise ValueError(
            f"resulting_registry_count must not {relation} the target checkpoint"
            if allow_equal_registry_count
            else "resulting_registry_count must strictly exceed the target checkpoint"
        )
    _require_digest("resulting_registry_commitment", resulting_registry_commitment)
    if type(reason) is not str or not reason.strip():
        raise ValueError("reason must be a nonblank string")


class _ResolvedProjectionKind(Enum):
    REGISTRY_ADVANCE = "REGISTRY_ADVANCE"
    RECONCILIATION_CURSOR_ADVANCE = "RECONCILIATION_CURSOR_ADVANCE"


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
    projection_kind: _ResolvedProjectionKind = _ResolvedProjectionKind.REGISTRY_ADVANCE

    def __post_init__(self) -> None:
        if type(self.projection_kind) is not _ResolvedProjectionKind:
            raise TypeError(
                "projection_kind must be the exact resolved projection kind"
            )
        _validate_registry_outcome_common(
            input_id=self.input_id,
            command_commitment=self.command_commitment,
            target_checkpoint=self.target_checkpoint,
            resulting_registry_count=self.resulting_registry_count,
            resulting_registry_commitment=self.resulting_registry_commitment,
            reason=self.reason,
            allow_equal_registry_count=(
                self.projection_kind
                is _ResolvedProjectionKind.RECONCILIATION_CURSOR_ADVANCE
            ),
        )
        if (
            self.projection_kind
            is _ResolvedProjectionKind.RECONCILIATION_CURSOR_ADVANCE
        ):
            if (
                self.resulting_registry_count != self.target_checkpoint.registry_count
                or self.resulting_registry_commitment
                != self.target_checkpoint.registry_commitment
            ):
                raise ValueError(
                    "cursor projection must preserve the exact target registry"
                )
        if type(self.source_binding) is not VenueExecutionBinding:
            raise TypeError(
                "source_binding must be the exact VenueExecutionBinding type"
            )

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


@dataclass(frozen=True, slots=True)
class _AttributedRegistryAdvanceOutcome:
    """New source-symbol truth bound to one exact retained venue owner."""

    input_id: VenueInputId
    command_commitment: bytes
    target_checkpoint: VenueExecutionCheckpoint
    prior_account_registry_count: int
    prior_account_registry_commitment: bytes
    prior_source_binding: VenueExecutionBinding
    resulting_source_binding: VenueExecutionBinding
    effect_id: EffectId
    leg_key: VenueLegKey
    fact: BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact
    observation_classification: FirstObservationClassification
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
            or self.prior_account_registry_count + 1 != self.resulting_registry_count
        ):
            raise ValueError(
                "attributed registry advance must append exactly one observation"
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
        _require("effect_id", self.effect_id, EffectId)
        _require("leg_key", self.leg_key, VenueLegKey)
        if type(self.fact) not in {
            BrokerFillFact,
            BrokerTradeCorrectFact,
            BrokerTradeBustFact,
        }:
            raise TypeError("fact must be one exact broker execution fact")
        if (
            type(self.observation_classification) is not FirstObservationClassification
            or self.observation_classification
            not in _DIRECT_BROKER_FACT_CLASSIFICATIONS
        ):
            raise ValueError(
                "attributed registry advance requires an applied classification"
            )
        if (
            self.target_checkpoint.registry_count != self.prior_account_registry_count
            or self.target_checkpoint.registry_commitment
            != self.prior_account_registry_commitment
            or self.target_checkpoint.binding != self.prior_source_binding
            or self.prior_source_binding.position_scope
            != self.resulting_source_binding.position_scope
            or self.target_checkpoint.position_scope
            != self.resulting_source_binding.position_scope
            or self.fact.scope.position_scope
            != self.resulting_source_binding.position_scope
            or self.fact.key.broker != self.leg_key.broker
            or self.fact.key.environment != self.leg_key.environment
            or self.fact.key.account != self.leg_key.account
            or self.fact.scope.order_id != self.leg_key.order_id
        ):
            raise ValueError(
                "attributed registry advance must retain one exact owner scope"
            )

    @property
    def canonical_applied(self) -> bool:
        return True

    @property
    def attribution_resolved(self) -> bool:
        return True

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
    _ResolvedRegistryProjectionOutcome
    | _UnresolvedRegistryAdvanceOutcome
    | _AttributedRegistryAdvanceOutcome
)


class _RegistryTransitionKind(Enum):
    RESOLVED_TARGET_PROJECTION = "RESOLVED_TARGET_PROJECTION"
    RESOLVED_CURSOR_PROJECTION = "RESOLVED_CURSOR_PROJECTION"
    UNRESOLVED_SOURCE_ADVANCE = "UNRESOLVED_SOURCE_ADVANCE"
    ATTRIBUTED_SOURCE_ADVANCE = "ATTRIBUTED_SOURCE_ADVANCE"


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
    item: CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
    outcome: ExecutionRegistryReconciliationRecord,
) -> _RegistryTransitionProof:
    if type(venue_scope) is not VenueScope:
        raise TypeError("venue_scope must be the exact VenueScope type")
    if type(item) not in {
        CatchUpExecutionRegistry,
        _BrokerExecutionRegistryCatchUp,
    }:
        raise TypeError("registry transition requires one exact CatchUp command")
    if type(item) is CatchUpExecutionRegistry:
        CatchUpExecutionRegistry.__post_init__(item)
    else:
        _BrokerExecutionRegistryCatchUp.__post_init__(
            cast(_BrokerExecutionRegistryCatchUp, item)
        )
    if type(outcome) is _ResolvedRegistryProjectionOutcome:
        _ResolvedRegistryProjectionOutcome.__post_init__(outcome)
    elif type(outcome) is _UnresolvedRegistryAdvanceOutcome:
        _UnresolvedRegistryAdvanceOutcome.__post_init__(outcome)
    elif type(outcome) is _AttributedRegistryAdvanceOutcome:
        _AttributedRegistryAdvanceOutcome.__post_init__(outcome)
    else:
        raise TypeError("registry transition outcome type is not admitted")
    if item.prior_source_binding is None:
        raise ValueError("admitted CatchUp transition requires a prior source binding")
    if type(outcome) is _ResolvedRegistryProjectionOutcome:
        if type(item) is not CatchUpExecutionRegistry:
            raise TypeError("registry projection requires ordinary CatchUp provenance")
        kind = (
            _RegistryTransitionKind.RESOLVED_CURSOR_PROJECTION
            if outcome.projection_kind
            is _ResolvedProjectionKind.RECONCILIATION_CURSOR_ADVANCE
            else _RegistryTransitionKind.RESOLVED_TARGET_PROJECTION
        )
        resulting_source_binding = outcome.source_binding
        if (
            item.prior_account_registry_count != outcome.resulting_registry_count
            or item.prior_account_registry_commitment
            != outcome.resulting_registry_commitment
            or item.prior_source_binding != resulting_source_binding
        ):
            raise ValueError("resolved projection contradicts its exact prior heads")
        if (
            outcome.projection_kind
            is _ResolvedProjectionKind.RECONCILIATION_CURSOR_ADVANCE
            and (item.target_checkpoint.reconciliation_transition_count >= ordinal - 1)
        ):
            raise ValueError(
                "same-registry projection requires a strict reconciliation-cursor prefix"
            )
        resulting_target_binding = item.target_checkpoint.binding
    elif type(outcome) is _UnresolvedRegistryAdvanceOutcome:
        if type(item) is not CatchUpExecutionRegistry:
            raise TypeError("unresolved advance requires ordinary CatchUp provenance")
        kind = _RegistryTransitionKind.UNRESOLVED_SOURCE_ADVANCE
        resulting_source_binding = outcome.resulting_source_binding
        if (
            item.prior_account_registry_count != outcome.prior_account_registry_count
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
    elif type(outcome) is _AttributedRegistryAdvanceOutcome:
        if type(item) is not _BrokerExecutionRegistryCatchUp:
            raise TypeError("attributed advance requires broker-owner provenance")
        kind = _RegistryTransitionKind.ATTRIBUTED_SOURCE_ADVANCE
        resulting_source_binding = outcome.resulting_source_binding
        observation = item.source_execution.seen_facts.get(item.fact.key)
        if (
            item.prior_account_registry_count != outcome.prior_account_registry_count
            or item.prior_account_registry_commitment
            != outcome.prior_account_registry_commitment
            or item.prior_source_binding != outcome.prior_source_binding
            or item.effect_id != outcome.effect_id
            or item.leg_key != outcome.leg_key
            or item.fact != outcome.fact
            or observation is None
            or observation.fact != outcome.fact
            or observation.classification is not outcome.observation_classification
            or item.source_execution.seen_facts.count
            != outcome.resulting_registry_count
            or item.source_execution.seen_facts.commitment
            != outcome.resulting_registry_commitment
            or _execution_binding_for_snapshot(item.source_execution)
            != resulting_source_binding
        ):
            raise ValueError("attributed advance contradicts its exact owner proof")
        resulting_target_binding = resulting_source_binding
    else:
        raise AssertionError("closed registry outcome union was not exhausted")
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
    current_registry_count: int | None,
    current_registry_commitment: bytes | None,
) -> None:
    input_by_id = {record.input_id: record.item for record in inputs}
    catch_up_input_ids = tuple(
        record.input_id
        for record in inputs
        if type(record.item)
        in {
            CatchUpExecutionRegistry,
            _BrokerExecutionRegistryCatchUp,
        }
    )
    if catch_up_input_ids != tuple(outcome.input_id for outcome in outcomes):
        raise ValueError("CatchUp input order contradicts registry outcomes")
    if len(proofs) != len(outcomes):
        raise ValueError("registry transition chain length contradicts outcomes")
    predecessor: bytes | None = None
    prior_result_count: int | None = None
    prior_result_commitment: bytes | None = None
    for ordinal, (proof, outcome) in enumerate(zip(proofs, outcomes), start=1):
        if type(proof) is not _RegistryTransitionProof:
            raise TypeError("registry transition proof type is not admitted")
        item = input_by_id.get(outcome.input_id)
        if type(item) not in {
            CatchUpExecutionRegistry,
            _BrokerExecutionRegistryCatchUp,
        }:
            raise ValueError("registry transition lacks its exact CatchUp input")
        expected = _registry_transition_proof_for(
            ordinal=ordinal,
            predecessor_commitment=predecessor,
            venue_scope=venue_scope,
            item=cast(
                CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
                item,
            ),
            outcome=outcome,
        )
        if proof != expected:
            raise ValueError(
                "registry transition chain contradicts its predecessor or outcome"
            )
        if prior_result_count is not None and (
            proof.prior_account_registry_count < prior_result_count
            or (
                proof.prior_account_registry_count == prior_result_count
                and proof.prior_account_registry_commitment != prior_result_commitment
            )
        ):
            raise ValueError("registry transition predecessor head regresses")
        same_head = bool(
            outcome.resulting_registry_count == proof.prior_account_registry_count
            and outcome.resulting_registry_commitment
            == proof.prior_account_registry_commitment
        )
        if same_head != (
            proof.kind
            in {
                _RegistryTransitionKind.RESOLVED_TARGET_PROJECTION,
                _RegistryTransitionKind.RESOLVED_CURSOR_PROJECTION,
            }
        ):
            raise ValueError(
                "registry transition kind contradicts its account-head advance"
            )
        prior_result_count = outcome.resulting_registry_count
        prior_result_commitment = outcome.resulting_registry_commitment
        predecessor = proof.commitment
    if predecessor != head_commitment:
        raise ValueError("registry transition chain head does not close exactly")
    if outcomes and (
        current_registry_count != prior_result_count
        or current_registry_commitment != prior_result_commitment
    ):
        raise ValueError("registry transition chain does not close at current registry")


class _ProtectionTransitionSourceKind(str, Enum):
    """Private owner-selected source of one protection cursor transition."""

    ORDINARY = "ORDINARY"
    SERIAL_SUCCESSOR_ROLLOVER = "SERIAL_SUCCESSOR_ROLLOVER"


_ORDINARY_PROTECTION_TRANSITION_SOURCE_BINDING = _commit_parts(
    b"execution-core/protection-transition-source/ordinary/v1"
)


@dataclass(frozen=True, slots=True)
class _ProtectionCursor:
    """Per-position predecessor-linked protection projection cursor."""

    ordinal: int
    head: bytes
    mandate_id: MandateId | None
    execution_commitment: bytes | None
    execution_checkpoint: VenueExecutionCheckpoint | None

    def __post_init__(self) -> None:
        if type(self.ordinal) is not int or self.ordinal < 0:
            raise ValueError("protection cursor ordinal must be a non-negative integer")
        _require_digest("protection cursor head", self.head)
        if self.mandate_id is not None and type(self.mandate_id) is not MandateId:
            raise TypeError("protection cursor mandate_id must be MandateId or None")
        if (self.execution_commitment is None) != (self.execution_checkpoint is None):
            raise ValueError(
                "protection cursor execution seal must be wholly present or absent"
            )
        if self.execution_commitment is not None:
            _require_digest(
                "protection cursor execution commitment",
                self.execution_commitment,
            )
            if type(self.execution_checkpoint) is not VenueExecutionCheckpoint:
                raise TypeError("protection cursor execution checkpoint must be exact")

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/protection-cursor/v2",
            _canonical_value_commitment(self.ordinal),
            self.head,
            _canonical_value_commitment(self.mandate_id),
            _canonical_value_commitment(self.execution_commitment),
            _canonical_value_commitment(self.execution_checkpoint),
        )


@dataclass(frozen=True, slots=True)
class _ProtectionTransitionProof:
    """Bounded proof of one venue transition's protection projection inputs."""

    position_scope: PositionScope
    predecessor_cursor: _ProtectionCursor
    cursor: _ProtectionCursor
    predecessor_book_scope: VenueScope
    book_scope: VenueScope
    predecessor_book_commitment: bytes
    book_commitment: bytes
    predecessor_execution_commitment: bytes
    execution_commitment: bytes
    predecessor_execution_checkpoint: VenueExecutionCheckpoint
    execution_checkpoint: VenueExecutionCheckpoint
    predecessor_summary: _SymbolAuthoritySummary
    summary: _SymbolAuthoritySummary
    predecessor_binding: VenueExecutionBinding | None
    binding: VenueExecutionBinding | None
    predecessor_execution_binding_matches: bool
    execution_binding_matches: bool
    predecessor_account_reconciliation_clear: bool
    account_reconciliation_clear: bool
    command_commitment: bytes
    disposition: VenueRecoveryDisposition
    quantity_delta: int
    source_kind: _ProtectionTransitionSourceKind = (
        _ProtectionTransitionSourceKind.ORDINARY
    )
    source_binding: bytes = _ORDINARY_PROTECTION_TRANSITION_SOURCE_BINDING

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/protection-transition-proof/v1",
            _canonical_value_commitment(self),
        )

    @property
    def lineage_is_authentic(self) -> bool:
        return _protection_transition_proof_is_authentic(self)


@dataclass(frozen=True, slots=True)
class _AcquisitionFactProof:
    """Private, direct provenance envelope for one applied broker fact.

    The venue reducer retains the exact economic command only inside this
    envelope.  The later acquisition projection exposes a small, sealed key
    relation instead of the command, an effect history, or a venue collection.
    """

    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    fact_key: ExecutionFactKey
    root_key: RootFillKey
    effect_id: EffectId
    request_occurrence_id: RequestOccurrenceId
    leg_key: VenueLegKey
    predecessor_execution_snapshot_commitment: bytes
    execution_snapshot_commitment: bytes
    predecessor_scope_execution_commitment: bytes
    scope_execution_commitment: bytes
    predecessor_venue_commitment: bytes
    venue_commitment: bytes
    command_commitment: bytes
    source_kind: AcquisitionVenueSourceKind
    _source_item: object = field(repr=False)

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/acquisition-fact-proof/v1",
            _encode_text(self.application_generation_id.value),
            _position_scope_index_key(self.position_scope),
            _canonical_value_commitment(self.fact_key),
            _canonical_value_commitment(self.root_key),
            _canonical_value_commitment(self.effect_id),
            _canonical_value_commitment(self.request_occurrence_id),
            _canonical_value_commitment(self.leg_key),
            self.predecessor_execution_snapshot_commitment,
            self.execution_snapshot_commitment,
            self.predecessor_scope_execution_commitment,
            self.scope_execution_commitment,
            self.predecessor_venue_commitment,
            self.venue_commitment,
            self.command_commitment,
            _encode_text(self.source_kind.value),
            _canonical_value_commitment(self._source_item),
        )


@dataclass(frozen=True, slots=True, init=False)
class VenueRecoveryTransition:
    book: VenueRecoveryBook
    execution: ExecutionSnapshot
    disposition: VenueRecoveryDisposition
    quantity_delta: int
    _source_item: object | None
    _protection_proof: _ProtectionTransitionProof
    _protection_proof_commitment: bytes
    _acquisition_fact_proof: _AcquisitionFactProof | None
    _acquisition_fact_proof_commitment: bytes | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError(
            "VenueRecoveryTransition is opaque and reducer-constructed only"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("VenueRecoveryTransition cannot be subclassed")

    def _m2_derivative_commitment(self) -> bytes:
        """Return one owner-authenticated derivative binding to peer owners."""

        _m2_venue_transition_source_item(self)
        return self._protection_proof_commitment


class _BootstrapSourceKind(str, Enum):
    """The only owner-selected origins for an unbound target checkpoint."""

    EMPTY_ACCOUNT = "EMPTY_ACCOUNT"
    SAME_ACCOUNT_SOURCE = "SAME_ACCOUNT_SOURCE"


@dataclass(frozen=True, slots=True, init=False)
class _BootstrapTargetRegistryInput:
    """Private, deterministic provenance for one first target checkpoint.

    This is intentionally not a public reducer input.  Authority derives every
    component from the exact venue/source boundary, then the venue reducer
    retains the command only as permanent provenance for the sealed target
    record.  It carries commitments rather than a caller-supplied snapshot or
    input identity.
    """

    input_id: VenueInputId = field(init=False)
    application_generation_id: ApplicationGenerationId = field(init=False)
    source_kind: _BootstrapSourceKind = field(init=False)
    position_scope: PositionScope = field(init=False)
    source_execution_commitment: bytes = field(init=False)
    target_genesis_execution_commitment: bytes = field(init=False)
    target_execution_commitment: bytes = field(init=False)
    prior_account_registry_count: int = field(init=False)
    prior_account_registry_commitment: bytes = field(init=False)
    reconciliation_transition_count: int = field(init=False)
    reconciliation_transition_head: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("bootstrap target registry input is venue-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("bootstrap target registry input cannot be subclassed")

    def __post_init__(self) -> None:
        if (
            type(self.input_id) is not VenueInputId
            or type(self.application_generation_id) is not ApplicationGenerationId
            or type(self.source_kind) is not _BootstrapSourceKind
            or type(self.position_scope) is not PositionScope
            or type(self.prior_account_registry_count) is not int
            or self.prior_account_registry_count < 0
            or type(self.reconciliation_transition_count) is not int
            or self.reconciliation_transition_count < 0
        ):
            raise TypeError("bootstrap target input has an invalid exact shape")
        for name in (
            "source_execution_commitment",
            "target_genesis_execution_commitment",
            "target_execution_commitment",
            "prior_account_registry_commitment",
            "reconciliation_transition_head",
            "commitment",
            "_seal",
        ):
            _require_digest(name, getattr(self, name))


@dataclass(frozen=True, slots=True, init=False)
class _BootstrapBoundTargetRecord:
    """Sealed bounded current-state evidence for one unbound target bootstrap."""

    application_generation_id: ApplicationGenerationId = field(init=False)
    position_scope: PositionScope = field(init=False)
    source_kind: _BootstrapSourceKind = field(init=False)
    source_execution_commitment: bytes = field(init=False)
    target_genesis_execution_commitment: bytes = field(init=False)
    target_execution_commitment: bytes = field(init=False)
    binding: VenueExecutionBinding = field(init=False)
    account_registry_count: int = field(init=False)
    account_registry_commitment: bytes = field(init=False)
    reconciliation_transition_count: int = field(init=False)
    reconciliation_transition_head: bytes = field(init=False)
    bootstrap_input_id: VenueInputId = field(init=False)
    bootstrap_input_commitment: bytes = field(init=False)
    # Bootstrap provenance remains immutable even when the bounded serving
    # checkpoint later advances through one ordinary zero-economic catch-up.
    bootstrap_target_execution_commitment: bytes = field(init=False)
    bootstrap_account_registry_count: int = field(init=False)
    bootstrap_account_registry_commitment: bytes = field(init=False)
    bootstrap_reconciliation_transition_count: int = field(init=False)
    bootstrap_reconciliation_transition_head: bytes = field(init=False)
    bootstrap_neutral_checkpoint_proof_commitment: bytes = field(init=False)
    _bootstrap_neutral_checkpoint_proof: _ProtectionTransitionProof = field(
        init=False,
        repr=False,
    )
    checkpoint_input_id: VenueInputId = field(init=False)
    checkpoint_command_commitment: bytes = field(init=False)
    neutral_checkpoint_proof_commitment: bytes = field(init=False)
    _neutral_checkpoint_proof: _ProtectionTransitionProof = field(
        init=False,
        repr=False,
    )
    _map_seal: bytes = field(init=False, repr=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("bootstrap-bound target records are venue-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("bootstrap-bound target records cannot be subclassed")


def _bootstrap_target_registry_input_commitment(
    *,
    application_generation_id: ApplicationGenerationId,
    source_kind: _BootstrapSourceKind,
    position_scope: PositionScope,
    source_execution_commitment: bytes,
    target_genesis_execution_commitment: bytes,
    target_execution_commitment: bytes,
    prior_account_registry_count: int,
    prior_account_registry_commitment: bytes,
    reconciliation_transition_count: int,
    reconciliation_transition_head: bytes,
) -> bytes:
    return _commit_parts(
        b"execution-core/bootstrap-target-registry-input/v1",
        _encode_text(application_generation_id.value),
        _encode_text(source_kind.value),
        _position_scope_index_key(position_scope),
        source_execution_commitment,
        target_genesis_execution_commitment,
        target_execution_commitment,
        _encode_int(prior_account_registry_count),
        prior_account_registry_commitment,
        _encode_int(reconciliation_transition_count),
        reconciliation_transition_head,
    )


def _bootstrap_target_registry_input_id(commitment: bytes) -> VenueInputId:
    _require_digest("bootstrap input commitment", commitment)
    return VenueInputId(
        _commit_parts(
            b"execution-core/bootstrap-target-registry-input-id/v1",
            commitment,
        ).hex()
    )


def _new_bootstrap_target_registry_input(
    *,
    application_generation_id: ApplicationGenerationId,
    source_kind: _BootstrapSourceKind,
    position_scope: PositionScope,
    source_execution_commitment: bytes,
    target_genesis_execution_commitment: bytes,
    target_execution_commitment: bytes,
    prior_account_registry_count: int,
    prior_account_registry_commitment: bytes,
    reconciliation_transition_count: int,
    reconciliation_transition_head: bytes,
) -> _BootstrapTargetRegistryInput:
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(source_kind) is not _BootstrapSourceKind
        or type(position_scope) is not PositionScope
        or type(prior_account_registry_count) is not int
        or prior_account_registry_count < 0
        or type(reconciliation_transition_count) is not int
        or reconciliation_transition_count < 0
    ):
        raise TypeError("bootstrap target input requires exact owner values")
    for name, value in (
        ("source_execution_commitment", source_execution_commitment),
        ("target_genesis_execution_commitment", target_genesis_execution_commitment),
        ("target_execution_commitment", target_execution_commitment),
        ("prior_account_registry_commitment", prior_account_registry_commitment),
        ("reconciliation_transition_head", reconciliation_transition_head),
    ):
        _require_digest(name, value)
    commitment = _bootstrap_target_registry_input_commitment(
        application_generation_id=application_generation_id,
        source_kind=source_kind,
        position_scope=position_scope,
        source_execution_commitment=source_execution_commitment,
        target_genesis_execution_commitment=target_genesis_execution_commitment,
        target_execution_commitment=target_execution_commitment,
        prior_account_registry_count=prior_account_registry_count,
        prior_account_registry_commitment=prior_account_registry_commitment,
        reconciliation_transition_count=reconciliation_transition_count,
        reconciliation_transition_head=reconciliation_transition_head,
    )
    result = object.__new__(_BootstrapTargetRegistryInput)
    object.__setattr__(
        result, "input_id", _bootstrap_target_registry_input_id(commitment)
    )
    object.__setattr__(result, "application_generation_id", application_generation_id)
    object.__setattr__(result, "source_kind", source_kind)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(
        result, "source_execution_commitment", source_execution_commitment
    )
    object.__setattr__(
        result,
        "target_genesis_execution_commitment",
        target_genesis_execution_commitment,
    )
    object.__setattr__(
        result, "target_execution_commitment", target_execution_commitment
    )
    object.__setattr__(
        result, "prior_account_registry_count", prior_account_registry_count
    )
    object.__setattr__(
        result,
        "prior_account_registry_commitment",
        prior_account_registry_commitment,
    )
    object.__setattr__(
        result,
        "reconciliation_transition_count",
        reconciliation_transition_count,
    )
    object.__setattr__(
        result,
        "reconciliation_transition_head",
        reconciliation_transition_head,
    )
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/bootstrap-target-registry-input-seal/v1",
            result.input_id.value.encode("utf-8"),
            commitment,
        ),
    )
    result.__post_init__()
    return result


def _bootstrap_target_registry_input_is_authentic(value: object) -> bool:
    if type(value) is not _BootstrapTargetRegistryInput:
        return False
    try:
        value.__post_init__()
        expected = _bootstrap_target_registry_input_commitment(
            application_generation_id=value.application_generation_id,
            source_kind=value.source_kind,
            position_scope=value.position_scope,
            source_execution_commitment=value.source_execution_commitment,
            target_genesis_execution_commitment=(
                value.target_genesis_execution_commitment
            ),
            target_execution_commitment=value.target_execution_commitment,
            prior_account_registry_count=value.prior_account_registry_count,
            prior_account_registry_commitment=value.prior_account_registry_commitment,
            reconciliation_transition_count=value.reconciliation_transition_count,
            reconciliation_transition_head=value.reconciliation_transition_head,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        value.commitment == expected
        and value.input_id == _bootstrap_target_registry_input_id(expected)
        and value._seal
        == _commit_parts(
            b"execution-core/bootstrap-target-registry-input-seal/v1",
            value.input_id.value.encode("utf-8"),
            expected,
        )
    )


def _bootstrap_bound_target_record_map_seal(
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    source_kind: _BootstrapSourceKind,
    source_execution_commitment: bytes,
    target_genesis_execution_commitment: bytes,
    target_execution_commitment: bytes,
    binding: VenueExecutionBinding,
    account_registry_count: int,
    account_registry_commitment: bytes,
    reconciliation_transition_count: int,
    reconciliation_transition_head: bytes,
    bootstrap_input_id: VenueInputId,
    bootstrap_input_commitment: bytes,
    bootstrap_target_execution_commitment: bytes,
    bootstrap_account_registry_count: int,
    bootstrap_account_registry_commitment: bytes,
    bootstrap_reconciliation_transition_count: int,
    bootstrap_reconciliation_transition_head: bytes,
    checkpoint_input_id: VenueInputId,
    checkpoint_command_commitment: bytes,
) -> bytes:
    return _commit_parts(
        b"execution-core/bootstrap-bound-target-record/map-seal/v2",
        _encode_text(application_generation_id.value),
        _position_scope_index_key(position_scope),
        _encode_text(source_kind.value),
        source_execution_commitment,
        target_genesis_execution_commitment,
        bootstrap_target_execution_commitment,
        _encode_int(bootstrap_account_registry_count),
        bootstrap_account_registry_commitment,
        _encode_int(bootstrap_reconciliation_transition_count),
        bootstrap_reconciliation_transition_head,
        target_execution_commitment,
        _canonical_value_commitment(binding),
        _encode_int(account_registry_count),
        account_registry_commitment,
        _encode_int(reconciliation_transition_count),
        reconciliation_transition_head,
        _canonical_value_commitment(bootstrap_input_id),
        bootstrap_input_commitment,
        _canonical_value_commitment(checkpoint_input_id),
        checkpoint_command_commitment,
    )


def _bootstrap_bound_target_record_commitment(
    *,
    map_seal: bytes,
    bootstrap_neutral_checkpoint_proof_commitment: bytes,
    neutral_checkpoint_proof_commitment: bytes,
) -> bytes:
    """Bind the current map seal to immutable bootstrap and current proofs."""

    _require_digest("bootstrap record map seal", map_seal)
    _require_digest(
        "bootstrap neutral checkpoint proof commitment",
        bootstrap_neutral_checkpoint_proof_commitment,
    )
    _require_digest(
        "neutral checkpoint proof commitment", neutral_checkpoint_proof_commitment
    )
    return _commit_parts(
        b"execution-core/bootstrap-bound-target-record/v3",
        map_seal,
        bootstrap_neutral_checkpoint_proof_commitment,
        neutral_checkpoint_proof_commitment,
    )


def _new_bootstrap_bound_target_record(
    *,
    application_generation_id: ApplicationGenerationId,
    position_scope: PositionScope,
    source_kind: _BootstrapSourceKind,
    source_execution_commitment: bytes,
    target_genesis_execution_commitment: bytes,
    target_execution_commitment: bytes,
    binding: VenueExecutionBinding,
    account_registry_count: int,
    account_registry_commitment: bytes,
    reconciliation_transition_count: int,
    reconciliation_transition_head: bytes,
    bootstrap_input: _BootstrapTargetRegistryInput,
    neutral_checkpoint_proof: _ProtectionTransitionProof,
    bootstrap_neutral_checkpoint_proof: _ProtectionTransitionProof | None = None,
    checkpoint_input_id: VenueInputId | None = None,
    checkpoint_command_commitment: bytes | None = None,
) -> _BootstrapBoundTargetRecord:
    if (
        type(application_generation_id) is not ApplicationGenerationId
        or type(position_scope) is not PositionScope
        or type(source_kind) is not _BootstrapSourceKind
        or type(binding) is not VenueExecutionBinding
        or binding.position_scope != position_scope
        or type(account_registry_count) is not int
        or account_registry_count < 0
        or not _bootstrap_target_registry_input_is_authentic(bootstrap_input)
        or not _protection_transition_proof_is_authentic(neutral_checkpoint_proof)
    ):
        raise TypeError("bootstrap record requires exact venue-owned components")
    for name, value in (
        ("source_execution_commitment", source_execution_commitment),
        ("target_genesis_execution_commitment", target_genesis_execution_commitment),
        ("target_execution_commitment", target_execution_commitment),
        ("account_registry_commitment", account_registry_commitment),
        ("reconciliation_transition_head", reconciliation_transition_head),
    ):
        _require_digest(name, value)
    if bootstrap_neutral_checkpoint_proof is None:
        bootstrap_neutral_checkpoint_proof = neutral_checkpoint_proof
    if not _protection_transition_proof_is_authentic(
        bootstrap_neutral_checkpoint_proof
    ):
        raise TypeError("bootstrap record requires one exact anchor proof")
    if checkpoint_input_id is None:
        checkpoint_input_id = bootstrap_input.input_id
    if checkpoint_command_commitment is None:
        checkpoint_command_commitment = _protection_command_commitment(bootstrap_input)
    if type(checkpoint_input_id) is not VenueInputId:
        raise TypeError("bootstrap record checkpoint input must be exact")
    _require_digest("checkpoint command commitment", checkpoint_command_commitment)
    if (
        bootstrap_input.application_generation_id != application_generation_id
        or bootstrap_input.source_kind is not source_kind
        or bootstrap_input.position_scope != position_scope
        or bootstrap_input.source_execution_commitment != source_execution_commitment
        or bootstrap_input.target_genesis_execution_commitment
        != target_genesis_execution_commitment
    ):
        raise ValueError("bootstrap record contradicts its private input")
    # Without an explicitly retained older anchor, this is the initial record
    # and its serving values must still be identical to bootstrap provenance.
    if bootstrap_neutral_checkpoint_proof is neutral_checkpoint_proof and (
        bootstrap_input.target_execution_commitment != target_execution_commitment
        or bootstrap_input.prior_account_registry_count != account_registry_count
        or bootstrap_input.prior_account_registry_commitment
        != account_registry_commitment
        or bootstrap_input.reconciliation_transition_count
        != reconciliation_transition_count
        or bootstrap_input.reconciliation_transition_head
        != reconciliation_transition_head
        or checkpoint_input_id != bootstrap_input.input_id
        or checkpoint_command_commitment
        != _protection_command_commitment(bootstrap_input)
    ):
        raise ValueError("initial bootstrap record must match its private input")
    bootstrap_proof_commitment = bootstrap_neutral_checkpoint_proof.commitment
    proof_commitment = neutral_checkpoint_proof.commitment
    map_seal = _bootstrap_bound_target_record_map_seal(
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        source_kind=source_kind,
        source_execution_commitment=source_execution_commitment,
        target_genesis_execution_commitment=target_genesis_execution_commitment,
        target_execution_commitment=target_execution_commitment,
        binding=binding,
        account_registry_count=account_registry_count,
        account_registry_commitment=account_registry_commitment,
        reconciliation_transition_count=reconciliation_transition_count,
        reconciliation_transition_head=reconciliation_transition_head,
        bootstrap_input_id=bootstrap_input.input_id,
        bootstrap_input_commitment=bootstrap_input.commitment,
        bootstrap_target_execution_commitment=(
            bootstrap_input.target_execution_commitment
        ),
        bootstrap_account_registry_count=bootstrap_input.prior_account_registry_count,
        bootstrap_account_registry_commitment=(
            bootstrap_input.prior_account_registry_commitment
        ),
        bootstrap_reconciliation_transition_count=(
            bootstrap_input.reconciliation_transition_count
        ),
        bootstrap_reconciliation_transition_head=(
            bootstrap_input.reconciliation_transition_head
        ),
        checkpoint_input_id=checkpoint_input_id,
        checkpoint_command_commitment=checkpoint_command_commitment,
    )
    commitment = _bootstrap_bound_target_record_commitment(
        map_seal=map_seal,
        bootstrap_neutral_checkpoint_proof_commitment=bootstrap_proof_commitment,
        neutral_checkpoint_proof_commitment=proof_commitment,
    )
    result = object.__new__(_BootstrapBoundTargetRecord)
    object.__setattr__(result, "application_generation_id", application_generation_id)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(result, "source_kind", source_kind)
    object.__setattr__(
        result, "source_execution_commitment", source_execution_commitment
    )
    object.__setattr__(
        result,
        "target_genesis_execution_commitment",
        target_genesis_execution_commitment,
    )
    object.__setattr__(
        result, "target_execution_commitment", target_execution_commitment
    )
    object.__setattr__(result, "binding", binding)
    object.__setattr__(result, "account_registry_count", account_registry_count)
    object.__setattr__(
        result,
        "account_registry_commitment",
        account_registry_commitment,
    )
    object.__setattr__(
        result,
        "reconciliation_transition_count",
        reconciliation_transition_count,
    )
    object.__setattr__(
        result,
        "reconciliation_transition_head",
        reconciliation_transition_head,
    )
    object.__setattr__(result, "bootstrap_input_id", bootstrap_input.input_id)
    object.__setattr__(result, "bootstrap_input_commitment", bootstrap_input.commitment)
    object.__setattr__(
        result,
        "bootstrap_target_execution_commitment",
        bootstrap_input.target_execution_commitment,
    )
    object.__setattr__(
        result,
        "bootstrap_account_registry_count",
        bootstrap_input.prior_account_registry_count,
    )
    object.__setattr__(
        result,
        "bootstrap_account_registry_commitment",
        bootstrap_input.prior_account_registry_commitment,
    )
    object.__setattr__(
        result,
        "bootstrap_reconciliation_transition_count",
        bootstrap_input.reconciliation_transition_count,
    )
    object.__setattr__(
        result,
        "bootstrap_reconciliation_transition_head",
        bootstrap_input.reconciliation_transition_head,
    )
    object.__setattr__(
        result,
        "bootstrap_neutral_checkpoint_proof_commitment",
        bootstrap_proof_commitment,
    )
    object.__setattr__(
        result,
        "_bootstrap_neutral_checkpoint_proof",
        bootstrap_neutral_checkpoint_proof,
    )
    object.__setattr__(result, "checkpoint_input_id", checkpoint_input_id)
    object.__setattr__(
        result,
        "checkpoint_command_commitment",
        checkpoint_command_commitment,
    )
    object.__setattr__(result, "neutral_checkpoint_proof_commitment", proof_commitment)
    object.__setattr__(result, "_neutral_checkpoint_proof", neutral_checkpoint_proof)
    object.__setattr__(result, "_map_seal", map_seal)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/bootstrap-bound-target-record-seal/v1",
            commitment,
            map_seal,
        ),
    )
    return result


def _bootstrap_bound_target_record_is_authentic(value: object) -> bool:
    if type(value) is not _BootstrapBoundTargetRecord:
        return False
    try:
        if (
            type(value.application_generation_id) is not ApplicationGenerationId
            or type(value.position_scope) is not PositionScope
            or type(value.source_kind) is not _BootstrapSourceKind
            or type(value.binding) is not VenueExecutionBinding
            or value.binding.position_scope != value.position_scope
            or type(value.account_registry_count) is not int
            or value.account_registry_count < 0
            or type(value.bootstrap_input_id) is not VenueInputId
            or type(value.bootstrap_account_registry_count) is not int
            or value.bootstrap_account_registry_count < 0
            or type(value.checkpoint_input_id) is not VenueInputId
            or type(value._bootstrap_neutral_checkpoint_proof)
            is not _ProtectionTransitionProof
            or not _protection_transition_proof_is_authentic(
                value._bootstrap_neutral_checkpoint_proof
            )
            or type(value._neutral_checkpoint_proof) is not _ProtectionTransitionProof
            or not _protection_transition_proof_is_authentic(
                value._neutral_checkpoint_proof
            )
        ):
            return False
        for digest in (
            value.source_execution_commitment,
            value.target_genesis_execution_commitment,
            value.target_execution_commitment,
            value.account_registry_commitment,
            value.reconciliation_transition_head,
            value.bootstrap_input_commitment,
            value.bootstrap_target_execution_commitment,
            value.bootstrap_account_registry_commitment,
            value.bootstrap_reconciliation_transition_head,
            value.bootstrap_neutral_checkpoint_proof_commitment,
            value.checkpoint_command_commitment,
            value.neutral_checkpoint_proof_commitment,
            value._map_seal,
            value.commitment,
            value._seal,
        ):
            if type(digest) is not bytes or len(digest) != 32:
                return False
        expected_map_seal = _bootstrap_bound_target_record_map_seal(
            application_generation_id=value.application_generation_id,
            position_scope=value.position_scope,
            source_kind=value.source_kind,
            source_execution_commitment=value.source_execution_commitment,
            target_genesis_execution_commitment=(
                value.target_genesis_execution_commitment
            ),
            target_execution_commitment=value.target_execution_commitment,
            binding=value.binding,
            account_registry_count=value.account_registry_count,
            account_registry_commitment=value.account_registry_commitment,
            reconciliation_transition_count=value.reconciliation_transition_count,
            reconciliation_transition_head=value.reconciliation_transition_head,
            bootstrap_input_id=value.bootstrap_input_id,
            bootstrap_input_commitment=value.bootstrap_input_commitment,
            bootstrap_target_execution_commitment=(
                value.bootstrap_target_execution_commitment
            ),
            bootstrap_account_registry_count=value.bootstrap_account_registry_count,
            bootstrap_account_registry_commitment=(
                value.bootstrap_account_registry_commitment
            ),
            bootstrap_reconciliation_transition_count=(
                value.bootstrap_reconciliation_transition_count
            ),
            bootstrap_reconciliation_transition_head=(
                value.bootstrap_reconciliation_transition_head
            ),
            checkpoint_input_id=value.checkpoint_input_id,
            checkpoint_command_commitment=value.checkpoint_command_commitment,
        )
        expected = _bootstrap_bound_target_record_commitment(
            map_seal=expected_map_seal,
            bootstrap_neutral_checkpoint_proof_commitment=(
                value.bootstrap_neutral_checkpoint_proof_commitment
            ),
            neutral_checkpoint_proof_commitment=(
                value.neutral_checkpoint_proof_commitment
            ),
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        value.bootstrap_neutral_checkpoint_proof_commitment
        == value._bootstrap_neutral_checkpoint_proof.commitment
        and value.neutral_checkpoint_proof_commitment
        == value._neutral_checkpoint_proof.commitment
        and value._map_seal == expected_map_seal
        and value.commitment == expected
        and value._seal
        == _commit_parts(
            b"execution-core/bootstrap-bound-target-record-seal/v1",
            expected,
            expected_map_seal,
        )
    )


@dataclass(frozen=True, slots=True, init=False)
class _StagedBootstrapBoundTargetRecord:
    """Ephemeral proof-independent replacement during one exact catch-up.

    A normal venue transition must mint its protection proof after its next
    compact book root is known.  This private staging value commits the future
    map root while retaining the prior immutable anchor.  It is finalized to
    an authenticated active record before any transition is returned.
    """

    active_record: _BootstrapBoundTargetRecord = field(init=False, repr=False)
    target_execution_commitment: bytes = field(init=False)
    account_registry_count: int = field(init=False)
    account_registry_commitment: bytes = field(init=False)
    reconciliation_transition_count: int = field(init=False)
    reconciliation_transition_head: bytes = field(init=False)
    checkpoint_input_id: VenueInputId = field(init=False)
    checkpoint_command_commitment: bytes = field(init=False)
    _map_seal: bytes = field(init=False, repr=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("staged bootstrap records are venue-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("staged bootstrap records cannot be subclassed")


def _new_staged_bootstrap_bound_target_record(
    *,
    active_record: _BootstrapBoundTargetRecord,
    target_execution: ExecutionSnapshot,
    binding: VenueExecutionBinding,
    catch_up: CatchUpExecutionRegistry,
) -> _StagedBootstrapBoundTargetRecord:
    if (
        not _bootstrap_bound_target_record_is_authentic(active_record)
        or type(target_execution) is not ExecutionSnapshot
        or type(binding) is not VenueExecutionBinding
        or type(catch_up) is not CatchUpExecutionRegistry
        or target_execution.position.scope != active_record.position_scope
        or binding != active_record.binding
        or catch_up.target_scope != active_record.position_scope
        or target_execution.position.raw_quantity != 0
        or target_execution.position.root_count != 0
        or target_execution.integrity is not PositionIntegrity.CONSISTENT
        or target_execution.account_reconciliation_required
    ):
        raise TypeError("staged bootstrap record requires one exact neutral refresh")
    map_seal = _bootstrap_bound_target_record_map_seal(
        application_generation_id=active_record.application_generation_id,
        position_scope=active_record.position_scope,
        source_kind=active_record.source_kind,
        source_execution_commitment=active_record.source_execution_commitment,
        target_genesis_execution_commitment=(
            active_record.target_genesis_execution_commitment
        ),
        target_execution_commitment=target_execution.commitment,
        binding=binding,
        account_registry_count=target_execution.seen_facts.count,
        account_registry_commitment=target_execution.seen_facts.commitment,
        reconciliation_transition_count=(
            target_execution.reconciliation_transition_count
        ),
        reconciliation_transition_head=target_execution.reconciliation_transition_head,
        bootstrap_input_id=active_record.bootstrap_input_id,
        bootstrap_input_commitment=active_record.bootstrap_input_commitment,
        bootstrap_target_execution_commitment=(
            active_record.bootstrap_target_execution_commitment
        ),
        bootstrap_account_registry_count=active_record.bootstrap_account_registry_count,
        bootstrap_account_registry_commitment=(
            active_record.bootstrap_account_registry_commitment
        ),
        bootstrap_reconciliation_transition_count=(
            active_record.bootstrap_reconciliation_transition_count
        ),
        bootstrap_reconciliation_transition_head=(
            active_record.bootstrap_reconciliation_transition_head
        ),
        checkpoint_input_id=catch_up.input_id,
        checkpoint_command_commitment=_protection_command_commitment(catch_up),
    )
    result = object.__new__(_StagedBootstrapBoundTargetRecord)
    object.__setattr__(result, "active_record", active_record)
    object.__setattr__(
        result,
        "target_execution_commitment",
        target_execution.commitment,
    )
    object.__setattr__(
        result,
        "account_registry_count",
        target_execution.seen_facts.count,
    )
    object.__setattr__(
        result,
        "account_registry_commitment",
        target_execution.seen_facts.commitment,
    )
    object.__setattr__(
        result,
        "reconciliation_transition_count",
        target_execution.reconciliation_transition_count,
    )
    object.__setattr__(
        result,
        "reconciliation_transition_head",
        target_execution.reconciliation_transition_head,
    )
    object.__setattr__(result, "checkpoint_input_id", catch_up.input_id)
    object.__setattr__(
        result,
        "checkpoint_command_commitment",
        _protection_command_commitment(catch_up),
    )
    object.__setattr__(result, "_map_seal", map_seal)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/bootstrap-bound-target-record/stage/v1",
            active_record.commitment,
            map_seal,
        ),
    )
    return result


def _staged_bootstrap_bound_target_record_is_authentic(value: object) -> bool:
    if type(value) is not _StagedBootstrapBoundTargetRecord:
        return False
    try:
        active = value.active_record
        if (
            not _bootstrap_bound_target_record_is_authentic(active)
            or type(value.account_registry_count) is not int
            or value.account_registry_count < 0
            or type(value.checkpoint_input_id) is not VenueInputId
        ):
            return False
        for digest in (
            value.target_execution_commitment,
            value.account_registry_commitment,
            value.reconciliation_transition_head,
            value.checkpoint_command_commitment,
            value._map_seal,
            value._seal,
        ):
            _require_digest("staged bootstrap record digest", digest)
        expected_map_seal = _bootstrap_bound_target_record_map_seal(
            application_generation_id=active.application_generation_id,
            position_scope=active.position_scope,
            source_kind=active.source_kind,
            source_execution_commitment=active.source_execution_commitment,
            target_genesis_execution_commitment=(
                active.target_genesis_execution_commitment
            ),
            target_execution_commitment=value.target_execution_commitment,
            binding=active.binding,
            account_registry_count=value.account_registry_count,
            account_registry_commitment=value.account_registry_commitment,
            reconciliation_transition_count=value.reconciliation_transition_count,
            reconciliation_transition_head=value.reconciliation_transition_head,
            bootstrap_input_id=active.bootstrap_input_id,
            bootstrap_input_commitment=active.bootstrap_input_commitment,
            bootstrap_target_execution_commitment=(
                active.bootstrap_target_execution_commitment
            ),
            bootstrap_account_registry_count=active.bootstrap_account_registry_count,
            bootstrap_account_registry_commitment=(
                active.bootstrap_account_registry_commitment
            ),
            bootstrap_reconciliation_transition_count=(
                active.bootstrap_reconciliation_transition_count
            ),
            bootstrap_reconciliation_transition_head=(
                active.bootstrap_reconciliation_transition_head
            ),
            checkpoint_input_id=value.checkpoint_input_id,
            checkpoint_command_commitment=value.checkpoint_command_commitment,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        value._map_seal == expected_map_seal
        and value._seal
        == _commit_parts(
            b"execution-core/bootstrap-bound-target-record/stage/v1",
            active.commitment,
            expected_map_seal,
        )
    )


@dataclass(frozen=True, slots=True, init=False)
class _ConsumedBootstrapBoundTargetRecord:
    """Permanent proof that one active R8 bootstrap record became one effect.

    ``_PersistentKeyMap`` intentionally has no deletion operation.  Replacing
    the active entry with this sealed non-serving record preserves the original
    zero-economic provenance while making the active record unavailable to any
    later bootstrap or ordinary request route.
    """

    active_record: _BootstrapBoundTargetRecord = field(init=False, repr=False)
    effect_id: EffectId = field(init=False)
    request_occurrence_id: RequestOccurrenceId = field(init=False)
    request_input_id: VenueInputId = field(init=False)
    effect_scope_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("consumed bootstrap records are venue-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("consumed bootstrap records cannot be subclassed")


_BootstrapBoundTargetValue = (
    _BootstrapBoundTargetRecord
    | _StagedBootstrapBoundTargetRecord
    | _ConsumedBootstrapBoundTargetRecord
    | bytes
)


def _consumed_bootstrap_bound_target_record_commitment(
    *,
    active_record: _BootstrapBoundTargetRecord,
    effect_id: EffectId,
    request_occurrence_id: RequestOccurrenceId,
    request_input_id: VenueInputId,
    effect_scope_commitment: bytes,
) -> bytes:
    if not _bootstrap_bound_target_record_is_authentic(active_record):
        raise TypeError("consumed bootstrap record requires an active record")
    _require("effect_id", effect_id, EffectId)
    _require("request_occurrence_id", request_occurrence_id, RequestOccurrenceId)
    _require("request_input_id", request_input_id, VenueInputId)
    _require_digest("effect_scope_commitment", effect_scope_commitment)
    return _commit_parts(
        b"execution-core/bootstrap-bound-target-record/consumed/v1",
        active_record.commitment,
        _canonical_value_commitment(effect_id),
        _canonical_value_commitment(request_occurrence_id),
        _canonical_value_commitment(request_input_id),
        effect_scope_commitment,
    )


def _new_consumed_bootstrap_bound_target_record(
    *,
    active_record: _BootstrapBoundTargetRecord,
    effect: BrokerEffect,
    request_input_id: VenueInputId,
) -> _ConsumedBootstrapBoundTargetRecord:
    if (
        not _bootstrap_bound_target_record_is_authentic(active_record)
        or type(effect) is not BrokerEffect
        or type(request_input_id) is not VenueInputId
        or effect.scope.position_scope != active_record.position_scope
        or effect.scope.kind is not EffectKind.SUBMIT
        or effect.scope.side is not ExecutionSide.BUY
    ):
        raise TypeError("bootstrap consumption requires one exact BUY effect")
    scope_commitment = _canonical_value_commitment(effect.scope)
    commitment = _consumed_bootstrap_bound_target_record_commitment(
        active_record=active_record,
        effect_id=effect.effect_id,
        request_occurrence_id=effect.scope.request_occurrence_id,
        request_input_id=request_input_id,
        effect_scope_commitment=scope_commitment,
    )
    result = object.__new__(_ConsumedBootstrapBoundTargetRecord)
    object.__setattr__(result, "active_record", active_record)
    object.__setattr__(result, "effect_id", effect.effect_id)
    object.__setattr__(
        result,
        "request_occurrence_id",
        effect.scope.request_occurrence_id,
    )
    object.__setattr__(result, "request_input_id", request_input_id)
    object.__setattr__(result, "effect_scope_commitment", scope_commitment)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/bootstrap-bound-target-record/consumed-seal/v1",
            commitment,
        ),
    )
    return result


def _consumed_bootstrap_bound_target_record_is_authentic(value: object) -> bool:
    if type(value) is not _ConsumedBootstrapBoundTargetRecord:
        return False
    try:
        commitment = _consumed_bootstrap_bound_target_record_commitment(
            active_record=value.active_record,
            effect_id=value.effect_id,
            request_occurrence_id=value.request_occurrence_id,
            request_input_id=value.request_input_id,
            effect_scope_commitment=value.effect_scope_commitment,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return bool(
        value.commitment == commitment
        and value._seal
        == _commit_parts(
            b"execution-core/bootstrap-bound-target-record/consumed-seal/v1",
            commitment,
        )
    )


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
    active_leg_keys: tuple[VenueLegKey, ...] = ()
    known_cancellable_leg_keys: tuple[VenueLegKey, ...] = ()
    known_cancel_pending_leg_keys: tuple[VenueLegKey, ...] = ()

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-effect-leg-summary/v2",
            _encode_text(str(self.owner_count)),
            _encode_text(str(self.active_count)),
            _encode_text(str(self.finalization_ready_count)),
            _canonical_value_commitment(self.active_leg_keys),
            _canonical_value_commitment(self.known_cancellable_leg_keys),
            _canonical_value_commitment(self.known_cancel_pending_leg_keys),
        )


@dataclass(frozen=True, slots=True)
class _CancelTargetReservation:
    effect_id: EffectId | None

    def __post_init__(self) -> None:
        if self.effect_id is not None and type(self.effect_id) is not EffectId:
            raise TypeError("cancel target reservation effect_id must be EffectId")

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-cancel-target-reservation/v1",
            _canonical_value_commitment(self.effect_id),
        )


@dataclass(frozen=True, slots=True)
class _EffectAuthorityContribution:
    effect_id: EffectId
    position_scope: PositionScope
    unclaimed_requested: bool
    target_exemptible: bool
    blocking_effect_count: int
    blocking_buy_effect_count: int
    stand_downable_buy_count: int
    stand_downable_buy_effect_ids: tuple[EffectId, ...]
    known_cancellable_buy_leg_keys: tuple[VenueLegKey, ...]
    known_cancel_pending_buy_leg_keys: tuple[VenueLegKey, ...]
    waiting_buy_parent_count: int
    unknown_buy_effect_count: int

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-effect-authority-contribution/v1",
            _canonical_value_commitment(self),
        )


@dataclass(frozen=True, slots=True)
class _SymbolAuthoritySummary:
    effect_count: int = 0
    blocking_effect_count: int = 0
    blocking_buy_effect_count: int = 0
    stand_downable_buy_count: int = 0
    stand_downable_buy_effect_ids: tuple[EffectId, ...] = ()
    known_cancellable_buy_leg_keys: tuple[VenueLegKey, ...] = ()
    known_cancel_pending_buy_leg_keys: tuple[VenueLegKey, ...] = ()
    waiting_buy_parent_count: int = 0
    unknown_buy_effect_count: int = 0

    @property
    def commitment(self) -> bytes:
        return _commit_parts(
            b"execution-core/venue-symbol-authority-summary/v1",
            _canonical_value_commitment(self),
        )


@dataclass(frozen=True, slots=True)
class _VenueAuthorityView:
    execution_binding_matches: bool
    account_reconciliation_clear: bool
    bootstrap_bound_target_active: bool
    blocking_effect_count: int
    blocking_buy_effect_count: int
    target_exemptible_count: int
    stand_downable_buy_count: int
    known_cancellable_buy_leg_count: int
    known_cancel_pending_buy_leg_count: int
    waiting_buy_parent_count: int
    unknown_buy_effect_count: int


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
    _acquisition_correlation_by_root: _PersistentKeyMap[
        _AcquisitionCorrelationEntry
    ] = field(default_factory=_PersistentKeyMap.empty)
    _leg_current_by_leg: _PersistentKeyMap[_LegCurrent] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _leg_summary_by_effect: _PersistentKeyMap[_EffectLegSummary] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _cancel_target_reservation_by_leg: _PersistentKeyMap[_CancelTargetReservation] = (
        field(default_factory=_PersistentKeyMap.empty)
    )
    _authority_contribution_by_effect: _PersistentKeyMap[
        _EffectAuthorityContribution
    ] = field(default_factory=_PersistentKeyMap.empty)
    _authority_summary_by_scope: _PersistentKeyMap[_SymbolAuthoritySummary] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _account_unclaimed_requested_effect_ids: tuple[EffectId, ...] = ()
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
    _registry_transition_ledger: _PersistentSequence[_RegistryTransitionProof] = field(
        default_factory=_PersistentSequence.empty
    )
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
    _execution_snapshot_by_scope: _PersistentKeyMap[ExecutionSnapshot] = field(
        default_factory=_PersistentKeyMap.empty
    )
    # A bootstrap checkpoint briefly holds one static map-seal before its
    # proof-bound record replaces that staging value at the identical key.
    # A fully published book always contains only _BootstrapBoundTargetRecord.
    _bootstrap_bound_target_by_scope: _PersistentKeyMap[_BootstrapBoundTargetValue] = (
        field(default_factory=_PersistentKeyMap.empty)
    )
    _protection_cursor_by_scope: _PersistentKeyMap[_ProtectionCursor] = field(
        default_factory=_PersistentKeyMap.empty
    )
    _protection_transition_ledger: _PersistentSequence[_ProtectionTransitionProof] = (
        field(default_factory=_PersistentSequence.empty)
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError(
            "VenueRecoveryBook is opaque; use empty() and the verified reducer"
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("VenueRecoveryBook is opaque and cannot be subclassed")

    @property
    def _protection_commitment(self) -> bytes:
        """Return the bounded envelope commitment used by protection projection."""

        return _protection_book_commitment(self)

    def _authority_epoch(self, position_scope: PositionScope) -> int:
        retained = self._authority_epoch_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        return 0 if retained is None else retained

    def _effective_effect(self, current: _EffectCurrent) -> BrokerEffect:
        effect = current.effect
        if effect.state is BrokerEffectState.OPERATOR_RECONCILED and (
            current.operator_epoch != self._authority_epoch(effect.scope.position_scope)
            or current.account_epoch != self._account_authority_epoch
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

        if type(self.scope) is not VenueScope:
            raise TypeError("scope must be the exact VenueScope type")
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
        self._validate_cancel_target_reservations()
        self._validate_authority_indexes()
        self._validated_execution_snapshots(effects)

    def _validate_cancel_target_reservations(self) -> None:
        expected = _rebuild_cancel_target_reservations(self)
        if self._cancel_target_reservation_by_leg.commitment != expected.commitment:
            raise ValueError(
                "cancel target reservation index contradicts canonical current state"
            )

    def _validate_authority_indexes(self) -> None:
        (
            expected_contributions,
            expected_summaries,
            expected_unclaimed,
        ) = _rebuild_authority_indexes(self)
        if (
            self._authority_contribution_by_effect.commitment
            != expected_contributions.commitment
            or self._authority_summary_by_scope.commitment
            != expected_summaries.commitment
            or self._account_unclaimed_requested_effect_ids != expected_unclaimed
        ):
            raise ValueError(
                "venue authority indexes contradict canonical current state"
            )

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
                _AttributedRegistryAdvanceOutcome,
            }
            for entry in self.execution_reconciliations
        ):
            raise TypeError(
                "execution reconciliation entries must be exact outcome types"
            )
        self._require_entries("human coverage", self.human_coverages, HumanCoverage)
        self._require_entries("broker coverage", self.broker_coverages, _BrokerCoverage)
        if any(
            type(entry)
            not in {
                ReconciliationRecord,
                RevisionReconciliationRecord,
            }
            for entry in self.reconciliations
        ):
            raise TypeError(
                "reconciliation entries must be exact reconciliation record types"
            )

    @staticmethod
    def _require_entries(
        name: str, entries: tuple[object, ...], expected: type[object]
    ) -> None:
        if any(type(entry) is not expected for entry in entries):
            raise TypeError(f"{name} entries must be exact {expected.__name__} values")

    def _validated_effects(self) -> dict[EffectId, BrokerEffect]:
        for entry in self.effects:
            entry = _require_effect_shape(entry)
            self._validate_effect_scope(entry.scope)
        self._require_unique("effect", (entry.effect_id for entry in self.effects))
        self._require_unique(
            "request occurrence",
            (entry.scope.request_occurrence_id for entry in self.effects),
        )
        self._require_unique(
            "client identity",
            (
                entry.scope.client_identity
                for entry in self.effects
                if entry.scope.client_identity is not None
            ),
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
                if (
                    effect.acceptance_proof.kind
                    is not AcceptanceProofKind.NEVER_DISPATCHED
                    and not _external_acceptance_closure_is_certified(
                        self,
                        effect,
                        effect.acceptance_proof,
                    )
                ):
                    raise ValueError(
                        "external acceptance closure requires M2 adapter-certified "
                        "coverage"
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
            ("effect scope.symbol_id", scope.symbol_id, SymbolId),
            ("effect scope.side", scope.side, ExecutionSide),
            ("effect scope.quantity", scope.quantity, Quantity),
        ):
            _require(name, value, expected)
        _validate_effect_identity_shape(
            scope.kind,
            scope.client_order_id,
            scope.target_leg_key,
        )
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

    def _validated_bootstrap_bound_target_records(
        self,
        effects: dict[EffectId, BrokerEffect],
    ) -> tuple[
        dict[PositionScope, _BootstrapBoundTargetRecord],
        dict[PositionScope, _ConsumedBootstrapBoundTargetRecord],
    ]:
        """Validate active and consumed R8 records through direct indexes only."""

        if type(self._bootstrap_bound_target_by_scope) is not type(
            _PersistentKeyMap.empty()
        ):
            raise TypeError("bootstrap target index must be a persistent key map")
        active_records: dict[PositionScope, _BootstrapBoundTargetRecord] = {}
        consumed_records: dict[PositionScope, _ConsumedBootstrapBoundTargetRecord] = {}
        for binding in self.execution_bindings:
            scope = binding.position_scope
            record = self._bootstrap_bound_target_by_scope.get(
                _position_scope_index_key(scope)
            )
            if record is None:
                continue
            snapshot = self._execution_snapshot_by_scope.get(
                _position_scope_index_key(scope)
            )
            if _bootstrap_bound_target_record_is_authentic(record):
                if (
                    record.application_generation_id != self.scope.generation
                    or record.position_scope != scope
                    or record.binding != binding
                    or type(snapshot) is not ExecutionSnapshot
                    or not self._bootstrap_bound_target_pair_matches(snapshot, scope)
                    or scope in active_records
                    or scope in consumed_records
                ):
                    raise ValueError("bootstrap target record contradicts its binding")
                active_records[scope] = record
                continue
            if not _consumed_bootstrap_bound_target_record_is_authentic(record):
                raise ValueError("bootstrap target index contains an unknown record")
            active = record.active_record
            effect = effects.get(record.effect_id)
            input_record = self._input_record(record.request_input_id)
            requested = (
                input_record.item if type(input_record) is VenueInputRecord else None
            )
            if (
                active.application_generation_id != self.scope.generation
                or active.position_scope != scope
                or active.binding != binding
                or not self._bootstrap_bound_target_anchor_matches(active, scope)
                or type(snapshot) is not ExecutionSnapshot
                or effect is None
                or effect.scope.position_scope != scope
                or effect.scope.kind is not EffectKind.SUBMIT
                or effect.scope.side is not ExecutionSide.BUY
                or effect.effect_id != record.effect_id
                or effect.scope.request_occurrence_id != record.request_occurrence_id
                or _canonical_value_commitment(effect.scope)
                != record.effect_scope_commitment
                or type(requested) is not RequestedEffect
                or requested.input_id != record.request_input_id
                or requested.effect_id != record.effect_id
                or requested.request_occurrence_id != record.request_occurrence_id
                or requested.kind is not EffectKind.SUBMIT
                or requested.side is not ExecutionSide.BUY
                or requested.symbol_id != scope.symbol_id
                or scope in active_records
                or scope in consumed_records
            ):
                raise ValueError("consumed bootstrap record contradicts its effect")
            consumed_records[scope] = record
        if self._bootstrap_bound_target_by_scope.size != len(active_records) + len(
            consumed_records
        ):
            raise ValueError(
                "bootstrap target index contains an unbound or extra record"
            )
        return active_records, consumed_records

    def _validated_execution_bindings(
        self, effects: dict[EffectId, BrokerEffect]
    ) -> None:
        for binding in self.execution_bindings:
            VenueExecutionBinding.__post_init__(binding)
        self._require_unique(
            "execution binding",
            (binding.position_scope for binding in self.execution_bindings),
        )
        bound_scopes = {binding.position_scope for binding in self.execution_bindings}
        effect_scopes = {effect.scope.position_scope for effect in effects.values()}
        records, consumed_records = self._validated_bootstrap_bound_target_records(
            effects
        )
        bootstrap_scopes = set(records)
        if effect_scopes & bootstrap_scopes:
            raise ValueError("an active bootstrap target cannot share an effect scope")
        if not set(consumed_records) <= effect_scopes:
            raise ValueError("a consumed bootstrap target requires its exact effect")
        if bound_scopes != effect_scopes | bootstrap_scopes:
            raise ValueError(
                "every effect symbol requires exactly one binding; every binding must "
                "belong to exactly one effect or bootstrap target"
            )
        if bool(effects or records) != (self.execution_registry_commitment is not None):
            raise ValueError(
                "effect or bootstrap checkpoints require one account registry commitment"
            )

    def _validated_protection_transition_history(
        self,
    ) -> dict[PositionScope, _ProtectionTransitionProof]:
        """Authenticate each retained per-scope cursor from ordered proofs."""

        if type(self._protection_transition_ledger) is not type(
            _PersistentSequence.empty()
        ):
            raise TypeError("protection transition history must be persistent")
        if type(self._protection_cursor_by_scope) is not type(
            _PersistentKeyMap.empty()
        ):
            raise TypeError("protection cursor index must be a persistent key map")

        rebuilt: _PersistentSequence[_ProtectionTransitionProof] = (
            _PersistentSequence.empty()
        )
        head_by_scope: dict[PositionScope, _ProtectionCursor] = {}
        terminal_by_scope: dict[PositionScope, _ProtectionTransitionProof] = {}
        for index in range(self._protection_transition_ledger.length):
            proof: _ProtectionTransitionProof = self._protection_transition_ledger.get(
                index
            )
            if type(proof) is not _ProtectionTransitionProof:
                raise TypeError("retained protection transition proof must be exact")
            if proof.cursor == proof.predecessor_cursor:
                raise ValueError("protection transition history retained a non-advance")
            if not proof.lineage_is_authentic:
                raise ValueError("protection transition history is not authentic")
            expected = head_by_scope.get(
                proof.position_scope,
                _protection_genesis_cursor(),
            )
            if proof.predecessor_cursor != expected:
                raise ValueError("protection transition history is not contiguous")
            head_by_scope[proof.position_scope] = proof.cursor
            terminal_by_scope[proof.position_scope] = proof
            rebuilt = rebuilt.append(proof, proof.commitment)

        if rebuilt.commitment != self._protection_transition_ledger.commitment:
            raise ValueError(
                "protection transition history commitment is not authentic"
            )

        bound_scopes = {binding.position_scope for binding in self.execution_bindings}
        if set(head_by_scope) != bound_scopes:
            raise ValueError(
                "every execution binding requires exact protection checkpoint continuity"
            )
        if self._protection_cursor_by_scope.size != len(bound_scopes):
            raise ValueError("every execution binding requires one protection cursor")
        for binding in self.execution_bindings:
            scope = binding.position_scope
            scope_key = _position_scope_index_key(scope)
            cursor = self._protection_cursor_by_scope.get(scope_key)
            terminal = terminal_by_scope[scope]
            summary = (
                self._authority_summary_by_scope.get(scope_key)
                or _SymbolAuthoritySummary()
            )
            if type(cursor) is not _ProtectionCursor or cursor != terminal.cursor:
                raise ValueError(
                    "protection cursor lacks its exact terminal transition proof"
                )
            unresolved_for_scope = (
                self._unresolved_execution_reconciliation_count_by_scope.get(scope_key)
                or 0
            )
            if terminal.summary != summary or (
                terminal.binding != binding and unresolved_for_scope == 0
            ):
                raise ValueError(
                    "terminal protection provenance contradicts current venue authority "
                    "and registry transition"
                )
        return terminal_by_scope

    def _validated_execution_snapshots(
        self,
        effects: dict[EffectId, BrokerEffect] | None = None,
    ) -> None:
        """Validate private scope material against retained transition history."""

        terminal_by_scope = self._validated_protection_transition_history()

        if type(self._execution_snapshot_by_scope) is not type(
            _PersistentKeyMap.empty()
        ):
            raise TypeError("execution snapshot index must be a persistent key map")
        bindings = self.execution_bindings
        if self._execution_snapshot_by_scope.size != len(bindings):
            raise ValueError(
                "every execution binding requires one retained exact snapshot"
            )
        rebuilt: _PersistentKeyMap[ExecutionSnapshot] = _PersistentKeyMap.empty()
        for binding in bindings:
            scope_key = _position_scope_index_key(binding.position_scope)
            snapshot = self._execution_snapshot_by_scope.get(scope_key)
            if type(snapshot) is not ExecutionSnapshot:
                raise TypeError("retained execution snapshot must be exact")
            cursor = self._protection_cursor_by_scope.get(scope_key)
            if (
                type(cursor) is not _ProtectionCursor
                or cursor.execution_commitment != snapshot.commitment
                or cursor.execution_checkpoint
                != VenueExecutionCheckpoint.from_execution(snapshot)
            ):
                raise ValueError(
                    "retained execution snapshot lacks its exact transition-cursor provenance"
                )
            terminal = terminal_by_scope[binding.position_scope]
            if (
                terminal.execution_commitment != snapshot.commitment
                or terminal.execution_checkpoint
                != VenueExecutionCheckpoint.from_execution(snapshot)
            ):
                raise ValueError(
                    "retained execution snapshot lacks its terminal transition proof"
                )
            _require_execution_components(
                snapshot.position,
                snapshot.integrity,
                snapshot.root_heads,
                snapshot.seen_facts,
            )
            unresolved_for_scope = (
                self._unresolved_execution_reconciliation_count_by_scope.get(scope_key)
                or 0
            )
            if (
                not _binding_matches_execution(binding, snapshot)
                and unresolved_for_scope == 0
            ):
                raise ValueError(
                    "retained execution snapshot contradicts its symbol binding"
                )
            if self.execution_registry_count is None:
                raise ValueError(
                    "retained execution snapshot requires account registry"
                )
            if snapshot.seen_facts.count > self.execution_registry_count:
                raise ValueError("retained execution snapshot exceeds account registry")
            if (
                snapshot.seen_facts.count == self.execution_registry_count
                and snapshot.seen_facts.commitment != self.execution_registry_commitment
            ):
                raise ValueError(
                    "current retained snapshot contradicts account registry"
                )
            if not self._execution_reconciliation_cursor_is_prefix(snapshot):
                raise ValueError(
                    "retained snapshot reconciliation cursor is not a book prefix"
                )
            if (
                snapshot.reconciliation_transition_count
                == self._registry_transition_ledger.length
                and not self._execution_reconciliation_cursor_matches(snapshot)
            ):
                raise ValueError(
                    "current retained snapshot contradicts reconciliation state"
                )
            rebuilt = _upsert_execution_snapshot_value(rebuilt, snapshot)
        if rebuilt.commitment != self._execution_snapshot_by_scope.commitment:
            raise ValueError("execution snapshot index commitment is not authentic")

        # The ordinary snapshot/cursor checks above establish every binding.
        # Bootstrap is the one pre-effect exception, so audit validation also
        # proves its sealed input and neutral checkpoint against those exact
        # bounded records.  This scan is deliberately confined to the explicit
        # audit validator; serving paths use the direct predicate below.
        if effects is None:
            effects = self._validated_effects()
        active_records, consumed_records = (
            self._validated_bootstrap_bound_target_records(effects)
        )

        def retained_proof_index(proof: _ProtectionTransitionProof) -> int | None:
            found: int | None = None
            for index in range(self._protection_transition_ledger.length):
                retained = self._protection_transition_ledger.get(index)
                if retained == proof:
                    if found is not None:
                        return None
                    found = index
            return found

        def is_retained_catch_up(
            proof: _ProtectionTransitionProof,
            position_scope: PositionScope,
        ) -> bool:
            for index in range(self._input_ledger.length):
                input_record = self._input_ledger.get(index)
                if (
                    type(input_record) is VenueInputRecord
                    and type(input_record.item) is CatchUpExecutionRegistry
                    and input_record.item.target_scope == position_scope
                    and _protection_command_commitment(input_record.item)
                    == proof.command_commitment
                ):
                    return True
            return False

        for position_scope, record in active_records.items():
            scope_key = _position_scope_index_key(position_scope)
            snapshot = self._execution_snapshot_by_scope.get(scope_key)
            anchor_index = retained_proof_index(
                record._bootstrap_neutral_checkpoint_proof
            )
            current_index = retained_proof_index(record._neutral_checkpoint_proof)
            if (
                type(snapshot) is not ExecutionSnapshot
                or not self._bootstrap_bound_target_anchor_matches(
                    record,
                    position_scope,
                )
                or not self._bootstrap_bound_target_pair_matches(
                    snapshot,
                    position_scope,
                )
                or anchor_index is None
                or current_index is None
                or anchor_index > current_index
                or terminal_by_scope.get(position_scope)
                != record._neutral_checkpoint_proof
            ):
                raise ValueError(
                    "bootstrap target record lacks its exact neutral checkpoint proof"
                )
            for index in range(anchor_index + 1, current_index + 1):
                retained = self._protection_transition_ledger.get(index)
                # The ledger is account-global, while a bootstrap record owns
                # exactly one target scope.  Sibling proofs may legitimately
                # interleave before the target's ordinary CatchUp checkpoint;
                # validate only the target's contiguous cursor chain here.
                if (
                    type(retained) is _ProtectionTransitionProof
                    and retained.position_scope != position_scope
                ):
                    continue
                if (
                    type(retained) is not _ProtectionTransitionProof
                    or retained.position_scope != position_scope
                    or retained.disposition is not VenueRecoveryDisposition.APPLIED
                    or retained.quantity_delta != 0
                    or not is_retained_catch_up(retained, position_scope)
                ):
                    raise ValueError(
                        "bootstrap checkpoint retained a non-neutral refresh proof"
                    )

        for position_scope, consumed in consumed_records.items():
            active = consumed.active_record
            request_input = self._input_record(consumed.request_input_id)
            requested = (
                request_input.item if type(request_input) is VenueInputRecord else None
            )
            consumption_proof: _ProtectionTransitionProof | None = None
            for index in range(self._protection_transition_ledger.length):
                retained = self._protection_transition_ledger.get(index)
                if (
                    type(retained) is _ProtectionTransitionProof
                    and retained.position_scope == position_scope
                    and type(requested) is RequestedEffect
                    and retained.command_commitment
                    == _protection_command_commitment(requested)
                ):
                    if consumption_proof is not None:
                        consumption_proof = None
                        break
                    consumption_proof = retained
            if (
                not self._bootstrap_bound_target_anchor_matches(active, position_scope)
                or retained_proof_index(active._bootstrap_neutral_checkpoint_proof)
                is None
                or retained_proof_index(active._neutral_checkpoint_proof) is None
                or type(requested) is not RequestedEffect
                or requested.input_id != consumed.request_input_id
                or requested.effect_id != consumed.effect_id
                or requested.request_occurrence_id != consumed.request_occurrence_id
                or requested.kind is not EffectKind.SUBMIT
                or requested.side is not ExecutionSide.BUY
                or consumption_proof is None
                or consumption_proof.disposition is not VenueRecoveryDisposition.APPLIED
                or consumption_proof.quantity_delta != 0
                or consumption_proof.predecessor_cursor
                != active._neutral_checkpoint_proof.cursor
                or consumption_proof.predecessor_execution_commitment
                != active.target_execution_commitment
                or consumption_proof.execution_commitment
                != active.target_execution_commitment
                or consumption_proof.predecessor_execution_checkpoint
                != active._neutral_checkpoint_proof.execution_checkpoint
                or consumption_proof.execution_checkpoint
                != active._neutral_checkpoint_proof.execution_checkpoint
                or consumption_proof.predecessor_binding != active.binding
                or consumption_proof.binding != active.binding
            ):
                raise ValueError(
                    "consumed bootstrap record lacks its exact consumption provenance"
                )

    def _validated_claims(
        self, effects: dict[EffectId, BrokerEffect]
    ) -> dict[EffectId, DispatchClaim]:
        for entry in self.claims:
            entry = _require_claim_shape(entry)
            self._validate_effect_scope(entry.effect_scope)
            _require(
                "claim.claim_occurrence_id",
                entry.claim_occurrence_id,
                ClaimOccurrenceId,
            )
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
        for entry in self.owners:
            entry = _require_owner_shape(entry)
            self._validate_effect_scope(entry.effect_scope)
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
            if owner.effect_scope.kind is EffectKind.CANCEL:
                raise ValueError("cancel effects cannot own venue legs")
            owners[owner.leg_key] = owner
        return owners

    def _validated_active_attempts(
        self, owners: dict[VenueLegKey, VenueIdentityOwner]
    ) -> dict[VenueLegKey, VenueAttempt]:
        for entry in self.active_attempts:
            _require_attempt_shape(entry)
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
        for entry in (*self.closure_heads, *self.closure_history):
            _require_closure_shape(entry)
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
        closure = _require_closure_shape(closure)
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

        input_types = _VENUE_INPUTS + (
            IngestHumanAttestedFill,
            RecordBrokerFillEvidence,
            RecordBrokerRevisionEvidence,
            ReleaseVenueLeg,
        )
        exact_input_types = set(input_types)
        for record in self.input_records:
            _require_input_record_shape(record)
            if type(record.item) not in exact_input_types:
                raise TypeError(
                    "input record item must be an exact venue-recovery input"
                )
            if record.semantic_alias_of is not None:
                _require(
                    "input record.semantic_alias_of",
                    record.semantic_alias_of,
                    VenueInputId,
                )
        self._require_unique("input", (entry.input_id for entry in self.input_records))
        prior_input_records: dict[VenueInputId, VenueInputRecord] = {}
        for record in self.input_records:
            if not isinstance(record.item, input_types):
                raise AssertionError("exact input type was not recognized")
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
                ):
                    raise ValueError(
                        "semantic input alias requires an earlier direct source"
                    )
                if not isinstance(semantic_source.item, input_types):
                    raise TypeError("semantic source must retain an exact input type")
                if (
                    type(semantic_source.item) is not type(record.item)
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
        ordered_effect_scopes: dict[EffectId, VenueEffectScope] = {}
        ordered_claim_occurrences: dict[EffectId, ClaimOccurrenceId] = {}
        ordered_acceptance_states: dict[EffectId, AcceptanceSetState] = {}
        ordered_leg_effects: dict[VenueLegKey, EffectId] = {}
        ordered_leg_states: dict[VenueLegKey, VenueAttemptState] = {}
        ordered_leg_pending: dict[VenueLegKey, PendingVenueOperation | None] = {}
        ordered_closed_legs: set[VenueLegKey] = set()
        ordered_cancel_reservations: dict[VenueLegKey, EffectId] = {}

        def ordered_target_is_exact_active(
            scope: VenueEffectScope,
            *,
            expected_cancel_effect_id: EffectId | None = None,
        ) -> bool:
            target_leg_key = scope.target_leg_key
            if target_leg_key is None or not _same_leg_scope(
                self.scope, target_leg_key
            ):
                return False
            owner_effect_id = ordered_leg_effects.get(target_leg_key)
            owner_scope = (
                None
                if owner_effect_id is None
                else ordered_effect_scopes.get(owner_effect_id)
            )
            reservation = ordered_cancel_reservations.get(target_leg_key)
            if scope.kind is EffectKind.CANCEL:
                reservation_matches = (
                    reservation is None
                    if expected_cancel_effect_id is None
                    else reservation == expected_cancel_effect_id
                )
            else:
                reservation_matches = reservation is None
            return bool(
                owner_effect_id is not None
                and owner_scope is not None
                and ordered_effect_states.get(owner_effect_id)
                is BrokerEffectState.ACKNOWLEDGED
                and target_leg_key not in ordered_closed_legs
                and ordered_leg_states.get(target_leg_key)
                in {
                    VenueAttemptState.WORKING,
                    VenueAttemptState.PARTIALLY_FILLED,
                }
                and ordered_leg_pending.get(target_leg_key) is None
                and reservation_matches
                and owner_scope.symbol_id == scope.symbol_id
                and owner_scope.side is scope.side
                and owner_scope.quantity == scope.quantity
            )

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
                requested_scope = _effect_scope(self, item)
                ordered_effect_scopes[item.effect_id] = requested_scope
                ordered_acceptance_states[item.effect_id] = AcceptanceSetState.OPEN
                if requested_scope.kind in {EffectKind.CANCEL, EffectKind.REPLACE}:
                    if not ordered_target_is_exact_active(requested_scope):
                        raise ValueError(
                            "target-bound effect requires one exact prior active owner "
                            "without another cancel reservation"
                        )
                    if requested_scope.kind is EffectKind.CANCEL:
                        target_leg_key = requested_scope.target_leg_key
                        assert target_leg_key is not None
                        ordered_cancel_reservations[target_leg_key] = item.effect_id
                ordered_effect_states[item.effect_id] = BrokerEffectState.REQUESTED
            elif isinstance(item, CancelBeforeDispatch):
                ordered_effect_states[item.effect_id] = (
                    BrokerEffectState.CANCELED_BEFORE_DISPATCH
                )
                scope = ordered_effect_scopes.get(item.effect_id)
                if scope is not None and scope.kind is EffectKind.CANCEL:
                    target_leg_key = scope.target_leg_key
                    if (
                        target_leg_key is not None
                        and ordered_cancel_reservations.get(target_leg_key)
                        == item.effect_id
                    ):
                        del ordered_cancel_reservations[target_leg_key]
            elif isinstance(item, RecordDispatchClaim):
                scope = ordered_effect_scopes.get(item.effect_id)
                if (
                    scope is not None
                    and scope.kind in {EffectKind.CANCEL, EffectKind.REPLACE}
                    and not ordered_target_is_exact_active(
                        scope,
                        expected_cancel_effect_id=(
                            item.effect_id if scope.kind is EffectKind.CANCEL else None
                        ),
                    )
                ):
                    raise ValueError(
                        "target-bound claim requires its exact active owner and "
                        "reservation"
                    )
                ordered_effect_states[item.effect_id] = (
                    BrokerEffectState.DISPATCH_CLAIMED
                )
                ordered_claim_occurrences[item.effect_id] = item.claim_occurrence_id
            elif isinstance(item, RecoverClaimedEffect):
                ordered_effect_states[item.effect_id] = (
                    BrokerEffectState.OUTCOME_UNKNOWN
                )
                scope = ordered_effect_scopes.get(item.effect_id)
                if (
                    scope is not None
                    and scope.kind is EffectKind.CANCEL
                    and scope.target_leg_key is not None
                ):
                    ordered_leg_pending[scope.target_leg_key] = (
                        PendingVenueOperation.CANCEL
                    )
            elif isinstance(item, RecordTransportOutcome):
                ordered_effect_states[item.effect_id] = item.state
                scope = ordered_effect_scopes.get(item.effect_id)
                if (
                    scope is not None
                    and scope.kind is EffectKind.CANCEL
                    and scope.target_leg_key is not None
                ):
                    target_leg_key = scope.target_leg_key
                    ordered_leg_pending[target_leg_key] = (
                        PendingVenueOperation.CANCEL
                        if item.state
                        in {
                            BrokerEffectState.ACKNOWLEDGED,
                            BrokerEffectState.OUTCOME_UNKNOWN,
                        }
                        else None
                    )
                    if (
                        item.state is BrokerEffectState.REJECTED
                        and ordered_cancel_reservations.get(target_leg_key)
                        == item.effect_id
                    ):
                        del ordered_cancel_reservations[target_leg_key]
            elif isinstance(item, DiscoverVenueLeg):
                discovery_scope = ordered_effect_scopes.get(item.effect_id)
                if (
                    discovery_scope is None
                    or discovery_scope.kind is EffectKind.CANCEL
                    or not _same_leg_scope(self.scope, item.leg_key)
                ):
                    raise ValueError(
                        "venue discovery requires a non-cancel effect in exact scope"
                    )
                prior_effect_id = ordered_leg_effects.get(item.leg_key)
                if prior_effect_id is None:
                    if ordered_effect_states.get(item.effect_id) not in {
                        BrokerEffectState.DISPATCH_CLAIMED,
                        BrokerEffectState.ACKNOWLEDGED,
                        BrokerEffectState.OUTCOME_UNKNOWN,
                        BrokerEffectState.NEEDS_REVIEW,
                    } and ordered_acceptance_states.get(item.effect_id) not in {
                        AcceptanceSetState.CLOSED,
                        AcceptanceSetState.INVALIDATED,
                    }:
                        raise ValueError(
                            "first venue discovery requires dispatch progress or a "
                            "closed acceptance set"
                        )
                    ordered_leg_effects[item.leg_key] = item.effect_id
                    ordered_leg_states[item.leg_key] = VenueAttemptState.WORKING
                    ordered_leg_pending[item.leg_key] = None
                    if (
                        ordered_acceptance_states.get(item.effect_id)
                        is AcceptanceSetState.CLOSED
                    ):
                        ordered_acceptance_states[item.effect_id] = (
                            AcceptanceSetState.INVALIDATED
                        )
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
            elif isinstance(item, RecordPendingVenueOperation):
                if (
                    item.operation is PendingVenueOperation.NONE
                    or item.leg_key not in ordered_leg_effects
                    or item.leg_key in ordered_closed_legs
                ):
                    raise ValueError(
                        "pending venue operation requires a previously discovered "
                        "active leg"
                    )
                ordered_leg_pending[item.leg_key] = item.operation
            elif isinstance(item, CloseAcceptanceSet):
                effect_scope = ordered_effect_scopes.get(item.effect_id)
                claim_occurrence_id = ordered_claim_occurrences.get(item.effect_id)
                proof = item.proof
                if (
                    ordered_acceptance_states.get(item.effect_id)
                    is not AcceptanceSetState.OPEN
                    or effect_scope is None
                    or proof.effect_scope != effect_scope
                    or proof.claim_occurrence_id != claim_occurrence_id
                    or (
                        proof.kind is AcceptanceProofKind.NEVER_DISPATCHED
                        and (
                            ordered_effect_states.get(item.effect_id)
                            is not BrokerEffectState.CANCELED_BEFORE_DISPATCH
                            or claim_occurrence_id is not None
                        )
                    )
                    or any(
                        effect_id == item.effect_id
                        and leg_key not in ordered_closed_legs
                        for leg_key, effect_id in ordered_leg_effects.items()
                    )
                ):
                    raise ValueError(
                        "acceptance closure requires its exact claim, proof, and no "
                        "active legs"
                    )
                ordered_acceptance_states[item.effect_id] = AcceptanceSetState.CLOSED
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

        for effect_id, effect in effects.items():
            if (
                ordered_acceptance_states.get(effect_id)
                is not effect.acceptance_set_state
            ):
                raise ValueError(
                    "effect acceptance state, proof, and contradiction must equal "
                    "its ordered input history"
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
                elif isinstance(item, RecoverClaimedEffect):
                    scope = ordered_effect_scopes.get(item.effect_id)
                    if (
                        scope is not None
                        and scope.kind is EffectKind.CANCEL
                        and scope.target_leg_key == owner.leg_key
                    ):
                        derived_pending = PendingVenueOperation.CANCEL
                elif isinstance(item, RecordTransportOutcome):
                    scope = ordered_effect_scopes.get(item.effect_id)
                    if (
                        scope is not None
                        and scope.kind is EffectKind.CANCEL
                        and scope.target_leg_key == owner.leg_key
                    ):
                        derived_pending = (
                            PendingVenueOperation.CANCEL
                            if item.state
                            in {
                                BrokerEffectState.ACKNOWLEDGED,
                                BrokerEffectState.OUTCOME_UNKNOWN,
                            }
                            else None
                        )
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
            self.execution_registry_count,
            self.execution_registry_commitment,
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
            if type(source) not in {
                CatchUpExecutionRegistry,
                _BrokerExecutionRegistryCatchUp,
            }:
                raise ValueError(
                    "execution reconciliation requires exact catch-up provenance"
                )
            source = cast(
                CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
                source,
            )
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
                or VenueExecutionCheckpoint.from_execution(target_prior)
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
                if type(source) is not CatchUpExecutionRegistry:
                    raise ValueError(
                        "resolved projection requires ordinary catch-up provenance"
                    )
                if (
                    source.prior_account_registry_count != execution.seen_facts.count
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
            if type(registry_record) is _AttributedRegistryAdvanceOutcome:
                if type(source) is not _BrokerExecutionRegistryCatchUp:
                    raise ValueError(
                        "attributed advance requires broker-owner provenance"
                    )
                source_prior = _replay_venue_hydration_snapshot(
                    scope,
                    execution.seen_facts,
                    authorized_human_facts=authorized_human_facts,
                    authorized_corroborations=authorized_corroborations,
                    limit=source.prior_account_registry_count,
                )
                prior_source_binding = _execution_binding_for_snapshot(source_prior)
                observation = execution.seen_facts.get(source.fact.key)
                owner = owners.get(source.leg_key)
                effect = effects.get(source.effect_id)
                if (
                    source.target_scope != scope
                    or source.prior_account_registry_count + 1
                    != execution.seen_facts.count
                    or source.prior_account_registry_count
                    != registry_record.prior_account_registry_count
                    or source.prior_account_registry_commitment
                    != registry_record.prior_account_registry_commitment
                    or source.prior_source_binding != prior_source_binding
                    or registry_record.prior_source_binding != prior_source_binding
                    or registry_record.resulting_source_binding
                    != resulting_source_binding
                    or registry_record.effect_id != source.effect_id
                    or registry_record.leg_key != source.leg_key
                    or registry_record.fact != source.fact
                    or observation is None
                    or observation.fact != source.fact
                    or observation.classification
                    is not registry_record.observation_classification
                    or observation.classification
                    not in _DIRECT_BROKER_FACT_CLASSIFICATIONS
                    or owner is None
                    or effect is None
                    or owner.effect_id != source.effect_id
                    or owner.leg_key != source.leg_key
                    or effect.scope.position_scope != scope
                    or effect.scope.symbol_id != source.fact.scope.symbol_id
                    or effect.scope.side is not source.fact.scope.side
                    or not _direct_acquisition_relation_matches_book(
                        self,
                        self.scope.generation,
                        scope,
                        effect.scope.request_occurrence_id,
                        source.effect_id,
                        source.leg_key,
                        source.fact.root_key,
                    )
                    or _execution_binding_for_snapshot(target_result)
                    != resulting_source_binding
                ):
                    raise ValueError(
                        "attributed catch-up outcome lacks exact owner/source proof"
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
                or source.prior_source_binding != registry_record.prior_source_binding
                or registry_record.prior_source_binding != prior_source_binding
                or registry_record.resulting_source_binding != resulting_source_binding
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
            _BrokerExecutionRegistryCatchUp,
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
        rebuilt_correlations = _audit_rebuild_acquisition_correlation_index(
            self.scope,
            self._effect_by_request_occurrence,
            self._effect_by_id,
            self._owner_by_leg,
            self.human_coverages,
            self.broker_coverages,
            self.input_records,
            self.execution_reconciliations,
        )
        if (
            rebuilt_correlations.commitment
            != self._acquisition_correlation_by_root.commitment
        ):
            raise ValueError(
                "acquisition correlation index contradicts exact retained provenance"
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
        if type(scope) is not VenueScope:
            raise TypeError("scope must be the exact VenueScope type")
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
            ("_acquisition_correlation_by_root", _PersistentKeyMap.empty()),
            ("_leg_current_by_leg", _PersistentKeyMap.empty()),
            ("_leg_summary_by_effect", _PersistentKeyMap.empty()),
            ("_cancel_target_reservation_by_leg", _PersistentKeyMap.empty()),
            ("_authority_contribution_by_effect", _PersistentKeyMap.empty()),
            ("_authority_summary_by_scope", _PersistentKeyMap.empty()),
            ("_account_unclaimed_requested_effect_ids", ()),
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
            ("_execution_snapshot_by_scope", _PersistentKeyMap.empty()),
            ("_bootstrap_bound_target_by_scope", _PersistentKeyMap.empty()),
            ("_protection_cursor_by_scope", _PersistentKeyMap.empty()),
            ("_protection_transition_ledger", _PersistentSequence.empty()),
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

    def acquisition_correlation(
        self,
        request_occurrence_id: RequestOccurrenceId,
        effect_id: EffectId,
        *,
        leg_key: VenueLegKey | None = None,
        root_key: RootFillKey | None = None,
    ) -> VenueAcquisitionCorrelation | None:
        """Return one direct immutable venue provenance projection, if exact.

        This query deliberately uses only current direct maps.  It neither
        evaluates effect status nor materializes an audit/history view.
        """

        _require("request_occurrence_id", request_occurrence_id, RequestOccurrenceId)
        _require("effect_id", effect_id, EffectId)
        if leg_key is not None:
            _require("leg_key", leg_key, VenueLegKey)
        if root_key is not None:
            _require("root_key", root_key, RootFillKey)
        if leg_key is None and root_key is None:
            return None
        mapped_effect_id = self._effect_by_request_occurrence.get(
            _request_occurrence_index_key(request_occurrence_id)
        )
        if mapped_effect_id != effect_id:
            return None
        current = self._effect_by_id.get(_effect_index_key(effect_id))
        if current is None:
            return None
        effect_scope = current.effect.scope
        if (
            effect_scope.request_occurrence_id != request_occurrence_id
            or effect_scope.effect_id != effect_id
            or effect_scope.generation != self.scope.generation
        ):
            return None
        proven_leg = leg_key
        if root_key is not None:
            entry = self._acquisition_correlation_by_root.get(
                _coverage_root_index_key(root_key)
            )
            if (
                entry is None
                or type(entry) is not _AcquisitionCorrelationEntry
                or entry.root_key != root_key
                or entry.request_occurrence_id != request_occurrence_id
                or entry.effect_id != effect_id
                or entry.application_generation_id != self.scope.generation
                or entry.position_scope != effect_scope.position_scope
                or (leg_key is not None and entry.leg_key != leg_key)
            ):
                return None
            proven_leg = entry.leg_key
        if proven_leg is not None:
            owner = self._owner_by_leg.get(_leg_index_key(proven_leg))
            if (
                owner is None
                or owner.leg_key != proven_leg
                or owner.effect_id != effect_id
                or owner.effect_scope != effect_scope
            ):
                return None
        result = object.__new__(VenueAcquisitionCorrelation)
        object.__setattr__(result, "application_generation_id", self.scope.generation)
        object.__setattr__(result, "position_scope", effect_scope.position_scope)
        object.__setattr__(result, "request_occurrence_id", request_occurrence_id)
        object.__setattr__(result, "effect_id", effect_id)
        object.__setattr__(result, "leg_key", proven_leg)
        object.__setattr__(result, "root_key", root_key)
        commitment = _acquisition_correlation_commitment(
            self.scope.generation,
            effect_scope.position_scope,
            request_occurrence_id,
            effect_id,
            proven_leg,
            root_key,
        )
        object.__setattr__(result, "correlation_commitment", commitment)
        object.__setattr__(
            result,
            "_seal",
            _commit_parts(
                b"execution-core/venue-acquisition-correlation-seal/v1",
                commitment,
            ),
        )
        return result

    def project_acquisition_context(
        self,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> AcquisitionVenueContext:
        """Mint one bounded target context without materializing account history.

        The returned value may be non-serving when the exact full-input checks
        fail.  It is still opaque and has no mutation authority; consumers must
        call ``matches_current`` before using its retained target token.
        """

        _require("execution", execution, ExecutionSnapshot)
        _require("position_scope", position_scope, PositionScope)
        scope_matches_book = (
            position_scope.broker == self.scope.broker
            and position_scope.environment == self.scope.environment
            and position_scope.account == self.scope.account
        )
        serving = bool(
            scope_matches_book
            and not execution.account_reconciliation_required
            and not self._has_unresolved_execution_reconciliation(position_scope)
            and self._execution_matches(execution, position_scope)
        )
        return _new_acquisition_venue_context(
            self,
            execution,
            position_scope,
            serving,
        )

    def project_acquisition_bootstrap(
        self,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> AcquisitionVenueProjection:
        """Produce a fail-closed target bootstrap proof from direct summaries."""

        context = self.project_acquisition_context(execution, position_scope)
        summary = self._authority_summary_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        if summary is None:
            summary = _SymbolAuthoritySummary()
        bootstrap_target = self._bootstrap_bound_target_pair_matches(
            execution,
            position_scope,
        )
        completed_target = bool(
            not bootstrap_target
            and summary.effect_count > 0
            and execution.position.raw_quantity == 0
        )
        serving = bool(
            context._serving
            and (bootstrap_target or completed_target)
            and execution.position.raw_quantity == 0
            and (completed_target or execution.position.root_count == 0)
            and execution.integrity is PositionIntegrity.CONSISTENT
            and summary.blocking_effect_count == 0
            and summary.blocking_buy_effect_count == 0
            and summary.waiting_buy_parent_count == 0
            and summary.unknown_buy_effect_count == 0
            and not self._has_unresolved_execution_reconciliation(position_scope)
        )
        return _new_acquisition_venue_projection(
            source_kind=AcquisitionVenueSourceKind.BOOTSTRAP,
            context=context,
            predecessor_execution_snapshot_commitment=None,
            predecessor_scope_execution_commitment=None,
            predecessor_venue_commitment=None,
            source_commitment=_commit_parts(
                b"execution-core/acquisition-venue/bootstrap/v1",
                context._seal,
            ),
            fact_relation=None,
            serving=serving,
        )

    def project_acquisition_fact(
        self,
        transition: VenueRecoveryTransition,
    ) -> AcquisitionVenueProjection:
        """Expose one current canonical fact through retained direct indexes."""

        _require("transition", transition, VenueRecoveryTransition)
        protection_proof = transition._protection_proof
        position_scope = (
            protection_proof.position_scope
            if type(protection_proof) is _ProtectionTransitionProof
            else transition.execution.position.scope
        )
        context = self.project_acquisition_context(transition.execution, position_scope)
        proof = transition._acquisition_fact_proof
        serving = _acquisition_fact_proof_matches_transition(self, transition)
        source_kind = (
            proof.source_kind
            if serving and type(proof) is _AcquisitionFactProof
            else (
                AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION
                if transition.disposition
                is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
                else AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT
            )
        )
        predecessor_execution_snapshot_commitment = (
            proof.predecessor_execution_snapshot_commitment
            if serving and type(proof) is _AcquisitionFactProof
            else None
        )
        predecessor_scope_execution_commitment = (
            proof.predecessor_scope_execution_commitment
            if serving and type(proof) is _AcquisitionFactProof
            else None
        )
        predecessor_venue_commitment = (
            proof.predecessor_venue_commitment
            if serving and type(proof) is _AcquisitionFactProof
            else None
        )
        source_commitment = (
            proof.commitment
            if serving and type(proof) is _AcquisitionFactProof
            else _commit_parts(
                b"execution-core/acquisition-venue/refused-fact/v1",
                (
                    transition._protection_proof_commitment
                    if type(transition._protection_proof_commitment) is bytes
                    and len(transition._protection_proof_commitment) == 32
                    else b""
                ),
            )
        )
        return _new_acquisition_venue_projection(
            source_kind=source_kind,
            context=context,
            predecessor_execution_snapshot_commitment=(
                predecessor_execution_snapshot_commitment
            ),
            predecessor_scope_execution_commitment=(
                predecessor_scope_execution_commitment
            ),
            predecessor_venue_commitment=predecessor_venue_commitment,
            source_commitment=source_commitment,
            fact_relation=(
                _new_acquisition_fact_relation(proof)
                if serving and type(proof) is _AcquisitionFactProof
                else None
            ),
            serving=serving,
        )

    def execution_binding(
        self, position_scope: PositionScope
    ) -> VenueExecutionBinding | None:
        return self._binding_by_scope.get(_position_scope_index_key(position_scope))

    def _bootstrap_bound_target_record(
        self,
        position_scope: PositionScope,
    ) -> _BootstrapBoundTargetRecord | None:
        """Return one sealed active-target record through its direct index only."""

        record = self._bootstrap_bound_target_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        return record if type(record) is _BootstrapBoundTargetRecord else None

    def _staged_bootstrap_bound_target_record(
        self,
        position_scope: PositionScope,
    ) -> _StagedBootstrapBoundTargetRecord | None:
        """Return an internal, not-yet-returnable checkpoint stage."""

        record = self._bootstrap_bound_target_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        return record if type(record) is _StagedBootstrapBoundTargetRecord else None

    def _bootstrap_bound_target_anchor_matches(
        self,
        record: _BootstrapBoundTargetRecord,
        position_scope: PositionScope,
    ) -> bool:
        """Validate immutable bootstrap provenance through direct retained keys."""

        if (
            not _bootstrap_bound_target_record_is_authentic(record)
            or record.application_generation_id != self.scope.generation
            or record.position_scope != position_scope
        ):
            return False
        input_record = self._input_record(record.bootstrap_input_id)
        bootstrap_input = (
            input_record.item if type(input_record) is VenueInputRecord else None
        )
        proof = record._bootstrap_neutral_checkpoint_proof
        target_genesis = ExecutionSnapshot.flat(position_scope)
        return bool(
            type(bootstrap_input) is _BootstrapTargetRegistryInput
            and _bootstrap_target_registry_input_is_authentic(bootstrap_input)
            and bootstrap_input.input_id == record.bootstrap_input_id
            and bootstrap_input.commitment == record.bootstrap_input_commitment
            and bootstrap_input.application_generation_id
            == record.application_generation_id
            and bootstrap_input.source_kind is record.source_kind
            and bootstrap_input.position_scope == position_scope
            and bootstrap_input.source_execution_commitment
            == record.source_execution_commitment
            and bootstrap_input.target_genesis_execution_commitment
            == record.target_genesis_execution_commitment
            and bootstrap_input.target_execution_commitment
            == record.bootstrap_target_execution_commitment
            and bootstrap_input.prior_account_registry_count
            == record.bootstrap_account_registry_count
            and bootstrap_input.prior_account_registry_commitment
            == record.bootstrap_account_registry_commitment
            and bootstrap_input.reconciliation_transition_count
            == record.bootstrap_reconciliation_transition_count
            and bootstrap_input.reconciliation_transition_head
            == record.bootstrap_reconciliation_transition_head
            and record.target_genesis_execution_commitment == target_genesis.commitment
            and proof.position_scope == position_scope
            and proof.predecessor_cursor == _protection_genesis_cursor()
            and proof.cursor.ordinal == 1
            and proof.predecessor_execution_commitment == target_genesis.commitment
            and proof.execution_commitment
            == record.bootstrap_target_execution_commitment
            and proof.predecessor_execution_checkpoint
            == VenueExecutionCheckpoint.from_execution(target_genesis)
            and proof.predecessor_summary == _SymbolAuthoritySummary()
            and proof.summary == _SymbolAuthoritySummary()
            and proof.predecessor_binding is None
            and proof.binding == record.binding
            and not proof.predecessor_execution_binding_matches
            and proof.execution_binding_matches
            and proof.predecessor_account_reconciliation_clear
            and proof.account_reconciliation_clear
            and proof.command_commitment
            == _protection_command_commitment(bootstrap_input)
            and proof.disposition is VenueRecoveryDisposition.APPLIED
            and proof.quantity_delta == 0
            and proof.book_scope == self.scope
            and proof.predecessor_book_scope == self.scope
            and proof.lineage_is_authentic
        )

    def _bootstrap_bound_target_current_pair_matches(
        self,
        record: _BootstrapBoundTargetRecord,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> bool:
        """Validate the current bounded checkpoint without scanning history."""

        if (
            execution.position.scope != position_scope
            or execution.position.raw_quantity != 0
            or execution.position.root_count != 0
            or execution.integrity is not PositionIntegrity.CONSISTENT
            or execution.account_reconciliation_required
            or self._has_unresolved_execution_reconciliation(position_scope)
            or self.execution_registry_count != execution.seen_facts.count
            or self.execution_registry_commitment != execution.seen_facts.commitment
            or self.execution_registry_count != record.account_registry_count
            or self.execution_registry_commitment != record.account_registry_commitment
            or record.target_execution_commitment != execution.commitment
            or record.reconciliation_transition_count
            != execution.reconciliation_transition_count
            or record.reconciliation_transition_head
            != execution.reconciliation_transition_head
            or not self._execution_reconciliation_cursor_matches(execution)
        ):
            return False
        binding = self.execution_binding(position_scope)
        snapshot = self._execution_snapshot_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        cursor = self._protection_cursor_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        input_record = self._input_record(record.checkpoint_input_id)
        checkpoint_input = (
            input_record.item if type(input_record) is VenueInputRecord else None
        )
        proof = record._neutral_checkpoint_proof
        summary = (
            self._authority_summary_by_scope.get(
                _position_scope_index_key(position_scope)
            )
            or _SymbolAuthoritySummary()
        )
        exact_checkpoint: _BootstrapTargetRegistryInput | CatchUpExecutionRegistry
        if type(checkpoint_input) is _BootstrapTargetRegistryInput:
            exact_checkpoint = checkpoint_input
            if (
                exact_checkpoint.input_id != record.bootstrap_input_id
                or exact_checkpoint.commitment != record.bootstrap_input_commitment
                or record.target_execution_commitment
                != record.bootstrap_target_execution_commitment
                or record.account_registry_count
                != record.bootstrap_account_registry_count
                or record.account_registry_commitment
                != record.bootstrap_account_registry_commitment
                or record.reconciliation_transition_count
                != record.bootstrap_reconciliation_transition_count
                or record.reconciliation_transition_head
                != record.bootstrap_reconciliation_transition_head
                or proof != record._bootstrap_neutral_checkpoint_proof
            ):
                return False
        elif type(checkpoint_input) is CatchUpExecutionRegistry:
            exact_checkpoint = checkpoint_input
            if exact_checkpoint.target_scope != position_scope:
                return False
        else:
            return False
        return bool(
            binding == record.binding
            and snapshot == execution
            and type(cursor) is _ProtectionCursor
            and exact_checkpoint.input_id == record.checkpoint_input_id
            and _protection_command_commitment(exact_checkpoint)
            == record.checkpoint_command_commitment
            and proof.position_scope == position_scope
            and proof.cursor == cursor
            and proof.execution_commitment == execution.commitment
            and proof.execution_checkpoint
            == VenueExecutionCheckpoint.from_execution(execution)
            and proof.summary == summary
            and proof.binding == binding
            and proof.execution_binding_matches
            and proof.account_reconciliation_clear
            and proof.command_commitment == record.checkpoint_command_commitment
            and proof.disposition is VenueRecoveryDisposition.APPLIED
            and proof.quantity_delta == 0
            and proof.book_commitment == _protection_book_commitment(self)
            and proof.book_scope == self.scope
            and proof.predecessor_book_scope == self.scope
            and summary.effect_count == 0
            and summary.blocking_effect_count == 0
            and summary.blocking_buy_effect_count == 0
            and summary.waiting_buy_parent_count == 0
            and summary.unknown_buy_effect_count == 0
            and proof.lineage_is_authentic
        )

    def _staged_bootstrap_bound_target_pair_matches(
        self,
        stage: _StagedBootstrapBoundTargetRecord,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> bool:
        """Validate an internal stage before its standard proof is minted."""

        if (
            not _staged_bootstrap_bound_target_record_is_authentic(stage)
            or not self._bootstrap_bound_target_anchor_matches(
                stage.active_record,
                position_scope,
            )
            or execution.position.scope != position_scope
            or execution.position.raw_quantity != 0
            or execution.position.root_count != 0
            or execution.integrity is not PositionIntegrity.CONSISTENT
            or execution.account_reconciliation_required
            or self._has_unresolved_execution_reconciliation(position_scope)
            or stage.target_execution_commitment != execution.commitment
            or stage.account_registry_count != execution.seen_facts.count
            or stage.account_registry_commitment != execution.seen_facts.commitment
            or stage.reconciliation_transition_count
            != execution.reconciliation_transition_count
            or stage.reconciliation_transition_head
            != execution.reconciliation_transition_head
            or self.execution_registry_count != execution.seen_facts.count
            or self.execution_registry_commitment != execution.seen_facts.commitment
            or not self._execution_reconciliation_cursor_matches(execution)
        ):
            return False
        binding = self.execution_binding(position_scope)
        snapshot = self._execution_snapshot_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        input_record = self._input_record(stage.checkpoint_input_id)
        checkpoint_input = (
            input_record.item if type(input_record) is VenueInputRecord else None
        )
        summary = (
            self._authority_summary_by_scope.get(
                _position_scope_index_key(position_scope)
            )
            or _SymbolAuthoritySummary()
        )
        return bool(
            binding == stage.active_record.binding
            and snapshot == execution
            and type(checkpoint_input) is CatchUpExecutionRegistry
            and checkpoint_input.input_id == stage.checkpoint_input_id
            and checkpoint_input.target_scope == position_scope
            and _protection_command_commitment(checkpoint_input)
            == stage.checkpoint_command_commitment
            and summary == _SymbolAuthoritySummary()
        )

    def _bootstrap_bound_target_pair_matches(
        self,
        execution: ExecutionSnapshot,
        position_scope: PositionScope,
    ) -> bool:
        """Authenticate the active zero-effect exception from bounded indexes.

        This intentionally does not materialize the protection ledger or any
        venue history.  The record carries the one sealed neutral proof and the
        per-scope cursor lets us re-derive its head directly.
        """

        record = self._bootstrap_bound_target_record(position_scope)
        if record is not None:
            return bool(
                self._bootstrap_bound_target_anchor_matches(record, position_scope)
                and self._bootstrap_bound_target_current_pair_matches(
                    record,
                    execution,
                    position_scope,
                )
            )
        stage = self._staged_bootstrap_bound_target_record(position_scope)
        return bool(
            stage is not None
            and self._staged_bootstrap_bound_target_pair_matches(
                stage,
                execution,
                position_scope,
            )
        )

    def _reconciliation_cursor(self) -> tuple[int, bytes]:
        return (
            self._registry_transition_ledger.length,
            self._registry_transition_head_commitment or _RECONCILIATION_GENESIS_HEAD,
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
        if self._bootstrap_bound_target_record(position_scope) is not None:
            return self._bootstrap_bound_target_pair_matches(
                execution,
                position_scope,
            )
        summary = (
            self._authority_summary_by_scope.get(
                _position_scope_index_key(position_scope)
            )
            or _SymbolAuthoritySummary()
        )
        return summary.effect_count > 0

    def _execution_pair_matches_fast(self, execution: ExecutionSnapshot) -> bool:
        """Authenticate one usable transition without touching either audit ledger."""

        position_scope = execution.position.scope
        if self._bootstrap_bound_target_record(position_scope) is not None:
            return self._bootstrap_bound_target_pair_matches(execution, position_scope)
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

    def _active_cancel_effect_for_target(
        self,
        leg_key: VenueLegKey,
    ) -> EffectId | None:
        retained = self._cancel_target_reservation_by_leg.get(_leg_index_key(leg_key))
        return None if retained is None else retained.effect_id

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


_CANCEL_RESERVATION_RELEASE_STATES = frozenset(
    {
        BrokerEffectState.CANCELED_BEFORE_DISPATCH,
        BrokerEffectState.REJECTED,
    }
)


def _cancel_effect_reserves_target(effect: BrokerEffect) -> bool:
    return bool(
        effect.scope.kind is EffectKind.CANCEL
        and effect.state not in _CANCEL_RESERVATION_RELEASE_STATES
    )


def _set_cancel_target_reservation(
    retained: _PersistentKeyMap[_CancelTargetReservation],
    effect: BrokerEffect,
) -> _PersistentKeyMap[_CancelTargetReservation]:
    if effect.scope.kind is not EffectKind.CANCEL:
        return retained
    target_leg_key = effect.scope.target_leg_key
    if target_leg_key is None:
        raise ValueError("cancel effect requires its exact target reservation")
    key = _leg_index_key(target_leg_key)
    current = retained.get(key)
    resulting_effect_id = (
        effect.effect_id if _cancel_effect_reserves_target(effect) else None
    )
    if (
        current is not None
        and current.effect_id is not None
        and current.effect_id != effect.effect_id
    ):
        raise ValueError("cancel target already has another active reservation")
    resulting = _CancelTargetReservation(resulting_effect_id)
    if current is None:
        return retained.insert_new(key, resulting, resulting.commitment)
    return retained.replace_existing(key, resulting, resulting.commitment)


def _evolve_cancel_target_reservations(
    retained: _PersistentKeyMap[_CancelTargetReservation],
    prior: BrokerEffect | None,
    resulting: BrokerEffect,
) -> _PersistentKeyMap[_CancelTargetReservation]:
    if resulting.scope.kind is not EffectKind.CANCEL:
        return retained
    if prior is not None:
        if prior.scope != resulting.scope:
            raise ValueError("cancel target reservation scope cannot change")
        prior_reserves = _cancel_effect_reserves_target(prior)
        resulting_reserves = _cancel_effect_reserves_target(resulting)
        if not prior_reserves and not resulting_reserves:
            return retained
        if not prior_reserves and resulting_reserves:
            raise ValueError("released cancel target reservation cannot reactivate")
    return _set_cancel_target_reservation(retained, resulting)


def _rebuild_cancel_target_reservations(
    book: VenueRecoveryBook,
) -> _PersistentKeyMap[_CancelTargetReservation]:
    retained: _PersistentKeyMap[_CancelTargetReservation] = _PersistentKeyMap.empty()
    for index in range(book._effect_order.length):
        effect_id = book._effect_order.get(index)
        effect = book._current_effect(effect_id)
        if effect is None:
            raise ValueError("cancel target reservation requires retained effect")
        retained = _set_cancel_target_reservation(retained, effect)
    return retained


def _set_authority_contribution(
    retained: _PersistentKeyMap[_EffectAuthorityContribution],
    contribution: _EffectAuthorityContribution,
) -> _PersistentKeyMap[_EffectAuthorityContribution]:
    key = _effect_index_key(contribution.effect_id)
    if retained.get(key) is None:
        return retained.insert_new(key, contribution, contribution.commitment)
    return retained.replace_existing(key, contribution, contribution.commitment)


def _set_symbol_authority_summary(
    retained: _PersistentKeyMap[_SymbolAuthoritySummary],
    position_scope: PositionScope,
    summary: _SymbolAuthoritySummary,
) -> _PersistentKeyMap[_SymbolAuthoritySummary]:
    key = _position_scope_index_key(position_scope)
    if retained.get(key) is None:
        return retained.insert_new(key, summary, summary.commitment)
    return retained.replace_existing(key, summary, summary.commitment)


def _derive_effect_authority_contribution(
    book: VenueRecoveryBook,
    effect_id: EffectId,
) -> _EffectAuthorityContribution:
    effect = book._current_effect(effect_id)
    if effect is None:
        raise KeyError("authority contribution requires one retained effect")
    legs = book._leg_summary(effect_id)
    reconciliation_clean = not book._has_effect_reconciliation(effect_id)
    fully_resolved = bool(
        effect.acceptance_set_state is AcceptanceSetState.CLOSED
        and legs.active_count == 0
        and reconciliation_clean
    )
    safely_local = bool(
        effect.state is BrokerEffectState.REQUESTED
        and effect.claim_occurrence_id is None
        and legs.owner_count == 0
        and reconciliation_clean
    )
    exposure_buy = bool(
        effect.scope.kind in {EffectKind.SUBMIT, EffectKind.REPLACE}
        and effect.scope.side is ExecutionSide.BUY
    )
    blocking_buy = exposure_buy and not fully_resolved
    known_cancellable = (
        legs.known_cancellable_leg_keys
        if blocking_buy and effect.state is BrokerEffectState.ACKNOWLEDGED
        else ()
    )
    known_cancel_pending = (
        legs.known_cancel_pending_leg_keys
        if blocking_buy and effect.state is BrokerEffectState.ACKNOWLEDGED
        else ()
    )
    return _EffectAuthorityContribution(
        effect_id=effect.effect_id,
        position_scope=effect.scope.position_scope,
        unclaimed_requested=bool(
            effect.state is BrokerEffectState.REQUESTED
            and effect.claim_occurrence_id is None
        ),
        target_exemptible=safely_local,
        blocking_effect_count=0 if fully_resolved else 1,
        blocking_buy_effect_count=1 if blocking_buy else 0,
        stand_downable_buy_count=1 if blocking_buy and safely_local else 0,
        stand_downable_buy_effect_ids=(
            (effect.effect_id,) if blocking_buy and safely_local else ()
        ),
        known_cancellable_buy_leg_keys=known_cancellable,
        known_cancel_pending_buy_leg_keys=known_cancel_pending,
        waiting_buy_parent_count=(
            1
            if blocking_buy
            and effect.acceptance_set_state
            in {AcceptanceSetState.OPEN, AcceptanceSetState.INVALIDATED}
            and not safely_local
            else 0
        ),
        unknown_buy_effect_count=(
            1
            if blocking_buy
            and not safely_local
            and not known_cancellable
            and not known_cancel_pending
            else 0
        ),
    )


def _without_tuple_items(
    retained: tuple[Any, ...],
    removed: tuple[Any, ...],
) -> tuple[Any, ...]:
    return tuple(item for item in retained if item not in removed)


def _update_authority_indexes(
    contribution_by_effect: _PersistentKeyMap[_EffectAuthorityContribution],
    summary_by_scope: _PersistentKeyMap[_SymbolAuthoritySummary],
    account_unclaimed: tuple[EffectId, ...],
    *,
    prior: _EffectAuthorityContribution | None,
    resulting: _EffectAuthorityContribution,
) -> tuple[
    _PersistentKeyMap[_EffectAuthorityContribution],
    _PersistentKeyMap[_SymbolAuthoritySummary],
    tuple[EffectId, ...],
]:
    if prior is not None and prior.position_scope != resulting.position_scope:
        raise ValueError("effect authority scope cannot change")
    position_scope = resulting.position_scope
    summary = summary_by_scope.get(_position_scope_index_key(position_scope))
    if summary is None:
        summary = _SymbolAuthoritySummary()
    if prior is not None:
        summary = replace(
            summary,
            blocking_effect_count=(
                summary.blocking_effect_count - prior.blocking_effect_count
            ),
            blocking_buy_effect_count=(
                summary.blocking_buy_effect_count - prior.blocking_buy_effect_count
            ),
            stand_downable_buy_count=(
                summary.stand_downable_buy_count - prior.stand_downable_buy_count
            ),
            stand_downable_buy_effect_ids=cast(
                tuple[EffectId, ...],
                _without_tuple_items(
                    summary.stand_downable_buy_effect_ids,
                    prior.stand_downable_buy_effect_ids,
                ),
            ),
            known_cancellable_buy_leg_keys=cast(
                tuple[VenueLegKey, ...],
                _without_tuple_items(
                    summary.known_cancellable_buy_leg_keys,
                    prior.known_cancellable_buy_leg_keys,
                ),
            ),
            known_cancel_pending_buy_leg_keys=cast(
                tuple[VenueLegKey, ...],
                _without_tuple_items(
                    summary.known_cancel_pending_buy_leg_keys,
                    prior.known_cancel_pending_buy_leg_keys,
                ),
            ),
            waiting_buy_parent_count=(
                summary.waiting_buy_parent_count - prior.waiting_buy_parent_count
            ),
            unknown_buy_effect_count=(
                summary.unknown_buy_effect_count - prior.unknown_buy_effect_count
            ),
        )
        if prior.unclaimed_requested:
            account_unclaimed = tuple(
                effect_id
                for effect_id in account_unclaimed
                if effect_id != prior.effect_id
            )
    else:
        summary = replace(summary, effect_count=summary.effect_count + 1)
    summary = replace(
        summary,
        blocking_effect_count=(
            summary.blocking_effect_count + resulting.blocking_effect_count
        ),
        blocking_buy_effect_count=(
            summary.blocking_buy_effect_count + resulting.blocking_buy_effect_count
        ),
        stand_downable_buy_count=(
            summary.stand_downable_buy_count + resulting.stand_downable_buy_count
        ),
        stand_downable_buy_effect_ids=(
            summary.stand_downable_buy_effect_ids
            + resulting.stand_downable_buy_effect_ids
        ),
        known_cancellable_buy_leg_keys=(
            summary.known_cancellable_buy_leg_keys
            + resulting.known_cancellable_buy_leg_keys
        ),
        known_cancel_pending_buy_leg_keys=(
            summary.known_cancel_pending_buy_leg_keys
            + resulting.known_cancel_pending_buy_leg_keys
        ),
        waiting_buy_parent_count=(
            summary.waiting_buy_parent_count + resulting.waiting_buy_parent_count
        ),
        unknown_buy_effect_count=(
            summary.unknown_buy_effect_count + resulting.unknown_buy_effect_count
        ),
    )
    if (
        min(
            summary.blocking_effect_count,
            summary.blocking_buy_effect_count,
            summary.stand_downable_buy_count,
            summary.waiting_buy_parent_count,
            summary.unknown_buy_effect_count,
        )
        < 0
    ):
        raise ValueError("symbol authority aggregate cannot become negative")
    if resulting.unclaimed_requested:
        account_unclaimed = account_unclaimed + (resulting.effect_id,)
    return (
        _set_authority_contribution(contribution_by_effect, resulting),
        _set_symbol_authority_summary(summary_by_scope, position_scope, summary),
        account_unclaimed,
    )


def _rebuild_authority_indexes(
    book: VenueRecoveryBook,
) -> tuple[
    _PersistentKeyMap[_EffectAuthorityContribution],
    _PersistentKeyMap[_SymbolAuthoritySummary],
    tuple[EffectId, ...],
]:
    contribution_by_effect: _PersistentKeyMap[_EffectAuthorityContribution] = (
        _PersistentKeyMap.empty()
    )
    summary_by_scope: _PersistentKeyMap[_SymbolAuthoritySummary] = (
        _PersistentKeyMap.empty()
    )
    account_unclaimed: tuple[EffectId, ...] = ()
    for index in range(book._effect_order.length):
        effect_id = book._effect_order.get(index)
        contribution = _derive_effect_authority_contribution(book, effect_id)
        (
            contribution_by_effect,
            summary_by_scope,
            account_unclaimed,
        ) = _update_authority_indexes(
            contribution_by_effect,
            summary_by_scope,
            account_unclaimed,
            prior=None,
            resulting=contribution,
        )
    return contribution_by_effect, summary_by_scope, account_unclaimed


def _authority_effect_identity_conflicts(
    book: VenueRecoveryBook,
    effect_id: EffectId,
    request_occurrence_id: RequestOccurrenceId,
    client_order_id: ClientOrderId | None,
) -> bool:
    """Check permanent effect identities through bounded canonical indexes."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be the exact opaque VenueRecoveryBook type")
    _require("effect_id", effect_id, EffectId)
    _require("request_occurrence_id", request_occurrence_id, RequestOccurrenceId)
    if client_order_id is not None:
        _require("client_order_id", client_order_id, ClientOrderId)
    return bool(
        book._current_effect(effect_id) is not None
        or book._has_request_occurrence(request_occurrence_id)
        or (client_order_id is not None and book._has_client_order(client_order_id))
    )


def _venue_authority_view(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
    target_effect_id: EffectId | None,
) -> _VenueAuthorityView:
    """Return the bounded current authority view without materializing audit history."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be the exact opaque VenueRecoveryBook type")
    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    if type(position_scope) is not PositionScope:
        raise TypeError("position_scope must be the exact PositionScope type")
    if target_effect_id is not None and type(target_effect_id) is not EffectId:
        raise TypeError("target_effect_id must be EffectId or None")
    summary = (
        book._authority_summary_by_scope.get(_position_scope_index_key(position_scope))
        or _SymbolAuthoritySummary()
    )
    binding = book.execution_binding(position_scope)
    bootstrap_bound_target_active = book._bootstrap_bound_target_pair_matches(
        execution,
        position_scope,
    )
    if bootstrap_bound_target_active:
        execution_binding_matches = True
    elif summary.effect_count == 0:
        execution_binding_matches = bool(
            binding is None
            and (
                (
                    book.execution_registry_count is None
                    and book.execution_registry_commitment is None
                )
                or (
                    book.execution_registry_count == execution.seen_facts.count
                    and book.execution_registry_commitment
                    == execution.seen_facts.commitment
                )
            )
        )
    else:
        execution_binding_matches = bool(
            binding is not None
            and binding.position_commitment == execution.position.commitment
            and binding.root_heads_commitment == execution.root_heads.commitment
            and binding.integrity_bits == execution.integrity.value
            and book.execution_registry_count == execution.seen_facts.count
            and book.execution_registry_commitment == execution.seen_facts.commitment
        )
    target = (
        None
        if target_effect_id is None
        else book._authority_contribution_by_effect.get(
            _effect_index_key(target_effect_id)
        )
    )
    return _VenueAuthorityView(
        execution_binding_matches=execution_binding_matches,
        account_reconciliation_clear=(
            book._unresolved_account_execution_reconciliation_count == 0
        ),
        bootstrap_bound_target_active=bootstrap_bound_target_active,
        blocking_effect_count=summary.blocking_effect_count,
        blocking_buy_effect_count=summary.blocking_buy_effect_count,
        target_exemptible_count=(
            1
            if target is not None
            and target.position_scope == position_scope
            and target.target_exemptible
            else 0
        ),
        stand_downable_buy_count=summary.stand_downable_buy_count,
        known_cancellable_buy_leg_count=len(summary.known_cancellable_buy_leg_keys),
        known_cancel_pending_buy_leg_count=len(
            summary.known_cancel_pending_buy_leg_keys
        ),
        waiting_buy_parent_count=summary.waiting_buy_parent_count,
        unknown_buy_effect_count=summary.unknown_buy_effect_count,
    )


def _protection_genesis_cursor() -> _ProtectionCursor:
    return _ProtectionCursor(
        ordinal=0,
        head=_commit_parts(b"execution-core/protection-cursor-genesis/v1"),
        mandate_id=None,
        execution_commitment=None,
        execution_checkpoint=None,
    )


def _m2_restore_compact_venue_book(
    *,
    scope: VenueScope,
    account_authority_epoch: int,
    unresolved_account_execution_reconciliation_count: int,
    execution_registry_count: int | None,
    execution_registry_commitment: bytes | None,
    registry_transition_head_commitment: bytes | None,
    authority_epochs: tuple[tuple[PositionScope, int], ...],
    effects: tuple[
        tuple[_EffectCurrent, tuple[AcceptanceContradiction, ...]], ...
    ],
    claims: tuple[DispatchClaim, ...],
    execution_snapshots: tuple[ExecutionSnapshot, ...],
    protection_cursors: tuple[tuple[PositionScope, _ProtectionCursor], ...],
) -> VenueRecoveryBook:
    """Construct one non-serving venue owner from complete compact current rows.

    This is deliberately not audit hydration.  The caller has already authenticated
    the inert checkpoint and its repository selection proof; this owner keeps only
    current rows which can be checked without omitted history.  All derived indexes
    are rebuilt from those rows, and all append-only ledgers remain empty.
    """

    if type(scope) is not VenueScope:
        raise TypeError("compact venue scope must be exact VenueScope")
    for scalar_name, scalar_value in (
        ("account authority epoch", account_authority_epoch),
        (
            "unresolved account execution reconciliation count",
            unresolved_account_execution_reconciliation_count,
        ),
    ):
        if type(scalar_value) is not int or scalar_value < 0:
            raise ValueError(
                f"{scalar_name} must be a non-negative exact integer"
            )
    if (execution_registry_count is None) != (
        execution_registry_commitment is None
    ):
        raise ValueError("compact venue registry coordinates must be wholly present")
    if execution_registry_count is not None and (
        type(execution_registry_count) is not int or execution_registry_count < 0
    ):
        raise ValueError("compact venue registry count must be non-negative")
    if execution_registry_commitment is not None:
        _require_digest(
            "compact venue registry commitment", execution_registry_commitment
        )
    if registry_transition_head_commitment is not None:
        _require_digest(
            "compact venue registry transition head",
            registry_transition_head_commitment,
        )
    for tuple_name, tuple_value in (
        ("authority_epochs", authority_epochs),
        ("effects", effects),
        ("claims", claims),
        ("execution_snapshots", execution_snapshots),
        ("protection_cursors", protection_cursors),
    ):
        if type(tuple_value) is not tuple:
            raise TypeError(f"compact venue {tuple_name} must be an exact tuple")

    authority_epoch_by_scope: _PersistentKeyMap[int] = _PersistentKeyMap.empty()
    seen_epoch_scopes: set[PositionScope] = set()
    for position_scope, epoch in authority_epochs:
        if (
            type(position_scope) is not PositionScope
            or position_scope in seen_epoch_scopes
            or position_scope.broker != scope.broker
            or position_scope.environment != scope.environment
            or position_scope.account != scope.account
            or type(epoch) is not int
            or epoch < 0
        ):
            raise ValueError("compact venue authority epoch is duplicated or spliced")
        seen_epoch_scopes.add(position_scope)
        authority_epoch_by_scope = _set_int_index(
            authority_epoch_by_scope,
            _position_scope_index_key(position_scope),
            epoch,
            domain=b"execution-core/venue-authority-epoch/v1",
        )

    base = VenueRecoveryBook.empty(scope)
    effect_order = base._effect_order
    effect_by_id = base._effect_by_id
    effect_by_request = base._effect_by_request_occurrence
    effect_by_client = base._effect_by_client_order
    contradiction_by_effect = base._contradiction_order_by_effect
    for current, contradictions in effects:
        if type(current) is not _EffectCurrent or type(contradictions) is not tuple:
            raise TypeError("compact venue effect row has an invalid exact type")
        effect = current.effect
        if (
            type(effect) is not BrokerEffect
            or effect.contradiction_evidence
            or effect.scope.generation != scope.generation
            or effect.scope.broker != scope.broker
            or effect.scope.environment != scope.environment
            or effect.scope.account != scope.account
        ):
            raise ValueError("compact venue effect leaves its venue owner")
        (
            effect_order,
            effect_by_id,
            effect_by_request,
            effect_by_client,
        ) = _append_effect_value(
            effect_order,
            effect_by_id,
            effect_by_request,
            effect_by_client,
            authority_epoch_by_scope,
            account_authority_epoch,
            replace(effect, contradiction_evidence=contradictions),
        )
        if effect_by_id.get(_effect_index_key(effect.effect_id)) != current:
            raise ValueError("compact venue effect epochs are stale or spliced")
        for contradiction in contradictions:
            contradiction_by_effect = _append_contradiction_value(
                contradiction_by_effect,
                effect.effect_id,
                contradiction,
            )

    claim_order = base._claim_order
    claim_by_effect = base._claim_by_effect
    claim_by_occurrence = base._claim_by_occurrence
    for claim in claims:
        claim_order, claim_by_effect, claim_by_occurrence = _append_claim_value(
            claim_order,
            claim_by_effect,
            claim_by_occurrence,
            claim,
        )
        retained = effect_by_id.get(_effect_index_key(claim.effect_id))
        if retained is None or retained.effect.scope != claim.effect_scope:
            raise ValueError("compact venue claim is not bound to its current effect")
    for current, _ in effects:
        retained_claim = claim_by_effect.get(
            _effect_index_key(current.effect.effect_id)
        )
        if (
            current.effect.claim_occurrence_id is None
            and retained_claim is not None
        ) or (
            current.effect.claim_occurrence_id is not None
            and (
                retained_claim is None
                or retained_claim.claim_occurrence_id
                != current.effect.claim_occurrence_id
            )
        ):
            raise ValueError("compact venue effect and claim current rows disagree")

    binding_order = base._binding_order
    binding_by_scope = base._binding_by_scope
    snapshot_by_scope = base._execution_snapshot_by_scope
    seen_snapshot_scopes: set[PositionScope] = set()
    for snapshot in execution_snapshots:
        if (
            type(snapshot) is not ExecutionSnapshot
            or snapshot.position.scope in seen_snapshot_scopes
            or snapshot.position.scope.broker != scope.broker
            or snapshot.position.scope.environment != scope.environment
            or snapshot.position.scope.account != scope.account
        ):
            raise ValueError("compact venue execution snapshot is duplicated or spliced")
        seen_snapshot_scopes.add(snapshot.position.scope)
        binding_order, binding_by_scope = _upsert_binding_value(
            binding_order,
            binding_by_scope,
            _execution_binding_for_snapshot(snapshot),
        )
        snapshot_by_scope = _upsert_execution_snapshot_value(
            snapshot_by_scope,
            snapshot,
        )

    cursor_by_scope = base._protection_cursor_by_scope
    seen_cursor_scopes: set[PositionScope] = set()
    for position_scope, cursor in protection_cursors:
        retained_snapshot = snapshot_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        if (
            type(position_scope) is not PositionScope
            or type(cursor) is not _ProtectionCursor
            or position_scope in seen_cursor_scopes
            or position_scope.broker != scope.broker
            or position_scope.environment != scope.environment
            or position_scope.account != scope.account
            or (
                cursor.execution_checkpoint is not None
                and (
                    retained_snapshot is None
                    or cursor.execution_commitment != retained_snapshot.commitment
                    or cursor.execution_checkpoint
                    != VenueExecutionCheckpoint.from_execution(retained_snapshot)
                )
            )
        ):
            raise ValueError("compact venue protection cursor is duplicated or spliced")
        seen_cursor_scopes.add(position_scope)
        cursor_by_scope = _set_protection_cursor(
            cursor_by_scope,
            position_scope,
            cursor,
        )

    replacements: dict[str, object] = {
        "_effect_order": effect_order,
        "_effect_by_id": effect_by_id,
        "_effect_by_request_occurrence": effect_by_request,
        "_effect_by_client_order": effect_by_client,
        "_authority_epoch_by_scope": authority_epoch_by_scope,
        "_account_authority_epoch": account_authority_epoch,
        "_contradiction_order_by_effect": contradiction_by_effect,
        "_claim_order": claim_order,
        "_claim_by_effect": claim_by_effect,
        "_claim_by_occurrence": claim_by_occurrence,
        "_unresolved_account_execution_reconciliation_count": (
            unresolved_account_execution_reconciliation_count
        ),
        "execution_registry_count": execution_registry_count,
        "execution_registry_commitment": execution_registry_commitment,
        "_registry_transition_head_commitment": (
            registry_transition_head_commitment
        ),
        "_binding_order": binding_order,
        "_binding_by_scope": binding_by_scope,
        "_execution_snapshot_by_scope": snapshot_by_scope,
        "_protection_cursor_by_scope": cursor_by_scope,
    }
    result = object.__new__(VenueRecoveryBook)
    for book_field in fields(base):
        object.__setattr__(
            result,
            book_field.name,
            replacements.get(book_field.name, getattr(base, book_field.name)),
        )
    (
        contributions,
        summaries,
        unclaimed,
    ) = _rebuild_authority_indexes(result)
    object.__setattr__(result, "_authority_contribution_by_effect", contributions)
    object.__setattr__(result, "_authority_summary_by_scope", summaries)
    object.__setattr__(result, "_account_unclaimed_requested_effect_ids", unclaimed)
    object.__setattr__(
        result,
        "_cancel_target_reservation_by_leg",
        _rebuild_cancel_target_reservations(result),
    )
    return result


def _protection_book_commitment(book: VenueRecoveryBook) -> bytes:
    """Commit compact book roots while excluding derived protection proofs.

    Legacy map-empty books retain their v1 commitment exactly.  R8 bootstrap
    checkpoints use a domain-separated v2 envelope which commits the static
    bootstrap-record map root before that record's neutral proof is minted.
    """

    if type(book) is not VenueRecoveryBook:
        raise TypeError("protection book commitment requires VenueRecoveryBook")
    parts: list[bytes] = []
    for retained in fields(book):
        if retained.name in {
            "_protection_cursor_by_scope",
            "_protection_transition_ledger",
            "_bootstrap_bound_target_by_scope",
        }:
            continue
        value = getattr(book, retained.name)
        parts.append(_encode_text(retained.name))
        if retained.name in {
            "scope",
            "_account_authority_epoch",
            "_account_unclaimed_requested_effect_ids",
            "_registry_transition_head_commitment",
            "_unresolved_account_execution_reconciliation_count",
            "execution_registry_count",
            "execution_registry_commitment",
        }:
            parts.append(_canonical_value_commitment(value))
        else:
            parts.append(value.commitment)
    legacy = _commit_parts(b"execution-core/protection-book-envelope/v1", *parts)
    bootstrap_records = book._bootstrap_bound_target_by_scope
    if bootstrap_records.size == 0:
        return legacy
    return _commit_parts(
        b"execution-core/protection-book-envelope/bootstrap/v2",
        legacy,
        bootstrap_records.commitment,
    )


def _protection_position_scope(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> PositionScope:
    if type(item) in {
        CatchUpExecutionRegistry,
        _BrokerExecutionRegistryCatchUp,
    }:
        return cast(
            CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
            item,
        ).target_scope
    if type(item) is RequestedEffect:
        return PositionScope(
            broker=book.scope.broker,
            environment=book.scope.environment,
            account=book.scope.account,
            symbol_id=item.symbol_id,
        )
    effect_id = getattr(item, "effect_id", None)
    effect = book._current_effect(effect_id) if type(effect_id) is EffectId else None
    if effect is not None:
        return effect.scope.position_scope
    leg_key = getattr(item, "leg_key", None)
    owner = book.owner(leg_key) if type(leg_key) is VenueLegKey else None
    if owner is not None:
        owned_effect = book._current_effect(owner.effect_id)
        if owned_effect is not None:
            return owned_effect.scope.position_scope
    return execution.position.scope


def _protection_mandate_id(
    book: VenueRecoveryBook,
    item: object,
) -> MandateId | None:
    if type(item) is RequestedEffect:
        return item.mandate_id
    effect_id = getattr(item, "effect_id", None)
    effect = book._current_effect(effect_id) if type(effect_id) is EffectId else None
    if effect is not None:
        return effect.scope.mandate_id
    leg_key = getattr(item, "leg_key", None)
    owner = book.owner(leg_key) if type(leg_key) is VenueLegKey else None
    if owner is not None:
        owned_effect = book._current_effect(owner.effect_id)
        if owned_effect is not None:
            return owned_effect.scope.mandate_id
    return None


def _protection_scope_values(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
) -> tuple[
    _SymbolAuthoritySummary,
    VenueExecutionBinding | None,
    _ProtectionCursor,
    bool,
    bool,
]:
    scope_key = _position_scope_index_key(position_scope)
    summary = (
        book._authority_summary_by_scope.get(scope_key) or _SymbolAuthoritySummary()
    )
    binding = book._binding_by_scope.get(scope_key)
    cursor = (
        book._protection_cursor_by_scope.get(scope_key) or _protection_genesis_cursor()
    )
    view = _venue_authority_view(book, execution, position_scope, None)
    return (
        summary,
        binding,
        cursor,
        view.execution_binding_matches,
        view.account_reconciliation_clear,
    )


def _m2_current_protection_scope_values(
    book: object,
    execution: object,
    position_scope: object,
) -> tuple[
    _SymbolAuthoritySummary,
    VenueExecutionBinding | None,
    _ProtectionCursor,
    bool,
    bool,
]:
    """Return one bounded owner-validated current projection for protection."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be exact VenueRecoveryBook")
    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be exact ExecutionSnapshot")
    if type(position_scope) is not PositionScope:
        raise TypeError("position_scope must be exact PositionScope")
    exact_book = cast(VenueRecoveryBook, book)
    exact_execution = cast(ExecutionSnapshot, execution)
    exact_scope = cast(PositionScope, position_scope)
    context = exact_book.project_acquisition_context(exact_execution, exact_scope)
    values = _protection_scope_values(exact_book, exact_execution, exact_scope)
    cursor = values[2]
    if (
        not context.matches_current(
            exact_book,
            exact_execution,
            exact_book.scope.generation,
            exact_scope,
        )
        or context._source_protection_cursor_ordinal != cursor.ordinal
        or context._source_protection_cursor_head != cursor.head
    ):
        raise ValueError("current venue protection projection is not exact")
    return values


def _set_protection_cursor(
    retained: _PersistentKeyMap[_ProtectionCursor],
    position_scope: PositionScope,
    cursor: _ProtectionCursor,
) -> _PersistentKeyMap[_ProtectionCursor]:
    scope_key = _position_scope_index_key(position_scope)
    if retained.get(scope_key) is None:
        return retained.insert_new(scope_key, cursor, cursor.commitment)
    return retained.replace_existing(scope_key, cursor, cursor.commitment)


def _with_protection_cursor(
    book: VenueRecoveryBook,
    position_scope: PositionScope,
    cursor: _ProtectionCursor,
    proof: _ProtectionTransitionProof,
) -> VenueRecoveryBook:
    if (
        type(proof) is not _ProtectionTransitionProof
        or proof.position_scope != position_scope
        or proof.cursor != cursor
        or proof.predecessor_cursor == cursor
        or not proof.lineage_is_authentic
    ):
        raise ValueError("protection cursor requires its exact advancing proof")
    cursor_by_scope = _set_protection_cursor(
        book._protection_cursor_by_scope,
        position_scope,
        cursor,
    )
    transition_ledger = book._protection_transition_ledger.append(
        proof,
        proof.commitment,
    )
    result = object.__new__(VenueRecoveryBook)
    for retained in fields(book):
        value: object
        if retained.name == "_protection_cursor_by_scope":
            value = cursor_by_scope
        elif retained.name == "_protection_transition_ledger":
            value = transition_ledger
        else:
            value = getattr(book, retained.name)
        object.__setattr__(result, retained.name, value)
    return result


def _authority_protection_cursor_matches_mandate(
    book: VenueRecoveryBook,
    position_scope: PositionScope,
    expected_mandate_id: MandateId | None,
) -> bool:
    """Check one direct scope cursor without exposing or scanning its index."""

    if (
        type(book) is not VenueRecoveryBook
        or type(position_scope) is not PositionScope
        or (
            expected_mandate_id is not None
            and type(expected_mandate_id) is not MandateId
        )
    ):
        return False
    cursor = book._protection_cursor_by_scope.get(
        _position_scope_index_key(position_scope)
    )
    if cursor is None:
        return True
    if type(cursor) is not _ProtectionCursor:
        return False
    return bool(
        expected_mandate_id is None
        or cursor.mandate_id is None
        or cursor.mandate_id == expected_mandate_id
    )


def _authority_rollover_acquisition_protection_cursor(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
    predecessor_mandate_id: MandateId,
    successor_mandate_id: MandateId,
    registration_commitment: bytes,
) -> VenueRecoveryTransition | None:
    """Mint one zero-economic completed-successor cursor transition."""

    if (
        type(book) is not VenueRecoveryBook
        or type(execution) is not ExecutionSnapshot
        or type(position_scope) is not PositionScope
        or type(predecessor_mandate_id) is not MandateId
        or type(successor_mandate_id) is not MandateId
        or predecessor_mandate_id == successor_mandate_id
        or type(registration_commitment) is not bytes
        or len(registration_commitment) != 32
        or execution.position.scope != position_scope
        or execution.position.raw_quantity != 0
        or execution.integrity is not PositionIntegrity.CONSISTENT
        or execution.account_reconciliation_required
        or not book._execution_pair_matches_fast(execution)
    ):
        return None
    (
        summary,
        binding,
        predecessor_cursor,
        binding_matches,
        reconciliation_clear,
    ) = _protection_scope_values(book, execution, position_scope)
    view = _venue_authority_view(book, execution, position_scope, None)
    execution_checkpoint = VenueExecutionCheckpoint.from_execution(execution)
    if not (
        predecessor_cursor.mandate_id == predecessor_mandate_id
        and predecessor_cursor.execution_commitment == execution.commitment
        and predecessor_cursor.execution_checkpoint == execution_checkpoint
        and binding is not None
        and binding.position_scope == position_scope
        and binding_matches
        and reconciliation_clear
        and view.execution_binding_matches
        and view.account_reconciliation_clear
        and view.blocking_effect_count == 0
        and view.blocking_buy_effect_count == 0
        and view.known_cancellable_buy_leg_count == 0
        and view.known_cancel_pending_buy_leg_count == 0
        and view.waiting_buy_parent_count == 0
        and view.unknown_buy_effect_count == 0
    ):
        return None
    book_commitment = _protection_book_commitment(book)
    command_commitment = _serial_successor_rollover_command_commitment(
        position_scope,
        predecessor_mandate_id,
        successor_mandate_id,
        registration_commitment,
    )
    cursor = _next_protection_cursor(
        predecessor_cursor,
        position_scope,
        successor_mandate_id,
        book.scope,
        book.scope,
        book_commitment,
        book_commitment,
        execution.commitment,
        execution.commitment,
        execution_checkpoint,
        execution_checkpoint,
        summary,
        summary,
        binding,
        binding,
        binding_matches,
        binding_matches,
        reconciliation_clear,
        reconciliation_clear,
        command_commitment,
        VenueRecoveryDisposition.APPLIED,
        0,
        _ProtectionTransitionSourceKind.SERIAL_SUCCESSOR_ROLLOVER,
        registration_commitment,
    )
    proof = _ProtectionTransitionProof(
        position_scope=position_scope,
        predecessor_cursor=predecessor_cursor,
        cursor=cursor,
        predecessor_book_scope=book.scope,
        book_scope=book.scope,
        predecessor_book_commitment=book_commitment,
        book_commitment=book_commitment,
        predecessor_execution_commitment=execution.commitment,
        execution_commitment=execution.commitment,
        predecessor_execution_checkpoint=execution_checkpoint,
        execution_checkpoint=execution_checkpoint,
        predecessor_summary=summary,
        summary=summary,
        predecessor_binding=binding,
        binding=binding,
        predecessor_execution_binding_matches=binding_matches,
        execution_binding_matches=binding_matches,
        predecessor_account_reconciliation_clear=reconciliation_clear,
        account_reconciliation_clear=reconciliation_clear,
        command_commitment=command_commitment,
        disposition=VenueRecoveryDisposition.APPLIED,
        quantity_delta=0,
        source_kind=_ProtectionTransitionSourceKind.SERIAL_SUCCESSOR_ROLLOVER,
        source_binding=registration_commitment,
    )
    try:
        resulting_book = _with_protection_cursor(
            book,
            position_scope,
            cursor,
            proof,
        )
    except (TypeError, ValueError):
        return None
    resulting_cursor = resulting_book._protection_cursor_by_scope.get(
        _position_scope_index_key(position_scope)
    )
    if not (
        resulting_book._execution_pair_matches_fast(execution)
        and type(resulting_cursor) is _ProtectionCursor
        and resulting_cursor.mandate_id == successor_mandate_id
    ):
        return None
    result = object.__new__(VenueRecoveryTransition)
    object.__setattr__(result, "book", resulting_book)
    object.__setattr__(result, "execution", execution)
    object.__setattr__(result, "disposition", VenueRecoveryDisposition.APPLIED)
    object.__setattr__(result, "quantity_delta", 0)
    object.__setattr__(result, "_source_item", None)
    object.__setattr__(result, "_protection_proof", proof)
    object.__setattr__(result, "_protection_proof_commitment", proof.commitment)
    object.__setattr__(result, "_acquisition_fact_proof", None)
    object.__setattr__(result, "_acquisition_fact_proof_commitment", None)
    return result


def _with_execution_snapshot_index(
    book: VenueRecoveryBook,
    snapshots: _PersistentKeyMap[ExecutionSnapshot],
) -> VenueRecoveryBook:
    """Replace only the private snapshot index on an immutable book."""

    if type(snapshots) is not type(_PersistentKeyMap.empty()):
        raise TypeError("execution snapshot index must be a persistent key map")
    result = object.__new__(VenueRecoveryBook)
    for retained in fields(book):
        value = (
            snapshots
            if retained.name == "_execution_snapshot_by_scope"
            else getattr(book, retained.name)
        )
        object.__setattr__(result, retained.name, value)
    return result


def _bootstrap_record_map_value_commitment(map_seal: bytes) -> bytes:
    _require_digest("bootstrap record map seal", map_seal)
    return _commit_parts(
        b"execution-core/bootstrap-bound-target-index-value/v1",
        map_seal,
    )


def _bootstrap_record_value_commitment(record: object) -> bytes:
    """Commit an active, staged, or permanently consumed record."""

    if _bootstrap_bound_target_record_is_authentic(record):
        return _bootstrap_record_map_value_commitment(
            cast(_BootstrapBoundTargetRecord, record)._map_seal
        )
    if _staged_bootstrap_bound_target_record_is_authentic(record):
        return _bootstrap_record_map_value_commitment(
            cast(_StagedBootstrapBoundTargetRecord, record)._map_seal
        )
    if _consumed_bootstrap_bound_target_record_is_authentic(record):
        return _bootstrap_record_map_value_commitment(
            cast(_ConsumedBootstrapBoundTargetRecord, record).commitment
        )
    raise TypeError("bootstrap target record must be exact and sealed")


def _copy_book_with_bootstrap_values(
    book: VenueRecoveryBook,
    **replacements: object,
) -> VenueRecoveryBook:
    """Copy only the narrow private checkpoint roots owned by bootstrap."""

    allowed = {
        "execution_registry_count",
        "execution_registry_commitment",
        "_binding_order",
        "_binding_by_scope",
        "_execution_snapshot_by_scope",
        "_bootstrap_bound_target_by_scope",
        "_input_ledger",
        "_input_by_id",
        "_direct_input_by_semantic",
        "_first_input_by_fact",
    }
    unknown = set(replacements) - allowed
    if unknown:
        raise TypeError(f"unsupported bootstrap checkpoint fields: {sorted(unknown)!r}")
    result = object.__new__(VenueRecoveryBook)
    for retained in fields(book):
        object.__setattr__(
            result,
            retained.name,
            replacements.get(retained.name, getattr(book, retained.name)),
        )
    return result


def _book_with_bootstrap_target_checkpoint(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: _BootstrapTargetRegistryInput,
) -> tuple[VenueRecoveryBook, VenueExecutionBinding]:
    """Install the pre-proof target roots for the private bootstrap reducer."""

    if (
        type(book) is not VenueRecoveryBook
        or type(execution) is not ExecutionSnapshot
        or not _bootstrap_target_registry_input_is_authentic(item)
    ):
        raise TypeError("bootstrap checkpoint requires exact venue-owned inputs")
    position_scope = item.position_scope
    scope_key = _position_scope_index_key(position_scope)
    if (
        execution.position.scope != position_scope
        or book.execution_binding(position_scope) is not None
        or book._execution_snapshot_by_scope.get(scope_key) is not None
        or book._bootstrap_bound_target_by_scope.get(scope_key) is not None
        or book._input_record(item.input_id) is not None
        or execution.seen_facts.count != item.prior_account_registry_count
        or execution.seen_facts.commitment != item.prior_account_registry_commitment
        or execution.reconciliation_transition_count
        != item.reconciliation_transition_count
        or execution.reconciliation_transition_head
        != item.reconciliation_transition_head
    ):
        raise ValueError("bootstrap checkpoint contradicts its exact target boundary")
    binding = VenueExecutionBinding(
        position_scope=position_scope,
        position_commitment=execution.position.commitment,
        root_heads_commitment=execution.root_heads.commitment,
        integrity_bits=execution.integrity.value,
    )
    binding_order, binding_by_scope = _upsert_binding_value(
        book._binding_order,
        book._binding_by_scope,
        binding,
    )
    snapshots = _upsert_execution_snapshot_value(
        book._execution_snapshot_by_scope,
        execution,
    )
    (
        input_ledger,
        input_by_id,
        direct_inputs,
        first_inputs,
    ) = _append_input_proof(book, item)
    return (
        _copy_book_with_bootstrap_values(
            book,
            execution_registry_count=execution.seen_facts.count,
            execution_registry_commitment=execution.seen_facts.commitment,
            _binding_order=binding_order,
            _binding_by_scope=binding_by_scope,
            _execution_snapshot_by_scope=snapshots,
            _input_ledger=input_ledger,
            _input_by_id=input_by_id,
            _direct_input_by_semantic=direct_inputs,
            _first_input_by_fact=first_inputs,
        ),
        binding,
    )


def _book_with_bootstrap_bound_target_record(
    book: VenueRecoveryBook,
    record: _BootstrapBoundTargetRecord,
) -> VenueRecoveryBook:
    """Finalize one staged bootstrap record without changing its map root."""

    if type(
        book
    ) is not VenueRecoveryBook or not _bootstrap_bound_target_record_is_authentic(
        record
    ):
        raise TypeError("bootstrap target record requires exact owner values")
    key = _position_scope_index_key(record.position_scope)
    retained = book._bootstrap_bound_target_by_scope
    staged = retained.get(key)
    if staged is None:
        retained = retained.insert_new(
            key,
            record,
            _bootstrap_record_value_commitment(record),
        )
    elif type(staged) is bytes and staged == record._map_seal:
        retained = retained.replace_existing(
            key,
            record,
            _bootstrap_record_value_commitment(record),
        )
    else:
        raise ValueError("bootstrap target record already exists for this scope")
    return _copy_book_with_bootstrap_values(
        book,
        _bootstrap_bound_target_by_scope=retained,
    )


def _consume_bootstrap_bound_target_record(
    book: VenueRecoveryBook,
    effect: BrokerEffect,
    request_input_id: VenueInputId,
) -> _PersistentKeyMap[_BootstrapBoundTargetValue]:
    """Replace one active bootstrap record with its non-serving proof record."""

    if (
        type(book) is not VenueRecoveryBook
        or type(effect) is not BrokerEffect
        or type(request_input_id) is not VenueInputId
    ):
        raise TypeError("bootstrap consumption requires exact venue-owned inputs")
    scope = effect.scope.position_scope
    key = _position_scope_index_key(scope)
    active = book._bootstrap_bound_target_by_scope.get(key)
    if not _bootstrap_bound_target_record_is_authentic(active):
        raise ValueError("bootstrap consumption requires one active target record")
    active = cast(_BootstrapBoundTargetRecord, active)
    consumed = _new_consumed_bootstrap_bound_target_record(
        active_record=active,
        effect=effect,
        request_input_id=request_input_id,
    )
    return book._bootstrap_bound_target_by_scope.replace_existing(
        key,
        consumed,
        _bootstrap_record_value_commitment(consumed),
    )


def _book_with_staged_bootstrap_refresh(
    book: VenueRecoveryBook,
    target_execution: ExecutionSnapshot,
    binding: VenueExecutionBinding,
    catch_up: CatchUpExecutionRegistry,
) -> VenueRecoveryBook:
    """Stage the next sealed checkpoint during one ordinary registry catch-up."""

    if (
        type(book) is not VenueRecoveryBook
        or type(target_execution) is not ExecutionSnapshot
        or type(binding) is not VenueExecutionBinding
        or type(catch_up) is not CatchUpExecutionRegistry
    ):
        raise TypeError("bootstrap refresh staging requires exact venue-owned values")
    key = _position_scope_index_key(target_execution.position.scope)
    active = book._bootstrap_bound_target_by_scope.get(key)
    if not _bootstrap_bound_target_record_is_authentic(active):
        raise ValueError("bootstrap refresh requires one active target record")
    active = cast(_BootstrapBoundTargetRecord, active)
    staged = _new_staged_bootstrap_bound_target_record(
        active_record=active,
        target_execution=target_execution,
        binding=binding,
        catch_up=catch_up,
    )
    retained = book._bootstrap_bound_target_by_scope.replace_existing(
        key,
        staged,
        _bootstrap_record_value_commitment(staged),
    )
    return _copy_book_with_bootstrap_values(
        book,
        _bootstrap_bound_target_by_scope=retained,
    )


def _finalize_staged_bootstrap_refresh(
    book: VenueRecoveryBook,
    target_execution: ExecutionSnapshot,
    proof: _ProtectionTransitionProof,
) -> VenueRecoveryBook:
    """Replace one staged map value with its exact standard transition proof."""

    if (
        type(book) is not VenueRecoveryBook
        or type(target_execution) is not ExecutionSnapshot
        or not _protection_transition_proof_is_authentic(proof)
    ):
        raise TypeError("bootstrap refresh finalization requires exact owner values")
    scope = target_execution.position.scope
    key = _position_scope_index_key(scope)
    staged = book._bootstrap_bound_target_by_scope.get(key)
    if not _staged_bootstrap_bound_target_record_is_authentic(staged):
        raise ValueError("bootstrap refresh finalization requires one staged record")
    staged = cast(_StagedBootstrapBoundTargetRecord, staged)
    active = staged.active_record
    bootstrap_input_record = book._input_record(active.bootstrap_input_id)
    bootstrap_input = (
        bootstrap_input_record.item
        if type(bootstrap_input_record) is VenueInputRecord
        else None
    )
    checkpoint_input_record = book._input_record(staged.checkpoint_input_id)
    checkpoint_input = (
        checkpoint_input_record.item
        if type(checkpoint_input_record) is VenueInputRecord
        else None
    )
    cursor = book._protection_cursor_by_scope.get(key)
    if (
        type(bootstrap_input) is not _BootstrapTargetRegistryInput
        or not _bootstrap_target_registry_input_is_authentic(bootstrap_input)
        or bootstrap_input.input_id != active.bootstrap_input_id
        or bootstrap_input.commitment != active.bootstrap_input_commitment
        or type(checkpoint_input) is not CatchUpExecutionRegistry
        or checkpoint_input.input_id != staged.checkpoint_input_id
        or _protection_command_commitment(checkpoint_input)
        != staged.checkpoint_command_commitment
        or proof.position_scope != scope
        or proof.cursor != cursor
        or proof.execution_commitment != target_execution.commitment
        or proof.execution_checkpoint
        != VenueExecutionCheckpoint.from_execution(target_execution)
        or proof.binding != active.binding
        or proof.command_commitment != staged.checkpoint_command_commitment
        or proof.disposition is not VenueRecoveryDisposition.APPLIED
        or proof.quantity_delta != 0
        or proof.book_commitment != _protection_book_commitment(book)
    ):
        raise ValueError("bootstrap refresh proof contradicts its staged checkpoint")
    record = _new_bootstrap_bound_target_record(
        application_generation_id=active.application_generation_id,
        position_scope=active.position_scope,
        source_kind=active.source_kind,
        source_execution_commitment=active.source_execution_commitment,
        target_genesis_execution_commitment=(
            active.target_genesis_execution_commitment
        ),
        target_execution_commitment=target_execution.commitment,
        binding=active.binding,
        account_registry_count=target_execution.seen_facts.count,
        account_registry_commitment=target_execution.seen_facts.commitment,
        reconciliation_transition_count=(
            target_execution.reconciliation_transition_count
        ),
        reconciliation_transition_head=target_execution.reconciliation_transition_head,
        bootstrap_input=bootstrap_input,
        neutral_checkpoint_proof=proof,
        bootstrap_neutral_checkpoint_proof=(active._bootstrap_neutral_checkpoint_proof),
        checkpoint_input_id=staged.checkpoint_input_id,
        checkpoint_command_commitment=staged.checkpoint_command_commitment,
    )
    if record._map_seal != staged._map_seal:
        raise ValueError("bootstrap refresh changed its staged map root")
    retained = book._bootstrap_bound_target_by_scope.replace_existing(
        key,
        record,
        _bootstrap_record_value_commitment(record),
    )
    return _copy_book_with_bootstrap_values(
        book,
        _bootstrap_bound_target_by_scope=retained,
    )


def _book_with_staged_bootstrap_record_map_seal(
    book: VenueRecoveryBook,
    position_scope: PositionScope,
    map_seal: bytes,
) -> VenueRecoveryBook:
    """Stage one proof-independent record core for the internal R8 transaction."""

    if type(book) is not VenueRecoveryBook or type(position_scope) is not PositionScope:
        raise TypeError("bootstrap record staging requires exact venue-owned inputs")
    _require_digest("bootstrap record map seal", map_seal)
    key = _position_scope_index_key(position_scope)
    retained = book._bootstrap_bound_target_by_scope
    if retained.get(key) is not None:
        raise ValueError("bootstrap target record already exists for this scope")
    retained = retained.insert_new(
        key,
        map_seal,
        _bootstrap_record_map_value_commitment(map_seal),
    )
    return _copy_book_with_bootstrap_values(
        book,
        _bootstrap_bound_target_by_scope=retained,
    )


def _protection_command_commitment(item: object) -> bytes:
    return _commit_parts(
        b"execution-core/protection-command/v1",
        *_input_command_identity(item, include_input_id=True),
    )


def _serial_successor_rollover_command_commitment(
    position_scope: PositionScope,
    predecessor_mandate_id: MandateId,
    successor_mandate_id: MandateId,
    registration_commitment: bytes,
) -> bytes:
    """Bind one venue-local cursor rollover to its authority registration."""

    if (
        type(position_scope) is not PositionScope
        or type(predecessor_mandate_id) is not MandateId
        or type(successor_mandate_id) is not MandateId
        or predecessor_mandate_id == successor_mandate_id
    ):
        raise TypeError("serial successor rollover requires distinct exact mandates")
    _require_digest("successor registration commitment", registration_commitment)
    return _commit_parts(
        b"execution-core/protection-cursor/serial-successor-rollover/v1",
        _position_scope_index_key(position_scope),
        _canonical_value_commitment(predecessor_mandate_id),
        _canonical_value_commitment(successor_mandate_id),
        registration_commitment,
    )


def _next_protection_cursor(
    predecessor: _ProtectionCursor,
    position_scope: PositionScope,
    mandate_id: MandateId | None,
    predecessor_book_scope: VenueScope,
    book_scope: VenueScope,
    predecessor_book_commitment: bytes,
    book_commitment: bytes,
    predecessor_execution_commitment: bytes,
    execution_commitment: bytes,
    predecessor_execution_checkpoint: VenueExecutionCheckpoint,
    execution_checkpoint: VenueExecutionCheckpoint,
    predecessor_summary: _SymbolAuthoritySummary,
    summary: _SymbolAuthoritySummary,
    predecessor_binding: VenueExecutionBinding | None,
    binding: VenueExecutionBinding | None,
    predecessor_execution_binding_matches: bool,
    execution_binding_matches: bool,
    predecessor_account_reconciliation_clear: bool,
    account_reconciliation_clear: bool,
    command_commitment: bytes,
    disposition: VenueRecoveryDisposition,
    quantity_delta: int,
    source_kind: _ProtectionTransitionSourceKind = (
        _ProtectionTransitionSourceKind.ORDINARY
    ),
    source_binding: bytes = _ORDINARY_PROTECTION_TRANSITION_SOURCE_BINDING,
) -> _ProtectionCursor:
    return _ProtectionCursor(
        ordinal=predecessor.ordinal + 1,
        head=_commit_parts(
            b"execution-core/protection-cursor-head/v2",
            predecessor.commitment,
            _canonical_value_commitment(position_scope),
            _canonical_value_commitment(mandate_id),
            _canonical_value_commitment(predecessor_book_scope),
            _canonical_value_commitment(book_scope),
            predecessor_book_commitment,
            book_commitment,
            predecessor_execution_commitment,
            execution_commitment,
            _canonical_value_commitment(predecessor_execution_checkpoint),
            _canonical_value_commitment(execution_checkpoint),
            _canonical_value_commitment(predecessor_summary),
            _canonical_value_commitment(summary),
            _canonical_value_commitment(predecessor_binding),
            _canonical_value_commitment(binding),
            _canonical_value_commitment(predecessor_execution_binding_matches),
            _canonical_value_commitment(execution_binding_matches),
            _canonical_value_commitment(predecessor_account_reconciliation_clear),
            _canonical_value_commitment(account_reconciliation_clear),
            command_commitment,
            _canonical_value_commitment(disposition),
            _canonical_value_commitment(quantity_delta),
            _canonical_value_commitment(source_kind),
            _canonical_value_commitment(source_binding),
        ),
        mandate_id=mandate_id,
        execution_commitment=execution_commitment,
        execution_checkpoint=execution_checkpoint,
    )


def _m2_venue_transition_source_item(
    transition: object,
) -> object | None:
    """Return the exact owner input only for a complete authentic transition."""

    if type(transition) is not VenueRecoveryTransition:
        raise TypeError("venue transition must be exact")
    exact = cast(VenueRecoveryTransition, transition)
    proof = exact._protection_proof
    if (
        not _protection_transition_proof_is_authentic(proof)
        or exact._protection_proof_commitment != proof.commitment
        or exact.disposition is not proof.disposition
        or exact.quantity_delta != proof.quantity_delta
        or proof.book_commitment != _protection_book_commitment(exact.book)
        or proof.execution_commitment != exact.execution.commitment
    ):
        raise ValueError("venue transition proof is not current")
    source = exact._source_item
    if source is None:
        if (
            proof.source_kind
            is not _ProtectionTransitionSourceKind.SERIAL_SUCCESSOR_ROLLOVER
        ):
            raise ValueError("ordinary venue transition omitted its exact source")
        return None
    if _protection_command_commitment(source) != proof.command_commitment:
        raise ValueError("venue transition source does not match its proof")
    return source


@dataclass(frozen=True, slots=True)
class _M2AcceptanceClosurePersistence:
    """Exact relational projection of one owner-authenticated acceptance closure."""

    effect_id: EffectId
    claim_occurrence_id: ClaimOccurrenceId | None
    proof_kind: str
    evidence_digest: bytes

    def __post_init__(self) -> None:
        _require("effect_id", self.effect_id, EffectId)
        if self.claim_occurrence_id is not None:
            _require(
                "claim_occurrence_id",
                self.claim_occurrence_id,
                ClaimOccurrenceId,
            )
        if type(self.proof_kind) is not str or not self.proof_kind:
            raise TypeError("acceptance closure proof kind must be exact text")
        if type(self.evidence_digest) is not bytes or len(self.evidence_digest) != 32:
            raise ValueError("acceptance closure evidence digest must be exact")


def _m2_venue_transition_acceptance_closure(
    transition: object,
) -> _M2AcceptanceClosurePersistence | None:
    """Project raw closure authority without exporting its reducer command type."""

    source = _m2_venue_transition_source_item(transition)
    if type(source) is not CloseAcceptanceSet:
        return None
    closure = cast(CloseAcceptanceSet, source)
    return _M2AcceptanceClosurePersistence(
        closure.effect_id,
        closure.proof.claim_occurrence_id,
        closure.proof.kind.value,
        closure.proof.evidence_digest,
    )


def _protection_transition_proof_is_authentic(
    proof: _ProtectionTransitionProof,
) -> bool:
    """Re-derive one bounded protection cursor from its complete proof envelope."""

    if type(proof) is not _ProtectionTransitionProof:
        return False
    if type(proof.position_scope) is not PositionScope:
        return False
    if type(proof.predecessor_cursor) is not _ProtectionCursor:
        return False
    if type(proof.cursor) is not _ProtectionCursor:
        return False
    if type(proof.predecessor_book_scope) is not VenueScope:
        return False
    if type(proof.book_scope) is not VenueScope:
        return False
    if type(proof.predecessor_execution_checkpoint) is not VenueExecutionCheckpoint:
        return False
    if type(proof.execution_checkpoint) is not VenueExecutionCheckpoint:
        return False
    if type(proof.predecessor_summary) is not _SymbolAuthoritySummary:
        return False
    if type(proof.summary) is not _SymbolAuthoritySummary:
        return False
    if (
        proof.predecessor_binding is not None
        and type(proof.predecessor_binding) is not VenueExecutionBinding
    ):
        return False
    if proof.binding is not None and type(proof.binding) is not VenueExecutionBinding:
        return False
    for digest in (
        proof.predecessor_book_commitment,
        proof.book_commitment,
        proof.predecessor_execution_commitment,
        proof.execution_commitment,
        proof.command_commitment,
    ):
        if type(digest) is not bytes or len(digest) != 32:
            return False
    for flag in (
        proof.predecessor_execution_binding_matches,
        proof.execution_binding_matches,
        proof.predecessor_account_reconciliation_clear,
        proof.account_reconciliation_clear,
    ):
        if type(flag) is not bool:
            return False
    if type(proof.disposition) is not VenueRecoveryDisposition:
        return False
    if type(proof.quantity_delta) is not int:
        return False
    if type(proof.source_kind) is not _ProtectionTransitionSourceKind:
        return False
    if type(proof.source_binding) is not bytes or len(proof.source_binding) != 32:
        return False
    if proof.predecessor_book_scope != proof.book_scope:
        return False
    if proof.predecessor_execution_checkpoint.position_scope != proof.position_scope:
        return False
    if proof.execution_checkpoint.position_scope != proof.position_scope:
        return False
    if (
        proof.predecessor_binding is not None
        and proof.predecessor_binding.position_scope != proof.position_scope
    ):
        return False
    if (
        proof.binding is not None
        and proof.binding.position_scope != proof.position_scope
    ):
        return False
    scope = proof.position_scope
    if (
        proof.book_scope.broker != scope.broker
        or proof.book_scope.environment != scope.environment
        or proof.book_scope.account != scope.account
    ):
        return False
    predecessor = proof.predecessor_cursor
    cursor = proof.cursor
    if predecessor.ordinal == 0:
        if predecessor != _protection_genesis_cursor():
            return False
    elif (
        predecessor.execution_commitment != proof.predecessor_execution_commitment
        or predecessor.execution_checkpoint != proof.predecessor_execution_checkpoint
    ):
        return False
    mandate_changed = bool(
        predecessor.mandate_id is not None
        and cursor.mandate_id != predecessor.mandate_id
    )
    if proof.source_kind is _ProtectionTransitionSourceKind.ORDINARY:
        if (
            proof.source_binding != _ORDINARY_PROTECTION_TRANSITION_SOURCE_BINDING
            or mandate_changed
        ):
            return False
    else:
        if not (
            mandate_changed
            and predecessor.mandate_id is not None
            and cursor.mandate_id is not None
            and proof.predecessor_book_scope == proof.book_scope
            and proof.predecessor_book_commitment == proof.book_commitment
            and proof.predecessor_execution_commitment == proof.execution_commitment
            and proof.predecessor_execution_checkpoint == proof.execution_checkpoint
            and proof.predecessor_summary == proof.summary
            and proof.predecessor_binding == proof.binding
            and proof.predecessor_execution_binding_matches
            == proof.execution_binding_matches
            and proof.predecessor_account_reconciliation_clear
            == proof.account_reconciliation_clear
            and proof.execution_binding_matches
            and proof.account_reconciliation_clear
            and proof.disposition is VenueRecoveryDisposition.APPLIED
            and proof.quantity_delta == 0
            and proof.command_commitment
            == _serial_successor_rollover_command_commitment(
                proof.position_scope,
                predecessor.mandate_id,
                cursor.mandate_id,
                proof.source_binding,
            )
        ):
            return False
    advances = cursor != predecessor
    if not advances:
        return proof.disposition is not VenueRecoveryDisposition.APPLIED
    if proof.disposition not in {
        VenueRecoveryDisposition.APPLIED,
        VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
    }:
        return False
    expected = _next_protection_cursor(
        predecessor,
        proof.position_scope,
        cursor.mandate_id,
        proof.predecessor_book_scope,
        proof.book_scope,
        proof.predecessor_book_commitment,
        proof.book_commitment,
        proof.predecessor_execution_commitment,
        proof.execution_commitment,
        proof.predecessor_execution_checkpoint,
        proof.execution_checkpoint,
        proof.predecessor_summary,
        proof.summary,
        proof.predecessor_binding,
        proof.binding,
        proof.predecessor_execution_binding_matches,
        proof.execution_binding_matches,
        proof.predecessor_account_reconciliation_clear,
        proof.account_reconciliation_clear,
        proof.command_commitment,
        proof.disposition,
        proof.quantity_delta,
        proof.source_kind,
        proof.source_binding,
    )
    return cursor == expected


def _extract_protection_transition(
    transition: VenueRecoveryTransition,
) -> tuple[
    _SymbolAuthoritySummary | None,
    VenueExecutionBinding | None,
    _ProtectionCursor | None,
]:
    scope_key = _position_scope_index_key(transition._protection_proof.position_scope)
    return (
        transition.book._authority_summary_by_scope.get(scope_key),
        transition.book._binding_by_scope.get(scope_key),
        transition.book._protection_cursor_by_scope.get(scope_key),
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


def _execution_snapshot_value_commitment(execution: ExecutionSnapshot) -> bytes:
    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution snapshot value must be exact")
    _require_execution_components(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
    )
    return _commit_parts(
        b"execution-core/venue-execution-snapshot-value/v1",
        execution.commitment,
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


def _acquisition_correlation_entry_for(
    venue_scope: VenueScope,
    effect_by_request_occurrence: _PersistentKeyMap[EffectId],
    effect_by_id: _PersistentKeyMap[_EffectCurrent],
    owner_by_leg: _PersistentKeyMap[VenueIdentityOwner],
    *,
    effect_id: EffectId,
    leg_key: VenueLegKey,
    root_key: RootFillKey,
) -> _AcquisitionCorrelationEntry:
    """Build one root entry from direct current venue indexes only."""

    _require("effect_id", effect_id, EffectId)
    _require("leg_key", leg_key, VenueLegKey)
    _require("root_key", root_key, RootFillKey)
    owner = owner_by_leg.get(_leg_index_key(leg_key))
    current = effect_by_id.get(_effect_index_key(effect_id))
    if owner is None or current is None:
        raise ValueError("acquisition correlation requires direct owner and effect")
    effect_scope = current.effect.scope
    if (
        owner.leg_key != leg_key
        or owner.effect_id != effect_id
        or owner.effect_scope != effect_scope
        or effect_by_request_occurrence.get(
            _request_occurrence_index_key(effect_scope.request_occurrence_id)
        )
        != effect_id
        or effect_scope.generation != venue_scope.generation
        or effect_scope.position_scope.broker != root_key.broker
        or effect_scope.position_scope.environment != root_key.environment
        or effect_scope.position_scope.account != root_key.account
    ):
        raise ValueError("acquisition correlation direct provenance is inconsistent")
    return _AcquisitionCorrelationEntry(
        application_generation_id=venue_scope.generation,
        position_scope=effect_scope.position_scope,
        request_occurrence_id=effect_scope.request_occurrence_id,
        effect_id=effect_id,
        leg_key=leg_key,
        root_key=root_key,
    )


def _append_acquisition_correlation(
    retained: _PersistentKeyMap[_AcquisitionCorrelationEntry],
    entry: _AcquisitionCorrelationEntry,
) -> _PersistentKeyMap[_AcquisitionCorrelationEntry]:
    if type(entry) is not _AcquisitionCorrelationEntry:
        raise TypeError("acquisition correlation entry must be exact")
    key = _coverage_root_index_key(entry.root_key)
    prior = retained.get(key)
    if prior is None:
        return retained.insert_new(key, entry, entry.commitment)
    if prior != entry:
        raise ValueError("broker root has conflicting acquisition correlation")
    return retained


def _evolve_acquisition_correlation_index(
    current: VenueRecoveryBook,
    retained: _PersistentKeyMap[_AcquisitionCorrelationEntry],
    resulting_execution: ExecutionSnapshot,
    item: object | None,
    effect_by_request_occurrence: _PersistentKeyMap[EffectId],
    effect_by_id: _PersistentKeyMap[_EffectCurrent],
    owner_by_leg: _PersistentKeyMap[VenueIdentityOwner],
) -> _PersistentKeyMap[_AcquisitionCorrelationEntry]:
    """Append an accepted broker root without touching coverage or audit history."""

    from .recovery import RecordBrokerFillEvidence

    if type(item) not in {
        RecordBrokerFillEvidence,
        _BrokerExecutionRegistryCatchUp,
    }:
        return retained
    exact_item = cast(
        RecordBrokerFillEvidence | _BrokerExecutionRegistryCatchUp,
        item,
    )
    observed = resulting_execution.seen_facts.get(exact_item.fact.key)
    if (
        observed is None
        or observed.fact != exact_item.fact
        or observed.classification
        not in {
            FirstObservationClassification.APPLIED_AVAILABLE,
            FirstObservationClassification.APPLIED_BASIS_PENDING,
            FirstObservationClassification.APPLIED_OVERFILL_QUARANTINE,
            FirstObservationClassification.APPLIED_PENDING_OVERFILL,
            FirstObservationClassification.CORROBORATED_ZERO_ECONOMIC,
        }
    ):
        return retained
    entry = _acquisition_correlation_entry_for(
        current.scope,
        effect_by_request_occurrence,
        effect_by_id,
        owner_by_leg,
        effect_id=exact_item.effect_id,
        leg_key=exact_item.leg_key,
        root_key=exact_item.fact.root_key,
    )
    return _append_acquisition_correlation(retained, entry)


def _audit_rebuild_acquisition_correlation_index(
    venue_scope: VenueScope,
    effect_by_request_occurrence: _PersistentKeyMap[EffectId],
    effect_by_id: _PersistentKeyMap[_EffectCurrent],
    owner_by_leg: _PersistentKeyMap[VenueIdentityOwner],
    human_coverages: tuple[object, ...],
    broker_coverages: tuple[object, ...],
    input_records: tuple[VenueInputRecord, ...],
    execution_reconciliations: tuple[ExecutionRegistryReconciliationRecord, ...],
    *,
    defer_invalid_provenance: bool = False,
) -> _PersistentKeyMap[_AcquisitionCorrelationEntry]:
    """Rebuild the derived direct root map only in the explicit slow audit fold."""

    from .recovery import HumanCoverage, _BrokerCoverage

    retained: _PersistentKeyMap[_AcquisitionCorrelationEntry] = (
        _PersistentKeyMap.empty()
    )

    def append_entry(
        current: _PersistentKeyMap[_AcquisitionCorrelationEntry],
        *,
        effect_id: EffectId,
        leg_key: VenueLegKey,
        root_key: RootFillKey,
    ) -> _PersistentKeyMap[_AcquisitionCorrelationEntry]:
        try:
            entry = _acquisition_correlation_entry_for(
                venue_scope,
                effect_by_request_occurrence,
                effect_by_id,
                owner_by_leg,
                effect_id=effect_id,
                leg_key=leg_key,
                root_key=root_key,
            )
        except ValueError:
            if defer_invalid_provenance:
                return current
            raise
        return _append_acquisition_correlation(current, entry)

    for coverage in broker_coverages:
        if type(coverage) is not _BrokerCoverage:
            raise TypeError("broker coverage audit value has the wrong type")
        retained = append_entry(
            retained,
            effect_id=coverage.effect_id,
            leg_key=coverage.leg_key,
            root_key=coverage.fact.root_key,
        )
    for coverage in human_coverages:
        if type(coverage) is not HumanCoverage:
            raise TypeError("human coverage audit value has the wrong type")
        if coverage.broker_corroborated and coverage.broker_fact is not None:
            retained = append_entry(
                retained,
                effect_id=coverage.effect_id,
                leg_key=coverage.leg_key,
                root_key=coverage.broker_fact.root_key,
            )
    outcomes_by_input = {
        outcome.input_id: outcome for outcome in execution_reconciliations
    }
    for record in input_records:
        if type(record.item) is not _BrokerExecutionRegistryCatchUp:
            continue
        item = cast(_BrokerExecutionRegistryCatchUp, record.item)
        outcome = outcomes_by_input.get(record.input_id)
        if (
            type(outcome) is not _AttributedRegistryAdvanceOutcome
            or outcome.fact != item.fact
            or outcome.effect_id != item.effect_id
            or outcome.leg_key != item.leg_key
        ):
            raise ValueError(
                "direct broker fact lacks its exact attributed registry outcome"
            )
        retained = append_entry(
            retained,
            effect_id=item.effect_id,
            leg_key=item.leg_key,
            root_key=item.fact.root_key,
        )
    return retained


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


def _attempt_authority_membership(
    attempt: VenueAttempt,
) -> tuple[tuple[VenueLegKey, ...], tuple[VenueLegKey, ...]]:
    if attempt.status not in {
        VenueAttemptState.WORKING,
        VenueAttemptState.PARTIALLY_FILLED,
    }:
        return (), ()
    if attempt.pending_operation is None:
        return (attempt.leg_key,), ()
    if attempt.pending_operation is PendingVenueOperation.CANCEL:
        return (), (attempt.leg_key,)
    return (), ()


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
    if type(effect) is not BrokerEffect:
        raise TypeError("effect append must be BrokerEffect (exact type required)")
    effect = _require_effect_shape(effect)
    effect_key = _effect_index_key(effect.effect_id)
    request_key = _request_occurrence_index_key(effect.scope.request_occurrence_id)
    client_key = (
        None
        if effect.scope.client_order_id is None
        else _client_order_index_key(effect.scope.client_order_id)
    )
    if (
        by_id.get(effect_key) is not None
        or by_request.get(request_key) is not None
        or (client_key is not None and by_client_order.get(client_key) is not None)
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
        (
            by_client_order
            if client_key is None
            else by_client_order.insert_new(
                client_key,
                effect.effect_id,
                id_commitment,
            )
        ),
    )


def _replace_effect_value(
    by_id: _PersistentKeyMap[_EffectCurrent],
    authority_epochs: _PersistentKeyMap[int],
    account_authority_epoch: int,
    effect: object,
) -> _PersistentKeyMap[_EffectCurrent]:
    if type(effect) is not BrokerEffect:
        raise TypeError("effect replacement must be the exact BrokerEffect type")
    effect = _require_effect_shape(effect)
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
    if type(claim) is not DispatchClaim:
        raise TypeError("claim append must be the exact DispatchClaim type")
    claim = _require_claim_shape(claim)
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
    if type(contradiction) is not AcceptanceContradiction:
        raise TypeError(
            "contradiction append must be the exact AcceptanceContradiction type"
        )
    contradiction = _require_contradiction_shape(contradiction)
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
        or type(owner_and_attempt[0]) is not VenueIdentityOwner
        or type(owner_and_attempt[1]) is not VenueAttempt
    ):
        raise TypeError("owner append must pair VenueIdentityOwner and VenueAttempt")
    owner, attempt = cast(tuple[VenueIdentityOwner, VenueAttempt], owner_and_attempt)
    owner = _require_owner_shape(owner)
    attempt = _require_attempt_shape(attempt)
    if owner.leg_key != attempt.leg_key:
        raise ValueError("owner and initial attempt must name the same leg")
    leg_key = _leg_index_key(owner.leg_key)
    if by_leg.get(leg_key) is not None or leg_current.get(leg_key) is not None:
        raise ValueError("venue leg already has an owner")
    current = _LegCurrent(attempt)
    summary = summaries.get(_effect_index_key(owner.effect_id)) or _EffectLegSummary()
    cancellable, cancel_pending = _attempt_authority_membership(attempt)
    summary = replace(
        summary,
        owner_count=summary.owner_count + 1,
        active_count=summary.active_count + 1,
        active_leg_keys=summary.active_leg_keys + (owner.leg_key,),
        known_cancellable_leg_keys=(summary.known_cancellable_leg_keys + cancellable),
        known_cancel_pending_leg_keys=(
            summary.known_cancel_pending_leg_keys + cancel_pending
        ),
    )
    return (
        order.append(owner.leg_key, _leg_value_commitment(owner.leg_key)),
        by_leg.insert_new(leg_key, owner, _owner_value_commitment(owner)),
        leg_current.insert_new(leg_key, current, current.commitment),
        _set_effect_leg_summary(summaries, owner.effect_id, summary),
    )


def _replace_attempt_value(
    retained: _PersistentKeyMap[_LegCurrent],
    owners: _PersistentKeyMap[VenueIdentityOwner],
    summaries: _PersistentKeyMap[_EffectLegSummary],
    attempt: object,
) -> tuple[_PersistentKeyMap[_LegCurrent], _PersistentKeyMap[_EffectLegSummary]]:
    if type(attempt) is not VenueAttempt:
        raise TypeError("attempt replacement must be the exact VenueAttempt type")
    attempt = _require_attempt_shape(attempt)
    key = _leg_index_key(attempt.leg_key)
    prior = retained.get(key)
    if prior is None or prior.attempt is None:
        raise ValueError("attempt replacement requires one active leg")
    owner = owners.get(key)
    if owner is None:
        raise ValueError("attempt replacement requires one retained owner")
    prior_cancellable, prior_cancel_pending = _attempt_authority_membership(
        prior.attempt
    )
    next_cancellable, next_cancel_pending = _attempt_authority_membership(attempt)
    summary = summaries.get(_effect_index_key(owner.effect_id)) or _EffectLegSummary()
    summary = replace(
        summary,
        known_cancellable_leg_keys=tuple(
            leg
            for leg in summary.known_cancellable_leg_keys
            if leg not in prior_cancellable
        )
        + next_cancellable,
        known_cancel_pending_leg_keys=tuple(
            leg
            for leg in summary.known_cancel_pending_leg_keys
            if leg not in prior_cancel_pending
        )
        + next_cancel_pending,
    )
    current = _LegCurrent(attempt)
    return (
        retained.replace_existing(key, current, current.commitment),
        _set_effect_leg_summary(summaries, owner.effect_id, summary),
    )


def _upsert_binding_value(
    order: _PersistentSequence[PositionScope],
    by_scope: _PersistentKeyMap[VenueExecutionBinding],
    binding: object,
) -> tuple[
    _PersistentSequence[PositionScope],
    _PersistentKeyMap[VenueExecutionBinding],
]:
    if type(binding) is not VenueExecutionBinding:
        raise TypeError("binding upsert must be the exact VenueExecutionBinding type")
    VenueExecutionBinding.__post_init__(binding)
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


def _upsert_execution_snapshot_value(
    retained: _PersistentKeyMap[ExecutionSnapshot],
    execution: ExecutionSnapshot,
) -> _PersistentKeyMap[ExecutionSnapshot]:
    commitment = _execution_snapshot_value_commitment(execution)
    key = _position_scope_index_key(execution.position.scope)
    if retained.get(key) is None:
        return retained.insert_new(key, execution, commitment)
    return retained.replace_existing(key, execution, commitment)


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

    if type(record) not in {ReconciliationRecord, RevisionReconciliationRecord}:
        raise TypeError(
            "reconciliation append must be a typed reconciliation record "
            "(exact type required)"
        )
    record = cast(ReconciliationRecord | RevisionReconciliationRecord, record)
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
    if type(record) is RevisionReconciliationRecord and record.canonical_applied:
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
        _AttributedRegistryAdvanceOutcome,
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
        if type(human_append) is not HumanCoverage:
            raise TypeError("human coverage append must be exact HumanCoverage")
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
        if type(prior) is not HumanCoverage or type(replacement) is not HumanCoverage:
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
        if type(broker_append) is not _BrokerCoverage:
            raise TypeError("broker coverage append must be exact _BrokerCoverage")
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
        if (
            type(prior) is not _BrokerCoverage
            or type(replacement) is not _BrokerCoverage
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
        if type(value) is not HumanCoverage:
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
        if type(value) is not _BrokerCoverage:
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
    closure = _require_closure_shape(closure)
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


def _audit_checkpoint_projection(book: VenueRecoveryBook) -> tuple[object, ...]:
    """Materialize one complete slow-path checkpoint for exact M1 reconstruction."""

    return (
        book.scope,
        book.execution_registry_count,
        book.execution_registry_commitment,
        book.effects,
        book.claims,
        book.owners,
        book.active_attempts,
        book.closure_heads,
        book.execution_bindings,
        book.closure_history,
        book.input_records,
        book.human_coverages,
        book.broker_coverages,
        book.reconciliations,
        book.execution_reconciliations,
    )


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
            _AttributedRegistryAdvanceOutcome,
        }
        for entry in execution_reconciliations
    ):
        raise TypeError("execution reconciliation entries must be exact outcome types")

    closure_ledger: _PersistentSequence[VenueTerminalClosure] = (
        _PersistentSequence.empty()
    )
    closure_by_id: _PersistentKeyMap[VenueTerminalClosure] = _PersistentKeyMap.empty()
    closure_heads_by_leg: _PersistentKeyMap[VenueTerminalClosure] = (
        _PersistentKeyMap.empty()
    )
    for closure in closure_history:
        closure = _require_closure_shape(closure)
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
        attempt = _require_attempt_shape(attempt)
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
        owner = _require_owner_shape(owner)
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
        active_attempt = active_by_leg.get(owner.leg_key)
        leg_current = _LegCurrent(active_attempt)
        leg_current_by_leg = leg_current_by_leg.insert_new(
            encoded_leg,
            leg_current,
            leg_current.commitment,
        )
        summary = (
            leg_summary_by_effect.get(_effect_index_key(owner.effect_id))
            or _EffectLegSummary()
        )
        cancellable, cancel_pending = (
            ((), ())
            if active_attempt is None
            else _attempt_authority_membership(active_attempt)
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
                active_leg_keys=(
                    summary.active_leg_keys
                    + ((owner.leg_key,) if active_attempt is not None else ())
                ),
                known_cancellable_leg_keys=(
                    summary.known_cancellable_leg_keys + cancellable
                ),
                known_cancel_pending_leg_keys=(
                    summary.known_cancel_pending_leg_keys + cancel_pending
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
        if type(binding) is not VenueExecutionBinding:
            raise TypeError(
                "execution binding must be VenueExecutionBinding (exact type required)"
            )
        VenueExecutionBinding.__post_init__(binding)
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
        record = _require_input_record_shape(record)
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
    object.__setattr__(
        result,
        "_acquisition_correlation_by_root",
        _PersistentKeyMap.empty(),
    )
    object.__setattr__(result, "_leg_current_by_leg", leg_current_by_leg)
    object.__setattr__(result, "_leg_summary_by_effect", leg_summary_by_effect)
    object.__setattr__(
        result,
        "_cancel_target_reservation_by_leg",
        _rebuild_cancel_target_reservations(result),
    )
    object.__setattr__(result, "_binding_order", binding_order)
    object.__setattr__(result, "_binding_by_scope", binding_by_scope)
    object.__setattr__(
        result,
        "_execution_snapshot_by_scope",
        book._execution_snapshot_by_scope,
    )
    object.__setattr__(
        result,
        "_bootstrap_bound_target_by_scope",
        book._bootstrap_bound_target_by_scope,
    )
    object.__setattr__(
        result,
        "_protection_cursor_by_scope",
        book._protection_cursor_by_scope,
    )
    object.__setattr__(
        result,
        "_protection_transition_ledger",
        book._protection_transition_ledger,
    )
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
    (
        authority_contribution_by_effect,
        authority_summary_by_scope,
        account_unclaimed_requested_effect_ids,
    ) = _rebuild_authority_indexes(result)
    object.__setattr__(
        result,
        "_authority_contribution_by_effect",
        authority_contribution_by_effect,
    )
    object.__setattr__(
        result,
        "_authority_summary_by_scope",
        authority_summary_by_scope,
    )
    object.__setattr__(
        result,
        "_account_unclaimed_requested_effect_ids",
        account_unclaimed_requested_effect_ids,
    )
    acquisition_correlation_by_root = _audit_rebuild_acquisition_correlation_index(
        result.scope,
        result._effect_by_request_occurrence,
        result._effect_by_id,
        result._owner_by_leg,
        result.human_coverages,
        result.broker_coverages,
        result.input_records,
        result.execution_reconciliations,
        defer_invalid_provenance=True,
    )
    object.__setattr__(
        result,
        "_acquisition_correlation_by_root",
        acquisition_correlation_by_root,
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
            if type(record.item) is _BrokerExecutionRegistryCatchUp:
                registry_outcome = result._execution_reconciliation_for_input(
                    record.input_id
                )
                observation = (
                    None
                    if source_fact is None
                    else execution.seen_facts.get(source_fact.key)
                )
                if (
                    type(registry_outcome) is _AttributedRegistryAdvanceOutcome
                    and observation is not None
                    and observation.fact == source_fact
                    and observation.classification
                    is not FirstObservationClassification.RECONCILIATION_REQUIRED
                ):
                    attributed_broker_facts.add(source_fact.key)
                continue
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
    result._validated_execution_snapshots()
    for binding in result.execution_bindings:
        retained_snapshot = result._execution_snapshot_by_scope.get(
            _position_scope_index_key(binding.position_scope)
        )
        if type(retained_snapshot) is not ExecutionSnapshot or not (
            execution.seen_facts.has_prefix(
                retained_snapshot.seen_facts.count,
                retained_snapshot.seen_facts.commitment,
            )
        ):
            raise ValueError(
                "retained execution snapshot is not an account-registry prefix"
            )
    if _audit_checkpoint_projection(result) != _audit_checkpoint_projection(book):
        raise ValueError(
            "M1 audit hydration requires an exact reconstruction of the supplied "
            "opaque checkpoint; replacement loading remains deferred"
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
        target_leg_key=item.target_leg_key,
    )


def _target_is_exact_active(
    book: VenueRecoveryBook,
    scope: VenueEffectScope,
    *,
    expected_cancel_effect_id: EffectId | None = None,
) -> bool:
    """Return whether a target-bound effect names one exact cancellable owner."""

    target_leg_key = scope.target_leg_key
    if target_leg_key is None or not _same_leg_scope(book.scope, target_leg_key):
        return False
    owner = book.owner(target_leg_key)
    attempt = book.active_attempt(target_leg_key)
    if owner is None or attempt is None or attempt.pending_operation is not None:
        return False
    active_cancel_effect_id = book._active_cancel_effect_for_target(target_leg_key)
    if scope.kind is EffectKind.CANCEL:
        if expected_cancel_effect_id is None:
            if active_cancel_effect_id is not None:
                return False
        elif active_cancel_effect_id != expected_cancel_effect_id:
            return False
    elif active_cancel_effect_id is not None:
        return False
    target = book._current_effect(owner.effect_id)
    return bool(
        target is not None
        and target.state is BrokerEffectState.ACKNOWLEDGED
        and attempt.status
        in {VenueAttemptState.WORKING, VenueAttemptState.PARTIALLY_FILLED}
        and target.scope.symbol_id == scope.symbol_id
        and target.scope.side is scope.side
        and target.scope.quantity == scope.quantity
    )


def _register_effect(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RequestedEffect,
    *,
    consume_bootstrap_target: bool = False,
) -> VenueRecoveryBook | None:
    if type(consume_bootstrap_target) is not bool:
        raise TypeError("bootstrap consumption flag must be an exact bool")
    if book._current_effect(item.effect_id) is not None:
        return None
    if (
        item.client_order_id is not None
        and book._has_client_order(item.client_order_id)
    ) or book._has_request_occurrence(item.request_occurrence_id):
        return None
    scope = _effect_scope(book, item)
    active_bootstrap = book._bootstrap_bound_target_record(scope.position_scope)
    if active_bootstrap is not None:
        if not (
            consume_bootstrap_target
            and item.kind is EffectKind.SUBMIT
            and item.side is ExecutionSide.BUY
            and book._bootstrap_bound_target_pair_matches(
                execution,
                scope.position_scope,
            )
        ):
            return None
    elif consume_bootstrap_target:
        return None
    if scope.kind in {EffectKind.CANCEL, EffectKind.REPLACE} and not (
        _target_is_exact_active(book, scope)
    ):
        return None
    effect = BrokerEffect(scope=scope)
    return _book_with_input_and_execution(
        evolve,
        book,
        item,
        execution,
        execution,
        _effect_append=effect,
        _consume_bootstrap_target=consume_bootstrap_target,
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
        or (
            effect is not None
            and effect.scope.kind in {EffectKind.CANCEL, EffectKind.REPLACE}
            and not _target_is_exact_active(
                book,
                effect.scope,
                expected_cancel_effect_id=(
                    effect.effect_id if effect.scope.kind is EffectKind.CANCEL else None
                ),
            )
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
    *,
    attempt_replace: VenueAttempt | None = None,
) -> VenueRecoveryBook:
    updated = replace(effect, state=state)
    return _book_with_input(
        evolve,
        book,
        execution,
        item,
        _effect_replace=updated,
        _attempt_replace=attempt_replace,
    )


def _cancel_target_attempt_for_outcome(
    book: VenueRecoveryBook,
    effect: BrokerEffect,
    state: BrokerEffectState,
) -> VenueAttempt | None:
    """Derive the target-leg ambiguity caused by one correlated cancel outcome."""

    if effect.scope.kind is not EffectKind.CANCEL:
        return None
    target_leg_key = effect.scope.target_leg_key
    if target_leg_key is None:
        return None
    attempt = book.active_attempt(target_leg_key)
    if attempt is None:
        return None
    pending = (
        PendingVenueOperation.CANCEL
        if state in {BrokerEffectState.ACKNOWLEDGED, BrokerEffectState.OUTCOME_UNKNOWN}
        else None
    )
    if attempt.pending_operation is pending:
        return None
    return replace(attempt, pending_operation=pending)


def _discover_leg(
    evolve: _BookEvolver,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: DiscoverVenueLeg,
) -> tuple[VenueRecoveryBook | None, VenueRecoveryDisposition]:
    effect = book._current_effect(item.effect_id)
    if (
        effect is None
        or effect.scope.kind is EffectKind.CANCEL
        or not _same_leg_scope(book.scope, item.leg_key)
    ):
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


def _external_acceptance_closure_is_certified(
    book: VenueRecoveryBook,
    effect: BrokerEffect,
    proof: AcceptanceProof,
) -> bool:
    """Default-deny external closure until M2 supplies concrete coverage facts."""

    del book, effect, proof
    return False


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
    elif effect.claim_occurrence_id is None or not (
        _external_acceptance_closure_is_certified(book, effect, proof)
    ):
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
    _BrokerExecutionRegistryCatchUp,
    _BootstrapTargetRegistryInput,
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
    return execution == genesis


def _apply_execution_registry_catch_up(
    book: VenueRecoveryBook,
    target: ExecutionSnapshot,
    item: CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
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
    if not book._execution_reconciliation_cursor_is_prefix(
        target
    ) or not book._execution_reconciliation_cursor_is_prefix(source):
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
        or item.prior_account_registry_commitment != book.execution_registry_commitment
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

    if type(item) is _BrokerExecutionRegistryCatchUp:
        exact_item = cast(_BrokerExecutionRegistryCatchUp, item)
        owner = book.owner(exact_item.leg_key)
        effect = book._current_effect(exact_item.effect_id)
        observation = source.seen_facts.get(exact_item.fact.key)
        applied = _apply_broker_execution_fact(
            target.position,
            target.integrity,
            target.root_heads,
            target.seen_facts,
            exact_item.fact,
        )
        expected_source = ExecutionSnapshot(
            applied.position,
            applied.integrity,
            applied.root_heads,
            applied.seen_facts,
        )
        if (
            source_scope != target_scope
            or not book._execution_pair_matches_fast(target)
            or book.execution_registry_count != target.seen_facts.count
            or book.execution_registry_commitment != target.seen_facts.commitment
            or source.seen_facts.count != target.seen_facts.count + 1
            or not source.seen_facts.has_prefix(
                target.seen_facts.count,
                target.seen_facts.commitment,
            )
            or not source_binding_changed
            or applied.disposition.value != "APPLIED"
            or expected_source != source
            or observation is None
            or observation.fact != exact_item.fact
            or observation.classification
            is FirstObservationClassification.RECONCILIATION_REQUIRED
            or owner is None
            or effect is None
            or owner.effect_id != exact_item.effect_id
            or owner.leg_key != exact_item.leg_key
            or effect.scope.position_scope != target_scope
            or effect.scope.symbol_id != exact_item.fact.scope.symbol_id
            or effect.scope.side is not exact_item.fact.scope.side
        ):
            return transition(
                book,
                target,
                target,
                VenueRecoveryDisposition.RECONCILIATION_REQUIRED,
                item=item,
                quantity_delta=0,
            )
        resulting_binding = _execution_binding_for_snapshot(source)
        attributed_record = _AttributedRegistryAdvanceOutcome(
            input_id=exact_item.input_id,
            command_commitment=_catch_up_input_commitment(exact_item),
            target_checkpoint=exact_item.target_checkpoint,
            prior_account_registry_count=target.seen_facts.count,
            prior_account_registry_commitment=target.seen_facts.commitment,
            prior_source_binding=source_binding,
            resulting_source_binding=resulting_binding,
            effect_id=exact_item.effect_id,
            leg_key=exact_item.leg_key,
            fact=exact_item.fact,
            observation_classification=observation.classification,
            resulting_registry_count=source.seen_facts.count,
            resulting_registry_commitment=source.seen_facts.commitment,
            reason="canonical broker fact retained exact venue-owner attribution",
        )
        registry_proof = _registry_transition_proof_for(
            ordinal=book_transition_count + 1,
            predecessor_commitment=book._registry_transition_head_commitment,
            venue_scope=book.scope,
            item=exact_item,
            outcome=attributed_record,
        )
        next_execution = _bind_execution_reconciliation_cursor(
            source,
            transition_count=book_transition_count + 1,
            transition_head=registry_proof.commitment,
            account_reconciliation_required=account_reconciliation_required,
        )
        next_book = evolve(
            book,
            target,
            next_execution,
            item=exact_item,
            execution_registry_count=source.seen_facts.count,
            execution_registry_commitment=source.seen_facts.commitment,
            _binding_upserts=(_execution_binding_for_snapshot(next_execution),),
            _execution_reconciliation_append=attributed_record,
            canonical_economic_input=True,
        )
        return transition(
            next_book,
            target,
            next_execution,
            VenueRecoveryDisposition.APPLIED,
            item=exact_item,
            quantity_delta=(
                next_execution.position.raw_quantity - target.position.raw_quantity
            ),
        )

    if source.seen_facts.count == book.execution_registry_count:
        target_registry_is_current = bool(
            target.seen_facts.count == source.seen_facts.count
            and target.seen_facts.commitment == source.seen_facts.commitment
        )
        target_cursor_is_current = bool(
            target.reconciliation_transition_count == book_transition_count
            and target.reconciliation_transition_head == book_transition_head
        )
        if target_registry_is_current and target_cursor_is_current:
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
            reason=(
                "target reconciliation cursor advanced from an exact registry prefix"
                if target_registry_is_current
                else "target registry projection retained exact source and binding proof"
            ),
            projection_kind=(
                _ResolvedProjectionKind.RECONCILIATION_CURSOR_ADVANCE
                if target_registry_is_current
                else _ResolvedProjectionKind.REGISTRY_ADVANCE
            ),
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
            _refresh_bootstrap_target=(
                book._bootstrap_bound_target_record(target_scope) is not None
            ),
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


@dataclass(frozen=True, slots=True, init=False)
class _BootstrapPromotionPermit:
    """Ephemeral venue-owned proof for the one specialized R8 promotion."""

    position_scope: PositionScope = field(init=False)
    book_commitment: bytes = field(init=False)
    execution_commitment: bytes = field(init=False)
    active_record_commitment: bytes = field(init=False)
    request_commitment: bytes = field(init=False)
    commitment: bytes = field(init=False)
    _seal: bytes = field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("bootstrap promotion permits are venue-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("bootstrap promotion permits cannot be subclassed")


def _bootstrap_promotion_permit_commitment(
    *,
    position_scope: PositionScope,
    book_commitment: bytes,
    execution_commitment: bytes,
    active_record_commitment: bytes,
    request_commitment: bytes,
) -> bytes:
    if type(position_scope) is not PositionScope:
        raise TypeError("promotion permit position_scope must be exact")
    for name, value in (
        ("promotion permit book commitment", book_commitment),
        ("promotion permit execution commitment", execution_commitment),
        ("promotion permit active record commitment", active_record_commitment),
        ("promotion permit request commitment", request_commitment),
    ):
        _require_digest(name, value)
    return _commit_parts(
        b"execution-core/bootstrap-promotion-permit/v1",
        _encode_position_scope(position_scope),
        book_commitment,
        execution_commitment,
        active_record_commitment,
        request_commitment,
    )


def _mint_bootstrap_promotion_permit(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RequestedEffect,
) -> _BootstrapPromotionPermit:
    """Mint the sole token that may consume a live bootstrap record."""

    if (
        type(book) is not VenueRecoveryBook
        or type(execution) is not ExecutionSnapshot
        or type(item) is not RequestedEffect
        or item.kind is not EffectKind.SUBMIT
        or item.side is not ExecutionSide.BUY
        or item.symbol_id != execution.position.scope.symbol_id
    ):
        raise TypeError("bootstrap promotion requires one exact BUY request")
    position_scope = execution.position.scope
    active = book._bootstrap_bound_target_record(position_scope)
    if active is None or not book._bootstrap_bound_target_pair_matches(
        execution, position_scope
    ):
        raise ValueError("bootstrap promotion requires one exact active target record")
    book_commitment = _protection_book_commitment(book)
    request_commitment = _protection_command_commitment(item)
    commitment = _bootstrap_promotion_permit_commitment(
        position_scope=position_scope,
        book_commitment=book_commitment,
        execution_commitment=execution.commitment,
        active_record_commitment=active.commitment,
        request_commitment=request_commitment,
    )
    result = object.__new__(_BootstrapPromotionPermit)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(result, "book_commitment", book_commitment)
    object.__setattr__(result, "execution_commitment", execution.commitment)
    object.__setattr__(result, "active_record_commitment", active.commitment)
    object.__setattr__(result, "request_commitment", request_commitment)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(b"execution-core/bootstrap-promotion-permit-seal/v1", commitment),
    )
    return result


def _bootstrap_promotion_permit_is_current(
    permit: object,
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> bool:
    """Require an unmodified token to match this exact pre-transition pair."""

    if (
        type(permit) is not _BootstrapPromotionPermit
        or type(book) is not VenueRecoveryBook
        or type(execution) is not ExecutionSnapshot
        or type(item) is not RequestedEffect
        or item.kind is not EffectKind.SUBMIT
        or item.side is not ExecutionSide.BUY
        or item.symbol_id != execution.position.scope.symbol_id
    ):
        return False
    try:
        position_scope = permit.position_scope
        book_commitment = permit.book_commitment
        execution_commitment = permit.execution_commitment
        active_record_commitment = permit.active_record_commitment
        request_commitment = permit.request_commitment
        commitment = permit.commitment
        seal = permit._seal
        expected = _bootstrap_promotion_permit_commitment(
            position_scope=position_scope,
            book_commitment=book_commitment,
            execution_commitment=execution_commitment,
            active_record_commitment=active_record_commitment,
            request_commitment=request_commitment,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    active = book._bootstrap_bound_target_record(execution.position.scope)
    return bool(
        position_scope == execution.position.scope
        and active is not None
        and book._bootstrap_bound_target_pair_matches(execution, position_scope)
        and book_commitment == _protection_book_commitment(book)
        and execution_commitment == execution.commitment
        and active_record_commitment == active.commitment
        and request_commitment == _protection_command_commitment(item)
        and commitment == expected
        and seal
        == _commit_parts(b"execution-core/bootstrap-promotion-permit-seal/v1", expected)
    )


def _apply_venue_input(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
    *,
    promotion: _BootstrapPromotionPermit | None = None,
) -> VenueRecoveryTransition:
    """Apply one exact immutable input through the complete private reducer."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be the exact opaque VenueRecoveryBook type")
    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    if promotion is not None and type(promotion) is not _BootstrapPromotionPermit:
        raise TypeError("bootstrap promotion must be an exact private permit or None")
    _require_execution_components(
        execution.position,
        execution.integrity,
        execution.root_heads,
        execution.seen_facts,
    )
    _require_exact_venue_recovery_input(item)

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
        consume_bootstrap_target = changes.pop("_consume_bootstrap_target", False)
        refresh_bootstrap_target = changes.pop("_refresh_bootstrap_target", False)
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
        if type(consume_bootstrap_target) is not bool:
            raise TypeError("bootstrap consumption flag must be an exact bool")
        if type(refresh_bootstrap_target) is not bool:
            raise TypeError("bootstrap refresh flag must be an exact bool")
        if consume_bootstrap_target and refresh_bootstrap_target:
            raise ValueError("bootstrap checkpoint cannot refresh and consume together")
        prior_pair_matches = current._execution_pair_matches_fast(prior_execution)
        registering_new_symbol = bool(
            isinstance(item, RequestedEffect)
            and current.execution_registry_count == prior_execution.seen_facts.count
            and current.execution_registry_commitment
            == prior_execution.seen_facts.commitment
            and current.execution_binding(prior_execution.position.scope) is None
        )
        catch_up_item = (
            cast(
                CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
                item,
            )
            if type(item)
            in {
                CatchUpExecutionRegistry,
                _BrokerExecutionRegistryCatchUp,
            }
            else None
        )
        catching_up_registry = bool(
            catch_up_item is not None
            and current._execution_binding_matches(prior_execution)
            and resulting_execution.seen_facts.commitment
            == catch_up_item.source_execution.seen_facts.commitment
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
            if type(item) not in {
                CatchUpExecutionRegistry,
                _BrokerExecutionRegistryCatchUp,
            }:
                raise TypeError(
                    "registry reconciliation requires one exact CatchUp command"
                )
            registry_transition = _registry_transition_proof_for(
                ordinal=registry_transition_ledger.length + 1,
                predecessor_commitment=registry_transition_head_commitment,
                venue_scope=current.scope,
                item=cast(
                    CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
                    item,
                ),
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
        bootstrap_bound_target_by_scope = current._bootstrap_bound_target_by_scope
        if consume_bootstrap_target:
            if (
                type(item) is not RequestedEffect
                or type(effect_append) is not BrokerEffect
                or item.kind is not EffectKind.SUBMIT
                or item.side is not ExecutionSide.BUY
                or effect_append.scope.position_scope
                != _effect_scope(current, item).position_scope
            ):
                raise ValueError(
                    "bootstrap consumption requires one exact specialized BUY request"
                )
            bootstrap_bound_target_by_scope = _consume_bootstrap_bound_target_record(
                current,
                effect_append,
                item.input_id,
            )
        cancel_target_reservation_by_leg = current._cancel_target_reservation_by_leg
        if isinstance(effect_append, BrokerEffect):
            cancel_target_reservation_by_leg = _evolve_cancel_target_reservations(
                cancel_target_reservation_by_leg,
                None,
                effect_append,
            )
        elif isinstance(effect_replace, BrokerEffect):
            cancel_target_reservation_by_leg = _evolve_cancel_target_reservations(
                cancel_target_reservation_by_leg,
                current._current_effect(effect_replace.effect_id),
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
            leg_current_by_leg, leg_summary_by_effect = _replace_attempt_value(
                leg_current_by_leg,
                owner_by_leg,
                leg_summary_by_effect,
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
                and effect_current.effect.state is BrokerEffectState.OPERATOR_RECONCILED
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
                active_leg_keys=tuple(
                    leg for leg in summary.active_leg_keys if leg != closure.leg_key
                ),
                known_cancellable_leg_keys=tuple(
                    leg
                    for leg in summary.known_cancellable_leg_keys
                    if leg != closure.leg_key
                ),
                known_cancel_pending_leg_keys=tuple(
                    leg
                    for leg in summary.known_cancel_pending_leg_keys
                    if leg != closure.leg_key
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
            if type(binding) is not VenueExecutionBinding:
                raise TypeError(
                    "binding upsert must be VenueExecutionBinding (exact type required)"
                )
            VenueExecutionBinding.__post_init__(binding)
            if binding.position_scope in seen_binding_scopes:
                raise ValueError("binding scope cannot be updated twice")
            seen_binding_scopes.add(binding.position_scope)
            binding_order, binding_by_scope = _upsert_binding_value(
                binding_order,
                binding_by_scope,
                binding,
            )

        execution_snapshot_by_scope = current._execution_snapshot_by_scope
        snapshot_upserts: tuple[ExecutionSnapshot, ...] = (resulting_execution,)
        for snapshot in snapshot_upserts:
            binding = binding_by_scope.get(
                _position_scope_index_key(snapshot.position.scope)
            )
            if binding is None or not _binding_matches_execution(binding, snapshot):
                raise ValueError(
                    "execution snapshot upsert requires its exact resulting binding"
                )
            execution_snapshot_by_scope = _upsert_execution_snapshot_value(
                execution_snapshot_by_scope,
                snapshot,
            )

        if refresh_bootstrap_target:
            if (
                type(item) is not CatchUpExecutionRegistry
                or effect_append is not None
                or effect_replace is not None
                or resulting_execution.position.scope != item.target_scope
            ):
                raise ValueError(
                    "bootstrap refresh requires one exact ordinary catch-up"
                )
            resulting_binding = binding_by_scope.get(
                _position_scope_index_key(resulting_execution.position.scope)
            )
            if type(resulting_binding) is not VenueExecutionBinding:
                raise ValueError("bootstrap refresh requires its exact binding")
            staged_book = _copy_book_with_bootstrap_values(
                current,
                _bootstrap_bound_target_by_scope=bootstrap_bound_target_by_scope,
            )
            staged_book = _book_with_staged_bootstrap_refresh(
                staged_book,
                resulting_execution,
                resulting_binding,
                item,
            )
            bootstrap_bound_target_by_scope = (
                staged_book._bootstrap_bound_target_by_scope
            )

        coverage_provenance_by_scope = _evolve_coverage_provenance(
            current._coverage_provenance_by_scope,
            prior_execution,
            resulting_execution,
            item,
            canonical_economic_input=canonical_economic_input,
        )
        acquisition_correlation_by_root = _evolve_acquisition_correlation_index(
            current,
            current._acquisition_correlation_by_root,
            resulting_execution,
            item,
            effect_by_request_occurrence,
            effect_by_id,
            owner_by_leg,
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
        object.__setattr__(
            result,
            "_acquisition_correlation_by_root",
            acquisition_correlation_by_root,
        )
        object.__setattr__(result, "_leg_current_by_leg", leg_current_by_leg)
        object.__setattr__(
            result,
            "_cancel_target_reservation_by_leg",
            cancel_target_reservation_by_leg,
        )
        object.__setattr__(
            result,
            "_leg_summary_by_effect",
            leg_summary_by_effect,
        )
        object.__setattr__(result, "_binding_order", binding_order)
        object.__setattr__(result, "_binding_by_scope", binding_by_scope)
        object.__setattr__(
            result,
            "_execution_snapshot_by_scope",
            execution_snapshot_by_scope,
        )
        object.__setattr__(
            result,
            "_bootstrap_bound_target_by_scope",
            bootstrap_bound_target_by_scope,
        )
        object.__setattr__(
            result,
            "_protection_cursor_by_scope",
            current._protection_cursor_by_scope,
        )
        object.__setattr__(
            result,
            "_protection_transition_ledger",
            current._protection_transition_ledger,
        )
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

        affected_authority_effect_ids: list[EffectId] = []

        def retain_affected(effect_id: EffectId | None) -> None:
            if effect_id is not None and effect_id not in affected_authority_effect_ids:
                affected_authority_effect_ids.append(effect_id)

        if isinstance(effect_append, BrokerEffect):
            retain_affected(effect_append.effect_id)
        if isinstance(effect_replace, BrokerEffect):
            retain_affected(effect_replace.effect_id)
        if (
            type(owner_and_attempt_append) is tuple
            and owner_and_attempt_append
            and isinstance(owner_and_attempt_append[0], VenueIdentityOwner)
        ):
            retain_affected(owner_and_attempt_append[0].effect_id)
        if isinstance(attempt_replace, VenueAttempt):
            attempt_owner = owner_by_leg.get(_leg_index_key(attempt_replace.leg_key))
            retain_affected(None if attempt_owner is None else attempt_owner.effect_id)
        if closure is not None:
            closure_owner = owner_by_leg.get(_leg_index_key(closure.leg_key))
            retain_affected(None if closure_owner is None else closure_owner.effect_id)
        reconciliation_effect_id = getattr(reconciliation_append, "effect_id", None)
        retain_affected(
            reconciliation_effect_id
            if isinstance(reconciliation_effect_id, EffectId)
            else None
        )

        authority_contribution_by_effect = current._authority_contribution_by_effect
        authority_summary_by_scope = current._authority_summary_by_scope
        account_unclaimed_requested_effect_ids = (
            current._account_unclaimed_requested_effect_ids
        )
        for affected_effect_id in affected_authority_effect_ids:
            prior_contribution = current._authority_contribution_by_effect.get(
                _effect_index_key(affected_effect_id)
            )
            resulting_contribution = _derive_effect_authority_contribution(
                result,
                affected_effect_id,
            )
            (
                authority_contribution_by_effect,
                authority_summary_by_scope,
                account_unclaimed_requested_effect_ids,
            ) = _update_authority_indexes(
                authority_contribution_by_effect,
                authority_summary_by_scope,
                account_unclaimed_requested_effect_ids,
                prior=prior_contribution,
                resulting=resulting_contribution,
            )
        object.__setattr__(
            result,
            "_authority_contribution_by_effect",
            authority_contribution_by_effect,
        )
        object.__setattr__(
            result,
            "_authority_summary_by_scope",
            authority_summary_by_scope,
        )
        object.__setattr__(
            result,
            "_account_unclaimed_requested_effect_ids",
            account_unclaimed_requested_effect_ids,
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
            _BrokerExecutionRegistryCatchUp,
        }
        if (
            economic_command
            and disposition is VenueRecoveryDisposition.APPLIED
            and (
                resulting_execution.position.raw_quantity < 0
                or resulting_execution.position.basis_authority
                is BasisAuthority.BASIS_RECONCILIATION_PENDING
            )
        ):
            disposition = VenueRecoveryDisposition.RECONCILIATION_REQUIRED
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

        position_scope = _protection_position_scope(
            book,
            resulting_execution,
            item,
        )
        staged_bootstrap_refresh = resulting_book._staged_bootstrap_bound_target_record(
            position_scope
        )
        if staged_bootstrap_refresh is not None and not (
            disposition is VenueRecoveryDisposition.APPLIED
            and type(item) is CatchUpExecutionRegistry
            and resulting_book._staged_bootstrap_bound_target_pair_matches(
                staged_bootstrap_refresh,
                resulting_execution,
                position_scope,
            )
        ):
            raise ValueError("bootstrap refresh stage is not an exact catch-up")
        retained_predecessor = book._execution_snapshot_by_scope.get(
            _position_scope_index_key(position_scope)
        )
        proof_predecessor_execution = prior_execution
        if (
            retained_predecessor is not None
            and disposition is not VenueRecoveryDisposition.EXACT_REPLAY
        ):
            if type(retained_predecessor) is not ExecutionSnapshot:
                raise TypeError("retained predecessor execution must be exact")
            proof_predecessor_execution = retained_predecessor
        (
            predecessor_summary,
            predecessor_binding,
            predecessor_cursor,
            predecessor_binding_matches,
            predecessor_reconciliation_clear,
        ) = _protection_scope_values(book, prior_execution, position_scope)
        (
            summary,
            binding,
            retained_cursor,
            binding_matches,
            reconciliation_clear,
        ) = _protection_scope_values(
            resulting_book,
            resulting_execution,
            position_scope,
        )
        if retained_cursor != predecessor_cursor:
            raise ValueError(
                "resulting book changed the protection cursor outside transition"
            )
        predecessor_book_commitment = _protection_book_commitment(book)
        predecessor_execution_checkpoint = VenueExecutionCheckpoint.from_execution(
            proof_predecessor_execution
        )
        execution_checkpoint = VenueExecutionCheckpoint.from_execution(
            resulting_execution
        )
        command_commitment = _protection_command_commitment(item)
        command_mandate_id = _protection_mandate_id(book, item)
        mandate_id = (
            predecessor_cursor.mandate_id
            if predecessor_cursor.mandate_id is not None
            else command_mandate_id
        )
        projection_changed = bool(
            prior_execution.position.raw_quantity
            != resulting_execution.position.raw_quantity
            or prior_execution.position.basis_authority
            != resulting_execution.position.basis_authority
            or prior_execution.position.cost_basis
            != resulting_execution.position.cost_basis
            or prior_execution.position.basis_price_metadata
            != resulting_execution.position.basis_price_metadata
            or predecessor_summary.blocking_effect_count
            != summary.blocking_effect_count
            or predecessor_summary.blocking_buy_effect_count
            != summary.blocking_buy_effect_count
            or predecessor_binding_matches != binding_matches
            or predecessor_reconciliation_clear != reconciliation_clear
        )
        advance_cursor = bool(
            disposition is VenueRecoveryDisposition.APPLIED
            or (
                disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
                and projection_changed
            )
        )
        if (
            not advance_cursor
            and retained_predecessor is not None
            and resulting_book._execution_snapshot_by_scope.commitment
            != book._execution_snapshot_by_scope.commitment
        ):
            resulting_book = _with_execution_snapshot_index(
                resulting_book,
                book._execution_snapshot_by_scope,
            )
        book_commitment = _protection_book_commitment(resulting_book)
        cursor = (
            _next_protection_cursor(
                predecessor_cursor,
                position_scope,
                mandate_id,
                book.scope,
                resulting_book.scope,
                predecessor_book_commitment,
                book_commitment,
                proof_predecessor_execution.commitment,
                resulting_execution.commitment,
                predecessor_execution_checkpoint,
                execution_checkpoint,
                predecessor_summary,
                summary,
                predecessor_binding,
                binding,
                predecessor_binding_matches,
                binding_matches,
                predecessor_reconciliation_clear,
                reconciliation_clear,
                command_commitment,
                disposition,
                derived_delta,
            )
            if advance_cursor
            else predecessor_cursor
        )
        protection_proof = _ProtectionTransitionProof(
            position_scope=position_scope,
            predecessor_cursor=predecessor_cursor,
            cursor=cursor,
            predecessor_book_scope=book.scope,
            book_scope=resulting_book.scope,
            predecessor_book_commitment=predecessor_book_commitment,
            book_commitment=book_commitment,
            predecessor_execution_commitment=proof_predecessor_execution.commitment,
            execution_commitment=resulting_execution.commitment,
            predecessor_execution_checkpoint=predecessor_execution_checkpoint,
            execution_checkpoint=execution_checkpoint,
            predecessor_summary=predecessor_summary,
            summary=summary,
            predecessor_binding=predecessor_binding,
            binding=binding,
            predecessor_execution_binding_matches=predecessor_binding_matches,
            execution_binding_matches=binding_matches,
            predecessor_account_reconciliation_clear=predecessor_reconciliation_clear,
            account_reconciliation_clear=reconciliation_clear,
            command_commitment=command_commitment,
            disposition=disposition,
            quantity_delta=derived_delta,
        )
        if advance_cursor:
            resulting_book = _with_protection_cursor(
                resulting_book,
                position_scope,
                cursor,
                protection_proof,
            )
        if staged_bootstrap_refresh is not None:
            if not advance_cursor:
                raise ValueError("bootstrap refresh requires one advancing proof")
            resulting_book = _finalize_staged_bootstrap_refresh(
                resulting_book,
                resulting_execution,
                protection_proof,
            )
            if not resulting_book._execution_pair_matches_fast(resulting_execution):
                raise ValueError(
                    "bootstrap refresh finalization produced a stale execution pair"
                )

        acquisition_fact_proof = _mint_acquisition_fact_proof(
            book,
            proof_predecessor_execution,
            resulting_book,
            resulting_execution,
            item,
            protection_proof,
            disposition,
        )

        result = object.__new__(VenueRecoveryTransition)
        object.__setattr__(result, "book", resulting_book)
        object.__setattr__(result, "execution", resulting_execution)
        object.__setattr__(result, "disposition", disposition)
        object.__setattr__(result, "quantity_delta", derived_delta)
        object.__setattr__(result, "_source_item", item)
        object.__setattr__(result, "_protection_proof", protection_proof)
        object.__setattr__(
            result,
            "_protection_proof_commitment",
            protection_proof.commitment,
        )
        object.__setattr__(result, "_acquisition_fact_proof", acquisition_fact_proof)
        object.__setattr__(
            result,
            "_acquisition_fact_proof_commitment",
            (
                None
                if acquisition_fact_proof is None
                else acquisition_fact_proof.commitment
            ),
        )
        return result

    input_id = _require_input_id("item.input_id", getattr(item, "input_id", None))
    if promotion is not None and not _bootstrap_promotion_permit_is_current(
        promotion,
        book,
        execution,
        item,
    ):
        return transition(
            book,
            execution,
            execution,
            VenueRecoveryDisposition.REFUSED,
            item=item,
            quantity_delta=0,
        )
    if isinstance(item, RequestedEffect):
        requested_scope = _effect_scope(book, item)
        if (
            promotion is None
            and book._bootstrap_bound_target_record(requested_scope.position_scope)
            is not None
        ):
            # An active R8 record is not a generic zero-effect admission.  The
            # sole ordinary request that may start from it must carry the
            # exact venue-minted promotion proof validated above.
            return transition(
                book,
                execution,
                execution,
                VenueRecoveryDisposition.REFUSED,
                item=item,
                quantity_delta=0,
            )
    if type(item) in {
        CatchUpExecutionRegistry,
        _BrokerExecutionRegistryCatchUp,
    }:
        return _apply_execution_registry_catch_up(
            book,
            execution,
            cast(
                CatchUpExecutionRegistry | _BrokerExecutionRegistryCatchUp,
                item,
            ),
            evolve,
            transition,
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
        target_refused = bool(
            item.kind in {EffectKind.CANCEL, EffectKind.REPLACE}
            and not _target_is_exact_active(book, _effect_scope(book, item))
        )
        if target_refused:
            next_book = None
            disposition = VenueRecoveryDisposition.REFUSED
        else:
            next_book = _register_effect(
                evolve,
                book,
                execution,
                item,
                consume_bootstrap_target=promotion is not None,
            )
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
            target_attempt = _cancel_target_attempt_for_outcome(
                book,
                effect,
                item.state,
            )
            next_book = _maybe_finalize_effect(
                evolve,
                _replace_effect_state(
                    evolve,
                    book,
                    execution,
                    effect,
                    item.state,
                    item,
                    attempt_replace=target_attempt,
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
            target_attempt = _cancel_target_attempt_for_outcome(
                book,
                effect,
                BrokerEffectState.OUTCOME_UNKNOWN,
            )
            next_book = _replace_effect_state(
                evolve,
                book,
                execution,
                effect,
                BrokerEffectState.OUTCOME_UNKNOWN,
                item,
                attempt_replace=target_attempt,
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


@dataclass(frozen=True, slots=True, init=False)
class _M2VenueState:
    """Owner-sealed venue state used by the public and direct-proof routes."""

    book: VenueRecoveryBook
    commitment: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("_M2VenueState is owner-constructed")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("_M2VenueState cannot be subclassed")


@dataclass(frozen=True, slots=True, init=False)
class _M2VenueObservationProof:
    """Exact operation-keyed evidence for one venue/recovery reduction."""

    mode: str
    source_state_commitment: bytes
    serving_state_commitment: bytes
    item: object
    retained_item: object | None
    retained_input_bytes: bytes | None
    retained_outcome_bytes: bytes | None
    retained_fact_item: object | None
    retained_fact_input_bytes: bytes | None
    retained_fact_outcome_bytes: bytes | None
    retained_coverage_items: tuple[object | None, object | None, object | None]
    retained_coverage_input_bytes: tuple[bytes | None, bytes | None, bytes | None]
    retained_coverage_outcome_bytes: tuple[bytes | None, bytes | None, bytes | None]
    commitment: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("_M2VenueObservationProof is owner-constructed")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("_M2VenueObservationProof cannot be subclassed")


def _require_m2_venue_operation_item(item: object) -> None:
    from .recovery import (
        IngestHumanAttestedFill,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
        ReleaseVenueLeg,
    )

    if type(item) not in {
        RecordTransportOutcome,
        RecoverClaimedEffect,
        DiscoverVenueLeg,
        ObserveVenueStatus,
        IngestHumanAttestedFill,
        ReleaseVenueLeg,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
    }:
        raise TypeError("M2 venue operation item has the wrong exact type")


def _is_m2_venue_operation_item(item: object) -> bool:
    try:
        _require_m2_venue_operation_item(item)
    except TypeError:
        return False
    return True


def _m2_venue_state_commitment(book: VenueRecoveryBook) -> bytes:
    return _commit_parts(
        b"execution-core/m2-venue-state/v1",
        _protection_book_commitment(book),
    )


def _m2_venue_state_from_book(book: VenueRecoveryBook) -> _M2VenueState:
    """Project one exact in-memory owner into the shared venue-kernel state."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be exact VenueRecoveryBook")
    result = object.__new__(_M2VenueState)
    object.__setattr__(result, "book", book)
    object.__setattr__(result, "commitment", _m2_venue_state_commitment(book))
    return result


def _m2_venue_state_is_authentic(state: object) -> bool:
    if type(state) is not _M2VenueState:
        return False
    try:
        return bool(
            type(state.book) is VenueRecoveryBook
            and state.commitment == _m2_venue_state_commitment(state.book)
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _m2_scoped_input_book(
    book: VenueRecoveryBook,
    retained_item: object | None,
    retained_fact_item: object | None,
    retained_coverage_items: tuple[object | None, object | None, object | None],
) -> VenueRecoveryBook:
    """Retain only the fixed operation-keyed semantic owners."""

    empty_sequence: _PersistentSequence[VenueInputRecord] = _PersistentSequence.empty()
    empty_map: _PersistentKeyMap[VenueInputRecord] = _PersistentKeyMap.empty()
    scoped = _copy_book_with_bootstrap_values(
        book,
        _input_ledger=empty_sequence,
        _input_by_id=empty_map,
        _direct_input_by_semantic=empty_map,
        _first_input_by_fact=empty_map,
    )
    retained: list[object] = []
    for candidate in (retained_fact_item, retained_item, *retained_coverage_items):
        if candidate is None:
            continue
        _require_m2_venue_operation_item(candidate)
        retained_input_id = getattr(candidate, "input_id", None)
        prior = next(
            (
                item
                for item in retained
                if getattr(item, "input_id", None) == retained_input_id
            ),
            None,
        )
        if prior is not None:
            if prior != candidate:
                raise ValueError(
                    "retained venue owners disagree for one input identity"
                )
            continue
        retained.append(candidate)
    for selected in retained:
        ledger, by_id, by_semantic, by_fact = _append_input_proof(scoped, selected)
        scoped = _copy_book_with_bootstrap_values(
            scoped,
            _input_ledger=ledger,
            _input_by_id=by_id,
            _direct_input_by_semantic=by_semantic,
            _first_input_by_fact=by_fact,
        )
    return scoped


def _validate_m2_direct_retained_evidence(
    item: object,
    retained_item: object | None,
    retained_input_bytes: bytes | None,
    retained_outcome_bytes: bytes | None,
    retained_fact_item: object | None,
    retained_fact_input_bytes: bytes | None,
    retained_fact_outcome_bytes: bytes | None,
    retained_coverage_items: tuple[object | None, object | None, object | None],
    retained_coverage_input_bytes: tuple[bytes | None, bytes | None, bytes | None],
    retained_coverage_outcome_bytes: tuple[bytes | None, bytes | None, bytes | None],
) -> None:
    """Validate the fixed command, fact, and coverage semantic identities."""

    from .recovery import (
        IngestHumanAttestedFill,
        RecordBrokerFillEvidence,
        RecordBrokerRevisionEvidence,
    )

    def coverage_interval(value: object) -> tuple[VenueLegKey, int, int] | None:
        if type(value) is IngestHumanAttestedFill:
            human = cast(IngestHumanAttestedFill, value)
            return (
                human.fact.leg_key,
                human.fact.prior_cumulative_quantity.value,
                human.fact.resulting_cumulative_quantity.value,
            )
        if type(value) is RecordBrokerFillEvidence:
            broker_fill = cast(RecordBrokerFillEvidence, value)
            return (
                broker_fill.leg_key,
                broker_fill.prior_cumulative_quantity.value,
                broker_fill.resulting_cumulative_quantity.value,
            )
        if type(value) is RecordBrokerRevisionEvidence:
            revision = cast(RecordBrokerRevisionEvidence, value)
            return (
                revision.leg_key,
                revision.prior_venue_cumulative_quantity.value,
                revision.resulting_venue_cumulative_quantity.value,
            )
        return None

    for name, values in (
        ("coverage items", retained_coverage_items),
        ("coverage input bytes", retained_coverage_input_bytes),
        ("coverage outcome bytes", retained_coverage_outcome_bytes),
    ):
        if type(values) is not tuple or len(values) != 3:
            raise TypeError(f"retained venue {name} must be an exact three-slot tuple")

    _require_m2_venue_operation_item(item)
    item_input_id = getattr(item, "input_id", None)
    if retained_item is None:
        if retained_input_bytes is not None or retained_outcome_bytes is not None:
            raise ValueError("absent semantic evidence cannot carry retained bytes")
    else:
        _require_m2_venue_operation_item(retained_item)
        if (
            _semantic_input_key(retained_item) != _semantic_input_key(item)
            or getattr(retained_item, "input_id", None) == item_input_id
            or type(retained_input_bytes) is not bytes
            or not retained_input_bytes
            or type(retained_outcome_bytes) is not bytes
            or not retained_outcome_bytes
        ):
            raise ValueError("retained venue semantic evidence is not exact")

    item_fact_key = getattr(getattr(item, "fact", None), "key", None)
    if retained_fact_item is None:
        if (
            retained_fact_input_bytes is not None
            or retained_fact_outcome_bytes is not None
        ):
            raise ValueError("absent fact evidence cannot carry retained bytes")
    else:
        _require_m2_venue_operation_item(retained_fact_item)
        retained_fact_key = getattr(
            getattr(retained_fact_item, "fact", None),
            "key",
            None,
        )
        if (
            type(item_fact_key) is not ExecutionFactKey
            or type(retained_fact_key) is not ExecutionFactKey
            or retained_fact_key != item_fact_key
            or getattr(retained_fact_item, "input_id", None) == item_input_id
            or type(retained_fact_input_bytes) is not bytes
            or not retained_fact_input_bytes
            or type(retained_fact_outcome_bytes) is not bytes
            or not retained_fact_outcome_bytes
        ):
            raise ValueError("retained venue fact evidence is not exact")

    fact = getattr(item, "fact", None)
    expected_root = getattr(fact, "root_key", None)
    if type(expected_root) is not RootFillKey:
        expected_root = None
    expected_interval = coverage_interval(item)
    expected_broker_fact = (
        item_fact_key
        if type(item) in {RecordBrokerFillEvidence, RecordBrokerRevisionEvidence}
        and type(item_fact_key) is ExecutionFactKey
        else None
    )
    expected = (expected_root, expected_interval, expected_broker_fact)
    for index, (candidate, input_bytes, outcome_bytes) in enumerate(
        zip(
            retained_coverage_items,
            retained_coverage_input_bytes,
            retained_coverage_outcome_bytes,
            strict=True,
        )
    ):
        if candidate is None:
            if input_bytes is not None or outcome_bytes is not None:
                raise ValueError("absent coverage evidence cannot carry retained bytes")
            continue
        _require_m2_venue_operation_item(candidate)
        candidate_fact = getattr(candidate, "fact", None)
        candidate_identity: object | None
        if index == 0:
            candidate_identity = getattr(candidate_fact, "root_key", None)
        elif index == 1:
            candidate_identity = coverage_interval(candidate)
        else:
            candidate_identity = (
                getattr(candidate_fact, "key", None)
                if type(candidate)
                in {RecordBrokerFillEvidence, RecordBrokerRevisionEvidence}
                else None
            )
        if (
            expected[index] is None
            or candidate_identity != expected[index]
            or getattr(candidate, "input_id", None) == item_input_id
            or type(input_bytes) is not bytes
            or not input_bytes
            or type(outcome_bytes) is not bytes
            or not outcome_bytes
        ):
            raise ValueError("retained venue coverage evidence is not exact")

    retained_triplets = (
        (retained_item, retained_input_bytes, retained_outcome_bytes),
        (
            retained_fact_item,
            retained_fact_input_bytes,
            retained_fact_outcome_bytes,
        ),
        *tuple(
            zip(
                retained_coverage_items,
                retained_coverage_input_bytes,
                retained_coverage_outcome_bytes,
                strict=True,
            )
        ),
    )
    seen_by_input: dict[object, tuple[object, bytes | None, bytes | None]] = {}
    for candidate, input_bytes, outcome_bytes in retained_triplets:
        if candidate is None:
            continue
        candidate_input_id = getattr(candidate, "input_id", None)
        prior = seen_by_input.get(candidate_input_id)
        current = (candidate, input_bytes, outcome_bytes)
        if prior is not None and prior != current:
            raise ValueError("retained venue owners disagree for one input identity")
        seen_by_input[candidate_input_id] = current


def _m2_venue_observation_proof_commitment(
    *,
    mode: str,
    source_state_commitment: bytes,
    serving_state_commitment: bytes,
    item: object,
    retained_item: object | None,
    retained_input_bytes: bytes | None,
    retained_outcome_bytes: bytes | None,
    retained_fact_item: object | None,
    retained_fact_input_bytes: bytes | None,
    retained_fact_outcome_bytes: bytes | None,
    retained_coverage_items: tuple[object | None, object | None, object | None],
    retained_coverage_input_bytes: tuple[bytes | None, bytes | None, bytes | None],
    retained_coverage_outcome_bytes: tuple[bytes | None, bytes | None, bytes | None],
) -> bytes:
    return _commit_parts(
        b"execution-core/m2-venue-observation-proof/v3",
        _encode_text(mode),
        source_state_commitment,
        serving_state_commitment,
        _canonical_value_commitment(item),
        _canonical_value_commitment(retained_item),
        _canonical_value_commitment(retained_input_bytes),
        _canonical_value_commitment(retained_outcome_bytes),
        _canonical_value_commitment(retained_fact_item),
        _canonical_value_commitment(retained_fact_input_bytes),
        _canonical_value_commitment(retained_fact_outcome_bytes),
        _canonical_value_commitment(retained_coverage_items),
        _canonical_value_commitment(retained_coverage_input_bytes),
        _canonical_value_commitment(retained_coverage_outcome_bytes),
    )


def _new_m2_venue_observation_proof(
    *,
    mode: str,
    source_state_commitment: bytes,
    serving_state_commitment: bytes,
    item: object,
    retained_item: object | None,
    retained_input_bytes: bytes | None,
    retained_outcome_bytes: bytes | None,
    retained_fact_item: object | None,
    retained_fact_input_bytes: bytes | None,
    retained_fact_outcome_bytes: bytes | None,
    retained_coverage_items: tuple[object | None, object | None, object | None],
    retained_coverage_input_bytes: tuple[bytes | None, bytes | None, bytes | None],
    retained_coverage_outcome_bytes: tuple[bytes | None, bytes | None, bytes | None],
) -> _M2VenueObservationProof:
    commitment = _m2_venue_observation_proof_commitment(
        mode=mode,
        source_state_commitment=source_state_commitment,
        serving_state_commitment=serving_state_commitment,
        item=item,
        retained_item=retained_item,
        retained_input_bytes=retained_input_bytes,
        retained_outcome_bytes=retained_outcome_bytes,
        retained_fact_item=retained_fact_item,
        retained_fact_input_bytes=retained_fact_input_bytes,
        retained_fact_outcome_bytes=retained_fact_outcome_bytes,
        retained_coverage_items=retained_coverage_items,
        retained_coverage_input_bytes=retained_coverage_input_bytes,
        retained_coverage_outcome_bytes=retained_coverage_outcome_bytes,
    )
    result = object.__new__(_M2VenueObservationProof)
    for name, value in (
        ("mode", mode),
        ("source_state_commitment", source_state_commitment),
        ("serving_state_commitment", serving_state_commitment),
        ("item", item),
        ("retained_item", retained_item),
        ("retained_input_bytes", retained_input_bytes),
        ("retained_outcome_bytes", retained_outcome_bytes),
        ("retained_fact_item", retained_fact_item),
        ("retained_fact_input_bytes", retained_fact_input_bytes),
        ("retained_fact_outcome_bytes", retained_fact_outcome_bytes),
        ("retained_coverage_items", retained_coverage_items),
        ("retained_coverage_input_bytes", retained_coverage_input_bytes),
        ("retained_coverage_outcome_bytes", retained_coverage_outcome_bytes),
        ("commitment", commitment),
    ):
        object.__setattr__(result, name, value)
    return result


def _m2_venue_observation_from_book(
    state: _M2VenueState,
    item: object,
) -> _M2VenueObservationProof:
    if not _m2_venue_state_is_authentic(state):
        raise ValueError("venue state is not authentic")
    _require_m2_venue_operation_item(item)
    return _new_m2_venue_observation_proof(
        mode="REFERENCE",
        source_state_commitment=state.commitment,
        serving_state_commitment=state.commitment,
        item=item,
        retained_item=None,
        retained_input_bytes=None,
        retained_outcome_bytes=None,
        retained_fact_item=None,
        retained_fact_input_bytes=None,
        retained_fact_outcome_bytes=None,
        retained_coverage_items=(None, None, None),
        retained_coverage_input_bytes=(None, None, None),
        retained_coverage_outcome_bytes=(None, None, None),
    )


def _m2_venue_observation_from_direct_evidence(
    state: _M2VenueState,
    item: object,
    *,
    retained_item: object | None,
    retained_input_bytes: bytes | None,
    retained_outcome_bytes: bytes | None,
    retained_fact_item: object | None,
    retained_fact_input_bytes: bytes | None,
    retained_fact_outcome_bytes: bytes | None,
    retained_coverage_items: tuple[object | None, object | None, object | None] = (
        None,
        None,
        None,
    ),
    retained_coverage_input_bytes: tuple[bytes | None, bytes | None, bytes | None] = (
        None,
        None,
        None,
    ),
    retained_coverage_outcome_bytes: tuple[bytes | None, bytes | None, bytes | None] = (
        None,
        None,
        None,
    ),
) -> _M2VenueObservationProof:
    """Mint one proof from exact retained command, fact, and coverage evidence."""

    if not _m2_venue_state_is_authentic(state):
        raise ValueError("venue state is not authentic")
    _require_m2_venue_operation_item(item)
    _validate_m2_direct_retained_evidence(
        item,
        retained_item,
        retained_input_bytes,
        retained_outcome_bytes,
        retained_fact_item,
        retained_fact_input_bytes,
        retained_fact_outcome_bytes,
        retained_coverage_items,
        retained_coverage_input_bytes,
        retained_coverage_outcome_bytes,
    )
    scoped_book = _m2_scoped_input_book(
        state.book,
        retained_item,
        retained_fact_item,
        retained_coverage_items,
    )
    serving_state_commitment = _m2_venue_state_commitment(scoped_book)
    return _new_m2_venue_observation_proof(
        mode="DIRECT",
        source_state_commitment=state.commitment,
        serving_state_commitment=serving_state_commitment,
        item=item,
        retained_item=retained_item,
        retained_input_bytes=retained_input_bytes,
        retained_outcome_bytes=retained_outcome_bytes,
        retained_fact_item=retained_fact_item,
        retained_fact_input_bytes=retained_fact_input_bytes,
        retained_fact_outcome_bytes=retained_fact_outcome_bytes,
        retained_coverage_items=retained_coverage_items,
        retained_coverage_input_bytes=retained_coverage_input_bytes,
        retained_coverage_outcome_bytes=retained_coverage_outcome_bytes,
    )


def _m2_venue_observation_proof_is_authentic(
    proof: object,
) -> bool:
    if type(proof) is not _M2VenueObservationProof:
        return False
    try:
        if proof.mode == "REFERENCE":
            if any(
                value is not None
                for value in (
                    proof.retained_item,
                    proof.retained_input_bytes,
                    proof.retained_outcome_bytes,
                    proof.retained_fact_item,
                    proof.retained_fact_input_bytes,
                    proof.retained_fact_outcome_bytes,
                )
            ):
                return False
            if (
                proof.retained_coverage_items != (None, None, None)
                or proof.retained_coverage_input_bytes != (None, None, None)
                or proof.retained_coverage_outcome_bytes != (None, None, None)
            ):
                return False
        elif proof.mode == "DIRECT":
            _validate_m2_direct_retained_evidence(
                proof.item,
                proof.retained_item,
                proof.retained_input_bytes,
                proof.retained_outcome_bytes,
                proof.retained_fact_item,
                proof.retained_fact_input_bytes,
                proof.retained_fact_outcome_bytes,
                proof.retained_coverage_items,
                proof.retained_coverage_input_bytes,
                proof.retained_coverage_outcome_bytes,
            )
        else:
            return False
        return bool(
            proof.commitment
            == _m2_venue_observation_proof_commitment(
                mode=proof.mode,
                source_state_commitment=proof.source_state_commitment,
                serving_state_commitment=proof.serving_state_commitment,
                item=proof.item,
                retained_item=proof.retained_item,
                retained_input_bytes=proof.retained_input_bytes,
                retained_outcome_bytes=proof.retained_outcome_bytes,
                retained_fact_item=proof.retained_fact_item,
                retained_fact_input_bytes=proof.retained_fact_input_bytes,
                retained_fact_outcome_bytes=proof.retained_fact_outcome_bytes,
                retained_coverage_items=proof.retained_coverage_items,
                retained_coverage_input_bytes=proof.retained_coverage_input_bytes,
                retained_coverage_outcome_bytes=proof.retained_coverage_outcome_bytes,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _m2_venue_state_from_direct_proof(
    state: _M2VenueState,
    proof: _M2VenueObservationProof,
) -> _M2VenueState:
    """Replace omitted input history with the proof's exact direct evidence."""

    if not _m2_venue_state_is_authentic(state):
        raise ValueError("venue state is not authentic")
    if (
        not _m2_venue_observation_proof_is_authentic(proof)
        or proof.mode != "DIRECT"
        or proof.source_state_commitment != state.commitment
    ):
        raise ValueError("venue direct proof is not bound to its source state")
    scoped = _m2_venue_state_from_book(
        _m2_scoped_input_book(
            state.book,
            proof.retained_item,
            proof.retained_fact_item,
            proof.retained_coverage_items,
        )
    )
    if scoped.commitment != proof.serving_state_commitment:
        raise ValueError("venue direct proof does not match its serving state")
    return scoped


def _m2_apply_venue_input(
    state: _M2VenueState,
    execution: ExecutionSnapshot,
    proof: _M2VenueObservationProof,
) -> VenueRecoveryTransition:
    """Apply one venue input through the sole shared owner decision kernel."""

    if not _m2_venue_state_is_authentic(state):
        raise ValueError("venue state is not authentic")
    if not _m2_venue_observation_proof_is_authentic(proof):
        raise ValueError("venue observation proof is not authentic")
    if proof.mode == "REFERENCE":
        if (
            proof.source_state_commitment != state.commitment
            or proof.serving_state_commitment != state.commitment
        ):
            raise ValueError("reference venue proof is not current")
    elif proof.mode == "DIRECT":
        if proof.serving_state_commitment != state.commitment:
            raise ValueError("direct venue proof is not current")
    else:
        raise ValueError("venue proof mode is not admitted")
    return _apply_venue_input(state.book, execution, proof.item)


def _m2_apply_venue_input_from_direct_observation(
    state: _M2VenueState,
    execution: ExecutionSnapshot,
    proof: _M2VenueObservationProof,
) -> VenueRecoveryTransition:
    """Apply one direct proof exactly once through the shared owner kernel."""

    if not _m2_venue_state_is_authentic(state):
        raise ValueError("venue state is not authentic")
    if (
        not _m2_venue_observation_proof_is_authentic(proof)
        or proof.mode != "DIRECT"
        or proof.source_state_commitment != state.commitment
    ):
        raise ValueError("direct venue observation is not bound to its owner")
    direct_state = _m2_venue_state_from_direct_proof(state, proof)
    direct = _m2_apply_venue_input(direct_state, execution, proof)
    if not _m2_venue_transition_matches_direct_observation(
        state,
        execution,
        proof,
        direct,
    ):
        raise ValueError("direct venue transition is not bound to its observation")
    return direct


def _m2_venue_transition_matches_direct_observation(
    state: _M2VenueState,
    execution: ExecutionSnapshot,
    proof: _M2VenueObservationProof,
    transition: VenueRecoveryTransition,
) -> bool:
    """Verify the direct proof-to-transition chain without deciding again."""

    if (
        not _m2_venue_state_is_authentic(state)
        or type(execution) is not ExecutionSnapshot
        or not _m2_venue_observation_proof_is_authentic(proof)
        or proof.mode != "DIRECT"
        or proof.source_state_commitment != state.commitment
        or type(transition) is not VenueRecoveryTransition
    ):
        return False
    try:
        serving = _m2_venue_state_from_direct_proof(state, proof)
        source = _m2_venue_transition_source_item(transition)
        transition_proof = transition._protection_proof
        return bool(
            source == proof.item
            and transition_proof.predecessor_book_commitment
            == _protection_book_commitment(serving.book)
            and transition_proof.predecessor_execution_commitment
            == execution.commitment
            and transition_proof.book_commitment
            == _protection_book_commitment(transition.book)
            and transition_proof.execution_commitment == transition.execution.commitment
        )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False


def _m2_catch_up_broker_execution_fact(
    book: VenueRecoveryBook,
    predecessor: ExecutionSnapshot,
    successor: ExecutionSnapshot,
    fact: BrokerFillFact | BrokerTradeCorrectFact | BrokerTradeBustFact,
) -> VenueRecoveryTransition:
    """Bind one direct broker fact to its existing venue owner and registry."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be exact VenueRecoveryBook")
    if type(predecessor) is not ExecutionSnapshot:
        raise TypeError("predecessor must be exact ExecutionSnapshot")
    if type(successor) is not ExecutionSnapshot:
        raise TypeError("successor must be exact ExecutionSnapshot")
    if type(fact) not in {
        BrokerFillFact,
        BrokerTradeCorrectFact,
        BrokerTradeBustFact,
    }:
        raise TypeError("fact must be an exact broker execution fact")
    applied = _apply_broker_execution_fact(
        predecessor.position,
        predecessor.integrity,
        predecessor.root_heads,
        predecessor.seen_facts,
        fact,
    )
    expected = ExecutionSnapshot(
        applied.position,
        applied.integrity,
        applied.root_heads,
        applied.seen_facts,
    )
    if expected != successor or applied.disposition.value != "APPLIED":
        raise ValueError("successor is not the exact first application of fact")
    leg_key = VenueLegKey(
        fact.scope.broker,
        fact.scope.environment,
        fact.scope.account,
        fact.scope.order_id,
    )
    owner = book.owner(leg_key)
    current = None if owner is None else book._current_effect(owner.effect_id)
    if (
        owner is None
        or current is None
        or owner.leg_key != leg_key
        or owner.effect_id != current.scope.effect_id
        or current.scope.position_scope != fact.scope.position_scope
        or book.execution_registry_count is None
        or book.execution_registry_commitment is None
        or not book._execution_pair_matches_fast(predecessor)
    ):
        raise ValueError("broker fact has no exact current venue owner")
    source_binding = book.execution_binding(predecessor.position.scope)
    if source_binding is None:
        raise ValueError("broker fact source has no current venue binding")
    item = _BrokerExecutionRegistryCatchUp(
        VenueInputId(
            "m2-broker-execution-catch-up:"
            + _commit_parts(
                b"execution-core/m2-broker-execution-catch-up/v1",
                _canonical_value_commitment(fact),
            ).hex()
        ),
        VenueExecutionCheckpoint.from_execution(predecessor),
        book.execution_registry_count,
        book.execution_registry_commitment,
        source_binding,
        successor,
        fact,
        owner.effect_id,
        leg_key,
    )
    return _apply_venue_input(book, predecessor, item)


def apply_venue_recovery_input(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: object,
) -> VenueRecoveryTransition:
    """Apply one public broker observation or recovery input without I/O."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be the exact opaque VenueRecoveryBook type")
    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    if type(item) in {
        _BootstrapTargetRegistryInput,
        _BrokerExecutionRegistryCatchUp,
    }:
        raise TypeError("internal venue input is not publicly admitted")
    _require_exact_venue_recovery_input(item)
    if type(item) in {
        RequestedEffect,
        RecordDispatchClaim,
        CancelBeforeDispatch,
        RecordPendingVenueOperation,
        CloseAcceptanceSet,
    }:
        raise TypeError(
            "authority-changing capability is internal and not admitted publicly"
        )
    if _is_m2_venue_operation_item(item):
        state = _m2_venue_state_from_book(book)
        proof = _m2_venue_observation_from_book(state, item)
        return _m2_apply_venue_input(state, execution, proof)
    return _apply_venue_input(book, execution, item)


def _authority_request_effect(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RequestedEffect,
) -> VenueRecoveryTransition:
    if type(item) is not RequestedEffect:
        raise TypeError("item must be the exact RequestedEffect type")
    return _apply_venue_input(book, execution, item)


def _authority_request_acquisition_effect(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RequestedEffect,
) -> VenueRecoveryTransition:
    """Apply the one authority-sealed first acquisition BUY promotion.

    This is deliberately distinct from the generic authority bridge.  Only
    authority's specialized permit handler may reach it, and the venue reducer
    still requires the exact active R8 target record before it may consume it.
    """

    if type(item) is not RequestedEffect:
        raise TypeError("item must be the exact RequestedEffect type")
    promotion = (
        _mint_bootstrap_promotion_permit(book, execution, item)
        if book._bootstrap_bound_target_record(execution.position.scope) is not None
        else None
    )
    return _apply_venue_input(book, execution, item, promotion=promotion)


def _authority_claim_effect(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    item: RecordDispatchClaim,
) -> VenueRecoveryTransition:
    if type(item) is not RecordDispatchClaim:
        raise TypeError("item must be the exact RecordDispatchClaim type")
    return _apply_venue_input(book, execution, item)


def _require_authority_namespace(namespace: object) -> str:
    if type(namespace) is not str:
        raise TypeError("namespace must be str")
    if not namespace:
        raise ValueError("namespace must be nonempty")
    return cast(str, namespace)


def _authority_registry_source_is_current(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
) -> bool:
    binding = book.execution_binding(execution.position.scope)
    return bool(
        binding is not None
        and _binding_matches_execution(binding, execution)
        and book.execution_registry_count == execution.seen_facts.count
        and book.execution_registry_commitment == execution.seen_facts.commitment
        and book._execution_reconciliation_cursor_is_prefix(execution)
    )


def _authority_execution_for_scope(
    book: VenueRecoveryBook,
    source_execution: ExecutionSnapshot | None,
    position_scope: PositionScope,
    namespace: str,
) -> (
    tuple[
        VenueRecoveryBook,
        ExecutionSnapshot,
        tuple[VenueRecoveryTransition, ...],
    ]
    | None
):
    """Return one exact current target snapshot, publishing registry catch-up."""

    retained = book._execution_snapshot_by_scope.get(
        _position_scope_index_key(position_scope)
    )
    binding = book.execution_binding(position_scope)
    if (
        type(retained) is not ExecutionSnapshot
        or binding is None
        or not _binding_matches_execution(binding, retained)
        or not book._execution_reconciliation_cursor_is_prefix(retained)
        or book.execution_registry_count is None
        or book.execution_registry_commitment is None
        or retained.seen_facts.count > book.execution_registry_count
    ):
        return None

    transition_count, transition_head = book._reconciliation_cursor()
    target_registry_is_current = bool(
        retained.seen_facts.count == book.execution_registry_count
        and retained.seen_facts.commitment == book.execution_registry_commitment
    )
    if target_registry_is_current and (
        retained.reconciliation_transition_count == transition_count
        and retained.reconciliation_transition_head == transition_head
    ):
        if not book._execution_matches(retained, position_scope):
            return None
        return book, retained, ()

    if source_execution is None or not _authority_registry_source_is_current(
        book,
        source_execution,
    ):
        return None
    if not source_execution.seen_facts.has_prefix(
        retained.seen_facts.count,
        retained.seen_facts.commitment,
    ):
        return None
    catch_up = CatchUpExecutionRegistry(
        input_id=VenueInputId(
            f"{namespace}:execution-catch-up:{position_scope.symbol_id.value}"
        ),
        target_checkpoint=VenueExecutionCheckpoint.from_execution(retained),
        prior_account_registry_count=book.execution_registry_count,
        prior_account_registry_commitment=book.execution_registry_commitment,
        prior_source_binding=book.execution_binding(source_execution.position.scope),
        source_execution=source_execution,
    )
    caught_up = _apply_venue_input(book, retained, catch_up)
    if (
        caught_up.disposition is not VenueRecoveryDisposition.APPLIED
        or caught_up.execution.position.scope != position_scope
        or not caught_up.book._execution_matches(
            caught_up.execution,
            position_scope,
        )
    ):
        return None
    return caught_up.book, caught_up.execution, (caught_up,)


def _authority_execution_pair_for_scope(
    book: VenueRecoveryBook,
    source_execution: ExecutionSnapshot | None,
    position_scope: PositionScope,
    namespace: str,
) -> (
    tuple[
        VenueRecoveryBook,
        ExecutionSnapshot,
        VenueRecoveryBook,
        ExecutionSnapshot,
        tuple[VenueRecoveryTransition, ...],
    ]
    | None
):
    """Resolve one bounded authority refresh without exposing venue internals.

    The source must already be the exact account-current snapshot.  The pair
    contains only the retained target predecessor, at most one authenticated
    catch-up transition, and its resulting target snapshot.  It never
    materializes effects, owners, closures, or historical records.
    """

    if (
        type(source_execution) is not ExecutionSnapshot
        or type(position_scope) is not PositionScope
        or not _authority_registry_source_is_current(book, source_execution)
        or source_execution.account_reconciliation_required
    ):
        return None
    source_scope = source_execution.position.scope
    if not (
        position_scope.broker == source_scope.broker == book.scope.broker
        and position_scope.environment
        == source_scope.environment
        == book.scope.environment
        and position_scope.account == source_scope.account == book.scope.account
    ):
        return None
    predecessor_execution = book._execution_snapshot_by_scope.get(
        _position_scope_index_key(position_scope)
    )
    if type(predecessor_execution) is not ExecutionSnapshot:
        return None
    resolved = _authority_execution_for_scope(
        book,
        source_execution,
        position_scope,
        namespace,
    )
    if resolved is None:
        return None
    resulting_book, resulting_execution, transitions = resolved
    if transitions == ():
        if (
            resulting_book is not book
            or resulting_execution is not predecessor_execution
        ):
            return None
    elif (
        len(transitions) != 1
        or transitions[0].book is not resulting_book
        or transitions[0].execution is not resulting_execution
    ):
        return None
    return (
        book,
        predecessor_execution,
        resulting_book,
        resulting_execution,
        transitions,
    )


def _authority_bootstrap_unbound_target_pair_for_scope(
    book: VenueRecoveryBook,
    source_execution: ExecutionSnapshot,
    position_scope: PositionScope,
) -> tuple[VenueRecoveryBook, ExecutionSnapshot, VenueRecoveryTransition] | None:
    """Mint the one private, neutral first checkpoint for an absent target.

    Ordinary refresh and generic catch-up intentionally cannot reach this
    function.  It accepts either the exact empty-account genesis or one
    current bound same-account source, projects only that source's registry
    high-water onto the owner-derived flat target, and publishes the result
    with a sealed direct record before returning it to authority.
    """

    if (
        type(book) is not VenueRecoveryBook
        or type(source_execution) is not ExecutionSnapshot
        or type(position_scope) is not PositionScope
    ):
        raise TypeError("bootstrap target pair requires exact venue-owned inputs")
    venue_scope = book.scope
    source_scope = source_execution.position.scope
    if not (
        position_scope.broker == source_scope.broker == venue_scope.broker
        and position_scope.environment
        == source_scope.environment
        == venue_scope.environment
        and position_scope.account == source_scope.account == venue_scope.account
    ):
        return None
    target_genesis = ExecutionSnapshot.flat(position_scope)
    target_key = _position_scope_index_key(position_scope)
    target_summary = (
        book._authority_summary_by_scope.get(target_key) or _SymbolAuthoritySummary()
    )
    if (
        book.execution_binding(position_scope) is not None
        or book._execution_snapshot_by_scope.get(target_key) is not None
        or book._bootstrap_bound_target_by_scope.get(target_key) is not None
        or book._has_unresolved_execution_reconciliation(position_scope)
        or target_summary != _SymbolAuthoritySummary()
    ):
        return None

    source_kind: _BootstrapSourceKind
    target_execution: ExecutionSnapshot
    if source_execution == target_genesis:
        # Exact equality with a freshly constructed empty book rules out a
        # hidden input, binding, registry, reconciliation cursor, or another
        # account-level history item.  No broader account scan is involved.
        if book != VenueRecoveryBook.empty(venue_scope):
            return None
        source_kind = _BootstrapSourceKind.EMPTY_ACCOUNT
        target_execution = target_genesis
    else:
        if (
            source_scope == position_scope
            or book._bootstrap_bound_target_record(source_scope) is not None
            or source_execution.account_reconciliation_required
            or not _authority_registry_source_is_current(book, source_execution)
            or not book._execution_reconciliation_cursor_matches(source_execution)
            or not book._execution_matches(source_execution, source_scope)
            or not source_execution.seen_facts.has_prefix(
                target_genesis.seen_facts.count,
                target_genesis.seen_facts.commitment,
            )
        ):
            return None
        source_kind = _BootstrapSourceKind.SAME_ACCOUNT_SOURCE
        transition_count, transition_head = book._reconciliation_cursor()
        try:
            target_execution = _project_execution_registry(
                target_genesis,
                source_execution,
                reconciliation_transition_count=transition_count,
                reconciliation_transition_head=transition_head,
            )
        except (TypeError, ValueError):
            return None
        if (
            target_execution.position.raw_quantity != 0
            or target_execution.position.root_count != 0
            or target_execution.integrity is not PositionIntegrity.CONSISTENT
            or target_execution.account_reconciliation_required
        ):
            return None

    if (
        target_execution.position.scope != position_scope
        or target_execution.reconciliation_transition_count
        != book._reconciliation_cursor()[0]
        or target_execution.reconciliation_transition_head
        != book._reconciliation_cursor()[1]
    ):
        return None
    bootstrap_input = _new_bootstrap_target_registry_input(
        application_generation_id=venue_scope.generation,
        source_kind=source_kind,
        position_scope=position_scope,
        source_execution_commitment=source_execution.commitment,
        target_genesis_execution_commitment=target_genesis.commitment,
        target_execution_commitment=target_execution.commitment,
        prior_account_registry_count=target_execution.seen_facts.count,
        prior_account_registry_commitment=target_execution.seen_facts.commitment,
        reconciliation_transition_count=(
            target_execution.reconciliation_transition_count
        ),
        reconciliation_transition_head=target_execution.reconciliation_transition_head,
    )
    try:
        checkpoint_book, binding = _book_with_bootstrap_target_checkpoint(
            book,
            target_execution,
            bootstrap_input,
        )
        checkpoint_book = _book_with_staged_bootstrap_record_map_seal(
            checkpoint_book,
            position_scope,
            _bootstrap_bound_target_record_map_seal(
                application_generation_id=venue_scope.generation,
                position_scope=position_scope,
                source_kind=source_kind,
                source_execution_commitment=source_execution.commitment,
                target_genesis_execution_commitment=target_genesis.commitment,
                target_execution_commitment=target_execution.commitment,
                binding=binding,
                account_registry_count=target_execution.seen_facts.count,
                account_registry_commitment=target_execution.seen_facts.commitment,
                reconciliation_transition_count=(
                    target_execution.reconciliation_transition_count
                ),
                reconciliation_transition_head=(
                    target_execution.reconciliation_transition_head
                ),
                bootstrap_input_id=bootstrap_input.input_id,
                bootstrap_input_commitment=bootstrap_input.commitment,
                bootstrap_target_execution_commitment=(target_execution.commitment),
                bootstrap_account_registry_count=target_execution.seen_facts.count,
                bootstrap_account_registry_commitment=(
                    target_execution.seen_facts.commitment
                ),
                bootstrap_reconciliation_transition_count=(
                    target_execution.reconciliation_transition_count
                ),
                bootstrap_reconciliation_transition_head=(
                    target_execution.reconciliation_transition_head
                ),
                checkpoint_input_id=bootstrap_input.input_id,
                checkpoint_command_commitment=(
                    _protection_command_commitment(bootstrap_input)
                ),
            ),
        )
    except (TypeError, ValueError):
        return None
    predecessor_cursor = _protection_genesis_cursor()
    summary = _SymbolAuthoritySummary()
    command_commitment = _protection_command_commitment(bootstrap_input)
    predecessor_book_commitment = _protection_book_commitment(book)
    checkpoint_book_commitment = _protection_book_commitment(checkpoint_book)
    target_checkpoint = VenueExecutionCheckpoint.from_execution(target_execution)
    target_genesis_checkpoint = VenueExecutionCheckpoint.from_execution(target_genesis)
    cursor = _next_protection_cursor(
        predecessor_cursor,
        position_scope,
        None,
        book.scope,
        checkpoint_book.scope,
        predecessor_book_commitment,
        checkpoint_book_commitment,
        target_genesis.commitment,
        target_execution.commitment,
        target_genesis_checkpoint,
        target_checkpoint,
        summary,
        summary,
        None,
        binding,
        False,
        True,
        True,
        True,
        command_commitment,
        VenueRecoveryDisposition.APPLIED,
        0,
    )
    proof = _ProtectionTransitionProof(
        position_scope=position_scope,
        predecessor_cursor=predecessor_cursor,
        cursor=cursor,
        predecessor_book_scope=book.scope,
        book_scope=checkpoint_book.scope,
        predecessor_book_commitment=predecessor_book_commitment,
        book_commitment=checkpoint_book_commitment,
        predecessor_execution_commitment=target_genesis.commitment,
        execution_commitment=target_execution.commitment,
        predecessor_execution_checkpoint=target_genesis_checkpoint,
        execution_checkpoint=target_checkpoint,
        predecessor_summary=summary,
        summary=summary,
        predecessor_binding=None,
        binding=binding,
        predecessor_execution_binding_matches=False,
        execution_binding_matches=True,
        predecessor_account_reconciliation_clear=True,
        account_reconciliation_clear=True,
        command_commitment=command_commitment,
        disposition=VenueRecoveryDisposition.APPLIED,
        quantity_delta=0,
    )
    try:
        checkpoint_book = _with_protection_cursor(
            checkpoint_book,
            position_scope,
            cursor,
            proof,
        )
        record = _new_bootstrap_bound_target_record(
            application_generation_id=venue_scope.generation,
            position_scope=position_scope,
            source_kind=source_kind,
            source_execution_commitment=source_execution.commitment,
            target_genesis_execution_commitment=target_genesis.commitment,
            target_execution_commitment=target_execution.commitment,
            binding=binding,
            account_registry_count=target_execution.seen_facts.count,
            account_registry_commitment=target_execution.seen_facts.commitment,
            reconciliation_transition_count=(
                target_execution.reconciliation_transition_count
            ),
            reconciliation_transition_head=(
                target_execution.reconciliation_transition_head
            ),
            bootstrap_input=bootstrap_input,
            neutral_checkpoint_proof=proof,
        )
        resulting_book = _book_with_bootstrap_bound_target_record(
            checkpoint_book,
            record,
        )
    except (TypeError, ValueError):
        return None
    if not resulting_book._bootstrap_bound_target_pair_matches(
        target_execution,
        position_scope,
    ):
        return None
    result = object.__new__(VenueRecoveryTransition)
    object.__setattr__(result, "book", resulting_book)
    object.__setattr__(result, "execution", target_execution)
    object.__setattr__(result, "disposition", VenueRecoveryDisposition.APPLIED)
    object.__setattr__(result, "quantity_delta", 0)
    object.__setattr__(result, "_source_item", bootstrap_input)
    object.__setattr__(result, "_protection_proof", proof)
    object.__setattr__(result, "_protection_proof_commitment", proof.commitment)
    object.__setattr__(result, "_acquisition_fact_proof", None)
    object.__setattr__(result, "_acquisition_fact_proof_commitment", None)
    return resulting_book, target_execution, result


def _authority_stand_down_requested_effect(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    effect_id: EffectId,
    namespace: str,
) -> tuple[VenueRecoveryBook, tuple[VenueRecoveryTransition, ...]] | None:
    """Atomically stand down and close one exact never-dispatched request."""

    if type(book) is not VenueRecoveryBook:
        raise TypeError("book must be the exact opaque VenueRecoveryBook type")
    if type(execution) is not ExecutionSnapshot:
        raise TypeError("execution must be the exact ExecutionSnapshot type")
    if type(effect_id) is not EffectId:
        raise TypeError("effect_id must be EffectId")
    namespace = _require_authority_namespace(namespace)
    effect = book._current_effect(effect_id)
    if (
        effect is None
        or effect.state is not BrokerEffectState.REQUESTED
        or effect.claim_occurrence_id is not None
        or effect.acceptance_set_state is not AcceptanceSetState.OPEN
        or book._leg_summary(effect_id).owner_count != 0
        or book._has_effect_reconciliation(effect_id)
    ):
        return None
    stand_down = CancelBeforeDispatch(
        input_id=VenueInputId(f"{namespace}:stand-down:{effect_id.value}"),
        effect_id=effect_id,
    )
    close = CloseAcceptanceSet(
        input_id=VenueInputId(f"{namespace}:close:{effect_id.value}"),
        effect_id=effect_id,
        proof=AcceptanceProof(
            kind=AcceptanceProofKind.NEVER_DISPATCHED,
            effect_scope=effect.scope,
            claim_occurrence_id=None,
            evidence_reference=EvidenceReference(
                f"{namespace}:never-dispatched:{effect_id.value}"
            ),
            evidence_digest=_commit_parts(
                b"execution-core/authority-never-dispatched/v1",
                _encode_text(namespace),
                _encode_text(effect_id.value),
            ),
        ),
    )
    if (
        book._input_record(stand_down.input_id) is not None
        or book._input_record(close.input_id) is not None
    ):
        return None
    stood_down = _apply_venue_input(book, execution, stand_down)
    if stood_down.disposition is not VenueRecoveryDisposition.APPLIED:
        return None
    closed = _apply_venue_input(stood_down.book, execution, close)
    if closed.disposition is not VenueRecoveryDisposition.APPLIED:
        return None
    return closed.book, (stood_down, closed)


def _authority_stand_down_account_requested_effects(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    namespace: str,
) -> tuple[VenueRecoveryBook, tuple[VenueRecoveryTransition, ...]] | None:
    """Atomically stand down every account request that never gained a claim."""

    namespace = _require_authority_namespace(namespace)
    candidates = book._account_unclaimed_requested_effect_ids
    grouped: list[tuple[PositionScope, list[EffectId]]] = []
    group_index: dict[PositionScope, int] = {}
    for effect_id in candidates:
        effect = book._current_effect(effect_id)
        if (
            effect is None
            or effect.state is not BrokerEffectState.REQUESTED
            or effect.claim_occurrence_id is not None
            or effect.acceptance_set_state is not AcceptanceSetState.OPEN
            or book._leg_summary(effect_id).owner_count != 0
            or book._has_effect_reconciliation(effect_id)
        ):
            return None
        position_scope = effect.scope.position_scope
        index = group_index.get(position_scope)
        if index is None:
            group_index[position_scope] = len(grouped)
            grouped.append((position_scope, [effect_id]))
        else:
            grouped[index][1].append(effect_id)
        for input_id in (
            VenueInputId(f"{namespace}:stand-down:{effect_id.value}"),
            VenueInputId(f"{namespace}:close:{effect_id.value}"),
        ):
            if book._input_record(input_id) is not None:
                return None
    source_execution = (
        execution if _authority_registry_source_is_current(book, execution) else None
    )
    if source_execution is None:
        return None
    current = book
    transitions: list[VenueRecoveryTransition] = []
    for position_scope, effect_ids in grouped:
        resolved = _authority_execution_for_scope(
            current,
            source_execution,
            position_scope,
            namespace,
        )
        if resolved is None:
            return None
        current, target_execution, catch_up_transitions = resolved
        transitions.extend(catch_up_transitions)
        if target_execution.position.scope == source_execution.position.scope:
            source_execution = target_execution
        for effect_id in effect_ids:
            updated = _authority_stand_down_requested_effect(
                current,
                target_execution,
                effect_id,
                namespace,
            )
            if updated is None:
                return None
            current, applied = updated
            transitions.extend(applied)
    return current, tuple(transitions)


def _authority_cancel_request_for_leg(
    book: VenueRecoveryBook,
    position_scope: PositionScope,
    mandate_id: MandateId,
    namespace: str,
    ordinal: int,
    leg_key: VenueLegKey,
) -> RequestedEffect | None:
    owner = book.owner(leg_key)
    if owner is None:
        return None
    target = book._current_effect(owner.effect_id)
    if target is None or target.scope.position_scope != position_scope:
        return None
    suffix = f"{ordinal}:{leg_key.order_id.value}"
    return RequestedEffect(
        input_id=VenueInputId(f"{namespace}:cancel-request:{suffix}"),
        effect_id=EffectId(f"{namespace}:cancel-effect:{suffix}"),
        request_occurrence_id=RequestOccurrenceId(
            f"{namespace}:cancel-occurrence:{suffix}"
        ),
        mandate_id=mandate_id,
        kind=EffectKind.CANCEL,
        client_order_id=None,
        symbol_id=position_scope.symbol_id,
        side=target.scope.side,
        quantity=target.scope.quantity,
        economic_scope=_commit_parts(
            b"execution-core/authority-cancel-scope/v1",
            _encode_text(namespace),
            _leg_index_key(leg_key),
        ),
        target_leg_key=leg_key,
    )


def _authority_begin_symbol_flatten(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
    mandate_id: MandateId,
    namespace: str,
) -> (
    tuple[
        VenueRecoveryBook,
        tuple[EffectId, ...],
        tuple[VenueRecoveryTransition, ...],
    ]
    | None
):
    """Apply one all-or-none safely-local stand-down and known-leg cancel set."""

    if type(position_scope) is not PositionScope:
        raise TypeError("position_scope must be the exact PositionScope type")
    if type(mandate_id) is not MandateId:
        raise TypeError("mandate_id must be MandateId")
    namespace = _require_authority_namespace(namespace)
    view = _venue_authority_view(book, execution, position_scope, None)
    summary = (
        book._authority_summary_by_scope.get(_position_scope_index_key(position_scope))
        or _SymbolAuthoritySummary()
    )
    if (
        not view.execution_binding_matches
        or not view.account_reconciliation_clear
        or view.unknown_buy_effect_count
    ):
        return None
    cancel_requests: list[RequestedEffect] = []
    for ordinal, leg_key in enumerate(
        summary.known_cancellable_buy_leg_keys,
        start=1,
    ):
        request = _authority_cancel_request_for_leg(
            book,
            position_scope,
            mandate_id,
            namespace,
            ordinal,
            leg_key,
        )
        if request is None or not _target_is_exact_active(
            book,
            _effect_scope(book, request),
        ):
            return None
        if (
            book._current_effect(request.effect_id) is not None
            or book._has_request_occurrence(request.request_occurrence_id)
            or book._input_record(request.input_id) is not None
        ):
            return None
        cancel_requests.append(request)
    for effect_id in summary.stand_downable_buy_effect_ids:
        if book._current_effect(effect_id) is None:
            return None
        for input_id in (
            VenueInputId(f"{namespace}:stand-down:{effect_id.value}"),
            VenueInputId(f"{namespace}:close:{effect_id.value}"),
        ):
            if book._input_record(input_id) is not None:
                return None

    current = book
    transitions: list[VenueRecoveryTransition] = []
    for effect_id in summary.stand_downable_buy_effect_ids:
        updated = _authority_stand_down_requested_effect(
            current,
            execution,
            effect_id,
            namespace,
        )
        if updated is None:
            return None
        current, applied = updated
        transitions.extend(applied)
    created: list[EffectId] = []
    for request in cancel_requests:
        transition = _authority_request_effect(current, execution, request)
        if transition.disposition is not VenueRecoveryDisposition.APPLIED:
            return None
        current = transition.book
        transitions.append(transition)
        created.append(request.effect_id)
    return current, tuple(created), tuple(transitions)


def _authority_symbol_flatten_ready(
    book: VenueRecoveryBook,
    execution: ExecutionSnapshot,
    position_scope: PositionScope,
) -> bool:
    view = _venue_authority_view(book, execution, position_scope, None)
    return bool(
        view.execution_binding_matches
        and view.account_reconciliation_clear
        and view.blocking_buy_effect_count == 0
        and view.stand_downable_buy_count == 0
        and view.known_cancellable_buy_leg_count == 0
        and view.known_cancel_pending_buy_leg_count == 0
        and view.waiting_buy_parent_count == 0
        and view.unknown_buy_effect_count == 0
    )


__all__ = [
    "AcceptanceSetState",
    "BrokerEffectState",
    "CatchUpExecutionRegistry",
    "ClientIdentityBinding",
    "DiscoverVenueLeg",
    "EffectKind",
    "ExecutionRegistryReconciliationRecord",
    "ObserveVenueStatus",
    "PendingVenueOperation",
    "RecordTransportOutcome",
    "RecoverClaimedEffect",
    "VenueAttemptState",
    "VenueAcquisitionCorrelation",
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
