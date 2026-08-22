"""Failure-capable round-trip and refusal pins for the M2-I1 durable codec.

The codec is a v1 wire contract: these tests pin the exact canonical atom
shapes, prove exact type/value preservation for every owning M1 class, and
refuse every malformed, reordered, duplicate, noncanonical, or forged atom
variant without normalization or repair.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from fractions import Fraction

import pytest

from app.execution_core.durable_codec import (
    DurableAtom,
    decode_m1_value,
    encode_m1_value,
)
from app.execution_core.fills import BrokerFillFact, ExecutionScope, ExecutionSide
from app.execution_core.identity import (
    AccountId,
    ActorId,
    AcquisitionGenerationId,
    AcquisitionMandateId,
    ApplicationGenerationId,
    AuthorityInputId,
    BrokerId,
    ClaimOccurrenceId,
    ClientOrderId,
    ClosureId,
    EffectId,
    EmergencyGrantId,
    EmergencyRecoveryCompatibilityId,
    EnvironmentId,
    EvidenceReference,
    ExecutionFactKey,
    ManualFlattenId,
    MandateId,
    MarketDataSourceId,
    MarketOccurrenceId,
    MarketStreamGenerationId,
    OrderId,
    QueryClaimId,
    RequestOccurrenceId,
    RootFillId,
    RootFillKey,
    SessionId,
    SourceEventId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.values import (
    ExactBasis,
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)


CONTRACT_VERSION = "1"

_HEX_64_A = "ab" * 32
_HEX_64_B = "cd" * 32
_HEX_64_C = "ef" * 32

ALL_IDENTITY_CLASSES = (
    BrokerId,
    EnvironmentId,
    AccountId,
    SymbolId,
    OrderId,
    RootFillId,
    SourceEventId,
    ApplicationGenerationId,
    EffectId,
    RequestOccurrenceId,
    ClientOrderId,
    ClaimOccurrenceId,
    ClosureId,
    VenueInputId,
    VenueObservationId,
    ActorId,
    EvidenceReference,
    MandateId,
    AcquisitionMandateId,
    EmergencyRecoveryCompatibilityId,
    MarketDataSourceId,
    MarketOccurrenceId,
    MarketStreamGenerationId,
    AcquisitionGenerationId,
    AuthorityInputId,
    QueryClaimId,
    SessionId,
    EmergencyGrantId,
    ManualFlattenId,
)

_HEX_IDENTITY_CLASSES = frozenset(
    {MarketOccurrenceId, MarketStreamGenerationId, AcquisitionGenerationId}
)


def _identity_sample(identity_class: type) -> str:
    if identity_class in _HEX_IDENTITY_CLASSES:
        return _HEX_64_A
    return "id-α-01"


def _price(
    units: int = 10_000,
    *,
    scale: str = "0.01",
    tick_units: int = 1,
) -> ReportedPrice:
    price_scale = PriceScale(Decimal(scale))
    return ReportedPrice(
        units=PriceUnits(units),
        scale=price_scale,
        tick=TickMetadata(
            tick_units=PriceUnits(tick_units),
            scale=price_scale,
        ),
    )


def _round_trip_cases() -> tuple[object, ...]:
    return (
        Quantity(0),
        Quantity(1),
        Quantity(10**250 + 123456789),
        PriceUnits(-(10**250 + 987654321)),
        PriceUnits(0),
        PriceUnits(10**250 + 987654321),
        PriceScale(Decimal("0.01")),
        PriceScale(Decimal("0.010")),
        PriceScale(Decimal("1E+3")),
        PriceScale(Decimal("1E-10000")),
        TickMetadata(tick_units=PriceUnits(5), scale=PriceScale(Decimal("0.0001"))),
        ReportedPrice(
            units=PriceUnits(-12345),
            scale=PriceScale(Decimal("0.001")),
            tick=TickMetadata(
                tick_units=PriceUnits(1),
                scale=PriceScale(Decimal("0.001")),
            ),
        ),
        ExactBasis(Fraction(0)),
        ExactBasis(Fraction(22, 7)),
        ExactBasis(Fraction(4, 8)),
        ExactBasis(Fraction(10**300 + 1, 3)),
    )


def _forge(
    contract_version: object,
    type_tag: object,
    fields: object,
) -> DurableAtom:
    """Build an atom outside the validating constructor to exercise decode."""

    atom = object.__new__(DurableAtom)
    object.__setattr__(atom, "contract_version", contract_version)
    object.__setattr__(atom, "type_tag", type_tag)
    object.__setattr__(atom, "fields", fields)
    return atom


def _assert_only_text_and_atoms(node: object) -> None:
    if type(node) is DurableAtom:
        assert isinstance(node.fields, tuple)
        for child in node.fields:
            _assert_only_text_and_atoms(child)
        return
    assert type(node) is str


# ---------------------------------------------------------------------------
# AC-1 / AC-2: exact round trips.


@pytest.mark.parametrize(
    "case",
    _round_trip_cases(),
    ids=lambda case: type(case).__name__,
)
def test_value_round_trip_preserves_exact_type_and_constructor_value(
    case: object,
) -> None:
    atom = encode_m1_value(case)

    decoded = decode_m1_value(atom)

    assert type(decoded) is type(case)
    assert decoded == case
    assert hash(decoded) == hash(case)
    assert decode_m1_value(encode_m1_value(decoded)) == decoded


def test_price_scale_decimal_tuple_survives_round_trip_exactly() -> None:
    cases = (
        Decimal("0.01"),
        Decimal("0.010"),
        Decimal("42"),
        Decimal("1E+3"),
        Decimal("7.5"),
        Decimal("1E-10000"),
    )

    for value in cases:
        original = PriceScale(value)
        decoded = decode_m1_value(encode_m1_value(original))

        assert type(decoded.value) is Decimal
        assert decoded.value.as_tuple() == original.value.as_tuple()
        assert decoded == original


def test_exact_basis_fraction_ratio_survives_round_trip_reduced() -> None:
    original = ExactBasis(Fraction(4, 8))

    decoded = decode_m1_value(encode_m1_value(original))

    assert decoded.value.numerator == 1
    assert decoded.value.denominator == 2
    assert decoded == original


@pytest.mark.parametrize(
    "identity_class",
    ALL_IDENTITY_CLASSES,
    ids=lambda identity_class: identity_class.__name__,
)
def test_identity_round_trip_preserves_exact_class_and_public_text(
    identity_class: type,
) -> None:
    value = identity_class(_identity_sample(identity_class))

    atom = encode_m1_value(value)
    decoded = decode_m1_value(atom)

    assert type(decoded) is identity_class
    assert decoded == value
    assert hash(decoded) == hash(value)
    assert decoded.value == value.value


def test_identity_exact_text_including_padding_round_trips() -> None:
    exact = "  Mixed-Case/café:01  "

    decoded = decode_m1_value(encode_m1_value(BrokerId(exact)))

    assert decoded.value == exact


def test_hex_strict_identities_keep_lowercase_sha256_text() -> None:
    for identity_class in sorted(_HEX_IDENTITY_CLASSES, key=lambda item: item.__name__):
        value = identity_class(_HEX_64_B)

        decoded = decode_m1_value(encode_m1_value(value))

        assert decoded.value == _HEX_64_B
        assert decoded._bytes.hex() == _HEX_64_B
        assert decoded._seal == value._seal


def test_composite_keys_round_trip_with_exact_types_and_equality() -> None:
    fact_key = ExecutionFactKey(
        broker=BrokerId("alpaca"),
        environment=EnvironmentId("paper"),
        account=AccountId("account-1"),
        source_event_id=SourceEventId("event-1"),
    )
    root_key = RootFillKey(
        broker=BrokerId("alpaca"),
        environment=EnvironmentId("paper"),
        account=AccountId("account-1"),
        root_fill_id=RootFillId("root-1"),
    )
    leg_key = VenueLegKey(
        broker=BrokerId("alpaca"),
        environment=EnvironmentId("paper"),
        account=AccountId("account-1"),
        order_id=OrderId("order-1"),
    )

    for key in (fact_key, root_key, leg_key):
        decoded = decode_m1_value(encode_m1_value(key))

        assert type(decoded) is type(key)
        assert decoded == key
        assert hash(decoded) == hash(key)


def test_composite_keys_stay_distinct_across_same_member_texts() -> None:
    members = (BrokerId("b"), EnvironmentId("e"), AccountId("a"))
    fact = ExecutionFactKey(*members, source_event_id=SourceEventId("s"))
    root = RootFillKey(*members, root_fill_id=RootFillId("s"))
    leg = VenueLegKey(*members, order_id=OrderId("s"))

    atoms = {encode_m1_value(key) for key in (fact, root, leg)}

    assert len(atoms) == 3
    decoded_fact = decode_m1_value(encode_m1_value(fact))
    assert decoded_fact != root
    assert type(decoded_fact.source_event_id) is SourceEventId


# ---------------------------------------------------------------------------
# Canonical wire-shape pins.


def test_quantity_atom_has_the_exact_v1_wire_shape() -> None:
    assert encode_m1_value(Quantity(5)) == DurableAtom(
        CONTRACT_VERSION, "quantity", ("5",)
    )
    assert encode_m1_value(PriceUnits(-5)) == DurableAtom(
        CONTRACT_VERSION, "price_units", ("-5",)
    )
    assert encode_m1_value(BrokerId("x")) == DurableAtom(
        CONTRACT_VERSION, "broker_id", ("x",)
    )
    assert encode_m1_value(MarketOccurrenceId(_HEX_64_A)).fields == ((_HEX_64_A,))


def test_decimal_atom_persists_the_exact_sign_digits_exponent_tuple() -> None:
    atom = encode_m1_value(PriceScale(Decimal("0.010")))

    decimal_atom = atom.fields[0]

    assert type(decimal_atom) is DurableAtom
    assert decimal_atom.type_tag == "_decimal"
    assert decimal_atom.contract_version == CONTRACT_VERSION
    assert decimal_atom.fields == ("0", "10", "-3")


def test_fraction_atom_persists_reduced_numerator_and_positive_denominator() -> None:
    atom = encode_m1_value(ExactBasis(Fraction(-8, -4)))

    fraction_atom = atom.fields[0]

    assert type(fraction_atom) is DurableAtom
    assert fraction_atom.type_tag == "_fraction"
    assert fraction_atom.fields == ("2", "1")


def test_atoms_never_persist_private_seals_caches_or_bytes() -> None:
    sealed = MarketOccurrenceId(_HEX_64_C)

    atom = encode_m1_value(sealed)

    _assert_only_text_and_atoms(atom)
    assert atom.fields == ((_HEX_64_C,))
    assert len(atom.fields) == 1

    decoded = decode_m1_value(atom)

    assert decoded is not sealed
    assert decoded == sealed
    assert decoded._seal == sealed._seal


# ---------------------------------------------------------------------------
# EC-1: unknown version/tag refused; no fallback decode.


@pytest.mark.parametrize("version", ["0", "2", "m1-v1", "", "１"])
def test_atom_constructor_refuses_unknown_contract_version(version: str) -> None:
    with pytest.raises(ValueError):
        DurableAtom(version, "quantity", ("5",))


@pytest.mark.parametrize("type_tag", ["mystery", "Quantity", "", "quantity "])
def test_atom_constructor_refuses_unknown_type_tag(type_tag: str) -> None:
    with pytest.raises(ValueError):
        DurableAtom(CONTRACT_VERSION, type_tag, ("5",))


def test_decode_refuses_forged_unknown_version_or_tag_without_fallback() -> None:
    good = encode_m1_value(Quantity(1))

    for forgery in (
        _forge("2", good.type_tag, good.fields),
        _forge("", good.type_tag, good.fields),
        _forge(None, good.type_tag, good.fields),
        _forge(CONTRACT_VERSION, "nope", good.fields),
        _forge(CONTRACT_VERSION, "", good.fields),
        _forge(CONTRACT_VERSION, None, good.fields),
    ):
        with pytest.raises((TypeError, ValueError)):
            decode_m1_value(forgery)


# ---------------------------------------------------------------------------
# EC-2: shape refusals without normalization or partial objects.


def test_atom_constructor_refuses_non_tuple_fields() -> None:
    with pytest.raises(TypeError):
        DurableAtom(CONTRACT_VERSION, "quantity", ["5"])
    with pytest.raises(TypeError):
        DurableAtom(CONTRACT_VERSION, "quantity", None)


def test_atom_constructor_refuses_missing_extra_duplicate_fields() -> None:
    with pytest.raises(ValueError):
        DurableAtom(CONTRACT_VERSION, "quantity", ())
    with pytest.raises(ValueError):
        DurableAtom(CONTRACT_VERSION, "quantity", ("5", "6"))
    with pytest.raises(ValueError):
        DurableAtom(CONTRACT_VERSION, "quantity", ("6", "6"))


def test_atom_constructor_refuses_wrong_type_field_elements() -> None:
    with pytest.raises(TypeError):
        DurableAtom(CONTRACT_VERSION, "quantity", (5,))
    with pytest.raises(TypeError):
        DurableAtom(CONTRACT_VERSION, "quantity", (None,))
    with pytest.raises(TypeError):
        DurableAtom(CONTRACT_VERSION, "quantity", (encode_m1_value(Quantity(1)),))


def test_atom_constructor_refuses_wrong_child_atom_tags_by_position() -> None:
    units = encode_m1_value(PriceUnits(1))
    scale = encode_m1_value(PriceScale(Decimal("0.01")))
    tick = encode_m1_value(
        TickMetadata(tick_units=PriceUnits(1), scale=PriceScale(Decimal("0.01")))
    )

    with pytest.raises(ValueError):
        DurableAtom(CONTRACT_VERSION, "tick_metadata", (scale, units))
    with pytest.raises(ValueError):
        DurableAtom(CONTRACT_VERSION, "reported_price", (scale, units, tick))
    with pytest.raises(ValueError):
        DurableAtom(CONTRACT_VERSION, "reported_price", (units, scale, units))
    with pytest.raises(ValueError):
        DurableAtom(
            CONTRACT_VERSION,
            "execution_fact_key",
            (units, scale, tick, units),
        )
    with pytest.raises(ValueError):
        DurableAtom(
            CONTRACT_VERSION,
            "execution_fact_key",
            (
                encode_m1_value(BrokerId("b")),
                encode_m1_value(EnvironmentId("e")),
                encode_m1_value(AccountId("a")),
                encode_m1_value(RootFillId("s")),
            ),
        )


def test_decode_refuses_reordered_composite_children() -> None:
    price = _price()
    atom = encode_m1_value(price)

    reversed_atom = _forge(
        CONTRACT_VERSION, atom.type_tag, tuple(reversed(atom.fields))
    )

    with pytest.raises(ValueError):
        decode_m1_value(reversed_atom)


def test_decode_refuses_text_where_child_atom_is_required() -> None:
    forgery = _forge(CONTRACT_VERSION, "tick_metadata", ("1", "0.01"))

    with pytest.raises((TypeError, ValueError)):
        decode_m1_value(forgery)


# ---------------------------------------------------------------------------
# FR-2 / EC-3: integer text canonicality.


@pytest.mark.parametrize(
    "text",
    [
        "+5",
        "05",
        "00",
        "-0",
        "--5",
        "",
        " ",
        " 5",
        "5 ",
        "1_000",
        "1.0",
        "0x5",
        "١٢",
        "五",
        "5\n",
    ],
)
def test_quantity_atom_refuses_every_noncanonical_integer_text(text: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        DurableAtom(CONTRACT_VERSION, "quantity", (text,))


@pytest.mark.parametrize(
    "text",
    [
        "+5",
        "05",
        "-0",
        "",
        "١٢",
        "5 ",
    ],
)
def test_price_units_atom_refuses_noncanonical_signed_integer_text(
    text: str,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        DurableAtom(CONTRACT_VERSION, "price_units", (text,))


def test_decode_refuses_negative_text_for_nonnegative_owning_value() -> None:
    forgery = _forge(CONTRACT_VERSION, "quantity", ("-5",))

    with pytest.raises(ValueError):
        decode_m1_value(forgery)


def test_decode_refuses_forged_noncanonical_integer_forms() -> None:
    for text in ("+5", "05", "-0", "١٢"):
        with pytest.raises(ValueError):
            decode_m1_value(_forge(CONTRACT_VERSION, "quantity", (text,)))
        with pytest.raises(ValueError):
            decode_m1_value(_forge(CONTRACT_VERSION, "price_units", (text,)))


# ---------------------------------------------------------------------------
# FR-3 / EC-3: decimal and rational component canonicality.


@pytest.mark.parametrize(
    "components",
    [
        ("2", "5", "0"),
        ("-1", "5", "0"),
        ("00", "5", "0"),
        ("", "5", "0"),
        ("0", "", "0"),
        ("0", "00", "0"),
        ("0", "010", "0"),
        ("0", "1a", "0"),
        ("0", "١", "0"),
        ("0", "5", "+3"),
        ("0", "5", "03"),
        ("0", "5", ""),
        ("0", "5", "--1"),
        ("0", "5", "1.0"),
    ],
)
def test_decimal_atom_refuses_noncanonical_components(
    components: tuple[str, str, str],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        DurableAtom(CONTRACT_VERSION, "_decimal", components)


def test_price_scale_owner_refuses_structurally_valid_negative_zero() -> None:
    negative_zero = DurableAtom(CONTRACT_VERSION, "_decimal", ("1", "0", "0"))
    atom = DurableAtom(CONTRACT_VERSION, "price_scale", (negative_zero,))

    with pytest.raises(ValueError):
        decode_m1_value(atom)


@pytest.mark.parametrize(
    "components",
    [
        ("+1", "2"),
        ("01", "2"),
        ("1", "0"),
        ("1", "-2"),
        ("1", "04"),
        ("1", ""),
        ("1", "٢"),
        ("", "2"),
        ("1", "2", "3"),
    ],
)
def test_fraction_atom_refuses_noncanonical_ratio_components(
    components: tuple[str, ...],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        DurableAtom(CONTRACT_VERSION, "_fraction", components)


def test_zero_denominator_is_refused_before_fraction_construction() -> None:
    zero_denominator = _forge(CONTRACT_VERSION, "_fraction", ("1", "0"))

    with pytest.raises(ValueError):
        DurableAtom(CONTRACT_VERSION, "exact_basis", (zero_denominator,))
    with pytest.raises(ValueError):
        decode_m1_value(
            DurableAtom(CONTRACT_VERSION, "exact_basis", (zero_denominator,))
        )


# ---------------------------------------------------------------------------
# EC-2: identity text canonicality at both directions.


def test_encode_refuses_non_nfc_identity_text_without_normalization() -> None:
    decomposed = SymbolId("cafe\u0301")

    assert decomposed.value == "cafe\u0301"
    with pytest.raises(ValueError):
        encode_m1_value(decomposed)


def test_encode_refuses_control_bearing_identity_text() -> None:
    for text in ("bad\u0007bell", "tab\tinside", "line\nbreak", "del\u007f"):
        with pytest.raises(ValueError):
            encode_m1_value(SymbolId(text))


def test_decode_refuses_non_nfc_and_control_text_from_forged_atoms() -> None:
    with pytest.raises(ValueError):
        decode_m1_value(_forge(CONTRACT_VERSION, "symbol_id", ("cafe\u0301",)))
    with pytest.raises(ValueError):
        decode_m1_value(_forge(CONTRACT_VERSION, "symbol_id", ("bad\u0007bell",)))
    with pytest.raises(ValueError):
        decode_m1_value(_forge(CONTRACT_VERSION, "symbol_id", ("",)))
    with pytest.raises(TypeError):
        decode_m1_value(_forge(CONTRACT_VERSION, "symbol_id", (5,)))


def test_accepted_unicode_text_round_trips_byte_exactly() -> None:
    exact = "génération-α-✓-01"

    decoded = decode_m1_value(encode_m1_value(SessionId(exact)))

    assert decoded.value == exact


# ---------------------------------------------------------------------------
# Typed-route boundary: foreign M1 objects are outside the codec contract.


def test_encode_refuses_objects_outside_the_m1_codec_contract() -> None:
    scope = ExecutionScope(
        broker=BrokerId("alpaca"),
        environment=EnvironmentId("paper"),
        account=AccountId("account-1"),
        order_id=OrderId("order-1"),
        symbol_id=SymbolId("AAPL"),
        side=ExecutionSide.BUY,
    )
    fill = BrokerFillFact(
        key=ExecutionFactKey(
            broker=BrokerId("alpaca"),
            environment=EnvironmentId("paper"),
            account=AccountId("account-1"),
            source_event_id=SourceEventId("event-1"),
        ),
        scope=scope,
        root_fill_id=RootFillId("root-1"),
        quantity=Quantity(1),
        price=_price(),
    )

    for foreign in (None, 5, "quantity", scope, fill):
        with pytest.raises((TypeError, ValueError)):
            encode_m1_value(foreign)


def test_decode_refuses_non_atom_inputs() -> None:
    for foreign in (None, 5, "atom", ("1", "quantity", ("5",))):
        with pytest.raises(TypeError):
            decode_m1_value(foreign)  # type: ignore[arg-type]


def test_decoded_atoms_are_immutable() -> None:
    atom = encode_m1_value(Quantity(1))

    with pytest.raises(dataclasses.FrozenInstanceError):
        atom.type_tag = "price_units"  # type: ignore[misc]
