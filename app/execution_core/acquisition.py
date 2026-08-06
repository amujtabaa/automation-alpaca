"""Pure E1 acquisition-generation identity and inert lineage read contracts.

E1 owns deterministic identity encoding plus the narrow, opaque shapes which a
later E2 composite reducer will populate.  It deliberately does not contain a
successful registration, lineage-binding, or fact-update transition: each of
those requires E2-owned admission/currentness and canonical-fact proof.

The empty containers are useful, authority-free values.  Until E2 supplies the
authenticated composite transition that owns those proofs, every lookup is
reconciliation-only and returns ``None`` rather than inferring a generation.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass, field as _field
from enum import Enum as _Enum
from hashlib import sha256 as _sha256

from .fills import (
    PositionScope as _PositionScope,
    _commit_parts,
    _encode_int,
    _encode_position_scope,
    _encode_text,
    _pack_parts,
)
from .identity import (
    AcquisitionGenerationId as _AcquisitionGenerationId,
    ApplicationGenerationId as _ApplicationGenerationId,
    EffectId as _EffectId,
    ExecutionFactKey as _ExecutionFactKey,
    RequestOccurrenceId as _RequestOccurrenceId,
    RootFillKey as _RootFillKey,
    VenueLegKey as _VenueLegKey,
    _acquisition_generation_id_is_canonical,
)


__all__ = [
    "GenerationServingClass",
    "GenerationRouteKind",
    "GenerationBindingView",
    "GenerationRecordView",
    "GenerationRouteView",
    "GenerationRegistry",
    "AcquisitionLineageIndex",
]


_IDENTITY_DOMAIN = b"execution-core/acquisition-generation-id/v1"
_GENESIS_DOMAIN = b"execution-core/acquisition-controller-genesis-head/v1"
_REGISTRY_EMPTY_DOMAIN = b"execution-core/acquisition-generation-registry/empty/v1"
_LINEAGE_EMPTY_DOMAIN = b"execution-core/acquisition-lineage-index/empty/v1"
_MAX_SUCCESSOR_ORDINAL = 2**64 - 1


def _require_exact(name: str, value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must be {expected.__name__}")


def _require_commitment(name: str, value: object) -> bytes:
    if type(value) is not bytes:
        raise TypeError(f"{name} must be bytes")
    if len(value) != 32:
        raise ValueError(f"{name} must contain exactly 32 bytes")
    return value


def _require_ordinal(value: object) -> int:
    if type(value) is not int:
        raise TypeError("successor ordinal must be an exact integer")
    if value < 0 or value > _MAX_SUCCESSOR_ORDINAL:
        raise ValueError("successor ordinal is outside the canonical range")
    return value


def _acquisition_controller_genesis_head(
    application_generation_id: _ApplicationGenerationId,
    position_scope: _PositionScope,
) -> bytes:
    """Return the canonical opaque first-controller identity coordinate."""

    _require_exact(
        "application_generation_id",
        application_generation_id,
        _ApplicationGenerationId,
    )
    _require_exact("position_scope", position_scope, _PositionScope)
    return _commit_parts(
        _GENESIS_DOMAIN,
        _encode_text(application_generation_id.value),
        _encode_position_scope(position_scope),
    )


def _derive_acquisition_generation_id(
    application_generation_id: _ApplicationGenerationId,
    position_scope: _PositionScope,
    successor_ordinal: int,
    dual_mandate_binding_commitment: bytes,
    predecessor_or_genesis_head_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
) -> _AcquisitionGenerationId:
    """Encode the exact E1 identity wire value from opaque E2 coordinates.

    This deterministic data derivation is not admission and does not create a
    generation, route, controller, or capability.  E2 alone decides whether
    the supplied coordinates are authentic and may become state.
    """

    _require_exact(
        "application_generation_id",
        application_generation_id,
        _ApplicationGenerationId,
    )
    _require_exact("position_scope", position_scope, _PositionScope)
    ordinal = _require_ordinal(successor_ordinal)
    dual = _require_commitment(
        "dual_mandate_binding_commitment",
        dual_mandate_binding_commitment,
    )
    predecessor = _require_commitment(
        "predecessor_or_genesis_head_commitment",
        predecessor_or_genesis_head_commitment,
    )
    compatibility = _require_commitment(
        "emergency_recovery_compatibility_commitment",
        emergency_recovery_compatibility_commitment,
    )
    return _AcquisitionGenerationId(
        _sha256(
            _pack_parts(
                _IDENTITY_DOMAIN,
                _encode_text(application_generation_id.value),
                _encode_position_scope(position_scope),
                _encode_int(ordinal),
                dual,
                predecessor,
                compatibility,
            )
        ).hexdigest()
    )


class GenerationServingClass(_Enum):
    """Read-only E2-provided serving classification."""

    LIVE = "LIVE"
    RETIRED_UNSERVING = "RETIRED_UNSERVING"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class GenerationRouteKind(_Enum):
    """The one immutable source family represented by a direct route."""

    REQUEST = "REQUEST"
    EFFECT = "EFFECT"
    OWNER = "OWNER"
    ROOT = "ROOT"
    FACT = "FACT"


@_dataclass(frozen=True, slots=True, init=False)
class GenerationBindingView:
    """Immutable, schema-neutral generation provenance projection.

    E2 will create authentic instances only as part of a completed composite
    transition.  E1 exposes the shape now so no raw/caller-built binding can be
    treated as a generation.
    """

    generation_id: _AcquisitionGenerationId = _field(init=False)
    application_generation_id: _ApplicationGenerationId = _field(init=False)
    position_scope: _PositionScope = _field(init=False)
    successor_ordinal: int = _field(init=False)
    dual_mandate_binding_commitment: bytes = _field(init=False)
    predecessor_or_genesis_head_commitment: bytes = _field(init=False)
    emergency_recovery_compatibility_commitment: bytes = _field(init=False)
    binding_commitment: bytes = _field(init=False)
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("GenerationBindingView is reducer-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("GenerationBindingView cannot be subclassed")


@_dataclass(frozen=True, slots=True, init=False)
class GenerationRecordView:
    """Read-only current economics/classification for one direct generation."""

    binding: GenerationBindingView = _field(init=False)
    economics_head_commitment: bytes = _field(init=False)
    serving_class: GenerationServingClass = _field(init=False)
    closure_summary_commitment: bytes = _field(init=False)
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("GenerationRecordView is reducer-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("GenerationRecordView cannot be subclassed")


@_dataclass(frozen=True, slots=True, init=False)
class GenerationRouteView:
    """Immutable source-to-generation route; mutable state never appears here."""

    route_kind: GenerationRouteKind = _field(init=False)
    source_commitment: bytes = _field(init=False)
    generation_id: _AcquisitionGenerationId = _field(init=False)
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("GenerationRouteView is reducer-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("GenerationRouteView cannot be subclassed")


@_dataclass(frozen=True, slots=True, init=False)
class GenerationRegistry:
    """Opaque, non-enumerable registry read boundary.

    It is deliberately empty in E1.  A populated registry requires an E2
    composite transition which has authenticated admission/currentness before
    it reaches this storage shape.
    """

    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("GenerationRegistry is opaque; use empty()")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("GenerationRegistry cannot be subclassed")

    @classmethod
    def empty(cls) -> GenerationRegistry:
        if cls is not GenerationRegistry:
            raise TypeError("GenerationRegistry.empty requires the exact type")
        result = object.__new__(cls)
        object.__setattr__(result, "_seal", _commit_parts(_REGISTRY_EMPTY_DOMAIN))
        return result

    def record(
        self,
        generation_id: _AcquisitionGenerationId,
    ) -> GenerationRecordView | None:
        if not _registry_is_authentic(self):
            raise ValueError("generation registry authenticity check failed")
        if not _acquisition_generation_id_is_canonical(generation_id):
            raise TypeError("generation_id must be a canonical acquisition identity")
        return None


def _registry_is_authentic(value: object) -> bool:
    if type(value) is not GenerationRegistry:
        return False
    try:
        seal = value._seal
    except AttributeError:
        return False
    return type(seal) is bytes and seal == _commit_parts(_REGISTRY_EMPTY_DOMAIN)


@_dataclass(frozen=True, slots=True, init=False)
class AcquisitionLineageIndex:
    """Opaque, non-enumerable direct lineage read boundary.

    E1 deliberately has no successful binder.  An unbound value is never
    inferred to belong to a current generation; all five lookup families return
    ``None`` until a later authenticated E2 transition supplies direct routes.
    """

    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionLineageIndex is opaque; use empty()")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionLineageIndex cannot be subclassed")

    @classmethod
    def empty(cls) -> AcquisitionLineageIndex:
        if cls is not AcquisitionLineageIndex:
            raise TypeError("AcquisitionLineageIndex.empty requires the exact type")
        result = object.__new__(cls)
        object.__setattr__(result, "_seal", _commit_parts(_LINEAGE_EMPTY_DOMAIN))
        return result

    def route_request(
        self,
        request_occurrence_id: _RequestOccurrenceId,
    ) -> GenerationRouteView | None:
        _require_exact(
            "request_occurrence_id", request_occurrence_id, _RequestOccurrenceId
        )
        _empty_route_result(self)
        return None

    def route_effect(self, effect_id: _EffectId) -> GenerationRouteView | None:
        _require_exact("effect_id", effect_id, _EffectId)
        _empty_route_result(self)
        return None

    def route_owner(self, leg_key: _VenueLegKey) -> GenerationRouteView | None:
        _require_exact("leg_key", leg_key, _VenueLegKey)
        _empty_route_result(self)
        return None

    def route_root(self, root_key: _RootFillKey) -> GenerationRouteView | None:
        _require_exact("root_key", root_key, _RootFillKey)
        _empty_route_result(self)
        return None

    def route_fact(self, fact_key: _ExecutionFactKey) -> GenerationRouteView | None:
        _require_exact("fact_key", fact_key, _ExecutionFactKey)
        _empty_route_result(self)
        return None


def _empty_route_result(index: AcquisitionLineageIndex) -> None:
    if not _lineage_is_authentic(index):
        raise ValueError("acquisition lineage index authenticity check failed")
    return None


def _lineage_is_authentic(value: object) -> bool:
    if type(value) is not AcquisitionLineageIndex:
        return False
    try:
        seal = value._seal
    except AttributeError:
        return False
    return type(seal) is bytes and seal == _commit_parts(_LINEAGE_EMPTY_DOMAIN)
