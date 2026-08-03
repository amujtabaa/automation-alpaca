"""RED-first contracts for the pure WO-0148 protection semantic center.

The suite uses only explicit immutable values and the genuine venue-recovery
reducer.  It imports the not-yet-implemented protection vocabulary lazily so
every example is collected and independently failure-capable before production
code exists.  No clock, database, broker, adapter, or runtime fixture is used.
"""

from __future__ import annotations

import ast
from copy import copy
from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal
from fractions import Fraction
import importlib
import inspect
from types import ModuleType

import pytest

import app.execution_core as execution_core
from app.execution_core.authority import (
    AuthorityDisposition,
    AuthorityReason,
    BrokerEffectRequest,
    ClaimEffect,
    CreateBrokerEffect,
    EnginePhase,
    RequestBudget,
    SupervisorFence,
    TradingMode,
    apply_execution_authority_input,
    initial_execution_authority_state,
)
from app.execution_core.fills import (
    BrokerTradeBustFact,
    BrokerTradeCorrectFact,
    ExecutionFactKey,
    ExecutionScope,
    ExecutionSide,
    PositionScope,
)
from app.execution_core.position import (
    ExecutionSnapshot,
    TransitionDisposition,
    apply_broker_execution_fact,
)
from app.execution_core.identity import (
    ClaimOccurrenceId,
    ClientOrderId,
    ClosureId,
    EffectId,
    EvidenceReference,
    MandateId,
    OrderId,
    RequestOccurrenceId,
    RootFillId,
    SourceEventId,
    VenueInputId,
    VenueLegKey,
    VenueObservationId,
)
from app.execution_core.recovery import (
    RecordBrokerFillEvidence,
    RecordBrokerRevisionEvidence,
    ReleaseVenueLeg,
)
from app.execution_core.values import (
    PriceScale,
    PriceUnits,
    Quantity,
    ReportedPrice,
    TickMetadata,
)
from app.execution_core.venue import (
    AcceptanceProof,
    AcceptanceProofKind,
    AcceptanceSetState,
    BrokerEffectState,
    CatchUpExecutionRegistry,
    CloseAcceptanceSet,
    DiscoverVenueLeg,
    EffectKind,
    ObserveVenueStatus,
    RecordDispatchClaim,
    RecordTransportOutcome,
    RequestedEffect,
    VenueAttemptState,
    VenueRecoveryBook,
    VenueRecoveryDisposition,
    VenueExecutionCheckpoint,
)
from tests.execution_core import test_venue_recovery as venue_fixtures


BROKER = venue_fixtures.BROKER
ENVIRONMENT = venue_fixtures.ENVIRONMENT
ACCOUNT = venue_fixtures.ACCOUNT
GENERATION = venue_fixtures.GENERATION
SYMBOL = venue_fixtures.SYMBOL
POSITION_SCOPE = venue_fixtures.POSITION_SCOPE
VENUE_SCOPE = venue_fixtures.VENUE_SCOPE
MANDATE_ID = venue_fixtures.MANDATE
BASE_EFFECT = venue_fixtures.EFFECT
BASE_LEG = venue_fixtures.LEG_A
BASE_CLAIM = venue_fixtures.CLAIM
SCALE = PriceScale(Decimal("1"))
TICK = TickMetadata(tick_units=PriceUnits(1), scale=SCALE)


def _price(units: int, *, tick_units: int = 1) -> ReportedPrice:
    tick = TickMetadata(tick_units=PriceUnits(tick_units), scale=SCALE)
    return ReportedPrice(units=PriceUnits(units), scale=SCALE, tick=tick)


def _protection_module() -> ModuleType:
    try:
        return importlib.import_module("app.execution_core.protection")
    except ModuleNotFoundError as exc:
        pytest.fail(f"WO-0148 protection module is not implemented: {exc}")


def _required(container: object, *names: str) -> tuple[object, ...]:
    missing = tuple(name for name in names if not hasattr(container, name))
    assert not missing, f"missing WO-0148 protection API: {missing!r}"
    return tuple(getattr(container, name) for name in names)


def _guard(module: ModuleType, label: str) -> object:
    (guard_type,) = _required(module, "ExecutionGuard")
    return guard_type(guard_id=label, policy_commitment=label.encode().ljust(32, b"!"))


def _mandate(
    module: ModuleType,
    *,
    mandate_id: MandateId = MANDATE_ID,
    position_scope: PositionScope = POSITION_SCOPE,
    loss_fraction: Fraction = Fraction(3, 40),
    approved_gain: Fraction = Fraction(3, 40),
    percent_trail_fraction: Fraction = Fraction(2, 25),
    atr_multiple: Fraction = Fraction(5, 2),
    tick: TickMetadata = TICK,
    max_age: int = 10,
    corroboration_window: int = 10,
    max_step_fraction: Fraction = Fraction(1, 2),
    maximum_quantity: int = 20,
    maximum_goal_rate: int = 4,
    deadline: int = 1_000,
    configuration_version: str = "protection-v1",
    normal_guard: object | None = None,
    emergency_guard: object | None = None,
) -> object:
    evidence_type, mandate_type = _required(
        module,
        "EvidencePolicy",
        "ProtectionMandate",
    )
    (source_type,) = _required(execution_core, "MarketDataSourceId")
    (session_type,) = _required(execution_core, "SessionId")
    evidence = evidence_type(
        source_id=source_type("sip-primary"),
        max_age=max_age,
        corroboration_window=corroboration_window,
        max_step_fraction=max_step_fraction,
    )
    return mandate_type(
        mandate_id=mandate_id,
        position_scope=position_scope,
        session_id=session_type("session-rth-1"),
        configuration_version=configuration_version,
        loss_fraction=loss_fraction,
        approved_gain=approved_gain,
        percent_trail_fraction=percent_trail_fraction,
        atr_multiple=atr_multiple,
        tick=tick,
        normal_guard=normal_guard or _guard(module, "normal-guard"),
        emergency_guard=emergency_guard or _guard(module, "emergency-guard"),
        evidence_policy=evidence,
        maximum_quantity=Quantity(maximum_quantity),
        maximum_goal_rate=maximum_goal_rate,
        deadline=deadline,
    )


def _owned_fill_fixture(
    *,
    label: str = "protection-first",
    quantity: int = 4,
    units: int = 100,
    capacity: int = 20,
    tick_units: int = 1,
):
    book, execution = venue_fixtures._seed_needs_review(capacity=capacity)
    fact = venue_fixtures._broker_fill(
        f"{label}-source",
        f"{label}-root",
        quantity=quantity,
        units=units,
    )
    if tick_units != 1:
        fact = replace(fact, price=_price(units, tick_units=tick_units))
    command = RecordBrokerFillEvidence(
        input_id=VenueInputId(f"{label}-input"),
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        prior_cumulative_quantity=Quantity(0),
        resulting_cumulative_quantity=Quantity(quantity),
        fact=fact,
        evidence_digest=b"\x91" * 32,
    )
    transition = venue_fixtures.apply_venue_recovery_input(
        book,
        execution,
        command,
    )
    assert transition.disposition is VenueRecoveryDisposition.APPLIED
    assert transition.quantity_delta == quantity
    return book, execution, command, transition


def _owned_fill_transition(
    *,
    label: str = "protection-first",
    quantity: int = 4,
    units: int = 100,
    capacity: int = 20,
    tick_units: int = 1,
):
    return _owned_fill_fixture(
        label=label,
        quantity=quantity,
        units=units,
        capacity=capacity,
        tick_units=tick_units,
    )[-1]


def _advance_owned_fill(
    transition: object,
    *,
    label: str,
    quantity: int,
    units: int,
    prior_cumulative: int,
):
    fact = venue_fixtures._broker_fill(
        f"{label}-source",
        f"{label}-root",
        quantity=quantity,
        units=units,
    )
    result = venue_fixtures.apply_venue_recovery_input(
        transition.book,
        transition.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(f"{label}-input"),
            effect_id=BASE_EFFECT,
            leg_key=BASE_LEG,
            prior_cumulative_quantity=Quantity(prior_cumulative),
            resulting_cumulative_quantity=Quantity(prior_cumulative + quantity),
            fact=fact,
            evidence_digest=b"\x92" * 32,
        ),
    )
    assert result.disposition is VenueRecoveryDisposition.APPLIED
    return result


def _correct_owned_root(
    transition: object,
    *,
    label: str,
    root_fill_id: RootFillId,
    predecessor_source_event_id: SourceEventId,
    prior_root_quantity: int,
    resulting_quantity: int,
    units: int,
    prior_venue_cumulative: int,
    tick_units: int = 1,
    effect_id: EffectId = BASE_EFFECT,
    leg_key: VenueLegKey = BASE_LEG,
    scope: ExecutionScope | None = None,
    closure_id: ClosureId | None = None,
    evidence_reference: EvidenceReference | None = None,
):
    fact = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(f"{label}-source"),
        ),
        scope=scope if scope is not None else venue_fixtures._execution_scope(),
        root_fill_id=root_fill_id,
        predecessor_source_event_id=predecessor_source_event_id,
        revised_quantity=Quantity(resulting_quantity),
        revised_price=_price(units, tick_units=tick_units),
    )
    command = RecordBrokerRevisionEvidence(
        input_id=VenueInputId(f"{label}-input"),
        effect_id=effect_id,
        leg_key=leg_key,
        prior_root_quantity=Quantity(prior_root_quantity),
        prior_venue_cumulative_quantity=Quantity(prior_venue_cumulative),
        resulting_venue_cumulative_quantity=Quantity(resulting_quantity),
        fact=fact,
        evidence_digest=b"\x97" * 32,
        closure_id=closure_id,
        evidence_reference=evidence_reference,
    )
    result = venue_fixtures.apply_venue_recovery_input(
        transition.book,
        transition.execution,
        command,
    )
    assert result.disposition is VenueRecoveryDisposition.APPLIED
    return command, result


def _bust_owned_root(
    transition: object,
    *,
    label: str,
    root_fill_id: RootFillId,
    predecessor_source_event_id: SourceEventId,
    prior_root_quantity: int,
    prior_venue_cumulative: int,
    effect_id: EffectId = BASE_EFFECT,
    leg_key: VenueLegKey = BASE_LEG,
    scope: ExecutionScope | None = None,
    closure_id: ClosureId | None = None,
    evidence_reference: EvidenceReference | None = None,
):
    fact = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(f"{label}-source"),
        ),
        scope=scope if scope is not None else venue_fixtures._execution_scope(),
        root_fill_id=root_fill_id,
        predecessor_source_event_id=predecessor_source_event_id,
    )
    command = RecordBrokerRevisionEvidence(
        input_id=VenueInputId(f"{label}-input"),
        effect_id=effect_id,
        leg_key=leg_key,
        prior_root_quantity=Quantity(prior_root_quantity),
        prior_venue_cumulative_quantity=Quantity(prior_venue_cumulative),
        resulting_venue_cumulative_quantity=Quantity(0),
        fact=fact,
        evidence_digest=b"\x98" * 32,
        closure_id=closure_id,
        evidence_reference=evidence_reference,
    )
    result = venue_fixtures.apply_venue_recovery_input(
        transition.book,
        transition.execution,
        command,
    )
    assert result.disposition is VenueRecoveryDisposition.APPLIED
    return command, result


def _projection(
    module: ModuleType, venue_transition: object, mandate: object
) -> object:
    (project,) = _required(module, "project_protection_venue")
    return project(venue_transition, mandate)


def _start(
    module: ModuleType,
    venue_transition: object,
    mandate: object | None = None,
) -> tuple[object, object, object]:
    current_mandate = mandate or _mandate(module)
    projection = _projection(module, venue_transition, current_mandate)
    (initialize,) = _required(module, "initialize_position_protection")
    state = initialize(current_mandate, projection)
    return current_mandate, projection, state


def _reduce(
    module: ModuleType,
    state: object,
    projection: object,
    occurrence: object | None = None,
) -> object:
    (reducer,) = _required(module, "reduce_position_protection")
    before = (state, projection, occurrence)
    first = reducer(state, projection, occurrence)
    second = reducer(state, projection, occurrence)
    assert first == second
    assert before == (state, projection, occurrence)
    return first


def _occurrence(
    module: ModuleType,
    label: str,
    *,
    kind: str = "BEST_BID",
    bid: int | None = None,
    ask: int | None = None,
    trade: int | None = None,
    sequence: int | None = 1,
    source_time: int = 100,
    evaluation_time: int = 105,
    market_epoch: int = 0,
    atr_distance: int | None = None,
    structure_trail: int | None = None,
    halted: bool = False,
    source_id: object | None = None,
    position_scope: PositionScope = POSITION_SCOPE,
    session_id: object | None = None,
) -> object:
    market_kind, occurrence_type = _required(module, "MarketKind", "MarketOccurrence")
    occurrence_id_type, source_id_type, session_type = _required(
        execution_core,
        "MarketOccurrenceId",
        "MarketDataSourceId",
        "SessionId",
    )
    return occurrence_type(
        occurrence_id=occurrence_id_type(label),
        source_id=source_id or source_id_type("sip-primary"),
        position_scope=position_scope,
        session_id=session_id or session_type("session-rth-1"),
        market_epoch=market_epoch,
        source_sequence=sequence,
        source_time=source_time,
        evaluation_time=evaluation_time,
        kind=getattr(market_kind, kind),
        best_bid=None if bid is None else _price(bid),
        best_ask=None if ask is None else _price(ask),
        trade_price=None if trade is None else _price(trade),
        atr_distance=(None if atr_distance is None else _price(atr_distance)),
        structure_trail=(None if structure_trail is None else _price(structure_trail)),
        halted=halted,
    )


def _terminal_fixture(
    transition: object,
    *,
    effect_id: EffectId,
    leg_key: VenueLegKey,
    label: str,
    cumulative_quantity: int,
) -> tuple[object, object]:
    command = ObserveVenueStatus(
        input_id=VenueInputId(f"{label}-terminal-input"),
        leg_key=leg_key,
        status=VenueAttemptState.FILLED,
        observation_id=VenueObservationId(f"{label}-terminal-observation"),
        cumulative_quantity=Quantity(cumulative_quantity),
        closure_id=ClosureId(f"{label}-terminal-closure"),
        evidence_reference=EvidenceReference(f"{label}-terminal-evidence"),
    )
    terminal = venue_fixtures.apply_venue_recovery_input(
        transition.book,
        transition.execution,
        command,
    )
    assert terminal.disposition is VenueRecoveryDisposition.APPLIED
    assert terminal.book.effect(effect_id) is not None
    return command, terminal


def _close_parent_fixture(
    transition: object,
    *,
    effect_id: EffectId,
    label: str,
) -> tuple[object, object]:
    effect = transition.book.effect(effect_id)
    assert effect is not None
    proof = AcceptanceProof(
        kind=AcceptanceProofKind.CONTRACT_COMPLETE_RESPONSE,
        effect_scope=effect.scope,
        claim_occurrence_id=effect.claim_occurrence_id,
        evidence_reference=EvidenceReference(f"{label}-parent-evidence"),
        evidence_digest=b"\x93" * 32,
    )
    command = CloseAcceptanceSet(
        input_id=VenueInputId(f"{label}-parent-close"),
        effect_id=effect_id,
        proof=proof,
    )
    closed = venue_fixtures.apply_venue_recovery_input(
        transition.book,
        transition.execution,
        command,
    )
    assert closed.disposition is VenueRecoveryDisposition.APPLIED
    assert (
        closed.book.effect(effect_id).acceptance_set_state is AcceptanceSetState.CLOSED
    )
    return command, closed


def _close_base_parent(transition: object) -> tuple[object, object]:
    _, terminal = _terminal_fixture(
        transition,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-base",
        cumulative_quantity=transition.execution.position.raw_quantity,
    )
    _, closed = _close_parent_fixture(
        terminal,
        effect_id=BASE_EFFECT,
        label="protection-base",
    )
    return terminal, closed


def _append_needs_review_effect(
    transition: object,
    *,
    prefix: str,
    side: ExecutionSide,
    quantity: int,
) -> tuple[tuple[object, ...], EffectId, VenueLegKey, ClaimOccurrenceId]:
    effect_id = EffectId(f"{prefix}-effect")
    request_id = RequestOccurrenceId(f"{prefix}-request")
    claim_id = ClaimOccurrenceId(f"{prefix}-claim")
    leg_key = VenueLegKey(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        order_id=OrderId(f"{prefix}-leg"),
    )
    commands = (
        RequestedEffect(
            input_id=VenueInputId(f"{prefix}-request-input"),
            effect_id=effect_id,
            request_occurrence_id=request_id,
            mandate_id=MANDATE_ID,
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId(f"{prefix}-client"),
            symbol_id=SYMBOL,
            side=side,
            quantity=Quantity(quantity),
            economic_scope=f"{prefix}|fixed-capacity".encode(),
        ),
        RecordDispatchClaim(
            input_id=VenueInputId(f"{prefix}-claim-input"),
            effect_id=effect_id,
            claim_occurrence_id=claim_id,
        ),
        RecordTransportOutcome(
            input_id=VenueInputId(f"{prefix}-unknown-input"),
            effect_id=effect_id,
            state=BrokerEffectState.OUTCOME_UNKNOWN,
        ),
        DiscoverVenueLeg(
            input_id=VenueInputId(f"{prefix}-discover-input"),
            effect_id=effect_id,
            leg_key=leg_key,
            observation_id=VenueObservationId(f"{prefix}-discover-observation"),
        ),
        ObserveVenueStatus(
            input_id=VenueInputId(f"{prefix}-review-input"),
            leg_key=leg_key,
            status=VenueAttemptState.NEEDS_REVIEW,
            observation_id=VenueObservationId(f"{prefix}-review-observation"),
            cumulative_quantity=Quantity(0),
        ),
        RecordTransportOutcome(
            input_id=VenueInputId(f"{prefix}-review-outcome-input"),
            effect_id=effect_id,
            state=BrokerEffectState.NEEDS_REVIEW,
        ),
    )
    current = transition
    transitions: list[object] = []
    for command in commands:
        current = venue_fixtures.apply_venue_recovery_input(
            current.book,
            current.execution,
            command,
        )
        assert current.disposition is VenueRecoveryDisposition.APPLIED
        transitions.append(current)
    return tuple(transitions), effect_id, leg_key, claim_id


def _clone_opaque(value: object, **overrides: object) -> object:
    clone = object.__new__(type(value))
    for retained in fields(value):
        object.__setattr__(
            clone,
            retained.name,
            overrides.get(retained.name, getattr(value, retained.name)),
        )
    return clone


def _flip_digest(value: bytes) -> bytes:
    return bytes((value[0] ^ 1,)) + value[1:]


def _assert_stale_unchanged(
    module: ModuleType,
    state: object,
    projection: object,
) -> None:
    result = _reduce(module, state, projection)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert result.disposition is disposition.STALE
    assert result.state == state
    assert result.goal is None
    assert result.critical_alert is None


def _sync_transitions(
    module: ModuleType,
    state: object,
    mandate: object,
    transitions: tuple[object, ...],
) -> tuple[object, object, object]:
    result = None
    projection = None
    for transition in transitions:
        projection = _projection(module, transition, mandate)
        result = _reduce(module, state, projection)
        state = result.state
    assert result is not None and projection is not None
    return state, projection, result


def _emergency_goal_fixture(
    module: ModuleType,
    *,
    label: str,
    mandate: object | None = None,
) -> tuple[object, object, object, object]:
    fill = _owned_fill_transition(label=f"{label}-fill")
    current_mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(
        module,
        state,
        current_mandate,
        (terminal, closed),
    )
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(module, f"{label}-first", bid=92, ask=93, sequence=1),
    )
    result = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            f"{label}-second",
            bid=91,
            ask=92,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    assert result.goal is not None
    return current_mandate, closed, result.state, result.goal


def _forge_authority_predecessor(
    venue: VenueRecoveryBook,
    *,
    session_id: object,
    kill_engaged: bool = False,
    fence: SupervisorFence = SupervisorFence.PAPER_MUTATION_ELIGIBLE,
) -> object:
    state = copy(initial_execution_authority_state(VENUE_SCOPE))
    object.__setattr__(state, "phase", EnginePhase.SERVING)
    object.__setattr__(state, "mode", TradingMode.ACTIVE)
    object.__setattr__(state, "supervisor_fence", fence)
    object.__setattr__(state, "kill_engaged", kill_engaged)
    object.__setattr__(state, "session_id", session_id)
    object.__setattr__(state, "budget", RequestBudget(remaining=3, safety_reserve=1))
    object.__setattr__(state, "venue", venue)
    return state


def test_public_protection_contract_is_exported_and_has_one_reducer() -> None:
    module = _protection_module()
    names = {
        "EvidencePolicy",
        "ExecutionGoal",
        "ExecutionGuard",
        "MarketKind",
        "MarketOccurrence",
        "PositionProtectionState",
        "ProtectionAlert",
        "ProtectionDisposition",
        "ProtectionMandate",
        "ProtectionPolicy",
        "ProtectionTransition",
        "ProtectionUrgency",
        "ProtectionVenueProjection",
        "initialize_position_protection",
        "project_protection_venue",
        "reduce_position_protection",
    }
    _required(module, *sorted(names))
    assert set(module.__all__) == names
    _required(
        execution_core, *sorted(names), "MarketDataSourceId", "MarketOccurrenceId"
    )
    assert {
        name
        for name in dir(module)
        if name.startswith(("create_", "claim_", "dispatch_", "grant_", "submit_"))
    } == set()


def test_mandate_is_frozen_exact_and_rejects_subclasses() -> None:
    module = _protection_module()
    mandate = _mandate(module)
    with pytest.raises(FrozenInstanceError):
        mandate.deadline = 2_000
    with pytest.raises(TypeError):
        _mandate(module, loss_fraction=0.1)  # type: ignore[arg-type]
    mandate_type = type(mandate)
    with pytest.raises(TypeError):
        type("ForgedMandate", (mandate_type,), {})


@pytest.mark.parametrize(
    ("override", "value", "error"),
    [
        ("loss_fraction", Fraction(0), ValueError),
        ("loss_fraction", Fraction(-1), ValueError),
        ("loss_fraction", Fraction(1), ValueError),
        ("approved_gain", Fraction(0), ValueError),
        ("approved_gain", Fraction(-1), ValueError),
        ("percent_trail_fraction", Fraction(0), ValueError),
        ("percent_trail_fraction", Fraction(-1), ValueError),
        ("percent_trail_fraction", Fraction(1), ValueError),
        ("atr_multiple", Fraction(0), ValueError),
        ("atr_multiple", Fraction(-1), ValueError),
        ("max_step_fraction", Fraction(0), ValueError),
        ("max_step_fraction", Fraction(-1), ValueError),
        ("max_step_fraction", Fraction(2), ValueError),
        ("maximum_quantity", 0, ValueError),
        ("maximum_goal_rate", 0, ValueError),
        ("max_age", 0, ValueError),
        ("corroboration_window", 0, ValueError),
    ],
)
def test_mandate_rejects_invalid_formula_evidence_quantity_and_rate(
    override: str,
    value: object,
    error: type[Exception],
) -> None:
    module = _protection_module()
    with pytest.raises(error):
        _mandate(module, **{override: value})


@pytest.mark.parametrize(
    ("field_name", "value", "error"),
    [
        ("mandate_id", "mandate", TypeError),
        ("position_scope", "scope", TypeError),
        ("session_id", "session", TypeError),
        ("configuration_version", "   ", ValueError),
        ("configuration_version", 1, TypeError),
        ("loss_fraction", True, TypeError),
        ("approved_gain", 1, TypeError),
        ("percent_trail_fraction", Decimal("0.1"), TypeError),
        ("atr_multiple", 2.5, TypeError),
        ("tick", object(), TypeError),
        ("normal_guard", object(), TypeError),
        ("emergency_guard", object(), TypeError),
        ("evidence_policy", object(), TypeError),
        ("maximum_quantity", 1, TypeError),
        ("maximum_goal_rate", True, TypeError),
        ("maximum_goal_rate", -1, ValueError),
        ("deadline", True, TypeError),
        ("deadline", -1, ValueError),
    ],
)
def test_mandate_rejects_every_malformed_authority_field(
    field_name: str,
    value: object,
    error: type[Exception],
) -> None:
    module = _protection_module()
    with pytest.raises(error):
        replace(_mandate(module), **{field_name: value})


@pytest.mark.parametrize(
    ("field_name", "value", "error"),
    [
        ("source_id", "feed", TypeError),
        ("max_age", True, TypeError),
        ("max_age", -1, ValueError),
        ("corroboration_window", True, TypeError),
        ("corroboration_window", 0, ValueError),
        ("max_step_fraction", True, TypeError),
        ("max_step_fraction", Fraction(0), ValueError),
        ("max_step_fraction", Fraction(2), ValueError),
    ],
)
def test_evidence_policy_rejects_malformed_fields(
    field_name: str,
    value: object,
    error: type[Exception],
) -> None:
    module = _protection_module()
    evidence = _mandate(module).evidence_policy
    with pytest.raises(error):
        replace(evidence, **{field_name: value})


@pytest.mark.parametrize(
    ("guard_id", "commitment", "error"),
    [
        ("   ", b"x" * 32, ValueError),
        (1, b"x" * 32, TypeError),
        ("guard", "not-bytes", TypeError),
        ("guard", b"x" * 31, ValueError),
        ("guard", b"x" * 33, ValueError),
    ],
)
def test_execution_guard_requires_nonblank_identity_and_exact_commitment(
    guard_id: object,
    commitment: object,
    error: type[Exception],
) -> None:
    module = _protection_module()
    (guard_type,) = _required(module, "ExecutionGuard")
    with pytest.raises(error):
        guard_type(guard_id=guard_id, policy_commitment=commitment)


@pytest.mark.parametrize(
    ("field_name", "value", "error"),
    [
        ("occurrence_id", "occurrence", TypeError),
        ("source_id", "source", TypeError),
        ("position_scope", "scope", TypeError),
        ("session_id", "session", TypeError),
        ("market_epoch", True, TypeError),
        ("market_epoch", -1, ValueError),
        ("source_sequence", True, TypeError),
        ("source_sequence", -1, ValueError),
        ("source_time", True, TypeError),
        ("source_time", -1, ValueError),
        ("evaluation_time", True, TypeError),
        ("evaluation_time", -1, ValueError),
        ("kind", "BEST_BID", TypeError),
        ("best_bid", object(), TypeError),
        ("best_ask", object(), TypeError),
        ("trade_price", object(), TypeError),
        ("atr_distance", object(), TypeError),
        ("structure_trail", object(), TypeError),
        ("halted", 0, TypeError),
    ],
)
def test_market_occurrence_rejects_malformed_exact_fields(
    field_name: str,
    value: object,
    error: type[Exception],
) -> None:
    module = _protection_module()
    occurrence = _occurrence(module, "shape-valid", bid=100, ask=101)
    with pytest.raises(error):
        replace(occurrence, **{field_name: value})


def test_state_projection_and_transition_are_opaque_and_sealed() -> None:
    module = _protection_module()
    state_type, projection_type = _required(
        module,
        "PositionProtectionState",
        "ProtectionVenueProjection",
    )
    for opaque in (state_type, projection_type):
        with pytest.raises(TypeError):
            opaque()
        with pytest.raises(TypeError):
            type("ForgedProtectionCapability", (opaque,), {})


def test_projection_rejects_substituted_transition_book_or_execution() -> None:
    module = _protection_module()
    prior_book, prior_execution, _, applied = _owned_fill_fixture()
    mandate = _mandate(module)
    with pytest.raises(ValueError):
        _projection(module, _clone_opaque(applied, book=prior_book), mandate)
    with pytest.raises(ValueError):
        _projection(
            module,
            _clone_opaque(applied, execution=prior_execution),
            mandate,
        )


def test_projection_rejects_forged_transition_envelope_and_donated_proof() -> None:
    module = _protection_module()
    _, _, _, applied = _owned_fill_fixture()
    mandate = _mandate(module)
    for forged in (
        _clone_opaque(
            applied,
            disposition=VenueRecoveryDisposition.EXACT_REPLAY,
        ),
        _clone_opaque(applied, quantity_delta=applied.quantity_delta + 1),
    ):
        with pytest.raises(ValueError):
            _projection(module, forged, mandate)

    _, branch_a = _terminal_fixture(
        applied,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-proof-donor-a",
        cumulative_quantity=4,
    )
    _, branch_b = _terminal_fixture(
        applied,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-proof-donor-b",
        cumulative_quantity=4,
    )
    assert branch_a.execution == branch_b.execution
    assert branch_a.disposition == branch_b.disposition
    assert branch_a.quantity_delta == branch_b.quantity_delta
    assert branch_a.book != branch_b.book
    donated = _clone_opaque(
        branch_b,
        _protection_proof=branch_a._protection_proof,
    )
    with pytest.raises(ValueError):
        _projection(module, donated, mandate)


def test_transition_and_projection_replace_cannot_donate_proof() -> None:
    module = _protection_module()
    prior_book, _, _, applied = _owned_fill_fixture()
    mandate, projection, _ = _start(module, applied)
    with pytest.raises(TypeError):
        replace(applied, book=prior_book)
    with pytest.raises(TypeError):
        replace(
            projection,
            cursor_head=_flip_digest(projection.cursor_head),
        )
    forged = _clone_opaque(
        projection,
        cursor_head=_flip_digest(projection.cursor_head),
    )
    with pytest.raises(ValueError):
        _required(module, "initialize_position_protection")[0](mandate, forged)


@pytest.mark.parametrize(
    "field_name",
    [
        "predecessor_cursor_ordinal",
        "predecessor_cursor_head",
        "cursor_ordinal",
        "cursor_head",
        "predecessor_execution_commitment",
        "execution_commitment",
        "predecessor_blocking_effect_count",
        "predecessor_blocking_buy_effect_count",
        "blocking_effect_count",
        "blocking_buy_effect_count",
    ],
)
def test_reducer_rejects_forged_projection_cursor_execution_and_summary(
    field_name: str,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    _, projection, state = _start(module, fill)
    current = getattr(projection, field_name)
    replacement = current + 1 if type(current) is int else _flip_digest(current)
    forged = _clone_opaque(projection, **{field_name: replacement})
    result = _reduce(module, state, forged)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert result.disposition is disposition.REFUSED
    assert result.state == state
    assert result.goal is None
    assert result.critical_alert is None


def test_sibling_venue_fork_cannot_advance_from_the_same_predecessor_twice() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    _, branch_a = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-fork-a",
        cumulative_quantity=4,
    )
    _, branch_b = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-fork-b",
        cumulative_quantity=4,
    )
    projection_a = _projection(module, branch_a, mandate)
    projection_b = _projection(module, branch_b, mandate)
    assert (
        projection_a.predecessor_cursor_ordinal
        == projection_b.predecessor_cursor_ordinal
    )
    assert projection_a.predecessor_cursor_head == projection_b.predecessor_cursor_head
    assert projection_a.cursor_head != projection_b.cursor_head
    after_a = _reduce(module, state, projection_a)
    _assert_stale_unchanged(module, after_a.state, projection_b)


def test_exact_venue_replay_never_advances_cursor_or_policy() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal_command, terminal = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-terminal-replay",
        cumulative_quantity=4,
    )
    terminal_projection = _projection(module, terminal, mandate)
    after_terminal = _reduce(module, state, terminal_projection)
    replay = venue_fixtures.apply_venue_recovery_input(
        terminal.book,
        terminal.execution,
        terminal_command,
    )
    assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    replay_projection = _projection(module, replay, mandate)
    assert (
        replay_projection.predecessor_cursor_ordinal == replay_projection.cursor_ordinal
    )
    assert replay_projection.predecessor_cursor_head == replay_projection.cursor_head
    assert replay_projection.cursor_head == terminal_projection.cursor_head
    replayed = _reduce(module, after_terminal.state, replay_projection)
    (disposition,) = _required(module, "ProtectionDisposition")
    assert replayed.disposition is disposition.EXACT_REPLAY
    assert replayed.state == after_terminal.state
    assert replayed.goal is None
    assert replayed.critical_alert is None


def test_protection_cursor_and_blocking_summaries_are_per_position_scope() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, aapl_projection, state = _start(module, fill)
    msft_symbol = type(SYMBOL)("MSFT")
    msft_scope = PositionScope(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        symbol_id=msft_symbol,
    )
    msft_execution = ExecutionSnapshot.bind_verified(
        execution_core.PositionState.flat(msft_scope),
        execution_core.PositionIntegrity.CONSISTENT,
        execution_core.RootHeadIndex.empty(msft_scope),
        fill.execution.seen_facts,
    )
    msft_effect = EffectId("protection-cursor-msft-effect")
    registered = venue_fixtures.apply_venue_recovery_input(
        fill.book,
        msft_execution,
        RequestedEffect(
            input_id=VenueInputId("protection-cursor-msft-request"),
            effect_id=msft_effect,
            request_occurrence_id=RequestOccurrenceId(
                "protection-cursor-msft-occurrence"
            ),
            mandate_id=MandateId("protection-cursor-msft-mandate"),
            kind=EffectKind.SUBMIT,
            client_order_id=ClientOrderId("protection-cursor-msft-client"),
            symbol_id=msft_symbol,
            side=ExecutionSide.BUY,
            quantity=Quantity(1),
            economic_scope=b"MSFT|BUY|one",
        ),
    )
    assert registered.disposition is VenueRecoveryDisposition.APPLIED
    assert registered.book.effect(msft_effect) is not None
    aapl_terminal = venue_fixtures.apply_venue_recovery_input(
        registered.book,
        fill.execution,
        ObserveVenueStatus(
            input_id=VenueInputId("protection-cursor-aapl-terminal"),
            leg_key=BASE_LEG,
            status=VenueAttemptState.FILLED,
            observation_id=VenueObservationId(
                "protection-cursor-aapl-terminal-observation"
            ),
            cumulative_quantity=Quantity(4),
            closure_id=ClosureId("protection-cursor-aapl-terminal-closure"),
            evidence_reference=EvidenceReference(
                "protection-cursor-aapl-terminal-evidence"
            ),
        ),
    )
    assert aapl_terminal.disposition is VenueRecoveryDisposition.APPLIED
    next_projection = _projection(module, aapl_terminal, mandate)
    assert next_projection.predecessor_cursor_ordinal == aapl_projection.cursor_ordinal
    assert next_projection.predecessor_cursor_head == aapl_projection.cursor_head
    assert (
        next_projection.predecessor_blocking_effect_count
        == aapl_projection.blocking_effect_count
        == 1
    )
    assert (
        next_projection.predecessor_blocking_buy_effect_count
        == aapl_projection.blocking_buy_effect_count
        == 1
    )
    assert next_projection.blocking_effect_count == 1
    assert next_projection.blocking_buy_effect_count == 1
    result = _reduce(module, state, next_projection)
    assert result.state != state


def test_refused_and_conflicting_venue_inputs_do_not_advance_protection_cursor() -> (
    None
):
    module = _protection_module()
    _, _, fill_command, fill = _owned_fill_fixture(label="protection-nonadvancing")
    mandate, _, state = _start(module, fill)
    refused = venue_fixtures.apply_venue_recovery_input(
        fill.book,
        fill.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-refused-unknown-effect"),
            effect_id=EffectId("protection-unknown-effect"),
            leg_key=BASE_LEG,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(1),
            fact=venue_fixtures._broker_fill(
                "protection-refused-source",
                "protection-refused-root",
                quantity=1,
            ),
            evidence_digest=b"\xa1" * 32,
        ),
    )
    conflict = venue_fixtures.apply_venue_recovery_input(
        fill.book,
        fill.execution,
        replace(fill_command, evidence_digest=b"\xa2" * 32),
    )
    assert refused.disposition is VenueRecoveryDisposition.REFUSED
    assert conflict.disposition is VenueRecoveryDisposition.CONFLICT
    for transition in (refused, conflict):
        assert transition.book == fill.book
        assert transition.execution == fill.execution
        assert transition.quantity_delta == 0
        projection = _projection(module, transition, mandate)
        assert projection.predecessor_cursor_ordinal == projection.cursor_ordinal
        assert projection.predecessor_cursor_head == projection.cursor_head
        result = _reduce(module, state, projection)
        assert result.state == state
        assert result.goal is None
        assert result.critical_alert is None


def test_nonmutating_reconciliation_does_not_advance_protection_cursor() -> None:
    module = _protection_module()
    book, execution = venue_fixtures._seed_needs_review(capacity=4)
    attested = venue_fixtures._ingest(
        book,
        execution,
        venue_fixtures._human_fill(quantity=4, prior=0, resulting=4),
    )
    mandate, _, state = _start(module, attested)
    contradicted = venue_fixtures.apply_venue_recovery_input(
        attested.book,
        attested.execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-nonmutating-contradiction"),
            effect_id=BASE_EFFECT,
            leg_key=BASE_LEG,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=venue_fixtures._broker_fill(
                "protection-nonmutating-contradiction-source",
                "protection-nonmutating-contradiction-root",
                quantity=4,
                units=101,
            ),
            evidence_digest=b"\xa3" * 32,
        ),
    )
    assert contradicted.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    synced = _reduce(
        module,
        state,
        _projection(module, contradicted, mandate),
    )
    release = venue_fixtures.apply_venue_recovery_input(
        contradicted.book,
        contradicted.execution,
        ReleaseVenueLeg(
            input_id=VenueInputId("protection-nonmutating-release"),
            effect_id=BASE_EFFECT,
            leg_key=BASE_LEG,
            claim_occurrence_id=venue_fixtures.CLAIM,
            venue_cumulative_quantity=Quantity(4),
            broker_terminal_state=VenueAttemptState.CANCELED,
            actor=venue_fixtures.ACTOR,
            reason="unresolved contradiction remains blocking",
            evidence_reference=venue_fixtures.EVIDENCE,
            closure_id=ClosureId("protection-nonmutating-release-closure"),
            evidence_digest=b"\xa4" * 32,
        ),
    )
    assert release.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert release.book == contradicted.book
    assert release.execution == contradicted.execution
    assert release.quantity_delta == 0
    projection = _projection(module, release, mandate)
    assert projection.predecessor_cursor_ordinal == projection.cursor_ordinal
    assert projection.predecessor_cursor_head == projection.cursor_head
    result = _reduce(module, synced.state, projection)
    assert result.state == synced.state
    assert result.goal is None
    assert result.critical_alert is None


def test_replayed_parent_close_cannot_release_a_preclose_state() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    _, terminal = _terminal_fixture(
        fill,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-close-replay",
        cumulative_quantity=4,
    )
    terminal_projection = _projection(module, terminal, mandate)
    before_close = _reduce(module, state, terminal_projection)
    close_command, closed = _close_parent_fixture(
        terminal,
        effect_id=BASE_EFFECT,
        label="protection-close-replay",
    )
    replay = venue_fixtures.apply_venue_recovery_input(
        closed.book,
        closed.execution,
        close_command,
    )
    assert replay.disposition is VenueRecoveryDisposition.EXACT_REPLAY
    _assert_stale_unchanged(
        module,
        before_close.state,
        _projection(module, replay, mandate),
    )


def test_old_close_equal_count_aba_cannot_release_a_new_buy_parent() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, _, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    old_close_projection = _projection(module, closed, mandate)
    new_chain, _, _, _ = _append_needs_review_effect(
        closed,
        prefix="protection-new-buy",
        side=ExecutionSide.BUY,
        quantity=4,
    )
    state, current_projection, _ = _sync_transitions(
        module,
        state,
        mandate,
        new_chain,
    )
    assert (
        old_close_projection.predecessor_blocking_buy_effect_count
        == current_projection.blocking_buy_effect_count
        == 1
    )
    assert old_close_projection.cursor_head != current_projection.cursor_head
    assert state.waiting_buy_resolution is True
    _assert_stale_unchanged(module, state, old_close_projection)


def test_flat_requires_zero_quantity_and_closed_buy_and_sell_parents() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(quantity=4)
    mandate, _, state = _start(module, fill)
    buy_terminal, buy_closed = _close_base_parent(fill)
    state, _, _ = _sync_transitions(
        module,
        state,
        mandate,
        (buy_terminal, buy_closed),
    )
    sell_chain, sell_effect, sell_leg, _ = _append_needs_review_effect(
        buy_closed,
        prefix="protection-flat-sell",
        side=ExecutionSide.SELL,
        quantity=4,
    )
    state, _, _ = _sync_transitions(module, state, mandate, sell_chain)
    sell_fact = venue_fixtures._broker_fill(
        "protection-flat-sell-source",
        "protection-flat-sell-root",
        leg_key=sell_leg,
        side=ExecutionSide.SELL,
        quantity=4,
        units=110,
    )
    sold = venue_fixtures.apply_venue_recovery_input(
        sell_chain[-1].book,
        sell_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-flat-sell-fill"),
            effect_id=sell_effect,
            leg_key=sell_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=sell_fact,
            evidence_digest=b"\x94" * 32,
        ),
    )
    assert sold.disposition is VenueRecoveryDisposition.APPLIED
    assert sold.quantity_delta == -4
    assert sold.execution.position.raw_quantity == 0
    zero_with_live_sell = _reduce(
        module,
        state,
        _projection(module, sold, mandate),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert zero_with_live_sell.state.policy is not policy.FLAT
    assert zero_with_live_sell.goal is None
    _, sell_terminal = _terminal_fixture(
        sold,
        effect_id=sell_effect,
        leg_key=sell_leg,
        label="protection-flat-sell",
        cumulative_quantity=4,
    )
    terminal_only = _reduce(
        module,
        zero_with_live_sell.state,
        _projection(module, sell_terminal, mandate),
    )
    assert terminal_only.state.policy is not policy.FLAT
    assert terminal_only.goal is None
    _, sell_closed = _close_parent_fixture(
        sell_terminal,
        effect_id=sell_effect,
        label="protection-flat-sell",
    )
    finalized = _reduce(
        module,
        terminal_only.state,
        _projection(module, sell_closed, mandate),
    )
    assert finalized.state.policy is policy.FLAT
    assert finalized.state.raw_quantity == 0
    assert finalized.state.mandate == mandate
    assert finalized.goal is None
    assert sell_closed.book.effect(BASE_EFFECT) is not None
    assert sell_closed.book.effect(sell_effect) is not None


def test_zero_quantity_with_account_reconciliation_cannot_remain_flat() -> None:
    module = _protection_module()
    _, _, fill_command, fill = _owned_fill_fixture(
        label="protection-flat-reconciliation-root",
        quantity=4,
        units=100,
        capacity=4,
    )
    mandate, _, state = _start(module, fill)
    _, busted = _bust_owned_root(
        fill,
        label="protection-flat-reconciliation-bust",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=fill_command.fact.key.source_event_id,
        prior_root_quantity=4,
        prior_venue_cumulative=4,
    )
    state = _reduce(module, state, _projection(module, busted, mandate)).state
    _, terminal = _terminal_fixture(
        busted,
        effect_id=BASE_EFFECT,
        leg_key=BASE_LEG,
        label="protection-flat-reconciliation",
        cumulative_quantity=4,
    )
    state = _reduce(module, state, _projection(module, terminal, mandate)).state
    _, closed = _close_parent_fixture(
        terminal,
        effect_id=BASE_EFFECT,
        label="protection-flat-reconciliation",
    )
    flat = _reduce(module, state, _projection(module, closed, mandate))
    (policy,) = _required(module, "ProtectionPolicy")
    assert flat.state.policy is policy.FLAT
    assert flat.state.raw_quantity == 0

    external_leg = VenueLegKey(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        order_id=OrderId("protection-flat-reconciliation-external-leg"),
    )
    external_fill = venue_fixtures._broker_fill(
        "protection-flat-reconciliation-external-fill",
        "protection-flat-reconciliation-external-root",
        leg_key=external_leg,
        quantity=1,
        units=101,
    )
    ahead = venue_fixtures._apply_broker(closed.execution, external_fill)
    external_bust = BrokerTradeBustFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId(
                "protection-flat-reconciliation-external-bust"
            ),
        ),
        scope=external_fill.scope,
        root_fill_id=external_fill.root_fill_id,
        predecessor_source_event_id=external_fill.key.source_event_id,
    )
    bust_transition = apply_broker_execution_fact(
        ahead.position,
        ahead.integrity,
        ahead.root_heads,
        ahead.seen_facts,
        external_bust,
    )
    assert bust_transition.disposition is TransitionDisposition.APPLIED
    source_execution = ExecutionSnapshot(
        position=bust_transition.position,
        integrity=bust_transition.integrity,
        root_heads=bust_transition.root_heads,
        seen_facts=bust_transition.seen_facts,
    )
    assert source_execution.position.raw_quantity == 0
    reconciled = venue_fixtures.apply_venue_recovery_input(
        closed.book,
        closed.execution,
        CatchUpExecutionRegistry(
            input_id=VenueInputId("protection-flat-reconciliation-catch-up"),
            target_checkpoint=VenueExecutionCheckpoint.from_execution(closed.execution),
            prior_account_registry_count=closed.book.execution_registry_count,
            prior_account_registry_commitment=(
                closed.book.execution_registry_commitment
            ),
            prior_source_binding=closed.book.execution_binding(
                source_execution.position.scope
            ),
            source_execution=source_execution,
        ),
    )
    assert reconciled.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert reconciled.execution.position.raw_quantity == 0
    assert reconciled.execution.account_reconciliation_required is True
    assert (
        reconciled.book.effect(BASE_EFFECT).acceptance_set_state
        is AcceptanceSetState.CLOSED
    )
    projection = _projection(module, reconciled, mandate)
    assert projection.blocking_effect_count == 0
    result = _reduce(module, flat.state, projection)
    assert result.state.raw_quantity == 0
    assert result.state.policy is not policy.FLAT
    assert result.goal is None


def test_late_owned_buy_after_flat_restores_hard_bail_and_alert() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(quantity=4)
    mandate, _, state = _start(module, fill)
    buy_terminal, buy_closed = _close_base_parent(fill)
    state, _, _ = _sync_transitions(
        module,
        state,
        mandate,
        (buy_terminal, buy_closed),
    )
    sell_chain, sell_effect, sell_leg, _ = _append_needs_review_effect(
        buy_closed,
        prefix="protection-late-flat-sell",
        side=ExecutionSide.SELL,
        quantity=4,
    )
    state, _, _ = _sync_transitions(module, state, mandate, sell_chain)
    sold = venue_fixtures.apply_venue_recovery_input(
        sell_chain[-1].book,
        sell_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-late-flat-sell-fill"),
            effect_id=sell_effect,
            leg_key=sell_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=venue_fixtures._broker_fill(
                "protection-late-flat-sell-source",
                "protection-late-flat-sell-root",
                leg_key=sell_leg,
                side=ExecutionSide.SELL,
                quantity=4,
                units=110,
            ),
            evidence_digest=b"\x95" * 32,
        ),
    )
    state = _reduce(module, state, _projection(module, sold, mandate)).state
    _, sell_terminal = _terminal_fixture(
        sold,
        effect_id=sell_effect,
        leg_key=sell_leg,
        label="protection-late-flat-sell",
        cumulative_quantity=4,
    )
    state = _reduce(
        module,
        state,
        _projection(module, sell_terminal, mandate),
    ).state
    _, sell_closed = _close_parent_fixture(
        sell_terminal,
        effect_id=sell_effect,
        label="protection-late-flat-sell",
    )
    flat = _reduce(module, state, _projection(module, sell_closed, mandate))
    (policy,) = _required(module, "ProtectionPolicy")
    assert flat.state.policy is policy.FLAT
    late_chain, late_effect, late_leg, _ = _append_needs_review_effect(
        sell_closed,
        prefix="protection-late-buy",
        side=ExecutionSide.BUY,
        quantity=2,
    )
    state, _, _ = _sync_transitions(
        module,
        flat.state,
        mandate,
        late_chain,
    )
    late = venue_fixtures.apply_venue_recovery_input(
        late_chain[-1].book,
        late_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-late-buy-fill"),
            effect_id=late_effect,
            leg_key=late_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=venue_fixtures._broker_fill(
                "protection-late-buy-source",
                "protection-late-buy-root",
                leg_key=late_leg,
                side=ExecutionSide.BUY,
                quantity=2,
                units=105,
            ),
            evidence_digest=b"\x96" * 32,
        ),
    )
    recovered = _reduce(
        module,
        state,
        _projection(module, late, mandate),
    )
    assert recovered.state.raw_quantity == 2
    assert recovered.state.policy is policy.HARD_BAIL
    assert recovered.state.mandate == mandate
    assert recovered.state.waiting_buy_resolution is True
    assert recovered.critical_alert is not None
    assert recovered.goal is None


@pytest.mark.parametrize("revision_kind", ["correction", "bust"])
def test_late_sell_revision_after_flat_restores_positive_hard_bail(
    revision_kind: str,
) -> None:
    module = _protection_module()
    buy = _owned_fill_transition(
        label=f"protection-late-{revision_kind}-buy",
        quantity=4,
        capacity=4,
    )
    mandate, _, state = _start(module, buy)
    buy_terminal, buy_closed = _close_base_parent(buy)
    state, _, _ = _sync_transitions(
        module,
        state,
        mandate,
        (buy_terminal, buy_closed),
    )
    sell_chain, sell_effect, sell_leg, _ = _append_needs_review_effect(
        buy_closed,
        prefix=f"protection-late-{revision_kind}-sell",
        side=ExecutionSide.SELL,
        quantity=4,
    )
    state, _, _ = _sync_transitions(module, state, mandate, sell_chain)
    sell_fact = venue_fixtures._broker_fill(
        f"protection-late-{revision_kind}-sell-source",
        f"protection-late-{revision_kind}-sell-root",
        leg_key=sell_leg,
        side=ExecutionSide.SELL,
        quantity=4,
        units=110,
    )
    sold = venue_fixtures.apply_venue_recovery_input(
        sell_chain[-1].book,
        sell_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId(f"protection-late-{revision_kind}-sell-fill"),
            effect_id=sell_effect,
            leg_key=sell_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(4),
            fact=sell_fact,
            evidence_digest=b"\xa5" * 32,
        ),
    )
    assert sold.disposition is VenueRecoveryDisposition.APPLIED
    state = _reduce(module, state, _projection(module, sold, mandate)).state
    _, sell_terminal = _terminal_fixture(
        sold,
        effect_id=sell_effect,
        leg_key=sell_leg,
        label=f"protection-late-{revision_kind}-sell",
        cumulative_quantity=4,
    )
    state = _reduce(
        module,
        state,
        _projection(module, sell_terminal, mandate),
    ).state
    _, sell_closed = _close_parent_fixture(
        sell_terminal,
        effect_id=sell_effect,
        label=f"protection-late-{revision_kind}-sell",
    )
    flat = _reduce(module, state, _projection(module, sell_closed, mandate))
    (policy,) = _required(module, "ProtectionPolicy")
    assert flat.state.policy is policy.FLAT
    closure_id = ClosureId(f"protection-late-{revision_kind}-revision-closure")
    evidence = EvidenceReference(f"protection-late-{revision_kind}-revision-evidence")
    if revision_kind == "correction":
        _, revised = _correct_owned_root(
            sell_closed,
            label="protection-late-correction-revision",
            root_fill_id=sell_fact.root_fill_id,
            predecessor_source_event_id=sell_fact.key.source_event_id,
            prior_root_quantity=4,
            resulting_quantity=3,
            units=110,
            prior_venue_cumulative=4,
            effect_id=sell_effect,
            leg_key=sell_leg,
            scope=sell_fact.scope,
            closure_id=closure_id,
            evidence_reference=evidence,
        )
        expected_quantity = 1
    else:
        _, revised = _bust_owned_root(
            sell_closed,
            label="protection-late-bust-revision",
            root_fill_id=sell_fact.root_fill_id,
            predecessor_source_event_id=sell_fact.key.source_event_id,
            prior_root_quantity=4,
            prior_venue_cumulative=4,
            effect_id=sell_effect,
            leg_key=sell_leg,
            scope=sell_fact.scope,
            closure_id=closure_id,
            evidence_reference=evidence,
        )
        expected_quantity = 4
    assert revised.quantity_delta == expected_quantity
    assert revised.execution.position.raw_quantity == expected_quantity
    recovered = _reduce(
        module,
        flat.state,
        _projection(module, revised, mandate),
    )
    assert recovered.state.raw_quantity == expected_quantity
    assert recovered.state.policy is policy.HARD_BAIL
    assert recovered.state.mandate == mandate
    assert recovered.critical_alert is not None
    assert recovered.goal is None


def test_rollback_and_mixed_book_execution_pairs_are_nonserving() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(quantity=2)
    mandate, fill_projection, state = _start(module, fill)
    higher = _advance_owned_fill(
        fill,
        label="protection-current-pair",
        quantity=2,
        units=120,
        prior_cumulative=2,
    )
    higher_projection = _projection(module, higher, mandate)
    current = _reduce(module, state, higher_projection)
    _assert_stale_unchanged(module, current.state, fill_projection)
    mixed = _clone_opaque(higher, execution=fill.execution)
    with pytest.raises(ValueError):
        _projection(module, mixed, mandate)


def test_protection_projection_never_materializes_slow_venue_histories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _protection_module()
    venue_module = importlib.import_module("app.execution_core.venue")
    small = _owned_fill_transition(label="protection-extractor-small")
    large = small
    for index in range(32):
        chain, _, _, _ = _append_needs_review_effect(
            large,
            prefix=f"protection-extractor-volume-{index}",
            side=ExecutionSide.BUY,
            quantity=1,
        )
        large = chain[-1]

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("protection materialized a slow venue history")

    for name in (
        "effects",
        "claims",
        "owners",
        "active_attempts",
        "closure_heads",
        "execution_bindings",
        "closure_history",
        "input_records",
        "human_coverages",
        "broker_coverages",
        "reconciliations",
        "execution_reconciliations",
    ):
        monkeypatch.setattr(VenueRecoveryBook, name, property(fail_if_called))
    for name in ("effect", "active_attempt", "owner", "closure_head"):
        monkeypatch.setattr(VenueRecoveryBook, name, fail_if_called)

    sequence_type = getattr(venue_module, "_PersistentSequence")
    map_type = getattr(venue_module, "_PersistentKeyMap")
    monkeypatch.setattr(sequence_type, "get", fail_if_called)
    original_map_get = map_type.get
    calls = 0

    def counted_map_get(retained: object, key: bytes) -> object:
        nonlocal calls
        calls += 1
        return original_map_get(retained, key)

    monkeypatch.setattr(map_type, "get", counted_map_get)
    mandate = _mandate(module)
    small_projection = _projection(module, small, mandate)
    small_calls = calls
    calls = 0
    large_projection = _projection(module, large, mandate)
    large_calls = calls
    assert small_projection.blocking_effect_count == 1
    assert small_projection.blocking_buy_effect_count == 1
    assert large_projection.blocking_effect_count == 33
    assert large_projection.blocking_buy_effect_count == 33
    assert large_calls == small_calls

    extractor = getattr(venue_module, "_extract_protection_transition")
    tree = ast.parse(inspect.getsource(extractor))
    forbidden = {
        "_effect_order",
        "_claim_order",
        "_owner_order",
        "_input_ledger",
        "_closure_ledger",
        "_human_coverage_ledger",
        "_broker_coverage_ledger",
        "_reconciliation_ledger",
        "_execution_reconciliation_ledger",
        "_registry_transition_ledger",
        "_binding_order",
    }
    accessed = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in forbidden
    }
    assert not accessed, (
        f"protection extractor traverses raw venue ledgers: {accessed!r}"
    )


def test_first_owned_fill_arms_only_its_exact_mandate_after_economics() -> None:
    module = _protection_module()
    venue_transition = _owned_fill_transition(quantity=4, units=100)
    mandate, projection, state = _start(module, venue_transition)
    (policy,) = _required(module, "ProtectionPolicy")
    assert state.policy is policy.FLOOR_ONLY
    assert state.raw_quantity == 4
    assert state.execution_commitment == venue_transition.execution.commitment
    assert state.mandate == mandate
    with pytest.raises(ValueError):
        _projection(
            module,
            venue_transition,
            _mandate(module, mandate_id=MandateId("unrelated-mandate")),
        )
    assert projection.execution_commitment == venue_transition.execution.commitment


def test_formula_uses_fraction_then_one_upward_tick_conversion() -> None:
    module = _protection_module()
    venue_transition = _owned_fill_transition(quantity=4, units=100)
    _, _, state = _start(module, venue_transition)
    assert state.armed_hard_bail_trigger.exact_value == Fraction(93)
    assert state.activation_price.exact_value == Fraction(108)


def test_coarse_tick_with_no_candidate_below_average_withholds_formula() -> None:
    module = _protection_module()
    venue_transition = _owned_fill_transition(quantity=1, units=100)
    coarse = TickMetadata(tick_units=PriceUnits(100), scale=SCALE)
    mandate = _mandate(
        module,
        loss_fraction=Fraction(1, 100),
        tick=coarse,
    )
    _, projection, state = _start(module, venue_transition, mandate)
    (policy,) = _required(module, "ProtectionPolicy")
    assert projection.execution_commitment == venue_transition.execution.commitment
    assert state.policy is policy.HARD_BAIL
    assert state.formula_available is False
    assert state.armed_hard_bail_trigger is None


def test_additional_economics_tightens_but_never_loosens_armed_trigger() -> None:
    module = _protection_module()
    first = _owned_fill_transition(quantity=2, units=100)
    mandate, _, state = _start(
        module,
        first,
        _mandate(module, loss_fraction=Fraction(1, 10)),
    )
    higher = _advance_owned_fill(
        first,
        label="protection-higher-basis",
        quantity=2,
        units=120,
        prior_cumulative=2,
    )
    higher_projection = _projection(module, higher, mandate)
    higher_result = _reduce(module, state, higher_projection)
    assert higher_result.state.armed_hard_bail_trigger.exact_value == Fraction(99)
    lower = _advance_owned_fill(
        higher,
        label="protection-lower-basis",
        quantity=4,
        units=80,
        prior_cumulative=4,
    )
    lower_projection = _projection(module, lower, mandate)
    lower_result = _reduce(module, higher_result.state, lower_projection)
    assert lower_result.state.armed_hard_bail_trigger.exact_value == Fraction(99)


def test_correction_and_bust_apply_economics_before_protection_policy() -> None:
    module = _protection_module()
    _, _, fill_command, fill = _owned_fill_fixture(
        label="protection-revision-root",
        quantity=4,
        units=100,
        capacity=4,
    )
    mandate, _, state = _start(module, fill)
    _, corrected = _correct_owned_root(
        fill,
        label="protection-revision-correct",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=fill_command.fact.key.source_event_id,
        prior_root_quantity=4,
        resulting_quantity=3,
        units=110,
        prior_venue_cumulative=4,
    )
    assert corrected.quantity_delta == -1
    assert corrected.execution.position.raw_quantity == 3
    corrected_result = _reduce(
        module,
        state,
        _projection(module, corrected, mandate),
    )
    assert corrected_result.state.raw_quantity == 3
    assert corrected_result.state.execution_commitment == corrected.execution.commitment
    assert corrected_result.state.armed_hard_bail_trigger.exact_value == Fraction(102)
    _, busted = _bust_owned_root(
        corrected,
        label="protection-revision-bust",
        root_fill_id=fill_command.fact.root_fill_id,
        predecessor_source_event_id=SourceEventId("protection-revision-correct-source"),
        prior_root_quantity=3,
        prior_venue_cumulative=3,
    )
    assert busted.quantity_delta == -3
    assert busted.execution.position.raw_quantity == 0
    busted_result = _reduce(
        module,
        corrected_result.state,
        _projection(module, busted, mandate),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert busted_result.state.raw_quantity == 0
    assert busted_result.state.execution_commitment == busted.execution.commitment
    assert busted_result.state.policy is not policy.FLAT
    assert busted_result.goal is None


def test_overfill_economics_are_retained_but_never_serving() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(quantity=4, capacity=4)
    mandate, _, state = _start(module, fill)
    sell_chain, sell_effect, sell_leg, _ = _append_needs_review_effect(
        fill,
        prefix="protection-overfill-sell",
        side=ExecutionSide.SELL,
        quantity=6,
    )
    state, _, _ = _sync_transitions(module, state, mandate, sell_chain)
    overfill = venue_fixtures.apply_venue_recovery_input(
        sell_chain[-1].book,
        sell_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-overfill-sell-fill"),
            effect_id=sell_effect,
            leg_key=sell_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(6),
            fact=venue_fixtures._broker_fill(
                "protection-overfill-sell-source",
                "protection-overfill-sell-root",
                leg_key=sell_leg,
                side=ExecutionSide.SELL,
                quantity=6,
                units=90,
            ),
            evidence_digest=b"\x99" * 32,
        ),
    )
    assert overfill.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert overfill.quantity_delta == -6
    assert overfill.execution.position.raw_quantity == -2
    result = _reduce(module, state, _projection(module, overfill, mandate))
    (policy,) = _required(module, "ProtectionPolicy")
    assert result.state.raw_quantity == -2
    assert result.state.policy is policy.HARD_BAIL
    assert result.state.formula_available is False
    assert result.goal is None


def test_pending_basis_advances_quantity_but_withholds_stale_formula() -> None:
    module = _protection_module()
    _, _, buy_command, buy = _owned_fill_fixture(
        label="protection-pending-buy",
        quantity=10,
        units=100,
        capacity=10,
    )
    mandate, _, state = _start(module, buy)
    sell_chain, sell_effect, sell_leg, _ = _append_needs_review_effect(
        buy,
        prefix="protection-pending-sell",
        side=ExecutionSide.SELL,
        quantity=5,
    )
    state, _, _ = _sync_transitions(module, state, mandate, sell_chain)
    sold = venue_fixtures.apply_venue_recovery_input(
        sell_chain[-1].book,
        sell_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-pending-sell-fill"),
            effect_id=sell_effect,
            leg_key=sell_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(5),
            fact=venue_fixtures._broker_fill(
                "protection-pending-sell-source",
                "protection-pending-sell-root",
                leg_key=sell_leg,
                side=ExecutionSide.SELL,
                quantity=5,
                units=120,
            ),
            evidence_digest=b"\x9a" * 32,
        ),
    )
    assert sold.disposition is VenueRecoveryDisposition.APPLIED
    sold_result = _reduce(module, state, _projection(module, sold, mandate))
    assert sold_result.state.raw_quantity == 5
    correction = BrokerTradeCorrectFact(
        key=ExecutionFactKey(
            broker=BROKER,
            environment=ENVIRONMENT,
            account=ACCOUNT,
            source_event_id=SourceEventId("protection-pending-correct-source"),
        ),
        scope=buy_command.fact.scope,
        root_fill_id=buy_command.fact.root_fill_id,
        predecessor_source_event_id=buy_command.fact.key.source_event_id,
        revised_quantity=Quantity(7),
        revised_price=_price(101),
    )
    pending = venue_fixtures.apply_venue_recovery_input(
        sold.book,
        sold.execution,
        RecordBrokerRevisionEvidence(
            input_id=VenueInputId("protection-pending-correct-input"),
            effect_id=BASE_EFFECT,
            leg_key=BASE_LEG,
            prior_root_quantity=Quantity(10),
            prior_venue_cumulative_quantity=Quantity(10),
            resulting_venue_cumulative_quantity=Quantity(7),
            fact=correction,
            evidence_digest=b"\x9b" * 32,
        ),
    )
    assert pending.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert pending.quantity_delta == -3
    assert pending.execution.position.raw_quantity == 2
    result = _reduce(
        module,
        sold_result.state,
        _projection(module, pending, mandate),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert result.state.raw_quantity == 2
    assert result.state.execution_commitment == pending.execution.commitment
    assert result.state.formula_available is False
    assert result.state.policy is policy.HARD_BAIL
    assert result.goal is None


def test_single_below_trigger_bid_cannot_emit_hard_bail_goal() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "below-one", bid=92, ask=93, sequence=1),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert first.state.policy is policy.FLOOR_ONLY
    assert first.goal is None


def test_two_distinct_advancing_bids_trigger_sticky_hard_bail() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "hard-bid-1", bid=92, ask=93, sequence=1),
    )
    second = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "hard-bid-2",
            bid=91,
            ask=92,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    policy, urgency = _required(module, "ProtectionPolicy", "ProtectionUrgency")
    assert second.state.policy is policy.HARD_BAIL
    assert second.goal is not None
    assert second.goal.urgency is urgency.EMERGENCY
    assert second.goal.guard == mandate.emergency_guard


def test_trade_plus_distinct_bid_within_window_triggers_hard_bail() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    trade = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "hard-trade", kind="TRADE", trade=92, sequence=1),
    )
    bid = _reduce(
        module,
        trade.state,
        projection,
        _occurrence(
            module,
            "hard-pair-bid",
            bid=92,
            ask=93,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert bid.state.policy is policy.HARD_BAIL
    assert bid.goal is not None


def test_duplicate_restart_and_nonadvancing_sequence_do_not_corroborate() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    occurrence = _occurrence(module, "duplicate-bid", bid=92, ask=93, sequence=7)
    first = _reduce(module, state, projection, occurrence)
    replay = _reduce(
        module, first.state, projection, replace(occurrence, evaluation_time=109)
    )
    equal_sequence = _reduce(
        module,
        replay.state,
        projection,
        _occurrence(
            module,
            "different-id-equal-sequence",
            bid=91,
            ask=92,
            sequence=7,
            source_time=106,
            evaluation_time=110,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert replay.state.policy is policy.FLOOR_ONLY
    assert equal_sequence.state.policy is policy.FLOOR_ONLY
    assert replay.goal is None and equal_sequence.goal is None


def test_above_trigger_interruption_resets_bid_corroboration() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "reset-below-1", bid=92, ask=93, sequence=1),
    )
    interrupted = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "reset-above",
            bid=95,
            ask=96,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    restarted = _reduce(
        module,
        interrupted.state,
        projection,
        _occurrence(
            module,
            "reset-below-2",
            bid=92,
            ask=93,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert restarted.state.policy is policy.FLOOR_ONLY
    assert restarted.goal is None
    triggered = _reduce(
        module,
        restarted.state,
        projection,
        _occurrence(
            module,
            "reset-below-3",
            bid=91,
            ask=92,
            sequence=4,
            source_time=118,
            evaluation_time=122,
        ),
    )
    assert triggered.state.policy is policy.HARD_BAIL
    assert triggered.goal is not None


def test_trigger_ratchet_cannot_reuse_evidence_from_the_old_trigger() -> None:
    module = _protection_module()
    fill = _owned_fill_transition(quantity=2, units=100)
    mandate, projection, state = _start(module, fill)
    old_branch = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "old-trigger-branch", bid=92, ask=93, sequence=1),
    )
    higher = _advance_owned_fill(
        fill,
        label="protection-trigger-ratchet",
        quantity=2,
        units=120,
        prior_cumulative=2,
    )
    synced = _reduce(
        module,
        old_branch.state,
        _projection(module, higher, mandate),
    )
    assert synced.state.armed_hard_bail_trigger.exact_value == Fraction(102)
    first_new = _reduce(
        module,
        synced.state,
        _projection(module, higher, mandate),
        _occurrence(
            module,
            "new-trigger-branch-1",
            bid=101,
            ask=102,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert first_new.state.policy is policy.FLOOR_ONLY
    second_new = _reduce(
        module,
        first_new.state,
        _projection(module, higher, mandate),
        _occurrence(
            module,
            "new-trigger-branch-2",
            bid=100,
            ask=101,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    assert second_new.state.policy is policy.HARD_BAIL


def test_sequence_absent_requires_distinct_stable_occurrence_ids() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first_occurrence = _occurrence(
        module,
        "no-sequence-1",
        bid=92,
        ask=93,
        sequence=None,
    )
    first = _reduce(module, state, projection, first_occurrence)
    duplicate = _reduce(module, first.state, projection, first_occurrence)
    (policy,) = _required(module, "ProtectionPolicy")
    assert duplicate.state.policy is policy.FLOOR_ONLY
    second = _reduce(
        module,
        duplicate.state,
        projection,
        _occurrence(
            module,
            "no-sequence-2",
            bid=91,
            ask=92,
            sequence=None,
            source_time=106,
            evaluation_time=110,
        ),
    )
    assert second.state.policy is policy.HARD_BAIL
    assert second.goal is not None


def test_source_time_regression_and_halt_reopen_start_fresh_branches() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "time-before-halt",
            bid=92,
            ask=93,
            sequence=None,
            source_time=100,
            evaluation_time=105,
        ),
    )
    regressed = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "time-regressed",
            bid=91,
            ask=92,
            sequence=None,
            source_time=99,
            evaluation_time=104,
        ),
    )
    halted = _reduce(
        module,
        regressed.state,
        projection,
        _occurrence(
            module,
            "halted-market",
            bid=91,
            ask=92,
            sequence=None,
            source_time=106,
            evaluation_time=110,
            halted=True,
        ),
    )
    reopened_first = _reduce(
        module,
        halted.state,
        projection,
        _occurrence(
            module,
            "reopen-below-1",
            bid=92,
            ask=93,
            sequence=None,
            source_time=112,
            evaluation_time=116,
            market_epoch=1,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert reopened_first.state.policy is policy.FLOOR_ONLY
    reopened_second = _reduce(
        module,
        reopened_first.state,
        projection,
        _occurrence(
            module,
            "reopen-below-2",
            bid=91,
            ask=92,
            sequence=None,
            source_time=118,
            evaluation_time=122,
            market_epoch=1,
        ),
    )
    assert reopened_second.state.policy is policy.HARD_BAIL


@pytest.mark.parametrize(
    "case",
    ["stale", "crossed", "wrong_scope", "wrong_source", "halted"],
)
def test_ineligible_market_data_cannot_change_policy_or_emit_goal(case: str) -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    kwargs: dict[str, object] = {"bid": 92, "ask": 93, "sequence": 1}
    if case == "stale":
        kwargs.update(source_time=1, evaluation_time=100)
    elif case == "crossed":
        kwargs.update(bid=94, ask=93)
    elif case == "wrong_scope":
        kwargs.update(
            position_scope=PositionScope(
                broker=BROKER,
                environment=ENVIRONMENT,
                account=ACCOUNT,
                symbol_id=type(SYMBOL)("MSFT"),
            )
        )
    elif case == "wrong_source":
        (source_type,) = _required(execution_core, "MarketDataSourceId")
        kwargs.update(source_id=source_type("unapproved-feed"))
    else:
        kwargs.update(halted=True)
    result = _reduce(
        module,
        state,
        projection,
        _occurrence(module, f"ineligible-{case}", **kwargs),
    )
    assert result.state == state
    assert result.goal is None


@pytest.mark.parametrize(
    "case",
    [
        "nonpositive",
        "misaligned",
        "tick_mismatch",
        "wrong_session",
        "future_source_time",
        "step_deviation",
    ],
)
def test_capital_relevant_market_eligibility_failures_are_inert(case: str) -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    sequence = 1
    source_time = 100
    if case == "step_deviation":
        anchored = _reduce(
            module,
            state,
            projection,
            _occurrence(module, "step-anchor", bid=100, ask=101, sequence=1),
        )
        state = anchored.state
        sequence = 2
        source_time = 106
    occurrence = _occurrence(
        module,
        f"capital-ineligible-{case}",
        bid=160 if case == "step_deviation" else 92,
        ask=161 if case == "step_deviation" else 93,
        sequence=sequence,
        source_time=source_time,
        evaluation_time=source_time + 4,
    )
    if case == "nonpositive":
        occurrence = replace(occurrence, best_bid=_price(0), best_ask=_price(1))
    elif case == "misaligned":
        occurrence = replace(
            occurrence,
            best_bid=_price(93, tick_units=2),
            best_ask=_price(94, tick_units=2),
        )
    elif case == "tick_mismatch":
        occurrence = replace(
            occurrence,
            best_bid=_price(92, tick_units=2),
            best_ask=_price(94, tick_units=2),
        )
    elif case == "wrong_session":
        occurrence = replace(
            occurrence,
            session_id=execution_core.SessionId("session-rth-other"),
        )
    elif case == "future_source_time":
        occurrence = replace(occurrence, source_time=110, evaluation_time=105)
    result = _reduce(module, state, projection, occurrence)
    assert result.state == state
    assert result.goal is None
    assert result.critical_alert is None


@pytest.mark.parametrize(
    ("case", "triggers"),
    [
        ("age-at-boundary", True),
        ("age-one-past", False),
        ("locked-quote", True),
        ("crossed-quote", False),
        ("equal-source-time", True),
        ("regressed-source-time", False),
        ("step-at-boundary", True),
        ("step-one-past", False),
    ],
)
def test_market_eligibility_boundaries_use_trigger_behavior_as_acceptance_oracle(
    case: str,
    triggers: bool,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate = _mandate(
        module,
        max_age=10 if case.startswith("age-") else 100,
        max_step_fraction=Fraction(1, 2),
    )
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    if case.startswith("step-"):
        anchor = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"{case}-anchor",
                bid=100,
                ask=101,
                sequence=1,
                source_time=100,
                evaluation_time=104,
            ),
        )
        first_bid = 50 if case == "step-at-boundary" else 49
        first = _reduce(
            module,
            anchor.state,
            projection,
            _occurrence(
                module,
                f"{case}-first",
                bid=first_bid,
                ask=first_bid + 1,
                sequence=2,
                source_time=106,
                evaluation_time=110,
            ),
        )
        second_bid = 49 if case == "step-at-boundary" else 48
        second = _reduce(
            module,
            first.state,
            projection,
            _occurrence(
                module,
                f"{case}-second",
                bid=second_bid,
                ask=second_bid + 1,
                sequence=3,
                source_time=112,
                evaluation_time=116,
            ),
        )
    else:
        first_ask = 92 if case == "locked-quote" else 93
        first = _reduce(
            module,
            state,
            projection,
            _occurrence(
                module,
                f"{case}-first",
                bid=92,
                ask=first_ask,
                sequence=1,
                source_time=100,
                evaluation_time=110 if case.startswith("age-") else 104,
            ),
        )
        second_source_time = 100 if case == "equal-source-time" else 106
        if case == "regressed-source-time":
            second_source_time = 99
        second_ask = 90 if case == "crossed-quote" else 91
        second = _reduce(
            module,
            first.state,
            projection,
            _occurrence(
                module,
                f"{case}-second",
                bid=91,
                ask=second_ask,
                sequence=2,
                source_time=second_source_time,
                evaluation_time=(
                    117
                    if case == "age-one-past"
                    else 116
                    if case == "age-at-boundary"
                    else 110
                ),
            ),
        )
    (policy,) = _required(module, "ProtectionPolicy")
    assert (second.state.policy is policy.HARD_BAIL) is triggers
    assert (second.goal is not None) is triggers


@pytest.mark.parametrize(
    ("case", "triggers"),
    [
        ("aligned", True),
        ("misaligned", False),
        ("metadata-mismatch", False),
    ],
)
def test_tick_alignment_and_metadata_compatibility_are_independently_required(
    case: str,
    triggers: bool,
) -> None:
    module = _protection_module()
    uses_two_unit_authority = case != "metadata-mismatch"
    fill = _owned_fill_transition(
        label=f"protection-tick-{case}",
        tick_units=2 if uses_two_unit_authority else 1,
    )
    mandate = _mandate(
        module,
        tick=(
            TickMetadata(tick_units=PriceUnits(2), scale=SCALE)
            if uses_two_unit_authority
            else TICK
        ),
    )
    mandate, _, state = _start(module, fill, mandate)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first = _occurrence(
        module,
        f"tick-{case}-first",
        bid=92,
        ask=94,
        sequence=1,
    )
    if case == "misaligned":
        first = replace(first, best_bid=_price(93, tick_units=2))
    elif case == "metadata-mismatch":
        first = replace(
            first,
            best_bid=_price(92, tick_units=2),
            best_ask=_price(94, tick_units=2),
        )
    first_result = _reduce(module, state, projection, first)
    second = _occurrence(
        module,
        f"tick-{case}-second",
        bid=90 if uses_two_unit_authority else 91,
        ask=92,
        sequence=2,
        source_time=106,
        evaluation_time=110,
    )
    if uses_two_unit_authority:
        second = replace(
            second,
            best_bid=_price(90, tick_units=2),
            best_ask=_price(92, tick_units=2),
        )
    second_result = _reduce(module, first_result.state, projection, second)
    (policy,) = _required(module, "ProtectionPolicy")
    assert (second_result.state.policy is policy.HARD_BAIL) is triggers
    assert (second_result.goal is not None) is triggers


def test_market_epoch_regression_cannot_reuse_reopen_evidence() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    halted = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "epoch-halt",
            bid=100,
            ask=101,
            sequence=1,
            halted=True,
        ),
    )
    reopened = _reduce(
        module,
        halted.state,
        projection,
        _occurrence(
            module,
            "epoch-reopen",
            bid=100,
            ask=101,
            sequence=2,
            source_time=106,
            evaluation_time=110,
            market_epoch=1,
        ),
    )
    regressed = _reduce(
        module,
        reopened.state,
        projection,
        _occurrence(
            module,
            "epoch-regression",
            bid=92,
            ask=93,
            sequence=3,
            source_time=112,
            evaluation_time=116,
            market_epoch=0,
        ),
    )
    assert regressed.state == reopened.state
    assert regressed.goal is None


@pytest.mark.parametrize(
    ("order", "gap", "triggers"),
    [
        ("trade-bid", 10, True),
        ("trade-bid", 11, False),
        ("bid-trade", 10, True),
        ("bid-trade", 11, False),
    ],
)
def test_trade_bid_corroboration_honors_both_orders_and_window_boundary(
    order: str,
    gap: int,
    triggers: bool,
) -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(
        module,
        fill,
        _mandate(module, max_age=100, corroboration_window=10),
    )
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    first_kind, second_kind = order.split("-")
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            f"window-{order}-first-{gap}",
            kind=first_kind.upper().replace("BID", "BEST_BID"),
            bid=92 if first_kind == "bid" else None,
            ask=93 if first_kind == "bid" else None,
            trade=92 if first_kind == "trade" else None,
            sequence=1,
            source_time=100,
            evaluation_time=104,
        ),
    )
    second = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            f"window-{order}-second-{gap}",
            kind=second_kind.upper().replace("BID", "BEST_BID"),
            bid=91 if second_kind == "bid" else None,
            ask=92 if second_kind == "bid" else None,
            trade=91 if second_kind == "trade" else None,
            sequence=2,
            source_time=100 + gap,
            evaluation_time=104 + gap,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert (second.state.policy is policy.HARD_BAIL) is triggers
    assert (second.goal is not None) is triggers


def test_trade_bid_pair_with_one_price_above_trigger_cannot_trip_hard_bail() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    trade = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "mixed-threshold-trade", kind="TRADE", trade=92),
    )
    bid = _reduce(
        module,
        trade.state,
        projection,
        _occurrence(
            module,
            "mixed-threshold-bid",
            bid=94,
            ask=95,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert bid.state.policy is policy.FLOOR_ONLY
    assert bid.goal is None


def test_activation_requires_the_exact_tick_rounded_approved_gain_boundary() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    below = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "activation-below", bid=107, ask=108, sequence=1),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert below.state.policy is policy.FLOOR_ONLY
    exact = _reduce(
        module,
        below.state,
        projection,
        _occurrence(
            module,
            "activation-exact",
            bid=108,
            ask=109,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    assert exact.state.policy is policy.TRAIL_ACTIVE
    assert exact.state.high_watermark.exact_value == Fraction(108)
    assert exact.state.trail.exact_value == Fraction(100)
    assert exact.goal is None


def test_activation_and_hybrid_trail_ratchet_use_available_components_only() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "activation-bid",
            bid=120,
            ask=121,
            sequence=1,
            atr_distance=3,
            structure_trail=112,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert activated.state.policy is policy.TRAIL_ACTIVE
    assert activated.state.high_watermark.exact_value == Fraction(120)
    assert activated.state.trail.exact_value == Fraction(113)
    without_components = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "higher-no-components",
            bid=125,
            ask=126,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    assert without_components.state.high_watermark.exact_value == Fraction(125)
    assert without_components.state.trail.exact_value == Fraction(115)


def test_fill_correction_and_bust_after_trail_activation_never_deactivate_or_loosen() -> (
    None
):
    module = _protection_module()
    fill = _owned_fill_transition(quantity=4, capacity=8)
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "trail-before-economics", bid=120, ask=121, sequence=1),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert activated.state.policy is policy.TRAIL_ACTIVE
    high_watermark = activated.state.high_watermark
    trail = activated.state.trail

    buy_chain, buy_effect, buy_leg, _ = _append_needs_review_effect(
        closed,
        prefix="protection-trail-late-buy",
        side=ExecutionSide.BUY,
        quantity=2,
    )
    state, _, _ = _sync_transitions(
        module,
        activated.state,
        mandate,
        buy_chain,
    )
    buy_fact = venue_fixtures._broker_fill(
        "protection-trail-late-buy-source",
        "protection-trail-late-buy-root",
        leg_key=buy_leg,
        quantity=2,
        units=140,
    )
    bought = venue_fixtures.apply_venue_recovery_input(
        buy_chain[-1].book,
        buy_chain[-1].execution,
        RecordBrokerFillEvidence(
            input_id=VenueInputId("protection-trail-late-buy-fill"),
            effect_id=buy_effect,
            leg_key=buy_leg,
            prior_cumulative_quantity=Quantity(0),
            resulting_cumulative_quantity=Quantity(2),
            fact=buy_fact,
            evidence_digest=b"\xa6" * 32,
        ),
    )
    bought_result = _reduce(
        module,
        state,
        _projection(module, bought, mandate),
    )
    assert bought_result.state.policy is policy.TRAIL_ACTIVE
    assert bought_result.state.high_watermark == high_watermark
    assert bought_result.state.trail == trail
    _, corrected = _correct_owned_root(
        bought,
        label="protection-trail-late-buy-correction",
        root_fill_id=buy_fact.root_fill_id,
        predecessor_source_event_id=buy_fact.key.source_event_id,
        prior_root_quantity=2,
        resulting_quantity=1,
        units=80,
        prior_venue_cumulative=2,
        effect_id=buy_effect,
        leg_key=buy_leg,
        scope=buy_fact.scope,
    )
    corrected_result = _reduce(
        module,
        bought_result.state,
        _projection(module, corrected, mandate),
    )
    assert corrected_result.state.policy is policy.TRAIL_ACTIVE
    assert corrected_result.state.high_watermark == high_watermark
    assert corrected_result.state.trail == trail
    _, busted = _bust_owned_root(
        corrected,
        label="protection-trail-late-buy-bust",
        root_fill_id=buy_fact.root_fill_id,
        predecessor_source_event_id=SourceEventId(
            "protection-trail-late-buy-correction-source"
        ),
        prior_root_quantity=1,
        prior_venue_cumulative=1,
        effect_id=buy_effect,
        leg_key=buy_leg,
        scope=buy_fact.scope,
    )
    busted_result = _reduce(
        module,
        corrected_result.state,
        _projection(module, busted, mandate),
    )
    assert busted_result.state.raw_quantity == 4
    assert busted_result.state.policy is policy.TRAIL_ACTIVE
    assert busted_result.state.high_watermark == high_watermark
    assert busted_result.state.trail == trail
    assert busted_result.goal is None


def test_trail_never_decreases_or_reuses_missing_optional_components() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(
            module,
            "trail-tight-atr",
            bid=120,
            ask=121,
            sequence=1,
            atr_distance=1,
        ),
    )
    assert activated.state.trail.exact_value == Fraction(118)
    missing = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "trail-missing-optional",
            bid=125,
            ask=126,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    assert missing.state.high_watermark.exact_value == Fraction(125)
    assert missing.state.trail.exact_value == Fraction(118)
    falling = _reduce(
        module,
        missing.state,
        projection,
        _occurrence(
            module,
            "trail-falling-bid",
            bid=124,
            ask=125,
            sequence=3,
            source_time=112,
            evaluation_time=116,
            atr_distance=10,
            structure_trail=100,
        ),
    )
    assert falling.state.high_watermark.exact_value == Fraction(125)
    assert falling.state.trail.exact_value == Fraction(118)


def test_hard_bail_outranks_trail_exit_on_the_same_evidence_branch() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "priority-activation", bid=120, ask=121, sequence=1),
    )
    first = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "priority-below-both-1",
            bid=92,
            ask=93,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    second = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "priority-below-both-2",
            bid=91,
            ask=92,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    policy, urgency = _required(module, "ProtectionPolicy", "ProtectionUrgency")
    assert second.state.policy is policy.HARD_BAIL
    assert second.goal is not None
    assert second.goal.urgency is urgency.EMERGENCY
    assert second.goal.guard == mandate.emergency_guard


def test_two_trail_bids_emit_normal_goal_with_normal_guard() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "trail-activation", bid=120, ask=121, sequence=1),
    )
    first = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "trail-below-1",
            bid=110,
            ask=111,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    second = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "trail-below-2",
            bid=109,
            ask=110,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    policy, urgency = _required(module, "ProtectionPolicy", "ProtectionUrgency")
    assert second.state.policy is policy.EXIT_NORMAL
    assert second.goal is not None
    assert second.goal.urgency is urgency.NORMAL
    assert second.goal.guard == mandate.normal_guard


def test_exit_normal_escalates_to_sticky_hard_bail() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "escalate-activation", bid=120, ask=121, sequence=1),
    )
    trail_one = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "escalate-trail-1",
            bid=110,
            ask=111,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    normal = _reduce(
        module,
        trail_one.state,
        projection,
        _occurrence(
            module,
            "escalate-trail-2",
            bid=109,
            ask=110,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert normal.state.policy is policy.EXIT_NORMAL
    hard_one = _reduce(
        module,
        normal.state,
        projection,
        _occurrence(
            module,
            "escalate-hard-1",
            bid=92,
            ask=93,
            sequence=4,
            source_time=118,
            evaluation_time=122,
        ),
    )
    hard_two = _reduce(
        module,
        hard_one.state,
        projection,
        _occurrence(
            module,
            "escalate-hard-2",
            bid=91,
            ask=92,
            sequence=5,
            source_time=124,
            evaluation_time=128,
        ),
    )
    (urgency,) = _required(module, "ProtectionUrgency")
    assert hard_two.state.policy is policy.HARD_BAIL
    assert hard_two.goal is not None
    assert hard_two.goal.urgency is urgency.EMERGENCY
    assert hard_two.goal.guard == mandate.emergency_guard


def test_buy_wait_is_orthogonal_and_parent_close_not_leg_terminal_releases() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, projection, state = _start(module, fill)
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "wait-activation", bid=120, ask=121, sequence=1),
    )
    first = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "wait-trail-1",
            bid=110,
            ask=111,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    waiting = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "wait-trail-2",
            bid=109,
            ask=110,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert waiting.state.policy is policy.EXIT_NORMAL
    assert waiting.state.waiting_buy_resolution is True
    assert waiting.goal is None
    terminal, closed = _close_base_parent(fill)
    terminal_projection = _projection(module, terminal, mandate)
    terminal_only = _reduce(module, waiting.state, terminal_projection)
    assert terminal_only.state.policy is policy.EXIT_NORMAL
    assert terminal_only.state.waiting_buy_resolution is True
    closed_projection = _projection(module, closed, mandate)
    released = _reduce(module, terminal_only.state, closed_projection)
    assert released.state.policy is policy.EXIT_NORMAL
    assert released.state.waiting_buy_resolution is False
    assert released.goal is not None


def test_hard_bail_wait_preserves_emergency_policy_until_exact_parent_close() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, projection, state = _start(module, fill)
    first = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "hard-wait-1", bid=92, ask=93, sequence=1),
    )
    waiting = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "hard-wait-2",
            bid=91,
            ask=92,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert waiting.state.policy is policy.HARD_BAIL
    assert waiting.state.waiting_buy_resolution is True
    assert waiting.goal is None
    terminal, closed = _close_base_parent(fill)
    terminal_only = _reduce(
        module,
        waiting.state,
        _projection(module, terminal, mandate),
    )
    assert terminal_only.state.policy is policy.HARD_BAIL
    assert terminal_only.state.waiting_buy_resolution is True
    assert terminal_only.goal is None
    released = _reduce(
        module,
        terminal_only.state,
        _projection(module, closed, mandate),
    )
    (urgency,) = _required(module, "ProtectionUrgency")
    assert released.state.policy is policy.HARD_BAIL
    assert released.state.waiting_buy_resolution is False
    assert released.goal is not None
    assert released.goal.urgency is urgency.EMERGENCY
    assert released.goal.guard == mandate.emergency_guard


def test_late_acceptance_invalidates_release_and_preserves_normal_policy() -> None:
    module = _protection_module()
    fill = _owned_fill_transition()
    mandate, _, state = _start(module, fill)
    terminal, closed = _close_base_parent(fill)
    state, projection, _ = _sync_transitions(module, state, mandate, (terminal, closed))
    activated = _reduce(
        module,
        state,
        projection,
        _occurrence(module, "invalidate-activation", bid=120, ask=121, sequence=1),
    )
    first = _reduce(
        module,
        activated.state,
        projection,
        _occurrence(
            module,
            "invalidate-trail-1",
            bid=110,
            ask=111,
            sequence=2,
            source_time=106,
            evaluation_time=110,
        ),
    )
    exited = _reduce(
        module,
        first.state,
        projection,
        _occurrence(
            module,
            "invalidate-trail-2",
            bid=109,
            ask=110,
            sequence=3,
            source_time=112,
            evaluation_time=116,
        ),
    )
    late_leg = VenueLegKey(
        broker=BROKER,
        environment=ENVIRONMENT,
        account=ACCOUNT,
        order_id=OrderId("protection-late-buy-leg"),
    )
    invalidated = venue_fixtures.apply_venue_recovery_input(
        closed.book,
        closed.execution,
        DiscoverVenueLeg(
            input_id=VenueInputId("protection-late-buy-discovery"),
            effect_id=BASE_EFFECT,
            leg_key=late_leg,
            observation_id=VenueObservationId("protection-late-buy-discovery"),
        ),
    )
    assert invalidated.disposition is VenueRecoveryDisposition.RECONCILIATION_REQUIRED
    assert (
        invalidated.book.effect(BASE_EFFECT).acceptance_set_state
        is AcceptanceSetState.INVALIDATED
    )
    result = _reduce(
        module,
        exited.state,
        _projection(module, invalidated, mandate),
    )
    (policy,) = _required(module, "ProtectionPolicy")
    assert result.state.policy is policy.EXIT_NORMAL
    assert result.state.waiting_buy_resolution is True
    assert result.goal is None


def test_goal_carries_complete_current_policy_binding() -> None:
    module = _protection_module()
    mandate, closed, state, goal = _emergency_goal_fixture(
        module,
        label="goal-binding",
    )
    (urgency,) = _required(module, "ProtectionUrgency")
    assert goal.side is ExecutionSide.SELL
    assert goal.residual == Quantity(4)
    assert goal.urgency is urgency.EMERGENCY
    assert goal.guard == mandate.emergency_guard
    assert goal.deadline == mandate.deadline
    assert goal.session_id == mandate.session_id
    assert goal.mandate_id == mandate.mandate_id
    assert goal.maximum_goal_rate == mandate.maximum_goal_rate
    assert goal.residual.value <= mandate.maximum_quantity.value
    assert goal.execution_commitment == closed.execution.commitment
    assert goal.protection_commitment == state.commitment
    assert type(goal.protection_commitment) is bytes
    assert len(goal.protection_commitment) == 32
    with pytest.raises(FrozenInstanceError):
        goal.residual = Quantity(1)

    changed_mandate = _mandate(
        module,
        configuration_version="protection-v2",
    )
    _, changed_closed, changed_state, changed_goal = _emergency_goal_fixture(
        module,
        label="goal-binding-changed-config",
        mandate=changed_mandate,
    )
    assert changed_goal.execution_commitment == changed_closed.execution.commitment
    assert changed_goal.execution_commitment == goal.execution_commitment
    assert changed_goal.protection_commitment == changed_state.commitment
    assert changed_goal.protection_commitment != goal.protection_commitment


def test_execution_goal_rejects_every_malformed_authority_binding() -> None:
    module = _protection_module()
    mandate, _, _, goal = _emergency_goal_fixture(
        module,
        label="goal-validation",
    )
    invalid = (
        ("side", "SELL", TypeError),
        ("side", ExecutionSide.BUY, ValueError),
        ("residual", 1, TypeError),
        ("residual", Quantity(0), ValueError),
        ("urgency", "EMERGENCY", TypeError),
        ("guard", object(), TypeError),
        ("deadline", True, TypeError),
        ("deadline", -1, ValueError),
        ("session_id", "session-rth-1", TypeError),
        ("mandate_id", "mandate", TypeError),
        ("maximum_goal_rate", True, TypeError),
        ("maximum_goal_rate", 0, ValueError),
        ("execution_commitment", "commitment", TypeError),
        ("execution_commitment", b"x" * 31, ValueError),
        ("protection_commitment", "commitment", TypeError),
        ("protection_commitment", b"x" * 33, ValueError),
    )
    for field_name, value, error in invalid:
        with pytest.raises(error):
            replace(goal, **{field_name: value})
    assert goal.guard == mandate.emergency_guard


def test_goal_translation_remains_subject_to_m1c_create_and_claim_gates() -> None:
    module = _protection_module()
    _, closed, _, goal = _emergency_goal_fixture(
        module,
        label="goal-m1c",
    )
    request = BrokerEffectRequest(
        effect_id=EffectId("protection-goal-m1c-effect"),
        request_occurrence_id=RequestOccurrenceId("protection-goal-m1c-occurrence"),
        mandate_id=goal.mandate_id,
        kind=EffectKind.SUBMIT,
        client_order_id=ClientOrderId("protection-goal-m1c-client"),
        symbol_id=SYMBOL,
        side=goal.side,
        quantity=goal.residual,
        economic_scope=goal.protection_commitment,
        target_leg_key=None,
    )
    create = CreateBrokerEffect(
        input_id=execution_core.AuthorityInputId("protection-goal-m1c-create"),
        session_id=goal.session_id,
        request=request,
        manual_flatten_id=None,
        emergency_grant_id=None,
    )
    for label, authority, reason in (
        (
            "kill",
            _forge_authority_predecessor(
                closed.book,
                session_id=goal.session_id,
                kill_engaged=True,
            ),
            AuthorityReason.KILL_ENGAGED,
        ),
        (
            "fence",
            _forge_authority_predecessor(
                closed.book,
                session_id=goal.session_id,
                fence=SupervisorFence.RECONCILIATION_ONLY,
            ),
            AuthorityReason.SUPERVISOR_FENCE_BLOCKED,
        ),
    ):
        denied = apply_execution_authority_input(authority, closed.execution, create)
        assert denied.disposition is AuthorityDisposition.REFUSED, label
        assert denied.reason is reason, label
        assert denied.state == authority, label

    eligible = _forge_authority_predecessor(
        closed.book,
        session_id=goal.session_id,
    )
    created = apply_execution_authority_input(eligible, closed.execution, create)
    assert created.disposition is AuthorityDisposition.APPLIED
    assert created.reason is None
    retained = created.state.venue.effect(request.effect_id)
    assert retained is not None
    assert retained.state is BrokerEffectState.REQUESTED
    assert retained.claim_occurrence_id is None
    claim = ClaimEffect(
        input_id=execution_core.AuthorityInputId("protection-goal-m1c-claim"),
        effect_id=request.effect_id,
        claim_occurrence_id=ClaimOccurrenceId("protection-goal-m1c-claim"),
    )
    for label, field_name, value, reason in (
        ("kill", "kill_engaged", True, AuthorityReason.KILL_ENGAGED),
        (
            "fence",
            "supervisor_fence",
            SupervisorFence.RECONCILIATION_ONLY,
            AuthorityReason.SUPERVISOR_FENCE_BLOCKED,
        ),
    ):
        regated = copy(created.state)
        object.__setattr__(regated, field_name, value)
        denied = apply_execution_authority_input(
            regated,
            closed.execution,
            claim,
        )
        assert denied.disposition is AuthorityDisposition.REFUSED, label
        assert denied.reason is reason, label
        assert denied.state == regated, label
        assert denied.state.budget == regated.budget, label
        retained = denied.state.venue.effect(request.effect_id)
        assert retained is not None
        assert retained.state is BrokerEffectState.REQUESTED
        assert retained.claim_occurrence_id is None
        assert denied.fresh_claim is None


def test_value_objects_expose_no_mutating_or_broker_capability_fields() -> None:
    module = _protection_module()
    forbidden = {
        "broker_effect",
        "claim",
        "dispatch",
        "emergency_grant",
        "may_execute",
        "parent_closed",
        "buy_clear",
        "flat_ready",
    }
    for name in (
        "ProtectionMandate",
        "PositionProtectionState",
        "ProtectionVenueProjection",
        "ExecutionGoal",
    ):
        (value_type,) = _required(module, name)
        assert forbidden.isdisjoint(field.name for field in fields(value_type))
