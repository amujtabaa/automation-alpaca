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
from typing import Generic as _Generic
from typing import TypeVar as _TypeVar

from .. import identity as _identity
from .. import profiles as _profiles
from .. import values as _values


class RepositoryOutcomeKind(_enum.Enum):
    APPLIED = "applied"
    FOUND = "found"
    ABSENT = "absent"
    CONFLICT = "conflict"
    INTEGRITY_FAILURE = "integrity-failure"


_RecordT = _TypeVar("_RecordT")


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


@_dataclass(frozen=True, slots=True)
class CurrentProofSlice:
    """Total scope-level proof loaded only from accepted direct-current rows."""

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
    "ScopeRecord",
    "SymbolControllerRecord",
    "VenueEffectRecord",
    "VenueIdentityOwnerRecord",
)
