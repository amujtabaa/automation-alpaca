"""Checkpoint-codec boundary for authenticated current-proof adaptation.

This module owns fixed checkpoint component encodings and the safe bridge from
a repository-issued current proof to the protection hydrator.  It never selects
rows, opens a connection, or serializes arbitrary Python objects.
"""

from __future__ import annotations as _annotations

from dataclasses import dataclass as _dataclass
from hashlib import sha256 as _sha256
import json as _json
from struct import pack as _struct_pack
from threading import RLock as _RLock
from typing import TypeVar as _TypeVar
from typing import Any as _Any
from typing import cast as _cast
from weakref import ReferenceType as _ReferenceType
from weakref import ref as _weakref_ref

from .. import acquisition as _acquisition
from .. import authority as _authority
from .. import durable_codec as _durable_codec
from .. import fills as _fills
from .. import identity as _identity
from .. import position as _position
from .. import protection as _protection
from .. import values as _values
from .. import venue as _venue
from . import operations as _operations
from . import records as _records


_M2_PROTECTION_CHECKPOINT_TAG = "m2.protection.checkpoint/v1"
_M2_EXECUTION_STATE_TAG = "m2.position.execution-state/v1"
_M2_TAIL_FOLD_INPUT_TAG = "m2.position.tail-fold-input/v1"
_M2_RUNTIME_CHECKPOINT_TAG = "m2.runtime-checkpoint/v1"
_M2_RUNTIME_SCOPE_TAG = "m2.runtime-checkpoint.scope/v1"
_M2_RUNTIME_SCOPES_TAG = "m2.runtime-checkpoint.scopes/v1"
_M2_VENUE_STATE_TAG = "m2.venue.State/v1"
_M2_AUTHORITY_CHECKPOINT_TAG = "m2.authority.Checkpoint/v1"
_M2_ACQUISITION_STATE_TAG = "m2.acquisition.State/v1"
_M2_DORMANT_ACQUISITION_TAG = "m2.acquisition.Dormant/v2"
_M2_DORMANT_PROTECTION_TAG = "m2.protection.Dormant/v1"
_M2_POSITION_SCOPE_TAG = "m1.fills.PositionScope/v1"
_MAX_RUNTIME_CHECKPOINT_SCOPES = 4_096
_MAX_CHECKPOINT_COLLECTION_ROWS = 65_535
_MAX_RUNTIME_CHECKPOINT_ROW_BYTES = 2_097_152
_MAX_RUNTIME_CHECKPOINT_COMPONENT_BYTES = 67_108_864
_MAX_RUNTIME_CHECKPOINT_PAYLOAD_BYTES = 268_435_456
_M1ValueT = _TypeVar("_M1ValueT")


@_dataclass(frozen=True, slots=True, weakref_slot=True, init=False)
class InertRuntimeCheckpointComponent:
    """Authenticated canonical bytes with no serving-state authority."""

    tag: str
    canonical_bytes: bytes
    commitment_sha256: str
    _binding: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("InertRuntimeCheckpointComponent is codec-issued only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("InertRuntimeCheckpointComponent cannot be subclassed")

    @classmethod
    def _is_authentic(cls, value: object) -> bool:
        return _component_is_authentic(value)


@_dataclass(frozen=True, slots=True, weakref_slot=True, init=False)
class RuntimeCheckpointScopeCandidate:
    """One inert, scope-local checkpoint candidate in canonical wire order."""

    scope_id: int
    position_scope: InertRuntimeCheckpointComponent
    acquisition: InertRuntimeCheckpointComponent
    execution: InertRuntimeCheckpointComponent
    protection: InertRuntimeCheckpointComponent
    _binding: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("RuntimeCheckpointScopeCandidate is codec-issued only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("RuntimeCheckpointScopeCandidate cannot be subclassed")

    @classmethod
    def _is_authentic(cls, value: object) -> bool:
        return _scope_candidate_is_authentic(value)


@_dataclass(frozen=True, slots=True)
class _RuntimeCheckpointOwnerPreimage:
    selection_proof_binding: bytes
    venue_owner_commitment: bytes
    authority_owner_commitment: bytes
    scope_owner_commitments: tuple[tuple[int, bytes, bytes, bytes], ...]


@_dataclass(frozen=True, slots=True)
class _RuntimeCheckpointScopeOwners:
    """Exact ordered serving owners admitted only as projection inputs."""

    scope_id: int
    acquisition: _acquisition.AcquisitionControllerState | None
    execution: _position.ExecutionSnapshot
    protection: _protection.PositionProtectionState | None


@_dataclass(frozen=True, slots=True, weakref_slot=True, init=False)
class RuntimeCheckpointEnvelope:
    """Canonical, authenticated, explicitly non-serving checkpoint payload."""

    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    market_source_profile_id: str
    currentness_head_ordinal: int
    checkpoint_version_ordinal: int
    venue: InertRuntimeCheckpointComponent
    authority: InertRuntimeCheckpointComponent
    scopes: tuple[RuntimeCheckpointScopeCandidate, ...]
    canonical_payload_bytes: bytes
    payload_sha256: str
    _provenance: str
    _selection_binding: bytes
    _owner_preimage: _RuntimeCheckpointOwnerPreimage | None
    _binding: bytes

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("RuntimeCheckpointEnvelope is codec-issued only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("RuntimeCheckpointEnvelope cannot be subclassed")

    @classmethod
    def _is_authentic(cls, value: object) -> bool:
        return _envelope_is_authentic(value)


_RegistryEntry = tuple[_ReferenceType[object], bytes, str]
_AUTHENTICITY_LOCK = _RLock()
_COMPONENT_REGISTRY: dict[int, _RegistryEntry] = {}
_SCOPE_REGISTRY: dict[int, _RegistryEntry] = {}
_ENVELOPE_REGISTRY: dict[int, _RegistryEntry] = {}


def _register_authentic(
    registry: dict[int, _RegistryEntry], value: object, binding: bytes, provenance: str
) -> None:
    identity = id(value)

    def cleanup(reference: _ReferenceType[object]) -> None:
        with _AUTHENTICITY_LOCK:
            entry = registry.get(identity)
            if entry is not None and entry[0] is reference:
                del registry[identity]

    reference = _weakref_ref(value, cleanup)
    with _AUTHENTICITY_LOCK:
        registry[identity] = (reference, binding, provenance)


def _registry_matches(
    registry: dict[int, _RegistryEntry],
    value: object,
    binding: bytes,
    provenance: str,
) -> bool:
    with _AUTHENTICITY_LOCK:
        entry = registry.get(id(value))
        return (
            entry is not None
            and entry[0]() is value
            and entry[1] == binding
            and entry[2] == provenance
        )


def _pack_parts(domain: bytes, *parts: bytes) -> bytes:
    if type(domain) is not bytes or not domain:
        raise TypeError("binding domain must be nonempty exact bytes")
    if any(type(part) is not bytes for part in parts):
        raise TypeError("binding parts must be exact bytes")
    return (
        _struct_pack(">I", len(domain))
        + domain
        + b"".join(_struct_pack(">Q", len(part)) + part for part in parts)
    )


def _commit_runtime_parts(domain: bytes, *parts: bytes) -> bytes:
    return _sha256(_pack_parts(domain, *parts)).digest()


def _binding_int(value: int) -> bytes:
    if type(value) is not int:
        raise TypeError("binding integer must be exact int")
    magnitude_value = abs(value)
    magnitude = magnitude_value.to_bytes(
        max(1, (magnitude_value.bit_length() + 7) // 8), "big"
    )
    return (
        bytes((0 if value >= 0 else 1,))
        + _struct_pack(">I", len(magnitude))
        + magnitude
    )


def _binding_text(value: str) -> bytes:
    if type(value) is not str:
        raise TypeError("binding text must be exact str")
    encoded = value.encode("utf-8")
    return _struct_pack(">Q", len(encoded)) + encoded


def _binding_bytes(value: bytes) -> bytes:
    if type(value) is not bytes:
        raise TypeError("binding bytes must be exact bytes")
    return _struct_pack(">Q", len(value)) + value


def _field_none() -> bytes:
    return _commit_runtime_parts(b"execution-core/runtime-checkpoint/field/absent/v1")


def _field_int(value: int) -> bytes:
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/field/int/v1", _binding_int(value)
    )


def _field_text(value: str) -> bytes:
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/field/text/v1", _binding_text(value)
    )


def _field_bytes(value: bytes) -> bytes:
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/field/bytes/v1", _binding_bytes(value)
    )


def _atom_binding(atom: _durable_codec.DurableAtom) -> bytes:
    if type(atom) is not _durable_codec.DurableAtom:
        raise TypeError("durable atom must be exact DurableAtom")
    fields: list[bytes] = []
    for field in atom.fields:
        if type(field) is str:
            fields.append(
                _commit_runtime_parts(
                    b"execution-core/runtime-checkpoint/atom-text/v1",
                    _binding_text(field),
                )
            )
        elif type(field) is _durable_codec.DurableAtom:
            fields.append(_atom_binding(field))
        else:
            raise TypeError("durable atom field is not admitted")
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/durable-atom/v1",
        _binding_text(atom.contract_version),
        _binding_text(atom.type_tag),
        _binding_int(len(fields)),
        *fields,
    )


def _field_m1(value: object) -> bytes:
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/field/m1-value/v1",
        _atom_binding(
            _durable_codec.encode_m1_value(_cast(_durable_codec._OwningValue, value))
        ),
    )


def _sequence_domain(domain: bytes, items: tuple[bytes, ...]) -> bytes:
    return _commit_runtime_parts(domain, _binding_int(len(items)), *items)


def _require_sha256_text(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or value.lower() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{name} must be lowercase SHA-256 text")
    return value


def _require_nonnegative_int(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be exact int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _component_binding(value: InertRuntimeCheckpointComponent) -> bytes:
    if type(value) is not InertRuntimeCheckpointComponent:
        raise TypeError("component must be exact InertRuntimeCheckpointComponent")
    _require_sha256_text("component commitment", value.commitment_sha256)
    if _sha256(value.canonical_bytes).hexdigest() != value.commitment_sha256:
        raise ValueError("component digest does not match canonical bytes")
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/component/v1",
        _field_text(value.tag),
        _field_bytes(value.canonical_bytes),
        _field_text(value.commitment_sha256),
    )


def _component_is_authentic(value: object) -> bool:
    if type(value) is not InertRuntimeCheckpointComponent:
        return False
    try:
        binding = _component_binding(value)
        return value._binding == binding and _registry_matches(
            _COMPONENT_REGISTRY, value, binding, "COMPONENT"
        )
    except (AttributeError, OverflowError, TypeError, ValueError):
        return False


def _issue_component(
    tag: str, canonical_bytes: bytes
) -> InertRuntimeCheckpointComponent:
    if type(tag) is not str or type(canonical_bytes) is not bytes:
        raise TypeError("component tag and bytes must be exact")
    if len(canonical_bytes) > _MAX_RUNTIME_CHECKPOINT_COMPONENT_BYTES:
        raise OverflowError("checkpoint component exceeds its byte limit")
    parsed = _decode_canonical_json(canonical_bytes)
    if type(parsed) is not list or not parsed or parsed[0] != tag:
        raise ValueError("component bytes do not carry their exact tag")
    result = object.__new__(InertRuntimeCheckpointComponent)
    digest = _sha256(canonical_bytes).hexdigest()
    object.__setattr__(result, "tag", tag)
    object.__setattr__(result, "canonical_bytes", canonical_bytes)
    object.__setattr__(result, "commitment_sha256", digest)
    binding = _component_binding(result)
    object.__setattr__(result, "_binding", binding)
    _register_authentic(_COMPONENT_REGISTRY, result, binding, "COMPONENT")
    return result


def _scope_binding(value: RuntimeCheckpointScopeCandidate) -> bytes:
    if type(value) is not RuntimeCheckpointScopeCandidate:
        raise TypeError("scope candidate must be exact RuntimeCheckpointScopeCandidate")
    _require_nonnegative_int("scope ID", value.scope_id)
    components = (
        value.position_scope,
        value.acquisition,
        value.execution,
        value.protection,
    )
    if not all(_component_is_authentic(component) for component in components):
        raise ValueError("scope candidate contains an inauthentic component")
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/scope-candidate/v1",
        _field_int(value.scope_id),
        *(_component_binding(component) for component in components),
    )


def _scope_candidate_is_authentic(value: object) -> bool:
    if type(value) is not RuntimeCheckpointScopeCandidate:
        return False
    try:
        binding = _scope_binding(value)
        return value._binding == binding and _registry_matches(
            _SCOPE_REGISTRY, value, binding, "SCOPE"
        )
    except (AttributeError, OverflowError, TypeError, ValueError):
        return False


def _issue_scope_candidate(
    scope_id: int,
    position_scope: InertRuntimeCheckpointComponent,
    acquisition: InertRuntimeCheckpointComponent,
    execution: InertRuntimeCheckpointComponent,
    protection: InertRuntimeCheckpointComponent,
) -> RuntimeCheckpointScopeCandidate:
    result = object.__new__(RuntimeCheckpointScopeCandidate)
    for name, value in (
        ("scope_id", scope_id),
        ("position_scope", position_scope),
        ("acquisition", acquisition),
        ("execution", execution),
        ("protection", protection),
    ):
        object.__setattr__(result, name, value)
    binding = _scope_binding(result)
    object.__setattr__(result, "_binding", binding)
    _register_authentic(_SCOPE_REGISTRY, result, binding, "SCOPE")
    return result


def _owner_row_binding(row: tuple[int, bytes, bytes, bytes]) -> bytes:
    if type(row) is not tuple or len(row) != 4:
        raise TypeError("scope owner row must be an exact four-member tuple")
    scope_id, acquisition, execution, protection = row
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/scope-owner-row/v1",
        _field_int(_require_nonnegative_int("owner scope ID", scope_id)),
        _field_bytes(acquisition),
        _field_bytes(execution),
        _field_bytes(protection),
    )


def _owner_preimage_binding(value: _RuntimeCheckpointOwnerPreimage) -> bytes:
    if type(value) is not _RuntimeCheckpointOwnerPreimage:
        raise TypeError("owner preimage must be exact _RuntimeCheckpointOwnerPreimage")
    for name in (
        "selection_proof_binding",
        "venue_owner_commitment",
        "authority_owner_commitment",
    ):
        member = getattr(value, name)
        if type(member) is not bytes or len(member) != 32:
            raise ValueError(f"{name} must be exact 32-byte commitment")
    rows = value.scope_owner_commitments
    if type(rows) is not tuple or len(rows) > _MAX_RUNTIME_CHECKPOINT_SCOPES:
        raise ValueError("owner rows must be a bounded exact tuple")
    ids = tuple(row[0] for row in rows)
    if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
        raise ValueError("owner rows must be strictly scope-ID ordered")
    row_bindings = tuple(_owner_row_binding(row) for row in rows)
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/owner-preimage/v1",
        _field_bytes(value.selection_proof_binding),
        _field_bytes(value.venue_owner_commitment),
        _field_bytes(value.authority_owner_commitment),
        _sequence_domain(
            b"execution-core/runtime-checkpoint/scope-owner-rows/v1", row_bindings
        ),
    )


def _canonical_payload_from_envelope(value: RuntimeCheckpointEnvelope) -> bytes:
    scopes: list[object] = []
    for scope in value.scopes:
        scopes.append(
            [
                _M2_RUNTIME_SCOPE_TAG,
                scope.scope_id,
                _decode_canonical_json(scope.position_scope.canonical_bytes),
                _decode_canonical_json(scope.acquisition.canonical_bytes),
                _decode_canonical_json(scope.execution.canonical_bytes),
                _decode_canonical_json(scope.protection.canonical_bytes),
            ]
        )
    payload: list[object] = [
        1,
        _M2_RUNTIME_CHECKPOINT_TAG,
        _operations._encode_m2_m1_atom(value.application_generation_id),
        value.execution_profile_id,
        value.market_source_profile_id,
        value.currentness_head_ordinal,
        value.checkpoint_version_ordinal,
        _decode_canonical_json(value.venue.canonical_bytes),
        _decode_canonical_json(value.authority.canonical_bytes),
        [_M2_RUNTIME_SCOPES_TAG, len(scopes), scopes],
    ]
    return _encode_canonical_json(payload)


def _envelope_public_binding(value: RuntimeCheckpointEnvelope) -> bytes:
    if type(value) is not RuntimeCheckpointEnvelope:
        raise TypeError("envelope must be exact RuntimeCheckpointEnvelope")
    if type(value.application_generation_id) is not _identity.ApplicationGenerationId:
        raise TypeError("application generation must be exact ApplicationGenerationId")
    _require_sha256_text("execution profile ID", value.execution_profile_id)
    _require_sha256_text("market source profile ID", value.market_source_profile_id)
    _require_nonnegative_int("currentness head ordinal", value.currentness_head_ordinal)
    _require_nonnegative_int(
        "checkpoint version ordinal", value.checkpoint_version_ordinal
    )
    if (
        type(value.scopes) is not tuple
        or len(value.scopes) > _MAX_RUNTIME_CHECKPOINT_SCOPES
    ):
        raise ValueError("checkpoint scopes must be a bounded exact tuple")
    ids = tuple(scope.scope_id for scope in value.scopes)
    if ids != tuple(sorted(ids)) or len(ids) != len(set(ids)):
        raise ValueError("checkpoint scopes must be strictly scope-ID ordered")
    if not _component_is_authentic(value.venue) or not _component_is_authentic(
        value.authority
    ):
        raise ValueError("checkpoint top component is not authentic")
    if not all(_scope_candidate_is_authentic(scope) for scope in value.scopes):
        raise ValueError("checkpoint scope is not authentic")
    expected_payload = _canonical_payload_from_envelope(value)
    if expected_payload != value.canonical_payload_bytes:
        raise ValueError("checkpoint public fields do not reproduce payload bytes")
    if len(expected_payload) > _MAX_RUNTIME_CHECKPOINT_PAYLOAD_BYTES:
        raise OverflowError("checkpoint payload exceeds its byte limit")
    _require_sha256_text("payload digest", value.payload_sha256)
    if _sha256(expected_payload).hexdigest() != value.payload_sha256:
        raise ValueError("checkpoint payload digest does not match bytes")
    scope_bindings = tuple(_scope_binding(scope) for scope in value.scopes)
    return _commit_runtime_parts(
        b"execution-core/runtime-checkpoint/envelope-public/v1",
        _field_m1(value.application_generation_id),
        _field_text(value.execution_profile_id),
        _field_text(value.market_source_profile_id),
        _field_int(value.currentness_head_ordinal),
        _field_int(value.checkpoint_version_ordinal),
        _component_binding(value.venue),
        _component_binding(value.authority),
        _sequence_domain(
            b"execution-core/runtime-checkpoint/scope-candidates/v1", scope_bindings
        ),
        _field_bytes(value.canonical_payload_bytes),
        _field_text(value.payload_sha256),
    )


def _envelope_binding(value: RuntimeCheckpointEnvelope) -> bytes:
    public = _envelope_public_binding(value)
    if (
        type(value._selection_binding) is not bytes
        or len(value._selection_binding) != 32
    ):
        raise ValueError("selection/load binding must be exact 32 bytes")
    if type(value._provenance) is not str:
        raise TypeError("envelope provenance must be exact str")
    if value._provenance == "PROJECTED":
        if type(value._owner_preimage) is not _RuntimeCheckpointOwnerPreimage:
            raise ValueError("projected envelope requires an owner preimage")
        if value._selection_binding != value._owner_preimage.selection_proof_binding:
            raise ValueError("projected envelope selection binding does not agree")
        if tuple(
            row[0] for row in value._owner_preimage.scope_owner_commitments
        ) != tuple(scope.scope_id for scope in value.scopes):
            raise ValueError("projected owner scope coordinates do not agree")
        return _commit_runtime_parts(
            b"execution-core/runtime-checkpoint/projected-envelope/v1",
            public,
            _field_text(value._provenance),
            _field_bytes(value._selection_binding),
            _owner_preimage_binding(value._owner_preimage),
        )
    if value._provenance == "LOADED":
        if value._owner_preimage is not None:
            raise ValueError("loaded envelope cannot retain owner preimage")
        return _commit_runtime_parts(
            b"execution-core/runtime-checkpoint/loaded-envelope/v1",
            public,
            _field_text(value._provenance),
            _field_bytes(value._selection_binding),
            _field_none(),
        )
    raise ValueError("envelope provenance is not admitted")


def _envelope_is_authentic(value: object) -> bool:
    if type(value) is not RuntimeCheckpointEnvelope:
        return False
    try:
        binding = _envelope_binding(value)
        return value._binding == binding and _registry_matches(
            _ENVELOPE_REGISTRY, value, binding, value._provenance
        )
    except (AttributeError, OverflowError, TypeError, ValueError):
        return False


def _issue_envelope(
    *,
    application_generation_id: _identity.ApplicationGenerationId,
    execution_profile_id: str,
    market_source_profile_id: str,
    currentness_head_ordinal: int,
    checkpoint_version_ordinal: int,
    venue: InertRuntimeCheckpointComponent,
    authority: InertRuntimeCheckpointComponent,
    scopes: tuple[RuntimeCheckpointScopeCandidate, ...],
    canonical_payload_bytes: bytes,
    provenance: str,
    selection_binding: bytes,
    owner_preimage: _RuntimeCheckpointOwnerPreimage | None,
) -> RuntimeCheckpointEnvelope:
    result = object.__new__(RuntimeCheckpointEnvelope)
    for name, value in (
        ("application_generation_id", application_generation_id),
        ("execution_profile_id", execution_profile_id),
        ("market_source_profile_id", market_source_profile_id),
        ("currentness_head_ordinal", currentness_head_ordinal),
        ("checkpoint_version_ordinal", checkpoint_version_ordinal),
        ("venue", venue),
        ("authority", authority),
        ("scopes", scopes),
        ("canonical_payload_bytes", canonical_payload_bytes),
        ("payload_sha256", _sha256(canonical_payload_bytes).hexdigest()),
        ("_provenance", provenance),
        ("_selection_binding", selection_binding),
        ("_owner_preimage", owner_preimage),
    ):
        object.__setattr__(result, name, value)
    binding = _envelope_binding(result)
    object.__setattr__(result, "_binding", binding)
    _register_authentic(_ENVELOPE_REGISTRY, result, binding, provenance)
    return result


def _encode_canonical_json(value: list[object]) -> bytes:
    try:
        encoded = _json.dumps(
            value, ensure_ascii=True, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("checkpoint payload is not canonical JSON") from error
    return encoded


def _decode_canonical_json(value: bytes) -> object:
    if type(value) is not bytes:
        raise TypeError("canonical JSON must be exact bytes")
    try:
        decoded = _json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, _json.JSONDecodeError) as error:
        raise ValueError("checkpoint bytes are not canonical JSON") from error
    if _encode_canonical_json(decoded) != value:
        raise ValueError("checkpoint JSON bytes are not canonical")
    return decoded


_COMPONENT_MEMBER_COUNTS = {
    _M2_VENUE_STATE_TAG: 23,
    _M2_AUTHORITY_CHECKPOINT_TAG: 14,
    _M2_ACQUISITION_STATE_TAG: 17,
    _M2_DORMANT_ACQUISITION_TAG: 17,
    _M2_EXECUTION_STATE_TAG: 21,
    _M2_PROTECTION_CHECKPOINT_TAG: 32,
    _M2_DORMANT_PROTECTION_TAG: 7,
    _M2_POSITION_SCOPE_TAG: 5,
}

_CHECKPOINT_COLLECTION_TAGS = {
    "m2.venue.AuthorityEpochs/v1",
    "m2.venue.Effects/v1",
    "m2.venue.Claims/v1",
    "m2.venue.OwnerAttempts/v1",
    "m2.venue.AcquisitionCorrelations/v1",
    "m2.venue.ClosureHeads/v1",
    "m2.venue.EconomicHighWaters/v1",
    "m2.venue.HumanCoverages/v1",
    "m2.venue.BrokerCoverages/v1",
    "m2.venue.CoverageProvenances/v1",
    "m2.venue.Reconciliations/v1",
    "m2.venue.ExecutionReconciliations/v1",
    "m2.venue.ExecutionScopes/v1",
    "m2.venue.BootstrapTargets/v1",
    "m2.venue.ProtectionCursors/v1",
    "m2.venue.Contradictions/v1",
    "m2.venue.CoveredRoots/v1",
    "m2.venue.StandDownEffects/v1",
    "m2.venue.CancellableBuyLegs/v1",
    "m2.venue.CancelPendingBuyLegs/v1",
    "m2.authority.EffectAuthorizations/v1",
    "m2.authority.ManualFlattens/v1",
    "m2.authority.CancelEffects/v1",
    "m2.authority.AcquisitionDescriptors/v1",
    "m2.authority.AcquisitionSlots/v1",
    "m2.acquisition.UnresolvedGenerations/v1",
    "m2.acquisition.UnresolvedMarketStreamRoutes/v1",
    "m2.acquisition.LineageRoutes/v1",
    "m2.acquisition.DormantGenerations/v1",
    "m2.acquisition.DormantGenerationCurrents/v1",
    "m2.acquisition.DormantMarketStreams/v1",
    "m2.acquisition.DormantMarketCursors/v1",
    "m2.acquisition.DormantLineageRoutes/v1",
}

_CHECKPOINT_FIXED_ROW_LENGTHS = {
    "m2.venue.Scope/v1": 5,
    "m2.venue.AuthorityEpoch/v1": 3,
    "m2.venue.EffectCurrent/v1": 10,
    "m2.venue.EffectScope/v1": 15,
    "m2.venue.AcceptanceProof/v1": 6,
    "m2.venue.AcceptanceContradiction/v1": 4,
    "m2.venue.DispatchClaim/v1": 3,
    "m2.venue.OwnerAttempt/v1": 6,
    "m2.venue.Attempt/v1": 6,
    "m2.venue.AcquisitionCorrelation/v1": 7,
    "m2.venue.TerminalClosure/v1": 17,
    "m2.venue.EconomicHighWater/v1": 3,
    "m2.venue.HumanCoverage/v1": 9,
    "m2.venue.BrokerCoverage/v1": 12,
    "m2.venue.CoverageProvenance/v1": 4,
    "m2.venue.CoveredRoot/v1": 3,
    "m2.venue.FillReconciliation/v1": 9,
    "m2.venue.RevisionReconciliation/v1": 11,
    "m2.venue.ExecutionScopeCurrent/v1": 3,
    "m2.venue.ExecutionCheckpoint/v1": 10,
    "m2.venue.ExecutionBinding/v1": 5,
    "m2.venue.ResolvedRegistryProjection/v1": 9,
    "m2.venue.UnresolvedRegistryAdvance/v1": 11,
    "m2.venue.ProtectionCursor/v1": 7,
    "m2.venue.BootstrapTargetActive/v1": 25,
    "m2.venue.BootstrapTargetConsumed/v1": 6,
    "m2.venue.ProtectionTransitionProof/v1": 25,
    "m2.venue.ProtectionTransitionCursor/v1": 6,
    "m2.venue.SymbolAuthoritySummary/v1": 10,
    "m2.authority.RequestBudget/v1": 3,
    "m2.authority.VenueRef/v1": 6,
    "m2.authority.EffectAuthorization/v1": 6,
    "m2.authority.ClaimEffect/v1": 4,
    "m2.authority.ClaimAcquisitionEffect/v1": 5,
    "m2.authority.AcquisitionClaimPermit/v1": 22,
    "m2.authority.ManualFlatten/v1": 5,
    "m1.authority.BeginManualFlatten/v1": 9,
    "m2.authority.EmergencyGrant/v1": 8,
    "m2.authority.AcquisitionDescriptor/v1": 3,
    "m2.authority.AcquisitionSlot/v1": 4,
    "m2.authority.AcquisitionSlotEmpty/v1": 1,
    "m2.authority.AcquisitionSlotActive/v1": 3,
    "m2.authority.AcquisitionSlotInactive/v1": 4,
    "m2.authority.AcquisitionCurrentness/v1": 16,
    "m2.authority.AcquisitionEffectPermit/v1": 22,
    "m2.acquisition.Controller/v1": 14,
    "m2.acquisition.Generation/v1": 12,
    "m2.acquisition.MarketStreamRoute/v1": 4,
    "m2.acquisition.LineageRoute/v1": 6,
    "m2.acquisition.LineageEffectSource/v1": 2,
    "m2.acquisition.LineageOwnerSource/v1": 3,
    "m2.acquisition.LineageRootSource/v1": 2,
    "m2.acquisition.LineageFactSource/v1": 2,
    "m2.acquisition.BoundedRegistry/v1": 5,
    "m2.acquisition.BoundedLineage/v1": 2,
    "m2.acquisition.DormantGeneration/v1": 8,
    "m2.acquisition.DormantGenerationCurrent/v1": 6,
    "m2.acquisition.DormantMarketStream/v1": 9,
    "m2.acquisition.DormantMarketCursor/v1": 11,
    "m2.acquisition.DormantLineageRoute/v1": 7,
    "m2.acquisition.DormantRootSourceBinding/v1": 3,
    "m2.acquisition.DormantRegistry/v2": 5,
    "m2.scalar.Fraction/v1": 3,
    "m2.position.PositionIntegrity": 2,
    _M2_TAIL_FOLD_INPUT_TAG: 7,
}

_CHECKPOINT_ENUM_OWNERS = {
    "m1.authority.EnginePhase",
    "m1.authority.TradingMode",
    "m1.authority.SupervisorFence",
    "m1.authority.FlattenPhase",
    "m1.authority.AcquisitionCurrentnessSourceKind",
    "m1.acquisition.AcquisitionRecoveryClass",
    "m1.acquisition.GenerationRouteKind",
    "m1.acquisition.GenerationServingClass",
    "m1.venue.EffectKind",
    "m1.venue.BrokerEffectState",
    "m1.venue.AcceptanceSetState",
    "m1.venue.AcceptanceProofKind",
    "m1.venue.VenueAttemptState",
    "m1.venue.PendingVenueOperation",
    "m1.venue.VenueClosureKind",
    "m1.venue.VenueRecoveryDisposition",
    "m1.venue.ProtectionTransitionSourceKind",
    "m1.venue.BootstrapSourceKind",
    "m1.venue.ResolvedProjectionKind",
    "m2.protection.AuthorityClass",
    "m2.protection.ProtectionPolicy",
    "m2.position.BasisAuthority",
    "m1.fills.ExecutionSide",
    "m1.fills.FirstObservationClassification",
    "m1.fills.FactKind",
    "m1.fills.ExecutionAuthority",
    "m1.protection.MarketSequenceMode",
}


def _validate_checkpoint_collection(value: object, expected_tag: str) -> None:
    if (
        type(value) is not list
        or len(value) != 3
        or value[0] != expected_tag
        or type(value[1]) is not int
        or value[1] < 0
        or type(value[2]) is not list
        or value[1] != len(value[2])
    ):
        raise ValueError(f"{expected_tag} has the wrong exact shape")
    if len(value[2]) > _MAX_CHECKPOINT_COLLECTION_ROWS:
        raise OverflowError(f"{expected_tag} exceeds its row limit")
    for row in value[2]:
        _validate_checkpoint_nested_value(row)


def _validate_checkpoint_nested_value(value: object) -> None:
    """Reject unknown nested tags, lengths, scalar aliases, and collection counts."""

    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is not list or not value or type(value[0]) is not str:
        raise ValueError("checkpoint nested value has no admitted tagged shape")
    tag = value[0]
    if tag == "1":
        if (
            len(value) != 3
            or type(value[1]) is not str
            or type(value[2]) is not list
            or any(type(field) is not str for field in value[2])
        ):
            raise ValueError("checkpoint durable atom has the wrong exact shape")
        return
    if tag in _CHECKPOINT_ENUM_OWNERS:
        if len(value) != 2 or type(value[1]) is not str:
            raise ValueError(f"{tag} enum has the wrong exact shape")
        return
    if tag in _CHECKPOINT_COLLECTION_TAGS:
        _validate_checkpoint_collection(value, tag)
        return
    expected_length = _CHECKPOINT_FIXED_ROW_LENGTHS.get(tag)
    if expected_length is None or len(value) != expected_length:
        raise ValueError(f"{tag} is not an admitted exact nested row")
    for member in value[1:]:
        _validate_checkpoint_nested_value(member)


def _validate_runtime_checkpoint_venue_wire(value: list[object]) -> None:
    scope = value[1]
    if type(scope) is not list or len(scope) != 5 or scope[0] != "m2.venue.Scope/v1":
        raise ValueError("venue scope has the wrong exact shape")
    for name, member, expected_type in (
        ("venue generation", scope[1], _identity.ApplicationGenerationId),
        ("venue broker", scope[2], _identity.BrokerId),
        ("venue environment", scope[3], _identity.EnvironmentId),
        ("venue account", scope[4], _identity.AccountId),
    ):
        _operations._decode_m2_m1_as(name, member, expected_type)
    for index in (2, 3):
        _require_nonnegative_int("venue ordinal/count", value[index])
    if (value[4] is None) != (value[5] is None):
        raise ValueError("venue registry count and commitment are partial")
    if value[4] is not None:
        _require_nonnegative_int("venue registry count", value[4])
        _require_sha256_text("venue registry commitment", value[5])
    if value[6] is not None:
        _require_sha256_text("venue transition head", value[6])
    tags = (
        "m2.venue.AuthorityEpochs/v1",
        "m2.venue.Effects/v1",
        "m2.venue.Claims/v1",
        "m2.venue.OwnerAttempts/v1",
        "m2.venue.AcquisitionCorrelations/v1",
        "m2.venue.ClosureHeads/v1",
        "m2.venue.EconomicHighWaters/v1",
        "m2.venue.HumanCoverages/v1",
        "m2.venue.BrokerCoverages/v1",
        "m2.venue.CoverageProvenances/v1",
        "m2.venue.Reconciliations/v1",
        "m2.venue.ExecutionReconciliations/v1",
        "m2.venue.ExecutionScopes/v1",
        "m2.venue.BootstrapTargets/v1",
        "m2.venue.ProtectionCursors/v1",
    )
    for member, tag in zip(value[7:22], tags, strict=True):
        _validate_checkpoint_collection(member, tag)
    retained = _require_sha256_text("venue checkpoint commitment", value[22])
    expected = _checkpoint_row_commitment(
        b"execution-core/m2-venue/state/v1", value[:22]
    ).hex()
    if retained != expected:
        raise ValueError("venue checkpoint commitment does not match its row")


def _validate_runtime_checkpoint_authority_wire(value: list[object]) -> None:
    for member, owner in zip(
        value[1:4],
        (
            "m1.authority.EnginePhase",
            "m1.authority.TradingMode",
            "m1.authority.SupervisorFence",
        ),
        strict=True,
    ):
        if type(member) is not list or member[0] != owner:
            raise ValueError("authority enum owner tag is not admitted")
        _validate_checkpoint_nested_value(member)
    for member, enum_type in zip(
        value[1:4],
        (_authority.EnginePhase, _authority.TradingMode, _authority.SupervisorFence),
        strict=True,
    ):
        enum_type(_cast(list[object], member)[1])
    if type(value[4]) is not bool:
        raise TypeError("authority kill flag must be exact bool")
    if value[5] is not None:
        _validate_checkpoint_nested_value(value[5])
    budget = value[6]
    if (
        type(budget) is not list
        or len(budget) != 3
        or budget[0] != "m2.authority.RequestBudget/v1"
    ):
        raise ValueError("authority request budget has the wrong exact shape")
    _require_nonnegative_int("authority remaining budget", budget[1])
    _require_nonnegative_int("authority safety reserve", budget[2])
    venue_ref = value[7]
    if (
        type(venue_ref) is not list
        or len(venue_ref) != 6
        or venue_ref[0] != "m2.authority.VenueRef/v1"
    ):
        raise ValueError("authority venue reference has the wrong exact shape")
    for name, member, expected_type in (
        ("authority venue generation", venue_ref[1], _identity.ApplicationGenerationId),
        ("authority venue broker", venue_ref[2], _identity.BrokerId),
        ("authority venue environment", venue_ref[3], _identity.EnvironmentId),
        ("authority venue account", venue_ref[4], _identity.AccountId),
    ):
        _operations._decode_m2_m1_as(name, member, expected_type)
    _require_sha256_text("authority venue commitment", venue_ref[5])
    if value[8] is not None:
        _validate_checkpoint_nested_value(value[8])
    for member, tag in zip(
        value[9:13],
        (
            "m2.authority.EffectAuthorizations/v1",
            "m2.authority.ManualFlattens/v1",
            "m2.authority.AcquisitionDescriptors/v1",
            "m2.authority.AcquisitionSlots/v1",
        ),
        strict=True,
    ):
        _validate_checkpoint_collection(member, tag)
    retained = _require_sha256_text("authority checkpoint commitment", value[13])
    expected = _checkpoint_row_commitment(
        b"execution-core/m2-authority/state/v1", value[:13]
    ).hex()
    if retained != expected:
        raise ValueError("authority checkpoint commitment does not match its row")


def _validate_runtime_checkpoint_acquisition_wire(value: list[object]) -> None:
    if value and value[0] == _M2_DORMANT_ACQUISITION_TAG:
        _validate_runtime_checkpoint_dormant_acquisition_wire(value)
        return
    _validate_checkpoint_nested_value(value[1])
    _operations._decode_m2_position_scope(value[2])
    for index in (3, 4, 5):
        _require_sha256_text("acquisition commitment", value[index])
    if value[6] is not None:
        _require_sha256_text("acquisition protection commitment", value[6])
    for member in value[7:14]:
        _validate_checkpoint_nested_value(member)
    registry = _require_sha256_text("acquisition registry commitment", value[14])
    lineage = _require_sha256_text("acquisition lineage commitment", value[15])
    expected_registry = _checkpoint_row_commitment(
        b"execution-core/m2-acquisition/bounded-registry/v1",
        ["m2.acquisition.BoundedRegistry/v1", *value[9:13]],
    ).hex()
    expected_lineage = _checkpoint_row_commitment(
        b"execution-core/m2-acquisition/bounded-lineage/v1",
        ["m2.acquisition.BoundedLineage/v1", value[13]],
    ).hex()
    if registry != expected_registry or lineage != expected_lineage:
        raise ValueError("acquisition bounded commitment does not match its rows")
    retained = _require_sha256_text("acquisition checkpoint commitment", value[16])
    expected = _checkpoint_row_commitment(
        b"execution-core/m2-acquisition/state/v1", value[:16]
    ).hex()
    if retained != expected:
        raise ValueError("acquisition checkpoint commitment does not match its row")


def _validate_runtime_checkpoint_dormant_acquisition_wire(
    value: list[object],
) -> None:
    """Validate the exact R18/R19 database-derived dormant acquisition row."""

    _operations._decode_m2_m1_as(
        "dormant acquisition application generation",
        value[1],
        _identity.ApplicationGenerationId,
    )
    _operations._decode_m2_position_scope(value[2])
    for index in (3, 4, 6, 7):
        _require_nonnegative_int("dormant acquisition integer", value[index])
    if type(value[5]) is not str:
        raise TypeError("dormant acquisition integrity state must be exact text")
    _require_sha256_text("dormant acquisition compatibility", value[8])
    wrapper_tags = (
        "m2.acquisition.DormantGenerations/v1",
        "m2.acquisition.DormantGenerationCurrents/v1",
        "m2.acquisition.DormantMarketStreams/v1",
        "m2.acquisition.DormantMarketCursors/v1",
        "m2.acquisition.DormantLineageRoutes/v1",
    )
    for member, tag in zip(value[9:14], wrapper_tags, strict=True):
        _validate_checkpoint_collection(member, tag)
    registry = _require_sha256_text(
        "dormant acquisition registry commitment", value[14]
    )
    lineage = _require_sha256_text("dormant acquisition lineage commitment", value[15])
    registry_row = ["m2.acquisition.DormantRegistry/v2", *value[9:13]]
    if (
        registry
        != _checkpoint_row_commitment(
            b"execution-core/m2-acquisition/dormant-registry/v2", registry_row
        ).hex()
    ):
        raise ValueError("dormant acquisition registry commitment does not match")
    if (
        lineage
        != _checkpoint_row_commitment(
            b"execution-core/m2-acquisition/dormant-lineage/v2",
            _cast(list[object], value[13]),
        ).hex()
    ):
        raise ValueError("dormant acquisition lineage commitment does not match")
    retained = _require_sha256_text("dormant acquisition commitment", value[16])
    if (
        retained
        != _checkpoint_row_commitment(
            b"execution-core/m2-acquisition/dormant/v2", value[:16]
        ).hex()
    ):
        raise ValueError("dormant acquisition commitment does not match its row")


def _validate_runtime_checkpoint_execution_wire(value: list[object]) -> None:
    _operations._decode_m2_position_scope(value[1])
    if type(value[2]) is not int:
        raise TypeError("execution quantity must be exact int")
    if type(value[3]) is not list or value[3][0] != "m2.position.BasisAuthority":
        raise ValueError("execution basis authority tag is not admitted")
    _validate_checkpoint_nested_value(value[3])
    for member in value[4:7]:
        if member is not None:
            _validate_checkpoint_nested_value(member)
    for index in (7, 8):
        if type(value[index]) is not list:
            raise ValueError("execution integrity row is not admitted")
        _validate_checkpoint_nested_value(value[index])
    if type(value[9]) is not bool:
        raise TypeError("execution reconciliation flag must be exact bool")
    for index in (10, 12):
        _require_nonnegative_int("execution count", value[index])
    for index in (11, 13, 14, 15, 16, 17, 18, 19, 20):
        _require_sha256_text("execution commitment", value[index])


def _validate_runtime_checkpoint_protection_wire(value: list[object]) -> None:
    if value and value[0] == _M2_DORMANT_PROTECTION_TAG:
        _validate_runtime_checkpoint_dormant_protection_wire(value)
        return
    if type(value[1]) is not list or value[1][0] != "m2.protection.ProtectionPolicy":
        raise ValueError("protection policy tag is not admitted")
    _validate_checkpoint_nested_value(value[1])
    _validate_checkpoint_nested_value(value[2])
    if type(value[3]) is not int:
        raise TypeError("protection quantity must be exact int")
    _require_sha256_text("protection execution commitment", value[4])
    if type(value[5]) is not bool or type(value[10]) is not bool:
        raise TypeError("protection flags must be exact bool")
    for member in value[6:10]:
        if member is not None:
            _validate_checkpoint_nested_value(member)
    _require_sha256_text("protection state commitment", value[11])
    _require_nonnegative_int("protection cursor ordinal", value[12])
    _require_sha256_text("protection cursor head", value[13])
    for index in range(14, 20):
        if value[index] is not None:
            _require_nonnegative_int("protection market coordinate", value[index])
    if value[20] is not None:
        _validate_checkpoint_nested_value(value[20])
    for index in (21, 22, 23):
        if type(value[index]) is not bool:
            raise TypeError("protection market flag must be exact bool")
    for index in (24, 25, 27, 29):
        if value[index] is not None:
            _validate_checkpoint_nested_value(value[index])
    for index in (26, 28, 30):
        if value[index] is not None:
            _require_nonnegative_int("protection source time", value[index])
    _require_sha256_text("protection exit provenance", value[31])


def _validate_runtime_checkpoint_dormant_protection_wire(
    value: list[object],
) -> None:
    """Validate one exact database-derived dormant protection row."""

    for index in (1, 3, 5):
        _require_nonnegative_int("dormant protection integer", value[index])
    if type(value[2]) is not str:
        raise TypeError("dormant protection authority class must be exact text")
    _require_sha256_text("dormant protection state commitment", value[4])
    retained = _require_sha256_text("dormant protection commitment", value[6])
    if (
        retained
        != _checkpoint_row_commitment(
            b"execution-core/m2-protection/dormant/v1", value[:6]
        ).hex()
    ):
        raise ValueError("dormant protection commitment does not match its row")


def _decode_component(
    value: object, expected_tag: str | tuple[str, ...]
) -> InertRuntimeCheckpointComponent:
    admitted_tags = (expected_tag,) if type(expected_tag) is str else expected_tag
    if type(value) is not list or not value or value[0] not in admitted_tags:
        label = "/".join(admitted_tags)
        raise ValueError(f"{label} has the wrong exact shape")
    actual_tag = _cast(str, value[0])
    expected_count = _COMPONENT_MEMBER_COUNTS[actual_tag]
    if len(value) != expected_count or type(value[0]) is not str:
        raise ValueError(f"{actual_tag} has the wrong exact shape")
    if actual_tag == _M2_POSITION_SCOPE_TAG:
        _operations._decode_m2_position_scope(value)
    elif actual_tag == _M2_VENUE_STATE_TAG:
        _validate_runtime_checkpoint_venue_wire(value)
    elif actual_tag == _M2_AUTHORITY_CHECKPOINT_TAG:
        _validate_runtime_checkpoint_authority_wire(value)
    elif actual_tag == _M2_ACQUISITION_STATE_TAG:
        _validate_runtime_checkpoint_acquisition_wire(value)
    elif actual_tag == _M2_DORMANT_ACQUISITION_TAG:
        _validate_runtime_checkpoint_dormant_acquisition_wire(value)
    elif actual_tag == _M2_EXECUTION_STATE_TAG:
        _validate_runtime_checkpoint_execution_wire(value)
    elif actual_tag == _M2_PROTECTION_CHECKPOINT_TAG:
        _validate_runtime_checkpoint_protection_wire(value)
    elif actual_tag == _M2_DORMANT_PROTECTION_TAG:
        _validate_runtime_checkpoint_dormant_protection_wire(value)
    canonical = _encode_canonical_json(value)
    if len(canonical) > _MAX_RUNTIME_CHECKPOINT_COMPONENT_BYTES:
        raise OverflowError("checkpoint component exceeds its byte limit")
    return _issue_component(actual_tag, canonical)


def _decode_runtime_checkpoint(
    payload_bytes: bytes, load_proof_binding: bytes
) -> RuntimeCheckpointEnvelope:
    """Parse canonical bytes to a registered LOADED, still-inert envelope."""

    if type(payload_bytes) is not bytes:
        raise TypeError("checkpoint payload must be exact bytes")
    if len(payload_bytes) > _MAX_RUNTIME_CHECKPOINT_PAYLOAD_BYTES:
        raise OverflowError("checkpoint payload exceeds its byte limit")
    if type(load_proof_binding) is not bytes or len(load_proof_binding) != 32:
        raise ValueError("load proof binding must be exact 32 bytes")
    payload = _decode_canonical_json(payload_bytes)
    if (
        type(payload) is not list
        or len(payload) != 10
        or payload[0] != 1
        or payload[1] != _M2_RUNTIME_CHECKPOINT_TAG
    ):
        raise ValueError("runtime checkpoint outer envelope has the wrong exact shape")
    application_generation_id = _operations._decode_m2_m1_as(
        "runtime checkpoint application generation",
        payload[2],
        _identity.ApplicationGenerationId,
    )
    execution_profile_id = _require_sha256_text("execution profile ID", payload[3])
    market_source_profile_id = _require_sha256_text(
        "market source profile ID", payload[4]
    )
    currentness_head_ordinal = _require_nonnegative_int(
        "currentness head ordinal", payload[5]
    )
    checkpoint_version_ordinal = _require_nonnegative_int(
        "checkpoint version ordinal", payload[6]
    )
    if checkpoint_version_ordinal < 1:
        raise ValueError("checkpoint version ordinal must be positive")
    venue = _decode_component(payload[7], _M2_VENUE_STATE_TAG)
    authority = _decode_component(payload[8], _M2_AUTHORITY_CHECKPOINT_TAG)
    scope_wrapper = payload[9]
    if (
        type(scope_wrapper) is not list
        or len(scope_wrapper) != 3
        or scope_wrapper[0] != _M2_RUNTIME_SCOPES_TAG
        or type(scope_wrapper[1]) is not int
        or type(scope_wrapper[2]) is not list
        or scope_wrapper[1] != len(scope_wrapper[2])
    ):
        raise ValueError("runtime checkpoint scope wrapper has the wrong exact shape")
    if len(scope_wrapper[2]) > _MAX_RUNTIME_CHECKPOINT_SCOPES:
        raise OverflowError("runtime checkpoint has too many scopes")
    scopes: list[RuntimeCheckpointScopeCandidate] = []
    prior_scope_id = -1
    for row in scope_wrapper[2]:
        if type(row) is not list or len(row) != 6 or row[0] != _M2_RUNTIME_SCOPE_TAG:
            raise ValueError("runtime checkpoint scope row has the wrong exact shape")
        scope_id = _require_nonnegative_int("scope ID", row[1])
        if scope_id <= prior_scope_id:
            raise ValueError("runtime checkpoint scopes are not strictly ordered")
        prior_scope_id = scope_id
        position_scope = _decode_component(row[2], _M2_POSITION_SCOPE_TAG)
        acquisition = _decode_component(
            row[3], (_M2_ACQUISITION_STATE_TAG, _M2_DORMANT_ACQUISITION_TAG)
        )
        execution = _decode_component(row[4], _M2_EXECUTION_STATE_TAG)
        protection = _decode_component(
            row[5], (_M2_PROTECTION_CHECKPOINT_TAG, _M2_DORMANT_PROTECTION_TAG)
        )
        if row[2] != row[3][2] or row[2] != row[4][1]:
            raise ValueError("runtime checkpoint scope components do not agree")
        if row[5][0] == _M2_DORMANT_PROTECTION_TAG and row[5][1] != scope_id:
            raise ValueError("dormant protection scope does not agree")
        scopes.append(
            _issue_scope_candidate(
                scope_id, position_scope, acquisition, execution, protection
            )
        )
    return _issue_envelope(
        application_generation_id=application_generation_id,
        execution_profile_id=execution_profile_id,
        market_source_profile_id=market_source_profile_id,
        currentness_head_ordinal=currentness_head_ordinal,
        checkpoint_version_ordinal=checkpoint_version_ordinal,
        venue=venue,
        authority=authority,
        scopes=tuple(scopes),
        canonical_payload_bytes=payload_bytes,
        provenance="LOADED",
        selection_binding=load_proof_binding,
        owner_preimage=None,
    )


def _issue_projected_runtime_checkpoint(
    *,
    selection_proof_binding: bytes,
    application_generation_id: _identity.ApplicationGenerationId,
    execution_profile_id: str,
    market_source_profile_id: str,
    currentness_head_ordinal: int,
    checkpoint_version_ordinal: int,
    venue_wire: list[object],
    authority_wire: list[object],
    scope_wires: tuple[
        tuple[int, list[object], list[object], list[object], list[object]], ...
    ],
    venue_owner_commitment: bytes,
    authority_owner_commitment: bytes,
    scope_owner_commitments: tuple[tuple[int, bytes, bytes, bytes], ...],
) -> RuntimeCheckpointEnvelope:
    """Seal already owner-authenticated projections without minting serving authority."""

    venue = _decode_component(venue_wire, _M2_VENUE_STATE_TAG)
    authority = _decode_component(authority_wire, _M2_AUTHORITY_CHECKPOINT_TAG)
    scopes = tuple(
        _issue_scope_candidate(
            scope_id,
            _decode_component(position_wire, _M2_POSITION_SCOPE_TAG),
            _decode_component(
                acquisition_wire,
                (_M2_ACQUISITION_STATE_TAG, _M2_DORMANT_ACQUISITION_TAG),
            ),
            _decode_component(execution_wire, _M2_EXECUTION_STATE_TAG),
            _decode_component(
                protection_wire,
                (_M2_PROTECTION_CHECKPOINT_TAG, _M2_DORMANT_PROTECTION_TAG),
            ),
        )
        for scope_id, position_wire, acquisition_wire, execution_wire, protection_wire in scope_wires
    )
    preimage = _RuntimeCheckpointOwnerPreimage(
        selection_proof_binding,
        venue_owner_commitment,
        authority_owner_commitment,
        scope_owner_commitments,
    )
    provisional = object.__new__(RuntimeCheckpointEnvelope)
    for name, value in (
        ("application_generation_id", application_generation_id),
        ("execution_profile_id", execution_profile_id),
        ("market_source_profile_id", market_source_profile_id),
        ("currentness_head_ordinal", currentness_head_ordinal),
        ("checkpoint_version_ordinal", checkpoint_version_ordinal),
        ("venue", venue),
        ("authority", authority),
        ("scopes", scopes),
    ):
        object.__setattr__(provisional, name, value)
    payload_bytes = _canonical_payload_from_envelope(provisional)
    return _issue_envelope(
        application_generation_id=application_generation_id,
        execution_profile_id=execution_profile_id,
        market_source_profile_id=market_source_profile_id,
        currentness_head_ordinal=currentness_head_ordinal,
        checkpoint_version_ordinal=checkpoint_version_ordinal,
        venue=venue,
        authority=authority,
        scopes=scopes,
        canonical_payload_bytes=payload_bytes,
        provenance="PROJECTED",
        selection_binding=selection_proof_binding,
        owner_preimage=preimage,
    )


def _checkpoint_collection(tag: str, rows: list[object]) -> list[object]:
    """Build one literal count-bearing checkpoint collection."""

    return [tag, len(rows), rows]


def _checkpoint_row_commitment(domain: bytes, row: list[object]) -> bytes:
    """Commit one already canonical explicit row under its frozen owner domain."""

    return _commit_runtime_parts(domain, _encode_canonical_json(row))


def _checkpoint_enum(owner: str, value: object) -> list[str]:
    """Encode an exact enum only where the caller supplies its literal owner tag."""

    member = getattr(value, "value", None)
    if type(member) is not str:
        raise TypeError("checkpoint enum must expose one exact text member")
    return [owner, member]


def _selected_record_binding(record: object) -> bytes:
    binding = _records._runtime_checkpoint_selected_record_binding(record)
    if type(binding) is not bytes or len(binding) != 32:
        raise ValueError("selected record binding is not exact SHA-256 bytes")
    return binding


def _dormant_generation_row(
    record: _records.AcquisitionGenerationRecord,
) -> list[object]:
    return [
        "m2.acquisition.DormantGeneration/v1",
        _operations._encode_m2_m1_atom(record.acquisition_generation_id),
        record.scope_id,
        record.status,
        record.successor_ordinal,
        None
        if record.predecessor_generation_id is None
        else _operations._encode_m2_m1_atom(record.predecessor_generation_id),
        _require_sha256_text(
            "generation mandate commitment", record.mandate_commitment_sha256
        ),
        _require_sha256_text(
            "generation compatibility", record.emergency_compatibility_sha256
        ),
    ]


def _dormant_generation_current_row(
    record: _records.AcquisitionGenerationCurrentRecord,
) -> list[object]:
    return [
        "m2.acquisition.DormantGenerationCurrent/v1",
        _operations._encode_m2_m1_atom(record.acquisition_generation_id),
        record.scope_id,
        record.current_economics_head_ordinal,
        record.unresolved_effect_count,
        record.active_protection_count,
    ]


def _dormant_stream_row(record: _records.MarketStreamAuthorityRecord) -> list[object]:
    return [
        "m2.acquisition.DormantMarketStream/v1",
        _operations._encode_m2_m1_atom(record.stream_generation_id),
        record.scope_id,
        _operations._encode_m2_m1_atom(record.application_generation_id),
        _operations._encode_m2_m1_atom(record.acquisition_generation_id),
        _require_sha256_text(
            "stream mandate commitment", record.generation_mandate_commitment_sha256
        ),
        record.source_profile_id,
        _operations._encode_m2_m1_atom(record.session_id),
        record.sequence_mode,
    ]


def _dormant_cursor_row(record: _records.MarketCursorRecord) -> list[object]:
    return [
        "m2.acquisition.DormantMarketCursor/v1",
        _operations._encode_m2_m1_atom(record.stream_generation_id),
        record.scope_id,
        _operations._encode_m2_m1_atom(record.application_generation_id),
        _operations._encode_m2_m1_atom(record.acquisition_generation_id),
        _require_sha256_text(
            "cursor mandate commitment", record.generation_mandate_commitment_sha256
        ),
        record.source_profile_id,
        _operations._encode_m2_m1_atom(record.session_id),
        record.sequence_mode,
        record.fixed_cursor_ordinal,
        record.published_head_ordinal,
    ]


def _dormant_lineage_row(
    kind: _acquisition.GenerationRouteKind,
    identity: object,
    generation_id: _identity.AcquisitionGenerationId,
    source: list[object],
    source_record_binding: bytes,
) -> list[object]:
    row: list[object] = [
        "m2.acquisition.DormantLineageRoute/v1",
        _checkpoint_enum("m1.acquisition.GenerationRouteKind", kind),
        _operations._encode_m2_m1_atom(_cast(_durable_codec._OwningValue, identity)),
        _operations._encode_m2_m1_atom(generation_id),
        source,
        source_record_binding.hex(),
    ]
    row.append(
        _checkpoint_row_commitment(
            b"execution-core/m2-acquisition/dormant-lineage-route/v1", row
        ).hex()
    )
    return row


def _encode_dormant_acquisition(
    selection: _records._RuntimeCheckpointSelectionSet,
    controller: _records.SymbolControllerRecord,
    position_scope: object,
    selection_binding: bytes,
) -> tuple[list[object], bytes]:
    """Project one null-LIVE scope solely from repository-authentic selected rows."""

    scope_id = controller.scope_id
    generations = tuple(
        row for row in selection.unresolved_generations if row.scope_id == scope_id
    )
    currents = tuple(
        row
        for row in selection.unresolved_generation_current
        if row.scope_id == scope_id
    )
    if len(generations) != len(currents) or any(
        generation.acquisition_generation_id != current.acquisition_generation_id
        for generation, current in zip(generations, currents, strict=True)
    ):
        raise ValueError("dormant generation/current rows do not pair exactly")
    generation_ids = {row.acquisition_generation_id for row in generations}
    streams = tuple(
        row
        for row in selection.streams
        if row.scope_id == scope_id and row.acquisition_generation_id in generation_ids
    )
    cursors = tuple(
        row
        for row in selection.cursors
        if row.scope_id == scope_id and row.acquisition_generation_id in generation_ids
    )
    stream_by_id = {row.stream_generation_id: row for row in streams}
    if any(
        cursor.stream_generation_id not in stream_by_id
        or (
            cursor.application_generation_id,
            cursor.acquisition_generation_id,
            cursor.generation_mandate_commitment_sha256,
            cursor.source_profile_id,
            cursor.session_id,
            cursor.sequence_mode,
        )
        != (
            stream_by_id[cursor.stream_generation_id].application_generation_id,
            stream_by_id[cursor.stream_generation_id].acquisition_generation_id,
            stream_by_id[
                cursor.stream_generation_id
            ].generation_mandate_commitment_sha256,
            stream_by_id[cursor.stream_generation_id].source_profile_id,
            stream_by_id[cursor.stream_generation_id].session_id,
            stream_by_id[cursor.stream_generation_id].sequence_mode,
        )
        for cursor in cursors
    ):
        raise ValueError("dormant stream/cursor rows do not pair exactly")

    position = _cast(_Any, position_scope)
    broker = position.broker
    environment = position.environment
    account = position.account
    roots_by_id = {
        row.root_fill_key_id: row
        for row in selection.roots
        if row.scope_id == scope_id and row.owner_generation_id in generation_ids
    }
    routes_by_root = {
        row.root_fill_key_id: row
        for row in selection.root_routes
        if row.scope_id == scope_id and row.acquisition_generation_id in generation_ids
    }
    lineage_rows: list[list[object]] = []
    lineage_bindings: list[bytes] = []
    for effect in selection.effects:
        if (
            effect.scope_id != scope_id
            or effect.acquisition_generation_id not in generation_ids
        ):
            continue
        binding = _selected_record_binding(effect)
        source: list[object] = [
            "m2.acquisition.LineageEffectSource/v1",
            _operations._encode_m2_m1_atom(effect.effect_external),
        ]
        lineage_rows.extend(
            (
                _dormant_lineage_row(
                    _acquisition.GenerationRouteKind.REQUEST,
                    effect.request_occurrence_id,
                    effect.acquisition_generation_id,
                    source,
                    binding,
                ),
                _dormant_lineage_row(
                    _acquisition.GenerationRouteKind.EFFECT,
                    effect.effect_external,
                    effect.acquisition_generation_id,
                    source,
                    binding,
                ),
            )
        )
        lineage_bindings.extend((binding, binding))
    for owner in selection.owners:
        if (
            owner.scope_id != scope_id
            or owner.owner_generation_id not in generation_ids
        ):
            continue
        binding = _selected_record_binding(owner)
        lineage_rows.append(
            _dormant_lineage_row(
                _acquisition.GenerationRouteKind.OWNER,
                _identity.VenueLegKey(broker, environment, account, owner.owner_id),
                owner.owner_generation_id,
                [
                    "m2.acquisition.LineageOwnerSource/v1",
                    scope_id,
                    _operations._encode_m2_m1_atom(owner.owner_id),
                ],
                binding,
            )
        )
        lineage_bindings.append(binding)
    for root_id, root in roots_by_id.items():
        route = routes_by_root.get(root_id)
        if route is None or route.acquisition_generation_id != root.owner_generation_id:
            raise ValueError("dormant root route is missing or spliced")
        route_binding = _selected_record_binding(route)
        root_binding = _selected_record_binding(root)
        pair: list[object] = [
            "m2.acquisition.DormantRootSourceBinding/v1",
            route_binding.hex(),
            root_binding.hex(),
        ]
        source_binding = _checkpoint_row_commitment(
            b"execution-core/m2-acquisition/dormant-root-source/v1", pair
        )
        lineage_rows.append(
            _dormant_lineage_row(
                _acquisition.GenerationRouteKind.ROOT,
                _identity.RootFillKey(broker, environment, account, root.root_fill_id),
                root.owner_generation_id,
                ["m2.acquisition.LineageRootSource/v1", root_id],
                source_binding,
            )
        )
        lineage_bindings.append(source_binding)
    for fact in selection.current_facts:
        selected_root = roots_by_id.get(fact.root_fill_key_id)
        if selected_root is None:
            continue
        binding = _selected_record_binding(fact)
        lineage_rows.append(
            _dormant_lineage_row(
                _acquisition.GenerationRouteKind.FACT,
                _identity.ExecutionFactKey(
                    broker, environment, account, fact.source_event_id
                ),
                selected_root.owner_generation_id,
                ["m2.acquisition.LineageFactSource/v1", fact.fact_id],
                binding,
            )
        )
        lineage_bindings.append(binding)

    generation_rows = _checkpoint_collection(
        "m2.acquisition.DormantGenerations/v1",
        [_dormant_generation_row(row) for row in generations],
    )
    current_rows = _checkpoint_collection(
        "m2.acquisition.DormantGenerationCurrents/v1",
        [_dormant_generation_current_row(row) for row in currents],
    )
    stream_rows = _checkpoint_collection(
        "m2.acquisition.DormantMarketStreams/v1",
        [_dormant_stream_row(row) for row in streams],
    )
    cursor_rows = _checkpoint_collection(
        "m2.acquisition.DormantMarketCursors/v1",
        [_dormant_cursor_row(row) for row in cursors],
    )
    lineage = _checkpoint_collection(
        "m2.acquisition.DormantLineageRoutes/v1",
        _cast(list[object], lineage_rows),
    )
    registry_preimage: list[object] = [
        "m2.acquisition.DormantRegistry/v2",
        generation_rows,
        current_rows,
        stream_rows,
        cursor_rows,
    ]
    registry_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-acquisition/dormant-registry/v2", registry_preimage
    )
    lineage_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-acquisition/dormant-lineage/v2", lineage
    )
    row: list[object] = [
        _M2_DORMANT_ACQUISITION_TAG,
        _operations._encode_m2_m1_atom(controller.application_generation_id),
        _operations._encode_m2_position_scope(position_scope),
        scope_id,
        controller.aggregate_quantity,
        controller.integrity_state,
        controller.currentness_head_ordinal,
        controller.controller_version_ordinal,
        _require_sha256_text(
            "controller compatibility", controller.emergency_compatibility_sha256
        ),
        generation_rows,
        current_rows,
        stream_rows,
        cursor_rows,
        lineage,
        registry_commitment.hex(),
        lineage_commitment.hex(),
    ]
    row.append(
        _checkpoint_row_commitment(
            b"execution-core/m2-acquisition/dormant/v2", row
        ).hex()
    )
    selected_bindings = tuple(
        _selected_record_binding(item)
        for family in (generations, currents, streams, cursors)
        for item in family
    ) + tuple(lineage_bindings)
    source_projection = _commit_runtime_parts(
        b"execution-core/m2-acquisition/dormant-source-projection/v1",
        _field_bytes(selection_binding),
        _field_int(scope_id),
        _field_bytes(_selected_record_binding(controller)),
        _sequence_domain(
            b"execution-core/m2-acquisition/dormant-selected-records/v1",
            tuple(_field_bytes(binding) for binding in selected_bindings),
        ),
    )
    return row, source_projection


def _encode_dormant_protection(
    authority: _records.ProtectionAuthorityRecord,
    selection_binding: bytes,
) -> tuple[list[object], bytes]:
    active = (
        authority.active_stream_generation_id,
        authority.active_acquisition_generation_id,
        authority.active_generation_mandate_commitment_sha256,
        authority.active_source_profile_id,
        authority.active_session_id,
        authority.active_sequence_mode,
    )
    if any(value is not None for value in active):
        raise ValueError("dormant protection authority is partially active")
    row: list[object] = [
        _M2_DORMANT_PROTECTION_TAG,
        authority.scope_id,
        authority.authority_class,
        authority.expected_controller_head_ordinal,
        _require_sha256_text(
            "dormant protection state", authority.state_commitment_sha256
        ),
        authority.version_ordinal,
    ]
    row.append(
        _checkpoint_row_commitment(
            b"execution-core/m2-protection/dormant/v1", row
        ).hex()
    )
    source_projection = _commit_runtime_parts(
        b"execution-core/m2-protection/dormant-source-projection/v1",
        _field_bytes(selection_binding),
        _field_int(authority.scope_id),
        _field_bytes(_selected_record_binding(authority)),
    )
    return row, source_projection


def _encode_runtime_checkpoint_venue(
    book: _venue.VenueRecoveryBook,
) -> tuple[list[object], bytes, bytes]:
    """Encode the frozen venue top row without serializing audit history."""

    if type(book) is not _venue.VenueRecoveryBook:
        raise TypeError("venue owner must be exact VenueRecoveryBook")
    book._validate_full()
    payload_maps = (
        book._authority_epoch_by_scope,
        book._effect_by_id,
        book._claim_by_effect,
        book._owner_by_leg,
        book._acquisition_correlation_by_root,
        book._closure_head_by_leg,
        book._economic_high_water_by_leg,
        book._human_coverage_by_root,
        book._broker_coverage_by_root,
        book._coverage_provenance_by_scope,
        book._reconciliation_by_input,
        book._execution_reconciliation_by_input,
        book._execution_snapshot_by_scope,
        book._bootstrap_bound_target_by_scope,
        book._protection_cursor_by_scope,
    )
    if any(retained.size for retained in payload_maps):
        raise ValueError(
            "nonempty venue checkpoint rows are not admitted by this projector"
        )
    if book._effect_order.length or book._owner_order.length:
        raise ValueError("venue source order is not represented by selected rows")
    registry_count = book.execution_registry_count
    registry_commitment = book.execution_registry_commitment
    row: list[object] = [
        _M2_VENUE_STATE_TAG,
        [
            "m2.venue.Scope/v1",
            _operations._encode_m2_m1_atom(book.scope.generation),
            _operations._encode_m2_m1_atom(book.scope.broker),
            _operations._encode_m2_m1_atom(book.scope.environment),
            _operations._encode_m2_m1_atom(book.scope.account),
        ],
        book._account_authority_epoch,
        book._unresolved_account_execution_reconciliation_count,
        registry_count,
        (
            None
            if registry_commitment is None
            else _operations._encode_m2_bytes(registry_commitment)
        ),
        (
            None
            if book._registry_transition_head_commitment is None
            else _operations._encode_m2_bytes(book._registry_transition_head_commitment)
        ),
        _checkpoint_collection("m2.venue.AuthorityEpochs/v1", []),
        _checkpoint_collection("m2.venue.Effects/v1", []),
        _checkpoint_collection("m2.venue.Claims/v1", []),
        _checkpoint_collection("m2.venue.OwnerAttempts/v1", []),
        _checkpoint_collection("m2.venue.AcquisitionCorrelations/v1", []),
        _checkpoint_collection("m2.venue.ClosureHeads/v1", []),
        _checkpoint_collection("m2.venue.EconomicHighWaters/v1", []),
        _checkpoint_collection("m2.venue.HumanCoverages/v1", []),
        _checkpoint_collection("m2.venue.BrokerCoverages/v1", []),
        _checkpoint_collection("m2.venue.CoverageProvenances/v1", []),
        _checkpoint_collection("m2.venue.Reconciliations/v1", []),
        _checkpoint_collection("m2.venue.ExecutionReconciliations/v1", []),
        _checkpoint_collection("m2.venue.ExecutionScopes/v1", []),
        _checkpoint_collection("m2.venue.BootstrapTargets/v1", []),
        _checkpoint_collection("m2.venue.ProtectionCursors/v1", []),
    ]
    commitment = _checkpoint_row_commitment(b"execution-core/m2-venue/state/v1", row)
    source_owner_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-venue/source-owner/v1", row
    )
    row.append(_operations._encode_m2_bytes(commitment))
    return row, commitment, source_owner_commitment


def _encode_runtime_checkpoint_manual_row(
    manual: _authority._ManualFlatten,
) -> list[object]:
    """Encode one payload-owned manual flatten row under the R20 section 3 rules."""

    if type(manual) is not _authority._ManualFlatten:
        raise TypeError("manual flatten must be exact _ManualFlatten")
    cancel_effect_ids = manual.cancel_effect_ids
    if type(cancel_effect_ids) is not tuple:
        raise TypeError("manual cancel effect IDs must be an exact tuple")
    if len(cancel_effect_ids) > _MAX_CHECKPOINT_COLLECTION_ROWS:
        raise ValueError("manual cancel effects exceed the bounded row cap")
    for effect_id in cancel_effect_ids:
        if type(effect_id) is not _identity.EffectId:
            raise TypeError("manual cancel effect must be exact EffectId")
    ordered = sorted(cancel_effect_ids, key=lambda effect_id: effect_id.value)
    if len({effect_id.value for effect_id in ordered}) != len(ordered):
        raise ValueError("manual cancel effects retain a duplicate effect ID")
    sell_effect_id = manual.sell_effect_id
    if sell_effect_id is not None and type(sell_effect_id) is not _identity.EffectId:
        raise TypeError("manual sell effect must be exact EffectId or None")
    return [
        "m2.authority.ManualFlatten/v1",
        _operations._encode_m2_begin_manual_flatten(manual.command),
        _checkpoint_enum("m1.authority.FlattenPhase", manual.phase),
        _checkpoint_collection(
            "m2.authority.CancelEffects/v1",
            [_operations._encode_m2_m1_atom(effect_id) for effect_id in ordered],
        ),
        (
            None
            if sell_effect_id is None
            else _operations._encode_m2_m1_atom(sell_effect_id)
        ),
    ]


def _encode_runtime_checkpoint_manual_rows(
    state: _authority.ExecutionAuthorityState,
    application_generation_id: _identity.ApplicationGenerationId,
    selected_position_scopes: tuple[_fills.PositionScope, ...],
) -> list[object]:
    """Project each manual reached from a selected scope, refusing any that is not.

    Manual state is payload-owned rather than repository-selected, so it is not one
    of the four permitted supersets: every retained manual must be reachable through
    ``_manual_flatten_by_scope`` then ``_manual_by_id`` from a selected scope. An
    unreachable manual fails closed instead of being dropped from the checkpoint.
    """

    reached: dict[str, _authority._ManualFlatten] = {}
    for position_scope in selected_position_scopes:
        slot_key = _authority._acquisition_scope_key(
            application_generation_id, position_scope
        )
        flatten_id = state._manual_flatten_by_scope.get(slot_key)
        if flatten_id is None:
            continue
        manual = state._manual_by_id.get(_authority._manual_key(flatten_id))
        if manual is None:
            raise ValueError("selected scope names an absent manual flatten")
        if flatten_id.value in reached:
            raise ValueError("selected scopes retain a duplicate manual flatten")
        reached[flatten_id.value] = manual
    if state._manual_by_id.size != len(reached):
        raise ValueError("manual flatten state is not reachable from selected scopes")
    return _checkpoint_collection(
        "m2.authority.ManualFlattens/v1",
        [
            _encode_runtime_checkpoint_manual_row(reached[flatten_value])
            for flatten_value in sorted(reached)
        ],
    )


def _encode_runtime_checkpoint_authority(
    state: _authority.ExecutionAuthorityState,
    venue_commitment: bytes,
    application_generation_id: _identity.ApplicationGenerationId,
    selected_position_scopes: tuple[_fills.PositionScope, ...],
) -> tuple[list[object], bytes]:
    """Encode the corrected R2 authority top row and its exact empty collections."""

    if type(state) is not _authority.ExecutionAuthorityState:
        raise TypeError("authority owner must be exact ExecutionAuthorityState")
    _authority._validate_authority_state(state)
    manual_rows = _encode_runtime_checkpoint_manual_rows(
        state, application_generation_id, selected_position_scopes
    )
    payload_maps = (
        state._effect_authority_by_id,
        state._acquisition_descriptor_by_effect,
        state._acquisition_currentness_by_scope,
        state._acquisition_descriptor_by_scope,
        state._acquisition_active_by_scope,
    )
    if any(retained.size for retained in payload_maps):
        raise ValueError("nonempty authority checkpoint rows are not admitted")
    if state._emergency_grant is not None:
        raise ValueError("emergency authority checkpoint row is not admitted")
    scope = state.venue.scope
    row: list[object] = [
        _M2_AUTHORITY_CHECKPOINT_TAG,
        _checkpoint_enum("m1.authority.EnginePhase", state.phase),
        _checkpoint_enum("m1.authority.TradingMode", state.mode),
        _checkpoint_enum("m1.authority.SupervisorFence", state.supervisor_fence),
        state.kill_engaged,
        (
            None
            if state.session_id is None
            else _operations._encode_m2_m1_atom(state.session_id)
        ),
        [
            "m2.authority.RequestBudget/v1",
            state.budget.remaining,
            state.budget.safety_reserve,
        ],
        [
            "m2.authority.VenueRef/v1",
            _operations._encode_m2_m1_atom(scope.generation),
            _operations._encode_m2_m1_atom(scope.broker),
            _operations._encode_m2_m1_atom(scope.environment),
            _operations._encode_m2_m1_atom(scope.account),
            _operations._encode_m2_bytes(venue_commitment),
        ],
        None,
        _checkpoint_collection("m2.authority.EffectAuthorizations/v1", []),
        manual_rows,
        _checkpoint_collection("m2.authority.AcquisitionDescriptors/v1", []),
        _checkpoint_collection("m2.authority.AcquisitionSlots/v1", []),
    ]
    commitment = _checkpoint_row_commitment(
        b"execution-core/m2-authority/state/v1", row
    )
    row.append(_operations._encode_m2_bytes(commitment))
    return row, commitment


def _encode_runtime_checkpoint_generation(
    record: _acquisition.GenerationRecordView,
) -> list[object]:
    binding = record.binding
    commitment = _acquisition._generation_record_view_commitment(
        binding,
        record.economics_head_commitment,
        record.serving_class,
        record.closure_summary_commitment,
    )
    return [
        "m2.acquisition.Generation/v1",
        _operations._encode_m2_m1_atom(binding.generation_id),
        _operations._encode_m2_m1_atom(binding.application_generation_id),
        _operations._encode_m2_position_scope(binding.position_scope),
        binding.successor_ordinal,
        _operations._encode_m2_bytes(binding.dual_mandate_binding_commitment),
        _operations._encode_m2_bytes(binding.predecessor_or_genesis_head_commitment),
        _operations._encode_m2_bytes(
            binding.emergency_recovery_compatibility_commitment
        ),
        _operations._encode_m2_bytes(record.economics_head_commitment),
        _checkpoint_enum("m1.acquisition.GenerationServingClass", record.serving_class),
        _operations._encode_m2_bytes(record.closure_summary_commitment),
        _operations._encode_m2_bytes(commitment),
    ]


def _encode_runtime_checkpoint_acquisition(
    state: _acquisition.AcquisitionControllerState,
    selection: _records._RuntimeCheckpointSelectionSet,
    scope_id: int,
) -> tuple[list[object], bytes]:
    """Encode one authentic bounded acquisition owner without generic traversal."""

    if not _acquisition._controller_state_is_authentic(state):
        raise ValueError("acquisition owner is not authentic")
    controller = state._controller
    generation_id = controller.live_generation_id
    if generation_id is None:
        raise ValueError("acquisition owner has no live generation")
    live = state.registry.record(generation_id)
    route = _acquisition._registry_market_stream_route(
        state.registry,
        state._mandate.protection_mandate.evidence_policy.stream_generation,
    )
    if live is None or route is None or route.binding != live.binding:
        raise ValueError("acquisition live generation route is incomplete")
    controller_wire = [
        "m2.acquisition.Controller/v1",
        _operations._encode_m2_m1_atom(controller.application_generation_id),
        _operations._encode_m2_position_scope(controller.position_scope),
        _operations._encode_m2_bytes(controller.controller_head),
        controller.successor_ordinal,
        _operations._encode_m2_m1_atom(generation_id),
        _checkpoint_enum(
            "m1.acquisition.AcquisitionRecoveryClass", controller.recovery_class
        ),
        _operations._encode_m2_bytes(controller.scope_execution_commitment),
        _operations._encode_m2_bytes(controller.venue_commitment),
        _operations._encode_m2_bytes(controller.authority_context_commitment),
        (
            None
            if controller.protection_commitment is None
            else _operations._encode_m2_bytes(controller.protection_commitment)
        ),
        _operations._encode_m2_bytes(controller._binding_commitment),
        _operations._encode_m2_bytes(controller._compatibility_commitment),
        _operations._encode_m2_bytes(controller.commitment),
    ]
    live_wire = _encode_runtime_checkpoint_generation(live)
    route_commitment = _acquisition._market_stream_generation_route_commitment(
        route.stream_generation, route.binding
    )
    route_wire = [
        "m2.acquisition.MarketStreamRoute/v1",
        _operations._encode_m2_m1_atom(route.stream_generation),
        _operations._encode_m2_m1_atom(generation_id),
        _operations._encode_m2_bytes(route_commitment),
    ]
    unresolved_records = tuple(
        record
        for record in selection.unresolved_generations
        if record.scope_id == scope_id
    )
    unresolved_views: list[_acquisition.GenerationRecordView] = []
    unresolved_route_wires: list[object] = []
    for selected_record in unresolved_records:
        retained = state.registry.record(selected_record.acquisition_generation_id)
        if retained is None:
            raise ValueError("selected unresolved generation is absent from owner")
        binding = retained.binding
        if (
            binding.application_generation_id != state.application_generation_id
            or binding.position_scope != state.position_scope
            or binding.successor_ordinal != selected_record.successor_ordinal
            or binding.dual_mandate_binding_commitment.hex()
            != selected_record.mandate_commitment_sha256
            or binding.emergency_recovery_compatibility_commitment.hex()
            != selected_record.emergency_compatibility_sha256
            or retained.serving_class.value != selected_record.status
        ):
            raise ValueError("selected unresolved generation is spliced")
        unresolved_views.append(retained)
        selected_streams = tuple(
            stream
            for stream in selection.streams
            if stream.scope_id == scope_id
            and stream.acquisition_generation_id
            == selected_record.acquisition_generation_id
        )
        if len(selected_streams) != 1:
            raise ValueError("selected unresolved generation requires one stream route")
        selected_stream = selected_streams[0]
        retained_route = _acquisition._registry_market_stream_route(
            state.registry, selected_stream.stream_generation_id
        )
        if (
            retained_route is None
            or retained_route.binding != binding
            or selected_stream.application_generation_id
            != state.application_generation_id
            or selected_stream.generation_mandate_commitment_sha256
            != selected_record.mandate_commitment_sha256
        ):
            raise ValueError("selected unresolved stream route is spliced")
        unresolved_route_wires.append(
            [
                "m2.acquisition.MarketStreamRoute/v1",
                _operations._encode_m2_m1_atom(retained_route.stream_generation),
                _operations._encode_m2_m1_atom(binding.generation_id),
                _operations._encode_m2_bytes(
                    _acquisition._market_stream_generation_route_commitment(
                        retained_route.stream_generation, binding
                    )
                ),
            ]
        )
    unresolved_generations = _checkpoint_collection(
        "m2.acquisition.UnresolvedGenerations/v1",
        [_encode_runtime_checkpoint_generation(value) for value in unresolved_views],
    )
    unresolved_routes = _checkpoint_collection(
        "m2.acquisition.UnresolvedMarketStreamRoutes/v1", unresolved_route_wires
    )

    position_scope = state.position_scope
    lineage_rows: list[object] = []

    def append_lineage(
        kind: _acquisition.GenerationRouteKind,
        identity_value: _durable_codec._OwningValue,
        generation: _identity.AcquisitionGenerationId,
        source_binding: list[object],
    ) -> None:
        if kind is _acquisition.GenerationRouteKind.REQUEST:
            route_view = state.lineage.route_request(
                _cast(_identity.RequestOccurrenceId, identity_value)
            )
        elif kind is _acquisition.GenerationRouteKind.EFFECT:
            route_view = state.lineage.route_effect(
                _cast(_identity.EffectId, identity_value)
            )
        elif kind is _acquisition.GenerationRouteKind.OWNER:
            route_view = state.lineage.route_owner(
                _cast(_identity.VenueLegKey, identity_value)
            )
        elif kind is _acquisition.GenerationRouteKind.ROOT:
            route_view = state.lineage.route_root(
                _cast(_identity.RootFillKey, identity_value)
            )
        else:
            route_view = state.lineage.route_fact(
                _cast(_identity.ExecutionFactKey, identity_value)
            )
        if route_view is None or route_view.generation_id != generation:
            raise ValueError("selected acquisition lineage route is absent or spliced")
        route_row: list[object] = [
            "m2.acquisition.LineageRoute/v1",
            _checkpoint_enum("m1.acquisition.GenerationRouteKind", kind),
            _operations._encode_m2_m1_atom(identity_value),
            _operations._encode_m2_m1_atom(generation),
            source_binding,
            _operations._encode_m2_bytes(
                _acquisition._generation_route_commitment(
                    route_view.route_kind,
                    route_view.source_commitment,
                    route_view.generation_id,
                )
            ),
        ]
        lineage_rows.append(route_row)

    selected_generation_ids = {generation_id} | {
        record.acquisition_generation_id for record in unresolved_records
    }
    for effect in selection.effects:
        if (
            effect.scope_id != scope_id
            or effect.acquisition_generation_id not in selected_generation_ids
        ):
            continue
        source: list[object] = [
            "m2.acquisition.LineageEffectSource/v1",
            _operations._encode_m2_m1_atom(effect.effect_external),
        ]
        append_lineage(
            _acquisition.GenerationRouteKind.REQUEST,
            effect.request_occurrence_id,
            effect.acquisition_generation_id,
            source,
        )
        append_lineage(
            _acquisition.GenerationRouteKind.EFFECT,
            effect.effect_external,
            effect.acquisition_generation_id,
            source,
        )
    for owner in selection.owners:
        if (
            owner.scope_id != scope_id
            or owner.owner_generation_id not in selected_generation_ids
        ):
            continue
        leg_key = _identity.VenueLegKey(
            position_scope.broker,
            position_scope.environment,
            position_scope.account,
            owner.owner_id,
        )
        append_lineage(
            _acquisition.GenerationRouteKind.OWNER,
            leg_key,
            owner.owner_generation_id,
            [
                "m2.acquisition.LineageOwnerSource/v1",
                scope_id,
                _operations._encode_m2_m1_atom(owner.owner_id),
            ],
        )
    roots_by_id = {
        root.root_fill_key_id: root
        for root in selection.roots
        if root.scope_id == scope_id
        and root.owner_generation_id in selected_generation_ids
    }
    for root_id, root in roots_by_id.items():
        root_key = _identity.RootFillKey(
            position_scope.broker,
            position_scope.environment,
            position_scope.account,
            root.root_fill_id,
        )
        append_lineage(
            _acquisition.GenerationRouteKind.ROOT,
            root_key,
            root.owner_generation_id,
            ["m2.acquisition.LineageRootSource/v1", root_id],
        )
    for fact in selection.current_facts:
        selected_root = roots_by_id.get(fact.root_fill_key_id)
        if selected_root is None:
            continue
        fact_key = _identity.ExecutionFactKey(
            position_scope.broker,
            position_scope.environment,
            position_scope.account,
            fact.source_event_id,
        )
        append_lineage(
            _acquisition.GenerationRouteKind.FACT,
            fact_key,
            selected_root.owner_generation_id,
            ["m2.acquisition.LineageFactSource/v1", fact.fact_id],
        )
    lineage = _checkpoint_collection("m2.acquisition.LineageRoutes/v1", lineage_rows)
    bounded_registry: list[object] = [
        "m2.acquisition.BoundedRegistry/v1",
        live_wire,
        route_wire,
        unresolved_generations,
        unresolved_routes,
    ]
    bounded_lineage: list[object] = [
        "m2.acquisition.BoundedLineage/v1",
        lineage,
    ]
    registry_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-acquisition/bounded-registry/v1", bounded_registry
    )
    lineage_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-acquisition/bounded-lineage/v1", bounded_lineage
    )
    row: list[object] = [
        _M2_ACQUISITION_STATE_TAG,
        _operations._encode_m2_m1_atom(state.application_generation_id),
        _operations._encode_m2_position_scope(state.position_scope),
        _operations._encode_m2_bytes(state.scope_execution_commitment),
        _operations._encode_m2_bytes(state.venue_commitment),
        _operations._encode_m2_bytes(state.authority_context_commitment),
        (
            None
            if state.protection_commitment is None
            else _operations._encode_m2_bytes(state.protection_commitment)
        ),
        controller_wire,
        _operations._encode_m2_acquisition_mandate(state._mandate),
        live_wire,
        route_wire,
        unresolved_generations,
        unresolved_routes,
        lineage,
        _operations._encode_m2_bytes(registry_commitment),
        _operations._encode_m2_bytes(lineage_commitment),
    ]
    commitment = _checkpoint_row_commitment(
        b"execution-core/m2-acquisition/state/v1", row
    )
    row.append(_operations._encode_m2_bytes(commitment))
    return row, commitment


def _project_runtime_checkpoint(
    selection_proof: _records.RuntimeCheckpointSelectionProof,
    venue: _venue.VenueRecoveryBook,
    authority: _authority.ExecutionAuthorityState,
    scope_owners: tuple[_RuntimeCheckpointScopeOwners, ...],
) -> RuntimeCheckpointEnvelope:
    """Project authentic owners into one canonical, explicitly inert envelope."""

    if type(selection_proof) is not _records.RuntimeCheckpointSelectionProof:
        raise TypeError("selection_proof must be exact RuntimeCheckpointSelectionProof")
    if not _records.RuntimeCheckpointSelectionProof._is_authentic(selection_proof):
        raise ValueError("selection_proof is not repository-authentic")
    if type(venue) is not _venue.VenueRecoveryBook:
        raise TypeError("venue must be exact VenueRecoveryBook")
    if type(authority) is not _authority.ExecutionAuthorityState:
        raise TypeError("authority must be exact ExecutionAuthorityState")
    if type(scope_owners) is not tuple:
        raise TypeError("scope_owners must be an exact tuple")

    venue._validate_full()
    _authority._validate_authority_state(authority)
    if authority.venue is not venue:
        raise ValueError("authority does not retain the selected venue owner")

    selected_scopes = selection_proof._selection.scopes
    selected_scope_ids = tuple(scope.scope_id for scope in selected_scopes)
    owner_scope_ids = tuple(
        owner.scope_id
        for owner in scope_owners
        if type(owner) is _RuntimeCheckpointScopeOwners
    )
    if len(owner_scope_ids) != len(scope_owners):
        raise TypeError("scope owner must be exact _RuntimeCheckpointScopeOwners")
    if owner_scope_ids != tuple(sorted(owner_scope_ids)) or len(owner_scope_ids) != len(
        set(owner_scope_ids)
    ):
        raise ValueError("scope owners must be strictly scope-ID ordered")
    if selected_scope_ids != owner_scope_ids:
        raise ValueError("selected scope coordinates do not match scope owners")

    request = selection_proof.request
    venue_scope = venue.scope
    if venue_scope.generation != request.application_generation_id:
        raise ValueError("top owner coordinates do not match selection proof")

    venue_wire, venue_commitment, venue_source_owner_commitment = (
        _encode_runtime_checkpoint_venue(venue)
    )
    selected_position_scopes = tuple(
        _fills.PositionScope(
            venue_scope.broker,
            venue_scope.environment,
            venue_scope.account,
            selected.symbol,
        )
        for selected in selected_scopes
    )
    authority_wire, authority_commitment = _encode_runtime_checkpoint_authority(
        authority,
        venue_commitment,
        request.application_generation_id,
        selected_position_scopes,
    )
    scope_wires: list[
        tuple[int, list[object], list[object], list[object], list[object]]
    ] = []
    owner_commitments: list[tuple[int, bytes, bytes, bytes]] = []
    controllers_by_scope = {
        controller.scope_id: controller
        for controller in selection_proof._selection.controllers
    }
    protections_by_scope = {
        protection.scope_id: protection
        for protection in selection_proof._selection.protection_authorities
    }
    for selected, owners in zip(selected_scopes, scope_owners, strict=True):
        acquisition = owners.acquisition
        execution = owners.execution
        protection = owners.protection
        if (
            acquisition is not None
            and type(acquisition) is not _acquisition.AcquisitionControllerState
        ):
            raise TypeError(
                "acquisition owner must be exact AcquisitionControllerState or None"
            )
        if type(execution) is not _position.ExecutionSnapshot:
            raise TypeError("execution owner must be exact ExecutionSnapshot")
        execution_state = _position._m2_execution_state_from_snapshot(execution)
        position_scope = execution.position.scope
        controller_record = controllers_by_scope.get(owners.scope_id)
        protection_record = protections_by_scope.get(owners.scope_id)
        if controller_record is None or protection_record is None:
            raise ValueError("selected scope is missing controller/protection state")
        if controller_record.aggregate_quantity != execution.position.raw_quantity:
            raise ValueError("controller/execution quantity does not agree")
        if (
            protection_record.expected_controller_head_ordinal
            != controller_record.currentness_head_ordinal
        ):
            raise ValueError("protection/controller head does not agree")
        if (
            selected.application_generation_id != request.application_generation_id
            or selected.execution_profile_id != request.execution_profile_id
            or selected.symbol != position_scope.symbol_id
            or controller_record.application_generation_id
            != request.application_generation_id
            or controller_record.execution_profile_id != request.execution_profile_id
            or protection_record.scope_id != owners.scope_id
            or venue_scope.broker != position_scope.broker
            or venue_scope.environment != position_scope.environment
            or venue_scope.account != position_scope.account
        ):
            raise ValueError("selected scope coordinates do not agree with owners")

        if controller_record.live_acquisition_generation_id is None:
            if acquisition is not None:
                raise ValueError("dormant acquisition cannot retain a serving owner")
            acquisition_wire, acquisition_source_commitment = (
                _encode_dormant_acquisition(
                    selection_proof._selection,
                    controller_record,
                    position_scope,
                    selection_proof._binding,
                )
            )
        else:
            if type(acquisition) is not _acquisition.AcquisitionControllerState:
                raise TypeError(
                    "active acquisition owner must be exact AcquisitionControllerState"
                )
            if not _acquisition._controller_state_is_authentic(acquisition):
                raise ValueError("acquisition owner is not authentic")
            if (
                acquisition.application_generation_id
                != request.application_generation_id
                or acquisition.position_scope != position_scope
                or acquisition._controller.live_generation_id
                != controller_record.live_acquisition_generation_id
                or acquisition.scope_execution_commitment != execution.commitment
                or acquisition.venue_commitment != venue._protection_commitment
            ):
                raise ValueError("active acquisition owner is spliced")
            acquisition_wire, _ = _encode_runtime_checkpoint_acquisition(
                acquisition, selection_proof._selection, owners.scope_id
            )
            acquisition_source_commitment = acquisition.commitment
        execution_wire = _encode_m2_execution_state_component(execution_state)
        active_protection_coordinates = (
            protection_record.active_stream_generation_id,
            protection_record.active_acquisition_generation_id,
            protection_record.active_generation_mandate_commitment_sha256,
            protection_record.active_source_profile_id,
            protection_record.active_session_id,
            protection_record.active_sequence_mode,
        )
        if all(value is None for value in active_protection_coordinates):
            if protection is not None:
                raise ValueError("dormant protection cannot retain a serving owner")
            protection_wire, protection_source_commitment = _encode_dormant_protection(
                protection_record, selection_proof._binding
            )
        else:
            if any(value is None for value in active_protection_coordinates):
                raise ValueError("active protection coordinates are partial")
            if type(protection) is not _protection.PositionProtectionState:
                raise TypeError(
                    "active protection owner must be exact PositionProtectionState"
                )
            if not _protection._state_is_authentic(protection):
                raise ValueError("protection owner is not authentic")
            if (
                protection.mandate.position_scope != position_scope
                or protection.raw_quantity != execution.position.raw_quantity
                or protection.execution_commitment != execution.commitment
                or protection.commitment.hex()
                != protection_record.state_commitment_sha256
            ):
                raise ValueError("active protection owner is spliced")
            checkpoint = _protection._M2ProtectionCheckpoint(
                protection.policy,
                protection.mandate,
                protection.raw_quantity,
                protection.execution_commitment,
                protection.formula_available,
                protection.armed_hard_bail_trigger,
                protection.activation_price,
                protection.high_watermark,
                protection.trail,
                protection.waiting_buy_resolution,
                protection.commitment,
                protection._cursor_ordinal,
                protection._cursor_head,
                protection._market_occurrence_epoch,
                protection._market_committed_epoch,
                protection._market_expected_epoch,
                protection._market_source_sequence,
                protection._market_source_time,
                protection._market_evaluation_time,
                protection._market_occurrence_identity,
                protection._market_halted,
                protection._market_baseline_required,
                protection._market_exhausted,
                protection._market_last_primary,
                protection._hard_bid_identity,
                protection._hard_bid_source_time,
                protection._trade_identity,
                protection._trade_source_time,
                protection._trail_bid_identity,
                protection._trail_bid_source_time,
                protection._exit_provenance,
            )
            protection_wire = _encode_m2_protection_checkpoint_component(checkpoint)
            protection_source_commitment = protection.commitment
        scope_wires.append(
            (
                owners.scope_id,
                _operations._encode_m2_position_scope(position_scope),
                acquisition_wire,
                execution_wire,
                protection_wire,
            )
        )
        owner_commitments.append(
            (
                owners.scope_id,
                acquisition_source_commitment,
                execution.commitment,
                protection_source_commitment,
            )
        )

    return _issue_projected_runtime_checkpoint(
        selection_proof_binding=selection_proof._binding,
        application_generation_id=request.application_generation_id,
        execution_profile_id=request.execution_profile_id,
        market_source_profile_id=request.market_source_profile_id,
        currentness_head_ordinal=selection_proof.target_currentness_head_ordinal,
        checkpoint_version_ordinal=selection_proof.target_checkpoint_version_ordinal,
        venue_wire=venue_wire,
        authority_wire=authority_wire,
        scope_wires=tuple(scope_wires),
        venue_owner_commitment=venue_source_owner_commitment,
        authority_owner_commitment=authority_commitment,
        scope_owner_commitments=tuple(owner_commitments),
    )


def encode_runtime_checkpoint(envelope: RuntimeCheckpointEnvelope) -> bytes:
    """Return exact canonical bytes only for one registered inert envelope."""

    if type(envelope) is not RuntimeCheckpointEnvelope:
        raise TypeError("envelope must be exact RuntimeCheckpointEnvelope")
    if not _envelope_is_authentic(envelope):
        raise ValueError("runtime checkpoint envelope is not authentic")
    return envelope.canonical_payload_bytes


def _encode_m2_protection_policy(value: object) -> list[str]:
    """Encode the checkpoint-owned protection policy without a generic enum path."""

    if type(value) is not _protection.ProtectionPolicy:
        raise TypeError("protection policy must be exact ProtectionPolicy")
    return ["m2.protection.ProtectionPolicy", value.value]


def _decode_m2_protection_policy(value: object) -> _protection.ProtectionPolicy:
    """Decode one exact checkpoint-owned policy enum pair."""

    if type(value) is not list or len(value) != 2:
        raise ValueError("protection policy must be a two-member array")
    owner_tag, member = value
    if owner_tag != "m2.protection.ProtectionPolicy" or type(member) is not str:
        raise ValueError("protection policy tag is not admitted")
    try:
        decoded = _protection.ProtectionPolicy(member)
    except ValueError as error:
        raise ValueError("protection policy value is not admitted") from error
    if _encode_m2_protection_policy(decoded) != value:
        raise ValueError("protection policy is not canonical")
    return decoded


def _encode_m2_optional_m1_value(value: object) -> list[object] | None:
    """Encode one explicitly optional owned M1 value for a fixed field."""

    return (
        None
        if value is None
        else _operations._encode_m2_m1_atom(_cast(_durable_codec._OwningValue, value))
    )


def _decode_m2_optional_m1_value(
    name: str,
    value: object,
    expected: type[_M1ValueT],
) -> _M1ValueT | None:
    """Decode one explicitly optional owned M1 value for a fixed field."""

    return _operations._decode_m2_optional_m1_as(name, value, expected)


def _decode_m2_optional_exact_int(name: str, value: object) -> int | None:
    """Decode one explicitly optional exact integer checkpoint field."""

    if value is None:
        return None
    return _operations._require_exact_int(name, value)


def _decode_m2_exact_bool(name: str, value: object) -> bool:
    """Decode one exact Boolean checkpoint field."""

    if type(value) is not bool:
        raise TypeError(f"{name} must be exact bool")
    return value


def _encode_m2_basis_authority(value: object) -> list[str]:
    """Encode the closed M2 execution basis-authority enum."""

    if type(value) is not _position.BasisAuthority:
        raise TypeError("basis authority must be exact BasisAuthority")
    return ["m2.position.BasisAuthority", value.value]


def _decode_m2_basis_authority(value: object) -> _position.BasisAuthority:
    """Decode one exact M2 execution basis-authority enum pair."""

    if type(value) is not list or len(value) != 2:
        raise ValueError("basis authority must be a two-member array")
    owner_tag, member = value
    if owner_tag != "m2.position.BasisAuthority" or type(member) is not str:
        raise ValueError("basis authority tag is not admitted")
    try:
        decoded = _position.BasisAuthority(member)
    except ValueError as error:
        raise ValueError("basis authority value is not admitted") from error
    if _encode_m2_basis_authority(decoded) != value:
        raise ValueError("basis authority is not canonical")
    return decoded


def _encode_m2_position_integrity(value: object) -> list[object]:
    """Encode the exact closed bit set for one M2 execution state."""

    if type(value) is not _position.PositionIntegrity:
        raise TypeError("position integrity must be exact PositionIntegrity")
    return ["m2.position.PositionIntegrity", value.value]


def _decode_m2_position_integrity(value: object) -> _position.PositionIntegrity:
    """Decode one exact closed M2 position-integrity enum pair."""

    if type(value) is not list or len(value) != 2:
        raise ValueError("position integrity must be a two-member array")
    owner_tag, member = value
    if owner_tag != "m2.position.PositionIntegrity" or type(member) is not int:
        raise ValueError("position integrity tag is not admitted")
    try:
        decoded = _position.PositionIntegrity(member)
    except ValueError as error:
        raise ValueError("position integrity value is not admitted") from error
    if _encode_m2_position_integrity(decoded) != value:
        raise ValueError("position integrity is not canonical")
    return decoded


def _encode_m2_optional_exact_basis(
    value: _values.ExactBasis | None,
) -> list[object] | None:
    """Encode one explicitly optional exact long-basis value."""

    if value is None:
        return None
    if type(value) is not _values.ExactBasis:
        raise TypeError("cost basis must be exact ExactBasis")
    return _operations._encode_m2_fraction(value.value)


def _decode_m2_optional_exact_basis(value: object) -> _values.ExactBasis | None:
    """Decode one explicitly optional exact long-basis value."""

    if value is None:
        return None
    return _values.ExactBasis(_operations._decode_m2_fraction(value))


def _encode_m2_tail_fold_input(value: object) -> list[object]:
    """Encode the exact bounded predecessor proof for one tail fold."""

    if type(value) is not _position.FoldInput:
        raise TypeError("tail fold input must be exact FoldInput")
    if not value.is_bound:
        raise ValueError("tail fold input must carry a bound predecessor proof")
    return [
        _M2_TAIL_FOLD_INPUT_TAG,
        value.raw_quantity,
        _operations._encode_m2_fraction(value.cost_basis.value),
        _encode_m2_optional_m1_value(value.price_metadata),
        (
            None
            if value.position_scope is None
            else _operations._encode_m2_position_scope(value.position_scope)
        ),
        _encode_m2_optional_m1_value(value.tail_root_key),
        value.prefix_count,
        _operations._encode_m2_bytes(value.prefix_heads_commitment),
    ]


def _decode_m2_tail_fold_input(value: object) -> _position.FoldInput:
    """Decode and re-encode one exact bounded tail-fold predecessor proof."""

    fields = _operations._require_m2_aggregate(value, _M2_TAIL_FOLD_INPUT_TAG, 7)
    scope = (
        None if fields[3] is None else _operations._decode_m2_position_scope(fields[3])
    )
    decoded = _position.FoldInput(
        _operations._require_exact_int("tail fold raw quantity", fields[0]),
        _values.ExactBasis(_operations._decode_m2_fraction(fields[1])),
        _decode_m2_optional_m1_value(
            "tail fold price metadata",
            fields[2],
            _values.ReportedPrice,
        ),
        scope,
        _decode_m2_optional_m1_value(
            "tail fold root key",
            fields[4],
            _identity.RootFillKey,
        ),
        _operations._require_exact_int("tail fold prefix count", fields[5]),
        _operations._decode_m2_bytes("tail fold prefix commitment", fields[6]),
    )
    if not decoded.is_bound:
        raise ValueError("tail fold input must carry a bound predecessor proof")
    if _encode_m2_tail_fold_input(decoded) != value:
        raise ValueError("tail fold input is not canonical")
    return decoded


def _encode_m2_execution_state_component(state: object) -> list[object]:
    """Encode every bounded execution-state member in frozen field order."""

    if type(state) is not _position._M2ExecutionState:
        raise TypeError("state must be exact _M2ExecutionState")
    if not _position._m2_execution_state_is_authentic(state):
        raise ValueError("execution state is not authentic")
    return [
        _M2_EXECUTION_STATE_TAG,
        _operations._encode_m2_position_scope(state.scope),
        state.raw_quantity,
        _encode_m2_basis_authority(state.basis_authority),
        _encode_m2_optional_exact_basis(state.cost_basis),
        _encode_m2_optional_m1_value(state.basis_price_metadata),
        None
        if state.tail_fold_input is None
        else _encode_m2_tail_fold_input(state.tail_fold_input),
        _encode_m2_position_integrity(state.integrity_floor),
        _encode_m2_position_integrity(state.integrity),
        state.account_reconciliation_required,
        state.reconciliation_transition_count,
        _operations._encode_m2_bytes(state.reconciliation_transition_head),
        state.root_count,
        _operations._encode_m2_bytes(state.root_order_commitment),
        _operations._encode_m2_bytes(state.head_ids_commitment),
        _operations._encode_m2_bytes(state.root_heads_commitment),
        _operations._encode_m2_bytes(state.seen_facts_commitment),
        _operations._encode_m2_bytes(state.root_head_map_commitment),
        _operations._encode_m2_bytes(state.seen_fact_map_commitment),
        _operations._encode_m2_bytes(state.root_claim_map_commitment),
        _operations._encode_m2_bytes(state.commitment),
    ]


def _decode_m2_execution_state_component(
    value: object,
    proof: _position._M2ExecutionObservationProof,
) -> _position._M2ExecutionState:
    """Decode only through the owner's aggregate-bound direct-proof seam."""

    fields = _operations._require_m2_aggregate(value, _M2_EXECUTION_STATE_TAG, 20)
    decoded_fields = (
        _operations._decode_m2_position_scope(fields[0]),
        _operations._require_exact_int("execution state raw quantity", fields[1]),
        _decode_m2_basis_authority(fields[2]),
        _decode_m2_optional_exact_basis(fields[3]),
        _decode_m2_optional_m1_value(
            "execution state basis price metadata", fields[4], _values.ReportedPrice
        ),
        None if fields[5] is None else _decode_m2_tail_fold_input(fields[5]),
        _decode_m2_position_integrity(fields[6]),
        _decode_m2_position_integrity(fields[7]),
        _decode_m2_exact_bool("execution state reconciliation required", fields[8]),
        _operations._require_exact_int(
            "execution state reconciliation transition count", fields[9]
        ),
        _operations._decode_m2_bytes(
            "execution state reconciliation transition head", fields[10]
        ),
        _operations._require_exact_int("execution state root count", fields[11]),
        _operations._decode_m2_bytes(
            "execution state root order commitment", fields[12]
        ),
        _operations._decode_m2_bytes("execution state head ids commitment", fields[13]),
        _operations._decode_m2_bytes(
            "execution state root heads commitment", fields[14]
        ),
        _operations._decode_m2_bytes(
            "execution state seen facts commitment", fields[15]
        ),
        _operations._decode_m2_bytes(
            "execution state root head map commitment", fields[16]
        ),
        _operations._decode_m2_bytes(
            "execution state seen fact map commitment", fields[17]
        ),
        _operations._decode_m2_bytes(
            "execution state root claim map commitment", fields[18]
        ),
    )
    decoded = _position._m2_execution_state_from_direct_proof(decoded_fields, proof)
    retained_commitment = _operations._decode_m2_bytes(
        "execution state commitment", fields[19]
    )
    if retained_commitment != decoded.commitment:
        raise ValueError("execution state is not authentic")
    if _encode_m2_execution_state_component(decoded) != value:
        raise ValueError("execution state component is not canonical")
    return decoded


def _encode_m2_protection_checkpoint_component(
    checkpoint: object,
) -> list[object]:
    """Encode every fixed protection checkpoint member in frozen field order."""

    if type(checkpoint) is not _protection._M2ProtectionCheckpoint:
        raise TypeError("checkpoint must be exact _M2ProtectionCheckpoint")
    if not _protection._m2_protection_checkpoint_is_authentic(checkpoint):
        raise ValueError("protection checkpoint is not authentic")
    return [
        _M2_PROTECTION_CHECKPOINT_TAG,
        _encode_m2_protection_policy(checkpoint.policy),
        _operations._encode_m2_protection_mandate(checkpoint.mandate),
        checkpoint.raw_quantity,
        _operations._encode_m2_bytes(checkpoint.execution_commitment),
        checkpoint.formula_available,
        _encode_m2_optional_m1_value(checkpoint.armed_hard_bail_trigger),
        _encode_m2_optional_m1_value(checkpoint.activation_price),
        _encode_m2_optional_m1_value(checkpoint.high_watermark),
        _encode_m2_optional_m1_value(checkpoint.trail),
        checkpoint.waiting_buy_resolution,
        _operations._encode_m2_bytes(checkpoint.commitment),
        checkpoint.cursor_ordinal,
        _operations._encode_m2_bytes(checkpoint.cursor_head),
        checkpoint.market_occurrence_epoch,
        checkpoint.market_committed_epoch,
        checkpoint.market_expected_epoch,
        checkpoint.market_source_sequence,
        checkpoint.market_source_time,
        checkpoint.market_evaluation_time,
        _encode_m2_optional_m1_value(checkpoint.market_occurrence_identity),
        checkpoint.market_halted,
        checkpoint.market_baseline_required,
        checkpoint.market_exhausted,
        _encode_m2_optional_m1_value(checkpoint.market_last_primary),
        _encode_m2_optional_m1_value(checkpoint.hard_bid_identity),
        checkpoint.hard_bid_source_time,
        _encode_m2_optional_m1_value(checkpoint.trade_identity),
        checkpoint.trade_source_time,
        _encode_m2_optional_m1_value(checkpoint.trail_bid_identity),
        checkpoint.trail_bid_source_time,
        _operations._encode_m2_bytes(checkpoint.exit_provenance),
    ]


def _decode_m2_protection_checkpoint_component(
    value: object,
) -> _protection._M2ProtectionCheckpoint:
    """Decode and re-encode one exact fixed protection checkpoint component."""

    fields = _operations._require_m2_aggregate(
        value,
        _M2_PROTECTION_CHECKPOINT_TAG,
        31,
    )
    formula_available = _decode_m2_exact_bool(
        "protection checkpoint formula availability", fields[4]
    )
    waiting_buy_resolution = _decode_m2_exact_bool(
        "protection checkpoint waiting-buy resolution", fields[9]
    )
    market_halted = _decode_m2_exact_bool(
        "protection checkpoint market halted", fields[20]
    )
    market_baseline_required = _decode_m2_exact_bool(
        "protection checkpoint market baseline required", fields[21]
    )
    market_exhausted = _decode_m2_exact_bool(
        "protection checkpoint market exhausted", fields[22]
    )
    decoded = _protection._M2ProtectionCheckpoint(
        _decode_m2_protection_policy(fields[0]),
        _operations._decode_m2_protection_mandate(fields[1]),
        _operations._require_exact_int("protection checkpoint raw quantity", fields[2]),
        _operations._decode_m2_bytes(
            "protection checkpoint execution commitment", fields[3]
        ),
        formula_available,
        _decode_m2_optional_m1_value(
            "protection checkpoint armed trigger",
            fields[5],
            _values.ReportedPrice,
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint activation price",
            fields[6],
            _values.ReportedPrice,
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint high watermark",
            fields[7],
            _values.ReportedPrice,
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint trail",
            fields[8],
            _values.ReportedPrice,
        ),
        waiting_buy_resolution,
        _operations._decode_m2_bytes("protection checkpoint commitment", fields[10]),
        _operations._require_exact_int(
            "protection checkpoint cursor ordinal", fields[11]
        ),
        _operations._decode_m2_bytes("protection checkpoint cursor head", fields[12]),
        _decode_m2_optional_exact_int(
            "protection checkpoint occurrence epoch", fields[13]
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint committed epoch", fields[14]
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint expected epoch", fields[15]
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint source sequence", fields[16]
        ),
        _decode_m2_optional_exact_int("protection checkpoint source time", fields[17]),
        _decode_m2_optional_exact_int(
            "protection checkpoint evaluation time", fields[18]
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint occurrence identity",
            fields[19],
            _identity.MarketOccurrenceId,
        ),
        market_halted,
        market_baseline_required,
        market_exhausted,
        _decode_m2_optional_m1_value(
            "protection checkpoint last primary",
            fields[23],
            _values.ReportedPrice,
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint hard bid identity",
            fields[24],
            _identity.MarketOccurrenceId,
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint hard bid time", fields[25]
        ),
        _decode_m2_optional_m1_value(
            "protection checkpoint trade identity",
            fields[26],
            _identity.MarketOccurrenceId,
        ),
        _decode_m2_optional_exact_int("protection checkpoint trade time", fields[27]),
        _decode_m2_optional_m1_value(
            "protection checkpoint trail bid identity",
            fields[28],
            _identity.MarketOccurrenceId,
        ),
        _decode_m2_optional_exact_int(
            "protection checkpoint trail bid time", fields[29]
        ),
        _operations._decode_m2_bytes(
            "protection checkpoint exit provenance", fields[30]
        ),
    )
    if not _protection._m2_protection_checkpoint_is_authentic(decoded):
        raise ValueError("protection checkpoint is not authentic")
    if _encode_m2_protection_checkpoint_component(decoded) != value:
        raise ValueError("protection checkpoint component is not canonical")
    return decoded


def _m2_protection_authority_proof_from_current_proof(
    checkpoint: _protection._M2ProtectionCheckpoint,
    current_proof: _records.CurrentProofSlice,
) -> _protection._M2ProtectionAuthorityProof:
    """Issue protection authority only from one sealed repository current proof."""

    if type(checkpoint) is not _protection._M2ProtectionCheckpoint:
        raise TypeError("checkpoint must be exact _M2ProtectionCheckpoint")
    if type(current_proof) is not _records.CurrentProofSlice:
        raise TypeError("current_proof must be exact CurrentProofSlice")
    if not _records.CurrentProofSlice._is_authentic(current_proof):
        raise ValueError("current_proof is not repository-authentic")
    authority = current_proof.protection_authority
    stream = current_proof.market_stream_authority
    if (
        type(stream) is not _records.MarketStreamAuthorityRecord
        or type(authority.active_stream_generation_id)
        is not _identity.MarketStreamGenerationId
        or type(authority.active_acquisition_generation_id)
        is not _identity.AcquisitionGenerationId
        or type(authority.active_generation_mandate_commitment_sha256) is not str
        or type(authority.active_source_profile_id) is not str
        or type(authority.active_session_id) is not _identity.SessionId
        or type(authority.active_sequence_mode) is not str
    ):
        raise ValueError("current_proof has no complete active protection authority")
    return _protection._m2_issue_protection_authority_proof(
        _protection._M2ProtectionAuthorityProof,
        current_proof.application_generation.application_generation_id,
        current_proof.execution_profile.connection_profile_id,
        current_proof.market_source_profile.market_source_profile_id,
        current_proof.scope.scope_id,
        checkpoint.mandate.position_scope,
        current_proof.symbol_controller.currentness_head_ordinal,
        current_proof.symbol_controller.live_acquisition_generation_id,
        authority.authority_class,
        authority.active_stream_generation_id,
        authority.active_acquisition_generation_id,
        authority.active_generation_mandate_commitment_sha256,
        authority.active_source_profile_id,
        authority.active_session_id,
        _protection.MarketSequenceMode(authority.active_sequence_mode),
        authority.expected_controller_head_ordinal,
        authority.state_commitment_sha256,
        authority.version_ordinal,
        checkpoint.mandate.evidence_policy.source_id,
    )


__all__ = (
    "InertRuntimeCheckpointComponent",
    "RuntimeCheckpointEnvelope",
    "RuntimeCheckpointScopeCandidate",
    "encode_runtime_checkpoint",
)
