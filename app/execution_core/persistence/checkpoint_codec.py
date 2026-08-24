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
    if book._economic_high_water_by_leg.size != reached:
        raise ValueError(
            "economic high water map retains a leg outside the selected owner set"
        )
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
    rows: list[object] = []
    reached = 0
    for ordinal, leg_key in enumerate(
        _selected_leg_keys_from_selection(book, selection)
    ):
        leg_index = _venue._leg_index_key(leg_key)
        owner = book._owner_by_leg.get(leg_index)
        if owner is None:
            raise ValueError("selected owner leg has no current owner row")
        if owner.leg_key != leg_key:
            raise ValueError("reached owner does not own its selected leg")
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
                    atom(owner.effect_scope.effect_id),
                    atom(owner.observation_id),
                    attempt_row,
                ]
            )
        )
    if book._owner_by_leg.size != reached:
        raise ValueError("owner map retains a leg outside the selected owner set")
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


def _encode_runtime_checkpoint_venue_correlation_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the acquisition correlation of each proof-selected root."""

    atom = _operations._encode_m2_m1_atom
    rows: list[object] = []
    reached = 0
    for root_key in _selected_root_keys_from_selection(book, selection):
        entry = book._acquisition_correlation_by_root.get(
            _venue._coverage_root_index_key(root_key)
        )
        if entry is None:
            continue
        if entry.root_key != root_key:
            raise ValueError("reached correlation does not own its selected root")
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
    if book._acquisition_correlation_by_root.size != reached:
        raise ValueError(
            "acquisition correlation map retains a selected root outside the selection"
        )
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
    rows: list[object] = []
    reached = 0
    for root_key in _selected_root_keys_from_selection(book, selection):
        index = book._broker_coverage_by_root.get(
            _venue._coverage_root_index_key(root_key)
        )
        if index is None:
            continue
        coverage = book._broker_coverage_ledger.get(index)
        if coverage is None:
            raise ValueError("broker coverage index does not resolve in its ledger")
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
    if book._broker_coverage_by_root.size != reached:
        raise ValueError(
            "broker coverage map retains a selected root outside the selection"
        )
    return _checkpoint_collection("m2.venue.BrokerCoverages/v1", rows)


def _encode_runtime_checkpoint_venue_human_coverage_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the human coverage of each proof-selected root through its ledger."""

    atom = _operations._encode_m2_m1_atom
    rows: list[object] = []
    reached = 0
    for root_key in _selected_root_keys_from_selection(book, selection):
        index = book._human_coverage_by_root.get(
            _venue._coverage_root_index_key(root_key)
        )
        if index is None:
            continue
        coverage = book._human_coverage_ledger.get(index)
        if coverage is None:
            raise ValueError("human coverage index does not resolve in its ledger")
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
    if book._human_coverage_by_root.size != reached:
        raise ValueError(
            "human coverage map retains a selected root outside the selection"
        )
    return _checkpoint_collection("m2.venue.HumanCoverages/v1", rows)


def _encode_runtime_checkpoint_venue_closure_head_rows(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> list[object]:
    """Project the terminal closure head of each proof-selected owner leg."""

    atom = _operations._encode_m2_m1_atom
    rows: list[object] = []
    reached = 0
    for leg_key in _selected_leg_keys_from_selection(book, selection):
        closure = book._closure_head_by_leg.get(_venue._leg_index_key(leg_key))
        if closure is None:
            continue
        if closure.leg_key != leg_key:
            raise ValueError("reached closure does not own its selected leg")
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
    if book._closure_head_by_leg.size != reached:
        raise ValueError(
            "closure head map retains a leg outside the selected owner set"
        )
    return _checkpoint_collection("m2.venue.ClosureHeads/v1", rows)


def _referenced_reconciliation_inputs(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> tuple[_identity.VenueInputId, ...]:
    """Collect the input IDs named directly by the selected current venue rows.

    R15 section 2 admits a reconciliation row only when its input ID is directly
    referenced by one of the selected current closure or coverage rows, so the
    reference order is the proof order of those referencing rows: closure heads
    over the selected owner legs, then human and broker coverage over the
    selected roots.  An input named more than once keeps its first reference, so
    no whole-map order and no input order is ever consulted.
    """

    ordered: dict[str, _identity.VenueInputId] = {}

    def _reference(input_id: _identity.VenueInputId) -> None:
        if type(input_id) is not _identity.VenueInputId:
            raise TypeError("referenced input must be the exact VenueInputId type")
        ordered.setdefault(input_id.value, input_id)

    for leg_key in _selected_leg_keys_from_selection(book, selection):
        closure = book._closure_head_by_leg.get(_venue._leg_index_key(leg_key))
        if closure is not None:
            _reference(closure.source_input_id)
    for root_key in _selected_root_keys_from_selection(book, selection):
        root_index_key = _venue._coverage_root_index_key(root_key)
        human_index = book._human_coverage_by_root.get(root_index_key)
        if human_index is not None:
            human = book._human_coverage_ledger.get(human_index)
            if human is None:
                raise ValueError("human coverage index does not resolve in its ledger")
            _reference(human.source_input_id)
            if human.broker_source_input_id is not None:
                _reference(human.broker_source_input_id)
        broker_index = book._broker_coverage_by_root.get(root_index_key)
        if broker_index is not None:
            broker = book._broker_coverage_ledger.get(broker_index)
            if broker is None:
                raise ValueError("broker coverage index does not resolve in its ledger")
            _reference(broker.root_source_input_id)
            _reference(broker.head_source_input_id)
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

    The map is an exact current index rather than a permitted superset: an input
    it retains that no selected current row names is a splice, so the reached
    count must equal the whole map size.
    """

    selected_legs = frozenset(_selected_leg_keys_from_selection(book, selection))
    rows: list[object] = []
    reached = 0
    for input_id in _referenced_reconciliation_inputs(book, selection):
        record = book._reconciliation_by_input.get(_venue._input_index_key(input_id))
        if record is None:
            continue
        if record.input_id != input_id:
            raise ValueError("reached reconciliation does not own its referenced input")
        if record.leg_key not in selected_legs:
            raise ValueError("reached reconciliation leaves the selected owner set")
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                _encode_runtime_checkpoint_venue_reconciliation_row(record)
            )
        )
    if book._reconciliation_by_input.size != reached:
        raise ValueError("reconciliation index retains an unreferenced input")
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


def _referenced_execution_reconciliation_inputs(
    book: _venue.VenueRecoveryBook,
    selection: _records._RuntimeCheckpointSelectionSet,
) -> tuple[_identity.VenueInputId, ...]:
    """Collect the catch-up input IDs named by the selected bootstrap targets.

    A registry outcome is minted from one ``CatchUpExecutionRegistry`` item, and a
    bootstrap target is the only selected current row that retains such an input
    identity: its origin ``bootstrap_input_id`` and its serving
    ``checkpoint_input_id``.  The reference order is therefore the proof order of
    the selected position scopes, with the first reference of a repeated input
    keeping its place.
    """

    ordered: dict[str, _identity.VenueInputId] = {}

    def _reference(input_id: _identity.VenueInputId) -> None:
        if type(input_id) is not _identity.VenueInputId:
            raise TypeError("referenced input must be the exact VenueInputId type")
        ordered.setdefault(input_id.value, input_id)

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
        _reference(anchor_record.bootstrap_input_id)
        _reference(anchor_record.checkpoint_input_id)
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

    Like the fill reconciliation index this is an exact current index rather than
    a permitted superset, so a retained input that no selected current row names
    is a splice and the reached count must equal the whole map size.
    """

    selected_scopes = frozenset(
        _selected_position_scopes_from_selection(book, selection)
    )
    rows: list[object] = []
    reached = 0
    for input_id in _referenced_execution_reconciliation_inputs(book, selection):
        record = book._execution_reconciliation_by_input.get(
            _venue._input_index_key(input_id)
        )
        if record is None:
            continue
        if record.input_id != input_id:
            raise ValueError(
                "reached execution reconciliation does not own its referenced input"
            )
        if record.position_scope not in selected_scopes:
            raise ValueError(
                "reached execution reconciliation leaves the selected scope set"
            )
        reached += 1
        rows.append(
            _require_bounded_checkpoint_row(
                _encode_runtime_checkpoint_venue_execution_reconciliation_row(record)
            )
        )
    if book._execution_reconciliation_by_input.size != reached:
        raise ValueError("execution reconciliation index retains an unreferenced input")
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
    proof: _venue.AcceptanceProof,
) -> list[object]:
    """Encode the frozen 6-member acceptance proof."""

    atom = _operations._encode_m2_m1_atom
    return [
        "m2.venue.AcceptanceProof/v1",
        _checkpoint_enum("m1.venue.AcceptanceProofKind", proof.kind),
        atom(proof.effect_scope.effect_id),
        (
            None
            if proof.claim_occurrence_id is None
            else atom(proof.claim_occurrence_id)
        ),
        atom(proof.evidence_reference),
        _operations._encode_m2_bytes(proof.evidence_digest),
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
    seen: set[bytes] = set()
    rows: list[object] = []
    for ordinal, record in enumerate(selection.effects):
        effect_external = record.effect_external
        current = book._effect_by_id.get(_venue._effect_index_key(effect_external))
        if current is None:
            raise ValueError("selected effect has no current owner row")
        scope = current.effect.scope
        if scope.effect_id != effect_external:
            raise ValueError("reached effect does not own its selected identity")
        if (
            scope.request_occurrence_id != record.request_occurrence_id
            or scope.mandate_id != record.mandate_id
            or scope.kind.value != record.effect_kind
            or scope.client_order_id != record.client_order_id
            or scope.side.value != record.side
            or scope.quantity != record.quantity
            or scope.economic_scope != record.economic_scope
        ):
            raise ValueError("reached effect disagrees with its selected record")
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
                            effect.acceptance_proof
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

    external_by_surrogate = {
        record.effect_id: record.effect_external for record in selection.effects
    }
    seen: set[bytes] = set()
    rows: list[object] = []
    for record in selection.claims:
        effect_external = external_by_surrogate.get(record.effect_id)
        if effect_external is None:
            raise ValueError("selected dispatch claim names an unselected effect")
        claim = book._claim_by_effect.get(_venue._effect_index_key(effect_external))
        if claim is None:
            raise ValueError("selected dispatch claim has no current owner row")
        if claim.effect_scope.effect_id != effect_external:
            raise ValueError("reached dispatch claim does not own its selected effect")
        if claim.claim_occurrence_id != record.claim_occurrence_id:
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
) -> tuple[list[object], _identity.EffectId | None]:
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
        ], descriptor.predecessor_effect_id
    if type(active) is _authority._AcquisitionInactiveSlot:
        raise ValueError("acquisition slot mixes an active and inactive variant")
    if descriptor_reference is None:
        raise ValueError("acquisition slot names no descriptor reference")
    effect_id, descriptor_commitment = descriptor_reference
    return [
        "m2.authority.AcquisitionSlotActive/v1",
        atom(effect_id),
        _operations._encode_m2_bytes(descriptor_commitment),
    ], effect_id


def _encode_runtime_checkpoint_acquisition_slot_rows(
    state: _authority.ExecutionAuthorityState,
    application_generation_id: _identity.ApplicationGenerationId,
    selected_position_scopes: tuple[_fills.PositionScope, ...],
) -> tuple[list[object], tuple[_identity.EffectId, ...]]:
    """Project one slot row per selected scope and report the effects it names.

    All three scope maps are exact current selected-scope maps under the R16 section 2
    taxonomy, so each is compared against *its own* reached count: comparing all three
    against the slot count would let an unselected-scope entry hide behind a selected
    scope that happens to carry no descriptor.  R20 section 2 orders these rows by the
    canonical ``PositionScope`` bytes rather than by any map or input order.
    """

    reached: dict[bytes, list[object]] = {}
    referenced: list[_identity.EffectId] = []
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
        if currentness.position_scope != position_scope:
            raise ValueError("reached currentness does not own its selected scope")
        reached_descriptors += descriptor is not None
        reached_actives += active is not None
        slot_value, effect_id = _encode_runtime_checkpoint_acquisition_slot_value(
            descriptor, active
        )
        if effect_id is not None:
            referenced.append(effect_id)
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


def _encode_runtime_checkpoint_acquisition_descriptor_rows(
    state: _authority.ExecutionAuthorityState,
    slot_effect_ids: tuple[_identity.EffectId, ...],
    selected_effect_ids: tuple[_identity.EffectId, ...],
) -> list[object]:
    """Project every descriptor named by a retained slot or a selected effect.

    ``_acquisition_descriptor_by_effect`` is a permitted authenticated superset in the
    R16 section 2 taxonomy: it keeps predecessor descriptors that no current row
    reaches, so it deliberately gets no whole-map cardinality check.  A slot
    reference that does not resolve is still a refusal, because a slot names only a
    retained descriptor.  R20 section 2 orders the rows by canonical effect ID.
    """

    reached: dict[bytes, list[object]] = {}
    for effect_id, required in (
        *((effect_id, True) for effect_id in slot_effect_ids),
        *((effect_id, False) for effect_id in selected_effect_ids),
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
        state, slot_effect_ids, selected_effect_ids
    )
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
