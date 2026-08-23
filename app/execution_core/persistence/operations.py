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
from fractions import Fraction as _Fraction
from typing import TypeAlias as _TypeAlias
from typing import TypeVar as _TypeVar
from typing import cast as _cast

from .. import acquisition as _acquisition
from .. import authority as _authority
from .. import durable_codec as _durable_codec
from .. import fills as _fills
from .. import identity as _identity
from .. import protection as _protection
from .. import recovery as _recovery
from .. import venue as _venue
from .. import values as _values


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
    "decode_m2_operation",
    "decode_m2_semantic_key",
    "encode_m2_operation",
    "encode_m2_semantic_key",
)


_SEMANTIC_KEY_PREFIX = b"execution-core/m2-semantic-key/v1\n"
_M2_DOCUMENT_PREFIX = b"execution-core/m2-document/v1\n"
_M2_OPERATION_DOCUMENT_KIND = 0x01
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


def _encode_m2_durable_atom(atom: _durable_codec.DurableAtom) -> list[object]:
    if type(atom) is not _durable_codec.DurableAtom:
        raise TypeError("durable atom must be exact DurableAtom")
    encoded_fields: list[object] = []
    for field in atom.fields:
        if type(field) is str:
            encoded_fields.append(field)
        elif type(field) is _durable_codec.DurableAtom:
            encoded_fields.append(_encode_m2_durable_atom(field))
        else:
            raise TypeError("durable atom field is malformed")
    return [atom.contract_version, atom.type_tag, encoded_fields]


def _decode_m2_durable_atom(value: object) -> _durable_codec.DurableAtom:
    if type(value) is not list or len(value) != 3:
        raise ValueError("durable atom must be a three-member array")
    contract_version, type_tag, raw_fields = value
    if type(contract_version) is not str or type(type_tag) is not str:
        raise TypeError("durable atom version and tag must be exact text")
    if type(raw_fields) is not list:
        raise TypeError("durable atom fields must be an array")
    decoded_fields: list[str | _durable_codec.DurableAtom] = []
    for raw_field in raw_fields:
        if type(raw_field) is str:
            decoded_fields.append(raw_field)
        elif type(raw_field) is list:
            decoded_fields.append(_decode_m2_durable_atom(raw_field))
        else:
            raise TypeError("durable atom field is malformed")
    atom = _durable_codec.DurableAtom(
        contract_version,
        type_tag,
        tuple(decoded_fields),
    )
    if _encode_m2_durable_atom(atom) != value:
        raise ValueError("durable atom is not canonical")
    return atom


def _encode_m2_m1_atom(value: _durable_codec._OwningValue) -> list[object]:
    return _encode_m2_durable_atom(_durable_codec.encode_m1_value(value))


def _decode_m2_m1_atom(value: object) -> object:
    atom = _decode_m2_durable_atom(value)
    return _durable_codec.decode_m1_value(atom)


def _encode_m2_enum(value: object) -> list[str]:
    if type(value) is OperationDomain:
        return ["m2.operations.OperationDomain", value.value]
    if type(value) is _fills.ExecutionSide:
        return ["m1.fills.ExecutionSide", value.value]
    if type(value) is _venue.EffectKind:
        return ["m1.venue.EffectKind", value.value]
    if type(value) is _venue.BrokerEffectState:
        return ["m1.venue.BrokerEffectState", value.value]
    if type(value) is _venue.VenueAttemptState:
        return ["m1.venue.VenueAttemptState", value.value]
    if type(value) is _authority.AuthorityQueryKind:
        return ["m1.authority.AuthorityQueryKind", value.value]
    if type(value) is _authority.AcquisitionOrderType:
        return ["m1.authority.AcquisitionOrderType", value.value]
    if type(value) is _protection.MarketKind:
        return ["m1.protection.MarketKind", value.value]
    if type(value) is _protection.MarketSequenceMode:
        return ["m1.protection.MarketSequenceMode", value.value]
    raise TypeError("enum is not admitted by the M2 operation wire contract")


def _decode_m2_enum(value: object) -> object:
    if type(value) is not list or len(value) != 2:
        raise ValueError("enum must be a two-member array")
    owner_tag, enum_value = value
    if type(owner_tag) is not str or type(enum_value) is not str:
        raise TypeError("enum owner tag and value must be exact text")
    try:
        if owner_tag == "m2.operations.OperationDomain":
            decoded: object = OperationDomain(enum_value)
        elif owner_tag == "m1.fills.ExecutionSide":
            decoded = _fills.ExecutionSide(enum_value)
        elif owner_tag == "m1.venue.EffectKind":
            decoded = _venue.EffectKind(enum_value)
        elif owner_tag == "m1.venue.BrokerEffectState":
            decoded = _venue.BrokerEffectState(enum_value)
        elif owner_tag == "m1.venue.VenueAttemptState":
            decoded = _venue.VenueAttemptState(enum_value)
        elif owner_tag == "m1.authority.AuthorityQueryKind":
            decoded = _authority.AuthorityQueryKind(enum_value)
        elif owner_tag == "m1.authority.AcquisitionOrderType":
            decoded = _authority.AcquisitionOrderType(enum_value)
        elif owner_tag == "m1.protection.MarketKind":
            decoded = _protection.MarketKind(enum_value)
        elif owner_tag == "m1.protection.MarketSequenceMode":
            decoded = _protection.MarketSequenceMode(enum_value)
        else:
            raise ValueError("enum owner tag is not admitted")
    except ValueError as exc:
        raise ValueError("enum value is not admitted") from exc
    if _encode_m2_enum(decoded) != value:
        raise ValueError("enum is not canonical")
    return decoded


_M1ValueT = _TypeVar("_M1ValueT")


def _decode_m2_m1_as(
    name: str,
    value: object,
    expected: type[_M1ValueT],
) -> _M1ValueT:
    decoded = _decode_m2_m1_atom(value)
    if type(decoded) is not expected:
        raise ValueError(f"{name} must decode to {expected.__name__}")
    return _cast(_M1ValueT, decoded)


def _encode_m2_coordinates(value: object) -> list[object]:
    if type(value) is ExecutionOperationCoordinates:
        return [
            "m2.operations.ExecutionOperationCoordinates/v1",
            _encode_m2_m1_atom(value.application_generation_id),
            value.execution_profile_id,
            value.scope_id,
        ]
    if type(value) is VenueOperationCoordinates:
        return [
            "m2.operations.VenueOperationCoordinates/v1",
            _encode_m2_m1_atom(value.application_generation_id),
            value.execution_profile_id,
            value.scope_id,
            None if value.session_id is None else _encode_m2_m1_atom(value.session_id),
        ]
    if type(value) is AcquisitionOperationCoordinates:
        return [
            "m2.operations.AcquisitionOperationCoordinates/v1",
            _encode_m2_m1_atom(value.application_generation_id),
            value.execution_profile_id,
            value.scope_id,
            _encode_m2_m1_atom(value.session_id),
            _encode_m2_m1_atom(value.acquisition_generation_id),
        ]
    if type(value) is MarketOperationCoordinates:
        return [
            "m2.operations.MarketOperationCoordinates/v1",
            _encode_m2_m1_atom(value.application_generation_id),
            value.execution_profile_id,
            value.scope_id,
            _encode_m2_m1_atom(value.session_id),
            _encode_m2_m1_atom(value.acquisition_generation_id),
            value.market_source_profile_id,
            _encode_m2_m1_atom(value.stream_generation_id),
        ]
    raise TypeError("coordinates are not admitted by the M2 operation wire contract")


def _decode_m2_coordinates(
    value: object,
) -> (
    ExecutionOperationCoordinates
    | VenueOperationCoordinates
    | AcquisitionOperationCoordinates
    | MarketOperationCoordinates
):
    if type(value) is not list or not value:
        raise ValueError("coordinate array is malformed")
    coordinate_tag = value[0]
    if type(coordinate_tag) is not str:
        raise TypeError("coordinate tag must be exact text")
    if coordinate_tag == "m2.operations.ExecutionOperationCoordinates/v1":
        if len(value) != 4:
            raise ValueError("execution coordinate array is malformed")
        application_generation_id = _decode_m2_m1_as(
            "application_generation_id",
            value[1],
            _identity.ApplicationGenerationId,
        )
        execution_profile_id = _require_exact_text("execution_profile_id", value[2])
        scope_id = _require_exact_int("scope_id", value[3])
        decoded: (
            ExecutionOperationCoordinates
            | VenueOperationCoordinates
            | AcquisitionOperationCoordinates
            | MarketOperationCoordinates
        ) = ExecutionOperationCoordinates(
            application_generation_id,
            execution_profile_id,
            scope_id,
        )
    elif coordinate_tag == "m2.operations.VenueOperationCoordinates/v1":
        if len(value) != 5:
            raise ValueError("venue coordinate array is malformed")
        application_generation_id = _decode_m2_m1_as(
            "application_generation_id",
            value[1],
            _identity.ApplicationGenerationId,
        )
        execution_profile_id = _require_exact_text("execution_profile_id", value[2])
        scope_id = _require_exact_int("scope_id", value[3])
        session_id = (
            None
            if value[4] is None
            else _decode_m2_m1_as("session_id", value[4], _identity.SessionId)
        )
        decoded = VenueOperationCoordinates(
            application_generation_id,
            execution_profile_id,
            scope_id,
            session_id,
        )
    elif coordinate_tag == "m2.operations.AcquisitionOperationCoordinates/v1":
        if len(value) != 6:
            raise ValueError("acquisition coordinate array is malformed")
        application_generation_id = _decode_m2_m1_as(
            "application_generation_id",
            value[1],
            _identity.ApplicationGenerationId,
        )
        execution_profile_id = _require_exact_text("execution_profile_id", value[2])
        scope_id = _require_exact_int("scope_id", value[3])
        session_id = _decode_m2_m1_as("session_id", value[4], _identity.SessionId)
        acquisition_generation_id = _decode_m2_m1_as(
            "acquisition_generation_id",
            value[5],
            _identity.AcquisitionGenerationId,
        )
        decoded = AcquisitionOperationCoordinates(
            application_generation_id,
            execution_profile_id,
            scope_id,
            session_id,
            acquisition_generation_id,
        )
    elif coordinate_tag == "m2.operations.MarketOperationCoordinates/v1":
        if len(value) != 8:
            raise ValueError("market coordinate array is malformed")
        application_generation_id = _decode_m2_m1_as(
            "application_generation_id",
            value[1],
            _identity.ApplicationGenerationId,
        )
        execution_profile_id = _require_exact_text("execution_profile_id", value[2])
        scope_id = _require_exact_int("scope_id", value[3])
        session_id = _decode_m2_m1_as("session_id", value[4], _identity.SessionId)
        acquisition_generation_id = _decode_m2_m1_as(
            "acquisition_generation_id",
            value[5],
            _identity.AcquisitionGenerationId,
        )
        market_source_profile_id = _require_exact_text(
            "market_source_profile_id",
            value[6],
        )
        stream_generation_id = _decode_m2_m1_as(
            "stream_generation_id",
            value[7],
            _identity.MarketStreamGenerationId,
        )
        decoded = MarketOperationCoordinates(
            application_generation_id,
            execution_profile_id,
            scope_id,
            session_id,
            acquisition_generation_id,
            market_source_profile_id,
            stream_generation_id,
        )
    else:
        raise ValueError("coordinate tag is not admitted")
    if _encode_m2_coordinates(decoded) != value:
        raise ValueError("coordinate array is not canonical")
    return decoded


def _encode_m2_document(payload: list[object]) -> bytes:
    if type(payload) is not list:
        raise TypeError("M2 document payload must be an exact array")
    encoded_payload = _json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return (
        _M2_DOCUMENT_PREFIX
        + bytes((_M2_OPERATION_DOCUMENT_KIND,))
        + _struct.pack(">Q", len(encoded_payload))
        + encoded_payload
    )


def _decode_m2_document(value: object) -> list[object]:
    if type(value) is not bytes:
        raise TypeError("M2 document must be exact bytes")
    fixed_size = len(_M2_DOCUMENT_PREFIX) + 9
    if len(value) < fixed_size or not value.startswith(_M2_DOCUMENT_PREFIX):
        raise ValueError("M2 document prefix is malformed")
    kind_octet = value[len(_M2_DOCUMENT_PREFIX)]
    if kind_octet != _M2_OPERATION_DOCUMENT_KIND:
        raise ValueError("M2 document kind is not an operation")
    length_offset = len(_M2_DOCUMENT_PREFIX) + 1
    payload_length = _struct.unpack(">Q", value[length_offset : length_offset + 8])[0]
    payload = value[fixed_size:]
    if len(payload) != payload_length:
        raise ValueError("M2 document payload length is malformed")
    try:
        decoded = _json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, _json.JSONDecodeError) as exc:
        raise ValueError("M2 document payload is not canonical JSON") from exc
    if type(decoded) is not list:
        raise ValueError("M2 document payload must be an array")
    try:
        if _encode_m2_document(decoded) != value:
            raise ValueError("M2 document bytes are not canonical")
    except (TypeError, ValueError) as exc:
        raise ValueError("M2 document payload is not canonical") from exc
    return decoded


def _encode_m2_bytes(value: object) -> str:
    if type(value) is not bytes:
        raise TypeError("M2 byte field must be exact bytes")
    return value.hex()


def _decode_m2_bytes(name: str, value: object) -> bytes:
    text = _require_exact_text(name, value)
    if len(text) % 2 != 0 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise ValueError(f"{name} must be lowercase even-length hexadecimal text")
    decoded = bytes.fromhex(text)
    if _encode_m2_bytes(decoded) != value:
        raise ValueError(f"{name} is not canonical")
    return decoded


def _encode_m2_fraction(value: object) -> list[object]:
    if type(value) is not _Fraction:
        raise TypeError("fraction must be exact Fraction")
    return ["m2.scalar.Fraction/v1", value.numerator, value.denominator]


def _decode_m2_fraction(value: object) -> _Fraction:
    fields = _require_m2_aggregate(value, "m2.scalar.Fraction/v1", 2)
    numerator = _require_exact_int("fraction numerator", fields[0])
    denominator = _require_exact_int("fraction denominator", fields[1])
    if denominator <= 0:
        raise ValueError("fraction denominator must be positive")
    decoded = _Fraction(numerator, denominator)
    if _encode_m2_fraction(decoded) != value:
        raise ValueError("fraction is not reduced and canonical")
    return decoded


_EnumValueT = _TypeVar("_EnumValueT", bound=_Enum)


def _decode_m2_enum_as(
    name: str,
    value: object,
    expected: type[_EnumValueT],
) -> _EnumValueT:
    decoded = _decode_m2_enum(value)
    if type(decoded) is not expected:
        raise ValueError(f"{name} must decode to {expected.__name__}")
    return _cast(_EnumValueT, decoded)


def _decode_m2_optional_m1_as(
    name: str,
    value: object,
    expected: type[_M1ValueT],
) -> _M1ValueT | None:
    if value is None:
        return None
    return _decode_m2_m1_as(name, value, expected)


def _require_m2_aggregate(
    value: object,
    expected_tag: str,
    field_count: int,
) -> list[object]:
    if type(value) is not list or len(value) != field_count + 1:
        raise ValueError(f"{expected_tag} aggregate has the wrong member count")
    if value[0] != expected_tag:
        raise ValueError(f"aggregate must have exact tag {expected_tag}")
    return value[1:]


def _encode_m2_position_scope(value: object) -> list[object]:
    if type(value) is not _fills.PositionScope:
        raise TypeError("position scope must be exact PositionScope")
    return [
        "m1.fills.PositionScope/v1",
        _encode_m2_m1_atom(value.broker),
        _encode_m2_m1_atom(value.environment),
        _encode_m2_m1_atom(value.account),
        _encode_m2_m1_atom(value.symbol_id),
    ]


def _decode_m2_position_scope(value: object) -> _fills.PositionScope:
    fields = _require_m2_aggregate(value, "m1.fills.PositionScope/v1", 4)
    decoded = _fills.PositionScope(
        _decode_m2_m1_as("position scope broker", fields[0], _identity.BrokerId),
        _decode_m2_m1_as(
            "position scope environment", fields[1], _identity.EnvironmentId
        ),
        _decode_m2_m1_as("position scope account", fields[2], _identity.AccountId),
        _decode_m2_m1_as("position scope symbol", fields[3], _identity.SymbolId),
    )
    if _encode_m2_position_scope(decoded) != value:
        raise ValueError("position scope is not canonical")
    return decoded


def _encode_m2_execution_scope(value: object) -> list[object]:
    if type(value) is not _fills.ExecutionScope:
        raise TypeError("execution scope must be exact ExecutionScope")
    return [
        "m1.fills.ExecutionScope/v1",
        _encode_m2_m1_atom(value.broker),
        _encode_m2_m1_atom(value.environment),
        _encode_m2_m1_atom(value.account),
        _encode_m2_m1_atom(value.order_id),
        _encode_m2_m1_atom(value.symbol_id),
        _encode_m2_enum(value.side),
    ]


def _decode_m2_execution_scope(value: object) -> _fills.ExecutionScope:
    fields = _require_m2_aggregate(value, "m1.fills.ExecutionScope/v1", 6)
    decoded = _fills.ExecutionScope(
        _decode_m2_m1_as("execution scope broker", fields[0], _identity.BrokerId),
        _decode_m2_m1_as(
            "execution scope environment", fields[1], _identity.EnvironmentId
        ),
        _decode_m2_m1_as("execution scope account", fields[2], _identity.AccountId),
        _decode_m2_m1_as("execution scope order", fields[3], _identity.OrderId),
        _decode_m2_m1_as("execution scope symbol", fields[4], _identity.SymbolId),
        _decode_m2_enum_as("execution scope side", fields[5], _fills.ExecutionSide),
    )
    if _encode_m2_execution_scope(decoded) != value:
        raise ValueError("execution scope is not canonical")
    return decoded


def _encode_m2_broker_fill_fact(value: object) -> list[object]:
    if type(value) is not _fills.BrokerFillFact:
        raise TypeError("broker fill fact must be exact BrokerFillFact")
    return [
        "m1.fills.BrokerFillFact/v1",
        _encode_m2_m1_atom(value.key),
        _encode_m2_execution_scope(value.scope),
        _encode_m2_m1_atom(value.root_fill_id),
        _encode_m2_m1_atom(value.quantity),
        _encode_m2_m1_atom(value.price),
    ]


def _decode_m2_broker_fill_fact(value: object) -> _fills.BrokerFillFact:
    fields = _require_m2_aggregate(value, "m1.fills.BrokerFillFact/v1", 5)
    decoded = _fills.BrokerFillFact(
        _decode_m2_m1_as("broker fill key", fields[0], _identity.ExecutionFactKey),
        _decode_m2_execution_scope(fields[1]),
        _decode_m2_m1_as("broker fill root", fields[2], _identity.RootFillId),
        _decode_m2_m1_as("broker fill quantity", fields[3], _values.Quantity),
        _decode_m2_m1_as("broker fill price", fields[4], _values.ReportedPrice),
    )
    if _encode_m2_broker_fill_fact(decoded) != value:
        raise ValueError("broker fill fact is not canonical")
    return decoded


def _encode_m2_broker_trade_correct_fact(value: object) -> list[object]:
    if type(value) is not _fills.BrokerTradeCorrectFact:
        raise TypeError("broker trade correction must be exact BrokerTradeCorrectFact")
    return [
        "m1.fills.BrokerTradeCorrectFact/v1",
        _encode_m2_m1_atom(value.key),
        _encode_m2_execution_scope(value.scope),
        _encode_m2_m1_atom(value.root_fill_id),
        _encode_m2_m1_atom(value.predecessor_source_event_id),
        _encode_m2_m1_atom(value.revised_quantity),
        _encode_m2_m1_atom(value.revised_price),
    ]


def _decode_m2_broker_trade_correct_fact(
    value: object,
) -> _fills.BrokerTradeCorrectFact:
    fields = _require_m2_aggregate(value, "m1.fills.BrokerTradeCorrectFact/v1", 6)
    decoded = _fills.BrokerTradeCorrectFact(
        _decode_m2_m1_as(
            "broker correction key", fields[0], _identity.ExecutionFactKey
        ),
        _decode_m2_execution_scope(fields[1]),
        _decode_m2_m1_as("broker correction root", fields[2], _identity.RootFillId),
        _decode_m2_m1_as(
            "broker correction predecessor", fields[3], _identity.SourceEventId
        ),
        _decode_m2_m1_as("broker correction quantity", fields[4], _values.Quantity),
        _decode_m2_m1_as("broker correction price", fields[5], _values.ReportedPrice),
    )
    if _encode_m2_broker_trade_correct_fact(decoded) != value:
        raise ValueError("broker trade correction is not canonical")
    return decoded


def _encode_m2_broker_trade_bust_fact(value: object) -> list[object]:
    if type(value) is not _fills.BrokerTradeBustFact:
        raise TypeError("broker trade bust must be exact BrokerTradeBustFact")
    return [
        "m1.fills.BrokerTradeBustFact/v1",
        _encode_m2_m1_atom(value.key),
        _encode_m2_execution_scope(value.scope),
        _encode_m2_m1_atom(value.root_fill_id),
        _encode_m2_m1_atom(value.predecessor_source_event_id),
        None
        if value.reported_price is None
        else _encode_m2_m1_atom(value.reported_price),
    ]


def _decode_m2_broker_trade_bust_fact(value: object) -> _fills.BrokerTradeBustFact:
    fields = _require_m2_aggregate(value, "m1.fills.BrokerTradeBustFact/v1", 5)
    decoded = _fills.BrokerTradeBustFact(
        _decode_m2_m1_as("broker bust key", fields[0], _identity.ExecutionFactKey),
        _decode_m2_execution_scope(fields[1]),
        _decode_m2_m1_as("broker bust root", fields[2], _identity.RootFillId),
        _decode_m2_m1_as("broker bust predecessor", fields[3], _identity.SourceEventId),
        _decode_m2_optional_m1_as(
            "broker bust reported price", fields[4], _values.ReportedPrice
        ),
    )
    if _encode_m2_broker_trade_bust_fact(decoded) != value:
        raise ValueError("broker trade bust is not canonical")
    return decoded


def _encode_m2_human_attested_fill_fact(value: object) -> list[object]:
    if type(value) is not _fills.HumanAttestedFillFact:
        raise TypeError("human fact must be exact HumanAttestedFillFact")
    return [
        "m1.fills.HumanAttestedFillFact/v1",
        _encode_m2_m1_atom(value.key),
        _encode_m2_execution_scope(value.scope),
        _encode_m2_m1_atom(value.root_fill_id),
        _encode_m2_m1_atom(value.leg_key),
        _encode_m2_m1_atom(value.request_occurrence_id),
        _encode_m2_m1_atom(value.claim_occurrence_id),
        _encode_m2_m1_atom(value.quantity),
        _encode_m2_m1_atom(value.prior_cumulative_quantity),
        _encode_m2_m1_atom(value.resulting_cumulative_quantity),
        _encode_m2_m1_atom(value.price),
        _encode_m2_m1_atom(value.actor),
        value.reason,
        _encode_m2_m1_atom(value.evidence_reference),
    ]


def _decode_m2_human_attested_fill_fact(
    value: object,
) -> _fills.HumanAttestedFillFact:
    fields = _require_m2_aggregate(value, "m1.fills.HumanAttestedFillFact/v1", 13)
    decoded = _fills.HumanAttestedFillFact(
        _decode_m2_m1_as("human fill key", fields[0], _identity.ExecutionFactKey),
        _decode_m2_execution_scope(fields[1]),
        _decode_m2_m1_as("human fill root", fields[2], _identity.RootFillId),
        _decode_m2_m1_as("human fill leg", fields[3], _identity.VenueLegKey),
        _decode_m2_m1_as(
            "human fill request", fields[4], _identity.RequestOccurrenceId
        ),
        _decode_m2_m1_as("human fill claim", fields[5], _identity.ClaimOccurrenceId),
        _decode_m2_m1_as("human fill quantity", fields[6], _values.Quantity),
        _decode_m2_m1_as("human fill prior", fields[7], _values.Quantity),
        _decode_m2_m1_as("human fill resulting", fields[8], _values.Quantity),
        _decode_m2_m1_as("human fill price", fields[9], _values.ReportedPrice),
        _decode_m2_m1_as("human fill actor", fields[10], _identity.ActorId),
        _require_exact_text("human fill reason", fields[11]),
        _decode_m2_m1_as(
            "human fill evidence", fields[12], _identity.EvidenceReference
        ),
    )
    if _encode_m2_human_attested_fill_fact(decoded) != value:
        raise ValueError("human attested fill fact is not canonical")
    return decoded


def _encode_m2_broker_execution_fact(value: object) -> list[object]:
    if type(value) is _fills.BrokerFillFact:
        return _encode_m2_broker_fill_fact(value)
    if type(value) is _fills.BrokerTradeCorrectFact:
        return _encode_m2_broker_trade_correct_fact(value)
    if type(value) is _fills.BrokerTradeBustFact:
        return _encode_m2_broker_trade_bust_fact(value)
    raise TypeError("value is not an admitted broker execution fact")


def _decode_m2_broker_execution_fact(
    value: object,
) -> _fills.BrokerExecutionFact:
    if type(value) is not list or not value or type(value[0]) is not str:
        raise ValueError("broker execution fact aggregate is malformed")
    tag = value[0]
    if tag == "m1.fills.BrokerFillFact/v1":
        return _decode_m2_broker_fill_fact(value)
    if tag == "m1.fills.BrokerTradeCorrectFact/v1":
        return _decode_m2_broker_trade_correct_fact(value)
    if tag == "m1.fills.BrokerTradeBustFact/v1":
        return _decode_m2_broker_trade_bust_fact(value)
    raise ValueError("broker execution fact tag is not admitted")


def _encode_m2_record_transport_outcome(value: object) -> list[object]:
    if type(value) is not _venue.RecordTransportOutcome:
        raise TypeError("transport outcome must be exact RecordTransportOutcome")
    return [
        "m1.venue.RecordTransportOutcome/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.effect_id),
        _encode_m2_enum(value.state),
    ]


def _decode_m2_record_transport_outcome(
    value: object,
) -> _venue.RecordTransportOutcome:
    fields = _require_m2_aggregate(value, "m1.venue.RecordTransportOutcome/v1", 3)
    decoded = _venue.RecordTransportOutcome(
        _decode_m2_m1_as("transport input", fields[0], _identity.VenueInputId),
        _decode_m2_m1_as("transport effect", fields[1], _identity.EffectId),
        _decode_m2_enum_as("transport state", fields[2], _venue.BrokerEffectState),
    )
    if _encode_m2_record_transport_outcome(decoded) != value:
        raise ValueError("transport outcome is not canonical")
    return decoded


def _encode_m2_recover_claimed_effect(value: object) -> list[object]:
    if type(value) is not _venue.RecoverClaimedEffect:
        raise TypeError("recovery command must be exact RecoverClaimedEffect")
    return [
        "m1.venue.RecoverClaimedEffect/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.effect_id),
    ]


def _decode_m2_recover_claimed_effect(value: object) -> _venue.RecoverClaimedEffect:
    fields = _require_m2_aggregate(value, "m1.venue.RecoverClaimedEffect/v1", 2)
    decoded = _venue.RecoverClaimedEffect(
        _decode_m2_m1_as("recovery input", fields[0], _identity.VenueInputId),
        _decode_m2_m1_as("recovery effect", fields[1], _identity.EffectId),
    )
    if _encode_m2_recover_claimed_effect(decoded) != value:
        raise ValueError("recovery command is not canonical")
    return decoded


def _encode_m2_discover_venue_leg(value: object) -> list[object]:
    if type(value) is not _venue.DiscoverVenueLeg:
        raise TypeError("venue leg discovery must be exact DiscoverVenueLeg")
    return [
        "m1.venue.DiscoverVenueLeg/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.effect_id),
        _encode_m2_m1_atom(value.leg_key),
        _encode_m2_m1_atom(value.observation_id),
    ]


def _decode_m2_discover_venue_leg(value: object) -> _venue.DiscoverVenueLeg:
    fields = _require_m2_aggregate(value, "m1.venue.DiscoverVenueLeg/v1", 4)
    decoded = _venue.DiscoverVenueLeg(
        _decode_m2_m1_as("discovery input", fields[0], _identity.VenueInputId),
        _decode_m2_m1_as("discovery effect", fields[1], _identity.EffectId),
        _decode_m2_m1_as("discovery leg", fields[2], _identity.VenueLegKey),
        _decode_m2_m1_as(
            "discovery observation", fields[3], _identity.VenueObservationId
        ),
    )
    if _encode_m2_discover_venue_leg(decoded) != value:
        raise ValueError("venue leg discovery is not canonical")
    return decoded


def _encode_m2_observe_venue_status(value: object) -> list[object]:
    if type(value) is not _venue.ObserveVenueStatus:
        raise TypeError("venue status must be exact ObserveVenueStatus")
    return [
        "m1.venue.ObserveVenueStatus/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.leg_key),
        _encode_m2_enum(value.status),
        _encode_m2_m1_atom(value.observation_id),
        _encode_m2_m1_atom(value.cumulative_quantity),
        None if value.closure_id is None else _encode_m2_m1_atom(value.closure_id),
        None
        if value.evidence_reference is None
        else _encode_m2_m1_atom(value.evidence_reference),
    ]


def _decode_m2_observe_venue_status(value: object) -> _venue.ObserveVenueStatus:
    fields = _require_m2_aggregate(value, "m1.venue.ObserveVenueStatus/v1", 7)
    decoded = _venue.ObserveVenueStatus(
        _decode_m2_m1_as("venue status input", fields[0], _identity.VenueInputId),
        _decode_m2_m1_as("venue status leg", fields[1], _identity.VenueLegKey),
        _decode_m2_enum_as("venue status", fields[2], _venue.VenueAttemptState),
        _decode_m2_m1_as(
            "venue status observation", fields[3], _identity.VenueObservationId
        ),
        _decode_m2_m1_as("venue status quantity", fields[4], _values.Quantity),
        _decode_m2_optional_m1_as(
            "venue status closure", fields[5], _identity.ClosureId
        ),
        _decode_m2_optional_m1_as(
            "venue status evidence", fields[6], _identity.EvidenceReference
        ),
    )
    if _encode_m2_observe_venue_status(decoded) != value:
        raise ValueError("venue status is not canonical")
    return decoded


def _encode_m2_ingest_human_attested_fill(value: object) -> list[object]:
    if type(value) is not _recovery.IngestHumanAttestedFill:
        raise TypeError("human fill command must be exact IngestHumanAttestedFill")
    return [
        "m1.recovery.IngestHumanAttestedFill/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.effect_id),
        _encode_m2_human_attested_fill_fact(value.fact),
    ]


def _decode_m2_ingest_human_attested_fill(
    value: object,
) -> _recovery.IngestHumanAttestedFill:
    fields = _require_m2_aggregate(value, "m1.recovery.IngestHumanAttestedFill/v1", 3)
    decoded = _recovery.IngestHumanAttestedFill(
        _decode_m2_m1_as("human command input", fields[0], _identity.VenueInputId),
        _decode_m2_m1_as("human command effect", fields[1], _identity.EffectId),
        _decode_m2_human_attested_fill_fact(fields[2]),
    )
    if _encode_m2_ingest_human_attested_fill(decoded) != value:
        raise ValueError("human fill command is not canonical")
    return decoded


def _encode_m2_release_venue_leg(value: object) -> list[object]:
    if type(value) is not _recovery.ReleaseVenueLeg:
        raise TypeError("venue release must be exact ReleaseVenueLeg")
    return [
        "m1.recovery.ReleaseVenueLeg/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.effect_id),
        _encode_m2_m1_atom(value.leg_key),
        _encode_m2_m1_atom(value.claim_occurrence_id),
        _encode_m2_m1_atom(value.venue_cumulative_quantity),
        _encode_m2_enum(value.broker_terminal_state),
        _encode_m2_m1_atom(value.actor),
        value.reason,
        _encode_m2_m1_atom(value.evidence_reference),
        _encode_m2_m1_atom(value.closure_id),
        _encode_m2_bytes(value.evidence_digest),
    ]


def _decode_m2_release_venue_leg(value: object) -> _recovery.ReleaseVenueLeg:
    fields = _require_m2_aggregate(value, "m1.recovery.ReleaseVenueLeg/v1", 11)
    decoded = _recovery.ReleaseVenueLeg(
        _decode_m2_m1_as("release input", fields[0], _identity.VenueInputId),
        _decode_m2_m1_as("release effect", fields[1], _identity.EffectId),
        _decode_m2_m1_as("release leg", fields[2], _identity.VenueLegKey),
        _decode_m2_m1_as("release claim", fields[3], _identity.ClaimOccurrenceId),
        _decode_m2_m1_as("release quantity", fields[4], _values.Quantity),
        _decode_m2_enum_as(
            "release terminal state", fields[5], _venue.VenueAttemptState
        ),
        _decode_m2_m1_as("release actor", fields[6], _identity.ActorId),
        _require_exact_text("release reason", fields[7]),
        _decode_m2_m1_as("release evidence", fields[8], _identity.EvidenceReference),
        _decode_m2_m1_as("release closure", fields[9], _identity.ClosureId),
        _decode_m2_bytes("release evidence digest", fields[10]),
    )
    if _encode_m2_release_venue_leg(decoded) != value:
        raise ValueError("venue release is not canonical")
    return decoded


def _encode_m2_record_broker_fill_evidence(value: object) -> list[object]:
    if type(value) is not _recovery.RecordBrokerFillEvidence:
        raise TypeError("broker fill evidence must be exact RecordBrokerFillEvidence")
    return [
        "m1.recovery.RecordBrokerFillEvidence/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.effect_id),
        _encode_m2_m1_atom(value.leg_key),
        _encode_m2_m1_atom(value.prior_cumulative_quantity),
        _encode_m2_m1_atom(value.resulting_cumulative_quantity),
        _encode_m2_broker_fill_fact(value.fact),
        _encode_m2_bytes(value.evidence_digest),
        None if value.closure_id is None else _encode_m2_m1_atom(value.closure_id),
        None
        if value.evidence_reference is None
        else _encode_m2_m1_atom(value.evidence_reference),
    ]


def _decode_m2_record_broker_fill_evidence(
    value: object,
) -> _recovery.RecordBrokerFillEvidence:
    fields = _require_m2_aggregate(value, "m1.recovery.RecordBrokerFillEvidence/v1", 9)
    decoded = _recovery.RecordBrokerFillEvidence(
        _decode_m2_m1_as(
            "broker fill evidence input", fields[0], _identity.VenueInputId
        ),
        _decode_m2_m1_as("broker fill evidence effect", fields[1], _identity.EffectId),
        _decode_m2_m1_as("broker fill evidence leg", fields[2], _identity.VenueLegKey),
        _decode_m2_m1_as("broker fill evidence prior", fields[3], _values.Quantity),
        _decode_m2_m1_as("broker fill evidence resulting", fields[4], _values.Quantity),
        _decode_m2_broker_fill_fact(fields[5]),
        _decode_m2_bytes("broker fill evidence digest", fields[6]),
        _decode_m2_optional_m1_as(
            "broker fill evidence closure", fields[7], _identity.ClosureId
        ),
        _decode_m2_optional_m1_as(
            "broker fill evidence reference", fields[8], _identity.EvidenceReference
        ),
    )
    if _encode_m2_record_broker_fill_evidence(decoded) != value:
        raise ValueError("broker fill evidence is not canonical")
    return decoded


def _encode_m2_record_broker_revision_evidence(value: object) -> list[object]:
    if type(value) is not _recovery.RecordBrokerRevisionEvidence:
        raise TypeError(
            "broker revision evidence must be exact RecordBrokerRevisionEvidence"
        )
    if type(value.fact) not in {
        _fills.BrokerTradeCorrectFact,
        _fills.BrokerTradeBustFact,
    }:
        raise TypeError("broker revision evidence requires correction or bust fact")
    return [
        "m1.recovery.RecordBrokerRevisionEvidence/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.effect_id),
        _encode_m2_m1_atom(value.leg_key),
        _encode_m2_m1_atom(value.prior_root_quantity),
        _encode_m2_m1_atom(value.prior_venue_cumulative_quantity),
        _encode_m2_m1_atom(value.resulting_venue_cumulative_quantity),
        _encode_m2_broker_execution_fact(value.fact),
        _encode_m2_bytes(value.evidence_digest),
        None if value.closure_id is None else _encode_m2_m1_atom(value.closure_id),
        None
        if value.evidence_reference is None
        else _encode_m2_m1_atom(value.evidence_reference),
    ]


def _decode_m2_record_broker_revision_evidence(
    value: object,
) -> _recovery.RecordBrokerRevisionEvidence:
    fields = _require_m2_aggregate(
        value, "m1.recovery.RecordBrokerRevisionEvidence/v1", 10
    )
    fact = _decode_m2_broker_execution_fact(fields[6])
    if type(fact) not in {_fills.BrokerTradeCorrectFact, _fills.BrokerTradeBustFact}:
        raise ValueError("broker revision evidence requires correction or bust fact")
    revision_fact = _cast(
        _fills.BrokerTradeCorrectFact | _fills.BrokerTradeBustFact,
        fact,
    )
    decoded = _recovery.RecordBrokerRevisionEvidence(
        _decode_m2_m1_as(
            "broker revision evidence input", fields[0], _identity.VenueInputId
        ),
        _decode_m2_m1_as(
            "broker revision evidence effect", fields[1], _identity.EffectId
        ),
        _decode_m2_m1_as(
            "broker revision evidence leg", fields[2], _identity.VenueLegKey
        ),
        _decode_m2_m1_as("broker revision evidence root", fields[3], _values.Quantity),
        _decode_m2_m1_as("broker revision evidence prior", fields[4], _values.Quantity),
        _decode_m2_m1_as(
            "broker revision evidence resulting", fields[5], _values.Quantity
        ),
        revision_fact,
        _decode_m2_bytes("broker revision evidence digest", fields[7]),
        _decode_m2_optional_m1_as(
            "broker revision evidence closure", fields[8], _identity.ClosureId
        ),
        _decode_m2_optional_m1_as(
            "broker revision evidence reference", fields[9], _identity.EvidenceReference
        ),
    )
    if _encode_m2_record_broker_revision_evidence(decoded) != value:
        raise ValueError("broker revision evidence is not canonical")
    return decoded


_VenueRecoveryItem: _TypeAlias = (
    _venue.RecordTransportOutcome
    | _venue.RecoverClaimedEffect
    | _venue.DiscoverVenueLeg
    | _venue.ObserveVenueStatus
    | _recovery.IngestHumanAttestedFill
    | _recovery.ReleaseVenueLeg
    | _recovery.RecordBrokerFillEvidence
    | _recovery.RecordBrokerRevisionEvidence
)


def _encode_m2_venue_recovery_item(value: object) -> list[object]:
    if type(value) is _venue.RecordTransportOutcome:
        return _encode_m2_record_transport_outcome(value)
    if type(value) is _venue.RecoverClaimedEffect:
        return _encode_m2_recover_claimed_effect(value)
    if type(value) is _venue.DiscoverVenueLeg:
        return _encode_m2_discover_venue_leg(value)
    if type(value) is _venue.ObserveVenueStatus:
        return _encode_m2_observe_venue_status(value)
    if type(value) is _recovery.IngestHumanAttestedFill:
        return _encode_m2_ingest_human_attested_fill(value)
    if type(value) is _recovery.ReleaseVenueLeg:
        return _encode_m2_release_venue_leg(value)
    if type(value) is _recovery.RecordBrokerFillEvidence:
        return _encode_m2_record_broker_fill_evidence(value)
    if type(value) is _recovery.RecordBrokerRevisionEvidence:
        return _encode_m2_record_broker_revision_evidence(value)
    raise TypeError("value is not an admitted venue recovery item")


def _decode_m2_venue_recovery_item(value: object) -> _VenueRecoveryItem:
    if type(value) is not list or not value or type(value[0]) is not str:
        raise ValueError("venue recovery aggregate is malformed")
    tag = value[0]
    if tag == "m1.venue.RecordTransportOutcome/v1":
        return _decode_m2_record_transport_outcome(value)
    if tag == "m1.venue.RecoverClaimedEffect/v1":
        return _decode_m2_recover_claimed_effect(value)
    if tag == "m1.venue.DiscoverVenueLeg/v1":
        return _decode_m2_discover_venue_leg(value)
    if tag == "m1.venue.ObserveVenueStatus/v1":
        return _decode_m2_observe_venue_status(value)
    if tag == "m1.recovery.IngestHumanAttestedFill/v1":
        return _decode_m2_ingest_human_attested_fill(value)
    if tag == "m1.recovery.ReleaseVenueLeg/v1":
        return _decode_m2_release_venue_leg(value)
    if tag == "m1.recovery.RecordBrokerFillEvidence/v1":
        return _decode_m2_record_broker_fill_evidence(value)
    if tag == "m1.recovery.RecordBrokerRevisionEvidence/v1":
        return _decode_m2_record_broker_revision_evidence(value)
    raise ValueError("venue recovery aggregate tag is not admitted")


def _encode_m2_broker_effect_request(value: object) -> list[object]:
    if type(value) is not _authority.BrokerEffectRequest:
        raise TypeError("broker effect request must be exact BrokerEffectRequest")
    return [
        "m1.authority.BrokerEffectRequest/v1",
        _encode_m2_m1_atom(value.effect_id),
        _encode_m2_m1_atom(value.request_occurrence_id),
        _encode_m2_m1_atom(value.mandate_id),
        _encode_m2_enum(value.kind),
        None
        if value.client_order_id is None
        else _encode_m2_m1_atom(value.client_order_id),
        _encode_m2_m1_atom(value.symbol_id),
        _encode_m2_enum(value.side),
        _encode_m2_m1_atom(value.quantity),
        _encode_m2_bytes(value.economic_scope),
        None
        if value.target_leg_key is None
        else _encode_m2_m1_atom(value.target_leg_key),
    ]


def _decode_m2_broker_effect_request(
    value: object,
) -> _authority.BrokerEffectRequest:
    fields = _require_m2_aggregate(value, "m1.authority.BrokerEffectRequest/v1", 10)
    decoded = _authority.BrokerEffectRequest(
        _decode_m2_m1_as("effect request effect", fields[0], _identity.EffectId),
        _decode_m2_m1_as(
            "effect request occurrence", fields[1], _identity.RequestOccurrenceId
        ),
        _decode_m2_m1_as("effect request mandate", fields[2], _identity.MandateId),
        _decode_m2_enum_as("effect request kind", fields[3], _venue.EffectKind),
        _decode_m2_optional_m1_as(
            "effect request client order", fields[4], _identity.ClientOrderId
        ),
        _decode_m2_m1_as("effect request symbol", fields[5], _identity.SymbolId),
        _decode_m2_enum_as("effect request side", fields[6], _fills.ExecutionSide),
        _decode_m2_m1_as("effect request quantity", fields[7], _values.Quantity),
        _decode_m2_bytes("effect request economic scope", fields[8]),
        _decode_m2_optional_m1_as(
            "effect request target leg", fields[9], _identity.VenueLegKey
        ),
    )
    if _encode_m2_broker_effect_request(decoded) != value:
        raise ValueError("broker effect request is not canonical")
    return decoded


def _encode_m2_create_broker_effect(value: object) -> list[object]:
    if type(value) is not _authority.CreateBrokerEffect:
        raise TypeError("authority creation must be exact CreateBrokerEffect")
    return [
        "m1.authority.CreateBrokerEffect/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.session_id),
        _encode_m2_broker_effect_request(value.request),
        None
        if value.manual_flatten_id is None
        else _encode_m2_m1_atom(value.manual_flatten_id),
        None
        if value.emergency_grant_id is None
        else _encode_m2_m1_atom(value.emergency_grant_id),
    ]


def _decode_m2_create_broker_effect(value: object) -> _authority.CreateBrokerEffect:
    fields = _require_m2_aggregate(value, "m1.authority.CreateBrokerEffect/v1", 5)
    decoded = _authority.CreateBrokerEffect(
        _decode_m2_m1_as("create effect input", fields[0], _identity.AuthorityInputId),
        _decode_m2_m1_as("create effect session", fields[1], _identity.SessionId),
        _decode_m2_broker_effect_request(fields[2]),
        _decode_m2_optional_m1_as(
            "create effect manual flatten", fields[3], _identity.ManualFlattenId
        ),
        _decode_m2_optional_m1_as(
            "create effect emergency grant", fields[4], _identity.EmergencyGrantId
        ),
    )
    if _encode_m2_create_broker_effect(decoded) != value:
        raise ValueError("authority creation is not canonical")
    return decoded


def _encode_m2_claim_effect(value: object) -> list[object]:
    if type(value) is not _authority.ClaimEffect:
        raise TypeError("effect claim must be exact ClaimEffect")
    return [
        "m1.authority.ClaimEffect/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.effect_id),
        _encode_m2_m1_atom(value.claim_occurrence_id),
    ]


def _decode_m2_claim_effect(value: object) -> _authority.ClaimEffect:
    fields = _require_m2_aggregate(value, "m1.authority.ClaimEffect/v1", 3)
    decoded = _authority.ClaimEffect(
        _decode_m2_m1_as("claim effect input", fields[0], _identity.AuthorityInputId),
        _decode_m2_m1_as("claim effect id", fields[1], _identity.EffectId),
        _decode_m2_m1_as(
            "claim effect occurrence", fields[2], _identity.ClaimOccurrenceId
        ),
    )
    if _encode_m2_claim_effect(decoded) != value:
        raise ValueError("effect claim is not canonical")
    return decoded


def _encode_m2_claim_broker_query(value: object) -> list[object]:
    if type(value) is not _authority.ClaimBrokerQuery:
        raise TypeError("broker query claim must be exact ClaimBrokerQuery")
    return [
        "m1.authority.ClaimBrokerQuery/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.query_claim_id),
        _encode_m2_m1_atom(value.symbol_id),
        _encode_m2_enum(value.kind),
    ]


def _decode_m2_claim_broker_query(value: object) -> _authority.ClaimBrokerQuery:
    fields = _require_m2_aggregate(value, "m1.authority.ClaimBrokerQuery/v1", 4)
    decoded = _authority.ClaimBrokerQuery(
        _decode_m2_m1_as("broker query input", fields[0], _identity.AuthorityInputId),
        _decode_m2_m1_as("broker query claim", fields[1], _identity.QueryClaimId),
        _decode_m2_m1_as("broker query symbol", fields[2], _identity.SymbolId),
        _decode_m2_enum_as(
            "broker query kind", fields[3], _authority.AuthorityQueryKind
        ),
    )
    if _encode_m2_claim_broker_query(decoded) != value:
        raise ValueError("broker query claim is not canonical")
    return decoded


def _encode_m2_engage_kill(value: object) -> list[object]:
    if type(value) is not _authority.EngageKill:
        raise TypeError("kill command must be exact EngageKill")
    return [
        "m1.authority.EngageKill/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.actor),
        value.reason,
        _encode_m2_m1_atom(value.evidence_reference),
    ]


def _decode_m2_engage_kill(value: object) -> _authority.EngageKill:
    fields = _require_m2_aggregate(value, "m1.authority.EngageKill/v1", 4)
    decoded = _authority.EngageKill(
        _decode_m2_m1_as("kill input", fields[0], _identity.AuthorityInputId),
        _decode_m2_m1_as("kill actor", fields[1], _identity.ActorId),
        _require_exact_text("kill reason", fields[2]),
        _decode_m2_m1_as("kill evidence", fields[3], _identity.EvidenceReference),
    )
    if _encode_m2_engage_kill(decoded) != value:
        raise ValueError("kill command is not canonical")
    return decoded


def _encode_m2_begin_manual_flatten(value: object) -> list[object]:
    if type(value) is not _authority.BeginManualFlatten:
        raise TypeError("manual flatten must be exact BeginManualFlatten")
    return [
        "m1.authority.BeginManualFlatten/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.flatten_id),
        _encode_m2_m1_atom(value.session_id),
        _encode_m2_m1_atom(value.symbol_id),
        _encode_m2_m1_atom(value.actor),
        value.reason,
        _encode_m2_m1_atom(value.evidence_reference),
        None
        if value.emergency_grant_id is None
        else _encode_m2_m1_atom(value.emergency_grant_id),
    ]


def _decode_m2_begin_manual_flatten(
    value: object,
) -> _authority.BeginManualFlatten:
    fields = _require_m2_aggregate(value, "m1.authority.BeginManualFlatten/v1", 8)
    decoded = _authority.BeginManualFlatten(
        _decode_m2_m1_as("flatten input", fields[0], _identity.AuthorityInputId),
        _decode_m2_m1_as("flatten id", fields[1], _identity.ManualFlattenId),
        _decode_m2_m1_as("flatten session", fields[2], _identity.SessionId),
        _decode_m2_m1_as("flatten symbol", fields[3], _identity.SymbolId),
        _decode_m2_m1_as("flatten actor", fields[4], _identity.ActorId),
        _require_exact_text("flatten reason", fields[5]),
        _decode_m2_m1_as("flatten evidence", fields[6], _identity.EvidenceReference),
        _decode_m2_optional_m1_as(
            "flatten emergency grant", fields[7], _identity.EmergencyGrantId
        ),
    )
    if _encode_m2_begin_manual_flatten(decoded) != value:
        raise ValueError("manual flatten is not canonical")
    return decoded


def _encode_m2_advance_manual_flatten(value: object) -> list[object]:
    if type(value) is not _authority.AdvanceManualFlatten:
        raise TypeError("manual flatten advance must be exact AdvanceManualFlatten")
    return [
        "m1.authority.AdvanceManualFlatten/v1",
        _encode_m2_m1_atom(value.input_id),
        _encode_m2_m1_atom(value.flatten_id),
    ]


def _decode_m2_advance_manual_flatten(
    value: object,
) -> _authority.AdvanceManualFlatten:
    fields = _require_m2_aggregate(value, "m1.authority.AdvanceManualFlatten/v1", 2)
    decoded = _authority.AdvanceManualFlatten(
        _decode_m2_m1_as(
            "flatten advance input", fields[0], _identity.AuthorityInputId
        ),
        _decode_m2_m1_as("flatten advance id", fields[1], _identity.ManualFlattenId),
    )
    if _encode_m2_advance_manual_flatten(decoded) != value:
        raise ValueError("manual flatten advance is not canonical")
    return decoded


def _encode_m2_acquisition_effect_terms(value: object) -> list[object]:
    if type(value) is not _authority.AcquisitionEffectTerms:
        raise TypeError("acquisition terms must be exact AcquisitionEffectTerms")
    if not _authority._acquisition_effect_terms_is_authentic(value):
        raise ValueError("acquisition effect terms are not authentic")
    return [
        "m1.authority.AcquisitionEffectTerms/v1",
        _encode_m2_m1_atom(value.quantity),
        _encode_m2_m1_atom(value.limit_price),
        _encode_m2_enum(value.order_type),
        value.evaluation_time,
    ]


def _decode_m2_acquisition_effect_terms(
    value: object,
) -> _authority.AcquisitionEffectTerms:
    fields = _require_m2_aggregate(value, "m1.authority.AcquisitionEffectTerms/v1", 4)
    decoded = _authority.AcquisitionEffectTerms(
        _decode_m2_m1_as("acquisition terms quantity", fields[0], _values.Quantity),
        _decode_m2_m1_as("acquisition terms price", fields[1], _values.ReportedPrice),
        _decode_m2_enum_as(
            "acquisition terms order type", fields[2], _authority.AcquisitionOrderType
        ),
        _require_exact_int("acquisition terms evaluation time", fields[3]),
    )
    if not _authority._acquisition_effect_terms_is_authentic(decoded):
        raise ValueError("decoded acquisition effect terms are not authentic")
    if _encode_m2_acquisition_effect_terms(decoded) != value:
        raise ValueError("acquisition effect terms are not canonical")
    return decoded


_AuthorityOperationCommand: _TypeAlias = (
    _authority.CreateBrokerEffect
    | _authority.ClaimEffect
    | _authority.ClaimBrokerQuery
    | _authority.EngageKill
    | _authority.BeginManualFlatten
    | _authority.AdvanceManualFlatten
)


def _encode_m2_authority_command(value: object) -> list[object]:
    if type(value) is _authority.CreateBrokerEffect:
        return _encode_m2_create_broker_effect(value)
    if type(value) is _authority.ClaimEffect:
        return _encode_m2_claim_effect(value)
    if type(value) is _authority.ClaimBrokerQuery:
        return _encode_m2_claim_broker_query(value)
    if type(value) is _authority.EngageKill:
        return _encode_m2_engage_kill(value)
    if type(value) is _authority.BeginManualFlatten:
        return _encode_m2_begin_manual_flatten(value)
    if type(value) is _authority.AdvanceManualFlatten:
        return _encode_m2_advance_manual_flatten(value)
    raise TypeError("value is not an admitted authority command")


def _decode_m2_authority_command(value: object) -> _AuthorityOperationCommand:
    if type(value) is not list or not value or type(value[0]) is not str:
        raise ValueError("authority aggregate is malformed")
    tag = value[0]
    if tag == "m1.authority.CreateBrokerEffect/v1":
        return _decode_m2_create_broker_effect(value)
    if tag == "m1.authority.ClaimEffect/v1":
        return _decode_m2_claim_effect(value)
    if tag == "m1.authority.ClaimBrokerQuery/v1":
        return _decode_m2_claim_broker_query(value)
    if tag == "m1.authority.EngageKill/v1":
        return _decode_m2_engage_kill(value)
    if tag == "m1.authority.BeginManualFlatten/v1":
        return _decode_m2_begin_manual_flatten(value)
    if tag == "m1.authority.AdvanceManualFlatten/v1":
        return _decode_m2_advance_manual_flatten(value)
    raise ValueError("authority aggregate tag is not admitted")


def _encode_m2_execution_guard(value: object) -> list[object]:
    if type(value) is not _protection.ExecutionGuard:
        raise TypeError("execution guard must be exact ExecutionGuard")
    return [
        "m1.protection.ExecutionGuard/v1",
        value.guard_id,
        _encode_m2_bytes(value.policy_commitment),
    ]


def _decode_m2_execution_guard(value: object) -> _protection.ExecutionGuard:
    fields = _require_m2_aggregate(value, "m1.protection.ExecutionGuard/v1", 2)
    decoded = _protection.ExecutionGuard(
        _require_exact_text("execution guard id", fields[0]),
        _decode_m2_bytes("execution guard policy commitment", fields[1]),
    )
    if _encode_m2_execution_guard(decoded) != value:
        raise ValueError("execution guard is not canonical")
    return decoded


def _encode_m2_evidence_policy(value: object) -> list[object]:
    if type(value) is not _protection.EvidencePolicy:
        raise TypeError("evidence policy must be exact EvidencePolicy")
    return [
        "m1.protection.EvidencePolicy/v1",
        _encode_m2_m1_atom(value.source_id),
        _encode_m2_m1_atom(value.stream_generation),
        _encode_m2_enum(value.sequence_mode),
        value.max_age,
        value.corroboration_window,
        _encode_m2_fraction(value.max_step_fraction),
    ]


def _decode_m2_evidence_policy(value: object) -> _protection.EvidencePolicy:
    fields = _require_m2_aggregate(value, "m1.protection.EvidencePolicy/v1", 6)
    decoded = _protection.EvidencePolicy(
        _decode_m2_m1_as("evidence source", fields[0], _identity.MarketDataSourceId),
        _decode_m2_m1_as(
            "evidence stream", fields[1], _identity.MarketStreamGenerationId
        ),
        _decode_m2_enum_as(
            "evidence sequence mode", fields[2], _protection.MarketSequenceMode
        ),
        _require_exact_int("evidence maximum age", fields[3]),
        _require_exact_int("evidence corroboration window", fields[4]),
        _decode_m2_fraction(fields[5]),
    )
    if _encode_m2_evidence_policy(decoded) != value:
        raise ValueError("evidence policy is not canonical")
    return decoded


def _encode_m2_emergency_recovery_compatibility(value: object) -> list[object]:
    if type(value) is not _protection.EmergencyRecoveryCompatibility:
        raise TypeError(
            "emergency recovery compatibility must be exact "
            "EmergencyRecoveryCompatibility"
        )
    if not _protection._emergency_recovery_compatibility_is_authentic(value):
        raise ValueError("emergency recovery compatibility is not authentic")
    return [
        "m1.protection.EmergencyRecoveryCompatibility/v1",
        _encode_m2_m1_atom(value.compatibility_id),
        _encode_m2_position_scope(value.position_scope),
        _encode_m2_m1_atom(value.session_id),
        value.configuration_version,
        _encode_m2_bytes(value.configuration_commitment),
        _encode_m2_execution_guard(value.emergency_guard),
        value.maximum_goal_rate,
        value.emergency_effect_budget,
        value.deadline,
        _encode_m2_m1_atom(value.aggregate_emergency_quantity),
    ]


def _decode_m2_emergency_recovery_compatibility(
    value: object,
) -> _protection.EmergencyRecoveryCompatibility:
    fields = _require_m2_aggregate(
        value,
        "m1.protection.EmergencyRecoveryCompatibility/v1",
        10,
    )
    decoded = _protection.EmergencyRecoveryCompatibility(
        _decode_m2_m1_as(
            "emergency compatibility id",
            fields[0],
            _identity.EmergencyRecoveryCompatibilityId,
        ),
        _decode_m2_position_scope(fields[1]),
        _decode_m2_m1_as(
            "emergency compatibility session", fields[2], _identity.SessionId
        ),
        _require_exact_text("emergency compatibility configuration", fields[3]),
        _decode_m2_bytes("emergency compatibility configuration commitment", fields[4]),
        _decode_m2_execution_guard(fields[5]),
        _require_exact_int("emergency compatibility maximum rate", fields[6]),
        _require_exact_int("emergency compatibility effect budget", fields[7]),
        _require_exact_int("emergency compatibility deadline", fields[8]),
        _decode_m2_m1_as(
            "emergency compatibility quantity", fields[9], _values.Quantity
        ),
    )
    if not _protection._emergency_recovery_compatibility_is_authentic(decoded):
        raise ValueError("decoded emergency recovery compatibility is not authentic")
    if _encode_m2_emergency_recovery_compatibility(decoded) != value:
        raise ValueError("emergency recovery compatibility is not canonical")
    return decoded


def _encode_m2_protection_mandate(value: object) -> list[object]:
    if type(value) is not _protection.ProtectionMandate:
        raise TypeError("protection mandate must be exact ProtectionMandate")
    if not _protection._protection_mandate_is_authentic(value):
        raise ValueError("protection mandate is not authentic")
    return [
        "m1.protection.ProtectionMandate/v1",
        _encode_m2_m1_atom(value.mandate_id),
        _encode_m2_position_scope(value.position_scope),
        _encode_m2_m1_atom(value.session_id),
        value.configuration_version,
        _encode_m2_fraction(value.loss_fraction),
        _encode_m2_fraction(value.approved_gain),
        _encode_m2_fraction(value.percent_trail_fraction),
        _encode_m2_fraction(value.atr_multiple),
        _encode_m2_m1_atom(value.tick),
        _encode_m2_execution_guard(value.normal_guard),
        _encode_m2_execution_guard(value.emergency_guard),
        _encode_m2_evidence_policy(value.evidence_policy),
        _encode_m2_m1_atom(value.maximum_quantity),
        value.maximum_goal_rate,
        value.deadline,
        _encode_m2_emergency_recovery_compatibility(
            value.emergency_recovery_compatibility
        ),
    ]


def _decode_m2_protection_mandate(value: object) -> _protection.ProtectionMandate:
    fields = _require_m2_aggregate(value, "m1.protection.ProtectionMandate/v1", 16)
    decoded = _protection.ProtectionMandate(
        _decode_m2_m1_as("protection mandate id", fields[0], _identity.MandateId),
        _decode_m2_position_scope(fields[1]),
        _decode_m2_m1_as("protection mandate session", fields[2], _identity.SessionId),
        _require_exact_text("protection mandate configuration", fields[3]),
        _decode_m2_fraction(fields[4]),
        _decode_m2_fraction(fields[5]),
        _decode_m2_fraction(fields[6]),
        _decode_m2_fraction(fields[7]),
        _decode_m2_m1_as("protection mandate tick", fields[8], _values.TickMetadata),
        _decode_m2_execution_guard(fields[9]),
        _decode_m2_execution_guard(fields[10]),
        _decode_m2_evidence_policy(fields[11]),
        _decode_m2_m1_as("protection mandate quantity", fields[12], _values.Quantity),
        _require_exact_int("protection mandate maximum rate", fields[13]),
        _require_exact_int("protection mandate deadline", fields[14]),
        _decode_m2_emergency_recovery_compatibility(fields[15]),
    )
    if not _protection._protection_mandate_is_authentic(decoded):
        raise ValueError("decoded protection mandate is not authentic")
    if _encode_m2_protection_mandate(decoded) != value:
        raise ValueError("protection mandate is not canonical")
    return decoded


def _encode_m2_market_occurrence(value: object) -> list[object]:
    if type(value) is not _protection.MarketOccurrence:
        raise TypeError("market occurrence must be exact MarketOccurrence")
    if not _protection._market_occurrence_is_authentic(value):
        raise ValueError("market occurrence is not authentic")
    return [
        "m1.protection.MarketOccurrence/v1",
        _encode_m2_m1_atom(value.source_id),
        _encode_m2_m1_atom(value.stream_generation),
        _encode_m2_position_scope(value.position_scope),
        _encode_m2_m1_atom(value.session_id),
        value.market_epoch,
        value.source_sequence,
        value.source_time,
        value.evaluation_time,
        _encode_m2_enum(value.kind),
        None if value.best_bid is None else _encode_m2_m1_atom(value.best_bid),
        None if value.best_ask is None else _encode_m2_m1_atom(value.best_ask),
        None if value.trade_price is None else _encode_m2_m1_atom(value.trade_price),
        None if value.atr_distance is None else _encode_m2_m1_atom(value.atr_distance),
        None
        if value.structure_trail is None
        else _encode_m2_m1_atom(value.structure_trail),
        value.halted,
    ]


def _decode_m2_optional_exact_int(name: str, value: object) -> int | None:
    if value is None:
        return None
    return _require_exact_int(name, value)


def _decode_m2_market_occurrence(value: object) -> _protection.MarketOccurrence:
    fields = _require_m2_aggregate(value, "m1.protection.MarketOccurrence/v1", 15)
    halted = fields[14]
    if type(halted) is not bool:
        raise TypeError("market occurrence halted must be exact bool")
    decoded = _protection.MarketOccurrence(
        _decode_m2_m1_as(
            "market occurrence source", fields[0], _identity.MarketDataSourceId
        ),
        _decode_m2_m1_as(
            "market occurrence stream", fields[1], _identity.MarketStreamGenerationId
        ),
        _decode_m2_position_scope(fields[2]),
        _decode_m2_m1_as("market occurrence session", fields[3], _identity.SessionId),
        _require_exact_int("market occurrence epoch", fields[4]),
        _decode_m2_optional_exact_int("market occurrence source sequence", fields[5]),
        _require_exact_int("market occurrence source time", fields[6]),
        _require_exact_int("market occurrence evaluation time", fields[7]),
        _decode_m2_enum_as("market occurrence kind", fields[8], _protection.MarketKind),
        _decode_m2_optional_m1_as(
            "market occurrence bid", fields[9], _values.ReportedPrice
        ),
        _decode_m2_optional_m1_as(
            "market occurrence ask", fields[10], _values.ReportedPrice
        ),
        _decode_m2_optional_m1_as(
            "market occurrence trade", fields[11], _values.ReportedPrice
        ),
        _decode_m2_optional_m1_as(
            "market occurrence ATR", fields[12], _values.ReportedPrice
        ),
        _decode_m2_optional_m1_as(
            "market occurrence structure trail", fields[13], _values.ReportedPrice
        ),
        halted,
    )
    if not _protection._market_occurrence_is_authentic(decoded):
        raise ValueError("decoded market occurrence is not authentic")
    if _encode_m2_market_occurrence(decoded) != value:
        raise ValueError("market occurrence is not canonical")
    return decoded


def _encode_m2_acquisition_order_types(value: object) -> list[object]:
    if type(value) is not tuple or len(value) != 1:
        raise ValueError("acquisition order types must be the exact one-member tuple")
    order_type = value[0]
    if type(order_type) is not _authority.AcquisitionOrderType:
        raise TypeError("acquisition order type must be AcquisitionOrderType")
    if order_type is not _authority.AcquisitionOrderType.LIMIT:
        raise ValueError("only LIMIT acquisition order type is admitted")
    return [
        "m2.acquisition.AcquisitionOrderTypes/v1",
        _encode_m2_enum(order_type),
    ]


def _decode_m2_acquisition_order_types(
    value: object,
) -> tuple[_authority.AcquisitionOrderType, ...]:
    fields = _require_m2_aggregate(
        value,
        "m2.acquisition.AcquisitionOrderTypes/v1",
        1,
    )
    order_type = _decode_m2_enum_as(
        "acquisition order type",
        fields[0],
        _authority.AcquisitionOrderType,
    )
    if order_type is not _authority.AcquisitionOrderType.LIMIT:
        raise ValueError("only LIMIT acquisition order type is admitted")
    decoded = (order_type,)
    if _encode_m2_acquisition_order_types(decoded) != value:
        raise ValueError("acquisition order type collection is not canonical")
    return decoded


def _encode_m2_acquisition_mandate(value: object) -> list[object]:
    if type(value) is not _acquisition.AcquisitionMandate:
        raise TypeError("acquisition mandate must be exact AcquisitionMandate")
    if not _acquisition._acquisition_mandate_is_authentic(value):
        raise ValueError("acquisition mandate is not authentic")
    return [
        "m1.acquisition.AcquisitionMandate/v1",
        _encode_m2_m1_atom(value.acquisition_mandate_id),
        _encode_m2_position_scope(value.position_scope),
        _encode_m2_m1_atom(value.session_id),
        value.configuration_version,
        _encode_m2_m1_atom(value.maximum_quantity),
        _encode_m2_fraction(value.maximum_notional),
        _encode_m2_m1_atom(value.maximum_entry_price),
        _encode_m2_acquisition_order_types(value.allowed_order_types),
        value.expiry,
        value.deadline,
        _encode_m2_m1_atom(value.fixed_child_cap),
        None
        if value.certified_participation_cap is None
        else _encode_m2_fraction(value.certified_participation_cap),
        value.cancel_reprice_budget,
        _encode_m2_protection_mandate(value.protection_mandate),
    ]


def _decode_m2_optional_fraction(value: object) -> _Fraction | None:
    if value is None:
        return None
    return _decode_m2_fraction(value)


def _decode_m2_acquisition_mandate(value: object) -> _acquisition.AcquisitionMandate:
    fields = _require_m2_aggregate(value, "m1.acquisition.AcquisitionMandate/v1", 14)
    decoded = _acquisition._m2_hydrate_acquisition_mandate(
        acquisition_mandate_id=_decode_m2_m1_as(
            "acquisition mandate id", fields[0], _identity.AcquisitionMandateId
        ),
        position_scope=_decode_m2_position_scope(fields[1]),
        session_id=_decode_m2_m1_as(
            "acquisition mandate session", fields[2], _identity.SessionId
        ),
        configuration_version=_require_exact_text(
            "acquisition mandate configuration", fields[3]
        ),
        maximum_quantity=_decode_m2_m1_as(
            "acquisition mandate maximum quantity", fields[4], _values.Quantity
        ),
        maximum_notional=_decode_m2_fraction(fields[5]),
        maximum_entry_price=_decode_m2_m1_as(
            "acquisition mandate maximum price", fields[6], _values.ReportedPrice
        ),
        allowed_order_types=_decode_m2_acquisition_order_types(fields[7]),
        expiry=_require_exact_int("acquisition mandate expiry", fields[8]),
        deadline=_require_exact_int("acquisition mandate deadline", fields[9]),
        fixed_child_cap=_decode_m2_m1_as(
            "acquisition mandate child cap", fields[10], _values.Quantity
        ),
        certified_participation_cap=_decode_m2_optional_fraction(fields[11]),
        cancel_reprice_budget=_require_exact_int(
            "acquisition mandate cancel/reprice budget", fields[12]
        ),
        protection_mandate=_decode_m2_protection_mandate(fields[13]),
    )
    if not _acquisition._acquisition_mandate_is_authentic(decoded):
        raise ValueError("decoded acquisition mandate is not authentic")
    if _encode_m2_acquisition_mandate(decoded) != value:
        raise ValueError("acquisition mandate is not canonical")
    return decoded


def encode_m2_operation(operation: M2Operation) -> bytes:
    """Encode one exact admitted M2 operation into immutable canonical bytes."""

    if type(operation) is BrokerExecutionOperation:
        broker_operation = BrokerExecutionOperation(
            operation.coordinates, operation.fact
        )
        domain = OperationDomain.BROKER_EXECUTION
        coordinates = _encode_m2_coordinates(broker_operation.coordinates)
        payload = _encode_m2_broker_execution_fact(broker_operation.fact)
    elif type(operation) is VenueRecoveryOperation:
        venue_operation = VenueRecoveryOperation(operation.coordinates, operation.item)
        domain = OperationDomain.VENUE_RECOVERY
        coordinates = _encode_m2_coordinates(venue_operation.coordinates)
        payload = _encode_m2_venue_recovery_item(venue_operation.item)
    elif type(operation) is AuthorityOperation:
        authority_operation = AuthorityOperation(
            operation.coordinates, operation.command
        )
        domain = OperationDomain.AUTHORITY
        coordinates = _encode_m2_coordinates(authority_operation.coordinates)
        payload = _encode_m2_authority_command(authority_operation.command)
    elif type(operation) is BeginAcquisitionGenerationOperation:
        acquisition_generation_operation = BeginAcquisitionGenerationOperation(
            operation.coordinates,
            operation.input_id,
            operation.successor_mandate,
        )
        domain = OperationDomain.BEGIN_ACQUISITION_GENERATION
        coordinates = _encode_m2_coordinates(
            acquisition_generation_operation.coordinates
        )
        payload = [
            "m2.acquisition.BeginAcquisitionGeneration/v1",
            _encode_m2_m1_atom(acquisition_generation_operation.input_id),
            _encode_m2_acquisition_mandate(
                acquisition_generation_operation.successor_mandate
            ),
        ]
    elif type(operation) is CreateAcquisitionEffectOperation:
        acquisition_effect_operation = CreateAcquisitionEffectOperation(
            operation.coordinates,
            operation.input_id,
            operation.terms,
        )
        domain = OperationDomain.CREATE_ACQUISITION_EFFECT
        coordinates = _encode_m2_coordinates(acquisition_effect_operation.coordinates)
        payload = [
            "m2.acquisition.CreateAcquisitionEffect/v1",
            _encode_m2_m1_atom(acquisition_effect_operation.input_id),
            _encode_m2_acquisition_effect_terms(acquisition_effect_operation.terms),
        ]
    elif type(operation) is ClaimAcquisitionEffectOperation:
        acquisition_claim_operation = ClaimAcquisitionEffectOperation(
            operation.coordinates,
            operation.input_id,
            operation.effect_id,
            operation.claim_occurrence_id,
        )
        domain = OperationDomain.CLAIM_ACQUISITION_EFFECT
        coordinates = _encode_m2_coordinates(acquisition_claim_operation.coordinates)
        payload = [
            "m2.acquisition.ClaimAcquisitionEffect/v1",
            _encode_m2_m1_atom(acquisition_claim_operation.input_id),
            _encode_m2_m1_atom(acquisition_claim_operation.effect_id),
            _encode_m2_m1_atom(acquisition_claim_operation.claim_occurrence_id),
        ]
    elif type(operation) is BeginAcquisitionPreemptionOperation:
        acquisition_preemption_operation = BeginAcquisitionPreemptionOperation(
            operation.coordinates,
            operation.input_id,
        )
        domain = OperationDomain.BEGIN_ACQUISITION_PREEMPTION
        coordinates = _encode_m2_coordinates(
            acquisition_preemption_operation.coordinates
        )
        payload = [
            "m2.acquisition.BeginAcquisitionPreemption/v1",
            _encode_m2_m1_atom(acquisition_preemption_operation.input_id),
        ]
    elif type(operation) is MarketOccurrenceOperation:
        market_operation = MarketOccurrenceOperation(
            operation.coordinates, operation.occurrence
        )
        domain = OperationDomain.MARKET_OCCURRENCE
        coordinates = _encode_m2_coordinates(market_operation.coordinates)
        payload = [
            "m2.protection.MarketOccurrenceOperation/v1",
            _encode_m2_market_occurrence(market_operation.occurrence),
        ]
    else:
        raise TypeError("operation is not an exact admitted M2 operation")
    return _encode_m2_document(
        [
            1,
            "m2.operation/v1",
            _encode_m2_enum(domain),
            coordinates,
            payload,
        ]
    )


def decode_m2_operation(value: object) -> M2Operation:
    """Decode only a byte-identical canonical M2 operation document."""

    document = _decode_m2_document(value)
    if len(document) != 5:
        raise ValueError("operation document must have exactly five members")
    if _require_exact_int("operation document version", document[0]) != 1:
        raise ValueError("operation document version is not admitted")
    if document[1] != "m2.operation/v1":
        raise ValueError("operation document type tag is not admitted")
    domain = _decode_m2_enum_as(
        "operation domain",
        document[2],
        OperationDomain,
    )
    coordinates = _decode_m2_coordinates(document[3])
    payload = document[4]
    if domain is OperationDomain.BROKER_EXECUTION:
        if type(coordinates) is not ExecutionOperationCoordinates:
            raise ValueError("broker execution requires execution coordinates")
        decoded: M2Operation = BrokerExecutionOperation(
            coordinates,
            _decode_m2_broker_execution_fact(payload),
        )
    elif domain is OperationDomain.VENUE_RECOVERY:
        if type(coordinates) is not VenueOperationCoordinates:
            raise ValueError("venue recovery requires venue coordinates")
        decoded = VenueRecoveryOperation(
            coordinates,
            _decode_m2_venue_recovery_item(payload),
        )
    elif domain is OperationDomain.AUTHORITY:
        if type(coordinates) is not ExecutionOperationCoordinates:
            raise ValueError("authority requires execution coordinates")
        decoded = AuthorityOperation(
            coordinates,
            _decode_m2_authority_command(payload),
        )
    elif domain is OperationDomain.BEGIN_ACQUISITION_GENERATION:
        if type(coordinates) is not AcquisitionOperationCoordinates:
            raise ValueError("acquisition generation requires acquisition coordinates")
        fields = _require_m2_aggregate(
            payload,
            "m2.acquisition.BeginAcquisitionGeneration/v1",
            2,
        )
        decoded = BeginAcquisitionGenerationOperation(
            coordinates,
            _decode_m2_m1_as(
                "acquisition generation input", fields[0], _identity.AuthorityInputId
            ),
            _decode_m2_acquisition_mandate(fields[1]),
        )
    elif domain is OperationDomain.CREATE_ACQUISITION_EFFECT:
        if type(coordinates) is not AcquisitionOperationCoordinates:
            raise ValueError("acquisition effect requires acquisition coordinates")
        fields = _require_m2_aggregate(
            payload,
            "m2.acquisition.CreateAcquisitionEffect/v1",
            2,
        )
        decoded = CreateAcquisitionEffectOperation(
            coordinates,
            _decode_m2_m1_as(
                "acquisition effect input", fields[0], _identity.AuthorityInputId
            ),
            _decode_m2_acquisition_effect_terms(fields[1]),
        )
    elif domain is OperationDomain.CLAIM_ACQUISITION_EFFECT:
        if type(coordinates) is not AcquisitionOperationCoordinates:
            raise ValueError("acquisition claim requires acquisition coordinates")
        fields = _require_m2_aggregate(
            payload,
            "m2.acquisition.ClaimAcquisitionEffect/v1",
            3,
        )
        decoded = ClaimAcquisitionEffectOperation(
            coordinates,
            _decode_m2_m1_as(
                "acquisition claim input", fields[0], _identity.AuthorityInputId
            ),
            _decode_m2_m1_as("acquisition claim effect", fields[1], _identity.EffectId),
            _decode_m2_m1_as(
                "acquisition claim occurrence", fields[2], _identity.ClaimOccurrenceId
            ),
        )
    elif domain is OperationDomain.BEGIN_ACQUISITION_PREEMPTION:
        if type(coordinates) is not AcquisitionOperationCoordinates:
            raise ValueError("acquisition preemption requires acquisition coordinates")
        fields = _require_m2_aggregate(
            payload,
            "m2.acquisition.BeginAcquisitionPreemption/v1",
            1,
        )
        decoded = BeginAcquisitionPreemptionOperation(
            coordinates,
            _decode_m2_m1_as(
                "acquisition preemption input", fields[0], _identity.AuthorityInputId
            ),
        )
    elif domain is OperationDomain.MARKET_OCCURRENCE:
        if type(coordinates) is not MarketOperationCoordinates:
            raise ValueError("market occurrence requires market coordinates")
        fields = _require_m2_aggregate(
            payload,
            "m2.protection.MarketOccurrenceOperation/v1",
            1,
        )
        decoded = MarketOccurrenceOperation(
            coordinates,
            _decode_m2_market_occurrence(fields[0]),
        )
    else:
        raise ValueError("operation domain is not admitted")
    if encode_m2_operation(decoded) != value:
        raise ValueError("operation document is not canonical")
    return decoded


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
        _validate_input_semantic_key(self)

    def __init_subclass__(cls, **kwargs: object) -> None:
        del cls, kwargs
        raise TypeError("InputSemanticKey cannot be subclassed")


def _validate_input_semantic_key(value: object) -> InputSemanticKey:
    """Authenticate every retained key, including objects forged after init."""

    if type(value) is not InputSemanticKey:
        raise TypeError("semantic match must be an exact InputSemanticKey")
    try:
        kind = value.kind
        canonical_key_bytes = value.canonical_key_bytes
        key_sha256 = value.key_sha256
        retained_input_domain = value.retained_input_domain
        retained_input_identity_sha256 = value.retained_input_identity_sha256
    except AttributeError as exc:
        raise TypeError("semantic match is missing a required field") from exc
    if type(kind) is not InputSemanticKeyKind:
        raise TypeError("semantic match kind must be InputSemanticKeyKind")
    if type(canonical_key_bytes) is not bytes:
        raise TypeError("semantic match canonical_key_bytes must be exact bytes")
    decoded_kind, _, _ = decode_m2_semantic_key(canonical_key_bytes)
    if decoded_kind is not kind:
        raise ValueError("semantic match kind does not match canonical key bytes")
    canonical_digest = _require_sha256("semantic match key_sha256", key_sha256)
    if _hashlib.sha256(canonical_key_bytes).hexdigest() != canonical_digest:
        raise ValueError("semantic match digest does not match canonical key bytes")
    _require_exact_text("semantic match retained_input_domain", retained_input_domain)
    _require_sha256(
        "semantic match retained_input_identity_sha256",
        retained_input_identity_sha256,
    )
    return value


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
            authenticated_match = _validate_input_semantic_key(match)
            if authenticated_match.canonical_key_bytes in key_bytes:
                raise ValueError("semantic_matches must not duplicate a canonical key")
            key_bytes.append(authenticated_match.canonical_key_bytes)

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
        if (
            self.coordinates.session_id is None
            and type(self.item) is not _venue.ObserveVenueStatus
        ):
            raise ValueError("missing session is permitted only for ObserveVenueStatus")

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
        if self.successor_mandate.session_id != self.coordinates.session_id:
            raise ValueError(
                "successor_mandate session must match acquisition coordinates"
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
        if not _protection._market_occurrence_is_authentic(self.occurrence):
            raise ValueError("occurrence must be an authentic market occurrence")
        if self.occurrence.session_id != self.coordinates.session_id:
            raise ValueError("occurrence session must match market coordinates")
        if self.occurrence.stream_generation != self.coordinates.stream_generation_id:
            raise ValueError("occurrence stream must match market coordinates")

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
