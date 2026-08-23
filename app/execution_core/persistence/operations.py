"""Pure, exact codec primitives for the WO-0168a operation boundary.

This opening implementation slice establishes the canonical semantic-key
grammar, retained alternate-key proof, technical-dedupe fact, exact coordinate
values, and the closed eight-operation type union. It intentionally performs no
database work, reducer work, runtime composition, or caller-supplied operation
dispatch. The operation document codec is added only alongside explicit owner
encoders and decoders; this module does not use reflection or a generic payload
registry as a shortcut.
"""

from __future__ import annotations as _annotations

import hashlib as _hashlib
import json as _json
import struct as _struct
from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum
from typing import TypeAlias as _TypeAlias

from .. import acquisition as _acquisition
from .. import authority as _authority
from .. import fills as _fills
from .. import identity as _identity
from .. import protection as _protection
from .. import recovery as _recovery
from .. import venue as _venue


__all__ = (
    "AcquisitionOperationCoordinates",
    "AuthorityOperation",
    "BeginAcquisitionGenerationOperation",
    "BeginAcquisitionPreemptionOperation",
    "BrokerExecutionOperation",
    "ClaimAcquisitionEffectOperation",
    "CreateAcquisitionEffectOperation",
    "ExecutionOperationCoordinates",
    "InputDedupeFact",
    "InputDedupeKind",
    "InputSemanticKey",
    "InputSemanticKeyKind",
    "M2Operation",
    "MarketOccurrenceOperation",
    "MarketOperationCoordinates",
    "OperationDomain",
    "VenueOperationCoordinates",
    "VenueRecoveryOperation",
    "decode_m2_semantic_key",
    "encode_m2_semantic_key",
)


_SEMANTIC_KEY_PREFIX = b"execution-core/m2-semantic-key/v1\n"
_SHA256_HEX_LENGTH = 64


class InputDedupeKind(str, _Enum):
    """Exact result of primary durable-input classification."""

    UNSEEN = "UNSEEN"
    EXACT_REPLAY = "EXACT_REPLAY"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


class InputSemanticKeyKind(str, _Enum):
    """Closed set of non-primary historical identity projections."""

    VENUE_COMMAND_V2 = "VENUE_COMMAND_V2"
    VENUE_EXECUTION_FACT_V1 = "VENUE_EXECUTION_FACT_V1"
    VENUE_COVERAGE_ROOT_V1 = "VENUE_COVERAGE_ROOT_V1"
    VENUE_COVERAGE_INTERVAL_V1 = "VENUE_COVERAGE_INTERVAL_V1"
    VENUE_BROKER_FACT_V1 = "VENUE_BROKER_FACT_V1"
    AUTHORITY_QUERY_CLAIM_V1 = "AUTHORITY_QUERY_CLAIM_V1"
    AUTHORITY_MANUAL_FLATTEN_V1 = "AUTHORITY_MANUAL_FLATTEN_V1"
    AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1 = (
        "AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1"
    )


class OperationDomain(str, _Enum):
    """Closed operation-domain discriminator for the eventual eight-row union."""

    BROKER_EXECUTION = "BROKER_EXECUTION"
    VENUE_RECOVERY = "VENUE_RECOVERY"
    AUTHORITY = "AUTHORITY"
    BEGIN_ACQUISITION_GENERATION = "BEGIN_ACQUISITION_GENERATION"
    CREATE_ACQUISITION_EFFECT = "CREATE_ACQUISITION_EFFECT"
    CLAIM_ACQUISITION_EFFECT = "CLAIM_ACQUISITION_EFFECT"
    BEGIN_ACQUISITION_PREEMPTION = "BEGIN_ACQUISITION_PREEMPTION"
    MARKET_OCCURRENCE = "MARKET_OCCURRENCE"


def _require_exact_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be exact text")
    text = value
    if not text.strip():
        raise ValueError(f"{name} must be nonblank")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{name} must be valid UTF-8 text") from exc
    return text


def _require_sha256(name: str, value: object) -> str:
    text = _require_exact_text(name, value)
    if len(text) != _SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ValueError(f"{name} must be lowercase SHA-256 hexadecimal text")
    return text


def _require_exact_int(name: str, value: object) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")
    return value


def _require_exact_tuple(name: str, value: object) -> tuple[object, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be an exact tuple")
    return value


def _require_application_generation_id(
    name: str,
    value: object,
) -> _identity.ApplicationGenerationId:
    if type(value) is not _identity.ApplicationGenerationId:
        raise TypeError(f"{name} must be ApplicationGenerationId")
    _identity.ApplicationGenerationId(value.value)
    return value


def _require_session_id(name: str, value: object) -> _identity.SessionId:
    if type(value) is not _identity.SessionId:
        raise TypeError(f"{name} must be SessionId")
    _identity.SessionId(value.value)
    return value


def _require_acquisition_generation_id(
    name: str,
    value: object,
) -> _identity.AcquisitionGenerationId:
    if type(value) is not _identity.AcquisitionGenerationId:
        raise TypeError(f"{name} must be AcquisitionGenerationId")
    if not _identity._acquisition_generation_id_is_canonical(value):
        raise ValueError(f"{name} must be a canonical acquisition generation identity")
    return value


def _require_market_stream_generation_id(
    name: str,
    value: object,
) -> _identity.MarketStreamGenerationId:
    if type(value) is not _identity.MarketStreamGenerationId:
        raise TypeError(f"{name} must be MarketStreamGenerationId")
    if not _identity._market_identity_is_canonical(value):
        raise ValueError(f"{name} must be a canonical market stream identity")
    return value


@_dataclass(frozen=True, slots=True)
class ExecutionOperationCoordinates:
    """Exact application/profile/scope coordinates for execution authority."""

    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    scope_id: int

    def __post_init__(self) -> None:
        if type(self) is not ExecutionOperationCoordinates:
            raise TypeError("ExecutionOperationCoordinates rejects subclass instances")
        _require_application_generation_id(
            "application_generation_id", self.application_generation_id
        )
        _require_exact_text("execution_profile_id", self.execution_profile_id)
        _require_exact_int("scope_id", self.scope_id)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("ExecutionOperationCoordinates cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class VenueOperationCoordinates:
    """Exact execution coordinates plus a venue observation session when present."""

    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    scope_id: int
    session_id: _identity.SessionId | None

    def __post_init__(self) -> None:
        if type(self) is not VenueOperationCoordinates:
            raise TypeError("VenueOperationCoordinates rejects subclass instances")
        _require_application_generation_id(
            "application_generation_id", self.application_generation_id
        )
        _require_exact_text("execution_profile_id", self.execution_profile_id)
        _require_exact_int("scope_id", self.scope_id)
        if self.session_id is not None:
            _require_session_id("session_id", self.session_id)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("VenueOperationCoordinates cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class AcquisitionOperationCoordinates:
    """Exact venue coordinates plus the acquisition generation that owns them."""

    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    scope_id: int
    session_id: _identity.SessionId
    acquisition_generation_id: _identity.AcquisitionGenerationId

    def __post_init__(self) -> None:
        if type(self) is not AcquisitionOperationCoordinates:
            raise TypeError(
                "AcquisitionOperationCoordinates rejects subclass instances"
            )
        _require_application_generation_id(
            "application_generation_id", self.application_generation_id
        )
        _require_exact_text("execution_profile_id", self.execution_profile_id)
        _require_exact_int("scope_id", self.scope_id)
        _require_session_id("session_id", self.session_id)
        _require_acquisition_generation_id(
            "acquisition_generation_id", self.acquisition_generation_id
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AcquisitionOperationCoordinates cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class MarketOperationCoordinates:
    """Exact acquisition coordinates plus one market-source stream coordinate."""

    application_generation_id: _identity.ApplicationGenerationId
    execution_profile_id: str
    scope_id: int
    session_id: _identity.SessionId
    acquisition_generation_id: _identity.AcquisitionGenerationId
    market_source_profile_id: str
    stream_generation_id: _identity.MarketStreamGenerationId

    def __post_init__(self) -> None:
        if type(self) is not MarketOperationCoordinates:
            raise TypeError("MarketOperationCoordinates rejects subclass instances")
        _require_application_generation_id(
            "application_generation_id", self.application_generation_id
        )
        _require_exact_text("execution_profile_id", self.execution_profile_id)
        _require_exact_int("scope_id", self.scope_id)
        _require_session_id("session_id", self.session_id)
        _require_acquisition_generation_id(
            "acquisition_generation_id", self.acquisition_generation_id
        )
        _require_exact_text("market_source_profile_id", self.market_source_profile_id)
        _require_market_stream_generation_id(
            "stream_generation_id", self.stream_generation_id
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("MarketOperationCoordinates cannot be subclassed")


_VENUE_SEMANTIC_KEY_KINDS = (
    InputSemanticKeyKind.VENUE_COMMAND_V2,
    InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
    InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1,
    InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1,
    InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
)


def _validate_semantic_coordinates(
    kind: InputSemanticKeyKind,
    coordinates: object,
) -> tuple[str | int, ...]:
    raw = _require_exact_tuple("coordinates", coordinates)
    if kind in _VENUE_SEMANTIC_KEY_KINDS:
        if len(raw) != 1:
            raise ValueError("venue semantic keys require one profile coordinate")
        return (_require_exact_text("coordinates[0]", raw[0]),)
    if len(raw) != 3:
        raise ValueError("authority semantic keys require three coordinates")
    return (
        _require_exact_text("coordinates[0]", raw[0]),
        _require_exact_text("coordinates[1]", raw[1]),
        _require_exact_int("coordinates[2]", raw[2]),
    )


def _validate_semantic_source(
    kind: InputSemanticKeyKind,
    source: object,
) -> tuple[str | int, ...]:
    raw = _require_exact_tuple("source", source)
    if kind is InputSemanticKeyKind.VENUE_COMMAND_V2:
        if len(raw) != 2 or raw[0] != "venue-semantic-digest":
            raise ValueError("venue command semantic key source is malformed")
        return (
            "venue-semantic-digest",
            _require_sha256("source[1]", raw[1]),
        )
    if kind in (
        InputSemanticKeyKind.VENUE_EXECUTION_FACT_V1,
        InputSemanticKeyKind.VENUE_BROKER_FACT_V1,
    ):
        if len(raw) != 5 or raw[0] != "execution-fact-key":
            raise ValueError("execution-fact semantic key source is malformed")
        return (
            "execution-fact-key",
            _require_exact_text("source[1]", raw[1]),
            _require_exact_text("source[2]", raw[2]),
            _require_exact_text("source[3]", raw[3]),
            _require_exact_text("source[4]", raw[4]),
        )
    if kind is InputSemanticKeyKind.VENUE_COVERAGE_ROOT_V1:
        if len(raw) != 5 or raw[0] != "root-fill-key":
            raise ValueError("coverage-root semantic key source is malformed")
        return (
            "root-fill-key",
            _require_exact_text("source[1]", raw[1]),
            _require_exact_text("source[2]", raw[2]),
            _require_exact_text("source[3]", raw[3]),
            _require_exact_text("source[4]", raw[4]),
        )
    if kind is InputSemanticKeyKind.VENUE_COVERAGE_INTERVAL_V1:
        if len(raw) != 7 or raw[0] != "coverage-interval":
            raise ValueError("coverage-interval semantic key source is malformed")
        return (
            "coverage-interval",
            _require_exact_text("source[1]", raw[1]),
            _require_exact_text("source[2]", raw[2]),
            _require_exact_text("source[3]", raw[3]),
            _require_exact_text("source[4]", raw[4]),
            _require_exact_int("source[5]", raw[5]),
            _require_exact_int("source[6]", raw[6]),
        )
    if kind is InputSemanticKeyKind.AUTHORITY_QUERY_CLAIM_V1:
        expected_tag = "query-claim-id"
    elif kind is InputSemanticKeyKind.AUTHORITY_MANUAL_FLATTEN_V1:
        expected_tag = "manual-flatten-id"
    elif kind is InputSemanticKeyKind.AUTHORITY_EMERGENCY_GRANT_CONSUMPTION_V1:
        expected_tag = "emergency-grant-id"
    else:
        raise TypeError("semantic key kind is not admitted")
    if len(raw) != 2 or raw[0] != expected_tag:
        raise ValueError("authority semantic key source is malformed")
    return (expected_tag, _require_exact_text("source[1]", raw[1]))


def encode_m2_semantic_key(
    kind: InputSemanticKeyKind,
    coordinates: tuple[str | int, ...],
    source: tuple[str | int, ...],
) -> bytes:
    """Encode one closed semantic-key projection into its canonical raw bytes.

    This low-level pure codec is deliberately not an operation input.  Owning
    operation code derives its coordinates and source from authenticated M1
    values and reducer state; the codec refuses every alternate kind, shape,
    type, or noncanonical value.
    """

    if type(kind) is not InputSemanticKeyKind:
        raise TypeError("kind must be InputSemanticKeyKind")
    canonical_coordinates = _validate_semantic_coordinates(kind, coordinates)
    canonical_source = _validate_semantic_source(kind, source)
    payload = _json.dumps(
        [1, kind.value, list(canonical_coordinates), list(canonical_source)],
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    kind_octet = tuple(InputSemanticKeyKind).index(kind) + 1
    return (
        _SEMANTIC_KEY_PREFIX
        + bytes((kind_octet,))
        + _struct.pack(">Q", len(payload))
        + payload
    )


def decode_m2_semantic_key(
    value: bytes,
) -> tuple[InputSemanticKeyKind, tuple[str | int, ...], tuple[str | int, ...]]:
    """Decode and re-encode one semantic key, refusing noncanonical bytes."""

    if type(value) is not bytes:
        raise TypeError("semantic key bytes must be exact bytes")
    fixed_size = len(_SEMANTIC_KEY_PREFIX) + 9
    if len(value) < fixed_size or not value.startswith(_SEMANTIC_KEY_PREFIX):
        raise ValueError("semantic key prefix is malformed")
    kind_octet = value[len(_SEMANTIC_KEY_PREFIX)]
    if kind_octet == 0:
        raise ValueError("semantic key kind octet is unknown")
    try:
        kind = tuple(InputSemanticKeyKind)[kind_octet - 1]
    except IndexError as exc:
        raise ValueError("semantic key kind octet is unknown") from exc
    length_offset = len(_SEMANTIC_KEY_PREFIX) + 1
    payload_length = _struct.unpack(">Q", value[length_offset : length_offset + 8])[0]
    payload = value[fixed_size:]
    if len(payload) != payload_length:
        raise ValueError("semantic key payload length is malformed")
    try:
        parsed = _json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, _json.JSONDecodeError) as exc:
        raise ValueError("semantic key payload is not canonical JSON") from exc
    if type(parsed) is not list or len(parsed) != 4:
        raise ValueError("semantic key payload shape is malformed")
    if type(parsed[0]) is not int or parsed[0] != 1:
        raise ValueError("semantic key payload version is malformed")
    if type(parsed[1]) is not str or parsed[1] != kind.value:
        raise ValueError("semantic key payload kind is malformed")
    if type(parsed[2]) is not list or type(parsed[3]) is not list:
        raise ValueError("semantic key payload members must be arrays")
    coordinates = _validate_semantic_coordinates(kind, tuple(parsed[2]))
    source = _validate_semantic_source(kind, tuple(parsed[3]))
    if encode_m2_semantic_key(kind, coordinates, source) != value:
        raise ValueError("semantic key bytes are not canonical")
    return kind, coordinates, source


@_dataclass(frozen=True, slots=True)
class InputSemanticKey:
    """One retained alternate-key match whose raw bytes remain authoritative."""

    kind: InputSemanticKeyKind
    canonical_key_bytes: bytes
    key_sha256: str
    retained_input_domain: str
    retained_input_identity_sha256: str

    def __post_init__(self) -> None:
        if type(self) is not InputSemanticKey:
            raise TypeError("InputSemanticKey rejects subclass instances")
        if type(self.kind) is not InputSemanticKeyKind:
            raise TypeError("kind must be InputSemanticKeyKind")
        if type(self.canonical_key_bytes) is not bytes:
            raise TypeError("canonical_key_bytes must be exact bytes")
        decoded_kind, _, _ = decode_m2_semantic_key(self.canonical_key_bytes)
        if decoded_kind is not self.kind:
            raise ValueError("semantic key kind does not match canonical key bytes")
        key_sha256 = _require_sha256("key_sha256", self.key_sha256)
        if _hashlib.sha256(self.canonical_key_bytes).hexdigest() != key_sha256:
            raise ValueError("semantic key digest does not match canonical key bytes")
        _require_exact_text("retained_input_domain", self.retained_input_domain)
        _require_sha256(
            "retained_input_identity_sha256",
            self.retained_input_identity_sha256,
        )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("InputSemanticKey cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class InputDedupeFact:
    """Repository-authenticated primary/alternate input classification."""

    kind: InputDedupeKind
    input_domain: str
    input_identity_sha256: str
    payload_sha256: str
    retained_outcome_sha256: str | None
    semantic_matches: tuple[InputSemanticKey, ...]

    def __post_init__(self) -> None:
        if type(self) is not InputDedupeFact:
            raise TypeError("InputDedupeFact rejects subclass instances")
        if type(self.kind) is not InputDedupeKind:
            raise TypeError("kind must be InputDedupeKind")
        _require_exact_text("input_domain", self.input_domain)
        _require_sha256("input_identity_sha256", self.input_identity_sha256)
        _require_sha256("payload_sha256", self.payload_sha256)
        if self.kind is InputDedupeKind.EXACT_REPLAY:
            if self.retained_outcome_sha256 is None:
                raise ValueError("exact replay requires a retained outcome digest")
            _require_sha256("retained_outcome_sha256", self.retained_outcome_sha256)
        elif self.retained_outcome_sha256 is not None:
            raise ValueError("only exact replay may retain an outcome digest")
        matches = _require_exact_tuple("semantic_matches", self.semantic_matches)
        key_bytes: list[bytes] = []
        for match in matches:
            if type(match) is not InputSemanticKey:
                raise TypeError("semantic_matches must contain InputSemanticKey values")
            if match.canonical_key_bytes in key_bytes:
                raise ValueError("semantic_matches must not duplicate a canonical key")
            key_bytes.append(match.canonical_key_bytes)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("InputDedupeFact cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class BrokerExecutionOperation:
    """One broker-authoritative canonical execution fact operation."""

    coordinates: ExecutionOperationCoordinates
    fact: (
        _fills.BrokerFillFact
        | _fills.BrokerTradeCorrectFact
        | _fills.BrokerTradeBustFact
    )

    def __post_init__(self) -> None:
        if type(self) is not BrokerExecutionOperation:
            raise TypeError("BrokerExecutionOperation rejects subclass instances")
        if type(self.coordinates) is not ExecutionOperationCoordinates:
            raise TypeError("coordinates must be ExecutionOperationCoordinates")
        if type(self.fact) not in (
            _fills.BrokerFillFact,
            _fills.BrokerTradeCorrectFact,
            _fills.BrokerTradeBustFact,
        ):
            raise TypeError("fact must be one exact broker execution fact type")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("BrokerExecutionOperation cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class VenueRecoveryOperation:
    """One admitted venue/recovery input, never an arbitrary venue command."""

    coordinates: VenueOperationCoordinates
    item: (
        _venue.RecordTransportOutcome
        | _venue.RecoverClaimedEffect
        | _venue.DiscoverVenueLeg
        | _venue.ObserveVenueStatus
        | _recovery.IngestHumanAttestedFill
        | _recovery.ReleaseVenueLeg
        | _recovery.RecordBrokerFillEvidence
        | _recovery.RecordBrokerRevisionEvidence
    )

    def __post_init__(self) -> None:
        if type(self) is not VenueRecoveryOperation:
            raise TypeError("VenueRecoveryOperation rejects subclass instances")
        if type(self.coordinates) is not VenueOperationCoordinates:
            raise TypeError("coordinates must be VenueOperationCoordinates")
        if type(self.item) not in (
            _venue.RecordTransportOutcome,
            _venue.RecoverClaimedEffect,
            _venue.DiscoverVenueLeg,
            _venue.ObserveVenueStatus,
            _recovery.IngestHumanAttestedFill,
            _recovery.ReleaseVenueLeg,
            _recovery.RecordBrokerFillEvidence,
            _recovery.RecordBrokerRevisionEvidence,
        ):
            raise TypeError("item must be one exact admitted venue recovery input")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("VenueRecoveryOperation cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class AuthorityOperation:
    """One admitted authority command, with no derivative top-level escape hatch."""

    coordinates: ExecutionOperationCoordinates
    command: (
        _authority.CreateBrokerEffect
        | _authority.ClaimEffect
        | _authority.ClaimBrokerQuery
        | _authority.EngageKill
        | _authority.BeginManualFlatten
        | _authority.AdvanceManualFlatten
    )

    def __post_init__(self) -> None:
        if type(self) is not AuthorityOperation:
            raise TypeError("AuthorityOperation rejects subclass instances")
        if type(self.coordinates) is not ExecutionOperationCoordinates:
            raise TypeError("coordinates must be ExecutionOperationCoordinates")
        if type(self.command) not in (
            _authority.CreateBrokerEffect,
            _authority.ClaimEffect,
            _authority.ClaimBrokerQuery,
            _authority.EngageKill,
            _authority.BeginManualFlatten,
            _authority.AdvanceManualFlatten,
        ):
            raise TypeError("command must be one exact admitted authority command")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("AuthorityOperation cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class BeginAcquisitionGenerationOperation:
    """Begin one exact acquisition generation with its approved successor mandate."""

    coordinates: AcquisitionOperationCoordinates
    input_id: _identity.AuthorityInputId
    successor_mandate: _acquisition.AcquisitionMandate

    def __post_init__(self) -> None:
        if type(self) is not BeginAcquisitionGenerationOperation:
            raise TypeError(
                "BeginAcquisitionGenerationOperation rejects subclass instances"
            )
        if type(self.coordinates) is not AcquisitionOperationCoordinates:
            raise TypeError("coordinates must be AcquisitionOperationCoordinates")
        if type(self.input_id) is not _identity.AuthorityInputId:
            raise TypeError("input_id must be AuthorityInputId")
        _identity.AuthorityInputId(self.input_id.value)
        if type(self.successor_mandate) is not _acquisition.AcquisitionMandate:
            raise TypeError("successor_mandate must be AcquisitionMandate")
        if not _acquisition._acquisition_mandate_is_authentic(self.successor_mandate):
            raise ValueError(
                "successor_mandate must be an authentic acquisition mandate"
            )

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("BeginAcquisitionGenerationOperation cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class CreateAcquisitionEffectOperation:
    """Create one exact acquisition effect from exact immutable terms."""

    coordinates: AcquisitionOperationCoordinates
    input_id: _identity.AuthorityInputId
    terms: _authority.AcquisitionEffectTerms

    def __post_init__(self) -> None:
        if type(self) is not CreateAcquisitionEffectOperation:
            raise TypeError(
                "CreateAcquisitionEffectOperation rejects subclass instances"
            )
        if type(self.coordinates) is not AcquisitionOperationCoordinates:
            raise TypeError("coordinates must be AcquisitionOperationCoordinates")
        if type(self.input_id) is not _identity.AuthorityInputId:
            raise TypeError("input_id must be AuthorityInputId")
        _identity.AuthorityInputId(self.input_id.value)
        if type(self.terms) is not _authority.AcquisitionEffectTerms:
            raise TypeError("terms must be AcquisitionEffectTerms")
        if not _authority._acquisition_effect_terms_is_authentic(self.terms):
            raise ValueError("terms must be authentic acquisition effect terms")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("CreateAcquisitionEffectOperation cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class ClaimAcquisitionEffectOperation:
    """Claim one previously created acquisition effect at one exact occurrence."""

    coordinates: AcquisitionOperationCoordinates
    input_id: _identity.AuthorityInputId
    effect_id: _identity.EffectId
    claim_occurrence_id: _identity.ClaimOccurrenceId

    def __post_init__(self) -> None:
        if type(self) is not ClaimAcquisitionEffectOperation:
            raise TypeError(
                "ClaimAcquisitionEffectOperation rejects subclass instances"
            )
        if type(self.coordinates) is not AcquisitionOperationCoordinates:
            raise TypeError("coordinates must be AcquisitionOperationCoordinates")
        if type(self.input_id) is not _identity.AuthorityInputId:
            raise TypeError("input_id must be AuthorityInputId")
        _identity.AuthorityInputId(self.input_id.value)
        if type(self.effect_id) is not _identity.EffectId:
            raise TypeError("effect_id must be EffectId")
        _identity.EffectId(self.effect_id.value)
        if type(self.claim_occurrence_id) is not _identity.ClaimOccurrenceId:
            raise TypeError("claim_occurrence_id must be ClaimOccurrenceId")
        _identity.ClaimOccurrenceId(self.claim_occurrence_id.value)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("ClaimAcquisitionEffectOperation cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class BeginAcquisitionPreemptionOperation:
    """Begin one exact acquisition preemption using a durable input identity."""

    coordinates: AcquisitionOperationCoordinates
    input_id: _identity.AuthorityInputId

    def __post_init__(self) -> None:
        if type(self) is not BeginAcquisitionPreemptionOperation:
            raise TypeError(
                "BeginAcquisitionPreemptionOperation rejects subclass instances"
            )
        if type(self.coordinates) is not AcquisitionOperationCoordinates:
            raise TypeError("coordinates must be AcquisitionOperationCoordinates")
        if type(self.input_id) is not _identity.AuthorityInputId:
            raise TypeError("input_id must be AuthorityInputId")
        _identity.AuthorityInputId(self.input_id.value)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("BeginAcquisitionPreemptionOperation cannot be subclassed")


@_dataclass(frozen=True, slots=True)
class MarketOccurrenceOperation:
    """Reduce one exact market occurrence against its authenticated stream state."""

    coordinates: MarketOperationCoordinates
    occurrence: _protection.MarketOccurrence

    def __post_init__(self) -> None:
        if type(self) is not MarketOccurrenceOperation:
            raise TypeError("MarketOccurrenceOperation rejects subclass instances")
        if type(self.coordinates) is not MarketOperationCoordinates:
            raise TypeError("coordinates must be MarketOperationCoordinates")
        if type(self.occurrence) is not _protection.MarketOccurrence:
            raise TypeError("occurrence must be MarketOccurrence")

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("MarketOccurrenceOperation cannot be subclassed")


M2Operation: _TypeAlias = (
    BrokerExecutionOperation
    | VenueRecoveryOperation
    | AuthorityOperation
    | BeginAcquisitionGenerationOperation
    | CreateAcquisitionEffectOperation
    | ClaimAcquisitionEffectOperation
    | BeginAcquisitionPreemptionOperation
    | MarketOccurrenceOperation
)
