"""Immutable schema-neutral v1 durable atoms for exact M1 values.

Every owning M1 value class, concrete identity class, and public composite
identity key has one versioned canonical atom shape. Encoding reads only
public constructor values; private seals and caches are never persisted and
are re-derived by the owning constructors on decode. The codec is pure: no
I/O, clock, randomness, side effects, reducer routes, or dependencies beyond
the deterministic standard library.

Canonical rules (v1, contract version ``"1"``):

- Integer fields are base-10 ASCII text with an optional leading ``-`` only
  where the owning value permits negatives; ``+``, leading zeros, negative
  zero, and non-ASCII digits are refused.
- ``Decimal`` persists its exact ``(sign, digits, exponent)`` tuple;
  ``Fraction`` persists its reduced numerator and positive denominator —
  unreduced or noncanonical-zero ratios are refused, never silently
  normalized. Float conversion never occurs.
- Composite atoms hold exact ordered typed child atoms. Unknown versions or
  tags and missing, extra, reordered, duplicate, malformed, wrong-type,
  non-NFC, blank, or control-bearing fields are refused without repair.

The public surface is exactly ``DurableAtom``, ``encode_m1_value``, and
``decode_m1_value``; every other name in this module is implementation-
private.
"""

from __future__ import annotations as _annotations

import unicodedata as _unicodedata
from dataclasses import dataclass as _dataclass
from decimal import Decimal as _Decimal
from fractions import Fraction as _Fraction
from typing import Any as _Any
from typing import Callable as _Callable
from typing import TypeVar as _TypeVar

from . import identity as _identity
from . import values as _values


_CONTRACT_VERSION = "1"

_DIGIT_CHARACTERS = "0123456789"

_IDENTITY_CLASSES: tuple[tuple[str, type], ...] = (
    ("broker_id", _identity.BrokerId),
    ("environment_id", _identity.EnvironmentId),
    ("account_id", _identity.AccountId),
    ("symbol_id", _identity.SymbolId),
    ("order_id", _identity.OrderId),
    ("root_fill_id", _identity.RootFillId),
    ("source_event_id", _identity.SourceEventId),
    ("application_generation_id", _identity.ApplicationGenerationId),
    ("effect_id", _identity.EffectId),
    ("request_occurrence_id", _identity.RequestOccurrenceId),
    ("client_order_id", _identity.ClientOrderId),
    ("claim_occurrence_id", _identity.ClaimOccurrenceId),
    ("closure_id", _identity.ClosureId),
    ("venue_input_id", _identity.VenueInputId),
    ("venue_observation_id", _identity.VenueObservationId),
    ("actor_id", _identity.ActorId),
    ("evidence_reference", _identity.EvidenceReference),
    ("mandate_id", _identity.MandateId),
    ("acquisition_mandate_id", _identity.AcquisitionMandateId),
    (
        "emergency_recovery_compatibility_id",
        _identity.EmergencyRecoveryCompatibilityId,
    ),
    ("market_data_source_id", _identity.MarketDataSourceId),
    ("market_occurrence_id", _identity.MarketOccurrenceId),
    ("market_stream_generation_id", _identity.MarketStreamGenerationId),
    ("acquisition_generation_id", _identity.AcquisitionGenerationId),
    ("authority_input_id", _identity.AuthorityInputId),
    ("query_claim_id", _identity.QueryClaimId),
    ("session_id", _identity.SessionId),
    ("emergency_grant_id", _identity.EmergencyGrantId),
    ("manual_flatten_id", _identity.ManualFlattenId),
)

_IDENTITY_CLASS_BY_TYPE: dict[type, str] = {
    identity_class: tag for tag, identity_class in _IDENTITY_CLASSES
}

_OwningValue = (
    _values.Quantity
    | _values.PriceUnits
    | _values.PriceScale
    | _values.TickMetadata
    | _values.ReportedPrice
    | _values.ExactBasis
    | _identity.BrokerId
    | _identity.EnvironmentId
    | _identity.AccountId
    | _identity.SymbolId
    | _identity.OrderId
    | _identity.RootFillId
    | _identity.SourceEventId
    | _identity.ApplicationGenerationId
    | _identity.EffectId
    | _identity.RequestOccurrenceId
    | _identity.ClientOrderId
    | _identity.ClaimOccurrenceId
    | _identity.ClosureId
    | _identity.VenueInputId
    | _identity.VenueObservationId
    | _identity.ActorId
    | _identity.EvidenceReference
    | _identity.MandateId
    | _identity.AcquisitionMandateId
    | _identity.EmergencyRecoveryCompatibilityId
    | _identity.MarketDataSourceId
    | _identity.MarketOccurrenceId
    | _identity.MarketStreamGenerationId
    | _identity.AcquisitionGenerationId
    | _identity.AuthorityInputId
    | _identity.QueryClaimId
    | _identity.SessionId
    | _identity.EmergencyGrantId
    | _identity.ManualFlattenId
    | _identity.ExecutionFactKey
    | _identity.RootFillKey
    | _identity.VenueLegKey
)

_FIELD_SPECS: dict[str, tuple[tuple[str, str], ...]] = {
    "quantity": (("text", "nonneg"),),
    "price_units": (("text", "signed"),),
    "_decimal": (
        ("text", "dec_sign"),
        ("text", "dec_digits"),
        ("text", "dec_exponent"),
    ),
    "_fraction": (("text", "frac_num"), ("text", "frac_den")),
    "price_scale": (("atom", "_decimal"),),
    "tick_metadata": (("atom", "price_units"), ("atom", "price_scale")),
    "reported_price": (
        ("atom", "price_units"),
        ("atom", "price_scale"),
        ("atom", "tick_metadata"),
    ),
    "exact_basis": (("atom", "_fraction"),),
    "execution_fact_key": (
        ("atom", "broker_id"),
        ("atom", "environment_id"),
        ("atom", "account_id"),
        ("atom", "source_event_id"),
    ),
    "root_fill_key": (
        ("atom", "broker_id"),
        ("atom", "environment_id"),
        ("atom", "account_id"),
        ("atom", "root_fill_id"),
    ),
    "venue_leg_key": (
        ("atom", "broker_id"),
        ("atom", "environment_id"),
        ("atom", "account_id"),
        ("atom", "order_id"),
    ),
}
for _identity_tag, _identity_class in _IDENTITY_CLASSES:
    _FIELD_SPECS[_identity_tag] = (("text", "identity"),)

__all__ = ("DurableAtom", "decode_m1_value", "encode_m1_value")


@_dataclass(frozen=True, slots=True)
class DurableAtom:
    """One immutable versioned durable atom with ordered typed fields."""

    contract_version: str
    type_tag: str
    fields: tuple["DurableAtom | str", ...]

    def __post_init__(self) -> None:
        _validate_atom(self)


def _is_canonical_int_text(value: str, *, allow_negative: bool) -> bool:
    if not value:
        return False
    negative = value.startswith("-")
    if negative:
        if not allow_negative:
            return False
        value = value[1:]
        if value == "0":
            return False
    if not value.isascii():
        return False
    for character in value:
        if character not in _DIGIT_CHARACTERS:
            return False
    return len(value) == 1 or value[0] != "0"


def _is_canonical_identity_text(value: str) -> bool:
    if not value.strip():
        return False
    for character in value:
        code_point = ord(character)
        if code_point < 0x20 or code_point == 0x7F:
            return False
    return _unicodedata.normalize("NFC", value) == value


def _is_reduced_ratio(numerator: int, denominator: int) -> bool:
    left = abs(numerator)
    right = denominator
    while right:
        left, right = right, left % right
    return left == 1


def _validate_leaf_text(kind: str, value: str) -> None:
    if kind == "nonneg":
        canonical = _is_canonical_int_text(value, allow_negative=False)
        if not canonical:
            raise ValueError("non-canonical non-negative integer text")
    elif kind == "signed":
        canonical = _is_canonical_int_text(value, allow_negative=True)
        if not canonical:
            raise ValueError("non-canonical signed integer text")
    elif kind == "dec_sign":
        if value not in ("0", "1"):
            raise ValueError("non-canonical decimal sign")
    elif kind == "dec_digits":
        if not _is_canonical_int_text(value, allow_negative=False):
            raise ValueError("non-canonical decimal digits")
    elif kind == "dec_exponent":
        if not _is_canonical_int_text(value, allow_negative=True):
            raise ValueError("non-canonical decimal exponent")
    elif kind == "frac_num":
        if not _is_canonical_int_text(value, allow_negative=True):
            raise ValueError("non-canonical fraction numerator")
    elif kind == "frac_den":
        positive = _is_canonical_int_text(value, allow_negative=False) and value != "0"
        if not positive:
            raise ValueError("fraction denominator must be a positive integer")
    else:
        if not _is_canonical_identity_text(value):
            raise ValueError(
                "identity text must be nonblank NFC text without control characters"
            )


def _validate_atom(atom: DurableAtom) -> None:
    if type(atom.contract_version) is not str:
        raise TypeError("contract version must be text")
    if atom.contract_version != _CONTRACT_VERSION:
        raise ValueError("unknown durable contract version")
    if type(atom.type_tag) is not str:
        raise TypeError("type tag must be text")
    specification = _FIELD_SPECS.get(atom.type_tag)
    if specification is None:
        raise ValueError("unknown durable type tag")
    if type(atom.fields) is not tuple:
        raise TypeError("fields must be a tuple")
    if len(atom.fields) != len(specification):
        raise ValueError("durable atom field count does not match its contract")
    for field, (container, detail) in zip(atom.fields, specification, strict=True):
        if container == "text":
            if type(field) is not str:
                raise TypeError("durable atom leaf field must be text")
            _validate_leaf_text(detail, field)
        else:
            if type(field) is not DurableAtom:
                raise TypeError("durable atom composite field must be an atom")
            if field.type_tag != detail:
                raise ValueError("child atom tag does not match its ordered position")
            _validate_atom(field)
    if atom.type_tag == "_fraction":
        numerator = int(_leaf_text(atom, 0))
        denominator = int(_leaf_text(atom, 1))
        if not _is_reduced_ratio(numerator, denominator):
            raise ValueError(
                "fraction components must be reduced to relatively prime "
                "numerator and positive denominator"
            )


def _leaf_text(atom: DurableAtom, index: int) -> str:
    field = atom.fields[index]
    if type(field) is not str:
        raise TypeError("durable atom leaf field is not text")
    return field


def _child_atom(atom: DurableAtom, index: int) -> DurableAtom:
    field = atom.fields[index]
    if type(field) is not DurableAtom:
        raise TypeError("durable atom composite field is not an atom")
    return field


def _encode_integer_atom(type_tag: str, value: int) -> DurableAtom:
    return DurableAtom(_CONTRACT_VERSION, type_tag, (str(value),))


def _encode_decimal_leaf(value: _Decimal) -> DurableAtom:
    sign, digits, exponent = value.as_tuple()
    digit_text = "".join(str(digit) for digit in digits)
    return DurableAtom(
        _CONTRACT_VERSION,
        "_decimal",
        (str(sign), digit_text, str(exponent)),
    )


def _encode_fraction_leaf(value: _Fraction) -> DurableAtom:
    numerator, denominator = value.as_integer_ratio()
    return DurableAtom(
        _CONTRACT_VERSION, "_fraction", (str(numerator), str(denominator))
    )


def _encode_quantity(value: _values.Quantity) -> DurableAtom:
    return _encode_integer_atom("quantity", value.value)


def _encode_price_units(value: _values.PriceUnits) -> DurableAtom:
    return _encode_integer_atom("price_units", value.value)


def _encode_price_scale(value: _values.PriceScale) -> DurableAtom:
    return DurableAtom(
        _CONTRACT_VERSION, "price_scale", (_encode_decimal_leaf(value.value),)
    )


def _encode_tick_metadata(value: _values.TickMetadata) -> DurableAtom:
    return DurableAtom(
        _CONTRACT_VERSION,
        "tick_metadata",
        (
            _encode_price_units(value.tick_units),
            _encode_price_scale(value.scale),
        ),
    )


def _encode_reported_price(value: _values.ReportedPrice) -> DurableAtom:
    return DurableAtom(
        _CONTRACT_VERSION,
        "reported_price",
        (
            _encode_price_units(value.units),
            _encode_price_scale(value.scale),
            _encode_tick_metadata(value.tick),
        ),
    )


def _encode_exact_basis(value: _values.ExactBasis) -> DurableAtom:
    return DurableAtom(
        _CONTRACT_VERSION,
        "exact_basis",
        (_encode_fraction_leaf(value.value),),
    )


def _encode_identity(value: _Any) -> DurableAtom:
    type_tag = _IDENTITY_CLASS_BY_TYPE.get(type(value))
    if type_tag is None:
        raise TypeError("value is not an M1 identity")
    text = value.value
    if type(text) is not str:
        raise TypeError("identity value must be text")
    return DurableAtom(_CONTRACT_VERSION, type_tag, (text,))


def _encode_execution_fact_key(value: _identity.ExecutionFactKey) -> DurableAtom:
    return DurableAtom(
        _CONTRACT_VERSION,
        "execution_fact_key",
        (
            _encode_identity(value.broker),
            _encode_identity(value.environment),
            _encode_identity(value.account),
            _encode_identity(value.source_event_id),
        ),
    )


def _encode_root_fill_key(value: _identity.RootFillKey) -> DurableAtom:
    return DurableAtom(
        _CONTRACT_VERSION,
        "root_fill_key",
        (
            _encode_identity(value.broker),
            _encode_identity(value.environment),
            _encode_identity(value.account),
            _encode_identity(value.root_fill_id),
        ),
    )


def _encode_venue_leg_key(value: _identity.VenueLegKey) -> DurableAtom:
    return DurableAtom(
        _CONTRACT_VERSION,
        "venue_leg_key",
        (
            _encode_identity(value.broker),
            _encode_identity(value.environment),
            _encode_identity(value.account),
            _encode_identity(value.order_id),
        ),
    )


_ENCODER_BY_TYPE: dict[type, _Callable[[_Any], DurableAtom]] = {
    _values.Quantity: _encode_quantity,
    _values.PriceUnits: _encode_price_units,
    _values.PriceScale: _encode_price_scale,
    _values.TickMetadata: _encode_tick_metadata,
    _values.ReportedPrice: _encode_reported_price,
    _values.ExactBasis: _encode_exact_basis,
    _identity.ExecutionFactKey: _encode_execution_fact_key,
    _identity.RootFillKey: _encode_root_fill_key,
    _identity.VenueLegKey: _encode_venue_leg_key,
}
for _identity_class in _IDENTITY_CLASS_BY_TYPE:
    _ENCODER_BY_TYPE[_identity_class] = _encode_identity


_IDENTITY_CONSTRUCTOR_BY_TAG: dict[str, _Callable[[str], _Any]] = {
    tag: identity_class for tag, identity_class in _IDENTITY_CLASSES
}


def encode_m1_value(value: _OwningValue) -> DurableAtom:
    """Encode one exact M1 value, identity, or composite key."""

    handler = _ENCODER_BY_TYPE.get(type(value))
    if handler is None:
        raise TypeError(
            "value type is outside the M1 durable codec contract: "
            + type(value).__name__
        )
    return handler(value)


def _decode_decimal_leaf(decimal_atom: DurableAtom) -> _Decimal:
    sign = int(_leaf_text(decimal_atom, 0))
    digit_text = _leaf_text(decimal_atom, 1)
    digits = tuple(int(character) for character in digit_text)
    exponent = int(_leaf_text(decimal_atom, 2))
    return _Decimal((sign, digits, exponent))


_DecodedType = _TypeVar("_DecodedType")


def _decode_owned(
    atom: DurableAtom,
    owner_type: type[_DecodedType],
) -> _DecodedType:
    decoded = decode_m1_value(atom)
    if type(decoded) is not owner_type:
        raise TypeError("decoded child atom does not own the required type")
    return decoded


def decode_m1_value(atom: DurableAtom) -> _OwningValue:
    """Decode an atom back to its exact owning M1 value or identity."""

    if type(atom) is not DurableAtom:
        raise TypeError("only DurableAtom instances can be decoded")
    _validate_atom(atom)
    type_tag = atom.type_tag
    if type_tag == "quantity":
        return _values.Quantity(int(_leaf_text(atom, 0)))
    if type_tag == "price_units":
        return _values.PriceUnits(int(_leaf_text(atom, 0)))
    if type_tag == "price_scale":
        return _values.PriceScale(_decode_decimal_leaf(_child_atom(atom, 0)))
    if type_tag == "tick_metadata":
        return _values.TickMetadata(
            tick_units=_decode_owned(_child_atom(atom, 0), _values.PriceUnits),
            scale=_decode_owned(_child_atom(atom, 1), _values.PriceScale),
        )
    if type_tag == "reported_price":
        return _values.ReportedPrice(
            units=_decode_owned(_child_atom(atom, 0), _values.PriceUnits),
            scale=_decode_owned(_child_atom(atom, 1), _values.PriceScale),
            tick=_decode_owned(_child_atom(atom, 2), _values.TickMetadata),
        )
    if type_tag == "exact_basis":
        fraction_atom = _child_atom(atom, 0)
        return _values.ExactBasis(
            _Fraction(
                int(_leaf_text(fraction_atom, 0)),
                int(_leaf_text(fraction_atom, 1)),
            )
        )
    if type_tag == "execution_fact_key":
        return _identity.ExecutionFactKey(
            broker=_decode_owned(_child_atom(atom, 0), _identity.BrokerId),
            environment=_decode_owned(_child_atom(atom, 1), _identity.EnvironmentId),
            account=_decode_owned(_child_atom(atom, 2), _identity.AccountId),
            source_event_id=_decode_owned(
                _child_atom(atom, 3), _identity.SourceEventId
            ),
        )
    if type_tag == "root_fill_key":
        return _identity.RootFillKey(
            broker=_decode_owned(_child_atom(atom, 0), _identity.BrokerId),
            environment=_decode_owned(_child_atom(atom, 1), _identity.EnvironmentId),
            account=_decode_owned(_child_atom(atom, 2), _identity.AccountId),
            root_fill_id=_decode_owned(_child_atom(atom, 3), _identity.RootFillId),
        )
    if type_tag == "venue_leg_key":
        return _identity.VenueLegKey(
            broker=_decode_owned(_child_atom(atom, 0), _identity.BrokerId),
            environment=_decode_owned(_child_atom(atom, 1), _identity.EnvironmentId),
            account=_decode_owned(_child_atom(atom, 2), _identity.AccountId),
            order_id=_decode_owned(_child_atom(atom, 3), _identity.OrderId),
        )
    constructor = _IDENTITY_CONSTRUCTOR_BY_TAG[type_tag]
    decoded: _Any = constructor(_leaf_text(atom, 0))
    return decoded
