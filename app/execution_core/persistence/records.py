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
from threading import RLock as _RLock
from typing import Generic as _Generic
from typing import Any as _Any
from typing import Callable as _Callable
from typing import TypeVar as _TypeVar
from typing import cast as _cast
from weakref import ReferenceType as _ReferenceType
from weakref import ref as _weakref_ref

from .. import durable_codec as _durable_codec
from .. import fills as _fills
from .. import identity as _identity
from .. import profiles as _profiles
from .. import values as _values
from .. import venue as _venue
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
_M2_INPUT_OUTCOME_DOCUMENT_KIND = 0x03
_M2_DECISION_RECEIPT_DOCUMENT_KIND = 0x04
_M2_BROKER_OUTBOX_DOCUMENT_KIND = 0x05
_M2_REDUCER_RESULT_PREFIX = b"execution-core/m2-reducer-result/v1\n"
_OWNER_DISPOSITIONS = {
    "POSITION": frozenset(
        {"APPLIED", "EXACT_REPLAY", "FACT_CONFLICT", "RECONCILIATION_REQUIRED"}
    ),
    "VENUE_RECOVERY": frozenset(
        {
            "APPLIED",
            "EXACT_REPLAY",
            "CONFLICT",
            "RECONCILIATION_REQUIRED",
            "REFUSED",
        }
    ),
    "AUTHORITY": frozenset({"APPLIED", "REFUSED", "EXACT_REPLAY", "CONFLICT"}),
    "ACQUISITION": frozenset({"APPLIED", "EXACT_REPLAY", "REFUSED"}),
    "PROTECTION": frozenset({"APPLIED", "EXACT_REPLAY", "STALE", "REFUSED"}),
}
_OPERATION_OWNER_DOMAINS = {
    _operations.OperationDomain.BROKER_EXECUTION: "POSITION",
    _operations.OperationDomain.VENUE_RECOVERY: "VENUE_RECOVERY",
    _operations.OperationDomain.AUTHORITY: "AUTHORITY",
    _operations.OperationDomain.BEGIN_ACQUISITION_GENERATION: "ACQUISITION",
    _operations.OperationDomain.CREATE_ACQUISITION_EFFECT: "ACQUISITION",
    _operations.OperationDomain.CLAIM_ACQUISITION_EFFECT: "ACQUISITION",
    _operations.OperationDomain.BEGIN_ACQUISITION_PREEMPTION: "ACQUISITION",
    _operations.OperationDomain.MARKET_OCCURRENCE: "PROTECTION",
}
_OUTBOX_INPUT_DOMAINS = frozenset(
    {
        _operations.OperationDomain.AUTHORITY,
        _operations.OperationDomain.CLAIM_ACQUISITION_EFFECT,
    }
)


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
    """Explicit result; a classified write may carry its typed local proof."""

    kind: RepositoryOutcomeKind
    record: _RecordT | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not RepositoryOutcomeKind:
            raise TypeError("repository outcome kind must be exact")
        if self.kind is RepositoryOutcomeKind.FOUND and self.record is None:
            raise ValueError("FOUND outcomes must carry one complete record")
        if self.record is not None and self.kind not in {
            RepositoryOutcomeKind.APPLIED,
            RepositoryOutcomeKind.FOUND,
            RepositoryOutcomeKind.CONFLICT,
        }:
            raise ValueError(
                "only APPLIED, FOUND, or CONFLICT outcomes may carry one record"
            )


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


_RUNTIME_CHECKPOINT_MAX_PAYLOAD_BYTES = 268_435_456
_RUNTIME_CHECKPOINT_REGISTRY_LOCK = _RLock()
_RUNTIME_CHECKPOINT_REGISTRY: dict[
    int, tuple[_ReferenceType[object], bytes, str]
] = {}
_RUNTIME_CHECKPOINT_ABSENCE_FIELDS = (
    ("owner_effect_absences", "owner/effect", "owner-effect"),
    ("claim_effect_absences", "claim/effect", "claim-effect"),
    ("acceptance_effect_absences", "acceptance/effect", "acceptance-effect"),
    (
        "evidence_acceptance_absences",
        "evidence/acceptance",
        "evidence-acceptance",
    ),
    ("closure_owner_absences", "closure/owner", "closure-owner"),
    ("route_owner_absences", "route/owner", "route-owner"),
    ("fact_head_root_absences", "fact-head/root", "fact-head-root"),
    ("current_fact_root_absences", "current-fact/root", "current-fact-root"),
    ("stream_generation_absences", "stream/generation", "stream-generation"),
    ("cursor_stream_absences", "cursor/stream", "cursor-stream"),
)


def _runtime_checkpoint_require_application_id(
    name: str, value: object
) -> _identity.ApplicationGenerationId:
    if type(value) is not _identity.ApplicationGenerationId:
        raise TypeError(f"{name} must be exact ApplicationGenerationId")
    _identity.ApplicationGenerationId(value.value)
    return value


def _runtime_checkpoint_require_nonnegative_int(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _runtime_checkpoint_require_positive_int(name: str, value: object) -> int:
    result = _runtime_checkpoint_require_nonnegative_int(name, value)
    if result < 1:
        raise ValueError(f"{name} must be positive")
    return result


def _runtime_checkpoint_require_binding(name: str, value: object) -> bytes:
    if type(value) is not bytes:
        raise TypeError(f"{name} must be exact bytes")
    if len(value) != 32:
        raise ValueError(f"{name} must be exactly 32 bytes")
    return value


def _runtime_checkpoint_field_none() -> bytes:
    return _commit_parts(b"execution-core/runtime-checkpoint/field/absent/v1")


def _runtime_checkpoint_field_bool(value: bool) -> bytes:
    if type(value) is not bool:
        raise TypeError("runtime checkpoint Boolean field must be exact")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/field/bool/v1",
        b"\x01" if value else b"\x00",
    )


def _runtime_checkpoint_field_int(value: int) -> bytes:
    return _commit_parts(
        b"execution-core/runtime-checkpoint/field/int/v1", _encode_int(value)
    )


def _runtime_checkpoint_field_text(value: str) -> bytes:
    if type(value) is not str:
        raise TypeError("runtime checkpoint text field must be exact")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/field/text/v1", _encode_text(value)
    )


def _runtime_checkpoint_field_bytes(value: bytes) -> bytes:
    if type(value) is not bytes:
        raise TypeError("runtime checkpoint bytes field must be exact")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/field/bytes/v1",
        len(value).to_bytes(8, "big") + value,
    )


def _runtime_checkpoint_atom_binding(atom: _durable_codec.DurableAtom) -> bytes:
    if (
        type(atom) is not _durable_codec.DurableAtom
        or type(atom.contract_version) is not str
        or type(atom.type_tag) is not str
        or type(atom.fields) is not tuple
    ):
        raise TypeError("runtime checkpoint durable atom must be exact")
    fields: list[bytes] = []
    for field in atom.fields:
        if type(field) is str:
            fields.append(
                _commit_parts(
                    b"execution-core/runtime-checkpoint/atom-text/v1",
                    _encode_text(field),
                )
            )
        elif type(field) is _durable_codec.DurableAtom:
            fields.append(_runtime_checkpoint_atom_binding(field))
        else:
            raise TypeError("runtime checkpoint durable atom field is invalid")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/durable-atom/v1",
        _encode_text(atom.contract_version),
        _encode_text(atom.type_tag),
        _encode_int(len(fields)),
        *fields,
    )


def _runtime_checkpoint_field_m1(value: object) -> bytes:
    try:
        atom = _durable_codec.encode_m1_value(_cast(_durable_codec._OwningValue, value))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("runtime checkpoint M1 field is invalid") from error
    return _commit_parts(
        b"execution-core/runtime-checkpoint/field/m1-value/v1",
        _runtime_checkpoint_atom_binding(atom),
    )


def _runtime_checkpoint_record_binding(
    tag: str, fields: tuple[bytes, ...]
) -> bytes:
    if type(tag) is not str or type(fields) is not tuple:
        raise TypeError("runtime checkpoint record binding is invalid")
    if any(type(field) is not bytes for field in fields):
        raise TypeError("runtime checkpoint record field binding is invalid")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/record/v1",
        _encode_text(tag),
        _encode_int(len(fields)),
        *fields,
    )


def _runtime_checkpoint_optional_record_binding(value: bytes | None) -> bytes:
    if value is None:
        return _commit_parts(b"execution-core/runtime-checkpoint/optional/absent/v1")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/optional/present/v1",
        _runtime_checkpoint_require_binding("optional record binding", value),
    )


def _runtime_checkpoint_sequence_binding(domain: str, items: tuple[bytes, ...]) -> bytes:
    if type(domain) is not str or type(items) is not tuple:
        raise TypeError("runtime checkpoint sequence binding is invalid")
    if any(type(item) is not bytes for item in items):
        raise TypeError("runtime checkpoint sequence item must be exact bytes")
    return _commit_parts(domain.encode("ascii"), _encode_int(len(items)), *items)


def _runtime_checkpoint_storage_field_binding(value: object) -> bytes:
    if value is None:
        return _runtime_checkpoint_field_none()
    if type(value) is bool:
        return _runtime_checkpoint_field_bool(value)
    if type(value) is int:
        return _runtime_checkpoint_field_int(value)
    if type(value) is str:
        return _runtime_checkpoint_field_text(value)
    if type(value) is bytes:
        return _runtime_checkpoint_field_bytes(value)
    raise TypeError("runtime checkpoint storage field has an invalid class")


def _runtime_checkpoint_identity_text(value: object, expected: type[_Any]) -> str:
    if type(value) is not expected:
        raise TypeError("runtime checkpoint identity has an invalid exact class")
    text = getattr(value, "value")
    if type(text) is not str:
        raise TypeError("runtime checkpoint identity value must be exact text")
    _cast(_Callable[[str], object], expected)(text)
    return text


def _runtime_checkpoint_quantity_value(value: object | None) -> int | None:
    if value is None:
        return None
    if type(value) is not _values.Quantity:
        raise TypeError("runtime checkpoint quantity must be exact Quantity")
    return value.value


def _runtime_checkpoint_price_columns(
    value: object | None, *, absent_is_null: bool
) -> tuple[object, ...]:
    if value is None:
        if absent_is_null:
            return (None,) * 9
        return (0, 0, 0, "0", 0, 0, 0, "0", 0)
    if type(value) is not _values.ReportedPrice:
        raise TypeError("runtime checkpoint price must be exact ReportedPrice")
    scale = value.scale.value.as_tuple()
    tick_scale = value.tick.scale.value.as_tuple()
    return (
        1,
        value.units.value,
        scale.sign,
        "".join(str(digit) for digit in scale.digits),
        scale.exponent,
        value.tick.tick_units.value,
        tick_scale.sign,
        "".join(str(digit) for digit in tick_scale.digits),
        tick_scale.exponent,
    )


def _runtime_checkpoint_storage_record(record: object) -> tuple[str, tuple[object, ...]]:
    identity = _runtime_checkpoint_identity_text
    if type(record) is ScopeRecord:
        return "scope/v1", (
            record.scope_id,
            identity(record.application_generation_id, _identity.ApplicationGenerationId),
            record.execution_profile_id,
            identity(record.symbol, _identity.SymbolId),
        )
    if type(record) is SymbolControllerRecord:
        return "controller/v1", (
            record.scope_id,
            identity(record.application_generation_id, _identity.ApplicationGenerationId),
            record.execution_profile_id,
            None
            if record.live_acquisition_generation_id is None
            else identity(
                record.live_acquisition_generation_id,
                _identity.AcquisitionGenerationId,
            ),
            record.aggregate_quantity,
            record.integrity_state,
            record.currentness_head_ordinal,
            record.controller_version_ordinal,
            record.emergency_compatibility_sha256,
        )
    if type(record) is ProtectionAuthorityRecord:
        return "protection/v1", (
            record.scope_id,
            record.authority_class,
            None
            if record.active_stream_generation_id is None
            else identity(
                record.active_stream_generation_id, _identity.MarketStreamGenerationId
            ),
            None
            if record.active_acquisition_generation_id is None
            else identity(
                record.active_acquisition_generation_id,
                _identity.AcquisitionGenerationId,
            ),
            record.active_generation_mandate_commitment_sha256,
            record.active_source_profile_id,
            None
            if record.active_session_id is None
            else identity(record.active_session_id, _identity.SessionId),
            record.active_sequence_mode,
            record.expected_controller_head_ordinal,
            record.state_commitment_sha256,
            record.version_ordinal,
        )
    if type(record) is AcquisitionGenerationRecord:
        return "generation/v1", (
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            record.scope_id,
            record.status,
            record.successor_ordinal,
            None
            if record.predecessor_generation_id is None
            else identity(
                record.predecessor_generation_id, _identity.AcquisitionGenerationId
            ),
            record.mandate_commitment_sha256,
            record.emergency_compatibility_sha256,
        )
    if type(record) is AcquisitionGenerationCurrentRecord:
        return "generation-current/v1", (
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            record.scope_id,
            record.current_economics_head_ordinal,
            record.unresolved_effect_count,
            record.active_protection_count,
        )
    if type(record) is VenueEffectRecord:
        return "effect/v1", (
            record.effect_id,
            identity(record.effect_external, _identity.EffectId),
            record.scope_id,
            identity(record.application_generation_id, _identity.ApplicationGenerationId),
            record.execution_profile_id,
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            record.generation_mandate_commitment_sha256,
            record.expected_controller_head_ordinal,
            record.expected_protection_version_ordinal,
            record.authority_class,
            identity(record.request_occurrence_id, _identity.RequestOccurrenceId),
            identity(record.mandate_id, _identity.MandateId),
            record.effect_kind,
            None
            if record.client_order_id is None
            else identity(record.client_order_id, _identity.ClientOrderId),
            None
            if record.target_order_id is None
            else identity(record.target_order_id, _identity.OrderId),
            record.side,
            _runtime_checkpoint_quantity_value(record.quantity),
            record.economic_scope,
            record.lifecycle_state,
            record.disposition,
            record.closure_proof_kind,
            record.closure_proof_digest,
            record.closure_proof_evidence_id,
            record.closure_proof_claim_id,
            record.created_ordinal,
        )
    if type(record) is VenueIdentityOwnerRecord:
        return "owner/v1", (
            record.scope_id,
            record.execution_profile_id,
            identity(record.owner_id, _identity.OrderId),
            identity(record.observation_id, _identity.VenueObservationId),
            record.effect_id,
            record.root_fill_key_id,
            identity(record.owner_generation_id, _identity.AcquisitionGenerationId),
            record.admitted_after_effect_closed,
        )
    if type(record) is DispatchClaimRecord:
        return "claim/v1", (
            record.claim_id,
            record.effect_id,
            record.execution_profile_id,
            identity(record.claim_occurrence_id, _identity.ClaimOccurrenceId),
            record.claim_ordinal,
        )
    if type(record) is AcceptanceSetRecord:
        return "acceptance/v1", (record.acceptance_set_id, record.effect_id)
    if type(record) is AcceptanceEvidenceRecord:
        return "evidence/v1", (
            record.evidence_id,
            record.acceptance_set_id,
            record.effect_id,
            record.evidence_kind,
            record.proof_kind,
            record.evidence_digest,
            record.evidence_ordinal,
            None
            if record.contradiction_owner_id is None
            else identity(record.contradiction_owner_id, _identity.OrderId),
            None
            if record.contradiction_observation_id is None
            else identity(
                record.contradiction_observation_id, _identity.VenueObservationId
            ),
        )
    if type(record) is ClosureChainRecord:
        return "closure/v1", (
            record.closure_id,
            record.scope_id,
            identity(record.owner_id, _identity.OrderId),
            record.ordinal,
            record.effect_id,
            record.closure_kind,
            record.predecessor_closure_id,
        )
    if type(record) is AcquisitionRootRouteRecord:
        return "route/v1", (
            record.root_fill_key_id,
            record.scope_id,
            identity(record.application_generation_id, _identity.ApplicationGenerationId),
            record.execution_profile_id,
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            record.effect_id,
            identity(record.owner_id, _identity.OrderId),
            identity(record.observation_id, _identity.VenueObservationId),
        )
    if type(record) is RootFillRecord:
        return "root/v1", (
            record.root_fill_key_id,
            record.scope_id,
            identity(record.application_generation_id, _identity.ApplicationGenerationId),
            record.execution_profile_id,
            identity(record.owner_generation_id, _identity.AcquisitionGenerationId),
            identity(record.root_fill_id, _identity.RootFillId),
            record.current_fact_id,
            record.current_kind,
            record.current_authority,
            record.current_side,
            _runtime_checkpoint_quantity_value(record.current_quantity),
            *_runtime_checkpoint_price_columns(
                record.current_price, absent_is_null=True
            ),
            record.economics_head_ordinal,
        )
    if type(record) is ExecutionFactHeadRecord:
        return "fact-head/v1", (
            record.root_fill_key_id,
            record.fact_id,
            record.fact_ordinal,
        )
    if type(record) is ExecutionFactRecord:
        return "fact/v1", (
            record.fact_id,
            record.scope_id,
            identity(record.application_generation_id, _identity.ApplicationGenerationId),
            record.execution_profile_id,
            record.root_fill_key_id,
            identity(record.source_event_id, _identity.SourceEventId),
            identity(record.order_id, _identity.OrderId),
            record.side,
            record.kind,
            record.authority,
            _runtime_checkpoint_quantity_value(record.quantity),
            *_runtime_checkpoint_price_columns(record.price, absent_is_null=False),
            None
            if record.request_occurrence_id is None
            else identity(record.request_occurrence_id, _identity.RequestOccurrenceId),
            None
            if record.claim_occurrence_id is None
            else identity(record.claim_occurrence_id, _identity.ClaimOccurrenceId),
            _runtime_checkpoint_quantity_value(record.prior_cumulative_quantity),
            _runtime_checkpoint_quantity_value(record.resulting_cumulative_quantity),
            None
            if record.actor_id is None
            else identity(record.actor_id, _identity.ActorId),
            record.reason_text,
            None
            if record.evidence_reference is None
            else identity(record.evidence_reference, _identity.EvidenceReference),
            record.predecessor_fact_id,
            record.fact_ordinal,
        )
    if type(record) is MarketStreamAuthorityRecord:
        return "stream/v1", (
            identity(
                record.stream_generation_id, _identity.MarketStreamGenerationId
            ),
            record.scope_id,
            identity(record.application_generation_id, _identity.ApplicationGenerationId),
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            record.generation_mandate_commitment_sha256,
            record.source_profile_id,
            identity(record.session_id, _identity.SessionId),
            record.sequence_mode,
        )
    if type(record) is MarketCursorRecord:
        return "cursor/v1", (
            identity(
                record.stream_generation_id, _identity.MarketStreamGenerationId
            ),
            record.scope_id,
            identity(record.application_generation_id, _identity.ApplicationGenerationId),
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            record.generation_mandate_commitment_sha256,
            record.source_profile_id,
            identity(record.session_id, _identity.SessionId),
            record.sequence_mode,
            record.fixed_cursor_ordinal,
            record.published_head_ordinal,
        )
    raise TypeError("runtime checkpoint selection has an unknown record class")


def _runtime_checkpoint_selected_record_binding(record: object) -> bytes:
    tag, fields = _runtime_checkpoint_storage_record(record)
    return _runtime_checkpoint_record_binding(
        tag, tuple(_runtime_checkpoint_storage_field_binding(field) for field in fields)
    )


@_dataclass(frozen=True, slots=True)
class _RuntimeCheckpointSelectionSet:
    scopes: tuple[ScopeRecord, ...]
    controllers: tuple[SymbolControllerRecord, ...]
    protection_authorities: tuple[ProtectionAuthorityRecord, ...]
    live_generations: tuple[AcquisitionGenerationRecord, ...]
    live_generation_current: tuple[AcquisitionGenerationCurrentRecord, ...]
    unresolved_generations: tuple[AcquisitionGenerationRecord, ...]
    unresolved_generation_current: tuple[AcquisitionGenerationCurrentRecord, ...]
    effects: tuple[VenueEffectRecord, ...]
    owners: tuple[VenueIdentityOwnerRecord, ...]
    claims: tuple[DispatchClaimRecord, ...]
    acceptance_sets: tuple[AcceptanceSetRecord, ...]
    evidence: tuple[AcceptanceEvidenceRecord, ...]
    closure_heads: tuple[ClosureChainRecord, ...]
    root_routes: tuple[AcquisitionRootRouteRecord, ...]
    roots: tuple[RootFillRecord, ...]
    fact_heads: tuple[ExecutionFactHeadRecord, ...]
    current_facts: tuple[ExecutionFactRecord, ...]
    streams: tuple[MarketStreamAuthorityRecord, ...]
    cursors: tuple[MarketCursorRecord, ...]
    owner_effect_absences: tuple[tuple[str, bytes], ...]
    claim_effect_absences: tuple[tuple[str, bytes], ...]
    acceptance_effect_absences: tuple[tuple[str, bytes], ...]
    evidence_acceptance_absences: tuple[tuple[str, bytes], ...]
    closure_owner_absences: tuple[tuple[str, bytes], ...]
    route_owner_absences: tuple[tuple[str, bytes], ...]
    fact_head_root_absences: tuple[tuple[str, bytes], ...]
    current_fact_root_absences: tuple[tuple[str, bytes], ...]
    stream_generation_absences: tuple[tuple[str, bytes], ...]
    cursor_stream_absences: tuple[tuple[str, bytes], ...]
    query_row_counts: tuple[int, ...]

    def __post_init__(self) -> None:
        for name in (
            "scopes",
            "controllers",
            "protection_authorities",
            "live_generations",
            "live_generation_current",
            "unresolved_generations",
            "unresolved_generation_current",
            "effects",
            "owners",
            "claims",
            "acceptance_sets",
            "evidence",
            "closure_heads",
            "root_routes",
            "roots",
            "fact_heads",
            "current_facts",
            "streams",
            "cursors",
        ):
            if type(getattr(self, name)) is not tuple:
                raise TypeError(f"runtime checkpoint {name} must be an exact tuple")
        for name, family, _suffix in _RUNTIME_CHECKPOINT_ABSENCE_FIELDS:
            values = getattr(self, name)
            if type(values) is not tuple:
                raise TypeError(f"runtime checkpoint {name} must be an exact tuple")
            if len(values) > 65_535:
                raise OverflowError(f"runtime checkpoint {name} exceeds its row limit")
            prior_key: bytes | None = None
            for item in values:
                if (
                    type(item) is not tuple
                    or len(item) != 2
                    or item[0] != family
                    or type(item[0]) is not str
                    or type(item[1]) is not bytes
                    or len(item[1]) != 32
                ):
                    raise ValueError(f"runtime checkpoint {name} item is invalid")
                if prior_key is not None and item[1] <= prior_key:
                    raise ValueError(f"runtime checkpoint {name} is not canonical")
                prior_key = item[1]
        if type(self.query_row_counts) is not tuple or len(self.query_row_counts) != 13:
            raise ValueError("runtime checkpoint requires exactly thirteen query counts")
        for count in self.query_row_counts:
            _runtime_checkpoint_require_nonnegative_int(
                "runtime checkpoint query count", count
            )
        _runtime_checkpoint_validate_selection_set(self)


_RUNTIME_CHECKPOINT_SELECTION_FIELDS = (
    ("scopes", "scopes"),
    ("controllers", "controllers"),
    ("protection_authorities", "protections"),
    ("live_generations", "live-generations"),
    ("live_generation_current", "live-generation-current"),
    ("unresolved_generations", "unresolved-generations"),
    ("unresolved_generation_current", "unresolved-generation-current"),
    ("effects", "effects"),
    ("owners", "owners"),
    ("claims", "claims"),
    ("acceptance_sets", "acceptance-sets"),
    ("evidence", "evidence"),
    ("closure_heads", "closure-heads"),
    ("root_routes", "root-routes"),
    ("roots", "roots"),
    ("fact_heads", "fact-heads"),
    ("current_facts", "current-facts"),
    ("streams", "streams"),
    ("cursors", "cursors"),
)


def _runtime_checkpoint_selection_record_key(name: str, record: object) -> tuple[object, ...]:
    identity = _runtime_checkpoint_identity_text
    if name == "scopes" and type(record) is ScopeRecord:
        return (record.scope_id,)
    if name == "controllers" and type(record) is SymbolControllerRecord:
        return (record.scope_id,)
    if name == "protection_authorities" and type(record) is ProtectionAuthorityRecord:
        return (record.scope_id,)
    if name in {"live_generations", "unresolved_generations"} and type(
        record
    ) is AcquisitionGenerationRecord:
        return (
            record.scope_id,
            record.successor_ordinal,
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
        )
    if name in {
        "live_generation_current",
        "unresolved_generation_current",
    } and type(record) is AcquisitionGenerationCurrentRecord:
        return (
            record.scope_id,
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
        )
    if name == "effects" and type(record) is VenueEffectRecord:
        return (record.created_ordinal, record.effect_id)
    if name == "owners" and type(record) is VenueIdentityOwnerRecord:
        return (
            record.effect_id,
            identity(record.owner_id, _identity.OrderId),
            identity(record.observation_id, _identity.VenueObservationId),
        )
    if name == "claims" and type(record) is DispatchClaimRecord:
        return (record.effect_id, record.claim_id)
    if name == "acceptance_sets" and type(record) is AcceptanceSetRecord:
        return (record.effect_id, record.acceptance_set_id)
    if name == "evidence" and type(record) is AcceptanceEvidenceRecord:
        return (record.effect_id, record.evidence_ordinal, record.evidence_id)
    if name == "closure_heads" and type(record) is ClosureChainRecord:
        return (
            record.effect_id,
            identity(record.owner_id, _identity.OrderId),
            record.ordinal,
        )
    if name == "root_routes" and type(record) is AcquisitionRootRouteRecord:
        return (
            record.effect_id,
            identity(record.owner_id, _identity.OrderId),
            record.root_fill_key_id,
        )
    if name == "roots" and type(record) is RootFillRecord:
        return (record.root_fill_key_id,)
    if name == "fact_heads" and type(record) is ExecutionFactHeadRecord:
        return (record.root_fill_key_id,)
    if name == "current_facts" and type(record) is ExecutionFactRecord:
        return (record.root_fill_key_id,)
    if name == "streams" and type(record) is MarketStreamAuthorityRecord:
        return (
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            identity(
                record.stream_generation_id, _identity.MarketStreamGenerationId
            ),
        )
    if name == "cursors" and type(record) is MarketCursorRecord:
        return (
            identity(
                record.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            identity(
                record.stream_generation_id, _identity.MarketStreamGenerationId
            ),
        )
    raise TypeError(f"runtime checkpoint {name} contains an invalid record class")


def _runtime_checkpoint_validate_selection_set(
    selection: _RuntimeCheckpointSelectionSet,
) -> None:
    parent_ordered_names = {
        "live_generation_current",
        "unresolved_generation_current",
        "roots",
        "fact_heads",
        "current_facts",
        "cursors",
    }
    for name, _suffix in _RUNTIME_CHECKPOINT_SELECTION_FIELDS:
        records = getattr(selection, name)
        limit = 4_096 if name == "scopes" else 65_535
        if len(records) > limit:
            raise OverflowError(f"runtime checkpoint {name} exceeds its row limit")
        if name in parent_ordered_names:
            for record in records:
                _runtime_checkpoint_selection_record_key(name, record)
            continue
        prior_record_key: tuple[object, ...] | None = None
        for record in records:
            key = _runtime_checkpoint_selection_record_key(name, record)
            if prior_record_key is not None and key <= prior_record_key:
                raise ValueError(f"runtime checkpoint {name} is not canonical")
            prior_record_key = key

    for generations_name, current_name in (
        ("live_generations", "live_generation_current"),
        ("unresolved_generations", "unresolved_generation_current"),
    ):
        generations = getattr(selection, generations_name)
        current_rows = getattr(selection, current_name)
        if len(generations) != len(current_rows):
            raise ValueError(
                f"runtime checkpoint {generations_name} current rows are incomplete"
            )
        if any(
            generation.scope_id != current.scope_id
            or generation.acquisition_generation_id
            != current.acquisition_generation_id
            for generation, current in zip(generations, current_rows, strict=True)
        ):
            raise ValueError(
                f"runtime checkpoint {generations_name} current rows do not agree"
            )

    routes = selection.root_routes
    if len(routes) != len(selection.roots):
        raise ValueError("runtime checkpoint root rows are incomplete")
    route_order_by_root: dict[int, tuple[object, ...]] = {}
    for route, root in zip(routes, selection.roots, strict=True):
        if route.root_fill_key_id != root.root_fill_key_id:
            raise ValueError("runtime checkpoint root rows do not agree")
        route_order_by_root[root.root_fill_key_id] = (
            route.effect_id,
            _runtime_checkpoint_identity_text(
                route.owner_id, _identity.OrderId
            ),
            route.root_fill_key_id,
        )

    for name in ("fact_heads", "current_facts"):
        prior_root_key: tuple[object, ...] | None = None
        for record in getattr(selection, name):
            root_key = route_order_by_root.get(record.root_fill_key_id)
            if root_key is None or (
                prior_root_key is not None and root_key <= prior_root_key
            ):
                raise ValueError(f"runtime checkpoint {name} is not canonical")
            prior_root_key = root_key

    if len(selection.fact_heads) != len(selection.current_facts) or any(
        head.root_fill_key_id != fact.root_fill_key_id
        or head.fact_id != fact.fact_id
        or head.fact_ordinal != fact.fact_ordinal
        for head, fact in zip(
            selection.fact_heads, selection.current_facts, strict=True
        )
    ):
        raise ValueError("runtime checkpoint current fact rows do not agree")

    stream_order: dict[object, tuple[str, str]] = {
        stream.stream_generation_id: (
            _runtime_checkpoint_identity_text(
                stream.acquisition_generation_id, _identity.AcquisitionGenerationId
            ),
            _runtime_checkpoint_identity_text(
                stream.stream_generation_id, _identity.MarketStreamGenerationId
            ),
        )
        for stream in selection.streams
    }
    prior_cursor_key: tuple[str, str] | None = None
    for cursor in selection.cursors:
        cursor_key = stream_order.get(cursor.stream_generation_id)
        if cursor_key is None or (
            prior_cursor_key is not None and cursor_key <= prior_cursor_key
        ):
            raise ValueError("runtime checkpoint cursors are not canonical")
        prior_cursor_key = cursor_key


def _runtime_checkpoint_selection_set_binding(
    selection: _RuntimeCheckpointSelectionSet,
) -> bytes:
    if type(selection) is not _RuntimeCheckpointSelectionSet:
        raise TypeError("runtime checkpoint selection set must be exact")
    record_sequences = tuple(
        _runtime_checkpoint_sequence_binding(
            f"execution-core/runtime-checkpoint/records/{suffix}/v1",
            tuple(
                _runtime_checkpoint_selected_record_binding(record)
                for record in getattr(selection, name)
            ),
        )
        for name, suffix in _RUNTIME_CHECKPOINT_SELECTION_FIELDS
    )
    absence_sequences: list[bytes] = []
    for name, family, suffix in _RUNTIME_CHECKPOINT_ABSENCE_FIELDS:
        absence_sequences.append(
            _runtime_checkpoint_sequence_binding(
                f"execution-core/runtime-checkpoint/absences/{suffix}/v1",
                tuple(
                    _commit_parts(
                        b"execution-core/runtime-checkpoint/absence/v1",
                        _encode_text(item_family),
                        len(key).to_bytes(8, "big") + key,
                    )
                    for item_family, key in getattr(selection, name)
                ),
            )
        )
    query_counts = _runtime_checkpoint_sequence_binding(
        "execution-core/runtime-checkpoint/query-counts/v1",
        tuple(
            _runtime_checkpoint_field_int(count)
            for count in selection.query_row_counts
        ),
    )
    return _commit_parts(
        b"execution-core/runtime-checkpoint/selection-set/v1",
        *record_sequences,
        *absence_sequences,
        query_counts,
    )


def _runtime_checkpoint_application_record_binding(
    record: ApplicationGenerationRecord,
) -> bytes:
    if type(record) is not ApplicationGenerationRecord:
        raise TypeError("runtime checkpoint application record must be exact")
    _runtime_checkpoint_require_application_id(
        "runtime checkpoint application", record.application_generation_id
    )
    _require_sha256_text(
        "runtime checkpoint selected execution profile",
        record.selected_execution_profile_id,
    )
    _require_sha256_text(
        "runtime checkpoint selected market profile",
        record.selected_market_source_profile_id,
    )
    _runtime_checkpoint_require_positive_int(
        "runtime checkpoint activation ordinal", record.activation_ordinal
    )
    return _runtime_checkpoint_record_binding(
        "app/v1",
        (
            _runtime_checkpoint_field_text(record.application_generation_id.value),
            _runtime_checkpoint_field_text(record.selected_execution_profile_id),
            _runtime_checkpoint_field_text(record.selected_market_source_profile_id),
            _runtime_checkpoint_field_int(record.activation_ordinal),
        ),
    )


def _runtime_checkpoint_execution_profile_binding(
    profile: _profiles.ExecutionConnectionProfile,
) -> bytes:
    if type(profile) is not _profiles.ExecutionConnectionProfile:
        raise TypeError("runtime checkpoint execution profile must be exact")
    fields = (
        profile.connection_profile_id,
        profile.application_generation,
        profile.broker_provider,
        profile.environment_class,
        profile.account_identity,
        profile.trade_command_origin,
        profile.order_query_origin,
        profile.order_event_origin,
        profile.credential_handle_fingerprint,
        profile.adapter_contract_version,
        profile.capability_profile_sha256,
        profile.deployment_identity,
        profile.profile_commitment_sha256,
    )
    return _runtime_checkpoint_record_binding(
        "exec-profile/v1",
        tuple(_runtime_checkpoint_field_text(field) for field in fields),
    )


def _runtime_checkpoint_market_profile_binding(
    profile: _profiles.MarketDataSourceProfile,
) -> bytes:
    if type(profile) is not _profiles.MarketDataSourceProfile:
        raise TypeError("runtime checkpoint market profile must be exact")
    fields = (
        profile.market_source_profile_id,
        profile.provider,
        profile.environment_or_feed,
        profile.source_origin,
        profile.entitlement_class,
        profile.normalization_contract_version,
        profile.data_capability_profile_sha256,
        profile.source_profile_commitment_sha256,
    )
    return _runtime_checkpoint_record_binding(
        "market-profile/v1",
        tuple(_runtime_checkpoint_field_text(field) for field in fields),
    )


def _runtime_checkpoint_head_record_binding(
    record: KernelCheckpointRecord,
) -> bytes:
    if type(record) is not KernelCheckpointRecord:
        raise TypeError("runtime checkpoint head must be exact KernelCheckpointRecord")
    _runtime_checkpoint_require_application_id(
        "runtime checkpoint head application", record.application_generation_id
    )
    _runtime_checkpoint_require_nonnegative_int(
        "runtime checkpoint head ordinal", record.currentness_head_ordinal
    )
    _require_sha256_text("runtime checkpoint head SHA-256", record.checkpoint_sha256)
    _runtime_checkpoint_require_positive_int(
        "runtime checkpoint version", record.checkpoint_version_ordinal
    )
    return _runtime_checkpoint_record_binding(
        "head/v1",
        (
            _runtime_checkpoint_field_text(record.application_generation_id.value),
            _runtime_checkpoint_field_int(record.currentness_head_ordinal),
            _runtime_checkpoint_field_text(record.checkpoint_sha256),
            _runtime_checkpoint_field_int(record.checkpoint_version_ordinal),
        ),
    )


@_dataclass(frozen=True, slots=True)
class RuntimeCheckpointPayloadRecord:
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str
    currentness_head_ordinal: int
    checkpoint_version_ordinal: int
    payload_bytes: bytes
    payload_length: int
    payload_sha256: str

    def __post_init__(self) -> None:
        _runtime_checkpoint_payload_record_binding(self)


def _runtime_checkpoint_payload_record_binding(
    record: RuntimeCheckpointPayloadRecord,
) -> bytes:
    if type(record) is not RuntimeCheckpointPayloadRecord:
        raise TypeError("runtime checkpoint payload record must be exact")
    _runtime_checkpoint_require_application_id(
        "runtime checkpoint payload application", record.application_generation_id
    )
    _require_sha256_text(
        "runtime checkpoint payload execution profile", record.execution_profile_id
    )
    _require_sha256_text(
        "runtime checkpoint payload market profile", record.market_source_profile_id
    )
    _runtime_checkpoint_require_nonnegative_int(
        "runtime checkpoint payload head", record.currentness_head_ordinal
    )
    _runtime_checkpoint_require_positive_int(
        "runtime checkpoint payload version", record.checkpoint_version_ordinal
    )
    if type(record.payload_bytes) is not bytes:
        raise TypeError("runtime checkpoint payload must be exact bytes")
    if not record.payload_bytes:
        raise ValueError("runtime checkpoint payload must be nonempty")
    if len(record.payload_bytes) > _RUNTIME_CHECKPOINT_MAX_PAYLOAD_BYTES:
        raise OverflowError("runtime checkpoint payload exceeds the contract limit")
    if type(record.payload_length) is not int:
        raise TypeError("runtime checkpoint payload length must be an exact integer")
    if record.payload_length != len(record.payload_bytes):
        raise ValueError("runtime checkpoint payload length does not match its bytes")
    _require_sha256_text("runtime checkpoint payload SHA-256", record.payload_sha256)
    if _sha256(record.payload_bytes).hexdigest() != record.payload_sha256:
        raise ValueError("runtime checkpoint payload SHA-256 does not match its bytes")
    return _runtime_checkpoint_record_binding(
        "payload/v1",
        (
            _runtime_checkpoint_field_text(record.application_generation_id.value),
            _runtime_checkpoint_field_text(record.execution_profile_id),
            _runtime_checkpoint_field_text(record.market_source_profile_id),
            _runtime_checkpoint_field_int(record.currentness_head_ordinal),
            _runtime_checkpoint_field_int(record.checkpoint_version_ordinal),
            _runtime_checkpoint_field_bytes(record.payload_bytes),
            _runtime_checkpoint_field_int(record.payload_length),
            _runtime_checkpoint_field_text(record.payload_sha256),
        ),
    )


@_dataclass(frozen=True, slots=True)
class RuntimeCheckpointSelectionRequest:
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str
    expected_checkpoint: KernelCheckpointRecord | None

    def __post_init__(self) -> None:
        _runtime_checkpoint_selection_request_binding(self)


def _runtime_checkpoint_selection_request_binding(
    request: RuntimeCheckpointSelectionRequest,
) -> bytes:
    if type(request) is not RuntimeCheckpointSelectionRequest:
        raise TypeError("runtime checkpoint selection request must be exact")
    application_id = _runtime_checkpoint_require_application_id(
        "runtime checkpoint selection application", request.application_generation_id
    )
    _require_sha256_text(
        "runtime checkpoint selection execution profile", request.execution_profile_id
    )
    _require_sha256_text(
        "runtime checkpoint selection market profile", request.market_source_profile_id
    )
    predecessor_binding: bytes | None = None
    if request.expected_checkpoint is not None:
        predecessor_binding = _runtime_checkpoint_head_record_binding(
            request.expected_checkpoint
        )
        if request.expected_checkpoint.application_generation_id != application_id:
            raise ValueError("runtime checkpoint expected head has wrong application")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/selection-request/v1",
        _runtime_checkpoint_field_m1(application_id),
        _runtime_checkpoint_field_text(request.execution_profile_id),
        _runtime_checkpoint_field_text(request.market_source_profile_id),
        _runtime_checkpoint_optional_record_binding(predecessor_binding),
    )


@_dataclass(frozen=True, slots=True)
class RuntimeCheckpointLoadRequest:
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str

    def __post_init__(self) -> None:
        _runtime_checkpoint_load_request_binding(self)


def _runtime_checkpoint_load_request_binding(
    request: RuntimeCheckpointLoadRequest,
) -> tuple[bytes, bytes, bytes]:
    if type(request) is not RuntimeCheckpointLoadRequest:
        raise TypeError("runtime checkpoint load request must be exact")
    application_id = _runtime_checkpoint_require_application_id(
        "runtime checkpoint load application", request.application_generation_id
    )
    _require_sha256_text(
        "runtime checkpoint load execution profile", request.execution_profile_id
    )
    _require_sha256_text(
        "runtime checkpoint load market profile", request.market_source_profile_id
    )
    return (
        _runtime_checkpoint_field_m1(application_id),
        _runtime_checkpoint_field_text(request.execution_profile_id),
        _runtime_checkpoint_field_text(request.market_source_profile_id),
    )


def _runtime_checkpoint_load_proof_binding(
    request: RuntimeCheckpointLoadRequest,
    initial_checkpoint: KernelCheckpointRecord,
    payload: RuntimeCheckpointPayloadRecord,
    selection: _RuntimeCheckpointSelectionSet,
) -> bytes:
    """Bind one freshly reselected private load proof without minting authority."""

    request_coordinates = _runtime_checkpoint_load_request_binding(request)
    head_binding = _runtime_checkpoint_head_record_binding(initial_checkpoint)
    payload_binding = _runtime_checkpoint_payload_record_binding(payload)
    selection_binding = _runtime_checkpoint_selection_set_binding(selection)
    if (
        initial_checkpoint.application_generation_id
        != request.application_generation_id
        or payload.application_generation_id != request.application_generation_id
        or payload.execution_profile_id != request.execution_profile_id
        or payload.market_source_profile_id != request.market_source_profile_id
        or payload.currentness_head_ordinal
        != initial_checkpoint.currentness_head_ordinal
        or payload.checkpoint_version_ordinal
        != initial_checkpoint.checkpoint_version_ordinal
        or payload.payload_sha256 != initial_checkpoint.checkpoint_sha256
    ):
        raise ValueError("runtime checkpoint load proof coordinates do not agree")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/load-proof/v1",
        *request_coordinates,
        head_binding,
        payload_binding,
        selection_binding,
    )


def _runtime_checkpoint_register(value: object, binding: bytes, provenance: str) -> None:
    exact_binding = _runtime_checkpoint_require_binding(
        "runtime checkpoint registry binding", binding
    )
    if type(provenance) is not str:
        raise TypeError("runtime checkpoint provenance must be exact text")
    key = id(value)

    def cleanup(reference: object) -> None:
        with _RUNTIME_CHECKPOINT_REGISTRY_LOCK:
            retained = _RUNTIME_CHECKPOINT_REGISTRY.get(key)
            if retained is not None and retained[0] is reference:
                del _RUNTIME_CHECKPOINT_REGISTRY[key]

    reference = _weakref_ref(value, cleanup)
    with _RUNTIME_CHECKPOINT_REGISTRY_LOCK:
        retained = _RUNTIME_CHECKPOINT_REGISTRY.get(key)
        if retained is not None and retained[0]() is not None:
            raise ValueError("runtime checkpoint object identity is already registered")
        _RUNTIME_CHECKPOINT_REGISTRY[key] = (
            reference,
            exact_binding,
            provenance,
        )


def _runtime_checkpoint_registry_authentic(
    value: object, binding: bytes, provenance: str
) -> bool:
    with _RUNTIME_CHECKPOINT_REGISTRY_LOCK:
        retained = _RUNTIME_CHECKPOINT_REGISTRY.get(id(value))
        return bool(
            retained is not None
            and retained[0]() is value
            and retained[1] == binding
            and retained[2] == provenance
        )


class _RuntimeCheckpointNonCopyable:
    __slots__ = ()

    def __copy__(self) -> _Any:
        raise TypeError(f"{type(self).__name__} cannot be copied")

    def __deepcopy__(self, memo: object) -> _Any:
        del memo
        raise TypeError(f"{type(self).__name__} cannot be copied")

    def __reduce__(self) -> _Any:
        raise TypeError(f"{type(self).__name__} cannot be reduced")

    def __reduce_ex__(self, protocol: _Any) -> _Any:
        del protocol
        raise TypeError(f"{type(self).__name__} cannot be reduced")


@_dataclass(frozen=True, slots=True, init=False, weakref_slot=True)
class RuntimeCheckpointSelectionProof(_RuntimeCheckpointNonCopyable):
    request: RuntimeCheckpointSelectionRequest
    application_generation: ApplicationGenerationRecord
    execution_profile: _profiles.ExecutionConnectionProfile
    market_source_profile: _profiles.MarketDataSourceProfile
    predecessor_checkpoint: KernelCheckpointRecord | None
    target_currentness_head_ordinal: int
    target_checkpoint_version_ordinal: int
    selection_commitment: bytes
    _selection: _RuntimeCheckpointSelectionSet
    _binding: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("RuntimeCheckpointSelectionProof is repository-issued")

    @classmethod
    def _is_authentic(cls, value: object) -> bool:
        if cls is not RuntimeCheckpointSelectionProof or type(value) is not cls:
            return False
        try:
            binding = _runtime_checkpoint_selection_proof_binding(value)
            return bool(
                type(value._binding) is bytes
                and value._binding == binding
                and _runtime_checkpoint_registry_authentic(
                    value, binding, "SELECTION"
                )
            )
        except (AttributeError, TypeError, ValueError, OverflowError):
            return False

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("RuntimeCheckpointSelectionProof cannot be subclassed")


def _runtime_checkpoint_selection_proof_binding(
    proof: RuntimeCheckpointSelectionProof,
) -> bytes:
    if type(proof) is not RuntimeCheckpointSelectionProof:
        raise TypeError("runtime checkpoint selection proof must be exact")
    request_binding = _runtime_checkpoint_selection_request_binding(proof.request)
    application_binding = _runtime_checkpoint_application_record_binding(
        proof.application_generation
    )
    execution_binding = _runtime_checkpoint_execution_profile_binding(
        proof.execution_profile
    )
    market_binding = _runtime_checkpoint_market_profile_binding(
        proof.market_source_profile
    )
    predecessor_binding = (
        None
        if proof.predecessor_checkpoint is None
        else _runtime_checkpoint_head_record_binding(proof.predecessor_checkpoint)
    )
    target_head = _runtime_checkpoint_require_nonnegative_int(
        "runtime checkpoint target head", proof.target_currentness_head_ordinal
    )
    target_version = _runtime_checkpoint_require_positive_int(
        "runtime checkpoint target version", proof.target_checkpoint_version_ordinal
    )
    selection_binding = _runtime_checkpoint_selection_set_binding(proof._selection)
    _runtime_checkpoint_require_binding(
        "runtime checkpoint selection commitment", proof.selection_commitment
    )
    application_id = proof.request.application_generation_id
    if (
        proof.application_generation.application_generation_id != application_id
        or proof.application_generation.selected_execution_profile_id
        != proof.request.execution_profile_id
        or proof.application_generation.selected_market_source_profile_id
        != proof.request.market_source_profile_id
        or proof.execution_profile.connection_profile_id
        != proof.request.execution_profile_id
        or proof.execution_profile.application_generation != application_id.value
        or proof.market_source_profile.market_source_profile_id
        != proof.request.market_source_profile_id
        or proof.predecessor_checkpoint != proof.request.expected_checkpoint
        or proof.selection_commitment != selection_binding
    ):
        raise ValueError("runtime checkpoint selection proof coordinates do not agree")
    if proof.predecessor_checkpoint is None:
        if target_version != 1:
            raise ValueError("runtime checkpoint genesis target version must be one")
    elif (
        target_head < proof.predecessor_checkpoint.currentness_head_ordinal
        or target_version
        != proof.predecessor_checkpoint.checkpoint_version_ordinal + 1
    ):
        raise ValueError("runtime checkpoint target does not advance its predecessor")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/selection-proof/v1",
        request_binding,
        application_binding,
        execution_binding,
        market_binding,
        _runtime_checkpoint_optional_record_binding(predecessor_binding),
        _encode_int(target_head),
        _encode_int(target_version),
        selection_binding,
    )


def _issue_runtime_checkpoint_selection_proof(
    request: RuntimeCheckpointSelectionRequest,
    application_generation: ApplicationGenerationRecord,
    execution_profile: _profiles.ExecutionConnectionProfile,
    market_source_profile: _profiles.MarketDataSourceProfile,
    predecessor_checkpoint: KernelCheckpointRecord | None,
    target_currentness_head_ordinal: int,
    target_checkpoint_version_ordinal: int,
    selection: _RuntimeCheckpointSelectionSet,
) -> RuntimeCheckpointSelectionProof:
    result = object.__new__(RuntimeCheckpointSelectionProof)
    object.__setattr__(result, "request", request)
    object.__setattr__(result, "application_generation", application_generation)
    object.__setattr__(result, "execution_profile", execution_profile)
    object.__setattr__(result, "market_source_profile", market_source_profile)
    object.__setattr__(result, "predecessor_checkpoint", predecessor_checkpoint)
    object.__setattr__(
        result, "target_currentness_head_ordinal", target_currentness_head_ordinal
    )
    object.__setattr__(
        result, "target_checkpoint_version_ordinal", target_checkpoint_version_ordinal
    )
    object.__setattr__(
        result,
        "selection_commitment",
        _runtime_checkpoint_selection_set_binding(selection),
    )
    object.__setattr__(result, "_selection", selection)
    binding = _runtime_checkpoint_selection_proof_binding(result)
    object.__setattr__(result, "_binding", binding)
    _runtime_checkpoint_register(result, binding, "SELECTION")
    return result


@_dataclass(frozen=True, slots=True, init=False, weakref_slot=True)
class RuntimeCheckpointWriteReceipt(_RuntimeCheckpointNonCopyable):
    payload: RuntimeCheckpointPayloadRecord
    predecessor_checkpoint: KernelCheckpointRecord | None
    resulting_checkpoint: KernelCheckpointRecord
    selection_commitment: bytes
    _binding: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("RuntimeCheckpointWriteReceipt is repository-issued")

    @classmethod
    def _is_authentic(cls, value: object) -> bool:
        if cls is not RuntimeCheckpointWriteReceipt or type(value) is not cls:
            return False
        try:
            binding = _runtime_checkpoint_write_receipt_binding(value)
            return bool(
                type(value._binding) is bytes
                and value._binding == binding
                and _runtime_checkpoint_registry_authentic(value, binding, "RECEIPT")
            )
        except (AttributeError, TypeError, ValueError, OverflowError):
            return False

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("RuntimeCheckpointWriteReceipt cannot be subclassed")


def _runtime_checkpoint_write_receipt_binding(
    receipt: RuntimeCheckpointWriteReceipt,
) -> bytes:
    if type(receipt) is not RuntimeCheckpointWriteReceipt:
        raise TypeError("runtime checkpoint write receipt must be exact")
    payload_binding = _runtime_checkpoint_payload_record_binding(receipt.payload)
    predecessor_binding = (
        None
        if receipt.predecessor_checkpoint is None
        else _runtime_checkpoint_head_record_binding(receipt.predecessor_checkpoint)
    )
    resulting_binding = _runtime_checkpoint_head_record_binding(
        receipt.resulting_checkpoint
    )
    selection_commitment = _runtime_checkpoint_require_binding(
        "runtime checkpoint receipt selection commitment",
        receipt.selection_commitment,
    )
    payload = receipt.payload
    resulting = receipt.resulting_checkpoint
    if (
        resulting.application_generation_id != payload.application_generation_id
        or resulting.currentness_head_ordinal != payload.currentness_head_ordinal
        or resulting.checkpoint_version_ordinal != payload.checkpoint_version_ordinal
        or resulting.checkpoint_sha256 != payload.payload_sha256
    ):
        raise ValueError("runtime checkpoint receipt result does not match its payload")
    predecessor = receipt.predecessor_checkpoint
    if predecessor is None:
        if resulting.checkpoint_version_ordinal != 1:
            raise ValueError("runtime checkpoint genesis receipt version must be one")
    elif (
        predecessor.application_generation_id != resulting.application_generation_id
        or resulting.currentness_head_ordinal < predecessor.currentness_head_ordinal
        or resulting.checkpoint_version_ordinal
        != predecessor.checkpoint_version_ordinal + 1
    ):
        raise ValueError("runtime checkpoint receipt does not advance its predecessor")
    return _commit_parts(
        b"execution-core/runtime-checkpoint/write-receipt/v1",
        payload_binding,
        _runtime_checkpoint_optional_record_binding(predecessor_binding),
        resulting_binding,
        selection_commitment,
    )


def _issue_runtime_checkpoint_write_receipt(
    payload: RuntimeCheckpointPayloadRecord,
    predecessor_checkpoint: KernelCheckpointRecord | None,
    resulting_checkpoint: KernelCheckpointRecord,
    selection_commitment: bytes,
) -> RuntimeCheckpointWriteReceipt:
    result = object.__new__(RuntimeCheckpointWriteReceipt)
    object.__setattr__(result, "payload", payload)
    object.__setattr__(result, "predecessor_checkpoint", predecessor_checkpoint)
    object.__setattr__(result, "resulting_checkpoint", resulting_checkpoint)
    object.__setattr__(result, "selection_commitment", selection_commitment)
    binding = _runtime_checkpoint_write_receipt_binding(result)
    object.__setattr__(result, "_binding", binding)
    _runtime_checkpoint_register(result, binding, "RECEIPT")
    return result


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
        _validate_durable_input_operation_binding(self)
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


@_dataclass(frozen=True, slots=True)
class DecisionReceiptRecord:
    """Immutable explanatory receipt correlated to one durable input outcome."""

    receipt_ordinal: int
    application_generation_id: _identity.ApplicationGenerationId
    input_domain: _operations.OperationDomain
    input_identity_sha256: str
    owner_domain: str
    owner_disposition: str
    terminal_technical_state: str
    result_sha256: str
    checkpoint_currentness_head_ordinal: int | None
    checkpoint_version_ordinal: int | None
    checkpoint_payload_sha256: str | None
    canonical_receipt_bytes: bytes
    receipt_length: int
    receipt_sha256: str

    def __post_init__(self) -> None:
        if type(self.receipt_ordinal) is not int:
            raise TypeError("decision receipt ordinal must be an exact integer")
        if self.receipt_ordinal < 1:
            raise ValueError("decision receipt ordinal must be positive")
        _validate_durable_input_reference(
            "decision receipt",
            self.application_generation_id,
            self.input_domain,
            self.input_identity_sha256,
        )
        _validate_input_owner_domain(
            "decision receipt", self.input_domain, self.owner_domain
        )
        checkpoint_reference = _validate_owner_result_fields(
            "decision receipt",
            self.owner_domain,
            self.owner_disposition,
            self.terminal_technical_state,
            self.result_sha256,
            self.checkpoint_currentness_head_ordinal,
            self.checkpoint_version_ordinal,
            self.checkpoint_payload_sha256,
        )
        document = _validate_canonical_document_bytes(
            "decision receipt",
            self.canonical_receipt_bytes,
            self.receipt_length,
            self.receipt_sha256,
            _M2_DECISION_RECEIPT_DOCUMENT_KIND,
        )
        _validate_decision_receipt_document(self, checkpoint_reference, document)


@_dataclass(frozen=True, slots=True)
class DurableInputOutcomeRecord:
    """Immutable terminal owner result that refers to its mandatory receipt."""

    application_generation_id: _identity.ApplicationGenerationId
    input_domain: _operations.OperationDomain
    input_identity_sha256: str
    owner_domain: str
    owner_disposition: str
    terminal_technical_state: str
    result_sha256: str
    checkpoint_currentness_head_ordinal: int | None
    checkpoint_version_ordinal: int | None
    checkpoint_payload_sha256: str | None
    receipt_ordinal: int
    receipt_sha256: str
    canonical_outcome_bytes: bytes
    outcome_length: int
    outcome_sha256: str

    def __post_init__(self) -> None:
        _validate_durable_input_reference(
            "durable input outcome",
            self.application_generation_id,
            self.input_domain,
            self.input_identity_sha256,
        )
        _validate_input_owner_domain(
            "durable input outcome", self.input_domain, self.owner_domain
        )
        checkpoint_reference = _validate_owner_result_fields(
            "durable input outcome",
            self.owner_domain,
            self.owner_disposition,
            self.terminal_technical_state,
            self.result_sha256,
            self.checkpoint_currentness_head_ordinal,
            self.checkpoint_version_ordinal,
            self.checkpoint_payload_sha256,
        )
        if type(self.receipt_ordinal) is not int:
            raise TypeError("outcome receipt ordinal must be an exact integer")
        if self.receipt_ordinal < 1:
            raise ValueError("outcome receipt ordinal must be positive")
        _require_sha256_text("outcome receipt SHA-256", self.receipt_sha256)
        document = _validate_canonical_document_bytes(
            "durable input outcome",
            self.canonical_outcome_bytes,
            self.outcome_length,
            self.outcome_sha256,
            _M2_INPUT_OUTCOME_DOCUMENT_KIND,
        )
        _validate_durable_input_outcome_document(
            self,
            checkpoint_reference,
            document,
        )


@_dataclass(frozen=True, slots=True)
class BrokerOutboxRecord:
    """Immutable dispatch snapshot, never a broker-success or serving fact."""

    outbox_sequence: int
    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    scope_id: int
    acquisition_generation_id: _identity.AcquisitionGenerationId
    input_domain: _operations.OperationDomain
    input_identity_sha256: str
    effect_id: int
    claim_id: int
    canonical_payload_bytes: bytes
    payload_length: int
    payload_sha256: str

    def __post_init__(self) -> None:
        if type(self.outbox_sequence) is not int:
            raise TypeError("broker outbox sequence must be an exact integer")
        if self.outbox_sequence < 1:
            raise ValueError("broker outbox sequence must be positive")
        if (
            type(self.application_generation_id)
            is not _identity.ApplicationGenerationId
        ):
            raise TypeError("broker outbox application generation must be exact")
        _identity.ApplicationGenerationId(self.application_generation_id.value)
        _require_sha256_text(
            "broker outbox execution profile", self.execution_profile_id
        )
        if type(self.scope_id) is not int:
            raise TypeError("broker outbox scope must be an exact integer")
        if self.scope_id < 1:
            raise ValueError("broker outbox scope must be positive")
        if (
            type(self.acquisition_generation_id)
            is not _identity.AcquisitionGenerationId
        ):
            raise TypeError("broker outbox acquisition generation must be exact")
        if not _identity._acquisition_generation_id_is_canonical(
            self.acquisition_generation_id
        ):
            raise ValueError("broker outbox acquisition generation is not canonical")
        if type(self.input_domain) is not _operations.OperationDomain:
            raise TypeError("broker outbox input domain must be exact OperationDomain")
        if self.input_domain not in _OUTBOX_INPUT_DOMAINS:
            raise ValueError("broker outbox input domain is not admitted")
        _require_sha256_text("broker outbox input identity", self.input_identity_sha256)
        if type(self.effect_id) is not int:
            raise TypeError("broker outbox effect id must be an exact integer")
        if self.effect_id < 1:
            raise ValueError("broker outbox effect id must be positive")
        if type(self.claim_id) is not int:
            raise TypeError("broker outbox claim id must be an exact integer")
        if self.claim_id < 1:
            raise ValueError("broker outbox claim id must be positive")
        document = _validate_canonical_document_bytes(
            "broker outbox",
            self.canonical_payload_bytes,
            self.payload_length,
            self.payload_sha256,
            _M2_BROKER_OUTBOX_DOCUMENT_KIND,
        )
        _validate_broker_outbox_document(self, document)


@_dataclass(frozen=True, slots=True)
class DurableInputSemanticKeyRecord:
    """Immutable alternate-key row whose canonical bytes remain authoritative."""

    key_kind: _operations.InputSemanticKeyKind
    key_application_generation_id: _identity.ApplicationGenerationId | None
    execution_profile_id: str
    key_scope_id: int | None
    canonical_key_bytes: bytes
    key_sha256: str
    input_application_generation_id: _identity.ApplicationGenerationId
    input_domain: _operations.OperationDomain
    input_identity_sha256: str
    created_ordinal: int

    def __post_init__(self) -> None:
        if type(self.key_kind) is not _operations.InputSemanticKeyKind:
            raise TypeError("semantic key kind must be exact InputSemanticKeyKind")
        _require_optional_exact_identity(
            "semantic key application generation",
            self.key_application_generation_id,
            _identity.ApplicationGenerationId,
        )
        _require_sha256_text(
            "semantic key execution profile", self.execution_profile_id
        )
        if self.key_scope_id is not None:
            if type(self.key_scope_id) is not int:
                raise TypeError("semantic key scope id must be an exact integer")
            if self.key_scope_id < 1:
                raise ValueError("semantic key scope id must be positive")
        if type(self.canonical_key_bytes) is not bytes:
            raise TypeError("semantic key bytes must be exact bytes")
        if not self.canonical_key_bytes:
            raise ValueError("semantic key bytes must be nonempty")
        _require_sha256_text("semantic key SHA-256", self.key_sha256)
        if self.key_sha256 != _sha256(self.canonical_key_bytes).hexdigest():
            raise ValueError("semantic key SHA-256 does not match key bytes")
        if (
            type(self.input_application_generation_id)
            is not _identity.ApplicationGenerationId
        ):
            raise TypeError("semantic key input application generation must be exact")
        _identity.ApplicationGenerationId(self.input_application_generation_id.value)
        if type(self.input_domain) is not _operations.OperationDomain:
            raise TypeError("semantic key input domain must be exact OperationDomain")
        _require_sha256_text("semantic key input identity", self.input_identity_sha256)
        if type(self.created_ordinal) is not int:
            raise TypeError("semantic key created ordinal must be an exact integer")
        if self.created_ordinal < 1:
            raise ValueError("semantic key created ordinal must be positive")
        _validate_durable_input_semantic_key_coordinates(self)


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


def _validate_durable_input_operation_binding(record: DurableInputRecord) -> None:
    """Require stored input fields to be the exact projection of retained bytes."""

    try:
        operation = _operations.decode_m2_operation(record.canonical_payload_bytes)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "durable input payload must be a canonical operation document"
        ) from error
    if _operations.encode_m2_operation(operation) != record.canonical_payload_bytes:
        raise ValueError("durable input payload must be a canonical operation document")
    (
        input_domain,
        application_generation_id,
        execution_profile_id,
        scope_id,
        session_id,
        acquisition_generation_id,
        market_source_profile_id,
        stream_generation_id,
        input_identity_sha256,
    ) = _operations._derive_m2_durable_input_projection(operation)
    if record.input_domain is not input_domain:
        raise ValueError("durable input domain does not match canonical operation")
    if record.application_generation_id != application_generation_id:
        raise ValueError(
            "durable input application generation does not match canonical operation"
        )
    if record.execution_profile_id != execution_profile_id:
        raise ValueError(
            "durable input execution profile does not match canonical operation"
        )
    if record.scope_id != scope_id:
        raise ValueError("durable input scope does not match canonical operation")
    if record.session_id != session_id:
        raise ValueError("durable input session does not match canonical operation")
    if record.acquisition_generation_id != acquisition_generation_id:
        raise ValueError(
            "durable input acquisition generation does not match canonical operation"
        )
    if record.market_source_profile_id != market_source_profile_id:
        raise ValueError(
            "durable input market-source profile does not match canonical operation"
        )
    if record.stream_generation_id != stream_generation_id:
        raise ValueError(
            "durable input stream generation does not match canonical operation"
        )
    if record.input_identity_sha256 != input_identity_sha256:
        raise ValueError("durable input identity does not match canonical operation")


_CheckpointReference = tuple[int, int, str]


def _validate_durable_input_reference(
    record_name: str,
    application_generation_id: object,
    input_domain: object,
    input_identity_sha256: object,
) -> None:
    if type(application_generation_id) is not _identity.ApplicationGenerationId:
        raise TypeError(f"{record_name} application generation must be exact")
    _identity.ApplicationGenerationId(application_generation_id.value)
    if type(input_domain) is not _operations.OperationDomain:
        raise TypeError(f"{record_name} input domain must be exact OperationDomain")
    _require_sha256_text(f"{record_name} input identity", input_identity_sha256)


def _validate_input_owner_domain(
    record_name: str,
    input_domain: _operations.OperationDomain,
    owner_domain: object,
) -> None:
    if type(owner_domain) is not str:
        raise TypeError(f"{record_name} owner domain must be exact text")
    if _OPERATION_OWNER_DOMAINS[input_domain] != owner_domain:
        raise ValueError(f"{record_name} owner domain does not match input domain")


def _checkpoint_reference_from_fields(
    record_name: str,
    currentness_head_ordinal: object,
    checkpoint_version_ordinal: object,
    checkpoint_payload_sha256: object,
) -> _CheckpointReference | None:
    members = (
        currentness_head_ordinal,
        checkpoint_version_ordinal,
        checkpoint_payload_sha256,
    )
    if all(member is None for member in members):
        return None
    if any(member is None for member in members):
        raise ValueError(f"{record_name} checkpoint reference must be all-or-none")
    if type(currentness_head_ordinal) is not int:
        raise TypeError(f"{record_name} checkpoint head must be an exact integer")
    if currentness_head_ordinal < 0:
        raise ValueError(f"{record_name} checkpoint head must be non-negative")
    if type(checkpoint_version_ordinal) is not int:
        raise TypeError(f"{record_name} checkpoint version must be an exact integer")
    if checkpoint_version_ordinal < 1:
        raise ValueError(f"{record_name} checkpoint version must be positive")
    return (
        currentness_head_ordinal,
        checkpoint_version_ordinal,
        _require_sha256_text(
            f"{record_name} checkpoint payload SHA-256",
            checkpoint_payload_sha256,
        ),
    )


def _encode_checkpoint_reference(
    reference: _CheckpointReference | None,
) -> list[object] | None:
    if reference is None:
        return None
    return [reference[0], reference[1], reference[2]]


def _decode_checkpoint_reference(
    record_name: str,
    value: object,
) -> _CheckpointReference | None:
    if value is None:
        return None
    if type(value) is not list or len(value) != 3:
        raise ValueError(f"{record_name} checkpoint reference is malformed")
    reference = _checkpoint_reference_from_fields(
        record_name,
        value[0],
        value[1],
        value[2],
    )
    if reference is None or _encode_checkpoint_reference(reference) != value:
        raise ValueError(f"{record_name} checkpoint reference is not canonical")
    return reference


def _derive_owner_result_sha256(
    owner_domain: str,
    owner_disposition: str,
    terminal_technical_state: str,
    checkpoint_reference: _CheckpointReference | None,
) -> str:
    """Derive the immutable owner-result digest from its complete semantic tuple."""

    payload = _operations._encode_m2_canonical_json(
        [
            1,
            owner_domain,
            owner_disposition,
            terminal_technical_state,
            _encode_checkpoint_reference(checkpoint_reference),
        ]
    )
    return _sha256(
        _M2_REDUCER_RESULT_PREFIX + len(payload).to_bytes(8, "big") + payload
    ).hexdigest()


def _validate_owner_result_fields(
    record_name: str,
    owner_domain: object,
    owner_disposition: object,
    terminal_technical_state: object,
    result_sha256: object,
    checkpoint_currentness_head_ordinal: object,
    checkpoint_version_ordinal: object,
    checkpoint_payload_sha256: object,
) -> _CheckpointReference | None:
    if type(owner_domain) is not str:
        raise TypeError(f"{record_name} owner domain must be exact text")
    admitted_dispositions = _OWNER_DISPOSITIONS.get(owner_domain)
    if admitted_dispositions is None:
        raise ValueError(f"{record_name} owner domain is not admitted")
    if type(owner_disposition) is not str:
        raise TypeError(f"{record_name} owner disposition must be exact text")
    if owner_disposition not in admitted_dispositions:
        raise ValueError(f"{record_name} owner disposition is not admitted")
    if type(terminal_technical_state) is not str:
        raise TypeError(f"{record_name} terminal technical state must be exact text")
    expected_technical_state = (
        "RECONCILIATION_PENDING"
        if owner_disposition == "RECONCILIATION_REQUIRED"
        else "TERMINAL"
    )
    if terminal_technical_state != expected_technical_state:
        raise ValueError(
            f"{record_name} terminal technical state does not match disposition"
        )
    checkpoint_reference = _checkpoint_reference_from_fields(
        record_name,
        checkpoint_currentness_head_ordinal,
        checkpoint_version_ordinal,
        checkpoint_payload_sha256,
    )
    _require_sha256_text(f"{record_name} result SHA-256", result_sha256)
    expected_result_sha256 = _derive_owner_result_sha256(
        owner_domain,
        owner_disposition,
        terminal_technical_state,
        checkpoint_reference,
    )
    if result_sha256 != expected_result_sha256:
        raise ValueError(f"{record_name} result SHA-256 does not match result fields")
    return checkpoint_reference


def _validate_canonical_document_bytes(
    record_name: str,
    document_bytes: object,
    document_length: object,
    document_sha256: object,
    expected_kind_octet: int,
) -> list[object]:
    if type(document_bytes) is not bytes:
        raise TypeError(f"{record_name} document bytes must be exact bytes")
    if not document_bytes:
        raise ValueError(f"{record_name} document bytes must be nonempty")
    if type(document_length) is not int:
        raise TypeError(f"{record_name} document length must be an exact integer")
    if document_length != len(document_bytes):
        raise ValueError(f"{record_name} document length does not match document bytes")
    _require_sha256_text(f"{record_name} document SHA-256", document_sha256)
    if document_sha256 != _sha256(document_bytes).hexdigest():
        raise ValueError(
            f"{record_name} document SHA-256 does not match document bytes"
        )
    try:
        return _operations._decode_m2_document_kind(
            document_bytes,
            expected_kind_octet,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"{record_name} document is not canonical") from error


def _validate_document_application_generation(
    record_name: str,
    value: object,
    expected: _identity.ApplicationGenerationId,
) -> None:
    decoded = _operations._decode_m2_m1_as(
        f"{record_name} application generation",
        value,
        _identity.ApplicationGenerationId,
    )
    if decoded != expected:
        raise ValueError(
            f"{record_name} application generation does not match document"
        )


def _validate_document_domain(
    record_name: str,
    value: object,
    expected: _operations.OperationDomain,
) -> None:
    if value != _operations._encode_m2_enum(expected):
        raise ValueError(f"{record_name} input domain does not match document")


def _validate_decision_receipt_document(
    record: DecisionReceiptRecord,
    checkpoint_reference: _CheckpointReference | None,
    document: list[object],
) -> None:
    if len(document) != 11:
        raise ValueError("decision receipt document must have exactly eleven members")
    if _operations._require_exact_int("decision receipt version", document[0]) != 1:
        raise ValueError("decision receipt document version is not admitted")
    if document[1] != "m2.decision-receipt/v1":
        raise ValueError("decision receipt document type tag is not admitted")
    _validate_document_application_generation(
        "decision receipt", document[2], record.application_generation_id
    )
    _validate_document_domain("decision receipt", document[3], record.input_domain)
    if document[4] != record.input_identity_sha256:
        raise ValueError("decision receipt input identity does not match document")
    if _operations._require_exact_int("decision receipt ordinal", document[5]) != (
        record.receipt_ordinal
    ):
        raise ValueError("decision receipt ordinal does not match document")
    if document[6] != record.owner_domain:
        raise ValueError("decision receipt owner domain does not match document")
    if document[7] != record.owner_disposition:
        raise ValueError("decision receipt disposition does not match document")
    if document[8] != record.terminal_technical_state:
        raise ValueError("decision receipt technical state does not match document")
    if document[9] != record.result_sha256:
        raise ValueError("decision receipt result SHA-256 does not match document")
    if _decode_checkpoint_reference("decision receipt", document[10]) != (
        checkpoint_reference
    ):
        raise ValueError(
            "decision receipt checkpoint reference does not match document"
        )


def _validate_durable_input_outcome_document(
    record: DurableInputOutcomeRecord,
    checkpoint_reference: _CheckpointReference | None,
    document: list[object],
) -> None:
    if len(document) != 12:
        raise ValueError(
            "durable input outcome document must have exactly twelve members"
        )
    if (
        _operations._require_exact_int("durable input outcome version", document[0])
        != 1
    ):
        raise ValueError("durable input outcome document version is not admitted")
    if document[1] != "m2.durable-input-outcome/v1":
        raise ValueError("durable input outcome document type tag is not admitted")
    _validate_document_application_generation(
        "durable input outcome", document[2], record.application_generation_id
    )
    _validate_document_domain("durable input outcome", document[3], record.input_domain)
    if document[4] != record.input_identity_sha256:
        raise ValueError("durable input outcome input identity does not match document")
    if document[5] != record.owner_domain:
        raise ValueError("durable input outcome owner domain does not match document")
    if document[6] != record.owner_disposition:
        raise ValueError("durable input outcome disposition does not match document")
    if document[7] != record.terminal_technical_state:
        raise ValueError(
            "durable input outcome technical state does not match document"
        )
    if document[8] != record.result_sha256:
        raise ValueError("durable input outcome result SHA-256 does not match document")
    if _decode_checkpoint_reference("durable input outcome", document[9]) != (
        checkpoint_reference
    ):
        raise ValueError(
            "durable input outcome checkpoint reference does not match document"
        )
    if _operations._require_exact_int("outcome receipt ordinal", document[10]) != (
        record.receipt_ordinal
    ):
        raise ValueError(
            "durable input outcome receipt ordinal does not match document"
        )
    if document[11] != record.receipt_sha256:
        raise ValueError(
            "durable input outcome receipt SHA-256 does not match document"
        )


def _require_document_nonnegative_int(name: str, value: object) -> int:
    decoded = _operations._require_exact_int(name, value)
    if decoded < 0:
        raise ValueError(f"{name} must be non-negative")
    return decoded


def _require_document_positive_int(name: str, value: object) -> int:
    decoded = _operations._require_exact_int(name, value)
    if decoded < 1:
        raise ValueError(f"{name} must be positive")
    return decoded


def _validate_broker_outbox_document(
    record: BrokerOutboxRecord,
    document: list[object],
) -> None:
    if len(document) != 26:
        raise ValueError("broker outbox document must have exactly twenty-six members")
    if _operations._require_exact_int("broker outbox version", document[0]) != 1:
        raise ValueError("broker outbox document version is not admitted")
    if document[1] != "m2.broker-outbox/v1":
        raise ValueError("broker outbox document type tag is not admitted")
    if _require_document_positive_int("broker outbox sequence", document[2]) != (
        record.outbox_sequence
    ):
        raise ValueError("broker outbox sequence does not match document")
    _validate_document_application_generation(
        "broker outbox", document[3], record.application_generation_id
    )
    _require_sha256_text("broker outbox document execution profile", document[4])
    if document[4] != record.execution_profile_id:
        raise ValueError("broker outbox execution profile does not match document")
    if _require_document_positive_int("broker outbox scope", document[5]) != (
        record.scope_id
    ):
        raise ValueError("broker outbox scope does not match document")
    acquisition_generation_id = _operations._decode_m2_m1_as(
        "broker outbox acquisition generation",
        document[6],
        _identity.AcquisitionGenerationId,
    )
    if acquisition_generation_id != record.acquisition_generation_id:
        raise ValueError("broker outbox acquisition generation does not match document")
    _validate_document_domain("broker outbox", document[7], record.input_domain)
    if document[8] != record.input_identity_sha256:
        raise ValueError("broker outbox input identity does not match document")
    if _require_document_positive_int("broker outbox effect id", document[9]) != (
        record.effect_id
    ):
        raise ValueError("broker outbox effect id does not match document")
    _operations._decode_m2_m1_as(
        "broker outbox effect external",
        document[10],
        _identity.EffectId,
    )
    _operations._decode_m2_m1_as(
        "broker outbox request occurrence",
        document[11],
        _identity.RequestOccurrenceId,
    )
    _operations._decode_m2_m1_as(
        "broker outbox mandate",
        document[12],
        _identity.MandateId,
    )
    _require_sha256_text("broker outbox mandate commitment", document[13])
    _require_document_nonnegative_int(
        "broker outbox expected controller head", document[14]
    )
    _require_document_positive_int(
        "broker outbox expected protection version", document[15]
    )
    _operations._require_exact_text("broker outbox authority class", document[16])
    _operations._decode_m2_enum_as(
        "broker outbox effect kind",
        document[17],
        _venue.EffectKind,
    )
    _operations._decode_m2_optional_m1_as(
        "broker outbox client order",
        document[18],
        _identity.ClientOrderId,
    )
    _operations._decode_m2_optional_m1_as(
        "broker outbox target order",
        document[19],
        _identity.OrderId,
    )
    _operations._decode_m2_enum_as(
        "broker outbox side",
        document[20],
        _fills.ExecutionSide,
    )
    _operations._decode_m2_m1_as(
        "broker outbox quantity",
        document[21],
        _values.Quantity,
    )
    _operations._decode_m2_bytes("broker outbox economic scope", document[22])
    if _require_document_positive_int("broker outbox claim id", document[23]) != (
        record.claim_id
    ):
        raise ValueError("broker outbox claim id does not match document")
    _operations._decode_m2_m1_as(
        "broker outbox claim occurrence",
        document[24],
        _identity.ClaimOccurrenceId,
    )
    _require_document_positive_int("broker outbox claim ordinal", document[25])


def _decode_broker_outbox_snapshot(
    record: BrokerOutboxRecord,
) -> tuple[
    _identity.EffectId,
    _identity.RequestOccurrenceId,
    _identity.MandateId,
    str,
    int,
    int,
    str,
    _venue.EffectKind,
    _identity.ClientOrderId | None,
    _identity.OrderId | None,
    _fills.ExecutionSide,
    _values.Quantity,
    bytes,
    _identity.ClaimOccurrenceId,
    int,
]:
    """Re-decode the immutable outbox snapshot for repository cross-row binding."""

    if type(record) is not BrokerOutboxRecord:
        raise TypeError("broker outbox snapshot requires an exact record")
    document = _validate_canonical_document_bytes(
        "broker outbox",
        record.canonical_payload_bytes,
        record.payload_length,
        record.payload_sha256,
        _M2_BROKER_OUTBOX_DOCUMENT_KIND,
    )
    _validate_broker_outbox_document(record, document)
    return (
        _operations._decode_m2_m1_as(
            "broker outbox effect external", document[10], _identity.EffectId
        ),
        _operations._decode_m2_m1_as(
            "broker outbox request occurrence",
            document[11],
            _identity.RequestOccurrenceId,
        ),
        _operations._decode_m2_m1_as(
            "broker outbox mandate", document[12], _identity.MandateId
        ),
        _require_sha256_text("broker outbox mandate commitment", document[13]),
        _require_document_nonnegative_int(
            "broker outbox expected controller head", document[14]
        ),
        _require_document_positive_int(
            "broker outbox expected protection version", document[15]
        ),
        _operations._require_exact_text("broker outbox authority class", document[16]),
        _operations._decode_m2_enum_as(
            "broker outbox effect kind", document[17], _venue.EffectKind
        ),
        _operations._decode_m2_optional_m1_as(
            "broker outbox client order", document[18], _identity.ClientOrderId
        ),
        _operations._decode_m2_optional_m1_as(
            "broker outbox target order", document[19], _identity.OrderId
        ),
        _operations._decode_m2_enum_as(
            "broker outbox side", document[20], _fills.ExecutionSide
        ),
        _operations._decode_m2_m1_as(
            "broker outbox quantity", document[21], _values.Quantity
        ),
        _operations._decode_m2_bytes("broker outbox economic scope", document[22]),
        _operations._decode_m2_m1_as(
            "broker outbox claim occurrence",
            document[24],
            _identity.ClaimOccurrenceId,
        ),
        _require_document_positive_int("broker outbox claim ordinal", document[25]),
    )


def _validate_durable_input_semantic_key_coordinates(
    record: DurableInputSemanticKeyRecord,
) -> None:
    """Bind canonical semantic-key bytes to their exact stored collision domain."""

    decoded_kind, coordinates, _ = _operations.decode_m2_semantic_key(
        record.canonical_key_bytes
    )
    if decoded_kind is not record.key_kind:
        raise ValueError("semantic key kind does not match canonical key bytes")
    venue_kinds = {
        _operations.InputSemanticKeyKind.VENUE_COMMAND_V2,
        _operations.InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
        _operations.InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
        _operations.InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
        _operations.InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
    }
    if record.key_kind in venue_kinds:
        if (
            record.key_application_generation_id is not None
            or record.key_scope_id is not None
            or record.input_domain is not _operations.OperationDomain.VENUE_RECOVERY
            or coordinates != (record.execution_profile_id,)
        ):
            raise ValueError(
                "venue semantic key coordinates do not match its collision domain"
            )
        return
    application_generation_id = record.key_application_generation_id
    scope_id = record.key_scope_id
    if application_generation_id != record.input_application_generation_id:
        raise ValueError(
            "authority semantic key input application generation does not match "
            "its collision domain"
        )
    if (
        application_generation_id is None
        or scope_id is None
        or record.input_domain is not _operations.OperationDomain.AUTHORITY
        or coordinates
        != (application_generation_id.value, record.execution_profile_id, scope_id)
    ):
        raise ValueError(
            "authority semantic key coordinates do not match its collision domain"
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
    "BrokerOutboxRecord",
    "ClosureChainRecord",
    "CurrentProofRequest",
    "CurrentProofSlice",
    "DecisionReceiptRecord",
    "DurableInputRecord",
    "DurableInputOutcomeRecord",
    "DurableInputSemanticKeyRecord",
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
    "RuntimeCheckpointLoadRequest",
    "RuntimeCheckpointPayloadRecord",
    "RuntimeCheckpointSelectionProof",
    "RuntimeCheckpointSelectionRequest",
    "RuntimeCheckpointWriteReceipt",
    "ScopeRecord",
    "SymbolControllerRecord",
    "VenueEffectRecord",
    "VenueIdentityOwnerRecord",
)
