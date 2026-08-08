"""Pure acquisition-generation contracts and the E2 controller composition.

E1 owns deterministic identity encoding and bounded, opaque lineage readers.
E2 composes those values only through sealed venue, authority, and protection
handoffs.  It remains pure, deterministic, and deliberately keeps mutation
authority in the owning modules rather than exposing a new action surface.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass, field as _field
from enum import Enum as _Enum
from fractions import Fraction as _Fraction
from hashlib import sha256 as _sha256

from .authority import (
    AcquisitionAdmissionKind as _AcquisitionAdmissionKind,
    AcquisitionAdmissionProjection as _AcquisitionAdmissionProjection,
    AcquisitionAuthorityOperation as _AcquisitionAuthorityOperation,
    AcquisitionAuthorityReceipt as _AcquisitionAuthorityReceipt,
    AcquisitionClaimReceipt as _AcquisitionClaimReceipt,
    ClaimAcquisitionEffect as _ClaimAcquisitionEffect,
    RegisterAcquisitionCurrentness as _RegisterAcquisitionCurrentness,
    AcquisitionContextRefresh as _AcquisitionContextRefresh,
    AcquisitionContextRefreshDisposition as _AcquisitionContextRefreshDisposition,
    AcquisitionEffectTerms,
    AcquisitionOrderType,
    BeginAcquisitionPreemption as _BeginAcquisitionPreemption,
    CreateAcquisitionEffect as _CreateAcquisitionEffect,
    CreateAcquisitionProtectionExit as _CreateAcquisitionProtectionExit,
    AuthorityInputId as _AuthorityInputId,
    AuthorityDisposition as _AuthorityDisposition,
    ExecutionAuthorityState as _ExecutionAuthorityState,
    SessionId as _SessionId,
    _apply_acquisition_bootstrap_initialization,
    _apply_acquisition_fact_preemption,
    _apply_acquisition_successor_registration,
    _mint_acquisition_claim_permit,
    _mint_acquisition_currentness_registration,
    _mint_acquisition_effect_permit,
    _mint_acquisition_exit_permit,
    _mint_acquisition_fact_preemption,
    apply_execution_authority_input as _apply_execution_authority_input,
    refresh_acquisition_context as _refresh_acquisition_context,
)
from .fills import (
    PositionScope as _PositionScope,
    _PersistentKeyMap,
    _commit_parts,
    _encode_int,
    _encode_position_scope,
    _encode_text,
    _pack_parts,
)
from .identity import (
    AcquisitionGenerationId as _AcquisitionGenerationId,
    AcquisitionMandateId as _AcquisitionMandateId,
    ApplicationGenerationId as _ApplicationGenerationId,
    ClaimOccurrenceId as _ClaimOccurrenceId,
    EffectId as _EffectId,
    ExecutionFactKey as _ExecutionFactKey,
    MandateId as _MandateId,
    MarketStreamGenerationId as _MarketStreamGenerationId,
    RequestOccurrenceId as _RequestOccurrenceId,
    RootFillKey as _RootFillKey,
    VenueLegKey as _VenueLegKey,
    _acquisition_generation_id_is_canonical,
    _market_identity_is_canonical,
)
from .position import ExecutionSnapshot as _ExecutionSnapshot
from .protection import (
    AcquisitionProtectionContext as _AcquisitionProtectionContext,
    AcquisitionProtectionRebaseKind as _AcquisitionProtectionRebaseKind,
    AcquisitionProtectionRebaseProjection as _AcquisitionProtectionRebaseProjection,
    PositionProtectionState as _PositionProtectionState,
    ProtectionDisposition as _ProtectionDisposition,
    ProtectionMandate as _ProtectionMandate,
    ProtectionPolicy as _ProtectionPolicy,
    ProtectionTransition as _ProtectionTransition,
    force_acquisition_mixed_recovery as _force_acquisition_mixed_recovery,
    initialize_position_protection as _initialize_position_protection,
    _mint_acquisition_mixed_recovery_proof,
    _project_acquisition_neutral_reprojection,
    _project_acquisition_preemption_intent,
    _project_acquisition_protection_exit_intent,
    _reduce_acquisition_mixed_recovery,
    project_acquisition_protection_context as _project_acquisition_protection_context,
    project_protection_venue as _project_protection_venue,
    reduce_position_protection as _reduce_position_protection,
)
from .values import Quantity as _Quantity, ReportedPrice as _ReportedPrice
from .venue import (
    AcquisitionFactRelation as _AcquisitionFactRelation,
    AcquisitionVenueSourceKind as _AcquisitionVenueSourceKind,
    AcquisitionVenueProjection as _AcquisitionVenueProjection,
    VenueRecoveryBook as _VenueRecoveryBook,
    VenueRecoveryDisposition as _VenueRecoveryDisposition,
    VenueRecoveryTransition as _VenueRecoveryTransition,
)


__all__ = [
    "AcquisitionControllerDisposition",
    "AcquisitionControllerState",
    "AcquisitionControllerStatus",
    "AcquisitionControllerTransition",
    "AcquisitionEffectTerms",
    "GenerationServingClass",
    "GenerationRouteKind",
    "GenerationBindingView",
    "GenerationRecordView",
    "GenerationRouteView",
    "GenerationRegistry",
    "AcquisitionLineageIndex",
    "AcquisitionMandate",
    "AcquisitionOrderType",
    "AcquisitionRecoveryClass",
    "DualMandateBinding",
    "SymbolAcquisitionController",
    "begin_acquisition_generation",
    "begin_acquisition_preemption",
    "claim_acquisition_effect",
    "create_acquisition_effect",
    "create_acquisition_protection_exit",
    "initialize_acquisition_controller",
    "project_acquisition_controller",
    "rebase_acquisition_protection",
    "reduce_acquisition_controller",
]


_IDENTITY_DOMAIN = b"execution-core/acquisition-generation-id/v1"
_GENESIS_DOMAIN = b"execution-core/acquisition-controller-genesis-head/v1"
_REGISTRY_EMPTY_DOMAIN = b"execution-core/acquisition-generation-registry/empty/v1"
_LINEAGE_EMPTY_DOMAIN = b"execution-core/acquisition-lineage-index/empty/v1"
_REGISTRY_DOMAIN = b"execution-core/acquisition-generation-registry/v3"
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
class _MarketStreamGenerationRoute:
    """Private sealed ownership relation for one exact market stream."""

    stream_generation: _MarketStreamGenerationId = _field(init=False)
    binding: GenerationBindingView = _field(init=False)
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("market stream routes are registry-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("market stream routes cannot be subclassed")


@_dataclass(frozen=True, slots=True, init=False)
class GenerationRegistry:
    """Opaque, non-enumerable direct generation registry.

    E1 exposes the useful empty value.  E2 may install a record only as part
    of a sealed controller transition; callers retain the direct ``record``
    reader and never receive an iterator or map escape hatch.
    """

    _records: _PersistentKeyMap[GenerationRecordView] = _field(
        init=False,
        repr=False,
    )
    _market_stream_routes: _PersistentKeyMap[_MarketStreamGenerationRoute] = _field(
        init=False,
        repr=False,
    )
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
        records: _PersistentKeyMap[GenerationRecordView] = _PersistentKeyMap.empty()
        market_stream_routes: _PersistentKeyMap[_MarketStreamGenerationRoute] = (
            _PersistentKeyMap.empty()
        )
        object.__setattr__(result, "_records", records)
        object.__setattr__(result, "_market_stream_routes", market_stream_routes)
        object.__setattr__(
            result,
            "_seal",
            _registry_seal(records, market_stream_routes),
        )
        return result

    def record(
        self,
        generation_id: _AcquisitionGenerationId,
    ) -> GenerationRecordView | None:
        if not _registry_is_authentic(self):
            raise ValueError("generation registry authenticity check failed")
        if not _acquisition_generation_id_is_canonical(generation_id):
            raise TypeError("generation_id must be a canonical acquisition identity")
        record = self._records.get(_generation_registry_key(generation_id))
        if record is None:
            return None
        if not _generation_record_is_authentic(record):
            raise ValueError("generation registry record authenticity check failed")
        if record.binding.generation_id != generation_id:
            raise ValueError("generation registry record key does not match binding")
        return record


def _registry_is_authentic(value: object) -> bool:
    if type(value) is not GenerationRegistry:
        return False
    try:
        records = value._records
        market_stream_routes = value._market_stream_routes
        seal = value._seal
    except AttributeError:
        return False
    return bool(
        type(records) is _PersistentKeyMap
        and type(market_stream_routes) is _PersistentKeyMap
        and records.size == market_stream_routes.size
        and type(seal) is bytes
        and len(seal) == 32
        and seal == _registry_seal(records, market_stream_routes)
    )


def _generation_registry_key(generation_id: _AcquisitionGenerationId) -> bytes:
    if not _acquisition_generation_id_is_canonical(generation_id):
        raise TypeError("generation_id must be a canonical acquisition identity")
    return generation_id.value.encode("ascii")


def _market_stream_route_key(stream_generation: _MarketStreamGenerationId) -> bytes:
    if not _market_identity_is_canonical(stream_generation):
        raise TypeError("stream_generation must be a canonical market stream identity")
    return _commit_parts(
        b"execution-core/acquisition/market-stream-route-key/v1",
        _encode_text(stream_generation.value),
    )


def _registry_seal(
    records: _PersistentKeyMap[GenerationRecordView],
    market_stream_routes: _PersistentKeyMap[_MarketStreamGenerationRoute],
) -> bytes:
    if type(records) is not _PersistentKeyMap:
        raise TypeError("generation registry records must be a persistent map")
    if type(market_stream_routes) is not _PersistentKeyMap:
        raise TypeError("generation registry stream routes must be a persistent map")
    if records.size == 0 and market_stream_routes.size == 0:
        # Preserve E1's exact empty-reader identity and known semantics.
        return _commit_parts(_REGISTRY_EMPTY_DOMAIN)
    return _commit_parts(
        _REGISTRY_DOMAIN,
        records.commitment,
        market_stream_routes.commitment,
    )


def _market_stream_generation_route_commitment(
    stream_generation: _MarketStreamGenerationId,
    binding: GenerationBindingView,
) -> bytes:
    if not _market_identity_is_canonical(stream_generation):
        raise TypeError("stream route requires a canonical market stream identity")
    if not _generation_binding_view_is_authentic(binding):
        raise TypeError("stream route requires an authentic generation binding")
    return _commit_parts(
        b"execution-core/acquisition/market-stream-route/v1",
        _encode_text(stream_generation.value),
        binding.binding_commitment,
    )


def _market_stream_generation_route_seal(
    stream_generation: _MarketStreamGenerationId,
    binding: GenerationBindingView,
) -> bytes:
    commitment = _market_stream_generation_route_commitment(
        stream_generation,
        binding,
    )
    return _commit_parts(
        b"execution-core/acquisition/market-stream-route-seal/v1",
        commitment,
    )


def _market_stream_generation_route_is_authentic(value: object) -> bool:
    if type(value) is not _MarketStreamGenerationRoute:
        return False
    try:
        return bool(
            value._seal
            == _market_stream_generation_route_seal(
                value.stream_generation,
                value.binding,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _registry_market_stream_route(
    registry: GenerationRegistry,
    stream_generation: _MarketStreamGenerationId,
) -> _MarketStreamGenerationRoute | None:
    """Return one direct retained route; malformed presence never means absent."""

    if not _registry_is_authentic(registry):
        raise ValueError("generation registry authenticity check failed")
    if not _market_identity_is_canonical(stream_generation):
        raise TypeError("stream_generation must be a canonical market stream identity")
    key = _market_stream_route_key(stream_generation)
    present, route = registry._market_stream_routes._lookup(key)
    if not present:
        return None
    if route is None or not _market_stream_generation_route_is_authentic(route):
        raise ValueError("market stream route does not match its retained key")
    if (
        route.stream_generation != stream_generation
        or _market_stream_route_key(route.stream_generation) != key
    ):
        raise ValueError("market stream route does not match its retained key")
    record = registry._records.get(
        _generation_registry_key(route.binding.generation_id)
    )
    if (
        type(record) is not GenerationRecordView
        or not _generation_record_is_authentic(record)
        or record.binding != route.binding
    ):
        raise ValueError("market stream route does not match a retained generation")
    return route


def _registry_with_initial_record(
    record: GenerationRecordView,
    stream_generation: _MarketStreamGenerationId,
) -> GenerationRegistry:
    if not _generation_record_is_authentic(record) or not _market_identity_is_canonical(
        stream_generation
    ):
        raise TypeError("initial generation record must be exact and sealed")
    records: _PersistentKeyMap[GenerationRecordView] = _PersistentKeyMap.empty()
    records = records.insert_new(
        _generation_registry_key(record.binding.generation_id),
        record,
        record._seal,
    )
    market_stream_routes: _PersistentKeyMap[_MarketStreamGenerationRoute] = (
        _PersistentKeyMap.empty()
    )
    route = object.__new__(_MarketStreamGenerationRoute)
    object.__setattr__(route, "stream_generation", stream_generation)
    object.__setattr__(route, "binding", record.binding)
    object.__setattr__(
        route,
        "_seal",
        _market_stream_generation_route_seal(stream_generation, record.binding),
    )
    market_stream_routes = market_stream_routes.insert_new(
        _market_stream_route_key(stream_generation),
        route,
        route._seal,
    )
    result = object.__new__(GenerationRegistry)
    object.__setattr__(result, "_records", records)
    object.__setattr__(result, "_market_stream_routes", market_stream_routes)
    object.__setattr__(
        result,
        "_seal",
        _registry_seal(records, market_stream_routes),
    )
    return result


def _registry_with_replaced_record(
    registry: GenerationRegistry,
    record: GenerationRecordView,
) -> GenerationRegistry:
    """Replace one direct generation record without enumerating the registry."""

    if not _registry_is_authentic(registry) or not _generation_record_is_authentic(
        record
    ):
        raise TypeError("generation record replacement requires exact sealed values")
    key = _generation_registry_key(record.binding.generation_id)
    retained = registry._records.get(key)
    if type(
        retained
    ) is not GenerationRecordView or not _generation_record_is_authentic(retained):
        raise ValueError("generation record replacement requires one retained record")
    if retained.binding != record.binding:
        raise ValueError("generation record replacement cannot change lineage")
    records = registry._records.replace_existing(key, record, record._seal)
    result = object.__new__(GenerationRegistry)
    object.__setattr__(result, "_records", records)
    object.__setattr__(
        result,
        "_market_stream_routes",
        registry._market_stream_routes,
    )
    object.__setattr__(
        result,
        "_seal",
        _registry_seal(records, registry._market_stream_routes),
    )
    return result


def _registry_with_successor(
    registry: GenerationRegistry,
    retired: GenerationRecordView,
    successor: GenerationRecordView,
    successor_stream_generation: _MarketStreamGenerationId,
) -> GenerationRegistry:
    """Retire one exact LIVE record and insert its one direct successor."""

    if (
        not _registry_is_authentic(registry)
        or not _generation_record_is_authentic(retired)
        or not _generation_record_is_authentic(successor)
        or not _market_identity_is_canonical(successor_stream_generation)
        or retired.serving_class is not GenerationServingClass.RETIRED_UNSERVING
        or successor.serving_class is not GenerationServingClass.LIVE
        or retired.binding.generation_id == successor.binding.generation_id
    ):
        raise TypeError("successor registry update requires exact sealed records")
    retired_key = _generation_registry_key(retired.binding.generation_id)
    successor_key = _generation_registry_key(successor.binding.generation_id)
    retained = registry._records.get(retired_key)
    if type(
        retained
    ) is not GenerationRecordView or not _generation_record_is_authentic(retained):
        raise ValueError(
            "successor registry update requires one exact live predecessor"
        )
    if (
        retained.binding != retired.binding
        or retained.serving_class is not GenerationServingClass.LIVE
        or registry._records.get(successor_key) is not None
    ):
        raise ValueError(
            "successor registry update requires one exact live predecessor"
        )
    records = registry._records.replace_existing(retired_key, retired, retired._seal)
    records = records.insert_new(successor_key, successor, successor._seal)
    if _registry_market_stream_route(registry, successor_stream_generation) is not None:
        raise ValueError("successor registry update cannot reuse a market stream")
    route = object.__new__(_MarketStreamGenerationRoute)
    object.__setattr__(route, "stream_generation", successor_stream_generation)
    object.__setattr__(route, "binding", successor.binding)
    object.__setattr__(
        route,
        "_seal",
        _market_stream_generation_route_seal(
            successor_stream_generation,
            successor.binding,
        ),
    )
    market_stream_routes = registry._market_stream_routes.insert_new(
        _market_stream_route_key(successor_stream_generation),
        route,
        route._seal,
    )
    result = object.__new__(GenerationRegistry)
    object.__setattr__(result, "_records", records)
    object.__setattr__(result, "_market_stream_routes", market_stream_routes)
    object.__setattr__(
        result,
        "_seal",
        _registry_seal(records, market_stream_routes),
    )
    return result


@_dataclass(frozen=True, slots=True, init=False)
class AcquisitionLineageIndex:
    """Opaque, non-enumerable direct lineage read boundary.

    E1 deliberately has no successful binder.  An unbound value is never
    inferred to belong to a current generation; all five lookup families return
    ``None`` until a later authenticated E2 transition supplies direct routes.
    """

    _request_routes: _PersistentKeyMap[GenerationRouteView] = _field(
        init=False, repr=False
    )
    _effect_routes: _PersistentKeyMap[GenerationRouteView] = _field(
        init=False, repr=False
    )
    _owner_routes: _PersistentKeyMap[GenerationRouteView] = _field(
        init=False, repr=False
    )
    _root_routes: _PersistentKeyMap[GenerationRouteView] = _field(
        init=False, repr=False
    )
    _fact_routes: _PersistentKeyMap[GenerationRouteView] = _field(
        init=False, repr=False
    )
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
        empty: _PersistentKeyMap[GenerationRouteView] = _PersistentKeyMap.empty()
        return _new_acquisition_lineage_index(
            request_routes=empty,
            effect_routes=empty,
            owner_routes=empty,
            root_routes=empty,
            fact_routes=empty,
        )

    def route_request(
        self,
        request_occurrence_id: _RequestOccurrenceId,
    ) -> GenerationRouteView | None:
        _require_exact(
            "request_occurrence_id", request_occurrence_id, _RequestOccurrenceId
        )
        if not _lineage_is_authentic(self):
            raise ValueError("acquisition lineage index authenticity check failed")
        return _lineage_route(
            self,
            self._request_routes,
            GenerationRouteKind.REQUEST,
            request_occurrence_id,
        )

    def route_effect(self, effect_id: _EffectId) -> GenerationRouteView | None:
        _require_exact("effect_id", effect_id, _EffectId)
        if not _lineage_is_authentic(self):
            raise ValueError("acquisition lineage index authenticity check failed")
        return _lineage_route(
            self,
            self._effect_routes,
            GenerationRouteKind.EFFECT,
            effect_id,
        )

    def route_owner(self, leg_key: _VenueLegKey) -> GenerationRouteView | None:
        _require_exact("leg_key", leg_key, _VenueLegKey)
        if not _lineage_is_authentic(self):
            raise ValueError("acquisition lineage index authenticity check failed")
        return _lineage_route(
            self,
            self._owner_routes,
            GenerationRouteKind.OWNER,
            leg_key,
        )

    def route_root(self, root_key: _RootFillKey) -> GenerationRouteView | None:
        _require_exact("root_key", root_key, _RootFillKey)
        if not _lineage_is_authentic(self):
            raise ValueError("acquisition lineage index authenticity check failed")
        return _lineage_route(
            self,
            self._root_routes,
            GenerationRouteKind.ROOT,
            root_key,
        )

    def route_fact(self, fact_key: _ExecutionFactKey) -> GenerationRouteView | None:
        _require_exact("fact_key", fact_key, _ExecutionFactKey)
        if not _lineage_is_authentic(self):
            raise ValueError("acquisition lineage index authenticity check failed")
        return _lineage_route(
            self,
            self._fact_routes,
            GenerationRouteKind.FACT,
            fact_key,
        )


def _generation_route_commitment(
    route_kind: GenerationRouteKind,
    source_commitment: bytes,
    generation_id: _AcquisitionGenerationId,
) -> bytes:
    _require_exact("route_kind", route_kind, GenerationRouteKind)
    _require_exact_digest("source_commitment", source_commitment)
    if not _acquisition_generation_id_is_canonical(generation_id):
        raise TypeError("generation route requires a canonical generation identity")
    return _commit_parts(
        b"execution-core/acquisition/generation-route/v1",
        _encode_text(route_kind.value),
        source_commitment,
        _encode_text(generation_id.value),
    )


def _new_generation_route_view(
    *,
    route_kind: GenerationRouteKind,
    source_commitment: bytes,
    generation_id: _AcquisitionGenerationId,
) -> GenerationRouteView:
    commitment = _generation_route_commitment(
        route_kind,
        source_commitment,
        generation_id,
    )
    result = object.__new__(GenerationRouteView)
    object.__setattr__(result, "route_kind", route_kind)
    object.__setattr__(result, "source_commitment", source_commitment)
    object.__setattr__(result, "generation_id", generation_id)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/generation-route-seal/v1", commitment
        ),
    )
    return result


def _generation_route_is_authentic(value: object) -> bool:
    if type(value) is not GenerationRouteView:
        return False
    try:
        commitment = _generation_route_commitment(
            value.route_kind,
            value.source_commitment,
            value.generation_id,
        )
        return bool(
            value._seal
            == _commit_parts(
                b"execution-core/acquisition/generation-route-seal/v1", commitment
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _lineage_source_key(
    route_kind: GenerationRouteKind,
    source: object,
) -> bytes:
    _require_exact("route_kind", route_kind, GenerationRouteKind)
    if route_kind is GenerationRouteKind.REQUEST:
        if type(source) is not _RequestOccurrenceId:
            raise TypeError("request_occurrence_id must be RequestOccurrenceId")
        source_value = source.value
    elif route_kind is GenerationRouteKind.EFFECT:
        if type(source) is not _EffectId:
            raise TypeError("effect_id must be EffectId")
        source_value = source.value
    elif route_kind is GenerationRouteKind.OWNER:
        _require_exact("leg_key", source, _VenueLegKey)
        source_value = repr(source)
    elif route_kind is GenerationRouteKind.ROOT:
        _require_exact("root_key", source, _RootFillKey)
        source_value = repr(source)
    else:
        _require_exact("fact_key", source, _ExecutionFactKey)
        source_value = repr(source)
    return _commit_parts(
        b"execution-core/acquisition/lineage-source-key/v1",
        _encode_text(route_kind.value),
        _encode_text(source_value),
    )


def _lineage_map_commitment(
    request_routes: _PersistentKeyMap[GenerationRouteView],
    effect_routes: _PersistentKeyMap[GenerationRouteView],
    owner_routes: _PersistentKeyMap[GenerationRouteView],
    root_routes: _PersistentKeyMap[GenerationRouteView],
    fact_routes: _PersistentKeyMap[GenerationRouteView],
) -> bytes:
    maps = (
        request_routes,
        effect_routes,
        owner_routes,
        root_routes,
        fact_routes,
    )
    if any(type(routes) is not _PersistentKeyMap for routes in maps):
        raise TypeError("lineage routes must be persistent maps")
    if all(routes.size == 0 for routes in maps):
        return _commit_parts(_LINEAGE_EMPTY_DOMAIN)
    return _commit_parts(
        b"execution-core/acquisition/lineage-index/v1",
        *(routes.commitment for routes in maps),
    )


def _new_acquisition_lineage_index(
    *,
    request_routes: _PersistentKeyMap[GenerationRouteView],
    effect_routes: _PersistentKeyMap[GenerationRouteView],
    owner_routes: _PersistentKeyMap[GenerationRouteView],
    root_routes: _PersistentKeyMap[GenerationRouteView],
    fact_routes: _PersistentKeyMap[GenerationRouteView],
) -> AcquisitionLineageIndex:
    seal = _lineage_map_commitment(
        request_routes,
        effect_routes,
        owner_routes,
        root_routes,
        fact_routes,
    )
    result = object.__new__(AcquisitionLineageIndex)
    for name, value in (
        ("_request_routes", request_routes),
        ("_effect_routes", effect_routes),
        ("_owner_routes", owner_routes),
        ("_root_routes", root_routes),
        ("_fact_routes", fact_routes),
        ("_seal", seal),
    ):
        object.__setattr__(result, name, value)
    return result


def _lineage_route(
    index: AcquisitionLineageIndex,
    routes: _PersistentKeyMap[GenerationRouteView],
    route_kind: GenerationRouteKind,
    source: object,
) -> GenerationRouteView | None:
    if not _lineage_is_authentic(index):
        raise ValueError("acquisition lineage index authenticity check failed")
    route = routes.get(_lineage_source_key(route_kind, source))
    if route is None:
        return None
    if (
        not _generation_route_is_authentic(route)
        or route.route_kind is not route_kind
        or route.source_commitment
        != _commit_parts(
            b"execution-core/acquisition/lineage-source/v1",
            _lineage_source_key(route_kind, source),
        )
    ):
        raise ValueError("acquisition lineage route authenticity check failed")
    return route


def _lineage_is_authentic(value: object) -> bool:
    if type(value) is not AcquisitionLineageIndex:
        return False
    try:
        request_routes = value._request_routes
        effect_routes = value._effect_routes
        owner_routes = value._owner_routes
        root_routes = value._root_routes
        fact_routes = value._fact_routes
        seal = value._seal
    except AttributeError:
        return False
    try:
        return bool(
            type(seal) is bytes
            and seal
            == _lineage_map_commitment(
                request_routes,
                effect_routes,
                owner_routes,
                root_routes,
                fact_routes,
            )
        )
    except (TypeError, ValueError):
        return False


def _lineage_with_first_effect(
    index: AcquisitionLineageIndex,
    *,
    request_occurrence_id: _RequestOccurrenceId,
    effect_id: _EffectId,
    generation_id: _AcquisitionGenerationId,
) -> AcquisitionLineageIndex:
    """Install the immutable first request/effect routes without enumeration."""

    if not _lineage_is_authentic(index):
        raise ValueError("first effect requires an authentic lineage index")
    if (
        index._request_routes.get(
            _lineage_source_key(GenerationRouteKind.REQUEST, request_occurrence_id)
        )
        is not None
        or index._effect_routes.get(
            _lineage_source_key(GenerationRouteKind.EFFECT, effect_id)
        )
        is not None
    ):
        raise ValueError("first effect lineage route already exists")
    request_key = _lineage_source_key(
        GenerationRouteKind.REQUEST,
        request_occurrence_id,
    )
    effect_key = _lineage_source_key(GenerationRouteKind.EFFECT, effect_id)
    request_route = _new_generation_route_view(
        route_kind=GenerationRouteKind.REQUEST,
        source_commitment=_commit_parts(
            b"execution-core/acquisition/lineage-source/v1",
            request_key,
        ),
        generation_id=generation_id,
    )
    effect_route = _new_generation_route_view(
        route_kind=GenerationRouteKind.EFFECT,
        source_commitment=_commit_parts(
            b"execution-core/acquisition/lineage-source/v1",
            effect_key,
        ),
        generation_id=generation_id,
    )
    return _new_acquisition_lineage_index(
        request_routes=index._request_routes.insert_new(
            request_key,
            request_route,
            request_route._seal,
        ),
        effect_routes=index._effect_routes.insert_new(
            effect_key,
            effect_route,
            effect_route._seal,
        ),
        owner_routes=index._owner_routes,
        root_routes=index._root_routes,
        fact_routes=index._fact_routes,
    )


def _lineage_with_first_fact(
    index: AcquisitionLineageIndex,
    *,
    relation: _AcquisitionFactRelation,
    generation_id: _AcquisitionGenerationId,
) -> AcquisitionLineageIndex:
    """Install the first owner/root/fact routes through direct keys only."""

    if (
        not _lineage_is_authentic(index)
        or type(relation) is not _AcquisitionFactRelation
        or not _acquisition_generation_id_is_canonical(generation_id)
    ):
        raise TypeError("first fact lineage requires exact sealed inputs")
    request_route = index.route_request(relation.request_occurrence_id)
    effect_route = index.route_effect(relation.effect_id)
    if (
        request_route is None
        or effect_route is None
        or request_route.generation_id != generation_id
        or effect_route.generation_id != generation_id
        or index.route_owner(relation.leg_key) is not None
        or index.route_root(relation.root_key) is not None
        or index.route_fact(relation.fact_key) is not None
    ):
        raise ValueError("first fact lineage route is not exact")
    owner_key = _lineage_source_key(GenerationRouteKind.OWNER, relation.leg_key)
    root_key = _lineage_source_key(GenerationRouteKind.ROOT, relation.root_key)
    fact_key = _lineage_source_key(GenerationRouteKind.FACT, relation.fact_key)
    owner_route = _new_generation_route_view(
        route_kind=GenerationRouteKind.OWNER,
        source_commitment=_commit_parts(
            b"execution-core/acquisition/lineage-source/v1",
            owner_key,
        ),
        generation_id=generation_id,
    )
    root_route = _new_generation_route_view(
        route_kind=GenerationRouteKind.ROOT,
        source_commitment=_commit_parts(
            b"execution-core/acquisition/lineage-source/v1",
            root_key,
        ),
        generation_id=generation_id,
    )
    fact_route = _new_generation_route_view(
        route_kind=GenerationRouteKind.FACT,
        source_commitment=_commit_parts(
            b"execution-core/acquisition/lineage-source/v1",
            fact_key,
        ),
        generation_id=generation_id,
    )
    return _new_acquisition_lineage_index(
        request_routes=index._request_routes,
        effect_routes=index._effect_routes,
        owner_routes=index._owner_routes.insert_new(
            owner_key,
            owner_route,
            owner_route._seal,
        ),
        root_routes=index._root_routes.insert_new(
            root_key,
            root_route,
            root_route._seal,
        ),
        fact_routes=index._fact_routes.insert_new(
            fact_key,
            fact_route,
            fact_route._seal,
        ),
    )


def _lineage_with_generation_fact(
    index: AcquisitionLineageIndex,
    *,
    relation: _AcquisitionFactRelation,
    generation_id: _AcquisitionGenerationId,
) -> AcquisitionLineageIndex:
    """Insert one new direct fact while preserving existing same-generation routes."""

    if (
        not _lineage_is_authentic(index)
        or type(relation) is not _AcquisitionFactRelation
        or not _acquisition_generation_id_is_canonical(generation_id)
    ):
        raise TypeError("generation fact lineage requires exact sealed inputs")
    request_route = index.route_request(relation.request_occurrence_id)
    effect_route = index.route_effect(relation.effect_id)
    owner_route = index.route_owner(relation.leg_key)
    root_route = index.route_root(relation.root_key)
    if (
        request_route is None
        or effect_route is None
        or request_route.generation_id != generation_id
        or effect_route.generation_id != generation_id
        or (owner_route is not None and owner_route.generation_id != generation_id)
        or (root_route is not None and root_route.generation_id != generation_id)
        or index.route_fact(relation.fact_key) is not None
    ):
        raise ValueError("generation fact lineage route is not exact")

    owner_routes = index._owner_routes
    if owner_route is None:
        owner_key = _lineage_source_key(GenerationRouteKind.OWNER, relation.leg_key)
        owner_route = _new_generation_route_view(
            route_kind=GenerationRouteKind.OWNER,
            source_commitment=_commit_parts(
                b"execution-core/acquisition/lineage-source/v1",
                owner_key,
            ),
            generation_id=generation_id,
        )
        owner_routes = owner_routes.insert_new(
            owner_key,
            owner_route,
            owner_route._seal,
        )

    root_routes = index._root_routes
    if root_route is None:
        root_key = _lineage_source_key(GenerationRouteKind.ROOT, relation.root_key)
        root_route = _new_generation_route_view(
            route_kind=GenerationRouteKind.ROOT,
            source_commitment=_commit_parts(
                b"execution-core/acquisition/lineage-source/v1",
                root_key,
            ),
            generation_id=generation_id,
        )
        root_routes = root_routes.insert_new(
            root_key,
            root_route,
            root_route._seal,
        )

    fact_key = _lineage_source_key(GenerationRouteKind.FACT, relation.fact_key)
    fact_route = _new_generation_route_view(
        route_kind=GenerationRouteKind.FACT,
        source_commitment=_commit_parts(
            b"execution-core/acquisition/lineage-source/v1",
            fact_key,
        ),
        generation_id=generation_id,
    )
    return _new_acquisition_lineage_index(
        request_routes=index._request_routes,
        effect_routes=index._effect_routes,
        owner_routes=owner_routes,
        root_routes=root_routes,
        fact_routes=index._fact_routes.insert_new(
            fact_key,
            fact_route,
            fact_route._seal,
        ),
    )


# ---------------------------------------------------------------------------
# E2 mandate and controller values
# ---------------------------------------------------------------------------


def _require_nonblank_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must be nonblank")
    return value


def _require_positive_quantity(name: str, value: object) -> _Quantity:
    if type(value) is not _Quantity:
        raise TypeError(f"{name} must be Quantity")
    if value.value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _require_positive_fraction(name: str, value: object) -> _Fraction:
    if type(value) is not _Fraction:
        raise TypeError(f"{name} must be Fraction")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _require_nonnegative_int(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _require_exact_digest(name: str, value: object) -> bytes:
    if type(value) is not bytes:
        raise TypeError(f"{name} must be bytes")
    if len(value) != 32:
        raise ValueError(f"{name} must contain exactly 32 bytes")
    return value


def _encode_fraction(value: _Fraction) -> bytes:
    if type(value) is not _Fraction:
        raise TypeError("fraction must be exact")
    return _pack_parts(
        _encode_int(value.numerator),
        _encode_int(value.denominator),
    )


def _reported_price_commitment(value: _ReportedPrice) -> bytes:
    if type(value) is not _ReportedPrice:
        raise TypeError("price must be ReportedPrice")
    if value.exact_value <= 0 or not value.is_aligned:
        raise ValueError("price must be positive and tick-aligned")
    return _commit_parts(
        b"execution-core/acquisition/reported-price/v1",
        _encode_fraction(value.exact_value),
        _encode_int(value.units.value),
        _encode_text(str(value.scale.value)),
        _encode_int(value.tick.tick_units.value),
        _encode_text(str(value.tick.scale.value)),
    )


def _allowed_order_types_commitment(
    allowed_order_types: tuple[AcquisitionOrderType, ...],
) -> bytes:
    if type(allowed_order_types) is not tuple or not allowed_order_types:
        raise ValueError("allowed_order_types must be a nonempty exact tuple")
    if any(type(value) is not AcquisitionOrderType for value in allowed_order_types):
        raise TypeError("allowed_order_types must contain AcquisitionOrderType values")
    if len(set(allowed_order_types)) != len(allowed_order_types):
        raise ValueError("allowed_order_types must not repeat a value")
    if set(allowed_order_types) != {AcquisitionOrderType.LIMIT}:
        raise ValueError("pure M1 permits only LIMIT acquisition orders")
    return _commit_parts(
        b"execution-core/acquisition/allowed-order-types/v1",
        *(_encode_text(value.value) for value in allowed_order_types),
    )


def _acquisition_mandate_terms_commitment(
    *,
    acquisition_mandate_id: _AcquisitionMandateId,
    position_scope: _PositionScope,
    session_id: _SessionId,
    configuration_version: str,
    maximum_quantity: _Quantity,
    maximum_notional: _Fraction,
    maximum_entry_price: _ReportedPrice,
    allowed_order_types: tuple[AcquisitionOrderType, ...],
    expiry: int,
    deadline: int,
    fixed_child_cap: _Quantity,
    certified_participation_cap: _Fraction | None,
    cancel_reprice_budget: int,
) -> bytes:
    _require_exact(
        "acquisition_mandate_id", acquisition_mandate_id, _AcquisitionMandateId
    )
    _require_exact("position_scope", position_scope, _PositionScope)
    _require_exact("session_id", session_id, _SessionId)
    _require_nonblank_text("configuration_version", configuration_version)
    maximum_quantity = _require_positive_quantity("maximum_quantity", maximum_quantity)
    maximum_notional = _require_positive_fraction("maximum_notional", maximum_notional)
    maximum_entry_price_commitment = _reported_price_commitment(maximum_entry_price)
    allowed_order_types_commitment = _allowed_order_types_commitment(
        allowed_order_types
    )
    expiry = _require_nonnegative_int("expiry", expiry)
    deadline = _require_nonnegative_int("deadline", deadline)
    if deadline > expiry:
        raise ValueError("deadline must not exceed expiry")
    fixed_child_cap = _require_positive_quantity("fixed_child_cap", fixed_child_cap)
    if fixed_child_cap.value > maximum_quantity.value:
        raise ValueError("fixed_child_cap must not exceed maximum_quantity")
    if certified_participation_cap is not None:
        if type(certified_participation_cap) is not _Fraction:
            raise TypeError("certified_participation_cap must be Fraction or None")
        if certified_participation_cap <= 0 or certified_participation_cap > 1:
            raise ValueError("certified_participation_cap must be in (0, 1]")
    cancel_reprice_budget = _require_nonnegative_int(
        "cancel_reprice_budget",
        cancel_reprice_budget,
    )
    return _commit_parts(
        b"execution-core/acquisition/mandate-terms/v1",
        _encode_text(acquisition_mandate_id.value),
        _encode_position_scope(position_scope),
        _encode_text(session_id.value),
        _encode_text(configuration_version),
        _encode_int(maximum_quantity.value),
        _encode_fraction(maximum_notional),
        maximum_entry_price_commitment,
        allowed_order_types_commitment,
        _encode_int(expiry),
        _encode_int(deadline),
        _encode_int(fixed_child_cap.value),
        b""
        if certified_participation_cap is None
        else _encode_fraction(certified_participation_cap),
        _encode_int(cancel_reprice_budget),
    )


@_dataclass(frozen=True, slots=True, init=False)
class DualMandateBinding:
    """Opaque commitment coupling one acquisition mandate to protection."""

    acquisition_mandate_id: _AcquisitionMandateId = _field(init=False)
    protection_mandate_id: _MandateId = _field(init=False)
    position_scope: _PositionScope = _field(init=False)
    session_id: _SessionId = _field(init=False)
    configuration_version: str = _field(init=False)
    commitment: bytes = _field(init=False)
    _acquisition_terms_commitment: bytes = _field(init=False, repr=False)
    _protection_mandate_commitment: bytes = _field(init=False, repr=False)
    _compatibility_commitment: bytes = _field(init=False, repr=False)
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("DualMandateBinding is reducer-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("DualMandateBinding cannot be subclassed")


def _dual_mandate_binding_commitment(
    acquisition_mandate_id: _AcquisitionMandateId,
    protection_mandate_id: _MandateId,
    position_scope: _PositionScope,
    session_id: _SessionId,
    configuration_version: str,
    acquisition_terms_commitment: bytes,
    protection_mandate_commitment: bytes,
    compatibility_commitment: bytes,
) -> bytes:
    _require_exact(
        "acquisition_mandate_id", acquisition_mandate_id, _AcquisitionMandateId
    )
    _require_exact("protection_mandate_id", protection_mandate_id, _MandateId)
    _require_exact("position_scope", position_scope, _PositionScope)
    _require_exact("session_id", session_id, _SessionId)
    _require_nonblank_text("configuration_version", configuration_version)
    for name, value in (
        ("acquisition_terms_commitment", acquisition_terms_commitment),
        ("protection_mandate_commitment", protection_mandate_commitment),
        ("compatibility_commitment", compatibility_commitment),
    ):
        _require_exact_digest(name, value)
    return _commit_parts(
        b"execution-core/acquisition/dual-mandate-binding/v1",
        _encode_text(acquisition_mandate_id.value),
        _encode_text(protection_mandate_id.value),
        _encode_position_scope(position_scope),
        _encode_text(session_id.value),
        _encode_text(configuration_version),
        acquisition_terms_commitment,
        protection_mandate_commitment,
        compatibility_commitment,
    )


def _mint_dual_mandate_binding(
    *,
    acquisition_mandate_id: _AcquisitionMandateId,
    position_scope: _PositionScope,
    session_id: _SessionId,
    configuration_version: str,
    maximum_quantity: _Quantity,
    maximum_notional: _Fraction,
    maximum_entry_price: _ReportedPrice,
    allowed_order_types: tuple[AcquisitionOrderType, ...],
    expiry: int,
    deadline: int,
    fixed_child_cap: _Quantity,
    certified_participation_cap: _Fraction | None,
    cancel_reprice_budget: int,
    protection_mandate: _ProtectionMandate,
) -> DualMandateBinding:
    """Mint a sealed complete dual binding for an already-approved mandate.

    This is deliberately private.  A future configuration boundary may own
    operator approval; pure M1 only consumes the sealed result.
    """

    if type(protection_mandate) is not _ProtectionMandate:
        raise TypeError("protection_mandate must be ProtectionMandate")
    if (
        protection_mandate.position_scope != position_scope
        or protection_mandate.session_id != session_id
    ):
        raise ValueError(
            "protection mandate must share the acquisition scope and session"
        )
    if acquisition_mandate_id.value == protection_mandate.mandate_id.value:
        raise ValueError("acquisition and protection mandate identities must differ")
    acquisition_terms_commitment = _acquisition_mandate_terms_commitment(
        acquisition_mandate_id=acquisition_mandate_id,
        position_scope=position_scope,
        session_id=session_id,
        configuration_version=configuration_version,
        maximum_quantity=maximum_quantity,
        maximum_notional=maximum_notional,
        maximum_entry_price=maximum_entry_price,
        allowed_order_types=allowed_order_types,
        expiry=expiry,
        deadline=deadline,
        fixed_child_cap=fixed_child_cap,
        certified_participation_cap=certified_participation_cap,
        cancel_reprice_budget=cancel_reprice_budget,
    )
    protection_mandate_commitment = _require_exact_digest(
        "protection_mandate.commitment",
        protection_mandate.commitment,
    )
    compatibility_commitment = _require_exact_digest(
        "emergency_recovery_compatibility.commitment",
        protection_mandate.emergency_recovery_compatibility.commitment,
    )
    commitment = _dual_mandate_binding_commitment(
        acquisition_mandate_id,
        protection_mandate.mandate_id,
        position_scope,
        session_id,
        configuration_version,
        acquisition_terms_commitment,
        protection_mandate_commitment,
        compatibility_commitment,
    )
    result = object.__new__(DualMandateBinding)
    object.__setattr__(result, "acquisition_mandate_id", acquisition_mandate_id)
    object.__setattr__(result, "protection_mandate_id", protection_mandate.mandate_id)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(result, "session_id", session_id)
    object.__setattr__(result, "configuration_version", configuration_version)
    object.__setattr__(result, "commitment", commitment)
    object.__setattr__(
        result,
        "_acquisition_terms_commitment",
        acquisition_terms_commitment,
    )
    object.__setattr__(
        result,
        "_protection_mandate_commitment",
        protection_mandate_commitment,
    )
    object.__setattr__(result, "_compatibility_commitment", compatibility_commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/dual-mandate-binding-seal/v1",
            commitment,
        ),
    )
    return result


def _dual_mandate_binding_is_authentic(value: object) -> bool:
    if type(value) is not DualMandateBinding:
        return False
    try:
        commitment = _dual_mandate_binding_commitment(
            value.acquisition_mandate_id,
            value.protection_mandate_id,
            value.position_scope,
            value.session_id,
            value.configuration_version,
            value._acquisition_terms_commitment,
            value._protection_mandate_commitment,
            value._compatibility_commitment,
        )
        return bool(
            value.commitment == commitment
            and value._seal
            == _commit_parts(
                b"execution-core/acquisition/dual-mandate-binding-seal/v1",
                commitment,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


@_dataclass(frozen=True, slots=True)
class AcquisitionMandate:
    """One complete operator-approved acquisition mandate and exact binding."""

    acquisition_mandate_id: _AcquisitionMandateId
    position_scope: _PositionScope
    session_id: _SessionId
    configuration_version: str
    maximum_quantity: _Quantity
    maximum_notional: _Fraction
    maximum_entry_price: _ReportedPrice
    allowed_order_types: tuple[AcquisitionOrderType, ...]
    expiry: int
    deadline: int
    fixed_child_cap: _Quantity
    certified_participation_cap: _Fraction | None
    cancel_reprice_budget: int
    protection_mandate: _ProtectionMandate
    binding: DualMandateBinding

    def __post_init__(self) -> None:
        terms = _acquisition_mandate_terms_commitment(
            acquisition_mandate_id=self.acquisition_mandate_id,
            position_scope=self.position_scope,
            session_id=self.session_id,
            configuration_version=self.configuration_version,
            maximum_quantity=self.maximum_quantity,
            maximum_notional=self.maximum_notional,
            maximum_entry_price=self.maximum_entry_price,
            allowed_order_types=self.allowed_order_types,
            expiry=self.expiry,
            deadline=self.deadline,
            fixed_child_cap=self.fixed_child_cap,
            certified_participation_cap=self.certified_participation_cap,
            cancel_reprice_budget=self.cancel_reprice_budget,
        )
        if type(self.protection_mandate) is not _ProtectionMandate:
            raise TypeError("protection_mandate must be ProtectionMandate")
        if not _dual_mandate_binding_is_authentic(self.binding):
            raise ValueError("dual mandate binding is not authentic")
        if (
            self.protection_mandate.position_scope != self.position_scope
            or self.protection_mandate.session_id != self.session_id
            or self.binding.acquisition_mandate_id != self.acquisition_mandate_id
            or self.binding.protection_mandate_id != self.protection_mandate.mandate_id
            or self.binding.position_scope != self.position_scope
            or self.binding.session_id != self.session_id
            or self.binding.configuration_version != self.configuration_version
            or self.binding._acquisition_terms_commitment != terms
            or self.binding._protection_mandate_commitment
            != self.protection_mandate.commitment
            or self.binding._compatibility_commitment
            != self.protection_mandate.emergency_recovery_compatibility.commitment
        ):
            raise ValueError("dual mandate binding does not match its complete mandate")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionMandate cannot be subclassed")


def _acquisition_mandate_is_authentic(value: object) -> bool:
    if type(value) is not AcquisitionMandate:
        return False
    try:
        AcquisitionMandate(
            acquisition_mandate_id=value.acquisition_mandate_id,
            position_scope=value.position_scope,
            session_id=value.session_id,
            configuration_version=value.configuration_version,
            maximum_quantity=value.maximum_quantity,
            maximum_notional=value.maximum_notional,
            maximum_entry_price=value.maximum_entry_price,
            allowed_order_types=value.allowed_order_types,
            expiry=value.expiry,
            deadline=value.deadline,
            fixed_child_cap=value.fixed_child_cap,
            certified_participation_cap=value.certified_participation_cap,
            cancel_reprice_budget=value.cancel_reprice_budget,
            protection_mandate=value.protection_mandate,
            binding=value.binding,
        )
    except (AttributeError, TypeError, ValueError):
        return False
    return True


class AcquisitionControllerDisposition(_Enum):
    APPLIED = "APPLIED"
    EXACT_REPLAY = "EXACT_REPLAY"
    REFUSED = "REFUSED"


class AcquisitionRecoveryClass(_Enum):
    NORMAL = "NORMAL"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    MIXED_GENERATION_RECOVERY = "MIXED_GENERATION_RECOVERY"
    MIXED_GENERATION_RECONCILIATION_REQUIRED = (
        "MIXED_GENERATION_RECONCILIATION_REQUIRED"
    )


def _generation_binding_view_commitment(
    generation_id: _AcquisitionGenerationId,
    application_generation_id: _ApplicationGenerationId,
    position_scope: _PositionScope,
    successor_ordinal: int,
    dual_mandate_binding_commitment: bytes,
    predecessor_or_genesis_head_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
) -> bytes:
    if not _acquisition_generation_id_is_canonical(generation_id):
        raise TypeError("generation_id must be a canonical acquisition identity")
    _require_exact(
        "application_generation_id",
        application_generation_id,
        _ApplicationGenerationId,
    )
    _require_exact("position_scope", position_scope, _PositionScope)
    successor_ordinal = _require_ordinal(successor_ordinal)
    for name, digest in (
        ("dual_mandate_binding_commitment", dual_mandate_binding_commitment),
        (
            "predecessor_or_genesis_head_commitment",
            predecessor_or_genesis_head_commitment,
        ),
        (
            "emergency_recovery_compatibility_commitment",
            emergency_recovery_compatibility_commitment,
        ),
    ):
        _require_exact_digest(name, digest)
    return _commit_parts(
        b"execution-core/acquisition/generation-binding/v1",
        _encode_text(generation_id.value),
        _encode_text(application_generation_id.value),
        _encode_position_scope(position_scope),
        _encode_int(successor_ordinal),
        dual_mandate_binding_commitment,
        predecessor_or_genesis_head_commitment,
        emergency_recovery_compatibility_commitment,
    )


def _new_generation_binding_view(
    *,
    generation_id: _AcquisitionGenerationId,
    application_generation_id: _ApplicationGenerationId,
    position_scope: _PositionScope,
    successor_ordinal: int,
    dual_mandate_binding_commitment: bytes,
    predecessor_or_genesis_head_commitment: bytes,
    emergency_recovery_compatibility_commitment: bytes,
) -> GenerationBindingView:
    binding_commitment = _generation_binding_view_commitment(
        generation_id,
        application_generation_id,
        position_scope,
        successor_ordinal,
        dual_mandate_binding_commitment,
        predecessor_or_genesis_head_commitment,
        emergency_recovery_compatibility_commitment,
    )
    result = object.__new__(GenerationBindingView)
    object.__setattr__(result, "generation_id", generation_id)
    object.__setattr__(result, "application_generation_id", application_generation_id)
    object.__setattr__(result, "position_scope", position_scope)
    object.__setattr__(result, "successor_ordinal", successor_ordinal)
    object.__setattr__(
        result,
        "dual_mandate_binding_commitment",
        dual_mandate_binding_commitment,
    )
    object.__setattr__(
        result,
        "predecessor_or_genesis_head_commitment",
        predecessor_or_genesis_head_commitment,
    )
    object.__setattr__(
        result,
        "emergency_recovery_compatibility_commitment",
        emergency_recovery_compatibility_commitment,
    )
    object.__setattr__(result, "binding_commitment", binding_commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/generation-binding-seal/v1",
            binding_commitment,
        ),
    )
    return result


def _generation_binding_view_is_authentic(value: object) -> bool:
    if type(value) is not GenerationBindingView:
        return False
    try:
        commitment = _generation_binding_view_commitment(
            value.generation_id,
            value.application_generation_id,
            value.position_scope,
            value.successor_ordinal,
            value.dual_mandate_binding_commitment,
            value.predecessor_or_genesis_head_commitment,
            value.emergency_recovery_compatibility_commitment,
        )
        return bool(
            value.binding_commitment == commitment
            and value._seal
            == _commit_parts(
                b"execution-core/acquisition/generation-binding-seal/v1",
                commitment,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _generation_record_view_commitment(
    binding: GenerationBindingView,
    economics_head_commitment: bytes,
    serving_class: GenerationServingClass,
    closure_summary_commitment: bytes,
) -> bytes:
    if not _generation_binding_view_is_authentic(binding):
        raise TypeError("generation record requires an authentic binding")
    _require_exact_digest("economics_head_commitment", economics_head_commitment)
    _require_exact("serving_class", serving_class, GenerationServingClass)
    _require_exact_digest("closure_summary_commitment", closure_summary_commitment)
    return _commit_parts(
        b"execution-core/acquisition/generation-record/v1",
        binding.binding_commitment,
        economics_head_commitment,
        _encode_text(serving_class.value),
        closure_summary_commitment,
    )


def _new_generation_record_view(
    *,
    binding: GenerationBindingView,
    economics_head_commitment: bytes,
    serving_class: GenerationServingClass,
    closure_summary_commitment: bytes,
) -> GenerationRecordView:
    commitment = _generation_record_view_commitment(
        binding,
        economics_head_commitment,
        serving_class,
        closure_summary_commitment,
    )
    result = object.__new__(GenerationRecordView)
    object.__setattr__(result, "binding", binding)
    object.__setattr__(result, "economics_head_commitment", economics_head_commitment)
    object.__setattr__(result, "serving_class", serving_class)
    object.__setattr__(result, "closure_summary_commitment", closure_summary_commitment)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/generation-record-seal/v1",
            commitment,
        ),
    )
    return result


def _generation_record_is_authentic(value: object) -> bool:
    if type(value) is not GenerationRecordView:
        return False
    try:
        commitment = _generation_record_view_commitment(
            value.binding,
            value.economics_head_commitment,
            value.serving_class,
            value.closure_summary_commitment,
        )
        return bool(
            value._seal
            == _commit_parts(
                b"execution-core/acquisition/generation-record-seal/v1",
                commitment,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _initial_generation_economics_head(
    binding: GenerationBindingView,
) -> bytes:
    if not _generation_binding_view_is_authentic(binding):
        raise TypeError("initial economics requires an authentic binding")
    return _commit_parts(
        b"execution-core/acquisition/generation-economics/genesis/v1",
        binding.binding_commitment,
    )


def _initial_generation_closure_summary(
    binding: GenerationBindingView,
) -> bytes:
    if not _generation_binding_view_is_authentic(binding):
        raise TypeError("initial closure summary requires an authentic binding")
    return _commit_parts(
        b"execution-core/acquisition/generation-closure/genesis/v1",
        binding.binding_commitment,
    )


def _retired_generation_closure_summary(
    record: GenerationRecordView,
    successor: GenerationBindingView,
) -> bytes:
    """Commit one derived terminal predecessor to its exact successor."""

    if (
        not _generation_record_is_authentic(record)
        or not _generation_binding_view_is_authentic(successor)
        or record.serving_class is not GenerationServingClass.LIVE
        or record.binding.application_generation_id
        != successor.application_generation_id
        or record.binding.position_scope != successor.position_scope
        or record.binding.successor_ordinal + 1 != successor.successor_ordinal
    ):
        raise TypeError("retirement requires one exact serial successor")
    return _commit_parts(
        b"execution-core/acquisition/generation-closure/retired/v1",
        record.closure_summary_commitment,
        record.binding.binding_commitment,
        successor.binding_commitment,
    )


@_dataclass(frozen=True, slots=True, init=False)
class SymbolAcquisitionController:
    """Constant-size sealed controller state for one exact position scope."""

    application_generation_id: _ApplicationGenerationId = _field(init=False)
    position_scope: _PositionScope = _field(init=False)
    controller_head: bytes = _field(init=False)
    successor_ordinal: int = _field(init=False)
    live_generation_id: _AcquisitionGenerationId | None = _field(init=False)
    recovery_class: AcquisitionRecoveryClass = _field(init=False)
    scope_execution_commitment: bytes = _field(init=False)
    venue_commitment: bytes = _field(init=False)
    authority_context_commitment: bytes = _field(init=False)
    protection_commitment: bytes | None = _field(init=False)
    commitment: bytes = _field(init=False)
    _binding_commitment: bytes = _field(init=False, repr=False)
    _compatibility_commitment: bytes = _field(init=False, repr=False)
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("SymbolAcquisitionController is reducer-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("SymbolAcquisitionController cannot be subclassed")


def _optional_digest_commitment(value: bytes | None, domain: bytes) -> bytes:
    if value is None:
        return _commit_parts(domain, b"none")
    return _require_exact_digest("optional commitment", value)


def _controller_commitment(
    *,
    application_generation_id: _ApplicationGenerationId,
    position_scope: _PositionScope,
    controller_head: bytes,
    successor_ordinal: int,
    live_generation_id: _AcquisitionGenerationId | None,
    recovery_class: AcquisitionRecoveryClass,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    protection_commitment: bytes | None,
    binding_commitment: bytes,
    compatibility_commitment: bytes,
) -> bytes:
    _require_exact(
        "application_generation_id",
        application_generation_id,
        _ApplicationGenerationId,
    )
    _require_exact("position_scope", position_scope, _PositionScope)
    _require_exact_digest("controller_head", controller_head)
    _require_ordinal(successor_ordinal)
    if live_generation_id is not None and not _acquisition_generation_id_is_canonical(
        live_generation_id
    ):
        raise TypeError("live_generation_id must be a canonical acquisition identity")
    _require_exact("recovery_class", recovery_class, AcquisitionRecoveryClass)
    for name, digest in (
        ("scope_execution_commitment", scope_execution_commitment),
        ("venue_commitment", venue_commitment),
        ("authority_context_commitment", authority_context_commitment),
        ("binding_commitment", binding_commitment),
        ("compatibility_commitment", compatibility_commitment),
    ):
        _require_exact_digest(name, digest)
    return _commit_parts(
        b"execution-core/acquisition/symbol-controller/v1",
        _encode_text(application_generation_id.value),
        _encode_position_scope(position_scope),
        controller_head,
        _encode_int(successor_ordinal),
        b"" if live_generation_id is None else _encode_text(live_generation_id.value),
        _encode_text(recovery_class.value),
        scope_execution_commitment,
        venue_commitment,
        authority_context_commitment,
        _optional_digest_commitment(
            protection_commitment,
            b"execution-core/acquisition/no-protection/v1",
        ),
        binding_commitment,
        compatibility_commitment,
    )


def _new_symbol_acquisition_controller(
    *,
    application_generation_id: _ApplicationGenerationId,
    position_scope: _PositionScope,
    controller_head: bytes,
    successor_ordinal: int,
    live_generation_id: _AcquisitionGenerationId,
    recovery_class: AcquisitionRecoveryClass,
    scope_execution_commitment: bytes,
    venue_commitment: bytes,
    authority_context_commitment: bytes,
    protection_commitment: bytes | None,
    binding_commitment: bytes,
    compatibility_commitment: bytes,
) -> SymbolAcquisitionController:
    commitment = _controller_commitment(
        application_generation_id=application_generation_id,
        position_scope=position_scope,
        controller_head=controller_head,
        successor_ordinal=successor_ordinal,
        live_generation_id=live_generation_id,
        recovery_class=recovery_class,
        scope_execution_commitment=scope_execution_commitment,
        venue_commitment=venue_commitment,
        authority_context_commitment=authority_context_commitment,
        protection_commitment=protection_commitment,
        binding_commitment=binding_commitment,
        compatibility_commitment=compatibility_commitment,
    )
    result = object.__new__(SymbolAcquisitionController)
    for name, value in (
        ("application_generation_id", application_generation_id),
        ("position_scope", position_scope),
        ("controller_head", controller_head),
        ("successor_ordinal", successor_ordinal),
        ("live_generation_id", live_generation_id),
        ("recovery_class", recovery_class),
        ("scope_execution_commitment", scope_execution_commitment),
        ("venue_commitment", venue_commitment),
        ("authority_context_commitment", authority_context_commitment),
        ("protection_commitment", protection_commitment),
        ("commitment", commitment),
        ("_binding_commitment", binding_commitment),
        ("_compatibility_commitment", compatibility_commitment),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/symbol-controller-seal/v1", commitment
        ),
    )
    return result


def _controller_is_authentic(value: object) -> bool:
    if type(value) is not SymbolAcquisitionController:
        return False
    try:
        commitment = _controller_commitment(
            application_generation_id=value.application_generation_id,
            position_scope=value.position_scope,
            controller_head=value.controller_head,
            successor_ordinal=value.successor_ordinal,
            live_generation_id=value.live_generation_id,
            recovery_class=value.recovery_class,
            scope_execution_commitment=value.scope_execution_commitment,
            venue_commitment=value.venue_commitment,
            authority_context_commitment=value.authority_context_commitment,
            protection_commitment=value.protection_commitment,
            binding_commitment=value._binding_commitment,
            compatibility_commitment=value._compatibility_commitment,
        )
        return bool(
            value.commitment == commitment
            and value._seal
            == _commit_parts(
                b"execution-core/acquisition/symbol-controller-seal/v1",
                commitment,
            )
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _controller_state_commitment(
    controller: SymbolAcquisitionController,
    registry: GenerationRegistry,
    lineage: AcquisitionLineageIndex,
) -> bytes:
    if not _controller_is_authentic(controller):
        raise TypeError("controller state requires an authentic controller")
    if not _registry_is_authentic(registry):
        raise TypeError("controller state requires an authentic registry")
    if not _lineage_is_authentic(lineage):
        raise TypeError("controller state requires an authentic lineage index")
    return _commit_parts(
        b"execution-core/acquisition/controller-state/v1",
        controller.commitment,
        registry._seal,
        lineage._seal,
    )


@_dataclass(frozen=True, slots=True, init=False)
class AcquisitionControllerState:
    """Opaque acquisition controller state with bounded current projections."""

    application_generation_id: _ApplicationGenerationId = _field(init=False)
    position_scope: _PositionScope = _field(init=False)
    scope_execution_commitment: bytes = _field(init=False)
    venue_commitment: bytes = _field(init=False)
    authority_context_commitment: bytes = _field(init=False)
    protection_commitment: bytes | None = _field(init=False)
    controller_commitment: bytes = _field(init=False)
    registry: GenerationRegistry = _field(init=False)
    lineage: AcquisitionLineageIndex = _field(init=False)
    commitment: bytes = _field(init=False)
    _controller: SymbolAcquisitionController = _field(init=False, repr=False)
    _mandate: AcquisitionMandate = _field(init=False, repr=False)
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionControllerState is reducer-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionControllerState cannot be subclassed")


def _new_acquisition_controller_state(
    *,
    controller: SymbolAcquisitionController,
    mandate: AcquisitionMandate,
    registry: GenerationRegistry,
    lineage: AcquisitionLineageIndex,
) -> AcquisitionControllerState:
    if not _controller_is_authentic(controller):
        raise TypeError("controller state requires an authentic controller")
    if not _acquisition_mandate_is_authentic(mandate):
        raise TypeError("controller state requires an authentic mandate")
    if (
        controller.position_scope != mandate.position_scope
        or controller._binding_commitment != mandate.binding.commitment
        or controller._compatibility_commitment
        != mandate.protection_mandate.emergency_recovery_compatibility.commitment
    ):
        raise ValueError("controller does not match the retained dual mandate")
    commitment = _controller_state_commitment(controller, registry, lineage)
    result = object.__new__(AcquisitionControllerState)
    for name, value in (
        ("application_generation_id", controller.application_generation_id),
        ("position_scope", controller.position_scope),
        ("scope_execution_commitment", controller.scope_execution_commitment),
        ("venue_commitment", controller.venue_commitment),
        ("authority_context_commitment", controller.authority_context_commitment),
        ("protection_commitment", controller.protection_commitment),
        ("controller_commitment", controller.commitment),
        ("registry", registry),
        ("lineage", lineage),
        ("commitment", commitment),
        ("_controller", controller),
        ("_mandate", mandate),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-state-seal/v1", commitment
        ),
    )
    return result


def _controller_state_is_authentic(value: object) -> bool:
    if type(value) is not AcquisitionControllerState:
        return False
    try:
        controller = value._controller
        mandate = value._mandate
        commitment = _controller_state_commitment(
            controller,
            value.registry,
            value.lineage,
        )
        if not _acquisition_mandate_is_authentic(mandate):
            return False
        if (
            value.application_generation_id != controller.application_generation_id
            or value.position_scope != controller.position_scope
            or value.scope_execution_commitment != controller.scope_execution_commitment
            or value.venue_commitment != controller.venue_commitment
            or value.authority_context_commitment
            != controller.authority_context_commitment
            or value.protection_commitment != controller.protection_commitment
            or value.controller_commitment != controller.commitment
            or value.commitment != commitment
            or value._seal
            != _commit_parts(
                b"execution-core/acquisition/controller-state-seal/v1",
                commitment,
            )
            or controller.position_scope != mandate.position_scope
            or controller._binding_commitment != mandate.binding.commitment
            or controller._compatibility_commitment
            != mandate.protection_mandate.emergency_recovery_compatibility.commitment
        ):
            return False
        if controller.live_generation_id is None:
            return False
        record = value.registry.record(controller.live_generation_id)
        route = _registry_market_stream_route(
            value.registry,
            mandate.protection_mandate.evidence_policy.stream_generation,
        )
        return bool(
            controller.live_generation_id is not None
            and record is not None
            and route is not None
            and route.stream_generation
            == mandate.protection_mandate.evidence_policy.stream_generation
            and route.binding == record.binding
            and route.binding.application_generation_id
            == controller.application_generation_id
            and route.binding.position_scope == controller.position_scope
            and record.binding.dual_mandate_binding_commitment
            == controller._binding_commitment
            and record.binding.successor_ordinal == controller.successor_ordinal
        )
    except (AttributeError, TypeError, ValueError):
        return False


@_dataclass(frozen=True, slots=True, init=False)
class AcquisitionControllerStatus:
    """Bounded immutable read projection with no authority or action surface."""

    application_generation_id: _ApplicationGenerationId = _field(init=False)
    position_scope: _PositionScope = _field(init=False)
    controller_head: bytes = _field(init=False)
    successor_ordinal: int = _field(init=False)
    live_generation_id: _AcquisitionGenerationId | None = _field(init=False)
    recovery_class: AcquisitionRecoveryClass = _field(init=False)
    scope_execution_commitment: bytes = _field(init=False)
    venue_commitment: bytes = _field(init=False)
    authority_context_commitment: bytes = _field(init=False)
    protection_commitment: bytes | None = _field(init=False)
    controller_commitment: bytes = _field(init=False)
    commitment: bytes = _field(init=False)
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionControllerStatus is controller-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionControllerStatus cannot be subclassed")


def _new_acquisition_controller_status(
    state: AcquisitionControllerState,
) -> AcquisitionControllerStatus:
    if not _controller_state_is_authentic(state):
        raise ValueError("controller state authenticity check failed")
    controller = state._controller
    commitment = _commit_parts(
        b"execution-core/acquisition/controller-status/v1",
        state.commitment,
    )
    result = object.__new__(AcquisitionControllerStatus)
    for name, value in (
        ("application_generation_id", controller.application_generation_id),
        ("position_scope", controller.position_scope),
        ("controller_head", controller.controller_head),
        ("successor_ordinal", controller.successor_ordinal),
        ("live_generation_id", controller.live_generation_id),
        ("recovery_class", controller.recovery_class),
        ("scope_execution_commitment", controller.scope_execution_commitment),
        ("venue_commitment", controller.venue_commitment),
        ("authority_context_commitment", controller.authority_context_commitment),
        ("protection_commitment", controller.protection_commitment),
        ("controller_commitment", controller.commitment),
        ("commitment", commitment),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-status-seal/v1", commitment
        ),
    )
    return result


@_dataclass(frozen=True, slots=True, init=False)
class AcquisitionControllerTransition:
    """One sealed composite result from the acquisition controller reducer."""

    state: AcquisitionControllerState = _field(init=False)
    venue: _VenueRecoveryBook = _field(init=False)
    execution: _ExecutionSnapshot = _field(init=False)
    protection: _PositionProtectionState | None = _field(init=False)
    authority: _ExecutionAuthorityState = _field(init=False)
    disposition: AcquisitionControllerDisposition = _field(init=False)
    created_effect_id: _EffectId | None = _field(init=False)
    fresh_claim: _AcquisitionClaimReceipt | None = _field(init=False)
    _refresh: _AcquisitionContextRefresh | None = _field(init=False, repr=False)
    _registration_receipt: _AcquisitionAuthorityReceipt | None = _field(
        init=False,
        repr=False,
    )
    _seal: bytes = _field(init=False, repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise TypeError("AcquisitionControllerTransition is reducer-constructed only")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionControllerTransition cannot be subclassed")


def _new_initialization_transition(
    *,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    authority: _ExecutionAuthorityState,
    receipt: _AcquisitionAuthorityReceipt,
) -> AcquisitionControllerTransition:
    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(authority) is not _ExecutionAuthorityState
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or refresh.execution is None
        or refresh.authority is None
        or authority.venue is not refresh.authority.venue
        or receipt.operation is not _AcquisitionAuthorityOperation.REGISTER
        or receipt.application_generation_id != state.application_generation_id
        or receipt.position_scope != state.position_scope
        or receipt.controller_head != state._controller.controller_head
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
        or receipt.ordered_venue_transition_commitments != ()
    ):
        raise ValueError("initialization composite components do not exactly match")
    commitment = _commit_parts(
        b"execution-core/acquisition/controller-initialization-transition/v1",
        state.commitment,
        refresh.commitment,
        receipt.commitment,
    )
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", refresh.execution),
        ("protection", None),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-transition-seal/v1",
            commitment,
        ),
    )
    return result


def _new_refused_successor_transition(
    *,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
) -> AcquisitionControllerTransition:
    """Return the exact predecessor components after successor refusal."""

    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or refresh.authority is None
        or refresh.execution is None
    ):
        raise ValueError("refused acquisition successor has incompatible components")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", refresh.authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", refresh.authority),
        ("disposition", AcquisitionControllerDisposition.REFUSED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-refused-successor-transition/v1",
            state.commitment,
            refresh.commitment,
            b"" if protection is None else protection.commitment,
        ),
    )
    return result


def _new_applied_successor_transition(
    *,
    predecessor_state: AcquisitionControllerState,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    authority: _ExecutionAuthorityState,
    receipt: _AcquisitionAuthorityReceipt,
) -> AcquisitionControllerTransition:
    """Assemble one atomic serial-generation retirement and registration."""

    if (
        not _controller_state_is_authentic(predecessor_state)
        or not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(authority) is not _ExecutionAuthorityState
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or refresh.authority is None
        or refresh.execution is None
        or authority.venue is not refresh.authority.venue
        or receipt.operation is not _AcquisitionAuthorityOperation.REGISTER
        or predecessor_state.application_generation_id
        != state.application_generation_id
        or predecessor_state.position_scope != state.position_scope
        or predecessor_state._controller.successor_ordinal + 1
        != state._controller.successor_ordinal
        or predecessor_state._controller.live_generation_id
        == state._controller.live_generation_id
        or state.protection_commitment is not None
        or receipt.predecessor_controller_head
        != predecessor_state._controller.controller_head
        or receipt.controller_head != state._controller.controller_head
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
        or receipt.ordered_venue_transition_commitments != ()
    ):
        raise ValueError("successor composite components do not exactly match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", refresh.execution),
        ("protection", None),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-successor-transition/v1",
            predecessor_state.commitment,
            state.commitment,
            refresh.commitment,
            receipt.commitment,
        ),
    )
    return result


def _new_refused_create_transition(
    *,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
) -> AcquisitionControllerTransition:
    """Return the exact pre-state after a non-mutating create refusal."""

    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or refresh.authority is None
        or refresh.execution is None
        or (protection is not None and type(protection) is not _PositionProtectionState)
        or (state._controller.protection_commitment is None) != (protection is None)
    ):
        raise ValueError("refused acquisition create has incompatible components")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", refresh.authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", refresh.authority),
        ("disposition", AcquisitionControllerDisposition.REFUSED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-refused-create-transition/v1",
            state.commitment,
            refresh.commitment,
            b"" if protection is None else protection.commitment,
        ),
    )
    return result


def _new_refused_claim_transition(
    *,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
) -> AcquisitionControllerTransition:
    """Return the exact pre-state after a non-mutating final-claim refusal."""

    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or refresh.authority is None
        or refresh.execution is None
        or (protection is not None and type(protection) is not _PositionProtectionState)
        or (state._controller.protection_commitment is None) != (protection is None)
    ):
        raise ValueError("refused acquisition claim has incompatible components")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", refresh.authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", refresh.authority),
        ("disposition", AcquisitionControllerDisposition.REFUSED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-refused-claim-transition/v1",
            state.commitment,
            refresh.commitment,
            b"" if protection is None else protection.commitment,
        ),
    )
    return result


def _new_refused_preemption_transition(
    *,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState,
) -> AcquisitionControllerTransition:
    """Return the exact current composite after a preemption refusal."""

    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(protection) is not _PositionProtectionState
        or refresh.authority is None
        or refresh.execution is None
    ):
        raise ValueError("refused acquisition preemption has incompatible components")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", refresh.authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", refresh.authority),
        ("disposition", AcquisitionControllerDisposition.REFUSED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-refused-preemption/v1",
            state.commitment,
            refresh.commitment,
            protection.commitment,
        ),
    )
    return result


def _new_applied_preemption_transition(
    *,
    predecessor_state: AcquisitionControllerState,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState,
    authority: _ExecutionAuthorityState,
    receipt: _AcquisitionAuthorityReceipt,
    created_effect_id: _EffectId | None,
) -> AcquisitionControllerTransition:
    """Assemble one currentness advance and at most one bounded BUY cancel."""

    if (
        not _controller_state_is_authentic(predecessor_state)
        or not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(protection) is not _PositionProtectionState
        or type(authority) is not _ExecutionAuthorityState
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or (created_effect_id is not None and type(created_effect_id) is not _EffectId)
        or refresh.execution is None
        or receipt.operation is not _AcquisitionAuthorityOperation.PREEMPT
        or receipt.predecessor_controller_head
        != predecessor_state._controller.controller_head
        or receipt.controller_head != state._controller.controller_head
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
    ):
        raise ValueError("preemption composite components do not exactly match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", created_effect_id),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-preemption-transition/v1",
            predecessor_state.commitment,
            state.commitment,
            refresh.commitment,
            protection.commitment,
            receipt.commitment,
            b"" if created_effect_id is None else _encode_text(created_effect_id.value),
        ),
    )
    return result


def _new_refused_protection_exit_transition(
    *,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState,
    transition: _ProtectionTransition,
) -> AcquisitionControllerTransition:
    """Return the exact current composite after a protective-SELL refusal."""

    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(protection) is not _PositionProtectionState
        or type(transition) is not _ProtectionTransition
        or refresh.authority is None
        or refresh.execution is None
    ):
        raise ValueError("refused acquisition protection exit has invalid components")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", refresh.authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", refresh.authority),
        ("disposition", AcquisitionControllerDisposition.REFUSED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-refused-protection-exit/v1",
            state.commitment,
            refresh.commitment,
            protection.commitment,
            transition._seal,
        ),
    )
    return result


def _new_applied_protection_exit_transition(
    *,
    predecessor_state: AcquisitionControllerState,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState,
    source_transition: _ProtectionTransition,
    authority: _ExecutionAuthorityState,
    receipt: _AcquisitionAuthorityReceipt,
    created_effect_id: _EffectId,
) -> AcquisitionControllerTransition:
    """Assemble one controller/currentness advance and one protective SELL."""

    if (
        not _controller_state_is_authentic(predecessor_state)
        or not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(protection) is not _PositionProtectionState
        or type(source_transition) is not _ProtectionTransition
        or type(authority) is not _ExecutionAuthorityState
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or type(created_effect_id) is not _EffectId
        or refresh.execution is None
        or receipt.operation is not _AcquisitionAuthorityOperation.PROTECTION_EXIT
        or receipt.predecessor_controller_head
        != predecessor_state._controller.controller_head
        or receipt.controller_head != state._controller.controller_head
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
    ):
        raise ValueError("protection-exit composite components do not exactly match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", created_effect_id),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-protection-exit/v1",
            predecessor_state.commitment,
            state.commitment,
            refresh.commitment,
            source_transition._seal,
            protection.commitment,
            receipt.commitment,
            _encode_text(created_effect_id.value),
        ),
    )
    return result


def _new_refused_rebase_transition(
    *,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    source: _AcquisitionProtectionRebaseProjection | _PositionProtectionState,
) -> AcquisitionControllerTransition:
    """Echo one owner-produced candidate without making it controller current."""

    source_is_projection = type(source) is _AcquisitionProtectionRebaseProjection
    source_is_raw_state = type(source) is _PositionProtectionState
    protection = (
        source.resulting_state
        if type(source) is _AcquisitionProtectionRebaseProjection
        else source
    )
    authority = refresh.authority
    execution = refresh.execution
    if (
        source_is_raw_state
        and refresh.disposition is _AcquisitionContextRefreshDisposition.REFRESHED
        and refresh.predecessor_authority is not None
        and refresh.predecessor_execution is not None
    ):
        authority = refresh.predecessor_authority
        execution = refresh.predecessor_execution
    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or not (source_is_projection or source_is_raw_state)
        or type(protection) is not _PositionProtectionState
        or type(authority) is not _ExecutionAuthorityState
        or type(execution) is not _ExecutionSnapshot
    ):
        raise TypeError("refused acquisition rebase requires exact sealed components")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.REFUSED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", None),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-refused-protection-rebase/v1",
            state.commitment,
            refresh.commitment,
        ),
    )
    return result


def _new_applied_neutral_reprojection_transition(
    *,
    state: AcquisitionControllerState,
    predecessor_protection: _PositionProtectionState,
    projection: _AcquisitionProtectionRebaseProjection,
    current_context: _AcquisitionProtectionContext,
    refresh: _AcquisitionContextRefresh,
) -> AcquisitionControllerTransition:
    """Transport one fresh raw protection value without semantic mutation."""

    if (
        not _controller_state_is_authentic(state)
        or type(predecessor_protection) is not _PositionProtectionState
        or type(projection) is not _AcquisitionProtectionRebaseProjection
        or projection.kind is not _AcquisitionProtectionRebaseKind.NEUTRAL_REPROJECTION
        or type(projection.resulting_state) is not _PositionProtectionState
        or type(current_context) is not _AcquisitionProtectionContext
        or type(refresh) is not _AcquisitionContextRefresh
        or refresh.disposition is not _AcquisitionContextRefreshDisposition.REFRESHED
        or refresh.authority is None
        or refresh.execution is None
        or len(refresh.venue_transitions) != 1
        or state.protection_commitment is None
        or not projection.matches_neutral_reprojection(
            state.protection_commitment,
            current_context,
            refresh.venue_transitions[0]._protection_proof_commitment,
        )
    ):
        raise ValueError("neutral acquisition reprojection components do not match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", refresh.authority.venue),
        ("execution", refresh.execution),
        ("protection", projection.resulting_state),
        ("authority", refresh.authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-neutral-reprojection/v1",
            state.commitment,
            predecessor_protection.commitment,
            projection.source_commitment,
            refresh.commitment,
        ),
    )
    return result


def _new_applied_rebase_transition(
    *,
    predecessor_state: AcquisitionControllerState,
    state: AcquisitionControllerState,
    protection: _PositionProtectionState,
    authority: _ExecutionAuthorityState,
    refresh: _AcquisitionContextRefresh,
    receipt: _AcquisitionAuthorityReceipt,
) -> AcquisitionControllerTransition:
    """Assemble one registration-only semantic protection transition."""

    if (
        not _controller_state_is_authentic(predecessor_state)
        or not _controller_state_is_authentic(state)
        or type(protection) is not _PositionProtectionState
        or type(authority) is not _ExecutionAuthorityState
        or type(refresh) is not _AcquisitionContextRefresh
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or refresh.authority is not authority
        or refresh.execution is None
        or receipt.operation is not _AcquisitionAuthorityOperation.REGISTER
        or receipt.application_generation_id != state.application_generation_id
        or receipt.position_scope != state.position_scope
        or receipt.predecessor_controller_head
        != predecessor_state._controller.controller_head
        or receipt.controller_head != state._controller.controller_head
        or receipt.predecessor_scope_execution_commitment
        != predecessor_state.scope_execution_commitment
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.predecessor_venue_commitment != predecessor_state.venue_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
        or receipt.ordered_venue_transition_commitments != ()
        or authority.venue is not refresh.authority.venue
        or state.protection_commitment == predecessor_state.protection_commitment
    ):
        raise ValueError("applied acquisition rebase components do not exactly match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-protection-rebase-transition/v1",
            predecessor_state.commitment,
            state.commitment,
            refresh.commitment,
            receipt.commitment,
        ),
    )
    return result


def _new_created_effect_transition(
    *,
    predecessor_state: AcquisitionControllerState,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    authority: _ExecutionAuthorityState,
    receipt: _AcquisitionAuthorityReceipt,
    effect_id: _EffectId,
    protection: _PositionProtectionState | None,
) -> AcquisitionControllerTransition:
    """Assemble the authority receipt and replacement controller atomically."""

    if (
        not _controller_state_is_authentic(predecessor_state)
        or not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(authority) is not _ExecutionAuthorityState
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or type(effect_id) is not _EffectId
        or refresh.execution is None
        or receipt.operation is not _AcquisitionAuthorityOperation.CREATE
        or receipt.application_generation_id != state.application_generation_id
        or receipt.position_scope != state.position_scope
        or receipt.predecessor_controller_head
        != predecessor_state._controller.controller_head
        or receipt.controller_head != state._controller.controller_head
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
        or len(receipt.ordered_venue_transition_commitments) != 1
        or state._controller.protection_commitment is not None
        or protection is not None
    ):
        raise ValueError("created acquisition effect components do not exactly match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", effect_id),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-create-transition/v1",
            predecessor_state.commitment,
            state.commitment,
            refresh.commitment,
            receipt.commitment,
            effect_id.value.encode("utf-8"),
        ),
    )
    return result


def _new_claimed_effect_transition(
    *,
    predecessor_state: AcquisitionControllerState,
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    authority: _ExecutionAuthorityState,
    receipt: _AcquisitionAuthorityReceipt,
    claim_receipt: _AcquisitionClaimReceipt,
    effect_id: _EffectId,
    claim_occurrence_id: _ClaimOccurrenceId,
    protection: _PositionProtectionState | None,
) -> AcquisitionControllerTransition:
    """Assemble one exact specialized final-claim composite result."""

    if (
        not _controller_state_is_authentic(predecessor_state)
        or not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(authority) is not _ExecutionAuthorityState
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or type(claim_receipt) is not _AcquisitionClaimReceipt
        or type(effect_id) is not _EffectId
        or type(claim_occurrence_id) is not _ClaimOccurrenceId
        or refresh.execution is None
        or receipt.operation is not _AcquisitionAuthorityOperation.CLAIM
        or receipt.application_generation_id != state.application_generation_id
        or receipt.position_scope != state.position_scope
        or receipt.predecessor_controller_head
        != predecessor_state._controller.controller_head
        or receipt.controller_head != predecessor_state._controller.controller_head
        or receipt.controller_head != state._controller.controller_head
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
        or len(receipt.ordered_venue_transition_commitments) != 1
        or claim_receipt.controller_head != state._controller.controller_head
        or claim_receipt.effect_id != effect_id
        or claim_receipt.claim_occurrence_id != claim_occurrence_id
        or claim_receipt.scope_execution_commitment != state.scope_execution_commitment
        or claim_receipt.venue_commitment != state.venue_commitment
        or state._controller.protection_commitment is not None
        or protection is not None
    ):
        raise ValueError("claimed acquisition effect components do not exactly match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", refresh.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", None),
        ("fresh_claim", claim_receipt),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-claim-transition/v1",
            predecessor_state.commitment,
            state.commitment,
            refresh.commitment,
            receipt.commitment,
            claim_receipt.commitment,
        ),
    )
    return result


def _new_refused_fact_transition(
    *,
    state: AcquisitionControllerState,
    transition: _VenueRecoveryTransition,
    protection: _PositionProtectionState | None,
    authority: _ExecutionAuthorityState,
) -> AcquisitionControllerTransition:
    """Return the retained controller/authority after a fact-route refusal."""

    if (
        not _controller_state_is_authentic(state)
        or type(transition) is not _VenueRecoveryTransition
        or type(authority) is not _ExecutionAuthorityState
    ):
        raise TypeError("refused acquisition fact requires exact sealed components")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", transition.book),
        ("execution", transition.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.REFUSED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", None),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-refused-fact-transition/v1",
            state.commitment,
            transition._acquisition_fact_proof_commitment or b"",
        ),
    )
    return result


def _new_replayed_fact_transition(
    *,
    state: AcquisitionControllerState,
    transition: _VenueRecoveryTransition,
    protection: _PositionProtectionState,
    authority: _ExecutionAuthorityState,
    refresh: _AcquisitionContextRefresh,
) -> AcquisitionControllerTransition:
    """Return the exact retained post-fact controller without a second update."""

    if (
        not _controller_state_is_authentic(state)
        or type(transition) is not _VenueRecoveryTransition
        or type(protection) is not _PositionProtectionState
        or type(authority) is not _ExecutionAuthorityState
        or type(refresh) is not _AcquisitionContextRefresh
        or refresh.authority is not authority
        or refresh.execution is not transition.execution
        or state.protection_commitment is None
        or refresh.venue_context is None
        or refresh.authority_context is None
        or not refresh.matches_current(
            authority,
            state.application_generation_id,
            state.position_scope,
        )
    ):
        raise ValueError("replayed acquisition fact components do not exactly match")
    if (
        refresh.venue_context.scope_execution_commitment
        != state.scope_execution_commitment
        or refresh.venue_context.commitment != state.venue_commitment
        or refresh.authority_context.authority_commitment
        != state.authority_context_commitment
    ):
        raise ValueError("replayed acquisition fact is no longer current")
    protection_context = _project_acquisition_protection_context(
        protection,
        authority.venue,
        transition.execution,
        refresh.venue_context,
    )
    if (
        type(protection_context) is not _AcquisitionProtectionContext
        or protection_context.scope_protection_commitment != state.protection_commitment
    ):
        raise ValueError("replayed acquisition fact protection is no longer current")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", transition.book),
        ("execution", transition.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.EXACT_REPLAY),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", None),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-replayed-fact-transition/v1",
            state.commitment,
            refresh.commitment,
            transition._acquisition_fact_proof_commitment or b"",
        ),
    )
    return result


def _new_applied_fact_transition(
    *,
    predecessor_state: AcquisitionControllerState,
    state: AcquisitionControllerState,
    transition: _VenueRecoveryTransition,
    protection: _PositionProtectionState,
    protection_context: _AcquisitionProtectionContext,
    authority: _ExecutionAuthorityState,
    refresh: _AcquisitionContextRefresh,
    receipt: _AcquisitionAuthorityReceipt,
) -> AcquisitionControllerTransition:
    """Assemble one atomic first-root controller, authority, and protection step."""

    if (
        not _controller_state_is_authentic(predecessor_state)
        or not _controller_state_is_authentic(state)
        or type(transition) is not _VenueRecoveryTransition
        or type(protection) is not _PositionProtectionState
        or type(protection_context) is not _AcquisitionProtectionContext
        or type(authority) is not _ExecutionAuthorityState
        or type(refresh) is not _AcquisitionContextRefresh
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or receipt.operation is not _AcquisitionAuthorityOperation.REGISTER
        or authority.venue is not transition.book
        or refresh.authority is not authority
        or refresh.execution is not transition.execution
        or not refresh.matches_current(
            authority,
            state.application_generation_id,
            state.position_scope,
        )
        or predecessor_state.application_generation_id
        != state.application_generation_id
        or predecessor_state.position_scope != state.position_scope
        or receipt.application_generation_id != state.application_generation_id
        or receipt.position_scope != state.position_scope
        or receipt.predecessor_controller_head
        != predecessor_state._controller.controller_head
        or receipt.controller_head != state._controller.controller_head
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
        or len(receipt.ordered_venue_transition_commitments) != 1
        or transition._protection_proof_commitment
        != receipt.ordered_venue_transition_commitments[0]
        or state._controller.protection_commitment
        != protection_context.scope_protection_commitment
        or protection_context.scope_protection_commitment is None
        or protection_context.source_protection_commitment != protection.commitment
        or protection_context.application_generation_id
        != state.application_generation_id
        or protection_context.position_scope != state.position_scope
        or protection_context.scope_execution_commitment
        != state.scope_execution_commitment
    ):
        raise ValueError("applied acquisition fact components do not exactly match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", transition.book),
        ("execution", transition.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", None),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-applied-fact-transition/v1",
            predecessor_state.commitment,
            state.commitment,
            refresh.commitment,
            receipt.commitment,
            protection_context.commitment,
        ),
    )
    return result


def _new_applied_fact_preemption_transition(
    *,
    predecessor_state: AcquisitionControllerState,
    state: AcquisitionControllerState,
    transition: _VenueRecoveryTransition,
    protection: _PositionProtectionState,
    protection_context: _AcquisitionProtectionContext,
    authority: _ExecutionAuthorityState,
    refresh: _AcquisitionContextRefresh,
    receipt: _AcquisitionAuthorityReceipt,
    created_effect_id: _EffectId | None,
) -> AcquisitionControllerTransition:
    """Assemble one atomic retired-fact and current-BUY preemption result."""

    if (
        not _controller_state_is_authentic(predecessor_state)
        or not _controller_state_is_authentic(state)
        or type(transition) is not _VenueRecoveryTransition
        or type(protection) is not _PositionProtectionState
        or type(protection_context) is not _AcquisitionProtectionContext
        or type(authority) is not _ExecutionAuthorityState
        or type(refresh) is not _AcquisitionContextRefresh
        or type(receipt) is not _AcquisitionAuthorityReceipt
        or (created_effect_id is not None and type(created_effect_id) is not _EffectId)
        or receipt.operation is not _AcquisitionAuthorityOperation.PREEMPT
        or refresh.authority is not authority
        or refresh.execution is None
        or refresh.execution.commitment != transition.execution.commitment
        or refresh.venue_context is None
        or not refresh.matches_current(
            authority,
            state.application_generation_id,
            state.position_scope,
        )
        or predecessor_state.application_generation_id
        != state.application_generation_id
        or predecessor_state.position_scope != state.position_scope
        or receipt.application_generation_id != state.application_generation_id
        or receipt.position_scope != state.position_scope
        or receipt.predecessor_controller_head
        != predecessor_state._controller.controller_head
        or receipt.controller_head != state._controller.controller_head
        or receipt.scope_execution_commitment != state.scope_execution_commitment
        or receipt.venue_commitment != state.venue_commitment
        or receipt.authority_commitment != state.authority_context_commitment
        or len(receipt.ordered_venue_transition_commitments) not in {1, 2, 3}
        or transition._protection_proof_commitment
        != receipt.ordered_venue_transition_commitments[0]
        or state.protection_commitment != protection_context.scope_protection_commitment
        or protection_context.source_protection_commitment != protection.commitment
        or protection_context.scope_execution_commitment
        != state.scope_execution_commitment
        or not protection_context.matches_current(
            authority.venue,
            refresh.execution,
            refresh.venue_context,
            protection,
        )
    ):
        raise ValueError("fact-preemption components do not exactly match")
    result = object.__new__(AcquisitionControllerTransition)
    for name, value in (
        ("state", state),
        ("venue", authority.venue),
        ("execution", transition.execution),
        ("protection", protection),
        ("authority", authority),
        ("disposition", AcquisitionControllerDisposition.APPLIED),
        ("created_effect_id", created_effect_id),
        ("fresh_claim", None),
        ("_refresh", refresh),
        ("_registration_receipt", receipt),
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(
        result,
        "_seal",
        _commit_parts(
            b"execution-core/acquisition/controller-fact-preemption-transition/v1",
            predecessor_state.commitment,
            state.commitment,
            refresh.commitment,
            receipt.commitment,
            protection_context.commitment,
            b""
            if created_effect_id is None
            else created_effect_id.value.encode("utf-8"),
        ),
    )
    return result


def _r8_unbound_initialization_inputs_are_exact(
    application_generation_id: _ApplicationGenerationId,
    mandate: AcquisitionMandate,
    bootstrap: _AcquisitionVenueProjection,
    admission: _AcquisitionAdmissionProjection,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
) -> bool:
    """Check the entire public R8 UB handoff before deriving any state."""

    if (
        type(application_generation_id) is not _ApplicationGenerationId
        or not _acquisition_mandate_is_authentic(mandate)
        or type(bootstrap) is not _AcquisitionVenueProjection
        or type(admission) is not _AcquisitionAdmissionProjection
        or type(refresh) is not _AcquisitionContextRefresh
        or protection is not None
        or refresh.disposition
        is not _AcquisitionContextRefreshDisposition.UNBOUND_BOOTSTRAP
        or refresh.authority is None
        or refresh.execution is None
        or refresh.venue_context is None
        or refresh.authority_context is None
        or refresh.predecessor_authority is None
        or refresh.predecessor_execution is not None
        or refresh.predecessor_venue_context is not None
        or refresh.predecessor_authority_context is not None
        or refresh.authority is refresh.predecessor_authority
        or refresh.authority.session_id != mandate.session_id
        or len(refresh.venue_transitions) != 1
        or len(refresh.ordered_venue_transition_commitments) != 1
    ):
        return False
    scope = mandate.position_scope
    transition = refresh.venue_transitions[0]
    if (
        type(transition) is not _VenueRecoveryTransition
        or transition.disposition is not _VenueRecoveryDisposition.APPLIED
        or transition.quantity_delta != 0
        or transition.book is not refresh.authority.venue
        or transition.execution is not refresh.execution
        or not refresh.matches_current(
            refresh.authority, application_generation_id, scope
        )
        or bootstrap.application_generation_id != application_generation_id
        or bootstrap.position_scope != scope
        or not bootstrap.matches_bootstrap(
            refresh.execution, refresh.authority.venue, scope
        )
        or admission.application_generation_id != application_generation_id
        or admission.position_scope != scope
        or admission.kind is not _AcquisitionAdmissionKind.GENESIS_EMPTY
        or not admission.permits_genesis(
            application_generation_id, refresh.execution, scope
        )
    ):
        return False
    return bool(
        bootstrap.execution_snapshot_commitment == refresh.execution.commitment
        and bootstrap.scope_execution_commitment
        == refresh.venue_context.scope_execution_commitment
        and bootstrap.venue_commitment == refresh.venue_context.commitment
        and admission.scope_execution_commitment
        == refresh.venue_context.scope_execution_commitment
        and admission.venue_commitment == refresh.venue_context.commitment
        and admission.authority_commitment
        == refresh.authority_context.authority_commitment
        and refresh.authority_context.application_generation_id
        == application_generation_id
        and refresh.authority_context.position_scope == scope
        and refresh.authority_context.scope_execution_commitment
        == refresh.venue_context.scope_execution_commitment
        and refresh.authority_context.venue_commitment
        == refresh.venue_context.commitment
    )


def initialize_acquisition_controller(
    application_generation_id: _ApplicationGenerationId,
    mandate: AcquisitionMandate,
    bootstrap: _AcquisitionVenueProjection,
    admission: _AcquisitionAdmissionProjection,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
) -> AcquisitionControllerTransition:
    """Atomically install ordinal-zero currentness from the exact R8 handoff.

    The API intentionally has no refusal result that could manufacture a
    candidate controller state.  Any malformed, stale, or non-serving handoff
    raises before mutation; the caller retains its original values unchanged.
    """

    if not _r8_unbound_initialization_inputs_are_exact(
        application_generation_id,
        mandate,
        bootstrap,
        admission,
        refresh,
        protection,
    ):
        raise ValueError("R8 unbound bootstrap initialization inputs are not exact")
    authority = refresh.authority
    execution = refresh.execution
    if authority is None or execution is None or authority.session_id is None:
        raise ValueError("R8 unbound bootstrap handoff has no serving authority pair")
    scope = mandate.position_scope
    controller_head = _acquisition_controller_genesis_head(
        application_generation_id,
        scope,
    )
    generation_id = _derive_acquisition_generation_id(
        application_generation_id,
        scope,
        0,
        mandate.binding.commitment,
        controller_head,
        mandate.protection_mandate.emergency_recovery_compatibility.commitment,
    )
    registration = _apply_acquisition_bootstrap_initialization(
        authority,
        execution,
        application_generation_id=application_generation_id,
        position_scope=scope,
        session_id=mandate.session_id,
        generation_id=generation_id,
        acquisition_mandate_id=mandate.acquisition_mandate_id,
        protection_mandate_id=mandate.protection_mandate.mandate_id,
        binding_commitment=mandate.binding.commitment,
        emergency_recovery_compatibility_commitment=(
            mandate.protection_mandate.emergency_recovery_compatibility.commitment
        ),
        controller_head=controller_head,
        refresh=refresh,
        bootstrap=bootstrap,
        admission=admission,
    )
    receipt = registration.acquisition_receipt
    if (
        registration.disposition is not _AuthorityDisposition.APPLIED
        or type(registration.state) is not _ExecutionAuthorityState
        or receipt is None
        or registration.acquisition_claim_receipt is not None
        or registration.created_effect_ids != ()
        or registration.venue_transitions != ()
    ):
        raise ValueError("R8 bootstrap registration did not apply exactly")
    binding = _new_generation_binding_view(
        generation_id=generation_id,
        application_generation_id=application_generation_id,
        position_scope=scope,
        successor_ordinal=0,
        dual_mandate_binding_commitment=mandate.binding.commitment,
        predecessor_or_genesis_head_commitment=controller_head,
        emergency_recovery_compatibility_commitment=(
            mandate.protection_mandate.emergency_recovery_compatibility.commitment
        ),
    )
    record = _new_generation_record_view(
        binding=binding,
        economics_head_commitment=_initial_generation_economics_head(binding),
        serving_class=GenerationServingClass.LIVE,
        closure_summary_commitment=_initial_generation_closure_summary(binding),
    )
    registry = _registry_with_initial_record(
        record,
        mandate.protection_mandate.evidence_policy.stream_generation,
    )
    controller = _new_symbol_acquisition_controller(
        application_generation_id=application_generation_id,
        position_scope=scope,
        controller_head=controller_head,
        successor_ordinal=0,
        live_generation_id=generation_id,
        recovery_class=AcquisitionRecoveryClass.NORMAL,
        scope_execution_commitment=receipt.scope_execution_commitment,
        venue_commitment=receipt.venue_commitment,
        authority_context_commitment=receipt.authority_commitment,
        protection_commitment=None,
        binding_commitment=mandate.binding.commitment,
        compatibility_commitment=(
            mandate.protection_mandate.emergency_recovery_compatibility.commitment
        ),
    )
    state = _new_acquisition_controller_state(
        controller=controller,
        mandate=mandate,
        registry=registry,
        lineage=AcquisitionLineageIndex.empty(),
    )
    return _new_initialization_transition(
        state=state,
        refresh=refresh,
        authority=registration.state,
        receipt=receipt,
    )


def project_acquisition_controller(
    state: AcquisitionControllerState,
) -> AcquisitionControllerStatus:
    """Return the bounded immutable status projection for one controller."""

    if type(state) is not AcquisitionControllerState:
        raise TypeError("state must be AcquisitionControllerState")
    return _new_acquisition_controller_status(state)


def _semantic_rebase_source_is_exact(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    projection: _AcquisitionProtectionRebaseProjection,
) -> bool:
    """Require every protection-, venue-, and authority-owned semantic fence."""

    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or type(projection) is not _AcquisitionProtectionRebaseProjection
        or refresh.disposition is not _AcquisitionContextRefreshDisposition.CURRENT
        or refresh.authority is None
        or refresh.execution is None
        or refresh.venue_context is None
        or refresh.authority_context is None
        or state._controller.live_generation_id is None
        or state.protection_commitment is None
        or type(projection.resulting_state) is not _PositionProtectionState
        or projection.kind is not _AcquisitionProtectionRebaseKind.SEMANTIC_REBASE
        or projection.application_generation_id != state.application_generation_id
        or projection.position_scope != state.position_scope
        or refresh.application_generation_id != state.application_generation_id
        or refresh.position_scope != state.position_scope
        or refresh.execution.position.scope != state.position_scope
        or refresh.authority.session_id != state._mandate.session_id
        or not refresh.matches_current(
            refresh.authority,
            state.application_generation_id,
            state.position_scope,
        )
        or refresh.venue_context.scope_execution_commitment
        != state.scope_execution_commitment
        or refresh.venue_context.commitment != state.venue_commitment
        or refresh.authority_context.authority_commitment
        != state.authority_context_commitment
        or projection.predecessor_execution_snapshot_commitment
        != refresh.execution.commitment
        or projection.execution_snapshot_commitment != refresh.execution.commitment
        or projection.predecessor_scope_execution_commitment
        != state.scope_execution_commitment
        or projection.scope_execution_commitment != state.scope_execution_commitment
        or projection.predecessor_scope_execution_commitment
        != refresh.venue_context.scope_execution_commitment
        or projection.scope_execution_commitment
        != refresh.venue_context.scope_execution_commitment
        or projection.predecessor_venue_commitment != state.venue_commitment
        or projection.venue_commitment != state.venue_commitment
        or projection.predecessor_venue_commitment != refresh.venue_context.commitment
        or projection.venue_commitment != refresh.venue_context.commitment
    ):
        return False
    current_context = _project_acquisition_protection_context(
        projection.resulting_state,
        refresh.authority.venue,
        refresh.execution,
        refresh.venue_context,
    )
    return bool(
        type(current_context) is _AcquisitionProtectionContext
        and current_context.matches_current(
            refresh.authority.venue,
            refresh.execution,
            refresh.venue_context,
            projection.resulting_state,
        )
        and current_context.scope_protection_commitment is not None
        and current_context.scope_protection_commitment != state.protection_commitment
        and current_context.commitment == projection.context_commitment
        and current_context.source_protection_commitment
        == projection.source_protection_commitment
    )


def _neutral_reprojection_source_is_exact(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
) -> bool:
    """Authenticate the complete R7 predecessor/current authority pair."""

    predecessor_authority = refresh.predecessor_authority
    predecessor_execution = refresh.predecessor_execution
    predecessor_venue_context = refresh.predecessor_venue_context
    predecessor_authority_context = refresh.predecessor_authority_context
    authority = refresh.authority
    execution = refresh.execution
    venue_context = refresh.venue_context
    authority_context = refresh.authority_context
    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or refresh.disposition is not _AcquisitionContextRefreshDisposition.REFRESHED
        or type(predecessor_authority) is not _ExecutionAuthorityState
        or type(predecessor_execution) is not _ExecutionSnapshot
        or predecessor_venue_context is None
        or predecessor_authority_context is None
        or type(authority) is not _ExecutionAuthorityState
        or type(execution) is not _ExecutionSnapshot
        or venue_context is None
        or authority_context is None
        or len(refresh.venue_transitions) != 1
        or refresh.application_generation_id != state.application_generation_id
        or refresh.position_scope != state.position_scope
        or predecessor_execution.position.scope != state.position_scope
        or execution.position.scope != state.position_scope
        or state.protection_commitment is None
        or state._controller.live_generation_id is None
        or not refresh.matches_current(
            authority,
            state.application_generation_id,
            state.position_scope,
        )
        or not predecessor_authority_context.matches_current(
            predecessor_authority,
            predecessor_execution,
            predecessor_venue_context,
        )
        or not authority_context.matches_current(
            authority,
            execution,
            venue_context,
        )
        or state.scope_execution_commitment
        != predecessor_venue_context.scope_execution_commitment
        or state.scope_execution_commitment != venue_context.scope_execution_commitment
        or state.venue_commitment != predecessor_venue_context.commitment
        or state.venue_commitment != venue_context.commitment
        or state.authority_context_commitment
        != predecessor_authority_context.authority_commitment
        or predecessor_authority_context.commitment != authority_context.commitment
        or predecessor_authority_context.authority_commitment
        != authority_context.authority_commitment
        or refresh.predecessor_scope_execution_commitment
        != state.scope_execution_commitment
        or refresh.scope_execution_commitment != state.scope_execution_commitment
        or refresh.predecessor_venue_commitment != state.venue_commitment
        or refresh.venue_commitment != state.venue_commitment
        or refresh.predecessor_authority_commitment
        != predecessor_authority_context.authority_commitment
        or refresh.authority_commitment != authority_context.authority_commitment
        or refresh.venue_transitions[0].book is not authority.venue
        or refresh.venue_transitions[0].execution is not execution
        or refresh.venue_transitions[0].disposition
        is not _VenueRecoveryDisposition.APPLIED
        or refresh.venue_transitions[0].quantity_delta != 0
    ):
        return False
    return True


def _ordinary_create_source_is_exact(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
) -> bool:
    """Require the ordinary post-bootstrap handoff before the first BUY."""

    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or refresh.disposition
        not in {
            _AcquisitionContextRefreshDisposition.CURRENT,
            _AcquisitionContextRefreshDisposition.REFRESHED,
        }
        or refresh.authority is None
        or refresh.execution is None
        or refresh.venue_context is None
        or refresh.authority_context is None
        or state._controller.protection_commitment is not None
        or protection is not None
        or refresh.application_generation_id != state.application_generation_id
        or refresh.position_scope != state.position_scope
        or refresh.execution.position.scope != state.position_scope
        or refresh.authority.session_id != state._mandate.session_id
    ):
        return False
    if not refresh.matches_current(
        refresh.authority,
        state.application_generation_id,
        state.position_scope,
    ):
        return False
    if (
        refresh.venue_context.scope_execution_commitment
        == state.scope_execution_commitment
        and refresh.venue_context.commitment == state.venue_commitment
        and refresh.authority_context.authority_commitment
        == state.authority_context_commitment
    ):
        return True
    # The authority-owned permit mint is the only place that may decide whether
    # a displaced R8 bootstrap checkpoint is the sealed continuation.  This
    # composition layer deliberately carries no duplicate private authority
    # predicate; the mint refuses every non-exact continuation before mutation.
    return True


def _ordinary_claim_source_is_exact(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
) -> bool:
    """Require the exact post-create current pair before final claim."""

    if (
        not _controller_state_is_authentic(state)
        or type(refresh) is not _AcquisitionContextRefresh
        or refresh.disposition
        not in {
            _AcquisitionContextRefreshDisposition.CURRENT,
            _AcquisitionContextRefreshDisposition.REFRESHED,
        }
        or refresh.authority is None
        or refresh.execution is None
        or refresh.venue_context is None
        or refresh.authority_context is None
        or state._controller.protection_commitment is not None
        or protection is not None
        or refresh.application_generation_id != state.application_generation_id
        or refresh.position_scope != state.position_scope
        or refresh.execution.position.scope != state.position_scope
        or refresh.authority.session_id != state._mandate.session_id
        or not refresh.matches_current(
            refresh.authority,
            state.application_generation_id,
            state.position_scope,
        )
    ):
        return False
    return bool(
        refresh.venue_context.scope_execution_commitment
        == state.scope_execution_commitment
        and refresh.venue_context.commitment == state.venue_commitment
        and refresh.authority_context.authority_commitment
        == state.authority_context_commitment
    )


def _terms_are_within_acquisition_mandate(
    mandate: AcquisitionMandate,
    terms: AcquisitionEffectTerms,
) -> bool:
    if (
        not _acquisition_mandate_is_authentic(mandate)
        or type(terms) is not AcquisitionEffectTerms
    ):
        return False
    if (
        terms.order_type not in mandate.allowed_order_types
        or terms.quantity.value > mandate.fixed_child_cap.value
        or terms.quantity.value > mandate.maximum_quantity.value
        or terms.limit_price.exact_value > mandate.maximum_entry_price.exact_value
        or terms.evaluation_time > mandate.expiry
        or terms.evaluation_time > mandate.deadline
    ):
        return False
    return bool(
        terms.quantity.value * terms.limit_price.exact_value <= mandate.maximum_notional
    )


def _controller_head_after_create(
    state: AcquisitionControllerState,
    terms: AcquisitionEffectTerms,
    input_id: _AuthorityInputId,
) -> bytes:
    if (
        not _controller_state_is_authentic(state)
        or type(terms) is not AcquisitionEffectTerms
        or type(input_id) is not _AuthorityInputId
    ):
        raise TypeError("create head requires exact sealed controller inputs")
    return _commit_parts(
        b"execution-core/acquisition/controller-head/create/v1",
        state._controller.controller_head,
        state.commitment,
        terms.commitment,
        _encode_text(input_id.value),
    )


def _controller_head_after_successor(
    state: AcquisitionControllerState,
    generation_id: _AcquisitionGenerationId,
    successor_mandate: AcquisitionMandate,
    bootstrap: _AcquisitionVenueProjection,
    admission: _AcquisitionAdmissionProjection,
) -> bytes:
    """Advance once from one exact terminal predecessor and successor binding."""

    if (
        not _controller_state_is_authentic(state)
        or not _acquisition_generation_id_is_canonical(generation_id)
        or not _acquisition_mandate_is_authentic(successor_mandate)
        or type(bootstrap) is not _AcquisitionVenueProjection
        or type(admission) is not _AcquisitionAdmissionProjection
        or successor_mandate.position_scope != state.position_scope
        or admission.position_scope != state.position_scope
        or bootstrap.position_scope != state.position_scope
    ):
        raise TypeError("successor head requires exact sealed components")
    return _commit_parts(
        b"execution-core/acquisition/controller-head/successor/v1",
        state._controller.controller_head,
        state.commitment,
        _encode_text(generation_id.value),
        successor_mandate.binding.commitment,
        bootstrap.source_commitment,
        admission.source_commitment,
    )


def _controller_head_after_preemption(
    state: AcquisitionControllerState,
    input_id: _AuthorityInputId,
    intent_commitment: bytes,
) -> bytes:
    """Advance once from one protection-owned cancel-only requirement."""

    if (
        not _controller_state_is_authentic(state)
        or type(input_id) is not _AuthorityInputId
        or type(intent_commitment) is not bytes
        or len(intent_commitment) != 32
    ):
        raise TypeError("preemption head requires exact sealed components")
    return _commit_parts(
        b"execution-core/acquisition/controller-head/preempt/v1",
        state._controller.controller_head,
        state.commitment,
        _encode_text(input_id.value),
        intent_commitment,
    )


def _controller_head_after_protection_exit(
    state: AcquisitionControllerState,
    input_id: _AuthorityInputId,
    intent_commitment: bytes,
    transition_commitment: bytes,
) -> bytes:
    """Advance once from one protection-owned, goal-bearing SELL relation."""

    if (
        not _controller_state_is_authentic(state)
        or type(input_id) is not _AuthorityInputId
        or type(intent_commitment) is not bytes
        or len(intent_commitment) != 32
        or type(transition_commitment) is not bytes
        or len(transition_commitment) != 32
    ):
        raise TypeError("protection-exit head requires exact sealed components")
    return _commit_parts(
        b"execution-core/acquisition/controller-head/protection-exit/v1",
        state._controller.controller_head,
        state.commitment,
        _encode_text(input_id.value),
        intent_commitment,
        transition_commitment,
    )


def _controller_head_after_fact(
    state: AcquisitionControllerState,
    projection: _AcquisitionVenueProjection,
    relation: _AcquisitionFactRelation,
) -> bytes:
    """Advance the controller exactly once from one sealed canonical fact."""

    if (
        not _controller_state_is_authentic(state)
        or type(projection) is not _AcquisitionVenueProjection
        or type(relation) is not _AcquisitionFactRelation
        or relation.application_generation_id != state.application_generation_id
        or relation.position_scope != state.position_scope
        or projection.application_generation_id != state.application_generation_id
        or projection.position_scope != state.position_scope
    ):
        raise TypeError("canonical fact head requires exact sealed components")
    return _commit_parts(
        b"execution-core/acquisition/controller-head/fact/v1",
        state._controller.controller_head,
        state.commitment,
        projection.source_commitment,
        relation.source_commitment,
        projection.scope_execution_commitment,
    )


def _controller_head_after_protection_rebase(
    state: AcquisitionControllerState,
    projection: _AcquisitionProtectionRebaseProjection,
) -> bytes:
    """Advance once from the sealed protection-owned semantic relation."""

    if (
        not _controller_state_is_authentic(state)
        or type(projection) is not _AcquisitionProtectionRebaseProjection
        or projection.kind is not _AcquisitionProtectionRebaseKind.SEMANTIC_REBASE
        or projection.application_generation_id != state.application_generation_id
        or projection.position_scope != state.position_scope
        or state.protection_commitment is None
    ):
        raise TypeError("protection rebase head requires one exact semantic relation")
    return _commit_parts(
        b"execution-core/acquisition/controller-head/protection-rebase/v1",
        state._controller.controller_head,
        state.commitment,
        projection.source_commitment,
        projection.context_commitment,
    )


def _generation_economics_head_after_fact(
    record: GenerationRecordView,
    projection: _AcquisitionVenueProjection,
    relation: _AcquisitionFactRelation,
) -> bytes:
    """Advance one generation-local economic coordinate from a direct fact."""

    if (
        not _generation_record_is_authentic(record)
        or type(projection) is not _AcquisitionVenueProjection
        or type(relation) is not _AcquisitionFactRelation
        or relation.application_generation_id
        != record.binding.application_generation_id
        or relation.position_scope != record.binding.position_scope
    ):
        raise TypeError("generation economics requires exact sealed fact inputs")
    return _commit_parts(
        b"execution-core/acquisition/generation-economics/fact/v1",
        record.economics_head_commitment,
        projection.source_commitment,
        relation.source_commitment,
        projection.scope_execution_commitment,
    )


def _first_current_generation_fact_is_exact(
    state: AcquisitionControllerState,
    transition: _VenueRecoveryTransition,
    protection: _PositionProtectionState | None,
) -> bool:
    """Fence the first normal root before it reaches the authority-owned mint."""

    if (
        not _controller_state_is_authentic(state)
        or type(transition) is not _VenueRecoveryTransition
        or protection is not None
        or state._controller.protection_commitment is not None
        or state._controller.recovery_class is not AcquisitionRecoveryClass.NORMAL
        or state._controller.live_generation_id is None
        or transition.disposition is not _VenueRecoveryDisposition.APPLIED
        or transition.quantity_delta <= 0
        or transition.execution.position.raw_quantity <= 0
    ):
        return False
    projection = transition.book.project_acquisition_fact(transition)
    relation = projection.fact_relation()
    generation_id = state._controller.live_generation_id
    if (
        projection.source_kind
        is not _AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT
        or relation is None
        or not projection.matches_fact_transition(transition, state.position_scope)
        or projection.application_generation_id != state.application_generation_id
        or projection.position_scope != state.position_scope
        or projection.predecessor_scope_execution_commitment
        != state.scope_execution_commitment
        or projection.predecessor_execution_snapshot_commitment is None
        or projection.predecessor_venue_commitment is None
        or projection.execution_snapshot_commitment != transition.execution.commitment
        or relation.application_generation_id != state.application_generation_id
        or relation.position_scope != state.position_scope
    ):
        return False
    record = state.registry.record(generation_id)
    request_route = state.lineage.route_request(relation.request_occurrence_id)
    effect_route = state.lineage.route_effect(relation.effect_id)
    return bool(
        record is not None
        and record.binding.generation_id == generation_id
        and record.serving_class is GenerationServingClass.LIVE
        and request_route is not None
        and request_route.generation_id == generation_id
        and effect_route is not None
        and effect_route.generation_id == generation_id
        and state.lineage.route_owner(relation.leg_key) is None
        and state.lineage.route_root(relation.root_key) is None
        and state.lineage.route_fact(relation.fact_key) is None
    )


def begin_acquisition_generation(
    state: AcquisitionControllerState,
    successor_mandate: AcquisitionMandate,
    bootstrap: _AcquisitionVenueProjection,
    admission: _AcquisitionAdmissionProjection,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
) -> AcquisitionControllerTransition:
    _require_exact("state", state, AcquisitionControllerState)
    _require_exact("successor_mandate", successor_mandate, AcquisitionMandate)
    _require_exact("bootstrap", bootstrap, _AcquisitionVenueProjection)
    _require_exact("admission", admission, _AcquisitionAdmissionProjection)
    _require_exact("refresh", refresh, _AcquisitionContextRefresh)
    if protection is not None:
        _require_exact("protection", protection, _PositionProtectionState)
    if refresh.authority is None or refresh.execution is None:
        raise ValueError("successor acquisition requires one complete authority pair")
    controller = state._controller
    prior_mandate = state._mandate
    current_generation_id = controller.live_generation_id
    retained_record = (
        None
        if current_generation_id is None
        else state.registry.record(current_generation_id)
    )
    current_record = (
        retained_record if type(retained_record) is GenerationRecordView else None
    )
    protection_context = (
        None
        if protection is None or refresh.venue_context is None
        else _project_acquisition_protection_context(
            protection,
            refresh.authority.venue,
            refresh.execution,
            refresh.venue_context,
        )
    )
    aborted = bool(
        state.protection_commitment is None
        and controller.protection_commitment is None
        and protection is None
    )
    completed = bool(
        state.protection_commitment is not None
        and type(protection) is _PositionProtectionState
        and protection.policy is _ProtectionPolicy.FLAT
        and protection.raw_quantity == 0
        and type(protection_context) is _AcquisitionProtectionContext
        and protection_context.scope_protection_commitment is not None
        and protection.mandate == prior_mandate.protection_mandate
    )
    sources_are_exact = bool(
        _controller_state_is_authentic(state)
        and _acquisition_mandate_is_authentic(successor_mandate)
        and controller.recovery_class is AcquisitionRecoveryClass.NORMAL
        and current_generation_id is not None
        and current_record is not None
        and _generation_record_is_authentic(current_record)
        and current_record.serving_class is GenerationServingClass.LIVE
        and current_record.binding.generation_id == current_generation_id
        and current_record.binding.successor_ordinal == controller.successor_ordinal
        and current_record.binding.dual_mandate_binding_commitment
        == prior_mandate.binding.commitment
        and refresh.disposition is _AcquisitionContextRefreshDisposition.CURRENT
        and refresh.matches_current(
            refresh.authority,
            state.application_generation_id,
            state.position_scope,
        )
        and refresh.venue_context is not None
        and refresh.authority_context is not None
        and (
            (
                aborted
                and refresh.venue_context.scope_execution_commitment
                == state.scope_execution_commitment
                and refresh.venue_context.commitment == state.venue_commitment
                and refresh.authority_context.authority_commitment
                == state.authority_context_commitment
            )
            or completed
        )
        and refresh.venue_transitions == ()
        and refresh.ordered_venue_transition_commitments == ()
        and bootstrap.application_generation_id == state.application_generation_id
        and bootstrap.position_scope == state.position_scope
        and bootstrap.matches_bootstrap(
            refresh.execution,
            refresh.authority.venue,
            state.position_scope,
        )
        and bootstrap.scope_execution_commitment
        == refresh.venue_context.scope_execution_commitment
        and bootstrap.venue_commitment == refresh.venue_context.commitment
        and admission.application_generation_id == state.application_generation_id
        and admission.position_scope == state.position_scope
        and admission.kind is _AcquisitionAdmissionKind.SUCCESSOR
        and admission.permits_successor(
            state.application_generation_id,
            refresh.execution,
            state.position_scope,
        )
        and admission.scope_execution_commitment
        == refresh.venue_context.scope_execution_commitment
        and admission.venue_commitment == refresh.venue_context.commitment
        and admission.authority_commitment
        == refresh.authority_context.authority_commitment
        and successor_mandate.position_scope == state.position_scope
        and successor_mandate.session_id == prior_mandate.session_id
        and successor_mandate.acquisition_mandate_id
        != prior_mandate.acquisition_mandate_id
        and successor_mandate.protection_mandate.mandate_id
        != prior_mandate.protection_mandate.mandate_id
        and successor_mandate.binding.commitment != prior_mandate.binding.commitment
        and successor_mandate.protection_mandate.evidence_policy.stream_generation
        != prior_mandate.protection_mandate.evidence_policy.stream_generation
        and successor_mandate.protection_mandate.emergency_recovery_compatibility.commitment
        == controller._compatibility_commitment
        and controller.successor_ordinal < _MAX_SUCCESSOR_ORDINAL
        and (aborted or completed)
    )
    if not sources_are_exact:
        return _new_refused_successor_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    assert current_record is not None
    candidate_stream_generation = (
        successor_mandate.protection_mandate.evidence_policy.stream_generation
    )
    try:
        candidate_stream_route = _registry_market_stream_route(
            state.registry,
            candidate_stream_generation,
        )
    except ValueError:
        return _new_refused_successor_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    if candidate_stream_route is not None:
        return _new_refused_successor_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    successor_ordinal = controller.successor_ordinal + 1
    successor_generation_id = _derive_acquisition_generation_id(
        state.application_generation_id,
        state.position_scope,
        successor_ordinal,
        successor_mandate.binding.commitment,
        controller.controller_head,
        controller._compatibility_commitment,
    )
    successor_head = _controller_head_after_successor(
        state,
        successor_generation_id,
        successor_mandate,
        bootstrap,
        admission,
    )
    registration = _apply_acquisition_successor_registration(
        refresh.authority,
        refresh.execution,
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        session_id=successor_mandate.session_id,
        generation_id=successor_generation_id,
        acquisition_mandate_id=successor_mandate.acquisition_mandate_id,
        protection_mandate_id=successor_mandate.protection_mandate.mandate_id,
        binding_commitment=successor_mandate.binding.commitment,
        emergency_recovery_compatibility_commitment=(
            controller._compatibility_commitment
        ),
        controller_head=successor_head,
        successor_ordinal=successor_ordinal,
        refresh=refresh,
        bootstrap=bootstrap,
        admission=admission,
    )
    receipt = registration.acquisition_receipt
    if (
        registration.disposition is not _AuthorityDisposition.APPLIED
        or type(registration.state) is not _ExecutionAuthorityState
        or receipt is None
        or registration.acquisition_claim_receipt is not None
        or registration.created_effect_ids != ()
        or registration.venue_transitions != ()
    ):
        return _new_refused_successor_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    successor_binding = _new_generation_binding_view(
        generation_id=successor_generation_id,
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        successor_ordinal=successor_ordinal,
        dual_mandate_binding_commitment=successor_mandate.binding.commitment,
        predecessor_or_genesis_head_commitment=controller.controller_head,
        emergency_recovery_compatibility_commitment=(
            controller._compatibility_commitment
        ),
    )
    retired_record = _new_generation_record_view(
        binding=current_record.binding,
        economics_head_commitment=current_record.economics_head_commitment,
        serving_class=GenerationServingClass.RETIRED_UNSERVING,
        closure_summary_commitment=_retired_generation_closure_summary(
            current_record,
            successor_binding,
        ),
    )
    successor_record = _new_generation_record_view(
        binding=successor_binding,
        economics_head_commitment=_initial_generation_economics_head(successor_binding),
        serving_class=GenerationServingClass.LIVE,
        closure_summary_commitment=_initial_generation_closure_summary(
            successor_binding
        ),
    )
    registry = _registry_with_successor(
        state.registry,
        retired_record,
        successor_record,
        candidate_stream_generation,
    )
    next_controller = _new_symbol_acquisition_controller(
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        controller_head=successor_head,
        successor_ordinal=successor_ordinal,
        live_generation_id=successor_generation_id,
        recovery_class=AcquisitionRecoveryClass.NORMAL,
        scope_execution_commitment=receipt.scope_execution_commitment,
        venue_commitment=receipt.venue_commitment,
        authority_context_commitment=receipt.authority_commitment,
        protection_commitment=None,
        binding_commitment=successor_mandate.binding.commitment,
        compatibility_commitment=controller._compatibility_commitment,
    )
    next_state = _new_acquisition_controller_state(
        controller=next_controller,
        mandate=successor_mandate,
        registry=registry,
        lineage=state.lineage,
    )
    return _new_applied_successor_transition(
        predecessor_state=state,
        state=next_state,
        refresh=refresh,
        authority=registration.state,
        receipt=receipt,
    )


def reduce_acquisition_controller(
    state: AcquisitionControllerState,
    transition: _VenueRecoveryTransition,
    protection: _PositionProtectionState | None,
    authority: _ExecutionAuthorityState,
) -> AcquisitionControllerTransition:
    _require_exact("state", state, AcquisitionControllerState)
    _require_exact("transition", transition, _VenueRecoveryTransition)
    _require_exact("authority", authority, _ExecutionAuthorityState)
    if protection is not None:
        _require_exact("protection", protection, _PositionProtectionState)
    initial_root = state._controller.protection_commitment is None
    projection = transition.book.project_acquisition_fact(transition)
    relation = projection.fact_relation()
    if (
        projection.source_kind
        not in {
            _AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT,
            _AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION,
        }
        or relation is None
        or not projection.matches_fact_transition(transition, state.position_scope)
        or projection.application_generation_id != state.application_generation_id
        or projection.position_scope != state.position_scope
        or projection.execution_snapshot_commitment != transition.execution.commitment
    ):
        return _new_refused_fact_transition(
            state=state,
            transition=transition,
            protection=protection,
            authority=authority,
        )
    request_route = state.lineage.route_request(relation.request_occurrence_id)
    effect_route = state.lineage.route_effect(relation.effect_id)
    if (
        request_route is None
        or effect_route is None
        or request_route.generation_id != effect_route.generation_id
    ):
        return _new_refused_fact_transition(
            state=state,
            transition=transition,
            protection=protection,
            authority=authority,
        )
    generation_id = request_route.generation_id
    record = state.registry.record(generation_id)
    current_generation_id = state._controller.live_generation_id
    retired_generation = bool(
        record is not None
        and record.serving_class is GenerationServingClass.RETIRED_UNSERVING
        and generation_id != current_generation_id
    )
    current_generation = bool(
        record is not None
        and record.serving_class is GenerationServingClass.LIVE
        and generation_id == current_generation_id
    )
    if (
        current_generation_id is None
        or not (retired_generation or current_generation)
        or (
            initial_root
            and current_generation
            and not _first_current_generation_fact_is_exact(
                state,
                transition,
                protection,
            )
        )
        or (current_generation and not initial_root and protection is None)
    ):
        return _new_refused_fact_transition(
            state=state,
            transition=transition,
            protection=protection,
            authority=authority,
        )
    replay_candidate = bool(
        not initial_root
        and state.lineage.route_fact(relation.fact_key) is not None
        and state.scope_execution_commitment == projection.scope_execution_commitment
        and state.venue_commitment == projection.venue_commitment
    )
    if not replay_candidate and (
        projection.predecessor_scope_execution_commitment
        != state.scope_execution_commitment
        or state.lineage.route_fact(relation.fact_key) is not None
    ):
        return _new_refused_fact_transition(
            state=state,
            transition=transition,
            protection=protection,
            authority=authority,
        )
    next_controller_head = (
        state._controller.controller_head
        if replay_candidate
        else _controller_head_after_fact(state, projection, relation)
    )
    fact_preemption = None
    try:
        if replay_candidate:
            if protection is None:
                raise TypeError("canonical fact replay requires protection")
            effective_protection = protection
        else:
            if retired_generation:
                mixed_proof, protection_venue = _mint_acquisition_mixed_recovery_proof(
                    application_generation_id=state.application_generation_id,
                    position_scope=state.position_scope,
                    retired_generation_id=generation_id,
                    retired_relation_commitment=relation.source_commitment,
                    predecessor_controller_head=state._controller.controller_head,
                    controller_head=next_controller_head,
                    venue_commitment=projection.venue_commitment,
                    dual_binding_commitment=state._mandate.binding.commitment,
                    compatibility_commitment=(
                        state._controller._compatibility_commitment
                    ),
                    mandate=state._mandate.protection_mandate,
                    prior_state=protection,
                    transition=transition,
                )
                protection_transition = _force_acquisition_mixed_recovery(
                    protection,
                    state._mandate.protection_mandate,
                    protection_venue,
                    mixed_proof,
                )
                if (
                    protection_transition.disposition
                    is not _ProtectionDisposition.APPLIED
                    or protection_transition.state.policy
                    is not _ProtectionPolicy.HARD_BAIL
                    or protection_transition.goal is not None
                ):
                    raise ValueError("retired fact mixed recovery refused")
                effective_protection = protection_transition.state
            elif initial_root:
                protection_venue = _project_protection_venue(
                    transition,
                    state._mandate.protection_mandate,
                )
                effective_protection = _initialize_position_protection(
                    state._mandate.protection_mandate,
                    protection_venue,
                )
            else:
                assert protection is not None
                protection_venue = _project_protection_venue(
                    transition,
                    state._mandate.protection_mandate,
                )
                protection_transition = _reduce_position_protection(
                    protection,
                    protection_venue,
                )
                if protection_transition.disposition not in {
                    _ProtectionDisposition.APPLIED,
                    _ProtectionDisposition.EXACT_REPLAY,
                }:
                    raise ValueError("canonical fact protection reduction refused")
                effective_protection = protection_transition.state
        if type(effective_protection) is not _PositionProtectionState:
            raise TypeError("canonical fact has no exact protection state")
        venue_context = transition.book.project_acquisition_context(
            transition.execution,
            state.position_scope,
        )
        protection_context = _project_acquisition_protection_context(
            effective_protection,
            transition.book,
            transition.execution,
            venue_context,
        )
        if (
            type(protection_context) is not _AcquisitionProtectionContext
            or protection_context.scope_protection_commitment is None
        ):
            raise ValueError("canonical fact protection context is not current")
        if replay_candidate:
            if (
                state.scope_execution_commitment
                != projection.scope_execution_commitment
                or state.venue_commitment != projection.venue_commitment
                or state.protection_commitment
                != protection_context.scope_protection_commitment
            ):
                raise ValueError("canonical fact replay state is not exact")
            next_controller_head = state._controller.controller_head
        preemption_intent = (
            _project_acquisition_preemption_intent(
                effective_protection,
                protection_context,
            )
            if retired_generation and not replay_candidate
            else None
        )
        if preemption_intent is not None and preemption_intent.matches_current(
            effective_protection,
            protection_context,
        ):
            fact_preemption_input_id = _AuthorityInputId(
                "acquisition-fact-preempt:"
                + _sha256(
                    _commit_parts(
                        b"execution-core/acquisition/fact-preemption-input/v1",
                        next_controller_head,
                        projection.source_commitment,
                        preemption_intent._seal,
                    )
                ).hexdigest()
            )
            fact_preemption = _mint_acquisition_fact_preemption(
                authority,
                fact_transition=transition,
                fact_projection=projection,
                application_generation_id=state.application_generation_id,
                position_scope=state.position_scope,
                session_id=state._mandate.session_id,
                generation_id=current_generation_id,
                acquisition_mandate_id=state._mandate.acquisition_mandate_id,
                protection_mandate_id=state._mandate.protection_mandate.mandate_id,
                binding_commitment=state._mandate.binding.commitment,
                emergency_recovery_compatibility_commitment=(
                    state._mandate.protection_mandate.emergency_recovery_compatibility.commitment
                ),
                predecessor_controller_head=state._controller.controller_head,
                controller_head=next_controller_head,
                successor_ordinal=state._controller.successor_ordinal,
                protection_commitment=(protection_context.scope_protection_commitment),
                residual_quantity=_Quantity(effective_protection.raw_quantity),
                intent_commitment=preemption_intent._seal,
                predecessor_authority_context_commitment=(
                    state.authority_context_commitment
                ),
                input_id=fact_preemption_input_id,
            )
        if fact_preemption is None:
            registration = _mint_acquisition_currentness_registration(
                application_generation_id=state.application_generation_id,
                position_scope=state.position_scope,
                session_id=state._mandate.session_id,
                generation_id=current_generation_id,
                acquisition_mandate_id=state._mandate.acquisition_mandate_id,
                protection_mandate_id=state._mandate.protection_mandate.mandate_id,
                binding_commitment=state._mandate.binding.commitment,
                emergency_recovery_compatibility_commitment=(
                    state._mandate.protection_mandate.emergency_recovery_compatibility.commitment
                ),
                controller_head=next_controller_head,
                successor_ordinal=state._controller.successor_ordinal,
                protection_commitment=(protection_context.scope_protection_commitment),
                authority=authority,
                fact_transition=transition,
                fact_projection=projection,
                predecessor_authority_context_commitment=(
                    state.authority_context_commitment
                ),
            )
            command = _RegisterAcquisitionCurrentness.from_registration(registration)
        else:
            command = None
    except (TypeError, ValueError):
        return _new_refused_fact_transition(
            state=state,
            transition=transition,
            protection=protection,
            authority=authority,
        )
    applied = (
        _apply_acquisition_fact_preemption(authority, fact_preemption)
        if fact_preemption is not None
        else _apply_execution_authority_input(
            authority,
            transition.execution,
            command,
        )
    )
    if applied.disposition is _AuthorityDisposition.EXACT_REPLAY:
        try:
            refresh = _refresh_acquisition_context(
                applied.state,
                transition.execution,
                state.position_scope,
            )
            if not refresh.matches_current(
                applied.state,
                state.application_generation_id,
                state.position_scope,
            ):
                raise ValueError("canonical fact replay refresh is not current")
            return _new_replayed_fact_transition(
                state=state,
                transition=transition,
                protection=effective_protection,
                authority=applied.state,
                refresh=refresh,
            )
        except (TypeError, ValueError):
            return _new_refused_fact_transition(
                state=state,
                transition=transition,
                protection=protection,
                authority=authority,
            )
    receipt = applied.acquisition_receipt
    if (
        applied.disposition is not _AuthorityDisposition.APPLIED
        or type(receipt) is not _AcquisitionAuthorityReceipt
    ):
        return _new_refused_fact_transition(
            state=state,
            transition=transition,
            protection=protection,
            authority=authority,
        )
    if fact_preemption is not None:
        try:
            for venue_transition in applied.venue_transitions:
                protection_transition = _reduce_acquisition_mixed_recovery(
                    effective_protection,
                    venue_transition,
                )
                if (
                    protection_transition.disposition
                    is not _ProtectionDisposition.APPLIED
                    or protection_transition.goal is not None
                    or protection_transition.critical_alert is not None
                ):
                    raise ValueError("fact preemption protection catch-up refused")
                effective_protection = protection_transition.state
            post_venue_context = applied.state.venue.project_acquisition_context(
                transition.execution,
                state.position_scope,
            )
            post_protection_context = _project_acquisition_protection_context(
                effective_protection,
                applied.state.venue,
                transition.execution,
                post_venue_context,
            )
            if (
                type(post_protection_context) is not _AcquisitionProtectionContext
                or post_protection_context.scope_protection_commitment is None
            ):
                raise ValueError("fact preemption protection context is not current")
            protection_context = post_protection_context
        except (TypeError, ValueError):
            return _new_refused_fact_transition(
                state=state,
                transition=transition,
                protection=protection,
                authority=authority,
            )
    if record is None:
        raise RuntimeError("admitted fact lost its direct generation record")
    serving_class = (
        GenerationServingClass.RETIRED_UNSERVING
        if retired_generation
        else (
            GenerationServingClass.RECONCILIATION_REQUIRED
            if projection.source_kind
            is _AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION
            else GenerationServingClass.LIVE
        )
    )
    replacement_record = _new_generation_record_view(
        binding=record.binding,
        economics_head_commitment=_generation_economics_head_after_fact(
            record,
            projection,
            relation,
        ),
        serving_class=serving_class,
        closure_summary_commitment=(
            _commit_parts(
                b"execution-core/acquisition/generation-closure/retired-fact/v1",
                record.closure_summary_commitment,
                relation.source_commitment,
                projection.source_commitment,
            )
            if retired_generation
            else record.closure_summary_commitment
        ),
    )
    next_registry = _registry_with_replaced_record(
        state.registry,
        replacement_record,
    )
    next_lineage = _lineage_with_generation_fact(
        state.lineage,
        relation=relation,
        generation_id=generation_id,
    )
    next_controller = _new_symbol_acquisition_controller(
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        controller_head=receipt.controller_head,
        successor_ordinal=state._controller.successor_ordinal,
        live_generation_id=current_generation_id,
        recovery_class=(
            (
                AcquisitionRecoveryClass.MIXED_GENERATION_RECONCILIATION_REQUIRED
                if projection.source_kind
                is _AcquisitionVenueSourceKind.CANONICAL_ECONOMIC_FACT_RECONCILIATION
                else AcquisitionRecoveryClass.MIXED_GENERATION_RECOVERY
            )
            if retired_generation
            else (
                AcquisitionRecoveryClass.RECONCILIATION_REQUIRED
                if serving_class is GenerationServingClass.RECONCILIATION_REQUIRED
                else AcquisitionRecoveryClass.NORMAL
            )
        ),
        scope_execution_commitment=receipt.scope_execution_commitment,
        venue_commitment=receipt.venue_commitment,
        authority_context_commitment=receipt.authority_commitment,
        protection_commitment=protection_context.scope_protection_commitment,
        binding_commitment=state._controller._binding_commitment,
        compatibility_commitment=state._controller._compatibility_commitment,
    )
    next_state = _new_acquisition_controller_state(
        controller=next_controller,
        mandate=state._mandate,
        registry=next_registry,
        lineage=next_lineage,
    )
    refresh = _refresh_acquisition_context(
        applied.state,
        transition.execution,
        state.position_scope,
    )
    if not refresh.matches_current(
        applied.state,
        state.application_generation_id,
        state.position_scope,
    ):
        raise RuntimeError("admitted canonical fact did not produce a current refresh")
    if fact_preemption is not None:
        created_effect_id = (
            applied.created_effect_ids[0] if applied.created_effect_ids else None
        )
        return _new_applied_fact_preemption_transition(
            predecessor_state=state,
            state=next_state,
            transition=transition,
            protection=effective_protection,
            protection_context=protection_context,
            authority=applied.state,
            refresh=refresh,
            receipt=receipt,
            created_effect_id=created_effect_id,
        )
    return _new_applied_fact_transition(
        predecessor_state=state,
        state=next_state,
        transition=transition,
        protection=effective_protection,
        protection_context=protection_context,
        authority=applied.state,
        refresh=refresh,
        receipt=receipt,
    )


def rebase_acquisition_protection(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    source: _AcquisitionProtectionRebaseProjection | _PositionProtectionState,
) -> AcquisitionControllerTransition:
    _require_exact("state", state, AcquisitionControllerState)
    _require_exact("refresh", refresh, _AcquisitionContextRefresh)
    if type(source) not in {
        _AcquisitionProtectionRebaseProjection,
        _PositionProtectionState,
    }:
        raise TypeError(
            "source must be AcquisitionProtectionRebaseProjection "
            "or PositionProtectionState"
        )
    if type(source) is _PositionProtectionState:
        if not _neutral_reprojection_source_is_exact(state, refresh):
            return _new_refused_rebase_transition(
                state=state,
                refresh=refresh,
                source=source,
            )
        assert refresh.predecessor_execution is not None
        assert refresh.predecessor_venue_context is not None
        assert refresh.venue_context is not None
        transition = refresh.venue_transitions[0]
        projection = _project_acquisition_neutral_reprojection(
            source,
            refresh.predecessor_execution,
            refresh.predecessor_venue_context,
            transition,
            refresh.venue_context,
        )
        if projection is None or refresh.authority is None or refresh.execution is None:
            return _new_refused_rebase_transition(
                state=state,
                refresh=refresh,
                source=source,
            )
        current_context = _project_acquisition_protection_context(
            projection.resulting_state,
            refresh.authority.venue,
            refresh.execution,
            refresh.venue_context,
        )
        if (
            type(current_context) is not _AcquisitionProtectionContext
            or state.protection_commitment is None
            or not projection.matches_neutral_reprojection(
                state.protection_commitment,
                current_context,
                transition._protection_proof_commitment,
            )
        ):
            return _new_refused_rebase_transition(
                state=state,
                refresh=refresh,
                source=source,
            )
        return _new_applied_neutral_reprojection_transition(
            state=state,
            predecessor_protection=source,
            projection=projection,
            current_context=current_context,
            refresh=refresh,
        )

    if type(source) is not _AcquisitionProtectionRebaseProjection:
        raise TypeError("semantic protection rebase requires one exact projection")
    projection = source
    if type(projection.resulting_state) is not _PositionProtectionState:
        raise TypeError("semantic protection rebase requires one exact resulting state")
    if (
        state.protection_commitment is None
        or not projection.matches_predecessor_scope_protection_commitment(
            state.protection_commitment
        )
        or not _semantic_rebase_source_is_exact(state, refresh, projection)
    ):
        return _new_refused_rebase_transition(
            state=state,
            refresh=refresh,
            source=projection,
        )
    authority = refresh.authority
    execution = refresh.execution
    venue_context = refresh.venue_context
    assert authority is not None
    assert execution is not None
    assert venue_context is not None
    protection_context = _project_acquisition_protection_context(
        projection.resulting_state,
        authority.venue,
        execution,
        venue_context,
    )
    if (
        type(protection_context) is not _AcquisitionProtectionContext
        or protection_context.scope_protection_commitment is None
        or protection_context.scope_protection_commitment == state.protection_commitment
    ):
        return _new_refused_rebase_transition(
            state=state,
            refresh=refresh,
            source=projection,
        )
    controller = state._controller
    generation_id = controller.live_generation_id
    if generation_id is None:
        return _new_refused_rebase_transition(
            state=state,
            refresh=refresh,
            source=projection,
        )
    mandate = state._mandate
    try:
        next_controller_head = _controller_head_after_protection_rebase(
            state,
            projection,
        )
        registration = _mint_acquisition_currentness_registration(
            application_generation_id=state.application_generation_id,
            position_scope=state.position_scope,
            session_id=mandate.session_id,
            generation_id=generation_id,
            acquisition_mandate_id=mandate.acquisition_mandate_id,
            protection_mandate_id=mandate.protection_mandate.mandate_id,
            binding_commitment=mandate.binding.commitment,
            emergency_recovery_compatibility_commitment=(
                mandate.protection_mandate.emergency_recovery_compatibility.commitment
            ),
            controller_head=next_controller_head,
            successor_ordinal=controller.successor_ordinal,
            protection_commitment=protection_context.scope_protection_commitment,
            authority=authority,
            refresh=refresh,
            predecessor_authority_context_commitment=(
                state.authority_context_commitment
            ),
            protection_rebase=projection,
        )
        command = _RegisterAcquisitionCurrentness.from_registration(registration)
    except (TypeError, ValueError):
        return _new_refused_rebase_transition(
            state=state,
            refresh=refresh,
            source=projection,
        )
    applied = _apply_execution_authority_input(authority, execution, command)
    receipt = applied.acquisition_receipt
    if (
        applied.disposition is not _AuthorityDisposition.APPLIED
        or type(applied.state) is not _ExecutionAuthorityState
        or receipt is None
        or applied.acquisition_claim_receipt is not None
        or applied.created_effect_ids != ()
        or applied.fresh_claim is not None
        or applied.venue_transitions != ()
    ):
        return _new_refused_rebase_transition(
            state=state,
            refresh=refresh,
            source=projection,
        )
    next_controller = _new_symbol_acquisition_controller(
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        controller_head=receipt.controller_head,
        successor_ordinal=controller.successor_ordinal,
        live_generation_id=generation_id,
        recovery_class=controller.recovery_class,
        scope_execution_commitment=receipt.scope_execution_commitment,
        venue_commitment=receipt.venue_commitment,
        authority_context_commitment=receipt.authority_commitment,
        protection_commitment=protection_context.scope_protection_commitment,
        binding_commitment=controller._binding_commitment,
        compatibility_commitment=controller._compatibility_commitment,
    )
    next_state = _new_acquisition_controller_state(
        controller=next_controller,
        mandate=mandate,
        registry=state.registry,
        lineage=state.lineage,
    )
    next_refresh = _refresh_acquisition_context(
        applied.state,
        execution,
        state.position_scope,
    )
    if not next_refresh.matches_current(
        applied.state,
        state.application_generation_id,
        state.position_scope,
    ):
        raise RuntimeError(
            "admitted protection rebase did not produce a current refresh"
        )
    return _new_applied_rebase_transition(
        predecessor_state=state,
        state=next_state,
        protection=projection.resulting_state,
        authority=applied.state,
        refresh=next_refresh,
        receipt=receipt,
    )


def create_acquisition_effect(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
    terms: AcquisitionEffectTerms,
    input_id: _AuthorityInputId,
) -> AcquisitionControllerTransition:
    _require_exact("state", state, AcquisitionControllerState)
    _require_exact("refresh", refresh, _AcquisitionContextRefresh)
    _require_exact("terms", terms, AcquisitionEffectTerms)
    _require_exact("input_id", input_id, _AuthorityInputId)
    if not _ordinary_create_source_is_exact(state, refresh, protection):
        return _new_refused_create_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    mandate = state._mandate
    if not _terms_are_within_acquisition_mandate(mandate, terms):
        return _new_refused_create_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    authority = refresh.authority
    execution = refresh.execution
    assert authority is not None
    assert execution is not None
    controller = state._controller
    generation_id = controller.live_generation_id
    if generation_id is None:
        return _new_refused_create_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    try:
        permit = _mint_acquisition_effect_permit(
            authority,
            execution,
            application_generation_id=state.application_generation_id,
            position_scope=state.position_scope,
            session_id=mandate.session_id,
            generation_id=generation_id,
            acquisition_mandate_id=mandate.acquisition_mandate_id,
            protection_mandate_id=mandate.protection_mandate.mandate_id,
            binding_commitment=mandate.binding.commitment,
            emergency_recovery_compatibility_commitment=(
                mandate.protection_mandate.emergency_recovery_compatibility.commitment
            ),
            predecessor_controller_head=controller.controller_head,
            controller_head=_controller_head_after_create(state, terms, input_id),
            successor_ordinal=controller.successor_ordinal,
            protection_commitment=state.protection_commitment,
            terms=terms,
            refresh=refresh,
            input_id=input_id,
        )
    except (TypeError, ValueError):
        return _new_refused_create_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    applied = _apply_execution_authority_input(
        authority,
        execution,
        _CreateAcquisitionEffect(input_id=input_id, permit=permit),
    )
    receipt = applied.acquisition_receipt
    if (
        applied.disposition is not _AuthorityDisposition.APPLIED
        or type(applied.state) is not _ExecutionAuthorityState
        or receipt is None
        or applied.acquisition_claim_receipt is not None
        or applied.created_effect_ids != (permit.effect_id,)
        or len(applied.venue_transitions) != 1
    ):
        return _new_refused_create_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    next_controller = _new_symbol_acquisition_controller(
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        controller_head=receipt.controller_head,
        successor_ordinal=controller.successor_ordinal,
        live_generation_id=generation_id,
        recovery_class=controller.recovery_class,
        scope_execution_commitment=receipt.scope_execution_commitment,
        venue_commitment=receipt.venue_commitment,
        authority_context_commitment=receipt.authority_commitment,
        protection_commitment=state.protection_commitment,
        binding_commitment=controller._binding_commitment,
        compatibility_commitment=controller._compatibility_commitment,
    )
    next_state = _new_acquisition_controller_state(
        controller=next_controller,
        mandate=mandate,
        registry=state.registry,
        lineage=_lineage_with_first_effect(
            state.lineage,
            request_occurrence_id=permit.request_occurrence_id,
            effect_id=permit.effect_id,
            generation_id=generation_id,
        ),
    )
    return _new_created_effect_transition(
        predecessor_state=state,
        state=next_state,
        refresh=refresh,
        authority=applied.state,
        receipt=receipt,
        effect_id=permit.effect_id,
        protection=protection,
    )


def claim_acquisition_effect(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
    effect_id: _EffectId,
    claim_occurrence_id: _ClaimOccurrenceId,
    input_id: _AuthorityInputId,
) -> AcquisitionControllerTransition:
    _require_exact("state", state, AcquisitionControllerState)
    _require_exact("refresh", refresh, _AcquisitionContextRefresh)
    _require_exact("effect_id", effect_id, _EffectId)
    _require_exact("claim_occurrence_id", claim_occurrence_id, _ClaimOccurrenceId)
    _require_exact("input_id", input_id, _AuthorityInputId)
    if not _ordinary_claim_source_is_exact(state, refresh, protection):
        return _new_refused_claim_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    authority = refresh.authority
    execution = refresh.execution
    assert authority is not None
    assert execution is not None
    mandate = state._mandate
    controller = state._controller
    generation_id = controller.live_generation_id
    if generation_id is None:
        return _new_refused_claim_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    try:
        permit = _mint_acquisition_claim_permit(
            authority,
            execution,
            application_generation_id=state.application_generation_id,
            position_scope=state.position_scope,
            session_id=mandate.session_id,
            generation_id=generation_id,
            acquisition_mandate_id=mandate.acquisition_mandate_id,
            protection_mandate_id=mandate.protection_mandate.mandate_id,
            binding_commitment=mandate.binding.commitment,
            emergency_recovery_compatibility_commitment=(
                mandate.protection_mandate.emergency_recovery_compatibility.commitment
            ),
            controller_head=controller.controller_head,
            successor_ordinal=controller.successor_ordinal,
            protection_commitment=state.protection_commitment,
            effect_id=effect_id,
            claim_occurrence_id=claim_occurrence_id,
            refresh=refresh,
            input_id=input_id,
        )
    except (TypeError, ValueError):
        return _new_refused_claim_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    applied = _apply_execution_authority_input(
        authority,
        execution,
        _ClaimAcquisitionEffect(
            input_id=input_id,
            effect_id=effect_id,
            claim_occurrence_id=claim_occurrence_id,
            permit=permit,
        ),
    )
    receipt = applied.acquisition_receipt
    claim_receipt = applied.acquisition_claim_receipt
    if (
        applied.disposition is not _AuthorityDisposition.APPLIED
        or type(applied.state) is not _ExecutionAuthorityState
        or receipt is None
        or claim_receipt is None
        or applied.created_effect_ids != ()
        or applied.fresh_claim is not None
        or len(applied.venue_transitions) != 1
    ):
        return _new_refused_claim_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    next_controller = _new_symbol_acquisition_controller(
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        controller_head=receipt.controller_head,
        successor_ordinal=controller.successor_ordinal,
        live_generation_id=generation_id,
        recovery_class=controller.recovery_class,
        scope_execution_commitment=receipt.scope_execution_commitment,
        venue_commitment=receipt.venue_commitment,
        authority_context_commitment=receipt.authority_commitment,
        protection_commitment=state.protection_commitment,
        binding_commitment=controller._binding_commitment,
        compatibility_commitment=controller._compatibility_commitment,
    )
    next_state = _new_acquisition_controller_state(
        controller=next_controller,
        mandate=mandate,
        registry=state.registry,
        lineage=state.lineage,
    )
    return _new_claimed_effect_transition(
        predecessor_state=state,
        state=next_state,
        refresh=refresh,
        authority=applied.state,
        receipt=receipt,
        claim_receipt=claim_receipt,
        effect_id=effect_id,
        claim_occurrence_id=claim_occurrence_id,
        protection=protection,
    )


def begin_acquisition_preemption(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
    input_id: _AuthorityInputId,
) -> AcquisitionControllerTransition:
    _require_exact("state", state, AcquisitionControllerState)
    _require_exact("refresh", refresh, _AcquisitionContextRefresh)
    _require_exact("input_id", input_id, _AuthorityInputId)
    if type(protection) is not _PositionProtectionState:
        raise TypeError("acquisition preemption requires one exact protection state")
    if (
        not _controller_state_is_authentic(state)
        or refresh.disposition is not _AcquisitionContextRefreshDisposition.CURRENT
        or refresh.authority is None
        or refresh.execution is None
        or refresh.venue_context is None
        or refresh.authority_context is None
        or not refresh.matches_current(
            refresh.authority,
            state.application_generation_id,
            state.position_scope,
        )
    ):
        return _new_refused_preemption_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    protection_context = _project_acquisition_protection_context(
        protection,
        refresh.authority.venue,
        refresh.execution,
        refresh.venue_context,
    )
    intent = (
        None
        if protection_context is None
        else _project_acquisition_preemption_intent(protection, protection_context)
    )
    controller = state._controller
    mandate = state._mandate
    generation_id = controller.live_generation_id
    if (
        protection_context is None
        or protection_context.scope_protection_commitment is None
        or protection_context.scope_protection_commitment != state.protection_commitment
        or intent is None
        or not intent.matches_current(protection, protection_context)
        or generation_id is None
    ):
        return _new_refused_preemption_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    next_controller_head = _controller_head_after_preemption(
        state,
        input_id,
        intent._seal,
    )
    try:
        permit = _mint_acquisition_exit_permit(
            refresh.authority,
            refresh.execution,
            purpose="PREEMPT_BUY_ONLY",
            application_generation_id=state.application_generation_id,
            position_scope=state.position_scope,
            session_id=mandate.session_id,
            generation_id=generation_id,
            acquisition_mandate_id=mandate.acquisition_mandate_id,
            protection_mandate_id=mandate.protection_mandate.mandate_id,
            binding_commitment=mandate.binding.commitment,
            emergency_recovery_compatibility_commitment=(
                mandate.protection_mandate.emergency_recovery_compatibility.commitment
            ),
            predecessor_controller_head=controller.controller_head,
            controller_head=next_controller_head,
            successor_ordinal=controller.successor_ordinal,
            protection_commitment=protection_context.scope_protection_commitment,
            residual_quantity=_Quantity(protection.raw_quantity),
            intent_commitment=intent._seal,
            refresh=refresh,
            input_id=input_id,
        )
    except (TypeError, ValueError):
        return _new_refused_preemption_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    applied = _apply_execution_authority_input(
        refresh.authority,
        refresh.execution,
        _BeginAcquisitionPreemption(input_id=input_id, permit=permit),
    )
    receipt = applied.acquisition_receipt
    if (
        applied.disposition is not _AuthorityDisposition.APPLIED
        or type(applied.state) is not _ExecutionAuthorityState
        or receipt is None
        or applied.acquisition_claim_receipt is not None
        or len(applied.created_effect_ids) > 1
        or not applied.venue_transitions
    ):
        return _new_refused_preemption_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )

    next_protection = protection
    try:
        for venue_transition in applied.venue_transitions:
            projected = _project_protection_venue(
                venue_transition,
                mandate.protection_mandate,
            )
            reduced = _reduce_position_protection(next_protection, projected)
            if (
                reduced.disposition is not _ProtectionDisposition.APPLIED
                or reduced.goal is not None
                or reduced.critical_alert is not None
            ):
                raise ValueError("preemption protection catch-up is not transport-only")
            next_protection = reduced.state
    except (TypeError, ValueError):
        return _new_refused_preemption_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    post_venue_context = applied.state.venue.project_acquisition_context(
        refresh.execution,
        state.position_scope,
    )
    post_protection_context = _project_acquisition_protection_context(
        next_protection,
        applied.state.venue,
        refresh.execution,
        post_venue_context,
    )
    if (
        post_protection_context is None
        or post_protection_context.scope_protection_commitment
        != state.protection_commitment
    ):
        return _new_refused_preemption_transition(
            state=state,
            refresh=refresh,
            protection=protection,
        )
    next_controller = _new_symbol_acquisition_controller(
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        controller_head=receipt.controller_head,
        successor_ordinal=controller.successor_ordinal,
        live_generation_id=generation_id,
        recovery_class=controller.recovery_class,
        scope_execution_commitment=receipt.scope_execution_commitment,
        venue_commitment=receipt.venue_commitment,
        authority_context_commitment=receipt.authority_commitment,
        protection_commitment=state.protection_commitment,
        binding_commitment=controller._binding_commitment,
        compatibility_commitment=controller._compatibility_commitment,
    )
    next_state = _new_acquisition_controller_state(
        controller=next_controller,
        mandate=mandate,
        registry=state.registry,
        lineage=state.lineage,
    )
    created_effect_id = (
        applied.created_effect_ids[0] if applied.created_effect_ids else None
    )
    return _new_applied_preemption_transition(
        predecessor_state=state,
        state=next_state,
        refresh=refresh,
        protection=next_protection,
        authority=applied.state,
        receipt=receipt,
        created_effect_id=created_effect_id,
    )


def create_acquisition_protection_exit(
    state: AcquisitionControllerState,
    refresh: _AcquisitionContextRefresh,
    protection: _PositionProtectionState | None,
    transition: _ProtectionTransition,
    input_id: _AuthorityInputId,
) -> AcquisitionControllerTransition:
    _require_exact("state", state, AcquisitionControllerState)
    _require_exact("refresh", refresh, _AcquisitionContextRefresh)
    _require_exact("transition", transition, _ProtectionTransition)
    _require_exact("input_id", input_id, _AuthorityInputId)
    if type(protection) is not _PositionProtectionState:
        raise TypeError(
            "acquisition protection exit requires one exact protection state"
        )
    if (
        not _controller_state_is_authentic(state)
        or refresh.disposition is not _AcquisitionContextRefreshDisposition.CURRENT
        or refresh.authority is None
        or refresh.execution is None
        or refresh.venue_context is None
        or refresh.authority_context is None
        or not refresh.matches_current(
            refresh.authority,
            state.application_generation_id,
            state.position_scope,
        )
        or refresh.execution.position.scope != state.position_scope
        or state.scope_execution_commitment
        != refresh.venue_context.scope_execution_commitment
        or state.authority_context_commitment
        != refresh.authority_context.authority_commitment
        or protection != transition.state
    ):
        return _new_refused_protection_exit_transition(
            state=state,
            refresh=refresh,
            protection=protection,
            transition=transition,
        )
    protection_context = _project_acquisition_protection_context(
        protection,
        refresh.authority.venue,
        refresh.execution,
        refresh.venue_context,
    )
    intent = (
        None
        if protection_context is None
        else _project_acquisition_protection_exit_intent(
            transition,
            protection_context,
        )
    )
    controller = state._controller
    mandate = state._mandate
    generation_id = controller.live_generation_id
    coordinates = (
        None
        if intent is None or protection_context is None
        else intent.request_coordinates(transition, protection_context)
    )
    if (
        protection_context is None
        or protection_context.scope_protection_commitment is None
        or intent is None
        or not intent.matches_current(transition, protection_context)
        or coordinates is None
        or generation_id is None
        or state.protection_commitment is None
        or mandate.position_scope != state.position_scope
        or mandate.session_id != refresh.authority.session_id
    ):
        return _new_refused_protection_exit_transition(
            state=state,
            refresh=refresh,
            protection=protection,
            transition=transition,
        )
    next_controller_head = _controller_head_after_protection_exit(
        state,
        input_id,
        intent._seal,
        transition._seal,
    )
    try:
        permit = _mint_acquisition_exit_permit(
            refresh.authority,
            refresh.execution,
            purpose="CREATE_PROTECTION_EXIT_ONLY",
            application_generation_id=state.application_generation_id,
            position_scope=state.position_scope,
            session_id=mandate.session_id,
            generation_id=generation_id,
            acquisition_mandate_id=mandate.acquisition_mandate_id,
            protection_mandate_id=mandate.protection_mandate.mandate_id,
            binding_commitment=mandate.binding.commitment,
            emergency_recovery_compatibility_commitment=(
                mandate.protection_mandate.emergency_recovery_compatibility.commitment
            ),
            predecessor_controller_head=controller.controller_head,
            controller_head=next_controller_head,
            successor_ordinal=controller.successor_ordinal,
            protection_commitment=(protection_context.scope_protection_commitment),
            residual_quantity=_Quantity(protection.raw_quantity),
            intent_commitment=intent._seal,
            refresh=refresh,
            input_id=input_id,
            protective_goal_coordinates=coordinates,
        )
    except (TypeError, ValueError):
        return _new_refused_protection_exit_transition(
            state=state,
            refresh=refresh,
            protection=protection,
            transition=transition,
        )
    applied = _apply_execution_authority_input(
        refresh.authority,
        refresh.execution,
        _CreateAcquisitionProtectionExit(input_id=input_id, permit=permit),
    )
    receipt = applied.acquisition_receipt
    if (
        applied.disposition is not _AuthorityDisposition.APPLIED
        or type(applied.state) is not _ExecutionAuthorityState
        or receipt is None
        or receipt.operation is not _AcquisitionAuthorityOperation.PROTECTION_EXIT
        or applied.acquisition_claim_receipt is not None
        or len(applied.created_effect_ids) != 1
        or len(applied.venue_transitions) != 1
    ):
        return _new_refused_protection_exit_transition(
            state=state,
            refresh=refresh,
            protection=protection,
            transition=transition,
        )
    try:
        reduced = _reduce_position_protection(
            protection,
            _project_protection_venue(
                applied.venue_transitions[0],
                mandate.protection_mandate,
            ),
        )
        if (
            reduced.disposition is not _ProtectionDisposition.APPLIED
            or reduced.goal is not None
            or reduced.critical_alert is not None
        ):
            raise ValueError("protective SELL catch-up is not transport-only")
        next_protection = reduced.state
    except (TypeError, ValueError):
        return _new_refused_protection_exit_transition(
            state=state,
            refresh=refresh,
            protection=protection,
            transition=transition,
        )
    post_venue_context = applied.state.venue.project_acquisition_context(
        refresh.execution,
        state.position_scope,
    )
    post_protection_context = _project_acquisition_protection_context(
        next_protection,
        applied.state.venue,
        refresh.execution,
        post_venue_context,
    )
    if (
        post_protection_context is None
        or post_protection_context.scope_protection_commitment
        != protection_context.scope_protection_commitment
    ):
        return _new_refused_protection_exit_transition(
            state=state,
            refresh=refresh,
            protection=protection,
            transition=transition,
        )
    next_controller = _new_symbol_acquisition_controller(
        application_generation_id=state.application_generation_id,
        position_scope=state.position_scope,
        controller_head=receipt.controller_head,
        successor_ordinal=controller.successor_ordinal,
        live_generation_id=generation_id,
        recovery_class=controller.recovery_class,
        scope_execution_commitment=receipt.scope_execution_commitment,
        venue_commitment=receipt.venue_commitment,
        authority_context_commitment=receipt.authority_commitment,
        protection_commitment=protection_context.scope_protection_commitment,
        binding_commitment=controller._binding_commitment,
        compatibility_commitment=controller._compatibility_commitment,
    )
    next_state = _new_acquisition_controller_state(
        controller=next_controller,
        mandate=mandate,
        registry=state.registry,
        lineage=state.lineage,
    )
    return _new_applied_protection_exit_transition(
        predecessor_state=state,
        state=next_state,
        refresh=refresh,
        protection=next_protection,
        source_transition=transition,
        authority=applied.state,
        receipt=receipt,
        created_effect_id=applied.created_effect_ids[0],
    )
