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
from typing import cast as _cast
from weakref import ReferenceType as _ReferenceType
from weakref import ref as _weakref_ref

from .. import durable_codec as _durable_codec
from .. import identity as _identity
from .. import position as _position
from .. import protection as _protection
from .. import values as _values
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
_M2_POSITION_SCOPE_TAG = "m1.fills.PositionScope/v1"
_MAX_RUNTIME_CHECKPOINT_SCOPES = 4_096
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
        _atom_binding(_durable_codec.encode_m1_value(value)),
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
    if _encode_canonical_json(decoded) != value:  # type: ignore[arg-type]
        raise ValueError("checkpoint JSON bytes are not canonical")
    return decoded


_COMPONENT_MEMBER_COUNTS = {
    _M2_VENUE_STATE_TAG: 23,
    _M2_AUTHORITY_CHECKPOINT_TAG: 14,
    _M2_ACQUISITION_STATE_TAG: 17,
    _M2_EXECUTION_STATE_TAG: 21,
    _M2_PROTECTION_CHECKPOINT_TAG: 32,
    _M2_POSITION_SCOPE_TAG: 5,
}


def _decode_component(
    value: object, expected_tag: str
) -> InertRuntimeCheckpointComponent:
    expected_count = _COMPONENT_MEMBER_COUNTS[expected_tag]
    if (
        type(value) is not list
        or len(value) != expected_count
        or value[0] != expected_tag
    ):
        raise ValueError(f"{expected_tag} has the wrong exact shape")
    canonical = _encode_canonical_json(value)
    if len(canonical) > _MAX_RUNTIME_CHECKPOINT_COMPONENT_BYTES:
        raise OverflowError("checkpoint component exceeds its byte limit")
    return _issue_component(expected_tag, canonical)


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
        acquisition = _decode_component(row[3], _M2_ACQUISITION_STATE_TAG)
        execution = _decode_component(row[4], _M2_EXECUTION_STATE_TAG)
        protection = _decode_component(row[5], _M2_PROTECTION_CHECKPOINT_TAG)
        if row[2] != row[3][2] or row[2] != row[4][1]:
            raise ValueError("runtime checkpoint scope components do not agree")
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
            _decode_component(acquisition_wire, _M2_ACQUISITION_STATE_TAG),
            _decode_component(execution_wire, _M2_EXECUTION_STATE_TAG),
            _decode_component(protection_wire, _M2_PROTECTION_CHECKPOINT_TAG),
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


def _project_runtime_checkpoint(
    selection_proof: object,
    venue: object,
    authority: object,
    scope_owners: tuple[object, ...],
) -> RuntimeCheckpointEnvelope:
    """Contract-defined owner projector; unavailable until its records API lands."""

    proof_type = getattr(_records, "RuntimeCheckpointSelectionProof", None)
    if proof_type is None:
        raise RuntimeError("RuntimeCheckpointSelectionProof is not installed")
    if type(selection_proof) is not proof_type:
        raise TypeError("selection_proof must be exact RuntimeCheckpointSelectionProof")
    del venue, authority, scope_owners
    raise RuntimeError("runtime checkpoint owner projection is not installed")


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
