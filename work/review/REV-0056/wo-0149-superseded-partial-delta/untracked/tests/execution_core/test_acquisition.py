"""RED-first contracts for the pure WO-0149 acquisition semantic center.

These examples use only immutable domain values.  They intentionally import the
new vocabulary lazily so the contract is failure-capable before production code
exists.  No clock, database, broker, adapter, or runtime fixture is used.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from fractions import Fraction
import importlib
import inspect
import textwrap
from types import ModuleType

import pytest

from app.execution_core.fills import (
    BrokerFillFact,
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionScope,
    ExecutionSide,
    PositionScope,
)
from app.execution_core.identity import (
    AccountId,
    ApplicationGenerationId,
    BrokerId,
    ClaimOccurrenceId,
    ClientOrderId,
    ClosureId,
    EvidenceReference,
    EffectId,
    EnvironmentId,
    ExecutionFactKey,
    MandateId,
    MarketDataSourceId,
    MarketStreamGenerationId,
    OrderId,
    RequestOccurrenceId,
    RootFillId,
    SessionId,
    SourceEventId,
    SymbolId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.protection import (
    EvidencePolicy,
    ExecutionGuard,
    MarketKind,
    MarketOccurrence,
    MarketSequenceMode,
    ProtectionPolicy,
    ProtectionMandate,
)
from app.execution_core.position import ExecutionSnapshot
from app.execution_core.recovery import (
    RecordBrokerFillEvidence,
    RecordBrokerRevisionEvidence,
)
from app.execution_core.values import (
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)
from app.execution_core.venue import (
    BrokerEffectState,
    DiscoverVenueLeg,
    EffectKind,
    ObserveVenueStatus,
    RecordDispatchClaim,
    RecordPendingVenueOperation,
    RecordTransportOutcome,
    RequestedEffect,
    PendingVenueOperation,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueScope,
    _apply_venue_input,
)


BROKER = "alpaca"
ENVIRONMENT = "paper"
ACCOUNT = AccountId("acquisition-account")
SYMBOL = SymbolId("AAPL")
POSITION_SCOPE = PositionScope(
    broker=BrokerId(BROKER),
    environment=EnvironmentId(ENVIRONMENT),
    account=ACCOUNT,
    symbol_id=SYMBOL,
)
SESSION = SessionId("acquisition-session")
VENUE_SCOPE = VenueScope(
    generation=ApplicationGenerationId("acquisition-generation"),
    broker=BrokerId(BROKER),
    environment=EnvironmentId(ENVIRONMENT),
    account=ACCOUNT,
)
SCALE = PriceScale(Decimal("1"))
TICK = TickMetadata(tick_units=PriceUnits(1), scale=SCALE)
MAXIMUM_ENTRY_PRICE = ReportedPrice(
    units=PriceUnits(100),
    scale=SCALE,
    tick=TICK,
)


def _acquisition_module() -> ModuleType:
    try:
        return importlib.import_module("app.execution_core.acquisition")
    except ModuleNotFoundError as exc:
        pytest.fail(f"WO-0149 acquisition module is not implemented: {exc}")


def _required(module: ModuleType, *names: str) -> tuple[object, ...]:
    missing = tuple(name for name in names if not hasattr(module, name))
    assert not missing, f"missing WO-0149 acquisition API: {missing!r}"
    return tuple(getattr(module, name) for name in names)


def _protection_mandate(
    *,
    position_scope: PositionScope = POSITION_SCOPE,
    session_id: SessionId = SESSION,
    configuration_version: str = "acquisition-v1",
) -> ProtectionMandate:
    return ProtectionMandate(
        mandate_id=MandateId("acquisition-protection"),
        position_scope=position_scope,
        session_id=session_id,
        configuration_version=configuration_version,
        loss_fraction=Fraction(3, 40),
        approved_gain=Fraction(3, 40),
        percent_trail_fraction=Fraction(2, 25),
        atr_multiple=Fraction(5, 2),
        tick=TICK,
        normal_guard=ExecutionGuard("normal", b"n" * 32),
        emergency_guard=ExecutionGuard("emergency", b"e" * 32),
        evidence_policy=EvidencePolicy(
            source_id=MarketDataSourceId("sip-primary"),
            stream_generation=MarketStreamGenerationId("11" * 32),
            sequence_mode=MarketSequenceMode.SEQUENCED,
            max_age=10,
            corroboration_window=10,
            max_step_fraction=Fraction(1, 2),
        ),
        maximum_quantity=Quantity(10),
        maximum_goal_rate=2,
        deadline=100,
    )


def _mandate(
    module: ModuleType,
    *,
    protection_mandate: ProtectionMandate | None = None,
    maximum_quantity: Quantity = Quantity(5),
    maximum_notional: Fraction = Fraction(500),
    allowed_order_types: tuple[object, ...] | None = None,
) -> object:
    acquisition_id_type, order_type, mandate_type = _required(
        module,
        "AcquisitionMandateId",
        "AcquisitionOrderType",
        "AcquisitionMandate",
    )
    return mandate_type(  # type: ignore[operator]
        acquisition_mandate_id=acquisition_id_type("acquisition-1"),
        position_scope=POSITION_SCOPE,
        session_id=SESSION,
        configuration_version="acquisition-v1",
        maximum_quantity=maximum_quantity,
        maximum_notional=maximum_notional,
        maximum_entry_price=MAXIMUM_ENTRY_PRICE,
        allowed_order_types=(
            allowed_order_types
            if allowed_order_types is not None
            else (order_type.LIMIT,)  # type: ignore[attr-defined]
        ),
        expiry=90,
        deadline=100,
        fixed_child_cap=Quantity(2),
        certified_participation_cap=Fraction(1, 4),
        cancel_reprice_budget=3,
        protection_mandate=(
            protection_mandate
            if protection_mandate is not None
            else _protection_mandate()
        ),
    )


def _market_occurrence(
    *,
    label: str,
    bid: int,
    ask: int,
    sequence: int,
    source_time: int,
    position_scope: PositionScope = POSITION_SCOPE,
    session_id: SessionId = SESSION,
) -> MarketOccurrence:
    """Return one exact routed market occurrence for the acquisition mandate."""

    del label
    return MarketOccurrence(
        source_id=MarketDataSourceId("sip-primary"),
        stream_generation=MarketStreamGenerationId("11" * 32),
        position_scope=position_scope,
        session_id=session_id,
        market_epoch=0,
        source_sequence=sequence,
        source_time=source_time,
        evaluation_time=source_time,
        kind=MarketKind.BEST_BID,
        best_bid=ReportedPrice(
            units=PriceUnits(bid),
            scale=SCALE,
            tick=TICK,
        ),
        best_ask=ReportedPrice(
            units=PriceUnits(ask),
            scale=SCALE,
            tick=TICK,
        ),
        trade_price=None,
        atr_distance=None,
        structure_trail=None,
        halted=False,
    )


def _initial_bound_venue_transition(mandate: object) -> object:
    transition = _apply_venue_input(
        VenueRecoveryBook.empty(VENUE_SCOPE),
        ExecutionSnapshot.flat(POSITION_SCOPE),
        RequestedEffect(
            input_id=VenueInputId("initial-bound-buy-input"),
            effect_id=EffectId("initial-bound-buy-effect"),
            request_occurrence_id=RequestOccurrenceId("initial-bound-buy-request"),
            mandate_id=mandate.protection_mandate.mandate_id,
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("initial-bound-buy-client"),
            symbol_id=SYMBOL,
            side=ExecutionSide.BUY,
            quantity=Quantity(2),
            economic_scope=b"commitment-only-not-policy",
            dual_mandate_binding=mandate.binding,
        ),
    )
    assert transition.disposition is VenueRecoveryDisposition.APPLIED
    return transition


def _bound_buy_fill_transitions(mandate: object) -> tuple[object, object]:
    """Build one direct test fixture; production ingress remains authority-owned."""

    requested = _initial_bound_venue_transition(mandate)
    effect_id = EffectId("initial-bound-buy-effect")
    leg_key = VenueLegKey(
        broker=BrokerId(BROKER),
        environment=EnvironmentId(ENVIRONMENT),
        account=ACCOUNT,
        order_id=OrderId("initial-bound-buy-order"),
    )
    claimed = _apply_venue_input(
        requested.book,
        requested.execution,
        RecordDispatchClaim(
            input_id=VenueInputId("initial-bound-buy-claim-input"),
            effect_id=effect_id,
            claim_occurrence_id=ClaimOccurrenceId("initial-bound-buy-claim"),
        ),
    )
    acknowledged = _apply_venue_input(
        claimed.book,
        claimed.execution,
        RecordTransportOutcome(
            input_id=VenueInputId("initial-bound-buy-ack-input"),
            effect_id=effect_id,
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    discovered = _apply_venue_input(
        acknowledged.book,
        acknowledged.execution,
        DiscoverVenueLeg(
            input_id=VenueInputId("initial-bound-buy-discover-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            observation_id=VenueObservationId("initial-bound-buy-discovery"),
        ),
    )
    filled = _apply_venue_input(
        discovered.book,
        discovered.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("initial-bound-buy-fill-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=BrokerFillFact(
                key=ExecutionFactKey(
                    broker=BrokerId(BROKER),
                    environment=EnvironmentId(ENVIRONMENT),
                    account=ACCOUNT,
                    source_event_id=SourceEventId("initial-bound-buy-fill-source"),
                ),
                scope=ExecutionScope(
                    broker=BrokerId(BROKER),
                    environment=EnvironmentId(ENVIRONMENT),
                    account=ACCOUNT,
                    order_id=leg_key.order_id,
                    symbol_id=SYMBOL,
                    side=ExecutionSide.BUY,
                ),
                root_fill_id=RootFillId("initial-bound-buy-fill-root"),
                quantity=Quantity(2),
                price=MAXIMUM_ENTRY_PRICE,
            ),
            evidence_digest=b"\x71" * 32,
        ),
    )
    assert filled.disposition is VenueRecoveryDisposition.APPLIED
    return requested, filled


def _correct_bound_buy_root(filled: object) -> object:
    """Replace the one owned BUY root through the existing canonical revision path."""

    leg_key = VenueLegKey(
        broker=BrokerId(BROKER),
        environment=EnvironmentId(ENVIRONMENT),
        account=ACCOUNT,
        order_id=OrderId("initial-bound-buy-order"),
    )
    corrected = _apply_venue_input(
        filled.book,
        filled.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("initial-bound-buy-correct-input"),
            effect_id=EffectId("initial-bound-buy-effect"),
            leg_key=leg_key,
            prior_root_quantity=Quantity(2),
            prior_venue_cumulative_quantity=Quantity(2),
            resulting_venue_cumulative_quantity=Quantity(1),
            fact=BrokerTradeCorrectFact(
                key=ExecutionFactKey(
                    broker=BrokerId(BROKER),
                    environment=EnvironmentId(ENVIRONMENT),
                    account=ACCOUNT,
                    source_event_id=SourceEventId("initial-bound-buy-correct-source"),
                ),
                scope=ExecutionScope(
                    broker=BrokerId(BROKER),
                    environment=EnvironmentId(ENVIRONMENT),
                    account=ACCOUNT,
                    order_id=leg_key.order_id,
                    symbol_id=SYMBOL,
                    side=ExecutionSide.BUY,
                ),
                root_fill_id=RootFillId("initial-bound-buy-fill-root"),
                predecessor_source_event_id=SourceEventId(
                    "initial-bound-buy-fill-source"
                ),
                revised_quantity=Quantity(1),
                revised_price=ReportedPrice(
                    units=PriceUnits(90),
                    scale=SCALE,
                    tick=TICK,
                ),
            ),
            evidence_digest=b"\x72" * 32,
        ),
    )
    assert corrected.disposition is VenueRecoveryDisposition.APPLIED
    return corrected


def _bust_corrected_bound_buy_root(corrected: object) -> object:
    """Bust the corrected owned root through the same canonical replacement path."""

    leg_key = VenueLegKey(
        broker=BrokerId(BROKER),
        environment=EnvironmentId(ENVIRONMENT),
        account=ACCOUNT,
        order_id=OrderId("initial-bound-buy-order"),
    )
    busted = _apply_venue_input(
        corrected.book,
        corrected.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("initial-bound-buy-bust-input"),
            effect_id=EffectId("initial-bound-buy-effect"),
            leg_key=leg_key,
            prior_root_quantity=Quantity(1),
            prior_venue_cumulative_quantity=Quantity(1),
            resulting_venue_cumulative_quantity=Quantity(0),
            fact=BrokerTradeBustFact(
                key=ExecutionFactKey(
                    broker=BrokerId(BROKER),
                    environment=EnvironmentId(ENVIRONMENT),
                    account=ACCOUNT,
                    source_event_id=SourceEventId("initial-bound-buy-bust-source"),
                ),
                scope=ExecutionScope(
                    broker=BrokerId(BROKER),
                    environment=EnvironmentId(ENVIRONMENT),
                    account=ACCOUNT,
                    order_id=leg_key.order_id,
                    symbol_id=SYMBOL,
                    side=ExecutionSide.BUY,
                ),
                root_fill_id=RootFillId("initial-bound-buy-fill-root"),
                predecessor_source_event_id=SourceEventId(
                    "initial-bound-buy-correct-source"
                ),
            ),
            evidence_digest=b"\x73" * 32,
        ),
    )
    assert busted.disposition is VenueRecoveryDisposition.APPLIED
    return busted


@pytest.mark.parametrize(
    "substitution",
    (
        lambda mandate: replace(
            mandate,
            position_scope=replace(mandate.position_scope, symbol_id=SymbolId("MSFT")),
        ),
        lambda mandate: replace(mandate, session_id=SessionId("other-session")),
        lambda mandate: replace(mandate, configuration_version="other-config"),
    ),
)
def test_acquisition_mandate_requires_the_complete_matching_protection_context(
    substitution,
) -> None:
    """FR-01: a BUY mandate cannot bind a protection mandate from another context."""

    module = _acquisition_module()
    protection = _protection_mandate()

    with pytest.raises(ValueError):
        _mandate(module, protection_mandate=substitution(protection))


def test_acquisition_mandate_is_exact_immutable_and_has_positive_bounded_policy() -> (
    None
):
    """FR-01/02: mandate construction is structural, immutable, and bounded."""

    module = _acquisition_module()
    (_, _, mandate_type) = _required(
        module,
        "AcquisitionMandateId",
        "AcquisitionOrderType",
        "AcquisitionMandate",
    )
    mandate = _mandate(module)

    assert type(mandate) is mandate_type
    assert mandate.protection_mandate == _protection_mandate()
    with pytest.raises(FrozenInstanceError):
        mandate.maximum_quantity = Quantity(1)
    with pytest.raises(TypeError):
        type("_Subclass", (mandate_type,), {})  # type: ignore[arg-type]

    for kwargs in (
        {"maximum_quantity": Quantity(0)},
        {"maximum_notional": Fraction(0)},
        {"allowed_order_types": ()},
    ):
        with pytest.raises((TypeError, ValueError)):
            _mandate(module, **kwargs)


def test_acquisition_mandate_identity_is_exact() -> None:
    """FR-01: a subtype cannot substitute for the immutable acquisition identity."""

    module = _acquisition_module()
    (identity_type,) = _required(module, "AcquisitionMandateId")

    with pytest.raises(TypeError):
        type("_Subclass", (identity_type,), {})  # type: ignore[arg-type]


def test_acquisition_effect_terms_are_exact_typed_and_broker_neutral() -> None:
    """FR-02/06: term inputs carry bounded policy, never an adapter command."""

    module = _acquisition_module()
    order_type, terms_type = _required(
        module,
        "AcquisitionOrderType",
        "AcquisitionEffectTerms",
    )
    terms = terms_type(  # type: ignore[operator]
        effect_id=EffectId("acquisition-effect"),
        request_occurrence_id=RequestOccurrenceId("acquisition-request"),
        client_order_id=ClientOrderId("acquisition-client"),
        quantity=Quantity(2),
        limit_price=MAXIMUM_ENTRY_PRICE,
        order_type=order_type.LIMIT,  # type: ignore[attr-defined]
        evaluation_time=50,
    )

    assert type(terms) is terms_type
    with pytest.raises(FrozenInstanceError):
        terms.quantity = Quantity(1)
    with pytest.raises(TypeError):
        type("_Subclass", (terms_type,), {})  # type: ignore[arg-type]

    with pytest.raises((TypeError, ValueError)):
        terms_type(  # type: ignore[operator]
            effect_id=EffectId("invalid-acquisition-effect"),
            request_occurrence_id=RequestOccurrenceId("invalid-acquisition-request"),
            client_order_id=ClientOrderId("invalid-acquisition-client"),
            quantity=Quantity(0),
            limit_price=MAXIMUM_ENTRY_PRICE,
            order_type=order_type.LIMIT,  # type: ignore[attr-defined]
            evaluation_time=50,
        )


def test_bound_venue_effect_retains_distinct_acquisition_and_protection_authority() -> (
    None
):
    """FR-01/03: effect scope retains typed dual authority, never hidden bytes."""

    module = _acquisition_module()
    mandate = _mandate(module)
    requested = RequestedEffect(
        input_id=VenueInputId("bound-buy-input"),
        effect_id=EffectId("bound-buy-effect"),
        request_occurrence_id=RequestOccurrenceId("bound-buy-request"),
        mandate_id=mandate.protection_mandate.mandate_id,
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("bound-buy-client"),
        symbol_id=SYMBOL,
        side=ExecutionSide.BUY,
        quantity=Quantity(2),
        economic_scope=b"commitment-only-not-policy",
        dual_mandate_binding=mandate.binding,
    )

    assert requested.mandate_id == mandate.protection_mandate.mandate_id
    assert requested.dual_mandate_binding == mandate.binding


def test_bound_venue_projection_initializes_opaque_acquisition_state() -> None:
    """FR-01/02: initialization consumes an authenticated bound venue snapshot."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    projection = venue.project_acquisition_venue(
        _initial_bound_venue_transition(mandate),
        mandate.binding,
    )
    transition = acquisition.initialize_acquisition(mandate, projection)

    disposition_type, state_type, currentness_type = _required(
        acquisition,
        "AcquisitionDisposition",
        "AcquisitionState",
        "AcquisitionCurrentness",
    )
    assert transition.disposition is disposition_type.APPLIED
    assert type(transition.state) is state_type
    assert type(transition.currentness) is currentness_type
    assert transition.authorization is None
    assert transition.exit_projection is None


def test_empty_venue_genesis_mints_only_a_zero_economic_currentness() -> None:
    """FR-03 R1: the initial sealed head needs no fabricated venue effect."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    empty = VenueRecoveryBook.empty(VENUE_SCOPE)
    flat = ExecutionSnapshot.flat(POSITION_SCOPE)

    projection = venue.project_acquisition_venue(
        empty,
        mandate.binding,
        execution=flat,
    )
    transition = acquisition.initialize_acquisition(mandate, projection)

    assert projection.owned_quantity_delta == 0
    assert projection.owned_notional_delta == Fraction(0)
    assert transition.currentness.is_authentic
    with pytest.raises((TypeError, ValueError)):
        venue.project_acquisition_venue(empty, mandate.binding)


def test_first_owned_buy_fill_arms_protection_from_the_same_transition() -> None:
    """FR-02/R2: do not pre-initialize flat protection or trust caller pairings."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    genesis = acquisition.initialize_acquisition(
        mandate,
        venue.project_acquisition_venue(
            VenueRecoveryBook.empty(VENUE_SCOPE),
            mandate.binding,
            execution=ExecutionSnapshot.flat(POSITION_SCOPE),
        ),
    )
    requested, filled = _bound_buy_fill_transitions(mandate)

    before_fill = acquisition.apply_acquisition_integration(genesis.state, requested)
    assert before_fill.protection_state is None

    projection = venue.project_acquisition_venue(filled, mandate.binding)
    assert projection.owned_quantity_delta == 2
    assert projection.owned_notional_delta == Fraction(200)

    integrated = acquisition.apply_acquisition_integration(before_fill.state, filled)
    assert integrated.protection_state is not None
    assert integrated.protection_state.raw_quantity == 2
    assert integrated.protection_state.policy is ProtectionPolicy.FLOOR_ONLY


def test_owned_correction_and_bust_replace_acquisition_economics_once() -> None:
    """FR-02/04: revisions replace one owned root without a second fill fold."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    genesis = acquisition.initialize_acquisition(
        mandate,
        venue.project_acquisition_venue(
            VenueRecoveryBook.empty(VENUE_SCOPE),
            mandate.binding,
            execution=ExecutionSnapshot.flat(POSITION_SCOPE),
        ),
    )
    requested, filled = _bound_buy_fill_transitions(mandate)
    after_request = acquisition.apply_acquisition_integration(genesis.state, requested)
    after_fill = acquisition.apply_acquisition_integration(after_request.state, filled)
    corrected = _correct_bound_buy_root(filled)
    correction = venue.project_acquisition_venue(corrected, mandate.binding)
    assert correction.owned_quantity_delta == -1
    assert correction.owned_notional_delta == Fraction(-110)

    after_correction = acquisition.apply_acquisition_integration(
        after_fill.state,
        corrected,
    )
    assert after_correction.protection_state is not None
    assert after_correction.protection_state.raw_quantity == 1

    busted = _bust_corrected_bound_buy_root(corrected)
    bust = venue.project_acquisition_venue(busted, mandate.binding)
    assert bust.owned_quantity_delta == -1
    assert bust.owned_notional_delta == Fraction(-90)

    after_bust = acquisition.apply_acquisition_integration(
        after_correction.state,
        busted,
    )
    assert after_bust.protection_state is not None
    assert after_bust.protection_state.raw_quantity == 0
    assert after_bust.protection_state.policy is ProtectionPolicy.HARD_BAIL


def test_market_reduction_requires_the_exact_current_venue_transition() -> None:
    """R3/FR-05: M1D market state advances only from the sealed current venue head."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    genesis = acquisition.initialize_acquisition(
        mandate,
        venue.project_acquisition_venue(
            VenueRecoveryBook.empty(VENUE_SCOPE),
            mandate.binding,
            execution=ExecutionSnapshot.flat(POSITION_SCOPE),
        ),
    )
    requested, filled = _bound_buy_fill_transitions(mandate)
    after_request = acquisition.apply_acquisition_integration(genesis.state, requested)
    after_fill = acquisition.apply_acquisition_integration(after_request.state, filled)

    baseline = acquisition.reduce_acquisition_market(
        after_fill.state,
        filled,
        _market_occurrence(
            label="acquisition-market-baseline",
            bid=100,
            ask=101,
            sequence=1,
            source_time=1,
        ),
    )
    (disposition_type,) = _required(acquisition, "AcquisitionDisposition")
    assert baseline.disposition is disposition_type.APPLIED
    assert baseline.protection_state is not None
    assert baseline.protection_alert is None
    assert baseline.exit_projection is None
    assert baseline.currentness.head != after_fill.currentness.head

    mismatched = acquisition.reduce_acquisition_market(
        baseline.state,
        requested,
        _market_occurrence(
            label="acquisition-market-mismatched-transition",
            bid=99,
            ask=100,
            sequence=2,
            source_time=2,
        ),
    )
    assert mismatched.disposition is disposition_type.REFUSED
    assert mismatched.state == baseline.state


def test_waiting_protection_exit_mints_preemption_before_a_sell_goal_exists() -> None:
    """FR-05: a live BUY cannot suppress the exit capability needed to cancel itself."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    genesis = acquisition.initialize_acquisition(
        mandate,
        venue.project_acquisition_venue(
            VenueRecoveryBook.empty(VENUE_SCOPE),
            mandate.binding,
            execution=ExecutionSnapshot.flat(POSITION_SCOPE),
        ),
    )
    requested, filled = _bound_buy_fill_transitions(mandate)
    after_request = acquisition.apply_acquisition_integration(genesis.state, requested)
    after_fill = acquisition.apply_acquisition_integration(after_request.state, filled)
    baseline = acquisition.reduce_acquisition_market(
        after_fill.state,
        filled,
        _market_occurrence(
            label="acquisition-wait-baseline",
            bid=100,
            ask=101,
            sequence=1,
            source_time=1,
        ),
    )
    armed = acquisition.reduce_acquisition_market(
        baseline.state,
        filled,
        _market_occurrence(
            label="acquisition-wait-first-low",
            bid=92,
            ask=93,
            sequence=2,
            source_time=2,
        ),
    )
    waiting_exit = acquisition.reduce_acquisition_market(
        armed.state,
        filled,
        _market_occurrence(
            label="acquisition-wait-second-low",
            bid=91,
            ask=92,
            sequence=3,
            source_time=3,
        ),
    )

    assert waiting_exit.protection_state is not None
    assert waiting_exit.protection_state.policy is ProtectionPolicy.HARD_BAIL
    assert waiting_exit.protection_state.waiting_buy_resolution is True
    assert waiting_exit.exit_projection is not None
    assert waiting_exit.exit_projection.is_authentic


def test_market_reduction_refuses_a_rejected_venue_carrier() -> None:
    """R3: a rejected venue input cannot authorize an otherwise current market step."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    genesis = acquisition.initialize_acquisition(
        mandate,
        venue.project_acquisition_venue(
            VenueRecoveryBook.empty(VENUE_SCOPE),
            mandate.binding,
            execution=ExecutionSnapshot.flat(POSITION_SCOPE),
        ),
    )
    requested, filled = _bound_buy_fill_transitions(mandate)
    after_request = acquisition.apply_acquisition_integration(genesis.state, requested)
    after_fill = acquisition.apply_acquisition_integration(after_request.state, filled)
    rejected = _apply_venue_input(
        filled.book,
        filled.execution,
        RecordTransportOutcome(
            input_id=VenueInputId("acquisition-rejected-market-carrier"),
            effect_id=EffectId("missing-acquisition-effect"),
            state=BrokerEffectState.ACKNOWLEDGED,
        ),
    )
    assert rejected.disposition is VenueRecoveryDisposition.REFUSED

    result = acquisition.reduce_acquisition_market(
        after_fill.state,
        rejected,
        _market_occurrence(
            label="acquisition-rejected-carrier-market",
            bid=100,
            ask=101,
            sequence=1,
            source_time=1,
        ),
    )
    (disposition_type,) = _required(acquisition, "AcquisitionDisposition")
    assert result.disposition is disposition_type.REFUSED
    assert result.state == after_fill.state


def test_market_reduction_leaves_wrong_route_validation_to_m1d() -> None:
    """R3/ADR-023: an invalid market route is a state-preserving refusal, not a duplicate rule."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    genesis = acquisition.initialize_acquisition(
        mandate,
        venue.project_acquisition_venue(
            VenueRecoveryBook.empty(VENUE_SCOPE),
            mandate.binding,
            execution=ExecutionSnapshot.flat(POSITION_SCOPE),
        ),
    )
    requested, filled = _bound_buy_fill_transitions(mandate)
    after_request = acquisition.apply_acquisition_integration(genesis.state, requested)
    after_fill = acquisition.apply_acquisition_integration(after_request.state, filled)

    result = acquisition.reduce_acquisition_market(
        after_fill.state,
        filled,
        _market_occurrence(
            label="acquisition-wrong-market-scope",
            bid=100,
            ask=101,
            sequence=1,
            source_time=1,
            position_scope=replace(
                POSITION_SCOPE,
                symbol_id=SymbolId("MSFT"),
            ),
        ),
    )
    (disposition_type,) = _required(acquisition, "AcquisitionDisposition")
    assert result.disposition is disposition_type.REFUSED
    assert result.state == after_fill.state


def test_current_leg_preemption_projection_derives_one_bound_buy_cancel() -> None:
    """FR-03/05: one sealed current-leg projection yields one target-derived cancel."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    _, filled = _bound_buy_fill_transitions(mandate)
    projector, builder = _required(
        venue,
        "project_next_buy_preemption",
        "build_acquisition_cancel_request",
    )
    head = VenueLegKey(
        broker=BrokerId(BROKER),
        environment=EnvironmentId(ENVIRONMENT),
        account=ACCOUNT,
        order_id=OrderId("initial-bound-buy-order"),
    )

    projection = projector(  # type: ignore[operator]
        filled.book,
        filled.execution,
        EffectId("initial-bound-buy-effect"),
        mandate.binding,
    )
    assert projection.is_authentic
    assert projection.can_cancel
    assert projection.head_active_leg_key == head
    request = builder(  # type: ignore[operator]
        projection,
        VenueInputId("acquisition-preemption-cancel-input"),
        EffectId("acquisition-preemption-cancel-effect"),
        RequestOccurrenceId("acquisition-preemption-cancel-occurrence"),
    )
    assert request is not None
    assert request.kind is EffectKind.CANCEL
    assert request.side is ExecutionSide.BUY
    assert request.target_leg_key == head
    assert request.dual_mandate_binding == mandate.binding


def test_buy_preemption_moves_from_a_closed_head_to_its_next_direct_leg() -> None:
    """FR-05: terminalizing one BUY leg advances the bounded active-leg FIFO."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    _, filled = _bound_buy_fill_transitions(mandate)
    projector, _ = _required(
        venue,
        "project_next_buy_preemption",
        "build_acquisition_cancel_request",
    )
    effect_id = EffectId("initial-bound-buy-effect")
    first = VenueLegKey(
        broker=BrokerId(BROKER),
        environment=EnvironmentId(ENVIRONMENT),
        account=ACCOUNT,
        order_id=OrderId("initial-bound-buy-order"),
    )
    second = VenueLegKey(
        broker=BrokerId(BROKER),
        environment=EnvironmentId(ENVIRONMENT),
        account=ACCOUNT,
        order_id=OrderId("initial-bound-buy-second-order"),
    )

    second_discovered = _apply_venue_input(
        filled.book,
        filled.execution,
        DiscoverVenueLeg(
            input_id=VenueInputId("initial-bound-buy-second-discover-input"),
            effect_id=effect_id,
            leg_key=second,
            observation_id=VenueObservationId("initial-bound-buy-second-discovery"),
        ),
    )
    assert second_discovered.disposition is VenueRecoveryDisposition.APPLIED
    before_close = projector(  # type: ignore[operator]
        second_discovered.book,
        second_discovered.execution,
        effect_id,
        mandate.binding,
    )
    assert before_close.head_active_leg_key == first

    first_closed = _apply_venue_input(
        second_discovered.book,
        second_discovered.execution,
        ObserveVenueStatus(
            input_id=VenueInputId("initial-bound-buy-first-close-input"),
            leg_key=first,
            status=venue.VenueAttemptState.CANCELED,
            observation_id=VenueObservationId(
                "initial-bound-buy-first-close-observation"
            ),
            cumulative_quantity=Quantity(2),
            closure_id=ClosureId("initial-bound-buy-first-close"),
            evidence_reference=EvidenceReference("initial-bound-buy-first-evidence"),
        ),
    )
    assert first_closed.disposition is VenueRecoveryDisposition.APPLIED
    after_close = projector(  # type: ignore[operator]
        first_closed.book,
        first_closed.execution,
        effect_id,
        mandate.binding,
    )
    assert after_close.is_authentic
    assert after_close.can_cancel
    assert after_close.head_active_leg_key == second


def test_buy_preemption_waits_for_the_current_pending_head_without_skipping() -> None:
    """FR-05: a later BUY leg cannot bypass the unresolved current head."""

    acquisition = _acquisition_module()
    venue = importlib.import_module("app.execution_core.venue")
    mandate = _mandate(acquisition)
    _, filled = _bound_buy_fill_transitions(mandate)
    (projector,) = _required(venue, "project_next_buy_preemption")
    effect_id = EffectId("initial-bound-buy-effect")
    first = VenueLegKey(
        broker=BrokerId(BROKER),
        environment=EnvironmentId(ENVIRONMENT),
        account=ACCOUNT,
        order_id=OrderId("initial-bound-buy-order"),
    )
    second = VenueLegKey(
        broker=BrokerId(BROKER),
        environment=EnvironmentId(ENVIRONMENT),
        account=ACCOUNT,
        order_id=OrderId("initial-bound-buy-second-pending-order"),
    )
    second_discovered = _apply_venue_input(
        filled.book,
        filled.execution,
        DiscoverVenueLeg(
            input_id=VenueInputId("initial-bound-buy-second-pending-discover-input"),
            effect_id=effect_id,
            leg_key=second,
            observation_id=VenueObservationId(
                "initial-bound-buy-second-pending-discovery"
            ),
        ),
    )
    pending = _apply_venue_input(
        second_discovered.book,
        second_discovered.execution,
        RecordPendingVenueOperation(
            input_id=VenueInputId("initial-bound-buy-first-pending-input"),
            leg_key=first,
            operation=PendingVenueOperation.CANCEL,
        ),
    )
    assert pending.disposition is VenueRecoveryDisposition.APPLIED

    projection = projector(  # type: ignore[operator]
        pending.book,
        pending.execution,
        effect_id,
        mandate.binding,
    )
    assert projection.is_authentic
    assert not projection.can_cancel
    assert projection.head_active_leg_key is None


def test_public_preemption_projector_uses_no_audit_history_traversal() -> None:
    """FR-05/06: the hot path remains one direct-index decision, not a history scan."""

    venue = importlib.import_module("app.execution_core.venue")
    source = textwrap.dedent(inspect.getsource(venue.project_next_buy_preemption))
    tree = ast.parse(source)
    forbidden_nodes = (
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )
    assert not [node for node in ast.walk(tree) if isinstance(node, forbidden_nodes)]
    accessed = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not accessed & {
        "active_attempts",
        "claims",
        "effects",
        "input_records",
        "owners",
        "terminal_closures",
    }
