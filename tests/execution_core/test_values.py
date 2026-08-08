from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

import pytest

from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionScope,
    ExecutionSide,
)
from app.execution_core.identity import (
    AccountId,
    BrokerId,
    EnvironmentId,
    ExecutionFactKey,
    OrderId,
    RootFillId,
    RootFillKey,
    SourceEventId,
    SymbolId,
)
from app.execution_core.values import (
    ExactBasis,
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)


IDENTITY_TYPES = (
    BrokerId,
    EnvironmentId,
    AccountId,
    SymbolId,
    OrderId,
    RootFillId,
    SourceEventId,
)


def _price(
    units: int = 10_000,
    *,
    scale: str = "0.01",
    tick_units: int = 1,
    tick_scale: str | None = None,
) -> ReportedPrice:
    price_scale = PriceScale(Decimal(scale))
    tick = TickMetadata(
        tick_units=PriceUnits(tick_units),
        scale=PriceScale(Decimal(tick_scale if tick_scale is not None else scale)),
    )
    return ReportedPrice(units=PriceUnits(units), scale=price_scale, tick=tick)


def _scope(
    *,
    broker: BrokerId | None = None,
    environment: EnvironmentId | None = None,
    account: AccountId | None = None,
    order_id: OrderId | None = None,
    symbol_id: SymbolId | None = None,
    side: ExecutionSide = ExecutionSide.BUY,
) -> ExecutionScope:
    return ExecutionScope(
        broker=broker or BrokerId("alpaca"),
        environment=environment or EnvironmentId("paper"),
        account=account or AccountId("account-1"),
        order_id=order_id or OrderId("order-1"),
        symbol_id=symbol_id or SymbolId("AAPL"),
        side=side,
    )


def _key(
    source_event_id: str = "event-1",
    *,
    broker: BrokerId | None = None,
    environment: EnvironmentId | None = None,
    account: AccountId | None = None,
) -> ExecutionFactKey:
    return ExecutionFactKey(
        broker=broker or BrokerId("alpaca"),
        environment=environment or EnvironmentId("paper"),
        account=account or AccountId("account-1"),
        source_event_id=SourceEventId(source_event_id),
    )


def _fill(
    *,
    key: ExecutionFactKey | None = None,
    scope: ExecutionScope | None = None,
    root_fill_id: RootFillId | None = None,
    quantity: Quantity | None = None,
    price: ReportedPrice | None = None,
) -> BrokerFillFact:
    return BrokerFillFact(
        key=key or _key(),
        scope=scope or _scope(),
        root_fill_id=root_fill_id or RootFillId("root-1"),
        quantity=quantity or Quantity(10),
        price=price or _price(),
    )


def _correct(
    *,
    key: ExecutionFactKey | None = None,
    scope: ExecutionScope | None = None,
    root_fill_id: RootFillId | None = None,
    predecessor_source_event_id: SourceEventId | None = None,
    revised_quantity: Quantity | None = None,
    revised_price: ReportedPrice | None = None,
) -> BrokerTradeCorrectFact:
    return BrokerTradeCorrectFact(
        key=key or _key("event-2"),
        scope=scope or _scope(),
        root_fill_id=root_fill_id or RootFillId("root-1"),
        predecessor_source_event_id=(
            predecessor_source_event_id or SourceEventId("event-1")
        ),
        revised_quantity=revised_quantity or Quantity(7),
        revised_price=revised_price or _price(10_100),
    )


def _bust(
    *,
    key: ExecutionFactKey | None = None,
    scope: ExecutionScope | None = None,
    root_fill_id: RootFillId | None = None,
    predecessor_source_event_id: SourceEventId | None = None,
    reported_price: ReportedPrice | None = None,
) -> BrokerTradeBustFact:
    return BrokerTradeBustFact(
        key=key or _key("event-2"),
        scope=scope or _scope(),
        root_fill_id=root_fill_id or RootFillId("root-1"),
        predecessor_source_event_id=(
            predecessor_source_event_id or SourceEventId("event-1")
        ),
        reported_price=reported_price,
    )


def test_quantity_rejects_bool_even_though_bool_is_an_int_subclass() -> None:
    for value in (False, True):
        with pytest.raises(TypeError):
            Quantity(value)


def test_quantity_rejects_every_non_integer_representation() -> None:
    for value in (1.0, Decimal("1"), Fraction(1), "1", None):
        with pytest.raises(TypeError):
            Quantity(value)  # type: ignore[arg-type]


def test_quantity_rejects_negative_integer() -> None:
    for value in (-1, -(10**200)):
        with pytest.raises(ValueError):
            Quantity(value)


def test_quantity_preserves_zero_and_huge_exact_integer() -> None:
    huge = 10**250 + 123456789

    assert Quantity(0).value == 0
    assert Quantity(huge).value == huge
    assert isinstance(Quantity(huge).value, int)


def test_price_units_reject_bool_and_non_integer_without_coercion() -> None:
    for value in (False, True, 1.0, Decimal("1"), Fraction(1), "1", None):
        with pytest.raises(TypeError):
            PriceUnits(value)  # type: ignore[arg-type]


def test_price_units_preserve_signed_and_huge_exact_integers() -> None:
    huge = 10**250 + 987654321

    assert PriceUnits(-huge).value == -huge
    assert PriceUnits(0).value == 0
    assert PriceUnits(huge).value == huge


def test_price_scale_requires_decimal_without_float_or_string_conversion() -> None:
    for value in (True, 1, 0.01, "0.01", Fraction(1, 100), None):
        with pytest.raises(TypeError):
            PriceScale(value)  # type: ignore[arg-type]


def test_price_scale_rejects_non_positive_and_non_finite_decimal() -> None:
    for value in (
        Decimal("0"),
        Decimal("-0"),
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ):
        with pytest.raises(ValueError):
            PriceScale(value)


def test_price_scale_preserves_tiny_finite_decimal_exactly() -> None:
    tiny = Decimal("1E-10000")

    scale = PriceScale(tiny)

    assert scale.value == tiny
    assert isinstance(scale.value, Decimal)
    assert PriceScale(Decimal("0.010")) == PriceScale(Decimal("0.01"))


def test_tick_metadata_requires_positive_price_units_and_explicit_scale() -> None:
    scale = PriceScale(Decimal("0.01"))

    for tick_units in (PriceUnits(0), PriceUnits(-1)):
        with pytest.raises(ValueError):
            TickMetadata(tick_units=tick_units, scale=scale)

    with pytest.raises(TypeError):
        TickMetadata(tick_units=1, scale=scale)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        TickMetadata(
            tick_units=PriceUnits(1),
            scale=Decimal("0.01"),  # type: ignore[arg-type]
        )


def test_reported_price_exposes_exact_fraction_and_alignment() -> None:
    price = _price(12_345, scale="0.01", tick_units=5)

    assert price.is_aligned
    assert price.exact_value == Fraction(2469, 20)
    assert isinstance(price.exact_value, Fraction)


def test_reported_price_alignment_requires_units_and_tick_scale_alignment() -> None:
    assert not _price(12_343, scale="0.01", tick_units=5).is_aligned
    assert not _price(
        12_345,
        scale="0.01",
        tick_units=5,
        tick_scale="0.10",
    ).is_aligned


def test_reported_price_compatibility_is_explicit_and_numeric() -> None:
    left = _price(100, scale="0.010", tick_units=5, tick_scale="0.0100")
    right = _price(200, scale="0.01", tick_units=5)

    assert left.is_aligned
    assert right.is_aligned
    assert left.is_compatible_with(right)
    assert right.is_compatible_with(left)

    assert not left.is_compatible_with(_price(200, scale="0.01", tick_units=10))
    assert not left.is_compatible_with(_price(201, scale="0.01", tick_units=5))


def test_reported_price_never_implicitly_rescales_equal_economic_values() -> None:
    cents = _price(100, scale="0.01", tick_units=1)
    dimes = _price(10, scale="0.1", tick_units=1)

    assert cents.exact_value == dimes.exact_value == Fraction(1)
    assert not cents.is_compatible_with(dimes)
    assert cents != dimes


def test_reported_price_requires_typed_components_but_retains_incompatibility() -> None:
    scale = PriceScale(Decimal("0.01"))
    tick = TickMetadata(PriceUnits(5), scale)

    with pytest.raises(TypeError):
        ReportedPrice(units=100, scale=scale, tick=tick)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ReportedPrice(
            units=PriceUnits(100),
            scale=Decimal("0.01"),  # type: ignore[arg-type]
            tick=tick,
        )
    with pytest.raises(TypeError):
        ReportedPrice(
            units=PriceUnits(100),
            scale=scale,
            tick=(PriceUnits(5), scale),  # type: ignore[arg-type]
        )

    incompatible = _price(101, scale="0.01", tick_units=5)
    assert incompatible.units == PriceUnits(101)
    assert not incompatible.is_aligned


def test_exact_basis_requires_non_negative_fraction_without_conversion() -> None:
    for value in (True, 1, Decimal("1"), 1.0, "1", None):
        with pytest.raises(TypeError):
            ExactBasis(value)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        ExactBasis(Fraction(-1, 3))

    assert ExactBasis(Fraction(0)).value == Fraction(0)


def test_exact_basis_preserves_huge_rational_value() -> None:
    huge = Fraction(10**300 + 1, 3)

    basis = ExactBasis(huge)

    assert basis.value == huge
    assert isinstance(basis.value, Fraction)


def test_identity_wrappers_preserve_exact_nonblank_text() -> None:
    exact = "  Broker/Mixed-Case:01  "

    for identity_type in IDENTITY_TYPES:
        identity = identity_type(exact)
        assert identity.value == exact
        assert identity_type(exact) == identity
        assert identity_type(exact.lower()) != identity


def test_identity_wrappers_reject_blank_and_non_string_values() -> None:
    for identity_type in IDENTITY_TYPES:
        for blank in ("", " ", "\t", "\r\n"):
            with pytest.raises(ValueError):
                identity_type(blank)
        for non_string in (None, True, 1, b"id"):
            with pytest.raises(TypeError):
                identity_type(non_string)  # type: ignore[arg-type]


def test_root_fill_and_source_event_ids_remain_distinct_types() -> None:
    root_fill_id = RootFillId("shared-external-text")
    source_event_id = SourceEventId("shared-external-text")

    assert root_fill_id != source_event_id
    assert len({root_fill_id, source_event_id}) == 2


def test_execution_fact_key_is_the_exact_four_part_dedupe_identity() -> None:
    first = _key()
    exact_retry = _key()
    changed_parts = (
        _key(broker=BrokerId("other-broker")),
        _key(environment=EnvironmentId("other-environment")),
        _key(account=AccountId("other-account")),
        _key("other-event"),
    )

    assert first == exact_retry
    assert hash(first) == hash(exact_retry)
    assert len({first, exact_retry}) == 1
    assert all(candidate != first for candidate in changed_parts)
    assert len({first, *changed_parts}) == 5


def test_execution_fact_key_rejects_cross_typed_identity_components() -> None:
    valid: dict[str, object] = {
        "broker": BrokerId("alpaca"),
        "environment": EnvironmentId("paper"),
        "account": AccountId("account-1"),
        "source_event_id": SourceEventId("event-1"),
    }
    invalid_components = (
        ("broker", EnvironmentId("paper"), "broker must be BrokerId"),
        (
            "environment",
            BrokerId("alpaca"),
            "environment must be EnvironmentId",
        ),
        ("account", SymbolId("AAPL"), "account must be AccountId"),
        (
            "source_event_id",
            RootFillId("root-1"),
            "source event must be SourceEventId",
        ),
    )

    for field_name, invalid_value, message in invalid_components:
        candidate = dict(valid)
        candidate[field_name] = invalid_value
        with pytest.raises(TypeError, match=message):
            ExecutionFactKey(**candidate)  # type: ignore[arg-type]


def test_root_fill_key_is_exact_broker_environment_account_and_root() -> None:
    first = RootFillKey(
        BrokerId("alpaca"),
        EnvironmentId("paper"),
        AccountId("account-1"),
        RootFillId("root-1"),
    )
    exact_retry = RootFillKey(
        BrokerId("alpaca"),
        EnvironmentId("paper"),
        AccountId("account-1"),
        RootFillId("root-1"),
    )
    changed_parts = (
        RootFillKey(
            BrokerId("other"),
            EnvironmentId("paper"),
            AccountId("account-1"),
            RootFillId("root-1"),
        ),
        RootFillKey(
            BrokerId("alpaca"),
            EnvironmentId("other"),
            AccountId("account-1"),
            RootFillId("root-1"),
        ),
        RootFillKey(
            BrokerId("alpaca"),
            EnvironmentId("paper"),
            AccountId("other"),
            RootFillId("root-1"),
        ),
        RootFillKey(
            BrokerId("alpaca"),
            EnvironmentId("paper"),
            AccountId("account-1"),
            RootFillId("other-root"),
        ),
    )

    assert first == exact_retry
    assert hash(first) == hash(exact_retry)
    assert all(candidate != first for candidate in changed_parts)
    assert len({first, exact_retry, *changed_parts}) == 5


def test_root_fill_key_rejects_cross_typed_identity_components() -> None:
    valid: dict[str, object] = {
        "broker": BrokerId("alpaca"),
        "environment": EnvironmentId("paper"),
        "account": AccountId("account-1"),
        "root_fill_id": RootFillId("root-1"),
    }
    invalid_components = (
        ("broker", EnvironmentId("paper"), "broker must be BrokerId"),
        (
            "environment",
            BrokerId("alpaca"),
            "environment must be EnvironmentId",
        ),
        ("account", SymbolId("AAPL"), "account must be AccountId"),
        (
            "root_fill_id",
            SourceEventId("event-1"),
            "root fill must be RootFillId",
        ),
    )

    for field_name, invalid_value, message in invalid_components:
        candidate = dict(valid)
        candidate[field_name] = invalid_value
        with pytest.raises(TypeError, match=message):
            RootFillKey(**candidate)  # type: ignore[arg-type]


def test_execution_scope_is_exact_typed_and_complete() -> None:
    scope = _scope()

    assert scope.broker == BrokerId("alpaca")
    assert scope.environment == EnvironmentId("paper")
    assert scope.account == AccountId("account-1")
    assert scope.order_id == OrderId("order-1")
    assert scope.symbol_id == SymbolId("AAPL")
    assert scope.side is ExecutionSide.BUY
    assert {member.name for member in ExecutionSide} == {"BUY", "SELL"}


def test_execution_scope_rejects_untyped_components() -> None:
    valid = {
        "broker": BrokerId("alpaca"),
        "environment": EnvironmentId("paper"),
        "account": AccountId("account-1"),
        "order_id": OrderId("order-1"),
        "symbol_id": SymbolId("AAPL"),
        "side": ExecutionSide.BUY,
    }

    for field_name in valid:
        invalid = dict(valid)
        invalid[field_name] = "BUY" if field_name == "side" else "raw-id"
        with pytest.raises(TypeError):
            ExecutionScope(**invalid)  # type: ignore[arg-type]


def test_all_value_identity_scope_and_fact_types_are_frozen_and_hashable() -> None:
    instances_and_fields = (
        (Quantity(1), "value"),
        (PriceUnits(100), "value"),
        (PriceScale(Decimal("0.01")), "value"),
        (TickMetadata(PriceUnits(1), PriceScale(Decimal("0.01"))), "tick_units"),
        (_price(), "units"),
        (ExactBasis(Fraction(100)), "value"),
        *((identity_type("id"), "value") for identity_type in IDENTITY_TYPES),
        (_key(), "source_event_id"),
        (
            RootFillKey(
                BrokerId("alpaca"),
                EnvironmentId("paper"),
                AccountId("account-1"),
                RootFillId("root-1"),
            ),
            "root_fill_id",
        ),
        (_scope(), "side"),
        (_fill(), "quantity"),
        (_correct(), "revised_quantity"),
        (_bust(), "reported_price"),
    )

    for instance, field_name in instances_and_fields:
        hash(instance)
        original = getattr(instance, field_name)
        with pytest.raises(AttributeError):
            setattr(instance, field_name, original)


def test_fill_constructor_requires_positive_quantity_and_price() -> None:
    zero_price = _price(0)
    negative_price = _price(-100)

    with pytest.raises(ValueError):
        _fill(quantity=Quantity(0))
    for price in (zero_price, negative_price):
        with pytest.raises(ValueError):
            _fill(price=price)


def test_trade_correct_constructor_requires_positive_revised_economics() -> None:
    zero_price = _price(0)
    negative_price = _price(-100)

    with pytest.raises(ValueError):
        _correct(revised_quantity=Quantity(0))
    for price in (zero_price, negative_price):
        with pytest.raises(ValueError):
            _correct(revised_price=price)


def test_revision_constructors_reject_self_predecessor() -> None:
    key = _key("revision-event")
    predecessor = SourceEventId("revision-event")

    with pytest.raises(ValueError):
        _correct(key=key, predecessor_source_event_id=predecessor)
    with pytest.raises(ValueError):
        _bust(key=key, predecessor_source_event_id=predecessor)


def test_trade_bust_has_structural_zero_quantity_and_optional_price_metadata() -> None:
    without_price = _bust()
    retained_price = _price(10_100)
    with_price = _bust(reported_price=retained_price)

    assert without_price.reported_price is None
    assert with_price.reported_price == retained_price
    assert not hasattr(without_price, "quantity")
    assert not hasattr(without_price, "revised_quantity")
    assert without_price != with_price


def test_trade_bust_rejects_non_positive_optional_reported_price() -> None:
    for price in (_price(0), _price(-100)):
        with pytest.raises(ValueError):
            _bust(reported_price=price)


def test_broker_facts_retain_explicitly_incompatible_price_metadata() -> None:
    misaligned = _price(101, scale="0.01", tick_units=5)

    fill = _fill(price=misaligned)
    correction = _correct(revised_price=misaligned)
    bust = _bust(reported_price=misaligned)

    assert not fill.price.is_aligned
    assert not correction.revised_price.is_aligned
    assert bust.reported_price is not None
    assert not bust.reported_price.is_aligned


def test_fact_constructors_reject_key_scope_broker_environment_account_mismatch() -> (
    None
):
    mismatched_scopes = (
        _scope(broker=BrokerId("other-broker")),
        _scope(environment=EnvironmentId("other-environment")),
        _scope(account=AccountId("other-account")),
    )

    for scope in mismatched_scopes:
        with pytest.raises(ValueError):
            _fill(scope=scope)
        with pytest.raises(ValueError):
            _correct(scope=scope)
        with pytest.raises(ValueError):
            _bust(scope=scope)


def test_fact_constructors_require_typed_root_and_predecessor_lineage() -> None:
    with pytest.raises(TypeError):
        _fill(root_fill_id="root-1")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _correct(root_fill_id="root-1")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _bust(root_fill_id="root-1")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _correct(predecessor_source_event_id="event-1")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        _bust(predecessor_source_event_id="event-1")  # type: ignore[arg-type]


def test_exact_reconstruction_produces_full_payload_equality() -> None:
    facts = (_fill(), _correct(), _bust(), _bust(reported_price=_price(10_100)))
    reconstructions = (
        _fill(),
        _correct(),
        _bust(),
        _bust(reported_price=_price(10_100)),
    )

    for fact, reconstructed in zip(facts, reconstructions, strict=True):
        assert fact == reconstructed
        assert hash(fact) == hash(reconstructed)


def test_full_payload_equality_changes_across_fact_kind_and_key() -> None:
    fill = _fill()
    correction = _correct()
    bust = _bust()

    assert fill != correction
    assert correction != bust
    assert _fill(key=_key("other-event")) != fill
    assert _correct(key=_key("other-revision")) != correction
    assert _bust(key=_key("other-revision")) != bust


def test_full_payload_equality_changes_across_complete_scope() -> None:
    baseline = _fill()
    changed_scopes = (
        _scope(order_id=OrderId("other-order")),
        _scope(symbol_id=SymbolId("MSFT")),
        _scope(side=ExecutionSide.SELL),
    )

    assert all(_fill(scope=scope) != baseline for scope in changed_scopes)


def test_full_payload_equality_changes_across_root_and_predecessor_lineage() -> None:
    fill = _fill()
    correction = _correct()
    bust = _bust()

    assert _fill(root_fill_id=RootFillId("other-root")) != fill
    assert _correct(root_fill_id=RootFillId("other-root")) != correction
    assert (
        _correct(predecessor_source_event_id=SourceEventId("other-predecessor"))
        != correction
    )
    assert _bust(root_fill_id=RootFillId("other-root")) != bust
    assert _bust(predecessor_source_event_id=SourceEventId("other-predecessor")) != bust


def test_full_payload_equality_changes_across_economics() -> None:
    fill = _fill()
    correction = _correct()

    assert _fill(quantity=Quantity(11)) != fill
    assert _fill(price=_price(10_001)) != fill
    assert _correct(revised_quantity=Quantity(8)) != correction
    assert _correct(revised_price=_price(10_101)) != correction


def test_full_payload_equality_changes_across_scale_and_tick_metadata() -> None:
    baseline_price = _price(100, scale="0.01", tick_units=1)
    same_value_new_scale = _price(10, scale="0.1", tick_units=1)
    same_value_new_tick = _price(100, scale="0.01", tick_units=2)
    baseline = _fill(price=baseline_price)

    assert baseline_price.exact_value == same_value_new_scale.exact_value
    assert _fill(price=same_value_new_scale) != baseline
    assert _fill(price=same_value_new_tick) != baseline
    assert _correct(revised_price=same_value_new_scale) != _correct(
        revised_price=baseline_price
    )
    assert _bust(reported_price=same_value_new_tick) != _bust(
        reported_price=baseline_price
    )
