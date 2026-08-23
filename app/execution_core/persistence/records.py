"""Immutable typed records for the M2-I3 SQLite repository boundary.

The accepted SQLite schema stores exact M1 identities and values in scalar
columns. These records keep the in-process side typed; repository code is
solely responsible for translating them through the accepted durable codec
and profile constructors. No record opens a database, discovers config, or
performs reducer work.
"""

from __future__ import annotations as _annotations

import enum as _enum
from dataclasses import dataclass as _dataclass
from hashlib import sha256 as _sha256
from typing import Generic as _Generic
from typing import TypeVar as _TypeVar
from typing import cast as _cast

from .. import durable_codec as _durable_codec
from .. import identity as _identity
from .. import profiles as _profiles
from .. import values as _values
from ..fills import _commit_parts as _commit_parts
from ..fills import _encode_int as _encode_int
from ..fills import _encode_text as _encode_text
from . import operations as _operations


class RepositoryOutcomeKind(_enum.Enum):
    APPLIED = "applied"
    FOUND = "found"
    ABSENT = "absent"
    CONFLICT = "conflict"
    INTEGRITY_FAILURE = "integrity-failure"


_RecordT = _TypeVar("_RecordT")


def _require_sha256_text(name: str, value: object) -> str:
    """Require one exact lowercase SHA-256 textual binding."""

    if type(value) is not str:
        raise TypeError(f"{name} must be exact text")
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{name} must be lowercase SHA-256 hexadecimal text")
    return value


@_dataclass(frozen=True, slots=True)
class RepositoryOutcome(_Generic[_RecordT]):
    """Explicit result; no outcome implies serving eligibility by itself."""

    kind: RepositoryOutcomeKind
    record: _RecordT | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not RepositoryOutcomeKind:
            raise TypeError("repository outcome kind must be exact")
        if (self.kind is RepositoryOutcomeKind.FOUND) != (self.record is not None):
            raise ValueError("only FOUND outcomes may carry one complete record")


@_dataclass(frozen=True, slots=True)
class ApplicationGenerationRecord:
    application_generation_id: _identity.ApplicationGenerationId
    selected_execution_profile_id: str
    selected_market_source_profile_id: str
    activation_ordinal: int


@_dataclass(frozen=True, slots=True)
class ScopeRecord:
    scope_id: int
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    symbol: _identity.SymbolId


@_dataclass(frozen=True, slots=True)
class AcquisitionGenerationRecord:
    acquisition_generation_id: _identity.AcquisitionGenerationId
    scope_id: int
    status: str
    successor_ordinal: int
    predecessor_generation_id: _identity.AcquisitionGenerationId | None
    mandate_commitment_sha256: str
    emergency_compatibility_sha256: str


@_dataclass(frozen=True, slots=True)
class AcquisitionGenerationCurrentRecord:
    acquisition_generation_id: _identity.AcquisitionGenerationId
    scope_id: int
    current_economics_head_ordinal: int
    unresolved_effect_count: int
    active_protection_count: int


@_dataclass(frozen=True, slots=True)
class KernelCheckpointRecord:
    application_generation_id: _identity.ApplicationGenerationId
    currentness_head_ordinal: int
    checkpoint_sha256: str
    checkpoint_version_ordinal: int


@_dataclass(frozen=True, slots=True)
class RuntimeCheckpointPayloadRecord:
    """One exact retained canonical checkpoint payload and its bound coordinates."""

    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str
    currentness_head_ordinal: int
    checkpoint_version_ordinal: int
    payload_bytes: bytes
    payload_length: int
    payload_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.application_generation_id)
            is not _identity.ApplicationGenerationId
        ):
            raise TypeError("checkpoint application generation must be exact")
        _identity.ApplicationGenerationId(self.application_generation_id.value)
        _require_sha256_text("checkpoint execution profile", self.execution_profile_id)
        _require_sha256_text(
            "checkpoint market-source profile", self.market_source_profile_id
        )
        if type(self.currentness_head_ordinal) is not int:
            raise TypeError("checkpoint head ordinal must be an exact integer")
        if self.currentness_head_ordinal < 0:
            raise ValueError("checkpoint head ordinal must be non-negative")
        if type(self.checkpoint_version_ordinal) is not int:
            raise TypeError("checkpoint version ordinal must be an exact integer")
        if self.checkpoint_version_ordinal < 1:
            raise ValueError("checkpoint version ordinal must be positive")
        if type(self.payload_bytes) is not bytes:
            raise TypeError("checkpoint payload bytes must be exact bytes")
        if not self.payload_bytes:
            raise ValueError("checkpoint payload bytes must be nonempty")
        if type(self.payload_length) is not int:
            raise TypeError("checkpoint payload length must be an exact integer")
        if self.payload_length != len(self.payload_bytes):
            raise ValueError("checkpoint payload length does not match payload bytes")
        _require_sha256_text("checkpoint payload SHA-256", self.payload_sha256)
        if self.payload_sha256 != _sha256(self.payload_bytes).hexdigest():
            raise ValueError("checkpoint payload SHA-256 does not match payload bytes")


@_dataclass(frozen=True, slots=True)
class DurableInputRecord:
    """Immutable technical input claim with its exact coordinate envelope."""

    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    scope_id: int
    input_domain: _operations.OperationDomain
    session_id: _identity.SessionId | None
    acquisition_generation_id: _identity.AcquisitionGenerationId | None
    market_source_profile_id: str | None
    stream_generation_id: _identity.MarketStreamGenerationId | None
    input_identity_sha256: str
    operation_contract_version: int
    canonical_payload_bytes: bytes
    payload_sha256: str
    technical_state: str
    created_ordinal: int

    def __post_init__(self) -> None:
        if (
            type(self.application_generation_id)
            is not _identity.ApplicationGenerationId
        ):
            raise TypeError("durable input application generation must be exact")
        _identity.ApplicationGenerationId(self.application_generation_id.value)
        _require_sha256_text(
            "durable input execution profile", self.execution_profile_id
        )
        if type(self.scope_id) is not int:
            raise TypeError("durable input scope id must be an exact integer")
        if self.scope_id < 1:
            raise ValueError("durable input scope id must be positive")
        if type(self.input_domain) is not _operations.OperationDomain:
            raise TypeError("durable input domain must be exact OperationDomain")
        _require_optional_exact_identity(
            "durable input session", self.session_id, _identity.SessionId
        )
        _require_optional_exact_identity(
            "durable input acquisition generation",
            self.acquisition_generation_id,
            _identity.AcquisitionGenerationId,
        )
        if self.market_source_profile_id is not None:
            _require_sha256_text(
                "durable input market-source profile", self.market_source_profile_id
            )
        _require_optional_exact_identity(
            "durable input stream generation",
            self.stream_generation_id,
            _identity.MarketStreamGenerationId,
        )
        _validate_durable_input_coordinates(self)
        _require_sha256_text("durable input identity", self.input_identity_sha256)
        if type(self.operation_contract_version) is not int:
            raise TypeError("durable input operation version must be an exact integer")
        if self.operation_contract_version != 1:
            raise ValueError("durable input operation version must be literal 1")
        if type(self.canonical_payload_bytes) is not bytes:
            raise TypeError("durable input payload bytes must be exact bytes")
        if not self.canonical_payload_bytes:
            raise ValueError("durable input payload bytes must be nonempty")
        _require_sha256_text("durable input payload SHA-256", self.payload_sha256)
        if self.payload_sha256 != _sha256(self.canonical_payload_bytes).hexdigest():
            raise ValueError(
                "durable input payload SHA-256 does not match payload bytes"
            )
        if type(self.technical_state) is not str:
            raise TypeError("durable input technical state must be exact text")
        if self.technical_state not in {
            "CLAIMED",
            "TERMINAL",
            "RECONCILIATION_PENDING",
        }:
            raise ValueError("durable input technical state is not admitted")
        if type(self.created_ordinal) is not int:
            raise TypeError("durable input created ordinal must be an exact integer")
        if self.created_ordinal < 1:
            raise ValueError("durable input created ordinal must be positive")


def _require_optional_exact_identity(
    name: str,
    value: object,
    owner: type[object],
) -> None:
    """Require an exact immutable identity when one coordinate is present."""

    if value is not None and type(value) is not owner:
        raise TypeError(f"{name} must be exact {owner.__name__} or None")


def _validate_durable_input_coordinates(record: DurableInputRecord) -> None:
    """Enforce the four frozen operation-coordinate shapes without inference."""

    domain = record.input_domain
    has_session = record.session_id is not None
    has_acquisition = record.acquisition_generation_id is not None
    has_market = record.market_source_profile_id is not None
    has_stream = record.stream_generation_id is not None
    if domain is _operations.OperationDomain.MARKET_OCCURRENCE:
        if not (has_session and has_acquisition and has_market and has_stream):
            raise ValueError(
                "market coordinates require session, acquisition, profile, and stream"
            )
        return
    if domain in {
        _operations.OperationDomain.BEGIN_ACQUISITION_GENERATION,
        _operations.OperationDomain.CREATE_ACQUISITION_EFFECT,
        _operations.OperationDomain.CLAIM_ACQUISITION_EFFECT,
        _operations.OperationDomain.BEGIN_ACQUISITION_PREEMPTION,
    }:
        if not (has_session and has_acquisition) or has_market or has_stream:
            raise ValueError(
                "acquisition coordinates require session and acquisition only"
            )
        return
    if domain is _operations.OperationDomain.VENUE_RECOVERY:
        if has_acquisition or has_market or has_stream:
            raise ValueError(
                "venue coordinates cannot retain acquisition or market coordinates"
            )
        return
    if has_session or has_acquisition or has_market or has_stream:
        raise ValueError(
            "execution coordinates cannot retain session or derived coordinates"
        )


@_dataclass(frozen=True, slots=True)
class SymbolControllerRecord:
    scope_id: int
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    live_acquisition_generation_id: _identity.AcquisitionGenerationId | None
    aggregate_quantity: int
    integrity_state: str
    currentness_head_ordinal: int
    controller_version_ordinal: int
    emergency_compatibility_sha256: str


@_dataclass(frozen=True, slots=True)
class RootFillRecord:
    root_fill_key_id: int
    scope_id: int
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    owner_generation_id: _identity.AcquisitionGenerationId
    root_fill_id: _identity.RootFillId
    current_fact_id: int | None
    current_kind: str | None
    current_authority: str | None
    current_side: str | None
    current_quantity: _values.Quantity | None
    current_price: _values.ReportedPrice | None
    economics_head_ordinal: int


@_dataclass(frozen=True, slots=True)
class ExecutionFactRecord:
    fact_id: int
    scope_id: int
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    root_fill_key_id: int
    source_event_id: _identity.SourceEventId
    order_id: _identity.OrderId
    side: str
    kind: str
    authority: str
    quantity: _values.Quantity
    price: _values.ReportedPrice | None
    request_occurrence_id: _identity.RequestOccurrenceId | None
    claim_occurrence_id: _identity.ClaimOccurrenceId | None
    prior_cumulative_quantity: _values.Quantity | None
    resulting_cumulative_quantity: _values.Quantity | None
    actor_id: _identity.ActorId | None
    reason_text: str | None
    evidence_reference: _identity.EvidenceReference | None
    predecessor_fact_id: int | None
    fact_ordinal: int


@_dataclass(frozen=True, slots=True)
class ExecutionFactHeadRecord:
    root_fill_key_id: int
    fact_id: int
    fact_ordinal: int


@_dataclass(frozen=True, slots=True)
class VenueEffectRecord:
    effect_id: int
    effect_external: _identity.EffectId
    scope_id: int
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    acquisition_generation_id: _identity.AcquisitionGenerationId
    generation_mandate_commitment_sha256: str
    expected_controller_head_ordinal: int
    expected_protection_version_ordinal: int
    authority_class: str
    request_occurrence_id: _identity.RequestOccurrenceId
    mandate_id: _identity.MandateId
    effect_kind: str
    client_order_id: _identity.ClientOrderId | None
    target_order_id: _identity.OrderId | None
    side: str
    quantity: _values.Quantity
    economic_scope: bytes
    lifecycle_state: str
    disposition: str
    closure_proof_kind: str | None
    closure_proof_digest: str | None
    closure_proof_evidence_id: int | None
    closure_proof_claim_id: int | None
    created_ordinal: int


@_dataclass(frozen=True, slots=True)
class VenueIdentityOwnerRecord:
    scope_id: int
    execution_profile_id: str
    owner_id: _identity.OrderId
    observation_id: _identity.VenueObservationId
    effect_id: int
    root_fill_key_id: int | None
    owner_generation_id: _identity.AcquisitionGenerationId
    admitted_after_effect_closed: bool


@_dataclass(frozen=True, slots=True)
class AcquisitionRootRouteRecord:
    root_fill_key_id: int
    scope_id: int
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    acquisition_generation_id: _identity.AcquisitionGenerationId
    effect_id: int
    owner_id: _identity.OrderId
    observation_id: _identity.VenueObservationId


@_dataclass(frozen=True, slots=True)
class DispatchClaimRecord:
    claim_id: int
    effect_id: int
    execution_profile_id: str
    claim_occurrence_id: _identity.ClaimOccurrenceId
    claim_ordinal: int


@_dataclass(frozen=True, slots=True)
class AcceptanceSetRecord:
    acceptance_set_id: int
    effect_id: int


@_dataclass(frozen=True, slots=True)
class AcceptanceEvidenceRecord:
    evidence_id: int
    acceptance_set_id: int
    effect_id: int
    evidence_kind: str
    proof_kind: str | None
    evidence_digest: str
    evidence_ordinal: int
    contradiction_owner_id: _identity.OrderId | None
    contradiction_observation_id: _identity.VenueObservationId | None


@_dataclass(frozen=True, slots=True)
class ClosureChainRecord:
    closure_id: int
    scope_id: int
    owner_id: _identity.OrderId
    ordinal: int
    effect_id: int
    closure_kind: str
    predecessor_closure_id: int | None


@_dataclass(frozen=True, slots=True)
class MarketStreamAuthorityRecord:
    stream_generation_id: _identity.MarketStreamGenerationId
    scope_id: int
    application_generation_id: _identity.ApplicationGenerationId
    acquisition_generation_id: _identity.AcquisitionGenerationId
    generation_mandate_commitment_sha256: str
    source_profile_id: str
    session_id: _identity.SessionId
    sequence_mode: str


@_dataclass(frozen=True, slots=True)
class MarketCursorRecord:
    stream_generation_id: _identity.MarketStreamGenerationId
    scope_id: int
    application_generation_id: _identity.ApplicationGenerationId
    acquisition_generation_id: _identity.AcquisitionGenerationId
    generation_mandate_commitment_sha256: str
    source_profile_id: str
    session_id: _identity.SessionId
    sequence_mode: str
    fixed_cursor_ordinal: int
    published_head_ordinal: int


@_dataclass(frozen=True, slots=True)
class ProtectionAuthorityRecord:
    scope_id: int
    authority_class: str
    active_stream_generation_id: _identity.MarketStreamGenerationId | None
    active_acquisition_generation_id: _identity.AcquisitionGenerationId | None
    active_generation_mandate_commitment_sha256: str | None
    active_source_profile_id: str | None
    active_session_id: _identity.SessionId | None
    active_sequence_mode: str | None
    expected_controller_head_ordinal: int
    state_commitment_sha256: str
    version_ordinal: int


@_dataclass(frozen=True, slots=True)
class CurrentProofRequest:
    """Exact coordinates whose direct proof must be returned atomically."""

    application_generation_id: _identity.ApplicationGenerationId
    scope_id: int
    root_fill_key_id: int | None = None
    effect_id: int | None = None
    owner_id: _identity.OrderId | None = None
    require_acceptance: bool = False
    require_closure: bool = False


@_dataclass(frozen=True, slots=True, init=False)
class CurrentProofSlice:
    """Opaque repository-issued proof of one exact direct-current selection."""

    request: CurrentProofRequest
    execution_profile: _profiles.ExecutionConnectionProfile
    market_source_profile: _profiles.MarketDataSourceProfile
    application_generation: ApplicationGenerationRecord
    scope: ScopeRecord
    acquisition_generation: AcquisitionGenerationRecord
    acquisition_current: AcquisitionGenerationCurrentRecord
    kernel_checkpoint: KernelCheckpointRecord
    symbol_controller: SymbolControllerRecord
    protection_authority: ProtectionAuthorityRecord
    market_stream_authority: MarketStreamAuthorityRecord | None
    market_cursor: MarketCursorRecord | None
    root_fill: RootFillRecord | None
    acquisition_root_route: AcquisitionRootRouteRecord | None
    execution_fact_head: ExecutionFactHeadRecord | None
    current_execution_fact: ExecutionFactRecord | None
    venue_effect: VenueEffectRecord | None
    dispatch_claim: DispatchClaimRecord | None
    venue_owner: VenueIdentityOwnerRecord | None
    acceptance_set: AcceptanceSetRecord | None
    acceptance_evidence: AcceptanceEvidenceRecord | None
    closure_head: ClosureChainRecord | None
    _binding: bytes
    _issuer: object

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CurrentProofSlice is repository-issued")

    @classmethod
    def _is_authentic(cls, proof: object) -> bool:
        if cls is not CurrentProofSlice or type(proof) is not cls:
            return False
        candidate = proof
        try:
            return (
                candidate._issuer is _CURRENT_PROOF_ISSUER
                and type(candidate._binding) is bytes
                and len(candidate._binding) == 32
                and candidate._binding == _current_proof_slice_binding(candidate)
            )
        except (AttributeError, TypeError, ValueError, OverflowError):
            return False

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("CurrentProofSlice cannot be subclassed")


_CURRENT_PROOF_ISSUER = object()


def _current_proof_optional_int(value: int | None) -> bytes:
    if value is None:
        return _commit_parts(b"execution-core/current-proof/optional-int/absent/v1")
    if type(value) is not int or value < 0:
        raise ValueError("current proof optional integer is invalid")
    return _commit_parts(
        b"execution-core/current-proof/optional-int/present/v1",
        _encode_int(value),
    )


def _current_proof_optional_identity(
    value: _identity.OrderId | None,
) -> bytes:
    if value is None:
        return _commit_parts(b"execution-core/current-proof/optional-owner/absent/v1")
    if type(value) is not _identity.OrderId:
        raise ValueError("current proof optional owner is invalid")
    return _commit_parts(
        b"execution-core/current-proof/optional-owner/present/v1",
        _encode_text(value.value),
    )


def _current_proof_request_binding(request: CurrentProofRequest) -> bytes:
    if (
        type(request) is not CurrentProofRequest
        or type(request.application_generation_id)
        is not _identity.ApplicationGenerationId
        or type(request.scope_id) is not int
        or request.scope_id < 0
        or type(request.require_acceptance) is not bool
        or type(request.require_closure) is not bool
    ):
        raise ValueError("current proof request is invalid")
    return _commit_parts(
        b"execution-core/current-proof/request/v1",
        _encode_text(request.application_generation_id.value),
        _encode_int(request.scope_id),
        _current_proof_optional_int(request.root_fill_key_id),
        _current_proof_optional_int(request.effect_id),
        _current_proof_optional_identity(request.owner_id),
        b"\x01" if request.require_acceptance else b"\x00",
        b"\x01" if request.require_closure else b"\x00",
    )


def _current_proof_optional_stream_binding(
    stream: MarketStreamAuthorityRecord | None,
    cursor: MarketCursorRecord | None,
) -> bytes:
    if stream is None and cursor is None:
        return _commit_parts(b"execution-core/current-proof/stream/absent/v1")
    if (
        type(stream) is not MarketStreamAuthorityRecord
        or type(cursor) is not MarketCursorRecord
        or stream.stream_generation_id != cursor.stream_generation_id
        or stream.scope_id != cursor.scope_id
        or stream.application_generation_id != cursor.application_generation_id
        or stream.acquisition_generation_id != cursor.acquisition_generation_id
        or (
            stream.generation_mandate_commitment_sha256
            != cursor.generation_mandate_commitment_sha256
        )
        or stream.source_profile_id != cursor.source_profile_id
        or stream.session_id != cursor.session_id
        or stream.sequence_mode != cursor.sequence_mode
    ):
        raise ValueError("current proof stream rows are invalid")
    return _commit_parts(
        b"execution-core/current-proof/stream/present/v1",
        _encode_text(stream.stream_generation_id.value),
        _encode_int(stream.scope_id),
        _encode_text(stream.application_generation_id.value),
        _encode_text(stream.acquisition_generation_id.value),
        _encode_text(stream.generation_mandate_commitment_sha256),
        _encode_text(stream.source_profile_id),
        _encode_text(stream.session_id.value),
        _encode_text(stream.sequence_mode),
        _encode_int(cursor.fixed_cursor_ordinal),
        _encode_int(cursor.published_head_ordinal),
    )


def _current_proof_durable_atom_binding(atom: _durable_codec.DurableAtom) -> bytes:
    """Encode one exact M1 atom without reflection or a generic record codec."""

    if (
        type(atom) is not _durable_codec.DurableAtom
        or type(atom.contract_version) is not str
        or type(atom.type_tag) is not str
        or type(atom.fields) is not tuple
    ):
        raise ValueError("current proof durable atom is invalid")
    fields: list[bytes] = []
    for field in atom.fields:
        if type(field) is str:
            fields.append(
                _commit_parts(
                    b"execution-core/current-proof/atom-text/v1",
                    _encode_text(field),
                )
            )
        elif type(field) is _durable_codec.DurableAtom:
            fields.append(_current_proof_durable_atom_binding(field))
        else:
            raise ValueError("current proof durable atom field is invalid")
    return _commit_parts(
        b"execution-core/current-proof/durable-atom/v1",
        _encode_text(atom.contract_version),
        _encode_text(atom.type_tag),
        _encode_int(len(fields)),
        *fields,
    )


def _current_proof_m1_value_binding(value: object) -> bytes:
    """Bind one exact M1 value or identity through its owner codec."""

    try:
        atom = _durable_codec.encode_m1_value(_cast(_durable_codec._OwningValue, value))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("current proof record has an invalid M1 value") from error
    return _commit_parts(
        b"execution-core/current-proof/m1-value/v1",
        _current_proof_durable_atom_binding(atom),
    )


def _current_proof_record_field_binding(value: object) -> bytes:
    """Bind one closed record field with an exact scalar or owned M1 encoding."""

    if value is None:
        return _commit_parts(b"execution-core/current-proof/field/absent/v1")
    if type(value) is bool:
        return _commit_parts(
            b"execution-core/current-proof/field/bool/v1",
            b"\x01" if value else b"\x00",
        )
    if type(value) is int:
        return _commit_parts(
            b"execution-core/current-proof/field/int/v1",
            _encode_int(value),
        )
    if type(value) is str:
        return _commit_parts(
            b"execution-core/current-proof/field/text/v1",
            _encode_text(value),
        )
    if type(value) is bytes:
        return _commit_parts(b"execution-core/current-proof/field/bytes/v1", value)
    return _current_proof_m1_value_binding(value)


def _current_proof_record_binding(
    tag: bytes,
    fields: tuple[object, ...],
) -> bytes:
    """Bind one explicitly enumerated record without dataclass reflection."""

    if type(tag) is not bytes or type(fields) is not tuple:
        raise ValueError("current proof record binding shape is invalid")
    return _commit_parts(
        b"execution-core/current-proof/record/v1",
        tag,
        _encode_int(len(fields)),
        *(_current_proof_record_field_binding(field) for field in fields),
    )


def _current_proof_optional_record_binding(record: object) -> bytes:
    """Bind every exact optional direct row carried by ``CurrentProofSlice``."""

    if record is None:
        return _commit_parts(b"execution-core/current-proof/record/absent/v1")
    if type(record) is RootFillRecord:
        return _current_proof_record_binding(
            b"root-fill/v1",
            (
                record.root_fill_key_id,
                record.scope_id,
                record.application_generation_id,
                record.execution_profile_id,
                record.owner_generation_id,
                record.root_fill_id,
                record.current_fact_id,
                record.current_kind,
                record.current_authority,
                record.current_side,
                record.current_quantity,
                record.current_price,
                record.economics_head_ordinal,
            ),
        )
    if type(record) is AcquisitionRootRouteRecord:
        return _current_proof_record_binding(
            b"acquisition-root-route/v1",
            (
                record.root_fill_key_id,
                record.scope_id,
                record.application_generation_id,
                record.execution_profile_id,
                record.acquisition_generation_id,
                record.effect_id,
                record.owner_id,
                record.observation_id,
            ),
        )
    if type(record) is ExecutionFactHeadRecord:
        return _current_proof_record_binding(
            b"execution-fact-head/v1",
            (record.root_fill_key_id, record.fact_id, record.fact_ordinal),
        )
    if type(record) is ExecutionFactRecord:
        return _current_proof_record_binding(
            b"execution-fact/v1",
            (
                record.fact_id,
                record.scope_id,
                record.application_generation_id,
                record.execution_profile_id,
                record.root_fill_key_id,
                record.source_event_id,
                record.order_id,
                record.side,
                record.kind,
                record.authority,
                record.quantity,
                record.price,
                record.request_occurrence_id,
                record.claim_occurrence_id,
                record.prior_cumulative_quantity,
                record.resulting_cumulative_quantity,
                record.actor_id,
                record.reason_text,
                record.evidence_reference,
                record.predecessor_fact_id,
                record.fact_ordinal,
            ),
        )
    if type(record) is VenueEffectRecord:
        return _current_proof_record_binding(
            b"venue-effect/v1",
            (
                record.effect_id,
                record.effect_external,
                record.scope_id,
                record.application_generation_id,
                record.execution_profile_id,
                record.acquisition_generation_id,
                record.generation_mandate_commitment_sha256,
                record.expected_controller_head_ordinal,
                record.expected_protection_version_ordinal,
                record.authority_class,
                record.request_occurrence_id,
                record.mandate_id,
                record.effect_kind,
                record.client_order_id,
                record.target_order_id,
                record.side,
                record.quantity,
                record.economic_scope,
                record.lifecycle_state,
                record.disposition,
                record.closure_proof_kind,
                record.closure_proof_digest,
                record.closure_proof_evidence_id,
                record.closure_proof_claim_id,
                record.created_ordinal,
            ),
        )
    if type(record) is DispatchClaimRecord:
        return _current_proof_record_binding(
            b"dispatch-claim/v1",
            (
                record.claim_id,
                record.effect_id,
                record.execution_profile_id,
                record.claim_occurrence_id,
                record.claim_ordinal,
            ),
        )
    if type(record) is VenueIdentityOwnerRecord:
        return _current_proof_record_binding(
            b"venue-identity-owner/v1",
            (
                record.scope_id,
                record.execution_profile_id,
                record.owner_id,
                record.observation_id,
                record.effect_id,
                record.root_fill_key_id,
                record.owner_generation_id,
                record.admitted_after_effect_closed,
            ),
        )
    if type(record) is AcceptanceSetRecord:
        return _current_proof_record_binding(
            b"acceptance-set/v1",
            (record.acceptance_set_id, record.effect_id),
        )
    if type(record) is AcceptanceEvidenceRecord:
        return _current_proof_record_binding(
            b"acceptance-evidence/v1",
            (
                record.evidence_id,
                record.acceptance_set_id,
                record.effect_id,
                record.evidence_kind,
                record.proof_kind,
                record.evidence_digest,
                record.evidence_ordinal,
                record.contradiction_owner_id,
                record.contradiction_observation_id,
            ),
        )
    if type(record) is ClosureChainRecord:
        return _current_proof_record_binding(
            b"closure-chain/v1",
            (
                record.closure_id,
                record.scope_id,
                record.owner_id,
                record.ordinal,
                record.effect_id,
                record.closure_kind,
                record.predecessor_closure_id,
            ),
        )
    raise ValueError("current proof has an unknown optional record")


def _current_proof_optional_rows_binding(proof: CurrentProofSlice) -> bytes:
    """Validate and bind the full direct-row selection carried by one proof."""

    request = proof.request
    application = proof.application_generation
    scope = proof.scope
    acquisition = proof.acquisition_generation
    controller = proof.symbol_controller
    authority = proof.protection_authority
    root = proof.root_fill
    route = proof.acquisition_root_route
    fact_head = proof.execution_fact_head
    current_fact = proof.current_execution_fact
    effect = proof.venue_effect
    claim = proof.dispatch_claim
    owner = proof.venue_owner
    acceptance = proof.acceptance_set
    evidence = proof.acceptance_evidence
    closure = proof.closure_head

    if request.root_fill_key_id is None:
        if any(value is not None for value in (root, route, fact_head, current_fact)):
            raise ValueError("current proof has unrequested root rows")
    else:
        if (
            type(root) is not RootFillRecord
            or type(route) is not AcquisitionRootRouteRecord
            or type(fact_head) is not ExecutionFactHeadRecord
            or type(current_fact) is not ExecutionFactRecord
            or root.root_fill_key_id != request.root_fill_key_id
            or root.scope_id != scope.scope_id
            or root.application_generation_id != application.application_generation_id
            or root.execution_profile_id != scope.execution_profile_id
            or root.owner_generation_id != acquisition.acquisition_generation_id
            or route.root_fill_key_id != root.root_fill_key_id
            or route.scope_id != scope.scope_id
            or route.application_generation_id != application.application_generation_id
            or route.execution_profile_id != scope.execution_profile_id
            or route.acquisition_generation_id != acquisition.acquisition_generation_id
            or root.current_fact_id != fact_head.fact_id
            or root.economics_head_ordinal != fact_head.fact_ordinal
            or current_fact.root_fill_key_id != root.root_fill_key_id
            or current_fact.scope_id != scope.scope_id
            or current_fact.application_generation_id
            != application.application_generation_id
            or current_fact.execution_profile_id != scope.execution_profile_id
            or current_fact.fact_id != fact_head.fact_id
            or current_fact.fact_ordinal != fact_head.fact_ordinal
            or root.current_kind != current_fact.kind
            or root.current_authority != current_fact.authority
            or root.current_side != current_fact.side
            or root.current_quantity != current_fact.quantity
            or root.current_price != current_fact.price
        ):
            raise ValueError("current proof root rows do not agree")

    if request.effect_id is None:
        if effect is not None or claim is not None:
            raise ValueError("current proof has unrequested effect rows")
    else:
        if (
            type(effect) is not VenueEffectRecord
            or effect.effect_id != request.effect_id
            or effect.scope_id != scope.scope_id
            or effect.application_generation_id != application.application_generation_id
            or effect.execution_profile_id != scope.execution_profile_id
            or effect.acquisition_generation_id != acquisition.acquisition_generation_id
            or effect.generation_mandate_commitment_sha256
            != acquisition.mandate_commitment_sha256
            or effect.authority_class != authority.authority_class
            or effect.expected_controller_head_ordinal
            != controller.currentness_head_ordinal
            or effect.expected_protection_version_ordinal != authority.version_ordinal
        ):
            raise ValueError("current proof effect row does not agree")
        if effect.lifecycle_state in ("REQUESTED", "CANCELED_BEFORE_DISPATCH"):
            if claim is not None:
                raise ValueError("current proof has an unexpected dispatch claim")
        elif (
            type(claim) is not DispatchClaimRecord
            or claim.effect_id != effect.effect_id
            or claim.execution_profile_id != effect.execution_profile_id
        ):
            raise ValueError("current proof dispatch claim does not agree")
        if route is not None and route.effect_id != effect.effect_id:
            raise ValueError("current proof root route does not match effect")

    if request.owner_id is None:
        if owner is not None:
            raise ValueError("current proof has an unrequested owner row")
    else:
        if (
            type(effect) is not VenueEffectRecord
            or type(owner) is not VenueIdentityOwnerRecord
            or owner.owner_id != request.owner_id
            or owner.scope_id != scope.scope_id
            or owner.execution_profile_id != scope.execution_profile_id
            or owner.effect_id != effect.effect_id
            or owner.owner_generation_id != acquisition.acquisition_generation_id
        ):
            raise ValueError("current proof owner row does not agree")
        if route is not None and (
            route.owner_id != owner.owner_id
            or route.observation_id != owner.observation_id
        ):
            raise ValueError("current proof root route does not match owner")

    if request.require_acceptance:
        if (
            type(effect) is not VenueEffectRecord
            or type(acceptance) is not AcceptanceSetRecord
            or type(evidence) is not AcceptanceEvidenceRecord
            or acceptance.effect_id != effect.effect_id
            or evidence.acceptance_set_id != acceptance.acceptance_set_id
            or evidence.effect_id != effect.effect_id
        ):
            raise ValueError("current proof acceptance rows do not agree")
    elif acceptance is not None or evidence is not None:
        raise ValueError("current proof has unrequested acceptance rows")

    if request.require_closure:
        if (
            type(effect) is not VenueEffectRecord
            or type(owner) is not VenueIdentityOwnerRecord
            or type(closure) is not ClosureChainRecord
            or closure.scope_id != scope.scope_id
            or closure.owner_id != owner.owner_id
            or closure.effect_id != effect.effect_id
        ):
            raise ValueError("current proof closure row does not agree")
    elif closure is not None:
        raise ValueError("current proof has an unrequested closure row")

    return _commit_parts(
        b"execution-core/current-proof/optional-rows/v1",
        _current_proof_optional_record_binding(root),
        _current_proof_optional_record_binding(route),
        _current_proof_optional_record_binding(fact_head),
        _current_proof_optional_record_binding(current_fact),
        _current_proof_optional_record_binding(effect),
        _current_proof_optional_record_binding(claim),
        _current_proof_optional_record_binding(owner),
        _current_proof_optional_record_binding(acceptance),
        _current_proof_optional_record_binding(evidence),
        _current_proof_optional_record_binding(closure),
    )


def _current_proof_slice_binding(proof: CurrentProofSlice) -> bytes:
    """Validate and bind the exact currentness envelope consumed by the codec."""

    if (
        type(proof.request) is not CurrentProofRequest
        or type(proof.execution_profile) is not _profiles.ExecutionConnectionProfile
        or type(proof.market_source_profile) is not _profiles.MarketDataSourceProfile
        or type(proof.application_generation) is not ApplicationGenerationRecord
        or type(proof.scope) is not ScopeRecord
        or type(proof.acquisition_generation) is not AcquisitionGenerationRecord
        or type(proof.acquisition_current) is not AcquisitionGenerationCurrentRecord
        or type(proof.kernel_checkpoint) is not KernelCheckpointRecord
        or type(proof.symbol_controller) is not SymbolControllerRecord
        or type(proof.protection_authority) is not ProtectionAuthorityRecord
    ):
        raise ValueError("current proof has invalid exact rows")
    request = proof.request
    application = proof.application_generation
    scope = proof.scope
    acquisition = proof.acquisition_generation
    current = proof.acquisition_current
    checkpoint = proof.kernel_checkpoint
    controller = proof.symbol_controller
    authority = proof.protection_authority
    if (
        request.application_generation_id != application.application_generation_id
        or request.scope_id != scope.scope_id
        or scope.application_generation_id != application.application_generation_id
        or scope.execution_profile_id != application.selected_execution_profile_id
        or proof.execution_profile.connection_profile_id
        != application.selected_execution_profile_id
        or proof.execution_profile.application_generation
        != application.application_generation_id.value
        or proof.market_source_profile.market_source_profile_id
        != application.selected_market_source_profile_id
        or acquisition.scope_id != scope.scope_id
        or acquisition.status != "LIVE"
        or current.acquisition_generation_id != acquisition.acquisition_generation_id
        or current.scope_id != scope.scope_id
        or checkpoint.application_generation_id != application.application_generation_id
        or checkpoint.currentness_head_ordinal != controller.currentness_head_ordinal
        or controller.scope_id != scope.scope_id
        or controller.application_generation_id != application.application_generation_id
        or controller.execution_profile_id != scope.execution_profile_id
        or controller.live_acquisition_generation_id
        != acquisition.acquisition_generation_id
        or authority.scope_id != scope.scope_id
        or authority.expected_controller_head_ordinal
        != controller.currentness_head_ordinal
    ):
        raise ValueError("current proof coordinates do not agree")
    active_coordinates = (
        authority.active_stream_generation_id,
        authority.active_acquisition_generation_id,
        authority.active_generation_mandate_commitment_sha256,
        authority.active_source_profile_id,
        authority.active_session_id,
        authority.active_sequence_mode,
    )
    active = all(value is not None for value in active_coordinates)
    if not active and not all(value is None for value in active_coordinates):
        raise ValueError("current proof authority stream is partial")
    stream_binding = _current_proof_optional_stream_binding(
        proof.market_stream_authority,
        proof.market_cursor,
    )
    if active:
        stream = proof.market_stream_authority
        if (
            type(stream) is not MarketStreamAuthorityRecord
            or authority.active_acquisition_generation_id
            != acquisition.acquisition_generation_id
            or authority.active_generation_mandate_commitment_sha256
            != acquisition.mandate_commitment_sha256
            or authority.active_source_profile_id
            != application.selected_market_source_profile_id
            or stream.stream_generation_id != authority.active_stream_generation_id
            or stream.scope_id != scope.scope_id
            or stream.application_generation_id != application.application_generation_id
            or stream.acquisition_generation_id != acquisition.acquisition_generation_id
            or stream.generation_mandate_commitment_sha256
            != acquisition.mandate_commitment_sha256
            or stream.source_profile_id != application.selected_market_source_profile_id
            or stream.session_id != authority.active_session_id
            or stream.sequence_mode != authority.active_sequence_mode
        ):
            raise ValueError("current proof active stream does not agree")
    elif proof.market_stream_authority is not None or proof.market_cursor is not None:
        raise ValueError("current proof has an unclaimed stream")
    active_stream_id = authority.active_stream_generation_id
    active_acquisition_id = authority.active_acquisition_generation_id
    active_mandate = authority.active_generation_mandate_commitment_sha256
    active_source_profile_id = authority.active_source_profile_id
    active_session_id = authority.active_session_id
    active_sequence_mode = authority.active_sequence_mode
    optional_rows_binding = _current_proof_optional_rows_binding(proof)
    return _commit_parts(
        b"execution-core/current-proof/slice/v1",
        _current_proof_request_binding(request),
        _encode_text(application.application_generation_id.value),
        _encode_text(application.selected_execution_profile_id),
        _encode_text(application.selected_market_source_profile_id),
        _encode_int(application.activation_ordinal),
        _encode_int(scope.scope_id),
        _encode_text(scope.execution_profile_id),
        _encode_text(scope.symbol.value),
        _encode_text(acquisition.acquisition_generation_id.value),
        _encode_int(acquisition.successor_ordinal),
        _encode_text(acquisition.mandate_commitment_sha256),
        _encode_text(acquisition.emergency_compatibility_sha256),
        _encode_int(current.current_economics_head_ordinal),
        _encode_int(current.unresolved_effect_count),
        _encode_int(current.active_protection_count),
        _encode_int(checkpoint.currentness_head_ordinal),
        _encode_text(checkpoint.checkpoint_sha256),
        _encode_int(checkpoint.checkpoint_version_ordinal),
        _encode_int(controller.aggregate_quantity),
        _encode_text(controller.integrity_state),
        _encode_int(controller.currentness_head_ordinal),
        _encode_int(controller.controller_version_ordinal),
        _encode_text(controller.emergency_compatibility_sha256),
        _encode_text(authority.authority_class),
        _encode_text(active_stream_id.value) if active_stream_id is not None else b"",
        (
            _encode_text(active_acquisition_id.value)
            if active_acquisition_id is not None
            else b""
        ),
        _encode_text(active_mandate) if active_mandate is not None else b"",
        _encode_text(active_source_profile_id)
        if active_source_profile_id is not None
        else b"",
        _encode_text(active_session_id.value) if active_session_id is not None else b"",
        _encode_text(active_sequence_mode) if active_sequence_mode is not None else b"",
        _encode_int(authority.expected_controller_head_ordinal),
        _encode_text(authority.state_commitment_sha256),
        _encode_int(authority.version_ordinal),
        stream_binding,
        optional_rows_binding,
    )


def _issue_current_proof_slice(
    issuer: object,
    request: CurrentProofRequest,
    execution_profile: _profiles.ExecutionConnectionProfile,
    market_source_profile: _profiles.MarketDataSourceProfile,
    application_generation: ApplicationGenerationRecord,
    scope: ScopeRecord,
    acquisition_generation: AcquisitionGenerationRecord,
    acquisition_current: AcquisitionGenerationCurrentRecord,
    kernel_checkpoint: KernelCheckpointRecord,
    symbol_controller: SymbolControllerRecord,
    protection_authority: ProtectionAuthorityRecord,
    market_stream_authority: MarketStreamAuthorityRecord | None,
    market_cursor: MarketCursorRecord | None,
    root_fill: RootFillRecord | None,
    acquisition_root_route: AcquisitionRootRouteRecord | None,
    execution_fact_head: ExecutionFactHeadRecord | None,
    current_execution_fact: ExecutionFactRecord | None,
    venue_effect: VenueEffectRecord | None,
    dispatch_claim: DispatchClaimRecord | None,
    venue_owner: VenueIdentityOwnerRecord | None,
    acceptance_set: AcceptanceSetRecord | None,
    acceptance_evidence: AcceptanceEvidenceRecord | None,
    closure_head: ClosureChainRecord | None,
) -> CurrentProofSlice:
    """Seal one already-verified repository current-proof result."""

    if issuer is not _CURRENT_PROOF_ISSUER:
        raise TypeError("only the repository may issue CurrentProofSlice")
    result = object.__new__(CurrentProofSlice)
    object.__setattr__(result, "request", request)
    object.__setattr__(result, "execution_profile", execution_profile)
    object.__setattr__(result, "market_source_profile", market_source_profile)
    object.__setattr__(result, "application_generation", application_generation)
    object.__setattr__(result, "scope", scope)
    object.__setattr__(result, "acquisition_generation", acquisition_generation)
    object.__setattr__(result, "acquisition_current", acquisition_current)
    object.__setattr__(result, "kernel_checkpoint", kernel_checkpoint)
    object.__setattr__(result, "symbol_controller", symbol_controller)
    object.__setattr__(result, "protection_authority", protection_authority)
    object.__setattr__(result, "market_stream_authority", market_stream_authority)
    object.__setattr__(result, "market_cursor", market_cursor)
    object.__setattr__(result, "root_fill", root_fill)
    object.__setattr__(result, "acquisition_root_route", acquisition_root_route)
    object.__setattr__(result, "execution_fact_head", execution_fact_head)
    object.__setattr__(result, "current_execution_fact", current_execution_fact)
    object.__setattr__(result, "venue_effect", venue_effect)
    object.__setattr__(result, "dispatch_claim", dispatch_claim)
    object.__setattr__(result, "venue_owner", venue_owner)
    object.__setattr__(result, "acceptance_set", acceptance_set)
    object.__setattr__(result, "acceptance_evidence", acceptance_evidence)
    object.__setattr__(result, "closure_head", closure_head)
    object.__setattr__(result, "_issuer", issuer)
    object.__setattr__(result, "_binding", _current_proof_slice_binding(result))
    return result


__all__ = (
    "AcceptanceEvidenceRecord",
    "AcceptanceSetRecord",
    "AcquisitionGenerationCurrentRecord",
    "AcquisitionGenerationRecord",
    "AcquisitionRootRouteRecord",
    "ApplicationGenerationRecord",
    "ClosureChainRecord",
    "CurrentProofRequest",
    "CurrentProofSlice",
    "DurableInputRecord",
    "DispatchClaimRecord",
    "ExecutionFactHeadRecord",
    "ExecutionFactRecord",
    "KernelCheckpointRecord",
    "MarketCursorRecord",
    "MarketStreamAuthorityRecord",
    "ProtectionAuthorityRecord",
    "RepositoryOutcome",
    "RepositoryOutcomeKind",
    "RootFillRecord",
    "RuntimeCheckpointPayloadRecord",
    "ScopeRecord",
    "SymbolControllerRecord",
    "VenueEffectRecord",
    "VenueIdentityOwnerRecord",
)
