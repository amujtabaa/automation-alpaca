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
from .. import recovery as _recovery
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


def _require_exact_signed_int(name: str, value: object) -> int:
    """Admit a signed wire integer while refusing the ``bool`` subclass of ``int``."""

    if type(value) is not int:
        raise TypeError(f"{name} must be exact int")
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
    "m1.authority.BrokerEffectRequest/v1": 11,
    "m1.acquisition.AcquisitionMandate/v1": 15,
    "m1.authority.AcquisitionEffectTerms/v1": 5,
    "m1.authority.AdvanceManualFlatten/v1": 3,
    "m1.authority.ClaimBrokerQuery/v1": 5,
    "m1.authority.ClaimEffect/v1": 4,
    "m1.authority.CreateBrokerEffect/v1": 6,
    "m1.authority.EngageKill/v1": 5,
    "m1.fills.ExecutionScope/v1": 7,
    "m1.fills.PositionScope/v1": 5,
    "m1.protection.EvidencePolicy/v1": 7,
    "m1.protection.ExecutionGuard/v1": 3,
    "m1.protection.MarketOccurrence/v1": 16,
    "m1.protection.ProtectionMandate/v1": 17,
    "m1.recovery.IngestHumanAttestedFill/v1": 4,
    "m1.recovery.RecordBrokerFillEvidence/v1": 10,
    "m1.recovery.ReleaseVenueLeg/v1": 12,
    "m1.venue.DiscoverVenueLeg/v1": 5,
    "m1.venue.ObserveVenueStatus/v1": 8,
    "m1.venue.RecordTransportOutcome/v1": 4,
    "m1.venue.RecoverClaimedEffect/v1": 3,
    "m1.fills.BrokerFillFact/v1": 6,
    "m1.fills.BrokerTradeCorrectFact/v1": 7,
    "m1.fills.BrokerTradeBustFact/v1": 6,
    "m1.fills.HumanAttestedFillFact/v1": 14,
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
    _M2_TAIL_FOLD_INPUT_TAG: 8,
}

_CHECKPOINT_ENUM_OWNERS = {
    "m1.authority.EnginePhase",
    "m1.authority.TradingMode",
    "m1.authority.SupervisorFence",
    "m1.authority.FlattenPhase",
    "m1.authority.AcquisitionCurrentnessSourceKind",
    # Nested inside AcquisitionEffectTerms, which reaches a checkpoint row only
    # through an acquisition effect permit. The other owners _encode_m2_enum can
    # emit -- AuthorityQueryKind, MarketKind, OperationDomain -- belong to query
    # claims, market records, and the operations envelope, none of which a
    # checkpoint row carries, so admitting them here would widen the wire for
    # nothing.
    "m1.authority.AcquisitionOrderType",
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
        if len(value) != 3 or type(value[1]) is not str or type(value[2]) is not list:
            raise ValueError("checkpoint durable atom has the wrong exact shape")
        for field in value[2]:
            # mirrors _encode_m2_durable_atom exactly: a field is text or one nested
            # atom. Requiring text alone refused every composite value, and therefore
            # every execution state carrying a price.
            if type(field) is str:
                continue
            if type(field) is not list or not field or field[0] != "1":
                raise ValueError("checkpoint durable atom has the wrong exact shape")
            _validate_checkpoint_nested_value(field)
        return
    if tag in _CHECKPOINT_ENUM_OWNERS:
        if len(value) != 2 or type(value[1]) is not str:
            raise ValueError(f"{tag} enum has the wrong exact shape")
        return
    if tag in _CHECKPOINT_COLLECTION_TAGS:
        _validate_checkpoint_collection(value, tag)
        return
    component_length = _COMPONENT_MEMBER_COUNTS.get(tag)
    if component_length is not None:
        if len(value) != component_length:
            raise ValueError(f"{tag} has the wrong exact shape")
        _validate_component_wire(tag, value)
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
        b"execution-core/m2-authority/checkpoint/v1", value[:13]
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
    _validate_component_wire(actual_tag, value)
    canonical = _encode_canonical_json(value)
    if len(canonical) > _MAX_RUNTIME_CHECKPOINT_COMPONENT_BYTES:
        raise OverflowError("checkpoint component exceeds its byte limit")
    return _issue_component(actual_tag, canonical)


def _validate_component_wire(actual_tag: str, value: list[object]) -> None:
    """Validate one component body by its own exact validator.

    A component nested inside a row is still a component: the generic nested-row walk
    cannot check it, so both the top-level decode path and nested members route here.
    """

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


_ORDER_OCTET_ATOM = 0x06
_ORDER_OCTET_ARRAY = 0x08


def _order_component(octet: int, value: object) -> bytes:
    """Contract 2.4 ``order_component``: type octet, u64-be length, canonical JSON.

    Collections are ordered by these bytes, never by Python comparison, repr, locale
    collation, implicit text conversion, or a digest surrogate. The length frame is
    load-bearing: it is what makes the ordering injective across nested shapes, and it
    reorders keys that a plain string comparison would sort differently.
    """

    canonical = _json.dumps(
        value, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")
    return bytes((octet,)) + _struct_pack(">Q", len(canonical)) + canonical


def _atom_order_key(value: _durable_codec._OwningValue) -> bytes:
    """Canonical order key for one ``A`` durable-atom collection member."""

    return _order_component(_ORDER_OCTET_ATOM, _operations._encode_m2_m1_atom(value))


def _array_order_key(wire: list[object]) -> bytes:
    """Canonical order key for one fully tagged fixed-array collection member."""

    return _order_component(_ORDER_OCTET_ARRAY, wire)


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


def _encode_runtime_checkpoint_venue_execution_checkpoint(
    checkpoint: _venue.VenueExecutionCheckpoint,
) -> list[object]:
    """Encode the frozen 10-member venue execution checkpoint."""

    if type(checkpoint) is not _venue.VenueExecutionCheckpoint:
        raise TypeError("execution checkpoint must be exact VenueExecutionCheckpoint")
    return [
        "m2.venue.ExecutionCheckpoint/v1",
        _operations._encode_m2_position_scope(checkpoint.position_scope),
        _require_nonnegative_int("registry count", checkpoint.registry_count),
        _operations._encode_m2_bytes(checkpoint.registry_commitment),
        _operations._encode_m2_bytes(checkpoint.position_commitment),
        _operations._encode_m2_bytes(checkpoint.root_heads_commitment),
        _require_nonnegative_int("integrity bits", checkpoint.integrity_bits),
        checkpoint.account_reconciliation_required,
        _require_nonnegative_int(
            "reconciliation transition count",
            checkpoint.reconciliation_transition_count,
        ),
        _operations._encode_m2_bytes(checkpoint.reconciliation_transition_head),
    ]


def _selected_position_scopes_from_selection(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> tuple[_fills.PositionScope, ...]:
    """Derive the exact selected position scopes from the repository selection."""

    return tuple(
        _fills.PositionScope(
            book.scope.broker, book.scope.environment, book.scope.account, record.symbol
        )
        for record in selection.scopes
    )


def _encode_runtime_checkpoint_venue_execution_scope_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the current execution snapshot of each proof-selected scope.

    ``_execution_snapshot_by_scope`` is an exact current selected-scope map, so a key
    outside the selection fails closed. The nested checkpoint is re-derived from the
    same snapshot through ``VenueExecutionCheckpoint.from_execution`` rather than
    carried independently, so it cannot disagree with the state beside it.
    """

    rows: list[object] = []
    reached = 0
    for position_scope in _selected_position_scopes_from_selection(book, selection):
        snapshot = book._execution_snapshot_by_scope.get(
            _venue._position_scope_index_key(position_scope)
        )
        if snapshot is None:
            continue
        if snapshot.position.scope != position_scope:
            raise ValueError(
                "reached execution snapshot does not own its selected scope"
            )
        reached += 1
        execution_state = _position._m2_execution_state_from_snapshot(snapshot)
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.ExecutionScopeCurrent/v1",
                    _encode_m2_execution_state_component(execution_state),
                    _encode_runtime_checkpoint_venue_execution_checkpoint(
                        _venue.VenueExecutionCheckpoint.from_execution(snapshot)
                    ),
                ]
            )
        )
    if book._execution_snapshot_by_scope.size != reached:
        raise ValueError(
            "execution snapshot map retains a key outside the selected scope set"
        )
    return _checkpoint_collection("m2.venue.ExecutionScopes/v1", rows)


def _encode_runtime_checkpoint_venue_authority_epoch_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the authority epoch of each proof-selected scope."""

    rows: list[object] = []
    reached = 0
    for position_scope in _selected_position_scopes_from_selection(book, selection):
        epoch = book._authority_epoch_by_scope.get(
            _venue._position_scope_index_key(position_scope)
        )
        if epoch is None:
            continue
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.AuthorityEpoch/v1",
                    _operations._encode_m2_position_scope(position_scope),
                    _require_nonnegative_int("authority epoch", epoch),
                ]
            )
        )
    if book._authority_epoch_by_scope.size != reached:
        raise ValueError(
            "authority epoch map retains a key outside the selected scope set"
        )
    return _checkpoint_collection("m2.venue.AuthorityEpochs/v1", rows)


def _selected_leg_keys_from_selection(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> tuple[_identity.VenueLegKey, ...]:
    """Derive the exact selected venue leg identities from the repository selection."""

    return tuple(
        _identity.VenueLegKey(
            book.scope.broker,
            book.scope.environment,
            book.scope.account,
            record.owner_id,
        )
        for record in selection.owners
    )


def _encode_runtime_checkpoint_venue_high_water_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the economic high water of each proof-selected owner leg."""

    rows: list[object] = []
    reached = 0
    for leg_key in _selected_leg_keys_from_selection(book, selection):
        high_water = book._economic_high_water_by_leg.get(
            _venue._leg_index_key(leg_key)
        )
        if high_water is None:
            continue
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.EconomicHighWater/v1",
                    _operations._encode_m2_m1_atom(leg_key),
                    _require_nonnegative_int("economic high water", high_water),
                ]
            )
        )
    # No whole-map cardinality check. _PersistentKeyMap has get/insert_new/
    # replace_existing and no deletion of any kind, so this index is monotonic,
    # while the repository selects only effects with disposition IN
    # ('OPEN','INVALIDATED') plus CLOSED effects carrying a late-admitted owner.
    # One ordinary closed effect therefore leaves a permanently unselected entry
    # behind, and comparing size against the reached count refused every book
    # from that point on. R15 section 2 omits such rows as audit history.
    return _checkpoint_collection("m2.venue.EconomicHighWaters/v1", rows)


def _encode_runtime_checkpoint_venue_owner_attempt_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project each proof-selected owner leg with its current attempt.

    This family reads two owner maps at one key: ``_owner_by_leg`` supplies the leg,
    effect and observation identities, and ``_leg_current_by_leg`` supplies the
    optional current attempt. Member 1 is the R18 dense ``checkpoint_ordinal`` over the
    proof-selected owner set, exactly as the effect family does.
    """

    atom = _operations._encode_m2_m1_atom
    relations = _selected_venue_relations(selection)
    rows: list[object] = []
    reached = 0
    for ordinal, (leg_key, owner_record) in enumerate(
        zip(_selected_leg_keys_from_selection(book, selection), selection.owners)
    ):
        leg_index = _venue._leg_index_key(leg_key)
        owner = book._owner_by_leg.get(leg_index)
        if owner is None:
            raise ValueError("selected owner leg has no current owner row")
        effect, _position_scope = _require_selected_owner_relation(
            book, relations, owner, owner_record, "owner"
        )
        reached += 1
        current = book._leg_current_by_leg.get(leg_index)
        attempt = None if current is None else current.attempt
        attempt_row: list[object] | None = None
        if attempt is not None:
            if attempt.leg_key != leg_key:
                raise ValueError("reached attempt does not own its selected leg")
            attempt_row = [
                "m2.venue.Attempt/v1",
                atom(attempt.leg_key),
                _checkpoint_enum("m1.venue.VenueAttemptState", attempt.status),
                (
                    None
                    if attempt.pending_operation is None
                    else _checkpoint_enum(
                        "m1.venue.PendingVenueOperation", attempt.pending_operation
                    )
                ),
                atom(attempt.cumulative_quantity),
                atom(attempt.last_observation_id),
            ]
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.OwnerAttempt/v1",
                    ordinal,
                    atom(leg_key),
                    atom(effect.effect_external),
                    atom(owner.observation_id),
                    attempt_row,
                ]
            )
        )
    # No whole-map cardinality check. _PersistentKeyMap has get/insert_new/
    # replace_existing and no deletion of any kind, so this index is monotonic,
    # while the repository selects only effects with disposition IN
    # ('OPEN','INVALIDATED') plus CLOSED effects carrying a late-admitted owner.
    # One ordinary closed effect therefore leaves a permanently unselected entry
    # behind, and comparing size against the reached count refused every book
    # from that point on. R15 section 2 omits such rows as audit history.
    return _checkpoint_collection("m2.venue.OwnerAttempts/v1", rows)


def _selected_root_keys_from_selection(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> tuple[_identity.RootFillKey, ...]:
    """Derive the exact selected root-fill identities from the repository selection."""

    return tuple(
        _identity.RootFillKey(
            book.scope.broker,
            book.scope.environment,
            book.scope.account,
            record.root_fill_id,
        )
        for record in selection.roots
    )


@_dataclass(frozen=True, slots=True)
class _SelectedVenueRelations:
    """Direct maps for the complete repository-selected venue relationship.

    The checkpoint may omit unrelated history, but it must never weaken a reached
    row into a few matching scalar IDs.  These maps make the selected proof the
    one authority for every effect, owner, route, root, and scope coordinate.
    """

    scopes_by_id: dict[int, _records.ScopeRecord]
    effects_by_id: dict[int, _records.VenueEffectRecord]
    claims_by_effect_id: dict[int, _records.DispatchClaimRecord]
    acceptance_sets_by_effect_id: dict[int, _records.AcceptanceSetRecord]
    evidence_by_id: dict[int, _records.AcceptanceEvidenceRecord]
    owners_by_id: dict[_identity.OrderId, _records.VenueIdentityOwnerRecord]
    routes_by_root_key_id: dict[int, _records.AcquisitionRootRouteRecord]
    roots_by_key_id: dict[int, _records.RootFillRecord]


def _selected_venue_relations(
    selection: _records._RuntimeCheckpointSelectionSet,
) -> _SelectedVenueRelations:
    """Index selected rows and reject ambiguous keys before any projection."""

    scopes = {record.scope_id: record for record in selection.scopes}
    effects = {record.effect_id: record for record in selection.effects}
    claims = {record.effect_id: record for record in selection.claims}
    acceptance_sets = {record.effect_id: record for record in selection.acceptance_sets}
    evidence = {record.evidence_id: record for record in selection.evidence}
    owners = {record.owner_id: record for record in selection.owners}
    routes = {record.root_fill_key_id: record for record in selection.root_routes}
    roots = {record.root_fill_key_id: record for record in selection.roots}
    for name, indexed, source in (
        ("scope", scopes, selection.scopes),
        ("effect", effects, selection.effects),
        ("dispatch claim", claims, selection.claims),
        ("acceptance set", acceptance_sets, selection.acceptance_sets),
        ("acceptance evidence", evidence, selection.evidence),
        ("owner", owners, selection.owners),
        ("root route", routes, selection.root_routes),
        ("root", roots, selection.roots),
    ):
        if len(indexed) != len(source):
            raise ValueError(f"selected {name} records repeat a key")
    return _SelectedVenueRelations(
        scopes,
        effects,
        claims,
        acceptance_sets,
        evidence,
        owners,
        routes,
        roots,
    )


def _selected_position_scope(
    book: _venue.VenueRecoveryBook,
    scope: _records.ScopeRecord,
) -> _fills.PositionScope:
    return _fills.PositionScope(
        book.scope.broker,
        book.scope.environment,
        book.scope.account,
        scope.symbol,
    )


def _selected_effect_position_scope(
    book: _venue.VenueRecoveryBook,
    relations: _SelectedVenueRelations,
    effect: _records.VenueEffectRecord,
    subject: str,
) -> _fills.PositionScope:
    """Return an effect's selected scope after checking durable coordinates."""

    scope = relations.scopes_by_id.get(effect.scope_id)
    if scope is None:
        raise ValueError(f"selected {subject} references an unselected scope")
    if (
        scope.application_generation_id != effect.application_generation_id
        or scope.execution_profile_id != effect.execution_profile_id
    ):
        raise ValueError(f"selected {subject} effect disagrees with its scope")
    return _selected_position_scope(book, scope)


def _require_selected_effect_scope(
    book: _venue.VenueRecoveryBook,
    relations: _SelectedVenueRelations,
    effect_scope: _venue.VenueEffectScope,
    effect: _records.VenueEffectRecord,
    subject: str,
) -> _fills.PositionScope:
    """Require a runtime effect scope to equal all selected durable coordinates."""

    position_scope = _selected_effect_position_scope(book, relations, effect, subject)
    target_leg_key = (
        None
        if effect.target_order_id is None
        else _identity.VenueLegKey(
            book.scope.broker,
            book.scope.environment,
            book.scope.account,
            effect.target_order_id,
        )
    )
    if (
        effect_scope.generation != effect.application_generation_id
        or effect_scope.position_scope != position_scope
        or effect_scope.effect_id != effect.effect_external
        or effect_scope.request_occurrence_id != effect.request_occurrence_id
        or effect_scope.mandate_id != effect.mandate_id
        or effect_scope.kind.value != effect.effect_kind
        or effect_scope.client_order_id != effect.client_order_id
        or effect_scope.target_leg_key != target_leg_key
        or effect_scope.side.value != effect.side
        or effect_scope.quantity != effect.quantity
        or effect_scope.economic_scope != effect.economic_scope
    ):
        raise ValueError(f"reached {subject} disagrees with its selected effect scope")
    return position_scope


def _require_selected_effect_current_relation(
    book: _venue.VenueRecoveryBook,
    relations: _SelectedVenueRelations,
    current: _venue.BrokerEffect,
    record: _records.VenueEffectRecord,
    subject: str,
) -> _fills.PositionScope:
    """Bind mutable current effect state to its selected durable closure relation.

    Scope equality alone cannot authenticate a current claim or closure proof:
    their lifecycle, claim, and evidence coordinates are selected durable state.
    The evidence *reference* remains payload-owned because no selected durable row
    carries that runtime identifier; its kind and digest remain exact durable ties.
    """

    position_scope = _require_selected_effect_scope(
        book, relations, current.scope, record, subject
    )
    if current.state.value != record.lifecycle_state:
        raise ValueError(f"reached {subject} disagrees with its selected lifecycle")
    if current.acceptance_set_state.value != record.disposition:
        raise ValueError(f"reached {subject} disagrees with its selected disposition")

    selected_claim = relations.claims_by_effect_id.get(record.effect_id)
    if selected_claim is None:
        if current.claim_occurrence_id is not None:
            raise ValueError(f"reached {subject} has an unselected dispatch claim")
    elif (
        selected_claim.execution_profile_id != record.execution_profile_id
        or current.claim_occurrence_id != selected_claim.claim_occurrence_id
    ):
        raise ValueError(
            f"reached {subject} disagrees with its selected dispatch claim"
        )

    closure_proof_evidence_id = record.closure_proof_evidence_id
    closure_values = (
        record.closure_proof_kind,
        record.closure_proof_digest,
        closure_proof_evidence_id,
        record.closure_proof_claim_id,
    )
    if record.disposition == "OPEN":
        if any(value is not None for value in closure_values):
            raise ValueError(f"selected {subject} OPEN closure is not empty")
    elif record.disposition in {"CLOSED", "INVALIDATED"}:
        if any(value is None for value in closure_values[:3]):
            raise ValueError(f"selected {subject} closure is incomplete")
        if (
            record.closure_proof_kind == "NEVER_DISPATCHED"
            and record.closure_proof_claim_id is not None
        ):
            raise ValueError(
                f"selected {subject} never-dispatched closure names a claim"
            )
        if (
            record.closure_proof_kind != "NEVER_DISPATCHED"
            and record.closure_proof_claim_id is None
        ):
            raise ValueError(f"selected {subject} external closure lacks a claim")
    else:
        raise ValueError(f"selected {subject} has an invalid disposition")

    proof = current.acceptance_proof
    if proof is None:
        if any(value is not None for value in closure_values):
            raise ValueError(f"reached {subject} lacks its selected closure proof")
        _require_selected_effect_invalidations(
            book, relations, current, record, subject
        )
        return position_scope
    if (
        record.disposition == "OPEN"
        or record.closure_proof_kind is None
        or record.closure_proof_digest is None
        or closure_proof_evidence_id is None
    ):
        raise ValueError(f"reached {subject} has an unselected effect closure proof")

    proof_kind = getattr(getattr(proof, "kind", None), "value", None)
    proof_digest = getattr(proof, "evidence_digest", None)
    if (
        proof_kind != record.closure_proof_kind
        or type(proof_digest) is not bytes
        or proof_digest.hex() != record.closure_proof_digest
    ):
        raise ValueError(f"reached {subject} disagrees with its selected closure proof")
    evidence = relations.evidence_by_id.get(closure_proof_evidence_id)
    acceptance_set = relations.acceptance_sets_by_effect_id.get(record.effect_id)
    if (
        evidence is None
        or acceptance_set is None
        or acceptance_set.acceptance_set_id != evidence.acceptance_set_id
        or evidence.effect_id != record.effect_id
        or evidence.evidence_kind != "CLOSURE_PROOF"
        or evidence.proof_kind != record.closure_proof_kind
        or evidence.evidence_digest != record.closure_proof_digest
    ):
        raise ValueError(
            f"reached {subject} disagrees with its selected closure evidence"
        )
    if record.closure_proof_kind == "NEVER_DISPATCHED":
        if selected_claim is not None or current.claim_occurrence_id is not None:
            raise ValueError(f"reached {subject} never-dispatched closure has a claim")
        if current.state is not _venue.BrokerEffectState.CANCELED_BEFORE_DISPATCH:
            raise ValueError(
                f"reached {subject} never-dispatched closure requires cancellation"
            )
    elif (
        selected_claim is None
        or selected_claim.claim_id != record.closure_proof_claim_id
        or getattr(proof, "claim_occurrence_id", None)
        != selected_claim.claim_occurrence_id
    ):
        raise ValueError(f"reached {subject} disagrees with its selected closure claim")
    _require_selected_effect_invalidations(book, relations, current, record, subject)
    return position_scope


def _require_selected_owner_relation(
    book: _venue.VenueRecoveryBook,
    relations: _SelectedVenueRelations,
    owner: _venue.VenueIdentityOwner,
    owner_record: _records.VenueIdentityOwnerRecord,
    subject: str,
) -> tuple[_records.VenueEffectRecord, _fills.PositionScope]:
    """Bind one reached owner to its full selected owner/effect/scope relation."""

    effect = relations.effects_by_id.get(owner_record.effect_id)
    if effect is None:
        raise ValueError(f"selected {subject} owner references an unselected effect")
    expected_leg = _identity.VenueLegKey(
        book.scope.broker,
        book.scope.environment,
        book.scope.account,
        owner_record.owner_id,
    )
    if owner.leg_key != expected_leg:
        raise ValueError(f"reached {subject} does not own its selected leg")
    if owner.observation_id != owner_record.observation_id:
        raise ValueError(f"reached {subject} disagrees with its selected observation")
    if (
        owner_record.scope_id != effect.scope_id
        or owner_record.execution_profile_id != effect.execution_profile_id
        or owner_record.owner_generation_id != effect.acquisition_generation_id
    ):
        raise ValueError(f"selected {subject} owner disagrees with its selected effect")
    position_scope = _require_selected_effect_scope(
        book, relations, owner.effect_scope, effect, subject
    )
    return effect, position_scope


def _require_selected_effect_invalidations(
    book: _venue.VenueRecoveryBook,
    relations: _SelectedVenueRelations,
    current: _venue.BrokerEffect,
    record: _records.VenueEffectRecord,
    subject: str,
) -> None:
    """Bind mutable contradiction tuples to selected invalidation evidence.

    An invalidation row names the exact selected owner and observation that
    generated one current contradiction. The row order is the selected durable
    evidence order; the runtime tuple cannot add, remove, or substitute one.
    """

    invalidations = tuple(
        sorted(
            (
                evidence
                for evidence in relations.evidence_by_id.values()
                if (
                    evidence.effect_id == record.effect_id
                    and evidence.evidence_kind == "INVALIDATION"
                )
            ),
            key=lambda evidence: (evidence.evidence_ordinal, evidence.evidence_id),
        )
    )
    contradictions = current.contradiction_evidence
    if record.disposition != "INVALIDATED":
        if invalidations or contradictions:
            raise ValueError(
                f"reached {subject} has invalidation evidence outside INVALIDATED"
            )
        return
    if not invalidations:
        raise ValueError(f"selected {subject} INVALIDATED lacks invalidation evidence")

    acceptance_set = relations.acceptance_sets_by_effect_id.get(record.effect_id)
    expected: list[_venue.AcceptanceContradiction] = []
    for evidence in invalidations:
        owner_id = evidence.contradiction_owner_id
        observation_id = evidence.contradiction_observation_id
        if (
            acceptance_set is None
            or evidence.acceptance_set_id != acceptance_set.acceptance_set_id
            or evidence.proof_kind is not None
            or owner_id is None
            or observation_id is None
        ):
            raise ValueError(
                f"selected {subject} invalidation evidence is structurally incomplete"
            )
        owner_record = relations.owners_by_id.get(owner_id)
        leg_key = _identity.VenueLegKey(
            book.scope.broker,
            book.scope.environment,
            book.scope.account,
            owner_id,
        )
        owner = book._owner_by_leg.get(_venue._leg_index_key(leg_key))
        if owner_record is None or owner is None:
            raise ValueError(
                f"selected {subject} invalidation evidence lacks its selected owner"
            )
        owner_effect, _position_scope = _require_selected_owner_relation(
            book, relations, owner, owner_record, "invalidation evidence"
        )
        if (
            owner_effect.effect_id != record.effect_id
            or owner_record.observation_id != observation_id
        ):
            raise ValueError(
                f"selected {subject} invalidation evidence disagrees with its owner"
            )
        expected.append(_venue.AcceptanceContradiction(leg_key, observation_id))
    if not all(
        type(item) is _venue.AcceptanceContradiction for item in contradictions
    ) or tuple(contradictions) != tuple(expected):
        raise ValueError(
            f"reached {subject} disagrees with selected invalidation evidence"
        )


def _require_selected_route_relation(
    book: _venue.VenueRecoveryBook,
    relations: _SelectedVenueRelations,
    route: _records.AcquisitionRootRouteRecord,
    root: _records.RootFillRecord,
    subject: str,
) -> tuple[
    _records.VenueEffectRecord, _records.VenueIdentityOwnerRecord, _fills.PositionScope
]:
    """Bind a selected route to every selected root, owner, effect, and scope key."""

    effect = relations.effects_by_id.get(route.effect_id)
    owner = relations.owners_by_id.get(route.owner_id)
    scope = relations.scopes_by_id.get(route.scope_id)
    if effect is None or owner is None or scope is None:
        raise ValueError(f"selected {subject} route has an absent selected relation")
    if (
        route.scope_id != root.scope_id
        or route.application_generation_id != root.application_generation_id
        or route.execution_profile_id != root.execution_profile_id
        or route.acquisition_generation_id != root.owner_generation_id
        or route.scope_id != effect.scope_id
        or route.application_generation_id != effect.application_generation_id
        or route.execution_profile_id != effect.execution_profile_id
        or route.acquisition_generation_id != effect.acquisition_generation_id
        or owner.scope_id != route.scope_id
        or owner.execution_profile_id != route.execution_profile_id
        or owner.owner_generation_id != route.acquisition_generation_id
        or owner.effect_id != route.effect_id
        or owner.observation_id != route.observation_id
        or owner.root_fill_key_id != route.root_fill_key_id
        or scope.application_generation_id != route.application_generation_id
        or scope.execution_profile_id != route.execution_profile_id
    ):
        raise ValueError(
            f"selected {subject} route disagrees with its selected relation"
        )
    return effect, owner, _selected_position_scope(book, scope)


def _require_selected_coverage_fact(
    fact: _Any,
    *,
    root_key: _identity.RootFillKey,
    effect: _records.VenueEffectRecord,
    leg_key: _identity.VenueLegKey,
    position_scope: _fills.PositionScope,
    subject: str,
) -> None:
    """Bind an economic fact through the coordinates that its type owns.

    Broker facts intentionally carry no venue-leg or request-occurrence field: those
    belong to their enclosing coverage/reconciliation record and are checked at that
    boundary.  Every admitted fact *does* carry an exact root key and execution
    scope, while human-attested evidence additionally owns the leg and request
    occurrence itself.  Keeping the two layers separate prevents both a fabricated
    attribute check and a weaker bare-root comparison.
    """

    fact_type = type(fact)
    if fact_type not in {
        _fills.BrokerFillFact,
        _fills.BrokerTradeCorrectFact,
        _fills.BrokerTradeBustFact,
        _fills.HumanAttestedFillFact,
    }:
        raise TypeError(f"reached {subject} is not an admitted execution fact")
    if fact.root_key != root_key:
        raise ValueError(f"reached {subject} does not own its selected root")
    if (
        fact.scope.position_scope != position_scope
        or fact.scope.order_id != leg_key.order_id
    ):
        raise ValueError(
            f"reached {subject} disagrees with its selected execution provenance"
        )
    if fact_type is _fills.HumanAttestedFillFact and (
        fact.leg_key != leg_key
        or fact.request_occurrence_id != effect.request_occurrence_id
    ):
        raise ValueError(
            f"reached {subject} disagrees with its selected human provenance"
        )


def _encode_runtime_checkpoint_venue_correlation_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the acquisition correlation of each proof-selected root."""

    atom = _operations._encode_m2_m1_atom
    relations = _selected_venue_relations(selection)
    rows: list[object] = []
    reached = 0
    for root_key, root_record in zip(
        _selected_root_keys_from_selection(book, selection),
        selection.roots,
        strict=True,
    ):
        entry = book._acquisition_correlation_by_root.get(
            _venue._coverage_root_index_key(root_key)
        )
        if entry is None:
            continue
        if entry.root_key != root_key:
            raise ValueError("reached correlation does not own its selected root")
        route = relations.routes_by_root_key_id.get(root_record.root_fill_key_id)
        if route is None:
            raise ValueError("reached correlation has no selected root route")
        effect, owner, position_scope = _require_selected_route_relation(
            book, relations, route, root_record, "correlation"
        )
        expected_leg = _identity.VenueLegKey(
            book.scope.broker,
            book.scope.environment,
            book.scope.account,
            owner.owner_id,
        )
        if (
            entry.application_generation_id != effect.application_generation_id
            or entry.position_scope != position_scope
            or entry.request_occurrence_id != effect.request_occurrence_id
            or entry.effect_id != effect.effect_external
            or entry.leg_key != expected_leg
        ):
            raise ValueError("reached correlation disagrees with its selected route")
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.AcquisitionCorrelation/v1",
                    atom(entry.application_generation_id),
                    _operations._encode_m2_position_scope(entry.position_scope),
                    atom(entry.request_occurrence_id),
                    atom(entry.effect_id),
                    atom(entry.leg_key),
                    atom(entry.root_key),
                ]
            )
        )
    # No whole-map cardinality check. _PersistentKeyMap has get/insert_new/
    # replace_existing and no deletion of any kind, so this index is monotonic,
    # while the repository selects only effects with disposition IN
    # ('OPEN','INVALIDATED') plus CLOSED effects carrying a late-admitted owner.
    # One ordinary closed effect therefore leaves a permanently unselected entry
    # behind, and comparing size against the reached count refused every book
    # from that point on. R15 section 2 omits such rows as audit history.
    return _checkpoint_collection("m2.venue.AcquisitionCorrelations/v1", rows)


def _encode_runtime_checkpoint_venue_coverage_provenance_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the covered-root provenance of each proof-selected scope.

    ``_CoverageProvenance.roots`` is itself a persistent key map with no iteration, so
    the nested covered-root collection is flattened by looking up each proof-selected
    root key. The nested map is counted too: a covered root outside the selection
    fails closed rather than being dropped from the proof.
    """

    root_keys = _selected_root_keys_from_selection(book, selection)
    rows: list[object] = []
    reached = 0
    for position_scope in _selected_position_scopes_from_selection(book, selection):
        provenance = book._coverage_provenance_by_scope.get(
            _venue._position_scope_index_key(position_scope)
        )
        if provenance is None:
            continue
        reached += 1
        covered: list[object] = []
        for root_key in root_keys:
            fact_commitment = provenance.roots.get(
                _venue._coverage_root_index_key(root_key)
            )
            if fact_commitment is None:
                continue
            covered.append(
                [
                    "m2.venue.CoveredRoot/v1",
                    _operations._encode_m2_m1_atom(root_key),
                    _operations._encode_m2_bytes(fact_commitment),
                ]
            )
        if provenance.roots.size != len(covered):
            raise ValueError(
                "coverage provenance retains a covered root outside the selection"
            )
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.CoverageProvenance/v1",
                    _operations._encode_m2_position_scope(position_scope),
                    _checkpoint_collection("m2.venue.CoveredRoots/v1", covered),
                    (
                        None
                        if provenance.root_heads_commitment is None
                        else _operations._encode_m2_bytes(
                            provenance.root_heads_commitment
                        )
                    ),
                ]
            )
        )
    if book._coverage_provenance_by_scope.size != reached:
        raise ValueError(
            "coverage provenance map retains a key outside the selected scope set"
        )
    return _checkpoint_collection("m2.venue.CoverageProvenances/v1", rows)


def _encode_runtime_checkpoint_venue_broker_coverage_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the broker coverage of each proof-selected root.

    The owner map stores an integer index into ``_broker_coverage_ledger`` rather than
    the coverage itself, so each proof-selected root is dereferenced through the
    ledger; a dangling index fails closed.
    """

    atom = _operations._encode_m2_m1_atom
    relations = _selected_venue_relations(selection)
    rows: list[object] = []
    reached = 0
    for root_key, root_record in zip(
        _selected_root_keys_from_selection(book, selection),
        selection.roots,
        strict=True,
    ):
        index = book._broker_coverage_by_root.get(
            _venue._coverage_root_index_key(root_key)
        )
        if index is None:
            continue
        coverage = book._broker_coverage_ledger.get(index)
        if coverage is None:
            raise ValueError("broker coverage index does not resolve in its ledger")
        route = relations.routes_by_root_key_id.get(root_record.root_fill_key_id)
        if route is None:
            raise ValueError("broker coverage has no selected root route")
        effect, owner, position_scope = _require_selected_route_relation(
            book, relations, route, root_record, "broker coverage"
        )
        leg_key = _identity.VenueLegKey(
            book.scope.broker,
            book.scope.environment,
            book.scope.account,
            owner.owner_id,
        )
        if coverage.effect_id != effect.effect_external or coverage.leg_key != leg_key:
            raise ValueError(
                "reached broker coverage disagrees with its selected route"
            )
        _require_selected_coverage_fact(
            coverage.fact,
            root_key=root_key,
            effect=effect,
            leg_key=leg_key,
            position_scope=position_scope,
            subject="broker coverage fact",
        )
        _require_selected_coverage_fact(
            coverage.head_fact,
            root_key=root_key,
            effect=effect,
            leg_key=leg_key,
            position_scope=position_scope,
            subject="broker coverage head",
        )
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.BrokerCoverage/v1",
                    atom(coverage.effect_id),
                    atom(coverage.leg_key),
                    atom(coverage.prior_cumulative_quantity),
                    atom(coverage.resulting_cumulative_quantity),
                    _operations._encode_m2_broker_fill_fact(coverage.fact),
                    _operations._encode_m2_bytes(coverage.evidence_digest),
                    atom(coverage.root_source_input_id),
                    _operations._encode_m2_broker_execution_fact(coverage.head_fact),
                    _operations._encode_m2_bytes(coverage.head_evidence_digest),
                    atom(coverage.head_source_input_id),
                    coverage.mapping_exact,
                ]
            )
        )
    # No whole-map cardinality check. _PersistentKeyMap has get/insert_new/
    # replace_existing and no deletion of any kind, so this index is monotonic,
    # while the repository selects only effects with disposition IN
    # ('OPEN','INVALIDATED') plus CLOSED effects carrying a late-admitted owner.
    # One ordinary closed effect therefore leaves a permanently unselected entry
    # behind, and comparing size against the reached count refused every book
    # from that point on. R15 section 2 omits such rows as audit history.
    return _checkpoint_collection("m2.venue.BrokerCoverages/v1", rows)


def _encode_runtime_checkpoint_venue_human_coverage_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the human coverage of each proof-selected root through its ledger."""

    atom = _operations._encode_m2_m1_atom
    relations = _selected_venue_relations(selection)
    rows: list[object] = []
    reached = 0
    for root_key, root_record in zip(
        _selected_root_keys_from_selection(book, selection),
        selection.roots,
        strict=True,
    ):
        index = book._human_coverage_by_root.get(
            _venue._coverage_root_index_key(root_key)
        )
        if index is None:
            continue
        coverage = book._human_coverage_ledger.get(index)
        if coverage is None:
            raise ValueError("human coverage index does not resolve in its ledger")
        route = relations.routes_by_root_key_id.get(root_record.root_fill_key_id)
        if route is None:
            raise ValueError("human coverage has no selected root route")
        effect, owner, position_scope = _require_selected_route_relation(
            book, relations, route, root_record, "human coverage"
        )
        leg_key = _identity.VenueLegKey(
            book.scope.broker,
            book.scope.environment,
            book.scope.account,
            owner.owner_id,
        )
        if coverage.effect_id != effect.effect_external or coverage.leg_key != leg_key:
            raise ValueError("reached human coverage disagrees with its selected route")
        _require_selected_coverage_fact(
            coverage.fact,
            root_key=root_key,
            effect=effect,
            leg_key=leg_key,
            position_scope=position_scope,
            subject="human coverage fact",
        )
        if coverage.broker_fact is not None:
            _require_selected_coverage_fact(
                coverage.broker_fact,
                root_key=root_key,
                effect=effect,
                leg_key=leg_key,
                position_scope=position_scope,
                subject="human coverage corroboration",
            )
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.HumanCoverage/v1",
                    atom(coverage.effect_id),
                    atom(coverage.leg_key),
                    _operations._encode_m2_human_attested_fill_fact(coverage.fact),
                    atom(coverage.source_input_id),
                    coverage.broker_corroborated,
                    (
                        None
                        if coverage.broker_fact is None
                        else _operations._encode_m2_broker_fill_fact(
                            coverage.broker_fact
                        )
                    ),
                    (
                        None
                        if coverage.broker_evidence_digest is None
                        else _operations._encode_m2_bytes(
                            coverage.broker_evidence_digest
                        )
                    ),
                    (
                        None
                        if coverage.broker_source_input_id is None
                        else atom(coverage.broker_source_input_id)
                    ),
                ]
            )
        )
    # No whole-map cardinality check. _PersistentKeyMap has get/insert_new/
    # replace_existing and no deletion of any kind, so this index is monotonic,
    # while the repository selects only effects with disposition IN
    # ('OPEN','INVALIDATED') plus CLOSED effects carrying a late-admitted owner.
    # One ordinary closed effect therefore leaves a permanently unselected entry
    # behind, and comparing size against the reached count refused every book
    # from that point on. R15 section 2 omits such rows as audit history.
    return _checkpoint_collection("m2.venue.HumanCoverages/v1", rows)


def _encode_runtime_checkpoint_venue_closure_head_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the terminal closure head of each proof-selected owner leg.

    No whole-map cardinality check: a closure head persists for every leg that has
    ever terminated, and the repository selects only OPEN/INVALIDATED effects plus
    late-admitted owners, so an ordinary completed effect leaves a head behind that
    is legitimately unselected. R15 section 2 calls those terminal rows audit
    history and omits them. An earlier revision compared the map size against the
    reached count and so refused every book after its first effect closed.
    """

    atom = _operations._encode_m2_m1_atom
    # R17 section 1 makes the repository proof the sole membership witness, and
    # every peer family binds its reached row against the selected record. The
    # closure family had no such binding at all, so a book whose head disagreed
    # with the durable closure_chain -- a different ordinal or kind -- was signed
    # as authentic. ClosureChainRecord.closure_id is a database surrogate and does
    # not compare with the owner's ClosureId, so the bindable fields are the
    # owner, the ordinal, the kind, and whether a predecessor exists.
    selected_closures = {record.owner_id: record for record in selection.closure_heads}
    if len(selected_closures) != len(selection.closure_heads):
        raise ValueError("selected closure heads repeat an owner")
    relations = _selected_venue_relations(selection)
    rows: list[object] = []
    reached = 0
    for leg_key in _selected_leg_keys_from_selection(book, selection):
        closure = book._closure_head_by_leg.get(_venue._leg_index_key(leg_key))
        if closure is None:
            if leg_key.order_id in selected_closures:
                raise ValueError("selected closure head has no current closure row")
            continue
        if closure.leg_key != leg_key:
            raise ValueError("reached closure does not own its selected leg")
        record = selected_closures.get(leg_key.order_id)
        if record is None:
            raise ValueError("reached closure head is not a selected closure")
        owner = relations.owners_by_id.get(record.owner_id)
        effect = relations.effects_by_id.get(record.effect_id)
        if owner is None or effect is None:
            raise ValueError("selected closure head has an absent selected relation")
        if (
            record.scope_id != owner.scope_id
            or record.effect_id != owner.effect_id
            or owner.scope_id != effect.scope_id
            or owner.execution_profile_id != effect.execution_profile_id
            or owner.owner_generation_id != effect.acquisition_generation_id
        ):
            raise ValueError("selected closure head disagrees with its owner relation")
        if (
            closure.ordinal != record.ordinal
            or closure.kind.value != record.closure_kind
            or (closure.predecessor_closure_id is None)
            != (record.predecessor_closure_id is None)
        ):
            raise ValueError("reached closure disagrees with its selected record")
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.TerminalClosure/v1",
                    atom(closure.leg_key),
                    atom(closure.closure_id),
                    _require_nonnegative_int("closure ordinal", closure.ordinal),
                    (
                        None
                        if closure.predecessor_closure_id is None
                        else atom(closure.predecessor_closure_id)
                    ),
                    _checkpoint_enum("m1.venue.VenueAttemptState", closure.status),
                    atom(closure.cumulative_quantity),
                    atom(closure.observed_cumulative_quantity),
                    atom(closure.evidence_reference),
                    _checkpoint_enum("m1.venue.VenueClosureKind", closure.kind),
                    atom(closure.source_input_id),
                    (
                        None
                        if closure.observation_id is None
                        else atom(closure.observation_id)
                    ),
                    (
                        None
                        if closure.source_event_id is None
                        else atom(closure.source_event_id)
                    ),
                    (
                        None
                        if closure.broker_terminal_state is None
                        else _checkpoint_enum(
                            "m1.venue.VenueAttemptState", closure.broker_terminal_state
                        )
                    ),
                    None if closure.actor is None else atom(closure.actor),
                    closure.reason,
                    (
                        None
                        if closure.evidence_digest is None
                        else _operations._encode_m2_bytes(closure.evidence_digest)
                    ),
                ]
            )
        )
    return _checkpoint_collection("m2.venue.ClosureHeads/v1", rows)


@_dataclass(frozen=True, slots=True)
class _ReconciliationReference:
    """One selected current row's precise reconciliation obligation."""

    input_id: _identity.VenueInputId
    leg_key: _identity.VenueLegKey
    effect: _records.VenueEffectRecord
    position_scope: _fills.PositionScope
    root_key: _identity.RootFillKey | None
    required: bool


def _merge_reconciliation_reference(
    ordered: dict[str, _ReconciliationReference],
    reference: _ReconciliationReference,
) -> None:
    """Merge one selected reconciliation obligation without losing coordinates.

    Multiple current rows may name one input.  The first reference is not allowed
    to erase coordinates learned from a later reference: agreement is required for
    every known leg/effect/scope/root coordinate, a known root strengthens an
    earlier unknown root, and ``required`` is monotonic.  Keeping this merge at a
    named boundary makes the collision contract directly testable.
    """

    if type(reference.input_id) is not _identity.VenueInputId:
        raise TypeError("referenced input must be the exact VenueInputId type")
    existing = ordered.get(reference.input_id.value)
    if existing is None:
        ordered[reference.input_id.value] = reference
        return
    if existing.leg_key != reference.leg_key:
        raise ValueError("referenced input is named by two different legs")
    if existing.effect != reference.effect:
        raise ValueError("referenced input is named by two different effects")
    if existing.position_scope != reference.position_scope:
        raise ValueError("referenced input is named by two different scopes")
    if (
        existing.root_key is not None
        and reference.root_key is not None
        and existing.root_key != reference.root_key
    ):
        raise ValueError("referenced input is named by two different roots")
    ordered[reference.input_id.value] = _ReconciliationReference(
        reference.input_id,
        reference.leg_key,
        reference.effect,
        reference.position_scope,
        reference.root_key if reference.root_key is not None else existing.root_key,
        existing.required or reference.required,
    )


def _referenced_reconciliation_inputs(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> tuple[_ReconciliationReference, ...]:
    """Collect the selected reconciliation obligations without blanket omission.

    A normal applied fill and an ordinary terminal closure may name an evidence
    input with no reconciliation record.  In contrast, the reducer creates a
    revision reconciliation atomically whenever an inexact revision head is
    retained.  References are therefore classified at their producer boundary;
    a missing mandatory revision record is an integrity failure, not history that
    can be silently omitted.  Duplicate references merge only when every known
    coordinate agrees, and a later known coordinate strengthens an earlier one.
    """

    relations = _selected_venue_relations(selection)
    ordered: dict[str, _ReconciliationReference] = {}

    def _reference(
        input_id: _identity.VenueInputId,
        leg_key: _identity.VenueLegKey,
        effect: _records.VenueEffectRecord,
        position_scope: _fills.PositionScope,
        root_key: _identity.RootFillKey | None,
        *,
        required: bool,
    ) -> None:
        _merge_reconciliation_reference(
            ordered,
            _ReconciliationReference(
                input_id, leg_key, effect, position_scope, root_key, required
            ),
        )

    for leg_key in _selected_leg_keys_from_selection(book, selection):
        closure = book._closure_head_by_leg.get(_venue._leg_index_key(leg_key))
        if closure is None:
            continue
        owner = relations.owners_by_id.get(leg_key.order_id)
        if owner is None:
            raise ValueError("closure has no selected owner relation")
        effect = relations.effects_by_id.get(owner.effect_id)
        if effect is None:
            raise ValueError("closure owner has no selected effect relation")
        scope = _selected_effect_position_scope(book, relations, effect, "closure")
        root_key = None
        if owner.root_fill_key_id is not None:
            root = relations.roots_by_key_id.get(owner.root_fill_key_id)
            if root is None:
                raise ValueError("closure owner references an unselected root")
            root_key = _identity.RootFillKey(
                book.scope.broker,
                book.scope.environment,
                book.scope.account,
                root.root_fill_id,
            )
        _reference(
            closure.source_input_id,
            closure.leg_key,
            effect,
            scope,
            root_key,
            required=False,
        )

    for root_key, root_record in zip(
        _selected_root_keys_from_selection(book, selection),
        selection.roots,
        strict=True,
    ):
        route = relations.routes_by_root_key_id.get(root_record.root_fill_key_id)
        if route is None:
            raise ValueError("coverage has no selected root route")
        effect, owner, position_scope = _require_selected_route_relation(
            book, relations, route, root_record, "coverage"
        )
        expected_leg = _identity.VenueLegKey(
            book.scope.broker,
            book.scope.environment,
            book.scope.account,
            owner.owner_id,
        )
        root_index_key = _venue._coverage_root_index_key(root_key)
        human_index = book._human_coverage_by_root.get(root_index_key)
        if human_index is not None:
            human = book._human_coverage_ledger.get(human_index)
            if human is None:
                raise ValueError("human coverage index does not resolve in its ledger")
            if (
                human.effect_id != effect.effect_external
                or human.leg_key != expected_leg
            ):
                raise ValueError("human coverage disagrees with its selected route")
            _require_selected_coverage_fact(
                human.fact,
                root_key=root_key,
                effect=effect,
                leg_key=expected_leg,
                position_scope=position_scope,
                subject="human reconciliation coverage",
            )
            _reference(
                human.source_input_id,
                human.leg_key,
                effect,
                position_scope,
                root_key,
                required=False,
            )
            if human.broker_source_input_id is not None:
                _reference(
                    human.broker_source_input_id,
                    human.leg_key,
                    effect,
                    position_scope,
                    root_key,
                    required=False,
                )
        broker_index = book._broker_coverage_by_root.get(root_index_key)
        if broker_index is not None:
            broker = book._broker_coverage_ledger.get(broker_index)
            if broker is None:
                raise ValueError("broker coverage index does not resolve in its ledger")
            if (
                broker.effect_id != effect.effect_external
                or broker.leg_key != expected_leg
            ):
                raise ValueError("broker coverage disagrees with its selected route")
            _require_selected_coverage_fact(
                broker.fact,
                root_key=root_key,
                effect=effect,
                leg_key=expected_leg,
                position_scope=position_scope,
                subject="broker reconciliation coverage",
            )
            _require_selected_coverage_fact(
                broker.head_fact,
                root_key=root_key,
                effect=effect,
                leg_key=expected_leg,
                position_scope=position_scope,
                subject="broker reconciliation head",
            )
            _reference(
                broker.root_source_input_id,
                broker.leg_key,
                effect,
                position_scope,
                root_key,
                required=False,
            )
            _reference(
                broker.head_source_input_id,
                broker.leg_key,
                effect,
                position_scope,
                root_key,
                required=(
                    not broker.mapping_exact
                    and type(broker.head_fact)
                    in {_fills.BrokerTradeCorrectFact, _fills.BrokerTradeBustFact}
                ),
            )
    return tuple(ordered.values())


def _encode_runtime_checkpoint_venue_reconciliation_row(
    record: _recovery.ReconciliationRecord | _recovery.RevisionReconciliationRecord,
) -> list[object]:
    """Encode one member of the closed fill/revision reconciliation union."""

    atom = _operations._encode_m2_m1_atom
    if type(record) is _recovery.ReconciliationRecord:
        return [
            "m2.venue.FillReconciliation/v1",
            atom(record.input_id),
            atom(record.effect_id),
            atom(record.leg_key),
            atom(record.prior_cumulative_quantity),
            atom(record.resulting_cumulative_quantity),
            _operations._encode_m2_broker_fill_fact(record.fact),
            _operations._encode_m2_bytes(record.evidence_digest),
            record.reason,
        ]
    if type(record) is _recovery.RevisionReconciliationRecord:
        fact = record.fact
        if type(fact) is _fills.BrokerTradeCorrectFact:
            encoded_fact = _operations._encode_m2_broker_trade_correct_fact(fact)
        elif type(fact) is _fills.BrokerTradeBustFact:
            encoded_fact = _operations._encode_m2_broker_trade_bust_fact(fact)
        else:
            raise TypeError("revision reconciliation fact is not an admitted type")
        return [
            "m2.venue.RevisionReconciliation/v1",
            atom(record.input_id),
            atom(record.effect_id),
            atom(record.leg_key),
            atom(record.prior_root_quantity),
            atom(record.prior_venue_cumulative_quantity),
            atom(record.resulting_venue_cumulative_quantity),
            encoded_fact,
            _operations._encode_m2_bytes(record.evidence_digest),
            record.canonical_applied,
            record.reason,
        ]
    raise TypeError("reconciliation record is not an admitted exact type")


def _encode_runtime_checkpoint_venue_reconciliation_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project every reconciliation named by a selected closure or coverage row.

    R15 section 2 is the governing rule for this venue index: rows are admitted
    "only when their input ID is directly referenced by one of those selected
    current closure/coverage rows," and unreferenced append-only ledger rows "are
    audit history and are omitted." ``_reconciliation_by_input`` is
    ``insert_new``-only beside that append-only ledger, so a whole-map
    cardinality check contradicts the omission rule. (R16 section 2's
    superset/exact taxonomy classifies *authority* maps and is deliberately not
    cited as authority here -- REV-0078 P2-1.)

    An earlier revision compared its size against the reached count. That refused
    every book whose reducer had taken a reconciliation-required branch, because
    ``recovery._reconciliation`` appends a record without touching any closure or
    coverage row -- so the input is legitimately unreferenced and the quarantine
    state a checkpoint exists to preserve could not be checkpointed at all.
    """

    rows: list[object] = []
    for reference in _referenced_reconciliation_inputs(book, selection):
        record = book._reconciliation_by_input.get(
            _venue._input_index_key(reference.input_id)
        )
        if record is None:
            if reference.required:
                raise ValueError("required reconciliation is absent")
            continue
        if record.input_id != reference.input_id:
            raise ValueError("reached reconciliation does not own its referenced input")
        # Equality with the row that admitted it, not membership in the selected
        # set: a stale reconciliation on another selected leg of the same scope
        # would satisfy membership while being reached through the wrong row.
        if record.leg_key != reference.leg_key:
            raise ValueError("reached reconciliation does not own its referencing leg")
        if record.effect_id != reference.effect.effect_external:
            raise ValueError(
                "reached reconciliation does not own its referencing effect"
            )
        if reference.root_key is not None:
            _require_selected_coverage_fact(
                record.fact,
                root_key=reference.root_key,
                effect=reference.effect,
                leg_key=reference.leg_key,
                position_scope=reference.position_scope,
                subject="reconciliation fact",
            )
        rows.append(
            _require_bounded_checkpoint_row(
                _encode_runtime_checkpoint_venue_reconciliation_row(record)
            )
        )
    return _checkpoint_collection("m2.venue.Reconciliations/v1", rows)


def _encode_runtime_checkpoint_venue_scope(scope: _venue.VenueScope) -> list[object]:
    """Encode the frozen 5-member venue scope."""

    if type(scope) is not _venue.VenueScope:
        raise TypeError("venue scope must be exact VenueScope")
    atom = _operations._encode_m2_m1_atom
    return [
        "m2.venue.Scope/v1",
        atom(scope.generation),
        atom(scope.broker),
        atom(scope.environment),
        atom(scope.account),
    ]


def _encode_runtime_checkpoint_venue_execution_binding(
    binding: _venue.VenueExecutionBinding,
) -> list[object]:
    """Encode the frozen 5-member venue execution binding."""

    if type(binding) is not _venue.VenueExecutionBinding:
        raise TypeError("execution binding must be exact VenueExecutionBinding")
    return [
        "m2.venue.ExecutionBinding/v1",
        _operations._encode_m2_position_scope(binding.position_scope),
        _operations._encode_m2_bytes(binding.position_commitment),
        _operations._encode_m2_bytes(binding.root_heads_commitment),
        _require_nonnegative_int("binding integrity bits", binding.integrity_bits),
    ]


def _encode_runtime_checkpoint_venue_transition_cursor(
    cursor: _venue._ProtectionCursor,
) -> list[object]:
    """Encode the frozen 6-member inert protection transition cursor.

    The execution commitment and its checkpoint are wholly present or wholly null;
    the source dataclass already refuses a partial pair, and encoding them from the
    one source object keeps that pairing on the wire.
    """

    if type(cursor) is not _venue._ProtectionCursor:
        raise TypeError("transition cursor must be exact _ProtectionCursor")
    return [
        "m2.venue.ProtectionTransitionCursor/v1",
        _require_nonnegative_int("transition cursor ordinal", cursor.ordinal),
        _operations._encode_m2_bytes(cursor.head),
        (
            None
            if cursor.mandate_id is None
            else _operations._encode_m2_m1_atom(cursor.mandate_id)
        ),
        (
            None
            if cursor.execution_commitment is None
            else _operations._encode_m2_bytes(cursor.execution_commitment)
        ),
        (
            None
            if cursor.execution_checkpoint is None
            else _encode_runtime_checkpoint_venue_execution_checkpoint(
                cursor.execution_checkpoint
            )
        ),
    ]


def _encode_runtime_checkpoint_venue_atom_tuple(
    tag: str, values: tuple[_durable_codec._OwningValue, ...], subject: str
) -> list[object]:
    """Encode one count-bearing summary tuple in source order without duplicates."""

    if type(values) is not tuple:
        raise TypeError(f"{subject} must be an exact tuple")
    atom = _operations._encode_m2_m1_atom
    rows: list[object] = []
    seen: set[bytes] = set()
    for value in values:
        encoded = atom(value)
        order_key = _array_order_key(encoded)
        if order_key in seen:
            raise ValueError(f"{subject} retains a duplicate member")
        seen.add(order_key)
        rows.append(encoded)
    return _checkpoint_collection(tag, rows)


def _encode_runtime_checkpoint_venue_symbol_authority_summary(
    summary: _venue._SymbolAuthoritySummary,
) -> list[object]:
    """Encode the frozen 10-member inert symbol authority summary."""

    if type(summary) is not _venue._SymbolAuthoritySummary:
        raise TypeError("summary must be exact _SymbolAuthoritySummary")
    return [
        "m2.venue.SymbolAuthoritySummary/v1",
        _require_nonnegative_int("summary effect count", summary.effect_count),
        _require_nonnegative_int(
            "summary blocking effect count", summary.blocking_effect_count
        ),
        _require_nonnegative_int(
            "summary blocking buy effect count", summary.blocking_buy_effect_count
        ),
        _require_nonnegative_int(
            "summary stand-downable buy count", summary.stand_downable_buy_count
        ),
        _encode_runtime_checkpoint_venue_atom_tuple(
            "m2.venue.StandDownEffects/v1",
            summary.stand_downable_buy_effect_ids,
            "summary stand-down effects",
        ),
        _encode_runtime_checkpoint_venue_atom_tuple(
            "m2.venue.CancellableBuyLegs/v1",
            summary.known_cancellable_buy_leg_keys,
            "summary cancellable buy legs",
        ),
        _encode_runtime_checkpoint_venue_atom_tuple(
            "m2.venue.CancelPendingBuyLegs/v1",
            summary.known_cancel_pending_buy_leg_keys,
            "summary cancel-pending buy legs",
        ),
        _require_nonnegative_int(
            "summary waiting buy parent count", summary.waiting_buy_parent_count
        ),
        _require_nonnegative_int(
            "summary unknown buy effect count", summary.unknown_buy_effect_count
        ),
    ]


def _encode_runtime_checkpoint_venue_transition_proof(
    proof: _venue._ProtectionTransitionProof,
) -> list[object]:
    """Encode the frozen 25-member inert venue transition proof.

    R1 admits this proof as inert evidence carried by a bootstrap record: decode
    never allocates the source proof, cursor, summary, or book.  R2 requires the
    exact source type and authentic lineage here, so a forged or spliced proof
    cannot reach the wire.
    """

    if type(proof) is not _venue._ProtectionTransitionProof:
        raise TypeError("transition proof must be exact _ProtectionTransitionProof")
    if not proof.lineage_is_authentic:
        raise ValueError("transition proof lineage is not authentic")
    cursor = _encode_runtime_checkpoint_venue_transition_cursor
    checkpoint = _encode_runtime_checkpoint_venue_execution_checkpoint
    summary = _encode_runtime_checkpoint_venue_symbol_authority_summary
    binding = _encode_runtime_checkpoint_venue_execution_binding
    digest = _operations._encode_m2_bytes
    return [
        "m2.venue.ProtectionTransitionProof/v1",
        _operations._encode_m2_position_scope(proof.position_scope),
        cursor(proof.predecessor_cursor),
        cursor(proof.cursor),
        _encode_runtime_checkpoint_venue_scope(proof.predecessor_book_scope),
        _encode_runtime_checkpoint_venue_scope(proof.book_scope),
        digest(proof.predecessor_book_commitment),
        digest(proof.book_commitment),
        digest(proof.predecessor_execution_commitment),
        digest(proof.execution_commitment),
        checkpoint(proof.predecessor_execution_checkpoint),
        checkpoint(proof.execution_checkpoint),
        summary(proof.predecessor_summary),
        summary(proof.summary),
        None
        if proof.predecessor_binding is None
        else binding(proof.predecessor_binding),
        None if proof.binding is None else binding(proof.binding),
        proof.predecessor_execution_binding_matches,
        proof.execution_binding_matches,
        proof.predecessor_account_reconciliation_clear,
        proof.account_reconciliation_clear,
        digest(proof.command_commitment),
        _checkpoint_enum("m1.venue.VenueRecoveryDisposition", proof.disposition),
        _require_exact_signed_int("transition quantity delta", proof.quantity_delta),
        _checkpoint_enum("m1.venue.ProtectionTransitionSourceKind", proof.source_kind),
        digest(proof.source_binding),
    ]


def _encode_runtime_checkpoint_venue_bootstrap_active(
    record: _venue._BootstrapBoundTargetRecord,
) -> list[object]:
    """Encode the frozen 25-member active bootstrap target row.

    The map seal, commitment, and record seal are derived rather than carried: R2
    refuses to trust a retained seal, so none of them appears in the bytes.
    """

    if type(record) is not _venue._BootstrapBoundTargetRecord:
        raise TypeError("bootstrap record must be exact _BootstrapBoundTargetRecord")
    # Contract 07 section 3.3: "All retained seals and commitments are re-derived
    # and compared, never trusted." Absence from the wire is not verification --
    # the record's own authenticity check re-derives _map_seal, commitment, _seal,
    # and both retained proof commitments against the proofs it carries, so a
    # record whose members were altered after minting cannot reach the wire.
    if not _venue._bootstrap_bound_target_record_is_authentic(record):
        raise ValueError("bootstrap target record is not venue-authentic")
    atom = _operations._encode_m2_m1_atom
    digest = _operations._encode_m2_bytes
    count = _require_nonnegative_int
    return [
        "m2.venue.BootstrapTargetActive/v1",
        atom(record.application_generation_id),
        _operations._encode_m2_position_scope(record.position_scope),
        _checkpoint_enum("m1.venue.BootstrapSourceKind", record.source_kind),
        digest(record.source_execution_commitment),
        digest(record.target_genesis_execution_commitment),
        digest(record.target_execution_commitment),
        _encode_runtime_checkpoint_venue_execution_binding(record.binding),
        count("bootstrap account registry count", record.account_registry_count),
        digest(record.account_registry_commitment),
        count(
            "bootstrap reconciliation transition count",
            record.reconciliation_transition_count,
        ),
        digest(record.reconciliation_transition_head),
        atom(record.bootstrap_input_id),
        digest(record.bootstrap_input_commitment),
        digest(record.bootstrap_target_execution_commitment),
        count(
            "bootstrap origin registry count", record.bootstrap_account_registry_count
        ),
        digest(record.bootstrap_account_registry_commitment),
        count(
            "bootstrap origin reconciliation count",
            record.bootstrap_reconciliation_transition_count,
        ),
        digest(record.bootstrap_reconciliation_transition_head),
        digest(record.bootstrap_neutral_checkpoint_proof_commitment),
        _encode_runtime_checkpoint_venue_transition_proof(
            record._bootstrap_neutral_checkpoint_proof
        ),
        atom(record.checkpoint_input_id),
        digest(record.checkpoint_command_commitment),
        digest(record.neutral_checkpoint_proof_commitment),
        _encode_runtime_checkpoint_venue_transition_proof(
            record._neutral_checkpoint_proof
        ),
    ]


def _encode_runtime_checkpoint_venue_bootstrap_target(
    value: object,
) -> tuple[list[object], _venue._BootstrapBoundTargetRecord]:
    """Encode one member of the closed active/consumed bootstrap union.

    Returns the row beside the active record it anchors on, so the caller checks
    the scope of the one record that owns it rather than re-deriving the union.

    R2 refuses the staged replacement value and the raw map-seal bytes outright:
    both are transient reducer states that a published book never retains, so a
    checkpoint carrying either is evidence of an interrupted or spliced write.
    """

    if type(value) is _venue._BootstrapBoundTargetRecord:
        return _encode_runtime_checkpoint_venue_bootstrap_active(value), value
    if type(value) is _venue._ConsumedBootstrapBoundTargetRecord:
        if not _venue._consumed_bootstrap_bound_target_record_is_authentic(value):
            raise ValueError("consumed bootstrap target is not venue-authentic")
        active = value.active_record
        if type(active) is not _venue._BootstrapBoundTargetRecord:
            raise TypeError("consumed bootstrap target retains no exact active record")
        atom = _operations._encode_m2_m1_atom
        row: list[object] = [
            "m2.venue.BootstrapTargetConsumed/v1",
            _encode_runtime_checkpoint_venue_bootstrap_active(active),
            atom(value.effect_id),
            atom(value.request_occurrence_id),
            atom(value.request_input_id),
            _operations._encode_m2_bytes(value.effect_scope_commitment),
        ]
        return row, active
    raise TypeError("bootstrap target is neither an active nor a consumed record")


def _encode_runtime_checkpoint_venue_bootstrap_target_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the bootstrap target of each proof-selected position scope.

    ``_bootstrap_bound_target_by_scope`` is an exact current selected-scope map, so
    a retained key outside the selection fails closed.
    """

    rows: list[object] = []
    reached = 0
    for position_scope in _selected_position_scopes_from_selection(book, selection):
        value = book._bootstrap_bound_target_by_scope.get(
            _venue._position_scope_index_key(position_scope)
        )
        if value is None:
            continue
        row, anchor = _encode_runtime_checkpoint_venue_bootstrap_target(value)
        if anchor.position_scope != position_scope:
            raise ValueError("reached bootstrap target does not own its selected scope")
        reached += 1
        rows.append(_require_bounded_checkpoint_row(row))
    if book._bootstrap_bound_target_by_scope.size != reached:
        raise ValueError(
            "bootstrap target map retains a key outside the selected scope set"
        )
    return _checkpoint_collection("m2.venue.BootstrapTargets/v1", rows)


@_dataclass(frozen=True, slots=True)
class _ExecutionReconciliationReference:
    """A selected bootstrap input and whether its outcome is mandatory."""

    input_id: _identity.VenueInputId
    position_scope: _fills.PositionScope
    required: bool


def _referenced_execution_reconciliation_inputs(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> tuple[_ExecutionReconciliationReference, ...]:
    """Classify initial bootstrap versus refreshed catch-up outcome obligations.

    An initial bootstrap retains the same source identity in both fields and has
    no catch-up outcome.  Once a target has a distinct ``checkpoint_input_id``,
    the venue producer creates an execution-reconciliation outcome atomically;
    omitting it would lose a selected registry transition.
    """

    ordered: dict[str, _ExecutionReconciliationReference] = {}

    def _reference(
        input_id: _identity.VenueInputId,
        position_scope: _fills.PositionScope,
        *,
        required: bool,
    ) -> None:
        if type(input_id) is not _identity.VenueInputId:
            raise TypeError("referenced input must be the exact VenueInputId type")
        existing = ordered.get(input_id.value)
        if existing is None:
            ordered[input_id.value] = _ExecutionReconciliationReference(
                input_id, position_scope, required
            )
        elif existing.position_scope != position_scope:
            raise ValueError("referenced input is named by two different scopes")
        elif required and not existing.required:
            ordered[input_id.value] = _ExecutionReconciliationReference(
                input_id, position_scope, True
            )

    for position_scope in _selected_position_scopes_from_selection(book, selection):
        value = book._bootstrap_bound_target_by_scope.get(
            _venue._position_scope_index_key(position_scope)
        )
        if value is None:
            continue
        if type(value) is _venue._BootstrapBoundTargetRecord:
            anchor_record = value
        elif type(value) is _venue._ConsumedBootstrapBoundTargetRecord:
            anchor_record = value.active_record
        else:
            raise TypeError(
                "bootstrap target is neither an active nor a consumed record"
            )
        _reference(anchor_record.bootstrap_input_id, position_scope, required=False)
        _reference(
            anchor_record.checkpoint_input_id,
            position_scope,
            required=(
                anchor_record.checkpoint_input_id != anchor_record.bootstrap_input_id
                and anchor_record._neutral_checkpoint_proof.source_kind
                is not _venue._ProtectionTransitionSourceKind.COMPACT_RESTORE
            ),
        )
    return tuple(ordered.values())


def _encode_runtime_checkpoint_venue_execution_reconciliation_row(
    record: object,
) -> list[object]:
    """Encode one member of the closed resolved/unresolved registry outcome union."""

    atom = _operations._encode_m2_m1_atom
    digest = _operations._encode_m2_bytes
    checkpoint = _encode_runtime_checkpoint_venue_execution_checkpoint
    binding = _encode_runtime_checkpoint_venue_execution_binding
    if type(record) is _venue._ResolvedRegistryProjectionOutcome:
        return [
            "m2.venue.ResolvedRegistryProjection/v1",
            atom(record.input_id),
            digest(record.command_commitment),
            checkpoint(record.target_checkpoint),
            binding(record.source_binding),
            _require_nonnegative_int(
                "resulting registry count", record.resulting_registry_count
            ),
            digest(record.resulting_registry_commitment),
            record.reason,
            _checkpoint_enum("m1.venue.ResolvedProjectionKind", record.projection_kind),
        ]
    if type(record) is _venue._UnresolvedRegistryAdvanceOutcome:
        return [
            "m2.venue.UnresolvedRegistryAdvance/v1",
            atom(record.input_id),
            digest(record.command_commitment),
            checkpoint(record.target_checkpoint),
            _require_nonnegative_int(
                "prior account registry count", record.prior_account_registry_count
            ),
            digest(record.prior_account_registry_commitment),
            binding(record.prior_source_binding),
            binding(record.resulting_source_binding),
            _require_nonnegative_int(
                "resulting registry count", record.resulting_registry_count
            ),
            digest(record.resulting_registry_commitment),
            record.reason,
        ]
    raise TypeError("execution reconciliation is not an admitted exact outcome")


def _encode_runtime_checkpoint_venue_execution_reconciliation_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project every registry outcome named by a selected bootstrap target.

    Like the fill reconciliation index this is governed by R15 section 2's
    selected-reference rule: ``insert_new``-only beside an append-only ledger, so
    unreferenced rows are omitted audit history and no whole-map cardinality
    check applies. A catch-up is appended for every
    ``CatchUpExecutionRegistry`` while a bootstrap target is refreshed only where
    one exists, the unresolved arm never advances ``checkpoint_input_id`` at all,
    and that field is replaced on each refresh -- so an unreferenced retained
    input is ordinary history, not a splice.
    """

    rows: list[object] = []
    for reference in _referenced_execution_reconciliation_inputs(book, selection):
        record = book._execution_reconciliation_by_input.get(
            _venue._input_index_key(reference.input_id)
        )
        if record is None:
            if reference.required:
                raise ValueError("required execution reconciliation is absent")
            continue
        if record.input_id != reference.input_id:
            raise ValueError(
                "reached execution reconciliation does not own its referenced input"
            )
        # Equality with the target that named it, not membership: a cross-scope
        # outcome would otherwise be admitted through another scope's target.
        if record.position_scope != reference.position_scope:
            raise ValueError(
                "reached execution reconciliation does not own its referencing scope"
            )
        rows.append(
            _require_bounded_checkpoint_row(
                _encode_runtime_checkpoint_venue_execution_reconciliation_row(record)
            )
        )
    return _checkpoint_collection("m2.venue.ExecutionReconciliations/v1", rows)


def _encode_runtime_checkpoint_venue_protection_cursor_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the protection cursor of each proof-selected scope.

    ``_protection_cursor_by_scope`` is an exact current selected-scope map (R16
    section 2): every present key must be one selected scope, so an entry outside the
    selection fails closed rather than being dropped.
    """

    scopes = _selected_position_scopes_from_selection(book, selection)
    rows: list[object] = []
    reached = 0
    for position_scope in scopes:
        cursor = book._protection_cursor_by_scope.get(
            _venue._position_scope_index_key(position_scope)
        )
        if cursor is None:
            continue
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.ProtectionCursor/v1",
                    _operations._encode_m2_position_scope(position_scope),
                    _require_nonnegative_int("cursor ordinal", cursor.ordinal),
                    _operations._encode_m2_bytes(cursor.head),
                    (
                        None
                        if cursor.mandate_id is None
                        else _operations._encode_m2_m1_atom(cursor.mandate_id)
                    ),
                    (
                        None
                        if cursor.execution_commitment is None
                        else _operations._encode_m2_bytes(cursor.execution_commitment)
                    ),
                    (
                        None
                        if cursor.execution_checkpoint is None
                        else _encode_runtime_checkpoint_venue_execution_checkpoint(
                            cursor.execution_checkpoint
                        )
                    ),
                ]
            )
        )
    if book._protection_cursor_by_scope.size != reached:
        raise ValueError(
            "protection cursor map retains a key outside the selected scope set"
        )
    return _checkpoint_collection("m2.venue.ProtectionCursors/v1", rows)


def _encode_runtime_checkpoint_venue_effect_scope(
    scope: _venue.VenueEffectScope,
) -> list[object]:
    """Encode the frozen 15-member venue effect scope."""

    atom = _operations._encode_m2_m1_atom
    return [
        "m2.venue.EffectScope/v1",
        atom(scope.generation),
        atom(scope.broker),
        atom(scope.environment),
        atom(scope.account),
        atom(scope.effect_id),
        atom(scope.request_occurrence_id),
        atom(scope.mandate_id),
        _checkpoint_enum("m1.venue.EffectKind", scope.kind),
        None if scope.client_order_id is None else atom(scope.client_order_id),
        atom(scope.symbol_id),
        _checkpoint_enum("m1.fills.ExecutionSide", scope.side),
        atom(scope.quantity),
        _operations._encode_m2_bytes(scope.economic_scope),
        None if scope.target_leg_key is None else atom(scope.target_leg_key),
    ]


def _encode_runtime_checkpoint_venue_acceptance_proof(
    proof: object,
    *,
    expected_scope: _venue.VenueEffectScope,
    expected_claim_occurrence_id: _identity.ClaimOccurrenceId | None,
) -> list[object]:
    """Encode one closure-evidence row after binding it to the current effect.

    Venue owns the private replay representation.  The checkpoint boundary admits
    only the exact immutable members it needs and proves that they still name the
    selected current effect; it must not depend on the venue's private replay type.
    """

    if type(expected_scope) is not _venue.VenueEffectScope:
        raise TypeError("expected acceptance scope must be exact VenueEffectScope")
    atom = _operations._encode_m2_m1_atom
    proof_scope = getattr(proof, "effect_scope", None)
    if type(proof_scope) is not _venue.VenueEffectScope:
        raise TypeError("acceptance proof scope must be exact VenueEffectScope")
    if proof_scope != expected_scope:
        raise ValueError("acceptance proof scope does not bind the selected effect")

    kind = getattr(proof, "kind", None)
    kind_value = getattr(kind, "value", None)
    if type(kind_value) is not str or kind_value not in {
        "NEVER_DISPATCHED",
        "CONTRACT_COMPLETE_RESPONSE",
        "COVERED_RECONCILIATION",
    }:
        raise ValueError("acceptance proof kind is not a frozen closure kind")

    claim_occurrence_id = getattr(proof, "claim_occurrence_id", None)
    if (
        claim_occurrence_id is not None
        and type(claim_occurrence_id) is not _identity.ClaimOccurrenceId
    ):
        raise TypeError("acceptance proof claim must be exact ClaimOccurrenceId")
    if claim_occurrence_id != expected_claim_occurrence_id:
        raise ValueError("acceptance proof claim does not bind the selected effect")
    if kind_value == "NEVER_DISPATCHED":
        if claim_occurrence_id is not None:
            raise ValueError("never-dispatched acceptance proof cannot name a claim")
    elif claim_occurrence_id is None:
        raise ValueError("external acceptance proof must name the selected claim")

    evidence_reference = getattr(proof, "evidence_reference", None)
    if type(evidence_reference) is not _identity.EvidenceReference:
        raise TypeError("acceptance proof evidence reference must be exact")
    evidence_digest = getattr(proof, "evidence_digest", None)
    if type(evidence_digest) is not bytes or len(evidence_digest) != 32:
        raise ValueError(
            "acceptance proof evidence digest must contain exactly 32 bytes"
        )
    return [
        "m2.venue.AcceptanceProof/v1",
        _checkpoint_enum("m1.venue.AcceptanceProofKind", kind),
        atom(expected_scope.effect_id),
        (None if claim_occurrence_id is None else atom(claim_occurrence_id)),
        atom(evidence_reference),
        _operations._encode_m2_bytes(evidence_digest),
    ]


def _encode_runtime_checkpoint_venue_effect_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project each proof-selected effect by direct current-owner key.

    R17 section 1: the selection proof is the sole membership and order witness, so
    rows are emitted in proof order and the projector never reads ``_effect_order``,
    ``_owner_order`` or any rank map. R18 section 1 fixes member 1 as the dense
    ``checkpoint_ordinal`` — the zero-based index of the row in its proof-selected
    family — which deliberately does not claim reducer insertion order.
    """

    atom = _operations._encode_m2_m1_atom
    relations = _selected_venue_relations(selection)
    seen: set[bytes] = set()
    rows: list[object] = []
    for ordinal, record in enumerate(selection.effects):
        effect_external = record.effect_external
        current = book._effect_by_id.get(_venue._effect_index_key(effect_external))
        if current is None:
            raise ValueError("selected effect has no current owner row")
        scope = current.effect.scope
        _require_selected_effect_current_relation(
            book, relations, current.effect, record, "effect"
        )
        order_key = _atom_order_key(effect_external)
        if order_key in seen:
            raise ValueError("selected effects retain a duplicate effect")
        seen.add(order_key)
        effect = current.effect
        contradictions: list[object] = [
            [
                "m2.venue.AcceptanceContradiction/v1",
                evidence_ordinal,
                atom(contradiction.leg_key),
                atom(contradiction.observation_id),
            ]
            for evidence_ordinal, contradiction in enumerate(
                effect.contradiction_evidence
            )
        ]
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.EffectCurrent/v1",
                    ordinal,
                    _encode_runtime_checkpoint_venue_effect_scope(scope),
                    _checkpoint_enum("m1.venue.BrokerEffectState", effect.state),
                    _checkpoint_enum(
                        "m1.venue.AcceptanceSetState", effect.acceptance_set_state
                    ),
                    (
                        None
                        if effect.claim_occurrence_id is None
                        else atom(effect.claim_occurrence_id)
                    ),
                    (
                        None
                        if effect.acceptance_proof is None
                        else _encode_runtime_checkpoint_venue_acceptance_proof(
                            effect.acceptance_proof,
                            expected_scope=scope,
                            expected_claim_occurrence_id=effect.claim_occurrence_id,
                        )
                    ),
                    _checkpoint_collection(
                        "m2.venue.Contradictions/v1", contradictions
                    ),
                    current.operator_epoch,
                    current.account_epoch,
                ]
            )
        )
    return _checkpoint_collection("m2.venue.Effects/v1", rows)


def _encode_runtime_checkpoint_venue_claim_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project each proof-selected dispatch claim by direct current-owner key.

    R20 section 2 keeps R17 proof-family order for database-selected venue families:
    rows are emitted in selection order and are never re-sorted, unlike the authority
    collections which use canonical semantic-key order. ``DispatchClaimRecord`` carries
    the repository surrogate effect ID, so each claim resolves through the selected
    effect family to the exact external identity before the direct-key lookup.
    """

    relations = _selected_venue_relations(selection)
    seen: set[bytes] = set()
    rows: list[object] = []
    for record in selection.claims:
        effect = relations.effects_by_id.get(record.effect_id)
        if effect is None:
            raise ValueError("selected dispatch claim names an unselected effect")
        effect_external = effect.effect_external
        claim = book._claim_by_effect.get(_venue._effect_index_key(effect_external))
        if claim is None:
            raise ValueError("selected dispatch claim has no current owner row")
        _require_selected_effect_scope(
            book, relations, claim.effect_scope, effect, "dispatch claim"
        )
        if (
            record.execution_profile_id != effect.execution_profile_id
            or claim.claim_occurrence_id != record.claim_occurrence_id
        ):
            raise ValueError(
                "reached dispatch claim disagrees with its selected record"
            )
        order_key = _atom_order_key(effect_external)
        if order_key in seen:
            raise ValueError("selected dispatch claims retain a duplicate effect")
        seen.add(order_key)
        rows.append(
            _require_bounded_checkpoint_row(
                [
                    "m2.venue.DispatchClaim/v1",
                    _operations._encode_m2_m1_atom(effect_external),
                    _operations._encode_m2_m1_atom(claim.claim_occurrence_id),
                ]
            )
        )
    return _checkpoint_collection("m2.venue.Claims/v1", rows)


def _encode_runtime_checkpoint_venue(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> tuple[list[object], bytes, bytes]:
    """Encode the frozen venue top row without serializing audit history."""

    if type(book) is not _venue.VenueRecoveryBook:
        raise TypeError("venue owner must be exact VenueRecoveryBook")
    effect_rows = _encode_runtime_checkpoint_venue_effect_rows(book, selection)
    authority_epoch_rows = _encode_runtime_checkpoint_venue_authority_epoch_rows(
        book, selection
    )
    high_water_rows = _encode_runtime_checkpoint_venue_high_water_rows(book, selection)
    owner_attempt_rows = _encode_runtime_checkpoint_venue_owner_attempt_rows(
        book, selection
    )
    correlation_rows = _encode_runtime_checkpoint_venue_correlation_rows(
        book, selection
    )
    coverage_provenance_rows = (
        _encode_runtime_checkpoint_venue_coverage_provenance_rows(book, selection)
    )
    broker_coverage_rows = _encode_runtime_checkpoint_venue_broker_coverage_rows(
        book, selection
    )
    human_coverage_rows = _encode_runtime_checkpoint_venue_human_coverage_rows(
        book, selection
    )
    closure_head_rows = _encode_runtime_checkpoint_venue_closure_head_rows(
        book, selection
    )
    execution_scope_rows = _encode_runtime_checkpoint_venue_execution_scope_rows(
        book, selection
    )
    protection_cursor_rows = _encode_runtime_checkpoint_venue_protection_cursor_rows(
        book, selection
    )
    reconciliation_rows = _encode_runtime_checkpoint_venue_reconciliation_rows(
        book, selection
    )
    bootstrap_target_rows = _encode_runtime_checkpoint_venue_bootstrap_target_rows(
        book, selection
    )
    execution_reconciliation_rows = (
        _encode_runtime_checkpoint_venue_execution_reconciliation_rows(book, selection)
    )
    claim_rows = _encode_runtime_checkpoint_venue_claim_rows(book, selection)
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
        authority_epoch_rows,
        effect_rows,
        claim_rows,
        owner_attempt_rows,
        correlation_rows,
        closure_head_rows,
        high_water_rows,
        human_coverage_rows,
        broker_coverage_rows,
        coverage_provenance_rows,
        reconciliation_rows,
        execution_reconciliation_rows,
        execution_scope_rows,
        bootstrap_target_rows,
        protection_cursor_rows,
    ]
    commitment = _checkpoint_row_commitment(b"execution-core/m2-venue/state/v1", row)
    source_owner_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-venue/source-owner/v1", row
    )
    row.append(_operations._encode_m2_bytes(commitment))
    return row, commitment, source_owner_commitment


def _encode_runtime_checkpoint_claim_permit(
    permit: _authority.AcquisitionClaimPermit,
) -> list[object]:
    """Encode the 21 semantic claim-permit members in exact contract order.

    ``commitment`` and ``_seal`` are derived from these members and are deliberately
    absent from the wire; the owning constructor re-derives them on decode. The permit
    is re-authenticated here rather than trusted, so a member tampered after minting
    cannot reach the checkpoint.
    """

    if type(permit) is not _authority.AcquisitionClaimPermit:
        raise TypeError("claim permit must be exact AcquisitionClaimPermit")
    if not _authority._acquisition_claim_permit_is_authentic(permit):
        raise ValueError("claim permit is not authority-authentic")
    return [
        "m2.authority.AcquisitionClaimPermit/v1",
        _operations._encode_m2_m1_atom(permit.input_id),
        _operations._encode_m2_m1_atom(permit.application_generation_id),
        _operations._encode_m2_position_scope(permit.position_scope),
        _operations._encode_m2_m1_atom(permit.session_id),
        _operations._encode_m2_m1_atom(permit.generation_id),
        _operations._encode_m2_m1_atom(permit.acquisition_mandate_id),
        _operations._encode_m2_m1_atom(permit.protection_mandate_id),
        _operations._encode_m2_bytes(permit.binding_commitment),
        _operations._encode_m2_bytes(
            permit.emergency_recovery_compatibility_commitment
        ),
        _operations._encode_m2_bytes(permit.controller_head),
        _require_nonnegative_int(
            "claim permit successor ordinal", permit.successor_ordinal
        ),
        _operations._encode_m2_bytes(permit.execution_snapshot_commitment),
        _operations._encode_m2_bytes(permit.scope_execution_commitment),
        _operations._encode_m2_bytes(permit.venue_commitment),
        _operations._encode_m2_bytes(permit.authority_context_commitment),
        (
            None
            if permit.protection_commitment is None
            else _operations._encode_m2_bytes(permit.protection_commitment)
        ),
        _operations._encode_m2_m1_atom(permit.effect_id),
        _operations._encode_m2_m1_atom(permit.claim_occurrence_id),
        _operations._encode_m2_bytes(permit.currentness_commitment),
        _operations._encode_m2_bytes(permit.descriptor_commitment),
        _operations._encode_m2_bytes(permit.active_commitment),
    ]


def _require_bounded_checkpoint_row(row: list[object]) -> list[object]:
    """Contract 2.4: one canonical semantic row is at most 2,097,152 bytes.

    The limit is a refusal, never a truncation: an oversize row cannot produce a
    serving checkpoint.
    """

    if len(_encode_canonical_json(row)) > _MAX_RUNTIME_CHECKPOINT_ROW_BYTES:
        raise ValueError("checkpoint row exceeds its canonical byte limit")
    return row


def _encode_runtime_checkpoint_claim_row(
    claim: _authority.ClaimEffect | _authority.ClaimAcquisitionEffect,
) -> list[object]:
    """Encode the exact ClaimRow variant for one authority-sealed claim."""

    if type(claim) is _authority.ClaimEffect:
        return [
            "m2.authority.ClaimEffect/v1",
            _operations._encode_m2_m1_atom(claim.input_id),
            _operations._encode_m2_m1_atom(claim.effect_id),
            _operations._encode_m2_m1_atom(claim.claim_occurrence_id),
        ]
    if type(claim) is _authority.ClaimAcquisitionEffect:
        return [
            "m2.authority.ClaimAcquisitionEffect/v1",
            _operations._encode_m2_m1_atom(claim.input_id),
            _operations._encode_m2_m1_atom(claim.effect_id),
            _operations._encode_m2_m1_atom(claim.claim_occurrence_id),
            _encode_runtime_checkpoint_claim_permit(claim.permit),
        ]
    raise TypeError("claim must be exact ClaimEffect or ClaimAcquisitionEffect")


def _encode_runtime_checkpoint_effect_authorization_row(
    authorization: _authority._EffectAuthorization,
    claim: _authority.ClaimEffect | _authority.ClaimAcquisitionEffect | None,
) -> list[object]:
    """Encode one effect authorization with its claim nested beneath it.

    The frozen contract requires every claim to name the same effect as the
    authorization it sits under, so the relation is proved here rather than assumed
    from the map key that reached them.
    """

    if type(authorization) is not _authority._EffectAuthorization:
        raise TypeError("effect authorization must be exact _EffectAuthorization")
    if type(authorization.request) is not _authority.BrokerEffectRequest:
        raise TypeError(
            "effect authorization request must be exact BrokerEffectRequest"
        )
    claim_row: list[object] | None = None
    if claim is not None:
        if claim.effect_id != authorization.request.effect_id:
            raise ValueError("claim does not name the same effect as its authorization")
        claim_row = _encode_runtime_checkpoint_claim_row(claim)
    row: list[object] = [
        "m2.authority.EffectAuthorization/v1",
        _operations._encode_m2_broker_effect_request(authorization.request),
        _operations._encode_m2_m1_atom(authorization.session_id),
        (
            None
            if authorization.manual_flatten_id is None
            else _operations._encode_m2_m1_atom(authorization.manual_flatten_id)
        ),
        (
            None
            if authorization.emergency_grant_id is None
            else _operations._encode_m2_m1_atom(authorization.emergency_grant_id)
        ),
        claim_row,
    ]
    return _require_bounded_checkpoint_row(row)


def _encode_runtime_checkpoint_effect_authorization_rows(
    state: _authority.ExecutionAuthorityState,
    selected_effect_ids: tuple[_identity.EffectId, ...],
) -> list[object]:
    """Project the authorization reached by each proof-selected effect.

    ``_effect_authority_by_id``, ``_claim_by_effect`` and ``_claim_by_occurrence`` are
    R20 section 2 permitted authenticated supersets: only rows reached by a selected
    effect are checkpointed, and their whole-map sizes are never compared against the
    selection. Unrelated closed-effect history is omitted, not refused.

    Two relations are proved rather than assumed from the key that reached the row: the
    authorization must own the selected effect ID, and a claim must resolve back to the
    same row through its canonical occurrence index.
    """

    reached: dict[bytes, list[object]] = {}
    for effect_id in selected_effect_ids:
        if type(effect_id) is not _identity.EffectId:
            raise TypeError("selected effect ID must be exact EffectId")
        effect_key = _authority._effect_key(effect_id)
        authorization = state._effect_authority_by_id.get(effect_key)
        if authorization is None:
            continue
        if type(authorization) is not _authority._EffectAuthorization:
            raise TypeError("effect authorization must be exact _EffectAuthorization")
        if authorization.request.effect_id != effect_id:
            raise ValueError(
                "reached authorization does not own its selected effect ID"
            )
        claim = state._claim_by_effect.get(effect_key)
        if claim is not None:
            resolved = state._claim_by_occurrence.get(
                _authority._claim_key(claim.claim_occurrence_id)
            )
            if resolved is not claim:
                raise ValueError(
                    "claim does not resolve to the same row by canonical occurrence"
                )
        order_key = _atom_order_key(effect_id)
        if order_key in reached:
            raise ValueError("selected effects retain a duplicate effect ID")
        reached[order_key] = _encode_runtime_checkpoint_effect_authorization_row(
            authorization, claim
        )
    return _checkpoint_collection(
        "m2.authority.EffectAuthorizations/v1",
        [reached[order_key] for order_key in sorted(reached)],
    )


def _encode_runtime_checkpoint_manual_row(
    manual: _authority._ManualFlatten,
) -> list[object]:
    """Encode one payload-owned manual flatten row under the R20 section 3 rules."""

    if type(manual) is not _authority._ManualFlatten:
        raise TypeError("manual flatten must be exact _ManualFlatten")
    if type(manual.phase) is not _authority._FlattenPhase:
        raise TypeError("manual flatten phase must be exact _FlattenPhase")
    cancel_effect_ids = manual.cancel_effect_ids
    if type(cancel_effect_ids) is not tuple:
        raise TypeError("manual cancel effect IDs must be an exact tuple")
    if len(cancel_effect_ids) > _MAX_CHECKPOINT_COLLECTION_ROWS:
        raise ValueError("manual cancel effects exceed the bounded row cap")
    for effect_id in cancel_effect_ids:
        if type(effect_id) is not _identity.EffectId:
            raise TypeError("manual cancel effect must be exact EffectId")
    ordered = sorted(cancel_effect_ids, key=_atom_order_key)
    if len({_atom_order_key(effect_id) for effect_id in ordered}) != len(ordered):
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

    R16 section 2 fixes the per-family rule, and the two maps sit in different
    categories. ``_manual_flatten_by_scope`` is an exact current selected-scope map, so
    every present key must be a selected scope and a dangling entry fails closed.
    ``_manual_by_id`` holds directly reachable current rows, where "older unreachable
    IDs are omitted" — comparing a selected subset against its whole size is the
    cardinality mutant R16 requires to fail, so it is deliberately not compared here.

    Ameen ratified this rule on 2026-08-24, superseding R15 section 3's conflicting
    cardinality sentences (36-R16-MANUAL-RULE-RATIFICATION.md). The strict refusals
    it retains — missing, stale, duplicate, cross-scope — are each pinned by name.
    """

    reached: dict[bytes, _authority._ManualFlatten] = {}
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
        if type(manual) is not _authority._ManualFlatten:
            raise TypeError("manual flatten must be exact _ManualFlatten")
        if type(manual.command) is not _authority.BeginManualFlatten:
            raise TypeError("manual flatten command must be exact BeginManualFlatten")
        if manual.command.flatten_id != flatten_id:
            raise ValueError("reached manual flatten does not own its index flatten ID")
        if manual.command.symbol_id != position_scope.symbol_id:
            raise ValueError(
                "reached manual flatten does not own its selected scope symbol"
            )
        order_key = _atom_order_key(flatten_id)
        if order_key in reached:
            raise ValueError("selected scopes retain a duplicate manual flatten")
        reached[order_key] = manual
    if state._manual_flatten_by_scope.size != len(reached):
        raise ValueError("manual flatten scope index retains an unselected scope")
    return _checkpoint_collection(
        "m2.authority.ManualFlattens/v1",
        [
            _encode_runtime_checkpoint_manual_row(reached[order_key])
            for order_key in sorted(reached)
        ],
    )


def _encode_runtime_checkpoint_acquisition_effect_permit(
    permit: _authority.AcquisitionEffectPermit,
) -> list[object]:
    """Encode the 21 semantic members of one sealed acquisition effect permit.

    ``commitment`` and ``_seal`` are derived and deliberately absent from the wire.
    The permit is re-authenticated rather than trusted, exactly as the claim permit
    beside it is, so a member tampered after minting cannot reach the checkpoint.
    """

    if type(permit) is not _authority.AcquisitionEffectPermit:
        raise TypeError("effect permit must be exact AcquisitionEffectPermit")
    if not _authority._acquisition_effect_permit_is_authentic(permit):
        raise ValueError("effect permit is not authority-authentic")
    atom = _operations._encode_m2_m1_atom
    digest = _operations._encode_m2_bytes
    return [
        "m2.authority.AcquisitionEffectPermit/v1",
        atom(permit.input_id),
        atom(permit.application_generation_id),
        _operations._encode_m2_position_scope(permit.position_scope),
        atom(permit.session_id),
        atom(permit.generation_id),
        atom(permit.acquisition_mandate_id),
        atom(permit.protection_mandate_id),
        digest(permit.binding_commitment),
        digest(permit.emergency_recovery_compatibility_commitment),
        digest(permit.predecessor_controller_head),
        digest(permit.controller_head),
        _require_nonnegative_int(
            "effect permit successor ordinal", permit.successor_ordinal
        ),
        digest(permit.execution_snapshot_commitment),
        digest(permit.scope_execution_commitment),
        digest(permit.venue_commitment),
        digest(permit.authority_context_commitment),
        (
            None
            if permit.protection_commitment is None
            else digest(permit.protection_commitment)
        ),
        _operations._encode_m2_acquisition_effect_terms(permit.terms),
        atom(permit.effect_id),
        atom(permit.request_occurrence_id),
        atom(permit.client_order_id),
    ]


def _encode_runtime_checkpoint_acquisition_currentness(
    entry: _authority._AcquisitionCurrentnessEntry,
) -> list[object]:
    """Encode the 15 semantic members of one sealed scope currentness entry."""

    if type(entry) is not _authority._AcquisitionCurrentnessEntry:
        raise TypeError("currentness must be exact _AcquisitionCurrentnessEntry")
    if not _authority._acquisition_currentness_entry_is_authentic(entry):
        raise ValueError("currentness entry is not authority-authentic")
    atom = _operations._encode_m2_m1_atom
    digest = _operations._encode_m2_bytes
    return [
        "m2.authority.AcquisitionCurrentness/v1",
        _checkpoint_enum(
            "m1.authority.AcquisitionCurrentnessSourceKind", entry.source_kind
        ),
        atom(entry.application_generation_id),
        _operations._encode_m2_position_scope(entry.position_scope),
        atom(entry.session_id),
        atom(entry.generation_id),
        atom(entry.acquisition_mandate_id),
        atom(entry.protection_mandate_id),
        digest(entry.binding_commitment),
        digest(entry.emergency_recovery_compatibility_commitment),
        digest(entry.controller_head),
        _require_nonnegative_int(
            "currentness successor ordinal", entry.successor_ordinal
        ),
        digest(entry.scope_execution_commitment),
        digest(entry.venue_commitment),
        (
            None
            if entry.protection_commitment is None
            else digest(entry.protection_commitment)
        ),
        digest(entry.predecessor_slot_commitment),
    ]


def _acquisition_slot_value_reference(
    value: object, subject: str
) -> tuple[_identity.EffectId, bytes] | None:
    """Reduce a scope-slot value to the one descriptor reference it names."""

    if value is None:
        return None
    if type(value) is _authority._AcquisitionEffectDescriptor:
        if not _authority._acquisition_effect_descriptor_is_authentic(value):
            raise ValueError(f"{subject} descriptor is not authority-authentic")
        return value.permit.effect_id, value.commitment
    if type(value) is _authority._AcquisitionActiveEffect:
        if not _authority._acquisition_active_effect_is_authentic(value):
            raise ValueError(f"{subject} active record is not authority-authentic")
        return value.effect_id, value.descriptor_commitment
    if type(value) is _authority._AcquisitionInactiveSlot:
        if not _authority._acquisition_inactive_slot_is_authentic(value):
            raise ValueError(f"{subject} inactive slot is not authority-authentic")
        return value.predecessor_effect_id, value.predecessor_descriptor_commitment
    raise TypeError(f"{subject} is not an admitted acquisition slot value")


def _encode_runtime_checkpoint_acquisition_slot_value(
    descriptor: object, active: object
) -> tuple[list[object], tuple[_identity.EffectId, bytes] | None]:
    """Encode the single SlotValue the descriptor and active indexes must agree on.

    Contract 07 kept a separate member per index; R2 collapses them because the two
    are required to be the same variant naming the same effect.  Encoding one value
    from both indexes is what makes a mixed pair unrepresentable rather than merely
    discouraged: disagreement raises here instead of producing a wire row.

    Returns the row beside the effect ID it names, so the caller collects descriptor
    references without re-reading the encoded atom back out of the row.
    """

    if (descriptor is None) != (active is None):
        raise ValueError("acquisition slot retains a partial descriptor/active pair")
    if descriptor is None:
        return ["m2.authority.AcquisitionSlotEmpty/v1"], None
    descriptor_reference = _acquisition_slot_value_reference(descriptor, "slot")
    active_reference = _acquisition_slot_value_reference(active, "slot active")
    if descriptor_reference != active_reference:
        raise ValueError("acquisition slot descriptor and active disagree")
    atom = _operations._encode_m2_m1_atom
    if type(descriptor) is _authority._AcquisitionInactiveSlot:
        if type(active) is not _authority._AcquisitionInactiveSlot:
            raise ValueError("acquisition slot mixes an inactive and active variant")
        if descriptor.successor_generation_id != active.successor_generation_id:
            raise ValueError("acquisition slot inactive successors disagree")
        return [
            "m2.authority.AcquisitionSlotInactive/v1",
            atom(descriptor.predecessor_effect_id),
            _operations._encode_m2_bytes(descriptor.predecessor_descriptor_commitment),
            atom(descriptor.successor_generation_id),
        ], (
            descriptor.predecessor_effect_id,
            descriptor.predecessor_descriptor_commitment,
        )
    if type(active) is _authority._AcquisitionInactiveSlot:
        raise ValueError("acquisition slot mixes an active and inactive variant")
    if descriptor_reference is None:
        raise ValueError("acquisition slot names no descriptor reference")
    effect_id, descriptor_commitment = descriptor_reference
    return [
        "m2.authority.AcquisitionSlotActive/v1",
        atom(effect_id),
        _operations._encode_m2_bytes(descriptor_commitment),
    ], (effect_id, descriptor_commitment)


@_dataclass(frozen=True, slots=True)
class _AcquisitionSlotReference:
    """The exact descriptor/currentness object a retained slot commits to."""

    effect_id: _identity.EffectId
    position_scope: _fills.PositionScope
    descriptor_commitment: bytes
    currentness: _authority._AcquisitionCurrentnessEntry


def _encode_runtime_checkpoint_acquisition_slot_rows(
    state: _authority.ExecutionAuthorityState,
    application_generation_id: _identity.ApplicationGenerationId,
    selected_position_scopes: tuple[_fills.PositionScope, ...],
) -> tuple[list[object], tuple[_AcquisitionSlotReference, ...]]:
    """Project one slot row per selected scope and report the effects it names.

    All three scope maps are exact current selected-scope maps under the R16 section 2
    taxonomy, so each is compared against *its own* reached count: comparing all three
    against the slot count would let an unselected-scope entry hide behind a selected
    scope that happens to carry no descriptor.  R20 section 2 orders these rows by the
    canonical ``PositionScope`` bytes rather than by any map or input order.
    """

    reached: dict[bytes, list[object]] = {}
    referenced: list[_AcquisitionSlotReference] = []
    reached_descriptors = 0
    reached_actives = 0
    for position_scope in selected_position_scopes:
        slot_key = _authority._acquisition_scope_key(
            application_generation_id, position_scope
        )
        currentness = state._acquisition_currentness_by_scope.get(slot_key)
        descriptor = state._acquisition_descriptor_by_scope.get(slot_key)
        active = state._acquisition_active_by_scope.get(slot_key)
        if currentness is None:
            if descriptor is not None or active is not None:
                raise ValueError("acquisition slot omits its required currentness")
            continue
        if currentness.application_generation_id != application_generation_id:
            raise ValueError(
                "reached currentness leaves the selected application generation"
            )
        if currentness.position_scope != position_scope:
            raise ValueError("reached currentness does not own its selected scope")
        reached_descriptors += descriptor is not None
        reached_actives += active is not None
        slot_value, descriptor_reference = (
            _encode_runtime_checkpoint_acquisition_slot_value(descriptor, active)
        )
        if descriptor_reference is not None:
            effect_id, descriptor_commitment = descriptor_reference
            referenced.append(
                _AcquisitionSlotReference(
                    effect_id, position_scope, descriptor_commitment, currentness
                )
            )
        order_key = _array_order_key(
            _operations._encode_m2_position_scope(position_scope)
        )
        if order_key in reached:
            raise ValueError("selected scopes retain a duplicate acquisition slot")
        reached[order_key] = _require_bounded_checkpoint_row(
            [
                "m2.authority.AcquisitionSlot/v1",
                _operations._encode_m2_position_scope(position_scope),
                _encode_runtime_checkpoint_acquisition_currentness(currentness),
                slot_value,
            ]
        )
    for name, index, count in (
        ("currentness", state._acquisition_currentness_by_scope, len(reached)),
        ("descriptor", state._acquisition_descriptor_by_scope, reached_descriptors),
        ("active", state._acquisition_active_by_scope, reached_actives),
    ):
        if index.size != count:
            raise ValueError(
                f"acquisition {name} scope index retains an unselected scope"
            )
    rows = _checkpoint_collection(
        "m2.authority.AcquisitionSlots/v1",
        [reached[order_key] for order_key in sorted(reached)],
    )
    return rows, tuple(referenced)


def _require_acquisition_currentness_matches_descriptor(
    currentness: _authority._AcquisitionCurrentnessEntry,
    permit: _authority.AcquisitionEffectPermit,
) -> None:
    """Require one slot's currentness and descriptor to name the same authority."""

    if not _authority._acquisition_currentness_entry_is_authentic(currentness):
        raise ValueError("slot currentness is not authority-authentic")
    if not _authority._acquisition_effect_permit_is_authentic(permit):
        raise ValueError("slot descriptor permit is not authority-authentic")
    if (
        currentness.application_generation_id != permit.application_generation_id
        or currentness.position_scope != permit.position_scope
        or currentness.session_id != permit.session_id
        or currentness.generation_id != permit.generation_id
        or currentness.acquisition_mandate_id != permit.acquisition_mandate_id
        or currentness.protection_mandate_id != permit.protection_mandate_id
        or currentness.binding_commitment != permit.binding_commitment
        or currentness.emergency_recovery_compatibility_commitment
        != permit.emergency_recovery_compatibility_commitment
        or currentness.controller_head != permit.controller_head
        or currentness.successor_ordinal != permit.successor_ordinal
        or currentness.scope_execution_commitment != permit.scope_execution_commitment
        or currentness.venue_commitment != permit.venue_commitment
        or currentness.protection_commitment != permit.protection_commitment
    ):
        raise ValueError(
            "slot currentness and descriptor do not name the same authority"
        )


def _encode_runtime_checkpoint_acquisition_descriptor_rows(
    state: _authority.ExecutionAuthorityState,
    application_generation_id: _identity.ApplicationGenerationId,
    slot_references: tuple[_AcquisitionSlotReference, ...],
    selected_effect_ids: tuple[_identity.EffectId, ...],
) -> list[object]:
    """Project every descriptor named by a retained slot or a selected effect.

    ``_acquisition_descriptor_by_effect`` is a permitted authenticated superset in the
    R16 section 2 taxonomy: it keeps predecessor descriptors that no current row
    reaches, so it deliberately gets no whole-map cardinality check.  A slot
    reference that does not resolve is still a refusal, because a slot names only a
    retained descriptor.  R20 section 2 orders the rows by canonical effect ID.

    REV-0078 P1-2: the effect ID alone bridged an authentic descriptor for one
    scope onto another selected scope's slot. Each slot reference now carries the
    referencing slot's position scope, and the resolved permit must own that
    scope and the selected application generation exactly.
    """

    reached: dict[bytes, list[object]] = {}
    for effect_id, slot_reference, required in (
        *((reference.effect_id, reference, True) for reference in slot_references),
        *((effect_id, None, False) for effect_id in selected_effect_ids),
    ):
        descriptor = state._acquisition_descriptor_by_effect.get(
            _authority._effect_key(effect_id)
        )
        if descriptor is None:
            if required:
                raise ValueError("acquisition slot names an absent descriptor")
            continue
        if type(descriptor) is not _authority._AcquisitionEffectDescriptor:
            raise TypeError("descriptor must be exact _AcquisitionEffectDescriptor")
        if not _authority._acquisition_effect_descriptor_is_authentic(descriptor):
            raise ValueError("reached descriptor is not authority-authentic")
        if descriptor.permit.effect_id != effect_id:
            raise ValueError("reached descriptor does not own its index effect ID")
        if descriptor.permit.application_generation_id != application_generation_id:
            raise ValueError(
                "reached descriptor leaves the selected application generation"
            )
        if (
            slot_reference is not None
            and descriptor.permit.position_scope != slot_reference.position_scope
        ):
            raise ValueError(
                "reached descriptor does not own its referencing slot scope"
            )
        if slot_reference is not None:
            if descriptor.commitment != slot_reference.descriptor_commitment:
                raise ValueError(
                    "reached descriptor disagrees with its slot commitment"
                )
            _require_acquisition_currentness_matches_descriptor(
                slot_reference.currentness, descriptor.permit
            )
        order_key = _atom_order_key(effect_id)
        if order_key in reached:
            continue
        reached[order_key] = _require_bounded_checkpoint_row(
            [
                "m2.authority.AcquisitionDescriptor/v1",
                _operations._encode_m2_m1_atom(effect_id),
                _encode_runtime_checkpoint_acquisition_effect_permit(descriptor.permit),
            ]
        )
    return _checkpoint_collection(
        "m2.authority.AcquisitionDescriptors/v1",
        [reached[order_key] for order_key in sorted(reached)],
    )


def _encode_runtime_checkpoint_emergency_grant(
    grant: _authority._EmergencyGrant,
) -> list[object]:
    """Encode the frozen 8-member emergency grant row.

    The grant is a plain sealed-by-construction dataclass: it carries no derived
    commitment, so re-running its own shape validation is the whole authenticity
    check available here.
    """

    if type(grant) is not _authority._EmergencyGrant:
        raise TypeError("emergency grant must be exact _EmergencyGrant")
    grant.__post_init__()
    atom = _operations._encode_m2_m1_atom
    return [
        "m2.authority.EmergencyGrant/v1",
        atom(grant.grant_id),
        atom(grant.account),
        atom(grant.symbol_id),
        atom(grant.session_id),
        atom(grant.actor),
        grant.reason,
        atom(grant.evidence_reference),
    ]


def _encode_runtime_checkpoint_authority(
    state: _authority.ExecutionAuthorityState,
    venue_commitment: bytes,
    application_generation_id: _identity.ApplicationGenerationId,
    selected_position_scopes: tuple[_fills.PositionScope, ...],
    selected_effect_ids: tuple[_identity.EffectId, ...],
) -> tuple[list[object], bytes, bytes]:
    """Encode the corrected R2 14-member authority top row from current owner maps."""

    if type(state) is not _authority.ExecutionAuthorityState:
        raise TypeError("authority owner must be exact ExecutionAuthorityState")
    _authority._validate_authority_state(state)
    manual_rows = _encode_runtime_checkpoint_manual_rows(
        state, application_generation_id, selected_position_scopes
    )
    effect_authorization_rows = _encode_runtime_checkpoint_effect_authorization_rows(
        state, selected_effect_ids
    )
    slot_rows, slot_effect_ids = _encode_runtime_checkpoint_acquisition_slot_rows(
        state, application_generation_id, selected_position_scopes
    )
    descriptor_rows = _encode_runtime_checkpoint_acquisition_descriptor_rows(
        state, application_generation_id, slot_effect_ids, selected_effect_ids
    )
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
        (
            None
            if state._emergency_grant is None
            else _encode_runtime_checkpoint_emergency_grant(state._emergency_grant)
        ),
        effect_authorization_rows,
        manual_rows,
        descriptor_rows,
        slot_rows,
    ]
    commitment = _checkpoint_row_commitment(
        b"execution-core/m2-authority/checkpoint/v1", row
    )
    source_owner_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-authority/source-owner/v1", row
    )
    row.append(_operations._encode_m2_bytes(commitment))
    return row, commitment, source_owner_commitment


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
        _encode_runtime_checkpoint_venue(venue, selection_proof._selection)
    )
    selected_effect_ids = tuple(
        record.effect_external for record in selection_proof._selection.effects
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
    (
        authority_wire,
        authority_commitment,
        authority_source_owner_commitment,
    ) = _encode_runtime_checkpoint_authority(
        authority,
        venue_commitment,
        request.application_generation_id,
        selected_position_scopes,
        selected_effect_ids,
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
            venue_context = venue.project_acquisition_context(
                execution,
                position_scope,
            )
            if (
                not venue_context.matches_current(
                    venue,
                    execution,
                    venue_scope.generation,
                    position_scope,
                )
                or acquisition.application_generation_id
                != request.application_generation_id
                or acquisition.position_scope != position_scope
                or acquisition._controller.live_generation_id
                != controller_record.live_acquisition_generation_id
                or acquisition.scope_execution_commitment
                != venue_context.scope_execution_commitment
                or acquisition.venue_commitment != venue_context.commitment
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
        authority_owner_commitment=authority_source_owner_commitment,
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


def _decode_m2_execution_checkpoint_state(
    value: object,
) -> _position._M2ExecutionState:
    """Decode one authentic but still non-serving execution checkpoint state."""

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
    decoded = _position._m2_execution_state_from_checkpoint_fields(decoded_fields)
    retained_commitment = _operations._decode_m2_bytes(
        "execution state commitment", fields[19]
    )
    if retained_commitment != decoded.commitment:
        raise ValueError("execution state is not authentic")
    if _encode_m2_execution_state_component(decoded) != value:
        raise ValueError("execution state component is not canonical")
    return decoded


def _decode_m2_execution_state_component(
    value: object,
    proof: _position._M2ExecutionObservationProof,
) -> _position._M2ExecutionState:
    """Decode only through the owner's aggregate-bound direct-proof seam."""

    decoded = _decode_m2_execution_checkpoint_state(value)
    return _position._m2_execution_state_from_direct_proof(decoded, proof)


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


@_dataclass(frozen=True, slots=True)
class _CompactRuntimeCheckpointOwners:
    """Non-serving compact owners bound to one loaded C0 and successor proof."""

    source_checkpoint: RuntimeCheckpointEnvelope
    selection_proof: _records.RuntimeCheckpointSelectionProof
    venue: _venue.VenueRecoveryBook
    authority: _authority.ExecutionAuthorityState
    scope_owners: tuple[_RuntimeCheckpointScopeOwners, ...]


def _decode_checkpoint_enum_value(
    name: str,
    value: object,
    owner: str,
    expected: type[_Any],
) -> _Any:
    if (
        type(value) is not list
        or len(value) != 2
        or value[0] != owner
        or type(value[1]) is not str
    ):
        raise ValueError(f"{name} is not an exact {owner} enum")
    try:
        decoded = expected(value[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} has an unadmitted value") from exc
    if _checkpoint_enum(owner, decoded) != value:
        raise ValueError(f"{name} is not canonical")
    return decoded


def _decode_checkpoint_collection_rows(
    value: object,
    tag: str,
) -> tuple[object, ...]:
    _validate_checkpoint_collection(value, tag)
    assert type(value) is list and type(value[2]) is list
    return tuple(value[2])


def _decode_compact_venue_effect_scope(value: object) -> _venue.VenueEffectScope:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.EffectScope/v1",
        14,
    )
    scope = _venue.VenueEffectScope(
        _operations._decode_m2_m1_as(
            "venue effect application generation",
            fields[0],
            _identity.ApplicationGenerationId,
        ),
        _operations._decode_m2_m1_as(
            "venue effect broker", fields[1], _identity.BrokerId
        ),
        _operations._decode_m2_m1_as(
            "venue effect environment", fields[2], _identity.EnvironmentId
        ),
        _operations._decode_m2_m1_as(
            "venue effect account", fields[3], _identity.AccountId
        ),
        _operations._decode_m2_m1_as("venue effect id", fields[4], _identity.EffectId),
        _operations._decode_m2_m1_as(
            "venue effect request occurrence",
            fields[5],
            _identity.RequestOccurrenceId,
        ),
        _operations._decode_m2_m1_as(
            "venue effect mandate", fields[6], _identity.MandateId
        ),
        _decode_checkpoint_enum_value(
            "venue effect kind",
            fields[7],
            "m1.venue.EffectKind",
            _venue.EffectKind,
        ),
        (
            None
            if fields[8] is None
            else _operations._decode_m2_m1_as(
                "venue effect client order",
                fields[8],
                _identity.ClientOrderId,
            )
        ),
        _operations._decode_m2_m1_as(
            "venue effect symbol", fields[9], _identity.SymbolId
        ),
        _decode_checkpoint_enum_value(
            "venue effect side",
            fields[10],
            "m1.fills.ExecutionSide",
            _fills.ExecutionSide,
        ),
        _operations._decode_m2_m1_as(
            "venue effect quantity", fields[11], _values.Quantity
        ),
        _operations._decode_m2_bytes("venue effect economic scope", fields[12]),
        (
            None
            if fields[13] is None
            else _operations._decode_m2_m1_as(
                "venue effect target leg", fields[13], _identity.VenueLegKey
            )
        ),
    )
    if _encode_runtime_checkpoint_venue_effect_scope(scope) != value:
        raise ValueError("venue effect scope is not compact-canonical")
    return scope


def _decode_compact_venue_acceptance_proof(
    value: object,
    *,
    effect_scope: _venue.VenueEffectScope,
    claim_occurrence_id: _identity.ClaimOccurrenceId | None,
) -> _venue.AcceptanceProof:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.AcceptanceProof/v1",
        5,
    )
    proof = _venue.AcceptanceProof(
        _decode_checkpoint_enum_value(
            "venue acceptance proof kind",
            fields[0],
            "m1.venue.AcceptanceProofKind",
            _venue.AcceptanceProofKind,
        ),
        effect_scope,
        (
            None
            if fields[2] is None
            else _operations._decode_m2_m1_as(
                "venue acceptance proof claim",
                fields[2],
                _identity.ClaimOccurrenceId,
            )
        ),
        _operations._decode_m2_m1_as(
            "venue acceptance proof evidence",
            fields[3],
            _identity.EvidenceReference,
        ),
        _operations._decode_m2_bytes("venue acceptance proof digest", fields[4]),
    )
    if (
        _operations._decode_m2_m1_as(
            "venue acceptance proof effect", fields[1], _identity.EffectId
        )
        != effect_scope.effect_id
        or proof.claim_occurrence_id != claim_occurrence_id
        or _encode_runtime_checkpoint_venue_acceptance_proof(
            proof,
            expected_scope=effect_scope,
            expected_claim_occurrence_id=claim_occurrence_id,
        )
        != value
    ):
        raise ValueError("venue acceptance proof is stale or spliced")
    return proof


def _decode_compact_venue_effect_row(
    value: object,
    *,
    checkpoint_ordinal: int,
) -> tuple[_venue._EffectCurrent, tuple[_venue.AcceptanceContradiction, ...]]:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.EffectCurrent/v1",
        9,
    )
    if (
        _operations._require_exact_int("venue effect checkpoint ordinal", fields[0])
        != checkpoint_ordinal
    ):
        raise ValueError("venue effect checkpoint ordinals are not dense")
    scope = _decode_compact_venue_effect_scope(fields[1])
    claim_occurrence_id = (
        None
        if fields[4] is None
        else _operations._decode_m2_m1_as(
            "venue effect claim occurrence",
            fields[4],
            _identity.ClaimOccurrenceId,
        )
    )
    acceptance_proof = (
        None
        if fields[5] is None
        else _decode_compact_venue_acceptance_proof(
            fields[5],
            effect_scope=scope,
            claim_occurrence_id=claim_occurrence_id,
        )
    )
    contradiction_rows = _decode_checkpoint_collection_rows(
        fields[6],
        "m2.venue.Contradictions/v1",
    )
    contradictions: list[_venue.AcceptanceContradiction] = []
    for ordinal, row in enumerate(contradiction_rows):
        contradiction_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.AcceptanceContradiction/v1",
            3,
        )
        if (
            _operations._require_exact_int(
                "venue contradiction ordinal", contradiction_fields[0]
            )
            != ordinal
        ):
            raise ValueError("venue contradiction ordinals are not dense")
        contradictions.append(
            _venue.AcceptanceContradiction(
                _operations._decode_m2_m1_as(
                    "venue contradiction leg",
                    contradiction_fields[1],
                    _identity.VenueLegKey,
                ),
                _operations._decode_m2_m1_as(
                    "venue contradiction observation",
                    contradiction_fields[2],
                    _identity.VenueObservationId,
                ),
            )
        )
    effect = _venue.BrokerEffect(
        scope,
        _decode_checkpoint_enum_value(
            "venue effect state",
            fields[2],
            "m1.venue.BrokerEffectState",
            _venue.BrokerEffectState,
        ),
        _decode_checkpoint_enum_value(
            "venue acceptance set state",
            fields[3],
            "m1.venue.AcceptanceSetState",
            _venue.AcceptanceSetState,
        ),
        claim_occurrence_id,
        acceptance_proof,
        (),
    )

    def _optional_epoch(name: str, candidate: object) -> int | None:
        if candidate is None:
            return None
        epoch = _operations._require_exact_int(name, candidate)
        if epoch < 0:
            raise ValueError(f"{name} must be non-negative")
        return epoch

    current = _venue._EffectCurrent(
        effect,
        _optional_epoch("venue effect operator epoch", fields[7]),
        _optional_epoch("venue effect account epoch", fields[8]),
    )
    expected_contradictions = _checkpoint_collection(
        "m2.venue.Contradictions/v1",
        [
            [
                "m2.venue.AcceptanceContradiction/v1",
                ordinal,
                _operations._encode_m2_m1_atom(contradiction.leg_key),
                _operations._encode_m2_m1_atom(contradiction.observation_id),
            ]
            for ordinal, contradiction in enumerate(contradictions)
        ],
    )
    expected = [
        "m2.venue.EffectCurrent/v1",
        checkpoint_ordinal,
        _encode_runtime_checkpoint_venue_effect_scope(scope),
        _checkpoint_enum("m1.venue.BrokerEffectState", effect.state),
        _checkpoint_enum("m1.venue.AcceptanceSetState", effect.acceptance_set_state),
        (
            None
            if claim_occurrence_id is None
            else _operations._encode_m2_m1_atom(claim_occurrence_id)
        ),
        (
            None
            if acceptance_proof is None
            else _encode_runtime_checkpoint_venue_acceptance_proof(
                acceptance_proof,
                expected_scope=scope,
                expected_claim_occurrence_id=claim_occurrence_id,
            )
        ),
        expected_contradictions,
        current.operator_epoch,
        current.account_epoch,
    ]
    if expected != value:
        raise ValueError("venue effect current row is not compact-canonical")
    return current, tuple(contradictions)


def _decode_compact_venue_execution_checkpoint(
    value: object,
) -> _venue.VenueExecutionCheckpoint:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.ExecutionCheckpoint/v1",
        9,
    )
    registry_count = _operations._require_exact_int(
        "venue execution registry count", fields[1]
    )
    integrity_bits = _operations._require_exact_int(
        "venue execution integrity bits", fields[5]
    )
    transition_count = _operations._require_exact_int(
        "venue execution reconciliation transition count", fields[7]
    )
    if min(registry_count, integrity_bits, transition_count) < 0:
        raise ValueError("venue execution checkpoint integers must be non-negative")
    if type(fields[6]) is not bool:
        raise TypeError("venue execution reconciliation flag must be exact bool")
    checkpoint = _venue.VenueExecutionCheckpoint(
        _operations._decode_m2_position_scope(fields[0]),
        registry_count,
        _operations._decode_m2_bytes("venue execution registry commitment", fields[2]),
        _operations._decode_m2_bytes("venue execution position commitment", fields[3]),
        _operations._decode_m2_bytes("venue execution root-head commitment", fields[4]),
        integrity_bits,
        fields[6],
        transition_count,
        _operations._decode_m2_bytes(
            "venue execution reconciliation transition head", fields[8]
        ),
    )
    if _encode_runtime_checkpoint_venue_execution_checkpoint(checkpoint) != value:
        raise ValueError("venue execution checkpoint is not compact-canonical")
    return checkpoint


def _decode_compact_venue_scope(value: object) -> _venue.VenueScope:
    fields = _operations._require_m2_aggregate(value, "m2.venue.Scope/v1", 4)
    scope = _venue.VenueScope(
        _operations._decode_m2_m1_as(
            "venue scope application", fields[0], _identity.ApplicationGenerationId
        ),
        _operations._decode_m2_m1_as(
            "venue scope broker", fields[1], _identity.BrokerId
        ),
        _operations._decode_m2_m1_as(
            "venue scope environment", fields[2], _identity.EnvironmentId
        ),
        _operations._decode_m2_m1_as(
            "venue scope account", fields[3], _identity.AccountId
        ),
    )
    if _encode_runtime_checkpoint_venue_scope(scope) != value:
        raise ValueError("venue scope is not compact-canonical")
    return scope


def _decode_compact_venue_execution_binding(
    value: object,
) -> _venue.VenueExecutionBinding:
    fields = _operations._require_m2_aggregate(value, "m2.venue.ExecutionBinding/v1", 4)
    integrity_bits = _operations._require_exact_int(
        "venue execution binding integrity bits", fields[3]
    )
    if integrity_bits < 0:
        raise ValueError("venue execution binding integrity bits must be non-negative")
    binding = _venue.VenueExecutionBinding(
        _operations._decode_m2_position_scope(fields[0]),
        _operations._decode_m2_bytes(
            "venue execution binding position commitment", fields[1]
        ),
        _operations._decode_m2_bytes(
            "venue execution binding root-head commitment", fields[2]
        ),
        integrity_bits,
    )
    if _encode_runtime_checkpoint_venue_execution_binding(binding) != value:
        raise ValueError("venue execution binding is not compact-canonical")
    return binding


def _decode_compact_venue_transition_cursor(
    value: object,
) -> _venue._ProtectionCursor:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.ProtectionTransitionCursor/v1",
        5,
    )
    ordinal = _operations._require_exact_int(
        "venue transition cursor ordinal", fields[0]
    )
    if ordinal < 0:
        raise ValueError("venue transition cursor ordinal must be non-negative")
    execution_commitment = _decode_optional_checkpoint_digest(
        "venue transition cursor execution commitment", fields[3]
    )
    execution_checkpoint = (
        None
        if fields[4] is None
        else _decode_compact_venue_execution_checkpoint(fields[4])
    )
    if (execution_commitment is None) != (execution_checkpoint is None):
        raise ValueError("venue transition cursor execution seal is partial")
    cursor = _venue._ProtectionCursor(
        ordinal,
        _operations._decode_m2_bytes("venue transition cursor head", fields[1]),
        (
            None
            if fields[2] is None
            else _operations._decode_m2_m1_as(
                "venue transition cursor mandate",
                fields[2],
                _identity.MandateId,
            )
        ),
        execution_commitment,
        execution_checkpoint,
    )
    if _encode_runtime_checkpoint_venue_transition_cursor(cursor) != value:
        raise ValueError("venue transition cursor is not compact-canonical")
    return cursor


def _decode_compact_venue_atom_tuple(
    value: object,
    *,
    tag: str,
    subject: str,
    expected: type[_Any],
) -> tuple[_Any, ...]:
    rows = _decode_checkpoint_collection_rows(value, tag)
    decoded = tuple(
        _operations._decode_m2_m1_as(subject, row, expected) for row in rows
    )
    if len(set(decoded)) != len(decoded):
        raise ValueError(f"{subject} retains a duplicate member")
    if (
        _encode_runtime_checkpoint_venue_atom_tuple(
            tag,
            _cast(tuple[_durable_codec._OwningValue, ...], decoded),
            subject,
        )
        != value
    ):
        raise ValueError(f"{subject} is not compact-canonical")
    return decoded


def _decode_compact_venue_symbol_authority_summary(
    value: object,
) -> _venue._SymbolAuthoritySummary:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.SymbolAuthoritySummary/v1",
        9,
    )
    counts = tuple(
        _operations._require_exact_int(name, candidate)
        for name, candidate in (
            ("venue summary effect count", fields[0]),
            ("venue summary blocking effect count", fields[1]),
            ("venue summary blocking buy count", fields[2]),
            ("venue summary stand-downable buy count", fields[3]),
            ("venue summary waiting buy parent count", fields[7]),
            ("venue summary unknown buy effect count", fields[8]),
        )
    )
    if min(counts) < 0:
        raise ValueError("venue summary counts must be non-negative")
    summary = _venue._SymbolAuthoritySummary(
        effect_count=counts[0],
        blocking_effect_count=counts[1],
        blocking_buy_effect_count=counts[2],
        stand_downable_buy_count=counts[3],
        stand_downable_buy_effect_ids=_cast(
            tuple[_identity.EffectId, ...],
            _decode_compact_venue_atom_tuple(
                fields[4],
                tag="m2.venue.StandDownEffects/v1",
                subject="venue summary stand-down effects",
                expected=_identity.EffectId,
            ),
        ),
        known_cancellable_buy_leg_keys=_cast(
            tuple[_identity.VenueLegKey, ...],
            _decode_compact_venue_atom_tuple(
                fields[5],
                tag="m2.venue.CancellableBuyLegs/v1",
                subject="venue summary cancellable buy legs",
                expected=_identity.VenueLegKey,
            ),
        ),
        known_cancel_pending_buy_leg_keys=_cast(
            tuple[_identity.VenueLegKey, ...],
            _decode_compact_venue_atom_tuple(
                fields[6],
                tag="m2.venue.CancelPendingBuyLegs/v1",
                subject="venue summary cancel-pending buy legs",
                expected=_identity.VenueLegKey,
            ),
        ),
        waiting_buy_parent_count=counts[4],
        unknown_buy_effect_count=counts[5],
    )
    if _encode_runtime_checkpoint_venue_symbol_authority_summary(summary) != value:
        raise ValueError("venue symbol authority summary is not compact-canonical")
    return summary


def _decode_compact_venue_transition_proof(
    value: object,
) -> _venue._ProtectionTransitionProof:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.ProtectionTransitionProof/v1",
        24,
    )
    flags = fields[15:19]
    if any(type(flag) is not bool for flag in flags):
        raise TypeError("venue transition proof flags must be exact bools")
    quantity_delta = _operations._require_exact_int(
        "venue transition proof quantity delta", fields[21]
    )
    proof = _venue._ProtectionTransitionProof(
        _operations._decode_m2_position_scope(fields[0]),
        _decode_compact_venue_transition_cursor(fields[1]),
        _decode_compact_venue_transition_cursor(fields[2]),
        _decode_compact_venue_scope(fields[3]),
        _decode_compact_venue_scope(fields[4]),
        _operations._decode_m2_bytes(
            "venue transition predecessor book commitment", fields[5]
        ),
        _operations._decode_m2_bytes("venue transition book commitment", fields[6]),
        _operations._decode_m2_bytes(
            "venue transition predecessor execution commitment", fields[7]
        ),
        _operations._decode_m2_bytes(
            "venue transition execution commitment", fields[8]
        ),
        _decode_compact_venue_execution_checkpoint(fields[9]),
        _decode_compact_venue_execution_checkpoint(fields[10]),
        _decode_compact_venue_symbol_authority_summary(fields[11]),
        _decode_compact_venue_symbol_authority_summary(fields[12]),
        (
            None
            if fields[13] is None
            else _decode_compact_venue_execution_binding(fields[13])
        ),
        (
            None
            if fields[14] is None
            else _decode_compact_venue_execution_binding(fields[14])
        ),
        _cast(bool, flags[0]),
        _cast(bool, flags[1]),
        _cast(bool, flags[2]),
        _cast(bool, flags[3]),
        _operations._decode_m2_bytes("venue transition command commitment", fields[19]),
        _decode_checkpoint_enum_value(
            "venue transition disposition",
            fields[20],
            "m1.venue.VenueRecoveryDisposition",
            _venue.VenueRecoveryDisposition,
        ),
        quantity_delta,
        _decode_checkpoint_enum_value(
            "venue transition source kind",
            fields[22],
            "m1.venue.ProtectionTransitionSourceKind",
            _venue._ProtectionTransitionSourceKind,
        ),
        _operations._decode_m2_bytes("venue transition source binding", fields[23]),
    )
    if (
        not proof.lineage_is_authentic
        or _encode_runtime_checkpoint_venue_transition_proof(proof) != value
    ):
        raise ValueError("venue transition proof is not authentic and canonical")
    return proof


def _decode_compact_venue_execution_reconciliation_row(
    value: object,
) -> (
    _venue._ResolvedRegistryProjectionOutcome | _venue._UnresolvedRegistryAdvanceOutcome
):
    if type(value) is not list or not value or type(value[0]) is not str:
        raise ValueError("venue execution reconciliation row is malformed")
    reason: object
    if value[0] == "m2.venue.ResolvedRegistryProjection/v1":
        fields = _operations._require_m2_aggregate(
            value,
            "m2.venue.ResolvedRegistryProjection/v1",
            8,
        )
        reason = fields[6]
        if type(reason) is not str:
            raise TypeError("venue resolved projection reason must be exact text")
        count = _operations._require_exact_int(
            "venue resolved projection registry count", fields[4]
        )
        if count < 0:
            raise ValueError("venue resolved projection count must be non-negative")
        result: (
            _venue._ResolvedRegistryProjectionOutcome
            | _venue._UnresolvedRegistryAdvanceOutcome
        ) = _venue._ResolvedRegistryProjectionOutcome(
            _operations._decode_m2_m1_as(
                "venue resolved projection input", fields[0], _identity.VenueInputId
            ),
            _operations._decode_m2_bytes(
                "venue resolved projection command", fields[1]
            ),
            _decode_compact_venue_execution_checkpoint(fields[2]),
            _decode_compact_venue_execution_binding(fields[3]),
            count,
            _operations._decode_m2_bytes(
                "venue resolved projection registry commitment", fields[5]
            ),
            reason,
            _decode_checkpoint_enum_value(
                "venue resolved projection kind",
                fields[7],
                "m1.venue.ResolvedProjectionKind",
                _venue._ResolvedProjectionKind,
            ),
        )
    elif value[0] == "m2.venue.UnresolvedRegistryAdvance/v1":
        fields = _operations._require_m2_aggregate(
            value,
            "m2.venue.UnresolvedRegistryAdvance/v1",
            10,
        )
        prior_count = _operations._require_exact_int(
            "venue unresolved prior account registry count", fields[3]
        )
        resulting_count = _operations._require_exact_int(
            "venue unresolved resulting registry count", fields[7]
        )
        reason = fields[9]
        if min(prior_count, resulting_count) < 0 or type(reason) is not str:
            raise ValueError("venue unresolved registry outcome is malformed")
        result = _venue._UnresolvedRegistryAdvanceOutcome(
            _operations._decode_m2_m1_as(
                "venue unresolved projection input", fields[0], _identity.VenueInputId
            ),
            _operations._decode_m2_bytes(
                "venue unresolved projection command", fields[1]
            ),
            _decode_compact_venue_execution_checkpoint(fields[2]),
            prior_count,
            _operations._decode_m2_bytes(
                "venue unresolved prior registry commitment", fields[4]
            ),
            _decode_compact_venue_execution_binding(fields[5]),
            _decode_compact_venue_execution_binding(fields[6]),
            resulting_count,
            _operations._decode_m2_bytes(
                "venue unresolved resulting registry commitment", fields[8]
            ),
            reason,
        )
    else:
        raise ValueError("venue execution reconciliation variant is not admitted")
    if _encode_runtime_checkpoint_venue_execution_reconciliation_row(result) != value:
        raise ValueError("venue execution reconciliation is not compact-canonical")
    return result


def _decode_compact_venue_bootstrap_active(
    value: object,
) -> _venue._BootstrapBoundTargetRecord:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.BootstrapTargetActive/v1",
        24,
    )
    application_generation_id = _operations._decode_m2_m1_as(
        "venue bootstrap application", fields[0], _identity.ApplicationGenerationId
    )
    position_scope = _operations._decode_m2_position_scope(fields[1])
    source_kind = _decode_checkpoint_enum_value(
        "venue bootstrap source kind",
        fields[2],
        "m1.venue.BootstrapSourceKind",
        _venue._BootstrapSourceKind,
    )
    current_count = _operations._require_exact_int(
        "venue bootstrap current registry count", fields[7]
    )
    current_reconciliation_count = _operations._require_exact_int(
        "venue bootstrap current reconciliation count", fields[9]
    )
    bootstrap_count = _operations._require_exact_int(
        "venue bootstrap origin registry count", fields[14]
    )
    bootstrap_reconciliation_count = _operations._require_exact_int(
        "venue bootstrap origin reconciliation count", fields[16]
    )
    if (
        min(
            current_count,
            current_reconciliation_count,
            bootstrap_count,
            bootstrap_reconciliation_count,
        )
        < 0
    ):
        raise ValueError("venue bootstrap counts must be non-negative")
    bootstrap_input = _venue._new_bootstrap_target_registry_input(
        application_generation_id=application_generation_id,
        source_kind=source_kind,
        position_scope=position_scope,
        source_execution_commitment=_operations._decode_m2_bytes(
            "venue bootstrap source execution", fields[3]
        ),
        target_genesis_execution_commitment=_operations._decode_m2_bytes(
            "venue bootstrap target genesis", fields[4]
        ),
        target_execution_commitment=_operations._decode_m2_bytes(
            "venue bootstrap origin target execution", fields[13]
        ),
        prior_account_registry_count=bootstrap_count,
        prior_account_registry_commitment=_operations._decode_m2_bytes(
            "venue bootstrap origin registry commitment", fields[15]
        ),
        reconciliation_transition_count=bootstrap_reconciliation_count,
        reconciliation_transition_head=_operations._decode_m2_bytes(
            "venue bootstrap origin reconciliation head", fields[17]
        ),
    )
    retained_bootstrap_input_id = _operations._decode_m2_m1_as(
        "venue bootstrap input", fields[11], _identity.VenueInputId
    )
    retained_bootstrap_input_commitment = _operations._decode_m2_bytes(
        "venue bootstrap input commitment", fields[12]
    )
    if (
        bootstrap_input.input_id != retained_bootstrap_input_id
        or bootstrap_input.commitment != retained_bootstrap_input_commitment
    ):
        raise ValueError("venue bootstrap private input is stale or spliced")
    bootstrap_proof = _decode_compact_venue_transition_proof(fields[19])
    current_proof = _decode_compact_venue_transition_proof(fields[23])
    bootstrap_proof_commitment = _operations._decode_m2_bytes(
        "venue bootstrap anchor proof commitment", fields[18]
    )
    current_proof_commitment = _operations._decode_m2_bytes(
        "venue bootstrap current proof commitment", fields[22]
    )
    if (
        bootstrap_proof.commitment != bootstrap_proof_commitment
        or current_proof.commitment != current_proof_commitment
    ):
        raise ValueError("venue bootstrap proof commitment is stale or spliced")
    if fields[19] == fields[23]:
        current_proof = bootstrap_proof
    binding = _decode_compact_venue_execution_binding(fields[6])
    target_execution_commitment = _operations._decode_m2_bytes(
        "venue bootstrap current target execution", fields[5]
    )
    account_registry_commitment = _operations._decode_m2_bytes(
        "venue bootstrap current registry commitment", fields[8]
    )
    reconciliation_transition_head = _operations._decode_m2_bytes(
        "venue bootstrap current reconciliation head", fields[10]
    )
    checkpoint_input_id = _operations._decode_m2_m1_as(
        "venue bootstrap checkpoint input", fields[20], _identity.VenueInputId
    )
    checkpoint_command_commitment = _operations._decode_m2_bytes(
        "venue bootstrap checkpoint command", fields[21]
    )
    current_checkpoint = current_proof.execution_checkpoint
    if (
        current_proof.position_scope != position_scope
        or current_proof.execution_commitment != target_execution_commitment
        or current_proof.binding != binding
        or current_proof.command_commitment != checkpoint_command_commitment
        or current_proof.disposition is not _venue.VenueRecoveryDisposition.APPLIED
        or current_proof.quantity_delta != 0
        or current_checkpoint.position_scope != position_scope
        or current_checkpoint.registry_count != current_count
        or current_checkpoint.registry_commitment != account_registry_commitment
        or current_checkpoint.position_commitment != binding.position_commitment
        or current_checkpoint.root_heads_commitment != binding.root_heads_commitment
        or current_checkpoint.integrity_bits != binding.integrity_bits
        or current_checkpoint.reconciliation_transition_count
        != current_reconciliation_count
        or current_checkpoint.reconciliation_transition_head
        != reconciliation_transition_head
        or bootstrap_proof.position_scope != position_scope
        or bootstrap_proof.execution_commitment
        != bootstrap_input.target_execution_commitment
        or bootstrap_proof.command_commitment
        != _venue._protection_command_commitment(bootstrap_input)
    ):
        raise ValueError("venue bootstrap proof contradicts its current row")
    record = _venue._new_bootstrap_bound_target_record(
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        source_kind=source_kind,
        source_execution_commitment=bootstrap_input.source_execution_commitment,
        target_genesis_execution_commitment=(
            bootstrap_input.target_genesis_execution_commitment
        ),
        target_execution_commitment=target_execution_commitment,
        binding=binding,
        account_registry_count=current_count,
        account_registry_commitment=account_registry_commitment,
        reconciliation_transition_count=current_reconciliation_count,
        reconciliation_transition_head=reconciliation_transition_head,
        bootstrap_input=bootstrap_input,
        neutral_checkpoint_proof=current_proof,
        bootstrap_neutral_checkpoint_proof=bootstrap_proof,
        checkpoint_input_id=checkpoint_input_id,
        checkpoint_command_commitment=checkpoint_command_commitment,
    )
    if _encode_runtime_checkpoint_venue_bootstrap_active(record) != value:
        raise ValueError("venue bootstrap active row is not compact-canonical")
    return record


def _decode_compact_venue_bootstrap_target(
    value: object,
    *,
    effects_by_id: dict[_identity.EffectId, _venue.BrokerEffect],
) -> object:
    if type(value) is not list or not value or type(value[0]) is not str:
        raise ValueError("venue bootstrap target row is malformed")
    if value[0] == "m2.venue.BootstrapTargetActive/v1":
        return _decode_compact_venue_bootstrap_active(value)
    if value[0] != "m2.venue.BootstrapTargetConsumed/v1":
        raise ValueError("venue bootstrap target variant is not admitted")
    fields = _operations._require_m2_aggregate(
        value,
        "m2.venue.BootstrapTargetConsumed/v1",
        5,
    )
    active = _decode_compact_venue_bootstrap_active(fields[0])
    effect_id = _operations._decode_m2_m1_as(
        "venue consumed bootstrap effect", fields[1], _identity.EffectId
    )
    request_occurrence_id = _operations._decode_m2_m1_as(
        "venue consumed bootstrap request occurrence",
        fields[2],
        _identity.RequestOccurrenceId,
    )
    request_input_id = _operations._decode_m2_m1_as(
        "venue consumed bootstrap request input", fields[3], _identity.VenueInputId
    )
    effect_scope_commitment = _operations._decode_m2_bytes(
        "venue consumed bootstrap effect scope", fields[4]
    )
    effect = effects_by_id.get(effect_id)
    if (
        type(effect) is not _venue.BrokerEffect
        or effect.scope.request_occurrence_id != request_occurrence_id
        or _venue._canonical_value_commitment(effect.scope) != effect_scope_commitment
    ):
        raise ValueError("venue consumed bootstrap effect is absent or spliced")
    consumed = _venue._new_consumed_bootstrap_bound_target_record(
        active_record=active,
        effect=effect,
        request_input_id=request_input_id,
    )
    encoded, _ = _encode_runtime_checkpoint_venue_bootstrap_target(consumed)
    if encoded != value:
        raise ValueError("venue consumed bootstrap target is not compact-canonical")
    return consumed


def _venue_checkpoint_matches_execution_state(
    checkpoint: _venue.VenueExecutionCheckpoint,
    state: _position._M2ExecutionState,
) -> bool:
    return bool(
        checkpoint.position_scope == state.scope
        and checkpoint.registry_commitment == state.seen_facts_commitment
        and checkpoint.root_heads_commitment == state.root_heads_commitment
        and checkpoint.integrity_bits == state.integrity.value
        and checkpoint.account_reconciliation_required
        == state.account_reconciliation_required
        and checkpoint.reconciliation_transition_count
        == state.reconciliation_transition_count
        and checkpoint.reconciliation_transition_head
        == state.reconciliation_transition_head
    )


def _decode_compact_venue_checkpoint(
    value: object,
    *,
    selection: _records._RuntimeCheckpointSelectionSet,
    application_generation_id: _identity.ApplicationGenerationId,
    compact_execution_by_scope: dict[_fills.PositionScope, _position.ExecutionSnapshot],
    source_execution_state_by_scope: dict[
        _fills.PositionScope, _position._M2ExecutionState
    ],
) -> _venue.VenueRecoveryBook:
    """Restore proof-selected venue current state and normalize owner commitments."""

    fields = _operations._require_m2_aggregate(value, _M2_VENUE_STATE_TAG, 22)
    scope_fields = _operations._require_m2_aggregate(
        fields[0],
        "m2.venue.Scope/v1",
        4,
    )
    scope = _venue.VenueScope(
        _operations._decode_m2_m1_as(
            "venue application generation",
            scope_fields[0],
            _identity.ApplicationGenerationId,
        ),
        _operations._decode_m2_m1_as(
            "venue broker", scope_fields[1], _identity.BrokerId
        ),
        _operations._decode_m2_m1_as(
            "venue environment", scope_fields[2], _identity.EnvironmentId
        ),
        _operations._decode_m2_m1_as(
            "venue account", scope_fields[3], _identity.AccountId
        ),
    )
    if scope.generation != application_generation_id:
        raise ValueError("venue checkpoint leaves the selected application")

    account_epoch = _operations._require_exact_int(
        "venue account authority epoch", fields[1]
    )
    unresolved_account_count = _operations._require_exact_int(
        "venue unresolved account reconciliation count", fields[2]
    )
    if min(account_epoch, unresolved_account_count) < 0:
        raise ValueError("venue account counters must be non-negative")
    old_registry_count = (
        None
        if fields[3] is None
        else _operations._require_exact_int("venue registry count", fields[3])
    )
    if old_registry_count is not None and old_registry_count < 0:
        raise ValueError("venue registry count must be non-negative")
    old_registry_commitment = _decode_optional_checkpoint_digest(
        "venue registry commitment", fields[4]
    )
    if (old_registry_count is None) != (old_registry_commitment is None):
        raise ValueError("venue registry coordinates must be wholly present")
    transition_head = _decode_optional_checkpoint_digest(
        "venue registry transition head", fields[5]
    )

    authority_epoch_rows = _decode_checkpoint_collection_rows(
        fields[6], "m2.venue.AuthorityEpochs/v1"
    )
    authority_epochs: list[tuple[_fills.PositionScope, int]] = []
    for row in authority_epoch_rows:
        epoch_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.AuthorityEpoch/v1",
            2,
        )
        position_scope = _operations._decode_m2_position_scope(epoch_fields[0])
        epoch = _operations._require_exact_int("venue authority epoch", epoch_fields[1])
        if epoch < 0:
            raise ValueError("venue authority epoch must be non-negative")
        expected_epoch_row = [
            "m2.venue.AuthorityEpoch/v1",
            _operations._encode_m2_position_scope(position_scope),
            epoch,
        ]
        if expected_epoch_row != row:
            raise ValueError("venue authority epoch row is not canonical")
        authority_epochs.append((position_scope, epoch))

    effect_rows = _decode_checkpoint_collection_rows(fields[7], "m2.venue.Effects/v1")
    effects = tuple(
        _decode_compact_venue_effect_row(row, checkpoint_ordinal=ordinal)
        for ordinal, row in enumerate(effect_rows)
    )
    effects_by_id = {current.effect.effect_id: current for current, _ in effects}
    if len(effects_by_id) != len(effects):
        raise ValueError("venue effect current rows retain a duplicate identity")
    claim_rows = _decode_checkpoint_collection_rows(fields[8], "m2.venue.Claims/v1")
    claims: list[_venue.DispatchClaim] = []
    for row in claim_rows:
        claim_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.DispatchClaim/v1",
            2,
        )
        effect_id = _operations._decode_m2_m1_as(
            "venue dispatch claim effect", claim_fields[0], _identity.EffectId
        )
        current = effects_by_id.get(effect_id)
        if current is None:
            raise ValueError("venue dispatch claim names an absent current effect")
        claim = _venue.DispatchClaim(
            current.effect.scope,
            _operations._decode_m2_m1_as(
                "venue dispatch claim occurrence",
                claim_fields[1],
                _identity.ClaimOccurrenceId,
            ),
        )
        if [
            "m2.venue.DispatchClaim/v1",
            _operations._encode_m2_m1_atom(effect_id),
            _operations._encode_m2_m1_atom(claim.claim_occurrence_id),
        ] != row:
            raise ValueError("venue dispatch claim row is not canonical")
        claims.append(claim)

    owner_rows = _decode_checkpoint_collection_rows(
        fields[9], "m2.venue.OwnerAttempts/v1"
    )
    owners: list[tuple[_venue.VenueIdentityOwner, _venue.VenueAttempt | None]] = []
    for ordinal, row in enumerate(owner_rows):
        owner_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.OwnerAttempt/v1",
            5,
        )
        if (
            _operations._require_exact_int(
                "venue owner checkpoint ordinal", owner_fields[0]
            )
            != ordinal
        ):
            raise ValueError("venue owner checkpoint ordinals are not dense")
        leg_key = _operations._decode_m2_m1_as(
            "venue owner leg", owner_fields[1], _identity.VenueLegKey
        )
        effect_id = _operations._decode_m2_m1_as(
            "venue owner effect", owner_fields[2], _identity.EffectId
        )
        current = effects_by_id.get(effect_id)
        if current is None:
            raise ValueError("venue owner names an absent current effect")
        observation_id = _operations._decode_m2_m1_as(
            "venue owner observation",
            owner_fields[3],
            _identity.VenueObservationId,
        )
        owner = _venue.VenueIdentityOwner(
            leg_key,
            current.effect.scope,
            observation_id,
        )
        attempt: _venue.VenueAttempt | None = None
        if owner_fields[4] is not None:
            attempt_fields = _operations._require_m2_aggregate(
                owner_fields[4],
                "m2.venue.Attempt/v1",
                5,
            )
            attempt = _venue.VenueAttempt(
                _operations._decode_m2_m1_as(
                    "venue attempt leg",
                    attempt_fields[0],
                    _identity.VenueLegKey,
                ),
                _decode_checkpoint_enum_value(
                    "venue attempt state",
                    attempt_fields[1],
                    "m1.venue.VenueAttemptState",
                    _venue.VenueAttemptState,
                ),
                (
                    None
                    if attempt_fields[2] is None
                    else _decode_checkpoint_enum_value(
                        "venue pending operation",
                        attempt_fields[2],
                        "m1.venue.PendingVenueOperation",
                        _venue.PendingVenueOperation,
                    )
                ),
                _operations._decode_m2_m1_as(
                    "venue attempt cumulative quantity",
                    attempt_fields[3],
                    _values.Quantity,
                ),
                _operations._decode_m2_m1_as(
                    "venue attempt observation",
                    attempt_fields[4],
                    _identity.VenueObservationId,
                ),
            )
            if attempt.leg_key != leg_key:
                raise ValueError("venue attempt does not own its current leg")
        expected_attempt = (
            None
            if attempt is None
            else [
                "m2.venue.Attempt/v1",
                _operations._encode_m2_m1_atom(attempt.leg_key),
                _checkpoint_enum("m1.venue.VenueAttemptState", attempt.status),
                (
                    None
                    if attempt.pending_operation is None
                    else _checkpoint_enum(
                        "m1.venue.PendingVenueOperation",
                        attempt.pending_operation,
                    )
                ),
                _operations._encode_m2_m1_atom(attempt.cumulative_quantity),
                _operations._encode_m2_m1_atom(attempt.last_observation_id),
            ]
        )
        if [
            "m2.venue.OwnerAttempt/v1",
            ordinal,
            _operations._encode_m2_m1_atom(leg_key),
            _operations._encode_m2_m1_atom(effect_id),
            _operations._encode_m2_m1_atom(observation_id),
            expected_attempt,
        ] != row:
            raise ValueError("venue owner current row is not canonical")
        owners.append((owner, attempt))

    correlation_rows = _decode_checkpoint_collection_rows(
        fields[10], "m2.venue.AcquisitionCorrelations/v1"
    )
    acquisition_correlations: list[_venue._AcquisitionCorrelationEntry] = []
    for row in correlation_rows:
        correlation_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.AcquisitionCorrelation/v1",
            6,
        )
        entry = _venue._AcquisitionCorrelationEntry(
            _operations._decode_m2_m1_as(
                "venue correlation application generation",
                correlation_fields[0],
                _identity.ApplicationGenerationId,
            ),
            _operations._decode_m2_position_scope(correlation_fields[1]),
            _operations._decode_m2_m1_as(
                "venue correlation request occurrence",
                correlation_fields[2],
                _identity.RequestOccurrenceId,
            ),
            _operations._decode_m2_m1_as(
                "venue correlation effect",
                correlation_fields[3],
                _identity.EffectId,
            ),
            _operations._decode_m2_m1_as(
                "venue correlation leg",
                correlation_fields[4],
                _identity.VenueLegKey,
            ),
            _operations._decode_m2_m1_as(
                "venue correlation root",
                correlation_fields[5],
                _identity.RootFillKey,
            ),
        )
        if [
            "m2.venue.AcquisitionCorrelation/v1",
            _operations._encode_m2_m1_atom(entry.application_generation_id),
            _operations._encode_m2_position_scope(entry.position_scope),
            _operations._encode_m2_m1_atom(entry.request_occurrence_id),
            _operations._encode_m2_m1_atom(entry.effect_id),
            _operations._encode_m2_m1_atom(entry.leg_key),
            _operations._encode_m2_m1_atom(entry.root_key),
        ] != row:
            raise ValueError("venue acquisition correlation row is not canonical")
        acquisition_correlations.append(entry)

    closure_rows = _decode_checkpoint_collection_rows(
        fields[11], "m2.venue.ClosureHeads/v1"
    )
    closure_heads: list[_venue.VenueTerminalClosure] = []
    for row in closure_rows:
        closure_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.TerminalClosure/v1",
            16,
        )
        closure_ordinal = _operations._require_exact_int(
            "venue closure ordinal", closure_fields[2]
        )
        if closure_ordinal < 0:
            raise ValueError("venue closure ordinal must be non-negative")
        reason = closure_fields[14]
        if reason is not None and type(reason) is not str:
            raise TypeError("venue closure reason must be exact text or None")
        closure = _venue.VenueTerminalClosure(
            _operations._decode_m2_m1_as(
                "venue closure leg", closure_fields[0], _identity.VenueLegKey
            ),
            _operations._decode_m2_m1_as(
                "venue closure id", closure_fields[1], _identity.ClosureId
            ),
            closure_ordinal,
            (
                None
                if closure_fields[3] is None
                else _operations._decode_m2_m1_as(
                    "venue closure predecessor",
                    closure_fields[3],
                    _identity.ClosureId,
                )
            ),
            _decode_checkpoint_enum_value(
                "venue closure state",
                closure_fields[4],
                "m1.venue.VenueAttemptState",
                _venue.VenueAttemptState,
            ),
            _operations._decode_m2_m1_as(
                "venue closure cumulative quantity",
                closure_fields[5],
                _values.Quantity,
            ),
            _operations._decode_m2_m1_as(
                "venue closure observed cumulative quantity",
                closure_fields[6],
                _values.Quantity,
            ),
            _operations._decode_m2_m1_as(
                "venue closure evidence",
                closure_fields[7],
                _identity.EvidenceReference,
            ),
            _decode_checkpoint_enum_value(
                "venue closure kind",
                closure_fields[8],
                "m1.venue.VenueClosureKind",
                _venue.VenueClosureKind,
            ),
            _operations._decode_m2_m1_as(
                "venue closure source input",
                closure_fields[9],
                _identity.VenueInputId,
            ),
            (
                None
                if closure_fields[10] is None
                else _operations._decode_m2_m1_as(
                    "venue closure observation",
                    closure_fields[10],
                    _identity.VenueObservationId,
                )
            ),
            (
                None
                if closure_fields[11] is None
                else _operations._decode_m2_m1_as(
                    "venue closure source event",
                    closure_fields[11],
                    _identity.SourceEventId,
                )
            ),
            (
                None
                if closure_fields[12] is None
                else _decode_checkpoint_enum_value(
                    "venue closure broker terminal state",
                    closure_fields[12],
                    "m1.venue.VenueAttemptState",
                    _venue.VenueAttemptState,
                )
            ),
            (
                None
                if closure_fields[13] is None
                else _operations._decode_m2_m1_as(
                    "venue closure actor", closure_fields[13], _identity.ActorId
                )
            ),
            reason,
            _decode_optional_checkpoint_digest(
                "venue closure evidence digest", closure_fields[15]
            ),
        )
        closure_heads.append(closure)

    high_water_rows = _decode_checkpoint_collection_rows(
        fields[12], "m2.venue.EconomicHighWaters/v1"
    )
    economic_high_waters: list[tuple[_identity.VenueLegKey, int]] = []
    for row in high_water_rows:
        high_water_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.EconomicHighWater/v1",
            2,
        )
        high_water = _operations._require_exact_int(
            "venue economic high water", high_water_fields[1]
        )
        if high_water < 0:
            raise ValueError("venue economic high water must be non-negative")
        economic_high_waters.append(
            (
                _operations._decode_m2_m1_as(
                    "venue economic high-water leg",
                    high_water_fields[0],
                    _identity.VenueLegKey,
                ),
                high_water,
            )
        )

    human_coverage_rows = _decode_checkpoint_collection_rows(
        fields[13], "m2.venue.HumanCoverages/v1"
    )
    human_coverages: list[_recovery.HumanCoverage] = []
    for row in human_coverage_rows:
        coverage_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.HumanCoverage/v1",
            8,
        )
        if type(coverage_fields[4]) is not bool:
            raise TypeError("venue human corroboration flag must be exact bool")
        human_coverage = _recovery.HumanCoverage(
            _operations._decode_m2_m1_as(
                "venue human coverage effect",
                coverage_fields[0],
                _identity.EffectId,
            ),
            _operations._decode_m2_m1_as(
                "venue human coverage leg",
                coverage_fields[1],
                _identity.VenueLegKey,
            ),
            _operations._decode_m2_human_attested_fill_fact(coverage_fields[2]),
            _operations._decode_m2_m1_as(
                "venue human coverage source input",
                coverage_fields[3],
                _identity.VenueInputId,
            ),
            coverage_fields[4],
            (
                None
                if coverage_fields[5] is None
                else _operations._decode_m2_broker_fill_fact(coverage_fields[5])
            ),
            _decode_optional_checkpoint_digest(
                "venue human broker evidence digest", coverage_fields[6]
            ),
            (
                None
                if coverage_fields[7] is None
                else _operations._decode_m2_m1_as(
                    "venue human broker source input",
                    coverage_fields[7],
                    _identity.VenueInputId,
                )
            ),
        )
        human_coverages.append(human_coverage)

    broker_coverage_rows = _decode_checkpoint_collection_rows(
        fields[14], "m2.venue.BrokerCoverages/v1"
    )
    broker_coverages: list[_recovery._BrokerCoverage] = []
    for row in broker_coverage_rows:
        coverage_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.BrokerCoverage/v1",
            11,
        )
        if type(coverage_fields[10]) is not bool:
            raise TypeError("venue broker mapping flag must be exact bool")
        broker_coverage = _recovery._BrokerCoverage(
            _operations._decode_m2_m1_as(
                "venue broker coverage effect",
                coverage_fields[0],
                _identity.EffectId,
            ),
            _operations._decode_m2_m1_as(
                "venue broker coverage leg",
                coverage_fields[1],
                _identity.VenueLegKey,
            ),
            _operations._decode_m2_m1_as(
                "venue broker prior cumulative quantity",
                coverage_fields[2],
                _values.Quantity,
            ),
            _operations._decode_m2_m1_as(
                "venue broker resulting cumulative quantity",
                coverage_fields[3],
                _values.Quantity,
            ),
            _operations._decode_m2_broker_fill_fact(coverage_fields[4]),
            _operations._decode_m2_bytes(
                "venue broker evidence digest", coverage_fields[5]
            ),
            _operations._decode_m2_m1_as(
                "venue broker root source input",
                coverage_fields[6],
                _identity.VenueInputId,
            ),
            _operations._decode_m2_broker_execution_fact(coverage_fields[7]),
            _operations._decode_m2_bytes(
                "venue broker head evidence digest", coverage_fields[8]
            ),
            _operations._decode_m2_m1_as(
                "venue broker head source input",
                coverage_fields[9],
                _identity.VenueInputId,
            ),
            coverage_fields[10],
        )
        broker_coverages.append(broker_coverage)

    provenance_rows = _decode_checkpoint_collection_rows(
        fields[15], "m2.venue.CoverageProvenances/v1"
    )
    coverage_provenances: list[
        tuple[_fills.PositionScope, _venue._CoverageProvenance]
    ] = []
    for row in provenance_rows:
        provenance_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.CoverageProvenance/v1",
            3,
        )
        position_scope = _operations._decode_m2_position_scope(provenance_fields[0])
        covered_rows = _decode_checkpoint_collection_rows(
            provenance_fields[1],
            "m2.venue.CoveredRoots/v1",
        )
        covered_roots: _fills._PersistentKeyMap[bytes] = (
            _fills._PersistentKeyMap.empty()
        )
        expected_covered_rows: list[object] = []
        for covered_row in covered_rows:
            covered_fields = _operations._require_m2_aggregate(
                covered_row,
                "m2.venue.CoveredRoot/v1",
                2,
            )
            root_key = _operations._decode_m2_m1_as(
                "venue covered root", covered_fields[0], _identity.RootFillKey
            )
            fact_commitment = _operations._decode_m2_bytes(
                "venue covered fact commitment", covered_fields[1]
            )
            covered_roots = covered_roots.insert_new(
                _venue._coverage_root_index_key(root_key),
                fact_commitment,
                fact_commitment,
            )
            expected_covered_rows.append(
                [
                    "m2.venue.CoveredRoot/v1",
                    _operations._encode_m2_m1_atom(root_key),
                    _operations._encode_m2_bytes(fact_commitment),
                ]
            )
        old_root_heads_commitment = _decode_optional_checkpoint_digest(
            "venue coverage root-head commitment", provenance_fields[2]
        )
        source_state = source_execution_state_by_scope.get(position_scope)
        compact_execution = compact_execution_by_scope.get(position_scope)
        if old_root_heads_commitment is not None and (
            source_state is None
            or compact_execution is None
            or old_root_heads_commitment != source_state.root_heads_commitment
        ):
            raise ValueError("venue coverage provenance is stale or spliced")
        if old_root_heads_commitment is not None:
            assert compact_execution is not None
        normalized_root_heads_commitment = (
            None
            if compact_execution is None or old_root_heads_commitment is None
            else compact_execution.root_heads.commitment
        )
        if [
            "m2.venue.CoverageProvenance/v1",
            _operations._encode_m2_position_scope(position_scope),
            _checkpoint_collection("m2.venue.CoveredRoots/v1", expected_covered_rows),
            (
                None
                if old_root_heads_commitment is None
                else _operations._encode_m2_bytes(old_root_heads_commitment)
            ),
        ] != row:
            raise ValueError("venue coverage provenance row is not canonical")
        coverage_provenances.append(
            (
                position_scope,
                _venue._CoverageProvenance(
                    covered_roots,
                    normalized_root_heads_commitment,
                ),
            )
        )

    reconciliation_rows = _decode_checkpoint_collection_rows(
        fields[16], "m2.venue.Reconciliations/v1"
    )
    reconciliations: list[
        _recovery.ReconciliationRecord | _recovery.RevisionReconciliationRecord
    ] = []
    for row in reconciliation_rows:
        if type(row) is not list or not row or type(row[0]) is not str:
            raise ValueError("venue reconciliation row is malformed")
        if row[0] == "m2.venue.FillReconciliation/v1":
            reconciliation_fields = _operations._require_m2_aggregate(
                row,
                "m2.venue.FillReconciliation/v1",
                8,
            )
            reason = reconciliation_fields[7]
            if type(reason) is not str:
                raise TypeError("venue fill reconciliation reason must be exact text")
            reconciliation: (
                _recovery.ReconciliationRecord | _recovery.RevisionReconciliationRecord
            ) = _recovery.ReconciliationRecord(
                _operations._decode_m2_m1_as(
                    "venue fill reconciliation input",
                    reconciliation_fields[0],
                    _identity.VenueInputId,
                ),
                _operations._decode_m2_m1_as(
                    "venue fill reconciliation effect",
                    reconciliation_fields[1],
                    _identity.EffectId,
                ),
                _operations._decode_m2_m1_as(
                    "venue fill reconciliation leg",
                    reconciliation_fields[2],
                    _identity.VenueLegKey,
                ),
                _operations._decode_m2_m1_as(
                    "venue fill reconciliation prior cumulative quantity",
                    reconciliation_fields[3],
                    _values.Quantity,
                ),
                _operations._decode_m2_m1_as(
                    "venue fill reconciliation resulting cumulative quantity",
                    reconciliation_fields[4],
                    _values.Quantity,
                ),
                _operations._decode_m2_broker_fill_fact(reconciliation_fields[5]),
                _operations._decode_m2_bytes(
                    "venue fill reconciliation evidence digest",
                    reconciliation_fields[6],
                ),
                reason,
            )
        elif row[0] == "m2.venue.RevisionReconciliation/v1":
            reconciliation_fields = _operations._require_m2_aggregate(
                row,
                "m2.venue.RevisionReconciliation/v1",
                10,
            )
            encoded_fact = reconciliation_fields[6]
            if type(encoded_fact) is not list or not encoded_fact:
                raise ValueError("venue revision reconciliation fact is malformed")
            if encoded_fact[0] == "m1.fills.BrokerTradeCorrectFact/v1":
                revision_fact: (
                    _fills.BrokerTradeCorrectFact | _fills.BrokerTradeBustFact
                ) = _operations._decode_m2_broker_trade_correct_fact(encoded_fact)
            elif encoded_fact[0] == "m1.fills.BrokerTradeBustFact/v1":
                revision_fact = _operations._decode_m2_broker_trade_bust_fact(
                    encoded_fact
                )
            else:
                raise ValueError("venue revision reconciliation fact is not admitted")
            canonical_applied = reconciliation_fields[8]
            reason = reconciliation_fields[9]
            if type(canonical_applied) is not bool or type(reason) is not str:
                raise TypeError("venue revision reconciliation flags are not exact")
            reconciliation = _recovery.RevisionReconciliationRecord(
                _operations._decode_m2_m1_as(
                    "venue revision reconciliation input",
                    reconciliation_fields[0],
                    _identity.VenueInputId,
                ),
                _operations._decode_m2_m1_as(
                    "venue revision reconciliation effect",
                    reconciliation_fields[1],
                    _identity.EffectId,
                ),
                _operations._decode_m2_m1_as(
                    "venue revision reconciliation leg",
                    reconciliation_fields[2],
                    _identity.VenueLegKey,
                ),
                _operations._decode_m2_m1_as(
                    "venue revision prior root quantity",
                    reconciliation_fields[3],
                    _values.Quantity,
                ),
                _operations._decode_m2_m1_as(
                    "venue revision prior venue cumulative quantity",
                    reconciliation_fields[4],
                    _values.Quantity,
                ),
                _operations._decode_m2_m1_as(
                    "venue revision resulting venue cumulative quantity",
                    reconciliation_fields[5],
                    _values.Quantity,
                ),
                revision_fact,
                _operations._decode_m2_bytes(
                    "venue revision reconciliation evidence digest",
                    reconciliation_fields[7],
                ),
                canonical_applied,
                reason,
            )
        else:
            raise ValueError("venue reconciliation variant is not admitted")
        if _encode_runtime_checkpoint_venue_reconciliation_row(reconciliation) != row:
            raise ValueError("venue reconciliation row is not compact-canonical")
        reconciliations.append(reconciliation)

    execution_reconciliation_rows = _decode_checkpoint_collection_rows(
        fields[17], "m2.venue.ExecutionReconciliations/v1"
    )
    execution_reconciliations: list[
        _venue._ResolvedRegistryProjectionOutcome
        | _venue._UnresolvedRegistryAdvanceOutcome
    ] = []
    reconciliation_by_input: dict[
        _identity.VenueInputId,
        _venue._ResolvedRegistryProjectionOutcome
        | _venue._UnresolvedRegistryAdvanceOutcome,
    ] = {}
    for row in execution_reconciliation_rows:
        execution_reconciliation = _decode_compact_venue_execution_reconciliation_row(
            row
        )
        if execution_reconciliation.input_id in reconciliation_by_input:
            raise ValueError("venue execution reconciliation input is duplicated")
        reconciliation_by_input[execution_reconciliation.input_id] = (
            execution_reconciliation
        )
        execution_reconciliations.append(execution_reconciliation)

    broker_effects_by_id = {
        current.effect.effect_id: current.effect for current, _ in effects
    }
    if len(broker_effects_by_id) != len(effects):
        raise ValueError("venue current effects contain a duplicate identity")
    bootstrap_rows = _decode_checkpoint_collection_rows(
        fields[19], "m2.venue.BootstrapTargets/v1"
    )
    bootstrap_targets: list[object] = []
    bootstrap_scopes: set[_fills.PositionScope] = set()
    active_bootstrap_scopes: set[_fills.PositionScope] = set()
    references: dict[_identity.VenueInputId, tuple[_fills.PositionScope, bool]] = {}

    def retain_reference(
        input_id: _identity.VenueInputId,
        position_scope: _fills.PositionScope,
        *,
        required: bool,
    ) -> None:
        existing = references.get(input_id)
        if existing is None:
            references[input_id] = (position_scope, required)
        elif existing[0] != position_scope:
            raise ValueError("venue bootstrap input is referenced by two scopes")
        elif required and not existing[1]:
            references[input_id] = (position_scope, True)

    for row in bootstrap_rows:
        target = _decode_compact_venue_bootstrap_target(
            row,
            effects_by_id=broker_effects_by_id,
        )
        active = (
            target
            if type(target) is _venue._BootstrapBoundTargetRecord
            else _cast(_venue._ConsumedBootstrapBoundTargetRecord, target).active_record
        )
        if (
            type(active) is not _venue._BootstrapBoundTargetRecord
            or active.position_scope in bootstrap_scopes
            or active.application_generation_id != application_generation_id
            or active.position_scope not in source_execution_state_by_scope
        ):
            raise ValueError("venue bootstrap target is duplicated or unselected")
        bootstrap_scopes.add(active.position_scope)
        if type(target) is _venue._BootstrapBoundTargetRecord:
            active_bootstrap_scopes.add(active.position_scope)
            source_state = source_execution_state_by_scope[active.position_scope]
            if not _venue_checkpoint_matches_execution_state(
                active._neutral_checkpoint_proof.execution_checkpoint,
                source_state,
            ):
                raise ValueError("venue active bootstrap target is stale or spliced")
        retain_reference(
            active.bootstrap_input_id,
            active.position_scope,
            required=False,
        )
        retain_reference(
            active.checkpoint_input_id,
            active.position_scope,
            required=(
                active.checkpoint_input_id != active.bootstrap_input_id
                and active._neutral_checkpoint_proof.source_kind
                is not _venue._ProtectionTransitionSourceKind.COMPACT_RESTORE
            ),
        )
        bootstrap_targets.append(target)

    for input_id, execution_reconciliation in reconciliation_by_input.items():
        reference = references.get(input_id)
        if reference is None or execution_reconciliation.position_scope != reference[0]:
            raise ValueError(
                "venue execution reconciliation is unreferenced or cross-scope"
            )
    for input_id, (_, required) in references.items():
        if required and input_id not in reconciliation_by_input:
            raise ValueError("required venue execution reconciliation is absent")

    execution_rows = _decode_checkpoint_collection_rows(
        fields[18], "m2.venue.ExecutionScopes/v1"
    )
    execution_snapshots: list[_position.ExecutionSnapshot] = []
    reached_execution_scopes: set[_fills.PositionScope] = set()
    for row in execution_rows:
        execution_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.ExecutionScopeCurrent/v1",
            2,
        )
        state = _decode_m2_execution_checkpoint_state(execution_fields[0])
        old_checkpoint = _decode_compact_venue_execution_checkpoint(execution_fields[1])
        compact_execution = compact_execution_by_scope.get(state.scope)
        if (
            state.scope in reached_execution_scopes
            or source_execution_state_by_scope.get(state.scope) != state
            or compact_execution is None
            or compact_execution.position.scope != state.scope
            or not _venue_checkpoint_matches_execution_state(old_checkpoint, state)
            or [
                "m2.venue.ExecutionScopeCurrent/v1",
                _encode_m2_execution_state_component(state),
                _encode_runtime_checkpoint_venue_execution_checkpoint(old_checkpoint),
            ]
            != row
        ):
            raise ValueError("venue execution scope is missing, stale, or spliced")
        reached_execution_scopes.add(state.scope)
        execution_snapshots.append(compact_execution)
    cursor_rows = _decode_checkpoint_collection_rows(
        fields[20], "m2.venue.ProtectionCursors/v1"
    )
    cursors: list[tuple[_fills.PositionScope, _venue._ProtectionCursor]] = []
    source_cursors: dict[_fills.PositionScope, _venue._ProtectionCursor] = {}
    for row in cursor_rows:
        cursor_fields = _operations._require_m2_aggregate(
            row,
            "m2.venue.ProtectionCursor/v1",
            6,
        )
        position_scope = _operations._decode_m2_position_scope(cursor_fields[0])
        ordinal = _operations._require_exact_int(
            "venue protection cursor ordinal", cursor_fields[1]
        )
        if ordinal < 0:
            raise ValueError("venue protection cursor ordinal must be non-negative")
        head = _operations._decode_m2_bytes(
            "venue protection cursor head", cursor_fields[2]
        )
        mandate_id = (
            None
            if cursor_fields[3] is None
            else _operations._decode_m2_m1_as(
                "venue protection cursor mandate",
                cursor_fields[3],
                _identity.MandateId,
            )
        )
        old_execution_commitment = _decode_optional_checkpoint_digest(
            "venue protection cursor execution commitment", cursor_fields[4]
        )
        old_execution_checkpoint = (
            None
            if cursor_fields[5] is None
            else _decode_compact_venue_execution_checkpoint(cursor_fields[5])
        )
        if (old_execution_commitment is None) != (old_execution_checkpoint is None):
            raise ValueError("venue protection cursor execution seal is partial")
        cursor_source_state = source_execution_state_by_scope.get(position_scope)
        compact_execution = compact_execution_by_scope.get(position_scope)
        if old_execution_checkpoint is not None and (
            cursor_source_state is None
            or compact_execution is None
            or not _venue_checkpoint_matches_execution_state(
                old_execution_checkpoint, cursor_source_state
            )
        ):
            raise ValueError("venue protection cursor execution seal is spliced")
        old_cursor = _venue._ProtectionCursor(
            ordinal,
            head,
            mandate_id,
            old_execution_commitment,
            old_execution_checkpoint,
        )
        expected_old_cursor = [
            "m2.venue.ProtectionCursor/v1",
            _operations._encode_m2_position_scope(position_scope),
            ordinal,
            _operations._encode_m2_bytes(head),
            (
                None
                if mandate_id is None
                else _operations._encode_m2_m1_atom(mandate_id)
            ),
            (
                None
                if old_execution_commitment is None
                else _operations._encode_m2_bytes(old_execution_commitment)
            ),
            (
                None
                if old_execution_checkpoint is None
                else _encode_runtime_checkpoint_venue_execution_checkpoint(
                    old_execution_checkpoint
                )
            ),
        ]
        if expected_old_cursor != row:
            raise ValueError("venue protection cursor row is not canonical")
        if position_scope in source_cursors:
            raise ValueError("venue protection cursor scope is duplicated")
        source_cursors[position_scope] = old_cursor
        normalized_cursor = old_cursor
        if (
            old_execution_checkpoint is not None
            and position_scope not in active_bootstrap_scopes
        ):
            assert compact_execution is not None
            normalized_cursor = _venue._ProtectionCursor(
                ordinal,
                head,
                mandate_id,
                compact_execution.commitment,
                _venue.VenueExecutionCheckpoint.from_execution(compact_execution),
            )
        cursors.append((position_scope, normalized_cursor))

    for target in bootstrap_targets:
        active = (
            target
            if type(target) is _venue._BootstrapBoundTargetRecord
            else _cast(_venue._ConsumedBootstrapBoundTargetRecord, target).active_record
        )
        if (
            type(target) is _venue._BootstrapBoundTargetRecord
            and source_cursors.get(active.position_scope)
            != active._neutral_checkpoint_proof.cursor
        ):
            raise ValueError("venue active bootstrap cursor is stale or spliced")

    normalized_registry_count = old_registry_count
    normalized_registry_commitment = old_registry_commitment
    if execution_snapshots:
        registry_pairs = {
            (snapshot.seen_facts.count, snapshot.seen_facts.commitment)
            for snapshot in execution_snapshots
        }
        if len(registry_pairs) != 1:
            raise ValueError("compact venue execution registries do not share one head")
        normalized_registry_count, normalized_registry_commitment = next(
            iter(registry_pairs)
        )
    elif old_registry_count is not None:
        raise ValueError("venue registry head has no selected execution scope")

    restored = _venue._m2_restore_compact_venue_book(
        scope=scope,
        account_authority_epoch=account_epoch,
        unresolved_account_execution_reconciliation_count=unresolved_account_count,
        execution_registry_count=normalized_registry_count,
        execution_registry_commitment=normalized_registry_commitment,
        registry_transition_head_commitment=transition_head,
        authority_epochs=tuple(authority_epochs),
        effects=effects,
        claims=tuple(claims),
        owners=tuple(owners),
        acquisition_correlations=tuple(acquisition_correlations),
        closure_heads=tuple(closure_heads),
        economic_high_waters=tuple(economic_high_waters),
        human_coverages=tuple(human_coverages),
        broker_coverages=tuple(broker_coverages),
        coverage_provenances=tuple(coverage_provenances),
        reconciliations=tuple(reconciliations),
        execution_reconciliations=tuple(execution_reconciliations),
        bootstrap_targets=tuple(bootstrap_targets),
        execution_snapshots=tuple(execution_snapshots),
        protection_cursors=tuple(cursors),
    )
    normalized_bootstrap_rows = _encode_runtime_checkpoint_venue_bootstrap_target_rows(
        restored,
        selection,
    )
    if normalized_bootstrap_rows[1] != len(bootstrap_rows):
        raise ValueError("venue compact bootstrap target cardinality changed")
    if (
        _encode_runtime_checkpoint_venue_authority_epoch_rows(restored, selection)
        != fields[6]
        or _encode_runtime_checkpoint_venue_effect_rows(restored, selection)
        != fields[7]
        or _encode_runtime_checkpoint_venue_claim_rows(restored, selection) != fields[8]
        or _encode_runtime_checkpoint_venue_owner_attempt_rows(restored, selection)
        != fields[9]
        or _encode_runtime_checkpoint_venue_correlation_rows(restored, selection)
        != fields[10]
        or _encode_runtime_checkpoint_venue_closure_head_rows(restored, selection)
        != fields[11]
        or _encode_runtime_checkpoint_venue_high_water_rows(restored, selection)
        != fields[12]
        or _encode_runtime_checkpoint_venue_human_coverage_rows(restored, selection)
        != fields[13]
        or _encode_runtime_checkpoint_venue_broker_coverage_rows(restored, selection)
        != fields[14]
        or _encode_runtime_checkpoint_venue_reconciliation_rows(restored, selection)
        != fields[16]
        or _encode_runtime_checkpoint_venue_execution_reconciliation_rows(
            restored, selection
        )
        != fields[17]
    ):
        raise ValueError("venue current rows disagree with the repository selection")
    expected_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-venue/state/v1",
        _cast(list[object], value)[:-1],
    )
    if (
        _operations._decode_m2_bytes("venue checkpoint commitment", fields[21])
        != expected_commitment
    ):
        raise ValueError("venue checkpoint commitment is stale or spliced")
    return restored


def _decode_compact_effect_authorization_row(
    value: object,
) -> tuple[
    _authority._EffectAuthorization,
    _authority.ClaimEffect | _authority.ClaimAcquisitionEffect | None,
]:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.authority.EffectAuthorization/v1",
        5,
    )
    authorization = _authority._EffectAuthorization(
        _operations._decode_m2_broker_effect_request(fields[0]),
        _operations._decode_m2_m1_as(
            "effect authorization session", fields[1], _identity.SessionId
        ),
        (
            None
            if fields[2] is None
            else _operations._decode_m2_m1_as(
                "effect authorization manual flatten",
                fields[2],
                _identity.ManualFlattenId,
            )
        ),
        (
            None
            if fields[3] is None
            else _operations._decode_m2_m1_as(
                "effect authorization emergency grant",
                fields[3],
                _identity.EmergencyGrantId,
            )
        ),
    )
    claim: _authority.ClaimEffect | _authority.ClaimAcquisitionEffect | None = None
    if fields[4] is not None:
        if type(fields[4]) is not list or not fields[4]:
            raise ValueError("effect claim checkpoint row is malformed")
        claim_tag = fields[4][0]
        if claim_tag == "m2.authority.ClaimEffect/v1":
            claim_fields = _operations._require_m2_aggregate(
                fields[4],
                "m2.authority.ClaimEffect/v1",
                3,
            )
            claim = _authority.ClaimEffect(
                _operations._decode_m2_m1_as(
                    "effect claim input", claim_fields[0], _identity.AuthorityInputId
                ),
                _operations._decode_m2_m1_as(
                    "effect claim id", claim_fields[1], _identity.EffectId
                ),
                _operations._decode_m2_m1_as(
                    "effect claim occurrence",
                    claim_fields[2],
                    _identity.ClaimOccurrenceId,
                ),
            )
        elif claim_tag == "m2.authority.ClaimAcquisitionEffect/v1":
            claim_fields = _operations._require_m2_aggregate(
                fields[4],
                "m2.authority.ClaimAcquisitionEffect/v1",
                4,
            )
            claim = _authority.ClaimAcquisitionEffect(
                _operations._decode_m2_m1_as(
                    "acquisition claim input",
                    claim_fields[0],
                    _identity.AuthorityInputId,
                ),
                _operations._decode_m2_m1_as(
                    "acquisition claim effect", claim_fields[1], _identity.EffectId
                ),
                _operations._decode_m2_m1_as(
                    "acquisition claim occurrence",
                    claim_fields[2],
                    _identity.ClaimOccurrenceId,
                ),
                _decode_compact_acquisition_claim_permit(claim_fields[3]),
            )
        else:
            raise ValueError("effect claim checkpoint variant is not admitted")
    if (
        _encode_runtime_checkpoint_effect_authorization_row(authorization, claim)
        != value
    ):
        raise ValueError("effect authorization checkpoint row is not canonical")
    return authorization, claim


def _decode_compact_manual_row(value: object) -> _authority._ManualFlatten:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.authority.ManualFlatten/v1",
        4,
    )
    command = _operations._decode_m2_begin_manual_flatten(fields[0])
    phase = _decode_checkpoint_enum_value(
        "manual phase",
        fields[1],
        "m1.authority.FlattenPhase",
        _authority._FlattenPhase,
    )
    cancel_effect_ids = tuple(
        _operations._decode_m2_m1_as(
            "manual cancel effect",
            row,
            _identity.EffectId,
        )
        for row in _decode_checkpoint_collection_rows(
            fields[2],
            "m2.authority.CancelEffects/v1",
        )
    )
    sell_effect_id = (
        None
        if fields[3] is None
        else _operations._decode_m2_m1_as(
            "manual sell effect",
            fields[3],
            _identity.EffectId,
        )
    )
    decoded = _authority._ManualFlatten(
        command,
        phase,
        cancel_effect_ids,
        sell_effect_id,
    )
    if _encode_runtime_checkpoint_manual_row(decoded) != value:
        raise ValueError("manual checkpoint row is not canonical")
    return decoded


def _decode_compact_emergency_grant(
    value: object,
) -> _authority._EmergencyGrant | None:
    if value is None:
        return None
    fields = _operations._require_m2_aggregate(
        value,
        "m2.authority.EmergencyGrant/v1",
        7,
    )
    decoded = _authority._EmergencyGrant(
        _operations._decode_m2_m1_as(
            "emergency grant id", fields[0], _identity.EmergencyGrantId
        ),
        _operations._decode_m2_m1_as(
            "emergency grant account", fields[1], _identity.AccountId
        ),
        _operations._decode_m2_m1_as(
            "emergency grant symbol", fields[2], _identity.SymbolId
        ),
        _operations._decode_m2_m1_as(
            "emergency grant session", fields[3], _identity.SessionId
        ),
        _operations._decode_m2_m1_as(
            "emergency grant actor", fields[4], _identity.ActorId
        ),
        _operations._require_exact_text("emergency grant reason", fields[5]),
        _operations._decode_m2_m1_as(
            "emergency grant evidence", fields[6], _identity.EvidenceReference
        ),
    )
    if _encode_runtime_checkpoint_emergency_grant(decoded) != value:
        raise ValueError("emergency grant checkpoint row is not canonical")
    return decoded


def _decode_optional_checkpoint_digest(name: str, value: object) -> bytes | None:
    return None if value is None else _operations._decode_m2_bytes(name, value)


def _decode_compact_acquisition_claim_permit(
    value: object,
) -> _authority.AcquisitionClaimPermit:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.authority.AcquisitionClaimPermit/v1",
        21,
    )
    decoded = _authority._new_acquisition_claim_permit(
        input_id=_operations._decode_m2_m1_as(
            "acquisition claim permit input", fields[0], _identity.AuthorityInputId
        ),
        application_generation_id=_operations._decode_m2_m1_as(
            "acquisition claim permit application",
            fields[1],
            _identity.ApplicationGenerationId,
        ),
        position_scope=_operations._decode_m2_position_scope(fields[2]),
        session_id=_operations._decode_m2_m1_as(
            "acquisition claim permit session", fields[3], _identity.SessionId
        ),
        generation_id=_operations._decode_m2_m1_as(
            "acquisition claim permit generation",
            fields[4],
            _identity.AcquisitionGenerationId,
        ),
        acquisition_mandate_id=_operations._decode_m2_m1_as(
            "acquisition claim permit mandate",
            fields[5],
            _identity.AcquisitionMandateId,
        ),
        protection_mandate_id=_operations._decode_m2_m1_as(
            "acquisition claim permit protection mandate",
            fields[6],
            _identity.MandateId,
        ),
        binding_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit binding", fields[7]
        ),
        emergency_recovery_compatibility_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit emergency compatibility", fields[8]
        ),
        controller_head=_operations._decode_m2_bytes(
            "acquisition claim permit controller", fields[9]
        ),
        successor_ordinal=_operations._require_exact_int(
            "acquisition claim permit successor ordinal", fields[10]
        ),
        execution_snapshot_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit execution", fields[11]
        ),
        scope_execution_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit scope execution", fields[12]
        ),
        venue_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit venue", fields[13]
        ),
        authority_context_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit authority", fields[14]
        ),
        protection_commitment=_decode_optional_checkpoint_digest(
            "acquisition claim permit protection", fields[15]
        ),
        effect_id=_operations._decode_m2_m1_as(
            "acquisition claim permit effect", fields[16], _identity.EffectId
        ),
        claim_occurrence_id=_operations._decode_m2_m1_as(
            "acquisition claim permit occurrence",
            fields[17],
            _identity.ClaimOccurrenceId,
        ),
        currentness_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit currentness", fields[18]
        ),
        descriptor_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit descriptor", fields[19]
        ),
        active_commitment=_operations._decode_m2_bytes(
            "acquisition claim permit active", fields[20]
        ),
    )
    if _encode_runtime_checkpoint_claim_permit(decoded) != value:
        raise ValueError("acquisition claim permit is not canonical")
    return decoded


def _decode_compact_acquisition_effect_permit(
    value: object,
) -> _authority.AcquisitionEffectPermit:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.authority.AcquisitionEffectPermit/v1",
        21,
    )
    decoded = _authority._new_acquisition_effect_permit(
        input_id=_operations._decode_m2_m1_as(
            "acquisition permit input", fields[0], _identity.AuthorityInputId
        ),
        application_generation_id=_operations._decode_m2_m1_as(
            "acquisition permit application",
            fields[1],
            _identity.ApplicationGenerationId,
        ),
        position_scope=_operations._decode_m2_position_scope(fields[2]),
        session_id=_operations._decode_m2_m1_as(
            "acquisition permit session", fields[3], _identity.SessionId
        ),
        generation_id=_operations._decode_m2_m1_as(
            "acquisition permit generation",
            fields[4],
            _identity.AcquisitionGenerationId,
        ),
        acquisition_mandate_id=_operations._decode_m2_m1_as(
            "acquisition permit mandate",
            fields[5],
            _identity.AcquisitionMandateId,
        ),
        protection_mandate_id=_operations._decode_m2_m1_as(
            "acquisition permit protection mandate",
            fields[6],
            _identity.MandateId,
        ),
        binding_commitment=_operations._decode_m2_bytes(
            "acquisition permit binding", fields[7]
        ),
        emergency_recovery_compatibility_commitment=_operations._decode_m2_bytes(
            "acquisition permit emergency compatibility", fields[8]
        ),
        predecessor_controller_head=_operations._decode_m2_bytes(
            "acquisition permit predecessor controller", fields[9]
        ),
        controller_head=_operations._decode_m2_bytes(
            "acquisition permit controller", fields[10]
        ),
        successor_ordinal=_operations._require_exact_int(
            "acquisition permit successor ordinal", fields[11]
        ),
        execution_snapshot_commitment=_operations._decode_m2_bytes(
            "acquisition permit execution", fields[12]
        ),
        scope_execution_commitment=_operations._decode_m2_bytes(
            "acquisition permit scope execution", fields[13]
        ),
        venue_commitment=_operations._decode_m2_bytes(
            "acquisition permit venue", fields[14]
        ),
        authority_context_commitment=_operations._decode_m2_bytes(
            "acquisition permit authority", fields[15]
        ),
        protection_commitment=_decode_optional_checkpoint_digest(
            "acquisition permit protection", fields[16]
        ),
        terms=_operations._decode_m2_acquisition_effect_terms(fields[17]),
        effect_id=_operations._decode_m2_m1_as(
            "acquisition permit effect", fields[18], _identity.EffectId
        ),
        request_occurrence_id=_operations._decode_m2_m1_as(
            "acquisition permit request occurrence",
            fields[19],
            _identity.RequestOccurrenceId,
        ),
        client_order_id=_operations._decode_m2_m1_as(
            "acquisition permit client order", fields[20], _identity.ClientOrderId
        ),
    )
    if _encode_runtime_checkpoint_acquisition_effect_permit(decoded) != value:
        raise ValueError("acquisition effect permit is not canonical")
    return decoded


def _decode_compact_acquisition_currentness(
    value: object,
) -> _authority._AcquisitionCurrentnessEntry:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.authority.AcquisitionCurrentness/v1",
        15,
    )
    decoded = _authority._new_acquisition_currentness_entry(
        source_kind=_decode_checkpoint_enum_value(
            "acquisition currentness source",
            fields[0],
            "m1.authority.AcquisitionCurrentnessSourceKind",
            _authority._AcquisitionCurrentnessSourceKind,
        ),
        application_generation_id=_operations._decode_m2_m1_as(
            "acquisition currentness application",
            fields[1],
            _identity.ApplicationGenerationId,
        ),
        position_scope=_operations._decode_m2_position_scope(fields[2]),
        session_id=_operations._decode_m2_m1_as(
            "acquisition currentness session", fields[3], _identity.SessionId
        ),
        generation_id=_operations._decode_m2_m1_as(
            "acquisition currentness generation",
            fields[4],
            _identity.AcquisitionGenerationId,
        ),
        acquisition_mandate_id=_operations._decode_m2_m1_as(
            "acquisition currentness mandate",
            fields[5],
            _identity.AcquisitionMandateId,
        ),
        protection_mandate_id=_operations._decode_m2_m1_as(
            "acquisition currentness protection mandate",
            fields[6],
            _identity.MandateId,
        ),
        binding_commitment=_operations._decode_m2_bytes(
            "acquisition currentness binding", fields[7]
        ),
        emergency_recovery_compatibility_commitment=_operations._decode_m2_bytes(
            "acquisition currentness emergency compatibility", fields[8]
        ),
        controller_head=_operations._decode_m2_bytes(
            "acquisition currentness controller", fields[9]
        ),
        successor_ordinal=_operations._require_exact_int(
            "acquisition currentness successor ordinal", fields[10]
        ),
        scope_execution_commitment=_operations._decode_m2_bytes(
            "acquisition currentness scope execution", fields[11]
        ),
        venue_commitment=_operations._decode_m2_bytes(
            "acquisition currentness venue", fields[12]
        ),
        protection_commitment=_decode_optional_checkpoint_digest(
            "acquisition currentness protection", fields[13]
        ),
        predecessor_slot_commitment=_operations._decode_m2_bytes(
            "acquisition currentness predecessor slot", fields[14]
        ),
    )
    if _encode_runtime_checkpoint_acquisition_currentness(decoded) != value:
        raise ValueError("acquisition currentness is not canonical")
    return decoded


def _decode_compact_acquisition_descriptors(
    rows: tuple[object, ...],
) -> tuple[_authority._AcquisitionEffectDescriptor, ...]:
    decoded: list[_authority._AcquisitionEffectDescriptor] = []
    seen: set[_identity.EffectId] = set()
    for row in rows:
        fields = _operations._require_m2_aggregate(
            row,
            "m2.authority.AcquisitionDescriptor/v1",
            2,
        )
        effect_id = _operations._decode_m2_m1_as(
            "acquisition descriptor effect", fields[0], _identity.EffectId
        )
        descriptor = _authority._new_acquisition_effect_descriptor(
            _decode_compact_acquisition_effect_permit(fields[1])
        )
        if descriptor.permit.effect_id != effect_id or effect_id in seen:
            raise ValueError("acquisition descriptor identity is duplicated or spliced")
        if [
            "m2.authority.AcquisitionDescriptor/v1",
            _operations._encode_m2_m1_atom(effect_id),
            _encode_runtime_checkpoint_acquisition_effect_permit(descriptor.permit),
        ] != row:
            raise ValueError("acquisition descriptor is not canonical")
        seen.add(effect_id)
        decoded.append(descriptor)
    return tuple(decoded)


def _decode_compact_acquisition_slots(
    rows: tuple[object, ...],
    descriptors: tuple[_authority._AcquisitionEffectDescriptor, ...],
) -> tuple[
    tuple[
        _authority._AcquisitionCurrentnessEntry,
        _authority._AcquisitionEffectDescriptor
        | _authority._AcquisitionInactiveSlot
        | None,
        _authority._AcquisitionActiveEffect
        | _authority._AcquisitionInactiveSlot
        | None,
    ],
    ...,
]:
    descriptor_by_effect = {
        descriptor.permit.effect_id: descriptor for descriptor in descriptors
    }
    decoded: list[
        tuple[
            _authority._AcquisitionCurrentnessEntry,
            _authority._AcquisitionEffectDescriptor
            | _authority._AcquisitionInactiveSlot
            | None,
            _authority._AcquisitionActiveEffect
            | _authority._AcquisitionInactiveSlot
            | None,
        ]
    ] = []
    seen: set[_fills.PositionScope] = set()
    for row in rows:
        fields = _operations._require_m2_aggregate(
            row,
            "m2.authority.AcquisitionSlot/v1",
            3,
        )
        position_scope = _operations._decode_m2_position_scope(fields[0])
        currentness = _decode_compact_acquisition_currentness(fields[1])
        if currentness.position_scope != position_scope or position_scope in seen:
            raise ValueError("acquisition slot scope is duplicated or spliced")
        descriptor: (
            _authority._AcquisitionEffectDescriptor
            | _authority._AcquisitionInactiveSlot
            | None
        )
        active: (
            _authority._AcquisitionActiveEffect
            | _authority._AcquisitionInactiveSlot
            | None
        )
        if fields[2] == ["m2.authority.AcquisitionSlotEmpty/v1"]:
            descriptor = None
            active = None
        elif (
            type(fields[2]) is list
            and fields[2]
            and fields[2][0] == ("m2.authority.AcquisitionSlotActive/v1")
        ):
            slot_fields = _operations._require_m2_aggregate(
                fields[2],
                "m2.authority.AcquisitionSlotActive/v1",
                2,
            )
            effect_id = _operations._decode_m2_m1_as(
                "active acquisition slot effect", slot_fields[0], _identity.EffectId
            )
            descriptor = descriptor_by_effect.get(effect_id)
            if (
                descriptor is None
                or descriptor.commitment
                != _operations._decode_m2_bytes(
                    "active acquisition slot descriptor", slot_fields[1]
                )
            ):
                raise ValueError(
                    "active acquisition slot descriptor is absent or spliced"
                )
            active = _authority._new_acquisition_active_effect(descriptor)
        elif (
            type(fields[2]) is list
            and fields[2]
            and fields[2][0] == ("m2.authority.AcquisitionSlotInactive/v1")
        ):
            slot_fields = _operations._require_m2_aggregate(
                fields[2],
                "m2.authority.AcquisitionSlotInactive/v1",
                3,
            )
            effect_id = _operations._decode_m2_m1_as(
                "inactive acquisition slot effect",
                slot_fields[0],
                _identity.EffectId,
            )
            source_descriptor = descriptor_by_effect.get(effect_id)
            if (
                source_descriptor is None
                or source_descriptor.commitment
                != _operations._decode_m2_bytes(
                    "inactive acquisition slot descriptor", slot_fields[1]
                )
            ):
                raise ValueError(
                    "inactive acquisition slot descriptor is absent or spliced"
                )
            inactive = _authority._new_acquisition_inactive_slot(
                _authority._new_acquisition_active_effect(source_descriptor),
                source_descriptor,
                _operations._decode_m2_m1_as(
                    "inactive acquisition successor",
                    slot_fields[2],
                    _identity.AcquisitionGenerationId,
                ),
            )
            descriptor = inactive
            active = inactive
        else:
            raise ValueError("acquisition slot variant is not admitted")
        encoded_value, _ = _encode_runtime_checkpoint_acquisition_slot_value(
            descriptor,
            active,
        )
        if encoded_value != fields[2]:
            raise ValueError("acquisition slot value is not canonical")
        seen.add(position_scope)
        decoded.append((currentness, descriptor, active))
    return tuple(decoded)


def _decode_compact_authority_checkpoint(
    value: object,
    *,
    venue: _venue.VenueRecoveryBook,
    venue_commitment: bytes,
    application_generation_id: _identity.ApplicationGenerationId,
    selected_position_scopes: tuple[_fills.PositionScope, ...],
    selected_effect_ids: tuple[_identity.EffectId, ...],
) -> _authority.ExecutionAuthorityState:
    fields = _operations._require_m2_aggregate(
        value,
        _M2_AUTHORITY_CHECKPOINT_TAG,
        13,
    )
    phase = _decode_checkpoint_enum_value(
        "authority phase",
        fields[0],
        "m1.authority.EnginePhase",
        _authority.EnginePhase,
    )
    mode = _decode_checkpoint_enum_value(
        "authority mode",
        fields[1],
        "m1.authority.TradingMode",
        _authority.TradingMode,
    )
    supervisor_fence = _decode_checkpoint_enum_value(
        "authority supervisor fence",
        fields[2],
        "m1.authority.SupervisorFence",
        _authority.SupervisorFence,
    )
    if type(fields[3]) is not bool:
        raise TypeError("authority kill flag must be exact bool")
    session_id = (
        None
        if fields[4] is None
        else _operations._decode_m2_m1_as(
            "authority session", fields[4], _identity.SessionId
        )
    )
    budget_fields = _operations._require_m2_aggregate(
        fields[5],
        "m2.authority.RequestBudget/v1",
        2,
    )
    budget = _authority.RequestBudget(
        _operations._require_exact_int("authority budget remaining", budget_fields[0]),
        _operations._require_exact_int(
            "authority budget safety reserve", budget_fields[1]
        ),
    )
    venue_fields = _operations._require_m2_aggregate(
        fields[6],
        "m2.authority.VenueRef/v1",
        5,
    )
    if (
        _operations._decode_m2_m1_as(
            "authority venue generation",
            venue_fields[0],
            _identity.ApplicationGenerationId,
        )
        != application_generation_id
        or _operations._decode_m2_m1_as(
            "authority venue broker", venue_fields[1], _identity.BrokerId
        )
        != venue.scope.broker
        or _operations._decode_m2_m1_as(
            "authority venue environment", venue_fields[2], _identity.EnvironmentId
        )
        != venue.scope.environment
        or _operations._decode_m2_m1_as(
            "authority venue account", venue_fields[3], _identity.AccountId
        )
        != venue.scope.account
        or _operations._decode_m2_bytes("authority venue commitment", venue_fields[4])
        != venue_commitment
    ):
        raise ValueError("authority venue reference is stale or spliced")

    effect_rows = _decode_checkpoint_collection_rows(
        fields[8],
        "m2.authority.EffectAuthorizations/v1",
    )
    manual_rows = _decode_checkpoint_collection_rows(
        fields[9],
        "m2.authority.ManualFlattens/v1",
    )
    descriptor_rows = _decode_checkpoint_collection_rows(
        fields[10],
        "m2.authority.AcquisitionDescriptors/v1",
    )
    slot_rows = _decode_checkpoint_collection_rows(
        fields[11],
        "m2.authority.AcquisitionSlots/v1",
    )
    acquisition_descriptors = _decode_compact_acquisition_descriptors(descriptor_rows)
    acquisition_slots = _decode_compact_acquisition_slots(
        slot_rows,
        acquisition_descriptors,
    )
    restored = _authority._m2_restore_compact_authority_state(
        phase=phase,
        mode=mode,
        supervisor_fence=supervisor_fence,
        kill_engaged=fields[3],
        session_id=session_id,
        budget=budget,
        venue=venue,
        effect_authorizations=tuple(
            _decode_compact_effect_authorization_row(row) for row in effect_rows
        ),
        acquisition_descriptors=acquisition_descriptors,
        acquisition_slots=acquisition_slots,
        manuals=tuple(_decode_compact_manual_row(row) for row in manual_rows),
        emergency_grant=_decode_compact_emergency_grant(fields[7]),
    )
    expected, _, _ = _encode_runtime_checkpoint_authority(
        restored,
        venue_commitment,
        application_generation_id,
        selected_position_scopes,
        selected_effect_ids,
    )
    if expected != value:
        raise ValueError("authority checkpoint is not compact-canonical")
    expected_commitment = _checkpoint_row_commitment(
        b"execution-core/m2-authority/checkpoint/v1",
        _cast(list[object], value)[:-1],
    )
    if (
        _operations._decode_m2_bytes("authority checkpoint commitment", fields[12])
        != expected_commitment
    ):
        raise ValueError("authority checkpoint commitment is stale or spliced")
    return restored


def _restore_compact_execution_from_selected_rows(
    state: _position._M2ExecutionState,
    *,
    scope_id: int,
    roots: tuple[_records.RootFillRecord, ...],
    fact_heads: tuple[_records.ExecutionFactHeadRecord, ...],
    current_facts: tuple[_records.ExecutionFactRecord, ...],
) -> _position.ExecutionSnapshot:
    """Build one current-root owner while intentionally omitting seen-fact history."""

    roots_by_id = {root.root_fill_key_id: root for root in roots}
    heads_by_root = {head.root_fill_key_id: head for head in fact_heads}
    facts_by_id = {fact.fact_id: fact for fact in current_facts}
    if (
        len(roots_by_id) != len(roots)
        or len(heads_by_root) != len(fact_heads)
        or len(facts_by_id) != len(current_facts)
        or set(roots_by_id) != set(heads_by_root)
        or {head.fact_id for head in fact_heads} != set(facts_by_id)
    ):
        raise ValueError("compact execution current rows are incomplete or duplicated")
    position_scope = state.scope
    restored_heads = _fills.RootHeadIndex.empty(position_scope)
    tail = state.tail_fold_input
    for ordinal, root in enumerate(roots):
        head_record = heads_by_root[root.root_fill_key_id]
        fact = facts_by_id[head_record.fact_id]
        if (
            root.scope_id != scope_id
            or fact.scope_id != scope_id
            or root.application_generation_id != fact.application_generation_id
            or root.execution_profile_id != fact.execution_profile_id
            or root.current_fact_id != fact.fact_id
            or root.economics_head_ordinal != fact.fact_ordinal
            or head_record.fact_ordinal != fact.fact_ordinal
            or fact.root_fill_key_id != root.root_fill_key_id
            or root.current_kind != fact.kind
            or root.current_authority != fact.authority
            or root.current_side != fact.side
            or root.current_quantity != fact.quantity
            or root.current_price != fact.price
        ):
            raise ValueError("compact execution root and current fact are spliced")
        root_key = _identity.RootFillKey(
            position_scope.broker,
            position_scope.environment,
            position_scope.account,
            root.root_fill_id,
        )
        prefix_heads = b""
        prefix_proof = b""
        if tail is not None and tail.tail_root_key == root_key:
            prefix_heads = tail.prefix_heads_commitment
            prefix_proof = tail.commitment
        restored_heads = restored_heads.append(
            _fills.RootHead(
                root_key=root_key,
                original_sequence=ordinal,
                scope=_fills.ExecutionScope(
                    position_scope.broker,
                    position_scope.environment,
                    position_scope.account,
                    fact.order_id,
                    position_scope.symbol_id,
                    _fills.ExecutionSide(fact.side),
                ),
                authority=_fills.ExecutionAuthority(fact.authority),
                current_source_event_id=fact.source_event_id,
                kind=_fills.FactKind(fact.kind),
                quantity=fact.quantity,
                price=fact.price,
                prefix_heads_commitment=prefix_heads,
                prefix_proof_commitment=prefix_proof,
            )
        )
    return _position._m2_restore_compact_execution_snapshot(
        state,
        restored_heads,
        _fills.SeenFactIndex.empty(position_scope),
    )


def _decode_compact_acquisition_generation(
    value: object,
) -> _acquisition.GenerationRecordView:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.acquisition.Generation/v1",
        11,
    )
    binding = _acquisition._new_generation_binding_view(
        generation_id=_operations._decode_m2_m1_as(
            "acquisition generation id",
            fields[0],
            _identity.AcquisitionGenerationId,
        ),
        application_generation_id=_operations._decode_m2_m1_as(
            "acquisition generation application",
            fields[1],
            _identity.ApplicationGenerationId,
        ),
        position_scope=_operations._decode_m2_position_scope(fields[2]),
        successor_ordinal=_operations._require_exact_int(
            "acquisition generation successor ordinal",
            fields[3],
        ),
        dual_mandate_binding_commitment=_operations._decode_m2_bytes(
            "acquisition generation mandate commitment",
            fields[4],
        ),
        predecessor_or_genesis_head_commitment=_operations._decode_m2_bytes(
            "acquisition generation predecessor commitment",
            fields[5],
        ),
        emergency_recovery_compatibility_commitment=_operations._decode_m2_bytes(
            "acquisition generation compatibility commitment",
            fields[6],
        ),
    )
    record = _acquisition._new_generation_record_view(
        binding=binding,
        economics_head_commitment=_operations._decode_m2_bytes(
            "acquisition generation economics commitment",
            fields[7],
        ),
        serving_class=_decode_checkpoint_enum_value(
            "acquisition generation serving class",
            fields[8],
            "m1.acquisition.GenerationServingClass",
            _acquisition.GenerationServingClass,
        ),
        closure_summary_commitment=_operations._decode_m2_bytes(
            "acquisition generation closure commitment",
            fields[9],
        ),
    )
    if (
        _operations._decode_m2_bytes(
            "acquisition generation record commitment",
            fields[10],
        )
        != _acquisition._generation_record_view_commitment(
            record.binding,
            record.economics_head_commitment,
            record.serving_class,
            record.closure_summary_commitment,
        )
        or _encode_runtime_checkpoint_generation(record) != value
    ):
        raise ValueError("acquisition generation record is not canonical")
    return record


def _decode_compact_acquisition_controller(
    value: object,
) -> _acquisition.SymbolAcquisitionController:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.acquisition.Controller/v1",
        13,
    )
    live_generation_id = _operations._decode_m2_m1_as(
        "acquisition controller live generation",
        fields[4],
        _identity.AcquisitionGenerationId,
    )
    controller = _acquisition._new_symbol_acquisition_controller(
        application_generation_id=_operations._decode_m2_m1_as(
            "acquisition controller application",
            fields[0],
            _identity.ApplicationGenerationId,
        ),
        position_scope=_operations._decode_m2_position_scope(fields[1]),
        controller_head=_operations._decode_m2_bytes(
            "acquisition controller head",
            fields[2],
        ),
        successor_ordinal=_operations._require_exact_int(
            "acquisition controller successor ordinal",
            fields[3],
        ),
        live_generation_id=live_generation_id,
        recovery_class=_decode_checkpoint_enum_value(
            "acquisition controller recovery class",
            fields[5],
            "m1.acquisition.AcquisitionRecoveryClass",
            _acquisition.AcquisitionRecoveryClass,
        ),
        scope_execution_commitment=_operations._decode_m2_bytes(
            "acquisition controller execution commitment",
            fields[6],
        ),
        venue_commitment=_operations._decode_m2_bytes(
            "acquisition controller venue commitment",
            fields[7],
        ),
        authority_context_commitment=_operations._decode_m2_bytes(
            "acquisition controller authority commitment",
            fields[8],
        ),
        protection_commitment=(
            None
            if fields[9] is None
            else _operations._decode_m2_bytes(
                "acquisition controller protection commitment",
                fields[9],
            )
        ),
        binding_commitment=_operations._decode_m2_bytes(
            "acquisition controller binding commitment",
            fields[10],
        ),
        compatibility_commitment=_operations._decode_m2_bytes(
            "acquisition controller compatibility commitment",
            fields[11],
        ),
    )
    if (
        _operations._decode_m2_bytes(
            "acquisition controller commitment",
            fields[12],
        )
        != controller.commitment
    ):
        raise ValueError("acquisition controller commitment does not match")
    return controller


def _decode_compact_acquisition_stream_route(
    value: object,
    records_by_id: dict[
        _identity.AcquisitionGenerationId,
        _acquisition.GenerationRecordView,
    ],
) -> tuple[_identity.MarketStreamGenerationId, _identity.AcquisitionGenerationId]:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.acquisition.MarketStreamRoute/v1",
        3,
    )
    stream_generation = _operations._decode_m2_m1_as(
        "acquisition stream generation",
        fields[0],
        _identity.MarketStreamGenerationId,
    )
    generation_id = _operations._decode_m2_m1_as(
        "acquisition stream owner generation",
        fields[1],
        _identity.AcquisitionGenerationId,
    )
    record = records_by_id.get(generation_id)
    if record is None:
        raise ValueError("acquisition stream route leaves the bounded registry")
    if _operations._decode_m2_bytes(
        "acquisition stream route commitment",
        fields[2],
    ) != _acquisition._market_stream_generation_route_commitment(
        stream_generation,
        record.binding,
    ):
        raise ValueError("acquisition stream route commitment does not match")
    return stream_generation, generation_id


def _decode_compact_acquisition_lineage_route(
    value: object,
) -> tuple[
    _acquisition.GenerationRouteKind,
    object,
    _identity.AcquisitionGenerationId,
]:
    fields = _operations._require_m2_aggregate(
        value,
        "m2.acquisition.LineageRoute/v1",
        5,
    )
    route_kind = _decode_checkpoint_enum_value(
        "acquisition lineage route kind",
        fields[0],
        "m1.acquisition.GenerationRouteKind",
        _acquisition.GenerationRouteKind,
    )
    source = _operations._decode_m2_m1_atom(fields[1])
    generation_id = _operations._decode_m2_m1_as(
        "acquisition lineage generation",
        fields[2],
        _identity.AcquisitionGenerationId,
    )
    source_key = _acquisition._lineage_source_key(route_kind, source)
    route = _acquisition._new_generation_route_view(
        route_kind=route_kind,
        source_commitment=_acquisition._commit_parts(
            b"execution-core/acquisition/lineage-source/v1",
            source_key,
        ),
        generation_id=generation_id,
    )
    if _operations._decode_m2_bytes(
        "acquisition lineage route commitment",
        fields[4],
    ) != _acquisition._generation_route_commitment(
        route.route_kind,
        route.source_commitment,
        route.generation_id,
    ):
        raise ValueError("acquisition lineage route commitment does not match")
    return route_kind, source, generation_id


def _decode_source_acquisition_checkpoint(
    value: list[object],
    *,
    selection_proof: _records.RuntimeCheckpointSelectionProof,
    scope_id: int,
) -> _acquisition.AcquisitionControllerState:
    """Authenticate one active C0 owner before any compact-context rebind."""

    fields = _operations._require_m2_aggregate(
        value,
        _M2_ACQUISITION_STATE_TAG,
        16,
    )
    controller = _decode_compact_acquisition_controller(fields[6])
    mandate = _operations._decode_m2_acquisition_mandate(fields[7])
    live = _decode_compact_acquisition_generation(fields[8])
    unresolved_rows = _decode_checkpoint_collection_rows(
        fields[10],
        "m2.acquisition.UnresolvedGenerations/v1",
    )
    generations = (live,) + tuple(
        _decode_compact_acquisition_generation(row) for row in unresolved_rows
    )
    records_by_id = {row.binding.generation_id: row for row in generations}
    if len(records_by_id) != len(generations):
        raise ValueError("acquisition bounded generation is duplicated")
    unresolved_route_rows = _decode_checkpoint_collection_rows(
        fields[11],
        "m2.acquisition.UnresolvedMarketStreamRoutes/v1",
    )
    stream_routes = (
        _decode_compact_acquisition_stream_route(fields[9], records_by_id),
    ) + tuple(
        _decode_compact_acquisition_stream_route(row, records_by_id)
        for row in unresolved_route_rows
    )
    lineage_rows = _decode_checkpoint_collection_rows(
        fields[12],
        "m2.acquisition.LineageRoutes/v1",
    )
    lineage_routes = tuple(
        _decode_compact_acquisition_lineage_route(row) for row in lineage_rows
    )
    restored = _acquisition._m2_restore_compact_acquisition_controller(
        controller=controller,
        mandate=mandate,
        generation_records=generations,
        stream_routes=stream_routes,
        lineage_routes=lineage_routes,
    )
    selection = selection_proof._selection
    selected_controller = tuple(
        row for row in selection.controllers if row.scope_id == scope_id
    )
    selected_live = tuple(
        row for row in selection.live_generations if row.scope_id == scope_id
    )
    selected_live_current = tuple(
        row for row in selection.live_generation_current if row.scope_id == scope_id
    )
    selected_stream = tuple(
        row
        for row in selection.streams
        if row.scope_id == scope_id
        and row.stream_generation_id
        == mandate.protection_mandate.evidence_policy.stream_generation
    )
    if (
        len(selected_controller) != 1
        or len(selected_live) != 1
        or len(selected_live_current) != 1
        or len(selected_stream) != 1
    ):
        raise ValueError("active acquisition current proof is incomplete")
    selected_controller_row = selected_controller[0]
    selected_live_row = selected_live[0]
    selected_live_current_row = selected_live_current[0]
    selected_stream_row = selected_stream[0]
    if (
        restored.application_generation_id
        != selection_proof.request.application_generation_id
        or restored.position_scope != mandate.position_scope
        or controller.live_generation_id
        != selected_controller_row.live_acquisition_generation_id
        or controller.live_generation_id != selected_live_row.acquisition_generation_id
        or selected_live_current_row.acquisition_generation_id
        != selected_live_row.acquisition_generation_id
        or selected_live_row.status != live.serving_class.value
        or selected_live_row.successor_ordinal != live.binding.successor_ordinal
        or selected_live_row.mandate_commitment_sha256
        != live.binding.dual_mandate_binding_commitment.hex()
        or selected_live_row.emergency_compatibility_sha256
        != live.binding.emergency_recovery_compatibility_commitment.hex()
        or selected_controller_row.emergency_compatibility_sha256
        != controller._compatibility_commitment.hex()
        or selected_stream_row.application_generation_id
        != selection_proof.request.application_generation_id
        or selected_stream_row.acquisition_generation_id
        != selected_live_row.acquisition_generation_id
        or selected_stream_row.generation_mandate_commitment_sha256
        != selected_live_row.mandate_commitment_sha256
        or selected_stream_row.source_profile_id
        != selection_proof.request.market_source_profile_id
        or selected_stream_row.session_id != mandate.session_id
        or selected_stream_row.sequence_mode
        != mandate.protection_mandate.evidence_policy.sequence_mode.value
    ):
        raise ValueError("active acquisition checkpoint is spliced from current proof")
    reencoded, _ = _encode_runtime_checkpoint_acquisition(
        restored,
        selection,
        scope_id,
    )
    if reencoded != value:
        raise ValueError("active acquisition checkpoint is not canonical current state")
    return restored


def _decode_source_protection_checkpoint(
    value: list[object],
    *,
    selection_proof: _records.RuntimeCheckpointSelectionProof,
    scope_id: int,
    position_scope: _fills.PositionScope,
    compact_execution: _position.ExecutionSnapshot,
) -> _protection.PositionProtectionState:
    """Authenticate one active C0 protection owner, then compact-rebind it."""

    checkpoint = _decode_m2_protection_checkpoint_component(value)
    selection = selection_proof._selection
    controllers = tuple(
        row for row in selection.controllers if row.scope_id == scope_id
    )
    authorities = tuple(
        row for row in selection.protection_authorities if row.scope_id == scope_id
    )
    if len(controllers) != 1 or len(authorities) != 1:
        raise ValueError("active protection current proof is incomplete")
    controller = controllers[0]
    authority = authorities[0]
    active_stream_generation_id = authority.active_stream_generation_id
    active_acquisition_generation_id = authority.active_acquisition_generation_id
    active_mandate_commitment = authority.active_generation_mandate_commitment_sha256
    active_source_profile_id = authority.active_source_profile_id
    active_session_id = authority.active_session_id
    active_sequence_mode = authority.active_sequence_mode
    if (
        type(active_stream_generation_id) is not _identity.MarketStreamGenerationId
        or type(active_acquisition_generation_id)
        is not _identity.AcquisitionGenerationId
        or type(active_mandate_commitment) is not str
        or type(active_source_profile_id) is not str
        or type(active_session_id) is not _identity.SessionId
        or type(active_sequence_mode) is not str
    ):
        raise ValueError("active protection authority coordinates are partial")
    streams = tuple(
        row
        for row in selection.streams
        if row.scope_id == scope_id
        and row.stream_generation_id == active_stream_generation_id
    )
    if len(streams) != 1:
        raise ValueError("active protection stream proof is incomplete")
    stream = streams[0]
    if (
        stream.application_generation_id
        != selection_proof.request.application_generation_id
        or stream.acquisition_generation_id != active_acquisition_generation_id
        or stream.generation_mandate_commitment_sha256 != active_mandate_commitment
        or stream.source_profile_id != active_source_profile_id
        or stream.session_id != active_session_id
        or stream.sequence_mode != active_sequence_mode
    ):
        raise ValueError("active protection stream proof is spliced")
    authority_proof = _protection._m2_issue_protection_authority_proof(
        _protection._M2ProtectionAuthorityProof,
        selection_proof.request.application_generation_id,
        selection_proof.request.execution_profile_id,
        selection_proof.request.market_source_profile_id,
        scope_id,
        position_scope,
        controller.currentness_head_ordinal,
        controller.live_acquisition_generation_id,
        authority.authority_class,
        active_stream_generation_id,
        active_acquisition_generation_id,
        active_mandate_commitment,
        active_source_profile_id,
        active_session_id,
        _protection.MarketSequenceMode(active_sequence_mode),
        authority.expected_controller_head_ordinal,
        authority.state_commitment_sha256,
        authority.version_ordinal,
        checkpoint.mandate.evidence_policy.source_id,
    )
    source = _protection._m2_position_protection_from_checkpoint(
        checkpoint,
        authority_proof,
    )
    return _protection._m2_rebind_compact_protection_execution(
        source,
        compact_execution,
    )


def _restore_compact_runtime_checkpoint(
    checkpoint: RuntimeCheckpointEnvelope,
    selection_proof: _records.RuntimeCheckpointSelectionProof,
) -> _CompactRuntimeCheckpointOwners:
    """Restore only proof-complete bounded semantics from one inert loaded C0."""

    if not _envelope_is_authentic(checkpoint) or checkpoint._provenance != "LOADED":
        raise ValueError("compact hydration requires an authentic loaded checkpoint")
    if (
        type(selection_proof) is not _records.RuntimeCheckpointSelectionProof
        or not _records.RuntimeCheckpointSelectionProof._is_authentic(selection_proof)
    ):
        raise ValueError("compact hydration requires an authentic selection proof")
    predecessor = selection_proof.predecessor_checkpoint
    if predecessor is None:
        raise ValueError("compact hydration proof has no checkpoint predecessor")
    if (
        predecessor.application_generation_id != checkpoint.application_generation_id
        or predecessor.currentness_head_ordinal != checkpoint.currentness_head_ordinal
        or predecessor.checkpoint_version_ordinal
        != checkpoint.checkpoint_version_ordinal
        or predecessor.checkpoint_sha256 != checkpoint.payload_sha256
        or selection_proof.request.application_generation_id
        != checkpoint.application_generation_id
        or selection_proof.request.execution_profile_id
        != checkpoint.execution_profile_id
        or selection_proof.request.market_source_profile_id
        != checkpoint.market_source_profile_id
        or selection_proof.request.expected_checkpoint != predecessor
    ):
        raise ValueError("compact hydration proof predecessor is stale or spliced")

    selection = selection_proof._selection
    venue_wire = _decode_canonical_json(checkpoint.venue.canonical_bytes)
    if type(venue_wire) is not list:
        raise ValueError("venue checkpoint component is not an exact row")
    venue_fields = _operations._require_m2_aggregate(
        venue_wire,
        _M2_VENUE_STATE_TAG,
        22,
    )
    venue_scope_wire = _operations._require_m2_aggregate(
        venue_fields[0],
        "m2.venue.Scope/v1",
        4,
    )
    venue_scope = _venue.VenueScope(
        _operations._decode_m2_m1_as(
            "venue application generation",
            venue_scope_wire[0],
            _identity.ApplicationGenerationId,
        ),
        _operations._decode_m2_m1_as(
            "venue broker", venue_scope_wire[1], _identity.BrokerId
        ),
        _operations._decode_m2_m1_as(
            "venue environment", venue_scope_wire[2], _identity.EnvironmentId
        ),
        _operations._decode_m2_m1_as(
            "venue account", venue_scope_wire[3], _identity.AccountId
        ),
    )
    if venue_scope.generation != checkpoint.application_generation_id:
        raise ValueError("venue checkpoint leaves the selected application")
    controllers = {row.scope_id: row for row in selection.controllers}
    protection_authorities = {
        row.scope_id: row for row in selection.protection_authorities
    }
    selected_scopes = {row.scope_id: row for row in selection.scopes}
    if (
        tuple(selected_scopes) != tuple(scope.scope_id for scope in checkpoint.scopes)
        or set(controllers) != set(selected_scopes)
        or set(protection_authorities) != set(selected_scopes)
    ):
        raise ValueError("compact hydration scope proof is incomplete")

    scope_owners: list[_RuntimeCheckpointScopeOwners] = []
    compact_execution_by_scope: dict[
        _fills.PositionScope, _position.ExecutionSnapshot
    ] = {}
    source_execution_state_by_scope: dict[
        _fills.PositionScope, _position._M2ExecutionState
    ] = {}
    position_scope_by_id: dict[int, _fills.PositionScope] = {}
    source_acquisition_by_id: dict[
        int, _acquisition.AcquisitionControllerState | None
    ] = {}
    compact_protection_by_id: dict[int, _protection.PositionProtectionState | None] = {}
    for candidate in checkpoint.scopes:
        selected = selected_scopes[candidate.scope_id]
        controller = controllers[candidate.scope_id]
        protection_authority = protection_authorities[candidate.scope_id]
        position_scope_wire = _decode_canonical_json(
            candidate.position_scope.canonical_bytes
        )
        position_scope = _operations._decode_m2_position_scope(position_scope_wire)
        if (
            position_scope
            != _fills.PositionScope(
                venue_scope.broker,
                venue_scope.environment,
                venue_scope.account,
                selected.symbol,
            )
            or controller.application_generation_id
            != checkpoint.application_generation_id
            or controller.execution_profile_id != checkpoint.execution_profile_id
            or controller.aggregate_quantity
            != _operations._require_exact_int(
                "execution checkpoint quantity",
                _operations._require_m2_aggregate(
                    _decode_canonical_json(candidate.execution.canonical_bytes),
                    _M2_EXECUTION_STATE_TAG,
                    20,
                )[1],
            )
        ):
            raise ValueError("compact hydration scope coordinates are spliced")

        execution_wire = _decode_canonical_json(candidate.execution.canonical_bytes)
        execution_state = _decode_m2_execution_checkpoint_state(execution_wire)
        scope_roots = tuple(
            row for row in selection.roots if row.scope_id == candidate.scope_id
        )
        scope_fact_heads = tuple(
            row
            for row in selection.fact_heads
            if row.root_fill_key_id in {root.root_fill_key_id for root in scope_roots}
        )
        scope_facts = tuple(
            row for row in selection.current_facts if row.scope_id == candidate.scope_id
        )
        execution = _restore_compact_execution_from_selected_rows(
            execution_state,
            scope_id=candidate.scope_id,
            roots=scope_roots,
            fact_heads=scope_fact_heads,
            current_facts=scope_facts,
        )
        if (
            position_scope in compact_execution_by_scope
            or position_scope in source_execution_state_by_scope
        ):
            raise ValueError("compact hydration position scope is duplicated")
        compact_execution_by_scope[position_scope] = execution
        source_execution_state_by_scope[position_scope] = execution_state
        position_scope_by_id[candidate.scope_id] = position_scope

        acquisition_wire = _decode_canonical_json(candidate.acquisition.canonical_bytes)
        if type(acquisition_wire) is not list or not acquisition_wire:
            raise ValueError("acquisition checkpoint component is not an exact row")
        if controller.live_acquisition_generation_id is None:
            if acquisition_wire[0] != _M2_DORMANT_ACQUISITION_TAG:
                raise ValueError("dormant acquisition checkpoint shape is spliced")
            expected_acquisition_wire, _ = _encode_dormant_acquisition(
                selection,
                controller,
                position_scope,
                selection_proof._binding,
            )
            if expected_acquisition_wire != acquisition_wire:
                raise ValueError("dormant acquisition checkpoint is spliced")
            source_acquisition_by_id[candidate.scope_id] = None
        else:
            if acquisition_wire[0] != _M2_ACQUISITION_STATE_TAG:
                raise ValueError("active acquisition checkpoint shape is spliced")
            source_acquisition_by_id[candidate.scope_id] = (
                _decode_source_acquisition_checkpoint(
                    acquisition_wire,
                    selection_proof=selection_proof,
                    scope_id=candidate.scope_id,
                )
            )

        protection_wire = _decode_canonical_json(candidate.protection.canonical_bytes)
        if type(protection_wire) is not list or not protection_wire:
            raise ValueError("protection checkpoint component is not an exact row")
        active_protection_coordinates = (
            protection_authority.active_stream_generation_id,
            protection_authority.active_acquisition_generation_id,
            protection_authority.active_generation_mandate_commitment_sha256,
            protection_authority.active_source_profile_id,
            protection_authority.active_session_id,
            protection_authority.active_sequence_mode,
        )
        if all(value is None for value in active_protection_coordinates):
            if protection_wire[0] != _M2_DORMANT_PROTECTION_TAG:
                raise ValueError("dormant protection checkpoint shape is spliced")
            expected_protection_wire, _ = _encode_dormant_protection(
                protection_authority,
                selection_proof._binding,
            )
            if expected_protection_wire != protection_wire:
                raise ValueError("dormant protection checkpoint is spliced")
            compact_protection_by_id[candidate.scope_id] = None
        else:
            if any(value is None for value in active_protection_coordinates):
                raise ValueError("active protection authority coordinates are partial")
            if protection_wire[0] != _M2_PROTECTION_CHECKPOINT_TAG:
                raise ValueError("active protection checkpoint shape is spliced")
            compact_protection_by_id[candidate.scope_id] = (
                _decode_source_protection_checkpoint(
                    protection_wire,
                    selection_proof=selection_proof,
                    scope_id=candidate.scope_id,
                    position_scope=position_scope,
                    compact_execution=execution,
                )
            )

    restored_venue = _decode_compact_venue_checkpoint(
        venue_wire,
        selection=selection,
        application_generation_id=checkpoint.application_generation_id,
        compact_execution_by_scope=compact_execution_by_scope,
        source_execution_state_by_scope=source_execution_state_by_scope,
    )
    for candidate in checkpoint.scopes:
        position_scope = position_scope_by_id[candidate.scope_id]
        execution = compact_execution_by_scope[position_scope]
        protection = compact_protection_by_id[candidate.scope_id]
        source_acquisition = source_acquisition_by_id[candidate.scope_id]
        acquisition: _acquisition.AcquisitionControllerState | None
        if source_acquisition is None:
            acquisition = None
        else:
            venue_context = restored_venue.project_acquisition_context(
                execution,
                position_scope,
            )
            if not venue_context.matches_current(
                restored_venue,
                execution,
                checkpoint.application_generation_id,
                position_scope,
            ):
                raise ValueError("compact acquisition venue context is not current")
            acquisition = _acquisition._m2_rebind_compact_acquisition_controller(
                source_acquisition,
                scope_execution_commitment=(venue_context.scope_execution_commitment),
                venue_commitment=venue_context.commitment,
                protection_commitment=(
                    None if protection is None else protection.commitment
                ),
            )
        scope_owners.append(
            _RuntimeCheckpointScopeOwners(
                candidate.scope_id,
                acquisition,
                execution,
                protection,
            )
        )
    authority_wire = _decode_canonical_json(checkpoint.authority.canonical_bytes)
    if type(authority_wire) is not list:
        raise ValueError("authority checkpoint component is not an exact row")
    selected_position_scopes = tuple(
        _fills.PositionScope(
            venue_scope.broker,
            venue_scope.environment,
            venue_scope.account,
            selected.symbol,
        )
        for selected in selection.scopes
    )
    restored_authority = _decode_compact_authority_checkpoint(
        authority_wire,
        venue=restored_venue,
        venue_commitment=_checkpoint_row_commitment(
            b"execution-core/m2-venue/state/v1", venue_wire[:-1]
        ),
        application_generation_id=checkpoint.application_generation_id,
        selected_position_scopes=selected_position_scopes,
        selected_effect_ids=tuple(
            effect.effect_external for effect in selection.effects
        ),
    )

    return _CompactRuntimeCheckpointOwners(
        checkpoint,
        selection_proof,
        restored_venue,
        restored_authority,
        tuple(scope_owners),
    )


__all__ = (
    "InertRuntimeCheckpointComponent",
    "RuntimeCheckpointEnvelope",
    "RuntimeCheckpointScopeCandidate",
    "encode_runtime_checkpoint",
)
